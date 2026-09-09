# J1 finding — the joint rushing-opportunity architecture

Pre-registration sha256
`85ff7c9cfe3f5aef2367e584c0835ccba56fa7a9c9a81db9d418200189afbf18`, committed
before any candidate was fitted or scored.

**EXPLORATORY.** 2022–2025 are development seasons. Nothing is promoted and
`PATH_C_STATE` is not edited.

## Result

Walk-forward, **all four folds ran**, 2,174 team-games. Energy score on
`(team_dropbacks, team_carries, QB_rush, RB/FB_carries)`, lower is better.

| arm | energy score | corr(carries, dropbacks) | \|error vs historical −0.393\| |
|---|---|---|---|
| A0 — control, the status quo | 8.5749 | **+0.0005** | 0.3935 |
| A1 — carve QB first | 8.5689 | −0.0019 | 0.3911 |
| A2 — causal split | 8.5682 | −0.4231 | 0.0301 |
| **A3 — joint residual resampling** | **8.4924** | **−0.4062** | **0.0132** |

Against the predeclared acceptance rule:

| contrast | ΔES | clustered CI95 | folds | worst marginal CRPS | invariants | rule |
|---|---|---|---|---|---|---|
| A1 − A0 | −0.0060 | [−0.0351, **+0.0256**] | 4 of 4 | +0.2% | no worse | **NOT MET** |
| A2 − A0 | −0.0067 | [−0.0771, **+0.0588**] | 3 of 4 | **+10.1%** | no worse | **NOT MET** |
| **A3 − A0** | **−0.0824** | **[−0.1160, −0.0503]** | **4 of 4** | −0.03% | no worse | **MET** |

## The owner was right to say "do not assume carve QB first"

**A1 fails.** Carving the QB rush out before the RB allocation fixes the
accounting invariants — `qb_rush_within_team_carries` goes from 0.0008 to
0.0000 — and does **nothing at all** for the joint structure: the reproduced
`corr(carries, dropbacks)` stays at −0.002 against a historical −0.393. Its
energy-score interval includes zero.

That is the whole lesson of this experiment. The visible symptom was an
accounting violation, so the obvious repair was an accounting repair, and an
accounting repair leaves the actual defect untouched.

**A2 fails too, and informatively.** The causal split reproduces the coupling
well (−0.423) but its QB-rush marginal CRPS is **10.1% worse** — outside the 2%
bound fixed in advance. Building the quantity through a chain of
snaps → split → scramble rate → allocation compounds error at every link, and it
buys a joint structure that a far cheaper arm also buys.

## What actually won, and why it matters that it is the cheapest arm

**A3 changes only the draw.** Every baseline, every residual pool and every
frozen marginal fit is untouched; the single change is that one historical
team-game index is drawn per simulation draw and **all** the residuals come from
that same game, instead of each metric resampling independently.

The consequences:

| | A0 | A3 |
|---|---|---|
| components sum to team carries (violation rate) | 0.0018 | **0.0000** |
| QB rush ≤ team carries (violation rate) | 0.0008 | **0.0000** |
| negative component | 0.0000 | 0.0000 |
| **draws clipped** | 0.0018 | **0.0000** |
| reproduced corr(carries, dropbacks) | +0.0005 | **−0.4062** |

Every marginal CRPS is unchanged to three decimal places (db 4.749 → 4.742,
tc 4.294 → 4.292, qb 1.546 → 1.546, rb 3.814 → 3.778). The accounting
violations disappear **because** the components now come from a single real
team-game, which by construction is internally consistent — not because
anything was clipped. A0's clipping rate goes to zero.

## The root defect this experiment was really about

`team_volume_v1.forecast` draws its five team metrics independently — a separate
RNG stream per metric, `hash(metric) % 9973`. Measured on 3,230 team-games:

| within-team correlation | historical | A0 draws |
|---|---|---|
| carries vs dropbacks | −0.393 | −0.004 |
| carries vs targets | −0.388 | +0.007 |

The dominant joint structure in team football is absent from the draws. The
QB-rush/OTHER incoherence that started this line of work was one symptom of it.

## P4C does NOT need replacing

§7 of the pre-registration said that if A2 won, the frozen P4C `carries` mass
pool would be fitted against a denominator the architecture no longer draws, and
that would require its own owner ruling. **A2 did not win.** A3 leaves
`team_carries` as a drawn quantity with an unchanged marginal, so the P4C
parameterization stands and no accepted artifact needs refitting.

## What is not claimed

- This is development data. There is no prospective evidence.
- The energy-score improvement is 0.96% in relative terms. The case for A3 rests
  at least as much on the invariants and the recovered coupling as on that
  number, and the invariants are not a scoring claim at all.
- A2 was tested in one concrete form. A more carefully built causal split might
  clear the 2% marginal bound; that is a different experiment, and the
  predeclared simplest-wins ordering would still prefer A3 if both cleared.
- No player-level allocation was re-estimated. This is a **group**-level
  factorization result.

## A defect in my own implementation, found by the tests and recorded here

The first production implementation of A3 drew the shared historical index from
the **global** residual pool. All five metrics select the `coach_empirical`
form, which resamples from **that coach's** residuals, so the global pool is a
different distribution. The test that checks marginals caught it:

| | first implementation | corrected |
|---|---|---|
| team_rz_carries mean shift vs independent mode | **−5.2%** | +0.3% |
| joint draws sitting on the zero floor | 0.0049 | **0.0000** |
| worst marginal shift across the five metrics | 5.2% | **1.1%** |

Sharing an index across metrics is only legitimate if **each metric still draws
from its own fitted pool**. The corrected version picks the shared index from
the coach's own set of team-games — the same pool and the same global fallback
that `V.draw` uses — so the fitted form is preserved exactly and the index is
still shared.

The corrected version reproduces `corr(carries, dropbacks) = −0.359` and
`corr(carries, targets) = −0.349` against historical −0.393 and −0.388. The
coupling is slightly weaker than the global-pool version's −0.382, which is
correct: the coach baseline already absorbs part of the between-coach variation,
so less of it remains in the residual.

**The J1 walk-forward scores above were computed on the research harness, whose
baseline is the declared team-mean-shrunk-to-league, not D1's `coach_empirical`
form.** The arm comparison is therefore valid on its own terms — every arm
shares that harness — but the production numbers in this section are the ones
that describe what D1 actually does.

## Recommendation

Adopt A3 as the draw mode for D1. It is implemented as an **opt-in** mode
(`joint_residuals=True`), defaulting **off**, because switching it on changes
every downstream number in the simulator even though no fit changed. That is an
owner decision, not an engineering one, and the R2 cache-equivalence property is
preserved and still tested under both modes.
