"""Current-season input freshness, SCOPED and FAIL-CLOSED.

WHAT WENT WRONG WITHOUT THIS. `qb_allocation.panel_freshness` correctly BLOCKS a
week-2 forecast whose incumbency panel stops at 202518, and `allocate()` records
that verdict in the artifact -- and nothing refuses on it. A stale panel was
named on the board and still produced a board.

WHY SCOPE IS THE WHOLE DESIGN. "Is the panel fresh?" has two right answers at
once. A DET-BUF board reads current-season state for DET and BUF, both present
and lawful, and blocking it because DEN and KC are absent would refuse a board
on clubs it never reads. A league-wide RATE fitted on 30 clubs while reporting
as though on 32 must refuse. One threshold either blocks the first or admits the
second, so the scope is declared per REQUIREMENT.

`expected_clubs` IS SUPPLIED AND NEVER INFERRED. Deriving the expected set from
what the data happens to contain makes the check tautological, and that is
exactly what let a 30-club panel look complete.

ORDINALS, NOT WALL-CLOCK. A file cannot be made fresh by touching it.

TWO FAILURES, TWO CODES. `..._STALE` means the newest ordinal is too old;
`..._INCOMPLETE` means the ordinal is fine and clubs are missing. Collapsing
them would repeat the `is_season_opener` mistake of one flag for two conditions,
which is the defect this module exists downstream of.
"""
from __future__ import annotations

import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402

SPEC_VERSION = 'current-season-input-freshness-1'

#: Bumped whenever an input is added, removed, or changes scope. A registry
#: that can change silently is not a registry.
FRESHNESS_REGISTRY_VERSION = 1

FIXTURE_LOCAL = 'FIXTURE_LOCAL'
LEAGUE_WIDE = 'LEAGUE_WIDE'
SCOPES = (FIXTURE_LOCAL, LEAGUE_WIDE)

#: A week-W forecast must be able to see week W-1. Not a tuning knob: it is the
#: definition of "the previous game is the previous game".
MAX_TRAIL_WEEKS = 1

CODE_FRESH = 'CURRENT_SEASON_INPUT_FRESH'
CODE_STALE = 'CURRENT_SEASON_INPUT_STALE'
CODE_INCOMPLETE = 'CURRENT_SEASON_INPUT_INCOMPLETE'
CODE_OPENER = 'NOT_APPLICABLE_AT_A_SEASON_OPENER'
CODE_UNDECLARED = 'CURRENT_SEASON_INPUT_UNDECLARED'
#: DISTINCT FROM STALE ON PURPOSE. Stale means the data exists and
#: stops too early. UNVERIFIED means nobody has established where the
#: current-season version of this input comes from at all. Both refuse
#: and neither is weaker, but a reader of the refusal has to be able to
#: tell which one they are looking at: one is fixed by a fresher pull
#: and the other by finding a source. They shared CODE_STALE until a
#: live run refused with `CURRENT_SEASON_INPUT_STALE` for an input that
#: was never stale.
CODE_UNVERIFIED = 'CURRENT_SEASON_SOURCE_UNVERIFIED'

#: The registry. `default_scope` is what a single-fixture board gets; a
#: league-wide fit must pass LEAGUE_WIDE explicitly and is refused on 30 of 32.
REGISTRY = {
    'panel_p3': {
        'what': 'QB incumbency: the previous primary passer per club',
        'default_scope': FIXTURE_LOCAL,
        'consumers': ('qb_allocation.previous_primary_detail',)},
    'denom_panel': {
        'what': 'carry / target / dropback denominators',
        'default_scope': LEAGUE_WIDE,
        # STALE BY DECLARATION, and the block is NOT blunt. Measured which
        # team-volume estimators actually consume recency, because
        # `eligibility.REQUIRED_INPUTS` labels this input "(history)" and a
        # training corpus being historical is not a defect:
        #
        #   team_off_snaps       league_mean   history only   unaffected
        #   team_dropbacks_part  coach_prior   history only   unaffected
        #   team_carries         coach_prior   history only   unaffected
        #   team_rz_carries      coach_prior   history only   unaffected
        #   team_targets         EWMA          RECENCY        STALE
        #
        # So ONE of five metrics is genuinely degraded: `team_targets` is an
        # EWMA whose most recent observation is 2025 week 18 for every club.
        # That is a real staleness and it blocks.
        #
        # It is NOT repaired by refreshing the panel, because the 2026 source's
        # vintage, completeness, coverage, field definitions and identity
        # behaviour are not established. A partially complete denominator
        # produces confidently wrong SHARES rather than a nameable refusal, so
        # the honest state is BLOCKED rather than refreshed-and-hoped.
        'declared_blocked': 'CURRENT_SEASON_SOURCE_UNVERIFIED',
        'recency_sensitive': ('team_targets (ewma)',),
        'history_only': ('team_off_snaps (league_mean)',
                         'team_dropbacks_part (coach_prior)',
                         'team_carries (coach_prior)',
                         'team_rz_carries (coach_prior)'),
        'consumers': ('team_volume_v1', 'nonqb.accounting', 'nonqb.eligibility')},
    'team_volume_history': {
        'what': 'team-level volume history',
        'default_scope': FIXTURE_LOCAL,
        'consumers': ('team_volume_v1',)},
}


class FreshnessError(ValueError):
    """Named so a caller can tell a refusal from an arithmetic failure."""


def required_ordinal(season: int, week: int) -> int:
    return int(season) * 100 + (int(week) - MAX_TRAIL_WEEKS)


def check_input(input_id: str, season: int, week: int, *, scope=None,
                newest_ordinal=None, expected_clubs=None, present_clubs=None,
                provenance=None) -> Outcome:
    """One registered input, at a declared scope.

    `expected_clubs` is REQUIRED at LEAGUE_WIDE and at FIXTURE_LOCAL alike. The
    caller states what it needs; this function states whether it has it. It
    never decides for the caller what "everything" means.
    """
    if input_id not in REGISTRY:
        return Outcome.fail(
            CODE_UNDECLARED,
            f'{input_id!r} is not in the freshness registry. An input nobody '
            f'declared cannot be certified fresh, and guessing its scope is '
            f'how the registry stops meaning anything.',
            registry_version=FRESHNESS_REGISTRY_VERSION,
            registered=sorted(REGISTRY))
    spec = REGISTRY[input_id]
    scope = scope or spec['default_scope']
    if scope not in SCOPES:
        return Outcome.fail(
            'FRESHNESS_SCOPE_UNKNOWN',
            f'{scope!r} is not one of {SCOPES}.', input_id=input_id)
    exp = sorted(set(expected_clubs or ()))
    got = sorted(set(present_clubs or ()))
    missing = sorted(set(exp) - set(got))
    need = required_ordinal(season, week)
    ev = {'spec_version': SPEC_VERSION,
          'registry_version': FRESHNESS_REGISTRY_VERSION,
          'input_id': input_id, 'scope': scope,
          'season': int(season), 'week': int(week),
          'expected_clubs': exp, 'n_expected': len(exp),
          'present_clubs': got, 'n_present': len(got),
          'missing_clubs': missing, 'n_missing': len(missing),
          'newest_ordinal': newest_ordinal, 'required_ordinal': need,
          'max_trail_weeks': MAX_TRAIL_WEEKS,
          'provenance': list(provenance or ()),
          'consumers': list(spec.get('consumers') or ())}

    # A season opener has no current-season prior week. NOT_APPLICABLE, never
    # FRESH -- conflating the two is what hid the defect for a week.
    if int(week) <= MAX_TRAIL_WEEKS:
        return Outcome.not_applicable(
            CODE_OPENER,
            f'{input_id}: week {week} crosses a season boundary by definition, '
            f'so there is no current-season prior week to require. This is an '
            f'EXEMPTION and is not a passing freshness check.', **ev)

    if spec.get('declared_blocked'):
        return Outcome.blocked(
            CODE_UNVERIFIED,
            f'{input_id} is BLOCKED BY DECLARATION '
            f'({spec["declared_blocked"]}): its current-season source has not '
            f'been established, and a partially complete input produces '
            f'confidently wrong numbers rather than a nameable refusal.',
            cause=Cause.DATA, declared_blocked=spec['declared_blocked'],
            recency_sensitive=list(spec.get('recency_sensitive') or ()),
            history_only=list(spec.get('history_only') or ()), **ev)

    if not exp:
        return Outcome.fail(
            'FRESHNESS_EXPECTED_CLUBS_NOT_SUPPLIED',
            f'{input_id}: no expected club set was supplied at scope {scope}. '
            f'Inferring it from the clubs present makes the check '
            f'tautological, which is the defect this module exists to stop.',
            **ev)

    if newest_ordinal is None or int(newest_ordinal) < need:
        return Outcome.blocked(
            CODE_STALE,
            f'{input_id}: newest ordinal {newest_ordinal} does not reach the '
            f'required {need} for {season} week {week}.',
            cause=Cause.DATA, **ev)

    if missing:
        return Outcome.blocked(
            CODE_INCOMPLETE,
            f'{input_id} at scope {scope}: {len(missing)} of {len(exp)} '
            f'expected club(s) carry no current-season row -- {missing}. The '
            f'ordinal is current; the coverage is not. Missing clubs are NAMED '
            f'and never inferred.',
            cause=Cause.DATA, **ev)

    return Outcome.ok(
        CODE_FRESH, value=dict(ev),
        detail=f'{input_id} at scope {scope}: {len(got)} of {len(exp)} club(s) '
               f'current to ordinal {newest_ordinal} (required {need})', **ev)


def check_all(season: int, week: int, inputs) -> Outcome:
    """Every registered input for one forecast. FAIL-CLOSED on any refusal.

    `inputs` is {input_id: kwargs for check_input}. An input in the REGISTRY and
    absent from `inputs` is a refusal, not a pass: a gate that can be satisfied
    by not mentioning an input is not a gate.
    """
    results, blocking = {}, []
    for input_id in sorted(REGISTRY):
        if input_id not in inputs:
            o = Outcome.blocked(
                CODE_STALE,
                f'{input_id} is registered and was not supplied to the '
                f'freshness check. An unmentioned input is not an absent '
                f'requirement.', cause=Cause.DATA, input_id=input_id,
                scope=REGISTRY[input_id]['default_scope'])
        else:
            o = check_input(input_id, season, week, **inputs[input_id])
        results[input_id] = {'state': o.state.value, 'code': o.code,
                             'detail': o.detail,
                             **{k: v for k, v in o.evidence.items()
                                if k != 'value'}}
        if o.state not in (State.PASS, State.NOT_APPLICABLE):
            blocking.append(input_id)
    ev = {'spec_version': SPEC_VERSION,
          'registry_version': FRESHNESS_REGISTRY_VERSION,
          'season': int(season), 'week': int(week),
          'inputs': results, 'blocking_inputs': blocking,
          'n_blocking': len(blocking)}
    if blocking:
        return Outcome.blocked(
            CODE_STALE,
            f'{len(blocking)} registered current-season input(s) refuse: '
            f'{blocking}. The board may not publish.',
            cause=Cause.DATA, **ev)
    return Outcome.ok(
        CODE_FRESH, value=dict(ev),
        detail=f'all {len(results)} registered input(s) satisfied for '
               f'{season} week {week}', **ev)
