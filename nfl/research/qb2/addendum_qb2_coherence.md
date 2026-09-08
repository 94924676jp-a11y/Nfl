# QB2 ADDENDUM — three impossible-draw defects found by the predeclared §8 check

Written **before** the corrected run, so the record shows the defect was found
by a check declared in advance and the repair was named before any new number
existed. Predeclaration sha256
`e69bd331bb72a3f869b8469c27f0d9782ff49c7c69874ea79585f55a9eb84ff1`, unchanged.

## What fired

§8 of the predeclaration requires the QB layer to reconcile **per draw**. Run
on the first candidate draw set (2024, n=625 QB-games, m=200, 125,000 draw
cells per statistic):

| constraint | violating draw cells | worst |
|---|---|---|
| `dropbacks == attempts + sacks + scrambles` | 0 | — |
| `completions <= attempts` | 0 | — |
| `passing TD <= completions` | **84** (0.067%) | +2 |
| `interceptions <= attempts − completions` | **189** (0.151%) | +2 |
| `scrambles <= rush opportunities` | **22,749** (18.2%) | +10 |
| `rush TD <= rush opportunities` | 0 | — |

All three are **impossible states**, not calibration error. A passing
touchdown that is not a completion, an interception on a completed pass, and a
quarterback with more scrambles than rushing opportunities do not exist.

## They do not occur in the data

Measured on `qb.pkl`, 2022–2025, 2,645 QB player-games with any attempt,
touchdown or interception: `pass_td > completions` **0 times**,
`interceptions > attempts − completions` **0 times**, `completions > attempts`
**0 times**. `rush_opp` is `designed_rushes + scrambles` by construction in
`qb2_lib.load`, so `scrambles <= rush_opp` is definitional. These are hard
identities in the source, and a draw set that breaks them is wrong.

## Cause, in each case mine

The causal factorization predeclared in §4 is

    ... -> completion -> pass yards -> pass TD / INT
        -> designed rush / scramble -> rush yards / rush TD

and the simulator did not follow it.

1. **Passing TD** was drawn `Binomial(ATT, td_per_attempt)` — from attempts,
   skipping the completion node the factorization places above it.
2. **Interceptions** were drawn `Binomial(ATT, int_per_attempt)` — also from
   attempts, and independently of completions, so a draw could charge an
   interception to a pass the same draw had completed.
3. **Rush opportunities** were drawn `Binomial(DB, rush_opp_per_dropback)`
   as a single quantity, with no coupling to the scramble count the dropback
   mix had already produced. This is the largest of the three and it
   contradicts §4's own sentence, "Designed rush and scramble stay distinct."

This is the same failure as R1's point-substitution and my own dispersion
defect earlier in this packet: a node modelled off the wrong parent. It was
found by an ex-ante check rather than by inspection of results.

## The repair, stated before the numbers move

1. `PTD ~ Binomial(CMP, td_per_completion)` — rate re-based to completions.
2. `INT ~ Binomial(ATT − CMP, int_per_incompletion)` — rate re-based to
   incompletions.
3. `DES ~ Binomial(DB, designed_rushes_per_dropback)` and
   `RO = SCR + DES` — designed rushes drawn as their own quantity and rush
   opportunity **composed**, never drawn whole. This also supplies the
   separate designed-rush and scramble distributions §7 asked for and the
   first run did not report.

Re-basing a rate to its causal parent is not tuning: the expected count is
unchanged when the conversion matches history, and no rate was chosen by
looking at a score. No threshold, half-life, or shrinkage constant is touched;
`K = 4` and half-life 2 remain inherited.

## What this invalidates

Every number in the first `qb2_results.json` is superseded. The decomposition,
persistence, distribution and subgroup tables are all re-run. The first run's
figures are not quoted anywhere as results.

## Secondary estimand also outstanding

§5 predeclared a **rushing-yards decomposition over three components**
(`V·S`, `RO`, `RY`, 2³ = 8 coalitions) which the first run did not execute.
It is run now, and one property is recorded in advance: its full-oracle arm
**will not reproduce the realised value exactly**, because the scramble half
of a QB's rushing opportunity comes from the dropback mix `M`, which is not
one of the three predeclared rush components. The residual is named as
scramble volume rather than closed by adding a fourth component after the
fact. Shapley efficiency still holds exactly and is still asserted.

## Constraints unchanged

G0A remains 11/12. NFL-1 remains NOT AUTHORIZED. Nothing is promoted. No 2026
outcomes, no market data, no FTN.
