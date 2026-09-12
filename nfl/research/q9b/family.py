"""Q9B step 2: the minimal family comparison, the fallback audit, the PIT scan.

    python3.12 -m nfl.research.q9b.family

THREE ARMS, registered in `Q9B_PREREGISTRATION.md` before any was built:

  BASELINE    current R8 allocation
  MNL_PLUS    a conditional logit over the appearing players on the SAME
              pregame covariates Q9's stage 1 uses, plus the log production
              share. No hurdle, no floor.
  Q9_HURDLE   the supported Q9 mechanism, IMPORTED FROM `nfl.research.q9`
              and frozen -- the allocator, the floor and both fallbacks are
              called, never reimplemented here.

MNL_PLUS IS THE TEST OF THE MECHANISM. It gets the same information the hurdle
gets. If the hurdle is only a reparameterisation of a better share model, this
arm recovers the same ground. The identifiability audit predicts it will
recover about a THIRD of the production zero-mass shortfall -- 1.22 points of
mis-estimated share out of 3.90 -- and that prediction is checked, not assumed.

NO DIRICHLET-MULTINOMIAL ARM. The dispersion audit measured a median variance
ratio of 1.193 at the CORRECT share against a threshold of 1.25 fixed before
the number was read. This system does not exhibit the overdispersion DM exists
to model, and an arm added on a literature scan alone would be an arm added
for no measured reason.
"""
from __future__ import annotations

import argparse
import collections
import csv
import gzip
import json
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
for _q in (str(_REPO), str(_REPO / 'nfl' / 'research' / 'p4b')):
    if _q not in sys.path:
        sys.path.insert(0, _q)

import p4b_volume as V                                            # noqa: E402
from nfl.research.q6 import frame as Q6F                          # noqa: E402
from nfl.research.q6 import forward_chain as Q6C                  # noqa: E402
from nfl.research.q7 import panel as Q7P                          # noqa: E402
from nfl.research.q8 import audit as AUD                          # noqa: E402
from nfl.research.q9 import hurdle as Q9                          # noqa: E402

SPEC_VERSION = 'q9b-family-1'
HERE = _REPO / 'nfl' / 'research' / 'q9b'
ARMS = ('BASELINE', 'MNL_PLUS', 'Q9_HURDLE')
EVAL_SEASONS = Q9.EVAL_SEASONS
N_DRAWS = 400
SEED = 20260923
BOOT = 1000
BOOT_SEED = 20260924

# The identifiability audit's decomposition, quoted so the falsifiable check
# is against a recorded number rather than a remembered one.
PREDICTED_SHARE_RECOVERABLE = 0.01224
PRODUCTION_SHORTFALL = 0.03903


def mnl_features(r, base_share, bz):
    """The SAME pregame covariates stage 1 uses, plus the log production share.

    Giving MNL_PLUS the hurdle's own information is the point: if it still
    cannot reach the hurdle's zero mass, the difference is the mechanism and
    not the feature set.
    """
    f = list(Q9.featurise(r, bz))
    f.append(float(np.log(max(base_share, 1e-9))))
    return f


def fit_mnl(groups, l2=1.0, iters=400, lr=0.5):
    """Conditional logit by gradient ascent on the multinomial likelihood.

    For a team-week with budget N and design rows x_i, the share is
    softmax(x_i'b) and the gradient of the log-likelihood is
    sum_i (y_i - N * pi_i) x_i. Deliberately small and readable: a coefficient
    vector that can be printed is the point, as it is in `stage_a`.
    """
    if not groups:
        return None
    X_all = np.vstack([g['X'] for g in groups])
    mu = X_all.mean(0)
    sd = X_all.std(0)
    sd[sd == 0] = 1.0
    mu[0] = 0.0
    sd[0] = 1.0
    Gs = [{'X': (g['X'] - mu) / sd, 'y': g['y'], 'N': g['N']} for g in groups]
    b = np.zeros(X_all.shape[1])
    n_obs = sum(g['N'] for g in Gs) or 1.0
    for _ in range(iters):
        grad = np.zeros_like(b)
        for g in Gs:
            z = g['X'] @ b
            z -= z.max()
            e = np.exp(z)
            pi = e / e.sum()
            grad += g['X'].T @ (g['y'] - g['N'] * pi)
        grad = grad / n_obs - l2 * b / n_obs
        grad[0] = grad[0] + l2 * b[0] / n_obs
        b += lr * grad
    return {'b': b, 'mu': mu, 'sd': sd}


def mnl_shares(model, X):
    z = ((np.asarray(X, float) - model['mu']) / model['sd']) @ model['b']
    z = z - z.max()
    e = np.exp(z)
    return e / e.sum()


def _crps(draws, y):
    return float(V.crps_samples(np.asarray(draws, float).reshape(1, -1),
                                np.array([float(y)]))[0])


def boot_paired(diffs, clusters, n=BOOT, seed=BOOT_SEED):
    diffs = np.asarray(diffs, float)
    if not len(diffs):
        return None
    idx = collections.defaultdict(list)
    for i, c in enumerate(clusters):
        idx[c].append(i)
    pos = [np.asarray(v, int) for v in idx.values()]
    rng = np.random.default_rng(seed)
    out = np.empty(n)
    for bi in range(n):
        pick = rng.integers(0, len(pos), size=len(pos))
        out[bi] = diffs[np.concatenate([pos[j] for j in pick])].mean()
    lo, hi = np.percentile(out, [2.5, 97.5])
    return {'mean': round(float(diffs.mean()), 6),
            'ci_lo': round(float(lo), 6), 'ci_hi': round(float(hi), 6),
            'n_clusters': len(pos), 'n_rows': int(len(diffs)),
            'excludes_zero': bool(lo > 0 or hi < 0)}


# ---------------------------------------------------------------- the run
def run(eval_seasons=EVAL_SEASONS, n_draws=N_DRAWS, seed=SEED, progress=True):
    rows, _ = Q6F.load_frame()
    rows = Q6F.attach_role_class(rows)
    rows, _ = Q6F.attach_opportunity(rows)
    rows = AUD._own_history(rows)
    q7 = Q7P.load_recv()
    rows, _ = AUD.attach_receiving(rows, q7)
    rows = Q9.attach_hurdle_history(rows)
    p_r8 = AUD.load_p_r8()
    denom = AUD.load_denom()

    out_rows, fb_rows, fit_log = [], [], []
    fallbacks = collections.Counter()
    sel_check = []

    for Y in eval_seasons:
        train = [r for r in rows if r['s'] < Y]
        test = [r for r in rows if r['s'] == Y]
        if not train or not test:
            continue
        bud_point, bud_resid, bud_est = AUD.budget_model(denom, Y)
        bvals = np.array(list(bud_point.values()), float)
        bmean, bsd = float(bvals.mean()), float(bvals.std(ddof=1))
        cm_fit = AUD._class_means(train)
        k_fit, _ = Q6C._share_k(train, 'targets')
        eff = AUD.efficiency_fit(q7, Y)
        hurdle_model = Q9.fit_hurdle(train, bud_point, bmean, bsd)
        if hurdle_model is None:
            continue

        def _base(g):
            own = np.array([r['own_share'] if r['own_share'] is not None
                            else AUD._class_of(cm_fit, r) for r in g], float)
            n_own = np.array([r['own_n'] for r in g], float)
            cls = np.array([AUD._class_of(cm_fit, r) for r in g], float)
            w = np.where(n_own > 0, n_own / (n_own + k_fit), 0.0)
            return np.maximum(w * own + (1 - w) * cls, 0.0)

        tr_groups = collections.defaultdict(list)
        for r in train:
            tr_groups[(r['s'], r['w'], r['t'])].append(r)
        mnl_train = []
        for gkey, g in tr_groups.items():
            app = [r for r in g if r['appeared']]
            if len(app) < 2:
                continue
            N = sum(r['targets'] for r in app)
            if N <= 0:
                continue
            b = _base(app)
            if b.sum() <= 0:
                continue
            pi = b / b.sum()
            bz = (bud_point.get(gkey, bmean) - bmean) / max(bsd, 1e-9)
            mnl_train.append({
                'X': np.array([mnl_features(r, pi[j], bz)
                               for j, r in enumerate(app)], float),
                'y': np.array([r['targets'] for r in app], float),
                'N': float(N)})
        mnl_model = fit_mnl(mnl_train)

        groups = collections.defaultdict(list)
        for r in test:
            groups[(r['s'], r['w'], r['t'])].append(r)

        for gkey, g in sorted(groups.items()):
            den = int(g[0]['den_targets'])
            if den <= 0:
                continue
            base = _base(g)
            pv = np.array([p_r8.get((r['s'], r['w'], r['t'], r['pid']), 0.0)
                           for r in g], float)
            bz = (bud_point.get(gkey, bmean) - bmean) / max(bsd, 1e-9)
            ph = np.asarray(Q9.SA.predict(
                hurdle_model, [Q9.featurise(r, bz) for r in g]), float)
            y_tgt = np.array([float(r['targets']) for r in g], float)
            y_yds = np.array([float(r['q7_yds']) for r in g], float)

            for arm in ARMS:
                rng = np.random.default_rng(
                    [seed, Y, gkey[1], AUD._stream(gkey[2]),
                     AUD._stream(arm)])
                budget = np.maximum(np.rint(
                    bud_point.get(gkey, den)
                    + bud_resid[rng.integers(0, len(bud_resid), n_draws)]),
                    0).astype(int)
                A = rng.binomial(1, np.clip(pv, 0.0, 1.0),
                                 size=(n_draws, len(g)))
                T = np.zeros((n_draws, len(g)))
                if arm == 'Q9_HURDLE':
                    H = rng.binomial(1, np.clip(ph, 0.0, 1.0),
                                     size=(n_draws, len(g)))
                    C = (A == 1) & (H == 1)
                    for d in range(n_draws):
                        # FROZEN: the supported allocator is called, not copied.
                        T[d], fb = Q9.allocate_hurdle(
                            base, C[d], int(budget[d]), rng)
                        fallbacks['DRAWS'] += 1
                        if fb:
                            fallbacks[fb] += 1
                            fb_rows.append({
                                'season': Y, 'week': gkey[1], 'team': gkey[2],
                                'state': fb, 'team_budget_drawn':
                                    int(budget[d]),
                                'actual_team_targets': den,
                                'n_players': len(g),
                                'n_appearing': int(A[d].sum()),
                                'n_clearers': int(C[d].sum()),
                                'budget_band': _band(int(budget[d]))})
                            if fb == Q9.MORE_CLEARERS_THAN_BUDGET:
                                # DOES THE WEIGHTED SUBSAMPLE DISTORT THE
                                # DECLARED PROBABILITIES? Recorded per clearer:
                                # was he selected, and what did he declare.
                                for j in np.where(C[d])[0]:
                                    sel_check.append({
                                        'p_hurdle': float(ph[j]),
                                        'selected': int(T[d][j] > 0),
                                        'role_class': g[j]['role_class'],
                                        'base_rank': int(
                                            np.argsort(-base)[j] if False
                                            else 0)})
                else:
                    if arm == 'MNL_PLUS' and mnl_model is not None:
                        bsum = base.sum()
                        pib = base / bsum if bsum > 0 else np.full(
                            len(g), 1.0 / len(g))
                        X = np.array([mnl_features(r, pib[j], bz)
                                      for j, r in enumerate(g)], float)
                        wgt = mnl_shares(mnl_model, X)
                    else:
                        wgt = base
                    W = np.tile(np.maximum(wgt, 0.0), (n_draws, 1)) * A
                    tot = W.sum(axis=1, keepdims=True)
                    P = np.divide(W, tot, out=np.zeros_like(W), where=tot > 0)
                    for d in range(n_draws):
                        if budget[d] > 0 and P[d].sum() > 0:
                            T[d] = rng.multinomial(
                                int(budget[d]), P[d] / P[d].sum())
                recon = float(np.abs(T.sum(axis=1) - budget).max())
                YD = AUD._yards(T, eff, rng)
                for j, r in enumerate(g):
                    d_ = T[:, j]
                    pos = d_[d_ > 0]
                    out_rows.append({
                        'season': Y, 'week': r['w'], 'team': r['t'],
                        'pid': r['pid'], 'pos': r['pos'],
                        'role_class': r['role_class'], 'arm': arm,
                        'team_game': f"{Y}-{r['w']}-{r['t']}",
                        'appearance_certainty': Q9._certainty(pv[j]),
                        'prior_depth': r['prior_depth_bucket'],
                        'appeared': int(r['appeared']),
                        'team_budget': den, 'budget_band': _band(den),
                        'actual_targets': y_tgt[j],
                        'is_zero_actual': int(y_tgt[j] == 0),
                        'p_zero_pred': round(float((d_ == 0).mean()), 6),
                        'pred_targets': round(float(d_.mean()), 5),
                        'marginal_crps': round(_crps(d_, y_tgt[j]), 5),
                        'marginal_pit': round(float((d_ < y_tgt[j]).mean()
                                                    + 0.5 * (d_ == y_tgt[j]).mean()),
                                              5),
                        'positive_crps': (round(_crps(pos, y_tgt[j]), 5)
                                          if len(pos) and y_tgt[j] > 0 else ''),
                        'rec_yard_crps': round(_crps(YD[:, j], y_yds[j]), 5),
                        'recon_error': recon,
                    })
        fit_log.append({'eval_season': Y, 'n_test': len(test),
                        'budget_estimator': bud_est,
                        'q8_budget_repair_applied': False,
                        'n_mnl_training_groups': len(mnl_train),
                        'mnl_n_features': (len(mnl_model['b'])
                                           if mnl_model else 0)})
        if progress:
            print(f'  {Y}: {len(test)} rows', flush=True)
    return {'rows': out_rows, 'fallback_rows': fb_rows,
            'fallbacks': dict(fallbacks), 'selection_check': sel_check,
            'fit_log': fit_log}


def _band(n):
    return ('<25' if n < 25 else '25-32' if n < 33 else
            '33-39' if n < 40 else '40+')


# ------------------------------------------------------------- reporting
def _pit_hist(pits, bins=10):
    v = [float(x) for x in pits if x != '']
    if not v:
        return None
    h, _ = np.histogram(np.asarray(v, float), bins=bins, range=(0, 1))
    e = len(v) / bins
    return {'n': len(v), 'hist': h.tolist(),
            'chi2': round(float(((h - e) ** 2 / e).sum()), 3),
            'chi2_per_row': round(float(((h - e) ** 2 / e).sum()) / len(v), 8)}


def _blocks(rs):
    y = np.array([r['is_zero_actual'] for r in rs], float)
    p = np.clip(np.array([r['p_zero_pred'] for r in rs], float), 1e-9, 1 - 1e-9)
    posr = [r for r in rs if r['positive_crps'] != '' and r['actual_targets'] > 0]
    return {
        'zero_target_probability': {
            'n': len(rs), 'brier': round(float(np.mean((p - y) ** 2)), 6),
            'log_loss': round(float(-np.mean(
                y * np.log(p) + (1 - y) * np.log(1 - p))), 6),
            'predicted_zero_rate': round(float(p.mean()), 5),
            'observed_zero_rate': round(float(y.mean()), 5),
            'zero_rate_gap': round(float(p.mean() - y.mean()), 5),
            'abs_zero_rate_gap': round(abs(float(p.mean() - y.mean())), 5)},
        'positive_target_distribution': {
            'n': len(posr),
            'mean_crps': (round(float(np.mean(
                [float(r['positive_crps']) for r in posr])), 6)
                if posr else None)},
        'full_marginal_target_distribution': {
            'n': len(rs),
            'mean_crps': round(float(np.mean(
                [r['marginal_crps'] for r in rs])), 6),
            'bias': round(float(np.mean(
                [r['pred_targets'] - r['actual_targets'] for r in rs])), 5),
            'pit': _pit_hist([r['marginal_pit'] for r in rs])},
        'downstream_receiving_yards': {
            'mean_crps': round(float(np.mean(
                [r['rec_yard_crps'] for r in rs])), 6)},
    }


def _sweep(rows, keyf, minimum=200):
    g = collections.defaultdict(list)
    for r in rows:
        g[keyf(r)].append(r)
    out = {}
    for k, rs in sorted(g.items()):
        if len(rs) < minimum * len(ARMS):
            continue
        ent = {arm: _blocks([r for r in rs if r['arm'] == arm])
               for arm in ARMS}
        keyed = collections.defaultdict(dict)
        for r in rs:
            keyed[(r['season'], r['week'], r['team'], r['pid'])][r['arm']] = r
        common = [v for v in keyed.values() if len(v) == len(ARMS)]
        if common:
            b = np.array([v['BASELINE']['marginal_crps'] for v in common])
            for arm in ARMS[1:]:
                c = np.array([v[arm]['marginal_crps'] for v in common])
                ent[arm]['marginal_delta_pct'] = round(
                    100.0 * float((c - b).mean()) / float(b.mean()), 4)
                ent[arm]['block_bootstrap_by_team_game'] = boot_paired(
                    c - b, [v['BASELINE']['team_game'] for v in common])
        out[k] = ent
    return out


def _falsifiable_check(by_arm):
    """Did the plain family recover the shortfall the audit said it could?"""
    b = by_arm['BASELINE']['zero_target_probability']
    obs = b['observed_zero_rate']
    shortfall = obs - b['predicted_zero_rate']
    out = {
        'baseline_zero_shortfall': round(shortfall, 6),
        'audit_predicted_share_recoverable': PREDICTED_SHARE_RECOVERABLE,
        'audit_production_shortfall': PRODUCTION_SHORTFALL,
        'by_arm': {},
        'reads': ('the fraction of the baseline\'s zero-mass shortfall each '
                  'arm closes. The identifiability audit predicted a plain '
                  'better-share arm could close about a third; an arm that '
                  'closes all of it would mean the hurdle is a '
                  'reparameterisation'),
    }
    for arm in ARMS[1:]:
        a = by_arm[arm]['zero_target_probability']
        closed = a['predicted_zero_rate'] - b['predicted_zero_rate']
        out['by_arm'][arm] = {
            'predicted_zero_rate': a['predicted_zero_rate'],
            'moved_toward_observed': round(closed, 6),
            'fraction_of_shortfall_closed': (round(closed / shortfall, 5)
                                             if abs(shortfall) > 1e-9 else None),
            'abs_gap': a['abs_zero_rate_gap'],
        }
    return out


def _fallback_audit(res, rows):
    fb = res['fallbacks']
    draws = fb.get('DRAWS', 0)
    out = {'n_hurdle_draws': draws, 'states': {}}
    for name in (Q9.NO_CLEARERS, Q9.MORE_CLEARERS_THAN_BUDGET):
        n = fb.get(name, 0)
        out['states'][name] = {'n': n,
                               'rate': round(n / draws, 8) if draws else None}
    fr = [r for r in res['fallback_rows']
          if r['state'] == Q9.MORE_CLEARERS_THAN_BUDGET]
    if fr:
        out['more_clearers_than_budget'] = {
            'n_events': len(fr),
            'by_budget_band': dict(collections.Counter(
                r['budget_band'] for r in fr)),
            'mean_team_budget_drawn': round(float(np.mean(
                [r['team_budget_drawn'] for r in fr])), 4),
            'mean_n_appearing': round(float(np.mean(
                [r['n_appearing'] for r in fr])), 4),
            'mean_n_clearers': round(float(np.mean(
                [r['n_clearers'] for r in fr])), 4),
            'max_team_budget_drawn': int(max(
                r['team_budget_drawn'] for r in fr)),
            'concentrated_in_low_budgets': bool(
                float(np.mean([r['team_budget_drawn'] for r in fr])) < 15),
        }
    sc = res['selection_check']
    if sc:
        # DOES THE WEIGHTED SUBSAMPLE DISTORT THE DECLARED PROBABILITIES?
        # Within the affected draws, compare each clearer's realised selection
        # rate against the hurdle probability he declared.
        by = collections.defaultdict(lambda: [0, 0])
        for s in sc:
            k = round(min(max(s['p_hurdle'], 0.0), 1.0), 1)
            by[k][0] += s['selected']
            by[k][1] += 1
        out['selection_distortion'] = {
            'n_clearer_observations': len(sc),
            'by_declared_hurdle_probability': {
                str(k): {'n': v[1], 'selected_rate': round(v[0] / v[1], 5)}
                for k, v in sorted(by.items()) if v[1] >= 30},
            'note': ('inside an affected draw the clearer set is already '
                     'conditioned on clearing, so a selection rate below 1 is '
                     'the subsample doing its job. What would be a defect is '
                     'the rate depending on the DECLARED probability in a way '
                     'the weighting did not intend -- the weighting is by the '
                     'base share, not by p_hurdle, so a strong gradient here '
                     'is the distortion to look for.'),
        }
    # The fallback rows carry season/week/team, not the composite key the
    # scored rows use. Building it here rather than adding a duplicate field
    # keeps one definition of a team-game.
    affected = {f"{r['season']}-{r['week']}-{r['team']}"
                for r in res['fallback_rows']}
    ha = [r for r in rows if r['arm'] == 'Q9_HURDLE'
          and r['team_game'] in affected]
    hn = [r for r in rows if r['arm'] == 'Q9_HURDLE'
          and r['team_game'] not in affected]
    if ha and hn:
        out['contribution'] = {
            'n_rows_in_affected_team_games': len(ha),
            'n_rows_elsewhere': len(hn),
            'marginal_crps_affected': round(float(np.mean(
                [r['marginal_crps'] for r in ha])), 6),
            'marginal_crps_elsewhere': round(float(np.mean(
                [r['marginal_crps'] for r in hn])), 6),
            'zero_gap_affected': round(float(np.mean(
                [r['p_zero_pred'] for r in ha]) - np.mean(
                [r['is_zero_actual'] for r in ha])), 5),
            'zero_gap_elsewhere': round(float(np.mean(
                [r['p_zero_pred'] for r in hn]) - np.mean(
                [r['is_zero_actual'] for r in hn])), 5),
        }
    return out


def _pit_diagnosis(rows):
    """Where the PIT deterioration lives. DIAGNOSED, never optimised."""
    out = {'note': ('PIT is diagnosed here and read by no decision. An arm '
                    'selected on its rank histogram would be an arm selected '
                    'on something that is not a proper score.')}
    for name, keyf in (
            ('by_actual_target_band',
             lambda r: ('zero' if r['actual_targets'] == 0 else
                        'low_1_2' if r['actual_targets'] <= 2 else
                        'mid_3_6' if r['actual_targets'] <= 6 else
                        'upper_tail_7plus')),
            ('by_role_class', lambda r: r['role_class']),
            ('by_prior_depth', lambda r: r['prior_depth'])):
        g = collections.defaultdict(list)
        for r in rows:
            g[(keyf(r), r['arm'])].append(r)
        ent = {}
        for (k, arm), rs in sorted(g.items()):
            if len(rs) < 200:
                continue
            ent.setdefault(k, {})[arm] = _pit_hist(
                [r['marginal_pit'] for r in rs])
        for k, v in ent.items():
            if 'BASELINE' in v and 'Q9_HURDLE' in v and v['BASELINE'] \
                    and v['Q9_HURDLE']:
                v['chi2_per_row_delta'] = round(
                    v['Q9_HURDLE']['chi2_per_row']
                    - v['BASELINE']['chi2_per_row'], 8)
                v['worsens'] = bool(v['chi2_per_row_delta'] > 0)
        out[name] = ent
    return out


def summarise(res):
    rows = res['rows']
    by_arm = {arm: _blocks([r for r in rows if r['arm'] == arm])
              for arm in ARMS}
    keyed = collections.defaultdict(dict)
    for r in rows:
        keyed[(r['season'], r['week'], r['team'], r['pid'])][r['arm']] = r
    common = [v for v in keyed.values() if len(v) == len(ARMS)]
    cl = [v['BASELINE']['team_game'] for v in common]
    paired = {}
    for arm in ARMS[1:]:
        paired[arm] = {}
        for metric, field in (('marginal_crps', 'marginal_crps'),
                              ('receiving_yard_crps', 'rec_yard_crps')):
            b = np.array([v['BASELINE'][field] for v in common], float)
            c = np.array([v[arm][field] for v in common], float)
            paired[arm][metric] = {
                'delta_pct': round(100.0 * float((c - b).mean()) /
                                   float(b.mean()), 4),
                'block_bootstrap_by_team_game': boot_paired(c - b, cl)}
        zb = np.array([(v['BASELINE']['p_zero_pred']
                        - v['BASELINE']['is_zero_actual']) ** 2
                       for v in common], float)
        za = np.array([(v[arm]['p_zero_pred'] - v[arm]['is_zero_actual']) ** 2
                       for v in common], float)
        paired[arm]['zero_brier'] = {
            'delta_mean': round(float((za - zb).mean()), 8),
            'block_bootstrap_by_team_game': boot_paired(za - zb, cl)}
    out = {
        'artifact': 'NFL_Q9B_MODEL_FAMILY_RESULTS',
        'spec_version': SPEC_VERSION, 'promoted': False,
        'is_research_only': True, 'market_inputs_used': [],
        'live_2026_rows_used': 0, 'q8_budget_repair_applied': False,
        'arms': list(ARMS),
        'dirichlet_multinomial_arm': {
            'included': False,
            'reason': ('the dispersion audit measured a median variance ratio '
                       'of 1.193 at the CORRECT share against a threshold of '
                       '1.25 fixed in code before the number was read. This '
                       'system does not exhibit the overdispersion a '
                       'Dirichlet-multinomial exists to model.')},
        'q9_is_frozen': ('the hurdle allocator, the one-target floor and both '
                         'fallbacks are imported from nfl.research.q9.hurdle '
                         'and called, never reimplemented or refitted here'),
        'n_rows': len(rows),
        'eval_seasons': sorted({r['season'] for r in rows}),
        'clustering': 'block bootstrap over whole team-games',
        'by_arm': by_arm, 'paired': paired,
        'falsifiable_check': _falsifiable_check(by_arm),
        'fallback_audit': _fallback_audit(res, rows),
        'pit_diagnosis': _pit_diagnosis(rows),
        'reconciliation': {
            arm: {'max_absolute_error': max(
                (r['recon_error'] for r in rows if r['arm'] == arm),
                default=None)} for arm in ARMS},
        'by_position': _sweep(rows, lambda r: r['pos']),
        'by_role_class': _sweep(rows, lambda r: r['role_class']),
        'by_appearance_certainty': _sweep(
            rows, lambda r: r['appearance_certainty']),
        'by_prior_depth': _sweep(rows, lambda r: r['prior_depth']),
        'fit_log': res['fit_log'],
    }
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--seasons', default=','.join(str(s) for s in EVAL_SEASONS))
    ap.add_argument('--draws', type=int, default=N_DRAWS)
    a = ap.parse_args(argv)
    res = run(tuple(int(x) for x in a.seasons.split(',')), a.draws)
    s = summarise(res)
    s['n_draws'] = a.draws
    (HERE / 'Q9B_FAMILY_RESULTS.json').write_text(
        json.dumps(s, indent=1, default=str) + '\n')
    (HERE / 'Q9_FALLBACK_AUDIT.json').write_text(
        json.dumps({'artifact': 'NFL_Q9_FALLBACK_AUDIT',
                    'spec_version': SPEC_VERSION,
                    **s['fallback_audit']}, indent=1, default=str) + '\n')
    with gzip.open(HERE / 'Q9B_FAMILY_ROWS.csv.gz', 'wt', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(res['rows'][0]))
        w.writeheader()
        w.writerows(res['rows'])
    print(f"\nrows: {len(res['rows'])}")
    for arm in ARMS:
        z = s['by_arm'][arm]['zero_target_probability']
        m = s['by_arm'][arm]['full_marginal_target_distribution']
        print(f"  {arm:11s} brier {z['brier']:.6f}  pzero {z['predicted_zero_rate']:.5f}"
              f"  gap {z['zero_rate_gap']:+.5f}  marg_crps {m['mean_crps']:.6f}"
              f"  pit_chi2 {m['pit']['chi2']:.0f}")
    fc = s['falsifiable_check']
    print(f"\nbaseline zero shortfall {fc['baseline_zero_shortfall']:+.5f}")
    for arm, v in fc['by_arm'].items():
        print(f"  {arm:11s} closed {v['fraction_of_shortfall_closed']}"
              f"  abs_gap {v['abs_gap']:.5f}")
    print(f"\nfallbacks: {s['fallback_audit']['states']}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
