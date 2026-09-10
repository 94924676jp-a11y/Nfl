"""What the V1 candidate configuration IS, in one readable table.

WHY THIS MODULE EXISTS. The owner's ruling is explicit: the canonical
entrypoint must be able to invoke the candidate configuration, it must stay
explicit and non-default, it must name every rehearsal-only component actually
active, and -- the load-bearing clause -- *"it must remain impossible for this
candidate mode to masquerade as the default/promoted production model."*

Impossible, not merely discouraged. So the mode is a DECLARED SET, not a pile
of boolean flags threaded through call sites. A component that is on has a row
here carrying its governance status and its pre-registration; a component with
no row cannot be switched on at all; and the artifact writes the resolved set
verbatim, so "which model produced this number" is answered by the artifact
rather than by reconstructing an invocation.

NOTHING HERE IS PROMOTED. Engineering integration is not prospective
validation. Every component below is REHEARSAL_ONLY and stays that way until
an owner artifact says otherwise -- which no code path can produce.
"""
from __future__ import annotations

import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Outcome            # noqa: E402

# The two configurations the entrypoint can run. PRODUCTION_BASELINE is the
# default and contains no candidate component.
PRODUCTION_BASELINE = 'PRODUCTION_BASELINE'
V1_CANDIDATE = 'V1_CANDIDATE'
V1_CANDIDATE_R5 = 'V1_CANDIDATE_R5'
MODES = (PRODUCTION_BASELINE, V1_CANDIDATE, V1_CANDIDATE_R5)

# component -> what it does, what governs it, and what it changes.
# `engine_flag` is the argument football_engine.run_game receives.
COMPONENTS = {
    'R2': {
        'what': 'QB dropback level owned by D1 x QB3 and apportioned by '
                'largest remainder; QB V1 supplies conditional rates only',
        'replaces': 'the composition that divided one level by another',
        'predeclaration': 'nfl/research/r2/'
                          'predeclaration_qb_level_ownership_r2.md',
        'predeclaration_sha256':
            '3d7beeb39f32da11623ac2be178ca4b764ecf314a5a55515b0d45c0e3d4f323c',
        'governance': 'REHEARSAL_ONLY -- engineering integration, not '
                      'prospective validation',
        'engine_flag': 'r2',
    },
    'C0': {
        'what': 'cold-start quarterbacks kept in the slate so allocated share '
                'reaches a modelled QB state',
        'replaces': 'a 2.3-6.9% dropback share leaving the system',
        'predeclaration': 'nfl/research/own3/predeclaration_own3.md',
        'predeclaration_sha256':
            'aedced9c82f74b5b406e4658ddf8b435fc1582fdfc0e7d759a5a7ff3b5f07c82',
        'governance': 'REHEARSAL_ONLY',
        'engine_flag': 'include_cold_start',
    },
    'C3': {
        'what': 'one passing event: the target budget comes from the throw '
                'process and the passer line is credited from the receiving '
                'event',
        'replaces': 'passing and receiving yards/TDs drawn independently',
        'predeclaration': 'nfl/research/xl1/predeclaration_xl1.md',
        'predeclaration_sha256':
            '60fe3fbc0f35933e7bd4b43c56fb0afb68d95de67b4f51699a878ceb488d94da',
        'governance': 'REHEARSAL_ONLY',
        'engine_flag': 'shared_pass',
    },
    'A3G': {
        'what': 'the two teams in a game share one coupled draw index; '
                'marginals unmoved by construction',
        'replaces': 'two independently drawn teams, and game totals whose '
                    'spread was the sum of independent marginals',
        'predeclaration': 'nfl/research/a3g/predeclaration_a3g.md',
        'predeclaration_sha256':
            'd3620883e52fd6d2da9b56403a219210e82e52d5a65bf73cbd23f1d13d4e78ea',
        'governance': 'REHEARSAL_ONLY -- its own pre-registered verdict did '
                      'NOT clear; integrated on corrected clauses recorded in '
                      'predeclaration_a3g_addendum_01.md',
        'engine_flag': 'game_coupling',
    },
    'SC1': {
        'what': 'the scramble/carry joint state is made coherent by permuting '
                'which draw index receives which carry value, so team carries '
                '>= QB scrambles in every draw',
        'replaces': 'two levels drawn on one index from independent '
                    'randomness, whose tails crossed into a negative '
                    'rush-play budget',
        'predeclaration': 'nfl/research/sc1/predeclaration_sc1.md',
        'predeclaration_sha256':
            'b62e48f23b5f3a16fb633e5286e575f23d7de3e07c8ebf923255d8d565e76729',
        'governance': 'REHEARSAL_ONLY',
        'engine_flag': 'rushing_a1',
    },
    'A1': {
        'what': 'single-owner rushing: one multinomial partitions the '
                'rush-play budget across kneel / designed QB / RB / WR / TE / '
                'fringe, so every carry has exactly one owner',
        'replaces': 'a QB rush draw that could exceed the carry pool it sits '
                    'inside',
        'predeclaration': 'nfl/research/own8/predeclaration_own8.md',
        'predeclaration_sha256':
            '90f6ecc37bcee427177f183be03374c13ec87fe1e14d667a4457c797748789db',
        'governance': 'REHEARSAL_ONLY',
        'engine_flag': 'rushing_a1',
    },
}

# The flag values the candidate mode resolves to. Kept beside the table so a
# reader can see the whole configuration without running anything.
V1_CANDIDATE_FLAGS = {
    'r2': True,
    'include_cold_start': True,
    'shared_pass': 'c3',
    'game_coupling': 'off_snaps',
    'rushing_a1': True,
}


# R5. THE ACTIVE-ROSTER POOL, AS A SEPARATE CONFIGURATION IDENTITY.
#
# V1_CANDIDATE is the immutable control and is unchanged, flag for flag. R5 is
# V1_CANDIDATE plus one repair, so any difference between the two runs is
# attributable to that repair and to nothing else.
#
# THE DEFECT, MEASURED. `p4c_params.class_point_forecast` returns an EWMA of a
# player's prior APPEARED class shares -- a share conditional on him playing --
# and the allocator uses it as a relative weight over whatever roster it is
# handed. The fitting panel holds 14.6 WR/TE/RB per team-game with C summing to
# 1.24. The prospective entrypoint hands it the full weekly roster: 22 and 23
# players for SF@LA, C summing to 2.25 and 2.04. The simplex divides by that
# sum, halving every real starter share.
#
# Of the 45 SF/LA WR/TE/RB roster rows, 29 are ACT, 10 DEV (practice squad),
# 3 RES and 3 CUT. Filtering to ACT restores the pool to 14 and 15 -- the size
# the estimator was fitted for -- without removing a single player who could
# take a snap.
#
# NO CONSTANT IS INTRODUCED AND NOTHING IS TUNED. The filter is a roster fact.
R5_FLAGS = dict(
    r2=True, include_cold_start=True, shared_pass='c3',
    game_coupling='off_snaps', rushing_a1=True,
    active_roster_only=True,
)

R5_REPAIR = {
    'component': 'R5',
    'what': 'restrict the non-QB allocation pool to players whose roster '
            'status is ACT',
    'replaces': 'an unfiltered weekly-roster pool that included practice '
                'squad, reserve and released players',
    'defect': 'P4C weights are conditional-on-appearing shares consumed as '
              'unconditional weights over an unfiltered roster, so the vector '
              'is not a partition and normalisation halves every starter',
    'evidence': 'historical pool 14.6/team-game with sum(C)=1.24; unfiltered '
                '2026 pool 22.5 with sum(C)=2.14; ACT-filtered 14.5 with '
                'sum(C)=1.46',
    'governance': 'REHEARSAL_ONLY',
    'introduces_no_constant': True,
}


def resolve(mode: str) -> Outcome:
    """The flags and the component manifest for a named mode, or a refusal.

    An unknown mode is REFUSED rather than falling back to the baseline: a
    typo that silently produced the promoted model while the operator believed
    they were running the candidate is precisely the masquerade this module
    exists to make impossible -- and it would fail in the dangerous direction,
    since the baseline is the one allowed to publish.
    """
    if mode in (None, '', PRODUCTION_BASELINE):
        return Outcome.ok(
            'MODE_PRODUCTION_BASELINE',
            value={'mode': PRODUCTION_BASELINE, 'flags': {},
                   'components': [], 'candidate': False},
            detail='no candidate component is active')
    if mode == V1_CANDIDATE_R5:
        return Outcome.ok(
            'MODE_V1_CANDIDATE_R5',
            value={'mode': V1_CANDIDATE_R5, 'flags': dict(R5_FLAGS),
                   'components': manifest() + [R5_REPAIR], 'candidate': True},
            detail='V1_CANDIDATE plus the R5 active-roster pool repair')
    if mode != V1_CANDIDATE:
        return Outcome.fail(
            'MODEL_CONFIGURATION_UNKNOWN',
            f'{mode!r} is not a declared model configuration. Declared: '
            f'{list(MODES)}. Refusing rather than defaulting -- a typo that '
            f'quietly ran the promoted baseline would be the masquerade this '
            f'refusal exists to prevent.',
            known=list(MODES))
    return Outcome.ok(
        'MODE_V1_CANDIDATE',
        value={'mode': V1_CANDIDATE, 'flags': dict(V1_CANDIDATE_FLAGS),
               'components': manifest(), 'candidate': True},
        detail=f'{len(COMPONENTS)} rehearsal-only component(s) active: '
               f'{", ".join(sorted(COMPONENTS))}')


def manifest() -> list:
    """Every active component, with what governs it. Written into the artifact
    verbatim so the run carries its own provenance."""
    return [{'component': k, **v} for k, v in sorted(COMPONENTS.items())]


def assert_not_promoted(mode: str, artifact: dict) -> Outcome:
    """A candidate artifact must say so, in every field that could be read as
    a promotion claim. Called by the sealer; tested with the guard stubbed."""
    if mode not in (V1_CANDIDATE, V1_CANDIDATE_R5):
        return Outcome.not_applicable('NOT_A_CANDIDATE_RUN',
                                      f'mode is {mode!r}')
    bad = []
    if artifact.get('model_configuration') not in (V1_CANDIDATE,
                                                   V1_CANDIDATE_R5):
        bad.append('model_configuration does not name the candidate mode')
    if not artifact.get('candidate_components'):
        bad.append('candidate_components is empty on a candidate run')
    if artifact.get('promoted') is not False:
        bad.append('promoted is not explicitly False')
    if artifact.get('prospective_eligible') is not False:
        bad.append('prospective_eligible is not explicitly False')
    ev = str(artifact.get('eligibility_verdict', ''))
    if not any(m in ev for m in (V1_CANDIDATE, V1_CANDIDATE_R5)):
        bad.append('eligibility_verdict does not carry the candidate mode')
    if bad:
        return Outcome.fail(
            'CANDIDATE_RUN_COULD_MASQUERADE_AS_PROMOTED',
            'a V1 candidate artifact must be unmistakable: ' + '; '.join(bad),
            problems=bad)
    return Outcome.ok(
        'CANDIDATE_RUN_DECLARED', value=True,
        detail=f'{len(artifact["candidate_components"])} component(s) named; '
               f'promoted False; prospective_eligible False')
