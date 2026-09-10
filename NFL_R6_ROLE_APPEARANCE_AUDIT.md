# R6 — role and appearance refinement

**Evidence first.** V1 remains the immutable control, R5 the pool repair, R6
adds one thing. Team totals and the QB path are untouched and proven so. No
sportsbook line was used as a label or a fit target.

---

## 1. Root cause of the appearance inversion

The frozen P3 logistic reads absence history, and **absence history carries
across the offseason boundary.** Feature values from the sealed run:

| player | `f_consec_missed` | `f_prev_appeared` | `f_n_prior` | P(appear) |
|---|--:|--:|--:|--:|
| Davante Adams | **3** | 0 | 110 | **0.532** |
| Ricky Pearsall | **1** | 0 | 26 | **0.384** |
| Puka Nacua | 0 | 1 | 50 | 0.947 |
| Brennan Presley | **0** | **None** | **0** | **0.998** |
| Tru Edwards | **0** | **None** | **0** | **0.998** |

Adams missed the last three games **of 2025**. Eight months and a training camp
later, with no entry on any injury report, he is still carried as a three-game
absentee into week 1.

Two sub-defects, and they compound:

**(a) Cross-season carry-over.** `f_consec_missed` and `f_prev_appeared` are
computed from the player's last observed game with no season reset. A player
who ended a season on injured reserve, or was rested in week 18, begins the
next season penalised for it.

**(b) Cold start is scored as a clean record.** A player with `f_n_prior = 0`
has no absences, so he presents identically to a man with perfect attendance.
**Absence of evidence is read as evidence of availability** — this project's
signature defect, here in the appearance layer.

**(c) A third finding, unlooked for: `A.depth()` returns an empty dict.**
`f_depth` is `None` on every row, historical and prospective. The appearance
model carries a depth feature it has never once received, so it is role-blind
by construction and absence history is the only role-adjacent signal it has.

**The training data is survivorship-filtered for cold starts.** The historical
"no prior information" bucket appears at 94.8–98.0%, because a player with no
history enters the panel when he first plays. A camp receiver who never dresses
is invisible to it. The model is not wrong about the data it saw; the data is
missing the players it most needs.

---

## 2. Root cause of the flat participation prior

`participation_prior.share_prior` is a **pass-snap participation rate** — the
probability of being on the field — used to weight **target allocation**.

| | model | historical realised |
|---|--:|--:|
| top-to-fringe ratio | **1.39 : 1** | **2.5 : 1** in snaps |
| | | **3.7 : 1** in targets |

So it is too flat *even as a snap quantity*, and it is then applied to a
quantity whose true spread is nearly three times wider. The layer's own warning
already says pass-snap participation is *"an upper bound on routes run"*; this
is the size of it.

Compounding: `class_point_forecast` falls back to the **positional mean** for a
player with no history — 0.1253 for every WR, whether he is a team's second
option or its ninth. A 3.7 : 1 spread collapsed to 1 : 1.

---

## 3. Historical calibration evidence

Point-in-time depth tier: the rank of a player's trailing mean snap share
within his team and position, from strictly earlier weeks. No row sees its own
game. 2020–2025, 83,144 player-weeks.

### Appearance by tier

| tier | realised appearance | tier | realised appearance |
|---|--:|---|--:|
| WR1 | **88.6%** | RB1 | **84.6%** |
| WR2 | 81.9% | RB2 | 81.7% |
| WR3 | 80.1% | RB3 | 65.5% |
| WR4+ | 61.1% | RB4+ | 50.5% |
| TE1 | 87.3% | TE3 | 74.7% |
| TE2 | 83.2% | TE4+ | 49.2% |
| *no prior information* | **94.8–98.0%** | | |

Realised appearance falls monotonically with depth. **The model runs the other
way**: established WR2 Adams at 0.532 against a tier rate of 81.9%; cold-start
players at 0.998 against a bucket whose 95–98% is a selection artifact.

### Participation and usage by tier (appeared rows only)

| tier | snap share | target share | carry share |
|---|--:|--:|--:|
| WR1 | 81.5% | **22.7%** | 0.6% |
| WR2 | 74.1% | 18.3% | 0.8% |
| WR3 | 59.7% | 13.3% | 0.7% |
| WR4+ | 32.7% | **6.1%** | 0.6% |
| TE1 | 71.1% | 14.9% | — |
| TE2 | 45.1% | 6.2% | — |
| RB1 | 59.8% | 10.6% | **50.5%** |
| RB2 | 37.7% | 6.6% | 26.4% |
| RB3 | 23.8% | 3.6% | 14.0% |
| RB4+ | 19.6% | 2.9% | 11.1% |

---

## 4. The R6 repair

**`V1_CANDIDATE_R6` = R5 + one flag.** The P4C class weight becomes a player's
own history **shrunk toward his point-in-time depth tier**, replacing the
role-blind positional-mean fallback.

- **Tier is point-in-time.** Trailing snap-share rank from strictly earlier
  weeks; the captured depth chart where a player has no trailing history; the
  lowest tier where neither exists, and it is *recorded* as such rather than
  assumed away.
- **The shrinkage weight is `n / (n + k)` with `k` estimated, never chosen** —
  within-player over between-player variance of the class share. Measured:
  WR 0.87, TE 0.78, RB-targets 1.54, RB-carries 0.74.
- **A long history is never overwritten.** At 100 prior games the weight goes
  to one and the player's own value is returned unchanged; a test asserts it.
- **No player or team is named.** A test greps for it.

What R6 does **not** do: it does not repair the appearance inversion. It
reduces the *damage* — a cold-start player at tier 6 now prices at the WR4+
tier mean rather than the positional mean, halving his weight even while his
P(appear) is still wrongly 1.00 — but the cause is untouched, and I would
rather say so than let a side effect be mistaken for a fix.

---

## 5. V1 vs R5 vs R6 against realised history

| quantity | V1 | R5 | **R6** | historical |
|---|--:|--:|--:|--:|
| SF targets top-1 | 11.8% | 17.0% | **18.1%** | 29.3% |
| LA targets top-1 | 15.9% | 22.4% | **24.3%** | 29.3% |
| SF targets top-3 | 34.0% | 49.0% | **52.5%** | 65.5% |
| LA targets top-3 | 30.8% | 44.4% | **46.9%** | 65.5% |
| SF players targeted | 11.0 | 7.9 | **7.4** | 8.0 |
| LA players targeted | 11.9 | 8.4 | **8.1** | 8.0 |
| SF carries top-1 | 39.8% | 52.6% | **67.6%** | 70.3% |
| LA carries top-1 | 36.4% | 60.1% | **60.2%** | 70.3% |
| SF RBs with a carry | 4.0 | 3.0 | **2.6** | 2.4 |
| LA RBs with a carry | 3.8 | 2.0 | **2.0** | 2.4 |

**R6 improves R5, it does not merely move it.** The largest single gain is San
Francisco's lead-back carry share, 52.6% → 67.6% against a realised 70.3%.

**Two places R6 is not better, reported because they are true:** San
Francisco's players-targeted goes 7.9 → 7.4 and slightly *overshoots* the
historical 8.0, and its carries top-3 goes 95.9% → 94.7% against 99.8%. Both
are small; neither is in the direction the repair was aimed.

**CRPS / PIT / coverage are not reconstructable here** for the same reason as
R5: the historical corpus contains only players who appeared, so neither
candidate's counterfactual exists in it. That needs historical roster vintages
carrying `status` — outbox OUT-002 — and I will not substitute a distributional
comparison for a per-game score and call it one.

---

## 6. SF@LA, V1 → R5 → R6 → market

Market is comparator only. Nothing here was fitted to it.

| player | market | line | V1 | R5 | **R6** |
|---|---|--:|--:|--:|--:|
| McCaffrey | Carries | 15.5 | 7.29 | 9.52 | **12.23** |
| K. Williams | Carries | 13.5 | 6.68 | 11.02 | **11.04** |
| Nacua | Receptions | 7.5 | 3.56 | 5.03 | **5.44** |
| Nacua | Receiving yds | 90.5 | 46.95 | 66.31 | **71.22** |
| Kittle | Receptions | 3.5 | 2.44 | 3.67 | **3.92** |
| Kittle | Receiving yds | 33.5 | 31.93 | 47.82 | **51.26** |
| McCaffrey | Receptions | 4.5 | 2.56 | 3.58 | **3.80** |
| Stafford | Pass attempts | 34.5 | 30.27 | 30.27 | **30.27** |
| Purdy | Pass attempts | 33.5 | 26.71 | 26.71 | **26.71** |

Median absolute disagreement with the market: **25.3 → 18.7 → 17.4 pp**.

Kittle now prices *above* the market on both his markets. R6 is not sliding
toward Vegas; it is moving toward the historical distribution and sometimes
past the price.

---

## 7–8. Team totals and QB path, unchanged

Every delta is exactly zero, at 1,000 draws:

| | V1 | R5 | R6 | max delta |
|---|--:|--:|--:|--:|
| SF dropbacks / targets / carries | 36.01 / 36.19 / 26.59 | same | same | **0.0000** |
| LA dropbacks / targets / carries | 33.89 / 29.78 / 28.35 | same | same | **0.0000** |
| SF qb att / db | 30.35 / 33.94 | same | same | **0.0000** |
| LA qb att / db | 33.20 / 35.91 | same | same | **0.0000** |

---

## 10. Does R6 deserve prospective evaluation?

**Yes, as a shadow candidate alongside R5 — and not promotion.**

For: it repairs a defect diagnosed independently of any market, it moves ten of
twelve concentration metrics toward realised history, it introduces no chosen
constant, it leaves team volume and the QB path bit-identical, and it cannot
overwrite an established player's own history.

Against, and this is the honest half: the validation is **distributional, not
per-game**. Nothing here shows R6 scores better on a held-out game, because
that comparison is not constructible without OUT-002. Two metrics moved the
wrong way. And the appearance inversion — the larger of the two defects the
mission named — is diagnosed but **unrepaired**, so R6 addresses one and a half
of the two.

**Recommended:** run R5 and R6 as shadow boards beside V1, score all three
through the permanent evaluator as games land, and let the four-game
refinement bar decide. Promotion should wait on per-game evidence, which means
it waits on OUT-002.

**Stopping after evidence, as instructed. Nothing is promoted.**
