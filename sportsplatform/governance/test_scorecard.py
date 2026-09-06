"""Rule 005 tested on the ways a model gets "better" while getting worse."""
import math, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from governance.outcome import State
from governance.scorecard import (score, headline, compare, LINKED,
                                  detectable_r_difference, design_effect,
                                  DesignEffectRetired,
                                  RETIRED_cluster_size_imbalance)


# NOTE 2026-09-04. score() no longer derives a design effect from cluster
# labels -- see scorecard.design_effect, retired. Where a test below feeds
# compare(), it now supplies deff=1.0 EXPLICITLY. That preserves each test's
# original arithmetic exactly, because the retired function returned 1.0 for
# the inputs these tests used; what changes is that the 1.0 is now a declared
# assumption of independence rather than a number that arrived by accident.

P = F = 0


def check(label, cond, detail=''):
    global P, F
    if cond:
        P += 1; print(f'  ok   {label}')
    else:
        F += 1; print(f'  FAIL {label}  {detail}')


def make(n=251, sd_p=0.7732, sd_a=4.2851, r=0.1101, seed=1):
    """Predictions and actuals with a KNOWN correlation, built not sampled."""
    import random
    rng = random.Random(seed)
    z1 = [rng.gauss(0, 1) for _ in range(n)]
    z2 = [rng.gauss(0, 1) for _ in range(n)]
    y = [r * a + math.sqrt(max(0.0, 1 - r * r)) * b for a, b in zip(z1, z2)]
    return ([9.0586 + sd_p * a for a in z1], [8.7171 + sd_a * b for b in y])


def test_the_three_are_one_fact():
    print('\nA. slope = r x SD_actual / SD_predicted, always')
    for seed in (1, 2, 3):
        p, a = make(seed=seed)
        c = score(p, a, fingerprint='FP-x', label='t').unwrap()
        lhs = c['calibration_slope']
        rhs = c['pearson_r'] * c['sd_actual'] / c['sd_predicted']
        check(f'seed {seed}: identity holds', abs(lhs - rhs) < 1e-12,
              f'{lhs} vs {rhs}')


def test_you_cannot_quote_one_of_them():
    print('\nB. the linked three cannot be split')
    p, a = make()
    c = score(p, a, fingerprint='FP-x', label='t').unwrap()
    for subset in (['pearson_r'], ['sd_ratio'], ['calibration_slope'],
                   ['pearson_r', 'sd_ratio']):
        o = headline(c, subset)
        check(f'{subset} refused', o.state is State.BLOCKED, str(o)[:60])
    o = headline(c, list(LINKED))
    check('all three together is allowed', o.state is State.PASS, str(o))
    o = headline(c, ['mae', 'rmse'])
    check('unlinked metrics are fine alone', o.state is State.PASS)


def test_dispersion_without_signal_is_caught():
    print('\nC. THE case: r rises, calibration degrades -> FAIL')
    p, a = make(r=0.11, sd_p=0.7732, seed=5)
    base = score(p, a, fingerprint='FP-v7', label='baseline', deff=1.0).unwrap()
    # Candidate: inflate the spread of predictions AND nudge r up slightly.
    m = sum(p) / len(p)
    p2 = [m + (x - m) * 3.0 for x in p]
    cand = score(p2, a, fingerprint='FP-v8', label='candidate', deff=1.0).unwrap()
    check('the SD ratio "improved"', cand['sd_ratio'] > base['sd_ratio'],
          f"{base['sd_ratio']:.4f} -> {cand['sd_ratio']:.4f}")
    check('but slope moved away from 1.0',
          abs(cand['calibration_slope'] - 1) > abs(base['calibration_slope'] - 1),
          f"{base['calibration_slope']:.4f} -> {cand['calibration_slope']:.4f}")
    # r is unchanged by a linear rescale, so force r up to trip the branch.
    cand2 = dict(cand); cand2['pearson_r'] = base['pearson_r'] + 0.05
    # r is unchanged by a linear rescale -- that is the point. Dispersion went
    # up, signal did not, and that is the combination to refuse.
    o = compare(base, cand)
    check('compare REFUSES it', o.state is State.FAIL, str(o)[:70])
    check('  naming dispersion without signal',
          o.code == 'DISPERSION_WITHOUT_SIGNAL', o.code)


def test_underpowered_is_not_no_improvement():
    print('\nD. "we could not tell" is DEFERRED, never FAIL or PASS')
    p, a = make(n=251, r=0.11, seed=9)
    base = score(p, a, fingerprint='FP-v7', label='b', deff=1.0,
                 date_clusters=[i // 2 for i in range(251)]).unwrap()
    p2, a2 = make(n=251, r=0.16, seed=10)
    cand = score(p2, a2, fingerprint='FP-v8', label='c', deff=1.0,
                 date_clusters=[i // 2 for i in range(251)]).unwrap()
    o = compare(base, cand)
    check('a small gain on 251 games is DEFERRED', o.state is State.DEFERRED,
          str(o)[:80])
    check('  and it is not terminal', o.state.is_terminal is False)
    check('  and says so explicitly',
          'NOT "it did not work"' in o.detail, o.detail[:90])
    check('  and states what r WOULD be detectable',
          o.evidence['r_needed_for_detection'] > cand['pearson_r'])


def test_a_real_improvement_passes():
    print('\nE. a large enough gain does pass')
    p, a = make(n=2000, r=0.11, seed=11)
    base = score(p, a, fingerprint='FP-v7', label='b', deff=1.0).unwrap()
    p2, a2 = make(n=2000, r=0.30, seed=12)
    cand = score(p2, a2, fingerprint='FP-v8', label='c', deff=1.0).unwrap()
    o = compare(base, cand)
    check('r 0.11 -> 0.30 on 2000 games passes', o.state is State.PASS, str(o)[:70])
    # ev is the PASS value here, not its evidence -- an earlier draft read the
    # wrong one and the Outcome was right to be empty.
    check('  and it flags that recalibration is needed, without failing it',
          o.unwrap().get('recalibration_required') is True,
          str(o.unwrap())[:80])


def test_cross_fingerprint_is_refused():
    print('\nF. two runs of the same engine are not a comparison')
    p, a = make()
    c1 = score(p, a, fingerprint='FP-same', label='a', deff=1.0).unwrap()
    c2 = score(p, a, fingerprint='FP-same', label='b', deff=1.0).unwrap()
    o = compare(c1, c2)
    check('same fingerprint refused', o.state is State.BLOCKED, str(o)[:60])


def test_clustering_makes_detection_harder():
    print('\nG. clustering inflates what it takes to detect something')
    solo = detectable_r_difference(251, 0.11, 1.0)
    clustered = detectable_r_difference(251, 0.11, 3.0)
    check('clustered needs a LARGER r to detect', clustered > solo,
          f'{solo:.4f} vs {clustered:.4f}')
    # RETIRED 2026-09-04. This check used to assert that the design effect
    # "is computed, not assumed". It was computed, and it was wrong: the
    # function returned exactly 1.0 for ANY balanced clustering, so on the
    # near-balanced date blocks this project actually has it reported no
    # clustering at all. The assertion `> 0` could never fail and was
    # therefore never evidence of anything. What replaces it is the refusal.
    try:
        design_effect([1, 1, 2, 2, 3, 3])
        check('design_effect refuses instead of returning a number', False,
              'it returned a value')
    except DesignEffectRetired:
        check('design_effect refuses instead of returning a number', True)
    check('the historical body is preserved so a past figure is re-derivable',
          RETIRED_cluster_size_imbalance([d for d in range(10)
                                          for _ in range(13)]) == 1.0,
          '1.0 for ten balanced clusters of thirteen')


def test_too_few_is_blocked_not_reported():
    print('\nH. an underpowered n is not a small result')
    o = score([1, 2], [1, 2], fingerprint='F', label='x')
    check('n=2 is BLOCKED', o.state is State.BLOCKED, str(o)[:60])
    check('  and says it is not a result', 'not a result' in o.detail)


if __name__ == '__main__':
    for t in (test_the_three_are_one_fact, test_you_cannot_quote_one_of_them,
              test_dispersion_without_signal_is_caught,
              test_underpowered_is_not_no_improvement,
              test_a_real_improvement_passes, test_cross_fingerprint_is_refused,
              test_clustering_makes_detection_harder,
              test_too_few_is_blocked_not_reported):
        t()
    print(f'\n{P} passed, {F} failed')
    sys.exit(1 if F else 0)
