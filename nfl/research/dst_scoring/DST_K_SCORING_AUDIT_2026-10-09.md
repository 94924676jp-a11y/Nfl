# DST and kicker scoring audit, 2026-10-09

SHADOW ONLY. No production file is changed; nothing is promoted. Development data (two Showdown games, one
eight-game Classic slate), exploratory. Machine-readable twin: `DST_K_SCORING_AUDIT_2026-10-09.json`.
Branch `claude/dst-scoring-research` from `a3929144`, python3.12.

## What was asked

The owner ruled (2026-10-09) that the event-consistent-worlds repair is not promoted. Separately, the incumbent
publishes non-integer DraftKings DST scores in most worlds, while real DST scores are always integers. Find out why
(an accounting error, an expected value used as a realised score, or something else), design a bounded correction
that does not use the failed event simulator, and audit the kicker the same way.

## Root cause: an expected-value anchor applied to a score that was already realised

The simulator's own DST draw is an integer in **100%** of worlds, on every slate measured. The non-integers are
created afterwards, in one step:

- `nfl/tools/classic_slate_run.py:150` `anchor_means`: `out[k] = [x * f for x in v]`, with `f = projection / simulated mean`.
- Showdown calls it on the DST draws at `nfl/tools/showdown_slate_run.py:113-114`.
- Classic calls it at `nfl/tools/classic_slate_run.py:276-277` on everything that is not a skill player (`# DST: no stat line`).

Multiplying an integer DK score by 0.5085 gives a number that is not a DK score. This is an **expected value
(the projection) imposed on a realised score**, not an accounting error in the components. These are NOT the
cause: `nfl/sim/dst.py:242-254` (`DstModel.draw_components`: integer tier plus integer historical tuples),
`nfl/sim/game.py:323-324` (stores that integer draw) and `nfl/product/dk_scoring.py` (pure adapters).

Evidence: on both Showdown slates, published = raw x one factor, to within 3.6e-15 for every DST. The Classic
Week-5 research run was replayed (`measure_classic.py`): all 266 published draws were reproduced exactly (max
|diff| 0.0), and the raw draw equals the tier plus components for all 16 DSTs.

## Per-stage measurements

S0 = raw simulator draw. S1 = published draw after the anchor step (what the optimizer scored). Mean is DK
points per world, 2,000 worlds; the Monte Carlo standard error of a mean is about 0.1.

| slate | DST | projection | S0 mean | S0 non-integer | anchor factor | S1 mean | S1 non-integer |
|---|---|---|---|---|---|---|---|
| TB@DAL W5 | DAL | 3.91 | 7.68 | 0% | 0.5085 | 3.91 | 97.3% |
| TB@DAL W5 | TB | 4.31 | 3.63 | 0% | 1.1867 | 4.31 | 92.1% |
| ATL@NO W4 | NO | 6.55 | 8.62 | 0% | 0.7599 | 6.55 | 98.2% |
| ATL@NO W4 | ATL | 5.61 | 6.47 | 0% | 0.8674 | 5.61 | 95.5% |
| Classic W5 | 16 DSTs | 3.55-8.42 | 5.14-8.92 | 0% | 0.563-1.338 | = projection | 94.7%-98.2% |

The anchor does more than create fractions. It also shrinks or stretches the whole distribution. DAL's SD goes
from 5.91 to 3.00 and its P(>= 15) from 12.95% to 0.35%; TB is stretched to a minimum of -4.75, which no DST can
score. A rescale keeps P(<= 0) fixed and nothing else.

**Kicker.** The published Showdown kicker draws are integers in 100% of worlds. I re-drew all four with
`kicker_world.draw` in the build's own random-number order (ATL@NO under its point-in-time manifest) and matched
every world exactly. Their components, re-scored through `dk_scoring.kicker_points`, equal the published draw in
every world. Showdown does not anchor kickers (`showdown_slate_run.py`, "LEFT AS DRAWN"). Classic would rescale a
kicker row through the same `anchor_means` call, but Classic DK has no kicker and the W5 projection carries no K
row, so no non-integer kicker has been published. **No kicker scoring defect was found.** Two kicker-adjacent
findings are recorded and not fixed:

- In 14-19% of worlds the kicker's points plus the offensive-touchdown points (6·TD + XP + 3·FG) exceed the club's
  rounded score. In 3.5-4.3% of worlds 6·TD alone exceeds it. The cause is upstream: the club's touchdown count is
  inverted from continuous club points with noise (`game.py`), and kicker_world's remainder can then be negative
  (12-19% of worlds). This is club-score accounting, which this bounded fix keeps by design.
- The kicker point projection (`kicker_model`, which charges -1 for a miss) and the in-world draw (rule A, a miss
  scores 0) still disagree: Aubrey 10.66 vs 9.25, McLaughlin 8.37 vs 7.98, Carlson 8.26 vs 8.61, Folk 8.92 vs 7.87.
  This was already recorded in `kicker_world.MISS_RULE`.

**Secondary DST findings in the incumbent** (TB@DAL and ATL@NO):

- Three tier conventions are applied to the same continuous points. `dst.tier` floors (`lo <= p < hi`, line 70).
  `dk_scoring.dst_points` on a non-integer behaves like a ceiling (`p <= ub`, line 136). `dst_model.pa_expectation`,
  the projection, rounds (`+-0.5`, line 188). On these slates, floor and rounding give different tiers in 5.7-7.6%
  of worlds, and floor raises the mean tier by 0.10-0.15 DK. The continuous opponent score lies in (0, 1) in up to
  1.1% of worlds, and the floor convention scores those as shutouts (+10).
- Interceptions are not tied to the opposing QB. The DST's takeaways come from a historical tuple, and the QB's
  interceptions are drawn separately by `efficiency_worlds`. The QB throws more interceptions than the DST has
  takeaways in **15-27%** of worlds (Classic: 17-25%).
- The repository's two DST definitions miss some return touchdowns. `dst.py:104` (td_team == defteam) and
  `dst_model.py:120` (td_team != posteam) both drop kick-return TDs, because nflfastR makes the receiving club
  posteam on a kickoff. Measured over 2021-2025: 0.134 defensive/return TDs per club-game against dst_model's
  league 0.109. Separately, `dst_model.py:139` counts punt blocks only: 0.018 blocked kicks per game against 0.072
  when field-goal and extra-point blocks are included. Together these understate DST projections by roughly
  0.15 + 0.11 DK per game. Not fixed here, because those are production artifacts.

## DraftKings rules: what the repository implements

`dk_scoring.dst_points` scores: sack +1, interception +2, fumble recovery +2, safety +2, blocked kick +2, defensive
or return TD +6, two-point return +2, and points-allowed tiers 0: +10, 1-6: +7, 7-13: +4, 14-20: +1, 21-27: 0,
28-34: -1, 35+: -4. These match the rules in the request. The function takes `points_allowed` as given:

- The repository's postgame grade uses **rule A**, the opponent's final score (`showdown_postgame.py`, `dk_A`).
- **Rule B** (`dk_B`) subtracts 6 per opponent return or defensive touchdown.
- On 2021-2025 history, rule B raises the mean DST score by +0.145 (6.64 vs 6.49).

The worlds' club points are a continuous draw calibrated to final scores, so they correspond to rule A. **Not
verified here (no network):** whether DraftKings excludes points scored against the DST's own offence (pick-sixes,
fumble returns) from points allowed. The networked agent should read DK's published NFL Classic and Showdown rule
text and say which of A or B it is. Kicker rule A (a missed FG scores 0) is what `kicker_world` and the postgame
grade implement.

## The bounded fix: shadow module `nfl/sim/dst_k_event_scoring.py` (ENABLED = False)

What it keeps unchanged from the incumbent: every club score, every skill-player draw and stat line (including
each QB's per-world interceptions), and every kicker draw. It replaces only the DST draw, rebuilding it per world
from integer events:

- **Points allowed:** the opponent's simulated club points in the same world, rounded half-down to an integer. This
  is the projection's own `pa_expectation` convention, so the projection and the worlds now agree on what a bucket is.
- **Interceptions:** the sum of the opposing QBs' simulated interceptions in that world. This is an exact identity.
- **Sacks:** negative binomial. Its mean is the club's projected rate times a band ratio. Its dispersion k = 24.8 is
  measured from history after conditioning on club-season and points-allowed band, so the band is not counted twice.
- **Fumble recoveries, defensive/return TDs, safeties, blocked kicks:** Poisson with mean = club rate x band ratio.
  All four have an after-band variance/mean between 0.94 and 1.01 in history.
- **Where the inputs come from:** the club rate is the DST projection row's own `event_items` divided by the DK
  weight, so it is club-specific. The band ratio is E[component | points-allowed band] / E[component], from
  2021-2025 play-by-play (`history.py`), using the same bands as `dst.py`. Every number is a count or a ratio of
  counts. Nothing is fitted.
- **Score:** DK points = `dk_scoring.dst_points` of those integers, world by world.

**Mean anchoring: an owner decision, not made here. Both arms are reported, from the same events and seed:**

- **EVENTS.** The mean is whatever the events give. It departs from the projection in three ways:
  - Points allowed: the worlds' opponent-score distribution differs from the projection's league residual
    spread (sd 9.9).
  - Interceptions now follow the opposing QB's simulated rate, not the defence's own rate. This is the largest term
    for DAL (+1.07), NYJ (+1.14) and TEN (+0.75).
  - Band effects on the free components.

  The decomposition for each DST is in the JSON.
- **PROJECTION.** One non-negative multiplier m on the free components' rates (sacks, fumble recoveries, TDs,
  safeties, blocked kicks) is solved in closed form so the expected mean equals the projection. Points allowed and
  interceptions are never moved. If the projection is below what those two alone give, m = 0 and the module reports
  `PROJECTION_MEAN_UNREACHABLE` rather than forcing the mean. All 20 DST-slates were reachable: m runs from 0.43
  (DAL, NYJ) to 1.25 (NYG). The PROJECTION arm has its own weakness: m = 0.43 means DAL's sacks are drawn at 43% of
  their measured club rate, to absorb a disagreement that actually sits in points allowed and interceptions.

| slate | DST | projection | published (S1) | FIX EVENTS | FIX PROJECTION | m |
|---|---|---|---|---|---|---|
| TB@DAL | DAL | 3.91 | 3.91 | 5.50 (+1.60) | 3.89 (-0.02) | 0.43 |
| TB@DAL | TB | 4.31 | 4.31 | 3.59 (-0.72) | 4.30 (-0.00) | 1.21 |
| ATL@NO | NO | 6.55 | 6.55 | 7.93 (+1.38) | 6.50 (-0.05) | 0.69 |
| ATL@NO | ATL | 5.61 | 5.61 | 5.63 (+0.02) | 5.59 (-0.02) | 0.98 |
| Classic | GB, CHI, MIA, CIN, NYJ, CLE, TEN, HOU | 3.55, 6.96, 3.78, 8.07, 4.96, 7.25, 4.62, 8.42 | same | 3.65, 6.22, 4.58, 8.97, 7.12, 7.08, 5.92, 9.21 | 3.51, 6.88, 3.77, 8.08, 4.98, 7.26, 4.61, 8.39 | 0.94, 1.17, 0.67, 0.83, 0.43, 1.05, 0.62, 0.85 |
| Classic | PIT, IND, NE, LV, NO, MIN, WAS, NYG | 7.12, 4.97, 6.60, 6.52, 5.61, 8.06, 5.80, 6.02 | same | 6.70, 5.12, 7.29, 6.07, 6.80, 7.95, 6.34, 5.24 | 7.07, 4.89, 6.51, 6.58, 5.57, 8.04, 5.75, 6.12 | 1.08, 0.94, 0.84, 1.10, 0.72, 1.01, 0.84, 1.25 |

**Kicker fix:** none needed for Showdown. `kicker_dk_from_components` re-scores kicker_world's components through
`dk_scoring.kicker_points`, so the identity is checked by the platform adapter. Classic should exclude kickers from
`anchor_means` if a classic projection ever carries one (promotion item).

**Downstream:** replacing the DST draws leaves every skill-player and kicker draw byte-identical. This was checked
on 49 + 30 + 266 players. **No skill player moves.** The DST mean change per slate is in the table above
(published -> fix).

## Tests

`nfl/tests/test_dst_k_event_scoring.py` is written in the repository harness style. Under `run_suite.py --modules`
it gives 11 functions, **61 checks, 0 failing**. It checks:

- `ENABLED` is False, and no production module references the shadow module.
- The rounding convention equals the projection's bucket edges.
- The incumbent anchor is reproduced as the cause: raw is integer, published is more than 90% non-integer, and
  published = raw x one factor.
- On TB@DAL, under both arms:
  - every world score is a valid DK value;
  - every world score equals `dst_points` of its own components;
  - the tier equals the tier of the opponent's club points in that world;
  - interceptions equal the opposing QBs' interceptions in that world.
- The PROJECTION arm's mean is within 4 MCSE of the projection.
- Skill draws are byte-identical after the DST is replaced.
- An unreachable projection is reported, not forced.
- Seeded violations are refused by name: a rescaled world, half points, a score below -4, non-integer or
  mis-sized interceptions, non-finite opponent points, a missing rate, an unknown kicker band.
- `kicker_world.draw` equals `kicker_points` of its components.
- Every fixed DST's SD is at or below the unconditional historical SD.

Ran in the same `run_suite.py` invocation (5 modules, 202 checks):

- `test_kicker_world`, `test_kicker_reaches_every_consumer`, `test_event_consistent_worlds`: 0 failing.
- `test_kicker_resolution`: 1 failing, "all 32 clubs resolve a kicker at 2026 week 2", NYJ
  `KICKER_ELIGIBILITY_DISAGREES_ACROSS_VINTAGES`. That module does not import anything added here. It is a
  data-vintage disagreement, recorded and not investigated.

## History comparison (2021-2025 regular season, 2,718 club-games, rule A)

History is unconditional, so a single matchup's distribution should be narrower than it, not equal to it. Slate
rows are the average over 20 DST-slates of each per-DST statistic.

| source | mean | sd | P(DK <= 0) | P(DK >= 15) | non-integer |
|---|---|---|---|---|---|
| history | 6.49 | 5.77 | 12.1% | 9.8% | 0% |
| incumbent raw (S0) | 6.90 | 5.74 | 10.7% | 11.4% | 0% |
| incumbent published (S1) | 5.94 | 5.02 | 10.7% | 6.4% | 96.2% |
| FIX EVENTS | 6.35 | 4.96 | 10.1% | 7.5% | 0% |
| FIX PROJECTION | 5.91 | 4.81 | 11.1% | 6.2% | 0% |

History component means per club-game: sacks 2.41, interceptions 0.756, fumble recoveries 0.499, defensive/return
TDs 0.134, safeties 0.024, blocked kicks 0.072, two-point returns 0.002.

The fix restores integer support and keeps each matchup's SD below the unconditional one. Both fix arms put less
mass at 15 or more than history (7.5% and 6.2% against 9.8%), and so does the published incumbent (6.4%). Two
development games and one slate cannot say whether that is matchup conditioning or a missing joint tail. The
incumbent's historical tuples drew sacks and takeaways together and gave 11.4%.

| kicker | mean | sd | P(<= 0) | P(>= 15) | non-integer |
|---|---|---|---|---|---|
| history | 8.21 | 4.56 | 2.3% | 9.1% | 0% |
| Aubrey DAL / McLaughlin TB | 9.25 / 7.98 | 4.88 / 4.65 | 0.25% / 3.75% | 14.7% / 9.8% | 0% |
| Carlson NO / Folk ATL | 8.61 / 7.87 | 4.68 / 4.97 | 1.5% / 5.75% | 11.6% / 10.3% | 0% |

The fixed kicker is identical to the incumbent.

## Promotion requirements (none met here)

1. Owner decision on the DST mean: EVENTS or PROJECTION. If PROJECTION is chosen, a decision on whether m < 1 for
   a defence whose gap sits in interceptions and points allowed is acceptable.
2. Wire the shadow behind a declared flag in `showdown_slate_run` and `classic_slate_run` in place of
   `anchor_means` for DST. Exclude kickers from `anchor_means` in Classic.
3. Full regression via `nfl/tests/run_suite.py` (normal, `--reverse`, `--shuffle`) of every module that consumes
   worlds: showdown_portfolio, world_accounting_check (add `DST_DK_FROM_COMPONENTS` and an INT identity check for
   the incumbent arm), postgame graders, classic_slate_run, candidates. Not run here; only the 5 modules above were.
4. The networked agent to confirm DraftKings' points-allowed definition (rule A or rule B).
5. Decide whether to correct the return-TD and blocked-kick undercounts in `dst_model` and `dst.py`. Those are
   production artifacts, and the club rates this fix reads inherit the undercount.
6. A forward, pre-registered check on new slates. Two Showdown games and one Classic slate are development data.

## Reproduce

```
PYTHONPATH=<numpy/pandas> python3.12 nfl/research/dst_scoring/history.py
PYTHONPATH=<numpy> python3.12 nfl/research/dst_scoring/measure_showdown.py nfl/dfs/salaries/showdown_tb_dal/OFFICIAL nfl/research/dst_scoring/measurements/TB_DAL_2026W5.json
NFL_PIT_MANIFEST=nfl/warehouse/pit_manifests/PIT_MANIFEST.ATL_NO_2026W4.1294f0dc638d95c9.json PYTHONPATH=<numpy> python3.12 nfl/research/dst_scoring/measure_showdown.py nfl/dfs/salaries/showdown_atl_no/RW_INACTIVES_CHARTFIX nfl/research/dst_scoring/measurements/ATL_NO_2026W4.json
PYTHONPATH=<numpy> python3.12 nfl/research/dst_scoring/measure_classic.py <main tree>/nfl/dfs/salaries/classic_early_2026W5/research_projection/final_2026-10-09/RESEARCH_STATE_2026W5 nfl/research/dst_scoring/measurements/CLASSIC_EARLY_2026W5.json <scratch>
PYTHONPATH=<numpy> python3.12 nfl/research/dst_scoring/compose.py <that RESEARCH_STATE_2026W5>
NFL_SUITE_PROGRESS=<scratch> PYTHONPATH=<numpy> python3.12 nfl/tests/run_suite.py --modules test_dst_k_event_scoring
```

The Classic research state is read from the main tree, read-only. It is not in this branch.
