"""P4F shared: the five systems, and the matched-estimand joint diagnostic."""
import collections, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
P4E = os.path.abspath(os.path.join(HERE, '..', 'p4e'))
P4C = os.path.abspath(os.path.join(HERE, '..', 'p4c'))
P5A = os.path.abspath(os.path.join(HERE, '..', 'p5a'))
for p in (P4E, P4C, P5A, HERE, '/home/user/nfl/sportsplatform'):
    sys.path.insert(0, p)
import p4e_build as B                                          # noqa: E402
import p4e_fit as F                                            # noqa: E402
import p4f_mpr as M                                            # noqa: E402
import p4c_build as CB                                         # noqa: E402
import p4c_lib as CL                                           # noqa: E402

BLOCKS_ABC = ['A', 'B', 'C']
SYSTEMS = ('P4C', 'MPR_ONLY', 'MC_ONLY', 'ABC_ONLY', 'ABC_MPR')
GRID = [0.5, 4.5, 9.5, 14.5, 19.5]
HIST_BANDS = (('<10', 0, 10), ('10-24', 10, 25), ('25-49', 25, 50),
              ('50-99', 50, 100), ('100+', 100, 1e18))
APP_BANDS = (('<0.25', 0.0, .25), ('0.25-0.50', .25, .50),
             ('0.50-0.80', .50, .80), ('0.80-0.95', .80, .95),
             ('>=0.95', .95, 1.01))


def band(v, bands):
    for lbl, lo, hi in bands:
        if lo <= v < hi:
            return lbl
    return bands[-1][0]


def build_systems(sub, cellv, ev, seasons):
    """The five pre-declared systems, plus the audit that the residual draws
    used here are byte-for-byte P4C's own."""
    c = cellv
    par = c['par']
    pos = [r['position'] for r in c['te']]
    allp = np.concatenate(list(par['add_pool'].values()))
    eps = CB._resample(par['add_pool'], pos, c['n'], CL.M_DRAWS,
                       np.random.default_rng(CL.SEED + 3034), allp)
    audit = {'eps_reproduces_P4C_weight': bool(np.array_equal(
        np.clip(c['C_pre'][:, None] + eps, 0.0, 1.0).astype(np.float32),
        c['W_ctrl']))}

    out = {'P4C': (c['W_ctrl'], None, None)}
    W, d, rep = M.rectify(c['C_pre'], eps)
    out['MPR_ONLY'] = (W.astype(np.float32), d, rep)
    out['MC_ONLY'] = (M.recentre_only(c['C_pre'], eps).astype(np.float32),
                      None, None)

    fit, pool, fd = F.fit_centre(sub, ev, BLOCKS_ABC, seasons)
    Wabc, mu = F.weights(c, fit, pool, BLOCKS_ABC,
                         np.random.default_rng(CL.SEED + 3034))
    out['ABC_ONLY'] = (Wabc, None, None)
    eps2 = CB._resample(pool, pos, c['n'], CL.M_DRAWS,
                        np.random.default_rng(CL.SEED + 3034),
                        np.concatenate(list(pool.values())))
    audit['eps2_reproduces_ABC_weight'] = bool(np.array_equal(
        np.clip(mu[:, None] + eps2, 0.0, 1.0).astype(np.float32), Wabc))
    W2, d2, rep2 = M.rectify(mu, eps2)
    out['ABC_MPR'] = (W2.astype(np.float32), d2, rep2)
    centres = {'P4C': c['C_pre'], 'MPR_ONLY': c['C_pre'], 'MC_ONLY': c['C_pre'],
               'ABC_ONLY': mu, 'ABC_MPR': mu}
    return out, centres, {'ctrl': eps, 'abc': eps2}, audit, fd


# ---------------------------------------------------------------------------
def rank_index(cellv, pred, kmax=3):
    """Per team-game, indices of the 1st..kmax backs BY PREGAME FORECAST."""
    out = {k: [] for k in range(1, kmax + 1)}
    gi = []
    for g, s in enumerate(cellv['starts']):
        e = s + cellv['cg'][g]
        order = sorted(range(s, e), key=lambda i: -pred[i])
        if len(order) < 2:
            continue
        gi.append(g)
        for k in range(1, kmax + 1):
            out[k].append(order[k - 1] if len(order) >= k else -1)
    return {k: np.array(v) for k, v in out.items()}, np.array(gi)


def _corr_across_units(A, B):
    """Pearson correlation ACROSS UNITS (rows), one value per column.

    A and B are (units, draws). Returns (draws,) -- the across-team-game
    correlation the model implies under each draw index, which is the SAME
    estimand as the realised across-team-game correlation.
    """
    a = A - A.mean(0, keepdims=True)
    b = B - B.mean(0, keepdims=True)
    d = np.sqrt((a * a).sum(0)) * np.sqrt((b * b).sum(0))
    return np.divide((a * b).sum(0), d, out=np.full(A.shape[1], np.nan),
                     where=d > 1e-12)


def _pear(a, b):
    m = np.isfinite(a) & np.isfinite(b)
    if m.sum() < 30 or a[m].std() < 1e-12 or b[m].std() < 1e-12:
        return None
    return float(np.corrcoef(a[m], b[m])[0, 1])


def ppc_pair(Xsim, Xreal, Ysim, Yreal, min_units=30):
    """Posterior predictive check on a matched estimand.

    `Xsim`/`Ysim` are (units, draws); `Xreal`/`Yreal` are (units,). Both sides
    are across-unit correlations, so they are the same quantity computed on the
    same population -- which is exactly what P4E's withdrawn rule 5 was not.
    """
    if len(Xreal) < min_units:
        return {'state': 'NOT_APPLICABLE', 'n_units': int(len(Xreal)),
                'why': f'fewer than {min_units} team-games carry this pair'}
    rm = _corr_across_units(Xsim, Ysim)
    rm = rm[np.isfinite(rm)]
    rstar = _pear(Xreal, Yreal)
    if rstar is None or len(rm) < 100:
        return {'state': 'NOT_APPLICABLE', 'n_units': int(len(Xreal)),
                'why': 'degenerate variance in the realised or simulated series'}
    lo, hi = float(np.percentile(rm, 2.5)), float(np.percentile(rm, 97.5))
    sd = float(rm.std())
    med = float(np.median(rm))
    return {'state': 'PASS', 'n_units': int(len(Xreal)), 'n_draws': int(len(rm)),
            'model_median_r': med, 'model_ci95': [lo, hi],
            'model_sd_r': sd, 'realised_r': rstar,
            'realised_inside_ci95': bool(lo <= rstar <= hi),
            'z': (float((rstar - med) / sd) if sd > 1e-12 else None)}


def joint_matched(cellv, S, Y, pred):
    """Section 9. Shares for the ranked pairs, counts for top1 vs remainder."""
    ri, gi = rank_index(cellv, pred)
    Sstar = cellv['Sstar'] * cellv['A_star']
    y = cellv['y']
    out = {'n_team_games_ranked': int(len(gi))}
    for lbl, (a, b) in (('RB1-RB2', (1, 2)), ('RB1-RB3', (1, 3)),
                        ('RB2-RB3', (2, 3))):
        ia, ib = ri[a], ri[b]
        m = (ia >= 0) & (ib >= 0)
        ia, ib = ia[m], ib[m]
        out[lbl] = ppc_pair(S[ia], Sstar[ia], S[ib], Sstar[ib])
    ys = CL.gsum(Y, cellv['starts'])
    Rem = CL.gexp(ys, cellv['cg']) - Y
    i1 = ri[1]
    m = i1 >= 0
    i1 = i1[m]
    rem_real = CL.gsum(y[:, None], cellv['starts'])[:, 0][gi[m]] - y[i1]
    out['top1-remainder'] = ppc_pair(Y[i1], y[i1], Rem[i1], rem_real)
    # concentration and coherence, unchanged in definition from P4C
    ss = CL.gsum(S, cellv['starts'])
    hhi = np.divide(CL.gsum(S * S, cellv['starts']), np.maximum(ss ** 2, 1e-12))
    p = np.divide(S, np.maximum(CL.gexp(ss, cellv['cg']), 1e-12))
    ent = -CL.gsum(np.where(p > 1e-9, p * np.log(np.maximum(p, 1e-9)), 0.0),
                   cellv['starts'])
    ssr = CL.gsum(Sstar[:, None], cellv['starts'])[:, 0]
    pr = np.divide(Sstar, np.maximum(CL.gexp(ssr[:, None], cellv['cg'])[:, 0],
                                     1e-12))
    out['concentration'] = {
        'hhi_sim': float(hhi.mean()),
        'hhi_realised': float(np.mean(np.divide(
            CL.gsum((Sstar ** 2)[:, None], cellv['starts'])[:, 0],
            np.maximum(ssr ** 2, 1e-12)))),
        'entropy_sim': float(ent.mean()),
        'entropy_realised': float(np.mean(-CL.gsum(
            np.where(pr > 1e-9, pr * np.log(np.maximum(pr, 1e-9)), 0.0)[:, None],
            cellv['starts'])[:, 0]))}
    out['impossible'] = {
        'share_gt_1': float((S > 1.0 + 1e-6).mean()),
        'share_lt_0': float((S < -1e-9).mean()),
        'group_sum_gt_1': float((ss > 1.0 + 1e-6).mean())}
    out['residual_mass'] = {
        'modelled_sum_mean': float(ss.mean()),
        'realised_modelled_sum_mean': float(ssr.mean()),
        'other_mass_mean': float(1.0 - ss.mean()),
        'realised_other_mass_mean': float(1.0 - ssr.mean())}
    return out
