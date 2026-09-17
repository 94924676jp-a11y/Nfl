"""American odds, de-vigging, and expected value. Arithmetic only.

NOTHING HERE READS A MODEL OR WRITES ONE. These are conversions between a
price and a probability, and they exist as their own module so that a market
number can never be mistaken for a model number by sitting in the same file.

THE ONE-SIDED CASE IS THE POINT OF THIS MODULE'S CARE. A no-vig probability is
defined only when BOTH sides are priced: the whole construction is to remove
the bookmaker's margin by normalising two prices that sum to more than one.
With one price there is no margin to remove and no pair to normalise, and
reporting the raw implied probability as though it were no-vig would overstate
the book's opinion by the entire hold. Those rows return
`NO_TWO_SIDED_DEVIG` and a break-even probability instead.
"""
from __future__ import annotations

CODE_NO_DEVIG = 'NO_TWO_SIDED_DEVIG'


def american_to_prob(odds) -> float | None:
    """Raw implied probability of an American price. Includes the vig."""
    if odds is None or odds == '':
        return None
    try:
        o = float(odds)
    except (TypeError, ValueError):
        return None
    if o == 0:
        return None
    if o > 0:
        return 100.0 / (o + 100.0)
    return (-o) / ((-o) + 100.0)


def american_to_profit(odds, stake: float = 1.0) -> float | None:
    """NET profit on a winning unit stake. Not the return."""
    if odds is None or odds == '':
        return None
    try:
        o = float(odds)
    except (TypeError, ValueError):
        return None
    if o == 0:
        return None
    return stake * (o / 100.0 if o > 0 else 100.0 / (-o))


def devig(over_odds, under_odds) -> dict:
    """Two-sided proportional de-vig. Refuses to invent a one-sided answer."""
    po = american_to_prob(over_odds)
    pu = american_to_prob(under_odds)
    out = {'raw_p_over': po, 'raw_p_under': pu,
           'over_odds': over_odds, 'under_odds': under_odds}
    if po is None or pu is None:
        out.update({'hold': None, 'novig_p_over': None,
                    'novig_p_under': None, 'devig_status': CODE_NO_DEVIG,
                    'break_even_p_over': po, 'break_even_p_under': pu,
                    'why': 'only one side is priced. A no-vig probability is '
                           'the normalisation of a PAIR; with one price there '
                           'is no margin to remove, and reporting the raw '
                           'implied probability as no-vig would overstate the '
                           'book by the whole hold.'})
        return out
    s = po + pu
    out.update({'hold': s - 1.0,
                'novig_p_over': po / s, 'novig_p_under': pu / s,
                'devig_status': 'TWO_SIDED_PROPORTIONAL',
                'devig_method': 'proportional (multiplicative): p / (p_over + '
                                'p_under). Declared because shin and '
                                'power methods give different answers and a '
                                'comparison must say which it used.'})
    return out


def ev_per_unit(p_win, p_push, odds, stake: float = 1.0) -> float | None:
    """EV = p_win * net_profit - p_loss * stake, with a push returning stake.

    A COMPARISON STATISTIC, NOT A MODEL INPUT and not a recommendation. It is
    the expected value IF the model's probability were correct, which is the
    thing in question rather than something established.
    """
    profit = american_to_profit(odds, stake)
    if profit is None or p_win is None:
        return None
    pp = 0.0 if p_push is None else float(p_push)
    p_loss = 1.0 - float(p_win) - pp
    if p_loss < -1e-9:
        return None
    return float(p_win) * profit - max(p_loss, 0.0) * stake
