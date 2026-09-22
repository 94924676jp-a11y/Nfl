"""The weekly DFS workflow as named stages, each with its own permissions.

WHAT THIS IS AND IS NOT

It is a REGISTRY, not a scheduler. Each stage declares what it needs, what it
may produce, and -- the part that matters -- whether it is allowed to generate
a projection or run an optimizer at all. Automation comes later; the
permissions are what stop a Tuesday placeholder board being treated as a
Sunday final one.

WHY PERMISSIONS BELONG ON THE STAGE

A Monday board is built before any practice report exists. It is a useful
artifact and a dangerous one: it looks exactly like a Sunday board. So
EARLY_BOARD declares `may_optimize = False`, and the stage gate refuses an
optimizer run against it by name rather than trusting whoever is at the
keyboard to remember what day it is.
"""
from __future__ import annotations

import pathlib
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome        # noqa: E402

SPEC_VERSION = 'nfl-dfs-workflow-stages-1'


@dataclass(frozen=True)
class Stage:
    name: str
    when: str
    purpose: str
    required_sources: Tuple[str, ...]
    optional_sources: Tuple[str, ...]
    freshness: str
    artifacts: Tuple[str, ...]
    may_project: bool
    may_optimize: bool
    note: str = ''

    def as_dict(self) -> Dict[str, Any]:
        return {'name': self.name, 'when': self.when, 'purpose': self.purpose,
                'required_sources': list(self.required_sources),
                'optional_sources': list(self.optional_sources),
                'freshness': self.freshness,
                'artifacts': list(self.artifacts),
                'may_project': self.may_project,
                'may_optimize': self.may_optimize, 'note': self.note}


_S = [
    Stage('EARLY_BOARD', 'Monday / Tuesday',
          'first look at the slate: who is on it, what they did last week',
          ('schedules', 'weekly_rosters', 'depth_charts',
           'current_season_usage', 'current_season_snaps'),
          ('dk_salaries', 'injuries'),
          'current-season usage through week N-1 REQUIRED; salaries usually '
          'not posted yet',
          ('EARLY_SLATE_PLAYER_BOARD', 'player_dossiers'),
          may_project=True, may_optimize=False,
          note='explicitly a PLACEHOLDER. Salaries are typically absent, so '
               'value and optimizer eligibility are unavailable and lineups '
               'may not be built from it'),

    Stage('PRACTICE_REFRESH', 'Wednesday',
          'first injury reports and practice participation land',
          ('injuries', 'weekly_rosters', 'depth_charts'),
          ('transactions', 'dk_salaries', 'coach_news'),
          'injuries at most 24h old',
          ('player_dossiers', 'PROJECTION_CHANGE_LOG'),
          may_project=True, may_optimize=False,
          note='role risers and fallers are identified here; transactions '
               'and coach news are UNAVAILABLE in this checkout and are '
               'listed as optional rather than pretended to be present'),

    Stage('DEEP_RESEARCH', 'Thursday / Friday',
          'player-by-player review across every game on the slate',
          ('player_dossiers', 'current_season_usage', 'current_season_snaps',
           'depth_charts', 'injuries'),
          ('routes', 'personnel', 'dk_salaries'),
          'all current-season sources through week N-1',
          ('SLATE_REVIEW', 'projection_audit', 'deep_research_queue'),
          may_project=True, may_optimize=False,
          note='the escalation queue is produced here on IMPACT x '
               'DISAGREEMENT x UNCERTAINTY'),

    Stage('SATURDAY_BOARD', 'Saturday',
          'provisional final board, subject to Sunday inactives',
          ('dk_salaries', 'injuries', 'depth_charts', 'weekly_rosters',
           'current_season_usage', 'current_season_snaps'),
          ('weather', 'transactions'),
          'injuries at most 24h old; salaries posted',
          ('SATURDAY_FINAL_CANDIDATE_BOARD', 'PLAYER_BOARD',
           'PROJECTION_CHANGE_LOG'),
          may_project=True, may_optimize=True,
          note='lineups may be built, but every one is provisional until the '
               'official inactive board lands'),

    Stage('T_MINUS_180', 'Sunday, 3h to kickoff',
          'refresh before the inactive window opens',
          ('injuries', 'weekly_rosters', 'dk_salaries'),
          ('weather',),
          'injuries at most 6h old',
          ('PLAYER_BOARD', 'PROJECTION_CHANGE_LOG'),
          may_project=True, may_optimize=True),

    Stage('T_MINUS_120', 'Sunday, 2h to kickoff',
          'refresh; early inactives begin to appear',
          ('injuries', 'weekly_rosters', 'dk_salaries'),
          ('official_inactives', 'weather'),
          'injuries at most 6h old',
          ('PLAYER_BOARD', 'PROJECTION_CHANGE_LOG'),
          may_project=True, may_optimize=True),

    Stage('T_MINUS_90', 'Sunday, 90m to kickoff',
          'the inactive window: most declarations land here',
          ('injuries', 'weekly_rosters', 'dk_salaries'),
          ('official_inactives', 'weather'),
          'injuries at most 6h old',
          ('PLAYER_BOARD', 'PROJECTION_CHANGE_LOG'),
          may_project=True, may_optimize=True),

    Stage('OFFICIAL_INACTIVES', 'Sunday, ~90m to kickoff',
          'the official board is complete: hard-zero and REDISTRIBUTE',
          ('official_inactives', 'weekly_rosters', 'depth_charts',
           'dk_salaries'),
          (),
          'the inactive board must be COMPLETE for the games in scope -- a '
          'partial board cannot distinguish ACTIVE from not-yet-declared',
          ('PLAYER_BOARD', 'redistribution_accounting',
           'PROJECTION_CHANGE_LOG'),
          may_project=True, may_optimize=True,
          note='opportunity is REDISTRIBUTED, never merely removed, and the '
               'accounting must conserve'),

    Stage('FINAL_PRELOCK', 'Sunday, minutes to lock',
          'last refresh and the lineups that are actually entered',
          ('official_inactives', 'dk_salaries', 'PLAYER_BOARD',
           'SLATE_REVIEW'),
          ('weather',),
          'everything current as of the last refresh; the review must match '
          'the projection artifact being consumed',
          ('CLASSIC_PORTFOLIO', 'DK_ENTRIES_CSV', 'PROJECTION_CHANGE_LOG'),
          may_project=True, may_optimize=True),
]

STAGES: Dict[str, Stage] = {s.name: s for s in _S}
ORDER: Tuple[str, ...] = tuple(s.name for s in _S)


def get(name: str) -> Outcome:
    if name not in STAGES:
        return Outcome.fail(
            'UNKNOWN_WORKFLOW_STAGE',
            f'{name!r} is not a declared stage. Declared: {list(ORDER)}. An '
            f'undeclared stage has no permissions, and defaulting it to '
            f'"allowed" is how a Tuesday board becomes a Sunday lineup.',
            value=name)
    return Outcome.ok('WORKFLOW_STAGE', STAGES[name].as_dict(),
                      detail=f'{name} ({STAGES[name].when})')


def assert_may_optimize(stage_name: str) -> Outcome:
    """The stage gate. Called before any lineup is built."""
    s = get(stage_name)
    if s.state.name != 'PASS':
        return s
    st = STAGES[stage_name]
    if not st.may_optimize:
        return Outcome.blocked(
            'STAGE_MAY_NOT_OPTIMIZE',
            f'{stage_name} ({st.when}) is a research stage and may not '
            f'produce lineups. {st.note or st.purpose}',
            cause=Cause.GOVERNANCE,
            value={'stage': stage_name, 'may_project': st.may_project})
    return Outcome.ok('STAGE_MAY_OPTIMIZE', {'stage': stage_name},
                      detail=f'{stage_name} may build lineups')


def assert_may_project(stage_name: str) -> Outcome:
    s = get(stage_name)
    if s.state.name != 'PASS':
        return s
    st = STAGES[stage_name]
    if not st.may_project:
        return Outcome.blocked(
            'STAGE_MAY_NOT_PROJECT',
            f'{stage_name} may not generate projections.',
            cause=Cause.GOVERNANCE, value={'stage': stage_name})
    return Outcome.ok('STAGE_MAY_PROJECT', {'stage': stage_name},
                      detail=f'{stage_name} may project')


def board() -> Dict[str, Any]:
    """The whole workflow, for a reader or an artifact."""
    return {'spec_version': SPEC_VERSION, 'order': list(ORDER),
            'stages': {n: STAGES[n].as_dict() for n in ORDER},
            'automation': 'MANUAL_TRIGGER. Scheduling is deliberately not '
                          'implemented yet; the permissions above are the '
                          'part that has to be right first.'}
