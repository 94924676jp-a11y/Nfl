# Pre-declaration — the single cheap internal proxy probe

Written 2026-09-08, **before the probe was run and before any probe result was
inspected**. Start HEAD `e64661c`.

Authorised by the information-gap directive §8, which permits "a tiny
falsification probe" that is predeclared, involves no model selection, answers
only whether a proxy contains **any** incremental signal, and **cannot promote
anything**.

## Why this probe and no other

The P recoverability study located the accepted control's residual in **role
transitions** (R² 0.753 stable versus 0.496/0.498 up/down, with a lag bias of
−0.027 rising and +0.038 falling). The obvious external fix is pregame role
data. This study has now measured that **no as-of pregame role record exists for
2022–2025** — the project's entire vintage capture begins 2026-09-06 — so that
hypothesis cannot be tested on development data at all.

That leaves one already-held, lawful, chronology-safe source that no study has
used for P: **offensive personnel and formation**, which W4 recorded as
"recoverable, cleanly" from `pbp_participation`. Blocks B (role/participation)
and C (teammate) were already tested in the P study and returned +0.13% and
−0.46%.

## The probe, fixed now

**Question**: does prior-game personnel and formation usage contain *any*
incremental signal for next-game pass-snap participation, beyond the accepted
control?

**Features**, all from strictly prior games, EWMA half-life 2 over prior
appeared games:

- `pers_3wr` — share of the player's pass snaps in personnel containing 3 WR
- `pers_2te` — share in personnel containing 2 TE
- `pers_2rb` — share in personnel containing 2 RB
- `form_shotgun` — share in SHOTGUN formation
- `form_empty` — share in EMPTY formation

**Specification**: exactly one ridge, penalty fixed at **1.0** (no search, no
selection), on `[p_ewma1, p_ewma2]` versus `[p_ewma1, p_ewma2] + the five probe
features`, same rows, same seasons, walk-forward, fitted on prior seasons only.

**Materiality, fixed now**: an improvement of **≥ 1% relative pooled MAE** is
"contains incremental signal". Below that is "no detectable incremental signal".
The threshold is deliberately low — this is a falsification probe, not a
promotion test, and a low bar makes a negative result stronger.

## What this probe cannot do

- It cannot promote anything, and nothing here is a candidate.
- A weak result **does not** mean true routes are weak. Personnel is not routes.
  The two are different quantities and the pre-declaration says so before the
  result exists.
- A strong result would not be a model. It would be grounds for a *separately
  authorised* study.
