# #99 — where the between-player variance goes

**Status: MEASURED. No production change is made by this work.** The projection system stays
`NOT_VALIDATED`. One arm is recommended for adoption on a separate commit; the recommendation is at
the end and it is a recommendation, not an adoption.

Run it with `python3.12 nfl/research/shrinkage/study.py`. Artifact:
`nfl/research/shrinkage/SHRINKAGE_STUDY.json`.

## The question, and why the repository could not already answer it

V1's projected means separate players far less than realised points do. The hypothesis was that the
hierarchical prior causes it by shrinking players toward broad positional and depth shapes.

`proj_v1.PRIOR_WEIGHT_CAP` had already been swept over {0, 2, 4, 8, 12, 24}, and rank correlation
came out highest at a cap of **0** — no prior at all — falling as prior weight rose. That looks like
a complete answer and it is not one, because the cap is a single scalar applied to a prior that is
two different objects:

- a **player-own** prior is built from that player's own games, so every player gets a different
  value;
- a **cohort** prior — `ROLE_GROUP`, `ARCHETYPE`, `TEAM_CONTEXT`, `POSITIONAL_BROAD` — is a pooled
  average over *other* players, so everyone in the cohort gets **the same value**.

Setting the cap to 0 switches off both at once. The sweep therefore could not tell "his own history
does not help" apart from "a constant shared with forty-five other players actively hurts", and
those two call for opposite repairs.

## How bad the collapse is, measured on the live Week 3 slate

63.5% of the 439 skill players on the slate receive a cohort prior. Within a tier, the number of
*distinct* prior values is the number of cohorts, not the number of players:

| position | tier | players | distinct prior values | collapse | prior's share of the blend |
|---|---|---|---|---|---|
| TE | ARCHETYPE | 46 | **1** | 98% | 0.964 |
| QB | ARCHETYPE | 35 | 2 | 94% | 0.990 |
| WR | ARCHETYPE | 17 | **1** | 94% | 0.951 |
| WR | ROLE_GROUP | 99 | 29 | 71% | 0.865 |
| RB | ROLE_GROUP | 62 | 33 | 47% | 0.868 |
| TE | ROLE_GROUP | 20 | 17 | 15% | 0.792 |
| WR | PLAYER_OWN_ROLE | 34 | 34 | 0% | 0.510 |
| RB | PLAYER_OWN_ROLE | 24 | 24 | 0% | 0.604 |

Forty-six tight ends hold one prior value between them, and that value takes 96% of their blend. The
ordering is backwards: **the least player-specific evidence carries the most weight.** The cap is
what does it. A cohort's effective observation count runs from 22 to 1,110 and a player's own runs
1.5 to 27, so `min(n, 2.0)` pins essentially all of both at 2.0 and erases the hierarchy's own
ordering at the moment it is applied.

## The experiment

The cap was made per-tier — defaulting to exactly the single-cap behaviour, verified by a no-op
parity check that fails the run if a per-tier cap set to production's value changes any projection —
and own-history and cohort weight were varied separately. Forward-chained, every input strictly
earlier than the scored week. Primary outcome preregistered as **within-slate-week Spearman rank
correlation** with a **week-blocked** standard error, because games in a week are not independent.

| arm | own cap | cohort cap | ρ selection | ρ confirmation | MAE sel | level sel | separation |
|---|---|---|---|---|---|---|---|
| OWN_OFF_COHORT_OFF | 0 | 0 | **0.4671** | 0.4456 | **4.846** | 1.0185 | 9.21 |
| OWN_ON_COHORT_OFF | 2 | 0 | 0.4586 | 0.4428 | 4.902 | **1.0048** | 8.08 |
| OWN_HIGH_COHORT_OFF | 8 | 0 | 0.4540 | 0.4413 | 4.913 | 1.0154 | 7.82 |
| OWN_ON_COHORT_LOW | 2 | 0.5 | 0.4524 | 0.4322 | 4.921 | 1.0031 | 7.76 |
| COHORT_ONLY | 0 | 2 | 0.4489 | 0.4173 | 4.893 | 1.0246 | 8.23 |
| **PRODUCTION** | 2 | 2 | **0.4417** | **0.4173** | 4.943 | 1.0098 | **7.32** |

Production is last on rank correlation on both splits, and every alternative beats it.

## What the decomposition says, and it is clean

Paired, week-blocked, against production, on the confirmation season:

| contrast | what it isolates | Δρ | z |
|---|---|---|---|
| COHORT_ONLY − PRODUCTION | turning the **own-history** prior off | **+0.0000** | 0.02 |
| OWN_ON_COHORT_OFF − PRODUCTION | turning the **cohort** prior off | **+0.0256** | 18.0 |
| OWN_OFF_COHORT_OFF − PRODUCTION | turning both off | +0.0284 | 16.2 |

**Essentially all of production's ranking loss is the cohort prior.** Removing the player's own
history changes nothing measurable; removing the cohort constant recovers the whole effect.

That is the owner's hypothesis — *"shrink much less toward broad positional/depth shapes"* — and on
this data it holds. The other half of the hypothesis, that a player's own history is worth keeping to
stabilise his level, is **not resolved**: keeping it costs 0.003 ρ and buys 0.005 of calibration
level on selection while losing 0.001 on confirmation. Those are too small to call, and this study
should not be quoted as having settled it either way.

The gain also lands where the collapse was. Within-slice rank correlation, production → cohort-off:
PRIMARY 0.443 → 0.481, ROTATIONAL 0.389 → 0.433, FRINGE 0.312 → 0.348, ALPHA 0.420 → 0.421. The
players whose priors were cohort constants are the players who improve; the alphas, who mostly held
their own priors already, do not move.

## Two things that are NOT true, including one this study was set up to find

**The prior is not the dominant cause of the compression.** Top-decile-to-median separation is 7.32
in production against 15.33 realised. Removing the prior entirely takes it to 9.21 — about a quarter
of the gap. Three quarters of the missing separation is somewhere else and this study does not say
where. Cross-sectional SD ratio tells the same story more mildly: 0.795 in production against 0.825
with no prior.

**The compression is not uniform, and it is mildest where DFS money is.** Predicted-to-realised SD
ratio by pregame role band: SECONDARY 0.737, PRIMARY 0.725, ALPHA 0.706, FRINGE 0.457,
ROTATIONAL 0.377. The worst compression is among low-role players, who matter least to a lineup.

## Two defects found in the existing constant's justification

`PRIOR_WEIGHT_CAP = 2.0` is recorded as *"SELECTED on out-of-sample skill over 42 weeks and
CONFIRMED on 28 untouched weeks."* Both parts have a problem.

**1. It was selected on differences far below their own noise.** The recorded sweep chose 2 over 0
on MAE 5.410 vs 5.428 and top-30 realised points 18.651 vs 18.645 — margins of 0.018 and 0.006. The
week-blocked standard errors of those same statistics, measured here, are **0.106 and 0.50**. The
margins are about one sixth and one eightieth of one standard error. It paid 0.0049 ρ for them, and
ρ differences of that size are the ones that reproduce (z of 16 to 18 here). A constant chosen on
noise, against a cost that is not noise.

**2. Half of the confirmation set could not respond to the treatment.** The usage panel begins in
2021, so a 2021 forecast reads `through_season = 2020`, which holds nothing. Every prior comes back
`PRIOR_UNAVAILABLE` and **0 of 2,698 projections in 2021 differ between any two arms** — against
3,617 of 3,627 in 2022. The "28 untouched weeks" that confirmed the cap are 14 weeks of evidence and
14 weeks that were identical by construction, which halves any difference toward zero before it is
read. That is why the sweep saw a near-tie.

This does not show the constant is wrong. It shows the evidence recorded for it does not support it,
which under this project's rules is the same class of finding as a fitted constant — and it is
logged as one rather than quietly re-tuned.

2021 was preregistered here as a confirmation season and has been **voided** for the same reason,
which is recorded in the artifact rather than done silently.

## Limits, stated before the recommendation

- **The worst tier is untested.** `ARCHETYPE` — the 46-tight-ends-one-value tier — barely fires in
  the forward chain, because a forward-chained season builds priors from a complete previous season
  while Week 3 of 2026 is three games into a thin live panel. The arm differences above are a
  **lower bound** on what the same change does to the live slate. That is a reason not to
  extrapolate, not a licence to assume the effect is bigger.
- **Confirmation is one season, 14 weeks,** and it had already been read once for this constant. It
  is not an untouched holdout. Six arms were compared with no multiplicity correction; the z values
  are descriptive.
- **Salary slices are unavailable** — no historical DraftKings salaries exist in this checkout — so
  "DFS-relevant" is a pregame role-band proxy, chosen because conditioning the slice on the
  projection would restrict range on the predictor and conditioning it on realised points would
  define the slice by the thing being scored.
- The prior-weight-versus-rank-error table is **observational and confounded**: a player gets a high
  prior weight *because* he has little current-season evidence, and that is a different kind of
  player. The arms are the experiment; that table is a description.
- Season phase is reported as a continuous week-index series and **no early/mid/late boundary is
  drawn**. The one real feature in it is week 18, where ρ falls from ~0.45 to 0.251 as starters sit.
  Mean prior weight falls monotonically 0.42 at week 5 to 0.23 at week 18, and ρ does not track it.

## Recommendation, for a separate commit

Set the cohort tiers' cap to **0** and leave the player-own tiers at 2. Concretely
`PRIOR_WEIGHT_CAP_BY_TIER = {'ROLE_GROUP': 0.0, 'ARCHETYPE': 0.0, 'TEAM_CONTEXT': 0.0,
'POSITIONAL_BROAD': 0.0}`.

A cap of 0 does **not** discard the cohort prior. `_combine` returns the prior unchanged when the
current season is silent, whatever the cap, so a cohort prior still supplies a number for a player
with no current-season evidence; the cap only stops it outvoting evidence that exists.

That is verbatim what the note above `PRIOR_WEIGHT_CAP` already concluded:

> the multi-season prior earns its place as a FALLBACK WHERE THE CURRENT SEASON IS SILENT, not as a
> shrinkage target for evidence that exists.

The note reached the right finding and then implemented it as a single global cap, which cannot
express it. A per-tier cap can. **The finding was already in the codebase; what was missing was a
mechanism able to obey it.**

Adoption is a separate decision on a separate commit, with the baseline snapshotted first, and it
does not move the projection system off `NOT_VALIDATED`.
