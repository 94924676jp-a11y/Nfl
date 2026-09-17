"""Where each football adjustment may enter the dependency graph. One answer.

THE FAILURE THIS PREVENTS, STATED CONCRETELY

Opponent strength enters the system once as information and can enter many
times as a feature. If team pass volume is already conditioned on opponent pass
strength and a downstream player module applies the same opponent effect again,
the system holds ONE signal counted TWICE. The forecast becomes over-responsive
to opponent quality, its intervals narrow, and the apparent agreement between
"two signals" is an artifact of one signal wearing two names. Nothing in the
arithmetic complains: totals still reconcile, conservation still holds, and
every guard stays green.

The only cheap moment to build this is BEFORE the second consumer exists.

WHAT MAKES A RE-APPLICATION LAWFUL

Not all double application is double counting. A downstream module may
legitimately model a DISTINCT CONDITIONAL MECHANISM -- for example, opponent
coverage affecting a receiver's catch rate is not the same quantity as opponent
pass strength affecting team volume, even though both are "opponent". So a
consumer may re-apply an adjustment id only with an explicit
`distinct_mechanism` declaration naming what is different. Silence is refused.

LINEAGE, NOT INTENT. The check reads what a frame SAYS has been applied to it,
carried in the frame's own tag, and refuses on that. A module's belief about
what it is doing is not evidence.
"""
from __future__ import annotations

import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402

SPEC_VERSION = 'nfl-adjustment-registry-1'

# ------------------------------------------------------------ refusal codes
ALREADY_APPLIED = 'ADJUSTMENT_ALREADY_APPLIED'
OWNER_MISMATCH = 'ADJUSTMENT_OWNER_MISMATCH'
UNREGISTERED = 'UNREGISTERED_ADJUSTMENT'
LINEAGE_UNKNOWN = 'ADJUSTMENT_LINEAGE_UNKNOWN'
CONSUMER_NOT_PERMITTED = 'ADJUSTMENT_CONSUMER_NOT_PERMITTED'
NOT_PRODUCTION_APPROVED = 'ADJUSTMENT_NOT_PRODUCTION_APPROVED'
OK = 'ADJUSTMENT_APPLICATION_PERMITTED'

#: Every refusal here is HARD. A duplicated adjustment is not a warning: the
#: number it produces is wrong and nothing downstream can detect it.
HARD_CODES = (ALREADY_APPLIED, OWNER_MISMATCH, UNREGISTERED, LINEAGE_UNKNOWN,
              CONSUMER_NOT_PERMITTED, NOT_PRODUCTION_APPROVED)

#: Why `purpose` exists. WEEK2_OAS1_FIT_LAWFUL is YES_RESEARCH_ONLY and
#: WEEK2_OAS1_DOWNSTREAM_LAWFUL is NO. Those are two different permissions and
#: a registry that cannot tell them apart enforces neither. `purpose` is how a
#: caller says which one it is claiming, and the DEFAULT is production, so a
#: caller that says nothing gets the stricter answer.
PRODUCTION = 'production'
RESEARCH = 'research'

#: Status vocabulary. REGISTERED means the id exists and its lineage is
#: governed; it does NOT mean the effect is production-approved.
RESEARCH_ONLY = 'RESEARCH_ONLY'
PRODUCTION_APPROVED = 'PRODUCTION_APPROVED'
NOT_AVAILABLE = 'NOT_AVAILABLE'

ADJUSTMENTS = {
    # ---------------------------------------------------------- OAS1 ------
    # SEPARATE IDS FOR PASS AND RUSH, DELIBERATELY. The B0-B5 chain found
    # opponent adjustment supported on pass (B4 beats B5, clustered interval
    # excluding zero under both clusterings) and NOT supported on rush (B4 is
    # worse than B5 and worse than the league constant). One id covering both
    # would let a rush effect inherit a pass effect's evidence.
    'opponent_pass_strength_v1': {
        'owner': 'oas1',
        'producer': 'nfl.research.oas1.fit',
        'applied_at': 'team_volume',
        'permitted_consumers': ('diagnostics', 'research'),
        'emitted_quantity_is_already_adjusted': False,
        'embeds': (),
        'version': 1,
        'status': RESEARCH_ONLY,
        'evidence': 'nfl/research/oas1/BASELINE_RESULT_FROZEN.md -- '
                    'PASS_OPPONENT_ADJUSTMENT_SUPPORTED',
        'why_single_owner': 'one estimate of one quantity. Applying it in the '
                            'team layer and again in a player layer multiplies '
                            'one signal by itself.',
    },
    'opponent_rush_strength_v1': {
        'owner': 'oas1',
        'producer': 'nfl.research.oas1.fit',
        'applied_at': 'team_volume',
        'permitted_consumers': ('diagnostics', 'research'),
        'emitted_quantity_is_already_adjusted': False,
        'embeds': (),
        'version': 1,
        'status': RESEARCH_ONLY,
        'evidence': 'nfl/research/oas1/BASELINE_RESULT_FROZEN.md -- '
                    'RUSH_OPPONENT_ADJUSTMENT_NOT_SUPPORTED_YET',
        'note': 'REGISTERED IS NOT APPROVED. The present B4 rush '
                'specification does not beat B5 and is worse than the league '
                'constant. Registration governs its lineage so a research '
                'artifact can exist; it does not imply the effect is fit to '
                'ship, and it must not inherit the pass result.',
    },
    # ------------------------------------------------- already in the system
    'pace_v1': {
        'owner': 'team_volume', 'producer': 'nfl.production.team_volume_v1',
        'applied_at': 'team_volume', 'permitted_consumers': ('diagnostics',),
        'emitted_quantity_is_already_adjusted': True, 'embeds': (),
        'version': 1, 'status': PRODUCTION_APPROVED,
        'evidence': 'team_volume_v1 draws team snap and dropback levels from '
                    'own history (league_mean, team_expanding, last_game, '
                    'roll3, roll5, ewma, prev_season, coach_prior). Tempo is '
                    'EMBEDDED in those levels; it is never applied as a '
                    'discrete step, and ownership_audit finds zero '
                    'application sites for it on the whole production path. '
                    'The flag above is the load-bearing part: a downstream '
                    'layer that multiplied a pace factor onto those levels '
                    'would count the same tempo twice.',
        'note': 'APPROVED BUT NOT APPLIED. The status says a pace effect may '
                'reach production; it does not claim one currently does.',
    },
    'game_environment_v1': {
        'owner': 'team_environment', 'producer': None,
        'applied_at': 'team_environment', 'permitted_consumers': ('diagnostics',),
        'emitted_quantity_is_already_adjusted': False, 'embeds': (),
        'version': 1, 'status': NOT_AVAILABLE,
        'evidence': 'CORRECTED by ownership_audit. This entry previously read '
                    'PRODUCTION_APPROVED, already-adjusted, with the evidence '
                    '"the team_environment stage; roof and surface reach the '
                    'engine there and nowhere else". Every clause of that was '
                    'wrong. The production stage NAMED team_environment calls '
                    'TV.forecast(season, week, teams, m, seed, '
                    'joint_residuals, game_pairs, game_coupling) -- no roof, '
                    'no surface, no stadium. The only place either field '
                    'survives on the production path is '
                    'q9shadow/seal.py:118-120, where both are carried into '
                    'the sealed pregame row and never read again. The stage '
                    'name was a label and it was read as a football input.',
        'note': 'A STAGE NAMED AFTER AN EFFECT IS NOT THE EFFECT. This is the '
                'same failure class as a data label mistaken for football '
                'reality, and it survived a registry built to catch exactly '
                'that, because the entry was written from the stage name.',
    },
    'score_state_v1': {
        'owner': 'game_state', 'producer': None, 'applied_at': 'game_state',
        'permitted_consumers': ('diagnostics',),
        'emitted_quantity_is_already_adjusted': False, 'embeds': (),
        'version': 1, 'status': NOT_AVAILABLE,
        'evidence': 'no pregame-only score-state generator is wired into '
                    'production. Registered so that a future one has an owner '
                    'before it has a consumer.',
    },
    'weather_v1': {
        'owner': 'team_environment', 'producer': None,
        'applied_at': 'team_environment', 'permitted_consumers': ('diagnostics',),
        'emitted_quantity_is_already_adjusted': False, 'embeds': (),
        'version': 1, 'status': NOT_AVAILABLE,
        'evidence': 'schedules `temp` and `wind` are quarantined POSTHOC -- '
                    'they are the observed game-time conditions, so a '
                    'forecast reading them is reading the weather it is '
                    'predicting under. A forecast vintage would be a '
                    'separate registered source.',
    },
    # ------------------------------------------------ declared, not yet real
    'ol_pass_protection_v1': {
        'owner': 'line_play', 'producer': None, 'applied_at': 'line_play',
        'permitted_consumers': ('diagnostics',),
        'emitted_quantity_is_already_adjusted': False, 'embeds': (),
        'version': 1, 'status': NOT_AVAILABLE,
        'evidence': 'true pressure rate is not available in-season: '
                    'pbp_participation `was_pressure` is 404 for 2026 and is '
                    'published only after the postseason. Sack rate on '
                    'dropbacks is the public in-season proxy.',
    },
    'run_blocking_v1': {
        'owner': 'line_play', 'producer': None, 'applied_at': 'line_play',
        'permitted_consumers': ('diagnostics',),
        'emitted_quantity_is_already_adjusted': False, 'embeds': (),
        'version': 1, 'status': NOT_AVAILABLE,
        'evidence': 'no governed in-season source. Box-count data is FTN '
                    'charting and is the thinnest evidence in the hierarchy.',
    },
    'coverage_v1': {
        'owner': 'coverage', 'producer': None, 'applied_at': 'coverage',
        'permitted_consumers': ('diagnostics',),
        'emitted_quantity_is_already_adjusted': False, 'embeds': (),
        'version': 1, 'status': NOT_AVAILABLE,
        'evidence': 'defense_coverage_type comes from participation data, '
                    'which arrives after the postseason. A DISTINCT mechanism '
                    'from opponent_pass_strength_v1: coverage acts on catch '
                    'rate, opponent strength on team volume.',
    },
}


def get(adjustment_id: str) -> Outcome:
    a = ADJUSTMENTS.get(adjustment_id)
    if a is None:
        return Outcome.fail(
            UNREGISTERED,
            f'{adjustment_id!r} is not in the adjustment registry. An '
            f'undeclared adjustment is not thereby clean -- it is undeclared, '
            f'and nothing can check where it has already been applied.',
            cause=Cause.GOVERNANCE, adjustment_id=adjustment_id,
            registered=sorted(ADJUSTMENTS))
    return Outcome.ok('ADJUSTMENT_REGISTERED', value=dict(a),
                      detail=f'{adjustment_id}: owner {a["owner"]}, applied at '
                             f'{a["applied_at"]}, status {a["status"]}',
                      adjustment_id=adjustment_id, **{k: v for k, v in a.items()
                                                      if k != 'evidence'})


def assert_may_apply(adjustment_id: str, *, calling_layer: str,
                     frame_tags=None, distinct_mechanism: str = None,
                     purpose: str = PRODUCTION) -> Outcome:
    """May `calling_layer` apply `adjustment_id` to a frame carrying `frame_tags`?

    `frame_tags` is the frame's OWN record of what has already been applied to
    it. `None` is not an empty list: a frame that cannot say what has been done
    to it has unknown lineage and is refused, because "no tag" and "no
    adjustment" are different states and only one of them is safe.

    `purpose` defaults to PRODUCTION. A RESEARCH_ONLY adjustment applied under
    the production purpose is refused even by its own owning layer -- being the
    owner is permission to be the ONLY applier, not permission to ship. A
    NOT_AVAILABLE adjustment is refused under every purpose because it has no
    producer: there is nothing to apply.
    """
    reg = get(adjustment_id)
    if reg.state is not State.PASS:
        return reg
    a = reg.value
    ev = {'spec_version': SPEC_VERSION, 'adjustment_id': adjustment_id,
          'calling_layer': calling_layer, 'owner': a['owner'],
          'applied_at': a['applied_at'], 'status': a['status'],
          'frame_tags': (None if frame_tags is None else sorted(frame_tags)),
          'distinct_mechanism': distinct_mechanism}
    ev['purpose'] = purpose
    if frame_tags is None:
        return Outcome.fail(
            LINEAGE_UNKNOWN,
            f'the frame carries no adjustment lineage, so it cannot be shown '
            f'that {adjustment_id!r} has not already been applied. An absent '
            f'tag is not an empty one: "nothing was applied" and "nobody '
            f'recorded what was applied" are different states and only the '
            f'first is safe.',
            cause=Cause.GOVERNANCE, **ev)
    if a['status'] == NOT_AVAILABLE:
        return Outcome.fail(
            NOT_PRODUCTION_APPROVED,
            f'{adjustment_id!r} is {NOT_AVAILABLE}: it has no producer, so '
            f'there is no estimate to apply. It is registered so that a '
            f'future one has an owner before it has a consumer.',
            cause=Cause.GOVERNANCE, **ev)
    if a['status'] != PRODUCTION_APPROVED:
        if purpose != RESEARCH:
            return Outcome.fail(
                NOT_PRODUCTION_APPROVED,
                f'{adjustment_id!r} is {a["status"]} and this call claims '
                f'purpose {purpose!r}. Registered is not approved. A '
                f'research-only estimate reaching a production frame is the '
                f'whole thing this status exists to stop, and being the '
                f'owning layer does not change it.',
                cause=Cause.GOVERNANCE, **ev)
        if RESEARCH not in a['permitted_consumers']:
            return Outcome.fail(
                NOT_PRODUCTION_APPROVED,
                f'{adjustment_id!r} is {a["status"]} and does not list '
                f'{RESEARCH!r} among its permitted consumers, so it may not '
                f'be applied even under a research purpose.',
                cause=Cause.GOVERNANCE, **ev)
    if calling_layer != a['applied_at']:
        return Outcome.fail(
            OWNER_MISMATCH,
            f'{calling_layer!r} may not apply {adjustment_id!r}. Exactly one '
            f'layer applies it, {a["applied_at"]!r}, and a well-meaning '
            f'addition inside another layer is precisely how one signal '
            f'becomes two.',
            cause=Cause.GOVERNANCE, **ev)
    if adjustment_id in set(frame_tags):
        if not distinct_mechanism:
            return Outcome.fail(
                ALREADY_APPLIED,
                f'{adjustment_id!r} is already in this frame`s lineage. '
                f'Applying it again multiplies one signal by itself: the '
                f'forecast becomes over-responsive to the effect, its '
                f'intervals narrow, and nothing in the arithmetic complains. '
                f'A genuinely distinct conditional mechanism must be declared '
                f'by name.',
                cause=Cause.GOVERNANCE, **ev)
        return Outcome.ok(
            OK, value={'tags_after': sorted(set(frame_tags) | {adjustment_id})},
            detail=f'{adjustment_id} re-applied under a declared distinct '
                   f'mechanism: {distinct_mechanism}',
            re_applied_under_distinct_mechanism=True, **ev)
    return Outcome.ok(
        OK, value={'tags_after': sorted(set(frame_tags) | {adjustment_id})},
        detail=f'{calling_layer} may apply {adjustment_id}',
        re_applied_under_distinct_mechanism=False, **ev)


def assert_consumer(adjustment_id: str, *, consumer: str) -> Outcome:
    """May `consumer` READ an adjusted quantity? Reading is not re-applying."""
    reg = get(adjustment_id)
    if reg.state is not State.PASS:
        return reg
    a = reg.value
    if a['status'] == NOT_AVAILABLE:
        return Outcome.fail(
            NOT_PRODUCTION_APPROVED,
            f'{adjustment_id!r} is {NOT_AVAILABLE}: there is no estimate to '
            f'read. Reading a declared-but-absent adjustment would return a '
            f'default, and a default read as a measurement is worse than a '
            f'refusal.',
            cause=Cause.GOVERNANCE, adjustment_id=adjustment_id,
            consumer=consumer, status=a['status'])
    # THE APPLYING LAYER IS NOT AUTOMATICALLY A PERMITTED READER.
    #
    # This union used to be unconditional, and it silently cancelled the one
    # restriction the OAS1 entries were written to express: both opponent
    # adjustments are applied AT `team_volume` and deliberately do NOT list
    # `team_volume` as a permitted consumer, so the union made `team_volume` a
    # permitted reader of the very effect it is barred from consuming. A layer
    # that writes a PRODUCTION_APPROVED quantity necessarily reads it back;
    # nothing of the sort follows for one that is not approved.
    allowed = set(a['permitted_consumers'])
    if a['status'] == PRODUCTION_APPROVED:
        allowed |= {a['applied_at']}
    if consumer not in allowed:
        return Outcome.fail(
            CONSUMER_NOT_PERMITTED,
            f'{consumer!r} is not a permitted consumer of {adjustment_id!r} '
            f'(status {a["status"]}). Permitted: {sorted(allowed)}.',
            cause=Cause.GOVERNANCE, adjustment_id=adjustment_id,
            consumer=consumer, permitted=sorted(allowed), status=a['status'])
    return Outcome.ok('ADJUSTMENT_CONSUMER_PERMITTED', value=consumer,
                      detail=f'{consumer} may read {adjustment_id}',
                      adjustment_id=adjustment_id, consumer=consumer)


def audit_frame(tags, *, label: str = 'frame') -> Outcome:
    """Seal-time audit: every applied adjustment registered, none applied twice."""
    t = list(tags or [])
    unknown = sorted({x for x in t if x not in ADJUSTMENTS})
    dupes = sorted({x for x in t if t.count(x) > 1})
    ev = {'spec_version': SPEC_VERSION, 'label': label, 'tags': t,
          'n_tags': len(t), 'unregistered': unknown, 'duplicated': dupes}
    if unknown:
        return Outcome.fail(
            UNREGISTERED,
            f'{label}: {unknown} appear in the lineage and are not '
            f'registered. Undeclared is not clean.',
            cause=Cause.GOVERNANCE, **ev)
    if dupes:
        return Outcome.fail(
            ALREADY_APPLIED,
            f'{label}: {dupes} appear more than once in the lineage.',
            cause=Cause.GOVERNANCE, **ev)
    return Outcome.ok('ADJUSTMENT_LINEAGE_CLEAN', value=dict(ev),
                      detail=f'{label}: {len(t)} adjustment(s), all registered, '
                             f'none duplicated', **ev)
