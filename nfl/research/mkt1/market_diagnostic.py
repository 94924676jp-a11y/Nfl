"""MKT1: compare a frozen forecast against an external market. DIAGNOSTIC ONLY.

WHY THIS LIVES IN nfl/research AND NOT IN nfl/product.

The product layer has a hard architectural boundary: no sportsbook number may
enter it, and `test_product_layer.py` greps the whole package for eleven market
terms to keep it that way. That boundary is worth more than the convenience of
putting this next to the board code, so the market never crosses it. Nothing in
`nfl/product` imports this module, and nothing here can reach a board.

WHAT THIS IS AND IS NOT.

The market is a second opinion formed by people with information we do not
have -- beat reporting, inactives, coaching intent -- and priced by people who
lose money when they are wrong. That makes a disagreement INFORMATIVE. It does
not make the market correct, and it is not a label. Nothing here fits, tunes,
calibrates or scores the model against a price. The only quantity produced is
`how far apart are we, and is the pattern systematic`.

DE-VIGGING. Where both sides of a two-way market are returned by the SAME book
at the SAME numeric line, the two implied probabilities are normalised to sum
to one (the proportional, or `multiplicative`, method). This is the standard
first-order correction and it is not exact: real vig is usually applied
asymmetrically, heavier on the long side, so a proportional de-vig
systematically flatters the favourite slightly. Stated because the residual is
of the same order as some of the disagreements below.

A ONE-SIDED PRICE IS NOT DE-VIGGED AND IS NOT COMPARED as a probability.
Anytime-TD comes back as a Yes price with no No side, so its raw implied
probability carries the whole book margin -- typically 4-8 points on a plus
-money scorer market. It is reported with the margin UNREMOVED and flagged,
never silently treated as a fair probability.
"""
from __future__ import annotations

import collections
import csv
import math
import pathlib
import statistics

import numpy as np

# market label -> (layer, metric key) in the model's own vocabulary
MARKET_MAP = {
    'Pass attempts': ('qb', 'att'),
    'Passing yards': ('qb', 'pyds'),
    'Passing TD': ('qb', 'ptd'),
    'Interceptions thrown': ('qb', 'int'),
    'Rushing yards': ('qb', 'ryds'),          # QB only; see RUSHING note
    'Carries': ('rushing', 'carries'),
    'Receptions': ('receiving', 'receptions'),
    'Receiving yards': ('receiving', 'receiving_yards'),
}
# Anytime TD is handled separately: it is a joint over the draw index, not a
# threshold on one metric.
ANYTIME = 'Anytime TD (Yes)'

# A RUSHING-YARDS ROW FOR A NON-QUARTERBACK CANNOT BE COMPARED AT ALL.
# V1 has no governed carry -> yards control. The market prices it; we decline
# to. That is a coverage gap, not a disagreement, and it is reported as one.
NO_MODEL_METRIC = 'RUSHING_CONVERSION_CONTROL_UNDEFINED'


def american_to_prob(odds) -> float:
    o = float(odds)
    return (-o) / ((-o) + 100.0) if o < 0 else 100.0 / (o + 100.0)


def devig(p_over, p_under):
    """Proportional de-vig. Returns (fair_over, fair_under, hold)."""
    tot = p_over + p_under
    if tot <= 0:
        return None, None, None
    return p_over / tot, p_under / tot, tot - 1.0


def load_snapshot(path) -> list:
    rows = []
    for r in csv.DictReader(open(path)):
        if (r.get('availability') or '').strip() != 'returned':
            continue
        rows.append(r)
    return rows


def consensus(rows) -> dict:
    """(player, market) -> the books' agreed line and fair probability.

    THE CONSENSUS IS TAKEN ONLY ACROSS BOOKS QUOTING THE SAME NUMERIC LINE.
    Averaging a 15.5 with a 13.5 produces a number no book offered and a
    probability that belongs to neither. Where books disagree on the line, the
    MODAL line is used and the others are reported as dispersion.
    """
    by = collections.defaultdict(list)
    for r in rows:
        by[(r['player'], r['market'])].append(r)
    out = {}
    for key, rs in by.items():
        player, market = key
        if market == ANYTIME:
            ps = [american_to_prob(r['over_odds']) for r in rs
                  if r.get('over_odds')]
            if not ps:
                continue
            out[key] = {'player': player, 'market': market, 'line': None,
                        'n_books': len(ps),
                        'p_market_raw': round(statistics.median(ps), 4),
                        'p_market_fair': None,
                        'one_sided': True,
                        'books': sorted({r['sportsbook'] for r in rs}),
                        'note': 'one-sided price; the book margin is NOT '
                                'removed, so this over-states the true '
                                'probability by roughly the hold'}
            continue
        lines = [float(r['line']) for r in rs if r.get('line')]
        if not lines:
            continue
        modal = collections.Counter(lines).most_common(1)[0][0]
        at = [r for r in rs if r.get('line') and float(r['line']) == modal]
        fair, holds = [], []
        for r in at:
            if not (r.get('over_odds') and r.get('under_odds')):
                continue
            fo, _fu, hold = devig(american_to_prob(r['over_odds']),
                                  american_to_prob(r['under_odds']))
            if fo is not None:
                fair.append(fo)
                holds.append(hold)
        if not fair:
            continue
        out[key] = {
            'player': player, 'market': market, 'line': modal,
            'n_books': len(fair),
            'p_market_fair': round(statistics.median(fair), 4),
            'p_market_raw': round(statistics.median(
                [american_to_prob(r['over_odds']) for r in at
                 if r.get('over_odds')]), 4),
            'median_hold': round(statistics.median(holds), 4),
            'line_dispersion': sorted(set(lines)),
            'books': sorted({r['sportsbook'] for r in at}),
            'one_sided': False}
    return out


def model_probability(vec, line, market) -> dict:
    """P(over the EXACT sportsbook line) from the stored draws.

    A count metric priced at a half-point line has no ambiguity: `over 15.5`
    is `at least 16`. The draws are used exactly as stored; nothing is
    smoothed, fitted or interpolated.
    """
    x = np.asarray(vec, float)
    return {'p_model_over': round(float((x > line).mean()), 4),
            'model_mean': round(float(x.mean()), 3),
            'model_median': round(float(np.percentile(x, 50)), 3),
            'model_sd': round(float(x.std(ddof=1)), 3),
            'model_p90': round(float(np.percentile(x, 90)), 3),
            'n_draws': int(x.size)}


def standardized(line, mean, sd) -> float:
    """How far the market's line sits from the model's mean, in model SDs.

    This is the honest way to size a disagreement across metrics: eight
    carries and eighty passing yards are not comparable in raw units, and a
    probability-point gap compresses badly in the tails.
    """
    return round((line - mean) / sd, 3) if sd and sd > 0 else None
