# QY1: passing yards dealt as a partition. Result.

**Arm:** `V1_CANDIDATE_R9_W1P_GSVUCY` (GSVUC + QY1). **Not promoted.**
**Control:** `V1_CANDIDATE_R9_W1P_GSVUC` (CS1), unchanged, not edited.
**Fixture:** 2026 week 2, DET at BUF, `written_at 2026-09-16T15:45:14Z`,
seed 20260908, 1,000 draws, both arms run **sequentially on the same machine**.
Pre-registration: `nfl/research/qb_yards/predeclaration_signed_deal.md`.

## Read this first: the arms were run twice and the first pair was discarded

The first pair was run **in parallel**, and they did not match. The incumbent
run's appearance layer returned `NOT_APPLICABLE[R8_K_NOT_ESTIMABLE]` and the
QY1 run's did not, so the two runs executed different sets of layers and
produced 34 arrays against 54. Any difference measured across that pair is a
difference between two pipelines, not between two yardage schemes. It is
recorded here rather than deleted, and **no number in this file comes from
it.** The sequential pair below produced 54 arrays in both arms.

## The treatment is isolated, and that is measured, not asserted

Of the **54 draw arrays** the two arms emit, **52 are byte-identical**
(sha256, from each run's own manifest). Exactly two differ:

| array | differs | why |
|---|---|---|
| `qb/pyds` | yes | the treatment |
| `dk_scoring/dk_points` | yes | a weighted sum that contains `qb/pyds` |

`qb/cmp`, `qb/ptd`, `qb/att` and `qb/ryds` are **bit-for-bit identical**
across the arms. That is the separate-stream design working: the partition's
permutation draws from its own generator (`0xC302`), so the completion and
touchdown hypergeometrics consume exactly what they consumed before. An arm
comparison here measures the yardage scheme and nothing else.

Rows are joined on **`gsis_id` from each run's own manifest**, never on board
order.

## Gate by gate

| # | gate | verdict |
|---|---|---|
| 1 | `sum_i pyds_i == Y` exactly, every draw | **HOLDS** — see closure below |
| 2 | `qb_cross_layer_reconciliation` still passes | **NOT_EXECUTED** — see below |
| 3 | a negative total dealt without error or clip | **HOLDS** |
| 4 | `cmp_i == 0` ⟹ `pyds_i == 0` at the MAXIMUM | **HOLDS** |
| 5 | byte-identical under a fixed seed | **HOLDS** |
| 6 | every existing sealed artifact unchanged | **HOLDS** — none rewritten |
| 7 | `qb/pyds` becomes 100% integer | **HOLDS** |

### Gate 7 — the support

| metric | incumbent | QY1 |
|---|---|---|
| `qb/pyds` non-integer | **678 / 4,000 (16.95%)** | **0 / 4,000 (0.00%)** |
| `qb/ryds` non-integer | 741 / 4,000 (18.52%) | 741 / 4,000 (18.52%) |
| `qb/cmp` non-integer | 0 | 0 |

`qb/ryds` is **unchanged on purpose**. It is not the same defect: it is
`rush_opp * ypr` at `nfl/research/qb2/qb2_lib.py:690`, an integer count times a
per-GAME yards-per-rush rate, with no team total and no share anywhere in it.
An earlier version of `nfl/product/support_kinds.py` gave both the name
`QB_YARDS_CONTINUOUS_SHARE`, which would have let this arm appear to repair a
quantity it never touches. The table now separates
`QB_YARDS_CONTINUOUS_SHARE` (repaired by QY1) from
`QB_RUSH_YARDS_RATE_PRODUCT` (**no repair written, none pre-registered**), and
the claim that `dk_scoring/dk_points` returns to its lattice under QY1 is
**WITHDRAWN** — it carries both defects and QY1 closes one.

### Gates 1 and 4 — the closure, per team, over 1,000 draws

Sum of the team's QB passing yards against the sum of its receivers'
receiving yards:

| arm | team | exact draws | largest residual |
|---|---|---|---|
| incumbent | BUF | 976 / 1,000 | 5.684e-14 |
| incumbent | DET | 973 / 1,000 | 5.684e-14 |
| **QY1** | BUF | **1,000 / 1,000** | **0** |
| **QY1** | DET | **1,000 / 1,000** | **0** |

**Say this accurately.** The incumbent's residual is floating-point noise from
the share multiplication, not a football discrepancy — 5.7e-14 of a yard. The
improvement is in KIND, not in magnitude: the partition closes **exactly, in
integers**, where the share closed to within a rounding error. Anyone quoting
"976 → 1,000" without the residual column is overstating it.

Gate 4 at the maximum, not the mean: across the 1,630 QB-draw cells with zero
completions, `max |pyds| = 0.0` exactly, in every one.

### Gate 3 — signed, and not clipped

Two of the four quarterbacks carry negative passing-yard cells under QY1
(minimum −1 and −3 yards). Nothing was clipped; the construction never
compares a value to zero.

### Per quarterback

| gsis_id | incumbent mean | QY1 mean | QY1 sd | QY1 non-integer | QY1 min | zero-cmp cells |
|---|---|---|---|---|---|---|
| 00-0034577 | 24.7126 | 25.2700 | 69.8867 | 0 | −1.0 | 772 |
| 00-0034857 | 221.0044 | 220.4470 | 102.9681 | 0 | 0.0 | 46 |
| 00-0033106 | 243.2857 | 243.3190 | 105.1032 | 0 | 0.0 | 53 |
| 00-0033949 | 24.1233 | 24.0900 | 66.6707 | 0 | −3.0 | 759 |

The means move by well under a yard and the direction is not consistent. That
is expected: the partition and the share have the same expectation
conditional on the completion counts, and the visible difference is the
per-completion variance the partition reproduces and the share cannot. **No
claim is made that this forecasts better.** Pre-registration §7 said so before
the arm ran and nothing here changes it.

## Gate 2 did not run, and is not counted as passed

`qb_cross_layer_reconciliation` is a HARD invariant and returns
`DEFERRED[CROSS_LAYER_RECONCILIATION_NOT_RUN]` on **every board, both arms**,
because `run_forecast` passes `receiving=fx.get('receiving_yard_draws')` and
nothing ever sets that key. The closure table above is the same quantity
measured directly off the draw arrays — a real measurement, but **not** the
governed invariant, and it gates nothing. Recorded in
`nfl/research/qb_yards/OWED_cross_layer_wiring.md`.

## Both arms REFUSED at seal, for a reason that is not QY1

`artifact_sealing: HARD_INVARIANT_FAILED: current_season_input_freshness`.
That is the freshness gate doing its job on a stale input, it applies to both
arms identically, and it is upstream of everything here. The draws are written
before sealing, which is why this comparison exists at all.

## What this does not establish

Nothing about forecast quality. One fixture, one week, four quarterbacks. This
repairs the SUPPORT of a quantity whose realised values are integers and
closes a team identity exactly instead of approximately. Whether it improves a
proper score is an out-of-sample question that no gate here asks.

**V2 NOT YET EARNED**
