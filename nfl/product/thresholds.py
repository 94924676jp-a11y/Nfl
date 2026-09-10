"""Threshold probabilities, from the model's stored draws and nothing else.

THESE ARE MODEL PROBABILITIES, NOT BETTING RECOMMENDATIONS, and no sportsbook
number enters this file. If a market feed does not exist -- and none does -- the
board shows no line, no implied probability, no edge and no recommendation.
There is nothing here to compare against a price, deliberately.

The thresholds are FIXED IN ADVANCE per metric, the same ladder for every
player, so a threshold can never be chosen after seeing where a projection
landed. Counts use `>= k` because a count can equal k exactly; yardage uses a
half-point line because a drawn yardage can equal a whole number and `over 200`
would otherwise be ambiguous.
"""
from __future__ import annotations

from nfl.product import distributions as D

# Fixed ladders. Owner-named where the directive named them.
LADDERS = {
    ('qb', 'pyds'): [175.5, 200.5, 225.5, 250.5, 275.5, 300.5],
    ('qb', 'att'): [24.5, 29.5, 34.5, 39.5],
    ('qb', 'cmp'): [14.5, 19.5, 24.5, 29.5],
    ('qb', 'ptd'): [1, 2, 3],
    ('qb', 'int'): [1, 2],
    ('qb', 'ryds'): [9.5, 19.5, 29.5, 39.5],
    ('qb', 'rush_opp'): [2, 4, 6],
    ('qb', 'sacks'): [1, 2, 3],

    ('rushing', 'carries'): [9.5, 12.5, 15.5, 18.5, 21.5],
    ('rushing', 'rushing_td'): [1, 2],

    ('receiving', 'receptions'): [2.5, 3.5, 4.5, 5.5, 6.5, 7.5],
    ('receiving', 'receiving_yards'): [24.5, 39.5, 49.5, 59.5, 74.5, 99.5],
    ('receiving', 'targets'): [4.5, 6.5, 8.5, 10.5],
    ('receiving', 'receiving_td'): [1, 2],
}

# Counts use `>= k`; anything else uses `> line`.
COUNT_METRICS = {('qb', 'ptd'), ('qb', 'int'), ('qb', 'rush_opp'),
                 ('qb', 'sacks'), ('rushing', 'rushing_td'),
                 ('receiving', 'receiving_td')}

DISCLAIMER = ('Model probabilities from stored simulation draws. No '
              'sportsbook line, implied probability or edge appears here, '
              'because no market feed exists in this system. Not a wager '
              'recommendation.')


def ladder(layer, key):
    return list(LADDERS.get((layer, key), []))


def probabilities(vec, layer, key) -> list:
    """The fixed ladder for this metric, evaluated on this player's draws."""
    if vec is None:
        return []
    out = []
    for t in ladder(layer, key):
        if (layer, key) in COUNT_METRICS:
            out.append({'threshold': f'{int(t)}+',
                        'p': D.p_at_least(vec, t)})
        else:
            out.append({'threshold': f'{t}+', 'p': D.p_over(vec, t)})
    return out


def td_probability(fc, gsis_id, layers) -> dict:
    """P(at least one touchdown), and the joint is taken PER DRAW.

    A receiver's receiving TD and a back's rushing TD are not independent
    events to be multiplied: they are two columns of the same draw index, and
    the same draw is the same simulated game. Multiplying the marginals would
    invent an independence the draws do not have. `anytime` is therefore
    computed as the fraction of draws in which the player scored at all.
    """
    import numpy as np
    cols, parts = [], {}
    for layer, key in (('qb', 'ptd'), ('qb', 'rtd'),
                       ('receiving', 'receiving_td'),
                       ('rushing', 'rushing_td')):
        if layer not in layers:
            continue
        v = fc.vector(layer, key, gsis_id)
        if v is None:
            continue
        # A PASSING TOUCHDOWN IS NOT A TOUCHDOWN THE PASSER SCORED. It is
        # excluded from `anytime` and reported on its own.
        parts[f'{layer}/{key}'] = D.p_at_least(v, 1)
        if (layer, key) != ('qb', 'ptd'):
            cols.append(np.asarray(v, float))
    if not cols:
        return {'anytime': None, 'components': parts}
    total = np.sum(cols, axis=0)
    return {'anytime': D.p_at_least(total, 1),
            'two_plus': D.p_at_least(total, 2),
            'components': parts,
            'basis': 'fraction of draws with at least one scoring play, '
                     'summed within each draw rather than multiplied across '
                     'marginals'}
