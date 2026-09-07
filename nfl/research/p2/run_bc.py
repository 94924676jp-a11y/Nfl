"""P2 §5: Model U vs Model C vs Model A x C, on ONE population.

THE ESTIMAND, DECLARED BEFORE FITTING (predeclaration_p2.md §3)

Expected unconditional share, E[Y] = P(appear) * E[Y | appear]. The forecast
distribution is a mixture: point mass (1 - P(appear)) at exactly zero, plus the
conditional distribution on (0, 1]. Multiplying is coherent here because Y is a
share in [0,1] and Y = 0 exactly when the player does not appear, so the product
of a probability and a conditional share is itself a valid share. That is
checked rather than assumed because the directive says not to blindly multiply.

All three models are scored on the SAME rows -- every pregame candidate,
including the ones who did not play, where the truth is 0. Scoring C on
appearances only and U on everyone would compare two different questions, which
is the P1 error this whole directive exists to correct.
"""
import collections, json, math, os, random, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stage_a as A

HERE = os.path.dirname(os.path.abspath(__file__))
TARGETS = {'snap_share': ('WR', 'TE', 'RB'), 'rpr': ('WR', 'TE', 'RB'),
           'target_share': ('WR', 'TE', 'RB'), 'carry_share': ('RB',),
           'rz_carry_share': ('RB',)}
# P1's incumbent on the unconditional population, from run_unconditional.log.
P1_INCUMBENT = {'snap_share': 'lag1', 'rpr': 'lag1', 'target_share': 'ewma3',
                'carry_share': 'lag1', 'rz_carry_share': 'ewma3'}


def ewma(vals, hl=3.0):
    if not vals:
        return None
    lam = 0.5 ** (1 / hl); num = den = 0.0; w = 1.0
    for v in reversed(vals):
        num += w * v; den += w; w *= lam
    return num / den


def histories(rows, target):
    """For each row: prior values over ALL prior games, and over prior
    APPEARANCES only. Both strictly before this game."""
    allh = collections.defaultdict(list)
    apph = collections.defaultdict(list)
    for r in sorted(rows, key=lambda x: (x['ord'], x['team'], x['gsis_id'])):
        pid = r['gsis_id']
        r['_all'] = list(allh[pid]); r['_app'] = list(apph[pid])
        y = r.get(target)
        if y is not None:
            allh[pid].append(y)
            if r['appeared']:
                apph[pid].append(y)


def block_boot(recs, ka, kb, n=400, seed=20260907):
    rng = random.Random(seed)
    agg = collections.defaultdict(lambda: [0.0, 0.0, 0])
    for r in recs:
        g = agg[r['pid']]
        g[0] += abs(r['y'] - r[ka]); g[1] += abs(r['y'] - r[kb]); g[2] += 1
    vals = list(agg.values()); m = len(vals)
    if m < 5:
        return None
    d = []
    for _ in range(n):
        ea = eb = c = 0.0
        for _i in range(m):
            v = vals[rng.randrange(m)]
            ea += v[0]; eb += v[1]; c += v[2]
        if c:
            d.append(ea / c - eb / c)
    d.sort()
    return {'mean': float(np.mean(d)), 'lo': d[int(.025 * len(d))],
            'hi': d[int(.975 * len(d))], 'n_players': m}


def met(recs, key):
    y = np.array([r['y'] for r in recs], float)
    p = np.array([r[key] for r in recs], float)
    e = y - p
    ybar = y.mean(); sst = ((y - ybar) ** 2).sum()
    return {'mae': float(np.abs(e).mean()),
            'rmse': float(np.sqrt((e * e).mean())),
            'r': float(np.corrcoef(y, p)[0, 1]) if y.std() and p.std() else float('nan'),
            'r2': float(1 - (e * e).sum() / sst) if sst > 0 else float('nan'),
            'n': len(recs)}


def main():
    kick = A.kickoffs(); inj, _ = A.injuries(kick); dep = A.depth()
    rows = A.build(kick, inj, dep)
    POSALL = ('WR', 'TE', 'RB', 'QB')
    cand = [r for r in rows if r['position'] in POSALL
            and (r.get('f_n_prior') or 0) >= 1]

    # ---- Stage A probability for every candidate, trained on prior seasons --
    for r in cand:
        r['y_app'] = 1 if r['appeared'] else 0
    pa = {}
    for ev in A.EVAL:
        tr = [r for r in cand if r['season'] < ev]
        te = [r for r in cand if r['season'] == ev]
        if len(tr) < 500:
            continue
        use_inj = ev <= 2024
        m = A.fit_logistic([A.featurise(r, use_inj) for r in tr],
                           [r['y_app'] for r in tr])
        p = A.predict(m, [A.featurise(r, use_inj) for r in te])
        for r, v in zip(te, p):
            pa[id(r)] = float(v)
        print(f'stage A {ev}: n_train={len(tr)} n_test={len(te)} '
              f'injury_feature={use_inj} '
              f'brier={A.brier([r["y_app"] for r in te], p):.4f} '
              f'auc={A.auc([r["y_app"] for r in te], p):.4f}')

    out = {}
    for target, positions in TARGETS.items():
        sub = [r for r in cand if r['position'] in positions]
        histories(sub, target)
        out[target] = {}
        for ev in A.EVAL:
            tr = [r for r in sub if r['season'] < ev]
            prior_all = {}
            prior_app = {}
            for p_ in positions:
                v = [r[target] for r in tr
                     if r['position'] == p_ and r.get(target) is not None]
                va = [r[target] for r in tr
                      if r['position'] == p_ and r.get(target) is not None
                      and r['appeared']]
                if v:
                    prior_all[p_] = float(np.mean(v))
                if va:
                    prior_app[p_] = float(np.mean(va))
            recs = []
            for r in sub:
                if r['season'] != ev or r.get(target) is None:
                    continue
                if id(r) not in pa:
                    continue
                pri = prior_all.get(r['position'])
                pria = prior_app.get(r['position'])
                if pri is None or pria is None:
                    continue
                allv, appv = r['_all'], r['_app']
                # MODEL U -- unconditional, P1's incumbent on this population
                u_lag1 = allv[-1] if allv else pri
                u_ewma = ewma(allv) if allv else pri
                u = u_lag1 if P1_INCUMBENT[target] == 'lag1' else u_ewma
                # MODEL C -- conditional forecast, applied to everyone
                c = ewma(appv) if appv else pria
                # MODEL A x C -- the mixture
                p_app = pa[id(r)]
                recs.append({'pid': r['gsis_id'], 'y': r[target],
                             'row': r, 'p_app': p_app,
                             'U': u, 'U_lag1': u_lag1, 'U_ewma': u_ewma,
                             'C': c, 'AC': p_app * c,
                             'AC_u': p_app * (u_ewma if u_ewma is not None
                                              else pri)})
            if len(recs) < 200:
                continue
            per = {k: met(recs, k) for k in
                   ('U', 'U_lag1', 'U_ewma', 'C', 'AC', 'AC_u')}
            out[target][ev] = {
                'per_model': per,
                'AC_vs_U': block_boot(recs, 'AC', 'U'),
                'C_vs_U': block_boot(recs, 'C', 'U'),
                'AC_vs_C': block_boot(recs, 'AC', 'C'),
                'subgroups': {},
            }
            def sub_(name, pred):
                sel = [x for x in recs if pred(x)]
                if len(sel) >= 60:
                    out[target][ev]['subgroups'][name] = {
                        'n': len(sel),
                        **{k: met(sel, k) for k in ('U', 'C', 'AC')}}
            for p_ in positions:
                sub_(f'pos={p_}', lambda x, q=p_: x['row']['position'] == q)
            sub_('role=stable', lambda x: x['row'].get('role_change') == 0)
            sub_('role=change', lambda x: x['row'].get('role_change') == 1)
            sub_('appeared', lambda x: x['row']['appeared'] == 1)
            sub_('did_not_appear', lambda x: x['row']['appeared'] == 0)
            sub_('returning', lambda x: (x['row'].get('f_consec_missed') or 0) >= 1)
            sub_('lowhist(<4)', lambda x: (x['row'].get('f_n_prior') or 0) < 4)
            sub_('starter_prior', lambda x: (x['row'].get('f_prev_snap') or 0) >= 0.5)
            sub_('backup_prior', lambda x: (x['row'].get('f_prev_snap') or 0) < 0.5)

    json.dump(out, open(f'{HERE}/stage_bc_results.json', 'w'), indent=1,
              default=float)

    for target in TARGETS:
        print(f'\n=== {target}')
        for ev, d in out[target].items():
            p = d['per_model']
            b = d['AC_vs_U']
            verdict = ('AxC BEATS U' if b and b['hi'] < 0 else
                       'AxC does NOT beat U')
            print(f' {ev} n={p["U"]["n"]:6d} '
                  f'U={p["U"]["mae"]:.4f}(r={p["U"]["r"]:.3f}) '
                  f'C={p["C"]["mae"]:.4f}(r={p["C"]["r"]:.3f}) '
                  f'AxC={p["AC"]["mae"]:.4f}(r={p["AC"]["r"]:.3f}) '
                  f'| AxC-U {b["mean"]:+.5f} [{b["lo"]:+.5f},{b["hi"]:+.5f}] '
                  f'{verdict}')
            sg = d['subgroups']
            for k in ('role=stable', 'role=change'):
                if k in sg:
                    s = sg[k]
                    print(f'      {k:<14} n={s["n"]:5d} U={s["U"]["mae"]:.4f} '
                          f'C={s["C"]["mae"]:.4f} AxC={s["AC"]["mae"]:.4f}')


if __name__ == '__main__':
    main()
