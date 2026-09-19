# Coupling reconciliation: both measurements are right, and they measure different things

**No simulator change is authorized by this document.** That is the directive's
instruction and it is also this document's conclusion.

## The conflict

| source | 2024 | 2025 | stated as |
|---|---:|---:|---|
| External report, §15 | **+0.1201** | **+0.2034** | "archived play-by-play … across 272 games each", against a simulated −0.128, called **a sign error** |
| External report, new panel §2.2 | +0.083 | +0.186 | "Team offense with opposing offense" |
| P5 canonical (`game_offense_coupling.py`) | **−0.086** | **+0.018** | offensive yards, intervals containing zero, simulation ≈ −0.131 |

Opposite signs in 2024, from the same two blobs.

## What the reconciliation found

`coupling_reconciliation.py`, every variant on a common footing, bootstrap over
games:

### 2024

| variant | r | n games | 95% CI |
|---|---:|---:|---|
| **offensive yards, all 272** — *P5's estimand* | **−0.0880** | 272 | [−0.224, +0.047] |
| offensive yards, ex-ante games | −0.1134 | 256 | [−0.245, +0.020] |
| offensive **touchdowns**, all 272 | +0.0388 | 272 | [−0.103, +0.177] |
| **club fantasy points, all players, all 272** | **+0.1576** | 272 | [+0.005, +0.292] |
| club fantasy points, all players, ex-ante games | +0.1478 | 256 | [−0.008, +0.290] |
| **role-six fantasy points** — *external panel's estimand* | **+0.1080** | 256 | [−0.031, +0.235] |

### 2025

| variant | r | n games | 95% CI |
|---|---:|---:|---|
| **offensive yards, all 272** — *P5's estimand* | **−0.0040** | 272 | [−0.133, +0.115] |
| offensive yards, ex-ante games | −0.0020 | 256 | [−0.129, +0.128] |
| offensive **touchdowns**, all 272 | +0.1056 | 272 | [−0.008, +0.225] |
| **club fantasy points, all players, all 272** | **+0.2190** | 272 | [+0.093, +0.337] |
| club fantasy points, all players, ex-ante games | +0.2212 | 256 | [+0.089, +0.343] |
| **role-six fantasy points** — *external panel's estimand* | **+0.1351** | 256 | [−0.001, +0.264] |

## The answer

**P5 reproduces to three decimals.** −0.0880 against P5's −0.086 for 2024;
−0.0040 against +0.018 for 2025, both indistinguishable from zero. P5 measured
what it said it measured and measured it correctly.

**The external's number also reproduces, under its own units.** Club fantasy
points over all players gives **+0.1576** and **+0.2190** against the report's
**+0.1201** and **+0.2034** — the same sign, the same order, and 2025 within
0.016.

**The axis is units, and only units.** Population barely moves it: dropping
week 1 changes 2024 yards from −0.0880 to −0.1134 and 2025 fantasy points from
+0.2190 to +0.2212. Coverage moves it some: role-six versus all-players is
+0.108 against +0.158 in 2024. Neither flips a sign. **Yards against fantasy
points flips it in both seasons.**

**The mechanism is touchdowns.** Offensive touchdowns alone are positively
coupled between opponents — +0.039 and +0.106 — while yards are not. Fantasy
scoring weights a touchdown at six points, four for a passing touchdown, so
fantasy points inherit the touchdown coupling that yardage does not carry. Two
opponents in a high-scoring game both score touchdowns; they do not both
accumulate yards, because yards are traded for clock and field position.

## Therefore

**The "sign error" claim is `UNSUPPORTED_AS_STATED`.** It compares a historical
correlation computed in **fantasy points** against a simulated correlation
P5 computed in **offensive yards**. Two different quantities with genuinely
different signs cannot establish that one of them is wrong. Nothing here says
the world generator is correct either — it says this comparison does not test it.

**It is not a retraction of the concern.** The concern may well be real. It is
untested, and the test is specified below.

## The measurement that would actually settle it

Compute the simulated coupling **in fantasy points**, on the sealed board, and
compare against the historical fantasy-point value of +0.158 / +0.219:

1. For each of the 8,000 sealed worlds, sum every modelled player's DraftKings
   points to a club total, using `nfl/dfs/scoring/draftkings.py`.
2. Pearson between the two clubs' world-level totals.
3. Compare the **sign** against +0.158 / +0.219, not the magnitude.

The magnitude comparison stays illegitimate for the reason P5's own docstring
gives: history is one observation per game and carries between-matchup
variation, while the simulation is 8,000 observations of one fixture and is
purely within-game. **These do not estimate the same quantity and the
comparison is only ever a sign test.** That caveat was in P5 before this
packet arrived and it survives the packet.

Two coverage caveats travel with it. The sealed board's club sum omits
`rush_player_pool__unmodelled_back_pool`, so simulated club totals are a lower
bound; P5 already reports the size of that shortfall. And the engine simulates
no fumbles, two-point conversions or return touchdowns, so a simulated fantasy
total is not scored on the same field set as a historical one.

## What is not concluded

That fantasy-point coupling is the right target for the world generator. It is
the right target for **DFS**, because DFS pays in fantasy points. Whether the
football layer should be tuned to reproduce a fantasy-point correlation is a
separate question, and tuning a simulator to match a scoring artifact is how a
football model stops being a football model.

**V2 NOT YET EARNED**
