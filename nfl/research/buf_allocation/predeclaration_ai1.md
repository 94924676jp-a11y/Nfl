# AI1: the appearance inversion. Pre-registration. Nothing is implemented.

**Scope: ONE defect, the smallest football-evidence-based correction that
addresses it.** The diagnostic (`P2_DIAGNOSTIC.md`) found two. This
pre-registration covers only the **ROLE_ALLOCATION_DEFECT**, because it has a
single named mechanism, a falsifiable test, and a correction that touches one
quantity. The **DATA_STATE_DEFECT** — CS1 being a quarterback-only panel — is a
larger build (a non-QB current-season role panel) and gets its own
pre-registration. Fixing the second without the first would leave the inversion
in place; fixing the first without the second is still an improvement.

## The defect, stated so it can be falsified

A player who is **first on his team's depth chart at his position**, **recorded
with opportunity in the most recent completed week**, and **carrying no
unavailable designation in the availability feed** must not be assigned a
higher zero-opportunity probability than a lower-depth player in the same room.

Measured violation in the sealed DET-BUF board:

| | P(carries = 0) | depth | week-1 carries | injury designation |
|---|---|---|---|---|
| James Cook | **0.375** | RB1 | 13 | none |
| Ray Davis | **0.292** | RB2 | 1 | none |

DET's room, the control: Gibbs 0.049 (RB1, 29 carries), Vaki 0.577 (RB2, 2).
The ordering there is correct, so this is not a universal property of the
appearance model.

## What is NOT proposed

- **No market quantity enters.** No line, no implied probability, no fantasy
  projection, in the correction or in its acceptance test.
- **No per-player tuning.** A fix that names James Cook is not a fix.
- **No change to conservation.** Target and carry shares already sum to
  1.0000; the correction must preserve that exactly.
- **No re-fit of the appearance model.** The proposal is a monotonicity
  constraint on its output, not a new estimator.
- **No change to CS1, OAS1, or any frozen arm.**
- **No touching of the sealed artifact.** `d709e67b82d5b01c` stays as it is.

## The correction: a declared ordering constraint, AI1

Within one team and one position group, order players by a **football-evidence
rank** built from evidence available before the forecast instant:

1. depth-chart rank at the position;
2. opportunity in the most recent completed week (carries for RB, targets for
   WR/TE);
3. availability designation.

Assert that zero-opportunity probability is **non-increasing** in that rank: a
higher-ranked player may not be absent more often than a lower-ranked one in
the same room. Where the constraint is violated, the room's appearance
probabilities are reordered to satisfy it — a **permutation within the room**,
not a rescaling, so the room's total expected opportunity is unchanged by
construction.

This is the smallest correction that removes the measured defect. It does not
decide how much more often Cook should play than Davis; it only refuses the
inversion.

## Literal acceptance gates, declared now

1. **The inversion is gone.** In every (team, position) room, for every pair
   where player A outranks player B on the football-evidence rank,
   `P(zero opportunity | A) <= P(zero opportunity | B)`. Zero violations.
2. **Conservation is exact.** Target-share sum and carry-share sum remain
   `1.0000` per team, to within 1e-9, before and after.
3. **DET is unmoved.** DET's room already satisfies the constraint, so the
   DET allocation must be **byte-identical** before and after. If DET moves,
   the correction is doing something other than what it claims.
4. **Cook's conditional share is not manufactured.** His carry share
   *conditional on appearing* is 0.692 today and must remain within
   ±0.02 of that. The correction is allowed to change how often he appears; it
   is **not** allowed to change how the room splits carries when he does.
5. **A new candidate identity.** `V1_CANDIDATE_R9_W1P_GSVUC_AI1`, never an
   edit to GSVUC or any sealed arm.
6. **The rank is auditable.** Each player's football-evidence rank and the
   three inputs that produced it are written into the artifact, so a reader
   can check the ordering rather than trust it.

## What would falsify this as the right fix

If, after the constraint, Cook's unconditional carry share is still far from
his conditional 0.692 — say below 0.60 — then the inversion was not the
dominant mechanism and the remaining gap belongs to the share model, not the
appearance model. That outcome is to be **reported, not patched**, and it
would redirect the work to the DATA_STATE_DEFECT.

If the constraint fires on many rooms across many fixtures rather than a few,
the appearance model has a general ordering problem and a monotonicity patch
on its output is treating a symptom. The count of firing rooms per fixture is
therefore recorded from the first run.

## Expected outcome, recorded in advance

Cook's unconditional carry share rises toward his conditional 0.692 and Ray
Davis's falls toward his week-1 share. **That is not a prediction that the
market is right.** Week 1 is one game and 13 carries is a small sample. The
claim being tested is only that the model's own allocation should not
contradict the single piece of current-season football evidence available to
it, in a direction no injury or depth-chart fact supports.

**MARKET IS DIAGNOSTIC EVIDENCE ONLY, NOT A TARGET**

**V2 NOT YET EARNED**
