# Contract 2 — result. It does not clear either, and the reason is mine.

Sweep on `V1_CANDIDATE_R9_W1P_GA`, DET at BUF, five draw counts. Contract 2
is applied exactly as written and is **not amended**. Contract 1 and its
result remain preserved and still failed.

## The decision

**No draw count on the grid clears contract 2.** The binding quantity at
16,000 is `rushing/rushing_yards@00-0039364.p90` — Sione Vaki — in
**class D, continuous quantiles**.

| n | checked | failing | A_mean | B_prob | C_discrete_q | D_cont_q |
|---|---|---|---|---|---|---|
| 1,000 | 1,694 | 979 | 302 | 161 | 183 | 333 |
| 2,000 | 1,682 | 758 | 232 | 83 | 120 | 323 |
| 4,000 | 1,618 | 337 | 10 | 6 | 73 | 248 |
| 8,000 | 1,602 | 218 | **0** | **0** | 53 | 165 |
| 16,000 | 1,590 | 157 | **0** | **0** | 38 | 119 |

## What worked, and it is the part that was diagnosed correctly

**Class A clears at 8,000 and stays clear.** Rescaling the mean tolerance
from the quantity's *level* to its own *dispersion* was the right repair:
302 failures at 1,000 fall to 0 at 8,000, where contract 1 still had 51
failing means at the same draw count.

**Class B clears at 8,000**, as it did under contract 1.

## What is still wrong, and it is the same mistake I had just diagnosed

Class D carried contract 1's rule over unchanged, on my claim that continuous
quantiles "were never the problem". **Contract 1's data did not establish
that** — a harder failure, the discrete quantiles, was masking it, and I
asserted it anyway.

The arithmetic is identical to the error I had just fixed for means:

- Sione Vaki's rushing yards: p25 = 0, p75 = 2, so **IQR = 2.0 yards**.
- Tolerance = 0.02 × 2.0 = **0.04 yards**.
- His p90 is about **25 yards**, with an MCSE of **0.48** across 20 batches
  (values 22.0 … 29.0).

Asking a 25-yard p90 to be pinned to a twenty-fifth of a yard is not a Monte
Carlo requirement, it is an impossible one. A low-usage player's IQR collapses
toward zero for exactly the same reason his mean does — most of his draws are
zero — so scaling to it reproduces the defect in a new place.

Class C (discrete quantiles, batch agreement) is improving with n — 183 → 38
— and is a sound instrument; it simply has not reached 19-of-20 for every
row on this grid.

## The production draw count

**Contract 2 does not select one, so none is claimed as contract-selected.**

The Thursday board is produced at **8,000 draws**, which is the smallest n at
which **every class whose rule is sound — A and B — clears**. That is a
narrower statement than convergence and is labelled as such wherever the board
is published:

> Means and probabilities meet a predeclared bar at 8,000. The two quantile
> classes do not, and no draw count on this grid makes them.

## What a contract 3 would have to fix, if one is written

Recorded now, applied to nothing:

1. **A quantile tolerance cannot be scaled to a spread that collapses.** Both
   the mean rule and the quantile rule failed this way. The fix that worked
   for means — scale to the quantity's own sd — is the obvious candidate, and
   it must be tested against the low-usage tail *before* being adopted, not
   asserted the way class D was.
2. **Publish fewer quantiles for a player whose distribution is mostly zero.**
   A p90 for a back with a 2-yard IQR may not be a quantity the board should
   carry at all; "we do not publish a stable p90 for him" is a legitimate
   answer and is cheaper than 110,000 draws.
3. Two contracts have now failed on the tail of the roster and not on the
   headline players. That is the pattern, and a third contract written
   without addressing it will fail the same way.
