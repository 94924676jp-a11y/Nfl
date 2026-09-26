#!/usr/bin/env python3.12
"""A carry with no owner must never reach the model. assert_frame_closes.

The census listed this STOP-effect guard with direct_test_coverage: false, on a
module inside the engineering branch's executed closure. Its docstring states
the stakes better than a summary could:

    "a frame that does not close would put a carry with no owner into the
    residual pool itself, and the per-draw counters downstream would report
    zero violations while the parameters were built on a broken ledger."

That is this audit's central failure mode -- a missing owner becoming invisible
mass -- caught at the data layer before any model runs. It is checked in BOTH
entry points, `build_frame` and the caller-supplied frame handed to `fit_frozen`,
and both are exercised here.

TWO DIRECTIONS OF NON-CLOSURE, and one code would not be enough to tell them
apart in the evidence, which is why `n_bad` and `max_abs` are asserted too:

  team_carries too high  -> a carry exists that no category claims
  a category too high    -> a category claims a carry that was never taken

And an EMPTY frame is a third state, not a passing one: "An empty frame is an
absence, not a season with no rushing."
"""
from __future__ import annotations

import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))

from nfl.production.nonqb import rushing_a1 as RA1
from nfl.tests import bypass as BP
from sportsplatform.governance.outcome import State

passed = failed = 0
MOD = 'nfl.production.nonqb.rushing_a1'
CLOSURE_CODES = ('A1_FRAME_CATEGORIES_DO_NOT_CLOSE', 'A1_FRAME_EMPTY')


def check(label, cond, detail=''):
    global passed, failed
    if cond:
        passed += 1
    else:
        failed += 1
        print(f'  FAIL {label}  {detail}')


def row(team_carries, scramble, **cats):
    r = {'season': 2024, 'week': 1, 'team': 'KC',
         'team_carries': team_carries, 'scramble': scramble}
    for c in RA1.CATEGORIES:
        r[c] = cats.get(c, 0)
    return r


CLOSES = row(10, 2, rb=8)
CARRY_WITH_NO_OWNER = row(11, 2, rb=8)      # 11 - 2 - 8 = +1 unclaimed
CATEGORY_INVENTS_A_CARRY = row(10, 2, rb=9)  # 10 - 2 - 9 = -1 invented


def test_a_closing_frame_is_not_refused():
    """The inverted check. A guard that refuses every frame is not a guard."""
    check('a frame that closes returns None',
          RA1.assert_frame_closes([CLOSES]) is None)


def test_a_carry_with_no_owner_is_refused_and_counted():
    g = RA1.assert_frame_closes([CARRY_WITH_NO_OWNER])
    check('an unclaimed carry refuses', g is not None
          and g.code == 'A1_FRAME_CATEGORIES_DO_NOT_CLOSE',
          getattr(g, 'code', g))
    if g is not None:
        check('  and counts the offending team-games', g.evidence.get('n_bad') == 1,
              g.evidence.get('n_bad'))
        check('  and reports the worst gap, so the size is visible',
              g.evidence.get('max_abs') == 1, g.evidence.get('max_abs'))


def test_a_category_inventing_a_carry_is_refused_too():
    """The other sign. Closure is an equality, not an upper bound -- a category
    claiming a carry nobody took is as wrong as a carry nobody claimed, and an
    abs() in the counter is what makes both visible."""
    g = RA1.assert_frame_closes([CATEGORY_INVENTS_A_CARRY])
    check('an invented carry refuses', g is not None
          and g.code == 'A1_FRAME_CATEGORIES_DO_NOT_CLOSE',
          getattr(g, 'code', g))
    if g is not None:
        check('  and its magnitude is reported as an absolute value',
              g.evidence.get('max_abs') == 1, g.evidence.get('max_abs'))


def test_an_empty_frame_is_an_absence_not_a_season_with_no_rushing():
    for label, frame in (('[]', []), ('None', None), ('{}', {})):
        g = RA1.assert_frame_closes(frame)
        check(f'{label} is BLOCKED[A1_FRAME_EMPTY], not a pass',
              g is not None and g.code == 'A1_FRAME_EMPTY'
              and g.state is not State.PASS, getattr(g, 'code', g))


def test_a_mixed_frame_reports_how_many_not_merely_that_one_failed():
    frame = [CLOSES, CARRY_WITH_NO_OWNER, CLOSES, CATEGORY_INVENTS_A_CARRY]
    g = RA1.assert_frame_closes(frame)
    check('a mixed frame refuses', g is not None)
    if g is not None:
        check('  and names 2 of 4 bad rather than just failing',
              g.evidence.get('n_bad') == 2, g.evidence.get('n_bad'))
        check('  and the detail states the denominator',
              '2 of 4' in (g.detail or ''), (g.detail or '')[:80])


def test_fit_frozen_refuses_a_caller_supplied_frame_that_does_not_close():
    """The second entry point. A guard on build_frame alone would be bypassed by
    any caller that builds its own frame, which is exactly what fit_frozen
    accepts."""
    o = RA1.fit_frozen(2026, 3, frame=[CARRY_WITH_NO_OWNER])
    check('fit_frozen refuses a non-closing caller frame',
          o.code == 'A1_FRAME_CATEGORIES_DO_NOT_CLOSE',
          f'{o.state.value}[{o.code}]')
    o = RA1.fit_frozen(2026, 3, frame=[])
    check('fit_frozen refuses an empty caller frame',
          o.code == 'A1_FRAME_EMPTY', f'{o.state.value}[{o.code}]')


def test_the_refusal_comes_from_the_guard_and_not_from_something_downstream():
    """The half that is usually skipped, per bypass.py's own docstring.

    With the guard stubbed permissive, fit_frozen must NOT still return a
    closure code. If it did, this file would pass with the guard deleted and
    would be testing nothing.
    """
    def run():
        try:
            return RA1.fit_frozen(2026, 3, frame=[CARRY_WITH_NO_OWNER])
        except Exception as exc:                               # noqa: BLE001
            return exc

    with_guard = run()
    check('with the guard: a closure refusal',
          getattr(with_guard, 'code', None) in CLOSURE_CODES,
          getattr(with_guard, 'code', with_guard))
    with BP.guard_bypassed(MOD, 'assert_frame_closes', returns=None):
        without = run()
    got = getattr(without, 'code', None)
    check('with the guard bypassed: NOT a closure refusal, so the refusal was '
          'the guard\'s', got not in CLOSURE_CODES,
          f'still {got} -- this test would pass with the guard deleted')
    if isinstance(without, Exception):
        # NOT DEF-079, and the difference matters. That defect was established
        # because bypassing assert_pairs_are_usable crashed on a path that
        # otherwise returns cleanly. Here the SAME KeyError appears with a
        # CLOSING frame, so it is this test's deliberately minimal fixture
        # lacking `rush_play_budget`, not evidence about what sits behind the
        # guard. The proof stands on the closure code being absent; the
        # exception is noise and is labelled as such rather than promoted into
        # a finding.
        clean = None
        try:
            RA1.fit_frozen(2026, 3, frame=[CLOSES])
        except Exception as exc:                               # noqa: BLE001
            clean = type(exc).__name__
        same = clean == type(without).__name__
        print(f'  note  bypassed -> {type(without).__name__}: '
              f'{str(without)[:60]} -- '
              + ('a thin-fixture artifact, since a CLOSING frame raises the '
                 'same thing. Not a finding.' if same else
                 'and a closing frame does NOT raise this, so it may be worth '
                 'a look.'))


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith('test_') and callable(fn):
            fn()
    print(f'test_a1_frame_closure_guard: {passed} ok, {failed} failed')
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
