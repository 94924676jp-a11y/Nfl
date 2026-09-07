"""P4B main run: distributional team volume -> absolute player opportunity.

FOUR SYSTEMS, ONE SHARE LAYER. A, B, C and D differ ONLY in how the team total
is treated, so a difference between them is attributable to the volume
treatment and to nothing else.

  A  team total = the P4-style point forecast (deterministic)
  B  team total ~ league-wide unconditional predictive distribution
  C  team total ~ team-/coach-conditioned predictive distribution
  D  team total = the REALISED total -- DIAGNOSTIC ONLY, NEVER ELIGIBLE

D is built in a separate pass, after selection has already happened, and
`select_system()` below cannot see it. nfl/research/p4b/run_p4b_adversarial.py
asserts that mechanically rather than trusting this comment.
"""
import collections, json, os, pickle, sys, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
for p in (os.path.join(HERE, '..', 'p1'), os.path.join(HERE, '..', 'p2'),
          os.path.join(HERE, '..', 'p3'), HERE, '/home/user/nfl'):
    sys.path.insert(0, os.path.abspath(p))
import p4b_lib as L                                            # noqa: E402
import p3_features as F                                        # noqa: E402
import stage_a as A                                            # noqa: E402

ELIGIBLE_SYSTEMS = ('A', 'B', 'C')       # D is not in this tuple, by design
DIAGNOSTIC_ONLY = ('D',)


def select_system(scores):
    """Choose among ELIGIBLE systems by CRPS. Coverage is reported but never
    selects: a uselessly wide interval hits nominal coverage and CRPS refuses
    to reward it."""
    cand = {k: v for k, v in scores.items() if k in ELIGIBLE_SYSTEMS}
    if not cand:
        return None
    return min(cand, key=lambda k: cand[k]['crps'])


def load_volume():
    arr = np.load(f'{HERE}/volume_store.npy', allow_pickle=True)
    out = {}
    for e in arr:
        d = dict(e)
        k = d.pop('k')
        d['index'] = {kk: i for i, kk in enumerate(d['keys'])}
        out[tuple(k)] = d
    return out


def appearance(rows):
    """P3 Stage-A, full feature set, trained on prior seasons only."""
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
        ui = ev <= 2024                      # injuries carry no timestamp in 2025
        m = A.fit_logistic([F.featurise_p3(r, ui, ALL) for r in tr],
                           [r['y_app'] for r in tr])
        for r, v in zip(te, A.predict(m, [F.featurise_p3(r, ui, ALL) for r in te])):
            pa[id(r)] = float(v)
        print(f'   appearance model {ev}: train {len(tr)} test {len(te)} '
              f'(injury features: {"yes" if ui else "NO -- 2025 has no timestamp"})')
    return pa


def share_history(rows, target, positions):
    """Conditional share EWMA over PRIOR APPEARED games only."""
    key = f's_{target}'
    sub = [r for r in rows if r['position'] in positions]
    hist = collections.defaultdict(list)
    for r in sorted(sub, key=lambda x: (x['ord'], x['team'], x['gsis_id'])):
        r['_app_hist'] = list(hist[r['gsis_id']])
        v = r.get(key)
        if v is not None and r['appeared']:
            hist[r['gsis_id']].append(v)
    return sub


def main():
    t0 = time.time()
    rows = pickle.load(open(f'{HERE}/panel_enriched.pkl', 'rb'))
    print(f'panel rows {len(rows)}')
    vol = load_volume()
    print('computing appearance probabilities ...')
    pa = appearance(rows)
    print(f'   p_app available for {len(pa)} player-games')

    out = {}
    for target, (den_key, positions) in L.TARGETS.items():
        sub = share_history(rows, target, positions)
        skey = f's_{target}'
        ykey = f'y_{target}'
        res_t = {}
        for ev in L.EVAL:
            store = vol.get((den_key, ev))
            if store is None:
                continue
            tr = [r for r in sub if r['season'] < ev and r.get(skey) is not None]
            te = [r for r in sub if r['season'] == ev and r.get(skey) is not None
                  and id(r) in pa and (r.get('f_n_prior') or 0) >= 1
                  and (r['team'], r['ord']) in store['index']]
            if len(te) < 200 or len(tr) < 500:
                continue
            # ---- position prior for a player with no appeared history -------
            pri = {}
            for p_ in positions:
                v = [r[skey] for r in tr if r['position'] == p_ and r['appeared']]
                if v:
                    pri[p_] = float(np.mean(v))
            # ---- conditional share point forecast ---------------------------
            for r in tr + te:
                h = r['_app_hist']
                r['_C'] = L.ewma(h) if h else pri.get(r['position'])
            # ---- share residual pool, PRIOR SEASONS, appeared games only ----
            pool = collections.defaultdict(list)
            pool_dec = collections.defaultdict(list)
            cuts = {}
            for p_ in positions:
                cv = sorted(r['_C'] for r in tr
                            if r['position'] == p_ and r['appeared']
                            and r['_C'] is not None)
                cuts[p_] = ([cv[int(q * len(cv))] for q in
                             (.1, .2, .3, .4, .5, .6, .7, .8, .9)] if cv else [])
            for r in tr:
                if not r['appeared'] or r['_C'] is None or r.get(skey) is None:
                    continue
                d = r[skey] - r['_C']
                pool[r['position']].append(d)
                b = int(np.searchsorted(cuts[r['position']], r['_C']))
                pool_dec[(r['position'], b)].append(d)
            pool = {k: np.array(v, np.float32) for k, v in pool.items()}
            pool_dec = {k: np.array(v, np.float32) for k, v in pool_dec.items()
                        if len(v) >= 50}

            te = [r for r in te if r['_C'] is not None
                  and r['position'] in pool]
            n = len(te)
            y = np.array([r[ykey] for r in te], float)
            p_app = np.array([pa[id(r)] for r in te], np.float32)
            C = np.array([r['_C'] for r in te], np.float32)
            ti = np.array([store['index'][(r['team'], r['ord'])] for r in te])
            cluster = [f"{r['team']}_{r['ord']}" for r in te]

            rng = np.random.default_rng(L.SEED + 1009)
            Ad = (rng.random((n, L.M_DRAWS), np.float32) < p_app[:, None])

            def share_draws(kind, seed):
                g = np.random.default_rng(seed)
                S = np.empty((n, L.M_DRAWS), np.float32)
                for i, r in enumerate(te):
                    if kind == 'pos':
                        pl = pool[r['position']]
                    else:
                        b = int(np.searchsorted(cuts[r['position']], r['_C']))
                        pl = pool_dec.get((r['position'], b), pool[r['position']])
                    S[i] = pl[g.integers(0, len(pl), L.M_DRAWS)]
                S += C[:, None]
                nclip = float(((S < 0) | (S > 1)).mean())
                np.clip(S, 0.0, 1.0, out=S)
                return S, nclip

            Sd, clip_rate = share_draws('pos', L.SEED + 2003)

            volumes = {
                'A': np.repeat(store['point'][ti][:, None], L.M_DRAWS, axis=1),
                'B': store['B'][ti],
                'C': store['C'][ti],
            }
            scores, thr = {}, {}
            crps_row = {}
            for sysname, T in volumes.items():
                Y = Ad * T * Sd
                scores[sysname] = L.score(Y, y)
                thr[sysname] = L.thresholds(Y, y, L.THRESHOLDS[target])
                crps_row[sysname] = L.crps_samples(Y, y)
                del Y
            chosen = select_system(scores)          # D cannot be seen here

            # ---- sensitivity: heteroskedastic share pool (labelled departure)
            Sd2, clip2 = share_draws('pos_decile', L.SEED + 2003)
            Y2 = Ad * volumes['B'] * Sd2
            sens = L.score(Y2, y)
            del Y2

            # ---- DIAGNOSTIC PASS. Runs only now, after `chosen` is fixed. ----
            Td = np.repeat(store['realized'][ti][:, None], L.M_DRAWS, axis=1)
            Yd = Ad * Td * Sd
            scores['D'] = L.score(Yd, y)
            thr['D'] = L.thresholds(Yd, y, L.THRESHOLDS[target])
            crps_row['D'] = L.crps_samples(Yd, y)
            del Yd, Td

            # ---- oracle decomposition (point arms) --------------------------
            S_real = np.array([r[skey] for r in te], float)
            A_real = np.array([1.0 if r['appeared'] else 0.0 for r in te])
            T_pt = store['point'][ti].astype(float)
            T_re = store['realized'][ti].astype(float)
            arms = {
                'PP_proj_vol_proj_share': p_app * T_pt * C,
                'RP_real_vol_proj_share': p_app * T_re * C,
                'PR_proj_vol_real_share': p_app * T_pt * S_real,
                'RR_real_vol_real_share': p_app * T_re * S_real,
                'RRR_real_app_vol_share': A_real * T_re * S_real,
            }
            oracle = {}
            for k, v in arms.items():
                e = y - v
                oracle[k] = {'mae': float(np.abs(e).mean()),
                             'rmse': float(np.sqrt((e * e).mean())),
                             'max_abs_err': float(np.abs(e).max())}

            # ---- covariance / coherence diagnostic --------------------------
            byteam = collections.defaultdict(list)
            for i, c in enumerate(cluster):
                byteam[c].append(i)
            multi = [np.array(v) for v in byteam.values() if len(v) >= 2]
            cov = {}
            for sysname in ('A', 'B'):
                T = volumes[sysname]
                Y = Ad * T * Sd
                sums = np.array([Y[g].sum(axis=0) for g in multi])   # (G, M)
                real = np.array([y[g].sum() for g in multi])
                cov[sysname] = {
                    'n_team_games': len(multi),
                    'mean_sd_of_team_sum': float(sums.std(axis=1).mean()),
                    'sd_of_realised_team_sums': float(real.std(ddof=1)),
                    'team_sum_coverage_90': float(
                        ((real >= np.percentile(sums, 5, axis=1))
                         & (real <= np.percentile(sums, 95, axis=1))).mean()),
                    'team_sum_crps': float(L.crps_samples(sums, real).mean()),
                }
                del Y, sums
            # implied share coherence: do the drawn shares still sum to 1?
            ssum = np.array([Sd[g].sum(axis=0).mean() for g in multi])
            cov['drawn_share_sum_mean'] = float(ssum.mean())
            cov['drawn_share_sum_sd'] = float(ssum.std(ddof=1))
            cov['realised_share_sum_mean'] = float(np.mean(
                [S_real[g].sum() for g in multi]))

            boots = {}
            for a, b in (('B', 'A'), ('C', 'A'), ('C', 'B'), ('D', 'A'), ('D', 'B')):
                boots[f'{a}_minus_{b}_crps'] = L.block_boot(
                    crps_row[a], crps_row[b], cluster)

            res_t[ev] = {
                'n': n, 'n_train_rows': len(tr),
                'n_team_game_clusters': len(byteam),
                'denominator': den_key, 'positions': list(positions),
                'appearance_rate': float(A_real.mean()),
                'mean_p_app': float(p_app.mean()),
                'share_clip_rate': clip_rate,
                'share_clip_rate_decile_pool': clip2,
                'scores': scores, 'thresholds': thr,
                'chosen_eligible_system': chosen,
                'systems_offered_to_selection': list(ELIGIBLE_SYSTEMS),
                'oracle': oracle, 'covariance': cov, 'bootstrap': boots,
                'sensitivity_B_decile_share_pool': sens,
            }
            s = scores
            print(f'  {target:12s} {ev} n={n:5d} app={A_real.mean():.3f} '
                  f'| CRPS A={s["A"]["crps"]:.4f} B={s["B"]["crps"]:.4f} '
                  f'C={s["C"]["crps"]:.4f} D*={s["D"]["crps"]:.4f} '
                  f'| chosen={chosen} '
                  f'| cov90 A={s["A"]["coverage"]["90"]["coverage"]:.3f} '
                  f'B={s["B"]["coverage"]["90"]["coverage"]:.3f} '
                  f'| oracle PP={oracle["PP_proj_vol_proj_share"]["mae"]:.3f} '
                  f'RP={oracle["RP_real_vol_proj_share"]["mae"]:.3f} '
                  f'PR={oracle["PR_proj_vol_real_share"]["mae"]:.3f} '
                  f'RRR={oracle["RRR_real_app_vol_share"]["max_abs_err"]:.2e}')
            out[target] = res_t
            json.dump(out, open(f'{HERE}/p4b_results.json', 'w'), indent=1)
        out[target] = res_t
        json.dump(out, open(f'{HERE}/p4b_results.json', 'w'), indent=1)
    print(f'\ndone in {time.time()-t0:.0f}s -> p4b_results.json')


if __name__ == '__main__':
    main()
