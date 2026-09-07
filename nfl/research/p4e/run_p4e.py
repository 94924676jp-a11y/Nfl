"""P4E main run: the candidate ladder for RB carry allocation.

The control is P4C system C, reproduced from its own artifact and asserted
bit-exact before anything else runs. Every rung changes ONE thing -- the centre
of the additive share weight -- and inherits P4C's appearance model, team-volume
draw, residual-mass reconciliation and joint draw identity unchanged.
"""
import collections, json, math, os, sys, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import p4e_build as B                                          # noqa: E402
import p4e_fit as F                                            # noqa: E402
import p4c_lib as CL                                           # noqa: E402

# P4C-CARRY's pre-declared carry grid (predeclaration_p4e.md section 9).
GRID = [0.5, 4.5, 9.5, 14.5, 19.5]
# P4C-CARRY allocation (share) Shapley component, CRPS units, by season.
SHAP_S = {2022: 0.9792, 2023: 1.0172, 2024: 1.0476, 2025: 1.0102}

# LADDER. predeclaration section 6 starts at E_A; E_0 is ADDED and labelled as
# a departure, because without it E_A conflates "a learned centre" with "block
# A", and the whole point of a ladder is that a rung changes one thing.
LADDER = [('P4C', None), ('E_0', []),
          ('E_A', ['A']), ('E_B', ['B']), ('E_C', ['C']),
          ('E_D', ['D']), ('E_E', ['E']),
          ('E_AB', ['A', 'B']), ('E_ABC', ['A', 'B', 'C']),
          ('E_ABCD', ['A', 'B', 'C', 'D']),
          ('E_ABCDE', ['A', 'B', 'C', 'D', 'E'])]


def fisher(c):
    c = np.asarray(c, float)
    c = c[np.isfinite(c)]
    c = np.clip(c, -0.999, 0.999)
    return float(np.tanh(np.mean(np.arctanh(c)))) if len(c) else None


def corr_rows(Xa, Xb):
    a = Xa - Xa.mean(1, keepdims=True)
    b = Xb - Xb.mean(1, keepdims=True)
    d = np.sqrt((a * a).sum(1)) * np.sqrt((b * b).sum(1))
    return np.divide((a * b).sum(1), d, out=np.full(len(a), np.nan), where=d > 1e-9)


def pear(a, b):
    a = np.asarray(a, float); b = np.asarray(b, float)
    m = np.isfinite(a) & np.isfinite(b)
    if m.sum() < 30 or a[m].std() < 1e-9 or b[m].std() < 1e-9:
        return None
    return float(np.corrcoef(a[m], b[m])[0, 1])


def rank_index(cellv, pred):
    """Per team-game, the indices of the 1st/2nd/3rd back BY PREGAME FORECAST.
    The outcome is never consulted."""
    out = {1: [], 2: [], 3: []}
    gi = []
    for g, s in enumerate(cellv['starts']):
        e = s + cellv['cg'][g]
        order = sorted(range(s, e), key=lambda i: -pred[i])
        if len(order) < 2:
            continue
        gi.append(g)
        for k in (1, 2, 3):
            out[k].append(order[k - 1] if len(order) >= k else -1)
    return {k: np.array(v) for k, v in out.items()}, np.array(gi)


def joint(cellv, S, Y, pred):
    """Section 8 diagnostics. Simulated quantities are across DRAWS within a
    team-game; realised quantities are across TEAM-GAMES. They are different
    populations and are labelled as such rather than differenced."""
    ri, gi = rank_index(cellv, pred)
    Sstar = cellv['Sstar'] * cellv['A_star']
    y = cellv['y']
    out = {'n_team_games_ranked': int(len(gi))}
    for lbl, (a, b) in (('RB1-RB2', (1, 2)), ('RB1-RB3', (1, 3)),
                        ('RB2-RB3', (2, 3))):
        ia, ib = ri[a], ri[b]
        m = (ia >= 0) & (ib >= 0)
        if m.sum() < 30:
            out[lbl] = None
            continue
        ia, ib = ia[m], ib[m]
        out[lbl] = {
            'n_team_games': int(len(ia)),
            'sim_share_corr_within_teamgame': fisher(corr_rows(S[ia], S[ib])),
            'realised_share_corr_across_teamgames': pear(Sstar[ia], Sstar[ib]),
            'sim_resid_corr': fisher(corr_rows(Y[ia], Y[ib])),
            'realised_resid_corr_across_teamgames': pear(
                y[ia] - Y[ia].mean(1), y[ib] - Y[ib].mean(1)),
        }
    # top1 vs the rest of the modelled backfield
    ys = CL.gsum(Y, cellv['starts'])
    Rem = CL.gexp(ys, cellv['cg']) - Y
    i1 = ri[1]
    out['top1-remainder'] = {
        'sim_corr': fisher(corr_rows(Y[i1], Rem[i1])),
        'realised_resid_corr_across_teamgames': pear(
            y[i1] - Y[i1].mean(1),
            (CL.gsum(y[:, None], cellv['starts'])[:, 0][gi] - y[i1])
            - Rem[i1].mean(1)),
    }
    # the named event probabilities, pre-declared in section 8
    ia, ib = ri[1], ri[2]
    m = (ia >= 0) & (ib >= 0)
    ia, ib = ia[m], ib[m]
    ss = CL.gsum(S, cellv['starts'])
    out['events'] = {
        'P_RB1_gt_RB2': {'sim': float((Y[ia] > Y[ib]).mean()),
                         'realised': float((y[ia] > y[ib]).mean())},
        'P_RB2_challenges_RB1_share_ge_0.8': {
            'sim': float((S[ib] >= 0.8 * np.maximum(S[ia], 1e-9)).mean()),
            'realised': float((Sstar[ib] >= 0.8 * np.maximum(Sstar[ia], 1e-9)).mean())},
        'P_two_backs_share_gt_0.25': {
            'sim': float((np.add.reduceat((S > 0.25).astype(np.float32),
                                          cellv['starts'], axis=0) >= 2).mean()),
            'realised': float((np.add.reduceat(
                (Sstar[:, None] > 0.25).astype(np.float32),
                cellv['starts'], axis=0)[:, 0] >= 2).mean())},
    }
    hhi = np.divide(CL.gsum(S * S, cellv['starts']), np.maximum(ss ** 2, 1e-12))
    p = np.divide(S, np.maximum(CL.gexp(ss, cellv['cg']), 1e-12))
    ent = -CL.gsum(np.where(p > 1e-9, p * np.log(np.maximum(p, 1e-9)), 0.0),
                   cellv['starts'])
    ssr = CL.gsum(Sstar[:, None], cellv['starts'])[:, 0]
    pr = np.divide(Sstar, np.maximum(CL.gexp(ssr[:, None], cellv['cg'])[:, 0], 1e-12))
    out['concentration'] = {
        'hhi_sim': float(hhi.mean()), 'hhi_sim_sd': float(hhi.std()),
        'hhi_realised': float(np.mean(np.divide(
            CL.gsum((Sstar ** 2)[:, None], cellv['starts'])[:, 0],
            np.maximum(ssr ** 2, 1e-12)))),
        'entropy_sim': float(ent.mean()),
        'entropy_realised': float(np.mean(-CL.gsum(
            np.where(pr > 1e-9, pr * np.log(np.maximum(pr, 1e-9)), 0.0)[:, None],
            cellv['starts'])[:, 0])),
    }
    return out


def cohorts(cellv, crps, pred, ri):
    """Section 10 cohorts. Every boundary was fixed in the pre-declaration."""
    te = cellv['te']
    y = cellv['y']
    rank_of = {}
    for k in (1, 2, 3):
        for i in ri[k]:
            if i >= 0:
                rank_of[int(i)] = k
    out = collections.defaultdict(lambda: collections.defaultdict(list))
    for i, r in enumerate(te):
        pc = r.get('g_car_career') or 0.0
        pa_ = float(cellv['p_app'][i])
        hhi = r.get('g_team_hhi')
        b = [('rank', {1: 'RB1', 2: 'RB2', 3: 'RB3'}.get(rank_of.get(i), 'RB4+')),
             ('prior_carries', '<10' if pc < 10 else '10-24' if pc < 25 else
              '25-49' if pc < 50 else '50-99' if pc < 100 else '100+'),
             ('p_appear', '<0.25' if pa_ < .25 else '0.25-0.50' if pa_ < .50 else
              '0.50-0.80' if pa_ < .80 else '0.80-0.95' if pa_ < .95 else '>=0.95'),
             ('role', 'role_change' if (r.get('g_sh_step') is not None
                                        and abs(r['g_sh_step']) >= 0.10)
              or (r.get('g_absent_run') or 0) >= 2 else 'stable_role'),
             ('backfield', 'unknown' if hhi is None else
              'concentrated' if hhi >= 0.50 else 'committee')]
        for dim, lvl in b:
            out[dim][lvl].append(i)
    res = {}
    for dim, d in out.items():
        res[dim] = {}
        for lvl, idx in sorted(d.items()):
            ii = np.array(idx)
            res[dim][lvl] = {'n': len(ii), 'crps': float(crps[ii].mean()),
                             'pred': float(pred[ii].mean()),
                             'real': float(y[ii].mean()),
                             'bias': float((pred[ii] - y[ii]).mean())}
    return res


def main():
    t0 = time.time()
    rows, vol, pa, sub, D = B.load_all()
    B.attach_features(sub)
    seasons = sorted({r['season'] for r in sub})
    print(f'panel seasons {seasons}')

    OUT = {'control_artifact': B.RESULTS_PATH, 'control_sha256': B.PUBLISHED_SHA256,
           'ladder': [k for k, _ in LADDER], 'seasons': {}, 'fits': {}}
    crps_rows = collections.defaultdict(dict)
    clusters = {}

    for ev in B.EVAL:
        c = B.cell(rows, vol, pa, sub, ev)
        clusters[ev] = c['cluster']
        print(f'\n== {ev}  n={c["n"]} G={c["G"]} ==')
        sres = {}
        for name, blocks in LADDER:
            if blocks is None:
                W = c['W_ctrl']
                fd = {'centre': 'P4C EWMA half-life 3 + position prior fallback'}
            else:
                fit, pool, fd = F.fit_centre(sub, ev, blocks, seasons)
                W, mu = F.weights(c, fit, pool, blocks,
                                  np.random.default_rng(CL.SEED + 3034))
                fd['centre_mean'] = float(mu.mean())
                fd['centre_vs_ewma_corr'] = pear(mu, c['C_pre'])
                OUT['fits'].setdefault(name, {})[str(ev)] = {
                    k: v for k, v in fd.items() if k != 'features'}
                if ev == B.EVAL[0]:
                    OUT['fits'][name]['features'] = fd.get('features')
            Y, S = B.counts_from_weights(c, W)
            if name == 'P4C':
                d = abs(float(CL.crps_samples(Y, c['y']).mean())
                        - B.PUBLISHED[ev])
                assert d == 0.0, f'control not bit-exact at {ev}: {d:.3e}'
            sc = CL.score(Y, c['y'], np.random.default_rng(CL.SEED + 31))
            cr = CL.crps_samples(Y, c['y'])
            crps_rows[ev][name] = cr
            pred = Y.mean(1)
            ri, _gi = rank_index(c, pred)
            sres[name] = {
                'scores': sc,
                'thresholds': CL.thresholds(Y, c['y'], GRID),
                'share_crps': float(CL.crps_samples(
                    S, c['Sstar'] * c['A_star']).mean()),
                'joint': joint(c, S, Y, pred),
                'cohorts': cohorts(c, cr, pred, ri),
                'fit': fd if blocks is not None else fd,
            }
            print(f'  {name:8s} CRPS {sc["crps"]:.4f}  MAE {sc["mae"]:.3f}  '
                  f'r {sc["r"]:+.3f}  bias {sc["bias"]:+.3f}  '
                  f'rPIT {sc["randomised_pit"]["chi2"]:7.1f}  '
                  f'shareCRPS {sres[name]["share_crps"]:.5f}')
            del Y, S, W
        # paired block bootstrap against the control, clustered by team-game
        for name, _b in LADDER:
            if name == 'P4C':
                continue
            sres[name]['boot_vs_P4C'] = CL.block_boot(
                crps_rows[ev][name], crps_rows[ev]['P4C'], c['cluster'])
        sres['_meta'] = {'n': c['n'], 'G': c['G'],
                         'shapley_allocation_component': SHAP_S[ev]}
        OUT['seasons'][str(ev)] = sres
        json.dump(OUT, open(f'{HERE}/p4e_results.json', 'w'), indent=1)

    # ---- pooled, and the per-season record kept visible --------------------
    pooled = {}
    allc = np.concatenate([clusters[e] for e in B.EVAL])
    for name, _b in LADDER:
        cat = np.concatenate([crps_rows[e][name] for e in B.EVAL])
        base = np.concatenate([crps_rows[e]['P4C'] for e in B.EVAL])
        per = {str(e): float(crps_rows[e][name].mean()) for e in B.EVAL}
        wins = sum(1 for e in B.EVAL
                   if crps_rows[e][name].mean() < crps_rows[e]['P4C'].mean())
        pooled[name] = {
            'pooled_crps': float(cat.mean()), 'per_season_crps': per,
            'seasons_better_than_P4C': wins,
            'delta_vs_P4C': float(cat.mean() - base.mean()),
            'boot_vs_P4C': (None if name == 'P4C'
                            else CL.block_boot(cat, base, list(allc))),
            'shapley_fraction_recovered': (
                float((base.mean() - cat.mean())
                      / np.mean([SHAP_S[e] for e in B.EVAL]))),
        }
    OUT['pooled'] = pooled
    print('\n== pooled ==')
    for name, _b in LADDER:
        p = pooled[name]
        bt = p['boot_vs_P4C']
        ci = ('' if bt is None else
              f"  95% [{bt['lo']:+.4f}, {bt['hi']:+.4f}] clusters {bt['n_clusters']}")
        print(f"  {name:8s} pooled {p['pooled_crps']:.4f}  "
              f"delta {p['delta_vs_P4C']:+.4f}  "
              f"seasons better {p['seasons_better_than_P4C']}/4  "
              f"shapley recovered {100*p['shapley_fraction_recovered']:+.2f}%{ci}")
    json.dump(OUT, open(f'{HERE}/p4e_results.json', 'w'), indent=1)
    print(f'\ndone in {time.time()-t0:.0f}s -> p4e_results.json')


if __name__ == '__main__':
    main()
