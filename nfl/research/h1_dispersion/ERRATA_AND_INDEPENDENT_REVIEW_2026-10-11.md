# H1: errata, independent review, and what the result means (2026-10-11)

This file adds to the H1 record. It does **not** edit the frozen pre-registration (`PREREG_H1_DISPERSION.md`,
`011fb4c5`) or the addendum (`PREREG_H1_ADDENDUM_v1.1.md`, `75a6125d`). Their decision rules stand, and nothing
here re-applies a rule to data it already covers.

Status: **shadow research only.** No production change, no promotion, no market input, nothing from FantasyCruncher.

## 1. Errata (errors in my own committed reporting)

| # | where | what was written | correct | found by |
|---|---|---|---|---|
| E1 | `RESULTS_CHECKS_A_B.md`, check A | "16,568 pool player-weeks" | **8,284 for the production arm.** 16,568 counts both arms. Development's 12,203 is per arm, so the two figures were not comparable. | independent reviewer |
| E2 | `CHECKA_RESULT.json` | `"H1_CONFIRMED": true` | **NOT REFUTED.** Check A can only refute (pre-registration section 5). The key was a label error; the Markdown result was worded correctly. The JSON is left as committed and superseded by this row. | independent reviewer |
| E3 | check B | numbers with no committed script or input | Now reproducible: `check_b.py` + `CHECK_B_RESULT.json`, inputs pinned by sha256. They reproduce every check-B number exactly (1.105 / 0.992 / 8.49 → 8.16; 0.975 / 0.888; 0.991 / 0.890). | independent reviewer |
| E4 | addendum | "frozen ~03:40 UTC" | The commit time **03:28:20Z** is authoritative. | self |
| E5 | `RESULTS_CHECKS_A_B.md` | production all-week ratio 1.315 set beside candidate fitted-week ratio 1.023 | Like for like: production on fitted weeks is **1.302**. | independent reviewer |

## 2. Independent review: what survived

The reviewer did not write the hypothesis, the candidate or the scripts. Their full report is
`INDEPENDENT_REVIEW_H1.md`.

| check | result |
|---|---|
| Rows re-run from raw (`capture_rows.py`, clean tree) | identical: 16,568 and 24,406 rows, 0 mismatches, max change 0.0 |
| Every check-A and development number, recomputed with independent code | reproduced (bootstrap B = 4,000 against 400) |
| Correction factor uses only strictly earlier weeks; q75 uses only that week's projections | confirmed in code |
| Leaks L1-L3 (TD rates, interception rate, pass share of TDs fitted through 2025) | real but immaterial: ratio 1.3133 against 1.3153 |
| H1 inside the harness, by season, position, top 9 %, club changers, tie conventions | robust, except development QB 1.012 [0.972, 1.051] |
| Selection by appearance (played vs not played) | cannot manufacture the excess; composition by appearance certainty explains at most about 3 % (check A) and 8 % (development) |
| **L4: the depth and appearance table is measured only over players on the 2026 rosters** | **material: it carries the whole harness excess** (section 3) |

## 3. What the frozen verdict means after L4

The frozen verdicts stand as defined. On the unmodified harness:
- H1 is **not refuted** on check A;
- H2 **passes** every harm test on check A and on development.

**But they no longer mean what H1 claimed.** The harness's top-of-board excess is almost entirely produced by one
input. When only the depth and appearance table is measured on the same player universe the allocation pool
already uses, the excess disappears:

| variant (reviewer sensitivity, not pre-registered) | check A top-quartile ratio | development |
|---|---|---|
| frozen harness | 1.315 [1.280, 1.357] | 1.137 [1.112, 1.166] |
| depth and appearance table on the pool's universe | **0.933 [0.907, 0.959]** | **0.918 [0.892, 0.947]** |
| MAE on played rows, frozen → variant | 6.686 → 5.682 | 5.912 → 5.443 |
| candidate's fitted c under the variant | about 1 at every position | about 1 |

**The candidate, and the addendum's O1 factors, are therefore largely a correction for a harness input.** Applying O1
to production's locked projections would carry that artefact into production.

### Production's own archived slates (check B, now reproducible)

| slate | production top-quartile ratio | candidate | top-quartile MAE production → candidate |
|---|---|---|---|
| week-4 early Classic (seen) | 1.105, n = 48 | 0.992 | 8.49 → 8.16 |
| ATL@NO showdown (seen) | 0.975, n = 8 | 0.888 | 5.25 → 4.66 |
| TB@DAL showdown (the clean slate) | 0.991, n = 13 | 0.890 | 7.63 → 7.18 |

- These are single slates with very small top-quartile samples.
- On both showdowns production is about calibrated at the top, and the candidate pushes it to about 0.89.
- Lower MAE alongside a ratio of 0.89 is what a level cut does to a right-skewed outcome. It is not evidence of a
  better forecast.

### Effect on actual DFS portfolio decisions (week-4 early Classic; already seen; descriptive)

- **Design.** Paired rebuild with `nfl/opt/classic_portfolio.py` (unmodified), with the same seed, worlds, ownership
  and constraints. The only change is the candidate's O1 rescaling of each top-quartile player's draws (87 of 378
  players, mean factor 0.832).
- **Reproduction.** The incumbent rebuild reproduces the archived lineups 150/150, 20/20 and 3/3.

| contest | lineups shared | mean DK points, incumbent → candidate | entries in top 10 %, incumbent → candidate | median field percentile (lower is better) |
|---|---|---|---|---|
| 150-entry | 89/150 | 129.41 → 128.62 | 39 → 36 | 0.301 → 0.301 |
| 20-entry | 11/20 | 132.33 → 129.99 | 5 → 4 | 0.303 → 0.308 |
| 3-entry | 1/3 | 157.13 → 125.84 | 2 → 0 | 0.044 → 0.323 |

- The candidate's lineups score lower in all three contests.
- This is one slate, already seen. Under the pre-registration (fewer than 10 slates) it is descriptive only and
  cannot accept or reject H2.
- It is the direction of the predeclared harm flag (candidate lineups score lower), on one of the slates the flag
  counts.

### Distribution and correlation effects (by construction)

- The candidate multiplies each affected player's draws by one factor (at most 1).
- Each player's correlation with every other player is unchanged.
- His spread and covariances shrink by that factor. So the top of the board loses both mean and upside, and
  the portfolio builder sees less ceiling exactly where tournament lineups need it.
- That fits the 3-entry result: the candidate replaced Lamb and Nacua (66.7 pp of exposure each).

## 4. Status of H1 (frozen rules; nothing re-applied)

| item | status |
|---|---|
| H1 on check A | **NOT REFUTED** (frozen rule); interpretation **undermined by L4** |
| H2 on check A and development | passes the frozen harm rules; the benefit is **largely a harness artefact** |
| confirmatory test (2026 week 6 onward, at least 6 graded weeks) | **not run.** W5 and W6 actuals are not yet in the usage panel (2026 weeks present: 1-4). |
| P-chain prospective stream (addendum) | sealed (`PROSPECTIVE_2026W5W6_SEAL.csv`, sha256 `e099bc4b…`). It will tend to "confirm" H1 by construction, because it uses the same harness. Its grade must be read with that caveat. |
| P-prod shadow on production's locked projections | the stream that can actually test H1. **Do not adopt O1 factors from it** without the L4 question resolved. |

## 5. Methods note: the pre-registered "no group worse" rule

The reviewer's simulation is in `INDEPENDENT_REVIEW_H1.md`, section 4.

**Finding.** The point-estimate harm rule (no position worse by more than 1 %, no decile worse by more than 2 %) does
not control the false-harm rate. A candidate with an exact true effect of zero, but this candidate's footprint and
noise, fails it:

| | 20 weeks | 6 weeks |
|---|---|---|
| check A | 57 % | 78 % |
| development | 19 % | 59 % |

It also cannot demonstrate non-harm. A +1.9 % point estimate with SD 5 passes, although harm up to about 12 % is
consistent with the data. At 6 prospective weeks it is mostly noise: TE and decile 8-10 standard deviations are
1.5-5 %, against margins of 1-2 %.

**The actual candidate is not near the margins.** 0 % of bootstrap replicates fail, and every one-sided upper bound is
inside them. So H2's pass does not depend on the rule's weakness.

**Not changed.** The v1.0 rule stands for H1 and is not modified retrospectively.

**Proposed for a separately versioned protocol, future data only (`HARM_RULE_v2_PROPOSAL.md`):**
- one-sided per-stratum non-inferiority bounds with a simultaneous or Holm correction;
- deciles formed within position-week;
- a harm flag when a lower bound exceeds 0;
- a rank-preservation check;
- a sample size planned so the margins are detectable.

A related gap: the H1 rule gives no verdict for a ratio of 1.00-1.05 with its interval above 1, or for an interval
entirely below 1.

## Files added in this commit

- `ERRATA_AND_INDEPENDENT_REVIEW_2026-10-11.md`: this file.
- `INDEPENDENT_REVIEW_H1.md`: the reviewer's report. Their scripts and outputs are in `review/` (`src/`, plus
  `recompute.json`, `refute.json`, `rule_sim.json`, `rule_sim6.json`, `rule_joint.json`, `sens_depthfix.json`).
- `check_b.py`, `CHECK_B_RESULT.json`: check B, reproducible.
- `portfolio_effect.py`, `W4_PORTFOLIO_EFFECT.txt`: the paired portfolio rebuild.
- `HARM_RULE_v2_PROPOSAL.md`: for future protocols only.
