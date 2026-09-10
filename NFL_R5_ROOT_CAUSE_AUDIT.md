# V1 calibration root-cause audit — SF @ LA

**Diagnosis first, then one repair, validated against actual historical
outcomes and never against a price.** No sportsbook line was used as a label,
a target or a fit input anywhere in this work.

---

## 1. Root causes, ranked by contribution

### #1 — The allocation pool is contaminated (dominant)

`p4c_params.class_point_forecast` returns `C`, an EWMA of a player's prior
**appeared** class shares — a share *conditional on him playing*. The P4C
simplex consumes it as an *unconditional weight over whatever roster it is
handed*, then normalises by the sum.

Those two agree historically and disagree prospectively:

| | pool size | sum(C) |
|---|--:|--:|
| historical fitting panel (per team-game) | **14.6** | **1.24** |
| prospective SF@LA, unfiltered roster | **22.5** | **2.14** |

Normalising by 2.14 instead of 1.24 **halves every genuine starter share**.

The surplus is not "backups". Of the 45 SF/LA WR/TE/RB roster rows: **29 ACT,
10 DEV (practice squad), 3 RES (reserve/injured), 3 CUT.** Players who had
been released were competing for Puka Nacua's targets.

The enabling defect is data plumbing: the raw nflverse roster carries `status`
and `depth_chart_position`, and **the vintage reduction keeps only
season/week/team/gsis_id/position.** The field the model needed was captured
and then discarded.

### #2 — Appearance probability is anti-correlated with role

Measured on the sealed run:

| player | role | P(appear) |
|---|---|--:|
| Davante Adams | LA WR2, no injury designation | **0.538** |
| Ricky Pearsall | SF WR | **0.395** |
| Brennan Presley, Tru Edwards, CJ Daniels | unlisted | **0.998–0.999** |

A camp body is treated as near-certain to play; the WR2 as a coin flip. Because
the weight is `appearance × share_prior`, Adams ends on 0.538 × 0.736 = 0.396
while Presley ends on 0.999 × 0.568 = 0.567 — **the camp body outranks the
WR2.** Unrepaired; see §6.

### #3 — The participation prior is too flat

`share_prior` gives LA's top four 0.787 / 0.740 / 0.736 / 0.725, and a shared
fallback of 0.568 to many others. A top-to-fringe ratio of 1.4 : 1 where real
target concentration is nearer 15 : 1. The layer's own declared warning says
it: pass-snap participation is *"an upper bound on routes run"*. **The model
allocates targets in proportion to being on the field.** Unrepaired.

### #4 — QB dropback ownership does not close per team

QB pool ÷ team dropbacks: **SF 0.942, LA 1.060** — and 0.999 across the game.
Every dropback has a quarterback, so both should be ~1.0. The apportionment
closes at game level while mis-splitting between the two teams. Unrepaired,
and it is part of why Purdy's attempts sit low. Small next to #1.

### #5 — Team volume: **not** a material cause

Backtested against 3,230 historical team-games, the team-volume baseline is
unbiased to within 1–2%:

| metric | overall bias | week-1 bias |
|---|--:|--:|
| team_off_snaps | −0.0% | +0.9% |
| team_dropbacks_part | −0.8% | +1.6% |
| team_targets | −0.6% | +2.0% |
| team_carries | −0.7% | −1.4% |

**The model is not forecasting a small game. It is forecasting an ordinary game
and dividing it among too many people.**

---

## 2. Waterfall — where the discrepancy is created

Using McCaffrey carries (market line 15.5, V1 mean 7.29):

| layer | model | historical / market reference | contribution to the gap |
|---|--:|---|--:|
| team volume (SF carries) | 26.59 | historical wk-1 mean 26.81 | **~0** |
| pool construction | 6 RBs | historical 2.4 with a carry | **large** |
| share allocation (RB1) | 39.8% | historical rank-1 **70.3%** | **dominant** |
| conversion (carries→yards) | n/a | `RUSHING_CONVERSION_CONTROL_UNDEFINED` | not modelled |
| **final** | **7.29** | 26.59 × 0.703 = **18.7** | |

Same shape for targets: team volume right, rank-1 share 15.9% against a
historical **29.3%**, top-3 31–34% against **65.5%**, distinct players targeted
11–12 against **8.0**.

Passing yards and TD gaps are **inherited**, not separately created —
conversion is applied to a suppressed opportunity. Interceptions, the metric
with least dependence on how opportunity splits among teammates, is the one
metric where model and market agree (−1.9 pp, split 1/1).

---

## 3. Is starter opportunity demonstrably too diffuse? **Yes** — against outcomes

Realised, 2020–2025, 3,230 team-games:

| | historical realised | V1 |
|---|--:|--:|
| targets, rank 1 | **29.3%** | 15.9% |
| targets, top 3 | **65.5%** | 30.8% |
| distinct players targeted | **8.0** | 11.9 |
| carries, rank 1 | **70.3%** | 36.4% |
| distinct RBs with a carry | **2.4** | 3.8 |

This is measured against football, not against Vegas. The market pointed at it;
the panel proved it.

---

## 4. Is team/QB volume independently biased low? **Essentially no**

Per §1 #5, under 2% in week 1 and in both directions. The residual QB attempt
gap is #4 (per-team dropback ownership), not a low team-volume forecast.

---

## 5–7. The repair, and candidate versus V1 on actual outcomes

**`V1_CANDIDATE_R5`** — a new, separate configuration identity. `V1_CANDIDATE`
is untouched, flag for flag, and a test asserts R5 differs from it by exactly
one flag.

The repair: **restrict the non-QB allocation pool to players whose roster
status is `ACT`.** No constant is introduced; a test asserts the module holds
no numeric threshold. An unknown status is **kept**, not dropped — removing a
player the roster does not describe would be the forcing-concentration move
this repair exists to avoid. Missing status **refuses by name**
(`ROSTER_STATUS_UNAVAILABLE`); it never runs unfiltered under an R5 label.

The QB pool is deliberately untouched: QB allocation does not run through the
P4C simplex and its shares are already right.

### Candidate vs V1 vs historical truth

| quantity | V1 | **R5** | historical |
|---|--:|--:|--:|
| SF targets top-1 | 11.8% | **17.0%** | 29.3% |
| LA targets top-1 | 15.9% | **22.4%** | 29.3% |
| SF targets top-3 | 34.0% | **49.0%** | 65.5% |
| LA targets top-3 | 30.8% | **44.4%** | 65.5% |
| SF players targeted | 11.0 | **7.9** | **8.0** |
| LA players targeted | 11.9 | **8.4** | **8.0** |
| SF pool size | 22 | **14** | **14.6** |
| LA pool size | 23 | **15** | **14.6** |
| SF carries top-1 | 39.8% | **52.6%** | 70.3% |
| LA carries top-1 | 36.4% | **60.1%** | 70.3% |
| SF RBs with a carry | 4.0 | **3.0** | **2.4** |
| LA RBs with a carry | 3.8 | **2.0** | **2.4** |

**Every metric moves toward the realised historical distribution.** Pool size
and players-targeted land essentially on it.

### Team totals are preserved exactly

| team | metric | V1 | R5 | delta |
|---|---|--:|--:|--:|
| SF | dropbacks / targets / carries | 36.01 / 36.19 / 26.59 | 36.01 / 36.19 / 26.59 | **0.000** |
| LA | dropbacks / targets / carries | 33.89 / 29.78 / 28.35 | 33.89 / 29.78 / 28.35 | **0.000** |

The repair changes the split, not the pie — which is what repairing at the
causal layer rather than compensating downstream means.

### What is NOT claimed

A per-game held-out CRPS/PIT comparison of R5 against V1 **is not runnable
here**, and I will not pretend otherwise. The historical corpus contains only
players who appeared, so the contamination R5 removes never existed in it;
constructing the counterfactual needs historical roster vintages carrying
`status`, which this repository does not hold. That is an **AGENT_OUTBOX**
item, not a result. The evidence above is distributional — predicted
concentration against realised concentration on 3,230 team-games — which is
outcome-anchored and weaker than a per-game score.

**R5 closes roughly half the gap.** Root causes #2, #3 and #4 remain and are
not bundled in; each needs its own diagnosis and its own validation.

---

## 8–9. SF@LA candidate projection, and the three-way comparison

Generated at `written_at 2026-09-10T17:10:46Z`, run `5ebc0508ed86c8ca`, from
stored pre-kickoff vintages only. **No market line entered it.**

| player | market | line | V1 mean | **R5 mean** | P(V1) | **P(R5)** | P(market) |
|---|---|--:|--:|--:|--:|--:|--:|
| McCaffrey | Carries | 15.5 | 7.29 | **9.52** | 0.033 | **0.101** | 0.506 |
| K. Williams | Carries | 13.5 | 6.68 | **11.02** | 0.033 | **0.282** | 0.458 |
| Nacua | Receptions | 7.5 | 3.56 | **5.03** | 0.053 | **0.206** | 0.441 |
| Nacua | Receiving yds | 90.5 | 46.95 | **66.31** | 0.124 | **0.268** | 0.500 |
| Kittle | Receptions | 3.5 | 2.44 | **3.67** | 0.253 | **0.501** | 0.454 |
| Kittle | Receiving yds | 33.5 | 31.93 | **47.82** | 0.397 | **0.612** | 0.500 |
| McCaffrey | Receptions | 4.5 | 2.56 | **3.58** | 0.133 | **0.301** | 0.525 |
| Stafford | Pass attempts | 34.5 | 30.27 | 30.27 | 0.316 | 0.316 | 0.505 |
| Purdy | Pass attempts | 33.5 | 26.71 | 26.71 | 0.264 | 0.264 | 0.517 |

Median absolute disagreement with the market: **25.3 pp → 18.7 pp**.

Two things worth noting. **QB attempts do not move at all** — R5 does not touch
the QB pool, so that gap is a separate unrepaired defect (#4), and its
persistence is evidence the repair is doing what it claims and nothing else.
And on Kittle, R5 lands *above* the market on both markets — it is not sliding
toward Vegas, it is moving toward the historical distribution and sometimes
overshooting the price.

---

## 10. SF@LA outcome was not used for fitting

The game has not been played. Kickoff is 2026-09-11T00:35:00Z; this work was
done on 2026-09-10 and the candidate is sealed with `written_at` before it.
No outcome file for this game exists anywhere in the repository. R5 was
specified from the historical panel and from roster status, and validated
against 2020–2025 realised shares.

---

## 11–12. Suite, commit, integration

See the return message.

---

## Open decision, returned rather than implemented

`RUSHING_CONVERSION_CONTROL_UNDEFINED` remains open. Nothing here computes
carries × yards-per-carry, and RB/WR/TE rushing yards stay `UNAVAILABLE`. R5
raises the stakes on that decision — it materially raises RB carry projections,
which is exactly the input a rushing-yards control would consume — and a
research design for it is owed separately.

**Two capture-layer requests, for the outbox, not worked around here:**

1. Retain `status` and `depth_chart_position` in the reduced weekly-roster
   vintage. Both exist in the raw download and are dropped. Without `status`,
   R5 can only run against a capture whose raw blob happens to be retained.
2. Historical weekly-roster vintages carrying `status`, so the R5
   counterfactual can be scored per game against held-out outcomes.
