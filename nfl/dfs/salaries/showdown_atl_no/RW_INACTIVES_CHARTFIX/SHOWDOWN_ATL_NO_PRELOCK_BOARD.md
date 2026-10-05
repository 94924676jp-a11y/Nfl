# ATL @ NO Showdown -- PRE-LOCK board (RW_INACTIVES_CHARTFIX)

**READY**

## FOOTBALL
- official inactives: `['Malcolm DeWalt IV', 'Jared Ivey', 'Robert Longerbeam', 'Ethan Onianwa', 'Cooper Rush', 'Jack Strand', 'Kaden Elliss', 'Noah Fant', 'Carl Granderson', 'Anfernee Jennings', 'Christen Miller', 'Decamerion Richardson', 'Zach Wilson']`
- starters: `{'Michael Penix Jr.': 'ATL', 'Tyler Shough': 'NO'}` (PUBLIC_DEPTH_CHART_AND_SNAPS_CITED)
- state counts: `{'PROJECTED': 29, 'INACTIVE': 25, 'ZERO_OPPORTUNITY': 2}`
- football sanity: `{"state": "PASS", "code": "FOOTBALL_SANITY_PASS", "detail": "56 rows, 2 clubs, no football contradiction", "flags": null}`
- **SHOWDOWN_COHERENCE_WARNING** (measured, not fixed tonight): `{"ours_by_team": {"NO": {"corr_team_td_vs_team_off_dk": 0.57, "corr_team_points_vs_team_off_dk": 0.501}, "ATL": {"corr_team_td_vs_team_off_dk": 0.578, "corr_team_points_vs_team_off_dk": 0.511}}, "ours_corr_home_points_vs_away_points": 0.027, "ours_corr_home_off_dk_vs_away_off_dk": 0.175, "history_2021_2025": {"corr_team_td_vs_team_off_dk": 0.811, "corr_team_points_vs_team_off_dk": 0.763, "corr_home_points_vs_away_points": -0.038, "corr_home_off_dk_vs_away_off_dk": 0.181, "team_games": 2718}, "FINDING": "DEFECT-COHERENCE (measured 2026-10-05): within a simulated world, a team's offensive DK points track its touchdowns and points far more loosely than in 2021-25 games (see the numbers). The TD identity holds, so this is not broken accounting: yardage/receptions are drawn too independently of scoring. Effect: same-team boom-together is understated, so stacks are undervalued in the top tail. NOT fixed tonight (no validated fix before lock; the sealed football model is preserved); registered as the first post-lock football item."}`

| player | team | pos | salary | state | availability | desig | depth | mean | p90 | P(0) |
|---|---|---|---|---|---|---|---|---|---|---|
| Bijan Robinson | ATL | RB | 11800 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 1 | 26.01 | 38.64 | 0.0 |
| Chris Olave | NO | WR | 10800 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 1 | 25.67 | 39.7 | 0.0 |
| Tyler Shough | NO | QB | 9600 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 1 | 22.46 | 34.13 | 0.0 |
| Drake London | ATL | WR | 10000 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 1 | 20.0 | 33.16 | 0.0 |
| Juwan Johnson | NO | TE | 7400 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 1 | 16.17 | 28.01 | 0.0 |
| Michael Penix Jr. | ATL | QB | 9000 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 1 | 15.33 | 24.2 | 0.0 |
| Alvin Kamara | NO | RB | 7000 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 1 | 13.66 | 22.02 | 0.0 |
| Devaughn Vele | NO | WR | 7800 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 2 | 11.02 | 19.67 | 0.003 |
| Daniel Carlson | NO | K | 4800 | PROJECTED | UNKNOWN_ACTIVE_STATE |  |  | 8.61 | 15.0 | 0.015 |
| Nick Folk | ATL | K | 5400 | PROJECTED | UNKNOWN_ACTIVE_STATE |  |  | 7.87 | 15.0 | 0.058 |
| Saints | NO | DST | 4200 | PROJECTED | UNKNOWN_ACTIVE_STATE |  |  | 6.55 | 12.92 | 0.046 |
| Falcons | ATL | DST | 3600 | PROJECTED | UNKNOWN_ACTIVE_STATE |  |  | 5.61 | 13.01 | 0.126 |
| Kyle Pitts Sr. | ATL | TE | 5800 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 1 | 5.13 | 10.14 | 0.021 |
| Brian Robinson Jr. | ATL | RB | 3800 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 2 | 4.65 | 9.4 | 0.007 |
| Jahan Dotson | ATL | WR | 3000 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 2 | 4.09 | 8.69 | 0.045 |
| Kendre Miller | NO | RB | 5000 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 2 | 3.75 | 7.98 | 0.013 |
| Austin Hooper | ATL | TE | 2800 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 1 | 3.64 | 8.29 | 0.123 |
| Bryce Lance | NO | WR | 1800 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 3 | 2.7 | 7.0 | 0.181 |
| Olamide Zaccheaus | ATL | WR | 2000 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 3 | 2.42 | 6.0 | 0.189 |
| Oscar Delp | NO | TE | 400 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 2 | 1.47 | 4.12 | 0.413 |

## PORTFOLIO
### 196285137 (150 entries)
- objective `{'m': 3, 'value': 2.9795, 'MEANING': 'E[min(entries at the first-place proxy, m)] per world'}`; proxy coverage 1.0; method GREEDY_THEN_1SWAP_POLISH; polish `{'rounds': 14, 'lineups_changed': 13, 'objective_greedy': 2.969, 'objective_final': 2.9795, 'coverage_greedy': 1.0, 'coverage_final': 1.0}`
- distinct captains 16; effective hypotheses 68.6; shared players between pairs `{'max': 5, 'distribution': {0: 67, 1: 1425, 2: 4213, 3: 3942, 4: 1382, 5: 146}}`
- captain exposure `{'Chris Olave': 21.3, 'Bijan Robinson': 20.0, 'Drake London': 16.0, 'Tyler Shough': 11.3, 'Juwan Johnson': 7.3, 'Alvin Kamara': 7.3, 'Devaughn Vele': 4.0, 'Falcons': 2.7, 'Daniel Carlson': 2.7, 'Saints': 2.0, 'Brian Robinson Jr.': 1.3, 'Michael Penix Jr.': 1.3, 'Kyle Pitts Sr.': 0.7, 'Nick Folk': 0.7, 'Austin Hooper': 0.7, 'Kendre Miller': 0.7}`
- player exposure `{'Bijan Robinson': 65.3, 'Tyler Shough': 65.3, 'Chris Olave': 58.0, 'Drake London': 50.0, 'Michael Penix Jr.': 45.3, 'Juwan Johnson': 43.3, 'Alvin Kamara': 41.3, 'Daniel Carlson': 34.0, 'Falcons': 30.0, 'Saints': 29.3, 'Nick Folk': 24.7, 'Devaughn Vele': 24.0, 'Austin Hooper': 16.0, 'Jahan Dotson': 15.3, 'Brian Robinson Jr.': 15.3}`
- RELAXATION: level 2; rungs L0 caps {'player': 75, 'captain': 45, 'overlap': 4} built 132/150 EHC 58.6; L1 caps {'player': 75, 'captain': 45, 'overlap': 5} built 145/150 EHC 68.8; L2 caps {'player': 98, 'captain': 45, 'overlap': 5} built 150/150 EHC 66.3
  - above the original cap: `{'Chris Olave': {'n': 87, 'final_pct': 58.0, 'orig_cap_n': 75, 'orig_cap_pct': 50.0}, 'Bijan Robinson': {'n': 98, 'final_pct': 65.3, 'orig_cap_n': 75, 'orig_cap_pct': 50.0}, 'Tyler Shough': {'n': 98, 'final_pct': 65.3, 'orig_cap_n': 75, 'orig_cap_pct': 50.0}}`; captains `{}`
  - lineups not in the level-0 build: 93; clusters `{'by_origin': {'RELAXATION': 84, 'SWAP_POLISH': 9}, 'by_captain': {'Bijan Robinson': 17, 'Chris Olave': 16, 'Drake London': 14, 'Tyler Shough': 11, 'Alvin Kamara': 8, 'Juwan Johnson': 7, 'Devaughn Vele': 5, 'Daniel Carlson': 3, 'Falcons': 3, 'Brian Robinson Jr.': 2, 'Saints': 2, 'Michael Penix Jr.': 2, 'Kyle Pitts Sr.': 1, 'Nick Folk': 1, 'Austin Hooper': 1}, 'by_split': {'2-4': 29, '3-3': 22, '4-2': 21, '1-5': 11, '5-1': 10}, 'by_salary_band': {'49500-49900': 56, '49000-49400': 15, '50000': 12, '48000-48900': 10}}`
  - why: level 0 built 132/150: under a 75-entry player cap, a 45-entry captain cap and at most 4 shared players, the lawful pool near the top-tail runs out of lineups that avoid the core (Bijan Robinson, Tyler Shough, Chris Olave)
  - effective hypotheses (rungs are GREEDY rebuilds, before the swap polish): last unfilled rung 68.8 -> filled rung 66.3; final polished portfolio 68.6
- salary-relief slots used: `{'Treyton Welch': 2, 'Charlie Woerner': 2, 'Kevin Austin Jr.': 1, 'Nick Muse': 1}`
### 196285160 (20 entries)
- objective `{'m': 2, 'value': 1.4035, 'MEANING': 'E[min(entries at the first-place proxy, m)] per world'}`; proxy coverage 0.827; method GREEDY_THEN_1SWAP_POLISH; polish `{'rounds': 9, 'lineups_changed': 7, 'objective_greedy': 1.3475, 'objective_final': 1.4035, 'coverage_greedy': 0.7675, 'coverage_final': 0.827}`
- distinct captains 5; effective hypotheses 15.8; shared players between pairs `{'max': 5, 'distribution': {0: 2, 1: 14, 2: 53, 3: 74, 4: 45, 5: 2}}`
- captain exposure `{'Chris Olave': 30.0, 'Bijan Robinson': 30.0, 'Tyler Shough': 15.0, 'Drake London': 15.0, 'Juwan Johnson': 10.0}`
- player exposure `{'Bijan Robinson': 65.0, 'Chris Olave': 65.0, 'Tyler Shough': 65.0, 'Alvin Kamara': 60.0, 'Juwan Johnson': 55.0, 'Drake London': 55.0, 'Oscar Delp': 45.0, 'Daniel Carlson': 40.0, 'Michael Penix Jr.': 35.0, 'Falcons': 30.0, 'Saints': 30.0, 'Bryce Lance': 15.0, 'Nick Folk': 15.0, 'Devaughn Vele': 10.0, 'Jahan Dotson': 5.0}`
- RELAXATION: level 2; rungs L0 caps {'player': 10, 'captain': 6, 'overlap': 4} built 16/20 EHC 12.5; L1 caps {'player': 10, 'captain': 6, 'overlap': 5} built 17/20 EHC 11.5; L2 caps {'player': 13, 'captain': 6, 'overlap': 5} built 20/20 EHC 13.0
  - above the original cap: `{'Juwan Johnson': {'n': 11, 'final_pct': 55.0, 'orig_cap_n': 10, 'orig_cap_pct': 50.0}, 'Bijan Robinson': {'n': 13, 'final_pct': 65.0, 'orig_cap_n': 10, 'orig_cap_pct': 50.0}, 'Chris Olave': {'n': 13, 'final_pct': 65.0, 'orig_cap_n': 10, 'orig_cap_pct': 50.0}, 'Tyler Shough': {'n': 13, 'final_pct': 65.0, 'orig_cap_n': 10, 'orig_cap_pct': 50.0}, 'Alvin Kamara': {'n': 12, 'final_pct': 60.0, 'orig_cap_n': 10, 'orig_cap_pct': 50.0}, 'Drake London': {'n': 11, 'final_pct': 55.0, 'orig_cap_n': 10, 'orig_cap_pct': 50.0}}`; captains `{}`
  - lineups not in the level-0 build: 14; clusters `{'by_origin': {'SWAP_POLISH': 6, 'RELAXATION': 8}, 'by_captain': {'Chris Olave': 4, 'Bijan Robinson': 3, 'Drake London': 3, 'Juwan Johnson': 2, 'Tyler Shough': 2}, 'by_split': {'3-3': 6, '1-5': 4, '2-4': 3, '4-2': 1}, 'by_salary_band': {'49500-49900': 6, '50000': 6, '49000-49400': 1, '48000-48900': 1}}`
  - why: level 0 built 16/20: under a 10-entry player cap, a 6-entry captain cap and at most 4 shared players, the lawful pool near the top-tail runs out of lineups that avoid the core (Bijan Robinson, Chris Olave, Tyler Shough, Alvin Kamara)
  - effective hypotheses (rungs are GREEDY rebuilds, before the swap polish): last unfilled rung 11.5 -> filled rung 13.0; final polished portfolio 15.8
- salary-relief slots used: `{}`
### 196285161 (2 entries)
- objective `{'m': 1, 'value': 0.3165, 'MEANING': 'E[min(entries at the first-place proxy, m)] per world'}`; proxy coverage 0.3165; method GREEDY_THEN_1SWAP_POLISH; polish `{'rounds': 1, 'lineups_changed': 0, 'objective_greedy': 0.3165, 'objective_final': 0.3165, 'coverage_greedy': 0.3165, 'coverage_final': 0.3165}`
- distinct captains 2; effective hypotheses 2.0; shared players between pairs `{'max': 3, 'distribution': {3: 1}}`
- captain exposure `{'Chris Olave': 50.0, 'Tyler Shough': 50.0}`
- player exposure `{'Chris Olave': 100.0, 'Juwan Johnson': 100.0, 'Tyler Shough': 100.0, 'Bijan Robinson': 50.0, 'Daniel Carlson': 50.0, 'Treyton Welch': 50.0, 'Alvin Kamara': 50.0, 'Drake London': 50.0, 'Oscar Delp': 50.0}`
- RELAXATION: level 0; rungs L0 caps {'player': 2, 'captain': 2, 'overlap': 4} built 2/2 EHC 2.0
  - above the original cap: `{}`; captains `{}`
  - lineups not in the level-0 build: 0; clusters `{'by_origin': {}, 'by_captain': {}, 'by_split': {}, 'by_salary_band': {}}`
  - why: no relaxation needed: level 0 built 2/2
  - effective hypotheses (rungs are GREEDY rebuilds, before the swap polish): last unfilled rung None -> filled rung 2.0; final polished portfolio 2.0
- salary-relief slots used: `{'Treyton Welch': 1}`
- **CPT Chris Olave** + Bijan Robinson, Daniel Carlson, Juwan Johnson, Treyton Welch, Tyler Shough -- $50000, mean 112.05, proxy 0.194
  - **Treyton Welch: SALARY RELIEF -- not a football conviction** (LOW_OPPORTUNITY_SALARY_RELIEF; mean 0.31, scores in 17% of worlds; proxy 0.1867 when he scores 0 vs 0.229 when he scores); unlocks ['Bijan Robinson', 'Juwan Johnson', 'Tyler Shough']
  - best realistic alternative without him: ['Chris Olave', 'Bijan Robinson', 'Daniel Carlson', 'Juwan Johnson', 'Nick Muse', 'Tyler Shough'] (proxy 0.188, mean 111.76); difference proxy +0.006, mean points +0.29
- **CPT Tyler Shough** + Alvin Kamara, Chris Olave, Drake London, Juwan Johnson, Oscar Delp -- $50000, mean 110.65, proxy 0.1655
  - portfolio test without_these ['Treyton Welch']: objective -0.004, coverage -0.4 pts (SE 1.04), mean points -0.14; alternative lineups [['Chris Olave', 'Bijan Robinson', 'Daniel Carlson', 'Juwan Johnson', 'Nick Muse', 'Tyler Shough'], ['Tyler Shough', 'Alvin Kamara', 'Chris Olave', 'Drake London', 'Juwan Johnson', 'Oscar Delp']]
  - portfolio test without_any_low_opportunity_or_filler ['Barion Brown', 'CJ Donaldson', 'Charlie Woerner', 'Chris Blair', 'Kevin Austin Jr.', 'Nick Muse', 'Spencer Rattler', 'Treyton Welch', 'Tua Tagovailoa', 'Zachariah Branch']: objective -0.0085, coverage -0.85 pts (SE 1.04), mean points -0.83; alternative lineups [['Bijan Robinson', 'Chris Olave', 'Falcons', 'Juwan Johnson', 'Oscar Delp', 'Tyler Shough'], ['Tyler Shough', 'Alvin Kamara', 'Chris Olave', 'Drake London', 'Juwan Johnson', 'Oscar Delp']]

## FIELD (EXTERNAL_RESEARCH_SHADOW, UNVALIDATED)
- NOT_PROMOTED. Both field projections are EXTERNAL_RESEARCH_SHADOW and UNVALIDATED; the blend fits five unverified anchors better, which is not validation. Neither feeds the football or the production portfolio.
### FC_ONLY (sigma 0.6, anchor RMSE 13.75)
- 196285137: **64 lineup(s) contain a player this shadow field never rosters -- their dupe estimates are UNDERSTATED, not evidence of uniqueness**
- 196285137: dupes exact `{'mean': 19.8, 'max': 188.2, 'n_over_guardrail': 39, 'guardrail': 20}` product `{'mean': 19.15, 'max': 124.77}`; salary left `{'ours': {'0': 105, '500': 29, '1000': 9, '1500': 7}, 'ours_mean': 395.0, 'shadow_field_mean': 1567.0}`; split `{'ours_pct': {'1-5': 14.0, '2-4': 29.3, '3-3': 30.0, '4-2': 18.7, '5-1': 8.0}, 'shadow_field_pct': {'1-5': 14.3, '2-4': 37.6, '3-3': 33.1, '4-2': 13.0, '5-1': 2.0}}`
- 196285160: **9 lineup(s) contain a player this shadow field never rosters -- their dupe estimates are UNDERSTATED, not evidence of uniqueness**
- 196285160: dupes exact `{'mean': 4.7, 'max': 28.2, 'n_over_guardrail': 1, 'guardrail': 20}` product `{'mean': 5.19, 'max': 24.77}`; salary left `{'ours': {'0': 16, '500': 3, '1000': 1}, 'ours_mean': 230.0, 'shadow_field_mean': 1567.0}`; split `{'ours_pct': {'1-5': 35.0, '2-4': 20.0, '3-3': 40.0, '4-2': 5.0}, 'shadow_field_pct': {'1-5': 14.3, '2-4': 37.6, '3-3': 33.1, '4-2': 13.0, '5-1': 2.0}}`
- 196285161: **2 lineup(s) contain a player this shadow field never rosters -- their dupe estimates are UNDERSTATED, not evidence of uniqueness**
- 196285161: dupes exact `{'mean': 0.0, 'max': 0.0, 'n_over_guardrail': 0, 'guardrail': 20}` product `{'mean': 0.0, 'max': 0.0}`; salary left `{'ours': {'0': 2}, 'ours_mean': 0.0, 'shadow_field_mean': 1567.0}`; split `{'ours_pct': {'1-5': 100.0}, 'shadow_field_pct': {'1-5': 14.3, '2-4': 37.6, '3-3': 33.1, '4-2': 13.0, '5-1': 2.0}}`
  - CPT/FLEX ownership (150): Tyler Shough 22.5/45.9; Bijan Robinson 21.2/44.3; Chris Olave 13.2/39.7; Kevin Austin Jr. 1.7/50.9; Michael Penix Jr. 9.2/39.7; Alvin Kamara 7.4/39.7; Drake London 7.8/34.6; Juwan Johnson 5.7/32.7; Daniel Carlson 3.0/32.3; Devaughn Vele 4.1/28.0; Olamide Zaccheaus 0.8/25.3; Kyle Pitts Sr. 1.5/20.1
### BLEND (sigma 0.6, anchor RMSE 10.87)
- 196285137: **1 lineup(s) contain a player this shadow field never rosters -- their dupe estimates are UNDERSTATED, not evidence of uniqueness**
- 196285137: dupes exact `{'mean': 51.8, 'max': 329.4, 'n_over_guardrail': 72, 'guardrail': 20}` product `{'mean': 32.23, 'max': 117.73}`; salary left `{'ours': {'0': 105, '500': 29, '1000': 9, '1500': 7}, 'ours_mean': 395.0, 'shadow_field_mean': 1019.0}`; split `{'ours_pct': {'1-5': 14.0, '2-4': 29.3, '3-3': 30.0, '4-2': 18.7, '5-1': 8.0}, 'shadow_field_pct': {'1-5': 14.3, '2-4': 37.6, '3-3': 33.5, '4-2': 12.8, '5-1': 1.8}}`
- 196285160: dupes exact `{'mean': 16.9, 'max': 47.1, 'n_over_guardrail': 7, 'guardrail': 20}` product `{'mean': 10.26, 'max': 36.74}`; salary left `{'ours': {'0': 16, '500': 3, '1000': 1}, 'ours_mean': 230.0, 'shadow_field_mean': 1019.0}`; split `{'ours_pct': {'1-5': 35.0, '2-4': 20.0, '3-3': 40.0, '4-2': 5.0}, 'shadow_field_pct': {'1-5': 14.3, '2-4': 37.6, '3-3': 33.5, '4-2': 12.8, '5-1': 1.8}}`
- 196285161: dupes exact `{'mean': 47.1, 'max': 47.1, 'n_over_guardrail': 2, 'guardrail': 20}` product `{'mean': 3.28, 'max': 4.27}`; salary left `{'ours': {'0': 2}, 'ours_mean': 0.0, 'shadow_field_mean': 1019.0}`; split `{'ours_pct': {'1-5': 100.0}, 'shadow_field_pct': {'1-5': 14.3, '2-4': 37.6, '3-3': 33.5, '4-2': 12.8, '5-1': 1.8}}`
  - CPT/FLEX ownership (150): Tyler Shough 19.9/44.1; Bijan Robinson 19.6/42.5; Chris Olave 17.6/40.8; Drake London 10.3/36.9; Juwan Johnson 7.8/37.8; Alvin Kamara 6.9/38.1; Michael Penix Jr. 8.1/36.8; Daniel Carlson 2.9/33.3; Kevin Austin Jr. 0.3/35.1; Devaughn Vele 3.1/25.9; Nick Folk 0.9/20.9; Saints 0.9/19.2

### DUPE STACK (MC-DUPE-1 / MC-FIELD-1: PRODUCTION_CANDIDATE, NOT PROMOTED)
- E1 independent product x N; E2 E1 x ETR-seeded correlation factors (SEEDED_NOT_FITTED); E3 copies in the archetype-first generated field x N/K (linear scaling; "<x" = below resolution); E4 copies in the optimizer field x N/K_opt. Flag when E1 and E3 differ by more than 2x.
- **FC_ONLY** archetype-field calibration residual (pts) by phi `{'50.0': {'cpt': 0.862, 'flex': 2.096}, '200.0': {'cpt': 0.308, 'flex': 1.768}, '1000.0': {'cpt': 0.111, 'flex': 1.581}}`; salary left `{'mean': 2278, 'p50': 1600.0, 'share_0': 0.035, 'share_le_900': 0.333, 'share_1000_1900': 0.225}`
  - 196285137: mean `{'E1': 19.15, 'E2': 24.22, 'E3_lower_bound_mean': 11.82, 'E4': 19.77}`; flags `{'PLAYER_ABSENT_FROM_FIELD_TARGETS': 64, 'E3_BELOW_RESOLUTION_E1_NOT': 19, 'E1_E3_DISAGREE_GT_2X': 26, 'None': 41}`; E3 mean by phi `{'50.0': 12.54, '200.0': 11.82, '1000.0': 11.51}`
  - 196285160: mean `{'E1': 5.19, 'E2': 7.21, 'E3_lower_bound_mean': 2.77, 'E4': 4.7}`; flags `{'E3_BELOW_RESOLUTION_E1_NOT': 3, 'PLAYER_ABSENT_FROM_FIELD_TARGETS': 9, 'None': 4, 'E1_E3_DISAGREE_GT_2X': 4}`; E3 mean by phi `{'50.0': 2.81, '200.0': 2.77, '1000.0': 2.96}`
  - 196285161: mean `{'E1': 0.0, 'E2': 0.0, 'E3_lower_bound_mean': 0.0, 'E4': 0.0}`; flags `{'PLAYER_ABSENT_FROM_FIELD_TARGETS': 2}`; E3 mean by phi `{'50.0': 0.0, '200.0': 0.0, '1000.0': 0.0}`
    - CPT Chris Olave + Bijan Robinson, Daniel Carlson, Juwan Johnson, Treyton Welch, Tyler Shough: E1 0.0, E2 0.0 ['CPT_WR_WITH_OWN_QB x2.0'], E3 <1.2, E4 0.0, flag PLAYER_ABSENT_FROM_FIELD_TARGETS
    - CPT Tyler Shough + Alvin Kamara, Chris Olave, Drake London, Juwan Johnson, Oscar Delp: E1 0.0, E2 0.0 ['none'], E3 <1.2, E4 0.0, flag PLAYER_ABSENT_FROM_FIELD_TARGETS
- **BLEND** archetype-field calibration residual (pts) by phi `{'50.0': {'cpt': 0.4, 'flex': 1.79}, '200.0': {'cpt': 0.296, 'flex': 1.786}, '1000.0': {'cpt': 0.141, 'flex': 1.484}}`; salary left `{'mean': 1939, 'p50': 1300.0, 'share_0': 0.057, 'share_le_900': 0.412, 'share_1000_1900': 0.217}`
  - 196285137: mean `{'E1': 32.23, 'E2': 41.42, 'E3_lower_bound_mean': 33.22, 'E4': 51.77}`; flags `{'E1_E3_DISAGREE_GT_2X': 43, 'None': 89, 'E3_BELOW_RESOLUTION_E1_NOT': 17, 'PLAYER_ABSENT_FROM_FIELD_TARGETS': 1}`; E3 mean by phi `{'50.0': 38.55, '200.0': 33.22, '1000.0': 35.89}`
  - 196285160: mean `{'E1': 10.26, 'E2': 13.95, 'E3_lower_bound_mean': 13.46, 'E4': 16.93}`; flags `{'None': 9, 'E1_E3_DISAGREE_GT_2X': 9, 'E3_BELOW_RESOLUTION_E1_NOT': 2}`; E3 mean by phi `{'50.0': 16.09, '200.0': 13.46, '1000.0': 14.07}`
  - 196285161: mean `{'E1': 3.28, 'E2': 4.43, 'E3_lower_bound_mean': 49.4, 'E4': 47.1}`; flags `{'E1_E3_DISAGREE_GT_2X': 2}`; E3 mean by phi `{'50.0': 60.6, '200.0': 49.4, '1000.0': 58.85}`
    - CPT Chris Olave + Bijan Robinson, Daniel Carlson, Juwan Johnson, Treyton Welch, Tyler Shough: E1 2.29, E2 4.59 ['CPT_WR_WITH_OWN_QB x2.0'], E3 69.4, E4 47.1, flag E1_E3_DISAGREE_GT_2X
    - CPT Tyler Shough + Alvin Kamara, Chris Olave, Drake London, Juwan Johnson, Oscar Delp: E1 4.27, E2 4.27 ['none'], E3 29.4, E4 47.1, flag E1_E3_DISAGREE_GT_2X

### DUPE SALARY-LEFT SENSITIVITY (Cycle 1 FC-08 / FC-09 field-side anchors; SENSITIVITY, not a fitted model)
- BLEND|FC08_90PCT_LE_500|phi200.0: anchor `{'0-500': {'target': 0.9, 'achieved': 0.891}, '600-50000': {'target': 0.1, 'achieved': 0.109}}`; residual `{'cpt': 0.147, 'flex': 0.921}`; E3 mean `{'196285137': 101.24, '196285160': 40.66, '196285161': 78.25}`; 2-entry E3 `[('Chris Olave', 62.4), ('Tyler Shough', 94.1)]`

## EXTERNAL
- Hard Rock: NOT CAPTURED HERE -- only after the football freeze, by the networked agent (docs/AGENT_OUTBOX.md); never fed back into the projection; no wager is recommended
- FC comparison (largest gaps; FC is never an input):
  - Kevin Austin Jr. (NO WR): ours 0.75 vs FC 8.4 (ROLE_OR_VOLUME)
  - Chris Olave (NO WR): ours 25.67 vs FC 20.85 (EFFICIENCY_OR_TD)
  - Olamide Zaccheaus (ATL WR): ours 2.42 vs FC 6.6 (ROLE_OR_VOLUME)
  - Austin Hooper (ATL TE): ours 3.64 vs FC 0.0 (DEPTH_OR_DATA (FC zero is not an inactive signal))
  - Kyle Pitts Sr. (ATL TE): ours 5.13 vs FC 8.72 (ROLE_OR_VOLUME)
  - Drake London (ATL WR): ours 20.0 vs FC 16.91 (EFFICIENCY_OR_TD)
  - Tyler Shough (NO QB): ours 22.46 vs FC 25.2 ()
  - Juwan Johnson (NO TE): ours 16.17 vs FC 14.0 ()
  - Charlie Woerner (ATL TE): ours 0.39 vs FC 2.55 ()
  - Michael Penix Jr. (ATL QB): ours 15.33 vs FC 17.37 ()
  - Devaughn Vele (NO WR): ours 11.02 vs FC 13.01 ()
  - Zachariah Branch (ATL WR): ours 0.75 vs FC 2.65 ()
- video claims compared: 20 (UNVERIFIED_EXTERNAL)

## FILES
- `nfl/dfs/salaries/showdown_atl_no/RW_INACTIVES_CHARTFIX/SHOWDOWN_ATL_NO_DK_UPLOAD_196285137.csv` -- 150 rows, sha256 `4047a1895c3dec8dbe22da5bb2386c06558e39ddc1c2d5a78f5e9c236ab7e002`
- `nfl/dfs/salaries/showdown_atl_no/RW_INACTIVES_CHARTFIX/SHOWDOWN_ATL_NO_DK_UPLOAD_196285160.csv` -- 20 rows, sha256 `17e397b48d5944aa3ce6113eab64818285ac42355f49c0963e53f7fd40501f1f`
- `nfl/dfs/salaries/showdown_atl_no/RW_INACTIVES_CHARTFIX/SHOWDOWN_ATL_NO_DK_UPLOAD_196285161.csv` -- 2 rows, sha256 `a30f529fbca23633b5bc4b73a8bfd2b39c7995cbf051e8856fbe1321d7ac1612`
- verifier: `{"n_rows": 172, "violations": []}`

nothing here enters a contest or uploads to DraftKings; PROJECTION_SYSTEM_STATE NOT_VALIDATED; no wager is recommended
