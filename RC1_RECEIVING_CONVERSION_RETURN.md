# RC1 — RECEIVING CONVERSION ORACLE DECOMPOSITION RETURN

**EXPLORATORY.** 2022–2025 are heavily mined. Everything below is diagnosis,
mechanism and recoverability characterisation. **Nothing here is confirmatory
and nothing is promoted.**

---

## 1. Pre-registration hash

| | |
|---|---|
| File | `nfl/research/rc1/predeclaration_rc1.md` |
| **sha256** | **`34f8ac10be7bc0c5b39ee0e89340a3061ff0910dca803d4975887b8811c02cdd`** |
| Bytes | 9,964 |
| Committed | `RC1 pre-registration: receiving conversion oracle decomposition`, **before any evaluation result was computed or inspected** |
| Verified | a test asserts the hash still matches, so a later edit cannot pass unnoticed |

The hash is of the file content, so it survives the rebases the periodic capture
bot forces on this branch.

### A specification defect I found in my own pre-registration

The pre-registration contradicts itself. §5 requires arm E to **reproduce `Y`
exactly**, and the sentence immediately below requires **all** substitution to
retain dispersion. Both cannot hold: a dispersion-retaining arm E produces a
distribution *around* `Y`, and the one arm whose correct answer is known in
advance — the arm that detects implementation defects in every other arm — could
never pass.

Cause: I imported R1's lesson into the wrong place. R1 was about substituting a
**candidate model's** estimate as a point value, which destroyed dispersion of
CV 0.914. That governs the composition test. It does not govern an **oracle**,
where collapsing dispersion is what "perfect" means.

Resolved by splitting the sentence into the two rules it conflated, **not** by
editing the pre-registration, which §11 forbids. Recorded in
`nfl/research/rc1/addendum_rc1_substitution.md`, written after the simulator and
**before running it**. Each rule now has its own test.

---

## 2. Data and provenance audit

Source: nflverse `play_by_play_{season}.csv.gz`, 2020–2025, `season_type == REG`,
CC BY 4.0. **No FTN. No PFR-restricted field. No market, DFS, props or 2026 data.**

**Target rule, inherited unchanged** from `nfl/research/p1/build_panel.py:88–95`:
`receiver_player_id` set **AND** `pass_attempt == 1`, two-point attempts excluded.

**The sack trap — measured, not assumed.** Every sack in every season carries
`pass_attempt == 1`: 1,135 / 1,244 / 1,297 / 1,410 / 1,314 / 1,287 for 2020–2025,
**all of them**. A target defined on `pass_attempt` alone would put every sack in
the receiving denominator. What actually excludes them is that **no sack carries
a `receiver_player_id` — 0 in every season.** Tested, not trusted.

| | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 |
|---|---|---|---|---|---|---|
| targets | 17,309 | 18,058 | 17,306 | 17,483 | 17,013 | 16,609 |
| receptions | 11,756 | 12,121 | 11,605 | 11,808 | 11,629 | 11,217 |
| incompletions | 5,553 | 5,937 | 5,701 | 5,675 | 5,384 | 5,392 |
| targets, null `air_yards` | 1 | 1 | 0 | 0 | 0 | 0 |
| receptions, null `receiving_yards` | 0 | 0 | 0 | 0 | 0 | 0 |
| `air_yards + yac == receiving_yards` | 11,750 | 12,119 | 11,598 | 11,801 | 11,625 | 11,214 |
| identity violations | 5 | 1 | 7 | 7 | 4 | 2 |
| receptions with a lateral | 8 | 14 | 14 | 8 | 20 | 18 |
| incompletions with non-null `yac` | 0 | 0 | 0 | 0 | 0 | 0 |
| incompletions with non-zero `receiving_yards` | 0 | 0 | 0 | 0 | 0 | 0 |

- **NULL is not zero.** `receiving_yards` and `yards_after_catch` are NULL on
  every incompletion and never 0. The builder counts a null as a **missing
  observation** and never sums it as 0; folding it in would bias any per-target
  rate downward by exactly the missing count.
- **The air-yards / YAC identity holds on 99.94% of receptions.** The violations
  are fumble plays where `receiving_yards` is adjusted. `receiving_yards` is
  therefore authoritative for caught-ball yardage and the AY/YAC split is
  **descriptive only** — it is never used to reconstruct the total. The `air_yard
  + YAC` decomposition in the directive's §2 is therefore reported as audited but
  **not** used as a decomposition axis, because its provenance supports
  description and not reconstruction.
- **`ngs_air_yards` REMAINS QUARANTINED.** The standing project note says
  "all-null"; measured here it is more specific — `pbp_participation` carries it
  on **36.31%** of 2022 plays and **0.00%** of 2023 and 2025 plays. It dies after
  2022. It is a **different field** from pbp's own `air_yards`, which is
  populated on essentially every target. Only the latter was read, and only
  descriptively.

**Identity check against the accepted panel.** The primitives built here
reproduce `panel_enriched.targets` for **all 25,765** player-games carrying a
target — **0 mismatches**, **103,559 targets** on both sides.

---

## 3. Sample sizes

| Season | n rows | games | mean `Y` | zero-target rows |
|---|---|---|---|---|
| 2022 | 5,645 | 271 | 22.29 | 1,378 |
| 2023 | 5,704 | 272 | 22.30 | 1,408 |
| 2024 | 5,585 | 272 | 22.57 | 1,398 |
| 2025 | 5,587 | 272 | 21.66 | 1,361 |
| **pooled** | **22,521** | **1,087** | 22.20 | 5,545 |

Zero-target appearances **stay in the frame**. Dropping them would condition on
the estimand and would flatter every arm; a test asserts they are present and
carry `Y = 0` rather than being treated as missing.

---

## 4. Baseline receiving-yard performance

Chronology-safe, prior-only, 2,000 draws per player-game, walk-forward, fitted on
strictly prior seasons.

| Metric | Pooled 2022–2025 |
|---|---|
| **CRPS** | **11.1798** (game-clustered 95% CI [11.026, 11.327]) |
| MAE | 17.298 |
| RMSE | 24.013 |
| bias | **+2.180** |
| Pearson r | 0.6019 |
| SD ratio (pred mean / actual) | 0.6222 |
| coverage 50 / 80 / 90 / 95 | **0.650 / 0.883 / 0.943 / 0.969** |

Per season CRPS: 11.1223 / 11.2715 / 11.2881 / 11.0360.

**Two baseline defects, stated plainly rather than buried.** The baseline
**over-predicts by 2.18 yards** and is **over-covered at every nominal level** —
65.0% inside a nominal 50% interval, 96.9% inside a nominal 95%. Its intervals
are too wide. Neither is fixed here: repairing the baseline after seeing the
decomposition is exactly the result-driven change §11 forbids. Both are recorded
as known properties of the baseline that any later work must address, and both
mean the coverage row above must **not** be read as calibration evidence.

**Why resampling and not a Gaussian.** Measured on 70,136 per-reception
yardages: skew **2.197**, excess kurtosis **7.830**, and `P(gain > 40 yds)` is
**0.0203** empirically against **0.0016** under a fitted Normal — a Gaussian
understates that tail **thirteenfold**. The pre-registration fixed resampling
before this was computed.

---

## 5. Oracle decomposition

`Y = T × C × V`. **Arm E — all three perfect — reproduces every realised `Y`
exactly** in all four seasons: max |error| 1.4e-14 to 2.8e-14 (float epsilon),
max draw spread **exactly 0.0**. The mechanical identity holds.

### Coalition CRPS reductions (pooled, n = 22,521, 1,087 games)

| Oracle coalition | arm CRPS | reduction |
|---|---|---|
| baseline | 11.1798 | 0.0000 |
| C | 10.4314 | 0.7484 |
| V | 9.6478 | 1.5320 |
| C + V | 8.9740 | 2.2058 |
| T | 7.2539 | 3.9259 |
| C + T | 5.7919 | 5.3879 |
| T + V | 3.9606 | 7.2192 |
| C + T + V | **0.0000** | 11.1798 |

**The components are strongly complementary, not additive.** Singles sum to
6.206 against a grand coalition of 11.180 — a **three-way interaction of +4.97**.
Knowing volume makes conversion far more valuable and vice versa. This is exactly
why an order-invariant attribution was predeclared: a sequential substitution
would have handed that 4.97 to whichever component happened to go first.

### Shapley attribution, with game-clustered 95% intervals

| Component | Shapley CRPS reduction | 95% CI | share | share CI |
|---|---|---|---|---|
| **T** target volume | **6.0211** | [5.9142, 6.1285] | **53.86%** | [52.90%, 54.82%] |
| **C** catch conversion | **1.9257** | [1.8749, 1.9830] | **17.22%** | [16.77%, 17.74%] |
| **V** yards per reception | **3.2331** | [3.1525, 3.3159] | **28.92%** | [28.20%, 29.66%] |

Efficiency gap **0.00e+00** — the parts sum exactly to the grand coalition.
1,000 resamples clustered by `game_id`.

**Conversion (C + V) holds 46.14% of the oracle CRPS reduction.** Opportunity
still leads at 53.86%, but conversion is not a rounding error at the oracle
level. **Oracle share is not modelability** — §6 is where that is tested, and the
answer there is very different.

---

## 6. Simple recoverability results

The closed four-rung ladder. No feature search, no hyperparameter tuning; K = 4
and half-life 2 are both inherited project constants.

### Primitive level

**Catch conversion `C`** (n = 16,976 player-games with ≥1 target), weighted MAE:

| Rung | wMAE | MAE | RMSE | bias |
|---|---|---|---|---|
| L0 pooled positional | 0.18513 | 0.25191 | 0.31157 | +0.00190 |
| **L1 shrinkage** | **0.18387** | 0.24975 | 0.31321 | +0.00389 |
| L2 EWMA hl 2 | 0.19914 | 0.26193 | 0.33753 | +0.00183 |
| L3 shrunk EWMA | 0.19373 | 0.25762 | 0.32643 | +0.00251 |

Best L1, **+0.680%** weighted MAE against the pooled positional value.

**Yards per reception `V`** (n = 15,247 player-games with ≥1 reception):

| Rung | wMAE | MAE | RMSE | bias |
|---|---|---|---|---|
| L0 pooled positional | 4.04110 | 4.88971 | 7.04203 | +0.10568 |
| **L1 shrinkage** | **4.03906** | 4.88437 | 7.04949 | +0.12483 |
| L2 EWMA hl 2 | 4.41945 | 5.24816 | 7.56671 | +0.05026 |
| L3 shrunk EWMA | 4.26406 | 5.07853 | 7.28897 | +0.06083 |

Best L1, **+0.050%** weighted MAE — essentially nothing.

**Both recency rungs are WORSE than knowing nothing about the player.** L2 loses
7.6% on `C` and 9.4% on `V` against the pooled positional value. Recent
conversion history is not merely uninformative here; weighting it heavily is
actively harmful, which is what you would expect if game-level conversion is
close to noise around a slow-moving player level.

---

## 7. Downstream composition results

Mandatory per §7 and per R1. Target machinery held fixed; substitution is
**draw-preserving** — the candidate supplies a mean and every per-reception draw
is scaled by `V̂ / mean(draws)`, so the coefficient of variation survives
(asserted by test: 1.2202 → 1.2202).

| Arm | CRPS | vs baseline | player info removed |
|---|---|---|---|
| accepted baseline | 11.1798 | — | — |
| **C = L1, V = L1** (calibration) | 11.1772 | **+0.0235%** | none |
| C = L0, V = L1 | 11.2318 | −0.4651% | catch conversion only |
| C = L1, V = L0 | 11.2862 | −0.9512% | yards per reception only |
| **C = L0, V = L0** | 11.2850 | **−0.9409%** | both |

**The calibration arm is the load-bearing row.** L1 is the baseline's own rule,
so routing it through the candidate machinery must land on the baseline — and it
does, to +0.02%. Without that check no other row here would mean anything,
because a substitution apparatus that shifted the answer by itself would
contaminate every comparison.

**So: every scrap of player-specific conversion information available to this
ladder is worth 0.1078 CRPS — 0.964% against the calibration arm, 0.941%
against the raw baseline.**

Against a conversion oracle opportunity of 2.2058 CRPS, this family recovered
**4.89% of the currently measured conversion oracle opportunity.**

### The primitive-level ranking REVERSES under composition

This is the single most useful thing in the section, and it is exactly why §7 is
mandatory.

| | primitive gain vs L0 | downstream cost of removing it |
|---|---|---|
| catch conversion `C` | **+0.680%** (the better primitive) | 0.465% |
| yards per reception `V` | +0.050% (barely anything) | **0.951%** (the bigger downstream effect) |

`C` is roughly **fourteen times** the better primitive and contributes **half**
as much downstream. `V` looks almost worthless in isolation and carries nearly
all of the composed value.

The mechanism is not mysterious once stated: `Y = T × C × V`, so an error in `V`
is multiplied by every reception while an error in `C` moves the reception count
by a fraction of one catch. A primitive metric measures the estimate; only
composition measures what the estimate *does*. R1 found this in the harmful
direction — a better primitive worsening the composed simulator. Here it appears
in the ranking direction, and it would have produced the wrong research priority
had the ladder been judged on primitive metrics alone.

The two removals also do not add: 0.465% + 0.951% = 1.42% against 0.94% for
removing both, so the two conversion channels are partly redundant.

Stated in the project's required form, and note which way round it goes:
**this model family recovered 4.89% of the currently measured conversion oracle
opportunity** — **not** "conversion is only 4.89% recoverable."

---

## 8. Subgroup diagnostics

Conversion share of the oracle CRPS reduction (C + V):

| Dimension | Cohort | n | base CRPS | mean Y | C | V | **conversion** |
|---|---|---|---|---|---|---|---|
| position | WR | 10,085 | 15.075 | 31.7 | 19.3% | 28.3% | **47.6%** |
| position | RB | 6,278 | 6.841 | 11.3 | 11.2% | 35.0% | **46.2%** |
| position | TE | 6,158 | 9.225 | 17.8 | 16.3% | 25.9% | **42.2%** |
| target volume | high | 11,642 | 15.600 | 34.8 | 18.6% | 30.2% | **48.8%** |
| target volume | low | 10,879 | 6.450 | 8.7 | 13.7% | 25.6% | **39.3%** |
| history | 25+ | 14,231 | 12.253 | 25.7 | 17.7% | 29.1% | **46.8%** |
| history | 10–24 | 4,923 | 9.695 | 17.7 | 16.8% | 29.4% | **46.2%** |
| history | 4–9 | 2,186 | 8.777 | 15.0 | 16.5% | 29.7% | **46.2%** |
| history | <4 | 1,181 | 8.880 | 12.6 | 12.9% | 21.8% | **34.7%** |
| role change | stable | 13,264 | 11.327 | 23.6 | 17.6% | 29.2% | **46.9%** |
| role change | up | 4,615 | 11.533 | 22.3 | 17.7% | 29.0% | **46.8%** |
| role change | down | 4,642 | 10.409 | 18.1 | 15.3% | 27.9% | **43.3%** |

**Conversion uncertainty is close to homogeneous, not concentrated.** Ten of the
twelve cohorts sit in a 42–49% band. The two genuine departures both move the
*same* way and for the same reason: **short history (<4 games, 34.7%)** and **low
target volume (39.3%)** shift weight back onto opportunity. When you know little
about a player, or he barely plays, the dominant question is whether he sees the
ball at all.

The **RB / WR split within conversion** is the one structural difference worth
naming: RB conversion is overwhelmingly `V` (35.0% vs C 11.2%) while WR is much
more balanced (28.3% / 19.3%). Running backs catch a high, stable share of their
targets; the variance is in how far the catch goes.

Role-change cohorts show **no material conversion signature** — 43–47% across up,
stable and down. Whatever role transitions do to this system, they do it through
opportunity, not conversion.

---

## 9. Adversarial and guard-deletion results

`nfl/tests/test_rc1_receiving.py` — **all sections pass.**

| Required case | Section | Result |
|---|---|---|
| current-game leakage | A | inflating the current game moves **no** `h_*` field of that row |
| future-game leakage | A2 | a later game leaves an earlier row untouched |
| same-week chronology | B | **1,318** player-ordinal pairs carry two rows; both have identical prior history — neither read the other |
| target/reception denominators | C | no row has R > T, yards with zero targets, or yards with zero receptions |
| sacks in receiving denominators | D | every sack has `pass_attempt == 1`; **no** sack has a receiver — asserted per season |
| null becoming zero | E | asserted per season, plus the builder's missing-counters |
| postgame fields as predictors | F | no prior-only field is named after a realised outcome; `weekly_rosters.status` absent |
| oracle leakage into a non-oracle arm | G | baseline **bit-identical** on corrupted rows; oracle-V moves; oracle-T correctly does not |
| point substitution destroying dispersion | H | oracle collapses (correct); candidate C and V both preserve; **CV 1.2202 → 1.2202** |
| identity failure | I | arm E exact; a 0.01% perturbation is detected; Shapley efficient and order-invariant |
| result-driven eligibility | J | pre-registration hash asserted; zero-target rows present; seed a fixed constant |

### Guard deletions (2 required, 2 delivered)

| Guard | With guard | Bypassed |
|---|---|---|
| **chronology prefix cut** (`bisect` in `rc1_lib.attach_prior`) | 0 shared-ordinal pairs leak | **625 pairs leak** — the same-week leak returns |
| **arm separation** (`oracle` flag in `rc1_sim.simulate`) | honest baseline CRPS 11.709 | secretly oracling everything scores **0.00 CRPS** |

### Defects found and fixed during this work — all mine

1. **Pre-registration self-contradiction** on substitution (§1 above). Recorded in an addendum committed before the run, not edited away.
2. **`np.add.reduceat` cannot express a zero-length segment.** A draw with zero receptions raised. Replaced with a cumsum difference that returns exactly 0 there rather than borrowing a neighbouring value.
3. **All rows shared one RNG stream.** Each row consumes a variable number of draws, so a change anywhere shifted every *later* row. The leakage probe caught it: 21 rows moved whose prior features had not. Fixed to per-row streams seeded on `(seed, ordinal, player)`; row-order independence is now asserted. **Effect on results: Shapley shares moved ≤ 0.02 pp and baseline CRPS by 0.0006** — both pre- and post-fix numbers are recorded so the fix can be checked rather than trusted.
4. **The audit JSON was a `Counter`,** which omits keys it never incremented — so `sack_WITH_receiver = 0` was *absent*, and `.get(k, 0)` would have let "never measured" pass as "measured zero". Every audited key is now written explicitly and a test asserts presence before any zero is believed.
5. **Two of my own probes were wrong** and would have passed vacuously: the leakage probe corrupted rows other probe rows used as history, and its "teeth" arm oracled `T` while the corruption touched `Y` and `R`. Both rewritten.

---

## 10. Unresolved information gaps

- **Laterals**: 8–20 receptions per season gain yardage not attributed through
  `receiver_player_id`. Too small to move a decomposition; recorded, not ignored.
- **Air-yards / YAC as a decomposition axis**: audited and available, but the
  identity fails on fumble-adjusted plays, so it supports description and not
  reconstruction. The directive's conditional third layer is therefore **not**
  claimed. Splitting `V` into air and YAC components remains open and would need
  its own provenance work.
- **True routes run**: still absent from every authorized source. The prior
  information-gap study's `PROSPECTIVE_DATA_PATH_ONLY` stands, unchanged by this
  work.
- **FTN**: not used, not assumed, not designed around. Commercial acquisition is
  externally pending.
- **Defensive and game-context conditioning**: not attempted. No opponent
  adjustment was made because none is established as PIT-safe here.
- **The baseline's own calibration** (bias +2.18, over-coverage at all four
  levels) is unresolved by design — fixing it after seeing the decomposition
  would be a result-driven change.

---

## 11. Repository-wide test result

**256 test functions, 0 failures** (was 245 before this work).

---

## 12. Commits and final HEAD

| Commit | |
|---|---|
| `RC1 pre-registration: receiving conversion oracle decomposition` | hashed and pushed **before** any result |
| `RC1 addendum: the pre-registration contradicts itself on substitution` | written **before** the run |
| `RC1: oracle decomposition, ladder, composition, adversarial suite` | this work |

Hashes are recorded in the commit log rather than inline, because the periodic
capture bot pushes to `main` every 30 minutes and rebases this branch, which
rewrites any short hash written into a file that same commit contains. **The
stable identifiers are the commit titles and the pre-registration sha256.**

---

## 13. State classification

# `SIGNAL_WEAK`

Precisely what that means here, and what it does not.

**It means:** receiving conversion holds **46.14%** of the oracle CRPS reduction
(C 17.22% + V 28.92%), and the closed four-rung ladder recovers **4.89%** of that
opportunity — worth **0.96%** of baseline CRPS. Both recency rungs are *worse*
than knowing nothing about the player. The only rung that helps is shrinkage
toward the positional pool, which the accepted baseline already does.

**It does not mean conversion is unmodelable.** Oracle share is not
modelability, and a four-rung ladder on already-authorized inputs cannot
establish a ceiling. What it establishes is that **the conversion signal
reachable from the inputs this project currently holds is small**, and that
opportunity continues to dominate at 53.86%.

**One methodological finding worth carrying forward regardless of the verdict:**
the primitive-level ranking of the two conversion channels **reverses** under
composition. Any future receiving work that ranks conversion candidates on
primitive metrics alone will get the priority backwards.

**The practical reading**, offered as a diagnosis and not a recommendation:
serious modelling effort aimed at catch conversion or yards-per-reception from
current inputs has very little measured headroom. If conversion is to be
attacked, it needs information this project does not have — and the honest next
question is which information, not which estimator.

---

**Nothing is promoted.** P4C unchanged. ABC_MPR unchanged and still frozen.
Stage 2 `ewma_hl2` unchanged as accepted P. `ewma_hl1` remains a development
candidate only. R remains `SIGNAL_WEAK / COMPOSITION_FAILED`.
`PROSPECTIVE_DATA_PATH_ONLY` unchanged. **G0A remains 11/12. NFL-1 remains NOT
AUTHORIZED.** No DFS, props, markets, optimization or portfolio work was begun.
