"""Adversarial tests for RC1, the receiving conversion decomposition.

WHAT EACH SECTION DEFENDS

  A  current-game leakage -- no prior-only field may read the current row
  B  same-week chronology -- 1,318 player-ordinal pairs carry two rows
  C  denominators -- targets are receiver_player_id AND pass_attempt
  D  sacks -- every sack carries pass_attempt == 1; only the receiver rule
     keeps them out, so that is tested rather than trusted
  E  null is not zero
  F  postgame-only fields as pregame predictors
  G  oracle leakage into a non-oracle arm
  H  point substitution destroying draw dispersion -- R1's lesson, and its
     deliberate exception for oracles
  I  the mechanical identity
  J  result-driven eligibility changes

Run standalone:  python3.12 nfl/tests/test_rc1_receiving.py
"""
import copy
import json
import os
import pathlib
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), 'nfl', 'research', 'rc1'))

from sportsplatform.governance.outcome import Outcome, State      # noqa: E402
import rc1_lib as L                                               # noqa: E402
import rc1_sim as S                                               # noqa: E402
from nfl.tests.bypass import (assert_guard_is_load_bearing,       # noqa: E402
                              guard_bypassed)

PASSED = FAILED = 0
_CACHE = {}


def check(label, cond, detail=''):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}' + (f'  [{detail}]' if detail else ''))


def frame():
    if 'f' not in _CACHE:
        rows, sub = L.load()
        L.attach_prior(sub)
        _CACHE['f'] = (rows, sub)
    return _CACHE['f']


# ==========================================================================
def test_a_no_prior_field_reads_the_current_game():
    print('\nA. current-game leakage')
    _rows, sub = frame()
    # Perturb ONLY the current row's realised primitives, recompute the
    # prior-only history, and require every h_* field to be unchanged. A field
    # that moves has read the outcome it is supposed to predict.
    victim = None
    for r in sub:
        if r['season'] == 2024 and r['T'] >= 5 and r['h_n'] >= 6:
            victim = r
            break
    check('found a probe row', victim is not None)
    keys = [k for k in victim if k.startswith('h_')]
    before = {k: copy.deepcopy(victim[k]) for k in keys}
    sub2 = copy.deepcopy(sub)
    for r in sub2:
        if (r['season'], r['week'], r['team'], r['gsis_id']) == \
           (victim['season'], victim['week'], victim['team'], victim['gsis_id']):
            r['T'], r['R'], r['Y'] = 99, 99, 9999.0
            r['rec_yards_list'] = [101.0] * 99
    L.attach_prior(sub2)
    after = None
    for r in sub2:
        if (r['season'], r['week'], r['team'], r['gsis_id']) == \
           (victim['season'], victim['week'], victim['team'], victim['gsis_id']):
            after = r
    moved = [k for k in keys if before[k] != after[k]]
    check('inflating the CURRENT game moves no h_* field of that row',
          not moved, str(moved))


def test_a2_a_future_game_cannot_move_a_past_row():
    print('\nA2. a LATER game cannot move an EARLIER row')
    _rows, sub = frame()
    pid = None
    for r in sub:
        if r['h_n'] >= 8 and r['season'] == 2023:
            pid = r['gsis_id']
            break
    mine = sorted([r for r in sub if r['gsis_id'] == pid],
                  key=lambda x: x['ord'])
    early, late = mine[2], mine[-1]
    sub2 = copy.deepcopy(sub)
    for r in sub2:
        if r['gsis_id'] == pid and r['ord'] == late['ord']:
            r['T'], r['R'], r['Y'] = 99, 99, 9999.0
            r['rec_yards_list'] = [101.0] * 99
    L.attach_prior(sub2)
    a2 = [r for r in sub2 if r['gsis_id'] == pid and r['ord'] == early['ord']][0]
    check('a later game leaves the earlier row untouched',
          a2['h_T'] == early['h_T'] and a2['h_yds'] == early['h_yds'])


def test_b_same_week_ordinal_collisions():
    print('\nB. same-week chronology: two rows at one ordinal')
    _rows, sub = frame()
    import collections
    c = collections.Counter((r['gsis_id'], r['ord']) for r in sub)
    dup = [k for k, v in c.items() if v > 1]
    check(f'the collision is real in this frame ({len(dup)} player-ordinal '
          f'pairs carry two rows)', len(dup) > 0, len(dup))
    # For every collision, neither row may include the other in its history.
    bad = 0
    byk = collections.defaultdict(list)
    for r in sub:
        byk[(r['gsis_id'], r['ord'])].append(r)
    for k in dup[:200]:
        a, b = byk[k][0], byk[k][1]
        # h_n counts strictly-earlier appeared games; both rows must agree,
        # because neither may have seen the other.
        if a['h_n'] != b['h_n']:
            bad += 1
    check('both rows at a shared ordinal have identical prior history -- '
          'neither read the other', bad == 0, bad)


# ==========================================================================
def test_c_and_d_denominators_and_sacks():
    print('\nC/D. target denominator, and the sack trap')
    audit = json.loads((pathlib.Path(__file__).parents[1] / 'research' / 'rc1'
                        / 'audit_pbp.json').read_text())
    keys = audit.pop('_measured_keys')
    audit.pop('_note', None)
    # A Counter omits keys it never incremented, so a MISSING key and a
    # measured 0 would read alike. Every audited key must be PRESENT before any
    # zero is believed.
    for y, a in audit.items():
        miss = [k for k in keys if k not in a]
        check(f'{y}: every audited key is present, so a 0 means measured-zero '
              f'and not never-measured', not miss, str(miss))
    for y, a in audit.items():
        check(f'{y}: every sack carries pass_attempt == 1 '
              f'({a["sack_WITH_pass_attempt"]}/{a["sacks"]})',
              a['sack_WITH_pass_attempt'] == a['sacks'])
        check(f'  {y}: and NO sack carries a receiver_player_id',
              a['sack_WITH_receiver'] == 0, a['sack_WITH_receiver'])
    check('so a pass_attempt-only target rule would admit every sack -- '
          'the receiver rule is what excludes them',
          all(a['sacks'] > 0 for a in audit.values()))
    _rows, sub = frame()
    bad = [r for r in sub if r['R'] > r['T']]
    check('no player-game has more receptions than targets', not bad, len(bad))
    bad2 = [r for r in sub if r['T'] == 0 and r['Y'] != 0]
    check('no player-game has receiving yards with zero targets',
          not bad2, len(bad2))
    bad3 = [r for r in sub if r['R'] == 0 and r['Y'] != 0]
    check('no player-game has receiving yards with zero receptions',
          not bad3, len(bad3))


def test_e_null_is_not_zero():
    print('\nE. a missing field never becomes a silent zero')
    audit = json.loads((pathlib.Path(__file__).parents[1] / 'research' / 'rc1'
                        / 'audit_pbp.json').read_text())
    audit.pop('_measured_keys', None)
    audit.pop('_note', None)
    for y, a in audit.items():
        check(f'{y}: receiving_yards is NULL on all {a["incompletions"]} '
              f'incompletions, never 0',
              a['INCOMPLETION_with_nonzero_recv_yards'] == 0
              and a.get('incompletion_recv_yards_NULL') == a['incompletions'])
        check(f'  {y}: yards_after_catch is never present on an incompletion',
              a['incompletion_yac_NOT_null'] == 0)
    src = (pathlib.Path(__file__).parents[1] / 'research' / 'rc1'
           / 'build_recv.py').read_text()
    check('the builder counts a null air_yards as MISSING rather than summing 0',
          "p['target_air_yards_missing'] += 1" in src)
    check('  and a null receiving_yards likewise',
          "p['reception_yards_missing'] += 1" in src)
    _rows, sub = frame()
    tot_missing = sum(r['n_missing_recv_yards'] for r in sub)
    check('the frame carries the missing count rather than discarding it',
          isinstance(tot_missing, int), tot_missing)


def test_f_postgame_fields_are_not_predictors():
    print('\nF. postgame-only fields never enter a prior-only feature')
    _rows, sub = frame()
    r = sub[0]
    prior = [k for k in r if k.startswith('h_')]
    outcome = {'T', 'R', 'Y', 'C', 'V', 'air_yards_caught', 'yac',
               'rec_yards_list', 'n_lateral'}
    check('no prior-only field is named after a realised outcome',
          not (set(prior) & outcome), set(prior) & outcome)
    # weekly_rosters.status is forbidden project-wide; assert it is absent.
    check('weekly_rosters.status is absent from the frame',
          'status' not in r, [k for k in r if k == 'status'])
    check('the simulator reads no realised value unless the arm is an oracle',
          'oracle' in S.simulate.__code__.co_varnames)


# ==========================================================================
def test_g_oracle_does_not_leak_into_a_non_oracle_arm():
    print('\nG. oracle leakage')
    _rows, sub = frame()
    rs = [r for r in sub if L.eligible(r, 2024)][:400]
    base = S.simulate(rs, 2024, sub, oracle=())

    # Rows are seeded per (seed, ordinal, player), so the draws for one row do
    # not depend on any other row. Proved here, because the probe below is
    # meaningless without it: a shared RNG stream made a change anywhere shift
    # every later row, and 21 rows once moved whose prior features had not.
    check('a row\'s draws do not depend on where it sits in the list',
          np.array_equal(base, S.simulate(list(reversed(rs)), 2024, sub,
                                          oracle=())[::-1]))

    # Corrupt the realised outcome ONLY on rows that no other probe row uses as
    # history -- a player's LAST appearance in the set. Corrupting an earlier
    # appearance would legitimately change a later row's prior history, which
    # is correct behaviour and would mask the thing being tested.
    import collections
    last = {}
    for i, r in enumerate(rs):
        last[r['gsis_id']] = i
    tail = set(last.values())
    check('the probe has rows to work with', len(tail) > 100, len(tail))
    sub2 = copy.deepcopy(sub)
    keep = {(rs[i]['season'], rs[i]['week'], rs[i]['team'], rs[i]['gsis_id'])
            for i in tail}
    for r in sub2:
        if (r['season'], r['week'], r['team'], r['gsis_id']) in keep:
            r['Y'] = r['Y'] * 3.0 + 17.0
            r['R'] = min(r['R'] + 2, r['T'])
            r['rec_yards_list'] = [77.0] * r['R']
    L.attach_prior(sub2)
    rs2 = [r for r in sub2 if L.eligible(r, 2024)][:400]
    base2 = S.simulate(rs2, 2024, sub2, oracle=())
    idx = sorted(tail)
    check('the baseline arm is bit-identical on every corrupted row -- it '
          'never reads the outcome it forecasts',
          np.array_equal(base[idx], base2[idx]))

    # The teeth arm must oracle a component the corruption actually touched.
    # An oracle-T arm reads r['T'], which this probe leaves alone, so it would
    # correctly NOT move -- and a passing test built on that would have proved
    # nothing. V = Y / R, and both were corrupted.
    orc = S.simulate(rs, 2024, sub, oracle=('V',))
    orc2 = S.simulate(rs2, 2024, sub2, oracle=('V',))
    check('  while an oracle-V arm DOES move, proving the probe had teeth',
          not np.array_equal(orc[idx], orc2[idx]))
    unt = S.simulate(rs2, 2024, sub2, oracle=('T',))
    check('  and an oracle-T arm does not, because T was not corrupted -- '
          'the probe moves exactly what it touched',
          np.array_equal(S.simulate(rs, 2024, sub, oracle=('T',))[idx],
                         unt[idx]))


def test_h_dispersion_oracle_versus_candidate():
    print('\nH. dispersion: an oracle may collapse it, a candidate may not')
    _rows, sub = frame()
    rs = [r for r in sub if L.eligible(r, 2024)][:400]
    base = S.simulate(rs, 2024, sub, oracle=())
    check('the baseline carries real dispersion',
          float(base.std(1).mean()) > 1.0, float(base.std(1).mean()))
    full = S.simulate(rs, 2024, sub, oracle=('C', 'T', 'V'))
    check('the FULL oracle collapses dispersion to zero -- that is what '
          '"perfect" means, per the substitution addendum',
          float(full.std(1).max()) == 0.0, float(full.std(1).max()))
    # A CANDIDATE substitution must NOT collapse it. R1: replacing a draw
    # matrix with a point estimate destroyed CV 0.914 of dispersion and
    # manufactured +0.0542 of apparent harm.
    def cand_C(r, pool_rate, w):
        return 0.65
    withc = S.simulate(rs, 2024, sub, oracle=(), candidate={'C': cand_C})
    check('a CANDIDATE catch-rate substitution preserves draw dispersion',
          float(withc.std(1).mean()) > 1.0, float(withc.std(1).mean()))
    check('  and it actually changed the forecast, so the probe is not vacuous',
          not np.array_equal(base, withc))

    # The V candidate is the sharper case: it supplies a MEAN, and a naive
    # implementation would write that mean into every pick.
    def cand_V(r, pool_mean, w):
        return 14.0
    withv = S.simulate(rs, 2024, sub, oracle=(), candidate={'V': cand_V})
    check('a CANDIDATE yards-per-reception substitution preserves dispersion '
          'by RECENTRING the draws, not replacing them',
          float(withv.std(1).mean()) > 1.0, float(withv.std(1).mean()))
    check('  and it moved the forecast', not np.array_equal(base, withv))
    # The coefficient of variation is what R1 lost. It must survive.
    m = (base.mean(1) > 1) & (withv.mean(1) > 1)
    cv_b = float((base.std(1)[m] / base.mean(1)[m]).mean())
    cv_v = float((withv.std(1)[m] / withv.mean(1)[m]).mean())
    check(f'  the coefficient of variation survives the substitution '
          f'({cv_b:.4f} -> {cv_v:.4f}) -- R1 destroyed CV 0.914 here',
          abs(cv_b - cv_v) < 0.02, f'{cv_b} vs {cv_v}')


def test_i_mechanical_identity():
    print('\nI. the identity Y = T x C x V')
    _rows, sub = frame()
    rs = [r for r in sub if L.eligible(r, 2023)]
    y = np.array([r['Y'] for r in rs], float)
    full = S.simulate(rs, 2023, sub, oracle=('C', 'T', 'V'))
    err = float(np.abs(full.mean(1) - y).max())
    check(f'arm E reproduces every realised Y exactly (max |err| {err:.2e})',
          err < 1e-9, err)
    check('  with zero draw spread', float(full.std(1).max()) == 0.0)
    # A deliberately wrong identity must fail this, or the check proves nothing.
    broken = full * 1.0001
    check('  a 0.01% perturbation is detected',
          float(np.abs(broken.mean(1) - y).max()) > 1e-9)
    # Shapley efficiency
    v = {frozenset(): 0.0}
    import itertools
    for k in range(1, 4):
        for c in itertools.combinations(S.COMPONENTS, k):
            v[frozenset(c)] = float(len(c))
    phi = S.shapley(v)
    check('Shapley is efficient: the parts sum to the grand coalition',
          abs(sum(phi.values()) - v[frozenset(S.COMPONENTS)]) < 1e-12)
    check('  and order-invariant: a pure 3-way interaction splits equally',
          len({round(x, 12) for x in S.shapley(
              {**{frozenset(c): 0.0 for k in range(3)
                  for c in itertools.combinations(S.COMPONENTS, k)},
               frozenset(S.COMPONENTS): 9.0}).values()}) == 1)


def test_j_eligibility_is_not_result_driven():
    print('\nJ. eligibility is fixed by the pre-registration, not by results')
    pre = (pathlib.Path(__file__).parents[1] / 'research' / 'rc1'
           / 'predeclaration_rc1.md')
    import hashlib
    h = hashlib.sha256(pre.read_bytes()).hexdigest()
    check('the pre-registration hash is unchanged since it was committed',
          h == '34f8ac10be7bc0c5b39ee0e89340a3061ff0910dca803d4975887b8811c02cdd',
          h)
    _rows, sub = frame()
    # The frame must NOT drop zero-target appearances: dropping them would
    # condition on the estimand and would flatter every arm.
    z = [r for r in sub if L.eligible(r, 2024) and r['T'] == 0]
    check('zero-target appearances remain in the frame', len(z) > 0, len(z))
    check('  and they carry Y == 0 rather than being treated as missing',
          all(r['Y'] == 0 for r in z))
    src = (pathlib.Path(__file__).parents[1] / 'research' / 'rc1'
           / 'rc1_lib.py').read_text()
    check('the seed is a fixed module constant, not an argument to be tuned',
          'SEED = 20260908' in src)
    check('EVAL is fixed to the predeclared seasons',
          L.EVAL == [2022, 2023, 2024, 2025], L.EVAL)


# ==========================================================================
def test_k_guard_deletions():
    print('\nK. guard-deletion proofs')

    _rows, sub = frame()
    rs = [r for r in sub if L.eligible(r, 2024)][:300]

    # K1 -- the chronology prefix cut. Bypass bisect and the history grows to
    # include same-ordinal rows, which is the same-week leak.
    import bisect as _b

    def run_chrono():
        s2 = copy.deepcopy(sub)
        L.attach_prior(s2)
        import collections
        byk = collections.defaultdict(list)
        for r in s2:
            byk[(r['gsis_id'], r['ord'])].append(r)
        dups = [v for v in byk.values() if len(v) > 1]
        # returns the number of shared-ordinal pairs whose histories DIFFER,
        # i.e. where one row saw the other
        return sum(1 for v in dups if v[0]['h_n'] != v[1]['h_n'])

    clean = run_chrono()
    check(f'K1 with the prefix cut in place, 0 shared-ordinal pairs leak '
          f'(got {clean})', clean == 0, clean)
    with guard_bypassed('rc1_lib', 'bisect',
                        replacement=None,
                        returns=None):
        pass  # bisect is a module; bypass it via its function instead

    class _FakeBisect:
        @staticmethod
        def bisect_left(a, x):
            return len(a)          # "everything appended so far"
    orig = L.bisect
    L.bisect = _FakeBisect
    try:
        leaked = run_chrono()
    finally:
        L.bisect = orig
    check(f'K1 bypassed, shared-ordinal pairs DO leak ({leaked} of them) -- '
          f'the prefix cut is load-bearing', leaked > 0, leaked)
    check('  and the guard is restored', run_chrono() == 0)

    # K2 -- the oracle flag. Bypass it and a "baseline" arm reads the outcome.
    def run_oracle_sep():
        b = S.simulate(rs, 2024, sub, oracle=())
        y = np.array([r['Y'] for r in rs], float)
        return float(L.crps_matrix(b, y).mean())

    honest = run_oracle_sep()
    _real = S.simulate

    def _leaky(rs_, ev, sub_, oracle=(), **kw):
        return _real(rs_, ev, sub_, oracle=('C', 'T', 'V'), **kw)
    S.simulate = _leaky
    try:
        cheating = run_oracle_sep()
    finally:
        S.simulate = _real
    check(f'K2 an arm that secretly oracles everything scores 0 CRPS '
          f'({cheating:.2e}) against the honest {honest:.3f} -- so the arm '
          f'separation is what produces the baseline number',
          cheating < 1e-9 < honest, f'{cheating} / {honest}')
    check('  and simulate is restored', abs(run_oracle_sep() - honest) < 1e-12)


if __name__ == '__main__':
    test_a_no_prior_field_reads_the_current_game()
    test_a2_a_future_game_cannot_move_a_past_row()
    test_b_same_week_ordinal_collisions()
    test_c_and_d_denominators_and_sacks()
    test_e_null_is_not_zero()
    test_f_postgame_fields_are_not_predictors()
    test_g_oracle_does_not_leak_into_a_non_oracle_arm()
    test_h_dispersion_oracle_versus_candidate()
    test_i_mechanical_identity()
    test_j_eligibility_is_not_result_driven()
    test_k_guard_deletions()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
