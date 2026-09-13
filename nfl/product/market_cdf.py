"""Exact model-vs-market probabilities, computed from the draws themselves.

THE MARKET IS STRICTLY DOWNSTREAM. Nothing in this module is ever read by a
model, a feature builder, or a fit. It consumes a frozen draw set that already
exists and a frozen price that already exists, and it subtracts. If this file
were deleted the forecasts would be byte-identical, and the suite asserts that.

WHY IT EXISTS

The export carried `model_probability_over_market_line` and filled it by
approximation -- a Normal fitted to a mean and an SD, or an interpolation
between stored percentiles -- while the actual Monte Carlo draws sat on disk
beside it. That is a lossy answer to a question with an exact one. A receiving
line at 39.5 against a distribution with 41% of its mass at exactly zero is not
Normal in any useful sense, and a percentile interpolation cannot see the atom
at all.

So: P(X > line) is the fraction of draws above the line. Nothing is fitted,
nothing is smoothed, and the count that produced each probability is stored
beside it so a later reader never has to re-approximate.

PUSHES ARE AN ATOM, NOT A ROUNDING QUESTION. On a whole-number line a discrete
metric -- receptions, carries, touchdowns -- can land exactly on it, and that
outcome is a push: the stake is returned and neither side wins. It is reported
as its own probability and never folded into either side. On a half-point line
the push probability is exactly zero, and that is asserted rather than assumed.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import math

import numpy as np

SPEC_VERSION = 'market-cdf-exact-1'

# Metrics whose support is the non-negative integers. A whole-number line on
# one of these can be pushed; a continuous metric (yards is treated as integer
# by the engine, but a line like 39.5 cannot be hit) cannot.
DISCRETE_METRICS = ('receptions', 'targets', 'carries', 'att', 'cmp', 'db',
                    'int', 'ptd', 'rtd', 'sacks', 'scr', 'rush_opp',
                    'receiving_td', 'rushing_td')

# Every field this module is allowed to read from a market quote. The suite
# checks that NO name here appears in any model feature schema.
MARKET_FIELDS = ('line', 'over_price', 'under_price', 'retrieved_at',
                 'source', 'market_timestamp')


class MarketLeak(RuntimeError):
    """Raised if a market value is asked to influence anything upstream."""


def american_to_implied(price) -> float | None:
    """American odds -> implied probability, WITH the vig still in it.

    Returned as the book's own number. De-vigging is a separate, named step
    because the two are different quantities and conflating them is how a
    3-6% hold silently becomes 'edge'.
    """
    if price is None or price == '':
        return None
    p = float(price)
    if p == 0:
        return None
    return (-p) / ((-p) + 100.0) if p < 0 else 100.0 / (p + 100.0)


def devig_proportional(p_over, p_under) -> dict:
    """Remove the hold by scaling both sides to sum to 1.

    PROPORTIONAL, AND SAID SO. It is the standard choice and it is a CHOICE:
    it assumes the book's margin is spread across the two sides in proportion
    to their prices. Shin and power methods answer differently on longshots.
    The method is recorded in every row so a later reader is never guessing
    which one produced the number.
    """
    if p_over is None or p_under is None:
        return {'method': 'none', 'no_vig_over': None, 'no_vig_under': None,
                'hold': None, 'reconciles_to_one': None}
    s = p_over + p_under
    if s <= 0:
        return {'method': 'none', 'no_vig_over': None, 'no_vig_under': None,
                'hold': None, 'reconciles_to_one': None}
    o, u = p_over / s, p_under / s
    return {'method': 'proportional', 'no_vig_over': o, 'no_vig_under': u,
            'hold': s - 1.0, 'reconciles_to_one': abs(o + u - 1.0) <= 1e-12}


def _is_discrete(metric: str) -> bool:
    tail = str(metric).split('/')[-1]
    return tail in DISCRETE_METRICS


def empirical_cdf_at(draws, line, metric) -> dict:
    """P(>line), P(<line), P(==line) counted, never fitted.

    The three probabilities sum to exactly 1 by construction because they
    partition the draws, and that is asserted rather than trusted.
    """
    x = np.asarray(draws, dtype=float).ravel()
    n = int(x.size)
    if n == 0:
        raise ValueError('EMPTY_DRAW_SET: an empty draw set is not a '
                         'distribution and cannot be evaluated at a line')
    L = float(line)
    n_over = int(np.count_nonzero(x > L))
    n_under = int(np.count_nonzero(x < L))
    n_push = int(np.count_nonzero(x == L))
    assert n_over + n_under + n_push == n, 'draw partition does not close'
    whole = float(L).is_integer()
    discrete = _is_discrete(metric)
    # A DRAW EXACTLY ON THE LINE IS NOT ALWAYS A PUSH, AND THE TWO MUST NOT BE
    # THE SAME NUMBER.
    #
    # MEASURED 2026-09-13 on real qb/pyds draws: one draw equalled exactly
    # 214.5 against a 214.5 line. Passing yards are integers in the world, so
    # a half-point line can never push -- but these draws are NOT integers.
    # The R2 composition scales each draw by a continuous factor, so the
    # stored values are real-valued and can land on a half point. That is a
    # property of the model's arithmetic, not a settleable outcome.
    #
    # So two different quantities are reported. `p_push` is a SETTLEMENT
    # statement and is non-zero only where a push can actually occur: a whole
    # line on a discrete metric. `p_model_equals_line` is an ARITHMETIC fact
    # about the draw set, always reported, never silently folded into a side.
    # This used to raise. Raising discarded a real forecast over a 1-in-1000
    # float coincidence, and a refusal that destroys the answer is worse than
    # a number that explains itself.
    push_possible = bool(whole and discrete)
    n_settle_push = n_push if push_possible else 0
    collision = bool(n_push and not push_possible)
    return {
        'n_draws': n,
        'n_over': n_over, 'n_under': n_under,
        'n_push': n_settle_push,
        'n_model_equals_line': n_push,
        'p_over': n_over / n, 'p_under': n_under / n,
        'p_push': n_settle_push / n,
        'p_model_equals_line': n_push / n,
        # F(line) = P(X <= line): the CDF proper, draws on the line included.
        'model_cdf_at_line': (n_under + n_push) / n,
        'model_percentile_of_line': 100.0 * (n_under + n_push) / n,
        'push_possible': push_possible,
        'line_is_whole_number': whole,
        'metric_is_discrete': discrete,
        'draw_on_a_non_pushable_line': collision,
        'draw_on_a_non_pushable_line_note': (
            (f'{n_push} draw(s) equal the line {L} exactly, on a line where a '
             f'push cannot settle. These draws are counted in '
             f'p_model_equals_line and in the CDF, and are NOT counted as a '
             f'push and NOT assigned to either side. Cause: the stored draws '
             f'are real-valued because the composition scales them by a '
             f'continuous factor.') if collision else None),
        'partition_closes': (n_over + n_under + n_push) == n,
        'partition_note': ('p_over + p_under + p_model_equals_line == 1 '
                           'exactly; p_push is a subset of '
                           'p_model_equals_line and is zero unless a push '
                           'can settle'),
        'method': 'EMPIRICAL_COUNT_OVER_STORED_DRAWS',
        'not_method': 'no Normal was fitted and no quantile was interpolated',
    }


def summarise_draws(draws) -> dict:
    x = np.asarray(draws, dtype=float).ravel()
    return {'mean': float(x.mean()), 'median': float(np.median(x)),
            'sd': float(x.std(ddof=0)), 'min': float(x.min()),
            'max': float(x.max()), 'n_draws': int(x.size),
            'frac_zero': float(np.count_nonzero(x == 0.0) / x.size)}


def draws_digest(draws) -> str:
    """Content identity of the draw set, so a leak is detectable, not argued."""
    x = np.ascontiguousarray(np.asarray(draws, dtype=float).ravel())
    return hashlib.sha256(x.tobytes()).hexdigest()


def compare(draws, metric, quote) -> dict:
    """One market, evaluated exactly against one frozen draw set.

    `quote` carries only MARKET_FIELDS. The draws are read and never written,
    and the digest before and after is recorded so "the market did not touch
    the model" is a measurement rather than a promise.
    """
    bad = [k for k in quote if k not in MARKET_FIELDS]
    if bad:
        raise MarketLeak(
            f'UNDECLARED_MARKET_FIELD: {sorted(bad)}. Only {MARKET_FIELDS} '
            f'may cross this boundary, so that what the comparator can see is '
            f'a fixed, reviewable list rather than whatever a caller passes.')
    before = draws_digest(draws)
    cdf = empirical_cdf_at(draws, quote['line'], metric)
    io = american_to_implied(quote.get('over_price'))
    iu = american_to_implied(quote.get('under_price'))
    nv = devig_proportional(io, iu)
    after = draws_digest(draws)
    if before != after:
        raise MarketLeak('DRAWS_MUTATED_DURING_COMPARISON: the comparator '
                         'changed the draw set it was given')
    d_over = (cdf['p_over'] - nv['no_vig_over']
              if nv['no_vig_over'] is not None else None)
    d_under = (cdf['p_under'] - nv['no_vig_under']
               if nv['no_vig_under'] is not None else None)
    return {
        'spec_version': SPEC_VERSION,
        'metric': metric,
        'market': {k: quote.get(k) for k in MARKET_FIELDS},
        'model': summarise_draws(draws),
        'model_draws_sha256': before,
        'model_draws_sha256_after': after,
        'draws_unchanged': True,
        'exact_probability': cdf,
        'implied_over': io, 'implied_under': iu,
        'implied_sum_with_vig': (io + iu) if (io is not None
                                             and iu is not None) else None,
        'no_vig': nv,
        'disagreement_over': d_over,
        'disagreement_under': d_under,
        'disagreement_definition': (
            'model probability minus de-vigged market probability, per side. '
            'It is a disagreement, not an edge estimate and not a '
            'recommendation.'),
        'computed_at': dt.datetime.now(dt.timezone.utc).isoformat(),
    }
