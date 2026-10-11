# H3 pre-registration: production's depth and appearance table, measured on a consistent player universe

Written 2026-10-11, before any 2026 week-6 kickoff (first lock 17:00 UTC) and before any week-6 outcome exists.
The commit time of this file is authoritative.

Status: **PRE-REGISTERED, SHADOW ONLY.**
- No production change and no promotion.
- No market input; nothing from FantasyCruncher.
- This is a separate study. It does not modify, merge with or re-score H1, AP-1, RC-1, APPEAR-SUCCESSOR-1 or
  H-TAIL. Each of those keeps its own candidate, weeks, metric and decision rule.

## 1. Hypotheses (defined against predictions, never outcomes)

**H3.** Production's depth table (`proj_v1.depth_shares(panel, position_index())`, `nfl/tools/proj_v1.py:1118`) counts
only players present on the 2026 rosters. It therefore understates how often depth players appear (L4,
`L4_FINDING_2026-10-11.md`).

Prediction, among players with a recorded DK actual:

- **H3a, top.** The top quartile of each position's locked projection is over-projected under the incumbent (ratio
  of projected to scored above 1). Under the candidate, `|log ratio|` is smaller.
- **H3b, depth.** Players whose **pregame** allocation depth rank is ≥ 2 (RB, TE) or ≥ 3 (WR) are under-projected
  under the incumbent (ratio below 1). Under the candidate, `|log ratio|` is smaller.
- **H3c, error.** The candidate does not worsen per-player absolute DK error.

## 2. Candidate (frozen)

Identical to the incumbent except for the position map given to `depth_shares`:

```text
roster     = player_prior.position_index()
pos_map, _ = forward_chain.positions_for_chain(panel, roster)
aug        = roster, plus, for each player absent from it, his inferred position from pos_map
             for his latest season in the panel
depth      = proj_v1.depth_shares(panel, aug)        # nothing else is changed
```

- `group_shares`, `bonus_rates`, `int_rate` and the TD rates keep the roster-only map. Changing them is out of scope.
- Reference implementation: `shadow_w4.py`, arm `DEPTHFIX`.
- Known weakness, declared now: usage cannot distinguish a tight end from a receiver, so inferred tight ends enter
  the WR table. A candidate built on historical rosters (OUT-038) is a different candidate, and needs its own
  pre-registration.

## 3. Data roles

| role | data | status |
|---|---|---|
| development | 2022-2025 forward-chain sensitivity (independent reviewer); 2026 week-4 early Classic paired shadow | **seen.** Exploratory only; cannot judge H3 |
| **confirmatory** | every 2026 regular-season early Classic main slate and every Sunday or Monday showdown, **week 6 through week 11 inclusive** | **untouched** |

## 4. How each slate is run (paired, identical point-in-time inputs)

1. **Input.** The production pregame state frozen before lock (`DK_<slate>_*_STATE*.json`), as committed with its
   capture clock. A slate without a frozen pre-lock state is **EXCLUDED**, with the reason recorded. It is never
   substituted.
2. **Same run, same commit.** Both arms run in the same process tree, at the same repository commit, with the same
   market arm production used. Results are written only to a scratch directory.
3. **Panel.** Truncated to 2026 weeks strictly before the slate's week.
4. **Point-in-time sealing.**
   - When the shadow runs after lock, it runs under a `point_in_time` manifest with cutoff = the slate's first
     lock (`NFL_PIT_MANIFEST`).
   - If no manifest can be sealed, the slate is reported **UNSEALED** and counted only in a separate sensitivity
     table, never in the verdict.
5. **Reproduction check, reported but not gating.** The incumbent arm's projection against production's locked
   file: number of rows differing by more than 0.01, and the maximum difference.
6. **Scoring.** DK actuals from the graded postgame table. Population: QB/RB/WR/TE with a recorded actual.

## 5. Metrics and decision rules (frozen)

Uncertainty for every metric: a cluster bootstrap by club-week, B = 4,000, seed 20261011.

**Sample floor.** At least **150 club-weeks**, Classic and showdown combined, counting a club-week once. Below that
the verdict is **NOT_YET_EVALUABLE**, never PASS.

| endpoint | definition | required for SHADOW-CONTINUE |
|---|---|---|
| H3a | paired difference in `abs(log(Σproj / Σactual))` over the top quartile per position (q75 = order statistic at floor(0.75 n) of that slate's projections for the position) | upper 95 % bound < 0 |
| H3b | the same over pregame depth rank ≥ 2 (RB, TE) or ≥ 3 (WR). The rank is the allocator's `depth_rank_in_group` in the incumbent arm's output. | upper 95 % bound < 0 |
| H3c | paired change in mean absolute DK error per player, all scored players | upper 95 % bound ≤ +1 % of the incumbent MAE |
| harm, by position | % change in MAE, QB/RB/WR/TE | each one-sided 95 % upper bound ≤ +2 %, Holm-adjusted across the four positions |
| harm flag | any position whose one-sided 95 % **lower** bound of the % change is > 0 | forces REJECT |
| reversal | the H3a or H3b ratio under the incumbent lies entirely on the other side of 1 (interval) | verdict REVERSED for that endpoint |

- **Verdicts:** SHADOW-CONTINUE (every row met), REJECT, REVERSED, or NOT_YET_EVALUABLE.
- **Promotion is not decided here.** It is a separate owner decision. It would also require the full `run_suite.py`
  regression with no new failure, and a separate commit for any harness change (validation and production are never
  changed together).

## 6. Reported, not decided on

- **Classic against showdown,** separately: the same endpoints per contest type.
- **Distribution.** Per-player p10/p90 coverage of actuals in each arm, and the change in each player's draw SD
  (needs a re-simulation per arm; if not run, say so).
- **Portfolio decisions.** A paired rebuild with `nfl/opt/classic_portfolio.py`, with the same seed, ownership and
  constraints:
  - lineups shared;
  - exposure shifts;
  - realised DK points;
  - field percentile per archived contest.

  With fewer than 10 slates this is descriptive only. A predeclared harm flag is raised if candidate lineups score
  lower on a majority of slates.

## 7. What voids this pre-registration

- Any change to the candidate, the weeks, the endpoints or the bars after the first confirmatory slate is graded.
- Any use of a week-6-or-later outcome in building either arm.
- Running either arm on inputs the other arm did not receive.

Each voids H3. A changed candidate needs a new pre-registration.

## 8. Dependency on the other agent (needs network)

- The frozen pre-lock state of each confirmatory slate.
- Graded DK actuals for each slate.
- The usage panel extended through each slate's previous week.
- **OUT-038 (historical rosters):** not needed for H3; needed for any successor.
