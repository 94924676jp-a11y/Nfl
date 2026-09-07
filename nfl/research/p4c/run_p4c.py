"""P4C main run: constrained joint allocation of player opportunity.

The ladder is deliberate. A -> B isolates RECONCILIATION, B -> C isolates the
MASS TREATMENT, C -> D isolates the COMPOSITIONAL FAMILY. Every system shares
the same marginal point forecast, the same appearance model and the same team
total draw, so a difference is attributable to exactly one of those three.

E is the realised-allocation oracle. It is not in ELIGIBLE_SYSTEMS, it is
computed after selection has happened, and two guard-deletion proofs show that
those two facts are what stop it rather than this comment.
"""
import collections, json, math, os, sys, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import p4c_lib as L                                            # noqa: E402
import p4c_build as B                                          # noqa: E402

# LADDER, and the pre-declared C had to be SPLIT to make it a ladder.
#
# predeclaration_p4c.md section 3 defined C as "stochastic available mass, with
# an explicit OTHER component that competes". That bundles TWO changes against
# B, so a difference could not be attributed to either. C is therefore split
# and NEITHER half is dropped:
#
#   B    reserved mass, DETERMINISTIC (prior-season mean)
#   C    reserved mass, STOCHASTIC   -- isolates the mass treatment
#   C2   stochastic mass with a COMPETING other component -- isolates whether
#        an absent player's mass leaks out of the modelled set (simplex only;
#        for the occupancy classes the team still fields five skill players
#        whoever is out, so there is no OTHER mass to compete for)
#
# Every D family uses C's reserved-mass reconciliation, so C -> D isolates the
# compositional family and nothing else.
SYSTEMS = {
    'simplex':   ['A', 'B', 'C', 'C2', 'D_dir', 'D_sln', 'D_emp', 'E'],
    'occupancy': ['A', 'B', 'C', 'D_ln', 'D_emp', 'E'],
}
PHYS_MAX = {'simplex': 1.0, 'occupancy': 5.0}


def groups_of(te):
    keys = [(r['team'], r['ord']) for r in te]
    starts, counts, cur = [], [], None
    for i, k in enumerate(keys):
        if k != cur:
            starts.append(i)
            cur = k
    starts = np.array(starts)
    counts = np.diff(np.append(starts, len(keys)))
    return starts, counts, [keys[s] for s in starts]


def fisher_mean(c):
    c = np.clip(np.asarray(c, float), -0.999, 0.999)
    c = c[np.isfinite(c)]
    return float(np.tanh(np.mean(np.arctanh(c)))) if len(c) else None


def corr_rows(Xa, Xb):
    """Correlation across draws, one value per row pair."""
    a = Xa - Xa.mean(1, keepdims=True)
    b = Xb - Xb.mean(1, keepdims=True)
    sa = np.sqrt((a * a).sum(1)); sb = np.sqrt((b * b).sum(1))
    d = sa * sb
    return np.divide((a * b).sum(1), d, out=np.full(len(a), np.nan), where=d > 1e-9)


def boot_corr(x, y, n=400, seed=L.SEED):
    rng = np.random.default_rng(seed)
    m = len(x)
    if m < 20:
        return None
    idx = rng.integers(0, m, (n, m))
    out = []
    for i in range(n):
        a, b = x[idx[i]], y[idx[i]]
        if a.std() > 1e-9 and b.std() > 1e-9:
            out.append(np.corrcoef(a, b)[0, 1])
    if len(out) < 50:
        return None
    out = np.sort(out)
    return {'lo': float(out[int(.025 * len(out))]),
            'hi': float(out[int(.975 * len(out))])}


def pair_index(te, starts, counts, positions_of):
    """Named teammate pairs, ranked by the PREGAME forecast, never the outcome."""
    out = collections.defaultdict(lambda: ([], []))
    tops = []
    for gi, s in enumerate(starts):
        e = s + counts[gi]
        idx = list(range(s, e))
        byp = collections.defaultdict(list)
        for i in idx:
            byp[positions_of[i]].append(i)
        for p_ in byp:
            byp[p_].sort(key=lambda i: -CBUF[i])
        top = max(idx, key=lambda i: CBUF[i])
        tops.append((gi, top))
        for lbl, (pa, ia), (pb, ib) in (
                ('WR1-WR2', ('WR', 0), ('WR', 1)),
                ('WR1-TE1', ('WR', 0), ('TE', 0)),
                ('WR1-RB1', ('WR', 0), ('RB', 0)),
                ('TE1-RB1', ('TE', 0), ('RB', 0)),
                ('RB1-RB2', ('RB', 0), ('RB', 1))):
            if len(byp.get(pa, [])) > ia and len(byp.get(pb, [])) > ib:
                a, b = byp[pa][ia], byp[pb][ib]
                if a != b:
                    out[lbl][0].append(a)
                    out[lbl][1].append(b)
    return out, tops


CBUF = None


def main():
    t0 = time.time()
    rows = B.load_panel()
    vol = B.load_volume()
    print(f'panel {len(rows)} rows; computing appearance ...')
    pa = B.appearance(rows)
    print(f'p_app for {len(pa)} player-games')
    OUT = {}
    global CBUF

    for cls, c in L.CLASSES.items():
        mode = c['mode']
        skey, ykey = c['share'], c['y']
        sub = B.prepare_class(rows, cls)
        res_c = {}
        for ev in L.EVAL:
            store = vol.get((c['den'], ev))
            if store is None:
                continue
            par = B.fit_params(sub, cls, ev, rows)
            te = [r for r in sub if r['season'] == ev and r.get(skey) is not None
                  and id(r) in pa and (r.get('f_n_prior') or 0) >= 1
                  and r['_C'] is not None
                  and (r['team'], r['ord']) in store['index']]
            te.sort(key=lambda r: (r['ord'], r['team'], r['gsis_id']))
            if len(te) < 200:
                continue
            n = len(te)
            starts, counts, gkeys = groups_of(te)
            G = len(starts)
            y = np.array([r[ykey] for r in te], float)
            C = np.array([r['_C'] for r in te], np.float32)
            CBUF = C
            positions = [r['position'] for r in te]
            p_app = np.array([pa[id(r)] for r in te], np.float32)
            S_real = np.array([r[skey] for r in te], np.float32)
            A_real = np.array([1.0 if r['appeared'] else 0.0 for r in te])
            ti = np.array([store['index'][(r['team'], r['ord'])] for r in te])
            gti = ti[starts]
            cluster = [f'{k[0]}_{k[1]}' for k in gkeys]
            row_cluster = [f"{r['team']}_{r['ord']}" for r in te]
            T = store['B'][ti]                      # (n, M) shared per team-game
            Tg = store['B'][gti]                    # (G, M)
            rngA = np.random.default_rng(L.SEED + 1009)
            Ad = (rngA.random((n, L.M_DRAWS), np.float32) < p_app[:, None])
            pairs, tops = pair_index(te, starts, counts, positions)

            scores, joints, crps_row, thr = {}, {}, {}, {}
            for si, sysname in enumerate(SYSTEMS[mode]):
                rng = np.random.default_rng(L.SEED + 3000 + 17 * si)
                if sysname == 'E':
                    W = np.repeat(S_real[:, None], L.M_DRAWS, axis=1)
                else:
                    W = B.gen_weights(sysname, C, positions, par, cls, n,
                                      L.M_DRAWS, rng)
                clip_rate = None
                if sysname in ('A', 'B', 'C', 'C2'):
                    raw = C[:, None] + B._resample(
                        par['add_pool'], positions, n, L.M_DRAWS,
                        np.random.default_rng(L.SEED + 3000 + 17 * si),
                        np.concatenate(list(par['add_pool'].values())))
                    clip_rate = float(((raw < 0) | (raw > 1)).mean())
                    del raw
                if sysname == 'A':
                    S = (W * Ad).astype(np.float32)
                    other = None
                    nbind = 0
                else:
                    mass = B.mass_draws(
                        'B' if sysname == 'B' else 'C', par, G, L.M_DRAWS,
                        np.random.default_rng(L.SEED + 5000 + si))
                    if sysname == 'C2':
                        # competing OTHER: the weight scale must match the
                        # family, so C2 runs only with the additive family
                        sumC = L.gsum(np.maximum(C, 1e-9)[:, None], starts)
                        w_other = (mass / np.maximum(1e-6, 1 - mass)) * sumC
                        S, other, nbind = L.allocate(W, Ad, starts, counts,
                                                     'simplex', None, w_other)
                    else:
                        # RESERVED mass: the available modelled mass is fixed
                        # (1 - m for a simplex class, K for an occupancy class)
                        # and all of it goes to the appearing modelled players.
                        avail = (1.0 - mass) if mode == 'simplex' else mass
                        S, other, nbind = L.allocate(W, Ad, starts, counts,
                                                     'occupancy', avail)
                        other = None if mode != 'simplex' else mass
                Y = (T * S).astype(np.float32)
                scores[sysname] = L.score(Y, y,
                                          np.random.default_rng(L.SEED + 31))
                thr[sysname] = L.thresholds(Y, y, L.THRESHOLDS[cls])
                crps_row[sysname] = L.crps_samples(Y, y)

                # ---- joint diagnostics --------------------------------------
                ss = L.gsum(S, starts)                    # (G, M) share sum
                ys = L.gsum(Y, starts)                    # (G, M) absolute sum
                ss_real = L.gsum(S_real[:, None] * A_real[:, None], starts)[:, 0]
                ys_real = L.gsum(y[:, None], starts)[:, 0]
                hhi = np.divide(L.gsum(S * S, starts), np.maximum(ss ** 2, 1e-12))
                top1 = np.maximum.reduceat(S, starts, axis=0)
                phys = PHYS_MAX[mode]
                j = {
                    'share_sum': {'mean': float(ss.mean()),
                                  'sd_within_group': float(ss.std(axis=1).mean()),
                                  'realised_mean': float(ss_real.mean()),
                                  'over_allocation_pct': float(
                                      100 * (ss.mean() - ss_real.mean())
                                      / max(ss_real.mean(), 1e-9))},
                    'abs_sum': {'mean': float(ys.mean()),
                                'realised_mean': float(ys_real.mean()),
                                'coverage_90': float(
                                    ((ys_real >= np.percentile(ys, 5, axis=1))
                                     & (ys_real <= np.percentile(ys, 95, axis=1))).mean()),
                                'crps': float(L.crps_samples(ys, ys_real).mean())},
                    'reconciliation_error_vs_sim_team_total': {
                        'mean_abs': float(np.abs(ys - ss * Tg).mean()),
                        'note': 'sum_i Y_i - (sum_i S_i) * T ; zero means the '
                                'player sum reconciles to the simulated team '
                                'total by construction'},
                    'impossible': {
                        'share_gt_1': float((S > 1.0 + 1e-6).mean()),
                        'share_lt_0': float((S < -1e-9).mean()),
                        'group_sum_gt_physical_max': float((ss > phys + 1e-6).mean()),
                        'physical_max': phys},
                    'boundary_clip_rate_before_allocation': clip_rate,
                    'waterfill_bindings': int(nbind),
                    'concentration_hhi': {'sim': float(hhi.mean()),
                                          'realised': float(np.mean(
                                              np.divide(L.gsum((S_real * A_real)[:, None] ** 2, starts)[:, 0],
                                                        np.maximum(ss_real ** 2, 1e-12))))},
                    'top1_share': {'sim': float(top1.mean()),
                                   'realised': float(np.maximum.reduceat(
                                       (S_real * A_real)[:, None], starts, axis=0)[:, 0].mean())},
                    'other_mass': (None if other is None else
                                   {'sim_mean': float(other.mean()),
                                    'sim_sd': float(other.std())}),
                }
                # ---- teammate covariance ------------------------------------
                mean_pred = Y.mean(axis=1)
                Rem = L.gexp(ys, counts) - Y
                pj = {}
                for lbl, (ia, ib) in pairs.items():
                    if len(ia) < 30:
                        continue
                    ia_ = np.array(ia); ib_ = np.array(ib)
                    sc = fisher_mean(corr_rows(Y[ia_], Y[ib_]))
                    ra = y[ia_] - mean_pred[ia_]
                    rb = y[ib_] - mean_pred[ib_]
                    ec = (float(np.corrcoef(ra, rb)[0, 1])
                          if ra.std() > 1e-9 and rb.std() > 1e-9 else None)
                    pj[lbl] = {'n_pairs': len(ia), 'sim_corr': sc,
                               'empirical_resid_corr': ec,
                               'empirical_ci': boot_corr(ra, rb)}
                ti_ = np.array([t for _g, t in tops])
                sc = fisher_mean(corr_rows(Y[ti_], Rem[ti_]))
                ra = y[ti_] - mean_pred[ti_]
                rem_real = ys_real[np.array([g for g, _t in tops])] - y[ti_]
                rem_pred = Rem[ti_].mean(axis=1)
                rb = rem_real - rem_pred
                pj['top1-remainder'] = {
                    'n_pairs': len(ti_), 'sim_corr': sc,
                    'empirical_resid_corr': (float(np.corrcoef(ra, rb)[0, 1])
                                             if ra.std() > 1e-9 and rb.std() > 1e-9
                                             else None),
                    'empirical_ci': boot_corr(ra, rb)}
                if other is not None:
                    Yo = other * Tg
                    sc = fisher_mean(corr_rows(Y[ti_], Yo[np.array([g for g, _t in tops])]))
                    pj['top1-OTHER'] = {'n_pairs': len(ti_), 'sim_corr': sc,
                                        'empirical_resid_corr': None,
                                        'note': 'OTHER is unmodelled mass; no '
                                                'per-player empirical analogue'}
                j['teammate'] = pj
                joints[sysname] = j
                del Y, S, W
            chosen = L.select_system(scores)      # E is not visible here

            boots = {}
            base = 'A'
            for k in scores:
                if k != base:
                    boots[f'{k}_minus_A_crps'] = L.block_boot(
                        crps_row[k], crps_row[base], row_cluster)

            res_c[ev] = {
                'n': n, 'n_team_games': G, 'mode': mode,
                'params': {'alpha0': par['alpha0'],
                           'sigma_lr': par['sigma_lr'],
                           'sigma_lg': par['sigma_lg'],
                           'q_zero': par['q_zero'],
                           'mass_mean': par['mass_mean'],
                           'mass_pool_seasons': par['mass_pool_seasons'],
                           'mass_pool_n': int(len(par['mass_pool']))},
                'appearance_rate': float(A_real.mean()),
                'scores': scores, 'thresholds': thr, 'joint': joints,
                'bootstrap_vs_A': boots,
                'chosen_eligible_system': chosen,
                'systems_offered': [s for s in SYSTEMS[mode]
                                    if s in L.ELIGIBLE_SYSTEMS],
            }
            line = ' '.join(
                f'{k}={scores[k]["crps"]:.4f}' for k in SYSTEMS[mode])
            over = ' '.join(
                f'{k}={joints[k]["share_sum"]["over_allocation_pct"]:+.1f}%'
                for k in SYSTEMS[mode])
            print(f'  {cls:11s} {ev} n={n:5d} G={G:3d} CRPS {line}')
            print(f'  {"":11s}      over-allocation {over}  chosen={chosen}')
            OUT[cls] = res_c
            json.dump(OUT, open(f'{HERE}/p4c_results.json', 'w'), indent=1)
        OUT[cls] = res_c
        json.dump(OUT, open(f'{HERE}/p4c_results.json', 'w'), indent=1)
    print(f'\ndone in {time.time()-t0:.0f}s -> p4c_results.json')


if __name__ == '__main__':
    main()
