"""Rank projections by how much the MODEL AND ITS INPUTS can be relied on.

HIGH CONFIDENCE DOES NOT MEAN THE OUTCOME IS LIKELY. It means the inputs were
complete, the player's role is settled, his status is known, the layers that
serve him all ran, and the distribution is narrow RELATIVE TO ITS OWN SCALE. A
high-confidence projection can still miss badly -- football is the variance --
and the board says so in those words rather than leaving a reader to supply the
usual meaning of the phrase.

Nothing here consults a sportsbook. There is no market feed in this system, so
there is no edge to rank by, and ranking by a fabricated one would be worse
than not ranking at all.
"""
from __future__ import annotations

import numpy as np

from nfl.product import metrics as M

# Weights over the five declared dimensions. Flat by design: there is no
# evidence yet about which dimension predicts a miss, and inventing a weighting
# would be a fitted constant with no data behind it. When the postgame ledger
# has accumulated enough independent games to say, that is a research ruling,
# not a product change.
DIMENSIONS = ('input_completeness', 'role_certainty', 'distribution_width',
              'status_certainty', 'layer_completeness')
WEIGHTS = {d: 1.0 / len(DIMENSIONS) for d in DIMENSIONS}

WEIGHTS_NOTE = ('flat by design: no evidence yet says which dimension '
                'predicts a miss, and a fitted weighting with nothing behind '
                'it would be a silent constant')


def dispersion(vec):
    """Width relative to scale, so a 250-yard metric and a 3-catch metric are
    comparable. Interquartile range over the median -- robust, and defined for
    the zero-inflated shapes these draws take.

    A ZERO IQR IS NOT PRECISION. It means the middle half of the draws are
    identical, which for a bench player means the model is putting most of its
    mass on "did not play a meaningful snap". Scoring that as a narrow
    distribution is how the FIRST version of this board ranked four backup
    quarterbacks and two fifth receivers ABOVE the starters: their IQR was
    zero, their width score was a perfect 1.0, and a role certainty of 1%
    could not outvote it. Degenerate is now reported as degenerate.
    """
    x = np.asarray(vec, float)
    iqr = float(np.percentile(x, 75) - np.percentile(x, 25))
    if iqr <= 0:
        return None
    med = float(np.percentile(x, 50))
    if med > 0:
        return iqr / med
    mean = float(x.mean())
    return iqr / mean if mean > 0 else None


DEGENERATE = ('degenerate: the middle half of the draws are identical, so '
              'there is no spread to be confident about')


def _score_width(disp):
    if disp is None:
        return 0.0, DEGENERATE
    # 0 at IQR/median >= 1.5, 1 at 0. Linear, declared, not fitted.
    return max(0.0, min(1.0, 1.0 - disp / 1.5)), 'IQR/median %.2f' % disp


def score_player(fc, gsis_id, position, layers_present, readiness,
                 primary=None) -> dict:
    """Five dimensions in [0, 1], each with the reason it scored what it did."""
    art = fc.artifact
    reasons = {}

    # 1. input completeness -- did every source this run declares arrive?
    caps = art.get('source_captures') or []
    reasons['input_completeness'] = f'{len(caps)} source capture(s) validated'
    inputs = 1.0 if len(caps) >= 5 else (0.6 if caps else 0.0)

    # 2. role certainty -- is this player's share of his team concentrated
    #    enough to call him a starter, or is he one of several?
    role, role_why = _role(fc, gsis_id, position, layers_present)
    reasons['role_certainty'] = role_why

    # 3. distribution width, on the player's PRIMARY metric
    prim = primary or _primary(position, layers_present)
    vec = fc.vector(*prim, gsis_id) if prim else None
    width, width_why = _score_width(dispersion(vec)) if vec is not None \
        else (0.0, 'no primary metric distribution')
    reasons['distribution_width'] = width_why

    # 4. status certainty -- from the readiness contract, not from a guess
    stat, stat_why = _status(readiness)
    reasons['status_certainty'] = stat_why

    # 5. layer completeness -- are the layers serving this position MODELED,
    #    or PROVISIONAL, or missing?
    layer, layer_why = _layers(position, layers_present)
    reasons['layer_completeness'] = layer_why

    parts = {'input_completeness': inputs, 'role_certainty': role,
             'distribution_width': width, 'status_certainty': stat,
             'layer_completeness': layer}
    total = sum(WEIGHTS[d] * parts[d] for d in DIMENSIONS)
    return {'score': round(total, 4), 'parts': {k: round(v, 4)
                                                for k, v in parts.items()},
            'reasons': reasons, 'primary_metric': '/'.join(prim) if prim
            else None,
            'means': 'confidence in the model and its inputs, NOT in the '
                     'outcome. A high-confidence projection can still miss.'}


def _primary(position, layers_present):
    for cand in (('qb', 'pyds'), ('rushing', 'carries'),
                 ('receiving', 'targets')):
        if cand[0] in layers_present:
            return cand
    return None


def _role(fc, gsis_id, position, layers_present):
    """Share of his own team's opportunity, per draw."""
    if 'qb' in layers_present:
        v = fc.vector('qb', 'db', gsis_id)
        tot = fc.arrays.get('qb__db')
        if v is not None and tot is not None:
            sh = float(v.mean()) / max(float(tot.sum(0).mean()), 1e-9)
            return (min(1.0, sh / 0.8),
                    f'{sh:.0%} of the game\'s quarterback dropbacks')
    # A BACK'S ROLE IS HIS CARRIES. Iterating receiving-first described
    # Christian McCaffrey as "5% of the game's targets" and scored his role
    # off that, which is true and is not what makes him the starter.
    order = ((('rushing', 'carries'), ('receiving', 'targets'))
             if position == 'RB'
             else (('receiving', 'targets'), ('rushing', 'carries')))
    for layer, key in order:
        if layer not in layers_present:
            continue
        v = fc.vector(layer, key, gsis_id)
        tot = fc.arrays.get(f'{layer}__{key}')
        if v is None or tot is None:
            continue
        sh = float(v.mean()) / max(float(tot.sum(0).mean()), 1e-9)
        # A featured back or a WR1 sits near 0.25 of his game's pool; that is
        # taken as the top of the scale rather than 100%, which no player has.
        return min(1.0, sh / 0.25), f'{sh:.0%} of the game\'s {key}'
    return 0.0, 'no opportunity share available'


def _status(readiness):
    if not readiness:
        return 0.0, 'no readiness state for this team'
    st = readiness.get('state', '')
    table = {'READY_WITH_COMPLETE_INPUT': (1.0, 'every contract field filed'),
             'READY': (0.85, 'input contract satisfied'),
             'INJURY_REPORT_INCOMPLETE': (
                 0.4, 'rows filed but report_status unfilled -- the '
                      'game-designation report was never captured'),
             'INJURY_REPORT_STALE': (0.4, 'the feed moved on, this block '
                                          'did not'),
             'INJURY_REPORT_NOT_YET_FILED': (
                 0.15, 'ABSENCE OF A REPORT, never read as absence of injury'),
             'INJURY_REPORT_CHRONOLOGY_FAILURE': (
                 0.0, 'no chronology-valid report'),
             'READINESS_CLOCK_UNRESOLVED': (0.0, 'no clock to judge by')}
    return table.get(st, (0.0, st or 'unknown'))


def _layers(position, layers_present):
    want = M.POSITION_LAYERS.get(position, ())
    if not want:
        return 0.0, f'{position} is not a forecastable position in V1'
    got = [w for w in want if w in layers_present]
    if not got:
        return 0.0, f'none of {want} produced output'
    keys = [(l, k) for (l, k) in M.SUPPORTED if l in got]
    if not keys:
        return 0.0, 'no declared metric for the layers present'
    n_mod = sum(1 for k in keys if M.SUPPORTED[k]['status'] == M.MODELED)
    frac_layers = len(got) / len(want)
    frac_mod = n_mod / len(keys)
    why = (f'{len(got)}/{len(want)} layer(s); {n_mod}/{len(keys)} metric(s) '
           f'fully modelled, the rest provisional')
    missing = M.unavailable_for(position)
    if missing:
        why += f'; {len(missing)} named absence(s)'
    return 0.5 * frac_layers + 0.5 * frac_mod, why


def board(rows, top=8):
    """Rank, and report the two ends. The widest end is not a 'worst' list --
    a wide distribution on a genuine bench player is the model being honest."""
    ranked = sorted(rows, key=lambda r: -r['confidence']['score'])
    return {
        'weights': WEIGHTS, 'weights_note': WEIGHTS_NOTE,
        'dimensions': list(DIMENSIONS),
        'highest_confidence': ranked[:top],
        # The widest list is about GENUINELY WIDE distributions, so a
        # degenerate one is excluded from it too: "no spread at all" is not
        # the same finding as "a very broad spread".
        'widest_uncertainty': sorted(
            [r for r in rows
             if r['confidence']['reasons']['distribution_width']
             != DEGENERATE],
            key=lambda r: r['confidence']['parts']['distribution_width'])[:top],
        'means': 'model and data confidence, never outcome certainty',
        'no_market_feed': 'ranking by sportsbook edge is not possible and is '
                          'not attempted; no price exists in this system',
    }
