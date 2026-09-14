# WS02 — independent verification of the C1 denominator repair

**CODE CHANGED: NO.** No file outside `nfl/research/parallel_pass/ws02/` was
written. `nfl/research/slate_audit/C1_EVALUATION.json` was hashed before and
after every step and is byte-identical (`a79772b4cc3c1e37…`); the evaluation was
re-run through `c1_eval.run()` from a scratchpad driver so its `main()` could not
overwrite the committed artifact. The only suite run was
`run_suite.py --only test_c1_denominator` (25 checks, 0 failing).

Adversarial brief: falsify, not confirm. The repair's **mechanism and direction
survive every test I could construct**. Three of its **registered numbers do
not**, and the harness that produced its headline result carries a units error
of exactly the class C1 exists to fix.

---

## Verdict table

| # | Item | Verdict |
|---|---|---|
| 1 | Pre-registration identity | **CONFIRMED** (with a chronology ceiling) |
| 2 | Exact FITTED denominator | **CONFIRMED** |
| 3 | Exact PRODUCTION denominator | **CONFIRMED** |
| 4 | Units at each boundary | **PARTIAL** — allocator correct; two stale claims; one live trap |
| 5 | Historical non-RB mass | **PARTIAL** — magnitude right, registered figure off-population |
| 6 | Applied RB-denominator mass | **CONFIRMED, VALUE CORRECTED** — 0.010774, not 0.0088 |
| 7 | Walk-forward CRPS / bias / MAE / coverage | **PARTIAL** — reproduces bit-identically, but the budget is mis-scaled |
| 8 | Clustered bootstrap | **CONFIRMED** |
| 9 | Per-season direction consistency | **CONFIRMED** |
| 10 | Replay blast radius | **CONFIRMED** (measured, not argued) |
| 11 | Receiving bit-identity | **CONFIRMED** (bit-identical, not "within noise") |
| 12 | Q9 frozen identity | **CONFIRMED** |

---

## 1. Pre-registration identity — CONFIRMED

`sha256(nfl/research/slate_audit/predeclaration_c1_denominator.md)` =
`9d0443e1bd777d31371d2f7073c4e8acf2be9afcc6b4730471957b225e83e9a0`, recomputed
here. It is cited in three places and all three agree:
`C1_EVALUATION.json:4`, `c1_eval.py:64`, `test_c1_denominator.py:45`.

**Ceiling, not a falsification.** The pre-registration, the estimator
(`p4c_build`), the harness (`c1_eval.py`), the result (`C1_EVALUATION.json`) and
the test all arrive in **one commit, `57d38ad`**. The document's own claim —
"written … **before** any line of the repair is written" — is therefore
*unverifiable from this repository*. Nothing contradicts it; nothing in the tree
can support it either. A pre-registration committed on its own, before the
estimator, would have been checkable.

## 2. Exact fitted denominator — CONFIRMED

`p4c_build.py:157`:

    pool = np.array([max(0.0, min(0.95, mall[k] - ms[k])) for k in mall], ...)

`mall[k]` accumulates `r['s_carries']` over **every** row regardless of position;
`ms[k]` only over `position in ('RB',)` **and** `f_n_prior >= 1`.

The pre-registration asserts `mall[k] == 1.0` "because the panel closes". I did
not take that on trust. Over all 2,718 pre-2026 team-games (2020 excluded per
`MASS_POOL_EXCLUDE_SEASONS`): **mean 1.00000000, min 1.000000, max 1.000000,
zero team-games deviating by more than 1e-6.** The claim holds exactly.

So the fitted quantity is `1 − (modelled RBs' share of TEAM carries)`.
Recomputed independently from `panel_enriched.pkl`: **0.198875**, matching
`own5_rush_ownership.json` and the production parameter object to six decimals.

## 3. Exact production denominator — CONFIRMED

`run_forecast.py:755`:

    rushing_budget = {t: a1.value['carries'][(t, 'rb')] for t in teams ...}

`rushing_a1.CATEGORIES` = kneel, designed_qb, rb, wr, te, fringe, and
`assert_frame_closes` enforces `team_carries − scramble == sum(categories)` in
the data. Read from the frozen parameters, the league shares over that budget
are:

| category | share |
|---|---|
| rb | 0.860235 |
| designed_qb | 0.068808 |
| wr | 0.036027 |
| kneel | 0.028758 |
| te | 0.002514 |
| fringe | 0.003658 |
| **sum** | **1.000000** |

So the budget handed to the allocator has kneel, designed_qb, wr, te and fringe
already removed, while the mass fitted against it is the residual on the whole
team. The double subtraction is real. `football_engine.py:535-556` swaps
`mass_pool_partition` in when and only when `rushing_budget is not None` — the
same variable that selects the multiplier at line 571, so the two cannot drift.

I verified the refusal paths **live**, not by grepping source as the committed
test does. With an A1 budget supplied and `mass_pool_partition` deleted the
engine halts at `carries` with `P4C_PARTITION_POOL_MISSING` and returns
`payload is None` — nothing is published. An empty (`size 0`) pool halts the same
way. It never falls back to the team pool.

**Non-A1 path behaves correctly.** With `rushing_budget=None` the engine reports
`carry_other_denominator = NOT_APPLICABLE[D1_TEAM_CARRIES_POOL]` alongside
`rushing_budget_owner = NOT_APPLICABLE[D1_TEAM_CARRIES]` and runs to completion.
Team pool with team budget is the correct pairing.

## 4. Units at each boundary — PARTIAL

**The allocator is share-correct, and OWN-6/7's fix is still right.**
`p4c_lib.allocate` (simplex) computes `S = W·A·(1 − w_other)/Σ(W·A)`,
`other = w_other`. Direct numerical test: group sums of `S` land exactly on
`1 − w_other` (0.800000 and 0.990000 for w = 0.20 / 0.01), `Σ S + other − 1` has
max deviation 1.19e-07 (float32 epsilon), and `S` stays proportional to `W·A`
within group to the same tolerance. Production reaches this identical function —
`layers.targets_carries` imports `p4c_lib` and calls `L.allocate`. Because the
allocator renormalises, the *scale* of `W` (and therefore of the point forecast
`C`) cancels, so `C`'s denominator is not a units risk. Both pools are shares on
their own denominators: `mall − ms` is a share because `mall ≡ 1`, and
`(mpos − ms)/mpos` is explicitly normalised.

**Stale claim (a).** `predeclaration_c1_denominator.md` §8 states that the OWN-5
second defect — "`other` is fitted as a share and consumed against an
unnormalised weight sum" — "is REAL and is **not** addressed by C1". As of HEAD
it is **not real**: OWN-6/7 fixed it and `p4c_lib.py:108-125` documents the fix
in place. The source of the stale claim is a hardcoded literal in
`nfl/research/own5/audit_rush_ownership.py:141-145` (`out['consumption'] = …
"other = w_other / (sum(W*A) + w_other)"`), which `own5_rush_ownership.json`
faithfully reproduced on 2026-09-14 and which `slate_audit/denominator.py:222`
then surfaces as `second_and_separate_defect`. Three artifacts repeating one
un-updated string.

**Stale claim (b).** The same OWN-5 `construction` string is still correct.

**Live trap (c) — `alpha0` was not carried across the swap.** `p4c_build.py:197`
fits the Dirichlet concentration using `mo = par['mass_mean']`, i.e. the **team**
mass 0.198875, through `scale = (1 − mo)/Σ C`. The engine swaps `mass_pool` and
`mass_mean` but leaves `alpha0` at 6.664756 — a value whose contract is the
0.199 mass. This is **harmless today**: production runs system `'C'`
(`W = C + resample(add_pool)`), and `gen_weights` only reads `alpha0` on the
`D_dir` branch. It becomes wrong the moment any Dirichlet system is selected for
carries. Nothing in the repair or its test notices this.

**Live trap (d) — the harness repeats the defect.** See item 7.

## 5. Historical non-RB mass — PARTIAL

The pbp files (`pbp_2021…pbp_2024`, 19 MB each) **carry no position column on a
rush row** — `denominator.py:118-120` says so explicitly and routes the
positional split to the panel. So a purely pbp recomputation of "non-RB mass" is
not available; what pbp supports is the QB/non-QB split. I recomputed on the
panel that actually carries position, and cross-read the pbp-derived split from
the OWN-5 artifact.

| population | RB | QB | WR | TE | **non-RB** | n team-games |
|---|---|---|---|---|---|---|
| panel, 2021–2025, 2020 excluded (**matches the fit**) | 0.809827 | 0.155309 | 0.029964 | 0.003983 | **0.190173** | 2,718 |
| panel, 2021–2024 only (**matches the pbp window**) | 0.808941 | 0.155425 | — | — | **0.191059** | 2,174 |
| OWN-5 as registered (panel_p3, **2020 included**) | 0.8082 | 0.1568 | 0.0302 | 0.0038 | **0.1918** | 3,230 |

The registered 0.1918 is the **2020-inclusive** figure. The fitted 0.198875
**excludes 2020**. The two terms in the identification argument are drawn from
different populations.

**The claim "those two agreeing to three decimals is the identification"
(`predeclaration…md` §1, repeated at `denominator.py:17` and in the commit
message) is FALSE.** 0.198875 against 0.1918 differ by **0.00707** — agreement
to one decimal place, not three. On the matched population it is 0.198875
against 0.190173, a gap of 0.00870.

**The argument still holds, by a route the prose does not take.** That gap *is*
the unmodelled-RB mass: 0.010773 × 0.809827 = 0.008724, which closes the
decomposition to five decimals. So the fitted quantity is confirmed as a
team-denominator residual — but by an exact accounting identity, not by a
coincidence of decimals that does not exist.

## 6. Applied RB-denominator mass — CONFIRMED, VALUE CORRECTED

Read from the production parameter object, `p4c_params.params(cls, 2026)`:

| class | `mass_pool` | `mass_pool_partition` | ratio | pool n | dropped |
|---|---|---|---|---|---|
| carries | 0.198875 | **0.010774** | **18.46x** | 2,718 | 0 |
| targets | 0.011282 | 0.009194 | 1.23x | 2,718 | 0 |

Reproduced independently from the panel: 0.010774 (ratio-of-means 0.010773,
mean-of-ratios 0.010792 — the estimator choice is worth ~0.00002).

**The registered 0.008754 and "22.7x" are not reproducible.** They come from
`denominator.py:190`, which computes `(rb_all − (1 − fitted))/rb_all` using
OWN-5's **2020-inclusive** `rb_all = 0.8082` against a **2020-exclusive**
`fitted = 0.198875`. On the matched panel the same formula gives 0.010746. The
population mismatch of item 5, propagated.

So: **the code is right and the paperwork is wrong.** The applied mass is 0.0108
and the overstatement is 18.5x. `predeclaration_c1_denominator.md` §1,
`denominator.py`'s docstring, the `p4c_build.py:174` comment, the
`football_engine.py:525` comment, the commit message and the task brief all
carry 0.0088 / 22.7x.

**The committed test cannot catch this.** `test_c1_denominator._pools()` returns
`np.full(400, 0.1989)` and `np.full(400, 0.0088)` — **hardcoded synthetic
constants**. `test_a` therefore asserts 0.1989 ≈ 0.1989 against an array it just
built, never opens the fitted parameters, and pins a partition value the code
does not produce. Its third check (`ratio > 10`) would pass at 18.5x too, so the
suite is green either way.

**Distributional note nobody records.** The partition pool is **exactly zero in
95.33% of training team-games** (baseline pool: broadly spread, median 0.178571).
C1 does not merely shift the `other` mass down; it replaces a diffuse
distribution with a spike-at-zero plus a thin right tail. In most draws the
modelled backs now take the entire A1 `rb` budget and the `other` container is
empty. The 0.95 clip binds on 1 team-game in the partition pool and 2 in the
baseline pool.

## 7. Walk-forward evaluation — PARTIAL (reproduces exactly; measures the wrong level)

**Reproduction: exact.** `c1_eval.run()` re-run at HEAD produces a JSON
**byte-identical** to the committed `C1_EVALUATION.json`
(`a79772b4cc3c1e376a31590151d149e077421da7fecb7f18466dff70df3f9324` both ways).
Pooled CRPS 2.171036 → 1.849061 (brief: 2.1710 → 1.8491 ✓), bias −1.624487 →
−0.809350 (brief: −1.6245 → −0.8094 ✓), MAE 3.093877 → 2.798075, coverage
0.5588/0.7305/0.8058 → 0.6317/0.8202/0.8864, closure max dev 2.38e-07 in all six
arm-seasons.

**FALSIFICATION — the oracled budget is not on the level it is declared to be
on.** `C1_EVALUATION.json` declares `"team_volume": "ORACLED at the realised
team level"`, and `c1_eval.py:216` says "`y` is per player, so the team level is
its group sum". It is not. `te` is filtered to `f_n_prior >= 1`, so the group sum
is the realised **modelled-RB** carry level, not the team carry level. Line 222
then multiplies it by `rb_share = 0.860235` — A1's share of
`team_carries − scrambles`. **A team→RB conversion factor is applied to a
quantity already on the RB scale.** That is the same units error C1 exists to
fix, one layer up.

Measured per team-game:

| | 2022 | 2023 | 2024 |
|---|---|---|---|
| modelled-RB carries (what `team_lvl` is) | 21.570 | 21.408 | 21.596 |
| all-RB carries | 21.838 | 21.575 | 21.756 |
| team carries | 27.251 | 26.849 | 26.998 |
| a true A1 `rb` budget = (team − scrambles) × 0.860235 | 22.006 | 21.460 | 21.545 |
| **the budget `c1_eval` actually hands both arms** | **18.555** | **18.416** | **18.577** |
| shortfall | −15.7% | −14.2% | −13.8% |

The mechanism reproduces the reported biases from arithmetic alone:

| arm | implied bias on the eval budget | **reported** | implied on a true A1 `rb` budget |
|---|---|---|---|
| BASELINE 2022 | −1.5028 | −1.5259 | −0.8630 |
| C1 2022 | −0.7377 | −0.7667 | **+0.0444** |
| BASELINE 2023 | −1.6011 | −1.6321 | −1.0121 |
| C1 2023 | −0.7748 | −0.8120 | **−0.0492** |
| BASELINE 2024 | −1.6857 | −1.7243 | −1.0884 |
| C1 2024 | −0.8067 | −0.8532 | **−0.0690** |

(residual ≈0.03 is the degenerate groups and the per-draw pool resample.)

**What this does and does not overturn.**

- It does **not** overturn the comparison. Both arms are scaled by the same
  budget, and the ratio of their projections is exactly
  `(1 − w_C1)/(1 − w_base)`, independent of budget scale. C1 still wins, in
  every season, by the same relative margin.
- It **does** invalidate every absolute number the artifact reports. Bias, MAE,
  CRPS, `mean_projected`, cov50/80/90 and PIT are all measured against a budget
  ~15% short. "bias −1.6245 → −0.8094" is not the bias of either arm; on a
  correctly-scaled budget it is roughly −0.99 → −0.02.
- It **does** hollow out acceptance criterion 4, "bias moves toward zero **and
  does not overshoot into over-projection**". The non-overshoot half is checked
  against a reference level that is systematically low. It still passes on a
  corrected budget (C1 lands at +0.04/−0.05/−0.07, and the residual sign is
  mixed), but that is luck, not measurement. The one criterion written to catch
  a correction that goes too far is the one the harness cannot see.
- Ironically the corrected picture is **better** for C1, not worse: on a budget
  equal to realised all-RB carries (21.838 in 2022) with `w_other = 0.011003`,
  the modelled block covers 21.598 against 21.570 realised — near-exact. That is
  independent corroboration that 0.0108 is the right residual.

**Second, smaller harness issue: the budget scale is fit on the evaluation
seasons.** `c1_eval.a1_rb_share()` calls `rushing_a1.params(2026, 1)`, whose
`seasons_used` is `[2020, 2021, 2022, 2023, 2024, 2025]` — it includes all three
evaluation seasons. §4 of the pre-registration constrains "every **P4C**
parameter", and A1's share is not a P4C parameter, so this is not a literal
breach. It is held identical across arms so it cannot flip the comparison. But a
2026-fit quantity is shaping the 2022 budget, and no artifact says so.

## 8. Clustered bootstrap — CONFIRMED

- **Unit is team-game.** `row_cluster = f"{r['team']}_{r['ord']}"`, and `ord` is
  `season*100 + week` (verified on the panel: 202001 … 202518, **zero** `ord`
  values shared across seasons). So the pooled bootstrap cannot merge a 2022
  team-game with a 2023 one. Cross-check: per-season clusters 542 + 544 + 544 =
  1,630 = the pooled `n_clusters`.
- **Counts reported everywhere.** All four bootstrap blocks carry
  `n_clusters`; `block_boot` returns `None` below 5 clusters rather than a thin
  interval.
- `block_boot` resamples clusters with replacement and forms the ratio of sums
  `(Σa − Σb)/Σn` — correct for unequal cluster sizes.
- Arms are **paired**: same `W`, same appearance draws, and the same
  `default_rng(SEED+5000)` index array into two pools of equal length (`dropped
  = 0` in all three seasons), so index *i* is the same historical team-game in
  both arms. That is the tightest pairing available and it makes the intervals
  narrow legitimately.
- **Limitation the artifact does not state:** the bootstrap resamples team-games
  only. Monte Carlo error from the 400 draws, from the appearance draws and from
  the single `W` realisation is inside the point estimate, not inside the
  interval. The intervals are conditional on one draw realisation.

## 9. Per-season direction — CONFIRMED

CRPS difference (C1 − BASELINE): 2022 **−0.307656** [−0.32942, −0.28448],
2023 **−0.324874** [−0.34903, −0.30484], 2024 **−0.334592** [−0.36021,
−0.30462]. Three of three negative, three of three intervals excluding zero,
monotone in season. Bias, MAE and all three coverage levels move the same way in
all three seasons. Nothing inconsistent.

## 10. Replay blast radius — CONFIRMED, measured

Engine A/B on a real game (`2026_01_ATL_PIT`, `FE.slate_fits(2026,1)`, m=200,
seed=20260908, an identical fixed `rushing_budget` in both arms). The **only**
difference between arms: in arm PRE, `mass_pool_partition` is overwritten with
`mass_pool` in memory, reproducing pre-repair behaviour. No file was touched.

| payload draw array | result |
|---|---|
| `carries` | **CHANGED** — mean 1.1276 → 1.3810 (×1.2248) |
| `rush_td` | **CHANGED** — mean 0.0327 → 0.0405 |
| `targets` | IDENTICAL |
| `receptions` | IDENTICAL |
| `receiving_yards` | IDENTICAL |
| `receiving_td` | IDENTICAL |

Record metrics: `carries` changed on 11 rows, `rushing_td` on 8 (3 of 11 RBs
coincide). `appearance`, `participation`, `targets`, `receptions`,
`receiving_yards`, `receiving_td` identical on all 47 rows.
`allocation.share`, `allocation.other` and `team_target_volume` bit-identical.

`rushing_yards` is identical on all 11 RBs — **not a bug**:
`layers.rushing_conversion` returns DEFERRED by design ("NO GOVERNED CONTROL
EXISTS"), so there is no yardage array for carries to move. A rebuilt board's
rushing-yard column is unchanged because it does not exist, not because the
change failed to propagate. Any future rushing-yards layer inherits the full
×1.22 shift.

Observed ratio 1.2248 against the algebraic prediction
`(1 − 0.010774)/(1 − 0.198875) = 1.2347`; the gap is degenerate groups and
per-draw pool resampling, both expected.

Two guards fired during setup and are worth recording as working: a budget drawn
from `integers(16,30)` was refused with "97 cell(s) where the A1 running-back
budget is above the D1 team-carry level it is a partition of", and
`integers(8,16)` with 1 such cell. The partition-cannot-exceed check is live.

## 11. Receiving bit-identity — CONFIRMED

Proven two ways.

*By construction:* the targets call at `football_engine.py:397` passes
`fits['p4c_params_targets'].value` untouched and executes **before** the carries
block; the C1 branch mutates a `dict(...)` **copy** of the carries parameters
only; every layer builds its own `default_rng` from a declared seed tuple
(`layers.py:326`, `_row_rng`), so no shared mutable stream can be perturbed;
`receiving_conversion(tc, T, …)` and `td_layer(cv, T, …)` take no carries input;
`joint_reconciliation` only *checks* cross-layer consistency and rescales
nothing.

*By measurement:* the item-10 A/B gives `np.array_equal == True` on `targets`,
`receptions`, `receiving_yards`, `receiving_td`, `allocation.share`,
`allocation.other` and `team_target_volume`. That is **bit-identical**, which is
the standard §2 of the pre-registration demands — stronger than the "within
Monte Carlo noise" that §6 settles for.

## 12. Q9 frozen identity — CONFIRMED

`candidate.identity_sha256(candidate.identity(season))` recomputed at HEAD:

    82c8b52699bbeb00e656a3d543f995bac7034e9a89ff2a8d783e27b6fdc8422e

matching both the sealed
`dryrun/2024_01_ARI_BUF/ARI/SEALED_FORECAST.json:candidate.identity_sha256` and
the target in the brief. The design decision that protects it is real: Q9 hashes
`nfl.production.nonqb.layers` source, and the repair deliberately lives in
`football_engine.py` instead of adding an argument to `layers.targets_carries`.
`layers.py` contains neither `budget_is_partition` nor `mass_pool_partition`.

---

## What the repair may have missed

1. **`rz_carries` has the identical class declaration** — `den='team_rz_carries'`,
   `pos=('RB',)`, `mode='simplex'` — and `p4c_build` now fits it a
   `mass_pool_partition` too. **It is not a live defect**: `rz_carries` is not
   consumed anywhere in `nfl/production/`; the engine instantiates only
   `p4c_params_targets` and `p4c_params_carries` and calls `targets_carries`
   only for `'targets'` and `'carries'`. It is latent: the moment a red-zone
   carry budget is wired from A1 (or any partition), the same seam opens, and
   nothing in the repair, the test or the pre-registration would notice.
2. **`targets` has a 1.23x version of the same gap** (`mass_pool` 0.011282 vs
   `mass_pool_partition` 0.009194) — 0.2% of team targets go to positions
   outside WR/TE/RB. Currently benign: under C3 the budget is *targeted throws*,
   which is the full denominator, and under D1 it is `team_targets`. Latent if a
   target budget is ever narrowed positionally.
3. **`alpha0` is not swapped with the pool** (item 4c). Unreachable today, wrong
   the moment a `D_*` system is selected for carries.
4. **The committed test is structurally unable to detect items 5 and 6.**
   `_pools()` fabricates its inputs, so no fitted value is ever read; the
   hardcoded 0.0088 is not what the code produces (0.010774) and the test passes
   anyway. Two source-string greps (`test_b`, `test_f`) do genuine work; one
   live-behaviour check (`test_c`, Q9) does; `test_a` does not. There is no
   `test_d`.
5. **`c1_eval`'s budget construction** (item 7) — the largest finding, and the
   one that changes what the artifact may be quoted for.
6. **The 95.3%-zero shape of the partition pool** (item 6) is undocumented, and
   it is the actual driver of the coverage change.

## Evidence ceiling

- **Chronology is not provable here.** Pre-registration, estimator, harness,
  result and test are one commit. Cited-hash integrity is verified; ordering is
  not.
- **`pbp_202[1-4].*.csv.gz` cannot yield a positional split** — no position
  column on a rush row. The non-RB mass is necessarily a panel measurement. My
  recomputation and OWN-5's share `panel_p3.csv.gz` and so are not fully
  independent of each other; they differ only in season window, which is the
  discrepancy item 5 identifies.
- **The "unmodelled RB" population is a proxy**, as §8 of the pre-registration
  already declares: `f_n_prior >= 1` is not the production depth-chart pool. The
  partition mass inherits that proxy exactly as the baseline mass does, so the
  *comparison* is unaffected; the *level* 0.010774 is only as good as the proxy.
- **The item-10/11 A/B used a synthetic `rushing_budget`** (a fixed integer draw
  in a feasible range), not a real A1 output, because supplying a real A1 budget
  requires the full `run_forecast` capture chain. Since both arms received the
  identical budget and the budget enters only as a multiplier, this affects the
  observed *magnitude* (1.1276 → 1.3810) but not the *set* of arrays that move,
  which is the claim under test.
- **No 2026 outcome was consulted; no market data was opened at any point.**
- **Only `test_c1_denominator` was run.** Whether the repair breaks any other
  suite is out of scope for this workstream and unverified here.

## Bottom line

The defect is real, the diagnosis is right, the mechanism is right, the
implementation is right, the scope discipline is exemplary (receiving is
bit-identical, Q9 is untouched, the non-A1 path is preserved, the missing-pool
case refuses instead of falling back), and the direction of the result is robust.

Three registered numbers are wrong and propagate through six artifacts
(**0.008754 → 0.010774**, **22.7x → 18.46x**, **"agree to three decimals" →
they differ by 0.0071**), all traceable to one population mismatch: the fitted
mass excludes 2020 and the panel share it is compared against includes it.

And the walk-forward artifact's absolute numbers — the ones the brief quotes —
are measured against a budget that is 14–16% below the level it is declared to
be. The comparison survives; the magnitudes do not. The honest statement of the
result is *"C1 raises the modelled backs' share of their budget by a factor of
1.22 and improves pooled CRPS by 0.322 with a team-game clustered interval of
[−0.336, −0.309]"* — not *"bias improves from −1.62 to −0.81"*.
