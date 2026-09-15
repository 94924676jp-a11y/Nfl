"""Q7 step 1: the efficiency panel, built from play-by-play with provenance.

WHY A SEPARATE PANEL RATHER THAN TRACK 1'S.

Track 1's reduction is frozen with its own specification and carries no
completions, no passing touchdowns and no receiver rows. Extending it would
edit a frozen artifact; building beside it from the same six source files,
re-hashed here, leaves both auditable.

DEFINITIONS, FIXED AT SPEC VERSION 1 AND UNCHANGED HERE.

    attempt      pass_attempt and not sack and not spike
    completion   an attempt that completed
    sack         a sack on a dropback
    scramble     a scramble on a dropback that is not a sack
    dropback     attempts + sacks + scrambles

ATTRIBUTION -- THIS IS WHAT SPEC VERSION 2 REPAIRS.

Spec version 1 incremented every QB counter inside `if pid:` with
`pid = passer_player_id`. A `qb_scramble` play carries NO passer id: nflverse
attributes a scramble to `rusher_player_id`, because the quarterback ran. The
`scr` column was therefore built structurally zero -- 1 scramble across 4,025
QB-games against 5,864 in the same six seasons of play-by-play. A scramble is
now charged to the scrambling quarterback through `rusher_player_id`.

WHY THE OLD CHECK COULD NOT SEE IT, AND WHAT REPLACES IT.

Version 1's docstring argued that composing `db = att + sacks + scr` made the
identity `att + sacks + scr == db` hold "by construction and cannot drift from
the engine's own check". That is true and it is worthless: the identity is
true of any three numbers whatsoever, including a zero, so it cannot detect a
counter that is never reached. Worse, composing displaced the one check that
WOULD have caught this -- nflverse publishes its own `qb_dropback` flag and
version 1 never compared against it.

The composition stays, because downstream consumers depend on the identity.
It is no longer the only check. `build` now also:

  * refuses any built count column that does not vary (`assert_not_degenerate`),
    which is the generalised form of this defect -- `qb2/build_qb.py` names the
    first instance this repository produced, this panel was the second, and the
    third should fail the build rather than ship;

  * reconciles the composed dropback total against nflverse's `qb_dropback`,
    player-game by player-game, and refuses to write on any UNEXPLAINED
    difference. The explained difference is enumerated, not waved at: see
    `RECONCILIATION` below.

THE RECONCILIATION RESIDUAL, DERIVED RATHER THAN TOLERATED.

Measured over 2020-2025 REG, the composed total is 122,053 against nflverse's
122,044. The 9-row gap is exactly the set of rows satisfying the frozen
`attempt` definition that nflverse does not flag as a dropback, and every one
of the nine is named in `Q7_DROPBACK_RECONCILIATION.json`:

  * 7 TWO-POINT CONVERSION passes. nflverse sets `pass_attempt = 1` and
    `complete_pass` on a two-point try but leaves `qb_dropback` at 0. The
    frozen attempt definition therefore counts them and nflverse does not.
    This divergence is INHERITED, not introduced: spec version 1 counted them
    the same way in `att` and `cmp`. It is recorded here rather than repaired,
    because repairing it would move `att` and every quantity conditioned on it,
    which is a separate change needing its own before-and-after.
  * 1 replay-reversed sack inside a penalty `no_play` (2025_02_SEA_PIT).
  * 1 blocked field goal whose row carries `pass_attempt = 1`, charged to the
    kicker (2025_03_LA_PHI) -- the only QB-game in the panel that nflverse does
    not recognise at all.

The build asserts that the residual equals that enumerated set and nothing
else, so the tolerance is a derived count and not a round number.

PER-RECEPTION YARDAGE IS KEPT PER CATCH, not as a game mean. RC1 measured skew
2.197 and excess kurtosis 7.830 on this quantity, with P(gain > 40) = 0.0203
empirically against 0.0016 under a fitted Normal -- a Gaussian understates the
tail thirteenfold. The list is what makes a resampled tail possible.

SUPERSESSION, NOT OVERWRITE. The version-1 artifacts stay on disk untouched,
under their original names, and the corrected panel is written beside them with
its own content hash. `Q7_PANEL_SUPERSESSION.json` records which conclusions
were drawn from which. Deleting the broken artifact would delete the audit
trail of every conclusion drawn from it.

NO MARKET COLUMN IS READ. `READ` is the complete list and is checked against a
forbidden-substring list at import, exactly as the Track 1 builder is.
"""
from __future__ import annotations

import argparse
import collections
import csv
import gzip
import hashlib
import io
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

SPEC_VERSION = 'q7-panel-2'
SUPERSEDES_SPEC_VERSION = 'q7-panel-1'
HERE = _REPO / 'nfl' / 'research' / 'q7'
RAW = _REPO / 'nfl' / 'research' / 'track1' / 'raw'

# The corrected panel. A NEW path: the version-1 artifacts below are left
# exactly as they were built, because the published Q7 conclusions rest on them
# and an audit has to be able to reach both.
QB = HERE / 'q7_qb_game_r2.csv.gz'
RECV = HERE / 'q7_recv_game_r2.csv.gz'
SUPERSEDED_QB = HERE / 'q7_qb_game.csv.gz'
SUPERSEDED_RECV = HERE / 'q7_recv_game.csv.gz'

MANIFEST = HERE / 'Q7_RAW_PROVENANCE_R2.json'
SUPERSEDED_MANIFEST = HERE / 'Q7_RAW_PROVENANCE.json'
RECONCILIATION = HERE / 'Q7_DROPBACK_RECONCILIATION.json'
SUPERSESSION = HERE / 'Q7_PANEL_SUPERSESSION.json'

SEASONS = (2020, 2021, 2022, 2023, 2024, 2025)
URL = ('https://github.com/nflverse/nflverse-data/releases/download/pbp/'
       'play_by_play_{season}.csv.gz')

READ = ('game_id', 'season', 'week', 'season_type', 'posteam', 'defteam',
        'passer_player_id', 'passer_player_name', 'rusher_player_id',
        'rusher_player_name', 'receiver_player_id', 'receiver_player_name',
        'pass_attempt', 'complete_pass', 'sack', 'qb_scramble', 'qb_spike',
        'qb_dropback', 'passing_yards', 'receiving_yards', 'pass_touchdown',
        'interception')

FORBIDDEN_SUBSTRINGS = ('spread_line', 'total_line', 'vegas', 'moneyline',
                        'odds', 'implied_prob')

# Count columns the builder composes. Every one of them must vary.
QB_COUNT_COLUMNS = ('db', 'att', 'cmp', 'sacks', 'scr', 'pyds', 'ptd', 'int')
RECV_COUNT_COLUMNS = ('targets', 'rec', 'rec_yds', 'rec_td')


def market_columns(fieldnames):
    return [c for c in fieldnames
            if any(s in str(c).lower() for s in FORBIDDEN_SUBSTRINGS)]


def assert_no_market_column(fieldnames, where):
    bad = market_columns(fieldnames)
    if bad:
        raise SystemExit(
            f'Q7_MARKET_COLUMN_IN_{where}: {bad}. Sportsbook prices, lines and '
            f'market probabilities are forbidden inputs.')


assert_no_market_column(READ, 'READ_LIST')


def degenerate_columns(rows, columns):
    """Count columns that do not vary, with the evidence for each.

    A count column is degenerate when its total over the frame is 0 or 1, or
    when at most one row carries a non-zero value. Both are what a counter that
    is never reached looks like from the outside, and both are the shape the
    scramble column had.
    """
    out = {}
    for c in columns:
        vals = [int(r[c]) for r in rows]
        total, nonzero = sum(vals), sum(1 for v in vals if v)
        if total <= 1 or nonzero <= 1:
            out[c] = {'total': total, 'nonzero_rows': nonzero,
                      'n_rows': len(vals)}
    return out


def assert_not_degenerate(rows, columns, where):
    """Refuse to ship a built count column that does not vary.

    THE GENERALISED GUARD. This repository has produced this failure mode
    twice: `qb2/build_qb.py` names the first, and this panel's `scr` column was
    the second. Both were a counter behind a condition that was never true.
    Raising here means the third fails the build.
    """
    bad = degenerate_columns(rows, columns)
    if bad:
        raise SystemExit(
            f'Q7_DEGENERATE_COUNT_COLUMN_IN_{where}: {json.dumps(bad)}. A '
            f'count column that is zero, or non-zero on at most one row, is a '
            f'counter that is never reached -- a build failure, not a result.')
    return len(rows)


def _i(v, d=0):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return d


def _f(v, d=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return d


def reduce_season(path):
    """One season's REG rows, reduced to QB-games and receiver-games.

    Also returns the nflverse reference needed to reconcile: `qb_dropback`
    counted per player-game with the SAME attribution the panel uses, and the
    individual rows where the frozen definitions and nflverse disagree.
    """
    qb = collections.defaultdict(collections.Counter)
    rc = collections.defaultdict(collections.Counter)
    rec_yards = collections.defaultdict(list)
    nv_db = collections.Counter()
    exceptions = []
    names = {}
    meta = {}
    with gzip.open(path, 'rt', newline='') as fh:
        for r in csv.DictReader(fh):
            if r.get('season_type') != 'REG':
                continue
            gid, off = r.get('game_id'), r.get('posteam')
            if not gid or not off:
                continue
            meta.setdefault(gid, {'season': _i(r.get('season')),
                                  'week': _i(r.get('week'))})
            sack = _i(r.get('sack'))
            scr = _i(r.get('qb_scramble'))
            spike = _i(r.get('qb_spike'))
            pa = _i(r.get('pass_attempt'))
            ndb = _i(r.get('qb_dropback'))
            is_att = bool(pa and not sack and not spike)
            comp = _i(r.get('complete_pass')) if is_att else 0
            pid = (r.get('passer_player_id') or '').strip()
            rid = (r.get('rusher_player_id') or '').strip()
            if pid:
                names[pid] = (r.get('passer_player_name') or '').strip()
                c = qb[(gid, off, pid)]
                if is_att:
                    c['att'] += 1
                    c['cmp'] += comp
                    c['pyds'] += _i(r.get('passing_yards'))
                    c['ptd'] += _i(r.get('pass_touchdown'))
                    c['int'] += _i(r.get('interception'))
                if sack and ndb:
                    c['sacks'] += 1
            # THE REPAIR. A scramble is a QB run: nflverse carries no passer id
            # on it and charges it to `rusher_player_id`. Gated on
            # `qb_dropback` exactly as the sack branch above is, and on `not
            # sack` because one 2020 row carries both flags -- a scramble
            # reversed to a sack on replay (2020_16_PHI_DAL) -- and a play
            # cannot be both.
            if scr and not sack and ndb and rid:
                names.setdefault(rid, (r.get('rusher_player_name') or '').strip())
                qb[(gid, off, rid)]['scr'] += 1
            elif scr and not sack and not ndb:
                exceptions.append({'kind': 'SCRAMBLE_NOT_A_DROPBACK',
                                   'game_id': gid, 'team': off,
                                   'play_type': r.get('play_type', ''),
                                   'note': 'penalty no_play; nflverse sets '
                                           'qb_dropback = 0'})
            if is_att and not ndb:
                exceptions.append({'kind': 'ATTEMPT_NOT_AN_NFLVERSE_DROPBACK',
                                   'game_id': gid, 'team': off,
                                   'player': pid,
                                   'play_type': r.get('play_type', ''),
                                   'desc': (r.get('desc') or '')[:120]})
            if ndb:
                who = pid or rid
                if who:
                    nv_db[(gid, off, who)] += 1
                else:
                    exceptions.append({'kind': 'DROPBACK_WITH_NO_PLAYER_ID',
                                       'game_id': gid, 'team': off})
            rcid = (r.get('receiver_player_id') or '').strip()
            if rcid and is_att:
                names[rcid] = (r.get('receiver_player_name') or '').strip()
                c = rc[(gid, off, rcid)]
                c['targets'] += 1
                c['rec'] += comp
                c['rec_yds'] += _i(r.get('receiving_yards'))
                c['rec_td'] += _i(r.get('pass_touchdown')) if comp else 0
                if comp:
                    rec_yards[(gid, off, rcid)].append(
                        _i(r.get('receiving_yards')))
    return qb, rc, rec_yards, names, meta, nv_db, exceptions


def reconcile(qb_rows, nv_db, exceptions):
    """Composed dropbacks against nflverse `qb_dropback`, per player-game.

    THE CHECK THE TAUTOLOGY DISPLACED. Returns the raw comparison, the
    enumerated explanation, and whatever is left over. The build refuses on a
    non-empty leftover; the leftover is REPORTED either way rather than folded
    into a tolerance.
    """
    panel = {(r['game_id'], r['team'], r['gsis_id']): r['db'] for r in qb_rows}
    att_nodb = [e for e in exceptions
                if e['kind'] == 'ATTEMPT_NOT_AN_NFLVERSE_DROPBACK']
    # The explained reference: nflverse's own flag, plus the rows the frozen
    # `attempt` definition counts and nflverse does not.
    explained = collections.Counter(nv_db)
    for e in att_nodb:
        explained[(e['game_id'], e['team'], e['player'])] += 1
    keys = set(panel) | set(explained)
    leftover = sorted(
        (f'{a}|{b}|{c}', panel.get((a, b, c), 0), explained.get((a, b, c), 0))
        for (a, b, c) in keys
        if panel.get((a, b, c), 0) != explained.get((a, b, c), 0))
    raw_keys = set(panel) | set(nv_db)
    raw_disagree = [k for k in raw_keys
                    if panel.get(k, 0) != nv_db.get(k, 0)]
    return {
        'panel_dropback_total': sum(panel.values()),
        'nflverse_dropback_total': sum(nv_db.values()),
        'residual_panel_minus_nflverse':
            sum(panel.values()) - sum(nv_db.values()),
        'panel_player_games': len(panel),
        'nflverse_player_games': len(nv_db),
        'player_games_disagreeing_with_raw_nflverse': len(raw_disagree),
        'player_games_agreeing_with_raw_nflverse':
            len(raw_keys) - len(raw_disagree),
        'explained_by': {
            'ATTEMPT_NOT_AN_NFLVERSE_DROPBACK': len(att_nodb),
            'rows': att_nodb,
        },
        'unexplained_player_games': len(leftover),
        'unexplained_rows': leftover[:50],
        'derivation': (
            'The frozen attempt definition is pass_attempt & !sack & !spike. '
            'nflverse leaves qb_dropback at 0 on a small number of rows that '
            'satisfy it anyway: two-point conversion passes (7 of the 9), one '
            'replay-reversed sack inside a penalty no_play, and one blocked '
            'field goal carrying pass_attempt = 1. The residual must equal '
            'that enumerated set exactly; the tolerance is the count of those '
            'rows, not a percentage.'),
        'scrambles_excluded_as_not_a_dropback': sum(
            1 for e in exceptions if e['kind'] == 'SCRAMBLE_NOT_A_DROPBACK'),
        'dropbacks_with_no_player_id': sum(
            1 for e in exceptions if e['kind'] == 'DROPBACK_WITH_NO_PLAYER_ID'),
    }


def _write_gz(rows, path):
    """Deterministic gzip: mtime 0, so the content hash is a content hash."""
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode='wb', mtime=0) as gz:
        with io.TextIOWrapper(gz, encoding='utf-8', newline='') as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    data = buf.getvalue()
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest(), len(data)


def _sha(path):
    return (hashlib.sha256(path.read_bytes()).hexdigest()
            if path.exists() else None)


def build(seasons=SEASONS):
    qb_rows, rc_rows, prov = [], [], []
    nv_db = collections.Counter()
    exceptions = []
    for s in seasons:
        p = RAW / f'play_by_play_{s}.csv.gz'
        if not p.exists():
            raise SystemExit(
                f'Q7_RAW_SEASON_MISSING: {p} is absent. A season silently '
                f'skipped would shrink the frame without saying so. It is '
                f're-fetchable from the url and hash in '
                f'nfl/research/track1/RAW_PROVENANCE.json.')
        qb, rc, ry, names, meta, nv, exc = reduce_season(p)
        nv_db.update(nv)
        exceptions.extend(exc)
        raw = p.read_bytes()
        prov.append({'season': s, 'file': str(p.relative_to(_REPO)),
                     'sha256': hashlib.sha256(raw).hexdigest(),
                     'n_bytes': len(raw), 'source_url': URL.format(season=s),
                     'source_name': 'nflverse_pbp', 'source_rank': 1})
        for (gid, team, pid), c in sorted(qb.items()):
            m = meta[gid]
            att, sk, sc = int(c['att']), int(c['sacks']), int(c['scr'])
            db = att + sk + sc
            if db <= 0:
                continue
            qb_rows.append({
                'game_id': gid, 'season': m['season'], 'week': m['week'],
                'ord': m['season'] * 100 + m['week'], 'team': team,
                'gsis_id': pid, 'name': names.get(pid, ''),
                'db': db, 'att': att, 'cmp': int(c['cmp']),
                'sacks': sk, 'scr': sc, 'pyds': int(c['pyds']),
                'ptd': int(c['ptd']), 'int': int(c['int'])})
        for (gid, team, rid), c in sorted(rc.items()):
            m = meta[gid]
            rc_rows.append({
                'game_id': gid, 'season': m['season'], 'week': m['week'],
                'ord': m['season'] * 100 + m['week'], 'team': team,
                'gsis_id': rid, 'name': names.get(rid, ''),
                'targets': int(c['targets']), 'rec': int(c['rec']),
                'rec_yds': int(c['rec_yds']), 'rec_td': int(c['rec_td']),
                'rec_yards_list': '|'.join(
                    str(x) for x in ry.get((gid, team, rid), []))})
    # ---- the checks, BEFORE a byte is written
    for rows, path, where, cols in (
            (qb_rows, QB, 'QB_PANEL', QB_COUNT_COLUMNS),
            (rc_rows, RECV, 'RECV_PANEL', RECV_COUNT_COLUMNS)):
        if not rows:
            raise SystemExit(f'Q7_EMPTY_PANEL: {path} would carry no rows. An '
                             f'empty panel is an error, not a result.')
        assert_no_market_column(list(rows[0]), where)
        assert_not_degenerate(rows, cols, where)
    bad = [r for r in qb_rows if r['att'] + r['sacks'] + r['scr'] != r['db']]
    if bad:
        raise SystemExit(f'Q7_DROPBACK_IDENTITY_VIOLATED: {len(bad)} rows')
    rec = reconcile(qb_rows, nv_db, exceptions)
    if rec['unexplained_player_games']:
        raise SystemExit(
            f'Q7_DROPBACK_RECONCILIATION_FAILED: '
            f"{rec['unexplained_player_games']} player-game(s) differ from "
            f'nflverse qb_dropback for a reason this build cannot name. '
            f"First: {rec['unexplained_rows'][:5]}. The composed identity "
            f'cannot detect this; that is why this check exists.')
    # ---- write
    qb_sha, qb_bytes = _write_gz(qb_rows, QB)
    rc_sha, rc_bytes = _write_gz(rc_rows, RECV)
    RECONCILIATION.write_text(json.dumps(
        {'artifact': 'NFL_Q7_DROPBACK_RECONCILIATION',
         'spec_version': SPEC_VERSION,
         'reference': 'nflverse play-by-play column `qb_dropback`',
         'why': ('The composed identity att + sacks + scr == db is a '
                 'tautology and cannot detect a counter that is never '
                 'reached. This is the external check it displaced.'),
         **rec}, indent=1) + '\n')
    MANIFEST.write_text(json.dumps({
        'artifact': 'NFL_Q7_RAW_PROVENANCE', 'spec_version': SPEC_VERSION,
        'supersedes_spec_version': SUPERSEDES_SPEC_VERSION,
        'market_columns_refused': list(FORBIDDEN_SUBSTRINGS),
        'definitions': {
            'attempt': 'pass_attempt and not sack and not spike',
            'completion': 'an attempt that completed',
            'sack': 'a sack on a dropback',
            'scramble': ('a scramble on a dropback that is not a sack, '
                         'charged to rusher_player_id'),
            'dropback': ('attempts + sacks + scrambles, COMPOSED and ALSO '
                         'reconciled against nflverse qb_dropback'),
        },
        'artifacts': {
            'qb': {'path': str(QB.relative_to(_REPO)), 'sha256': qb_sha,
                   'n_bytes': qb_bytes, 'n_rows': len(qb_rows)},
            'recv': {'path': str(RECV.relative_to(_REPO)), 'sha256': rc_sha,
                     'n_bytes': rc_bytes, 'n_rows': len(rc_rows)},
        },
        'checks': ['NO_MARKET_COLUMN', 'NO_DEGENERATE_COUNT_COLUMN',
                   'DROPBACK_IDENTITY', 'NFLVERSE_DROPBACK_RECONCILIATION'],
        'seasons': prov}, indent=1) + '\n')
    SUPERSESSION.write_text(json.dumps({
        'artifact': 'NFL_Q7_PANEL_SUPERSESSION',
        'spec_version': SPEC_VERSION,
        'supersedes': SUPERSEDES_SPEC_VERSION,
        'defect': ('q7-panel-1 charged QB counters to passer_player_id only. '
                   'A qb_scramble play carries no passer id, so the `scr` '
                   'column was built with 1 scramble across 4,025 QB-games '
                   'against 5,864 in the same six seasons, and the composed '
                   'dropback total was 116,190 against nflverse 122,044.'),
        'why_it_was_not_caught': (
            'The only dropback check was the composed identity '
            'att + sacks + scr == db, which is true of any three numbers and '
            'cannot detect a counter that is never reached.'),
        'superseded_artifacts': {
            str(SUPERSEDED_QB.relative_to(_REPO)): _sha(SUPERSEDED_QB),
            str(SUPERSEDED_RECV.relative_to(_REPO)): _sha(SUPERSEDED_RECV),
            str(SUPERSEDED_MANIFEST.relative_to(_REPO)):
                _sha(SUPERSEDED_MANIFEST),
        },
        'superseded_artifacts_retained': True,
        'retention_reason': (
            'The published Q7 conclusions were computed from the version-1 '
            'panel. Deleting it would delete the audit trail of every '
            'conclusion drawn from it.'),
        'conclusions_drawn_from_the_superseded_panel': [
            'nfl/research/q7/Q7_DECISION.md',
            'nfl/research/q7/Q7_FORWARD_CHAIN_RESULTS.json',
            'nfl/research/q7/Q7_SCORED_ROWS.csv.gz',
            'nfl/research/q7/Q7_DIAGNOSTICS.csv',
        ],
        'rebuilt_comparison': 'nfl/research/v4/p5/P5_Q7_SCRAMBLE_REPAIR.md',
    }, indent=1) + '\n')
    return {'qb_game_rows': len(qb_rows), 'recv_game_rows': len(rc_rows),
            'seasons': list(seasons), 'qb_sha256': qb_sha,
            'recv_sha256': rc_sha,
            'scrambles': sum(r['scr'] for r in qb_rows),
            'reconciliation': {k: v for k, v in rec.items()
                               if k != 'explained_by'}}


def load(path, ints=(), lists=()):
    """Read a panel, or raise a NAMED error. Never a bare FileNotFoundError.

    Ten modules outside Q7 call `load_recv`. Spec version 2 moved the default
    paths, so a checkout where the panel has not been rebuilt must say exactly
    that rather than surfacing an opaque traceback from inside gzip -- and must
    not silently fall back to the superseded artifact, which is how a corrected
    build quietly stops being the thing that runs.
    """
    path = pathlib.Path(path)
    if not path.exists():
        raise SystemExit(
            f'Q7_PANEL_NOT_BUILT: {path} is absent. Spec version '
            f'{SPEC_VERSION} writes the corrected panel beside the superseded '
            f'one; rebuild with `python3.12 -m nfl.research.q7.panel`. There '
            f'is deliberately no fallback to the superseded artifact.')
    with gzip.open(path, 'rt', newline='') as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        for k in ints:
            r[k] = int(r[k])
        for k in lists:
            r[k] = [int(x) for x in r[k].split('|') if x != '']
    return rows


QB_INTS = ('season', 'week', 'ord', 'db', 'att', 'cmp', 'sacks', 'scr',
           'pyds', 'ptd', 'int')
RECV_INTS = ('season', 'week', 'ord', 'targets', 'rec', 'rec_yds', 'rec_td')


def load_qb(path=None):
    return load(path or QB, QB_INTS)


def load_recv(path=None):
    return load(path or RECV, RECV_INTS, ('rec_yards_list',))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--seasons', default=','.join(str(s) for s in SEASONS))
    a = ap.parse_args(argv)
    print(json.dumps(build(tuple(int(x) for x in a.seasons.split(','))),
                     indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
