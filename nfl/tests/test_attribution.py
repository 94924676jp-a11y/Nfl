"""Adversarial tests for nfl/capture/attribution.py -- game_id on the capture row.

WHY THIS EXISTS

`schedule._clears` has always required a game-specific target to be cleared by a
capture carrying that target's own game_id, and the capture tool recorded none.
Measured 2026-09-07: 63 week-1 targets, 0 covered, 0 of 60 captures attributed.
The runner could execute perfectly inside a T-90 window and the manifest would
not say which game it was for.

THE CENTRAL PROPERTY, TESTED IN SECTION F

An attribution is a CLAIM written by the capture layer and RE-VERIFIED by the
accounting layer. Section F forges claims -- wrong game, wrong time, wrong
source, a game that does not exist -- and requires that none of them discharges
anything. If a forged claim could discharge a target, this whole mechanism would
be a way to write "covered" into a file, which is the opposite of the point.

Run standalone:  python3.12 nfl/tests/test_attribution.py
"""
import datetime as dt
import json
import pathlib
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.capture import attribution as A  # noqa: E402
from nfl.capture.attribution import (CLAIM_VERSION, claimed_game_ids,  # noqa: E402
                                     claims_for, week_plan_for)
from nfl.capture.coverage import coverage  # noqa: E402
from nfl.capture.schedule import GAME_SPECIFIC_KINDS  # noqa: E402
from sportsplatform.governance.outcome import Outcome, State  # noqa: E402

PASSED = FAILED = 0
PLAN = None


def check(label, cond, detail=''):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')


def _is(o, state, code=None):
    return (isinstance(o, Outcome) and o.state is state
            and (code is None or o.code == code))


def plan():
    global PLAN
    if PLAN is None:
        PLAN = week_plan_for(2026, 1).value
    return PLAN


def target(game_id='2026_01_NE_SEA', kind='inactives'):
    return next(c for c in plan() if c.kind == kind and c.game_id == game_id)


def _manifest(rows):
    fh = tempfile.NamedTemporaryFile('w', suffix='.jsonl', delete=False)
    for r in rows:
        fh.write(json.dumps(r) + '\n')
    fh.close()
    return pathlib.Path(fh.name)


def _row(source, ts, claims_block):
    return {'capture_id': 'x', 'season': 2026, 'source': source,
            'state': 'PASS', 'code': 'CAPTURED',
            'value': {'provenance': {'retrieved_at': ts},
                      'discharge_claims': claims_block}}


def _gids(o):
    return sorted({c['game_id'] for c in o.value['claims']})


# --------------------------------------------------------------------------
def test_A_the_honest_case():
    print('\nA. a capture inside a window, from an authorised source')
    t = target()
    lo, hi = t.window
    ts = (lo + dt.timedelta(minutes=20)).isoformat()
    o = claims_for('official_inactives', ts, plan())
    check('it claims exactly the game whose window is open',
          _is(o, State.PASS, 'DISCHARGE_CLAIMS')
          and _gids(o) == ['2026_01_NE_SEA'], str(o)[:130])
    c = o.value['claims'][0]
    check('the claim names the window it sits in, not just the game',
          c['window_start_utc'] == lo.isoformat()
          and c['window_end_utc'] == hi.isoformat())
    check('and how far into the window the bytes arrived',
          c['seconds_into_window'] == 1200, str(c['seconds_into_window']))
    check('the clock used is declared, and it is retrieved_at',
          o.value['clock'] == 'retrieved_at')
    check('the block declares itself derived, never source-provided',
          o.value['authority'] == 'DERIVED_DETERMINISTIC')
    check('and it says in words that it is a claim awaiting verification',
          'not a verdict' in o.value['verified_by'])
    check('it carries a version so a rule change is visible downstream',
          o.value['claim_version'] == CLAIM_VERSION)

    # Ten games kicking off together share one window; one capture serves all.
    sunday = target('2026_01_CHI_CAR')
    o = claims_for('official_inactives',
                   (sunday.window[0] + dt.timedelta(minutes=5)).isoformat(),
                   plan())
    check('a shared window is claimed for every game in it, not just the first',
          len(_gids(o)) == 8, str(len(_gids(o))))


def test_B_the_window_boundaries_are_exact():
    print('\nB. one second outside is outside')
    t = target()
    lo, hi = t.window
    for label, ts, want in [
        ('one second before it opens', lo - dt.timedelta(seconds=1), False),
        ('exactly at T-90', lo, True),
        ('exactly at T-10', hi, True),
        ('one second after it closes', hi + dt.timedelta(seconds=1), False),
        ('after kickoff', hi + dt.timedelta(hours=2), False),
        ('the day before', lo - dt.timedelta(days=1), False),
    ]:
        o = claims_for('official_inactives', ts.isoformat(), plan())
        got = '2026_01_NE_SEA' in _gids(o)
        check(f'{label} -> {"claimed" if want else "not claimed"}', got == want,
              str(_gids(o))[:80])


def test_C_authority_still_gates_it():
    print('\nC. perfect timing from an unauthorised source claims nothing')
    t = target()
    ts = (t.window[0] + dt.timedelta(minutes=10)).isoformat()
    for src in ('injuries', 'schedules', 'depth_charts', 'weekly_rosters',
                'espn_injuries_json', 'official_injury_report'):
        o = claims_for(src, ts, plan())
        check(f'{src} inside the inactives window claims no inactives target',
              not any(c['kind'] == 'inactives' for c in o.value['claims']),
              str(_gids(o))[:80])
    check('ESPN in particular claims nothing, however easy its JSON is',
          claims_for('espn_injuries_json', ts, plan()).value['claims'] == [])


def test_D_it_fails_closed_rather_than_claiming_nothing_quietly():
    print('\nD. an unreadable clock BLOCKS; it does not read as "no windows"')
    for bad in (None, '', 'yesterday', 'not-a-time', 12345):
        o = claims_for('official_inactives', bad, plan())
        check(f'retrieved_at={bad!r} -> BLOCKED',
              _is(o, State.BLOCKED, 'ATTRIBUTION_CLOCK_UNREADABLE'),
              str(o)[:110])
    check('and the refusal says why guessing would be the defect',
          'invent' in claims_for('official_inactives', None, plan()).detail)

    o = claims_for('official_inactives', '2026-09-09T23:00:00+00:00', [])
    check('an empty plan BLOCKS -- "no targets open" and "not knowing" are '
          'different answers',
          _is(o, State.BLOCKED, 'ATTRIBUTION_NO_PLAN'), str(o)[:110])

    o = claims_for('official_inactives', '2026-01-01T00:00:00+00:00', plan())
    check('a genuinely quiet moment is PASS with an empty list, which is a '
          'result rather than an absence',
          _is(o, State.PASS) and o.value['claims'] == [])

    check('a row written before this module existed claims nothing, rather '
          'than everything',
          claimed_game_ids({'provenance': {}}) == []
          and claimed_game_ids(None) == [])


def test_E_the_claim_actually_discharges():
    print('\nE. an attributed in-window capture covers its target')
    t = target()
    lo, hi = t.window
    ts = (lo + dt.timedelta(minutes=20)).isoformat()
    block = claims_for('official_inactives', ts, plan()).value
    m = _manifest([_row('official_inactives', ts, block)])
    o = coverage(2026, 1, manifest_path=m, now=hi + dt.timedelta(minutes=1))
    check('coverage counts it', o.evidence['covered'] >= 1, str(o)[:120])
    check('and NE@SEA inactives is no longer in the missed list',
          not any(md['kind'] == 'inactives'
                  and md['game_id'] == '2026_01_NE_SEA'
                  for md in o.evidence['missed_detail']),
          str([md['game_id'] for md in o.evidence['missed_detail']])[:120])
    check('the capture is counted as attributed',
          o.evidence['attributed_captures'] >= 1)

    # And without the claim block, the identical capture covers nothing.
    m = _manifest([_row('official_inactives', ts, {'claims': []})])
    o2 = coverage(2026, 1, manifest_path=m, now=hi + dt.timedelta(minutes=1))
    check('the SAME capture with no attribution covers nothing -- so the '
          'attribution is what closed it',
          any(md['kind'] == 'inactives' and md['game_id'] == '2026_01_NE_SEA'
              for md in o2.evidence['missed_detail']), str(o2)[:120])


def test_F_a_forged_claim_discharges_nothing():
    """The property the whole mechanism rests on."""
    print('\nF. FORGED claims -- coverage re-verifies and refuses every one')
    t = target()
    lo, hi = t.window
    now = hi + dt.timedelta(minutes=1)
    inside = (lo + dt.timedelta(minutes=20)).isoformat()
    outside = (lo - dt.timedelta(days=2)).isoformat()

    def still_missed(m):
        o = coverage(2026, 1, manifest_path=m, now=now)
        return any(md['kind'] == 'inactives'
                   and md['game_id'] == '2026_01_NE_SEA'
                   for md in o.evidence['missed_detail'])

    forgeries = [
        ('a claim for the right game at the WRONG time', outside,
         'official_inactives', '2026_01_NE_SEA'),
        ('a claim from an UNAUTHORISED source, perfectly timed', inside,
         'espn_injuries_json', '2026_01_NE_SEA'),
        ('a claim naming a DIFFERENT game', inside,
         'official_inactives', '2026_01_DEN_KC'),
        ('a claim naming a game that does not exist', inside,
         'official_inactives', '2026_01_FAKE_XXX'),
    ]
    for label, ts, src, gid in forgeries:
        block = {'claim_version': CLAIM_VERSION, 'source': src,
                 'clock': 'retrieved_at', 'retrieved_at': ts,
                 'authority': 'DERIVED_DETERMINISTIC', 'verified_by': 'x',
                 'claims': [{'game_id': gid, 'kind': 'inactives',
                             'label': 'inactives',
                             'window_start_utc': lo.isoformat(),
                             'window_end_utc': hi.isoformat(),
                             'due_utc': lo.isoformat(),
                             'cadence_confirmed': True,
                             'seconds_into_window': 0}]}
        check(f'{label} -> NE@SEA still missed',
              still_missed(_manifest([_row(src, ts, block)])))

    # A claim that lies about its own window, while the row's clock is honest.
    block = {'claims': [{'game_id': '2026_01_NE_SEA', 'kind': 'inactives',
                         'label': 'inactives',
                         'window_start_utc': '2020-01-01T00:00:00+00:00',
                         'window_end_utc': '2030-01-01T00:00:00+00:00',
                         'due_utc': '2020-01-01T00:00:00+00:00',
                         'cadence_confirmed': True, 'seconds_into_window': 0}]}
    check('a claim declaring a ten-year window is judged against the PLAN, not '
          'against its own declaration',
          still_missed(_manifest([_row('official_inactives', outside, block)])))

    check('and the honest version of the same row does discharge, so this is '
          'not a function that refuses everything',
          not still_missed(_manifest([_row(
              'official_inactives', inside,
              claims_for('official_inactives', inside, plan()).value)])))


def test_G_team_week_kinds_are_unaffected():
    print('\nG. only game-specific kinds need attribution')
    check('inactives is the game-specific kind', GAME_SPECIFIC_KINDS
          == ('inactives',), str(GAME_SPECIFIC_KINDS))
    p = target(kind='practice')
    ts = (p.window[0] + dt.timedelta(hours=1)).isoformat()
    m = _manifest([_row('official_injury_report', ts,
                        claims_for('official_injury_report', ts, plan()).value)])
    o = coverage(2026, 1, manifest_path=m,
                 now=p.window[1] + dt.timedelta(minutes=1))
    check('a practice report fetch covers its team-week target',
          o.evidence['covered'] >= 1, str(o)[:120])
    check('a practice window is much wider than 80 minutes, which is why it '
          'is not cron-anchored',
          (p.window[1] - p.window[0]) == dt.timedelta(hours=20),
          str(p.window[1] - p.window[0]))


def test_H_the_authority_check_is_load_bearing():
    print('\nH. guard-deletion -- is can_discharge what refuses ESPN?')
    t = target()
    ts = (t.window[0] + dt.timedelta(minutes=10)).isoformat()

    with_guard = claims_for('espn_injuries_json', ts, plan())
    check('with the guard: ESPN claims nothing inside the window',
          with_guard.value['claims'] == [])

    import nfl.capture.registry as R
    original = R.can_discharge
    try:
        R.can_discharge = lambda name, kind: True      # the deleted guard
        loose = claims_for('espn_injuries_json', ts, plan())
    finally:
        R.can_discharge = original

    check('with it bypassed ESPN claims the inactives target -- so the '
          'authority check is what refused it',
          any(c['kind'] == 'inactives' for c in loose.value['claims']),
          str(loose.value['claims'])[:110])
    print(f'       [bypassed: ESPN claims {len(loose.value["claims"])} '
          f'target(s) -- this is the promotion the directive forbids]')
    check('and restoring it restores the refusal',
          claims_for('espn_injuries_json', ts, plan()).value['claims'] == [])


if __name__ == '__main__':
    test_A_the_honest_case()
    test_B_the_window_boundaries_are_exact()
    test_C_authority_still_gates_it()
    test_D_it_fails_closed_rather_than_claiming_nothing_quietly()
    test_E_the_claim_actually_discharges()
    test_F_a_forged_claim_discharges_nothing()
    test_G_team_week_kinds_are_unaffected()
    test_H_the_authority_check_is_load_bearing()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
