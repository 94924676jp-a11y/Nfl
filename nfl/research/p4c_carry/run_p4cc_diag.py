"""P4C-CARRY items 14-19 and 24: component diagnostics and cohorts."""
import collections, csv, json, math, os, pickle, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
P4B = os.path.abspath(os.path.join(HERE, '..', 'p4b'))
P4C = os.path.abspath(os.path.join(HERE, '..', 'p4c'))
P5A = os.path.abspath(os.path.join(HERE, '..', 'p5a'))
sys.path.insert(0, HERE); sys.path.insert(0, P4C); sys.path.insert(0, P5A)
import p4c_lib as CL                                           # noqa: E402
import p4c_build as CB                                         # noqa: E402
import p5a_lib as PL                                           # noqa: E402
EVAL = [2022, 2023, 2024, 2025]
OUT = {}

# ---------------------------------------------------------------------------
# 14. TEAM VOLUME
# ---------------------------------------------------------------------------
vol = np.load(f'{P4B}/volume_store.npy', allow_pickle=True)
V = {}
for e in vol:
    d = dict(e); k = tuple(d.pop('k'))
    d['index'] = {kk: i for i, kk in enumerate(d['keys'])}
    V[k] = d
car = []
for r in csv.DictReader(open(f'{P5A}/carries.csv')):
    car.append({'season': int(r['season']), 'week': int(r['week']),
                'team': r['posteam'], 'rusher': r['rusher'],
                'scramble': int(r['scramble'])})
panel = pickle.load(open(f'{P4B}/panel_enriched.pkl', 'rb'))
pos_of = {}
for p in panel:
    pos_of[(p['season'], p['week'], p['team'], p['gsis_id'])] = p['position']
split = collections.defaultdict(lambda: collections.Counter())
for c in car:
    k = (c['team'], c['season'] * 100 + c['week'])
    p = pos_of.get((c['season'], c['week'], c['team'], c['rusher']), 'UNKNOWN')
    s = split[k]
    s['total'] += 1
    s['scramble'] += c['scramble']
    s['QB' if p == 'QB' else ('RB' if p == 'RB' else 'OTHER_POS')] += 1
tv = {}
for ev in EVAL:
    st = V[('team_carries', ev)]
    keys = st['keys']; pt = st['point']; rz = st['realized']
    e = rz - pt
    q = np.array([split[k]['QB'] for k in keys], float)
    rb = np.array([split[k]['RB'] for k in keys], float)
    sc = np.array([split[k]['scramble'] for k in keys], float)
    tot = np.array([split[k]['total'] for k in keys], float)
    B = st['B']
    lo = np.percentile(B, 5, axis=1); hi = np.percentile(B, 95, axis=1)
    tv[ev] = {
        'n_team_games': len(keys),
        'mean_pred': float(pt.mean()), 'mean_real': float(rz.mean()),
        'bias': float(-e.mean()), 'mae': float(np.abs(e).mean()),
        'rmse': float(math.sqrt((e ** 2).mean())),
        'r': float(np.corrcoef(pt, rz)[0, 1]) if pt.std() > 0 else None,
        'sd_pred': float(pt.std(ddof=1)), 'sd_real': float(rz.std(ddof=1)),
        'variance_captured_r2': float(1 - (e ** 2).sum()
                                      / ((rz - rz.mean()) ** 2).sum()),
        'coverage_90': float(((rz >= lo) & (rz <= hi)).mean()),
        'below_p05': float((rz < lo).mean()), 'above_p95': float((rz > hi).mean()),
        'lower_decile_bias': float(-(e[rz <= np.percentile(rz, 10)]).mean()),
        'upper_decile_bias': float(-(e[rz >= np.percentile(rz, 90)]).mean()),
        'composition': {'RB_share': float((rb / tot).mean()),
                        'QB_share': float((q / tot).mean()),
                        'scramble_share': float((sc / tot).mean()),
                        'OTHER_pos_share': float(
                            ((tot - rb - q) / tot).mean())},
    }
OUT['team_volume'] = tv
print('== 14. TEAM VOLUME (accepted P4B carry total) ==')
for ev, d in tv.items():
    print(f'  {ev} n={d["n_team_games"]} pred {d["mean_pred"]:.2f} real '
          f'{d["mean_real"]:.2f} bias {d["bias"]:+.3f} MAE {d["mae"]:.3f} '
          f'r {(d["r"] or 0):+.3f} R2 {d["variance_captured_r2"]:+.4f} '
          f'cov90 {d["coverage_90"]:.3f} lowDecBias {d["lower_decile_bias"]:+.2f} '
          f'upDecBias {d["upper_decile_bias"]:+.2f}')
print('  composition (mean of per-team-game shares):',
      {k: round(v, 4) for k, v in tv[2024]['composition'].items()})

# ---------------------------------------------------------------------------
# 15-19, 24. ROW-LEVEL COHORTS
# ---------------------------------------------------------------------------
pg = pickle.load(open(f'{P5A}/pg.pkl', 'rb'))['pg']
pgi = {(r['season'], r['week'], r['team'], r['gsis_id']): r for r in pg}
res = json.load(open(f'{HERE}/p4cc_results.json'))
cohorts = collections.defaultdict(lambda: collections.defaultdict(
    lambda: collections.defaultdict(float)))
rb12 = collections.defaultdict(lambda: collections.defaultdict(float))
asym = collections.defaultdict(lambda: collections.defaultdict(float))
appear = collections.defaultdict(lambda: collections.defaultdict(float))
for ev in EVAL:
    R = pickle.load(open(f'{HERE}/rowlevel_{ev}.pkl', 'rb'))
    y = R['y']; n = len(y)
    sh = R['shapley_rows']; cr = R['crps_rows']
    starts = R['starts']; cg = R['counts_g']
    Cpre = R['C_pre']
    gidx = np.searchsorted(starts, np.arange(n), 'right') - 1
    base = cr['A_baseline']
    pred_mean_base = None
    # rank within team-game by the PREGAME share forecast
    rank = np.zeros(n, int)
    for gi, s in enumerate(starts):
        e = s + cg[gi]
        idx = np.arange(s, e)
        order = idx[np.argsort(-Cpre[s:e])]
        for k, i in enumerate(order):
            rank[i] = k + 1

    def tier(k):
        return ('0' if k == 0 else '1-4' if k <= 4 else '5-9' if k <= 9
                else '10-14' if k <= 14 else '15+')

    def band(p):
        return ('p<0.25' if p < .25 else 'p 0.25-0.50' if p < .5
                else 'p 0.50-0.80' if p < .8
                else 'p 0.80-0.95' if p < .95 else 'p>=0.95')
    eff = []
    for k in R['keys']:
        q = pgi.get(k)
        if q and q['p'] and q['p']['n'] >= 25:
            eff.append('high' if q['p']['ypc'] >= 4.3 else 'low')
        else:
            eff.append('none')
    splits = {
        'carry_tier': [tier(int(v)) for v in y],
        'rank': [f'RB{r}' if r <= 3 else 'RB4+' for r in rank],
        'role': ['role_change' if v == 1 else 'stable' for v in R['role_change']],
        'info_quality': [v or 'UNKNOWN' for v in R['info_quality']],
        'appearance_band': [band(p) for p in R['p_app']],
        'efficiency_history': eff,
        'season': [str(ev)] * n,
    }
    for sname, lab in splits.items():
        lab = np.array(lab)
        for u in set(lab.tolist()):
            m = lab == u
            if m.sum() < 40:
                continue
            a = cohorts[sname][u]
            a['n'] += m.sum()
            a['crps_base'] += base[m].sum()
            for comp in ('T', 'S', 'A'):
                a[f'sh_{comp}'] += sh[comp][m].sum()
            a['y'] += y[m].sum()
            a['zero'] += (y[m] < 0.5).sum()
    # ---- 24. asymmetry: are carries over/under projected by eff history? --
    predm = {}
    for nm in ('A_baseline',):
        pass
    # mean predicted carries from the baseline: recover via bias per row
    # (base CRPS rows do not carry the mean, so recompute from the corner file)
    # -> use the stored per-row realised y and the corner's pooled bias instead
    for u in set(eff):
        m = np.array(eff) == u
        if m.sum() < 40:
            continue
        a = asym[u]
        a['n'] += m.sum(); a['y'] += y[m].sum()
        a['crps'] += base[m].sum()
        a['p_app'] += R['p_app'][m].sum()
        a['Cpre'] += Cpre[m].sum()
        a['Sstar'] += R['Sstar'][m].sum()
    # ---- RB1 <-> RB2 realised share dependence -------------------------
    for gi, s in enumerate(starts):
        e = s + cg[gi]
        idx = np.arange(s, e)
        if len(idx) < 2:
            continue
        order = idx[np.argsort(-Cpre[s:e])]
        a, b = order[0], order[1]
        rb12[ev]['n'] += 1
        rb12[ev]['s1'] += R['Sstar'][a]; rb12[ev]['s2'] += R['Sstar'][b]
        rb12[ev].setdefault('_pairs', [])
        rb12[ev]['_pairs'] = rb12[ev].get('_pairs') or []
    # store pairs properly
    pr = []
    for gi, s in enumerate(starts):
        e = s + cg[gi]
        idx = np.arange(s, e)
        if len(idx) < 2:
            continue
        order = idx[np.argsort(-Cpre[s:e])]
        pr.append((R['Sstar'][order[0]], R['Sstar'][order[1]],
                   Cpre[order[0]], Cpre[order[1]]))
    pr = np.array(pr)
    rb12[ev] = {'n_pairs': int(len(pr)),
                'corr_realised_S1_S2': float(np.corrcoef(pr[:, 0], pr[:, 1])[0, 1]),
                'corr_forecast_C1_C2': float(np.corrcoef(pr[:, 2], pr[:, 3])[0, 1]),
                'mean_S1': float(pr[:, 0].mean()), 'mean_S2': float(pr[:, 1].mean()),
                'mean_C1': float(pr[:, 2].mean()), 'mean_C2': float(pr[:, 3].mean())}

OUT['cohorts'] = {s: {u: {'n': int(a['n']),
                          'crps_base': a['crps_base'] / a['n'],
                          'mean_carries': a['y'] / a['n'],
                          'zero_rate': a['zero'] / a['n'],
                          'shapley_T': a['sh_T'] / a['n'],
                          'shapley_S': a['sh_S'] / a['n'],
                          'shapley_A': a['sh_A'] / a['n'],
                          'pct_T': 100 * a['sh_T'] / max(a['sh_T'] + a['sh_S'] + a['sh_A'], 1e-9),
                          'pct_S': 100 * a['sh_S'] / max(a['sh_T'] + a['sh_S'] + a['sh_A'], 1e-9),
                          'pct_A': 100 * a['sh_A'] / max(a['sh_T'] + a['sh_S'] + a['sh_A'], 1e-9)}
                      for u, a in d.items()} for s, d in cohorts.items()}
OUT['rb1_rb2'] = {str(k): v for k, v in rb12.items()}
OUT['efficiency_asymmetry'] = {u: {'n': int(a['n']),
                                   'mean_realised_carries': a['y'] / a['n'],
                                   'mean_forecast_share_C': a['Cpre'] / a['n'],
                                   'mean_realised_share': a['Sstar'] / a['n'],
                                   'share_gap_forecast_minus_realised':
                                       (a['Cpre'] - a['Sstar']) / a['n'],
                                   'mean_p_app': a['p_app'] / a['n'],
                                   'crps_base': a['crps'] / a['n']}
                               for u, a in asym.items()}
json.dump(OUT, open(f'{HERE}/p4cc_diag.json', 'w'), indent=1)

print('\n== cohort Shapley attribution (share of the three-component total) ==')
for s in ('carry_tier', 'rank', 'role', 'appearance_band', 'info_quality',
          'efficiency_history', 'season'):
    print(f'\n {s}')
    for u, a in sorted(OUT['cohorts'][s].items(), key=lambda kv: -kv[1]['n']):
        print(f'   {u:14s} n={a["n"]:5d} meanCar={a["mean_carries"]:5.2f} '
              f'zero={a["zero_rate"]:.3f} CRPS={a["crps_base"]:6.3f} | '
              f'T={a["pct_T"]:5.1f}% S={a["pct_S"]:5.1f}% A={a["pct_A"]:5.1f}%')
print('\n== RB1<->RB2 realised share dependence ==')
for ev, d in OUT['rb1_rb2'].items():
    print(f'  {ev} pairs={d["n_pairs"]} corr(realised S1,S2)='
          f'{d["corr_realised_S1_S2"]:+.4f}  corr(forecast C1,C2)='
          f'{d["corr_forecast_C1_C2"]:+.4f}  meanS1={d["mean_S1"]:.4f} '
          f'meanS2={d["mean_S2"]:.4f}')
print('\n== 24. efficiency-history asymmetry in CARRY forecasts ==')
for u, a in OUT['efficiency_asymmetry'].items():
    print(f'  {u:6s} n={a["n"]:5d} forecast share {a["mean_forecast_share_C"]:.5f} '
          f'realised share {a["mean_realised_share"]:.5f} gap '
          f'{a["share_gap_forecast_minus_realised"]:+.5f} '
          f'p_app {a["mean_p_app"]:.4f} meanCarries {a["mean_realised_carries"]:.2f}')
print('\nwrote p4cc_diag.json')
