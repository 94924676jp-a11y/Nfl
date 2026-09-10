# PRE-REGISTRATION — the next three football-intelligence tracks

**Date** 2026-09-10 · **Status: REGISTERED, NOT STARTED.** No code for any of
these tracks exists, and none may be written before the owner authorises the
track. This document exists so the hypothesis, the metric and the falsification
condition are fixed before anyone looks at the data again.

**Priority rule, as directed.** Causal position, then reliable point-in-time
data, then measurable incremental value, then historical or prospective
validatability. Not sophistication. The standing order is: structural
accounting, appearance/role correctness, game state and pass/run behaviour,
conditional substitution, opponent defensive behaviour, line/front interaction,
red-zone and TD refinement, environment, and advanced matchup features only on
evidence. Tracks 1-3 below are items three and four of that list; items one and
two are what R2, R5, R6, R7 and R8 have been.

**Rules that bind all three.** Forward chaining by season, never a random split.
Clustering by game and by date, blocked bootstrap, with the equivalence margin
predeclared. Every constant estimated, never chosen. No sportsbook price as a
label, a target or an input. A rejected hypothesis is recorded as rejected in
`NFL_FEATURE_REGISTRY.md`, which is the point of writing this down first.

---

## TRACK 1 — Game-state-conditioned offence

### The question

Can **pregame-known** information improve the distribution of pass and run
volume beyond static team marginals?

### Why it is first

It is the highest node in the causal chain that is currently a constant. Team
volume is drawn once per team-game from `league_mean` / `coach_prior` / `ewma`,
with no opponent, no score, no clock. Every player projection is a share of it.
The engine cannot today produce the behaviour the owner named — the same team
throwing 43 times when trailing and 27 when leading — because it holds one
number, not a path.

### H1, stated before the data

**H1.** Conditioning team dropbacks and team carries on a *pregame-generated*
latent game-state path improves CRPS on both, and raises the spread of
conditional means relative to the spread of realised values, beyond the frozen
P4B estimator selection.

**H1a.** The improvement is concentrated in games whose pregame-expected script
is asymmetric, and is near zero in games expected to stay neutral.

### The structure, and the restriction that defines it

Game state is **generated inside the simulation**, never supplied from the
realised game:

1. a pregame distribution over score paths, built only from quantities knowable
   before kickoff;
2. leading / trailing / neutral play-calling responses estimated historically
   from `pbp`;
3. team volume drawn *along* the simulated path rather than once for the game.

**Forbidden as inputs, and this is the whole integrity of the track:** realised
score differential, realised win probability, `vegas_wp`, `spread_line`,
`total_line`, and every other market or outcome column already quarantined by
`nfl/ingest/allowlist.py`. The quarantine is enforced at ingest, so a violation
is a refusal rather than a review comment.

**The honest failure mode, named in advance.** If the only thing that predicts
game script is the market line, then we have no pregame script signal of our
own, and *that is the finding*. It must be reported as such rather than worked
around by admitting the line "just as a prior".

### Order of proof

Incremental value must be shown on the primitives **before** any player-level
claim:

| # | target | metric |
|---|---|---|
| 1 | team dropbacks | CRPS, and SD of conditional means / SD of realised |
| 2 | team carries | CRPS, same ratio |
| 3 | QB attempts | CRPS, calibration slope |
| 4 | tails | coverage at the 5th, 10th, 90th, 95th percentiles |

A gain on player projections with no gain on team dropbacks is not evidence for
H1; it is evidence that something else changed.

### Falsification

H1 is **rejected** if, on held-out seasons, CRPS on team dropbacks and team
carries does not improve with a game-and-date-blocked interval excluding zero,
or if the SD ratio of conditional means does not rise. H1a is rejected if the
improvement is statistically indistinguishable between expected-asymmetric and
expected-neutral games.

### Known hazards

* Pace and total plays are **already rejected** as team traits — plays per game
  ICC 0.000, drives per team-game split-half 0.001 (W5). A "volume" gain that
  turns out to be a play-count gain is measuring something the project has
  already refused.
* Simulating a path introduces many free choices. Every one is a constant that
  must be estimated from history and declared, or the track becomes tuning.

---

## TRACK 2 — Neutral pass-rate trait

### The question

Does a shrunk pregame neutral pass-rate prior improve the pass/run split beyond
`coach_prior`?

### Why it is second

It is nearly free and it is the cheapest possible test of whether the volume
layer can be improved at all. The quantity is already measured reliable —
split-half **0.532**, Spearman-Brown **0.695**, ICC 0.116 (W5) — the source is
reachable for every season, there is no licensing question, and it is used
**nowhere**. If a trait this reliable does not help, Track 1's far more
elaborate conditioning is much less likely to.

### H2, stated before the data

**H2.** A neutral-situation early-down pass rate, estimated from strictly prior
games and shrunk by `n/(n+k)` with `k` estimated from within/between team
variance, improves the pass/run split beyond `coach_prior`, and the improvement
survives conditioning on the same team's total volume.

### Targets, in order

1. the split itself, `team_dropbacks_part / team_off_snaps`;
2. QB attempts;
3. RB carries;
4. team-volume calibration.

Each is reported separately. A gain on QB attempts that is really a gain on
total plays is the confusion this track exists to avoid.

### The trap, named in advance

**Pass-rate predictability is not total-play predictability.** W5 found neutral
pass rate reliable at 0.532 and *plays per game* at ICC 0.000 in the same
analysis. The estimand is the RATIO. Any evaluation must hold total plays fixed
— by conditioning on them, or by reporting the split and the level separately —
so a level effect cannot be read as a split effect.

### Falsification

H2 is rejected if CRPS and calibration slope on the split do not improve on
held-out seasons with a blocked interval excluding zero. Rejection is recorded
in the feature registry beside the W5 measurement, so the next reader sees that
a reliable trait was tested and did not pay.

---

## TRACK 3 — Role-conditional substitution

### The question

When a player is absent, does his opportunity redistribute in proportion to the
survivors' overall shares, or preferentially to an adjacent role?

### Why it is third, and why it is newly possible

Current behaviour is **proportional renormalisation**: absence zeroes the weight
and the P4C simplex renormalises. Nothing models who inherits what. The cost is
already quantified — the participation control's residual sits in role
transitions, R² 0.753 for stable roles against **0.496 / 0.498** for roles
moving up or down, with lag bias −0.027 rising and +0.038 falling
(`GAP-PREGAME-ROLE`).

It is newly testable because **R7's union frame is the first population in this
project that contains players who were available and did not play.** Naive
next-man-up cannot be tested against a frame that holds only people who played.

### H3, stated before the data

**H3.** Vacated targets and carries redistribute preferentially to players
occupying an adjacent point-in-time depth role, and modelling that adjacency
improves projections for the inheriting players beyond proportional
renormalisation.

Three nested alternatives, tested in this order so a positive result names its
own mechanism:

1. **adjacent depth role** — the vacancy flows to the next rank at the same
   position;
2. **historical substitution relationship** — a fitted player-pair or
   role-pair propensity;
3. **archetype similarity** — position-and-usage similarity rather than rank.

### Primary targets

WR target redistribution · RB carry and target redistribution · TE role
redistribution.

### Predeclared design

Absence events identified on the union frame. Adjacency taken from the
**point-in-time depth chart**, never from realised outcomes. The counterfactual
is the engine's current proportional renormalisation, computed on the same
draws. Clustering by team-game — the players in one game are emphatically not
independent observations, and this is the setting where that bites hardest.

### Falsification, and why a null here is worth having

**Do not assume next-man-up wins.** If realised redistribution is
statistically indistinguishable from proportional renormalisation, the engine's
current behaviour is **vindicated**, `GAP-PREGAME-ROLE`'s substitution half
closes, and an assumed defect leaves the register. That is a result, not a
failed track, and it must be reported with the same prominence as a positive
one.

---

## What is NOT in these tracks

Named so scope creep is visible if it happens: opponent defensive behaviour,
offensive-line and defensive-front interaction, red-zone and TD refinement,
environment and context, and advanced matchup features. They sit below these
three in the standing order and stay there until these are resolved.
