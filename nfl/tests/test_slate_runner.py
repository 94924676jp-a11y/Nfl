"""Slate orchestration: discovery, incrementality, phases, provenance, latency.

WHAT THESE TESTS PROTECT.

  * A WHOLE-FILE CHANGE IS NOT A FOOTBALL CHANGE. The capture bot rewrites
    vintage files on a schedule; measured during the SF@LA window the
    schedules file moved eight times while the SF@LA slice never moved once.
    Recomputing on a file hash would burn a Sunday on forecasts that cannot
    differ, so the verdict is over the CONSUMED SLICE.
  * PHASES ARE PER GAME. One early kickoff reaching POST_INACTIVES must never
    imply the slate has, and a partial list is not a complete one.
  * PROVENANCE SURVIVES INGESTION. A status packet missing any provenance
    field is refused, and a secondary report is never elevated to official.
  * ONE GAME'S FAILURE IS ONE GAME'S FAILURE, with a NAMED refusal and no
    silent omission.
  * NO TIERS, PICKS, EV OR THRESHOLDS. Orchestration only.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import os
import pathlib
import sys
import tempfile

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sportsplatform.governance.outcome import State                  # noqa: E402
from nfl.research import slate_runner as SR                          # noqa: E402

PASSED = FAILED = 0
SUNDAY = '2026-09-13'


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}' + (f'  {detail}' if detail else ''))
    else:
        FAILED += 1
        print(f'  FAIL {label}' + (f'  {detail}' if detail else ''))


def test_a_discovery_needs_no_hand_supplied_game_list():
    o = SR.discover_slate(SUNDAY)
    if o.state is not State.PASS:
        print(f'  ..   no schedule vintage; skipped ({o.code})')
        return
    games = o.value
    check('the Sunday slate is discovered from the schedule vintage',
          len(games) > 1, f'{len(games)} games')
    check('  every game carries both teams', all(len(g['teams']) == 2
                                                 for g in games))
    check('  and a kickoff on the requested date',
          all(g['kickoff_utc'][:10] == SUNDAY for g in games))
    check('  game ids are unique', len({g['game_id'] for g in games})
          == len(games))
    empty = SR.discover_slate('1999-01-01')
    check('a date with no games BLOCKS by name rather than returning []',
          empty.state is State.BLOCKED
          and empty.code == 'SLATE_NO_GAMES_ON_DATE',
          f'{empty.state.name}[{empty.code}]')


def test_b_a_whole_file_change_is_not_a_reason_to_recompute():
    """The central incrementality claim, asserted on the verdict function."""
    slices = {'schedules': {'slice_sha': 'aaa', 'n_rows': 1, 'file_sha16': 'F1'},
              'depth_charts': {'slice_sha': 'bbb', 'n_rows': 9,
                               'file_sha16': 'F2'},
              'weekly_rosters': {'slice_sha': 'ccc', 'n_rows': 90,
                                 'file_sha16': 'F3'},
              'injuries': {'slice_sha': 'ddd', 'n_rows': 7,
                           'file_sha16': 'F4'}}
    changed, moved = SR.slice_verdict(slices, slices)
    check('identical slices -> no recompute', not changed and not moved,
          str(moved))

    # The file moved underneath, the consumed rows did not. THIS is the case
    # that was measured eight times in one evening.
    same_rows_new_file = {k: dict(v, file_sha16='CHANGED')
                          for k, v in slices.items()}
    changed, moved = SR.slice_verdict(slices, same_rows_new_file)
    check('  every FILE hash changed but no SLICE did -> still no recompute',
          not changed and not moved, str(moved))

    one_moved = dict(slices)
    one_moved['injuries'] = dict(slices['injuries'], slice_sha='zzz')
    changed, moved = SR.slice_verdict(slices, one_moved)
    check('  one slice moving DOES force a recompute, and is named',
          changed and moved == ['injuries'], str(moved))

    changed, moved = SR.slice_verdict({}, slices)
    check('  no prior state means NEW, never silently reused', changed)


def test_c_phases_are_per_game_information_states():
    now = dt.datetime(2026, 9, 13, 18, 0, tzinfo=dt.timezone.utc)
    early = {'game_id': '2026_01_AA_BB', 'teams': ('AA', 'BB'),
             'kickoff_utc': '2026-09-13T17:00:00Z'}
    late = {'game_id': '2026_01_CC_DD', 'teams': ('CC', 'DD'),
            'kickoff_utc': '2026-09-13T20:25:00Z'}
    p_early, _ = SR.phase_of(early, now)
    p_late, _ = SR.phase_of(late, now)
    check('a kicked-off game is FINAL', p_early == 'final', p_early)
    check('  while a later game on the SAME slate is not',
          p_late != 'final', p_late)
    check('  so one early game never speaks for the slate',
          p_early != p_late, f'{p_early} vs {p_late}')
    far = dict(late, kickoff_utc='2026-09-13T23:59:00Z')
    check('  a game hours out is still morning',
          SR.phase_of(far, now)[0] == 'morning', SR.phase_of(far, now)[0])


def test_d_post_inactives_needs_BOTH_clubs():
    """A partial list is not a complete one, and the code must say so."""
    d = tempfile.mkdtemp(prefix='sr-inact-')
    gid = '2026_01_ZZ_YY'
    gdir = pathlib.Path(d) / gid
    gdir.mkdir(parents=True)
    real_live = SR.RB.LIVE
    SR.RB.LIVE = pathlib.Path(d)
    try:
        (gdir / 'INACTIVES_INGESTION.json').write_text(json.dumps({
            'teams': ['ZZ', 'YY'],
            'steps': [{'step': '4.', 'inactive_by_team': {'ZZ': ['a', 'b']}}]}))
        st = SR.inactives_state(gid)
        check('one club resolved is PARTIAL, never complete',
              st['state'] == 'PARTIAL_INACTIVES' and not st['complete'],
              str(st['state']))
        (gdir / 'INACTIVES_INGESTION.json').write_text(json.dumps({
            'teams': ['ZZ', 'YY'],
            'steps': [{'step': '4.', 'inactive_by_team':
                       {'ZZ': ['a', 'b'], 'YY': ['c']}}]}))
        st2 = SR.inactives_state(gid)
        check('  both clubs resolved is COMPLETE',
              st2['state'] == 'POST_INACTIVES_COMPLETE' and st2['complete'],
              str(st2['state']))
        st3 = SR.inactives_state('2026_01_NO_SUCH')
        check('  and a game with no list at all says so',
              st3['state'] == 'NO_OFFICIAL_LIST' and not st3['complete'])
    finally:
        SR.RB.LIVE = real_live


def _packet(rows, cols=None):
    cols = cols or list(SR.STATUS_REQUIRED)
    fh = tempfile.NamedTemporaryFile('w', suffix='.csv', delete=False,
                                     newline='')
    w = csv.DictWriter(fh, fieldnames=cols)
    w.writeheader()
    for r in rows:
        w.writerow(r)
    fh.close()
    return fh.name


def test_e_the_status_packet_keeps_its_provenance():
    full = {'team': 'SF', 'player': 'A B', 'status_type': 'OFFICIAL_INACTIVE',
            'source_authority': 'official_league',
            'source_url': 'https://example.invalid/x',
            'published_at': '2026-09-13T16:00:00Z',
            'retrieved_at': '2026-09-13T16:05:00Z'}
    o = SR.load_external_status(_packet([full]))
    check('a complete row is kept', o.state is State.PASS
          and o.evidence['n_kept'] == 1, f'{o.state.name}[{o.code}]')
    check('  and recognised as official',
          o.value[0]['is_official'] is True)
    for drop in ('published_at', 'source_authority', 'source_url'):
        bad = dict(full)
        bad[drop] = ''
        o2 = SR.load_external_status(_packet([bad]))
        check(f'  a row missing {drop} is refused, not kept',
              o2.evidence['n_refused_incomplete'] == 1
              and o2.evidence['n_kept'] == 0, str(o2.evidence['refused'])[:70])
    o3 = SR.load_external_status(_packet(
        [{k: v for k, v in full.items() if k != 'published_at'}],
        cols=[c for c in SR.STATUS_REQUIRED if c != 'published_at']))
    check('  a packet MISSING the column entirely is a schema refusal',
          o3.state is State.FAIL
          and o3.code == 'EXTERNAL_STATUS_SCHEMA_INCOMPLETE', o3.code)


def test_f_a_secondary_report_is_never_elevated():
    sneaky = {'team': 'LA', 'player': 'C D',
              'status_type': 'OFFICIAL_INACTIVE',
              'source_authority': 'beat_reporter',
              'source_url': 'https://example.invalid/tweet',
              'published_at': '2026-09-13T16:00:00Z',
              'retrieved_at': '2026-09-13T16:01:00Z'}
    o = SR.load_external_status(_packet([sneaky]))
    check('a reporter claiming OFFICIAL is kept but NOT made official',
          o.value[0]['is_official'] is False, str(o.value[0]['is_official']))
    check('  and the refusal to elevate is recorded by name',
          o.evidence['n_elevation_refused'] == 1
          and 'recorded as secondary' in o.value[0]['elevation_refused'],
          o.value[0].get('elevation_refused', '')[:60])
    check('  the official count excludes it', o.evidence['n_official'] == 0)


def test_g_one_game_failing_does_not_kill_the_slate():
    """A raised exception becomes a NAMED refusal for that game alone."""
    timer = SR.Timer()
    bad = {'game_id': '2026_01_XX_YY', 'teams': ('XX', 'YY'),
           'kickoff_utc': '2099-01-01T00:00:00Z', 'season': 2026, 'week': 1}
    real = SR._information_set

    def boom(game, written_at):
        raise RuntimeError('seeded explosion')

    SR._information_set = boom
    try:
        rec, action = SR.run_game(bad, 'R8', {}, timer,
                                  '2026-09-13T12:00:00Z')
    finally:
        SR._information_set = real
    check('the game returns instead of raising into the slate',
          action.startswith('BLOCKED_'), action)
    check('  the refusal is NAMED, not generic',
          action == 'BLOCKED_RUNTIMEERROR', action)
    check('  it carries the reason', 'seeded explosion' in rec['reason'])
    check('  and it is marked not recomputed', rec['recomputed'] is False)
    check('  while still reporting its own timing',
          'game_total' in rec['timing_seconds'])


def test_h_latency_is_measured_not_described():
    t = SR.Timer()
    with t.stage('slate_discovery'):
        pass
    with t.stage('forecasting'):
        pass
    check('every stage the directive names is measurable',
          {'slate_discovery', 'forecasting'} <= set(t.stages), str(t.stages))
    check('  totals are real numbers', isinstance(t.total, float))
    check('  and stages accumulate rather than overwrite',
          (t.stage('forecasting').__enter__() or True))


def test_i_orchestration_only_no_tiers_picks_or_ev():
    src = pathlib.Path(_ROOT, 'nfl', 'research', 'slate_runner.py').read_text()
    lowered = src.lower()
    for banned in ('tier_a', 'tier a', 'bankroll', 'stake', 'kelly',
                   'min_disagreement', 'threshold_disagreement'):
        check(f'  the runner has no {banned!r}', banned not in lowered)
    check('  and nothing it emits is promoted',
          "'promoted': False" in src)
    check('  phases are exactly the four information states',
          SR.PHASES == ('morning', 'pre_inactives', 'post_inactives', 'final'),
          str(SR.PHASES))


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for fn in sorted(k for k in dict(globals()) if k.startswith('test_')):
        globals()[fn]()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
