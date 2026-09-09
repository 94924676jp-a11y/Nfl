# OWN-6 — P4C simplex units rectification

**Verdict: `P4C_UNITS_FIX_NO_REFIT_REQUIRED`**

The fitted parameters never passed through the allocator, and the one parameter
whose objective *does* reference a normalisation — `alpha0` — was fitted under
**exactly the corrected contract**. The allocator is the piece that diverged from
the fit, not the other way round. **`W` did not absorb the dilution.**

**Production was not modified.** The three arms come from capturing the exact
inputs production hands `p4c_lib.allocate` and applying both contracts to the
**same captured draw**.

**A second, separate defect was found and is reported here because it makes the
Part A freeze impossible as stated: the allocation layer is not reproducible
across processes.**

---

## 0. The seed that is not a seed

`layers.targets_carries:200`

```python
rng = np.random.default_rng([seed, hash(cls) % 9973])
```

Python randomises string hashing per process and `PYTHONHASHSEED` is unset
anywhere in this repository. Measured directly — three processes, identical
inputs, identical `seed=20260908`:

| process | `hash('targets') % 9973` | share matrix sha256 | mean `other` |
|---|---|---|---|
| 1 | 1007 | `1be6827d93a5b3e2…` | 0.005328 |
| 2 | 5343 | `f0fe1e349c2d15cb…` | 0.006891 |
| 3 | 5523 | `7a5eba06dfd5e666…` | 0.004916 |

**The targets and carries allocation draw differs on every run.** Consequences:

- Part A's instruction to *freeze current target and carry outputs* cannot be
  satisfied as numbers. Only the code, the parameters and the panel hashes are
  freezable; the outputs are not.
- **Any cross-process "same seed" comparison of this layer compares RNG streams,
  not the thing under test.** Every arm in this study therefore runs in **one
  process**, which is why the design says so rather than treating it as a
  convenience.
- It violates the project's own fingerprint discipline: an experiment whose
  draw cannot be reproduced has no execution identity.

The fix is one line — a stable class key instead of `hash(cls)` — but it changes
every drawn allocation, so it is **reported, not applied**.

---

## 1. Part A — ownership and units, both simplexes

| | `targets` | `carries` |
|---|---|---|
| mode | `simplex` | `simplex` |
| modelled positions | **WR, TE, RB** | **RB only** |
| denominator | `team_targets` | `team_carries` (the pbp `rush_attempt` count) |
| `W_i A_i` | `_C` (ewma of the player's realised **share**) + a residual pool draw, clipped to [0,1] — **share scale** | same |
| `w_other` | `mass_pool` = `mall − ms`, and `mall` is 1.0 because the panel closes — **a share on [0,1]** | same |
| must sum to 1 | `Σ modelled shares + other` | `Σ modelled shares + other` |
| who owns the residual | fringe non-WR/TE/RB targets — **fitted mean 0.0113** | **an entire position group**: QB 0.1568 + WR 0.0302 + TE 0.0038 — fitted mean **0.1989** |

**Both branches share one mathematical contract, so one allocator is correct for
both.** They differ in what `other` *contains*: for targets it is a fringe
residual; for carries it is a structural block holding the quarterback, whose
rushing another layer models independently. That is a naming and ownership
problem — `other` is doing load-bearing work in the carry branch — but it is not
a reason for two allocator contracts.

**The defect.** `p4c_lib.allocate:110-113` computes
`other = w_other / (Σ(W·A) + w_other)`. `Σ(W·A)` is a sum over however many
players are in the modelled set and is **not normalised**, so a fitted share is
diluted by an arbitrary scale.

---

## 2. Part B — three arms, one draw

| arm | contract |
|---|---|
| **C0** incumbent | `S_i = W_iA_i / (ΣWA + w_other)`, `other = w_other/(ΣWA + w_other)` |
| **C1** normalisation-only, **no refit** | `S_i = (1 − w_other)·W_iA_i / ΣWA`, `other = w_other` |
| **C2** normalisation + refit | see §3 — **provably identical to C0's parameters** |

### Carries

| | C0 | **C1** | historical |
|---|---|---|---|
| mean modelled (RB) mass | 0.891489 | **0.811104** | **0.8082** |
| mean `other` mass | 0.108511 | **0.188896** | **0.1918** |
| per-team per-draw closure | exact (2.4e-07) | exact (2.1e-07) | — |
| zero-share fraction | 0.1704 | **0.1704** | — |
| player share p99 | 0.4558 | 0.4418 | — |
| per-draw ordering preserved | — | **True** | — |

**C1 lands on the historical values: RB +0.36%, `other` −1.5%.** C0 is +10.3% on
the modelled block and −43% on `other`.

### Targets

| | C0 | **C1** | fitted `mass_mean` |
|---|---|---|---|
| mean modelled mass | 0.994712 | 0.987748 | — |
| mean `other` mass | 0.005288 | **0.012252** | **0.0113** |
| closure | exact | exact | — |
| zero-share fraction | 0.2098 | **0.2098** | — |
| player share p99 | 0.1524 | 0.1522 | — |
| per-draw ordering preserved | — | **True** | — |

**The receiving simplex is diluted by the same defect** — `other` at less than
half its fitted value — but the absolute effect is **0.7 percentage points of
team targets**. C1 moves it onto the fitted mass and changes essentially nothing
else: identical zeros, p99 moves by 0.0002, ordering preserved per draw.

**C1 does not harm the receiving simplex.** It corrects it by a small amount in
the direction of its own fit.

*A correction to my own first run.* It split captures by modelled-row count and
mislabelled 7 of 8, because a game with few receivers can have fewer target rows
than another game has carry rows. The class is now captured from `gen_weights`,
which receives it, and paired by call order. The numbers above are from the
corrected run.

---

## 3. Part C — did `W` absorb the dilution? No, and the fit says so

**Static, and decisive.** The string `allocate` appears in `p4c_build.py`
**once**, in a comment. `fit_params` estimates every parameter — `add_pool`,
`lr_pool`, `sigma_lr`, `sigma_lg`, `q_zero`, `prior`, `mass_pool`, `alpha0` —
**directly from realised shares** `s_targets` / `s_carries`. There is no loss, no
optimisation and no allocator in the fitting path. A refit under C1 therefore
returns **byte-identical parameters**: the objective is allocator-independent.

**And the fit was already written to C1's contract.** `p4c_build.py:166-175`:

```python
mo = par['mass_mean']
tot = sum(x['_C'] for x in rs)
scale = (1.0 - mo) / tot          # <- exactly C1
mu = x['_C'] * scale
```

`alpha0` — the Dirichlet concentration, the one fitted quantity that references
a normalisation at all — is estimated assuming the modelled block is scaled to
**`1 − mass_mean`**. That is C1, written into the frozen fit. `allocate`
implements something else.

**Empirically consistent:** if `W` had absorbed the dilution, C1 would overshoot
the historical mass. It does not — it lands on it (0.8111 against 0.8082).

**So C2 is a formality, not an experiment**, and it is reported as one rather
than dressed up as a result.

---

## 4. Part D — rushing accounting under C1

| requirement | under C1 |
|---|---|
| team carries conserved | **yes** — closure exact per team per draw (2.1e-07, float32) |
| QB scrambles counted once | yes — drawn once in the dropback multinomial |
| QB designed runs counted once | yes — `Binom(db, dpd)`, drawn once |
| `rush_opp == scrambles + designed` | yes, by construction in `qb2_lib` |
| **QB opportunity fits its container** | **yes** — QB needs **0.1526**, C1's `other` is **0.1889**; under C0 it is 0.1085 and cannot fit |
| RB/WR/TE/OTHER coherent | residual after QB is **0.0363** against a historical WR+TE of **0.0340** |
| zero carries → zero yards | unchanged; RB rushing yards remain refused (`RUSHING_CONVERSION_CONTROL_UNDEFINED`) |
| no clipping, no silent residual | C1 adds neither |

QB rush opportunity measured **4.2445 of 27.8154 team carries = 0.1526**, against
a historical 0.1568 including kneels and 0.1333 excluding them. **This is
diagnostic evidence and was not fitted toward.** Nothing in C1 touches the QB
rush model; C1 only changes the size of the container.

**Kneels remain owned by nobody** — 0.7746 per team-game inside D1's carry
budget, modelled in no layer. Under C1 they sit inside the 0.1889 `other` mass
without being named. That is better than not fitting, and it is still not
ownership.

---

## 5. Part E — decision

### `P4C_UNITS_FIX_NO_REFIT_REQUIRED`

- The defect is real and is a units mismatch, confirmed at both ends: fitted as a
  share (`pool = mall − ms`, `mall = 1`), consumed as an unnormalised weight.
- **No refit is required.** The fitting objective never touches the allocator,
  and `alpha0` is already fitted under the corrected normalisation.
- **The repair does not harm the valid simplex.** Targets move 0.7pp toward
  their own fitted mass with identical zeros, unchanged tails and preserved
  per-draw ordering.
- **One allocator contract is correct for both branches.** They differ in what
  `other` contains, not in the arithmetic it must satisfy.

### Recommended production repair — recommended, not applied

```python
# p4c_lib.allocate, simplex branch
te    = gexp(gsum(W * A, starts), counts)
S     = (W * A) * gexp(1.0 - w_other, counts) / te
other = w_other
```

Not applied: the experiment captured production's inputs without modifying it,
so the repair is **not mechanically unavoidable**, and `p4c_lib` is a frozen P4C
module. Applying it is an owner decision. It would change every drawn
allocation in both simplexes.

**Two further items for the same decision**, both reported and neither applied:

1. **The RNG defect in §0** — the layer is not reproducible across processes.
   This is arguably more urgent than the units fix, because it makes any
   before/after evidence about the units fix unverifiable by anyone else.
2. **Kneels**, 0.7746 carries per team-game, owned by no layer.

---

## 6. Governance

No PATH_C promotion · no 2026 outcomes · no market/DFS input · no T-90 change ·
G0A **11/12** · NFL-1 **NOT AUTHORIZED** · R2 preregistered and unimplemented ·
production untouched.

## 7. Files

| File | Role |
|---|---|
| `nfl/research/own6/run_own6.py`, `own6_results.json` | the three arms, the freeze hashes, the RNG demonstration |
