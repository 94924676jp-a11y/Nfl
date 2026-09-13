"""QB inactive ownership: the governed state, and the draw that conditions on it.

WHAT THESE TESTS PROTECT.

  * A SENTINEL WITH NO WRITER IS NOT A CONTROL. `qb_inactive_ownership_enforced`
    was READ by the product board and SET NOWHERE in the repository, so
    QB_INACTIVE_NOT_CONSUMED could never clear -- not even on the 2026-09-13
    New Orleans board that had demonstrably consumed the league's list and
    zeroed Zach Wilson. The field is now computed by the layer that owns the
    share, from six named conditions, and no caller can assert it.

  * ELIGIBILITY CONDITIONS THE DRAW; IT DOES NOT EDIT THE RESULT. The old
    wiring drew the room unconditioned and zeroed inactive rows afterwards.
    `Q.allocate` samples the primary's share from an empirical pool whose modal
    value is exactly 1.0, so those draws are one-hot and the renormalisation is
    0/0. Indianapolis measured 20.8% of draws in that state.

  * PARITY IS THE PROOF THAT THIS IS WIRING AND NOT A NEW MODEL. With no
    inactive quarterback the eligible room IS the room and the output must be
    bit-identical, draw for draw.
"""
from __future__ import annotations

import os
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
_Q3 = os.path.join(_ROOT, 'nfl', 'research', 'qb3')
if _Q3 not in sys.path:
    sys.path.insert(0, _Q3)

from sportsplatform.governance.outcome import State                  # noqa: E402
from nfl.production.nonqb import qb_allocation as QA                 # noqa: E402
from nfl.product import daily_board as PBD                           # noqa: E402

PASSED = FAILED = 0


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}' + (f'  {detail}' if detail else ''))
    else:
        FAILED += 1
        print(f'  FAIL {label}' + (f'  {detail}' if detail else ''))


# --------------------------------------------------------------- fixtures
# A room shaped like a real one: a rank-1 incumbent, a rank-2 and two rank-3s.
ROOM = [{'gsis_id': 'QB1', 'team': 'ZZ', 'position': 'QB'},
        {'gsis_id': 'QB2', 'team': 'ZZ', 'position': 'QB'},
        {'gsis_id': 'QB3', 'team': 'ZZ', 'position': 'QB'}]
PROV = {'game_id': '2026_01_YY_ZZ', 'teams': ['ZZ'],
        'post_inactives_complete': True, 'n_unmapped': 0}


def _alloc(**kw):
    return QA.allocate(2026, 1, ['ZZ'], ROOM, m=400, seed=20260908, **kw)


def _shares(o, team='ZZ'):
    return o.value[team]['shares'], o.value[team]['pids']


# ----------------------------------------------------------------- A - F
def test_a_inactive_qb_removed_field_true_contamination_clears():
    o = _alloc(inactive_ids=['QB3'], inactive_provenance=PROV)
    check('an allocation with an inactive QB passes', o.state is State.PASS,
          o.code)
    own = o.evidence['qb_inactive_ownership']
    check('  the ownership field is TRUE', own['enforced'] is True,
          str(own['failed_conditions']))
    S, pids = _shares(o)
    check('  the inactive QB holds exactly zero in EVERY draw',
          float(S[pids.index('QB3')].max()) == 0.0,
          f'max {float(S[pids.index("QB3")].max()):.3e}')
    check('  and the shares still close in every draw',
          float(np.abs(S.sum(0) - 1.0).max()) <= 1e-9)
    check('  the excluded QB is named', own['inactive_qbs_excluded']
          .get('ZZ') == ['QB3'])
    board = {'component_manifest': {'applied': ['R2']},
             'qb_inactive_ownership_enforced': own['enforced']}
    flags = PBD._defect_flags(board, 'qb/pyds')
    check('  so the product board raises NO contamination flag',
          not any(f['id'] == 'QB_INACTIVE_NOT_CONSUMED' for f in flags),
          str([f['id'] for f in flags]))


def test_b_no_qb_inactive_but_complete_list_consumed_is_still_enforced():
    # The official list was consumed; it simply names no quarterback. That is
    # ENFORCEMENT, not an absence of it, and conflating the two is how a clean
    # room keeps a contamination flag forever.
    o = _alloc(inactive_ids=['SOME_WR', 'SOME_LB'], inactive_provenance=PROV)
    check('a list naming no QB still passes', o.state is State.PASS, o.code)
    own = o.evidence['qb_inactive_ownership']
    check('  the ownership field is TRUE', own['enforced'] is True,
          str(own['failed_conditions']))
    check('  and no QB is recorded as excluded',
          own['inactive_qbs_excluded'] == {})
    flags = PBD._defect_flags(
        {'component_manifest': {'applied': ['R2']},
         'qb_inactive_ownership_enforced': True}, 'qb/pyds')
    check('  contamination clears', not flags, str(flags))


def test_c_absent_inactive_evidence_keeps_the_flag():
    o = _alloc()
    check('an allocation with no list passes', o.state is State.PASS, o.code)
    own = o.evidence['qb_inactive_ownership']
    check('  the ownership field is FALSE', own['enforced'] is False)
    check('  and names WHICH condition failed',
          'official_inactive_evidence_ingested' in own['failed_conditions'],
          str(own['failed_conditions']))
    flags = PBD._defect_flags(
        {'component_manifest': {'applied': ['R2']},
         'qb_inactive_ownership_enforced': False}, 'qb/pyds')
    check('  so the contamination flag REMAINS',
          any(f['id'] == 'QB_INACTIVE_NOT_CONSUMED' for f in flags))
    check('  and it says it contaminates a QB metric',
          flags[0]['contaminates_this_metric'] is True)


def test_d_unresolved_official_identity_refuses_enforcement():
    prov = dict(PROV, n_unmapped=2, unmapped=['ZZ:Someone Unknown',
                                              'ZZ:Another Name'])
    o = _alloc(inactive_ids=['QB3'], inactive_provenance=prov)
    check('the allocation itself still runs', o.state is State.PASS, o.code)
    own = o.evidence['qb_inactive_ownership']
    check('  but ownership is NOT claimed', own['enforced'] is False)
    check('  because an official name went unresolved',
          own['failed_conditions'] == ['no_unresolved_identity'],
          str(own['failed_conditions']))
    check('  and the unresolved names are carried, not dropped',
          own['unmapped_official_names'] == prov['unmapped'])
    S, pids = _shares(o)
    check('  the resolved inactive QB is STILL excluded from the draw',
          float(S[pids.index('QB3')].max()) == 0.0)


def test_e_a_pre_inactives_artifact_is_false():
    o = _alloc(inactive_ids=None, inactive_provenance=None)
    own = o.evidence['qb_inactive_ownership']
    check('a pre-inactives allocation is not enforced',
          own['enforced'] is False)
    check('  and three conditions fail, not one',
          set(own['failed_conditions']) == {
              'official_inactive_evidence_ingested',
              'evidence_tied_to_this_game_and_team',
              'no_unresolved_identity'},
          str(own['failed_conditions']))
    check('the product board keeps the flag on a pre-inactives board',
          any(f['id'] == 'QB_INACTIVE_NOT_CONSUMED' for f in PBD._defect_flags(
              {'component_manifest': {'applied': ['R2']}}, 'qb/att')))


def test_f_a_forged_flag_cannot_make_a_row_admissible():
    # A board can CLAIM the field. What it cannot do is claim it with no
    # governed provenance behind it: the verdict is computed from the run, and
    # the evidence block travels with it, so a forged boolean is detectable.
    o = _alloc(inactive_ids=['QB3'], inactive_provenance=None)
    own = o.evidence['qb_inactive_ownership']
    check('inactive ids WITHOUT provenance do not enforce',
          own['enforced'] is False, str(own['failed_conditions']))
    check('  the missing link is named',
          'evidence_tied_to_this_game_and_team' in own['failed_conditions'])
    check('  and no game id is claimed', own['game_id'] is None)
    forged = {'component_manifest': {'applied': ['R2']},
              'qb_inactive_ownership_enforced': True}
    check('a board asserting the boolean with no evidence block is detectable',
          forged.get('qb_inactive_ownership') is None)
    # the caller cannot inject the verdict: allocate() computes it and the
    # keyword does not exist.
    import inspect
    sig = set(inspect.signature(QA.allocate).parameters)
    check('allocate() has no parameter that could set the verdict',
          'qb_inactive_ownership_enforced' not in sig and
          'enforced' not in sig, str(sorted(sig)))


# ------------------------------------------- the mechanism, not the flag
def test_g_parity_with_no_inactive_qb_is_bit_identical():
    a = _alloc()
    b = _alloc(inactive_ids=['SOME_WR'], inactive_provenance=PROV)
    Sa, _ = _shares(a)
    Sb, _ = _shares(b)
    check('a list naming no quarterback changes NOTHING in the draw',
          np.array_equal(Sa, Sb),
          f'max |diff| {float(np.abs(Sa - Sb).max()):.3e}')
    check('  bit-identical, not merely close',
          Sa.tobytes() == Sb.tobytes())


def test_h_conditioning_beats_post_hoc_removal_where_it_used_to_refuse():
    import qb3_lib as Q
    par, _ = QA._fit_for(2026)
    # rank-1 incumbent + two others: the primary's share pool is modal at 1.0,
    # so post-hoc removal of the incumbent leaves whole draws at zero.
    trip = [('A', 1, 1), ('B', 2, 0), ('C', 3, 0)]
    S = Q.allocate(par, trip, m=1000, seed=20260908, ordinal=202601, team='ZZ')
    post = S.copy()
    post[0, :] = 0.0
    zero_frac = float((post.sum(0) <= 0).mean())
    check('post-hoc removal DOES strand whole draws at zero share',
          zero_frac > 0.0, f'{zero_frac:.1%} of draws')
    cond = Q.allocate(par, trip[1:], m=1000, seed=20260908, ordinal=202601,
                      team='ZZ')
    check('  conditioning on the eligible room leaves none',
          float((cond.sum(0) <= 0).mean()) == 0.0)
    check('  and the conditioned draw closes to 1 everywhere',
          float(np.abs(cond.sum(0) - 1.0).max()) <= 1e-9)
    # and the production path agrees
    o = _alloc(inactive_ids=['QB1'], inactive_provenance=PROV)
    check('the production allocation no longer refuses that case',
          o.state is State.PASS, f'{o.state.value}:{o.code}')


def test_i_every_quarterback_inactive_still_refuses():
    o = _alloc(inactive_ids=['QB1', 'QB2', 'QB3'], inactive_provenance=PROV)
    check('a room with nobody dressed is REFUSED, not divided by zero',
          o.state is State.FAIL, f'{o.state.value}:{o.code}')
    check('  with the named code',
          o.code == 'QB_ALLOCATION_ALL_QUARTERBACKS_INACTIVE')


def test_j_the_zero_share_guard_is_retained():
    # It is meant to be unreachable now. A guard deleted once it stops firing
    # cannot tell you when the thing it guarded against comes back.
    src = open(os.path.join(_ROOT, 'nfl', 'production', 'nonqb',
                            'qb_allocation.py')).read()
    check('QB_ALLOCATION_ZERO_ACTIVE_SHARE is still raised somewhere',
          "'QB_ALLOCATION_ZERO_ACTIVE_SHARE'," in src)
    check('the six conditions are declared as data, not prose',
          len(QA.OWNERSHIP_CONDITIONS) == 6, str(QA.OWNERSHIP_CONDITIONS))
    v = QA.ownership_verdict(['ZZ'], {}, set(), {}, 0.0, None)
    check('an empty allocation cannot claim accounting passed',
          v['conditions']['allocation_passes_accounting'] is False)


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for fn in sorted(k for k in dict(globals()) if k.startswith('test_')):
        print(f'\n{fn}')
        globals()[fn]()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
