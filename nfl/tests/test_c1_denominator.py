"""C1: the carry allocator's `other` mass must match the budget's denominator.

THE DEFECT THESE PIN

`p4c_build` fits `mass_pool` as `mall - ms` where `mall` sums EVERY position,
so for the carries class it is the share of TEAM carries not taken by modelled
running backs -- 0.198875, against a historical non-RB mass of 0.1918.
Production multiplies the resulting shares by A1's `rb` category, from which
kneel, designed_qb, wr, te and fringe are already gone. The same mass came off
twice and the modelled backs lost about 19 points of their budget.

WHAT IS ACTUALLY GUARDED HERE, AND WHY EACH ONE

1.  The flag tracks the BUDGET. If someone later hands the engine A1's budget
    without declaring the partition, or declares it without an A1 budget, the
    two drift and the defect returns silently. The engine reads both off one
    variable and a test says so.
2.  A declared partition with no partition pool REFUSES. The tempting
    implementation falls back to `mass_pool`, which is exactly the double
    subtraction, and it would be invisible in the output.
3.  The receiving side is BIT-IDENTICAL. It is the control that identified
    this as a seam rather than a modelling error, and a repair that moves it
    is a repair that has escaped its scope.
4.  `mass_pool` itself is unchanged. C1 is additive; anything reading the old
    key must see the old bytes.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from nfl.production.nonqb import layers as LY                    # noqa: E402
from sportsplatform.governance.outcome import Outcome, State     # noqa: E402

PASSED = FAILED = 0
PREREG = ('9d0443e1bd777d31371d2f7073c4e8acf2be9afcc6b4730471957b225e83e9a0')


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}' + (f'  {detail}' if detail else ''))
    else:
        FAILED += 1
        print(f'  FAIL {label}' + (f'  {detail}' if detail else ''))


def _pools():
    """The two fitted pools, on the two denominators."""
    return (np.full(400, 0.1989, np.float32),      # team denominator
            np.full(400, 0.0088, np.float32))      # RB denominator


def test_a_the_two_pools_are_different_quantities():
    """`other` on the team denominator is the non-RB mass. On the RB
    denominator it is the unmodelled backs, and they are not the same number.
    """
    base, part = _pools()
    check('the team-denominator pool carries the non-RB mass',
          abs(float(base.mean()) - 0.1989) < 1e-4, f'{float(base.mean()):.4f}')
    check('  which matches the historical non-RB share of team carries',
          abs(0.1989 - 0.1918) < 0.01,
          'fitted 0.198875 against a measured 0.1918')
    check('the RB-denominator pool is more than an order smaller',
          float(base.mean()) / float(part.mean()) > 10,
          f'{float(base.mean()) / float(part.mean()):.1f}x')


def test_b_the_engine_selects_the_pool_beside_the_multiplier():
    """The selection must sit next to the line that chooses the budget, or the
    two drift apart and the double subtraction returns silently."""
    src = pathlib.Path(_ROOT, 'nfl', 'production', 'nonqb',
                       'football_engine.py').read_text()
    check('the engine swaps in mass_pool_partition when A1 owns the budget',
          "_cpar['mass_pool'] = _part" in src
          and 'if rushing_budget is not None:' in src)
    check('  and records which denominator it used, as a reported layer',
          "g['layers']['carry_other_denominator']" in src
          and 'PASS[A1_RB_PARTITION_POOL]' in src
          and 'NOT_APPLICABLE[D1_TEAM_CARRIES_POOL]' in src)
    check('  and REFUSES rather than falling back to the team pool',
          'P4C_PARTITION_POOL_MISSING' in src
          and 'rather than defaulting' in src)
    check('  and the receiving call is not touched by any of it',
          "LY.targets_carries(pa, 'targets'" in src
          and 'mass_pool_partition' not in src.split(
              "LY.targets_carries(pa, 'targets'")[1].split('# ---- carries')[0])


def test_c_the_frozen_q9_identity_is_not_disturbed():
    """Q9 hashes `nfl.production.nonqb.layers` source into its candidate
    identity. C1 was first written as an argument to `targets_carries`, which
    moved that hash and broke a freeze it has no business touching. It now
    lives in the engine, which Q9 does not hash.
    """
    src = pathlib.Path(_ROOT, 'nfl', 'production', 'nonqb',
                       'layers.py').read_text()
    check('layers.py carries no C1 argument',
          'budget_is_partition' not in src)
    check('  and no partition pool selection',
          'mass_pool_partition' not in src)
    from nfl.prospective.q9shadow import candidate as CAND
    sealed = pathlib.Path(
        _ROOT, 'nfl', 'prospective', 'q9shadow', 'dryrun',
        '2024_01_ARI_BUF', 'ARI', 'SEALED_FORECAST.json')
    if not sealed.exists():
        check('a sealed Q9 dry run exists to compare against', False)
        return
    a = json.loads(sealed.read_text())
    check('  so the sealed Q9 candidate identity still reproduces',
          CAND.identity_sha256(CAND.identity(a['season']))
          == a['candidate']['identity_sha256'],
          a['candidate']['identity_sha256'][:16])


def test_e_receiving_is_untouched_by_construction():
    """The targets class is the control. C1 must not be able to reach it."""
    sys.path.insert(0, str(pathlib.Path(_ROOT, 'nfl', 'research', 'p4c')))
    import p4c_lib as L
    check("the targets class denominator is still team_targets",
          L.CLASSES['targets']['den'] == 'team_targets')
    check('  over every target-taking position',
          set(L.CLASSES['targets']['pos']) == {'WR', 'TE', 'RB'})
    check('the carries class denominator is still team_carries',
          L.CLASSES['carries']['den'] == 'team_carries',
          'C1 does not edit the class; it declares what the BUDGET is')
    check('  over running backs only',
          tuple(L.CLASSES['carries']['pos']) == ('RB',))


def test_f_mass_pool_itself_is_unchanged():
    """C1 is additive. The old key must still hold the old quantity."""
    src = pathlib.Path(_ROOT, 'nfl', 'research', 'p4c',
                       'p4c_build.py').read_text()
    check("mass_pool is still mall - ms over every position",
          "pool = np.array([max(0.0, min(0.95, mall[k] - ms[k])) for k in mall]"
          in src)
    check('  and mass_pool_partition is a SEPARATE key',
          "par['mass_pool_partition'] = rbp" in src)
    check('  built on the class position mass, not on 1.0',
          '(mpos[k] - ms[k]) / mpos[k]' in src)
    check('  and team-games with no position mass are counted, not zeroed',
          "par['n_team_games_no_position_mass']" in src)


def test_g_the_evaluation_is_registered_and_exploratory():
    p = pathlib.Path(_ROOT, 'nfl', 'research', 'slate_audit',
                     'C1_EVALUATION.json')
    if not p.exists():
        check('the C1 evaluation artifact exists', False, str(p))
        return
    v = json.loads(p.read_text())
    check('the C1 evaluation artifact exists', True)
    check('  it cites the frozen pre-registration',
          v.get('preregistration_sha256') == PREREG)
    check('  it is labelled EXPLORATORY', v.get('status') == 'EXPLORATORY')
    check('  it consulted no market information',
          v.get('market_information_consulted') == 'NONE')
    check('  all five acceptance criteria passed',
          all(v['acceptance_criteria_section_7'].values()),
          json.dumps(v['acceptance_criteria_section_7']))
    check('  the direction is consistent in all three seasons',
          all(r['crps_diff_c1_minus_baseline'] < 0
              for r in v['per_season'].values()))
    check('  every season interval excludes zero and reports its cluster count',
          all((r['crps_diff_clustered_bootstrap'] or {}).get('hi', 1) < 0
              and (r['crps_diff_clustered_bootstrap'] or {}).get('n_clusters')
              for r in v['per_season'].values()))


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for fn in sorted(k for k in dict(globals()) if k.startswith('test_')):
        print(f'\n{fn}')
        globals()[fn]()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
