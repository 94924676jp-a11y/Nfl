"""What a captured artifact is effective FOR. G0A item 4, owner-failed and reopened.

WHY THIS EXISTS

`sportsplatform/governance/provenance.py` already keeps five clocks apart and already offers
`assert_usable_for(p, game_date)`. The NFL capture satisfied the *structure* --
all five fields present, validated, no backfilling -- while setting
`effective_for_date = "2026"`.

A season string cannot answer the question the control exists to ask:

    "Was this information effective for THIS game, at THIS forecast timestamp?"

Owner verdict, and it is right: a five-field object whose effective clock cannot
answer that is structurally complete and semantically insufficient. Calling it
PASS because the fields exist turns semantic correctness back into schema
correctness -- the exact substitution this project keeps paying for. Item 4 was
overridden to FAIL and this module is the fix.

THE RULE THAT SHAPES THE DESIGN

Upstream sources supply coarse semantics. `depth_charts` gives a `dt`;
`weekly_rosters` gives a season and week; `schedules` gives no effective clock at
all. The temptation is to write a precise-looking value and move on. That would
fabricate precision.

So a scope carries BOTH:
  * the raw source value, never overwritten; and
  * an explicitly derived applicability interval, when one is derived, carrying
    its method, its evidence and its authority class.

A derived value may never be presented as source-provided. That is a named
failure at construction, not a convention.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import enum
import pathlib
import sys
from typing import Optional, Sequence

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402


class ScopeKind(str, enum.Enum):
    """How precisely applicability is pinned. Ordered coarse -> fine."""
    SEASON = 'SEASON'                    # never sufficient on its own
    DATE_INTERVAL = 'DATE_INTERVAL'
    WEEK_TEAM = 'WEEK_TEAM'
    TEAM_GAME = 'TEAM_GAME'
    GAME = 'GAME'
    EXACT_TIMESTAMP = 'EXACT_TIMESTAMP'


# WHAT ACTUALLY MAKES A SCOPE GAME-LEVEL.
#
# An earlier version gated on the declared `kind` -- `INSUFFICIENT_ALONE =
# (ScopeKind.SEASON,)`. That was defeated by one enum value: the item-4 artifact
# itself, a bare season string, relabelled `DATE_INTERVAL` and carrying no
# interval, certified use for any game in the season. **Relabelling is not
# narrowing**, and a gate that reads a label is a gate on the caller's honesty.
#
# The question is therefore asked of the CONTENT: does this scope carry anything
# that could distinguish one game in the season from another?
GAME_LEVEL_DISCRIMINATORS = ('game_id', 'week_and_teams', 'bounded_interval')


def game_level_discriminators(scope: 'EffectiveScope') -> list:
    """Which discriminators this scope actually carries. Content, not label."""
    found = []
    if scope.game_id:
        found.append('game_id')
    if scope.week is not None and scope.teams:
        found.append('week_and_teams')
    # An interval open at the top ([t, infinity)) discriminates on the forecast
    # timestamp but NOT between two games later in the same season, so it does
    # not qualify. Both bounds are required.
    if scope.valid_from and scope.valid_to:
        found.append('bounded_interval')
    return found


class Authority(str, enum.Enum):
    SOURCE_PROVIDED = 'SOURCE_PROVIDED'
    DERIVED_DETERMINISTIC = 'DERIVED_DETERMINISTIC'
    DERIVED_HEURISTIC = 'DERIVED_HEURISTIC'

    @property
    def is_derived(self) -> bool:
        return self is not Authority.SOURCE_PROVIDED


class EffectiveScopeError(ValueError):
    pass


@dataclasses.dataclass(frozen=True)
class Derivation:
    """How a narrowed scope was obtained, when it was not given."""
    method: str
    evidence: str
    status: str = 'DERIVED'

    def __post_init__(self):
        # An empty method with a dataclass round it is "we narrowed it somehow"
        # wearing a provenance. The object existing was never the requirement.
        if not (self.method or '').strip():
            raise EffectiveScopeError(
                'DERIVATION_METHOD_EMPTY: a derivation must name its method.')
        if not (self.evidence or '').strip():
            raise EffectiveScopeError(
                'DERIVATION_EVIDENCE_EMPTY: a derivation must cite what '
                'justifies it.')

    def as_dict(self) -> dict:
        return dataclasses.asdict(self)


def _parse(ts, field: str) -> dt.datetime:
    if isinstance(ts, dt.datetime):
        return ts if ts.tzinfo else ts.replace(tzinfo=dt.timezone.utc)
    d = dt.datetime.fromisoformat(str(ts).replace('Z', '+00:00'))
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)


@dataclasses.dataclass(frozen=True)
class EffectiveScope:
    """The applicability of one captured artifact.

    `source_value` is what the upstream actually said, verbatim. It is never
    replaced by a narrowed value -- narrowing is additive.
    """
    kind: ScopeKind
    authority: Authority
    source_value: str
    season: Optional[int] = None
    week: Optional[int] = None
    teams: tuple = ()
    game_id: Optional[str] = None
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None
    derivation: Optional[Derivation] = None

    def __post_init__(self):
        if not self.source_value:
            raise EffectiveScopeError(
                'EFFECTIVE_SCOPE_NO_SOURCE_VALUE: a scope must record what the '
                'source actually said, even when that is coarse. Dropping it '
                'makes a derived value indistinguishable from a given one.')
        # The rule the owner named explicitly: never present derived as source.
        if self.authority is Authority.SOURCE_PROVIDED and self.derivation:
            raise EffectiveScopeError(
                'DERIVED_PRESENTED_AS_SOURCE: this scope claims the source '
                'supplied it while carrying a derivation. A narrowed value '
                'wearing source authority is unfalsifiable downstream -- a '
                'reader cannot tell what the upstream guaranteed from what we '
                'inferred.')
        if self.authority.is_derived and not self.derivation:
            raise EffectiveScopeError(
                'DERIVATION_UNDECLARED: a derived scope must carry its method '
                'and evidence. "We narrowed it somehow" is not a provenance.')
        # Every kind states what it must carry. Previously only GAME and
        # WEEK_TEAM did, so DATE_INTERVAL, TEAM_GAME and EXACT_TIMESTAMP could be
        # declared over empty content -- which is how a season string wore a
        # finer label.
        required = {
            ScopeKind.GAME: ('game_id',),
            ScopeKind.TEAM_GAME: ('game_id', 'teams'),
            ScopeKind.WEEK_TEAM: ('week', 'teams'),
            ScopeKind.DATE_INTERVAL: ('valid_from',),
            ScopeKind.EXACT_TIMESTAMP: ('valid_from',),
            ScopeKind.SEASON: (),
        }[self.kind]
        missing = [f for f in required
                   if getattr(self, f) in (None, '', (), [])]
        if missing:
            # One code per kind, not a shared CONTENT_MISSING. V7 proved the
            # difference: a refusal whose code was reused for two causes sent an
            # operator to the wrong place.
            code = {
                ScopeKind.GAME: 'EFFECTIVE_SCOPE_GAME_WITHOUT_ID',
                ScopeKind.TEAM_GAME: 'EFFECTIVE_SCOPE_TEAM_GAME_INCOMPLETE',
                ScopeKind.WEEK_TEAM: 'EFFECTIVE_SCOPE_WEEK_TEAM_INCOMPLETE',
                ScopeKind.DATE_INTERVAL: 'EFFECTIVE_SCOPE_INTERVAL_UNBOUNDED',
                ScopeKind.EXACT_TIMESTAMP: 'EFFECTIVE_SCOPE_TIMESTAMP_MISSING',
            }[self.kind]
            raise EffectiveScopeError(
                f'{code}: kind={self.kind.value} declares precision it does not '
                f'carry -- missing {missing}. Relabelling a coarse value with a '
                f'finer kind is not narrowing.')

    def as_dict(self) -> dict:
        d = dataclasses.asdict(self)
        d['kind'] = self.kind.value
        d['authority'] = self.authority.value
        return d


def narrow(scope: EffectiveScope, *, kind: ScopeKind, method: str,
           evidence: str, deterministic: bool = True,
           **fields) -> EffectiveScope:
    """Add applicability without overwriting what the source said.

    The source value rides through untouched; only the derived fields are added,
    and the authority is downgraded to a derived class so the narrowing is
    visible forever.
    """
    merged = dict(season=scope.season, week=scope.week, teams=scope.teams,
                  game_id=scope.game_id, valid_from=scope.valid_from,
                  valid_to=scope.valid_to)
    unknown = set(fields) - set(merged)
    if unknown:
        raise EffectiveScopeError(
            f'EFFECTIVE_SCOPE_UNKNOWN_FIELD: {sorted(unknown)} is not a scope '
            f'field. Narrowing may only fill declared fields.')
    merged.update(fields)
    return EffectiveScope(
        kind=kind,
        authority=(Authority.DERIVED_DETERMINISTIC if deterministic
                   else Authority.DERIVED_HEURISTIC),
        source_value=scope.source_value,          # never replaced
        derivation=Derivation(method=method, evidence=evidence),
        **merged)


def assert_usable_for(scope: EffectiveScope, *, game_id: str,
                      season: int, week: int, teams: Sequence[str],
                      forecast_timestamp) -> Outcome:
    """May this artifact inform a forecast of THIS game, written THEN?

    Every refusal is named. There is no boolean and no default-allow.
    """
    ev = {'scope': scope.as_dict(), 'game_id': game_id,
          'season': season, 'week': week}

    # 1. Too coarse to certify anything at game level -- asked of the CONTENT.
    discriminators = game_level_discriminators(scope)
    if not discriminators:
        return Outcome.blocked(
            'EFFECTIVE_SCOPE_TOO_COARSE',
            f'scope is labelled {scope.kind.value} ({scope.source_value!r}) but '
            f'carries none of {list(GAME_LEVEL_DISCRIMINATORS)}, so nothing in '
            f'it could distinguish {game_id} from any other game in the season. '
            f'A season answers "which year", never "which game", and a finer '
            f'label is not a finer fact. Narrow it with a declared method, or '
            f'refuse the artifact.',
            cause=Cause.DATA, **ev)
    ev = {**ev, 'discriminators': discriminators}

    # 2. Wrong season is a hard mismatch before anything finer is considered.
    if scope.season is not None and scope.season != season:
        return Outcome.fail(
            'EFFECTIVE_SCOPE_WRONG_SEASON',
            f'scope is effective for season {scope.season}, asked for {season}.',
            **ev)

    # 3. A record pinned to another game.
    if scope.game_id and scope.game_id != game_id:
        return Outcome.fail(
            'EFFECTIVE_SCOPE_WRONG_GAME',
            f'scope is effective for {scope.game_id!r}, asked for {game_id!r}.',
            **ev)

    # 4. Prior-week reuse. The common, quiet one: a week-3 report silently
    #    informing a week-5 forecast because both are "2026".
    if scope.week is not None and scope.week != week:
        return Outcome.fail(
            'EFFECTIVE_SCOPE_WRONG_WEEK',
            f'scope is effective for week {scope.week}, asked for week {week}. '
            f'Reusing an earlier week\'s record for a later game needs an '
            f'explicit declared validity interval, not silence.',
            **ev)

    # 5. Cross-team application.
    if scope.teams:
        asked = {t.upper() for t in teams}
        held = {t.upper() for t in scope.teams}
        if not (held & asked):
            return Outcome.fail(
                'EFFECTIVE_SCOPE_WRONG_TEAM',
                f'scope is effective for {sorted(held)}, asked about '
                f'{sorted(asked)}. No overlap.', **ev)

    # 6. Interval bounds against the forecast timestamp.
    try:
        fts = _parse(forecast_timestamp, 'forecast_timestamp')
    except (ValueError, TypeError) as exc:
        return Outcome.blocked('EFFECTIVE_TIMESTAMP_UNPARSEABLE', str(exc),
                               cause=Cause.DATA, **ev)

    if scope.valid_from is not None:
        try:
            vf = _parse(scope.valid_from, 'valid_from')
        except (ValueError, TypeError) as exc:
            return Outcome.blocked('EFFECTIVE_TIMESTAMP_UNPARSEABLE', str(exc),
                                   cause=Cause.DATA, **ev)
        if vf > fts:
            return Outcome.fail(
                'EFFECTIVE_AFTER_FORECAST',
                f'this information becomes effective at {scope.valid_from}, '
                f'after the forecast was written at {fts.isoformat()}. It was '
                f'not knowable yet.', **ev)

    if scope.valid_to is not None:
        try:
            vt = _parse(scope.valid_to, 'valid_to')
        except (ValueError, TypeError) as exc:
            return Outcome.blocked('EFFECTIVE_TIMESTAMP_UNPARSEABLE', str(exc),
                                   cause=Cause.DATA, **ev)
        if vt < fts:
            return Outcome.fail(
                'EFFECTIVE_SCOPE_EXPIRED',
                f'scope stops being effective at {scope.valid_to}, before the '
                f'forecast at {fts.isoformat()}. A superseded record is not a '
                f'usable one.', **ev)

    return Outcome.ok(
        'EFFECTIVE_SCOPE_USABLE', value=scope.as_dict(),
        detail=f'{scope.kind.value}/{scope.authority.value} certifies use for '
               f'{game_id} at {fts.isoformat()} via {discriminators}',
        **ev)
