"""Prediction-time eligibility, and the debt that stands in for it. Directive 3 §6.

THE GAP, MEASURED

A forecast needs to know, before kickoff, who is eligible to play. The only
eligibility-shaped field in the reachable data is `weekly_rosters.status`, and it
is a POST-HOC GAMEDAY OUTCOME: ACT -> 0.9715 snap rate, INA -> 0 of 3,438,
DEV -> 3 of 8,306. It is a near-perfect predictor of playing that only exists
afterwards. It is quarantined in `allowlist.py`.

Nothing reachable from this environment replaces it. Official transactions and
the inactives feed would close or partly close it, and neither is reachable here.

WHY A DEBT AND NOT A HEURISTIC

The tempting move is depth-chart rank or last week's snaps as a proxy, and call
eligibility solved. That would be a fabricated input wearing the name of a
measured one -- and it would be invisible, because a plausible eligibility list
produces plausible projections. Directive 3 §6 forbids it explicitly.

So eligibility is represented by an explicit refusal that a consumer must handle.
A component that needs gameday eligibility REFUSES until a prediction-time source
exists. A component that does not need it -- the NFL-1 team-level baseline does
not -- is unaffected, and that asymmetry is the point: the debt blocks exactly
what it should and nothing else.
"""
from __future__ import annotations

import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

CODE = 'PREDICTION_TIME_ELIGIBILITY_UNAVAILABLE'

# Sources that WOULD satisfy it. None is reachable from this environment; each is
# an assignment, and the list is here so closing the debt is a matter of adding a
# source rather than remembering what was needed.
CLOSING_SOURCES = (
    'official inactives feed (~90 min pre-kickoff; resolves Questionable to 0/1)',
    'official transactions feed (elevations, signings, IR moves)',
    'official gameday active/inactive designation at its publication time',
)


def require_prediction_time_eligibility(component: str,
                                        source_available: bool = False,
                                        source_name: str = '') -> Outcome:
    """Call this wherever gameday eligibility is needed.

    Returns BLOCKED until a genuine prediction-time source is wired in. BLOCKED
    rather than FAIL because nothing is broken -- the input does not exist yet,
    and per DEC-029 that is assigned rather than blocked for the project.
    """
    if source_available and source_name:
        # The escape hatch has to be guarded or it IS the substitution Directive
        # 3 forbids. Without this check the call accepted any non-empty string --
        # including 'weekly_rosters.status', the exact post-hoc field this
        # module's docstring quarantines (INA -> 0 snaps of 3,438).
        if source_name not in CLOSING_SOURCES:
            return Outcome.fail(
                'ELIGIBILITY_SOURCE_NOT_RECOGNISED',
                f'{component}: {source_name!r} is not a declared prediction-time '
                f'eligibility source, so it cannot close this debt. Declared '
                f'sources: {list(CLOSING_SOURCES)}. If a genuine new source '
                f'exists, add it to CLOSING_SOURCES deliberately -- passing its '
                f'name here is how a post-hoc field gets substituted for a '
                f'prediction-time one.',
                component=component, offered=source_name,
                closing_sources=list(CLOSING_SOURCES))
        return Outcome.ok(
            'PREDICTION_TIME_ELIGIBILITY_AVAILABLE', value=source_name,
            detail=f'{component}: eligibility supplied by {source_name}.',
            component=component)
    return Outcome.blocked(
        CODE,
        f'{component} requires gameday eligibility at prediction time, and no '
        f'prediction-time source exists. weekly_rosters.status is post-hoc '
        f'(INA -> 0 snaps of 3,438) and is quarantined; substituting a depth '
        f'chart or last week\'s snaps would fabricate the input rather than '
        f'supply it. Closes when one of: {"; ".join(CLOSING_SOURCES)}.',
        cause=Cause.DEPENDENCY, component=component,
        closing_sources=list(CLOSING_SOURCES))


def component_needs_eligibility(component: str) -> bool:
    """Declared, not inferred. NFL-1's team-level baseline consumes prior-season
    team scores only and is deliberately outside the debt."""
    return component not in ('nfl1_coldstart_team_baseline',)
