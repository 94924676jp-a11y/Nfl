"""TD2: frame, estimands and rare-event metrics.

Pre-registration sha256
31e75d823c0027a9a4f623670a2cf104de6a1eccde8adf4027ae3d2b0f250f83.

Unit of evaluation is the OPPORTUNITY. A player-game with n opportunities and
k touchdowns is n Bernoulli trials at the row's predicted rate, so trial-level
log loss, Brier and AUC are exact from counts without per-play identity.

EXPLORATORY. 2022-2025 are heavily mined. Nothing may be promoted.
"""
from __future__ import annotations

import bisect, collections, math, os, pickle, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'rc1'))
import rc1_lib as L                                            # noqa: E402

EVAL = [2022, 2023, 2024, 2025]
SEED = 20260908
K_SHRINK = 4.0
HL = 2.0
EPS = 1e-12

# (label, opportunity field, TD field). PRIMARY first, per the pre-registration.
ESTIMANDS = {
    'rec': [('target', 'targets', 'rec_td'),
            ('rz_target', 'rz_targets', 'rec_td_rz'),
            ('in10_target', 'in10_targets', 'rec_td_in10'),
            ('in5_target', 'in5_targets', 'rec_td_in5'),
            ('g2g_target', 'g2g_targets', 'rec_td_g2g')],
    'rush': [('carry', 'carries', 'rush_td'),
             ('rz_carry', 'rz_carries', 'rush_td_rz'),
             ('in10_carry', 'in10_carries', 'rush_td_in10'),
             ('in5_carry', 'in5_carries', 'rush_td_in5'),
             ('g2g_carry', 'g2g_carries', 'rush_td_g2g')],
}
PRIMARY = {'rec': 'target', 'rush': 'carry'}
POS = {'rec': ('WR', 'TE', 'RB'), 'rush': ('WR', 'TE', 'RB', 'QB')}


def load(kind: str, opp_field: str, td_field: str):
    """Frame rows carrying (n, k) for one estimand, plus prior-only history."""
    P = pickle.load(open(f'{HERE}/td2.pkl', 'rb'))['player']
    rows, _sub = L.load()
    rs = [r for r in rows if r.get('position') in POS[kind]]
    rs.sort(key=lambda r: (r['ord'], r['team'], r['gsis_id']))
    for r in rs:
        m = P.get((r['season'], r['week'], r['team'], r['gsis_id'])) or {}
        r['n_opp'] = int(m.get(opp_field, 0))
        r['n_td'] = int(m.get(td_field, 0))
        # location mix, prior-only when used; realised here for the L4 feature
        # it is NEVER read from the current row (see attach()).
        r['n_rz'] = int(m.get('rz_targets' if kind == 'rec' else 'rz_carries', 0))
        r['all_opp'] = int(m.get('targets' if kind == 'rec' else 'carries', 0))
    attach(rs)
    return rs


def attach(rs):
    """Prior-only conversion and opportunity history. Strict ordinal prefix cut."""
    hist = collections.defaultdict(list)
    hord = collections.defaultdict(list)
    for r in rs:
        pid = r['gsis_id']
        i = bisect.bisect_left(hord[pid], r['ord'])
        past = [x for x in hist[pid][:i] if x['appeared']]
        r['h_games'] = len(past)
        r['h_n'] = sum(x['n_opp'] for x in past)
        r['h_k'] = sum(x['n_td'] for x in past)
        r['h_all_opp'] = sum(x['all_opp'] for x in past)
        r['h_rz'] = sum(x['n_rz'] for x in past)
        r['h_opp_per_game'] = (r['h_n'] / len(past)) if past else None
        # game-level conversion series, for EWMA and split-half
        r['h_rates'] = [(x['n_td'] / x['n_opp']) for x in past if x['n_opp'] > 0]
        r['h_pairs'] = [(x['n_td'], x['n_opp']) for x in past if x['n_opp'] > 0]
        hist[pid].append(r)
        hord[pid].append(r['ord'])
    return rs


def eligible(r, ev=None):
    if ev is not None and r['season'] != ev:
        return False
    return bool(r['appeared'] and r['n_opp'] >= 1 and r['h_games'] >= 1)


def ewma(vals, hl=HL):
    lam = 0.5 ** (1.0 / hl)
    num = den = 0.0
    w = 1.0
    for v in reversed(vals):
        num += w * v
        den += w
        w *= lam
    return num / den if den > 0 else None


# --------------------------------------------------------------------------
# rare-event metrics, exact from (n, k, p)
# --------------------------------------------------------------------------
def metrics(n, k, p):
    """n opportunities, k touchdowns, p predicted rate -- all arrays per row."""
    n = np.asarray(n, float); k = np.asarray(k, float)
    p = np.clip(np.asarray(p, float), EPS, 1 - EPS)
    N = float(n.sum()); K = float(k.sum())
    base = K / N
    ll = float(-(k * np.log(p) + (n - k) * np.log(1 - p)).sum() / N)
    brier = float(((k * (1 - p) ** 2 + (n - k) * p ** 2).sum()) / N)

    # Murphy decomposition, on the predicted-probability bins.
    # Brier = reliability - resolution + uncertainty. RESOLUTION IS THE
    # DISCRIMINATION TEST: a model that only shrinks toward the base rate
    # improves reliability and gains no resolution.
    # THE DECOMPOSITION IS EXACT ONLY WHEN PREDICTIONS ARE CONSTANT WITHIN A
    # BIN. Quantile bins leave a within-bin variance term and the identity
    # fails to close -- measured at 1e-4, small enough to look like rounding
    # and large enough to be wrong. Bins are therefore the UNIQUE PREDICTED
    # VALUES, which makes rel - res + unc == Brier exactly. The readable
    # 10-quantile calibration table is built separately and is a REPORT, not
    # the decomposition.
    uq, inv = np.unique(p, return_inverse=True)
    rel = res = 0.0
    for b in range(len(uq)):
        m = inv == b
        nb = float(n[m].sum())
        if nb <= 0:
            continue
        pb = float(uq[b])
        ob = float(k[m].sum() / nb)
        rel += nb * (pb - ob) ** 2
        res += nb * (ob - base) ** 2
    rel /= N; res /= N

    # TWO RESOLUTIONS, AND THEY MEASURE DIFFERENT THINGS.
    #
    # The unique-value decomposition above closes the identity EXACTLY, which
    # the quantile-binned one does not -- the binned form leaves a within-bin
    # variance residual measured at ~1e-4, small enough to look like rounding
    # and large enough to be wrong. But with a near-continuous predictor almost
    # every unique-value bin holds a handful of trials, so its observed rate is
    # 0 or 1 and `res_exact` is upward-biased by that sparsity. It is NOT a
    # discrimination measure.
    #
    # The 10-quantile binned resolution IS the interpretable discrimination
    # measure and is what the pre-registration's "resolution is the
    # discrimination test" means. Both are reported; the binned one governs.
    res_exact = res
    rel_b = res_b = 0.0
    edges = np.unique(np.concatenate([[0.0], np.quantile(p, np.linspace(0, 1, 11)),
                                      [1.0]]))
    idx = np.clip(np.searchsorted(edges, p, side='right') - 1, 0, len(edges) - 2)
    table = []
    for b in range(len(edges) - 1):
        m = idx == b
        nb = float(n[m].sum())
        if nb <= 0:
            continue
        pb = float((p[m] * n[m]).sum() / nb)
        ob = float(k[m].sum() / nb)
        rel_b += nb * (pb - ob) ** 2
        res_b += nb * (ob - base) ** 2
        table.append({'bin': b, 'n_opp': int(nb), 'n_td': int(k[m].sum()),
                      'pred': pb, 'obs': ob})
    rel_b /= N; res_b /= N
    unc = base * (1 - base)

    # AUC from aggregated trials: rank distinct predicted rates.
    # AUC = P(p_pos > p_neg) + 0.5 P(tie). Iterating ASCENDING, the positives
    # that outrank a block's negatives are the ones in HIGHER blocks, so the
    # accumulator must be positives ABOVE, not below. Counting positives below
    # inverts the statistic -- it returned 0.253 for a perfect predictor.
    order = np.argsort(p)
    ps, ks, ns = p[order], k[order], n[order]
    auc_num = 0.0
    pos_seen = 0.0
    i = 0
    while i < len(ps):
        j = i
        while j < len(ps) and ps[j] == ps[i]:
            j += 1
        blk_pos = float(ks[i:j].sum())
        blk_neg = float((ns[i:j] - ks[i:j]).sum())
        pos_above = K - pos_seen - blk_pos
        auc_num += blk_neg * pos_above + 0.5 * blk_neg * blk_pos
        pos_seen += blk_pos
        i = j
    P_ = K; N_ = N - K
    auc = (auc_num / (P_ * N_)) if P_ > 0 and N_ > 0 else None

    return {'n_opportunities': int(N), 'n_td': int(K), 'base_rate': base,
            'log_loss': ll, 'brier': brier,
            'reliability_exact': rel, 'resolution_exact': res_exact,
            'uncertainty': unc, 'brier_check': rel - res_exact + unc,
            'reliability': rel_b,
            # `resolution` is the BINNED one: the interpretable discrimination
            # measure, and the one the state rules use.
            'resolution': res_b,
            'binned_closure_residual': brier - (rel_b - res_b + unc),
            'auc': auc,
            'sd_pred': float(np.sqrt(((p - (p * n).sum() / N) ** 2 * n).sum() / N)),
            'mean_pred': float((p * n).sum() / N),
            'calibration_table': table}


def cluster_bootstrap(rows, n, k, p_by_arm, stat, B=1000, seed=SEED):
    """Resample GAMES. Player-games in one game share opponent and script."""
    rng = np.random.default_rng(seed)
    by = collections.defaultdict(list)
    for i, r in enumerate(rows):
        by[r['game_id']].append(i)
    keys = list(by)
    idxs = [np.array(by[q]) for q in keys]
    out = {a: [] for a in p_by_arm}
    for _ in range(B):
        pick = rng.integers(0, len(keys), len(keys))
        sel = np.concatenate([idxs[j] for j in pick])
        for a, p in p_by_arm.items():
            out[a].append(stat(n[sel], k[sel], p[sel]))
    return {a: {'lo': float(np.quantile(v, 0.025)),
                'hi': float(np.quantile(v, 0.975))} for a, v in out.items()}
