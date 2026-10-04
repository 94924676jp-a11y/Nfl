"""classic_staging / classic_scenarios: every Sunday input sits in a named AWAITING state, and the open
questions are read from the state, never chosen."""
from __future__ import annotations

import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import classic_staging as S     # noqa: E402
from nfl.tools import classic_scenarios as SC  # noqa: E402

PASSED = FAILED = 0


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(ok)


def _p(name, team, desig=None, nh=False, resolution=None, pos='WR'):
    return {'name': name, 'team': team, 'position': pos,
            'current_availability': {'designation': desig, 'resolution': resolution},
            'predicted_lineup_context': {'state': SC.NEXT_HEALTHY} if nh else {}}


STATE = {'official_inactives': {'STATE': 'AWAITING_OFFICIAL_INACTIVES'},
         'players': {'1': _p('Q Open', 'BAL', 'QUESTIONABLE'), '2': _p('Q Cleared', 'BAL', 'QUESTIONABLE', resolution={'claim': 'ACTIVE'}),
                     '3': _p('Chart QB', 'CHI', nh=True, pos='QB'), '4': _p('Healthy', 'BAL'),
                     '5': _p('D Open', 'NE', 'DOUBTFUL')}}
AUDIT = {'contradictions': [{'kind': 'ROSTER_MOVE_SINCE_LAST_CAPTURE'}, {'kind': 'TEAM_MISMATCH'}],
         'stadiums': {'games': {'G1': {'stadium': 'X', 'roof': 'outdoors'}}}}


def test_01_open_questions_come_from_the_state():
    q = [dk for dk, _ in SC.open_questions(STATE)]
    check('positive control: unresolved Q, unresolved D and a chart-only QB are open questions', set(q) == {'1', '3', '5'}, q)
    check('  negative control: a resolved Questionable and a healthy player are not', '2' not in q and '4' not in q)


def test_02_every_sunday_slot_is_named_and_awaiting():
    si = S.sunday_inputs('T', {'STATE': STATE, 'AUDIT': AUDIT})
    sl = si['slots']
    want = {'OFFICIAL_INACTIVES': 'AWAITING_OFFICIAL_INACTIVES', 'QUESTIONABLE_PLAYER_STATUS': 'UNRESOLVED_QUESTIONABLE',
            'WEEK4_ROSTER_REFRESH': 'AWAITING_FRESH_CAPTURE', 'HARD_ROCK_BOARD': 'AWAITING_POST_FINAL_SEAL',
            'WEATHER': 'AWAITING_CURRENT_WEATHER', 'CHI_STARTING_QB': 'ROLE_DEPENDENT_AWAITING_CONFIRMATION'}
    check("every slot carries the owner's placeholder state", {k: sl[k]['state'] for k in want} == want,
          {k: sl.get(k, {}).get('state') for k in want})
    check('  the unresolved list holds only open questions',
          [x['player'] for x in sl['QUESTIONABLE_PLAYER_STATUS']['players']] == ['Q Open', 'D Open'])
    check('  weather is per game and context only', sl['WEATHER']['games']['G1']['weather'] == 'AWAITING_CURRENT_WEATHER'
          and 'CONTEXT_ONLY' in sl['WEATHER']['use'])
    check('  only the roster-move contradictions count toward the roster refresh', sl['WEEK4_ROSTER_REFRESH']['why'].startswith('1 '))
    check('  the five non-substitutes are written down', len(si['NEVER_A_SUBSTITUTE_FOR_OFFICIAL_EVIDENCE']) == 5)
    check('  the packet template asks for the open starter', si['packet_template']['starters'] == {'CHI': '<name>'})
    st2 = {**STATE, 'official_inactives': {'STATE': 'REHEARSAL_NOT_EVIDENCE'}}
    check('negative control: a rehearsal state is shown as itself, never as AWAITING or APPLIED',
          S.sunday_inputs('T', {'STATE': st2, 'AUDIT': AUDIT})['slots']['OFFICIAL_INACTIVES']['state'] == 'REHEARSAL_NOT_EVIDENCE')


def test_zz_every_check_passed():
    """The module's own counter, re-raised so a failure turns this module RED."""
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for n, f in sorted((k, v) for k, v in globals().items() if k.startswith('test_') and callable(v)):
        f()
    print(f'PASSED {PASSED}  FAILED {FAILED}')
