# OWN-3 pre-registration — cold-start quarterback state

**Written and committed before any candidate is fitted or scored.** Its sha256 is
recorded in the commit that adds it and re-checked by `run_own3.py`, which
refuses to run against a modified file.

**Authority.** Owner ruling, OWN-3 authorized: *"Build and compare the smallest
defensible cold-start QB models needed to prevent allocated QB share from
disappearing."* Core principle from the same ruling: *"cold start is a missing
state in the generative process, not permission to reassign its probability mass
to somebody else."*

**Informed by OWN-2 and by nothing else.** No candidate has been fitted and no
score has been computed. One structural fact was verified before writing this,
because it decides whether the simplest candidate is admissible at all, and it is
stated in §3 rather than discovered later.

---

## 1. Population and estimand

**Population.** A quarterback who, at the moment of forecast, holds **positive
allocated dropback share** and whom QB V1 refuses because
`slate_prospective` keeps only rows with `h_games >= 1`, where `h_games` counts
prior rows in the panel QB frame carrying `db > 0`.

OWN-2 established, and this study assumes without re-deriving: no ingestion or
identity defect in this population (0 of 35 live, 0 of 275 historical); depth
rank is the dominant observed signal; the four cold-start class labels are not
separable once rank is held; the evidence is **30 positive historical played
weeks out of 275**, including **6 at rank 1**.

**Estimand — two quantities, and they are never collapsed.**

1. `p = P(the quarterback takes at least one dropback in this game)`
2. `D | D >= 1` — the **distribution** of his dropback count given he does

A point expectation for either is a candidate failure, not a simplification.
This project has found the point-for-distribution defect five times.

Downstream, the drawn dropback count feeds the primitives the engine already
needs: attempts, sacks, scrambles, completions, passing yards, passing
touchdowns, interceptions, rush opportunity, rushing yards, rushing touchdowns.

---

## 2. What is fixed and may not be touched

- QB V1's frozen estimator, its rung ladder, and its positional pools.
- QB3's allocation, which stays `REHEARSAL_ONLY` and unpromoted.
- A3 and C3, which stay rehearsal-only.
- `PATH_C_STATE.json`, G0A (11/12), NFL-1 (NOT AUTHORIZED), T-90.
- `QB_ALLOCATION_SHARE_UNCONSUMED`, which stays **fail-closed** until a
  candidate clears every gate in §5.

---

## 3. The structural fact that sets the bottom of the ladder

Verified by reading `qb2_lib` before writing this, and stated here so it is not
mistaken for a result:

- `rung_weight` returns **0** when `h_games == 0`.
- `rung_rate` returns the **pool value** when `h_seq` is empty.
- `_mix` returns a **pure pool resample** when the own-history array is empty.

So QB V1's machinery **already runs correctly on a zero-history row**. The
`h_games >= 1` filter is the only thing excluding these quarterbacks.

Further, `football_engine.run_game` composes each QB as
`target = team_dropbacks_part x share_j`, then `fac = target / drawn` and scales
**every** field by `fac`. The drawn level therefore cancels: what survives is the
allocated target and the per-dropback rates. This is why a passthrough candidate
is admissible, and why closure is a property of the composition rather than of
the estimator.

---

## 4. Candidates, and the simplest-wins order declared now

**C0 — pool-path passthrough. Zero new parameters.**
Keep the cold-start rows. Every rate falls back to the existing positional pool
by the mechanisms in §3. The level comes from the QB3 allocation. Both estimand
margins exist and are distributional: within a draw QB3 draws a primary
identity, so a backup carries near-zero share in most draws and a starter's
share in the draws where he is primary; `p` is the fraction of draws in which his
allocated dropbacks round to at least one, and `D | D >= 1` is the distribution
over the rest.

**C0 inherits its participation model from QB3 rather than fitting one, and that
is the first thing the evaluation tests**: does QB3's allocated share reproduce
the observed participation rates OWN-2 measured — **1.000 at rank 1, 0.1494 at
rank 2, 0.0604 at rank 3+**?

**C1 — C0 plus a rank-conditioned participation margin.**
Admissible only if C0's participation is miscalibrated. `p` is estimated per
depth-rank cell {1, 2, 3+} and **shrunk toward the all-quarterback rate at the
same rank**, not toward the pooled all-rank rate. Shrinking a rank-1 starter
toward a third-stringer's rate would be aggressive in the wrong direction; the
football-correct prior for a rank-1 cold-start passer is what rank-1 passers do.
That target has a large sample and is estimated **on the fitting folds only**.

Shrinkage weight is `n / (n + K)` with **K = 4.0**, the constant this project
already uses in RC1 and at Stage-2's history-cohort boundary. It is reused with
its provenance stated rather than invented here, and it is **not tuned**.
At the rank-1 cell that gives `6/(6+4) = 0.6` on the observed rate and `0.4` on
the rank-1 prior — the aggressive shrinkage the ruling requires, applied to a
target that is not football-nonsense.

`D | D >= 1` is drawn by **resampling** the rank cell's observed played-week
dropback counts mixed with the all-rank pool at the same `n/(n+K)` weight —
RC1's own-versus-pool mixture, reused. Never a fitted parametric family, never a
mean.

**C2 — C1 plus limited static career markers.**
Admissible only if C1 wins and C2 then beats it by the §6 margin. Markers are
restricted to **experience bucket** and **draft state as a three-level factor**:
`{drafted 1-3, drafted 4-7, undrafted-or-unrecorded}`. Undrafted is a **real
state with its own cell**, never a mean imputation — OWN-2 measured that 17 of 35
live cases lack a draft number and hold 0.6313 of the 1.7014 lost share, so
imputing them would be imputing the majority of the exposure.

**No four-state class model is admissible.** OWN-2 does not support one
(0.150 / 0.158 / 0.100 at rank 2 on n of 20, 57, 10) and building it would be
fitting a label the data cannot see.

### Declared order: **C0 < C1 < C2**

The simpler candidate wins unless the more complex one beats it by the declared
margin. Ties, equivalence and indeterminate results all resolve to the simpler.

---

## 5. Gates. Pass or fail, never traded against a score

Evaluated on the full 2026 week-1 rehearsal slate, A3 on, TEST_ONLY, and on the
chronological folds where applicable.

1. **Allocation closure.** `reconcile_allocation_share` returns PASS: every unit
   of allocated dropback share reaches a modelled quarterback. **No candidate may
   pass if any allocation mass disappears.**
2. **No survivor renormalisation.** Verified structurally, not asserted: the sum
   of surviving quarterbacks' shares is unchanged by the candidate.
3. **Team dropback closure.** `Sum_q db_q == team_dropbacks_part` per draw.
4. **QB terminal-state closure.** `att + sacks + scr == db` in every draw
   (`QB_DROPBACK_IDENTITY_VIOLATED`).
5. **C3 shared-pass closure.** Completions, passing yards and passing touchdowns
   agree between layers in every draw.
6. **Rushing accounting closure.** `reconcile_rushing` and
   `qb_rush_within_team_carries` pass.
7. **No point-for-distribution.** The conditional dropback draw has positive
   dispersion in every rank cell it populates.
8. **The suite passes with no test weakened**, and every existing guard keeps
   its input.

A candidate failing any gate is rejected outright. There is no appeal on score.

---

## 6. Scores, and the margin fixed now

Chronological, forward-chained. Evaluation seasons **2022, 2023, 2024**; 2020 and
2021 are **burn-in** and are never scored, because a player cannot be shown to be
new when the coverage itself is new. Each evaluation ordinal is fitted on
strictly earlier data only, reproducing the information state available before
kickoff: depth chart, roster career markers, injury and practice report, and no
outcome at or after the ordinal.

| # | quantity | score |
|---|---|---|
| 1 | participation probability | Brier score, plus a reliability table and log score |
| 2 | conditional dropback distribution | CRPS on `D given D >= 1` |
| 3 | **overall QB dropback allocation error** | **CRPS on the unconditional dropback count — PRIMARY** |
| 4–7 | closure and accounting | §5 gates, not scored |

**Primary endpoint:** mean CRPS on the unconditional dropback count over
cold-start player-weeks. It is primary because it is the quantity the leak
destroys and because it combines both margins without letting either be traded
away.

**Uncertainty.** Cluster by **team-game** — a quarterback room shares one team
dropback budget, so its rows are not independent. Bootstrap 2,000 resamples of
clusters, 95% intervals. Sensitivity: contiguous season-week blocks. **A naive
independent-row interval is forbidden and the reporting layer must refuse one.**

**Margin.** Improvement is `control CRPS − candidate CRPS`.
**δ = 2% of the control's CRPS.** Support the more complex candidate if its 95%
clustered interval lies **entirely above δ**; flag harm if entirely below −δ;
declare practical equivalence if entirely inside `[−δ, δ]`; otherwise
**indeterminate**. Equivalence and indeterminate both resolve to the simpler
candidate.

**Predicted in advance, so it cannot be claimed as a finding afterwards:** with
30 positive observations and 6 at rank 1, the most likely outcome is
**indeterminate**, and the declared rule then selects **C0**. That is the
expected result of this study, not a disappointment, and it is written here
before any number exists.

---

## 7. Prohibitions

1. **No survivor renormalisation**, in any candidate, under any condition.
2. **No point estimate where a distribution belongs.**
3. **No silent constants.** K = 4.0 is reused with provenance; every other rate
   is estimated on fitting folds or refused by name.
4. **No mean imputation of draft number.** Undrafted is a state.
5. **No 2026 outcomes.** None exist.
6. **No market, sportsbook, DFS or restricted-vendor input.**
7. **Nothing is promoted.** Development evidence may reject a candidate; it may
   never promote one.
8. **This must not become a general replacement for QB V1.** It is a week-1 and
   backup instrument. OWN-2 measured rank 1 at 0 of 1,731 from week 2 onward.
   A candidate that changes any forecastable quarterback's draw is rejected.
9. **G0A, T-90 and the cold-start freeze are untouched.** Where a candidate
   would require altering the cold-start freeze, it is reported to the owner
   rather than implemented.

---

## 8. After the study

Whatever wins, rerun the week-1 rehearsal and remeasure, per the ruling: total
QB allocation consumed, completions, passing yards, targeted throws, passing
touchdowns, and the C3 accounting identities. Only then is the surviving
passing-TD gap reassessed. XL2 and the C3 retrospective stay blocked until the
allocation leak is resolved.

## 9. What this study cannot conclude

- That any candidate **forecasts** the cold-start population well. Thirty
  positive observations cannot establish that.
- That C0 winning means QB3's participation model is correct — only that a
  simpler alternative was not beaten.
- Anything justifying promotion.

## 10. Order of execution

1. Commit this file. Record its sha256.
2. Build C0. Gates, then scores.
3. Build C1 **only if** C0's participation calibration fails. Gates, then scores.
4. Build C2 **only if** C1 wins. Gates, then scores.
5. Report, including every result that disagrees with what is written above.
