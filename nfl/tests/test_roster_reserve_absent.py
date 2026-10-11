"""Roster membership on the DK-pool state path (owner ruling 2026-10-11, week-5 prelock).

A player whose captured roster status for the slate's week is RES / EXE / CUT is not on the active roster and gets
NOT_ON_ACTIVE_ROSTER_CAPTURED, an absence the allocator honours, so his club volume goes to active teammates. A
club activation recorded in `roster_activation_reported` leaves him as he was. A research-universe state and a
slate that declares no roster capture are unchanged.
"""
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))
from nfl.tools import classic_slate_state as CS, availability as AV  # noqa: E402
from nfl.dfs.salaries import early_only as EO  # noqa: E402

PASSED = FAILED = 0
AS_OF = '2026-10-11T14:30:00Z'


def check(ok, msg):
    global PASSED, FAILED
    PASSED, FAILED = (PASSED + 1, FAILED) if ok else (PASSED, FAILED + 1)
    print('  ok  ' if ok else '  FAIL', msg)


def _row(P, name, team):
    return next(v for v in P.values() if v['name'] == name and v['team'] == team)


def test_01_status_is_an_absence():
    check(AV.NOT_ON_ACTIVE_ROSTER_CAPTURED in AV.ABSENT_STATUSES, 'NOT_ON_ACTIVE_ROSTER_CAPTURED is an absent status')
    check(AV.NOT_ON_ACTIVE_ROSTER_CAPTURED not in AV.PRESENT_STATUSES, 'and never a present one')


def test_02_reserve_players_absent_on_w5_pool():
    files = EO.slate_files('2026W5')
    if not files.get('roster_capture') or not (_REPO / files['roster_capture']).is_file():
        print('BLOCKED[ROSTER_CAPTURE_ABSENT] the W5 roster capture blob is not in this checkout')
        return
    o = CS.build('2026W5', as_of=AS_OF, write=False)
    check(o.state.value == 'PASS', f'W5 state builds: {o.state.value} {o.code}')
    P = o.value['players']
    for nm, tm in (('Josh Oliver', 'MIN'), ('A.J. Brown', 'NE'), ('Jeremy McNichols', 'WAS')):
        a = _row(P, nm, tm)['current_availability']
        check(a['status'] == AV.NOT_ON_ACTIVE_ROSTER_CAPTURED and a['tier'] == AV.TIER_ROSTER_STATUS,
              f'{nm} ({a.get("roster_status_captured")}, corroborated) is NOT_ON_ACTIVE_ROSTER_CAPTURED')
    # a roster snapshot alone never zeroes a player (owner ruling, modified)
    for nm, tm in (('Josh Jacobs', 'GB'), ("De'Von Achane", 'MIA'), ('Travis Etienne Jr.', 'NO')):
        a = _row(P, nm, tm)['current_availability']
        check(a['status'] == AV.UNKNOWN_ACTIVE_STATE and a['roster_status_captured'] in AV.ROSTER_STATUSES_NOT_ACTIVE,
              f'{nm} ({a.get("roster_status_captured")}, uncorroborated) stays UNKNOWN_ACTIVE_STATE')
    n = sum(1 for v in P.values() if v['current_availability']['status'] == AV.NOT_ON_ACTIVE_ROSTER_CAPTURED)
    check(n == 5, f'exactly the 5 corroborated players are absent on roster grounds ({n})')
    for nm, tm in (('Tim Patrick', 'NYJ'), ('Ben Yurosek', 'MIN')):
        a = _row(P, nm, tm)['current_availability']
        check(a['status'] == AV.UNKNOWN_ACTIVE_STATE and a['roster_activation_reported'],
              f'{nm}: reported activation leaves him UNKNOWN_ACTIVE_STATE')
    for nm, tm in (('Justin Jefferson', 'MIN'), ('Tyson Bagent', 'CHI')):
        a = _row(P, nm, tm)['current_availability']
        check(a['status'] == AV.UNKNOWN_ACTIVE_STATE and a['roster_status_captured'] == 'ACT', f'{nm} (ACT) unchanged')
    out = [v for v in P.values() if v['current_availability']['status'] == AV.REPORTED_INACTIVE_OFFICIAL_RELEASE_CITED]
    check(len(out) == 20, f'the 20 official-report absences keep their own status ({len(out)})')


def test_03_legacy_slate_has_no_roster_rule():
    check(not EO.slate_files('2026W4').get('roster_capture'), 'W4 declares no roster capture, so the rule cannot fire')


if __name__ == '__main__':
    for f in (test_01_status_is_an_absence, test_02_reserve_players_absent_on_w5_pool, test_03_legacy_slate_has_no_roster_rule):
        print(f.__name__); f()
    print(f'{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
