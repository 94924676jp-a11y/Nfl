"""Q8 step 2: the one repair the audit licensed, forward-chained.

    python3.12 -m nfl.research.q8.repair

ONE CHANGE. The frozen P4B team-target point estimate is shrunk toward the
training league mean by an OLS slope fitted on strictly earlier seasons, and
the residual pool is recomputed around the new centre so the width stays
honest. Everything else is byte-identical across arms: the union frame,
production R8 appearance, the class prior, the shrinkage weight, the
redistribution rule, the receiving efficiency, the touchdown layer, the draw
count, the seed and the random stream.

WHY THIS AND NOTHING ELSE. `Q8_ATTRIBUTION_AUDIT.md` ranks five sources by
exact Shapley over 32 oracle subsets. The class prior, the shrinkage weight
and the redistribution rule carry under 5 % of the movement on every value
function. The appearance channel carries the bias and is fixed to production
R8 by directive -- and, per the audit's first finding, that bias is
substantially a selection artefact of scoring a marginal forecast on an
appeared-only population. The budget carries 91.5 % of the player-target CRPS
movement, and its calibration slope is below 1 in every season.

A GAIN IN BIAS IS NOT A GAIN. The audit showed that bias on the appeared-only
population is largely mechanical, so the decision reads CRPS and `decide`
refuses to call an arm supported on coverage or bias alone.
"""
from __future__ import annotations

import argparse
import collections
import csv
import gzip
import json
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
for _q in (str(_REPO), str(_REPO / 'nfl' / 'research' / 'p4b')):
    if _q not in sys.path:
        sys.path.insert(0, _q)

import p4b_volume as V                                            # noqa: E402
from nfl.research.q6 import frame as Q6F                          # noqa: E402
from nfl.research.q6 import forward_chain as Q6C                  # noqa: E402
from nfl.research.q7 import panel as Q7P                          # noqa: E402
from nfl.research.q8 import audit as AUD                          # noqa: E402

SPEC_VERSION = 'q8-repair-budget-shrink-1'
HERE = _REPO / 'nfl' / 'research' / 'q8'
RESULTS = HERE / 'Q8_FORWARD_CHAIN_RESULTS.json'
DIAGNOSTICS = HERE / 'Q8_DIAGNOSTICS.csv'
ROWS = HERE / 'Q8_REPAIR_ROWS.csv.gz'

ARMS = ('BASELINE', 'Q8_BUDGET_SHRINK')
EVAL_SEASONS = AUD.EVAL_SEASONS
N_DRAWS = 400
SEED = 20260918
BOOT = 1000
BOOT_SEED = 20260919


def budget_arms(denom, season):
    """Both budgets, from the same frozen P4B point. One fitted parameter.

    `beta` is the OLS slope of realised team targets on the frozen point over
    seasons strictly earlier than the one being forecast. The residual pool is
    recomputed around the shrunk centre, because a spread fitted around a
    different centre is not this predictive distribution's spread.
    """
    point, resid, est = AUD.budget_model(denom, season)
    cut = season * 100
    hist = [r for r in denom if r['ord'] < cut and r['team_targets'] > 0]
    if len(hist) < 100:
        return ({'BASELINE': (point, resid), 'Q8_BUDGET_SHRINK': (point, resid)},
                {'basis': 'TOO_LITTLE_HISTORY_NO_SHRINK', 'beta': 1.0,
                 'estimator': est})
    p = np.array([point[(r['season'], r['week'], r['team'])] for r in hist],
                 float)
    y = np.array([r['team_targets'] for r in hist], float)
    m = float(p.mean())
    X = np.column_stack([np.ones(len(p)), p])
    beta_vec, *_ = np.linalg.lstsq(X, y, rcond=None)
    beta = float(beta_vec[1])
    shrunk = {k: m + beta * (v - m) for k, v in point.items()}
    resid2 = np.array([r['team_targets'] -
                       shrunk[(r['season'], r['week'], r['team'])]
                       for r in hist], float)
    return ({'BASELINE': (point, resid),
             'Q8_BUDGET_SHRINK': (shrunk, resid2)},
            {'basis': 'OLS_SLOPE_ON_STRICTLY_EARLIER_SEASONS',
             'beta': round(beta, 5), 'league_mean': round(m, 4),
             'intercept': round(float(beta_vec[0]), 4),
             'estimator': est, 'n_training_team_games': len(hist),
             'residual_sd_baseline': round(float(resid.std(ddof=1)), 4),
             'residual_sd_shrunk': round(float(resid2.std(ddof=1)), 4)})


def _crps(draws, y):
    return float(V.crps_samples(np.asarray(draws, float).reshape(1, -1),
                                np.array([float(y)]))[0])


def run(eval_seasons=EVAL_SEASONS, n_draws=N_DRAWS, seed=SEED, progress=True):
    rows, _ = Q6F.load_frame()
    rows = Q6F.attach_role_class(rows)
    rows, _ = Q6F.attach_opportunity(rows)
    rows = AUD._own_history(rows)
    q7_recv = Q7P.load_recv()
    rows, join_ev = AUD.attach_receiving(rows, q7_recv)
    p_r8 = AUD.load_p_r8()
    denom = AUD.load_denom()

    out_rows, team_rows, fit_log = [], [], []
    for Y in eval_seasons:
        train = [r for r in rows if r['s'] < Y]
        test = [r for r in rows if r['s'] == Y]
        if not train or not test:
            continue
        cm_fit = AUD._class_means(train)
        k_fit, _ = Q6C._share_k(train, 'targets')
        eff = AUD.efficiency_fit(q7_recv, Y)
        budgets, bud_ev = budget_arms(denom, Y)
        Q6C.role_base(rows, 'targets', k_fit, cm_fit)
        vac, _ = Q6C.fit_vacancy(train, 'targets')

        groups = collections.defaultdict(list)
        for r in test:
            groups[(r['s'], r['w'], r['t'])].append(r)

        for gkey, g in sorted(groups.items()):
            den = int(g[0]['den_targets'])
            if den <= 0:
                continue
            own = np.array([r['own_share'] if r['own_share'] is not None
                            else AUD._class_of(cm_fit, r) for r in g], float)
            n_own = np.array([r['own_n'] for r in g], float)
            cls = np.array([AUD._class_of(cm_fit, r) for r in g], float)
            pv = np.array([p_r8.get((r['s'], r['w'], r['t'], r['pid']), 0.0)
                           for r in g], float)
            w = np.where(n_own > 0, n_own / (n_own + k_fit), 0.0)
            base = np.maximum(w * own + (1 - w) * cls, 0.0)
            cls_idx = [r['role_class'] for r in g]
            starter_i = [j for j, r in enumerate(g)
                         if r['role_class'] == 'starter']
            y_tgt = np.array([float(r['targets']) for r in g], float)
            y_yds = np.array([float(r['q7_yds']) for r in g], float)
            y_share = np.array([(r['share_targets']
                                 if r.get('share_targets') is not None else 0.0)
                                for r in g], float)

            for arm in ARMS:
                point, resid = budgets[arm]
                rng = np.random.default_rng(
                    [seed, Y, gkey[1], AUD._stream(gkey[2])])
                A = rng.binomial(1, np.clip(pv, 0.0, 1.0),
                                 size=(n_draws, len(g)))
                W = np.tile(base, (n_draws, 1)) * A
                if starter_i:
                    out_any = (A[:, starter_i] == 0).any(axis=1)
                    boost = np.array([float(vac.get(c, 1.0)) for c in cls_idx])
                    W = np.where(out_any.reshape(-1, 1), W * boost, W)
                tot = W.sum(axis=1, keepdims=True)
                P = np.divide(W, tot, out=np.zeros_like(W), where=tot > 0)
                pp = float(point.get(gkey, den))
                budget = np.maximum(np.rint(
                    pp + resid[rng.integers(0, len(resid), n_draws)]),
                    0).astype(int)
                ok = (P.sum(axis=1) > 0) & (budget > 0)
                T = np.zeros(P.shape)
                if ok.any():
                    Q = P[ok] / P[ok].sum(axis=1, keepdims=True)
                    for u, row in enumerate(np.where(ok)[0]):
                        T[row] = rng.multinomial(int(budget[row]), Q[u])
                YD = AUD._yards(T, eff, rng)
                team_rows.append({
                    'season': Y, 'week': gkey[1], 'team': gkey[2], 'arm': arm,
                    'team_game': f'{Y}-{gkey[1]}-{gkey[2]}',
                    'actual_team_targets': den,
                    'pred_team_targets': round(pp, 4),
                    'budget_error': round(pp - den, 4),
                    'budget_crps': round(_crps(budget, den), 5),
                })
                for j, r in enumerate(g):
                    st = AUD._strata(r, y_tgt[j], pv[j])
                    d = T[:, j]
                    out_rows.append({
                        'season': Y, 'week': r['w'], 'team': r['t'],
                        'pid': r['pid'], 'pos': r['pos'],
                        'role_class': r['role_class'], 'arm': arm,
                        'team_game': f"{Y}-{r['w']}-{r['t']}",
                        'appeared': int(r['appeared']),
                        'rc2_population': int(bool(r['appeared'])
                                              and (r['own_n'] or 0) >= 1),
                        'appearance_certainty': st['appearance_certainty'],
                        'target_regime': st['regime'],
                        'actual_targets': y_tgt[j],
                        'pred_targets': round(float(d.mean()), 5),
                        'target_crps': round(_crps(d, y_tgt[j]), 5),
                        'target_pit': round(float((d < y_tgt[j]).mean() +
                                                  0.5 * (d == y_tgt[j]).mean()),
                                            5),
                        'p_zero_targets': round(float((d <= 0).mean()), 5),
                        'is_zero_actual': int(y_tgt[j] == 0),
                        'actual_share': round(float(y_share[j]), 6),
                        'pred_share': round(float(base[j] /
                                                  max(base.sum(), 1e-12)), 6),
                        'actual_rec_yards': y_yds[j],
                        'pred_rec_yards': round(float(YD[:, j].mean()), 4),
                        'rec_yard_crps': round(_crps(YD[:, j], y_yds[j]), 5),
                        **{f'cov{L}': int(
                            float(np.percentile(d, (100 - L) / 2)) <= y_tgt[j]
                            <= float(np.percentile(d, 100 - (100 - L) / 2)))
                           for L in (50, 80, 90, 95)},
                    })
        fit_log.append({'eval_season': Y, 'n_test': len(test),
                        'budget': bud_ev, 'k_fitted': round(k_fit, 5),
                        'catch_rate': round(eff['catch_rate'], 5)})
        if progress:
            print(f"  {Y}: {len(test)} rows, beta {bud_ev['beta']}", flush=True)
    return {'rows': out_rows, 'team': team_rows, 'fit_log': fit_log,
            'receiving_join_evidence': join_ev}


# ------------------------------------------------------------- scoring
def boot_paired(diffs, clusters, n=BOOT, seed=BOOT_SEED):
    diffs = np.asarray(diffs, float)
    if not len(diffs):
        return None
    idx = collections.defaultdict(list)
    for i, c in enumerate(clusters):
        idx[c].append(i)
    pos = [np.asarray(v, int) for v in idx.values()]
    rng = np.random.default_rng(seed)
    out = np.empty(n)
    for b in range(n):
        pick = rng.integers(0, len(pos), size=len(pos))
        out[b] = diffs[np.concatenate([pos[j] for j in pick])].mean()
    lo, hi = np.percentile(out, [2.5, 97.5])
    return {'mean': round(float(diffs.mean()), 6),
            'ci_lo': round(float(lo), 6), 'ci_hi': round(float(hi), 6),
            'n_clusters': len(pos), 'n_rows': int(len(diffs)),
            'excludes_zero': bool(lo > 0 or hi < 0)}


def _pit_chi2(pits, bins=10):
    h, _ = np.histogram(np.asarray(pits, float), bins=bins, range=(0, 1))
    e = len(pits) / bins
    return {'hist': h.tolist(), 'chi2': round(float(((h - e) ** 2 / e).sum()),
                                              3), 'df': bins - 1}


def _ols(x, y):
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    if len(x) < 20 or x.std() <= 1e-12:
        return None
    X = np.column_stack([np.ones(len(x)), x])
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    return {'intercept': round(float(b[0]), 6), 'slope': round(float(b[1]), 5),
            'reads': 'slope 1 and intercept 0 is calibrated in the mean'}


def _block(rs):
    return {
        'n': len(rs),
        'target_crps': round(float(np.mean([r['target_crps'] for r in rs])), 6),
        'target_bias': round(float(np.mean(
            [r['pred_targets'] - r['actual_targets'] for r in rs])), 5),
        'rec_yard_crps': round(float(np.mean(
            [r['rec_yard_crps'] for r in rs])), 6),
        'rec_yard_bias': round(float(np.mean(
            [r['pred_rec_yards'] - r['actual_rec_yards'] for r in rs])), 5),
        'coverage': {str(L): round(float(np.mean([r[f'cov{L}'] for r in rs])), 4)
                     for L in (50, 80, 90, 95)},
        'pit': _pit_chi2([r['target_pit'] for r in rs]),
        'zero_target_probability': {
            'predicted': round(float(np.mean(
                [r['p_zero_targets'] for r in rs])), 5),
            'observed': round(float(np.mean(
                [r['is_zero_actual'] for r in rs])), 5)},
        'target_share_calibration': _ols(
            [r['pred_share'] for r in rs], [r['actual_share'] for r in rs]),
    }


def _sweep(rows, keyf, arms, base='BASELINE'):
    g = collections.defaultdict(list)
    for r in rows:
        g[keyf(r)].append(r)
    out = {}
    for k, rs in sorted(g.items()):
        if len(rs) < 60:
            continue
        ent = {arm: _block([r for r in rs if r['arm'] == arm]) for arm in arms
               if any(r['arm'] == arm for r in rs)}
        keyed = collections.defaultdict(dict)
        for r in rs:
            keyed[(r['season'], r['week'], r['team'], r['pid'])][r['arm']] = r
        common = [v for v in keyed.values() if len(v) == len(arms)]
        for arm in arms:
            if arm == base or not common:
                continue
            b = np.array([v[base]['target_crps'] for v in common], float)
            c = np.array([v[arm]['target_crps'] for v in common], float)
            ent[arm]['delta_pct'] = round(
                100.0 * float((c - b).mean()) / float(b.mean()), 4)
            ent[arm]['improves'] = bool((c - b).mean() < 0)
            ent[arm]['block_bootstrap_by_team_game'] = boot_paired(
                c - b, [v[base]['team_game'] for v in common])
        out[k] = ent
    return out


def summarise(res):
    rows = res['rows']
    rc2 = [r for r in rows if r['rc2_population']]
    out = {
        'artifact': 'NFL_Q8_FORWARD_CHAIN_RESULTS',
        'spec_version': SPEC_VERSION,
        'promoted': False, 'is_research_only': True,
        'market_inputs_used': [], 'live_2026_rows_used': 0,
        'arms': list(ARMS), 'n_rows': len(rows),
        'n_rows_rc2_population': len(rc2),
        'eval_seasons': sorted({r['season'] for r in rows}),
        'held_fixed': [
            'production R8 appearance, read from the committed Q6 chain',
            'the class-level target-share prior',
            'the player-level shrinkage weight',
            'the redistribution rule after an absence',
            'receiving efficiency: one catch rate and one per-catch pool',
            'the touchdown layer',
        ],
        'the_one_change': ('the frozen P4B team-target point is shrunk toward '
                           'the training league mean by an OLS slope fitted on '
                           'strictly earlier seasons, with the residual pool '
                           'recomputed around the new centre'),
        'clustering': 'block bootstrap over whole team-games',
        'overall': {}, 'by_position': {}, 'by_role_class': {},
        'by_target_regime': {}, 'by_appearance_certainty': {},
        'team_budget': {}, 'fit_log': res['fit_log'],
        'receiving_join_evidence': res['receiving_join_evidence'],
    }
    for arm in ARMS:
        out['overall'][arm] = _block([r for r in rows if r['arm'] == arm])
        out['overall'][arm]['rc2_population'] = _block(
            [r for r in rc2 if r['arm'] == arm])
    keyed = collections.defaultdict(dict)
    for r in rows:
        keyed[(r['season'], r['week'], r['team'], r['pid'])][r['arm']] = r
    common = [v for v in keyed.values() if len(v) == len(ARMS)]
    for arm in ARMS[1:]:
        for metric in ('target_crps', 'rec_yard_crps'):
            b = np.array([v['BASELINE'][metric] for v in common], float)
            c = np.array([v[arm][metric] for v in common], float)
            out['overall'][arm][f'paired_{metric}_delta'] = {
                'delta_mean': round(float((c - b).mean()), 6),
                'delta_pct': round(100.0 * float((c - b).mean()) /
                                   float(b.mean()), 4),
                'block_bootstrap_by_team_game': boot_paired(
                    c - b, [v['BASELINE']['team_game'] for v in common]),
            }
    out['by_position'] = _sweep(rows, lambda r: r['pos'], ARMS)
    out['by_role_class'] = _sweep(rows, lambda r: r['role_class'], ARMS)
    out['by_target_regime'] = _sweep(rows, lambda r: r['target_regime'], ARMS)
    out['by_appearance_certainty'] = _sweep(
        rows, lambda r: r['appearance_certainty'], ARMS)
    out['starter_dilution'] = _dilution(rows)
    out['replacement'] = _replacement(rows)
    out['team_budget'] = _budget_block(res['team'])
    out['decision'] = decide(out)
    return out


def _dilution(rows):
    out = {}
    for arm in ARMS:
        ent = {}
        for rc in Q6F.ROLE_CLASSES:
            sel = [r for r in rows if r['arm'] == arm and r['role_class'] == rc]
            if not sel:
                continue
            p = float(np.mean([r['pred_targets'] for r in sel]))
            a = float(np.mean([r['actual_targets'] for r in sel]))
            ent[rc] = {'n': len(sel), 'mean_predicted': round(p, 5),
                       'mean_actual': round(a, 5),
                       'ratio': round(p / a, 5) if a else None}
        out[arm] = ent
    out['reads'] = 'below 1 is dilution: the class is given less than it takes'
    return out


def _replacement(rows):
    """Only team-weeks whose starter did not appear."""
    absent = set()
    for r in rows:
        if r['role_class'] == 'starter' and not r['appeared']:
            absent.add(r['team_game'])
    out = {'n_team_games_with_an_absent_starter': len(absent)}
    for arm in ARMS:
        ent = {}
        for rc in Q6F.ROLE_CLASSES:
            sel = [r for r in rows if r['arm'] == arm
                   and r['role_class'] == rc and r['team_game'] in absent]
            if len(sel) < 30:
                continue
            p = float(np.mean([r['pred_targets'] for r in sel]))
            a = float(np.mean([r['actual_targets'] for r in sel]))
            ent[rc] = {'n': len(sel), 'mean_predicted': round(p, 5),
                       'mean_actual': round(a, 5),
                       'ratio': round(p / a, 5) if a else None}
        out[arm] = ent
    out['reads'] = ('measured only where a starter was absent; below 1 means '
                    'the replacement is under-fed relative to what he took')
    return out


def _budget_block(team_rows):
    out = {}
    keyed = collections.defaultdict(dict)
    for r in team_rows:
        keyed[(r['season'], r['week'], r['team'])][r['arm']] = r
    common = [v for v in keyed.values() if len(v) == len(ARMS)]
    for arm in ARMS:
        sel = [r for r in team_rows if r['arm'] == arm]
        p = np.array([r['pred_team_targets'] for r in sel], float)
        y = np.array([r['actual_team_targets'] for r in sel], float)
        out[arm] = {
            'n': len(sel),
            'bias': round(float((p - y).mean()), 5),
            'rmse': round(float(np.sqrt(((p - y) ** 2).mean())), 5),
            'crps': round(float(np.mean([r['budget_crps'] for r in sel])), 5),
            'calibration': _ols(p, y),
        }
        if arm != 'BASELINE' and common:
            b = np.array([v['BASELINE']['budget_crps'] for v in common], float)
            c = np.array([v[arm]['budget_crps'] for v in common], float)
            out[arm]['paired_crps_delta_pct'] = round(
                100.0 * float((c - b).mean()) / float(b.mean()), 4)
            out[arm]['block_bootstrap_by_team_game'] = boot_paired(
                c - b, [f"{v['BASELINE']['season']}-{v['BASELINE']['week']}-"
                        f"{v['BASELINE']['team']}" for v in common])
    return out


def decide(summary, arm='Q8_BUDGET_SHRINK'):
    """SUPPORT / WEAK_SUPPORT / REJECT, against the rule frozen in the spec.

      SUPPORT       player-target CRPS improves overall and in a majority of
                    strata, at least one improvement survives the
                    team-game-clustered bootstrap, no stratum is significantly
                    worse, and downstream receiving-yard CRPS does not degrade.
      WEAK_SUPPORT  player-target CRPS improves overall and nothing is
                    significantly worse.
      REJECT        otherwise.

    A GAIN IN COVERAGE OR BIAS IS NOT SUPPORT. The audit showed that bias on
    the appeared-only population is substantially a selection artefact, so the
    proper score is the only thing that counts and this function enforces it.
    """
    o = summary['overall'].get(arm, {})
    d = o.get('paired_target_crps_delta')
    if not d:
        return {'decision': 'REJECT', 'arm': arm, 'why': 'no paired delta',
                'rule': decide.__doc__.strip()}
    improves = d['delta_mean'] < 0
    yd = o.get('paired_rec_yard_crps_delta') or {}
    yb = yd.get('block_bootstrap_by_team_game') or {}
    yards_degrade = bool(yb.get('excludes_zero')
                         and yd.get('delta_mean', 0) > 0)
    n_imp = n_tot = 0
    sig_better, sig_worse = [], []
    for name in ('by_position', 'by_role_class', 'by_target_regime',
                 'by_appearance_certainty'):
        for k, ent in summary[name].items():
            e = ent.get(arm) or {}
            if 'improves' not in e:
                continue
            n_tot += 1
            n_imp += 1 if e['improves'] else 0
            bb = e.get('block_bootstrap_by_team_game') or {}
            if bb.get('excludes_zero'):
                (sig_better if e['improves'] else sig_worse).append(
                    f'{name}:{k}')
    if not improves:
        return {'decision': 'REJECT', 'arm': arm,
                'why': 'player-target CRPS did not improve; coverage and bias '
                       'cannot rescue a proper score',
                'coverage_or_bias_cannot_rescue': True,
                'strata_improved': n_imp, 'strata_total': n_tot,
                'strata_significantly_worse': sorted(sig_worse),
                'rule': decide.__doc__.strip()}
    broad = (n_tot and n_imp > n_tot / 2 and bool(sig_better)
             and not sig_worse and not yards_degrade)
    dec = 'SUPPORT' if broad else (
        'WEAK_SUPPORT' if not sig_worse and not yards_degrade else 'REJECT')
    return {'decision': dec, 'arm': arm,
            'overall_target_crps_delta_pct': d['delta_pct'],
            'overall_target_crps_significant':
                d['block_bootstrap_by_team_game']['excludes_zero'],
            'downstream_receiving_yard_crps_degrades': yards_degrade,
            'strata_improved': n_imp, 'strata_total': n_tot,
            'strata_significantly_better': sorted(sig_better),
            'strata_significantly_worse': sorted(sig_worse),
            'coverage_or_bias_cannot_rescue': True,
            'rule': decide.__doc__.strip()}


def _write(rows, path, gz=True):
    if not rows:
        raise SystemExit(f'Q8_EMPTY_TABLE: {path} would carry no rows. An '
                         f'empty table is an error, not a result.')
    opener = ((lambda: gzip.open(path, 'wt', newline='')) if gz
              else (lambda: open(path, 'w', newline='')))
    with opener() as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return len(rows)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--seasons', default=','.join(str(s) for s in EVAL_SEASONS))
    ap.add_argument('--draws', type=int, default=N_DRAWS)
    a = ap.parse_args(argv)
    res = run(tuple(int(x) for x in a.seasons.split(',')), a.draws)
    s = summarise(res)
    s['n_draws'] = a.draws
    RESULTS.write_text(json.dumps(s, indent=1, default=str) + '\n')
    _write(res['rows'], ROWS)
    _write(res['team'], DIAGNOSTICS, gz=False)
    print(f"\nrows        : {len(res['rows'])}")
    print(f"decision    : {s['decision']['decision']}")
    for arm in ARMS:
        o = s['overall'][arm]
        print(f"  {arm:18s} target_crps {o['target_crps']:.5f}  "
              f"rec_yard_crps {o['rec_yard_crps']:.4f}")
    b = s['team_budget']
    for arm in ARMS:
        print(f"  budget {arm:18s} bias {b[arm]['bias']:+7.4f} "
              f"rmse {b[arm]['rmse']:.4f} crps {b[arm]['crps']:.4f} "
              f"slope {b[arm]['calibration']['slope']}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
