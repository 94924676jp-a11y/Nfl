# P3 -- QB rush accounting and composition

Repair 4. Owner P3. Written 2026-09-15. Nothing here is a wager, a promotion,
or a prospective result.

---

## 0. What was wrong, in one paragraph

The product gate `RUSH_ACCOUNTING_FAILURE` fired on both clubs of
`2026_01_DEN_KC` because the named rush owners -- the modelled running backs
plus the quarterbacks' rushing opportunity -- were dealt more carries than the
team's own carry level. **It was not A1's multinomial.** It was the
COMPOSITION around it: three steps at the `run_forecast` call site, each
defensible on its own, whose order and arguments left the constraint
unenforceable. The repair changes the composition, introduces no constant,
refits nothing, and clips, truncates, renormalises and deletes nothing.

---

## 1. The reproduction, DECOMPOSED, before any change

`python3.12 nfl/research/v4/p3/p3_measure.py <board_dir>`, run against the
sealed R9 board `96954efc523bd7d3` (2026_01_DEN_KC, cutoff
2026-09-14T23:27:47Z, 1,000 draws). Gate tolerance is 0.5 carries.

| series | DEN | KC |
|---|---|---|
| **RB carries only** vs level | 0/1000 over the gate, 2 draws positive, max **+0.2619** | 0/1000 over, 2 positive, max **+0.0854** |
| **QB rush opportunity only** vs level | 0/1000 over, 0 positive, max −4.8852 | **1/1000 over**, 1 positive, max **+0.6915** |
| **RB + QB rush opportunity** vs level | **149/1000 over**, 206 positive, max **+6.1219** | **148/1000 over**, 237 positive, max **+9.6915** |

**The multinomial running-back deal is sound.** The impossibility enters with
the quarterback. A single undecomposed check is what aimed an earlier repair at
the RB deal; the two halves are reported separately from here on and never
their sum alone.

Reproduced a second time on a fresh R9 build of the same game at the same
cutoff with the same seed (`97473fb9d7a71042`, built 2026-09-15): every figure
above is identical to the cell.

### The two answers for designed QB runs

| | A1 `rush_category.designed_qb` | QB layer `rush_opp − scr` | cells disagreeing |
|---|--:|--:|--:|
| DEN | 2.2960 | 1.6270 | **814 / 1000**, per draw −6 to +15 |
| KC | 0.7090 | 0.6150 | **528 / 1000**, per draw −10 to +11 |

### The category partition -- and a correction to the reported figure

The brief and `AUTOPSY_DEN_KC.md` §5.2 record `Σ rush_category` against
`team_carries` at max |difference| **8.4278** (DEN) and **10.2027** (KC), and
say this contradicts an earlier report that unowned category mass is
identically zero. **Measured, the earlier report is the one that is right, and
the 8.4278 / 10.2027 comparison is mis-specified.**

A1's declared ownership graph subtracts the scrambles from the level BEFORE
partitioning -- they are dropback-owned and are not one of the six categories
-- and it partitions the INTEGERISED level. The partition A1 actually claims is

    Σ rush_category + scrambles == rint(team_carries)

and on the sealed board that closes **exactly**: max |difference| **0.000000**,
**0 of 1,000 cells open**, on both clubs. The 8.4278 and 10.2027 are almost
exactly the mean scramble counts (2.4080 and 2.8430) plus their spread; they
measure the omitted term, not a non-closure. The `rb` category also splits
exactly into the named backs plus the unmodelled-back pool: max |difference|
**0.0000** on both clubs.

So item 3 of the brief -- "close the category partition" -- needed no closing.
What it needed was for the identity to be **asserted in its correct form**,
which nothing did. It is now asserted per draw inside
`rushing_a1.compose_rush_ownership` and refused by name
(`A1_COMPOSE_PARTITION_DOES_NOT_CLOSE`) if it ever opens.

### Failing tests first

`nfl/tests/test_p3_rush_accounting.py` was written before the repair and run.
Result: **15 passed, 6 failed**. The 15 are the reproduction -- both
decomposed halves on the sealed cohort, and the same breach reproduced on
synthetic inputs with no board involved. The 6 failures are the repair tests,
every one of them `rushing_a1 exposes compose_rush_ownership -- absent`.

---

## 2. The three causes, and where each lived

None is in `rushing_a1.allocate`'s estimator. All three are composition.

1. **SC1's bound was too weak.** `run_forecast` coupled the carry level
   against the SCRAMBLES. A designed quarterback run is a team carry exactly
   as a scramble is, so `rush_opp > team_carries` stayed reachable -- 1 of
   1,000 KC draws.
2. **Two owners for one quantity.** `allocate` was called without
   `qb_designed_rush`, so A1 drew its own `designed_qb` while the QB layer
   drew `rush_opp`. The table in §1 is the size of the disagreement, and the
   gap between the two answers is exactly the amount by which the named owners
   can exceed the level.
3. **The published level was not the level that was partitioned.**
   `run_forecast` sealed D1's raw continuous draw while the engine partitioned
   the SC1-permuted, integerised one. `draw_coherence` says so itself, in the
   `why_not_hard` of `team_qb_rush_opportunity_within_team_carries`: a breach
   could not be split between a carry with two owners and a denominator that
   was never used, which is why that identity is a diagnostic rather than a
   gate.

---

## 3. The repair -- the constraint holds BY CONSTRUCTION

One new function, `rushing_a1.compose_rush_ownership`, holds all three steps in
the order that makes the bound an identity:

    coupled   = SC1.couple(qb_rush_opportunity, team_carry_level)
    published = rint(coupled)                       # A1's declared rounding
    designed  = qb_rush_opportunity - qb_scrambles  # ONE owner: the QB layer
    alloc     = allocate(..., qb_designed_rush=designed)

`SC1.couple` is generic in its first argument -- it is a per-draw lower bound
on carries -- so raising the bound needs **no change inside
`scramble_coherence.py`**, which is untouched. Because `qb_rush_opportunity` is
integral and `coupled >= rush_opp` elementwise, `rint(coupled) >= rush_opp`,
so the budget `published - scr` is never smaller than `designed` and A1's
`_partition_given` draws the remaining five categories from the **exact
conditional multinomial**. Then, in every draw:

    rb_category + qb_rush_opportunity
        = (published - scr - designed - kneel - wr - te - fringe)
          + (scr + designed)
        = published - (kneel + wr + te + fringe)
        <= published

and the named backs are a partition of `rb_category`, so they are contained a
fortiori. **No clipping, no truncation, no renormalisation of a drawn result,
no deleted draw.** SC1 only chooses which draw index receives which carry
value, and it checks the multiset invariance itself; A1 draws a conditional
law rather than adjusting a partition after the fact.

The bound is then **verified**, not asserted, by a second new function
`rushing_a1.assert_named_owner_containment`, which returns BOTH decomposed
halves on every call and whose refusal carries both. It is shown to reject a
seeded one-carry breach.

`football_engine.run_game` calls it and records
`g['accounting']['rush_named_owner_containment']` with the decomposed evidence.
A club with a category ledger but no player split (an
`APPEARANCE_TEAM_DEFERRED` club) is **named** as not measured rather than
folded in as a zero row.

### Reconciling the two answers for designed QB runs

They are one quantity and now have one value: `rush_category.designed_qb` **is**
`rush_opp - scr`, cell for cell, 0 disagreeing cells. They were never two
different things measuring two different quantities -- both were answering "how
many of this team's carries did its quarterbacks take on designed runs", one
from A1's multinomial and one from the QB layer's draw, and only the QB layer
owns the quarterback's rushing.

### What is NOT fixed, and is named

`stat_contract.py` needed no change and has none.

`g['accounting']` is **not serialised into any sealed artifact** -- neither the
new containment verdict nor `rush_opportunity_single_owner`, which has been in
the engine since R4, appears in `board.json`, `run_status.json` or
`forecast_artifact.json`. The containment is still auditable from a sealed
board through `draw_coherence.components.carries` (see §4). Publishing the
engine accounting block is a separate repair with a separate owner and is
recorded here rather than absorbed.

---

## 4. Before and after, on a matched pair

Both boards: `2026_01_DEN_KC`, cutoff `2026-09-14T23:27:47Z`, 1,000 draws,
seed 20260908, same tree, same `code_commit`
`64783d0aebe440469e97c4bf5439b7a8c20635`. The **declared treatment** is
`model_configuration`; `run_id` and `spec_hash` follow from it. Nothing else in
the execution identity differs.

* before `nfl/research/v4/p3/before_r9/97473fb9d7a71042` -- `V1_CANDIDATE_R9`
* after  `nfl/research/v4/p3/after_r11/8d4671c7b4c7befd` -- `V1_CANDIDATE_R11`

`python3.12 nfl/research/v4/p3/p3_blast.py <before> <after>`

### Containment, both decompositions, both clubs

| club | series | over the gate | any positive | max excess |
|---|---|--:|--:|--:|
| DEN | RB only | 0 → **0** | 2 → **0** | +0.2619 → **+0.0000** |
| DEN | QB rush only | 0 → **0** | 0 → **0** | −4.8852 → −5.0000 |
| DEN | **RB + QB rush** | **149 → 0** | **206 → 0** | **+6.1219 → +0.0000** |
| KC | RB only | 0 → **0** | 2 → **0** | +0.0854 → **+0.0000** |
| KC | QB rush only | **1 → 0** | 1 → **0** | **+0.6915 → +0.0000** |
| KC | **RB + QB rush** | **148 → 0** | **237 → 0** | **+9.6915 → +0.0000** |

Not "under tolerance" -- **zero excess in every draw**, which is what "by
construction" means here.

### The product gate itself, re-run on both boards

`quality_gates.gate_rush_accounting`:

| club | R9 | R11 |
|---|---|---|
| DEN/rushing | **FIRED**, 149/1000, max 6.1219, action QUARANTINE_FAMILY | **PASS**, 0/1000, max 0.0 |
| KC/rushing | **FIRED**, 148/1000, max 9.6915, action QUARANTINE_FAMILY | **PASS**, 0/1000, max 0.0 |

`draws_with_negative_designed_rush` is 0 on all four.
`RUSH_UNOWNED_SHARE_OUTSIDE_CORPUS_RANGE` fires on neither board: mean unowned
share DEN 0.10959 → 0.08590 and KC 0.073514 → 0.065787, both inside the sealed
corpus range [0.00616, 0.45290].

### `draw_coherence`, independently, from the sealed arrays

The `carries` component, 2,000 cells each:

| identity | R9 | R11 |
|---|--:|--:|
| `team_carry_allocation_containment` | **443** violations | **0** |
| `team_qb_rush_opportunity_within_team_carries` | **1** | **0** |
| `team_scrambles_within_team_carries` | 0 | 0 |
| `diagnostics_not_clean` | `{443, 1}` | **`{}`** |

The 443 → 0 is the stored-vector defect (cause 3) closing: those cells were the
allocation measured against a denominator the game never used.

### Blast radius

| quantity | DEN | KC |
|---|---|---|
| designed_qb state | TWO_ANSWERS → **ONE_ANSWER**, 814 → **0** cells disagreeing | TWO_ANSWERS → **ONE_ANSWER**, 528 → **0** |
| partition, declared form | 0.0000 → 0.0000 | 0.0000 → 0.0000 |
| `rb` split (backs + unmodelled pool) | 0.0000 → 0.0000 | 0.0000 → 0.0000 |
| `rushing_td <= carries` violations | **0 → 0** | **0 → 0** |
| published level | mean 27.5514 → 27.5320, integer **False → True** | 25.2449 → 25.1720, **False → True** |
| team carries, named backs | 20.4970 → **21.1320** (+0.6350) | 19.9310 → **20.0580** (+0.1270) |
| QB rush opportunity | 4.0350 → **4.0350** (unchanged) | 3.4580 → **3.4580** (unchanged) |
| scrambles | 2.4080 → **2.4080** (unchanged) | 2.8430 → **2.8430** (unchanged) |

Per named back, mean carries:

| club | player | before | after | change |
|---|---|--:|--:|--:|
| DEN | 00-0036158 | 10.7240 | 10.9520 | +0.2280 |
| DEN | 00-0040730 | 6.5150 | 6.8350 | +0.3200 |
| DEN | 00-0041496 | 2.5070 | 2.5520 | +0.0450 |
| DEN | 00-0037085 | 0.7510 | 0.7930 | +0.0420 |
| KC | 00-0041013 | 8.4950 | 8.5370 | +0.0420 |
| KC | 00-0038134 | 8.0520 | 8.0920 | +0.0400 |
| KC | 00-0040078 | 3.3840 | 3.4290 | +0.0450 |

**Why the backs gain, and it is arithmetic rather than a view.** A1's own
`designed_qb` mean was ABOVE the QB layer's on both clubs (2.2960 vs 1.6270;
0.7090 vs 0.6150). Handing the quarterback's smaller, owned count to A1 returns
that difference to the rush-play budget, and the `rb` category holds roughly
80% of it. DEN 2.2960 − 1.6270 = 0.6690 against a measured +0.6350 to the
backs; KC 0.0940 against +0.1270. Nothing was moved toward any player.

**The quarterback layer is bit-identical.** `rush_opp` and `scr` means are
unchanged to four decimals on both clubs, which is the point: the QB layer owns
those draws and this repair reads them.

**Run status.** Both boards SEALED with 0 refusals. The accounting verdict list
is identical on both, item for item, except `rushing_single_owner`, whose code
moves `A1_RUSH_ALLOCATION` → `A1_RUSH_OWNERSHIP_COMPOSED` (PASS on both).
`draw_coherence` PASS on both.

---

## 5. Successor candidate, and what was NOT edited

Registered **`V1_CANDIDATE_R11`** in `nfl/production/candidate_mode.py`, flag
`rush_single_owner`, following how R9 was added.

**It inherits R9, not R10.** R10 was claimed by a concurrent appearance repair
while this work was in progress (my first patch collided with it and was
withdrawn); R12 was claimed by a third. R11 is R9 plus this one repair, so any
difference between an R9 and an R11 run is attributable to it and to nothing
else. Stacking an unrelated unvalidated mechanism underneath would destroy
that.

`R11_REPAIR` records the defect at its measured size, the decomposition, the
structural guarantee, `introduces_no_constant: True`,
`no_clip_truncation_renormalisation_or_deleted_draw: True`, and four open items
that are **not** smoothed over:

* raising SC1's bound permutes more draws, so A3G's game-level pairing survives
  in fewer cells. The carry marginal is unchanged element for element; **the
  joint with the opposing club is not, and that is not measured here.**
* `designed_qb`'s marginal is now the QB layer's draw, so this composition
  inherits whatever `qb2_lib` carries -- including its own open dropback-share
  miscalibration.
* the published carry level becomes integral, which is a change to what the
  board publishes.
* the repair was found by inspecting a sealed board in this repository, so it
  is engineering integration on development data. **Nothing here is a
  prospective result.**

**R8 and R9 are untouched. `rushing_a1.allocate` is untouched** -- the
composition calls it; `_partition_given` already existed and is now reached.
`nfl/production/nonqb/layers.py` verified `481f005f682cd721...` at start and at
end, unmodified. **All 870 sealed files under `nfl/research/live/` and
`nfl/research/v2/u1/` are byte-identical before and after this work**, verified
by sha256 diff. Trial builds are under `nfl/research/v4/p3/` only; nothing was
written into `nfl/research/live/`.

Files changed: `nfl/production/nonqb/rushing_a1.py` (two new functions, nothing
edited), `nfl/production/nonqb/football_engine.py` (the decomposed verdict),
`nfl/production/candidate_mode.py` (R11), `nfl/production/run_forecast.py` (the
wiring, gated so the R9 path is byte-identical), and the new
`nfl/tests/test_p3_rush_accounting.py`, `nfl/research/v4/p3/p3_measure.py`,
`nfl/research/v4/p3/p3_blast.py`. `nfl/production/stat_contract.py` needed no
change.

`run_forecast.py` is outside the file set P3 was given and is edited here
because the wiring has nowhere else to live: two of the three causes ARE that
call site. The edit is inside `if fl.get('rushing_a1')`, gated on
`rush_single_owner`, and the R9 branch is the previous code verbatim.

---

## 6. Tests

| suite | before this work | after |
|---|---|---|
| `test_p3_rush_accounting` (new) | 15 pass / **6 fail** | **52 pass / 0 fail**, 10 functions |
| `test_v1_rushing_a1` | 148 / 0 fail | 148 / 0 fail |
| `test_football_engine_r4` | 142 / 0 fail | 142 / 0 fail |
| `test_stat_contract` | 94 / **1 fail** | 94 / **1 fail** (same check, unrelated) |
| `test_quality_gates` | 253 / 0 fail | 253 / 0 fail |
| `test_v1_scramble_coherence` | 24 / 0 fail | 24 / 0 fail |
| `test_conservation` | 225 / **6 fail** | 225 / **6 fail** (unchanged) |
| `test_draw_coherence` | 135 / **9 fail** | 135 / **9 fail** (unchanged) |
| `test_decomposition` | 86 / 0 fail | 86 / 0 fail |
| `test_product_layer` | 54 / 0 fail | 54 / 0 fail |

The `test_conservation`, `test_draw_coherence` and `test_stat_contract`
failures are pre-existing and are the deliberate reproductions for other
repairs. **No baseline was moved to make anything green.** The corpus fences
read `sealed_index.live_draw_files()` under `nfl/research/live/`, which the
trial builds under `nfl/research/v4/p3/` do not enter.

---

## 7. What this is not

**Nothing here is tuned to DEN@KC.** The realized outcome is not in this
repository: the newest 2026 play-by-play capture predates the
2026-09-15T00:15Z kickoff and holds zero DEN or KC rows. No realized carry
count appears anywhere in the code, the tests or this document as a target, and
the two sealed boards are used as a FIXTURE OF THE DEFECT, never as a
scoreboard. The carry means in §4 moved because an accounting identity was
enforced; that is not evidence that they are better, and no such claim is made.

**Nothing here is a forecasting result.** Every number is an arithmetic
property of the draws -- a containment count, a closure residual, a cell
disagreement. No calibration, no discrimination, no score against an outcome,
no equivalence margin, no TOST. `V1_CANDIDATE_R11` is REHEARSAL_ONLY and
nothing in this work promotes anything.
