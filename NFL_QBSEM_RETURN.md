# QBSEM — acceptance package, verdict, and what actually got found

**Branch** `claude/nfl-greenfield-architecture-stsxmk`.
**Game** `2026_02_DET_BUF`, kickoff `2026-09-18T00:15Z`, forecasts written at
`2026-09-16T15:45:14Z`.
**Candidate** `V1_CANDIDATE_R9_W1P_GSVUQ`. **Baseline** `V1_CANDIDATE_R9_W1P_GSVU`.

---

## The verdict, first

**QBSEM is WITHDRAWN under its own pre-registration. No board is sealed.
Nothing is promoted. The mixed-semantics blocker stands.**

Gate 1 fails. §3 of `predeclaration_qbsem.md` says a failed gate withdraws
QBSEM, and it does. The gate is not reinterpreted after the fact.

Contract 3 also returns `chosen: null` at every draw count, as it did for GSVU.
The grid was not extended and no threshold was moved.

---

## Two things that went wrong before any of this, stated plainly

**1. The container restarted and took the in-flight GSVUQ run with it. The
QBSEM implementation was uncommitted at the time.** Both recovered; the code is
committed and pushed.

**2. The first GSVUQ run did not die in the restart — it refused.**

```
QB_ALLOCATOR_UNKNOWN: 'qb_room_v2_sem' is not one of ('qb3', 'qb_room_v2').
```

I wired QBSEM's allocator name into every call site that *uses* it and none of
the guards that *validate* it, so naming the mechanism — the entire reason
QBSEM is an allocator name and not a flag — refused every stage downstream. The
guard was right. This is the project's own defect class and it cost a full
8,000-draw run. Fixed, with three reproduction checks in `test_qb_room_v2.py`
that fail on the code which produced the refusal.

---

## Why gate 1 fails, and it is not the rate

The gate named **0.0694** as Josh Allen's zero-dropback target. That is the
realised rate of cell **(1, 1, 0)**. The production run puts him in **(1, 0, 1)**.

| QB | tm | board cell | cell n | historical P(db=0) | GSVU sim | QBSEM sim | used |
|---|---|---|---|---|---|---|---|
| Josh Allen | BUF | (1,0,1) | 90 | **0.0000** | 0.003875 | 0.002875 | FELL BACK |
| Jared Goff | DET | (1,1,1) | 70 | **0.0000** | 0.003000 | 0.002500 | FELL BACK |
| Kyle Allen | BUF | (2,0,1) | 133 | **0.8647** | 0.763375 | **0.857625** | own cell rate |
| Joshua Dobbs | DET | (2,0,1) | 133 | **0.8647** | 0.762500 | **0.863375** | own cell rate |

The chain, every link measured:

1. The QB panel carries no 2026 play-by-play, so the previous-primary signal
   falls back. **The ordinal in force for 2026 week 2 is `202518` for every
   club** — 2025 week 18.
2. `is_season_opener` is a fact about the gap, not about `week == 1`. With a
   2025 ordinal it is **true for a week-2 game**.
3. Buffalo rested Allen in 2025 week 18, so BUF's previous primary is
   `00-0033869` and not Allen — hence `was_prev_primary = 0`, cell (1,0,1).
4. Cells (1,0,1) and (1,1,1) have **P(starter) = 1.0000** across 90 and 70
   rows: **no rank-1 quarterback in this frame has ever failed to start at a
   season boundary.** Both hold **zero non-starting rows**.
5. With nothing to estimate, QBSEM falls back to `p_reliever_by_rank[1] =
   0.30303` for both starters — the exact rate it exists to replace.

**QBSEM did nothing for the two quarterbacks it was built for, and could not
have.** This is the already-accepted rest-state limitation reaching a second
mechanism, not a new defect, and no third fix is attempted.

The gate's *general* clause — "the realised rate for his cell" — passes on all
four, strikingly so where the cell rate actually ran. **The verdict is taken
from the clause that was written down.** A pre-registration that named the
wrong cell is a defect in the pre-registration.

---

## The evidence: the mechanism is right and the declared fallback is the defect

Forward-chained, one fit per evaluation season, cut at `season*100+1` — stricter
than production. **3,206 rows, 2,153 team-game clusters, base rate 0.1051**,
folds 2022–2025, intervals clustered by team-game, R = 2,000.

| arm | Brier | log loss | AUC |
|---|---|---|---|
| baseline `p_reliever_by_rank` | 0.47319 | 1.48254 | 0.6223 |
| **QBSEM cell rate** | **0.10700** | **0.36918** | 0.6210 |
| constant, forward-chained | **0.09418** | **0.33680** | 0.4711 |

QBSEM demolishes the shipped baseline — Brier −0.36619, clustered 95%
[−0.38292, −0.34974], 2,000 of 2,000 resamples. **But beating a miscalibrated
predecessor is not skill, and against a constant QBSEM loses overall.**

| comparison | rows | Brier(QBSEM) − Brier(constant) | clustered 95% | P(QBSEM better) |
|---|---|---|---|---|
| all rows | 3,206 | **+0.012818** | [+0.00822, +0.01735] | 0.000 |
| **own cell rate used** | 3,102 | **−0.002668** | [−0.00348, −0.00181] | **1.000** |
| sparse-cell fallback | 104 | **+0.474709** | [+0.39126, +0.55197] | 0.000 |

**The cell conditioning earns its keep exactly where it is used; the declared
fallback destroys the gain several times over.** 104 rows — 3.2% of the sample —
carry a Brier of 0.5309 against the constant's 0.0562. Equal AUC (0.6223 vs
0.6210) shows the baseline's failure is **pure calibration**, not
discrimination.

**The fallback to `p_reliever_by_rank` was pre-registered and it is wrong.** It
is not changed here — a pre-registration is not amended after seeing a result.
The successor should fall back to the pooled `P(relieves | not starter)`, and
that is a new candidate identity, never an edit to QBSEM.

---

## The ten acceptance items

| # | item | state |
|---|---|---|
| 1 | fixed-cohort baseline vs QBSEM | **PASS** — 29 players, identical cohort, none added or dropped; effect confined to the QB room, every non-QB row under 0.11 DK |
| 2 | cell-wise `P(relieves \| not starter)` calibration | **PASS (reported)** — forward-chained, clustered |
| 3 | simulated vs historical `P(db=0)` by cell | **PASS** — 544 team-games replayed out of sample; row-weighted MAE 0.052251 → 0.046544 |
| 4 | **Allen-cell target ≈ 0.0694** | **FAIL** — he is not in that cell on this board |
| 5 | Brier and log loss | **PASS (reported)** — beats the baseline decisively, loses to a constant overall |
| 6 | zero leakage | **PASS** — 23 mechanical checks |
| 7 | explicit fallback counts | **PASS** — **2 of 4 QBs fell back, both starters**, counted per player on the artifact |
| 8 | semantic parity QB/RB/WR/TE/K | **PASS** — 112 boards, 14,770 metrics, 13,027 discriminating, 0 violations; K now checked |
| 9 | exact QB team-volume conservation | **PASS** — 8,000/8,000 both clubs, worst integer deviation **0** |
| 10 | Contract 3, unchanged grid | **FAIL** — `chosen: null` |

### The pre-registration's own seven gates

2, 3, 4 and 7 **PASS**; 6 passes on QB/RB/WR/TE; 5 is not exercised (the board
emits no conditional diagnostic and the gate says "may"); **1 FAILS**.

---

## Contract 3

| draws | GSVU fail/checked | QBSEM fail/checked | QBSEM binding (boot sd vs threshold) |
|---|---|---|---|
| 1,000 | 553 / 1,649 | 538 / 1,662 | `qb/pyds` p90 Allen — 6.3147 vs 1.0 |
| 2,000 | 356 / 1,664 | 328 / 1,677 | `qb/pyds` p90 Goff — 3.5004 vs 1.0 |
| 4,000 | 194 / 1,686 | 180 / 1,689 | `qb/pyds` p90 Goff — 2.9262 vs 1.0 |
| **8,000** | **108** / 1,691 | **117** / 1,700 | `qb/cmp` p10 Goff — 0.4997 vs 0.25 |
| 16,000 | 72 / 1,697 | **67** / 1,705 | `qb/cmp` p10 Goff — 0.4999 vs 0.25 |

`n_checked` differs between the arms, so the failing counts are not a
like-for-like ratio.

**The §5 hypothesis is directionally confirmed and practically irrelevant.**
`qb/pyds` p90 stopped being the binding quantity at 8,000 and 16,000 — GSVU
bound there at 2.4011 yards against a 1.0-yard threshold; QBSEM binds on
`qb/cmp` p10 at 0.4997 against 0.25, a discrete count quantile on a half-integer
boundary. The tail settled enough to stop binding and the contract still fails.

**I predicted the p90 bootstrap sd would not fall materially. It fell for all
four QBs and I was wrong about the direction.** But the two large falls are
**degeneracy, not stability**: the backups' `P(pyds=0)` is 0.9086 and 0.9116,
both above 0.90, so the p90 lands inside a point mass at zero and its sd is
0.0000 because the statistic is constant. The honest figures are the starters':
Goff −29%, Josh Allen −9% (2.2403 → 2.0320).

---

## Three accounting errors of mine, each caught and each corrected

These are the same mistake in three shapes: **a column I did not read.**

1. **Gadget rushing.** I defined participation as dropbacks + targets + carries
   and reported that receivers score DK points with none of those — Greg Dortch
   6.1 at the maximum over 266 draws. A receiver can take a gadget carry, whose
   yards reach him through `rushing_total` and whose carry count is stored
   nowhere per player. Adding the column accounts for 19/19, 266/266, 53/53 and
   20/20 exactly and the maximum falls to 0.00.
2. **Kicking.** I told you kicking was ABSENT and no kicker was in the room.
   **Wrong.** The kicking layer carries two rows with full distributions. The
   true statement is narrower and is a real defect: **every board computes a
   kicking layer and no board publishes a kicker among its players** — 112
   boards, 6 kicking rows, **0 published**. My tripwire's "K NOT_EXECUTED" was a
   gap in the test, not in the corpus.
3. **`kicking/offensive_td`.** Fixing (2) made check C fire on it across four
   boards. Not a defect either: it is the **team's** offensive touchdowns
   recorded on the kicker's row as the model's **input**. `xpa` tracks it at
   ~0.86 attempts per TD (0.856 / 1.768 / 2.677 / 3.623 at td = 1..4), the rest
   two-point tries, and P(xpa=0 | td=4) = 0.0025 — a rare world, not an
   impossible one.

Also withdrawn: a caveat I wrote into the cell-replay artifact claiming the
realised and fitted rates came from the same rows. That holds only when the fit
includes the evaluation season; this one cuts before it, so the comparison is
out of sample.

---

## The board

**Nothing is sealed.** The surviving clean candidate is GSVU, which itself fails
Contract 3. Its full stat board — passing attempts / completions / yards / TD /
INT, carries, targets / receptions / receiving yards / receiving TD, QB rushing,
touchdown and threshold probabilities, quantiles and confidence — is the
engine's own `BOARD.md` for run `dfb5f5fb8c99e58f`.

Delivered separately because `BOARD.md` does not render them:

- **DraftKings points** with P(0 points) per player — `DK_AND_ABSENCES.md`
- **Kicking** — `KICKING_CORRECTION.md`, with the correction above

**Named rather than estimated:**

| quantity | state |
|---|---|
| **Rushing yards, RB / WR / TE** | **UNAVAILABLE** — `RUSHING_CONVERSION_CONTROL_UNDEFINED`. No governed carry → yards control exists; three owner decisions are open. `carries × YPC` is named in `layers.py` as the prohibited implementation. |
| **Passer rating** | **UNAVAILABLE** — `NO_RATE_COMPOSITE_LAYER` |
| **Air yards / aDOT** | **UNAVAILABLE** — `NO_AIR_YARDS_LAYER` |
| **Kicking on the published board** | **MODELLED, NOT PUBLISHED** — see above |

QB rushing yards **are** produced and are flagged provisional.

---

## Limitations carried forward

- **Rest-state / season boundary — unresolved and accepted.** Differential
  −0.0715. It now demonstrably drives the QB cell assignment as well as R8's
  recency state. **Josh Allen and James Cook carry the caveat.**
- **Eligibility-gate double-count** — declared; nil exposure here, since no 2026
  week-2 official report exists and the gate removed no quarterback.
- **EXPLORATORY** — the cells were chosen on the frame every earlier QB repair
  was selected on. The forward chain controls parameter leakage only.
- **Kicker publication gap** — modelled on every board, published on none.
- Postseason excluded from the appearance panel; **GSP/GSVP permanently
  disqualified** (survivorship-filtered panel).

## Recorded for later, not part of this gate

QB participation should eventually be a **joint hierarchical multinomial /
competing-risk** system over starter / reliever / full absence / emergency-only.
Two findings here bear on it: the states are not separable from pregame
information as the frame stands, and the fallback failure is exactly the
argument for hierarchical shrinkage toward a parent rather than a hard switch.

---

## The confirming full suite

Measured at the final HEAD, not one commit behind it.

| | pre-QBSEM baseline | QBSEM HEAD |
|---|---|---|
| modules | 146 | **148** |
| test functions | 1,657 | **1,668** |
| checks | 9,051 | **9,100** |
| **FAILING CHECKS** | **53** | **53** |
| RAISED | 15 | 15 |
| ZERO-CHECK FUNCTIONS | 0 | **0** |
| BLOCKED FUNCTIONS | 22 | 22 |

**The failing-module set and every per-module count are identical before and
after.** Two new modules, 49 new checks, **zero new failures and no
regression.** `SUITE_AT_QBSEM_HEAD.log`.

`SUITE FAIL` is the standing state of this repository — the 53 failures are
pre-existing and each is a known open defect, among them the 54.89% non-integer
carry cells, the W1 panel survivorship gap, and `REPLAY_RE_SELECTS`. None of
them is new and none is QBSEM's.

**BLOCKED is not a pass and NOT_EXECUTED has not disappeared.** 22 functions
are BLOCKED, and this work adds one NOT_EXECUTED of its own: the kicker
publication gap, stated in `test_publication_semantics.py` rather than worked
around.

---

**V2 NOT YET EARNED**
