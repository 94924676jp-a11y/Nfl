"""Does the DEALT allocation match the INTENDED one?

WHAT THIS REPLACES, AND WHY THE OLD NUMBER MEASURED NOTHING

Both `q6/forward_chain.py` and `q9b/family.py` published a column called
`recon_error`, computed as::

    recon = |multinomial(n, p).sum(axis=1) - n|

and it was exactly 0.0 on every row: 276,968 in `Q6_DIAGNOSTICS.csv.gz`,
104,130 in `Q9B_FAMILY_ROWS.csv.gz`, 4,348 in `Q9_DIAGNOSTICS.csv`.
Three hundred and eighty-five thousand rows of zero, read as "the allocator
reconciles to the team total on every draw."

It reconciles numpy. `numpy.random.multinomial(n, p)` sums to `n` by its own
contract, so the statistic restates the library's documentation once per row.
Measured on seeded violations (`test_p6_false_greens.py` P6-FG-2): handing one
player every single unit scores 0.0; deleting a player and giving his mass to
his neighbour scores 0.0. It cannot see ANY error that preserves the total,
which is every allocation error there is. The one thing it does catch is an
allocation built against a different budget than it is scored against.

This is the same shape as the defect `q7/panel.py` already wrote down: compose
`db = att + sacks + scr`, then assert `att + sacks + scr == db`, and learn
nothing except that addition works -- least of all that one of the three terms
is structurally zero.

THE REPLACEMENT

Compare what was DEALT against what was INTENDED, standardised by the sampling
noise the multinomial itself implies. For player j over `D` draws:

    intended_j = mean_d( budget_d * P[d, j] )          expected units
    dealt_j    = mean_d( T[d, j] )                     units actually dealt
    se_j       = sqrt( mean_d( budget_d * P[d,j] * (1 - P[d,j]) ) / D )
    z_j        = |dealt_j - intended_j| / se_j

and report `max_j z_j`.

NO FITTED CONSTANT. `se_j` is the multinomial's own standard error, derived
rather than chosen, and the statistic is a z-score whose null behaviour is
computable rather than asserted. Measured over 300 seeds at D=64, 5 players,
budget 30, a correct allocation gives median 1.43, p95 2.57, max 3.71. The
seeded violations above give 87.6 (all to one player) and 21.9 (a player
dropped). The separation is roughly an order of magnitude and does not rest on
a cutoff: nothing here thresholds, it reports.

WHAT IT STILL CANNOT SEE, stated so nobody reads it as more than it is:

  * It scores the allocation against the intent it was GIVEN. If `P` itself is
    wrong -- the wrong shares, from the wrong model -- dealt will match intended
    and this will read clean. Reconciliation is not validation.
  * It is a mean over draws, so a correct mean with a wrong spread passes.
  * `se_j` is zero when `P[d, j]` is 0 or 1 for every draw. A discrepancy there
    is unbounded rather than large, and is reported as `inf`, never as 0.
"""
import numpy as np

SPEC_VERSION = 'allocation_residual/1.0.0'

#: The column name the old, inert statistic was published under. Kept here so a
#: reader can search one place and find out what happened to it.
SUPERSEDED_COLUMN = 'recon_error'
SUPERSEDED_MEANING = (
    'abs(multinomial(n, p).sum() - n), which numpy guarantees is zero. '
    'Constant 0.0 on 385,446 published rows. It measured nothing.'
)


def allocation_residual_z(dealt, shares, budget):
    """Max standardised per-player deviation of DEALT from INTENDED.

    dealt   (D, J) integer units actually allocated, per draw per player
    shares  (D, J) or (J,) the intended probability each unit lands on player j
    budget  (D,) or scalar, the units available to deal on each draw

    Returns a float >= 0, or float('inf') when a player whose share leaves no
    room for sampling noise nonetheless came out different from intent.
    """
    T = np.asarray(dealt, dtype=float)
    if T.ndim != 2:
        raise ValueError(f'dealt must be (draws, players), got {T.shape}')
    D, J = T.shape
    P = np.asarray(shares, dtype=float)
    if P.ndim == 1:
        P = np.tile(P, (D, 1))
    if P.shape != T.shape:
        raise ValueError(f'shares {P.shape} does not match dealt {T.shape}')
    b = np.asarray(budget, dtype=float)
    if b.ndim == 0:
        b = np.full(D, float(b))
    if b.shape != (D,):
        raise ValueError(f'budget must be ({D},) or scalar, got {b.shape}')
    b = b[:, None]

    intended = (b * P).mean(axis=0)
    dealt_mean = T.mean(axis=0)
    gap = np.abs(dealt_mean - intended)
    var = (b * P * (1.0 - P)).mean(axis=0) / float(D)
    se = np.sqrt(np.maximum(var, 0.0))

    # A PLAYER WITH NO ROOM FOR NOISE IS NOT A PLAYER WITH NO ERROR.
    # se == 0 means P was 0 or 1 on every draw. If dealt still differs from
    # intended there, the deviation is unbounded in z units; reporting 0.0
    # would be the exact failure this module exists to end.
    airless = (se <= 0.0) & (gap > 1e-9)
    if airless.any():
        return float('inf')
    z = np.divide(gap, se, out=np.zeros_like(gap), where=se > 0.0)
    return float(z.max()) if z.size else 0.0


def null_quantiles(n_players, budget, n_draws, *, n_seeds=300, seed=0):
    """What a CORRECT allocation of this shape scores. For reporting, not gating.

    A statistic whose null behaviour is never computed is a number nobody can
    read. This makes the comparison available rather than leaving the reader to
    assume that small means good.
    """
    out = []
    for s in range(n_seeds):
        rng = np.random.default_rng(seed + s)
        P = np.full((n_draws, n_players), 1.0 / n_players)
        T = np.array([rng.multinomial(int(budget), P[d])
                      for d in range(n_draws)], dtype=float)
        out.append(allocation_residual_z(T, P, float(budget)))
    a = np.array(out, dtype=float)
    return {'median': float(np.median(a)),
            'p95': float(np.quantile(a, 0.95)),
            'max': float(a.max()),
            'n_seeds': int(n_seeds)}
