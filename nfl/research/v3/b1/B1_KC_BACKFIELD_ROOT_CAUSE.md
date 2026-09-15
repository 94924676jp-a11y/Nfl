# B1 — Kansas City's backfield on `d1e2727743c93990`: what pregame evidence existed, and what the pipeline did with it

**Question.** Given only bytes lawfully available before the board's cutoff
`2026-09-14T20:58:33Z`, was the information to separate Kenneth Walker III
(`00-0038134`) from Emmett Johnson (`00-0041013`) present, and did the pipeline
use it?

**Answer: (a). The evidence was there, the role prior consumed it correctly, and
the appearance layer destroyed it.** The carry-share prior separated the two
backs **1.62 : 1 in Walker's favour** and the board reported parity. The parity
is not a coin flip, is not produced by a tie, and is not the model honestly
declining to have a view. It is an inversion, and it is attributable in full to
one layer.

The game result was not used, fetched, or reasoned from. Verified absent:
`nfl/research/postgame/pbp_2026.1415dd98ba7f701a.csv.gz` holds 1,738 rows across
21 `posteam` values and **0 rows for KC**. The 23/8 split asserted in
conversation was never an input; everything below is a forward decomposition of
the sealed board.

---

## 0. What ran, and how faithfully I reproduced it

`run_status.json` records `code_version`
`2dc44abc8b316f2f23ede1bc9eb7015c6b19e14a+src1[2885ba3e58da646c]` — the sealed
run executed at commit `2dc44abc` with **13 dirty source files**. That matters,
and I got it wrong once before checking.

Two of those dirty files are byte-identical to the current working tree:

| file | sealed sha256 (16) | HEAD sha256 (16) | bytes | same? |
|---|---|---|---|---|
| `nfl/production/nonqb/role_prior.py` | `bf927f5a46210546` | `bf927f5a46210546` | 16,871 | **yes** |
| `nfl/production/nonqb/depth_vintage.py` | `b18d88fe48a49054` | `b18d88fe48a49054` | 30,762 | **yes** |
| `nfl/production/run_forecast.py` | `5325be5822393ea6` | `91780b92c273a718` | — | no |
| `nfl/production/nonqb/football_engine.py` | `578a4fcf7f858041` | `fe763c355385a6a7` | — | no |
| `nfl/production/nonqb/rushing_a1.py` | `51b2d38b4bce79b5` | `f87bf3a7acd5ea7e` | — | no |

`layers.py` is not dirty and is unchanged: `481f005f682cd721…`, verified at the
start and at the end of this task.

**Consequence.** The two stages this report indicts — the role prior and the
depth-rank scale — are byte-identical to what ran, so the instrumented values
below *are* the sealed run's values. The end-to-end rerun is not identical
(`run_forecast`, `football_engine`, `rushing_a1` and `board` differ and their
sealed bytes are unrecoverable), so my rerun gives Walker 8.05 / Johnson 8.49
against the sealed 8.345 / 8.420. Same mechanism, same direction, slightly
different magnitude. Every number is labelled with which run it came from.

**A correction made in the course of this work.** I first reconstructed the
sealed role prior from the *committed* `role_prior.py` at `2dc44abc` (196 lines,
pre-R3 two-pass) and derived C = 0.4296 / 0.1466 / 0.1396. That is wrong and is
withdrawn. The dirty file that actually ran is the R3 single-scale version, and
the correct sealed values are in §3.

---

## 1. The seven evidence classes

### 1. Depth chart — **evidence existed, unambiguous, and there is no tie**

Raw vendor bytes, `nfl/vintage/depth_charts.f66f0c2583dba463.raw.csv.gz`,
518,581 rows, sealed into the forecast at `retrieved_at 2026-09-14T16:16:25Z`.
Newest `dt` slice `2026-09-14T13:53:31Z` — seven hours before the cutoff:

```
dt=2026-09-14T13:53:31Z team=KC pos_grp='3WR 1TE' pos_abb=RB pos_slot=11
  Kenneth Walker III  00-0038134  pos_rank=1
  Emmett Johnson      00-0041013  pos_rank=2
  Brashard Smith      00-0040078  pos_rank=3
```

Stable on every one of the six `dt` slices from 2026-09-09 to 2026-09-14. Across
all **178** `(dt, pos_grp)` KC RB groups in the capture: **0** groups with more
than one player at `pos_rank 1`. At the latest `dt` across all 32 clubs: RB 0/32,
WR 0/32, TE 0/32, QB 0/32 rooms tied at rank 1. The reduced blob the pipeline
reads carries the same 1/2/3.

The known tie fact does **not** apply here. "2,396 of 2,432 WR rooms carry 2–4
players tied at `depth_team` rank 1"
(`nfl/research/v2/INTEGRATION_RECORD.md:87`) describes the **2020–2024 nflverse
weekly** schema, where `depth_team` ranks within `depth_position`. The 2026
capture is the ESPN daily schema, where `pos_rank` ranks within `pos_abb`.
`depth_vintage.py:316-318` already records 0 tie groups on all six 2026 reduced
blobs and across 170/174/177 `dt` slices of the raw files.

**Verdict: evidence present and clean.**

### 2. Prior-season history — **evidence existed and was consumed**

The rushing-capable panel is `nfl/research/inputs/panel_p3.csv.gz` (2020–2025,
57,670 rows), enriched to `panel_enriched.pkl` (83,144 rows) by
`nfl.production.derived`. `q7_qb_game.csv.gz` is QBs; `q7_recv_game.csv.gz` is
the receiving companion and agrees.

| back | panel rows | seasons / teams | carries | 2025 carry share | 2025 snap share |
|---|---|---|---|---|---|
| Walker | 67 (58 appeared with a carry share) | 2022–2025 **SEA** | 821 | 0.385 – 0.440 | 0.42 – 0.55 |
| Johnson | **0** | — | — | — | — |
| Smith | 17 | 2025 **KC** | 44 | 0.000 – 0.522 | 0.05 – 0.53 |

Johnson has zero rows in `panel_p3`, zero in the enriched panel, and zero in
`q7_recv_game`. He is a genuine cold start. Walker is one of the most
history-rich backs on the slate.

**Verdict: evidence present, and §3 shows the role prior did reach it.**

### 3. New-team transfer — **checked specifically; not a defect here**

Walker changed clubs (SEA → KC) and all of his history sits under the old team,
so this is exactly the shape where a `(player, season, team)` key silently
returns nothing. It does not happen. Every trailing lookup on this path keys on
`gsis_id` alone:

- `role_prior.build` — `trail[r['gsis_id']].append(s)`
- `p4c_params.class_point_forecast` — `hist.setdefault(r['gsis_id'], []).append(v)`
- `appearance_r8.predict` — `hist[r['pid']].append(r)`

Measured at the real cutoff, Walker's Seattle history reaches his Kansas City
row intact: class history `n_own = 58`, trailing snap `n = 8`, appearance frame
`n_prior = 68`, and a fully populated V1 feature block (`f_rate3 = 1.0`,
`f_rate5 = 1.0`, `f_rate_ewma = 0.98874`, `f_prev_snap = 0.42`). No empty read,
no silent zero.

**Verdict: not the cause. Explicitly cleared.**

### 4. Rookie / cold start — **distinguishable, and in the carry prior it is correct**

With no history, `role_prior.weight` returns `w = 0` and therefore exactly the
tier anchor. Johnson receives the measured historical **RB2 mean carry share,
0.264512**, against Walker's 0.429622. That is distinguishable from an
established back, and it is the right behaviour: a population mean standing in
for a player about whom nothing is known.

**In the appearance layer the same cold start runs the other way**, and that is
the defect. See §4.

**Verdict: correct in the share prior, inverted in the availability prior.**

### 5. Allocator tie / symmetry — **`w` does not collapse; this is not a tie**

Full instrumented values in §3. Neither `w` collapses to 0 for Walker, the
anchors differ, the scores differ, the tiers differ, and the outputs differ.

**Verdict: not the cause. The earlier hypothesis is falsified — see §6.**

### 6. Stale role prior — **no**

The prior is built at ordinal cut `202601` from rows strictly earlier, so no
2026 outcome can enter (`p4c_params.params` refuses outright if a panel row is
from the forecast season). The depth rank is selected point-in-time with
`as_of = 2026-09-14 20:58:33+00:00`, returning `PASS[DEPTH_RANK_OK]` over 119
players from the `2026-09-14T13:53:31Z` snapshot — the newest lawful one.

The sealed run's `run_forecast.py` bytes are unrecoverable, so I cannot say
whether it supplied the depth rank or swallowed a `VINTAGE_CLOCK_UNRESOLVED`
refusal (`board.depth_rank` with no `as_of` raises — confirmed by running it).
**It does not matter**: I measured `assign_tiers` both ways and the tiers, and
therefore C, are identical (§3).

**Verdict: not the cause, and robust to the one thing I cannot recover.**

### 7. Preseason / coaching-usage signal — **not captured at all**

`nfl/vintage/` holds ten source families: `delivered_injury_evidence`,
`depth_charts`, `espn_injuries_json`, `hardrock_market_snapshot`, `injuries`,
`official_inactives`, `official_injury_report`, `official_status_evidence`,
`schedules`, `weekly_rosters`. Seven were sealed into this forecast
(`forecast_artifact.source_captures`).

**None carries preseason snap counts, training-camp or joint-practice usage,
first-team rotation, or coaching statements.** A club's stated plan for a
newly-acquired lead back is exactly the evidence a human would use here, and the
system has no channel for it.

This is a **coverage finding, not a bug**. Request lodged as OUT-015 in
`docs/AGENT_OUTBOX.md` with the exact sources and dates.

---

## 2. Where the carries actually come from

```
role_prior.build            tier anchors + shrinkage constants   (snap share AND carry share)
role_prior.assign_tiers     one continuous scale -> tier          [w_snap]
p4c_params.class_point_forecast -> role_prior.weight -> C         [w_carry]
layers.appearance -> appearance_r8.predict                        p(appear)
layers.participation        out[pid] = a * s
layers.targets_carries      W = clip(C + resample(add_pool), 0, 1)
                            A = (participation > 0)               <-- THE MASK
  p4c_lib.allocate (simplex)  S_i = W_i A_i (1 - other) / sum_g(W A)
football_engine             multinomial deal of A1's `rb` budget on S
```

`rushing_a1` partitions the rush-play budget across *categories*
(kneel / designed_qb / rb / wr / te / fringe), not players. The within-room
split is `S`, and `E[carries_i] = budget x S_i`.

---

## 3. The instrumented values, as requested

Measured by running the real pregame path at the board's own cutoff with the
lawful clock. Both modules are byte-identical to the sealed run.

### (a) `role_prior.assign_tiers` — the **snap-share** scale that sets the tier

`k_snap[RB] = 0.882360`. Anchors: RB1 0.598097, RB2 0.376784, RB3 0.237735,
RB4 0.196390.

| back | `w` | `own_trailing` | `anchor` | `score` | tier | basis |
|---|---|---|---|---|---|---|
| **Walker** | **0.900662** | **0.493750** | **0.598097** (RB1) | **0.504116** | **1** | `shrunk_trailing_and_depth` |
| **Johnson** | **0.000000** | **None** | **0.376784** (RB2) | **0.376784** | **2** | `depth_chart` |
| **Smith** | **0.900662** | **0.175000** | **0.237735** (RB3) | **0.181232** | **3** | `shrunk_trailing_and_depth` |

`ordering = single_scale_shrunk_expected_snap_share`, `degraded = False`.

With the depth rank **absent** (the state I cannot rule out for the sealed run)
all three anchor on RB4 = 0.196390 and score 0.464226 / 0.196390 / 0.177153 —
**the same tiers 1 / 2 / 3.**

### (b) `role_prior.weight` — the **carry-share** scale that sets `C`

`k_carries[RB] = 0.743941`. Tier means: RB1 0.505131, RB2 0.264512,
RB3 0.139589, RB4 0.110964.

| back | `w` | `own_trailing` (ewma of own carry share) | `anchor` | **final score `C`** |
|---|---|---|---|---|
| **Walker** | **0.987336** | **0.428653** (n_own = 58) | **0.505131** (RB1) | **0.429622** |
| **Johnson** | **0.000000** | **None** (n_own = 0) | **0.264512** (RB2) | **0.264512** |
| **Smith** | **0.958074** | **0.141459** (n_own = 17) | **0.139589** (RB3) | **0.141380** |

Normalised across the KC room: **Walker 0.5142, Johnson 0.3166, Smith 0.1692.**
**Walker : Johnson = 1.624 : 1.**

`w` collapses to 0 for exactly one back — Johnson, correctly, because he has no
history — and he still receives a *different* anchor from Walker. There is no
tie and no symmetry.

### (c) What the appearance layer then did

`layers.appearance` → `appearance_r8.predict`, `clock 2026-09-14T20:58:33+00:00`:

| back | **p(appear)** | `rank` seen by the model | `n_prior` | `app_ewma` | state |
|---|---|---|---|---|---|
| **Walker** | **0.723664** | 3 | 68 | **0.988740** | `KNOWN_HEALTHY` |
| **Johnson** | **0.992530** | 8 | **0** | **None** | `NO_HISTORY` |
| **Smith** | **0.762094** | 11 | 17 | 1.000000 | `KNOWN_HEALTHY` |

No KC running back carries an injury row. The eleven KC rows in
`injuries.66e960ec81fccc6e.csv.gz` are Jones, Mahomes, Sneed, T. Smith,
Cochrane, Conner, Rice, Worthy, Simmons, Gillotte, Thomas. Readiness for KC is
`READY`. **Nothing about health is driving this.**

`reliability_weight_mean = 0.0` and `reliability_weight_max = 0.0`: in week 1
`n_cur = 0` for every player, so R8's current-season participation block
contributes nothing by design, and the whole prediction rests on the depth
bucket, the R7 history block and the V1 block.

### (d) The mask, and the inversion

`p_available` in the 1,000 draws: Walker **0.732**, Johnson **0.995**, Smith 0.742.

`layers.targets_carries` binarises participation (`A = (A > 0)`) and
`p4c_lib.allocate` renormalises over survivors, so every draw in which Walker is
absent hands his share to Johnson.

| | Walker | Johnson | Smith |
|---|---|---|---|
| normalised `C` **in** | **0.5142** | **0.3166** | 0.1692 |
| mean simplex share **out** | **0.3984** | **0.4231** | 0.1636 |

**Order inverted.** Walker loses 22.5% of his prior share; Johnson gains 33.6%.

The sealed board's own stored draws show the identical shape. KC `rush_category/rb`
budget mean **20.194**; `rushing/carries` rows:

| back | mean | P10 | P50 | P90 | P(zero) | implied mean share |
|---|---|---|---|---|---|---|
| Walker | 8.345 | 0 | 8 | 17 | 0.2480 | 0.4133 |
| Johnson | 8.420 | 1 | 7 | 17 | 0.0820 | 0.4170 |
| Smith | 3.052 | 0 | 1 | 9 | 0.4400 | 0.1511 |

0.5142 → 0.4133 and 0.3166 → 0.4170.

---

## 4. Why 0.72 against 0.99

`appearance_r8` is an L2 logistic on standardised features
(`stage_a.fit_logistic`, `predict` applies `(X - mu) / sd`). Re-running the
fitted model on the captured feature rows reproduces the pipeline exactly —
0.723664 / 0.992530 / 0.762094 — so the ablations below are on the real object.

Total logit gap, Walker − Johnson: **−3.9266**.

### Cause A — the absence of a record is scored as evidence of availability

| ablation (one thing moved, everything else held) | p |
|---|---|
| Walker, as the pipeline saw him | **0.723664** |
| Walker, V1 numerics → None (block still present) | **0.983417** |
| Walker, `f_weeks_since_appear` → None only | **0.924229** |
| Johnson, as the pipeline saw him | **0.992530** |
| Johnson **given Walker's full history**, rank held at 8 | **0.813458** |
| Johnson given Walker's history **and** rank 3 | 0.723664 *(= Walker exactly)* |

Handing a player a 68-game record in which he appeared **98.87%** of the time
**lowers** his predicted availability by **17.9 points**. Erasing a veteran's
record **raises** him by **26.0 points**.

**The largest single term is a silent default.** In `appearance_r8.featurise`:

```python
v = blk.get('f_weeks_since_appear')
f.append(min(v or 9, 9) / 9.0)
```

`None` is imputed to **9 — the maximum** — and this feature gets **no
missingness indicator**, unlike all twelve `V1_NUMERIC` features, each of which
appends a paired `_MISSING` flag. Johnson's V1 block is present-but-null, so the
block-level `v1_block_MISSING` flag does not fire for him either.

Standardised logit contribution: Walker **−0.2785**, Johnson **+1.2600** — a gap
of **1.5385**, which is **39% of the entire 3.9266 gap**, from one field whose
value for Johnson is not a measurement.

This is the repository's Class A failure inside a feature: *a read that returned
nothing, used as a value*. The module's own docstring states "NO_HISTORY is not
evidence of availability" and `R7.state_of` keeps the state separate — but only
the `no_history_and_not_depth_listed` cell is declined. The depth-**listed**
no-history cell carries the same selection effect (a player with no frame row
who nonetheless reaches a depth chart has, in training, almost always played)
and is scored rather than declined.

### Cause B — the depth evidence arrives on a position-blind scale

`appearance_r7.featurise` / `appearance_r8.featurise` bucket `rank` into
`r1 / r2 / r3 / r4plus / unlisted`. That `rank` is **not** the vendor's
within-position `pos_rank`. It is `depth_vintage.daily`'s **offence-wide
ordinal** within `(team, dt)` across QB, RB, WR and TE, ordered by
`(pos_rank, slot_sort, gsis_id)`.

KC's four `pos_rank == 1` players are tied and separated only by that
`gsis_id` tail:

```
ordinal  1  TE  00-0030506
ordinal  2  QB  00-0033873
ordinal  3  RB  00-0038134   <- Walker, the unambiguous RB1
ordinal  4  WR  00-0039067
...
ordinal  8  RB  00-0041013   <- Johnson
ordinal 11  RB  00-0040078   <- Smith
```

Across 32 clubs `rank_1_position_mix` is `{QB: 12, RB: 9, TE: 9, WR: 2}` — which
position wins ordinal 1 is effectively arbitrary.

**Cost: Walker at ordinal 1 instead of 3 gives p = 0.977057 against 0.723664 — a
25.3-point swing.**

**This is a tie mechanism, and it is the one the earlier note was reaching
for — but it lives in `depth_vintage.daily` feeding `appearance_r8`, not in
`role_prior.assign_tiers`.** `depth_vintage.py` already declares it under
`rank_scale`: *"It is NOT a within-position depth rank… Declared by R3
2026-09-14, not repaired."* Declared is not harmless: it is worth a quarter of
this back's availability.

---

## 5. Counterfactual arms

Identical cutoff, seed (20260908), draws (1,000) and configuration
(`V1_CANDIDATE_R9`). Only the appearance probability for the three KC backs was
moved. Diagnostic only; nothing in the repository was changed.

| arm | Walker | Johnson | Smith |
|---|---|---|---|
| **baseline** (rerun at HEAD) | **8.05** | **8.49** | 3.38 |
| all three KC backs at `p = 1.0` | **10.25** | **6.37** | 3.37 |
| Walker at his ordinal-1 `p` (0.977057), others untouched | **10.71** | **6.62** | 2.65 |

Removing the availability asymmetry alone moves the room from **Johnson +0.44**
to **Walker +3.88**. In the equalised arm the shares are 0.513 / 0.319 / 0.169 —
**the normalised `C` exactly.**

**So 100% of the parity is the appearance layer. The carry-share prior never
thought these two backs were equal.**

---

## 6. A claim I am withdrawing

`nfl/research/live/2026_01_DEN_KC/REBUILD_ACCEPTANCE.md:154-160` says the parity
is

> a coin flip, produced by the tie mechanism — `depth_team` ties plus little
> trailing history give both men the same anchor and therefore the same score

**Every clause is measured false**:

| clause | measurement |
|---|---|
| "`depth_team` ties" | 0 of 178 KC RB groups tied; 0 of 32 RB rooms at the latest `dt`. `depth_team` is the 2020–2024 schema, not this capture. |
| "little trailing history" | Walker: `n_trailing = 8`, `n_own = 58`, `n_prior = 68`. |
| "the same anchor" | 0.598097 vs 0.376784 (snap); 0.505131 vs 0.264512 (carry). |
| "the same score" | 0.504116 vs 0.376784 (snap); 0.429622 vs 0.264512 (carry). |

It also said the room "needs a tiebreaker or an explicit declaration that the
model has no view." Neither is the right remedy. The model **had** a view, a
strong one, and a different layer overturned it.

---

## 7. Root cause

**One named cause.**

> `nfl/production/nonqb/appearance_r8.py` — the week-1 appearance model scores
> the **absence** of a career record as stronger evidence of availability than a
> 68-game record of 98.87% availability, and simultaneously receives the depth
> evidence as a position-blind offence-wide ordinal that demotes a club's RB1 to
> bucket `r3`. Together these set Walker at 0.723664 against Johnson at
> 0.992530, and the availability mask in `layers.targets_carries` converts that
> into a reversal of a 1.62 : 1 carry-share prior.

Two sub-causes, by file and construct:

1. **`appearance_r8.featurise`, the `f_weeks_since_appear` line** —
   `min(v or 9, 9) / 9.0` imputes a missing value to the maximum and supplies no
   missingness indicator, unlike every other V1 numeric. **39% of the logit gap.**
2. **`depth_vintage.daily`, the `rank_scale` ordinal** — offence-wide, with a
   `gsis_id` tie-break among `pos_rank == 1` players, consumed by
   `appearance_r7.featurise` / `appearance_r8.featurise` as though it were a role
   rank. **25.3 points of Walker's appearance probability.**

**Not causes, each checked and cleared:** depth-chart ties (none exist); a
stale or missing depth vintage (tiers identical either way); new-team history
loss (all lookups key on `gsis_id`); cold start in the carry prior (correct);
`w` collapsing in the allocator (it does not); injury or readiness state (no KC
back carries a row).

---

## 8. The fix, described and deliberately not applied

This was a diagnostic task. Nothing was repaired. `layers.py` is unchanged:
`481f005f682cd72129e6bf02e55cba86913ddffd7d88367743c616e3e11c0108`, verified at
start and end.

1. **Give `f_weeks_since_appear` a paired missingness indicator** and set the
   value to 0 (or the training mean) when absent, exactly as the twelve
   `V1_NUMERIC` features already do. This changes the design matrix, so it
   invalidates the frozen coefficient vector: it is a **registered refit** with
   a predeclaration, not an edit.
2. **Give the appearance model a within-position rank.** Either pass it
   alongside the offence-wide ordinal and fit a separate bucket block, or
   decline the depth bucket for a player whose ordinal is contaminated by a
   cross-position tie at `pos_rank 1`. Changing the ordinal in place would move
   a served feature whose coefficients were fitted on the current scale —
   `depth_vintage.py` says so itself, and it is right.
3. **Reconsider the `NO_HISTORY`-and-depth-listed cell.** The cell whose
   appearance rate is 1.0000 with zero variance is already declined when the
   player is *unlisted*. The listed cell carries the same survivorship: a player
   with no frame row who nonetheless reaches a depth chart has, in the training
   frame, almost always played. Declining it, or widening it, is a
   specification decision that needs a predeclaration.

Which of the three to do first is a decision for the owner, because (1) and (3)
both forfeit a frozen coefficient vector.

---

## 9. Reproduction

```
python3.12  # 3.12 floor, as required
# stage instrumentation (role prior, allocation, appearance):
#   monkeypatch role_prior.assign_tiers / role_prior.weight /
#   p4c_params.class_point_forecast / layers.targets_carries /
#   appearance_r8.featurise / appearance_r8.predict, then
nfl.tools.make_board.build_one(
    2026, 1, '2026_01_DEN_KC', '2026-09-14T20:58:33Z',
    <scratch out dir>, 1000, 20260908, 'V1_CANDIDATE_R9')
```

Scratch outputs were written outside the repository. Nothing was written into
`nfl/research/live/`. The only repository files this task creates are this
report and the OUT-015 entry in `docs/AGENT_OUTBOX.md`.
