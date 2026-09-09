"""RBDEP: RB1 <-> RB2 opportunity dependence. Shared library.

Everything here is read-only against the frozen P4B/P4C machinery. The single
behavioural switch is `p4c_build.gen_weights(..., add_pool_groups=...)`, which
is None everywhere by default; this module is what passes it.

THE ONE RULE THIS FILE EXISTS TO ENFORCE. Reality hands us ONE draw per
team-game, so every model statistic that is going to be set beside a realised
one is computed the same way: one draw index per team-game, correlate ACROSS
team-games, and report the distribution over draw indices. The within-team-game
across-draw correlation and the correlation of predictive means are both
computed too, and both are labelled, because they are what a reader reaches for
by accident and neither is comparable to a realised series.
"""
from __future__ import annotations

import collections
import math
import os
import pickle
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RESEARCH = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(RESEARCH))
for _q in (ROOT,
           os.path.join(RESEARCH, 'p1'), os.path.join(RESEARCH, 'p2'),
           os.path.join(RESEARCH, 'p3'), os.path.join(RESEARCH, 'p4b'),
           os.path.join(RESEARCH, 'p4c')):
    if _q not in sys.path:
        sys.path.insert(0, _q)

import p4c_build as CB                                            # noqa: E402
import p4c_lib as CL                                              # noqa: E402
from sportsplatform.governance.outcome import Cause, Outcome      # noqa: E402

CLS = 'carries'
SYSTEM = 'C'
EVAL = (2022, 2023, 2024, 2025)
BURN_IN = (2020, 2021)
MAX_SEASON_ALLOWED = 2025          # 2026 outcomes do not exist and are never read
LAMBDA_GRID = (1.00, 0.75, 0.50, 0.25, 0.00)
MIN_WEEK_FOR_RANK = 5

# Seeds. Identical in both arms -- the arms differ in ONE argument and nothing
# else. Taken from run_p4cc.py so the incumbent arm reproduces that harness.
SEED_MASS = CL.SEED + 5002
SEED_W = CL.SEED + 3034
SEED_APP = CL.SEED + 1009

M_DRAWS = CL.M_DRAWS                # 1000, the frozen P4C draw count

CLOSURE_TOL = 1e-5
BUDGET_REL_TOL = 1e-3


# ---------------------------------------------------------------------------
# inputs
# ---------------------------------------------------------------------------
def _artifact(name):
    """The derived artifacts are gitignored and regenerable. Production's
    verified cache is preferred; the research tree is the fallback."""
    for d in (os.path.join(ROOT, 'nfl', 'derived'),
              os.path.join(RESEARCH, 'p4b')):
        p = os.path.join(d, name)
        if os.path.exists(p):
            return p
    return None


def load_inputs():
    """rows, volume store. BLOCKED[DEPENDENCY] if the derived cache is absent,
    which is a build step and not a defect in this experiment."""
    pp, vp = _artifact('panel_enriched.pkl'), _artifact('volume_store.npy')
    if pp is None or vp is None:
        return Outcome.blocked(
            'RBDEP_DERIVED_ARTIFACTS_ABSENT',
            'panel_enriched.pkl / volume_store.npy are gitignored and '
            'regenerable; run nfl/research/repro/regenerate.py --emit or '
            'nfl/production/derived.py to populate nfl/derived/.',
            cause=Cause.DEPENDENCY,
            looked_in=[os.path.join(ROOT, 'nfl', 'derived'),
                       os.path.join(RESEARCH, 'p4b')])
    rows = pickle.load(open(pp, 'rb'))
    if not rows:
        return Outcome.blocked('RBDEP_PANEL_EMPTY',
                               f'{pp} unpickled to zero rows',
                               cause=Cause.DATA)
    arr = np.load(vp, allow_pickle=True)
    vol = {}
    for e in arr:
        d = dict(e)
        k = tuple(d.pop('k'))
        d['index'] = {kk: i for i, kk in enumerate(d['keys'])}
        vol[k] = d
    if not vol:
        return Outcome.blocked('RBDEP_VOLUME_STORE_EMPTY',
                               f'{vp} carried no entries', cause=Cause.DATA)
    return Outcome.ok('RBDEP_INPUTS_OK', value=(rows, vol),
                      panel=pp, volume=vp, n_rows=len(rows),
                      n_volume_keys=len(vol))


def assert_no_future_season(rows):
    """GUARD. Refuses if the panel carries a season above the declared ceiling.

    Load-bearing: this is the only thing standing between this experiment and a
    2026 outcome. It is a REFUSAL, not a filter -- silently dropping 2026 rows
    would let a leaking panel through and report success.
    """
    seasons = sorted({int(r['season']) for r in rows})
    bad = [s for s in seasons if s > MAX_SEASON_ALLOWED]
    if bad:
        return Outcome.fail(
            'RBDEP_FUTURE_SEASON_IN_PANEL',
            f'seasons {bad} exceed the declared ceiling '
            f'{MAX_SEASON_ALLOWED}. This experiment must never read a 2026 '
            f'outcome; refusing rather than filtering.',
            seasons=seasons)
    scored = [s for s in EVAL if s in seasons]
    return Outcome.ok('RBDEP_SEASONS_OK', value=seasons, seasons=seasons,
                      scored=scored, burn_in_never_scored=list(BURN_IN))


# ---------------------------------------------------------------------------
# outcome-free ranking
# ---------------------------------------------------------------------------
def prior_week_carries(rows):
    """(season, team, gsis_id, week) -> (carries, appearances) in weeks < week
    of THAT season. Strictly prior: a week's own rows are folded in only once
    the week has been left behind."""
    byteam = collections.defaultdict(list)
    for r in rows:
        if r['position'] == 'RB':
            byteam[(r['season'], r['team'])].append(r)
    out = {}
    for (se, tm), rs in byteam.items():
        rs.sort(key=lambda x: x['week'])
        car = collections.defaultdict(float)
        app = collections.defaultdict(int)
        lastw, pend = None, []
        for r in rs:
            if lastw is not None and r['week'] != lastw:
                for q in pend:
                    car[q['gsis_id']] += (q['y_carries'] or 0)
                    app[q['gsis_id']] += 1
                pend = []
            lastw = r['week']
            out[(se, tm, r['gsis_id'], r['week'])] = (car[r['gsis_id']],
                                                      app[r['gsis_id']])
            pend.append(r)
    return out


def rank_two(te, s, e, pc):
    """Row indices of RB1 and RB2 in te[s:e], from strictly prior weeks only,
    or None. The SAME ranking is used for the model draws and for reality."""
    if te[s]['week'] < MIN_WEEK_FOR_RANK:
        return None
    cand = []
    for i in range(s, e):
        r = te[i]
        v = pc.get((r['season'], r['team'], r['gsis_id'], r['week']))
        if v is None or v[0] < 1:
            continue
        cand.append((-v[0], -v[1], r['gsis_id'], i))
    if len(cand) < 2:
        return None
    cand.sort()
    return cand[0][3], cand[1][3]


# ---------------------------------------------------------------------------
# the simulation, one evaluation season, one arm, one lambda
# ---------------------------------------------------------------------------
def groups_of(te):
    keys = [(r['team'], r['ord']) for r in te]
    starts, cur = [], None
    for i, k in enumerate(keys):
        if k != cur:
            starts.append(i)
            cur = k
    starts = np.array(starts, dtype=np.int64)
    return starts, np.diff(np.append(starts, len(keys)))


def eligible_rows(sub, ev, pa, store):
    te = [r for r in sub
          if r['season'] == ev and r.get('s_carries') is not None
          and id(r) in pa and (r.get('f_n_prior') or 0) >= 1
          and r['_C'] is not None and (r['team'], r['ord']) in store['index']]
    te.sort(key=lambda r: (r['ord'], r['team'], r['gsis_id']))
    return te


def shrink_C(C, starts, counts, lam):
    """Frame L: pull each back's share forecast toward his team-game's mean.
    lam = 1 leaves C untouched and IS Frame H."""
    if lam == 1.0:
        return C
    mu = CL.gsum(C[:, None], starts)[:, 0] / counts
    return (lam * C + (1.0 - lam) * CL.gexp(mu, counts)).astype(np.float32)


def simulate(te, par, pa, store, arm, lam, m):
    """One arm, one season, one lambda. Returns draws and the gate counts.

    `arm` is 'INC' (add_pool_groups=None, the standing default) or 'SHR' (one
    shared resample position per team-game). Nothing else differs.
    """
    if arm not in ('INC', 'SHR'):
        raise ValueError(f'RBDEP_UNKNOWN_ARM: {arm!r}')
    n = len(te)
    starts, counts = groups_of(te)
    G = len(starts)
    ti = np.array([store['index'][(r['team'], r['ord'])] for r in te],
                  dtype=np.int64)
    gti = ti[starts]
    C0 = np.array([r['_C'] for r in te], np.float32)
    C = shrink_C(C0, starts, counts, lam)
    groups = None
    if arm == 'SHR':
        groups = np.repeat(np.arange(G, dtype=np.int64), counts)
    W = CB.gen_weights(SYSTEM, C, [r['position'] for r in te], par, CLS, n, m,
                       np.random.default_rng(SEED_W), add_pool_groups=groups)
    # The floor rate is a REPORTED diagnostic (G5). It is recomputed from the
    # pre-clip weight rather than inferred from W == 0, because a residual can
    # legitimately land the weight at exactly zero.
    allpool = (np.concatenate([v for v in par['add_pool'].values()])
               if par['add_pool'] else np.zeros(1, np.float32))
    Wraw = C[:, None] + CB._resample(par['add_pool'],
                                     [r['position'] for r in te], n, m,
                                     np.random.default_rng(SEED_W), allpool,
                                     groups=groups)
    floored = int((Wraw < 0.0).sum()) + int((Wraw > 1.0).sum())
    mass = CB.mass_draws(SYSTEM, par, G, m, np.random.default_rng(SEED_MASS))
    avail = (1.0 - mass).astype(np.float32)
    # Appearance probability. `pa` is keyed by object identity, so a row that
    # has been COPIED out of the panel cannot be looked up in it; such a row
    # must carry `_p_app` instead. Neither present is a named refusal, never a
    # default, because a defaulted appearance probability would silently become
    # the model.
    if pa is not None:
        p_app = np.array([pa[id(r)] for r in te], np.float32)
    else:
        missing = [i for i, r in enumerate(te) if r.get('_p_app') is None]
        if missing:
            raise ValueError(
                f'RBDEP_APPEARANCE_PROBABILITY_MISSING: {len(missing)} row(s) '
                f'carry neither an identity in the appearance map nor a '
                f'_p_app field. Refused rather than defaulted.')
        p_app = np.array([r['_p_app'] for r in te], np.float32)
    A = (np.random.default_rng(SEED_APP).random((n, m), np.float32)
         < p_app[:, None])
    # The volume store holds a FIXED number of draw columns. Taking fewer is
    # a prefix of the same stream and is allowed; asking for more would silently
    # broadcast or wrap, so it is refused.
    ncol = int(store['B'].shape[1])
    if m > ncol:
        raise ValueError(
            f'RBDEP_M_EXCEEDS_VOLUME_STORE: asked for {m} draws, the frozen '
            f'team-volume store carries {ncol}. Refused rather than reused.')
    T = store['B'][gti][:, :m].astype(np.float32)
    WA = W * A
    tot = CL.gsum(WA, starts)
    tee = CL.gexp(tot, counts)
    S = np.divide(WA * CL.gexp(avail, counts), tee,
                  out=np.zeros_like(WA), where=tee > 1e-12)
    S, n_bind = CL.waterfill(S, starts, counts, 1.0)
    degenerate = (tot <= 1e-12)
    other = np.where(degenerate, 1.0, mass).astype(np.float64)
    draws = (CL.gexp(T, counts) * S).astype(np.float32)
    # ---- gates ---------------------------------------------------------
    ssum = CL.gsum(S.astype(np.float64), starts)
    closure = np.abs(ssum + other - 1.0)
    nsum = CL.gsum(draws.astype(np.float64), starts)
    budget = np.abs(nsum - T.astype(np.float64) * (1.0 - other))
    gates = {
        'n_rows': n, 'n_team_games': G, 'n_draws': m,
        'n_cells': int(n) * int(m), 'n_group_cells': int(G) * int(m),
        'G1_closure_violations': int((closure > CLOSURE_TOL).sum()),
        'G1_closure_max_abs_dev': float(closure.max()),
        'G2_budget_violations': int(
            (budget > BUDGET_REL_TOL * np.maximum(T, 1.0)).sum()),
        'G2_budget_max_abs_dev': float(budget.max()),
        'G3_negative_shares': int((S < 0).sum()),
        'G3_negative_counts': int((draws < 0).sum()),
        'G4_waterfill_bind': int(n_bind),
        'G5_weight_floor_cells': floored,
        'G5_weight_floor_rate': floored / float(n * m),
        'G6_degenerate_group_cells': int(degenerate.sum()),
        'G6_degenerate_group_rate': float(degenerate.mean()),
    }
    return {'draws': draws, 'S': S, 'T': T, 'other': other,
            'starts': starts, 'counts': counts, 'gates': gates,
            'C_used': C}


# ---------------------------------------------------------------------------
# statistics
# ---------------------------------------------------------------------------
def _colcorr(A, B):
    a = A - A.mean(0)
    b = B - B.mean(0)
    sa = np.sqrt((a * a).sum(0))
    sb = np.sqrt((b * b).sum(0))
    d = sa * sb
    return np.divide((a * b).sum(0), d, out=np.full(A.shape[1], np.nan),
                     where=d > 0)


def _band(v):
    v = v[np.isfinite(v)]
    if not len(v):
        return None
    return {'median': float(np.median(v)), 'mean': float(v.mean()),
            'p05': float(np.percentile(v, 5)),
            'p95': float(np.percentile(v, 95)),
            'p_gt_zero': float((v > 0).mean()), 'n_draws_used': int(len(v))}


def dependence(N1, N2, T, y1, y2, Tstar):
    """Every dependence number this experiment reports, each labelled by which
    estimand it is. Only `between_*` may be set beside `realised_*`."""
    N1 = np.asarray(N1, float)
    N2 = np.asarray(N2, float)
    T = np.asarray(T, float)
    S1 = np.divide(N1, T, out=np.zeros_like(N1), where=T > 0)
    S2 = np.divide(N2, T, out=np.zeros_like(N2), where=T > 0)
    within, within_s = [], []
    for i in range(N1.shape[0]):
        if N1[i].std() > 0 and N2[i].std() > 0:
            within.append(np.corrcoef(N1[i], N2[i])[0, 1])
        if S1[i].std() > 0 and S2[i].std() > 0:
            within_s.append(np.corrcoef(S1[i], S2[i])[0, 1])
    ok = np.asarray(Tstar, float) > 0
    ry1 = np.asarray(y1, float)[ok] / np.asarray(Tstar, float)[ok]
    ry2 = np.asarray(y2, float)[ok] / np.asarray(Tstar, float)[ok]
    tvfrac = [(S1[i].mean() ** 2 * T[i].var()) / N1[i].var()
              for i in range(N1.shape[0]) if N1[i].var() > 0]
    return {
        'n_team_games': int(N1.shape[0]),
        'LIKE_FOR_LIKE_between_team_game_counts': _band(_colcorr(N1, N2)),
        'LIKE_FOR_LIKE_between_team_game_shares': _band(_colcorr(S1, S2)),
        'realised_between_team_game_counts': float(
            np.corrcoef(y1, y2)[0, 1]),
        'realised_between_team_game_shares': float(
            np.corrcoef(ry1, ry2)[0, 1]) if ok.sum() > 2 else None,
        'NOT_COMPARABLE_within_team_game_across_draws_counts': (
            float(np.mean(within)) if within else None),
        'NOT_COMPARABLE_within_team_game_across_draws_shares': (
            float(np.mean(within_s)) if within_s else None),
        'FORBIDDEN_corr_of_predictive_means': float(
            np.corrcoef(N1.mean(1), N2.mean(1))[0, 1]),
        'team_volume_variance_fraction_of_RB1': (
            float(np.mean(tvfrac)) if tvfrac else None),
        'rb1_predicted_mean': float(N1.mean()),
        'rb2_predicted_mean': float(N2.mean()),
        # Ratio of POOLED means, plus the median of per-team-game ratios over
        # the team-games where RB2 has a workload at all. A plain mean of
        # per-team-game ratios divides by a near-zero RB2 mean and returns a
        # number in the tens of millions, which is an artifact of the divisor
        # and not a football quantity.
        'rb1_over_rb2_pooled_mean_ratio': float(
            N1.mean() / max(N2.mean(), 1e-9)),
        'rb1_over_rb2_median_ratio_where_rb2_ge_half_carry': (
            float(np.median(N1.mean(1)[N2.mean(1) >= 0.5]
                            / N2.mean(1)[N2.mean(1) >= 0.5]))
            if (N2.mean(1) >= 0.5).sum() else None),
        'n_team_games_with_rb2_below_half_carry': int(
            (N2.mean(1) < 0.5).sum()),
        'sd_across_team_games_of_rb1_predictive_mean': float(
            N1.mean(1).std(ddof=1)),
    }


def marginals(draws, y):
    """Frame H only. Per-player CRPS and the distribution summary."""
    y = np.asarray(y, float)
    crps = CL.crps_samples(draws, y)
    mean = draws.mean(axis=1)
    e = y - mean
    out = {'n': int(len(y)), 'crps': float(crps.mean()),
           'mae': float(np.abs(e).mean()),
           'rmse': float(math.sqrt(float((e * e).mean()))),
           'bias': float(e.mean()),
           'r_pred_vs_actual': (float(np.corrcoef(y, mean)[0, 1])
                                if mean.std() > 0 else None),
           'dist': {'mean': float(draws.mean()),
                    'sd': float(draws.std()),
                    'p05': float(np.percentile(draws, 5)),
                    'p50': float(np.percentile(draws, 50)),
                    'p95': float(np.percentile(draws, 95)),
                    'zero_mass': float((draws < 0.5).mean())},
           'actual_dist': {'mean': float(y.mean()), 'sd': float(y.std(ddof=1)),
                           'p05': float(np.percentile(y, 5)),
                           'p50': float(np.percentile(y, 50)),
                           'p95': float(np.percentile(y, 95)),
                           'zero_mass': float((y < 0.5).mean())},
           'coverage': {}}
    for lv in CL.LEVELS:
        lo = np.percentile(draws, 100 * (1 - lv) / 2, axis=1)
        hi = np.percentile(draws, 100 * (1 + lv) / 2, axis=1)
        out['coverage'][str(int(lv * 100))] = float(
            ((y >= lo) & (y <= hi)).mean())
    return out, crps


def gates_verdict(g):
    """G1-G4 are refusals. G5 is reported. G6 is compared between arms."""
    bad = {k: g[k] for k in ('G1_closure_violations', 'G2_budget_violations',
                             'G3_negative_shares', 'G3_negative_counts',
                             'G4_waterfill_bind') if g[k] != 0}
    if bad:
        return Outcome.fail('RBDEP_HARD_GATE_FAILED',
                            'allocation closure / negativity / cap repair: '
                            + ', '.join(f'{k}={v}' for k, v in bad.items()),
                            **g)
    return Outcome.ok('RBDEP_HARD_GATES_PASS', value=g, **g)
