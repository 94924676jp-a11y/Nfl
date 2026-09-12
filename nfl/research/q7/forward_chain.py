"""Q7 step 2: forward-chained efficiency, with opportunity oracled.

    python3.12 -m nfl.research.q7.forward_chain

THE ISOLATION. Every arm receives the REALISED attempts, completions, targets
and receptions. There is no volume error in the isolated condition at all, so
a volume error cannot disguise an efficiency error -- the requirement is met by
construction rather than controlled for.

THE LADDER OF ESTIMANDS, narrowest first:

    cmp | att        the completion rate alone
    ptd | cmp        passing-touchdown efficiency alone
    pyds | cmp       yards per completion alone -- no completion draw at all
    pyds | att       completion draw and yardage together
    rec | targets    the catch rate alone
    rec_yds | rec    yards per reception alone
    rec_yds | targets

`pyds | cmp` is where the width hypothesis lives purest: the only randomness
left is the yards-per-completion draw.

THE ARMS differ in the efficiency mechanism and in nothing else. They share the
opportunity, the pools, the per-row seed and the fitted own-history.
"""
from __future__ import annotations

import argparse
import bisect
import collections
import json
import math
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
for _q in (str(_REPO), str(_REPO / 'nfl' / 'research' / 'p4b')):
    if _q not in sys.path:
        sys.path.insert(0, _q)

import p4b_volume as V                                            # noqa: E402
from nfl.research.q7 import panel as PAN                          # noqa: E402

SPEC_VERSION = 'q7-forward-chain-1'
HERE = _REPO / 'nfl' / 'research' / 'q7'

ARMS = ('BASELINE', 'Q7_WIDTH', 'Q7_SHRINK', 'Q7_BOTH')
HEADLINE_ARM = 'Q7_BOTH'
EVAL_SEASONS = (2022, 2023, 2024, 2025)
N_DRAWS = 1000
SEED = 20260915

# The inherited constants this work is testing. Read from the production
# library rather than restated, so a change there cannot leave this stale.
INHERITED_K = 4.0

# Predeclared on football grounds before any result was seen.
QB_REGIMES = ((0, 19, '<20'), (20, 29, '20-29'), (30, 39, '30-39'),
              (40, 10 ** 6, '40+'))
RECV_REGIMES = ((1, 2, '1-2'), (3, 5, '3-5'), (6, 9, '6-9'),
                (10, 10 ** 6, '10+'))
DEPTH_BUCKETS = ((0, 0, '0'), (1, 3, '1-3'), (4, 8, '4-8'), (9, 16, '9-16'),
                 (17, 10 ** 6, '17+'))


def _bucket(n, table):
    for lo, hi, label in table:
        if lo <= n <= hi:
            return label
    return table[-1][2]


def _inherited_k():
    sys.path.insert(0, str(_REPO / 'nfl' / 'research' / 'qb2'))
    import qb2_lib as Q
    return float(Q.K)


# ------------------------------------------------------------- history
def attach_history(rows):
    """Strictly-prior own rows per player, by ordinal prefix cut.

    `bisect` on strictly-earlier ordinals, not "everything appended so far":
    a player-ordinal pair can carry two rows when a player changed team
    mid-week, and appending as we go lets the second read the first.
    """
    hist = collections.defaultdict(list)
    hord = collections.defaultdict(list)
    for r in sorted(rows, key=lambda x: (x['ord'], x['team'], x['gsis_id'])):
        pid = r['gsis_id']
        k = bisect.bisect_left(hord[pid], r['ord'])
        r['h_rows'] = hist[pid][:k]
        r['h_games'] = len(r['h_rows'])
        hist[pid].append(r)
        hord[pid].append(r['ord'])
    return rows


def own_rate(r, num, den, cut=None):
    """The player's own pooled rate over strictly earlier rows."""
    past = [x for x in r['h_rows'] if cut is None or x['season'] < cut]
    a = sum(x[num] for x in past)
    b = sum(x[den] for x in past)
    return (a / b) if b > 0 else None, len(past)


def own_list(r, num, den, cut=None):
    """The player's own per-game ratios, one per prior game with a denominator."""
    past = [x for x in r['h_rows'] if cut is None or x['season'] < cut]
    return np.array([x[num] / x[den] for x in past if x[den] > 0], float)


def estimate_k(train, num, den):
    """K = within-player variance / between-player variance. ESTIMATED.

    The same empirical-Bayes estimator the role prior and the R8 appearance
    weight already use, in the same units the production weight uses -- GAMES,
    because the production form is n_games/(n_games + K). Estimating it in
    attempt units would be a different weight wearing the same name.
    """
    by = collections.defaultdict(list)
    for r in train:
        if r[den] > 0:
            by[r['gsis_id']].append(r[num] / r[den])
    within, between = [], []
    for v in by.values():
        if len(v) >= 4:
            within.append(float(np.var(v, ddof=1)))
            between.append(float(np.mean(v)))
    if len(within) < 20:
        return INHERITED_K, {'basis': 'TOO_FEW_PLAYERS_KEPT_INHERITED',
                             'n_players': len(within)}
    w = float(np.mean(within))
    b = float(np.var(between, ddof=1))
    k = w / b if b > 0 else INHERITED_K
    return float(k), {'basis': 'WITHIN_OVER_BETWEEN_PLAYER_VARIANCE',
                      'within': round(w, 8), 'between': round(b, 8),
                      'k': round(float(k), 5), 'n_players': len(within)}


def _rate(r, pool, k):
    """w * own + (1 - w) * pool, the production form."""
    w = r['h_games'] / (r['h_games'] + k) if r['h_games'] else 0.0
    own = (r['h_num'] / r['h_den']) if r['h_den'] > 0 else None
    return (w * own + (1 - w) * pool) if own is not None else pool, w


def _mix_draw(rng, own, pool, w, m):
    """The production `_mix`: a Bernoulli switch between two resamples."""
    own = np.asarray(own, float)
    if len(own) == 0 or w <= 0:
        return pool[rng.integers(0, len(pool), m)]
    use = rng.random(m) < w
    return np.where(use, own[rng.integers(0, len(own), m)],
                    pool[rng.integers(0, len(pool), m)])


def _width_scaled(draw, own, pool, w, n, n_ref):
    """The same draw, recentred on its own conditional mean and rescaled.

    A game yards-per-completion is an average over however many completions
    that game happened to have. The production mechanism resamples it whole
    and multiplies by this game's completion count, so the predictive spread of
    PER-COMPLETION yardage does not depend on how many completions there are.
    Real per-completion means concentrate about as 1/sqrt(n).

    The scale is sqrt(n_ref / n) with n_ref the training-frame mean completion
    count, so it is exactly 1.0 at an average game and this arm cannot win by
    being globally wider or globally tighter. THE MEAN IS UNCHANGED BY
    CONSTRUCTION: only the deviation from it is scaled.
    """
    mu = (w * float(np.mean(own)) + (1 - w) * float(np.mean(pool))
          if len(own) else float(np.mean(pool)))
    s = math.sqrt(n_ref / max(float(n), 1.0))
    return mu + (np.asarray(draw, float) - mu) * s


def _binom_logscore(y, n, p):
    """Exact log score for a Binomial predictive. No smoothing, no bandwidth."""
    p = min(max(float(p), 1e-9), 1 - 1e-9)
    n, y = int(n), int(y)
    if y < 0 or y > n:
        return float('inf')
    return -(math.lgamma(n + 1) - math.lgamma(y + 1) - math.lgamma(n - y + 1)
             + y * math.log(p) + (n - y) * math.log(1 - p))


def _score(draws, y):
    d = np.asarray(draws, float)
    return {
        'crps': float(V.crps_samples(d.reshape(1, -1), np.array([float(y)]))[0]),
        'mean': float(d.mean()), 'sd': float(d.std(ddof=1)) if len(d) > 1 else 0.0,
        'pit': float((d < y).mean() + 0.5 * (d == y).mean()),
        'error': float(d.mean() - y),
    }


def _cov(draws, y):
    out = {}
    for L in (50, 80, 90, 95):
        lo = float(np.percentile(draws, (100 - L) / 2))
        hi = float(np.percentile(draws, 100 - (100 - L) / 2))
        out[L] = int(lo <= y <= hi)
    return out


# ------------------------------------------------------------- the chain
def _pools(train):
    """League fallbacks, from training rows only."""
    att = sum(r['att'] for r in train)
    cmp_ = sum(r['cmp'] for r in train)
    ptd = sum(r['ptd'] for r in train)
    return {
        'p_cmp': cmp_ / att if att else 0.6,
        'p_ptd': ptd / cmp_ if cmp_ else 0.05,
        'ypc': np.array([r['pyds'] / r['cmp'] for r in train if r['cmp'] > 0],
                        float),
        'n_ref_cmp': float(np.mean([r['cmp'] for r in train if r['cmp'] > 0])),
        'att_mean': float(np.mean([r['att'] for r in train])),
    }


def _recv_pools(train):
    tg = sum(r['targets'] for r in train)
    rc = sum(r['rec'] for r in train)
    flat = [y for r in train for y in r['rec_yards_list']]
    return {
        'p_rec': rc / tg if tg else 0.62,
        'ypr_flat': np.array(flat, float) if flat else np.array([10.0]),
        'n_ref_rec': float(np.mean([r['rec'] for r in train if r['rec'] > 0])),
    }


def run(eval_seasons=EVAL_SEASONS, n_draws=N_DRAWS, seed=SEED, progress=True):
    qb = attach_history(PAN.load_qb())
    rc = attach_history(PAN.load_recv())
    rows, comp_rows, fit_log = [], [], []

    for Y in eval_seasons:
        tr_qb = [r for r in qb if r['season'] < Y]
        te_qb = [r for r in qb if r['season'] == Y]
        tr_rc = [r for r in rc if r['season'] < Y]
        te_rc = [r for r in rc if r['season'] == Y]
        if not tr_qb or not te_qb:
            continue
        po = _pools(tr_qb)
        pr = _recv_pools(tr_rc)
        k_cmp, k_ev = estimate_k(tr_qb, 'cmp', 'att')
        k_ypc, k_ypc_ev = estimate_k(tr_qb, 'pyds', 'cmp')
        k_by_arm = {'BASELINE': (INHERITED_K, INHERITED_K),
                    'Q7_WIDTH': (INHERITED_K, INHERITED_K),
                    'Q7_SHRINK': (k_cmp, k_ypc),
                    'Q7_BOTH': (k_cmp, k_ypc)}

        for r in te_qb:
            att, cmp_r, pyds, ptd_r = r['att'], r['cmp'], r['pyds'], r['ptd']
            if att <= 0:
                continue
            depth = _bucket(r['h_games'], DEPTH_BUCKETS)
            regime = _bucket(att, QB_REGIMES)
            for arm in ARMS:
                kc, ky = k_by_arm[arm]
                rng = np.random.default_rng(
                    [seed, r['ord'], _stream(r['gsis_id']), _stream(arm)])
                pc, w_c = _rate_own(r, 'cmp', 'att', po['p_cmp'], kc)
                CMP = rng.binomial(att, min(max(pc, 0.0), 1.0), size=n_draws)
                own_ypc = own_list(r, 'pyds', 'cmp')
                w_y = r['h_games'] / (r['h_games'] + ky) if r['h_games'] else 0.0
                base_draw = _mix_draw(rng, own_ypc, po['ypc'], w_y, n_draws)
                # yards GIVEN the realised completions: the purest efficiency
                if arm in ('Q7_WIDTH', 'Q7_BOTH'):
                    d_given = _width_scaled(base_draw, own_ypc, po['ypc'], w_y,
                                            max(cmp_r, 1), po['n_ref_cmp'])
                else:
                    d_given = base_draw
                PY_given = np.maximum(d_given, 0.0) * cmp_r
                # yards given ATTEMPTS: the completion draw enters too, and the
                # width scale uses each draw's OWN completion count
                if arm in ('Q7_WIDTH', 'Q7_BOTH'):
                    mu = (w_y * float(np.mean(own_ypc)) +
                          (1 - w_y) * float(np.mean(po['ypc']))
                          if len(own_ypc) else float(np.mean(po['ypc'])))
                    sc = np.sqrt(po['n_ref_cmp'] /
                                 np.maximum(CMP.astype(float), 1.0))
                    d_att = mu + (base_draw - mu) * sc
                else:
                    d_att = base_draw
                PY_att = np.maximum(d_att, 0.0) * CMP
                ptd_rate, _ = _rate_own(r, 'ptd', 'cmp', po['p_ptd'], kc)
                PTD = rng.binomial(max(cmp_r, 0),
                                   min(max(ptd_rate, 0.0), 1.0), size=n_draws)

                for est, draws, y, extra in (
                        ('cmp|att', CMP, cmp_r,
                         {'log_score': _binom_logscore(cmp_r, att, pc)}),
                        ('ptd|cmp', PTD, ptd_r,
                         {'log_score': _binom_logscore(ptd_r, cmp_r, ptd_rate)}
                         if cmp_r > 0 else {'log_score': ''}),
                        ('pyds|cmp', PY_given, pyds, {}),
                        ('pyds|att', PY_att, pyds, {})):
                    if est == 'ptd|cmp' and cmp_r <= 0:
                        continue
                    rec = {'season': Y, 'week': r['week'],
                           'game_id': r['game_id'], 'gsis_id': r['gsis_id'],
                           'unit': 'QB', 'arm': arm, 'estimand': est,
                           'opportunity_regime': regime,
                           'sample_depth': depth,
                           'h_games': r['h_games'],
                           'att': att, 'cmp': cmp_r, 'actual': float(y),
                           'shrinkage_k_rate': round(kc, 5),
                           'shrinkage_k_yards': round(ky, 5),
                           'own_weight_rate': round(w_c, 5),
                           'own_weight_yards': round(w_y, 5)}
                    rec.update(_score(draws, y))
                    rec.update({f'cov{L}': v
                                for L, v in _cov(draws, y).items()})
                    rec.update(extra)
                    rows.append(rec)

            # the COMPOSED decomposition: one fixed opportunity model, shared
            comp_rows.append(_decompose(r, po, rng_seed=[seed, r['ord'], 7]))

        for r in te_rc:
            tg, rcv, ry = r['targets'], r['rec'], r['rec_yds']
            if tg <= 0:
                continue
            regime = _bucket(tg, RECV_REGIMES)
            depth = _bucket(r['h_games'], DEPTH_BUCKETS)
            rng = np.random.default_rng(
                [seed, r['ord'], _stream(r['gsis_id']), 11])
            prec, w_r = _rate_own(r, 'rec', 'targets', pr['p_rec'],
                                  INHERITED_K)
            REC = rng.binomial(tg, min(max(prec, 0.0), 1.0), size=n_draws)
            own_flat = np.array(
                [y for x in r['h_rows'] for y in x['rec_yards_list']], float)
            # PER CATCH, never a game mean: RC1 measured skew 2.197 and excess
            # kurtosis 7.830 on this quantity, with the Gaussian tail 13x too
            # thin. Each reception draws its own yardage.
            def _yards(counts):
                out = np.zeros(len(counts))
                src = own_flat if (len(own_flat) and w_r > 0) else pr['ypr_flat']
                for i, c in enumerate(counts):
                    if c <= 0:
                        continue
                    use_own = (len(own_flat) > 0 and rng.random() < w_r)
                    pool = own_flat if use_own else pr['ypr_flat']
                    out[i] = float(pool[rng.integers(0, len(pool), int(c))].sum())
                return out
            RY_given = _yards(np.full(n_draws, rcv, int))
            RY_tgt = _yards(REC)
            for est, draws, y, extra in (
                    ('rec|targets', REC, rcv,
                     {'log_score': _binom_logscore(rcv, tg, prec)}),
                    ('rec_yds|rec', RY_given, ry, {}),
                    ('rec_yds|targets', RY_tgt, ry, {})):
                rec = {'season': Y, 'week': r['week'],
                       'game_id': r['game_id'], 'gsis_id': r['gsis_id'],
                       'unit': 'RECV', 'arm': 'BASELINE', 'estimand': est,
                       'opportunity_regime': regime, 'sample_depth': depth,
                       'h_games': r['h_games'], 'att': tg, 'cmp': rcv,
                       'actual': float(y),
                       'shrinkage_k_rate': round(INHERITED_K, 5),
                       'shrinkage_k_yards': '',
                       'own_weight_rate': round(w_r, 5),
                       'own_weight_yards': ''}
                rec.update(_score(draws, y))
                rec.update({f'cov{L}': v for L, v in _cov(draws, y).items()})
                rec.update(extra)
                rows.append(rec)

        fit_log.append({'eval_season': Y, 'n_train_qb': len(tr_qb),
                        'n_test_qb': len(te_qb), 'n_train_recv': len(tr_rc),
                        'n_test_recv': len(te_rc),
                        'inherited_k': INHERITED_K,
                        'estimated_k_completion_rate': k_ev,
                        'estimated_k_yards_per_completion': k_ypc_ev,
                        'pool_completion_rate': round(po['p_cmp'], 5),
                        'mean_completions_reference': round(po['n_ref_cmp'], 4)})
        if progress:
            print(f'  {Y}: qb {len(te_qb)} recv {len(te_rc)} '
                  f'k_cmp {k_cmp:.3f} k_ypc {k_ypc:.3f}', flush=True)
    return {'rows': rows, 'composed': comp_rows, 'fit_log': fit_log}


def _rate_own(r, num, den, pool, k):
    own, n = own_rate(r, num, den)
    w = r['h_games'] / (r['h_games'] + k) if r['h_games'] else 0.0
    return ((w * own + (1 - w) * pool) if own is not None else pool), w


def _stream(text):
    """Deterministic in every process. Python randomises str hashing."""
    import zlib
    return int(zlib.crc32(str(text).encode()) & 0x7FFFFFFF)


def _decompose(r, po, rng_seed):
    """The COMPOSED condition: opportunity predicted, not oracled.

    One fixed opportunity model, identical for every arm, so the four fields
    below are real rather than zero by construction. The isolated condition
    records `OPPORTUNITY_ORACLED` instead of a flag computed from a zero.
    """
    own_att = own_list(r, 'att', 'db')
    past = r['h_rows']
    e_att = (float(np.mean([x['att'] for x in past[-8:]])) if past
             else po['att_mean'])
    own_ypa, _ = own_rate(r, 'pyds', 'att')
    pool_ypa = float(np.mean(po['ypc'])) * po['p_cmp']
    w = r['h_games'] / (r['h_games'] + INHERITED_K) if r['h_games'] else 0.0
    e_ypa = (w * own_ypa + (1 - w) * pool_ypa) if own_ypa is not None else pool_ypa
    a_ypa = (r['pyds'] / r['att']) if r['att'] else 0.0
    opp_err = e_att - r['att']
    eff_err = e_ypa - a_ypa
    comb_err = e_att * e_ypa - r['pyds']
    return {
        'season': r['season'], 'week': r['week'], 'game_id': r['game_id'],
        'gsis_id': r['gsis_id'], 'unit': 'QB',
        'condition': 'COMPOSED',
        'opportunity_error': round(opp_err, 5),
        'efficiency_error': round(eff_err, 6),
        'combined_error': round(comb_err, 5),
        'same_sign_or_offsetting': (
            'OFFSETTING' if opp_err * eff_err < 0 else
            'SAME_SIGN' if opp_err * eff_err > 0 else 'ZERO_COMPONENT'),
        'predicted_attempts': round(e_att, 4),
        'actual_attempts': r['att'],
        'predicted_ypa': round(e_ypa, 5),
        'actual_ypa': round(a_ypa, 5),
        'predicted_yards': round(e_att * e_ypa, 4),
        'actual_yards': r['pyds'],
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--seasons', default=','.join(str(s) for s in EVAL_SEASONS))
    ap.add_argument('--draws', type=int, default=N_DRAWS)
    a = ap.parse_args(argv)
    res = run(tuple(int(x) for x in a.seasons.split(',')), a.draws)
    print(f"scored rows   : {len(res['rows'])}")
    print(f"composed rows : {len(res['composed'])}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
