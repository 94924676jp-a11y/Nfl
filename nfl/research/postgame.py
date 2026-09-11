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


def _rows(blob):
    import csv
    with gzip.open(blob, 'rt') as fh:
        return list(csv.DictReader(fh))


# -------------------------------------------------------- 1. discovery
def completed_with_seals(now=None):
    """Sealed forecasts whose kickoff has passed, across every namespace."""
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


def score_game(sealed, rows, outcome_sha) -> Outcome:
    """Score one sealed forecast against realised play-by-play."""
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
            row.update({'game_id': sealed['game_id'], 'entity': 'player',
                        'actual_basis': basis,
                        'gsis_id': pid, 'player': nm.get(pid, pid),
                        'metric': metric, 'actual': float(a),
                        'estimand': 'EXACT', 'outcome_sha16': outcome_sha[:16],
                        'sealed_dir': str(d), 'namespace': sealed['namespace'],
                        'model_configuration': sealed.get('model_configuration'),
                        'promoted': False})
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
            row.update({'game_id': sealed['game_id'], 'entity': 'team',
                        'team': t, 'metric': metric,
                        'actual': float(got['value']), 'estimand': 'EXACT',
                        'outcome_sha16': outcome_sha[:16], 'sealed_dir': str(d),
                        'namespace': sealed['namespace'], 'promoted': False})
            scored.append(row)
    # ---- named refusals for every mismatched estimand --------------------
    for metric, why in REFUSED_ESTIMANDS.items():
        refused.append({'game_id': sealed['game_id'], 'metric': metric,
                        'code': why.split(':')[0], 'detail': why})

    agg = qb_room_aggregate(sealed, manifest, draws, qb, rows, outcome_sha)
    scored.extend(agg)
    return Outcome.ok(
        'POSTGAME_GAME_SCORED',
        value={'scored': scored, 'refused': refused,
               'no_forecast': no_forecast},
        n_scored=len(scored), n_refused=len(refused),
        n_no_forecast=len(no_forecast), game_id=sealed['game_id'])




def qb_room_aggregate(sealed, manifest, draws, qb_act, rows, outcome_sha):
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
            row.update({
                'game_id': sealed['game_id'], 'entity': 'qb_room',
                'team': team, 'metric': metric, 'actual': actual,
                'estimand': 'EXACT', 'n_quarterbacks': len(pids),
                'outcome_sha16': outcome_sha[:16],
                'sealed_dir': str(sealed['dir']),
                'namespace': sealed['namespace'], 'promoted': False,
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
        'outcome_sha16'))


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


def run(season=2026, out_dir=None, url=None) -> Outcome:
    out = pathlib.Path(out_dir or STORE)
    out.mkdir(parents=True, exist_ok=True)
    fetched = fetch_outcomes(season, url=url)
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
        'scoring_rows_added': 0, 'duplicate_rows_avoided': 0,
        'estimands_refused_by_name': sorted(REFUSED_ESTIMANDS),
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
        for s in seals:
            o = score_game(s, by_pbp[gid], sha)
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
    (out / 'POSTGAME_STATUS.json').write_text(
        json.dumps(status, indent=1, default=str) + '\n')
    return Outcome.ok('POSTGAME_RUN_COMPLETE', value=str(out),
                      spec_version=SPEC_VERSION, **{
                          k: status[k] for k in (
                              'n_completed_games_discovered',
                              'n_sealed_forecasts_found', 'n_games_scored',
                              'n_games_deferred', 'n_games_refused',
                              'scoring_rows_added',
                              'duplicate_rows_avoided')})


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--season', type=int, default=2026)
    ap.add_argument('--out', default=None)
    ap.add_argument('--url', default=None)
    a = ap.parse_args(argv)
    o = run(a.season, a.out, a.url)
    e = o.evidence
    if o.state is not State.PASS:
        print(f'{o.state.name}[{o.code}] {o.detail[:160]}')
        return 1
    print(f'completed games discovered : {e["n_completed_games_discovered"]}')
    print(f'sealed forecasts found     : {e["n_sealed_forecasts_found"]}')
    print(f'games scored               : {e["n_games_scored"]}')
    print(f'games deferred             : {e["n_games_deferred"]}')
    print(f'games refused              : {e["n_games_refused"]}')
    print(f'scoring rows added         : {e["scoring_rows_added"]}')
    print(f'duplicate rows avoided     : {e["duplicate_rows_avoided"]}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
