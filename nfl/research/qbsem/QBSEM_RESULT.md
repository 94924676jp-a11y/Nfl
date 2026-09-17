# QBSEM result — the mechanism is sound, the gate fails, nothing is sealed

**Verdict: QBSEM is WITHDRAWN under its own pre-registration. The DET–BUF board
is NOT sealed. The mixed-semantics blocker stands.**

Pre-registration: `nfl/research/qbsem/predeclaration_qbsem.md`, §3: *"If any
gate fails, QBSEM is withdrawn and the mixed-semantics blocker stands,
unsealed."* Gate 1 fails. It is not reinterpreted after the fact.

Candidate identity `V1_CANDIDATE_R9_W1P_GSVUQ`. Baseline `V1_CANDIDATE_R9_W1P_GSVU`.
Both at 8,000 draws, seed 20260908, `written_at` 2026-09-16T15:45:14Z, game
`2026_02_DET_BUF`, same code checkout, one declared component apart.

---

## 1. Why gate 1 fails, and it is not the rate

Gate 1 reads: *"For each QB on the board, simulated `P(db = 0)` must lie within
Monte Carlo error of the realised rate for his cell. Reported per QB; Josh
Allen's target is **0.0694**."*

**0.0694 is the realised zero-dropback rate of cell (1, 1, 0). The production
run does not put Josh Allen in that cell.** It puts him in **(1, 0, 1)**.

| QB | team | board cell | cell n | historical P(db=0) | GSVU sim | QBSEM sim | used |
|---|---|---|---|---|---|---|---|
| Josh Allen | BUF | (1, 0, 1) | 90 | **0.0000** | 0.003875 | 0.002875 | FELL BACK |
| Jared Goff | DET | (1, 1, 1) | 70 | **0.0000** | 0.003000 | 0.002500 | FELL BACK |
| Kyle Allen | BUF | (2, 0, 1) | 133 | **0.8647** | 0.763375 | **0.857625** | own cell rate |
| Joshua Dobbs | DET | (2, 0, 1) | 133 | **0.8647** | 0.762500 | **0.863375** | own cell rate |

So gate 1 has two clauses that now disagree:

- **the named clause** — Allen's target is 0.0694 — **FAILS**. Simulated
  0.002875.
- **the general clause** — "the realised rate for his cell" — **passes on all
  four**, and on the two rows where QBSEM used its own cell rate it passes
  strikingly well: 0.8576 and 0.8634 against 0.8647, from 0.7634 and 0.7625.

**The verdict is taken from the named clause, because that is the one written
down.** A pre-registration that turns out to have named the wrong cell is a
defect in the pre-registration, recorded as a failure. It is not resolved by
choosing whichever clause the result satisfies.

### Where the wrong cell comes from

`QB3_WEEK1_SEASON_BOUNDARY`, already declared on the artifact with
`week1_specification_defect: true`, and already accepted by the owner as the
unresolved rest-state limitation. The chain, every link measured:

1. The QB panel carries no 2026 play-by-play, so `previous_primary_detail`
   falls back. **The previous-primary ordinal in force for 2026 week 2 is
   `202518` for every club** — 2025 week 18.
2. `is_season_opener` is `(ordinal // 100) != season`, which is a fact about
   the gap and not about `week == 1`. With a 2025 ordinal it is **true for a
   week-2 game**, for both clubs.
3. Buffalo rested Josh Allen in 2025 week 18. BUF's previous primary is
   therefore `00-0033869`, not Allen, so `was_prev_primary = 0` and his cell is
   **(1, 0, 1)**. Detroit did not rest Goff, so Goff is (1, 1, 1).
4. Cells (1, 0, 1) and (1, 1, 1) have **P(starter) = 1.0000** — in 90 and 70
   frame rows, **no rank-1 quarterback has ever failed to start at a season
   boundary**. Both cells therefore hold **zero non-starting rows**.
5. With nothing to estimate, QBSEM falls back to `p_reliever_by_rank[1] =
   0.30303` for both starters — the exact rate it exists to replace.

**QBSEM did nothing at all for the two quarterbacks the repair was built for,
and could not have.** The 0.002875 it reports for Allen is consistent with his
board cell's historical 0.0000, and tells us nothing about whether 0.0039 or
0.0694 is the right zero-dropback mass for a quarterback whose incumbency
signal is nine months stale.

**This is the same root cause as the accepted rest-state limitation**, reaching
a second mechanism. It is not a new defect and no third fix is attempted here.

---

## 2. The forward-chained evidence — and the fallback is the problem

`QBSEM_FORWARD_CHAINED.json`. Expanding-window forward chain, one fit per
evaluation season, cut at `season*100+1` so no row of the evaluation season or
later is in its own training set — **stricter than production**, which cuts at
202602. Event: `y = 1[db > 0]` for a depth-charted quarterback who was not the
starter. **3,206 rows, 2,153 team-game clusters, base rate 0.1051**, four folds
(2022–2025). Intervals are clustered by team-game, R = 2,000.

| arm | Brier | log loss | AUC | mean prediction |
|---|---|---|---|---|
| baseline — pooled `p_reliever_by_rank` | 0.47319 | 1.48254 | 0.6223 | 0.6555 |
| **QBSEM — cell rate** | **0.10700** | **0.36918** | 0.6210 | 0.1204 |
| constant — forward-chained base rate | **0.09418** | **0.33680** | 0.4711 | 0.1018 |

Read in that order, three things follow and the second is uncomfortable.

**QBSEM demolishes the shipped baseline.** Brier −0.36619, clustered 95%
[−0.38292, −0.34974]; log loss −1.11336, [−1.16087, −1.06653]; 2,000 of 2,000
resamples favour QBSEM. The old mechanism predicts 0.6555 against a realised
0.1051. That is not a close call and it is the defect QBSEM was built to fix.

**But beating a miscalibrated predecessor is not skill, and against a constant
QBSEM loses overall.**

| comparison | rows | Brier(QBSEM) − Brier(constant) | clustered 95% | P(QBSEM better) |
|---|---|---|---|---|
| all rows | 3,206 | **+0.012818** | [+0.00822, +0.01735] | 0.000 |
| **own cell rate used** | 3,102 | **−0.002668** | [−0.00348, −0.00181] | **1.000** |
| sparse-cell fallback | 104 | **+0.474709** | [+0.39126, +0.55197] | 0.000 |

**The cell conditioning earns its keep exactly where it is used, and the
declared fallback destroys the gain several times over.** 104 rows — 3.2% of
the sample — carry a Brier of 0.5309 against the constant's 0.0562, and that
alone accounts for more than the whole pooled deficit.

The AUC column says why: baseline 0.6223 and QBSEM 0.6210 are the same ranking
ability. The baseline's catastrophic Brier is **pure calibration failure**, not
a failure to discriminate. (The constant's 0.4711 is an artefact — it varies
only by fold, so it "ranks" by fold and the number is not interpretable.)

**The fallback to `p_reliever_by_rank` was pre-registered and it is wrong.**
Falling back to the mechanism QBSEM exists to replace preserves the defect
precisely where the evidence is thinnest. **It is not changed in this pass** —
the pre-registration is not amended after seeing a result. The successor is
named in §6.

### Cell-wise calibration, forward-chained

| cell | n | k | observed | QBSEM | baseline | QBSEM err | baseline err |
|---|---|---|---|---|---|---|---|
| (1,0,0) | 141 | 5 | 0.0355 | 0.0607 | 0.3167 | +0.0253 | +0.2812 |
| (1,1,0) | 128 | 4 | 0.0312 | 0.0412 | 0.3145 | **+0.0099** | +0.2833 |
| (2,0,0) | 1,735 | 262 | 0.1510 | 0.1366 | 0.9270 | −0.0144 | +0.7760 |
| (2,0,1) | 105 | 13 | 0.1238 | 0.3461 | 0.9270 | +0.2223 | +0.8032 |
| (2,1,0) | 61 | 9 | 0.1475 | 0.4385 | 0.9255 | +0.2910 | +0.7780 |
| (2,1,1) | 18 | 0 | 0.0000 | 0.9261 | 0.9261 | +0.9261 | +0.9261 |
| (3,0,0) | 950 | 44 | 0.0463 | 0.0494 | 0.2337 | **+0.0031** | +0.1874 |
| (3,0,1) | 56 | 0 | 0.0000 | 0.1027 | 0.2302 | +0.1027 | +0.2302 |
| (3,1,0) | 8 | 0 | 0.0000 | 0.2441 | 0.2441 | +0.2441 | +0.2441 |
| (3,1,1) | 4 | 0 | 0.0000 | 0.2315 | 0.2315 | +0.2315 | +0.2315 |

The three rows where QBSEM equals the baseline exactly — (2,1,1), (3,1,0),
(3,1,1) — are fallbacks. They are also the three worst rows in the table.
The two best-supported cells, (2,0,0) at n = 1,735 and (3,0,0) at n = 950,
are calibrated to within 0.0144 and 0.0031.

---

## 3. Every acceptance item, stated

| # | item | state | where |
|---|---|---|---|
| 1 | fixed-cohort baseline vs QBSEM | **PASS** | §4, `QBSEM_FIXED_COHORT_DELTA.json`; 29 players, identical cohort, no row added or dropped |
| 2 | cell-wise `P(relieves \| not starter)` calibration | **PASS (reported)** | §2 table, forward-chained, clustered |
| 3 | simulated vs historical `P(db = 0)` by cell | **PASS** | §1 table; 0.8576/0.8634 against 0.8647 where the cell rate ran |
| 4 | Allen-cell target ≈ 0.0694 | **FAIL** | §1. He is not in that cell on this board |
| 5 | Brier and log loss for the participation event | **PASS (reported)** | §2; QBSEM beats the baseline decisively and loses to a constant overall |
| 6 | zero leakage — every cell feature pregame | **PASS** | `nfl/tests/test_qbsem_leakage.py`, 23 checks. Previous-primary ordinals in force: `202518`, all in the past |
| 7 | explicit fallback counts for sparse cells | **PASS** | §1; **2 of 4 quarterbacks fell back**, both starters, counted per player on the artifact |
| 8 | machine-checkable unconditional-semantic parity, QB/RB/WR/TE/K | **PASS, K NOT_EXECUTED** | `nfl/tests/test_publication_semantics.py`; 112 boards, 14,770 metrics, 13,027 discriminating, 0 violations. No kicker exists on any sealed board |
| 9 | exact QB team-volume conservation | **PASS** | §4; 8,000/8,000 draws on both clubs, worst integer deviation **0** |
| 10 | Contract 3 on the unchanged grid | see §5 | grid not extended, contract not amended |

**Item 4 is the gate. It fails. Nothing is sealed.**

---

## 4. Fixed-cohort deltas, 29 players

Same 29 players in both arms — none added, none dropped. Rows resolved through
the manifest's `row_ids`, never board order.

Conservation, QBSEM arm: `sum_i db_i == team dropbacks` in **8,000 of 8,000
draws on both clubs, worst integer deviation 0.0**.

DraftKings means, largest movers first:

| player | tm | pos | GSVU | QBSEM | Δ |
|---|---|---|---|---|---|
| Josh Allen | BUF | QB | 21.9964 | 22.7479 | **+0.7515** |
| Joshua Dobbs | DET | QB | 0.9884 | 0.2641 | **−0.7243** |
| Jared Goff | DET | QB | 17.3906 | 18.0363 | **+0.6457** |
| Kyle Allen | BUF | QB | 0.8300 | 0.2195 | **−0.6105** |
| Khalil Shakir | BUF | WR | 11.5392 | 11.6446 | +0.1054 |
| Dalton Kincaid | BUF | TE | 5.8513 | 5.7475 | −0.1038 |
| Amon-Ra St. Brown | DET | WR | 18.6021 | 18.7013 | +0.0992 |
| Jahmyr Gibbs | DET | RB | 22.2667 | 22.3473 | +0.0806 |

Every remaining non-QB row moves by less than 0.08 DK, and the full table is in
`QBSEM_FIXED_COHORT_DELTA.json`. **The effect is confined to the QB room, which
is what a repair scoped to the QB room should do.** Mean dropbacks: Josh Allen
34.6857 → 35.9354, Kyle Allen 1.7361 → 0.4865; Goff 34.9415 → 36.1835, Dobbs
1.6923 → 0.4502. The starters gain exactly what the backups lose.

### The declared hypothesis on `qb/pyds` p90 instability — and it is not what it looks like

Pre-registration §5 recorded this as a hypothesis with a predeclared test, and
said Contract 3's verdict does not depend on it. Bootstrap sd of the empirical
p90, R = 400, the estimator Contract 3 uses:

| QB | GSVU sd | QBSEM sd | change |
|---|---|---|---|
| Jared Goff | 2.5158 | 1.7940 | −0.7219 |
| Joshua Dobbs | 1.4712 | **0.0000** | −1.4712 |
| Kyle Allen | 1.8408 | **0.5885** | −1.2523 |
| Josh Allen | 2.2403 | 2.0320 | −0.2082 |

**My prediction on record was that it would not fall materially. It fell for all
four, and I was wrong about the direction.** But the two large falls are
**degeneracy, not stability**: under QBSEM the backups' `P(pyds = 0)` is 0.9086
and 0.9116, both above 0.90, so the p90 lands *inside a point mass at zero* and
its bootstrap sd is 0.0000 because the statistic is constant, not because the
tail settled. Reading that as a convergence gain would be wrong.

The honest figures are the starters': Goff −29%, **Josh Allen −9% (2.2403 →
2.0320)**. Real, and small. Contract 3 is not relaxed on the strength of it.

---

## 5. Contract 3

Run on the already-predeclared grid n ∈ {1000, 2000, 4000, 8000, 16000}. **The
grid is not extended and the contract is not amended, whatever the result.**

<!-- C3_RESULT -->

---

## 6. What survives, and the successor

**The mechanism is right and the fallback is wrong.** That is the finding, and
it is worth more than the gate.

- `P(relieves | not starter, cell)` beats a forward-chained constant where it
  has its own evidence: −0.002668 Brier, clustered 95% [−0.00348, −0.00181],
  on 3,102 rows. Small, real, and on the correct side.
- The declared fallback to `p_reliever_by_rank` costs +0.4747 Brier on the 104
  rows it touches and turns a net win into a net loss. **The successor should
  fall back to the pooled `P(relieves | not starter)` — the constant arm — not
  to the reliever-identity weight.** That is a mechanism change and takes a new
  candidate identity; it is not an edit to QBSEM.
- Neither of those helps the DET–BUF starters while `is_season_opener` is true
  for a week-2 game. The binding problem on this board is the **staleness of
  the incumbency signal**, not the relief rate. A fix there is a third
  rest-state mechanism and is out of scope by instruction.

## 7. Limitations carried forward

- **Rest-state / season-boundary (unresolved, accepted).** Measured SAT-vs-PLAYED
  differential −0.0715. It now demonstrably drives the QB cell assignment as
  well as R8's recency state. Josh Allen and James Cook carry the caveat.
- **Eligibility-gate double-count (declared, nil exposure here).** The cell rate
  is estimated on a frame including inactive quarterbacks, while at serve time
  the gate has already removed hard-OUT quarterbacks. No 2026 week-2 official
  report exists, so the gate removed nobody on this board.
- **EXPLORATORY.** The cells were chosen on the frame every earlier QB repair
  was selected on. The forward chain controls parameter leakage only.
- **Postseason excluded** from the appearance panel. **Gadget kicker support is
  thin.** **GSP/GSVP remain permanently disqualified** (survivorship-filtered
  panel).
- **K is unexercised** by the semantic-parity tripwire — no kicker row exists on
  any sealed board.

---

**V2 NOT YET EARNED**
