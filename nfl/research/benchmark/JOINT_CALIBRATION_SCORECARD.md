# JOINT_CALIBRATION_SCORECARD (mandate b0540a52 phase 4)

**Record.** `JOINT_CALIBRATION_SCORECARD.json`, produced by `joint_calibration.py`.

**Source.** The production system's own **prelock** joint worlds, scored against what happened. 2026 W4–W5: four
incumbent slates, **11 games, 22 clubs**.

**Exploratory.** These slates were inspected before. No decision rests on this file.

**What is scored.**
- **Draws.** The draws are world-aligned: draw i is one simulated world for every player. Club, stack and pair sums are
  formed within each world.
- **Comparator: independence.** The same marginals with each player's draws shuffled independently, which removes the
  dependence and keeps the marginals unchanged.
  - CRPS joint − CRPS independent < 0 means the simulated dependence makes the forecast of the sum better.
- **Uncertainty.** Game-blocked bootstrap (10,000, seed 20261014).

## Results

| unit | n | 50 / 80 / 90% coverage | mean bias (DK) | CRPS joint − independent | spread, joint / independent |
|---|---|---|---|---|---|
| club skill total | 22 | 0.45 / 0.95 / 0.95 | −2.3 [−8.5, +4.2] | +0.18 [−0.12, +0.46] | 1.24 |
| QB + top-2 pass catchers | 22 | 0.45 / 0.73 / 0.86 | +5.1 [−2.1, +12.3] | **−0.24 [−0.58, +0.08]** | 1.23 |

| QB–pass-catcher pairs (44) | value |
|---|---|
| simulated rank correlation (mean) | 0.37 |
| realised normal-scores correlation (mean of z_QB × z_rec) | 0.42 [0.15, 0.75] |
| simulated − realised | −0.05 [−0.39, +0.23] |

## Reading

- **QB–receiver dependence.** The simulated dependence (0.37) is **consistent** with what happened (0.42). The
  interval is wide: 44 pairs in 11 games cannot separate 0.2 from 0.6. Inside that resolution, there is no evidence
  that the worlds under-correlate stacks.
- **Stacks.** The simulated dependence helps the stack forecast by about 0.24 CRPS, but the interval includes 0.
- **Club totals.** The dependence widens club totals by 24% and does not improve their CRPS. The point estimate leans
  slightly the other way. Coverage of 45% at 50% and 95% at 80% is what 22 units of noise looks like. It is not a
  calibration finding in either direction.
- **No adequacy claim.** Nothing here is written as "calibrated". There is no predeclared margin and no equivalence
  test, and 11 games cannot support one.

## What this harness now makes possible

Every prospective slate from Week 6 adds about 2 club units per game to this scorecard automatically, through the
proposed `score-completed` job (AUTONOMY_RUNBOOK). Each slate's frozen worlds are scored at that point. A **held-out
historical** joint check is still missing: the forward chain produces means, not worlds. It needs the simulator run on
historical states, and those have no vintage injury inputs (RES-010).

## Not scored

- **Kickers and team defences:** no panel actuals.
- **Real scorelines:** game points are not joined here. Club fantasy sums are.

## Found while building this

**BENCH-D4.** The prospective scorers clustered each Classic club as its own "game", so the prospective benchmark is
**11 games, not 19**. Corrected in FOUR_ARM_EXPLORATORY, PROSPECTIVE_SCORECARD, MODEL_SCORECARD
(`CORRECTION_BENCH_D4`) and BENCHMARK_PROGRESS_REPORT. Point estimates are unchanged.
