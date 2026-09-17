# QBSEM pre-registration — one publication semantic across every position

**Written before implementation.** §1 measures already-frozen components against
already-realised history and fits nothing. The board is not sealed and no prior
candidate is touched: `qb_room_v2`, `appearance_r8`, R8/R9 and every registered
arm stay byte-identical. QBSEM is a **new candidate identity**.

---

## 1. Where the defect actually is, measured

### Two of my earlier framings are withdrawn first

- **"The QB room understates zero-dropback mass by a factor of 30."** That
  compared the board's 0.0039 for Josh Allen against a *pooled* rank-1 no-snap
  rate of 0.1157. Not like-for-like — the pool mixes his cell with
  (rank 1, not previous primary), whose realised zero rate is 0.6627.
- **"Wire R8's `P(appear)` into the QB room."** `qb_room_v2` already argues
  against this in its own source, with a measured example: a governing-inactive
  player (Jack Endries, TB@CIN) carried `p_app = 0.9920` through R8, so the soft
  appearance probability is **not an availability gate**. The room consumes hard
  availability through `eligibility_gate.snapshot()` → `choice_set()` instead,
  and that is correct. **The repair must not reintroduce what that module
  deliberately refuses.**

### The like-for-like number

Realised rates on the room's OWN depth-chart frame, 6,673 rows over 2,717
team-games:

| cell (rank, was_prev_primary, is_opener) | n | P(starter) | **P(db = 0)** | mean db |
|---|---|---|---|---|
| (1, 0, 0) | 252 | 0.3095 | 0.6627 | 10.794 |
| (1, 0, 1) | 90 | 1.0000 | 0.0000 | 37.556 |
| **(1, 1, 0)** | **2,290** | **0.9284** | **0.0694** | 33.578 |
| (1, 1, 1) | 70 | 1.0000 | 0.0000 | 38.057 |
| (2, 0, 0) | 2,301 | 0.0543 | 0.8057 | 2.994 |
| (2, 1, 0) | 220 | 0.6455 | 0.3091 | 23.668 |
| (3, 0, 0) | 1,192 | 0.0185 | 0.9379 | 1.051 |

**Josh Allen sits in (1, 1, 0). Realised P(db = 0) = 0.0694 on n = 2,290. The
sealed board gives 0.0039.** An eighteen-fold understatement, in his own cell,
against the room's own frame.

### The mechanism, isolated

The **starter model is well calibrated**: fitted `p_start` for that cell is
0.928197 against a realised P(starter) of 0.9284. Nothing is wrong there.

The gap is downstream. From the realised rates,

    P(relieves | not the starter, cell (1,1,0))
        = (1 - 0.9284 - 0.0694) / (1 - 0.9284) = 0.0022 / 0.0716 = 0.031

The room instead applies `p_reliever_by_rank[1] = 0.303` — a weight pooled over
all rank-1 relief behaviour — which together with `p_exit = 0.134` brings the
non-starting QB1 back into roughly **93%** of his non-starting worlds.

> **The defect: a rank-1 quarterback who does not start almost never relieves
> (3.1% realised), because the dominant reason he is not starting is that he is
> not available. The room's reliever weight does not condition on why he is not
> starting, so it returns him to the field in 93% of those worlds.**

That is a mis-specification **inside the QB world generator**, estimable from
the room's own frame, requiring no external signal.

## 2. The mechanism change — QBSEM

Replace the unconditional `p_reliever_by_rank` for a **non-starting quarterback**
with a rate conditioned on the same cell the starter scenario already uses:

    P(relieves | not the starter, cell) , estimated per starter-cell from the
    room's own frame as  (1 - P(starter|cell) - P(db=0|cell)) / (1 - P(starter|cell))

- **No new data source.** The frame, the cells and the estimator are the ones
  `qb_room_v2` already builds.
- **No threshold, no tuning knob.** A cell rate with the module's existing
  Jeffreys prior, exactly as `p_start` is estimated.
- **Cells with too few non-starting rows fall back to the existing pooled
  `p_reliever_by_rank`**, and the fallback count is reported, never silent.
- The reliever *identity* mechanism (who relieves, integer split, largest
  remainder) is **unchanged**. Only the probability that the non-starter
  returns at all is re-estimated.

Conservation is untouched by construction: `V` (team dropbacks) is an input and
`allocate_dropbacks` already raises `ALLOCATION_DOES_NOT_CLOSE` on any integer
deviation.

## 3. Acceptance — every gate must pass

1. **`P(qb volume > 0)` matches the published participation event.** For each
   QB on the board, simulated `P(db = 0)` must lie within Monte Carlo error of
   the realised rate for his cell. Reported per QB; Josh Allen's target is
   **0.0694**.
2. **Zero-primary-passer worlds are exactly zero.** In every draw with
   `db = 0`, all of `att, cmp, pyds, ptd, int, sacks, rush_opp, ryds, rtd, scr`
   and `dk_points` must be **0 at the maximum**, not the mean. (This already
   holds; it must keep holding.)
3. **Replacement inherits with exact conservation.** `sum_i db_i == V` in every
   draw, and team attempts, sacks, scrambles and rushing opportunities conserve
   against their team levels.
4. **Published QB means are unconditional over all worlds** — the mean of the
   sealed draw vector, nothing else.
5. **Conditional means may be emitted as a separate labelled diagnostic field**
   (`conditional_on_primary_passer`), never substituted for the published
   figure.
6. **Machine-checkable semantic parity.** A new tripwire asserts, for EVERY
   player on the board regardless of position, that the published mean equals
   the unconditional draw mean and that `P(volume = 0)` is consistent with the
   participation event the board declares. It must pass on QB, RB, WR, TE and K
   alike.
7. **No sportsbook or DFS information enters the repair.** Asserted by the
   existing component declaration and by inspection of the diff.

**If any gate fails, QBSEM is withdrawn** and the mixed-semantics blocker
stands, unsealed.

## 4. Then, in this order

1. Rerun the DET-BUF candidate on QBSEM.
2. Rerun the QB semantic tripwires.
3. **Contract 3 on the already-predeclared grid** — n ∈ {1000, 2000, 4000,
   8000, 16000}. **The grid is not extended and the contract is not amended**,
   whatever the result.
4. Confirming full suite.
5. Seal only if every gate passes.

## 5. A hypothesis to TEST, not to assume

Contract 3's binding quantity at 8,000 and 16,000 is **`qb/pyds` p90 for Josh
Allen** — the same player and layer this defect sits in. It is plausible that a
correctly-specified participation state settles that tail.

**It is recorded here as a hypothesis with a predeclared test:** compare the
bootstrap sd of `qb/pyds` p90 for each QB, QBSEM against GSVU, at matched draw
counts. If it does not fall, say so. **Contract 3's verdict does not depend on
this and the contract is not relaxed if the hypothesis is false.**

## 6. What would make QBSEM wrong

- **Small cells.** (1, 0, 1) has n = 90, (3, 1, 0) n = 33. The fallback exists
  for exactly this and its use is counted.
- **`P(db = 0 | cell)` conflates causes** — inactive, benched, blowout — as
  every other quantity here does. Nothing pregame separates them.
- **The frame is the one every earlier QB repair was selected on**, so this is
  **EXPLORATORY**. It controls parameter leakage, not specification leakage.
- A cell rate estimated from 2020-2025 is served in 2026 on a daily-vendor
  depth chart; `fit_for_ordinal` already records that vintage asymmetry and it
  is not repaired here.

V2 NOT YET EARNED.
