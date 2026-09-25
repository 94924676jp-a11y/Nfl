"""A fired gate stops the consumer. Detection was never the missing piece.

THE GAP THIS CLOSES

`pregame_readiness.build()` ends its own output with the sentence *"This is a
report; it decides nothing."* That was honest and it was the whole problem. On
2026-09-24 the board had already refused with `NFL1_NOT_AUTHORIZED`;
`AUTHORITATIVE_INACTIVE_NONZERO_OPPORTUNITY` stood at INSUFFICIENT_EVIDENCE;
`HEALTHY_QB1_ZERO_OPPORTUNITY_ANOMALY` had fired on a QB1 carrying
P(zero dropbacks) = 0.412 against a realised 0 of 128. Every one of those
described a failure that then occurred, and a DFS selector consumed the state
anyway, because nothing obliged it to ask.

So this module owns exactly one decision: **may this consumer proceed given the
gate verdicts that were actually evaluated?**

THREE STATES THAT MUST NOT COLLAPSE

    FAILED            the gate ran and found the thing it looks for.
    NOT_EXERCISED     the gate ran and the condition was absent, so there was
                      nothing to catch. Safe to proceed on, and NOT evidence
                      that the mechanism works.
    NOT_CHECKED       the gate did not run. This is the one that gets read as a
                      pass, and it is the reason `FRESH` once meant "nobody
                      looked". For a consumer requiring established gates it
                      blocks.

The distinction between the last two is the whole care of this file. "Nobody was
declared out, so the removal path had nothing to remove" is a different fact from
"nobody evaluated whether the removal path works", and only the second is a hole.

SEVERITY IS DECLARED, NOT INFERRED

`SEVERITY` names each gate HARD or DIAGNOSTIC. Promoting a gate is an owner
decision, and `unavailable_owns_nothing` is recorded DIAGNOSTIC here because that
promotion has been requested and not granted. This module enforces whatever the
table says; it does not promote anything on its own.
"""
from __future__ import annotations

SPEC_VERSION = 'dfs-gate-enforcement/1.0.0'

FAILED = 'FAILED'
PASSED = 'PASSED'
NOT_EXERCISED = 'NOT_EXERCISED'
NOT_CHECKED = 'NOT_CHECKED'

HARD = 'HARD'
DIAGNOSTIC = 'DIAGNOSTIC'

#: gate id -> severity. Owner ruling required to move a row to HARD.
SEVERITY = {
    'pregame_readiness.execution': HARD,
    'authoritative_inactive_nonzero_opportunity': HARD,
    'healthy_qb1_zero_opportunity_anomaly': HARD,
    'board_authorization': HARD,
    # Promotion to HARD requested 2026-09-24, not yet granted.
    'unavailable_owns_nothing': DIAGNOSTIC,
    'conditioning_contract': DIAGNOSTIC,
    'source_census.invariance': DIAGNOSTIC,
}

#: Consumers that stake nothing on the state and may therefore run against a
#: broken one. A diagnostic exists to DESCRIBE a failure, so refusing it on that
#: failure would make a failing game the one game nobody can audit. They still
#: receive the full decision record, including every failed gate.
#:
#: Anything absent from this set requires gates to be established AND passing,
#: because a consumer nobody has classified should get the safe behaviour.
STAKES_NOTHING = frozenset({
    'research.diagnostic',
    'tools.pool_audit',
    'tools.cross_layer_audit',
})


class ConsumptionRefused(RuntimeError):
    """A HARD gate failed, or was never evaluated for a consumer needing it."""



class GateUnknown(RuntimeError):
    """A verdict was supplied for a gate with no declared severity."""


def classify_unavailable_owns_nothing(verdict: dict | None) -> str:
    """Map that check's own vocabulary onto the three states, carefully.

    Its `NOT_APPLICABLE` / `NO_PLAYER_DECLARED_UNAVAILABLE` means the condition
    was absent, which is NOT_EXERCISED -- there was nothing to catch and nothing
    unsafe. Its own docstring warns this must not be read as proof the removal
    path works, and that warning is about the MECHANISM, not about this game.
    Recording it as NOT_EXERCISED keeps both facts: proceed now, cite nothing
    later.
    """
    if not verdict:
        return NOT_CHECKED
    state = verdict.get('state')
    if state == 'FAIL':
        return FAILED
    if state == 'NOT_APPLICABLE':
        return NOT_EXERCISED
    if state == 'PASS':
        return PASSED
    return NOT_CHECKED


def classify_readiness(matrix: dict | None) -> str:
    """`pregame_readiness` execution verdict, with UNKNOWN kept as NOT_CHECKED."""
    if not matrix:
        return NOT_CHECKED
    if matrix.get('execution_verdict') == 'REFUSED':
        return FAILED
    if matrix.get('unknown_layers'):
        return NOT_CHECKED
    if matrix.get('execution_verdict') == 'ELIGIBLE':
        return PASSED
    return NOT_CHECKED


def decide(verdicts: dict, consumer: str) -> dict:
    """The decision record. `verdicts` is gate id -> one of the four states."""
    for gate in verdicts:
        if gate not in SEVERITY:
            raise GateUnknown(
                f'{gate!r} has no declared severity. An unclassified gate '
                f'cannot be enforced or waived, so it is an error rather than '
                f'a default.')
    tolerant = consumer in STAKES_NOTHING
    hard = [g for g in SEVERITY if SEVERITY[g] == HARD]
    failed_hard = sorted(g for g, s in verdicts.items()
                         if s == FAILED and SEVERITY[g] == HARD)
    failed_diag = sorted(g for g, s in verdicts.items()
                         if s == FAILED and SEVERITY[g] == DIAGNOSTIC)
    unchecked_hard = sorted(
        g for g in hard if verdicts.get(g, NOT_CHECKED) == NOT_CHECKED)
    not_exercised = sorted(g for g, s in verdicts.items() if s == NOT_EXERCISED)
    rec = {
        'spec_version': SPEC_VERSION,
        'consumer': consumer,
        'stakes_nothing': tolerant,
        'verdicts': dict(sorted(verdicts.items())),
        'failed_hard': failed_hard,
        'failed_diagnostic': failed_diag,
        'unchecked_hard': unchecked_hard,
        'not_exercised': not_exercised,
        'may_consume': tolerant or (not failed_hard and not unchecked_hard),
    }
    rec['citable_as_mechanism_evidence'] = not not_exercised
    return rec


def assert_may_consume(verdicts: dict, consumer: str) -> dict:
    """Return the decision, or refuse. This is the enforcement point."""
    rec = decide(verdicts, consumer)
    if rec['may_consume']:
        return rec
    parts = []
    if rec['failed_hard']:
        parts.append('HARD gate(s) FAILED: ' + ', '.join(rec['failed_hard']))
    if rec['unchecked_hard'] and not rec['stakes_nothing']:
        parts.append(
            'HARD gate(s) NOT_CHECKED (not the same as passed): '
            + ', '.join(rec['unchecked_hard']))
    raise ConsumptionRefused(f'{consumer} may not consume this state. '
                             + ' | '.join(parts))
