# RBDEP — RB1 <-> RB2 opportunity dependence

**2026-09-09.** Authorised under owner ruling B11. Pre-registration
`predeclaration_rbdep.md`, sha256 `f922f2c3…96697ee5`, pinned in
`run_rbdep.py` and reverified at run time. **EXPLORATORY.** Nothing promoted;
no default changed. `NFL-1` untouched. No 2026 outcome read — the guard that
would refuse one is `rbdep_lib.assert_no_future_season` and it has a
bypass test.

---

## What was asked

Run the minimal ablation identified in B11 — share ONE `add_pool` resample
index across the players of a team-game instead of resampling independently per
player — measure first, pre-register before scoring, and stop when the sign is
no longer materially wrong with closure exact and marginals intact.

## The headline, in one paragraph

**The minimal ablation does not fix the sign, and on the frame where the sign
is at risk it makes it worse.** It also turns out that the sign was never wrong
on the historical evaluation frame at all: `+0.081` and `-0.329` are **not the
same statistic**, and the model half of that pair was measured on the 2026
week-1 rehearsal rather than on history. Both halves reproduce exactly, so
neither number is wrong — the comparison between them is.

---

## 1. Reproduction, before anything was changed

`run_rbdep_baseline.py` -> `rbdep_baseline.json`.

| B11 quotes | what the number actually is | reproduced |
|---|---|---|
| `+0.081` | mean over team-games of corr **ACROSS DRAWS WITHIN one team-game**, 2026 week-1 rehearsal payload, 32 team-games | **+0.0809** |
| `-0.179` | the same, on shares | **-0.1792** |
| `+0.113`, `P(r>0)=0.68` | **BETWEEN** team-game, one draw each, same 32 team-games | **+0.1132**, `0.680` |
| `-0.329` | **BETWEEN** team-game corr of REALISED carries, historical | **-0.3330** |
| `28.7%` | team-volume share of RB1 carry variance | **28.1%** |

The three model-side figures land on B11's to the fourth decimal. The two
computed from history land within `0.004` and `0.6pp` respectively, which is a
difference in the eligible team-game set and not in the quantity. The harness
is sound.

**The first two rows are a different estimand from the fourth.** Reality
supplies one draw per team-game, so `-0.329` is necessarily a between-team-game
correlation. `+0.081` is a *within*-team-game conditional correlation. Setting
them side by side is the like-for-like defect this project has already caught
six times, appearing in a seventh place. A second break sits underneath it:
B11's model figure ranked RB1/RB2 by **the model's own predicted mean** while
its historical figure ranked by **prior form**.

**Run the same code on the historical evaluation frame and the sign is
correct**, on every statistic:

| statistic, historical frame, 1,662 team-games, ranks from prior weeks | value |
|---|---|
| **LIKE-FOR-LIKE between team-game, counts** — median over 1,000 draws | **-0.3559**, `P(r>0) = 0.000`, band `[-0.389, -0.322]` |
| realised between team-game, counts | **-0.3716** |
| LIKE-FOR-LIKE between team-game, shares | -0.5476 (realised -0.5951) |
| within team-game across draws (NOT comparable) | -0.2391 |
| corr of predictive means (FORBIDDEN) | -0.6170 |
| team-volume variance fraction of RB1 | 0.2772 |

So the allocator's simplex competition is present, correctly signed, and within
0.016 of the realised value on the like-for-like statistic. `gen_weights` is
byte-identical in the two measurements, so **the sign is a property of what is
fed to the allocator, not of the allocator.**

## 2. What differs about the rehearsal

The rehearsal's backs carry almost no role separation: **6.66 RBs per
team-game** (min 5, max 10), and one team-game's seven backs have predicted
means of 4.31, 3.04, 2.97, 2.89, 2.80, 2.50 and 1.21 carries. It is week 1 of a
season, with partial player coverage and no in-season history.
The diagnostic consequence is visible in one number: **the correlation of the
two backs' predictive MEANS across team-games is `+0.3994` in the rehearsal and
`-0.6170` on the historical frame.** When role separation disappears, both
backs' conditional means are driven by the shared team-carry point forecast and
move together, and that swamps the competition.

The same flatness shows in the workload split: the RB1/RB2 predicted-mean ratio
(pooled) is **1.595 in the rehearsal against 2.231 on the historical frame**.

Frame L was pre-declared to traverse exactly that axis. It confirms the
mechanism: as `lambda` falls from 1 to 0 the incumbent's forbidden
predictive-mean correlation runs `-0.617 -> -0.512 -> -0.341 -> -0.095 ->
+0.179`, and the like-for-like dependence follows it up from `-0.356` toward
zero.

**But it does not close the gap, and that must be said plainly.** Frame L at
`lambda = 0` — every back in a team-game given an identical share forecast, the
most extreme flatness the axis allows — reaches only `-0.1479`. The rehearsal
sits at `+0.1132`. So flat share forecasts account for most of the movement
(`-0.356 -> -0.148`, about 71% of the distance to zero) and **at least one
further driver of the rehearsal's positive sign is unidentified.** Candidates
not separated here, because each sits behind a production module outside this
task's write scope: the rehearsal draws team volume from `team_volume_v1` (D1)
rather than the frozen P4B store used here, it carries 6.66 backs per team-game
against 4.4, and its week-1 appearance probabilities come from an injury report
that is not yet filed. Naming them is not measuring them.

## 3. The ablation

`run_rbdep.py` -> `rbdep_results.json`. Two arms one argument apart. INC is the
standing default (`add_pool_groups=None`); SHR passes one group id per
team-game. Same seeds, same `C`, same appearance draws, same team-volume draws,
same allocator, 1,000 draws, evaluation seasons 2022-2025 fitted strictly on
prior seasons.

**Primary metric — like-for-like between-team-game median `r`, 1,662 team-games:**

| lambda | INC | SHR | direction |
|---|---|---|---|
| **1.00 (Frame H)** | **-0.3559** | **-0.3696** | slightly more negative |
| 0.75 | -0.3096 | -0.3185 | slightly more negative |
| 0.50 | -0.2542 | -0.2430 | **toward zero** |
| 0.25 | -0.1981 | **-0.1258** | **toward zero** |
| 0.00 | -0.1479 | **+0.1112** | **through zero, sign now wrong** |

**The incumbent's median `r` is negative at every grid point** (`P(r>0) = 0.000`
in all five), so there is no grid point at which a fix is needed. **The
ablation flips the sign at `lambda = 0`** — `P(r>0) = 0.999`, band
`[+0.049, +0.174]`.

**The mechanism is not subtle.** With `C` flat inside a team-game and one shared
residual, `W` is *identical* for every back in that team-game, so the allocator
splits the budget equally and the two backs' carries become the same number
twice over, less the appearance draw. Sharing the residual removes the only
remaining source of within-team-game differentiation. The nearer the point
forecasts are to flat — which is where the rehearsal sits — the more damage it
does.

Verdict recorded: **`ABLATION_UNNECESSARY_ON_FRAME_H`**, with the Frame L branch
recording `SIGN_NEVER_WRONG_ON_GRID` and, by section 5's tie rule, **the
incumbent winning**.

## 4. Hard gates — counts, every arm, every frame

All ten arm/frame combinations, 8,960 rows x 1,000 draws each:

| gate | INC | SHR |
|---|---|---|
| G1 simplex closure violations (`\|sum S + other - 1\| > 1e-5`) | **0** | **0** |
| G2 team budget partition violations | **0** | **0** |
| G3 negative shares / negative counts | **0 / 0** | **0 / 0** |
| G4 waterfill cap-repair bindings | **0** | **0** |
| G5 weight floor rate, Frame H (reported, not a gate) | 0.1617 | 0.1615 |
| G6 degenerate team-game rate, Frame H | 0.0084 | 0.0146 |

G6 inflates by **1.73x**, in the direction predicted in section 8 of the
pre-registration and below the 3x threshold declared there. Nothing was
clipped, renormalised or repaired to reach any of these numbers.

## 5. Marginal quality, Frame H — before and after

Scored against realised `y_carries` on 8,960 player-games.

| | INC | SHR |
|---|---|---|
| **CRPS** | **2.0206** | **2.0198** (`-0.042%`) |
| MAE | 3.0987 | 3.0118 |
| RMSE | 4.4368 | 4.4263 |
| bias | -0.0060 | +0.0271 |
| r(pred mean, actual) | 0.7593 | 0.7596 |
| mean / sd | 5.227 / 6.913 | 5.194 / 6.956 |
| p05 / p50 / p95 | 0.00 / 2.24 / 19.82 | 0.00 / 2.31 / 20.08 |
| zero-mass `P(N < 0.5)` | 0.4226 | 0.4194 |
| coverage 50 / 80 / 90 / 95 | .701 / .896 / .954 / .981 | .676 / .870 / .928 / .964 |

Realised: mean 5.221, sd 6.805, p05/p50/p95 = 0 / 2 / 19, zero-mass 0.4267.

`-0.042%` on CRPS is inside the pre-declared `0.2%` tie band, so **the arms are
tied on marginals** and the incumbent wins. Both arms over-cover at every
nominal level; that is a pre-existing property of the frozen system C carry
distribution and neither arm creates or repairs it.

## 6. The owner's stopping condition

> *Stop once: the sign is no longer materially wrong; allocation closure remains
> exact; marginal CRPS/distributions do not materially deteriorate.*

* **sign** — on the historical frame it was never materially wrong (`-0.3559`,
  `P(r>0) = 0.000`). The ablation does not fix the rehearsal's sign; it is the
  wrong lever, and at flat priors it drives the statistic positive.
* **closure** — exact, 0 violations, both arms, every frame.
* **marginals** — tied to within `0.042%` CRPS.

**Stopping condition met on closure and marginals; the sign clause is met by
the incumbent and NOT by the ablation.** Per the owner's instruction, no
redesign of P4C follows from this and none was attempted.

## 7. What is still open, and what it is not

`B11` should be **rewritten, not closed.** The defect it names is real but
mislocated, and its evidence line needs correcting in two places: the model
figure must be the like-for-like `+0.1132`, not the within-team-game `+0.081`,
and it must be labelled as a rehearsal measurement rather than set against a
historical one without a label.

The largest identified driver is the **information content of the per-player
share forecast in a week-1 cold start** — 71% of the distance to zero — which
sits in `nfl/production/nonqb/participation_prior.py` and the cold-start
specification, not in `p4c_build`. The remaining 29% is **not identified**, and
this experiment cannot identify it without touching production modules it is
not authorised to write. That is an open measurement, not a conclusion.

Left deliberately undone, because it is outside this task's write scope and
would be a redesign: measuring the rehearsal path directly under both arms, and
separating the three named candidates for the unexplained 29%.
`layers.targets_carries` does not thread `add_pool_groups`, and threading it is
the lead's call. **What this experiment does settle is that threading it would
not help**, and at flat priors would hurt.

**This is exploratory.** The evaluation seasons are the seasons P4B and P4C
were selected on. Nothing here establishes that any variant is better on unseen
games, and a confirmatory result needs games no design decision has touched.

## 8. Tests and the suite

`nfl/tests/test_v1_teammate_dependence.py` — **10 test functions, 59 checks, 0
failing.** Positive tests, seeded-violation tests, and three load-bearing
bypass proofs via `nfl/tests/bypass.py`: the pre-registration hash guard, the
future-season guard, and the hard-gate verdict. One test (section D) encodes
the B11 measurement defect itself as a regression: a synthetic team-game whose
within-team-game and between-team-game correlations carry **opposite signs**,
asserting that the library reports them separately and labels which is
comparable.

Run through the runner rather than directly, so the tally is the runner's:
`python3.12 nfl/tests/run_suite.py --only test_v1_teammate_dependence` →
**modules 1, test functions 10, checks 59, FAILING CHECKS 0, RAISED 0, SUITE
PASS.**

**The full suite is NOT clean, and not because of this work.**
`python3.12 nfl/tests/run_suite.py`: **50 modules, 527 test functions, 3,099
checks, 1 failing check, 1 raised — SUITE FAIL.** Both come from one module,
`nfl/tests/test_v1_composition_fidelity.py`, failing
`COMPOSITION_VERDICT_IS_PASS_ONLY` against `football_engine.py` — another
agent's live work on the QB composition layer (blocker B8), which this task may
not write. An earlier run in the same session also showed a second failure in
the untracked `test_v1_draw_artifact.py`, since repaired by that agent between
runs; the count moved because the tree is being edited concurrently. **The
honest count is 1 failing and 1 raised, not 0**, and neither names
`p4c_build`, `rbdep`, or `test_v1_teammate_dependence`. It is stated rather
than attributed away.

## 9. Files

| file | what |
|---|---|
| `predeclaration_rbdep.md` | pre-registration, sha256-pinned, reverified at run time |
| `rbdep_lib.py` | frames, arms, gates, and the like-for-like statistics |
| `run_rbdep_baseline.py` / `rbdep_baseline.json` | the reproduction of B11 |
| `run_rbdep.py` / `rbdep_results.json` | the pre-registered ablation |
| `nfl/research/p4c/p4c_build.py` | `gen_weights(..., add_pool_groups=None)`, opt-in, default bit-identical |
| `nfl/tests/test_v1_teammate_dependence.py` | the switch contract, the guards, and the B11 measurement defect as a regression test |
