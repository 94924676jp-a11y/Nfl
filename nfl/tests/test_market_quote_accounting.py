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
        # THE FIXTURE DECLARES ITS ROOM, because a board that does not is now
        # -- correctly -- a BLOCKED board. `qb_metric_blockers` fails closed on
        # an absent `qb3_configuration`, and these synthetic clubs (ZZ, YY) are
        # not in any real week plan, so the season-opener condition can never
        # be established for them. That is the guard working; the fixture was
        # simply under-specified. A mid-season, non-opener room is declared so
        # these accounting tests exercise ACCOUNTING rather than inheriting a
        # QB-governance refusal they were not written to test.
        'qb3_configuration': {
            'ZZ': {'configuration': 'AGREE', 'is_season_opener': False,
                   'week1_specification_defect': False},
            'YY': {'configuration': 'AGREE', 'is_season_opener': False,
                   'week1_specification_defect': False}},
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


def test_e_an_unenforced_board_refuses_every_qb_metric_even_without_r2():
    """REWRITTEN, AND THE REWRITE IS THE POINT.

    This test used to assert `rows == []` -- that an unenforced board refused
    the WHOLE game. That assertion encoded the suppression defect: it was
    satisfied precisely because skill-player markets were being thrown away
    with the QB ones.

    Rewriting a test to match new behaviour is how a guard gets quietly
    weakened, so the replacement is strictly stronger where it matters. It
    pins the hole that removing the early return opened:
    `daily_board._defect_flags` raises QB_INACTIVE_NOT_CONSUMED only when 'R2'
    is in the component manifest, so on a board without R2 an unenforced
    ownership state produced NO flag, and the QB quote would have been priced.
    The ownership verdict now refuses QB metrics on its own authority.
    """
    q = _quotes(('Real Passer', 'ZZ', 'Passing Yards'),
                ('Star Receiver', 'ZZ', 'Receiving Yards'))
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _board_dir(tmp, with_wr=True)
        bd = next(cfg.glob('*/board.json'))
        b = json.loads(bd.read_text())
        b['qb_inactive_ownership_enforced'] = False
        b['qb_inactive_ownership'] = {
            'failed_conditions': ['no_unresolved_identity']}
        b['component_manifest'] = {'applied': []}   # NO R2 -- no flag fires
        bd.write_text(json.dumps(b))
        rows, refused = _run(cfg, q, {'QB1': 'Real Passer',
                                      'WR1': 'Star Receiver'})
    check('accounting balances', len(rows) + len(refused) == len(q))
    check('  NO qb/ row is priced off a board that did not enforce',
          all(not str(r['metric']).startswith('qb/') for r in rows),
          str([r['metric'] for r in rows]))
    check('  even though no component flag fires without R2',
          len(refused) == 1 and refused[0]['reason'] == 'CONTAMINATING_DEFECT',
          str(refused))
    check('    and the ownership state is named as the authority',
          'QB_INACTIVE_OWNERSHIP_NOT_ENFORCED' in refused[0]['detail'],
          refused[0]['detail'])
    check('    carrying the condition that failed',
          'no_unresolved_identity' in refused[0]['detail'],
          refused[0]['detail'])
    check('  and the non-QB market still flows',
          [r['market'] for r in rows] == ['Receiving Yards'],
          str([r['market'] for r in rows]))


def test_f_a_qb_defect_refuses_qb_markets_not_the_whole_game():
    """THE SUPPRESSION DEFECT. One quarterback-room state silenced every skill
    player on the card.

    `rows_for_game` used to return early for the WHOLE game whenever
    `qb_inactive_ownership_enforced` was false, so a running back's carries and
    a receiver's receptions -- quantities the QB allocation never touches --
    were refused because of a defect in the QB room.
    `daily_board._defect_flags` had always scoped the contamination correctly
    (`contaminates_this_metric` is true only for `qb/` metrics); the early
    return simply ignored it.

    Widening what is published deserves an exact statement of what did NOT
    change: no QB row becomes admissible here. The QB quote is still refused.
    It is refused individually, by name, instead of by collateral damage.
    """
    q = _quotes(('Real Passer', 'ZZ', 'Passing Yards'),
                ('Star Receiver', 'ZZ', 'Receiving Yards'))
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _board_dir(tmp, appearance_state='PASS', with_wr=True)
        bd = next(cfg.glob('*/board.json'))
        b = json.loads(bd.read_text())
        b['qb_inactive_ownership_enforced'] = False
        b['qb_inactive_ownership'] = {
            'failed_conditions': ['official_inactive_evidence_ingested']}
        b['component_manifest'] = {'applied': ['R2']}
        bd.write_text(json.dumps(b))
        rows, refused = _run(cfg, q, {'QB1': 'Real Passer',
                                      'WR1': 'Star Receiver'})
    check('accounting still balances', len(rows) + len(refused) == len(q),
          f'{len(rows)}+{len(refused)} vs {len(q)}')
    priced = {r['market'] for r in rows}
    check('  the RECEIVER is priced despite the QB defect',
          'Receiving Yards' in priced, str(priced))
    check('  the QB market is refused', len(refused) == 1, str(refused))
    check('    naming the contaminating defect',
          refused[0]['reason'] == 'CONTAMINATING_DEFECT'
          and 'QB_INACTIVE_NOT_CONSUMED' in refused[0]['detail'],
          str(refused[0]))
    check('    and carrying the condition that failed, not just the flag',
          'official_inactive_evidence_ingested' in refused[0]['detail'],
          refused[0]['detail'])
    check('  no QB row was made admissible',
          all(not str(r['metric']).startswith('qb/') for r in rows),
          str([r['metric'] for r in rows]))


def test_g_a_whole_game_refusal_answers_every_quote_in_that_game():
    """ZERO SILENT LOSS INCLUDES THE GAME-LEVEL REFUSALS.

    A single {'game': gid, 'reason': ...} row is honest about the game and
    silent about the book: 162 quotes for 2026_01_DAL_NYG produced exactly one
    refusal, and the accounting guard correctly called it unbalanced. A reason
    that applies to the whole game applies to each of its quotes.

    THIS TEST WAS REWRITTEN, AND THE REASON MATTERS. It used to trigger the
    refusal with a PRE-INACTIVES board, because a board that was not
    post-inactives was refused wholesale. The two-stage product removed that
    behaviour deliberately: a pre-inactives board is now COMPARED and labelled
    PRE_INACTIVES, because the absence of an official inactive list is a reason
    to be uncertain about availability, not a reason to have no forecast.

    So the old trigger is gone by design. The INVARIANT it protected is not,
    and rewriting a test to match new behaviour is how a guard gets quietly
    weakened -- so the replacement uses triggers that still exist and checks
    MORE of them than the original did: a directory whose stage cannot be
    named, and a sealed board with no stored draws.
    """
    q = _quotes(('Real Passer', 'ZZ', 'Passing Yards'),
                ('Star Receiver', 'ZZ', 'Receiving Yards'),
                ('Someone Else', 'QQ', 'Receptions'))

    # TRIGGER 1: a stage that cannot be named. This refusal is NEW -- it
    # arrived with the same change that removed the old trigger -- and it must
    # answer every quote exactly as the old one had to.
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _board_dir(tmp, with_wr=True)
        odd = cfg.parent / 'sideways_V1_CANDIDATE_R8'
        cfg.rename(odd)
        rows, refused = _run(odd, q, {'QB1': 'Real Passer',
                                      'WR1': 'Star Receiver'})
    check('nothing is priced off a board whose stage cannot be named',
          rows == [], str(rows))
    check("  and BOTH of this game's quotes are refused, not one",
          len(refused) == 2, str(len(refused)))
    check('    each naming the same reason',
          {r['reason'] for r in refused} == {'FORECAST_STAGE_UNKNOWN'},
          str({r['reason'] for r in refused}))
    check('    each naming the player it answers',
          {r.get('player') for r in refused}
          == {'Real Passer', 'Star Receiver'},
          str({r.get('player') for r in refused}))
    check('  a quote for another game is left to that game',
          all(r.get('player') != 'Someone Else' for r in refused))
    check('  and the refusal declares its scope so a reader is not misled',
          all(r.get('scope') == 'WHOLE_GAME' for r in refused))

    # TRIGGER 2: a sealed board with no stored draws. There is no exact CDF to
    # evaluate, so every quote is refused -- and counted.
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _board_dir(tmp, with_wr=True)
        for npz in cfg.glob('*/player_draws.npz'):
            npz.unlink()
        rows, refused = _run(cfg, q, {'QB1': 'Real Passer',
                                      'WR1': 'Star Receiver'})
    check('a board with no stored draws prices nothing', rows == [], str(rows))
    check('  and still answers every quote of this game',
          len(refused) == 2 and {r['reason'] for r in refused}
          == {'NO_STORED_DRAWS'}, str(refused))

    # AND THE BEHAVIOUR THE OLD TRIGGER TESTED IS NOW THE OPPOSITE, ON PURPOSE.
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _board_dir(tmp, with_wr=True)
        pre = cfg.parent / 'pre_inactives_V1_CANDIDATE_R8'
        cfg.rename(pre)
        rows, refused = _run(pre, q, {'QB1': 'Real Passer',
                                      'WR1': 'Star Receiver'})
    check('a PRE-INACTIVES board now PRODUCES a forecast rather than refusing',
          len(rows) >= 1, f'{len(rows)} row(s)')
    check('  labelled as stage 1, never unlabelled',
          all(r['forecast_stage'] == 'PRE_INACTIVES' for r in rows),
          str({r['forecast_stage'] for r in rows}))
    check('  and the accounting still balances',
          len(rows) + len(refused) == 2, f'{len(rows)}+{len(refused)}')


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for fn in sorted(k for k in dict(globals()) if k.startswith('test_')):
        print(f'\n{fn}')
        globals()[fn]()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
