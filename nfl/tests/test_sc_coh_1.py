#!/usr/bin/env python3.12
"""SC-COH-1: the shadow coherence candidate and its held-out measurement harness.

    python3.12 nfl/tests/test_sc_coh_1.py

  A  ACCOUNTING IDENTITIES in candidate draws, RECOMPUTED here from the returned stat lines (not by calling the
     candidate's own verify): passing yards == sum of receiving yards, passing TDs == sum of receiving TDs,
     receptions == completions, rec TD <= receptions, rush TD <= carries, team TD == pass TD + rush TD,
     points >= 6 x TD -- on a synthetic analogue and on a real 2024 library game.
  B  HELD-OUT SEPARATION: no fitted quantity may contain a 2025 row; every route that could put one there refuses
     with SC_COH_1_HELDOUT_LEAK, and pregame shares do not move when the evaluation week's outcome is changed.
  C  REFUSAL ON EMPTY INPUT with a named error, at every stage.
  D  ADVERSARIAL: the candidate's verify() is load-bearing (a seeded TD-on-an-incompletion is caught, and is NOT
     caught with verify bypassed); the incumbent audit counts a seeded violation; the statistic and the bootstrap
     agree with an independent reference computation.
"""
from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd

_REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))
from nfl.research.coherence import sc_coh_1_candidate as C  # noqa: E402
from nfl.research.coherence import sc_coh_1_measure as M  # noqa: E402
from nfl.tests.bypass import assert_guard_is_load_bearing  # noqa: E402

PASSED = FAILED = 0
G = C.GROUPS


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
    except M.CoherenceInputError as e:
        return e.code == code, e.code
    except Exception as e:  # noqa: BLE001
        return False, f'{type(e).__name__}: {e}'
    return False, 'no error'


def _club(points=24.0, td_on_incomplete=False):
    return {'n_att': 6,
            'tgt_group': np.array([G['WR'], G['WR'], G['TE'], G['RB'], G['ANY']]),
            'tgt_cmp': np.array([1, 0, 1, 1, 1]),
            'tgt_yds': np.array([12.0, 0.0, 30.0, -2.0, 9.0]),
            'tgt_td': np.array([0, 1 if td_on_incomplete else 0, 1, 0, 1]),
            'run_qb': np.array([False, True, False, False]),
            'run_yds': np.array([4.0, 7.0, -1.0, 22.0]), 'run_td': np.array([1, 0, 0, 0]),
            'points': points, 'dst': (2.0, 1.0, 0.0, 0.0, 0.0)}


def _lib(td_on_incomplete=False, season=2023):
    games = [{'game_id': f'{season}_01_A_B', 'season': season, 'total_line': 44.0, 'spread_line': 3.0,
              'home': _club(31.0, td_on_incomplete), 'away': _club(20.0, td_on_incomplete)},
             {'game_id': f'{season}_02_A_B', 'season': season, 'total_line': 49.0, 'spread_line': -2.5,
              'home': _club(24.0, td_on_incomplete), 'away': _club(28.0, td_on_incomplete)}]
    return C.Library(games, (season,))


CONC = {'targets': {'alpha': 30.0}, 'carries': {'alpha': 8.0}}


def _spec(empty=False, no_qb_share=False):
    def club(c):
        if empty:
            return {'club': c, 'players': [], 'dst_id': f'DST|{c}'}
        return {'club': c, 'dst_id': f'DST|{c}', 'players': [
            {'id': f'{c}QB', 'position': 'QB', 'target_share': 0.0, 'carry_share': 0.15,
             'pass_att_share': 0.0 if no_qb_share else 1.0},
            {'id': f'{c}WR1', 'position': 'WR', 'target_share': 0.35, 'carry_share': 0.0, 'pass_att_share': 0.0},
            {'id': f'{c}WR2', 'position': 'WR', 'target_share': 0.25, 'carry_share': 0.05, 'pass_att_share': 0.0},
            {'id': f'{c}TE1', 'position': 'TE', 'target_share': 0.25, 'carry_share': 0.0, 'pass_att_share': 0.0},
            {'id': f'{c}RB1', 'position': 'RB', 'target_share': 0.15, 'carry_share': 0.8, 'pass_att_share': 0.0}]}
    return {'total_line': 45.0, 'home_spread': 2.0, 'clubs': [club('HOM'), club('AWY')]}


def _identities(spec, w):
    """Independent recomputation of every football identity from the returned worlds. Returns {name: n_bad}."""
    bad = {k: 0 for k in ('pass_yds_eq_rec_yds', 'pass_td_eq_rec_td', 'rec_td_le_rec', 'rec_le_tgt',
                          'yds_only_on_rec', 'rush_td_le_car', 'team_td', 'points_ge_6td')}
    n = None
    for c in spec['clubs']:
        S = np.stack([np.asarray(w['stat_draws'][p['id']], float) for p in c['players']])
        n = S.shape[1]
        qb = np.array([p['position'] == 'QB' for p in c['players']])
        bad['pass_yds_eq_rec_yds'] += int((np.abs(S[qb, :, 1].sum(0) - S[~qb, :, 8].sum(0)) > 1e-9).sum())
        bad['pass_td_eq_rec_td'] += int((S[qb, :, 2].sum(0) != S[~qb, :, 9].sum(0)).sum())
        bad['rec_td_le_rec'] += int((S[..., 9] > S[..., 7]).sum())
        bad['rec_le_tgt'] += int((S[..., 7] > S[..., 6]).sum())
        bad['yds_only_on_rec'] += int(((np.abs(S[..., 8]) > 1e-9) & (S[..., 7] == 0)).sum())
        bad['rush_td_le_car'] += int((S[..., 5] > S[..., 3]).sum())
        td = np.asarray(w['club_td'][c['club']])
        bad['team_td'] += int((td != S[qb, :, 2].sum(0) + S[..., 5].sum(0)).sum())
        bad['points_ge_6td'] += int((np.asarray(w['club_points'][c['club']]) < 6 * td).sum())
    return bad, n


# ------------------------------------------------------------------------------------------------ A
def test_a1_identities_exact_on_synthetic_analogue():
    print('\nA1. accounting identities, synthetic analogue, recomputed independently')
    spec = _spec()
    w = C.simulate(_lib(), CONC, spec, 300, seed=7)
    bad, n = _identities(spec, w)
    check(n == 300, f'300 worlds returned (got {n})')
    for k, v in bad.items():
        check(v == 0, f'{k}: 0 violating worlds (got {v})')
    S = np.stack([np.asarray(w['stat_draws'][p['id']], float) for p in spec['clubs'][0]['players']])
    check(set(np.round(S[0, :, 1], 6)) == {49.0}, 'team passing yards in every world are the analogue\'s real 49 yds')
    check(set(S[:, :, 7].sum(0)) == {4.0}, 'receptions sum to the analogue\'s 4 completions in every world')
    wr1 = S[1, :, 6]
    check(wr1.std() > 0, f'targets are allocated, not fixed: WR1 target SD {wr1.std():.3f} > 0')
    check(set(np.asarray(w['club_points']['HOM'])) <= {31.0, 24.0}, 'points are a real analogue score')


def test_a2_identities_exact_on_real_2024_library_game():
    print('\nA2. accounting identities on a real 2024 library game and a real 2024 pregame pool')
    lib = C.build_library((2024,))
    conc = C.estimate_share_concentration((2024,))
    check(conc['targets']['state'] == 'ESTIMATED' and conc['carries']['state'] == 'ESTIMATED',
          f"both concentrations estimated on 2024 (targets {conc['targets'].get('alpha')}, "
          f"carries {conc['carries'].get('alpha')})")
    df = M.load_pbp(2024)
    plays = M.offensive_plays(df)
    pools = M.pregame_pools(2024, M.player_games(plays), M.snap_pool(2024))
    fin = M.finals(df)
    g = next(r for _, r in fin.iterrows() if (r.game_id, r.home) in pools and (r.game_id, r.away) in pools)
    spec = M.game_spec(g, pools)
    w = C.simulate(lib, conc, spec, 200, seed=11)
    bad, n = _identities(spec, w)
    check(n == 200 and sum(bad.values()) == 0, f'{g.game_id}: 0 identity violations over 200 worlds ({bad})')
    check(w['identity_checks_passed'] == 200 * 2 * 13, f"verify() ran 13 checks x 2 clubs x 200 worlds "
                                                        f"({w['identity_checks_passed']})")


# ------------------------------------------------------------------------------------------------ B
def test_b1_heldout_season_refused_everywhere():
    print('\nB1. held-out separation: 2025 cannot enter a fitted quantity')
    for seasons in ((2025,), (2024, 2025), (2021, 2026)):
        ok, got = _raises(lambda: C.build_library(seasons), 'SC_COH_1_HELDOUT_LEAK')
        check(ok, f'build_library{seasons} refuses SC_COH_1_HELDOUT_LEAK ({got})')
        ok, got = _raises(lambda: C.estimate_share_concentration(seasons), 'SC_COH_1_HELDOUT_LEAK')
        check(ok, f'estimate_share_concentration{seasons} refuses SC_COH_1_HELDOUT_LEAK ({got})')
    ok, got = _raises(lambda: _lib(season=2025), 'SC_COH_1_HELDOUT_LEAK')
    check(ok, f'a Library holding a 2025 game refuses at construction ({got})')
    lib = _lib()
    lib.max_season = 2025          # a library tampered after construction
    ok, got = _raises(lambda: C.simulate(lib, CONC, _spec(), 5, 1), 'SC_COH_1_HELDOUT_LEAK')
    check(ok, f'simulate refuses a library whose max season is 2025 ({got})')
    check(max(M.FIT_SEASONS) <= 2024 and M.EVAL_SEASON not in M.FIT_SEASONS and C.CONC_SEASON <= 2024,
          f'declared fit seasons {M.FIT_SEASONS}, concentration season {C.CONC_SEASON}, evaluation {M.EVAL_SEASON}')


def test_b2_real_library_and_concentration_contain_no_2025():
    print('\nB2. the real fitted objects carry no 2025 row')
    lib = C.build_library((2024,))
    ss = {g['season'] for g in lib.games}
    gids = {g['game_id'][:4] for g in lib.games}
    check(ss == {2024} and gids == {'2024'}, f'library seasons {sorted(ss)}, game-id prefixes {sorted(gids)}')
    check(len(lib.games) > 250, f'library is not partial: {len(lib.games)} games')
    conc = C.estimate_share_concentration((2024,))
    check(conc['season'] == 2024, f"concentration season {conc['season']}")


def test_b3_pregame_shares_do_not_see_the_evaluation_week():
    print('\nB3. pregame shares are a function of weeks < W only')

    def pg_with(week3_targets):
        rows = []
        for wk, (a, b) in enumerate([(8, 2), (6, 4), week3_targets], start=1):
            gid = f'2025_{wk:02d}_AAA_BBB'
            rows += [{'game_id': gid, 'season': 2025, 'week': wk, 'team': 'AAA', 'pid': 'W1', 'targets': a,
                      'carries': 0, 'pass_att': 0, 'receptions': a / 2},
                     {'game_id': gid, 'season': 2025, 'week': wk, 'team': 'AAA', 'pid': 'W2', 'targets': b,
                      'carries': 0, 'pass_att': 0, 'receptions': b / 2},
                     {'game_id': gid, 'season': 2025, 'week': wk, 'team': 'AAA', 'pid': 'R1', 'targets': 0,
                      'carries': 10, 'pass_att': 0, 'receptions': 0},
                     {'game_id': gid, 'season': 2025, 'week': wk, 'team': 'AAA', 'pid': 'Q1', 'targets': 0,
                      'carries': 1, 'pass_att': 30, 'receptions': 0}]
        return pd.DataFrame(rows)
    pool = pd.DataFrame([{'game_id': '2025_03_AAA_BBB', 'team': 'AAA', 'pid': p, 'pos': pos, 'offense_snaps': 50}
                         for p, pos in (('W1', 'WR'), ('W2', 'WR'), ('R1', 'RB'), ('Q1', 'QB'))])
    a = M.pregame_pools(2025, pg_with((1, 15)), pool)[('2025_03_AAA_BBB', 'AAA')]
    b = M.pregame_pools(2025, pg_with((30, 0)), pool)[('2025_03_AAA_BBB', 'AAA')]
    sa = {p['pid']: p['target_share'] for p in a['players']}
    sb = {p['pid']: p['target_share'] for p in b['players']}
    check(sa == sb, f'week-3 outcome changed, week-3 shares unchanged ({sa})')
    check(abs(sa['W1'] - 0.7) < 1e-12, f"W1 share = 14/20 from weeks 1-2 ({sa['W1']})")
    check(a['roles']['WR1'] == b['roles']['WR1'] == 'W1', 'WR1 is the prior-week leader, not the week-3 leader')


# ------------------------------------------------------------------------------------------------ C
def test_c1_refusal_on_empty_input():
    print('\nC1. refusal on empty input, named')
    ok, got = _raises(lambda: M.offensive_plays(pd.DataFrame(columns=M.PBP_COLS)), 'SC_COH_1_EMPTY_INPUT')
    check(ok, f'offensive_plays(empty) -> SC_COH_1_EMPTY_INPUT ({got})')
    ok, got = _raises(lambda: C.Library([], (2024,)), 'SC_COH_1_EMPTY_INPUT')
    check(ok, f'Library([]) -> SC_COH_1_EMPTY_INPUT ({got})')
    ok, got = _raises(lambda: C.build_library(()), 'SC_COH_1_EMPTY_INPUT')
    check(ok, f'build_library(()) -> SC_COH_1_EMPTY_INPUT ({got})')
    ok, got = _raises(lambda: C.simulate(_lib(), CONC, _spec(empty=True), 10, 1), 'SC_COH_1_EMPTY_INPUT')
    check(ok, f'simulate(club with no players) -> SC_COH_1_EMPTY_INPUT ({got})')
    ok, got = _raises(lambda: C.simulate(_lib(), CONC, _spec(), 0, 1), 'SC_COH_1_EMPTY_INPUT')
    check(ok, f'simulate(n_sims=0) -> SC_COH_1_EMPTY_INPUT ({got})')
    ok, got = _raises(lambda: C.simulate(_lib(), CONC, _spec(no_qb_share=True), 10, 1), 'SC_COH_1_NO_PASSER')
    check(ok, f'a club whose QBs have no attempt share -> SC_COH_1_NO_PASSER, not silent zeros ({got})')
    ok, got = _raises(lambda: M.pregame_pools(2025, pd.DataFrame(), pd.DataFrame()), 'SC_COH_1_EMPTY_INPUT')
    check(ok, f'pregame_pools(empty) -> SC_COH_1_EMPTY_INPUT ({got})')
    fin = pd.DataFrame([{'game_id': 'g', 'home': 'A', 'away': 'B', 'week': 3, 'total_line': 44, 'spread_line': 1}])
    ok, got = _raises(lambda: M.sim_units(lambda s, n, sd: {}, fin, {}, 5), 'SC_COH_1_EMPTY_INPUT')
    check(ok, f'sim_units with no replayable game -> SC_COH_1_EMPTY_INPUT ({got})')
    qb = {'pid': 'x', 'pos': 'QB', 'target_share': 0, 'carry_share': 1, 'pass_att_share': 1, 'catch_rate': .6}
    pools = {('g', 'A'): {'players': [qb], 'roles': {}}, ('g', 'B'): {'players': [], 'roles': {}}}
    empty_provider = lambda s, n, sd: {'stat_draws': {}, 'dst': {}, 'club_points': {}, 'club_td': {}}
    ok, got = _raises(lambda: M.sim_units(empty_provider, fin, pools, 5), 'SC_COH_1_EMPTY_DRAWS')
    check(ok, f'a provider that returns no draws -> SC_COH_1_EMPTY_DRAWS, never an empty table ({got})')
    ok, got = _raises(lambda: M.finals(pd.DataFrame([{'game_id': 'g', 'season': 2025, 'week': 1, 'home_team': 'A',
                                                       'away_team': 'B', 'home_score': None, 'away_score': 3,
                                                       'total_line': 40, 'spread_line': 1}])),
                      'SC_COH_1_FINALS_INCOMPLETE')
    check(ok, f'a game with no final score -> SC_COH_1_FINALS_INCOMPLETE ({got})')


# ------------------------------------------------------------------------------------------------ D
def test_d1_verify_is_load_bearing():
    print('\nD1. the candidate\'s verify() is load-bearing')

    def run():
        try:
            C.simulate(_lib(td_on_incomplete=True), CONC, _spec(), 50, seed=3)
        except M.CoherenceInputError as e:
            return e.code
        return None
    got = run()
    check(got == 'SC_COH_1_IDENTITY_VIOLATED', f'a TD on an incompletion in the analogue is refused ({got})')
    try:
        assert_guard_is_load_bearing(run=run, module_path='nfl.research.coherence.sc_coh_1_candidate',
                                     attr='verify', caught=lambda r: r == 'SC_COH_1_IDENTITY_VIOLATED', returns=0)
        check(True, 'with verify bypassed the same corrupt analogue passes silently -> the guard is what catches it')
    except AssertionError as e:
        check(False, f'verify is not load-bearing: {e}')


def test_d2_library_refuses_incoherent_plays():
    print('\nD2. the library refuses a pass TD without a completion')
    p = pd.DataFrame({'kind': ['pass', 'pass'], 'att': [1, 1], 'receiver': ['r1', 'r2'], 'cmp': [0, 1],
                      'recyds': [0.0, 10.0], 'ptd': [1, 0], 'rusher': [None, None], 'rushyds': [0.0, 0.0],
                      'rtd': [0, 0]})
    ok, got = _raises(lambda: C._club_plays(p, {}), 'SC_COH_1_LIBRARY_INCOHERENT')
    check(ok, f'_club_plays -> SC_COH_1_LIBRARY_INCOHERENT ({got})')


def test_d3_incumbent_audit_counts_a_seeded_violation():
    print('\nD3. the incumbent accounting audit counts what it claims to count')
    spec = {'clubs': [{'club': 'A', 'players': [{'id': 'q', 'position': 'QB'}, {'id': 'w', 'position': 'WR'}]}]}
    #            pa  pyd  ptd car ryd rtd tgt rec recyd rectd
    clean = {'q': [[30, 200, 1, 2, 10, 0, 0, 0, 0, 0]], 'w': [[0, 0, 0, 0, 0, 0, 8, 5, 200, 1]]}
    dirty = {'q': [[30, 200, 1, 2, 10, 1, 0, 0, 0, 0]], 'w': [[0, 0, 0, 0, 0, 0, 8, 0, 150, 1]]}
    for name, sd, want in (('clean', clean, 0), ('dirty', dirty, 1)):
        acc = {}
        w = {'club_td': {'A': [2]}, 'club_points': {'A': [14.0]}}
        M.audit_worlds(spec, {k: np.asarray(v, float) for k, v in sd.items()}, w, acc)
        check(acc['player_rec_td_gt_receptions'] == want and acc['player_rec_yards_without_reception'] == want
              and acc['pass_yards_ne_sum_rec_yards'] == want,
              f'{name} world: rec TD>rec {acc["player_rec_td_gt_receptions"]}, yards w/o rec '
              f'{acc["player_rec_yards_without_reception"]}, pass!=rec yds {acc["pass_yards_ne_sum_rec_yards"]} '
              f'(want {want} each)')
    acc = {}
    M.audit_worlds(spec, {k: np.asarray(v, float) for k, v in clean.items()},
                   {'club_td': {'A': [3]}, 'club_points': {'A': [14.5]}}, acc)
    check(acc['team_points_lt_6_x_off_td'] == 1 and acc['team_points_not_integer'] == 1
          and acc['team_td_ne_pass_plus_rush_td'] == 1, f'3 TDs on 14.5 points is counted three ways ({acc})')


def test_d4_statistic_and_bootstrap_match_reference():
    print('\nD4. sufficient-statistic correlation / slope and the block bootstrap against a reference')
    rng = np.random.default_rng(5)
    n = 300
    x = rng.normal(size=n)
    y = 0.4 * x + rng.normal(size=n)
    u = pd.DataFrame({'game_id': np.repeat(np.arange(n // 2), 2), 'x': x, 'y': y})
    games = sorted(set(u.game_id))
    T = M.suffstats(u, 'x', 'y', games).sum(0)
    check(abs(M._stat(T, 'corr') - np.corrcoef(x, y)[0, 1]) < 1e-12, 'corr equals numpy corrcoef')
    check(abs(M._stat(T, 'slope') - np.polyfit(x, y, 1)[0]) < 1e-12, 'slope equals numpy polyfit')
    u.loc[3, 'y'] = np.nan
    T2 = M.suffstats(u, 'x', 'y', games).sum(0)
    m = ~np.isnan(u.y.to_numpy())
    check(abs(M._stat(T2, 'corr') - np.corrcoef(x[m], u.y.to_numpy()[m])[0, 1]) < 1e-12,
          'a missing role is dropped from that statistic only, never read as zero')
    weeks = {g: g % 5 for g in games}
    Cw = M.boot_counts(games, weeks, 'week', np.random.default_rng(1))
    same = all(np.all(Cw[:, [i for i, g in enumerate(games) if weeks[g] == k]] ==
                      Cw[:, [[i for i, g in enumerate(games) if weeks[g] == k][0]]]) for k in range(5))
    check(same and Cw.shape == (M.N_BOOT, len(games)), 'week block: every game in a week gets the same resample count')
    Cg = M.boot_counts(games, weeks, 'game', np.random.default_rng(1))
    check(np.all(Cg.sum(1) == len(games)), 'game block: each resample draws exactly G games')


def test_d5_matching_assigns_every_play_once():
    print('\nD5. play-to-slot matching: every play exactly one owner, owner counts preserved, groups first')
    rng = np.random.default_rng(9)
    pg = np.array([0, 0, 1, 2, 0, 1, 4])
    owner = np.array([5, 5, 6, 7, 7, 5, 6])
    sg = np.array([0, 0, 1, 2, 2, 0, 1])
    got = C._match(pg, owner, sg, rng)
    check(sorted(got.tolist()) == sorted(owner.tolist()), f'owner multiset preserved ({got.tolist()})')
    pg2 = np.array([0, 0, 1, 1])
    own2 = np.array([1, 1, 2, 2])
    sg2 = np.array([0, 0, 1, 1])
    ok = all(np.array_equal(C._match(pg2, own2, sg2, np.random.default_rng(s)), np.array([1, 1, 2, 2]))
             for s in range(20))
    check(ok, 'when the group sizes match, every play goes to a same-group slot (20 seeds)')
    ok, got = _raises(lambda: C._match(np.array([0, 1]), np.array([1]), np.array([0]), rng), 'SC_COH_1_SLOT_MISMATCH')
    check(ok, f'plays != slots -> SC_COH_1_SLOT_MISMATCH ({got})')


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed')


if __name__ == '__main__':
    for name, fn in sorted((k, v) for k, v in dict(globals()).items() if k.startswith('test_') and callable(v)):
        if name != 'test_zz_every_check_passed':
            fn()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
