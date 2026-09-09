# J1 downstream — what restoring team-level dependence changed, and what it exposed

Full football engine, real 2026 week-1 slate, 16 games, 400 draws, TEST_ONLY
appearance stand-in, identical seeds in both modes. **EXPLORATORY**; nothing
promoted, no 2026 outcome consumed, `PATH_C_STATE` untouched.

The owner's instruction was not to stop at "A3 integrates successfully". It does
integrate. The useful result is what it revealed.

---

## 1. Intended dependence recovery — it worked

| quantity | independent | **A3** | historical |
|---|---|---|---|
| team carries ↔ dropbacks | +0.0017 | **−0.3732** | **−0.393** |
| team carries ↔ targets | +0.0022 | **−0.3521** | **−0.388** |

Both recovered to within 0.02–0.04 of the historical value, through the full
non-linear composition rather than merely at the team layer.

## 2. Harmless distributional movement — the marginals held

The owner warned that unchanged team marginals need not imply unchanged player
distributions. Checked, and they did hold:

| | independent | A3 | relative |
|---|---|---|---|
| mean targets | 1.1693 | 1.1596 | −0.8% |
| mean receiving yards | 8.5729 | 8.5070 | −0.8% |
| p90 receiving yards | 22.75 | 22.62 | −0.6% |
| **p99 receiving yards** | 49.83 | 49.78 | **−0.1%** |
| mean carries | 3.6259 | 3.7008 | +2.1% |
| mean receiving TD | 0.0553 | 0.0545 | −1.6% |
| mean rushing TD | 0.1162 | 0.1191 | +2.5% |
| team receiving yards, mean | 214.59 | 212.94 | −0.8% |
| team receiving yards, sd | 77.42 | 76.90 | −0.7% |

Everything moves by ≤2.5%, and the far tail (p99) is the least disturbed of all.
Accounting is unchanged: receiving reconciles 16/16 in both modes, the cell
count is identical, and negative-yard cells are 228 against 227.

## 3. Newly exposed structural defects — the actual result

Restoring one dependence made it possible to see that **almost every other
dependence in the simulator is missing or badly understated**. Benchmarks
measured on 3,230 historical team-games:

| dependence | simulator (A3) | historical | status |
|---|---|---|---|
| **team passing TD ↔ team receiving TD** | **+0.055** | **1.000000**, exact in **3,230 of 3,230** | **broken** |
| team passing yards ↔ team receiving yards | +0.334 | **0.9996**, mean \|diff\| **0.26 yd** | **broken** |
| opposing teams' carries | +0.0009 | **−0.535** | **absent** |
| opposing teams' snaps | +0.0123 | **−0.464** | **absent** |
| RB carries ↔ his own targets | +0.053 | **+0.308** | understated 5.8× |
| competing receivers' targets | +0.207 | **+0.584** | understated 2.8× |
| competing receivers' yards | +0.058 | +0.126 | understated 2.2× |

### 3a. The worst of them, and a third dormant guard

**Team passing yards and team receiving yards are the same football quantity.**
A completed pass adds identical yardage to both columns. Measured: correlation
**0.9996**, mean absolute difference **0.26 yards**, exact agreement in 3,154 of
3,230 team-games — the residue being the lateral exception this repository
already names. For touchdowns the identity is **exact in 3,230 of 3,230** with
no exception at all.

The simulator draws them in two independent layers. Fed to
`qb_accounting.reconcile_cross_layer` for the first time:

```
ARI  FAIL[PASSING_TD_RECEIVING_TD_MISMATCH]  yards: 200/200 draws violate
     team passing yards 251.1   mean |passing - receiving| 116.3   worst 781.4
     passing TD != receiving TD in 188 of 200 draws
LAC  FAIL  103.6 mean residual on 221.8 passing yards; TD mismatch 180/200
ATL  FAIL   88.8 mean residual on 211.8 passing yards; TD mismatch 178/200
PIT  FAIL  106.9 mean residual on 237.9 passing yards; TD mismatch 198/200
```

Across the whole slate — 32 teams, 6,400 team-draws:

| | |
|---|---|
| team-checks failing | **32 of 32** |
| mean \|passing − receiving\| | **98.3 yards** |
| mean team passing yards | 221.7 |
| **residual as a share of the quantity** | **44.3%** |
| reproduced correlation | **+0.018** |
| touchdown identity violated | **5,949 of 6,400 draws (93.0%)** |

The two estimates of one quantity differ by **44% of the quantity**, in
**every draw**, and the touchdown identity — which has no exception — fails in
93% of them.

**`reconcile_cross_layer` has been written, correct and `DEFERRED` since R3
because no caller ever supplied it the receiving draws.** They were in the same
run all along. This is the **third** dormant guard found in this project, after
`assert_batch_games_are_new` and `reconcile_team`'s rush check. It is now fed.

One honest note on how it was fed: the guard enforces row alignment while
comparing team totals, and a QB room and a receiver room have different row
counts. The call sums each side to `(1, m)` first, which is mathematically
identical to the `py.sum(0) - ry.sum(0)` the guard itself computes. **The guard
was not loosened.**

### 3b. What A3 did and did not do here

A3 moved passing↔receiving yards from **+0.005 to +0.334** — a real improvement,
because both layers now inherit the same team dropback and target draws. It gets
nowhere near **0.9996**, because the two layers still draw the shared quantity
independently. A3 is a partial mitigation of a defect that needs its own fix.

### 3c. Opposing-team dependence is untouched, and A3 could not have touched it

`corr(A carries, B carries) = −0.535` and `corr(A snaps, B snaps) = −0.464`
historically: the two teams of a game split a finite play budget. D1 draws each
team independently, and A3 couples **metrics within a team**, so this is
structurally out of its reach. The simulator reproduces +0.001 and +0.012.

## 4. Estimator defects and composition failures

None found. Every difference above is a **missing dependence**, not a
mis-estimated marginal: no marginal moved more than 2.5%, no accounting rate
worsened, and no arm required clipping. The composition is doing what it was
built to do; it was built on inputs that did not carry the structure.

## 5. Ranking of what this exposes

1. **Cross-layer passing ↔ receiving.** An exact identity, violated in ~100% of
   draws by ~45% of the quantity, with a written guard already waiting. Largest
   and cheapest to attack.
2. **Opposing-team dependence.** −0.535 and −0.464 reproduced as ≈0. Requires a
   game-level play-budget object that does not exist.
3. **Within-team player dependence.** RB carries↔targets understated 5.8×,
   competing receivers 2.8×.

That ordering supersedes P5A rectification and QB3b, which remain queued.

## 6. Recommendation on A3 itself

Keep it on in rehearsal. It recovers what it was designed to recover, costs
nothing in the marginals or the tails, and — the reason it earns its place —
made three larger defects visible and measurable. It remains `joint_residuals`,
defaulting off in production, pending an owner ruling.
