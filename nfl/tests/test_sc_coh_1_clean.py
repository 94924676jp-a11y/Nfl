#!/usr/bin/env python3.12
"""SC-COH-1 CLEAN comparison harness (nfl/research/coherence/sc_coh_1_clean_eval.py).

    python3.12 nfl/tests/test_sc_coh_1_clean.py

  A  NO SPORTSBOOK FIELD reaches any incumbent or candidate input in the clean path. Adversarial: total_line /
     spread_line / moneyline / odds injected into every source (play-by-play frame, TEAM_GAME rows, player-games,
     pools, specs, library games) are REFUSED with SC_COH_1_CLEAN_MARKET_INPUT; whitelisting drops them from a
     perturbed row; the committed play-by-play loads without them; the module never calls the market-line routes of
     the original harness.
  B  POINT-IN-TIME POOLS: removing or perturbing every row of the evaluated week (and later weeks) leaves every
     pool byte-identical; a player whose only appearance is in the evaluated game never enters it; no snap source
     is referenced.
  C  HELD-OUT SEPARATION: every fitted quantity is identical with and without 2025 rows; 2025 play-by-play is
     unreadable with the gate closed; a 2025 library season or game is refused.
  D  PRE-REGISTRATION ENFORCED: a changed prereg / frozen file, a missing lock, a confirmation re-read, a code change
     since development and an off-design confirmation are each refused by name.
  E  REFUSAL ON EMPTY INPUT with named errors, at every stage.
  F  CONSERVATION COUNTERS count exactly the planted violations, and nothing on a clean world.
  G  SCORING RULES against reference computations (CRPS, energy, variogram, PIT, log-score floor, block bootstrap).
  H  SMOKE: the whole scoring loop on two IN-SAMPLE 2024 games; the candidate's identities hold at stage S0.
"""
from __future__ import annotations

import ast
import collections
import json
import pathlib
import sys
import tempfile

import numpy as np
import pandas as pd

_REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))
from nfl.research.coherence import sc_coh_1_clean_eval as E  # noqa: E402

PASSED = FAILED = 0
SRC = pathlib.Path(E.__file__).read_text()


def check(ok, msg):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {msg}')
    else:
        FAILED += 1
        print(f'  FAIL {msg}')


def _raises(fn, code):
    try:
        fn()
    except E.CleanEvalError as e:
        return e.code == code, e.code
    except Exception as e:  # noqa: BLE001
        return False, f'{type(e).__name__}: {e}'
    return False, 'no error'


def _canon(x):
    if isinstance(x, dict):
        x = {('|'.join(map(str, k)) if isinstance(k, tuple) else k): v for k, v in x.items()}
    return json.dumps(x, sort_keys=True, default=float)


# --------------------------------------------------------------------------------------------- fixtures
def _spec(n_extra=0):
    def club(t):
        return {'club': t, 'dst_id': f'DST|{t}', 'players': [
            {'id': f'{t}_QB', 'position': 'QB', 'target_share': 0.0, 'carry_share': 0.1, 'pass_att_share': 1.0,
             'pass_td_share': 0.0, 'rush_td_share': 0.1, 'catch_rate': 0.65, 'slot': 'OTHER'},
            {'id': f'{t}_WR', 'position': 'WR', 'target_share': 0.7, 'carry_share': 0.0, 'pass_att_share': 0.0,
             'pass_td_share': 0.7, 'rush_td_share': 0.0, 'catch_rate': 0.65, 'slot': 'OTHER'},
            {'id': f'{t}_RB', 'position': 'RB', 'target_share': 0.3, 'carry_share': 0.9, 'pass_att_share': 0.0,
             'pass_td_share': 0.3, 'rush_td_share': 0.9, 'catch_rate': 0.75, 'slot': 'OTHER'}]}
    return {'total_line': 44.0, 'home_spread': 2.0, 'fc_total': 44.0, 'fc_margin': 2.0,
            'scoring_basis': 'FOOTBALL_ONLY_OWN_OFFENCE_BLEND', 'clubs': [club('H'), club('A')]}


def _clean_world(n=4):
    """A coherent world: QB 10 att / 6 cmp-to-WR+RB, every identity holds, points 21 = 3 TD x 7."""
    P = {}
    for t in ('H', 'A'):
        qb = np.zeros((n, 10)); wr = np.zeros((n, 10)); rb = np.zeros((n, 10))
        qb[:, E.SX['pass_att']] = 10; qb[:, E.SX['pass_yards']] = 80; qb[:, E.SX['pass_td']] = 2
        qb[:, E.SX['carries']] = 2; qb[:, E.SX['rush_yards']] = 6
        wr[:, E.SX['targets']] = 6; wr[:, E.SX['receptions']] = 4; wr[:, E.SX['rec_yards']] = 60
        wr[:, E.SX['rec_td']] = 2
        rb[:, E.SX['targets']] = 3; rb[:, E.SX['receptions']] = 2; rb[:, E.SX['rec_yards']] = 20
        rb[:, E.SX['carries']] = 15; rb[:, E.SX['rush_yards']] = 70; rb[:, E.SX['rush_td']] = 1
        P[f'{t}_QB'], P[f'{t}_WR'], P[f'{t}_RB'] = qb, wr, rb
    pts = {'H': np.full(n, 21.0), 'A': np.full(n, 21.0)}
    comp = {t: np.tile([2.0, 1.0, 0.0, 0.0], (n, 1)) for t in ('H', 'A')}
    from nfl.sim import dst as D
    dk = {t: np.full(n, D.tier(21.0) + 2 + 2 * 1) for t in ('H', 'A')}
    return {'players': P, 'ints': None, 'club_points': pts, 'club_td': {t: np.full(n, 3.0) for t in ('H', 'A')},
            'dst_dk': dk, 'dst_comp': comp}


def _counts(world):
    acc = collections.Counter()
    E.conservation(_spec(), world, acc)
    return acc


# --------------------------------------------------------------------------------------------- A
def test_a_no_market_field_reaches_any_input():
    print('\nA. no sportsbook field reaches any clean-path input (adversarial injection is refused)')
    for col in ('total_line', 'spread_line', 'moneyline', 'odds', 'home_moneyline', 'implied_total', 'vegas_wp'):
        df = pd.DataFrame({'game_id': ['g'], col: [1.0]})
        ok, got = _raises(lambda: E.guard_no_market(df, 'pbp'), 'SC_COH_1_CLEAN_MARKET_INPUT')
        check(ok, f'play-by-play frame carrying {col!r} -> refused ({got})')
    rows = [{'game_id': 'g', 'club': 'H', 'season': 2023, 'week': 3, 'points': 20.0, 'total_line': 44.5}]
    ok, got = _raises(lambda: E.points_table(rows), 'SC_COH_1_CLEAN_MARKET_INPUT')
    check(ok, f'TEAM_GAME row carrying total_line -> football centre table refused ({got})')
    ok, got = _raises(lambda: E.fit_shared_state(rows * 500), 'SC_COH_1_CLEAN_MARKET_INPUT')
    check(ok, f'TEAM_GAME row carrying total_line -> volume/scoring refit refused ({got})')
    ok, got = _raises(lambda: E.fit_football_residuals(rows * 500), 'SC_COH_1_CLEAN_MARKET_INPUT')
    check(ok, f'TEAM_GAME row carrying total_line -> residual refit refused ({got})')
    # whitelisting removes market fields from a perturbed row, so their values cannot move anything
    a = {'game_id': 'g', 'club': 'H', 'season': 2023, 'week': 3, 'points': 20.0, 'total_line': 44.5,
         'club_spread': 3.0, 'implied_total': 23.75, 'moneyline': -150, 'spread_line_raw': -3}
    b = dict(a, total_line=60.0, club_spread=-14.0, implied_total=40.0, moneyline=500, spread_line_raw=14)
    wa, wb = E.whitelist_rows([a], E.TG_FIELDS), E.whitelist_rows([b], E.TG_FIELDS)
    check(wa == wb and not any(E.is_market_name(k) for k in wa[0]),
          'perturbing every TEAM_GAME market field leaves the whitelisted row identical and market-free')
    ok, got = _raises(lambda: E.whitelist_rows([a], ('points', 'total_line')), 'SC_COH_1_CLEAN_MARKET_INPUT')
    check(ok, f'a whitelist that names a market field is itself refused ({got})')
    pg = pd.DataFrame({'game_id': ['g'], 'team': ['H'], 'week': [1], 'pid': ['p'], 'spread_line': [3.0]})
    sch = pd.DataFrame({'game_id': ['g2'], 'week': [2], 'home': ['H'], 'away': ['A']})
    ok, got = _raises(lambda: E.build_pools(pg, sch), 'SC_COH_1_CLEAN_MARKET_INPUT')
    check(ok, f'player-games carrying spread_line -> pool builder refused ({got})')
    s = _spec()
    s['moneyline_home'] = -150
    ok, got = _raises(lambda: E.assert_spec_football_only(s), 'SC_COH_1_CLEAN_MARKET_INPUT')
    check(ok, f'a spec carrying a moneyline -> refused ({got})')
    s = _spec()
    s['total_line'] = 47.5          # a market total smuggled into the simulator's API key
    ok, got = _raises(lambda: E.assert_spec_football_only(s), 'SC_COH_1_CLEAN_SPEC_NOT_FOOTBALL')
    check(ok, f'a simulator centre that is not the football centre -> refused ({got})')
    s = _spec()
    s['scoring_basis'] = 'MARKET_LINES'
    ok, got = _raises(lambda: E.assert_spec_football_only(s), 'SC_COH_1_CLEAN_SPEC_NOT_FOOTBALL')
    check(ok, f'a spec whose scoring basis is the market -> refused ({got})')
    s = _spec()
    s['clubs'][0]['players'][0]['implied_share'] = 0.5
    ok, got = _raises(lambda: E.assert_spec_football_only(s), 'SC_COH_1_CLEAN_MARKET_INPUT')
    check(ok, f'a player row carrying a market-derived field -> refused ({got})')
    g = {'game_id': 'x', 'season': 2023, 'fc_total': 44.0, 'fc_margin': 1.0, 'home': {}, 'away': {}}
    ok, got = _raises(lambda: E.CleanLibrary([g, dict(g, game_id='y', fc_total=40.0, fc_margin=-3.0,
                                                      total_line=44.5)], (2023,)), 'SC_COH_1_CLEAN_MARKET_INPUT')
    check(ok, f'a library game carrying total_line -> refused ({got})')
    # the real committed play-by-play carries total_line / spread_line / vegas_wp; the clean loader never reads them
    df = E.load_pbp_clean(2024)
    bad = [c for c in df.columns if E.is_market_name(c)]
    head = pd.read_csv(E.M.pbp_path(2024), nrows=1).columns
    check(not bad and 'total_line' in head and 'spread_line' in head,
          f'2024 pbp file carries total_line/spread_line; the clean frame has no market column ({bad})')
    check(not any(E.is_market_name(f) for f in E.TG_FIELDS + E.PG_FIELDS + E.RH_FIELDS)
          and not any(E.is_market_name(c) for c in E.PBP_CLEAN_COLS), 'every source whitelist is market-free')
    # the clean module never calls the market-line routes of the first pass
    tree = ast.parse(SRC)
    called = {f'{n.value.id}.{n.attr}' for n in ast.walk(tree) if isinstance(n, ast.Attribute)
              and isinstance(n.value, ast.Name)}
    forbidden = {'M.load_pbp', 'M.finals', 'M.game_spec', 'M.history_units', 'M.snap_pool', 'M.pregame_pools',
                 'C.build_library', 'C.simulate', 'C.Library', 'C.estimate_share_concentration', 'FP.load', 'FP._rows'}
    check(not (called & forbidden), f'no call to a market-line or snap-pool route of the first pass ({called & forbidden})')


# --------------------------------------------------------------------------------------------- B
def test_b_pools_are_point_in_time():
    print('\nB. pools use only weeks < W: evaluated-game rows removed or perturbed -> identical pools')
    fr = E.season_frames(2024)
    pg, sch = fr['pg'], fr['sched']
    W = 10
    base, ex = E.build_pools(pg, sch, 'SEASON_TO_DATE', weeks={W})
    check(len(base) > 20, f'{len(base)} week-{W} club-game pools built')
    cut, _ = E.build_pools(pg[pg.week < W], sch, 'SEASON_TO_DATE', weeks={W})
    check(_canon(cut) == _canon(base), 'every row of week >= W removed -> pools identical')
    rng = np.random.default_rng(3)
    pert = pg.copy()
    m = pert.week >= W
    for c in ('targets', 'carries', 'pass_att', 'receptions', 'rec_yards', 'rush_yards', 'pass_yards', 'dk'):
        pert.loc[m, c] = rng.permutation(pert.loc[m, c].to_numpy()) * 3 + 7
    pert = pert.sample(frac=1.0, random_state=5)
    p2, _ = E.build_pools(pert, sch, 'SEASON_TO_DATE', weeks={W})
    check(_canon(p2) == _canon(base), 'week >= W rows shuffled and rescaled (row order shuffled too) -> identical')
    gid, club = next(iter(base))
    extra = pd.DataFrame([{'game_id': gid, 'season': 2024, 'week': W, 'team': club, 'pid': '00-NEWGUY',
                           'pass_att': 0, 'pass_yards': 0, 'pass_td': 0, 'targets': 12, 'receptions': 9,
                           'rec_yards': 150, 'rec_td': 2, 'carries': 0, 'rush_yards': 0, 'rush_td': 0, 'dk': 45}])
    p3, _ = E.build_pools(pd.concat([pg, extra], ignore_index=True), sch, 'SEASON_TO_DATE', weeks={W})
    check(all(p['pid'] != '00-NEWGUY' for p in p3[(gid, club)]['players']) and _canon(p3) == _canon(base),
          'a player whose only appearance is the evaluated game never enters its pool')
    last, _ = E.build_pools(pg[pg.week < W], sch, 'LAST_GAME', weeks={W})
    lb, _ = E.build_pools(pg, sch, 'LAST_GAME', weeks={W})
    check(_canon(last) == _canon(lb) and all(len(lb[k]['players']) <= len(base[k]['players']) for k in lb),
          'LAST_GAME pools are point-in-time too and are subsets of SEASON_TO_DATE pools')
    tree = ast.parse(SRC)
    idents = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | \
             {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    snapish = sorted(i for i in idents if 'snap' in i.lower())
    check(not snapish, f'the clean module names no snap-count source in code ({snapish})')


# --------------------------------------------------------------------------------------------- C
def test_c_fits_identical_without_2025_rows():
    print('\nC. every fitted quantity identical with and without 2025 rows; 2025 unreadable with the gate closed')
    raw_tg = E.whitelist_rows(E._rows_of(str(E.TG_PATH)), E.TG_FIELDS)
    with25 = [r for r in raw_tg if r.get('season') is not None and r.get('week') is not None]
    without = [r for r in with25 if int(r['season']) <= E.CUTOFF]
    check(any(int(r['season']) == 2025 for r in with25), 'the TEAM_GAME fixture really carries 2025 rows')
    for name, fn in (('football residuals', E.fit_football_residuals), ('volume/scoring (SHARED_STATE)', E.fit_shared_state),
                     ('DST bands', E.fit_dst_bands)):
        check(_canon(fn(with25)) == _canon(fn(without)), f'{name}: identical with and without 2025 rows')
    raw_pg = E.whitelist_rows(E._rows_of(str(E.PG_PATH)), E.PG_FIELDS)
    pg_w = [r for r in raw_pg if r.get('season') is not None]
    pg_o = [r for r in pg_w if int(r['season']) <= E.CUTOFF]
    raw_rh = E.whitelist_rows(E._rows_of(str(E.RH_PATH)), E.RH_FIELDS)
    rh_w = [r for r in raw_rh if r.get('season') is not None]
    rh_o = [r for r in rh_w if int(r['season']) <= E.CUTOFF]
    check(any(int(r['season']) == 2025 for r in pg_w), 'the PLAYER_GAME fixture really carries 2025 rows')
    check(_canon(E.fit_efficiency(pg_w)) == _canon(E.fit_efficiency(pg_o)), 'efficiency: identical without 2025')
    check(_canon(E.fit_usage(pg_w, rh_w)) == _canon(E.fit_usage(pg_o, rh_o)), 'teammate concentration: identical')
    check(_canon(E.fit_variance_components(pg_w)) == _canon(E.fit_variance_components(pg_o)),
          'variance components: identical without 2025')
    ok, got = _raises(lambda: E.load_pbp_clean(2025), 'SC_COH_1_CLEAN_EVAL_SEASON_LOCKED')
    check(ok, f'2025 play-by-play read with the gate closed -> refused ({got})')
    check(all(int(r['season']) <= E.CUTOFF for r in E.load_team_game()), 'TEAM_GAME loader holds no 2025 row (gate closed)')
    ok, got = _raises(lambda: E.build_clean_library((2024, 2025), without), 'SC_COH_1_CLEAN_HELDOUT_LEAK')
    check(ok, f'a 2025 library season -> refused ({got})')
    g = {'game_id': 'x', 'season': 2025, 'fc_total': 44.0, 'fc_margin': 1.0, 'home': {}, 'away': {}}
    ok, got = _raises(lambda: E.CleanLibrary([g, dict(g, game_id='y', fc_total=40.0, fc_margin=-2.0)], (2025,)),
                      'SC_COH_1_CLEAN_HELDOUT_LEAK')
    check(ok, f'a library holding a 2025 game -> refused ({got})')
    ok, got = _raises(lambda: E.dry_run_in_sample(season=2025), 'SC_COH_1_CLEAN_DRY_RUN_NOT_IN_SAMPLE')
    check(ok, f'the in-sample smoke route cannot be pointed at 2025 ({got})')


# --------------------------------------------------------------------------------------------- D
def test_d_prereg_hash_enforced():
    print('\nD. pre-registration hash enforced; confirmation read once')
    d = pathlib.Path(tempfile.mkdtemp(prefix='sc_coh_1_clean_'))
    pr, fz, lk = d / 'prereg.md', d / 'frozen.json', d / 'lock.json'
    pr.write_text('# prereg\nmargin 1.02\n')
    fz.write_text('{"a": 1}')
    ok, got = _raises(lambda: E.verify_prereg(pr, lk, fz), 'SC_COH_1_CLEAN_PREREG_NOT_LOCKED')
    check(ok, f'no lock -> refused ({got})')
    lk.write_text(json.dumps({'prereg_sha256': E._sha(pr), 'frozen_sha256': E._sha(fz)}))
    check(E.verify_prereg(pr, lk, fz)['prereg_sha256'] == E._sha(pr), 'unchanged prereg + frozen -> verified')
    pr.write_text('# prereg\nmargin 1.05\n')
    ok, got = _raises(lambda: E.verify_prereg(pr, lk, fz), 'SC_COH_1_CLEAN_PREREG_CHANGED')
    check(ok, f'one character of the prereg changed -> refused ({got})')
    pr.write_text('# prereg\nmargin 1.02\n')
    fz.write_text('{"a": 2}')
    ok, got = _raises(lambda: E.verify_prereg(pr, lk, fz), 'SC_COH_1_CLEAN_FROZEN_CHANGED')
    check(ok, f'frozen scales changed after the lock -> refused ({got})')
    pr.unlink()
    ok, got = _raises(lambda: E.verify_prereg(pr, lk, fz), 'SC_COH_1_CLEAN_PREREG_ABSENT')
    check(ok, f'prereg deleted -> refused ({got})')
    reg = (E.N_WORLDS, None, E.POOL_MODES)
    check(E.check_phase_preconditions('development', {}, 'abc', *reg), 'a first development run is allowed')
    ok, got = _raises(lambda: E.check_phase_preconditions('confirmation', {}, 'abc', *reg),
                      'SC_COH_1_CLEAN_NO_DEVELOPMENT_RUN')
    check(ok, f'confirmation before development -> refused ({got})')
    dev = {'development': {'code_sha256': 'abc'}}
    check(E.check_phase_preconditions('confirmation', dev, 'abc', *reg), 'confirmation after a same-code dev run: allowed')
    ok, got = _raises(lambda: E.check_phase_preconditions('confirmation', dev, 'abd', *reg),
                      'SC_COH_1_CLEAN_CODE_CHANGED_SINCE_DEVELOPMENT')
    check(ok, f'harness changed since development -> refused ({got})')
    ok, got = _raises(lambda: E.check_phase_preconditions('confirmation', dev, 'abc', 100, None, E.POOL_MODES),
                      'SC_COH_1_CLEAN_CONFIRMATION_NOT_AS_REGISTERED')
    check(ok, f'confirmation with fewer worlds than registered -> refused ({got})')
    done = dict(dev, confirmation={'code_sha256': 'abc'})
    for ph in ('confirmation', 'development'):
        ok, got = _raises(lambda: E.check_phase_preconditions(ph, done, 'abc', *reg),
                          'SC_COH_1_CLEAN_CONFIRMATION_ALREADY_READ')
        check(ok, f'{ph} after confirmation was read -> refused ({got})')
    if E.LOCK.exists() and E.PREREG.exists():
        lkd = json.loads(E.LOCK.read_text())
        check(lkd['prereg_sha256'] == E._sha(E.PREREG) and lkd['frozen_sha256'] == E._sha(E.FROZEN),
              'the committed prereg and frozen file match the committed lock')
        if E.OUT.exists():
            o = json.loads(E.OUT.read_text())
            check(o['prereg']['sha256'] == lkd['prereg_sha256']
                  and all(p.get('prereg_sha256') == lkd['prereg_sha256'] for k, p in o['phases'].items()
                          if isinstance(p, dict) and 'prereg_sha256' in p),
                  'every scored phase in the output carries the locked prereg sha256')


# --------------------------------------------------------------------------------------------- E
def test_e_refusal_on_empty_input():
    print('\nE. refusal on empty input, by name')
    empty_pg = pd.DataFrame(columns=['game_id', 'team', 'week', 'pid'])
    sch = pd.DataFrame({'game_id': ['g'], 'week': [2], 'home': ['H'], 'away': ['A']})
    for name, fn in (('pools: empty player-games', lambda: E.build_pools(empty_pg, sch)),
                     ('pools: empty schedule', lambda: E.build_pools(pd.DataFrame({'team': ['H'], 'week': [1]}),
                                                                     sch.iloc[0:0])),
                     ('efficiency fit', lambda: E.fit_efficiency([])),
                     ('volume fit', lambda: E.fit_shared_state([])),
                     ('football centre table', lambda: E.points_table([])),
                     ('library', lambda: E.CleanLibrary([], (2024,))),
                     ('candidate: a club with no players',
                      lambda: E.simulate_candidate(None, {}, dict(_spec(), clubs=[dict(_spec()['clubs'][0], players=[]),
                                                                                  _spec()['clubs'][1]]), 10, 1)),
                     ('incumbent: a club with no passer',
                      lambda: E._check_spec_nonempty({'clubs': [_spec()['clubs'][0],
                                                                dict(_spec()['clubs'][1],
                                                                     players=_spec()['clubs'][1]['players'][1:])]}, 10)),
                     ('incumbent: zero worlds', lambda: E._check_spec_nonempty(_spec(), 0))):
        code = 'SC_COH_1_CLEAN_EMPTY_INPUT'
        ok, got = _raises(fn, code)
        check(ok, f'{name} -> {code} ({got})')
    ok, got = _raises(lambda: E.summarise_pool('SEASON_TO_DATE', [], [], [], [], [], [], [], {}, {}, {}, {}, {}, {}),
                      'SC_COH_1_CLEAN_EMPTY_INPUT')
    check(ok, f'no scorable game -> SC_COH_1_CLEAN_EMPTY_INPUT ({got})')
    ok, got = _raises(lambda: E.build_pools(empty_pg, sch, mode='BY_SNAPS'), 'SC_COH_1_CLEAN_POOL_MODE')
    check(ok, f'an unregistered pool mode -> refused ({got})')


# --------------------------------------------------------------------------------------------- F
def test_f_conservation_counters_on_planted_violations():
    print('\nF. conservation counters: zero on a coherent world, exact on planted violations')
    acc = _counts(_clean_world())
    zero = [k for k in E.CONSERVATION_CHECKS if k not in ('club_opp_qb_ints_gt_dst_takeaways',)]
    check(all(acc.get(k, 0) == 0 for k in zero) and acc['club_worlds'] == 8 and acc['player_worlds'] == 24,
          f'coherent world: every counter 0 ({ {k: acc[k] for k in zero if acc.get(k)} })')
    w = _clean_world()
    w['players']['H_WR'][0, E.SX['receptions']] = 0          # yards + TD with no catch, in world 0
    acc = _counts(w)
    check(acc['player_rec_yards_without_reception'] == 1 and acc['player_rec_td_without_reception'] == 1
          and acc['player_rec_td_gt_receptions'] == 1, f'one catchless 60-yd 2-TD line counted three ways ({dict(acc)})')
    w = _clean_world()
    w['players']['A_RB'][1, E.SX['carries']] = 0               # rush TD and yards with no carry
    acc = _counts(w)
    check(acc['player_rush_td_without_carry'] == 1 and acc['player_rush_yards_without_carry'] == 1
          and acc['player_rush_td_gt_carries'] == 1, 'a carryless rushing TD counted')
    w = _clean_world()
    w['players']['H_RB'][2, E.SX['receptions']] = 5             # 5 catches on 3 targets
    check(_counts(w)['player_receptions_gt_targets'] == 1, 'receptions > targets counted')
    w = _clean_world()
    w['club_td']['H'][3] = 4                                     # team TD 4 != 2 pass + 1 rush
    acc = _counts(w)
    check(acc['club_team_td_ne_pass_td_plus_rush_td'] == 1 and acc['club_points_lt_6_x_off_td'] == 1
          and acc['club_kicker_remainder_negative_if_every_xp_good'] == 1,
          f'4 TDs on 21 points: TD identity, points < 6 TD and kicker remainder all counted ({dict(acc)})')
    w = _clean_world()
    w['players']['A_QB'][0, E.SX['pass_yards']] = 95             # QB 95 vs receivers 80
    w['players']['A_QB'][1, E.SX['pass_td']] = 3                 # QB 3 pass TD vs receivers 2
    acc = _counts(w)
    check(acc['club_qb_pass_yards_ne_sum_rec_yards'] == 1 and acc['club_qb_pass_td_ne_sum_rec_td'] == 1
          and acc['club_team_td_ne_pass_td_plus_rush_td'] == 1, 'passer/receiver yard and TD mismatches counted')
    w = _clean_world()
    w['club_points']['H'][0] = 21.5                              # same DST tier (21-27) as 21
    acc = _counts(w)
    check(acc['club_points_not_integer'] == 1 and acc['club_dst_dk_ne_tier_plus_components'] == 0,
          'non-integer points counted (the opposing DST scored off 21.5 stays consistent: same tier)')
    w = _clean_world()
    w['dst_dk']['A'] = w['dst_dk']['A'] * 1.3                    # an anchor-style rescale
    check(_counts(w)['club_dst_dk_ne_tier_plus_components'] == 4, 'rescaled DST no longer equals tier + components')
    w = _clean_world()
    w['ints'] = {k: np.zeros(4) for k in w['players']}
    w['ints']['A_QB'][2] = 2                                     # A's QB throws 2 INT; H's defence has 1 takeaway
    acc = _counts(w)
    check(acc['club_opp_qb_ints_gt_dst_takeaways'] == 1 and acc['ints_present_club_worlds'] == 8,
          'opponent interceptions above the defence takeaways counted')
    hist = collections.Counter()
    fr = E.season_frames(2024)
    gids = sorted(fr['fin'].game_id)[:30]
    E.history_conservation(fr, gids, hist)
    check(hist['club_games'] == 60 and hist['player_rec_td_without_reception'] == 0
          and hist['club_points_lt_6_x_off_td'] == 0 and hist['club_opp_qb_ints_gt_dst_takeaways'] == 0,
          f'30 real 2024 games: no impossible event in history ({dict(hist)})')


# --------------------------------------------------------------------------------------------- G
def test_g_scoring_rules_against_reference():
    print('\nG. scoring rules against reference computations')
    rng = np.random.default_rng(11)
    X = rng.normal(size=(5, 50))
    y = rng.normal(size=5)
    ref = np.abs(X - y[:, None]).mean(1) - 0.5 * np.abs(X[:, :, None] - X[:, None, :]).mean((1, 2))
    check(np.allclose(E.crps_draws(X, y), ref), 'CRPS equals the brute-force pairwise estimator')
    check(np.allclose(E.crps_draws(np.full((1, 9), 3.0), np.array([5.0])), [2.0]), 'CRPS of a point mass is |x - y|')
    Z = rng.normal(size=(60, 1))
    check(abs(E.energy_score(Z, np.array([0.3])) - E.crps_draws(Z.T, np.array([0.3]))[0]) < 1e-12,
          'energy score in one dimension equals CRPS')
    Xv = np.tile(np.array([1.0, 4.0, 9.0]), (20, 1))
    check(E.variogram_score(Xv, np.array([1.0, 4.0, 9.0])) < 1e-12 and
          E.variogram_score(Xv, np.array([1.0, 4.0, 4.0])) > 0, 'variogram score: 0 at a matching vector, > 0 otherwise')
    Xc = np.array([[0, 0, 1, 1, 2, 2, 2, 3.0]])
    ls, fl = E.count_log_score(Xc, np.array([2.0]))
    ls5, fl5 = E.count_log_score(Xc, np.array([5.0]))
    check(abs(ls[0] + np.log(3 / 8)) < 1e-12 and not fl[0] and abs(ls5[0] + np.log(0.5 / 8)) < 1e-12 and fl5[0],
          'count log score: -log(3/8) on support, half-draw floor -log(0.5/8) off support, flagged')
    lam = 2.3
    Xp = rng.poisson(lam, size=(4000, 400)).astype(float)
    yp = rng.poisson(lam, size=4000).astype(float)
    u = E.randomized_pit(Xp, yp, np.random.default_rng(2))
    h = np.histogram(u, bins=10, range=(0, 1))[0] / len(u)
    check(np.abs(h - 0.1).max() < 0.02, f'randomized PIT of a calibrated discrete forecast is flat ({h.round(3)})')
    cov = E.central_coverage(Xp, yp, 0.8).mean()
    check(0.78 < cov < 0.95, f'80% central interval covers a calibrated discrete outcome >= nominal ({cov:.3f})')
    check(E.is_integral(Xc) and not E.is_integral(Xc + 0.5), 'integral-support detection')
    games = list(range(12))
    weeks = {g: g // 3 for g in games}
    Wb = E._boot_weights(games, weeks, np.random.default_rng(1))
    same = all(np.all(Wb['week'][:, [g for g in games if weeks[g] == k]] ==
                      Wb['week'][:, [[g for g in games if weeks[g] == k][0]]]) for k in range(4))
    check(same and np.all(Wb['game'].sum(1) == 12) and Wb['game'].shape == (E.N_BOOT, 12),
          'block bootstrap: one count per week block, G games per game-block resample')
    s = {'A': (np.arange(12.0), np.ones(12)), 'B': (np.arange(12.0) * 2, np.ones(12))}
    r = E.summarise_metric(s, games, weeks, Wb, 'A', 'B')
    check(abs(r['A_vs_B']['ratio'] - 0.5) < 1e-12 and r['A_vs_B']['ratio_ci95_game_block'][0] <= 0.5
          <= r['A_vs_B']['ratio_ci95_game_block'][1], 'paired ratio and its interval')
    ok, got = _raises(lambda: E.summarise_metric({'A': s['A'], 'B': (s['B'][0], np.r_[np.ones(11), 2.0])},
                                                 games, weeks, Wb, 'A', 'B'), 'SC_COH_1_CLEAN_UNPAIRED')
    check(ok, f'a comparison over different unit sets -> refused ({got})')


# --------------------------------------------------------------------------------------------- H
def test_h_smoke_in_sample_pipeline():
    print('\nH. smoke: the full scoring loop on two IN-SAMPLE 2024 games (not evidence)')
    if not E.FROZEN.exists():
        check(False, 'SC_COH_1_CLEAN_FROZEN.json missing: run `sc_coh_1_clean_eval.py freeze` first')
        return
    r = E.dry_run_in_sample(n_worlds=30, limit_games=2)
    check(r['n_games_scored'] == 2 and not r['games_refused'], f"2 games scored ({r['games_refused']})")
    c0 = r['conservation_counts_per_stage']['CANDIDATE']['S0_raw_library']
    ident = [k for k in E.CONSERVATION_CHECKS if k not in ('club_kicker_remainder_negative_if_every_xp_good',
                                                           'club_opp_qb_ints_gt_dst_takeaways')]
    check(all(c0.get(k, 0) == 0 for k in ident) and c0['club_worlds'] == 120,
          f'candidate S0: every accounting identity holds in every world ({ {k: c0[k] for k in ident if c0.get(k)} })')
    i0 = r['conservation_counts_per_stage']['INCUMBENT']['S0_raw_simulator']
    check(i0['club_points_not_integer'] > 0, 'incumbent S0: non-integer points are COUNTED, not hidden')
    i1 = r['conservation_counts_per_stage']['INCUMBENT']['S1_after_efficiency_worlds']
    check(i1['ints_present_club_worlds'] == 120, 'the efficiency stage adds interceptions and the INT check runs')
    pd_ = r['primary_decision']
    check(set(pd_) >= {'P1_energy_score', 'P2_variogram_score', 'P3_team_points_crps', 'P4_player_dk_crps'},
          'primary decision panel present')
    m = r['marginal']['player_dk']['crps']
    check(all(v in m for v in E.VARIANTS) and 'CANDIDATE_RAW_vs_INCUMBENT_PROD' in m, 'all four variants scored')
    check(r['marginal']['club_team_points']['log_score']['support_valid']['INCUMBENT_PROD'] is False,
          'continuous incumbent team points: count log score marked invalid, not computed')


def test_i_traded_player_in_both_pools_gets_separate_draws():
    print('\nI. regression (DEVIATIONS[0]): one player id in BOTH clubs\' pools -> two separate draw sets')
    def pool(extra):
        ps = [{'pid': f'QB{extra}', 'pos': 'QB', 'target_share': 0.0, 'carry_share': 0.1, 'pass_att_share': 1.0,
               'catch_rate': 0.65, 'eff': {'targets': 0, 'rec_yards': 0, 'carries': 5, 'rush_yards': 20,
                                           'pass_attempts': 100, 'pass_yards': 700}},
              {'pid': 'TRADED', 'pos': 'WR', 'target_share': 0.6, 'carry_share': 0.0, 'pass_att_share': 0.0,
               'catch_rate': 0.65, 'eff': {'targets': 40, 'rec_yards': 400, 'carries': 0, 'rush_yards': 0,
                                           'pass_attempts': 0, 'pass_yards': 0}},
              {'pid': f'RB{extra}', 'pos': 'RB', 'target_share': 0.4, 'carry_share': 0.9, 'pass_att_share': 0.0,
               'catch_rate': 0.75, 'eff': {'targets': 20, 'rec_yards': 150, 'carries': 60, 'rush_yards': 250,
                                           'pass_attempts': 0, 'pass_yards': 0}}]
        return {'players': ps, 'roles': {}, 'week': 10}
    pools = {('g', 'H'): pool('h'), ('g', 'A'): pool('a')}
    G_ = collections.namedtuple('G_', 'game_id week home away')('g', 10, 'H', 'A')
    spec = E.game_spec(G_, pools, {'total': 44.0, 'home_margin': 1.0, 'BASIS': 'FOOTBALL_ONLY_OWN_OFFENCE_BLEND'})
    ids = [p['id'] for c in spec['clubs'] for p in c['players']]
    check(len(ids) == len(set(ids)) and 'TRADED|H' in ids and 'TRADED|A' in ids, f'distinct keys per club ({ids})')
    from nfl.research.coherence import sc_coh_1_candidate as C

    def club(points):
        return {'n_att': 6, 'tgt_group': np.array([0, 0, 2, 2, 0]), 'tgt_cmp': np.array([1, 0, 1, 1, 1]),
                'tgt_yds': np.array([12.0, 0.0, 30.0, -2.0, 9.0]), 'tgt_td': np.array([0, 0, 1, 0, 1]),
                'run_qb': np.array([False, True, False, False]), 'run_yds': np.array([4.0, 7.0, -1.0, 22.0]),
                'run_td': np.array([1, 0, 0, 0]), 'points': points, 'dst': (2.0, 1.0, 0.0, 0.0, 0.0)}
    lib = E.CleanLibrary([{'game_id': 'x', 'season': 2023, 'fc_total': 44.0, 'fc_margin': 2.0,
                           'home': club(31.0), 'away': club(20.0)},
                          {'game_id': 'y', 'season': 2023, 'fc_total': 48.0, 'fc_margin': -3.0,
                           'home': club(24.0), 'away': club(28.0)}], (2023,))
    w = E.simulate_candidate(lib, {'targets': {'alpha': 30.0}, 'carries': {'alpha': 8.0}}, spec, 25, 4)
    w1 = E.stage_efficiency(w, {'H': pools[('g', 'H')], 'A': pools[('g', 'A')]}, 0.02, 5)
    shapes = {k: v.shape for k, v in w1['players'].items()}
    acc = collections.Counter()
    E.conservation(spec, w1, acc)
    check(all(s_ == (25, 10) for s_ in shapes.values()) and acc['club_worlds'] == 50,
          f'every key has exactly one draw set after the efficiency stage; conservation runs ({shapes})')
    _ = C


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed')


if __name__ == '__main__':
    for name, fn in sorted((k, v) for k, v in dict(globals()).items() if k.startswith('test_') and callable(v)):
        if name != 'test_zz_every_check_passed':
            fn()
    print(f'\n{PASSED} passed, {FAILED} failed')
    raise SystemExit(1 if FAILED else 0)
