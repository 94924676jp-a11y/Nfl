"""The eight football support states, and the two salary-identity states.

WHY THESE ARE A CLOSED SET

Blueprint 1.2: no player silently disappears. Every player in the
authoritative football universe lands in exactly ONE state, and "absent from
the board" is not one of them. A player the model cannot support is
MODEL_UNSUPPORTED -- a fact with a name -- rather than a row that was never
written.

SALARY IDENTITY IS A SEPARATE AXIS AND MUST STAY THAT WAY

A DraftKings salary row that will not resolve to a gsis_id is not a missing
football forecast, and a player with no salary row is not unsupported by the
model. Week 2 produced both cases on the same slate: Davon Booth was ACTIVE
with a salary row and NO football row, and "Drew Ogletree" had a football row
under the club-declared name with NO salary link. Collapsing the two axes
turns one into the other. They are different dictionaries here and nothing
joins them except a downstream reader that asks for both.
"""
from __future__ import annotations

#: Football support states. Order is the assignment PRECEDENCE used by
#: `player_universe.classify`: the first that applies wins, because a player
#: who is officially inactive is officially inactive whatever else is true of
#: him.
PROJECTED = 'PROJECTED'
OFFICIALLY_INACTIVE = 'OFFICIALLY_INACTIVE'
EVIDENCE_DEFERRED = 'EVIDENCE_DEFERRED'
IDENTITY_UNRESOLVED = 'IDENTITY_UNRESOLVED'
MODEL_UNSUPPORTED = 'MODEL_UNSUPPORTED'
OUTSIDE_SUPPORTED_POSITION = 'OUTSIDE_SUPPORTED_POSITION'
ROSTERED_BUT_NOT_EXPECTED_TO_PARTICIPATE = (
    'ROSTERED_BUT_NOT_EXPECTED_TO_PARTICIPATE')
REMOVED_BY_GOVERNED_RULE = 'REMOVED_BY_GOVERNED_RULE'

FOOTBALL_STATES = (
    PROJECTED, OFFICIALLY_INACTIVE, EVIDENCE_DEFERRED, IDENTITY_UNRESOLVED,
    MODEL_UNSUPPORTED, OUTSIDE_SUPPORTED_POSITION,
    ROSTERED_BUT_NOT_EXPECTED_TO_PARTICIPATE, REMOVED_BY_GOVERNED_RULE,
)

#: Salary identity. Downstream metadata; never a football state.
SALARY_IDENTITY_RESOLVED = 'SALARY_IDENTITY_RESOLVED'
SALARY_IDENTITY_UNRESOLVED = 'SALARY_IDENTITY_UNRESOLVED'
SALARY_STATES = (SALARY_IDENTITY_RESOLVED, SALARY_IDENTITY_UNRESOLVED)

#: States in which a player IS expected on the field and the model therefore
#: owes a row. Everything outside this set is accounted for by a reason.
EXPECTED_TO_PLAY = (PROJECTED, MODEL_UNSUPPORTED, EVIDENCE_DEFERRED)

#: The football positions this engine models. A player outside them is
#: OUTSIDE_SUPPORTED_POSITION -- a declared scope limit, not a defect.
#:
#: FB IS INCLUDED DELIBERATELY AND SAYS NOTHING ABOUT WORKLOAD. A fullback is
#: a supported position because the engine can carry a row for him; whether
#: he should receive a lead back's carries is a ROLE question and P0-B does
#: not answer it. Ben VanSumeren must appear here with his depth-chart
#: evidence attached and his workload untouched.
SUPPORTED_POSITIONS = ('QB', 'RB', 'FB', 'WR', 'TE', 'K')

#: Roster `status` codes that mean the player is on the active game-day roster.
#: Anything else is ROSTERED_BUT_NOT_EXPECTED_TO_PARTICIPATE, which is a
#: statement about the roster and NOT an inference about availability: an
#: elevation is a transaction and this module does not have one.
ACTIVE_ROSTER_STATUS = ('ACT',)

#: Availability evidence tiers, blueprint 8. Tier 9 is inference and may never
#: be the governing evidence for a state.
EVIDENCE_TIERS = {
    1: 'official inactive list',
    2: 'official team or league status',
    3: 'transaction / roster status',
    4: 'practice report',
    5: 'depth chart',
    6: 'trusted reporter',
    7: 'owner screenshot',
    8: 'secondary summary',
    9: 'inference -- FORBIDDEN as governing evidence',
}
