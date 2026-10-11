# ECW-2 pre-registration: event-consistent worlds, repairing the defects the 2026-10-09 evaluation found

- **Written:** 2026-10-11 at about 19:35 UTC. The commit time is authoritative.
- **Parent:** ECW-1 (`nfl/sim/event_consistent_worlds.py`, `bd895bb3`). Its integration evaluation
  (`INTEGRATION_EVALUATION_2026-10-09.md`) recorded DAMAGE_DETECTED on calibration, means and game outcomes, plus
  defects ECW-D1 to D8.
- **ECW-1 is not edited.** Its verdict stands. ECW-2 is a new candidate.
- **Status:** PRE-REGISTERED, SHADOW ONLY. ECW-2 is the world builder of the CORRECTED_V1 arm. That arm runs beside the
  incumbent (owner decision E2) and is never production until this protocol passes.

## 1. What ECW-2 changes

Inputs are measured from 2021-2025 regular-season play-by-play by `ecw2_inputs.py`, written to `ECW2_INPUTS.json`.

| defect | ECW-2 change |
|---|---|
| **D2:** defensive TD and safety points counted on top of the drawn remainder | The club's own DST defensive/return TD points (6 each) and safety points (2 each) in that world are **subtracted from the drawn remainder before field goals and tries are allocated**. Club points remain the event sum. |
| **D1:** no overtime | A world tied after the event sum is resolved by the measured outcome shares of games tied after regulation (FG 0.571, TD 0.345, tie 0.048, other 0.036, the last added to the FG share). The winner is home with probability 0.525. **FG:** +3 to the winner, credited to no Classic player. **TD:** +6 and no try (an OT touchdown ends the game). It is placed as one extra play of the winner's in that world: a pass with the club's pass-TD share, one target and catch and the receiver's projected yards per catch for a receiver weighted by TD shares, plus a pass TD, an attempt and the same yards for the QB; otherwise one carry and a rush TD to a carrier weighted by rush-TD shares, with his projected yards per carry. Every box-score law still holds. |
| **D4:** receivers too wide | A receiver's catch yards in a world are his projected yards per catch × the **sum over his catches of draws from the measured catch-shape distribution** (yards on one catch over the player-season mean, CV 0.85), times the club's raw yards-per-target ratio in that world over its mean. The club factor keeps teammates' shared efficiency. The ECW-1 per-player raw ratio, which carried the raw simulator's wide yards per catch, is removed. |
| **D5:** DST band from continuous points | **Recorded, not repaired here.** The count of band-changed worlds stays in the account. |
| **D7:** club passing anchor | **QB anchor** (ECW-1's default). Club passing yards come from the QB side. This is the only anchor through which a different quarterback can change his receivers' yardage, which is the W5-G18 direction. **Owner decision pending;** the receiver anchor stays available as a declared alternative. |
| **D3:** 3- and 7-point margins; **D6:** league-average DST tuples | **Open.** Declared, not changed. |

## 2. Structural acceptance

These are checked on every build, not on outcomes:

- `world_accounting_check`: **0 violations** on every law, on the published worlds.
- Club points == the event sum in every world.
- Tie share of worlds ≤ **0.6%** (twice the historical 0.29% final-tie share).
- Median, over receivers with mean > 2 catches, of the ratio (their simulated single-game receiving-yards CV over the
  historical benchmark CV 0.451) within **[0.85, 1.15]**.
- An inactive player has no events in any world.

## 3. Predictive evaluation (prospective only)

- **Window:** 2026 weeks 6-11, every early Classic main slate the pipeline builds. The incumbent and CORRECTED_V1
  arms are paired on the same frozen state.
- **Harm rule:** `HARM_RULE_v2_PROPOSAL.md` is adopted by name here, including sample-size planning. A stratum with
  fewer weeks than its planned need is **INCONCLUSIVE**, never PASS.
- **Metric:** per-player DK CRPS (exact empirical CRPS from the 2,000 worlds), paired on player-weeks with a DK
  actual.
- **Uncertainty:** week-block bootstrap, B = 4,000, seed 20261011.

| result | condition |
|---|---|
| SHADOW-CONTINUE | non-inferiority on every non-vacuous stratum, no harm flag, rank preservation |
| REJECT | a harm flag or a failed bound |
| INCONCLUSIVE | below planned power |

## 4. Voids

- Any change to section 1 after the first prospective week is graded.
- Any use of a 2026 week-6-or-later outcome in building either arm.

## Amendment A1 (2026-10-11, about 19:40 UTC, before any ECW-2 evaluation)

Found on the first CORRECTED_V1 replay of the 2026-10-11 slate, before any ECW-2 world was evaluated.

### D7: the QB anchor fixed the QB's mean whatever his receivers did

- On the replay, McLaurin played a mean 0.82 of his role, and Daniels' passing yards moved 187.86 → 187.98.
- **Change.** The QB anchor's club passing yards are multiplied by r_mix. r_mix is the club's yards per target at
  the worlds' expected target mix, divided by the same quantity at the projection's target mix.
  - Each receiver enters at his projected catch rate and yards per catch.
  - With no participation change, r_mix is 1 up to Monte Carlo noise in mean targets.
- The QB still sets the level, so a different quarterback still moves his receivers. The mix his targets go to
  now moves him.

### Accounting: two violations remained on the replay, and both are repaired

| violation | world | cause | repair |
|---|---|---|---|
| one passer with more interceptions than attempts | NO, world 1798 | — | interceptions are placed one at a time against each QB's attempts |
| club targets above club attempts | WAS, world 1243; present in the incumbent too | the raw simulator's unallocated QB attempts | those attempts are credited to the club's QB with the most attempts that world |

### Unchanged

Section 1's other changes and the acceptance and evaluation sections are unchanged.
