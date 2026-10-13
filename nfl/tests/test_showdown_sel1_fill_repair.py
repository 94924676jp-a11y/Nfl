#!/usr/bin/env python3.12
"""SEL-1 fill repair (PREREG_SEL1_FILL_REPAIR.md): a greedy shortfall at a rung is repaired by single exchanges before the
ladder relaxes. Every repaired portfolio is lawful (size, caps, overlap, exclusions) and never relaxes further than greedy;
the default selector is unchanged; an unknown selector refuses."""
from __future__ import annotations

import collections
import os
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import showdown_portfolio as SP  # noqa: E402


PASSED = FAILED = 0


def check(ok, label=''):
    """Counted check (nfl/tests/run_suite.py reads PASSED/FAILED around every test function)."""
    global PASSED, FAILED
    if ok:
        PASSED += 1
    else:
        FAILED += 1
        print(f'  FAIL {label}')
    return bool(ok)

def _fixture(seed, n_c=300, n_w=400, n_p=14):
    rng = np.random.default_rng(seed)
    seats_of = [list(rng.choice(n_p, 6, replace=False)) for _ in range(n_c)]
    q = rng.uniform(0.02, 0.25, n_c)
    hit = rng.random((n_c, n_w)) < q[:, None]
    rows = [{'first_place_proxy': float(hit[i].mean()), 'structural_duplication_index': 0.0} for i in range(n_c)]
    return hit, rows, seats_of, n_w


def _lawful(P, seats_of, n, exclude):
    ch = P['chosen']
    check(len(ch) == n and len(set(ch)) == n, 'size / distinct')
    check(not (set(ch) & set(exclude)), 'exclusion')
    exp = collections.Counter(k for j in ch for k in seats_of[j])
    cexp = collections.Counter(seats_of[j][0] for j in ch)
    check(max(exp.values()) <= P['caps']['player'] and max(cexp.values()) <= P['caps']['captain'], 'caps')
    sets = [set(seats_of[j]) for j in ch]
    check(all(len(a & b) <= P['caps']['overlap'] for i, a in enumerate(sets) for b in sets[i + 1:]), 'overlap')


def _run(sel, hit, rows, seats_of, n, n_w, exclude=frozenset()):
    old = os.environ.pop('NFL_SHOWDOWN_SELECTOR', None)
    try:
        if sel:
            os.environ['NFL_SHOWDOWN_SELECTOR'] = sel
        return SP.ladder(hit, rows, seats_of, n, n_w, exclude)
    finally:
        os.environ.pop('NFL_SHOWDOWN_SELECTOR', None)
        if old is not None:
            os.environ['NFL_SHOWDOWN_SELECTOR'] = old


def test_repair_is_lawful_never_relaxes_more_and_completes_some_greedy_shortfall():
    completed_at_stricter = 0
    for seed in range(40):
        hit, rows, seats_of, n_w = _fixture(seed)
        excl = frozenset(range(0, 300, 37))
        G, _ = _run(None, hit, rows, seats_of, 20, n_w, excl)
        R, log = _run('FILL_REPAIR_V1', hit, rows, seats_of, 20, n_w, excl)
        if R['short'] == 0:
            _lawful(R, seats_of, 20, excl)
        check(R['relaxation_level'] <= G['relaxation_level'], (seed, R['relaxation_level'], G['relaxation_level']))
        if R['relaxation_level'] < G['relaxation_level']:
            completed_at_stricter += 1
            check(any(x.get('repair') == 'COMPLETED' for x in log), "any(x.get('repair') == 'COMPLETED' for x in log)")
    check(completed_at_stricter > 0, 'fixture never exercised a greedy shortfall that a repair completes')


def test_default_unchanged_and_unknown_selector_refuses():
    hit, rows, seats_of, n_w = _fixture(3)
    a, la = _run(None, hit, rows, seats_of, 20, n_w)
    b, lb = _run('GREEDY', hit, rows, seats_of, 20, n_w)
    check(a['chosen'] == b['chosen'] and la == lb and 'repair' not in a, "a['chosen'] == b['chosen'] and la == lb and 'repair' not in a")
    try:
        _run('FILL', hit, rows, seats_of, 20, n_w)
        raise AssertionError('an unknown selector must refuse')
    except ValueError:
        pass


def test_sel2_fixed_policy_level_2_for_20s_untouched_150_and_loud_when_unfillable():
    for seed in range(12):
        hit, rows, seats_of, n_w = _fixture(seed)
        F, flog = _run('FIXED_POLICY_V1', hit, rows, seats_of, 20, n_w)
        check(F['relaxation_level'] == SP.FIXED_POLICY_LEVEL and flog[0]['policy'] == 'FIXED_POLICY_V1', "F['relaxation_level'] == SP.FIXED_POLICY_LEVEL and flog[0]['policy'] == 'FIXED_POLICY_V1'")
        if not F.get('POLICY_UNFILLABLE'):
            _lawful(F, seats_of, 20, frozenset())
        else:
            check(F['short'] > 0, 'an unfillable contest must stay visibly short')
    # the 150-entry ladder is not covered by the owner decision and stays the greedy ladder
    hit, rows, seats_of, n_w = _fixture(5, n_c=1200, n_p=24)
    g150, _ = _run(None, hit, rows, seats_of, 150, n_w)
    f150, _ = _run('FIXED_POLICY_V1', hit, rows, seats_of, 150, n_w)
    check(g150['chosen'] == f150['chosen'] and g150['relaxation_level'] == f150['relaxation_level'], "g150['chosen'] == f150['chosen'] and g150['relaxation_level'] == f150['relaxation_level']")
    # unfillable at the policy: too few distinct lineups exist -> flagged, never relaxed
    hit, rows, seats_of, n_w = _fixture(9, n_c=12, n_p=8)
    U, ulog = _run('FIXED_POLICY_V1', hit, rows, seats_of, 20, n_w)
    check(U.get('POLICY_UNFILLABLE') is True and U['short'] > 0 and U['relaxation_level'] == SP.FIXED_POLICY_LEVEL, "U.get('POLICY_UNFILLABLE') is True and U['short'] > 0 and U['relaxation_level'] == SP.FIXED_POLICY_LEVEL")


def test_zz_every_check_passed():
    """The module's own counter, re-raised so a failure turns this module RED when run standalone."""
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')
    check(PASSED > 0, 'the module counted at least one check')


if __name__ == '__main__':
    test_repair_is_lawful_never_relaxes_more_and_completes_some_greedy_shortfall()
    test_default_unchanged_and_unknown_selector_refuses()
    test_sel2_fixed_policy_level_2_for_20s_untouched_150_and_loud_when_unfillable()
    test_zz_every_check_passed()
    print(f'PASSED {PASSED}  FAILED {FAILED}')
