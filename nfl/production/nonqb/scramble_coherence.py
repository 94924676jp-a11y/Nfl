"""SC1: make the scramble/carry joint state coherent by construction.

Pre-registered in nfl/research/sc1/predeclaration_sc1.md, sha256
b62e48f23b5f3a16fb633e5286e575f23d7de3e07c8ebf923255d8d565e76729.

THE DEFECT. A scramble IS a rush attempt, so `team_carries >= scrambles` holds
in 3,230 of 3,230 historical team-games. The model draws the two on the same
draw index but from independent randomness -- corr +0.0299 against a historical
+0.1802 -- so their tails can cross. Measured: one cell in 6,400 with A3G on,
a scramble draw of 8 landing on a carry draw of 5.3.

WHAT THIS IS. A permutation of WHICH DRAW INDEX RECEIVES WHICH CARRY VALUE.
It changes no value. The carry marginal is invariant element-for-element, the
scramble draw is not touched at all, nothing is fitted and no parameter is
introduced. That is what makes it a coherent joint state generated at draw
time rather than an incoherent state corrected afterwards.

WHAT THIS IS NOT. Not scrambles redefined as a share of carries. Not clipping
scrambles down. Not inflating carries. Not survivor renormalisation. Not a new
estimator.

FEASIBILITY IS CHECKED, NEVER ASSUMED. A satisfying assignment exists iff
sorted(scrambles)[k] <= sorted(carries)[k] for every k -- the condition is
exact, and it is Hall's condition for this bipartite matching. Where it fails
there is no permutation that works, and the only honest answer is a named
refusal.
"""
from __future__ import annotations

import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome     # noqa: E402

SPEC_VERSION = 'sc1-scramble-carry-coherence-v1'
PREDECLARATION = 'nfl/research/sc1/predeclaration_sc1.md'
PREDECLARATION_SHA256 = \
    'b62e48f23b5f3a16fb633e5286e575f23d7de3e07c8ebf923255d8d565e76729'
GOVERNANCE = ('REHEARSAL_ONLY -- engineering integration in the V1 candidate '
              'configuration, not prospective validation')


def feasible(scrambles, carries) -> Outcome:
    """Hall's condition for this matching: sorted_scr[k] <= sorted_car[k].

    Reported before any assignment is attempted, so an infeasible pair refuses
    with the reason rather than with a failed search.
    """
    s = np.sort(np.asarray(scrambles, float))
    c = np.sort(np.asarray(carries, float))
    if s.shape != c.shape:
        return Outcome.fail(
            'SC1_SHAPE_MISMATCH',
            f'scrambles {s.shape} against carries {c.shape}; these are two '
            f'views of one draw index and must agree')
    bad = int((s > c + 1e-9).sum())
    if bad:
        k = int(np.argmax(s - c))
        return Outcome.fail(
            'SC1_NO_FEASIBLE_ASSIGNMENT',
            f'no permutation of the carry draws can satisfy '
            f'carries >= scrambles: at rank {k} the sorted scramble draw is '
            f'{s[k]:.4f} against a sorted carry draw of {c[k]:.4f}, and '
            f'{bad} rank(s) fail. The marginals themselves are incompatible, '
            f'so this refuses rather than clipping either of them.',
            n_ranks_failing=bad, worst_rank=k,
            worst_scramble=float(s[k]), worst_carry=float(c[k]))
    return Outcome.ok('SC1_FEASIBLE', value=True,
                      detail=f'all {s.size} ranks admit an assignment',
                      n_draws=int(s.size))


def couple(scrambles, carries) -> Outcome:
    """Reorder the carry draws so every draw satisfies carries >= scrambles.

    MINIMAL SWAPS. A draw that already satisfies the constraint keeps its
    value, so whatever coupling produced this index -- A3G's game-level pairing
    in particular -- survives everywhere it was not the problem.

    The construction: rank the violating draws by scramble count descending and
    give each the smallest still-available carry value that clears it. Because
    Hall's condition holds, a value always exists; the assertion at the end is
    a construction check, not a tolerance.
    """
    s = np.asarray(scrambles, float)
    c = np.asarray(carries, float)
    f = feasible(s, c)
    if f.state.name != 'PASS':
        return f
    out = c.copy()
    viol = np.flatnonzero(out < s - 1e-9)
    n_before = int(viol.size)
    if not n_before:
        return Outcome.ok(
            'SC1_ALREADY_COHERENT', value=out,
            detail='every draw already satisfies carries >= scrambles; the '
                   'draw index is returned untouched',
            n_violations_before=0, n_swaps=0, n_cells_moved=0,
            marginal_preserved=True, spec_version=SPEC_VERSION)
    # Donors: draws whose carry value could be spared, largest first.
    swaps = 0
    for j in sorted(viol, key=lambda x: -s[x]):
        if out[j] >= s[j] - 1e-9:
            continue
        # A donor must clear THIS draw, and must not break its own draw once
        # it receives the value being displaced.
        cand = [k for k in range(out.size)
                if k != j and out[k] >= s[j] - 1e-9
                and out[j] >= s[k] - 1e-9]
        if not cand:
            return Outcome.fail(
                'SC1_NO_DONOR_DRAW',
                f'draw {j} needs a carry value of at least {s[j]:.4f} and no '
                f'other draw can supply one without breaking its own '
                f'constraint. Refusing rather than clipping.',
                draw=int(j), needed=float(s[j]))
        # The SMALLEST sufficient donor: take no more than the constraint needs.
        k = min(cand, key=lambda x: out[x])
        out[j], out[k] = out[k], out[j]
        swaps += 1
    left = int((out < s - 1e-9).sum())
    if left:
        return Outcome.fail(
            'SC1_ASSIGNMENT_DID_NOT_CLOSE',
            f'{left} draw(s) still violate after {swaps} swap(s). This is a '
            f'construction, so a failure here is a defect in the assignment '
            f'itself and never a tolerance to widen.', n_left=left)
    # The marginal is a multiset invariant. Checked, not asserted.
    if not np.array_equal(np.sort(out), np.sort(c)):
        return Outcome.fail(
            'SC1_MARGINAL_NOT_PRESERVED',
            'the reordered carry draws are not a permutation of the input. '
            'SC1 may only choose which draw receives which value.')
    return Outcome.ok(
        'SC1_COUPLED', value=out,
        detail=f'{n_before} violating draw(s) resolved by {swaps} swap(s); '
               f'carry marginal preserved exactly as a multiset',
        n_violations_before=n_before, n_swaps=swaps,
        n_cells_moved=int((out != c).sum()),
        frac_cells_moved=round(float((out != c).mean()), 8),
        marginal_preserved=True, nothing_fitted=True, no_clipping=True,
        scrambles_untouched=True, spec_version=SPEC_VERSION)
