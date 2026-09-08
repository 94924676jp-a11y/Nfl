"""TD1: touchdown / red-zone oracle decomposition, receiving and rushing.

Pre-registration sha256
8effcb5a95ec1cfe721dde743c3f394889135c3e8c423156163e34ad849f2d6c.

Identity: TD = (TeamOpp x Share) x [Z*k_rz + (1-Z)*k_nrz], components V S Z K.

EXPLORATORY. 2022-2025 are heavily mined. Nothing may be promoted.
"""
import bisect, collections, itertools, json, math, os, pickle, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'rc1'))
import rc1_lib as L                                            # noqa: E402

COMPONENTS = ('V', 'S', 'Z', 'K')
SUBSETS = [frozenset(c) for k in range(5)
           for c in itertools.combinations(COMPONENTS, k)]
M = 1000
K_SHRINK = 4.0
PREREG = '8effcb5a95ec1cfe721dde743c3f394889135c3e8c423156163e34ad849f2d6c'


def shapley(vals):
    n = len(COMPONENTS)
    phi = {}
    for c in COMPONENTS:
        rest = [x for x in COMPONENTS if x != c]
        tot = 0.0
        for k in range(len(rest) + 1):
            for Ss in itertools.combinations(rest, k):
                fs = frozenset(Ss)
                w = math.factorial(k) * math.factorial(n - k - 1) / math.factorial(n)
                tot += w * (vals[fs | {c}] - vals[fs])
        phi[c] = tot
    return phi


def load(kind):
    """kind = 'rec' or 'rush'."""
    d = pickle.load(open(f'{HERE}/td.pkl', 'rb'))
    P, T = d['player'], d['team']
    rows, sub = L.load()
    L.attach_prior(sub)
    if kind == 'rec':
        opp, rzo, td, topp = 'targets', 'rz_targets', 'rec_td', 'targets'
        pos_ok = ('WR', 'TE', 'RB')
    else:
        opp, rzo, td, topp = 'carries', 'rz_carries', 'rush_td', 'carries'
        pos_ok = ('WR', 'TE', 'RB')
    out = []
    for r in sub:
        if r['position'] not in pos_ok:
            continue
        k = (r['season'], r['week'], r['team'], r['gsis_id'])
        m = P.get(k) or {}
        t = T.get((r['season'], r['week'], r['team'])) or {}
        r['N'] = int(m.get(opp, 0))
        r['RZ'] = int(m.get(rzo, 0))
        r['TD'] = int(m.get(td, 0))
        r['TEAM_N'] = int(t.get(topp, 0))
        out.append(r)
    return out


def attach(rs):
    """Prior-only histories, strict ordinal prefix cut."""
    hist = collections.defaultdict(list); hord = collections.defaultdict(list)
    for r in sorted(rs, key=lambda x: (x['ord'], x['team'], x['gsis_id'])):
        pid = r['gsis_id']
        i = bisect.bisect_left(hord[pid], r['ord'])
        past = [x for x in hist[pid][:i] if x['appeared']]
        r['h_N'] = [x['N'] for x in past]
        r['h_teamN'] = [x['TEAM_N'] for x in past]
        r['h_share'] = [x['N'] / x['TEAM_N'] for x in past if x['TEAM_N'] > 0]
        r['h_z'] = [x['RZ'] / x['N'] for x in past if x['N'] > 0]
        r['h_td_rz'] = (sum(x['TD'] for x in past if x['RZ'] > 0),
                        sum(x['RZ'] for x in past))
        r['h_td_all'] = (sum(x['TD'] for x in past), sum(x['N'] for x in past))
        r['h_n2'] = len(past)
        hist[pid].append(r); hord[pid].append(r['ord'])
    return rs


def pools(rs, ev):
    p = collections.defaultdict(lambda: collections.defaultdict(list))
    agg = collections.defaultdict(lambda: collections.Counter())
    for r in rs:
        if r['season'] >= ev or not r['appeared']:
            continue
        q = r['position']
        p[q]['teamN'].append(r['TEAM_N'])
        if r['TEAM_N'] > 0: p[q]['share'].append(r['N'] / r['TEAM_N'])
        if r['N'] > 0: p[q]['z'].append(r['RZ'] / r['N'])
        agg[q]['td_rz'] += r['TD'] if r['RZ'] > 0 else 0
        agg[q]['rz'] += r['RZ']
        agg[q]['td'] += r['TD']; agg[q]['n'] += r['N']
    out = {}
    for q in p:
        rz_rate = agg[q]['td_rz'] / agg[q]['rz'] if agg[q]['rz'] else 0.0
        nrz_n = agg[q]['n'] - agg[q]['rz']
        nrz_td = agg[q]['td'] - agg[q]['td_rz']
        out[q] = {'teamN': np.array(p[q]['teamN'], float),
                  'share': np.array(p[q]['share'], float),
                  'z': np.array(p[q]['z'], float),
                  'k_rz': rz_rate,
                  'k_nrz': (nrz_td / nrz_n) if nrz_n > 0 else 0.0}
    return out


def simulate(rs, ev, allrows, oracle=(), seed=L.SEED, k_candidate=None):
    """`k_candidate` maps a row to a candidate OVERALL conversion rate.

    Substitution is DRAW-PRESERVING and mean-shifting: the historical
    k_rz / k_nrz structure is retained and both are scaled by the single factor
    that makes the implied overall rate equal the candidate's. Replacing them
    with a point value would collapse the location structure, which is a
    different component (Z) and not the candidate's to change."""
    po = pools(allrows, ev)
    out = np.zeros((len(rs), M), float)
    for idx, r in enumerate(rs):
        q = po.get(r['position'])
        if q is None:
            continue
        rng = np.random.default_rng(
            [seed, int(r['ord']),
             int.from_bytes(str(r['gsis_id']).encode()[-8:], 'little')])
        w = r['h_n2'] / (r['h_n2'] + K_SHRINK)

        def mix(own, pool):
            own = np.asarray(own, float)
            if len(own) == 0:
                return pool[rng.integers(0, len(pool), M)] if len(pool) else np.zeros(M)
            use = rng.random(M) < w
            return np.where(use, own[rng.integers(0, len(own), M)],
                            pool[rng.integers(0, len(pool), M)] if len(pool)
                            else 0.0)

        V = (np.full(M, r['TEAM_N'], float) if 'V' in oracle
             else mix(r['h_teamN'], q['teamN']))
        S = (np.full(M, (r['N'] / r['TEAM_N']) if r['TEAM_N'] > 0 else 0.0, float)
             if 'S' in oracle else mix(r['h_share'], q['share']))
        N = V * S
        Z = (np.full(M, (r['RZ'] / r['N']) if r['N'] > 0 else 0.0, float)
             if 'Z' in oracle else np.clip(mix(r['h_z'], q['z']), 0, 1))
        if 'K' in oracle:
            k_rz = (r['TD'] / r['RZ']) if r['RZ'] > 0 else 0.0
            nrz = r['N'] - r['RZ']
            td_rz = r['TD'] if r['RZ'] > 0 else 0
            k_nrz = ((r['TD'] - td_rz) / nrz) if nrz > 0 else 0.0
        else:
            a, b = r['h_td_rz']
            k_rz = (w * (a / b) + (1 - w) * q['k_rz']) if b > 0 else q['k_rz']
            ta, tn = r['h_td_all']
            nrz_n = tn - b
            k_nrz = ((w * ((ta - a) / nrz_n) + (1 - w) * q['k_nrz'])
                     if nrz_n > 0 else q['k_nrz'])
        if k_candidate is not None and 'K' not in oracle:
            phat = k_candidate(r)
            if phat is not None:
                implied = float(np.mean(Z * k_rz + (1 - Z) * k_nrz))
                if implied > 1e-12:
                    f = phat / implied
                    k_rz = k_rz * f
                    k_nrz = k_nrz * f
        out[idx] = N * (Z * k_rz + (1 - Z) * k_nrz)
    return out


def crps(D, y):
    return L.crps_matrix(D, y)


def main():
    OUT = {'prereg_sha256': PREREG, 'identity':
           'TD = (TeamOpp x Share) x [Z*k_rz + (1-Z)*k_nrz]',
           'label': 'EXPLORATORY -- heavily mined; no promotion',
           'end_zone_targets': 'UNAVAILABLE -- yardline_100 is the line of '
                               'scrimmage, not target depth',
           'kinds': {}}
    for kind in ('rec', 'rush'):
        rs_all = attach(load(kind))
        print(f'\n=== {kind.upper()} TD ===')
        per = {fs: [] for fs in SUBSETS}
        Y, G = [], []
        ident = {}
        for ev in L.EVAL:
            rs = [r for r in rs_all if L.eligible(r, ev)]
            y = np.array([r['TD'] for r in rs], float)
            Y.append(y); G += [r['game_id'] for r in rs]
            for fs in SUBSETS:
                D = simulate(rs, ev, rs_all, oracle=tuple(sorted(fs)))
                per[fs].append(crps(D, y))
                if fs == frozenset(COMPONENTS):
                    ident[ev] = float(np.abs(D.mean(1) - y).max())
            print(f'  {ev}: n={len(rs):5d}  mean TD {y.mean():.4f}  '
                  f'identity |err| {ident[ev]:.2e} -> '
                  f'{"VALID" if ident[ev] < 1e-9 else "INVALID"}')
        Y = np.concatenate(Y)
        C = {fs: np.concatenate(per[fs]) for fs in SUBSETS}
        base = float(C[frozenset()].mean())
        vals = {fs: base - float(C[fs].mean()) for fs in SUBSETS}
        phi = shapley(vals); tot = sum(phi.values())
        # game-clustered bootstrap
        by = collections.defaultdict(list)
        for i2, g in enumerate(G): by[g].append(i2)
        keys = list(by); idxs = [np.array(by[k]) for k in keys]
        rng = np.random.default_rng(L.SEED)
        boot = {c: [] for c in COMPONENTS}
        for _ in range(400):
            pick = rng.integers(0, len(keys), len(keys))
            sel = np.concatenate([idxs[j] for j in pick])
            b = float(C[frozenset()][sel].mean())
            v = {fs: b - float(C[fs][sel].mean()) for fs in SUBSETS}
            p = shapley(v)
            for c in COMPONENTS: boot[c].append(p[c])
        # Brier on P(TD>=1) for the baseline
        D0 = np.concatenate([simulate([r for r in rs_all if L.eligible(r, ev)],
                                      ev, rs_all) for ev in L.EVAL])
        p1 = (D0 >= 0.5).mean(1)
        brier = float(((p1 - (Y >= 1)) ** 2).mean())
        OUT['kinds'][kind] = {
            'n': int(len(Y)), 'n_games': len(set(G)), 'mean_TD': float(Y.mean()),
            'baseline_crps': base, 'brier_TD_ge_1': brier,
            'identity_max_abs_error': ident,
            'identity_valid': all(v < 1e-9 for v in ident.values()),
            'coalition_crps_reduction': {'+'.join(sorted(k)) or 'baseline': v
                                         for k, v in vals.items()},
            'shapley_crps': phi,
            'shapley_pct': {k: 100 * v / tot for k, v in phi.items()},
            'shapley_ci': {c: {'lo': float(np.quantile(boot[c], 0.025)),
                               'hi': float(np.quantile(boot[c], 0.975))}
                           for c in COMPONENTS},
            'efficiency_gap': tot - vals[frozenset(COMPONENTS)]}
        print(f'  baseline CRPS {base:.5f}  Brier(TD>=1) {brier:.5f}  '
              f'mean TD {Y.mean():.4f}')
        for c in COMPONENTS:
            ci = OUT['kinds'][kind]['shapley_ci'][c]
            print(f'    {c}: {phi[c]:8.5f}  {100*phi[c]/tot:6.2f}%  '
                  f'95% CI [{ci["lo"]:.5f}, {ci["hi"]:.5f}]')
        print(f'    efficiency gap {tot - vals[frozenset(COMPONENTS)]:.2e}')
    json.dump(OUT, open(f'{HERE}/td1_results.json', 'w'), indent=1, default=str)
    print('\nwrote td1_results.json')
    return 0


if __name__ == '__main__':
    sys.exit(main())
