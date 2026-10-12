# Pre-registration: how CORRECTED_V1 is graded from Week 6, and which weeks can confirm anything

- **Written:** 2026-10-12 at 13:20 UTC (09:20 ET), before any 2026 Week 6 game. The commit time is
  authoritative.
- **Why:** owner review step 2. The Week 5 receiver-spread result stays FAIL. The new statistic (C3) was designed
  after Week 5 was seen, so the weeks that follow have to be split into those that can confirm and those that cannot.
- **Amends:** PREREG_ECW2 section 3 (predictive window weeks 6-11), by adding sections 2-4 below. Nothing in its
  metric, uncertainty or harm rule changes.

## 1. Frozen configuration (CORRECTED_V1)

| component | file | SHA-256 (first 16) |
|---|---|---|
| world builder, ECW version 3 | `nfl/sim/event_consistent_worlds.py` | 5fd21934e5d58668 |
| measured inputs | `nfl/research/accounting_repair/ECW2_INPUTS.json` | 056d2baba254fcab |
| structural acceptance (C2 + C3) | `nfl/research/accounting_repair/ecw2_acceptance.py` | f834b9e34b7c8946 |
| participation worlds | `nfl/sim/participation.py` | db4e83e2e55ba8df |
| P(no participation) | `nfl/research/participation_pm1/PM1_TABLE.json` | 801f670c480ec1bb |
| φ | `nfl/research/participation_pm1/PM3_PHI.json` | d8573a547bcfeea2 |
| raw simulator | `nfl/sim/game.py` | cc0a94e72c073d50 |
| arm runner | `nfl/tools/classic_slate_run.py` | 4f98e6ac4449419a |
| draws builder | `nfl/tools/showdown_draws.py` | 8fd69a85fea81c2d |

- Each week's arm build records these hashes.
- A build whose hashes differ is a **different configuration**, and the weeks graded on the old one stay with the old
  one.
- **Dependency, not frozen:** the QBCTX-DB1 starter deviations exist for Week 5 only
  (`QBCTX_W5_2026_FORECASTS.json`). The arm runs without them in any week that has no registered forecast file, and
  that is recorded per week as `qb_conditioned_volume: NOT_APPLIED`. It is never silently substituted.

## 2. The structural statistic, frozen

**C3** decides the receiver-dispersion check from Week 6 on:

- simulated receiving-yards CV per receiver with mean > 2 catches;
- computed over worlds with > 2 catches;
- using the benchmark's estimator (pstdev over mean) at the benchmark's sample sizes (k worlds, k drawn from
  `ECW2_INPUTS.json` `games_per_player_season`, median of 400 draws, seed 20261011);
- the median over receivers, divided by 0.4514;
- bar: [0.85, 1.15], unchanged.

C3 is a **measurement repair** (ACC-D1), and it is labelled as one everywhere it appears. It was chosen after Week 5
was seen. **No week graded on C3 is cited as evidence that the world builder is realistic.** It only reports whether
the frozen builder stays inside the bar.

## 3. Which weeks are exploratory and which confirm

| weeks | role | why |
|---|---|---|
| 5 | **development**, closed | C3, SIM-D9's reading and the release fixes were designed on it |
| 6-8 | **exploratory** | the first prospective weeks; anything found here may change the arm |
| 9-11 | **confirmatory**, only if the section 1 hashes are unchanged from the Week 9 build onward | untouched by any design decision |
| 12-14 | **reserve confirmation** | used **only** if any change to the arm is made after Week 8 is graded. The confirmatory window then moves here, in full. |

- PREREG_ECW2 section 3's predictive comparison is unchanged: per-player DK CRPS, paired with the incumbent on the same
  frozen pre-lock state, week-block bootstrap B = 4,000. It is **reported separately for weeks 6-8 and for the
  confirmatory window**.
- Only the confirmatory window decides SHADOW-CONTINUE, REJECT or INCONCLUSIVE.
- A window with fewer weeks than the harm rule's planned need reads **INCONCLUSIVE**, never PASS.

## 4. What each week must archive before lock

Both arms, the incumbent and CORRECTED_V1, are built from the **same** frozen pre-lock STATE. Each week archives:

- the STATE, PROJ, DRAWS and WORLDS of each arm, with their hashes and the section 1 hashes;
- the evidence packet the STATE consumed, with its hash and receipt time;
- the clock (UTC and ET) at each build, and the kickoff;
- whether the build was a ledgered pipeline run, with its run id, or hand-run, and that is stated either way.

A week that lacks any of these is **not graded**. It is not imputed and not replaced.

## 5. Voids

- Grading a confirmatory week on a build whose section 1 hashes differ.
- Using any outcome from a week to change the arm and then grading that same week as confirmatory.
- Any post-lock fact in either arm's build (the release record's `BUILT_AFTER_LOCK` block applies).
