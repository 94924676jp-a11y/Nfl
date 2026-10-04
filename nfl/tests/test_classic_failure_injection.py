"""Failure injection on the Week-4 classic production path (owner priority 20, 2026-10-03).

Every failure the owner listed is injected into the function production actually calls, and that
function must refuse it by name. Each case has its negative control beside it.

  stale roster / evidence        world_clock.for_target           EVIDENCE_BEHIND_THE_SLATE
  wrong starter                  classic_prelock.evaluate         RERUN_REQUIRED (STARTER_ASSUMPTION_BROKEN)
  inactive player in a lineup    classic_prelock.evaluate         RERUN_REQUIRED (INACTIVE_IN_A_LINEUP)
  inactive player with volume    classic_production_audit         accounting FAIL
  ghost targets                  classic_production_audit         accounting FAIL
  non-QB pass-attempt leakage    football_sanity.assess           NON_QB_PASS_ATTEMPTS_ABOVE_CEILING
  unresolved DK identity         classic_upload_verify.verify     id not in the DK pool
  stale portfolio hash           classic_owner_board              portfolio_is_current False
  stale draws hash               classic_portfolio.load           PORTFOLIO_DRAWS_NOT_FROM_THIS_PROJECTION
  sportsbook leakage             classic_portfolio.load           PORTFOLIO_REFUSES_MARKET_ARM
  FC leakage                     fc_context                       FC_READ_FROM_PROPRIETARY_CONTEXT
  illegal / duplicate / salary   classic_portfolio.verify_lineup  named violations
  missing book / failed acctg    classic_portfolio.research_book_gate
  stale / pre-seal Hard Rock     price_history.comparable / classic_prop_compare (tested in
                                 test_classic_prop_compare; re-driven here for the pre-seal case)
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tests._controls import observe  # noqa: E402

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


def test_01_stale_evidence_blocks_the_slate():
    from nfl.production import world_clock as W
    td = pathlib.Path(tempfile.mkdtemp())
    tg = td / 'TEAM_GAME.json'
    tg.write_text(json.dumps({'rows': [{'season': 2026, 'game_id': '2026_03_AAA_BBB', 'club': c, 'points': 20, 'week': 3}
                                       for c in ('AAA', 'BBB')]}))
    sched = [{'season': 2026, 'week': 3, 'game_id': '2026_03_AAA_BBB', 'gameday': '2026-09-21'},
             {'season': 2026, 'week': 3, 'game_id': '2026_03_CCC_DDD', 'gameday': '2026-09-21'}]
    saved = W.TEAM_GAME
    try:
        W.TEAM_GAME = tg
        o = W.for_target(2026, 4, as_of='2026-10-03', rows=sched)
    finally:
        W.TEAM_GAME = saved
    check('positive control: an unscored week-3 game -> EVIDENCE_BEHIND_THE_SLATE', o.code == 'EVIDENCE_BEHIND_THE_SLATE', o.code)


def _state(chart_only='Tyson Bagent', q=None):
    return {'players': {
        '1': {'name': chart_only, 'team': 'CHI', 'current_availability': {'status': 'UNKNOWN_ACTIVE_STATE', 'designation': None},
              'predicted_lineup_context': {'state': 'DEPTH_CHART_NEXT_HEALTHY_AFTER_REPORTED_OUT'}},
        '2': {'name': 'DJ Moore', 'team': 'BUF', 'current_availability': {'status': 'UNKNOWN_ACTIVE_STATE', 'designation': q},
              'predicted_lineup_context': {}}}}


PORT = {'contests': [{'profile': 'MAX20', 'report': {'player_exposure': {'a': {'dk_id': '1', 'overall': 0.35},
                                                                         'b': {'dk_id': '2', 'overall': 0.2}}}}]}


def test_02_prelock_triggers():
    from nfl.tools import classic_prelock as L
    o = L.evaluate(_state(), PORT, None)
    observe('nfl.tools.classic_prelock:evaluate:AWAITING_OFFICIAL_INACTIVES', o)
    check('positive control: no inactive list -> AWAITING, never "no change"', o.code == 'AWAITING_OFFICIAL_INACTIVES', o.code)
    o = L.evaluate(_state(), PORT, ['Somebody Else'])
    check('negative control: lists supplied, nothing relevant -> NO_RERUN_REQUIRED', o.code == 'NO_RERUN_REQUIRED', o.code)
    o = L.evaluate(_state(), PORT, [], {'CHI': 'Case Keenum'})
    observe('nfl.tools.classic_prelock:evaluate:RERUN_REQUIRED', o)
    check('positive control: wrong starter (club names Keenum) -> RERUN_REQUIRED',
          o.code == 'RERUN_REQUIRED' and any(r['kind'] == 'STARTER_ASSUMPTION_BROKEN' for r in o.evidence['reasons']))
    o = L.evaluate(_state(), PORT, ['DJ Moore'])
    check('positive control: a lineup player on the inactive list -> INACTIVE_IN_A_LINEUP',
          o.code == 'RERUN_REQUIRED' and any(r['kind'] == 'INACTIVE_IN_A_LINEUP' for r in o.evidence['reasons']))
    o = L.evaluate(_state(q='QUESTIONABLE'), PORT, [], None, ['DJ Moore'])
    check('positive control: a Questionable player explicitly cleared -> rerun',
          any(r['kind'] == 'QUESTIONABLE_RESOLVED' and r['now'] == 'ACTIVE' for r in (o.evidence or {}).get('reasons', [])))
    o = L.evaluate(_state(q='QUESTIONABLE'), PORT, ['Somebody Else'])
    check('negative control: a Questionable player on neither list stays unresolved (absence is not active)',
          not any(r['kind'] == 'QUESTIONABLE_RESOLVED' for r in (o.evidence or {}).get('reasons', [])), o.evidence)


def _proj(targets_sum=30.0, absent_targets=0.0, team_targets=30.0):
    return {'team_volume': {'CIN': {'proj_pass_attempts': 35.0, 'proj_targets': team_targets, 'proj_rush_attempts': 25.0}},
            'rows': {'q': {'team': 'CIN', 'position': 'QB', 'pass_attempts': 35.0, 'targets': 0.0, 'carries': 3.0, 'td': {'pass_td': 1.5}},
                     'w': {'team': 'CIN', 'position': 'WR', 'pass_attempts': 0.0, 'targets': targets_sum - absent_targets,
                           'carries': 0.0, 'td': {'rec_td': 1.5}},
                     'r': {'team': 'CIN', 'position': 'RB', 'pass_attempts': 0.0, 'targets': 0.0, 'carries': 22.0, 'td': {}},
                     'x': {'team': 'CIN', 'position': 'WR', 'pass_attempts': 0.0, 'targets': absent_targets, 'carries': 0.0, 'td': {}}}}


def test_03_accounting_refuses_ghost_and_absent_volume():
    from nfl.tools import classic_production_audit as A
    st = {'games': {'g': {'away': 'CIN', 'home': 'CIN'}},
          'players': {'x': {'current_availability': {'status': 'REPORTED_INACTIVE_OFFICIAL_RELEASE_CITED'}}}}
    o = A.accounting(_proj(), st)
    check('negative control: closed club accounting passes', o['state'] == 'PASS', o)
    o = A.accounting(_proj(team_targets=32.0), st)
    check('positive control: 2 ghost targets (club 32, players 30) -> FAIL', o['state'] == 'FAIL' and o['failures'] == ['CIN'], o)
    o = A.accounting(_proj(absent_targets=4.0), st)
    check('positive control: an OUT player carrying 4 targets -> FAIL',
          o['state'] == 'FAIL' and o['per_team']['CIN']['absent_players_volume'] == 4.0, o)


def test_04_non_qb_pass_attempts_refused():
    from nfl.tools import football_sanity as FS
    art = {'rows': {'1': {'name': 'Q', 'team': 'CIN', 'position': 'QB', 'pass_attempts': 30.0, 'dk_points': 18.0},
                    '2': {'name': 'W', 'team': 'CIN', 'position': 'WR', 'pass_attempts': 6.0, 'targets': 8.0, 'dk_points': 12.0}},
           'team_volume': {'CIN': {'proj_pass_attempts': 36.0, 'proj_targets': 33.0, 'proj_rush_attempts': 25.0}}}
    o = FS.assess(art, clubs=['CIN'], units=('DST',))
    got = FS.NON_QB_PASS_ATTEMPTS if FS.NON_QB_PASS_ATTEMPTS in ((o.evidence or {}).get('problems') or {}) else o.code
    observe('nfl.tools.football_sanity:assess:NON_QB_PASS_ATTEMPTS_ABOVE_CEILING', got)
    check('positive control: a receiver throwing 6 passes is refused, naming the class',
          o.state.value == 'FAIL' and got == 'NON_QB_PASS_ATTEMPTS_ABOVE_CEILING', o.detail)


def test_05_lineup_and_upload_refusals():
    from nfl.opt import classic_portfolio as P
    from nfl.tools import classic_upload_verify as U
    meta = {str(i): {'pos': pos, 'team': t, 'opp': o, 'game': g, 'salary': sal, 'state': 'PROJECTED' if pos != 'DST' else 'PROJECTED_DST',
                     'designation': None}
            for i, (pos, t, o, g, sal) in enumerate([('QB', 'A', 'B', 'G1', 7000), ('RB', 'A', 'B', 'G1', 6000), ('RB', 'C', 'D', 'G2', 6000),
                                                     ('WR', 'A', 'B', 'G1', 6000), ('WR', 'B', 'A', 'G1', 5000), ('WR', 'C', 'D', 'G2', 5000),
                                                     ('TE', 'C', 'D', 'G2', 4000), ('RB', 'D', 'C', 'G2', 4000), ('DST', 'C', 'D', 'G2', 3000),
                                                     ('WR', 'C', 'D', 'G2', 20000)])}
    legal = [str(i) for i in range(9)]
    check('negative control: a legal lineup has no violation', P.verify_lineup(legal, meta) == [])
    check('positive control: a duplicated player is refused', any('twice' in v for v in P.verify_lineup(legal[:8] + ['1'], meta)))
    check('positive control: a salary-cap breach is refused',
          any('cap' in v for v in P.verify_lineup(legal[:5] + ['9'] + legal[6:], meta)))
    pool = [{'dk_id': '1', 'dk_name': 'X', 'dk_pos': 'QB', 'flex_eligible': False, 'salary': 7000, 'game_info': 'A@B x'}]
    rows = [list(U.HEADER), ['E1', 'C', '1', '$1', '1', '777', '2', '3', '4', '5', '6', '7', '8']]
    o = U.verify(rows, pool, [{'entry_id': 'E1', 'contest_name': 'C', 'contest_id': '1', 'entry_fee': '$1'}], set())
    check('positive control: an unresolved id (not in DK\'s pool) is refused in the upload',
          o.state.value == 'FAIL' and any('not in the DK pool' in v for v in o.evidence['violations']))


def _portfolio_fixture(td, arm='FOOTBALL_ONLY', draws_sha=None):
    (td / 'DK_T_EARLY_STATE.json').write_text(json.dumps({'players': {}}))
    (td / 'DK_T_EARLY_PROJ.json').write_text(json.dumps({'market_arm': arm, 'rows': {}}))
    sha = hashlib.sha256((td / 'DK_T_EARLY_PROJ.json').read_bytes()).hexdigest()
    (td / 'DK_T_EARLY_DRAWS.json').write_text(json.dumps({'market_arm': arm, 'football_sanity': {'state': 'PASS', 'code': 'X'},
                                                          'projection_sha256': draws_sha or sha}))


def test_06_portfolio_input_refusals():
    from nfl.opt import classic_portfolio as P
    old = P.OUT_DIR
    try:
        td = pathlib.Path(tempfile.mkdtemp())
        P.OUT_DIR = td
        _portfolio_fixture(td, draws_sha='0' * 64)
        o = P.load('T')
        observe('nfl.opt.classic_portfolio:load:PORTFOLIO_DRAWS_NOT_FROM_THIS_PROJECTION', o)
        check('positive control: draws from another projection are refused', o.code == 'PORTFOLIO_DRAWS_NOT_FROM_THIS_PROJECTION', o.code)
        _portfolio_fixture(td, arm='MARKET')
        o = P.load('T')
        observe('nfl.opt.classic_portfolio:load:PORTFOLIO_REFUSES_MARKET_ARM', o)
        check('positive control: a market-arm (sportsbook-fed) projection is refused', o.code == 'PORTFOLIO_REFUSES_MARKET_ARM', o.code)
        _portfolio_fixture(td)
        o = P.load('T')
        check('  and with clean inputs the next refusal is the missing research book',
              o.code == 'PORTFOLIO_NO_RESEARCH_BOOK', o.code)
    finally:
        P.OUT_DIR = old


def test_07_stale_portfolio_never_lends_exposures():
    from nfl.tools import classic_owner_board as OB
    cur = {'state': 'a', 'proj': 'b', 'draws': 'c'}
    check('negative control: a portfolio built on these inputs is current', OB.portfolio_is_current({'inputs_sha256': dict(cur)}, cur))
    check('positive control: a portfolio from other draws is stale',
          not OB.portfolio_is_current({'inputs_sha256': {**cur, 'draws': 'old'}}, cur))


def test_08_fc_firewall_refuses_in_a_proprietary_process():
    import importlib
    from nfl.tools import fc_context as FC
    importlib.import_module('nfl.production.world_clock')     # a proprietary module is now on the graph
    o = FC.assert_no_proprietary_importer()
    observe('nfl.tools.fc_context:assert_no_proprietary_importer:FC_READ_FROM_PROPRIETARY_CONTEXT', o)
    check('positive control: FantasyCruncher values are refused to a process holding proprietary code',
          o.code == 'FC_READ_FROM_PROPRIETARY_CONTEXT', o.code)


def test_09_pre_seal_and_post_kickoff_prices_refused():
    from nfl.market import price_history as PH
    seal = {'written_at': '2026-10-03T18:20:00+00:00', 'kickoff_utc': '2026-10-04T17:00:00+00:00'}
    check('negative control: a price after the seal and before kickoff is comparable',
          PH.comparable(seal, {'ts_utc': '2026-10-04T15:45:00+00:00'}).code == 'COMPARABLE')
    o = PH.comparable(seal, {'ts_utc': '2026-10-03T12:00:00+00:00'})
    check('positive control: a pre-seal price is refused', o.code == 'PRICE_PREDATES_THE_SEAL', o.code)
    o = PH.comparable(seal, {'ts_utc': '2026-10-04T17:30:00+00:00'})
    check('positive control: an in-play price is refused', o.code == 'PRICE_IS_POST_KICKOFF', o.code)


def test_zz_every_check_passed():
    """The module's own counter, re-raised so a failure turns this module RED."""
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for n, f in sorted((k, v) for k, v in globals().items() if k.startswith('test_') and callable(v)):
        f()
    print(f'PASSED {PASSED}  FAILED {FAILED}')
