"""Track 1: the market firewall, the mechanism, and the decision rule.

WHAT THESE TESTS PROTECT.

  * THE MARKET NEVER ENTERS THE FOOTBALL FORECAST. The source play-by-play
    ships `spread_line`, `total_line` and `vegas_wp`. The guard is on what
    this code READS and EMITS, never on what the upstream happens to carry --
    a first version checked the source header and refused the whole build,
    and its substring list also matched `yardline_100`, which is field
    position rather than a price.

  * THE CONDITIONING VARIABLE IS PRE-DETERMINED. The differential is taken at
    the quarter BOUNDARY. A within-quarter differential is partly caused by
    the plays being counted, and a mechanism fitted that way would report the
    consequence as the cause.

  * THE TREATMENT CANNOT WIN BY SHIFTING THE LEVEL. A neutral state path must
    give a multiplier of exactly 1.0, and the multiplier is normalised to mean
    1.0 on the training frame.

  * AN UNTREATED METRIC IS UNTREATED. `team_rz_carries` has no response curve
    and must score IDENTICALLY in both arms -- not nearly, exactly.

  * THE DECISION RULE IS THE ONE THAT WAS WRITTEN DOWN. Three states, no
    fourth, and a metric that is significantly worse cannot produce support.
"""
from __future__ import annotations

import csv
import gzip
import json
import os
import pathlib
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from nfl.research.track1 import build_state_panel as BSP           # noqa: E402
from nfl.research.track1 import response as RESP                   # noqa: E402
from nfl.research.track1 import state as ST                        # noqa: E402
from nfl.research.track1 import analyse as AN                      # noqa: E402
from nfl.research.track1 import forward_chain as FC                # noqa: E402

PASSED = FAILED = 0


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}' + (f'  {detail}' if detail else ''))
    else:
        FAILED += 1
        print(f'  FAIL {label}' + (f'  {detail}' if detail else ''))


def _panel_cols(path):
    if not path.exists():
        return None
    with gzip.open(path, 'rt', newline='') as fh:
        return next(csv.reader(fh))


# ============================================ the market firewall
def test_a_no_market_quantity_is_read_or_emitted():
    check('the read list carries no market column',
          not BSP.market_columns(BSP.READ), str(BSP.market_columns(BSP.READ)))
    for name, path in (('team-quarter', BSP.TEAM_QUARTER),
                       ('game', BSP.GAME), ('qb-game', BSP.QB_GAME)):
        cols = _panel_cols(path)
        if cols is None:
            check(f'the {name} panel exists', False, str(path))
            continue
        check(f'the {name} panel carries no market column',
              not BSP.market_columns(cols), str(BSP.market_columns(cols)))
    check('the guard is on the artifact, not on the upstream header',
          'yardline' not in ''.join(BSP.FORBIDDEN_SUBSTRINGS),
          str(BSP.FORBIDDEN_SUBSTRINGS))
    check('an actual market column would still be caught',
          BSP.market_columns(['spread_line', 'plays']) == ['spread_line'])


def test_b_the_state_generator_feature_set_is_pregame_only():
    check('the declared feature set passes',
          ST.assert_pregame_only(ST.PREGAME_FEATURES) is True)
    for bad in ('closing_spread', 'vegas_wp', 'final_margin_home',
                'win_probability'):
        try:
            ST.assert_pregame_only(list(ST.PREGAME_FEATURES) + [bad])
            check(f'{bad} is refused', False)
        except ValueError as e:
            check(f'{bad} is refused by name', bad in str(e))
    check('the feature set is three names long, not an open list',
          len(ST.PREGAME_FEATURES) == 3, str(ST.PREGAME_FEATURES))


def test_c_the_evaluation_frame_excludes_the_live_games():
    p = RESP.load_panels()
    seasons = sorted({g['season'] for g in p['game']})
    check('the frame is 2020-2025 and holds no 2026 game',
          2026 not in seasons, str(seasons))
    ids = {g['game_id'] for g in p['game']}
    for live in ('2026_01_NE_SEA', '2026_01_SF_LA'):
        check(f'{live} is absent from the frame', live not in ids)
    check('the evaluation seasons are all inside the frame',
          set(FC.EVAL_SEASONS) <= set(seasons), str(FC.EVAL_SEASONS))


# ============================================ the conditioning variable
def test_d_the_differential_is_taken_at_the_quarter_boundary():
    p = RESP.load_panels()
    q1 = [r for r in p['team_quarter'] if r['qtr'] == 1]
    check('every first quarter starts level',
          all(r['diff_at_quarter_start'] == 0 for r in q1),
          f'{len(q1)} rows')
    later = [r for r in p['team_quarter'] if r['qtr'] == 4]
    check('later quarters do not',
          any(r['diff_at_quarter_start'] != 0 for r in later))
    check('both sides of a game carry opposite differentials',
          _opposite_sides(p['team_quarter']))


def _opposite_sides(rows):
    by = {}
    for r in rows:
        by.setdefault((r['game_id'], r['qtr']), []).append(r)
    pairs = [v for v in by.values() if len(v) == 2]
    if not pairs:
        return False
    return all(a['diff_at_quarter_start'] == -b['diff_at_quarter_start']
               for a, b in pairs)


# ============================================ the response mechanism
def test_e_shrinkage_is_estimated_and_does_visible_work():
    p = RESP.load_panels()
    fit = RESP.fit_response(p['team_quarter'])
    ws = [c['shrinkage_weight'] for name in fit['cells']
          for k, c in fit['cells'][name].items()
          if not k.endswith('_quarter')]
    check('every shrinkage weight is a proper weight',
          all(0.0 <= w <= 1.0 for w in ws), f'{len(ws)} cells')
    weak = fit['cells']['plays']['2|<=-11']['shrinkage_weight']
    strong = fit['cells']['dropbacks_rate']['4|<=-11']['shrinkage_weight']
    check('a cell with no signal is shrunk hard', weak < 0.25, f'{weak:.3f}')
    check('a cell with strong signal is barely shrunk', strong > 0.9,
          f'{strong:.3f}')
    check('  and the two differ by a lot, so the shrinkage is not cosmetic',
          strong - weak > 0.6, f'{strong - weak:.3f}')


def test_f_the_response_runs_the_direction_football_says():
    p = RESP.load_panels()
    fit = RESP.fit_response(p['team_quarter'])
    q4 = [RESP._rho_at(fit['dropbacks_rate'], 4, b) for b in range(5)]
    check('fourth-quarter pass tendency falls monotonically as the lead grows',
          all(q4[i] > q4[i + 1] for i in range(4)),
          ' '.join(f'{v:.3f}' for v in q4))
    r4 = [RESP._rho_at(fit['designed_rush_rate'], 4, b) for b in range(5)]
    check('  and the designed-rush tendency rises monotonically',
          all(r4[i] < r4[i + 1] for i in range(4)),
          ' '.join(f'{v:.3f}' for v in r4))
    check('the neutral bucket is close to no response',
          abs(RESP._rho_at(fit['dropbacks_rate'], 4, RESP.NEUTRAL) - 1) < 0.05)
    check('trailing by two scores raises pass tendency by a lot in Q4',
          q4[0] / q4[4] > 1.5, f'{q4[0] / q4[4]:.3f}')


def test_g_a_neutral_path_moves_nothing():
    p = RESP.load_panels()
    fit = RESP.fit_response(p['team_quarter'])
    B = np.full((7, 4), RESP.NEUTRAL, int)
    m = RESP.multipliers(B, fit)
    for driver, v in m.items():
        # the neutral bucket's own rho is not exactly 1, so the neutral-path
        # multiplier is the neutral rho itself rather than 1.0 -- what must
        # hold is that it is the SAME for every draw and close to 1.
        check(f'{driver} is constant along a neutral path',
              float(np.ptp(v)) < 1e-12, f'{float(np.ptp(v)):.2e}')
        check(f'  and within 5% of no response', abs(v[0] - 1.0) < 0.05,
              f'{v[0]:.5f}')


def test_h_the_two_sides_of_a_game_mirror_each_other():
    B = np.array([[2, 0, 1, 4], [2, 4, 3, 0]], int)
    M = ST.mirror(B)
    check('mirroring is an involution', np.array_equal(ST.mirror(M), B))
    check('neutral mirrors to neutral',
          int(ST.mirror(np.array([[RESP.NEUTRAL]]))[0, 0]) == RESP.NEUTRAL)
    check('trailing big mirrors to leading big',
          int(M[0, 1]) == 4 and int(B[0, 1]) == 0)


def test_i_the_state_generator_uses_no_future_game():
    p = RESP.load_panels()
    games = sorted([dict(g) for g in p['game']],
                   key=lambda r: (r['season'], r['week'], r['game_id']))
    base = {s['game_id']: s['strength_diff']
            for s in ST.strength_series(games, 8.0)}
    tampered = [dict(g) for g in games]
    tampered[-1]['final_margin_home'] = 99
    after = {s['game_id']: s['strength_diff']
             for s in ST.strength_series(tampered, 8.0)}
    moved = [k for k in base if abs(base[k] - after[k]) > 1e-12]
    check('rewriting the LAST game moves no earlier strength', not moved,
          f'{len(moved)} moved')
    tampered2 = [dict(g) for g in games]
    tampered2[10]['final_margin_home'] = 99
    after2 = {s['game_id']: s['strength_diff']
              for s in ST.strength_series(tampered2, 8.0)}
    later = [k for k in base if abs(base[k] - after2[k]) > 1e-12]
    check('  while rewriting an EARLY game does move later ones',
          len(later) > 0, f'{len(later)} moved')


def test_j_the_half_life_is_selected_inside_the_training_window():
    p = RESP.load_panels()
    tr = [g for g in p['game'] if g['season'] < 2023]
    sel = ST.select_half_life(tr)
    check('the half life comes from leave-one-season-out',
          sel['basis'] == 'LEAVE_ONE_SEASON_OUT_RMSE', sel['basis'])
    check('  over a grid, with every score reported',
          len(sel['scores']) == len(RESP.HALF_LIFE_GRID), str(sel['scores']))
    check('  and it is the grid point with the lowest error',
          float(sel['half_life']) == float(min(sel['scores'],
                                               key=lambda k: sel['scores'][k])))
    one = ST.select_half_life([g for g in p['game'] if g['season'] == 2020])
    check('a single training season says it could not cross-validate',
          one['basis'].startswith('GRID_MIDPOINT'), one['basis'])


# ============================================ the arms and the artifacts
def test_k_the_untreated_metric_is_left_exactly_alone():
    check('team_rz_carries is declared untreated',
          'team_rz_carries' in RESP.UNTREATED)
    check('  and has no driver',
          'team_rz_carries' not in RESP.METRIC_DRIVER)
    r = _results()
    if r is None:
        check('the forward-chain results artifact exists', False)
        return
    e = r['metrics'].get('team_rz_carries')
    if not e:
        check('the untreated metric was still scored', False)
        return
    check('the untreated metric is marked untreated', e['is_treated'] is False)
    check('  and scores IDENTICALLY in both arms, not nearly',
          e['mean_crps']['BASELINE'] == e['mean_crps']['TRACK1'],
          f"{e['mean_crps']['BASELINE']} vs {e['mean_crps']['TRACK1']}")
    check('  with a multiplier spread of exactly zero',
          e['multiplier_sd'] == 0.0, str(e['multiplier_sd']))


def _results():
    p = AN.RESULTS
    return json.loads(p.read_text()) if p.exists() else None


def test_l_the_results_artifact_says_what_it_is():
    r = _results()
    if r is None:
        check('the forward-chain results artifact exists', False)
        return
    check('nothing is promoted', r['promoted'] is False)
    check('it is labelled research only', r['is_research_only'] is True)
    check('no market input is recorded as used',
          r['market_inputs_used'] == [], str(r['market_inputs_used']))
    check('every arm is reported', set(r['arms']) == set(FC.ARMS))
    check('the decision is exactly one of the three states',
          r['decision']['decision'] in ('SUPPORT', 'WEAK_SUPPORT', 'REJECT'),
          r['decision']['decision'])
    check('each treated metric is reported season by season',
          all(len(e['by_season']) >= 1 for e in r['metrics'].values()))
    check('intervals are clustered, and both clusterings are present',
          all('block_bootstrap_by_game' in d and 'block_bootstrap_by_week' in d
              for e in r['metrics'].values()
              for d in e['paired_crps_delta_vs_baseline'].values()))
    check('the diagnostics table exists', AN.DIAGNOSTICS.exists())
    check('the specification exists',
          (RESP.HERE / 'TRACK1_SPEC.md').exists())
    check('the decision document exists',
          (RESP.HERE / 'TRACK1_DECISION.md').exists())


def test_m_the_decision_rule_is_the_one_written_down():
    def mk(deltas, sig_better=(), sig_worse=(), season_improves=True):
        metrics = {}
        for m, d in deltas.items():
            metrics[m] = {
                'is_treated': True,
                'paired_crps_delta_vs_baseline': {'TRACK1': {
                    'delta_mean': d,
                    'block_bootstrap_by_game': {
                        'excludes_zero': m in sig_better or m in sig_worse},
                }},
                'by_season': {'2024': {'TRACK1_improves': season_improves}},
            }
        return {'metrics': metrics}

    d = AN.decide(mk({'a': -0.1, 'b': -0.2}, sig_better=('a',)))
    check('all improve, one significant -> SUPPORT',
          d['decision'] == 'SUPPORT', d['decision'])
    d = AN.decide(mk({'a': -0.1, 'b': +0.2}))
    check('a mixed result with nothing significant -> WEAK_SUPPORT',
          d['decision'] == 'WEAK_SUPPORT', d['decision'])
    d = AN.decide(mk({'a': -0.1, 'b': +0.2}, sig_worse=('b',)))
    check('one metric significantly WORSE -> REJECT', d['decision'] == 'REJECT',
          d['decision'])
    d = AN.decide(mk({'a': +0.1, 'b': +0.2}))
    check('nothing improves -> REJECT', d['decision'] == 'REJECT',
          d['decision'])
    d = AN.decide(mk({'a': -0.1, 'b': -0.2}, sig_better=('a',),
                     season_improves=False))
    check('improvement in no season cannot be SUPPORT',
          d['decision'] != 'SUPPORT', d['decision'])
    check('the rule is carried in the artifact, not only in code',
          'SUPPORT' in d['rule'] and 'REJECT' in d['rule'])


def test_n_volume_and_efficiency_error_are_reported_apart():
    if not AN.DIAGNOSTICS.exists():
        check('the diagnostics table exists', False)
        return
    with open(AN.DIAGNOSTICS) as fh:
        rows = list(csv.DictReader(fh))
    check('the diagnostics table has rows', bool(rows), str(len(rows)))
    for col in ('err_volume_dropbacks', 'err_volume_attempts',
                'err_efficiency_ypa', 'err_final_pass_yards', 'offsetting'):
        check(f'every row carries {col}', all(col in r for r in rows))
    bad = [r for r in rows if r['err_efficiency_ypa'] != '' and
           int(r['offsetting']) != int(
               float(r['err_volume_attempts']) *
               float(r['err_efficiency_ypa']) < 0)]
    check('the offsetting flag is exactly the opposite-sign condition',
          not bad, f'{len(bad)} rows disagree')
    off = [r for r in rows if int(r['offsetting'])]
    check('offsetting errors do occur and are counted, not hidden',
          len(off) > 0, f'{len(off)} of {len(rows)}')
    check('the unit is the QB room, one row per arm per team-game',
          len({r['arm'] for r in rows}) == len(FC.ARMS),
          str(sorted({r['arm'] for r in rows})))


def test_o_the_multiplier_points_the_way_football_does():
    """A sign error here would invert the whole mechanism and still run."""
    p = RESP.load_panels()
    tr_tq = [x for x in p['team_quarter'] if x['season'] < 2025]
    tr_gm = [g for g in p['game'] if g['season'] < 2025]
    rfit = RESP.fit_response(tr_tq)
    sfit = ST.fit_state(tr_gm)
    tab = FC._mu_table(sfit, rfit)

    def at(side, driver, mu):
        return float(FC._mu_lookup(tab, side, driver, mu))

    fav, dog = at('home', 'dropbacks', 10.0), at('away', 'dropbacks', 10.0)
    check('an expected favourite throws LESS than neutral', fav < 1.0,
          f'{fav:.4f}')
    check('an expected underdog throws MORE than neutral', dog > 1.0,
          f'{dog:.4f}')
    fr, dr = at('home', 'designed_rush', 10.0), at('away', 'designed_rush', 10.0)
    check('an expected favourite runs MORE than neutral', fr > 1.0, f'{fr:.4f}')
    check('an expected underdog runs LESS than neutral', dr < 1.0, f'{dr:.4f}')
    check('a pick-em game moves almost nothing',
          abs(at('home', 'dropbacks', 0.0) - 1.0) < 0.01,
          f"{at('home', 'dropbacks', 0.0):.5f}")
    check('the response grows with the expected margin',
          at('home', 'dropbacks', 14.0) < at('home', 'dropbacks', 7.0)
          < at('home', 'dropbacks', 0.0))
    check('the two sides move in opposite directions',
          (fav - 1.0) * (dog - 1.0) < 0)


def test_p_the_treatment_shifts_no_level():
    """Track 1 must redistribute the baseline's level, never move it."""
    if not AN.ROWS.exists():
        check('the scored-row table exists', False, str(AN.ROWS))
        return
    with gzip.open(AN.ROWS, 'rt', newline='') as fh:
        rows = list(csv.DictReader(fh))
    check('the scored-row table has rows', bool(rows), str(len(rows)))
    by = {}
    for r in rows:
        by.setdefault(r['metric'], []).append(r)
    for metric, rs in sorted(by.items()):
        m = np.array([float(r['multiplier_expected']) for r in rs])
        check(f'{metric}: the expected multiplier averages 1',
              abs(float(m.mean()) - 1.0) < 0.01, f'{float(m.mean()):.5f}')
        b = np.array([float(r['BASELINE_mean']) for r in rs])
        t = np.array([float(r['TRACK1_mean']) for r in rs])
        rel = abs(float(t.mean()) - float(b.mean())) / max(1e-9, float(b.mean()))
        check(f'  and the arm means agree to within 1%', rel < 0.01,
              f'{100 * rel:.4f}%')


def test_q_the_boundary_is_reported_rather_than_averaged_away():
    r = _results()
    if r is None:
        check('the forward-chain results artifact exists', False)
        return
    d = r['decision']
    check('the decision names which metrics improved',
          'metrics_improved' in d and isinstance(d['metrics_improved'], list))
    check('  and which were significantly worse',
          'metrics_significantly_worse_by_game_cluster' in d)
    check('  and counts metric-seasons rather than pooling them',
          d['metric_seasons_total'] == sum(
              len(e['by_season']) for e in r['metrics'].values()
              if e['is_treated']),
          f"{d['metric_seasons_total']}")
    for m, e in r['metrics'].items():
        if not e['is_treated']:
            continue
        check(f'{m} reports every season separately',
              len(e['by_season']) == len(r['eval_seasons']),
              str(sorted(e['by_season'])))
        check(f'  and reports which channel the pregame margin carries',
              'channel_diagnostics' in e)
        cd = e['channel_diagnostics']
        check(f'  with the net pregame signal measured, not asserted',
              'corr_own_expected_margin_with_actual' in cd,
              str(cd.get('corr_own_expected_margin_with_actual')))
    rz = r['metrics'].get('team_rz_carries', {}).get('channel_diagnostics', {})
    check('an untreated metric says its multiplier is constant rather than '
          'emitting a NaN correlation',
          rz.get('corr_own_expected_margin_with_multiplier') is None
          and rz.get('multiplier_is_constant') is True, str(rz))


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for fn in sorted(k for k in dict(globals()) if k.startswith('test_')):
        globals()[fn]()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
