"""The full scorecard. Rule 005 made executable.

"Get the correlation higher" is a target a model can hit while getting worse.
This module makes single-metric reporting structurally awkward and
single-metric *comparison* impossible.

Three things it refuses, each from a real failure:

1. Reporting r without SD ratio and calibration slope. Those three are
   ALGEBRAICALLY ONE FACT -- slope = r x SD_actual / SD_predicted, which
   reproduces V7's recorded 0.6101 exactly. Quoting one is not a partial view,
   it is a misleading one: inflating dispersion with no gain in signal
   "improves" the SD ratio while driving slope away from 1.0.

2. Comparing across engine fingerprints. Results under different fingerprints
   are not evidence about each other.

3. Declaring a difference without the power to detect it. A comparison whose
   sample cannot resolve the effect returns UNDERPOWERED, not "no
   improvement" -- V7's 251-game set needs ~1,131 clustered games to detect
   r 0.11 -> 0.25, and reading that as "the change did not help" is the error
   this guard exists to prevent.
"""
from __future__ import annotations

import math
from collections import defaultdict
from typing import Sequence

from .outcome import Cause, Outcome, State

# The three that must always travel together, because they are one fact.
LINKED = ('pearson_r', 'sd_ratio', 'calibration_slope')


def _mean(x):
    return sum(x) / len(x)


def _sd(x):
    if len(x) < 2:
        return 0.0
    m = _mean(x)
    return math.sqrt(sum((v - m) ** 2 for v in x) / (len(x) - 1))


def _pearson(a, b):
    n = len(a)
    if n < 2:
        return 0.0
    ma, mb = _mean(a), _mean(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    da = math.sqrt(sum((x - ma) ** 2 for x in a))
    db = math.sqrt(sum((y - mb) ** 2 for y in b))
    return num / (da * db) if da and db else 0.0


class DesignEffectRetired(RuntimeError):
    """design_effect was retired. Calling it is the error, not a fallback."""


def design_effect(clusters: Sequence) -> float:
    """RETIRED by owner ruling 2026-09-04. Raises; never returns a number.

    WHAT IT USED TO COMPUTE, preserved so history is not rewritten. The body is
    kept verbatim below as RETIRED_cluster_size_imbalance. It computed
    sum(s^2) * m / n^2, which is the Kish factor divided by the mean cluster
    size, and which is exactly 1.0 for ANY balanced clustering:

        10 dates x 13 games, balanced   -> 1.0000   (Kish sum(s^2)/n = 13.0)
        100 clusters x 2, balanced      -> 1.0000   (Kish = 2.0)
        130 singletons, no clustering   -> 1.0000   (Kish = 1.0)
        3 singletons + one of 127       -> 3.8182   (Kish = 124.09)

    So it measured the relative VARIABILITY OF CLUSTER SIZES, not clustering,
    and MLB date blocks are close to balanced -- in precisely the case it
    existed for, it reported no clustering and resolvable_band did not widen.
    Its docstring said "the simple Kish factor from cluster sizes"; it was not
    that either.

    WHY IT WAS NOT REPAIRED. Changing the body to sum(s^2)/n returns the Kish
    factor, which is still not a design effect. A design effect is
    Var_actual / Var_iid, approximately 1 + (s_bar - 1) * rho, and rho -- the
    intraclass correlation -- must be estimated from the data. No function
    whose only argument is a list of cluster labels can return a design effect
    even in principle. Repairing it would have left the name wrong in a subtler
    way.

    WHAT TO USE INSTEAD. Take the widening from a validated resampling
    procedure directly, which produces the interval without needing a deff at
    all; or use stopping.design_effect_from_se_ratio, which derives a variance
    inflation from two MEASURED standard errors and is correct.

    Absence is refused rather than defaulted to 1.0, because defaulting
    understates uncertainty, which is the unsafe direction.
    """
    raise DesignEffectRetired(
        'DESIGN_EFFECT_RETIRED: design_effect(clusters) was retired by owner '
        'ruling 2026-09-04 because it returned 1.0 for any balanced '
        'clustering. A design effect requires an intraclass correlation and '
        'cannot be computed from cluster labels alone. Use a validated '
        'resampling procedure, or stopping.design_effect_from_se_ratio on two '
        'measured standard errors. Historical behaviour is preserved for '
        'forensics as RETIRED_cluster_size_imbalance.')


def RETIRED_cluster_size_imbalance(clusters: Sequence) -> float:
    """The retired body, verbatim, kept so a past number can be reproduced.

    This is NOT a design effect and must never be used as one. It exists so
    that a figure computed before 2026-09-04 can be re-derived and classified,
    which is what "do not rewrite history" requires.
    """
    if not clusters:
        return 1.0
    sizes = defaultdict(int)
    for c in clusters:
        sizes[c] += 1
    n = sum(sizes.values())
    m = list(sizes.values())
    if n == 0 or len(m) == 0:
        return 1.0
    return sum(s * s for s in m) * len(m) / (n * n) if n else 1.0


def detectable_r_difference(n: int, base_r: float, deff: float = 1.0,
                            power: float = 0.80) -> float:
    """The smallest r a sample this size could distinguish from base_r.

    Fisher-z, two-sided alpha .05. deff divides the effective n, so clustering
    makes the detectable difference larger -- which is the honest direction.
    """
    n_eff = max(4.0, n / max(deff, 1e-9))
    z_needed = 2.802 if power >= 0.80 else 1.96
    se = 1.0 / math.sqrt(n_eff - 3.0)
    return math.tanh(math.atanh(base_r) + z_needed * se)


def resolvable_band(*, n: int, base_r: float, deff: float = 1.0,
                    power: float = 0.80) -> tuple:
    """The two-sided band this sample cannot resolve, as (lo, hi).

    `detectable_r_difference` gives only the UPPER edge, and reading a
    comparison off one edge is what made a collapse from r 0.30 to 0.02 report
    as "we could not tell" at z = 12.94. Anything strictly inside this band is
    genuinely unresolved; anything at or beyond an edge is a direction.

    Symmetric in FISHER-Z space, not in r. r is bounded at 1 and its variance
    depends on its own value, so a band symmetric in r would be wider on one
    side in the only units that matter. The test asserts the z-symmetry rather
    than the r-symmetry for that reason.
    """
    n_eff = max(4.0, n / max(deff, 1e-9))
    se = 1.0 / math.sqrt(n_eff - 3.0)
    z_needed = 2.802 if power >= 0.80 else 1.96
    z = math.atanh(base_r)
    return math.tanh(z - z_needed * se), math.tanh(z + z_needed * se)


def resolved_z(*, n: int, base_r: float, cand_r: float,
               deff: float = 1.0) -> float:
    """How many standard errors apart the two correlations are.

    Reported so a verdict carries the strength of its own evidence rather than
    only its direction.
    """
    n_eff = max(4.0, n / max(deff, 1e-9))
    se = 1.0 / math.sqrt(n_eff - 3.0)
    return (math.atanh(cand_r) - math.atanh(base_r)) / se


def score(predicted: Sequence[float], actual: Sequence[float], *,
          fingerprint: str, label: str,
          date_clusters: Sequence = (), team_clusters: Sequence = (),
          deff: float | None = None) -> Outcome:
    """The whole scorecard, or nothing."""
    if len(predicted) != len(actual):
        return Outcome.blocked(
            'SCORECARD_LENGTH_MISMATCH',
            f'{len(predicted)} predictions against {len(actual)} actuals.', cause=Cause.DATA)
    n = len(predicted)
    if n < 3:
        return Outcome.blocked(
            'SCORECARD_TOO_FEW',
            f'n={n} cannot support a scorecard. An underpowered number is not '
            f'a small result, it is not a result.', cause=Cause.DATA)

    sd_p, sd_a = _sd(predicted), _sd(actual)
    r = _pearson(predicted, actual)
    resid = [a - p for p, a in zip(predicted, actual)]
    mae = _mean([abs(e) for e in resid])
    rmse = math.sqrt(_mean([e * e for e in resid]))
    slope = (r * sd_a / sd_p) if sd_p else float('nan')

    # No design effect is computed from cluster labels. See design_effect's
    # docstring: the retired function returned 1.0 for balanced clustering, and
    # the quantity cannot be recovered from labels in any case. `deff` is an
    # explicit caller-supplied argument or it is absent, and absent means
    # UNAVAILABLE rather than 1.0 -- defaulting to 1.0 understates uncertainty.
    deff = None if deff is None else float(deff)
    if deff is not None and deff < 1.0:
        return Outcome.blocked(
            'DESIGN_EFFECT_IMPLAUSIBLE',
            f'deff={deff} is below 1.0. Clustering cannot reduce variance '
            f'below independence.', cause=Cause.DATA)

    card = {
        'label': label,
        'fingerprint': fingerprint,
        'n': n,
        'mean_predicted': _mean(predicted),
        'mean_actual': _mean(actual),
        'bias': _mean(predicted) - _mean(actual),
        'sd_predicted': sd_p,
        'sd_actual': sd_a,
        # the three that travel together
        'pearson_r': r,
        'sd_ratio': (sd_p / sd_a) if sd_a else float('nan'),
        'calibration_slope': slope,
        'r_squared': r * r,
        'mae': mae,
        'rmse': rmse,
        'design_effect': deff,
        'deff_source': 'CALLER_SUPPLIED' if deff is not None
                       else 'UNAVAILABLE_RETIRED',
        'n_effective': (n / deff) if deff is not None else None,
        'n_date_clusters': len(set(date_clusters)) if date_clusters else None,
        'n_team_clusters': len(set(team_clusters)) if team_clusters else None,
        # Refused rather than computed at deff=1.0. A detectable difference
        # computed as though observations were independent is SMALLER than the
        # truth, so a candidate would look resolvable when it is not.
        'detectable_r_at_80_power': (detectable_r_difference(n, r, deff)
                                     if deff is not None else None),
    }
    return Outcome.ok('SCORECARD', card,
                      detail=f'{label}: n={n}, r={r:.4f}, sd_ratio='
                             f'{card["sd_ratio"]:.4f}, slope={slope:.4f}')


def headline(card: dict, metrics: Sequence[str]) -> Outcome:
    """Quote metrics from a scorecard -- refusing to split the linked three."""
    asked = set(metrics)
    if asked & set(LINKED) and not asked >= set(LINKED):
        missing = sorted(set(LINKED) - asked)
        return Outcome.blocked(
            'LINKED_METRICS_SPLIT',
            f'{sorted(asked & set(LINKED))} cannot be quoted without '
            f'{missing}. slope = r x SD_actual / SD_predicted, so these are '
            f'one measurement in three forms; quoting a subset is misleading '
            f'rather than partial. Inflating dispersion with no gain in signal '
            f'"improves" the SD ratio while slope moves away from 1.0.', cause=Cause.GOVERNANCE)
    unknown = sorted(asked - set(card))
    if unknown:
        return Outcome.blocked(
            'SCORECARD_UNKNOWN_METRIC',
            f'{unknown} are not on this scorecard.', cause=Cause.GOVERNANCE)
    return Outcome.ok('HEADLINE', {k: card[k] for k in sorted(asked)})


def compare(baseline: dict, candidate: dict) -> Outcome:
    """Baseline versus candidate, with power respected.

    Returns DEFERRED -- not FAIL, and never PASS -- when the sample cannot
    resolve the difference. "We could not tell" is a real answer and is
    routinely misread as "it did not work".
    """
    if baseline.get('fingerprint') == candidate.get('fingerprint'):
        return Outcome.blocked(
            'SAME_FINGERPRINT',
            'baseline and candidate carry the same engine fingerprint, so this '
            'is not a comparison of two engines.', cause=Cause.GOVERNANCE)
    n = min(baseline['n'], candidate['n'])
    # Absence is refused, not defaulted. Defaulting to 1.0 here is precisely
    # how the retired design_effect could keep influencing inference after
    # being retired: a missing key would silently become "independent".
    b_deff, c_deff = baseline.get('design_effect'), candidate.get('design_effect')
    if b_deff is None or c_deff is None:
        return Outcome.blocked(
            'DEPENDENCE_UNAVAILABLE',
            'one or both scorecards carry no design effect, so the resolvable '
            'band cannot be computed. Games are not independent observations '
            'and treating a missing deff as 1.0 would understate the band in '
            'the unsafe direction. Supply a deff from a validated resampling '
            'procedure, or from measured standard errors.',
            cause=Cause.GOVERNANCE)
    deff = max(float(b_deff), float(c_deff))
    need = detectable_r_difference(n, baseline['pearson_r'], deff)
    got = candidate['pearson_r']

    moved = {k: candidate[k] - baseline[k]
             for k in ('pearson_r', 'sd_ratio', 'mae', 'rmse', 'bias')
             if k in baseline and k in candidate}
    # Calibration must move TOWARD 1.0, not merely change.
    cal_base = abs(baseline['calibration_slope'] - 1.0)
    cal_cand = abs(candidate['calibration_slope'] - 1.0)
    moved['calibration_distance_from_1'] = cal_cand - cal_base

    ev = {'deltas': moved, 'r_needed_for_detection': need,
          'r_candidate': got, 'n': n, 'design_effect': deff}

    # The failure to catch is dispersion bought WITHOUT signal: the SD ratio
    # rises while r does not. That is a model spreading its predictions
    # without knowing more, which is confidently wrong more often.
    #
    # An earlier version of this function also failed a candidate whose slope
    # moved away from 1.0 while r ROSE. That was wrong, and the test caught it:
    # slope is fixable by an affine rescale, and a rescale does not change r.
    # Refusing real new signal over a trivially correctable presentation
    # problem is exactly the "reject the improvement" mirror of cherry-picking.
    r_gain = got - baseline['pearson_r']
    sd_gain = candidate['sd_ratio'] - baseline['sd_ratio']
    if sd_gain > 1e-9 and r_gain <= 1e-9:
        return Outcome.fail(
            'DISPERSION_WITHOUT_SIGNAL',
            f'SD ratio rose {baseline["sd_ratio"]:.4f} -> '
            f'{candidate["sd_ratio"]:.4f} while r did not improve '
            f'({baseline["pearson_r"]:.4f} -> {got:.4f}). Spreading '
            f'predictions without knowing more makes the forecast confidently '
            f'wrong more often; slope moved '
            f'{baseline["calibration_slope"]:.4f} -> '
            f'{candidate["calibration_slope"]:.4f}.', **ev)
    ev['recalibration_required'] = cal_cand > cal_base

    # Directive section 4D: BETTER / WORSE / INCONCLUSIVE are three answers.
    # The band has two edges, and reading only the upper one is what made a
    # collapse from r 0.30 to 0.02 report as "we could not tell" at z = 12.94.
    lo, hi = resolvable_band(n=n, base_r=baseline['pearson_r'], deff=deff)
    z = resolved_z(n=n, base_r=baseline['pearson_r'], cand_r=got, deff=deff)
    ev['resolvable_band'] = [lo, hi]
    ev['resolved_z'] = z

    if got <= lo:
        ev['verdict'] = 'WORSE'
        return Outcome.fail(
            'CANDIDATE_WORSE',
            f'r fell {baseline["pearson_r"]:.4f} -> {got:.4f}, at or below the '
            f'{lo:.4f} lower edge this sample can resolve (n={n}, design '
            f'effect {deff:.2f}), z={z:.2f}. This is a DETECTED decline, not an '
            f'unresolved one: reporting it as "we could not tell" would leave a '
            f'harmful mechanism accumulating the forward sample instead of '
            f'being rejected.', **ev)

    if got < hi:
        ev['verdict'] = 'INCONCLUSIVE'
        return Outcome.deferred(
            'UNDERPOWERED',
            f'candidate r={got:.4f}; this sample (n={n}, design effect '
            f'{deff:.2f}) can only resolve outside [{lo:.4f}, {hi:.4f}] at 80% '
            f'power, and z={z:.2f}. That is "we could not tell", NOT "it did '
            f'not work". More out-of-sample games are owed before this can be '
            f'decided.', owed=int(n), **ev)

    note = ('; slope is off and an affine recalibration is required before '
            'use, which does not change r' if cal_cand > cal_base else '')
    ev['verdict'] = 'BETTER'
    return Outcome.ok('CANDIDATE_BETTER', ev,
                      detail=f'r {baseline["pearson_r"]:.4f} -> {got:.4f}, '
                             f'above the {hi:.4f} upper edge resolvable at this '
                             f'n, z={z:.2f}{note}')
