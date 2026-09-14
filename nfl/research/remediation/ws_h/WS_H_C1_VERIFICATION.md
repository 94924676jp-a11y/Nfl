# WS-H — corrected C1 evidence

**CODE CHANGED: NO.** Every write is under `nfl/research/remediation/ws_h/`.
`nfl/research/slate_audit/C1_EVALUATION.json` was hashed before and after every
step and is byte-identical (`a79772b4cc3c1e37…`); the evaluation was re-run
through a scratchpad driver so `c1_eval.main()` could not reach it. The only
suite run was `run_suite.py --only test_c1_denominator` (25 checks, 0 failing).
No market data was opened at any point.

The corrected artifact is
`nfl/research/remediation/ws_h/C1_EVIDENCE_CORRECTED.json`, 37 claims:
**22 VALID, 10 CORRECTED, 5 INVALIDATED.**

Brief: verify independently, do not copy WS02. Three of WS02's own conclusions
did not survive that, and they are classified here on the same terms as
everything else.

---

## 1. The short version

The repair is right. Its mechanism, its direction, its scope discipline and its
refusal path all survive. What does not survive is a layer of paperwork and one
number WS02 itself preserved.

* The **causal diagnosis is VALID.** `p4c_build` fits the `other` mass on
  `team_carries`; `run_forecast` hands the allocator A1's `rb` category. The
  double subtraction is real.
* The **three registered numbers are CORRECTED** exactly as WS02 said —
  0.008754 → **0.010774**, 22.7× → **18.46×**, "agree to three decimals" →
  they differ by 0.0071. I reproduce all three independently.
* **WS02's explanation of why those numbers are wrong is INVALIDATED.** It
  blames a 2020-inclusive panel. The population moves the number by 0.0002 and
  *in the wrong direction*. The driver is a different **estimator** on a
  different **source file** with a different **denominator column**, worth
  0.0021.
* **WS02's own "honest statement" does not survive its own critique.** It
  invalidated every absolute metric because the budget is ~15% short, then
  quoted pooled CRPS −0.322 [−0.336, −0.309] as what remains. CRPS is in
  carries. On a correctly-scaled budget it is **−0.182997 [−0.195603,
  −0.170441]**. The sign, the intervals excluding zero and the three-season
  consistency survive; the magnitude does not.
* **New:** the C1 evidence does **not** inherit WS-F's zero-row leak. 40.6–44.9%
  of scored rows carry a realised zero and none are dropped.

---

## 2. Verdict table

| # | Item | Verdict |
|---|---|---|
| 1 | Exact FITTED denominator (`team_carries`, `mall ≡ 1.0`) | **VALID** |
| 2 | Exact CONSUMED denominator (A1 `rb`) | **VALID** |
| 3 | Fitted mass 0.198875 | **VALID** |
| 4 | Applied partition mass | **CORRECTED** 0.008754 → 0.010774 |
| 5 | Overstatement factor | **CORRECTED** 22.7× → 18.46× |
| 6 | "Agree to three decimals is the identification" | **INVALIDATED** |
| 7 | Historical non-RB mass 0.1918 | **CORRECTED** → 0.190173 / 0.191059 |
| 8 | WS02's root cause for 6 and 7 (2020 inclusion) | **INVALIDATED** |
| 9 | Units at every boundary | **VALID** for the allocator; the harness boundary is **INVALIDATED** |
| 10 | `team_volume` "ORACLED at the realised team level" | **INVALIDATED** |
| 11 | All absolute metrics in `C1_EVALUATION.json` | **INVALIDATED** |
| 12 | Pooled CRPS delta and interval | **CORRECTED** −0.322 → −0.183 |
| 13 | Clustered bootstrap design, 1,630 clusters | **VALID** |
| 14 | Acceptance criteria 1, 2, 3, 5 | **VALID** |
| 15 | Acceptance criterion 4 (no overshoot) | **CORRECTED** — passes, but was not measured |
| 16 | Carry conservation | **VALID**, 0 violations, independently recomputed |
| 17 | Receiving bit-identity | **VALID**, on a *real* A1 budget |
| 18 | Q9 frozen identity | **VALID** |
| 19 | Zero-completion / no selection on outcome | **VALID** (new) |
| 20 | "OWN-5's second defect is REAL and unaddressed" | **INVALIDATED** |
| 21 | Hardcoded 0.0088 in a passing test | **VALID**, demonstrated |

---

## 3. The denominators, re-derived

### Fitted — `p4c_build.py:157`

    pool[k] = clip(mall[k] - ms[k], 0, 0.95)

`mall` sums every position's `s_carries`; `s_carries = y_carries /
den['team_carries']` (`p4b_panel.py:56`). I did not take "the panel closes" on
trust. Over the **2,718** pre-2026 team-games excluding 2020: mean
**1.00000000**, min 0.9999999999999998, max 1.0000000000000002, **zero**
team-games deviating by more than 1e-6.

So the fitted quantity is exactly `1 − (modelled RBs' share of TEAM carries)`.
Recomputed from `panel_enriched.pkl`: **0.19887535274028778**, matching the
production parameter object.

### Consumed — `run_forecast.py:755`

    rushing_budget = {t: a1.value['carries'][(t, 'rb')] for t in teams}

A1's league shares, read live from the frozen parameter object
(`nfl/derived/rushing_a1_params_2026w01.json`, sha16 `9d56c2604832cff7`):

| category | share |
|---|---|
| rb | 0.860235 |
| designed_qb | 0.068808 |
| wr | 0.036027 |
| kneel | 0.028758 |
| fringe | 0.003658 |
| te | 0.002514 |
| **sum** | **1.0000000000** |

Every one of those matches the brief. `kneel`, `designed_qb`, `wr`, `te` and
`fringe` are gone before the allocator sees the budget, and the mass fitted
against it is the residual on the whole team. The double subtraction is real.

### Repaired — `p4c_build.py:183-187`, selected at `football_engine.py:534-558`

`mass_pool_partition` mean **0.010773708112537861** on 2,718 team-games, 0
dropped. Ratio **18.459321975708008**.

Independent panel recomputation: ratio-of-means 0.010773, mean-of-ratios
0.010792 — the estimator choice is worth about 0.00002, which is two orders
below the discrepancy under discussion.

**Shape, which no committed artifact records.** The partition pool is **exactly
zero in 95.33%** of training team-games (median 0.0) against a baseline pool
that is broadly spread (median 0.1786). C1 does not merely shift the `other`
mass down; it replaces a diffuse distribution with a spike at zero plus a thin
right tail. In most draws the modelled backs now take the *entire* A1 `rb`
budget and the `other` container is empty. That is the mechanism behind the
coverage change.

---

## 4. Where the registered 0.008754 actually comes from, and why WS02's account is wrong

WS02 says the registered figures come from a 2020-inclusive panel, and that
aligning the populations resolves them. **Measured, it does not.**

`denominator.py:193` computes `correct_other = (rb_all − (1 − fitted)) / rb_all`
with `fitted = 0.198875` and `rb_all` read from OWN-5's artifact. Feeding that
same formula different `rb_all` estimates:

| `rb_all` | source | `correct_other` |
|---|---|---|
| 0.8082 (rounded, as registered) | OWN-5 estimator, all seasons | **0.008754** |
| 0.808221 | OWN-5 estimator, all seasons, unrounded | 0.008780 |
| 0.808139 | OWN-5 estimator, **ex-2020** | 0.008679 |
| 0.809985 | **fit estimator**, all seasons | 0.010938 |
| 0.809827 | fit estimator, ex-2020 | 0.010746 |
| — | **what the code produces** | **0.010774** |

Read the two middle rows against each other.

* Holding the estimator fixed and **changing the population**: −0.000101
  (OWN-5) or −0.000193 (fit). It moves the number *away* from 0.010774.
* Holding the population fixed and **changing the estimator**: +0.002159 (all
  seasons) or +0.002066 (ex-2020).

The estimator is worth **ten to twenty times** the population, and it is the
only term with the right sign. Same picture on the non-RB mass itself: OWN-5's
estimator gives 0.191779 on all seasons and **0.191861 excluding 2020** — it
barely moves. My own recomputation on the 2020-*inclusive* population with the
**fit's** estimator gives 0.190015, not 0.1918.

**The actual cause.** `own5/audit_rush_ownership.historical_from_panel` reads a
different file (`nfl/research/inputs/panel_p3.csv.gz`, not
`p4b/panel_enriched.pkl`), a different denominator column (`team_rush_att`, not
`team_carries`), and a different estimator (ratio of means of raw `carries`, not
the mean of per-team-game `s_carries`). The two denominator columns have the
*same mean* (26.9157 on the ex-2020 window), so this is a Jensen gap between
ratio-of-means and mean-of-ratios.

This matters operationally: the remedy WS02's diagnosis implies — align the
season windows — would move the number by 0.0002 and leave the discrepancy
intact.

**What survives from WS02 here:** every corrected *value*. Only the explanation
is withdrawn.

One smaller correction: WS02 writes that `0.010773 × 0.809827 = 0.008724`
"closes the decomposition to five decimals". The exact gap is
`0.19887535 − 0.190173 = 0.008702`. That closes to **four** decimals.

---

## 5. The harness, and the number WS02 should not have kept

`c1_eval.run()` at HEAD reproduces the committed artifact **byte for byte** —
sha256 `a79772b4cc3c1e376a31590151d149e077421da7fecb7f18466dff70df3f9324`
before, after, and for my own re-serialisation.

`C1_EVALUATION.json` declares `"team_volume": "ORACLED at the realised team
level"`. It is not. `te` is filtered to `f_n_prior >= 1`, so the group sum is the
realised **modelled-RB** level, and `c1_eval.py:222` then multiplies it by
`rb_share = 0.860235` — a team→RB conversion applied to an RB-level quantity.

| per team-game | 2022 | 2023 | 2024 |
|---|---|---|---|
| modelled-RB carries (what `team_lvl` is) | 21.5701 | 21.4081 | 21.5956 |
| all-RB carries | 21.8376 | 21.5754 | 21.7555 |
| team carries | 27.2509 | 26.8493 | 26.9982 |
| A1 analogue, (team − scr) × 0.860235 | 22.0058 | 21.4600 | 21.5454 |
| **budget both arms actually get** | **18.5554** | **18.4160** | **18.5773** |
| shortfall vs A1 analogue | −15.68% | −14.18% | −13.78% |

WS02's figures reproduce to four decimals. **This part is VALID and it is
WS02's largest finding.**

### Where WS02 then goes wrong

Its Bottom Line reads: *"The honest statement of the result is 'C1 raises the
modelled backs' share of their budget by a factor of 1.22 and improves pooled
CRPS by 0.322 with a team-game clustered interval of [−0.336, −0.309]'."*

CRPS is in **carries**. It scales with the budget exactly as bias and MAE do.
A quantity cannot be invalidated as an absolute metric in item 7 and preserved
as the headline in the same document.

I re-ran the evaluation varying **one thing** — the budget level — holding the
arms, seeds, weights, appearance draws, test rows, pools and bootstrap
identical. The `AS_SHIPPED` variant reproduces every committed per-season number
exactly, which is what licenses reading the rest as a pure re-scaling.

**Primary corrected budget: realised all-RB carries.** That is the realised
value of the quantity A1's `rb` category estimates, and it is the budget
coherent with `other`, which exists precisely to hold the unmodelled backs. The
A1-analogue budget is reported alongside because it is equally defensible.

| pooled | shipped | **corrected (all-RB oracle)** |
|---|---|---|
| CRPS BASELINE | 2.171036 | **1.913023** |
| CRPS C1 | 1.849061 | **1.730026** |
| **CRPS difference** | **−0.321975** | **−0.182997** |
| clustered 95% | [−0.335537, −0.308541] | **[−0.195603, −0.170441]** |
| n clusters | 1,630 | 1,630 |
| relative improvement | 14.83% | **9.57%** |
| bias BASELINE | −1.624487 | **−1.010582** |
| bias C1 | −0.809350 | **−0.054454** |
| MAE BASELINE → C1 | 3.093877 → 2.798075 | **2.872961 → 2.678038** |
| coverage BASELINE | 0.5588 / 0.7305 / 0.8058 | **0.6141 / 0.8078 / 0.8899** |
| coverage C1 | 0.6317 / 0.8202 / 0.8864 | **0.6992 / 0.8985 / 0.9549** |

Per season, C1 − BASELINE CRPS on the corrected oracle: **−0.184153**
[−0.204298, −0.160956]; **−0.187333** [−0.208316, −0.166245]; **−0.177223**
[−0.202551, −0.151365]. Three of three negative, three of three excluding zero.
Under the A1-analogue budget: −0.168578, −0.194522, −0.188114 — same picture.

**Acceptance criterion 4** passes on the corrected measurement (|C1 bias|
0.054454 < 1.010582, per-season C1 bias −0.028136 / −0.065205 / −0.071997, all
still negative so no overshoot). But under the A1-analogue budget 2022 flips to
**+0.009496** — which side of zero C1 lands on in a single season is settled by
which of two defensible budget definitions you pick, not by the data. No
equivalence margin and no TOST were predeclared, so **nothing here is a claim
that C1 is unbiased.**

**Coverage, recorded not diagnosed.** On a correct budget both arms *over*-cover.
The shipped artifact's near-nominal look was a product of the short budget.
Interpretation is constrained: 40.6–44.9% of scored rows have a realised zero,
the predictive distribution carries a large point mass at zero, and a percentile
interval is conservative by construction there.

### What is genuinely budget-invariant

The ratio of the two arms' mean projections, measured across three budgets that
differ by 18%:

| season | as shipped | all-RB oracle | A1 analogue |
|---|---|---|---|
| 2022 | 1.222153 | 1.222105 | 1.222075 |
| 2023 | 1.232151 | 1.232138 | 1.232149 |
| 2024 | 1.235456 | 1.235454 | 1.235414 |

Invariant to six decimals. Pooled **×1.230**. *That* is what survives a budget
error, and it is why the direction is safe while every level is not.

---

## 6. Carry conservation

`rushing_a1.allocate` on 2 teams × 200 draws, fed **real** D1 team-carry draws
from `team_volume_v1.forecast` through `scramble_coherence.couple`:
`PASS A1_RUSH_ALLOCATION`, with `closure_violations 0`, `negative_allocations 0`,
`category_budget_overruns 0`, `ledger_violations 0`, `carries_with_no_owner 0`,
`carries_with_two_owners 0`, `clipping_applied 0`,
`survivor_renormalisation_applied 0`, `post_hoc_repairs 0`, `deleted_draws 0`,
`scrambles_redrawn 0`.

I did not trust that evidence block. Recomputing from the returned category
arrays: **0 violations across 400 draw cells** of both
`Σ(kneel, designed_qb, rb, wr, te, fringe) == team_carries − scrambles` and
"no negative allocation". The engine's `RUSHING_BUDGET_EXCEEDS_TEAM_CARRIES`
guard is live.

Out of scope but worth passing on: `share_floor_binds` was **756** on this game,
so A1's per-category share floor binds often, and the two teams' realised
category shares are driven by a halflife-2 EWMA over a short recent history
(PIT `te` 0.059 against a league 0.0025). Conservation is unaffected.

---

## 7. Receiving bit-identity, on a real A1 budget

WS02 used a synthetic integer budget because a real one "requires the full
`run_forecast` capture chain". It does not: `team_volume_v1.forecast` →
`scramble_coherence.couple` → `rushing_a1.allocate` produces one. Means ATL
25.135, PIT 21.825 against SC1-coupled team carries 29.525 / 28.140. (Scrambles
were resampled from the historical per-team-game distribution because the QB
layer does need the capture chain — declared, and irrelevant, since both arms
get the identical budget.)

Arms differ **only** in that arm PRE has `mass_pool_partition` overwritten with
`mass_pool` in memory. No file was touched.

| draw array | POST sha256₁₆ | PRE sha256₁₆ | cells differing | result |
|---|---|---|---|---|
| `targets` | c5fc4712c73784f3 | c5fc4712c73784f3 | 0 / 9,400 | IDENTICAL |
| `receptions` | f1a310ed8aff7d9e | f1a310ed8aff7d9e | 0 / 9,400 | IDENTICAL |
| `receiving_yards` | 70fddedae9fcd510 | 70fddedae9fcd510 | 0 / 9,400 | IDENTICAL |
| `receiving_td` | dc3e73fa8cff0e42 | dc3e73fa8cff0e42 | 0 / 9,400 | IDENTICAL |
| `carries` | 4fd3134965dd1c41 | b992b9480d958ea4 | 1,639 / 2,200 | CHANGED, ×1.224798 |
| `rush_td` | dcae3df7d1175b05 | 49a80e9742123c3d | 148 / 2,200 | CHANGED |

`allocation.share` (8f0542c5a06ffff9), `allocation.other` (d3d1e40eb9a9dc86),
`allocation.counts`, `allocation.starts` and all ten `team_draws` arrays are
identical. Of 47 player records, 11 differ and only in `metrics`; those 11 are
the running backs. Layer states are identical in both arms.
`rushing_conversion` returns `DEFERRED[RUSHING_CONVERSION_CONTROL_UNDEFINED]` —
there is no rushing-yards array for carries to move.

**Correction to WS02 item 10.** It attributes the gap between the observed
1.2248 and the algebraic `(1 − 0.010774)/(1 − 0.198875) = 1.234797` to
"degenerate groups and per-draw pool resampling". Degenerate groups **cannot**
contribute: they set `S = 0` in *both* arms, so they cancel out of the ratio
exactly. The resample alone accounts for all of it — a matched-index resample of
shape (2, 200) from the two fitted pools, 2,000 replicates, gives
**1.234925 ± 0.008517, 95% [1.219030, 1.252441]**, which contains 1.224798.

That both the observed ratio and the algebraic prediction reproduce WS02 to four
decimals *on a different budget* is itself the direct proof of budget-scale
invariance.

---

## 8. Q9 frozen identity

`candidate.identity_sha256(candidate.identity(2024))` recomputed at HEAD:

    82c8b52699bbeb00e656a3d543f995bac7034e9a89ff2a8d783e27b6fdc8422e

matching the sealed `dryrun/2024_01_ARI_BUF/ARI/SEALED_FORECAST.json`.
`module_source_sha16` matches `WAVE0_BASELINE.json` exactly —
`nfl.research.q9.hurdle` bb51133641338547, `nfl.research.q9b.family`
5b411b4f00e28e6f, `nfl.research.q9b.production_parity` 1f320b1ee3170e64,
`nfl.production.nonqb.layers` 481f005f682cd721. Freeze file sha16 recomputed
`a28e8832430b1420`. `layers.py` source sha16 recomputed independently
`481f005f682cd721`, and it contains neither `budget_is_partition` nor
`mass_pool_partition`. Placing the selection in `football_engine.py` is what
buys this, and it holds.

---

## 9. Zero-completion — the C1 evidence does not inherit WS-F's leak

`c1_eval` scores the P4C panel directly and never touches
`same_day_retrospective.py`. Its fold filter reads only pregame quantities:
`f_n_prior >= 1`, a fitted point forecast, appearance-model membership, and
volume-store membership. Nothing conditions on the outcome.

| season | rows scored | realised zeros | dropped for a zero outcome |
|---|---|---|---|
| 2022 | 2,365 | 1,061 (44.86%) | **0** |
| 2023 | 2,255 | 972 (43.10%) | **0** |
| 2024 | 2,166 | 880 (40.63%) | **0** |

That already satisfies `postgame.py:762` ("A MISSING PLAYER IS A ZERO") for this
frame. **No patch is being handed to WS-F or WS-G.** Nearly half this frame is
zeros, which is also why the coverage reading above is constrained.

---

## 10. The test that cannot catch any of this

`test_c1_denominator._pools()` returns `np.full(400, 0.1989)` and
`np.full(400, 0.0088)` — fabricated constants, so no fitted value is ever read.

Demonstrated rather than argued: substituting the **real** fitted pools
(0.198875 / 0.010774) into the module and re-running `test_a` leaves all three
checks passing, the only visible change being the printed detail `22.6x`
becoming `18.5x`.

The three checks are (1) an assertion about an array the function just built,
(2) `abs(0.1989 - 0.1918) < 0.01`, which compares two literals and reads no code
at all, and (3) a `ratio > 10` threshold that 18.46 and 22.7 both clear. So
`test_a` pins a partition value the code does not produce and is structurally
unable to notice.

`run_suite.py --only test_c1_denominator` at HEAD: modules 1, test functions 7,
checks 25, **FAILING CHECKS 0, SUITE PASS** — and that green says nothing about
either number it was written to guard. `test_b` and `test_f` are source greps
that do genuine work, `test_c` performs a live Q9 recomputation, `test_e` reads
the class declarations. There is no `test_d`.

---

## 11. Stale paperwork, and a fourth carrier WS02 missed

Pre-registration §8 states that OWN-5's second defect — "`other` is fitted as a
share and consumed against an unnormalised weight sum" — "is REAL and is **not**
addressed by C1". **It is not real at HEAD.** OWN-6/7 fixed it:
`p4c_lib.allocate` computes `S = W·A·(1 − w_other)/Σ(W·A)` with
`other = w_other`, documented in place at `p4c_lib.py:108-125`.

WS02 names three carriers of the stale sentence
(`own5/audit_rush_ownership.py:144`, `own5_rush_ownership.json`,
`denominator.py:233`). There is a **fourth**, and it is the one closest to the
code: `p4c_lib.allocate`'s own docstring at **`p4c_lib.py:101`** still states the
superseded formula

    simplex   : S_i = w_i A_i / (sum_g w A + w_other)

four lines above the comment explaining that that formula was replaced.

---

## 12. Everything else confirmed, briefly

* **`alpha0` is not swapped with the pool** (WS02 4c) — VALID.
  `p4c_build.py:197` fits it with the team mass through `scale = (1 − mo)/ΣC`;
  the engine leaves it at 6.664756. But the latency is **more remote** than WS02
  says: `gen_weights` reads `alpha0` only on `D_dir`, and
  `layers.targets_carries` hardcodes the string literal `'C'` — so reaching it
  requires editing `layers.py`, which the Q9 freeze hashes. Worth fixing; not one
  flag away.
* **`rz_carries` is latent** — VALID, and worse than stated. `mass_mean`
  0.213614 against `mass_pool_partition` 0.009634, a **22.17×** gap, larger than
  the carries gap that was the defect. Its partition pool is also **68
  team-games shorter** than its base pool (`n_team_games_no_position_mass` = 68,
  against 0 for carries), so a future consumer would compare pools of different
  length with nothing saying so. Confirmed unconsumed: `slate_fits` instantiates
  only `targets` and `carries`.
* **`targets` has a 1.227× version of the same gap** — VALID, benign. The swap is
  gated on `rushing_budget is not None` inside the carries block; the targets
  call passes its parameters untouched and runs first.
* **A1's `rb` share is fit on the evaluation seasons** — VALID.
  `seasons_used = [2020…2025]`. Not a P4C parameter so not a literal breach of
  §4, held identical across arms so it cannot flip the comparison — and still
  unstated in any committed artifact. It is equally present in my corrected
  evaluation, which uses the same share.
* **Chronology** — VALID. Pre-registration, estimator, harness, result and test
  are one commit (`57d38ad`). Cited-hash integrity verified; ordering is not
  provable here.
* **Correction to the WS-H brief.** C1 shipped in **`57d38ad`**, not `3f5fc82`.
  `3f5fc82` ships the slate audit and `denominator.py` — the *measurement*, and
  the source of the 0.008754 / 22.7× figures.

---

## 13. The honest statement of the result

> C1 corrects a real denominator mismatch. It raises the modelled running backs'
> share of the budget they are dealt by a factor of **1.230** (1.222–1.235 by
> season, invariant to the budget level to six decimals), and on a
> correctly-scaled oracled budget it improves pooled carry CRPS by **0.182997**,
> team-game clustered 95% **[−0.195603, −0.170441]** over **1,630 clusters**, in
> the same direction in all three evaluation seasons with every per-season
> interval excluding zero. The applied `other` mass is **0.010774** against a
> fitted **0.198875**, an **18.46×** overstatement. Receiving is bit-identical
> and the frozen Q9 candidate identity is unchanged.
>
> The result is **EXPLORATORY**: the defect was found by inspecting the data the
> evaluation then scored. No equivalence margin and no TOST were predeclared, so
> nothing here supports a claim that any quantity is unbiased, stable, closed or
> correct.

**Do not quote:** bias −1.6245 → −0.8094; MAE 3.0939 → 2.7981; CRPS 2.1710 →
1.8491 as levels; pooled CRPS −0.322 [−0.336, −0.309]; coverage 0.5588/0.7305/
0.8058 → 0.6317/0.8202/0.8864.

---

## 14. Evidence ceilings

* Chronology is not provable from this repository.
* The "unmodelled running back" population is a proxy (`f_n_prior >= 1` is not
  the production depth chart), as §8 already declares. The *comparison* is
  unaffected; the *level* 0.010774 is only as good as the proxy.
* The corrected budget is still **oracled**. It isolates the allocation layer,
  which is the layer under test. These numbers are not comparable with `run_p4c`
  or with any live forecast.
* The bootstrap resamples team-games only. Monte Carlo error from the 400 draws,
  the appearance draws and the single `W` realisation sits inside the point
  estimate, not inside the interval.
* Only `test_c1_denominator` was run.
* `football_engine.py` was **dirty** during this work (WS-B, 328 insertions). The
  C1 block at `HEAD:509-558` is untouched by that diff — verified with
  `git diff` — but the A/B ran against the working-tree module, not HEAD.
* No 2026 outcome was consulted. No market data was opened at any point.
