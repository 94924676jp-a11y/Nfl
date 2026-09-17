# Guard-to-publication certification — the guard must certify what ships

**Pre-registered before implementation.** `joint.py` is not wired and is not
rewritten. All work is in `draw_coherence.py`, the layer that is actually wired
— 699 lines, 7 non-test importers.

## 1. The failure class, named by the repository itself

Commit `8c81079`, the most recent change to `draw_coherence.py`, is titled:

> **"The guard ran, then the values it guarded were overwritten."**

That is the mechanism. Not a missing guard — an **order-of-operations gap
between certification and publication**. A conservation suite that runs before
the last mutation of the data it certifies is not a conservation suite; it is a
statement about an intermediate state that nobody ships.

Every accounting check can pass and the published board still be incoherent,
and no existing assertion can see it, because each one looks at the array *at
the moment it runs*.

## 2. The certification boundary

```
   ... engine stages ...
        |
        v
   HARD coherence guards run          <-- certification point
        |
        +--> for every guarded array:  sha256(C-contiguous float64 bytes)
        |    recorded in the forecast artifact as `coherence_certificate`
        v
   ... any remaining stages ...        <-- the gap where 8c81079 lived
        |
        v
   PUBLICATION / SEAL                  <-- verification point
        |
        +--> re-hash every certified array and compare
        |
        +--> any mismatch: BLOCKED, cause GOVERNANCE,
             code COHERENCE_CERTIFICATE_BROKEN,
             naming the array, both digests, and the guard that certified it
```

**The certificate is data, not a promise.** It goes in the artifact, so a reader
of a sealed board can re-verify it without re-running the engine.

## 3. What is hashed, and how

- **Scope: every array a HARD guard reads.** Derived from the guards'
  own declared inputs, never a hand-written list — the same reasoning
  `draw_coherence.py` already applies when it derives `COUNT_ARRAYS` from
  `metrics.SUPPORTED` rather than hardcoding a tuple, because a hand-written
  tuple goes stale.
- **Digest:** `sha256` over `np.ascontiguousarray(a, dtype=np.float64).tobytes()`
  plus the shape and the row-id list. Dtype and contiguity are pinned because
  the same numbers in a different memory layout hash differently and that would
  be a false alarm; the row ids are in because a permutation that preserves the
  bytes but changes whose row is whose is a real defect.
- **`-0.0` is normalised to `0.0`** before hashing. It is bitwise distinct from
  `0.0` and numerically identical, so leaving it would produce a mismatch that
  is not a mutation.
- **NaN:** there should be none; if one is present the certificate records its
  count, because two NaNs never compare equal and a silent hash difference must
  not be the way we learn about it.

## 4. Relationship to `verify_seal()`

`product/evaluator.verify_seal()` already refuses to score unless every sealed
file still hashes to its seal-time value. **That is preserved unchanged.**

The two protect different intervals and neither replaces the other:

| protection | interval | catches |
|---|---|---|
| `coherence_certificate` (new) | **guard → publication** | a downstream engine stage overwriting a certified array |
| `verify_seal` (existing) | **publication → scoring** | a sealed file edited after the outcome was known |

Together they close the path from the last guard to the graded score.

## 5. The adversarial tests

Every one must produce a **refusal**, never a silent correction. Evaluated
through `draw_coherence.py`.

| # | injected condition | required outcome |
|---|---|---|
| **1** | **guard passes, then a downstream stage mutates one certified cell** | **`BLOCKED`, `COHERENCE_CERTIFICATE_BROKEN`, naming the array and both digests** |
| 2 | player carries exceed team carries by 1 in a single draw | `FAIL`, HARD, naming team, draw index, magnitude |
| 3 | player targets exceed team targets in one cell | `FAIL`, HARD |
| 4 | team total positive, every eligible player row zero | **`FAIL`** — not PASS-with-a-residual. This is the unattributed-mass case `joint.reconcile_team_total` returns `ok` on |
| 5 | `receptions > targets` in one cell | `FAIL`, HARD, **no clip applied** |
| 6 | a **negative yardage** cell injected | **`PASS`, explicitly** — guarding the declared invariant against a future clip |
| 7 | a **negative count** cell injected | `FAIL`, HARD — 6 and 7 together are the whole point |
| 8 | an unnamed / unresolved row given non-zero opportunity | `FAIL`, HARD, naming the row |
| 9 | an officially inactive player given non-zero opportunity | `FAIL`, HARD, extended beyond QBs |
| 10 | the same board run twice, same seed | byte-identical draw artifact |

**Test 1 is the one that matters** and is the reason this document exists. Tests
6 and 7 must be written as a pair or the suite will eventually "fix" the
negative-yardage invariant by clipping it: `draw_coherence.py:44-54` records
2,261 negative `qb/pyds`, 2,821 `qb/ryds` and 8,213 `receiving/receiving_yards`
cells as **lawful**, and states that `pyds >= 0`, `pyds >= -k` and any clip are
refused — only a negative **count** is impossible.

## 6. What this does not do

It does not make the board coherent. It makes the certificate **honest** — if a
stage mutates a certified array, publication refuses instead of shipping a
board whose guard report describes a different set of numbers.

**V2 NOT YET EARNED**
