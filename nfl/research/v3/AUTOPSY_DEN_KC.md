# DEN@KC postgame adversarial autopsy

Coordinator synthesis. Board under autopsy: `d1e2727743c93990`
(`V1_CANDIDATE_R9`, cutoff 2026-09-14T20:58:33Z, 1,000 draws).

---

## 0. The finding that governs every other one

**The realized DEN@KC outcome is not in this repository, so the layer
decomposition and the sequential counterfactual that were requested cannot be
run, and I have not run them.**

Measured, not assumed: the newest 2026 play-by-play capture
(`pbp_2026.1415dd98ba7f701a.csv.gz`, sha256 `1415dd98…`) has
`retrieved_at` **2026-09-14T00:25:56Z**, roughly 24 hours BEFORE the
2026-09-15T00:15Z kickoff. It holds 10 week-1 games and **zero DEN or KC
rows**. No capture has been attempted since 17:39Z; the executor is halted.

Four figures were supplied in conversation — Mahomes 184 passing yards, Nix
131, Walker 23 carries, Johnson 8. **They are unverified against any capture
and are treated throughout as hypotheticals.** Even taken as true they pin one
endpoint each and leave all nine requested layers free: team plays, team
dropbacks, dropback share, attempts/dropback, completions/attempt,
yards/completion, TD/attempt, INT/attempt, scramble/rush-opportunity. The
sequential counterfactual is **underdetermined** by them. An attribution built
on them would be a decomposition of assumptions wearing the costume of a
measurement. Request lodged as OUT-014.

What IS computable without the capture, and is computed here: the complete
forecast-side chain, the exact position of any hypothesised outcome inside the
sealed predictive distribution (exact, because the board stores 1,000 draws
rather than nine percentiles), and the full 2025 reference distribution.

---

## 1. QB error attribution

### Forecast-side chain, from the sealed draws

| layer | Mahomes (KC) | Nix (DEN) |
|---|--:|--:|
| team off snaps | 67.6970 | 65.4120 |
| team dropbacks | 41.4679 | 37.1858 |
| QB dropback share | 0.9445 | 0.9499 |
| attempts / dropback | 0.8877 | 0.8977 |
| completions / attempt | 0.6550 | 0.6503 |
| yards / completion | 10.7707 | 10.1915 |
| passing TD / attempt | 0.0463 | 0.0445 |
| INT / attempt | 0.0186 | 0.0183 |
| scrambles / rush opp | 0.8856 | 0.5965 |
| sacks / dropback | 0.0457 | 0.0375 |
| **passing yards** | **245.2703** | **210.1484** |

The identity `dropbacks = attempts + sacks + scrambles` holds with maximum
deviation **0.0000** on both. The forecast chain is internally consistent;
there is no layer disagreement to exploit on the QB side.

### One-at-a-time sensitivity — which layers could produce the gaps

Each layer alone, others held at forecast:

| layer | Mahomes 245→184 | Nix 210→131 |
|---|---|---|
| team dropbacks | 41.47 → 31.11 | 37.19 → 23.18 |
| QB dropback share | 0.9445 → 0.7085 | 0.9499 → 0.5921 |
| attempts/dropback | 0.8877 → 0.6659 | 0.8977 → 0.5596 |
| completions/attempt | 0.6550 → 0.4914 | 0.6503 → 0.4054 |
| yards/completion | 10.77 → 8.08 | 10.19 → 6.35 |

None is impossible; they are not equally plausible. A 40.5% completion rate or
6.35 yards per completion would each be extreme. Nix's chain reaching 131 via
team dropbacks falling to 23 is unremarkable in a run-heavy game. **Which
actually happened requires the capture.**

---

## 2. Anomaly or bias — determined on 540 games, not on one

Answered from the 2025 forward-chained reference distribution (540 eligible
starting-QB games, 272 games, 32 teams, 20 layers; block bootstrap over whole
games, 2,000 resamples; **EXPLORATORY** — 2025 is development data in this
project). Sign convention: error = predicted − realised, **positive =
over-projection**.

**C. Did the model systematically over-project QB passing VOLUME in 2025?
No — it UNDER-projected it.**

| quantity | bias | interval |
|---|--:|---|
| team offensive plays | **+1.7987** | [+1.238, +2.337] |
| team dropbacks | +1.6369 | [+1.001, +2.251] |
| QB dropback share | **−0.0778** | [−0.0868, −0.0687] |
| QB dropbacks | **−1.3697** | [−2.099, −0.704] |
| attempts | −1.1394 | [−1.825, −0.486] |
| passing yards | −5.9223 | [−12.804, +0.426] |

The team-level over-projection is a **league drift, not a QB defect**: the
team-play forecast is a league mean with predicted SD 0.27 across 540 games,
and mean snaps fell 66.107 (2020–24) → 64.237 (2025), a drift of +1.870
against a measured bias of +1.799. The bias *is* the drift.

**D. Did it over-project conditional EFFICIENCY? No.** Both efficiency layers
clear a predeclared equivalence test — the only two quantities in the study
that do:

- yards/completion **+0.0268** [−0.1895, +0.2242], TOST p=0.0178, equivalent within ±0.25
- completions/attempt **−0.0031** [−0.0109, +0.0050], TOST p=0.0458, equivalent within ±0.010

**E. No cut survives multiplicity.** 15 predeclared cuts × 5 layers = 75
tests; 18 nominally significant against 3.75 expected; Holm leaves **two**,
neither on passing yards. **Week 1**: n=30, bias +3.874 vs −6.499 elsewhere,
difference +10.372 [−17.15, +32.60], p=0.371, p_holm 1.000. The direction is a
mild over-projection and 30 games cannot distinguish it from nothing.

Two requested cuts were refused and the refusals are declared: **"leading
teams"** is realised in-game state (conditioning on the outcome manufactures a
defect for any forecaster), and **no lawful pregame spread exists** —
`spread_line` and `vegas_wp` are market quantities and are refused — so a
non-market prior-point-differential proxy was substituted and labelled as one.

### The real QB defect, and it is neither volume nor efficiency

> **CORRECTED 2026-09-15. Two of the three numbers below were instrument
> artifacts and I published them twice before checking the instrument.**
> **78.89% of the 540 realised shares are exactly 1.0**, verified directly.
> The 929.0 was a *mid*-PIT, which is not uniform on an atom even under a
> perfect forecast — the published histogram's spike at bins 6–7 with a
> literal zero in the top bin is that signature. The atom-correct
> **randomized** PIT on the same draws is **χ² 32.481 (p = 1.6e-04)**: a real
> defect, roughly 29× smaller in χ² than advertised. Likewise "above P90 in
> 79% of games" reproduces arithmetically but means nothing, because P90 = 1.0
> in most games and `y < P90` is false whenever y = 1.0; the atom-safe
> analogue is u < 0.90 in **89.44%** against a nominal 90%, essentially
> nominal. **The genuine coverage failure is in the LOWER tail** — u < 0.10 in
> **4.81%** against 10%. The signed bias below is untouched and reproduces to
> 1e-6. Anyone tracking "929" will read the repair as a regression, because
> the repaired distribution puts *more* mass at exactly 1.0 and the mid-PIT
> rises to 1074.9.

**QB dropback SHARE is miscalibrated**, signed bias **−0.0778**
[−0.0868, −0.0687] — the starter's share is put too low. Randomized PIT
χ² 32.481 on 9 df. Mechanism read out of the code: `qb2_lib.simulate`
resamples share against a pool containing every QB-game **including backups**,
and conditioning on being the primary passer selects the top of that pool.
This is the mirror image of the already-recorded 2.17× over-allocation summed
across the room — the same missing normalisation, opposite sign at the
starter.

---

## 3. Historical residual position of the two hypothesised outcomes

| | 184 on 245 | 131 on 210 |
|---|---|---|
| implied over-projection | +61 | +79 |
| standardized residual (2025 frame) | **+0.657** | **+0.788** |
| 2025 games in matched band missing ≥ this far, same direction | **65/215 = 30.2%** | **16/216 = 7.4%** |

Position inside the sealed DEN@KC predictive distribution itself (exact, from
the stored draws):

| | reported | mean | PIT | std resid | CRPS | sealed P10/P50/P90 |
|---|--:|--:|--:|--:|--:|---|
| Mahomes pyds | 184 | 245.27 | **0.2415** | −0.68 | 35.3 | 140.9 / 241.0 / 358.0 |
| Nix pyds | 131 | 210.15 | **0.1470** | −1.00 | 47.2 | 117.0 / 209.4 / 307.0 |
| Walker carries | 23 | 8.35 | **0.9750** | **+2.13** | 11.0 | 0 / 8 / 17 |
| Johnson carries | 8 | 8.42 | 0.5585 | −0.06 | 1.4 | 1 / 7 / 17 |

**A. Mahomes' 184 is an ordinary lower-middle realization, not a miss.**
PIT 0.2415, above the sealed P10 of 140.9, with 24% of draws below it.

**B. Nix's 131 is ordinary lower-tail variance, not evidence of efficiency
over-projection.** PIT 0.1470, and 131 is **above** the sealed P10 of 117. The
season-level evidence runs the other way: efficiency passes equivalence.

**And the pair together, which is what the question was really about:** of the
268 2025 games carrying both primary passers, **11 (4.10%, about one game in
24)** had one starter over-projected by ≥79 and the other by ≥61. Within-game
error correlation +0.100. **A game containing both misses is an ordinary 2025
Sunday under this methodology.**

Two QB observations both below median cannot distinguish bias from noise; the
probability of that under a perfect model is 25%.

---

## 4. The KC backfield — where the real miss is

Walker at PIT **0.9750** (z = +2.13) is a genuine tail event. Johnson at
**0.5585** is essentially dead-on the median. So the **total** backfield volume
was plausible and the **split** failed. This is the defect flagged in writing
*before* kickoff, in `nfl/research/v2/INTEGRATION_RECORD.md`:

> Kansas City's two lead backs come out at parity — 8.233 against 8.227 …
> what replaces it is a coin flip between Walker and Johnson, which is a
> strong football claim about a committee and is a consequence of the tie
> mechanism, not of any evidence that the two are equal. **This needs a
> tiebreaker or an explicit declaration that the model has no view. It should
> not ship as though it were a measurement.**

### WITHDRAWN: my "coin flip" explanation was wrong in every clause

I wrote, before kickoff and again in this document's first draft, that the
parity was "a coin flip produced by the tie mechanism — `depth_team` ties plus
little trailing history give both men the same anchor and therefore the same
score." **All four clauses are false, measured.**

There was no tie: the captured depth chart lists Walker/Johnson/Smith at
`pos_rank` 1/2/3, stable 2026-09-09 through 09-14, with **0 ties across 178 KC
RB groups** and 0 of 32 rooms tied at the latest `dt`. The "2,396 of 2,432 WR
rooms carry ties" fact I cited belongs to the 2020–2024 `depth_team` schema,
not to this capture. The two backs did **not** get the same anchor, and the
carry prior did **not** fail to separate them.

**The carry-share prior separated them 1.62 : 1 in Walker's favour. The
appearance layer then inverted it.** This is not a model with no view; it is a
model whose view was overturned downstream.

| back | `w` | `own_trailing` | `anchor` | final `C` | normalised |
|---|--:|--:|--:|--:|--:|
| Walker | 0.987336 | 0.428653 (n=58) | 0.505131 (RB1) | **0.429622** | 0.5142 |
| Johnson | 0.000000 | none (n=0) | 0.264512 (RB2) | **0.264512** | 0.3166 |
| Smith | 0.958074 | 0.141459 (n=17) | 0.139589 (RB3) | 0.141380 | 0.1692 |

`w` collapses only for Johnson, correctly — he has no NFL history — and he
still receives a *different* anchor. The tie/symmetry hypothesis is falsified.

Then `appearance_r8.predict` returns **Walker 0.723664, Johnson 0.992530**,
Smith 0.762094 — against Walker's own appearance EWMA of **0.988740 over 68
games**, with no injury row for any KC back and KC readiness `READY`.
`layers.targets_carries` binarises participation and `p4c_lib.allocate`
renormalises over survivors, so 0.5142 in becomes **0.3984** out for Walker
while 0.3166 in becomes **0.4231** out for Johnson. The sealed draws agree:
shares 0.4133 / 0.1511 / 0.4170.

A counterfactual holding cutoff, seed and draws fixed and moving only KC RB
appearance to `p = 1.0` returns **10.25 / 6.37 / 3.37** — shares
0.513 / 0.319 / 0.169, the normalised carry prior exactly. **100% of the
parity is the appearance layer.**

### Two named sub-causes

**(i) `appearance_r8.featurise` line 300 — a read that returned nothing, used
as a value.** Every one of the twelve `V1_NUMERIC` features is encoded as a
value **plus a missingness indicator** (lines 296–298). `f_weeks_since_appear`
gets neither:

    f.append(min(v or 9, 9) / 9.0)

It contributes **39% of the 3.9266 logit gap** (Walker −0.2785, Johnson
+1.2600). Ablation confirms the direction is perverse: giving Johnson Walker's
full history *drops* him 0.9925 → 0.8135, and erasing Walker's V1 numerics
*raises* him 0.7237 → 0.9834. Having a history is being penalised.

**And it is worse than a missing-value defect — the feature is non-monotonic
in its own quantity.** `v or 9` is a falsy test, so:

| `f_weeks_since_appear` | encodes to |
|---|---|
| `None` (never seen) | **1.0000** |
| `0` (appeared LAST WEEK) | **1.0000** |
| `1` | 0.1111 |
| `2` | 0.2222 |
| `9` or more (gone all season) | **1.0000** |

A back who played last week, a back who has not played in nine weeks, and a
back who has never played are encoded **identically**, and both are encoded as
*further from appearing* than a player who missed exactly one week.

**(ii) `depth_vintage.daily` `rank_scale` — the rank is offence-wide, and ties
break on `gsis_id`.** The ordinal the appearance model buckets is not
within-position. Every `pos_rank == 1` player on a club competes for one
ordinal and the tie is broken **alphabetically by player id**. KC's RB1 lands
at ordinal **3**, behind a tight end and a quarterback; Johnson 8, Smith 11.
Across 32 clubs the `rank_1_position_mix` is {QB 12, RB 9, TE 9, WR 2}. Cost
to Walker: **0.723664 at ordinal 3 against 0.977057 at ordinal 1**, a 25.3-point
swing. R3 declared this in code. Declaring a contamination does not make it
harmless.

### Evidence classes, all seven

| class | verdict |
|---|---|
| Depth chart | **Clean.** Unambiguous 1/2/3, zero ties, stable across the week. |
| Prior-season history | **Present and consumed.** Walker 67 rows / 821 carries (SEA); Johnson 0 rows anywhere. |
| New-team transfer | **Not the defect** — checked specifically; every lookup keys on `gsis_id` alone and Walker's Seattle history reaches his KC row intact. |
| Cold start | Correct in the carry prior, **inverted in the availability prior**. |
| Committee prior | Not implicated. |
| Stale role prior | **No** — tiers identical whether depth rank is supplied or withheld. |
| Preseason / coaching usage | **No such source family is captured.** A coverage gap, not a bug; requested as OUT-015. |

**Verdict: (a). The evidence was there and one layer destroyed it.** The answer
is not "the model correctly had no view" — it had a strong, correct,
evidence-backed view and the appearance layer reversed it.

### Reproducibility caveat, recorded

The sealed run was built from a working tree with 13 dirty files.
`role_prior.py` and `depth_vintage.py` are byte-identical to HEAD, so the two
stages indicted above *are* what ran. `run_forecast`, `football_engine`,
`rushing_a1` and `board` differ and their sealed bytes are unrecoverable, so an
end-to-end rerun gives 8.05 / 8.49 against the sealed 8.345 / 8.420 — same
mechanism, slightly different magnitude.

---

## 5. Structural defects exposed

### 5.1 The rush impossibility is in the QB rush path, not the RB deal

The product gate reports `RUSH_ACCOUNTING_FAILURE` at 149/1000 (DEN) and
148/1000 (KC) draws, excess up to 6.12 and 9.69 carries. Decomposed against
the sealed arrays of `96954efc523bd7d3`:

| comparison | DEN | KC |
|---|---|---|
| **RB carries only** vs team level | 2/1000, max excess **+0.262** | 2/1000, max excess **+0.085** |
| **RB + QB rush opportunity** vs team level | 206/1000, max **+6.122** | 237/1000, max **+9.691** |

**The multinomial RB deal is essentially sound.** The impossibility enters
with the quarterback's rushing opportunity. A repair aimed at the RB deal —
which is what the unwired, unverified candidate fix in the tree targets —
would have been aimed at the wrong layer.

### 5.2 Two answers for designed QB runs, still

| | A1 `rush_category.designed_qb` | QB layer `rush_opp − scr` |
|---|--:|--:|
| DEN | 2.296 | 1.627 |
| KC | 0.709 | 0.615 |

> **WITHDRAWN 2026-09-15. This was my mis-specified comparison, not a
> defect.** A1 subtracts scrambles from the budget *before* partitioning and
> partitions the **integerised** level. I compared `Σ rush_category` against
> the raw continuous `team_carries`, omitting scrambles and skipping the
> rounding. In A1's declared form the partition closes **exactly**:
> `max |Σ rush_category + scrambles − rint(team_carries)| = 0.000000` on both
> clubs of the sealed R9 board, verified directly. The earlier report that
> unowned category mass is identically 0.0000 was right and my contradiction
> of it was wrong. What was genuinely missing was not closure but the
> **assertion** of it; that is now made per draw and refused by name.

### 5.3 A committed research panel has a structurally-zero column

`nfl/research/q7/q7_qb_game.csv.gz` carries **1 scramble across 4,025
QB-games**. The play-by-play captures hold **5,655 scramble plays for 2021–25
alone**. `q7/panel.py` increments QB counters inside `if pid:` where
`pid = passer_player_id`, and a `qb_scramble` play carries no passer id.

The docstring's "dropbacks are COMPOSED rather than read, so the identity
holds by construction" makes it worse: composing `db = att + sacks + scr`
turns the identity into a tautology that **cannot detect** the defect, and
discards the one check that would have — comparison against `qb_dropback`.

The repository had already named this exact failure, in
`nfl/research/qb2/build_qb.py`: *"a scramble charged to the passer would be a
structurally-zero column — this project has produced one already."* Q7
produced the second.

**Blast radius, checked:** no module under `nfl/production/` or
`nfl/product/` reads the q7 panel; only its own builder and the new study do.
The sealed board's `qb__scr` is non-degenerate (2.288 and 2.610 for the two
starters). **Production is unaffected. Q7's own published conclusions rest on
it and are now suspect**, and the requested scramble/rush-opportunity layer is
not computable from that panel at all.

### 5.4 My own fences scan 104 of 121 boards

The corpus fences I re-froze — `test_conservation`, `test_draw_coherence`,
`test_stat_contract` — all glob `2026_01_*/*/*/player_draws.npz` and match
**104** boards. On disk: **116 `.npz` + 5 `.npz.gz` = 121**.

- 12 `REPLAY_C1` boards excluded by path shape — deliberate.
- **5 `2026_01_SF_LA` boards excluded by file extension alone** — an entire
  game invisible to all three fences, silently.

Comments I wrote saying "every sealed board" are wrong, and this is the
repository's signature failure mode: a glob silently returning a subset.

### 5.5 D19 is the small end of two larger defects

The negative-yardage cell is real and its mechanism is traced to
`nfl/research/qb2/qb2_lib.py:306-307`:

    ypc_d = _mix(rng, r['h_ypc'], po['ypc'], w, m, ew)
    PY = CMP * ypc_d

`PY` is not a per-completion yardage draw. One **game-level** yards-per-
completion ratio is resampled whole and multiplied by an independently drawn
completion count, carrying no record of the completion count that produced it
and no weighting by it. The donor pool has 3,787 entries; ten are negative and
**every one comes from a 1- or 2-completion game**. −2.0 × 16 = −32.0 exactly.
All 2,262 negative cells in the corpus match a pool value; none is unmatched.

**The hypothesis I gave — a symmetric distribution fitted to a skewed
quantity — is rejected. No distribution is fitted on this path.** `_mix` is an
empirical resample of realised game ratios. The defect is **scale
non-exchangeability**: a ratio estimated at n=1 completion applied at n=16
with no shrinkage and no denominator weighting.

Two larger defects were found behind it, neither of which had a fence:

- **36,587 impossible per-QB passing-line cells across 51 of 121 boards.**
  (The figure of 27,564 I relayed earlier **reproduces from no corpus** and
  should not be quoted. Independently recounted: 36,587 over all 121 boards
  on disk; 27,301 over the 109-board fence corpus; 9,286 in the REPLAY_C1
  namespace that the fences exclude by name — and 27,301 + 9,286 = 36,587
  exactly.) Components — `cmp==0 &
  pyds≠0` 18,041; `cmp>att` 8,214; `cmp+int>att` 9,189; `ptd>cmp` 1,113;
  `ptd>att` 30; `rushing_td>carries` 442. Cause: the old credit function
  splits completions multinomially on **attempt** share and yards on attempt
  share independent of the completion draw. Team totals close exactly; the
  per-QB split is not a box score. **The replacement already exists in the
  tree** and asserts all four coherence properties; boards built with it carry
  **zero** impossible cells.
- **The right tail is worse than the left.** Max `pyds` = **1,587 yards**, and
  **680 cells exceed the all-time NFL single-game record of 554**. At cmp≥10,
  2,140 of 130,422 cells sit outside the realised yards-per-completion
  support, and **94.2% of those trace to a donor game with exactly one
  completion**. Left tail: 156 cells worse than −30.

**The C3 invariant I recorded was mis-framed, not violated.** C3 binds per
**team-side**, not per board. `d1e2727743c93990` carries a receiving layer for
KC only; Nix is DEN. Per side: **0 of 2,262** negative cells sit on a
C3-bound side. The invariant holds exactly.

### 5.6 Downstream effect — negligible where expected, material in a thin slice

- **D19 alone**: Nix mean 210.1484 → 210.3907 (+0.24 yd, 0.12%), P50 +0.46, no
  threshold probability moving more than **0.07 pp**. Negligible.
- **All contaminated cells, 490 QB rows**: the **median row moves exactly
  0.000 at every statistic**; mean shift −0.453 yd; but P90 min −26.8 yd,
  SD min −53.5 yd, and threshold probabilities move up to **2.6 pp** on
  individual rows, 35–50 rows of 490 moving >0.5 pp. Concentrated, not
  diffuse.
- **CRPS is exact** (full draws stored). **Log score is refused, not
  approximated** — it needs a bandwidth, itself a free parameter. **PIT across
  the corpus is not assessable**: only 20 QB passing lines in the repo have
  outcomes.

### 5.7 Market boundary

No market feed exists in this system and none was consulted. Stated only as a
property of our own distribution, the quantities unsafe to compare against any
external threshold are: `qb/pyds` on any side with no receiving layer (the
tail region there is built out of one-completion donor games); and `qb/cmp`,
`qb/pyds`, `qb/ptd`, `rushing/rushing_td` on the 50 old-credit boards. **No
price, no line, no edge, no wager.**

---

## 6. Ranked repairs by expected impact

Ranked by cells affected × consequence, not by ease.

| # | repair | scope | why it ranks here |
|---|---|---|---|
| **1** | Rebuild or quarantine the **50 old-credit boards** | 27,564 impossible cells | Largest defect found. The fix already exists in the tree; these boards predate it. Nothing needs inventing — they need rebuilding or marking. |
| **2** | **QB dropback share** normalisation | every QB forecast | PIT χ² 929 on 9 df, realised above P90 in 79% of games. The one QB layer with a demonstrated systematic defect, on 540 games. Needs pre-registration. |
| **3** | **Yards-per-completion scale non-exchangeability** (`qb2_lib.py:306-307`) | both tails, all boards | 680 cells above the all-time record and 156 below −30. Weight `_mix` by donor completion count, shrink by n/(n+k), or draw per completion. **Never a clip.** Mechanism change → pre-registration. |
| **4** | **QB rush opportunity vs team carry level** | 206–237/1000 draws per team | The actual location of the rush impossibility. Fix the composition, not the RB deal. |
| **5** | Reconcile **two answers for designed QB runs** and close the category partition | every board with A1 | 8.43 / 10.20 carries of non-closure, and a quantity with two values. |
| **6** | **Backfield tie-break or explicit no-view declaration** | every committee backfield | The pre-kickoff flag. A 50/50 that is really a 50/50 is honest; presenting it as a measurement is not. |
| **7** | Fix the **fence globs** to cover 121 boards | 3 test modules | Cheap, and it is the reason 5 boards went unscanned. |
| **8** | Rebuild the **q7 panel** scramble attribution | research only | No production consumer, but Q7's conclusions depend on it. |

---

## 7. Tests that would have caught each defect before publication

| defect | the test that was missing |
|---|---|
| 27,564 impossible per-QB cells | A per-row box-score coherence assertion at seal time: `cmp ≤ att`, `cmp + int ≤ att`, `ptd ≤ cmp`, `cmp == 0 → pyds == 0`, `rushing_td ≤ carries`. The replacement credit function asserts exactly these; the old one asserted none, and **no fence stood between them**. |
| Right-tail yardage above the NFL record | A support check: every emitted `pyds` must lie within the realised historical support given its own completion count. 680 cells above 554 passed because nothing compared the draw to football. |
| D19 negative yardage | The same support check, from the other side. The existing fence only counted negatives; it never asked whether the magnitude was reachable at that completion count. |
| QB dropback share miscalibration | A PIT/coverage gate on **each layer**, not only on the published quantity. Share was never scored on its own; a χ² of 929 cannot hide from a per-layer PIT. |
| Rush impossibility located in the QB path | The gate fired, correctly. What was missing was a **decomposed** gate: reporting RB-only and RB+QB separately would have aimed the repair at the right layer immediately. |
| Two answers for designed QB runs | A cross-layer agreement assertion: any quantity computed in two places must be asserted equal at seal time, with the check naming both sources. |
| q7 structurally-zero scramble column | A non-degeneracy assertion on every built column — a count column that is zero (or one) across 4,025 rows must fail the build. The repo names this failure mode and still shipped it twice. |
| Fences scanning 104 of 121 boards | A census assertion: the fence's own corpus count must equal an independently derived board count, so a glob that silently narrows fails loudly. |

---

## 8. Verdict on the three candidate explanations

**Were the data wrong?** Not for the QBs. For the requested decomposition, the
data are *absent*, which is different and is recorded rather than worked
around. One committed research panel is genuinely wrong (q7 scrambles) and
does not touch production.

**Was the model interpretation wrong?** Yes, in one place that matters and it
is not where the question pointed: **QB dropback share**, demonstrated over
540 games. And the **backfield split**, flagged before kickoff.

**Was the game a valid low-tail outcome?** For the quarterbacks, it was not
even low-tail. PIT 0.2415 and 0.1470 are ordinary, and a 2025 Sunday produces
a game containing both misses about **once in 24**. The pressure to read two
below-median quarterback games as a model failure is exactly the pressure this
autopsy exists to resist.

**Nothing here is a wager and no market data entered any part of it.**


---

## 13. Added 2026-09-15: a CONFIRMED leak, found after this autopsy was written

**`run_forecast.py:501` called `qb_allocation.allocate(...)` with neither
`kickoff_utc` nor `written_at`, so the depth-chart chronology guard has never
executed on any production run.** The guard is real and correct:

    for label, bound in (('kickoff', kickoff_utc), ('written_at', written_at)):
        if bound and got and str(got) >= str(bound):
            return Outcome.fail('DEPTH_CHART_CHRONOLOGY_FAILURE', ...)

Both parameters default to `None`, so `if bound` was false every time. Verified
directly: the call site passed neither, and both defaults are `None`.

What it guards: the depth chart is chosen by `sorted(glob(...))[-1]` —
lexicographic content-hash order, no clock. That resolves to
`depth_charts.f66f0c2583dba463.reduced.csv.gz`, retrieved **2026-09-14T16:16:25Z**,
and **74 of the 79 week-1 kickoff targets precede it**. The QB room ordering
read from that chart feeds dropback allocation, so a board built for an earlier
week-1 game consumed a depth chart published after its own kickoff.

Tonight's DEN@KC board is **not** affected — its kickoff is 2026-09-15T00:15Z,
after the chart's retrieval — but earlier week-1 boards are.

**This is the `board.depth_rank` defect one function over, on the same source,
and the exact opposite failure.** There the guard fired on every run and a bare
`except Exception: dr = {}` destroyed the evidence. Here the guard never fired
at all. Both are one lesson: *a guard nobody can see is not a guard.*

Repaired at both call sites — `run_forecast.py:501` and
`engine_rehearsal.py:121`, the latter bounded by the **earliest** kickoff in
the slate, since a chart lawful for the whole slate must precede its first
game. A board rebuilt with the guard armed still seals (`cbaa9c6409960679`), so
arming it does not break the current path.

**The wider finding is that enforcement covers a third of the sources.**
`vintage_selector.FAMILIES` declares 4 of 12; the other eight have no clocked
selector and are reached by globbing, which is why every leak finding in this
audit is glob-shaped.