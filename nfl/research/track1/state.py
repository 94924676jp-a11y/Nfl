"""Track 1 step 3: simulate the game state from PREGAME information only.

WHAT MAY ENTER, AND WHAT MAY NOT.

May enter: results of games already played, who is at home, and the schedule.
That is all. May NOT enter, at any point: the realised score of the game being
forecast, the closing spread, the sportsbook total, a market win probability,
or anything else that exists only after kickoff or only in a book. The panel
this reads was built without ever reading a market column, and
`assert_pregame_only` re-checks the feature names it was handed.

THE GENERATOR, AND WHY EACH PIECE IS THE SHAPE IT IS.

Team strength is an exponentially-weighted mean of a team's own prior scoring
margins. The half-life is SELECTED INSIDE THE TRAINING WINDOW by
leave-one-season-out error on margin; it is not a number somebody liked. The
expected margin is then an ordinary least-squares fit of realised margin on
the strength difference, so the shrinkage toward zero is the fitted slope
rather than a second free constant.

The within-game path is NOT a fitted curve. Each quarter's scoring increment
is a drift share of the expected margin plus a residual, and the residuals are
RESAMPLED AS FOUR-VECTORS from whole training games. That preserves the joint
behaviour of a real game's scoring path -- quarters that blow open together,
quarters that stay tight together -- without assuming a distribution for it.
It is the same discipline as the shared historical index the team-volume layer
already uses, for the same reason: drawing dependent quantities apart
manufactures paths no real game has taken.

BOTH SIDES OF A GAME SHARE ONE PATH, with the sign flipped. A simulated game
in which both teams are trailing by two scores is not a game.
"""
from __future__ import annotations

import collections
import math
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.research.track1 import response as RESP                  # noqa: E402

SPEC_VERSION = 'track1-state-1'

# Features the generator is allowed to see. Anything outside this set is
# refused by name rather than trusted not to matter.
PREGAME_FEATURES = ('ewma_margin_home', 'ewma_margin_away', 'home_field')
FORBIDDEN_FEATURES = ('spread', 'total_line', 'vegas', 'moneyline', 'odds',
                      'closing', 'implied', 'realized_margin', 'final_margin',
                      'wp', 'win_probability')


def assert_pregame_only(feature_names):
    bad = [f for f in feature_names
           if any(s in str(f).lower() for s in FORBIDDEN_FEATURES)]
    if bad:
        raise ValueError(
            f'TRACK1_NON_PREGAME_FEATURE: {bad}. Realised score, closing '
            f'spread, sportsbook total and market win probability may not '
            f'enter the football forecast. The feature set is refused, not '
            f'filtered.')
    return True


assert_pregame_only(PREGAME_FEATURES)


def _ewma(values, half_life):
    if not values:
        return 0.0
    lam = 0.5 ** (1.0 / half_life)
    num = den = 0.0
    w = 1.0
    for v in reversed(values):
        num += w * v
        den += w
        w *= lam
    return num / den


def strength_series(game_rows, half_life):
    """Each game's pregame strength difference, from strictly earlier games.

    Margins carry across the season boundary. That is deliberate and declared:
    last December is stale information but it is not future information, and
    discarding it would leave every week 1 with no prior at all.
    """
    rows = sorted(game_rows, key=lambda r: (r['season'], r['week'],
                                            r['game_id']))
    hist = collections.defaultdict(list)
    out = []
    for r in rows:
        h, a = r['home_team'], r['away_team']
        dh = _ewma(hist[h], half_life)
        da = _ewma(hist[a], half_life)
        out.append({'game_id': r['game_id'], 'season': r['season'],
                    'week': r['week'], 'home_team': h, 'away_team': a,
                    'ewma_margin_home': dh, 'ewma_margin_away': da,
                    'strength_diff': dh - da,
                    'n_prior_home': len(hist[h]), 'n_prior_away': len(hist[a]),
                    'margin_home': r['final_margin_home'],
                    'q_starts': [r.get(f'margin_home_start_q{q}')
                                 for q in (2, 3, 4)]})
        m = r['final_margin_home']
        hist[h].append(m)
        hist[a].append(-m)
    return out


def _ols(x, y):
    """margin = b0 + b1 * strength_diff. b0 IS the home-field advantage."""
    X = np.column_stack([np.ones(len(x)), np.asarray(x, float)])
    y = np.asarray(y, float)
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    pred = X @ beta
    return float(beta[0]), float(beta[1]), pred


def select_half_life(game_rows, grid=RESP.HALF_LIFE_GRID):
    """Leave-one-season-out inside the TRAINING window. Never on eval data."""
    seasons = sorted({r['season'] for r in game_rows})
    if len(seasons) < 2:
        # One season cannot be cross-validated. Say so and take the middle of
        # the grid rather than pretending a selection happened.
        return {'half_life': float(grid[len(grid) // 2]),
                'basis': 'GRID_MIDPOINT_NO_CROSS_VALIDATION_POSSIBLE',
                'n_seasons': len(seasons), 'scores': {}}
    scores = {}
    for hl in grid:
        ss = strength_series(game_rows, hl)
        err = []
        for held in seasons:
            tr = [s for s in ss if s['season'] != held]
            te = [s for s in ss if s['season'] == held]
            if not tr or not te:
                continue
            b0, b1, _ = _ols([s['strength_diff'] for s in tr],
                             [s['margin_home'] for s in tr])
            for s in te:
                err.append((b0 + b1 * s['strength_diff'] - s['margin_home']) ** 2)
        scores[hl] = float(np.sqrt(np.mean(err))) if err else float('inf')
    best = min(scores, key=lambda k: scores[k])
    return {'half_life': float(best), 'basis': 'LEAVE_ONE_SEASON_OUT_RMSE',
            'n_seasons': len(seasons),
            'scores': {str(k): round(v, 5) for k, v in scores.items()}}


def fit_state(game_rows):
    """The whole pregame state generator, fitted on TRAINING games only."""
    sel = select_half_life(game_rows)
    hl = sel['half_life']
    ss = strength_series(game_rows, hl)
    usable = [s for s in ss if s['margin_home'] is not None]
    b0, b1, mu = _ols([s['strength_diff'] for s in usable],
                      [s['margin_home'] for s in usable])
    # per-quarter scoring increments, and their drift share of the expected
    # margin. Games missing a quarter boundary are dropped from the residual
    # pool rather than imputed.
    inc, mus = [], []
    for s, m in zip(usable, mu):
        q2, q3, q4 = s['q_starts']
        if q2 is None or q3 is None or q4 is None:
            continue
        fin = s['margin_home']
        inc.append([q2, q3 - q2, q4 - q3, fin - q4])
        mus.append(m)
    I = np.asarray(inc, float)
    mu_tr = np.asarray(mus, float)
    lam = np.zeros(4)
    denom = float((mu_tr ** 2).sum())
    for q in range(4):
        lam[q] = float((mu_tr * I[:, q]).sum() / denom) if denom else 0.25
    total = float(lam.sum())
    lam = lam / total if total else np.full(4, 0.25)
    resid = I - np.outer(mu_tr, lam)
    return {
        'spec_version': SPEC_VERSION,
        'half_life': hl, 'half_life_selection': sel,
        'home_field_advantage': b0, 'strength_slope': b1,
        'n_training_games': len(usable),
        'drift_share_by_quarter': [float(x) for x in lam],
        'increment_residuals': resid,
        'n_residual_games': int(resid.shape[0]),
        'margin_rmse_in_sample': float(np.sqrt(np.mean(
            (mu - np.array([s['margin_home'] for s in usable], float)) ** 2))),
        'pregame_features': list(PREGAME_FEATURES),
    }


def expected_margin(fit, strength_diff):
    return fit['home_field_advantage'] + fit['strength_slope'] * strength_diff


def simulate_buckets(fit, mu_home, n_draws, rng):
    """(n_draws, 4) bucket indices for the HOME side; away is the mirror.

    Quarter 1 is neutral by construction -- every game starts 0-0 -- so no
    differential is invented for it.
    """
    R = fit['increment_residuals']
    idx = rng.integers(0, R.shape[0], size=n_draws)
    lam = np.asarray(fit['drift_share_by_quarter'], float)
    e = R[idx]
    s2 = lam[0] * mu_home + e[:, 0]
    s3 = s2 + lam[1] * mu_home + e[:, 1]
    s4 = s3 + lam[2] * mu_home + e[:, 2]
    B = np.empty((n_draws, 4), int)
    B[:, 0] = RESP.NEUTRAL
    B[:, 1] = RESP.bucket_index(s2)
    B[:, 2] = RESP.bucket_index(s3)
    B[:, 3] = RESP.bucket_index(s4)
    return B, np.column_stack([s2, s3, s4])


def mirror(B):
    """The away side of the same path: bucket b becomes its reflection."""
    return (len(RESP.BUCKET_LABELS) - 1) - np.asarray(B, int)
