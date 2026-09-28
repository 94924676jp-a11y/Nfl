#!/usr/bin/env python3.12
"""The exact optimiser must be exact, and the warehouse must never turn absence into zero.

Two families of check, and both are about claims that are easy to make and hard to earn.

  EXACTNESS. "PROVEN_OPTIMAL" is a string until something proves it. The optimiser is checked against
  brute-force enumeration on slates small enough to enumerate, on value AND on the reconstructed
  roster -- a correct value with a wrong roster means an illegal lineup gets uploaded.

  ERA SEMANTICS. The warehouse's whole purpose is that NOT_AVAILABLE_FOR_ERA,
  UNKNOWN_PENDING_ACQUISITION and a real measurement never collapse into each other. These checks
  fail if any of them starts reading as zero.
"""
from __future__ import annotations

import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.opt import exact, verify  # noqa: E402
from nfl.warehouse import era  # noqa: E402
from sportsplatform.governance.outcome import State  # noqa: E402

RESULTS = []


def check(name):
    def deco(fn):
        RESULTS.append((name, fn))
        return fn
    return deco


@check('LOAD-BEARING: the optimiser matches brute force on value, roster and legality')
def t_exact():
    o = verify.run(trials=30, seed=3)
    assert o.state is State.PASS, o
    ev = o.value
    assert ev['trials_vs_brute_force'] >= 25, ev
    assert not ev['failures'] and not ev['tight_cap_failures'] and not ev['k_best_failures']
    return (f"{ev['trials_vs_brute_force']} slates matched brute force exactly, "
            f"{ev['tight_cap_trials']} more at a binding cap")


@check('LOAD-BEARING: a wrong DP is caught -- a seeded bad solver fails the brute-force check')
def t_verify_can_fail():
    # If verify() cannot fail, it proves nothing. Replace the position table with one that drops the
    # best item and require the verification to refuse.
    real = exact._position_table

    def crippled(items, kmax, nbuckets):
        return real(items[1:], kmax, nbuckets)
    try:
        exact._position_table = crippled
        o = verify.run(trials=6, seed=5)
        assert o.state is State.FAIL, (
            'brute-force verification passed a solver that ignores the first player at every '
            'position, so it is not actually comparing anything')
    finally:
        exact._position_table = real
    return 'a deliberately crippled DP is refused by the verification'


@check('LOAD-BEARING: required players are honoured, and the requirement is checked not assumed')
def t_required():
    import random
    rng = random.Random(21)
    pool = []
    for pos, n in (('QB', 6), ('RB', 10), ('WR', 14), ('TE', 8), ('DST', 6)):
        for i in range(n):
            pool.append({'id': f'{pos}{i}', 'position': pos,
                         'salary': rng.randrange(30, 90) * 100,
                         'value': round(rng.uniform(2, 26), 3)})
    free = exact.solve(pool)
    assert free.state is State.PASS

    # this argument was ACCEPTED AND IGNORED: solve() passed it to an enumerator that took the
    # parameter and never read it, so a constrained solve returned the unconstrained lineup and
    # still called itself PROVEN_OPTIMAL. Nothing in the suite exercised it.
    worst_qb = min((p for p in pool if p['position'] == 'QB'), key=lambda p: p['value'])
    con = exact.solve(pool, required_players=[worst_qb['id']])
    assert con.state is State.PASS, con
    assert worst_qb['id'] in con.value['ids'], (
        'the required player is absent from the solution, which is the original defect')
    assert con.value['value'] <= free.value['value'] + 1e-9, (
        'a requirement RAISED the optimum, which is impossible: a constraint cannot enlarge the '
        'feasible set')

    # brute force the constrained problem, on value AND on the roster
    best = None
    for shape in exact.SHAPES:
        import itertools
        groups = []
        for pos, k in shape.items():
            cands = [p for p in pool if p['position'] == pos]
            groups.append([c for c in itertools.combinations(cands, k)])
        for combo in itertools.product(*groups):
            flat = [p for g in combo for p in g]
            if worst_qb['id'] not in {p['id'] for p in flat}:
                continue
            if sum(p['salary'] for p in flat) > exact.SALARY_CAP:
                continue
            v = sum(p['value'] for p in flat)
            if best is None or v > best[0]:
                best = (v, sorted(p['id'] for p in flat))
    assert best is not None
    assert abs(best[0] - con.value['value']) < 1e-6, (
        f'brute force found {best[0]:.4f} under the requirement, solver returned '
        f'{con.value["value"]:.4f}')
    assert sorted(con.value['ids']) == best[1], (
        f'value matches but the roster differs: {sorted(con.value["ids"])} vs {best[1]}')

    # an impossible requirement must block, not quietly drop the constraint
    rich = sorted(pool, key=lambda p: -p['salary'])[:7]
    imp = exact.solve(pool, required_players=[r['id'] for r in rich])
    assert imp.state is State.BLOCKED, imp
    absent = exact.solve(pool, required_players=['NOT_A_PLAYER'])
    assert absent.state is State.FAIL and absent.code == 'REQUIRED_PLAYER_NOT_IN_POOL', absent
    clash = exact.solve(pool, required_players=[worst_qb['id']],
                        banned_players=[worst_qb['id']])
    assert clash.state is State.FAIL and clash.code == 'REQUIRED_PLAYER_ALSO_BANNED', clash
    return (f'forcing the weakest quarterback gives {con.value["value"]:.3f} against '
            f'{free.value["value"]:.3f} free, matching brute force on value and roster; '
            f'impossible, absent and contradictory requirements each refuse')


@check('the optimiser refuses a salary off the DK grid rather than rounding it')
def t_grid():
    pool = [{'id': 'x', 'position': 'QB', 'salary': 5050, 'value': 10.0}]
    o = exact.solve(pool)
    assert o.state is State.FAIL and o.code == 'SALARY_NOT_ON_GRID', o
    return 'a 5,050 salary is refused; the DP assumes the 100 grid and says so'


@check('an infeasible pool BLOCKS instead of returning a partial lineup')
def t_infeasible():
    pool = [{'id': f'QB{i}', 'position': 'QB', 'salary': 5000, 'value': 10.0} for i in range(3)]
    o = exact.solve(pool)
    assert o.state is State.BLOCKED, o
    assert o.code == 'NO_FEASIBLE_LINEUP'
    return 'a pool with only quarterbacks blocks rather than emitting an eight-man roster'


@check('structured solve honours a stack minimum and prices it')
def t_structured():
    v1 = _REPO / 'nfl/dfs/salaries/DK_WEEK3_PROJ_V1.json'
    if not v1.exists():
        return 'V1 artifact absent; skipped'
    art = json.loads(v1.read_text())
    pool, team_of, opp_of = [], {}, {}
    post = json.loads((_REPO / 'nfl/dfs/salaries/DK_WEEK3_TODAY_STATE_POST_INACTIVES.json')
                      .read_text())
    for dk, r in art['rows'].items():
        val, sal = r.get('dk_points_if_plays'), r.get('salary')
        if val is None or not sal:
            continue
        pool.append({'id': dk, 'position': r['position'], 'salary': sal, 'value': float(val)})
        team_of[dk] = r['team']
        opp_of[dk] = (post['players'].get(dk) or {}).get('opponent')
    free = exact.solve_structured(pool, team_of=team_of, opp_of=opp_of, qb_stack_min=0)
    two = exact.solve_structured(pool, team_of=team_of, opp_of=opp_of, qb_stack_min=2)
    assert free.state is State.PASS and two.state is State.PASS
    assert two.value['value'] <= free.value['value'] + 1e-9, (
        'requiring a stack produced a HIGHER optimum, which is impossible: a constraint cannot '
        'enlarge the feasible set')
    assert two.value['stack_size'] >= 2, two.value['stack_size']
    return (f"unconstrained {free.value['value']}, stack>=2 {two.value['value']}, "
            f"price {free.value['value'] - two.value['value']:.2f}")


@check('era semantics: a statistic that did not exist reads NOT_AVAILABLE_FOR_ERA, never zero')
def t_era():
    assert era.available('snap_counts', 2008) == era.NOT_AVAILABLE_FOR_ERA
    assert era.available('snap_counts', 2015) == era.AVAILABLE
    assert era.available('routes_run', 2024) == era.UNKNOWN_PENDING_ACQUISITION
    assert era.available('moneyline', 2002) == era.NOT_AVAILABLE_FOR_ERA, (
        'moneyline was corrected to a measured window beginning 2006; 2002 must not read available')
    assert era.available('spread', 2000) == era.AVAILABLE
    # the three states must be distinct strings; collapsing any two is the failure mode
    assert len({era.AVAILABLE, era.NOT_AVAILABLE_FOR_ERA, era.UNKNOWN_PENDING_ACQUISITION}) == 3
    return 'snap counts 2008 absent, 2015 present, routes unknown, moneyline 2002 absent'


@check('the team-game table carries the era sentinel, not zeros, for seasons without play detail')
def t_team_game_sentinel():
    f = _REPO / 'nfl/warehouse/TEAM_GAME.json'
    if not f.exists():
        return 'team-game table absent; skipped'
    art = json.loads(f.read_text())
    early = [r for r in art['rows'].values() if r['season'] == 2005]
    late = [r for r in art['rows'].values() if r['season'] == 2024]
    assert early and late
    sent = {era.NOT_AVAILABLE_FOR_ERA, era.UNKNOWN_PENDING_ACQUISITION}
    assert all(r['plays'] in sent for r in early), (
        'a 2005 club-game carries a numeric play count, which this checkout cannot know. A zero or '
        'an imputed number here would say the 2005 Colts ran no plays.')
    assert all(isinstance(r['plays'], (int, float)) for r in late)
    # and the market IS present for the early season
    assert all(r['total_line'] is not None for r in early[:50])
    return (f'2005 play detail is {early[0]["plays"]}; 2024 is numeric; the 2005 market is present')


@check('the spread sign is verified from outcomes, and the build would refuse an ambiguous one')
def t_spread_sign():
    f = _REPO / 'nfl/warehouse/TEAM_GAME.json'
    if not f.exists():
        return 'team-game table absent; skipped'
    art = json.loads(f.read_text())
    sv = art['spread_sign_verification']
    assert sv['state'] == 'VERIFIED', sv
    assert sv['convention'] == 'SPREAD_LINE_IS_HOME_MARGIN', sv
    assert abs(sv['correlation_with_home_margin']) > 0.3, sv
    assert sv['n_games'] > 5000, sv
    return (f"{sv['convention']} at r={sv['correlation_with_home_margin']} over "
            f"{sv['n_games']} games")


@check('the source registry selects on measured coverage, and records what it rejected')
def t_registry():
    from nfl.warehouse import sources
    o = sources.select(sources.registry()['schedules'])
    assert o.state is State.PASS, o
    v = o.value
    assert v['n_seasons'] >= 25, v['n_seasons']
    assert v['completeness_min'] > 0.9, v['completeness_min']
    assert v['n_rejected'] > 100, (
        f"only {v['n_rejected']} candidates rejected; the registry is meant to MEASURE every "
        f"candidate rather than take the first match")
    assert 'NOT on filename' in v['SELECTED_ON']
    return (f"{v['n_candidates_measured']} measured, {v['n_rejected']} rejected, winner has "
            f"{v['n_seasons']} seasons at completeness {v['completeness_min']}")


def main() -> int:
    ok = fail = 0
    for name, fn in RESULTS:
        try:
            detail = fn()
        except AssertionError as e:
            print(f'FAIL  {name}\n        {e}')
            fail += 1
        except Exception as e:  # noqa: BLE001
            print(f'ERROR {name}\n        {type(e).__name__}: {e}')
            fail += 1
        else:
            print(f'pass  {name}\n        {detail}')
            ok += 1
    print(f'\n{ok} passed, {fail} failed, {len(RESULTS)} checks')
    return 1 if fail else 0


if __name__ == '__main__':
    raise SystemExit(main())
