# ATL @ NO Showdown -- PRE-LOCK board (RW_INACTIVES)

**NOT_READY** -- blockers: INACTIVES_FROM_SECONDARY_SOURCE_NOT_OFFICIALLY_VERIFIED (SECONDARY_AGGREGATOR_RELAYED (RotoWire lineups page, screens)

## FOOTBALL
- official inactives: `['Malcolm DeWalt IV', 'Jared Ivey', 'Robert Longerbeam', 'Ethan Onianwa', 'Cooper Rush', 'Jack Strand', 'Kaden Elliss', 'Noah Fant', 'Carl Granderson', 'Anfernee Jennings', 'Christen Miller', 'Decamerion Richardson', 'Zach Wilson']`
- starters: `{'Michael Penix Jr.': 'ATL', 'Tyler Shough': 'NO'}` (PUBLIC_DEPTH_CHART_AND_SNAPS_CITED)
- state counts: `{'PROJECTED': 29, 'INACTIVE': 25, 'ZERO_OPPORTUNITY': 2}`
- football sanity: `{"state": "PASS", "code": "FOOTBALL_SANITY_PASS", "detail": "56 rows, 2 clubs, no football contradiction", "flags": null}`
- **SHOWDOWN_COHERENCE_WARNING** (measured, not fixed tonight): `{"ours_by_team": {"NO": {"corr_team_td_vs_team_off_dk": 0.539, "corr_team_points_vs_team_off_dk": 0.477}, "ATL": {"corr_team_td_vs_team_off_dk": 0.57, "corr_team_points_vs_team_off_dk": 0.482}}, "ours_corr_home_points_vs_away_points": 0.081, "ours_corr_home_off_dk_vs_away_off_dk": 0.158, "history_2021_2025": {"corr_team_td_vs_team_off_dk": 0.811, "corr_team_points_vs_team_off_dk": 0.763, "corr_home_points_vs_away_points": -0.038, "corr_home_off_dk_vs_away_off_dk": 0.181, "team_games": 2718}, "FINDING": "DEFECT-COHERENCE (measured 2026-10-05): within a simulated world, a team's offensive DK points track its touchdowns and points far more loosely than in 2021-25 games (see the numbers). The TD identity holds, so this is not broken accounting: yardage/receptions are drawn too independently of scoring. Effect: same-team boom-together is understated, so stacks are undervalued in the top tail. NOT fixed tonight (no validated fix before lock; the sealed football model is preserved); registered as the first post-lock football item."}`

| player | team | pos | salary | state | availability | desig | depth | mean | p90 | P(0) |
|---|---|---|---|---|---|---|---|---|---|---|
| Bijan Robinson | ATL | RB | 11800 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 1 | 26.14 | 38.83 | 0.0 |
| Chris Olave | NO | WR | 10800 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 1 | 25.63 | 39.74 | 0.0 |
| Tyler Shough | NO | QB | 9600 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 1 | 22.4 | 33.34 | 0.0 |
| Drake London | ATL | WR | 10000 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 1 | 20.58 | 33.98 | 0.001 |
| Juwan Johnson | NO | TE | 7400 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 1 | 16.18 | 27.86 | 0.0 |
| Michael Penix Jr. | ATL | QB | 9000 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 1 | 15.42 | 24.0 | 0.0 |
| Alvin Kamara | NO | RB | 7000 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 1 | 13.62 | 22.13 | 0.0 |
| Devaughn Vele | NO | WR | 7800 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 2 | 11.11 | 19.93 | 0.001 |
| Daniel Carlson | NO | K | 4800 | PROJECTED | UNKNOWN_ACTIVE_STATE |  |  | 8.53 | 15.0 | 0.019 |
| Nick Folk | ATL | K | 5400 | PROJECTED | UNKNOWN_ACTIVE_STATE |  |  | 8.22 | 15.0 | 0.045 |
| Saints | NO | DST | 4200 | PROJECTED | UNKNOWN_ACTIVE_STATE |  |  | 6.55 | 12.74 | 0.054 |
| Falcons | ATL | DST | 3600 | PROJECTED | UNKNOWN_ACTIVE_STATE |  |  | 5.61 | 12.74 | 0.122 |
| Kyle Pitts Sr. | ATL | TE | 5800 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 1 | 5.1 | 10.07 | 0.015 |
| Brian Robinson Jr. | ATL | RB | 3800 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 2 | 4.8 | 9.56 | 0.007 |
| Jahan Dotson | ATL | WR | 3000 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 2 | 4.06 | 8.66 | 0.045 |
| Kendre Miller | NO | RB | 5000 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 2 | 3.67 | 8.06 | 0.013 |
| Austin Hooper | ATL | TE | 2800 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 1 | 3.54 | 8.25 | 0.141 |
| Bryce Lance | NO | WR | 1800 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 3 | 2.75 | 6.69 | 0.178 |
| Olamide Zaccheaus | ATL | WR | 2000 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 3 | 2.39 | 6.0 | 0.172 |
| Treyton Welch | NO | TE | 200 | PROJECTED | UNKNOWN_ACTIVE_STATE |  |  | 1.59 | 4.82 | 0.403 |

## PORTFOLIO
### 196285137 (150 entries)
- objective `{'m': 3, 'value': 2.9815, 'MEANING': 'E[min(entries at the first-place proxy, m)] per world'}`; proxy coverage 0.9995; method GREEDY_THEN_1SWAP_POLISH; polish `{'rounds': 15, 'lineups_changed': 14, 'objective_greedy': 2.973, 'objective_final': 2.9815, 'coverage_greedy': 1.0, 'coverage_final': 0.9995}`
- distinct captains 16; effective hypotheses 68.3; shared players between pairs `{'max': 5, 'distribution': {0: 53, 1: 1253, 2: 4257, 3: 4066, 4: 1409, 5: 137}}`
- captain exposure `{'Bijan Robinson': 21.3, 'Chris Olave': 18.7, 'Drake London': 14.7, 'Tyler Shough': 10.7, 'Juwan Johnson': 10.0, 'Daniel Carlson': 4.7, 'Alvin Kamara': 4.0, 'Devaughn Vele': 4.0, 'Falcons': 3.3, 'Michael Penix Jr.': 2.0, 'Brian Robinson Jr.': 1.3, 'Jahan Dotson': 1.3, 'Kyle Pitts Sr.': 1.3, 'Saints': 1.3, 'Kendre Miller': 0.7, 'Nick Folk': 0.7}`
- player exposure `{'Tyler Shough': 65.3, 'Chris Olave': 64.0, 'Bijan Robinson': 63.3, 'Drake London': 51.3, 'Juwan Johnson': 46.0, 'Alvin Kamara': 45.3, 'Michael Penix Jr.': 40.0, 'Daniel Carlson': 30.7, 'Falcons': 28.0, 'Saints': 27.3, 'Nick Folk': 27.3, 'Devaughn Vele': 23.3, 'Treyton Welch': 18.0, 'Brian Robinson Jr.': 14.0, 'Jahan Dotson': 13.3}`
- RELAXATION: level 2; rungs L0 caps {'player': 75, 'captain': 45, 'overlap': 4} built 134/150 EHC 73.5; L1 caps {'player': 75, 'captain': 45, 'overlap': 5} built 142/150 EHC 71.9; L2 caps {'player': 98, 'captain': 45, 'overlap': 5} built 150/150 EHC 66.1
  - above the original cap: `{'Chris Olave': {'n': 96, 'final_pct': 64.0, 'orig_cap_n': 75, 'orig_cap_pct': 50.0}, 'Bijan Robinson': {'n': 95, 'final_pct': 63.3, 'orig_cap_n': 75, 'orig_cap_pct': 50.0}, 'Tyler Shough': {'n': 98, 'final_pct': 65.3, 'orig_cap_n': 75, 'orig_cap_pct': 50.0}, 'Drake London': {'n': 77, 'final_pct': 51.3, 'orig_cap_n': 75, 'orig_cap_pct': 50.0}}`; captains `{}`
  - lineups not in the level-0 build: 107; clusters `{'by_origin': {'SWAP_POLISH': 14, 'RELAXATION': 93}, 'by_captain': {'Bijan Robinson': 19, 'Chris Olave': 17, 'Tyler Shough': 15, 'Drake London': 14, 'Juwan Johnson': 11, 'Devaughn Vele': 6, 'Alvin Kamara': 5, 'Falcons': 4, 'Daniel Carlson': 4, 'Michael Penix Jr.': 3, 'Jahan Dotson': 2, 'Kyle Pitts Sr.': 2, 'Saints': 2, 'Brian Robinson Jr.': 1, 'Kendre Miller': 1, 'Nick Folk': 1}, 'by_split': {'3-3': 33, '2-4': 31, '1-5': 20, '4-2': 20, '5-1': 3}, 'by_salary_band': {'49500-49900': 50, '49000-49400': 25, '48000-48900': 17, '50000': 15}}`
  - why: level 0 built 134/150: under a 75-entry player cap, a 45-entry captain cap and at most 4 shared players, the lawful pool near the top-tail runs out of lineups that avoid the core (Tyler Shough, Chris Olave, Bijan Robinson, Drake London)
  - effective hypotheses (rungs are GREEDY rebuilds, before the swap polish): last unfilled rung 71.9 -> filled rung 66.1; final polished portfolio 68.3
- salary-relief slots used: `{'Oscar Delp': 4, 'Kevin Austin Jr.': 4, 'Barion Brown': 5}`
### 196285160 (20 entries)
- objective `{'m': 2, 'value': 1.3865, 'MEANING': 'E[min(entries at the first-place proxy, m)] per world'}`; proxy coverage 0.8105; method GREEDY_THEN_1SWAP_POLISH; polish `{'rounds': 7, 'lineups_changed': 4, 'objective_greedy': 1.351, 'objective_final': 1.3865, 'coverage_greedy': 0.794, 'coverage_final': 0.8105}`
- distinct captains 6; effective hypotheses 15.0; shared players between pairs `{'max': 5, 'distribution': {1: 15, 2: 45, 3: 77, 4: 48, 5: 5}}`
- captain exposure `{'Chris Olave': 30.0, 'Drake London': 30.0, 'Bijan Robinson': 20.0, 'Juwan Johnson': 10.0, 'Tyler Shough': 5.0, 'Alvin Kamara': 5.0}`
- player exposure `{'Chris Olave': 65.0, 'Bijan Robinson': 65.0, 'Tyler Shough': 65.0, 'Juwan Johnson': 60.0, 'Drake London': 60.0, 'Alvin Kamara': 55.0, 'Treyton Welch': 50.0, 'Daniel Carlson': 40.0, 'Saints': 35.0, 'Michael Penix Jr.': 35.0, 'Falcons': 25.0, 'Nick Folk': 20.0, 'Bryce Lance': 10.0, 'Austin Hooper': 5.0, 'Olamide Zaccheaus': 5.0}`
- RELAXATION: level 2; rungs L0 caps {'player': 10, 'captain': 6, 'overlap': 4} built 17/20 EHC 14.3; L1 caps {'player': 10, 'captain': 6, 'overlap': 5} built 17/20 EHC 13.3; L2 caps {'player': 13, 'captain': 6, 'overlap': 5} built 20/20 EHC 15.1
  - above the original cap: `{'Chris Olave': {'n': 13, 'final_pct': 65.0, 'orig_cap_n': 10, 'orig_cap_pct': 50.0}, 'Bijan Robinson': {'n': 13, 'final_pct': 65.0, 'orig_cap_n': 10, 'orig_cap_pct': 50.0}, 'Juwan Johnson': {'n': 12, 'final_pct': 60.0, 'orig_cap_n': 10, 'orig_cap_pct': 50.0}, 'Tyler Shough': {'n': 13, 'final_pct': 65.0, 'orig_cap_n': 10, 'orig_cap_pct': 50.0}, 'Alvin Kamara': {'n': 11, 'final_pct': 55.0, 'orig_cap_n': 10, 'orig_cap_pct': 50.0}, 'Drake London': {'n': 12, 'final_pct': 60.0, 'orig_cap_n': 10, 'orig_cap_pct': 50.0}}`; captains `{}`
  - lineups not in the level-0 build: 10; clusters `{'by_origin': {'SWAP_POLISH': 3, 'RELAXATION': 7}, 'by_captain': {'Bijan Robinson': 4, 'Chris Olave': 2, 'Drake London': 2, 'Juwan Johnson': 1, 'Alvin Kamara': 1}, 'by_split': {'1-5': 4, '3-3': 4, '2-4': 2}, 'by_salary_band': {'49500-49900': 8, '50000': 1, '48000-48900': 1}}`
  - why: level 0 built 17/20: under a 10-entry player cap, a 6-entry captain cap and at most 4 shared players, the lawful pool near the top-tail runs out of lineups that avoid the core (Chris Olave, Bijan Robinson, Tyler Shough, Juwan Johnson)
  - effective hypotheses (rungs are GREEDY rebuilds, before the swap polish): last unfilled rung 13.3 -> filled rung 15.1; final polished portfolio 15.0
- salary-relief slots used: `{}`
### 196285161 (2 entries)
- objective `{'m': 1, 'value': 0.328, 'MEANING': 'E[min(entries at the first-place proxy, m)] per world'}`; proxy coverage 0.328; method GREEDY_THEN_1SWAP_POLISH; polish `{'rounds': 1, 'lineups_changed': 0, 'objective_greedy': 0.328, 'objective_final': 0.328, 'coverage_greedy': 0.328, 'coverage_final': 0.328}`
- distinct captains 2; effective hypotheses 2.0; shared players between pairs `{'max': 4, 'distribution': {4: 1}}`
- captain exposure `{'Chris Olave': 50.0, 'Drake London': 50.0}`
- player exposure `{'Chris Olave': 100.0, 'Juwan Johnson': 100.0, 'Treyton Welch': 100.0, 'Tyler Shough': 100.0, 'Bijan Robinson': 50.0, 'Daniel Carlson': 50.0, 'Drake London': 50.0, 'Alvin Kamara': 50.0}`
- RELAXATION: level 0; rungs L0 caps {'player': 2, 'captain': 2, 'overlap': 4} built 2/2 EHC 2.0
  - above the original cap: `{}`; captains `{}`
  - lineups not in the level-0 build: 0; clusters `{'by_origin': {}, 'by_captain': {}, 'by_split': {}, 'by_salary_band': {}}`
  - why: no relaxation needed: level 0 built 2/2
  - effective hypotheses (rungs are GREEDY rebuilds, before the swap polish): last unfilled rung None -> filled rung 2.0; final polished portfolio 2.0
- salary-relief slots used: `{}`
- **CPT Chris Olave** + Bijan Robinson, Daniel Carlson, Juwan Johnson, Treyton Welch, Tyler Shough -- $50000, mean 113.28, proxy 0.2145
- **CPT Drake London** + Alvin Kamara, Chris Olave, Juwan Johnson, Treyton Welch, Tyler Shough -- $50000, mean 110.29, proxy 0.1475

## FIELD (EXTERNAL_RESEARCH_SHADOW, UNVALIDATED)
- NOT_PROMOTED. Both field projections are EXTERNAL_RESEARCH_SHADOW and UNVALIDATED; the blend fits five unverified anchors better, which is not validation. Neither feeds the football or the production portfolio.
### FC_ONLY (sigma 0.6, anchor RMSE 13.75)
- 196285137: **65 lineup(s) contain a player this shadow field never rosters -- their dupe estimates are UNDERSTATED, not evidence of uniqueness**
- 196285137: dupes exact `{'mean': 25.7, 'max': 329.4, 'n_over_guardrail': 40, 'guardrail': 20}` product `{'mean': 21.41, 'max': 368.82}`; salary left `{'ours': {'0': 94, '500': 35, '1000': 13, '1500': 7, '2000': 1}, 'ours_mean': 465.0, 'shadow_field_mean': 1567.0}`; split `{'ours_pct': {'1-5': 15.3, '2-4': 32.0, '3-3': 35.3, '4-2': 14.7, '5-1': 2.7}, 'shadow_field_pct': {'1-5': 14.3, '2-4': 37.6, '3-3': 33.1, '4-2': 13.0, '5-1': 2.0}}`
- 196285160: **10 lineup(s) contain a player this shadow field never rosters -- their dupe estimates are UNDERSTATED, not evidence of uniqueness**
- 196285160: dupes exact `{'mean': 8.0, 'max': 65.9, 'n_over_guardrail': 1, 'guardrail': 20}` product `{'mean': 4.08, 'max': 17.31}`; salary left `{'ours': {'0': 19, '1000': 1}, 'ours_mean': 265.0, 'shadow_field_mean': 1567.0}`; split `{'ours_pct': {'1-5': 35.0, '2-4': 25.0, '3-3': 30.0, '4-2': 10.0}, 'shadow_field_pct': {'1-5': 14.3, '2-4': 37.6, '3-3': 33.1, '4-2': 13.0, '5-1': 2.0}}`
- 196285161: **2 lineup(s) contain a player this shadow field never rosters -- their dupe estimates are UNDERSTATED, not evidence of uniqueness**
- 196285161: dupes exact `{'mean': 0.0, 'max': 0.0, 'n_over_guardrail': 0, 'guardrail': 20}` product `{'mean': 0.0, 'max': 0.0}`; salary left `{'ours': {'0': 2}, 'ours_mean': 0.0, 'shadow_field_mean': 1567.0}`; split `{'ours_pct': {'1-5': 100.0}, 'shadow_field_pct': {'1-5': 14.3, '2-4': 37.6, '3-3': 33.1, '4-2': 13.0, '5-1': 2.0}}`
  - CPT/FLEX ownership (150): Tyler Shough 22.5/45.9; Bijan Robinson 21.2/44.3; Chris Olave 13.2/39.7; Kevin Austin Jr. 1.7/50.9; Michael Penix Jr. 9.2/39.7; Alvin Kamara 7.4/39.7; Drake London 7.8/34.6; Juwan Johnson 5.7/32.7; Daniel Carlson 3.0/32.3; Devaughn Vele 4.1/28.0; Olamide Zaccheaus 0.8/25.3; Kyle Pitts Sr. 1.5/20.1
### BLEND (sigma 0.6, anchor RMSE 10.77)
- 196285137: **5 lineup(s) contain a player this shadow field never rosters -- their dupe estimates are UNDERSTATED, not evidence of uniqueness**
- 196285137: dupes exact `{'mean': 54.3, 'max': 564.7, 'n_over_guardrail': 64, 'guardrail': 20}` product `{'mean': 35.67, 'max': 273.68}`; salary left `{'ours': {'0': 94, '500': 35, '1000': 13, '1500': 7, '2000': 1}, 'ours_mean': 465.0, 'shadow_field_mean': 1019.0}`; split `{'ours_pct': {'1-5': 15.3, '2-4': 32.0, '3-3': 35.3, '4-2': 14.7, '5-1': 2.7}, 'shadow_field_pct': {'1-5': 14.2, '2-4': 37.3, '3-3': 33.7, '4-2': 13.0, '5-1': 1.8}}`
- 196285160: dupes exact `{'mean': 25.9, 'max': 75.3, 'n_over_guardrail': 8, 'guardrail': 20}` product `{'mean': 9.86, 'max': 21.73}`; salary left `{'ours': {'0': 19, '1000': 1}, 'ours_mean': 265.0, 'shadow_field_mean': 1019.0}`; split `{'ours_pct': {'1-5': 35.0, '2-4': 25.0, '3-3': 30.0, '4-2': 10.0}, 'shadow_field_pct': {'1-5': 14.2, '2-4': 37.3, '3-3': 33.7, '4-2': 13.0, '5-1': 1.8}}`
- 196285161: dupes exact `{'mean': 70.6, 'max': 94.1, 'n_over_guardrail': 2, 'guardrail': 20}` product `{'mean': 6.36, 'max': 7.58}`; salary left `{'ours': {'0': 2}, 'ours_mean': 0.0, 'shadow_field_mean': 1019.0}`; split `{'ours_pct': {'1-5': 100.0}, 'shadow_field_pct': {'1-5': 14.2, '2-4': 37.3, '3-3': 33.7, '4-2': 13.0, '5-1': 1.8}}`
  - CPT/FLEX ownership (150): Tyler Shough 19.6/44.3; Bijan Robinson 19.7/42.3; Chris Olave 17.5/40.8; Drake London 10.7/37.0; Juwan Johnson 7.8/37.7; Michael Penix Jr. 8.1/36.7; Alvin Kamara 6.8/38.1; Daniel Carlson 2.9/33.1; Kevin Austin Jr. 0.3/34.7; Devaughn Vele 3.1/26.1; Nick Folk 1.1/21.6; Saints 0.9/19.2

### DUPE STACK (MC-DUPE-1 / MC-FIELD-1: PRODUCTION_CANDIDATE, NOT PROMOTED)
- E1 independent product x N; E2 E1 x ETR-seeded correlation factors (SEEDED_NOT_FITTED); E3 copies in the archetype-first generated field x N/K (linear scaling; "<x" = below resolution); E4 copies in the optimizer field x N/K_opt. Flag when E1 and E3 differ by more than 2x.
- **FC_ONLY** archetype-field calibration residual (pts) by phi `{'50.0': {'cpt': 0.862, 'flex': 2.096}, '200.0': {'cpt': 0.308, 'flex': 1.768}, '1000.0': {'cpt': 0.111, 'flex': 1.581}}`; salary left `{'mean': 2278, 'p50': 1600.0, 'share_0': 0.035, 'share_le_900': 0.333, 'share_1000_1900': 0.225}`
  - 196285137: mean `{'E1': 21.41, 'E2': 27.49, 'E3_lower_bound_mean': 15.53, 'E4': 25.73}`; flags `{'PLAYER_ABSENT_FROM_FIELD_TARGETS': 65, 'E3_BELOW_RESOLUTION_E1_NOT': 20, 'E1_E3_DISAGREE_GT_2X': 26, 'None': 39}`; E3 mean by phi `{'50.0': 16.15, '200.0': 15.53, '1000.0': 14.84}`
  - 196285160: mean `{'E1': 4.08, 'E2': 6.37, 'E3_lower_bound_mean': 2.08, 'E4': 8.0}`; flags `{'PLAYER_ABSENT_FROM_FIELD_TARGETS': 10, 'E1_E3_DISAGREE_GT_2X': 6, 'E3_BELOW_RESOLUTION_E1_NOT': 1, 'None': 3}`; E3 mean by phi `{'50.0': 1.5, '200.0': 2.08, '1000.0': 2.11}`
  - 196285161: mean `{'E1': 0.0, 'E2': 0.0, 'E3_lower_bound_mean': 0.0, 'E4': 0.0}`; flags `{'PLAYER_ABSENT_FROM_FIELD_TARGETS': 2}`; E3 mean by phi `{'50.0': 0.0, '200.0': 0.0, '1000.0': 0.0}`
    - CPT Chris Olave + Bijan Robinson, Daniel Carlson, Juwan Johnson, Treyton Welch, Tyler Shough: E1 0.0, E2 0.0 ['CPT_WR_WITH_OWN_QB x2.0'], E3 <1.2, E4 0.0, flag PLAYER_ABSENT_FROM_FIELD_TARGETS
    - CPT Drake London + Alvin Kamara, Chris Olave, Juwan Johnson, Treyton Welch, Tyler Shough: E1 0.0, E2 0.0 ['none'], E3 <1.2, E4 0.0, flag PLAYER_ABSENT_FROM_FIELD_TARGETS
- **BLEND** archetype-field calibration residual (pts) by phi `{'50.0': {'cpt': 0.368, 'flex': 2.554}, '200.0': {'cpt': 0.296, 'flex': 1.627}, '1000.0': {'cpt': 0.232, 'flex': 1.444}}`; salary left `{'mean': 1886, 'p50': 1200.0, 'share_0': 0.06, 'share_le_900': 0.425, 'share_1000_1900': 0.216}`
  - 196285137: mean `{'E1': 35.67, 'E2': 46.53, 'E3_lower_bound_mean': 44.63, 'E4': 54.28}`; flags `{'E1_E3_DISAGREE_GT_2X': 46, 'None': 86, 'PLAYER_ABSENT_FROM_FIELD_TARGETS': 5, 'E3_BELOW_RESOLUTION_E1_NOT': 13}`; E3 mean by phi `{'50.0': 39.43, '200.0': 44.63, '1000.0': 39.05}`
  - 196285160: mean `{'E1': 9.86, 'E2': 15.41, 'E3_lower_bound_mean': 21.41, 'E4': 25.88}`; flags `{'E1_E3_DISAGREE_GT_2X': 15, 'None': 5}`; E3 mean by phi `{'50.0': 20.85, '200.0': 21.41, '1000.0': 20.14}`
  - 196285161: mean `{'E1': 6.36, 'E2': 10.15, 'E3_lower_bound_mean': 85.25, 'E4': 70.6}`; flags `{'E1_E3_DISAGREE_GT_2X': 2}`; E3 mean by phi `{'50.0': 77.05, '200.0': 85.25, '1000.0': 78.8}`
    - CPT Chris Olave + Bijan Robinson, Daniel Carlson, Juwan Johnson, Treyton Welch, Tyler Shough: E1 7.58, E2 15.17 ['CPT_WR_WITH_OWN_QB x2.0'], E3 77.6, E4 94.1, flag E1_E3_DISAGREE_GT_2X
    - CPT Drake London + Alvin Kamara, Chris Olave, Juwan Johnson, Treyton Welch, Tyler Shough: E1 5.14, E2 5.14 ['none'], E3 92.9, E4 47.1, flag E1_E3_DISAGREE_GT_2X

### DUPE SALARY-LEFT SENSITIVITY (Cycle 1 FC-08 / FC-09 field-side anchors; SENSITIVITY, not a fitted model)
- NOT_RUN

## EXTERNAL
- Hard Rock: NOT CAPTURED HERE -- only after the football freeze, by the networked agent (docs/AGENT_OUTBOX.md); never fed back into the projection; no wager is recommended
- FC comparison (largest gaps; FC is never an input):
  - Kevin Austin Jr. (NO WR): ours 0.69 vs FC 8.4 (ROLE_OR_VOLUME)
  - Chris Olave (NO WR): ours 25.63 vs FC 20.85 (EFFICIENCY_OR_TD)
  - Olamide Zaccheaus (ATL WR): ours 2.39 vs FC 6.6 (ROLE_OR_VOLUME)
  - Drake London (ATL WR): ours 20.58 vs FC 16.91 (EFFICIENCY_OR_TD)
  - Kyle Pitts Sr. (ATL TE): ours 5.1 vs FC 8.72 (ROLE_OR_VOLUME)
  - Austin Hooper (ATL TE): ours 3.54 vs FC 0.0 (DEPTH_OR_DATA (FC zero is not an inactive signal))
  - Tyler Shough (NO QB): ours 22.4 vs FC 25.2 ()
  - Juwan Johnson (NO TE): ours 16.18 vs FC 14.0 ()
  - Charlie Woerner (ATL TE): ours 0.38 vs FC 2.55 ()
  - Michael Penix Jr. (ATL QB): ours 15.42 vs FC 17.37 ()
  - Daniel Carlson (NO K): ours 8.53 vs FC 10.45 ()
  - Devaughn Vele (NO WR): ours 11.11 vs FC 13.01 ()
- video claims compared: 20 (UNVERIFIED_EXTERNAL)

## FILES
- `nfl/dfs/salaries/showdown_atl_no/RW_INACTIVES/SHOWDOWN_ATL_NO_DK_UPLOAD_196285137.csv` -- 150 rows, sha256 `4cc2ded69bf7df0fe089d3104d05f1aff94e7368a089d8280bfe40fc05163ec6`
- `nfl/dfs/salaries/showdown_atl_no/RW_INACTIVES/SHOWDOWN_ATL_NO_DK_UPLOAD_196285160.csv` -- 20 rows, sha256 `45197fe7ae5e42736b56c55168c38849b144d740c0db43ad9f56ccac092c30e3`
- `nfl/dfs/salaries/showdown_atl_no/RW_INACTIVES/SHOWDOWN_ATL_NO_DK_UPLOAD_196285161.csv` -- 2 rows, sha256 `565f4c2982baf7f9cef79b2f50cead457974192f6e57f80b541e76d5e5b309c0`
- verifier: `{"n_rows": 172, "violations": []}`

nothing here enters a contest or uploads to DraftKings; PROJECTION_SYSTEM_STATE NOT_VALIDATED; no wager is recommended
