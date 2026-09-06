# C2 — NFL clustering, design effects, statistical power, and gate timing

**Pass type:** CORRECTION. Research and measurement only. No predictive
production code was written and no file outside this one was modified.

**Date of measurement:** 2026-09-06, in this container.

**What this document is for.** The owner issued two corrections, (F) and (H),
against claims that currently stand in
`nfl/NFL_FOUNDATION_AND_MODEL_ARCHITECTURE.md` §2.3 and §7. Both corrections
say the same thing in two places: an MLB-measured clustering figure was
imported into NFL as though it were a constant, and conclusions were drawn from
it. This document estimates the NFL quantity directly and restates both
conclusions on NFL evidence.

Every substantive claim below carries exactly one of `VERIFIED`, `DERIVED`, or
`UNVERIFIED-RECALL`, per `nfl/research/_GROUNDING.md`.

**Headline, before the detail, because two of these are not what the owner's
correction anticipated:**

1. NFL's design effect is **not** MLB's 7.93 imported, and it is not a single
   number. It ranges from **≈1.0 to ≈10.5** depending entirely on *how many
   rows you write per player-game* and *which statistic you are computing*.
   At one graded row per player-game per market it is **≈1.0**. `DERIVED`
2. The "2,000–3,000 game-equivalents / 7–11 seasons" figure does not survive.
   Not because the NFL number differs from 7.93 — measured on a comparable row
   set it is 7.12, which is close — but because the **arithmetic that produced
   it multiplies a game count by a row-level design effect**, which is the same
   unit error `v8/experiments/J2_STOPPING_RULE.md` already recorded for MLB.
   `DERIVED`
3. The corrected NFL figure is **market-dependent and spans two orders of
   magnitude**: about **0.5 seasons for a broad receiving market** and about
   **3–6 seasons for a QB passing market**, at realistic effect sizes. The
   "7–11 seasons" headline is roughly right for thin markets and roughly ten
   times too pessimistic for broad ones. `DERIVED`
4. On gate timing, the correction **does not rescue the week-3 claim's
   reasoning but does not overturn its answer either** — for the broadest
   market. The 369 figure is not per-market supply, the per-market week-1
   supply is 152, and the binding constraint was never row count: it is the
   `min_distinct_dates = 10` breadth rule, which cannot clear before week 3 in
   any season measured. For QB and RB markets the gate is **8–11 weeks**, not
   3. `VERIFIED` + `DERIVED`

---

## 1. Provenance and method

### 1.1 Data — all `VERIFIED`

Downloaded in this container on 2026-09-06 with the command shape recorded in
`_GROUNDING.md`:

```
curl -sS -L -o OUT.csv "https://github.com/nflverse/nflverse-data/releases/download/<path>"
```

| Path | Bytes | md5 |
|---|---|---|
| `stats_player/stats_player_week_2022.csv` | 8,408,729 | `e8399c7da59ddc45c0ec59935ad16cca` |
| `stats_player/stats_player_week_2023.csv` | 8,332,874 | `af56ef21a44182ffc65d1f76f988bf39` |
| `stats_player/stats_player_week_2024.csv` | 8,470,040 | `4a708de137579069b5688467217a6601` |
| `stats_player/stats_player_week_2025.csv` | 8,656,387 | `10b14793616fc74657676b8323501166` |
| `schedules/games.csv` (cached as `schedules_games.csv`) | 2,177,171 | `882e4db26f2f4f18c18818d790be1316` |

**A `_GROUNDING.md` C4-class note, recorded because it cost ten minutes.**
`player_stats/player_stats_2025.csv` returns **404** while
`player_stats/player_stats_2024.csv` returns 200. The 2025 file is live at
`stats_player/stats_player_week_2025.csv` (**200**), and the same path serves
2022–2024. This is the third instance of C4's rule: *a 404 means that path
404ed.* All four seasons here are read from the `stats_player/` path so the
schema is identical across years. `VERIFIED`

**Schedule facts.** REG games by season: 2022 = **271**, 2023 = **272**,
2024 = **272**, 2025 = **272**. `_GROUNDING.md` carried "~272 regular-season
games per season" as `UNVERIFIED-RECALL` and asked worker 1 to confirm it. It is
now `VERIFIED` for 2023–2025; 2022 is 271 (one cancelled game — the reason is
`UNVERIFIED-RECALL` and is not load-bearing here). Games per week
272 / 18 = **15.11**. `VERIFIED`

**2024 REG panel:** 18,130 player-game stat rows, 272 games, **58 distinct
gamedays**, 18 weeks. 2025: 18,540 rows, 272 games, 57 gamedays. `VERIFIED`

### 1.2 A supply discrepancy against W8, recorded not resolved

W8 states 24.4 skill players per game → 369 skill player-games per week
(`W8_BENCHMARK_DFS.md:296,444`). Counting rows in the `stats_player` feed with
`position ∈ {QB, RB, WR, TE}` gives **5,864 skill player-games in 2024**
(6,037 in 2025) = **21.6 per game = 326 per week**. `VERIFIED`

The two numbers count different things — W8's denominator is not this feed —
and I did not reconcile them. It does not change any conclusion below, because
**neither number is the right one for the gate**: the gate is per market, and
per-market supply is measured in §4. Recorded so nobody later treats 369 and
326 as a contradiction that needs resolving before proceeding.

### 1.3 What is being clustered — the analysis unit

`board_config.json:270` fixes the gate's counting unit as **rows**, where a row
is defined by `graded_prediction_means`: *"a stored predicted probability for a
specific player, stat and threshold on a specific game, paired with that game's
realised outcome."*

So a row is a **(player, market, threshold, game)** tuple. Two multiplicities sit
above the player-game:

- **markets per player-game** — a WR carries receiving yards, receptions and
  anytime TD at minimum;
- **thresholds per market** — the alternate-line ladder.

MLB measured **31.4 rows per player-game** (`board_config.json:276`). The NFL
equivalent is not knowable from nflverse, because it depends on what Hard Rock
Bet actually offers. I therefore measure **two declared row designs** and report
both, rather than guessing one:

- **SINGLE-LINE** — one threshold per market per player-game. 2.9 rows per
  player-game across the eight markets below; ~39 rows per game.
- **LADDER** — a declared alternate-line ladder per market. 9.3 rows per
  player-game; ~125 rows per game.

Neither is a claim about Hard Rock's NFL board. **What Hard Rock actually offers
is unmeasured here and is the single largest input to which of these two
columns applies.** See §6.

### 1.4 The markets, the thresholds, and the eligibility rule — all DECLARED

`CLAUDE.md` rule 3 forbids silent constants. Every number in this subsection is
a **declared analysis choice**, chosen to sit near the population centre so the
binary is informative, and **not fitted to any result**. Changing them changes
the measured design effect; §2.6 reports the sensitivity.

| Market | Stat | SINGLE-LINE threshold | LADDER thresholds | Positions |
|---|---|---|---|---|
| `rec_yds` | receiving_yards | 49.5 | 29.5 / 39.5 / 49.5 / 59.5 / 69.5 | WR, TE, RB |
| `receptions` | receptions | 3.5 | 2.5 / 3.5 / 4.5 / 5.5 | WR, TE, RB |
| `rush_yds` | rushing_yards | 49.5 | 29.5 / 39.5 / 49.5 / 59.5 / 69.5 | RB |
| `carries` | carries | 12.5 | 10.5 / 12.5 / 14.5 | RB |
| `pass_yds` | passing_yards | 224.5 | 199.5 / 224.5 / 249.5 / 274.5 | QB |
| `pass_tds` | passing_tds | 1.5 | 0.5 / 1.5 / 2.5 | QB |
| `completions` | completions | 20.5 | 18.5 / 20.5 / 22.5 | QB |
| `anytime_td` | rush TD + rec TD | 0.5 | 0.5 | RB, WR, TE |

**Eligibility.** Two rules are used and they are not interchangeable:

- *Forward-chained* (§2, the ICC/DEFF measurements): player has ≥ 2 prior games
  this season **and** prior-weeks mean targets ≥ 3.0 (receiving), carries ≥ 8.0
  (rushing), attempts ≥ 15.0 (passing). Uses no future information. Costs
  weeks 1–2.
- *Season-level* (§4, the gate accumulation curve, where weeks 1–2 are the whole
  question): player has ≥ 6 games and season-mean targets ≥ 3.0 / carries ≥ 8.0
  / attempts ≥ 15.0. **This is ex-post and is a selection.** It stands in for
  "a book would have listed this player", which cannot be measured from
  nflverse. Its effect is to slightly *understate* week-1 row supply variance;
  it is labelled everywhere it is used.

### 1.5 The predicted probability, and why one is needed at all

A design effect is a property of **a statistic on a population**, not of the
population alone. The statistic that matters for the calibration gate is
calibration-in-the-large: the mean of the residual `e = y − p̂`. So a `p̂` is
required.

There is no NFL forecaster. I use a deliberately crude forward-chained baseline:

```
p̂(player, market, line, week w) = (hits in weeks < w  +  K · p_league(< w))
                                  / (games in weeks < w  +  K)
```

with `p_league(< w)` the league hit rate for that market and line over weeks
strictly before `w` in the same season, and **`K = 5` a DECLARED shrinkage prior,
not a fitted constant.** `K ∈ {2, 5, 10}` was checked; see §2.6.

**This baseline conditions on the player and nothing else.** It has no opponent
term, no game total, no weather, no game script. That matters for the direction
of every number here, and §2.5 measures the direction.

### 1.6 Two estimators, reported side by side

- **ICC (one-way random-effects ANOVA)** and the Kish design effect
  `DEFF_formula = 1 + (m_a − 1)·ICC`, with `m_a = Σmᵢ²/Σmᵢ`.
- **Empirical design effect** — the ratio the MLB figure was built from:
  `DEFF_emp = (SE_clustered / SE_naive)²` for the sample mean, with a
  finite-cluster correction `k/(k−1)`.

Uncertainty is a **cluster bootstrap** (resample whole clusters with
replacement, 400 replicates for DEFF, 300 for ICC), which is the resampling
scheme `CLAUDE.md` rule 9 requires. Seed 20260906.

Scripts live in the session scratchpad under `c2/` (`panel.py`, `rows.py`,
`icc.py`, `ladder.py`, `multi.py`, `cont.py`, `selfmed.py`, `gate.py`,
`cross.py`, `rdeff.py`, `power.py`, `upper.py`). They are evidence, not
deliverables, and are not committed to `nfl/` per the grounding brief's scope
limit.

---

## 2. The central deliverable — NFL intra-cluster correlation, measured

### 2.1 The MLB number this replaces

`CLAUDE.md` records pooled naive SE **0.587pp** against **1.653pp** clustered by
game, on MLB prop rows. `(1.653 / 0.587)² = 7.930`. `VERIFIED` (arithmetic
reproduced; the underlying MLB measurement is quoted, not re-run — the corpus is
not reproducible per `CLAUDE.md`'s M0-D).

### 2.2 Binary prop-like outcome, residual `e = y − p̂`, four schemes

**SINGLE-LINE row set, all eight markets pooled.** Statistic: mean residual.

Season 2024, N = 9,355 rows, 240 games. `VERIFIED`

| Clustering | clusters | m̄ | m_Kish | ICC | ICC 95% CI | DEFF_formula | DEFF_emp | DEFF_emp 95% CI |
|---|---|---|---|---|---|---|---|---|
| game | 240 | 38.98 | 39.66 | 0.0315 | [0.0230, 0.0391] | 2.22 | **2.20** | [1.86, 2.55] |
| team-game | 480 | 19.49 | 20.16 | 0.0619 | [0.0484, 0.0736] | 2.19 | 2.11 | [1.89, 2.36] |
| player (within season) | 327 | 28.61 | 39.36 | 0.0398 | [0.0307, 0.0499] | 2.53 | 2.30 | [1.99, 2.63] |
| date (gameday) | 51 | 183.4 | 397.6 | 0.0088 | [0.0036, 0.0154] | 4.47 | 2.66 | [1.48, 3.67] |
| week | 16 | 584.7 | 588.9 | 0.0032 | [0.0004, 0.0060] | 2.88 | 3.01 | [1.29, 4.96] |
| player-game | 3,232 | 2.89 | 3.23 | 0.3072 | [0.2826, 0.3283] | 1.68 | 1.68 | [1.63, 1.73] |

**LADDER row set, all eight markets pooled.** Season 2024, N = 30,039 rows,
9.29 rows per player-game, 125.2 rows per game. `VERIFIED`

| Clustering | clusters | m̄ | m_Kish | ICC | DEFF_formula | DEFF_emp | DEFF_emp 95% CI |
|---|---|---|---|---|---|---|---|
| game | 240 | 125.2 | 127.7 | 0.0467 | 6.92 | **6.76** | [5.77, 7.96] |
| team-game | 480 | 62.6 | 65.1 | 0.0902 | 6.78 | 6.43 | [5.74, 7.17] |
| player (within season) | 327 | 91.9 | 135.4 | 0.0730 | 10.81 | 8.79 | [7.48, 10.05] |
| date (gameday) | 51 | 589.0 | 1278.2 | 0.0125 | 16.90 | 8.29 | [4.47, 11.55] |
| week | 16 | 1877.4 | 1890.5 | 0.0043 | 9.04 | 9.33 | [3.28, 13.85] |
| player-game | 3,232 | 9.29 | 11.17 | 0.4399 | 5.47 | 5.18 | [5.02, 5.33] |

**Multiway clustering** (Cameron–Gelbach–Miller: `V_A + V_B − V_{A∩B}`), which is
the right estimator when both games and players repeat across the accumulation
window. `VERIFIED`

| Row set | season | two-way (game, player) | two-way (date, player) |
|---|---|---|---|
| SINGLE-LINE | 2024 | **2.83** | 3.28 |
| SINGLE-LINE | 2025 | **3.18** | 3.66 |
| LADDER | 2024 | **10.37** | 11.90 |
| LADDER | 2025 | **10.53** | 11.88 |

**Four-season replication, clustered by game.** `VERIFIED`

| Season | SINGLE-LINE N | DEFF | 95% CI | n_eff | LADDER N | DEFF | 95% CI | n_eff |
|---|---|---|---|---|---|---|---|---|
| 2022 | 9,260 | 2.18 | [1.86, 2.48] | 4,247 | 29,859 | 6.55 | [5.59, 7.54] | 4,556 |
| 2023 | 9,294 | 2.38 | [2.04, 2.74] | 3,902 | 29,974 | 7.15 | [5.92, 8.32] | 4,193 |
| 2024 | 9,355 | 2.20 | [1.89, 2.56] | 4,252 | 30,039 | 6.76 | [5.76, 7.68] | 4,446 |
| 2025 | 9,141 | 2.78 | [2.32, 3.28] | 3,283 | 29,507 | 8.01 | [6.75, 9.35] | 3,686 |
| **mean (sd)** | | **2.39 (0.28)** | | **3,921** | | **7.12 (0.64)** | | **4,220** |

**The single most useful line in this document.** Compare the two `n_eff`
columns. The LADDER row set contains **3.2× as many rows** as the SINGLE-LINE
set and carries **essentially the same amount of independent information**
(4,220 vs 3,921 effective units per season, a 7.6% gain for a 220% increase in
rows). `DERIVED`

The transferable NFL quantity is therefore not a design effect at all. It is:

> **Effective independent player-prop observations per NFL game ≈ 14–19**, for
> an eight-market menu, and it barely moves when you add alternate lines.
> `DERIVED` (2024: 9,355/2.20/240 = 17.7 single-line; 30,039/6.76/240 = 18.5
> ladder. Across four seasons: single-line 13.7 / 16.3 / 17.7 / 17.8 and ladder
> 15.4 / 17.5 / 18.5 / 19.1, i.e. **13.7 to 19.1**, with 2025 the low year in
> both row designs.)

### 2.3 Single market, one line per player-game — the case where DEFF ≈ 1

This is the configuration that matters most for the gate, because the gate is
per market. Season 2024, clustered by game, residual statistic. `VERIFIED`

| Market | N | clusters | m_Kish | ICC | ICC 95% CI | DEFF_emp | 95% CI |
|---|---|---|---|---|---|---|---|
| `rec_yds` | 2,053 | 240 | 8.85 | 0.0033 | [−0.0193, 0.0239] | **1.02** | [0.86, 1.19] |
| `receptions` | 2,053 | 240 | 8.85 | −0.0040 | [−0.0245, 0.0176] | **0.96** | [0.81, 1.11] |
| `anytime_td` | 2,774 | 240 | 11.83 | −0.0115 | [−0.0253, 0.0023] | **0.88** | [0.71, 1.04] |
| `rush_yds` | 575 | 239 | 2.68 | −0.0875 | [−0.1696, 0.0011] | **0.83** | [0.72, 0.97] |
| `pass_yds` | 458 | 240 | 2.01 | 0.1288 | [−0.0193, 0.2585] | **1.12** | [0.97, 1.25] |

**Read this correctly.** A DEFF below 1.0 is not a discovery that games are
anti-correlated; it is a small-negative ICC estimate, which the ANOVA estimator
produces routinely when the true ICC is near zero. The defensible statement is
that **at one graded row per player-game per market, clustering by game costs
between nothing and about 25%**, and the confidence intervals include 1.0 in
every case.

The design effects in §2.2 come almost entirely from writing several rows about
the same player-game, not from NFL players in the same game being coupled.
`DERIVED`

### 2.4 The outcome definitions the correction asked for

**Self-referenced binary** — `y = 1` if the stat exceeds the player's own
season median, so the line is per-player and `p ≈ 0.5` by construction. This
removes between-player variance by design, which isolates game- and week-level
structure. It uses full-season information to set the line, so it is a
**descriptive variance-decomposition device and not a forecast.** `VERIFIED`

| Market | Season | n | hit rate | ICC game | ICC 95% CI | DEFF game | DEFF date | DEFF week |
|---|---|---|---|---|---|---|---|---|
| `rec_yds` | 2024 | 1,900 | 0.469 | 0.010 | [−0.013, 0.041] | 1.06 | 1.16 | 1.31 |
| `rec_yds` | 2025 | 1,845 | 0.469 | 0.040 | [0.010, 0.067] | 1.28 | 1.69 | 2.36 |
| `rush_yds` | 2024 | 493 | 0.475 | −0.087 | [−0.197, 0.019] | 0.89 | 0.68 | 0.67 |
| `rush_yds` | 2025 | 511 | 0.464 | −0.134 | [−0.225, −0.032] | 0.80 | 1.01 | 1.22 |
| `pass_yds` | 2024 | 419 | 0.468 | 0.151 | [0.017, 0.295] | 1.14 | 1.71 | 1.71 |
| `pass_yds` | 2025 | 424 | 0.472 | 0.127 | [−0.014, 0.280] | 1.13 | 1.38 | 1.63 |

Note `pass_yds`: ICC by game is 0.13–0.15, which is the largest game-level ICC
anywhere in this document — two QBs in the same game genuinely share a scoring
environment, and with `m ≈ 1.9` that still only produces DEFF ≈ 1.14.
Receiving is near zero. Rushing is negative, which is consistent with the
within-team-game substitution the architecture doc's §3.5 redistribution
section already anticipates. `DERIVED`

**Continuous outcomes**, 2024, three variable definitions each. `VERIFIED`

| Stat | Variable | ICC game | DEFF game | ICC player | DEFF player | ICC date | DEFF date |
|---|---|---|---|---|---|---|---|
| receiving_yards (n=2,053, mean 41.4, sd 35.0) | raw level | −0.006 | 0.97 | **0.290** | **4.20** | 0.001 | 1.09 |
| | player-centred | 0.031 | 1.23 | −0.119 | 0.00 | 0.013 | 1.73 |
| | residual vs prior mean | 0.022 | 1.17 | −0.030 | 0.78 | 0.009 | 1.55 |
| rushing_yards (n=526, mean 59.3, sd 40.1) | raw level | −0.098 | 0.85 | **0.354** | **4.74** | −0.033 | 0.65 |
| | residual vs prior mean | −0.039 | 0.90 | 0.008 | 1.02 | −0.015 | 0.87 |
| passing_yards (n=458, mean 223.7, sd 83.2) | raw level | 0.122 | 1.18 | **0.155** | **2.23** | 0.059 | 1.78 |
| | residual vs prior mean | 0.131 | 1.14 | 0.004 | 0.94 | 0.047 | 1.71 |

**The distinction this table exists to make.** The only large ICC on a
continuous NFL prop outcome is **by player, on the raw level** — 0.29 to 0.35.
That is *between-player skill*, which is the thing a forecaster is supposed to
predict. It is **not** a source of dependence in a forecaster's errors: once you
subtract a player-specific prediction, player-level ICC drops to −0.03 to +0.01
and the design effect drops to ≈1.0.

Anyone who computes an ICC on raw player-game outcomes and applies it as a design
effect to a forecast evaluation will inflate the requirement roughly fourfold
for no reason. That error is available in this data and is worth naming before
someone makes it. `DERIVED`

### 2.5 Direction of bias — these design effects are upper bounds

The §1.5 baseline has no game-environment term. If the game-level ICC I measure
is partly predictable game environment, then a forecaster that models game
environment would show a *smaller* residual ICC, and my design effects are
conservative.

Measured with an **oracle** control (residual regressed on the game's realised
total points — this uses the outcome and is descriptive only, per `CLAUDE.md`
rule 6 it manufactures nothing because it is not being used to define a defect):
`VERIFIED`

| Row set, 2024 | ICC by game | DEFF by game |
|---|---|---|
| `rec_yds` single-line, baseline residual | 0.0074 | 1.05 |
| `rec_yds` single-line, after oracle game total | 0.0009 | **1.00** |
| pooled LADDER, baseline residual | 0.0467 | 6.76 |
| pooled LADDER, after oracle game total | 0.0323 | **4.95** |

A perfect game-total forecast would remove about **27%** of the pooled ladder
design effect and essentially all of the single-line one. The numbers in §2.2
and §2.3 are therefore upper bounds relative to a forecaster that conditions on
game environment. `DERIVED`

### 2.6 Sensitivity, and the caveats that belong with every number above

- **Shrinkage prior `K`.** Re-run on the pooled 2024 row sets at `K = 2`, `5`,
  `10` and `K → ∞` (league rate only, no player history at all). `VERIFIED`

  | Row set | K=2 | K=5 | K=10 | league-only |
  |---|---|---|---|---|
  | LADDER pooled (N=30,039) | 6.72 | 6.76 | 6.76 | 6.72 |
  | single-line subset (N=9,764) | 2.47 | 2.47 | 2.46 | 2.44 |

  The design effect moves by less than 0.05 across the whole range, against a
  bootstrap width of roughly ±1.0. This is expected rather than reassuring: the
  design effect is a property of the residual's cluster structure, not of the
  baseline's sharpness. It does mean **no conclusion here depends on `K = 5`.**
- **Threshold placement.** Every threshold in §1.4 is declared, not fitted.
  Moving a line into a tail lowers the outcome variance and can move ICC
  materially. The `anytime_td` row (hit rate 0.25–0.28) already shows a
  different sign from the near-0.5 markets. **No claim here should be
  transported to a market whose line sits far from the middle without
  re-measuring.**
- **Eligibility is a selection.** §1.4's rules are usage filters, not a book's
  listing decision. A real prop board is a different population and will
  include marginal players whose outcomes are more injury- and game-script
  driven, which would raise game-level ICC.
- **Cluster counts.** The date scheme has 51 clusters and the week scheme has
  16. Their bootstrap intervals are correspondingly wide ([4.47, 11.55] and
  [3.28, 13.85] for the 2024 ladder). Those two rows should be read as
  "somewhere between the game figure and roughly double it", not as point
  estimates.
- **Postseason is out of scope** (`CLAUDE.md` rule 10); REG only throughout.
- I have **not** shown that any of these design effects is close to any other,
  and I am not writing "stable", "unbiased" or "correct" about them. There is no
  predeclared equivalence margin and no TOST here, per `CLAUDE.md` rule 8.

### 2.7 Design effects are statistic-specific — and this is the crux of §3

Everything above is the design effect for a **calibration** statistic (the mean
residual). The power calculation in §3 is about a **correlation**. These are not
the same design effect and the difference is large.

Measured directly: Fisher-z of `corr(p̂, y)`, cluster-bootstrapped by game,
600 replicates. `VERIFIED`

| Market | Variant | Season | n | r | SE_z naive | SE_z bootstrap | **DEFF_r** |
|---|---|---|---|---|---|---|---|
| `rec_yds` | single | 2024 | 2,426 | 0.3304 | 0.02032 | 0.01978 | **0.95** |
| `rec_yds` | single | 2025 | 2,291 | 0.3081 | 0.02091 | 0.02283 | **1.19** |
| `rec_yds` | ladder | 2024 | 12,130 | 0.4027 | 0.00908 | 0.01265 | 1.94 |
| `receptions` | single | 2024 | 2,426 | 0.2976 | 0.02032 | 0.01917 | 0.89 |
| `receptions` | ladder | 2024 | 9,704 | 0.4300 | 0.01015 | 0.01121 | 1.22 |
| `rush_yds` | single | 2024 | 598 | 0.2414 | 0.04100 | 0.04145 | 1.02 |
| `rush_yds` | ladder | 2024 | 2,990 | 0.3714 | 0.01830 | 0.02331 | 1.62 |
| `pass_yds` | single | 2024 | 555 | 0.1294 | 0.04256 | 0.04469 | 1.10 |
| `pass_yds` | ladder | 2024 | 2,220 | 0.2921 | 0.02124 | 0.02594 | 1.49 |
| `anytime_td` | single | 2024 | 3,316 | 0.1986 | 0.01737 | 0.01927 | 1.23 |

**On the same ladder row set where the calibration design effect is 6.76, the
discrimination design effect is 1.94.** `VERIFIED`

The reason is mechanical: a correlation statistic already conditions on `p̂`,
which varies within a cluster; a mean-residual statistic does not. Using a
calibration-measured design effect in a correlation power calculation inflates
the requirement by roughly 3.5× on the ladder set and does nothing at all on the
single-line set.

**This is the third distinct unit error available in this corner of the
project**, after the SE-ratio-as-multiplier error (`_GROUNDING.md` C1) and the
games-times-row-DEFF error (§3.1). All three are the same failure: a number
carried across a boundary its definition does not cross.

---

## 3. Correction (F) — the 7.93 import and the "7–11 seasons" figure

> **(F), verbatim:** "Keep the finding that clustered player-level confirmation
> requires substantially more evidence than naive row counts. However: do not
> promote MLB's 7.93 design effect into an NFL constant; estimate NFL effective
> sample size/design effects directly when enough NFL data exists; mark the
> 2,000–3,000 game-equivalent / 7–11 season estimate as planning-level DERIVED
> until NFL-specific clustering validates it."

### 3.1 The finding that survives — kept, and strengthened

**Clustered player-level confirmation does require substantially more evidence
than naive row counts.** NFL data confirms it and quantifies it: on the LADDER
row set, **12,130 `rec_yds` rows in a 2024 season carry ~3,138 effective
independent units** (DEFF 3.87). Season-wide across eight markets, 30,039 rows
carry ~4,446. A naive row count overstates the evidence by a factor of
**3 to 10** whenever more than one line per player-game is graded. `VERIFIED`

The owner's finding stands. Only its magnitude and its scope needed measuring.

### 3.2 The import is refused, and the NFL number is measured instead

MLB's 7.93 is not promoted into an NFL constant. NFL's measured equivalent, on
a comparable multi-line row set clustered by game, is:

> **DEFF = 7.12, sd 0.64 across four seasons, range [6.55, 8.01]**,
> at 9.3 rows per player-game. `VERIFIED`

**Does it differ materially from MLB's 7.93? Not on this comparison — and that
is a coincidence, not a validation.** MLB reached 7.93 at **31.4 rows per
player-game**; NFL reaches 7.12 at **9.3**. Per row written, NFL prop rows are
*more* strongly coupled than MLB's, not less. Had NFL been graded at MLB's row
density the design effect would be substantially higher.

So the honest statement is the opposite of a reassurance: **the two numbers
agreeing is an artifact of different row designs cancelling different
correlations, and neither number transfers.** What transfers is §2.2's
per-game effective count. `DERIVED`

### 3.3 The "2,000–3,000 game-equivalents / 7–11 seasons" figure — WITHDRAWN

`NFL_FOUNDATION_AND_MODEL_ARCHITECTURE.md:110-128` carries:

| Analysis level | Games needed | NFL seasons at 272 REG |
|---|---|---|
| Game-level r (0.11 → 0.25) | ~377 | ~1.4 |
| Player-prop, with clustering | ~2,000–3,000 game-equivalents | **7–11** |

**The first row reproduces.** Fisher-z, α = .05 two-sided, power 0.80,
r 0.11 → 0.25: `n = ((1.959964 + 0.841621) / (atanh(0.25) − atanh(0.11)))² + 3
= (2.801585 / 0.144966)² + 3 = 376.5`. And 377/272 = 1.39 seasons. `VERIFIED`

**The second row is a unit error.** `376.5 × 7.930 = 2,985`, which is where
"~2,000–3,000" comes from and where 2,985/272 = 11.0 seasons comes from. The
multiplication takes:

- **377**, a count of **games**, derived for a **game-level** correlation
  endpoint where one game is one observation; and multiplies it by
- **7.93**, a variance inflation for **prop rows clustered by game**, on a
  **calibration** statistic.

The product is games × (rows-per-game correlation penalty) × (wrong statistic).
It denominates in nothing.

**This project has already recorded this exact error.** `J2_STOPPING_RULE.md:47-58`
states it in terms — *"Do NOT reuse DEFF 10.54 from the prop-row design; games do
not nest inside games"* — and files the MLB version as
`Clustering | deff = 3 | DOES_NOT_APPLY | square error (7.93), and it is a
prop-row measurement forbidden for a game-level endpoint`. The NFL architecture
document inherited the correction to J2's *defect 1* (the square) while
inheriting the uncorrected *defect 2* (the unit). `VERIFIED`

**Disposition: the 2,000–3,000 / 7–11 figure is WITHDRAWN as an NFL figure.**
Not downgraded to planning-level DERIVED — the owner's instruction was to
downgrade it pending NFL measurement, and the NFL measurement does not support
it at any confidence level, because the defect is in the arithmetic rather than
in the input. It is recorded here rather than deleted, per `CLAUDE.md`.

### 3.4 The corrected NFL figure

The arithmetic, stated so it can be re-run with different inputs:

```
n_independent      = Fisher-z requirement for the declared effect size
rows_required      = n_independent × DEFF_r          (the DISCRIMINATION DEFF, §2.7)
games_required     = rows_required / (rows per game for that market)
seasons_required   = games_required / 272
weeks_required     = games_required / 15.11
```

**(a) At the architecture document's own declared effect size, r 0.11 → 0.25:**
`DERIVED`

| Market | Variant | rows/game | DEFF_r | rows req. | games req. | seasons | weeks |
|---|---|---|---|---|---|---|---|
| `rec_yds` | single | 8.92 | 0.95 | 358 | **40** | 0.15 | 2.7 |
| `rec_yds` | ladder | 44.6 | 1.94 | 730 | **16** | 0.06 | 1.1 |
| `receptions` | single | 8.92 | 0.89 | 335 | **38** | 0.14 | 2.5 |
| `anytime_td` | single | 12.19 | 1.23 | 463 | **38** | 0.14 | 2.5 |
| `rush_yds` | single | 2.20 | 1.02 | 384 | **175** | 0.64 | 11.6 |
| `pass_yds` | single | 2.04 | 1.10 | 414 | **203** | 0.75 | 13.4 |

**Not 7–11 seasons. 0.06 to 0.75 seasons — a factor of 10 to 180 smaller.**
The reason is simple once the units are fixed: an NFL game supplies between 2
and 45 prop rows carrying **2 to 23 effective independent observations**, so
377 effective observations do not need 377 games, let alone 2,985.

**(b) But r 0.11 → 0.25 is an MLB game-total target and does not describe an
NFL prop analysis.** My crude §1.5 baseline already achieves r = 0.13 to 0.43
depending on market (§2.7). Detecting a *realistic improvement over a real
baseline* is the harder and honest question. `DERIVED`

| Market | baseline r (measured) | target | n indep. | DEFF_r | rows req. | games req. | **seasons** |
|---|---|---|---|---|---|---|---|
| `rec_yds` | 0.330 | +0.05 → 0.380 | 2,398 | 0.95 | 2,278 | 255 | **0.94** |
| `rec_yds` | 0.330 | +0.07 → 0.400 | 1,204 | 0.95 | 1,144 | 128 | **0.47** |
| `rec_yds` | 0.330 | +0.10 → 0.430 | 575 | 0.95 | 547 | 61 | **0.23** |
| `receptions` | 0.298 | +0.05 | 2,521 | 0.89 | 2,244 | 252 | **0.92** |
| `receptions` | 0.298 | +0.07 | 1,268 | 0.89 | 1,129 | 127 | **0.47** |
| `anytime_td` | 0.199 | +0.05 | 2,835 | 1.23 | 3,487 | 286 | **1.05** |
| `anytime_td` | 0.199 | +0.07 | 1,433 | 1.23 | 1,763 | 145 | **0.53** |
| `rush_yds` | 0.241 | +0.05 | 2,711 | 1.02 | 2,765 | 1,258 | **4.62** |
| `rush_yds` | 0.241 | +0.07 | 1,368 | 1.02 | 1,395 | 635 | **2.33** |
| `pass_yds` | 0.129 | +0.05 | 2,993 | 1.10 | 3,293 | 1,614 | **5.93** |
| `pass_yds` | 0.129 | +0.07 | 1,518 | 1.10 | 1,670 | 818 | **3.01** |

**The corrected NFL statement, with its uncertainty:**

> **DERIVED, planning-level.** A confirmatory NFL player-prop claim needs, at
> 80% power and α = .05 two-sided:
> - **broad receiving and anytime-TD markets: 0.2 to 1.0 seasons** (61–286
>   games) for a +0.05 to +0.10 improvement in r over a simple own-rate
>   baseline;
> - **QB and RB markets: 2.3 to 5.9 seasons** (635–1,614 games) for the same
>   improvements, because those markets supply only ~2 rows per game.
>
> Uncertainty on the design-effect input is ±20% (four-season sd 0.64 on 7.12,
> and bootstrap intervals of roughly ±15% on each season's figure), which moves
> every seasons figure by less than ±20%. **The dominant uncertainty is not the
> design effect. It is the declared effect size**, which moves the answer by a
> factor of four across the columns above, and the **baseline r**, which is
> currently a crude own-rate baseline and not a real NFL forecaster.

**So "7–11 seasons" is in the right neighbourhood for QB passing at a small
effect size, and roughly ten times too pessimistic for receiving markets.**
A single headline number for "NFL player props" does not exist; the market's
rows-per-game is the dominant term and it varies 20-fold across the board.

### 3.5 What this does not license

None of §3.4 is an argument that a confirmatory NFL claim is quick. Three
constraints sit outside the power arithmetic and are not relaxed by it:

1. **Confirmatory requires unseen games** (`CLAUDE.md`, "Critical constraint",
   and V8 Rule 006). Games arrive at 15.11 per week regardless of how many rows
   each supplies. A 128-game requirement is **8.5 weeks of calendar** that
   cannot be compressed.
2. **Design decisions must be made outside the evaluation fold.** Every number
   in §3.4 assumes the candidate and the metric were fixed before the window
   opened.
3. **`season_boundary`** (`board_config.json`) permits pooling across seasons
   only absent a declared structural rule change. Whether NFL's annual rule
   changes qualify is unmeasured and unruled — see §6.

---

## 4. Correction (H) — gate timing, recomputed

> **(H), verbatim:** "Withdraw 'gate reachable in roughly three weeks because
> Week 1 supplies 369 player-games' as a hard conclusion. Correlated
> player-games are not independent observations. Recompute effective sample size
> under the actual grading unit and clustering structure. Keep the ≥5-season
> trigger statement as DEFERRED planning guidance only until Hard Rock NFL
> market availability and actual eligible-play frequency are measured."

### 4.1 The claim being corrected

`NFL_FOUNDATION_AND_MODEL_ARCHITECTURE.md:510-535`, from `W8_BENCHMARK_DFS.md:444-462`:

> The **gate** is fast — breadth-bound at roughly **end of week 3**, since week 1
> alone supplies 369 skill player-games against a 300-row floor.

Three separate things are wrong with the *reasoning*, and they are worth
separating because only one of them is the one the owner named.

**(i) 369 is not per-market supply, and the gate is per market.**
`board_config.json` scopes the gate per market throughout — `failure_policy`
("A market that fails its calibration backtest…"), the `breadth` block, and
`guards.assert_market_eligible_for_live`. Measured week-1 supply **per market**,
2024, one line per player-game: `VERIFIED`

| Market | week-1 rows (2024) | 4-season median |
|---|---|---|
| `anytime_td` | 201 | 194 |
| `rec_yds` | 152 | 145.5 |
| `receptions` | 152 | 145.5 |
| `rush_yds` | 39 | 40 |
| `pass_yds` | 34 | 32.5 |

No single market supplies 300 rows in week 1 at one line per player-game. The
largest supplies **152**.

**(ii) Correlated player-games are not independent observations** — the owner's
point. Correct in principle. **Measured, it costs almost nothing at one line per
player-game** (§2.3: DEFF 0.83–1.12) and it costs a factor of 3–4 on a ladder.

**(iii) The row count was never the binding constraint.** `min_distinct_dates =
10` (`board_config.json:282`) is. NFL plays on 3 gamedays in a typical week and
4 in week 1. Cumulative distinct gamedays, 2024: **4, 7, 10, 13, 16, …**
`VERIFIED`. Ten dates therefore cannot be reached before the end of week 3, and
in 2022 and 2023 it took until **week 4**.

### 4.2 The accumulation curve, week by week

Season 2024, market `rec_yds`, one line per player-game. `n_eff = rows / DEFF`,
with DEFF re-estimated on the accumulated rows at each week. `VERIFIED`

| Week | rows | dates | player-games | games | DEFF (game) | DEFF (2-way g,p) | **n_eff** | n_eff (2-way) |
|---|---|---|---|---|---|---|---|---|
| 1 | 152 | 4 | 152 | 16 | 1.20 | 1.20 | 126 | 126 |
| 2 | 294 | 7 | 294 | 32 | 1.13 | 1.12 | 261 | 262 |
| **3** | **437** | **10** | **437** | 48 | 0.91 | 0.74 | **483** | **590** |
| 4 | 580 | 13 | 580 | 64 | 1.04 | 0.96 | 559 | 601 |
| 5 | 708 | 16 | 708 | 78 | 0.96 | 1.01 | 735 | 699 |
| 10 | 1,374 | 31 | 1,374 | 152 | 0.98 | 1.14 | 1,395 | 1,203 |
| 18 | 2,426 | 58 | 2,426 | 272 | 1.05 | 1.30 | 2,311 | 1,865 |

Same market, LADDER (5 lines): `VERIFIED`

| Week | rows | dates | DEFF (game) | **n_eff** |
|---|---|---|---|---|
| 1 | **760** | 4 | 5.81 | **131** |
| 2 | 1,470 | 7 | 5.48 | 268 |
| **3** | 2,185 | **10** | 4.68 | **467** |
| 18 | 12,130 | 58 | 3.87 | 3,138 |

**Week 1 of a laddered receiving market writes 760 graded rows carrying 131
effective independent units.** That single line is the whole of correction (H)
made concrete. `DERIVED`

### 4.3 First week each floor is crossed — median across four seasons

`VERIFIED` (per-season detail in the scratchpad `c2/crossings.csv`). **Season
spread matters and is not uniform:** the `rows ≥ 300` columns agree to within
one week across all four seasons in every market, but the `n_eff` columns
spread more — `rush_yds` single crosses at weeks 7/8/8/9 and `pass_yds` single
two-way at weeks 6/7/8/13. Read the medians below as ±1 week for row-count
cells and ±2–3 weeks for the effective cells on thin markets.

| Market | Variant | wk-1 rows | rows ≥ 300 | rows ≥ 500 | **n_eff ≥ 300** | n_eff ≥ 300 (2-way) | dates ≥ 10 | pg ≥ 50 |
|---|---|---|---|---|---|---|---|---|
| `rec_yds` | single | 146 | wk 3 | wk 4 | **wk 3** | wk 2.5 | wk 3.5 | wk 1 |
| `rec_yds` | ladder | 728 | wk 1 | wk 1 | **wk 2** | wk 2 | wk 3.5 | wk 1 |
| `receptions` | single | 146 | wk 3 | wk 4 | **wk 3** | wk 3 | wk 3.5 | wk 1 |
| `receptions` | ladder | 582 | wk 1 | wk 1 | **wk 2** | wk 2 | wk 3.5 | wk 1 |
| `anytime_td` | single | 194 | wk 2 | wk 3 | **wk 1.5** | wk 1.5 | wk 3.5 | wk 1 |
| `rush_yds` | single | 40 | wk 8.5 | wk 14.5 | **wk 8** | wk 7.5 | wk 3.5 | wk 2 |
| `rush_yds` | ladder | 200 | wk 2 | wk 3 | **wk 5.5** | wk 6 | wk 3.5 | wk 2 |
| `pass_yds` | single | 33 | wk 11 | wk 17.5 | **wk 10** | wk 7.5 | wk 3.5 | wk 2 |
| `pass_yds` | ladder | 130 | wk 3 | wk 4 | **wk 8** | wk 7 | wk 3.5 | wk 2 |

### 4.4 The corrected answer, stated plainly

**Under the rule as written** (`gate_floor_unit: "rows"`, §5):

- Broadest markets (`rec_yds`, `receptions`, `anytime_td`), one line per
  player-game: **end of week 3**, and the binding constraint is the 10-date
  breadth rule, not the 300-row floor. In 2022 and 2023 it was **week 4**.
- Same markets with an alternate-line ladder: rows clear in **week 1**, dates
  still bind at **week 3 or 4**.
- The 500-row low-probability floor: **week 4** single-line, week 1 laddered.
- `rush_yds`: **week 8–9** single-line, week 3–4 laddered (date-bound).
- `pass_yds`: **week 11** single-line, week 3–4 laddered (date-bound).

**Under an effective-independent-units reading** (a reinterpretation — see §5):

- Broadest markets, single line: **end of week 3.** Unchanged.
- Broadest markets, laddered: **week 2–3**, not week 1. The ladder's apparent
  week-1 clearance is borrowed entirely from correlation.
- `rush_yds`: **week 5–8.**
- `pass_yds`: **week 8–10.**

**So the specific sentence in the correction — "gate reachable in roughly three
weeks because Week 1 supplies 369 player-games" — is withdrawn on its reasoning
and retained on its answer, for the broadest market only.** Three weeks is
right. "Because week 1 supplies 369 player-games" is wrong twice: the supply is
152 for the biggest market, and the constraint that actually produces week 3 is
the calendar, which no amount of row supply can accelerate.

**The part of W8's claim that does not survive at all** is its implicit
generality. "The gate is fast" is true for three of the eight markets measured.
For QB and RB markets the calibration gate is a **two-to-three-month**
proposition under the rule as written and longer under the effective reading —
and `board_config.json`'s `two_stage_bar.ordering_is_not_optional` means the
margin trigger for those markets cannot even begin to accrue until then.

**And the precondition W8 states is unchanged and absolute.**
`graded_prediction_means` forbids percentiles. If the joint draw archive does
not ship before week 1, none of the clocks above start — not slowly, not
partially. Nothing in this document touches that.

---

## 5. What the 300 floor actually counts — two readings, and the distinction matters

**This section exists because §4's "effective" column is a reinterpretation of
an owner-set rule, and presenting it as a measurement would be a silent
redefinition.**

### 5.1 The rule as written

`board_config.json:255-285`, `operating_constraints.decision_objective.sample_floor`:

- `gate_unit`: **"graded predictions"**; `gate_min` 300, `gate_min_low_probability` 500.
- `trigger_unit`: **"graded resolved bets"**; same floors.
- `resolved_means`: **"Terminal settlement (Won, Lost, Refunded, Half Won, Half
  Lost). Pending does not count."**
- `gate_floor_unit`: **`"rows"`** (line 270).
- `gate_floor_unit_ruling` (line 271), verbatim:

  > "Ruled 2026-08-30: count ROWS, the way a professional would -- meaning rows
  > count toward the floor, and correlation is handled in the estimator rather
  > than by discarding rows. A professional does not treat five ladder rows on
  > one player-game as five independent observations."

- `clustering_required_on`: `["player_game", "date"]`, enforced by
  `guards.assert_clustering_declared`, replay test
  `test_clustering_must_be_declared`.
- `breadth` (lines 277-290): `min_distinct_dates` 10, `min_distinct_player_games`
  50, `unmeasured_is_refusal: true`, refusal codes `BREADTH_DATES_BELOW_FLOOR`,
  `BREADTH_DATES_UNMEASURED`, `BREADTH_PLAYER_GAMES_BELOW_FLOOR`,
  `BREADTH_PLAYER_GAMES_UNMEASURED`.

`VERIFIED` — all read from the file at the line numbers given.

### 5.2 The distinction, stated so it cannot be blurred

**The floor is defined in raw graded rows. It is not defined in effective
independent units.** The ruling does not merely fail to mention design effects;
it **positively assigns correlation to the estimator and away from the floor**,
and it names the exact case — five ladder rows on one player-game — that §4.2
measures.

Therefore:

> **Applying a design effect to the 300-row floor is a REINTERPRETATION of an
> owner ruling, not a measurement.** Anyone who reports "the gate is not reached
> until week 8 because 760 rows are only 131 effective units" has changed the
> rule, not applied it.

Both readings are presented in §4.3 and §4.4 and neither is presented as the
rule. Nothing in this document changes `board_config.json`.

### 5.3 What the measurement does say about the ruling

Two observations, offered as information rather than as an argument for change:

1. **The ruling looks well-founded for NFL single-line markets.** §2.3 measures
   DEFF between 0.83 and 1.12 at one row per player-game per market. There,
   rows and effective units are the same quantity to within the bootstrap
   width, and counting rows costs nothing.
2. **The gap opens exactly where the ruling says it opens.** On a laddered
   market the row count runs 3–6× ahead of the effective count (§4.2). The
   ruling's own answer to that is `clustering_required_on: ["player_game",
   "date"]` — the correlation is charged in the estimator when the calibration
   statistic is computed. §2.2 gives the NFL numbers that estimator would need:
   ICC 0.44 by player-game on the ladder set, 0.31 on the single-line set.

**What I am flagging, without proposing a change:** the `breadth` block already
does part of the job a design effect would do — `min_distinct_player_games = 50`
is precisely a guard against 300 rows drawn from a handful of player-games. For
NFL it is not binding (it clears in week 1 for every market measured), whereas
`min_distinct_dates = 10` binds in every case. If anyone later wants the floor
to reflect correlation, **raising `min_distinct_player_games` for NFL is a
smaller and more auditable change than reinterpreting the row unit** — but that
is an owner decision under `docs/AGENT_PROTOCOL.md` (it changes what counts as
evidence), and it is not proposed here.

### 5.4 One thing the trigger side needs said now

`trigger_unit` is **graded resolved bets** and `resolved_means` is **terminal
settlement only**. Everything measured in this document is on the population of
*eligible player-games*, which is **not** the population of *placed bets*.

Placed bets are a selected subset — selected on edge, which is selected on model
disagreement with a price, which is correlated within a game far more strongly
than the underlying player-games are. **The design effect on a resolved-bet
ledger is a different and almost certainly larger number, and it is not
estimable from nflverse at all.** No figure in §2 may be carried onto the
trigger. See §6, item 4.

---

## 6. What must be measured before "≥5 seasons" moves from planning guidance to an established figure

The architecture document's recommended registration is
`DEFERRED` with "≥5 seasons" stated. **That registration should stand
unchanged.** Nothing in this document establishes it, and nothing here
disestablishes it either, because every input to it is on the *bet* side, which
nflverse cannot see.

Six things have to be measured or ruled, and they do not all belong to the same
party.

**1. Hard Rock Bet NFL market availability. — Owner's other agent (network).**
Which NFL player-prop markets Hard Rock actually lists; the alternate-line
ladder depth per market (this single number selects between the SINGLE-LINE and
LADDER columns everywhere above, and they differ by 3–6× in rows and 2–8× in
design effect); the time before kickoff at which lines post; and whether market
availability differs by game slot (Thursday / Sunday early / Sunday late /
Sunday night / Monday). Captured weekly with provenance, under `oddsclient.py`'s
discipline — refuse prices arriving without provenance, write the raw response
to disk before parsing (`CLAUDE.md`, "Read COMMANDS.md"). **Every week not
captured is permanently unavailable**, the same argument `_GROUNDING.md` makes
about injury vintages. This is not blocked, it is **assigned**
(`docs/AGENT_PROTOCOL.md` DEC-029).

**2. Eligible-play frequency. — This repository, but not yet.**
How many predictions per week clear `price_floor_singles`, the de-vigged edge
threshold, and `play_count_cap`. **This is not measurable before a calibrated
NFL forecaster exists**, because the play rate is a function of the forecaster's
disagreement with the book. The W8 derivation that produced "≥5 seasons" scaled
*MLB's asserted play rate* to NFL's 272 games — that is the same import defect
as the 7.93 one, one level down, and it should be labelled as such in any
document that repeats it.

**3. Terminal settlement rate. — Owner's other agent (network), then here.**
`resolved_means` excludes Pending. The fraction of NFL prop bets that reach
terminal settlement, and the void/push rate by market, sets the conversion from
placed to graded. NFL props void on inactives at a rate MLB does not have an
analogue for.

**4. The design effect on the resolved-bet population. — This repository, once
a ledger exists.** §5.4. Selected bets cluster far more strongly than eligible
player-games. Until it is measured on a real NFL bet ledger, **no number from §2
may be used in a trigger calculation**, and any document that does so is
repeating the import error this pass exists to correct.

**5. Whether NFL rule changes trigger `season_boundary`. — OWNER RULING, not a
measurement.** `board_config.json` `season_boundary` resets pooled evidence only
on a declared *structural* change, and its examples are all MLB
(ball specification, pitch clock, strike zone, mound). NFL's annual competition-
committee changes (`UNVERIFIED-RECALL` that they are annual — this needs
confirming from a source, and the confirmation is the network agent's) would
have to be classified market by market. **If most seasons carry a qualifying
change, the trigger is unreachable rather than slow**, which is the escalation
W8 already flagged. This is an owner call under the escalation bar: it changes
what counts as evidence.

**6. The gate must pass first.** `two_stage_bar.ordering_is_not_optional`. Per
§4.4 that is weeks 3–4 for three markets and weeks 8–11 for the rest, under the
rule as written. A trigger estimate for a market that has not cleared its gate
is not a forecast of anything.

**Suggested text for `docs/AGENT_OUTBOX.md`** — not written there, because this
pass is instructed not to modify any other file. Whoever integrates this should
copy it:

> **Request to the network-holding agent — NFL market structure, C2.**
> For the 2026 NFL season, weekly from the next unplayed week: (a) the full list
> of Hard Rock Bet NFL player-prop market types offered; (b) for each, the
> number of alternate lines listed per player, and the main line; (c) posting
> time relative to kickoff, by game slot; (d) whether any market is offered for
> only a subset of games. Also, one-off: (e) a citable source for NFL rule
> changes by season 2022–2026, sufficient to classify each against
> `board_config.json` `season_boundary.structural_change_examples`.
> Items (a)–(d) are perishable — a week not captured cannot be recovered.

---

## 7. Label summary

| Claim | Label |
|---|---|
| NFL REG games/season = 272 (2023–2025), 271 (2022); 15.11 games/week | VERIFIED |
| 2024 REG panel: 18,130 player-game rows, 272 games, 58 gamedays | VERIFIED |
| Cumulative distinct gamedays 2024: 4, 7, 10 at end of weeks 1, 2, 3 | VERIFIED |
| `player_stats/player_stats_2025.csv` 404; `stats_player/stats_player_week_2025.csv` 200 | VERIFIED |
| NFL DEFF, single-market single-line, clustered by game = 0.83–1.12 | VERIFIED |
| NFL DEFF, 8 markets pooled single-line, clustered by game = 2.39 (sd 0.28, 4 seasons) | VERIFIED |
| NFL DEFF, 8 markets laddered (9.3 rows/pg), clustered by game = 7.12 (sd 0.64, 4 seasons) | VERIFIED |
| NFL two-way (game, player) DEFF: 2.83–3.18 single-line, 10.37–10.53 laddered | VERIFIED |
| ICC by player-game = 0.31 (single-line) / 0.44 (laddered) | VERIFIED |
| Discrimination DEFF (Fisher-z of r) = 0.89–1.23 single-line, 1.22–1.94 laddered | VERIFIED |
| Continuous raw-level player ICC 0.29–0.35; residual player ICC ≈ 0 | VERIFIED |
| Effective independent prop observations per NFL game ≈ 13.7–19.1 (8-market menu) | DERIVED |
| Design effect is insensitive to the declared shrinkage prior K (moves < 0.05 over K=2..∞) | VERIFIED |
| Ladder rows add 220% row count for 7.6% effective-information gain | DERIVED |
| MLB's 7.93 reproduces as (1.653/0.587)²; NFL's comparable figure is 7.12 at 1/3 the row density | VERIFIED / DERIVED |
| "2,000–3,000 game-equivalents / 7–11 seasons" is a games × row-DEFF unit error | DERIVED — **WITHDRAWN** |
| Corrected NFL requirement: 0.2–1.0 seasons broad markets, 2.3–5.9 seasons QB/RB, at +0.05–0.10 r | DERIVED, planning-level |
| Per-market week-1 row supply 2024: 201/152/152/39/34 | VERIFIED |
| Gate clears end of week 3 (broad markets, both readings); week 4 in 2022–2023 | VERIFIED / DERIVED |
| Gate clears week 8–11 for `rush_yds` and `pass_yds` single-line | VERIFIED / DERIVED |
| The 10-date breadth rule, not the 300-row floor, is what binds the NFL gate | DERIVED |
| Applying a design effect to the 300 floor is a reinterpretation of `gate_floor_unit_ruling` | VERIFIED (rule text) |
| Resolved-bet DEFF is a different, larger, unmeasured quantity | DERIVED |
| ≥5-season trigger: registration stands as DEFERRED planning guidance | unchanged |
| NFL competition-committee rule changes are annual | UNVERIFIED-RECALL — needs the network agent |
| W8's 24.4 skill players/game vs this pass's 21.6 | discrepancy recorded, unresolved, not load-bearing |

---

## 8. Disagreements this pass leaves standing

Recorded rather than averaged away, per `docs/AGENT_PROTOCOL.md`.

1. **Against `NFL_FOUNDATION_AND_MODEL_ARCHITECTURE.md` §2.3.** Its player-prop
   row ("~2,000–3,000 game-equivalents, 7–11 seasons") is withdrawn on the
   arithmetic, not downgraded on the evidence. The owner's correction (F) asked
   for it to be marked planning-level DERIVED pending NFL clustering; NFL
   clustering does not rescue it, because the defect is a unit error rather than
   a parameter error. If the owner prefers the softer disposition, that is his
   call — but the number should not be quoted in the interim, because the
   quantity it denominates in does not exist.
2. **Against `W8_BENCHMARK_DFS.md` §4.2's mechanism, not its conclusion.**
   Week 3 is right for the broadest markets; "because week 1 supplies 369
   player-games" is not the reason, and the same section's implicit
   generalisation to all markets is contradicted by the 8–11 week figures for
   QB and RB markets.
3. **Unresolved and left open.** Whether an NFL market layer should count rows
   or effective units at the floor. §5 presents both and rules neither. It is an
   owner decision because it changes what counts as evidence.
