"""classic_research_book: measured roles, game stories and distributions -- and the gate before lineups."""
from __future__ import annotations

import csv
import gzip
import json
import pathlib
import sys
import tempfile

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import classic_research_book as B   # noqa: E402
from nfl.opt import classic_portfolio as P          # noqa: E402
from nfl.tests._controls import observe             # noqa: E402

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


COLS = ['game_id', 'season_type', 'week', 'posteam', 'defteam', 'yardline_100', 'down', 'ydstogo', 'yards_gained',
        'pass_attempt', 'rush_attempt', 'sack', 'qb_scramble', 'qb_kneel', 'qb_spike', 'two_point_attempt',
        'air_yards', 'complete_pass', 'passing_yards', 'receiving_yards', 'rushing_yards', 'pass_touchdown',
        'rush_touchdown', 'touchdown', 'interception', 'passer_player_id', 'receiver_player_id', 'rusher_player_id']


def _play(**k):
    base = {c: '' for c in COLS}
    base.update({'game_id': 'G1', 'season_type': 'REG', 'week': '1', 'posteam': 'CIN', 'defteam': 'JAX',
                 'yardline_100': '60', 'down': '1', 'ydstogo': '10', 'yards_gained': '0', 'pass_attempt': '0',
                 'rush_attempt': '0', 'sack': '0', 'qb_scramble': '0', 'qb_kneel': '0', 'qb_spike': '0',
                 'two_point_attempt': '0', 'complete_pass': '0', 'pass_touchdown': '0', 'rush_touchdown': '0',
                 'touchdown': '0', 'interception': '0'})
    base.update({kk: str(v) for kk, v in k.items()})
    return base


def _pbp(path, plays):
    with gzip.open(path, 'wt', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=COLS)
        w.writeheader()
        for p in plays:
            w.writerow(p)


def test_01_measured_usage_counts_football_correctly():
    td = pathlib.Path(tempfile.mkdtemp())
    plays = [
        _play(pass_attempt=1, passer_player_id='QB', receiver_player_id='WR', air_yards=25, complete_pass=1,
              passing_yards=30, receiving_yards=30, yards_gained=30),
        _play(pass_attempt=1, passer_player_id='QB', receiver_player_id='WR', air_yards=12, yardline_100=12,
              complete_pass=1, passing_yards=12, receiving_yards=12, pass_touchdown=1, touchdown=1, yards_gained=12),
        _play(pass_attempt=1, passer_player_id='QB', receiver_player_id='TE', air_yards=3, down=3, passing_yards=0),
        _play(rush_attempt=1, rusher_player_id='RB', yardline_100=3, ydstogo=1, rushing_yards=3, rush_touchdown=1,
              touchdown=1, yards_gained=3),
        _play(rush_attempt=1, rusher_player_id='QB', qb_scramble=1, rushing_yards=9, yards_gained=9, down=2),
        _play(pass_attempt=1, sack=1, passer_player_id='QB', yards_gained=-7),
        _play(rush_attempt=1, rusher_player_id='QB', qb_kneel=1),          # kneel: not counted
        _play(pass_attempt=1, passer_player_id='QB', receiver_player_id='WR', two_point_attempt=1),  # 2pt: not counted
        _play(week=2, rush_attempt=1, rusher_player_id='RB', rushing_yards=5),                         # outside window
    ]
    f = td / 'pbp.csv.gz'
    _pbp(f, plays)
    PU, TU, DU = B.measured_usage(f, 2026, [1])
    check('targets count real pass attempts only (no kneel, no two-point, no sack)', PU['WR']['targets'] == 2, PU['WR'])
    check('  deep target at 20+ air yards', PU['WR']['deep_targets'] == 1)
    check('  end-zone target when air yards reach the goal line', PU['WR']['end_zone_targets'] == 1)
    check('  red-zone target inside the 20', PU['WR']['rz_targets'] == 1)
    check('  goal-line carry inside the 5, short-yardage at 2 or less to go',
          PU['RB']['gl_carries'] == 1 and PU['RB']['short_yardage_carries'] == 1)
    check('  scramble counted as a carry and as a scramble', PU['QB']['carries'] == 1 and PU['QB']['scrambles'] == 1)
    check('  sack charged to the passer, not a pass attempt', PU['QB']['sacks_taken'] == 1 and PU['QB']['pass_att'] == 4 - 1)
    check('  the week outside the window is excluded', PU['RB']['carries'] == 1)
    check('  the defence sees the same plays: 3 pass attempts faced, 1 sack, 1 explosive pass',
          DU['JAX']['pass_att_faced'] == 3 and DU['JAX']['sacks'] == 1 and DU['JAX']['explosive_pass_allowed'] == 1, DU['JAX'])
    check('  club targets reconcile to the players', TU['CIN']['targets'] == sum(PU[x].get('targets', 0) for x in PU))


def test_02_game_stories_are_shares_of_simulated_worlds():
    hp = np.array([35, 35, 10, 31, 24.0])
    ap = np.array([31, 18, 9, 10, 20.0])
    labels, d = B.game_stories(hp, ap, np.array([20, 30, 40, 50, 60, 70.0]), 'CIN', 'JAX')
    check('a 66-point one-score world is a competitive shootout', labels[0] == 'competitive shootout', labels)
    check('  a 17-point margin at a middling total (53) is two scores or more', 'two scores' in labels[1], labels[1])
    check('  a 19-point total is a close defensive game', labels[2] == 'close defensive game', labels[2])
    check('  every world gets exactly one story', len(labels) == 5 and all(labels))


def test_03_prop_distribution_reads_the_stored_worlds():
    st = np.zeros((1000, 11), dtype=np.int16)
    st[:, 8] = np.arange(1000) * 1     # rec_yards in tenths: 0.0 .. 99.9
    st[:, 6] = 5
    st[:500, 9] = 1                    # rec_td in half the worlds
    d = B.prop_distribution(st, ('pass_att', 'pass_yards', 'pass_td', 'carries', 'rush_yards', 'rush_td',
                                 'targets', 'receptions', 'rec_yards', 'rec_td', 'interceptions'), 10)
    check('yards are rescaled from tenths', abs(d['rec_yards']['mean'] - 49.95) < 0.01, d['rec_yards'])
    check('  anytime TD probability from the worlds', d['anytime_td']['p_yes'] == 0.5)
    check('  a market with no volume is absent, not zero', 'pass_yards' not in d)
    check('  the distribution says P(over) must come from stored worlds', 'stored worlds' in d['P_OVER_FROM'])


def test_04_no_lineups_before_the_book():
    td = pathlib.Path(tempfile.mkdtemp())
    (td / 'p.json').write_text('{"a": 1}')
    (td / 'd.json').write_text('{"b": 2}')
    Pp = {'proj': td / 'p.json', 'draws': td / 'd.json'}
    old = P.OUT_DIR
    P.OUT_DIR = td
    try:
        o = P.research_book_gate('T', Pp)
        observe('nfl.opt.classic_portfolio:research_book_gate:PORTFOLIO_NO_RESEARCH_BOOK', o)
        check('positive control: no research book -> no lineups', o is not None and o.code == 'PORTFOLIO_NO_RESEARCH_BOOK')
        import hashlib
        sh = {'PROJ.json': hashlib.sha256(Pp['proj'].read_bytes()).hexdigest(),
              'DRAWS.json': hashlib.sha256(Pp['draws'].read_bytes()).hexdigest()}
        bp = td / 'DK_T_EARLY_RESEARCH_BOOK.json'
        bp.write_text(json.dumps({'inputs_sha256': {**sh, 'DRAWS.json': 'other'}, 'ACCOUNTING': {'state': 'PASS'}}))
        o = P.research_book_gate('T', Pp)
        observe('nfl.opt.classic_portfolio:research_book_gate:PORTFOLIO_RESEARCH_BOOK_STALE', o)
        check('positive control: a book from other draws is stale', o is not None and o.code == 'PORTFOLIO_RESEARCH_BOOK_STALE')
        bp.write_text(json.dumps({'inputs_sha256': sh, 'ACCOUNTING': {'state': 'FAIL', 'failures': ['CIN targets']}}))
        o = P.research_book_gate('T', Pp)
        observe('nfl.opt.classic_portfolio:research_book_gate:PORTFOLIO_REFUSES_ACCOUNTING_FAILURE', o)
        check('positive control: failed accounting refuses publication',
              o is not None and o.code == 'PORTFOLIO_REFUSES_ACCOUNTING_FAILURE')
        bp.write_text(json.dumps({'inputs_sha256': sh, 'ACCOUNTING': {'state': 'PASS'}}))
        check('negative control: a current book with accounting PASS lets lineups be built',
              P.research_book_gate('T', Pp) is None)
    finally:
        P.OUT_DIR = old


def test_05_kickoff_is_converted_through_the_zone():
    check('1:00 PM ET on 4 Oct 2026 (EDT) is 17:00Z', B.kickoff_utc('10/04/2026 01:00PM ET') == '2026-10-04T17:00:00+00:00')
    check('  and 1:00 PM ET on 6 Dec 2026 (EST) is 18:00Z', B.kickoff_utc('12/06/2026 01:00PM ET') == '2026-12-06T18:00:00+00:00')


def test_zz_every_check_passed():
    """The module's own counter, re-raised so a failure turns this module RED."""
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for n, f in sorted((k, v) for k, v in globals().items() if k.startswith('test_') and callable(v)):
        f()
    print(f'PASSED {PASSED}  FAILED {FAILED}')
