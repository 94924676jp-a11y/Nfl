"""Typed evidence axes for the mandatory player review. One fact, one axis.

WHY THE AXES ARE SEPARATE AND STAY SEPARATE

Every defect this project has paid for came from two facts sharing a field.
A depth listing that was both "where the club ranks him" and "how much he
plays". A zero that was both "we measured none" and "we measured nothing".
A share that was both "what he had" and "what we gave him when someone left".

So each axis below carries its own value AND its own grade, and a consumer
that wants the value has to look at the grade to get it. There is no way to
read a number here without reading where it came from.

THE GRADES, IN DESCENDING AUTHORITY FOR A CURRENT-GAME CLAIM

    MEASURED        observed this season at this club, from the lawful corpus
    DECLARED        an authoritative current-game statement (inactives, the
                    club's own starting lineup) with its source and tier
    HISTORICAL      observed, but in a prior season or at another club, and
                    used only because current evidence is thin -- which the
                    row says out loud
    PRIOR           a model prior with no player-specific observation behind it
    REDISTRIBUTED   opportunity assigned because somebody else vacated it
    COLD_START      no observation of this player in this role at all
    UNAVAILABLE     the source does not exist in this checkout; NOT a zero

UNAVAILABLE IS THE ONE THAT MATTERS MOST. Routes, pass-block and run-block
snaps and personnel groupings are all UNAVAILABLE for 2026 --
`pbp_participation` returns 404 for the season and the snap file carries no
pass/run split. A dossier that silently omitted them would let a reader think
a TE's role had been examined on routes when it was examined on raw snaps.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

SPEC_VERSION = 'player-review-evidence-1'

MEASURED = 'MEASURED'
DECLARED = 'DECLARED'
HISTORICAL = 'HISTORICAL'
PRIOR = 'PRIOR'
REDISTRIBUTED = 'REDISTRIBUTED'
COLD_START = 'COLD_START'
UNAVAILABLE = 'UNAVAILABLE'
GRADES = (MEASURED, DECLARED, HISTORICAL, PRIOR, REDISTRIBUTED, COLD_START,
          UNAVAILABLE)

#: Grades that may support a current-game workload claim on their own.
SUPPORTS_CURRENT_GAME = (MEASURED, DECLARED)

# --- cold-start / uncertainty states --------------------------------------
CURRENT_ROLE_COLD_START = 'CURRENT_ROLE_COLD_START'
OFFENSIVE_DEPTH_UNKNOWN = 'OFFENSIVE_DEPTH_UNKNOWN'
CURRENT_GAME_ROLE_UNCERTAIN = 'CURRENT_GAME_ROLE_UNCERTAIN'
HISTORICAL_PRIOR_DOMINANT = 'HISTORICAL_PRIOR_DOMINANT'
EVIDENCE_SUFFICIENT = 'EVIDENCE_SUFFICIENT'

#: Evidence this project cannot obtain for 2026, named once so every dossier
#: reports the same absence the same way instead of each caller inventing a
#: blank. Registered rather than worked around.
UNAVAILABLE_SOURCES: Dict[str, str] = {
    'routes': ('nflverse pbp_participation returns 404 for 2026, so no '
               'route-level participation exists. Routes are the correct '
               'denominator for a receiving role and raw snaps are not.'),
    'routes_per_dropback': 'requires routes; see routes.',
    'pass_block_snaps': ('no pass/run split exists in the PFR snap file and '
                         'participation is unavailable.'),
    'run_block_snaps': 'same source gap as pass_block_snaps.',
    'personnel_11': ('offense_personnel lives in pbp_participation, which is '
                     '404 for 2026.'),
    'personnel_12': 'see personnel_11.',
    'personnel_13': 'see personnel_11.',
    'personnel_21': 'see personnel_11.',
    'alignment_slot_outside': 'requires participation or charting.',
    'coach_news': ('no egress from this container: nfl.com, club sites and '
                   'the open web all refuse. ASSIGNED to the '
                   'network-capable agent, see docs/AGENT_OUTBOX.md.'),
    'transactions': 'no egress; endpoint not verified. ASSIGNED.',
}


@dataclass
class Axis:
    """One evidence fact: its value, its grade, and where it came from."""
    name: str
    value: Any = None
    grade: str = UNAVAILABLE
    source: Optional[str] = None
    observed_at: Optional[str] = None
    window: Optional[str] = None
    note: Optional[str] = None

    @property
    def supports_current_game(self) -> bool:
        return self.grade in SUPPORTS_CURRENT_GAME

    def as_dict(self) -> Dict[str, Any]:
        d = {'value': self.value, 'grade': self.grade}
        for k in ('source', 'observed_at', 'window', 'note'):
            v = getattr(self, k)
            if v is not None:
                d[k] = v
        if self.grade == UNAVAILABLE and self.name in UNAVAILABLE_SOURCES:
            d['why_unavailable'] = UNAVAILABLE_SOURCES[self.name]
        return d


def unavailable(name: str) -> Axis:
    """An axis this checkout cannot fill. Never a zero, never omitted."""
    return Axis(name=name, value=None, grade=UNAVAILABLE,
                note=UNAVAILABLE_SOURCES.get(name))


@dataclass
class ProjectionComponent:
    """One number in a projection, and the evidence that produced it."""
    component: str
    value: Optional[float]
    grade: str
    derived_from: List[str] = field(default_factory=list)
    note: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return {'value': self.value, 'grade': self.grade,
                'derived_from': self.derived_from,
                **({'note': self.note} if self.note else {})}
