# Exposure-cap sensitivity, TB@DAL 2026 W5 Showdown (research only, 2026-10-09)

**Production caps are unchanged:** player 50%, captain 30%, overlap at most 4 of 6, with the relaxation ladder.
Nothing here is wired into a build.

## Design

- **Same worlds for every arm:** the OFFICIAL TB@DAL draws, 2,000 worlds.
- **Same candidate pool for every arm:** the 5,387 candidates of the corrected R1 build.
- **Same objective:** E_w[min(hits, m)], where a hit means scoring at least 0.9× the world optimum.
- **Only the player cap varies:** 40%, 50%, 60%, or uncapped.
  - The captain cap stays 30%; uncapped also lifts it to 100%.
  - The ladder may relax only the overlap (4 to 5). It does not relax the cap under test, or the arm would no
    longer be testing that cap.
- **How the cap was changed:** only on each research process's copy of `showdown_portfolio.LADDER`
  (`scripts/build.py`).

**Control check:** the 50% arm's upload is byte-identical to the entered R1 upload (sha `9d05d9bb…`), so the arms
share the incumbent's machinery exactly.

## Results (in-simulation; `CAP_SENSITIVITY_TB_DAL.json`, `CAP_SENSITIVITY_DOWNSIDE.json`)

| | 40% | 50% (control = R1) | 60% | uncapped |
|---|---|---|---|---|
| Build | **FAILS**: short 32 / 4 / 4 entries after the ladder | built, 150-max relaxed to overlap 5 | built, L0 | built, L0 |
| 150-max objective | — | 0.9975 | 0.9985 | 0.9985 |
| 20-max objective (m=2) | — | 1.146 | 1.243 | 1.343 |
| 150-max max player exposure | — | 50% | 60% | 79% (Lamb, Prescott) |
| 150-max top captain share | — | 22% | 30% | 46% |
| 150-max distinct captains | — | 16 | 17 | 17 |
| 150-max mean pairwise players shared | — | 2.31 | 2.38 | 2.51 |
| 150-max mean lineup score | — | 88.8 | 92.7 | 96.1 |
| 150-max portfolio-mean p5 world | — | 64.8 | 66.4 | 67.3 |
| 150-max best-lineup p5 world | — | 93.1 | 92.5 | 92.6 |
| 20-max max exposure | — | 50% | 60% | 85% (Otton) |
| 20-max best-lineup p5 world | — | 88.0 | 88.7 | 88.4 |

**Downside in the worlds where Lamb lands in his own bottom decile (200 worlds, 150-max):**

| | 50% | 60% | uncapped |
|---|---|---|---|
| Portfolio mean | 73.7 | 74.9 | 72.7 |
| Mean of the best lineup | 106.7 | 106.7 | 106.2 |

## What this does and does not show

1. **For the 150-max, the cap barely moves the objective.** The objective is already saturated (0.998 against a
   ceiling of 1), so raising the cap mostly raises the *average* lineup, not the chance of holding a
   near-optimal one.
   - That is the expected behaviour of a "first-place proxy" objective, which rewards one hit per world.
   - The 20-max objective does rise with the cap.
2. **A 40% player cap is infeasible** with the 30% captain cap and overlap ≤ 5 on this pool. That is a measured
   constraint, not a preference.
3. **Concentration rises steeply once uncapped:**
   - 79% of 150 lineups hold Lamb and Prescott;
   - one captain takes 46% of entries.
4. **In-simulation downside does not penalise concentration, and it cannot.** The worlds are ours, and their lower
   tail for high-mean players is under-stated (defect D-01, `TB_DAL_DEFECT_REGISTER.json`). An optimizer judged
   on worlds that under-state a star's dud rate will always prefer more of the star. The cap is the only guard
   against that, and this experiment cannot validate removing it.
5. **Hindsight (one game, NOT evidence):**

   | | 50% | 60% | uncapped |
   |---|---|---|---|
   | 150-max best | 130.0 | 133.6 | 133.6 |
   | 150-max mean | 79.0 | 81.2 | 73.7 |

   The uncapped portfolio's average lineup was the worst, because Lamb scored 2.9. One slate decides nothing.
6. **No contest objective is measurable.** There is no payout table, so there is no EV, ROI or cash rate (see the
   tournament plan, §3).

## Verdict

**No change recommended.**
- The evidence that would justify raising the cap needs worlds with a calibrated lower tail (D-01 repair) and a
  contest-EV objective with real payout tables (plan items T4/T5).
- The cap stays a declared policy, not an estimate.
- Re-run this sensitivity once both exist, on at least 8 prospective contests clustered by slate.
