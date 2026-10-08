# QB dependency audit and SC-QB-ENV-1 pre-registration (design only), 2026-10-08

**Owner directive:** when QB1 is ruled out, the system must resolve QB2, rebuild the team offensive environment and
condition every relevant teammate on the selected QB. A forecast may stay unchanged only where an explicit model says
so, never because a dependency is missing.

**Status:** AUDIT COMPLETE. MEASUREMENT COMPLETE. CANDIDATE DESIGNED, NOT IMPLEMENTED. Nothing in production
changed, apart from the readiness gate in section 4.

## 1. Where QB identity enters today, and where it does not

The production Showdown path, stage by stage. All `file:line` references are at `7390def0`.

| # | Stage | Code | Uses QB identity? | Consequence |
|---|---|---|---|---|
| 1 | Slate state: starter flag, availability, depth rank | `showdown_slate_state.build`, `_starter_context` | **yes**: who is flagged starting, who is OUT | correct after the P0 guard |
| 2 | Role state and QB depth rank | `role_state.assign`; `classic_slate_state._qb_rank` | **yes**: the starter takes rank 1 | correct |
| 3 | QB share of club attempts | `proj_v1.depth_shares` (QB only, by rank) | **yes**: rank 1 ≈ 0.95 of club attempts | the starter gets the attempts, whoever he is |
| 4 | **Club volume** (plays, pass/rush attempts, targets) | `proj_v1.team_volume`; blend at `proj_v1.py:167-273` | **no**: club history, current season plus 4 prior pseudo-games | **first missing dependency** |
| 5 | **Scoring centre** (team points, total, margin) | `nfl/sim/football_points.expected_points` / `centre_for_game` | **no**: club points history | **second missing dependency**; feeds the TD pool, the opposing DST and the joint simulation |
| 6 | Club TD pool and pass/rush TD split | `proj_v1.allocate_club_td` from the centre | no | inherits stage 5 |
| 7 | Receiver targets and shares | `proj_v1.allocate_opportunity`, `group_shares` | no | targets are QB-invariant (measured on TB@DAL: identical) |
| 8 | Player efficiency | player priors (`player_prior`) | **only the QB's own** yards per attempt | Daniels 4.96 vs Mayfield 6.09 per attempt, but receivers' efficiency is unchanged |
| 9 | Joint simulation: total and margin | `sim/game.py` around the stage-5 centre | no | team points are QB-invariant (TB 19.7 vs 19.5) |
| 10 | Volume response to the realised game | `SHARED_STATE.volume_response_to_realised_game` | no | — |
| 11 | **Efficiency post-step** | `classic_slate_run.efficiency_worlds` (`:106-124`, registered defect R1) | scales each player's yards **independently** | QB yards ≠ receivers' yards: in the Daniels worlds receivers get +30 yards per game more than he throws |
| 12 | Opposing DST (sacks, takeaways) | `dst_model`, opponent centre | no | a weaker QB does not raise the opposing DST |
| 13 | Kicker | `kicker_model` | no | — |

**Answer to "where should the first QB-dependent adjustment enter".**
- **Stage 4/5, the club environment**, before allocation.
- Every later stage (6, 7, 9, 12, 13) reads the environment. Conditioning it there propagates through the TD pool, the
  joint simulation, the opposing DST and the kicker without touching each consumer.
- **Stage 8/11** is the second entry point. Passing efficiency must be a team-passing quantity that the receivers share
  (passer yards = the sum of receiver yards). It must not be a QB-only scale.
- The registered repair, event-linked world EL_S1, makes passer yards the sum of receiver events but drops the QB's own
  yards-per-attempt row, so it would make passing **fully** QB-invariant. SC-QB-ENV-1 has to supply that row at the
  team level.

## 2. Measurement: how much the missing dependency is worth on average

Source: `nfl/research/qb_env/qb_change_effect.py` → `QB_CHANGE_EFFECT.json`.

**Data and method.**
- 2021–2025 regular seasons. Everything is before any 2026 cutoff.
- A starter counts as a change when his pre-game blended share of the club's attempts is at most 0.5. This is the
  runner's own rule.
- Mid-game QB changes are excluded (118 club-games), to avoid conditioning on in-game events.
- Residuals are measured against the production QB-blind centres.
- Confidence intervals are 95%, cluster bootstrap over game dates.

| vs incumbent starts (n = 1,847) | n | Points vs centre | Pass yds / att | Pass att | Rush att |
|---|---:|---|---|---|---|
| All changes | 719 | −0.81 [−1.68, +0.06] | −0.15 [−0.30, −0.01] | −0.40 [−1.10, +0.38] | +0.51 [−0.14, +1.14] |
| **In-season replacement** (≥ 2 current games, current share < 0.5) | 462 | **−1.06 [−2.06, −0.02]** | −0.17 [−0.36, +0.02] | −0.52 [−1.35, +0.35] | **+0.92 [+0.12, +1.67]** |
| New-season starter | 257 | −0.36 [−1.56, +0.85] | −0.13 [−0.29, +0.05] | −0.17 [−1.27, +1.02] | −0.22 [−1.10, +0.66] |

**Reading.**
- The average in-season replacement scores about 1 point less than the QB-blind centre says, runs about 1 more time
  and is about 0.17 yards per attempt less efficient.
- That is real and modest **on average**. Backups vary, so an average is not a forecast for a particular QB.
- These are averages over non-random events (injury, benching), so they are **not** causal estimates.
- This is why a universal backup downgrade is ruled out: the candidate has to be specific to the QB.
- **CORRECTION (2026-10-08, after the independent Perplexity review).** The starter here is labelled from the
  outcome: the QB with the most attempts in that game. Excluding mid-game changes also conditions on in-game events.
  - These figures are therefore **descriptive associations on outcome-labelled cases**, not pregame forecast effects.
  - A pregame cohort needs point-in-time starter evidence; see `FOOTBALL_INTELLIGENCE_AUDIT_2026-10-08.md` §6, item 7.

## 3. SC-QB-ENV-1: candidate design (declared now; nothing fitted until this is frozen)

**What it does:** conditions the club environment (stages 4 and 5) and team passing efficiency (stages 8 and 11) on
the scenario's starter.

**Model.**
- **QB passing quality:** shrunk yards per attempt, TD rate, INT rate and sack rate for the starter. Shrinkage is
  toward a pool of replacement-QB priors, estimated from the in-season replacement population in 2021–2024.
- **Club environment:** the incumbent's quality is estimated the same way, from the blend. The environment is moved by
  the starter-minus-incumbent difference through measured elasticities:
  - points per unit of passing quality;
  - pass and rush attempts per point of expected margin, re-using the measured realised-game volume response;
  - receivers' yards per target scaled by the starter's completion and air-yards profile.

  So a better QB can raise the environment and a worse one lower it. If the two are equivalent, nothing moves, and
  that is an explicit result.
- **Coherence:** passer yards equal the sum of receiver yards in every world. This needs the EL_S1-style event ledger
  with the starter's team-passing efficiency carried in.
- **Uncertainty:** QBs with a thin history get wider passing-quality spreads, which the joint simulation carries.

**Validation.**
- **Fit:** 2021–2024.
- **Confirmation:** 2025 in-season replacement games, read once. The measurement above used 2025 descriptively, so
  confirmation must be on 2026 weeks 6 and later, prospectively. That is declared here.
- **Prospective:** every 2026 Showdown and Classic slate with a QB change from now on.
- **Endpoints:**
  - team points CRPS and pass-yards CRPS against the incumbent on replacement starts, with non-inferiority on incumbent
    starts;
  - receiver-yards calibration;
  - joint coherence (zero QB-vs-receiver yard breaks);
  - DFS: portfolio exposure and lineup changes, reported, not scored as a bar.
- **Bar:** declared before any fit, in the freeze document.
- **Status:** SHADOW_ONLY.

## 4. Applied tonight (validation only, commit `7390def0`)

**The rule.** `showdown_run_guards.football_model_status`:
- `COMPLETE_FOR_STARTERS` only when every named starter threw a majority of the attempts his club environment is
  built from;
- otherwise `INCOMPLETE_QB_ENVIRONMENT`.

**`final_verify`** reports `technical`, `data`, `football_model` and `dfs_decision` separately, and READY needs all
four.

| TB@DAL scenario | Starter's blended share | Status |
|---|---:|---|
| Daniels | 0.116 | **INCOMPLETE_QB_ENVIRONMENT**: cannot be READY |
| Mayfield | 0.870 | COMPLETE_FOR_STARTERS, but he is formally Out |
| Prescott (DAL) | 0.982 | complete |

**What COMPLETE does and does not mean.** It is not a claim that the model is right. It is a claim that the
environment's QB-blind history is that QB's own history, so no dependency is missing.
