"""Kickoff-anchored capture cadence. G0A item 1.

WHY NOT "ONCE A DAY"

A once-per-week or once-per-day capture reproduces the defect being fixed. The
NFL reporting cascade is anchored to each GAME, not to a nominal Sunday: a
Thursday game's "Friday-equivalent" final status lands on Wednesday. 2026 week 1
alone has games on Wed 09-09, Thu 09-10, Sun 09-13 and Mon 09-14, so a
Sunday-shaped schedule would miss the first two entirely.

PROVENANCE OF THE CADENCE BELOW

From the networked researcher's return (Directive 3 §5), treated as evidence
rather than as architecture authority:

  * standard Sunday games -- practice reports Wed/Thu/Fri, game status Friday
  * Thursday games -- compressed schedule
  * Monday games -- shifted schedule
  * filing deadline generally 4:00 p.m. New York time
  * official inactives approximately 90 minutes before kickoff

Only the Sunday pattern and the two fixed times were given explicitly. The
Thursday, Monday and Saturday day-offsets below are DERIVED by shifting the
Wed/Thu/Fri pattern to preserve its relationship to the game, and each is marked
`confirmed=False` so it is visibly an inference and can be corrected without
archaeology. They are never silently presented as the official calendar.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
from typing import Optional
from zoneinfo import ZoneInfo

NY = ZoneInfo('America/New_York')

# The two clock facts the researcher gave explicitly.
FILING_DEADLINE_LOCAL = dt.time(16, 0)      # 4:00 p.m. New York
INACTIVES_LEAD = dt.timedelta(minutes=90)   # ~90 min before kickoff

# ACCEPTABLE CAPTURE WINDOWS, declared per target rather than shared.
#
# A single symmetric tolerance was the defect: with +/- 6h, a routine poll five
# hours BEFORE a 4pm filing deadline counted as having captured the report --
# a capture taken before the thing existed satisfying the target for it. Owner
# Directive 4 section 2: targeted deadlines must have targeted executions, and an
# unrelated capture hours earlier may not discharge them.
#
# Every window below therefore OPENS at or after the moment the artifact can
# exist, and closes while it is still the current vintage.
WINDOWS: dict[str, tuple[dt.timedelta, dt.timedelta]] = {
    # Report is filed at 4pm NY. Nothing before that can contain it. It stays the
    # current vintage until the next day's filing.
    'practice': (dt.timedelta(0), dt.timedelta(hours=20)),
    'final_status': (dt.timedelta(0), dt.timedelta(hours=20)),
    # The tight one. Inactives post ~90 min before kickoff; after kickoff the
    # pre-kickoff information state no longer exists to be captured.
    'inactives': (dt.timedelta(0), dt.timedelta(minutes=80)),
    'seal': (dt.timedelta(0), dt.timedelta(minutes=1)),
    'unschedulable': (dt.timedelta(0), dt.timedelta(0)),
}

# ARTIFACT SCOPE, NOT DISCHARGE AUTHORITY. Read the next paragraph before using
# this constant for anything.
#
# A practice report is filed per team per week; inactives are posted per game at
# that game's kickoff minus 90. That is a true statement about what the retrieved
# BYTES cover, and it is why `execution.declare` may legitimately name several
# targets for one fetch.
#
# It is NOT a statement about which targets need an explicitly declared identity.
# Until 2026-09-07 `_clears` consulted this tuple and let ANY in-window capture
# discharge a kind that was not listed here, and two practice obligations were
# duly discharged by the periodic sweep -- unanchored, game_id None, zero
# attributed captures, coverage PASS. The governing rule is not "only certain
# source kinds require game identity"; it is:
#
#     every event-anchored coverage obligation requires an explicitly declared
#     target identity and an authorised discharging execution basis.
#
# `_clears` therefore no longer reads this constant, and `test_capture_schedule`
# asserts that it does not.
GAME_SPECIFIC_KINDS = ('inactives',)

# Kinds that carry a coverage obligation at all. `seal` and `unschedulable` are
# bookkeeping rows, not evidence deadlines.
NON_OBLIGATION_KINDS = ('seal', 'unschedulable')

# Day offsets BEFORE the game date on which a practice/status report is due,
# keyed by the game's weekday. `final` marks the game-status report.
#   Mon=0 ... Sun=6
_CADENCE: dict[int, dict] = {
    6: {'offsets': [(4, 'practice_wed'), (3, 'practice_thu'), (2, 'final_status_fri')],
        'confirmed': True,
        'note': 'Standard Sunday game: Wed/Thu/Fri, status Friday. Explicitly '
                'reported.'},
    0: {'offsets': [(5, 'practice_wed'), (4, 'practice_thu'), (3, 'final_status_fri')],
        'confirmed': False,
        'note': 'Monday game: "shifted schedule" reported without day detail. '
                'DERIVED by holding the Wed/Thu/Fri calendar days fixed.'},
    3: {'offsets': [(3, 'practice_mon'), (2, 'practice_tue'), (1, 'final_status_wed')],
        'confirmed': False,
        'note': 'Thursday game: "compressed schedule" reported without day '
                'detail. DERIVED by compressing to the three days before.'},
    5: {'offsets': [(3, 'practice_wed'), (2, 'practice_thu'), (1, 'final_status_fri')],
        'confirmed': False,
        'note': 'Saturday game: not reported. DERIVED from the Sunday pattern '
                'shifted one day.'},
}


@dataclasses.dataclass(frozen=True)
class CaptureDue:
    game_id: str
    label: str
    due_utc: dt.datetime
    kind: str            # 'practice' | 'final_status' | 'inactives' | 'seal'
    confirmed: bool
    note: str
    # Kickoff, carried on every target rather than recomputed. Directive 7 §4
    # requires it in the manifest, and for a practice target it is NOT
    # recoverable from due_utc -- that is a filing deadline days earlier, tied
    # to no fixed offset from the game.
    kickoff_utc: Optional[dt.datetime] = None

    @property
    def window(self) -> tuple:
        lo, hi = WINDOWS.get(self.kind, (dt.timedelta(0), dt.timedelta(0)))
        return self.due_utc + lo, self.due_utc + hi

    def satisfied_by(self, performed_utc) -> bool:
        """Is this capture inside the window? A pure timing predicate.

        Deliberately NOT the discharge decision. Window membership is necessary
        and not sufficient -- a routine `injuries` mirror poll landing inside the
        inactives window must not discharge an inactives target -- but mixing the
        two questions into one predicate made a timing check depend on registry
        state, which is neither testable in isolation nor honest about what it is
        asserting. Authority is `discharges` below.
        """
        lo, hi = self.window
        return lo <= performed_utc <= hi

    def discharges(self, performed_utc, source: str) -> bool:
        """Does this capture, from THIS source, actually clear the target?

        Window membership AND source authority. `registry.can_discharge` holds
        the second rule and nothing in this module used to call it -- a gap the
        adversarial tests found and that nobody owned: `injuries` is a terminal
        weekly snapshot, not the intraweek cascade, so it may never clear a
        practice, final-status or inactives deadline however well-timed it is.
        """
        if not self.satisfied_by(performed_utc):
            return False
        from nfl.capture import registry as _reg
        return _reg.can_discharge(source, self.kind)

    def as_dict(self) -> dict:
        lo, hi = self.window
        return {'game_id': self.game_id, 'label': self.label,
                'due_utc': self.due_utc.isoformat(), 'kind': self.kind,
                'window_start_utc': lo.isoformat(),
                'window_end_utc': hi.isoformat(),
                'kickoff_utc': (self.kickoff_utc.isoformat()
                                if self.kickoff_utc else None),
                'cadence_confirmed': self.confirmed, 'note': self.note}


def _parse_kick(gameday: str, gametime: Optional[str]) -> dt.datetime:
    """Local (New York) kickoff -> UTC. `gametime` is local per the schedule
    file; when absent we refuse rather than assume a time, because assuming
    would silently move every derived deadline."""
    if not gametime or not str(gametime).strip():
        raise ValueError(
            f'{gameday}: no gametime. A kickoff-anchored cadence cannot be '
            f'computed from a date alone, and defaulting the time would shift '
            f'every capture deadline by an unknown amount.')
    h, m = str(gametime).strip().split(':')[:2]
    naive = dt.datetime.strptime(gameday, '%Y-%m-%d').replace(
        hour=int(h), minute=int(m))
    return naive.replace(tzinfo=NY).astimezone(dt.timezone.utc)


def capture_plan(game_id: str, gameday: str,
                 gametime: Optional[str]) -> list[CaptureDue]:
    """Every capture owed for one game, in time order."""
    kick = _parse_kick(gameday, gametime)
    game_date = dt.datetime.strptime(gameday, '%Y-%m-%d').date()
    wd = game_date.weekday()

    cad = _CADENCE.get(wd)
    if cad is None:
        # Tue/Wed games happen (2026 week 1 opens on a Wednesday). No reported
        # cadence exists for them; say so rather than inventing one.
        cad = {'offsets': [(2, 'practice_a'), (1, 'final_status_b')],
               'confirmed': False,
               'note': f'Game on weekday {wd}: no reported cadence. DERIVED '
                       f'fallback of the two preceding days.'}

    out: list[CaptureDue] = []
    for days_before, label in cad['offsets']:
        d = game_date - dt.timedelta(days=days_before)
        due_local = dt.datetime.combine(d, FILING_DEADLINE_LOCAL, tzinfo=NY)
        out.append(CaptureDue(
            game_id=game_id, label=label,
            due_utc=due_local.astimezone(dt.timezone.utc),
            kind='final_status' if label.startswith('final') else 'practice',
            confirmed=cad['confirmed'], note=cad['note'], kickoff_utc=kick))

    out.append(CaptureDue(
        game_id=game_id, label='inactives',
        due_utc=kick - INACTIVES_LEAD, kind='inactives',
        confirmed=True, kickoff_utc=kick,
        note='Official inactives ~90 minutes before kickoff. This is the '
             'capture that resolves Questionable to 0/1.'))
    out.append(CaptureDue(
        game_id=game_id, label='kickoff_seal', due_utc=kick, kind='seal',
        confirmed=True, kickoff_utc=kick,
        note='Seals the vintage log for this game. Nothing after this is '
             'pre-kickoff information.'))
    return sorted(out, key=lambda c: c.due_utc)


def season_plan(games: list[dict], through: Optional[dt.datetime] = None
                ) -> list[CaptureDue]:
    """Plan for many games. `games` rows come from the schedule file and must
    carry game_id, gameday, gametime."""
    plan: list[CaptureDue] = []
    unschedulable: list[CaptureDue] = []
    for g in games:
        gid = (g.get('game_id') or '').strip()
        if not gid:
            # Schedulable in principle, but a capture that cannot be attributed
            # to a game is not a usable vintage. Raise it as a debt rather than
            # planning captures under '<unknown>'.
            unschedulable.append(CaptureDue(
                game_id='<missing>', label='unschedulable',
                due_utc=dt.datetime.max.replace(tzinfo=dt.timezone.utc),
                kind='unschedulable', confirmed=False,
                note=f'Schedule row has no game_id ({sorted(g)[:6]}); captures '
                     f'could not be attributed to a game.'))
            continue
        try:
            # `.get` on every field: reading g['game_id'] directly raised
            # KeyError past a ValueError-only handler, so ONE malformed row lost
            # the whole season's plan. A bad row must cost that row.
            plan.extend(capture_plan(gid, g['gameday'], g.get('gametime')))
        except (ValueError, KeyError, TypeError) as exc:
            unschedulable.append(CaptureDue(
                game_id=gid, label='unschedulable',
                due_utc=dt.datetime.max.replace(tzinfo=dt.timezone.utc),
                kind='unschedulable', confirmed=False,
                note=f'Cadence not computable for this row ({exc}). This is a '
                     f'debt, not a skip.'))
    if through is not None:
        plan = [c for c in plan if c.due_utc <= through]
    # Unschedulable entries are appended AFTER the window filter, never through
    # it. They sit at datetime.max so any `through` cutoff removed them --
    # turning the debt this branch exists to raise back into the silent skip it
    # exists to prevent.
    return sorted(plan, key=lambda c: c.due_utc) + unschedulable


def _clears(target: CaptureDue, performed) -> bool:
    """One performed capture against one target. The discharge decision.

    THE RULE, AND WHY IT IS UNIVERSAL

    A capture discharges an event-anchored obligation only when the execution
    DECLARED that exact obligation before it fetched anything. Timing is
    necessary and never sufficient. Concretely, a `(ts, src, game_id, kind)`
    tuple clears a target only if:

        game_id == target.game_id      explicit target identity
        kind    == target.kind         the declared obligation, not a neighbour
        window + source authority      via `target.discharges`

    and the tuple exists at all only because `execution.eligibility` already
    passed the declared target on execution basis, window, source authority,
    persisted bytes, sha and provenance.

    WHAT THIS REPLACED, AND THE DEFECT IT LET THROUGH

    This used to read `GAME_SPECIFIC_KINDS` and require a matching `game_id`
    only for kinds inside it. `practice` was outside it, so an UNATTRIBUTED
    capture -- `(ts, src, None)` -- cleared any practice target whose window it
    happened to fall in. On 2026-09-07 two practice obligations,
    2026_01_NE_SEA/practice_a and 2026_01_SF_LA/practice_mon, were discharged by
    the `*/30` periodic sweep at 20:05:40Z and 20:37:36Z: no declaration, no
    anchored basis, `game_id` None, `attributed_captures: 0`, and coverage
    nevertheless reported PASS with the first real T-90 window still 49.5 hours
    away. That is exactly what Directive 7 section 5 forbids, and
    `nfl/tests/fixtures/regression_2026_09_07_practice_false_cover.json` holds
    the observed state so the refusal stays testable.

    An unattributed capture is still real evidence and stays in the manifest. It
    simply is not THIS target's evidence, and nothing about the passage of time
    can make it so.
    """
    if isinstance(performed, tuple):
        parts = (tuple(performed) + (None, None))[:4]
        ts, src, game_id, kind = parts
        if not game_id:
            # No declared target identity. Under the universal rule this cannot
            # discharge anything, whatever its kind and however well timed.
            return False
        if game_id != target.game_id:
            return False
        if kind is not None and kind != target.kind:
            # Declared for a different obligation of the same game. Windows for
            # `practice` and `final_status` overlap, so without this a declared
            # practice capture would silently clear a final-status deadline.
            return False
        return target.discharges(ts, src)
    return target.satisfied_by(performed)


def missed_captures(plan: list[CaptureDue], performed_utc: list[dt.datetime],
                    now: Optional[dt.datetime] = None) -> list[CaptureDue]:
    """Due targets no capture landed inside the window for.

    There is no `tolerance` parameter any more, and its removal is the point. A
    shared symmetric tolerance let a poll taken hours BEFORE a filing deadline
    discharge the target for a report that did not yet exist. Each target now
    declares its own window and only a capture inside it counts.
    """
    now = now or dt.datetime.now(dt.timezone.utc)
    performed = list(performed_utc)
    missed = []
    for c in plan:
        if c.kind in ('seal', 'unschedulable'):
            continue
        # Only judge a target whose window has closed. An open window is not yet
        # missed -- that is DEFERRED, not FAIL, and conflating them is Class B.
        _, hi = c.window
        if hi > now:
            continue
        if not any(_clears(c, p) for p in performed):
            missed.append(c)
    return missed


def due_now(plan: list[CaptureDue], now: Optional[dt.datetime] = None,
            performed_utc: Optional[list] = None) -> list[CaptureDue]:
    """Targets whose window is open right now and not already discharged.

    This is what an event-anchored runner executes. A periodic poll may still run
    alongside it, but a targeted deadline is only discharged by an execution
    inside its own window.
    """
    now = now or dt.datetime.now(dt.timezone.utc)
    performed = list(performed_utc or [])
    out = []
    for c in plan:
        if c.kind in ('seal', 'unschedulable'):
            continue
        lo, hi = c.window
        if lo <= now <= hi and not any(_clears(c, p) for p in performed):
            out.append(c)
    return out


def next_target(plan: list[CaptureDue], now: Optional[dt.datetime] = None
                ) -> Optional[CaptureDue]:
    """The next target whose window opens. A scheduler wakes for this, rather
    than polling and hoping it lands inside a window."""
    now = now or dt.datetime.now(dt.timezone.utc)
    upcoming = [c for c in plan if c.kind not in ('seal', 'unschedulable')
                and c.window[0] > now]
    return min(upcoming, key=lambda c: c.window[0]) if upcoming else None
