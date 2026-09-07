"""Source registry. G0A items 1 and 4.

TWO JOBS

1. Make adding a verified official endpoint a REGISTRY EDIT, not a redesign.
   `official_injury_report`, `official_inactives` and `official_transactions` are
   already registered, already wired to the capture kinds they serve, and already
   carry their effective-scope semantics. What they lack is a verified URL. Until
   the networked researcher supplies one they resolve to a named BLOCKED state.
   **No endpoint is invented.** A guessed URL that 404s is indistinguishable from
   a real one that is down, and the difference matters.

2. Declare, per source, what its effective clock ACTUALLY pins -- and separately,
   what we may deterministically derive. Owner Directive 4 section 3: a
   season string alone may never certify game-level usability, and a derived
   value may never wear source authority.
"""
from __future__ import annotations

import dataclasses
import enum
import pathlib
import sys
from typing import Optional

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402
from nfl.identity.effective_scope import (  # noqa: E402
    Authority, EffectiveScope, EffectiveScopeError, ScopeKind, narrow)

NFLVERSE = "https://github.com/nflverse/nflverse-data/releases/download"


class Reachability(str, enum.Enum):
    """Whether THIS executor can fetch it. Retained as the operational axis."""
    REACHABLE = 'REACHABLE'
    BLOCKED_NO_EGRESS = 'BLOCKED_NO_EGRESS'
    PENDING_ENDPOINT_VERIFICATION = 'PENDING_ENDPOINT_VERIFICATION'


class SourceAuthority(str, enum.Enum):
    """WHOSE statement this is. Never inherited by being easier to consume.

    A structured mirror is often easier to parse than the official page. That is
    a convenience, not a promotion: if a mirror could silently acquire OFFICIAL
    authority, the cheapest source would always win and the authority hierarchy
    would exist only on paper.
    """
    OFFICIAL = 'OFFICIAL'                      # the league or the club itself
    INDEPENDENT_MIRROR = 'INDEPENDENT_MIRROR'  # validated restatement
    CANDIDATE_FALLBACK = 'CANDIDATE_FALLBACK'  # semantics not yet verified
    ARCHIVE = 'ARCHIVE'                        # terminal, post-hoc


class SourceStatus(str, enum.Enum):
    """Whether the SOURCE exists and answers, independent of who is asking.

    Kept apart from Reachability because conflating them produced a false
    statement in this repository: nfl.com was recorded as globally unreachable
    when it answers HTTP 200 externally and is refused by OUR proxy. A source
    being fine and an executor being unable to reach it are different facts with
    different owners.
    """
    VERIFIED_REACHABLE_EXTERNALLY = 'VERIFIED_REACHABLE_EXTERNALLY'
    UNVERIFIED = 'UNVERIFIED'
    KNOWN_DEAD = 'KNOWN_DEAD'


class ExecutorAccess(str, enum.Enum):
    """WHY this executor cannot reach it, measured rather than assumed."""
    REACHABLE = 'REACHABLE'
    LOCAL_PROXY_CONNECT_403 = 'LOCAL_PROXY_CONNECT_403'
    UNTESTED = 'UNTESTED'


@dataclasses.dataclass(frozen=True)
class SourceSpec:
    name: str
    url_template: Optional[str]
    required: bool
    durability: str
    reachability: Reachability
    # Which scheduler targets this source can discharge. A source that serves no
    # target is archival only, and saying so is what stops a routine poll from
    # appearing to satisfy an inactives deadline.
    serves_kinds: tuple = ()
    reduce_cols: tuple = ()
    # What the SOURCE itself pins, and what we may derive from it.
    source_scope_kind: ScopeKind = ScopeKind.SEASON
    content_kind: str = "csv"
    authority: SourceAuthority = SourceAuthority.ARCHIVE
    source_status: SourceStatus = SourceStatus.UNVERIFIED
    executor_access: ExecutorAccess = ExecutorAccess.UNTESTED
    # Lower number = preferred. A target is served by the best AVAILABLE source,
    # and preference is declared here rather than emerging from what happens to
    # work.
    authority_rank: int = 99
    narrow_method: Optional[str] = None
    narrow_evidence: Optional[str] = None
    narrow_to_kind: Optional[ScopeKind] = None
    note: str = ""

    def url(self, season: int) -> Optional[str]:
        return self.url_template.format(season=season) if self.url_template else None


REGISTRY: tuple = (
    SourceSpec(
        name="injuries",
        authority=SourceAuthority.ARCHIVE,
        source_status=SourceStatus.VERIFIED_REACHABLE_EXTERNALLY,
        executor_access=ExecutorAccess.REACHABLE,
        url_template=f"{NFLVERSE}/injuries/injuries_{{season}}.csv",
        required=True, durability="commit_raw",
        reachability=Reachability.REACHABLE,
        serves_kinds=(),   # a mirror, not the cascade; see note
        source_scope_kind=ScopeKind.SEASON,
        narrow_to_kind=ScopeKind.DATE_INTERVAL,
        narrow_method="valid_from := HTTP Last-Modified of the captured file",
        narrow_evidence=(
            "The file is season-scoped and carries per-row season/week, but the "
            "2025+ schema dropped date_modified so no row-level clock survives. "
            "The file's own Last-Modified is the only defensible effective "
            "boundary and is recorded as DERIVED, not as source-provided."),
        note=("Weekly archive mirror. It does NOT discharge a practice or "
              "final-status target: it is a terminal weekly snapshot, not the "
              "intraweek cascade."),
    ),
    SourceSpec(
        name="schedules",
        authority=SourceAuthority.ARCHIVE,
        source_status=SourceStatus.VERIFIED_REACHABLE_EXTERNALLY,
        executor_access=ExecutorAccess.REACHABLE,
        url_template=f"{NFLVERSE}/schedules/games.csv",
        required=True, durability="commit_raw",
        reachability=Reachability.REACHABLE,
        source_scope_kind=ScopeKind.SEASON,
        narrow_to_kind=ScopeKind.DATE_INTERVAL,
        narrow_method="valid_from := HTTP Last-Modified of the captured file",
        narrow_evidence="Reference data with no per-row effective clock.",
        note="Market and outcome columns quarantined at use, not at capture.",
    ),
    SourceSpec(
        name="depth_charts",
        authority=SourceAuthority.ARCHIVE,
        source_status=SourceStatus.VERIFIED_REACHABLE_EXTERNALLY,
        executor_access=ExecutorAccess.REACHABLE,
        url_template=f"{NFLVERSE}/depth_charts/depth_charts_{{season}}.csv",
        required=True, durability="reduce",
        reduce_cols=("dt", "team", "gsis_id", "pos_abb", "pos_rank"),
        reachability=Reachability.REACHABLE,
        # The one source that genuinely pins its own effective instant.
        source_scope_kind=ScopeKind.EXACT_TIMESTAMP,
        narrow_method=None, narrow_evidence=None, narrow_to_kind=None,
        note="Upstream cumulative dt series; source-provided effective instant.",
    ),
    SourceSpec(
        name="weekly_rosters",
        authority=SourceAuthority.ARCHIVE,
        source_status=SourceStatus.VERIFIED_REACHABLE_EXTERNALLY,
        executor_access=ExecutorAccess.REACHABLE,
        url_template=f"{NFLVERSE}/weekly_rosters/roster_weekly_{{season}}.csv",
        required=False, durability="reduce",
        reduce_cols=("season", "week", "team", "gsis_id", "position"),
        reachability=Reachability.REACHABLE,
        source_scope_kind=ScopeKind.SEASON,
        narrow_to_kind=ScopeKind.DATE_INTERVAL,
        narrow_method="valid_from := HTTP Last-Modified of the captured file",
        narrow_evidence=(
            "Rows carry season and week, but `status` is a post-hoc gameday "
            "outcome (INA -> 0 snaps of 3,438) and is quarantined."),
        note="Archival only; status quarantined from forecast use.",
    ),

    # --- Registered, wired, and deliberately without a URL -------------------
    SourceSpec(
        name="official_injury_report",
        url_template="https://www.nfl.com/injuries/",
        required=True, durability="commit_raw", content_kind="html",
        # REACHABLE means "attempt it", not "we can get it". Executor capability
        # is not a property of the source and is not knowable here: the same URL
        # returns 403 at a proxy from one executor and 200 with 328,961 bytes
        # from a GitHub runner. So the fetch resolves it at runtime and records
        # what actually happened.
        reachability=Reachability.REACHABLE,
        authority=SourceAuthority.OFFICIAL, authority_rank=1,
        source_status=SourceStatus.VERIFIED_REACHABLE_EXTERNALLY,
        executor_access=ExecutorAccess.UNTESTED,
        serves_kinds=("practice", "final_status"),
        # The CAPTURE is a whole-page snapshot, effective at the instant the
        # origin produced it. WEEK_TEAM is what a PARSED ROW would carry, and no
        # parser exists yet -- declaring it here made scope construction refuse
        # every capture, because the object had no week and no teams to put in
        # it. Capture scope and parsed-row scope are different things.
        source_scope_kind=ScopeKind.EXACT_TIMESTAMP,
        note=("THE intraweek cascade. Measured externally 2026-09-06: HTTP 200, "
              "server-rendered HTML, no CAPTCHA or robots exclusion. Measured "
              "HERE: DNS resolves to 151.101.65.55 and the LOCAL proxy answers "
              "403 to CONNECT www.nfl.com:443. The source is fine; this "
              "executor is denied. Those are different facts."),
    ),
    SourceSpec(
        name="official_inactives",
        url_template="https://www.nfl.com/inactives/",
        required=True, durability="commit_raw", content_kind="html",
        reachability=Reachability.REACHABLE,
        authority=SourceAuthority.OFFICIAL, authority_rank=1,
        source_status=SourceStatus.VERIFIED_REACHABLE_EXTERNALLY,
        executor_access=ExecutorAccess.UNTESTED,
        serves_kinds=("inactives",),
        source_scope_kind=ScopeKind.EXACT_TIMESTAMP,
        note=("Resolves Questionable to 0/1 at ~T-90. The only source that can "
              "discharge an inactives target."),
    ),
    SourceSpec(
        name="espn_injuries_json",
        url_template=("https://site.api.espn.com/apis/site/v2/sports/"
                      "football/nfl/injuries"),
        required=False, durability="commit_raw",
        reachability=Reachability.REACHABLE, content_kind="json",
        authority=SourceAuthority.CANDIDATE_FALLBACK, authority_rank=9,
        source_status=SourceStatus.VERIFIED_REACHABLE_EXTERNALLY,
        executor_access=ExecutorAccess.LOCAL_PROXY_CONNECT_403,
        # Deliberately EMPTY. It may not discharge any target until its contents
        # are audited: whether it carries practice participation, game status,
        # inactives, publication timestamps, and whether prior states are
        # overwritten. Registering a source is not the same as trusting it, and
        # being easier to parse than the official page is not an argument.
        serves_kinds=(),
        source_scope_kind=ScopeKind.UNVERIFIED_SEMANTICS
        if hasattr(ScopeKind, 'UNVERIFIED_SEMANTICS') else ScopeKind.SEASON,
        note=("CANDIDATE FALLBACK / RECONCILIATION ONLY. Measured externally "
              "2026-09-06: HTTP 200 structured JSON. Semantics NOT audited "
              "from this environment -- the same proxy denies it "
              "(CONNECT 403). It discharges NO target and does not inherit "
              "OFFICIAL authority by being easier to consume."),
    ),
    SourceSpec(
        name="official_transactions", url_template=None,
        required=False, durability="commit_raw",
        reachability=Reachability.PENDING_ENDPOINT_VERIFICATION,
        authority=SourceAuthority.OFFICIAL, authority_rank=1,
        source_status=SourceStatus.UNVERIFIED,
        executor_access=ExecutorAccess.UNTESTED,
        serves_kinds=(),
        source_scope_kind=ScopeKind.EXACT_TIMESTAMP,
        note="Elevations, signings, IR moves. Candidate for closing the "
             "prediction-time eligibility debt.",
    ),
)

BY_NAME = {s.name: s for s in REGISTRY}


def resolve(name: str, season: int) -> Outcome:
    """A usable URL, or a named refusal. Never a guessed endpoint."""
    spec = BY_NAME.get(name)
    if spec is None:
        return Outcome.blocked(
            'SOURCE_NOT_IN_REGISTRY',
            f'{name!r} is not registered. An unregistered source is undeclared, '
            f'not clean.', cause=Cause.GOVERNANCE, source=name)
    if spec.reachability is Reachability.BLOCKED_NO_EGRESS:
        return Outcome.blocked(
            'LOCAL_EXECUTOR_NO_EGRESS',
            f'{name}: the SOURCE is {spec.source_status.value} and the endpoint '
            f'is known ({spec.url(season)}), but THIS executor is denied: '
            f'{spec.executor_access.value}. DNS resolves; the local proxy '
            f'answers 403 to CONNECT. This says nothing about the source and '
            f'everything about where the capture must run.',
            cause=Cause.NETWORK, source=name,
            serves_kinds=list(spec.serves_kinds),
            source_status=spec.source_status.value,
            executor_access=spec.executor_access.value,
            authority=spec.authority.value)
    if spec.reachability is Reachability.PENDING_ENDPOINT_VERIFICATION:
        return Outcome.blocked(
            'ENDPOINT_NOT_YET_VERIFIED',
            f'{name}: registered and wired to {list(spec.serves_kinds) or "no"} '
            f'capture target(s), but no verified endpoint exists. Assigned to '
            f'the networked researcher. A guessed URL is refused here because a '
            f'guess that 404s is indistinguishable from a real endpoint that is '
            f'down.', cause=Cause.DEPENDENCY, source=name,
            serves_kinds=list(spec.serves_kinds))
    url = spec.url(season)
    if not url:
        return Outcome.fail(
            'SOURCE_URL_MISSING',
            f'{name}: reachable but no url_template. Inconsistent registration.',
            source=name)
    return Outcome.ok('SOURCE_RESOLVED', value=url, detail=f'{name} -> {url}',
                      source=name)


def can_discharge(name: str, kind: str) -> bool:
    """May this source discharge a scheduler target of this kind?

    The guard against a routine mirror poll appearing to satisfy an inactives
    deadline. `injuries` serves no target on purpose: it is a terminal weekly
    snapshot, not the intraweek cascade.
    """
    spec = BY_NAME.get(name)
    return bool(spec and kind in spec.serves_kinds)


def unmet_targets(manifest_path=None) -> dict:
    """Capture kinds no source has ACTUALLY been captured for.

    Evidence-based, and it has to be. An earlier version computed `met` from the
    `REACHABLE` flag -- but REACHABLE means "attempt this source", not "this
    executor can retrieve it". The same URL returns 403 at a proxy from one
    executor and 200 with 328,961 bytes from a GitHub runner, so a declaration
    cannot answer the question.

    Computing `met` from the declaration produced a false green immediately:
    marking the official sources REACHABLE made all three perishable targets
    report as met while nothing had ever been captured. A target is met when a
    source authorised to serve it has a recorded successful capture, and not
    before.
    """
    import json as _json
    import pathlib as _pathlib
    needed = {'practice', 'final_status', 'inactives'}

    captured: set = set()
    if manifest_path is not None:
        mp = _pathlib.Path(manifest_path)
        if mp.exists():
            for line in mp.read_text().splitlines():
                if not line.strip():
                    continue
                try:
                    row = _json.loads(line)
                except ValueError:
                    continue
                if row.get('state') == 'PASS' and row.get('source'):
                    captured.add(row['source'])

    met = {k for spec in REGISTRY if spec.name in captured
           for k in spec.serves_kinds}
    return {'unmet': sorted(needed - met), 'met': sorted(needed & met),
            'captured_sources': sorted(captured),
            'evidence': ('manifest' if manifest_path is not None
                         else 'none supplied -- nothing can be claimed met'),
            'pending_sources': sorted(
                s.name for s in REGISTRY
                if s.reachability is Reachability.PENDING_ENDPOINT_VERIFICATION)}


def build_scope(name: str, *, season: int, source_timestamp: str) -> Outcome:
    """The effective scope of one capture, honestly attributed.

    Two refusals here that an earlier version did not make.

    First, an unverified source gets NO scope. `resolve()` already refuses to
    invent an endpoint for it; building a `SOURCE_PROVIDED` scope for the same
    source invents the *semantics* instead -- a claim that an upstream we have
    never successfully contacted told us its data is pinned to a team-game. That
    object then certified use for a real game. Refusing the URL while fabricating
    the meaning is the same defect wearing different clothes.

    Second, this is an Outcome-returning stage boundary, so a malformed scope
    comes back as a named FAIL rather than raising past the caller's contract.
    """
    spec = BY_NAME.get(name)
    if spec is None:
        return Outcome.blocked('SOURCE_NOT_IN_REGISTRY', f'{name!r}',
                               cause=Cause.GOVERNANCE)
    if spec.url_template is None:
        # The real unverified case: no endpoint exists, so its declared
        # source_scope_kind is an expectation about bytes nobody has, not a fact
        # about bytes we hold. Refusing the URL while inventing the semantics
        # would be the same defect in different clothes.
        return Outcome.blocked(
            'SCOPE_UNAVAILABLE_UNVERIFIED_SOURCE',
            f'{name}: no effective scope can be built for a source with no '
            f'verified endpoint ({spec.reachability.value}).',
            cause=Cause.DEPENDENCY, source=name,
            reachability=spec.reachability.value)
    try:
        return _build_scope_unchecked(spec, season, source_timestamp)
    except EffectiveScopeError as exc:
        return Outcome.fail(
            'SCOPE_CONSTRUCTION_REFUSED',
            f'{name}: {exc}', source=name)


def _build_scope_unchecked(spec: SourceSpec, season: int,
                           source_timestamp: str) -> Outcome:
    name = spec.name
    base = EffectiveScope(
        kind=spec.source_scope_kind,
        authority=Authority.SOURCE_PROVIDED,
        source_value=(source_timestamp if spec.source_scope_kind
                      is ScopeKind.EXACT_TIMESTAMP else str(season)),
        season=season,
        valid_from=(source_timestamp if spec.source_scope_kind
                    is ScopeKind.EXACT_TIMESTAMP else None),
    )
    if spec.narrow_to_kind is None:
        return Outcome.ok('EFFECTIVE_SCOPE_BUILT', value=base,
                          detail=f'{name}: source-provided '
                                 f'{base.kind.value}', source=name,
                          scope_level='FILE')
    narrowed = narrow(base, kind=spec.narrow_to_kind,
                      method=spec.narrow_method, evidence=spec.narrow_evidence,
                      deterministic=True, valid_from=source_timestamp)
    # NOTE, and it is deliberate: this is a FILE-level scope. Its interval is
    # open at the top, so `assert_usable_for` will correctly return
    # EFFECTIVE_SCOPE_TOO_COARSE if a caller tries to certify a specific game
    # with it. A season file narrowed only by its own Last-Modified cannot
    # distinguish two games in that season, and pretending otherwise is exactly
    # what item 4 failed for. Row-level narrowing (per-row week and team) is a
    # separate step and is not built; it must not be faked here.
    return Outcome.ok('EFFECTIVE_SCOPE_BUILT', value=narrowed,
                      detail=f'{name}: source {base.kind.value} narrowed to '
                             f'{narrowed.kind.value} ({narrowed.authority.value})'
                             f' -- FILE level, not game-level certifiable',
                      source=name, scope_level='FILE')


def bound_from_series(name: str, captures: list, index: int) -> Outcome:
    """Close a file-level scope's interval using the NEXT capture of the source.

    Why this is a separate function and not part of `build_scope`: at capture
    time the interval genuinely is open at the top -- we do not yet know when
    this vintage stopped being current. Writing a `valid_to` then would be
    fabricated precision, which Directive 4 forbids.

    Once a vintage SERIES exists, the bound is a fact rather than a guess: this
    vintage was current until the next capture of the same source observed
    different content. That makes the derivation deterministic and evidenced, and
    it is what turns a FILE-level scope into one that can certify a specific
    game -- because a bounded interval discriminates between games in a season
    and an open one does not.

    `captures` is a list of (source_timestamp, sha256) for one source in
    ascending time order. `index` selects which vintage to bound.
    """
    spec = BY_NAME.get(name)
    if spec is None:
        return Outcome.blocked('SOURCE_NOT_IN_REGISTRY', f'{name!r}',
                               cause=Cause.GOVERNANCE)
    if not captures:
        return Outcome.fail(
            'VINTAGE_SERIES_EMPTY',
            f'{name}: cannot bound a vintage from an empty series. An empty '
            f'series is not a one-element one.', source=name)
    if not 0 <= index < len(captures):
        return Outcome.fail(
            'VINTAGE_INDEX_OUT_OF_RANGE',
            f'{name}: index {index} against {len(captures)} captures.',
            source=name)

    ts, digest = captures[index][0], captures[index][1]
    successor = None
    for later_ts, later_digest in captures[index + 1:]:
        if later_digest != digest:
            successor = later_ts
            break

    if successor is None:
        # Still the current vintage. Honest answer: it has no upper bound yet, so
        # it stays FILE-level. Inventing "until now" would make the scope look
        # game-certifiable on the strength of when somebody happened to ask.
        return Outcome.deferred(
            'VINTAGE_NOT_YET_SUPERSEDED',
            f'{name}: the vintage captured at {ts} has not been superseded, so '
            f'its interval is still open and it remains FILE-level. Closes when '
            f'a later capture observes different content.',
            owed=f'{name}@{ts}', source=name, valid_from=ts)

    base = EffectiveScope(
        kind=ScopeKind.DATE_INTERVAL, authority=Authority.SOURCE_PROVIDED,
        source_value=ts, season=None, valid_from=ts)
    bounded = narrow(
        base, kind=ScopeKind.DATE_INTERVAL,
        method='valid_to := source_timestamp of the next capture of this '
               'source whose content hash differs',
        evidence=f'vintage {digest[:12]} was current from {ts} until '
                 f'{successor}, when the content changed',
        deterministic=True, valid_to=successor)
    return Outcome.ok('VINTAGE_BOUNDED', value=bounded,
                      detail=f'{name}: [{ts}, {successor}] -- bounded, so '
                             f'game-level certification is now possible',
                      source=name)
