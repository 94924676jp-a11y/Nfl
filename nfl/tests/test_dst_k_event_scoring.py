"""DST and kicker DK points are an exact function of integer per-world events (shadow, default OFF; 2026-10-09).

The incumbent publishes non-integer DST scores in 92-98% of worlds because showdown_slate_run / classic_slate_run
rescale the already-scored integer DST draw by a multiplicative mean anchor (classic_slate_run.anchor_means). The
shadow scorer nfl/sim/dst_k_event_scoring.py rebuilds the DST from integer events instead. These checks hold it to:
every DST/K world score is a valid DK value, equals dk_scoring of its own components exactly, takes its points-allowed
tier from the opponent's simulated club points in the same world, and takes its interceptions from the opposing
quarterbacks' simulated interceptions in that world. Plus: nothing in production calls it, skill draws are untouched,
and a seeded violation of each identity is caught.
"""
import json
import pathlib
import random
import re
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))
from nfl.product import dk_scoring as DK  # noqa: E402
from nfl.sim import dst as dst_mod, dst_k_event_scoring as X  # noqa: E402
from nfl.tools import classic_slate_run as CR  # noqa: E402

PASSED = FAILED = 0
TB = _REPO / 'nfl/dfs/salaries/showdown_tb_dal/OFFICIAL'


def check(ok, msg):
    global PASSED, FAILED
    PASSED, FAILED = (PASSED + 1, FAILED) if ok else (PASSED, FAILED + 1)
    print('  ok  ' if ok else '  FAIL', msg)


def _row(dk=5.0, **items):
    base = {'sack': 2.4, 'fumble_recovery': 1.0, 'interception': 1.5, 'return_td': 0.65, 'safety': 0.05,
            'blocked_kick': 0.04, 'points_allowed': 0.5}
    base.update(items)
    return {'name': 'Test', 'team': 'TST', 'position': 'DST', 'dk_points': dk, 'dst': {'event_items': base}}


def _slate():
    d = json.loads(next(TB.glob('*_DRAWS.json')).read_text())
    p = json.loads(next(TB.glob('*_PROJ.json')).read_text())
    return d, {f"{r['name']}|{r['team']}": r for r in p['rows'].values()}


def test_default_off_and_not_imported_by_production():
    check(X.ENABLED is False, 'ENABLED is False')
    pat = re.compile(r'dst_k_event_scoring')
    users = []
    for f in _REPO.glob('nfl/**/*.py'):
        rel = f.relative_to(_REPO).as_posix()
        if rel.startswith(('nfl/research/', 'nfl/tests/')) or rel == 'nfl/sim/dst_k_event_scoring.py':
            continue
        if pat.search(f.read_text(errors='ignore')):
            users.append(rel)
    check(not users, f'no production module references the shadow scorer ({users})')


def test_points_allowed_integer_convention():
    got = X.points_allowed_integer([0.0, 0.3, 0.5, 0.51, 6.5, 6.51, 13.49, 20.5, 34.6, 0.0])
    check(got.tolist() == [0, 0, 0, 1, 6, 7, 13, 20, 35, 0], f'round half-down, clamp at 0 ({got.tolist()})')
    # the same convention as the DST projection's pa_expectation bucket edges (+-0.5, first match)
    from nfl.tools import dst_model
    for p in (0.5, 6.5, 13.5, 20.5, 27.5, 34.5, 7.2, 27.6):
        b = next(v for lo, hi, v in dst_model.PA_BUCKETS if p >= lo - 0.5 and (hi is None or p <= hi + 0.5))
        check(DK.dst_points(points_allowed=int(X.points_allowed_integer([p])[0])) == b,
              f'{p}: tier of the integer equals the projection bucket ({b})')


def test_incumbent_anchor_is_the_cause():
    d, rows = _slate()
    for k, compw in d['dst_components'].items():
        club = k.rsplit('|', 1)[1]
        opp = d['away'] if club == d['home'] else d['home']
        col = 0 if opp == d['world_points']['home'] else 1
        opp_pts = np.asarray(d['world_points']['points'], float)[:, col]
        c = np.asarray(compw, float)
        s0 = np.array([dst_mod.tier(p) for p in opp_pts]) + c[:, 0] + 2 * c[:, 1] + 6 * c[:, 2] + 2 * c[:, 3]
        pub = np.asarray(d['draws'][k], float)
        f = pub.mean() / s0.mean()
        check(X.is_integer_array(s0), f'{k}: the raw simulator DST draw is integer in every world')
        check(not X.is_integer_array(pub) and (np.abs(pub - np.round(pub)) > 1e-9).mean() > 0.9,
              f'{k}: the published draw is non-integer in >90% of worlds')
        check(float(np.abs(s0 * f - pub).max()) < 1e-9, f'{k}: published == raw x one factor ({f:.4f}) exactly')
    # and the anchor function itself turns an integer draw into non-integers
    out, _ = CR.anchor_means({'A|X': [0.0, 4.0, 7.0, 10.0]}, {'A|X': 3.3})
    check(not X.is_integer_array(out['A|X']), f'anchor_means rescales an integer DST draw to {out["A|X"]}')


def test_fixed_dst_identities_on_tb_dal():
    d, rows = _slate()
    params = X.load_params()
    for k in d['dst_components']:
        club = k.rsplit('|', 1)[1]
        opp = d['away'] if club == d['home'] else d['home']
        col = 0 if opp == d['world_points']['home'] else 1
        opp_pts = np.asarray(d['world_points']['points'], float)[:, col]
        ints = np.sum([np.asarray(v, float) for q, v in d['qb_interceptions'].items() if q.endswith('|' + opp)], 0)
        for mode in (X.MEAN_EVENTS, X.MEAN_PROJECTION):
            r = X.dst_event_worlds(opp_pts, ints, rows[k], params, seed=1, mean_mode=mode)
            c = r['components']
            check(X.valid_dst_values(r['dk']), f'{k} {mode}: every world score is an integer DK value >= -4')
            check(np.array_equal(r['dk'], X.dst_dk_from_components(c)),
                  f'{k} {mode}: every world equals dk_scoring.dst_points of its own components')
            tiers = np.array([DK.dst_points(points_allowed=int(p)) for p in c['points_allowed']])
            ref = np.array([next(v for lo, hi, v in __import__('nfl.tools.dst_model', fromlist=['x']).PA_BUCKETS
                                 if p >= lo - 0.5 and (hi is None or p <= hi + 0.5)) for p in opp_pts])
            check(np.array_equal(tiers, ref), f'{k} {mode}: points-allowed tier == the tier of the opponent\'s '
                                              f'club points in the same world, every world')
            check(np.array_equal(c['ints'], ints.astype(int)),
                  f'{k} {mode}: interceptions == the opposing QBs\' interceptions, every world')
            for f in ('sacks', 'fumble_recoveries', 'tds', 'safeties', 'blocked_kicks'):
                assert c[f].dtype.kind == 'i' and (c[f] >= 0).all()
            check(True, f'{k} {mode}: free components are non-negative integers')
            if mode == X.MEAN_PROJECTION and r['account']['state'] == 'PROJECTION_MEAN_REACHED':
                gap = abs(r['dk'].mean() - rows[k]['dk_points'])
                se = r['dk'].std(ddof=1) / np.sqrt(r['dk'].size)
                check(gap < 4 * se, f'{k}: PROJECTION arm mean {r["dk"].mean():.3f} within 4 MCSE of the projection '
                                    f'{rows[k]["dk_points"]:.3f}')


def test_skill_players_unmoved():
    d, rows = _slate()
    before = json.dumps({k: v for k, v in d['draws'].items() if k not in d['dst_components']}, sort_keys=True)
    params = X.load_params()
    for k in d['dst_components']:
        club = k.rsplit('|', 1)[1]
        opp = d['away'] if club == d['home'] else d['home']
        col = 0 if opp == d['world_points']['home'] else 1
        ints = np.sum([np.asarray(v, float) for q, v in d['qb_interceptions'].items() if q.endswith('|' + opp)], 0)
        d['draws'][k] = X.dst_event_worlds(np.asarray(d['world_points']['points'], float)[:, col], ints, rows[k],
                                           params, seed=2)['dk'].tolist()
    after = json.dumps({k: v for k, v in d['draws'].items() if k not in d['dst_components']}, sort_keys=True)
    check(before == after, 'replacing the DST draws leaves every skill-player and kicker draw byte-identical')


def test_projection_arm_reports_unreachable_rather_than_forcing():
    params = X.load_params()
    pts = np.full(500, 3.0)          # opponent held to 3: the 1-6 tier alone is worth +7
    r = X.dst_event_worlds(pts, np.ones(500), _row(dk=2.0), params, seed=3, mean_mode=X.MEAN_PROJECTION)
    check(r['account']['state'] == 'PROJECTION_MEAN_UNREACHABLE' and r['account']['multiplier_on_free_rates'] == 0.0,
          f'a projection below tier + interceptions is reported unreachable, m = 0 ({r["account"]["state"]})')
    check(X.valid_dst_values(r['dk']) and (r['dk'] == 9).all(), 'and the worlds stay valid: 7 tier + 2 per INT')


def test_seeded_violations_are_caught():
    params = X.load_params()
    r = X.dst_event_worlds(np.linspace(0, 45, 400), np.zeros(400), _row(), params, seed=4)
    bad = r['dk'].copy()
    bad[7] *= 0.5085
    check(not X.valid_dst_values(bad) or not np.array_equal(bad, X.dst_dk_from_components(r['components'])),
          'a rescaled world fails the component identity')
    check(not X.valid_dst_values([1.0, 3.5]), 'a half point is not a valid DK DST value')
    check(not X.valid_dst_values([-5.0]), 'below -4 is not a valid DK DST value')
    for args, name in (((np.full(5, 10.0), np.array([0, 1.5, 0, 0, 0]), _row()), 'non-integer interceptions'),
                       ((np.full(5, 10.0), np.zeros(4), _row()), 'interceptions of the wrong length'),
                       ((np.array([10.0, np.nan]), np.zeros(2), _row()), 'non-finite opponent points'),
                       ((np.full(5, 10.0), np.zeros(5), {'name': 'N', 'team': 'T', 'dst': {'event_items': {}}}),
                        'a DST row with no event rates')):
        try:
            X.dst_event_worlds(*args, params, seed=5)
            check(False, f'{name} refused')
        except X.ShadowRefused as e:
            check(True, f'{name} refused: {str(e)[:60]}')


def test_kicker_rescoring_matches_kicker_world():
    from nfl.tools import kicker_world as KW
    rng = random.Random(9)
    mix = {'made_mix': {'fg_0_39': 0.5, 'fg_40_49': 0.3, 'fg_50_plus': 0.2},
           'make_rate': {'fg_0_39': 0.95, 'fg_40_49': 0.8, 'fg_50_plus': 0.68}}
    rates = {'try_rate_2pt': 0.08, 'two_pt_success': 0.48, 'pat_make_rate': 0.955, 'fg_share': 0.9}
    dks, comp, xp = [], {b: [] for b in KW.BAND_POINTS}, []
    for _ in range(3000):
        pts = rng.uniform(0, 45)
        td = max(0, int(round((pts - 6) / 7)))
        dk, det = KW.draw(pts, td, mix, rates, rng)
        dks.append(dk)
        xp.append(det['xp_made'])
        for b in KW.BAND_POINTS:
            comp[b].append(det[f'{b}_made'])
    dks = np.asarray(dks, float)
    check(X.valid_kicker_values(dks), 'every kicker world score is a non-negative integer')
    check(np.array_equal(X.kicker_dk_from_components(comp, xp), dks),
          'kicker_world.draw == dk_scoring.kicker_points of its own components, every world')
    try:
        X.kicker_dk_from_components({'fg_60_plus': [1]}, [0])
        check(False, 'an unknown kicker band refused')
    except X.ShadowRefused:
        check(True, 'an unknown kicker band refused')
    check(not X.valid_kicker_values([3.0, 4.5]) and not X.valid_kicker_values([-1.0]),
          'a fractional or negative kicker score is not valid under rule A')


def test_published_kickers_are_integer():
    d, _ = _slate()
    for k in d['kickers']:
        check(X.valid_kicker_values(d['draws'][k]), f'{k}: the published Showdown kicker draw is valid DK values')


def test_distribution_against_history():
    h = json.loads(X.PARAMS.read_text())
    hist = h['dst_dk_rule_A']
    check(hist['integer_share'] == 1.0 and hist['n'] > 2000, f'history: {hist["n"]} club-games, all integer')
    d, rows = _slate()
    params = X.load_params()
    for k in d['dst_components']:
        club = k.rsplit('|', 1)[1]
        opp = d['away'] if club == d['home'] else d['home']
        col = 0 if opp == d['world_points']['home'] else 1
        ints = np.sum([np.asarray(v, float) for q, v in d['qb_interceptions'].items() if q.endswith('|' + opp)], 0)
        r = X.dst_event_worlds(np.asarray(d['world_points']['points'], float)[:, col], ints, rows[k], params, seed=6)
        sd = float(r['dk'].std(ddof=1))
        # unconditional league SD is an UPPER benchmark for a single matchup's conditional SD
        check(sd <= hist['sd'], f'{k}: fixed SD {sd:.2f} <= unconditional historical SD {hist["sd"]:.2f}')
        check(float(r['dk'].min()) >= -4 and float(r['dk'].max()) <= 60, f'{k}: support inside the DK range')


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for n, f in list(globals().items()):
        if n.startswith('test_') and n != 'test_zz_every_check_passed':
            f()
    print(f'{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
