# Where each gap stands, with the evidence and the blockers

Every number below was measured in this repository and is reproducible from the named module.
Where something is blocked, the blocker is a data request in `docs/AGENT_OUTBOX.md`, not an
unfinished thought. Nothing here is a recommendation and no wager is implied.

Read the status words strictly. **BUILT** means it runs and is tested. **MEASURED** means a number
exists with an interval. **PARTIAL** means it works and a named part of it does not. **BLOCKED**
means it cannot be done here and says what would unblock it.

## The development order the owner fixed, and what happened

| # | Step | Status | The number that says so |
|---|---|---|---|
| 1 | Historical warehouse from 2000 | BUILT | 13,982 club-games 2000–2026; 27,577 player-games; 17,721 role rows; 945 statistic-seasons in the coverage ledger |
| 2 | V1 complete projections | BUILT | 457 rosterable players, every one with a state; no player silently absent |
| 3 | Forward-chained calibration | BUILT | MAE 4.824, bias +0.012, rank correlation 0.446 on held-out 2024–25 |
| 4 | Optimiser / search quality | BUILT, PROVEN | exact 172.31 against a 171.59 floor; verified against brute force on value and roster |
| 5 | Ownership / field model | PARTIAL | identities exact, generator reproduces its marginals to 0.00079; ownership LEVEL uncalibrated |
| 6 | Joint game simulation | PARTIAL | **11 of 16** pair correlations reproduced inside a predeclared tolerance, 4 inside the measured interval (was 7 of 16) |
| 7 | Contest-aware portfolio | BUILT | P(one entry in the top 1%) 0.4775 → 0.7575, a 1.59× improvement |
| 8 | Real-time automation | BUILT | 14 stages with declared freshness tolerances; the Saturday rule passes |
| 9 | SIM_OPTIMAL | NOT_CLAIMED | deliberately: the field level is uncalibrated and the entry selection is parameter-dependent |

## Defect removal since the first pass, with the measured effect

Four unit and contract mismatches, each of which produced a confident wrong answer rather than an
error. They are listed together because they are one species: a number carrying the right information
in the wrong units, or a claim counted over the wrong sample.

| Defect | Effect when fixed |
|---|---|
| `required_players` accepted and ignored by the optimiser, returning PROVEN_OPTIMAL for a different question | constraint manifest; 14 constraint types each with a positive, negative and brute-force test |
| `depth_rank` is CLUB-WIDE, read as position depth, so every club's WR2 and beyond capped at FRINGE | 124 players out of rank 4-plus, 49 role bands corrected, ROTATIONAL 4 → 33, SECONDARY 15 → 34 |
| the hierarchical prior's WEIGHT counted over the at-role subset while its VALUE came from the whole history | an established prior no longer takes 12% of the blend; weight floored at the at-role count |
| `ROLE_HISTORY.share_of_club` is a share of the RANKED GROUP, fed in as a share of the club | two backs stopped splitting 97% of a club's carries; simulated pair correlations 7 of 16 → 11 of 16 |

Two smaller ones inside the same work: `xlsx_writer.verify`'s `expected_sheets` compared a count
against whatever it was handed, and the Sunday orchestrator returned PASS with a failed child step.

**The pipeline shape worth remembering.** Fixing `role_state.py` changed nothing until
`nfl/derived/ROLE_STATE.json` was regenerated, because the projection reads the artifact. A correct
module behind a stale artifact is indistinguishable from a broken module.

## Constraint enforcement, measured

Costs on the Week 3 slate against a free optimum of 166.6295, each PROVEN_OPTIMAL under the complete
compiled set and verified against the returned roster:

| Constraint | Optimum | Cost |
|---|---|---|
| stack ≥ 2 | 165.6944 | −0.935 |
| stack ≥ 3 | 159.2234 | −7.406 |
| bring-back ≥ 1 | 166.3454 | −0.284 |
| stack ≥ 2 and bring-back ≥ 1 | 160.9736 | −5.656 |
| stack ≥ 3 and bring-back ≥ 2 | 150.4273 | −16.202 |

The stack figure agrees to four decimals across three independent mechanisms. A budget-limited search
returns BEST_KNOWN or refuses; it never returns a proof it has not earned.

## What is genuinely blocked, and on what

**Archived contest ownership (OUT-040).** Blocks the ownership *level*, duplication, chalk-failure
study, and which specific 48 entries to entER. Does **not** block the method: joint selection beats
independent selection at every field setting tested, by 0.18 to 0.32 absolute.

**Defensive and return touchdowns (OUT-041).** Every defensive projection is a **floor**, and the
understatement sits in the upside tail, which is the part a tournament portfolio is selected on.

**Play-by-play 2000–2020 (OUT-039) and historical rosters (OUT-038).** Play detail before 2021
reads `UNKNOWN_PENDING_ACQUISITION`, never zero.

## The findings a future session should not re-derive

- **Same-club receivers are positively correlated**, +0.170. Cannibalisation does not dominate at
  the WR1/WR2 level; the shared game environment does.
- **Opposing players are positively correlated**: +0.153 for the two quarterbacks, +0.093 for the
  two lead receivers. Shootouts lift both sides.
- **The same-club stack and the bring-back move opposite ways with the total.** Same-club QB~WR1
  falls 0.424 → 0.332 as the total rises; bring-back rises 0.033 → 0.152.
- **Stacking a quarterback with his WR1 doubles the chance both go big**, 2.03× over independence
  (interval 1.83–2.22). Quarterback with his own back shows **no** established lift, 1.07
  (0.89–1.24).
- **Clubs trade passes against runs**: corr(pass attempts, rush attempts) = −0.4255, and −0.3440
  even after points and margin. Two independent attempt regressions imply only −0.1407, which is
  why volume is parameterised as plays and pass share.
- **Losing a lead receiver makes a club pass LESS**, not more (−2.22 attempts, −2.7pp pass rate).
- **The market's implied club total explains r² = 0.156 of actual club scoring.** The simulator
  draws game totals around that line, so our club-level scoring view *is* the market's. Any edge
  has to come from allocation inside a club, not from disagreeing about team totals.
- **Carry shares are far more volatile than target shares**, 2.78× the multinomial variance against
  1.21×. A backfield is not a receiver rotation.

## Rejected by its own comparison

A usage-first allocation arm was built on a real measurement — 63% of yards-per-carry variance is
player-level, 80% for yards-per-target — and it is **not** the default, because head to head with the
denominator defect fixed in both arms it reproduced 8 of 16 pair correlations against the baseline's
11. Both comparison logs are committed. The measurement stands; the conclusion that it helps does not.

## The open architectural question

Hard reconciliation to a drawn club total makes the split between teammates zero-sum, so the two
backs come out at −0.249 against +0.000 measured, and adding share dispersion made it *worse*
because a Dirichlet moves work between them rather than creating it. Real football expands a club's
carry total when a back's role grows instead of taking carries off his teammate.

The surviving five misses now tell one story, and it is not the one this project first declared. The
two backs sit at −0.310 against a measured +0.000, and the two receivers have **flipped sign**, −0.053
against a measured +0.170. Decomposing the observed teammate covariance explains both: for the backs
+5.389 comes from the shared club total and −3.880 from share competition, while for the receivers the
competition term is **positive**, +0.995. A Dirichlet can only produce negative share covariance, so
no concentration exists for receivers at all.

So the root cause of both is the same: the Dirichlet is the wrong family for shares. The next
experiment is logistic-normal shares with the measured covariance matrix, which can represent positive
and negative co-movement alike. Five hypotheses have now been tested against this defect; three were
refuted by measurement, one was confirmed and adopted, one was adopted and then rejected on the
acceptance metric.

## Things that must not be done to make the numbers look better

- No per-pair correlation correction. A correlation produced by a fudge factor is the hand-added
  bonus the design forbids, and it would destroy the only property worth having.
- No external projection as a feature input, ever, by any path.
- No ownership synthesised to unblock a contest decision.
- No defensive touchdown rate invented to lift the defence floor.
- SIM_OPTIMAL stays unclaimed until the field level is calibrated.
