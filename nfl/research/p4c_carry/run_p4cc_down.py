"""P4C-CARRY items 23 and 24: frozen P5A propagation, and the carry-bias check.

The conversion layer is P5A's CONTROL, imported and not refitted: the pooled
prior-season per-carry empirical distribution with a zero location shift. Only
the carry counts change between corners, so anything that moves in rushing-yard
space is the carry decomposition propagating and nothing else.
"""
import collections, csv, itertools, json, math, os, pickle, sys, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
P4B = os.path.abspath(os.path.join(HERE, '..', 'p4b'))
P4C = os.path.abspath(os.path.join(HERE, '..', 'p4c'))
P5A = os.path.abspath(os.path.join(HERE, '..', 'p5a'))
sys.path.insert(0, HERE); sys.path.insert(0, P4C); sys.path.insert(0, P5A)
import p4c_lib as CL                                           # noqa: E402
import p4c_build as CB                                         # noqa: E402
import p5a_lib as PL                                           # noqa: E402
from run_p4c import groups_of                                  # noqa: E402
from run_p4cc import CORNERS, cname, shapley, interactions, COMPONENTS  # noqa

CLS = 'carries'
EVAL = [2022, 2023, 2024, 2025]


def main():
    t0 = time.time()
    rows = CB.load_panel(); vol = CB.load_volume(); pa = CB.appearance(rows)
    sub = CB.prepare_class(rows, CLS); c = CL.CLASSES[CLS]
    D = pickle.load(open(f'{P5A}/pg.pkl', 'rb'))
    carries, pg = D['carries'], D['pg']
    pgi = {(r['season'], r['week'], r['team'], r['gsis_id']): r for r in pg}
    OUT = {}
    for ev in EVAL:
        store = vol[(c['den'], ev)]
        par = CB.fit_params(sub, CLS, ev, rows)
        te = [r for r in sub if r['season'] == ev and r.get('s_carries') is not None
              and id(r) in pa and (r.get('f_n_prior') or 0) >= 1
              and r['_C'] is not None and (r['team'], r['ord']) in store['index']]
        te.sort(key=lambda r: (r['ord'], r['team'], r['gsis_id']))
        n = len(te)
        starts, cg, gk = groups_of(te)
        G = len(starts)
        ti = np.array([store['index'][(r['team'], r['ord'])] for r in te])
        gti = ti[starts]
        mass = CB.mass_draws('C', par, G, CL.M_DRAWS,
                             np.random.default_rng(CL.SEED + 5002))
        avail_pred = (1.0 - mass).astype(np.float32)
        W_pred = CB.gen_weights('C', np.array([r['_C'] for r in te], np.float32),
                                [r['position'] for r in te], par, CLS, n,
                                CL.M_DRAWS, np.random.default_rng(CL.SEED + 3034))
        p_app = np.array([pa[id(r)] for r in te], np.float32)
        A_pred = (np.random.default_rng(CL.SEED + 1009)
                  .random((n, CL.M_DRAWS), np.float32) < p_app[:, None])
        T_pred = store['B'][gti]
        Tstar = store['realized'][gti].astype(np.float64)
        gidx = np.searchsorted(starts, np.arange(n), 'right') - 1
        ycar = np.array([r['y_carries'] for r in te], float)
        A_star = np.array([1.0 if r['appeared'] else 0.0 for r in te], np.float32)
        Sstar = np.array([(ycar[i] / Tstar[gidx[i]]) if Tstar[gidx[i]] > 0 else 0.0
                          for i in range(n)], np.float64)
        mstar = CL.gsum((Sstar * A_star)[:, None], starts)[:, 0]
        keep = [pgi.get((r['season'], r['week'], r['team'], r['gsis_id']))
                for r in te]
        yyd = np.array([q['rush_yards'] if q else 0.0 for q in keep], float)
        # FROZEN P5A control conversion: pooled prior-season empirical, no shift
        trc = [x for x in carries if x['season'] < ev]
        pool = PL.Pool([x['yards'] for x in trc])
        pool.body_or_stuff = pool.y[pool.y < PL.EXPLOSIVE]
        pars = [{'shift': 0.0} for _ in range(n)]
        res = {}
        pred_mean_carries = {}
        for cs in CORNERS:
            T = (np.repeat(Tstar[:, None], CL.M_DRAWS, 1).astype(np.float32)
                 if 'T' in cs else T_pred)
            AV = (np.repeat(mstar[:, None], CL.M_DRAWS, 1).astype(np.float32)
                  if 'T' in cs else avail_pred)
            Wm = (np.repeat(Sstar[:, None], CL.M_DRAWS, 1).astype(np.float32)
                  if 'S' in cs else W_pred)
            Ad = (np.repeat(A_star[:, None], CL.M_DRAWS, 1).astype(bool)
                  if 'A' in cs else A_pred)
            WA = Wm * Ad
            tot = CL.gsum(WA, starts)
            den = CL.gexp(tot, cg)
            S = np.divide(WA * CL.gexp(AV, cg), den, out=np.zeros_like(WA),
                          where=den > 1e-12)
            S, _ = CL.waterfill(S, starts, cg, 1.0)
            cnt = np.clip(np.rint(CL.gexp(T, cg) * S), 0, None).astype(np.int32)
            if not cs:
                pred_mean_carries['A_baseline'] = cnt.mean(axis=1)
            Y = PL.compound(cnt, 'emp_shift', pool, pars, PL.SEED + 77)
            sc = PL.score(Y, yyd, np.random.default_rng(PL.SEED + 31))
            res[cname(cs)] = {k: sc[k] for k in
                              ('crps', 'mae', 'rmse', 'r', 'bias', 'n')}
            res[cname(cs)]['rpit'] = sc['randomised_pit']['chi2']
            del Y, cnt, S, WA
        base = res['A_baseline']['crps']
        v = {cs: base - res[cname(cs)]['crps'] for cs in CORNERS}
        sh = shapley(v)
        tot_r = v[frozenset(COMPONENTS)]
        # ---- 24. carry bias by efficiency-history cohort -------------------
        pm = pred_mean_carries['A_baseline']
        eff = []
        for k in [(r['season'], r['week'], r['team'], r['gsis_id']) for r in te]:
            q = pgi.get(k)
            eff.append('none' if not (q and q['p'] and q['p']['n'] >= 25)
                       else ('high' if q['p']['ypc'] >= 4.3 else 'low'))
        eff = np.array(eff)
        bias = {}
        for u in ('high', 'low', 'none'):
            m = eff == u
            if m.sum() < 40:
                continue
            bias[u] = {'n': int(m.sum()),
                       'mean_predicted_carries': float(pm[m].mean()),
                       'mean_realised_carries': float(ycar[m].mean()),
                       'bias_pred_minus_real': float((pm[m] - ycar[m]).mean()),
                       'relative_bias_pct': float(
                           100 * (pm[m] - ycar[m]).mean()
                           / max(ycar[m].mean(), 1e-9))}
        OUT[ev] = {'n': n, 'downstream': res, 'shapley_yards': sh,
                   'shapley_pct': {k: 100 * x / tot_r for k, x in sh.items()},
                   'total_reduction_yards': tot_r,
                   'carry_bias_by_efficiency_history': bias}
        print(f'\n{ev} downstream rushing yards (frozen P5A control conversion)')
        for cs in CORNERS:
            s = res[cname(cs)]
            print(f'  {cname(cs):16s} CRPS {s["crps"]:8.4f} '
                  f'({100*(s["crps"]-base)/base:+7.2f}%) MAE {s["mae"]:7.3f} '
                  f'r {(s["r"] or 0):+.3f} rPIT {s["rpit"]:7.1f}')
        print('  Shapley % (yards): ' + '  '.join(
            f'{k}={OUT[ev]["shapley_pct"][k]:5.1f}%' for k in COMPONENTS))
        print('  carry bias by efficiency history: ' + '  '.join(
            f'{u}: pred {b["mean_predicted_carries"]:.2f} vs real '
            f'{b["mean_realised_carries"]:.2f} ({b["relative_bias_pct"]:+.1f}%)'
            for u, b in bias.items()))
        json.dump(OUT, open(f'{HERE}/p4cc_downstream.json', 'w'), indent=1)
    print(f'\ndone in {time.time()-t0:.0f}s -> p4cc_downstream.json')


if __name__ == '__main__':
    main()
