"""An absent player must not hold a depth rank over his replacement (found 2026-10-09 by the engine dependency audit).

role_state._position_scoped_ranks re-ranked every player, the OUT ones included, so the healthy replacement of an OUT
starter was numbered 2 at his position and capped at the DEPTH_RANK_2 ceiling (SECONDARY) instead of ALPHA. Measured on
real states: Alvin Kamara (ATL@NO W4) and Braelon Allen, Dontayvion Wicks, Zach Ertz (W4 Early) were all capped.

Covered: every skill position (QB, RB, WR, TE), every absent status, several absences at once in one room and across
rooms and clubs, and the converse -- a DOUBTFUL, QUESTIONABLE or unknown player is NOT absent and keeps his rank
(UNRESOLVED is not INACTIVE).
"""
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))
from nfl.tools import role_state as RS, availability as AV  # noqa: E402

PASSED = FAILED = 0
ACTIVE = AV.UNKNOWN_ACTIVE_STATE


def check(ok, msg):
    global PASSED, FAILED
    PASSED, FAILED = (PASSED + 1, FAILED) if ok else (PASSED, FAILED + 1)
    print('  ok  ' if ok else '  FAIL', msg)


def _p(name, rank, status, pos='RB', team='XXX'):
    return {'name': name, 'team': team, 'position': pos, 'depth_rank': rank, 'observed_2026': {},
            'current_availability': {'status': status}}


def test_absent_starter_does_not_outrank_replacement():
    out = sorted(AV.ABSENT_STATUSES)[0]
    players = {'1': _p('Starter Out', 1, out), '2': _p('Replacement', 2, ACTIVE), '3': _p('Third', 3, ACTIVE)}
    ranks = RS._position_scoped_ranks(players)
    check('1' not in ranks, f'absent player holds no scoped rank ({ranks.get("1")})')
    check(ranks.get('2') == 1 and ranks.get('3') == 2, f'replacement ranks 1, next ranks 2 ({ranks})')
    a, _ = RS.assign(players)
    check(a['2']['askable_ceiling'] == 'ALPHA', f"replacement ceiling ALPHA ({a['2']['askable_ceiling']})")
    check(a['1']['state'] == 'NOT_PLAYING', 'absent starter still NOT_PLAYING')


def test_every_skill_position_and_every_absent_status():
    for pos in ('QB', 'RB', 'WR', 'TE'):
        for st in sorted(AV.ABSENT_STATUSES):
            P = {'s': _p('S', 1, st, pos), 'r': _p('R', 2, ACTIVE, pos), 't': _p('T', 3, ACTIVE, pos)}
            a, _ = RS.assign(P)
            ok = (a['r']['askable_ceiling'] == 'ALPHA' and a['t']['askable_ceiling'] == 'SECONDARY'
                  and a['s']['state'] == 'NOT_PLAYING')
            check(ok, f"{pos} / {st}: replacement ALPHA, next SECONDARY, absent NOT_PLAYING "
                      f"({a['r']['askable_ceiling']}, {a['t']['askable_ceiling']}, {a['s']['state']})")


def test_two_absences_in_one_room():
    out = AV.REPORTED_INACTIVE_OFFICIAL_RELEASE_CITED
    P = {'w1': _p('WR1', 1, out, 'WR'), 'w2': _p('WR2', 2, AV.CONFIRMED_INACTIVE, 'WR'),
         'w3': _p('WR3', 3, ACTIVE, 'WR'), 'w4': _p('WR4', 4, ACTIVE, 'WR'), 'w5': _p('WR5', 5, ACTIVE, 'WR')}
    r = RS._position_scoped_ranks(P)
    check(r == {'w3': 1, 'w4': 2, 'w5': 3}, f'WR1 and WR2 both out: WR3, WR4, WR5 rank 1, 2, 3 ({r})')
    a, _ = RS.assign(P)
    got = [a[k]['askable_ceiling'] for k in ('w3', 'w4', 'w5')]
    check(got == ['ALPHA', 'SECONDARY', 'ROTATIONAL'], f'ceilings move up two places ({got})')


def test_simultaneous_absences_across_rooms_and_clubs_do_not_leak():
    out = AV.REPORTED_OUT_UNVERIFIED
    P = {'aq1': _p('A QB1', 1, out, 'QB', 'AAA'), 'aq2': _p('A QB2', 2, ACTIVE, 'QB', 'AAA'),
         'ar1': _p('A RB1', 1, out, 'RB', 'AAA'), 'ar2': _p('A RB2', 2, ACTIVE, 'RB', 'AAA'),
         'at1': _p('A TE1', 1, out, 'TE', 'AAA'), 'at2': _p('A TE2', 2, ACTIVE, 'TE', 'AAA'),
         'aw1': _p('A WR1', 1, ACTIVE, 'WR', 'AAA'), 'aw2': _p('A WR2', 2, ACTIVE, 'WR', 'AAA'),
         'br1': _p('B RB1', 1, ACTIVE, 'RB', 'BBB'), 'br2': _p('B RB2', 2, ACTIVE, 'RB', 'BBB'),
         'bt1': _p('B TE1', 1, out, 'TE', 'BBB'), 'bt2': _p('B TE2', 2, ACTIVE, 'TE', 'BBB')}
    r = RS._position_scoped_ranks(P)
    want = {'aq2': 1, 'ar2': 1, 'at2': 1, 'aw1': 1, 'aw2': 2, 'br1': 1, 'br2': 2, 'bt2': 1}
    check(r == want, f'QB, RB and TE out together at AAA, TE out at BBB: each room re-ranks alone ({r})')
    a, _ = RS.assign(P)
    check(all(a[k]['askable_ceiling'] == 'ALPHA' for k in ('aq2', 'ar2', 'at2', 'bt2')),
          'every replacement reaches ALPHA')
    check(a['aw2']['askable_ceiling'] == 'SECONDARY' and a['br2']['askable_ceiling'] == 'SECONDARY',
          'rooms with no absence are unchanged (WR2 and B RB2 stay SECONDARY)')


def test_unresolved_is_not_inactive():
    for st in (AV.REPORTED_DOUBTFUL_UNVERIFIED, AV.UNKNOWN_ACTIVE_STATE):
        P = {'s': _p('S', 1, st, 'WR'), 'r': _p('R', 2, ACTIVE, 'WR')}
        r = RS._position_scoped_ranks(P)
        check(r == {'s': 1, 'r': 2}, f'{st} keeps his rank; the backup is not promoted ({r})')


def test_no_absence_is_a_no_op():
    P = {str(i): _p(f'P{i}', rk, ACTIVE, pos, team) for i, (rk, pos, team) in enumerate(
        [(1, 'WR', 'AAA'), (7, 'WR', 'AAA'), (3, 'RB', 'AAA'), (4, 'TE', 'AAA'), (10, 'WR', 'AAA'), (2, 'QB', 'BBB')])}
    r = RS._position_scoped_ranks(P)
    check(r == {'0': 1, '1': 2, '2': 1, '3': 1, '4': 3, '5': 1}, f'club-wide order re-indexed per room, as before ({r})')


def test_real_states_replacements_uncapped():
    for path, name in (('nfl/dfs/salaries/showdown_atl_no/RW_INACTIVES_CHARTFIX/SHOWDOWN_ATL_NO_2026W4_STATE.json', 'Alvin Kamara'),
                       ('nfl/dfs/salaries/DK_2026W4_EARLY_STATE.json', 'Braelon Allen')):
        P = json.loads((_REPO / path).read_text())['players']
        a, _ = RS.assign(P)
        k = next(k for k, v in P.items() if v['name'] == name)
        check(a[k]['askable_ceiling'] == 'ALPHA', f'{name} ceiling ALPHA with the absent starter out of the ranking ({a[k]["askable_ceiling"]})')


if __name__ == '__main__':
    test_absent_starter_does_not_outrank_replacement()
    test_every_skill_position_and_every_absent_status()
    test_two_absences_in_one_room()
    test_simultaneous_absences_across_rooms_and_clubs_do_not_leak()
    test_unresolved_is_not_inactive()
    test_no_absence_is_a_no_op()
    test_real_states_replacements_uncapped()
    print(f'{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
