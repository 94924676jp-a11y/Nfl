"""The OAS1 hurdle, per play class, as literals. Declared BEFORE any candidate fit.

WHY THE HURDLES ARE ASYMMETRIC, AND WHY THAT IS NOT AN INCONSISTENCY

The B0-B5 chain answered the two play classes differently and the answer is
frozen in BASELINE_RESULT_FROZEN.md:

  PASS  B4 (opponent-adjusted) beats B5 with a clustered interval excluding
        zero under BOTH clusterings. Opponent information earns its place.
  RUSH  B4 is WORSE than B5 and worse than the league constant B0, and
        significantly worse than B5 under game clustering. B3 (EWMA) is
        nominally strongest but does NOT significantly beat B5.

Forcing one model form on both classes would mean either shipping an
opponent adjustment into rush where it measurably does not help, or
discarding it from pass where it measurably does. The hurdles therefore
differ by class, and that is the evidence rather than a compromise.

WHAT IS PRE-REGISTERED AND WHAT IS NOT

`B5` is the PRE-REGISTERED comparator in both classes and that has not moved.
`strongest observed baseline` was identified by reading results, so every
interval against it is CONDITIONAL ON THAT SELECTION. Those comparisons are
labelled POST_HOC_STRONGEST_BASELINE and may never be substituted for the
pre-registered B5 test.

The pass rule adds B4 as a second hurdle. That is a TIGHTENING, not a
weakening: the pre-registration already required a candidate to beat B4 as
well as B5 (`PROMOTION_CRITERION` clause (b), "it also beats B4, so the gain
is not shrinkage alone"). Naming B4 as the strongest observed pass baseline
does not change what must be cleared; it records that on pass the two
requirements happen to bind at the same estimator.
"""
from __future__ import annotations

SPEC_VERSION = 'oas1-hurdles-by-class-1'
DECLARED_AT = '2026-09-17'
DECLARED_BEFORE_ANY_CANDIDATE_FIT = True

#: The pre-registered comparator. Unchanged, both classes.
PREREGISTERED_COMPARATOR = 'B5'

#: Identified by reading the chain. Conditional on that selection.
STRONGEST_OBSERVED = {'pass': 'B4', 'rush': 'B3'}
POST_HOC_LABEL = 'POST_HOC_STRONGEST_BASELINE'
STRONGEST_IS_PREREGISTERED = False

#: Named research results. Not permanent architectural laws.
RESULT_PASS = 'PASS_OPPONENT_ADJUSTMENT_SUPPORTED'
RESULT_RUSH = 'RUSH_OPPONENT_ADJUSTMENT_NOT_SUPPORTED_YET'
RESULT_RUSH_SCOPE = (
    'a statement about the B4 specification on this frame, NOT about opponent '
    'information in rushing. A better rush specification may still prove '
    'value and would need its own pre-registration. B4 must not be shipped '
    'for rush merely because pass uses it.')

HURDLES = {
    'pass': {
        'must_beat': ('B5', 'B4'),
        'preregistered': ('B5', 'B4'),
        'post_hoc': (),
        'rule': 'OAS1 must beat B5 under the pre-registered clustered test '
                'AND beat B4, the strongest observed pass baseline, to '
                'justify its added complexity. Beating B5 while losing to B4 '
                'is a FAILURE under the pre-registered rule.',
    },
    'rush': {
        'must_beat': ('B5',),
        'preregistered': ('B5',),
        'post_hoc': ('B3',),
        'rule': 'the pre-registered hurdle remains B5. The comparison against '
                'B3 is reported and labelled POST_HOC_STRONGEST_BASELINE. If '
                'OAS1 beats B5 but loses to B3, BOTH facts are reported and '
                'no promotion conclusion is forced either way.',
    },
}

#: Reported for every comparison. Significance alone is not materiality.
PRACTICAL_EFFECT_FIELDS = (
    'mae_delta_absolute', 'mae_delta_relative', 'rmse_delta', 'crps_delta',
    'calibration_slope_before', 'calibration_slope_after',
    'calibration_slope_change', 'ci95_by_game', 'ci95_by_team',
    'downstream_team_distribution_change', 'downstream_player_distribution_change',
)

STATISTICALLY_DETECTABLE = 'STATISTICALLY_DETECTABLE'
OPERATIONALLY_MATERIAL = 'OPERATIONALLY_MATERIAL'

#: The observed spread between the worst and best baseline, per class. This is
#: the scale any candidate improvement sits inside, and it is why the two
#: labels above are reported separately.
OBSERVED_BASELINE_SPREAD = {
    'pass': {'absolute': 0.00393, 'relative': 0.0034},
    'rush': {'absolute': 0.00516, 'relative': 0.0078},
}

MATERIALITY_RULE = (
    'STATISTICALLY_DETECTABLE means the clustered interval excludes zero. '
    'OPERATIONALLY_MATERIAL is a separate judgement about football size and '
    'is NOT implied by it. Six materially different estimators are separated '
    'by under one percent MAE in both classes, so an interval excluding zero '
    'can accompany a change no downstream consumer would notice. Both are '
    'reported; neither is allowed to stand in for the other.')

CALIBRATION_DIAGNOSTIC = 'BASELINE_UNDERDISPERSION_OR_COMPRESSION'
CALIBRATION_RULE = (
    'every defined baseline calibration slope is below 1.0 -- pass 0.4432 to '
    '0.7201, rush 0.2323 to 0.6238. The baselines are NOT calibrated in '
    'response. The candidate is evaluated against this same unaltered family, '
    'and whether OAS1 improves or worsens calibration is determined AFTER the '
    'candidate runs, not before.')
