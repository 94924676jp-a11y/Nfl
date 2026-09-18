# GAME_OFFENSE_COUPLING — measured, and the review's premise does not survive

**The gate was: "sealed DET-BUF club-vs-opponent offensive correlation is
approximately negative, while archived historical game-level measurements are
positive."**

The first half is true. **The second half is not.** Measured on the same
statistic, the same transformation and the same exclusions:

| population | n | r | 95% CI |
|---|---:|---:|---|
| history 2024, yards | 285 | **−0.0858** | [−0.2000, +0.0307] |
| 2024, club-demeaned | 285 | −0.0165 | [−0.1324, +0.0999] |
| 2024, **points** | 285 | **−0.0912** | [−0.2053, +0.0252] |
| history 2025, yards | 285 | **+0.0178** | [−0.0986, +0.1337] |
| 2025, club-demeaned | 285 | −0.0265 | [−0.1423, +0.0899] |
| 2025, **points** | 285 | **−0.0221** | [−0.1379, +0.0943] |
| sealed DET-BUF worlds | 8,000 | **−0.1310** | [−0.1525, −0.1094] |

**Historical coupling is not positive. It is indistinguishable from zero**, on
yards and on points, in both seasons, with and without club de-meaning. Every
historical interval contains zero. The simulated value is the only one that
excludes zero, and it sits *inside* 2024's yardage interval.

## The definition, stated once

`offensive_yards = passing yards + rushing yards` per club per game, two-point
plays excluded. **Receiving yards are deliberately not added** — they are the
passing yards again, seen from the other end, and including them would double
every completion. `GAME_OFFENSE_COUPLING` is the Pearson r between the two
clubs' values over the population.

## Why between-game correlation was the wrong place to look

**Two clubs share one clock.** Every drive one offence runs is a drive the
other does not. Time of possession puts a mechanical *negative* component into
between-game yardage correlation that has nothing to do with whether the clubs
pushed each other. That is why the points version was computed too: points do
not share a clock in the same way, both clubs can score heavily in the same
game, and if a positive coupling exists at this aggregation it should show
there. **It does not.**

The shootout intuition is real football, but it is a statement about the
*within-game conditional* structure — a trailing team throws more, a leading
team runs — not about the marginal correlation of two offences across games.
Those are different quantities and the marginal one is confounded in the
opposite direction.

## The two populations were never the same quantity

History gives **one observation per game**, so its r carries between-matchup
variation as well as any within-game coupling. The simulation gives **8,000
observations of one game** — same clubs, same opponent, same venue every time
— so its r is purely within-game. The comparison is legitimate as a **sign
test** and not as an equality of estimates, and that is how it is reported.

## The absence that is itself the finding

**The points coupling cannot be measured on the simulation at all, because the
sealed board emits no score and no game total anywhere.** Its team layer is
snaps, dropbacks, carries, targets and red-zone carries. A simulator with no
score cannot produce a shootout, cannot be asked whether it does, and cannot
be corrected toward one.

That is the structural gap `H2_GAME_ENVIRONMENT_TOO_COMPRESSED` and
`H3_UPPER_TAIL_JOINT_DEPENDENCE_UNDERSTATED` are about, and it is upstream of
any correlation repair.

## What was NOT done, deliberately

No historical correlation was written into the simulator. No correlation
constant was introduced. No sign was flipped. The instruction was to establish
the measurement first, and the measurement says the thing it was meant to
confirm is not there.

## Coverage, stated

The simulated side sums the **named** rows of the sealed board — 4 QB rows and
27 rushing rows across both clubs. A club's unmodelled rushers sit in
`rush_player_pool__unmodelled_back_pool` and are not in the per-player layers,
so simulated club yards are a lower bound. A constant shortfall cannot create
or destroy a correlation; a shortfall that varies with production can, and the
size is carried in the artifact rather than assumed away.

## What follows

The next step is **not** a correlation repair. It is the score-state layer the
target architecture names: game environment → drives → plays per drive →
evolving score → pass/rush tendency → team opportunities. Once a world has a
score, the within-game conditional structure becomes measurable, and *that* is
where the shootout question can actually be asked.

Until then `R4_GAME_OFFENSE_COUPLING_SIGN` is recorded as **premise not
supported by measurement**, and the simulated −0.131 is a small, real, and
so-far unexplained negative that no historical positive justifies correcting
toward.

**V2 NOT YET EARNED**
