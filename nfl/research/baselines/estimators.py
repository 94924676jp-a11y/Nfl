"""The baseline estimators. Pure functions of STRICTLY PRIOR history.

EVERY ESTIMATOR HERE TAKES `hist`, A LIST OF `(ordinal, value)` PAIRS THAT THE
CALLER HAS ALREADY CUT AT THE FORECAST ORDINAL, AND NOTHING ELSE THAT VARIES
WITH THE FORECAST GAME.

That signature is the point-in-time guarantee, and it is structural rather than
documentary: an estimator cannot peek at the game it is forecasting because the
game is not in its arguments. What it can still do -- and what the leak test in
`nfl/tests/test_baselines.py` actually attacks -- is receive a history the
CALLER cut wrongly. So the cut is one function, `prior`, used by everything,
and the test mutates future rows and demands byte-identical forecasts.

A leak test that only asserts `forecast(week 5) == forecast(week 5)` proves
nothing. The test here perturbs the future and requires the past not to move,
and it is demonstrated against a deliberately-leaking estimator that it does
catch.
"""
from __future__ import annotations

import bisect


class Undefined(Exception):
    """An estimator was asked for a value its declared window cannot supply."""


def prior(series, cutoff_ordinal: int):
    """The strictly-earlier prefix of an ascending `(ordinal, value)` series.

    `bisect_left` on the ordinal keys is what makes it STRICTLY earlier: a row
    at the same ordinal as the forecast -- the forecast game itself, or a
    second game a club plays in the same week after a postponement -- is on the
    future side of the cut. `everything so far` and `strictly earlier` are
    different sets and this project has already paid for confusing them once.
    """
    keys = [o for o, _ in series]
    i = bisect.bisect_left(keys, cutoff_ordinal)
    return series[:i]


def in_season(hist, season: int):
    return [(o, v) for o, v in hist if o // 100 == season]


def mean(vals):
    return sum(vals) / len(vals)


# ------------------------------------------------------------------ B-STD
def season_to_date(hist, season: int):
    """Mean of the subject's completed games in THIS season. No carry-over.

    Undefined at week 1 by construction, which is the honest state: there is no
    current-season history at week 1 and pretending otherwise is the error this
    package exists to avoid. The caller supplies the declared week-1 fallback.
    """
    cur = in_season(hist, season)
    if not cur:
        raise Undefined('SEASON_TO_DATE_NO_CURRENT_SEASON_GAMES')
    return mean([v for _, v in cur])


# ----------------------------------------------------------------- B-RECN
def recent_n(hist, n: int):
    """Mean of the last `n` completed games, crossing the season boundary.

    Crossing the boundary is a deliberate difference from B-STD and is the
    reason both exist: one asks what a season-local window buys, the other what
    a fixed-length window buys.
    """
    if not hist:
        raise Undefined('RECENT_N_NO_HISTORY')
    w = hist[-n:]
    return mean([v for _, v in w])


# ----------------------------------------------------------------- B-EWMA
def ewma(hist, half_life_games: float):
    """Exponentially weighted mean, weight 0.5 ** (games_back / half_life).

    `games_back` counts APPEARANCES, not weeks: a player who missed four weeks
    has one game of decay, not five. That is a choice, it is not obviously
    right, and it is declared in the spec rather than buried here.
    """
    if not hist:
        raise Undefined('EWMA_NO_HISTORY')
    num = den = 0.0
    m = len(hist)
    for j, (_, v) in enumerate(hist):
        back = m - 1 - j
        w = 0.5 ** (back / float(half_life_games))
        num += w * v
        den += w
    return num / den


# --------------------------------------------------------------- B-SHRINK
def shrunk(hist, season: int, mu_pos: float, k: float, c: float):
    """Prior-season carry-over shrunk toward the position mean, then updated
    by the current season.

    Two stages, each with one derived constant:

      level_prior = mu_pos + c * (m_prev - mu_pos)      c: season-to-season
                                                          OLS slope
      estimate    = (n_cur * m_cur + k * level_prior) / (n_cur + k)
                                                       k: sigma^2_within
                                                          / sigma^2_between

    `k` is the normal-normal posterior weight: with within-subject game
    variance sigma_w^2 and between-subject variance sigma_b^2, the posterior
    mean of n observations is the precision-weighted average of the sample mean
    and the prior mean with prior weight sigma_w^2 / sigma_b^2. That is a
    derivation, not a fit. `c` IS a fit, to the estimation window only, and the
    spec says so in those words.

    With no prior season, `level_prior` collapses to `mu_pos`, which is the
    correct degenerate case rather than a special one.
    """
    cur = in_season(hist, season)
    prev = in_season(hist, season - 1)
    if prev:
        m_prev = mean([v for _, v in prev])
        level_prior = mu_pos + c * (m_prev - mu_pos)
    else:
        level_prior = mu_pos
    n_cur = len(cur)
    if n_cur == 0:
        return level_prior
    m_cur = mean([v for _, v in cur])
    return (n_cur * m_cur + k * level_prior) / (n_cur + k)


# ----------------------------------------------------------------- B-ROLE
def role_average(role_table, position: str, rank: int):
    """The league mean for a role slot -- (position, within-team usage rank) --
    computed from seasons strictly before the forecast season.

    THIS ESTIMATOR NEVER READS THE PLAYER'S OWN LEVEL. Its only input from the
    subject is which slot he occupies, and the slot is assigned from strictly
    prior usage. It is the baseline that answers "how much of this is just
    knowing who the WR1 is".
    """
    key = (position, min(rank, role_table['max_rank']))
    v = role_table['means'].get(key)
    if v is None:
        raise Undefined(f'ROLE_SLOT_UNSEEN:{key}')
    return v


# --------------------------------------------------------------- L-PRIOR
def league_prior(prior_table, position: str):
    """The league/position mean from strictly prior seasons. Always defined for
    a labelled position, and the terminal fallback for every other estimator."""
    v = prior_table.get(position)
    if v is None:
        raise Undefined(f'LEAGUE_PRIOR_UNSEEN_POSITION:{position}')
    return v


# ------------------------------------------------ week-1 transition family
def w1_prior_season_shrunk(hist, season: int, mu_pos: float, k: float,
                           c: float):
    """THE FROZEN WEEK-1 BASELINE. Identical to `shrunk` with an empty current
    season, i.e. the carried-over prior-season mean shrunk to the position
    mean.

    Chosen on a stated principle and NOT on its score: a mean over a player's
    whole prior season has strictly smaller sampling variance than any single
    game drawn from it, for the same estimand. Nothing about the evaluation
    window entered the choice, and the comparator below was scored only after
    this spec was frozen and hashed.
    """
    return shrunk([h for h in hist if h[0] // 100 < season], season, mu_pos,
                  k, c)


def w1_final_game(hist, season: int):
    """DIAGNOSTIC COMPARATOR, NOT A FROZEN DEFAULT: the prior season's final
    game.

    This is the estimator SHAPE the engine already carries, and its pathology
    is already measured: `previous_primary_detail(2026, 1)['KC']` resolves to
    2025 week 18, and the charted QB1 equals the prior-season final-game
    primary in only 59 of 160 week-1 rooms (0.3688). Anything built on "last
    season's final game" inherits that. It is scored here so the cost is a
    number rather than an assertion.
    """
    prevs = [h for h in hist if h[0] // 100 < season]
    if not prevs:
        raise Undefined('W1_FINAL_GAME_NO_PRIOR_SEASON')
    return prevs[-1][1]


def w1_prior_season_mean(hist, season: int):
    """Unshrunk prior-season mean. The middle term between the two above, kept
    so the shrinkage and the window can be told apart."""
    prevs = [(o, v) for o, v in hist if o // 100 == season - 1]
    if not prevs:
        raise Undefined('W1_PRIOR_SEASON_MEAN_NO_PRIOR_SEASON')
    return mean([v for _, v in prevs])
