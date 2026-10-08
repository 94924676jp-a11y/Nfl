# Why the engine did not use Daniels' week-4 start: root cause, 2026-10-08

**Owner directive.** The engine had TB's week-4 game, which Daniels started and Mayfield did not play, in its own
data. It did not recognize what that game meant, and the owner had to point it out.

**Evidence below:**
- tonight's projection, `PRECOMPUTE_TBQB_DANIELS_R10/SHOWDOWN_TB_DAL_2026W5_PROJ.json`;
- the automatic audit, `nfl/tools/qb_regime_audit.py` → `QB_REGIME_AUDIT_PRECOMPUTE_TBQB_DANIELS_R10.json`.

**Nothing in the forecast was changed.**

## 1. Where QB identity is lost: exact code and numbers

| Stage | Code | Input actually used | Result |
|---|---|---|---|
| Starter identity | `showdown_slate_state._starter_context`, guarded by `showdown_run_guards.verify_starter_state` | Daniels starting; Mayfield OUT | **Correct** |
| Week-4 statistics | `player_prior` panel; `TEAM_GAME` | present and lawful at the cutoff | **Present** |
| Daniels' carries (3.39) | `proj_v1.project_player` → `_combine` (`proj_v1.py:~560`) | `carry_share`: current 0.173 = 9/52 over **both** games he appeared in (week-3 relief: 1 carry; week-4 start: 8). Blended **50/50** with an ARCHETYPE cohort prior of 0.068 | **Starts and relief appearances are pooled; the prior is a generic cohort, not his mobility.** His start alone is 8/31 = 0.258 |
| Daniels' passing (4.96 yds/att) | the same `_combine` | current 4.48 (148/33, relief pooled) blended 50/50 with cohort 5.44 | A coincidence of the blend. **It is not evidence of accuracy** (an earlier statement is withdrawn) |
| Club volume and centre | `proj_v1.team_volume` (`:167`); `football_points.expected_points` (`:68`) | 4 current club-games plus 4 prior pseudo-games, **with no QB argument** | The Daniels game is about **⅛** of the weight. TB is projected at 35.3 pass attempts against 30 in his start |
| Teammate targets | `proj_v1` `target_share` `_combine` | all club-games pooled, plus the prior | The Daniels game is about **⅙** of each teammate's weight |
| Receiver efficiency | `showdown_draws._shares` → `sim/game` catches | the receiver's own catch rate; the QB's completion rate is not consumed | QB-invariant |
| Joint worlds | `classic_slate_run.efficiency_worlds` | independent per-player yard factors | Receivers about 30 yds/game above Daniels' passing |
| Lineups | `showdown_portfolio` | those worlds | Egbuka captain 8 → 14 under Daniels |

**Teammate shares in Daniels' start, against the other three games, against our projection** (from the audit):

| Player | Share in Daniels' start | Share in other games | Our projected targets |
|---|---|---|---|
| Egbuka | 0.154 | 0.211 | 7.75 |
| Godwin | 0.269 | 0.116 | 4.61 |
| Otton | 0.231 | 0.179 | 7.01 |
| Irving | 0.000 | 0.158 | 4.06 |

These are one game. They are descriptive and are not estimates.

**The common cause.** Every evidence window is built from club-games pooled regardless of who started. No step
separates starts from relief, and no step splits team history by quarterback.

## 2. Why it was not discovered earlier

Several causes, together:

1. **Missing starter-history feature.** No representation of "games this QB started for this club".
2. **Missing conditional modelling.** Team volume, scoring and teammate shares have no QB argument.
3. **Weighting that dilutes the regime.** The only Daniels game carries ⅛ (team) and ⅙ (teammates) of the weight.
   His start is pooled with a relief cameo and averaged 50/50 with a generic cohort.
4. **Missing dependency propagation:** edges QB1–QB5 in `DEPENDENCY_GRAPH_SHOWDOWN_v0.json`.
5. **Missing validation test.** Nothing checked that a projection consumed the starter's own starts.
6. **My own process.** Today I computed Daniels' 0.116 share and gated READY on it, and I measured the historical
   QB-change association. I never opened the game behind the 0.116. A gate that reports a share without showing the
   games behind it hides exactly this.
   **Worse than not looking:** at 2026-10-07 17:20Z this project's own `docs/AGENT_OUTBOX.md` recorded *"Baker Mayfield
   was INACTIVE in week 4 (thumb); Jalon Daniels started (30 att)"*. The fact was known and written down, and it was
   never turned into an evaluation of the offence. Writing a fact into a request log is not consuming it. This is the
   failure the regime audit exists to make impossible.

## 3. What now runs without being asked

**`nfl/tools/qb_regime_audit.py`**, for both clubs of a slate, reports:
- the current starter against the dominant QB of the modelling window;
- attempt shares by QB;
- the starter's starts and relief appearances;
- team volume and points in his starts against the other games;
- his own lines;
- for each of his projection inputs: how many games were pooled, how many were starts, the prior tier and weight, and
  the flags `RELIEF_POOLED_WITH_STARTS` and `GENERIC_COHORT_PRIOR`;
- every teammate's share in his starts against the other games, and the weight his games carry;
- the response against the other-QB scenario;
- the status of every QB-dependent edge.

It is diagnostic only. It runs tonight after the final run (trigger), and it is wired into the runner after tonight
behind a matched regression.

**Permanent guard: `nfl/tests/test_qb_regime_audit.py` (8/8).**
- It fails if a club in a regime change is reported as needing no QB conditioning, or as COMPLETE, while its QB edges
  are not consumed.
- It also fails if the audit stops finding TB's regime change, Daniels' start and relief split, or his pooled inputs.

## 4. Correction plan (strengthened by the owner, 2026-10-08)

**Owner rulings that bind every step:**
- **No single-game overfitting.** Separate starts from relief, then use **hierarchical partial pooling**. The pooling
  covers the QB's own profile, his starts, comparable QBs (mobility, experience), the club and coaching context, the
  opponent, and historical reliability. Shrinkage is set by sample size. One start informs; it does not dominate.
  Godwin's 26.9% in Daniels' start against 11.6% is evidence, not a forecast.
- **Detection is not a solution.** Starter identity must reach, through executable consumers with validation
  evidence:
  - team volume and scoring;
  - QB passing and rushing;
  - receiver targets and catchability;
  - RB opportunities;
  - touchdowns and efficiency;
  - the joint worlds;
  - the opponent's DST and the kicker.
- **Accounting correctness comes first** (event-based passing and scoring arms) before more DFS-optimizer work.
- **An evidence-response report for every slate, unprompted:**
  - what new football information existed;
  - whether it entered the model, and its estimated influence and uncertainty;
  - which material dependencies remain missing.

**Steps:**

Each step is a separate change, shadow first, and evaluated against the incumbent. No one-game adjustment is made.

1. **Role-aware evidence windows inside a partially pooled model.** Starts and relief enter as separately weighted
   evidence, never as a starts-only replacement. Arm `QBCTX_2026_10_ROLE`; it changes outputs, so shadow only.
2. **QB rushing by identity.** Designed runs and scrambles per dropback, partially pooled toward a mobility-aware
   prior rather than a generic cohort, weighted by sample size. Daniels' NFL evidence is 9 carries.
3. **QB-split team history as a prior.** Team volume and centre by QB regime, shrunk to the club (SC-QB-ENV-1).
4. **Teammate shares by QB regime**, with shrinkage (QBCTX-M3).
5. **The same audit for every role.** RB1, WR1, TE1, OL, defence and coach: who produced the history against who
   plays, using the same majority rule.
6. **Every club, historically.**
   - All 2021–2025 primary-passer changes, as the Perplexity 311-row screen and the 719 cases already measured.
   - These are outcome-labelled until pregame starter evidence is joined.
   - 2026 is prospective from week 6.

## 5. The development standard, as the owner set it

**Both questions are mandatory for every slate:**
1. Did the pipeline execute correctly?
2. Did it use the relevant football evidence and model the dependencies?

The regime audit and the accounting checker are the first two automatic answers to question 2.
