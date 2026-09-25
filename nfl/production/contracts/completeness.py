"""No stage may emit an apparently complete artifact without proving coverage.

THE INVARIANT THIS FILE EXISTS TO ENFORCE

    A join that does not report its coverage is indistinguishable from a join
    that lost half its rows.

On 2026-09-24 a Showdown portfolio was built from 27 of 29 available players.
Both kickers were modelled, in their own layer, and the selector's universe was
assembled from `dk_scoring` alone. Nothing raised. No test failed. The artifact
said ten lineups and meant ten lineups drawn from an incomplete contest.

That was not an unlucky omission, it was the repository's most expensive failure
class in its purest form: **a step returned something partial and the caller
read it as complete.** Eleven of thirteen errors recorded on 2026-09-24 were
that same shape. This module is that lesson turned into machinery, so the next
instance is caught before kickoff by a contract rather than afterwards by
somebody noticing.

WHAT A JOIN MUST REPORT

Every field below is mandatory, because each one distinguishes a different
failure that the others hide:

    expected_keys         what the consumer declared it needs. Not what it got.
    present_keys          what reached the output.
    missing_left          expected and absent from the DEMAND side. A contest
                          requirement the universe file never listed.
    missing_right         expected and absent from the SUPPLY side. The kicker
                          case: priced, active, and never modelled.
    dropped_rows          present upstream, filtered out during the join. A
                          silent drop is worse than an absence, because the data
                          existed and a decision discarded it.
    unmatched_identities  keys that exist on both sides under names that did not
                          resolve. Never guessed, never matched on position and
                          team.
    coverage              |present| / |expected|. A single number for a dashboard
                          and never a substitute for the sets above.

SEVERITY IS THE CONSUMER'S, NOT THE JOIN'S

The same 93% coverage is fatal for a lineup selector and unremarkable for a
research diagnostic. So completeness is not a property of the join, it is a
contract between a join and a named consumer, and the DEFAULT IS REFUSAL. A
consumer that tolerates partial input must say so in `CONSUMER_POLICY` with a
written reason. A consumer nobody has thought about refuses, which is the
correct behaviour for a consumer nobody has thought about.

WHAT THIS MODULE DELIBERATELY DOES NOT DO

It does not fill gaps, redistribute missing mass, or substitute a prior for an
absent player. Those are modelling decisions with their own evidence
requirements. This module's only job is to make an incomplete join impossible to
mistake for a complete one.
"""
from __future__ import annotations

SPEC_VERSION = 'join-completeness/1.0.0'

#: A consumer that must have every expected key. The default for anything not
#: listed in CONSUMER_POLICY.
REQUIRES_COMPLETE = 'REQUIRES_COMPLETE'

#: A consumer that may proceed on partial input. Requires a written reason.
PERMITS_PARTIAL = 'PERMITS_PARTIAL'

#: Consumer id -> (policy, reason). The reason is mandatory for PERMITS_PARTIAL
#: and must say what the consumer does about the gap, not merely that it exists.
CONSUMER_POLICY = {
    # Products. A contest the model cannot cover is not a contest we searched.
    'dfs.showdown.selector': (REQUIRES_COMPLETE, None),
    'dfs.classic.selector': (REQUIRES_COMPLETE, None),
    'product.board': (REQUIRES_COMPLETE, None),
    'postgame.grade_portfolios': (REQUIRES_COMPLETE, None),

    # Diagnostics. These EXIST to describe gaps, so refusing on a gap would
    # make them useless; each says what it does with the incompleteness.
    'research.diagnostic': (
        PERMITS_PARTIAL,
        'a diagnostic reports the gap as its result and stakes nothing on it'),
    'tools.pool_audit': (
        PERMITS_PARTIAL,
        'its output IS the list of players the model cannot cover'),
    'tools.cross_layer_audit': (
        PERMITS_PARTIAL,
        'it enumerates incomplete joins and must be able to read one'),
}


class JoinIncomplete(RuntimeError):
    """A consumer requiring complete input was handed a partial join."""


class PolicyUndeclared(RuntimeError):
    """PERMITS_PARTIAL was recorded without a reason."""


def policy_for(consumer: str) -> tuple:
    """(policy, reason) for `consumer`. Unknown consumers REQUIRE completeness.

    The default is deliberate. A new consumer added by somebody who has not
    thought about coverage gets the safe behaviour, not the convenient one.
    """
    pol, reason = CONSUMER_POLICY.get(consumer, (REQUIRES_COMPLETE, None))
    if pol == PERMITS_PARTIAL and not reason:
        raise PolicyUndeclared(
            f'{consumer!r} permits partial input with no reason recorded. '
            f'A permission without a reason is how a gap becomes permanent.')
    return pol, reason


def join_report(join_id: str, expected_keys, left_keys, right_keys,
                present_keys, unmatched_identities=(), left_name='left',
                right_name='right') -> dict:
    """Build the mandatory coverage record for one join.

    `expected_keys` is the consumer's declared requirement. Passing the keys
    you happen to have produces a report that always reads complete, which is
    the failure this module exists to prevent, so expected is never derived
    from present.
    """
    exp = set(expected_keys)
    left, right, present = set(left_keys), set(right_keys), set(present_keys)
    if not exp:
        raise JoinIncomplete(
            f'{join_id}: expected_keys is empty. An empty requirement makes '
            f'every join complete by construction and is never a valid input.')
    stray = present - exp
    missing_right = sorted(exp - right)
    dropped = sorted((exp & left & right) - present)
    return {
        'spec_version': SPEC_VERSION,
        'join_id': join_id,
        'left_name': left_name,
        'right_name': right_name,
        'n_expected': len(exp),
        'n_present': len(present),
        'expected_keys': sorted(exp),
        'present_keys': sorted(present),
        'missing_left': sorted(exp - left),
        'missing_right': missing_right,
        'dropped_rows': dropped,
        'unmatched_identities': sorted(unmatched_identities),
        'present_not_expected': sorted(stray),
        'coverage': (len(exp & present) / len(exp)),
        'complete': not (exp - present) and not unmatched_identities,
    }


def assert_complete(report: dict, consumer: str) -> dict:
    """Return `report`, or raise JoinIncomplete for a consumer that needs all.

    The message names the join, the consumer, the coverage and WHICH SIDE the
    keys went missing on, because "94% coverage" does not tell an operator
    whether a source truncated or a model has no row.
    """
    pol, reason = policy_for(consumer)
    out = dict(report, consumer=consumer, policy=pol, policy_reason=reason)
    if report['complete'] or pol == PERMITS_PARTIAL:
        out['verdict'] = 'COMPLETE' if report['complete'] else 'PARTIAL_PERMITTED'
        return out
    bits = []
    for field, sense in (('missing_right', 'never produced upstream'),
                         ('missing_left', 'absent from the demand side'),
                         ('dropped_rows', 'present upstream and dropped here'),
                         ('unmatched_identities', 'identity unresolved')):
        v = report.get(field) or []
        if v:
            shown = ', '.join(map(str, v[:6]))
            more = f' (+{len(v) - 6} more)' if len(v) > 6 else ''
            bits.append(f'{field} [{sense}]: {shown}{more}')
    raise JoinIncomplete(
        f"{report['join_id']}: {consumer} requires complete input and coverage "
        f"is {report['coverage']:.1%} "
        f"({report['n_present']} of {report['n_expected']}). "
        + ' | '.join(bits))
