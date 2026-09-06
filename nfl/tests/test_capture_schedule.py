"""Adversarial replay tests for the kickoff-anchored capture cadence. G0A item 1.

Written by an agent that did NOT write nfl/capture/schedule.py.

DEFECTS THIS FILE REPLAYS

  * THE UNIVERSAL ONCE-A-DAY ASSUMPTION. A cadence anchored to a nominal Sunday
    misses every game that is not on Sunday. 2026 week 1 alone has games on Wed
    09-09, Thu 09-10, Sun 09-13 and Mon 09-14. Sections A-D require the plan to
    be anchored to EACH GAME.

  * THE SILENT DEFAULT. `_parse_kick` refuses a game with no gametime rather
    than assuming one, because a defaulted kickoff shifts every derived deadline
    by an unknown amount and nothing downstream can tell. Section F seeds it and
    Section H proves the refusal is load-bearing.

  * SILENT ABSENCE, the dominant defect class in this project: a step that
    produced nothing was read as success. A capture that never happened must
    surface as a debt. Section G seeds a missed capture.

  * THE UNMARKED INFERENCE. Only the Sunday pattern, the 4:00 p.m. filing
    deadline and the ~90-minute inactives lead were externally confirmed. The
    Thursday, Monday and Saturday offsets are DERIVED, and Section E requires
    them to say so in the data rather than in a comment.

FINDINGS, NOT PAPERED OVER (both are in Section F2, and both are written to
FAIL rather than asserted around):

  1. `season_plan(..., through=X)` SILENTLY DROPS the unschedulable entry it
     just created. The entry is parked at `datetime.max` so it sorts last, and
     the `through` filter then removes it. The module's own comment says "a
     debt, not a silent skip"; with a `through` argument it is a silent skip.

  2. `season_plan` reads `g['game_id']` directly, but its handler catches only
     ValueError. A schedule row missing `game_id` therefore raises KeyError and
     takes the WHOLE season plan down with it -- every other game included --
     and the handler's own `g.get('game_id', '<unknown>')` fallback is dead
     code that can never be reached.

Run standalone:  python3.12 nfl/tests/test_capture_schedule.py
"""
import dataclasses
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from nfl.capture import schedule as sched_mod                     # noqa: E402
from nfl.capture.schedule import (INACTIVES_LEAD, CaptureDue,     # noqa: E402
                                  capture_plan, missed_captures,
                                  season_plan)
from nfl.tests.bypass import (assert_guard_is_load_bearing,       # noqa: E402
                              guard_bypassed)

PASSED = FAILED = 0
UTC = dt.timezone.utc


def check(label, cond, detail=''):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')


def by_label(plan):
    return {c.label: c for c in plan}


def iso(plan, label):
    return by_label(plan)[label].due_utc.isoformat()


# --------------------------------------------------------------------------
def test_a_standard_sunday():
    print('\nA. a standard Sunday game -> Wed/Thu/Fri practice + Friday status')
    # 2026-09-13 is a Sunday, 1:00 p.m. New York kickoff (EDT, UTC-4).
    plan = capture_plan('2026_01_AAA_BBB', '2026-09-13', '13:00')
    labels = [c.label for c in plan]
    check('five captures are owed', len(plan) == 5, str(labels))
    check('the three practice/status reports are present and named by weekday',
          [l for l in labels if l.startswith(('practice', 'final'))] ==
          ['practice_wed', 'practice_thu', 'final_status_fri'], str(labels))
    check('the Friday report is typed as the final status, not a practice',
          by_label(plan)['final_status_fri'].kind == 'final_status')
    check('the Wednesday report is typed as a practice',
          by_label(plan)['practice_wed'].kind == 'practice')

    # 4:00 p.m. New York, in EDT, is 20:00 UTC.
    check('Wednesday deadline is 2026-09-09 20:00Z (4pm EDT)',
          iso(plan, 'practice_wed') == '2026-09-09T20:00:00+00:00',
          iso(plan, 'practice_wed'))
    check('Thursday deadline is 2026-09-10 20:00Z',
          iso(plan, 'practice_thu') == '2026-09-10T20:00:00+00:00',
          iso(plan, 'practice_thu'))
    check('Friday status deadline is 2026-09-11 20:00Z',
          iso(plan, 'final_status_fri') == '2026-09-11T20:00:00+00:00',
          iso(plan, 'final_status_fri'))
    check('the three reports land on three consecutive calendar days',
          [iso(plan, l)[:10] for l in
           ('practice_wed', 'practice_thu', 'final_status_fri')] ==
          ['2026-09-09', '2026-09-10', '2026-09-11'])
    check('every due time carries a timezone -- a naive deadline is unusable',
          all(c.due_utc.tzinfo is not None for c in plan))
    check('and every capture is attributed to the game that anchors it',
          all(c.game_id == '2026_01_AAA_BBB' for c in plan))


def test_b_daylight_saving_is_not_assumed_away():
    """4:00 p.m. New York is a LOCAL fact. Its UTC hour is not constant.

    A fixed UTC offset would put every late-season deadline an hour wrong, and
    nothing downstream would notice: the timestamps would still parse, still
    sort, still look plausible.
    """
    print('\nB. 4:00 p.m. New York converts differently in EDT and EST')
    edt = capture_plan('g_sep', '2026-09-13', '13:00')      # September, EDT
    est = capture_plan('g_dec', '2026-12-13', '13:00')      # December, EST
    h_edt = by_label(edt)['final_status_fri'].due_utc.hour
    h_est = by_label(est)['final_status_fri'].due_utc.hour
    check('the September filing deadline is 20:00Z', h_edt == 20, str(h_edt))
    check('the December filing deadline is 21:00Z', h_est == 21, str(h_est))
    check('the two UTC hours actually DIFFER -- the offset was not hard-coded',
          h_edt != h_est, f'{h_edt} == {h_est}')
    check('a 1pm local kickoff is 17:00Z in September',
          by_label(edt)['kickoff_seal'].due_utc.isoformat() ==
          '2026-09-13T17:00:00+00:00')
    check('and 18:00Z in December',
          by_label(est)['kickoff_seal'].due_utc.isoformat() ==
          '2026-12-13T18:00:00+00:00')

    # The hard case: a game whose practice week is in EDT and whose kickoff is
    # in EST. DST ends 2026-11-01. Each deadline must be anchored to ITS OWN
    # local date, not computed as a fixed offset from kickoff.
    cross = capture_plan('g_dst', '2026-11-01', '13:00')
    check('a DST-crossing week keeps the practice deadlines at 20:00Z (EDT)',
          all(by_label(cross)[l].due_utc.isoformat().endswith('T20:00:00+00:00')
              for l in ('practice_wed', 'practice_thu', 'final_status_fri')),
          str([iso(cross, l) for l in
               ('practice_wed', 'practice_thu', 'final_status_fri')]))
    check('while the same week\'s kickoff is 18:00Z (EST)',
          iso(cross, 'kickoff_seal') == '2026-11-01T18:00:00+00:00',
          iso(cross, 'kickoff_seal'))
    gap = (by_label(cross)['kickoff_seal'].due_utc -
           by_label(cross)['final_status_fri'].due_utc)
    check('so the Friday-to-kickoff gap is 46h, not the naive 45h -- the extra '
          'hour of the fall-back is real and is not swallowed',
          gap == dt.timedelta(hours=46), str(gap))


def test_c_non_sunday_games_get_their_own_cadence():
    print('\nC. Thursday compressed, Monday shifted, Saturday and midweek derived')
    thu = capture_plan('g_thu', '2026-09-10', '20:15')      # Thursday night
    check('a Thursday game is compressed onto Mon/Tue/Wed',
          [c.label for c in thu if c.kind in ('practice', 'final_status')] ==
          ['practice_mon', 'practice_tue', 'final_status_wed'],
          str([c.label for c in thu]))
    check('and its final status lands the DAY BEFORE kickoff, not three days '
          'before', iso(thu, 'final_status_wed')[:10] == '2026-09-09',
          iso(thu, 'final_status_wed'))
    check('a Sunday-shaped schedule would have owed nothing before the '
          'Thursday game -- the earliest Sunday-pattern capture is Wednesday',
          iso(thu, 'practice_mon')[:10] == '2026-09-07')

    mon = capture_plan('g_mon', '2026-09-14', '20:15')      # Monday night
    check('a Monday game shifts back to the previous Wed/Thu/Fri',
          [iso(mon, l)[:10] for l in
           ('practice_wed', 'practice_thu', 'final_status_fri')] ==
          ['2026-09-09', '2026-09-10', '2026-09-11'], str(by_label(mon)))
    check('leaving a three-day gap that ONLY the inactives capture closes',
          (by_label(mon)['inactives'].due_utc -
           by_label(mon)['final_status_fri'].due_utc) >= dt.timedelta(days=3))

    sat = capture_plan('g_sat', '2026-12-19', '13:00')      # Saturday
    check('a Saturday game gets a plan at all', len(sat) == 5, str(len(sat)))
    check('and its status lands the day before',
          iso(sat, 'final_status_fri')[:10] == '2026-12-18')

    # 2026 week 1 opens on a WEDNESDAY. No reported cadence exists for it.
    wed = capture_plan('g_wed', '2026-09-09', '20:20')
    check('a midweek game with no reported cadence still yields a plan '
          'rather than nothing', len(wed) == 4, str([c.label for c in wed]))
    check('and the fallback says in the note that it is a fallback',
          'no reported cadence' in by_label(wed)['practice_a'].note,
          by_label(wed)['practice_a'].note[:80])

    # The whole point: four games in one week, four different capture calendars.
    cals = {tuple(c.due_utc.isoformat() for c in p)
            for p in (capture_plan('a', '2026-09-13', '13:00'), thu, mon, wed)}
    check('four games in one week produce four DISTINCT capture calendars -- a '
          'single Sunday-shaped cadence would have produced one',
          len(cals) == 4, str(len(cals)))
    check('and the Thursday game is owed captures before the Sunday game is '
          'owed its first',
          min(c.due_utc for c in thu) <
          min(c.due_utc for c in capture_plan('a', '2026-09-13', '13:00')))


def test_d_inactives_and_ordering():
    print('\nD. inactives are exactly 90 minutes before kickoff, and the plan '
          'is time-ordered')
    check('the declared lead is 90 minutes',
          INACTIVES_LEAD == dt.timedelta(minutes=90), str(INACTIVES_LEAD))
    for gd, gt in (('2026-09-13', '13:00'), ('2026-09-10', '20:15'),
                   ('2026-12-13', '16:25'), ('2026-11-01', '13:00')):
        plan = capture_plan('g', gd, gt)
        d = by_label(plan)
        delta = d['kickoff_seal'].due_utc - d['inactives'].due_utc
        check(f'{gd} {gt}: inactives are exactly 90 min before kickoff',
              delta == dt.timedelta(minutes=90), str(delta))
        check(f'{gd} {gt}: the plan is in ascending time order',
              [c.due_utc for c in plan] == sorted(c.due_utc for c in plan),
              str([c.due_utc.isoformat() for c in plan]))
        check(f'{gd} {gt}: the kickoff seal is last -- nothing after it is '
              'pre-kickoff information',
              plan[-1].kind == 'seal', plan[-1].label)
        check(f'{gd} {gt}: inactives come after every practice/status report',
              d['inactives'].due_utc > max(
                  c.due_utc for c in plan if c.kind in ('practice',
                                                        'final_status')))
    # Seconds in the gametime must not shift the 90 minutes.
    p = capture_plan('g', '2026-09-13', '13:05:00')
    check('a HH:MM:SS gametime is parsed without the seconds moving anything',
          by_label(p)['kickoff_seal'].due_utc.isoformat() ==
          '2026-09-13T17:05:00+00:00',
          by_label(p)['kickoff_seal'].due_utc.isoformat())


def test_e_derived_cadence_is_flagged_as_derived():
    """Only the Sunday pattern and the two fixed times were confirmed.

    An inference presented as a fact is how a placeholder becomes a constant
    nobody can trace. The flag must be IN THE DATA -- a reader consuming
    as_dict() must see it without reading the source.
    """
    print('\nE. confirmed vs DERIVED is carried in the data, not in a comment')
    sun = capture_plan('g', '2026-09-13', '13:00')
    check('the Sunday practice cadence is marked confirmed',
          all(by_label(sun)[l].confirmed for l in
              ('practice_wed', 'practice_thu', 'final_status_fri')))
    check('the inactives lead is marked confirmed',
          by_label(sun)['inactives'].confirmed)
    check('the kickoff seal is marked confirmed',
          by_label(sun)['kickoff_seal'].confirmed)

    for gd, gt, what in (('2026-09-10', '20:15', 'Thursday'),
                         ('2026-09-14', '20:15', 'Monday'),
                         ('2026-12-19', '13:00', 'Saturday'),
                         ('2026-09-09', '20:20', 'midweek')):
        plan = capture_plan('g', gd, gt)
        cadence = [c for c in plan if c.kind in ('practice', 'final_status')]
        check(f'the {what} cadence is flagged confirmed=False',
              all(not c.confirmed for c in cadence),
              str([(c.label, c.confirmed) for c in cadence]))
        check(f'and the {what} note says it was DERIVED',
              all('DERIVED' in c.note for c in cadence),
              cadence[0].note[:80])
        check(f'while the {what} inactives capture stays confirmed -- the two '
              'are not conflated',
              by_label(plan)['inactives'].confirmed)

    check('the flag survives serialisation under an unambiguous key',
          capture_plan('g', '2026-09-10', '20:15')[0].as_dict()
          ['cadence_confirmed'] is False,
          str(capture_plan('g', '2026-09-10', '20:15')[0].as_dict()))
    check('and the note travels with it, so a reader sees WHY',
          'DERIVED' in capture_plan('g', '2026-09-10', '20:15')[0]
          .as_dict()['note'])
    frozen = True
    try:
        capture_plan('g', '2026-09-13', '13:00')[0].confirmed = True
        frozen = False
    except dataclasses.FrozenInstanceError:
        pass
    check('a CaptureDue is frozen -- a flag that can be flipped in place is '
          'not a record', frozen)


def test_f_no_gametime_refuses_rather_than_assuming():
    print('\nF. a game with no gametime refuses; it does not invent a kickoff')
    for bad in (None, '', '   ', '\t'):
        try:
            capture_plan('g', '2026-09-13', bad)
            check(f'gametime {bad!r} refused', False, 'a plan was returned')
        except ValueError as exc:
            check(f'gametime {bad!r} refused', 'no gametime' in str(exc),
                  str(exc)[:80])
    check('and the message names the consequence of assuming one',
          'shift every capture deadline' in _raise_msg('2026-09-13', None),
          _raise_msg('2026-09-13', None)[:100])
    # Contrast: a valid time produces a plan, so the refusal is specific to the
    # absence and not to the code path being broken.
    check('a present gametime still plans normally',
          len(capture_plan('g', '2026-09-13', '13:00')) == 5)


def _raise_msg(gd, gt):
    try:
        capture_plan('g', gd, gt)
    except ValueError as exc:
        return str(exc)
    return ''


def test_f2_season_plan_surfaces_the_unschedulable_game():
    print('\nF2. an unschedulable game is a debt, not a silent skip')
    games = [{'game_id': 'ok_1', 'gameday': '2026-09-13', 'gametime': '13:00'},
             {'game_id': 'broken_1', 'gameday': '2026-09-13', 'gametime': None},
             {'game_id': 'ok_2', 'gameday': '2026-09-10', 'gametime': '20:15'}]
    plan = season_plan(games)
    check('the two schedulable games are planned',
          len({c.game_id for c in plan if c.kind != 'unschedulable'}) == 2,
          str({c.game_id for c in plan}))
    uns = [c for c in plan if c.kind == 'unschedulable']
    check('the unschedulable game appears as an explicit entry',
          len(uns) == 1, str([c.as_dict() for c in plan if c.kind ==
                              'unschedulable']))
    check('named by game_id, so it can be chased',
          uns and uns[0].game_id == 'broken_1', str(uns))
    check('flagged unconfirmed', uns and uns[0].confirmed is False)
    check('and its note says why it could not be scheduled',
          uns and 'no gametime' in uns[0].note.lower(),
          uns[0].note if uns else '')
    # FINDING -- NOT PAPERED OVER.
    # season_plan reads g['game_id'] directly but its handler catches only
    # ValueError, so a schedule row missing game_id raises KeyError and takes
    # the WHOLE season plan down with it -- every other game included. The
    # handler's own `g.get('game_id', '<unknown>')` fallback is therefore dead
    # code: it can never be reached, because the KeyError fires first.
    try:
        salvaged = season_plan([{'game_id': 'ok', 'gameday': '2026-09-13',
                                 'gametime': '13:00'},
                                {'gameday': '2026-09-13', 'gametime': None}])
        crashed = None
    except Exception as exc:                    # noqa: BLE001
        salvaged, crashed = [], exc
    check('BUG: a schedule row missing game_id must surface as one '
          'unschedulable entry, not abort the whole season plan '
          '[nfl/capture/schedule.py:139-149 -- `except ValueError` does not '
          'catch the KeyError from g[\'game_id\']]',
          crashed is None and any(c.kind == 'unschedulable' for c in salvaged),
          f'{type(crashed).__name__}: {crashed}' if crashed else str(salvaged))
    check('(context) and the dead fallback proves the intent was to survive it',
          "'<unknown>'" in __import__('inspect').getsource(season_plan))

    # ---------------------------------------------------------------------
    # FINDING -- NOT PAPERED OVER.
    # `season_plan` parks the unschedulable entry at datetime.max so it sorts
    # last, then filters the plan by `due_utc <= through`. Any caller who passes
    # `through` therefore gets the debt silently removed, which is the exact
    # failure the entry exists to prevent. The module comment says "a debt, not
    # a silent skip"; with a `through` argument it is a silent skip.
    windowed = season_plan(games, through=dt.datetime(2026, 12, 31, tzinfo=UTC))
    check('BUG: season_plan(through=...) must NOT drop the unschedulable entry '
          '[nfl/capture/schedule.py:150-152 -- datetime.max is filtered out by '
          'the `through` window]',
          any(c.kind == 'unschedulable' for c in windowed),
          f'through= dropped it; kinds returned: '
          f'{sorted({c.kind for c in windowed})}')
    check('(context) the `through` window does correctly keep in-window '
          'captures', len([c for c in windowed if c.kind != 'unschedulable']) ==
          len([c for c in plan if c.kind != 'unschedulable']))
    check('(context) and it does correctly exclude out-of-window captures',
          len(season_plan(games,
                          through=dt.datetime(2026, 9, 9, tzinfo=UTC))) < len(plan))


def test_g_missed_captures_surface_as_debt():
    print('\nG. a due capture with no performed capture is reported')
    plan = capture_plan('g_sun', '2026-09-13', '13:00')
    # After all three report WINDOWS have closed, not merely after the
    # deadlines. A window that is still open is DEFERRED, not missed -- and
    # conflating those is the Class B error that aborted V7's first live batch.
    # The Friday filing at 20:00Z stays the current vintage for 20h, so it
    # closes at 16:00Z on the 12th.
    now = dt.datetime(2026, 9, 12, 17, 0, tzinfo=UTC)

    missed = missed_captures(plan, performed_utc=[], now=now)
    check('with nothing performed, all three due reports are reported missing',
          sorted(c.label for c in missed) ==
          ['final_status_fri', 'practice_thu', 'practice_wed'],
          str([c.label for c in missed]))
    check('the not-yet-due inactives capture is NOT reported',
          all(c.label != 'inactives' for c in missed))
    check('and the kickoff seal is never reported as a missed capture',
          all(c.kind != 'seal' for c in missed))

    due = [c.due_utc for c in plan if c.kind in ('practice', 'final_status')]

    def at(offset):
        return [d + offset for d in due]

    check('a capture performed 5 minutes after the deadline satisfies it',
          missed_captures(plan, at(dt.timedelta(minutes=5)), now=now) == [])
    check('a capture performed 5h58m after the deadline is still within the '
          'window -- the filed report stays the current vintage',
          missed_captures(plan, at(dt.timedelta(hours=5, minutes=58)),
                          now=now) == [],
          str([c.label for c in missed_captures(
              plan, at(dt.timedelta(hours=5, minutes=58)), now=now)]))
    # The old symmetric +/-6h tolerance is gone, so 6h02m is no longer the
    # boundary: a practice/final-status window runs 20h because the filed report
    # remains the current vintage until the next filing. The boundary that
    # matters now is the one that CANNOT be crossed -- a capture before the
    # deadline, when the report did not yet exist.
    check('a capture 6h02m after the deadline is still within the 20h window',
          missed_captures(plan, at(dt.timedelta(hours=6, minutes=2)),
                          now=now) == [])
    check('a capture 20h02m after the deadline is outside it',
          len(missed_captures(plan, at(dt.timedelta(hours=20, minutes=2)),
                              now=now)) == 3)
    check('a capture ONE MINUTE BEFORE the deadline discharges nothing -- the '
          'report did not exist yet, which the old symmetric tolerance allowed',
          len(missed_captures(plan, at(dt.timedelta(minutes=-1)),
                              now=now)) == 3)

    # Drop exactly one. The other two must not mask it.
    performed = at(dt.timedelta(minutes=5))
    check('exactly one skipped capture is reported, by name',
          [c.label for c in missed_captures(plan, performed[:1] + performed[2:],
                                            now=now)] == ['practice_thu'],
          str([c.label for c in missed_captures(
              plan, performed[:1] + performed[2:], now=now)]))

    early = dt.datetime(2026, 9, 9, 12, 0, tzinfo=UTC)   # before any deadline
    check('before anything is due, nothing is owed',
          missed_captures(plan, [], now=early) == [])
    check('and a capture performed for a LATER game does not close an earlier '
          'game\'s debt',
          len(missed_captures(plan, [dt.datetime(2026, 9, 13, 15, 0, tzinfo=UTC)],
                              now=now)) == 3)

    # FIXED. This was the defect: the tolerance was SYMMETRIC, so a capture
    # taken five hours BEFORE a 4pm filing deadline discharged the target for a
    # report that did not yet exist. Windows are now one-sided -- each opens at
    # or after the moment the artifact can exist -- so an early capture
    # discharges nothing.
    # Stated precisely, because the imprecise version of this assertion is
    # wrong in an instructive way. Shifting all three captures 5h earlier does
    # NOT leave all three owed: Thursday-minus-5h lands inside WEDNESDAY's 20h
    # window, and discharging Wednesday's target with a capture taken while
    # Wednesday's report was still the current vintage is correct. That is
    # vintage-shaped, not tolerance-shaped.
    #
    # What the fix actually guarantees is narrower and is the thing that
    # matters: a capture never discharges ITS OWN target early, because no
    # window opens before its artifact exists.
    for c in plan:
        if c.kind not in ('practice', 'final_status'):
            continue
        own_early = c.due_utc - dt.timedelta(hours=5)
        check(f'FIXED -- a capture 5h before {c.label} does not discharge '
              f'{c.label} itself',
              not c.satisfied_by(own_early),
              f'{own_early.isoformat()} vs window {c.window[0].isoformat()}')

    early = [p - dt.timedelta(hours=5) for p in performed]
    still_missed = [c.label for c in missed_captures(plan, early, now=now)]
    check('and the last target, with nothing inside its window, stays owed',
          still_missed == ['final_status_fri'], str(still_missed))

    # An unschedulable entry must never be silently counted as satisfied.
    uns = CaptureDue('x', 'unschedulable', dt.datetime.max.replace(tzinfo=UTC),
                     'unschedulable', False, 'n')
    check('an unschedulable entry is not reported as missed (it is never due) '
          'and is not silently marked done either',
          missed_captures([uns], performed, now=now) == [])


def test_h_the_refusal_is_load_bearing():
    """If `_parse_kick` stops refusing, the missing gametime becomes a plan
    built on an invented kickoff, and every deadline in it is wrong by an
    unknown amount with nothing in the output saying so."""
    print('\nH. bypassing the kickoff parser removes the refusal (load-bearing)')

    def run():
        try:
            return capture_plan('g', '2026-09-13', None)
        except ValueError as exc:
            return exc

    try:
        assert_guard_is_load_bearing(
            run=run, module_path='nfl.capture.schedule', attr='_parse_kick',
            caught=lambda r: isinstance(r, ValueError),
            replacement=lambda gameday, gametime:
                dt.datetime(2026, 9, 13, 17, 0, tzinfo=UTC))
        check('the refusal comes from _parse_kick, not from an accident', True)
    except AssertionError as exc:
        check('the refusal comes from _parse_kick, not from an accident',
              False, str(exc)[:200])

    # And show what the bypass actually produces: a complete, plausible,
    # entirely fabricated plan. That is what the refusal is preventing.
    with guard_bypassed('nfl.capture.schedule', '_parse_kick',
                        replacement=lambda gameday, gametime:
                            dt.datetime(2026, 9, 13, 17, 0, tzinfo=UTC)):
        fabricated = capture_plan('g', '2026-09-13', None)
    check('without the guard a full 5-item plan is produced from no gametime '
          'at all, and nothing in it is marked suspect',
          len(fabricated) == 5 and
          by_label(fabricated)['inactives'].confirmed is True,
          str([c.label for c in fabricated]))


if __name__ == '__main__':
    test_a_standard_sunday()
    test_b_daylight_saving_is_not_assumed_away()
    test_c_non_sunday_games_get_their_own_cadence()
    test_d_inactives_and_ordering()
    test_e_derived_cadence_is_flagged_as_derived()
    test_f_no_gametime_refuses_rather_than_assuming()
    test_f2_season_plan_surfaces_the_unschedulable_game()
    test_g_missed_captures_surface_as_debt()
    test_h_the_refusal_is_load_bearing()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
