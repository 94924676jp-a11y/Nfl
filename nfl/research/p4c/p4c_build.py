"""P4C: panel prep, walk-forward parameter fitting, weight generators.

Everything fitted here is fitted on seasons STRICTLY BEFORE the evaluation
season. Mass pools additionally exclude 2020, which is the panel's first season
and whose no-prior-game rate (2.0-4.2% against 0.4-0.9% later) is a
construction artifact rather than a football quantity. That decision is in
predeclaration_p4c.md section 1 and was taken from a training-season
measurement, before any result.
"""
import collections, math, os, pickle, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
P4B = os.path.abspath(os.path.join(HERE, '..', 'p4b'))
for p in (os.path.abspath(os.path.join(HERE, '..', 'p1')),
          os.path.abspath(os.path.join(HERE, '..', 'p2')),
          os.path.abspath(os.path.join(HERE, '..', 'p3')),
          P4B, HERE, '/home/user/nfl'):
    sys.path.insert(0, p)
import p4c_lib as L                                            # noqa: E402
import p3_features as F                                        # noqa: E402
import stage_a as A                                            # noqa: E402

EPS = 1e-6


def ewma(v, hl=3.0):
    if not v:
        return None
    lam = 0.5 ** (1 / hl)
    n = d = 0.0
    w = 1.0
    for x in reversed(v):
        n += w * x
        d += w
        w *= lam
    return n / d


def load_panel():
    return pickle.load(open(f'{P4B}/panel_enriched.pkl', 'rb'))


def load_volume():
    arr = np.load(f'{P4B}/volume_store.npy', allow_pickle=True)
    out = {}
    for e in arr:
        d = dict(e)
        k = tuple(d.pop('k'))
        d['index'] = {kk: i for i, kk in enumerate(d['keys'])}
        out[k] = d
    return out


def appearance(rows):
    POSALL = ('WR', 'TE', 'RB', 'QB')
    cand = [r for r in rows if r['position'] in POSALL
            and (r.get('f_n_prior') or 0) >= 1]
    for r in cand:
        r['y_app'] = 1 if r['appeared'] else 0
    ALL = set(F.FEATURE_GROUPS) - {'p2_base'}
    pa = {}
    for ev in L.EVAL:
        tr = [r for r in cand if r['season'] < ev]
        te = [r for r in cand if r['season'] == ev]
        if len(tr) < 500:
            continue
        ui = ev <= 2024
        m = A.fit_logistic([F.featurise_p3(r, ui, ALL) for r in tr],
                           [r['y_app'] for r in tr])
        for r, v in zip(te, A.predict(m, [F.featurise_p3(r, ui, ALL) for r in te])):
            pa[id(r)] = float(v)
    return pa


def prepare_class(rows, cls):
    """Attach per-player prior-APPEARED history and the point forecast C."""
    c = L.CLASSES[cls]
    skey = c['share']
    sub = [r for r in rows if r['position'] in c['pos']]
    hist = collections.defaultdict(list)
    for r in sorted(sub, key=lambda x: (x['ord'], x['team'], x['gsis_id'])):
        r['_h'] = list(hist[r['gsis_id']])
        v = r.get(skey)
        if v is not None and r['appeared']:
            hist[r['gsis_id']].append(v)
    return sub


def fit_params(sub, cls, ev, rows_all):
    """Every parameter the allocation families need, from seasons < ev."""
    c = L.CLASSES[cls]
    skey = c['share']
    tr = [r for r in sub if r['season'] < ev and r.get(skey) is not None]
    pri = {}
    for p_ in c['pos']:
        v = [r[skey] for r in tr if r['position'] == p_ and r['appeared']]
        if v:
            pri[p_] = float(np.mean(v))
    for r in sub:
        h = r['_h']
        r['_C'] = ewma(h) if h else pri.get(r['position'])

    # ---- additive share-residual pool (the P4B family), by position --------
    add_pool = collections.defaultdict(list)
    lr_pool = collections.defaultdict(list)      # log(S/C), S>0
    lg_pool = collections.defaultdict(list)      # logit(S)-logit(C)
    zero_n = collections.Counter()
    zero_d = collections.Counter()
    for r in tr:
        if not r['appeared'] or r['_C'] is None:
            continue
        s, cc = r[skey], r['_C']
        add_pool[r['position']].append(s - cc)
        zero_d[r['position']] += 1
        if s <= 0:
            zero_n[r['position']] += 1
        elif cc > 0:
            lr_pool[r['position']].append(math.log(s / cc))
            sc = min(max(s, EPS), 1 - EPS); ccl = min(max(cc, EPS), 1 - EPS)
            lg_pool[r['position']].append(
                math.log(sc / (1 - sc)) - math.log(ccl / (1 - ccl)))
    par = {
        'add_pool': {k: np.array(v, np.float32) for k, v in add_pool.items()},
        'lr_pool': {k: np.array(v, np.float32) for k, v in lr_pool.items()},
        'sigma_lr': {k: float(np.std(v, ddof=1)) for k, v in lr_pool.items()
                     if len(v) > 30},
        'sigma_lg': {k: float(np.std(v, ddof=1)) for k, v in lg_pool.items()
                     if len(v) > 30},
        'q_zero': {k: zero_n[k] / zero_d[k] for k in zero_d if zero_d[k]},
        'prior': pri,
    }

    # ---- mass pool: OTHER (simplex) or K (occupancy) -----------------------
    # From seasons < ev, EXCLUDING 2020 (pre-declaration section 1).
    ms = collections.defaultdict(float)
    mall = collections.defaultdict(float)
    seasons_used = set()
    for r in rows_all:
        if r['season'] >= ev or r['season'] in L.MASS_POOL_EXCLUDE_SEASONS:
            continue
        s = r.get(skey)
        if s is None:
            continue
        seasons_used.add(r['season'])
        k = (r['team'], r['ord'])
        mall[k] += s
        if r['position'] in c['pos'] and (r.get('f_n_prior') or 0) >= 1:
            ms[k] += s
    if c['mode'] == 'simplex':
        pool = np.array([max(0.0, min(0.95, mall[k] - ms[k])) for k in mall],
                        np.float32)
    else:
        pool = np.array([ms[k] for k in mall], np.float32)
    par['mass_pool'] = pool
    par['mass_mean'] = float(pool.mean())
    par['mass_pool_seasons'] = sorted(seasons_used)

    # ---- Dirichlet concentration, pooled moment estimator ------------------
    if c['mode'] == 'simplex':
        num = den = 0.0
        by_g = collections.defaultdict(list)
        for r in tr:
            if r['appeared'] and r['_C'] is not None:
                by_g[(r['team'], r['ord'])].append(r)
        mo = par['mass_mean']
        for g, rs in by_g.items():
            tot = sum(x['_C'] for x in rs)
            if tot <= 0:
                continue
            scale = (1.0 - mo) / tot
            for x in rs:
                mu = min(max(x['_C'] * scale, EPS), 1 - EPS)
                num += mu * (1 - mu)
                den += (x[skey] - mu) ** 2
        par['alpha0'] = float(max(0.5, num / den - 1.0)) if den > 0 else 5.0
    else:
        par['alpha0'] = None
    return par



# ---------------------------------------------------------------------------
# WEIGHT GENERATORS. Each returns (W, w_other_raw_or_None) for one system.
# W is (n, M) nonnegative relative weight; allocate() turns it into shares.
# ---------------------------------------------------------------------------
def _resample(pool_by_pos, positions, n, m, rng, fallback, groups=None):
    """Draw one residual per (row, draw) from that row's position pool.

    `groups` is the RBDEP opt-in and is None everywhere by default, which is
    the incumbent: every row resamples INDEPENDENTLY, so two team-mates never
    see the same residual. Passing an array of one group id per row instead
    shares ONE resample position across the rows of a group -- the trick A3
    already uses one level up, moved down to the allocation layer.

    The shared quantity is a UNIFORM, not a raw integer index. For a
    single-position class (carries: RB only) every row in a group reads the
    same pool, so a shared uniform IS a shared index and the two are identical.
    For a mixed-position class (targets: WR/TE/RB) the position pools have
    different lengths, so a raw index is not defined across them; a shared
    uniform against each pool's SORTED order is the quantile-level statement of
    the same idea, and it reduces exactly to a shared index when the pools
    coincide. The per-row MARGINAL is unchanged either way -- a uniform draw
    from the same pool -- which is what makes this an ablation of dependence
    alone and not a change of marginals.
    """
    W = np.empty((n, m), np.float32)
    if groups is None:
        for i, p_ in enumerate(positions):
            pl = pool_by_pos.get(p_)
            if pl is None or len(pl) < 30:
                pl = fallback
            W[i] = pl[rng.integers(0, len(pl), m)]
        return W
    g = np.asarray(groups)
    if g.ndim != 1 or g.shape[0] != n or not np.issubdtype(g.dtype, np.integer):
        raise ValueError(
            f'SHARED_ADD_POOL_GROUP_SHAPE: expected one integer group id per '
            f'row, shape ({n},); got shape {g.shape} dtype {g.dtype}. Refused '
            f'rather than broadcast into a silently wrong pairing.')
    if g.min() < 0:
        raise ValueError(
            f'SHARED_ADD_POOL_GROUP_NEGATIVE: group ids index a table of '
            f'shared draws and cannot be negative; min is {int(g.min())}.')
    U = rng.random((int(g.max()) + 1, m))
    srt = {}
    for i, p_ in enumerate(positions):
        pl = pool_by_pos.get(p_)
        key = p_ if (pl is not None and len(pl) >= 30) else None
        if key not in srt:
            srt[key] = np.sort(pl if key is not None else fallback)
        pl = srt[key]
        idx = np.minimum((U[g[i]] * len(pl)).astype(np.int64), len(pl) - 1)
        W[i] = pl[idx]
    return W


def gen_weights(system, C, positions, par, cls, n, m, rng,
                add_pool_groups=None):
    """C is (n,) the marginal point forecast. Nothing here sees the outcome.

    `add_pool_groups` defaults to None, which is the production default and
    changes nothing. See `_resample`; it is the RBDEP ablation switch and the
    lead decides whether it ever becomes a default.
    """
    c = L.CLASSES[cls]
    allpool = np.concatenate([v for v in par['add_pool'].values()]) \
        if par['add_pool'] else np.zeros(1, np.float32)
    if system in ('A', 'B', 'C', 'C2'):
        W = C[:, None] + _resample(par['add_pool'], positions, n, m, rng,
                                   allpool, groups=add_pool_groups)
        np.clip(W, 0.0, 1.0, out=W)
        return W
    if add_pool_groups is not None:
        raise ValueError(
            f'SHARED_ADD_POOL_NOT_APPLICABLE: system {system!r} does not draw '
            f'from add_pool, so a shared add_pool index would be accepted and '
            f'then silently ignored. Refused.')
    if system == 'D_dir':
        mu = np.maximum(C, EPS)[:, None]
        a = par['alpha0'] * mu
        return rng.gamma(np.broadcast_to(a, (n, m))).astype(np.float32)
    if system == 'D_sln':
        sig = np.array([par['sigma_lr'].get(p_, 0.8) for p_ in positions],
                       np.float32)[:, None]
        W = np.maximum(C, EPS)[:, None] * np.exp(
            sig * rng.standard_normal((n, m), np.float32))
        q = np.array([par['q_zero'].get(p_, 0.0) for p_ in positions],
                     np.float32)[:, None]
        W *= (rng.random((n, m), np.float32) >= q)
        return W
    if system == 'D_ln':
        sig = np.array([par['sigma_lg'].get(p_, 1.0) for p_ in positions],
                       np.float32)[:, None]
        cc = np.clip(C, EPS, 1 - EPS)[:, None]
        z = np.log(cc / (1 - cc)) + sig * rng.standard_normal((n, m), np.float32)
        return (1.0 / (1.0 + np.exp(-z))).astype(np.float32)
    if system == 'D_emp':
        lrall = np.concatenate([v for v in par['lr_pool'].values()]) \
            if par['lr_pool'] else np.zeros(1, np.float32)
        W = np.maximum(C, EPS)[:, None] * np.exp(
            _resample(par['lr_pool'], positions, n, m, rng, lrall))
        q = np.array([par['q_zero'].get(p_, 0.0) for p_ in positions],
                     np.float32)[:, None]
        W *= (rng.random((n, m), np.float32) >= q)
        return W
    raise ValueError(system)


def mass_draws(system, par, G, m, rng):
    """Available-mass treatment. B is the prior-season MEAN; C and every D
    family draw from the prior-season empirical distribution."""
    if system == 'B':
        return np.full((G, m), par['mass_mean'], np.float32)
    pool = par['mass_pool']
    return pool[rng.integers(0, len(pool), (G, m))]
