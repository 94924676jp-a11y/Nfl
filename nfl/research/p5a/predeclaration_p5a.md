# P5A pre-declaration — carry → rushing yards: skill vs context vs noise

Written 2026-09-07. HEAD at task start `74e327d`.

Written **before** any carry-level distribution was inspected, any efficiency
signal was fitted, any CRPS, coverage, threshold or tail number existed. The
only thing run before this file was the extraction of the carry table itself
(a filter, not a result). Departures are labelled where they occur.

## 1. Estimand

For player *i* in team-game *g*:

```
rushing_yards_i  =  sum over the player's carries of the per-carry yardage
carries_i        =  A_i * T_g * S_i     (the ACCEPTED P4C joint allocation)
```

The forecast object is the **predictive distribution of rushing yards**. It is
built as a compound: draw the carry count from the accepted architecture, then
draw that many per-carry outcomes from a conversion distribution.

**Not modelled, at all:** fantasy points, receiving, receptions, receiving
yards, passing, touchdowns. **Yards per carry is not the forecasting target** —
it appears only as a candidate predictor and as a diagnostic.

## 2. Carry definition — must match P4C exactly or nothing composes

`rush_attempt == 1`, non-empty `rusher_player_id`, `season_type == REG`,
two-point attempts excluded, **scrambles included** (P1 measured that
`passer_player_id` is NULL on all 1,134 qb_scramble plays of 2024 while
`rusher_player_id` is set on 1,062). The carry table must aggregate to the
panel's `y_carries` **exactly**, and that is checked rather than assumed. If it
does not, P5A stops and reports the mismatch.

## 3. Chronology

Strict walk-forward. For evaluation season *Y*: every parameter — pooled
conversion distributions, shrinkage constants, context coefficients, opponent
adjustments, mixture components — is fitted on seasons `< Y`. Within-season
player, team and opponent histories use **games strictly before the target
game**. No same-game value of any kind. No future season. No 2026 outcome.

Carry-level history may reach back to **2016** (pbp availability) even though
the opportunity panel starts in 2020: earlier carries are strictly prior
information and using them is chronology-safe.

All existing quarantines carry over: no market data, no observed weather, no
`weekly_rosters.status`, no `xpass`/`pass_oe`, **no Grade-B ESPN/Wayback
material**, **and the 2025 nflverse injury final file is not used as historical
point-in-time evidence** (R9 owner ruling).

## 4. Definitions fixed now, before any distribution was looked at

- **Explosive run: `yards_gained >= 10`.** Secondary definition 15+, reported
  alongside but never substituted. **The cutoff is not tuned on any season.**
- **Stuff / non-positive run: `yards_gained <= 0`.**
- **Rushing-yard threshold grid: 9.5, 19.5, 39.5, 59.5, 79.5, 99.5.** Evenly
  spaced round numbers spanning the range of a player-game rushing total. **No
  sportsbook price was consulted and none exists in this repository.**

## 5. Control — deliberately simple, and not weakened

**A — opportunity-only pooled conversion.** Carries from the accepted P4C
joint allocation (system C, reserved stochastic mass) with the accepted
incumbent appearance model. Conversion draws per-carry yardage from a **pooled
league distribution estimated on prior seasons**, stratified only by what the
directive allows as basic eligible stratification: **position group**
(RB versus non-RB rusher). No player-specific efficiency information of any
kind.

Every richer system must beat this. It is estimated on the full prior-season
carry population, not a crippled subsample.

## 6. Candidate ladder — one information class per rung

| id | adds |
|---|---|
| **A** | control: pooled per-carry conversion |
| **B** | **player** historical rushing efficiency, shrunk |
| **C** | **team / offence / run-environment** context |
| **D** | **opponent** defensive rushing context |
| **E** | combined — **only** components that individually survived |
| **O\*** | oracles, diagnostic only, never eligible |

**Nothing is presumed predictive.** A rung that does not beat the rung below it
on chronology-safe out-of-sample CRPS is reported as not earning inclusion, and
is excluded from E.

### Player signals to test (B)

Yards per attempt; rushing EPA per attempt; success rate; explosive-run rate;
stuff rate; and — where the data exists — yards after contact per attempt,
yards before contact per attempt, and broken tackles per attempt.

### Context signals to test (C)

Team rushing yards per attempt and rushing EPA per attempt from prior games;
team explosive-run rate; team stuff rate; shotgun-run share; QB rushing share
of team carries; team pass rate (P4's accepted environment quantity).
**Offensive-line continuity is tested only if a chronology-safe source exists
in this repository** — §7.

### Opponent signals to test (D)

Opponent rushing yards allowed per attempt; opponent rushing EPA allowed per
attempt; opponent explosive-run rate allowed; opponent stuff rate.
**P4 found naive opponent adjustment can add noise. It is not assumed to help.**

## 7. Data availability is audited before anything is claimed

Return item 7 is a first-class deliverable. In particular, R6's yards-after-
contact and broken-tackle hypotheses depend on PFR advanced weekly rushing
data, and **what this checkout holds must be stated exactly** — including if
that means those hypotheses can only be tested on a single season, or not at
all. A hypothesis that cannot be tested is reported as untested, never as
rejected and never as supported.

## 8. Shrinkage — asked of every player signal

For each candidate: (1) raw prior value; (2) recency-weighted (EWMA); (3)
empirical-Bayes shrinkage toward the pooled prior with the shrinkage constant
**fitted on prior seasons only**; (4) the pooled prior itself. The question
asked of each is the same and it is asked out of sample:

> Does the player-specific estimate beat the pooled prior on the **next game's**
> rushing outcome?

If not, it shrinks harder or it is discarded. **Self-correlation is not
predictive value** and persistence is reported separately from incremental
next-game value.

## 9. Unit of analysis and distribution family

Modelling is **carry-level**, not a game-level Gaussian. The predictive
distribution for a player-game is the sum of a drawn number of per-carry
outcomes, so non-positive runs, ordinary runs and explosive runs stay
distinguishable by construction.

**Families to test, none hard-coded:** empirical resampling of prior-season
per-carry yardage; a discrete binned empirical distribution; a two-component
**body + explosive-tail mixture**; and a three-component
**stuff / body / explosive** mixture. Gaussian, gamma, negative binomial,
skew-t and Pareto are **not** assumed because external literature used them —
R7 found no public NFL literature strong enough to establish a family. The
family is chosen by CRPS on an **inner validation season** (`Y−1`) fitted on
seasons before that, the P4B/P4C/P4D nesting, unchanged.

## 10. Explosive-run component

Tested explicitly as a separate question: does forecasting the probability and
the size of explosive runs separately improve CRPS, tail calibration and
rushing-yard threshold calibration over one homogeneous per-carry distribution?
The 10-yard cutoff is fixed in §4 and is not revisited.

## 11. Joint preservation

**The carry distribution is preserved, never replaced by realised carries.**
Within each team-game every player's rushing-yard draws come from the **same**
accepted joint opportunity realisation — draw column *j* is the same simulated
game for every teammate, exactly as in P4B/P4C. Draw-level identity is
preserved so a later J0 could consume it. **This is not J0 and no joint game
simulator is built.**

## 12. Oracles — diagnostic only

Realised carries; realised per-carry efficiency; realised explosive-run
occurrence; realised opponent/team context. Each is computed **after** selection
has happened, none is in the eligible tuple, and a guard-deletion proof shows
the eligibility filter is what stops them.

## 13. Metrics

MAE, RMSE, r, R², bias, CRPS, discretised log score, coverage at 50/80/90/95,
mean interval width, randomised PIT (the predictive has an atom at zero), and
exceedance calibration on the §4 grid. Conditional on: position, carry-volume
tier, prior-history depth, role stable/change, appearance-information quality,
team, season, high/low efficiency history, and opponent-quality tier **if**
opponent signals survive.

**Tail calibration is reported separately and is not allowed to hide behind a
good mean MAE**: upper-tail coverage, forecast versus observed probability of a
20+ yard rush, upper quantiles of the game rushing total, and whether player
identity or team context contributes anything to tail probability.

## 14. Selection rule, fixed before any result

A rung is promoted over the rung below only if:

1. pooled CRPS improves, **and**
2. the team-game block-bootstrap interval on the CRPS difference excludes zero,
   **and**
3. the direction is consistent in at least **3 of the 4** evaluation seasons,
   **and**
4. randomised PIT does not worsen by more than 25% relative, **and**
5. tail calibration — forecast minus observed P(20+ yard rush) — does not
   worsen in absolute value.

**CRPS decides; coverage never selects alone.** If no rung clears the bar over
the control, the return says the opportunity-only control is not beaten and
names what would be needed.

## 15. What would count as a negative result

Stated now, in the words the return will use if they apply:

- If no player efficiency signal beats a pooled prior out of sample, the return
  says **rushing efficiency contains no reproducible next-game player
  information at this sample size**, and reports the shrinkage that survives.
- If R6's missed-tackle or yards-after-contact hypotheses cannot be tested on
  the data in this checkout, the return says **untested**, and says exactly what
  would be needed. It does not report them as confirmed or rejected.
- If a separate explosive component does not improve CRPS or tail calibration,
  the return says the homogeneous per-carry distribution is sufficient.
- If the resulting rushing-yard distribution fails randomised PIT, the return
  says it is **not sufficiently calibrated to move forward**, whatever its CRPS.
