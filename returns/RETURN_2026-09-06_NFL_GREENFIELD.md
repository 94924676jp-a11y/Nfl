# Return: NFL Greenfield Architecture pass

**Date:** 2026-09-06
**Branch:** `claude/nfl-greenfield-architecture-stsxmk` (8 commits, pushed)
**Scope delivered:** architecture and evidence. **No NFL predictive production code.**
**Read next:** `nfl/NFL_FOUNDATION_AND_MODEL_ARCHITECTURE.md`, then
`nfl/NFL_EXPERIMENTAL_ROADMAP.md`, then `docs/AGENT_OUTBOX.md` §33.

---

## 1. What was asked, and what came back

The instruction was to run an NFL greenfield architecture directive with about
eight specialised workers, research only, returning the foundation and the
experimental roadmap before any NFL predictive code is written. That is what
happened.

| Deliverable | Path |
|---|---|
| The directive itself | `nfl/NFL_GREENFIELD_DIRECTIVE.md` |
| Eight worker returns (~380 KB measured research) | `nfl/research/W1..W8_*.md` |
| Shared grounding brief, with its corrections | `nfl/research/_GROUNDING.md` |
| **Integrated architecture** | `nfl/NFL_FOUNDATION_AND_MODEL_ARCHITECTURE.md` |
| **Experimental roadmap, NFL-0 → NFL-5 with exit gates** | `nfl/NFL_EXPERIMENTAL_ROADMAP.md` |
| Reproducible source audit + tool | `nfl/NFL_DATA_AVAILABILITY.json`, `nfl/tools/probe_nfl_sources.py` |
| Vintage capture harness (running) | `nfl/tools/capture_vintage.py`, `nfl/vintage_manifest.jsonl` |
| Assignments for the networked agent | `docs/AGENT_OUTBOX.md` §33 |

Every worker claim carries one of `VERIFIED` / `DERIVED` / `UNVERIFIED-RECALL`.
Nothing was stubbed, mocked, or routed around a constraint.

---

## 2. The finding that reframed the pass before it started

`CLAUDE.md` states this agent has no egress. **That is too strong**, and I probed
rather than assumed it.

`raw.githubusercontent.com` and GitHub **release downloads** answer 200.
pro-football-reference, the ESPN API, the Sleeper API and the GitHub API for
other owners do not. Recorded with deliberate negative controls so the boundary
is demonstrated rather than asserted: **30 targets, 25 PASS, 1 BLOCKED, 4 FAIL**.

Consequence: the entire nflverse stack is readable from inside the sandbox —
play-by-play (372 columns), participation, FTN charting, snap counts, injuries,
depth charts, rosters, NGS, PFR advanced stats, officials, schedules, 2024 and
2025 complete. So NFL-0 was **assigned work, not blocked work**, and the workers
measured against real bytes instead of recalling field names.

---

## 3. The organising result

**Opportunity is predictable. Efficiency mostly is not.** Three workers reached
this independently, from three position groups, using identical random game
splits where comparable.

| Position | Opportunity | reliability | Efficiency | reliability |
|---|---|---|---|---|
| WR/TE (n=219) | pass-play participation | **0.948** | catch rate | 0.300 |
| | target share | **0.915** | yards per target | 0.253 |
| | air-yards share | **0.887** | TD per target | 0.167 |
| RB (n=92) | carry share | **0.926** | yards per carry | 0.385 |
| | snap share | **0.925** | EPA per rush | 0.308 |
| QB (n=40–46) | designed rushes/game | **0.911** | completion % | 0.425 |
| | | | interception rate | 0.212 (CI spans 0) |

Forward-chained, it is blunter:

- **QB:** prior-form prediction of game passing yards reaches **r = 0.136**. The
  *same rate model* handed the **realised** dropback count reaches **r = 0.636**.
  Prior dropbacks/game predicts realised dropbacks at only **+0.147**.
- **RB:** opportunity holds at **r = 0.75**; all three efficiency metrics score
  **negative R² against the pooled mean** — a back's own prior efficiency is
  worse than a constant.
- **WR:** predicting receiving TDs from a player's own prior TD rate gives RMSE
  **1.771** against **1.269** for ignoring the player entirely.

**The QB pair is the thesis.** The gap between 0.136 and 0.636 is not model
quality — it is the volume forecast. Nearly all available discrimination sits in
a quantity the system does not yet predict, and **0.136 lands essentially on top
of MLB's 0.1101 baseline**. A competent NFL rate model without an opportunity
forecast arrives exactly where MLB already is.

Architecturally: `OpportunityEstimate` is the primary subsystem, not a modifier
on a talent projection. Skill models are shrunk hard and exist mostly to convert
opportunity into outcomes.

---

## 4. Five parts of the proposed design that do not survive the data

Stated plainly rather than quietly dropped.

| Proposed | Measured reality |
|---|---|
| **Targets per route run**, route participation | `participation.route` is **one scalar per play** — 14 route names, 0 rows contain `;` — and it is the *targeted* receiver's route. Per-player routes-run is not derivable from any reachable feed. Found independently by two workers. |
| **Slot / wide alignment** | `offense_positions` is alphabetically sorted on **45,919/45,919** rows. List order carries no field information. Not recoverable. |
| **Receiver vs specific corner matchup** | No assignment data in any feed. Opposing defence explains **0.66%** of receiver-game yardage residual variance (placebo p = 0.113). **REJECTED — SOURCE INSUFFICIENT.** |
| **The goal-line back** | Own goal-line share adds **+0.5%** out of sample over overall carry share; goal-to-go adds **0.0%**. The **third-down** role is the real one (+13.3%). |
| **Backup absorbs the vacated role** | "Next-man-up takes all" is the **worst** of five rules; flat split is best. Only **~47%** of removed share returns to the position group — renormalising within position **over-projects the backup ~2×**. The 8→19 jump is real but uncommon: 3.4% of sub-8-opportunity backs reach 19. |

What replaces the first row is better founded: pass-play participation from
`offense_players` on dropbacks, which reconciles **exactly** against official
weekly stats — 11,629 = 11,629 receptions across 4,263/4,263 player-weeks.

"Heavily regress turnover generation" was **half right**: aggressive regression
confirmed (shrink 50% even after 17 games), but it is not pure noise — variance
ratio 1.94, CI [1.21, 2.68] excludes 1.

---

## 5. Three results that bound ambition

**5.1 The SD ratio is not a dial.** At calibration slope 1.0 the identity
`slope = r · SD_actual / SD_predicted` collapses to
**`SD_predicted / SD_actual = r`**. A calibrated model's SD ratio *equals* its own
discrimination. MLB's 0.18 was never a ceiling — it was a slope of 0.61, i.e.
over-dispersion relative to the signal present. Estimated calibrated NFL
team-total SD ratio: **0.34–0.46**.

The canonical illustration, worth keeping: across a shrinkage grid K = 2→24,
**r stays flat at 0.339** while the SD ratio moves 0.489 → 0.182 and the slope
moves 0.688 → 1.866. At K = 24 it lands on **MLB's exact headline SD ratio with
three times MLB's r.** The SD ratio read alone cannot tell those apart.

**5.2 The baseline bar is much higher than MLB's.** A trivial **market-free**
forward-chained baseline reaches **r = 0.339 [0.244, 0.425], slope 1.021** on
team points. A frozen NFL baseline that does not beat this is a strawman, and
beating 0.1101 means nothing here. Game totals are the *harder* target — the book
itself manages only r = 0.305 on totals against 0.501 on margin.

**5.3 Power, corrected.** The grounding brief's "~1,131 games with threefold
clustering" was **mine and is withdrawn** — it treated a standard-error ratio as
a sample-size multiplier. MLB's 1.653pp against 0.587pp is a design effect of
**7.93**, applying to player-prop analyses rather than game-level r.

| Level | Games needed | NFL seasons at 272 |
|---|---|---|
| Game-level r (0.11 → 0.25) | ~377 | **~1.4** |
| Player-prop, clustered | ~2,000–3,000 game-equivalents | **7–11** |

This is the binding constraint on the programme, and saying so now prevents it
being discovered later as a disappointment.

---

## 6. The item with a deadline

**The weekly injury cascade is destroyed by waiting.** Measured:

- The nflverse archive keeps **one row per player-week** — 2024: 6,215 rows
  against 6,213 distinct `(season, week, gsis_id)` — stamped near the Friday
  report. Wednesday's practice vintage is overwritten, not stored.
- **`injuries_2025.csv` dropped `date_modified` while keeping 16 columns**
  (`season_type` replaced it). A column-count check passes straight through the
  loss of the file's only clock.
- **`injuries_2026.csv` is 404 today.** Week 1 opens **2026-09-09**.
- Loss per uncaptured week: **~132 bits of availability entropy** and **~331
  practice trajectories**. The only surviving evidence of the cascade anywhere in
  2024 is **two accidental duplicate rows**.

`nfl/tools/capture_vintage.py` is built and running. It is data capture, not
prediction: it fetches bytes, records what arrived, and refuses to interpret. It
inherits `Outcome` and the five clocks from `v8/governance` rather than coining a
parallel vocabulary; HTTP `Last-Modified` supplies the `source_timestamp` the
2025+ schema no longer carries. Raw bytes are written **before** parsing. The log
is **append-only**, so "never overwrite Tuesday with Sunday" holds by
construction rather than by remembering — an unchanged file at a later hour is a
*measurement*, getting a new manifest row and no new blob.

First real run carries `injuries` as an owed **`DEFERRED / SOURCE_NOT_YET_PUBLISHED`**
debt — the expected pre-season state, and precisely the condition whose absence
(Class B1) aborted V7's first live batch.

**What it still needs from the networked agent:** official inactives (the
~90-minute pre-kickoff list that resolves `Questionable` to 0/1), transactions,
the primary practice feed, and beat-reporter role information. Outbox §33 item A1.

Related and favourable: **role vintages are not on the losing clock.**
`depth_charts` became a daily `dt` series in 2025 and is already running for
2026 (170 values through 2026-09-06T11:29:30Z).

---

## 7. Availability, measured — the table most likely to change a projection

Cluster-bootstrapped by team-week, with 2025 as out-of-sample replication:

| Designation | n | P(play) 2024 | 95% CI | P(play) 2025 |
|---|---|---|---|---|
| Out | 1,116 | 0.0009 | [0.0000, 0.0028] | 0.0000 |
| Doubtful | 194 | 0.0000 | [0.0000, 0.0000] | 0.0000 |
| Questionable | 1,513 | **0.6550** | [0.6297, 0.6786] | 0.6518 |
| No designation | 3,386 | 0.9430 | [0.9336, 0.9520] | 0.9385 |

The conventional reading of Doubtful ≈ 25% and Questionable ≈ 50% is **wrong by
25 and 15 points**. Both 2025 figures replicate within a third of a point.

**Role given active is the larger half.** Questionable players who play sit at
0.90× their own healthy baseline at the median, but P(< 0.50× baseline) = **0.178
against 0.077** for healthy. RBs worst; QBs effectively binary. A point estimate
destroys this — hence `P(role | active)` must be a distribution.

Two fields beat practice status outright: the **`Not injury related - resting
player`** tag inverts DNP entirely (0.876 vs 0.118), and **body part** spreads
Questionable from hamstring 0.554 to foot 0.881.

---

## 8. Data traps found, and the rule that generalises them

| Field | Reality |
|---|---|
| `participation.ngs_air_yards` | **0 non-null of 45,919** — REJECTED, SOURCE EMPTY |
| `pbp.pass_attempt` | **includes sacks** (1,314 of 19,153). As a completion denominator gives 0.6072 vs 0.6555 — an error **larger than the entire between-QB spread** (0.0343) |
| `pbp.passer_player_id` | **null on 100% of scrambles** (5.25% of dropbacks) |
| `ftn.n_blitzers` | counts **extra** rushers; a naive `>= 5` filter returned **1 blitz in a season** |
| `n_pass_rushers==0`, `defenders_in_box==0`, `read_thrown=='0'` | **not-applicable sentinels**, not measured zeros |
| `advstats.receiving_broken_tackles` | **100% null** — REJECTED, SOURCE EMPTY |
| `advstats.def_yards_allowed` | **39.7% missing** while siblings are 0%; summing it under-counts ~40% and looks plausible |
| `injuries.date_modified` | **removed in 2025** behind an unchanged column count |

**The rule:** *a column existing is not a column carrying values.* Ingest must
assert per-column non-null fractions and refuse an empty field.

**And its necessary qualifier**, from the defence worker: missingness must be
reported **against the denominator the field is defined on**. The coverage
columns are 51.2% blank file-wide but **0.23% blank on dropbacks** — the blanks
are run plays, where a coverage shell is undefined. Discarding the column on the
file-wide figure would have been absence-read-as-success in mirror image: a
correctly-scoped NULL read as data loss.

**Leakage:** 14 market-derived columns (6 in `pbp`, 8 in `schedules`), already
populated for **112 of the 272 unplayed 2026 games**, and re-stamped by `pbp`
onto all 49,492 rows — so quarantining `schedules` alone is insufficient. Also
`result`/`total`, `away_qb_id`/`home_qb_id` (285/285 for 2024, **0/272 for 2026**
— the zeros are the tell), `weekly_rosters.status` encoding `INA` with no
timestamp, and 31 model-derived pbp columns with unconfirmed fit windows.

---

## 9. The asset MLB never had

The 2026 season is **272 regular-season games, 18 weeks, and zero results
recorded** as of 2026-09-06. It is a genuinely untouched prospective window.

Everything in the foundation document is **exploratory** — measured on 2024–25
data that has now been inspected, and inspection is exactly what disqualified
MLB's 251-game development set. Freezing inspected data does not make it a
holdout. The 2026 window is consumed by use, so sealing predictions before
kickoff from week 1 is worth more than any modelling head start.

---

## 10. Corrections I made to my own inputs

Six, all recorded in `nfl/research/_GROUNDING.md` rather than edited away, so a
reader of an earlier copy can see what moved:

1. The **power figure** (§5.3) — misapplied a standard-error ratio. Withdrawn.
2. **`route` supports TPRR** — refuted by two workers, reproduced by me. Withdrawn.
3. **NGS receiving is 404** — wrong extension, not a missing dataset. It is at
   `.csv.gz`, 2016–2025, and is the stack's only separation/cushion source
   (with a selection hazard: 29.4% coverage, correlated with volume).
4. **`ngs_air_yards` is usable** — it is entirely empty.
5. **Denominator defects** in `pass_attempt`, `passer_player_id`, `n_blitzers`.
6. **`injuries` schema** lost its timestamp in 2025.

Two of the four datasets I originally recorded as "absent" were live under
another name. The rule now stated: **a 404 means this path 404ed** — never that
the dataset does not exist.

---

## 11. Tensions left standing, not averaged

1. **Efficiency shrinkage (RB).** Forward-chained, prior efficiency is worse than
   a constant. Yet full shrinkage to the league mean is *not* supported — optimal
   own-YPC weight 0.93, costing +1.135 RMSE yards with a CI excluding zero under
   three clusterings. Resolution is an experiment, not an argument.
2. **Opponent adjustment.** An opponent term marginally helped team points but
   *reduced* points-per-drive r from 0.338 to 0.321 while improving slope to
   0.978. Both within noise at n = 330.
3. **Sack rate.** The QB worker measured sacks *taken* as the best year-over-year
   figure in the pass (+0.725/+0.571/+0.423); the defence worker measured sacks
   *generated* at reliability **0.000**, and showed a sack is definitionally a
   pressure. Opposite sides of the ball, so not a contradiction — but they must
   not be conflated under one feature name.

Two workers also withdrew their own attractive results mid-pass, including one
where a paired bootstrap put P(effect > 0) at 0.670 rather than established.

---

## 12. What needs you, and what needs the other agent

**Yours (owner-level):**
- Whether the capture harness should have been built during a research-only pass.
  My judgement: it is data capture, not prediction, and the window closes
  2026-09-09. It is reversible; say so if you disagree and it stops.
- Whether the first frozen NFL baseline is authorised to proceed once NFL-0's
  gate passes.

**Theirs (outbox §33), seven items, one urgent:**
- **A1** live injury capture before 2026-09-09 — the only irreversible item.
- **A2** fit windows for `xpass`/`pass_oe` and 31 model-derived columns.
- **A3** whether the `ffopportunity` expected-points column is genuinely
  oracle-opportunity — the claim I most want checked, since a benchmark bracket
  rests on schema inference rather than documentation.
- **A4** whether NFL changes a structural rule most offseasons — decides whether
  the market **trigger** is slow or **unreachable**.
- **A5–A7** Hard Rock Bet NFL coverage, DFS structures from primary sources, and
  whether NFL data already exists in storage outside this checkout.

The entry also states what **not** to spend egress on: the 2016–2025 archives are
verified and already measured here.

---

## 13. Status

`real_money.status` remains `NOT ENABLED`. `weekly_exposure_cap` remains `UNSET`
and was not filled in. No wager is recommended anywhere in this pass. No parlay
appears anywhere, including in discussion. Nothing is CORE in the NFL feature
register, because no NFL experiment has run.

The work is the **NFL Greenfield Track**. Not V9, not NFL V1. The first frozen
baseline takes a name chosen when it is frozen, and does **not** inherit "M0".
