"""Adversarial replay tests for event-anchored capture windows. G0A item 1.

Written by an agent that did NOT write nfl/capture/schedule.py.

THE DEFECT THIS FILE REPLAYS

A single symmetric +/-6h tolerance was shared by every capture target. Under it,
a routine poll taken FIVE HOURS BEFORE a 4:00 p.m. filing deadline discharged
the target for the report filed at that deadline -- a capture taken before the
artifact existed counted as having captured it. Owner Directive 4 section 2:
targeted deadlines must have targeted executions, and an unrelated capture hours
earlier may not discharge them.

The fix is that each target declares its own window (`CaptureDue.window`,
`CaptureDue.satisfied_by`), every window OPENS at or after the moment the
artifact can exist, and `missed_captures` no longer takes a `tolerance` at all.
Section A seeds the original defect against all three intraweek kinds; section
J asserts the removal itself, because a fix that leaves the old lever in place
is one keyword argument away from being undone.

SECOND DEFECT REPLAYED: Class B, an open window reported as a failure. "Not yet"
is DEFERRED and still owed; it is not a miss. Section F requires that an open
window is not reported by `missed_captures`, and section E requires that a
closed one is -- one of those without the other is not a control.

BINDING TEST STANDARD (Owner Directive 3 section 8): "A guard is not demonstrated
merely because compliant data passes it. It must reject a seeded violation, and
critical guards must demonstrate that removing/bypassing the guard causes the
replay test to fail." Section K restores the old symmetric tolerance by bypass
and requires the seeded violation to stop being caught.

Run standalone:  python3.12 nfl/tests/test_capture_windows.py
"""
import datetime as dt
import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from nfl.capture import schedule as sched                          # noqa: E402
from nfl.capture.schedule import (CaptureDue, INACTIVES_LEAD,      # noqa: E402
                                  capture_plan, due_now,
                                  missed_captures, next_target,
                                  season_plan)
from nfl.tests.bypass import (assert_guard_is_load_bearing,        # noqa: E402
                              guard_bypassed)

PASSED = FAILED = 0


def check(label, cond, detail=''):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')


# --------------------------------------------------------------------------
# Fixtures. One standard Sunday game: 2026-09-13, 13:00 New York -> 17:00Z.
# Nothing below hardcodes a deadline; every instant is read off the plan, so a
# cadence change moves the tests with the code instead of silently past it.
GAME = '2026_01_AAA_BBB'
SUNDAY_PLAN = capture_plan(GAME, '2026-09-13', '13:00')
THURSDAY_PLAN = capture_plan('2026_01_CCC_DDD', '2026-09-10', '20:15')

H = dt.timedelta(hours=1)
M = dt.timedelta(minutes=1)


def target(plan, kind=None, label=None):
    for c in plan:
        if (kind is None or c.kind == kind) and (label is None or c.label == label):
            return c
    raise AssertionError(f'no target kind={kind} label={label} in plan')


PRACTICE = target(SUNDAY_PLAN, 'practice')
FINAL = target(SUNDAY_PLAN, 'final_status')
INACTIVES = target(SUNDAY_PLAN, 'inactives')
SEAL = target(SUNDAY_PLAN, 'seal')
KICKOFF = SEAL.due_utc
INTRAWEEK = (PRACTICE, FINAL, INACTIVES)      # one representative per kind
ALL_INTRAWEEK = [c for c in SUNDAY_PLAN
                 if c.kind in ('practice', 'final_status', 'inactives')]


# --------------------------------------------------------------------------
def test_a_a_capture_before_the_window_never_satisfies():
    """THE FIX. A poll taken before the artifact exists discharges nothing."""
    print('\nA. a capture BEFORE the window opens does not satisfy the target')
    for c in INTRAWEEK:
        lo, _ = c.window
        for early in (5 * H, 6 * H, 1 * H, 1 * M, dt.timedelta(seconds=1)):
            check(f'{c.kind}: a capture {early} before the window opens does '
                  f'not discharge it',
                  c.satisfied_by(lo - early) is False,
                  f'window opens {lo.isoformat()}')
    # The literal historical case: a routine poll at 11:00 New York, five hours
    # before the 4:00 p.m. filing deadline, "capturing" a report not yet filed.
    five_early = FINAL.due_utc - 5 * H
    check('the exact defect -- an 11:00 poll does not capture a 16:00 filing',
          FINAL.satisfied_by(five_early) is False,
          f'poll {five_early.isoformat()} vs due {FINAL.due_utc.isoformat()}')
    check('and the window opens at the deadline, never before it',
          FINAL.window[0] == FINAL.due_utc,
          f'{FINAL.window[0].isoformat()} != {FINAL.due_utc.isoformat()}')
    check('the same holds for every intraweek target in the plan',
          all(c.window[0] >= c.due_utc for c in INTRAWEEK))
    # A Thursday game's cascade is anchored to ITS kickoff, not to a Sunday.
    thu_final = target(THURSDAY_PLAN, 'final_status')
    check('a Thursday game files on the Wednesday, and a Friday-shaped poll '
          'would be after its window, not inside it',
          thu_final.due_utc.astimezone(sched.NY).weekday() == 2,
          thu_final.due_utc.isoformat())


def test_b_a_capture_inside_the_window_satisfies():
    """The positive case, including both closed boundaries."""
    print('\nB. a capture INSIDE the window discharges the target')
    for c in INTRAWEEK:
        lo, hi = c.window
        mid = lo + (hi - lo) / 2
        check(f'{c.kind}: a capture at the midpoint discharges it',
              c.satisfied_by(mid) is True, f'[{lo}, {hi}]')
        check(f'{c.kind}: the opening instant counts',
              c.satisfied_by(lo) is True)
        check(f'{c.kind}: the closing instant counts',
              c.satisfied_by(hi) is True)
        check(f'{c.kind}: one second inside the open edge counts',
              c.satisfied_by(lo + dt.timedelta(seconds=1)) is True)
    check('the window is a closed interval on the target itself, so the same '
          'instant judged against a DIFFERENT target does not transfer',
          PRACTICE.satisfied_by(FINAL.window[0] + H) is False,
          'a Friday capture discharged the Wednesday practice target')
    check('and a naive datetime is not quietly accepted as UTC',
          _raises_typeerror(lambda: INACTIVES.satisfied_by(
              dt.datetime(2026, 9, 13, 15, 45))))


def _raises_typeerror(fn):
    try:
        fn()
        return False
    except TypeError:
        return True


def test_c_a_capture_after_the_window_never_satisfies():
    """Stale is as wrong as early -- the vintage has been superseded."""
    print('\nC. a capture AFTER the window closes does not satisfy the target')
    for c in INTRAWEEK:
        _, hi = c.window
        for late in (dt.timedelta(seconds=1), 1 * M, 1 * H, 6 * H):
            check(f'{c.kind}: a capture {late} after the window closes does '
                  f'not discharge it',
                  c.satisfied_by(hi + late) is False,
                  f'window closes {hi.isoformat()}')
    check('a practice window closes before the NEXT filing deadline, so one '
          'capture cannot discharge two days of the cascade',
          PRACTICE.window[1] <= target(SUNDAY_PLAN, label='practice_thu').due_utc,
          f'{PRACTICE.window[1]} > next due')


def test_d_the_t_minus_90_inactives_window_is_tight():
    """The tightest target, and the one a routine poll must never discharge."""
    print('\nD. inactives at T-90: tight, one-sided, and dead at kickoff')
    lo, hi = INACTIVES.window
    width = hi - lo
    check('the target is anchored 90 minutes before kickoff',
          INACTIVES.due_utc == KICKOFF - INACTIVES_LEAD,
          f'{INACTIVES.due_utc} vs {KICKOFF - INACTIVES_LEAD}')
    check('a poll SIX HOURS earlier does not discharge it',
          INACTIVES.satisfied_by(INACTIVES.due_utc - 6 * H) is False,
          f'window opens {lo.isoformat()}')
    check('nor five hours earlier, the original tolerance case',
          INACTIVES.satisfied_by(INACTIVES.due_utc - 5 * H) is False)
    check(f'the window is genuinely tight: width {width} is well under 1h30m',
          width < dt.timedelta(hours=1, minutes=30), str(width))
    check('and it is measurably tighter than the daily-report windows',
          width < (FINAL.window[1] - FINAL.window[0]) / 4,
          f'{width} vs {FINAL.window[1] - FINAL.window[0]}')
    check('the window opens exactly at T-90, not before',
          lo == KICKOFF - INACTIVES_LEAD, lo.isoformat())
    check('and closes strictly before kickoff, because after kickoff the '
          'pre-kickoff information state no longer exists to capture',
          hi < KICKOFF, f'{hi.isoformat()} vs kickoff {KICKOFF.isoformat()}')
    for after in (dt.timedelta(seconds=1), 1 * M, 30 * M, 3 * H):
        check(f'a capture {after} after kickoff never satisfies inactives',
              INACTIVES.satisfied_by(KICKOFF + after) is False)
    check('a capture exactly AT kickoff never satisfies inactives either',
          INACTIVES.satisfied_by(KICKOFF) is False)
    check('inactives is marked confirmed -- it is a reported fact, not a '
          'derived day-offset',
          INACTIVES.confirmed is True)
    check('while the derived Saturday/Thursday/Monday cadences say so',
          target(THURSDAY_PLAN, 'practice').confirmed is False,
          target(THURSDAY_PLAN, 'practice').note[:60])
    d = INACTIVES.as_dict()
    check('the window is serialised for the audit trail, not only computed',
          d['window_start_utc'] == lo.isoformat()
          and d['window_end_utc'] == hi.isoformat(), str(d)[:120])


def test_e_missed_reports_a_closed_window_with_no_capture():
    """A target whose window has closed undischarged is a FAIL, and named."""
    print('\nE. missed_captures reports a CLOSED window with no in-window capture')
    after_everything = KICKOFF + dt.timedelta(days=1)
    missed = missed_captures(SUNDAY_PLAN, [], now=after_everything)
    labels = sorted(c.label for c in missed)
    check('with no captures at all, every intraweek target is missed',
          labels == ['final_status_fri', 'inactives', 'practice_thu',
                     'practice_wed'], str(labels))
    # The seeded defect: the ONLY capture is an early poll before each window.
    # 30 minutes, not 5 hours, and the difference is instructive. A capture five
    # hours before THURSDAY's 4pm deadline falls inside WEDNESDAY's window,
    # because the Wednesday report is still the current vintage until Thursday's
    # filing -- so it legitimately discharges the Wednesday target. The windows
    # are vintage-shaped, not tolerance-shaped, and a seeded violation has to be
    # early for every target rather than merely early for one.
    early_only = [c.window[0] - 30 * M for c in ALL_INTRAWEEK]
    missed_early = missed_captures(SUNDAY_PLAN, early_only,
                                   now=after_everything)
    check('captures taken before every window still leave every target missed',
          sorted(c.label for c in missed_early) == labels, str(missed_early))
    check('specifically, the inactives target is reported missed',
          any(c.kind == 'inactives' for c in missed_early))
    # And the vintage property just described, asserted rather than assumed.
    thu = target(SUNDAY_PLAN, label='practice_thu')
    check('a capture 5h before the Thursday filing DOES discharge the '
          'Wednesday target, because the Wednesday report is still the current '
          'vintage -- windows track vintage, not proximity',
          PRACTICE.satisfied_by(thu.due_utc - 5 * H) is True
          and thu.satisfied_by(thu.due_utc - 5 * H) is False,
          f'practice_wed window {PRACTICE.window}')
    # And a capture inside each window clears them all.
    in_window = [c.window[0] + dt.timedelta(minutes=5)
                 for c in ALL_INTRAWEEK]
    check('one in-window capture per target clears the plan',
          missed_captures(SUNDAY_PLAN, in_window, now=after_everything) == [],
          str(missed_captures(SUNDAY_PLAN, in_window, now=after_everything)))
    # Partial discharge is partial: three of four is not "captured".
    partial = in_window[:2]
    left = sorted(c.label for c in missed_captures(SUNDAY_PLAN, partial,
                                                   now=after_everything))
    check('and discharging some targets does not clear the others',
          left == ['final_status_fri', 'inactives'], str(left))


def test_f_an_open_window_is_not_a_miss():
    """Class B: "not yet" is DEFERRED and still owed. It is not a failure."""
    print('\nF. missed_captures does NOT report a target whose window is OPEN')
    inside = INACTIVES.window[0] + dt.timedelta(minutes=5)
    missed = missed_captures(SUNDAY_PLAN, [], now=inside)
    check('while the inactives window is open it is not reported missed',
          all(c.kind != 'inactives' for c in missed),
          str([c.label for c in missed]))
    check('though the earlier targets, whose windows have closed, ARE reported',
          sorted(c.label for c in missed) == ['final_status_fri',
                                              'practice_thu', 'practice_wed'],
          str(sorted(c.label for c in missed)))
    check('and the same target IS reported once its window closes',
          any(c.kind == 'inactives'
              for c in missed_captures(SUNDAY_PLAN, [],
                                       now=INACTIVES.window[1] + M)))
    before_all = PRACTICE.window[0] - dt.timedelta(days=2)
    check('before anything is due, nothing is missed -- a plan is not a debt',
          missed_captures(SUNDAY_PLAN, [], now=before_all) == [])
    check('a window that closes exactly at `now` is judged, not deferred',
          any(c.kind == 'inactives'
              for c in missed_captures(SUNDAY_PLAN, [],
                                       now=INACTIVES.window[1])))


def test_g_due_now_returns_open_undischarged_targets_only():
    print('\nG. due_now: open, and not already discharged')
    inside = INACTIVES.window[0] + dt.timedelta(minutes=5)
    due = due_now(SUNDAY_PLAN, now=inside)
    check('the open inactives target is due',
          [c.label for c in due] == ['inactives'], str([c.label for c in due]))
    check('an already-discharged target is not due again',
          due_now(SUNDAY_PLAN, now=inside,
                  performed_utc=[INACTIVES.window[0] + M]) == [])
    check('but an EARLY capture does not discharge it, so it stays due',
          [c.label for c in due_now(
              SUNDAY_PLAN, now=inside,
              performed_utc=[INACTIVES.window[0] - 6 * H])] == ['inactives'])
    check('nothing is due before the first window opens',
          due_now(SUNDAY_PLAN, now=PRACTICE.window[0] - M) == [])
    check('nothing is due after the last window closes',
          due_now(SUNDAY_PLAN, now=KICKOFF + dt.timedelta(days=1)) == [])
    check('a closed but undischarged target is NOT due -- it is missed, and '
          'the two lists must not be the same list',
          due_now(SUNDAY_PLAN, now=KICKOFF + H) == []
          and missed_captures(SUNDAY_PLAN, [], now=KICKOFF + H) != [])


def test_h_next_target_is_the_earliest_upcoming_window_open():
    print('\nH. next_target: the instant a scheduler should wake for')
    before_all = PRACTICE.window[0] - dt.timedelta(days=2)
    nxt = next_target(SUNDAY_PLAN, now=before_all)
    check('the first upcoming target is the Wednesday practice report',
          nxt is not None and nxt.label == 'practice_wed', str(nxt))
    check('and it is identified by its window OPENING, not by proximity to now',
          nxt.window[0] == min(c.window[0] for c in SUNDAY_PLAN
                               if c.kind not in ('seal', 'unschedulable')))
    inside_first = PRACTICE.window[0] + M
    check('a target already open is not "next" -- it is due',
          next_target(SUNDAY_PLAN, now=inside_first).label == 'practice_thu',
          str(next_target(SUNDAY_PLAN, now=inside_first)))
    check('across two games the earliest window wins regardless of game',
          next_target(SUNDAY_PLAN + THURSDAY_PLAN, now=before_all).game_id
          == '2026_01_CCC_DDD',
          str(next_target(SUNDAY_PLAN + THURSDAY_PLAN, now=before_all)))
    check('once every intraweek window has opened, there is no next target',
          next_target(SUNDAY_PLAN, now=KICKOFF - 20 * M) is None,
          str(next_target(SUNDAY_PLAN, now=KICKOFF - 20 * M)))


def test_i_seal_and_unschedulable_are_outside_the_capture_logic():
    """The seal is a boundary, not a capture; unschedulable is a debt."""
    print('\nI. seal and unschedulable kinds are excluded from missed/due/next')
    after = KICKOFF + dt.timedelta(days=2)
    check('the seal is never reported as a missed capture',
          all(c.kind != 'seal' for c in missed_captures(SUNDAY_PLAN, [], now=after)))
    check('the seal is never returned as due',
          all(c.kind != 'seal' for c in due_now(SUNDAY_PLAN, now=KICKOFF)))
    check('and never as the next target, even when it is chronologically next',
          next_target(SUNDAY_PLAN, now=KICKOFF - 5 * M) is None)
    rows = [{'game_id': '', 'gameday': '2026-09-13', 'gametime': '13:00'},
            {'game_id': 'G2', 'gameday': '2026-09-13', 'gametime': None},
            {'game_id': 'G3', 'gameday': '2026-09-13', 'gametime': '13:00'}]
    plan = season_plan(rows)
    uns = [c for c in plan if c.kind == 'unschedulable']
    check('a row with no game_id becomes a named debt, not a silent skip',
          any(c.game_id == '<missing>' for c in uns), str([c.game_id for c in uns]))
    check('a row with no gametime becomes a debt too, and names the row',
          any(c.game_id == 'G2' for c in uns), str([c.game_id for c in uns]))
    check('one malformed row costs that row only -- the good game is planned',
          len([c for c in plan if c.game_id == 'G3']) == len(SUNDAY_PLAN),
          str(len([c for c in plan if c.game_id == 'G3'])))
    check('unschedulable debts are never reported as missed captures',
          all(c.kind != 'unschedulable'
              for c in missed_captures(plan, [], now=after)))
    check('nor as due, despite sitting at datetime.max',
          all(c.kind != 'unschedulable' for c in due_now(plan, now=after)))
    filtered = season_plan(rows, through=KICKOFF - dt.timedelta(days=10))
    check('a `through` cutoff does not delete the debts it would have hidden',
          len([c for c in filtered if c.kind == 'unschedulable']) == 2,
          str([c.kind for c in filtered]))


def test_j_the_tolerance_argument_is_gone():
    """The removal IS the fix. A surviving lever is one keyword from undoing it."""
    print('\nJ. missed_captures no longer accepts a `tolerance`')
    sig = inspect.signature(missed_captures)
    check('tolerance is not in the signature',
          'tolerance' not in sig.parameters, str(sig))
    check('the parameters are exactly plan, performed_utc, now',
          list(sig.parameters) == ['plan', 'performed_utc', 'now'], str(sig))
    try:
        missed_captures(SUNDAY_PLAN, [], tolerance=dt.timedelta(hours=6))
        check('passing tolerance= raises rather than being ignored', False,
              'it was accepted silently')
    except TypeError as exc:
        check('passing tolerance= raises rather than being ignored',
              'tolerance' in str(exc), str(exc)[:80])
    for fn in (due_now, next_target):
        check(f'{fn.__name__} has no tolerance parameter either',
              'tolerance' not in inspect.signature(fn).parameters)
    check('and no shared symmetric tolerance survives as a module constant',
          not [n for n in dir(sched) if 'TOLERANC' in n.upper()],
          str([n for n in dir(sched) if 'TOLERANC' in n.upper()]))
    check('every declared window opens at or after its due instant, so no '
          'window is symmetric about it',
          all(lo >= dt.timedelta(0) for lo, _ in sched.WINDOWS.values()),
          str(sched.WINDOWS))


# --------------------------------------------------------------------------
_OLD_SYMMETRIC = {k: (-dt.timedelta(hours=6), dt.timedelta(hours=6))
                  for k in ('practice', 'final_status', 'inactives')}
_OLD_SYMMETRIC.update({'seal': (dt.timedelta(0), dt.timedelta(minutes=1)),
                       'unschedulable': (dt.timedelta(0), dt.timedelta(0))})


def test_k_the_window_declaration_is_load_bearing():
    """Restore the old +/-6h tolerance and the seeded violation walks through."""
    print('\nK. bypassing WINDOWS re-opens the exact defect that was fixed')
    early = INACTIVES.due_utc - 5 * H

    try:
        assert_guard_is_load_bearing(
            run=lambda: INACTIVES.satisfied_by(early),
            module_path='nfl.capture.schedule', attr='WINDOWS',
            caught=lambda r: r is False,
            replacement=_OLD_SYMMETRIC)
        check('the early-poll refusal comes from the per-target window', True)
    except AssertionError as exc:
        check('the early-poll refusal comes from the per-target window',
              False, str(exc)[:200])

    after = KICKOFF + dt.timedelta(days=1)
    try:
        assert_guard_is_load_bearing(
            run=lambda: missed_captures(SUNDAY_PLAN, [early], now=after),
            module_path='nfl.capture.schedule', attr='WINDOWS',
            caught=lambda m: any(c.kind == 'inactives' for c in m),
            replacement=_OLD_SYMMETRIC)
        check('and missed_captures depends on it to report the T-90 target',
              True)
    except AssertionError as exc:
        check('and missed_captures depends on it to report the T-90 target',
              False, str(exc)[:200])

    with guard_bypassed('nfl.capture.schedule', 'WINDOWS',
                        replacement=_OLD_SYMMETRIC):
        leaked = INACTIVES.satisfied_by(early)
        leaked_missed = missed_captures(SUNDAY_PLAN, [early], now=after)
    check('with the old tolerance restored, a poll five hours early "captures" '
          'a list that did not exist -- the defect verbatim',
          leaked is True, str(leaked))
    check('and the missed-capture report goes quiet about it',
          all(c.kind != 'inactives' for c in leaked_missed),
          str([c.label for c in leaked_missed]))
    check('the real WINDOWS table is restored after the bypass',
          INACTIVES.satisfied_by(early) is False)


def test_l_what_the_window_alone_cannot_decide():
    """Recorded, not asserted as a defect: discharge is time-only.

    `satisfied_by` takes an instant and nothing else. It cannot know WHICH
    source performed the capture, so nothing in this module stops an `injuries`
    mirror poll that happens to land inside the inactives window from
    discharging the inactives target. That join belongs to
    `nfl.capture.registry.can_discharge`, which schedule.py never calls. The
    checks below state the coupling so a reader cannot mistake window
    membership for source suitability.
    """
    print('\nL. window membership is not source suitability (recorded gap)')
    sig = inspect.signature(CaptureDue.satisfied_by)
    check('satisfied_by judges an instant only -- no source, no kind argument',
          list(sig.parameters) == ['self', 'performed_utc'], str(sig))
    check('and missed_captures likewise takes bare timestamps',
          missed_captures.__annotations__.get('performed_utc')
          == 'list[dt.datetime]',
          str(missed_captures.__annotations__))
    inside = INACTIVES.window[0] + dt.timedelta(minutes=5)
    check('so ANY capture inside the window discharges the target, whatever '
          'made it -- registry.can_discharge is the control for that, and it '
          'is not consulted here',
          INACTIVES.satisfied_by(inside) is True
          and due_now(SUNDAY_PLAN, now=inside, performed_utc=[inside]) == [])


if __name__ == '__main__':
    test_a_a_capture_before_the_window_never_satisfies()
    test_b_a_capture_inside_the_window_satisfies()
    test_c_a_capture_after_the_window_never_satisfies()
    test_d_the_t_minus_90_inactives_window_is_tight()
    test_e_missed_reports_a_closed_window_with_no_capture()
    test_f_an_open_window_is_not_a_miss()
    test_g_due_now_returns_open_undischarged_targets_only()
    test_h_next_target_is_the_earliest_upcoming_window_open()
    test_i_seal_and_unschedulable_are_outside_the_capture_logic()
    test_j_the_tolerance_argument_is_gone()
    test_k_the_window_declaration_is_load_bearing()
    test_l_what_the_window_alone_cannot_decide()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
