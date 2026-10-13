#!/usr/bin/env python3.12
"""Production identity paths of the Showdown state, each driven directly (ENG-013, GAME-ID-D1; 2026-10-13).

  GAME   the unplayed game is chosen by ORIENTATION (away@home), not by the club pair: a division rematch whose first
         meeting has not reached the schedules capture must not lend its environment to the second
  REKEY  showdown_portfolio._to_dk_keys re-keys corpus-club draws (Puka Nacua|LA) to the DK club (LAR) and leaves an
         identical-code document untouched (the 2026-10-12 BUF@LAR fix that had no test)
  RESERVE showdown_slate_state.build(roster_blocked=...) makes a reserve / non-elevated player absent BEFORE projection
         (the e0adeb91 fix that had no test), and only him"""
from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import availability as AV  # noqa: E402
from nfl.tools import showdown_portfolio as SP  # noqa: E402
from nfl.tools import showdown_slate_state as SSS  # noqa: E402

PASSED = FAILED = 0


def check(ok, label=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}')
    return bool(ok)


def _row(gid, club, opp, points=None):
    return {'game_id': gid, 'season': 2026, 'week': int(gid.split('_')[1]), 'club': club, 'opponent': opp, 'points': points}


def test_game_is_chosen_by_orientation_not_by_the_club_pair():
    lag = [_row('2026_04_ATL_NO', 'ATL', 'NO'), _row('2026_04_ATL_NO', 'NO', 'ATL'),        # result not yet captured
           _row('2026_17_NO_ATL', 'NO', 'ATL'), _row('2026_17_NO_ATL', 'ATL', 'NO')]
    g = SSS.unplayed_games_for(lag, 2026, 'NO', 'ATL')
    check({r['game_id'] for r in g} == {'2026_17_NO_ATL'},
          f'positive control: the week-17 NO@ATL slate reads week 17 although week 4 is still unplayed in the capture ({[r["game_id"] for r in g]})')
    g = SSS.unplayed_games_for(lag, 2026, 'ATL', 'NO')
    check({r['game_id'] for r in g} == {'2026_04_ATL_NO'}, f'negative control: the ATL@NO slate reads week 4 ({[r["game_id"] for r in g]})')
    played = [_row('2026_04_ATL_NO', 'ATL', 'NO', 24), _row('2026_04_ATL_NO', 'NO', 'ATL', 45)] + lag[2:]
    check(SSS.unplayed_games_for(played, 2026, 'ATL', 'NO') == [],
          'a played ATL@NO is never replaced by the opposite-orientation rematch (empty -> the builder refuses)')
    twice = [_row('2026_04_ATL_NO', 'ATL', 'NO'), _row('2026_09_ATL_NO', 'ATL', 'NO')]
    o = SSS.unplayed_games_for(twice, 2026, 'ATL', 'NO')
    check(getattr(o, 'code', None) == 'SLATE_STATE_GAME_AMBIGUOUS', f'two unplayed games with one orientation refuse ({getattr(o, "code", o)})')


def test_draws_are_rekeyed_to_the_dk_club_and_identical_codes_are_untouched():
    slate = {'players': {'Puka Nacua|LAR': {'name': 'Puka Nacua', 'team': 'LA', 'dk_team': 'LAR'},
                         'Josh Allen|BUF': {'name': 'Josh Allen', 'team': 'BUF', 'dk_team': 'BUF'}}}
    doc = {'draws': {'Puka Nacua|LA': [1.0], 'Josh Allen|BUF': [2.0], 'Ghost Player|LA': [0.0]},
           'club_worlds': {'LA': 'la', 'BUF': 'buf'}, 'home': 'LA', 'away': 'BUF',
           'world_points': {'home': 'LA', 'away': 'BUF'}}
    out = SP._to_dk_keys(doc, slate)
    check(set(out['draws']) == {'Puka Nacua|LAR', 'Josh Allen|BUF', 'Ghost Player|LA'}, f'draws re-keyed {sorted(out["draws"])}')
    check(set(out['club_worlds']) == {'LAR', 'BUF'} and out['home'] == 'LAR' and out['world_points']['home'] == 'LAR',
          'club worlds, home and world_points re-keyed to LAR')
    check(out['_DK_REKEY']['clubs'] == {'LA': 'LAR'} and out['_DK_REKEY']['draw_keys_not_on_dk_slate'] == ['Ghost Player|LA'],
          f'the re-key is recorded, with the draw key that is not on the DK slate ({out["_DK_REKEY"]})')
    same = {'players': {'Josh Allen|BUF': {'name': 'Josh Allen', 'team': 'BUF', 'dk_team': 'BUF'}}}
    d2 = {'draws': {'Josh Allen|BUF': [2.0]}}
    check(SP._to_dk_keys(d2, same) is d2, 'legitimate exception: identical codes return the document unchanged')


def _build(roster_blocked=None):
    R = _REPO / 'nfl/dfs/salaries/raw/showdown_atl_no_2026W4'
    saved = SSS.OUT, SSS.TEAM_GAME
    tmp = pathlib.Path(tempfile.mkdtemp(prefix='sss_identity_'))
    SSS.OUT = tmp / saved[0].name
    SSS.TEAM_GAME = tmp / 'TEAM_GAME.json'                  # the warehouse as it stood before the game (8feac0f3)
    SSS.TEAM_GAME.write_bytes(subprocess.run(['git', 'show', '8feac0f3:nfl/warehouse/TEAM_GAME.json'], cwd=_REPO,
                                             capture_output=True, check=True).stdout)
    try:
        return SSS.build(R / 'DKEntries_ATL_NO_SHOWDOWN_2026W4.fd0c1faa2271ca66.csv', roster_blocked=roster_blocked)
    finally:
        SSS.OUT, SSS.TEAM_GAME = saved


def test_roster_blocked_player_is_absent_before_projection_and_only_him():
    base = _build()
    ok = base.state.value == 'PASS'
    check(ok, f'fixture: the ATL@NO state builds at its own vintage ({base.state.value} {getattr(base, "code", "")})')
    if not ok:
        return
    by = {v['name']: v for v in base.value['players'].values()}
    target = sorted(n for n, v in by.items() if v.get('position', v.get('dk_position')) in ('WR', 'RB', 'TE')
                    and v['current_availability']['status'] != AV.NOT_ON_ACTIVE_ROSTER_CAPTURED)[0]
    blk = _build({target: 'RESERVE'})
    by2 = {v['name']: v for v in blk.value['players'].values()}
    check(by2[target]['current_availability']['status'] == AV.NOT_ON_ACTIVE_ROSTER_CAPTURED,
          f'positive control: {target} blocked -> NOT_ON_ACTIVE_ROSTER_CAPTURED before projection')
    changed = [n for n in by if n != target and by[n]['current_availability']['status'] != by2[n]['current_availability']['status']]
    check(not changed, f'negative control: no other player changes status ({changed[:5]})')
    rec = (blk.value.get('availability_semantics') or {}).get('roster_blocked_before_projection')
    check(rec == {target: 'RESERVE'}, f'the block is recorded in availability_semantics ({rec})')


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')
    check(PASSED > 0, 'the module counted at least one check')


if __name__ == '__main__':
    for n, f in sorted((k, v) for k, v in globals().items() if k.startswith('test_') and callable(v)):
        f()
    print(f'PASSED {PASSED}  FAILED {FAILED}')
