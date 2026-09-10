# V1 ENGINEERING FREEZE

# `V1_ENGINEERING_READY_WAITING_ON_G0A`

**2026-09-10.** Every engineering freeze criterion passes. The only remaining
refusals are legitimate chronology and external-input conditions.

**G0A 11/12. NFL-1 NOT AUTHORIZED.** `PATH_C_STATE` untouched. Nothing
promoted. No 2026 outcome consumed for tuning.

---

## The final blocker, closed

`SCRAMBLE_CARRY_LEVEL_INCOHERENCE` → **SC1**, pre-registered
`b62e48f23b5f3a16fb633e5286e575f23d7de3e07c8ebf923255d8d565e76729`.

**The audit came first and changed the diagnosis twice.**

*It is a real football law.* Scrambles exceed team carries in **0 of 3,230**
historical team-games.

*R2 had already fixed the level defect.* Before R2 the model summed a scramble
draw over **every rostered quarterback as if each were the primary passer** —
team scrambles mean **5.973**, max 24, against a historical 1.82/11, with
**16 of 6,400** cells violating. Under R2 the same measurement gives mean
**2.046**, max 12, and **0 of 6,400** across all 32 teams. The level was never
the coupling problem.

*What actually remained was a tail-overlap on an independent draw index.* Model
corr(scrambles, carries) **+0.0299** against a historical **+0.1802**. A3G did
not lower the carry draw — its minimum is 5.26 either way — it changed **which
draw index** held that minimum, and once it landed where scrambles were high.

**SC1 is a permutation of which draw index receives which carry value.** No
value changes. The carry marginal is invariant element-for-element, the
scramble draw is untouched, nothing is fitted, no parameter is introduced, and
an infeasible pair refuses by name (`SC1_NO_FEASIBLE_ASSIGNMENT`) on Hall's
condition rather than clipping. It is a coherent joint state chosen at
generation time, not an incoherent one corrected afterwards.

## Gates — every one measured

| gate | result |
|---|---|
| cells with scrambles > carries | **0** |
| negative rush-play budgets | **0** |
| A1 exact rushing closure | **preserved** — `HARD PASS[A1_RUSH_ALLOCATION]`, every carry exactly one owner |
| QB dropback closure | **preserved** — integer-exact |
| scramble marginal | **untouched** — SC1 never reads it as a target |
| team-carry marginal | **exactly invariant** — multiset identity checked, not asserted |
| QB rushing tails | plausible; passing-TD max 9 against an all-time record of 7 |
| new clipping or capping | **none** |
| duplicate causal ownership | **none** |
| game-level A3G dependence | **preserved** — within-game corr −0.0865 → −0.0857, max change 0.013 |
| cross-game RNG contamination | **none** — 0.0634, sampling noise |
| deterministic replay | 15 distinct run ids and 15 distinct draw-artifact hashes for 15 games |

SC1's footprint on the whole slate: **1 swap, 2 cells moved of 6,400
(0.031%)**.

## Final rehearsal — canonical entrypoint, real 2026 week 1

| configuration | result |
|---|---|
| `PRODUCTION_BASELINE` | **15 SEALED, 1 REFUSED** |
| `V1_CANDIDATE` | **15 SEALED, 1 REFUSED** |

The single refusal in both is `SOURCE_CHRONOLOGY_FAILURE` on the Thursday
game, which has been played and cannot be forecast at a `written_at` after its
kickoff. **That is the guard working, not a defect.**

Accounting verdicts per sealed candidate artifact: **10 HARD PASS, 1 HARD
DEFERRED, 3 DIAGNOSTIC FAIL**. The DEFERRED is cross-layer reconciliation,
recorded as *owed* because C3 needs the receiving budget the appearance layer
has not produced. Applied: **A1, A3G, C0, R2, SC1**. Not reached: **C3**.

Suite **52 modules, 559 test functions, 3,245 checks, 0 failing, 0 raised**.

## The frozen candidate configuration

`nfl/production/candidate_mode.py` — R2, C0, C3, A3G, A1, SC1. Explicit,
non-default, every component carrying its pre-registration and its
`REHEARSAL_ONLY` governance. An unknown mode name is refused rather than
defaulted to the baseline, and `assert_not_promoted` runs at the seal on the
assembled artifact.

**Engineering integration is not prospective validation. Nothing here is
promoted.**

## What remains, and none of it is engineering

1. **G0A item 1** — needs an anchored capture inside a real T−90 window.
   External. Do not read a T−90 job merely running as 12/12.
2. **The injury feed** — 2 of 32 teams filed, so C3 and the non-QB player
   chain cannot execute. External.
3. **`RUSHING_CONVERSION_CONTROL_UNDEFINED`** — unchanged, deliberately. Carry
   ownership being coherent is not a reason to build a rushing-yard model, and
   none was built.

## POST_V1_REFINEMENT — recorded, not delayed for

A1 params are committed frozen but a **refit** still needs pbp, which is not in
this repository (`pbp_sources()` BLOCKS by name) · A3G recovers about a fifth
of the historical cross-team carry coupling, pre-declared as under-recovery ·
RB1↔RB2 at flat week-1 priors reads +0.11 where history reads −0.37, and ~29%
of that gap is unexplained · the additive share-residual floor fires on 20.68%
of small-category draws · kneel dependence z = +6.10 · receiving calibration
bias +2.18 · `rint` erases 0.5–0.9% of allocated target opportunity.

**Frozen at this commit. Optimisation stops here.**
