# ATL@NO Showdown 2026-10-05 -- postgame autopsy and next-Showdown readiness

Layers kept apart: PRELOCK_FORECAST / PRELOCK_PORTFOLIO (sealed, unchanged), POSTGAME_ACTUAL, POSTGAME_DIAGNOSIS, SUCCESSOR_CANDIDATE. **ATL@NO is one prospective observation, not proof of edge.**

## Deliverables

1. Immutable postgame truth package -- `nfl/postgame/showdown_atl_no_2026W4/ATL_NO_POSTGAME_ACTUAL.json + nfl/postgame/showdown_atl_no_2026W4/ATL_NO_OWNER_ENTRIES_GRADED.csv`
2. Owner portfolio scorecard -- `nfl/postgame/showdown_atl_no_2026W4/ATL_NO_PORTFOLIO_SCORECARD.json`
3. Best-lineup / top-1% autopsy -- `nfl/postgame/showdown_atl_no_2026W4/ATL_NO_TOP_LINEUP_AUTOPSY.json + nfl/postgame/showdown_atl_no_2026W4/ATL_NO_AUTOPSY_VERDICTS.json`
4. Player forecast grading -- `nfl/postgame/showdown_atl_no_2026W4/ATL_NO_PLAYER_FORECAST_GRADING.json`
5. Projection calibration report -- `nfl/postgame/showdown_atl_no_2026W4/ATL_NO_CALIBRATION_REPORT.json + nfl/postgame/showdown_atl_no_2026W4/ATL_NO_COHERENCE_REMEASURE.json`
6. Role/depth-chart defect audit -- `nfl/postgame/showdown_atl_no_2026W4/ATL_NO_ROLE_AUDIT.json + nfl/tests/test_role_depth_adversarial.py`
7. Ownership/field/dupe calibration update -- `nfl/postgame/showdown_atl_no_2026W4/ATL_NO_FIELD_ACTUAL_PREREGISTERED.json + nfl/postgame/showdown_atl_no_2026W4/SHOWDOWN_FIELD_LOSO.json`
8. Portfolio-performance decomposition -- `nfl/postgame/showdown_atl_no_2026W4/ATL_NO_PORTFOLIO_STUDY.json`
9. Hard Rock grading -- `nfl/postgame/showdown_atl_no_2026W4/ATL_NO_HARD_ROCK_STATUS.json (NO_VALID_PRELOCK_MARKET_CAPTURE)`
10. Successor-candidate comparison -- `nfl/postgame/showdown_atl_no_2026W4/ATL_NO_SUCCESSOR_CANDIDATES.json`
11. Next-Showdown readiness board -- `nfl/postgame/showdown_atl_no_2026W4/NEXT_SHOWDOWN_READINESS_BOARD.json`

## Autopsy verdicts (item 3)

- **Q1 Did the lineup succeed because the football forecast was directionally right?** `CONTRADICTED` -- the game script that produced it (ATL blowout) was a 2.7% world in our simulation, and the three players who carried the lineup finished at PIT 1.00 / 0.99 / 0.92 of their own forecasts. Volume forecasts for Olave and London were close, but those are not what made this lineup.
- **Q2 Did it succeed because the portfolio captured the correct tail scenario?** `PARTIALLY_SUPPORTED` -- the coverage objective did put lineups into the ATL-led script (this lineup was 2.5x likelier to hit the proxy there), and the portfolio beat both one-lineup-at-a-time ablations in its own prelock worlds and on the night. But the outcome hinged on Brian Robinson Jr. (3 TDs on a 4.65-point projection), in every top-1% lineup we held, at low exposure -- the portfolio reached that tail by breadth, not by forecasting it.
- **Q3 Did ownership/leverage help?** `CONTRADICTED` -- our 6th-place lineup was chalkier than the median field entry (65th percentile of product ownership). What separated 1st from 6th was the captain: the winner captained Brian Robinson Jr. at 0.83% CPT ownership; ours captained Kamara, a more popular build. Leverage helped the winner, not us.
- **Q4 Did low duplication help?** `CONTRADICTED` -- the lineup was in the field 120 times: 120 entries tied at 6th and, under DK's tie rule, split the prizes for places 6-125, which is why a 6th-place finish paid $87.50. Only 1 of our 150 lineups was unique; median 62.5 copies. Duplication cost us money on the best result of the night.
- **Q5 Was there material outcome luck?** `SUPPORTED` -- one lineup is 65% of the 150-max return and without it the 150-max ROI is -37%. Its decisive player scored at the 100th percentile of his forecast on three short touchdowns, while his pregame red-zone share (1 carry vs Bijan 11 in weeks 1-3) gave no reason to expect them. V1 (not entered) held a lineup 0.09 points short of the same score -- placed in the real field it is #126, behind the 120-way tie.

## Field comparisons (from the full standings)

| contest | winner (pts, copies) | winner CPT own | our best: rank, pts, copies (entries tied at that rank) | CPT is RB: top 1% vs field |
|---|---|---|---|---|
| 196285137 | CPT Brian Robinson Jr. + Alvin Kamara, Bijan Robinson, Chris Olave, Jahan Dotson, Tyler Shough (143.99, 1) | 0.83% | #6, 142.54, 120 (120) | 84.95% vs 31.74% |
| 196285160 | CPT Brian Robinson Jr. + Alvin Kamara, Bijan Robinson, Chris Olave, Jahan Dotson, Tyler Shough (143.99, 1) | 1.21% | #9748, 110.45, 33 (33) | 85.62% vs 32.01% |
| 196285161 | CPT Alvin Kamara + Bijan Robinson, Brian Robinson Jr., Chris Olave, Devaughn Vele, Jahan Dotson (144.00002, 1) | 4.11% | #29262, 98.44, 22 (53) | 87.14% vs 31.95% |

## Hard Rock (item 9)

- `NO_VALID_PRELOCK_MARKET_CAPTURE`. historical prices are NOT reconstructed; the sealed forecast stays SHADOW / NOT_VALIDATED.

## WHAT WE LEARNED

- The 150-max profit (+$59.47) is one lineup: $87.50 of $134.47; without it the 150-max is -37%. 20-max -80%, 2-entry -100%.
- The game script was a 2.7% world in our simulation (ATL 45-24 against sim means ATL 17.6 / NO 23.0). The forecast was not directionally right about this game.
- Player calibration on the night looks unremarkable (PIT mean 0.50, 80% coverage 0.80 over 20 players) -- consistent with calibration, not evidence of it.
- DEFECT-COHERENCE is real when measured like-for-like: yards/receptions per extra TD are +0.05 / -0.05 DK in the simulator vs +4.72 [4.35, 5.09] in 2021-25 (within team-season). The prelock 0.55-vs-0.811 comparison mixed definitions; the corrected gap is 0.63 vs 0.792 [0.777, 0.806].
- Pair correlations (QB-receiver, QB-RB, cross-team) are NOT under-correlated against pregame-role history; the published COR-01/02 targets overstated them.
- The allocator's P(plays) is a depth-rank population rate. For active players with an opportunity in each of their last 3 games it shrinks means and adds zero-mass far beyond history (B. Robinson Jr. carries 35% vs 4%).
- The coverage objective beat one-lineup-at-a-time ablations in its own worlds and on the night; it reached the ATL tail by breadth.
- The 6th-place lineup was NOT unique: 120 identical entries tied at 6th and split the prizes for places 6-125 ($87.50 each). Only 1 of our 150 lineups was unique in the field; median 62.5 copies. Low duplication did not help -- duplication cost money.
- Leverage helped the winner, not us: the winner captained Brian Robinson Jr. at 0.83% CPT ownership; our best lineup sat at the 65th percentile of field product ownership.
- Our lineups were duplicated 3-6x more than independent product ownership predicts EVEN WITH THE ACTUAL ownership (150-max: 15,823 copies vs 5,334); the ownership forecast itself (BLEND) was close on aggregate. The field builds optimizer-like lineups together.
- Shadow ownership: BLEND beat FC_ONLY on every ownership metric in every contest, but both missed cheap rotation players badly (B. Robinson Jr. 17.6% FLEX actual vs 0.0 / 1.0 predicted; Bryce Lance 21.8 vs 6.4 / 9.4).
- Field priors on three slates (leave-one-slate-out): our same-slate team-split prior was very close on ATL@NO (distance 0.01); nothing beats the current shape or CPT:FLEX priors on every fold; the count-scale dupe model (SC-DUPE-COUNT-1) fails its pre-declared bar on ATL@NO.
- Correction: an earlier note called V1's 142.45 lineup a top-10 finish. In the real field it is #126, directly behind the 120-way tie.

## WHAT WE ARE CHANGING

- Readiness check before the next slate: automated specialist detector on the captured chart (no model change).
- Registering SC-COH-1, SC-APPEAR-1, SC-DUPE-COUNT-1, SC-DUPE-CORR-1 and SC-OWN-ROTATION-1 as SHADOW successors with their held-out bars stated in advance.
- Prelock board (reporting only): expected copies of our lineups shown beside the measured 3-6x independence miss, so a duplicated portfolio is visible before lock.
- Labelling fixes proposed (PROJECTIONS.csv if-plays columns; the _chart_rank comment).

## WHAT WE ARE NOT CHANGING

- The production football model, simulator, allocator and portfolio objective for the next slate. No successor is ready and none is promoted on one game.
- The shadow ownership / field / dupe stack stays SHADOW; FC-08 / FC-09 / CPT = 0.5 x FLEX are not used.
- Hard Rock props stay SHADOW / NOT_VALIDATED; no prices reconstructed.
- Nothing is refitted on ATL@NO, and ATL@NO is not called evidence of edge.

## WHAT MUST PASS BEFORE THE NEXT SHOWDOWN

- finalization gates suite green on the commit that runs the slate
- official inactives captured and verified (READY gate unchanged)
- specialist check: every DK skill player whose captured chart rows are special-teams only is designated
- determinism: same inputs + seed reproduce the upload byte-for-byte (repro run before upload)
- prop forecast sealed BEFORE any Hard Rock price is captured; a board captured after the seal and before kickoff
- nothing in SHADOW changes a production lineup; no successor promoted without its held-out bar

## Pre-registered measurements

- All five (docs/NFL_SHOWDOWN_ATL_NO_POSTGAME_PREREGISTRATION.md) are scored in ATL_NO_FIELD_ACTUAL_PREREGISTERED.json, per contest, against the frozen prelock predictions (committed 9736516d before lock). The 150-max dupe stack was recomputed from the frozen inputs and matched every stored mean, row and top-10 before use.
