# OWNER_READINESS_BOARD (mandate b0540a52 phase 7), 2026-10-14

**Headline (OD-003).**

| question | answer |
|---|---|
| Does the complete football model beat a news-adjusted simple baseline? | **Prospectively, yes, on 11 already-inspected games (exploratory; INTERIM / NOT A DECISION).** C − B1 −0.53 [−0.70, −0.37]; C − B3 −0.70 [−0.99, −0.43] DK MAE. |
| Historically, with news on both sides? | **UNAVAILABLE** (no lawful historical injury vintages, RES-010). |
| Historically, with no news on either side? | The **incumbent core loses** to the naive baseline: +0.70 [+0.62, +0.77]. The **D2 challenger beats it** on the 2025 look: −0.05 [−0.10, −0.01]. Not confirmed. |

**Nothing was promoted.** No production default, no real-money setting and no workflow changed.

## The eight mandate outputs

| # | output | state | file (nfl/research/benchmark/) |
|---|---|---|---|
| 1 | BENCHMARK_REPRODUCTION | **DONE.** 15 steps; all 12 published artifacts byte-identical at 37565c3e. | `BENCHMARK_REPRODUCTION.json`, `reproduce.py` |
| 2 | FORECAST_ERROR_ATLAS | **DONE** (2024 dev). Appearance is the largest error, APPEAR-D1. Club volume is right. Top-claimant share is high. Efficiency is close. | `FORECAST_ERROR_ATLAS.{json,md}` |
| 3 | FAIR_BASELINE_SCORECARD | **DONE.** Equal-information comparison throughout. Historical news arms are UNAVAILABLE. | `FAIR_BASELINE_SCORECARD.json` |
| 4 | JOINT_CALIBRATION_SCORECARD | **DONE** on prelock worlds (11 games, exploratory). QB–receiver dependence is consistent (sim 0.37, realised 0.42 [0.15, 0.75]). | `JOINT_CALIBRATION_SCORECARD.{json,md}` |
| 5 | CHALLENGER_PREREG + results | **DONE.** D1 FAIL (look 1, retained). D2 PASS (look 2), all ablations reported. | `PREREG_D2_APPEARANCE.md`, `RESULT_D2.md`, `D2_*.json`, `HOLDOUT_LOOKS.jsonl` |
| 6 | DFS_DOWNSTREAM_SCORECARD | **DONE as status.** EV is UNAVAILABLE (FIELD-D1). SEL-2 is opt-in. CG-1 is registered, with its harness not built. | `DFS_DOWNSTREAM_SCORECARD.md` |
| 7 | AUTONOMY_RUNBOOK | **PROPOSED, not activated.** Workflow text for the owner to install. | `AUTONOMY_RUNBOOK.md` |
| 8 | OWNER_READINESS_BOARD | this file | `OWNER_READINESS_BOARD.md` |

## What changed in what the system knows

**APPEAR-D1, the largest error found.** The football core's P(plays) is a depth-*slot* occupancy rate, not a
player-level probability. It is 1.0 for 93% of pool players, while 60% appear (2024).

**The fix, D2.** D2 is a player-level beta-binomial with a role prior, fitted on 2022–23.

| season | D2 − incumbent (DK MAE) | positions |
|---|---|---|
| 2024 | −0.71 | — |
| 2025 (one logged look; previously inspected season) | −0.61 [−0.71, −0.51] | all four better |

- Appearance Brier: 0.39 → 0.17.
- This is the first held-out result in which the core is not beaten by the naive baseline.

**BENCH-D4 (measurement fix).** The prospective benchmark is 11 games, not 19. Point estimates are unchanged; the
intervals were recomputed and the records corrected.

**Joint worlds.** No evidence of under-correlated stacks at the available resolution. The dependence does not improve
club totals. There is no adequacy claim.

## Readiness

| layer | state | blocking |
|---|---|---|
| production gate (32 modules) | **PASS** at be798fd6: 1,785 checks, 0 failing, 0 blocked (not a full-suite result) | — |
| full suite | last measured at 3fc67181: 61 red modules (unchanged here; not re-run this cycle) | suite trust (P0-B) |
| point-in-time | enforced on guarded captures, TEAM_GAME, derived and fitted content; pit_exempt barred from release | PIT-D1 coverage completion |
| eligibility (OD-002) | three-state contract and release gate in code | ELIG-D4 roster freshness |
| football core | D2 passes its look; **not confirmed, not promoted** | prospective arm D (engineering, next) |
| DFS selection | SEL-2 opt-in; CG-1 harness not built | W6 prospective evidence; ENG-015 |
| DFS EV | **UNAVAILABLE** | lawful prize tables and a field model (FIELD-D1) |
| production certification | **NOT CLAIMED** | all of the above |

## Owner decisions requested (nothing below is assumed)

1. **D1 equivalence margin.** D1 failed by its rule on RB at +0.0007 DK MAE, with no margin declared. Should a
   per-position non-inferiority margin (for example 0.05 DK) apply to future challengers? This changes what counts as
   evidence, so it is yours. Until then the rule stays strict.
2. **Autonomy cadence and budget.** About 200 runner-minutes a week, as proposed. Approve or adjust it, set a monthly
   cap, and install `nfl-evaluation.yml` (agent-denied path).
3. **Perplexity package.** It was not found in any upload or tree. Send it, or confirm that it is withdrawn.
4. **Data, RES-008..011** (W5 play-by-play, elevations, historical injury vintages, vendor archives). These are blocked
   for the agents on rights and network. Each one unblocks a named UNAVAILABLE row above.

## Next queued research (no owner decision needed; shadow only)

1. Prospective arm D = D2-ROLE on the slate path, prelock, beside C, from Week 6. It applies only to players the news
   does not already mark absent.
2. CG-1 harness (ENG-015), on the frozen slates, diagnostic.
3. W6 onward: score each slate as it completes (four-arm, joint, D2) until the pre-registered 30-game decision point.
