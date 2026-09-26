#!/usr/bin/env python3.12
"""Three guards on an executing path that had no test at all.

The 91-guard census listed `assert_coupling_is_declared` (STOP),
`assert_coupling_has_joint_index` (ANNOTATE) and `assert_pairs_are_usable`
(ANNOTATE) with `direct_test_coverage: false`. All three sit in
nfl/production/team_volume_v1.py, whose `forecast()` is inside the engineering
branch's executed closure -- the closure the scheduled board refresh reaches. So
they are the worst remaining combination in the census: reachable, consequential,
untested.

`team_volume_v1.py` says of them, in its own words: "Each of these is a
module-level function returning an Outcome or None, so nfl/tests/bypass.py can
replace it with a permissive stub and prove the refusal came from the guard
rather than from something downstream." That mechanism existed and nothing used
it on these three.

EVERY CHECK HERE USES IT, because the alternative proves nothing. The standard in
bypass.py's own docstring: `assert_batch_games_are_new` read a field no row
carried, so it passed on every input it was ever given and had never once refused
anything -- and every test of it passed. A test that would still pass with the
guard deleted is testing nothing.

WHAT THESE GUARDS PROTECT. A coupling name is a claim about the joint
distribution the run sampled. A typo that silently fell back to `none` would be
reported as a run that had coupling on, and the board would carry a shared-world
claim it never computed. Each refusal below says exactly that in its own detail
text.
"""
from __future__ import annotations

import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))

from nfl.production import team_volume_v1 as TV
from nfl.tests import bypass as BP
from sportsplatform.governance.outcome import State

passed = failed = 0
MOD = 'nfl.production.team_volume_v1'
TEAMS = ['KC', 'MIA']


def check(label, cond, detail=''):
    global passed, failed
    if cond:
        passed += 1
    else:
        failed += 1
        print(f'  FAIL {label}  {detail}')


def run_forecast(**kw):
    """The real entry point, with small m so this stays fast and deterministic."""
    base = dict(season=2026, week=3, teams=TEAMS, m=4, seed=1)
    base.update(kw)
    return lambda: TV.forecast(**base)


def caught(code):
    return lambda o: getattr(o, 'code', None) == code


def load_bearing(label, attr, code, **kw):
    """Seeded violation gives a NAMED refusal with the guard, and not without.

    A TRACEBACK IS NOT A NAMED REFUSAL, and behind two of these guards there is
    nothing but a traceback. Bypassing `assert_pairs_are_usable` with
    `game_pairs=None` does not produce a different Outcome -- it reaches
    team_volume_v1.py:577 `for _pair in game_pairs:` and raises TypeError:
    'NoneType' object is not iterable.

    That is the strongest possible evidence the guard is load-bearing: remove it
    and the module cannot even complete. It is also DEF-079: the guard is the
    ONLY thing between a None and a crash, with no second named refusal behind
    it, and this repository's own rule is that every stage owes a named outcome
    because "a traceback is the one thing it may not return".

    So a raise is recorded as NOT CAUGHT, which is what it is: the violation was
    not caught, it exploded. bypass.assert_guard_is_load_bearing cannot express
    that -- it propagates -- so the two halves are run directly here and the
    crash is reported as evidence rather than swallowed.
    """
    global passed, failed
    run = run_forecast(**kw)
    try:
        with_guard = run()
    except Exception as exc:                                   # noqa: BLE001
        failed += 1
        print(f'  FAIL {label}  the guard itself did not hold: '
              f'{type(exc).__name__}: {exc}')
        return
    if getattr(with_guard, 'code', None) != code:
        failed += 1
        print(f'  FAIL {label}  expected {code}, got '
              f'{getattr(with_guard, "code", with_guard)!r}')
        return
    crashed = None
    try:
        with BP.guard_bypassed(MOD, attr, returns=None):
            without_guard = run()
    except Exception as exc:                                   # noqa: BLE001
        crashed = f'{type(exc).__name__}: {exc}'
        without_guard = None
    if crashed is None and getattr(without_guard, 'code', None) == code:
        failed += 1
        print(f'  FAIL {label}  the refusal survived the guard being bypassed, '
              f'so this proves nothing about the guard')
        return
    passed += 1
    if crashed:
        print(f'  note  {label}: bypassed -> {crashed} '
              f'(DEF-079: no named refusal behind this guard)')


def test_a_declared_coupling_name_is_required_and_the_guard_is_load_bearing():
    # A typo must not fall through to `none`. The guard's own words: "a typo
    # that silently disables the coupling would be reported as a run that had
    # it on."
    o = TV.forecast(2026, 3, TEAMS, m=4, seed=1, game_coupling='zmeen',
                    joint_residuals=True, game_pairs=[('KC', 'MIA')])
    check('an undeclared coupling name refuses',
          o.state is not State.PASS and o.code == 'GAME_COUPLING_UNKNOWN',
          f'{o.state.value}[{o.code}]')
    check('  and the refusal lists the declared names',
          all(n in (o.detail or '') for n in TV.GAME_COUPLINGS), o.detail[:90])
    load_bearing('assert_coupling_is_declared is load-bearing',
                 'assert_coupling_is_declared', 'GAME_COUPLING_UNKNOWN',
                 game_coupling='zmeen', joint_residuals=True,
                 game_pairs=[('KC', 'MIA')])


def test_coupling_without_a_joint_index_is_a_contradiction_not_a_no_op():
    o = TV.forecast(2026, 3, TEAMS, m=4, seed=1, game_coupling='zmean',
                    joint_residuals=False, game_pairs=[('KC', 'MIA')])
    check('coupling with no joint index refuses',
          o.code == 'GAME_COUPLING_WITHOUT_JOINT_INDEX',
          f'{o.state.value}[{o.code}]')
    load_bearing('assert_coupling_has_joint_index is load-bearing',
                 'assert_coupling_has_joint_index',
                 'GAME_COUPLING_WITHOUT_JOINT_INDEX',
                 game_coupling='zmean', joint_residuals=False,
                 game_pairs=[('KC', 'MIA')])


def test_every_unusable_pair_shape_refuses_by_its_own_name():
    # Four distinct violations, four distinct codes. One code for all of them
    # would tell a reader that something was wrong with the pairs and not what.
    for label, pairs, code in (
            ('no pairs at all', None, 'GAME_COUPLING_WITHOUT_PAIRS'),
            ('a one-element pair', [('KC',)], 'GAME_PAIR_MALFORMED'),
            ('a team paired with itself', [('KC', 'KC')], 'GAME_PAIR_SELF'),
            ('a team not on the slate', [('KC', 'XXX')],
             'GAME_PAIR_TEAM_NOT_ON_SLATE')):
        o = TV.forecast(2026, 3, TEAMS, m=4, seed=1, game_coupling='zmean',
                        joint_residuals=True, game_pairs=pairs)
        check(f'{label} -> {code}', o.code == code,
              f'{o.state.value}[{o.code}]')


def test_assert_pairs_are_usable_is_load_bearing():
    load_bearing('assert_pairs_are_usable is load-bearing (no pairs)',
                 'assert_pairs_are_usable', 'GAME_COUPLING_WITHOUT_PAIRS',
                 game_coupling='zmean', joint_residuals=True, game_pairs=None)
    load_bearing('assert_pairs_are_usable is load-bearing (self pair)',
                 'assert_pairs_are_usable', 'GAME_PAIR_SELF',
                 game_coupling='zmean', joint_residuals=True,
                 game_pairs=[('KC', 'KC')])


def test_the_uncoupled_path_is_not_refused_by_these_guards():
    """The inverted check. A guard that refuses everything is not a guard.

    `none` is a legitimate declared coupling and must reach the model, so if the
    call below refuses for a COUPLING reason these guards are over-strict rather
    than load-bearing.
    """
    o = TV.forecast(2026, 3, TEAMS, m=4, seed=1, game_coupling='none',
                    joint_residuals=False, game_pairs=None)
    coupling_codes = {'GAME_COUPLING_UNKNOWN',
                      'GAME_COUPLING_WITHOUT_JOINT_INDEX',
                      'GAME_COUPLING_WITHOUT_PAIRS', 'GAME_PAIR_MALFORMED',
                      'GAME_PAIR_SELF', 'GAME_PAIR_TEAM_NOT_ON_SLATE'}
    check('the uncoupled path is not refused for a coupling reason',
          o.code not in coupling_codes, f'{o.state.value}[{o.code}]')


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith('test_') and callable(fn):
            fn()
    print(f'test_team_volume_coupling_guards: {passed} ok, {failed} failed')
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
