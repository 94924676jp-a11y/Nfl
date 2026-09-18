"""The exact solver must return the LAWFUL optimum, not the mathematical one.

THE DEFECT. `optimal_worlds.solve` optimised over (flex slots, captain,
salary) and never knew that DraftKings Showdown requires both clubs.
`candidates.py` recorded `both_teams = len(teams) >= 2` after construction,
which is a note about a lineup, not a constraint on a search. Every
`p_optimal` published from that solver was a frequency over lineups that could
not necessarily be entered.

THE TEST THAT MATTERS is `test_B`: a toy slate built so the unconstrained
optimum is single-team in EVERY world. A post-hoc rejection would return
nothing there. A solver that merely reports legality would return an
unenterable lineup and say so. Only a solver that carries team coverage in its
DP state returns the right answer, and `test_C` proves it is the right answer
by enumerating every legal lineup.
"""
from __future__ import annotations

import itertools
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.dfs.showdown import optimal_worlds as OW                     # noqa: E402
from sportsplatform.governance.outcome import State                   # noqa: E402

PASSED = 0
FAILED = 0
NOT_EXECUTED = []

CAP = 50000
N_FLEX = 3
W = 200


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}: {detail}')


def _slate(seed=7):
    """Four cheap-enough stars on one club; the other club is worthless.

    Built so the unconstrained optimum is single-team every time, which is the
    only configuration that can tell the three solver behaviours apart.
    """
    rng = np.random.default_rng(seed)
    spec = [('a1', 'AAA', 9000, 25.0), ('a2', 'AAA', 8000, 22.0),
            ('a3', 'AAA', 7000, 20.0), ('b1', 'BBB', 6000, 4.0),
            ('b2', 'BBB', 3000, 2.0), ('a4', 'AAA', 5000, 15.0)]
    return [{'name': nm, 'team': tm, 'pos': 'X', 'tag': 'T', 'salary': s,
             'cpt_salary': int(s * 1.5),
             'draws': rng.normal(mu, 1.0, W)} for nm, tm, s, mu in spec]


def _solver_order(players):
    """THE SOLVER SORTS BY NAME. Lineup indices refer to THAT order.

    Indexing the caller's own list instead is how the first verification run
    of this fix reported 200 mismatches that were not mismatches. Array
    identity is never inferred from the order a list happened to arrive in.
    """
    return sorted(players, key=lambda p: p['name'])


def _brute(P, w, require):
    best = None
    for cpt in range(len(P)):
        rest = [i for i in range(len(P)) if i != cpt]
        for flex in itertools.combinations(rest, N_FLEX):
            if P[cpt]['cpt_salary'] + sum(P[i]['salary']
                                          for i in flex) > CAP:
                continue
            if require and len({P[i]['team']
                                for i in (cpt,) + flex}) < 2:
                continue
            sc = (1.5 * P[cpt]['draws'][w]
                  + sum(P[i]['draws'][w] for i in flex))
            if best is None or sc > best[0]:
                best = (sc, cpt, sorted(flex))
    return best


def test_A_the_constraint_is_carried_in_the_evidence():
    players = _slate()
    o = OW.solve(players, cap=CAP, n_flex=N_FLEX, chunk_report=0)
    check('A the lawful solve passes', o.state is State.PASS,
          f'{o.state}[{o.code}]')
    if o.state is not State.PASS:
        NOT_EXECUTED.append('A-D solver assertions')
        return
    check('A it declares that site legality was enforced',
          o.evidence['site_legality_enforced'] is True)
    check('A and names the rule it enforced',
          'both clubs' in o.evidence['site_rule'], o.evidence['site_rule'])


def test_B_the_unconstrained_optimum_is_not_the_answer():
    players = _slate()
    P = _solver_order(players)
    law = OW.solve(players, cap=CAP, n_flex=N_FLEX, chunk_report=0)
    un = OW.solve(players, cap=CAP, n_flex=N_FLEX, chunk_report=0,
                  require_team_coverage=False)
    if law.state is not State.PASS or un.state is not State.PASS:
        NOT_EXECUTED.append('B lawful vs unconstrained')
        return
    illegal = sum(1 for cpt, flex in un.value['lineups']
                  if len({P[i]['team'] for i in [cpt] + list(flex)}) < 2)
    check('B this slate is the hard case: every unconstrained optimum is '
          'single-team', illegal == W, f'{illegal}/{W}')
    bad = [w for w, (cpt, flex) in enumerate(law.value['lineups'])
           if len({P[i]['team'] for i in [cpt] + list(flex)}) < 2]
    check('B the lawful solver returns a legal lineup in every world',
          not bad, f'{len(bad)} illegal')
    differs = sum(1 for a, b in zip(un.value['lineups'], law.value['lineups'])
                  if a != b)
    check('B and it is a DIFFERENT lineup, so the constraint is not cosmetic',
          differs == W, f'{differs}/{W}')


def test_C_the_dp_equals_brute_force_enumeration():
    players = _slate()
    P = _solver_order(players)
    o = OW.solve(players, cap=CAP, n_flex=N_FLEX, chunk_report=0)
    if o.state is not State.PASS:
        NOT_EXECUTED.append('C brute force')
        return
    worst, mismatches = 0.0, 0
    for w in range(W):
        cpt, flex = o.value['lineups'][w]
        got = 1.5 * P[cpt]['draws'][w] + sum(P[i]['draws'][w] for i in flex)
        want = _brute(P, w, True)[0]
        worst = max(worst, abs(got - want))
        mismatches += abs(got - want) > 1e-9
    check('C the DP matches exhaustive enumeration in all 200 worlds',
          mismatches == 0, f'{mismatches} mismatch, worst {worst:.3e}')
    check('C to machine precision', worst < 1e-9, f'{worst:.3e}')


def test_D_a_single_club_slate_is_refused_not_solved():
    players = [p for p in _slate() if p['team'] == 'AAA']
    o = OW.solve(players, cap=CAP, n_flex=2, chunk_report=0)
    check('D a one-club universe is refused, not silently allowed',
          o.state is State.FAIL and o.code == OW.CODE_TEAM_COVERAGE,
          f'{o.state}[{o.code}]')


def test_E_the_mask_is_a_state_not_a_filter():
    """A filter would drop worlds; the DP solves every one of them."""
    players = _slate()
    o = OW.solve(players, cap=CAP, n_flex=N_FLEX, chunk_report=0)
    if o.state is not State.PASS:
        NOT_EXECUTED.append('E feasibility')
        return
    check('E no world is left infeasible', o.evidence['n_infeasible'] == 0,
          str(o.evidence['n_infeasible']))
    check('E every world produced a lineup',
          all(x is not None for x in o.value['lineups']))
    bits, full = OW.team_bits(_solver_order(players))
    check('E two clubs give a two-bit mask with full == 3',
          len(bits) == 2 and full == 3, f'{bits} {full}')


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for fn in (test_A_the_constraint_is_carried_in_the_evidence,
               test_B_the_unconstrained_optimum_is_not_the_answer,
               test_C_the_dp_equals_brute_force_enumeration,
               test_D_a_single_club_slate_is_refused_not_solved,
               test_E_the_mask_is_a_state_not_a_filter):
        fn()
    for n in NOT_EXECUTED:
        print(f'  NOT_EXECUTED {n}')
    print(f'\n{PASSED} passed, {FAILED} failed, {len(NOT_EXECUTED)} NOT_EXECUTED')
    raise SystemExit(1 if FAILED else 0)
