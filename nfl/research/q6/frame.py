"""Q6 step 1: the frame, the role classes, and the arms' feature builders.

WHAT THIS REUSES RATHER THAN REBUILDS.

The population is `appearance_r8.enriched_frame()` -- the played panel unioned
with the point-in-time depth listing -- imported, not reimplemented. A second
copy of the frame would be a second thing to drift, and the frame is the whole
of R7's repair.

WHAT IS ADDED HERE.

  * ROLE CLASS, point-in-time. Rank inside (team, week, position) by a
    TRAILING snap-share mean built from strictly earlier rows, falling back to
    the depth rank and then to the lowest class. `r['snap']` is THIS game's
    snap share and is never used for the row it belongs to -- a player has a
    snap share if and only if he appeared, so using it would carry the label.
    R8 documents the same trap after scoring an in-sample Brier of 0.04101 the
    one time it was featurised.

  * REALISED OPPORTUNITY, for the role and composition layers: targets and
    carries with their team totals, aggregated from the same player panel the
    denominators were originally built from, so the identity
    share x team total == player opportunity holds exactly.

  * THE Q6 FEATURE ADDITIONS, both pregame-legal: the injury designation
    interacted with depth rank, and the practice status as an ordinal.

WHAT IS REFUSED. `weekly_rosters.status` is never read at any point. Nor is any
2026 row, any market quantity, or any column knowable only after kickoff.
"""
from __future__ import annotations

import collections
import csv
import gzip
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
for _q in (str(_REPO), str(_REPO / 'nfl' / 'research' / 'p2')):
    if _q not in sys.path:
        sys.path.insert(0, _q)

from nfl.production.nonqb import appearance_r7 as R7              # noqa: E402
from nfl.production.nonqb import appearance_r8 as R8              # noqa: E402
from sportsplatform.governance.outcome import State               # noqa: E402

SPEC_VERSION = 'q6-frame-1'
PANEL = _REPO / 'nfl' / 'research' / 'inputs' / 'panel_p3.csv.gz'

POSITIONS = ('RB', 'WR', 'TE')
# Both opportunity pools. A running back catches passes and a receiver takes
# handoffs; assigning one metric per position would drop the first outright.
METRICS = ('targets', 'carries')
ROLE_CLASSES = ('starter', 'rotational', 'fringe')
TRAIL = 8                     # the same trailing window the role prior uses
EVAL_SEASONS = (2022, 2023, 2024, 2025)

# Refused as inputs, by name. The check is on the feature-name list this code
# builds, never on what some upstream file happens to contain.
FORBIDDEN_INPUTS = ('weekly_rosters.status', 'roster_status', 'status_ina',
                    'inactive_list', 'spread', 'vegas', 'total_line', 'odds',
                    'final_', 'realized_', 'postgame')

# The practice-status ladder, as an ordinal. R8 carries only the improving and
# worsening flags derived from consecutive weeks; the level itself is a
# different quantity and is not currently a feature.
PRACTICE_ORDINAL = (
    ('Full Participation in Practice', 0.0),
    ('Limited Participation in Practice', 0.5),
    ('Did Not Participate In Practice', 1.0),
)


def assert_pregame_only(feature_names):
    bad = [f for f in feature_names
           if any(s in str(f).lower() for s in FORBIDDEN_INPUTS)]
    if bad:
        raise ValueError(
            f'Q6_NON_PREGAME_INPUT: {bad}. Game-day roster status, postgame '
            f'quantities and market quantities may not enter an appearance '
            f'model. The list is refused, not filtered.')
    return True


def _rank_group(rk):
    if rk == 1:
        return 'r1'
    if rk in (2, 3):
        return 'r23'
    return 'r4plus_or_unlisted'


RANK_GROUPS = ('r1', 'r23', 'r4plus_or_unlisted')


def load_frame():
    """R8's union frame, restricted to the positions this layer allocates."""
    o = R8.enriched_frame()
    if o.state is not State.PASS:
        raise SystemExit(f'Q6_FRAME_UNAVAILABLE: {o.state.name}[{o.code}] '
                         f'{o.detail[:200]}')
    rows = [r for r in o.value if r['pos'] in POSITIONS]
    if not rows:
        raise SystemExit('Q6_EMPTY_FRAME: an empty frame is an error, not a '
                         'result.')
    late = [r for r in rows if r['s'] >= 2026]
    if late:
        raise SystemExit(
            f'Q6_LIVE_SEASON_IN_FRAME: {len(late)} row(s) from 2026 or later. '
            f'The 2026 live games are motivation only and may not be fitted.')
    rows.sort(key=lambda r: (r['s'], r['w'], r['t'], r['pid']))
    return rows, dict(o.evidence)


def attach_role_class(rows):
    """Point-in-time role class. Nothing here can see the game being scored."""
    trail = collections.defaultdict(list)
    by_ord = collections.defaultdict(list)
    for r in rows:
        by_ord[(r['s'], r['w'])].append(r)
    for key in sorted(by_ord):
        grp = collections.defaultdict(list)
        for r in by_ord[key]:
            h = trail.get(r['pid'])
            # STRICTLY EARLIER snaps only. `r['snap']` belongs to this game.
            r['trail_snap'] = float(np.mean(h[-TRAIL:])) if h else None
            grp[(r['t'], r['pos'])].append(r)
        for _k, rs in grp.items():
            known = sorted([x for x in rs if x['trail_snap'] is not None],
                           key=lambda x: -x['trail_snap'])
            for i, x in enumerate(known):
                x['role_rank'] = i + 1
                x['role_rank_basis'] = 'TRAILING_SNAP_SHARE'
            for x in rs:
                if x['trail_snap'] is None:
                    rk = x.get('rank')
                    x['role_rank'] = int(rk) if rk else None
                    x['role_rank_basis'] = ('DEPTH_CHART' if rk
                                            else 'NEITHER_LOWEST_CLASS')
        for r in by_ord[key]:
            rk = r.get('role_rank')
            r['role_class'] = ('starter' if rk == 1 else
                               'rotational' if rk in (2, 3) else 'fringe')
        # append AFTER the whole week is classified, so no row inside a week
        # can see another row's outcome in that week
        for r in by_ord[key]:
            if r.get('snap') is not None:
                trail[r['pid']].append(float(r['snap']))
    return rows


def attach_opportunity(rows):
    """Realised targets and carries with their team totals, from the panel.

    The team totals are aggregated from the same player rows the denominators
    were originally built from, so share x team total == opportunity exactly
    rather than to within a percent.
    """
    per, team = {}, collections.defaultdict(collections.Counter)
    with gzip.open(PANEL, 'rt', newline='') as fh:
        for r in csv.DictReader(fh):
            try:
                s, w = int(r['season']), int(r['week'])
            except (KeyError, TypeError, ValueError):
                continue
            tg = int(float(r.get('targets') or 0))
            cy = int(float(r.get('carries') or 0))
            per[(s, w, r['team'], r['gsis_id'])] = {'targets': tg,
                                                    'carries': cy}
            c = team[(s, w, r['team'])]
            c['targets'] += tg
            c['carries'] += cy
    n_with = 0
    for r in rows:
        k = (r['s'], r['w'], r['t'], r['pid'])
        got = per.get(k)
        if got is None:
            # No panel row means the player took no part: a realised zero, and
            # it is exactly the population the union frame exists to supply.
            r['targets'] = 0
            r['carries'] = 0
            r['opportunity_basis'] = 'ZERO_BY_ABSENCE_FROM_PANEL'
        else:
            r['targets'] = got['targets']
            r['carries'] = got['carries']
            r['opportunity_basis'] = 'OBSERVED'
            n_with += 1

    # THE DENOMINATOR IS THE SKILL-POSITION POOL, NOT THE WHOLE TEAM.
    #
    # This is the correction that mattered. The first version divided a
    # player's targets by the TEAM target total while normalising the
    # prediction within his own position group, so predicted shares summed to
    # 1 inside a position while realised shares summed to about 0.55 across
    # three of them. Every measured vacancy ratio came out near 0.6 for that
    # reason alone, which is a denominator artefact and not a football fact.
    #
    # Summed over the FRAME's own RB/WR/TE rows, so the shares of the players
    # being modelled sum to exactly 1 and the simplex is exact rather than
    # approximate. Quarterback rushing is a different layer and is out of this
    # one's scope by declaration, not by oversight.
    tot = collections.defaultdict(collections.Counter)
    for r in rows:
        c = tot[(r['s'], r['w'], r['t'])]
        c['targets'] += r['targets']
        c['carries'] += r['carries']
    for r in rows:
        c = tot[(r['s'], r['w'], r['t'])]
        for m in METRICS:
            den = int(c[m])
            r[f'den_{m}'] = den
            r[f'share_{m}'] = (r[m] / den) if den else None
        r['team_targets'] = int(c['targets'])
        r['team_carries'] = int(c['carries'])
    return rows, {'n_rows_with_a_panel_opportunity_row': n_with,
                  'n_rows_zero_by_absence': len(rows) - n_with}


# ------------------------------------------------------------------- arms
def flat_rate(train_rows):
    """The role-class fallback: appearance rate by position and role class."""
    agg = collections.defaultdict(lambda: [0, 0])
    for r in train_rows:
        a = agg[(r['pos'], r['role_class'])]
        a[0] += int(r['appeared'])
        a[1] += 1
    overall = (sum(int(r['appeared']) for r in train_rows) /
               max(1, len(train_rows)))
    return {k: (v[0] / v[1] if v[1] else overall) for k, v in agg.items()}, overall


def practice_ordinal(s):
    t = (s or '').strip()
    for label, v in PRACTICE_ORDINAL:
        if t == label:
            return v
    return None


def featurise_r8(r, k):
    """The production candidate's design row, imported not restated."""
    return R8.featurise(r, k)


def featurise_q6(r, k):
    """R8's row plus the two Q6 additions. Both are pregame quantities.

    THE INTERACTION IS THE POINT. R8 carries the designation and the depth
    rank as separate main effects, so it can learn that Questionable lowers
    appearance and that rank 1 raises it, but not that a questionable starter
    and a questionable fifth receiver are different events. On a logistic scale
    that is exactly what an interaction term is for.
    """
    f = list(featurise_r8(r, k))
    status = r.get('inj_status')
    grp = _rank_group(r.get('rank'))
    for L in R7.STATUS:
        for g in RANK_GROUPS:
            f.append(1.0 if (status == L and grp == g) else 0.0)
    p = practice_ordinal(r.get('inj_practice'))
    f.append(0.0 if p is None else float(p))
    f.append(1.0 if p is None else 0.0)
    return f


FEATURE_NAMES_Q6_ADDED = tuple(
    [f'inj_{L}_x_rank_{g}' for L in R7.STATUS for g in RANK_GROUPS]
    + ['practice_ordinal', 'practice_ordinal_missing'])

assert_pregame_only(FEATURE_NAMES_Q6_ADDED)


def blank_injury_block(r):
    """A row as an UNFILED injury report presents it. Nothing else moves."""
    q = dict(r)
    q['inj_status'] = None
    q['inj_practice'] = None
    q['inj_available'] = 0
    v1 = dict(q.get('v1') or {}) if q.get('v1') is not None else None
    if v1 is not None:
        for key in ('f_practice_seq', 'f_practice_improving',
                    'f_practice_worsening'):
            v1[key] = None
        q['v1'] = v1
    return q
