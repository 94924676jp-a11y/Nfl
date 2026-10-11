# Independent review of H1 (top of board over-projected): reproduction, leakage audit, refutation

Reviewer: independent agent, 2026-10-11. I did not write the hypothesis, the candidate or the scripts.

Inputs:
- Branch `claude/h1-top-of-board-prereg` at `de8c4a67`, read with `git show`. I did not check it out.
- Pre-registration frozen at `011fb4c5`, committed 03:09:19 UTC. Check A's committed rows have an mtime of 03:09:59 in `/tmp/claude-0/trackb`, and a run takes about 32 s, so the run started after the freeze. That is file-time evidence, not proof.
- Harness: `nfl/tools/forward_chain.py` in the working tree, HEAD `0c5bf600`, which is the parent of both research commits. The tree was clean before and after every run.

Nothing under `/home/user/nfl` was written. All code and outputs are in `/tmp/claude-0/h1review/`:
- scripts in `src/`
- JSON outputs: `recompute.json`, `refute.json`, `rule_sim*.json`, `rule_joint.json`, `sens_depthfix.json`.

## Verdict

**REPRODUCED, with one reporting error and one material caveat.**

- **Rows.** The rows are reproduced byte-for-value from raw.
- **Check A numbers.** Every number in `CHECKA_RESULT.json` and in the check-A table of `RESULTS_CHECKS_A_B.md` is reproduced by an independent implementation.
- **Verdicts.** Under the frozen section-5 rules:
  - H1 is **not refuted** on check A;
  - H2 passes every harm test on check A and on development;
  - the pass also holds under an interval (non-inferiority) reading of the harm rules.
- **Check B.** Not reproduced. The committed artifacts name no input file, no script and no hash. Several candidate projection files exist for the same slate (for ATL@NO: `BASE/`, `CHARTFIX_REPRO/`, `FANT_OUT/`, `OFFICIAL_DRYRUN/`, `RW_CRN/` …), so I did not guess.
- **The material caveat.** I found it while trying to refute H1. The harness's over-projection at the top of the board is not a robust property of the model. Almost all of it comes from one harness input:
  - the depth-rank **appearance table** is measured only over players on the **2026 roster blobs**;
  - so it uses future information (who survived to 2026) and sharply under-counts how often depth players appear.
  - When that one table is measured over the same player universe the allocation pool already uses (no seasons after S-1), the top-quartile ratio is **0.933 [0.907, 0.959]** on check A and **0.918 [0.892, 0.947]** on development, against the claimed 1.315 and 1.137.
  - This does not change the frozen verdict, which is defined on the unmodified harness. It does change what that verdict means. Section 3 has the evidence.

## 1. Reproduction from raw (task 1)

**Rows.** I re-ran `capture_rows.py` (branch copy, unmodified) for 2022,2023 and 2024,2025. Comparison:

| file | committed rows | reproduced rows | key mismatches | max abs Δ proj | max abs Δ actual | pos / appeared mismatches |
|---|---|---|---|---|---|---|
| CHECKA 2022-2023 (both arms) | 16,568 | 16,568 | 0 | 0.0 | 0.0 | 0 |
| DEV 2024-2025 (both arms) | 24,406 | 24,406 | 0 | 0.0 | 0.0 | 0 |

**Metrics.** I recomputed them with my own code (`src/lib.py`, `src/recompute.py`: numpy and pandas, written from the pre-registration text). My bootstrap uses B = 4,000 week blocks; theirs used B = 400.

| quantity (check A) | claimed | reproduced | note |
|---|---|---|---|
| weeks | 28 | 28 | |
| **pool player-weeks** | **16,568** | **8,284** (production arm) | **Reporting error.** 16,568 counts both arms. The production arm has 8,284. Development's 12,203 is per arm, so the two figures in the documents are not comparable. |
| played | 5,207 | 5,207 | |
| slope of actual on projection | 0.4768 [0.4537, 0.5009] | 0.4768 [0.4511, 0.5017] | |
| **top-quartile ratio, played** | **1.3153 [1.2823, 1.3628], n = 1,680** | **1.3153 [1.2799, 1.3571], n = 1,680** | over 1 in 28 of 28 weeks |
| top-decile ratio | 1.4445 | 1.4445 | |
| weeks fitted | 20 | 20 | |
| MAE, production / candidate | 6.6164 / 6.1352 | 6.6164 / 6.1352 | |
| MAE difference, weekly paired | −0.4865 [−0.5714, −0.4016] | −0.4865 [−0.5714, −0.4016] | pooled week-block bootstrap: −0.481 [−0.568, −0.409] |
| position MAE change (%) | QB −1.648, RB −4.389, WR −9.818, TE −10.308 | identical to 3 dp | |
| decile MAE change (%) | 0×6, −3.164, −9.174, −13.442, −26.845 | identical | |
| top-decile ratio, production → candidate | 1.4408 → 1.0774 | same | |
| slope, production → candidate | 0.4747 → 0.605 | same | |
| top-quartile ratio on fitted weeks, production → candidate | 1.3018 → 1.0225 | same, n = 1,281 | |
| top-quartile MAE difference, weekly paired | −1.5058 [−1.7683, −1.2434] | same | bootstrap: −1.483 [−1.756, −1.254] |
| c at the last week | QB 0.9139, RB 0.782, WR 0.7094, TE 0.6815 | same | |
| H1 rule result / H2 accept | "CONFIRMED" / true | rule met / true | Check A can only refute. The JSON's `H1_CONFIRMED: true` label overstates what it can show; the Markdown says it correctly. |

**Development** (`DEV_H2_IN_SAMPLE.json`):
- Every value is reproduced exactly: ratio 1.1373, n = 2,417; H2 MAE −0.1594; QB +0.037 %; deciles; c values 0.9911 / 0.885 / 0.8443 / 0.848.
- My interval for the ratio is [1.1117, 1.1658]; theirs is [1.112, 1.167].

**Addendum.** The uncommitted `PREREG_H1_ADDENDUM_v1.1.md` (in `/tmp/claude-0/trackb`) gives O1 factors. I reproduce them exactly from the pooled 2022-2025 rows: QB 0.9517, RB 0.8440, WR 0.7771, TE 0.7652.

**Percentile convention.** The q75 convention (order statistic at floor(0.75 n)) gives the same membership as numpy's linear percentile in every position-week. That is an identity: floor(0.75 n) = ceil(0.75 (n−1)). The convention is therefore not a hidden degree of freedom.

**Two minor presentation points:**
- The table sets the production all-week ratio (1.315) beside the candidate fitted-week ratio (1.023). The like-for-like production figure is 1.302.
- Check B's numbers (1.105, 0.975, 0.991, and the MAEs) cannot be recomputed from anything committed.

## 2. Leakage audit in code (task 2)

### (a) Projections: what is pregame and clean

| input | where | finding |
|---|---|---|
| multi-season prior | `forward_chain.py:231-242` (`through = season-1`); `player_prior.py:137` skips seasons after `through` | clean |
| historical band | `forward_chain.py:204-228`, via `_observations(... through+1, through)` | clean |
| current-season shares | `forward_chain.py:251` (`int(wk) >= week: continue`) | strictly earlier weeks |
| club volume | `forward_chain.py:292`: weeks before W plus the full prior season | clean |
| allocation pool | `forward_chain.py:339`: club rows in weeks before W | clean. The week-W row is read at `:347`, but `_w` is never used (`:395`). |
| starting-QB proxy | `forward_chain.py:368-378`: weeks before W, else the prior season | clean |
| depth, group and bonus tables | `forward_chain.py:460-462`, `through=season-1` (`proj_v1.py:381, 709, 1499, 1507`) | season-clean; but see L4 |

### (a) Projections: leaks found

**L1. Positional TD rates are fitted on 2021-2025.**
- `forward_chain.py:459` calls `positional_rates`, with `FIT_SEASONS` at `td_rates.py:43` and `:133`.
- The fit includes the season being evaluated and later seasons.
- It only splits a pregame club TD pool across players (`proj_v1.py:1018-1060`).

**L2. The league interception rate runs through 2025.**
- `forward_chain.py:463` passes no `through`, so `proj_v1.py:446` falls back to `THROUGH_SEASON = 2025`.

**L3. The pass share of TDs is a hard-coded 0.6156.**
- `forward_chain.py:423`; it equals `TD_RATES.json` `mean_pass_share_of_offensive_td` over 2021-2025.
- **L1-L3 are immaterial.** I restricted all three to seasons up to S−1 (`src/capture_tdfix.py`):
  - check A ratio 1.3133 against 1.3153;
  - development 1.1375 against 1.1373;
  - largest single projection change 0.64 points.

**L4. The position source is the 2026 roster blobs. This is future information, and it is material.**
- `player_prior.position_index()` (`player_prior.py:248-272`, `ROSTERS` at `:55`) reads `nfl/vintage/weekly_rosters.*raw.csv.gz`. Every raw blob holds season 2026 only; I checked.
- For a 2022 week, "has a position" therefore means "is still on a roster in 2026". The index is used for four things:
  1. **The scored set.** Inferred players are excluded (`forward_chain.py:458`, `capture_rows.py:42-44`), so scored players are those who survived to 2026.
  2. **Cohort priors.** `player_prior.py:373` filters cohorts by the roster position.
  3. **The depth and appearance table.** `forward_chain.py:460` passes the roster-only `pos_of` to `depth_shares`. There, `proj_v1.py:1496` filters players and `:1544` computes `appearance_rate = n / n_club_weeks`.
  4. **Group shares, bonus rates and TD rates.**
- The allocation **pool** includes the usage-inferred players (via `season_pos`). The **appearance table** that discounts each rank's claim (`proj_v1.py:879, 912`) counts only survivors. The two are measured on different universes.
- Measured appearance rates, roster-only against all players with a position:

| table through | RB2 | WR2 | WR3 | WR4 | WR5 |
|---|---|---|---|---|---|
| 2021 | 0.254 vs 0.941 | 0.588 vs 1.000 | 0.238 vs 1.000 | 0.041 vs 0.911 | 0.002 vs 0.667 |
| 2023 | 0.441 vs 0.951 | 0.775 vs 1.000 | 0.397 vs 0.990 | 0.108 vs 0.861 | 0.025 vs 0.567 |
| 2025 (production default) | 0.635 vs 0.972 | 0.861 vs 1.000 | 0.587 vs 0.985 | 0.266 vs 0.803 | 0.077 vs 0.463 |

- **Effect.** Depth players' claims are shrunk by appearance rates that are far too low, and starters absorb the volume. Measured effect on the H1 ratio: section 3, item 7.
- **The repository already does this the consistent way elsewhere.** `nfl/eval/calibration.py:108` calls `depth_shares(panel, season_pos, ...)`.
- **Production uses the same roster-only table.** `proj_v1.py:1114-1118` calls `depth_shares(panel, position_index())` through 2025. That is a hypothesis for why production may share the defect, not a measurement.

**L5. Inferred positions use the whole season's usage.**
- `forward_chain.py:166-177`. This includes week W and later weeks, and it decides who is in or out of the scored and q75 population for players not on the roster. It is minor.

### Not leakage, but it affects the numbers

**N1. Bye weeks are in the pool.**
- The pool never checks that the club plays in week W.
- On check A, 591 of 8,284 pool rows (155 of 2,116 top-quartile rows) belong to a club with no game that week. On development it is 847 of 12,203 (216 of 3,101).
- They count as "did not play". That inflates the unconditional view, including the pre-registration's "3.3 of 6.05 points come from players who did not play". It barely moves H1: q75 recomputed on clubs that played gives 1.3093 on check A and 1.1361 on development.

**N2. The backup-QB appearance discount never fires in the chain.**
- `forward_chain.py:406` passes neither `depth_rank` nor `predicted_feed_covers_club`. The `is_predicted_starter is False` branch at `proj_v1.py:648` needs the second.
- The comment at `forward_chain.py:356-366` describes a fix that no longer takes effect.

### (b) The correction factor uses only strictly earlier weeks: confirmed

- `eval_h2.py:37` uses `weeks[:i]`; the minimum of 8 weeks is enforced at `:38`; the cap at 1 is at `:39`.
- My implementation (`lib.candidate`, cumulative sums over weeks before w) gives identical c and identical candidate values.
- The fit pools earlier seasons forward (2022 fits 2023). No later season fits an earlier one.

### (c) The q75 threshold uses only that week's projections: confirmed

- `eval_h2.py:30` uses that week's projections for the position over the whole pool, including players who did not appear. No outcome enters.
- Caveat: who is in that pool depends on L4 (survival to 2026) and L5, and it includes N1's bye-week rows.

### (d) The actual DK points definition: no leak into projections

- `actual_dk` (`forward_chain.py:98-115`) is computed from the week-W row only, at `capture_rows.py:46-49`.
- No projection path reads week-W statistics.
- It omits lost fumbles and two-point conversions, as the projection does. That is consistent internally, but it is not exact DraftKings scoring. It matters for check B, which compares with production; its scoring source is undocumented.

## 3. Refutation attempts (task 3)

All results are among players who played, with 95 % week-block bootstrap intervals (B = 4,000). Source: `refute.json`.

| stratum | check A ratio [95 %] | n | weeks over 1 | development ratio [95 %] | n | weeks over 1 |
|---|---|---|---|---|---|---|
| primary | 1.315 [1.280, 1.357] | 1,680 | 28/28 | 1.137 [1.112, 1.166] | 2,417 | 28/28 |
| season 2022 / 2024 | 1.361 [1.303, 1.437] | 730 | 14/14 | 1.133 [1.103, 1.165] | 1,148 | 14/14 |
| season 2023 / 2025 | 1.279 [1.243, 1.318] | 950 | 14/14 | 1.142 [1.099, 1.187] | 1,269 | 14/14 |
| QB | 1.100 [1.050, 1.159] | 279 | 21/28 | **1.012 [0.972, 1.051]** | 373 | 18/28 |
| RB | 1.261 [1.203, 1.325] | 406 | 27/28 | 1.135 [1.087, 1.189] | 599 | 24/28 |
| WR | 1.417 [1.351, 1.489] | 600 | 28/28 | 1.192 [1.149, 1.241] | 909 | 28/28 |
| TE | 1.472 [1.369, 1.589] | 395 | 28/28 | 1.185 [1.130, 1.247] | 536 | 26/28 |
| excluding in-season club changers | 1.317 [1.282, 1.359] | 1,653 | 28/28 | 1.136 [1.110, 1.165] | 2,386 | 28/28 |
| club changers only | 1.210 [1.035, 1.452] | 27 | 9/14 | 1.231 [0.983, 1.555] | 31 | 17/25 |
| top 9 % per position-week | 1.418 [1.370, 1.472] | 668 | 28/28 | 1.185 [1.143, 1.236] | 901 | 28/28 |
| top 9 % pooled | 1.422 [1.357, 1.497] | 468 | 28/28 | 1.141 [1.101, 1.189] | 646 | 25/28 |
| q75 to q91 band | 1.232 [1.186, 1.287] | 1,012 | 28/28 | 1.100 [1.076, 1.127] | 1,516 | 26/28 |
| strict p > q75 | 1.323 [1.287, 1.366] | 1,593 | | 1.138 [1.112, 1.168] | 2,326 | |
| rank-based top 25 % by count, 50 random tie-break seeds | 1.3153 (range 1.3153 to 1.3153) | 1,680 | | 1.1373 (no range) | 2,417 | |
| inclusive "lower" percentile | 1.304 [1.270, 1.344] | 1,744 | | 1.136 [1.110, 1.164] | 2,469 | |
| **unconditional** (every top-quartile candidate, absent scored 0), shown separately | 1.640 [1.566, 1.722]; appearance rate 0.794 | 2,116 | | 1.449 [1.388, 1.514]; appearance rate 0.779 | 3,101 | |
| unconditional, clubs that played only | 1.518 [1.456, 1.589]; appearance rate 0.857 | | | 1.347 [1.295, 1.409]; appearance rate 0.838 | | |

How to read this:
1. **Within the harness, H1 is robust.** It holds by season, by position, after excluding club changers, within the top 9 %, and under every tie and percentile convention.
2. **Ties do not matter.** No two projections tie at the threshold, so threshold and rank membership are identical.
3. **One exception.** Development QB is 1.012 [0.972, 1.051]: the interval contains 1.00, and 2024 QB is 0.982. Read as a stratum, H1 fails at QB on development. On check A it holds (1.100).
4. **"Club changers" is a hindsight label.** It is a whole-season attribute, so that stratum is defined after the fact. n is about 30, which is uninformative.

**5. Appearance selection.** Near-certain starters are players who appeared in each of their club's previous three games; this is pregame information.

| group (top-quartile pool) | check A: pool n, appearance rate | check A: played ratio, excess | development: pool n, appearance rate | development: played ratio, excess |
|---|---|---|---|---|
| near-certain | 1,687, 0.868 | 1.299 [1.265, 1.339], +4.59 pts, n = 1,464 | 2,447, 0.870 | 1.124 [1.096, 1.157], +1.82 pts, n = 2,129 |
| others | 429, 0.504 | 1.451 [1.357, 1.559], +5.54 pts, n = 216 | 654, 0.440 | 1.254 [1.155, 1.375], +3.08 pts, n = 288 |
| all | 2,116, 0.794 | 1.315, +4.71 pts | 3,101, 0.779 | 1.137, +1.97 pts |
| near-certain, non-changer | | 1.302 [1.268, 1.340] | | 1.124 [1.095, 1.157] |

**6. Conditioning on appearance cannot manufacture the excess.**
- "Appeared" requires a panel row with at least one opportunity. That is positive selection on the outcome, so it pushes the played-only ratio **down**, against H1.
- Top-quartile players who did not appear had slightly lower projections (check A 18.69 against 19.66 for those who played; development 15.81 against 16.32). Dropping them raises the mean projection of the played group by about 1 %.
- If every top-quartile player were treated as a near-certain starter, the excess would be 4.59 rather than 4.71 points on check A and 1.82 rather than 1.97 on development. Composition by appearance certainty therefore explains at most about 3 % (check A) and 8 % (development) of the excess.
- The over-projection is not an appearance artefact.

**7. The refutation that matters: the depth table (L4).** These are reviewer sensitivity runs, not pre-registered. In each, the harness is unmodified except for one input, monkeypatched in-process:

| variant | check A top-quartile ratio | development top-quartile ratio |
|---|---|---|
| frozen harness | 1.315 [1.280, 1.357] | 1.137 [1.112, 1.166] |
| L1-L3 restricted to seasons up to S−1 | 1.313 [1.279, 1.354] | 1.138 [1.112, 1.166] |
| cohort priors with non-survivors included (`PATCH_COHORT` only) | 1.319 [1.283, 1.361] | |
| all fits with non-survivors, except the depth table kept roster-only | 1.315 [1.279, 1.357] | |
| **only the depth and appearance table measured on the pool's universe** (roster position, else the harness's own inferred position, seasons up to S−1; `src/capture_depthfix.py`) | **0.933 [0.907, 0.959]** | **0.918 [0.892, 0.947]** |

The same depth-table variant, in more detail:

| measure | check A | development |
|---|---|---|
| by season | 2022: 0.927, 2023: 0.938 | 2024: 0.880, 2025: 0.955 |
| by position | QB 1.015, RB 0.876, WR 0.924, TE 0.930 | QB 0.963, RB 0.905, WR 0.922, TE 0.873 |
| MAE on played rows, frozen → variant | 6.686 → 5.682 | 5.912 → 5.443 |
| Spearman, frozen → variant | 0.473 → 0.523 | 0.515 → 0.540 |
| candidate c under the variant | about 1 at every position, so the candidate does nothing | about 1 at every position, so the candidate does nothing |

- That one input accounts for all of H1's harness excess, and for the larger check-A figure (1.32 against 1.14). Older tables are more survivor-biased, which fits better than the results file's guess about "fewer seasons in the prior".
- Correcting the input improves MAE about twice as much as the frozen candidate does on check A (−1.00 against −0.49).
- The variant is crude. Inferred tight ends become receivers, and the pool still contains released or injured-reserve players the table cannot see. So the truth may lie between 0.93 and 1.32. What the variant shows is that the harness does not identify H1's magnitude, or even its sign.
- The candidate, and the addendum's O1 factors (RB 0.844, WR 0.777, TE 0.765) fitted on this harness, are largely a correction for this harness input. Applying O1 to production's projections (P-prod) would carry a harness artefact into production.
- Check B is consistent with this:
  - production is about 1.0 on both showdown slates (0.975 and 0.991);
  - the candidate takes them to 0.89 on both (0.888, 0.890).
- The addendum's P-chain stream uses the same harness, so it will tend to "confirm" H1 by construction.

## 4. The frozen harm rules: statistical assessment (task 4)

Source: `rule_sim.json`, `rule_sim6.json`, `rule_joint.json`. The data are fitted weeks only, players who played. Check A has 20 weeks and 3,947 rows; development has 20 weeks and 5,299 rows.

**Sampling SD of the percentage change in MAE, week-block bootstrap:**

| stratum | check A, 20 weeks | development, 20 weeks | check A, 6 weeks | development, 6 weeks |
|---|---|---|---|---|
| deciles 1-5 | 0 | 0 | 0 | 0 |
| decile 6 | 0.09 | 0.08 | 0.26 | 0.17 |
| decile 7 | 0.84 | 0.82 | 1.54 | 1.55 |
| decile 8 | 2.06 | 0.98 | 3.89 | 1.89 |
| decile 9 | 2.36 | 1.11 | 4.23 | 1.94 |
| decile 10 | 2.81 | 1.10 | 5.05 | 1.99 |
| QB | 0.52 | 0.04 | 0.99 | 0.09 |
| RB | 0.72 | 0.50 | 1.34 | 0.92 |
| WR | 0.89 | 0.40 | 1.63 | 0.74 |
| TE | 1.40 | 0.80 | 2.57 | 1.45 |

**Would a null candidate fail by chance?** I tested three constructions:

1. **Exact-zero-effect candidate.** Same footprint and noise as this candidate, bootstrap centred so every stratum's true change is 0, correlations between strata kept. It fails the decile-or-position rule:
   - check A: **57 %** at 20 weeks, **78 %** at 6 weeks;
   - development: **19 %** at 20 weeks, **59 %** at 6 weeks.
   - For a single stratum, the chance of a false harm flag is up to 24 % (check A decile 10, and TE) at 20 weeks, and about 35 % at 6 weeks.
2. **Week-level relabelling** (production and candidate swapped at random by week). It fails 97 % of the time on check A and 50 % on development. The rule does have power against a candidate pointing in a random direction.
3. **Zero-bias random perturbation.** The same top-quartile rows are moved by ±|Δ|. At 25 % of the observed move it fails 4 % (check A) and 0 % (development). At 100 % it fails about 93-100 %, correctly, because noise worsens MAE.

**The observed candidate is not near the margins.**
- On both datasets, 0 % of bootstrap replicates fail.
- Every one-sided 95 % upper bound is within the margins: the worst decile upper bound is −1.55 %, and the worst position upper bound is QB +0.14 % on development.
- The H2 pass therefore does **not** depend on reading a point estimate rather than an interval.

**Is a point-estimate threshold appropriate?** No:
- It does not control the false-harm rate. That rate is 19-78 % for an exactly neutral candidate, depending on noise and weeks.
- It cannot show non-harm. A +1.9 % decile point estimate with SD 5 passes, although harm up to about +12 % is consistent with the data.
- Six of the ten deciles are mechanically 0, because the candidate never changes anything below q75. The decile rule is vacuous there.
- Deciles are pooled across positions and weeks, so their composition shifts with the mix of positions.
- At 6 prospective weeks the rule is mostly noise. At TE and deciles 8-10, the SD (1.5-5 %) is as large as or larger than the margins (1 % and 2 %).

**Recommendation, for a future protocol version only.** **The frozen v1.0 rule must stand for this study and must not be re-applied to data it already covers.** The addendum states the same.
- Replace the point-estimate rule with a per-stratum one-sided non-inferiority test. Use the week-block bootstrap upper 95 % bound of the percentage change in MAE: at most +2 % per decile and +1 % per position.
- Use a simultaneous (max-statistic) bound, or Holm's correction across strata.
- Form deciles within position-week.
- Raise a separate harm flag when a lower bound exceeds 0.
- Size the number of weeks so the margins are detectable. At TE and a 1 % margin, the SD needs to be about 0.5, which implies roughly 40 or more weeks of harness-equivalent volume.
- Add a rank-preservation check, such as Spearman within position-week. The candidate creates ties at q75, which MAE cannot see.

**A related gap in the H1 rule.** "Confirmed if over 1.05 with lower bound over 1.00; refuted if the interval contains 1.00" gives no verdict in two cases:
- a ratio between 1.00 and 1.05 whose interval lies above 1.00;
- a ratio whose interval lies entirely below 1.00, as in the depth-table variant (0.93 [0.91, 0.96]).

## Caveats

- Check A is not clean data, as the authors say. It can only refute, and it did not.
- Everything here is conditional on the harness. The harness is a different engine from production: it has no market input, no injury information, no chart ranks, and the QB discount is inactive (N2).
- My depth-table variant is an unregistered sensitivity with a crude position inference. It shows non-robustness; it is not a corrected estimate.
- Week blocks are the only clustering used. Player-level dependence across weeks is not separately blocked, so the intervals may be somewhat narrow.
- Check B could not be audited.

Files: `/tmp/claude-0/h1review/` (`src/*.py`, `recompute.json`, `refute.json`, `rule_sim.json`, `rule_sim6.json`, `rule_joint.json`, `sens_depthfix.json`, reproduced rows `repro_*.csv.gz`, scored rows `scored_*.csv.gz`).
