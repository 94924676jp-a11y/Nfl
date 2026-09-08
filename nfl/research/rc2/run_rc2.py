"""RC2: the four predeclared calibration repairs, scored against the frozen baseline.

Pre-registration sha256
65c5e295ba864a1dc5b82f39f29667c295b100a66a80e4602129b6fc8f74db0e, committed
before any repair was implemented.

EVERY repair parameter is estimated on TRAINING SEASONS ONLY and applied to the
evaluation season. A repair fitted on the evaluation season is a different and
invalid study, and a test asserts the training rows carry no evaluation season.

EXPLORATORY. 2022-2025 are heavily mined. Nothing here may be promoted.
"""
import collections, json, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'rc1'))
sys.path.insert(0, HERE)
import rc1_lib as L                                            # noqa: E402
import rc1_sim as S                                            # noqa: E402

ARMS = ('R0', 'R1', 'R2', 'R3', 'R4')
PREREG = '65c5e295ba864a1dc5b82f39f29667c295b100a66a80e4602129b6fc8f74db0e'


def cohort(r):
    n = r.get('q_n_prior_app') or 0
    return '<4' if n < 4 else '4-9' if n < 10 else '10-24' if n < 25 else '25+'


def fit_repairs(sub, ev, rng):
    """All three repairs, estimated on season < ev ONLY."""
    tr = [r for r in sub if r['season'] < ev and L.eligible(r)]
    assert all(r['season'] < ev for r in tr), 'TRAINING LEAKED THE EVAL SEASON'

    # --- R1: per-history-cohort centring factor for T ---------------------
    num = collections.defaultdict(float)
    den = collections.defaultdict(float)
    for r in tr:
        w = r['h_n'] / (r['h_n'] + L.K_SHRINK)
        own = np.mean(r['h_T']) if r['h_T'] else 0.0
        # the baseline's own implied mean T for this row
        num[cohort(r)] += r['T']
        den[cohort(r)] += w * own + (1 - w) * _poolmeanT(sub, ev, r)
    r1 = {k: (num[k] / den[k] if den[k] > 0 else 1.0) for k in num}

    # --- R2: zero-target probability per position x cohort ----------------
    zn = collections.defaultdict(int); zd = collections.defaultdict(int)
    for r in tr:
        k = (r['position'], cohort(r))
        zd[k] += 1
        zn[k] += 1 if r['T'] == 0 else 0
    r2 = {k: (zn[k] / zd[k]) for k in zd if zd[k] >= 30}

    # --- R3: variance scale per position x volume tercile -----------------
    #   estimated from the TRAINING seasons' own simulated spread vs residual
    trs = [r for r in tr if r['season'] == ev - 1]
    r3 = {}
    if len(trs) >= 500:
        D = S.simulate(trs, ev - 1, sub)
        y = np.array([r['Y'] for r in trs], float)
        p = D.mean(1)
        vol = np.array([_voltile(r) for r in trs])
        pos = np.array([r['position'] for r in trs])
        for ps in ('WR', 'TE', 'RB'):
            for vt in (0, 1, 2):
                m = (pos == ps) & (vol == vt)
                if m.sum() < 100:
                    continue
                w_sd = float(D[m].std(1).mean())
                r_sd = float((y[m] - p[m]).std(ddof=1))
                r3[(ps, vt)] = (r_sd / w_sd) if w_sd > 1e-9 else 1.0
    return r1, r2, r3


_POOLC = {}


def _poolmeanT(sub, ev, r):
    k = (ev, r['position'])
    if k not in _POOLC:
        pT, _pV, _pr = S.pools(sub, ev)
        for ps, a in pT.items():
            _POOLC[(ev, ps)] = float(a.mean())
    return _POOLC.get(k, 0.0)


_VOLQ = {}


def _voltile(r):
    v = r.get('h_mean_T') or 0.0
    return 0 if v < 1.5 else 1 if v < 3.5 else 2


def apply_repair(D, rs, arm, r1, r2, r3, rng):
    """Repairs act on the DRAW MATRIX, never on the model's information."""
    D = D.copy()
    if arm in ('R1', 'R4'):
        f = np.array([r1.get(cohort(r), 1.0) for r in rs])[:, None]
        D = D * f                       # mean-shifting, CV-preserving
    if arm in ('R2', 'R4'):
        for i, r in enumerate(rs):
            p = r2.get((r['position'], cohort(r)))
            if p is None:
                continue
            cur = float((D[i] == 0).mean())
            if p > cur:                 # force extra zeros, chosen at random
                need = int(round((p - cur) * D.shape[1]))
                nz = np.flatnonzero(D[i] > 0)
                if need > 0 and len(nz) > need:
                    D[i, rng.choice(nz, need, replace=False)] = 0.0
    if arm in ('R3', 'R4'):
        for i, r in enumerate(rs):
            s = r3.get((r['position'], _voltile(r)))
            if s is None or abs(s - 1.0) < 1e-9:
                continue
            mu = D[i].mean()
            D[i] = np.maximum(mu + (D[i] - mu) * s, 0.0)   # mean-preserving
    return D


def rpit(D, y, rng):
    """Randomized PIT. Required by section 4: with a point mass at zero the
    ordinary PIT is degenerate and cannot separate a real defect from the
    zero-mass artifact."""
    lo = (D < y[:, None]).mean(1)
    hi = (D <= y[:, None]).mean(1)
    u = lo + rng.random(len(y)) * (hi - lo)
    h, _ = np.histogram(u, bins=10, range=(0, 1))
    exp = len(u) / 10.0
    return {'chi2': float(((h - exp) ** 2 / exp).sum()),
            'max_bin_dev': float(np.abs(h / len(u) - 0.1).max()),
            'bins': [int(x) for x in h]}


def score(D, y, rng):
    p = D.mean(1)
    e = p - y
    out = {'n': int(len(y)), 'crps': float(L.crps_matrix(D, y).mean()),
           'mae': float(np.abs(e).mean()),
           'rmse': float(np.sqrt(float((e * e).mean()))),
           'bias': float(e.mean()),
           'r': float(np.corrcoef(p, y)[0, 1]) if p.std() > 1e-12 else None,
           'sd_pred_mean': float(p.std(ddof=1)),
           'sd_actual': float(y.std(ddof=1))}
    out['sd_ratio'] = out['sd_pred_mean'] / out['sd_actual']
    q25 = np.quantile(D, 0.25, axis=1)
    for lvl in (50, 80, 90, 95):
        a = (100 - lvl) / 200.0
        lo = np.quantile(D, a, axis=1); hi = np.quantile(D, 1 - a, axis=1)
        out[f'cover{lvl}'] = float(((y >= lo) & (y <= hi)).mean())
        out[f'width{lvl}'] = float((hi - lo).mean())
    pos = q25 > 0
    out['cover50_q25_positive'] = float(
        ((y[pos] >= np.quantile(D[pos], 0.25, axis=1))
         & (y[pos] <= np.quantile(D[pos], 0.75, axis=1))).mean()) if pos.sum() else None
    out['n_q25_positive'] = int(pos.sum())
    out['P_zero_pred'] = float((D == 0).mean())
    out['P_zero_actual'] = float((y == 0).mean())
    out['rpit'] = rpit(D, y, rng)
    return out


def main():
    rows, sub = L.load()
    L.attach_prior(sub)
    rng = np.random.default_rng(L.SEED)
    OUT = {'prereg_sha256': PREREG, 'arms': list(ARMS),
           'label': 'EXPLORATORY -- heavily mined; no promotion possible',
           'by_season': {}, 'training_seasons_only': True}

    acc = {a: {'D': [], 'y': [], 'g': []} for a in ARMS}
    for ev in L.EVAL:
        rs = [r for r in sub if L.eligible(r, ev)]
        y = np.array([r['Y'] for r in rs], float)
        base = S.simulate(rs, ev, sub)
        r1, r2, r3 = fit_repairs(sub, ev, rng)
        OUT['by_season'][ev] = {'n': len(rs), 'r1_factors': r1,
                                'r2_zero_p': {f'{k[0]}/{k[1]}': v for k, v in r2.items()},
                                'r3_scales': {f'{k[0]}/{k[1]}': v for k, v in r3.items()}}
        for a in ARMS:
            D = base if a == 'R0' else apply_repair(base, rs, a, r1, r2, r3, rng)
            acc[a]['D'].append(D); acc[a]['y'].append(y)
            acc[a]['g'] += [r['game_id'] for r in rs]
        print(f'  {ev}: n={len(rs)}  R1 factors ' +
              ' '.join(f'{k}={v:.3f}' for k, v in sorted(r1.items())))

    print('\n== pooled ==')
    OUT['pooled'] = {}
    for a in ARMS:
        D = np.concatenate(acc[a]['D']); y = np.concatenate(acc[a]['y'])
        OUT['pooled'][a] = score(D, y, np.random.default_rng(L.SEED))
        s = OUT['pooled'][a]
        print(f"  {a}: CRPS {s['crps']:8.4f}  MAE {s['mae']:7.3f}  bias {s['bias']:+7.4f}  "
              f"r {s['r']:.4f}  sdratio {s['sd_ratio']:.4f}  "
              f"cov50 {s['cover50']:.3f} ({s['cover50_q25_positive']:.3f} on q25>0)  "
              f"PIT chi2 {s['rpit']['chi2']:8.1f}")

    # ---- predeclared acceptance ------------------------------------------
    b = OUT['pooled']['R0']
    print('\n== predeclared acceptance criteria ==')
    OUT['acceptance'] = {}
    for a in ARMS[1:]:
        s = OUT['pooled'][a]
        c1 = abs(s['bias']) < 1.00
        c2 = (s['crps'] - b['crps']) / b['crps'] <= 0.005
        c3 = (b['r'] - s['r']) <= 0.01
        c4 = s['rpit']['chi2'] <= b['rpit']['chi2']
        ok = c1 and c2 and c3 and c4
        OUT['acceptance'][a] = {
            'bias_below_1.00': c1, 'crps_not_worse_than_0.5pct': c2,
            'r_not_down_more_than_0.01': c3, 'rpit_not_worse': c4,
            'all_four': ok,
            'crps_rel_pct': 100 * (b['crps'] - s['crps']) / b['crps'],
            'r_delta': s['r'] - b['r']}
        print(f"  {a}: bias<1.00 {c1}  CRPS<=+0.5% {c2} ({100*(b['crps']-s['crps'])/b['crps']:+.3f}%)  "
              f"r-drop<=0.01 {c3} ({s['r']-b['r']:+.4f})  PIT {c4}  -> "
              f"{'MEETS ALL FOUR' if ok else 'FAILS'}")

    json.dump(OUT, open(f'{HERE}/rc2_results.json', 'w'), indent=1, default=str)
    print('\nwrote rc2_results.json')
    return 0


if __name__ == '__main__':
    sys.exit(main())
