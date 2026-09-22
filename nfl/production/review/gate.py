"""The enforced gate. No projection reaches the optimizer merely because the
model emitted a number.

THREE VERDICTS, AND NO AMBIGUOUS GREEN

    PASS                 reviewed, nothing material contradicts the numbers
    PASS_WITH_WARNINGS   reviewed, annotations recorded, publication continues
    BLOCKED              a material contradiction; publication and
                         optimization stop

There is no fourth state and no "probably fine". A slate that was not reviewed
is `PLAYER_REVIEW_NOT_RUN`; a slate whose review does not match the projection
in front of it is `PLAYER_REVIEW_STALE`. Neither is a verdict -- both are
refusals to issue one, which is different and reads differently.

WHY MATERIALITY EXISTS AND WHY IT IS NOT A TUNING KNOB

Every conflict is real. Not every conflict can change an outcome. A third-string
tight end with 0.4 projected targets and an unsupported role is a genuine
finding and cannot move a lineup, a price or a decision; blocking on it would
train everyone to clear the gate without reading it, which is worse than not
having a gate.

So materiality is a SEPARATE, EXPLICIT judgement from severity:

    severity     what kind of wrongness this is        (a property of the code)
    materiality  whether this instance can change an   (a property of the row)
                 outcome

A conflict blocks when its code is in `BLOCKING_CODES` **and** the row is
material. A blocking code on an immaterial row is recorded as a warning with
`immaterial_blocking_code` set, so it is visible and countable and nobody can
claim it was hidden. A warning code never blocks however large the row.

WHERE ITS FOOTBALL FACTS COME FROM

The gate decides whether canonical football truth and governed model outputs
are publishable. It does not create football truth. Exactly ONE input to this
module is a football fact rather than a model output or review metadata --
the player's share of his club's opportunity -- and it is read from
`PregameSlateState.PlayerState`, never rebuilt here and never taken from the
dossier's relabelled copy. Everything else it weighs is a projection value, a
contest fact, or a property of a conflict the audit already raised.

MATERIALITY USES FOOTBALL AND CONTEST QUANTITIES ONLY

Owner rule, enforced here: sportsbook prices and external projections may
raise investigation priority and may not decide whether a football projection
is valid. `materiality()` therefore takes no market argument at all -- not one
it ignores, one it cannot be passed. The signature is the enforcement.
"""
from __future__ import annotations

import collections
import datetime as _dt
import hashlib
import json
import pathlib
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production.integrity import contract as IC               # noqa: E402
from nfl.production.review import audit as AUD                     # noqa: E402
from sportsplatform.governance.outcome import Cause, Outcome       # noqa: E402

SPEC_VERSION = 'player-review-gate-1'

PASS = 'PASS'
PASS_WITH_WARNINGS = 'PASS_WITH_WARNINGS'
BLOCKED = 'BLOCKED'
VERDICTS = (PASS, PASS_WITH_WARNINGS, BLOCKED)

# --- refusals that are not verdicts ---------------------------------------
PLAYER_REVIEW_NOT_RUN = 'PLAYER_REVIEW_NOT_RUN'
PLAYER_REVIEW_STALE = 'PLAYER_REVIEW_STALE'

# --- codes this module adds to the audit's own ----------------------------
C_INACTIVE_IN_POOL = 'INACTIVE_PLAYER_IN_SIMULATION_OR_OPTIMIZER_POOL'
C_IDENTITY_UNRESOLVED = 'IDENTITY_UNRESOLVED_BLOCKS_INACTIVE_APPLICATION'
C_DUPLICATE_IDENTITY = 'DUPLICATE_PLAYER_IDENTITY'
C_MISSING_ROW_IDS = 'MISSING_ROW_IDS'
C_SIM_ROW_MISMATCH = 'SIMULATION_ROW_MISMATCH'
C_CONSERVATION = 'OPPORTUNITY_CONSERVATION_FAILURE'
C_FORBIDDEN_INPUT = 'FORBIDDEN_EXTERNAL_INPUT_IN_PREDICTIVE_FEATURES'
C_UNAVAILABLE_CLAIMED = 'UNAVAILABLE_EVIDENCE_CLAIMED_AS_MEASURED'
C_INTEGRITY_COVERAGE_MISSING = 'INTEGRITY_COVERAGE_MISSING'
GATE_CODES = (C_INACTIVE_IN_POOL, C_IDENTITY_UNRESOLVED, C_DUPLICATE_IDENTITY,
              C_MISSING_ROW_IDS, C_SIM_ROW_MISMATCH, C_CONSERVATION,
              C_FORBIDDEN_INPUT, C_UNAVAILABLE_CLAIMED)

#: INTEGRITY CODES THIS GATE ADVERTISES, each with the subsystem that OWNS
#: the invariant and the producer that proves it. The gate CONSUMES these; it
#: does not compute them. An invariant belongs to the subsystem that owns the
#: data it is about, and putting all of them here would make the governance
#: layer a second implementation of everything it governs.
ADVERTISED_INTEGRITY: Dict[str, Dict[str, str]] = {
    C_INACTIVE_IN_POOL: {
        'owner': IC.OWNER_ELIGIBILITY,
        'producer': 'dfs.eligibility_integrity.'
                    'will_not_play_in_dfs_populations',
        'invariant': 'no player whose canonical availability is '
                     'WILL_NOT_PLAY survives into a governed DFS population '
                     '-- the optimizer pool at all, or the simulation with '
                     'draws that were never zeroed'},
    C_DUPLICATE_IDENTITY: {
        'owner': IC.OWNER_STATE,
        'producer': 'state.identity_integrity.duplicate_player_identity',
        'invariant': 'no canonical player id appears twice in the governed '
                     'population'},
    C_MISSING_ROW_IDS: {
        'owner': IC.OWNER_SIMULATION,
        'producer': 'simulation_integrity.missing_row_ids',
        'invariant': 'every draw layer says whose draws it carries'},
    C_SIM_ROW_MISMATCH: {
        'owner': IC.OWNER_SIMULATION,
        'producer': 'simulation_integrity.simulation_row_mismatch',
        'invariant': "a layer's row_ids and its arrays agree on the count"},
    C_UNAVAILABLE_CLAIMED: {
        'owner': IC.OWNER_PROVENANCE,
        'producer': 'review.provenance_integrity.'
                    'unavailable_claimed_as_measured',
        'invariant': 'a component published as MEASURED rests on at least '
                     'one MEASURED canonical axis'},
}

#: CODES THIS GATE HAS RELINQUISHED, and why. Each was declared BLOCKING with
#: NO PRODUCER ANYWHERE -- the gate advertised a guarantee production never
#: evaluated, and a clean gate record meant only that nobody had checked.
#:
#: Removing a code from BLOCKING_CODES does NOT weaken the gate: `classify`
#: sends an unregistered code to BLOCKING under `unregistered_code`, so if
#: one of these ever arrives it still stops the slate. What changes is that
#: the gate stops CLAIMING a guarantee it cannot consume.
#:
#: Three of the four invariants are already enforced in production by their
#: owning subsystem; what is missing is the wiring that surfaces the verdict
#: here, and that wiring belongs to those subsystems, not to this one.
RELINQUISHED_CODES: Dict[str, Dict[str, str]] = {
    C_IDENTITY_UNRESOLVED: {
        'owner': IC.OWNER_STATE,
        'enforced_today': 'player_universe classifies an unresolvable row '
                          'IDENTITY_UNRESOLVED, and inactives.resolve '
                          'REFUSES an ambiguous name rather than guessing',
        'gap': 'neither result is surfaced as an integrity finding, so a '
               'slate where an inactive could not be applied to a named '
               'player reads the same as one where every name resolved',
        'returns_when': 'the identity layer emits a finding for an inactive '
                        'declaration that could not be attached to a '
                        'canonical id'},
    C_CONSERVATION: {
        'owner': IC.OWNER_ALLOCATION,
        'enforced_today': 'allocation.assert_allocation_conserves runs in '
                          'universe/run_chain.py, and '
                          'draw_coherence.assert_draw_coherence runs in '
                          'run_forecast.py',
        'gap': 'both return their own Outcome and neither reaches this '
               'gate, so the gate cannot say whether conservation held',
        'returns_when': 'the allocation layer emits its verdict as an '
                        'IntegrityReport fragment'},
    C_FORBIDDEN_INPUT: {
        'owner': IC.OWNER_PROVENANCE,
        'enforced_today': 'pipeline.assert_no_postgame_inputs runs in '
                          'pipeline.py and refuses a stage that declares a '
                          'postgame field; adjustment_registry refuses an '
                          'undeclared re-application',
        'gap': 'both check DECLARED reads at the pipeline layer and neither '
               'reaches this gate',
        'returns_when': 'the pipeline emits its declaration verdict as an '
                        'IntegrityReport fragment'},
}

#: BLOCKING. Each can materially corrupt opportunity, projection ordering,
#: simulation integrity or optimizer selection. Grouped by the owner's
#: categories so the taxonomy is readable as policy, not as a list.
#: OWNER RULING: `INACTIVE_PLAYER_OWNS_OPPORTUNITY` KEEPS ITS NAME AND ITS
#: MEANING IS WIDENED. The code now reads:
#:
#:     a player with authoritative WILL_NOT_PLAY evidence still owns material
#:     projected opportunity
#:
#: which covers OFFICIAL_INACTIVE (and the dossier's INACTIVE alias) AND
#: INJURY_OUT. Before the availability slice the dossier collapsed an OUT
#: player into ACTIVE, so the code could only ever fire on the first of
#: those; the rule it encodes did not change, the evidence reaching it did.
#:
#: It is NOT renamed. The identifier is already wired into the audit, this
#: module, the enforcement suite and historical gate artifacts, and renaming
#: it would be schema churn with no change to the underlying rule. A later
#: schema-versioning cleanup may rename it.
WIDENED_CODE_MEANING = {
    AUD.C_INACTIVE_OWNS_OPPORTUNITY: (
        'a player with authoritative WILL_NOT_PLAY evidence -- '
        'OFFICIAL_INACTIVE, the dossier alias INACTIVE, or INJURY_OUT -- '
        'still owns material projected opportunity'),
}

BLOCKING_CODES: Dict[str, str] = {
    # availability integrity
    AUD.C_INACTIVE_OWNS_OPPORTUNITY: 'availability_integrity',
    # unsupported published role
    AUD.C_UNSUPPORTED_ROLE_PUBLISHED: 'unsupported_published_role',
    # role / opportunity inversion
    AUD.C_ROOM_ORDER_INVERTED: 'role_opportunity_inversion',
    # cold-start dominance
    AUD.C_COLD_START_MATERIAL: 'cold_start_dominance',
    # role-axis contamination
    AUD.C_ST_ONLY_OFFENSIVE_LOAD: 'role_axis_contamination',
    # a claim made on evidence that does not exist
    C_UNAVAILABLE_CLAIMED: 'contradicted_evidence_claim',
    # conservation / integrity
    AUD.C_NOT_EMITTED: 'integrity',
    C_DUPLICATE_IDENTITY: 'integrity',
    C_MISSING_ROW_IDS: 'integrity',
    C_SIM_ROW_MISMATCH: 'integrity',
    C_INACTIVE_IN_POOL: 'availability_integrity',
    # the gate's own: an advertised invariant nobody checked
    C_INTEGRITY_COVERAGE_MISSING: 'integrity',
}

#: WARNING. Real, recorded, visible in the slate report, never silently
#: cleared -- and never blocking, at any magnitude.
WARNING_CODES: Dict[str, str] = {
    AUD.C_RECEIVING_ROLE_ON_SNAPS_ONLY: 'optional_source_unavailable',
    AUD.C_DECLARED_STARTER_ZERO: 'conservative_disagreement',
    AUD.C_REDISTRIBUTION_DOMINATES: 'redistribution_disclosure',
}

#: Integrity codes that block whatever their magnitude: a duplicated identity
#: or a row-axis mismatch corrupts every number in the artifact, so asking
#: whether THIS row is material is the wrong question.
MATERIALITY_EXEMPT = frozenset({
    C_DUPLICATE_IDENTITY, C_MISSING_ROW_IDS, C_SIM_ROW_MISMATCH,
    C_UNAVAILABLE_CLAIMED, C_INTEGRITY_COVERAGE_MISSING, C_INACTIVE_IN_POOL,
    AUD.C_INACTIVE_OWNS_OPPORTUNITY,
})


# --------------------------------------------------------------------------
# materiality
# --------------------------------------------------------------------------
#: The thresholds. Every one is a DECLARED CONTEST-STRUCTURE FACT or a
#: DECLARED REVIEW CHOICE. None is fitted, none is estimated from an outcome,
#: and none may be moved to make a slate pass. Where a number comes from the
#: DraftKings rules it says so, because a contest rule is not a model constant.
MATERIALITY_RULE: Dict[str, Any] = {
    'spec_version': SPEC_VERSION,
    'statement': (
        'A conflict is MATERIAL when the row it sits on could change a '
        'published projection, a lineup, or a market comparison. It is the '
        'OR of five independent tests, because any one of them is enough to '
        'reach an outcome -- a player can matter through his points, his '
        'opportunity, his share of a team, the size of the disagreement, or '
        'simply by being rosterable at captain multiplier.'),
    'tests': {
        'dk_points': {
            'threshold': 2.0,
            'provenance': 'DECLARED REVIEW CHOICE, NOT FITTED. Two DK points '
                          'is roughly one reception plus a few yards; below '
                          'it a projection error cannot reorder a six-player '
                          'showdown lineup. Not calibrated against any '
                          'outcome and not to be moved to clear a slate.'},
        'opportunity': {
            'threshold': 2.0,
            'provenance': 'DECLARED REVIEW CHOICE. Two expected touches per '
                          'game is the smallest workload that separates a '
                          'rotational role from a spectator. The audit layer '
                          'uses 1.0 to RAISE a conflict; the gate uses 2.0 to '
                          'BLOCK on one, so noticing is cheaper than '
                          'stopping, deliberately.'},
        'team_opportunity_share': {
            'threshold': 0.05,
            'provenance': 'DECLARED REVIEW CHOICE. Five per cent of a club\'s '
                          'touches is about three plays a game; a role that '
                          'small cannot invert a room.',
            'rule': 'the LARGEST share of any relevant team resource: '
                    'max(carry_share, target_share) where both exist, '
                    'whichever exists where only one does, and UNAVAILABLE '
                    'where neither does. Never their sum -- the two have '
                    'different denominators. The selected resource is '
                    'reported, because a max over two numbers is not an '
                    'explanation.'},
        'projection_disagreement': {
            'threshold': 1.5,
            'provenance': 'DECLARED REVIEW CHOICE. The magnitude of the '
                          'conflicting quantity itself -- for an inversion, '
                          'how many opportunities the wrong way round. 1.5 is '
                          'below the opportunity floor on purpose: a large '
                          'ordering error between two small projections still '
                          'matters because it reveals the mechanism.'},
        'captain_exposure': {
            'threshold': None,
            'provenance': 'DRAFTKINGS CONTEST RULE, NOT A MODEL CONSTANT. In '
                          'a Showdown a rostered player can be captain at a '
                          '1.5x multiplier, so optimizer eligibility alone '
                          'makes a row able to change a lineup. True when the '
                          'player is in the optimizer pool.'},
    },
    'evidence_grade_modifier': (
        'A row whose projection rests on MEASURED current-season evidence is '
        'material at the stated thresholds. A row resting on a PRIOR or a '
        'COLD_START is material at HALF of them, because the same number '
        'carries less warrant and a smaller error is worth stopping for.'),
    'forbidden_inputs': (
        'Sportsbook prices, external projection services, ownership estimates '
        'and optimizer metrics are NOT arguments to this function. They may '
        'raise investigation priority in `escalation`; they may not decide '
        'whether a football projection is valid.'),
}

_COLD = ('PRIOR', 'COLD_START', 'HISTORICAL')


#: Which team resource a materiality share was taken from. Carried so the
#: dimension that triggered materiality is never something a reader has to
#: infer from two numbers.
CARRY_SHARE = 'carry_share'
TARGET_SHARE = 'target_share'
NO_SHARE = 'none_available'


@dataclass(frozen=True)
class TeamOpportunityMateriality:
    """The gate's concept of a player's share of his club's opportunity.

    `value` is None when neither share exists -- UNAVAILABLE, not zero. A
    player nobody measured is not a player measured at nothing, and a caller
    that wants a number for a threshold comparison asks for `.for_threshold`
    and gets the 0.0 explicitly rather than by accident.
    """
    value: Optional[float]
    selected_metric: str
    carry_share: Optional[float]
    target_share: Optional[float]

    @property
    def available(self) -> bool:
        return self.value is not None

    @property
    def for_threshold(self) -> float:
        """0.0 stands in for absent ONLY here, where a comparison needs a
        number, and it is visible in `selected_metric` that it did."""
        return 0.0 if self.value is None else float(self.value)

    def as_dict(self) -> Dict[str, Any]:
        return {'value': self.value, 'selected_metric': self.selected_metric,
                'carry_share': self.carry_share,
                'target_share': self.target_share,
                'available': self.available}


def team_opportunity_materiality(dossier) -> TeamOpportunityMateriality:
    """The largest share of any team resource this player owns.

    THE RULE, STATED RATHER THAN IMPLIED

        neither present            -> None, selected_metric none_available
        only carry_share present   -> carry_share
        only target_share present  -> target_share
        both present               -> max(carry_share, target_share)

    They are NEVER summed: carry_share is a share of team carries and
    target_share a share of team targets, so their sum is not a share of
    anything and cannot meet a threshold expressed as one.

    WHY MAX. Materiality asks whether this row can change an outcome AT ALL.
    A player is material through the largest claim he has on any relevant
    team resource, so a pass-catching back with a fifth of his club's
    targets is material whether or not he also carries the ball.

    WHAT THIS REPLACES, AND WHY IT WAS NEVER CAUGHT. The rule was
    `carry_share or target_share or 0.0`, which is positional precedence
    wearing a fallback's clothes: a back at carry_share 0.04 and
    target_share 0.20 was weighed on 0.04 and the 0.20 was never seen.
    Measured over all 312 saved review dossiers it produced ZERO flips --
    because in every row where the target share was larger, the carry share
    was EXACTLY 0.0, which is falsy, so the `or` fell through and happened to
    be right. The correctness rested on Python truthiness and on the usage
    panel emitting 0.0 rather than a small positive number for a non-rusher.
    See nfl/research/review/MATERIALITY_SHARE_PRECEDENCE.json.

    NO DENOMINATOR IS REBUILT HERE. Both shares are registered features the
    state carries whole, taken against `club_of_record`. The gate never sees
    a club total and must never compute one.
    """
    c = getattr(dossier, 'canonical', None)
    if c is None:
        raise AssertionError(
            'this dossier carries no canonical facts, so the gate has no '
            'authoritative team share to weigh. A dossier built outside '
            '`build_from_state`, or rehydrated from an artifact written '
            'before canonical facts were carried, is not gateable.')
    cs, ts = c.carry_share, c.target_share
    if cs is None and ts is None:
        return TeamOpportunityMateriality(None, NO_SHARE, None, None)
    if ts is None:
        return TeamOpportunityMateriality(float(cs), CARRY_SHARE, cs, ts)
    if cs is None:
        return TeamOpportunityMateriality(float(ts), TARGET_SHARE, cs, ts)
    if float(cs) >= float(ts):
        return TeamOpportunityMateriality(float(cs), CARRY_SHARE, cs, ts)
    return TeamOpportunityMateriality(float(ts), TARGET_SHARE, cs, ts)


def team_opportunity_share(dossier) -> float:
    """The number a threshold comparison uses. See
    `team_opportunity_materiality` for the rule and for what it replaced."""
    return team_opportunity_materiality(dossier).for_threshold


def materiality(dossier, conflict: Dict[str, Any], *,
                in_optimizer_pool: bool = False,
                rule: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Can this conflict, on this row, change an outcome?

    Takes no market argument by construction. Returns the verdict AND every
    test that produced it, so a reader can see which one fired rather than
    trusting a boolean.
    """
    rule = rule or MATERIALITY_RULE
    th = {k: v['threshold'] for k, v in rule['tests'].items()}

    if conflict.get('code') in MATERIALITY_EXEMPT:
        return {'material': True, 'exempt': True,
                'why': 'integrity or availability code: corrupts the artifact '
                       'or the availability frame regardless of this row\'s '
                       'size, so magnitude is not the question',
                'tests': {}}

    grades = {c.grade for c in dossier.projection.values()}
    cold = bool(grades) and grades.issubset(set(_COLD))
    scale = 0.5 if cold else 1.0

    pts = dossier.headline or 0.0
    opp = sum(dossier.mean(m) or 0.0
              for m in ('carries', 'targets', 'pass_attempts'))
    tshare = team_opportunity_materiality(dossier)
    share = tshare.for_threshold
    ev = conflict.get('evidence') or {}
    gap = 0.0
    hi, lo = ev.get('higher') or {}, ev.get('lower') or {}
    metric = ev.get('metric')
    if metric and metric in hi and metric in lo:
        gap = abs(float(hi[metric]) - float(lo[metric]))
    gap = max(gap, float(ev.get('opportunity') or 0.0)
              if conflict.get('code') == AUD.C_UNSUPPORTED_ROLE_PUBLISHED
              else gap)

    tests = {
        'dk_points': pts >= th['dk_points'] * scale,
        'opportunity': opp >= th['opportunity'] * scale,
        'team_opportunity_share': share >= (
            th['team_opportunity_share'] * scale),
        'projection_disagreement': gap >= th['projection_disagreement'] * scale,
        'captain_exposure': bool(in_optimizer_pool) and pts > 0.0,
    }
    fired = sorted(k for k, v in tests.items() if v)
    return {'material': bool(fired), 'exempt': False,
            'evidence_grade_scale': scale,
            'cold_start_dominated': cold,
            'measured': {'dk_points': round(pts, 4),
                         'opportunity': round(opp, 4),
                         'team_opportunity_share': round(share, 6),
                         'projection_disagreement': round(gap, 4),
                         'in_optimizer_pool': bool(in_optimizer_pool)},
            # WHICH RESOURCE TRIGGERED IT. Two numbers and a max is not an
            # explanation; the selected dimension is.
            'team_opportunity_share_detail': tshare.as_dict(),
            'tests': tests, 'fired': fired,
            'why': (f'material: {fired}' if fired else
                    'no test fired: this conflict cannot change a projection, '
                    'a lineup or a price on this row')}


def classify(conflict: Dict[str, Any], mat: Dict[str, Any]) -> Dict[str, Any]:
    """BLOCKING, WARNING, or a blocking code held back as immaterial."""
    code = conflict.get('code')
    if code in WARNING_CODES:
        return {'disposition': 'WARNING', 'category': WARNING_CODES[code],
                'immaterial_blocking_code': False}
    if code in BLOCKING_CODES:
        if mat['material']:
            return {'disposition': 'BLOCKING',
                    'category': BLOCKING_CODES[code],
                    'immaterial_blocking_code': False}
        return {'disposition': 'WARNING', 'category': BLOCKING_CODES[code],
                'immaterial_blocking_code': True}
    # An unregistered code is not quietly a warning. Governance failures have
    # been created exactly this way: a new code appears, nothing classifies
    # it, and it defaults to harmless.
    return {'disposition': 'BLOCKING', 'category': 'unregistered_code',
            'immaterial_blocking_code': False,
            'note': f'{code!r} is in neither BLOCKING_CODES nor '
                    f'WARNING_CODES. An unclassified conflict blocks, because '
                    f'defaulting an unknown code to harmless is how a gate '
                    f'stops working.'}


# --------------------------------------------------------------------------
# the gate
# --------------------------------------------------------------------------
def assert_producer_coverage(integrity_report) -> Outcome:
    """Every advertised integrity code must have been CHECKED, or say why not.

    THERE IS NO FOURTH STATE. A code this gate advertises as BLOCKING has a
    producer that ran (passing or failing), or a declared NOT_APPLICABLE with
    a reason. 'Declared but nobody checks it' is the state this whole slice
    exists to remove, and it is what this function refuses.
    """
    if integrity_report is None:
        return Outcome.fail(
            C_INTEGRITY_COVERAGE_MISSING,
            f'no integrity report was supplied, so all '
            f'{len(ADVERTISED_INTEGRITY)} advertised invariant(s) are '
            f'NOT_CHECKED: {sorted(ADVERTISED_INTEGRITY)}. Absence of a '
            f'finding is not a passing check.',
            value={'not_checked': sorted(ADVERTISED_INTEGRITY)})
    missing = sorted(c for c in ADVERTISED_INTEGRITY
                     if integrity_report.state_of(c) == IC.NOT_CHECKED)
    if missing:
        return Outcome.fail(
            C_INTEGRITY_COVERAGE_MISSING,
            f'{len(missing)} advertised integrity invariant(s) were not '
            f'checked: {missing}. The gate declares them BLOCKING, so a '
            f'verdict issued without them would claim a guarantee nobody '
            f'evaluated.',
            value={'not_checked': missing,
                   'checked': list(integrity_report.codes_checked())})
    return Outcome.ok(
        'INTEGRITY_COVERAGE_COMPLETE',
        {'checked': list(integrity_report.codes_checked()),
         'coverage': {c: integrity_report.state_of(c)
                      for c in sorted(ADVERTISED_INTEGRITY)}},
        detail=f'{len(ADVERTISED_INTEGRITY)} advertised invariant(s), none '
               f'NOT_CHECKED')


def evaluate(report: Optional[Dict[str, Any]], *,
             dossiers: Sequence[Any] = (),
             projection_digest: Optional[str] = None,
             optimizer_pool_ids=None,
             resolved_conflict_codes=None,
             integrity_report=None,
             require_integrity_coverage: bool = False,
             extra_conflicts: Sequence[Dict[str, Any]] = ()) -> Outcome:
    """The one call an optimizer makes. PASS / PASS_WITH_WARNINGS / BLOCKED.

    `projection_digest` is the npz digest the optimizer is about to consume.
    Supplying it is what makes staleness detectable; omitting it is allowed
    only where no projection is being consumed at all.
    """
    if not report:
        return Outcome.blocked(
            PLAYER_REVIEW_NOT_RUN,
            'no player review was supplied for this slate, so no projection '
            'may be published or optimized. A slate nobody looked at is not a '
            'slate that passed.', cause=Cause.GOVERNANCE,
            value={'verdict': BLOCKED})

    reviewed = ((report.get('projection_source') or {}).get('digests')
                or {}).get('player_draws.npz')
    if projection_digest is not None:
        if reviewed is None:
            return Outcome.blocked(
                PLAYER_REVIEW_STALE,
                'the review records no draw-artifact digest, so it cannot be '
                'tied to the projection being consumed. An untied review is '
                'indistinguishable from a review of something else.',
                cause=Cause.DATA, value={'verdict': BLOCKED})
        if reviewed != projection_digest:
            return Outcome.blocked(
                PLAYER_REVIEW_STALE,
                f'the review audited draws {reviewed[:16]}... and the '
                f'optimizer is about to consume {projection_digest[:16]}.... '
                f'A review of a different run is not a review of this one.',
                cause=Cause.DATA,
                value={'verdict': BLOCKED, 'reviewed': reviewed,
                       'consuming': projection_digest})

    pool = set(optimizer_pool_ids or ())
    resolved = set(resolved_conflict_codes or ())
    dby = {d.gsis_id: d for d in dossiers}

    # INTEGRITY FINDINGS ARE CONFLICTS. They arrive from the subsystems that
    # own the invariants, already coded and severity-tagged, and they join
    # the audit's rows rather than opening a second classification path.
    integrity_conflicts = (list(integrity_report.conflicts())
                           if integrity_report is not None else [])
    coverage_conflicts: List[Dict[str, Any]] = []
    icov = assert_producer_coverage(integrity_report)
    if require_integrity_coverage and icov.state.name != 'PASS':
        for code in (icov.value or icov.evidence.get('value')
                     or {}).get('not_checked', []):
            coverage_conflicts.append({
                'code': C_INTEGRITY_COVERAGE_MISSING, 'severity': 'BLOCKING',
                'gsis_id': None, 'display_name': f'invariant {code}',
                'detail': f'{code} is advertised as a blocking integrity '
                          f'guarantee and NOTHING CHECKED IT on this run. '
                          f'{ADVERTISED_INTEGRITY.get(code, {}).get("invariant", "")} '
                          f'Owner: '
                          f'{ADVERTISED_INTEGRITY.get(code, {}).get("owner")}.',
                'evidence': {'uncovered_code': code,
                             'expected_producer': ADVERTISED_INTEGRITY.get(
                                 code, {}).get('producer')},
                'integrity': True})

    rows: List[Dict[str, Any]] = []
    for c in (list(report.get('conflicts', [])) + integrity_conflicts
              + coverage_conflicts + list(extra_conflicts)):
        d = dby.get(c.get('gsis_id'))
        if d is None:
            # No dossier for a conflict's subject is itself an integrity
            # failure; it cannot be assessed and must not be waved through.
            rows.append({**c, 'disposition': 'BLOCKING',
                         'category': 'integrity',
                         'materiality': {'material': True, 'exempt': True,
                                         'why': 'no dossier for this player, '
                                                'so the conflict cannot be '
                                                'assessed'}})
            continue
        try:
            mat = materiality(d, c, in_optimizer_pool=c.get('gsis_id') in pool)
        except AssertionError as e:
            # A dossier with no canonical state cannot be weighed against
            # football truth. Fail closed, in the same shape as a conflict
            # with no dossier at all, rather than raising out of a
            # governance call.
            rows.append({**c, 'disposition': 'BLOCKING',
                         'category': 'integrity',
                         'materiality': {'material': True, 'exempt': True,
                                         'why': str(e)}})
            continue
        cls = classify(c, mat)
        row = {**c, **cls, 'materiality': mat}
        if cls['disposition'] == 'BLOCKING' and c.get('code') in resolved:
            row['disposition'] = 'WARNING'
            row['resolved_by_name'] = True
        rows.append(row)

    blocking = [r for r in rows if r['disposition'] == 'BLOCKING']
    warnings = [r for r in rows if r['disposition'] == 'WARNING']
    verdict = (BLOCKED if blocking
               else (PASS_WITH_WARNINGS if warnings else PASS))

    cov = report.get('coverage', {})
    value = {
        'verdict': verdict,
        'spec_version': SPEC_VERSION,
        'run_identity': {
            'run_id': (report.get('projection_source') or {}).get('run_id'),
            'slate_key': report.get('slate_key'),
            'information_cut': report.get('information_cut'),
            'reviewed_draw_digest': reviewed,
            'consumed_draw_digest': projection_digest},
        'reviewed_player_count': cov.get('n_universe'),
        'publishable_player_count': cov.get('n_publishable'),
        'optimizer_pool_count': len(pool),
        'blocking_conflict_count': len(blocking),
        'warning_count': len(warnings),
        'blocking_players': sorted({(r.get('display_name') or r.get('gsis_id'))
                                    for r in blocking}),
        'warning_players': sorted({(r.get('display_name') or r.get('gsis_id'))
                                   for r in warnings}),
        'blocking_by_category': dict(collections.Counter(
            r['category'] for r in blocking)),
        'warning_by_category': dict(collections.Counter(
            r['category'] for r in warnings)),
        'immaterial_blocking_codes_held_as_warnings': dict(
            collections.Counter(r['code'] for r in warnings
                                if r.get('immaterial_blocking_code'))),
        'resolved_by_name': sorted(resolved),
        'integrity': {
            'report_supplied': integrity_report is not None,
            'required': bool(require_integrity_coverage),
            'coverage_verdict': icov.code,
            'report_hash': (None if integrity_report is None
                            else integrity_report.report_hash()),
            'coverage': ({c: IC.NOT_CHECKED for c in ADVERTISED_INTEGRITY}
                         if integrity_report is None else
                         {c: integrity_report.state_of(c)
                          for c in sorted(ADVERTISED_INTEGRITY)}),
            'advertised': {c: dict(v) for c, v in
                           sorted(ADVERTISED_INTEGRITY.items())},
            'relinquished': {c: dict(v) for c, v in
                             sorted(RELINQUISHED_CODES.items())},
            'n_findings': (0 if integrity_report is None
                           else len(integrity_report.findings)),
            'producer_versions': ({} if integrity_report is None
                                  else integrity_report.producer_versions()),
        },
        'conflicts': rows,
        'materiality_rule': MATERIALITY_RULE,
        'artifact_hashes': (report.get('projection_source') or {}).get(
            'digests', {}),
        'review_timestamp_utc': _dt.datetime.now(
            _dt.timezone.utc).isoformat(),
    }
    if verdict == BLOCKED:
        return Outcome.fail(
            'PLAYER_REVIEW_BLOCKED',
            f'{len(blocking)} material blocking conflict(s) across '
            f'{len(value["blocking_players"])} player(s): '
            f'{sorted(value["blocking_by_category"])}. Publication and '
            f'optimization stop here.', value=value)
    return Outcome.ok(
        f'PLAYER_REVIEW_{verdict}', value,
        detail=f'{verdict}: {len(blocking)} blocking, {len(warnings)} '
               f'warning(s) over {cov.get("n_universe")} reviewed players')


def payload(outcome) -> Dict[str, Any]:
    """The value dict on any Outcome, whichever field it landed in.

    `Outcome.ok` puts it on `.value`; `Outcome.fail` and `Outcome.blocked` put
    it under `.evidence['value']`. A consumer that reads only `.value` gets
    None on exactly the outcomes it most needs to inspect, and this project
    has now written that bug twice. One accessor.
    """
    v = getattr(outcome, 'value', None)
    if isinstance(v, dict):
        return v
    e = (getattr(outcome, 'evidence', None) or {}).get('value')
    return e if isinstance(e, dict) else {}


def verdict_of(outcome) -> Optional[str]:
    """The verdict on any gate Outcome, PASS or refusal alike.

    `Outcome.fail` and `Outcome.blocked` put `value=` into `.evidence`, not
    `.value`, so `outcome.value['verdict']` silently reads None on exactly the
    outcomes a caller most needs to inspect. Rather than making every consumer
    remember that, this is the one accessor.
    """
    return payload(outcome).get('verdict')


def write_gate(gate_value: Dict[str, Any], path) -> Outcome:
    """Persist `review_gate.json`. Refuses to write a verdict-free record."""
    if gate_value.get('verdict') not in VERDICTS:
        return Outcome.fail(
            'GATE_RECORD_WITHOUT_A_VERDICT',
            f'{gate_value.get("verdict")!r} is not one of {VERDICTS}. A gate '
            f'record with no verdict is the ambiguous green this module '
            f'exists to prevent.', value=gate_value.get('verdict'))
    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(gate_value, indent=1, sort_keys=True,
                      default=str).encode()
    p.write_bytes(body)
    return Outcome.ok('GATE_RECORD_WRITTEN',
                      {'path': str(p), 'sha256':
                       hashlib.sha256(body).hexdigest(),
                       'verdict': gate_value['verdict']},
                      detail=f'{gate_value["verdict"]} -> {p}')


def require_pass(gate: Outcome, *, allow_warnings: bool = True) -> Outcome:
    """The optimizer's own assertion. Call this, then optimize, never before.

    Separate from `evaluate` so the refusal is visible at the optimizer's call
    site rather than buried in the evaluation that produced it.
    """
    v = (gate.value or gate.evidence.get('value') or {}).get('verdict')
    if v == PASS or (v == PASS_WITH_WARNINGS and allow_warnings):
        return Outcome.ok('OPTIMIZATION_PERMITTED',
                          {'verdict': v},
                          detail=f'gate verdict {v}')
    return Outcome.fail(
        'OPTIMIZATION_REFUSED_BY_PLAYER_REVIEW',
        f'the player-review gate returned {v or gate.code}, so no lineup may '
        f'be built from this projection set.',
        value={'verdict': v, 'gate_code': gate.code,
               'gate_detail': gate.detail})
