"""FROZEN COPY of review/gate.py at commit 7dadfee. DO NOT EDIT.

The accepted pre-migration gate, kept so the migrated one can be proved to
return the same verdict for the same slate rather than a plausible one. A
separate artifact for the same reason `dfs/classic/reference.py`,
`review/dossier_reference.py` and `review/audit_reference.py` are: a change
to one must not be able to be silently a change to both.
"""

from __future__ import annotations

import collections
import datetime as _dt
import hashlib
import json
import pathlib
import sys
from typing import Any, Dict, List, Optional, Sequence

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production.review import audit as AUD                     # noqa: E402
from sportsplatform.governance.outcome import Cause, Outcome       # noqa: E402

SPEC_VERSION = 'player-review-gate-reference-7dadfee'

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
GATE_CODES = (C_INACTIVE_IN_POOL, C_IDENTITY_UNRESOLVED, C_DUPLICATE_IDENTITY,
              C_MISSING_ROW_IDS, C_SIM_ROW_MISMATCH, C_CONSERVATION,
              C_FORBIDDEN_INPUT, C_UNAVAILABLE_CLAIMED)

#: BLOCKING. Each can materially corrupt opportunity, projection ordering,
#: simulation integrity or optimizer selection. Grouped by the owner's
#: categories so the taxonomy is readable as policy, not as a list.
BLOCKING_CODES: Dict[str, str] = {
    # availability integrity
    AUD.C_INACTIVE_OWNS_OPPORTUNITY: 'availability_integrity',
    C_INACTIVE_IN_POOL: 'availability_integrity',
    C_IDENTITY_UNRESOLVED: 'availability_integrity',
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
    C_CONSERVATION: 'integrity',
    C_FORBIDDEN_INPUT: 'integrity',
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
    C_CONSERVATION, C_FORBIDDEN_INPUT, C_IDENTITY_UNRESOLVED,
    C_INACTIVE_IN_POOL, AUD.C_INACTIVE_OWNS_OPPORTUNITY,
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
                          'small cannot invert a room.'},
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
    share = dossier.value('carry_share') or dossier.value('target_share') or 0.0
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
        'team_opportunity_share': float(share) >= (
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
                         'team_opportunity_share': round(float(share), 6),
                         'projection_disagreement': round(gap, 4),
                         'in_optimizer_pool': bool(in_optimizer_pool)},
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
def evaluate(report: Optional[Dict[str, Any]], *,
             dossiers: Sequence[Any] = (),
             projection_digest: Optional[str] = None,
             optimizer_pool_ids=None,
             resolved_conflict_codes=None,
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

    rows: List[Dict[str, Any]] = []
    for c in list(report.get('conflicts', [])) + list(extra_conflicts):
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
        mat = materiality(d, c, in_optimizer_pool=c.get('gsis_id') in pool)
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
