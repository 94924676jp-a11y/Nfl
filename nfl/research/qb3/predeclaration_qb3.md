# QB3 pre-registration — the QB dropback allocation layer

Written 2026-09-09, **before any estimator was built, run or scored**. Start
HEAD `a955498`. Departures are labelled where they occur.

Owner ruling of 2026-09-09 directs this work: *"Do not assume 'pick the starter'
is sufficient. Determine the actual production quantity the simulator needs, how
it should behave for normal starters, genuine QB committees, injury uncertainty,
midgame replacement, and multi-QB packages while preserving same-draw team
accounting."*

## 1. The defect this addresses

Measured in R4 on the real 2026 week-1 roster, 32 teams × 200 draws:

| | |
|---|---|
| D1 team dropbacks | 36.75 |
| QB-summed dropbacks | **79.76** — ratio **2.17** |
| cells where a team's QBs collectively out-drop their own team | 5,930 of 6,400 (92.7%) |
| QB rows per team | 2.62 |

The QB layer models a passer's line **conditional on being the team's primary
passer**, and nothing selects which of the room that is. The engine currently
forecasts 2.62 starters per team.

## 2. The estimand, and why it is not "pick the starter"

The production quantity is **`s_dropbacks`: a quarterback's share of his team's
dropbacks in a game** — the same object `s_targets` and `s_carries` already are
for skill players. `W2_QB_PASSING.md` §7.2 names it, gives its denominator, and
records it as *not measured here*. It was specified and never built.

It is a **distribution on a simplex, not a pick**. Measured on `panel_p3`,
2020–2025, 3,230 team-games:

| | |
|---|---|
| team-games with exactly one QB taking a dropback | 2,710 (83.9%) |
| with two | 512 | with three | 8 |
| share exactly 1.0 | 72.1% of QB-games |
| share ≤ 0.05 | 3.9% |
| second QB's share when there is one, median | 0.125 |

And the decisive fact against a point forecast: taking last game's primary and
assigning him 1.0 would have **mean absolute error 0.155** and would assign
**probability zero to the 11.9% of games in which he takes no snap at all**.

## 3. Pregame inputs — declared now, both verified available for 2026

**A. Depth-chart QB rank.** Captured for 2026 at `2026-09-08T11:56:57Z`, all 32
teams, exactly one rank-1 QB per team, with `gsis_id`. The capture precedes the
earliest week-1 game (2026-09-09).

**B. Last game's primary passer**, from panel history, strictly earlier ordinal.

### 3a. The leakage probe on input A, run BEFORE the design was fixed

Depth charts are a lagging-file risk: the week *w* file could be a post-hoc
reflection of who actually played, as the injuries file is known to be for
in-week revisions. Probed three ways:

| probe | result | reading |
|---|---|---|
| week *w−1* chart predicts week *w* primary | 0.8151 | — |
| week *w* chart | 0.8551 | — |
| week *w+1* chart | 0.9067 | expected: it is published after the game |
| **week *w* chart on PLANNED primary changes** (n=324) | **0.3765** | a post-hoc file would be ≈1.0 |
| **week *w* chart on MIDGAME replacements** (n=45) | **0.0889** | nobody could know this pregame, and the chart does not |

**The week *w* chart is genuinely pregame.** It is bad at anticipating change,
which is what an honest pregame source looks like. `w+1 > w` is not leakage; it
is next week's chart knowing what happened.

Incidental finding, recorded: `stage_a.build` computes `f_depth` and **no
feature vector consumes it** — neither `stage_a.featurise` nor
`p3_features.featurise_p3` references it. It is dead data in the appearance
model, so there is no existing production exposure to depth charts either way.

## 4. The cells, fixed now

Two pregame variables, both declared by football logic before any evaluation:

- `rank` ∈ {1, 2, 3+} from the depth chart
- `was_prev_primary` ∈ {yes, no}

**Rank 3+ and rank 2 are POOLED when `was_prev_primary` is yes**, because the
rank-3/yes cell holds n=33. The pooling is declared here, before scoring, and is
justified on sample size rather than on the two cells having similar rates.

No other feature enters. In particular: **no injury designation**, so this layer
is NOT blocked on `injuries_2026`; no market data; no 2026 outcome.

## 5. The mechanism

Per team, per draw *j*:

1. Draw the **primary passer identity** from the cell probabilities, normalised
   across that team's charted quarterbacks.
2. Draw **his share** by RESAMPLING the empirical conditional share distribution
   of his cell. Never a point estimate — that is the defect class this project
   has hit four times.
3. Allocate the **remainder** among the team's other quarterbacks in proportion
   to their cell probabilities.

Closure is by construction: the shares sum to 1 in every draw, so team dropbacks
are exactly allocated and the R4 accounting identity
`qb_dropback_within_team_volume` holds by design rather than by clipping.

This mechanism is required to reproduce, without any special-casing:

| case | how it arises |
|---|---|
| normal starter | rank 1 / yes: share resampled from a distribution that is 1.0 in 77.7% of its mass |
| injury / benching | the same cell has 7.4% mass at exactly 0 |
| genuine committee | steps 2–3 leave a remainder for the other QBs |
| midgame replacement | the primary's drawn share is partial, the rest goes to the room |
| multi-QB package | the backup's cell carries small non-zero mass |

## 6. Baselines it must beat, declared now

- **B0 — the incumbent**: last game's primary gets 1.0, everyone else 0.
- **B1 — depth chart**: rank-1 QB gets 1.0, everyone else 0.
- **B2 — current production**: every rostered QB gets 1.0. This is the status
  quo and is included so the size of the existing defect is scored, not merely
  described.

## 7. Scoring, fixed now

Walk-forward. For evaluation season *Y*, every rate is estimated on seasons
`< Y` only, and the previous-primary feature uses a strictly-earlier ordinal
prefix cut. Evaluation seasons: **2022, 2023, 2024, 2025**.

Primary metric: **CRPS of the predicted share distribution against the realised
share**, per QB-game, pooled. Reported alongside: Brier score on
`is_primary`, mean absolute share error, and the **team-closure violation rate**
(fraction of draws where the team's QB shares do not sum to 1).

Uncertainty: **team-game clustered bootstrap**, because the quarterbacks of one
team-game are one observation, not several. A naive interval is not reported.

**Selection rule, fixed before any result:** the layer is preferred over B0 and
B1 only if pooled CRPS improves **and** the team-game clustered interval on the
CRPS difference excludes zero **and** the direction is consistent in at least
3 of the 4 evaluation seasons.

## 8. What a negative result would say

Stated now, in the words the return will use if they apply:

- If the allocation does not beat B0 on CRPS, the return says **the incumbent
  point forecast is not beaten**, and the layer is still adopted for the
  *closure* property alone if and only if that is stated separately as an
  accounting fix rather than a forecasting improvement.
- If the 11.9% zero-share event cannot be predicted better than its base rate,
  the return says **the timing of quarterback changes is not forecastable from
  these two inputs**, and names what would be.

## 9. Governance

This is a **new component**. It is not promoted by this work and
`PATH_C_STATE` is not edited. `td_red_zone`, `appearance`, `team_volume` and
every other subsystem state is untouched. The evaluation seasons 2022–2025 are
development data and any result on them is EXPLORATORY.
