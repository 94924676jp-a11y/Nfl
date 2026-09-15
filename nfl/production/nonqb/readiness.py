"""nonqb_readiness.report(): exactly which condition blocks execution.

DESIGNED SO A GENERIC FAILURE IS IMPOSSIBLE. Every blocking condition is
computed from the captured data and named. "It didn't work" is not an output
this module can produce.

The state it reports is deliberately finer than R2's. R2 said
WAITING_FOR_INJURIES_2026 because the feed was 404. The feed has since been
published -- and it is nearly empty. Those are different conditions and they
need different names, because the first clears itself and the second may not.
"""
from __future__ import annotations

import collections
import contextvars
import csv
import datetime as _dt
import gzip
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import (Cause, Outcome,    # noqa: E402
                                               State)
from nfl.production.nonqb import eligibility as EL                # noqa: E402
from nfl.production.nonqb import vintage_selector as VS           # noqa: E402

# What the frozen appearance mechanism needs, and the minimum that makes it
# runnable at all. These are structural requirements of the mechanism, not
# quality thresholds chosen to get a pass.
MIN_TEAMS_COVERED = 32          # every team on the slate must appear
NEEDS_REPORT_STATUS = True      # teammate_availability reads it


# A cut that admits everything, used ONLY where "no bound" is the declared
# answer. Named so that a reader can grep for every place the bound is off.
_UNBOUNDED = _dt.datetime.max.replace(tzinfo=_dt.timezone.utc)


# =====================================================================
# THE GATE HANDS ITS CUT TO THE FEED. TRANSITIONAL, AND MARKED AS SUCH.
#
# WS12's finding is that the gate and the feed are two selectors and only one
# has a clock. The permanent repair is for the caller to declare the cut once
# with `vintage_selector.clock(...)`, which `football_engine.run_game` should
# do -- that patch is written and handed to the owning workstream, and it is
# the C1 pattern.
#
# It cannot be applied from here, and until it lands the production path has no
# declared clock at all, so the feed would refuse every game. Refusing is the
# right direction and the wrong outcome: the information needed is already in
# the process. `layers.py:117` evaluates the GATE two lines before it reads the
# feed, on the same season, week and kickoff. So the gate publishes the cut it
# used and the feed consumes it.
#
# THE DISCIPLINE THAT MAKES THIS SAFE, AND IT IS THE WHOLE DESIGN:
#   * the feed CONSUMES the handoff -- a second read without a fresh gate
#     evaluation refuses, so a cut cannot be reused across games;
#   * where several gate evaluations are outstanding (the slate-wide branch),
#     the MINIMUM is taken, which is lawful for every game judged;
#   * an explicit `as_of`, and a declared `vintage_selector.clock(...)`, both
#     BEAT the handoff, so wiring the caller properly retires this path;
#   * every feed answer records which of the three resolved it, so
#     `GATE_HANDOFF` is visible in the artifact and cannot be mistaken for the
#     call site having been fixed.
# =====================================================================
_GATE_CUTS: contextvars.ContextVar = contextvars.ContextVar(
    'nfl_readiness_gate_cuts', default=())


def _publish_gate_cut(cut, origin: str):
    """Record the cut a gate evaluation used, for the feed that follows it."""
    if cut is None:
        return
    _GATE_CUTS.set(tuple(_GATE_CUTS.get()) + ((cut, origin),))


def _consume_gate_cut():
    """The most conservative outstanding gate cut, and then forget it."""
    cuts = _GATE_CUTS.get()
    _GATE_CUTS.set(())
    if not cuts:
        return None, None
    best = min(c for c, _o in cuts)
    origins = sorted({o for _c, o in cuts})
    return best, {'n_gate_evaluations': len(cuts),
                  'n_distinct_cuts': len({c for c, _o in cuts}),
                  'origins': origins}


def gate_cuts_clear():
    """Drop any outstanding handoff. For tests and for a caller that wants the
    feed to refuse rather than inherit a gate it did not intend."""
    _GATE_CUTS.set(())


def _read_rows(path):
    txt = (gzip.open(path, 'rt').read() if str(path).endswith('.gz')
           else path.read_text())
    return list(csv.DictReader(txt.splitlines()))


def _latest_injuries(season: int, as_of=VS.UNSET):
    """(retrieved_at, rows) of the newest injuries capture lawful at the cut.

    THE OPERATOR VIEW, AND IT IS LABELLED AS ONE. Called with an explicit
    `as_of=None` this enumerates without a bound, which is the honest answer to
    "what does the feed look like right now" that `report()` exists to give an
    operator. It is NOT a model feed and nothing in the forecast path may take
    its rows: `latest_injuries_rows` below is the feed, and it refuses without
    a clock.
    """
    cut = (None if as_of is None
           else VS.resolve_as_of(as_of, caller='readiness._latest_injuries'))
    lawful = VS.lawful_paths('injuries', as_of=cut or _UNBOUNDED)
    if not lawful:
        return None, None
    ts, path = lawful[0]
    if path is None or not path.exists():
        return ts, None
    return ts, _read_rows(path)


def lawful_injuries_rows(season: int, as_of=VS.UNSET,
                         clock_basis='EXPLICIT',
                         handoff=None) -> Outcome:
    """THE FEED. Every team's newest injury block that is lawful at the cut.

    L1, AND WHY THE REPAIR IS A COMPOSITION RATHER THAN A FILTER.

    The old feed took the single newest capture on disk. Bounding that to the
    cut is necessary and not sufficient, because THE FEED IS NOT MONOTONE.
    Measured over the seven 2026 injuries blobs, week 1 only:

        2026-09-07T13:06Z   2 teams,  11 rows
        2026-09-08T17:06Z   2 teams,  11 rows
        2026-09-10T05:05Z   4 teams,  29 rows
        2026-09-10T12:07Z  30 teams, 139 rows
        2026-09-11T12:19Z  32 teams, 167 rows
        2026-09-13T12:47Z  20 teams,  48 rows   <- SHRINKS
        2026-09-13T15:45Z  32 teams, 182 rows

    A team filed on the 11th and absent from the 12:47 capture on the 13th is
    not a team with nobody injured, and `readiness` has said so since R4. So
    "the newest lawful FILE" and "each team's newest lawful BLOCK" are
    different answers, and the gate (`team_report_history`) has always used the
    second. Taking the first in the feed is how the gate and the feed came to
    disagree even inside the lawful window.

    This composes exactly the gate's rule, generalised over weeks so it needs
    no week argument: for each (team, week), the rows from the newest capture
    retrieved at or before the cut that carries that block. Gate and feed then
    resolve to the same vintage per team BY CONSTRUCTION, not by coincidence.

    The composition is itself a vintage: the contributing blobs are listed and
    a composite content hash is computed over them, so "which bytes" still has
    one answer.
    """
    if as_of is VS.UNSET or as_of is None:
        cut, clock_basis, handoff = _resolve_feed_cut(as_of)
    else:
        cut = VS.resolve_as_of(as_of, caller='readiness.lawful_injuries_rows')
    lawful = VS.lawful_paths('injuries', as_of=cut)
    if not lawful:
        sel = VS.select('injuries', as_of=cut)
        return sel
    rows, seen, parts, prov = [], {}, set(), {}
    for ts, path in lawful:                       # newest-first
        for r in _read_rows(path):
            if r.get('season') != str(season) or not r.get('team'):
                continue
            key = (r.get('team'), r.get('week'))
            if key in seen and seen[key] != ts:
                continue                          # an older block, superseded
            seen[key] = ts
            rows.append(r)
            parts.add((f'{key[0]}:{key[1]}', str(path.name)))
            # PER-BLOCK PROVENANCE, so "gate and feed chose the same vintage"
            # is a checkable claim rather than an argument about two code
            # paths that happen to be written the same way.
            prov[f'{key[0]}:{key[1]}'] = {
                'retrieved_at': ts,
                'blob': str(path.relative_to(_REPO))}
    if not rows:
        return Outcome.blocked(
            'INJURIES_NO_LAWFUL_ROWS',
            f'{len(lawful)} injuries capture(s) are lawful at '
            f'{cut.isoformat()} and none carries a {season} row. An empty '
            f'feed is a refusal, not an empty injury list.',
            cause=Cause.DATA, as_of=cut.isoformat(), n_lawful=len(lawful))
    blobs = sorted({p for _k, p in parts})
    return Outcome.ok(
        'INJURIES_LAWFUL_FEED', value=rows, spec_version=VS.SPEC_VERSION,
        as_of=cut.isoformat(), n_rows=len(rows),
        n_blocks=len(seen), n_teams=len({t for t, _w in seen}),
        n_captures_lawful=len(lawful), contributing_blobs=blobs,
        composite_sha256=VS.composite_hash(parts)[:16],
        block_provenance=prov,
        clock_basis=clock_basis, clock_handoff=handoff,
        newest_lawful_retrieved_at=lawful[0][0],
        selection_rule='per (team, week): the newest capture retrieved at or '
                       'before the cut that carries that block')


def latest_injuries_rows(season: int, as_of=VS.UNSET):
    """The rows the appearance mechanism eats. NEVER selected without a clock.

    KEPT AT THIS NAME AND THIS ARITY ON PURPOSE. The call site is
    `nfl/production/nonqb/layers.py:145`, which is hashed by Q9's frozen
    candidate identity `481f005f682cd721` and may not be edited. So the repair
    cannot add an argument there; it changes what this function does when it is
    called with one argument, and it declines to answer at all unless an
    upstream caller has declared the cut with `vintage_selector.clock(...)`.
    That is the C1 pattern: the corrected behaviour is placed upstream of the
    frozen module, not inside it.

    Raises rather than returning None, and the two failures are different
    exceptions because they need different responses:

        VintageClockUnresolved  the call site was never wired to a clock.
                                A defect in us. Fix the wiring.
        NoLawfulVintage         a clock exists and nothing predates it.
                                A true statement about the world. Refuse the
                                forecast; do not widen the cut.

    Returning None here would have reached `layers.py:148`, which reports
    DEFERRED[INJURIES_BLOB_MISSING] -- "the blob is missing" -- for what is
    actually "no lawful vintage at this cutoff" or "nobody gave me a clock".
    A refusal filed under the wrong name sends the reader to the wrong place,
    so this refuses under its own.
    """
    cut, basis, handoff = _resolve_feed_cut(as_of)
    o = lawful_injuries_rows(season, as_of=cut, clock_basis=basis,
                             handoff=handoff)
    if o.state is not State.PASS:
        raise VS.NoLawfulVintage(
            f'{o.code}: {o.detail} (as_of={cut.isoformat()}, '
            f'clock_basis={basis})')
    return o.value


def _resolve_feed_cut(as_of):
    """EXPLICIT, then DECLARED CONTEXT, then the GATE HANDOFF, then refuse.

    The order is the point. Wiring a caller properly retires the handoff
    without anyone having to remove it, and the basis travels with the answer
    so `GATE_HANDOFF` cannot be read as "the call site was fixed".
    """
    if as_of is not VS.UNSET and as_of is not None:
        return (VS.resolve_as_of(as_of, caller='readiness feed'), 'EXPLICIT',
                None)
    cur = VS.current_clock()
    if cur is not None:
        gate_cuts_clear()
        return cur.as_of, 'DECLARED_CONTEXT', cur.record()
    cut, info = _consume_gate_cut()
    if cut is not None:
        return cut, 'GATE_HANDOFF', info
    raise VS.VintageClockUnresolved(
        'VINTAGE_CLOCK_UNRESOLVED: the injuries feed was read with no as_of, '
        'no declared vintage_selector.clock(...) context, and no gate '
        'evaluation to inherit a cut from. Selecting without a clock means '
        'taking the newest capture on disk, which at HEAD 837d52f was '
        'post-kickoff for 28 of 32 week-1 teams. Refusing rather than '
        'guessing a cutoff.')


def injuries_readiness(season: int, week: int, teams, as_of=None) -> dict:
    ts, rows = _latest_injuries(season, as_of=as_of)
    if ts is None:
        return {'state': f'WAITING_FOR_INJURIES_{season}',
                'reason': 'no injuries capture has ever succeeded',
                'retrieved_at': None}
    if rows is None:
        return {'state': 'INJURIES_BLOB_MISSING',
                'reason': 'the manifest records a capture whose blob is absent',
                'retrieved_at': ts}
    wk = [r for r in rows if r.get('season') == str(season)
          and r.get('week') == str(week)]
    covered = sorted({r['team'] for r in wk if r.get('team')})
    want = sorted(set(teams))
    absent = [t for t in want if t not in covered]
    pop = {c: sum(1 for r in wk if (r.get(c) or '').strip())
           for c in ('report_status', 'practice_status',
                     'practice_primary_injury')}
    d = {'retrieved_at': ts, 'n_rows': len(wk),
         'teams_covered': len(covered), 'teams_required': len(want),
         'teams_absent': absent, 'column_population': pop}
    if not wk:
        d.update(state=f'INJURIES_{season}_EMPTY_FOR_WEEK_{week}',
                 reason='the feed is published but carries no row for this '
                        'week')
        return d
    if absent:
        d.update(
            state=f'INJURIES_{season}_PUBLISHED_BUT_INSUFFICIENT',
            reason=(f'the feed is published and parses, but covers '
                    f'{len(covered)} of {len(want)} slate teams. '
                    f'teammate_availability is a team-level feature, so a team '
                    f'with no rows cannot be distinguished from a team with '
                    f'nobody injured.'))
        return d
    if NEEDS_REPORT_STATUS and pop['report_status'] == 0:
        d.update(state=f'INJURIES_{season}_REPORT_STATUS_UNFILED',
                 reason='every row carries an empty report_status; '
                        'teammate_availability reads it, and an unfiled '
                        'designation is not an absence of injury')
        return d
    d.update(state='INJURIES_READY', reason='all slate teams covered and '
                                            'report_status filed')
    return d


def report(season: int = 2026, week: int = 1, teams=None,
           as_of=VS.UNSET) -> dict:
    """The single call an operator makes to learn what is blocking.

    TWO VIEWS, NAMED. With a clock -- passed, or declared by an upstream
    `vintage_selector.clock(...)` -- this is the replay view and answers what
    was knowable at that cutoff. With none it is the operator dashboard and
    answers what the feed looks like right now, which is the question an
    operator is actually asking. The returned dict says which, because
    `layers.py:130` reaches this on the slate-wide branch and a dashboard
    answer must never be mistaken there for a bounded one.
    """
    cut = None
    if as_of is not VS.UNSET and as_of is not None:
        cut = VS.parse_ts(as_of)
    else:
        _amb = VS.current_clock()
        if _amb is not None:
            cut = _amb.as_of
    teams = sorted(teams) if teams else _slate_teams(season, week)
    inj = injuries_readiness(season, week, teams, as_of=cut)
    inputs = {}
    for layer, needs in EL.REQUIRED_INPUTS.items():
        for n in needs:
            if 'injuries_' in n:
                inputs[n] = ('AVAILABLE' if inj['state'] == 'INJURIES_READY'
                             else 'MISSING')
    mx = EL.matrix(inputs)
    blocking = [l for l, v in mx.items()
                if v['allowed_runtime_role'] == 'BLOCKED']
    return {
        'artifact': 'NONQB_READINESS',
        'season': season, 'week': week, 'n_teams': len(teams),
        'as_of': cut.isoformat() if cut is not None else None,
        'clock_view': ('BOUNDED_REPLAY' if cut is not None
                       else 'UNBOUNDED_OPERATOR_DASHBOARD'),
        'overall_state': (inj['state'] if blocking else 'ENGINE_INPUTS_READY'),
        'blocking_layers': blocking,
        'injuries': inj,
        'eligibility': mx,
        'gates': json.loads(EL.STATE.read_text())['gates'],
        'next_action': _next_action(inj),
        'game_readiness': game_readiness(season, week),
        'future_requirements': future_requirements(season, week),
    }


def _next_action(inj) -> str:
    s = inj['state']
    if s.startswith('WAITING_FOR_INJURIES'):
        return ('none: the capture workflow already polls the feed and will '
                'record it when it publishes. No code change is required.')
    if s.endswith('PUBLISHED_BUT_INSUFFICIENT'):
        return (f'none in code. The feed covers {inj["teams_covered"]} of '
                f'{inj["teams_required"]} slate teams; the remaining teams file '
                f'their reports later in the game week and the periodic capture '
                f'will pick them up. Re-run readiness then.')
    if s.endswith('REPORT_STATUS_UNFILED'):
        return ('none in code. Game-status designations are filed later in the '
                'week; the capture path will record them.')
    if s == 'INJURIES_READY':
        return ('run the slate. D2 executes on the real source and D3-D5 '
                'follow without a code change.')
    return 'inspect the manifest: the capture record and the blob disagree.'


def _slate_teams(season, week):
    from nfl.capture import coverage as C
    p = C.load_week_plan(season, week)
    if p.state.name != 'PASS':
        return []
    out = set()
    for c in p.value:
        parts = c.game_id.split('_')
        out.update(parts[2:4])
    return sorted(out)


# =====================================================================
# R4 section G: readiness is a PER-GAME property, not a slate property.
#
# The slate dashboard ("2 of 32 teams covered") is the right thing to show an
# operator and the wrong thing to gate execution on. Two teams that have both
# filed can be forecast while thirty have not, and holding them back is a
# scheduling decision masquerading as a modelling one.
#
# NOTHING BELOW LOWERS THE FEATURE REQUIREMENT. A game executes D2 only when
# BOTH participating teams satisfy the same frozen input contract the slate
# check applies. What changes is the granularity of the answer.
# =====================================================================

# Declared, not tuned. A team's block is stale when the feed has been
# refreshed well past it and that team's rows have not moved -- 48 hours is
# long enough to span a normal practice-report cadence and short enough to
# catch a block that stopped updating.
STALE_HOURS = 48.0

GAME_STATES = (
    'READY_WITH_COMPLETE_INPUT',       # both teams, every contract field filed
    'READY',                           # both teams satisfy the contract
    # The club has EXPLICITLY STATED that it filed no game designations, and
    # that statement is captured, clocked and content-hashed in the vintage
    # manifest. Kept DISTINCT from 'READY' so the basis is never lost, and
    # spelled with a READY prefix because every consumer in this repository
    # tests `state.startswith('READY')` -- layers.py:119 (frozen),
    # football_engine.py:595-605, readiness.py:700, pool_audit.py:679,
    # completeness.py:123. See `explicit_no_designation` below.
    'READY_BY_EXPLICIT_NO_DESIGNATION',
    # NOBODY IN THE LEAGUE HAS FILED YET, so this club's silence carries no
    # club-specific information. Distinguished from the club-specific case
    # BY EVIDENCE, not by a guessed filing calendar: it is assigned only when
    # `seen` is empty for EVERY club in the capture. On the Tuesday before a
    # Thursday game that is the normal state of the world, and refusing it
    # produced a blank board for a game 51 hours away. READY-prefixed because
    # every consumer tests startswith('READY'); the projection is EARLY and
    # the artifact says so.
    'READY_BY_EARLY_VINTAGE_NO_LEAGUE_REPORT',
    'INJURY_REPORT_NOT_YET_FILED',     # a team has no row for this week at all
    'INJURY_REPORT_INCOMPLETE',        # rows exist, a contract field is unfilled
    'INJURY_REPORT_STALE',             # the feed moved on, this block did not
    'INJURY_REPORT_CHRONOLOGY_FAILURE',  # the capture is not before kickoff
    # No clock could be resolved, so no observation set can be bounded. It is
    # the WORST state deliberately: an unbounded read is more dangerous than a
    # missing report, because it looks like an answer.
    'READINESS_CLOCK_UNRESOLVED',
)
# Worst-first: a game takes the worst state of its two teams.
_SEVERITY = {s: i for i, s in enumerate(reversed(GAME_STATES))}


def _parse_ts(t):
    """Delegates to the canonical parser. One clock parser, not two."""
    return VS.parse_ts(t)


def as_of_cut(kickoff_utc=None, written_at=None):
    """The latest instant whose observations this run is allowed to consume.

    THE CONSUMED-CLOCK CONTRACT: `retrieved_at <= written_at < kickoff`.

    A forecast written at T may consume an observation retrieved at or before
    T, and nothing else. Kickoff bounds it further: a capture at or after
    kickoff is never pre-kickoff information whatever `written_at` says, so
    both bounds are applied and the tighter one wins. Returns None only when
    the caller supplied neither clock, which means "no cut" and is the
    operational `what is true now` reading rather than a replay.
    """
    # DELEGATED, NOT DUPLICATED. The gate and the feed drifted apart once by
    # each holding its own copy of this rule; there is now one copy, in
    # vintage_selector, and this name is kept because callers and tests use it.
    return VS.as_of_cut(kickoff_utc=kickoff_utc, written_at=written_at)


def _all_injury_captures(season: int, as_of=None):
    """Every successful injuries capture ELIGIBLE AT `as_of`, newest first.

    THE CUT IS APPLIED HERE, AT SELECTION, AND NOT AFTERWARDS.

    This function used to return every capture on disk and let the caller
    notice afterwards that the newest one was too late. That is not the same
    thing: `team_report_history` takes each team's block from the FIRST
    capture that carries it, so a post-kickoff capture became the team's block
    and every historical replay then refused with
    INJURY_REPORT_CHRONOLOGY_FAILURE -- while a perfectly good pre-kickoff
    report sat unused two files away. The guard was right and the selector
    never looked. Measured on 2026_01_NE_SEA: the pre-kickoff report exists in
    `injuries.1bf460ad261559a8.csv.gz`, retrieved 2026-09-08T16:06:25Z, 32.2
    hours before kickoff, carrying 11 rows for exactly NE and SEA.

    Selection is by `retrieved_at` and by nothing else -- never by filesystem
    order, file size, row count, or position in the manifest.
    """
    # DELEGATED to vintage_selector, which applies the same cut, rejects a
    # capture with no clock or no blob by name, and orders by
    # (retrieved_at, content_sha256) -- never by filesystem order, file size or
    # position in the manifest.
    #
    # `as_of=None` here means ENUMERATE EVERYTHING and is used by the suite to
    # show the cut is load-bearing. It is not a feed: the feed is
    # `lawful_injuries_rows`, which has no such mode.
    return VS.lawful_paths('injuries', as_of=(as_of if as_of is not None
                                              else _UNBOUNDED))


_CAPTURE_CACHE: dict = {}


def team_report_history(season: int, week: int, as_of=None):
    """team -> {newest_capture_with_rows, n_rows, column population}.

    `as_of` is part of the answer, so it is part of the CACHE KEY. Keying on
    (season, week) alone would let the first caller's clock decide what every
    later caller sees -- a replay served the operational `now` view, or worse,
    the operational view served a replay's cut and silently under-reported.
    A cache that restamps a hit under a different clock is not a cache.
    """
    key = (season, week, as_of.isoformat() if as_of is not None else None)
    if key in _CAPTURE_CACHE:
        return _CAPTURE_CACHE[key]
    seen, newest_overall = {}, None
    for ts, path in _all_injury_captures(season, as_of=as_of):
        if newest_overall is None:
            newest_overall = ts
        txt = (gzip.open(path, 'rt').read() if str(path).endswith('.gz')
               else path.read_text())
        rows = [r for r in csv.DictReader(txt.splitlines())
                if r.get('season') == str(season) and r.get('week') == str(week)]
        by_team = collections.defaultdict(list)
        for r in rows:
            if r.get('team'):
                by_team[r['team']].append(r)
        for t, rs in by_team.items():
            if t in seen:            # captures are newest-first
                continue
            seen[t] = {'newest_capture': ts, 'n_rows': len(rs),
                       'blob': str(path.relative_to(_REPO)),
                       'population': {
                           c: sum(1 for r in rs if (r.get(c) or '').strip())
                           for c in ('report_status', 'practice_status',
                                     'practice_primary_injury')}}
    _CAPTURE_CACHE[key] = (seen, newest_overall)
    return _CAPTURE_CACHE[key]


def cache_clear():
    _CAPTURE_CACHE.clear()


_KICKOFF_CACHE: dict = {}


def team_kickoff(season: int, week: int, team: str):
    """The team's own kickoff for this week, from the capture week plan.

    A team plays once a week, so `no clock supplied` has a correct answer and
    does not need to be guessed at. Returns None only when the plan itself
    cannot be loaded or does not contain the team.
    """
    key = (season, week)
    if key not in _KICKOFF_CACHE:
        table = {}
        try:
            from nfl.capture import coverage as C
            plan = C.load_week_plan(season, week)
            if plan.state.name == 'PASS':
                for c in plan.value:
                    for t in c.game_id.split('_')[2:4]:
                        ko = c.kickoff_utc
                        table[t] = (ko.isoformat().replace('+00:00', 'Z')
                                    if hasattr(ko, 'isoformat') else ko)
        except Exception:                                     # noqa: BLE001
            table = {}
        _KICKOFF_CACHE[key] = table
    return _KICKOFF_CACHE[key].get(team)


def explicit_no_designation(season: int, team: str, kickoff_utc=None,
                            as_of=None) -> dict | None:
    """The club's own "we filed no game designations" statement, or None.

    THE THIRD STATE THE INJURIES FEED CANNOT SPELL.

    `nfl/capture/delivered_injuries.py:426-452` names three genuinely different
    team states and observes that the nflverse schema can express only two:

      (a) rows filed, designations present   -- report_status is populated
      (b) rows filed, no designation FILED YET -- report_status blank
      (c) the club has EXPLICITLY STATED it has NO designations

    (b) is an absence of evidence and (c) is evidence. They are byte-identical
    in the feed, which is why the gate below could only ever read (c) as (b)
    and refuse a club for being healthy. Measured on 2026 week 1 at the
    DEN@KC cut: the gate deferred exactly {DEN, HOU, MIA, MIN, WAS}, and the
    delivered package carries an explicit (c) statement for exactly those five
    clubs and no others. The gate was not detecting missing reports. It was
    detecting (c) and calling it (b).

    THIS READS EVIDENCE. IT DOES NOT INVENT A THRESHOLD.

    `nfl/research/slate_audit/EVIDENCE_CEILING_injury_report_publication.md`
    withdrew an earlier repair that tried to separate (b) from (c) by a rule
    over blank columns, correctly, because that is a threshold chosen to make
    games pass. This is the other route the same write-up names as sufficient:
    the official final report captured as its own source, carrying its own
    report type and game date. Nothing here is derived from row counts, blank
    counts, or how many clubs would pass.

    WHAT IT WILL NOT DO.

      * It does not clear INJURY_REPORT_NOT_YET_FILED. A club with no rows at
        all has filed no PRACTICE report either, and this statement speaks only
        to game designations. Those are different fields with different
        consumers.
      * It does not clear INJURY_REPORT_STALE or a chronology failure. Both are
        statements about the capture, not about the club.
      * It applies the SAME as-of cut as the rest of the gate. A statement
        retrieved after the cut is not evidence this forecast may consume.
    """
    ko = VS.parse_ts(kickoff_utc or team_kickoff(season, 1, team))
    if ko is None:
        return None
    # PARSED ONCE, HERE. The production caller passes an already-parsed cut,
    # so `got > as_of` worked on that path and only that path; any caller
    # handing in the ISO string every other selector in this module accepts
    # got a TypeError comparing a datetime to a str. The cut is a clock
    # wherever it comes from.
    cut = VS.parse_ts(as_of) if as_of is not None else None
    # An NFL game date is the LOCAL date the league publishes the fixture
    # under. For a kickoff instant in UTC that is either the same UTC date or
    # the one before it -- an evening US kickoff rolls past midnight UTC. Both
    # are accepted and nothing narrower is assumed, because assuming a specific
    # offset here would be a constant nobody derived.
    ok_dates = {(ko.date()).isoformat(),
                (ko.date() - _dt.timedelta(days=1)).isoformat()}
    try:
        lines = VS.MANIFEST.read_text().splitlines()
    except OSError:
        return None
    best = None
    for line in lines:
        if 'explicit_no_designations' not in line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        v = row.get('value')
        if not isinstance(v, dict) or row.get('season') != season:
            continue
        for rec in (v.get('explicit_no_designations') or []):
            if rec.get('team') != team:
                continue
            if rec.get('kind') != 'EXPLICIT_TEAM_NO_INJURY_DESIGNATIONS':
                continue
            if rec.get('game_date') not in ok_dates:
                continue
            got = VS.parse_ts(rec.get('retrieved_at'))
            if got is None or got >= ko:
                continue
            if cut is not None and got > cut:
                continue
            if best is None or got > VS.parse_ts(best['retrieved_at']):
                best = rec
    return best


def team_readiness(season: int, week: int, team: str, kickoff_utc=None,
                   written_at=None) -> dict:
    """One team's state against the frozen input contract.

    NO CLOCK IS NOT `ANY CLOCK`. Called bare, this used to apply no cut at
    all, so the newest capture on disk answered -- and after a game has been
    played that capture is post-kickoff, which is how a team whose report was
    never filed in time reads READY. The team's own kickoff is resolved from
    the week plan instead, so the default is the safe reading rather than the
    unbounded one. If the plan cannot supply it, that is said out loud
    (`READINESS_CLOCK_UNRESOLVED`) rather than silently treated as no bound.
    """
    # L2. THE SECOND HALF OF THE CONTRACT, AND THE ONE THAT WAS MISSING.
    #
    # `layers.py:117` calls this with `kickoff_utc` and never with
    # `written_at`, although `observed_before` -- which IS the forecast's
    # written_at -- is a parameter of the enclosing function. `as_of_cut` then
    # resolved to `kickoff - 1us` instead of `written_at`, admitting every
    # capture retrieved between the forecast's own cutoff and kickoff.
    # Measured at HEAD 837d52f over the 20 teams of the 10 executable week-1
    # games, at a written_at of kickoff minus 24 hours: 85 player-rows differ,
    # almost all of them the Friday game-status filing landing after a Thursday
    # cutoff ('' -> 'Out', '' -> 'Questionable', '' -> 'Doubtful').
    #
    # layers.py is hashed by Q9's frozen candidate identity and may not be
    # edited, so the bound is taken from the clock an upstream caller declared.
    # Only `written_at` is taken from the context: `as_of` already carries the
    # declaring game's kickoff, and this team may belong to a different game
    # whose own kickoff bound is applied below.
    if written_at is None:
        _amb = VS.current_clock()
        if _amb is not None and _amb.written_at:
            written_at = _amb.written_at
    resolved_ko = kickoff_utc or team_kickoff(season, week, team)
    if resolved_ko is None and written_at is None:
        return {'team': team, 'state': 'READINESS_CLOCK_UNRESOLVED',
                'reason': f'no kickoff could be resolved for {team} in '
                          f'{season} week {week} and no written_at was '
                          f'supplied, so there is no clock to judge which '
                          f'observations existed yet. Refusing to answer is '
                          f'not the same as answering from everything on '
                          f'disk.',
                'n_rows': 0, 'newest_capture': None, 'as_of': None}
    kickoff_utc = resolved_ko
    cut = as_of_cut(kickoff_utc, written_at)
    _publish_gate_cut(cut, f'team_readiness:{season}w{week}:{team}')
    seen, newest_overall = team_report_history(season, week, as_of=cut)
    d = seen.get(team)
    if d is None:
        # ABSENCE IS ABSENCE. A team with no filed report is NOT a team with
        # nobody injured, and teammate_availability is a team-level feature, so
        # the two cannot be told apart from the data.
        # ABSENCE UNDER A CUT IS STILL ABSENCE, and it is reported honestly
        # rather than by reaching past the cut for something newer. Naming the
        # cut in the reason is what stops `not yet filed` being read as `this
        # team has nobody injured` when the truth is `nothing had been filed
        # YET at the moment this forecast was written`.
        # IS THIS CLUB SILENT, OR IS THE WHOLE LEAGUE? Different facts.
        # A club that has not filed while 30 others have is a gap in OUR
        # evidence about that club. A week where NOBODY has filed is a report
        # that does not exist yet, and reading the second as the first blanks
        # the board for every game in the week.
        if not seen:
            return {
                'team': team,
                'state': 'READY_BY_EARLY_VINTAGE_NO_LEAGUE_REPORT',
                'reason': f'NO club has an injuries row for {season} week '
                          f'{week} in any capture'
                          + (f' retrieved at or before {cut.isoformat()}'
                             if cut is not None else '')
                          + f'. The report does not exist yet rather than '
                            f'{team} being silent about it, so this is an '
                            f'EARLY vintage. It is NEVER read as absence of '
                            f'injury: every player keeps the availability '
                            f'uncertainty his own evidence carries.',
                'n_rows': 0, 'newest_capture': None,
                'projection_vintage': 'EARLY',
                'league_wide_absence': True,
                'as_of': cut.isoformat() if cut is not None else None}
        return {'team': team, 'state': 'INJURY_REPORT_NOT_YET_FILED',
                'reason': f'no injuries row for {team} in any capture for '
                          f'{season} week {week}'
                          + (f' retrieved at or before {cut.isoformat()}'
                             if cut is not None else '')
                          + '. This is ABSENCE OF A REPORT '
                            'and is never read as absence of injury.',
                'n_rows': 0, 'newest_capture': None,
                'as_of': cut.isoformat() if cut is not None else None}
    got = _parse_ts(d['newest_capture'])
    ko = _parse_ts(kickoff_utc)
    wr = _parse_ts(written_at)
    if (ko and got and got >= ko) or (wr and got and got > wr):
        # POST-SELECTION ASSERTION. Selection now applies the cut, so reaching
        # here means the selector handed back something it was told to
        # exclude. It is kept precisely because it is meant to be unreachable:
        # a guard removed once it stops firing is a guard that cannot tell you
        # when the thing it guarded against comes back.
        return {'team': team, 'state': 'INJURY_REPORT_CHRONOLOGY_FAILURE',
                'reason': f'SELECTOR_RETURNED_INELIGIBLE_CAPTURE: the capture '
                          f'carrying {team}\'s rows was retrieved at '
                          f'{d["newest_capture"]}, which is not strictly '
                          f'before kickoff {kickoff_utc} / written_at '
                          f'{written_at}. The as-of cut was '
                          f'{cut.isoformat() if cut else "none"}.',
                'as_of': cut.isoformat() if cut is not None else None, **d}
    newest = _parse_ts(newest_overall)
    if got and newest and (newest - got).total_seconds() > STALE_HOURS * 3600:
        return {'team': team, 'state': 'INJURY_REPORT_STALE',
                'as_of': cut.isoformat() if cut is not None else None,
                'reason': f'the feed was refreshed at {newest_overall} but '
                          f'{team}\'s block has not changed since '
                          f'{d["newest_capture"]}, more than {STALE_HOURS:g}h '
                          f'earlier',
                **d}
    pop = d['population']
    if NEEDS_REPORT_STATUS and pop['report_status'] == 0:
        # An unfiled designation is not an absence of injury -- UNLESS the club
        # has said in its own words that it has none, in which case the absence
        # IS the filed fact. `explicit_no_designation` returns that statement
        # only when it is captured, hashed, and lawful at this same cut.
        # NEEDS_REPORT_STATUS is unchanged and still True: this does not lower
        # the requirement, it recognises a second way of meeting it.
        nd = explicit_no_designation(season, team, kickoff_utc=kickoff_utc,
                                     as_of=cut)
        if nd is not None:
            return {'team': team,
                    'state': 'READY_BY_EXPLICIT_NO_DESIGNATION',
                    'as_of': cut.isoformat() if cut is not None else None,
                    'reason': f'{team} has {d["n_rows"]} row(s) and no filed '
                              f'designation, and the club has EXPLICITLY '
                              f'stated it filed none: '
                              f'"{nd.get("evidence_text")}" '
                              f'({nd.get("report_period")}, game date '
                              f'{nd.get("game_date")}), from '
                              f'{nd.get("source_id")} retrieved '
                              f'{nd.get("retrieved_at")}. This is the filed '
                              f'fact, not an absence of one.',
                    'no_designation_evidence': {
                        k: nd.get(k) for k in
                        ('kind', 'evidence_text', 'report_period', 'game_date',
                         'source_id', 'source_url', 'content_sha256',
                         'retrieved_at', 'publication_time',
                         'source_modified_time', 'locator')},
                    **d}
        return {'team': team, 'state': 'INJURY_REPORT_INCOMPLETE',
                'as_of': cut.isoformat() if cut is not None else None,
                'reason': f'{team} has {d["n_rows"]} row(s) but report_status '
                          f'is unfilled on every one. teammate_availability '
                          f'reads it, and an unfiled designation is not an '
                          f'absence of injury.',
                **d}
    complete = all(pop[c] == d['n_rows'] for c in
                   ('report_status', 'practice_status'))
    return {'team': team,
            'as_of': cut.isoformat() if cut is not None else None,
            'state': 'READY_WITH_COMPLETE_INPUT' if complete else 'READY',
            'reason': 'the team satisfies the frozen input contract',
            **d}


def game_readiness(season: int = 2026, week: int = 1, games=None,
                   written_at=None) -> dict:
    """Per-game execution readiness. A game is ready only if BOTH teams are.

    Each game is judged on its OWN two teams. A missing report elsewhere on the
    slate changes nothing here, and the suite checks that.

    `written_at` is the consumed clock. Omitted, each game is judged strictly
    before its OWN kickoff, which is the operational reading. Supplied, it
    bounds every game as well -- that is the historical-replay reading, and
    without it a replay would silently consume whatever has landed since.
    """
    from nfl.capture import coverage as C
    if written_at is None:
        _amb = VS.current_clock()
        if _amb is not None and _amb.written_at:
            written_at = _amb.written_at
    if games is None:
        p = C.load_week_plan(season, week)
        if p.state.name != 'PASS':
            return {'artifact': 'NONQB_GAME_READINESS', 'season': season,
                    'week': week, 'fatal': f'{p.code}: {p.detail}',
                    'games': []}
        games = sorted({c.game_id: c.kickoff_utc for c in p.value}.items())
    out, counts = [], collections.Counter()
    for gid, ko in games:
        away, home = gid.split('_')[2:4]
        ko_s = (ko.isoformat().replace('+00:00', 'Z')
                if hasattr(ko, 'isoformat') else ko)
        tr = [team_readiness(season, week, t, kickoff_utc=ko_s,
                             written_at=written_at)
              for t in (away, home)]
        worst = min(tr, key=lambda d: _SEVERITY[d['state']])
        ready = all(t['state'].startswith('READY') for t in tr)
        state = (('READY_WITH_COMPLETE_INPUT'
                  if all(t['state'] == 'READY_WITH_COMPLETE_INPUT' for t in tr)
                  else 'READY') if ready else worst['state'])
        counts[state] += 1
        out.append({'game_id': gid, 'kickoff_utc': ko_s, 'state': state,
                    'may_execute_d2': ready,
                    'blocking_team': None if ready else worst['team'],
                    'reason': ('both teams satisfy the frozen input contract'
                               if ready else worst['reason']),
                    'teams': tr})
    # ONE CUT FOR A SLATE-WIDE ANSWER, AND IT IS THE EARLIEST KICKOFF'S.
    #
    # The per-game gates above published sixteen different cuts. A slate-wide
    # consumer has no single game, so the only cut lawful for ALL of them is
    # the tightest -- anything later is post-kickoff for whichever game starts
    # first. The per-game publishes are replaced rather than added to.
    slate_cuts = [as_of_cut(g['kickoff_utc'], written_at) for g in out]
    slate_cuts = [c for c in slate_cuts if c is not None]
    _GATE_CUTS.set(())
    if slate_cuts:
        _publish_gate_cut(min(slate_cuts), f'game_readiness:{season}w{week}')
    return {'artifact': 'NONQB_GAME_READINESS', 'season': season, 'week': week,
            'written_at': written_at,
            'slate_as_of': (min(slate_cuts).isoformat() if slate_cuts
                            else None),
            'n_games': len(out),
            'n_executable': sum(1 for g in out if g['may_execute_d2']),
            'state_counts': dict(counts),
            'stale_hours': STALE_HOURS,
            'states_defined': list(GAME_STATES),
            'note': 'a game is judged on its own two teams only; a missing '
                    'report elsewhere on the slate does not change it, and a '
                    'missing report for a team is never read as that team '
                    'having no injuries',
            'games': out}


# =====================================================================
# R4 section M: the two future requirements are DIFFERENT and are named
# separately. Collapsing them into one "waiting on data" line is how a week-2
# forecast quietly runs on 2025 as though it were last week.
# =====================================================================
FUTURE_REQUIREMENTS = {
    'injuries_{season}': {
        'needed_from': 'WEEK 1',
        'serves': ['appearance (practice_progression, teammate_availability)'],
        'refusal_if_absent': 'INJURY_REPORT_NOT_YET_FILED / '
                             'INJURY_REPORT_INCOMPLETE, per game',
        'substitute': 'NONE. A reduced-feature fit would be a different model '
                      'wearing an accepted model name.',
    },
    'pbp_participation_{season}': {
        'needed_from': 'WEEK 2',
        'serves': ['participation (Stage-2 ewma_hl2 over prior pass-snap '
                   'shares)',
                   'targets_carries (the point forecast C is a prior share)',
                   'team_environment (team_dropbacks_part is a P4B metric)'],
        'refusal_if_absent': 'PARTICIPATION_HISTORY_STALE',
        'substitute': 'NONE. snap_counts is registered but carries no pass/run '
                      'split, so it cannot bound pass-play participation.',
        'why_week_1_is_safe': 'a week-1 forecast conditions only on PRIOR '
                              'seasons; panel_p3 carries 2020-2025.',
    },
}


def future_requirements(season: int = 2026, week: int = 1) -> dict:
    """What is needed, when, and what happens if it does not arrive.

    Both are reported at every week so neither can be forgotten because the
    other is the live one.
    """
    from nfl.production.nonqb import participation_prior as PP
    out = {}
    for tmpl, spec in FUTURE_REQUIREMENTS.items():
        name = tmpl.format(season=season)
        d = dict(spec)
        d['source'] = name
        if tmpl.startswith('injuries'):
            gr = game_readiness(season, week)
            d['state'] = ('SATISFIED' if gr.get('n_executable') == gr.get('n_games')
                          and gr.get('n_games') else 'NOT_SATISFIED')
            d['detail'] = (f"{gr.get('n_executable', 0)} of "
                           f"{gr.get('n_games', 0)} games executable")
        else:
            o = PP.share_prior(season, week,
                               [{'gsis_id': '_probe', 'position': 'WR'}])
            d['state'] = ('SATISFIED' if o.state.name == 'PASS'
                          else 'NOT_SATISFIED')
            d['detail'] = f'{o.state.value}[{o.code}]'
            d['newest_history_ordinal'] = (
                o.evidence.get('newest_history_ordinal')
                or o.evidence.get('newest_ordinal'))
            d['binds_at_week'] = 2
            d['binding_now'] = week >= 2
        out[name] = d
    return {'artifact': 'NONQB_FUTURE_REQUIREMENTS', 'season': season,
            'week': week, 'requirements': out,
            'note': 'two separate sources with two separate refusals. Week 2 '
                    'may not silently use 2025 as though it were last week.'}
