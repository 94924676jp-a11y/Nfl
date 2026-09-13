"""Which arm a sealed artifact was SUPPOSED to carry. External to the artifact.

WHY THIS EXISTS, AND IT IS NOT A STYLE PREFERENCE.

The dry-run guard used to read `artifact['model_arm'] == 'A'`. That is not a
guard: it asks the artifact to grade its own homework, and it silently assumes
every artifact that ever existed was sealed under today's arm. When the arm was
corrected from B to A, four committed arm-B artifacts stopped satisfying it --
and the conflict was resolved by DELETING them. The suite went green because
the evidence was gone.

Owner ruling 2026-09-13: historical sealed artifacts are immutable, a later run
never replaces or mutates an earlier one, and the expected arm must come from
an external seal-time/identity policy rather than from the artifact's own
field. This module is that policy.

HOW IT DECIDES. An artifact is identified by (game_id, team). Identities sealed
before the arm-A transition are registered here, by name, with the arm the
regime of the day actually used. Everything else is expected to carry
`CURRENT_ARM`. The guard then compares the artifact's recorded `model_arm`
against what the policy says it should be, so:

  * a historical arm-B artifact validates AS ARM B and needs no edit;
  * anything sealed from here on must be arm A or the guard fails;
  * an artifact whose arm was tampered with fails, in either direction.

`CURRENT_ARM` IS DECLARED HERE, NOT READ FROM `seal.MODEL_ARM`. If the policy
imported the code's constant, then changing the constant would change what the
policy demands and the guard could never catch an unauthorised arm switch --
the thing most worth catching. They are cross-checked instead, and disagreement
is a failure.

THE ARMS ARE NEVER POOLED. `expected_arm` returns exactly one arm. There is no
"A or B is fine" branch anywhere in this file, because an artifact that could
be either is an artifact whose evidentiary status nobody can state.
"""
from __future__ import annotations

import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402

SPEC_VERSION = 'q9-arm-policy/1.0.0'

# Every arm this contract has ever defined. Membership is checked so an
# unrecognised arm is a named refusal rather than a silent pass.
KNOWN_ARMS = ('A', 'B', 'C')

# A: static pre-2026 benchmark, consumes no forecast-season outcome at any week.
# B: frozen prequential rule admitting strictly-earlier weeks of the forecast
#    season.
# C: reserved; defined so that a stray 'C' is refused by name rather than by
#    falling off the end of a lookup.
ARM_MEANING = {
    'A': 'static pre-forecast-season benchmark; no forecast-season outcome is '
         'consumed at any week',
    'B': 'frozen prequential rule admitting strictly-earlier weeks of the '
         'forecast season',
    'C': 'reserved, not in use',
}

# The arm every NEW seal must carry. Owner-directed correction from B to A,
# recorded in seal.py's MODEL_ARM commentary: arm A is the stronger evidentiary
# status because `shadow.fit_for` trains on strictly prior SEASONS for every
# week, so no forecast-season result reaches coefficients or features.
CURRENT_ARM = 'A'
CURRENT_ARM_BASIS = (
    'owner-directed correction from arm B to arm A. Recorded in '
    'nfl/prospective/q9shadow/seal.py at MODEL_ARM and in '
    'Q9_LIVE_FEATURE_PARITY.json window_divergence.open_owner_decision, which '
    'states it was implemented per directive rather than chosen in code.')

# IDENTITIES SEALED UNDER THE EARLIER REGIME. These are facts about what
# happened, not preferences. Adding an entry here is how a NEW historical
# artifact would be admitted; it is never how a current-arm seal is excused.
HISTORICAL_ARM_BY_IDENTITY = {
    ('2025_01_ARI_NO', 'ARI'): 'B',
    ('2025_01_ARI_NO', 'NO'): 'B',
}

HISTORICAL_BASIS = (
    'sealed before the arm-A correction, under the arm-B regime that '
    'nfl/prospective/q9shadow/seal.py carried at commit da58aec. Immutable by '
    'owner ruling 2026-09-13: a later run never replaces or mutates an earlier '
    'sealed artifact, and these four files must remain byte-identical.')


def identity_of(artifact) -> tuple:
    """The key this policy decides on. Never reads `model_arm`."""
    a = artifact or {}
    return (a.get('game_id'), a.get('team'))


def expected_arm(game_id, team) -> str:
    """Exactly one arm. Never a set, never a permissive 'either'."""
    return HISTORICAL_ARM_BY_IDENTITY.get((game_id, team), CURRENT_ARM)


def basis_for(game_id, team) -> str:
    if (game_id, team) in HISTORICAL_ARM_BY_IDENTITY:
        return HISTORICAL_BASIS
    return CURRENT_ARM_BASIS


def assert_arm(artifact) -> Outcome:
    """Does this artifact carry the arm the policy says it should?

    FAILS on a mismatch in EITHER direction: a historical artifact relabelled
    to the current arm is as much a defect as a new seal carrying an old one.
    """
    gid, team = identity_of(artifact)
    if not gid or not team:
        return Outcome.blocked(
            'Q9_ARM_IDENTITY_UNREADABLE',
            'the artifact carries no (game_id, team), so no policy can be '
            'applied to it. Refusing rather than defaulting to the current arm.',
            cause=Cause.DATA)
    got = (artifact or {}).get('model_arm')
    if got not in KNOWN_ARMS:
        return Outcome.fail(
            'Q9_ARM_NOT_A_KNOWN_ARM',
            f'{gid}/{team} records model_arm {got!r}, which is not one of '
            f'{KNOWN_ARMS}. An unrecognised arm has no evidentiary meaning.',
            game_id=gid, team=team, model_arm=got)
    want = expected_arm(gid, team)
    if got != want:
        return Outcome.fail(
            'Q9_ARM_POLICY_MISMATCH',
            f'{gid}/{team} records model_arm {got!r} but the governed policy '
            f'expects {want!r}. {basis_for(gid, team)}',
            game_id=gid, team=team, model_arm=got, expected_arm=want)
    return Outcome.ok(
        'Q9_ARM_MATCHES_POLICY', value=want, game_id=gid, team=team,
        expected_arm=want, arm_meaning=ARM_MEANING[want],
        basis=basis_for(gid, team),
        is_historical=(gid, team) in HISTORICAL_ARM_BY_IDENTITY,
        spec_version=SPEC_VERSION)


def assert_code_matches_policy() -> Outcome:
    """`seal.MODEL_ARM` must equal the arm the policy demands of new seals.

    This is the cross-check that makes CURRENT_ARM worth declaring separately.
    An arm switch made in code alone, without moving the policy, fails here.
    """
    from nfl.prospective.q9shadow import seal as SEAL
    got = getattr(SEAL, 'MODEL_ARM', None)
    if got != CURRENT_ARM:
        return Outcome.fail(
            'Q9_SEAL_ARM_DIVERGES_FROM_POLICY',
            f'seal.MODEL_ARM is {got!r} but the governed policy sets new seals '
            f'to {CURRENT_ARM!r}. An arm is an owner decision; changing the '
            f'code constant alone does not make it one.',
            seal_model_arm=got, policy_current_arm=CURRENT_ARM)
    return Outcome.ok('Q9_SEAL_ARM_MATCHES_POLICY', value=CURRENT_ARM,
                      spec_version=SPEC_VERSION)
