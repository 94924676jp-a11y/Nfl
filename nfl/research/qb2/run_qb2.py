"""QB2: oracle decomposition, ladder, persistence, distributions, subgroups.

EXPLORATORY. No promotion. Production BASELINE SELECTION only.
"""
import collections, itertools, json, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', 'rc1'))
sys.path.insert(0, os.path.join(HERE, '..', '..', '..'))
import qb2_lib as Q                                            # noqa: E402
import rc1_lib as L                                            # noqa: E402
from nfl.production import qb_accounting as ACC                # noqa: E402
from sportsplatform.governance.outcome import State            # noqa: E402

PREREG = 'e69bd331bb72a3f869b8469c27f0d9782ff49c7c69874ea79585f55a9eb84ff1'
PSUB = [frozenset(c) for k in range(6)
        for c in itertools.combinations(Q.PASS_COMPONENTS, k)]
RSUB = [frozenset(c) for k in range(4)
        for c in itertools.combinations(Q.RUSH_COMPONENTS, k)]
# 'VS' oracles team volume and QB share together, per prereg s5.
_EXPAND = {'VS': ('V', 'S'), 'RO': ('RO',), 'RY': ('RY',)}


def score(D, y):
    p = D.mean(1); e = p - y
    return {'crps': float(L.crps_matrix(D, y).mean()),
            'mae': float(np.abs(e).mean()),
            'rmse': float(np.sqrt(float((e * e).mean()))),
            'bias': float(e.mean()),
            'r': (float(np.corrcoef(p, y)[0, 1])
                  if p.std() > 1e-12 and y.std() > 1e-12 else None),
            'sd_ratio': (float(p.std(ddof=1) / y.std(ddof=1))
                         if y.std(ddof=1) > 1e-12 else None),
            **{f'cover{l}': float(((y >= np.quantile(D, (100 - l) / 200, axis=1))
                                   & (y <= np.quantile(D, 1 - (100 - l) / 200,
                                                       axis=1))).mean())
               for l in (50, 80, 90, 95)}}


def main():
    rs = Q.load()
    OUT = {'prereg_sha256': PREREG,
           'label': 'EXPLORATORY -- heavily mined; baseline selection only, '
                    'never promotion',
           'policy': 'team-QB aggregate then allocation'}

    # ---- oracle decomposition on PASSING YARDS ---------------------------
    print('== oracle decomposition: QB passing yards ==')
    per = {fs: [] for fs in PSUB}
    Y, G, ROWS = [], [], []
    ident = {}
    for ev in Q.EVAL:
        e = [r for r in rs if Q.eligible(r, ev)]
        y = np.array([r['pyds'] for r in e], float)
        Y.append(y); G += [r['game_id'] for r in e]; ROWS += e
        for fs in PSUB:
            D = Q.simulate(e, ev, rs, oracle=tuple(sorted(fs)))
            per[fs].append(L.crps_matrix(D['pyds'], y))
            if fs == frozenset(Q.PASS_COMPONENTS):
                ident[ev] = float(np.abs(D['pyds'].mean(1) - y).max())
        print(f'  {ev}: n={len(e):4d}  identity |err| {ident[ev]:.2e} -> '
              f'{"VALID" if ident[ev] < 1e-9 else "INVALID"}')
    Y = np.concatenate(Y)
    C = {fs: np.concatenate(per[fs]) for fs in PSUB}
    base = float(C[frozenset()].mean())
    vals = {fs: base - float(C[fs].mean()) for fs in PSUB}
    phi = Q.shapley(vals, Q.PASS_COMPONENTS); tot = sum(phi.values())
    by = collections.defaultdict(list)
    for i, g in enumerate(G): by[g].append(i)
    keys = list(by); idxs = [np.array(by[k]) for k in keys]
    rng = np.random.default_rng(Q.SEED)
    boot = {c: [] for c in Q.PASS_COMPONENTS}
    for _ in range(400):
        pick = rng.integers(0, len(keys), len(keys))
        sel = np.concatenate([idxs[j] for j in pick])
        b = float(C[frozenset()][sel].mean())
        v = {fs: b - float(C[fs][sel].mean()) for fs in PSUB}
        p = Q.shapley(v, Q.PASS_COMPONENTS)
        for c in Q.PASS_COMPONENTS: boot[c].append(p[c])
    OUT['pass_yards_decomposition'] = {
        'n': int(len(Y)), 'n_games': len(set(G)), 'baseline_crps': base,
        'identity_max_abs_error': ident,
        'identity_valid': all(v < 1e-9 for v in ident.values()),
        'shapley_crps': phi,
        'shapley_pct': {k: 100 * v / tot for k, v in phi.items()},
        'shapley_ci': {c: {'lo': float(np.quantile(boot[c], .025)),
                           'hi': float(np.quantile(boot[c], .975))}
                       for c in Q.PASS_COMPONENTS},
        'efficiency_gap': tot - vals[frozenset(Q.PASS_COMPONENTS)]}
    print(f'  baseline CRPS {base:.4f}   n={len(Y)}  games={len(set(G))}')
    for c in Q.PASS_COMPONENTS:
        ci = OUT['pass_yards_decomposition']['shapley_ci'][c]
        print(f'    {c}: {phi[c]:8.4f}  {100*phi[c]/tot:6.2f}%  '
              f'95% CI [{ci["lo"]:.4f}, {ci["hi"]:.4f}]')
    print(f'    efficiency gap {tot - vals[frozenset(Q.PASS_COMPONENTS)]:.2e}')

    # ---- SECONDARY estimand: rushing yards, 3 components, 8 coalitions ---
    print('\n== oracle decomposition: QB rushing yards (secondary) ==')
    rper = {fs: [] for fs in RSUB}
    RY_, RG = [], []
    rident = {}
    for ev in Q.EVAL:
        e = [r for r in rs if Q.eligible(r, ev)]
        y = np.array([r['ryds'] for r in e], float)
        RY_.append(y); RG += [r['game_id'] for r in e]
        for fs in RSUB:
            orc = tuple(sorted({x for c in fs for x in _EXPAND[c]}))
            D = Q.simulate(e, ev, rs, oracle=orc)
            rper[fs].append(L.crps_matrix(D['ryds'], y))
            if fs == frozenset(Q.RUSH_COMPONENTS):
                rident[ev] = float(np.abs(D['ryds'].mean(1) - y).max())
    RY_ = np.concatenate(RY_)
    RC = {fs: np.concatenate(rper[fs]) for fs in RSUB}
    rbase = float(RC[frozenset()].mean())
    rvals = {fs: rbase - float(RC[fs].mean()) for fs in RSUB}
    rphi = Q.shapley(rvals, Q.RUSH_COMPONENTS); rtot = sum(rphi.values())
    rby = collections.defaultdict(list)
    for i, g in enumerate(RG): rby[g].append(i)
    rkeys = list(rby); ridxs = [np.array(rby[k]) for k in rkeys]
    rrng = np.random.default_rng(Q.SEED)
    rboot = {c: [] for c in Q.RUSH_COMPONENTS}
    for _ in range(400):
        pick = rrng.integers(0, len(rkeys), len(rkeys))
        sel = np.concatenate([ridxs[j] for j in pick])
        b = float(RC[frozenset()][sel].mean())
        v = {fs: b - float(RC[fs][sel].mean()) for fs in RSUB}
        pp = Q.shapley(v, Q.RUSH_COMPONENTS)
        for c in Q.RUSH_COMPONENTS: rboot[c].append(pp[c])
    OUT['rush_yards_decomposition'] = {
        'n': int(len(RY_)), 'baseline_crps': rbase,
        'full_oracle_crps': float(RC[frozenset(Q.RUSH_COMPONENTS)].mean()),
        'full_oracle_max_abs_error': rident,
        'full_oracle_is_exact': False,
        'why_not_exact': ('the scramble half of a QB rushing opportunity comes '
                          'from the dropback mix M, which prereg s5 did not '
                          'make one of the three rush components. The residual '
                          'is NAMED as scramble volume rather than closed by '
                          'adding a fourth component after the fact.'),
        'shapley_crps': rphi,
        'shapley_pct': {k: 100 * v / rtot for k, v in rphi.items()},
        'shapley_ci': {c: {'lo': float(np.quantile(rboot[c], .025)),
                           'hi': float(np.quantile(rboot[c], .975))}
                       for c in Q.RUSH_COMPONENTS},
        'efficiency_gap': rtot - rvals[frozenset(Q.RUSH_COMPONENTS)]}
    print(f'  baseline CRPS {rbase:.4f}  full-oracle CRPS '
          f'{RC[frozenset(Q.RUSH_COMPONENTS)].mean():.4f} (NOT exact, by '
          f'construction)')
    for c in Q.RUSH_COMPONENTS:
        ci = OUT['rush_yards_decomposition']['shapley_ci'][c]
        print(f'    {c}: {rphi[c]:8.4f}  {100*rphi[c]/rtot:6.2f}%  '
              f'95% CI [{ci["lo"]:.4f}, {ci["hi"]:.4f}]')
    print(f'    efficiency gap {rtot - rvals[frozenset(Q.RUSH_COMPONENTS)]:.2e}')

    # ---- CLOSED four-rung ladder, prereg s6 ------------------------------
    print('\n== V1 ladder: L0 pooled / L1 shrunk / L2 EWMA / L3 shrunk EWMA ==')
    lad = {}
    lcr = {}
    LG = []
    for i, rung in enumerate(Q.RUNGS):
        cur, yy, gg = [], [], []
        for ev in Q.EVAL:
            e = [r for r in rs if Q.eligible(r, ev)]
            y = np.array([r['pyds'] for r in e], float)
            D = Q.simulate(e, ev, rs, rung=rung)
            cur.append(L.crps_matrix(D['pyds'], y)); yy.append(y)
            if i == 0: gg += [r['game_id'] for r in e]
        if i == 0: LG = gg
        lcr[rung] = np.concatenate(cur)
        lad[rung] = {'crps': float(lcr[rung].mean())}
        print(f'  {rung}  CRPS {lad[rung]["crps"]:8.4f}')
    lby = collections.defaultdict(list)
    for i, g in enumerate(LG): lby[g].append(i)
    lkeys = list(lby); lidxs = [np.array(lby[k]) for k in lkeys]
    lrng = np.random.default_rng(Q.SEED)
    ref = 'L1'
    diffs = {r_: [] for r_ in Q.RUNGS if r_ != ref}
    for _ in range(400):
        pick = lrng.integers(0, len(lkeys), len(lkeys))
        sel = np.concatenate([lidxs[j] for j in pick])
        b = float(lcr[ref][sel].mean())
        for r_ in diffs: diffs[r_].append(float(lcr[r_][sel].mean()) - b)
    for r_ in diffs:
        lad[r_]['delta_vs_L1'] = lad[r_]['crps'] - lad[ref]['crps']
        lad[r_]['delta_ci'] = {'lo': float(np.quantile(diffs[r_], .025)),
                               'hi': float(np.quantile(diffs[r_], .975))}
        d = lad[r_]
        print(f'  {r_} - L1  {d["delta_vs_L1"]:+8.4f}  95% CI '
              f'[{d["delta_ci"]["lo"]:+.4f}, {d["delta_ci"]["hi"]:+.4f}]  '
              f'{"separates" if d["delta_ci"]["hi"] < 0 or d["delta_ci"]["lo"] > 0 else "DOES NOT SEPARATE"}')
    OUT['ladder'] = {
        'rungs': list(Q.RUNGS), 'reference': ref, 'metric': 'pass-yards CRPS',
        'bootstrap': 'game-clustered, 400 resamples',
        'results': lad,
        'label': ('EXPLORATORY. These four seasons already selected the '
                  'definitions, the policy and this ladder. A rung winning '
                  'here is a production BASELINE SELECTION, never a '
                  'promotion.')}

    # ---- persistence: opportunity vs efficiency, measured identically ----
    print('\n== persistence: opportunity vs efficiency ==')
    def wc(x, y_, w):
        x, y_, w = np.array(x, float), np.array(y_, float), np.array(w, float)
        if len(x) < 20: return None
        mx = (x * w).sum() / w.sum(); my = (y_ * w).sum() / w.sum()
        vx = (w * (x - mx) ** 2).sum(); vy = (w * (y_ - my) ** 2).sum()
        return (float((w * (x - mx) * (y_ - my)).sum() / np.sqrt(vx * vy))
                if vx > 0 and vy > 0 else None)
    P = {}
    for nm, prior, cur, wt in (
            ('opportunity: dropbacks', lambda r: r['h_db'] / r['h_games'],
             lambda r: r['db'], lambda r: 1.0),
            ('opportunity: team dropbacks',
             lambda r: np.mean(r['h_team_db_series']) if r['h_team_db_series'] else None,
             lambda r: r['team_db'], lambda r: 1.0),
            ('opportunity: QB share',
             lambda r: r['h_db'] / max(sum(r['h_team_db_series']), 1)
             if r['h_team_db_series'] else None,
             lambda r: r['db'] / r['team_db'] if r['team_db'] else None,
             lambda r: r['team_db']),
            ('efficiency: completion rate',
             lambda r: r['h_cmp'] / r['h_att'] if r['h_att'] >= 20 else None,
             lambda r: r['cmp'] / r['att'] if r['att'] else None,
             lambda r: r['att']),
            ('efficiency: yards per completion',
             lambda r: r['h_pyds'] / r['h_cmp'] if r['h_cmp'] >= 20 else None,
             lambda r: r['pyds'] / r['cmp'] if r['cmp'] else None,
             lambda r: r['cmp']),
            ('efficiency: pass TD rate',
             lambda r: r['h_ptd'] / r['h_att'] if r['h_att'] >= 50 else None,
             lambda r: r['ptd'] / r['att'] if r['att'] else None,
             lambda r: r['att']),
            ('efficiency: INT rate',
             lambda r: r['h_int'] / r['h_att'] if r['h_att'] >= 50 else None,
             lambda r: r['int'] / r['att'] if r['att'] else None,
             lambda r: r['att']),
            ('efficiency: sack rate',
             lambda r: r['h_sack'] / r['h_db'] if r['h_db'] >= 50 else None,
             lambda r: r['sacks'] / r['db'] if r['db'] else None,
             lambda r: r['db'])):
        a, b, w = [], [], []
        for r in ROWS:
            try:
                pa, cb, ww = prior(r), cur(r), wt(r)
            except (ZeroDivisionError, TypeError):
                continue
            if pa is None or cb is None or not ww:
                continue
            a.append(pa); b.append(cb); w.append(ww)
        P[nm] = {'n': len(a), 'r': wc(a, b, w)}
        rr = P[nm]['r']
        print(f'  {nm:<34} n={len(a):5d}  r {"None" if rr is None else f"{rr:+.4f}"}')
    OUT['persistence'] = P

    # ---- distributions and subgroups -------------------------------------
    print('\n== V1 distributions, walk-forward ==')
    FIELDS = ('db', 'att', 'cmp', 'sacks', 'scr', 'pyds', 'ptd', 'int',
              'drush', 'rush_opp', 'ryds', 'rtd')
    ACT = {'db': 'db', 'att': 'att', 'cmp': 'cmp', 'sacks': 'sacks',
           'scr': 'scr', 'pyds': 'pyds', 'ptd': 'ptd', 'int': 'int',
           'drush': 'drush', 'rush_opp': 'rush_opp', 'ryds': 'ryds',
           'rtd': 'rtd'}
    acc = {f: {'D': [], 'y': []} for f in FIELDS}
    seasonal = {}; acct = {}
    for ev in Q.EVAL:
        e = [r for r in rs if Q.eligible(r, ev)]
        D = Q.simulate(e, ev, rs)
        # prereg s8: the per-draw chain is ASSERTED here, not assumed.
        _a = ACC.reconcile_draws(D)
        if _a.state is not State.PASS:
            raise SystemExit(f'QB accounting failed on {ev}: {_a.code} '
                             f'{_a.detail}')
        acct[ev] = _a.value['report']
        seasonal[ev] = {}
        for f in FIELDS:
            y = np.array([r[ACT[f]] for r in e], float)
            acc[f]['D'].append(D[f]); acc[f]['y'].append(y)
            seasonal[ev][f] = score(D[f], y)
    OUT['distributions'] = {}
    for f in FIELDS:
        D = np.concatenate(acc[f]['D']); y = np.concatenate(acc[f]['y'])
        s = score(D, y)
        OUT['distributions'][f] = s
        print(f"  {f:<10} CRPS {s['crps']:8.3f}  MAE {s['mae']:8.3f}  "
              f"bias {s['bias']:+7.3f}  r {('%.4f'%s['r']) if s['r'] else 'n/a':>7}  "
              f"cov50 {s['cover50']:.3f} cov90 {s['cover90']:.3f}")
    OUT['by_season'] = seasonal
    OUT['per_draw_accounting'] = {
        'state': 'PASS', 'seasons': list(acct),
        'identities': len(ACC.PER_DRAW_IDENTITIES),
        'violating_cells': {str(k): sum(v['violating_cells'] for v in r.values())
                            for k, r in acct.items()},
        'named_residual_not_enforced': ACC.ALLOCATION_RESIDUAL}

    print('\n== subgroups ==')
    OUT['subgroups'] = {}
    labs_change = []
    tg = collections.defaultdict(int)
    for r in rs:
        if r['db'] > 0: tg[(r['season'], r['week'], r['team'])] += 1
    for r in ROWS:
        labs_change.append('multi_qb' if tg[(r['season'], r['week'], r['team'])] > 1
                           else 'single_qb')
    labs_hist = ['low_history' if r['h_games'] < 8 else 'established'
                 for r in ROWS]
    Dall = {f: np.concatenate(acc[f]['D']) for f in ('pyds', 'db')}
    Yall = {f: np.concatenate(acc[f]['y']) for f in ('pyds', 'db')}
    for dim, labs in (('qb_change', labs_change), ('history', labs_hist)):
        OUT['subgroups'][dim] = {}
        labs = np.array(labs)
        for lab in sorted(set(labs.tolist())):
            m = labs == lab
            if m.sum() < 50: continue
            s = score(Dall['pyds'][m], Yall['pyds'][m])
            OUT['subgroups'][dim][lab] = {'n': int(m.sum()), **s}
            print(f"  {dim:<11}{lab:<14} n={int(m.sum()):5d}  "
                  f"pass-yds CRPS {s['crps']:7.3f}  bias {s['bias']:+7.2f}  "
                  f"r {s['r']:.4f}  cov90 {s['cover90']:.3f}")
    json.dump(OUT, open(f'{HERE}/qb2_results.json', 'w'), indent=1, default=str)
    print('\nwrote qb2_results.json')
    return 0


if __name__ == '__main__':
    sys.exit(main())
