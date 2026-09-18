"""CS2 stage 1: it counts, it conserves, it names what it does not have.

The layer this tests is the one whose ABSENCE is the DATA_STATE_DEFECT in
`P2_DIAGNOSTIC.md`: CS1 is a quarterback panel, so current-season receiving
and rushing usage never reached non-QB role allocation. Stage 1 is the data.
Stage 2, which would turn it into a role state, is REFUSED and this module
pins the refusal so a convenient default cannot appear later without someone
deleting a test.
"""
from __future__ import annotations

import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production.nonqb import current_season_nonqb_panel as CS2    # noqa: E402
from sportsplatform.governance.outcome import State                   # noqa: E402

PASSED = 0
FAILED = 0
NOT_EXECUTED = []

SEAL = '2026-09-16T15:45:14Z'
CLUBS = ('ARI', 'ATL', 'BAL', 'BUF', 'CAR', 'CHI', 'CIN', 'CLE', 'DAL', 'DEN',
         'DET', 'GB', 'HOU', 'IND', 'JAX', 'KC', 'LA', 'LAC', 'LV', 'MIA',
         'MIN', 'NE', 'NO', 'NYG', 'NYJ', 'PHI', 'PIT', 'SEA', 'SF', 'TB',
         'TEN', 'WAS')

#: gsis_ids, so nothing here matches on a name.
COOK = '00-0037248'
MOORE = '00-0034827'


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}: {detail}')


def _usage():
    return CS2.usage(2026, 1, as_of=SEAL, all_clubs=CLUBS)


def test_A_it_measures_week_one():
    o = _usage()
    check('A stage 1 measures', o.state is State.PASS,
          f'{o.state}[{o.code}] {o.detail}')
    if o.state is not State.PASS:
        NOT_EXECUTED.append('A-D usage assertions')
        return
    check('A it says it is measurement, not estimation',
          o.evidence['is_measurement_not_estimation'] is True)
    check('A the counting rules travel with the numbers',
          set(o.evidence['counting_rules']) >= {'carries', 'targets',
                                                'receptions'},
          str(sorted(o.evidence['counting_rules'])))


def test_B_the_buffalo_room_reproduces_the_diagnostic():
    o = _usage()
    if o.state is not State.PASS:
        NOT_EXECUTED.append('B buffalo room')
        return
    buf = o.evidence['team_totals']['BUF']
    check('B BUF week-1 carries are 21, exactly as P2 reports',
          buf['carries'] == 21.0, str(buf['carries']))
    check('B BUF week-1 targets are 28, and the one-target gap against P2 is '
          'a reconciled definition, not a disagreement',
          buf['targets'] == 28.0
          and CS2.P2_TARGET_RECONCILIATION['this_module_buf_targets'] == 28
          and CS2.P2_TARGET_RECONCILIATION['p2_diagnostic_buf_targets'] == 29,
          str(buf['targets']))
    cook = o.value[('BUF', COOK)]
    check('B Cook carried 13 with a 0.619 carry share',
          cook['carries'] == 13.0 and abs(cook['carry_share'] - 13/21) < 1e-12,
          str((cook['carries'], cook['carry_share'])))
    moore = o.value[('BUF', MOORE)]
    check('B Moore drew 8 targets, the most on the club',
          moore['targets'] == 8.0
          and moore['targets'] == max(r['targets'] for r in o.value.values()
                                      if r['team'] == 'BUF'),
          str(moore['targets']))
    check('B this is the evidence that never reached role allocation',
          cook['carry_share'] > 0.6, str(cook['carry_share']))


def test_C_shares_conserve_exactly():
    o = _usage()
    if o.state is not State.PASS:
        NOT_EXECUTED.append('C conservation')
        return
    worst = 0.0
    for club in o.evidence['team_totals']:
        for key, tot in (('carry_share', 'carries'),
                         ('target_share', 'targets')):
            if not o.evidence['team_totals'][club][tot]:
                continue
            s = sum(r[key] for r in o.value.values()
                    if r['team'] == club and r[key] is not None)
            worst = max(worst, abs(s - 1.0))
    check('C every club share sums to 1.0 within 1e-9', worst < 1e-9,
          f'worst deviation {worst:.3e}')


def test_D_a_club_with_no_lawful_game_gets_nothing():
    o = _usage()
    if o.state is not State.PASS:
        NOT_EXECUTED.append('D missing clubs')
        return
    absent = o.evidence['clubs_without_usage']
    check('D clubs outside the lawful capture are named, not imputed',
          len(absent) == 12 and 'KC' in absent
          and not any(r['team'] in absent for r in o.value.values()),
          str(absent))
    check('D and the artifact says a fallback must be visible',
          'silent fallback' in o.evidence['clubs_without_usage_get_nothing'])


def test_E_the_clock_is_enforced():
    """A capture taken after the forecast instant is not evidence."""
    early = CS2.usage(2026, 1, as_of='2026-09-12T00:00:00Z')
    late = _usage()
    if late.state is not State.PASS:
        NOT_EXECUTED.append('E clock')
        return
    check('E an earlier as_of drops later captures',
          early.evidence['dropped_by_clock']
          > late.evidence['dropped_by_clock'],
          f'{early.evidence["dropped_by_clock"]} vs '
          f'{late.evidence["dropped_by_clock"]}')
    check('E and sees strictly fewer clubs as a result',
          early.state is not State.PASS
          or early.evidence['n_clubs'] < late.evidence['n_clubs'],
          f'{early.state}[{early.code}]')
    none_yet = CS2.usage(2026, 1, as_of='2026-09-01T00:00:00Z')
    check('E before any capture existed it BLOCKS rather than returning empty',
          none_yet.state is State.BLOCKED, f'{none_yet.state}[{none_yet.code}]')


def test_F_stage_two_is_refused_and_says_what_is_missing():
    o = CS2.stage2_state()
    check('F stage 2 is blocked, not defaulted',
          o.state is State.BLOCKED and o.code == CS2.CODE_INCOMPLETE,
          f'{o.state}[{o.code}]')
    check('F it names all three missing choices',
          set(o.evidence['missing']) == {'half_life', 'min_opportunity',
                                         'shrinkage_target'},
          str(o.evidence['missing']))
    check('F and it does not take stage 1 down with it',
          o.evidence['stage1_is_available'] is True)
    check('F each missing choice carries why it is not neutral',
          all(len(v) > 40 for v in o.evidence['details'].values()))


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for fn in (test_A_it_measures_week_one,
               test_B_the_buffalo_room_reproduces_the_diagnostic,
               test_C_shares_conserve_exactly,
               test_D_a_club_with_no_lawful_game_gets_nothing,
               test_E_the_clock_is_enforced,
               test_F_stage_two_is_refused_and_says_what_is_missing):
        fn()
    for n in NOT_EXECUTED:
        print(f'  NOT_EXECUTED {n}')
    print(f'\n{PASSED} passed, {FAILED} failed, {len(NOT_EXECUTED)} NOT_EXECUTED')
    raise SystemExit(1 if FAILED else 0)
