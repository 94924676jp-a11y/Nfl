# H1 pre-registration: the top of the projection board is over-projected, 2026-10-11

Status: **PRE-REGISTERED.** Written after the development diagnosis (2024-2025) and **before** any confirmatory data
or any confirmatory evaluation of the candidate. It freezes the hypothesis, the candidate, the data roles, the
metrics, the decision rules and the verification protocol.

Research only:
- no production change, no promotion;
- no market input; nothing from FantasyCruncher used as an input;
- the production incumbent is not touched.

Registered tests already running are not duplicated and must not be disturbed: AP-1, RC-1, APPEAR-SUCCESSOR-1,
QBCTX-DB1, SC-OWN-ROTATION-2, B4/B3S and Q9 (landscape map, `/tmp/claude-0/landscape/LANDSCAPE.md`).

## 1. The defect, measured on development data (2024-2025)

**Source.** The repository's own forward chain (`nfl/tools/forward_chain.py`, unmodified), production arm (blend
1.0, `PRIOR_WEIGHT_CAP = 2.0`, `nfl/tools/proj_v1.py:104`):
- 28 scored weeks;
- 12,203 pool player-weeks, of which 7,182 played;
- every projection made from strictly earlier weeks.

Scripts: `capture_rows.py` (reads the repository, writes only its own output), `diagnose.py`, `eval_h2.py`.

**Defined against predictions** (governing rule): players are grouped by projection, never by outcome. For a
calibrated forecaster, E[actual | projection] = projection in every projection group, however noisy outcomes are.
A group chosen by its projection and over-projected in 28 of 28 weeks is therefore a calibration defect, not
regression to the mean.

| measure (production arm, players who played) | value | 95 % interval (weeks resampled as blocks) |
|---|---|---|
| **top quartile of each position's weekly projection: projected / scored** | **1.137** | [1.112, 1.167], n = 2,417 |
| top decile, all positions | 1.146 | |
| top 12 QB / 24 RB / 36 WR / 12 TE per week, every pool candidate: projected minus scored | +3.30 / +5.49 / +6.59 / +5.58 pts | over-projected in 23 / 28 / 28 / 27 of 28 weeks, both seasons |

**Production shows the same sign on the archived slates where it can be checked.**
- Week-4 early Classic, top 30 by locked projection: 19.47 projected / 17.73 scored (1.098), n = 201.
- ATL@NO showdown: slope 0.904, n = 30.
- These are single slates with wide intervals; the direction is consistent.

**Three things are deliberately not this hypothesis:**
- **Not playing.** About 3.3 of the top decile's 6.05-point unconditional excess comes from players who did not
  play. The chain cannot see injury reports or inactives; production can. Appearance is AP-1's and
  APPEAR-SUCCESSOR-1's subject.
- **The whole-population slope (0.596).** It is dragged down by players projected near zero who then played. That
  is outcome selection (Q8's documented trap, `nfl/research/q8/Q8_DECISION.md`). A first candidate fitted on it
  over-corrected the top decile to 0.78 on development data, so it was discarded before this freeze.
- **The distribution's lower tail.** That is H-TAIL's subject. H1 is about the mean at the top of the board. A
  missing bust or early-exit component would raise exactly these means, so H-TAIL and H1 may share a cause; they
  are tested as separate arms.

**Exploratory, one slate** (week-4 early top 30): yards per opportunity overshoot more than opportunity — receiving
yards 1.267 and rushing yards 1.352, against targets 1.134 and carries 1.071. This is H1b below, not a finding.

## 2. Hypotheses

- **H1 (primary).** Among players who play, the top quartile of each position's weekly production projection is
  over-projected: ratio > 1.05, with a 95 % week-blocked interval above 1.00.
- **H1b (mechanism).** The excess is larger in efficiency (yards and touchdowns per opportunity) than in
  opportunity (targets, carries, attempts).
- **H2 (repair).** The frozen candidate in section 4 improves error on the top quartile without harming any
  predeclared stratum.

## 3. Data roles (no retrospective information)

| role | data | how clean |
|---|---|---|
| development | 2024-2025 forward chain | **used** for section 1 and to redesign the candidate once; cannot judge H1 or H2 |
| check A | 2022-2023 forward chain, same harness and arm | **not clean for the project**: earlier studies (Q8, 2022-2025) read these seasons. Never computed for this metric or this candidate. Run once after this commit. It can **refute**; it cannot confirm. |
| check B | archived pre-kickoff production projections of 2026 slates with graded actuals | partly seen: week 4 and ATL@NO are quoted above, so they count as development. TB@DAL (week 5) is the one frozen-then-graded slate no candidate was selected on. |
| **confirmatory** | **2026 week 6 onward, prospective.** The candidate runs in shadow beside production on each slate's locked projection and is graded after the slate | **the only untouched evidence** |

**Leakage controls:**
- every correction factor is fitted only on weeks strictly before the week it is applied to;
- prospectively, only on graded weeks before the slate;
- nothing from a later season fits anything evaluated on an earlier one;
- DK actuals are used only for scoring.

## 4. Candidate (frozen)

For each position and week, take q75, the 75th percentile of that week's pool projections for the position. Then:

```text
c_pos,w = sum(DK points) / sum(projection)
          over strictly earlier weeks' top-quartile players at that position who played;
          minimum 8 earlier weeks, else c = 1; capped at c <= 1
p'      = min(p, max(q75, c * p))   if p >= q75
p'      = p                         otherwise
```

Properties:
- One factor per position, re-estimated weekly.
- It only ever lowers a projection.
- It is monotone within a position (ties are possible near q75).
- It changes values across positions and against salary, which is where lineup construction reads them.
- It is applied after the projection, so it does not touch the allocator under test in AP-1 and RC-1.

**Development, in-sample (not evidence).** Over 20 fitted weeks:

| measure | production | candidate |
|---|---|---|
| top-quartile ratio | 1.130 | 1.004 |
| top-quartile MAE | | −0.47 pts per player [−0.55, −0.39] |
| overall MAE | | −0.16 [−0.19, −0.13] |
| QB MAE | | +0.04 % |
| RB / WR / TE MAE | | −2.8 / −3.4 / −3.7 % |
| deciles 1-5 | | unchanged |
| deciles 7-10 | | −3 to −7 % |

The fitted factors at the end of 2025 were QB 0.99, RB 0.89, WR 0.84 and TE 0.85.

## 5. Decision rules (frozen)

**H1.**
- **Confirmed** on a dataset if the top-quartile ratio is > 1.05 and its 95 % week-blocked interval lies above 1.00.
- **Refuted** if the interval contains 1.00.
- Check A can only refute.
- The confirmatory verdict comes from prospective 2026 week 6 onward, with **at least 6 graded weeks**.

**H2 accepted for continued shadow** only if all of these hold on the same data:
- top-quartile MAE improves, with a 95 % week-blocked interval that excludes zero;
- overall MAE does not worsen (the interval's upper end is at most 0);
- no position's MAE worsens by more than 1 %;
- no projection decile's MAE worsens by more than 2 % (the stratified-harm rule that rejected Q8_BUDGET_SHRINK);
- the top-quartile ratio moves toward 1.

Anything else is **REJECT**. Promotion is not decided here: it would be a separate owner decision after the
prospective verdict.

**Lineup decisions.**
- On each prospective slate, record the optimizer's lineups under production and under candidate projections (same
  seed, constraints and ownership inputs), with their realised DK points and contest finish.
- Fewer than 10 slates is **descriptive only**. It cannot accept H2; it can raise a predeclared harm flag: candidate
  lineups score lower on a majority of slates.

## 6. Independent verification protocol

1. This file and the scripts are committed before check A is computed. The commit hash is quoted in every result.
2. A reviewer who did not write the candidate does all of the following:
   - re-runs `capture_rows.py` from a clean checkout;
   - recomputes every section-5 number from the raw rows;
   - confirms in code that every fit uses only earlier weeks;
   - attempts to refute H1, by season, by position, excluding players who changed club, and within the top 9 %.
3. Results are reported as CONFIRMED / REFUTED / REJECT exactly as section 5 defines them. Development, check A,
   check B and prospective numbers are kept in separate tables.
