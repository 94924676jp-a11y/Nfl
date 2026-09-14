"""The Model Health contract: what the product must expose, and what it must refuse.

THE RULE THIS EXISTS TO ENFORCE, stated first because it is the reason the
module was asked for: a giant model-versus-market gap must NEVER automatically
become a top-ranked recommendation when the governing layer is under a health
warning. On 2026-09-13 the largest gaps on the card were the worst-performing
props -- rushing attempts carried a mean gap of 26.0 pp and went 3-5 -- so
ranking by gap alone promotes exactly the rows the evidence says to distrust.

A HEALTH WARNING IS NOT A SCORE. It is a named, sourced statement about a
specific layer and metric, carrying the evidence that raised it. Nothing here
computes a single number that a reader could mistake for model quality.

WHAT A WARNING DOES. It makes a metric INELIGIBLE FOR RANKING. It does not
delete the row, hide the disagreement, or alter any projection -- the number is
still published, with the warning attached, because suppressing a row the model
genuinely produced would be its own kind of dishonesty.
"""
from __future__ import annotations

import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

# 1.1.0 on coordinator ruling, 2026-09-14. ADDITIVE: `FIELDS` gained four
# entries (n_zero_completed_rows, n_game_clusters, outcome_selection_basis,
# market_selection_basis) and `WARNINGS` gained two
# (OUTCOME_CONDITIONAL_SELECTION, MARKET_STATS_OUTCOME_SELECTED). No existing
# field changed meaning and none was removed, so this is NOT the 1.0.0 -> 2.0.0
# break that `same_day_retrospective` correctly took when its scored SET
# changed. Leaving the string at 1.0.0 would have been worse than either
# choice: a consumer keying on 1.0.0 would read a different schema under the
# same name, which is the drift this workstream exists to stop.
# `MODEL_HEALTH_2026-09-13.json` is published quoting 1.0.0 and is NOT
# rewritten; CORRECTIONS.json records what changed under that name.
SPEC_VERSION = 'model-health/1.1.0'

# The fields the API is contracted to expose per metric.
FIELDS = (
    'metric', 'layer', 'n_scored', 'mean_signed_error', 'mean_abs_error',
    'mean_crps', 'coverage_50', 'coverage_80', 'coverage_90', 'pit_mean',
    'n_model_below_actual', 'n_model_above_actual',
    'market_n_graded', 'market_pct_under', 'market_hit_rate',
    'market_mean_model_probability', 'market_mean_novig_probability',
    'market_mean_gap_pp',
    'n_contaminated_rows', 'n_refused_rows',
    # HOW THE SCORED SET WAS CHOSEN travels with every row, because a
    # statistic computed on rows selected after the outcome was known is not
    # the same kind of object as one computed on a complete set, and nothing
    # in the numbers themselves reveals the difference.
    'n_zero_completed_rows', 'n_game_clusters',
    'outcome_selection_basis', 'market_selection_basis',
    'warnings', 'ranking_eligible',
)

# The only selection basis that is not itself a warning.
SELECTION_COMPLETE = 'COMPLETE_INCLUDING_ZERO_BY_COMPLETION'

# Named warnings. Each is a CONDITION on measured evidence, never a judgement.
WARNINGS = {
    'COVERAGE_BELOW_NOMINAL':
        'realised interval coverage is below the nominal level at 50% or 80%. '
        'The forecast is narrower than the outcomes it faced.',
    'DIRECTIONAL_SKEW':
        'the model-selected side is one-sided beyond 70% across graded market '
        'comparisons, which is a property of the model before it is a property '
        'of the market.',
    'MARKET_GAP_ANTICALIBRATED':
        'larger model-versus-market probability gaps did NOT produce a higher '
        'realised hit rate. Ranking by gap is therefore ranking by error.',
    'SELECTED_SIDE_BELOW_EVEN':
        'the model-selected side won less than half of its graded, non-push '
        'comparisons.',
    'LAYER_SPECIFICATION_DEFECT':
        'an accepted audit has classified this layer as carrying a '
        'specification defect.',
    'CONTAMINATED_STRATUM':
        'rows for this metric sit in a contaminated stratum and are not '
        'evidence about the layer.',
    'OUTCOME_CONDITIONAL_SELECTION':
        'the scored set for this metric was chosen using the realised '
        'outcome, or its selection basis was not declared. Which forecasts '
        'get graded must be decided by what existed at forecast time. A '
        'statistic from such a set describes the selection as much as the '
        'model and may not rank anything.',
    'MARKET_STATS_OUTCOME_SELECTED':
        'the market comparison for this metric was graded on a set chosen '
        'using the realised outcome, or its selection basis was not '
        'declared. Dropping the players who recorded nothing removes exactly '
        'the comparisons a positive-volume forecast loses, so the hit rate '
        'is measured on survivors.',
}

# Thresholds, declared here rather than inline so they are reviewable.
SKEW_THRESHOLD = 0.70
MIN_N_FOR_A_WARNING = 8


def evaluate(metric, outcome_stats=None, market_stats=None, buckets=None,
             declared_defects=(), n_contaminated=0, n_refused=0,
             n_zero_completed=0, n_game_clusters=None,
             outcome_selection_basis=None, market_selection_basis=None,
             carried_warnings=()):
    """Health for one metric. Returns the contract row, warnings included.

    SELECTION IS PART OF THE EVIDENCE AND IS REQUIRED, NOT OPTIONAL. The
    2026-09-13 artifact reported `receiving/targets` as the single
    ranking-eligible metric on a coverage figure computed after every row
    whose realised value was zero had been deleted. Nothing in the contract
    could have caught that, because the contract never asked how the rows
    were chosen. It asks now, and an undeclared basis is treated as an
    outcome-conditional one: silence is not a clean bill.
    """
    w = []
    if str(outcome_selection_basis or 'UNDECLARED') != SELECTION_COMPLETE:
        w.append('OUTCOME_CONDITIONAL_SELECTION')
    o = outcome_stats or {}
    m = market_stats or {}
    n_o = int(o.get('n') or 0)
    n_m = int(m.get('n') or 0)
    if n_o >= MIN_N_FOR_A_WARNING:
        if (o.get('coverage_50') is not None and o['coverage_50'] < 0.50) or \
           (o.get('coverage_80') is not None and o['coverage_80'] < 0.80):
            w.append('COVERAGE_BELOW_NOMINAL')
    if n_m and str(market_selection_basis or 'UNDECLARED') != SELECTION_COMPLETE:
        w.append('MARKET_STATS_OUTCOME_SELECTED')
    if n_m >= MIN_N_FOR_A_WARNING:
        pu = m.get('pct_under')
        if pu is not None and (pu >= SKEW_THRESHOLD or pu <= 1 - SKEW_THRESHOLD):
            w.append('DIRECTIONAL_SKEW')
        hr = m.get('hit_rate_excl_push')
        if hr is not None and hr < 0.50:
            w.append('SELECTED_SIDE_BELOW_EVEN')
    if buckets:
        # ANTICALIBRATION: does a bigger gap buy a better hit rate? Compared
        # only across buckets that carry enough rows to mean anything.
        usable = [(k, v) for k, v in buckets.items()
                  if (v or {}).get('n', 0) >= MIN_N_FOR_A_WARNING
                  and v.get('hit_rate_excl_push') is not None]
        if len(usable) >= 2:
            order = ['<5pp', '5-10pp', '10-20pp', '20-30pp', '>30pp']
            usable.sort(key=lambda x: order.index(x[0])
                        if x[0] in order else 99)
            lo = usable[0][1]['hit_rate_excl_push']
            hi = usable[-1][1]['hit_rate_excl_push']
            if hi <= lo:
                w.append('MARKET_GAP_ANTICALIBRATED')
    for dd in declared_defects or ():
        w.append('LAYER_SPECIFICATION_DEFECT')
        break
    if n_contaminated:
        w.append('CONTAMINATED_STRATUM')
    # A WARNING THIS CALL CANNOT RECOMPUTE IS CARRIED, NOT DROPPED.
    #
    # Regenerating an artifact without the inputs a previous warning was
    # raised from must never be the reason a metric becomes rankable again. A
    # rebuild that silently loosens a gate is worse than no rebuild.
    for cw in carried_warnings or ():
        if cw not in WARNINGS:
            raise ValueError(
                f'MODEL_HEALTH_UNKNOWN_CARRIED_WARNING: {cw!r} is not in the '
                f'declared vocabulary. A warning with no meaning attached is '
                f'not a warning.')
        w.append(cw)
    w = list(dict.fromkeys(w))
    return {
        'metric': metric, 'layer': str(metric).split('/')[0],
        'n_scored': n_o,
        'mean_signed_error': o.get('mean_signed_error'),
        'mean_abs_error': o.get('mean_abs_error'),
        'mean_crps': o.get('mean_crps'),
        'coverage_50': o.get('coverage_50'),
        'coverage_80': o.get('coverage_80'),
        'coverage_90': o.get('coverage_90'),
        'pit_mean': o.get('pit_mean'),
        'n_model_below_actual': o.get('n_model_below_actual'),
        'n_model_above_actual': o.get('n_model_above_actual'),
        'market_n_graded': n_m,
        'market_pct_under': m.get('pct_under'),
        'market_hit_rate': m.get('hit_rate_excl_push'),
        'market_mean_model_probability': m.get('mean_model_probability'),
        'market_mean_novig_probability': m.get('mean_market_novig_probability'),
        'market_mean_gap_pp': m.get('mean_probability_gap_pp'),
        'n_contaminated_rows': int(n_contaminated),
        'n_refused_rows': int(n_refused),
        'n_zero_completed_rows': int(n_zero_completed),
        # ROWS ARE NOT A SAMPLE SIZE. n_scored counts player-game-metric rows;
        # the unit these errors vary in is the game. Both are published so a
        # reader cannot mistake one for the other.
        'n_game_clusters': (int(n_game_clusters)
                            if n_game_clusters is not None else None),
        'outcome_selection_basis': str(outcome_selection_basis or 'UNDECLARED'),
        'market_selection_basis': (str(market_selection_basis or 'UNDECLARED')
                                   if n_m else None),
        'warnings': w,
        'ranking_eligible': not w,
        'warning_meanings': {x: WARNINGS[x] for x in w},
    }


def assert_ranking_admissible(rows, health):
    """Strip from a ranked table any row whose metric is under a warning.

    THE GATE. This is the rule the product exists to enforce. A row removed
    here is NOT deleted from the comparison -- it is removed from the RANKING,
    and the reason travels with it, because a large disagreement produced by a
    layer under a health warning is evidence about the layer, not a candidate.
    """
    by_metric = {h['metric']: h for h in health}
    kept, blocked = [], []
    for r in rows:
        h = by_metric.get(r.get('metric'))
        if h and not h['ranking_eligible']:
            blocked.append({**r, 'blocked_by_health': h['warnings']})
        else:
            kept.append(r)
    return kept, blocked
