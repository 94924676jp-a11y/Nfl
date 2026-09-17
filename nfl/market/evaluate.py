"""Exact evaluation of a sealed simulation at a sportsbook threshold.

NO DISTRIBUTIONAL ASSUMPTION IS MADE ANYWHERE IN THIS FILE. The probability at
a line is counted from the frozen draws:

    P(over)  = mean(x >  line)
    P(under) = mean(x <  line)
    P(push)  = mean(x == line)

and those three sum to exactly 1 by construction. Nothing is read from a mean,
a standard deviation, a stored percentile, or a Gaussian fitted to them. A
p10/p50/p90 triple cannot answer "what is P(X > 36.5)" and interpolating one
into an answer is the failure this module exists to avoid.

HALF-POINT VERSUS WHOLE-NUMBER LINES ARE HANDLED BY THE SAME CODE, and that is
deliberate. At a half-point line no draw can equal it, so `P(push)` counts zero
by construction rather than by a special case. At a whole number the atom is
REAL and is counted: the pushed mass is the share of draws landing exactly on
the line, which for an integer-supported count can be large.

MARKET-TO-ARRAY MAPPING IS AN EXPLICIT TABLE, NEVER A GUESS. A market whose
quantity the sealed world does not contain is refused by name. That is why
longest-reception, longest-rush and longest-completion are unsupported here:
the frozen draws hold per-game totals, not the per-event maxima those markets
settle on, and a maximum cannot be recovered from a sum.
"""
from __future__ import annotations

import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

SPEC_VERSION = 'market-exact-evaluation-1'

# ---------------------------------------------------------------- coverage
EXACT = 'EXACT_MODEL_SUPPORTED'
LINE_UNSUPPORTED = 'MODEL_STAT_EXISTS_BUT_LINE_EVALUATION_UNSUPPORTED'
STAT_MISSING = 'MODEL_STAT_NOT_AVAILABLE'
NOT_IN_UNIVERSE = 'PLAYER_NOT_IN_MODEL_UNIVERSE'
IDENTITY_UNRESOLVED = 'IDENTITY_UNRESOLVED'
ONE_SIDED = 'ONE_SIDED_MARKET'
NON_PLAYER = 'NON_PLAYER_MARKET'
OTHER_REFUSAL = 'OTHER_EXPLICIT_REFUSAL'
COVERAGE_STATES = (EXACT, LINE_UNSUPPORTED, STAT_MISSING, NOT_IN_UNIVERSE,
                   IDENTITY_UNRESOLVED, ONE_SIDED, NON_PLAYER, OTHER_REFUSAL)

#: market name -> how to build the per-draw quantity from the sealed layers.
#: `sum` entries add WITHIN A DRAW, which is the dependence check a combined
#: prop demands: adding marginal means, or convolving two independent
#: marginals, would give a different and wrong answer.
MARKET_MAP = {
    'Player Passing Yards': {'layer': 'qb', 'metric': 'pyds'},
    'Player Passing Attempts': {'layer': 'qb', 'metric': 'att'},
    'Player Passing Completions': {'layer': 'qb', 'metric': 'cmp'},
    'Player Passing Touchdowns': {'layer': 'qb', 'metric': 'ptd'},
    'Player Interceptions': {'layer': 'qb', 'metric': 'int'},
    'Player Receptions': {'layer': 'receiving', 'metric': 'receptions'},
    'Player Receiving Yards': {'layer': 'receiving',
                               'metric': 'receiving_yards'},
    'Player Rushing Attempts': {'layer': 'rushing', 'metric': 'carries'},
    'Player Rushing Yards': {'layer': 'rushing_total',
                             'metric': 'rushing_yards',
                             'note': 'rushing_total carries every rusher '
                                     'including quarterbacks; the `rushing` '
                                     'layer covers 6 backs only'},
    'Player Rushing + Receiving Yards': {
        'sum': [('rushing_total', 'rushing_yards'),
                ('receiving', 'receiving_yards')],
        'note': 'added WITHIN each draw, so the joint dependence between a '
                'player`s rushing and receiving yards is preserved. Adding '
                'marginal means or convolving independently would answer a '
                'different question.'},
    'Player Field Goals Made': {'layer': 'kicking', 'metric': 'fgm'},
}

#: Markets refused BY NAME, with the reason. Recorded rather than omitted so
#: that absence is a decision a reader can audit.
UNSUPPORTED_MARKETS = {
    'Player Longest Reception': 'settles on the MAXIMUM single reception. The '
                                'sealed world holds per-game receiving totals '
                                'and per-catch atoms are not exported in this '
                                'artifact, so a maximum cannot be recovered '
                                'from a sum.',
    'Player Longest Rush': 'settles on the maximum single carry; the sealed '
                           'world holds per-game rushing totals only.',
    'Player Longest Passing Completion': 'settles on the maximum single '
                                         'completion; not present as an '
                                         'event-level quantity.',
    'Player Kicking Points': 'requires the kicker`s scoring construction '
                             '(field goals by distance bucket plus extra '
                             'points) resolved to a point total in the same '
                             'draw. The arrays exist but the scoring '
                             'composition is not verified exact in this '
                             'artifact, and an approximation is worse than a '
                             'refusal.',
    'Player Touchdowns': 'a touchdown ladder needs each player`s TOTAL '
                         'touchdowns in the same simulated world. Receiving, '
                         'rushing and passing touchdowns live in three '
                         'separate layers with different row sets, and '
                         'combining them is a construction this artifact has '
                         'not verified.',
}

CODE_OK = 'MARKET_ROW_EVALUATED'


def build_quantity(z, manifest, market: str, gsis_id: str):
    """The per-draw vector for one player and one market, or (None, reason)."""
    spec = MARKET_MAP.get(market)
    if spec is None:
        return None, (STAT_MISSING, f'{market!r} has no declared mapping')
    layers = manifest['layers']

    def one(layer, metric):
        L = layers.get(layer)
        if L is None:
            return None, f'layer {layer!r} absent from the sealed draws'
        ids = list(L.get('row_ids') or [])
        if gsis_id not in ids:
            return None, f'{gsis_id} has no row in the {layer!r} layer'
        key = f'{layer}__{metric}'
        if key not in z.files:
            return None, f'{key} absent from the draw archive'
        # ROW MAPPED BY EXPLICIT ID, NEVER BY BOARD ORDER.
        return np.asarray(z[key], float)[ids.index(gsis_id)], None

    if 'sum' in spec:
        parts, notes = [], []
        for layer, metric in spec['sum']:
            v, err = one(layer, metric)
            if v is None:
                return None, (STAT_MISSING,
                              f'combined market needs {layer}/{metric}: {err}')
            parts.append(v)
            notes.append(f'{layer}/{metric}')
        n = {len(p) for p in parts}
        if len(n) != 1:
            return None, (OTHER_REFUSAL,
                          f'component draw counts differ: {sorted(n)}')
        return np.sum(parts, axis=0), ('+'.join(notes), spec.get('note'))
    v, err = one(spec['layer'], spec['metric'])
    if v is None:
        return None, (STAT_MISSING, err)
    return v, (f"{spec['layer']}/{spec['metric']}", spec.get('note'))


def evaluate_line(x, line: float) -> dict:
    """Counted from the draws. No distribution is assumed or fitted."""
    v = np.asarray(x, float)
    v = v[np.isfinite(v)]
    n = int(v.size)
    if n == 0:
        return {'n_draws': 0, 'p_over': None, 'p_under': None,
                'p_push': None, 'error': 'no finite draws'}
    L = float(line)
    n_over = int((v > L).sum())
    n_under = int((v < L).sum())
    n_push = int((v == L).sum())
    p_over = n_over / n
    p_under = n_under / n
    p_push = n_push / n
    return {
        'n_draws': n,
        'n_over': n_over, 'n_under': n_under, 'n_push': n_push,
        'p_over': p_over, 'p_under': p_under, 'p_push': p_push,
        # THE MONTE CARLO STANDARD ERROR OF A COUNTED PROPORTION.
        'mcse_over': float(np.sqrt(max(p_over * (1 - p_over), 0.0) / n)),
        'mcse_under': float(np.sqrt(max(p_under * (1 - p_under), 0.0) / n)),
        'sums_to_one': abs(p_over + p_under + p_push - 1.0) < 1e-12,
        'mean': float(v.mean()), 'median': float(np.median(v)),
        'sd': float(v.std(ddof=1)) if n > 1 else None,
        'p05': float(np.percentile(v, 5)),
        'p25': float(np.percentile(v, 25)),
        'p75': float(np.percentile(v, 75)),
        'p95': float(np.percentile(v, 95)),
        'min': float(v.min()), 'max': float(v.max()),
        'frac_zero': float((v == 0).mean()),
        'line_is_half_point': abs(L - round(L)) > 1e-9,
        'method': 'counted from the frozen draws: mean(x>L), mean(x<L), '
                  'mean(x==L). No mean/sd/percentile/Gaussian is used.',
    }
