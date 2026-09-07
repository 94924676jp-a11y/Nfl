"""P4C-CARRY: the 2^3 oracle factorial over team volume x share x appearance.

The P4C/P4D machinery is imported unchanged. The only thing this module does is
substitute a realised component for a predicted one, one corner at a time, and
score the resulting carry-count distribution.

CORNER ALGEBRA, and it closes exactly:
    count_ij = T_gj * avail_gj * w_ij A_ij / sum_g(w A)
    all-oracle = T* * m* * S* A* / m* = T* * S* = realised carries
`avail` sits with TEAM because it is a team-level quantity; that is what makes
the corner close, and the identity is checked, not asserted.
"""
import collections, itertools, json, math, os, pickle, sys, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
P4C = os.path.abspath(os.path.join(HERE, '..', 'p4c'))
P5A = os.path.abspath(os.path.join(HERE, '..', 'p5a'))
sys.path.insert(0, HERE); sys.path.insert(0, P4C); sys.path.insert(0, P5A)
import p4c_lib as CL                                           # noqa: E402
import p4c_build as CB                                         # noqa: E402
import p5a_lib as PL                                           # noqa: E402
from run_p4c import groups_of                                  # noqa: E402

CLS = 'carries'
EVAL = [2022, 2023, 2024, 2025]
# Pre-declared, section 5, before any result.
THRESH = [0.5, 4.5, 9.5, 14.5, 19.5]
COMPONENTS = ('T', 'S', 'A')
CORNERS = [frozenset(c) for r in range(4)
           for c in itertools.combinations(COMPONENTS, r)]


def cname(s):
    return 'A_baseline' if not s else 'O_' + '_'.join(sorted(s))


def score_counts(draws, y, rng):
    y = np.asarray(y, float)
    mean = draws.mean(axis=1)
    e = y - mean
    sst = ((y - y.mean()) ** 2).sum()
    o = {'n': int(len(y)), 'crps': float(PL.crps_samples(draws, y).mean()),
         'mae': float(np.abs(e).mean()),
         'rmse': float(math.sqrt((e * e).mean())), 'bias': float(e.mean()),
         'r': (float(np.corrcoef(y, mean)[0, 1]) if mean.std() > 0 else None),
         'r2': float(1 - (e * e).sum() / sst) if sst > 0 else None,
         'sd_pred': float(mean.std(ddof=1)), 'sd_actual': float(y.std(ddof=1)),
         'p_zero_pred': float((draws < 0.5).mean()),
         'p_zero_actual': float((y < 0.5).mean()),
         'coverage': {}}
    for L in PL.LEVELS:
        lo = np.percentile(draws, 100 * (1 - L) / 2, axis=1)
        hi = np.percentile(draws, 100 * (1 + L) / 2, axis=1)
        o['coverage'][str(int(L * 100))] = {
            'coverage': float(((y >= lo) & (y <= hi)).mean()),
            'mean_width': float((hi - lo).mean())}
    o['randomised_pit'] = PL.pit_stats(PL.rpit(draws, y, rng))
    o['thresholds'] = {}
    for t in THRESH:
        p = (draws > t).mean(axis=1)
        ob = (y > t).astype(float)
        o['thresholds'][str(t)] = {
            'mean_p': float(p.mean()), 'observed': float(ob.mean()),
            'calibration_in_the_large': float(p.mean() - ob.mean()),
            'brier': float(((p - ob) ** 2).mean())}
    return o


def shapley(v):
    """v maps frozenset -> value, v(empty) = 0. Three components."""
    n = 3
    fact = {0: 1, 1: 1, 2: 2, 3: 6}
    out = {}
    for i in COMPONENTS:
        rest = [c for c in COMPONENTS if c != i]
        tot = 0.0
        for r in range(3):
            for sub in itertools.combinations(rest, r):
                Sset = frozenset(sub)
                w = fact[len(Sset)] * fact[n - len(Sset) - 1] / fact[n]
                tot += w * (v[Sset | {i}] - v[Sset])
        out[i] = tot
    return out


def interactions(v):
    """Standard factorial interaction terms on the REDUCTION scale."""
    m = {c: v[frozenset([c])] for c in COMPONENTS}
    out = {'main_' + c: m[c] for c in COMPONENTS}
    for a, b in itertools.combinations(COMPONENTS, 2):
        out[f'int_{a}{b}'] = v[frozenset([a, b])] - m[a] - m[b]
    out['int_TSA'] = (v[frozenset(COMPONENTS)]
                      - sum(m.values())
                      - sum(out[f'int_{a}{b}']
                            for a, b in itertools.combinations(COMPONENTS, 2)))
    return out


def main():
    t0 = time.time()
    rows = CB.load_panel()
    vol = CB.load_volume()
    pa = CB.appearance(rows)
    sub = CB.prepare_class(rows, CLS)
    c = CL.CLASSES[CLS]
    D = pickle.load(open(f'{P5A}/pg.pkl', 'rb'))
    pgi = {(r['season'], r['week'], r['team'], r['gsis_id']): r for r in D['pg']}
    OUT = {}
    for ev in EVAL:
        store = vol[(c['den'], ev)]
        par = CB.fit_params(sub, CLS, ev, rows)
        te = [r for r in sub if r['season'] == ev and r.get('s_carries') is not None
              and id(r) in pa and (r.get('f_n_prior') or 0) >= 1
              and r['_C'] is not None and (r['team'], r['ord']) in store['index']]
        te.sort(key=lambda r: (r['ord'], r['team'], r['gsis_id']))
        n = len(te)
        starts, cg, gkeys = groups_of(te)
        G = len(starts)
        ti = np.array([store['index'][(r['team'], r['ord'])] for r in te])
        gti = ti[starts]
        # ---- FROZEN predicted components ---------------------------------
        mass = CB.mass_draws('C', par, G, CL.M_DRAWS,
                             np.random.default_rng(CL.SEED + 5002))
        avail_pred = (1.0 - mass).astype(np.float32)            # (G, M)
        W_pred = CB.gen_weights('C', np.array([r['_C'] for r in te], np.float32),
                                [r['position'] for r in te], par, CLS, n,
                                CL.M_DRAWS, np.random.default_rng(CL.SEED + 3034))
        p_app = np.array([pa[id(r)] for r in te], np.float32)
        A_pred = (np.random.default_rng(CL.SEED + 1009)
                  .random((n, CL.M_DRAWS), np.float32) < p_app[:, None])
        T_pred = store['B'][gti]                                # (G, M)
        # ---- REALISED components -----------------------------------------
        Tstar = store['realized'][gti].astype(np.float64)       # (G,)
        y = np.array([r['y_carries'] for r in te], float)
        A_star = np.array([1.0 if r['appeared'] else 0.0 for r in te], np.float32)
        Sstar = np.array([(r['y_carries'] / Tstar[gi]) if Tstar[gi] > 0 else 0.0
                          for gi, r in
                          ((np.searchsorted(starts, i, 'right') - 1, rr)
                           for i, rr in enumerate(te))], np.float64)
        mstar = CL.gsum((Sstar * A_star)[:, None], starts)[:, 0]  # (G,)

        corners, crps_row = {}, {}
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
            te_ = CL.gexp(tot, cg)
            S = np.divide(WA * CL.gexp(AV, cg), te_,
                          out=np.zeros_like(WA), where=te_ > 1e-12)
            S, _nb = CL.waterfill(S, starts, cg, 1.0)
            draws = (CL.gexp(T, cg) * S).astype(np.float32)
            nm = cname(cs)
            corners[nm] = score_counts(draws, y, np.random.default_rng(PL.SEED + 31))
            crps_row[nm] = PL.crps_samples(draws, y)
            if len(cs) == 3:
                corners[nm]['max_abs_identity_error'] = float(
                    np.abs(draws.mean(axis=1) - y).max())
            del draws, S, WA
        base = corners['A_baseline']['crps']
        v = {cs: base - corners[cname(cs)]['crps'] for cs in CORNERS}
        sh = shapley(v)
        iv = interactions(v)
        # per-row Shapley for subgroup attribution
        vr = {cs: crps_row['A_baseline'] - crps_row[cname(cs)] for cs in CORNERS}
        shr = {i: np.zeros(n) for i in COMPONENTS}
        fact = {0: 1, 1: 1, 2: 2, 3: 6}
        for i in COMPONENTS:
            rest = [x for x in COMPONENTS if x != i]
            for r in range(3):
                for s_ in itertools.combinations(rest, r):
                    Ss = frozenset(s_)
                    w = fact[len(Ss)] * fact[3 - len(Ss) - 1] / fact[3]
                    shr[i] += w * (vr[Ss | {i}] - vr[Ss])
        OUT[ev] = {
            'n': n, 'n_team_games': G,
            'corners': corners,
            'value_function': {cname(cs): v[cs] for cs in CORNERS},
            'shapley': sh,
            'shapley_pct_of_total': {k: 100 * x / v[frozenset(COMPONENTS)]
                                     for k, x in sh.items()},
            'interactions': iv,
            'total_reduction': v[frozenset(COMPONENTS)],
        }
        with open(f'{HERE}/rowlevel_{ev}.pkl', 'wb') as f:
            pickle.dump({'keys': [(r['season'], r['week'], r['team'],
                                   r['gsis_id']) for r in te],
                         'y': y, 'p_app': p_app, 'A_star': A_star,
                         'Sstar': Sstar, 'Tstar_row': Tstar[
                             np.searchsorted(starts, np.arange(n), 'right') - 1],
                         'shapley_rows': {k: vv for k, vv in shr.items()},
                         'crps_rows': crps_row,
                         'starts': starts, 'counts_g': cg,
                         'position': [r['position'] for r in te],
                         'role_change': [r.get('role_change') for r in te],
                         'info_quality': [r.get('info_quality') for r in te],
                         'C_pre': np.array([r['_C'] for r in te]),
                         }, f, protocol=4)
        print(f'\n{ev} n={n} G={G}  total CRPS reduction '
              f'{v[frozenset(COMPONENTS)]:.4f} from base {base:.4f}')
        for cs in CORNERS:
            s = corners[cname(cs)]
            print(f'  {cname(cs):16s} CRPS {s["crps"]:7.4f} '
                  f'({100*(s["crps"]-base)/base:+7.2f}%) MAE {s["mae"]:6.3f} '
                  f'r {(s["r"] or 0):+.3f} rPIT {s["randomised_pit"]["chi2"]:8.1f}'
                  + (f'  identity |err| {s.get("max_abs_identity_error", 0):.2e}'
                     if len(cs) == 3 else ''))
        print('  Shapley %: ' + '  '.join(
            f'{k}={OUT[ev]["shapley_pct_of_total"][k]:5.1f}%' for k in COMPONENTS))
        print('  interactions: ' + '  '.join(
            f'{k}={x:+.4f}' for k, x in iv.items() if k.startswith('int')))
        json.dump(OUT, open(f'{HERE}/p4cc_results.json', 'w'), indent=1)
    print(f'\ndone in {time.time()-t0:.0f}s -> p4cc_results.json')


if __name__ == '__main__':
    main()
