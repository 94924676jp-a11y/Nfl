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
| 3 | Forward-chained calibration | BUILT, **VERDICT NEGATIVE** | the multi-season prior buys level and costs ordering; it does NOT beat a current-season baseline on rank. See FORWARD_CHAIN_VERDICT.md |
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

**Defensive and return touchdowns (OUT-041) — CLOSED 2026-09-28, and no outside data was needed.**
It was raised as a data request because `TEAM_GAME` carries only offensive touchdowns. Play-by-play
carries `td_team`, `return_touchdown` and `safety`, so the tail is measured, not excluded: 0.1197
defensive or return touchdowns per club-game and 0.0237 safeties over 2021-2026, drawn jointly with
sacks and takeaways inside each points-allowed band. The 99th percentile of a defence allowing 20
moved 15 to 20 DK points. **Defensive projections are no longer floors.** Blocked kicks and the
field-goal split remain unmeasured; neither affects DK defensive scoring.

**Archived contest ownership (OUT-040) — still absent, now an exact and EXPIRING list.** The field
model stays `NOT_CALIBRATED_NO_ARCHIVED_CONTEST_OWNERSHIP`. What changed is that the request is no
longer open-ended: the fourteen contests the owner actually entered are read out of the `DKEntries`
files, seven of them Classic, and the data is a per-contest DraftKings standings CSV that the
entering account can download. **This is the only outstanding request that can expire** — access is
to contests the account can still view, so if DraftKings stops serving a finished contest page that
week's ownership is unrecoverable. `nfl/field/contest_ownership.py` is the single door: it validates
against the real export schema, refuses a partial file whole, and returns BLOCKED-on-DATA naming the
missing contest ids instead of a number. FantasyCruncher `Exp.`/`EXP+` is **not** a substitute and
the module has no code path to it.

**Play-by-play 2000–2020 (OUT-039) and historical rosters (OUT-038).** Play detail before 2021
reads `UNKNOWN_PENDING_ACQUISITION`, never zero.

**Where the between-player variance goes (#99) — MEASURED 2026-09-28, nothing adopted.** V1's
projections separate players less than realised points do, and the hierarchical prior is part of the
cause but not most of it. 63.5% of skill players on the Week 3 slate get a COHORT prior, which is a
constant shared by everyone in that cohort: 46 tight ends hold **one** prior value between them and
it takes 96% of their blend. Splitting the prior's weight cap by tier and forward-chaining six arms
separates what a single scalar could not: turning the **own-history** prior off moves rank
correlation by **+0.0000** against production, and turning the **cohort** prior off moves it by
**+0.0256** (z 18.0, confirmation season). Essentially all the ranking loss is the cohort constant,
which is the owner's hypothesis and it holds. But removing the prior entirely closes only about a
**quarter** of the separation gap (7.32 → 9.21 against a realised 15.33), so three quarters of the
missing spread is elsewhere and this study does not say where. Compression is also mildest where the
money is: predicted-to-realised SD ratio is 0.71-0.74 for ALPHA/PRIMARY/SECONDARY against 0.38 for
ROTATIONAL. See `nfl/research/shrinkage/VERDICT.md`. **No production change was made.**

**`PRIOR_WEIGHT_CAP = 2.0` rests on evidence that does not support it, and is LEFT AS IT IS.** It was
chosen over 0 on MAE and top-30 margins of 0.018 and 0.006 against week-blocked standard errors of
0.106 and 0.50 for those same statistics, and its confirmation set was "28 untouched weeks" of which
14 were 2021 — a season where the panel has no prior at all, so **0 of 2,698 projections differ
between any two arms**. Recorded at the constant's definition. Changing it is a production decision
on its own commit.

**The role-state cap and the weekly band (owner item 4) — MEASURED 2026-09-28, and it reverses a
recorded verdict.** `forward_chain.historical_band` said a historical role state was not
reconstructible, so the starter cap was asserted in production and measured nowhere; and it assigned
ONE band per player per season, which is **not** what production runs. Reconstructing a point-in-time
weekly band — proved point-in-time by rebuilding it from a panel with the scored week and every later
week deleted — decomposes cleanly: **updating the band weekly is worth +0.047 to +0.056 rho**, the
**cap adds +0.004 to +0.014**, and **knowing who is out adds +0.067 to +0.072 more than everything
else combined**. Against the current-season-only baseline, the season-constant band loses by
−0.0364 rho (reproducing `FORWARD_CHAIN_VERDICT.md`) and the weekly capped band **wins** by +0.0151
selection and +0.0336 confirmation. The negative verdict measured a configuration production does not
run, and is marked superseded on that claim. See `nfl/research/rolestate/VERDICT.md`.

**The highest-value outstanding item is now known by measurement, not intuition.** The gap between
the pregame arm and an oracle that knows who actually played is **+0.067 to +0.072 rho and −0.33
MAE** — larger than every other effect measured on 2026-09-28 combined, including the whole shrinkage
study. That gap is exactly what an injury report buys, so **official inactives (A7) and historical
injury reports (OUT-038) outrank the research work they were queued behind.**

## The confidence statement, kept separate on purpose

| layer | standing |
|---|---|
| exact optimiser | **trusted** — proven against brute force, every constraint compiled and verified |
| contest portfolio | method **promising**, specific entries **not determined** |
| joint simulator | **partially** trusted — 11 of 16 correlations, one named open question |
| role / prior pipeline | **improving** — four unit defects removed, effects measured; the cohort prior is now measured as costing ranking, and the weight cap's own evidence does not support it |
| **proprietary projections** | **NOT yet validated** — but ranking skill above a current-season baseline **is now demonstrated**, forward-chained, once the harness uses the weekly role band production actually runs: +0.0151 rho (z 3.2) on selection and +0.0336 (z 3.7) on confirmation, and better MAE on both. One cell of a three-part scoreboard; no economic metric is tested. |

The last line is the one that gates everything downstream, and it is not closed by any amount of
machinery quality upstream of it.

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
- **The multi-season prior buys level and costs ordering.** Weeks 2–4 it improves MAE 5.870 → 5.678
  and the level ratio 0.846 → 0.880; in both regimes it reduces rank correlation, every paired
  week-blocked difference beyond two standard errors. The more the *depth curve* decides the worse
  it gets; the more the *player's own* history decides the better.
- **A Dirichlet cannot represent co-moving teammates.** Measured in centred-log-ratio space, 10 of
  56 off-diagonal target-share correlations are positive. Logistic-normal fixes WR1~WR2 and breaks
  four passing pairs, so it is rejected as default — the marginal covariance double-counts the
  game-state channel the simulator already models.
- **Recency is not provenance.** An artifact 0.00 seconds old whose builder has since changed is
  stale, and lineage catches it where a timestamp cannot.

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
