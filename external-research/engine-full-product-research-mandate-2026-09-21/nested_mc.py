r"""Block XV corrected: nested Monte Carlo error, and uncertainty after reweighting.

FINDING 7. THE REVISION 2 FORMULA DOUBLE-COUNTS, AND BY EXACTLY 2x AND 3x.

Revision 2, Block XV:

    Var_hat(Y_bar) = s_M^2 / M  +  s_K^2 / (M K)  +  s_N^2 / (M K N)

with s_M^2 "the sample variance of the M parameter-level means (each averaged
over its K N worlds)", s_K^2 the pooled within-parameter variance of the K
scenario-level means, and s_N^2 the pooled within-cell variance of worlds.

THE DERIVATION. Write the balanced nested model

    Y_mkn = mu + a_m + b_mk + e_mkn,
    a_m ~ (0, sigma_M^2),  b_mk ~ (0, sigma_K^2),  e_mkn ~ (0, sigma_N^2),

all independent. The parameter-level mean is Y_bar_m = mu + a_m + b_bar_m. +
e_bar_m.., so

    Var(Y_bar_m) = sigma_M^2 + sigma_K^2 / K + sigma_N^2 / (K N).            (1)

The M parameter draws are independent and identically distributed, so the
grand mean has

    Var(Y_bar) = Var(Y_bar_m) / M
               = [ sigma_M^2 + sigma_K^2/K + sigma_N^2/(K N) ] / M.          (2)

s_M^2 is the sample variance of the Y_bar_m, so E[s_M^2] is exactly (1).
Therefore

    E[ s_M^2 / M ] = Var(Y_bar)                                              (3)

-- the FIRST TERM ALONE is already unbiased for the whole Monte Carlo
variance. The lower-level noise is not missing from it; it is inside it, by
construction, because a parameter-level mean is itself an average of noisy
things.

Now take expectations of the other two terms. With E[s_K^2] = sigma_K^2 +
sigma_N^2/N and E[s_N^2] = sigma_N^2,

    E[Var_hat_rev2] = sigma_M^2/M + 2 sigma_K^2/(M K) + 3 sigma_N^2/(M K N).  (4)

Against the truth (2), the SCENARIO component is counted TWICE and the WORLD
component THREE TIMES. The bias is not a rounding matter: in a design where
the parameter component is small -- which is the regime the packet says to
watch for, and the regime a well-converged release is in -- the estimator can
approach three times the true variance, so the reported Monte Carlo standard
error approaches 1.73x too large. G-XV-2 ("MC SE below a fraction of the
predictive SD") would then fail releases that are fine, and the draw-count
controller in T-34 would buy worlds it does not need.

The packet calls s_M^2/M "the conservative estimator". It is not conservative.
It is the exact one, and the "finer decomposition" offered in preference to it
is the inflated one.

WHAT REPLACES IT

Monte Carlo error of the grand mean:      Var_hat(Y_bar) = s_M^2 / M.
Variance COMPONENTS, for deciding which level to expand, from the standard
balanced-nested expected mean squares:

    sigma_hat_N^2 = MS_N
    sigma_hat_K^2 = (MS_K - MS_N) / N
    sigma_hat_M^2 = (MS_M - MS_K) / (K N)

These two are different quantities answering different questions and the
module returns both separately, which is the distinction Block XV blurred:

  * PREDICTIVE variance (sigma_M^2 + sigma_K^2 + sigma_N^2) is how much the
    forecast itself spreads. It does not shrink when you draw more.
  * MONTE CARLO variance (2) is how precisely we located its mean. It shrinks
    like 1/M.

G-XV-1 ("components sum to total") is a statement about the first. G-XV-2 and
G-XV-3 are statements about the second. Checking one against the other is how
the two got mixed in the first place.

UNCERTAINTY AFTER FITTED WORLD REWEIGHTING (Block XIX)

Reweighting multiplies world w by a non-negative weight. Two things change and
Revision 2 specified neither.

1. The estimator becomes self-normalised: mu_hat_w = sum(w Y) / sum(w). It is
   a RATIO, so it is biased at finite sample and its variance is not the
   unweighted one. The block structure is the thing to preserve: parameter
   draws are still independent, so take the ratio over parameter blocks and
   use the standard linearisation,

       Var_hat(mu_hat_w) = [1 / (M * W_bar^2)] * (1/(M-1)) *
                            sum_m [ W_m (Y_bar_m^w - mu_hat_w) ]^2

   with W_m the block's total weight and W_bar their mean. With equal weights
   this collapses to s_M^2/M, which is the check the tests make.

2. THE WEIGHTS ARE FITTED, AND THAT UNCERTAINTY IS NOT IN THE ABOVE. The
   raking targets are estimated forward-chain from past PIT records, so the
   weight vector is itself an estimate with sampling error. The formula above
   conditions on the weights as if they were known. This is NOT resolved here
   and must not be presented as if it were: see UNRESOLVED_DESIGN_QUESTIONS.md,
   question Q-3. The module reports `weights_treated_as_fixed: True` on every
   result so no consumer can mistake the conditional interval for the full
   one.

Effective sample size is reported as ESS = (sum w)^2 / sum(w^2), which is what
G-XIX-3's floor is checked against.

Unaccepted specification. Synthetic validation only.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

SPEC_VERSION = "nested-mc-2"


@dataclass
class NestedResult:
    grand_mean: float
    mc_variance: float
    mc_se: float
    var_components: Dict[str, float]
    predictive_variance: float
    m: int
    k: int
    n: int
    negative_components_clamped: List[str] = field(default_factory=list)
    rev2_mc_variance: Optional[float] = None
    rev2_inflation_ratio: Optional[float] = None
    notes: List[str] = field(default_factory=list)


def _mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs)


def _svar(xs: Sequence[float]) -> float:
    """Sample variance with the n-1 denominator; 0.0 for a single item."""
    if len(xs) < 2:
        return 0.0
    m = _mean(xs)
    return sum((x - m) ** 2 for x in xs) / (len(xs) - 1)


def nested_mc(y) -> NestedResult:
    """`y[m][k][n]` -> Monte Carlo error and predictive variance components.

    Balanced design only. An unbalanced one needs the Satterthwaite-style
    coefficients rather than K and N, and this refuses instead of pretending
    the balanced algebra applies.
    """
    M = len(y)
    if M < 2:
        raise ValueError(
            "at least two parameter draws are needed; with M = 1 the "
            "parameter component is not identified and no honest Monte "
            "Carlo error can be reported for it")
    K = len(y[0])
    N = len(y[0][0])
    for m in range(M):
        if len(y[m]) != K:
            raise ValueError(f"unbalanced design: block {m} has {len(y[m])} "
                             f"scenarios, expected {K}")
        for k in range(K):
            if len(y[m][k]) != N:
                raise ValueError(
                    f"unbalanced design: cell ({m},{k}) has {len(y[m][k])} "
                    f"worlds, expected {N}")

    cell = [[_mean(y[m][k]) for k in range(K)] for m in range(M)]
    param = [_mean(cell[m]) for m in range(M)]
    grand = _mean(param)

    # --- Monte Carlo error: the first term, and only the first term --------
    s_M2 = _svar(param)
    mc_var = s_M2 / M

    # --- variance components from expected mean squares --------------------
    ms_N = (sum((y[m][k][n] - cell[m][k]) ** 2
                for m in range(M) for k in range(K) for n in range(N))
            / (M * K * (N - 1))) if N > 1 else 0.0
    ms_K = (N * sum((cell[m][k] - param[m]) ** 2
                    for m in range(M) for k in range(K))
            / (M * (K - 1))) if K > 1 else 0.0
    ms_M = K * N * s_M2

    clamped: List[str] = []
    sig_N = ms_N
    sig_K = (ms_K - ms_N) / N if K > 1 else 0.0
    sig_M = (ms_M - ms_K) / (K * N)
    for name, val in (("scenario", sig_K), ("parameter", sig_M)):
        if val < 0:
            clamped.append(f"{name}={val:.6g}")
    sig_K_c, sig_M_c = max(0.0, sig_K), max(0.0, sig_M)

    # --- what Revision 2 would have reported, for the record ---------------
    s_K2 = (sum(_svar(cell[m]) for m in range(M)) / M) if K > 1 else 0.0
    s_N2 = (sum(_svar(y[m][k]) for m in range(M) for k in range(K))
            / (M * K)) if N > 1 else 0.0
    rev2 = s_M2 / M + s_K2 / (M * K) + s_N2 / (M * K * N)

    res = NestedResult(
        grand_mean=grand, mc_variance=mc_var, mc_se=math.sqrt(max(0.0, mc_var)),
        var_components={"parameter": sig_M_c, "scenario": sig_K_c,
                        "world": sig_N,
                        "parameter_raw": sig_M, "scenario_raw": sig_K},
        predictive_variance=sig_M_c + sig_K_c + sig_N,
        m=M, k=K, n=N, negative_components_clamped=clamped,
        rev2_mc_variance=rev2,
        rev2_inflation_ratio=(rev2 / mc_var) if mc_var > 0 else None)
    if clamped:
        res.notes.append(
            "a negative variance component is a real signal that the "
            "component is near zero relative to sampling noise; the raw "
            "value is kept beside the clamped one rather than hidden")
    res.notes.append(
        "mc_variance answers how precisely the mean was located; "
        "predictive_variance answers how much the forecast spreads. They are "
        "different quantities and G-XV-1 speaks to the second while G-XV-2 "
        "and G-XV-3 speak to the first")
    return res


def which_level_to_expand(res: NestedResult) -> Dict[str, object]:
    """Which axis buys the most Monte Carlo precision per draw.

    dVar/dM, dVar/dK and dVar/dN from (2). The parameter component does not
    shrink in K or N at all, which is why a release whose parameter component
    dominates must buy parameter draws and gains nothing from more worlds.
    """
    M, K, N = res.m, res.k, res.n
    sm = res.var_components["parameter"]
    sk = res.var_components["scenario"]
    sn = res.var_components["world"]
    total = sm + sk / K + sn / (K * N)
    if total <= 0:
        return {"recommend": "NONE", "why": "no estimated variance to reduce"}
    share = {"parameter": sm / total, "scenario": (sk / K) / total,
             "world": (sn / (K * N)) / total}
    rec = max(share, key=share.get)
    return {
        "recommend": {"parameter": "INCREASE_M", "scenario": "INCREASE_K",
                      "world": "INCREASE_N"}[rec],
        "share_of_mc_variance": share,
        "why": (f"the {rec} level carries {share[rec]:.1%} of the Monte "
                f"Carlo variance of the mean; the parameter component is "
                f"divided by M alone and no number of worlds reduces it"),
    }


@dataclass
class WeightedResult:
    weighted_mean: float
    mc_variance: float
    mc_se: float
    ess: float
    ess_fraction: float
    max_weight_ratio: float
    weights_treated_as_fixed: bool = True
    notes: List[str] = field(default_factory=list)


def weighted_nested_mc(y, weights) -> WeightedResult:
    """Self-normalised weighted mean over parameter blocks, with its variance.

    `weights[m][k][n]` are non-negative world weights from Block XIX raking.
    """
    M = len(y)
    if M < 2:
        raise ValueError("at least two parameter draws are needed")
    flat_w, flat_y = [], []
    block_w, block_num = [], []
    for m in range(M):
        bw = bn = 0.0
        for k in range(len(y[m])):
            for n in range(len(y[m][k])):
                w = weights[m][k][n]
                if w < 0:
                    raise ValueError("a negative world weight is not a weight")
                flat_w.append(w)
                flat_y.append(y[m][k][n])
                bw += w
                bn += w * y[m][k][n]
        block_w.append(bw)
        block_num.append(bn)
    W = sum(flat_w)
    if W <= 0:
        raise ValueError("the weight vector sums to zero; nothing is weighted")
    mu = sum(block_num) / W

    ess = (W ** 2) / sum(w * w for w in flat_w)
    ratio = (max(flat_w) / min(w for w in flat_w if w > 0)
             if any(w > 0 for w in flat_w) else float("inf"))

    # Linearised self-normalised variance over the M independent blocks.
    Wbar = W / M
    resid = [block_num[m] - block_w[m] * mu for m in range(M)]
    var = sum(r * r for r in resid) / (M - 1) / (M * Wbar * Wbar)

    out = WeightedResult(
        weighted_mean=mu, mc_variance=var, mc_se=math.sqrt(max(0.0, var)),
        ess=ess, ess_fraction=ess / len(flat_w), max_weight_ratio=ratio)
    out.notes.append(
        "the weights are treated as FIXED. They are fitted by raking to "
        "forward-chain calibration targets, so the vector carries its own "
        "sampling error, and this interval is conditional on it. See "
        "UNRESOLVED_DESIGN_QUESTIONS.md Q-3; do not present this as the full "
        "uncertainty.")
    out.notes.append(
        f"ESS {ess:.1f} of {len(flat_w)} worlds "
        f"({ess / len(flat_w):.1%}); G-XIX-3 checks this against its floor")
    return out
