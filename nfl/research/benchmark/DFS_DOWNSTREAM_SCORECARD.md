# DFS_DOWNSTREAM_SCORECARD (mandate b0540a52 phase 5)

**Question.** Does a better forecast become a better DFS portfolio, and what can be measured about that today?

**Short answer.**
- **Expected value is UNAVAILABLE.** There are no lawful prize tables and no field or duplication model (FIELD-D1).
- What is measurable today is selector correctness, candidate recall, and model-world objectives on frozen slates.
  All of these are **diagnostic**: they are scored on one model's worlds.

## 1. Selector: greedy shortfall versus true infeasibility (fixed first, as the mandate orders)

**Defect, SEL-D1.** The default ladder relaxed caps after a *greedy* shortfall, not after proven infeasibility. Cap
level and objective then jumped with pool composition.

**Fix.** SEL-2, `NFL_SHOWDOWN_SELECTOR=FIXED_POLICY_V1`:
- 20-entry contests are held at the policy level (L2);
- a contest that cannot fill is reported **loudly** as UNFILLABLE, never silently relaxed;
- the 150 is untouched.
- Tested in `test_showdown_sel1_fill_repair.py`, with mutation tests.

**Diagnostic result on three frozen slates.** Held-out odd worlds, `RESULT_SEL2_FIXED_POLICY.md`.

| contest | GREEDY | SEL-2 | spread over pool subsamples, GREEDY / SEL-2 |
|---|---|---|---|
| BUF@LAR $5K 20 | 0.801 (L1) | **0.892** (L2) | 0.032 / 0.037 |
| TB@DAL 20 (b) | 1.047 (L1) | **1.131** (L2) | 0.103 / 0.037 |
| BUF@LAR $10K 20 | 0.880 | 0.880 | 0.163 / **0.042** |
| TB@DAL 20 (a) | 1.192 | 1.192 | 0.105 / **0.020** |

- No contest was unfillable.
- **The pre-registered rule failed on one cell:** BUF@LAR $5K, where the spread was 0.037 against 0.032.
- So SEL-2 stays **opt-in**. Owner 2026-10-13: promotion only on `PREREG_SEL2_PROSPECTIVE_W6` evidence.

**SEL-1** (an earlier fill-repair design) failed its test and is retained, not promoted.

**Still open:**
- **SEL-D2:** sequential cross-contest exclusion makes later contests depend on earlier builds.
- **SEL-D3:** the greedy selector is not monotone in the candidate pool.

## 2. Candidate recall at a fixed cap (CAND-D1, CAND-D2)

**Measured.** `RESULT_PORT_D3_AND_WR1OUT_RB2.md`, on BUF@LAR W5 frozen worlds.
- Only **19.4%** of the lineups at or above the pool's own median persistence ever reach the selector (3,012 of 15,540).
- Candidates are generated from, and selected on, the same worlds (CAND-D2).

**Registered fix.** CG-1, `PREREG_CG1_CANDIDATE_GENERATOR.md` @98f88f38:
- disjoint generation, selection and evaluation thirds of the worlds (index mod 3);
- an identical pool size N between arms;
- the selector held fixed at SEL-2 level 2 for the 20s and level 0 for the 150;
- arms: A incumbent, B persistence-ranked, C union control;
- hard gates: zero checker violations, a 10-minute generation budget, identical N.

**Status.** The CG-1 harness is **not built** (ENG-015). It is the next queued DFS engineering item, and it needs no new
data.

## 3. Realised portfolios (what happened; one game each, not evidence of skill)

**TB@DAL W5** (`nfl/postgame/showdown_tb_dal_2026W5/TB_DAL_POSTGAME_REPORT.md`, section C):
- The hindsight-best lineup had a prelock simulated mean of 77.4 and a 95th percentile of 113.0. It was in **neither**
  candidate pool.
- This is a candidate-recall symptom, not a selection error.
- The two 20-max contests received identical portfolios (D-07; this is what SEL-D2's per-contest independence
  addresses).

**Single games cannot rank portfolios.** Owner contest results stay in their postgame folders and are not
re-published here.

## 4. What would make DFS expected value measurable

| need | status |
|---|---|
| prize tables per contest | not lawfully available to the agents (FIELD-D1) |
| field ownership and duplication model | OWN-D1: the trained shadow loses to the FC-proportional baseline on one slate. FC is a benchmark, never an input. |
| realised field lineups | owner uploads only; never committed |
| a forecast that beats an equal-information baseline | **now in view:** D2 passes its 2025 look (RESULT_D2.md); confirmation needs W6+ |

**Order.** Forecast skill first: D2 prospective. Then selector and recall: SEL-2 prospective and CG-1. EV is last,
after lawful field and payout data. No EV number is reported before then, and no lineup is uploaded or entered by an
agent.
