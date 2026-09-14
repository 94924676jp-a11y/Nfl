"""Hierarchical reference bands. A DIAGNOSTIC INSTRUMENT AND NOTHING ELSE.

WHAT A REFERENCE BAND IS FOR, AND THE ONE QUESTION IT ANSWERS

    Is this player's conditional projection unusually low or high relative to
    his own history, his team's history, or his role's history?

That is the whole contract. A band is a DESCRIPTION OF THE PAST. It is never a
floor, never a cap, never a correction, and never an input. Nothing in this
module may be imported by anything under `nfl/production/` or `nfl/product/`,
and `nfl/tests/test_refbands.py` asserts that by reading the tree, because a
comment saying "diagnostic only" is not a control.

The failure mode this guards against is specific and it is seductive: a
projection lands at the 4th percentile of its role band, someone widens or
shifts the projection toward the band, and the band -- which is a marginal,
unconditional, historical summary -- has silently become a prior on a
conditional forecast. The band knows nothing about tonight. It cannot know
whether the 4th percentile is an error or the entire point of having a model.

THREE DEFINITIONAL TRAPS, ALL THREE ALREADY SPRUNG IN THIS PROJECT

1.  GROUP BY (game_id, posteam), NEVER BY game_id. Taking the top passer of a
    GAME selects the better of the two starting quarterbacks and inflates
    every band. D3's own first pass did this and corrected it.

2.  `pass_attempt` IN nflverse INCLUDES SACKS AND SPIKES. It is not the
    passing-attempts statistic a box score reports and it is not what this
    repository's own `nfl/research/qb2/build_qb.py` calls `attempts`. The two
    differ by 2.44 per team-game over 2021-2024 REG, which is most of an
    interquartile step. Both are computed here and both are named; neither is
    called "pass attempts" without a qualifier.

3.  KNEELS ARE RUSHING ATTEMPTS IN THE FEED. `qb_kneel == '1'` is excluded
    from every rushing count here, as in the broad bands this extends.

CHRONOLOGY

Bands used to assess a forecast must be built from data lawfully available
before that forecast's cutoff. The cutoff is FORECAST_CUTOFF below. A prior
agent globbed `pbp_20*` and pulled the forecast season's own results into a
"historical" frame. There is therefore no wildcard season accessor in this
module: `pbp_path()` takes an integer and refuses any season at or after
FORECAST_SEASON before it touches the filesystem.
"""
from __future__ import annotations

import collections
import csv
import gzip
import math
import pathlib
import sys

import numpy as np

_ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

POSTGAME = _ROOT / 'nfl' / 'research' / 'postgame'
PANEL_P3 = _ROOT / 'nfl' / 'research' / 'inputs' / 'panel_p3.csv.gz'

SPEC_VERSION = 'refbands-diagnostic-1'

# --- chronology ------------------------------------------------------------
FORECAST_CUTOFF = '2026-09-14T17:40:19Z'
FORECAST_SEASON = 2026
#: seasons with a play-by-play blob in the postgame corpus AND wholly before
#: the cutoff. 2025 is lawful but HAS NO pbp BLOB in this repository; it is
#: reachable only through PANEL_SEASONS below, on the reduced metric set that
#: `panel_p3` carries.
PBP_SEASONS = (2021, 2022, 2023, 2024)
PANEL_SEASONS = (2021, 2022, 2023, 2024, 2025)


class ChronologyError(RuntimeError):
    """A season at or after the forecast season was requested."""


class EmptyStageError(RuntimeError):
    """A stage produced nothing. Zeros and empties are errors, not results."""


def assert_lawful_season(season) -> int:
    s = int(season)
    if s >= FORECAST_SEASON:
        raise ChronologyError(
            f'REFBANDS_SEASON_NOT_LAWFUL: season {s} is at or after the '
            f'forecast season {FORECAST_SEASON}. Its games are the outcomes '
            f'this board is being assessed against, and one of them '
            f'(DEN@KC) has not been played. Cutoff {FORECAST_CUTOFF}.')
    return s


def pbp_path(season) -> pathlib.Path:
    """The single play-by-play blob for one lawful season. No wildcards."""
    s = assert_lawful_season(season)
    hits = sorted(POSTGAME.glob(f'pbp_{s}.*.csv.gz'))
    if len(hits) != 1:
        raise EmptyStageError(
            f'REFBANDS_PBP_BLOB_NOT_UNIQUE: season {s} resolved {len(hits)} '
            f'blobs under {POSTGAME}; expected exactly 1.')
    return hits[0]


# --- adequacy and shrinkage, both DERIVED ---------------------------------
#
# ALPHA and the quantile levels are the two declarations. Everything numeric
# below follows from them by formula; nothing here was chosen by looking at an
# output.
ALPHA = 0.05
LEVELS = (10, 25, 50, 75, 90)


def n_min_for(level: int, alpha: float = ALPHA) -> int:
    """Smallest n at which the sample is >= (1-alpha) likely to contain an
    observation at or beyond the tail being reported.

        P(at least one of n observations in the t-tail) = 1 - (1-t)^n >= 1-a
        =>  n >= ln(a) / ln(1-t)

    Below this, the empirical quantile at that level is not an estimate from
    data in the region; it is an extrapolation from the nearest point that
    happens to exist. p10/p90 -> 29, p25/p75 -> 11, p50 -> 5.
    """
    t = min(level, 100 - level) / 100.0
    return int(math.ceil(math.log(alpha) / math.log(1.0 - t)))


#: n at which a group's own EXTREME reported quantiles first become estimable.
#: Used as the shrinkage half-weight constant, so a group reaches equal weight
#: with its parent exactly where its own widest band becomes admissible.
N0 = n_min_for(min(LEVELS))          # == 29
#: below this a group gets no own band at any level.
N_FLOOR = n_min_for(50)              # == 5

INSUFFICIENT = 'INSUFFICIENT_EVIDENCE'


def raw_band(values, levels=LEVELS) -> dict:
    """Empirical quantiles. `method='linear'` is declared, not defaulted."""
    a = np.asarray(list(values), dtype=float)
    if a.size == 0:
        raise EmptyStageError('REFBANDS_EMPTY_GROUP: raw_band got 0 values.')
    out = {f'p{L}': float(np.percentile(a, L, method='linear')) for L in levels}
    out['mean'] = float(a.mean())
    out['n'] = int(a.size)
    return out


def adequacy(n: int, levels=LEVELS) -> dict:
    return {f'p{L}': ('OK' if n >= n_min_for(L) else INSUFFICIENT)
            for L in levels}


def shrink(child: dict, parent: dict, n: int, n0: int = N0,
           levels=LEVELS) -> dict:
    """Convex blend of a group's own band with its parent's.

        w = n / (n + n0)

    n0 is NOT fitted. It is n_min_for(10) = 29, the sample size at which the
    widest quantile pair this module publishes first becomes estimable from
    data rather than extrapolated. Publish a different quantile pair and n0
    moves by the same formula. No outcome was consulted in choosing it.

    Because both inputs are monotone in the level and w is in [0,1], the blend
    is monotone too -- a shrunk band cannot cross itself.
    """
    w = n / (n + n0)
    out = {f'p{L}': w * child[f'p{L}'] + (1 - w) * parent[f'p{L}']
           for L in levels}
    out['mean'] = w * child['mean'] + (1 - w) * parent['mean']
    out['n'] = int(n)
    out['w_own'] = float(w)
    return out


def percentile_of(value: float, values) -> float:
    """Where `value` sits in an empirical sample, as a percentile. Midrank, so
    ties do not silently round a projection to one side of a mass point."""
    a = np.asarray(list(values), dtype=float)
    below = float((a < value).sum())
    equal = float((a == value).sum())
    return 100.0 * (below + 0.5 * equal) / a.size


def clustered_band_ci(values, clusters, level: int, b: int = 400,
                      seed: int = 20260914) -> dict:
    """Bootstrap CI for one quantile, resampling CLUSTERS, not rows.

    Team-games inside one game move together -- pace, score state and weather
    are shared -- so a row-level bootstrap understates the interval. The
    cluster is the game."""
    vals = np.asarray(list(values), dtype=float)
    cl = np.asarray(list(clusters))
    uniq, inv = np.unique(cl, return_inverse=True)
    idx_by_cluster = [np.flatnonzero(inv == k) for k in range(uniq.size)]
    rng = np.random.default_rng(seed)
    draws = np.empty(b, dtype=float)
    for i in range(b):
        pick = rng.integers(0, uniq.size, uniq.size)
        sel = np.concatenate([idx_by_cluster[j] for j in pick])
        draws[i] = np.percentile(vals[sel], level, method='linear')
    return {'level': level, 'n_clusters': int(uniq.size), 'b': b,
            'lo': float(np.percentile(draws, 2.5)),
            'hi': float(np.percentile(draws, 97.5))}


# --- the usage panel -------------------------------------------------------
#
# Counter names follow `nfl/research/qb2/build_qb.py` so that a band and the
# board it is used to read are the same statistic:
#
#   att_raw  = pass_attempt                      (INCLUDES sacks and spikes)
#   attempts = pass_attempt & !sack & !spike     (the board's `qb/att`)
#   dropbacks= att_raw + scrambles - spikes      (the board's `qb/db`)
#
# Two-point plays are RETAINED, matching build_qb.py, so that these bands and
# the board's own numbers are the same quantity. Excluding them moves QB1
# att_raw by -0.17 per team-game; the variant is reported in the write-up and
# is not the published band.
PANEL_FIELDS = ('season', 'week', 'game_id', 'team', 'opponent', 'home',
                'player_id', 'position', 'att_raw', 'attempts', 'completions',
                'sacks', 'spikes', 'scrambles', 'dropbacks', 'pass_yards',
                'carries', 'rush_yards', 'targets', 'receptions', 'rec_yards',
                'first_dropback', 'route_proxy', 'offense_pct')


def _i(v) -> int:
    return 1 if v == '1' else 0


def _f(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def load_positions():
    """(season, gsis_id) -> position, plus a career-modal fallback, from the
    committed `panel_p3` leaf. Play-by-play carries no position column."""
    by_season, career = {}, collections.defaultdict(collections.Counter)
    with gzip.open(PANEL_P3, 'rt') as fh:
        for r in csv.DictReader(fh):
            pos = (r['position'] or '').strip()
            if not pos:
                continue
            by_season[(int(r['season']), r['gsis_id'])] = pos
            career[r['gsis_id']][pos] += 1
    if not by_season:
        raise EmptyStageError('REFBANDS_NO_POSITIONS: panel_p3 gave 0 rows.')
    modal = {p: c.most_common(1)[0][0] for p, c in career.items()}
    return by_season, modal


def load_participation():
    """(game_id, gsis_id) -> (pass-play participation snaps, offense share).

    `pass_snaps` counts a player present on the field for a team dropback. It
    is an UPPER BOUND on routes run, not routes run: a receiver on the field
    may stay in to block. It is labelled ROUTE_PROXY_PASS_PARTICIPATION
    everywhere it is published and is never called a route count."""
    out = {}
    with gzip.open(PANEL_P3, 'rt') as fh:
        for r in csv.DictReader(fh):
            pct = r['offense_pct']
            out[(r['game_id'], r['gsis_id'])] = (
                int(r['pass_snaps'] or 0),
                float(pct) if pct not in ('', 'NA') else None)
    if not out:
        raise EmptyStageError('REFBANDS_NO_PARTICIPATION: panel_p3 gave 0 rows.')
    return out


def build_pbp_panel(seasons=PBP_SEASONS):
    """One row per (game_id, team, player) with any offensive usage."""
    pos_season, pos_modal = load_positions()
    part = load_participation()
    acc = collections.defaultdict(collections.Counter)
    meta, first_db = {}, {}
    for s in seasons:
        with gzip.open(pbp_path(s), 'rt') as fh:
            for r in csv.DictReader(fh):
                if r['season_type'] != 'REG':
                    continue
                team = r['posteam']
                if not team:
                    continue
                gid = r['game_id']
                if gid not in meta:
                    meta[gid] = (int(r['season']), int(r['week']),
                                 r['home_team'], r['away_team'])
                pid_pass = r['passer_player_id']
                pid_rush = r['rusher_player_id']
                pid_rec = r['receiver_player_id']
                sack, spike = _i(r['sack']), _i(r['qb_spike'])
                pa = _i(r['pass_attempt'])
                if pid_pass:
                    c = acc[(gid, team, pid_pass)]
                    c['att_raw'] += pa
                    c['sacks'] += sack
                    c['spikes'] += spike
                    c['attempts'] += 1 if (pa and not sack and not spike) else 0
                    c['completions'] += _i(r['complete_pass'])
                    c['pass_yards'] += _f(r['passing_yards'])
                if pid_rush:
                    c = acc[(gid, team, pid_rush)]
                    c['scrambles'] += _i(r['qb_scramble'])
                    if _i(r['rush_attempt']) and not _i(r['qb_kneel']):
                        c['carries'] += 1
                        c['rush_yards'] += _f(r['rushing_yards'])
                if pid_rec and pa:
                    c = acc[(gid, team, pid_rec)]
                    c['targets'] += 1
                    c['receptions'] += _i(r['complete_pass'])
                    c['rec_yards'] += _f(r['receiving_yards'])
                if _i(r['qb_dropback']):
                    key = (gid, team)
                    pl = int(r['play_id'])
                    if key not in first_db or pl < first_db[key][0]:
                        first_db[key] = (pl, pid_pass or pid_rush or '')
    if not acc:
        raise EmptyStageError('REFBANDS_EMPTY_PANEL: pbp produced 0 rows.')
    rows = []
    for (gid, team, pid), c in acc.items():
        season, week, home, away = meta[gid]
        ps, pct = part.get((gid, pid), (None, None))
        rows.append({
            'season': season, 'week': week, 'game_id': gid, 'team': team,
            'opponent': away if team == home else home,
            'home': 1 if team == home else 0,
            'player_id': pid,
            'position': pos_season.get((season, pid))
                        or pos_modal.get(pid) or 'UNK',
            'att_raw': c['att_raw'], 'attempts': c['attempts'],
            'completions': c['completions'], 'sacks': c['sacks'],
            'spikes': c['spikes'], 'scrambles': c['scrambles'],
            'dropbacks': c['att_raw'] + c['scrambles'] - c['spikes'],
            'pass_yards': round(c['pass_yards'], 1),
            'carries': c['carries'], 'rush_yards': round(c['rush_yards'], 1),
            'targets': c['targets'], 'receptions': c['receptions'],
            'rec_yards': round(c['rec_yards'], 1),
            'first_dropback': 1 if first_db.get((gid, team), (0, ''))[1] == pid
                              else 0,
            'route_proxy': ps if ps is not None else '',
            'offense_pct': pct if pct is not None else '',
        })
    rows.sort(key=lambda r: (r['game_id'], r['team'], r['player_id']))
    return rows


# --- roles -----------------------------------------------------------------
RB_POS = ('RB', 'FB')


def assign_roles(rows):
    """Depth roles WITHIN a team-game, from realised usage.

    These are OBSERVED ranks, not depth-chart ranks: 'RB1' here means the back
    who led that team in carries in that game. That is the right frame for a
    band (it describes the distribution of the lead role), and it is the wrong
    frame for a forecast (tonight's lead back is not yet observed). Stated so
    that nobody reads a band as a prediction of who will lead."""
    by_tg = collections.defaultdict(list)
    for r in rows:
        by_tg[(r['game_id'], r['team'])].append(r)
    for tg, group in by_tg.items():
        for r in group:
            r['roles'] = []

        def rank(cands, key, label, cap):
            ordered = sorted([c for c in cands if c[key] > 0],
                             key=lambda c: (-c[key], c['player_id']))
            for i, c in enumerate(ordered[:cap], start=1):
                c['roles'].append(f'{label}{i}')

        rank(group, 'dropbacks', 'QB', 3)
        # position-agnostic, matching the broad bands this extends
        rank(group, 'carries', 'RUSH', 3)
        rank([c for c in group if c['position'] in RB_POS], 'carries', 'RB', 3)
        rank([c for c in group if c['position'] == 'WR'], 'targets', 'WR', 4)
        rank([c for c in group if c['position'] == 'TE'], 'targets', 'TE', 3)
    return rows


def starter_class(r) -> str:
    """Snap-share class. A PROXY for 'started', not a start.

    For a quarterback the repository can do better than a share: the passer or
    scrambler on his team's first dropback of the game is the one who took the
    game's first pass play. That is FIRST_DROPBACK below. Everyone else is
    classified by offensive snap share, and a missing share says UNKNOWN
    rather than guessing."""
    if r['position'] == 'QB':
        return 'FIRST_DROPBACK' if r['first_dropback'] else 'RELIEF'
    pct = r['offense_pct']
    if pct in ('', None):
        return 'UNKNOWN'
    pct = float(pct)
    if pct >= 0.55:
        return 'STARTER'
    if pct >= 0.25:
        return 'ROTATIONAL'
    return 'RESERVE'


# --- the hierarchy ---------------------------------------------------------
#
# Every level names its PARENT, and a sparse group is blended toward that
# parent by `shrink()`. The chain is deliberately short: a group's parent is
# the smallest cohort that still contains it and is certain to be dense.
#
#   player x role x recent8  ->  player x role  ->  role  ->  position  ->  -
#   player x role x season   ->  player x role
#   role x team              ->  role
#   role x season            ->  role
#   role x starter-class     ->  role
ROLE_METRICS = {
    'QB1': ('attempts', 'att_raw', 'dropbacks', 'pass_yards', 'completions'),
    'QB2': ('attempts', 'att_raw', 'dropbacks', 'pass_yards'),
    'QB3': ('attempts', 'dropbacks'),
    'RUSH1': ('carries',), 'RUSH2': ('carries',), 'RUSH3': ('carries',),
    'RB1': ('carries', 'targets', 'receptions', 'route_proxy'),
    'RB2': ('carries', 'targets', 'receptions', 'route_proxy'),
    'RB3': ('carries', 'targets', 'receptions', 'route_proxy'),
    'WR1': ('targets', 'receptions', 'rec_yards', 'route_proxy'),
    'WR2': ('targets', 'receptions', 'rec_yards', 'route_proxy'),
    'WR3': ('targets', 'receptions', 'rec_yards', 'route_proxy'),
    'WR4': ('targets', 'receptions', 'rec_yards', 'route_proxy'),
    'TE1': ('targets', 'receptions', 'rec_yards', 'route_proxy'),
    'TE2': ('targets', 'receptions', 'rec_yards', 'route_proxy'),
    'TE3': ('targets', 'receptions', 'rec_yards', 'route_proxy'),
}
#: the cohort a role's band is shrunk toward. RUSH* is position-agnostic by
#: construction -- it is the broad bands' "lead rusher" -- so its cohort is
#: every ball-carrier, not every running back.
ROLE_COHORT = {r: ('ANYRUSHER' if r.startswith('RUSH') else r[:2])
               for r in ROLE_METRICS}
RECENT_WINDOW = 8   # half a regular season. See the note in build_hierarchy.


def _vals(rows, metric):
    out, clus = [], []
    for r in rows:
        v = r.get(metric, '')
        if v == '' or v is None:
            continue
        out.append(float(v))
        clus.append(r['game_id'])
    return out, clus


def _record(level, key, metric, rows, parent_band, parent_key):
    vals, clus = _vals(rows, metric)
    n = len(vals)
    rec = {'level': level, 'key': key, 'metric': metric, 'n': n,
           'n_clusters': len(set(clus)), 'parent_key': parent_key}
    if n == 0:
        rec.update({'status': INSUFFICIENT, 'reason': 'no observations',
                    'own': None, 'adequacy': None, 'band': parent_band,
                    'band_source': 'parent'})
        return rec
    own = raw_band(vals)
    rec['own'] = own
    rec['adequacy'] = adequacy(n)
    if parent_band is None:
        rec.update({'status': 'OWN', 'band': own, 'band_source': 'own'})
        return rec
    if n < N_FLOOR:
        rec.update({'status': INSUFFICIENT,
                    'reason': f'n={n} < N_FLOOR={N_FLOOR}; below this even the '
                              f'median is an extrapolation',
                    'band': parent_band, 'band_source': 'parent'})
        return rec
    rec.update({'status': 'SHRUNK' if n < N0 else 'OWN_DOMINANT',
                'band': shrink(own, parent_band, n), 'band_source': 'shrunk'})
    return rec


def build_hierarchy(rows):
    """Every band record, at every level, with n on every one.

    RECENT_WINDOW = 8 is declared, not fitted, and it is chosen so that the
    level is honest by construction: 8 clears N_FLOOR (5) but not n_min_for(25)
    (11), so a recent-window band can never publish its own p25/p75 or p10/p90
    and is always shrunk at weight 8/(8+29) = 0.216 toward the player's full
    history. A recent window that could publish a confident tail would be the
    defect, not the feature."""
    for r in rows:
        r['starter_class'] = starter_class(r)
    recs = []

    # L1 position cohorts (no parent, no shrinkage)
    cohort_rows = collections.defaultdict(list)
    for r in rows:
        cohort_rows[r['position']].append(r)
        if r['carries'] > 0:
            cohort_rows['ANYRUSHER'].append(r)
    cohort_band = {}
    for role, metrics in ROLE_METRICS.items():
        coh = ROLE_COHORT[role]
        for m in metrics:
            if (coh, m) in cohort_band:
                continue
            sub = cohort_rows.get(coh, [])
            vals, _ = _vals(sub, m)
            if not vals:
                cohort_band[(coh, m)] = None
                continue
            rec = _record('position', f'pos:{coh}', m, sub, None, None)
            cohort_band[(coh, m)] = rec['band']
            recs.append(rec)

    role_rows = collections.defaultdict(list)
    for r in rows:
        for role in r['roles']:
            role_rows[role].append(r)

    role_band = {}
    for role, metrics in ROLE_METRICS.items():
        rr = role_rows.get(role, [])
        for m in metrics:
            pb = cohort_band.get((ROLE_COHORT[role], m))
            rec = _record('role', f'role:{role}', m, rr, pb,
                          f'pos:{ROLE_COHORT[role]}')
            role_band[(role, m)] = rec['band']
            recs.append(rec)

            pk = f'role:{role}'
            # L3 role x season
            for s in sorted({x['season'] for x in rr}):
                recs.append(_record(
                    'role_season', f'role:{role}|season:{s}', m,
                    [x for x in rr if x['season'] == s], rec['band'], pk))
            # L4 role x team (the "system" level)
            for t in sorted({x['team'] for x in rr}):
                recs.append(_record(
                    'role_team', f'role:{role}|team:{t}', m,
                    [x for x in rr if x['team'] == t], rec['band'], pk))
            # L8 role x starter class
            for sc in sorted({x['starter_class'] for x in rr}):
                recs.append(_record(
                    'role_starter', f'role:{role}|starter:{sc}', m,
                    [x for x in rr if x['starter_class'] == sc],
                    rec['band'], pk))
            # L5/L6/L7 player levels
            by_p = collections.defaultdict(list)
            for x in rr:
                by_p[x['player_id']].append(x)
            for pid, pr in by_p.items():
                prec = _record('player_role', f'player:{pid}|role:{role}', m,
                               pr, rec['band'], pk)
                recs.append(prec)
                ppk = f'player:{pid}|role:{role}'
                for s in sorted({x['season'] for x in pr}):
                    recs.append(_record(
                        'player_role_season',
                        f'player:{pid}|role:{role}|season:{s}', m,
                        [x for x in pr if x['season'] == s],
                        prec['band'], ppk))
                recent = sorted(pr, key=lambda x: (x['season'], x['week'])
                                )[-RECENT_WINDOW:]
                recs.append(_record(
                    'player_role_recent',
                    f'player:{pid}|role:{role}|last{RECENT_WINDOW}', m,
                    recent, prec['band'], ppk))
    if not recs:
        raise EmptyStageError('REFBANDS_NO_RECORDS: hierarchy built 0 bands.')
    return recs
