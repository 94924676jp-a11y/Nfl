# Shortest sound path from `9d7947e` to Week-3 player distributions

Written 2026-09-27. Answers items 8A–8G of the owner's request with measured field
coverage rather than recollection. Every count below was read out of
`DK_WEEK3_TODAY_STATE_POST_INACTIVES.json` at this commit.

## The headline, because it changes the plan

**Routes are not required for an initial governed projection, and the one 404 feed is
blocking far less than the pipeline's refusal implies.**

`pbp_participation_2026` supplies exactly one thing: **true route participation**, i.e.
how many pass plays a receiver actually ran a route on. Everything else the first
projection stage needs is already in the tree, measured, from weeks 1–2 play-by-play and
snap counts. The pipeline currently refuses the whole slate because the *accepted arm* of
`participation_prior` was specified to consume that feed — a specification choice, not a
data impossibility.

That distinction is the difference between "blocked until nflverse publishes" and "a
declared arm needs a second arm".

## D — what weeks 1–2 already supports, measured

518 player-weeks, of which 482 carry both a play-by-play and a snap row.

| quantity | field | player-weeks carrying it | state |
|---|---|--:|---|
| team plays | `team_plays` | 481 | **READY** |
| team dropbacks | `team_dropbacks` | 481 | **READY** |
| team rush attempts | `team_carries` | 481 | **READY** |
| team targets | `team_targets` | 481 | **READY** |
| offensive snaps / share | `offense_snaps`, `offense_pct` | 481 | **READY** |
| targets, target share | `targets`, `target_share` | 286 / 285 | **READY** |
| carries, rush share | `carries`, `rush_share` | 142 | **READY** |
| receptions | `receptions` | 257 | **READY** |
| air yards | `air_yards` | 279 | **READY** |
| red-zone opportunities | `rz_opportunities` | 353 | **READY** |
| goal-line opportunities | `gl_opportunities` | 353 | **READY** |
| red-zone carries / targets | `rz_carries`, `rz_targets` | 72 / 97 | **READY** |
| goal-line carries / targets | `gl_carries`, `gl_targets` | 31 / 30 | **READY** |
| QB pass attempts | `pass_attempts` | 43 | **READY** |
| QB dropbacks | `dropbacks` | 43 | **READY** |
| completions | `completions` | 40 | **READY** |
| passing / rushing / receiving TD | `passing_td`, `rushing_td`, `receiving_td` | 30 / 24 / 43 | **READY** |
| passing, rushing, receiving yards | `passing_yards`, `rushing_yards`, `receiving_yards` | 39 / 140 / 255 | **READY** |
| **routes, route participation** | — | **0** | **BLOCKED, 404** |

A low count is not a gap: only quarterbacks have `pass_attempts`, only ball-carriers have
`carries`. The count is the population that legitimately has the field.

## C — are routes genuinely required? No, and here is the honest substitute

Routes matter because target share conditioned on routes run is a much better opportunity
signal than target share conditioned on team pass attempts. Without them the choice is:

1. **Infer routes from pass snaps.** Forbidden, repeatedly, and rightly — a blocking tight
   end and a slot receiver have similar pass snaps and completely different route counts.
2. **Estimate routes with a model.** That invents the missing field with extra steps and
   would be logged as a fitted constant.
3. **Condition opportunity on what we measured, and widen the interval to cover the
   uncertainty routes would have resolved.** This is honest, and it is the only one of the
   three that does not fabricate.

Option 3 is the recommendation. It means a target-share prior built on **observed snap
share and observed team pass volume**, with an explicitly wider dispersion for players
whose route role is unverifiable — and that widening declared in advance, not tuned. The
cost is real: less discrimination among same-snap-share receivers. The cost is also
*stated*, which is what makes it publishable.

## A — buildable immediately, with nothing new from outside

- **Team volume** — plays, dropbacks, rush attempts, targets, all measured for 18 clubs
  over two weeks, plus the market's spread and total for game-script conditioning.
- **Opportunity shares** — target share, rush share, red-zone and goal-line share, all
  measured.
- **Red-zone and goal-line allocation** — measured at the opportunity level, which is the
  right level; converting to touchdowns is an efficiency question, not an opportunity one.
- **Post-inactives redistribution as a distribution** — the 13 trees already exist with
  ranked candidates and unresolved inheritance. That is exactly the shape a prior wants.
- **Cold-start pathway** — 53 players have no prior history and 19 were materially active.
  The observed layer already gives them a current-season role, which is a better cold-start
  input than any historical prior would have been.

## B — genuinely requires the unavailable feed

Only **true route participation**, and therefore only the *accepted* `ewma_hl2` arm of
`participation_prior` as specified. Nothing else in the chain names it.

## E — missing for efficiency projections

Two games is the binding constraint, not a missing field. Yards per target, yards per
carry and touchdown rate over 2 games are dominated by noise. The fix is not a feed; it is
shrinkage toward a multi-season prior with the shrinkage weight declared in advance. The
historical panel for that already exists.

## F — missing for team-volume projections

Nothing structural. Two weeks of pace is a small sample and the second-pass research says
so itself. Needs opponent adjustment and game-script conditioning, both buildable from
held data plus the market.

## G — missing for joint simulation

The most, and it is the real gap. A joint simulator needs shared latent game state — plays,
drives, script, pass rate by state — with player opportunity reconciling *inside* each
draw so targets cannot exceed attempts and touchdowns cannot exceed team scoring. None of
that machinery exists. This is where the work is, and it is weeks, not hours.

## The dependency graph, with each arrow's real state

```
CURRENT DATA (weeks 1-2 pbp + snaps + market + post-inactives state)
    |  READY      measured, 482 of 518 player-weeks dual-sourced
    v
TEAM VOLUME (plays, dropbacks, rush att, targets)
    |  PARTIAL    computable now; needs opponent adjustment + script conditioning
    v
OPPORTUNITY DISTRIBUTION (target share, rush share, rz/gl share)
    |  PARTIAL    computable now WITHOUT routes, at a stated cost in discrimination
    |             among same-snap-share receivers. Routes would sharpen it; their
    |             absence widens it rather than stopping it.
    v
EFFICIENCY (yds/target, yds/carry, completion, TD rate)
    |  PARTIAL    fields present; 2 games is too little. Needs declared shrinkage
    |             to the existing multi-season panel.
    v
TD / RZ ALLOCATION
    |  PARTIAL    rz/gl opportunity measured; conversion needs the efficiency layer
    v
PLAYER OUTCOME DISTRIBUTIONS
    |  BLOCKED    by specification, not by data: player_draws refuses because the
    |             receiving and rushing layers are CONTRACT_DECLARED_LAYER_ABSENT and
    |             participation_prior is BLOCKED on the 404. A second declared arm
    |             that does not consume participation would unblock it.
    v
JOINT GAME SIMULATION
    |  BLOCKED    nothing built. Needs shared latent game state with within-draw
    |             reconciliation. This is the largest remaining piece.
    v
DFS CANDIDATE GENERATION
    |  BLOCKED    needs the simulator; correlation must emerge from football
    v
PORTFOLIO SELECTION
       BLOCKED    additionally needs an ownership / opponent-field model, which does
                  not exist. Duplication and expected payout are UNKNOWN until it does.
```

## The shortest sound path, in order

1. **Declare a second `participation_prior` arm that does not consume routes.** Snap-share
   based, with a predeclared wider dispersion for unverifiable route roles. This is the
   single highest-leverage change: it converts a hard block into a labelled, wider
   estimate and unblocks the four stages beneath it.
2. **Implement the rushing and receiving opportunity layers** against measured weeks 1–2
   shares, consuming the redistribution trees as priors for players affected by today's
   absences.
3. **Add efficiency with declared shrinkage** to the existing multi-season panel.
4. **Build a DST pathway.** It currently has *no component at all* — the position most
   likely to be forgotten precisely because it has no player features to notice missing.
5. **Then** the joint simulator, and only then candidate generation and portfolio
   selection.

Steps 1–4 produce a governed, labelled player-distribution layer without a single byte
from outside this repository. Step 5 is the real project.

## What this does not license

Steps 1–4 do not make the slate proprietary and do not retire the FC fallback. A
projection layer built on two games with widened intervals is a *first* governed
projection, not a validated one, and it must be forward-chained against unseen games
before any comparison with FC is read as evidence that either side is sharper.
