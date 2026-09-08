"""RC1: receiving conversion oracle decomposition. Frame, primitives, scoring.

Estimand: Y = receiving yards in a player-game.
Identity: Y = T x C x V, with Y = 0 whenever T = 0 or R = 0.

EXPLORATORY. 2022-2025 are heavily mined. Nothing here may be promoted.
"""
from __future__ import annotations

import bisect, collections, math, os, pickle, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
R = os.path.abspath(os.path.join(HERE, '..'))
for p in (f'{R}/s2', f'{R}/p4c', f'{R}/p4e', f'{R}/p1s'):
    sys.path.insert(0, p)
import s2_lib as SL                                            # noqa: E402
import p4c_build as CB                                         # noqa: E402

POS = ('WR', 'TE', 'RB')
EVAL = [2022, 2023, 2024, 2025]
SEED = 20260908
M_DRAWS = 2000
# The ONE shrinkage constant, and it is inherited rather than searched: 4 is
# Stage 2's own history-cohort boundary (`<4` prior appeared games), already
# fixed in this project before RC1 existed. No alternative was tried, and the
# pre-registration forbids trying one after seeing a result.
K_SHRINK = 4.0
ROLE_STEP = 0.10

RECV_PKL = os.environ.get('RC1_RECV_PKL', f'{HERE}/recv.pkl')


def load_recv():
    with open(RECV_PKL, 'rb') as fh:
        return pickle.load(fh)


def load():
    """Stage 2's frame, with receiving primitives attached per player-game."""
    rows, sub = SL.load()
    SL.attach(sub)
    recv = load_recv()
    for r in sub:
        k = (r['season'], r['week'], r['team'], r['gsis_id'])
        m = recv.get(k) or {}
        r['T'] = int(m.get('targets', 0))
        r['R'] = int(m.get('receptions', 0))
        # NULL IS NOT ZERO on a per-play field, but a player-game with no
        # receptions has receiving yards of exactly 0 -- that is an observed
        # outcome, not a missing one, and the two are kept apart here.
        r['Y'] = float(m.get('rec_yards', 0.0))
        r['air_yards_caught'] = float(m.get('air_yards_caught', 0.0))
        r['yac'] = float(m.get('yac', 0.0))
        r['n_lateral'] = int(m.get('lateral_receptions', 0))
        r['n_missing_recv_yards'] = int(m.get('reception_yards_missing', 0))
        r['rec_yards_list'] = list(m.get('rec_yards_list') or [])
        r['C'] = (r['R'] / r['T']) if r['T'] > 0 else None
        r['V'] = (r['Y'] / r['R']) if r['R'] > 0 else None
    return rows, sub


def attach_prior(sub):
    """Strictly-prior history per player. Ordinal prefix cut, never 'so far'.

    1,318 player-ordinal pairs in this frame carry two rows from mid-week team
    changes, so appending as we go would let the second row read the first.
    """
    hist = collections.defaultdict(list)
    hord = collections.defaultdict(list)
    for r in sorted(sub, key=lambda x: (x['ord'], x['team'], x['gsis_id'])):
        pid = r['gsis_id']
        k = bisect.bisect_left(hord[pid], r['ord'])
        past = [x for x in hist[pid][:k] if x['appeared']]
        r['h_n'] = len(past)
        r['h_T'] = [x['T'] for x in past]
        r['h_tgt'] = sum(x['T'] for x in past)
        r['h_rec'] = sum(x['R'] for x in past)
        r['h_yds'] = sum(x['Y'] for x in past)
        r['h_mean_T'] = float(np.mean(r['h_T'])) if past else None
        # per-reception yardage cannot be recovered per catch from a game
        # total, so the player's own V history is game-level mean yardage per
        # reception, weighted by receptions when pooled.
        r['h_V_games'] = [(x['Y'], x['R']) for x in past if x['R'] > 0]
        # The player's own per-reception yardages, flattened across prior
        # games. Kept per catch rather than per game: measured on this corpus,
        # per-reception yardage has skew 2.197 and excess kurtosis 7.830, and
        # P(gain > 40) is 0.0203 empirically against 0.0016 under a fitted
        # Normal -- the tail is understated thirteenfold by a Gaussian, so it
        # is resampled, never parameterised.
        r['h_V_flat'] = [y for x in past for y in (x.get('rec_yards_list') or [])]
        # prior-only participation step, for the role-change subgroup
        v = [x[SL.TARGET] for x in past if x.get(SL.TARGET) is not None]
        r['h_step'] = (float(np.mean(v[-2:]) - np.mean(v[-4:-2]))
                       if len(v) >= 4 else None)
        r['h_role'] = ('up' if (r['h_step'] is not None and r['h_step'] >= ROLE_STEP)
                       else 'down' if (r['h_step'] is not None
                                       and r['h_step'] <= -ROLE_STEP)
                       else 'stable')
        hist[pid].append(r)
        hord[pid].append(r['ord'])
    return sub


def eligible(r, ev=None):
    """Stage 2's accepted rule. Appeared player-games with >=1 prior appeared
    game. A zero-target appearance STAYS IN: Y = 0 is a real outcome a
    receiving-yards forecast faces, and dropping it conditions on the estimand.
    """
    if ev is not None and r['season'] != ev:
        return False
    return (r['appeared'] and (r.get('q_n_prior_app') or 0) >= 1
            and r.get('h_n') is not None and r['h_n'] >= 1)


# --------------------------------------------------------------------------
# scoring
# --------------------------------------------------------------------------
def crps_sample(draws: np.ndarray, y: float) -> float:
    """CRPS from an empirical sample.

        CRPS = E|X - y| - 0.5 E|X - X'|

    with the second term computed in O(M log M) from the sorted draws rather
    than an O(M^2) double sum.
    """
    x = np.sort(np.asarray(draws, float))
    m = len(x)
    i = np.arange(m)
    return float(np.abs(x - y).mean() - ((2 * i - m + 1) * x).sum() / (m * m))


def crps_matrix(D: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Row-wise CRPS for an (n, M) draw matrix against n observations."""
    X = np.sort(D, axis=1)
    n, m = X.shape
    i = np.arange(m)
    w = (2 * i - m + 1)
    return (np.abs(X - y[:, None]).mean(1) - (X * w).sum(1) / (m * m))


def score(D: np.ndarray, y: np.ndarray) -> dict:
    """The full predeclared set. No single number is returned alone."""
    y = np.asarray(y, float)
    point = D.mean(1)
    e = point - y
    sst = float(((y - y.mean()) ** 2).sum())
    out = {'n': int(len(y)),
           'crps': float(crps_matrix(D, y).mean()),
           'mae': float(np.abs(e).mean()),
           'rmse': float(math.sqrt(float((e * e).mean()))),
           'bias': float(e.mean()),
           'r': (float(np.corrcoef(point, y)[0, 1])
                 if point.std() > 1e-12 and y.std() > 1e-12 else None),
           'r2': float(1 - float((e * e).sum()) / sst) if sst > 0 else None,
           'sd_pred_mean': float(point.std(ddof=1)) if len(y) > 1 else None,
           'sd_actual': float(y.std(ddof=1)) if len(y) > 1 else None,
           'mean_pred': float(point.mean()), 'mean_actual': float(y.mean())}
    out['sd_ratio'] = (out['sd_pred_mean'] / out['sd_actual']
                       if out['sd_actual'] and out['sd_actual'] > 1e-12 else None)
    for lvl in (50, 80, 90, 95):
        a = (100 - lvl) / 200.0
        lo = np.quantile(D, a, axis=1)
        hi = np.quantile(D, 1 - a, axis=1)
        out[f'cover{lvl}'] = float(((y >= lo) & (y <= hi)).mean())
    return out


def cluster_bootstrap(D: np.ndarray, y: np.ndarray, games: list,
                      stat, B: int = 1000, seed: int = SEED) -> dict:
    """Resample GAMES, not rows.

    Player-games in the same game share opponent, game script and weather. An
    unclustered interval would be too narrow, and this project has already
    ruled that games are not independent observations.
    """
    rng = np.random.default_rng(seed)
    by = collections.defaultdict(list)
    for i, g in enumerate(games):
        by[g].append(i)
    keys = list(by)
    vals = []
    for _ in range(B):
        pick = rng.integers(0, len(keys), len(keys))
        idx = np.concatenate([by[keys[j]] for j in pick])
        vals.append(stat(D[idx], y[idx]))
    v = np.array(vals, float)
    v = v[np.isfinite(v)]
    if len(v) == 0:
        return {'lo': None, 'hi': None, 'B': 0}
    return {'lo': float(np.quantile(v, 0.025)),
            'hi': float(np.quantile(v, 0.975)), 'B': int(len(v))}
