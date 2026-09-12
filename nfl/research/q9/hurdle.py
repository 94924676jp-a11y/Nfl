"""Q9 step 1: the two-stage target hurdle, forward-chained.

    python3.12 -m nfl.research.q9.hurdle

THE ARCHITECTURE.

    P(appears)                production R8, unchanged, upstream
      x P(targeted | appears) STAGE 1 -- the hurdle, fitted here
      -> allocation | targeted STAGE 2 -- positive-only, exact

THE TWO STAGES ARE NOT COLLAPSED. Stage 1 is fitted on APPEARED player-games
only and is a conditional probability. The marginal zero-target probability is
composed at draw time as 1 - p_appear * p_hurdle and is never fitted as one
quantity, because a player who is out and a player who dressed and was ignored
are different events with different predictors.

WHY THERE IS A ONE-TARGET FLOOR. A multinomial over the roster can hand a
"positive" player zero targets, which would make the hurdle decorative. Every
clearer therefore receives one target and the REMAINDER is allocated among the
clearers by multinomial over the unchanged baseline weights. Team targets
reconcile exactly on every draw by construction.

THE ONLY CHANGE. Stage 2 allocates on the SAME `base` vector the baseline
allocates on -- the same class prior, the same shrinkage weight, the same
own-history share. The budget is the frozen P4B point plus its own residual
pool, with the Q8 shrink repair deliberately absent. Appearance, receiving
efficiency and the touchdown layer are untouched.
"""
from __future__ import annotations

import argparse
import collections
import csv
import gzip
import json
import math
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
for _q in (str(_REPO), str(_REPO / 'nfl' / 'research' / 'p2'),
           str(_REPO / 'nfl' / 'research' / 'p4b')):
    if _q not in sys.path:
        sys.path.insert(0, _q)

import p4b_volume as V                                            # noqa: E402
import stage_a as SA                                              # noqa: E402
from nfl.production.nonqb import appearance_r7 as R7              # noqa: E402
from nfl.research.q6 import frame as Q6F                          # noqa: E402
from nfl.research.q6 import forward_chain as Q6C                  # noqa: E402
from nfl.research.q7 import panel as Q7P                          # noqa: E402
from nfl.research.q8 import audit as AUD                          # noqa: E402

SPEC_VERSION = 'q9-target-hurdle-1'
HERE = _REPO / 'nfl' / 'research' / 'q9'
RESULTS = HERE / 'Q9_FORWARD_CHAIN_RESULTS.json'
DIAGNOSTICS = HERE / 'Q9_DIAGNOSTICS.csv'
ROWS = HERE / 'Q9_HURDLE_ROWS.csv.gz'

ARMS = ('BASELINE', 'Q9_HURDLE')
EVAL_SEASONS = (2022, 2023, 2024, 2025)
N_DRAWS = 400
SEED = 20260920
L2 = 1.0
HL = 3.0                    # the participation EWMA half-life, declared
DEPTH_BUCKETS = ((0, 0, '0'), (1, 3, '1-3'), (4, 8, '4-8'), (9, 16, '9-16'),
                 (17, 10 ** 6, '17+'))

# Named states for the two ways the hurdle can fail to fill a budget.
NO_CLEARERS = 'HURDLE_NO_CLEARERS'
MORE_CLEARERS_THAN_BUDGET = 'HURDLE_MORE_CLEARERS_THAN_BUDGET'

FEATURE_NAMES = (
    'intercept',
    'prior_target_frequency', 'prior_target_frequency_missing',
    'prior_zero_target_frequency',
    'recent_participation_ewma', 'recent_participation_missing',
    'prior_share_given_positive', 'prior_share_given_positive_missing',
    'prior_opportunity_depth_capped', 'is_cold_start',
    'role_starter', 'role_rotational', 'role_fringe',
    'rank_r1', 'rank_r23', 'rank_r4plus_or_unlisted',
    'pos_RB', 'pos_WR', 'pos_TE',
    'inj_Out', 'inj_Doubtful', 'inj_Questionable',
    'inj_did_not_practise', 'inj_report_available',
    'expected_team_budget_standardised',
)

FORBIDDEN_INPUTS = ('realized', 'realised', 'actual_targets', 'weekly_rosters',
                    'roster_status', 'inactive_list', 'spread', 'vegas',
                    'total_line', 'odds', 'postgame', 'final_')


def assert_pregame_only(names):
    bad = [f for f in names
           if any(s in str(f).lower() for s in FORBIDDEN_INPUTS)]
    if bad:
        raise ValueError(
            f'Q9_NON_PREGAME_INPUT: {bad}. Current-game realised availability, '
            f'realised targets, game-day roster status and market quantities '
            f'may not enter the hurdle. The list is refused, not filtered.')
    return True


assert_pregame_only(FEATURE_NAMES)


def _bucket(n, table=DEPTH_BUCKETS):
    for lo, hi, lab in table:
        if lo <= n <= hi:
            return lab
    return table[-1][2]


def _ewma(vals, hl=HL):
    if not vals:
        return None
    lam = 0.5 ** (1.0 / hl)
    num = den = 0.0
    w = 1.0
    for v in reversed(vals):
        num += w * v
        den += w
        w *= lam
    return num / den


def attach_hurdle_history(rows):
    """Prior target behaviour per player, from strictly earlier APPEARED games.

    Only appeared games enter the history: the hurdle is a conditional
    probability given appearance, so a game the player missed carries no
    information about whether he would have been targeted.
    """
    hist = collections.defaultdict(list)
    for r in sorted(rows, key=lambda x: (x['s'], x['w'], x['t'], x['pid'])):
        past = hist[r['pid']]
        hits = [1.0 if x['targets'] > 0 else 0.0 for x in past]
        pos_shares = [x['share_targets'] for x in past
                      if x['targets'] > 0 and x.get('share_targets') is not None]
        r['h_appeared_games'] = len(past)
        r['h_target_freq'] = float(np.mean(hits)) if hits else None
        r['h_participation_ewma'] = _ewma(hits)
        r['h_share_given_positive'] = (float(np.mean(pos_shares[-8:]))
                                       if pos_shares else None)
        r['prior_depth_bucket'] = _bucket(len(past))
        if r['appeared']:
            hist[r['pid']].append(r)
    return rows


def featurise(r, budget_z):
    f = [1.0]
    tf = r.get('h_target_freq')
    f.append(0.0 if tf is None else float(tf))
    f.append(1.0 if tf is None else 0.0)
    f.append(0.0 if tf is None else 1.0 - float(tf))
    pe = r.get('h_participation_ewma')
    f.append(0.0 if pe is None else float(pe))
    f.append(1.0 if pe is None else 0.0)
    sp = r.get('h_share_given_positive')
    f.append(0.0 if sp is None else float(sp))
    f.append(1.0 if sp is None else 0.0)
    n = r.get('h_appeared_games') or 0
    f.append(min(n, 20) / 20.0)
    f.append(1.0 if n == 0 else 0.0)
    for c in Q6F.ROLE_CLASSES:
        f.append(1.0 if r['role_class'] == c else 0.0)
    grp = Q6F._rank_group(r.get('rank'))
    for gname in Q6F.RANK_GROUPS:
        f.append(1.0 if grp == gname else 0.0)
    for p in ('RB', 'WR', 'TE'):
        f.append(1.0 if r['pos'] == p else 0.0)
    st = r.get('inj_status')
    for L in R7.STATUS:
        f.append(1.0 if st == L else 0.0)
    f.append(1.0 if (r.get('inj_practice') or '').startswith('Did Not') else 0.0)
    f.append(float(r.get('inj_available') or 0))
    f.append(float(budget_z))
    return f


assert len(featurise(
    {'role_class': 'starter', 'pos': 'WR', 'rank': 1}, 0.0)) == \
    len(FEATURE_NAMES), 'Q9_FEATURE_NAME_COUNT_MISMATCH'


def fit_hurdle(train, budget_point, bud_mean, bud_sd):
    """Stage 1, on APPEARED training rows only. The estimator is imported."""
    rows = [r for r in train if r['appeared']]
    if len(rows) < 500:
        return None
    X, y = [], []
    for r in rows:
        bz = ((budget_point.get((r['s'], r['w'], r['t']), bud_mean) - bud_mean)
              / max(bud_sd, 1e-9))
        X.append(featurise(r, bz))
        y.append(1.0 if r['targets'] > 0 else 0.0)
    return SA.fit_logistic(X, y, l2=L2)


def allocate_hurdle(base, clear, budget, weights_rng):
    """Stage 2 for ONE draw: every clearer gets one target, the rest is drawn.

    Returns (counts, fallback_state_or_None). Reconciles to `budget` exactly.
    """
    idx = np.where(clear)[0]
    out = np.zeros(len(base))
    if budget <= 0:
        return out, None
    if len(idx) == 0:
        # NAMED, NOT SILENT. The budget is never dropped and no player is
        # forced active: the draw degrades to the baseline mechanism.
        w = np.maximum(base, 0.0)
        if w.sum() <= 0:
            return out, NO_CLEARERS
        out[:] = weights_rng.multinomial(int(budget), w / w.sum())
        return out, NO_CLEARERS
    if len(idx) > budget:
        # The declared hurdle probabilities are PRESERVED IN PROPORTION: the
        # budget's worth of clearers is chosen without replacement weighted by
        # each clearer's own hurdle probability, rather than truncating the
        # tail by an arbitrary rule.
        p = np.maximum(base[idx], 1e-12)
        pick = weights_rng.choice(idx, size=int(budget), replace=False,
                                  p=p / p.sum())
        out[pick] = 1.0
        return out, MORE_CLEARERS_THAN_BUDGET
    out[idx] = 1.0
    rem = int(budget) - len(idx)
    if rem > 0:
        w = np.maximum(base[idx], 0.0)
        if w.sum() <= 0:
            w = np.ones(len(idx))
        out[idx] += weights_rng.multinomial(rem, w / w.sum())
    return out, None


# ------------------------------------------------------------- the chain
def _crps(draws, y):
    return float(V.crps_samples(np.asarray(draws, float).reshape(1, -1),
                                np.array([float(y)]))[0])


def _certainty(p):
    return ('near_certain' if p >= 0.9 else 'likely' if p >= 0.7
            else 'uncertain' if p >= 0.4 else 'doubtful')


REALISED_REGIMES = ((0, 0, '0'), (1, 2, '1-2'), (3, 5, '3-5'), (6, 9, '6-9'),
                    (10, 10 ** 6, '10+'))


def run(eval_seasons=EVAL_SEASONS, n_draws=N_DRAWS, seed=SEED, progress=True):
    rows, _ = Q6F.load_frame()
    rows = Q6F.attach_role_class(rows)
    rows, _ = Q6F.attach_opportunity(rows)
    rows = AUD._own_history(rows)
    q7_recv = Q7P.load_recv()
    rows, join_ev = AUD.attach_receiving(rows, q7_recv)
    rows = attach_hurdle_history(rows)
    p_r8 = AUD.load_p_r8()
    denom = AUD.load_denom()

    out_rows, team_rows, fit_log = [], [], []
    fallbacks = collections.Counter()

    for Y in eval_seasons:
        train = [r for r in rows if r['s'] < Y]
        test = [r for r in rows if r['s'] == Y]
        if not train or not test:
            continue
        # THE Q8 SHRINK REPAIR IS DELIBERATELY ABSENT. This is the frozen P4B
        # point and its own residual pool, which is what production draws.
        bud_point, bud_resid, bud_est = AUD.budget_model(denom, Y)
        bvals = np.array([v for v in bud_point.values()], float)
        bud_mean, bud_sd = float(bvals.mean()), float(bvals.std(ddof=1))
        model = fit_hurdle(train, bud_point, bud_mean, bud_sd)
        if model is None:
            continue
        cm_fit = AUD._class_means(train)
        k_fit, _ = Q6C._share_k(train, 'targets')
        eff = AUD.efficiency_fit(q7_recv, Y)

        groups = collections.defaultdict(list)
        for r in test:
            groups[(r['s'], r['w'], r['t'])].append(r)

        for gkey, g in sorted(groups.items()):
            den = int(g[0]['den_targets'])
            if den <= 0:
                continue
            own = np.array([r['own_share'] if r['own_share'] is not None
                            else AUD._class_of(cm_fit, r) for r in g], float)
            n_own = np.array([r['own_n'] for r in g], float)
            cls = np.array([AUD._class_of(cm_fit, r) for r in g], float)
            w = np.where(n_own > 0, n_own / (n_own + k_fit), 0.0)
            base = np.maximum(w * own + (1 - w) * cls, 0.0)
            pv = np.array([p_r8.get((r['s'], r['w'], r['t'], r['pid']), 0.0)
                           for r in g], float)
            bz = (bud_point.get(gkey, bud_mean) - bud_mean) / max(bud_sd, 1e-9)
            ph = np.asarray(SA.predict(
                model, [featurise(r, bz) for r in g]), float)
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
                if arm == 'BASELINE':
                    W = np.tile(base, (n_draws, 1)) * A
                    tot = W.sum(axis=1, keepdims=True)
                    P = np.divide(W, tot, out=np.zeros_like(W), where=tot > 0)
                    for d in range(n_draws):
                        if budget[d] > 0 and P[d].sum() > 0:
                            T[d] = rng.multinomial(
                                int(budget[d]), P[d] / P[d].sum())
                else:
                    H = rng.binomial(1, np.clip(ph, 0.0, 1.0),
                                     size=(n_draws, len(g)))
                    C = (A == 1) & (H == 1)
                    for d in range(n_draws):
                        T[d], fb = allocate_hurdle(base, C[d], int(budget[d]),
                                                   rng)
                        if fb:
                            fallbacks[(arm, fb)] += 1
                        fallbacks[(arm, 'DRAWS')] += 1
                recon = float(np.abs(T.sum(axis=1) - budget).max())
                YD = AUD._yards(T, eff, rng)
                team_rows.append({
                    'season': Y, 'week': gkey[1], 'team': gkey[2], 'arm': arm,
                    'team_game': f'{Y}-{gkey[1]}-{gkey[2]}',
                    'actual_team_targets': den,
                    'mean_budget_drawn': round(float(budget.mean()), 4),
                    'max_reconciliation_error': recon,
                    'n_players': len(g)})
                for j, r in enumerate(g):
                    d = T[:, j]
                    pos = d[d > 0]
                    reg = REALISED_REGIMES[-1][2]
                    for lo, hi, lab in REALISED_REGIMES:
                        if lo <= y_tgt[j] <= hi:
                            reg = lab
                            break
                    out_rows.append({
                        'season': Y, 'week': r['w'], 'team': r['t'],
                        'pid': r['pid'], 'pos': r['pos'],
                        'role_class': r['role_class'], 'arm': arm,
                        'team_game': f"{Y}-{r['w']}-{r['t']}",
                        'appearance_certainty': _certainty(pv[j]),
                        'prior_depth': r['prior_depth_bucket'],
                        'p_appear': round(float(pv[j]), 6),
                        'p_hurdle': round(float(ph[j]), 6),
                        'actual_targets': y_tgt[j],
                        'is_zero_actual': int(y_tgt[j] == 0),
                        'p_zero_pred': round(float((d == 0).mean()), 6),
                        'pred_targets': round(float(d.mean()), 5),
                        'marginal_crps': round(_crps(d, y_tgt[j]), 5),
                        'marginal_pit': round(float((d < y_tgt[j]).mean() +
                                                    0.5 * (d == y_tgt[j]).mean()),
                                              5),
                        'positive_crps': (round(_crps(pos, y_tgt[j]), 5)
                                          if len(pos) and y_tgt[j] > 0 else ''),
                        'positive_pred': (round(float(pos.mean()), 5)
                                          if len(pos) else ''),
                        'positive_pit': (round(float((pos < y_tgt[j]).mean() +
                                                     0.5 * (pos == y_tgt[j]).mean()),
                                               5)
                                         if len(pos) and y_tgt[j] > 0 else ''),
                        'actual_rec_yards': y_yds[j],
                        'rec_yard_crps': round(_crps(YD[:, j], y_yds[j]), 5),
                        'realised_target_regime': reg,
                    })
        fit_log.append({
            'eval_season': Y, 'n_train': len(train), 'n_test': len(test),
            'budget_estimator': bud_est, 'budget_mean': round(bud_mean, 4),
            'q8_budget_repair_applied': False,
            'k_fitted_share': round(k_fit, 5),
            'catch_rate': round(eff['catch_rate'], 5),
            'n_hurdle_training_rows': sum(1 for r in train if r['appeared']),
        })
        if progress:
            print(f'  {Y}: {len(test)} rows', flush=True)
    return {'rows': out_rows, 'team': team_rows, 'fit_log': fit_log,
            'fallbacks': {f'{a}|{b}': n for (a, b), n in fallbacks.items()},
            'receiving_join_evidence': join_ev}


# ------------------------------------------------------------- scoring
BOOT = 1000
BOOT_SEED = 20260921


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
    for b in range(n):
        pick = rng.integers(0, len(pos), size=len(pos))
        out[b] = diffs[np.concatenate([pos[j] for j in pick])].mean()
    lo, hi = np.percentile(out, [2.5, 97.5])
    return {'mean': round(float(diffs.mean()), 6),
            'ci_lo': round(float(lo), 6), 'ci_hi': round(float(hi), 6),
            'n_clusters': len(pos), 'n_rows': int(len(diffs)),
            'excludes_zero': bool(lo > 0 or hi < 0)}


def _calibration_bins(p, y, bins=10):
    p = np.asarray(p, float)
    y = np.asarray(y, float)
    edges = np.linspace(0.0, 1.0, bins + 1)
    out, ece = [], 0.0
    for i in range(bins):
        lo, hi = edges[i], edges[i + 1]
        sel = (p >= lo) & (p < hi if i < bins - 1 else p <= hi)
        k = int(sel.sum())
        if not k:
            out.append({'bin': f'{lo:.1f}-{hi:.1f}', 'n': 0})
            continue
        mp, ob = float(p[sel].mean()), float(y[sel].mean())
        out.append({'bin': f'{lo:.1f}-{hi:.1f}', 'n': k,
                    'mean_predicted': round(mp, 5),
                    'observed_rate': round(ob, 5), 'gap': round(mp - ob, 5)})
        ece += k / len(p) * abs(mp - ob)
    return out, round(float(ece), 6)


def _pit_chi2(pits, bins=10):
    v = [float(x) for x in pits if x != '']
    if not v:
        return None
    h, _ = np.histogram(np.asarray(v, float), bins=bins, range=(0, 1))
    e = len(v) / bins
    return {'n': len(v), 'chi2': round(float(((h - e) ** 2 / e).sum()), 3),
            'df': bins - 1}


def _zero_block(rs):
    y = np.array([r['is_zero_actual'] for r in rs], float)
    p = np.clip(np.array([r['p_zero_pred'] for r in rs], float), 1e-9,
                1 - 1e-9)
    bins, ece = _calibration_bins(p, y)
    return {'n': len(rs), 'brier': round(float(np.mean((p - y) ** 2)), 6),
            'log_loss': round(float(-np.mean(
                y * np.log(p) + (1 - y) * np.log(1 - p))), 6),
            'predicted_zero_rate': round(float(p.mean()), 5),
            'observed_zero_rate': round(float(y.mean()), 5),
            'zero_rate_gap': round(float(p.mean() - y.mean()), 5),
            'abs_zero_rate_gap': round(abs(float(p.mean() - y.mean())), 5),
            'expected_calibration_error': ece, 'calibration_bins': bins}


def _positive_block(rs):
    sel = [r for r in rs if r['positive_crps'] != '' and r['actual_targets'] > 0]
    if not sel:
        return {'n': 0}
    c = np.array([float(r['positive_crps']) for r in sel], float)
    e = np.array([float(r['positive_pred']) - r['actual_targets']
                  for r in sel], float)
    return {'n': len(sel), 'mean_crps': round(float(c.mean()), 6),
            'bias': round(float(e.mean()), 5),
            'pit': _pit_chi2([r['positive_pit'] for r in sel])}


def _marginal_block(rs):
    c = np.array([r['marginal_crps'] for r in rs], float)
    return {'n': len(rs), 'mean_crps': round(float(c.mean()), 6),
            'bias': round(float(np.mean(
                [r['pred_targets'] - r['actual_targets'] for r in rs])), 5),
            'pit': _pit_chi2([r['marginal_pit'] for r in rs]),
            'zero_mass_calibration': {
                'predicted': round(float(np.mean(
                    [r['p_zero_pred'] for r in rs])), 5),
                'observed': round(float(np.mean(
                    [r['is_zero_actual'] for r in rs])), 5)}}


def _yard_block(rs):
    return {'n': len(rs), 'mean_crps': round(float(np.mean(
        [r['rec_yard_crps'] for r in rs])), 6)}


def _arm_blocks(rs):
    return {'zero_target_probability': _zero_block(rs),
            'positive_target_distribution': _positive_block(rs),
            'full_marginal_target_distribution': _marginal_block(rs),
            'downstream_receiving_yards': _yard_block(rs)}


def _sweep(rows, keyf):
    g = collections.defaultdict(list)
    for r in rows:
        g[keyf(r)].append(r)
    out = {}
    for k, rs in sorted(g.items()):
        if len(rs) < 80:
            continue
        ent = {arm: _arm_blocks([r for r in rs if r['arm'] == arm])
               for arm in ARMS}
        keyed = collections.defaultdict(dict)
        for r in rs:
            keyed[(r['season'], r['week'], r['team'], r['pid'])][r['arm']] = r
        common = [v for v in keyed.values() if len(v) == len(ARMS)]
        if common:
            for metric, field in (('marginal', 'marginal_crps'),
                                  ('receiving_yards', 'rec_yard_crps')):
                b = np.array([v['BASELINE'][field] for v in common], float)
                c = np.array([v['Q9_HURDLE'][field] for v in common], float)
                ent.setdefault('paired', {})[metric] = {
                    'delta_pct': round(100.0 * float((c - b).mean()) /
                                       float(b.mean()), 4),
                    'improves': bool((c - b).mean() < 0),
                    'block_bootstrap_by_team_game': boot_paired(
                        c - b, [v['BASELINE']['team_game'] for v in common])}
            zb = ent['BASELINE']['zero_target_probability']
            zh = ent['Q9_HURDLE']['zero_target_probability']
            ent['paired']['zero_brier_improves'] = bool(
                zh['brier'] < zb['brier'])
            ent['paired']['zero_gap_narrows'] = bool(
                zh['abs_zero_rate_gap'] < zb['abs_zero_rate_gap'])
        out[k] = ent
    return out


def summarise(res):
    rows = res['rows']
    out = {
        'artifact': 'NFL_Q9_FORWARD_CHAIN_RESULTS',
        'spec_version': SPEC_VERSION, 'promoted': False,
        'is_research_only': True, 'market_inputs_used': [],
        'live_2026_rows_used': 0,
        'q8_budget_repair_applied': False,
        'arms': list(ARMS), 'n_rows': len(rows),
        'eval_seasons': sorted({r['season'] for r in rows}),
        'stage_1_feature_names': list(FEATURE_NAMES),
        'stages_not_collapsed': (
            'P(appears) is production R8 and P(targeted | appears) is fitted '
            'on appeared rows only; the marginal zero probability is composed '
            'at draw time as 1 - p_appear * p_hurdle and is never fitted as '
            'one quantity'),
        'held_fixed': [
            'the team target budget: frozen P4B point plus its residual pool, '
            'with the Q8 shrink repair deliberately absent',
            'the appearance model: production R8',
            'the class-level prior', 'the share shrinkage weight',
            'receiving efficiency', 'the touchdown layer',
        ],
        'clustering': 'block bootstrap over whole team-games',
        'by_arm': {}, 'paired': {},
        'fallbacks': _fallback_block(res['fallbacks']),
        'reconciliation': _recon_block(res['team']),
        'fit_log': res['fit_log'],
    }
    for arm in ARMS:
        out['by_arm'][arm] = _arm_blocks([r for r in rows if r['arm'] == arm])
    keyed = collections.defaultdict(dict)
    for r in rows:
        keyed[(r['season'], r['week'], r['team'], r['pid'])][r['arm']] = r
    common = [v for v in keyed.values() if len(v) == len(ARMS)]
    cl = [v['BASELINE']['team_game'] for v in common]
    for metric, field in (('marginal_crps', 'marginal_crps'),
                          ('receiving_yard_crps', 'rec_yard_crps')):
        b = np.array([v['BASELINE'][field] for v in common], float)
        c = np.array([v['Q9_HURDLE'][field] for v in common], float)
        out['paired'][metric] = {
            'delta_pct': round(100.0 * float((c - b).mean()) /
                               float(b.mean()), 4),
            'block_bootstrap_by_team_game': boot_paired(c - b, cl)}
    pos = [v for v in common if v['BASELINE']['positive_crps'] != ''
           and v['Q9_HURDLE']['positive_crps'] != ''
           and v['BASELINE']['actual_targets'] > 0]
    if pos:
        b = np.array([float(v['BASELINE']['positive_crps']) for v in pos])
        c = np.array([float(v['Q9_HURDLE']['positive_crps']) for v in pos])
        out['paired']['positive_crps'] = {
            'delta_pct': round(100.0 * float((c - b).mean()) /
                               float(b.mean()), 4),
            'block_bootstrap_by_team_game': boot_paired(
                c - b, [v['BASELINE']['team_game'] for v in pos])}
    zb = np.array([(r['p_zero_pred'] - r['is_zero_actual']) ** 2
                   for r in rows if r['arm'] == 'BASELINE'], float)
    zh = np.array([(r['p_zero_pred'] - r['is_zero_actual']) ** 2
                   for r in rows if r['arm'] == 'Q9_HURDLE'], float)
    out['paired']['zero_brier'] = {
        'delta_mean': round(float((zh - zb).mean()), 8),
        'block_bootstrap_by_team_game': boot_paired(
            zh - zb, [r['team_game'] for r in rows if r['arm'] == 'BASELINE'])}
    out['by_position'] = _sweep(rows, lambda r: r['pos'])
    out['by_role_class'] = _sweep(rows, lambda r: r['role_class'])
    out['by_appearance_certainty'] = _sweep(
        rows, lambda r: r['appearance_certainty'])
    out['by_prior_opportunity_depth'] = _sweep(rows, lambda r: r['prior_depth'])
    out['diagnostic_not_read_by_the_decision'] = {
        'note': ('a realised-target-volume breakdown. It is defined FROM the '
                 'outcome, so it may not select a model and `decide` does not '
                 'read it. It is emitted because it is informative to a '
                 'reader who already knows the verdict.'),
        'by_realised_target_regime': _sweep(
            rows, lambda r: r['realised_target_regime']),
    }
    out['decision'] = decide(out)
    return out


def _fallback_block(fb):
    draws = fb.get('Q9_HURDLE|DRAWS', 0)
    out = {'n_hurdle_draws': draws, 'states': {}}
    for name in (NO_CLEARERS, MORE_CLEARERS_THAN_BUDGET):
        k = f'Q9_HURDLE|{name}'
        n = fb.get(k, 0)
        out['states'][name] = {
            'n': n, 'rate': round(n / draws, 8) if draws else None}
    out['NO_CLEARERS_means'] = (
        'nobody cleared the hurdle but the budget was positive. The draw '
        'degrades to the baseline mechanism over every appearing player; the '
        'budget is never dropped and no player is forced active.')
    out['MORE_CLEARERS_THAN_BUDGET_means'] = (
        'more clearers than targets. The budget\'s worth of clearers is drawn '
        'without replacement weighted by each clearer\'s own hurdle '
        'probability, so the declared probabilities are preserved in '
        'proportion rather than the tail being truncated by an arbitrary rule.')
    return out


def _recon_block(team_rows):
    out = {}
    for arm in ARMS:
        sel = [t for t in team_rows if t['arm'] == arm]
        out[arm] = {
            'n_team_games': len(sel),
            'max_absolute_reconciliation_error': (
                max(t['max_reconciliation_error'] for t in sel)
                if sel else None),
            'exact': bool(sel and max(
                t['max_reconciliation_error'] for t in sel) == 0.0)}
    return out


def decide(summary):
    """SUPPORT / WEAK_SUPPORT / REJECT, against the rule frozen in the spec.

      SUPPORT requires ALL of: improved zero-target calibration (Brier and log
      loss both improve and the absolute predicted-minus-observed zero-rate
      gap narrows); positive-target CRPS not significantly worse on the
      team-game-clustered bootstrap; full marginal target CRPS improved or not
      worse; and exact team reconciliation on every draw.

      WEAK_SUPPORT: zero-target calibration improves and nothing above is
      significantly worse, but the marginal CRPS does not improve.

      REJECT: otherwise.

    A GAIN IN RECEIVING-YARD CRPS ALONE IS INSUFFICIENT, and this function
    never reads that metric when deciding.
    """
    b = summary['by_arm']['BASELINE']
    h = summary['by_arm']['Q9_HURDLE']
    zb, zh = b['zero_target_probability'], h['zero_target_probability']
    zero_ok = (zh['brier'] < zb['brier']
               and zh['log_loss'] < zb['log_loss']
               and zh['abs_zero_rate_gap'] < zb['abs_zero_rate_gap'])
    pos = summary['paired'].get('positive_crps') or {}
    pbb = pos.get('block_bootstrap_by_team_game') or {}
    pos_worse = bool(pbb.get('excludes_zero') and pbb.get('mean', 0) > 0)
    marg = summary['paired']['marginal_crps']
    mbb = marg['block_bootstrap_by_team_game']
    marg_improves = marg['delta_pct'] < 0
    marg_worse = bool(mbb['excludes_zero'] and mbb['mean'] > 0)
    recon = summary['reconciliation']['Q9_HURDLE']['exact']
    if not recon:
        dec = 'REJECT'
    elif zero_ok and not pos_worse and not marg_worse and marg_improves:
        dec = 'SUPPORT'
    elif zero_ok and not pos_worse and not marg_worse:
        dec = 'WEAK_SUPPORT'
    else:
        dec = 'REJECT'
    return {
        'decision': dec,
        'zero_target_calibration_improved': bool(zero_ok),
        'zero_brier': [zb['brier'], zh['brier']],
        'zero_log_loss': [zb['log_loss'], zh['log_loss']],
        'zero_rate_gap_abs': [zb['abs_zero_rate_gap'], zh['abs_zero_rate_gap']],
        'positive_crps_significantly_worse': pos_worse,
        'positive_crps_delta_pct': pos.get('delta_pct'),
        'marginal_crps_delta_pct': marg['delta_pct'],
        'marginal_crps_improves': bool(marg_improves),
        'marginal_crps_significantly_worse': marg_worse,
        'team_reconciliation_exact': bool(recon),
        'receiving_yard_crps_not_read_by_this_rule': True,
        'rule': decide.__doc__.strip(),
    }


def _write(rows, path, gz=True):
    if not rows:
        raise SystemExit(f'Q9_EMPTY_TABLE: {path} would carry no rows. An '
                         f'empty table is an error, not a result.')
    opener = ((lambda: gzip.open(path, 'wt', newline='')) if gz
              else (lambda: open(path, 'w', newline='')))
    with opener() as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return len(rows)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--seasons', default=','.join(str(s) for s in EVAL_SEASONS))
    ap.add_argument('--draws', type=int, default=N_DRAWS)
    a = ap.parse_args(argv)
    res = run(tuple(int(x) for x in a.seasons.split(',')), a.draws)
    s = summarise(res)
    s['n_draws'] = a.draws
    RESULTS.write_text(json.dumps(s, indent=1, default=str) + '\n')
    _write(res['rows'], ROWS)
    _write(res['team'], DIAGNOSTICS, gz=False)
    d = s['decision']
    print(f"\nrows       : {len(res['rows'])}")
    print(f"decision   : {d['decision']}")
    print(f"  zero brier   {d['zero_brier'][0]:.6f} -> {d['zero_brier'][1]:.6f}")
    print(f"  zero logloss {d['zero_log_loss'][0]:.6f} -> "
          f"{d['zero_log_loss'][1]:.6f}")
    print(f"  zero gap     {d['zero_rate_gap_abs'][0]:.5f} -> "
          f"{d['zero_rate_gap_abs'][1]:.5f}")
    print(f"  marginal CRPS {d['marginal_crps_delta_pct']:+.4f}%  "
          f"positive CRPS {d['positive_crps_delta_pct']:+.4f}%")
    print(f"  reconciliation exact: {d['team_reconciliation_exact']}")
    print(f"  fallbacks: {s['fallbacks']['states']}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
