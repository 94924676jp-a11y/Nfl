# W6 — Defence and matchup layer

**Worker:** 6 (defence / matchup) · **Date:** 2026-09-06 · **Status:** research output,
not a finding of the project until reviewed. No production code was written and no
file outside this one was modified.

Every substantive claim below carries exactly one of `VERIFIED` / `DERIVED` /
`UNVERIFIED-RECALL`, per `nfl/research/_GROUNDING.md`. Commands and scripts are in
the appendix; the scripts live in the session scratchpad
(`.../scratchpad/w6/`) as evidence, not as deliverables.

---

## 0. The one-paragraph answer to the central question

`DERIVED` from the measurements below. **Most of the defensive layer that public NFL
models use is noise at one-season resolution, and the part that is real is mostly
*behaviour*, not *outcomes*.** In 2024, a defence's play-calling tendencies (man/zone
share, coverage-shell share, blitz rate) are estimated with 17-game reliability of
0.81–0.88 and separate the 32 teams by 12–19× the binomial noise floor. Its
*outcome* rates are far weaker: pass EPA allowed has 17-game reliability 0.094 with a
95% interval reaching 0.000, and sack rate per dropback has no resolvable
between-team component at all. Pressure rate generated (0.693) and takeaways per play
(0.499) are the only two outcome-side quantities that survive a bootstrap over teams.
The practical consequence is a strict ordering for what a defence adjustment may be
built from — scheme first, pressure second, takeaways third with heavy shrinkage,
everything else effectively league-average until multi-season pooling exists.

---

## 1. Frame and provenance

`VERIFIED` — all measurements use the shared cache; no pbp or participation file was
re-downloaded.

| Item | Value | Command |
|---|---|---|
| `pbp2024.csv` rows | 49,492 | `python3.12 w6/m1_load.py` |
| ... regular season (`season_type == "REG"`) | 47,274 | same |
| REG games | **272** | same; cross-checked against `schedules_games.csv` (2024 REG = 272) |
| Defensive teams | 32, each exactly 17 team-games (544 total) | `w6/m2_teamgame.py` |
| Scrimmage plays (`play==1`, `special_teams_play==0`, no kneel/spike, `play_type ∈ {pass, run}`) | 33,470 (61.5 per team-game) | same |
| ... pass-flagged | 20,216 | same |
| ... rush-flagged | 13,254 | same |
| REG dropbacks (`qb_dropback==1`) | 20,215 (37.2 per team-game) | `w6/m4_join.py` |

`VERIFIED` — this settles one `UNVERIFIED-RECALL` item carried in `_GROUNDING.md`:
the NFL regular season is **272 games**, confirmed from two independent files.

### Participation join — the missingness result matters and reverses the brief's premise

The task brief asked me to check missingness before building on the scheme columns.
I did, and the naive answer is misleading.

`VERIFIED` (`w6/m3_part.py`, `w6/m4_join.py`):

| Column | Missing over all 45,919 participation rows | Missing **over the 20,215 REG dropbacks** |
|---|---|---|
| `was_pressure` | 0.0003 | **0.0000** |
| `number_of_pass_rushers` | 0.0003 | 0.0000 |
| `defenders_in_box` | 0.0003 | 0.0000 |
| `defense_man_zone_type` | 0.5120 | **0.0023** |
| `defense_coverage_type` | 0.5120 | **0.0023** |
| `time_to_throw` | 0.5703 | 0.1187 |
| `route` | 0.5838 | — |

`DERIVED`: the 51.2% blank rate on the coverage columns is **entirely the non-dropback
plays**. Charting a coverage shell on a handoff is not meaningful, and the column is
correctly blank there. On the population where the field is defined — dropbacks — it
is 99.77% populated, with no per-defence concentration (worst team DAL at 1.51%
missing, `w6/m14_scheme.py`) and no week-level pattern (max 1.23% in week 1,
`w6/m4_join.py`).

`DERIVED` — **this is a live instance of V8 Failure Taxonomy Class A in the opposite
direction.** The usual Class A error is reading absence as success. The mirror-image
error, which a careless missingness audit produces, is reading a *correctly scoped
NULL* as data loss and discarding a usable column. Both are the same defect: a
denominator was not stated. Under Constitution Rule 019 every rate declares its
unit; the same discipline must apply to missingness, which is always missingness
*with respect to a denominator*. Any ingest check the NFL system builds should report
missingness against the denominator on which the field is defined, never against the
whole file.

100% of REG dropbacks matched a participation row (20,215 of 20,215). Overall,
43,853 of 47,274 REG pbp rows matched — the gap is non-dropback and non-scrimmage
plays that participation does not carry.

---

## 2. Defensive team stability, ranked (task item 1)

### Method

`VERIFIED`. Two independent estimators, deliberately, because the first turned out to
be unreliable and I would have reported a wrong ranking from it alone.

1. **Split-half.** Partition each defence's 17 games into 8 and 9, compute each rate
   from *pooled* numerator and denominator within each half (not the mean of game
   rates), correlate across the 32 defences. I report both the single odd/even split
   the brief asked for and the mean over 500 random partitions.
2. **One-way random-effects reliability on game-level values.** Estimate the
   between-defence variance component σ²_b and the within (game-to-game) component
   σ²_w by ANOVA on team-game means, giving single-game reliability
   ρ₁ = σ²_b / (σ²_b + σ²_w), and n-game reliability by Spearman-Brown
   ρ_n = nρ₁ / (1 + (n−1)ρ₁).

Confidence intervals are a **bootstrap over the 32 defences**, resampling whole
defences with all their games. That choice is load-bearing and is explained in §2.3.

### 2.1 The ranking

`VERIFIED` — `python3.12 w6/m29_boot.py` (ρ₁ and CI), `python3.12 w6/m6_repsplit.py`
(repeated split-half), `python3.12 w6/m5_splithalf.py` (odd/even).

n = 32 defences, 544 team-games, 2024 regular season only.

| Rank | Component | ρ₁ (1 game) | **Reliability at 17 games** | 95% CI (bootstrap over defences) | Repeated split-half r (8 v 9 games) | Odd/even split r |
|---|---|---|---|---|---|---|
| 1 | Cover-3 rate *(behaviour)* | 0.2976 | **0.878** | [0.770, 0.923] | — | — |
| 2 | Man-coverage rate *(behaviour)* | 0.2916 | **0.875** | [0.807, 0.907] | +0.776 | — |
| 3 | Cover-1 rate *(behaviour)* | 0.2631 | **0.859** | [0.738, 0.908] | — | — |
| 4 | Blitz rate, ≥5 rushers *(behaviour)* | 0.2005 | **0.810** | [0.706, 0.862] | — | — |
| 5 | **Pressure rate generated** | 0.1170 | **0.693** | [0.426, 0.796] | +0.514 | +0.281 |
| 6 | **Takeaways per play** | 0.0554 | **0.499** | [0.176, 0.668] | +0.315 | +0.231 |
| 7 | Rush EPA/play allowed | 0.0504 | 0.475 | [0.000, 0.658] | +0.381 | +0.396 |
| 8 | Completion rate allowed | 0.0423 | 0.429 | [0.000, 0.615] | +0.243 | +0.218 |
| 9 | All EPA/play allowed | 0.0411 | 0.422 | [0.000, 0.604] | +0.252 | +0.225 |
| 10 | Explosive rate allowed (all) | 0.0263 | 0.315 | [0.000, 0.534] | +0.209 | +0.241 |
| 11 | Points allowed per drive | 0.0225 | 0.281 | [0.000, 0.511] | +0.176 | +0.157 |
| 12 | INT per dropback | 0.0133 | 0.187 | [0.000, 0.472] | +0.164 | −0.056 |
| 13 | Pass EPA/play allowed | 0.0061 | 0.094 | [0.000, 0.341] | +0.042 | +0.073 |
| 14 | Explosive pass allowed (≥20 yd) | 0.0015 | 0.024 | [0.000, 0.331] | +0.008 | +0.077 |
| 15 | **Sack rate per dropback** | 0.0000 | **0.000** | [0.000, 0.234] | −0.060 | −0.005 |

Metric definitions (`VERIFIED`, `w6/m6_repsplit.py`): explosive = ≥20 yards on a
pass-flagged play or ≥10 on a rush-flagged play; points per drive maps
`fixed_drive_result` Touchdown → 7, Field goal → 3, Opp touchdown → −7, Safety → −2,
everything else → 0, one row per `(game_id, defteam, fixed_drive)`.

`DERIVED` — the two estimators agree closely where both were run. Reliability at 8.5
games from ANOVA versus mean repeated-split r: pressure 0.530 / 0.514, takeaways
0.333 / 0.315, completion allowed 0.273 / 0.243, all-EPA 0.267 / 0.252, explosive-all
0.187 / 0.209, points/drive 0.163 / 0.176, pass-EPA 0.049 / 0.042, explosive-pass
0.012 / 0.008, sack rate 0.000 / −0.060 (`w6/m10_shrink.py` vs `w6/m6_repsplit.py`).
Two methods with different assumptions landing on the same ordering is the reason I
am willing to state the ordering at all.

### 2.2 Sack rate has no measurable team component, and here is why

`VERIFIED` — `python3.12 w6/m11_sack.py`:

- League sack rate 0.0650 per dropback on 20,215 dropbacks. Observed between-team
  variance 1.05×10⁻⁴; the variance expected from binomial sampling alone at each
  team's dropback count is 9.7×10⁻⁵. **Ratio 1.08.**
- Sack rate given `was_pressure == 1`: **0.2104** (n = 6,240). Given
  `was_pressure == 0`: **0.0001** (1 sack in 13,975 plays).
- Team-level conversion of pressure into sacks: league 0.2104, observed variance
  6.56×10⁻⁴ against a binomial expectation of 8.73×10⁻⁴ — **ratio 0.75**, i.e. *below*
  the chance floor.

`DERIVED` — two consequences, both structural.

1. **A sack is definitionally a pressure in this feed.** With 1 sack out of 13,975
   non-pressure dropbacks, `was_pressure` is very close to a necessary condition for
   `sack`. Sack rate and pressure rate are therefore not two independent measurements
   of a pass rush; sack rate is pressure rate multiplied by a conversion factor.
2. **That conversion factor is a constant, not a team property.** At a variance ratio
   of 0.75 the 32 teams are indistinguishable from 32 draws of the same binomial. Any
   feature of the form "this defence finishes its pressures" is, on one season of
   data, a feature with nothing in it.

`DERIVED` — reconciling with the 0.648 season correlation between team pressure rate
and team sack rate (`w6/m11_sack.py`): sack rate *does* inherit signal from pressure
rate, but the inherited true SD (0.0376 × 0.2104 ≈ 0.0079) sits under a binomial noise
SD of 0.0099 at ~630 dropbacks per team, so it is not separable at this sample. The
honest statement is not "sack rate is meaningless" — it is **"sack rate is a
low-efficiency estimator of a quantity that `was_pressure` measures directly and
about four times more precisely, and at n = 32 defences × 17 games the difference is
the whole signal."** Use pressure; never fit on sacks.

### 2.3 A methodological warning the brief's own recipe produced

`VERIFIED`. The brief asked for odd/even split-half. For pressure rate that specific
split returns r = +0.281, while the mean over 2,000 random 8-v-9 partitions of the
same data is +0.513 (sd 0.091). **The odd/even value sits at the 0.4th percentile of
the random-split distribution** (`python3.12 w6/m7_check.py`).

I looked for a cause and did not find one:

- Home/away parity confound `RULED OUT` (`w6/m8_parity.py`): mean absolute
  home-share difference between odd and even halves is 0.214, against 0.203 for
  random splits — no difference. (Pressure is 0.320 at home vs 0.298 away, n ≈ 10k
  each, so the confound would have been real had the imbalance existed.)
- Single-team leverage `RULED OUT` (`w6/m9_jk.py`): the largest leave-one-defence-out
  change is +0.043 (dropping CIN). No team drives it.

`DERIVED` — I cannot name the cause, so I report it as what it is: **a single
split-half correlation on 32 units is not a stable statistic, and ranking metrics by
one is unsafe.** Had I run only the odd/even split I would have reported pressure
rate as *less* stable than rush EPA allowed, which both other estimators contradict.
Any NFL stability protocol this project adopts must specify repeated partitions or a
variance-component estimator, and must state the resampling unit.

`DERIVED` — related and more important: the percentile intervals in the "repeated
split-half" column measure *split-to-split* variation with the teams held fixed. They
are **not** sampling uncertainty and are much too narrow to be read as such. The CI
column in the table is the honest one, because it resamples defences. Where the two
disagree, the wider one is right. This is the same lesson `CLAUDE.md` records for MLB
props — naive SEs understated uncertainty roughly threefold because the clustering
unit was wrong.

### 2.4 What the true spreads actually are

`VERIFIED` — `python3.12 w6/m27_effect2.py`. Between-defence SD after removing the
game-clustered sampling component:

| Component | Observed season SD | **True between-defence SD** | Signal share of observed variance |
|---|---|---|---|
| Man-coverage rate | 0.0879 | **0.0822** | 0.875 |
| Pressure rate generated | 0.0432 | **0.0360** | 0.693 |
| Rush EPA/play allowed | 0.0733 | 0.0505 | 0.475 |
| All EPA/play allowed | 0.0660 | 0.0428 | 0.422 |
| Takeaways per play | 0.0060 | 0.0042 | 0.499 |
| Pass EPA/play allowed | 0.0793 | **0.0243** | 0.094 |

`DERIVED` — a 2-SD-good pass defence is worth 0.049 EPA/play, roughly 1.8 EPA over
37 dropbacks, and the *observed* season table will suggest 0.159 EPA/play — over
three times too much. Publishing raw defensive rankings without this correction is
the single most likely way this layer would mislead a projection.

`VERIFIED` caution on estimator choice: a play-level noise estimate (treating plays
as independent) gives a true pass-EPA SD of 0.0384 instead of 0.0243
(`w6/m26_effect.py` vs `w6/m27_effect2.py`), i.e. it inflates the apparent signal
variance by 2.5×, because plays within a team-game are correlated. **Every variance
component in this document is computed on game-level means for that reason.** The
game is the cluster.

---

## 3. Turnover generation (task item 2)

The prior I was asked to test, restated: `UNVERIFIED-RECALL` — "turnover generation
is heavily noise-driven and needs aggressive regression."

`VERIFIED` — `python3.12 w6/m21_to.py`, `python3.12 w6/m22_tocheck.py`:

| Component | Unit | League rate | Season count range | Observed var ÷ binomial | ρ₁ | Reliability @17g |
|---|---|---|---|---|---|---|
| Takeaways (INT + fumble lost) | per play | 0.01861 | 8 – 31 | **1.94** (bootstrap 95% CI **[1.21, 2.68]**) | 0.0554 | **0.499** |
| Interceptions | per play | 0.01156 | — | 1.60 | — | — |
| Interceptions | per dropback | 0.01912 | 4 – 24 | 1.35 | 0.0133 | 0.187 |
| Opponent fumbles **forced** | per play | 0.01173 | 5 – 18 | **1.03** | 0.0050 | 0.079 |
| Opponent fumbles (any) | per play | 0.01634 | 7 – 26 | 1.10 | 0.0131 | 0.184 |
| Opponent fumbles **lost** | per play | 0.00705 | 2 – 14 | 1.32 | 0.0261 | 0.313 |
| Fumble **recovery share** given an offensive fumble | per fumble | **0.4314** (236 of 547) | — | **0.98** | — | — |

### The verdict is a qualified confirmation, and the qualification matters

`DERIVED`:

- **Confirmed:** the prior is right that aggressive regression is required.
  Reliability at a full 17 games is 0.499, so **half the observed season-long spread
  in takeaways is sampling noise**, and a defence's observed rate should be pulled
  half of the way back to league average even after a complete season. True
  between-defence SD is 0.0042 per play against a league mean of 0.0186 — a 2-SD
  defence is 0.0102 to 0.0270 takeaways per play, while the *observed* 2024 range is
  0.0072 to 0.0289.
- **Not confirmed:** the prior is wrong if read as "pure noise". The bootstrap CI on
  the variance ratio, [1.21, 2.68], excludes 1.00. There is a real, resolvable
  team component. Cross-half predictive correlation is +0.321 (95% split interval
  [0.096, 0.539]; `w6/m20_cross.py`) — *higher* than that of points allowed per drive
  (+0.166) or all-EPA allowed (+0.252).
- **Fumble recovery is a coin flip, measured.** 0.4314 recovery share with a variance
  ratio of 0.98 — precisely the chance floor. Forced fumbles per play at 1.03 is also
  at the floor. Neither may be modelled as a team skill from one season.
- **A structural surprise worth recording.** The composite is *more* reliable than
  either component. Signal variance of takeaways/play is 1.643×10⁻⁵, against
  8.73×10⁻⁶ expected if INT-signal and fumble-signal were independent
  (`w6/m22_tocheck.py`). The reason is that they covary across defences: r = +0.303
  between team INT rate and team fumble-lost rate. Defences that take the ball away
  one way take it away the other way. `UNVERIFIED-RECALL` for the mechanism (pressure
  and aggressive coverage plausibly generate both); `VERIFIED` for the correlation.

### Year-over-year: interceptions do not carry at all

`VERIFIED` — `python3.12 w6/m23_yoy.py`, using `pfr_advstats` weekly defence files
for 2022, 2023 and 2024 (911 KB / 914 KB / 924 KB; small files, downloaded fresh; no
pbp or participation re-downloaded):

| Team-season quantity | 2022→2023 | 2023→2024 | 2022→2024 |
|---|---|---|---|
| PFR pressures per game | +0.356 | +0.229 | −0.106 |
| PFR sacks per game | +0.275 | +0.167 | +0.142 |
| **Interceptions per game** | **+0.026** | **−0.073** | **+0.317** |

`DERIVED` — team interception rate has essentially **no** adjacent-season carryover
(mean of the two adjacent pairs ≈ −0.02). The 2022→2024 value of +0.317 with two
adjacent values near zero is not a pattern any mechanism explains; it is what
n = 32 sampling noise looks like across three comparisons.

### The negative result, stated bluntly as asked

`DERIVED`. **A pre-season or early-season defensive turnover rating carried over from
the prior year is a feature with no measured content, and it should not be built.**
Within a season, takeaway rate is real but must be shrunk by half at 17 games and by
81% at 4 games (§5.2). Any decomposition into "this defence forces fumbles" or "this
defence recovers fumbles" is unsupported: both components sit at the chance floor.
The only defensible turnover feature is the **composite takeaway rate, opponent-
adjusted, heavily shrunk, and rebuilt from scratch each season.**

---

## 4. Scheme (task item 3)

Missingness was checked first (§1): 0.23% on the dropback denominator, so the columns
are usable. This is the strongest part of the defensive layer.

### 4.1 How much teams differ

`VERIFIED` — `python3.12 w6/m14_scheme.py`, 20,168 charted REG dropbacks:

| Tendency | League rate | Team range | Observed var ÷ binomial | ρ₁ | Reliability @17g |
|---|---|---|---|---|---|
| **Man coverage** (`MAN_COVERAGE`) | 0.4847 | 0.3226 (MIN) – 0.6114 (DET) | **19.3** | 0.2916 | 0.875 |
| Cover-1 | 0.3651 | 0.160 – 0.490 | 17.5 | 0.2631 | 0.859 |
| Cover-3 | 0.1765 | 0.058 – 0.325 | 16.7 | 0.2976 | 0.878 |
| Cover-2 | 0.2062 | 0.120 – 0.296 | 9.0 | 0.1607 | 0.765 |
| 2-Man | 0.0754 | 0.021 – 0.147 | 10.2 | 0.1380 | 0.731 |
| Cover-0 | 0.0443 | 0.019 – 0.084 | 3.9 | 0.1027 | 0.661 |
| Cover-6 | 0.0345 | 0.012 – 0.067 | 3.5 | 0.0642 | 0.538 |
| Cover-4 | 0.0604 | 0.023 – 0.118 | 5.9 | 0.0397 | 0.413 |
| **Blitz (≥5 rushers)** | 0.2644 | 0.162 – 0.389 | **12.6** | 0.2005 | 0.810 |

Man-coverage rate repeated split-half r = **+0.776** [0.673, 0.863] over 500 random
partitions, Spearman-Brown 0.874 — matching the ANOVA estimate of 0.875 to three
decimal places.

`DERIVED` — the contrast with §2 is the headline of this section. **Scheme separates
teams at 12–19× the noise floor; the outcomes those schemes produce separate teams at
1.0–5.2×.** Two defences differing by 0.29 in man rate (MIN 0.32 vs DET 0.61) is a
difference you can measure in four games; two defences differing in pass EPA allowed
need over 160 games to reach reliability 0.5 (§5.2).

`DERIVED` — the reason scheme is measurable and outcome is not is a denominator
argument, not a football argument. Man/zone is a near-50/50 binary observed 630 times
per team-season, so its binomial noise SD is ≈ 0.020 against a true spread of 0.082.
Pass EPA per play has a play-level SD of about 1.6 against a true team spread of
0.024, so at 630 dropbacks the noise SD is ≈ 0.063 — larger than the whole signal.
No modelling can recover what the denominator does not supply.

### 4.2 The confound that must be handled before scheme is used

`VERIFIED` — man-coverage rate by down (`w6/m14_scheme.py`): 1st down 0.434
(n=7,230), 2nd 0.461 (n=6,911), 3rd 0.559 (n=5,440), 4th 0.675 (n=489).

`DERIVED` — a defence's raw man rate is partly a record of the *game scripts it
faced*. A defence that led all season saw more obvious passing downs and will read as
more man-heavy than its own call sheet. **A scheme feature must be residualised on
down, distance and score state before it is treated as a team identity**, or the
feature will encode last season's win-loss record. I did not build that residualised
version — it is a modelling step and out of scope for this pass — but the raw rates
above should not be used until it exists. This is registered as experiment D-3 in §7.

### 4.3 What scheme is not, yet

`DERIVED` — high reliability establishes that a scheme measurement is **repeatable**.
It does not establish that it is **useful**. Nothing in this section shows that
knowing a defence's man rate improves any projection of any outcome. Under
Constitution Rule 005 those are different properties and neither implies the other,
exactly as calibration and discrimination are different properties in
`CLAUDE.md`. Scheme features enter the registry as EXPERIMENTAL with a stability
citation only; the usefulness experiment is D-3/D-4 in §7 and has not been run.

---

## 5. Pass rush versus protection (task item 4)

### 5.1 Pressure is the strongest process signal in the defensive layer

`VERIFIED` — `python3.12 w6/m15_pressure.py`, 20,215 REG dropbacks, league pressure
rate 0.3087:

| Outcome | `was_pressure == 0` (n=13,975) | `was_pressure == 1` (n=6,240) |
|---|---|---|
| EPA per dropback | +0.2444 | **−0.3818** (Δ = **−0.6262**) |
| Sack rate | 0.0001 | 0.2104 |
| Completion rate | 0.6777 | 0.3458 |
| Interception rate | 0.0182 | 0.0212 |
| Time to throw (s) | 2.424 | 3.321 |
| Yards gained | 7.555 | 3.399 |

Removing sacks, so the mechanical "a sack cannot be a completion" effect is gone
(n = 13,974 vs 4,927): EPA +0.2445 vs −0.0116, completion 0.6778 vs **0.4380**,
interception 0.0182 vs **0.0268**.

`DERIVED` — pressure costs the offence ~0.63 EPA per dropback overall and ~0.26 EPA
even when it does not produce a sack, and lifts interception rate by 47% relative.
It is not a proxy for sacks; it is the wider quantity of which sacks are the tail.

Rushers sent versus pressure produced (`w6/m15_pressure.py`, from
`number_of_pass_rushers`, 0.0000 missing): 3 rushers → 0.228 pressure rate (n=715),
4 → 0.281 (n=13,844), 5 → 0.378 (n=4,042), 6 → 0.446 (n=1,084), 7 → 0.484 (n=219).

### 5.2 Pressure predicts future defensive outcomes better than those outcomes predict themselves

`VERIFIED` — `python3.12 w6/m20_cross.py`, cross-half correlation r(X in half 1,
Y in half 2), mean over 400 random 8-v-9 partitions, n = 32 defences:

| Predictor (half 1) ↓ / Target (half 2) → | pressure rate | pass EPA | rush EPA | all EPA | sack rate | explosive | TO/play | pts/drive |
|---|---|---|---|---|---|---|---|---|
| **pressure rate** | **+0.518** | **−0.223** | −0.182 | −0.241 | +0.262 | −0.043 | +0.160 | **−0.242** |
| pass EPA | −0.195 | **+0.037** | +0.280 | +0.136 | −0.027 | +0.115 | −0.187 | +0.035 |
| rush EPA | −0.187 | +0.288 | **+0.375** | +0.371 | −0.059 | +0.229 | −0.223 | +0.331 |
| all EPA | −0.225 | +0.140 | +0.367 | **+0.252** | −0.051 | +0.167 | −0.235 | +0.165 |
| sack rate | +0.250 | −0.025 | −0.051 | −0.044 | **−0.066** | +0.007 | +0.095 | −0.021 |
| explosive rate | −0.032 | +0.106 | +0.221 | +0.157 | −0.001 | **+0.205** | −0.127 | +0.078 |
| TO/play | +0.164 | −0.201 | −0.220 | −0.241 | +0.114 | −0.135 | **+0.321** | −0.181 |
| pts/drive | −0.224 | +0.040 | +0.331 | +0.168 | −0.023 | +0.093 | −0.181 | **+0.166** |

`DERIVED` — the diagonal is not the maximum of its column for three targets. Pressure
rate in half 1 predicts half-2 pass EPA allowed (−0.223) better than half-1 pass EPA
does (+0.037), and predicts half-2 points allowed per drive (−0.242) better than
half-1 points per drive does (+0.166). Sack rate predicts nothing about itself
(−0.066) but does predict pressure rate (+0.250) — consistent with §2.2, sacks being
a noisy read of the pressure quantity.

**And here is where I have to hold the line on my own most attractive result.**

`VERIFIED` — `python3.12 w6/m28_paired.py`, paired bootstrap resampling the 32
defences *and* re-drawing the half split on each replicate:

- pressure(h1) → passEPA(h2): r = −0.191, 95% CI [−0.511, +0.159]
- passEPA(h1) → passEPA(h2): r = +0.006, 95% CI [−0.343, +0.347]
- paired difference in |r|: +0.079, 95% CI [−0.266, +0.416], **P(difference > 0) = 0.670**

`DERIVED` — **the ordering is not established.** The point estimate favours pressure
in 67% of bootstrap replicates, which is barely better than a coin flip. With 32
defences the sampling SE of a correlation is about 0.19, and the entire claimed
effect is 0.23. The narrow intervals in the table above are split-to-split variation
with the teams fixed, and reading them as evidence would be exactly the error §2.3
warns about. **Under Constitution Rule 006 this is `DEFERRED / UNDERPOWERED`, not a
finding.** It becomes testable at three to five seasons (96–160 team-seasons); it is
not testable on 2024. It is registered as experiment D-2 in §7 with that sample floor
attached, precisely so it cannot be quietly promoted later on the strength of the
2024 point estimate that suggested it.

### 5.3 Offensive line quality — what is and is not measurable

`VERIFIED` — I checked `pfr_advstats` as the brief asked (`w6/m19_pfrdef.py`).
`advstats_week_pass_2024.csv` (73 KB, 664 REG rows) carries `times_sacked`,
`times_blitzed`, `times_hurried`, `times_hit`, `times_pressured`,
`times_pressured_pct` with **0.0000 missingness on all six** — but every row is a
**quarterback**. Grep for any column naming a lineman or a block returns `[]`. The
weekly rush file carries `rushing_yards_before_contact`, which is a running-back row,
not a lineman row.

`DERIVED` — **individual offensive line quality is not directly measurable from any
feed reachable in this container.** What is measurable is the *offence's* pressure-
allowed rate, which is the joint product of five linemen, the backs and tight ends
who stay in, the play call, and the quarterback's own pocket behaviour. Attributing
it to "the line" would be a naming error with a real consequence: a quarterback
change would silently move a feature labelled as line quality.

Measured properties of that joint quantity (`w6/m16_matchup.py`, `w6/m23_yoy.py`):

| Quantity | ρ₁ | Reliability @17g | Season range | YoY 22→23 | YoY 23→24 |
|---|---|---|---|---|---|
| Defence: pressure **generated** | 0.1170 | 0.693 | 0.225 – 0.411 (sd 0.042) | +0.356 | +0.229 |
| Offence: pressure **allowed** | 0.0607 | 0.523 | 0.245 – 0.372 (sd 0.036) | **+0.469** | **+0.383** |
| Offence: sacks allowed | — | — | — | +0.406 | +0.364 |

`DERIVED` — within a season the pass rush is the more reliable half of the pair
(0.693 vs 0.523); across seasons the protection side carries better (+0.383 to +0.469
vs +0.229 to +0.356). `UNVERIFIED-RECALL` for the mechanism — line units turn over
less than edge-rusher rotations — and it must not be used as an explanation without
being tested.

### 5.4 Is a rush-versus-protection matchup term identifiable?

`VERIFIED` — `python3.12 w6/m16_matchup.py`. Additive logit model on game pressure
rate with empirical-Bayes shrunk team effects (pseudo-count 200 dropbacks), fitted on
a random half of the 272 games and scored on the held-out half, weighted RMSE,
averaged over 300 splits:

| Model | Out-of-sample weighted RMSE | Improvement vs league constant |
|---|---|---|
| League constant | 0.10324 | — |
| Defence effect only | 0.10073 | +2.43% |
| Offence effect only | 0.10261 | +0.61% |
| **Defence + offence** | **0.09970** | **+3.43%** |

`DERIVED` — **yes, a matchup term is identifiable, and the two sides are close to
additive**: 2.43% + 0.61% = 3.04% predicted, 3.43% measured, so if anything they
combine slightly better than additively. Cross-team correlation between a team's own
pass-rush rate and its own pressure-allowed rate is +0.209 (`w6/m16_matchup.py`), so
the two effects are close to separable and the design is not collinear.

`DERIVED` — but read the magnitude honestly. **3.4% RMSE reduction on the quantity the
model is most reliable about.** That is the ceiling of the pass-rush matchup layer,
not a starting point, and it is measured on the metric the defence layer knows best.
Any downstream feature that claims a larger effect on a *less* reliable quantity —
pass EPA allowed, points allowed — is claiming something this data contradicts.

---

## 6. The opponent-adjustment trap (task item 5)

### 6.1 How big is the problem

`VERIFIED` — `python3.12 w6/m24_sched.py`. Dispersion across the 32 defences of the
season-mean offensive EPA/play of the opponents they had faced, by week:

| Games played | SD of opponent-offence strength faced |
|---|---|
| 1 | 0.1003 |
| 2 | 0.0758 |
| 4 | **0.0475** |
| 6 | 0.0339 |
| 8 | 0.0290 |
| 12 | 0.0167 |
| 17 | 0.0147 |

For comparison (`w6/m27_effect2.py`): the **true** between-defence SD in all-EPA
allowed is **0.0428**, and the observed season SD is 0.0660. Correlation between
schedule strength faced and raw EPA allowed over the full season is +0.196
(`w6/m24_sched.py`).

`DERIVED` — **through roughly week 5, the spread in schedules faced is larger than the
entire true spread in defensive quality.** An unadjusted week-4 defensive ranking is
majority schedule. By week 17 the schedule contribution is down to 0.0147, about a
third of the true defensive SD, which is small but not ignorable.

### 6.2 Does adjustment help, and is the help real?

`VERIFIED` — `python3.12 w6/m12_oppadj.py`. Leave-one-out adjustment: for each
defence-game, subtract the opponent offence's own season mean computed **excluding
that game**, then re-estimate reliability.

| Metric | Reliability @17g, raw | Opponent-adjusted (LOO) |
|---|---|---|
| Pass EPA/play allowed | 0.094 | **0.259** |
| All EPA/play allowed | 0.422 | **0.545** |
| Rush EPA/play allowed | 0.475 | 0.519 |
| Pressure rate generated | 0.693 | 0.725 |
| Takeaways per play | 0.499 | 0.515 |

`VERIFIED` — placebo test (`python3.12 w6/m13_placebo.py`), 300 replicates shuffling
the opponent-strength values across rows so the adjustment is applied to the wrong
opponents:

| Metric | Raw | True adjustment | Placebo mean [2.5%, 97.5%] | P(placebo ≥ true) |
|---|---|---|---|---|
| Pass EPA allowed | 0.094 | 0.259 | 0.087 [0.000, 0.284] | **0.040** |
| All EPA allowed | 0.422 | 0.545 | 0.361 [0.160, 0.496] | **0.0033** |

`DERIVED` — the placebo mean sits at the raw value, so the adjustment machinery does
not manufacture reliability by itself. The all-EPA gain is solid (p = 0.0033). The
pass-EPA gain is **marginal** (p = 0.040 on one of two tests reported here; with any
multiplicity correction over the five metrics it does not survive). The
attention-grabbing "pass-EPA reliability nearly tripled" is the least secure number
in this document and I flag it as such.

### 6.3 How to avoid the circularity

`DERIVED` — the circularity is real and my own §6.2 measurement is inside it: the
opponent's season offensive EPA was itself produced against defences, one or two of
which are the defence being adjusted. Leave-one-out removes the single game; it does
not remove the second divisional meeting, and it does not remove the fact that the
offence's rating absorbed defensive quality league-wide.

Five requirements, in the order they bind:

1. **Simultaneous estimation, not sequential.** Adjusting offences for defences and
   then defences for the already-adjusted offences is a one-and-a-half-step version
   of an iteration that has a fixed point. Fit both sides at once — a single ridge or
   mixed model with offence and defence effects and a home term — so neither is
   conditioned on a partially-adjusted version of the other. Constitution Rule 016's
   one-direction-of-flow requirement applies to the pipeline, not to the estimator;
   this is a within-stage joint fit.
2. **The rating a game uses must never have seen that game.** Not "recomputed after
   the season with a hold-out"; the input manifest for a week-N projection contains
   only weeks 1..N−1. `CLAUDE.md`'s M0 lesson applies exactly: a fingerprint that
   excludes the corpus will not catch a corpus substitution, so the *adjustment
   ratings themselves* must be content-hashed into the manifest.
3. **A shuffled-opponent placebo is mandatory, not optional.** §6.2 shows a placebo
   can reach 0.284 on pass EPA by chance. Any claimed gain must be reported against
   its placebo distribution, and the placebo must be pre-registered under Rule 004a
   before the real adjustment is scored.
4. **Sum-to-zero, and say against what.** An adjustment is only interpretable
   relative to a stated league mean over a stated window. State it.
5. **Never adjust toward the market.** `spread_line`, `total_line`, `vegas_wp`,
   `vegas_wpa`, `vegas_home_wp` sit inside `play_by_play` (`_GROUNDING.md`), and
   opponent strength is exactly the quantity a spread encodes. Quarantine at ingest,
   per `CLAUDE.md` rule 1 and Constitution Rule 012.

### 6.4 How many games before an adjustment is worth applying, and how much to shrink

`VERIFIED` — `python3.12 w6/m25_table.py`. Shrinkage weight w on the observed value
(projection = w × observed + (1 − w) × league mean), from
w(n) = nρ₁ / (1 + (n−1)ρ₁), with ρ₁ from §2.1:

| Component | w @1g | w @2g | w @4g | w @6g | w @8g | w @12g | w @17g | w @34g | Games to w = 0.5 |
|---|---|---|---|---|---|---|---|---|---|
| Cover-3 rate | 0.298 | 0.459 | 0.629 | 0.718 | 0.772 | 0.836 | 0.878 | 0.935 | **2.4** |
| Man-coverage rate | 0.292 | 0.452 | 0.622 | 0.712 | 0.767 | 0.832 | 0.875 | 0.933 | **2.4** |
| Cover-1 rate | 0.263 | 0.417 | 0.588 | 0.682 | 0.741 | 0.811 | 0.859 | 0.924 | 2.8 |
| Blitz rate ≥5 | 0.201 | 0.334 | 0.501 | 0.601 | 0.667 | 0.751 | 0.810 | 0.895 | 4.0 |
| Pressure rate generated | 0.117 | 0.209 | 0.346 | 0.443 | 0.515 | 0.614 | 0.693 | 0.818 | **7.5** |
| Takeaways per play | 0.055 | 0.105 | 0.190 | 0.260 | 0.319 | 0.413 | 0.499 | 0.666 | **17.1** |
| Rush EPA/play allowed | 0.050 | 0.096 | 0.175 | 0.242 | 0.298 | 0.389 | 0.474 | 0.643 | 18.8 |
| Completion rate allowed | 0.042 | 0.081 | 0.150 | 0.209 | 0.261 | 0.346 | 0.429 | 0.600 | 22.6 |
| All EPA/play allowed | 0.041 | 0.079 | 0.146 | 0.205 | 0.255 | 0.340 | 0.422 | 0.593 | 23.3 |
| Explosive rush allowed | 0.033 | 0.064 | 0.120 | 0.170 | 0.214 | 0.291 | 0.367 | 0.537 | 29.3 |
| Explosive rate (all) | 0.026 | 0.051 | 0.098 | 0.139 | 0.178 | 0.245 | 0.315 | 0.479 | 37.0 |
| Fumbles recovered/play | 0.026 | 0.051 | 0.097 | 0.139 | 0.177 | 0.243 | 0.313 | 0.477 | 37.3 |
| Points allowed per drive | 0.022 | 0.044 | 0.084 | 0.121 | 0.156 | 0.216 | 0.281 | 0.439 | 43.4 |
| INT per dropback | 0.013 | 0.026 | 0.051 | 0.075 | 0.097 | 0.139 | 0.186 | 0.314 | 74.2 |
| Pass EPA/play allowed | 0.006 | 0.012 | 0.024 | 0.036 | 0.047 | 0.069 | 0.094 | 0.173 | **162.9** |
| Explosive pass allowed | 0.002 | 0.003 | 0.006 | 0.009 | 0.012 | 0.018 | 0.025 | 0.049 | 665.7 |
| Sack rate per dropback | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | ∞ |

`DERIVED` — the direct answers.

- **A scheme adjustment is worth applying from about game 3.** By game 4 the observed
  value already carries 62% weight.
- **A pressure adjustment is worth applying from about game 8** (w = 0.515). Before
  game 4 it should carry no more than one third weight.
- **A takeaway adjustment is not worth applying inside a single season at more than
  half weight, ever**, and at week 4 it is 81% league average.
- **A pass-EPA-allowed adjustment is not worth applying at all from one season.**
  w = 0.094 at 17 games; the prior dominates by a factor of ten. Anyone who ranks
  pass defences by EPA allowed and adjusts a projection by the full spread is
  applying a correction that is 91% noise.
- **A sack-rate adjustment must not exist.**
- Two hard caveats: these weights use ρ₁ estimated **on 2024 alone**, and the
  bootstrap CIs in §2.1 mean the lower rows are compatible with w = 0 at every n. And
  Spearman-Brown assumes the games are exchangeable draws around a fixed team mean —
  which injuries and midseason personnel change violate, in the direction of making
  these weights **optimistic**. Nothing here justifies applying more shrinkage weight
  than the table shows; it may justify applying less.

---

## 7. Individual matchup — receiver against a specific defender (task item 6)

### 7.1 Is the assignment even recorded? No.

`VERIFIED` — `python3.12 w6/m18_wr.py` header inspection and
`head -1 pbp2024.csv | tr ',' '\n' | grep -iE "defend|coverage|assign|matchup|corner"`:

- `play_by_play` (372 columns) has `receiver_player_id` and `receiver_player_name`
  but **no coverage-defender column of any kind**. Grep matches only receiver and
  lateral-receiver fields. Tackler columns exist, and a tackler is not a coverage
  assignment.
- `pbp_participation` gives `defense_players` as an **unordered** `;`-delimited list
  of 11 gsis ids with a parallel `defense_positions` list (verified sample:
  `CB;CB;CB;DE;DE;DT;DT;FS;ILB;ILB;SS`). Who covered whom is not in it.
- `pfr_advstats_week_def_2024.csv` **does** carry per-defender coverage volume —
  `def_targets`, `def_completions_allowed`, `def_yards_allowed`,
  `def_passer_rating_allowed`, `def_adot` — but the grep for any receiver-identifying
  column returns `[]`. It is a defender-game aggregate with the receiver's identity
  already summed away.

`DERIVED` — **a receiver × defender pair is not identifiable from any feed reachable
in this container.** Not "hard"; not present. A "WR vs CB" feature could only be
fabricated by assuming an assignment rule (nearest CB, shadow, side-of-field), and
that assumption would be a silent constant of exactly the kind `CLAUDE.md` rule 3
logs as a bug.

### 7.2 Even the team-level version of the feature is near-empty

`VERIFIED` — `python3.12 w6/m18_wr.py`. Take every receiver-game, subtract the
receiver's own season mean, and ask how much of what is left the opposing defence
explains. 102 receivers with ≥10 games and ≥60 targets, 1,566 receiver-games. Placebo
= the same computation with defence labels shuffled, 300 replicates.

| Receiver-game outcome | Defence share of residual variance | Placebo mean | Placebo 95th pct | p |
|---|---|---|---|---|
| Receiving **yards** | 0.00658 | 0.00209 | 0.00960 | **0.113** |
| **Targets** | 0.01980 | 0.00199 | 0.00915 | **0.000** |
| Receiving **EPA** | 0.00216 | 0.00216 | 0.00959 | 0.327 |

`DERIVED`:

- **Receiving yards: the opposing defence explains 0.66% of the residual variance, and
  that is not distinguishable from a randomly assigned opponent (p = 0.113).**
- **Receiving EPA: 0.216%, identical to the placebo mean to three decimals
  (p = 0.327). Zero.**
- **Targets: 1.98%, real (p = 0.000) but tiny.** `UNVERIFIED-RECALL` for the
  mechanism — a plausible reading is game script, since trailing teams throw more and
  strong defences produce trailing opponents, which would make this a score-state
  effect wearing a defence's name rather than a coverage effect. That reading is not
  tested here and must not be asserted.

### 7.3 What *is* measurable about individual defenders

`VERIFIED` — `python3.12 w6/m19_pfrdef.py`, 167 defenders with ≥12 games and ≥40
targets, 2,501 player-games; and `w6/m23_yoy.py`, 77 defenders with ≥50 targets in
both 2023 and 2024:

| Defender quantity | ρ₁ | Reliability @16g | Placebo p | YoY 2023→2024 |
|---|---|---|---|---|
| `def_targets` (volume thrown at) | 0.1049 | **0.652** | 0.000 | **+0.638** |
| Completion % allowed | 0.0502 | 0.458 | 0.000 | +0.392 |
| `def_yards_allowed` | 0.0309 | 0.338 | — | — |
| Yards per target allowed | 0.0100 | 0.139 | — | — |

`VERIFIED` data-quality flag: in `advstats_week_def_2024.csv`, `def_yards_allowed` is
missing on **39.70%** of rows and `def_adot` on **33.02%**, while `def_targets`,
`def_completions_allowed`, `def_pressures` and `def_missed_tackles` are 0.0000
missing. `DERIVED` — any aggregation that sums `def_yards_allowed` across defenders
will silently under-count by roughly 40% and produce a plausible-looking wrong number.
That is Class A of the failure taxonomy, and it is a real trap sitting in a file this
project would otherwise treat as clean.

### 7.4 Verdict on the feature class, stated as asked

`DERIVED`. **The popular "receiver versus cornerback" feature class is closed off, and
should be recorded as REJECTED — SOURCE INSUFFICIENT so it is not re-proposed.** The
pairing is not in the data (§7.1); the team-level shadow of it explains under 1% of
receiver-game yardage and is indistinguishable from a shuffled opponent (§7.2). This
is the same disposition `v8/FEATURE_REGISTRY.md` gives to the MLB `umpire` field —
rejected because the source is empty, not because an experiment failed.

The salvageable residue is narrow and honest: individual defenders have a stable
*coverage volume* (targets/game reliability 0.652 within season, +0.638 across
seasons) and a weak but real completion-rate-allowed signal (0.458, +0.392). Both are
properties of a defender, not of a matchup, and their most defensible use is as
descriptive context — for instance, flagging that a defender who absorbed 8 targets
per game is inactive — rather than as a projection input.

---

## 8. Proposed defence layer, with per-component falsification experiments

`DERIVED` throughout. Statuses follow `v8/FEATURE_REGISTRY.md` Rule 024. **Everything
below is EXPERIMENTAL or lower.** Nothing measured in this pass earns SECONDARY, let
alone CORE, because stability is not usefulness (Rule 005) and 2024 is development
data (Rule 006).

### 8.1 Shape

Four tiers, ordered by measured reliability, each with an explicit shrinkage weight
taken from §6.4 rather than chosen:

- **Tier D1 — scheme priors (behaviour).** Man rate, Cover-1/2/3 shares, blitz rate;
  residualised on down, distance and score state; w from §6.4 (0.62 at 4 games).
- **Tier D2 — pass rush.** Pressure rate generated, opponent-adjusted, jointly fitted
  against offensive pressure-allowed; w = 0.35 at 4 games, 0.69 at 17. Sack rate is
  **not** an input.
- **Tier D3 — takeaways.** Composite takeaway rate only, never decomposed, w capped at
  0.50, reset each season.
- **Tier D4 — everything else, held at league mean.** Pass EPA allowed, explosive-pass
  allowed, points allowed per drive and INT rate enter as DESCRIPTIVE only, so they
  can be reported to a human without being able to move a projection.

Cross-cutting requirements: joint offence-defence estimation (§6.3.1); ratings built
only from weeks strictly before the projected week and content-hashed into the input
manifest (§6.3.2); market columns quarantined at ingest (§6.3.5); every rate declares
its denominator per Rule 019; every reported SE clusters on the **game**, since §2.4
shows play-level independence inflates apparent signal 2.5×.

### 8.2 Falsification experiments

Each states what would kill the component. All metrics, splits, clustering and
multiplicity correction are frozen before running, per Rule 004a. All use seasons
**other than 2024** for confirmation, since 2024 selected everything above — this
document is development data by construction (Rule 006).

| ID | Component | Question | Design | **Falsified if** |
|---|---|---|---|---|
| **D-1** | Whole layer | Does *any* defensive adjustment beat league-average? | Forward-chained weekly refit, 2022–2023 and 2025, CRPS and log score on full stored draws, clustered by game and by week | Adding the defence layer does not improve CRPS by more than its own bootstrap CI on ≥3 seasons |
| **D-2** | Pressure over outcomes | Does pressure rate predict next-window pass EPA allowed better than pass EPA does? | Same cross-half design as §5.2, pooled over ≥4 seasons (128+ team-seasons); paired bootstrap over team-seasons | P(|r_pressure| > |r_passEPA|) < 0.90 at the pooled sample. *(Currently 0.670 on 2024 alone — `DEFERRED / UNDERPOWERED`, not FAIL)* |
| **D-3** | Scheme, situationally adjusted | Does man/zone share survive residualising on down, distance and score state? | Refit man rate with situation controls, re-estimate ρ₁ | ρ₁ falls below 0.10 (reliability @17g < 0.65), i.e. most of the apparent tendency was game script |
| **D-4** | Scheme usefulness | Does knowing a defence's scheme improve any projection? | Add residualised scheme shares to a receiver-yards and a team-total model; nested comparison, clustered by game | No CRPS improvement outside its bootstrap CI. **This is the experiment that decides whether §4 is a finding or a curiosity** |
| **D-5** | Takeaways | Is the within-season takeaway component real across seasons? | Variance ratio with bootstrap CI on each of ≥4 seasons | The CI includes 1.00 in 2 or more seasons *(2024: [1.21, 2.68], excludes 1.00)* |
| **D-6** | Turnover decomposition | Are forced fumbles or recovery share ever a team skill? | Variance ratio per season, ≥4 seasons | Ratio ≤ 1.10 in ≥3 of 4 seasons ⇒ permanently REJECTED *(2024: 1.03 and 0.98)* |
| **D-7** | Opponent adjustment | Is the reliability gain real, or an artefact of the adjustment machinery? | LOO adjustment vs 300 shuffled-opponent placebos, per season, Holm correction across metrics | True adjustment inside the placebo 95% interval in ≥2 seasons *(2024: all-EPA p=0.0033 passes; pass-EPA p=0.040 is marginal and fails Holm)* |
| **D-8** | Rush-vs-protection matchup | Does the additive matchup term hold out of sample beyond 2024? | Repeat §5.4 on 2022, 2023, 2025; held-out weighted RMSE | def+off fails to beat league constant by ≥2% in ≥2 of 3 seasons *(2024: +3.43%)* |
| **D-9** | Individual matchup | Is anything about a specific defender projectable onto a specific receiver? | Receiver-game variance decomposition with shuffled-defence placebo, pooled ≥3 seasons | Already falsified for yards and EPA on 2024 (p = 0.113, 0.327). Run once more pooled; if it fails again, register **REJECTED — SOURCE INSUFFICIENT** permanently |
| **D-10** | Sack rate | Is there ever a team sack-conversion skill? | Pressure→sack conversion variance ratio, ≥4 seasons | Ratio ≤ 1.10 in ≥3 of 4 ⇒ permanently REJECTED *(2024: 0.75, below the chance floor)* |

`DERIVED` — the power constraint from `_GROUNDING.md` binds hardest here and should be
stated before anyone runs D-1. NFL supplies 272 games and 544 team-games per season.
Every confirmatory claim in this list needs multiple seasons, and D-2 in particular
needs four or more. A defence layer that shows no improvement on one season has not
been shown to be useless; under Constitution Rule 006a that is `DEFERRED`, and the
registry must say so rather than letting an underpowered null read as a negative.

---

## 9. Open items and what I could not do

`VERIFIED` / stated as gaps:

1. **Single season for the core stability table.** Every ρ₁ in §2.1 comes from 2024
   alone. The brief forbade downloading another season of pbp or participation, which
   was the right call for disk, but it means the ranking is a 2024 measurement, not a
   league property. The YoY work in §3 and §5.3 uses the small `pfr_advstats` files
   (73 KB – 924 KB) as a partial substitute, and PFR's pressure definition is not the
   same as participation's `was_pressure`; the two must not be pooled.
2. **The situational residualisation of scheme (§4.2) is not done.** Until D-3 runs,
   the raw man/zone rates in §4.1 should be read as *tendency plus game script*.
3. **Coverage-type effects on outcomes are unmeasured.** I established that coverage
   shares are stable and 99.77% populated on dropbacks; I did not measure whether
   facing Cover-1 versus Cover-3 changes anything. That is D-4.
4. **The pass-EPA opponent-adjustment gain (§6.2) is the weakest claim here** —
   p = 0.040 on a single test, would not survive multiplicity correction, and is the
   number most likely to be quoted out of context. It is flagged, not suppressed.
5. **`time_to_throw` is 11.87% missing on dropbacks** and I did not use it. Anyone
   who does must state that denominator; it is the one participation field in this
   scope whose missingness is neither negligible nor structurally explained.

---

## Appendix — reproduction

All inputs are in the shared session cache
`/tmp/claude-0/-home-user-mlb-prop-system-v7/8de98087-4781-5a10-ae09-ef74590f8116/scratchpad/`.
Scripts are in the `w6/` subdirectory of the same path. `m1` and `m4` must run first
(they build `w6/pbp_reg.pkl`, `w6/part.pkl` and `w6/merged.pkl`); the rest are
independent. `python3.12` throughout; `pandas 3.0.5`, `numpy 2.5.3`; `scipy` is **not**
installed in this container and no measurement here requires it.

| Script | Produces |
|---|---|
| `m1_load.py` | REG frame; row and game counts (§1) |
| `m2_teamgame.py` | Team-game defensive aggregates; drive-result mapping |
| `m3_part.py` | Participation column missingness over the whole file (§1) |
| `m4_join.py` | pbp × participation join; **missingness on the dropback denominator** (§1) |
| `m5_splithalf.py` | Odd/even split-half, all metrics (§2.1) |
| `m6_repsplit.py` | 500-replicate random split-half (§2.1) |
| `m7_check.py` | Odd/even at the 0.4th percentile of the random-split null (§2.3) |
| `m8_parity.py` | Home/away parity confound ruled out (§2.3) |
| `m9_jk.py` | Leave-one-defence-out jackknife (§2.3) |
| `m10_shrink.py` | ANOVA ρ₁ and Spearman-Brown reliability, all metrics (§2.1) |
| `m11_sack.py` | Sack/pressure structure; variance-vs-binomial ratios (§2.2) |
| `m12_oppadj.py` | Leave-one-out opponent adjustment (§6.2) |
| `m13_placebo.py` | Shuffled-opponent placebo (§6.2) |
| `m14_scheme.py` | Man/zone and coverage-type rates, stability, down confound (§4) |
| `m15_pressure.py` | Pressure→outcome; rushers sent; cross-half (§5.1) |
| `m16_matchup.py` | Held-out rush-vs-protection matchup model (§5.4) |
| `m18_wr.py` | Receiver-game variance decomposition with placebo (§7.2) |
| `m19_pfrdef.py` | `pfr_advstats` defender-level stability and missingness (§7.3) |
| `m20_cross.py` | Full 8×8 cross-half predictor matrix (§5.2) |
| `m21_to.py`, `m22_tocheck.py` | Turnover decomposition; recovery share; composite covariance (§3) |
| `m23_yoy.py` | Year-over-year 2022/2023/2024 from `pfr_advstats` (§3, §5.3) |
| `m24_sched.py` | Schedule-strength dispersion by week (§6.1) |
| `m25_table.py` | Shrinkage-weight table (§6.4) |
| `m26_effect.py`, `m27_effect2.py` | True between-team SDs; play-level vs game-clustered (§2.4) |
| `m28_paired.py` | Paired bootstrap over defences for the pressure-vs-EPA claim (§5.2) |
| `m29_boot.py` | Bootstrap CIs over the 32 defences for the headline table (§2.1) |

Files downloaded in this pass (small only, per the brief; no pbp/participation
re-download):
`advstats_week_{pass,rush,rec,def}_2024.csv`, `advstats_week_{def,pass}_{2022,2023}.csv`
from `https://github.com/nflverse/nflverse-data/releases/download/pfr_advstats/`.
`advstats_season_pass_2024.csv` and `advstats_season_def_2024.csv` return **404** —
`pfr_advstats` is weekly-only under those names.
