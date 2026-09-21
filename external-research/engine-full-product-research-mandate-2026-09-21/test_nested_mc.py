"""Synthetic validation of the corrected Block XV estimator.

THE CLAIM UNDER TEST. For the balanced nested design, s_M^2 / M is unbiased
for Var(Y_bar), and the Revision 2 formula

    s_M^2/M + s_K^2/(M K) + s_N^2/(M K N)

has expectation

    sigma_M^2/M + 2 sigma_K^2/(M K) + 3 sigma_N^2/(M K N),

counting the scenario component twice and the world component three times.
These are checked against known variance components by repeated sampling,
which is the only way to show an estimator is unbiased rather than merely
plausible.

Synthetic only; this validates arithmetic, not football.
"""
from __future__ import annotations

import os
import random
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import nested_mc as nmc                                          # noqa: E402

PASSED = FAILED = 0


def ok(cond, what):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f"  ok     {what}")
    else:
        FAILED += 1
        print(f"  FAIL   {what}")


def draw(rng, M, K, N, sm, sk, sn, mu=0.0):
    out = []
    for _m in range(M):
        a = rng.gauss(0, sm)
        blk = []
        for _k in range(K):
            b = rng.gauss(0, sk)
            blk.append([mu + a + b + rng.gauss(0, sn) for _n in range(N)])
        out.append(blk)
    return out


def test_the_first_term_alone_is_unbiased_for_the_mc_variance():
    rng = random.Random(20260921)
    M, K, N = 12, 4, 25
    sm, sk, sn = 0.30, 0.50, 1.20
    truth = (sm ** 2 + sk ** 2 / K + sn ** 2 / (K * N)) / M
    reps = 4000
    ours = [nmc.nested_mc(draw(rng, M, K, N, sm, sk, sn)).mc_variance
            for _ in range(reps)]
    est = statistics.fmean(ours)
    se = statistics.pstdev(ours) / (reps ** 0.5)
    ok(abs(est - truth) < 3 * se,
       f"E[s_M^2/M] = {est:.6g} against the true Var(Y_bar) = {truth:.6g} "
       f"(3 SE = {3 * se:.2g})")

    # And the empirical variance of the grand mean agrees with the truth,
    # which is what makes `truth` the right target rather than an algebra
    # exercise.
    means = [nmc.nested_mc(draw(rng, M, K, N, sm, sk, sn)).grand_mean
             for _ in range(reps)]
    ok(abs(statistics.pvariance(means) - truth) < 0.12 * truth,
       f"the realised spread of the grand mean, {statistics.pvariance(means):.6g}, "
       f"matches it within 12%")


def test_revision_2_inflates_by_exactly_two_and_three():
    rng = random.Random(7)
    M, K, N = 10, 5, 20
    reps = 4000
    for sm, sk, sn, label in ((0.0, 0.8, 0.0, "scenario only"),
                              (0.0, 0.0, 1.5, "world only"),
                              (0.4, 0.6, 1.0, "all three")):
        truth = (sm ** 2 + sk ** 2 / K + sn ** 2 / (K * N)) / M
        rev2_expected = (sm ** 2 / M + 2 * sk ** 2 / (M * K)
                         + 3 * sn ** 2 / (M * K * N))
        got = statistics.fmean(
            nmc.nested_mc(draw(rng, M, K, N, sm, sk, sn)).rev2_mc_variance
            for _ in range(reps))
        ok(abs(got - rev2_expected) < 0.05 * rev2_expected,
           f"[{label}] the Revision 2 formula averages {got:.6g}, predicted "
           f"{rev2_expected:.6g} by the derivation")
        ok(got > truth * 1.05,
           f"[{label}] and overstates the truth {truth:.6g} by "
           f"{got / truth:.2f}x")
    # The two clean cases pin the multipliers exactly.
    truth_s = (0.8 ** 2 / K) / M
    got_s = statistics.fmean(
        nmc.nested_mc(draw(rng, M, K, N, 0.0, 0.8, 0.0)).rev2_mc_variance
        for _ in range(reps))
    ok(abs(got_s / truth_s - 2.0) < 0.10,
       f"a scenario-only design is inflated {got_s / truth_s:.3f}x, "
       f"predicted exactly 2")
    truth_w = (1.5 ** 2 / (K * N)) / M
    got_w = statistics.fmean(
        nmc.nested_mc(draw(rng, M, K, N, 0.0, 0.0, 1.5)).rev2_mc_variance
        for _ in range(reps))
    ok(abs(got_w / truth_w - 3.0) < 0.12,
       f"a world-only design is inflated {got_w / truth_w:.3f}x, predicted "
       f"exactly 3")


def test_the_variance_components_recover_what_generated_them():
    rng = random.Random(99)
    M, K, N = 60, 6, 40
    sm, sk, sn = 0.35, 0.55, 1.10
    reps = 240
    acc = {"parameter": [], "scenario": [], "world": []}
    for _ in range(reps):
        r = nmc.nested_mc(draw(rng, M, K, N, sm, sk, sn))
        acc["parameter"].append(r.var_components["parameter_raw"])
        acc["scenario"].append(r.var_components["scenario_raw"])
        acc["world"].append(r.var_components["world"])
    for name, true in (("parameter", sm ** 2), ("scenario", sk ** 2),
                       ("world", sn ** 2)):
        est = statistics.fmean(acc[name])
        ok(abs(est - true) < 0.10 * true + 1e-4,
           f"sigma^2_{name} estimated {est:.5f} against {true:.5f}")

    r = nmc.nested_mc(draw(rng, M, K, N, sm, sk, sn))
    ok(abs(r.predictive_variance
           - sum(r.var_components[k] for k in
                 ("parameter", "scenario", "world"))) < 1e-12,
       "G-XV-1: the reported components sum to the predictive variance")
    ok(r.predictive_variance > r.mc_variance * 100,
       f"and the predictive variance ({r.predictive_variance:.4f}) is a "
       f"different and far larger quantity than the Monte Carlo variance "
       f"({r.mc_variance:.6f}) -- conflating them was the underlying error")


def test_it_refuses_a_design_it_cannot_speak_for():
    rng = random.Random(3)
    try:
        nmc.nested_mc(draw(rng, 1, 3, 5, 0.3, 0.3, 0.3))
        ok(False, "M = 1 should refuse")
    except ValueError as e:
        ok("not identified" in str(e),
           f"M = 1 refuses rather than reporting a zero parameter component: "
           f"{e}")
    bad = draw(rng, 3, 3, 5, 0.3, 0.3, 0.3)
    bad[1] = bad[1][:2]
    try:
        nmc.nested_mc(bad)
        ok(False, "an unbalanced design should refuse")
    except ValueError as e:
        ok("unbalanced" in str(e),
           f"an unbalanced design refuses rather than applying balanced "
           f"algebra: {e}")


def test_which_level_to_expand_points_at_the_dominant_component():
    rng = random.Random(11)
    M, K, N = 20, 5, 30
    cases = ((2.0, 0.05, 0.05, "INCREASE_M"),
             (0.01, 2.0, 0.05, "INCREASE_K"),
             (0.01, 0.02, 9.0, "INCREASE_N"))
    for sm, sk, sn, want in cases:
        r = nmc.nested_mc(draw(rng, M, K, N, sm, sk, sn))
        rec = nmc.which_level_to_expand(r)
        ok(rec["recommend"] == want,
           f"sm={sm} sk={sk} sn={sn} -> {rec['recommend']} (want {want})")


def test_weighted_reweighting_uncertainty():
    rng = random.Random(5)
    M, K, N = 30, 4, 20
    y = draw(rng, M, K, N, 0.4, 0.5, 1.0, mu=2.0)
    flat = [[[1.0] * N for _ in range(K)] for _ in range(M)]
    w = nmc.weighted_nested_mc(y, flat)
    u = nmc.nested_mc(y)
    ok(abs(w.weighted_mean - u.grand_mean) < 1e-12,
       "with equal weights the weighted mean is the grand mean")
    ok(abs(w.mc_variance - u.mc_variance) < 1e-12,
       f"and the weighted variance collapses to s_M^2/M: "
       f"{w.mc_variance:.8g} vs {u.mc_variance:.8g}")
    ok(abs(w.ess - M * K * N) < 1e-6,
       f"equal weights give full effective sample size: {w.ess:.1f}")

    uneven = [[[rng.expovariate(1.0) for _ in range(N)] for _ in range(K)]
              for _ in range(M)]
    wu = nmc.weighted_nested_mc(y, uneven)
    ok(wu.ess < M * K * N,
       f"uneven weights reduce ESS: {wu.ess:.1f} of {M * K * N}")
    ok(0 < wu.ess_fraction < 1 and wu.max_weight_ratio > 1,
       f"ESS fraction {wu.ess_fraction:.3f} and weight ratio "
       f"{wu.max_weight_ratio:.1f} are what G-XIX-3 checks")
    ok(wu.weights_treated_as_fixed is True
       and any("sampling error" in n for n in wu.notes),
       "and the result states that the weights are treated as fixed, so the "
       "interval is conditional on a fitted vector")

    try:
        nmc.weighted_nested_mc(y, [[[-1.0] * N for _ in range(K)]
                                   for _ in range(M)])
        ok(False, "a negative weight should refuse")
    except ValueError as e:
        ok("negative" in str(e), f"a negative weight refuses: {e}")


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f"{FAILED} check(s) failed in this module")


def main():
    for t in (test_the_first_term_alone_is_unbiased_for_the_mc_variance,
              test_revision_2_inflates_by_exactly_two_and_three,
              test_the_variance_components_recover_what_generated_them,
              test_it_refuses_a_design_it_cannot_speak_for,
              test_which_level_to_expand_points_at_the_dominant_component,
              test_weighted_reweighting_uncertainty):
        print(f"== {t.__name__}")
        t()
    print(f"\nPASSED {PASSED} FAILED {FAILED}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
