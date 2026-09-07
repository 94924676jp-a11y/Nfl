"""P4B step 2: predictive DISTRIBUTIONS for team offensive volume.

The whole point of P4B is that P4 found team volume close to unforecastable:
the best simple baseline was the league mean in two seasons of four, and
correlation peaked at 0.167. A point forecast of an unforecastable quantity is
not wrong, it is merely silent about how wrong it is. This module makes it
speak.

DISCIPLINE, in the order the pre-declaration fixed:
  1. the point estimator is chosen ON PRIOR SEASONS ONLY, walk-forward;
  2. residuals are gathered from prior seasons only;
  3. the distribution FORM is chosen by CRPS on an INNER validation season,
     fitted on seasons strictly before that, so neither the form nor the
     estimator ever sees the evaluation season;
  4. normality is TESTED before any Gaussian is used, and the test is reported
     whether or not it is convenient.
"""
import collections, csv, json, math, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DEN = ('team_off_snaps', 'team_dropbacks_part', 'team_targets', 'team_carries',
       'team_rz_carries')
EVAL = [2022, 2023, 2024, 2025]
BASELINES = ['league_mean', 'team_expanding', 'last_game', 'roll3', 'roll5',
             'ewma', 'prev_season', 'coach_prior']
FORMS = ['empirical', 'gaussian', 'student_t', 'team_empirical',
         'coach_empirical']
MIN_COND_GAMES = 24          # pre-declared
M_DRAWS = 1000               # pre-declared
SEED = 20260907


def load():
    rows = []
    for r in csv.DictReader(open(f'{HERE}/denom_panel.csv')):
        for k in ('season', 'week', 'ord'):
            r[k] = int(r[k])
        for k in DEN:
            r[k] = int(r[k])
        rows.append(r)
    rows.sort(key=lambda x: (x['ord'], x['team']))
    return rows


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


def attach(rows, key):
    """Prior values for this team and this coach. Strictly earlier games only."""
    th = collections.defaultdict(list)
    ch = collections.defaultdict(list)
    sp = collections.defaultdict(list)
    for r in rows:
        t, c = r['team'], r['coach']
        r['_h'] = list(th[t])
        r['_ch'] = list(ch[c])
        prev = sp[(t, r['season'] - 1)]
        r['_prev_season'] = float(np.mean(prev)) if prev else None
        v = r[key]
        if v:
            th[t].append(v); ch[c].append(v); sp[(t, r['season'])].append(v)
    return rows


def baselines(r, league_mean):
    h, ch = r['_h'], r['_ch']
    return {
        'league_mean': league_mean,
        'team_expanding': float(np.mean(h)) if h else league_mean,
        'last_game': float(h[-1]) if h else league_mean,
        'roll3': float(np.mean(h[-3:])) if h else league_mean,
        'roll5': float(np.mean(h[-5:])) if h else league_mean,
        'ewma': float(ewma(h)) if h else league_mean,
        'prev_season': (r['_prev_season'] if r['_prev_season'] is not None
                        else league_mean),
        'coach_prior': (float(np.mean(ch)) if len(ch) >= 8 else league_mean),
    }


# --------------------------------------------------------------------------
def normality(res):
    """Reported BEFORE any Gaussian is used. Rule 8 of the platform: this is a
    description of the residuals, not a verdict that they are or are not
    normal."""
    r = np.asarray(res, float)
    n = len(r)
    mu, sd = r.mean(), r.std(ddof=1)
    z = (r - mu) / sd
    g1 = float((z ** 3).mean())
    g2 = float((z ** 4).mean() - 3.0)
    jb = n / 6.0 * (g1 ** 2 + g2 ** 2 / 4.0)
    return {
        'n': int(n), 'mean': float(mu), 'sd': float(sd),
        'skew': g1, 'excess_kurtosis': g2,
        'jarque_bera': float(jb),
        'jb_p_lt_0.001': bool(jb > 13.816),
        'frac_abs_z_gt_1.96': float((np.abs(z) > 1.96).mean()),
        'frac_abs_z_gt_2.58': float((np.abs(z) > 2.58).mean()),
        'frac_abs_z_gt_3.29': float((np.abs(z) > 3.29).mean()),
        'gaussian_expectation': [0.05, 0.01, 0.001],
        'q01': float(np.percentile(z, 1)), 'q99': float(np.percentile(z, 99)),
    }


def fit_t_df(z):
    """df by profile likelihood on a coarse pre-declared grid. Not optimised to
    the evaluation season -- z is training-season residuals only."""
    z = np.asarray(z, float)
    best, bestll = None, -np.inf
    for df in (3, 4, 5, 6, 8, 10, 15, 20, 30, 50, 200):
        s = math.sqrt(df / (df - 2.0))          # unit-variance scaling
        x = z * s
        ll = (len(x) * (math.lgamma((df + 1) / 2) - math.lgamma(df / 2)
                        - 0.5 * math.log(df * math.pi) + math.log(s))
              - (df + 1) / 2 * np.log1p(x * x / df).sum())
        if ll > bestll:
            best, bestll = df, ll
    return best, float(bestll)


def crps_samples(draws, y):
    """CRPS from samples, sorted-sample identity. draws (n, m), y (n,)."""
    d = np.sort(np.asarray(draws, np.float64), axis=1)
    n, m = d.shape
    y = np.asarray(y, np.float64).reshape(-1, 1)
    i = np.arange(1, m + 1, dtype=np.float64).reshape(1, -1)
    w = m * (y < d).astype(np.float64) - i + 0.5
    return (2.0 / (m * m)) * ((d - y) * w).sum(axis=1)


# --------------------------------------------------------------------------
def build_forms(res_rows, key, rng_seed):
    """Fit every candidate form on a set of TRAINING rows carrying '_resid'."""
    res = np.array([r['_resid'] for r in res_rows], float)
    out = {'_residuals': res, 'normality': normality(res)}
    out['gaussian_sd'] = float(res.std(ddof=1))
    z = (res - res.mean()) / res.std(ddof=1)
    df, ll = fit_t_df(z)
    out['t_df'] = df
    out['t_loglik'] = ll
    _, ll_norm = None, float(
        -0.5 * len(z) * math.log(2 * math.pi) - 0.5 * (z * z).sum())
    out['gaussian_loglik'] = ll_norm
    by_team = collections.defaultdict(list)
    by_coach = collections.defaultdict(list)
    for r in res_rows:
        by_team[r['team']].append(r['_resid'])
        by_coach[r['coach']].append(r['_resid'])
    out['team_residuals'] = {k: np.array(v, float)
                             for k, v in by_team.items() if len(v) >= MIN_COND_GAMES}
    out['coach_residuals'] = {k: np.array(v, float)
                              for k, v in by_coach.items() if len(v) >= MIN_COND_GAMES}
    return out


def draw(form, fit, rows, rng):
    """Return (n, M) residual draws for `rows` under `form`."""
    n = len(rows)
    m = M_DRAWS
    res = fit['_residuals']
    if form == 'empirical':
        return res[rng.integers(0, len(res), size=(n, m))]
    if form == 'gaussian':
        return rng.normal(0.0, fit['gaussian_sd'], size=(n, m))
    if form == 'student_t':
        df = fit['t_df']
        sd = fit['gaussian_sd']
        return rng.standard_t(df, size=(n, m)) * (sd / math.sqrt(df / (df - 2.0)))
    if form in ('team_empirical', 'coach_empirical'):
        pool = fit['team_residuals'] if form == 'team_empirical' else fit['coach_residuals']
        fld = 'team' if form == 'team_empirical' else 'coach'
        out = np.empty((n, m))
        n_fallback = 0
        for i, r in enumerate(rows):
            p = pool.get(r[fld])
            if p is None:
                p = res
                n_fallback += 1
            out[i] = p[rng.integers(0, len(p), size=m)]
        fit.setdefault('_fallback', {})[form] = n_fallback
        return out
    raise ValueError(form)


def coverage(draws, y, levels=(0.50, 0.80, 0.90, 0.95)):
    q = {}
    for L in levels:
        lo = np.percentile(draws, 100 * (1 - L) / 2, axis=1)
        hi = np.percentile(draws, 100 * (1 - (1 - L) / 2), axis=1)
        q[f'{int(L*100)}'] = {
            'coverage': float(((y >= lo) & (y <= hi)).mean()),
            'mean_width': float((hi - lo).mean())}
    return q


def pit(draws, y, bins=10):
    u = (draws < y.reshape(-1, 1)).mean(axis=1)
    h, _ = np.histogram(u, bins=bins, range=(0, 1))
    return {'hist': h.tolist(), 'n': int(len(u)),
            'expected_per_bin': float(len(u) / bins),
            'chi2': float((((h - len(u) / bins) ** 2) / (len(u) / bins)).sum()),
            'df': bins - 1}


def main():
    rows_all = load()
    result = {}
    store = {}
    for key in DEN:
        rows = [dict(r) for r in rows_all]
        rows = attach(rows, key)
        rows = [r for r in rows if r[key] > 0]
        res_key = {}
        print(f'\n=== {key} : {len(rows)} team-games with a positive denominator')

        def prep(train_seasons, eval_rows_seasons):
            tr = [r for r in rows if r['season'] in train_seasons]
            lm = float(np.mean([r[key] for r in tr])) if tr else None
            for r in rows:
                r['_b'] = baselines(r, lm)
            return tr, lm

        for ev in EVAL:
            inner = ev - 1
            # ---- 1. inner pass: choose the FORM on season ev-1 -------------
            tr_i = [r for r in rows if r['season'] < inner]
            va_i = [r for r in rows if r['season'] == inner]
            if len(tr_i) < 200 or len(va_i) < 100:
                form_pick, inner_crps = 'empirical', None
            else:
                lm_i = float(np.mean([r[key] for r in tr_i]))
                for r in rows:
                    r['_b'] = baselines(r, lm_i)
                est_i = min(BASELINES,
                            key=lambda b: np.mean([abs(r[key] - r['_b'][b]) for r in tr_i]))
                for r in tr_i + va_i:
                    r['_resid'] = r[key] - r['_b'][est_i]
                fit_i = build_forms(tr_i, key, SEED)
                yv = np.array([r[key] for r in va_i], float)
                pv = np.array([r['_b'][est_i] for r in va_i], float)
                inner_crps = {}
                for f in FORMS:
                    rng = np.random.default_rng(SEED + 7)
                    d = pv.reshape(-1, 1) + draw(f, fit_i, va_i, rng)
                    inner_crps[f] = float(crps_samples(d, yv).mean())
                form_pick = min(inner_crps, key=inner_crps.get)

            # ---- 2. outer pass: fit on all seasons < ev --------------------
            tr = [r for r in rows if r['season'] < ev]
            te = [r for r in rows if r['season'] == ev]
            lm = float(np.mean([r[key] for r in tr]))
            for r in rows:
                r['_b'] = baselines(r, lm)
            est = min(BASELINES,
                      key=lambda b: np.mean([abs(r[key] - r['_b'][b]) for r in tr]))
            for r in tr + te:
                r['_resid'] = r[key] - r['_b'][est]
            fit = build_forms(tr, key, SEED)

            y = np.array([r[key] for r in te], float)
            p = np.array([r['_b'][est] for r in te], float)

            per_form = {}
            for f in FORMS:
                rng = np.random.default_rng(SEED + 13)
                d = p.reshape(-1, 1) + draw(f, fit, te, rng)
                per_form[f] = {
                    'crps': float(crps_samples(d, y).mean()),
                    'coverage': coverage(d, y),
                    'pit': pit(d, y),
                }
            # SYSTEM B: the unconditional form chosen on the inner season.
            # SYSTEM C: the conditional form, only if the inner season also
            # preferred a conditional one; otherwise C is declared UNSUPPORTED
            # for this target-season rather than forced into existence.
            uncond = [f for f in FORMS if f in ('empirical', 'gaussian', 'student_t')]
            cond = [f for f in FORMS if f.endswith('_empirical') and f != 'empirical']
            if inner_crps:
                b_form = min(uncond, key=lambda f: inner_crps[f])
                c_form = min(cond, key=lambda f: inner_crps[f])
                c_supported = inner_crps[c_form] < inner_crps[b_form]
            else:
                b_form, c_form, c_supported = 'empirical', 'team_empirical', False

            res_key[ev] = {
                'n_eval': len(te), 'n_train': len(tr),
                'train_seasons': sorted({r['season'] for r in tr}),
                'point_estimator': est,
                'point_mae': float(np.abs(y - p).mean()),
                'point_r': (float(np.corrcoef(y, p)[0, 1]) if p.std() > 0 else None),
                'realized_sd': float(y.std(ddof=1)),
                'residual_sd_train': fit['gaussian_sd'],
                'normality_train': fit['normality'],
                't_df': fit['t_df'],
                'inner_validation_season': inner,
                'inner_crps': inner_crps,
                'form_B': b_form, 'form_C': c_form,
                'C_supported_on_inner': bool(c_supported),
                'per_form': per_form,
                'conditional_fallbacks': fit.get('_fallback', {}),
                'n_teams_with_own_residuals': len(fit['team_residuals']),
                'n_coaches_with_own_residuals': len(fit['coach_residuals']),
            }
            print(f'  {ev}: est={est:15s} mae={np.abs(y-p).mean():6.3f} '
                  f'sd_y={y.std(ddof=1):6.3f} kurt={fit["normality"]["excess_kurtosis"]:+.3f} '
                  f't_df={fit["t_df"]:3d} B={b_form:12s} C={c_form:15s} '
                  f'C_supported={c_supported}')
            for f in FORMS:
                pf = per_form[f]
                print(f'      {f:16s} crps={pf["crps"]:7.4f} '
                      f'cov50={pf["coverage"]["50"]["coverage"]:.3f} '
                      f'cov80={pf["coverage"]["80"]["coverage"]:.3f} '
                      f'cov90={pf["coverage"]["90"]["coverage"]:.3f} '
                      f'cov95={pf["coverage"]["95"]["coverage"]:.3f} '
                      f'w90={pf["coverage"]["90"]["mean_width"]:6.2f}')

            # ---- 3. persist the draws the player layer will consume --------
            rngB = np.random.default_rng(SEED + 101)
            rngC = np.random.default_rng(SEED + 211)
            dB = p.reshape(-1, 1) + draw(b_form, fit, te, rngB)
            dC = p.reshape(-1, 1) + draw(c_form, fit, te, rngC)
            # A denominator cannot be negative. Clipping is a modelling choice
            # and its rate is reported rather than swallowed.
            nclipB = int((dB < 0).sum()); nclipC = int((dC < 0).sum())
            res_key[ev]['negative_draw_rate'] = {
                'B': nclipB / dB.size, 'C': nclipC / dC.size}
            np.clip(dB, 0, None, out=dB); np.clip(dC, 0, None, out=dC)
            store[(key, ev)] = {
                'keys': [(r['team'], r['ord']) for r in te],
                'point': p.astype(np.float32),
                'realized': y.astype(np.float32),
                'B': dB.astype(np.float32),
                'C': dC.astype(np.float32),
            }
        result[key] = res_key

    json.dump(result, open(f'{HERE}/volume_results.json', 'w'), indent=1,
              default=lambda o: o.tolist() if isinstance(o, np.ndarray) else str(o))
    np.save(f'{HERE}/volume_store.npy',
            np.array([{'k': k, **v} for k, v in store.items()], dtype=object),
            allow_pickle=True)
    print('\nwrote volume_results.json and volume_store.npy')


if __name__ == '__main__':
    main()
