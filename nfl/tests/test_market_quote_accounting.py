"""Every quote in the frozen snapshot is compared or refused, by name.

THE DEFECT. `market_comparison.rows_for_game` walks BOARD PLAYERS and looks up
each player's quotes. A quote whose player the board does not carry was
therefore never visited at all: it produced no row, no refusal and no count,
and the table quietly described a smaller market than the book had quoted.
Measured 2026-09-13 against the frozen 4:25 Hard Rock snapshot: 166 quotes in,
76 rows and 3 refusals out. Eighty-seven quotes were simply absent from both
outputs, and nothing said so.

WHY IT MATTERS BEYOND TIDINESS. The commonest reason a quote has no board
player on this project is that an upstream layer REFUSED -- `appearance` goes
NOT_APPLICABLE with INJURY_REPORT_INCOMPLETE and the club contributes no
non-quarterback at all. A refusal is a governed fact about what the engine
declined to forecast. Dropping it converts that fact into an absence, which
reads as though the book never quoted the player.

These tests build a real sealed-board directory on disk and call the real
function, because the guarantee is about emitted artifacts, not about what any
module's source says it does.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import tempfile

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from nfl.tools import market_comparison as MCMP                      # noqa: E402

PASSED = FAILED = 0


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')


GID = '2026_01_ZZ_YY'


def _board_dir(tmp, appearance_state='PASS', with_wr=True):
    """A minimal sealed post-inactives board the comparator will accept."""
    d = pathlib.Path(tmp) / f'post_inactives_V1_CANDIDATE_R8' / 'run0'
    d.mkdir(parents=True, exist_ok=True)
    players = [{'gsis_id': 'QB1', 'team': 'ZZ', 'position': 'QB',
                'metrics': {'qb/pyds': {'mean': 200.0}}}]
    if with_wr:
        players.append({'gsis_id': 'WR1', 'team': 'ZZ', 'position': 'WR',
                        'metrics': {'receiving/receiving_yards':
                                    {'mean': 50.0}}})
    board = {
        'game_id': GID, 'teams': ['ZZ', 'YY'], 'run_id': 'run0',
        'n_players': len(players), 'players': players,
        'completeness': 'PARTIAL_PLAYER_COVERAGE',
        'component_manifest': {'applied': []},
        'qb_inactive_ownership_enforced': True,
        'qb_inactive_ownership': {'enforced': True, 'failed_conditions': []},
        'freshness': {'sources': [{'retrieved_at': '2026-09-13T19:00:00Z'}]},
        'layer_governance': [
            {'stage': 'appearance', 'state': appearance_state,
             'code': ('APPEARANCE_OK' if appearance_state == 'PASS'
                      else 'INJURY_REPORT_INCOMPLETE')}],
    }
    (d / 'board.json').write_text(json.dumps(board))
    layers = {'qb': {'row_axis': 'gsis_id', 'row_ids': ['QB1'],
                     'shape': [1, 100]}}
    arrays = {'qb__pyds': np.full((1, 100), 200.0)}
    if with_wr:
        layers['receiving'] = {'row_axis': 'gsis_id', 'row_ids': ['WR1'],
                               'shape': [1, 100]}
        arrays['receiving__receiving_yards'] = np.full((1, 100), 50.0)
    (d / 'player_draws_manifest.json').write_text(
        json.dumps({'game_id': GID, 'layers': layers}))
    np.savez(d / 'player_draws.npz', **arrays)
    return pathlib.Path(tmp) / 'post_inactives_V1_CANDIDATE_R8'


def _quotes(*keys):
    return {k: {'line': 100.5, 'over_price': -110, 'under_price': -110,
                'sportsbook': 'Hard Rock Bet',
                'timestamp': '2026-09-13T18:11:57Z',
                'source_url': 'https://example.invalid', 'opponent': 'YY'}
            for k in keys}


def _run(cfg_dir, quotes, names):
    return MCMP.rows_for_game(GID, cfg_dir, quotes, names)


def test_a_a_quoted_player_absent_from_the_board_is_refused_not_dropped():
    q = _quotes(('Real Passer', 'ZZ', 'Passing Yards'),
                ('Ghost Receiver', 'ZZ', 'Receiving Yards'))
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _board_dir(tmp, with_wr=False)
        rows, refused = _run(cfg, q, {'QB1': 'Real Passer'})
    check('the board player is priced', len(rows) == 1, str(rows))
    check('  and the quoted player the board lacks is REFUSED',
          len(refused) == 1, str(refused))
    check('  by name, so the reader knows which quote it was',
          refused[0].get('player') == 'Ghost Receiver', str(refused[0]))
    check('EVERY quote is accounted for: rows + refusals == quotes',
          len(rows) + len(refused) == len(q))


def test_b_an_upstream_refusal_is_named_as_one():
    """A club with no non-QB because `appearance` refused is not a gap."""
    q = _quotes(('Real Passer', 'ZZ', 'Passing Yards'),
                ('Star Receiver', 'ZZ', 'Receiving Yards'))
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _board_dir(tmp, appearance_state='NOT_APPLICABLE',
                         with_wr=False)
        rows, refused = _run(cfg, q, {'QB1': 'Real Passer'})
    check('the quote is still accounted for',
          len(rows) + len(refused) == len(q))
    check('  and the reason names the layer that refused',
          refused[0]['reason'] == 'APPEARANCE_LAYER_NOT_APPLICABLE',
          str(refused[0]))
    check('  carrying the governed code, not a generic miss',
          'INJURY_REPORT_INCOMPLETE' in refused[0]['detail'],
          refused[0]['detail'])


def test_c_a_genuine_gap_is_not_blamed_on_an_upstream_refusal():
    """When the layers DID run, a missing player is a real coverage gap."""
    q = _quotes(('Real Passer', 'ZZ', 'Passing Yards'),
                ('Star Receiver', 'ZZ', 'Receiving Yards'))
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _board_dir(tmp, appearance_state='PASS', with_wr=True)
        rows, refused = _run(cfg, q, {'QB1': 'Real Passer', 'WR1': 'Other WR'})
    check('accounting still balances', len(rows) + len(refused) == len(q))
    check('  and the missing name is NOT excused as an upstream refusal',
          refused[0]['reason'] == 'QUOTE_PLAYER_NOT_ON_BOARD',
          str(refused[0]))


def test_d_quotes_for_a_club_outside_this_game_are_not_this_games_refusals():
    q = _quotes(('Real Passer', 'ZZ', 'Passing Yards'),
                ('Someone Else', 'QQ', 'Receiving Yards'))
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _board_dir(tmp, with_wr=False)
        rows, refused = _run(cfg, q, {'QB1': 'Real Passer'})
    check('a quote for a club not in this game is left to that game',
          all(r.get('player') != 'Someone Else' for r in refused),
          str(refused))
    check('  and this game accounts for exactly its own clubs',
          len(rows) + len(refused) == 1, f'{len(rows)}+{len(refused)}')


def test_e_an_unenforced_board_refuses_the_whole_game():
    q = _quotes(('Real Passer', 'ZZ', 'Passing Yards'))
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _board_dir(tmp, with_wr=False)
        bd = next(cfg.glob('*/board.json'))
        b = json.loads(bd.read_text())
        b['qb_inactive_ownership_enforced'] = False
        b['qb_inactive_ownership'] = {'failed_conditions': ['no_unresolved_identity']}
        bd.write_text(json.dumps(b))
        rows, refused = _run(cfg, q, {'QB1': 'Real Passer'})
    check('no row is priced off a board that did not enforce',
          rows == [], str(rows))
    check('  and the refusal names the failed condition',
          'no_unresolved_identity' in str(refused), str(refused))


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for fn in sorted(k for k in dict(globals()) if k.startswith('test_')):
        print(f'\n{fn}')
        globals()[fn]()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
