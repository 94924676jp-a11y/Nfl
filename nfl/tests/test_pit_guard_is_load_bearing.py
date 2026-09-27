"""`assert_pit` stops leaked evidence reaching the caller. Proved, not asserted.

WHAT IS PROTECTED

`current_season_evidence` builds the usage rows a forecast learns from.
`assert_pit` re-derives the maximum week present and refuses if any row is at or
after the forecast week -- a game inside its own evidence. Its docstring says it
"deliberately does not trust the filter that produced `rows`", which is the right
instinct: the filter and the check are independent, so a broken filter is caught
rather than believed.

The protected action is that the CALLER RETURNS THE REFUSAL and the usage rows
are never handed downstream. A guard returning FAIL while the function went on to
return rows would put the outcome of a game into the evidence used to predict it,
and the resulting model would look excellent.

WEEK EQUALITY IS THE WHOLE POINT

The comparison is `w >= before_week`, not `>`. Week `before_week` itself is the
game being forecast, so its own week must not appear. A test that only seeds
week+1 would pass against a `>` bug, so the boundary case is tested explicitly
and separately.

AND THE BYPASS HALF

Stubbed to the guard's pass shape, the caller must return rows instead of the
refusal. If it refuses anyway, something other than this guard is doing the work
and the proof would be void.
"""
from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bypass import guard_bypassed                               # noqa: E402
from nfl.production.nonqb import current_season_evidence as CSE  # noqa: E402
from sportsplatform.governance.outcome import Outcome, State    # noqa: E402

PASSED = FAILED = 0
MODULE = 'nfl.production.nonqb.current_season_evidence'
GUARD = 'assert_pit'


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(ok)


def _rows(*weeks):
    """Usage rows in the (week, team, player) shape the guard reads."""
    return [(w, 'PHI', f'00-000{i}') for i, w in enumerate(weeks)]


# =================================================== the guard's own verdicts

def test_clean_evidence_passes():
    o = CSE.assert_pit(_rows(1, 2), before_week=3)
    check('weeks strictly before the forecast week pass', o.state is State.PASS,
          f'{o.state} {o.code}')
    check('and the max week used is reported',
          (o.value or {}).get('max_week_used') == 2, str(o.value))


def test_a_future_week_is_refused():
    o = CSE.assert_pit(_rows(1, 4), before_week=3)
    check('a later week refuses', o.state is not State.PASS, str(o.state))
    check('with CURRENT_SEASON_EVIDENCE_LEAKS_FORWARD',
          o.code == 'CURRENT_SEASON_EVIDENCE_LEAKS_FORWARD', str(o.code))


def test_the_forecast_week_ITSELF_is_refused():
    """The boundary. `>=`, not `>`: week 3 is the game being forecast."""
    o = CSE.assert_pit(_rows(1, 3), before_week=3)
    check('the forecast week itself is a leak', o.state is not State.PASS,
          f'{o.state} {o.code}')
    check('with the leak code',
          o.code == 'CURRENT_SEASON_EVIDENCE_LEAKS_FORWARD', str(o.code))
    # Read through GATE.payload, not `.value`. On a FAILED Outcome the
    # diagnostic lives under `.evidence['value']`, because Outcome.fail has no
    # `value` parameter and the kwarg lands in evidence -- DEF-084. Reading
    # `.value` here returned None and this check failed, which is how that
    # defect surfaced. `payload()` is the project's one accessor for it.
    from nfl.production.review.gate import payload
    check('and the offending week is named',
          3 in (payload(o).get('weeks_present') or []),
          f'.value={o.value} evidence={sorted(o.evidence)}')
    check('the diagnostic is NOT on .value for a failed outcome (DEF-084)',
          o.value is None, repr(o.value))


def test_empty_rows_are_not_a_leak_but_are_not_evidence_either():
    o = CSE.assert_pit([], before_week=3)
    check('no rows is not reported as a leak', o.state is State.PASS,
          f'{o.state} {o.code}')
    check('and max_week_used is None rather than 0',
          (o.value or {}).get('max_week_used') is None, str(o.value))


# ============================== the protected action, via a real caller frame

def _caller(rows, week):
    """The guarded shape of the call site: refuse, or return the rows.

    Mirrors current_season_evidence lines 104-106 exactly -- `pit =
    assert_pit(...)` then `if pit.state.name != 'PASS': return pit`. The guard is
    looked up through the module so `guard_bypassed` reaches it, which is the
    same indirection the real call site has.
    """
    pit = CSE.assert_pit(rows, before_week=week)
    if pit.state.name != 'PASS':
        return pit
    return Outcome.ok('USAGE_ROWS', value=rows)


def test_leaked_rows_never_reach_the_caller():
    o = _caller(_rows(1, 3), 3)
    check('the caller returns a refusal', o.state is not State.PASS, str(o.state))
    check('and NOT the rows', o.code != 'USAGE_ROWS', str(o.code))
    check('so no leaked evidence is handed downstream',
          o.value is None or not isinstance(o.value, list)
          or all(w < 3 for w, _t, _p in (o.value or [])),
          str(o.value)[:120])


def test_clean_rows_do_reach_the_caller():
    """Otherwise the test above could be a broken caller, not a guard."""
    o = _caller(_rows(1, 2), 3)
    check('clean rows are returned', o.code == 'USAGE_ROWS',
          f'{o.state} {o.code}')
    check('and there are two of them', len(o.value) == 2, str(o.value))


def test_bypassing_the_guard_lets_leaked_rows_through():
    with guard_bypassed(MODULE, GUARD,
                        returns=Outcome.ok(
                            'CURRENT_SEASON_EVIDENCE_IS_POINT_IN_TIME',
                            {'weeks_present': [], 'before_week': 3,
                             'max_week_used': None})):
        o = _caller(_rows(1, 3), 3)
    check('bypassed, the caller no longer refuses', o.code == 'USAGE_ROWS',
          f'{o.state} {o.code}')
    check('bypassed, the leaked week IS handed downstream',
          any(w >= 3 for w, _t, _p in o.value), str(o.value))
    check('so the refusal came from the guard and nowhere else', True)


def test_the_bypass_stub_matches_the_guards_pass_shape():
    real = CSE.assert_pit(_rows(1, 2), before_week=3)
    check('the real pass code is what the stub returns',
          real.code == 'CURRENT_SEASON_EVIDENCE_IS_POINT_IN_TIME', str(real.code))
    check('and the real pass state is PASS', real.state is State.PASS,
          str(real.state))


def test_the_bypass_target_exists():
    check(f'{MODULE}.{GUARD} exists', hasattr(CSE, GUARD))


if __name__ == '__main__':
    import traceback
    for _n in sorted(k for k in dict(globals()) if k.startswith('test_')):
        print(f'## {_n}')
        try:
            globals()[_n]()
        except Exception:                                      # noqa: BLE001
            FAILED += 1
            traceback.print_exc()
    print(f'\nPASSED {PASSED} FAILED {FAILED}')
    sys.exit(1 if FAILED else 0)
