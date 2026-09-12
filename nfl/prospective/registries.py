"""Stages 10 and 12: the frozen benchmark registry and the candidate registry.

TWO RULES THAT ARE ENFORCED RATHER THAN STATED

1. A PROFESSIONAL PROJECTION IS A BENCHMARK, NEVER A TRAINING LABEL. Training
   on someone else's projection teaches the model to imitate a forecaster, not
   to forecast, and the resulting agreement is not evidence.

2. A FINAL FILE IS NOT A POINT-IN-TIME CAPTURE. If historical as-of pro
   projections are unavailable, the honest record is that they are unavailable.
   Backfilling a final version and treating it as contemporaneous manufactures
   the exact evidence the prospective protocol exists to require.
"""
from __future__ import annotations

import dataclasses
import pathlib
import sys
from typing import Optional

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402


@dataclasses.dataclass(frozen=True)
class Benchmark:
    name: str
    version: str
    source: str
    kind: str                    # 'static_baseline'|'accepted_model'|
                                 # 'frozen_candidate'|'external_projection'
    eligibility: str
    metric_set: tuple
    seasons: tuple
    comparison_rule: str
    captured_at: Optional[str] = None
    retrieved_at: Optional[str] = None
    may_be_training_label: bool = False
    point_in_time_available: Optional[bool] = None
    note: str = ''


BENCHMARKS = (
    Benchmark(
        name='position_pool_mean', version='1', source='internal',
        kind='static_baseline',
        eligibility='ELIGIBLE -- prior-season pooled positional mean; consumes '
                    'no 2026 outcome',
        metric_set=('crps', 'mae', 'rmse', 'r', 'coverage'),
        seasons=(2026,), comparison_rule='arm A only; never pooled with B or C',
        note='The floor every candidate must clear. RC1 measured that the '
             'closed conversion ladder beats it by 0.96% of CRPS.'),
    Benchmark(
        name='player_shrinkage_L1', version='1', source='internal',
        kind='static_baseline',
        eligibility='ELIGIBLE -- prior-only shrinkage toward the positional pool',
        metric_set=('crps', 'mae', 'rmse', 'r', 'coverage'),
        seasons=(2026,), comparison_rule='arm A only',
        note='The accepted receiving baseline`s own rule.'),
    Benchmark(
        name='p4c_carry_allocation', version='C', source='internal',
        kind='accepted_model',
        eligibility='ELIGIBLE -- accepted production model, unchanged',
        metric_set=('crps', 'mae', 'rmse', 'r', 'coverage'),
        seasons=(2026,), comparison_rule='arm A or B by its frozen rule',
        note='ACCEPTED. Not altered by any 2026 work.'),
    Benchmark(
        name='stage2_ewma_hl2', version='1', source='internal',
        kind='accepted_model',
        eligibility='ELIGIBLE -- accepted participation model',
        metric_set=('crps', 'mae', 'rmse', 'r'),
        seasons=(2026,), comparison_rule='arm A or B by its frozen rule'),
    Benchmark(
        name='ABC_MPR', version='frozen', source='internal',
        kind='frozen_candidate',
        eligibility='FROZEN PROSPECTIVE CANDIDATE -- NOT PROMOTED. May be '
                    'evaluated prospectively; may never be promoted on '
                    '2022-2025 evidence.',
        metric_set=('crps', 'mae', 'rmse', 'r', 'coverage'),
        seasons=(2026,), comparison_rule='arm B; its freeze spec fixes the rule',
        note='Freeze spec nfl/research/p4f/CANDIDATE_FREEZE_ABC_MPR.md; '
             'identity gate nfl/research/repro/ABC_MPR_IDENTITY.json'),
    Benchmark(
        name='professional_projection_consensus', version='UNAVAILABLE',
        source='EXTERNAL -- vendor, not held',
        kind='external_projection',
        eligibility='NOT ELIGIBLE -- no point-in-time capture exists',
        metric_set=('crps', 'mae', 'rmse', 'r'),
        seasons=(), comparison_rule='BENCHMARK ONLY, never a training label',
        captured_at=None, retrieved_at=None,
        may_be_training_label=False, point_in_time_available=False,
        note='No historical as-of professional projection is held by this '
             'project. A final published version is NOT a contemporaneous '
             'capture and MAY NOT be backfilled as one. Registered as '
             'unavailable so its absence is visible rather than inferred.'),
)

BY_NAME = {b.name: b for b in BENCHMARKS}


def check_benchmark(name: str) -> Outcome:
    b = BY_NAME.get(name)
    if b is None:
        return Outcome.blocked('BENCHMARK_NOT_REGISTERED', f'{name!r}',
                               cause=Cause.GOVERNANCE)
    if b.kind == 'external_projection' and b.may_be_training_label:
        return Outcome.fail(
            'PROJECTION_AS_TRAINING_LABEL',
            f'{name}: a professional projection is registered as a training '
            f'label. Training on another forecaster teaches imitation, and the '
            f'resulting agreement is not evidence.')
    if b.point_in_time_available is False and b.captured_at:
        return Outcome.fail(
            'BACKFILLED_BENCHMARK',
            f'{name}: declared to have no point-in-time capture yet carries a '
            f'captured_at. A final file presented as contemporaneous '
            f'manufactures the evidence the prospective protocol requires.')
    if b.kind == 'external_projection' and b.point_in_time_available is not True:
        return Outcome.deferred(
            'BENCHMARK_UNAVAILABLE_PIT',
            f'{name}: registered, and NOT eligible -- no point-in-time capture '
            f'exists. Owed until one is captured prospectively; never '
            f'backfilled.', owed=name)
    return Outcome.ok('BENCHMARK_ELIGIBLE', value=b.name, detail=b.eligibility)


# ==========================================================================
# Stage 12: prospective candidate registry
# ==========================================================================

CANDIDATES = {
    'Q9_TARGET_HURDLE': {
        'status': 'FROZEN PROSPECTIVE CANDIDATE -- SHADOW ONLY',
        'promoted': False,
        'prospective_candidate': True,
        'shadow_only': True,
        'frozen_prospective': True,
        'freeze_artifact': 'nfl/research/q9b/Q9_PROSPECTIVE_FREEZE.json',
        'identity_gate': ('nfl/prospective/q9shadow/'
                          'Q9_PROSPECTIVE_CANDIDATE.json'),
        'mechanism': ('two-stage target hurdle: P(targeted | appears) from a '
                      'pregame-only logistic stage, then a one-target floor '
                      'and a multinomial remainder that reconciles exactly '
                      'to the team target budget'),
        'allowed_inputs': ('those named in nfl.research.q9.hurdle.FEATURE_NAMES '
                           'and no others; appearance is UPSTREAM and separate'),
        # WRITTEN OUT RATHER THAN IMPORTED, DELIBERATELY. This is a
        # governance module and importing the research stack into it to read
        # one tuple would drag numpy and the whole panel loader behind it.
        # The copy is kept honest by a test that asserts it equals
        # `nfl.research.q9.hurdle.FORBIDDEN_INPUTS` exactly, so drift is a
        # failing check rather than a stale comment.
        'prohibited_inputs': ['realized', 'realised', 'actual_targets',
                              'weekly_rosters', 'roster_status',
                              'inactive_list', 'spread', 'vegas',
                              'total_line', 'odds', 'postgame', 'final_'],
        'prohibited_inputs_source': 'nfl.research.q9.hurdle.FORBIDDEN_INPUTS',
        'first_admissible_evaluation': (
            'the first shadow forecast sealed under '
            'nfl.prospective.q9shadow.seal for a 2026 REG game whose kickoff '
            'is after G0A is discharged, with written_at strictly before that '
            'kickoff'),
        'may_promote_on_2022_2025': False,
        'why_not': ('2022-2025 selected this mechanism: the Q8 attribution '
                    'audit, the zero-mass decomposition and the Q9 ordering '
                    'all came out of those seasons. They cannot confirm it.'),
        'shadow_only_means': (
            'the candidate is evaluated alongside production and influences '
            'no published number, no board and no decision. It has no '
            'production call site outside nfl/prospective/q9shadow.'),
        'promotion_rulebook': 'nfl/prospective/PROSPECTIVE_EVALUATION_PROTOCOL.md',
        'known_conflict_to_resolve_before_promotion': (
            'protocol S9.6 requires RANDOMIZED PIT not worse. Q9B measured '
            'MID-PIT (chi2 8821 -> 8913, worse). Mid-PIT is not the quantity '
            'the rule names, so the rule is not yet evaluable on the measured '
            'evidence; the prospective harness emits randomized PIT so that '
            'it becomes evaluable.'),
    },
    'ABC_MPR': {
        'status': 'FROZEN PROSPECTIVE CANDIDATE',
        'promoted': False,
        'freeze_artifact': 'nfl/research/p4f/CANDIDATE_FREEZE_ABC_MPR.md',
        'identity_gate': 'nfl/research/repro/ABC_MPR_IDENTITY.json',
        'allowed_inputs': 'those named in the freeze spec, and no others',
        'prohibited_inputs': ['2026 outcomes beyond the frozen prequential rule',
                              'market or DFS data', 'FTN', 'PFR-restricted',
                              'weekly_rosters.status'],
        'first_admissible_evaluation': 'the first arm-B forecast written under '
                                       'the frozen rule after G0A is satisfied',
        'may_promote_on_2022_2025': False,
        'why_not': '2022-2025 are heavily mined development data',
    },
    'participation_ewma_hl1': {
        'status': 'DEVELOPMENT CANDIDATE ONLY',
        'promoted': False,
        'frozen_prospective': False,
        'note': 'NOT a frozen prospective candidate. Owner authorization would '
                'be required to make it one. Stage 2 ewma_hl2 remains the '
                'accepted participation model.',
        'may_promote_on_2022_2025': False,
    },
    'rc2_R1_draw_centring': {
        'status': 'DEVELOPMENT ONLY -- FAILED its predeclared acceptance',
        'promoted': False,
        'frozen_prospective': False,
        'evidence': 'RC2: improved CRPS +0.226%, MAE, r +0.0012 and randomized '
                    'PIT 178.9 -> 135.9 together, and cut bias 2.18 -> 1.67, '
                    'but the predeclared bar was |bias| < 1.00.',
        'note': 'Recorded because a near miss that is not written down becomes '
                'a rediscovery. The bar was NOT moved to admit it.',
        'may_promote_on_2022_2025': False,
    },
}


def check_candidate(name: str) -> Outcome:
    c = CANDIDATES.get(name)
    if c is None:
        return Outcome.blocked('CANDIDATE_NOT_REGISTERED', f'{name!r}',
                               cause=Cause.GOVERNANCE)
    if c.get('promoted'):
        return Outcome.fail(
            'CANDIDATE_MARKED_PROMOTED',
            f'{name} is marked promoted. Promotion is an owner decision and '
            f'cannot be recorded by a registry edit.')
    if c.get('may_promote_on_2022_2025'):
        return Outcome.fail(
            'MINED_DATA_PROMOTION_PATH',
            f'{name} declares it may promote on 2022-2025, which are heavily '
            f'mined development data.')
    # A SHADOW CANDIDATE MUST STAY SHADOW. `shadow_only` is not decoration:
    # it is the claim that the candidate influences no published number, and a
    # registry that let it sit beside `promoted` or beside a missing
    # `prospective_candidate` flag would make the phrase unfalsifiable.
    if c.get('shadow_only') and not c.get('prospective_candidate'):
        return Outcome.fail(
            'SHADOW_WITHOUT_PROSPECTIVE_STATUS',
            f'{name} is marked shadow_only but not prospective_candidate. A '
            f'shadow arm that is not registered as a prospective candidate is '
            f'running without the rulebook that makes its evidence countable.')
    if c.get('prospective_candidate') and not c.get('freeze_artifact'):
        return Outcome.fail(
            'PROSPECTIVE_CANDIDATE_WITHOUT_FREEZE',
            f'{name} is a prospective candidate with no freeze artifact. A '
            f'candidate whose identity was not frozen before the first '
            f'forecast cannot be shown later to be the thing that was '
            f'evaluated.')
    return Outcome.ok('CANDIDATE_OK', value=c['status'], detail=name)
