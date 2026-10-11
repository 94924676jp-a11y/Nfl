# NFL forecasting repository: research landscape (read-only synthesis)

Source: `/home/user/nfl`, branch `claude/nfl-greenfield-architecture-stsxmk`, HEAD `0c5bf600` (2026-10-10). I wrote
nothing inside the repo and ran nothing that writes there. I ran no tests and used no network. All paths below are
relative to `/home/user/nfl`. Every number is quoted from the file cited. "Not re-read" means I cite the file without
quoting a number from it.

Verdict vocabulary used here:
- **PROMOTED**: in the production path.
- **REJECTED**: failed a predeclared bar, or was withdrawn.
- **OPEN**: supported, but neither promoted nor refuted, or a prospective test is still running.
- **BLOCKED**: cannot run on the evidence that exists.

## 0. Ground truth to keep in mind

- **Status line.** "NFL-0 … NFL-1 is not authorised" (`CLAUDE.md`). The live DFS path still runs a forecaster, which
  `nfl/research/qb_regime/README.md` flags as being in tension with that line:
  `proj_v1` → `showdown_draws` / `classic_slate_run` → `showdown_portfolio` / `nfl/opt/classic_portfolio.py`.
- **Authority documents.**
  - Candidate register: `nfl/research/registry/CANDIDATE_STATUS_REGISTER.json`. Append-only, and its last row is
    dated 2026-10-07.
  - Production decision board: `docs/PRODUCTION_CHANGE_DECISION_BOARD.md`.
  - V1 ledger: `NFL_V1_RESEARCH_LEDGER.md`, dated 2026-09-09. Its §3 "Rejected — do not re-propose" and §8 "investigated
    more than once" lists still apply.
  - Latest gap register: `nfl/dfs/salaries/classic_early_2026W5/WEEK5_FORECASTING_GAP_REGISTER.json`, W5-G1…G26, as
    of 2026-10-10T19:00Z.
- **Data already read for development.** None of these is an untouched holdout any more:
  - 2022–2025: "heavily mined" (TD1, RC1, RC2).
  - 2025: read four or more times for appearance (`CANDIDATE_STATUS_REGISTER.json`, APPEAR-SUCCESSOR-1 row).
  - 2026 W2–W3: read by COH-EVENT-LINKED-1.
  - 2026 W1–W4: read by OPP-ADJUST-1 (supplementary).
  - 2026 W2–W4: read by the RC-1 development replays.
  - ATL@NO: used three or more times.
  - **The only clean held-out evidence is 2026 W6 onward, prospectively.** TB@DAL W5 is the one frozen-then-graded
    Showdown slate that no candidate selected on (`docs/HISTORICAL_REPLAY_FEASIBILITY.md`).
- **Market lines.**
  - Sportsbook prices may evaluate a forecast and never feed one (`CURRENT_STATE.md` §8, `MARKET_IS_EVALUATION_ONLY`).
  - FantasyCruncher (FC) is "context only, NEVER a model input" (`docs/INTEGRATION_FEASIBILITY_AUDIT_2026-10-09.md`
    F01). FC features are allowed for **ownership** forecasting (`docs/NFL_SHOWDOWN_CHEAP_OWNERSHIP_PREREGISTRATION.md`
    l.45).

---

## 1. Research ledger

Abbreviations:
- **FC-hist**: forward-chained over history, each season fit only on earlier seasons.
- **PR**: pre-registered (hash-pinned where noted).
- **PROSP**: prospective on unseen 2026 games.
- **Δ**: candidate minus incumbent. Negative is better for CRPS, Brier and MAE.

### 1a. Opportunity: appearance, shares, redistribution

| id | question | population | design | headline (exact) | verdict | path |
|---|---|---|---|---|---|---|
| P1 | Can opportunity be forecast before efficiency? | 2021–2025 player-games | FC-hist, PR | Snap-share persistence r ≈ 0.71. Team pass volume from QB history r ≈ 0.10–0.22. "Proportional transfer is worse than … no transfer" | baseline only | `TASK_REPORT_2026-09-07_P1_OPPORTUNITY.md` |
| P2 | Appearance × conditional usage | 2021–2025 | FC-hist, PR | A×C r: snap_share 0.70→0.78. MAE beats P1 in only 11/20 target-seasons, and is worse in 2025 (no injury vintage) | REJECTED as a replacement; Stage A kept | `TASK_REPORT_2026-09-07_P2_APPEARANCE_USAGE.md` |
| P3 | Availability quality, role transition | 2021–2025 | FC-hist, PR | Stage A Brier 0.1286→0.1257 (2024). `from_starter` AUC 0.841, `to_starter` 0.769 | P3 Stage-A logistic ACCEPTED (V1 rehearsal-only) | `TASK_REPORT_2026-09-07_P3.md`; `NFL_V1_RESEARCH_LEDGER.md` §1 |
| P4D | Appearance calibration in the 0.25–0.50 band | 2021–2025 | FC-hist, PR | Within-band AUC 0.536→0.686, but downstream PIT worse (snaps 91.2→105.2) | REJECTED (incumbent retained) | `TASK_REPORT_2026-09-07_P4D.md` |
| p1s (P-recov.) | Pass-snap participation recoverability | n = 22,500 | FC-hist, PR `149faf8` | `ewma_hl1` +1.86% MAE, 4/4 seasons better, 0/4 reach the 5% bar | OPEN (`ewma_hl1` rehearsal-only) | `P_RECOVERABILITY_RETURN_2026-09-08.md` |
| R study | Target rate R* = W*/P* | 2022–2025 | FC-hist, PR `322b567` | Every R context block rejected | REJECTED | `R_STUDY_RETURN_2026-09-08.md`; V1 ledger §3 |
| Q6 | Appearance features plus conditional role | 2022–2025, 34,621 player-games | FC-hist, frozen spec, team-game block bootstrap | Q6_FEATURES Brier −0.632% [−0.000771, −0.000391], 8/9 cells. Headline arm Q6_CALIBRATED gives WEAK_SUPPORT (6/9). Vacancy correction carries CRPS +0.251% (worse, significant). Surviving starter over-fed, ratio 1.186 | OPEN (WEAK_SUPPORT, not promoted) | `nfl/research/q6/Q6_DECISION.md` |
| Q8 | Where receiving-opportunity error lives | 2022–2025, 34,710 | FC-hist, exact Shapley | APPEAR bias +2.118 (112.3%), a selection artefact: appeared-only −1.998 vs forecast population +0.139. CLASS/SHRINK/REDIST each carry < 5% of movement. Budget-shrink repair: slope 0.575→0.954, but downstream 4 strata better and 4 worse | REJECTED (repair) | `nfl/research/q8/Q8_DECISION.md` |
| Q9 | Target hurdle (zero mass) | 2022–2025, 69,420 rows | FC-hist, frozen spec | Marginal target CRPS −0.591% [−0.00644, −0.00338]. Zero-rate gap 0.0247→0.0044. Cold start −7.297% | OPEN (SUPPORT) | `nfl/research/q9/Q9_DECISION.md` |
| Q9B | Is the hurdle structural? | 22,958 appearing | PR, then audit | Structural excess +0.02679 (10.68% of zero mass). MNL_PLUS moves zero mass the wrong way (−0.04068 gap) | OPEN: "PROMOTION_READY_FOR_PROSPECTIVE_TEST", but the prospective ledger holds **0 rows** and the freeze pin has diverged | `nfl/research/q9b/Q9_MODEL_FAMILY_AUDIT.md`; `nfl/prospective/q9shadow/Q9_PROSPECTIVE_LEDGER_STATE.json`; `nfl/research/q9b/FREEZE_PIN_DIVERGED.md` |
| A1 (assumption) | Appearance certainty | — | governed assumption | FALSIFIED. Successor DISC-2 BLOCKED: "the conditioning variable has no contrast" | BLOCKED | `CURRENT_STATE.md` §4, §7 |
| A2 (assumption) | Proportional redistribution | 2022–2025, 1,257 single-shock room-weeks | Thresholds declared before the run; cluster bootstrap | 6.1% (targets) to 22.8% (rz_targets) of vacated work leaves the room. Survivor-gain slope: carries **0.495**, targets **−0.161**. Survivors who were already larger absorb far less than proportional predicts | FALSIFIED. Successor is design only. Production is still pro-rata | `nfl/research/assumptions/A2_RESULT.md`, `A2_SUCCESSOR_SPEC.md` |
| Track 3 (H3) | Does vacated work go to the adjacent depth role? | union frame | PR only | **Never run.** Only Track 1 and Track 2 results exist | OPEN (unrun) | `nfl/research/prereg/PREREG_TRACKS_1_2_3.md` §Track 3 |
| CS2 | Current-season non-QB role state | 2022–2025, 136 folds | FC-hist, PR | "INVERSION_RESOLVED" | accepted into V1 rehearsal | `nfl/research/cs2/CS2_STAGE2_RESULT.md` |
| SC-APPEAR-1 | Corrected appearance rates (DFS path) | 2025 retrospective | dev | Zero-opportunity Brier .223→.062 for qualifiers. Gate alone −0.0475 (z −20.6, FAILS). Rates plus gate +0.027 (z 8.2). `p_plays` is dropped at `showdown_draws.py:103`. 2025 forward test: Brier 0.22054→0.18122 (z 14.04) | SHADOW (OPEN) | `CANDIDATE_STATUS_REGISTER.json`; `nfl/research/appearance/SC_APPEAR_1_FORWARD_TEST.json` |
| APPEAR-SUCCESSOR-1 | Rates plus hurdle gate inside the draws | 2025 dev; 2026 W5 PROSP | PR; sealed 2026-10-07T15:22Z, 15/15 games, 437 units | Dev: zero-opportunity Brier 0.2123→0.1442. Positive-count CRPS worse than the ungated candidate (−0.194, z −13.7) | OPEN: prospective in flight. Verdict needs ≥ 4 graded weeks, ≥ 1,500 units, ≥ 25 clubs | `docs/NFL_APPEARANCE_SUCCESSOR_PREREGISTRATION.md` §5; `nfl/prospective/appearance/APPEARANCE_SUCCESSOR_W5_SEAL.json` |
| AP-1 | Player appearance history replaces the club-slot P(plays) | 2026 W6–W11 PROSP | PR 2026-10-09 | Dev (W4 Early, real pool): −0.116 [−0.274, +0.046], 16 clubs | OPEN: prospective. Needs ≥ 150 club-weeks | `nfl/research/role_ceiling/PREREGISTRATION_ROLE_CEILING_AND_APPEARANCE.md` |
| RC-1 | Formation (position-aware) rank ceiling | 2026 W6–W11 PROSP | PR 2026-10-09 | Dev replays: −0.217 [−0.327, −0.102]. Real W4 pool: +0.054 [−0.154, +0.294], "did not replicate" | OPEN: prospective | same |
| W5-G12 / W5-G13 | Absent-player rank; tie broken by id | 2026 | repair plus regression | W5: 26 rooms with a tied rank, 10 tied at rank 1 | PROMOTED, provisionally ("rollback = revert 39340321, a8efedae") | `docs/OWNER_RULINGS_RELAYED_2026-10-09.md`; gap register |
| C1 `_chart_rank` | Conditional pass keeps chart rank | ATL@NO, TB@DAL | one-change A/B | Only `dk_points_if_plays` moves. Lineups identical | SHADOW / insufficient evidence | `docs/SHOWDOWN_AB_EXPERIMENT_MATRIX.md` |
| Specialist detector | Auto-tag special-teams-only players | ATL@NO | byte-identity | Upload unchanged | PROMOTED (owner-approved) | `CANDIDATE_STATUS_REGISTER.json` |

### 1b. Team volume and environment

| id | question | population | design | headline (exact) | verdict | path |
|---|---|---|---|---|---|---|
| P4 | Team plays and pass/run environment | 2021–2025 | FC-hist, PR | Team plays r = 0.093–0.167. League mean is the best baseline in 2 of 4 seasons | REJECTED ("cannot forecast the size of the pie") | `TASK_REPORT_2026-09-07_P4.md` |
| P4B | Team volume as a distribution | 2021–2025 | FC-hist, PR | CRPS better in 20/20 target-seasons, by 0.35–4.5%. A perfect pie buys 5.4–18.5% of MAE; a perfect slice buys 45–64% | PROMOTED to the V1 baseline (D1 `team_volume_v1`, rehearsal-only) | `TASK_REPORT_2026-09-07_P4B.md`; V1 ledger §1 |
| Track 1 | Game-state-conditioned offence | 2022–2025, 10,727 team-games | FC-hist, PR | 3 of 4 metrics significantly worse. Only `team_carries` improves: −0.611% [−0.0493, −0.0027] | REJECTED | `nfl/research/track1/TRACK1_DECISION.md` |
| Track 2 | Neutral pass-rate trait | 2020–2025 | FC-hist, PR | +0.00001 MAE against a base of 0.07994; the coefficient flips sign | REJECTED | `nfl/research/prereg/TRACK2_NEUTRAL_PASS_RATE_RESULT.md` |
| v4 teamvol | Team-volume drift | 2023–2025, 1,632 team-games | chronological | Bias off_snaps **+0.996** (SE 0.266), dropbacks **+0.605** (SE 0.296). Both excluded zero and rose monotonically by season | measured. Repair status at HEAD not re-verified | `nfl/research/v4/teamvol/TEAM_VOLUME_DRIFT.md` |
| Coupling | Is offence coupled within a game? | 2024–2025, 285 games/season | measured | History ≈ 0 (2024 yards −0.0858 [−0.2000, +0.0307]). Sealed DET-BUF worlds −0.1310 | premise REJECTED | `nfl/research/coupling/COUPLING_RESULT.md` |
| A3G | Couple the two teams in a game | 2020–2025 dev | PR | not re-read (`a3g_results.json`) | not promoted | `nfl/research/a3g/A3G_FINDING.md` |
| OAS1 | Opponent-adjusted team strength | 2025 W2–18 plus 2026 W1 | FC-hist | Pass B4 −0.001443, game CI [−0.002477, −0.000535]. Fitting declared NO-GO | REJECTED for fitting (NO-GO) | `nfl/research/oas1/BASELINE_RESULT_FROZEN.md`, `GO_NO_GO.md` |
| OPP-ADJUST-1 | Opponent variables D2–D7 | 2021–2025, held-out 2024+2025, n = 1,088 club-games | PR plus amendment A1; truncation self-test 0 mismatches | Pass att −0.85% [−0.082, +0.006]; rush −1.53% [−0.126, +0.0004]; points −1.08% [−0.117, +0.012] (98.33% Bonferroni). 2026 W1–4: no gain. Player level ≤ 0.2%. **Incidental:** the incumbent's held-out slopes are 0.59 / 0.59 / 0.67, and a training-fit shrink moves points MAE from 7.661 to 7.536 | REJECTED (all FAIL) | `nfl/research/opponent_adjustment/OPP_ADJUST_1_RESULTS.md` |
| C3 cold start | Week-1 team rating | backtest | frozen spec `b356ecaa…` | prior regressed by a factor of about 0.4 | frozen: "do not revisit" (T1/T3 closed) | `nfl/research/C3_COLD_START_SPEC.md`; `CLAUDE.md` |
| REST / REST2 | Last-regular-week rest state | 2022–2025 | FC-hist, PR | Coefficients' z between −0.96 and +0.27 | REJECTED (withdrawn) | `nfl/research/rest/REST2_WITHDRAWN.md` |

### 1c. Efficiency and touchdowns

| id | question | population | design | headline (exact) | verdict | path |
|---|---|---|---|---|---|---|
| Q7 | Efficiency calibration given opportunity | 2022–2025, 93,961 rows | FC-hist, frozen spec | `pyds\|cmp` at 40+ attempts: bias **+19.80**, slope 0.728. Width repair ΔCRPS −0.143% (CI spans 0). About 72% of RC2's bias is upstream | REJECTED (the mean defect remains) | `nfl/research/q7/Q7_DECISION.md` |
| P5A | Carries → rushing yards | 2021–2025 | FC-hist, PR | Knowing carries buys 50.9%; perfect efficiency 16.2%; the whole efficiency ladder 0.93% | REJECTED (whole ladder) | `TASK_REPORT_2026-09-07_P5A.md` |
| RC1 | Receiving conversion decomposition | 2022–2025 | PR `34f8ac10…` | Opportunity 53.86%, conversion 46.14% (as quoted in TD1) | control ACCEPTED | `RC1_RECEIVING_CONVERSION_RETURN.md` |
| RC2 | Receiving calibration repair | 2022–2025 | PR `65c5e295…` | R0 bias +2.1801. R1–R4 all FAIL | REJECTED (`CALIBRATION_DEFECT_CONFIRMED`; population artefact per Q8) | `nfl/research/rc2/RC2_FINDING.md` |
| TD1 | TD decomposition | 2022–2025, n = 22,521 | PR `8effcb5a…` | Conversion K carries 76.55% (receiving) and 75.07% (rushing) | diagnosis | `nfl/research/td1/TD1_FINDING.md` |
| TD2 | TD recoverability | 67,672 targets, 56,293 carries | PR `31e75d82…` | Pooled `B_pos` wins (receiving log loss 0.184822) | `B_pos` control ACCEPTED | `TD2_TOUCHDOWN_RECOVERABILITY_RETURN.md` |
| S4 / R1 / infogap | Receiving information gap | 2022–2025 | PR proxy probe (VOID, then replaced) | S4: A 11.73 / T 13.84 / P 28.47 / R 45.95%. R1 `SIGNAL_WEAK` | REJECTED (`NO_DETECTABLE_INCREMENTAL_SIGNAL`) | `nfl/research/infogap/RECEIVING_INFORMATION_GAP_RETURN.md` |
| Shrinkage #99 | Does the cohort prior compress the ranking? | FC-hist, selection 2023–2025, confirmation 2022 | PR, week-blocked | Cohort off: Δρ **+0.0256 (z 18.0)**; own-history off +0.0000. Production ranks last on both splits | OPEN: recommended (cohort cap 0), **not adopted** (`PRIOR_WEIGHT_CAP_BY_TIER: dict = {}` at `nfl/tools/proj_v1.py:117`) | `nfl/research/shrinkage/VERDICT.md` |
| Role state | Weekly band plus depth cap | selection 2023–2025, confirmation 2022 | PR | Pregame cap vs current-season-only: +0.0151 (z 3.2) and +0.0336 (z 3.7). The oracle-availability gap is +0.067–0.072 ρ | production mechanism validated in this one cell. Oracle gap = value of knowing who is out | `nfl/research/rolestate/VERDICT.md` |

### 1d. Quarterback

| id | question | population | design | headline (exact) | verdict | path |
|---|---|---|---|---|---|---|
| QB3 | QB dropback allocation | 3,851 QB-games, 2022–2024 | PR `be613926…` | CRPS 0.0945 vs production B2 0.5842 | OPEN (rehearsal-only) | `nfl/research/qb3/QB3_FINDING.md` |
| OWN-3 (C0) | Cold-start QB share leak | — | PR | Leak 5.3168% → 0.000000% | OPEN (`include_cold_start=False`) | `NFL_OWN3_COLDSTART_RETURN.md` |
| OWN-8 / 9 / 10, J1 | Rushing ownership | 2022–2025 | PR | J1 A3 ΔES −0.0824 [−0.1160, −0.0503]. OWN-9 A1 valid. OWN-10 A2 rejected; A1 per draw +0.3065 [+0.2768, +0.3388] vs observed +0.3140. "Carve QB first" settled in **7 passes** | A3/A1 rehearsal-only. Rest REJECTED | `nfl/research/j1/J1_FINDING.md`; `NFL_OWN10_RETURN.md`; V1 ledger §8 |
| XL1 / C3-shared | Pass event generated once | rehearsal | PR `60fe3fbc…` | Identities close 12,800/12,800 | OPEN (`SHARED_PASS_DEFAULT='off'`) | `NFL_XL1_CROSS_LAYER_RETURN.md` |
| QBSEM, QY1 | Publication semantics, yards partition | DET@BUF W2 | PR | QBSEM gate 1 fails | REJECTED (withdrawn) | `NFL_QBSEM_RETURN.md`; `nfl/research/qb_yards/QY1_RESULT.md` |
| QB-change effect | Replacement vs QB-blind centre | 2021–2025, 719 changes | descriptive, outcome-labelled (corrected) | In-season replacement: points −1.06 [−2.06, −0.02], rush att +0.92 [+0.12, +1.67] | descriptive only | `docs/QB_DEPENDENCY_AUDIT_2026-10-08.md` §2 |
| SC-QB-ENV-1 | Condition the club environment on the starter | — | design only | — | not implemented | same §3 |
| QBCTX shadow | Hierarchical QB-conditioned volume, pass rate, rushing | 2024–2025, 1,088 team-games | predeclared bar, amendment A1 | Dropbacks QB_CHANGE −0.216 [−0.394, −0.040] PASS. Pass rate FAIL (+0.065). QB rush FAIL. 2026 n = 34: candidate worse | REJECTED (1 of 3) | `nfl/research/qb_regime/README.md`, `QBCTX_SHADOW_EVAL.json` |
| QBCTX-DB1 | Dropbacks arm only | 2026 W6–W14 PROSP | PR; needs ≥ 40 QB_CHANGE games | not yet evaluated | OPEN (prospective) | `nfl/research/qb_regime/PREREGISTRATION_QBCTX_DB1.md` |

### 1e. Joint worlds, accounting, DST/K, tails

| id | question | population | design | headline (exact) | verdict | path |
|---|---|---|---|---|---|---|
| SC-COH-1 (first pass) | Analogue-library coherence | — | — | matched on sportsbook lines; outcome-derived pool | REJECTED (development evidence only) | `CANDIDATE_STATUS_REGISTER.json` |
| SC-COH-1-CLEAN | same, football-only | 2025 W10–18, 136 games | PR, read once | Energy 1.000, variogram 1.011, team CRPS 1.037 [1.002, 1.075] all FAIL; player DK CRPS 0.980 PASS (1 of 4) | REJECTED | `docs/NFL_SC_COH_1_CLEAN_EVAL_PREREGISTRATION.md`; `nfl/research/coherence/SC_COH_1_CLEAN_EVAL.json` |
| COH-EVENT-LINKED-1 | Event-linked post-steps | 2025 dev; 2026 W2–3 confirmation (n = 32) | PR | 0 violations. Player DK CRPS 1.0148 [1.0072, 1.0224] FAIL | REJECTED. A successor needs a per-catch/drive model | `docs/NFL_COHERENCE_REPAIR_PREREGISTRATION.md` |
| Accounting repair | Event-consistent Showdown worlds | TB@DAL, ATL@NO (79 player-games) | dev | DAMAGE_DETECTED on calibration, means and game outcomes. Ties 1.8–3.7% vs 0.29%. 169 of 190 lineups reshuffled | REJECTED for promotion (owner, 2026-10-09) | `nfl/research/accounting_repair/INTEGRATION_EVALUATION_2026-10-09.md` |
| DST/K audit | Why DST worlds are non-integer | 2 Showdown games plus W5 Classic | root cause | `anchor_means` (`classic_slate_run.py:150`) rescales realised scores. DAL SD 5.91→3.00 | OPEN. Shadow scorer has `ENABLED=False`; owner decision pending | `nfl/research/dst_scoring/DST_K_SCORING_AUDIT_2026-10-09.md` |
| Star dud rate (D-01) | Lower tail of star players | 2021–2025, 650 games / 122 player-seasons at 20+ | historical comparator | Historical P(<5) for 20+ projections: ALL 0.0492 [0.0316, 0.0702], WR 0.0657 [0.0401, 0.0949]. Worlds: Lamb 0.0045 | MEASURED; "repair next". No candidate exists | `nfl/research/tail_calibration/STAR_DUD_RATE_2021_2025.json`; `TB_DAL_REPAIR_PROGRAM.md` §H |
| DFS-FS1 | Prediction-time dependence panel | 4 panels × 512 team-games | descriptive | not re-read | targets only | `nfl/research/dfs/fullslate/DFS_FS1_RESULTS.md` |

### 1f. Ownership, field, duplication, portfolio

| id | question | population | design | headline (exact) | verdict | path |
|---|---|---|---|---|---|---|
| SC-OWN-ROTATION-1 | Cheap-player ownership | PIT@CLE ↔ ATL@NO | PR, LOSO | Fails both folds. Baseline misses −6.7 pp (ATL) and +8.5 pp (PIT) | REJECTED | `docs/NFL_SHOWDOWN_CHEAP_OWNERSHIP_PREREGISTRATION.md`; `nfl/postgame/dupe_research/CHEAP_OWNERSHIP_LOSO.json` |
| SC-OWN-ROTATION-2 | Successor | fitted on PIT@CLE plus ATL@NO, frozen 2026-10-07T17:44Z | PR, PROSP; verdict needs N = 4 slates | TB@DAL (slate 1 of 4): cheap \|bias\| 5.74 vs 2.59; FLEX MAE +2.55 pp vs a +1.0 allowance. **Fails this slate** | OPEN (1/4, failing) | `docs/NFL_SHOWDOWN_OWNERSHIP_SUCCESSOR_2_PREREGISTRATION.md`; `docs/NFL_SHOWDOWN_TOURNAMENT_PLAN_2026-10-09.md` §2 |
| Shadow BLEND / FC_ONLY | Ownership forecasts | TB@DAL, sealed pregame | graded | CPT MAE 1.83 / 1.56; FLEX MAE 4.28 / 6.58. **The no-fit ∝FC projection gets CPT 1.09, Spearman 0.93, FLEX 2.88** | fitted models beaten by the no-fit one | `nfl/research/field_study/TB_DAL_2026W5_SEALED_FORECAST_GRADES.json`; tournament plan §2 |
| ∝FC / ∝FC² (Classic) | Classic ownership | W4 Early, 35,671 entries | retrospective (development) | ∝FC Spearman 0.83, MAE 3.48, top-12 error 14.3 pp. ∝FC² MAE 3.30, top-12 10.8 pp | OPEN: ∝FC declared the W5 incumbent pregame, ∝FC² the challenger | `nfl/dfs/salaries/classic_early_2026W5/WEEK5_OWNERSHIP_AND_DUPLICATION_RESEARCH_BOARD.md` |
| B4 / B3S | Duplication (legal-lineup maxent) | 3 contests (ATL@NO) plus 2 slates; TB@DAL PROSP | PR §7 (proposal ≥ 5 slates) | LOSO other-copies 1.01 / 1.03 / 0.70 vs B0 2.92 / 5.00 / 5.70. TB@DAL: Spearman 0.708, Σactual/Σpred **0.16**, 43% within 2× | OPEN (shadow). Fails the calibration bar on TB@DAL | `docs/NFL_SHOWDOWN_DUPLICATION_PREREGISTRATION.md`; `TB_DAL_2026W5_SEALED_FORECAST_GRADES.json` |
| SC-DUPE-COUNT-1 | Count-scale dupe model | ATL@NO | PR | fails its bar | REJECTED | `nfl/postgame/showdown_atl_no_2026W4/ATL_NO_POSTGAME_REPORT.md` |
| ATL@NO autopsy | Did the forecast or the portfolio win? | 1 game, 3 contests | retrospective | The script was a 2.7% world. Our lineups duplicated 3–6× above independence even with actual ownership (15,823 vs 5,334 copies). The 6th place was a 120-way tie paying $87.50. Net +$55.27 on $80.20 | descriptive | same; `docs/SHOWDOWN_HISTORICAL_PERFORMANCE_REPORT.md` |
| Exposure caps | Cap sensitivity | TB@DAL | research | 40% infeasible; 50% byte-identical; 60%/uncapped concentrate. "No change recommended" | REJECTED (change) | `nfl/research/exposure_caps/TB_DAL_2026W5/README.md` |
| T1–T7 | Field simulator, contest EV objective | — | plan with promotion bars | not built. Payout tables are missing for every slate | BLOCKED (EV); planned (T1–T3) | `docs/NFL_SHOWDOWN_TOURNAMENT_PLAN_2026-10-09.md` §4–5 |
| D-12 | Does disagreement with FC predict our error? | 2 slates so far | ledger, test after ≥ 8 slates | FC closer 24 of 34 (W4 Classic) and 7 of 10 (TB@DAL) | OPEN (accumulating) | `nfl/postgame/SHOWDOWN_PLAYER_GRADING_LEDGER.jsonl` (79 rows: TB@DAL 49, ATL@NO 30) |

### 1g. Vendor and data value, and market

| id | headline (exact) | verdict | path |
|---|---|---|---|
| FTN-S1 (routes) | ρ_FTN +0.0062 [−0.0705, +0.0916] | REJECTED (`NO_MATERIAL_VALUE`) | `FTN_S1_VENDOR_SAMPLE_VALUE_RETURN.md` |
| FTN-S2 (alignment) | "~10 games" needed | BLOCKED (`TOO_SMALL_TO_RESOLVE`) | `FTN_S2_ALIGNMENT_MATCHUP_RETURN.md` |
| ROUTE-BB1 | A position-only route rate: +0.0074 CRPS (worse) | BLOCKED (`DATA_BLOCKED_BUY_CANDIDATE`) | `ROUTE_BB1_BUILD_VS_BUY_RETURN.md` |
| ALIGN-B1 | no coordinate data | BLOCKED | `ALIGN_B1_ALIGNMENT_GEOMETRY_RETURN.md` |
| MKT1 (SF@LA) | McCaffrey carries gap −47.3 pp vs the de-vigged market | diagnostic | `NFL_MKT1_MARKET_DIAGNOSTIC.md` |
| W2 props | Book Brier 0.246738 vs ours 0.249412; we lean UNDER 203 vs 60 OVER | diagnostic (market wins) | `nfl/research/postgame/week2_what_failed_what_held.md` |

**Settled — do not re-propose without materially new information** (`NFL_V1_RESEARCH_LEDGER.md` §3, §8, plus the
October items above):
- forecastable team volume (5 passes, all negative);
- proportional redistribution (3 passes, all negative);
- naive shrinkage fixes;
- true routes (7 passes);
- carve QB first (7 passes);
- RB1↔RB2 sign (6 passes);
- PROE, neutral pass rate, game-state multiplier;
- opponent adjustment (OAS1, OPP-ADJUST-1);
- efficiency ladders (P5A, Q7, RC2);
- event-linked / analogue coherence (SC-COH-1-CLEAN, COH-EVENT-LINKED-1, event-consistent worlds);
- the QBCTX full model;
- SC-OWN-ROTATION-1;
- every FTN, route and alignment line.

---

## 2. Data inventory (pre-kickoff evidence usable for evaluation)

### 2a. 2026 slates

Showdown entry counts are full fields, counted from the files. Ownership rows are player × slot rows carrying
`%Drafted`.

| slate | frozen pre-kickoff projection / worlds | sealed ownership / dupe forecasts | our entries | graded actuals | DK standings (entries; ownership rows) | class |
|---|---|---|---|---|---|---|
| 2026 W1 (16 games) | V1 candidate sealed forecasts, pre/post inactives (`nfl/research/live/2026_01_*`). 150 of 164 `run_status.json` SEALED (`CURRENT_STATE.md` §6, 2026-10-07) | none | none | 1 game (`nfl/research/live/2026_01_SF_LA/REALIZED_OUTCOMES.json`) | none | V1 engine, not the DFS path |
| DET@BUF W2 Showdown | sealed board (`DET_BUF_PREKICKOFF_PROJECTIONS_2026-09-17.md`) | none | 40 (`DKEntries_UPLOAD_DET_BUF_40.csv`) | GRADED (prospective ledger, 1 row) | none | Hard Rock frozen snapshot: `nfl/research/market/DET_BUF_2026W2` |
| IND@KC W2, NYG@LAR W2 Showdown | pre/post-inactives boards (`nfl/research/sunday/`, `showdown_fixture/`) | none | DKEntries in `nfl/dfs/salaries/raw/` | not inventoried | none | INCOMPLETE_EVIDENCE |
| W2 Early Classic | board `V1_CANDIDATE_R9_W1P_GSVUCY`, UNSEALED | none | 73 (`OWNERSHIP_ACQUISITION_MANIFEST.json`) | 133 player-games / 7 games: r 0.6927, bias −0.1088 | **not archived** | — |
| W3 Early Classic | `DK_WEEK3_PROJ_V1.json` etc. | none | entered (manifest) | not found | **not archived** | — |
| PHI@CHI W3 Showdown | **none** (no salary file) | none | owner hand lineup | — | 196036243: 47,562; 82 | INCOMPLETE_EVIDENCE |
| PIT@CLE W4 Showdown | flat STATE/PROJ/DRAWS; **reproduces 0 of 45 players** | none | 78 entries / 4 contests (owner played a hand lineup) | prospective ledger AWAITING | 196187080 only: 47,562; 79 | PORTFOLIO_ONLY / SCORING_ONLY |
| **W4 Early Classic** | lock `039cfd0e`, seal 2026-10-04 16:01Z, `DK_2026W4_EARLY_WORLDS.npz` | none pregame (∝FC graded retro) | 173 lineups | 201 players: MAE 4.45, Spearman 0.68. 34% outside p10–p90 | 196208416: 35,671; 390. 196208417: 14,268; 299. 196208418: 11,890; 285 | development (∝FC vs ∝FC² chosen on it) |
| **ATL@NO W4 Showdown** | 7 scenario dirs; PIT manifest `PIT_MANIFEST.ATL_NO_2026W4.1294f0dc638d95c9.json`; upload `8f4d9a77` | BLEND / FC_ONLY shadows; B4 dry run (ATL excluded) | 172 | 30 players | 196285137: 237,812; 102. 196285160: 47,562; 97. 196285161: 59,453; 97 | FULL_REPLAY_ELIGIBLE, but development (used ≥ 3×) |
| **TB@DAL W5 Showdown** | OFFICIAL frozen, 97 files hashed (`PREGAME_FREEZE_MANIFEST.json`), R1 upload | BLEND, FC_ONLY, SC-OWN-2 (cand/base), B4, B3S, all sealed and graded | 190 / 3 contests | 49 players, AGREE 528/528 vs nflverse | 196438543: 237,812; 91. 196438555: 47,562; 83. 196438556: 47,562; 85 | **only clean prospective Showdown slate** |
| W5 Early Classic (today) | research universe 266 players × 2,000 worlds (`nfl/dfs/salaries/runs/w5_final/`, gitignored); APPEAR-SUCCESSOR-1 seal (437 units); QBCTX W5 forecasts (16 clubs) | ∝FC incumbent / ∝FC² challenger, to be frozen | 190 entries, all one lineup (`CLASSIC_READINESS_AUDIT_2026-10-10.md`) | pending | pending owner export | prospective |

Counts:
- **Showdown slates with standings:** 4 (PHI@CHI, PIT@CLE, ATL@NO, TB@DAL), 8 contests.
- **Showdown slates with pregame salaries:** 3 of those 4.
- **Showdown slates with a frozen pregame forecast that reproduces:** 2 (ATL@NO and TB@DAL).
- **Classic slates with standings:** 1 (W4), 3 contests.
- **Payout tables:** none, for any slate (`docs/HISTORICAL_REPLAY_FEASIBILITY.md`).
- **DK pools (salaries):** W2/W3/W4/W5 Early, IND@KC, NYG@LAR, PIT@CLE, ATL@NO, TB@DAL (`nfl/dfs/salaries/raw/`,
  `nfl/dfs/inbox/store/`).
- **FC exports:** `nfl/dfs/salaries/raw/THIRDPARTY_*_CONTEXT_ONLY.csv`.
- **Hard Rock boards:** DET@BUF W2, the W2 Early 1PM board and IND@KC W2 (`nfl/research/market/`). ATL@NO has
  `NO_VALID_PRELOCK_MARKET_CAPTURE`.

### 2b. Historical data, 2021–2025

| item | present | path | note |
|---|---|---|---|
| Play-by-play | 2021–2025, plus 2026 captures | `nfl/research/postgame/pbp_20{21..25}.*.csv.gz`; `nfl/vintage/pbp_*` | Track 1 raw pbp gitignored, re-fetchable |
| Player-game DK history | 2021–2025 = 26,944 player-games (5,440 / 5,398 / 5,399 / 5,334 / 5,373); 2026 = 955 (weeks 1–3) | `nfl/warehouse/PLAYER_GAME.json` | current DK rules; `snap_counts` UNKNOWN in the warehouse |
| Team-game panel 2000–2026, **with nflverse closing spread / total / moneyline** | yes | `nfl/warehouse/TEAM_GAME.json`, `MARKET_VOLUME.json` | OUT-036 withdrawn: "27 seasons of closing lines" exist. Evaluation-only by rule. The note in `nfl/derived/FORWARD_CHAIN.json` saying none exist is stale |
| Injury reports | 2020–2025 | `nfl/research/inputs/inj_20{20..25}.csv.gz` | 2020–2024 are "retrospectively chronology-defensible" (`nfl/research/p2/stage_a.py:46`). **2025 has no `date_modified`**, so it carries no injury feature. Not a captured pregame vintage |
| Depth charts | 2020–2024 plus 2025 daily | `nfl/research/inputs/dc_*.csv.gz`, `dc25_daily.csv.gz` | point-in-time adjacency possible |
| Snap counts | 2024, 2025 only | `nfl/postgame/raw/role_audit_history/` | realised post-game, not pregame |
| Usage / role / redistribution / forward chain | yes | `nfl/derived/USAGE_HISTORY_2021_2026.json`, `nfl/warehouse/ROLE_HISTORY.json` (rank is same-week, so it **leaks** if used as an input: `nfl/research/rolestate/VERDICT.md`), `REDISTRIBUTION_STUDY.json`, `FORWARD_CHAIN.json` (28 weeks, conditional on playing) | `nfl/derived/` is gitignored and rebuilt by `nfl/tools/rebuild_derived.sh` |
| DST/K history | 2021–2025, 2,718 club-games | `nfl/research/dst_scoring/DST_K_HISTORY_2021_2025.json` | DK DST integer in 100% |
| `stats_player_week_2021–2025` | **referenced by sha only, not committed** | `STAR_DUD_RATE_2021_2025.json` `sources_sha256` | re-fetch needed to re-derive tails |

Missing, checked rather than assumed:
- **Historical DK salaries.** None ("no historical DraftKings salaries exist in this checkout",
  `nfl/research/shrinkage/VERDICT.md`).
- **Historical ownership or standings before 2026 W3.** None.
- **Payouts.** None, ever.
- **Historical weekly rosters and game-day inactives, 2021–2025.** None (OUT-038 open). Historical predicted lineups
  and pregame inactive lists are therefore absent, and `FORWARD_CHAIN.json` records `ROLE_STATE_NOT_RECONSTRUCTIBLE`.
- **Historical player-prop lines.** None.
- **Other data.** No participation or routes (`pbp_participation` not captured; FTN is a sealed one-game sample), no
  coverage, OL grades or tracking (OPP-ADJUST-1 "Data that is missing").

What this supports:
- **Supported:** forward-chained, point-in-time football evaluation 2021–2025 of opportunity, team volume, efficiency,
  TDs, DK point distributions and tails, using injuries to 2024 and depth charts.
- **Not supported:**
  - salary, value or ownership models historically;
  - historical contest or field simulation;
  - oracle-free appearance with pregame inactives before 2026;
  - EV/ROI, at any time.

---

## 3. Known open defects affecting forecasts or lineups (unrepaired)

| id | defect | measured magnitude | path |
|---|---|---|---|
| **D-01 / W5-G5** | Star lower tail too thin | Projected 20+: simulated P(<5) **0.62%** vs **4.92%** historical; WR 6.57% [4.01, 9.49]. Projected 15–20: 2.34% vs 10.26%. 40 of the top 40 W5 players fall below the lower 95% bound. Lamb 0.0045 (actual 2.9). The comparator bins on realised ppg, so these shortfalls are lower bounds | `nfl/dfs/salaries/classic_early_2026W5/world_audit/WEEK5_WORLD_CORRECTNESS_AUDIT.md` §4; `TB_DAL_DEFECT_REGISTER.json` |
| D-04 | No between-game share volatility | Lamb weekly share 0.119–0.488 vs a projected 0.314 | `TB_DAL_DEFECT_REGISTER.json` |
| **D-05 / W5-G6** | Worlds violate accounting | W5 Classic: receiving ≠ passing yards in **30,641 / 32,000** club-worlds; yards without a catch 17,192; receiving TD without a catch 4,151; points below 6 × TD 1,155; DST vs INT 977. 93 cells above 554 pass yards | same §2 |
| **W5-G19** | DST multiplicative anchor | 92–98% of DST worlds non-integer; factors 0.563–1.338; DAL P(≥15) 12.95% → 0.35% | `DST_K_SCORING_AUDIT_2026-10-09.md` |
| **W5-G16** | Club-slot table used as P(this player plays) | WR5 table 7.7% vs 67% reappearance (n = 52); RB3 23% vs 75%. In the worlds, zero-world share minus (1 − p_plays) averages **−0.135** (min −0.497). No backup-starts world exists | gap register; world audit §1 |
| **W5-G1 / G18, D-02 / D-03** | QB identity is not consumed by club volume, scoring or shares | Bagent → Williams moves CHI receiving yards by +0.25. TB projected 34.6 attempts against 27 / 25 actual. Daniels 3.3 carries projected against 8 / 7 | gap register; `TB_DAL_REPAIR_PROGRAM.md` §G |
| **W5-G11 / G22** | Pro-rata, club-wide redistribution (QB absorbs RB carries) | QB +1.13 to +2.11 carries when an RB is out. A2 survivor slope 0.495 (carries), −0.161 (targets) | gap register; `A2_RESULT.md` |
| W5-G24 | `current_season_shares` divides by the current club's totals | Allen 0.185 MIA carry share; about 0.10 DK | gap register |
| W5-G4 | No partial-workload or in-game-exit risk; DOUBTFUL is not treated as absent | not quantified | gap register |
| Fumbles | not modelled (`proj_v1.py:419`) | ball-carrier means "slightly high" | world audit §3 |
| Club points | a continuous draw | 95.6–99.65% non-integer; 2.65–4.1% ties | world audit §2 |
| Club environment over-reacts | incumbent held-out slopes 0.59 / 0.59 / 0.67; v4 drift +0.996 snaps / +0.605 dropbacks | `OPP_ADJUST_1_RESULTS.md`; `TEAM_VOLUME_DRIFT.md` |
| Cohort-prior collapse | 46 TEs share 1 prior at 0.964 blend weight. Daniels blended 50/50 with an ARCHETYPE 0.068 prior | `shrinkage/VERDICT.md`; `docs/QB_REGIME_ROOT_CAUSE_2026-10-08.md` |
| Efficiency mean at high volume (QB V1 chain) | `pyds\|cmp` 40+ attempts bias +19.80, slope 0.728. `rec_yds` 10+ targets +2.538 | `Q7_DECISION.md` |
| **D-06 / W5-G7** | Ownership, duplication and payout absent from selection | "Ownership enters nowhere" (`showdown_portfolio.py:18-29`). B4 level off about 6–9×. Fitted ownership loses to the no-fit model | tournament plan §1–2 |
| D-07 | Two 20-max contests get identical portfolios | Showdown and Classic | `TB_DAL_DEFECT_REGISTER.json`; `CLASSIC_READINESS_AUDIT_2026-10-10.md` |
| W4 Classic concentration | WR1 share −6.4 pts [−12.6, −0.2]; WR3+ +8.3 [+4.2, +12.2]. One slate; W2 measured the opposite (HHI 0.1588 vs 0.1889) | `nfl/dfs/salaries/postgame/WEEK4_POSTGAME_REPORT.md`; `week2_what_failed_what_held.md` |
| W5-G25 | No verified automated in-window inactives executor | none succeeded since week 1 | `docs/sunday_executor/SUNDAY_INACTIVES_EXECUTOR_AUDIT_2026-10-10.md` |

---

## 4. Ranked candidate next hypotheses (not settled, not already registered)

**Already in flight. Do not duplicate, and do not change their incumbent during their windows:**
- AP-1 and RC-1 (W6–W11, ≥ 150 club-weeks);
- APPEAR-SUCCESSOR-1 (sealed W5, ≥ 4 graded weeks);
- QBCTX-DB1 (W6–W14, ≥ 40 QB_CHANGE games);
- SC-OWN-ROTATION-2 (N = 4 Showdown slates; failing at 1/4);
- B4/B3S §7;
- ∝FC vs ∝FC² (W5);
- the D-12 ledger;
- Q9 hurdle (frozen, 0 prospective rows).

The largest measured opportunity defect (W5-G16 appearance) is **already** under AP-1 and APPEAR-SUCCESSOR-1.

Ranking = decision impact × evidence strength × testability.

### 1. H-TAIL: a mixture lower tail for player DK distributions

**Hypothesis.** Add an in-game early-exit / partial-game component and between-game share volatility, estimated on
prior seasons. This should fix the star bust-rate shortfall without moving means.

- **Evidence.** D-01: 0.62% vs 4.92% (WR 6.57% [4.01, 9.49]); 40/40 top W5 players affected; seen on TB@DAL, ATL@NO
  (Olave 0.005) and W5. W4 Classic high-exposure players: 38.5% fell below p10 (n = 13).
  Sources: `STAR_DUD_RATE_2021_2025.json`, `WEEK5_WORLD_CORRECTNESS_AUDIT.md`, `WEEK4_POSTGAME_REPORT.md` §3.
- **Decision it changes.** Lineup construction and portfolio: star and captain exposure, and stacks. The world audit
  says "bias TOWARD stars … understated 3–23×".
- **Held-out data.**
  - Fit 2021–2024 on `PLAYER_GAME.json` / pbp, with 2025 as development.
  - Re-run frozen 2026 inputs (TB@DAL OFFICIAL; ATL@NO under its PIT manifest; W4 Classic lock `039cfd0e`; W5 once
    graded) as a pre-kickoff check, about 4 slates and roughly 550 player-games.
  - Confirm prospectively from W6.
- **Main leakage risk.**
  - The historical comparator bins on realised season ppg; re-bin by pregame projection.
  - Exit rates must come from prior seasons only.
  - Do not select on TB@DAL (Lamb).
- **Design caution.** Q7 and Track 1 showed that dispersion changes do not move CRPS. Declare tail-specific primary
  endpoints in advance (threshold Brier for P(DK < 5), quantile loss at p05 / p10), with CRPS non-inferiority and
  means held fixed.
- **Thin.** Prospective 2026 graded slates for this pipeline are only about 4.

### 2. H-SUBST: conditional substitution in place of pro-rata, club-wide redistribution

This is the A2 successor and the never-run Track 3. Out-player volume should spread down the room and out of it, not
to already-large survivors or the QB.

- **Evidence.**
  - A2: 1,257 shocks; slopes 0.495 (carries) and −0.161 (targets); 6.1–22.8% of work leaves the room.
  - Surviving starter over-fed: ratio 1.186 (Q6) and 1.162 (Q8).
  - W5-G22: QB +1.13 to +2.11 carries.
  - W4 Classic: WR3+ got more than twice the targets we gave them.
- **Counter-evidence.** Q8 puts REDIST at under 1% of population-wide movement, so the impact is concentrated in
  injury weeks.
- **Decision it changes.** Projections for teammates of Out players, and therefore value plays and the ownership
  disagreements that follow.
- **Held-out data.** 2022–2024 development; 2025 (read before); 2026 prospective, using captured designations and
  inactives in `nfl/vintage`.
- **Main leakage risk.**
  - A2 defines a shock by **realised zero opportunity**, which is outcome-defined and includes in-game exits.
    Shocks must come from pregame Out / Doubtful status (`inj_2020–2024`; 2025 has no chronology) or from 2026
    captures.
  - Adjacency must come from point-in-time depth charts (`dc_*`), never `ROLE_HISTORY`.
  - OUT-038 (historical rosters and inactives) is still missing.
  - It touches the allocator that AP-1 and RC-1 test, so it must be a separate shadow arm.

### 3. H-DUPE: a calibrated level for field duplication

**Hypothesis.** A legal-field sampler whose marginals match the no-fit ∝FC ownership, plus a declared
chalk-concentration term, predicts the copies of our lineups.

- **Evidence.**
  - B4 Σactual / Σpred 0.16 with Spearman 0.708 (TB@DAL).
  - ATL@NO duplication was 3–6× above independence even with actual ownership (15,823 vs 5,334).
  - The median TB@DAL field entry shared its lineup with 42 others; the winner was shared 18 times; ATL@NO 6th place
    was a 120-way tie.
  - Sources: `TB_DAL_2026W5_SEALED_FORECAST_GRADES.json`, `ATL_NO_POSTGAME_REPORT.md`, tournament plan T2 / T3.
- **Decision it changes.** Portfolio construction (duplication avoidance). It matters only once an objective consumes
  it, and an EV objective is blocked by the missing payout tables.
- **Held-out data.** LOSO over 8 Showdown contests (3 slates with salaries) plus 3 W4 Classic contests, then prospective.
- **Main leakage risk.**
  - Feeding actual %Drafted as the marginals is an oracle.
  - Tuning the concentration term on the scored fold.
  - ATL@NO is development data.
- **Thin.** 3–4 folds. It needs a new id and pre-registration, separate from B4 §7 and SC-OWN-2.

### 4. H-COHORT: prospective confirmation of cohort-prior cap 0

The `ROLE_GROUP`, `ARCHETYPE`, `TEAM_CONTEXT` and `POSITIONAL_BROAD` tiers would get cap 0, with player-own tiers
left at 2.

- **Evidence.** Δρ +0.0256 (z 18.0) on confirmation. Production ranks last on both splits. The cap of 2.0 was "selected
  on differences far below their own noise". The cohort prior also drove the Daniels dilution.
  Sources: `shrinkage/VERDICT.md`; `QB_REGIME_ROOT_CAUSE_2026-10-08.md` §1.
- **Decision it changes.** Projection ranking, and therefore lineups.
- **Held-out data.** Frozen 2026 W6+ pregame states (and W2–W5 point-in-time replays as development only).
- **Main leakage risk.** Low. The confirmation season (2022) was already read. Editing `proj_v1` breaks the
  SC-APPEAR-1 replay pin (W5-G24 note), so this must run as a shadow arm.
- **Expected gain.** Small: +0.015–0.034 ρ on a base of about 0.48.

### 5. H-ENV: calibration-slope shrink of the club environment

The club environment here means the points centre and volume.

- **Evidence.**
  - Incumbent held-out slopes 0.59 / 0.59 / 0.67 (n = 1,088); a training-fit shrink moves points MAE from 7.661 to
    7.536, which is larger than the opponent effect.
  - Q8 budget slope 0.575.
  - v4 drift +0.996 / +0.605.
  - Sources: `OPP_ADJUST_1_RESULTS.md` (incidental, **not pre-registered**); `Q8_DECISION.md`; `TEAM_VOLUME_DRIFT.md`.
- **Decision it changes.** Team totals, which feed the TD pool, stack choices and DST.
- **Held-out data.** The point-in-time frame `nfl/research/opponent_adjustment/build_frame.py` for 2021–2025, then
  2026 W6+ prospectively (about 416 club-games).
- **Main leakage risk.** 2024–2025 have already shown this effect, so only prospective data can confirm it. No market
  total may be used as an input.
- **Distinct from settled work.** This is a shrink, not "forecast volume better". Q8 showed that a global budget
  shrink harms zero-target players, so it must be scored downstream per stratum.

### 6. H-OBJ: a field-aware, rank-based portfolio objective

**Hypothesis.** An objective that sees field duplication beats the 0.9 × optimum coverage proxy on exact field ranks
(top-1% rate, prize-split-adjusted rank).

- **Evidence.** Thin and anecdotal:
  - the TB@DAL hindsight-best lineup was in no candidate pool (ex-ante mean 77.4);
  - the ATL@NO payout was a single tied lineup.
  - Source: tournament plan §1–2.
- **Data.** Exact ranks are computable on ATL@NO (development), TB@DAL and W4 Classic: **3 slates**.
- **Blocked.** Payout tables are missing, so EV/ROI is not testable. It depends on H-DUPE and H-TAIL.
- **Main leakage risk.** Optimising toward yesterday's top 1% (plan §2 warns about exactly this).
- **Low priority until payouts are archived** (outbox).

**Not ranked.** The DST club-adjusted component draws, which replace `anchor_means`, are an owner-directed bounded
repair with a history-based acceptance test (integers in 100% of 2,718 club-games; KS). They are correctness work,
not a research hypothesis, and their decision impact is small (`DST_K_SCORING_AUDIT_2026-10-09.md`).
