# Pre-registration D1: shrink receiver target allocation toward observed usage (owner OD-003, 2026-10-14)

**Written** before any challenger code exists and before any 2025-holdout look at a challenger.

## Diagnosis this rests on (development season 2024 only, `DECOMPOSE_2024.json`)

**Where.** Top-decile WR and TE, given that they played, production settings:
- points are over-projected by 32% (WR) and 28% (TE);
- **targets** are +25% (WR) and +18% (TE);
- yards per target is +8% (WR);
- catch rate is right.

**Control.** Ranked by itself, the naive per-appearance mean also over-shoots its own top decile (regression to the mean):
WR 1.09, TE 0.99. The engine's excess is +0.23 (WR) and +0.29 (TE). RB shows little excess (1.18 vs 1.11), and QB none
(1.01 vs 1.03).

**Root-cause hypothesis.** The claim-based allocation concentrates club target volume on the top claimant more than
his observed usage supports.

## Challenger

**Rule.** Receivers only (WR, TE). Club target volume and every club identity are unchanged. For each pool receiver,
the allocated target share becomes

  `(1 − w) × allocated share + w × observed share`

- **Observed share:** his 2026 (or evaluated-season) targets per club pass play over weeks before W, from his
  appearances.
- **Renormalisation:** the result is renormalised within the club so the club total is preserved.
- **Missing observed share:** a player with no observed share keeps his allocated share.
- **Untouched:** RB, QB, rushing, efficiency and touchdowns.

**The one parameter, `w`.**
- **Estimated on 2024 only:** a grid of 0.0, 0.1, …, 1.0, chosen to minimise week-blocked unconditional MAE.
- **Frozen in the result file before 2025 is read.**
- `w = 0` reproduces the incumbent exactly (golden test).

## Evaluation

| step | rule |
|---|---|
| **Holdout 2025, one look, logged** | D1(w*) against the incumbent and against naive STD_U on the same rows, unconditional and conditional, week-blocked. **Pass:** the upper 95% bound of D1 − incumbent MAE is below 0 unconditionally, **and** no position worse with an interval excluding 0, **and** the top-decile WR+TE level ratio moves toward the naive control's. |
| **Prospective, W6 onward** | D1 runs prelock beside C as arm D of PREREG_FOUR_ARM. The decision is that pre-registration's own (30 games). |
| **Failure** | Recorded, preserved, and not tuned. A different `w` or rule is a new pre-registration. |

**Not authorized here.** Promotion. Any change to production defaults (D1 is an opt-in research arm).
