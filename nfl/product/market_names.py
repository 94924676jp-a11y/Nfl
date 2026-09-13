"""What a sportsbook market is called, and which modelled metric it is.

DECLARED, NOT INFERRED. A book's market name and this engine's metric name are
two different vocabularies, and matching them by string similarity is how
"Rushing Attempts" quietly becomes a quarterback's scramble count. Every pair
below states the basis on which the two are the same quantity, and anything
not confidently the same quantity is ABSENT from the table -- which makes the
comparator refuse it by name rather than join it by hope.

POSITION MATTERS, because one market name maps to different metrics for
different players. "Rushing Yards" for a quarterback is `qb/ryds`; for a
running back this engine models no rushing-yards metric at all, and the
comparator says NOT_MODELLED rather than substituting carries.
"""
from __future__ import annotations

QB_POSITIONS = frozenset({'QB'})

# (market name, is the player a quarterback) -> (metric, basis)
MARKET_TO_METRIC = {
    ('Passing Yards', True): ('qb/pyds', 'passing yards, same quantity'),
    ('Passing TDs', True): ('qb/ptd', 'passing touchdowns, same quantity'),
    ('Interceptions', True): ('qb/int', 'interceptions thrown, same quantity'),
    ('Pass Completions', True): ('qb/cmp', 'completions, same quantity'),
    ('Pass Attempts', True): ('qb/att', 'pass attempts, same quantity'),
    ('Rushing Yards', True): ('qb/ryds', 'quarterback rushing yards'),
    ('Rushing Attempts', True): (
        'qb/rush_opp',
        'rush_opp is defined by the accounting invariant '
        'rush_opportunity_composition as scrambles + designed runs, which is '
        'what a quarterback rushing-attempts market counts. CAVEAT, stated '
        'rather than buried: whether kneel-downs are inside `drush` and '
        'inside the book\'s count is not established here, and a kneel-heavy '
        'game is where the two would diverge.'),
    ('Rushing Yards', False): (None, 'NOT_MODELLED: this engine has no '
                                     'non-quarterback rushing-yards metric. '
                                     'Carries are not yards.'),
    ('Rushing Attempts', False): ('rushing/carries', 'carries, same quantity'),
    ('Receiving Yards', False): ('receiving/receiving_yards',
                                 'receiving yards, same quantity'),
    ('Receptions', False): ('receiving/receptions',
                            'receptions, same quantity'),
    ('Receiving Yards', True): (None, 'NOT_MODELLED for a quarterback'),
    ('Receptions', True): (None, 'NOT_MODELLED for a quarterback'),
}


def metric_for(market: str, position: str):
    """(metric or None, basis). None means refuse, with the reason."""
    is_qb = str(position or '').strip().upper() in QB_POSITIONS
    hit = MARKET_TO_METRIC.get((str(market).strip(), is_qb))
    if hit is None:
        return None, (f'MARKET_NOT_IN_DECLARED_MAPPING: {market!r} for a '
                      f'{"quarterback" if is_qb else "non-quarterback"}. '
                      f'Refused rather than matched by name similarity.')
    return hit
