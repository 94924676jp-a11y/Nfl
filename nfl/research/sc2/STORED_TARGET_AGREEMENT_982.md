# The 982 agreeing cells: attributed, explained, and NOT caused by SC2

`test_conservation` pins `stored_target_exact_agreement_cells: 0` against
`stored_target_cells: 110000`. The scan now reads **982 / 114000**. My first
guess was that the repaired C3/SC2 path had produced it. **That guess is
wrong**, and the measurement says so plainly.

## 1. Attribution — exactly two boards

Scanned all 112 boards in the fence corpus and summed `n_zero` per board:

| cells | board | mode | draws | code_commit |
|---|---|---|---|---|
| 491 / 2000 | `2026_02_DET_BUF/pre_inactives_V1_CANDIDATE_R9_W1P/81db92580ac3d872` | `V1_CANDIDATE_R9_W1P` | 1,000 | `af9ef9e1cdd8` |
| 491 / 2000 | `2026_02_DET_BUF/pre_inactives_V1_CANDIDATE_R9_W1P_G/e58206e3e8473dc1` | `V1_CANDIDATE_R9_W1P_G` | 1,000 | `a488cee70562` |
| **982** | | | | |

Per team, identical on both: **BUF 267/1000, DET 224/1000**. Identical because
`R9_W1P_G` is `R9_W1P` plus the gadget-rush allocation, which touches no part
of the target budget, so the two boards share the same target draws.

**Both commits predate SC2 and the C3 refusal transport entirely.** Neither
board carries SC2. The cause cannot be a change made after they were sealed.

## 2. Why those cells agree — derived, then verified

The check measures `team_volume/team_targets - rint(sum QB attempts)`.

`R9_W1P` introduced `publish_partitioned_team_targets`. From that arm forward
the board publishes **the level the partition actually consumed** --
`targeted = throws - untargeted` -- instead of D1's separately drawn
continuous vector. So the gap this check measures is, identically,

    gap = targeted - throws = -untargeted

and it is **zero exactly when no throw in that draw was a throwaway or a
spike**. `untargeted ~ Binomial(throws, u)` with `u = 0.042320`, estimated in
`shared_pass.untargeted_rate()` from held history, so

    P(gap = 0) = E[(1 - u) ** throws]

Measured against that closed form on the sealed draws:

| board | team | cells | gap = 0 | observed | `E[(1-u)^throws]` |
|---|---|---|---|---|---|
| R9_W1P (1,000) | BUF | 1000 | 267 | 0.2670 | **0.2656** |
| R9_W1P (1,000) | DET | 1000 | 224 | 0.2240 | **0.2426** |
| R9_W1P_G (1,000) | BUF | 1000 | 267 | 0.2670 | 0.2656 |
| R9_W1P_G (1,000) | DET | 1000 | 224 | 0.2240 | 0.2426 |
| GA (8,000) | BUF | 8000 | 2127 | 0.2659 | **0.2637** |
| GA (8,000) | DET | 8000 | 1912 | 0.2390 | **0.2430** |
| GS (8,000) | BUF | 8000 | 2127 | 0.2659 | 0.2637 |
| GSV (8,000) | DET | 8000 | 1912 | 0.2390 | 0.2430 |

And the sign is the proof the derivation is the right one: **`gap <= 0` in
1.0000 of every board's cells**, max exactly `+0`, min `-7` and `-8`. A gap
that can only be non-positive and lands on zero at the Binomial-zero rate is
the untargeted pool and nothing else.

## 3. Why it is an expected consequence of a repair, not an artifact

WS09 J-12's defect was that the board published D1's separately drawn
CONTINUOUS team-target vector -- a second owner of one football quantity,
which nothing partitioned. Exact agreement between an independent continuous
draw and an integer budget has probability ~0, which is why the pin reads 0.

`R9_W1P` repaired that. The stored vector IS the partitioned level now, so
agreement is not a coincidence between two unrelated numbers; it is the
identity `targeted = throws` holding on the draws where the throwaway pool
happened to be empty. **The pin of 0 encodes a pre-repair world.**

## 4. SC2 changes this by exactly nothing

GA (C3 NOT reached, no SC2), GS (C3 + SC2) and GSV (C3 + SC2) return
**identical** counts -- BUF 2127, DET 1912 on 8,000 draws. SC2 reserves
interceptions out of the catch pool; it does not touch the throw budget or the
untargeted draw, and the measurement confirms it to the cell.

GA contributes 0 to the fence total only because the check declares
`regime: 'C3'` and GA's applied list lacks C3 -- the half-applied-C3 board is
skipped by the fence, which is itself worth noticing.

## 5. What this licenses, and what it does not

**Licensed:** re-pinning `stored_target_exact_agreement_cells`, because the
quantity is understood, derived in closed form and verified.

**NOT licensed:** leaving the check's prose as it stands. Its `contract` field
still reads *"the stored vector is a separate unused D1 draw"* and its
`asserts` still describes the gap as *"the distance between the stored team
target total and the budget the game ACTUALLY dealt from"*. For every arm
carrying `publish_partitioned_team_targets` that is **false**: the stored
vector IS the budget, and the gap is the throwaway pool. A check whose
description contradicts what it measures is the next defect, not a tidy-up.

V2 NOT YET EARNED.
