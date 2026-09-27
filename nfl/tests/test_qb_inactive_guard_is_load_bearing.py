"""`assert_inactive_qbs_own_nothing` refuses the run. Proved, and scoped honestly.

WHAT IS PROTECTED

An officially inactive quarterback owning dropbacks or attempts is allocated
mass taken from the men who are dressed. The guard reads the realised per-draw
output and requires the MAXIMUM over all draws to be zero -- not the mean,
because a mean of 0.0004 over a thousand draws is one draw in which a
quarterback who was not dressed took a snap.

Both call sites in `run_forecast.py` (lines ~969 and ~2198) are STOP-shaped:
FAIL -> `RF.refuse('INCOMPLETE_PLAYER_ACCOUNTING', ...)` -> immediate return, so
the QB layer yields nothing and the run refuses. This file proves that shape.

THE THREE STATES ARE THE POINT, AND ONE OF THEM IS TODAY'S

  no list supplied  -> DEFERRED, `QB_INACTIVE_OWNERSHIP_NOT_ESTABLISHED`. The
                       guard refuses to record a pass on a check that never
                       ran. Carried as hard_owed; it does not block the seal,
                       because an ordinary game with no published list should
                       still seal while saying plainly that this was not
                       established.
  list, clean       -> PASS
  list, violated    -> FAIL, and the caller refuses

**AND THIS IS WHERE REACHABILITY IS NOT OBSERVATION.** In production today no
official inactive list is threaded through, so this guard returns DEFERRED on
every real run. Its STOP branch is load-bearing by construction and by the
proof below, and it has never been taken in a live forecast. That is a statement
about what has been observed, not a defect in the guard: the missing piece is
the inactives feed, requested as OUT-033. A test proving the FAIL branch works
does not license saying this guard has fired in production, and the census entry
should not be read that way.
"""
from __future__ import annotations

import os
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bypass import guard_bypassed                               # noqa: E402
from nfl.production import qb_accounting as QBACC               # noqa: E402
from sportsplatform.governance.outcome import Outcome, State    # noqa: E402

PASSED = FAILED = 0
MODULE = 'nfl.production.qb_accounting'
GUARD = 'assert_inactive_qbs_own_nothing'
OUT, IN_ = '00-0000001', '00-0000002'


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(ok)


def _rows():
    """Row 0 is the inactive quarterback, row 1 is dressed."""
    return [{'gsis_id': OUT}, {'gsis_id': IN_}]


def _draws(out_db=0.0, out_att=0.0, n=8):
    db = np.zeros((2, n), float)
    att = np.zeros((2, n), float)
    db[0, 0] = out_db          # one draw only -- the max is what is checked
    att[0, 0] = out_att
    db[1, :] = 30.0
    att[1, :] = 28.0
    return {'db': db, 'att': att}


# ================================================== the three states, apart

def test_no_list_is_DEFERRED_not_PASS():
    o = QBACC.assert_inactive_qbs_own_nothing(_draws(), _rows(), None)
    check('no inactive list does not pass', o.state is not State.PASS, str(o.state))
    check('it is DEFERRED', o.state is State.DEFERRED, str(o.state))
    check('with QB_INACTIVE_OWNERSHIP_NOT_ESTABLISHED',
          o.code == 'QB_INACTIVE_OWNERSHIP_NOT_ESTABLISHED', str(o.code))
    check('and it says what it is owed',
          bool((o.evidence or {}).get('owed')), str(o.evidence))


def test_an_empty_list_is_also_DEFERRED():
    """An empty list is the absence of the question, not an answer to it."""
    for empty in ([], (), set()):
        o = QBACC.assert_inactive_qbs_own_nothing(_draws(), _rows(), empty)
        check(f'{type(empty).__name__} is DEFERRED, not PASS',
              o.code == 'QB_INACTIVE_OWNERSHIP_NOT_ESTABLISHED', str(o.code))


def test_a_clean_list_passes():
    o = QBACC.assert_inactive_qbs_own_nothing(_draws(), _rows(), [OUT])
    check('an inactive QB owning zero passes', o.state is State.PASS,
          f'{o.state} {o.code}')
    check('with QB_INACTIVE_OWNS_NOTHING', o.code == 'QB_INACTIVE_OWNS_NOTHING',
          str(o.code))
    check('and one row was actually checked',
          (o.value or {}).get('n_checked') == 1, str(o.value))


def test_a_violation_fails():
    o = QBACC.assert_inactive_qbs_own_nothing(_draws(out_db=1.0), _rows(), [OUT])
    check('an inactive QB owning a dropback fails', o.state is State.FAIL,
          f'{o.state} {o.code}')
    check('with QB_INACTIVE_STILL_OWNS_DROPBACKS',
          o.code == 'QB_INACTIVE_STILL_OWNS_DROPBACKS', str(o.code))
    check('and the offender is named',
          OUT in ((o.evidence or {}).get('offenders') or {}),
          str((o.evidence or {}).get('offenders')))


def test_ONE_draw_out_of_many_is_enough():
    """The max, not the mean. This is the check that catches the real bug."""
    d = _draws(out_db=1.0, n=1000)
    mean = float(np.mean(d['db'][0]))
    o = QBACC.assert_inactive_qbs_own_nothing(d, _rows(), [OUT])
    check(f'a mean of {mean:.6f} over 1000 draws still fails',
          o.state is State.FAIL, f'{o.state} {o.code}')
    check('because one draw held a dropback', mean < 0.002, str(mean))


def test_an_attempt_alone_is_enough():
    o = QBACC.assert_inactive_qbs_own_nothing(
        _draws(out_att=1.0), _rows(), [OUT])
    check('attempts are checked as well as dropbacks', o.state is State.FAIL,
          f'{o.state} {o.code}')


def test_a_dressed_quarterback_owning_everything_is_fine():
    """Otherwise the guard would be refusing ordinary football."""
    o = QBACC.assert_inactive_qbs_own_nothing(_draws(), _rows(), [OUT])
    check('the dressed QB keeps his volume', o.state is State.PASS,
          f'{o.state} {o.code}')


# ================================ the protected action, at the caller shape

def _caller(draws, rows, inactive_ids):
    """The guarded shape of run_forecast.py:969-975.

    FAIL -> refuse and return; anything else -> return the QB draws. Looked up
    through the module so `guard_bypassed` reaches it, as the real site does.
    """
    o = QBACC.assert_inactive_qbs_own_nothing(draws, rows, inactive_ids)
    if o.state is State.FAIL:
        return Outcome.fail('INCOMPLETE_PLAYER_ACCOUNTING',
                            f'{o.code}: {o.detail}')
    return Outcome.ok('QB_LAYER_OK', value=draws)


def test_a_violating_run_produces_no_qb_layer():
    o = _caller(_draws(out_db=1.0), _rows(), [OUT])
    check('the run refuses', o.state is State.FAIL, str(o.state))
    check('with INCOMPLETE_PLAYER_ACCOUNTING',
          o.code == 'INCOMPLETE_PLAYER_ACCOUNTING', str(o.code))
    check('AND no QB draws are returned', o.value is None, str(type(o.value)))


def test_a_clean_run_does_produce_a_qb_layer():
    o = _caller(_draws(), _rows(), [OUT])
    check('a clean run returns the layer', o.code == 'QB_LAYER_OK',
          f'{o.state} {o.code}')
    check('and the draws are present', o.value is not None, 'None')


def test_a_DEFERRED_guard_does_not_block_the_layer():
    """DEFERRED is not FAIL. An ordinary game with no list still proceeds."""
    o = _caller(_draws(), _rows(), None)
    check('no list does not refuse the run', o.code == 'QB_LAYER_OK',
          f'{o.state} {o.code}')
    check('which is why the DEFERRED state has to be carried as owed '
          'rather than silently passing', True)


# ========================================================= THE BYPASS HALF

def test_bypassing_the_guard_lets_the_violating_run_through():
    with guard_bypassed(MODULE, GUARD,
                        returns=Outcome.ok('QB_INACTIVE_OWNS_NOTHING',
                                           value={'n_checked': 0})):
        o = _caller(_draws(out_db=1.0), _rows(), [OUT])
    check('bypassed, the run no longer refuses', o.code == 'QB_LAYER_OK',
          f'{o.state} {o.code}')
    check('bypassed, the inactive QB keeps his dropback',
          o.value is not None and float(np.max(o.value['db'][0])) > 0.0,
          'the draws were not returned')
    check('so the refusal came from the guard and nowhere else', True)


def test_the_bypass_stub_matches_the_guards_pass_shape():
    real = QBACC.assert_inactive_qbs_own_nothing(_draws(), _rows(), [OUT])
    check('the real pass code is what the stub returns',
          real.code == 'QB_INACTIVE_OWNS_NOTHING', str(real.code))
    check('and the real pass state is PASS', real.state is State.PASS,
          str(real.state))


def test_the_bypass_target_exists():
    check(f'{MODULE}.{GUARD} exists', hasattr(QBACC, GUARD))


# ============================ what this file does NOT establish, pinned

def test_this_proof_does_not_claim_the_guard_has_fired_in_production():
    """Reachability is not observation, and the census must not blur them.

    With no inactives feed threaded through, the live path reaches this guard
    and gets DEFERRED. The STOP branch is proved above against seeded input and
    has not been taken in a real forecast. Pinning that here so the distinction
    survives the next person reading the census row.
    """
    o = QBACC.assert_inactive_qbs_own_nothing(_draws(), _rows(), None)
    check('with no feed, the production-shaped call is DEFERRED',
          o.state is State.DEFERRED, str(o.state))
    check('so a LOAD_BEARING classification here means PROVABLE, not OBSERVED',
          True)
    print('       the missing piece is the inactives feed -- see OUT-033')


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
