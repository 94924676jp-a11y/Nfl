# Preregistration: QBCTX-DB1, a QB-conditioned team-dropbacks candidate (2026-10-09)

**Status: PREREGISTERED, NOT EVALUATED.** Written before any prospective result exists. Nothing here changes a
production forecast.

## Why this is a new candidate and not a rescue

The parent candidate (QBCTX shadow, branch `claude/qbctx-shadow-research`, commits `dd440398` predeclaration and
`84bdf269` result; preserved on the main research branch as `eddf6459` and `d990493e` by cherry-pick, contents
identical) **failed its predeclared bar**: 1 of 3 quantities passed. Its verdict file
`nfl/research/qb_regime/QBCTX_SHADOW_EVAL.json` is preserved unchanged and stays a FAIL.
- **Dropbacks passed:** QB-change MAE −0.216, 95% CI [−0.394, −0.040], non-inferior on stable games.
- **Pass rate and QB rush attempts failed.**

That verdict stands as recorded. Selecting the one passing component of a failed test and declaring it validated would
be choosing the answer after seeing it. The 2024–2025 evidence that suggested it is **development evidence for this
candidate, never its confirmation**. QBCTX-DB1 is therefore evaluated only on games that **no part of either study has
seen**.

## The candidate (frozen at commit time of this file)

- **Quantity:** team dropbacks for a team-game with a known pregame starting QB.
- **Model:** exactly the parent's dropbacks arm, as committed in `84bdf269` (= `d990493e`)
  (`nfl/research/qb_regime/qbctx_shadow.py`):
  - club baseline over the prior 8 club games, blended as `proj_v1.team_volume` blends;
  - plus a QB deviation with exposure `a = f − c`, shrunk by maximum-likelihood between-QB variance with prior mean 0;
  - population parameters re-fitted each week on games strictly before that week (point-in-time asserted).
- **Not included:** pass rate, QB rushing and teammate shares. They are absent, not "kept for later".
- **Incumbent:** the parent's incumbent arm, the same quantity without the QB term.

## Evaluation (prospective only)

- **Games:** every regular-season team-game from **2026 week 6 through 2026 week 14 inclusive**. Forecasts are frozen
  before each week's first kickoff by the postgame system's freeze step and graded after.
- **Subsets:**
  - QB_CHANGE: the starter (most dropbacks) is not the club's dominant starter over the prior 8 games;
  - STABLE: all others.
  - Starter identity is the pregame starter announced or listed before kickoff, **not** the dropback leader. That
    removes the parent's oracle. A game whose actual leader differs from the pregame starter is reported separately
    as STARTER_SURPRISE.
- **Metric:** MAE of team dropbacks. Paired cluster bootstrap by team-season, B = 4000, seed 20261009.
- **Acceptance (all required):**
  1. QB_CHANGE: the 95% CI of MAE(candidate − incumbent) lies entirely below 0;
  2. STABLE: the CI upper bound ≤ +2% of the incumbent's STABLE MAE;
  3. at least **40 QB_CHANGE team-games** in the window. With fewer, the verdict is NOT_YET_EVALUABLE, never PASS.
- **Promotion** additionally requires downstream checks:
  - team pass attempts and DK points of the club's QB and pass catchers are non-inferior on the same games;
  - simulation accounting PASS for the arm's worlds.

Promotion is an owner decision after the verdict, never automatic.

## What would make this preregistration void

- Any change to the model, window, subsets or bar after the first prospective week is graded.
- Any use of 2026 week 6+ outcomes in fitting before that week's forecast is frozen.

Either voids QBCTX-DB1. A new candidate needs a new preregistration.
