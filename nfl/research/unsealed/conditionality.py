"""Separate the two quantities a player projection table silently mixes.

THE DEFECT THIS ADDRESSES, IN ONE EXAMPLE

In run 2fc4e9599f0889f1, Jordan Love's mean DK points are 15.25 and Cooper
Rush's are 9.23. Read side by side, Rush looks like a badly underprojected
starting quarterback. He is not. Love records an opportunity in 96% of
simulated worlds, so his 15.25 is very nearly a conditional number. Rush does
so in 66%, and a third of his 9.23 is mass contributed by worlds in which he
never takes a snap. Conditional on playing he is 14.04, an ordinary starter's
line.

Both numbers are correct and they answer different questions. The
unconditional mean is right for a question that integrates over who starts.
The conditional mean is right for "how good is he if he plays". A table that
prints one of them under a heading that could mean either invites the reader
to compare quantities that are not comparable, and the reader is not at fault
for accepting the invitation.

This module alters no projection. It reads the same draws and reports the
decomposition alongside them.

WHY THE FIELD IS NOT CALLED `p_plays`

The artifact carries no participation or appearance layer. What can be
measured from the draws is whether a player recorded a non-zero MODELLED
OPPORTUNITY -- a dropback, a target, a carry, a kick attempt -- in a given
world. A player who is on the field all game and is never thrown to records
none, and would be counted here as not participating. So this quantity is a
LOWER BOUND on participation and is named for what it measures rather than
for what a reader might wish it measured. Naming it `p_plays` would be the
same class of error the module exists to fix.
"""
from __future__ import annotations

import numpy as np

SPEC_VERSION = 'draw-conditionality/1.0.0'

#: Arrays that represent an OPPORTUNITY rather than an outcome, by layer.
#: Outcome arrays are deliberately excluded: a player can play and gain zero
#: yards, so conditioning on a non-zero outcome would confuse "did not play"
#: with "played badly" -- which is exactly the conflation being repaired.
OPPORTUNITY_ARRAYS = {
    'qb': ('db', 'att'),
    'receiving': ('targets',),
    'rushing': ('carries',),
    'kicking': ('fga', 'xpa'),
    'gadget_rush': ('te', 'wr'),
}

#: Below this many qualifying draws the conditional mean is not reported.
#: A mean over a handful of draws is noise wearing a decimal point, and this
#: project's rule is that a number too weak to support a claim is withheld
#: rather than printed with a caveat nobody reads. 200 of 8,000 is 2.5%;
#: the standard error of a mean over 200 draws of an sd-9 quantity is about
#: 0.64 DK points, which is small enough to be worth printing.
MIN_CONDITIONAL_DRAWS = 200


class ConditionalityError(RuntimeError):
    """The draws cannot support a conditionality decomposition."""


def opportunity_mask(arrays: dict, layers: dict, gsis_id: str) -> np.ndarray | None:
    """Per-draw boolean: did this player record any modelled opportunity?

    `arrays` maps 'layer__metric' to the (rows, draws) matrix; `layers` maps
    layer name to its manifest entry carrying `row_ids`. Returns None when the
    player appears in no opportunity-bearing layer at all, which is a
    different thing from never taking an opportunity and must not be rendered
    as zero.
    """
    mask = None
    for layer, metrics in OPPORTUNITY_ARRAYS.items():
        spec = layers.get(layer)
        if not spec or gsis_id not in (spec.get('row_ids') or ()):
            continue
        i = list(spec['row_ids']).index(gsis_id)
        for metric in metrics:
            arr = arrays.get(f'{layer}__{metric}')
            if arr is None:
                continue
            here = np.asarray(arr[i]) > 0
            mask = here if mask is None else (mask | here)
    return mask


def decompose(values: np.ndarray, mask: np.ndarray | None) -> dict:
    """Split `values` into its unconditional and conditional readings."""
    values = np.asarray(values, dtype=float)
    if values.size == 0:
        raise ConditionalityError('no draws to decompose')
    out = {
        'n_draws': int(values.size),
        'mean_unconditional': float(values.mean()),
        'sd_unconditional': float(values.std(ddof=1)),
    }
    if mask is None:
        out.update({
            'p_any_modelled_opportunity': None,
            'mean_given_opportunity': None,
            'basis': 'NO_OPPORTUNITY_LAYER',
            'note': ('this player appears in no opportunity-bearing layer, so '
                     'participation cannot be measured from these draws. That '
                     'is not the same as never participating.'),
        })
        return out

    n = int(np.count_nonzero(mask))
    out['p_any_modelled_opportunity'] = float(n) / values.size
    out['n_draws_with_opportunity'] = n
    if n < MIN_CONDITIONAL_DRAWS:
        out.update({
            'mean_given_opportunity': None,
            'basis': 'TOO_FEW_QUALIFYING_DRAWS',
            'note': (f'{n} qualifying draws is below the floor of '
                     f'{MIN_CONDITIONAL_DRAWS}, so a conditional mean would '
                     f'be noise. Withheld rather than printed with a caveat.'),
        })
        return out

    kept = values[mask]
    out.update({
        'mean_given_opportunity': float(kept.mean()),
        'sd_given_opportunity': float(kept.std(ddof=1)),
        'basis': 'CONDITIONED_ON_ANY_MODELLED_OPPORTUNITY',
        'conditionality_ratio': (float(kept.mean() / out['mean_unconditional'])
                                 if out['mean_unconditional'] else None),
    })
    return out


def table(arrays: dict, layers: dict, value_layer: str, value_metric: str) -> list[dict]:
    """Decompose one metric for every row that carries it.

    Rows come back sorted by unconditional mean, which is the order a reader
    already expects, so the conditional column lands next to the number it
    corrects rather than re-ordering the table underneath them.
    """
    spec = layers.get(value_layer)
    if not spec:
        raise ConditionalityError(f'no layer {value_layer!r} in this artifact')
    key = f'{value_layer}__{value_metric}'
    values = arrays.get(key)
    if values is None:
        raise ConditionalityError(f'no array {key!r} in this artifact')
    rows = list(spec.get('row_ids') or ())
    if not rows:
        raise ConditionalityError(f'layer {value_layer!r} carries no row_ids')

    out = []
    for i, gsis_id in enumerate(rows):
        entry = {'gsis_id': gsis_id}
        entry.update(decompose(values[i], opportunity_mask(arrays, layers, gsis_id)))
        out.append(entry)
    out.sort(key=lambda r: -r['mean_unconditional'])
    return out


def flag_misreadable(rows, ratio_threshold: float = 1.25) -> list[dict]:
    """Rows whose unconditional mean most understates their conditional one.

    `ratio_threshold` is a REPORTING trigger, not a model parameter. It
    decides which rows carry a warning; it changes no number. It is passed
    explicitly rather than hidden so a caller can widen or narrow the warning
    without anyone mistaking it for a fitted quantity.
    """
    return [r for r in rows
            if r.get('conditionality_ratio')
            and r['conditionality_ratio'] >= ratio_threshold]
