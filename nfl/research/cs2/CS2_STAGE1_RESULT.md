# CS2 stage 1 — the current-season non-QB usage that never reached allocation

`nfl/production/nonqb/current_season_nonqb_panel.py`, spec
`current-season-nonqb-usage-panel-1`. **Measurement, not estimation.** No
parameter, no prior, no shrinkage, no outcome from any graded game.

## What was missing, precisely

`current_season_panel` is `current-season-qb-panel-1` — a quarterback panel by
construction. The refresh that fixed the QB season-boundary problem has no
non-QB counterpart, so 2026 week-1 receiving and rushing usage never reached
role allocation for RB, WR or TE. That is the `DATA_STATE_DEFECT` half of
`P2_DIAGNOSTIC.md`, and it is why Buffalo's starters were priced off
prior-season and depth-chart evidence alone.

Stage 1 is that data. It does not yet change any projection.

## Measured, 2026 week 1, `as_of` the DET @ BUF seal instant

196 player-club rows across **20 clubs**, from
`pbp_2026.1415dd98ba7f701a.csv.gz` (retrieved 2026-09-14T00:25:56Z, 10 games).

Buffalo, the room the defect lives in — team totals 21 carries, 28 targets:

| player | carries | carry share | targets | target share | receptions |
|---|---:|---:|---:|---:|---:|
| James Cook | 13 | **0.619** | 4 | 0.143 | 3 |
| DJ Moore | 0 | – | 8 | **0.286** | 5 |
| Ray Davis | 6 | 0.286 | 0 | – | 0 |
| Dalton Kincaid | 0 | – | 6 | 0.214 | 4 |
| Khalil Shakir | 0 | – | 6 | 0.214 | 5 |

Set that beside the sealed board: Cook's model carry share was **0.454**
unconditional, against 0.619 of the actual team carries in the only
current-season game there is. **This is the evidence that existed before the
seal and could not reach the layer that needed it.**

## Twelve clubs have nothing, and are named

`ARI DAL DEN GB KC LAC LV MIA MIN NYG PHI WAS` are absent from the widest
lawful capture, so they get **no row, no imputed share and no silent
fallback**. CS2 invariant 7: a caller that falls back to prior-season state
for them must do it visibly. Widening that coverage is a capture problem, and
it is owed rather than approximated.

## One number reconciled rather than left to disagree

`P2_DIAGNOSTIC.md` reports BUF week-1 team totals of **29 targets** and 21
carries. This module measures **28** and 21. The carries agree exactly. The
single target is a definition: Buffalo threw 32 pass attempts, of which 1 was
a two-point play and 3 carried no receiver id. A throwaway is not a target, so
32 − 1 − 3 = 28 is the box-score figure. The shares in P2 are computed on 29
and move by under half a point; **no conclusion in that document changes.**

## Stage 2 is REFUSED

`stage2_state()` returns `BLOCKED[PREREGISTRATION_INCOMPLETE]`. Turning usage
into a role state needs three choices `predeclaration_cs2.md` does not fix:

| missing | why a default is not neutral |
|---|---|
| `half_life` | how fast current-season evidence decays against older weeks. The predeclaration calls the weight "a declared, tuned quantity, not a constant" and does not declare it |
| `min_opportunity` | one carry in garbage time is not thirteen carries of evidence |
| `shrinkage_target` | the room mean, the prior-season share, or the depth-chart ordering give **different answers for exactly the rooms the defect lives in** |

A convenient default would produce a plausible number and an unfalsifiable
one. Stage 1 is available now and is not blocked by this.

## What is NOT claimed

One week, 20 of 32 clubs, and an appearance proxy — `carries + targets > 0` —
that cannot distinguish a player who took snaps and was not used from one who
did not play. Snap counts are 404 for 2026 and participation is published
after the postseason; both are recorded as owed. Nothing here is fitted to the
DET @ BUF result, which this module does not read.

**V2 NOT YET EARNED**
