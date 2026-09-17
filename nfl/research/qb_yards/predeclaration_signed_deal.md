# QB passing yards: a signed integer allocation. Math first, no code.

**Pre-registered. Nothing is implemented.** Contract 3 untouched. No existing
candidate altered. This will take a new candidate identity when it is built.

## 1. The defect, exactly

`football_engine.credit_passing_line`:

```python
pyds_q = np.where(Ki > 0, cmp_q / denom * Y, 0.0)
```

A quarterback's passing yards are a **continuous share of a team total**.
Measured: `qb/pyds` non-integer in 5,594 of 32,000 cells (17.48%), `qb/ryds` in
5,760 of 32,000 (18.00%), fractional parts equal to the `k/n` completion-share
denominators. `draw_coherence.py` independently reports 22.75% over a different
corpus; both stand.

## 2. Why a multivariate hypergeometric is the WRONG family

The recommendation to use an MVHG deal must not be taken literally.

**An MVHG is a distribution over non-negative integer counts drawn without
replacement from an urn of non-negative category sizes.** `Y`, the team's
passing yards in a draw, is a **signed** integer: the repository carries 2,261
lawful negative `qb/pyds` cells. There is no urn with −7 balls in it.

Applying a non-negative family to a signed total would either raise on negative
input or be "fixed" by clipping, and a clip breaks the **HARD**
`qb_cross_layer_reconciliation`, which asserts team passing yards **equals**
player receiving yards — and those are lawfully negative. **The clip is the
failure mode, not the fallback.**

## 3. The correct construction: deal the COMPLETIONS, not the yards

The generative truth is that `Y` is not a quantity to be divided. It is already
a **sum of per-completion yardages**:

```
Y  =  y_(1) + y_(2) + ... + y_(K)        K = team completions
```

each `y_(j)` an integer, any of them possibly negative. So:

> **Partition the multiset of K completion-yardages into blocks of sizes
> `cmp_1 ... cmp_n`, and give quarterback i the sum of his block.**

This is sampling without replacement — a random partition of a labelled
multiset into blocks of declared sizes — and every property falls out of the
construction rather than being asserted:

| requirement | how it holds |
|---|---|
| `sum_i pyds_i == Y` exactly, per draw | the blocks partition the multiset; a partition's block sums total the whole |
| `pyds_i` integer | a sum of integers |
| **signed totals lawful** | no step assumes a sign anywhere |
| `cmp_i == 0` ⟹ `pyds_i == 0` | an empty block sums to 0 **by definition**, not by a `np.where` |
| deterministic under fixed seed | the permutation is drawn from the run's seeded generator |
| no clipping | nothing is compared to zero at any point |

The completion counts `cmp_i` are **already** dealt by a hypergeometric in
`credit_passing_line` — that part is correct and is unchanged. The repair is to
stop dividing `Y` and start distributing the **atoms that sum to it**.

**Implementation shape:** draw one permutation of the K atom indices, take the
first `cmp_1` for QB 1, the next `cmp_2` for QB 2, and so on. Equivalent to the
partition above and O(K log K).

## 4. The one thing that must be checked before any code

**The atoms are currently thrown away.** `layers.receiving_conversion` (RC1)
draws *per-catch* yardages — its docstring says "per-catch yardage RESAMPLED"
and warns that multiplying receptions by a fixed yards-per-reception "collapses
a distribution whose tail a Normal already understates thirteenfold" — but it
returns only `receiving_yards` **summed per receiver**, and
`football_engine.py:1663` forms `Y` as `receiving_yards[ri].sum(0)`.

So the preferred construction needs **one additive plumbing change**: RC1
returns its per-catch atom vector alongside the existing totals. **It does not
change RC1's distribution, its shrinkage, or any existing return value.** That
change must be verified as additive before the deal is built on it.

## 5. Fallback, if the atoms cannot be exposed

**Largest-remainder (Hamilton) apportionment of the signed total**, the same
idiom `qb_room_v2` already uses for post-exit dropbacks:

```
w_i   = cmp_i / K
base_i = floor(w_i * Y)                   # floor toward -inf, signed-safe
R      = Y - sum_i base_i                 # 0 <= R < n, an integer
        distribute the R remaining units by descending fractional part
```

Exact, integer, signed-safe, deterministic. **It is strictly worse** than §3 and
is recorded as a fallback rather than a choice: it has no per-completion
variance, so two quarterbacks with equal completion shares receive
near-proportional yards in every draw, whereas in football they do not. §3
reproduces that variance for free because it is the real mechanism.

## 6. Acceptance gates, pre-registered

1. `sum_i pyds_i == Y` **exactly**, integer comparison, in every draw of every
   team — not within a tolerance.
2. `qb_cross_layer_reconciliation` still passes: team passing yards **equals**
   player receiving yards.
3. **A lawful negative `Y` is dealt without error and without clipping**, and at
   least one arm is tested on a synthetic negative-total draw.
4. `pyds_i == 0` wherever `cmp_i == 0`, at the maximum, not the mean.
5. Byte-identical output under a fixed seed across two runs.
6. Every existing sealed artifact unchanged.
7. `qb/pyds` becomes **100% integer**, which moves it into Contract 4's discrete
   class — a consequence recorded in advance, not discovered afterwards.

## 7. What is not claimed

That integer yards forecast better. This repairs the **support** of a quantity
whose realised values are integers. Whether it improves a proper score is a
separate, out-of-sample question, and §6 contains no such gate.

**V2 NOT YET EARNED**
