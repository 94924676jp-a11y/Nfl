# REST pre-registration — the last regular week in the recency state

**Written after §1's measurement and before any fix is built or scored.** §1 is
measurement of an already-frozen mechanism against already-realised outcomes;
it fits nothing.

---

## 1. What is actually wrong, measured

### Two claims of mine are withdrawn first

- **"2025 week 18 was a league-wide rest week."** FALSE. At team level the last
  regular week is not anomalous at all. Mean team appearance rate, typical week
  against last week: 2020 0.6899/0.6919, 2021 0.6438/0.6627, 2022 0.6483/0.7157,
  2023 0.6769/0.7167, 2024 0.6655/0.7190, 2025 0.5791/0.5822. **Zero** of 192
  team-seasons fall below 60% of their own typical rate. The last week is if
  anything a HIGHER-participation week, because rosters expand.
- **"James Cook's `app_ewma` is dragged down by a week-18 rest game."** FALSE.
  Cook's 2025 week 18 reads `appeared = 1` and his `app_ewma` is **0.9997**.
  What is low for Cook is his SNAP share in that game — 0.03 — which reaches a
  different feature. Josh Allen is the one whose appearance state is hit:
  `appeared = 0`, `snap = 0.00`, listed **rank 1**, after seven straight weeks
  at snap 1.00.

So this is not a calendar effect and not a team effect. It is an **individual
sit by an established starter**, and it is common enough to matter.

### Frequency

Signature, defined only from evidence available at the time: listed rank 1–3 in
the last regular week, appeared with snap ≥ 0.50 in each of the three prior
weeks, and then in the last week either did not appear or took ≤ 10% of snaps.

| season | played | **SAT** | rate |
|---|---|---|---|
| 2020 | 109 | 17 | 0.1349 |
| 2021 | 102 | 10 | 0.0893 |
| 2022 | 106 | 13 | 0.1092 |
| 2023 | 104 | 19 | 0.1545 |
| 2024 | 106 | **25** | 0.1908 |
| 2025 | 47 | 10 | 0.1754 |

**94 established starters across six seasons, 8.9%–19.1% per season.**

### The cost, and it is a DIFFERENTIAL mis-calibration

Weeks 1–4 of the following season, five transitions, R8 scored against what
happened:

| | n | predicted | realised | gap |
|---|---|---|---|---|
| **SAT** | 368 | 0.7141 | 0.7473 | **−0.0332** |
| PLAYED (control) | 2,509 | 0.7430 | 0.7075 | **+0.0355** |

**Differential −0.0688, team-blocked 95% CI [−0.1133, −0.0256]**, 4,000
resamples. The interval excludes zero.

Read it as the differential, not as either half: R8 slightly over-predicts
established starters generally and under-predicts the ones who sat, and the gap
between the two is about **7 percentage points**.

### Who it hits on DET-BUF

| player | 2025 signature |
|---|---|
| **Josh Allen** | **SAT** |
| **James Cook** | **SAT** |
| Amon-Ra St. Brown | PLAYED |
| Jared Goff | PLAYED |
| Ray Davis, Jahmyr Gibbs, Sam LaPorta, Greg Dortch | not established starters by the precondition |

Cook qualifies on the snap limb (0.03), not the appearance limb.

---

## 2. Candidate fixes, none selected here

### A — drop the last-regular-week row from the recency walk for signature players

Preserves R8's coefficients exactly. **Rejected as the primary, and the reason
is a rule this project already has:** the signature carries three thresholds —
rank ≤ 3, snap ≥ 0.50 in the prior three, snap ≤ 0.10 in the last — and I chose
all three **while looking at Josh Allen and James Cook**. They are fitted
constants with no derivation, which is exactly what `board_config` logs as a
bug. It also destroys real evidence: a sit is informative about something, and
deleting it asserts it is informative about nothing.

Retained only as a **sensitivity arm**, to show what the ceiling of any
correction looks like.

### B — one binary feature, no thresholds, and the model estimates it

Add **`prev_was_last_regular_week`** to the R8 design: 1 when the player's
immediately preceding frame row is the final regular-season week of its season,
0 otherwise. Refit on the same forward-chained frame.

- **No thresholds.** No rank cut, no snap cut, no player list. The feature is a
  fact about the calendar position of a row, computable for every row in the
  frame, and the coefficient is estimated from six seasons.
- **It is an explicit mechanism change**, so it takes its own candidate
  identity and refits. R8's coefficients are preserved under R8; this is a
  successor lineage, not an edit.
- It can come back with a coefficient near zero, and that is a legitimate
  result which would say the §1 differential is carried by something else.

### C — down-weight the last regular week in the EWMA

**Rejected.** The weight is a constant nobody can derive, and choosing it to
close a 0.0688 gap is fitting to the number this file exists to measure.

### D — a post-hoc calibration offset on flagged players

**Rejected** under "prefer a structural fix over player-specific exceptions".

---

## 3. What decides it, fixed now

Forward-chained exactly as R8's own evidence was: trained on seasons strictly
earlier than the evaluation season, scored on that season, 2022–2025, identical
rows, identical `is_unsupported` exclusion, identical l2, same reliability `k`
handed to both arms.

**Primary estimand, and it is the differential, not the level:**

> (SAT gap − PLAYED gap) in weeks 1–4, R8 against candidate B.

**B is selected only if ALL of:**

1. The differential moves toward zero, with a team-blocked 95% interval on the
   CHANGE that excludes zero.
2. **Overall weeks 1–4 Brier does not get worse** — the interval on
   ΔBrier(B − R8) must not sit entirely above zero. A fix that closes one gap
   by spending accuracy elsewhere is not a fix.
3. **Weeks 5–18 Brier does not get worse** on the same test. The feature must
   not buy early-season calibration with late-season damage.
4. The estimated coefficient is reported with its standard error **whatever its
   sign**, including if it is indistinguishable from zero.

**If B fails any of these, B is withdrawn and R8 stands unchanged**, with the
§1 differential recorded as a known, quantified, unrepaired limitation of the
board. That is an acceptable outcome and it is written here so it cannot be
argued away later.

## 4. What would make this pre-registration wrong

- **The signature in §1 is mine, and it is post-hoc.** It was built after
  looking at two players. It is used ONLY to measure and report the defect and
  to define the evaluation subgroup; it is deliberately **not** used by fix B,
  which is why B is the primary.
- **n is small.** 368 SAT rows over five transitions, 10–25 players a season.
  The interval reflects that and the point estimate should not be quoted
  without it.
- **"SAT" conflates causes.** A healthy rest, a minor injury nobody reported,
  and a benching are one row here. Nothing available pregame separates them,
  and inventing a separation would be the fabrication this project forbids.
- The evaluation frame is the same one every earlier repair was selected on, so
  this is **EXPLORATORY**. Forward chaining controls parameter leakage and says
  nothing about specification leakage.

## 5. Order of operations, stated so it is not reordered later

1. Build B, refit, forward-chain 2022–2025. *(not started)*
2. Apply §3. Select or withdraw.
3. **Only then** rerun the corrected week-1 challenger.
4. Then Contract 3 on the survivor, then the confirming suite.
5. Seal the Thursday board only if those gates pass.

**No Allen or Cook projection is to be interpreted before step 2 closes.**

V2 NOT YET EARNED.
