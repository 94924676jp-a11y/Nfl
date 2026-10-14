# Benchmark mandate: first measurement report (owner 37cdd6dc, 2026-10-14)

**Headline.** For the first time, the system's player forecasts are scored against outcomes and against transparent
baselines, with uncertainty.

**What this file is not.**
- It is not an industry ranking. `EXTERNAL_RANK` is **UNKNOWN**: no timestamped vendor projection archive exists for
  matched slates (requested as RES-011).
- It promotes nothing.

**Machine-readable record.**

| file | content |
|---|---|
| `MODEL_SCORECARD.json` | the summary scorecard |
| `PLAYER_SCORECARD.json` | held-out player means, 2024-2025 |
| `PROSPECTIVE_SCORECARD.json` | the system's real prelock forecasts, 2026 |
| `REPLAY_MANIFEST.json` | inputs, code hashes, commands, seeds, what is and is not vintage-correct |
| `DATA_INVENTORY.json` | 16 slates and 18 data families, with clocks and rights status |

All are under `nfl/research/benchmark/`.

## 1. Held-out seasons, equal information (the football core)

**Setup.** The forward chain scores held-out 2024-2025, 28 weeks.
- Priors use earlier seasons only; current-season inputs use earlier weeks only.
- Since this commit, touchdown rates, the pass/rush split and the interception rate are also fitted on earlier seasons
  only (PIT-D4, fixed and mutation-tested).
- The old full-period fit was **not** materially optimistic: −0.0001 DK MAE, 95% interval [−0.0005, +0.0002].
  Earlier paired results stand.

**What neither side sees.** No injury reports and no market lines. Baselines are naive per-appearance means; no model,
no fitted constant.

| scoring | incumbent MAE | naive MAE | incumbent − naive (week-blocked 95%) |
|---|---|---|---|
| Unconditional: every pool player, 0 if he did not play (9,321) | 5.51 | 4.82 | **+0.68 [+0.60, +0.76]** (worse) |
| Conditional: players who played, no appearance discount (5,816) | 5.45 | 5.31 | **+0.14 [+0.04, +0.24]** (worse) |

**Reading the table.**
- The incumbent's football core does not beat "his average so far this season".
- Unconditionally it is worse at QB, RB, WR and TE alike.
- Conditionally, RB, WR and TE are tied, and QB is worse (+1.20).

**Decomposing the top projection decile** (where lineups are built):
- Given that the player played, the projection is 15% too high: WR +31%, RB +17%, QB +2%.
- In about 18% of these weeks the player did not play. The chain gives those weeks the same projection, because it
  cannot see injuries. That part is **NOT_EVALUABLE** without historical pregame injury and inactive archives
  (RES-010).

## 2. The real prelock forecasts, 2026 (what was actually produced before kickoff)

**Sample.** Four incumbent slates whose forecasts are prelock by both the artifact clock and the git clock: W4 Classic
Early, ATL@NO, PIT@CLE and TB@DAL. That is 445 skill-player games in 11 games (corrected from 19, BENCH-D4). Kickers and team defences are not scored
(no panel actuals).

**Top third of players by forecast** (n = 149; the strata are defined on the prediction, not the outcome):

| measure | value |
|---|---|
| Mean bias | +0.24 [−0.62, +1.12] (corrected interval, BENCH-D4); no detectable bias |
| Against the naive baseline (MAE) | **−1.20 [−1.62, −0.75]** (corrected interval, BENCH-D4): better. These forecasts had injury designations and inactives; the baseline did not. |
| 50/80/90% interval coverage | **43 / 71 / 81%**; PIT is heavy in both tails |

**On coverage.** The intervals lean too narrow. With 11 game clusters (corrected from 19, BENCH-D4), no predeclared margin and no equivalence test,
this is a **lean, not a finding** (BENCH-D2).

**One correction to my own first pass.** I had computed coverage on "players who played". That subset is selected on
the outcome, so it manufactures tail misses. It is kept only as a labelled diagnostic and is not evidence.

## 3. What is measurable, what is not, what improved, what got worse

| | |
|---|---|
| **Measurable now** | held-out player means (with the limits above); prospective 2026 skill-player means and intervals on 7 evaluable slates (4 incumbent, scored) |
| **Not measurable** | availability (RES-010); external rank (RES-011); tournament EV, ownership and field (no lawful prize tables or fields, FIELD-D1); held-out joint simulation calibration (no harness yet); W5 games beyond TB@DAL (RES-008) |
| **Improved this cycle** | measurement only. No model change was made or promoted. |
| **Worse** | nothing changed in production. The measurement shows the core allocation trails a naive baseline on equal information. That was always true; it is newly visible. |

## 4. Next, within existing authority (no promotion)

1. **Root-cause BENCH-D1** before proposing any change. Decompose the top-decile WR over-projection into volume
   (targets) and efficiency (points per target) on the same held-out rows.
2. **Pre-register one bounded challenger.** Blend each player's allocated volume with his naive per-appearance usage,
   on a fixed rule. Write the pre-registration before any run, with a paired held-out bar.
3. **Add K and DST to the prospective scorer**, and a held-out joint-calibration harness (QB–WR covariance, team
   totals).
4. **Score Week 6 onward prospectively** as each slate completes.

**Blocked, queued** in `coordination/RESEARCH_QUEUE.json`:
- RES-008: week-5 play-by-play
- RES-009: elevation records
- RES-010: historical pregame injury and inactive archives
- RES-011: vendor projection archives

None of these is in this checkout, and engineering has no network.
