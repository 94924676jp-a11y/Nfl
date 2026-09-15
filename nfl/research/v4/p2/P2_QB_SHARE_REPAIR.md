# P2 repair 3 — QB starter / dropback-share calibration

**EXPLORATORY. Not a confirmatory result and not prospective performance.**
2025 is development data in this project. Worse than that for this study:
**four candidate share specifications were compared on this same 540-game
frame before one of them was chosen** — pool-conditioned only, pool and own
history (shipped), a fully role-coherent variant, and an explicit role
mixture. All four are reported in section 4.1; none is hidden. Forward
chaining controls parameter leakage; it does not control specification
leakage. What a confirmatory result would need is in section 11.

Artifacts: `nfl/research/v4/p2/P2_RESULTS.json` (every number below),
`p2_cohort.py`, `p2_run.py`, `nfl/tests/test_qb_share_calibration.py`.

---

## 1. What was asked, and the two-sided verdict

Repair the QB dropback-share miscalibration recorded in
`nfl/research/v3/AUTOPSY_DEN_KC.md` §2 and `nfl/research/v3/h1/
H1_2025_QB_RESIDUALS.md` §1, reproduce it with a failing test first, verify the
mechanism independently, ship the smallest structural fix, register a new
successor candidate, rerun the exact 540-game 2025 cohort, and clear a
**two-sided** bar: share calibration must improve materially **and** end-to-end
passing-yard CRPS must not worsen.

**Both sides clear.**

| bar | before | after | verdict |
|---|--:|--:|---|
| share randomized PIT chi2, 9 df | 32.481 (p = 1.6e-04) | **8.667 (p = 0.469)** | uniformity no longer rejected at the predeclared alpha = 0.01 |
| share signed bias | -0.0778 [-0.0870, -0.0691] | **-0.0190 [-0.0278, -0.0109]** | 76% smaller; both intervals still exclude zero |
| share randomized coverage, u < 0.10 / 0.50 / 0.90 | 0.0481 / 0.4667 / 0.8944 | **0.0852 / 0.5241 / 0.9056** | all three move toward nominal |
| **passing-yard CRPS** | 43.042 [40.754, 45.290] | **41.744 [39.407, 43.984]** | paired difference **-1.298 [-2.198, -0.436]**, block bootstrap over whole games — better, and the interval excludes zero |

**And it costs something, which is section 8 and is not buried:** passing-yard
signed bias moves from **-5.922 [-12.669, +0.734]**, an interval containing
zero, to **+7.538 [+0.902, +14.167]**, an interval that does not. The
incumbent's apparent accuracy on passing yards was two errors cancelling.

The word *calibrated* is not used of either arm. The predeclared TOST on share
bias against a ±0.010 margin returns **NOT_SHOWN_EQUIVALENT** in both arms
(repaired 90% CI [-0.0261, -0.0119]).

---

## 2. The failing test, shown failing before production code was touched

`nfl/tests/test_qb_share_calibration.py`, run against the unmodified engine:

```
test_c_share_pit_is_uniform
       incumbent randomized-PIT chi2 32.481 on 9 df, p = 1.643e-04
  FAIL a starter-conditioned share specification exists  QB_SHARE_CANDIDATE_ABSENT:
       qb2_lib exposes no SHARE_SPEC_STARTER_CONDITIONED, so the incumbent
       unconditional pool is the only path. Its randomized-PIT chi2 is 32.48 on
       9 df (p = 1.643e-04), rejecting uniformity at alpha=0.01.
       Histogram [26, 38, 52, 63, 73, 65, 61, 59, 46, 57].
test_d_share_bias_shrinks
  FAIL a starter-conditioned share specification exists  absent; incumbent signed bias -0.0778
PASSED 13  FAILED 2
```

The same file reproduces the recorded defect to the digit before repairing it
(`test_b`): signed bias **-0.07783625** against `H1_SUMMARY.json`'s
-0.07783625 (agreement to 1e-6), mean realised share 0.97178596, and realised
share below the predictive P90 in exactly **0.2111111** of games.

After the repair the module is 7 functions, 24 checks, `SUITE PASS`.

---

## 3. THE PUBLISHED 929.0 IS MOSTLY THE INSTRUMENT, NOT THE MODEL

This is the first place this work disagrees with its own brief, and it changes
how large the defect is.

The brief and both source documents call the 929.0 a **randomized** PIT. It is
not one. `nfl/research/v3/h1/h1_run.py` scores the share layer with
`discrete=False`, which routes it to `h1_run.cpit` — the **mid-PIT**,
`P(X < y) + 0.5 P(X = y)`.

**78.89% of the 540 realised shares are exactly 1.0**: the quarterback took
every one of his team's dropbacks. A share is a ratio of small integers with an
enormous atom, and a mid-PIT is **not uniform on an atom even under a perfect
forecast**. The signature is visible in the published histogram itself —
`[26, 32, 21, 12, 12, 135, 236, 53, 13, 0]`, a spike in bins 6 and 7 and a
literal zero in the top bin, which is what a single atom does to a mid-PIT.

Recomputed on the same draws with the **randomized** PIT, the instrument a
discrete quantity requires:

| instrument | incumbent | repaired |
|---|--:|--:|
| mid-PIT chi2 (what was published) | 944.593 | **1074.852** |
| randomized PIT chi2, 9 df | **32.481** | **8.667** |

Two consequences, both of which must be carried forward:

1. The real miscalibration is about **29x smaller in chi2** than advertised.
   It is still a real defect: p = 1.6e-04 rejects uniformity comfortably.
2. **The mid-PIT gets WORSE after the repair, 944.6 -> 1074.9**, because the
   repaired predictive distribution puts more mass at exactly 1.0 and a
   mid-PIT punishes that. Anyone tracking the 929 number will read this repair
   as a regression. It is not; the instrument is.

The same atom disposes of the headline "realised share above the predictive P90
in 79% of games". It reproduces exactly — but `P90 = 1.0` in most games, so
`y < P90` is false whenever `y = 1.0`, and that statistic is measuring the atom.
The atom-safe analogue is **u < 0.90 in 89.44% of games against a nominal 90%**,
which is essentially nominal. The incumbent's genuine coverage failure is in the
**lower** tail: u < 0.10 in **4.81%** against 10%, i.e. far too much predictive
mass sitting below the realisation. That is exactly the shape backup
contamination produces, and it is what the repair moves (4.81% -> 8.52%).

**The part of the published finding that survives untouched is the signed bias,
-0.0778 [-0.0870, -0.0691].** It reproduces to 1e-6 and it is real.

---

## 4. Mechanism, verified independently — and the brief's description is incomplete

The brief's mechanism ("`qb2_lib.simulate` resamples share against a pool
containing every QB-game including backups") is **confirmed and quantified**:

`qb2_lib.simulate` draws `S = _mix(rng, r['h_share'], po['share'], w, m, ew)`,
where `w = h_games / (h_games + 4)` and `po['share']` is built in
`qb2_lib.pools` from every prior-season quarterback-game with a dropback.

Measured on the 2020-2024 pool actually used for the 2025 evaluation:

| pool composition | n | share of pool | mean share |
|---|--:|--:|--:|
| primary passer that week | 2,686 | 79.6% | **0.9683** |
| **not the primary passer** | **690** | **20.4%** | **0.1233** |
| whole pool as used | 3,376 | 100% | 0.7956 |

Mean own-history weight `w` across the 540 rows is 0.8529, so on average 14.7%
of each starter's share draws come from that pool and about one in five of
those is a backup appearance.

**But the pool is not the only contaminated component, and fixing it alone does
most of nothing.** The quarterback's *own* history `r['h_share']` also contains
his own backup appearances: **1,231 of the 26,044 prior appearances behind the
540 rows (4.73%), at a mean share of 0.1726**. Because `w` averages 0.85, that
term is weighted five times more heavily than the pool term.

Measured, on the full 540-game cohort:

| what is conditioned | randomized PIT chi2 | signed bias |
|---|--:|--:|
| nothing (incumbent) | 32.481 | -0.0778 |
| **pool only** — exactly the brief's fix | **23.703** | **-0.0703** |
| pool and own history | **8.667** | **-0.0190** |

**Implementing the brief's description on trust would have recovered under a
quarter of the available repair and left the PIT still rejecting uniformity.**
The defect is one defect — a mixture whose two components estimate different
quantities — but it lives in both components, not only in the pool.

### 4.1 Every specification that was tried, including the ones rejected

Specification selection happened on this development frame and is reported in
full rather than as a single winner.

| specification | randomized PIT chi2 | signed bias | share CRPS |
|---|--:|--:|--:|
| incumbent, unconditional | 32.481 | -0.0778 | 0.03847 |
| pool stratified only (the brief's fix) | 23.703 | -0.0703 | 0.04146 |
| **pool stratified + own history role-conditioned — SHIPPED** | **8.667** | **-0.0190** | **0.03012** |
| fully role-coherent (own AND pool both switched to the backup basis when the lagged role is not primary) | 31.001 | -0.0579 | 0.07316 |
| explicit role mixture, `P(primary | played, lagged)` drawn per draw | 30.216 | -0.0857 | 0.04785 |

The last two are the more *principled* constructions — they carry role
uncertainty honestly — and they score **worse on this frame**, for a reason
that is not a defect in them: **the 540-game frame is selected on the realised
primary-passer label.** A forecast that correctly assigns, say, 93.6%
probability to a quarterback being the primary passer is guaranteed to look
biased low on a frame from which the 6.4% were removed by the selection rule.
This frame can only fairly score a forecast conditioned on being the starter,
which is what the shipped specification is. That is a property of the
evaluation, is stated here rather than discovered later, and is one more reason
this result is exploratory.

---

## 5. The fix

`nfl/research/qb2/qb2_lib.py`. Both mixture components are put on **one
conditioning basis**:

- **own component**: this quarterback's prior games **as his team's primary
  passer** (`r['h_share_primary']`, written by `attach`);
- **pool component**: the pool stratified by `prior_primary` — the pool row's
  passer's own role in **his own most recent previous appearance**.

Both labels are facts about games strictly earlier than the one being forecast.
`test_g` asserts this directly: for all 540 rows, `h_share_primary` equals the
shares of strictly-earlier primary games and `prior_primary` equals the role in
the last strictly-earlier appearance, 0 disagreements. No row's own realised
role is ever its own conditioner.

**No constant is introduced.** The mixture weight is the module's existing
`rung_weight`, unchanged. There is no floor, clip, threshold or minimum
anywhere in the change. Nothing is refitted.

The strata, built from prior seasons only:

| `prior_primary` | n | mean share |
|---|--:|--:|
| True | 2,606 | 0.9232 |
| False | 512 | 0.3887 |
| None (no prior appearance) | 258 | 0.3149 |

**Why the lagged label and not a depth chart.** There is **no 2025 weekly depth
chart in this repository**. `nfl/research/inputs/` holds `dc_2020`..`dc_2024`
(the `depth_team` schema) and `dc25_daily.csv.gz`, whose earliest `dt` is
2026-03-14. The lagged role is the only pregame role signal available for this
cohort. A real starter designation would strictly improve the repair and is not
assumed here.

**What this is NOT.** It does not forecast *whether* he starts. It forecasts
his share given the role his history points at, and role uncertainty survives
only as whatever non-primary mass the stratified pool carries. That limitation
is priced in section 8.

### Default-off, and proved so

The incumbent is the default and every sealed artifact was produced under it.
`simulate(..., share_spec=...)` defaults to `SHARE_SPEC_UNCONDITIONAL`, whose
branch is the byte-identical expression that was inline before.

- `simulate` default output over the 540-row cohort: **0 of 1,296,000 draw
  cells differ** from the pre-repair module.
- `pools()` returns identical arrays and scalars on every incumbent key.
- `test_e` locks a sha256 over all twelve default draw matrices,
  `d67b8b825e2624574373c32ef782b6114170b6e8828d049d78cb66d1c8f11a19`, taken
  before the repair existed and asserted after it.
- An unknown `share_spec` raises rather than falling back (`test_f`), and the
  repaired path refuses a frame missing the role fields by name
  (`QB_SHARE_ROLE_FIELDS_ABSENT`) rather than quietly drawing the pool it
  exists to replace.

---

## 6. New candidate: `V1_CANDIDATE_R12`

Registered in `nfl/production/candidate_mode.py` as `R12_FLAGS` /
`R12_REPAIR`, resolving to R9's flags plus
`qb_share_spec='starter_conditioned'`.

**It is R12 and not R10.** R10 (`appearance_r10`) and R11
(`rush_single_owner`) were registered by the two concurrent agents while this
work was in progress; my first registration attempt was refused by the
assertion in the patch and wrote zero bytes, which is how the collision was
found rather than silently overwritten. R12 inherits R9 and explicitly does not
inherit R10 or R11, matching R11's own declaration.

**R8 and R9 were not edited.** `qb3_lib`, `football_engine.py`,
`appearance_r8.py`, `rushing_a1.py`, `depth_vintage.py`, `shared_pass.py`,
`stat_contract.py` and `q7/panel.py` were not touched.

### R12 IS INERT ON THE ENGINE PATH, AND THAT IS STATED RATHER THAN DISCOVERED

`football_engine.py:448` always passes `db_external` when `r2` is set, and
every mode from `V1_CANDIDATE` onward sets `r2`. Under R2 the share is **not
drawn at all** — `qb2_lib.simulate` takes the apportioned integer level from
D1 x QB3. So on the engine path R12 changes nothing, and `qb_v1.forecast` now
**refuses** a call carrying both `share_spec` and `db_external`
(`QB_SHARE_SPEC_INERT_UNDER_R2`) rather than running with a component label it
did not use.

The path this repair actually changes is `qb_v1.forecast` called **without**
`db_external` — which is `PRODUCTION_BASELINE`, and is the path
`nfl/research/v3/h1` scored. That is where the defect was measured and where it
is fixed.

---

## 7. Seals preserved

- **273 sealed artifacts** across `nfl/research/live/`, `nfl/research/shadow/`,
  `nfl/product/boards/` and `nfl/prospective/` (`SEAL_SHA256.txt`,
  `SEALED_FORECAST.json`, `board.json`, `forecast_artifact.json`) hashed before
  the first edit and after the last: **byte-identical, 0 differences**.
  `git status` on those four trees is clean.
- `nfl/production/nonqb/layers.py` sha256 `481f005f682cd721...` at start and at
  end — **unchanged**, not edited.
- Nothing was written into `nfl/research/live/`.

---

## 8. What the repair costs, recorded and not smoothed

### 8.1 The passing-yard bias flips sign, and this is the real finding

| layer | incumbent bias [95% game-blocked] | R12 bias [95% game-blocked] |
|---|---|---|
| team dropbacks (`V`, unchanged between arms) | **+1.6369** | +1.6369 |
| QB dropback share | -0.0778 [-0.0870, -0.0691] | -0.0190 [-0.0278, -0.0109] |
| QB dropbacks | -1.3697 [-2.047, -0.667] | **+0.8406 [+0.175, +1.567]** |
| QB attempts | -1.1394 [-1.785, -0.452] | +0.7928 [+0.150, +1.473] |
| QB passing yards | -5.9223 [-12.669, +0.734] | **+7.5384 [+0.902, +14.167]** |

The `V` draw is bit-identical between the two arms (checked), and its bias
**+1.6369** reproduces `H1_SUMMARY.json`'s `team_dropbacks_qb2` figure exactly.

The chain closes arithmetically. With mean realised team dropbacks 36.3037 and
mean realised share 0.9718, the first-order decomposition
`E[team_db]·bias_share + E[share]·bias_team_db` gives **-1.235** for the
incumbent against a measured -1.372, and **+0.901** for R12 against a measured
+0.843.

**So the incumbent's QB-dropback under-projection was a share drawn ~2.8
dropbacks too low partially cancelling a team layer drawn ~1.6 too high.**
Repairing the share removes one error and leaves the other standing alone,
where it is now visible as an over-projection. **I did not absorb the
team-level error into the share** — the team layer is untouched and its bias is
identical to the digit in both arms. H1 §1 attributes that +1.637 to league
drift in a frozen 2020-2024 league mean (mean snaps 66.107 in 2020-24 against
64.237 in 2025), and it lives in the team volume layer, not here. **It is not
mine and I have not touched it.**

CRPS nevertheless improves at every level of the chain, because CRPS scores the
whole distribution rather than the mean: dropbacks 5.153 -> 5.023, attempts
4.764 -> 4.678, passing yards 43.042 -> 41.744.

### 8.2 Where the repair is worse

On the **40 of 540** games where the lagged role is not the role he played —
week-1 starters whose last appearance was a week-18 cameo, and mid-season
returns — the repair makes things slightly worse:

| split | n | share CRPS | passing-yard CRPS |
|---|--:|---|---|
| lagged role = primary | 500 | 0.03293 -> **0.02305** | 43.110 -> **41.336** |
| lagged role != primary | 40 | 0.10770 -> 0.11840 | 42.192 -> **46.839** |

Share bias on the 500 goes to **-0.0074**, essentially zero; on the 40 it barely
moves, -0.1983 -> -0.1637. **The repair helps where the role signal is right
and costs a little where it is not.** A genuine pregame starter designation
would remove this cell; the lagged label is the best this repository holds.

### 8.3 Still open on the repaired arm

- Share bias TOST against ±0.010: **NOT_SHOWN_EQUIVALENT** (90% CI
  [-0.0261, -0.0119]). Smaller, not shown equivalent.
- Passing-yard randomized PIT improves 31.222 -> 20.407 but still rejects
  uniformity at alpha = 0.05 (p = 0.0156), though no longer at 0.01.
- Passing-yard randomized coverage u < 0.90 moves 0.9315 -> 0.9444, i.e.
  further above nominal, while u < 0.10 and u < 0.50 both move toward it.
- The mid-PIT rises (section 3). Anyone quoting 929 will read this as a
  regression.

---

## 9. Method

- **Frame**: 540 eligible 2025 starting-QB games over 272 games, 32 teams.
  `qb.pkl` sha256 `e2de51d345502a2717a64e584f5e883a64eb3ed51ff97e5f42e406a0ddba0c54`.
  This is the exact cohort the defect was established on; `p2_cohort.cohort()`
  raises if the count is not 540 rather than scoring a different frame under
  the same name.
- **Clustering**: **block bootstrap over whole games**, 2,000 resamples, seed
  20260915. Games are not independent observations. **No naive standard error
  appears anywhere in this report or in `P2_RESULTS.json`.**
- **Equivalence**: predeclared margins — share bias ±0.010, passing-yard CRPS
  non-inferiority +1.0 yards (about 2% of `qb_v1.LADDER_RESULT`'s L1 CRPS of
  48.64), uniformity alpha 0.01. TOST is two one-sided tests on the clustered
  bootstrap SE and reports NOT_SHOWN_EQUIVALENT rather than adequacy.
- **No market quantity is an input anywhere.**
- **DEN@KC was not used, sought, or fitted to.** Nothing in this work reads the
  2026 captures. Mahomes' and Nix's yards appear nowhere in it.

### What was reused rather than rebuilt

The whole H1 harness, called unmodified: `h1_frame.build` (the frame and its
identity checks), `h1_run.eligible` (the predeclared eligibility rule),
`h1_run.score` (mean, sd, P10/P50/P90, CRPS, PIT), `h1_run.rpit` and
`h1_run.cpit`, and through them `p4b_volume.crps_samples`. The V/S recovery in
`p2_run._vs_matrix` is `h1_run.vs_draws`'s construction, and the reproduction is
**checked** — `rint(V*S)` must equal `simulate`'s own `db` matrix cell for cell
in both arms, or the run raises rather than scoring a layer it cannot prove it
observed. It passed in both arms.

**What was deliberately not rerun:** the two P4B team layers. This repair does
not touch team volume, and rerunning a layer that cannot move would only invite
noise to be read as an effect.

`chi2_sf` is hand-rolled (there is no scipy here) and is checked against six
published chi-square table values in `test_a` rather than trusted.

---

## 10. Test suites run

`python3.12 nfl/tests/run_suite.py --only <module>` for every module touched:

| suite | result |
|---|---|
| `qb_share_calibration` (new) | PASS — 7 functions, 24 checks, 0 failing |
| `v1_entrypoint_integration` | PASS — 8 functions, 26 checks |
| `pool_audit` | PASS — 17 functions, 38 checks, 1 declared blocked |
| `may_publish` | PASS — 25 functions, 94 checks |
| `production_pipeline` | PASS — 9 functions, 69 checks |
| `full_slate_rehearsal` | PASS — 7 functions, 30 checks |
| `forecast_completeness` | PASS — 7 functions, 30 checks |
| `v1_scramble_coherence` | PASS — 10 functions, 24 checks |
| `xl1_shared_pass` | PASS — 17 functions, 115 checks |
| `r5_active_pool` | PASS — 8 functions, 24 checks |
| `r6_role_prior` | PASS — 8 functions, 24 checks |
| `harness_audit` | PASS — 5 functions, 20 checks |
| `qb2_production` | **FAIL — pre-existing, not mine** |
| `draw_coherence` | **FAIL — pre-existing, not mine** |

Twelve suites pass, 524 checks, 0 failing, 1 declared blocked. Two fail and
both were failing before this task began.

Both failures were confirmed pre-existing by restoring the original
`qb2_lib.py` and re-running: `qb2_production` raises the identical
`FileNotFoundError` on `nfl/research/p4b/panel_enriched.pkl` (a file that has
never been committed on any branch — the absence `h1_frame.py`'s own docstring
records), and `draw_coherence` produces the identical nine failing checks with
the identical violating-cell counts (6827, 6085, 24, 841, 13524) against its
frozen Wave-0 baseline. Neither moves by a single cell when my change is
removed. `nfl/tests/test_draw_coherence.py` was already modified in the working
tree before this task began.

---

## 11. What would make this confirmatory

Nothing here is. The specification was chosen after comparing four variants on
this same 540-game 2025 development frame; section 4.1 is that comparison in
full, including the two that scored worse. Forward chaining controls parameter
leakage only. Section 4.1 also records a second, structural reason for caution:
the frame is selected on the realised primary-passer label, so it can only
fairly score a forecast conditioned on being the starter.

A confirmatory result needs: the 2026 season forward-chained with the
specification frozen as it stands now, or a sealed holdout of 2025 games never
inspected during this work, with the arm chosen before the fold is opened. The
sample would need to reach the project's own floors before any of it could
influence a price, and nothing in this work is a step toward a wager.

---

## 12. For the other agents and the owner

1. **`candidate_mode.assert_not_promoted` silently skips R9, R10 and R11.**
   Its mode list is `(V1_CANDIDATE, R5, R6, R7, R8)`, so an artifact in any of
   the three newest configurations returns `NOT_APPLICABLE` — the masquerade
   check does not run on it. This is the "a guard that deletes itself leaves
   the suite green" failure mode, live on three configurations. **I added R12
   to that list so my own mode is checked, and deliberately did not add R9,
   R10 or R11: they are not my lineage.** Their owners should add them.
2. **The 929.0 should be corrected wherever it is quoted** —
   `AUTOPSY_DEN_KC.md` §2, `H1_2025_QB_RESIDUALS.md` §1, and any downstream
   summary. It is a mid-PIT on a 78.89% atom, not a randomized PIT, and the
   atom-correct figure is 32.481. The "79% above P90" statistic should be
   retired for the same reason; its atom-safe analogue is 89.44% against a
   nominal 90%, which is close to nominal.
3. **The team dropback layer's +1.6369 over-projection is now the binding
   error on QB passing volume** and it is not in `qb2_lib`. With the share
   repaired it passes straight through to a +7.538-yard passing-yard
   over-projection whose interval excludes zero. Whoever owns
   `team_volume_v1` / P4B should know that the share error was masking it.
4. **A pregame starter designation would materially improve R12** and there is
   no 2025 weekly depth chart in this repository to supply one. Whoever holds
   `depth_vintage.py` and the capture path may be able to; 40 of 540 games in
   this cohort are the cell that needs it.
