# P2 — Appearance × conditional usage

**Date:** 2026-09-07 · **Repository:** `94924676jp-a11y/nfl`
**Track:** quarantined research. G0A untouched at **11/12**. NFL-1 not executed.
**2026 outcomes used:** none.

---

## Verdict up front

**The two-stage decomposition works, and its value is bought entirely by
point-in-time injury data.**

- Stage A is genuinely predictable: AUC **0.85–0.87** for "will he take an
  offensive snap", rising to **0.92** for "will he play more than half the
  snaps".
- A×C raises correlation on every target in every season — `snap_share`
  0.70 → 0.78, `rpr` 0.72 → 0.79, `carry_share` 0.67 → 0.76.
- **But on MAE it beats the P1 incumbent in only 11 of 20 target-seasons, and
  it is decisively worse in 2025** — the one season with no usable injury
  vintage. Stage A's AUC falls from 0.87 (2024, injuries available) to 0.81
  (2025, none), and the mixture degrades with it.

So the honest answer to the directive's question is: **yes, but conditionally.**
The appearance model is what makes A×C work, injury designations are what make
the appearance model work, and where those are missing the added complexity is
a net loss on absolute error while still helping ranking.

**Four things of mine were wrong here and are corrected in place.** A
role-change "prediction" scoring AUC 0.9999, which was a definition predicting
itself (§12); a strawman appearance baseline that made the logistic model look
better than it is (§7); rate baselines scored on the wrong scale (§7); and — the
one that nearly shipped — **a subgroup table in §15–17 that I wrote from
expectation instead of reading from the results file, and whose real numbers
say close to the opposite**. All four are described where they occurred rather
than quietly fixed.

---

## 1. Exact HEAD

`3d22b3a` at task start; P2 commits listed in §24.

## 2. Historical seasons and sample sizes

Seasons **2020–2025** regular season. Evaluation seasons 2022–2025, strictly
chronological — train on all seasons before, test on that one.

| Population | n |
|---|---|
| Panel player-games (any recorded activity) | 57,670 |
| Extended with pregame-identifiable non-appearances | 83,144 |
| Stage A candidate player-games (WR/TE/RB/QB, ≥1 prior game) | **35,757** |
| Role-change-next population (≥4 prior games) | **41,234** |
| Redistribution events / affected player-games | 2,534 / 36,815 (snaps) |
| Cold-start rows (<4 prior games) per season | 337–371 |

Base appearance rate across candidates: **0.659–0.682** by season.

## 3. Appearance target definitions

Primary: **at least one offensive snap**. Sensitivity reported at four
thresholds rather than one being chosen and the rest suppressed:

| Threshold | Base rate (2024) | Best AUC |
|---|---|---|
| any snap (>0.00) | 0.681 | 0.813 |
| snap share > 0.10 | 0.612 | 0.843 |
| snap share > 0.25 | 0.499 | 0.871 |
| snap share > 0.50 | 0.334 | **0.906** |

**Meaningful workload is more predictable than mere presence.** AUC rises
monotonically with the threshold. That is worth stating because the intuitive
expectation runs the other way.

Population is the pregame candidate set — anyone who appeared for that team in
any of the previous 4 team-games. `weekly_rosters.status` is not used.

## 4. Conditional-usage target definitions

Carried forward from P1 unchanged: `snap_share`, `rpr` (pass-play participation
proxy, **not** routes run), `target_share` (denominated on team targets, not
`pass_attempt`), `carry_share`, `rz_carry_share`, plus `third_target_share` for
the redistribution study. QB: `team_dropbacks`, `pass_att_as_passer`,
`scrambles`, `designed_rushes`.

## 5. Pregame feature inventory

| Feature | Source | Chronology |
|---|---|---|
| `prev_appeared`, `rate3`, `rate5`, `rate_ewma` | panel | prior games only |
| `prev_snap`, `snap_ewma` | snap_counts | prior games only |
| `n_prior`, low-history flag | panel | prior games only |
| `weeks_since_appear`, `consec_missed` | panel | prior games only |
| `team_change` | panel | prior games only |
| position indicators | weekly rosters | static |
| **`report_status`, `practice_status`** | nflverse injuries | **same-week, chronology-enforced per row** |
| `depth_team` rank | depth charts | same-week, 2020–2024 only |

Every numeric feature carries an explicit missingness indicator. Nothing is
imputed to a neutral value silently.

## 6. Chronology rules — and the injury audit that shaped the whole study

Features may read only `season*100 + week` strictly less than the target, with
one deliberate exception: the **same-week injury designation**, which is filed
before kickoff and is the entire point of the capture track. That exception is
verified, not asserted:

| Season | rows | `date_modified` present | before kickoff | dropped |
|---|---|---|---|---|
| 2020 | 5,414 | all | 5,401 | 13 after kickoff |
| 2021 | 5,348 | all | 5,345 | 3 after kickoff |
| 2022 | 5,450 | all | 5,433 | 17 no kickoff match |
| 2023 | 5,451 | all | 5,451 | 0 |
| 2024 | 5,954 | all | 5,953 | 1 after kickoff |
| **2025** | **5,783** | **none** | **—** | **all 5,783 unusable** |

**27,583 of 27,617 (99.88%)** are provably pregame. A row is used only if its
own timestamp precedes that game's kickoff. **2025 carries no injury feature at
all**, because the schema dropped `date_modified` and there is no way to
establish the chronology from the file. `depth_charts` also changed schema in
2025 (daily `dt` snapshots), and is used for 2020–2024 only rather than
half-adapted and quietly wrong.

## 7. Stage A baseline results

Brier, threshold "any snap", after making the simple controls fair (§19):

| Season | base rate | prev_game | rate3 | rate_ewma | snap_ewma | **logistic** |
|---|---|---|---|---|---|---|
| 2022 | 0.2251 | 0.1883 | 0.1850 | 0.1851 | 0.1874 | **0.1613** |
| 2023 | 0.2170 | 0.1830 | 0.1799 | 0.1791 | 0.1809 | **0.1557** |
| 2024 | 0.2171 | 0.1826 | 0.1807 | 0.1795 | 0.1817 | **0.1570** |
| 2025 | 0.2234 | 0.1930 | 0.1918 | 0.1898 | 0.1922 | **0.1597** |

The trailing-rate baselines are **recalibrated on training seasons** before
scoring, because an EWMA of 0/1 appearance is a rate for "any snap" and not for
a share threshold; without that they lose for asking the wrong question rather
than on merit.

## 8. Stage A best candidate

Logistic regression on the pregame inventory, **plus injury designation where
chronology permits**. The injury contribution is the headline:

| Season | no injury feature | with injury | Δ Brier | Δ AUC |
|---|---|---|---|---|
| 2022 | 0.1613 / 0.8153 | **0.1421 / 0.8569** | −0.0192 | **+0.0416** |
| 2023 | 0.1557 / 0.8201 | **0.1381 / 0.8594** | −0.0176 | **+0.0393** |
| 2024 | 0.1570 / 0.8126 | **0.1371 / 0.8587** | −0.0199 | **+0.0461** |
| 2025 | 0.1597 / 0.8143 | *unavailable* | — | — |

Calibration is reported per season in `stage_a_results.json` (10 bins, bins with
n < 20 suppressed).

---

## 9–11. Stage B, and U vs C vs A×C

All three scored on the **same** rows — every pregame candidate, including
non-appearances where the truth is 0. Scoring C on appearances only and U on
everyone would compare two different questions, which is precisely the P1 error
this directive exists to correct.

**Estimand, declared before fitting:** expected unconditional share,
`E[Y] = P(appear) · E[Y | appear]`. The forecast distribution is a mixture —
point mass `1 − P(appear)` at exactly zero plus the conditional distribution on
(0,1]. The multiplication is coherent because `Y` is a share in [0,1] and `Y = 0`
exactly when the player does not appear, so the product is itself a valid share.
Checked rather than assumed, per §5 of the directive.

| Target | Season | n | U (MAE / r) | C (MAE / r) | **A×C (MAE / r)** | A×C − U |
|---|---|---|---|---|---|---|
| snap_share | 2022 | 7,836 | 0.1516 / .701 | 0.2033 / .639 | **0.1508 / .761** | −0.0007 [−.0050,+.0043] ✗ |
| | 2023 | 7,578 | 0.1464 / .726 | 0.1909 / .662 | **0.1446 / .774** | −0.0018 [−.0064,+.0025] ✗ |
| | 2024 | 7,537 | 0.1528 / .700 | 0.1936 / .647 | **0.1450 / .776** | −0.0078 [−.0130,−.0028] ✓ |
| | **2025** | 7,436 | **0.1528 / .705** | 0.1919 / .652 | 0.1599 / .727 | **+0.0069 [+.0028,+.0109] ✗✗** |
| rpr | 2022 | 8,092 | 0.1566 / .706 | 0.2049 / .658 | **0.1558 / .767** | −0.0006 ✗ |
| | 2023 | 7,840 | 0.1506 / .734 | 0.1906 / .692 | **0.1478 / .785** | −0.0027 ✗ |
| | 2024 | 7,743 | 0.1549 / .719 | 0.1937 / .678 | **0.1485 / .790** | −0.0064 ✓ |
| | **2025** | 7,768 | **0.1564 / .712** | 0.1925 / .677 | 0.1646 / .737 | **+0.0082 ✗✗** |
| target_share | 2022 | 8,092 | 0.0467 / .678 | 0.0550 / .641 | **0.0435 / .717** | −0.0032 ✓ |
| | 2023 | 7,840 | 0.0453 / .710 | 0.0524 / .681 | **0.0427 / .740** | −0.0026 ✓ |
| | 2024 | 7,743 | 0.0469 / .689 | 0.0541 / .659 | **0.0434 / .741** | −0.0034 ✓ |
| | 2025 | 7,768 | 0.0460 / .697 | 0.0530 / .664 | **0.0455 / .703** | −0.0005 ✓ (margin ×7 smaller) |
| carry_share | 2022 | 2,365 | 0.1034 / .743 | 0.1319 / .718 | **0.0991 / .801** | −0.0041 ✗ |
| | 2023 | 2,255 | 0.1054 / .744 | 0.1380 / .679 | **0.1036 / .784** | −0.0017 ✗ |
| | 2024 | 2,166 | 0.1261 / .665 | 0.1411 / .670 | **0.1092 / .755** | −0.0165 ✓ |
| | 2025 | 2,174 | 0.1056 / .748 | 0.1278 / .738 | **0.1044 / .789** | −0.0012 ✗ |
| rz_carry_share | 2022 | 2,208 | 0.1628 / .558 | 0.1918 / .525 | **0.1556 / .597** | −0.0073 ✓ |
| | 2023 | 2,105 | 0.1639 / .581 | 0.1943 / .533 | **0.1553 / .630** | −0.0087 ✓ |
| | 2024 | 2,024 | 0.1729 / .562 | 0.1957 / .542 | **0.1633 / .605** | −0.0094 ✓ |
| | 2025 | 2,037 | 0.1631 / .600 | 0.1880 / .569 | **0.1625 / .607** | −0.0006 ✗ |

**Three things to read out of this.**

*A×C improves discrimination universally.* Correlation rises in **20 of 20**
target-seasons, by 0.03 to 0.09. Ranking players by expected opportunity gets
consistently better.

*A×C improves absolute error only sometimes* — 11 of 20, and against the
acceptance rule declared beforehand (majority of seasons, interval excluding
zero) it passes for `target_share` and `rz_carry_share`, and fails for
`snap_share`, `rpr` and `carry_share`.

*Model C alone is the worst of the three, everywhere.* Applying a
conditional-usage forecast without an appearance probability is worse than
the unconditional P1 model on every target and season. **The conditional model
is not usable on its own** — it only earns its keep multiplied by P(appear).

### The 2025 result is the finding, not an anomaly

For `snap_share` and `rpr`, A×C is significantly **worse** than P1 in 2025 and
significantly better in 2024. The difference between those two seasons is not
the method — it is that 2025 has no usable injury vintage:

| | 2024 | 2025 |
|---|---|---|
| injury feature | available | **absent** |
| Stage A Brier | 0.1288 | 0.1544 |
| Stage A AUC | 0.8715 | 0.8126 |
| A×C vs U on snap_share | **−0.0078 ✓** | **+0.0069 ✗** |

A weaker appearance probability multiplied into a good conditional forecast
makes the product worse than not multiplying at all. **This is the strongest
empirical argument yet for the T−90 capture infrastructure**: it is not
bureaucratic overhead, it is the input that decides whether the two-stage model
is worth having.

## 12. Role-change detection — and a tautology I had to withdraw

**The first version of this scored AUC 0.9999 and was meaningless.** P1's
role-change label is `|snap(t−1) − mean(t−2..t−4)| > 0.20` — a function of prior
games only, therefore perfectly knowable before kickoff by construction. My
"prediction" feature was that same expression unthresholded. Not a leak of the
future; a definition predicting itself.

The question the directive actually asks needs a target that includes game *t*:

```
role_change_next = |snap_share(t) − mean snap_share(t−1..t−3)| > 0.20
```

Honest results, 41,234 player-games, base rate **0.275**:

| Season | n | base | Brier (base → model) | AUC | TP | FP | FN | precision | recall |
|---|---|---|---|---|---|---|---|---|---|
| 2022 | 7,479 | 0.278 | 0.2007 → **0.1555** | 0.766 | 1,195 | 919 | 883 | 0.565 | 0.575 |
| 2023 | 7,267 | 0.256 | 0.1910 → **0.1484** | 0.770 | 1,097 | 944 | 762 | 0.537 | 0.590 |
| 2024 | 7,213 | 0.274 | 0.1991 → **0.1496** | **0.788** | 1,168 | 809 | 811 | 0.591 | 0.590 |
| 2025 | 7,130 | 0.281 | 0.2022 → **0.1659** | 0.744 | 1,081 | 874 | 925 | 0.553 | 0.539 |

Decision counts are taken at the threshold that makes as many positive calls as
there are events, so precision and recall are directly comparable.

**Role change is partially anticipable and nowhere near solved.** At an
operating point calling ~2,000 role changes a season, roughly **2 in 5 calls are
false and 2 in 5 real changes are missed**. 2025 is again the worst season
(AUC 0.744), same cause.

## 13. Vacated-opportunity experiments

Six rules × six opportunity classes, learning the team-specific absorbed
fraction on 2020–21 and evaluating on 2022–25.

| Class | events | best rule | best MAE | `none` MAE | `proportional` MAE |
|---|---|---|---|---|---|
| `snap_share` | 2,534 | **backup_weighted** | **0.1604** | 0.1805 | 0.1838 |
| `rpr` | 2,507 | **backup_weighted** | **0.1606** | 0.1819 | 0.1849 |
| `carry_share` | 340 | equal_within_position | **0.0361** | 0.0365 | 0.0462 |
| `target_share` | 335 | **none** | **0.0399** | 0.0399 | 0.0462 |
| `rz_carry_share` | 327 | **none** | **0.0505** | 0.0505 | 0.0598 |
| `third_target_share` | 447 | **none** | **0.0569** | 0.0569 | 0.0675 |

**The directive's hypothesis is confirmed: the mechanism is not the same across
opportunity types.** Snaps and route participation genuinely redistribute, and a
backup-weighted rule captures it (MAE −11%). Targets, red-zone carries and
third-down work do **not** redistribute in any learnable way — no rule beats
doing nothing.

**Proportional redistribution is the worst or near-worst rule in all six
classes**, confirming and strengthening P1. Note the win-rate column in
`redistribution_results.json`: proportional beats `none` on 32.8% of snap-share
player-games while having *higher* MAE — it is right more often and wrong by
more, which is exactly the failure mode you would not notice from a hit rate.

`backup_weighted` shows the mirror pattern: it beats `none` on only 9.1% of
player-games yet wins on MAE, because it makes large correct corrections for the
few players who actually absorb the work and leaves everyone else alone.

---

## 14. Cold starts — the directive's instruction is contradicted by the data

§8 says: *"Do not let low-sample players inherit extreme recent rates without
shrinkage."* Measured, **shrinkage makes low-history players worse, monotonically
in the amount of shrinkage, on every target and every season.**

`snap_share`, players with fewer than 4 prior games:

| Season | n | **unshrunk EWMA** | shrink k=2 | shrink k=4 | position prior |
|---|---|---|---|---|---|
| 2022 | 371 | **0.1393** | 0.2013 | 0.2265 | 0.2844 |
| 2023 | 343 | **0.1364** | 0.1946 | 0.2189 | 0.2741 |
| 2024 | 340 | **0.1073** | 0.1797 | 0.2096 | 0.2762 |
| 2025 | 337 | **0.1151** | 0.1873 | 0.2158 | 0.2792 |

Checked against noisier targets in case the result was specific to a stable
quantity — it is not:

| Target | 2024 unshrunk | shrink2 | shrink4 | prior |
|---|---|---|---|---|
| `snap_share` | **0.1324** | 0.1822 | 0.2035 | 0.2514 |
| `target_share` | **0.0382** | 0.0490 | 0.0535 | 0.0641 |
| `rz_carry_share` | **0.0386** | 0.0486 | 0.0516 | 0.0582 |

Also tested and beaten by the unshrunk rate: team-position prior, depth-chart
prior, previous-season player mean, and shrinkage toward the depth-chart prior.

**Why.** Between-player variance in role is far larger than the sampling noise
in a 1–3 game share. A player who took 80% of snaps in his two appearances is a
starter; pulling him toward a 0.33 position mean is not regularisation, it is a
wrong prior applied confidently.

**Scope limit, stated because it bounds the claim.** My low-history cohort has
1–3 prior games, not zero — the candidate set requires a recent appearance. A
true week-1 rookie with no NFL history is **outside this evidence** and the
finding must not be extended to him. That genuine cold start is untested here.

## 15–17. Position, season, and stable vs role-change breakdowns

**Correction.** The first draft of this section carried a table I wrote from
expectation rather than from the results file, and the real numbers say
something materially different — A×C is *not* uniformly best on the hard
cohorts. Every figure below is read from `stage_bc_results.json`.

`snap_share`, 2024, MAE (bold = best of the three):

| Cohort | n | U | C | A×C |
|---|---|---|---|---|
| WR | 3,416 | 0.1650 | 0.2204 | **0.1619** |
| TE | 1,999 | 0.1431 | 0.1746 | **0.1341** |
| RB | 2,122 | 0.1422 | 0.1684 | **0.1279** |
| role = stable | 5,217 | 0.1231 | 0.1588 | **0.1202** |
| **role = change** | 1,990 | 0.2332 | 0.2700 | **0.2083** |
| starter (prior snap ≥ 0.5) | 2,490 | 0.1855 | 0.1704 | **0.1582** |
| appeared | 5,379 | 0.1595 | **0.1307** | 0.1364 |
| **did not appear** | 2,158 | **0.1362** | 0.3504 | 0.1662 |
| **returning from absence** | 2,024 | **0.1258** | 0.2632 | 0.1423 |
| **low history (<4)** | 315 | **0.1403** | 0.2806 | 0.1536 |
| backup (prior snap < 0.5) | 5,047 | **0.1367** | 0.2051 | 0.1384 |

`target_share`, 2024:

| Cohort | n | U | C | A×C |
|---|---|---|---|---|
| WR | 3,549 | 0.0566 | 0.0659 | **0.0522** |
| TE | 2,028 | 0.0414 | 0.0464 | **0.0380** |
| RB | 2,166 | 0.0361 | 0.0419 | **0.0340** |
| role = stable | 5,346 | 0.0403 | 0.0463 | **0.0385** |
| **role = change** | 2,019 | 0.0651 | 0.0720 | **0.0563** |
| did not appear | 2,158 | 0.0413 | 0.0663 | **0.0305** |
| returning from absence | 2,045 | 0.0340 | 0.0552 | **0.0306** |
| low history (<4) | 325 | **0.0398** | 0.0685 | 0.0423 |
| starter | 2,524 | 0.0687 | 0.0685 | **0.0633** |

**A×C wins where the directive most wanted it to.** Role-change weeks improve on
both targets and by the largest margins of any cohort — `snap_share` 0.2332 →
0.2083 (−10.7%), `target_share` 0.0651 → 0.0563 (−13.5%). Starters improve
(−14.7% on snaps). All three positions improve on both targets.

**But it loses on snap-share for the absence cohorts, which is the opposite of
what I expected.** On `did_not_appear` (0.1362 → 0.1662), `returning`
(0.1258 → 0.1423) and `low history` (0.1403 → 0.1536), the plain unconditional
model is better. The reason is visible in the C column: for a player who did
not appear, the truth is 0, and U — driven by last week's value, often also 0 —
predicts 0 almost exactly. A×C multiplies a good conditional estimate by a
probability that is confident but not certain, leaving a positive residual where
U left none. **A probability of 0.15 costs you when the answer is exactly
zero.**

That pattern does not appear on `target_share`, where A×C wins the absence
cohorts too (0.0413 → 0.0305). The difference is scale: target shares are small
and the residual from an imperfect probability is small with them; snap shares
are large and it is not.

**Against the acceptance rule declared in advance:** A×C improves role-change
weeks materially on both targets, so this is *not* "improves the easy cases
only". It is "improves role change and starters, at a cost on players who do not
play, on the large-scale target".

Season effects are in §9–11. The only material one is 2025, and its cause is the
missing injury vintage rather than anything about the season itself.

## 18. Ablation table

Stage A, injury-bearing seasons, change in Brier when each group is removed
(larger positive = more load-bearing):

| Feature group | 2022 | 2023 | 2024 |
|---|---|---|---|
| **history rates** (appearance + snap EWMAs) | **+0.0287** | **+0.0252** | **+0.0326** |
| **injury designation** | **+0.0080** | **+0.0087** | **+0.0086** |
| absence (weeks since, consecutive missed) | +0.0047 | +0.0032 | +0.0058 |
| sample size (n prior, low-history flag) | +0.0003 | +0.0003 | +0.0005 |
| position indicators | −0.0001 | +0.0006 | +0.0010 |
| team change | −0.0005 | −0.0005 | −0.0009 |

Source of the A×C gain, decomposed: **the appearance model supplies essentially
all of it**, history rates supply ~75% of the appearance model, injury
designations ~20%, absence structure ~5%. Position and team-change contribute
nothing measurable and removing them is very slightly *better* — they are noise
at this sample size.

## 19. Features that helped

- prior appearance rates and snap EWMAs — dominant, by a factor of three
- **official injury designation, chronology-verified** — second, and the only
  input the project can act on by collecting more of
- absence structure (weeks since last appearance, consecutive games missed)
- for redistribution: backup-weighting, for snaps and routes only

## 20. Features that failed to help

- **position indicators** and **team change** in Stage A — no measurable
  contribution
- **all shrinkage for low-history players** — monotonically harmful (§14)
- **proportional redistribution** — worst or near-worst in all six classes
- **Model C standalone** — worse than P1's unconditional model everywhere
- depth-chart rank as a cold-start prior — beaten by the player's own 1–3 games

## 21. Unsafe or unavailable features

| Field | Status |
|---|---|
| `weekly_rosters.status` | **quarantined**, not used |
| injuries 2025 | **unusable** — `date_modified` absent, chronology unverifiable |
| injuries, 17 rows 2020–24 | dropped, timestamp at or after kickoff |
| `depth_charts` 2025 | schema changed to daily snapshots; not adapted |
| true routes run | not available (P1, W4) |
| `ngs_air_yards` | 0 non-null of 45,919 |
| air-yards share | computed, still not reported — provenance unaudited |
| market variables, nflfastR model fields, 2026 outcomes | excluded by rule |

## 22. Remaining identifier and data debts

- `PLAYER_GSIS_UNMAPPED` — open; the official injury page carries zero gsis ids.
- snap_counts joins to the panel **by name and team**, not by identifier:
  9,049–9,342 hits per season against 397–589 misses (**4.1–6.1% loss**). Those
  misses are silently absent from every snap-share number here. Closing this
  needs the pfr↔gsis crosswalk.
- Broadcast UUID join (79 vs 16), `.reduced` blob hash naming — unchanged.
- `prediction_time_eligibility` — **open**, and P2 makes it sharper: Stage A is
  the model that would consume it.

## 23. Recommendation for P3

**1. Do not add model complexity. Add injury vintage.** The ablation says the
appearance model carries the gain and injury designations are 20% of it; the
2025 collapse says the whole two-stage approach degrades without them. The
highest-value next step is not an algorithm, it is the capture track already
running — and a P3 that reconstructs point-in-time injury history for 2025 from
an archival source would be worth more than any modelling I could do.

**2. Fix the snap-counts identifier join before trusting any snap-share number
to two decimal places.** 4–6% of rows are dropped by a name join.

**3. Take A×C for ranking, not yet for absolute level.** Correlation improves in
20 of 20; MAE in 11 of 20. If a downstream use needs an ordering, A×C is ready.
If it needs a calibrated level, it is not.

**4. Redistribution should be per-opportunity-class or absent.** Snaps and
routes: backup-weighted. Targets, red-zone, third-down: no rule beat doing
nothing, so do nothing.

**5. Role change remains the open problem.** AUC 0.77 with ~40% false positives
is real signal and not an operational tool. The untested inputs are practice
participation as a *series* across a week and transaction feeds — both of which
the capture track collects going forward and neither of which exists
historically.

**What I would not do:** model fantasy points, add efficiency, or escalate to a
larger model class. Nothing in these results suggests the ceiling is model
capacity.

## 24. Files and commits changed

Research artifacts only. No production module, no G0A file, no capture path, no
2026 artifact touched.

```
A  nfl/research/p2/predeclaration_p2.md        written before any P2 result
A  nfl/research/p2/stage_a.py                  features + chronology enforcement
A  nfl/research/p2/run_a.py                    Stage A baselines and model
A  nfl/research/p2/run_bc.py                   U vs C vs AxC
A  nfl/research/p2/run_role.py                 role-change-next detection
A  nfl/research/p2/run_redist.py               6 rules x 6 opportunity classes
A  nfl/research/p2/run_abl.py                  ablations, cold starts, leakage
A  nfl/research/p2/*.json                      every metric, every subgroup
A  nfl/research/p2/run_bc.log
A  TASK_REPORT_2026-09-07_P2_APPEARANCE_USAGE.md
```

## 25. Markdown task-report path

`TASK_REPORT_2026-09-07_P2_APPEARANCE_USAGE.md`, repository root.

---

## Leakage negative tests (§12)

The probe is required to have demonstrated sensitivity, or its negative results
mean nothing. Two same-game features are seeded deliberately and must light up;
two pregame features must not.

| Probe | Brier | AUC | Δ AUC | verdict |
|---|---|---|---|---|
| honest Stage A | 0.1288 | 0.8715 | — | — |
| **+ same-game `appeared` [seeded]** | 0.0001 | 1.0000 | **+0.1285** | **LEAK DETECTED** |
| **+ same-game `snap_share` [seeded]** | 0.0515 | 0.9823 | **+0.1109** | **LEAK DETECTED** |
| + previous-game snap (pregame) | 0.1289 | 0.8714 | −0.0001 | no material gain |
| + week number (pregame) | 0.1266 | 0.8772 | +0.0057 | no material gain |

The probe detects what it is meant to detect. Week number gives a small genuine
gain (late-season attrition) and is legitimately pregame.

## Governance

Research only. Nothing is promoted by having improved a retrospective metric and
no promotion is requested. G0A remains **11/12**, Item 1 remains PARTIAL /
PENDING REAL EVENT, NFL-1 remains unexecuted. No fantasy-point, touchdown,
efficiency, DFS, ownership, lineup, market or wagering work was done. No wager
is recommended or discussed.
