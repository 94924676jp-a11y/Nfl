#!/usr/bin/env python3.12
"""Behavioural tests for the owner's injury-completeness ruling of 2026-10-02, written BEFORE the
gate was changed. The four ruled cases, each forced in its own direction, plus the real capture
against the real schedule. The final check asserts the GATE consumes the rule; it is red until it
does, which is the order the owner asked for.
"""
from __future__ import annotations

import datetime as dt
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.prospective.q9shadow import injury_completeness as IC  # noqa: E402
from nfl.tests import _registry  # noqa: E402

RESULTS = []


def check(name):
    def deco(fn):
        RESULTS.append((name, fn))
        return fn
    return deco


# A two-game week 9 whose last kickoff is Sunday 2026-11-01 16:25 ET = 21:25Z.
SCHED = [
    {'season': '2026', 'week': '9', 'gameday': '2026-10-29', 'gametime': '20:15'},
    {'season': '2026', 'week': '9', 'gameday': '2026-11-01', 'gametime': '16:25'},
]
AFTER = '2026-11-02T12:00:00Z'     # capture after every week-9 kickoff
BEFORE = '2026-10-28T12:00:00Z'    # capture before the first week-9 kickoff


@check('practice-only row ACCEPTED: report_status blank + practice_status present is not unfilled')
def _practice_only_accepted():
    rows = [{'season': '2026', 'week': '9', 'report_status': '',
             'practice_status': 'Full Participation in Practice'}]
    assert not IC.row_is_unfilled(rows[0])
    a = IC.assess(rows, AFTER, SCHED, 2026)
    assert a['by_week']['9']['state'] == IC.COMPLETE, a
    assert a['by_week']['9']['n_report_blank_practice_present'] == 1
    return f"week 9 -> {a['by_week']['9']['state']}"


@check('both blank REFUSED: a row saying nothing makes the week incomplete')
def _both_blank_refused():
    rows = [{'season': '2026', 'week': '9', 'report_status': '', 'practice_status': ''},
            {'season': '2026', 'week': '9', 'report_status': 'Out',
             'practice_status': 'Did Not Participate In Practice'}]
    assert IC.row_is_unfilled(rows[0]) and not IC.row_is_unfilled(rows[1])
    a = IC.assess(rows, AFTER, SCHED, 2026)
    assert a['by_week']['9']['state'] == IC.INCOMPLETE_BOTH_BLANK, a
    assert a['by_week']['9']['n_both_blank'] == 1
    return f"week 9 -> {a['by_week']['9']['state']} (1 both-blank row)"


@check('stale pre-designation capture REFUSED even when every row looks filled')
def _stale_capture_refused():
    rows = [{'season': '2026', 'week': '9', 'report_status': 'Questionable',
             'practice_status': 'Limited Participation in Practice'}]
    a = IC.assess(rows, BEFORE, SCHED, 2026)
    assert a['by_week']['9']['state'] == IC.INCOMPLETE_PREDATES, a
    return (f"captured {BEFORE} < final kickoff {a['by_week']['9']['final_kickoff_utc']} "
            f"-> {a['by_week']['9']['state']}")


@check('final-designation capture ACCEPTED: after the last kickoff, designated rows clear')
def _final_capture_accepted():
    rows = [{'season': '2026', 'week': '9', 'report_status': 'Questionable',
             'practice_status': 'Limited Participation in Practice'},
            {'season': '2026', 'week': '9', 'report_status': '',
             'practice_status': 'Full Participation in Practice'}]
    a = IC.assess(rows, AFTER, SCHED, 2026)
    assert a['by_week']['9']['state'] == IC.COMPLETE, a
    assert a['complete_weeks'] == ['9'] and a['incomplete_weeks'] == []
    return 'two ordinary final-report rows -> COMPLETE'


@check('a week with no kickoff in the schedule is INCOMPLETE by name, never assumed final')
def _unknown_kickoff():
    rows = [{'season': '2026', 'week': '17', 'report_status': 'Out', 'practice_status': 'DNP'}]
    a = IC.assess(rows, AFTER, SCHED, 2026)
    assert a['by_week']['17']['state'] == IC.INCOMPLETE_NO_KICKOFF, a
    return a['by_week']['17']['state']


@check('kickoff conversion: Eastern gameday+gametime -> UTC, DST-aware')
def _kickoff_tz():
    k = IC.kickoff_utc({'gameday': '2026-09-24', 'gametime': '20:15'})
    assert k == dt.datetime(2026, 9, 25, 0, 15, tzinfo=dt.timezone.utc), k
    return f'2026-09-24 20:15 ET -> {k.isoformat()}'


@check('REAL CAPTURE vs REAL SCHEDULE: weeks 1-2 COMPLETE, week 3 predates designations')
def _real_vintage():
    from nfl.prospective.q9shadow import live_features as LF
    from nfl.production import world_clock as W
    o = LF.injury_rows(2026, dt.datetime.now(dt.timezone.utc).isoformat())
    assert o.state.name == 'PASS', o
    s = W.schedule(); sched = s.value if hasattr(s, 'value') else s
    a = IC.assess(o.value, o.evidence['retrieved_at'], sched, 2026)
    st = {w: v['state'] for w, v in a['by_week'].items()}
    assert st['1'] == IC.COMPLETE and st['2'] == IC.COMPLETE, st
    assert st['3'] == IC.INCOMPLETE_PREDATES, st
    assert a['by_week']['3']['n_both_blank'] == 0
    return (f"observed {a['observed_at']}; {st}; week-3 final kickoff "
            f"{a['by_week']['3']['final_kickoff_utc']}")


@check('THE GATE CONSUMES THE RULE: _eval_injury_report names the incomplete weeks, not a blank count')
def _gate_uses_rule():
    from nfl.prospective.q9shadow import ledger as LED
    state, detail = LED._eval_injury_report()
    assert state == 'BLOCKED', (state, detail)       # the Sep 24 blob stays blocked (week 3)
    assert 'carry no report_status' not in detail, detail
    assert IC.INCOMPLETE_PREDATES in detail and "'3'" in detail or 'week 3' in detail, detail
    return detail[:160]


_EMITTED = _registry.emit(globals(), RESULTS)


def test_zz_every_check_passed():
    # The tally tripwire, in this module's own source because run_suite recognises it by shape.
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


def main() -> int:
    for fname in _EMITTED:
        try:
            globals()[fname]()
        except Exception:  # noqa: BLE001  -- already printed and counted by the wrapper
            pass
    print(f'\n{PASSED} passed, {FAILED} failed, {len(RESULTS)} checks')
    return 1 if FAILED else 0


if __name__ == '__main__':
    raise SystemExit(main())
