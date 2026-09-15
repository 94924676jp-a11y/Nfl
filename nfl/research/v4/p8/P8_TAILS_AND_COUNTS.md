# P8 — impossible distribution tails, and integer count support

V2 directive items **1.8** and **1.9**. Two defects, one class: a quantity
generated at one scale and published as though the scale did not matter.

`nfl/production/nonqb/layers.py` verified unchanged at start and at end:
`481f005f682cd72129e6bf02e55cba86913ddffd7d88367743c616e3e11c0108`.
`board_pointer.verify_seal('V1_SEALED')` returns `PASS[SEAL_INTACT]`; no sealed
board was read for anything but measurement and none was written.
No market data, no external projection, no DEN@KC outcome — that result is not
in this repository and was not sought.

Machine-readable companion: `P8_EVIDENCE.json`.
Reproduce: `python3.12 nfl/research/v4/p8/p8_measure.py`.
Failing reproduction: `python3.12 nfl/research/v4/p8/p8_reproduce.py incumbent`.

---

## 0. Headline

| | before | after |
|---|---|---|
| max simulated passing yards, 2025 cohort | **2,898** | **772** |
| min simulated passing yards | **−238** | **−3** |
| rate above the 554-yard all-time record | **5.260e−03** | **5.102e−04** |
| …against a bound derived from realised football | 6.65× **outside** | 0.65×, **inside** |
| cells below −30 yards (D19's own magnitude) | **970** | **0** |
| cells in D19's exact state (16+ cmp, ≤ −32 yds) | **938** | **0** |
| cells outside the realised ratio support at their own completion count | **13,803** | **112** |
| passing-yard CRPS | 48.855 | 49.103 (Δ **+0.248 [−0.074, +0.524]**) |

**Both tails closed together, from one mechanism change, with no clip.** The
CRPS interval contains zero: this cohort does **not** establish that either arm
forecasts better, and the repair is not offered as one that does.

**Item 1.9 is a different story and the honest version is shorter than the
brief implies: the carry-generation defect was already repaired in code before
I started.** What was open was that nothing asserted the invariant. That fence
now exists. Details in §5.

---

## 1. What the brief said, and what reproduces

Every figure below was re-measured in this checkout, not carried over.

| brief claim | verdict |
|---|---|
| max `qb/pyds` = 1,587 across sealed boards | **reproduced exactly** (990,000 cells, 121 boards) |
| 680 cells above the 554-yard record | **reproduced exactly**, on the 520,000 QB-only-side cells. The all-boards figure is **795**; C3-bound sides carry the other 115 |
| QB-only rate 1.308e−03, outside the bound by 1.65× | **reproduced**: 680/520,000 = 1.3077e−03; bound 7.9074e−04; ratio **1.654** |
| C3 sides at 2.454e−04, inside | **reproduced**: 115/470,000 = **2.4468e−04** |
| 2,140 of 130,422 cells outside the ratio support at `cmp ≥ 10` | **reproduced exactly**, on QB-only sides |
| 94.2% of those trace to a one-completion donor | **mechanism confirmed, on my own cohort.** On cohort C1's incumbent arm, **100%** of out-of-support cells at `cmp ≥ 10` match a *pool* ratio exactly (none comes from own history), **86.5%** from a one-completion donor and **95.0%** from a 1- or 2-completion donor. I did not re-derive the sealed corpus's own 94.2% because its cell frame is not fully specified; mine is stated here instead |
| the mechanism is `qb2_lib.py:306-307` | **true when written, now at `qb2_lib.py:436-437`** — P2's `share_draws` was inserted above it. Verified by reading, not by line number |
| D19: −2.0 × 16 = −32.0, the −2.0 from a one-completion game | **reproduced**: 10 negative donor ratios in the 3,787-game pool, **every one from a 1- or 2-completion game**; four of them are exactly −2.0 |
| derived bound 7.907e−04 from n = 3,787, observed max 525, zero above 554 | **reproduced**: pool max **525**, zero above 554, 1 − 0.05^(1/3787) = **7.90744e−04** (rule of three 3/n = 7.92184e−04) |
| `rushing/carries` non-integer in 327,103 of 516,000 cells (63.4%) | **reproduced exactly** (63.39%, 51 of 121 boards) |
| every `rushing_td > carries` cell is `0 < carries < 1` with `td == 1` | **CORRECTED — see §5.1** |

### 1.1 Two corrections to the record

**(a) The `rushing_td > carries` shape.** 442 violating cells, of which **415**
are `0 < carries < 1` with one touchdown and **27** are `1 < carries < 2` with
*two*. "Every violation is the first kind" is **93.9%**, not all. What *is* true
of all 442: every one has a fractional carry, and every one vanishes against
`ceil` and against `rint` — which is exactly why neither is the comparison.

**(b) The X1 census's "3,181 games with 5 or more completions".** That is the
count at **ten** or more. At five or more it is **3,385**. The minimum ratio
+3.462 is correct either way, because it occurs in the 10–14 band.

---

## 2. Defect A — the mechanism, verified by reading

`nfl/research/qb2/qb2_lib.py:436-437`, before the repair:

    ypc_d = _mix(rng, r['h_ypc'], po['ypc'], w, m, ew)
    PY = CMP * ypc_d

`_mix` resamples one **game-level** yards-per-completion ratio — uniformly over
games, from the quarterback's own history with probability
`w = h_games/(h_games+4)` and from a 3,787-game positional pool otherwise — and
multiplies it by a completion count drawn independently. The donor ratio
carries no record of the completion count that produced it and is not weighted
by it.

**The defect is scale non-exchangeability.** A ratio estimated at n = 1
completion is applied at n = 16 with no shrinkage and no denominator weighting.
The realised pool says how wrong that is:

| completions | games | mean cmp | min ratio | max ratio | variance |
|---|---|---|---|---|---|
| 1 | 222 | 1.00 | **−7.000** | **75.000** | 148.489 |
| 2–4 | 180 | 2.69 | −2.000 | 40.000 | 53.663 |
| 5–9 | 204 | 7.04 | +4.111 | 27.333 | 17.021 |
| 10–14 | 410 | 12.43 | +3.462 | 22.091 | 10.006 |
| 15–19 | 846 | 17.20 | +4.235 | 21.000 | 7.222 |
| 20+ | 1,925 | 25.12 | +5.125 | 21.200 | 4.178 |

The incumbent emits the **1-completion** support at every completion count. On
cohort C1 its implied-ratio range is `[−7.000, +75.000]` in the 10–14, 15–19
**and** 20+ bands alike, and its variance in the 20+ band is **9.877** against a
realised 4.178.

### 2.1 A candidate I tested and rejected on evidence

Reliability shrinkage `n/(n+k)` needs a derived `k`, and `k = σ²_within /
σ²_between` is **not identified in this data**. Fitting
`Var(ratio | n) = σ²_b + σ²_w/n` by weighted least squares over the 37 exact
completion counts with ≥ 10 games returns **σ²_b = −2.29**, a negative variance
component. With σ²_b pinned at zero the implied σ²_w still falls monotonically
with n (148.5 at n = 1 down to 105.0 at 20+), so one constant does not describe
the pool. There is no derivation for `k`, so there is no `k`, and a chosen one
would be a silent constant. Rejected.

---

## 3. The repair — resample completions, not ratios

`YPC_SPEC_COMPLETION_BLOCKS` in `qb2_lib.py`, default **off**.

A draw needing `CMP` completions draws donor games **with probability
proportional to their own completion count** and consumes
`t = min(n_donor, completions still needed)` from each, until `CMP` are covered:

    PY = Σ_k t_k · ratio_k ,    Σ_k t_k = CMP ,    t_k ≤ n_k

**The invariant: no donor game supplies yardage for more completions than it
itself recorded.** The −7.0 one-completion donor that made D19's magnitude can
now contribute −7 yards to a 16-completion game, not −112. The function returns
its own block ledger and `passing_yards_draws` raises
`QB_YPC_BLOCK_LEDGER_BROKEN` if the closure fails, because an unchecked
construction is an assumption.

The source mixture weight `w` is applied **per completion block** rather than
per game. That is one coherent statement — `w` is a reliability weight on an
estimate of a per-completion rate, so it belongs at the completion — and it is
declared as part of the treatment because it is worth measuring: the per-game
variant (source chosen once per draw) lands at **9.50e−04**, which is *outside*
the derived bound, and at 1,237 out-of-support cells against 112.

### 3.1 It is not a clip, and here is how that is checked

Nothing is truncated, rejected or renormalised. The **support is unchanged** —
every value the generator can emit is still a completion-weighted average of
realised ratios — and only the probability law moves. Reaching an extreme now
requires many independent extreme draws instead of one.

`test_p8_tails_and_counts::test_f` asserts it three ways: the candidate's 40
largest cells are 31+ distinct values rather than copies of a bound; its maximum
equals no fence in the module; and the AST of `qb2_lib.py` still contains
exactly the **two** pre-existing `np.clip` calls (both on the share), with no
`trunc` and no rejection loop added.

### 3.2 The treatment is isolated, and that took a deliberate device

The candidate draws a *variable* number of random numbers, so naively it would
shift the RNG position of every layer drawn after passing yards. Two measures:

- the block draws run on `rng.spawn(1)[0]`, a child derived from the parent's
  seed sequence rather than its stream position, so the yardage draw is
  reproducible and consumes nothing from the parent;
- the incumbent's own `_mix` is still called on the parent and its result
  **discarded**, purely to hold the parent at the position the incumbent leaves
  it in.

The result, asserted in the test module and again inside `p8_measure.py`:
**the only draw matrix that differs between the two arms is `pyds`.** `db`,
`att`, `sacks`, `scr`, `cmp`, `ptd`, `int`, `drush`, `rush_opp`, `ryds` and
`rtd` are byte-identical. R2 made the opposite choice — skip the draws, accept a
shifted stream — and said so; this says so too.

The **default path is byte-identical to the pre-repair tree**, cell for cell,
verified on 635,000 cells.

---

## 4. Results

### 4.1 The cohort question, answered honestly

**The cohort that established the 680 cells cannot be rerun in this checkout.**
Those cells were counted over the sealed boards, which `run_forecast` produced
through the engine's R2 dropback path from 2026 roster inputs, and
`qb2_lib.load()` cannot run here at all — `nfl/research/p4b/panel_enriched.pkl`
is absent, which is why H1 and P2 both rebuild the frame from `qb.pkl`. I
confirmed the gap rather than assumed it: re-simulating a sealed board's QB rows
through raw `qb_v1` does **not** reproduce its sealed cells. Two substitute
cohorts are used and both are named.

**C1 — 635 eligible 2025 QB-game rows over 272 games**, forward-chained
(pool 2020–2024), `rung='L1'`, seed 20260908, 1,000 draws = **635,000 cells**.
The only cohort with realised outcomes, so all prediction-quality numbers come
from here. C1's incumbent tail rate (5.26e−03) is **four times the sealed
corpus's** (1.31e−03), so C1 is a harsher cohort, not a stand-in for the
corpus's own rate. What transfers is the mechanism and the direction.

**C2 — the 79 quarterbacks who actually appear on the sealed boards**, run as
2026 week-1 prospective rows through raw `qb_v1` with no engine, 79,000 cells.
Same players, different execution path from the boards, and **no realised
outcome exists for them**, so nothing is scored.

### 4.2 Tails

| | C1 incumbent | C1 candidate | C2 incumbent | C2 candidate |
|---|---|---|---|---|
| cells | 635,000 | 635,000 | 79,000 | 79,000 |
| max | 2,898 | **772** | 2,208 | **693** |
| min | −238 | **−3** | −189 | **−4** |
| cells > 554 | 3,340 | **324** | 464 | **30** |
| rate | 5.2598e−03 | **5.1024e−04** | 5.8734e−03 | **3.7975e−04** |
| row-clustered 95% CI | [4.611e−03, 5.909e−03] | **[4.317e−04, 5.888e−04]** | — | — |
| negative cells | 1,483 | 12 | 396 | 75 |
| cells < −30 | 970 | **0** | 204 | **0** |
| out-of-support (banded) | 13,803 | **112** | 2,395 | **10** |
| mean | 207.264 | 205.531 | 185.697 | 184.840 |

**Against the derived bound 7.9074e−04**: the incumbent's whole clustered
interval sits above it; the candidate's whole clustered interval sits below it.

### 4.3 The band table — the repair reproduces the scaling it was missing

Implied yards-per-completion on C1, by the cell's **own** completion count:

| band | realised var | incumbent var | incumbent range | candidate var | candidate range | oos: inc → cand |
|---|---|---|---|---|---|---|
| 1 | 148.489 | 27.410 | [−7.000, 75.000] | 12.553 | [−3.000, 69.000] | 0 → 0 |
| 2–4 | 53.663 | 21.289 | [−7.000, 69.000] | 7.544 | [−0.500, 40.000] | 50 → 0 |
| 5–9 | 17.021 | 14.282 | [−7.000, 69.000] | 6.230 | [+2.667, 27.139] | 781 → 19 |
| 10–14 | 10.006 | 11.751 | [−7.000, 75.000] | 5.714 | [+3.462, 22.116] | 1,201 → 1 |
| 15–19 | 7.222 | 11.084 | [−7.000, 75.000] | 5.035 | [+4.033, 21.995] | 3,449 → 45 |
| 20+ | 4.178 | 9.877 | [−7.000, 75.000] | 3.899 | [+4.174, 21.200] | 8,322 → 47 |

The incumbent's range is the same in every band, which is the defect stated as a
picture. The candidate's tightens with the band and tracks the realised support;
its 20+ maximum is **21.200**, the realised value to the digit.

### 4.4 Blast radius — what else moved

| | incumbent | candidate | reading |
|---|---|---|---|
| CRPS | 48.8553 | 49.1030 | Δ **+0.2477 [−0.0738, +0.5244]**, game-clustered block bootstrap, 2,000 resamples. **Interval contains zero.** |
| mean `pyds` | 207.264 | 205.531 | **−1.73 yards, −0.84%** |
| signed bias | +15.662 | +13.929 | moves toward zero; still far from it |
| SD of draws | 113.858 | 100.704 | |
| SD of row means | 43.971 | 42.424 | −3.5% less spread of conditional means |
| Pearson r (row mean vs realised) | 0.4406 | 0.4530 | |
| coverage 50 / 80 / 90 / 95 | .531 / .827 / .934 / .967 | .498 / .798 / .912 / .959 | toward nominal at 50 and 80, slightly **below** at 90 and 95 |
| randomised PIT χ²(9 df) | 19.094 | 16.512 | 5% critical value 16.919 |
| completion marginal | — | **identical, cell for cell** | |

**The centre moves and it is declared as part of the change, not discovered
after it.** The shift is the denominator weighting doing exactly what it is for:
the completion-weighted mean ratio is **10.955** and the unweighted mean of
game ratios is **11.135**. A repair that weights by the denominator must move
the centre by that difference; this one moves it by −0.84%.

**On the PIT: neither arm is shown calibrated and the word is not used of
either.** The incumbent's randomised PIT rejects uniformity at 5% and the
candidate's does not (16.512 against 16.919, p ≈ 0.057). Failure to reject is
not evidence of adequacy, and no equivalence margin was predeclared.

### 4.5 What did NOT close, with its residual count

- **324 cells still exceed 554 yards** on C1 (the rate is inside the bound, the
  count is not zero). **46 of them (14.2%) carry a completion count above 47,
  the realised maximum** — those cells are impossible before the yardage layer
  sees them, and that is the completion/dropback layer's, not this one's. Their
  completion counts run 28 to 60, median 41.
- **112 cells remain outside the banded ratio support**: 47 below in the 20+
  band, 45 above in 15–19, 19 below in 5–9, 1 above in 10–14.
- **12 negative cells remain**, none below −3 yards, all at low completion
  counts. Real football has negative ratios at 1–2 completions, so a generator
  with none there would be wrong in the other direction.
- **The 1–4 completion bands get worse.** Implied-ratio variance at 1 completion
  falls 27.4 → 12.6 against a realised 148.5. Both arms are badly
  under-dispersed there; the repair widens that gap, because a one-completion
  draw now takes one donor's *game average* rather than a whole game ratio. The
  band is 7% of cells and no starting-quarterback forecast lives in it, but it
  is a cost and it is recorded as one.
- **`qb/ryds` was not touched.** `out['ryds'] = RO * ypr` at `qb2_lib.py:480` is
  the *same mechanism* on rushing yards, and the sealed corpus carries 3,353
  negative `qb/ryds` cells. It is named here and left alone: repairing it in the
  same change would make the two unattributable.

---

## 5. Defect B — `rushing/carries` is not a count

### 5.1 Measured state

121 sealed boards, **516,000** carry cells, **327,103 non-integer (63.39%)**,
across 51 boards. `rushing_td > carries` in **442** cells: **415** at
`0 < carries < 1` with one touchdown, **27** at `1 < carries < 2` with two.

**Every one of the 442 disappears against `ceil(carries)` and against
`rint(carries)`, and that is the reason neither is used.** The mechanism is
visible in it: `layers.rushing_td:552` draws its binomial on
`rint(carry_draws)` while the board publishes the unrounded column. Two numbers
for one quantity. Comparing against a rounding would take the count to zero
without removing one fractional carry from one board.

### 5.2 The finding the brief did not have: the generator is already repaired

`rushing/carries` is the **only** declared count in the entire corpus that is
ever non-integer. Measured over all 121 boards:

| metric | cells | non-integer |
|---|---|---|
| every `qb/*` count (9 metrics) | 990,000 each | **0** |
| every `receiving/*` count (3 metrics) | 1,924,000 each | **0** |
| `rushing/rushing_td` | 516,000 | **0** |
| `rushing/carries` | 516,000 | **327,103** |

And the split by board vintage is a switch, not a gradient: the **two boards
built after the R4 counts repair** (`V1_CANDIDATE_R9`, commit `f326a6d`) carry
**10,000 carry cells, 0 non-integer, 0 violations**. `football_engine` now calls
`stat_contract.integerise_level` on the A1 budget and `stat_contract.deal_counts`
to deal it, and `assert_counts_are_counts` halts the run on the values that
actually seal. **Item 1.9's generation half was closed before this task began.**

I say so rather than re-fixing it: the brief's instruction was to generate the
carry as a count using `deal_counts`, and `deal_counts` is already what
generates it.

### 5.3 What was actually open, and what I did about it

**The cause was closed and the symptom was never fenced.** Nothing in this
repository asserts `rushing_td ≤ carries`, or any other event-within-opportunity
bound, on the matrices that seal. The 442 cells reached sealed artifacts with no
check pointed at them, and the integrality gate only catches them by accident —
it catches the fractional carry, not the impossible touchdown. A second route to
an over-drawn event would still arrive unannounced.

Added to `nfl/production/stat_contract.py` (which P8 owns):
**`assert_events_within_opportunity`**, with five declared pairs —
`rushing/rushing_td ≤ rushing/carries`, `receiving/receptions ≤
receiving/targets`, `receiving/receiving_td ≤ receiving/receptions`,
`qb/cmp ≤ qb/att`, `qb/ptd ≤ qb/cmp` — each naming *why* the bound holds.

It asserts and never repairs. It refuses `round_opportunity=` by name
(`EVENT_OPPORTUNITY_ROUNDING_REQUESTED`) so the `ceil` shortcut cannot be taken
through this contract. A pair whose opportunity array is missing is **skipped
and named**; a call that completes no pair at all is **BLOCKED**, not passed.

Demonstrated on seeded violations, not only on compliant data
(`test_p8_tails_and_counts::test_h`): a contaminated sealed board is REFUSED, a
post-repair board PASSES, `round_opportunity='ceil'` is REFUSED, a shape
mismatch is REFUSED rather than broadcast, and a seeded violation on
`receiving/receptions` is caught with the right cell count.

**Not wired into the engine.** `nfl/production/nonqb/football_engine.py` is on
P8's do-not-edit list, and the call site is one line beside the existing
`assert_counts_are_counts` at line 1801 — `_count_mats` already holds every
array the five pairs need. That one line is the remaining work on item 1.9 and
it is not mine to write; see §7.

---

## 6. Tests

`nfl/tests/test_p8_tails_and_counts.py` — new, 8 functions, **48 checks, 0
failing, 0 blocked**.

**The failing reproduction, shown failing.** `p8_reproduce.py` states one
criterion — the rate above 554 yards must lie inside the bound derived from the
donor pool — and runs it against one named arm:

    $ python3.12 nfl/research/v4/p8/p8_reproduce.py incumbent
    donor pool         3787 realised QB game-lines, maximum 525 yards, 0 above 554
    derived bound      7.907440e-04  (one-sided 95%, zero of 3787)
    cohort             635 rows x 1000 draws = 635000 cells
    cells above 554    3340
    rate               5.259843e-03  (6.65x the bound)
    maximum            2898 yards
    minimum            -238 yards
    cells below -30    970
    FAIL P8_UPPER_TAIL_OUTSIDE_DERIVED_BOUND: 5.259843e-03 > 7.907440e-04
    exit=1

    $ python3.12 nfl/research/v4/p8/p8_reproduce.py candidate
    rate               5.102362e-04  (0.65x the bound)
    maximum            772 yards
    minimum            -3 yards
    cells below -30    0
    PASS P8_UPPER_TAIL_INSIDE_DERIVED_BOUND
    exit=0

**No suite regressed.** Every suite that imports `qb_v1`, `qb2_lib` or
`stat_contract` was run in this tree and again in a `git worktree` at HEAD, and
the failing-check counts are identical in every one:

| suite | baseline | this tree |
|---|---|---|
| `test_stat_contract` | 94 checks, 1 failing | 94 checks, 1 failing |
| `test_draw_coherence` | 136 checks, 4 failing | 136 checks, 4 failing |
| `test_qb2_production` | 40 checks, 0 failing, 9 raised | identical |
| `test_qb_share_calibration` | 24, 0 | identical |
| `test_v1_entrypoint_integration` | 26, 0 | identical |
| `test_production_pipeline` | 69, 0 | identical |
| `test_p6_false_greens` | 36, 19 failing, 1 raised | identical |
| `test_passer_credit_migration` | 35, 3 failing, 1 raised | identical |
| `test_refbands` | 124, 0 | identical |
| `test_xl1_shared_pass` | 115, 0 | identical |
| `test_p3_rush_accounting` | 52, 0 | identical |
| `test_sealed_corpus_census` | 10, 0 | identical |
| `test_full_slate_rehearsal` | **not comparable** | 30 checks, 0 failing, 0 raised |

`test_full_slate_rehearsal` is the one row where the two runs differ, and the
difference is the *baseline* rather than this tree: a fresh `git worktree`
holds only tracked files, and that suite reads inputs this checkout carries
untracked, so it came back 23 checks / 9 failing / 3 raised there against 30
checks / 0 failing / 0 raised here. The worktree number is an artefact of the
comparison method and is NOT evidence that anything improved. In this tree the
suite is clean.

Those pre-existing failures are not mine and are not touched. In particular
`test_stat_contract`'s single failure is the deliberate one its own comment
declares: the non-integer carry fence is held at 243,766 (the state the counts
repair achieved) against 271,691 on the fenced corpus, and it fails until the
unmigrated boards are dealt with. Absorbing the difference would convert 27,925
defective cells into "the expected number".

---

## 7. What I did not do, and why

**The R13 candidate is NOT registered.** Step 3 of my brief says to register a
new successor candidate additively in `nfl/production/candidate_mode.py`; the
same brief lists `candidate_mode.py` among the files I must not edit, and says
to stop and say so if the work needs one. It does. During this task HEAD moved
from `53a3c27` to `6216de0` and another agent's uncommitted edit to
`nfl/tests/test_qb_eligibility_den_kc.py` appeared in the tree, so two agents
appending to one `MODES` tuple is a live risk and R13 could be claimed twice.

The complete block is written out at
**`nfl/research/v4/p8/R13_REGISTRATION_BLOCK.py.txt`** — four additive edits,
R8 and R9 untouched, with the flag `qb_ypc_spec: 'completion_blocks'` and the
full measured evidence and cost list in the `R13_REPAIR` dict. **It needs the
coordinator to apply it, and to confirm R13 is free.**

**`assert_events_within_opportunity` is not called from the engine**, for the
same reason: `football_engine.py` is not mine. One line at
`football_engine.py:1801`.

**`qb/ryds` carries the same defect and was left alone** (§4.5).

**No confirmatory claim is made.** 2025 is development data, four constructions
were compared on it, and the sealed corpus was inspected before the repair was
designed. Forward chaining controls parameter leakage, not specification
leakage. A confirmatory result needs untouched games, and this one cannot be it.

---

## 8. Files

| path | change |
|---|---|
| `nfl/research/qb2/qb2_lib.py` | `YPC_SPECS`, `completion_block_yards`, `passing_yards_draws`, `_norm_w`; `attach` writes `h_ypc_n`; `pools` returns `ypc_n`/`ypc_w`; `simulate(ypc_spec=…)`. Default byte-identical |
| `nfl/production/qb_v1.py` | `forecast(ypc_spec=…)`, refusal `QB_YPC_SPEC_UNKNOWN`, spec recorded in the outcome evidence |
| `nfl/production/stat_contract.py` | `EVENT_BOUNDS`, `assert_events_within_opportunity` |
| `nfl/tests/test_p8_tails_and_counts.py` | new, 48 checks |
| `nfl/research/v4/p8/p8_measure.py` | both arms, both cohorts, writes `P8_EVIDENCE.json` |
| `nfl/research/v4/p8/p8_reproduce.py` | the one-criterion failing reproduction |
| `nfl/research/v4/p8/R13_REGISTRATION_BLOCK.py.txt` | prepared, not applied |
| `nfl/research/v4/p8/P8_EVIDENCE.json` | every number above |

Nothing was committed or pushed. Nothing was written into `nfl/research/live/`.

**One side effect, declared.** Running the existing suites bumped
`nfl/research/v2/r5/active_board_pointer.json` (`pointer_version` 52 -> 58, two
timestamps) and appended four lines to
`nfl/prospective/q9shadow/Q9_SHADOW_DRYRUN_SEAL_LEDGER.jsonl`. Those are the
suites writing their own run records, not edits I authored. They are left in
place rather than reverted: the ledger is append-only and reverting it would
destroy someone else's run record as readily as mine.
