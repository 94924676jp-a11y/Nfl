"""Why the pool got smaller. A typed ledger, not a count.

TWO KINDS OF EXCLUSION, AND THEY ARE NOT THE SAME THING

    GOVERNANCE   this player MAY NOT enter the pool. He is not legally or
                 semantically eligible: the football state says he will not
                 play, the review blocked him, his identity is unresolved.
    STRATEGY     this player COULD enter and the caller chose not to use
                 him: an explicit exclude, a projection cutoff, an exposure
                 decision.

Collapsing them loses the only distinction that matters. "Six players were
excluded" is compatible with a safe pool and with a broken one; "one player
was removed because his club declared him OUT, and five because the caller
set a projection cutoff" is not. A governance exclusion is a protection
working. A strategy exclusion is a preference.

AND AN EXCLUSION MUST NOT DISAPPEAR. A player silently dropped is
indistinguishable from a player who was never there, which is how a
protection stops being observable. Every removal is recorded with the
canonical state that justified it.
"""
from __future__ import annotations

import collections
import dataclasses
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

SPEC_VERSION = 'nfl-dfs-exclusion-ledger-0'

GOVERNANCE = 'GOVERNANCE'
STRATEGY = 'STRATEGY'
KINDS = (GOVERNANCE, STRATEGY)

# --- reasons, each with its kind -------------------------------------------
WILL_NOT_PLAY = 'WILL_NOT_PLAY'
BLOCKED_BY_REVIEW = 'BLOCKED_BY_REVIEW'
IDENTITY_UNRESOLVED = 'IDENTITY_UNRESOLVED'
NO_DK_POSITION = 'NO_DK_POSITION'
NO_DK_ID = 'NO_DK_ID'
NO_RESOLVED_SALARY = 'NO_RESOLVED_SALARY'
NO_PROJECTION = 'NO_PROJECTION'
PROJECTION_CUTOFF = 'PROJECTION_CUTOFF'
EXPLICIT_USER_EXCLUDE = 'EXPLICIT_USER_EXCLUDE'
EXPOSURE_DECISION = 'EXPOSURE_DECISION'

#: NO_DK_POSITION, NO_DK_ID, NO_RESOLVED_SALARY and NO_PROJECTION are
#: GOVERNANCE, not strategy: a player DraftKings will not accept, or one the
#: model wrote no number for, is not a player the caller declined to use. He
#: cannot lawfully be in a lineup at all.
REASON_KIND: Dict[str, str] = {
    WILL_NOT_PLAY: GOVERNANCE,
    BLOCKED_BY_REVIEW: GOVERNANCE,
    IDENTITY_UNRESOLVED: GOVERNANCE,
    NO_DK_POSITION: GOVERNANCE,
    NO_DK_ID: GOVERNANCE,
    NO_RESOLVED_SALARY: GOVERNANCE,
    NO_PROJECTION: GOVERNANCE,
    PROJECTION_CUTOFF: STRATEGY,
    EXPLICIT_USER_EXCLUDE: STRATEGY,
    EXPOSURE_DECISION: STRATEGY,
}

FROM_SIMULATION = 'simulation'
FROM_OPTIMIZER = 'optimizer'
FROM_BOTH = 'both'


@dataclass(frozen=True)
class Exclusion:
    """One player removed from one population, with the reason and evidence."""
    gsis_id: Optional[str]
    name: Optional[str]
    team: Optional[str]
    reason: str
    kind: str
    excluded_from: str
    availability: Optional[str] = None
    evidence_grade: Optional[str] = None
    state_identity: Optional[Dict[str, Any]] = None
    detail: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass
class ExclusionLedger:
    """Every removal, kept apart by kind so neither can hide the other."""
    entries: List[Exclusion] = field(default_factory=list)
    spec_version: str = SPEC_VERSION

    def add(self, **kw) -> Exclusion:
        reason = kw.get('reason')
        if reason not in REASON_KIND:
            raise AssertionError(
                f'{reason!r} is not a declared exclusion reason. An '
                f'undeclared reason cannot be classified GOVERNANCE or '
                f'STRATEGY, and an unclassified exclusion is exactly the '
                f'thing this ledger exists to prevent.')
        kw.setdefault('kind', REASON_KIND[reason])
        kw.setdefault('excluded_from', FROM_OPTIMIZER)
        e = Exclusion(**kw)
        self.entries.append(e)
        return e

    def of_kind(self, kind: str) -> List[Exclusion]:
        return [e for e in self.entries if e.kind == kind]

    def by_reason(self) -> Dict[str, int]:
        return dict(collections.Counter(e.reason for e in self.entries))

    def as_dict(self) -> Dict[str, Any]:
        gov, strat = self.of_kind(GOVERNANCE), self.of_kind(STRATEGY)
        return {
            'spec_version': self.spec_version,
            'n_excluded': len(self.entries),
            'n_governance': len(gov),
            'n_strategy': len(strat),
            'by_reason': self.by_reason(),
            'by_kind_and_reason': {
                GOVERNANCE: dict(collections.Counter(e.reason for e in gov)),
                STRATEGY: dict(collections.Counter(e.reason for e in strat)),
            },
            'governance': [e.as_dict() for e in gov],
            'strategy': [e.as_dict() for e in strat],
            'what_the_two_mean': {
                GOVERNANCE: 'this player MAY NOT enter the pool',
                STRATEGY: 'this player COULD enter and was not used',
            },
        }
