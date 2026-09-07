"""Tests for the event-anchored T-90 workflow and its generator.

THE FAILURE THIS GUARDS AGAINST IS SILENT

A cron block generated from a schedule snapshot is correct on the day it is
written and wrong the moment a kickoff moves. Nothing announces that. It is the
Class C failure -- a declaration drifting away from what it declares -- and its
consequence here is a window that nobody wakes for, in the one part of the
system where the evidence cannot be recovered afterwards.

So section D regenerates the workflow from the current snapshot and fails if the
committed file differs by a byte. The suite, not a missed kickoff, is what
notices.

Section E is the honesty check on the claim being made. The workflow must say
what it does not guarantee, because "event-anchored" is easy to hear as
"guaranteed to run".

Run standalone:  python3.12 nfl/tests/test_t90_workflow.py
"""
import datetime as dt
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.capture.coverage import load_week_plan  # noqa: E402
from nfl.tools.gen_t90_schedule import (ANCHORED_KINDS, STEP_MINUTES,  # noqa: E402
                                        WORKFLOW, cron_entries, render)
from sportsplatform.governance.outcome import State  # noqa: E402

SEASON, WEEK = 2026, 1
PASSED = FAILED = BLOCKED = 0


def check(label, cond, detail=''):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')


def blocked(label, why):
    """A check that could not run. Counted separately and never as a pass.

    PyYAML is not in the standard library, so on a bare runner the parse checks
    below cannot execute. Skipping them silently would make the suite report
    green for work it did not do -- and "the same commit behaves differently on
    another box" is the Class D failure. So it is stated, counted apart, and
    does not colour the run green.
    """
    global BLOCKED
    BLOCKED += 1
    print(f'  BLOCKED {label} -- {why}')


def windows():
    return sorted({c.window for c in load_week_plan(SEASON, WEEK).value
                   if c.kind in ANCHORED_KINDS})


def firings(entry):
    """Every UTC instant a 5-field cron entry nominally fires in 2026."""
    minute, hour, dom, month, _dow = entry.split()
    mins = (list(range(0, 60, STEP_MINUTES)) if minute.startswith('*/')
            else [int(x) for x in minute.split(',')])
    return [dt.datetime(2026, int(month), int(dom), int(hour), m,
                        tzinfo=dt.timezone.utc) for m in mins]


def committed_crons():
    return [ln.split("'")[1] for ln in WORKFLOW.read_text().splitlines()
            if ln.strip().startswith('- cron:')]


# --------------------------------------------------------------------------
def test_A_every_firing_is_inside_a_real_window():
    print('\nA. no cron entry fires outside a window derived from a kickoff')
    wins = windows()
    allf = [t for e in committed_crons() for t in firings(e)]
    outside = [t for t in allf
               if not any(lo <= t <= hi for lo, hi in wins)]
    check(f'{len(allf)} nominal firings, none outside a window',
          not outside, str(outside[:3]))
    check('and there are firings at all -- an empty cron is not coverage',
          len(allf) > 0)
    check('every entry is a valid 5-field cron',
          all(len(e.split()) == 5 for e in committed_crons()))
    check('day-of-week is left open on every entry, so day-of-month decides',
          all(e.split()[4] == '*' for e in committed_crons()))


def test_B_every_window_is_covered_densely():
    print('\nB. every window gets many chances, not one')
    allf = [t for e in committed_crons() for t in firings(e)]
    for lo, hi in windows():
        n = sum(1 for t in allf if lo <= t <= hi)
        width = int((hi - lo).total_seconds() // 60)
        check(f'{lo:%m-%d %H:%M}Z ({width}m): {n} firings',
              n >= width // STEP_MINUTES, f'{n} for a {width}m window')
    check('no window is left with zero entries',
          all(any(lo <= t <= hi for t in allf) for lo, hi in windows()))
    check('the anchored kind is the tight per-game one, not the 20-hour ones',
          ANCHORED_KINDS == ('inactives',), str(ANCHORED_KINDS))


def test_C_the_generator_handles_the_awkward_windows():
    print('\nC. windows crossing midnight and month ends')
    # Real case: 2026-09-09 22:50Z -> 2026-09-10 00:10Z.
    lo = dt.datetime(2026, 9, 9, 22, 50, tzinfo=dt.timezone.utc)
    hi = lo + dt.timedelta(minutes=80)
    e = cron_entries(lo, hi)
    days = {x.split()[2] for x in e}
    check('a window crossing midnight produces entries on both days',
          days == {'9', '10'}, str(e))
    ts = [t for x in e for t in firings(x)]
    check('and every one of them is inside the window',
          all(lo <= t <= hi for t in ts), str([t for t in ts
                                               if not lo <= t <= hi][:2]))

    # Synthetic: a window crossing a month end. Arithmetic on hour boundaries
    # got this wrong; walking the window cannot.
    lo = dt.datetime(2026, 9, 30, 23, 30, tzinfo=dt.timezone.utc)
    hi = lo + dt.timedelta(minutes=80)
    e = cron_entries(lo, hi)
    months = {x.split()[3] for x in e}
    ts = [t for x in e for t in firings(x)]
    check('a window crossing a month end produces entries in both months',
          months == {'9', '10'}, str(e))
    check('and every one of those is inside the window too',
          all(lo <= t <= hi for t in ts))

    # A window shorter than one step still gets an entry.
    lo = dt.datetime(2026, 9, 9, 22, 51, tzinfo=dt.timezone.utc)
    e = cron_entries(lo, lo + dt.timedelta(minutes=4))
    check('a window narrower than the step is not silently dropped',
          len(e) >= 1, str(e))


def test_D_the_committed_file_matches_the_current_schedule():
    """The drift guard. This is the section that earns its keep later."""
    print('\nD. the committed workflow is what the generator produces TODAY')
    check('the workflow file exists', WORKFLOW.exists(), str(WORKFLOW))
    out = render(SEASON, WEEK)
    check('the generator runs against the current snapshot',
          out.state is State.PASS, str(out)[:120])
    same = WORKFLOW.read_text() == out.value
    check('and the committed file is byte-identical to its output -- if this '
          'fails, a kickoff moved and the cron is stale',
          same,
          'regenerate: python3.12 nfl/tools/gen_t90_schedule.py '
          f'--season {SEASON} --week {WEEK} --write')
    check('it names the snapshot it was generated from',
          out.evidence['snapshot'] in WORKFLOW.read_text(),
          out.evidence['snapshot'])
    check('and it marks itself generated so nobody hand-edits it',
          'GENERATED FILE' in WORKFLOW.read_text())


def test_E_it_does_not_overclaim():
    print('\nE. the workflow states what it does NOT guarantee')
    text = WORKFLOW.read_text()
    check('it says GitHub may delay or drop a scheduled run',
          'delay or drop' in text)
    check('it does not promise the firings it schedules',
          'does not promise' in text)
    check('it says discharge is decided on evidence, not on which workflow '
          'fired',
          'never because this' in text)
    check('it shares the baseline concurrency group rather than racing it',
          'group: nfl-vintage-capture' in text)
    check('and it runs the same capture tool, not a variant',
          'nfl/tools/capture_vintage.py' in text)

    try:
        import yaml
    except ImportError:
        blocked('the YAML structural checks',
                'PyYAML is not installed here; the cron entries above were '
                'still checked by parsing the file directly')
        return
    d = yaml.safe_load(text)
    check('the YAML parses -- a malformed block scalar silently disabled a '
          'workflow once already',
          isinstance(d, dict) and 'jobs' in d)
    on = d[True] if True in d else d['on']
    check('it carries both a schedule and workflow_dispatch',
          set(on) == {'schedule', 'workflow_dispatch'}, str(list(on)))
    check('the parsed cron count matches the committed lines',
          len(on['schedule']) == len(committed_crons()))


def test_F_the_generator_refuses_rather_than_emitting_an_empty_cron():
    print('\nF. no schedule, no cron -- never an empty one')
    import nfl.tools.gen_t90_schedule as G
    original = G.VINTAGE
    try:
        G.VINTAGE = _REPO / 'nfl' / 'tests' / '__pycache__' / '_no_such_dir'
        o = render(SEASON, WEEK)
        check('an absent snapshot BLOCKS',
              o.state is State.BLOCKED and o.code == 'NO_SCHEDULE_SNAPSHOT',
              str(o)[:110])
        check('and says that inventing the schedule is the alternative it is '
              'refusing',
              'inventing the schedule' in o.detail, o.detail[:80])
    finally:
        G.VINTAGE = original

    o = render(SEASON, 99)
    check('a week with no games BLOCKS rather than emitting zero entries',
          o.state is State.BLOCKED and o.code == 'NO_GAMES_IN_SNAPSHOT',
          str(o)[:110])
    check('and says an empty cron is not a covered week',
          'not a covered week' in o.detail, o.detail[:80])
    check('the healthy case still renders, so this is not a refusing stub',
          render(SEASON, WEEK).state is State.PASS)


if __name__ == '__main__':
    test_A_every_firing_is_inside_a_real_window()
    test_B_every_window_is_covered_densely()
    test_C_the_generator_handles_the_awkward_windows()
    test_D_the_committed_file_matches_the_current_schedule()
    test_E_it_does_not_overclaim()
    test_F_the_generator_refuses_rather_than_emitting_an_empty_cron()
    tail = f', {BLOCKED} blocked' if BLOCKED else ''
    print(f'\n{PASSED} passed, {FAILED} failed{tail}')
    sys.exit(1 if FAILED else 0)
