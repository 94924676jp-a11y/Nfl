"""Missing is a state. Zero is an outcome. Never the same number.

THE INVARIANT THIS FILE EXISTS FOR, owner's wording 2026-09-25:

    A failed join must never silently become a football number.

It is written down because it was violated in the most damaging possible
place. Grading resolved a player's name through `frozen_board_names.json`,
which does not list either kicker, so the lookup failed, fell through to a
zero stat line, and reported `state: GRADED`. A 0.0 actual against an 8.2
projection reads as a catastrophic model miss. It was a failed name lookup,
and it would have entered the prospective ledger as evidence against the
model -- poisoning the only thing the ledger is for.

FOUR STATES THAT MUST NOT COLLAPSE, and the reason each is separate:

  MATCHED_BY_IDENTITY      the outcome row was found by gsis_id / player_id.
                           The strongest join available, and it is available
                           more often than this codebase was asking.
  MATCHED_BY_NAME          found by normalised name because the upstream
                           artifact carries NO identity. Legitimate -- the
                           PORTFOLIO csv is DraftKings entry format with no
                           id anywhere -- and never a substitute for an id
                           that exists.
  ABSENCE_RESOLVED_TO_ZERO a GOVERNED zero: the outcome covers his club and
                           records no production for him, so zero is the
                           measurement. `outcome.resolve_absent` decides this
                           and names it ZERO_NO_RECORDED_PRODUCTION.
  IDENTITY_NOT_ESTABLISHED neither an id nor a resolvable name. NOT GRADEABLE.
                           This is the state the kickers were silently given a
                           zero in instead of.

  PLAYER_NOT_IN_OUTCOME    the outcome has no row for him at all, and his club
                           is not covered either. NOT GRADEABLE.

And the value-level distinction, which is the one that was lost:

  REAL_ZERO                a MATCHED row whose stats are genuinely zero. Ray
                           Davis: projected 7.16, actual 0.0, present in the
                           outcome as 00-0039875 with every stat zero. He was
                           active and did nothing. That is a real model miss
                           and the model owns it.

A zero from REAL_ZERO and a zero from a failed join are the same float and
opposite facts. Collapsing them lets a wiring defect masquerade as model
error, which is the one confusion that makes every downstream measurement
untrustworthy.
"""
from __future__ import annotations

SPEC_VERSION = 'nfl-join-provenance-1'

#: How the actual was obtained. Exactly one applies to any row.
MATCHED_BY_IDENTITY = 'MATCHED_BY_IDENTITY'
MATCHED_BY_NAME = 'MATCHED_BY_NAME'
ABSENCE_RESOLVED_TO_ZERO = 'ABSENCE_RESOLVED_TO_ZERO'
IDENTITY_NOT_ESTABLISHED = 'IDENTITY_NOT_ESTABLISHED'
PLAYER_NOT_IN_OUTCOME = 'PLAYER_NOT_IN_OUTCOME'

JOINS = (MATCHED_BY_IDENTITY, MATCHED_BY_NAME, ABSENCE_RESOLVED_TO_ZERO,
         IDENTITY_NOT_ESTABLISHED, PLAYER_NOT_IN_OUTCOME)

#: The only joins under which a row may carry a graded number at all.
GRADEABLE = frozenset({MATCHED_BY_IDENTITY, MATCHED_BY_NAME,
                       ABSENCE_RESOLVED_TO_ZERO})

#: Why a zero is a zero. Required whenever a graded actual is 0.
REAL_ZERO = 'REAL_ZERO'
ZERO_BASES = (REAL_ZERO, ABSENCE_RESOLVED_TO_ZERO)


class AnonymousZero(RuntimeError):
    """A graded number whose provenance is not stated. The named defect."""


class JoinNotDeclared(RuntimeError):
    """A graded row that does not say how it was joined."""


def stamp(join: str, *, key=None, zero_basis: str = None) -> dict:
    """The provenance block a graded row carries.

    `key` is the thing that actually matched -- the gsis_id, or the normalised
    name -- so a reader can reproduce the join rather than trust it.
    """
    if join not in JOINS:
        raise JoinNotDeclared(f'{join!r} is not one of {JOINS}')
    if zero_basis is not None and zero_basis not in ZERO_BASES:
        raise AnonymousZero(f'{zero_basis!r} is not one of {ZERO_BASES}')
    out = {'spec_version': SPEC_VERSION, 'join': join}
    if key is not None:
        out['matched_on'] = str(key)
    if zero_basis is not None:
        out['zero_basis'] = zero_basis
    return out


def assert_graded_row(row: dict, *, actual, where: str = 'row') -> dict:
    """Every graded row proves how its actual arrived. No exceptions.

    Called at the point a row is emitted rather than in a later audit, because
    an audit that runs afterwards cannot recover the join that was used -- the
    information is gone by then, which is exactly why the kicker zeros looked
    like football.
    """
    prov = (row or {}).get('join_provenance') or {}
    join = prov.get('join')
    if not join:
        raise JoinNotDeclared(
            f'{where}: a graded row carries no join_provenance. A number with '
            f'no stated origin cannot be told apart from a failed lookup, and '
            f'this is the row that enters the prospective ledger.')
    if join not in GRADEABLE:
        raise AnonymousZero(
            f'{where}: join is {join}, which is NOT gradeable. The row must be '
            f'reported unscorable rather than given a number -- a failed join '
            f'must never become a football number.')
    if actual is not None and float(actual) == 0.0 \
            and prov.get('zero_basis') not in ZERO_BASES:
        raise AnonymousZero(
            f'{where}: actual is 0.0 with no zero_basis. A real zero and a '
            f'failed join are the same float and opposite facts; say which '
            f'one this is ({ZERO_BASES}).')
    return prov


def audit_rows(rows, *, stat: str = 'dk_points') -> dict:
    """Count provenance across a graded set, for a report rather than a gate.

    Refuses nothing. A tally is how a slow drift gets noticed -- a rising
    MATCHED_BY_NAME share means identity is being lost upstream, which is a
    real signal and not an error in any single row.
    """
    by_join, anonymous, zeros = {}, [], {}
    for r in rows or ():
        st = (r.get('stats') or {}).get(stat) or {}
        if st.get('state') != 'GRADED':
            continue
        prov = r.get('join_provenance') or {}
        j = prov.get('join') or 'UNDECLARED'
        by_join[j] = by_join.get(j, 0) + 1
        act = st.get('actual')
        if j == 'UNDECLARED' or j not in GRADEABLE:
            anonymous.append(r.get('player'))
        elif act is not None and float(act) == 0.0:
            b = prov.get('zero_basis') or 'UNDECLARED'
            zeros[b] = zeros.get(b, 0) + 1
            if b == 'UNDECLARED':
                anonymous.append(r.get('player'))
    return {'spec_version': SPEC_VERSION, 'by_join': by_join,
            'graded_zeros_by_basis': zeros,
            'anonymous': sorted(x for x in anonymous if x),
            'clean': not anonymous}
