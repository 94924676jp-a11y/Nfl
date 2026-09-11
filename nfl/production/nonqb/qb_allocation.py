"""Production QB dropback allocation. CANDIDATE -- not promoted.

WHAT THIS FIXES

R4 measured the engine forecasting 2.62 starting quarterbacks per team: D1 team
dropbacks 36.75 against QB-summed 79.76, a ratio of 2.17, with the quarterbacks
out-dropping their own team in 92.7% of draw cells. The QB layer models a
passer's line CONDITIONAL ON BEING THE PRIMARY PASSER and nothing selected
which of the room that was.

GOVERNANCE. This is a new component evaluated on 2022-2024 development data and
it is NOT promoted. `PATH_C_STATE` is not edited by it. It enters the engine as
a REHEARSAL_ONLY candidate, which is the same runtime role every other non-QB
layer already has, and nothing in the engine is publication-eligible while
NFL-1 is unauthorised.

WHY IT IS STILL THE RIGHT THING TO WIRE IN. Two of its properties are separable:
the CRPS improvement is a forecasting claim on development data and is
exploratory; the SIMPLEX CLOSURE is an accounting property that holds by
construction in every draw. The alternative to wiring it in is leaving the
engine at 2.17x, which is not a neutral default.

PREGAME INPUTS, both available for 2026 and neither blocked on injuries:
  1. the captured depth chart -- QB rank per team
  2. last game's primary passer, strictly-earlier ordinal, spanning seasons

Research: nfl/research/qb3/. Pre-registration sha256
be61392619d45f3ad1936ef0512d203d9f415ba92e271aa6010281e707f05a9e
"""
from __future__ import annotations

import bisect
import collections
import csv
import glob
import gzip
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
for _q in (str(_REPO), str(_REPO / 'nfl' / 'research' / 'qb3')):
    if _q not in sys.path:
        sys.path.insert(0, _q)

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402

SPEC_VERSION = 'qb3-dropback-allocation-candidate-1'
GOVERNANCE = 'CANDIDATE -- evaluated on 2022-2024 development data, NOT promoted'
DEPTH_GLOB = 'depth_charts.*.csv.gz'
KNOWN_LIMITATIONS = {
    'development_data': 'the walk-forward evaluation ran on 2022-2024, which '
                        'are development seasons. No prospective evidence '
                        'exists.',
    'week_1_incumbent': 'for week 1 the previous primary comes from the last '
                        'game of the PRIOR SEASON, so an offseason change of '
                        'starter is the hardest case this layer faces and is '
                        'not separately modelled.',
    'calibration_untested': 'the zero-share calibration table is descriptive. '
                            'No equivalence margin was predeclared and no test '
                            'was run, so it is not called calibrated.',
    'depth_chart_2025_absent': 'the committed depth-chart leaves stop at 2024, '
                               'so the 2025 evaluation fold could not run.',
}

_FIT = {}


def _fit_for(season: int):
    if season in _FIT:
        return _FIT[season]
    import qb3_lib as Q
    frame = Q.build_frame(Q.load_qb_panel(), Q.load_depth())
    par = Q.fit(frame, season)
    if not par['n']:
        return None
    _FIT[season] = (par, frame)
    return _FIT[season]


def cache_clear():
    _FIT.clear()


def captured_depth_chart() -> Outcome:
    """QB rank per team from the newest captured depth chart."""
    fs = sorted(glob.glob(str(_REPO / 'nfl' / 'vintage' / DEPTH_GLOB)))
    if not fs:
        return Outcome.blocked('DEPTH_CHART_NOT_CAPTURED',
                               'no depth-chart capture exists in nfl/vintage',
                               cause=Cause.DATA)
    p = fs[-1]
    rows = list(csv.DictReader(gzip.open(p, 'rt')))
    qb = [r for r in rows if (r.get('pos_abb') or '').upper() == 'QB'
          and r.get('gsis_id')]
    if not qb:
        return Outcome.fail(
            'DEPTH_CHART_NO_QB_ROWS',
            f'{pathlib.Path(p).name} carries {len(rows)} rows and none is a '
            f'quarterback. An empty read is not an empty depth chart.')
    out = collections.defaultdict(dict)
    for r in qb:
        try:
            rank = int(r['pos_rank'])
        except (ValueError, TypeError, KeyError):
            continue
        prev = out[r['team']].get(r['gsis_id'])
        if prev is None or rank < prev:
            out[r['team']][r['gsis_id']] = rank
    dts = sorted({r.get('dt') for r in qb if r.get('dt')})
    return Outcome.ok('DEPTH_CHART_OK', value=dict(out),
                      blob=pathlib.Path(p).name, n_teams=len(out),
                      n_qb_rows=len(qb), retrieved_at=(dts[-1] if dts else None))


def previous_primary(season: int, week: int) -> dict:
    """team -> the gsis_id of the primary passer of its last game, strictly
    earlier by ordinal and spanning seasons."""
    import qb3_lib as Q
    rows = Q.load_qb_panel()
    tg = Q.team_games(rows)
    prim, by_team = {}, collections.defaultdict(list)
    for (t, o), v in tg.items():
        prim[(t, o)] = Q.primary_of(v)
        by_team[t].append(o)
    cut = season * 100 + week
    out = {}
    for t, oo in by_team.items():
        oo.sort()
        i = bisect.bisect_left(oo, cut)
        out[t] = prim.get((t, oo[i - 1])) if i > 0 else None
    return out


def allocate(season, week, teams, qb_players, m=200, seed=20260908,
             kickoff_utc=None, written_at=None, inactive_ids=None) -> Outcome:
    """team -> (pids, shares (n_qb, m)). Shares sum to 1 in every draw.

    OFFICIALLY INACTIVE QUARTERBACKS OWN NOTHING, AND THIS IS WHERE THAT IS
    ENFORCED.

    `official_inactive_ids` used to reach the non-QB engine only
    (run_forecast.py:713). The QB path never saw it, so on the sealed SF@LA
    board Kurtis Rourke held 0.90 dropbacks and Ty Simpson 0.73 while both
    were on the league's inactive list -- about 2.5% of each team's dropbacks
    allocated to quarterbacks who were not dressed, and not redistributed to
    the men who actually played.

    The repair is here rather than downstream because this is the earliest
    causal point: the share is the thing that is wrong. Zeroing the inactive
    rows and renormalising the remainder leaves R2's largest-remainder
    apportionment completely untouched -- it simply receives the correct pool.
    A downstream subtraction would have been a second mechanism papering over
    the first.
    """
    f = _fit_for(season)
    if f is None:
        return Outcome.blocked(
            'QB_ALLOCATION_NOT_FITTED',
            f'no cell could be fitted on seasons before {season}',
            cause=Cause.DATA)
    par, _frame = f
    dc = captured_depth_chart()
    if dc.state is not State.PASS:
        return dc
    got = dc.evidence.get('retrieved_at')
    for label, bound in (('kickoff', kickoff_utc), ('written_at', written_at)):
        if bound and got and str(got) >= str(bound):
            return Outcome.fail(
                'DEPTH_CHART_CHRONOLOGY_FAILURE',
                f'the depth chart was retrieved at {got}, which is not '
                f'strictly before {label} {bound}')
    import qb3_lib as Q
    prev = previous_primary(season, week)
    by_team = collections.defaultdict(list)
    for q in qb_players:
        if q.get('gsis_id'):
            by_team[q.get('team')].append(q['gsis_id'])
    inact = set(inactive_ids or ())
    zeroed = {}
    out, ev = {}, {'teams_without_a_depth_chart': [],
                   'n_qb_by_team': {}, 'unranked_players': 0}
    for t in teams:
        room = dc.value.get(t) or {}
        pids = by_team.get(t, [])
        if not room:
            ev['teams_without_a_depth_chart'].append(t)
        # A ROSTERED QB WITH NO DEPTH RANK IS RANKED LAST, NOT DROPPED. Dropping
        # him would quietly shrink the room; ranking him last says what we know.
        trip = []
        for pid in pids:
            r = room.get(pid)
            if r is None:
                ev['unranked_players'] += 1
                r = 3
            trip.append((pid, min(int(r), 3), int(prev.get(t) == pid)))
        if not trip:
            continue
        S = Q.allocate(par, trip, m=m, seed=seed, ordinal=season * 100 + week,
                       team=t)
        pid_list = [x[0] for x in trip]
        if inact:
            mask = np.array([p in inact for p in pid_list])
            if mask.any():
                if mask.all():
                    return Outcome.fail(
                        'QB_ALLOCATION_ALL_QUARTERBACKS_INACTIVE',
                        f'{t}: every rostered quarterback is on the official '
                        f'inactive list, so there is nobody to receive the '
                        f'team dropback share. Refusing rather than dividing '
                        f'by zero or leaving the share with a player who is '
                        f'not dressed.',
                        team=t, n_qb=len(pid_list))
                S = S.copy()
                S[mask, :] = 0.0
                col = S.sum(0)
                if float(np.min(col)) <= 0.0:
                    return Outcome.fail(
                        'QB_ALLOCATION_ZERO_ACTIVE_SHARE',
                        f'{t}: after removing officially inactive '
                        f'quarterbacks at least one draw has no share left to '
                        f'renormalise. Allocated mass may never be dropped.',
                        team=t)
                S = S / col
                zeroed.setdefault(t, []).extend(
                    [p for p, mk in zip(pid_list, mask) if mk])
        out[t] = {'pids': pid_list, 'shares': S,
                  'ranks': [x[1] for x in trip],
                  'was_prev_primary': [x[2] for x in trip]}
        ev['n_qb_by_team'][t] = len(trip)
    if not out:
        return Outcome.fail(
            'QB_ALLOCATION_EMPTY',
            'no team received a quarterback allocation; an empty allocation '
            'is not an allocation')
    worst = max(float(np.abs(v['shares'].sum(0) - 1.0).max())
                for v in out.values())
    if worst > 1e-6:
        return Outcome.fail(
            'QB_ALLOCATION_DOES_NOT_CLOSE',
            f'the shares of some team do not sum to 1 (worst {worst:.2e}). '
            f'Closure is the property this layer exists for.')
    return Outcome.ok('QB_ALLOCATION_OK', value=out,
                      spec_version=SPEC_VERSION, governance=GOVERNANCE,
                      n_inactive_qb_zeroed=sum(len(v) for v in zeroed.values()),
                      inactive_qb_zeroed=zeroed,
                      n_teams=len(out), closure_max_dev=worst,
                      depth_chart_blob=dc.evidence['blob'],
                      depth_chart_retrieved_at=got,
                      cells_fitted=len(par['n']),
                      trained_on_seasons_before=season,
                      warnings=[f'known limitation: {k}'
                                for k in KNOWN_LIMITATIONS])
