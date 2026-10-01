#!/usr/bin/env python3.12
"""A fresh file containing stale football reality must not read FRESH, and that must be provable.

The readiness board measures age from mtime for every stage -- its own output says so -- and mtime is
when a file was written, not what it knows. On 2026-10-01 that let `warehouse.team_game` read FRESH
while the evidence stopped a full completed week behind the football world.

So the checks here are not only "does the gate agree with today's reality". Each direction is forced:
the gate must PASS when the evidence does reach the world, FAIL when it does not, and the leakage
guard must FAIL on a seeded future score rather than only passing on data that happens to be clean.
"""
from __future__ import annotations

import copy
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production import world_clock as W  # noqa: E402
from sportsplatform.governance.outcome import State  # noqa: E402

from nfl.tests import _registry  # noqa: E402

RESULTS = []


def check(name):
    def deco(fn):
        RESULTS.append((name, fn))
        return fn
    return deco


def _sched():
    o = W.schedule()
    assert o.state is State.PASS, o
    return o.value


@check('the schedule carries a calendar day and a kickoff for every game of the season')
def t_schedule():
    rows = _sched()
    assert len(rows) > 250, f'only {len(rows)} regular-season games'
    assert all(r.get('gameday') for r in rows), 'a game has no gameday'
    assert all(r.get('gametime') for r in rows), 'a game has no gametime'
    return f'{len(rows)} games, every one dated and timed'


@check('the world frontier is the last game day strictly BEFORE the as-of day')
def t_world_frontier():
    rows = _sched()
    o = W.latest_completed_in_world(rows, as_of='2026-09-29')
    assert o.state is State.PASS, o
    assert o.value['latest_completed_gameday'] == '2026-09-28', o.value
    assert o.value['latest_completed_week'] == 3, o.value
    return (f"through {o.value['latest_completed_gameday']}, week "
            f"{o.value['latest_completed_week']}, {o.value['n_completed_games']} games")


@check("a game on the as-of day is NOT counted complete, so tonight's game is not assumed played")
def t_in_progress_not_counted():
    rows = _sched()
    # 2026-10-01 carries exactly one game, PIT at CLE at 20:15.
    today = [r for r in rows if r['gameday'] == '2026-10-01']
    assert len(today) == 1, [r['game_id'] for r in today]
    o = W.latest_completed_in_world(rows, as_of='2026-10-01')
    assert o.state is State.PASS, o
    assert o.value['latest_completed_gameday'] < '2026-10-01', o.value
    assert today[0]['game_id'] not in str(o.value), 'the in-progress game leaked into the frontier'
    return (f"{today[0]['game_id']} at {today[0]['gametime']} is excluded; frontier stays at "
            f"{o.value['latest_completed_gameday']}")


@check('the evidence frontier is read from scores actually held, not from a file timestamp')
def t_evidence_frontier():
    rows = _sched()
    o = W.latest_completed_in_evidence(rows)
    assert o.state is State.PASS, o
    assert o.value['latest_scored_gameday'] == '2026-09-21', o.value
    assert o.value['latest_scored_week'] == 2, o.value
    return (f"through {o.value['latest_scored_gameday']}, week {o.value['latest_scored_week']}, "
            f"{o.value['n_scored_club_games']} club-games")


@check('LOAD-BEARING: the gate FAILS today, naming the missing week and game count')
def t_gate_fails_now():
    o = W.semantic_freshness(as_of='2026-10-01')
    assert o.state is State.FAIL, o
    assert o.code == 'EVIDENCE_BEHIND_THE_WORLD', o.code
    ev = o.evidence
    assert ev['missing_weeks'] == [3], ev['missing_weeks']
    assert ev['n_missing_games'] == 16, ev['n_missing_games']
    assert ev['latest_completed_week_in_world'] == 3
    assert ev['latest_completed_week_in_evidence'] == 2
    return f"{o.code}: weeks {ev['missing_weeks']}, {ev['n_missing_games']} games absent"


@check('LOAD-BEARING: the gate PASSES when the evidence does reach the world')
def t_gate_passes_when_caught_up():
    # As of 2026-09-22 the world is through 09-21, which is exactly where the evidence stops. The gate
    # must distinguish "behind" from "level"; a gate that always failed would be useless.
    o = W.semantic_freshness(as_of='2026-09-22')
    assert o.state is State.PASS, o
    assert o.code == 'EVIDENCE_REACHES_THE_WORLD', o.code
    assert o.evidence['latest_completed_week_in_world'] == 2
    return f"{o.code} at a cutoff where world and evidence are both week 2"


@check('the gate is a FAIL, not a DEFERRED: a missing played week is not an errand to proceed around')
def t_gate_is_a_fail_not_a_deferral():
    o = W.semantic_freshness(as_of='2026-10-01')
    assert o.state is State.FAIL, f'state is {o.state}, which would let the pipeline continue'
    return 'FAIL, so a product mode cannot read READY through it'


@check('the leakage guard passes on the real tree, having examined a non-zero number of games')
def t_leakage_clean_now():
    o = W.assert_no_post_cutoff_outcomes('2026-10-01')
    assert o.state is State.PASS, o
    assert o.code == 'NO_POST_CUTOFF_OUTCOME', o.code
    assert o.evidence['n_future_games_examined'] > 100, o.evidence
    return (f"{o.evidence['n_future_games_examined']} future games, "
            f"{len(W.SCHEDULE_OUTCOME_FIELDS) + len(W.TEAM_GAME_OUTCOME_FIELDS)} fields, clean")


@check('LOAD-BEARING: a seeded future SCORE in the schedule is caught')
def t_leakage_schedule_seeded():
    rows = copy.deepcopy(_sched())
    target = next(r for r in rows if r['gameday'] > '2026-10-01')
    target['home_score'] = '31'
    o = W.assert_no_post_cutoff_outcomes('2026-10-01', rows=rows, team_game_rows=[])
    assert o.state is State.FAIL, o
    assert o.code == 'POST_CUTOFF_OUTCOME_PRESENT', o.code
    assert o.evidence['by_field'].get('home_score') == 1, o.evidence['by_field']
    return f"caught {target['game_id']} home_score=31 after the cutoff"


@check('LOAD-BEARING: a seeded future STAT in TEAM_GAME is caught')
def t_leakage_team_game_seeded():
    rows = _sched()
    fut = next(r for r in rows if r['gameday'] > '2026-10-01')
    seeded = [{'game_id': fut['game_id'], 'club': fut['home_team'], 'points': 24}]
    o = W.assert_no_post_cutoff_outcomes('2026-10-01', rows=rows, team_game_rows=seeded)
    assert o.state is State.FAIL, o
    assert o.code == 'POST_CUTOFF_OUTCOME_PRESENT', o.code
    assert o.evidence['by_field'].get('points') == 1, o.evidence['by_field']
    return f"caught points=24 on {fut['game_id']}"


@check('the PENDING sentinel is treated as absent, and a real zero is NOT')
def t_pending_vs_zero():
    rows = _sched()
    fut = next(r for r in rows if r['gameday'] > '2026-10-01')
    pend = [{'game_id': fut['game_id'], 'club': fut['home_team'], 'points': W.PENDING}]
    o = W.assert_no_post_cutoff_outcomes('2026-10-01', rows=rows, team_game_rows=pend)
    assert o.state is State.PASS, o
    # A shutout is a real outcome and must still be caught. This is the half of the distinction that
    # a falsiness check would get wrong.
    zero = [{'game_id': fut['game_id'], 'club': fut['home_team'], 'points': 0}]
    o2 = W.assert_no_post_cutoff_outcomes('2026-10-01', rows=rows, team_game_rows=zero)
    assert o2.state is State.FAIL, o2
    assert o2.evidence['by_field'].get('points') == 1, o2.evidence
    return 'PENDING passes, points=0 is caught as the real outcome it is'


@check('LOAD-BEARING: a leakage check that examined nothing refuses rather than passing')
def t_leakage_vacuous_refused():
    rows = _sched()
    o = W.assert_no_post_cutoff_outcomes('2099-01-01', rows=rows, team_game_rows=[])
    assert o.state is State.BLOCKED, o
    assert o.code == 'LEAKAGE_CHECK_VACUOUS', o.code
    return f'{o.code} rather than a green tick over zero rows'


@check('the outcome field lists are explicit, and points leads the TEAM_GAME list')
def t_fields_named_explicitly():
    assert 'home_score' in W.SCHEDULE_OUTCOME_FIELDS and 'away_score' in W.SCHEDULE_OUTCOME_FIELDS
    assert W.TEAM_GAME_OUTCOME_FIELDS[0] == 'points', W.TEAM_GAME_OUTCOME_FIELDS[0]
    assert len(W.TEAM_GAME_OUTCOME_FIELDS) >= 10, len(W.TEAM_GAME_OUTCOME_FIELDS)
    return (f'{len(W.SCHEDULE_OUTCOME_FIELDS)} schedule and '
            f'{len(W.TEAM_GAME_OUTCOME_FIELDS)} TEAM_GAME fields named, not inferred')


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
    test_zz_every_check_passed.__doc__
    print(f'\n{PASSED} passed, {FAILED} failed, {len(RESULTS)} checks')
    return 1 if FAILED else 0


if __name__ == '__main__':
    raise SystemExit(main())
