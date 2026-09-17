# Production football-intelligence matrix, verified source by source

**Method.** Every row was checked by reading the hits, not by counting them. A
keyword count is worthless here and I have the scars: my first pass scored
**weather** as present in 9 production files because the regex `wind` matched
**wind**ow, and **personnel** as present in 33 because the word appears in
prose. Both are **ABSENT**. Every "IMPLEMENTED" below names the module and the
symbol that carries it.

**Scope.** `nfl/production/**` and `nfl/product/**` — what reaches a board.
Research-only work is listed in its own column and **does not count as
implemented**, because nothing in a board consumes it.

| # | area | production | research | evidence |
|---|---|---|---|---|
| 1 | **possessions** | **ABSENT** | partial | no symbol in production. `product/quality_gates.py` names a drive layer as something that "would be needed" |
| 2 | **drives** | **ABSENT** | — | every production hit is prose. `conservation.py:381` states outright that no drive layer is modelled |
| 3 | **pace** | **ABSENT** | partial | zero exact-token hits in production for `pace`, `sec_per_play`, `plays_per` |
| 4 | **PROE** | **ABSENT** | partial | zero production hits |
| 5 | **score-state pass rate** | **ABSENT** | partial | zero production hits for `score_diff`, `win_prob`, `game_script` |
| 6 | **opponent-adjusted off/def** | **ABSENT** | **ABSENT** | zero hits anywhere in the tree for `opponent_adj`, `def_adj`, `sos`, `strength_of`. Not started |
| 7 | **pass/rush matchup strength** | **ABSENT** | minimal | the one production hit is `seeds.py` prose about matchup-keyed seeds |
| 8 | **EPA / success rate** | **ABSENT** | partial | zero exact-token hits in production |
| 9 | **pressure / sacks** | **APPROXIMATION** | partial | sacks are a modelled **outcome** — `qb_room_v2.KINDS = ('sack','scramble','attempt')`, a per-dropback branch. Pressure as a **predictor** is absent: zero hits for `pressure`, `sack_rate`, `blitz` |
| 10 | **explosive plays** | **ABSENT** | partial | the single production hit is `rushing_conversion.py` saying the model **discards** the explosive component |
| 11 | **red zone** | **PARTIAL** | yes | real: `team_volume/team_rz_carries` is drawn and sealed, `eligibility.td_layer = 'td_red_zone'`, `appearance_model` carries `rz_targets`/`rz_carries`/`team_rz_rush`. No red-zone **conversion** layer |
| 12 | **weather / venue** | **ABSENT** | partial | zero real hits. My first pass scored 9 — `wind` inside `window` |
| 13 | **coaching / scheme** | **PARTIAL** | yes | real and load-bearing: `team_volume_v1.coaches()` reads `schedules.home_coach/away_coach`, and `coach_prior` is the **selected estimator for 3 of the 5 team-volume metrics**. Scheme itself is absent |
| 14 | **OL / DL** | **ABSENT** | **ABSENT** | zero hits anywhere for `pass_block`, `run_block`, `o_line`, `pff`. Not started |
| 15 | **personnel** | **ABSENT** | partial | one production hit, `panel_2026w1.py`, and it records that per-play personnel data "exists only" upstream — a note of absence, not a feature |
| 16 | **routes (routes run)** | **ABSENT** | partial | every production hit is a docstring saying the model works "on route participation, **not routes run**" |
| 17 | **route participation** | **APPROXIMATION** | yes | `participation_prior.py`, `SPEC_VERSION = 'participation-s2-ewma_hl2-frozen-1'` — an **EWMA of historical target share**, declared as a proxy for route participation. It is not observed participation |
| 18 | **player-specific efficiency** | **PARTIAL** | yes | per-player donor pools exist (`qb_room_v2` two-stage donor resample; RC1 receiving conversion). Governance on RC1 is `SIGNAL_WEAK` with a declared `CALIBRATION_DEFECT`, and RB rushing conversion is `RUSHING_CONVERSION_CONTROL_UNDEFINED` |
| 19 | **shared game-state coupling** | **PARTIAL** | yes | `team_volume_v1` couples the two clubs' volume draws — `coupling_scores`, `coupling_rho`, `coupled_index`, `assert_coupling_is_declared`. That is **team-volume coupling only**. `production/joint.py`, which exists to reconcile player draws to the shared team game, is **UNWIRED** — imported by research only |
| 20 | **TD correlation** | **ABSENT** | **ABSENT** | zero hits for `td_corr`, `joint_td`, `td_depend`. `board.touchdown.basis` states anytime-TD is taken as "the fraction of draws with at least one scoring play, summed within each draw rather than multiplied across marginals" — within-draw dependence, not a modelled TD correlation |

## Tally

| verdict | n | areas |
|---|---|---|
| **IMPLEMENTED** | **0** | none |
| **PARTIAL** | 4 | red zone, coaching, player efficiency, shared game-state coupling |
| **APPROXIMATION** | 2 | pressure/sacks, route participation |
| **ABSENT** | 14 | possessions, drives, pace, PROE, score-state pass rate, opponent-adjusted, pass/rush matchup, EPA/success, explosive, weather/venue, OL/DL, personnel, routes run, TD correlation |

**Not one of the twenty is fully implemented in production.** Four are partial,
two are approximations standing in for the real quantity, and fourteen are
absent.

**The audit's "22 of 28 absent" is the right order of magnitude.** On this
twenty-area list the count is 14 absent outright and 16 absent-or-approximated,
and **zero** fully implemented. I did not reproduce its 28-area list, so I
neither confirm nor dispute the exact figure — I report what I measured.

## The one that matters most, restated

**Areas 6, 7 and 14 are absent from research as well as production.** Opponent
adjustment, matchup strength and line play have not been started anywhere.
Everything else has at least a research footing. **The engine is matchup-blind
in production and there is no research asset to wire up** — so that work is a
build, not an integration, and should be estimated as one.

**V2 NOT YET EARNED**
