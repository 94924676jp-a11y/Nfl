"""Automatic authoritative postgame ingestion and scoring.

    python3.12 -m nfl.research.postgame --season 2026

Discovers completed games that have a sealed pregame forecast, fetches the
authoritative outcome, stores it immutably with its provenance, scores only
the metrics whose estimand genuinely matches, and appends to the prospective
ledger. It never writes into a sealed forecast.

WHY ESTIMAND MATCHING IS THE HARD PART, NOT THE ARITHMETIC.

`actuals.team_actuals` already labels what it produces: `team_carries` is
EXACT, while `team_off_snaps` is a SURROGATE whose own note says it is "NOT
the same quantity -- offensive snaps from snap_counts include
penalty-nullified plays that appear here as separate no_play rows", and
`team_dropbacks_part` is an upper bound rather than the participation-matched
count. Scoring a forecast of one quantity against a realisation of another
produces a number that looks like skill and measures a definition. This
pipeline therefore scores EXACT matches and refuses the rest BY NAME.

That refusal has teeth: the largest miss in the manual SF@LA review -- LA
running 57 plays against a 65.65 forecast -- was a play count scored against
a snap-count estimand. The automatic pipeline declines to reproduce it, and
says why.

WHAT IT WILL NOT INVENT. Snap and route estimands are not derivable from
play-by-play and are never fabricated from it. RB/WR/TE rushing yards remain
unmodelled and are not scored. A metric a game never forecast stays
NO_FORECAST_MISSING_PREGAME_INPUT rather than being scored as a zero.

THREE THINGS A SCORING PIPELINE GETS WRONG BY DEFAULT, GUARDED HERE.

1. COMPLETION IS NOT KICKOFF-PASSED. The first version scored any sealed game
   whose kickoff clock had passed. A game in progress, suspended, postponed or
   published with partial play-by-play would have been scored against a
   part-played realisation, and the result would have looked like a forecast
   error. Finality is now PROVEN from the authoritative bytes -- see
   `game_finality` -- and a game that cannot prove it produces ZERO scoring
   rows under the named state POSTGAME_NOT_FINAL.

2. ROWS ARE NOT A SAMPLE SIZE. Nineteen sealed artifacts across two completed
   games generate thousands of scoring rows, and none of that is nineteen
   games of evidence. Every row now carries the identity a unit can be counted
   from -- forecast_id, game_id, candidate, cutoff, metric, player_id,
   outcome_hash -- and `accounting` reports rows, graded metrics, distinct
   games, distinct player-games and distinct candidate forecasts SEPARATELY,
   each with its unit declared. Candidate variants of one game are paired
   comparisons on that game, not independent games.

3. AN OUTCOME CAN BE REVISED. nflverse restates play-by-play. Only one outcome
   version per (forecast_id, game_id, metric, player_id) may be CURRENT;
   earlier versions stay in the file, immutable, marked SUPERSEDED with the
   hash that superseded them. Calibration reads CURRENT only; an audit may ask
   for every version. Nothing is ever deleted or rewritten.
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import gzip
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State   # noqa: E402
from nfl.research import sealed_index as SI                           # noqa: E402
from nfl.research.shadow import actuals as ACT                        # noqa: E402
from nfl.research.shadow import score as SC                           # noqa: E402

SPEC_VERSION = 'postgame-ingestion-1'

STORE = _REPO / 'nfl' / 'research' / 'postgame'
LEDGER = STORE / 'PROSPECTIVE_LEDGER.jsonl'

# The approved postgame source hierarchy. Authority 1 is the only source this
# pipeline will SCORE from; anything lower is recorded and refused for
# scoring, because a transcription cannot be re-derived by a third party.
SOURCES = (
    {'rank': 1, 'name': 'nflverse_pbp', 'scoreable': True,
     'url': 'https://github.com/nflverse/nflverse-data/releases/download/'
            'pbp/play_by_play_{season}.csv.gz'},
    {'rank': 9, 'name': 'external_delivery', 'scoreable': False,
     'url': None,
     'note': 'an owner or agent transcription. Recorded for audit, never '
             'scored: a number nobody else can re-derive from bytes is not '
             'an authoritative outcome.'},
)

# METRICS WHOSE FORECAST ESTIMAND EXACTLY MATCHES THE REALISED DEFINITION.
# Everything absent from this map is refused by name rather than scored.
EXACT_ESTIMANDS = {
    'qb/att': ('qb', 'att'),
    'qb/cmp': ('qb', 'cmp'),
    'qb/pyds': ('qb', 'pyds'),
    'qb/ptd': ('qb', 'ptd'),
    'qb/int': ('qb', 'int'),
    'qb/sacks': ('qb', 'sacks'),
    'qb/db': ('qb', 'db'),
    'rushing/carries': ('rushing', 'carries'),
    'receiving/targets': ('receiving', 'targets'),
    'receiving/receptions': ('receiving', 'receptions'),
    # THE ACTUALS DICT CALLS THIS `rec_yds`. Mapping it to
    # 'receiving_yards' silently produced None, which the old fallback then
    # turned into a realised zero -- Nacua scored 0 against an actual 74.
    'receiving/receiving_yards': ('receiving', 'rec_yds'),
    'team_volume/team_carries': ('team', 'team_carries'),
}

# Refused by name, with the reason attached to every row.
REFUSED_ESTIMANDS = {
    'team_volume/team_off_snaps':
        'ESTIMAND_MISMATCH_SNAP_COUNT_VS_PLAY_ROW: the forecast is of '
        'offensive snaps from snap_counts; play-by-play rows are a different '
        'quantity and include penalty-nullified no_play rows',
    'team_volume/team_dropbacks_part':
        'ESTIMAND_MISMATCH_UPPER_BOUND: the play-by-play dropback count is an '
        'upper bound on the participation-matched quantity forecast, not the '
        'quantity itself',
    'team_volume/team_targets':
        'ESTIMAND_UNVERIFIED: the team target definition has not been shown '
        'to match the realised aggregation and is not scored on assumption',
    'team_volume/team_rz_carries':
        'ESTIMAND_UNVERIFIED: red-zone boundary conventions differ between '
        'the forecast and the play-by-play and have not been reconciled',
    'rushing/rushing_yards':
        'NOT_MODELLED: RB/WR/TE rushing yards remain unavailable until '
        'RUSHING_CONVERSION_CONTROL_UNDEFINED is resolved, so there is no '
        'forecast to score',
    'receiving/receiving_td':
        'ESTIMAND_UNVERIFIED: touchdown attribution across rushing and '
        'receiving has not been reconciled with the allocation layer',
    'rushing/rushing_td':
        'ESTIMAND_UNVERIFIED: touchdown attribution across rushing and '
        'receiving has not been reconciled with the allocation layer',
}


# ----------------------------------------------------- 2/3. fetch + store
def fetch_outcomes(season=2026, url=None, timeout=240) -> Outcome:
    """Fetch the authoritative outcome file and store it immutably.

    The stored artifact is content-addressed, so re-fetching identical bytes
    re-uses the same path and cannot create a second, differently-named copy
    of the same outcome. Provenance -- source url, retrieved_at, content hash
    and the games inside -- is written beside it, never inferred later.
    """
    src = SOURCES[0]
    u = url or src['url'].format(season=season)
    STORE.mkdir(parents=True, exist_ok=True)
    tmp = STORE / f'.fetch_{season}.tmp'
    got = dt.datetime.now(dt.timezone.utc)
    r = subprocess.run(['curl', '-sSL', '--max-time', str(timeout),
                        '-o', str(tmp), '-w', '%{http_code}', u],
                       capture_output=True, text=True)
    status = (r.stdout or '').strip()[-3:]
    if r.returncode != 0 or status != '200' or not tmp.exists():
        if tmp.exists():
            tmp.unlink()
        return Outcome.blocked(
            'POSTGAME_SOURCE_UNREACHABLE',
            f'{src["name"]} returned HTTP {status or "000"} for {u}. No '
            f'outcome is invented and nothing is scored from a lower-rank '
            f'source.', cause=Cause.NETWORK, url=u, http_status=status)
    raw = tmp.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    blob = STORE / f'pbp_{season}.{digest[:16]}.csv.gz'
    already = blob.exists()
    if already:
        tmp.unlink()
    else:
        shutil.move(str(tmp), str(blob))
    try:
        games = sorted({r2.get('game_id') for r2 in
                        _rows(blob) if r2.get('game_id')})
    except Exception as e:                                   # noqa: BLE001
        return Outcome.fail('POSTGAME_SOURCE_UNREADABLE',
                            f'{blob} could not be parsed: {type(e).__name__}')
    if not games:
        return Outcome.fail(
            'POSTGAME_SOURCE_EMPTY',
            f'{blob} carries no game_id. An empty outcome file is an error, '
            f'not an absence of games.')
    prov = {
        'artifact': 'NFL_POSTGAME_OUTCOME_PROVENANCE',
        'spec_version': SPEC_VERSION, 'source_name': src['name'],
        'source_rank': src['rank'], 'source_url': u,
        'retrieved_at': got.isoformat(), 'sha256': digest,
        'n_bytes': len(raw), 'blob': str(blob.relative_to(_REPO)),
        'games': games, 'season': season,
        'already_present': already,
        'source_timestamp_note': (
            'nflverse publishes no per-file publication clock, so only the '
            'retrieval clock is asserted. They are different quantities and '
            'neither substitutes for the other.'),
    }
    (blob.with_suffix('.provenance.json')).write_text(
        json.dumps(prov, indent=1) + '\n')
    return Outcome.ok('POSTGAME_OUTCOME_STORED', value=prov,
                      spec_version=SPEC_VERSION, sha256=digest,
                      n_games=len(games), games=games,
                      already_present=already, blob=str(blob))


def stored_outcome(blob) -> Outcome:
    """Re-use an ALREADY-STORED authoritative outcome, without re-fetching.

    Reproduction must not depend on the network being up, and must not depend
    on the upstream file still being byte-identical -- if it has been restated
    since, a re-fetch would silently score against different bytes and call it
    a reproduction. The stored blob plus its recorded provenance is the exact
    realisation a previous run used, and its hash is re-derived here rather
    than trusted from the provenance file.
    """
    blob = pathlib.Path(blob)
    if not blob.exists():
        return Outcome.fail(
            'POSTGAME_STORED_OUTCOME_MISSING',
            f'{blob} does not exist. A reproduction cannot invent the bytes '
            f'it is meant to reproduce against.')
    prov_p = blob.with_suffix('.provenance.json')
    if not prov_p.exists():
        return Outcome.fail(
            'POSTGAME_STORED_OUTCOME_NO_PROVENANCE',
            f'{blob} has no provenance beside it. An outcome whose source is '
            f'unrecorded is not authoritative, whatever its contents.')
    prov = dict(json.loads(prov_p.read_text()))
    digest = hashlib.sha256(blob.read_bytes()).hexdigest()
    if digest != prov.get('sha256'):
        return Outcome.fail(
            'POSTGAME_STORED_OUTCOME_HASH_MISMATCH',
            f'{blob} hashes {digest[:16]} but its provenance records '
            f'{str(prov.get("sha256"))[:16]}. The stored artifact and its '
            f'provenance disagree; neither is trusted.')
    try:
        shown = str(blob.resolve().relative_to(_REPO.resolve()))
    except ValueError:
        # A blob outside the repository is legitimate in a sandboxed test.
        # Recording its absolute path is honest; pretending it is relative
        # would put a path in the artifact that resolves to the wrong file.
        shown = str(blob)
    prov.update({'already_present': True, 'reused_stored': True,
                 'blob': shown})
    return Outcome.ok('POSTGAME_OUTCOME_REUSED', value=prov,
                      spec_version=SPEC_VERSION, sha256=digest,
                      n_games=len(prov.get('games') or []),
                      games=prov.get('games'), already_present=True,
                      blob=str(blob))


def _rows(blob):
    import csv
    with gzip.open(blob, 'rt') as fh:
        return list(csv.DictReader(fh))


# ---------------------------------------------------- 1. FINALITY GUARD
# Every condition a FINAL game satisfies in the authoritative play-by-play.
# All five are required. Each is checked against the bytes, never against a
# clock we hold ourselves.
FINALITY_SIGNALS = (
    ('END_GAME_MARKER_PRESENT',
     'the source carries an END GAME play row. An in-progress, suspended, '
     'abandoned or partially-published game does not have one.'),
    ('GAME_CLOCK_EXPIRED',
     'game_seconds_remaining is 0 on that row.'),
    ('REGULATION_OR_LATER_COMPLETE',
     'the quarter on that row is 4 or later, so the game did not stop early.'),
    ('FINAL_RESULT_POPULATED',
     'the game-level result field is filled in. It is blank while a game is '
     'unfinished.'),
    ('SCOREBOARD_AGREES_WITH_RESULT',
     'result equals total_home_score - total_away_score. A file caught '
     'mid-restatement can disagree with itself, and that is not a final '
     'scoreboard.'),
)

NOT_FINAL = 'POSTGAME_NOT_FINAL'


def _num(v):
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return None


def game_finality(rows):
    """Is this game FINAL, proven from the authoritative bytes themselves?

    KICKOFF-PASSED IS NOT COMPLETION. A kickoff clock in the past makes a game
    eligible to be CHECKED. It says nothing about whether the game finished,
    and scoring a forecast against a game that is still being played, was
    suspended, or whose play-by-play is only partly published produces a
    number that looks like forecast error and is mostly missing plays.

    Returns a verdict dict rather than a bare bool so the reason survives into
    the artifact: `final`, `code`, `unmet` (named signals), `signals`.
    """
    sig = {'n_play_rows': len(rows or [])}
    if not rows:
        return {
            'final': False, 'code': NOT_FINAL, 'signals': sig,
            'unmet': ['NO_PLAY_ROWS'],
            'detail': ('the authoritative source carries no play rows for '
                       'this game. That is a postponed, cancelled or '
                       'not-yet-published game, not a game that ended 0-0.')}
    ends = [r for r in rows
            if (r.get('desc') or '').strip().upper() == 'END GAME']
    sig['n_end_game_markers'] = len(ends)
    unmet = []
    if ends:
        last = ends[-1]
    else:
        unmet.append('END_GAME_MARKER_PRESENT')
        last = rows[-1]
    gsr = _num(last.get('game_seconds_remaining'))
    qtr = _num(last.get('qtr'))
    res = _num(last.get('result'))
    home = _num(last.get('total_home_score'))
    away = _num(last.get('total_away_score'))
    sig.update({'game_seconds_remaining': gsr, 'qtr': qtr, 'result': res,
                'total_home_score': home, 'total_away_score': away,
                'last_desc': (last.get('desc') or '').strip()[:60]})
    if gsr is None or gsr != 0:
        unmet.append('GAME_CLOCK_EXPIRED')
    if qtr is None or qtr < 4:
        unmet.append('REGULATION_OR_LATER_COMPLETE')
    if res is None:
        unmet.append('FINAL_RESULT_POPULATED')
    if home is None or away is None or res is None:
        unmet.append('SCOREBOARD_AGREES_WITH_RESULT')
    elif abs(res - (home - away)) > 1e-9:
        unmet.append('SCOREBOARD_AGREES_WITH_RESULT')
    unmet = list(dict.fromkeys(unmet))
    if not unmet:
        return {'final': True, 'code': 'POSTGAME_FINAL', 'unmet': [],
                'signals': sig,
                'detail': 'every finality signal is satisfied by the source'}
    why = {name: note for name, note in FINALITY_SIGNALS}
    return {
        'final': False, 'code': NOT_FINAL, 'unmet': unmet, 'signals': sig,
        'detail': ('the authoritative source does not prove this game is '
                   'final: ' + '; '.join(
                       f'{u} -- {why.get(u, "no play rows are present")}'
                       for u in unmet) +
                   '. Kickoff having passed makes a game eligible for '
                   'checking, never eligible for scoring.')}


# -------------------------------------------------------- 2. discovery
def completed_with_seals(now=None):
    """Sealed forecasts whose kickoff has passed, across every namespace.

    NAMING IS DELIBERATE: this is the CHECK list, not the SCORE list. Kickoff
    having passed is necessary and nowhere near sufficient; `game_finality`
    decides what may actually be scored.
    """
    now = now or dt.datetime.now(dt.timezone.utc)
    out = []
    for rec in SI.discover_all():
        ko = rec.get('kickoff_utc')
        if not ko or not rec.get('game_id'):
            continue
        try:
            k = dt.datetime.fromisoformat(str(ko).replace('Z', '+00:00'))
        except ValueError:
            continue
        if k < now:
            out.append(rec)
    return out


# --------------------------------------------- 6/7/8. estimand + scoring
def _vec(draws, manifest, metric, pid):
    if draws is None or manifest is None:
        return None
    lay = metric.split('/')[0]
    ids = ((manifest.get('layers') or {}).get(lay) or {}).get('row_ids') or []
    if pid not in ids:
        return None
    key = metric.replace('/', '__')
    if key not in draws:
        return None
    arr = np.asarray(draws[key], float)
    i = ids.index(pid)
    return arr[i] if i < arr.shape[0] else None


def _score_one(x, y):
    """CRPS, PIT, coverage and bias from stored draws. No approximation."""
    s = SC.summarise(np.asarray(x, float), float(y))
    s['crps'] = SC.crps(np.asarray(x, float), float(y))
    s['bias'] = round(float(np.mean(x)) - float(y), 4)
    s['error_actual_minus_mean'] = round(float(y) - float(np.mean(x)), 4)
    return s


def identity_of(sealed, outcome_sha):
    """The unit-of-evidence identity stamped on every scoring row.

    WHY EACH FIELD IS HERE. `forecast_id` separates a candidate variant from
    another game -- without it five candidates of one game count as five
    games. `candidate` and `cutoff_utc` say WHICH forecast, so a pre-inactives
    and a post-inactives board of the same game are never pooled.
    `outcome_hash` says which realisation the row was scored against, which is
    what makes a revision detectable instead of silent.
    """
    return {
        'forecast_id': sealed.get('forecast_id'),
        'candidate': sealed.get('candidate'),
        'cutoff_utc': sealed.get('cutoff_utc'),
        'cutoff_basis': sealed.get('cutoff_basis'),
        'cutoff_regime': sealed.get('cutoff_regime'),
        'run_id': sealed.get('run_id'),
        'outcome_hash': outcome_sha,
        'outcome_sha16': outcome_sha[:16],
        # RELATIVE, not absolute: an absolute path is a property of the
        # machine that happened to run the scoring, not of the evidence.
        'sealed_dir': sealed.get('rel_dir') or str(sealed['dir']),
        'namespace': sealed.get('namespace'),
        'model_configuration': sealed.get('model_configuration'),
        'promoted': False,
    }


def score_game(sealed, rows, outcome_sha, finality=None) -> Outcome:
    """Score one sealed forecast against realised play-by-play.

    REFUSES A GAME THAT IS NOT PROVEN FINAL. The gate lives here rather than
    only in `run` so a direct caller cannot route around it.
    """
    fin = finality or game_finality(rows)
    if not fin['final']:
        return Outcome.blocked(
            NOT_FINAL, fin['detail'], cause=Cause.DATA,
            game_id=sealed.get('game_id'), unmet=fin['unmet'],
            signals=fin['signals'], n_scored=0)
    ident = identity_of(sealed, outcome_sha)
    d = pathlib.Path(sealed['dir'])
    man_p = d / 'player_draws_manifest.json'
    if not man_p.exists():
        return Outcome.deferred(
            'POSTGAME_NO_DRAW_MANIFEST',
            f'{d} carries no draw manifest, so no distribution can be scored',
            owed={'dir': str(d)})
    manifest = json.loads(man_p.read_text())
    draws = SI.load_draws(d)
    if draws is None:
        return Outcome.deferred(
            'POSTGAME_NO_STORED_DRAWS',
            f'{d} carries no stored draws; nine percentiles cannot support '
            f'CRPS and none is computed from them', owed={'dir': str(d)})

    qb = ACT.qb_actuals(rows)
    rr = ACT.receiving_rushing_actuals(rows)
    team = ACT.team_actuals(rows)
    nm = ACT.names(rows)

    scored, refused, no_forecast = [], [], []
    # ---- per-player, exact estimands only -------------------------------
    for metric, (family, field) in EXACT_ESTIMANDS.items():
        if family == 'team':
            continue
        src = qb if family == 'qb' else rr
        lay = metric.split('/')[0]
        ids = ((manifest.get('layers') or {}).get(lay) or {}).get('row_ids') or []
        for pid in ids:
            x = _vec(draws, manifest, metric, pid)
            if x is None or not len(x):
                no_forecast.append({'game_id': sealed['game_id'], 'pid': pid,
                                    'metric': metric,
                                    'code': 'NO_FORECAST_MISSING_PREGAME_INPUT'})
                continue
            # A MISSING FIELD IS A MAPPING BUG. A MISSING PLAYER IS A ZERO.
            #
            # These are different facts and the first version conflated them:
            # any field the actuals dict did not carry became 0.0, so a
            # mis-mapped key scored as a realised zero. Puka Nacua's 74
            # receiving yards were scored as 0 that way, and CRPS moved from
            # 12.02 to 43.11 without anything objecting.
            rec = src.get(pid)
            if rec is None:
                # The game is complete and this player appears on no
                # qualifying play, so every count is a realised zero.
                a, basis = 0.0, 'ZERO_BY_COMPLETION'
            elif field not in rec:
                refused.append({
                    'game_id': sealed['game_id'], 'gsis_id': pid,
                    'metric': metric,
                    'code': 'ESTIMAND_FIELD_NOT_IN_ACTUALS',
                    'detail': f'{field!r} is not a key of the realised '
                              f'record; refusing rather than defaulting to '
                              f'zero'})
                continue
            else:
                a, basis = rec[field], 'OBSERVED'
            row = _score_one(x, a)
            row.update(ident)
            row.update({'game_id': sealed['game_id'], 'entity': 'player',
                        'actual_basis': basis,
                        'gsis_id': pid, 'player_id': pid,
                        'player': nm.get(pid, pid),
                        'metric': metric, 'actual': float(a),
                        'estimand': 'EXACT'})
            scored.append(row)
    # ---- team, exact only ------------------------------------------------
    t_ids = ((manifest.get('layers') or {}).get('team_volume') or {}).get(
        'row_ids') or []
    for metric, (family, field) in EXACT_ESTIMANDS.items():
        if family != 'team':
            continue
        for t in t_ids:
            x = _vec(draws, manifest, metric, t)
            got = (team.get(t) or {}).get(field)
            if x is None or got is None:
                continue
            if got.get('basis') != 'EXACT':
                refused.append({'game_id': sealed['game_id'], 'team': t,
                                'metric': metric,
                                'code': f"ESTIMAND_NOT_EXACT:{got.get('basis')}"})
                continue
            row = _score_one(x, got['value'])
            row.update(ident)
            row.update({'game_id': sealed['game_id'], 'entity': 'team',
                        'team': t, 'player_id': None, 'metric': metric,
                        'actual': float(got['value']), 'estimand': 'EXACT'})
            scored.append(row)
    # ---- named refusals for every mismatched estimand --------------------
    for metric, why in REFUSED_ESTIMANDS.items():
        refused.append({'game_id': sealed['game_id'], 'metric': metric,
                        'code': why.split(':')[0], 'detail': why})

    agg = qb_room_aggregate(sealed, manifest, draws, qb, rows, ident)
    scored.extend(agg)
    return Outcome.ok(
        'POSTGAME_GAME_SCORED',
        value={'scored': scored, 'refused': refused,
               'no_forecast': no_forecast},
        n_scored=len(scored), n_refused=len(refused),
        n_no_forecast=len(no_forecast), game_id=sealed['game_id'],
        forecast_id=ident['forecast_id'], finality=fin['code'])




def qb_room_aggregate(sealed, manifest, draws, qb_act, rows, ident):
    """Score the QB ROOM beside the individual quarterbacks.

    NE@SEA is why this exists. Seattle's room aggregate was nearly exact --
    200 passing yards realised against 197.46 forecast -- while the split
    inside it was maximally wrong, because Darnold was injured early and Lock
    replaced him. No pregame information set can know that. Reporting only
    per-QB error charges irreducible in-game replacement variance to the
    allocation layer and invites a "fix" to something that was not broken.

    The aggregate is summed ACROSS DRAWS, not across means: the draw axis is
    column-aligned within a row's stream, so summing per column preserves the
    room's joint distribution rather than pretending the quarterbacks are
    independent.
    """
    ids = ((manifest.get('layers') or {}).get('qb') or {}).get('row_ids') or []
    if not ids:
        return []
    by_team = collections.defaultdict(list)
    for pid in ids:
        by_team[_team_of(rows, pid) or 'UNKNOWN'].append(pid)
    changes = _replacement_flags(rows)
    out = []
    for team, pids in sorted(by_team.items()):
        if team == 'UNKNOWN':
            continue
        for metric, field in (('qb/att', 'att'), ('qb/pyds', 'pyds'),
                              ('qb/db', 'db')):
            vecs = [_vec(draws, manifest, metric, p) for p in pids]
            vecs = [v for v in vecs if v is not None and len(v)]
            if not vecs:
                continue
            n = min(len(v) for v in vecs)
            total = np.sum([np.asarray(v[:n], float) for v in vecs], axis=0)
            actual = sum(float((qb_act.get(p) or {}).get(field) or 0.0)
                         for p in pids)
            row = _score_one(total, actual)
            row.update(ident)
            row.update({
                'game_id': sealed['game_id'], 'entity': 'qb_room',
                'team': team, 'player_id': None, 'metric': metric,
                'actual': actual,
                'estimand': 'EXACT', 'n_quarterbacks': len(pids),
                'in_game_replacement': bool(changes.get(team)),
                'replacement_detail': changes.get(team),
                'why_this_row_exists': (
                    'the room aggregate is forecastable pregame; the split '
                    'inside it is not when a quarterback is replaced mid-game'),
            })
            out.append(row)
    return out


def _team_of(rows, pid):
    for r in rows:
        if r.get('passer_player_id') == pid:
            return r.get('posteam')
    return None


def _replacement_flags(rows):
    """Which teams changed passer mid-game, classified apart from allocation.

    An in-game replacement is not an allocation error. It is an event that
    occurred after the information set closed, and every row it touches is
    labelled so the two are never summed together.
    """
    seq = collections.defaultdict(list)
    for r in rows:
        p = r.get('passer_player_id')
        if p and (not seq[r.get('posteam')] or seq[r.get('posteam')][-1] != p):
            seq[r.get('posteam')].append(p)
    out = {}
    for team, order in seq.items():
        distinct = list(dict.fromkeys(order))
        if len(distinct) > 1:
            out[team] = {
                'passers_in_order': distinct,
                'classification': 'IN_GAME_REPLACEMENT_NOT_PREGAME_ALLOCATION',
                'note': ('the passer changed during the game. Per-quarterback '
                         'error here mixes pregame allocation with an event '
                         'no pregame information set could observe.'),
            }
    return out


# ----------------------------- UNIT OF EVIDENCE + OUTCOME SUPERSESSION
# What one count MEANS. A floor stated without its unit is not a floor: "300"
# against rows, against games and against player-games are three different
# requirements, and the loosest of them is the one a row count accidentally
# satisfies first.
EVIDENCE_UNITS = {
    'scoring_rows': (
        'ROW -- one metric x one sealed forecast x one outcome version. This '
        'is a bookkeeping count and is NEVER a prospective sample size.'),
    'graded_metrics': (
        'METRIC -- a distinct forecast quantity that produced at least one '
        'scored row.'),
    'distinct_games': (
        'GAME -- the independent unit. Two candidates of one game are one '
        'game.'),
    'distinct_team_games': (
        'TEAM-GAME -- one team in one game. The unit a target budget, a play '
        'count and a snap total are allocated within, so it is the unit a '
        'within-team allocation error is shared across. Two teams in one game '
        'are NOT independent of each other either -- they share the clock and '
        'the score -- which is why GAME remains the floor unit.'),
    'distinct_player_games': (
        'PLAYER-GAME -- one player in one game. Not independent across '
        'players within a game: teammates share the same game state.'),
    'distinct_candidate_forecasts': (
        'CANDIDATE FORECAST -- one sealed forecast. Variants of the same game '
        'are PAIRED comparisons on that game, not independent games.'),
}

# Which unit an evidence floor is counted in. Named, so no floor can be
# quietly satisfied by the largest available number.
FLOOR_UNIT = 'distinct_games'

PAIRED_NOTE = (
    'Candidate variants from the same game are paired comparisons, not '
    'independent games. Pooling them inflates an apparent sample by the '
    'number of variants run and narrows every interval computed from it.')


def accounting(rows):
    """Count the evidence in every unit separately, each unit declared.

    THE DEFECT THIS PREVENTS. Nineteen sealed artifacts across two completed
    games produced thousands of scoring rows. Reported as a single number,
    that reads as a large prospective sample. It is two games.
    """
    rows = list(rows or [])
    games = {r.get('game_id') for r in rows if r.get('game_id')}
    return {
        'scoring_rows': len(rows),
        'graded_metrics': len({r.get('metric') for r in rows
                               if r.get('metric')}),
        'distinct_games': len(games),
        'distinct_team_games': len(
            {(r.get('game_id'), r.get('team')) for r in rows
             if r.get('game_id') and r.get('team')}),
        'distinct_player_games': len(
            {(r.get('game_id'), r.get('player_id')) for r in rows
             if r.get('player_id')}),
        'distinct_candidate_forecasts': len(
            {r.get('forecast_id') for r in rows if r.get('forecast_id')}),
        'games': sorted(g for g in games if g),
        'units': EVIDENCE_UNITS,
        'floor_unit': FLOOR_UNIT,
        'paired_note': PAIRED_NOTE,
        'prospective_sample_size': {
            'value': len(games), 'unit': 'GAME',
            'note': ('the sample size for an evidence floor. scoring_rows is '
                     'not this number and must never be reported as it.')},
    }


# One outcome version per forecast x metric x subject may be CURRENT. The
# subject is the player, the team, or the quarterback room -- entity is part
# of the identity because a team row and a room row share a team code.
# `arm` IS PART OF THE SUBJECT, AND LEAVING IT OUT WAS A DEFECT.
#
# Found by the Q9 prospective harness, which seals BOTH arms of a side-by-side
# comparison inside ONE forecast artifact. Both arms then shared all six
# fields, so `versioned` read the second arm as a REVISION of the first and
# marked it SUPERSEDED: of four rows -- two arms x two outcome versions --
# only one came back CURRENT. The scoring machinery would have silently
# discarded one arm of every paired comparison.
#
# It never surfaced before because each candidate variant had its own
# `forecast_id`. A row with no `arm` key resolves to the empty string exactly
# as it did, so every ledger row already on disk keeps the identity it had.
VERSION_IDENTITY = ('forecast_id', 'game_id', 'entity', 'metric', 'player_id',
                    'team', 'arm')


def _version_identity(r):
    return '|'.join(str(r.get(k) or '') for k in VERSION_IDENTITY)


def versioned(rows):
    """Label every ledger row CURRENT or SUPERSEDED. Computed, never written.

    WHY IT IS COMPUTED AND NOT EDITED IN PLACE. The ledger is append-only, so
    a row already on disk is immutable; going back to stamp SUPERSEDED into it
    would be a rewrite of recorded evidence. The version label is therefore
    derived from ledger ORDER, which is itself append-only and cannot be
    reordered without rewriting the file.

    A revision is detected by `outcome_hash`: the same forecast scored against
    restated play-by-play is a NEW row, and the older one stops being current
    without stopping being true.
    """
    rows = list(rows or [])
    order = collections.defaultdict(list)
    for i, r in enumerate(rows):
        order[_version_identity(r)].append(i)
    out = []
    for i, r in enumerate(rows):
        idx = order[_version_identity(r)]
        winner = rows[idx[-1]]
        r2 = dict(r)
        r2['version_index'] = idx.index(i)
        r2['n_outcome_versions'] = len(idx)
        if i == idx[-1]:
            r2['version_status'] = 'CURRENT'
            r2['superseded_by_outcome_hash'] = None
        else:
            r2['version_status'] = 'SUPERSEDED'
            r2['superseded_by_outcome_hash'] = (
                winner.get('outcome_hash') or winner.get('outcome_sha16'))
        out.append(r2)
    return out


def load_ledger(path=None):
    """Every ledger row in FILE ORDER. Order is the version authority."""
    p = pathlib.Path(path or LEDGER)
    if not p.exists():
        return []
    out = []
    for line in p.read_text().splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def current_rows(rows=None, path=None):
    """The CURRENT outcome version only. What calibration reads by default."""
    src = rows if rows is not None else load_ledger(path)
    return [r for r in versioned(src) if r['version_status'] == 'CURRENT']


def all_versions(rows=None, path=None):
    """Every version, current and superseded. What an audit reads."""
    src = rows if rows is not None else load_ledger(path)
    return versioned(src)


def supersession_index(rows=None, path=None):
    """Which identities have been revised, and by which outcome hash."""
    v = all_versions(rows, path)
    by = collections.defaultdict(list)
    for r in v:
        by[_version_identity(r)].append(r)
    revised = {}
    for key, rs in by.items():
        if len(rs) < 2:
            continue
        revised[key] = {
            'n_versions': len(rs),
            'current_outcome_hash': rs[-1].get('outcome_hash'),
            'superseded_outcome_hashes': [x.get('outcome_hash')
                                          for x in rs[:-1]],
        }
    return {
        'artifact': 'NFL_POSTGAME_SUPERSESSION_INDEX',
        'spec_version': SPEC_VERSION,
        'n_rows_total': len(v),
        'n_rows_current': sum(1 for r in v
                              if r['version_status'] == 'CURRENT'),
        'n_rows_superseded': sum(1 for r in v
                                 if r['version_status'] == 'SUPERSEDED'),
        'n_identities': len(by),
        'n_identities_revised': len(revised),
        'revised': revised,
        'rule': ('one CURRENT version per ' + ' + '.join(VERSION_IDENTITY) +
                 '. Older versions are preserved verbatim and never deleted.'),
    }


# ------------------------------------------------ 9/10. append-only ledger
def _row_key(r):
    """Identity of a scoring row. Re-running on the SAME bytes is a no-op.

    The key deliberately includes the outcome hash and the sealed directory:
    the same forecast scored against a REVISED outcome file is a new row, not
    a duplicate, because the realised value may have changed. What must never
    duplicate is the same forecast against the same bytes.
    """
    return '|'.join(str(r.get(k, '')) for k in (
        'game_id', 'entity', 'gsis_id', 'team', 'metric', 'sealed_dir',
        'forecast_id', 'outcome_sha16'))


def existing_keys():
    if not LEDGER.exists():
        return set()
    out = set()
    for line in LEDGER.read_text().splitlines():
        if not line.strip():
            continue
        try:
            out.add(_row_key(json.loads(line)))
        except ValueError:
            continue
    return out


def append_rows(rows):
    """Append only what is genuinely new. Never rewrites an existing line."""
    have = existing_keys()
    new = [r for r in rows if _row_key(r) not in have]
    seen = set()
    uniq = []
    for r in new:
        k = _row_key(r)
        if k in seen:
            continue
        seen.add(k)
        uniq.append(r)
    if uniq:
        STORE.mkdir(parents=True, exist_ok=True)
        with open(LEDGER, 'a') as fh:
            for r in uniq:
                fh.write(json.dumps(r, sort_keys=True, default=str) + '\n')
    return {'added': len(uniq), 'duplicates_avoided': len(rows) - len(uniq)}


def run(season=2026, out_dir=None, url=None, blob=None) -> Outcome:
    out = pathlib.Path(out_dir or STORE)
    out.mkdir(parents=True, exist_ok=True)
    fetched = (stored_outcome(blob) if blob
               else fetch_outcomes(season, url=url))
    completed = completed_with_seals()
    by_game = collections.defaultdict(list)
    for rec in completed:
        by_game[rec['game_id']].append(rec)

    status = {
        'artifact': 'NFL_POSTGAME_STATUS', 'spec_version': SPEC_VERSION,
        'generated_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
        'season': season, 'promoted': False,
        'completed_games_discovered': sorted(by_game),
        'n_completed_games_discovered': len(by_game),
        'n_sealed_forecasts_found': len(completed),
        'outcome_source': {'state': fetched.state.name, 'code': fetched.code,
                           'sha256': fetched.evidence.get('sha256'),
                           'games': fetched.evidence.get('games'),
                           'already_present': fetched.evidence.get(
                               'already_present')},
        'games_scored': [], 'games_deferred': [], 'games_refused': [],
        'games_not_final': [],
        'scoring_rows_added': 0, 'duplicate_rows_avoided': 0,
        'estimands_refused_by_name': sorted(REFUSED_ESTIMANDS),
        'finality_signals_required': [n for n, _ in FINALITY_SIGNALS],
    }
    if fetched.state is not State.PASS:
        status['games_refused'] = [
            {'game_id': g, 'code': fetched.code,
             'reason': 'no authoritative outcome could be fetched; nothing is '
                       'scored from a lower-rank source'} for g in by_game]
        (out / 'POSTGAME_STATUS.json').write_text(
            json.dumps(status, indent=1, default=str) + '\n')
        return Outcome.blocked(
            'POSTGAME_NO_AUTHORITATIVE_OUTCOME', fetched.detail,
            cause=Cause.NETWORK, **{k: status[k] for k in
                                    ('n_completed_games_discovered',)})
    blob = pathlib.Path(fetched.evidence['blob'])
    sha = fetched.evidence['sha256']
    available = set(fetched.evidence.get('games') or [])
    all_rows = _rows(blob)
    by_pbp = collections.defaultdict(list)
    for r in all_rows:
        by_pbp[r.get('game_id')].append(r)

    ledger_rows = []
    for gid, seals in sorted(by_game.items()):
        if gid not in available:
            status['games_deferred'].append(
                {'game_id': gid,
                 'code': 'OUTCOME_NOT_YET_PUBLISHED',
                 'reason': 'the game is complete and has a sealed forecast, '
                           'but the authoritative source does not carry it '
                           'yet. Deferred, not refused.'})
            continue
        fin = game_finality(by_pbp[gid])
        if not fin['final']:
            # ZERO SCORING ROWS. Kickoff passed and the source carries the
            # game, but the bytes do not prove it finished.
            status['games_not_final'].append(
                {'game_id': gid, 'code': fin['code'], 'unmet': fin['unmet'],
                 'signals': fin['signals'], 'reason': fin['detail'],
                 'n_sealed_forecasts_skipped': len(seals)})
            continue
        for s in seals:
            o = score_game(s, by_pbp[gid], sha, finality=fin)
            if o.state is not State.PASS:
                status['games_deferred'].append(
                    {'game_id': gid, 'sealed_dir': s['dir'],
                     'code': o.code, 'reason': o.detail[:200]})
                continue
            ledger_rows.extend(o.value['scored'])
            status['games_scored'].append(
                {'game_id': gid, 'sealed_dir': s['dir'],
                 'namespace': s['namespace'],
                 'n_scored': o.evidence['n_scored'],
                 'n_refused_estimands': o.evidence['n_refused'],
                 'n_no_forecast': o.evidence['n_no_forecast']})
    added = append_rows(ledger_rows)
    status['scoring_rows_added'] = added['added']
    status['duplicate_rows_avoided'] = added['duplicates_avoided']
    status['n_games_scored'] = len({g['game_id']
                                    for g in status['games_scored']})
    status['n_games_deferred'] = len(status['games_deferred'])
    status['n_games_refused'] = len(status['games_refused'])
    status['n_games_not_final'] = len(status['games_not_final'])

    # THE LEDGER IS READ BACK, NOT ASSUMED. Accounting reports the CURRENT
    # outcome version only, in every unit separately, so a row count can never
    # stand in for a sample size.
    ledger = load_ledger()
    sup = supersession_index(ledger)
    status['evidence'] = accounting(current_rows(ledger))
    status['evidence_all_versions'] = accounting(ledger)
    status['supersession'] = {k: sup[k] for k in (
        'n_rows_total', 'n_rows_current', 'n_rows_superseded',
        'n_identities', 'n_identities_revised', 'rule')}
    (out / 'SUPERSESSION_INDEX.json').write_text(
        json.dumps(sup, indent=1, default=str) + '\n')
    (out / 'POSTGAME_STATUS.json').write_text(
        json.dumps(status, indent=1, default=str) + '\n')
    return Outcome.ok('POSTGAME_RUN_COMPLETE', value=str(out),
                      spec_version=SPEC_VERSION,
                      evidence_units=status['evidence'],
                      **{k: status[k] for k in (
                          'n_completed_games_discovered',
                          'n_sealed_forecasts_found', 'n_games_scored',
                          'n_games_deferred', 'n_games_refused',
                          'n_games_not_final',
                          'scoring_rows_added',
                          'duplicate_rows_avoided')})


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--season', type=int, default=2026)
    ap.add_argument('--out', default=None)
    ap.add_argument('--url', default=None)
    ap.add_argument('--blob', default=None,
                    help='score against an already-stored outcome artifact '
                         'instead of fetching. Reproduction, not retrieval.')
    a = ap.parse_args(argv)
    o = run(a.season, a.out, a.url, a.blob)
    e = o.evidence
    if o.state is not State.PASS:
        print(f'{o.state.name}[{o.code}] {o.detail[:160]}')
        return 1
    print(f'completed games discovered : {e["n_completed_games_discovered"]}')
    print(f'sealed forecasts found     : {e["n_sealed_forecasts_found"]}')
    print(f'games scored               : {e["n_games_scored"]}')
    print(f'games deferred             : {e["n_games_deferred"]}')
    print(f'games refused              : {e["n_games_refused"]}')
    print(f'games NOT FINAL (skipped)  : {e["n_games_not_final"]}')
    print(f'scoring rows added         : {e["scoring_rows_added"]}')
    print(f'duplicate rows avoided     : {e["duplicate_rows_avoided"]}')
    ev = e['evidence_units']
    print('')
    print('PROSPECTIVE EVIDENCE, current outcome version only:')
    for k in ('scoring_rows', 'graded_metrics', 'distinct_games',
              'distinct_player_games', 'distinct_candidate_forecasts'):
        print(f'  {k:30s} {ev[k]:6d}   unit: {ev["units"][k].split(" --")[0]}')
    print(f'  sample size for a floor        {ev["prospective_sample_size"]["value"]:6d}'
          f'   unit: {ev["prospective_sample_size"]["unit"]}')
    print(f'  {PAIRED_NOTE}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
