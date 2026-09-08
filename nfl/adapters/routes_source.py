"""Stage 16: a routes-run source adapter that FAILS CLOSED.

WHAT THIS IS: an interface contract for a licensed per-player routes-run
source, so that acquiring one later is a configuration step rather than a
redesign.

WHAT THIS IS NOT, and each of these is a deliberate absence:

  * there is NO implementation of any vendor's API;
  * there are NO sample rows, fake or real;
  * there is NO default that returns data;
  * nothing here assumes FTN, or any other vendor, has been licensed.

FTN is externally pending: an unsigned commercial agreement, with ML/model
training rights, local retention, derived-output ownership, post-termination
rights, skp_role coverage and identifier crosswalk all unresolved. This module
must not make any of that look settled.

THE FAIL-CLOSED RULE. With no licensed provider registered, every call returns
BLOCKED. There is no code path that yields routes data without a provider
having been supplied, and the test suite proves it by deleting the guard.

`nflverse.route` IS NOT ROUTES RUN. It is one route-type string per play with
no player identifier, populated on 41.8% of 2025 plays, describing the targeted
receiver only. It may never be adapted into this interface.
"""
from __future__ import annotations

import pathlib
import sys
from typing import Optional, Protocol

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

FORBIDDEN_SOURCES = {
    'nflverse.route': 'one route-type string per play, no player id, '
                      'targeted receiver only -- NOT routes run',
    'pbp_participation.route': 'same field; see above',
    'ngs_air_yards': 'quarantined: 36.31% populated in 2022, 0.00% from 2023',
}


class RoutesProvider(Protocol):
    """What a licensed provider must supply. No implementation ships here."""
    name: str
    licence_id: str
    permits_model_training: bool
    permits_local_retention: bool
    permits_derived_output_ownership: bool

    def routes_run(self, season: int, week: int) -> Outcome:
        """Per-player routes run for one week, keyed by gsis_id."""
        ...


_PROVIDER: Optional[RoutesProvider] = None


def register_provider(p: RoutesProvider) -> Outcome:
    """Accept a provider only if it declares the rights this project needs."""
    global _PROVIDER
    needed = ('permits_model_training', 'permits_local_retention',
              'permits_derived_output_ownership')
    missing = [k for k in needed if not getattr(p, k, False)]
    if missing:
        return Outcome.blocked(
            'PROVIDER_RIGHTS_INSUFFICIENT',
            f'{getattr(p, "name", "?")}: does not declare {missing}. Rights '
            f'are not inferred from silence, and a provider that cannot '
            f'confirm model-training and retention rights may not be used for '
            f'model training or retained.',
            cause=Cause.GOVERNANCE, missing=missing)
    if not getattr(p, 'licence_id', None):
        return Outcome.blocked(
            'PROVIDER_UNLICENSED',
            f'{getattr(p, "name", "?")}: no licence_id. An unlicensed provider '
            f'is refused.', cause=Cause.GOVERNANCE)
    _PROVIDER = p
    return Outcome.ok('PROVIDER_REGISTERED', value=p.name)


def clear_provider() -> None:
    global _PROVIDER
    _PROVIDER = None


def routes_run(season: int, week: int) -> Outcome:
    """FAILS CLOSED. No provider, no data -- and no placeholder either."""
    if _PROVIDER is None:
        return Outcome.blocked(
            'NO_LICENSED_ROUTES_PROVIDER',
            f'routes run for {season} week {week}: no licensed provider is '
            f'registered. This adapter has no implementation, no sample rows '
            f'and no default that returns data. FTN acquisition is externally '
            f'pending and nothing here assumes it. Per the information-gap '
            f'study, true routes run remains unavailable from every source '
            f'this project can reach.',
            cause=Cause.DEPENDENCY, season=season, week=week)
    return _PROVIDER.routes_run(season, week)


def assert_not_a_forbidden_substitute(source_name: str) -> Outcome:
    """A near-miss field may never be adapted in as routes run."""
    why = FORBIDDEN_SOURCES.get(source_name)
    if why:
        return Outcome.fail(
            'FORBIDDEN_ROUTES_SUBSTITUTE',
            f'{source_name} may not be used as routes run: {why}. Substituting '
            f'it would make every downstream number mean something other than '
            f'what it is labelled.', source=source_name)
    return Outcome.ok('NOT_A_FORBIDDEN_SUBSTITUTE', value=source_name)
