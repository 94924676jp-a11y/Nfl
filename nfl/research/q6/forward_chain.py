"""Q6 step 2: forward-chained appearance, conditional role, and composition.

    python3.12 -m nfl.research.q6.forward_chain

THREE LAYERS, MEASURED SEPARATELY AND THEN COMPOSED.

  1. P(appears)          arms: ROLE_CLASS_FLAT, R8, Q6_FEATURES, Q6_CALIBRATED
  2. role | appears      arms: TIER_PRIOR, Q6_VACANCY
  3. the composition     Bernoulli(p) x share, renormalised over whoever
                         appeared IN THAT DRAW

They are reported apart because they are different properties and a single
player CRPS hides which one moved -- the same reason the team-volume work
carries a mean-only arm beside a full one.

WHAT IS HELD FIXED SO THE COMPARISON MEASURES THE LAYER.

  * The team total is the REALISED one, identical in every arm. It isolates
    appearance and role; no arm gains from it because every arm gets the same
    number; and it is not a claim that the total is known pregame.
  * The conditional-role arms are scored against the REALISED appearance set,
    because "role given appears" is conditional on appearing and mixing in the
    appearance model would stop it measuring role.
  * Random indices are shared across arms wherever the pools have the same
    shape, so a paired difference measures the treatment and not the draws.

THE RECALIBRATION IS FITTED ON A NESTED FORWARD CHAIN, never in sample. A
logistic is over-confident on its own training rows, so a recalibration fitted
there would learn that over-confidence and then be applied to rows that do not
have it. The inner model is fitted on seasons before Y-1 and calibrated on
Y-1.
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import sys
import zlib

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
for _q in (str(_REPO), str(_REPO / 'nfl' / 'research' / 'p2'),
           str(_REPO / 'nfl' / 'research' / 'p4b')):
    if _q not in sys.path:
        sys.path.insert(0, _q)

import p4b_volume as V                                            # noqa: E402
import stage_a as SA                                              # noqa: E402
from nfl.production.nonqb import appearance_r7 as R7              # noqa: E402
from nfl.production.nonqb import appearance_r8 as R8              # noqa: E402
from nfl.research.q6 import frame as FR                           # noqa: E402

SPEC_VERSION = 'q6-forward-chain-1'
HERE = _REPO / 'nfl' / 'research' / 'q6'

APPEARANCE_ARMS = ('ROLE_CLASS_FLAT', 'R8', 'Q6_FEATURES', 'Q6_CALIBRATED')
ROLE_ARMS = ('TIER_PRIOR', 'Q6_VACANCY')
COMPOSITION_ARMS = (
    ('BASELINE', 'R8', 'TIER_PRIOR'),
    ('Q6_APPEARANCE_ONLY', 'Q6_CALIBRATED', 'TIER_PRIOR'),
    ('Q6_ROLE_ONLY', 'R8', 'Q6_VACANCY'),
    ('Q6_BOTH', 'Q6_CALIBRATED', 'Q6_VACANCY'),
)
N_DRAWS = 200
SEED = 20260913
L2 = 1.0
CAL_BINS = 10


# --------------------------------------------------------------- appearance
def _fit_logistic(rows, featurise, k):
    X = [featurise(r, k) for r in rows]
    y = [float(r['appeared']) for r in rows]
    return SA.fit_logistic(X, y, l2=L2)


def _predict(model, rows, featurise, k):
    return np.asarray(SA.predict(model, [featurise(r, k) for r in rows]),
                      float)


def _logit(p):
    p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def fit_role_class_calibration(p, y, classes):
    """One Platt scaling per role class. Estimated, never assumed to be 1."""
    out = {}
    for c in sorted(set(classes)):
        sel = np.asarray([x == c for x in classes], bool)
        if sel.sum() < 200:
            out[c] = None                # too thin to calibrate; left alone
            continue
        z = _logit(p[sel]).reshape(-1, 1)
        X = np.column_stack([np.ones(len(z)), z])
        out[c] = SA.fit_logistic(X, y[sel], l2=1.0)
    return out


def apply_calibration(cal, p, classes):
    out = np.array(p, float, copy=True)
    for c in sorted(set(classes)):
        m = cal.get(c)
        if m is None:
            continue
        sel = np.asarray([x == c for x in classes], bool)
        z = _logit(p[sel]).reshape(-1, 1)
        out[sel] = SA.predict(m, np.column_stack([np.ones(len(z)), z]))
    return out


def calibration_bins(p, y, bins=CAL_BINS):
    p = np.asarray(p, float)
    y = np.asarray(y, float)
    edges = np.linspace(0.0, 1.0, bins + 1)
    out, ece = [], 0.0
    for i in range(bins):
        lo, hi = edges[i], edges[i + 1]
        sel = (p >= lo) & (p < hi if i < bins - 1 else p <= hi)
        n = int(sel.sum())
        if not n:
            out.append({'bin': f'{lo:.1f}-{hi:.1f}', 'n': 0,
                        'mean_predicted': None, 'observed_rate': None})
            continue
        mp, ob = float(p[sel].mean()), float(y[sel].mean())
        out.append({'bin': f'{lo:.1f}-{hi:.1f}', 'n': n,
                    'mean_predicted': round(mp, 5),
                    'observed_rate': round(ob, 5),
                    'gap': round(mp - ob, 5)})
        ece += n / len(p) * abs(mp - ob)
    return out, round(float(ece), 6)


# ----------------------------------------------------- conditional role
def _share_k(train, metric):
    """Shrinkage constant for the role share. ESTIMATED, as R6 estimates it."""
    key = f'share_{metric}'
    by = collections.defaultdict(list)
    for r in train:
        if r['appeared'] and r.get(key) is not None:
            by[r['pid']].append(r[key])
    within, between = [], []
    for v in by.values():
        if len(v) >= 4:
            within.append(float(np.var(v, ddof=1)))
            between.append(float(np.mean(v)))
    if len(within) < 30:
        return 1.0, {'basis': 'TOO_FEW_PLAYER_SEASONS_DEFAULT_ONE',
                     'n_players': len(within)}
    w = float(np.mean(within))
    b = float(np.var(between, ddof=1))
    k = w / b if b > 0 else 1.0
    return float(k), {'basis': 'WITHIN_OVER_BETWEEN_PLAYER_VARIANCE',
                      'within': round(w, 8), 'between': round(b, 8),
                      'k': round(float(k), 5), 'n_players': len(within)}


def class_means(train, metric):
    key = f'share_{metric}'
    out = collections.defaultdict(list)
    for r in train:
        if r['appeared'] and r.get(key) is not None:
            out[(r['pos'], r['role_class'])].append(r[key])
            out[('__ALL__', r['pos'])].append(r[key])
    return {k: float(np.mean(v)) for k, v in out.items() if v}


def role_base(rows, metric, k_share, class_mean):
    """Each row's shrunk conditional share prior, from strictly earlier games.

    A player's own appeared-game history governs him where he has one; where he
    has little, he is shrunk toward his point-in-time role-class mean by
    n/(n+k) with k estimated. Nothing here is a chosen constant, and nothing
    reads the game being scored.
    """
    key = f'share_{metric}'
    fld = f'base_{metric}'
    hist = collections.defaultdict(list)
    for r in sorted(rows, key=lambda x: (x['s'], x['w'])):
        h = hist[r['pid']]
        n = len(h)
        own = float(np.mean(h[-FR.TRAIL:])) if h else None
        cm = class_mean.get((r['pos'], r['role_class']))
        if cm is None:
            cm = class_mean.get(('__ALL__', r['pos'])) or 0.0
        w = n / (n + k_share) if n else 0.0
        r[fld] = (w * own + (1 - w) * cm) if own is not None else cm
        r[fld + '_weight'] = w
        if r['appeared'] and r.get(key) is not None:
            hist[r['pid']].append(r[key])
    return rows


def fit_vacancy(train, metric):
    """How an absent starter's share ACTUALLY redistributes, per role class.

    Proportional renormalisation is the null: every survivor's share rises by
    the same factor. This measures whether it does, as the ratio of realised
    share to proportionally-renormalised share on team-weeks where a `starter`
    did not appear.

    SHRINKAGE IS A MEASUREMENT. The weight is what is left of the observed
    deviation from 1.0 once its own sampling noise is removed:
    w = 1 - var(mean) / (raw - 1)^2, floored at zero. A deviation no larger
    than its own standard error shrinks all the way back to the null, which is
    the correct behaviour and not a failure to find an effect.
    """
    key = f'share_{metric}'
    fld = f'base_{metric}'
    # RATIO OF SUMS, NOT A MEAN OF RATIOS.
    #
    # The first version averaged actual/predicted per player. Where the
    # predicted share is near zero that ratio explodes, and the carry pool --
    # which is full of receivers predicted almost no carries -- produced class
    # ratios of 4 to 8. Those were an estimator artefact, not a football fact.
    # Summing numerator and denominator first weights each observation by the
    # mass it actually carries, which is the same fix the play-by-play rate
    # response uses.
    num = collections.defaultdict(float)
    den = collections.defaultdict(float)
    inf = collections.defaultdict(list)
    for g in _groups(train).values():
        starters = [r for r in g if r['role_class'] == 'starter']
        if not starters or all(r['appeared'] for r in starters):
            continue
        present = [r for r in g if r['appeared'] and r.get(key) is not None]
        tot = sum(max(float(r[fld]), 0.0) for r in present)
        if tot <= 0:
            continue
        for r in present:
            pred = max(float(r[fld]), 0.0) / tot
            num[r['role_class']] += float(r[key])
            den[r['role_class']] += pred
            inf[r['role_class']].append((float(r[key]), pred))
    out, ev = {}, {}
    for c in sorted(den):
        n = len(inf[c])
        if n < 30 or den[c] <= 0:
            out[c] = 1.0
            ev[c] = {'n': n, 'raw': None, 'shrunk': 1.0,
                     'note': 'too few vacancy groups; the null is kept'}
            continue
        raw = num[c] / den[c]
        # Cluster-linearised variance of the ratio estimator, one cluster per
        # observation, so the shrinkage weight below is a measurement.
        d = den[c]
        u = np.array([(a - raw * q) / d for a, q in inf[c]], float)
        var = float((u ** 2).sum())
        dev2 = (raw - 1.0) ** 2
        w = 0.0 if dev2 <= 0 else min(1.0, max(0.0, 1.0 - var / dev2))
        out[c] = 1.0 + w * (raw - 1.0)
        ev[c] = {'n': n, 'raw': round(float(raw), 5),
                 'shrunk': round(float(out[c]), 5),
                 'shrinkage_weight': round(float(w), 5),
                 'se': round(float(np.sqrt(var)), 6)}
    for c in FR.ROLE_CLASSES:
        out.setdefault(c, 1.0)
        ev.setdefault(c, {'n': 0, 'raw': None, 'shrunk': 1.0,
                          'note': 'no vacancy group at all; the null is kept'})
    return out, ev


def role_predictions(group, metric, arm, vac, appearing):
    """Normalised conditional shares for one team-week opportunity pool.

    Keyed by player id, not by object identity. The pool is every RB, WR and
    TE on the team that week, so the predicted shares sum to exactly one over
    the same population the realised shares do.
    """
    fld = f'base_{metric}'
    present = [r for r in group if appearing.get(r['pid'], r['appeared'])]
    if not present:
        return {}
    starter_out = any(r['role_class'] == 'starter'
                      and not appearing.get(r['pid'], r['appeared'])
                      for r in group)
    base = {}
    for r in present:
        b = max(float(r[fld]), 0.0)
        if arm == 'Q6_VACANCY' and starter_out:
            b *= float(vac.get(r['role_class'], 1.0))
        base[r['pid']] = b
    tot = sum(base.values())
    if tot <= 0:
        return {r['pid']: 0.0 for r in present}
    return {kk: vv / tot for kk, vv in base.items()}


def _stream(text):
    """A deterministic per-name substream integer, identical in every process."""
    return int(zlib.crc32(str(text).encode()) & 0x7FFFFFFF)


def _groups(rows):
    """One opportunity pool per team-week: every RB, WR and TE together."""
    g = collections.defaultdict(list)
    for r in rows:
        g[(r['s'], r['w'], r['t'])].append(r)
    return g


# ------------------------------------------------------------ the chain
def run(eval_seasons=FR.EVAL_SEASONS, n_draws=N_DRAWS, seed=SEED,
        progress=True):
    rows, frame_ev = FR.load_frame()
    rows = FR.attach_role_class(rows)
    rows, opp_ev = FR.attach_opportunity(rows)

    app_rows, role_rows, comp_rows = [], [], []
    missing_rows, fit_log = [], []

    for Y in eval_seasons:
        train = [r for r in rows if r['s'] < Y and not R8.is_unsupported(r)]
        test = [r for r in rows if r['s'] == Y]
        kept = [r for r in test if not R8.is_unsupported(r)]
        declined = len(test) - len(kept)
        if not train or not kept:
            continue
        ko = R8.reliability_k(rows, cut=Y * 100)
        k = float(ko.value)

        m_r8 = _fit_logistic(train, FR.featurise_r8, k)
        m_q6 = _fit_logistic(train, FR.featurise_q6, k)
        flat, overall = FR.flat_rate(train)

        # NESTED forward chain for the recalibration: fit on seasons before
        # Y-1, calibrate on Y-1, apply to Y. Never in sample.
        inner_train = [r for r in train if r['s'] < Y - 1]
        inner_cal = [r for r in train if r['s'] == Y - 1]
        if len(inner_train) >= 2000 and len(inner_cal) >= 500:
            m_inner = _fit_logistic(inner_train, FR.featurise_q6, k)
            p_inner = _predict(m_inner, inner_cal, FR.featurise_q6, k)
            cal = fit_role_class_calibration(
                p_inner, np.array([float(r['appeared']) for r in inner_cal]),
                [r['role_class'] for r in inner_cal])
            cal_basis = 'NESTED_FORWARD_CHAIN'
        else:
            cal = {}
            cal_basis = 'NOT_FITTED_TOO_LITTLE_HISTORY'

        p = {
            'R8': _predict(m_r8, kept, FR.featurise_r8, k),
            'Q6_FEATURES': _predict(m_q6, kept, FR.featurise_q6, k),
            'ROLE_CLASS_FLAT': np.array(
                [flat.get((r['pos'], r['role_class']), overall) for r in kept],
                float),
        }
        p['Q6_CALIBRATED'] = (
            apply_calibration(cal, p['Q6_FEATURES'],
                              [r['role_class'] for r in kept])
            if cal else np.array(p['Q6_FEATURES'], copy=True))

        for i, r in enumerate(kept):
            rec = {'season': r['s'], 'week': r['w'], 'team': r['t'],
                   'pid': r['pid'], 'pos': r['pos'],
                   'role_class': r['role_class'],
                   'role_rank_basis': r['role_rank_basis'],
                   'state': r['state'], 'appeared': int(r['appeared']),
                   'team_game': f"{r['s']}-{r['w']}-{r['t']}"}
            for arm in APPEARANCE_ARMS:
                rec[f'p_{arm}'] = float(p[arm][i])
            app_rows.append(rec)

        # ---- the missing-data study, on the same test rows -----------------
        blanked = [FR.blank_injury_block(r) for r in kept]
        p_blank = _predict(m_q6, blanked, FR.featurise_q6, k)
        p_blank = (apply_calibration(cal, p_blank,
                                     [r['role_class'] for r in kept])
                   if cal else p_blank)
        had_report = [bool(r.get('inj_available')) for r in kept]
        for i, r in enumerate(kept):
            missing_rows.append({
                'season': r['s'], 'pos': r['pos'],
                'role_class': r['role_class'],
                'appeared': int(r['appeared']),
                'had_injury_report': int(had_report[i]),
                'team_game': f"{r['s']}-{r['w']}-{r['t']}",
                'p_PROBABILISTIC_FALLBACK': float(p_blank[i]),
                'p_HISTORICAL_ROLE_FALLBACK': float(
                    flat.get((r['pos'], r['role_class']), overall)),
                'p_INFORMED': float(p['Q6_CALIBRATED'][i]),
            })

        # ---- conditional role and composition, one pool per metric -------
        vac_ev_all, k_ev_all = {}, {}
        for metric in FR.METRICS:
            key = f'share_{metric}'
            cm = class_means(train, metric)
            k_share, k_ev = _share_k(train, metric)
            k_ev_all[metric] = k_ev
            role_base(rows, metric, k_share, cm)
            vac, vac_ev = fit_vacancy([r for r in rows if r['s'] < Y], metric)
            vac_ev_all[metric] = vac_ev

            rng = np.random.default_rng([seed, Y, _stream(metric)])
            resid = collections.defaultdict(list)
            for g in _groups([r for r in rows if r['s'] < Y]).values():
                pred = role_predictions(g, metric, 'TIER_PRIOR', vac, {})
                for r in g:
                    if r['appeared'] and r.get(key) is not None:
                        q = pred.get(r['pid'])
                        if q is not None:
                            resid[(r['pos'], r['role_class'])].append(
                                r[key] - q)
            pools = {kk: np.asarray(vv, float) for kk, vv in resid.items()
                     if len(vv) >= 100}

            te_groups = _groups(kept)
            for gkey, g in sorted(te_groups.items()):
                for arm in ROLE_ARMS:
                    pred = role_predictions(g, metric, arm, vac, {})
                    for r in g:
                        if not (r['appeared'] and r.get(key) is not None):
                            continue
                        q = pred.get(r['pid'])
                        pool = pools.get((r['pos'], r['role_class']))
                        if q is None or pool is None or not len(pool):
                            continue
                        d = np.clip(
                            q + pool[rng.integers(0, len(pool), size=n_draws)],
                            0.0, 1.0)
                        role_rows.append({
                            'season': r['s'], 'week': r['w'], 'team': r['t'],
                            'pid': r['pid'], 'pos': r['pos'],
                            'role_class': r['role_class'], 'arm': arm,
                            'metric': metric,
                            'team_game': f"{r['s']}-{r['w']}-{r['t']}",
                            'actual_share': float(r[key]),
                            'pred_share': float(q),
                            'crps': float(V.crps_samples(
                                d.reshape(1, -1), np.array([r[key]]))[0]),
                            'error': float(q - r[key]),
                        })

            # ---- composition: Bernoulli(p) x share, renormalised per draw --
            pmap = {(r['pid'], r['s'], r['w'], r['t']): i
                    for i, r in enumerate(kept)}
            for gkey, g in sorted(te_groups.items()):
                den = float(g[0][f'den_{metric}'])
                if den <= 0:
                    continue
                idx = [pmap.get((r['pid'], r['s'], r['w'], r['t']))
                       for r in g]
                if any(i is None for i in idx):
                    continue
                base = np.array([max(float(r[f'base_{metric}']), 0.0)
                                 for r in g])
                cls = [r['role_class'] for r in g]
                starter_i = [j for j, r in enumerate(g)
                             if r['role_class'] == 'starter']
                for label, app_arm, role_arm in COMPOSITION_ARMS:
                    # crc32, NOT hash(). Python randomises str hashing per
                    # process, so hash() here would draw a different stream on
                    # every run at an identical declared seed -- the exact
                    # defect nfl/production/seeds.py exists to end.
                    rs = np.random.default_rng([
                        seed, Y, _stream(label), _stream(metric), gkey[1],
                        _stream(gkey[2])])
                    pv = np.array([p[app_arm][i] for i in idx], float)
                    A = rs.binomial(1, np.clip(pv, 0.0, 1.0),
                                    size=(n_draws, len(g)))
                    W = np.tile(base, (n_draws, 1)) * A
                    if role_arm == 'Q6_VACANCY' and starter_i:
                        out_any = (A[:, starter_i] == 0).any(axis=1)
                        boost = np.array([float(vac.get(c, 1.0)) for c in cls])
                        W = np.where(out_any.reshape(-1, 1), W * boost, W)
                    tot = W.sum(axis=1, keepdims=True)
                    S = np.divide(W, tot, out=np.zeros_like(W), where=tot > 0)
                    # A COUNT, NOT A CONTINUOUS SHARE.
                    #
                    # The first version emitted share x total, which is
                    # strictly positive for every player who appeared, so the
                    # only route to a zero was non-appearance and the harness
                    # reported a zero-inflation deficit that was its own
                    # construction. A multinomial draw over the simplex gives
                    # integer opportunity, produces zeros for small shares the
                    # way the production allocator does, and still reconciles
                    # to the team total exactly on every draw.
                    ok = (S.sum(axis=1) > 0)
                    OPP = np.zeros_like(S)
                    if ok.any():
                        Ps = S[ok]
                        Ps = Ps / Ps.sum(axis=1, keepdims=True)
                        OPP[ok] = rs.multinomial(int(round(den)), Ps)
                    recon = float(np.abs(OPP.sum(axis=1) - den).mean())
                    for j, r in enumerate(g):
                        y = float(r[metric])
                        d = OPP[:, j]
                        comp_rows.append({
                            'season': r['s'], 'week': r['w'], 'team': r['t'],
                            'pid': r['pid'], 'pos': r['pos'],
                            'role_class': r['role_class'], 'arm': label,
                            'metric': metric,
                            'team_game': f"{r['s']}-{r['w']}-{r['t']}",
                            'actual': y, 'pred_mean': float(d.mean()),
                            'crps': float(V.crps_samples(
                                d.reshape(1, -1), np.array([y]))[0]),
                            'p_zero_pred': float((d <= 1e-12).mean()),
                            'is_zero_actual': int(y == 0),
                            'team_total': den,
                            'recon_error': recon,
                            'starter_absent': int(any(
                                not r2['appeared'] for r2 in g
                                if r2['role_class'] == 'starter')),
                        })

        fit_log.append({
            'eval_season': Y, 'n_train': len(train), 'n_test': len(kept),
            'n_declined_unsupported_cell': declined,
            'reliability_k': round(k, 5),
            'role_share_k': k_ev_all, 'vacancy': vac_ev_all,
            'calibration_basis': cal_basis,
        })
        if progress:
            print(f'  {Y}: train {len(train)} test {len(kept)} '
                  f'declined {declined}', flush=True)

    return {'appearance': app_rows, 'role': role_rows,
            'composition': comp_rows, 'missing': missing_rows,
            'fit_log': fit_log, 'frame_evidence': frame_ev,
            'opportunity_evidence': opp_ev}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--seasons', default=','.join(str(s) for s in FR.EVAL_SEASONS))
    ap.add_argument('--draws', type=int, default=N_DRAWS)
    a = ap.parse_args(argv)
    res = run(tuple(int(x) for x in a.seasons.split(',')), a.draws)
    for k2 in ('appearance', 'role', 'composition', 'missing'):
        print(f'{k2:14s} rows {len(res[k2])}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
