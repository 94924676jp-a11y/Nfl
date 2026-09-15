"""H1 step 4: score the residuals. Nothing here chooses anything.

Every cut, every margin, every clustering choice and every band was fixed in
`H1_PREREGISTRATION.md` before the first residual was computed. This module
reads that file's decisions and applies them.

CLUSTERING. The game is the primary cluster: two quarterbacks in one game
share an opponent, a script and a weather. Every interval is a BLOCK BOOTSTRAP
OVER WHOLE GAMES, 2,000 resamples, seed 20260915. A team-clustered bootstrap
is reported alongside. No naive standard error is computed anywhere.

EXPLORATORY. 2025 is development data in this project.
"""
from __future__ import annotations

import collections
import csv
import gzip
import json
import math
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[4]
for _q in (str(_REPO), str(_REPO / 'nfl' / 'research' / 'qb2'),
           str(_REPO / 'nfl' / 'research' / 'v3' / 'h1')):
    if _q not in sys.path:
        sys.path.insert(0, _q)

import qb2_lib as Q                                               # noqa: E402
import h1_frame as FR                                             # noqa: E402

HERE = _REPO / 'nfl' / 'research' / 'v3' / 'h1'
ROWS = HERE / 'H1_RESIDUALS.csv.gz'
SUMMARY = HERE / 'H1_SUMMARY.json'

B = 2000
BOOT_SEED = 20260915

# predeclared, H1_PREREGISTRATION section 4
MARGIN = {
    'qb_passing_yards': 5.0,
    'qb_dropbacks': 0.5,
    'qb_attempts': 0.5,
    'cmp_per_attempt': 0.010,
    'yards_per_completion': 0.25,
}
COVERAGE_MARGIN = 0.03

FLOATS = ('pred_mean', 'pred_sd', 'pred_p10', 'pred_p50', 'pred_p90',
          'actual', 'error', 'z', 'crps', 'pit', 'own_weight')
INTS = ('season', 'week', 'home', 'h_games', 'realised_db', 'realised_att',
        'realised_cmp', 'team_db', 'team_plays', 'n_qb_in_team_game',
        'below_p10', 'below_p50', 'below_p90', 'in_p10_p90')


def load():
    with gzip.open(ROWS, 'rt', newline='') as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        raise SystemExit('H1_RESIDUALS_EMPTY')
    for r in rows:
        for k in FLOATS:
            r[k] = float(r[k])
        for k in INTS:
            r[k] = int(r[k])
        r['realised_pyds'] = float(r['realised_pyds'])
    return rows


# --------------------------------------------------------------- bootstrap
def cluster_boot(rows, stat, cluster='game_id', b=B, seed=BOOT_SEED):
    """Block bootstrap over whole clusters. Returns the resample distribution."""
    by = collections.defaultdict(list)
    for r in rows:
        by[r[cluster]].append(r)
    keys = list(by)
    if len(keys) < 2:
        return None, keys
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(keys), size=(b, len(keys)))
    out = np.empty(b)
    blocks = [by[k] for k in keys]
    for j in range(b):
        pool = []
        for i in idx[j]:
            pool.extend(blocks[i])
        out[j] = stat(pool)
    return out, keys


def _mean_error(rs):
    return float(np.mean([r['error'] for r in rs]))


def ci(dist, level=0.95):
    a = (1 - level) / 2
    return [float(np.percentile(dist, 100 * a)),
            float(np.percentile(dist, 100 * (1 - a)))]


def tost(point, dist, margin):
    """Two one-sided tests against a PREDECLARED margin, bootstrap SE."""
    se = float(np.std(dist, ddof=1))
    if se <= 0:
        return {'margin': margin, 'se': se, 'verdict': 'UNDEFINED_ZERO_SE'}
    t_lo = (point + margin) / se
    t_hi = (margin - point) / se
    p_lo = 0.5 * math.erfc(t_lo / math.sqrt(2))
    p_hi = 0.5 * math.erfc(t_hi / math.sqrt(2))
    p = max(p_lo, p_hi)
    ci90 = [float(np.percentile(dist, 5)), float(np.percentile(dist, 95))]
    inside = (-margin < ci90[0]) and (ci90[1] < margin)
    return {'margin': margin, 'clustered_se': se, 'p_tost': p,
            'ci90': ci90, 'equivalence_ci90_inside_margin': bool(inside),
            'verdict': ('EQUIVALENT_WITHIN_MARGIN' if (p < 0.05 and inside)
                        else 'NOT_SHOWN_EQUIVALENT')}


def moments(x):
    a = np.asarray(x, float)
    a = a[np.isfinite(a)]
    if len(a) < 2:
        return None
    mu, sd = float(a.mean()), float(a.std(ddof=1))
    z = (a - mu) / sd if sd > 0 else a * 0
    return {'n': int(len(a)), 'mean': mu, 'sd': sd,
            'skew': float((z ** 3).mean()),
            'excess_kurtosis': float((z ** 4).mean() - 3.0),
            'p01': float(np.percentile(a, 1)),
            'p10': float(np.percentile(a, 10)),
            'p50': float(np.percentile(a, 50)),
            'p90': float(np.percentile(a, 90)),
            'p99': float(np.percentile(a, 99))}


def layer_summary(rs):
    e = np.array([r['error'] for r in rs], float)
    z = np.array([r['z'] for r in rs], float)
    pit = np.array([r['pit'] for r in rs], float)
    h, _ = np.histogram(pit, bins=10, range=(0, 1))
    exp = len(pit) / 10.0
    d_game, gk = cluster_boot(rs, _mean_error, 'game_id')
    d_team, tk = cluster_boot(rs, _mean_error, 'team')
    out = {
        'n': len(rs),
        'n_game_clusters': len(gk), 'n_team_clusters': len(tk),
        'mean_signed_error': float(e.mean()),
        'mae': float(np.abs(e).mean()),
        'rmse': float(np.sqrt((e ** 2).mean())),
        'mean_actual': float(np.mean([r['actual'] for r in rs])),
        'mean_pred': float(np.mean([r['pred_mean'] for r in rs])),
        'sd_actual': float(np.std([r['actual'] for r in rs], ddof=1)),
        'sd_pred_mean': float(np.std([r['pred_mean'] for r in rs], ddof=1)),
        'mean_pred_sd': float(np.mean([r['pred_sd'] for r in rs])),
        'pearson_r': (float(np.corrcoef(
            [r['pred_mean'] for r in rs], [r['actual'] for r in rs])[0, 1])
            if np.std([r['pred_mean'] for r in rs]) > 0 else None),
        'mean_crps': float(np.mean([r['crps'] for r in rs])),
        'calibration_slope': None, 'calibration_intercept': None,
        'standardized_residual': moments(z),
        'pit_kind': rs[0]['pit_kind'],
        'pit_hist10': h.tolist(),
        'pit_chi2': float((((h - exp) ** 2) / exp).sum()),
        'pit_df': 9,
        'coverage_p10_below': float(np.mean([r['below_p10'] for r in rs])),
        'coverage_p50_below': float(np.mean([r['below_p50'] for r in rs])),
        'coverage_p90_below': float(np.mean([r['below_p90'] for r in rs])),
        'coverage_p10_p90': float(np.mean([r['in_p10_p90'] for r in rs])),
        'mean_error_ci95_game_clustered': ci(d_game),
        'mean_error_ci95_team_clustered': ci(d_team),
        'mean_error_se_game_clustered': float(np.std(d_game, ddof=1)),
        'mean_error_se_team_clustered': float(np.std(d_team, ddof=1)),
    }
    xx = np.array([r['pred_mean'] for r in rs], float)
    yy = np.array([r['actual'] for r in rs], float)
    if xx.std(ddof=1) > 0:
        A = np.vstack([xx, np.ones(len(xx))]).T
        sl, ic = np.linalg.lstsq(A, yy, rcond=None)[0]
        out['calibration_slope'] = float(sl)
        out['calibration_intercept'] = float(ic)
        out['sd_ratio_pred_over_actual'] = float(
            xx.std(ddof=1) / yy.std(ddof=1)) if yy.std(ddof=1) > 0 else None
    for nm, lvl, key in (('p10', 0.10, 'below_p10'),
                         ('p50', 0.50, 'below_p50'),
                         ('p90', 0.90, 'below_p90')):
        d, _ = cluster_boot(
            rs, lambda x, k=key: float(np.mean([r[k] for r in x])), 'game_id')
        out[f'coverage_{nm}_ci95_game_clustered'] = ci(d)
        out[f'coverage_{nm}_tost'] = tost(
            float(np.mean([r[key] for r in rs])) - lvl, d - lvl,
            COVERAGE_MARGIN)
    lay = rs[0]['layer']
    if lay in MARGIN:
        out['mean_error_tost'] = tost(float(e.mean()), d_game, MARGIN[lay])
    return out


# ------------------------------------------------------------------- cuts
def build_cuts():
    """Fifteen predeclared cuts, every one from pregame-known information."""
    rows, _ = FR.build()
    Q.attach(rows)
    by_team = collections.defaultdict(list)
    for r in sorted(rows, key=lambda x: x['ord']):
        by_team[r['team']].append(r)
    # team-game level series, strictly earlier
    tg = {}
    for r in rows:
        tg[(r['team'], r['ord'])] = r
    team_games = sorted({(r['team'], r['ord']) for r in rows})
    seq = collections.defaultdict(list)
    for t, o in team_games:
        seq[t].append(o)

    # per team-game context
    ctx = {}
    for (t, o) in team_games:
        r = tg[(t, o)]
        ctx[(t, o)] = {
            'season': r['season'], 'week': r['week'],
            'pf': r['points_for'], 'pa': r['points_against'],
            'rush_plays': r['team_rush_plays'],
            'rush_yards': r['team_rush_yards'],
            'opponent': r['opponent'],
            'sacks_allowed': r['team_sacks_allowed'],
            'team_db': r['team_db']}

    def prior(team, ordn, season, field_num, field_den, prev_season_ok=True):
        """Strictly earlier within the season; prior season as the week-1
        fallback. Never the current game."""
        num = den = 0.0
        for o in seq[team]:
            if o >= ordn:
                break
            c = ctx[(team, o)]
            if c['season'] == season:
                num += c[field_num]
                den += c[field_den]
        if den > 0:
            return num / den
        if not prev_season_ok:
            return None
        num = den = 0.0
        for o in seq[team]:
            c = ctx[(team, o)]
            if c['season'] == season - 1:
                num += c[field_num]
                den += c[field_den]
        return (num / den) if den > 0 else None

    def prior_ppg_diff(team, ordn, season):
        n = 0
        pf = pa = 0.0
        for o in seq[team]:
            if o >= ordn:
                break
            c = ctx[(team, o)]
            if c['season'] == season:
                pf += c['pf']; pa += c['pa']; n += 1
        if n:
            return (pf - pa) / n
        pf = pa = 0.0
        n = 0
        for o in seq[team]:
            c = ctx[(team, o)]
            if c['season'] == season - 1:
                pf += c['pf']; pa += c['pa']; n += 1
        return ((pf - pa) / n) if n else None

    def prior_def_sack_rate(team, ordn, season):
        """Sacks this DEFENCE recorded over dropbacks it faced. Both sides come
        from the opponent's own offensive row in the same game."""
        s = d = 0.0
        for o in seq[team]:
            if o >= ordn:
                break
            c = ctx[(team, o)]
            if c['season'] != season:
                continue
            oc = ctx.get((c['opponent'], o))
            if oc:
                s += oc['sacks_allowed']; d += oc['team_db']
        if d > 0:
            return s / d
        s = d = 0.0
        for o in seq[team]:
            c = ctx[(team, o)]
            if c['season'] != season - 1:
                continue
            oc = ctx.get((c['opponent'], o))
            if oc:
                s += oc['sacks_allowed']; d += oc['team_db']
        return (s / d) if d > 0 else None

    # player-level role history
    pteam = collections.defaultdict(set)
    plast = {}
    feat = {}
    prev_primary = {}
    for r in sorted(rows, key=lambda x: (x['ord'], x['team'], x['gsis_id'])):
        key = (r['game_id'], r['team'], r['gsis_id'])
        t, o, s = r['team'], r['ord'], r['season']
        # games this team played since this QB's last appearance
        last = plast.get(r['gsis_id'])
        gap = None
        if last is not None:
            gap = sum(1 for oo in seq[t] if last < oo < o)
        feat[key] = {
            'week': r['week'], 'season': s, 'home': r['home'],
            'h_games': r['h_games'],
            'fav_proxy': (lambda a, b: (a - b) if (a is not None
                                                   and b is not None) else None)(
                prior_ppg_diff(t, o, s), prior_ppg_diff(r['opponent'], o, s)),
            'own_ypc_rush': prior(t, o, s, 'rush_yards', 'rush_plays'),
            'opp_rush_allowed': prior(r['opponent'], o, s, 'rush_yards',
                                      'rush_plays'),
            'opp_def_sack_rate': prior_def_sack_rate(r['opponent'], o, s),
            'new_team': int(t not in pteam[r['gsis_id']]),
            'qb_returning': int(bool(gap)),
            'new_starter': int(prev_primary.get(t) not in (None, r['gsis_id'])),
        }
        pteam[r['gsis_id']].add(t)
        plast[r['gsis_id']] = o
        if r['qb_ord'] == 1:
            prev_primary[t] = r['gsis_id']
    if not feat:
        raise SystemExit('H1_CUT_FEATURES_EMPTY')
    return feat


def tertiles(vals):
    a = np.array([v for v in vals if v is not None], float)
    return float(np.percentile(a, 100 / 3)), float(np.percentile(a, 200 / 3))


CUT_ORDER = [
    'week_1', 'weeks_2_4', 'weeks_5_plus',
    'fav_proxy_top_third', 'fav_proxy_bottom_third',
    'own_rush_strong_top_third', 'opp_run_defence_strong_top_third',
    'opp_sack_rate_top_third', 'opp_sack_rate_bottom_third',
    'qb_returning_after_missed_game', 'new_team', 'new_starter',
    'own_history_1_to_3_games', 'own_history_17_plus_games', 'home',
]


def assign_cuts(rs, feat):
    fav = tertiles([feat[(r['game_id'], r['team'], r['gsis_id'])]['fav_proxy']
                    for r in rs])
    own = tertiles([feat[(r['game_id'], r['team'], r['gsis_id'])]['own_ypc_rush']
                    for r in rs])
    opd = tertiles([feat[(r['game_id'], r['team'],
                          r['gsis_id'])]['opp_rush_allowed'] for r in rs])
    sk = tertiles([feat[(r['game_id'], r['team'],
                         r['gsis_id'])]['opp_def_sack_rate'] for r in rs])
    for r in rs:
        f = feat[(r['game_id'], r['team'], r['gsis_id'])]
        c = {}
        c['week_1'] = f['week'] == 1
        c['weeks_2_4'] = 2 <= f['week'] <= 4
        c['weeks_5_plus'] = f['week'] >= 5
        c['fav_proxy_top_third'] = (f['fav_proxy'] is not None
                                    and f['fav_proxy'] >= fav[1])
        c['fav_proxy_bottom_third'] = (f['fav_proxy'] is not None
                                       and f['fav_proxy'] <= fav[0])
        c['own_rush_strong_top_third'] = (f['own_ypc_rush'] is not None
                                          and f['own_ypc_rush'] >= own[1])
        c['opp_run_defence_strong_top_third'] = (
            f['opp_rush_allowed'] is not None
            and f['opp_rush_allowed'] <= opd[0])
        c['opp_sack_rate_top_third'] = (f['opp_def_sack_rate'] is not None
                                        and f['opp_def_sack_rate'] >= sk[1])
        c['opp_sack_rate_bottom_third'] = (f['opp_def_sack_rate'] is not None
                                           and f['opp_def_sack_rate'] <= sk[0])
        c['qb_returning_after_missed_game'] = bool(f['qb_returning'])
        c['new_team'] = bool(f['new_team'])
        c['new_starter'] = bool(f['new_starter'])
        c['own_history_1_to_3_games'] = 1 <= f['h_games'] <= 3
        c['own_history_17_plus_games'] = f['h_games'] >= 17
        c['home'] = bool(f['home'])
        r['_cuts'] = c
    return {'fav_proxy_tertiles': fav, 'own_ypc_rush_tertiles': own,
            'opp_rush_allowed_tertiles': opd,
            'opp_def_sack_rate_tertiles': sk}


def holm(pvals):
    order = sorted(range(len(pvals)), key=lambda i: pvals[i])
    n = len(pvals)
    adj = [0.0] * n
    run = 0.0
    for k, i in enumerate(order):
        v = min(1.0, (n - k) * pvals[i])
        run = max(run, v)
        adj[i] = run
    return adj


def cut_tests(rs, layer):
    sub = [r for r in rs if r['layer'] == layer]
    res = []
    for name in CUT_ORDER:
        a = [r for r in sub if r['_cuts'][name]]
        b = [r for r in sub if not r['_cuts'][name]]
        if len(a) < 10 or len(b) < 10:
            res.append({'cut': name, 'n_in': len(a), 'n_out': len(b),
                        'status': 'TOO_SMALL_NOT_TESTED'})
            continue

        def diff(pool):
            ia = [r for r in pool if r['_cuts'][name]]
            ib = [r for r in pool if not r['_cuts'][name]]
            if not ia or not ib:
                return float('nan')
            return (float(np.mean([r['error'] for r in ia]))
                    - float(np.mean([r['error'] for r in ib])))

        d, gk = cluster_boot(sub, diff, 'game_id')
        d = d[np.isfinite(d)]
        point = diff(sub)
        p = 2 * min(float((d <= 0).mean()), float((d >= 0).mean()))
        p = min(1.0, max(p, 1.0 / len(d)))
        res.append({
            'cut': name, 'n_in': len(a), 'n_out': len(b),
            'mean_error_in': float(np.mean([r['error'] for r in a])),
            'mean_error_out': float(np.mean([r['error'] for r in b])),
            'difference': point,
            'ci95_game_clustered': ci(d),
            'p_nominal_game_clustered': p,
            'n_game_clusters': len(gk),
            'status': 'TESTED'})
    tested = [r for r in res if r['status'] == 'TESTED']
    adj = holm([r['p_nominal_game_clustered'] for r in tested])
    for r, a in zip(tested, adj):
        r['p_holm'] = a
        r['significant_holm_0.05'] = bool(a < 0.05)
    return {
        'layer': layer,
        'n_cuts_declared': len(CUT_ORDER),
        'n_cuts_tested': len(tested),
        'expected_nominally_significant_under_null': 0.05 * len(tested),
        'n_nominally_significant': sum(
            1 for r in tested if r['p_nominal_game_clustered'] < 0.05),
        'n_significant_after_holm': sum(
            1 for r in tested if r.get('significant_holm_0.05')),
        'multiplicity': 'Holm-Bonferroni across every tested cut',
        'cuts': res}


# ----------------------------------------------------- the located outcomes
def locate(rs, forecast, outcome, half=25.0, widen=40.0, min_n=30):
    sub = [r for r in rs if r['layer'] == 'qb_passing_yards']
    band = [r for r in sub if abs(r['pred_mean'] - forecast) <= half]
    used = half
    if len(band) < min_n:
        band = [r for r in sub if abs(r['pred_mean'] - forecast) <= widen]
        used = widen
    if not band:
        raise SystemExit(f'H1_LOCATE_EMPTY_BAND: {forecast}')
    err = forecast - outcome
    be = np.array([r['error'] for r in band], float)
    ae = np.array([r['error'] for r in sub], float)
    sd = float(np.mean([r['pred_sd'] for r in band]))
    bz = np.array([r['z'] for r in sub], float)
    bz = bz[np.isfinite(bz)]
    return {
        'status': 'HYPOTHETICAL -- supplied to the task by the user and '
                  'verified against nothing in this repository',
        'stated_forecast': forecast, 'stated_outcome': outcome,
        'implied_signed_error_over_projection': err,
        'band_half_width_used': used,
        'n_in_band': len(band),
        'band_mean_pred_sd': sd,
        'standardized_residual_at_band_sd': err / sd if sd > 0 else None,
        'percentile_of_error_within_band': float((be < err).mean() * 100),
        'percentile_of_error_in_full_2025_frame': float((ae < err).mean() * 100),
        'freq_band_error_at_least_this_large_same_direction':
            float((be >= err).mean()),
        'n_band_error_at_least_this_large': int((be >= err).sum()),
        'freq_full_frame_error_at_least_this_large_same_direction':
            float((ae >= err).mean()),
        'n_full_frame_error_at_least_this_large': int((ae >= err).sum()),
        'percentile_of_standardized_residual_in_full_frame':
            float((bz < (err / sd if sd > 0 else 0)).mean() * 100),
        'band_mean_signed_error': float(be.mean()),
        'band_sd_signed_error': float(be.std(ddof=1)) if len(be) > 1 else None,
    }


def joint_same_game(rs, a=61.0, b=79.0):
    """How often did BOTH primary passers in one 2025 game over-project this
    far? The question one game cannot answer, asked of 268 of them."""
    sub = [r for r in rs if r['layer'] == 'qb_passing_yards']
    by = collections.defaultdict(list)
    for r in sub:
        by[r['game_id']].append(r)
    two = [v for v in by.values() if len(v) == 2]
    if not two:
        raise SystemExit('H1_NO_TWO_QB_GAMES')
    both = either = both_a = 0
    for v in two:
        e = sorted([v[0]['error'], v[1]['error']], reverse=True)
        both += int(e[0] >= b and e[1] >= a)
        both_a += int(e[1] >= a)
        either += int(e[0] >= a)
    x = np.array([v[0]['error'] for v in two])
    y = np.array([v[1]['error'] for v in two])
    xx, yy = np.concatenate([x, y]), np.concatenate([y, x])
    return {
        'n_games_with_both_primary_passers_eligible': len(two),
        'n_games_total': len(by),
        'thresholds_over_projection': {'larger': b, 'smaller': a},
        'n_games_one_over_by_larger_and_other_by_smaller': both,
        'freq_games_one_over_by_larger_and_other_by_smaller': both / len(two),
        'n_games_both_over_by_smaller': both_a,
        'freq_games_both_over_by_smaller': both_a / len(two),
        'n_games_at_least_one_over_by_smaller': either,
        'freq_games_at_least_one_over_by_smaller': either / len(two),
        'within_game_correlation_of_the_two_errors':
            float(np.corrcoef(xx, yy)[0, 1]),
    }


def league_drift():
    """The team-volume layers are near-constant forecasts. Their 2025 bias is
    a league level shift, and that is measured rather than asserted."""
    with gzip.open(_REPO / 'nfl' / 'research' / 'inputs' /
                   'denom_panel.csv.gz', 'rt', newline='') as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        raise SystemExit('H1_DENOM_PANEL_EMPTY')
    out = {}
    for k in ('team_off_snaps', 'team_dropbacks_part'):
        per = {s: float(np.mean([int(r[k]) for r in rows
                                 if r['season'] == s]))
               for s in sorted({r['season'] for r in rows})}
        tr = float(np.mean([int(r[k]) for r in rows if r['season'] != '2025']))
        te = float(np.mean([int(r[k]) for r in rows if r['season'] == '2025']))
        out[k] = {'per_season_mean': per, 'mean_2020_2024': tr,
                  'mean_2025': te, 'training_minus_2025': tr - te}
    return out


def main():
    rs = load()
    feat = build_cuts()
    tert = assign_cuts(rs, feat)
    layers = sorted({r['layer'] for r in rs})
    summ = {}
    for L in layers:
        sub = [r for r in rs if r['layer'] == L]
        if not sub:
            raise SystemExit(f'H1_LAYER_EMPTY: {L}')
        summ[L] = layer_summary(sub)
    cuts = {L: cut_tests(rs, L)
            for L in ('qb_passing_yards', 'qb_dropbacks', 'qb_attempts',
                      'cmp_per_attempt', 'yards_per_completion')}
    out = {
        'artifact': 'NFL_H1_SUMMARY',
        'spec_version': 'h1-analyse-1',
        'status': 'EXPLORATORY -- 2025 is development data in this project; '
                  'this is not a confirmatory result and may not be quoted as '
                  'prospective performance',
        'preregistration': 'nfl/research/v3/h1/H1_PREREGISTRATION.md',
        'clustering': {'primary': 'game', 'secondary': 'team',
                       'method': 'block bootstrap over whole clusters',
                       'resamples': B, 'seed': BOOT_SEED,
                       'naive_se_reported': False},
        'metrics_refused': {
            'log_score_passing_yards':
                'not computed -- a sample-based log score on a continuous '
                'quantity needs a bandwidth, which is itself a free parameter'},
        'n_scored_rows': len(rs),
        'n_qb_games': len({(r['game_id'], r['gsis_id']) for r in rs}),
        'n_games': len({r['game_id'] for r in rs}),
        'tertile_boundaries': tert,
        'layers': summ,
        'cuts': cuts,
        'joint_same_game_2025': joint_same_game(rs),
        'league_volume_drift': league_drift(),
        'multiplicity_across_all_tested_cuts': None,
        'located_outcomes': {
            'hypothetical_184_on_forecast_245': locate(rs, 245.0, 184.0),
            'hypothetical_131_on_forecast_210': locate(rs, 210.0, 131.0)},
    }
    flat = [(L, x['cut'], x['p_nominal_game_clustered'])
            for L, c in cuts.items() for x in c['cuts']
            if x['status'] == 'TESTED']
    adj = holm([t[2] for t in flat])
    out['multiplicity_across_all_tested_cuts'] = {
        'n_tests': len(flat),
        'note': 'Holm within each layer is reported in `cuts`. This block '
                'applies Holm across EVERY tested cut on EVERY layer, which '
                'is the stricter and more honest family. The cuts overlap '
                'heavily (weeks_5_plus and own_history_17_plus_games share '
                'most of their rows), so neither correction is exact.',
        'expected_nominally_significant_under_null': 0.05 * len(flat),
        'n_nominally_significant': sum(1 for t in flat if t[2] < 0.05),
        'surviving': [{'layer': L, 'cut': c, 'p_nominal': pn, 'p_holm': a}
                      for (L, c, pn), a in zip(flat, adj) if a < 0.05]}
    SUMMARY.write_text(json.dumps(out, indent=1, default=float) + '\n')
    return out


if __name__ == '__main__':
    o = main()
    for L in ('team_offensive_plays', 'team_dropbacks_qb2',
              'qb_dropback_share', 'qb_dropbacks', 'qb_attempts',
              'att_per_dropback', 'cmp_per_attempt', 'yards_per_completion',
              'ptd_per_attempt', 'int_per_attempt',
              'scr_per_rush_opportunity', 'qb_passing_yards'):
        s = o['layers'][L]
        print(f"{L:28s} n={s['n']:4d} bias={s['mean_signed_error']:+9.4f} "
              f"ci=[{s['mean_error_ci95_game_clustered'][0]:+8.4f},"
              f"{s['mean_error_ci95_game_clustered'][1]:+8.4f}] "
              f"mae={s['mae']:8.4f} rmse={s['rmse']:8.4f} "
              f"cov10-90={s['coverage_p10_p90']:.3f}")
