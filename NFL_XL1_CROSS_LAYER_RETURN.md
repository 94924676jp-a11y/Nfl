# XL1 — the shared passing event, generated once

**Task:** the cross-layer passing ↔ receiving defect, which NFL-INTEL-1's
reconciliation left at the front of the queue. Owner constraint: *"do not simply
force equality after independently generating QB and receiver outcomes.
Determine the correct causal ownership of the shared passing event."*

**Result, stated first.** Two candidates were built under a committed
pre-registration. Both close all three identities **exactly, in 12,800 of 12,800
draws, with no clipping**. Against the baseline's **12,800 of 12,800
violations**. `C3`, the event-owned construction, is the recommended
architecture: it is better than the simpler control on all three team metrics
and it credits each completion to the quarterback who actually threw it.

**Nothing is promoted.** `SHARED_PASS_DEFAULT` is `'off'`, production still runs
B0, `PATH_C_STATE.json` is untouched, G0A is 11/12, NFL-1 is NOT AUTHORIZED.

**And the defect turned out not to be the defect it was reported as** — §1. That
correction changed the design, and it left behind a larger, newly localised
problem that neither candidate fixes and that is now the successor — §6.

---

## 0. Canonical state

| | |
|---|---|
| Repo | `94924676jp-a11y/Nfl`, branch `main` |
| Pre-registration | `nfl/research/xl1/predeclaration_xl1.md`, sha256 `60fe3fbc0f35933e7bd4b43c56fb0afb68d95de67b4f51699a878ceb488d94da`, **committed before any candidate was built** |
| Suite | **42 modules, 445 test functions, 2,577 checks, 0 failing** (was 41 / 434 / 2,525) |
| G0A | **11/12**, unchanged |
| NFL-1 | **NOT AUTHORIZED**, unchanged |
| `PATH_C_STATE.json` | **not modified** |
| A3 | on in rehearsal, **not promoted** |
| 2026 outcomes consumed | **none** |
| Market / DFS / restricted-vendor input | **none** |

---

## 1. The defect is dependence, not level. The earlier reading was wrong.

`nfl/research/xl1/diagnose_xl1.py`. Full 2026 week-1 rehearsal slate, **32
team-games, 400 draws**, A3 on, TEST_ONLY. History is
`nfl/research/xl1/history_levels.json`: REG 2020–2025, **3,230 team-games**.

| link | receiving side | QB side | history | mean abs diff/draw | corr |
|---|---|---|---|---|---|
| team completions | 19.371 | 19.759 | 21.714 | 5.05 | 0.522 |
| team passing yards | 212.90 | 218.75 | 237.88 | 80.18 | 0.343 |
| team passing TD | 1.3505 | 1.3627 | 1.4969 | 1.35 | 0.060 |

The two sides are within **2.7% of each other** on passing yards and **2.0%** on
completions. Neither is the wrong one. A previous session recorded this defect
as "~45% of the quantity"; that figure was a **per-draw absolute difference read
as a level error**, and it is not one. I am correcting my own earlier number.

What it actually is: two independent draws of one quantity. For independent
X, Y, `E|X−Y| = sqrt(2/π)·sqrt(σx²+σy²)`:

| link | σ recv | σ QB | E&#124;d&#124; if independent | E&#124;d&#124; observed |
|---|---|---|---|---|
| completions | 5.96 | 7.20 | 7.46 | 5.42 |
| passing yards | 80.79 | 102.16 | 103.92 | 85.45 |
| passing TD | 1.22 | 2.23 | 2.03 | 1.52 |

Observed sits below the independence prediction by exactly what the measured
correlations imply, and those correlations exist only because both layers
descend from D1's team volume with A3 coupling it. The identity held in **0 of
12,800 draws**.

**This changed the design.** A candidate that repairs the identity by moving one
side's level onto the other trades a dependence defect for a level defect, so
Gate 2 scores levels with margins fixed before the candidates ran.

### The identity the simulator has to reproduce

Measured on the same 3,230 historical team-games:

| identity | exact | mean abs diff |
|---|---|---|
| team completions == team receptions | **3,230 / 3,230** | 0 |
| team passing TD == team receiving TD | **3,230 / 3,230** | 0 |
| team passing yards == team receiving yards | 3,154 / 3,230 (97.65%) | 0.26 yd |
| passing yards == receiving yards **+ lateral receiving yards** | 3,214 / 3,230 (99.50%) | 0.033 yd, max 20 |

81 team-games contain a lateral. The **16** that still do not close after
laterals are a **source discrepancy**, reported and never absorbed into a
residual — the discipline NFL-INTEL-1 asked for. Our generator emits no laterals,
so its target is the **exact** identity in every draw.

---

## 2. Causal ownership

A dropback resolves into exactly one of **sack**, **scramble**, **throw**. The QB
layer already owns that partition as a chained multinomial that closes exactly.

A **throw** is either untargeted (throwaway, spike) or aimed at a receiver, where
it is incomplete, intercepted, or complete. A **completion is one event** that
simultaneously produces a completion for the passer, a reception for the catcher,
**one yardage gain credited to both**, and possibly one touchdown credited to
both.

Neither layer owns that event. The throw budget is the passer's. The assignment
of a targeted throw to a receiver is the competition's. The gain is a property of
the completion.

Measured decomposition of the historical throw budget per team-game: **33.55
throws = 32.13 targeted + 1.42 untargeted**. Attempts as nflverse reports them
are ~35.9 because `pass_attempt` includes sacks (W2 §3.1), so the identity must
use **targeted throws**, never attempts — the constraint NFL-INTEL-1 named,
now quantified.

**An interception needs no special handling and that is worth stating**, because
it looks like it should. An intercepted pass carries a `receiver_player_id` and
`complete_pass == 0`, so RC1's catch rate — receptions over targets — already has
interceptions inside its incompletion mass. Modelling them separately would
double-count them. Verified in `build_recv.py`'s own target rule.

---

## 3. The candidates

**C1 — receiver-owned derivation.** The receiving chain is untouched; the QB's
completions, passing yards and passing touchdowns are the team sum over its
receivers. Simple, but it derives a **team** total where the QB layer emits
**per-QB** lines, so it needs an allocation — QB3's dropback share — and it makes
a passer's yards a function of his receivers alone.

**C3 — event-owned construction.** The recommended one.

1. throws := the QB layer's `att`, already a closed multinomial component of DB
2. throws split into targeted and **untargeted**, the latter a *named pool*
3. each targeted throw dealt to a receiver by the **existing target simplex**
4. RC1 and TD2 then run **completely unmodified** on that budget

C3 changes exactly one input to the receiving chain — the target vector — and
calls `layers.receiving_conversion` and `layers.td_layer` with no modification at
all. Each completion belongs to a specific passer, so per-QB credit comes from
construction, which is the thing C1 can only approximate.

**C2 — QB-owned allocation** was declared last and not built: it needs a
compositional yardage model that does not exist, and naive normalisation would
flatten the per-catch tail RC1 exists to preserve (skew 2.197, excess kurtosis
7.830, `P(gain>40)` 0.0203 empirical against 0.0016 Gaussian).

**No fitted constant was introduced.** The one new rate — the untargeted-throw
share, **0.042320** — is read from the historical artifact with its seasons and
its n=3,230, and `untargeted_rate()` returns
`BLOCKED[UNTARGETED_RATE_NOT_ESTIMATED]` if that artifact is absent. Tested.

### The equivalence gate that licenses reading the C3 numbers

B0 comes from `football_engine.run_game` itself, not from a local
re-composition. Before any C3 number is quoted, the study re-runs the conversion
chain on **B0's own target vector** and must reproduce B0 byte for byte.
**48 of 48 checks byte-identical.** Without that, a C3 difference could be the
changed orchestration rather than the candidate.

---

## 4. Gate 1 — structural. Decisive.

32 team-games × 400 draws = 12,800 draws per link.

| arm | completions | passing yards | passing TD | verdict |
|---|---|---|---|---|
| **B0** | **12,800 / 12,800 violate**, mean 5.07 | **12,800 / 12,800**, mean 80.25 | **11,948 / 12,800**, mean 1.36 | **FAIL** |
| **C1** | 0 / 12,800 | 0 / 12,800 | 0 / 12,800 | **PASS** |
| **C3** | 0 / 12,800 | 0 / 12,800 | 0 / 12,800 | **PASS** |

Exact, in every draw, by construction. **No clipping anywhere, no post-hoc
overwrite, no equality forced after independent generation.** Every accounting
identity that was passing still passes and no test was weakened.

---

## 5. Gate 2 — what it cost, against margins fixed in advance

Margins declared before the run: **5%** at team level, **10%** at player level.

### Team level

| metric | B0 vs history | C1 | C3 | history |
|---|---|---|---|---|
| completions | −9.00% | −10.67% (+1.67 worse) | **−10.00% (+1.00 worse)** | 21.714 |
| passing yards | −8.04% | −10.44% (+2.40 worse) | **−10.01% (+1.97 worse)** | 237.876 |
| passing TD | −8.97% | −9.31% (+0.34 worse) | **−8.96% (−0.01, better)** | 1.4969 |

**No flags on either candidate.** Both move slightly further from history because
both adopt the receiving side, which was the lower of the two. **C3 beats C1 on
all three.** Under the simplest-wins ordering declared in advance, C1 was
preferred only if it matched or beat C3; it does not, and C3 also solves the
per-QB credit problem C1 must approximate. **C3 is the recommendation.**

### Player level — C3, and the pooled number is misleading

Pooled: 3,333 of 5,936 checks beyond the 10% margin, mean |rel| 0.220. Stratified,
which is the reading that means something:

| stratum | n | mean &#124;rel&#124; | **median rel** |
|---|---|---|---|
| **means** | 3,189 | 0.149 | **+0.008** |
| **means, players with B0 mean ≥ 3** | 672 | 0.115 | **−0.001** |
| **p95** | 2,747 | 0.302 | **+0.171** |

**Player means do not move. The upper tail moves up by about 17%.** For players
with meaningful volume the median mean displacement is **−0.1%**.

This is a **dispersion** change, not a level change, and its cause is exact
arithmetic rather than a mystery. B0 computes `T = share × volume`, which treats
a *count* as deterministic given the share draw. C3 **deals** the throws, so
target counts carry the multinomial term B0 omitted. For a player on ~17% of ~29
targeted throws the added variance is `29 × 0.17 × 0.83 ≈ 4.1`, an SD of ~2.0 on
top of B0's ~1.5 — predicting a p95 lift near 20% against the 17% observed.

C1 has no player displacement at all: it reads B0's own arrays.

**What this is not.** It is not evidence the wider tail is better calibrated.
There are no outcomes here and none may be used. C3 restores a sampling layer
B0 omitted, which is a correctness argument; whether it scores better is a
separate question §7 says how to answer.

The worst individual rows are receiving-TD p95 moving from 0.05 to 1.0 — a
percentile crossing an integer on a near-zero-touchdown player, `rel = 19`.
Those inflate the pooled mean and say nothing, which is why the strata are
reported and the pooled figure is not the headline.

---

## 6. What neither candidate fixes, now localised — and it is bigger

Every arm sits **8–10% below history on the whole passing chain**. Restoring the
identity does not touch that, and it was never going to. Measured directly from
D1 on the same slate, 32 teams, 400 draws:

| D1 metric | simulator | history | rel |
|---|---|---|---|
| `team_carries` | 27.70 | 26.92 | **+2.9%** |
| `team_dropbacks_part` | 36.53 | 37.61 | **−2.9%** |
| `team_targets` | **29.19** | **32.13** | **−9.2%** |

**D1's carries and dropbacks are fine. Its target metric is 9.2% low, on its
own.** That is where the passing chain's level gap starts, and it is a defect in
one metric rather than in the volume layer.

**C3 does not consume `team_targets` at all** — it derives targeted throws from
the QB attempt budget — so C3 routes around this defect rather than inheriting
it. That was not the reason C3 was designed, and it is worth recording as a
consequence rather than claiming it as an intention.

**A second lead, and it is stated as a lead.** Σ QB attempts is **30.43** against
a team dropback budget of **36.53**, an attempt share of **0.833**; historically
throws over dropbacks is **33.55 / 37.61 = 0.892**. Sacks plus scrambles are
therefore taking **6.10** of the simulator's dropbacks against **4.32**
historically — about 41% too much, costing roughly three throws per team-game.
**This is a lead, not a diagnosis:** it compares a 2026 week-1 rehearsal roster,
heavy with players who fall back to positional pools, against a 2020–2025
realised mean. Those are different populations and the gap may be the roster
rather than the model. It needs its own study before anyone calls it a defect.

---

## 7. What this study cannot conclude

- **That either candidate forecasts better.** No outcomes exist, none were used,
  and no holdout exists. Coherence is not accuracy.
- **That C3 is correct.** It is coherent, which is weaker.
- **Anything justifying promotion.** Nothing is promoted.

What would settle it: a retrospective run of B0 and C3 across 2020–2025 with
strictly-prior information at each issuance, scored by CRPS on player counts and
yards, energy score on the teammate vectors, and interval coverage clustered by
game. That is a separate pre-registration on heavily-mined development seasons,
so it could **reject** C3 and could never promote it.

---

## 8. Files

| File | Role |
|---|---|
| `nfl/research/xl1/predeclaration_xl1.md` | the pre-registration, committed first |
| `nfl/research/xl1/build_history_levels.py`, `history_levels.json` | the historical identity and levels, 3,230 team-games |
| `nfl/research/xl1/diagnose_xl1.py`, `xl1_diagnosis.json` | §1 |
| `nfl/production/nonqb/shared_pass.py` | the candidate mechanics; default `'off'` |
| `nfl/research/xl1/run_xl1.py`, `xl1_results.json` | the two gates |
| `nfl/tests/test_xl1_shared_pass.py` | **52 checks**, including the bypass proof |
| `nfl/production/nonqb/football_engine.py` | one additive payload key, `allocation` |

The one production change is additive: the engine's payload now carries the
allocation layer's own outputs so a study can re-run the conversion chain on a
different budget without reimplementing the layers that produced the
competition. B0's draws are unchanged, which the equivalence gate verifies.

---

## 9. Queue

1. **D1's `team_targets`, 9.2% low on its own** while carries and dropbacks are
   within 3%. Newly localised, and the largest measured level defect in the
   system.
2. **Opposing-team dependence.** Simulator +0.001 carries against historical
   −0.535; needs a game-level play-budget object that does not exist.
3. **The dropback attempt share, 0.833 against 0.892.** A lead, per §6.
4. **Role-aware reallocation.** NFL-INTEL-1's experiment 3 is the right shape.
5. Lateral exception on the receiving identity (small, from NFL-INTEL-1 §3).
6. P5A rectification. 7. QB3b week-1 incumbency.
