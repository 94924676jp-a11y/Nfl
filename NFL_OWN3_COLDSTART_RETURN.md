# OWN-3 — the cold-start quarterback state

**Mission:** build and compare the smallest defensible cold-start models needed
to stop allocated QB share disappearing. Pre-registration committed first
(`nfl/research/own3/predeclaration_own3.md`, sha256 `aedced9c…`), re-checked at
run time.

**Result in one line: the winner has zero new parameters, it fixes most of the
leak, and it exposes a second one it does not fix.**

- `C0`, a pool-path passthrough, closes the **share-level** leak completely:
  **5.3168% → 0.000000%**, 23 leaking teams → 0, share mass unchanged at exactly
  32.0000, no survivor renormalisation, and **no forecastable quarterback's draw
  altered in 924 field comparisons**. No estimator, no fitted constant.
- `C1` is **not admissible on its own premise**. The participation
  miscalibration it was meant to fix is largely **not a cold-start property** —
  it is present at nearly the same magnitude for quarterbacks the system *can*
  forecast.
- **C0 does not pass the team-dropback gate.** A second leak survives it, in the
  same defect class: when an allocated passer's raw draw is zero dropbacks, the
  composition drops his whole allocated target for that draw. **0.0518% of the
  mass — but up to 37.7 dropbacks in a single draw.**

Governance unchanged: `include_cold_start` defaults **False**, production
byte-identical; `PATH_C_STATE.json` untouched; G0A **11/12**; NFL-1 **NOT
AUTHORIZED**; QB3/A3/C3 rehearsal-only; no 2026 outcome used.

---

## 1. The ladder starts below a model

Declared in pre-registration §3 and verified by reading `qb2_lib` **before**
writing it, so it could not be presented as a result afterwards:

`rung_weight` returns **0** at `h_games == 0`; `rung_rate` returns the **pool
value** on an empty `h_seq`; `_mix` returns a **pure pool resample** on an empty
own-history array. **QB V1 already runs correctly on a zero-history row.** The
`h_games >= 1` filter was the only thing excluding these quarterbacks.

And `run_game` composes each passer as `target = team_dropbacks_part × share_j`,
then scales every field by `fac = target / drawn`, so the drawn level cancels.

**C0** keeps the cold-start rows, takes every rate from the existing positional
pool, and takes the level from the QB3 allocation. Both estimand margins survive
and stay distributional because QB3 draws a primary identity per draw.

---

## 2. Gates

| gate | scope verified | B0 (refuse) | **C0** |
|---|---|---|---|
| 1. allocation closure | full slate, 32 teams, m=400 | **FAIL** — 1.7014 / 32.0000 units reach nobody, **5.3168%**, 23 of 32 teams | **PASS — 0.000000%, 0 teams** |
| 2. no survivor renormalisation | full slate | — | **PASS** — mass exactly 32.0000, unchanged |
| 3. team dropback closure | 8 games / 16 team-games, m=100 | **FAIL** — max abs diff **25.96** | **FAIL — max abs diff 0.862** (§3) |
| 4. QB terminal-state closure | 8 games, m=100 | PASS — 0 / 4,300 | **PASS — 0 / 5,800** |
| 7. no point-for-distribution | 8 games, m=100 | n/a | **PASS — 0 of 15 cold-start rows undispersed** |
| 8. no forecastable draw changed | full slate, m=200 | — | **PASS — 0 differences, 924 comparisons, 84 quarterbacks** |

Example cold-start rows, showing both margins are real rather than a point:

| player | mean db | sd | p50 | p95 | **P(db ≥ 1)** |
|---|---|---|---|---|---|
| `00-0041561` | 0.985 | 2.795 | 0.0 | 9.8 | **0.150** |
| `00-0040464` | 0.870 | 0.866 | 0.8 | 2.2 | **0.450** |

### A correction to my own earlier reading

On a single game I saw team-dropback closure become **exact** under C0 and said
so. Across 16 team-games it is **not exact**: max abs diff 0.862. One game was
not general, and the wider run is what caught it.

### Two gates already failing before this study, and still failing

`rushing` fails in 8 of 8 games under **both** arms, and `qb_team_volume` is
4 PASS / 4 FAIL under **both**. Both are the same pre-existing item —
`qb_rush_contained_in_other`, QB rush opportunity against the team carry budget,
the R4-recorded boundary of 0.284 drawn against **0.157** measured. C0 neither
causes nor cures it.

**I am not relaxing a gate I wrote.** As the pre-registration stands, no OWN-3
candidate can pass the rushing gate, because the defect is in the QB rush model
and not in cold start. That needs an owner ruling.

---

## 3. The second leak, which C0 does not fix

`run_game` sets `fac = 0` when a quarterback's raw QB V1 draw is **zero**
dropbacks. His allocated target is then dropped **in exactly those draws**.

Measured, full slate, 32 teams, m=200, with C0 on:

| | |
|---|---|
| allocated QB rows | 119 |
| rows with at least one zero-dropback draw | **14** |
| target dropbacks lost | **0.6063 of 1171.3827 = 0.0518%** |
| **worst per-draw shortfall** | **PHI 37.71**, NE 33.64, GB 11.79, BAL 7.40 |

**The mean is negligible and the tail is not.** In the draws where a team's
*primary* passer drew zero, that team's entire passing game disappears for that
draw — 37.7 dropbacks on a budget of ~37. It would barely move an average and
would quietly distort every tail quantity built on it.

This is the same class as OWN-1: allocated mass that reaches nobody. **OWN-1's
leak had two components** — a share-level one, which C0 closes, and this
draw-level one, which it does not.

It is **not** a cold-start problem: it applies to any allocated passer whose draw
happens to be zero. The fix belongs in the composition — the natural one is to
draw the allocated target directly rather than rescaling a draw that may be zero
— and it is a change to `run_game`, not to a cold-start model. I have **not**
made it: it is outside OWN-3's pre-registered scope, and rescaling survivors to
absorb it is forbidden.

---

## 4. Part B — where the miscalibration actually lives

Strictly chronological: parameters for evaluation season `ev` fitted on seasons
strictly before `ev`; evaluation 2022–2024; 2020–2021 burn-in, never scored. The
room is the **depth chart** — the live information state, not the men who played.

| cell | n | observed | C0 model | gap |
|---|---|---|---|---|
| **cold \| rank 1** | **6** | **1.0000** | **0.5887** | **−0.4113** |
| forecastable \| rank 1 | 1,610 | 0.8689 | 0.8863 | **+0.0173** |
| cold \| rank 2 | 81 | 0.1605 | 0.2362 | +0.0757 |
| forecastable \| rank 2 | 1,514 | 0.2404 | 0.2518 | **+0.0114** |
| **cold \| rank 3+** | 167 | 0.0659 | 0.1930 | **+0.1272** |
| forecastable \| rank 3+ | 473 | 0.1226 | 0.2376 | **+0.1150** |

**Read the last two rows together.** At rank 3+ the allocation over-forecasts
participation by **+0.1272 for cold-start passers and +0.1150 for forecastable
ones** — the same defect, the same size, in a population the cold-start
component has nothing to do with. It is a **QB3 allocation property**, measured
on n = 473 forecastable cases.

At rank 1 the allocation is well calibrated where evidence is thick (+0.0173 on
n = 1,610) and badly calibrated where it is thin (−0.4113 on **n = 6**). And
6-of-6 participation is unremarkable against the general rank-1 rate of 0.8689:
`0.8689^6 = 0.43`. **The rank-1 cell cannot distinguish a cold-start effect from
the ordinary rank-1 rate** — which is why the pre-registration required it to be
shrunk rather than believed.

### Why C1 is not admissible

1. **The dominant, well-measured part of the miscalibration is not cold-start
   specific.** Building the correction into a cold-start model fixes the wrong
   layer.
2. **Any participation correction must move share inside the QB room.** Shares
   sum to one per draw, so raising a cold-start passer's participation lowers a
   teammate's — changing a forecastable quarterback's draw, which
   **pre-registration prohibition 8 rejects**, and prohibition 8 exists because
   the ruling said this must not become a general replacement for QB V1.

The correction belongs in the allocation. Its home is **QB3b**, already queued
as the week-1 incumbency definition, and it now arrives with a number attached.

**By the declared simplest-wins order, C0 wins.** The pre-registration predicted
in advance that the simplest candidate would win, and said so before any number
existed.

---

## 5. What this does not establish

- **That C0 forecasts the cold-start population well.** It does not; its
  participation is miscalibrated at every rank and the study says so.
- **That the leak is closed.** The share-level component is; the draw-level
  component in §3 is not.
- **That QB3's participation model is correct.**
- **Anything justifying promotion.** Development evidence may reject; never
  promote.

**Honest summary: C0 stops most of the probability mass disappearing, and does
not make the football better.** Under the core principle — *cold start is a
missing state in the generative process, not permission to reassign its mass* —
that is the job asked of it, and it is not yet finished.

---

## 6. Outstanding

**The full suite has not been re-run since the `qb_v1` / `football_engine`
change.** The three directly affected modules pass — `test_qb2_production` 40,
`test_qb3_allocation` 43, `test_xl1_shared_pass` 61, **144 checks, 0 failures** —
but nine `test_qb2_production` cases could not execute outside the suite harness
because a derived artifact path is not provisioned there, so this is not a
substitute for `run_suite.py`. The full-slate Part A at m=400 also did not
complete. Both are compute, not findings, and both are outstanding.

## 7. Recommendation

1. **Rule on `include_cold_start`.** It is the only change that clears the
   share-level leak, at zero parameters and zero change to any forecastable draw.
2. **Authorise a fix for the draw-level leak in §3** — a composition change,
   separate from cold start.
3. **Rule on the rushing gate**, per §2.
4. **Hand the participation miscalibration to QB3b** with the §4 table.
5. Then rerun the week-1 rehearsal and remeasure, per the ruling.

## 8. Files

| File | Role |
|---|---|
| `nfl/research/own3/predeclaration_own3.md` | committed before any fitting; sha256 re-checked at run time |
| `nfl/research/own3/run_own3.py`, `own3_results.json` | gates and the chronological calibration |
| `nfl/production/qb_v1.py` | `include_cold_start`, **default False** |
| `nfl/production/nonqb/football_engine.py` | flag passed through, evidence recorded |
