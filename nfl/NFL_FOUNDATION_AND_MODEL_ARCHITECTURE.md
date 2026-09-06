# NFL Foundation and Model Architecture

**Status:** integration of the eight-worker greenfield research pass, 2026-09-06.
**Branch:** `claude/nfl-greenfield-architecture-stsxmk`.
**Scope:** architecture and evidence. **No NFL predictive production code exists.**
**Inputs:** all eight worker returns, `nfl/research/W1..W8`, each claim labelled VERIFIED / DERIVED /
UNVERIFIED-RECALL, with `nfl/research/_GROUNDING.md` carrying the corrections.

---

## 0. The one-paragraph version

NFL is a greenfield sibling product on the shared scientific platform. The
research pass measured, rather than assumed, what the data supports, and it
returned a single organising result that three workers reached independently
from three position groups: **opportunity is predictable and efficiency is
mostly not.** That result — not a preference for elegance — is what makes the
Skill × Opportunity × Environment decomposition the right architecture, and it
relocates the hard problem from "how good is this player" to "how much football
will he get". A second result bounds ambition honestly: at calibration slope
1.0, a model's SD ratio equals its own discrimination, so dispersion is not a
dial. A third imposes a deadline: the weekly injury cascade is not
reconstructable from history and is being lost weekly, starting now.

---

## 1. The organising result, measured three times independently

| Position | Opportunity metric | reliability | Efficiency metric | reliability |
|---|---|---|---|---|
| WR/TE (W4, n=219) | pass-play participation | **0.948** | catch rate | 0.300 |
| | target share | **0.915** | yards per target | 0.253 |
| | air-yards share | **0.887** | TD per target | 0.167 |
| RB (W3, n=92) | snap share | **0.925** | yards per carry | 0.385 |
| | carry share | **0.926** | EPA per rush | 0.308 |
| QB (W2, n=40–46) | designed rushes/game | **0.911** | completion % | 0.425 |
| | | | interception rate | 0.212, CI spans 0 |

Split-half within season; W3 and W4 used identical random game splits so the
comparison is not confounded by method.

The forward-chained version is blunter still, and it is the number that should
drive the roadmap:

- **W2 (QB):** prior-form prediction of game passing yards reaches **r = 0.136**.
  The *same rate model* handed the **realised** dropback count reaches
  **r = 0.636**. Prior dropbacks/game predicts realised dropbacks at only
  **+0.147**.
- **W3 (RB):** forward-chained opportunity holds at **r = 0.75**, while all three
  efficiency metrics score **negative R² against the pooled mean** — carrying a
  back's own prior efficiency forward is worse than using a constant.
- **W4 (WR):** predicting receiving touchdowns from a player's own prior TD rate
  gives RMSE **1.771** against **1.269** for ignoring the player entirely. Same
  direction for receiving yards (71.73 vs 58.05).

**Read the QB pair carefully, because it is the whole thesis.** The gap between
0.136 and 0.636 is not model quality. It is the volume forecast. Almost all of
the available discrimination sits in a quantity the system does not yet predict.
And 0.136 sits essentially on top of MLB's 0.1101 baseline — i.e. a competent
NFL rate model, absent an opportunity forecast, lands where MLB already is.

**Architectural consequence.** `OpportunityEstimate` is the primary subsystem,
not a modifier applied to a talent projection. Skill models are shrunk hard and
are mostly there to convert opportunity into outcomes. This matches the owner's
framing and is now measured rather than asserted.

---

## 2. What bounds the ambition

### 2.1 The SD ratio is not a dial (W5)

At calibration slope 1.0, the identity `slope = r · SD_actual / SD_predicted`
collapses to **`SD_predicted / SD_actual = r`**, verified numerically to 4 dp.

Therefore a calibrated model's SD ratio **equals its own discrimination**.
Raising dispersion without raising signal moves the slope away from 1.0; it does
not improve the model. MLB's 0.18 was never a ceiling — it was a slope of 0.61,
meaning over-dispersion relative to the signal actually present.

W5's worked example is worth keeping as the canonical Rule 005 illustration:
across a shrinkage grid K = 2→24, **r stays flat at 0.339** while the SD ratio
moves 0.489 → 0.182 and the slope moves 0.688 → 1.866. At K = 24 it lands on
**MLB's exact headline SD ratio of 0.182 with three times MLB's r.** The SD
ratio, read alone, cannot tell those apart.

Estimated calibrated NFL team-total SD ratio: **0.34–0.46**.

### 2.2 The baseline bar is high, and the first frozen baseline must clear it (W5)

A trivial **market-free** baseline — forward-chained shrunken season-to-date
scoring, weeks 8–18 — reaches **r = 0.339 [0.244, 0.425], slope 1.021** on team
points. Roughly three times MLB's baseline.

A frozen NFL baseline that does not beat this is a strawman, and beating MLB's
0.1101 means nothing here. **Game totals are the harder target, not the easier
one**: the book itself manages only r = 0.305 on totals against 0.501 on margin.

W8's independent bracket, from `ffopportunity`: a prior-weeks-mean player
baseline gets **r = 0.5907** pooled (n = 3,576), while an *oracle-opportunity*
expected-points column gets **0.8419** pooled and **0.6853** within-player
demeaned. Those bracket the problem from both ends and agree with §1: **the hard
part is projecting opportunity, not converting it into points.**

> **Do not compare any of these to MLB's r = 0.1101.** Different unit, different
> population, and the pooled figures carry between-player variance. "NFL gets
> 0.59 where MLB got 0.11" is exactly the false-finding shape this repository has
> already paid for.

### 2.3 Statistical power, corrected (W1)

**Two figures have been withdrawn here, and the second withdrawal matters more
than the first.**

Revision 1 of the grounding brief said "~1,131 games with threefold clustering".
That treated a standard-error ratio as a sample-size multiplier. Withdrawn.

Revision 1 of *this document* then replaced it with "~2,000–3,000
game-equivalents / 7–11 seasons". **That is also withdrawn, as a unit error
rather than an over-estimate.** It was `377 × 7.93`: a **game** count for a
**game-level r**, multiplied by a **row-level** design effect measured on a
**calibration** statistic. Three different units in one product.

**This repository had already diagnosed that exact defect and written it down.**
`v8/experiments/J2_STOPPING_RULE.md:47-52` records it for MLB, quoting
`J2-handedness-01.md:84`: *"Do NOT reuse DEFF 10.54 from the prop-row design;
games do not nest inside games."* It also warns that *"correcting defect 1 alone
would have produced a more precise wrong number"* — which is precisely what
revision 1 did. The correction to the *square* was inherited; the correction to
the *unit* was not.

**NFL's design effect, measured directly (C2), is not a constant. It is a
function of rows per player-game:**

| Grading design | rows / player-game | DEFF (clustered by game) |
|---|---|---|
| One row per player-game per market | 1.0 | **0.83–1.12** (CIs include 1.0) |
| Eight markets, one line each | 2.9 | **2.39 ± 0.28** |
| Eight markets, laddered | 9.3 | **7.12 ± 0.64** |

Two-way (game, player) clustering: 2.83–3.18 and 10.37–10.53 respectively.

**MLB's 7.93 and NFL's 7.12 agreeing is a coincidence, not a validation.** MLB
reached 7.93 at **31.4** rows/player-game; NFL reaches 7.12 at **9.3**. Per row,
NFL is *more* coupled. Neither number transfers, and MLB's is not promoted to an
NFL constant.

The transferable NFL quantity is **~14–19 effective independent prop observations
per game**, nearly invariant to how many rows are written: the laddered set has
3.2× the rows of the single-line set and carries 7.6% more information.

**A third layer, previously missed entirely:** the design effect depends on the
*statistic*, not only the clustering. The **discrimination** DEFF (Fisher-z of r)
is 0.89–1.23 single-line and 1.22–1.94 laddered — roughly **3.5× smaller** than
the calibration DEFF on the same rows.

**Corrected NFL figures**, at realistic effect sizes over measured baselines:

| Market family | Seasons to confirm |
|---|---|
| Broad receiving / anytime-TD | **0.2–1.0** |
| QB / RB markets | **2.3–5.9** |

So "7–11 seasons" is roughly right for QB passing and about **10× too
pessimistic** for receiving. Sample size remains a real constraint, but it is not
uniformly a multi-season one, and treating it as such would have wrongly
suppressed the markets with the most supply.

These are **planning-level** figures and are marked DERIVED: they rest on
measured NFL clustering but on assumed effect sizes. Reported design effects are
**upper bounds** — an oracle game-total control cuts the laddered DEFF from 6.76
to 4.95 and the single-line from 1.05 to 1.00.

---

## 3. Architecture

### 3.1 Platform / sport separation

```
platform/            sport-neutral, shared with MLB
  outcome            five states (sportsplatform/governance/outcome.py)      REUSE AS-IS
  provenance         five clocks (sportsplatform/governance/provenance.py)   REUSE AS-IS
  scorecard          linked r / SD ratio / slope                 REUSE AS-IS
  identity           fingerprints, input manifests               EXTEND
  registry           experiments, features, promotion gates      EXTEND
  evaluation         CRPS, PIT, coverage, clustered SEs          EXTEND
models/nfl/          this document
models/mlb/          existing v7 + v8
```

The platform pieces are **not rewritten for NFL**. `outcome.py`,
`provenance.py` and `scorecard.py` already encode the rules NFL needs, and the
capture harness (`nfl/tools/capture_vintage.py`) already imports them. Building
NFL is the forcing function that reveals which pieces are genuinely
sport-neutral — that is a stated benefit of doing this now, and it is being
realised rather than promised.

### 3.2 The NFL forecasting stack

```
Information vintages (NFL-0)
  └─ Availability model          P(active), P(role | active) as a DISTRIBUTION
      └─ Game environment        drives, plays, pace, neutral pass rate
          └─ Opportunity allocation   snap/carry/target/participation shares
              └─ Skill conversion     efficiency, heavily shrunk
                  └─ Drive / play simulation
                      └─ Joint draws  ← everything downstream reads only this
                          ├─ NFL Market   (de-vig, edge, gated separately)
                          └─ NFL DFS      (salary, ownership, contests)
```

Two boundaries are load-bearing and must be enforced structurally, not by
convention:

1. **Market never enters forecasting.** See §4.3.
2. **DFS never enters forecasting.** The forecaster must not know a salary or an
   ownership projection while estimating football ability. W8 specifies the check
   and notes the strongest precedent already exists in this repo:
   `v7/test_price_capture.py`'s AST/import defence, whose own docstring says the
   structural check is the real one.

### 3.3 Why the simulator must be joint, and cannot be marginal (W5, W8)

This is settled by measurement, not taste:

- **Total plays barely move with game script (r = +0.100) while pass share swings
  (−0.545).** Pass and rush attempts are anti-correlated *through the scoreboard*.
- Q4 pass rate spans 0.284–0.878 by score state against a between-team SD of
  0.042 — about **3×**. Q4 pace spans 20.95–35.51 s against a between-team SD of
  0.99 s — about **15×**.
- Drives are a **game-level** quantity (between-team-within-game SD 0.429 against
  game SD 3.198, correlation +0.851); plays are **zero-sum** between the two
  teams (−0.513).
- `passer_player_id`, `receiver_player_id` and `td_player_id` sit on the **same
  play row**, so one draw credits two players by construction.

Independent marginal draws would reproduce every marginal correctly and get the
joint wrong. Since correlation is the entire product for stacking and for any
multi-player question, marginals are not a cheaper version of the right answer —
they are the wrong object.

**Storage is not an excuse.** W8's sizing, DERIVED from verified counts (272
games, 24.4 skill players/game, 540 integers per sim-game): **2.94 GB/season at
10,000 sims, 5.88 GB at 20,000** — about one fifth of the MLB equivalent. Store
full joint draws from day one. MLB's nine stored percentiles are precisely why it
cannot compute exact CRPS, log score, or tail calibration, and why
`graded_prediction_means` is unmet for its development set.

One trap W8 flags that MLB's experience does not cover: cross-game `sim_index`
alignment is only valid while games are independent, so `cross_game_dependence`
must be a **required declared header field** on the draw archive.

### 3.4 Availability, as a distribution (W7)

The measured designation → participation mapping, cluster-bootstrapped by
team-week, with 2025 as out-of-sample replication:

| Designation | n | P(play) 2024 | 95% CI | P(play) 2025 |
|---|---|---|---|---|
| Out | 1,116 | 0.0009 | [0.0000, 0.0028] | 0.0000 |
| Doubtful | 194 | 0.0000 | [0.0000, 0.0000] | 0.0000 |
| Questionable | 1,513 | **0.6550** | [0.6297, 0.6786] | 0.6518 |
| **On the practice report, no game designation** | 3,386 | 0.9430 | [0.9336, 0.9520] | 0.9385 |

The conventional reading of Doubtful ≈ 25% and Questionable ≈ 50% is **wrong by
25 and 15 points**. Both 2025 figures land within a third of a point of 2024.

**Role given active is the larger half.** Questionable players who play sit at
0.90× their own healthy baseline at the median, but P(< 0.50× baseline) = **0.178
against 0.077** for healthy. RBs are worst; QBs are effectively binary. A point
estimate destroys this — hence `P(role | active)` must be a distribution.

Two fields beat practice status outright: the **`Not injury related - resting
player`** tag inverts DNP entirely (P(play) 0.876 vs 0.118, a +0.485 risk
difference *inside one cell*), and **body part** spreads Questionable from
hamstring 0.554 to foot 0.881.

Practice status itself gets a split verdict, and both halves are recorded: it
separates the tails (DNP-vs-Full risk difference +0.183 [+0.106, +0.259]) while
adding little on average and saying nothing about the 56% in `Limited`. On snap
share given active it is **DEFERRED / UNDERPOWERED at n = 222** — explicitly not
a null result.

### 3.4a Correction — what population 0.9430 was measured on (C1)

**Revision 1 of this document attached 0.9430 to the wrong population, and the
error would have propagated into production as an availability prior.** Recorded
here rather than edited away.

`n = 3,386` is exactly the count of rows in `injuries_2024.csv` whose
`report_status` is blank — no join, no roster filter. Reproduced independently:
6,215 total rows, **3,386 blank**, and 3,203 of those are REG. Of the REG rows,
**3,203 / 3,203 carry a `practice_status`** and 3,202 carry a practice injury.

So the cell is **"named on the practice report with an ailment, then cleared of a
game designation"** — a player the team looked at and passed. It is emphatically
**not** "a player absent from the injury report", which is what the state code
`PLAYER_NOT_ON_REPORT` names. The two are opposite populations, and the second is
much larger and much more heterogeneous.

**What the correct populations actually give:**

| Population | P(≥1 snap) | n |
|---|---|---|
| On practice report, no game designation (the 0.9430 cell) | **0.9430** | 3,386 |
| Roster player, never on that week's report, **gameday-eligible** | **0.8876** | 24,101 |
| Roster player, never on that week's report, **roster membership only** | **0.5553** | 38,524 |
| Practice squad | **0.0000** | — |

Bias from applying a flat 0.943 to each: **+0.055 / +0.388 / +0.943**. Replicates
on 2025 within 0.005 on every cell.

**The obvious fix is also wrong.** 0.8876 is *itself* a mixture marginal;
substituting it for 0.9430 corrects the label while preserving the defect. Most
of the apparent "being on the report is good news" effect is **role composition**:
the injury report is 67.6% depth-1 starters against 43.7% off-report, and direct
standardisation on depth rank closes **60%** of the 0.0745 gap (0.8876 → 0.9326).

**Dressed is not the same as playing a role**, and the gap is enormous. Within
the same off-report cell, across prior-week snap-share buckets, P(≥1 snap) moves
0.8505 → 0.9905 — but **P(offense_pct ≥ 50%) moves 0.0098 → 0.9325, a factor of
95.** A skill-position player with zero snaps last week and no designation is
**0.4685** to take a single snap, not 0.943. QBs off-report: P(dressed) 0.9095,
P(snap) 0.4783.

**Therefore production must condition on four separated things**, never on
injury-report absence alone:

1. roster membership,
2. gameday participation universe (measured: active limit **48**, sd 0.34; **46.7**
   distinct players take a snap per team-game; eligible pool **54.34**),
3. injury-report presence/absence,
4. football role — prior snap share or depth rank.

And a further leakage finding falls out of it: **`weekly_rosters.status` is a
post-hoc gameday outcome, not a roster state** — `ACT` → 0.9715 snap rate,
`INA` → **0 of 3,438**, `DEV` → 3 of 8,306. It must be quarantined at ingest
alongside the market columns. That leaves **prediction-time eligibility currently
unsatisfiable from reachable data**, which is an assignment (outbox), not a
blocker, and must not be stubbed.

Also measured: **59% of gameday inactives never appear on the injury report at
all**, which is the clearest single statement of why report-absence cannot carry
an availability prior on its own.

### 3.5 Redistribution — the mechanism that is most often modelled wrong

Two workers measured it independently and agree, against the intuitive answer:

- **W3 (39 events, 21 focal players, 16 teams):** "next-man-up takes all" is the
  **worst** of five rules (MAE 0.2554); a flat split is the best (0.2011). The
  top remaining back absorbs a mean of only **+0.102** of vacated share, while
  ranks 3+ absorb **+0.627**.
- **W7:** losing ≥0.50 baseline share moves surviving teammates by +0.221 (RB),
  +0.122 (WR), +0.200 (TE) — all CIs clear of zero — but **only ~47% of removed
  share returns to the position group.** A model that renormalises within the
  group **over-projects the backup by roughly 2×.**

The owner's "8 → 19" case is real but uncommon: of sub-8-opportunity backs,
10.2% reach ≥15 and 3.4% reach ≥19.

**Consequence:** redistribution happens **inside the opportunity allocation
draw**, never as a post-hoc adjustment, and never by renormalising within
position.

### 3.6 Defence and matchup — scheme is real, outcomes mostly are not (W6)

17-game reliability across the 32 defences, with bootstrap CIs:

| Defensive quantity | reliability | reading |
|---|---|---|
| Cover-3 rate | **0.878** | scheme is a stable team trait, 12–19x the binomial noise floor |
| Man rate | **0.875** | |
| Blitz rate | **0.810** | |
| Pressure rate generated | 0.693 | the usable outcome measure |
| Takeaways | 0.499 | regress hard, but not noise — see below |
| All-EPA allowed | 0.422 | CI touches zero |
| **Pass EPA allowed** | **0.094** | [0.000, 0.341] — near-useless as a team trait |
| **Sack rate** | **0.000** | structurally dead, see below |

**Sack rate is a worse estimator of the same thing.** Sack rate given no pressure
is 0.0001 (1 in 13,975) — a sack *is* a pressure. Team conversion of pressure
into sacks has a variance ratio of **0.75**, *below* the chance floor. So sack
rate measures what `was_pressure` measures, about 4x less precisely. Use pressure.

**Turnovers: the conventional prior is half right.** Aggressive regression is
confirmed — shrink 50% even after 17 games, 81% at week 4 — but it is *not* pure
noise: variance ratio 1.94 with CI [1.21, 2.68] excluding 1. The components
differ sharply: fumble-recovery share (ratio 0.98) and forced fumbles (1.03) are
**exactly chance**, and team INT/game has ~zero adjacent-season carryover
(+0.026, −0.073). The composite is more reliable than either component because
INT and fumble-lost rates covary across teams (r = +0.303).

**Individual matchup is closed off, and that is a useful closure.** No
coverage-defender column exists in `pbp`'s 372; participation gives an unordered
11-player list with no assignment; PFR defender rows carry targets but no
receiver identity. Empirically, opposing defence explains **0.66%** of
receiver-game yardage residual variance (placebo p = 0.113) and **0.216%** of
receiving EPA (p = 0.327, identical to placebo). Recorded **REJECTED — SOURCE
INSUFFICIENT**, which forecloses a popular and unsupportable feature class.

**The opponent-adjustment trap, quantified.** Through about week 5, the spread in
*schedules faced* (0.0475 EPA/play at 4 games) **exceeds the entire true
defensive spread** (0.0428). Adjusting for opponent early in a season therefore
injects more noise than it removes, and the circularity is not hypothetical.

**One methodological result worth carrying beyond the defence layer.**
`defense_man_zone_type` and `defense_coverage_type` are 51.2% blank across the
whole participation file but **0.23% blank on the dropback denominator** — the
blanks are run plays, where a coverage shell is not defined. Discarding the
column on the file-wide figure would have been Class A in mirror image: a
correctly-scoped NULL read as data loss. **Missingness must always be reported
against the denominator the field is defined on**, and §4.2's empty-column rule
must not be applied so bluntly that it deletes correctly-scoped nulls.

Also flagged: `advstats` `def_yards_allowed` is **39.7% missing** while sibling
columns are 0% — summing it under-counts by ~40% and looks entirely plausible.

---

---

## 4. What the data actually supports

### 4.1 Reachable from this environment (VERIFIED)

`nfl/NFL_DATA_AVAILABILITY.json`, produced by `nfl/tools/probe_nfl_sources.py`:
**30 targets, 25 PASS, 1 BLOCKED, 4 FAIL**, with negative controls proving the
egress boundary rather than asserting it. `raw.githubusercontent.com` and GitHub
release downloads answer 200; pro-football-reference, ESPN and Sleeper do not.

The whole nflverse stack is therefore readable here: play-by-play (372 cols),
participation, FTN charting (2022+), snap counts, injuries, depth charts,
rosters, NGS, PFR advanced stats, officials, schedules — 2024 and 2025 complete.

Identity is healthy but not free: `players.csv` is a clean injective
`pfr_id → gsis_id` crosswalk (22,653 entries, 0 dupes); participation→pbp and
ftn→pbp both join at **1.0000**; snap_counts joins at **99.8422%**. W1 measured
what a name-based fallback would do to the 42 unmapped rows: **2 recover, 2
silently mis-join, 2 fail** — which is the quantified argument for a named
`PFR_ID_UNMAPPED` FAIL over an inner join that drops rows quietly.

### 4.2 Fields that are NOT what they appear (all VERIFIED, all corrections)

| Field | Reality | Disposition |
|---|---|---|
| `participation.route` | **one scalar per play**, 14 route names, 0 rows contain `;` — the *targeted* receiver's route | per-player routes-run **not derivable**; "TPRR" as specified is unavailable |
| `participation.ngs_air_yards` | **0 non-null of 45,919** | REJECTED — SOURCE EMPTY |
| `pbp.pass_attempt` | **includes sacks** (1,314 of 19,153) | using it as completion denominator gives 0.6072 vs 0.6555 — an error larger than the whole between-QB spread (0.0343) |
| `pbp.passer_player_id` | **null on 100% of scrambles** (5.25% of dropbacks) | must group on a cleaned passer id |
| `ftn.n_blitzers` | counts **extra** rushers, not total | a naive `>= 5` filter returned 1 blitz in a season |
| `n_pass_rushers==0`, `defenders_in_box==0`, `read_thrown=='0'` | **not-applicable sentinels** | never read as measured zeros |
| `advstats.receiving_broken_tackles` | **100% null** | REJECTED — SOURCE EMPTY |
| `offense_positions` | depth-chart position, **alphabetically sorted on 45,919/45,919 rows** | list order carries no field information; **slot/wide alignment is not recoverable** |
| `injuries.date_modified` | **removed in 2025**, `season_type` added, **column count unchanged at 16** | a column-count check passes through the loss |

The generalising rule, and it is the Class A defect this project keeps paying
for: **a column existing is not a column carrying values.** Ingest must assert
per-column non-null fractions and refuse an empty field, rather than reading the
header as availability.

### 4.3 Leakage inventory (W1, W5)

**14 market-derived columns** — 6 in `pbp`, 8 in `schedules` — including
`spread_line`, `total_line`, both moneylines, both spread prices, both totals
prices, and the easily-missed derived pair `vegas_wp` / `vegas_wpa`. The
schedules market columns are **already populated for 112 of the 272 unplayed 2026
games**, and `pbp` re-stamps them onto all 49,492 rows, so quarantining
`schedules` alone is insufficient.

Also flagged:
- `result` / `total` are outcome leakage replicated onto every play row.
- `schedules.away_qb_id` / `home_qb_id` are **post-hoc** — 285/285 populated for
  2024, **0/272 for 2026**. W1 calls this the most seductive leak in the file,
  and the 2026 zeros are the tell.
- `weekly_rosters.status` is **a post-hoc gameday outcome, not a roster state**,
  and has **no timestamp column** — so a kickoff-minus-90-minutes fact looks like
  a weekly one. Measured (C1): `ACT` → 0.9715 snap rate, `INA` → **0 of 3,438**,
  `DEV` → 3 of 8,306. A near-perfect predictor of playing, available only after
  the fact. Quarantine at ingest alongside the market columns. Consequence:
  **prediction-time eligibility is currently unsatisfiable from reachable data**
  — an assignment, not a blocker, and it must not be stubbed.
- `xpass` / `pass_oe` and 31 other model-derived pbp columns have an unconfirmed
  fit window and are **treated as contaminated until checked**.
- Observed `temp` / `wind` are conditions, not forecasts: using them in a backtest
  is a Rule 003 leak. Production needs forecast vintages.

Quarantine must be **at ingest, with a named error and a replay test on the real
call site** — not a convention of not selecting the columns.

### 4.4 Rejected on measurement — recorded so they are not re-proposed

| Candidate | Result | Source |
|---|---|---|
| Plays per game as a team trait | split-half 0.220, **shrunk ICC 0.000**; out of sample worse than league mean | W5 |
| Drives per team-game as a team trait | split-half **0.001**; pace predicts next-half play count at **r = −0.099**, wrong sign | W5 |
| "The goal-line back" | own goal-line share adds **+0.5%** over overall carry share; goal-to-go adds **0.0%** | W3 |
| Free-standing red-zone target rate | partial r = 0.126; overall target share predicts next-half red-zone share (0.732) **better than red-zone share predicts itself** (0.617) | W4 |
| Charged drop rate | r = 0.020 (WR), 0.008 (QB) — noise | W4, W2 |
| Interception rate as QB skill | within-season 0.212 [−0.168, +0.530]; YoY −0.130 / +0.049 / +0.232, every interval covers zero | W2 |
| Blitz-faced rate as QB trait | r = 0.020 | W2 |
| Defensive sack rate as a team trait | reliability **0.000**; a sack is a pressure, and pressure->sack conversion has variance ratio 0.75, below chance | W6 |
| Pass EPA allowed as a defensive team trait | reliability 0.094 [0.000, 0.341] | W6 |
| Fumble-recovery share / forced fumbles | variance ratios 0.98 and 1.03 — exactly chance | W6 |
| Individual receiver-vs-defender matchup | not identifiable in any reachable feed; opposing defence explains 0.66% of receiver yardage residual, placebo p = 0.113 | W6 |

Two of these are methodology findings in their own right. W2's odd-even split
gave INT rate 0.523 — a **lucky-partition artefact** that a median over 1,000
random partitions dissolves. And the **third-down** back role *does* survive
(+13.3%), so "situational role" is not uniformly noise; the goal-line version
specifically is.

### 4.5 The MLB shrinkage method does not transfer uniformly (W2)

DerSimonian–Laird as at `v7/rates.py:220` agrees with split-half for **outcome**
rates (within-QB overdispersion φ = 0.90–1.14) but **breaks for scheme and
opponent rates** (φ = 1.65–3.02): DL returns k = 200 for blitz-faced where
replication gives r = 0.020 and k ≈ 10,221 — a fiftyfold error.

**NFL shrinkage constants must be estimated by game-level split-half over many
random partitions, or with a measured φ correction.** Importing MLB's estimator
wholesale would silently under-shrink exactly the noisiest feature class.

W4 adds the same warning within a single position: TD-rate k is **137 targets
for WR+TE pooled but 1,422 for WR alone against 51.6 for TE** — a 28× difference
that one pooled constant would get badly wrong.

---

## 5. The evidence system (NFL-0), and why it has a deadline

### 5.1 What is already lost, and what is still recoverable

| Stream | Status | Recoverable later? |
|---|---|---|
| Play-by-play, participation, FTN, snaps | complete 2016/2022–2025 | yes, static archives |
| **Depth charts / role** | daily `dt` series since 2025, **already running for 2026** (170 values to 2026-09-06T11:29:30Z) | **yes** — role vintages are not on the losing clock |
| **Injury reports** | one row per player-week; **2025+ carries no clock at all**; `injuries_2026.csv` is **404 today** | **NO** |

The only surviving evidence of the weekly cascade in all of 2024 is **two
accidental duplicate rows** — both Questionable→Out downgrades hours apart.

Loss per uncaptured week (W7): **~132 bits of availability entropy** (75.6 in
Questionable, 38.5 on skill positions) plus **~331 practice trajectories**.

### 5.2 The capture harness exists and is running

`nfl/tools/capture_vintage.py` — built under this pass because the deadline is
real. It is **data capture, not prediction**: it fetches bytes, records what
arrived, and refuses to interpret.

- Inherits `Outcome` and the five clocks from `sportsplatform/governance`, rather than
  coining a parallel vocabulary. HTTP `Last-Modified` supplies the
  `source_timestamp` that the 2025+ injury schema no longer carries.
- Raw bytes written **before** parsing, with status and headers.
- **Append-only**: update is physically unavailable, so "never overwrite Tuesday
  with Sunday" holds by construction. An unchanged file at a later hour is a
  *measurement* — new manifest row, no new blob (content-addressed).
- First real capture, 2026-09-06: `injuries` → **DEFERRED /
  SOURCE_NOT_YET_PUBLISHED**, carried as an owed debt. That is the expected
  pre-season state, and it is exactly the condition whose absence (Class B1)
  aborted V7's first live batch. A 200 with zero bytes, or a header with no rows,
  is FAIL — never success.

Cadence must be **kickoff-anchored, not nominal-Sunday**: 2026 week 1 has games
on Wed 09-09, Thu 09-10, Sun 09-13 and Mon 09-14, so a Thursday game's
"Friday-equivalent" report is Tuesday.

### 5.3 The state distinction that will be got wrong

Two conditions look identical — "no row for this player" — and mean opposite
things:

| Condition | State | Code |
|---|---|---|
| Report not yet published for this game-week | **`DEFERRED`** | `REPORT_NOT_YET_PUBLISHED` — stays **owed** |
| Player absent from a report that *did* publish | **`NOT_APPLICABLE`** | `PLAYER_NOT_ON_REPORT` |

The second is a positive observation and the largest cell in §3.4's table.
Storing it as a missing row destroys it.

**It is NOT worth P(play) = 0.9430, and revision 1 of this document said it was.**
See the correction in §3.4a: 0.9430 was measured on players *on* the report, and
the state code names players *absent* from it — the opposite population.

### 5.4 Reproducibility, against the MLB failure

MLB's M0 is not reproducible because the consumed corpus was never hashed or
committed, and `SIM_FORMULA` excluded it so the fingerprint could not catch the
substitution. The NFL equivalent hazard is live: W1 observed that
`schedules/games.csv` and `players/players.csv` were **both rewritten upstream on
2026-09-06** — the same trap, one HTTP request away.

**Therefore:** content-addressed input manifests, with the sha256 of every
consumed partition inside the execution identity, not beside it. The capture
manifest already records sha256 per fetch; the model fingerprint must consume it.

---

## 6. Evaluation

Forward-chained by week, never random row splits — NFL weeks share information
(opponent, weather, injury state) and a random split leaks across them.

Scored together, never individually (Rule 005): r, SD ratio and calibration slope
are algebraically one fact. Plus CRPS, log score, PIT, interval coverage, tail
calibration — all of which require the **stored joint draws** of §3.3.

Clustered by **date and by team**, predeclared. MLB measured a design effect of
**7.93** on player-prop analyses; NFL player-games within a team-game are more
strongly coupled, not less, because §3.3 shows one play row credits two players.

**Skill error vs opportunity error must be decomposed separately.** This is the
owner's requirement and §1 shows why it is the highest-value diagnostic
available: a receiver missed because we mis-estimated his talent and one missed
because we mis-estimated his route participation require completely different
fixes, and the measured evidence says the second dominates.

**Exploratory vs confirmatory.** Everything in this document is **exploratory**.
It was measured on 2024–2025 data that has now been inspected, and inspection is
what disqualified MLB's 251-game set. The 2026 season — **272 games, 18 weeks,
zero results recorded as of 2026-09-06** — is a genuinely untouched prospective
window, and it is the asset MLB never had. Preserving it requires sealing
predictions before kickoff, from week 1.

---

## 7. Market and DFS

Both consume the joint draw archive and neither influences it.

**Market.** Hard Rock Bet only. No parlays, ever, including in discussion.
De-vig before comparing anything. The two-stage bar applies unchanged:
calibration is the **gate**, margin is the **trigger**, 300 graded units rising
to 500 below 0.2 implied probability.

W8's DERIVED timing, and it is blunt:

- The **gate**: the conclusion survives for some markets and the reasoning does
  not. **369 was never per-market supply, and the gate is per market.** Measured
  week-1 supply: **152** (`rec_yds`), **39** (`rush_yds`), **34** (`pass_yds`).
  The binding constraint was never rows at all — it is
  `min_distinct_dates = 10`, and cumulative gamedays run 4 / 7 / 10, making
  **week 3 a calendar floor** (week 4 in 2022–2023). "Fast" holds for **3 of 8**
  markets; `rush_yds` and `pass_yds` are **8–11 weeks**. And it does not start at
  all unless the joint archive ships on day one, because
  `graded_prediction_means` forbids percentiles.

  **The 300 floor is not re-scaled by a design effect, and must not be.**
  `board_config.json` sets `gate_floor_unit: "rows"` with an explicit 2026-08-30
  ruling: *"count ROWS ... correlation is handled in the estimator rather than by
  discarding rows."* Applying a DEFF to the floor would be a **reinterpretation
  contrary to a ruling already made**, not a measurement. Both readings are
  tabulated in `C2_POWER_AND_CLUSTERING.md`; neither is presented as the rule,
  and `board_config.json` was not changed.
- The **trigger** is not. Scaling MLB's asserted play rate to NFL's 272 games
  gives ~11 plays per market per season → on the order of **decades**, and even a
  generous 5× rate leaves ~5.5 seasons. If NFL changes a structural rule most
  offseasons (UNVERIFIED-RECALL, needs confirmation), `season_boundary` may reset
  evidence faster than it accumulates, making the trigger **unreachable rather
  than slow**.

Recommended registration: **`DEFERRED` with "≥5 seasons" stated**, escalating to
`BLOCKED` only on confirmation. Recording it now prevents it being discovered as
a disappointment later.

**DFS.** Consumes distributions and prices them; never informs them. The
forecaster must not see salary or ownership. W8 specifies a structural check
modelled on `v7/test_price_capture.py`'s AST/import defence, plus a
`written_at_utc < captured_at_utc` ordering check that makes blindness
**provable rather than asserted**.

---

## 8. Disagreements left standing

Recorded rather than averaged away, per `docs/AGENT_PROTOCOL.md` Rule 2.

1. **Efficiency shrinkage (W3 internal).** Forward-chained, a back's own prior
   efficiency is worse than a constant (§1). Yet full shrinkage to the league
   mean is *not* supported: optimal own-YPC weight 0.93, costing +1.135 RMSE
   yards with a CI excluding zero under player-, game- and week-clustering. Both
   measurements stand; the resolution is an experiment, not an argument.
2. **Opponent adjustment (W5 internal).** An opponent term marginally helped team
   points but *reduced* points-per-drive r from 0.338 to 0.321 while improving
   slope to 0.978. Both are within noise at n = 330. W5 caught and corrected its
   own defect here mid-pass — an earlier draft reported the term as included when
   the script had not included it.
3. **Sack rate's level (W2 vs W6).** W2 measured QB sack rate — sacks *taken* —
   as middling within-season (0.399) but the **best year-over-year figure in the
   pass** (+0.725 / +0.571 / +0.423), because it is substantially a *team*
   property. W6 measured defensive sack rate — sacks *generated* — at reliability
   **0.000**, and showed a sack is definitionally a pressure.
   These are different quantities and are not a direct contradiction, but they
   must not be conflated under one feature name, and the offence-side result
   should be re-checked against a pressure-based denominator before anything is
   built on it. Whether the offence-side term belongs in the QB layer or the
   environment layer is also unresolved.

---

## 9. Feature register — opening state

Per `v8/FEATURE_REGISTRY.md`, **nothing is CORE**, because no NFL experiment has
run. Everything measured above is EXPERIMENTAL; everything in §4.4 is REJECTED;
everything market-derived is quarantined. A status above EXPERIMENTAL requires
citing the experiment that earned it, and the experiments do not exist yet.

## 10. Version naming

This is the **NFL Greenfield Track**. Not V9, not NFL V1. The first frozen
baseline takes a name chosen when it is frozen and does **not** inherit "M0" —
that name belongs to a specific, preserved, non-reproducible MLB artifact, and
reusing it would collapse exactly the distinction `CLAUDE.md` protects.
