"""The executable audit behind A1: where does the model assert certainty?

WHAT IT COUNTS, AND WHY THE BAND IS DERIVED

  exactly 1.0 / exactly 0.0   the model saying an event cannot fail to happen
                              or cannot happen.
  near-boundary               a probability so extreme that, at the draw count
                              the simulator actually uses, the rare outcome is
                              expected FEWER THAN ONCE across every world.

The near-boundary band is `1 / n_draws`, not a round number somebody liked.
At 8,000 worlds that is 1.25e-4: a probability below it means the simulator
will, in expectation, never once produce the other outcome, so the difference
between it and exact certainty is invisible in everything downstream. The band
therefore comes from the sampler, and it moves if the sampler does.

WHAT THIS AUDIT DOES NOT DO

It does not clip, floor, or adjust a single probability. Its output is a
count, a list of who, and a verdict. The repair -- if one is justified -- is a
modelling decision with a number in it and belongs in a preregistration.
`ASSUMPTION_AUDIT.json` records what was found; nothing downstream reads a
changed value because of it.
"""
from __future__ import annotations

import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome          # noqa: E402

SPEC_VERSION = 'nfl-appearance-boundary-audit-1'
CODE = 'APPEARANCE_PROBABILITY_AT_BOUNDARY'


def band(n_draws: int) -> float:
    """The width below which certainty is indistinguishable from certainty.

    One expected occurrence across the whole simulation. Derived from the
    sampler, never chosen.
    """
    if n_draws <= 0:
        raise ValueError('n_draws must be positive')
    return 1.0 / float(n_draws)


def audit(p_appears: dict, *, n_draws: int, label='appearance') -> Outcome:
    """`p_appears`: key -> probability. Counts, lists, and refuses to repair."""
    if not p_appears:
        return Outcome.fail(
            'APPEARANCE_AUDIT_EMPTY',
            f'{label}: no probabilities supplied. An empty audit is not a '
            f'clean audit.', cause=Cause.DATA)
    eps = band(n_draws)
    at_one, at_zero, near_one, near_zero, out_of_range = [], [], [], [], []
    for k, v in p_appears.items():
        p = float(v)
        if p < 0.0 or p > 1.0:
            out_of_range.append({'key': str(k), 'p': p})
            continue
        if p >= 1.0:
            at_one.append(str(k))
        elif p <= 0.0:
            at_zero.append(str(k))
        elif p > 1.0 - eps:
            near_one.append({'key': str(k), 'p': p})
        elif p < eps:
            near_zero.append({'key': str(k), 'p': p})
    n = len(p_appears)
    n_boundary = (len(at_one) + len(at_zero)
                  + len(near_one) + len(near_zero))
    ev = {'spec_version': SPEC_VERSION, 'label': label, 'n_draws': n_draws,
          'band': eps,
          'band_is_derived': ('1 / n_draws: the probability below which the '
                              'other outcome is expected fewer than once '
                              'across every simulated world'),
          'n_rows': n,
          'n_exactly_one': len(at_one), 'n_exactly_zero': len(at_zero),
          'n_near_one': len(near_one), 'n_near_zero': len(near_zero),
          'n_at_or_near_boundary': n_boundary,
          'share_at_or_near_boundary': n_boundary / n,
          'exactly_one': sorted(at_one)[:50],
          'exactly_zero': sorted(at_zero)[:50],
          'near_one': near_one[:50], 'near_zero': near_zero[:50],
          'out_of_range': out_of_range,
          'nothing_is_clipped': (
              'this audit counts and lists. It does not floor, clip or adjust '
              'a probability. A floor is a modelling decision with a number '
              'in it and belongs in a preregistration.')}
    if out_of_range:
        return Outcome.fail(
            'APPEARANCE_PROBABILITY_OUT_OF_RANGE',
            f'{label}: {len(out_of_range)} value(s) outside [0, 1]. That is '
            f'not a boundary case, it is an arithmetic error.',
            cause=Cause.DATA, **ev)
    if n_boundary:
        return Outcome.fail(
            CODE,
            f'{label}: {n_boundary} of {n} row(s) assert certainty — '
            f'{len(at_one)} at exactly 1.0, {len(at_zero)} at exactly 0.0, '
            f'{len(near_one)} within {eps:.2e} of 1 and {len(near_zero)} '
            f'within {eps:.2e} of 0. The model output is NOT modified by this '
            f'finding.', cause=Cause.DATA, **ev)
    return Outcome.ok(
        'APPEARANCE_PROBABILITIES_INTERIOR', value=sorted(p_appears),
        detail=f'{label}: {n} row(s), none at or within {eps:.2e} of a '
               f'boundary', **ev)
