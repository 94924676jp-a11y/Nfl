# QB participation: the successor architecture, and why it is not a patch

**Status: RECORDED, NOT STARTED. Not part of the V2 gate.** Owner's direction,
2026-09-17: record hierarchical / competing-risk QB participation as the
successor architecture rather than building another immediate patch. No
QBSEM2, and no further fallback variant.

This file exists so the next person does not re-derive the case for it from
scratch, and does not mistake it for work in progress.

---

## What the evidence already says about the design

Three measurements from the QBSEM work (`nfl/research/qbsem/`) constrain the
successor. None of them is an argument for another cell-rate variant.

### 1. Conditioning on the starter cell is worth something, and only where it has support

Forward-chained over 3,206 non-starting quarterback rows in 2,153 team-game
clusters, against a forward-chained constant:

| rows | Brier(cell) − Brier(constant) | clustered 95% |
|---|---|---|
| 3,102 using their own cell rate | **−0.002668** | [−0.00348, −0.00181] |
| 104 falling back | **+0.474709** | [+0.39126, +0.55197] |
| all 3,206 | +0.012818 | [+0.00822, +0.01735] |

**The signal is real and small; the hard fallback is the dominant failure.**

### 2. A hard switch is the wrong response to a thin cell

The fallback replaced a thin cell's own rate with a *different estimator*
answering a *different question* — the reliever-identity weight. On the 104
rows it touched it scored 0.5309 against a constant's 0.0562.

**Hierarchical shrinkage is the direct fix for this and is the main reason to
prefer it.** A partially-pooled estimate moves a thin cell toward its parent in
proportion to its own precision, so the thinnest cells become the *least*
influential rather than the most damaging. There is no switch to get wrong,
and no threshold — `CELL_RELIEF_MIN_N = 30` disappears rather than being tuned.

### 3. The states are not separable from pregame information as the frame stands

`P(db = 0 | cell)` conflates **inactive**, **benched** and **blowout**. A
competing-risk model over *starter / reliever / full absence / emergency-only*
needs those states labelled, and nothing in the present frame distinguishes
them.

**That is a data question before it is a modelling one, and it is the first
piece of work the successor needs** — not the likelihood.

---

## What the successor would have to do that QBSEM did not

- **One likelihood over the whole room**, so a quarterback's states sum to one
  by construction instead of being reconciled afterwards by forcing rules.
- **Partial pooling across cells**, replacing the min-n switch.
- **Labelled absence causes**, so "did not play" stops being one bucket.
- **Room-level dependence**: exactly one man starts, which is a multinomial
  constraint the present per-player Bernoulli treatment does not encode.

## What it must not inherit

- **The stale incumbency signal.** Whatever the likelihood, a model fed a
  season-boundary state that is wrong for a week-2 game is fed the wrong cell.
  That defect is upstream of every participation model and is being repaired
  separately — see `nfl/research/sbs/`.
- **The frame's selection history.** These cells were chosen on the same 2020
  –2025 frame every earlier QB repair was selected on, so a successor fitted
  and judged on it is exploratory for the same reason QBSEM was.

## Prerequisite before any of this starts

A labelled participation-state frame. Until absence causes are separable, a
competing-risk model has competing risks it cannot tell apart, and it will
report precision it does not have.

**V2 NOT YET EARNED**
