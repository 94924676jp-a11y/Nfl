# ATL @ NO Showdown -- PRE-LOCK board (OFFICIAL)

**NOT_READY** -- blockers: INACTIVES_FROM_SECONDARY_SOURCE_NOT_OFFICIALLY_VERIFIED (SECONDARY_AGGREGATOR_RELAYED (RotoWire lineups page, screens)

## FOOTBALL
- official inactives: `['Ajani Cornelius', 'Antoine Winfield Jr.', 'Baker Mayfield', 'Benjamin Morrison', 'Billy Schrauth', 'Camden Brown', 'Cobie Durant', 'DeMarvion Overshown', 'DeMonte Capehart', 'Drew Shelton', 'James Houston', 'Joey Porter Jr.', 'Luke Haggard', 'SirVocea Dennis']`
- starters: `{'Jalon Daniels': 'TB', 'Dak Prescott': 'DAL'}` (OWNER_RELAYED_TEAM_ANNOUNCEMENT)
- state counts: `{'PROJECTED': 31, 'ZERO_OPPORTUNITY': 18, 'PROJECTED_WITH_UNCERTAINTY': 1, 'INACTIVE': 2}`
- football sanity: `{"state": "PASS", "code": "FOOTBALL_SANITY_PASS", "detail": "52 rows, 2 clubs, no football contradiction", "flags": null}`
- **SHOWDOWN_COHERENCE_WARNING** (measured, not fixed tonight): `{"ours_by_team": {"DAL": {"corr_team_td_vs_team_off_dk": 0.582, "corr_team_points_vs_team_off_dk": 0.511}, "TB": {"corr_team_td_vs_team_off_dk": 0.642, "corr_team_points_vs_team_off_dk": 0.566}}, "ours_corr_home_points_vs_away_points": 0.044, "ours_corr_home_off_dk_vs_away_off_dk": 0.176, "history_2021_2025": {"corr_team_td_vs_team_off_dk": 0.811, "corr_team_points_vs_team_off_dk": 0.763, "corr_home_points_vs_away_points": -0.038, "corr_home_off_dk_vs_away_off_dk": 0.181, "team_games": 2718}, "FINDING": "DEFECT-COHERENCE (measured 2026-10-05): within a simulated world, a team's offensive DK points track its touchdowns and points far more loosely than in 2021-25 games (see the numbers). The TD identity holds, so this is not broken accounting: yardage/receptions are drawn too independently of scoring. Effect: same-team boom-together is understated, so stacks are undervalued in the top tail. NOT fixed tonight (no validated fix before lock; the sealed football model is preserved); registered as the first post-lock football item."}`

| player | team | pos | salary | state | availability | desig | depth | mean | p90 | P(0) |
|---|---|---|---|---|---|---|---|---|---|---|
| CeeDee Lamb | DAL | WR | 11800 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 1 | 28.28 | 43.15 | 0.0 |
| Dak Prescott | DAL | QB | 10400 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 1 | 22.45 | 33.16 | 0.0 |
| Javonte Williams | DAL | RB | 10800 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 1 | 18.73 | 29.68 | 0.0 |
| Bucky Irving | TB | RB | 8400 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 1 | 16.5 | 26.96 | 0.0 |
| Jalon Daniels | TB | QB | 8600 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 1 | 13.99 | 22.61 | 0.0 |
| Emeka Egbuka | TB | WR | 8200 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 1 | 11.99 | 21.56 | 0.001 |
| George Pickens | DAL | WR | 9400 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 2 | 11.7 | 21.51 | 0.003 |
| Cade Otton | TB | TE | 4400 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 1 | 11.57 | 20.02 | 0.001 |
| Jake Ferguson | DAL | TE | 6400 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 1 | 10.08 | 18.03 | 0.006 |
| Brandon Aubrey | DAL | K | 5400 | PROJECTED | UNKNOWN_ACTIVE_STATE |  |  | 9.25 | 16.0 | 0.003 |
| Chris Godwin Jr. | TB | WR | 7200 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 2 | 8.54 | 15.57 | 0.009 |
| Chase McLaughlin | TB | K | 5000 | PROJECTED | UNKNOWN_ACTIVE_STATE |  |  | 7.98 | 14.0 | 0.037 |
| Ryan Flournoy | DAL | WR | 3800 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 3 | 5.43 | 11.17 | 0.041 |
| Kenny Gainwell | TB | RB | 4000 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 2 | 4.57 | 9.27 | 0.018 |
| Tyler Goodson | DAL | RB | 2000 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 2 | 4.43 | 9.62 | 0.011 |
| Buccaneers | TB | DST | 3000 | PROJECTED | UNKNOWN_ACTIVE_STATE |  |  | 4.31 | 10.68 | 0.266 |
| Ted Hurst III | TB | WR | 2800 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 3 | 3.95 | 8.71 | 0.1 |
| Cowboys | DAL | DST | 4800 | PROJECTED | UNKNOWN_ACTIVE_STATE |  |  | 3.91 | 8.14 | 0.077 |
| Payne Durham | TB | TE | 200 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 2 | 2.73 | 6.57 | 0.216 |
| Brevyn Spann-Ford | DAL | TE | 1600 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 2 | 2.54 | 6.32 | 0.243 |
| Sean Tucker | TB | RB | 2400 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 3 | 1.42 | 6.0 | 0.349 |
| KaVontae Turpin | DAL | WR | 1200 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 4 | 1.12 | 3.64 | 0.523 |
| Emari Demercado | DAL | RB | 400 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 3 | 1.08 | 3.2 | 0.402 |
| Tez Johnson | TB | WR | 2200 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 4 | 1.07 | 3.43 | 0.516 |

## PORTFOLIO
### 196438543 (150 entries)
- objective `{'m': 1, 'value': 0.9995, 'MEANING': 'E[min(entries at the first-place proxy, m)] per world'}`; proxy coverage 0.9995; method GREEDY_THEN_1SWAP_POLISH; polish `{'rounds': 1, 'lineups_changed': 0, 'objective_greedy': 0.9995, 'objective_final': 0.9995, 'coverage_greedy': 0.9995, 'coverage_final': 0.9995}`
- distinct captains 16; effective hypotheses 95.4; shared players between pairs `{'max': 4, 'distribution': {0: 396, 1: 2095, 2: 4319, 3: 3231, 4: 1134}}`
- captain exposure `{'CeeDee Lamb': 22.7, 'Javonte Williams': 22.0, 'Bucky Irving': 14.0, 'Dak Prescott': 8.7, 'Cade Otton': 5.3, 'Emeka Egbuka': 5.3, 'Chris Godwin Jr.': 5.3, 'Jalon Daniels': 4.0, 'George Pickens': 2.7, 'Brandon Aubrey': 2.7, 'Buccaneers': 2.7, 'Jake Ferguson': 2.0, 'Brevyn Spann-Ford': 0.7, 'Sean Tucker': 0.7, 'Ryan Flournoy': 0.7, 'Cowboys': 0.7}`
- player exposure `{'CeeDee Lamb': 50.0, 'Bucky Irving': 50.0, 'Dak Prescott': 50.0, 'Javonte Williams': 50.0, 'Cade Otton': 49.3, 'Jalon Daniels': 46.0, 'Brandon Aubrey': 40.0, 'Emeka Egbuka': 38.0, 'Jake Ferguson': 34.0, 'George Pickens': 30.0, 'Chase McLaughlin': 27.3, 'Chris Godwin Jr.': 27.3, 'Buccaneers': 23.3, 'Tyler Goodson': 14.7, 'Ryan Flournoy': 14.7}`
- RELAXATION: level 0; rungs L0 caps {'player': 75, 'captain': 45, 'overlap': 4} built 150/150 EHC 95.9
  - above the original cap: `{}`; captains `{}`
  - lineups not in the level-0 build: 1; clusters `{'by_origin': {'RELAXATION': 1}, 'by_captain': {'Jalon Daniels': 1}, 'by_split': {'3-3': 1}, 'by_salary_band': {'<48000': 1}}`
  - why: no relaxation needed: level 0 built 150/150
  - effective hypotheses (rungs are GREEDY rebuilds, before the swap polish): last unfilled rung None -> filled rung 95.9; final polished portfolio 95.4
- salary-relief slots used: `{'KaVontae Turpin': 3, 'Tez Johnson': 1, 'David Sills V': 1, 'Luke Schoonmaker': 1, 'Josh Williams': 1}`
### 196438555 (20 entries)
- objective `{'m': 2, 'value': 1.1245, 'MEANING': 'E[min(entries at the first-place proxy, m)] per world'}`; proxy coverage 0.701; method GREEDY_THEN_1SWAP_POLISH; polish `{'rounds': 1, 'lineups_changed': 0, 'objective_greedy': 1.1245, 'objective_final': 1.1245, 'coverage_greedy': 0.701, 'coverage_final': 0.701}`
- distinct captains 7; effective hypotheses 17.4; shared players between pairs `{'max': 4, 'distribution': {0: 17, 1: 43, 2: 43, 3: 54, 4: 33}}`
- captain exposure `{'CeeDee Lamb': 30.0, 'Bucky Irving': 15.0, 'Dak Prescott': 15.0, 'Javonte Williams': 15.0, 'Jalon Daniels': 10.0, 'Buccaneers': 10.0, 'Emeka Egbuka': 5.0}`
- player exposure `{'CeeDee Lamb': 50.0, 'Bucky Irving': 50.0, 'Cade Otton': 50.0, 'Dak Prescott': 50.0, 'Javonte Williams': 50.0, 'Brandon Aubrey': 50.0, 'Jalon Daniels': 45.0, 'Emeka Egbuka': 45.0, 'Chase McLaughlin': 40.0, 'Jake Ferguson': 35.0, 'Tyler Goodson': 25.0, 'George Pickens': 25.0, 'Buccaneers': 20.0, 'Payne Durham': 15.0, 'Brevyn Spann-Ford': 10.0}`
- RELAXATION: level 0; rungs L0 caps {'player': 10, 'captain': 6, 'overlap': 4} built 20/20 EHC 17.4
  - above the original cap: `{}`; captains `{}`
  - lineups not in the level-0 build: 1; clusters `{'by_origin': {'RELAXATION': 1}, 'by_captain': {'Emeka Egbuka': 1}, 'by_split': {'3-3': 1}, 'by_salary_band': {'<48000': 1}}`
  - why: no relaxation needed: level 0 built 20/20
  - effective hypotheses (rungs are GREEDY rebuilds, before the swap polish): last unfilled rung None -> filled rung 17.4; final polished portfolio 17.4
- salary-relief slots used: `{}`
### 196438556 (20 entries)
- objective `{'m': 2, 'value': 1.1245, 'MEANING': 'E[min(entries at the first-place proxy, m)] per world'}`; proxy coverage 0.701; method GREEDY_THEN_1SWAP_POLISH; polish `{'rounds': 1, 'lineups_changed': 0, 'objective_greedy': 1.1245, 'objective_final': 1.1245, 'coverage_greedy': 0.701, 'coverage_final': 0.701}`
- distinct captains 7; effective hypotheses 17.4; shared players between pairs `{'max': 4, 'distribution': {0: 17, 1: 43, 2: 43, 3: 54, 4: 33}}`
- captain exposure `{'CeeDee Lamb': 30.0, 'Bucky Irving': 15.0, 'Dak Prescott': 15.0, 'Javonte Williams': 15.0, 'Jalon Daniels': 10.0, 'Buccaneers': 10.0, 'Emeka Egbuka': 5.0}`
- player exposure `{'CeeDee Lamb': 50.0, 'Bucky Irving': 50.0, 'Cade Otton': 50.0, 'Dak Prescott': 50.0, 'Javonte Williams': 50.0, 'Brandon Aubrey': 50.0, 'Jalon Daniels': 45.0, 'Emeka Egbuka': 45.0, 'Chase McLaughlin': 40.0, 'Jake Ferguson': 35.0, 'Tyler Goodson': 25.0, 'George Pickens': 25.0, 'Buccaneers': 20.0, 'Payne Durham': 15.0, 'Brevyn Spann-Ford': 10.0}`
- RELAXATION: level 0; rungs L0 caps {'player': 10, 'captain': 6, 'overlap': 4} built 20/20 EHC 17.4
  - above the original cap: `{}`; captains `{}`
  - lineups not in the level-0 build: 1; clusters `{'by_origin': {'RELAXATION': 1}, 'by_captain': {'Emeka Egbuka': 1}, 'by_split': {'3-3': 1}, 'by_salary_band': {'<48000': 1}}`
  - why: no relaxation needed: level 0 built 20/20
  - effective hypotheses (rungs are GREEDY rebuilds, before the swap polish): last unfilled rung None -> filled rung 17.4; final polished portfolio 17.4
- salary-relief slots used: `{}`

## FIELD (EXTERNAL_RESEARCH_SHADOW, UNVALIDATED)
- NOT_PROMOTED. Both field projections are EXTERNAL_RESEARCH_SHADOW and UNVALIDATED; the blend fits five unverified anchors better, which is not validation. Neither feeds the football or the production portfolio.
### FC_ONLY (sigma 0.25, anchor RMSE 21.48)
- 196438543: **56 lineup(s) contain a player this shadow field never rosters -- their dupe estimates are UNDERSTATED, not evidence of uniqueness**
- 196438543: dupes exact `{'mean': 58.4, 'max': 3905.9, 'n_over_guardrail': 12, 'guardrail': 20}` product `{'mean': 16.47, 'max': 905.6}`; salary left `{'ours': {'0': 64, '1000': 20, '500': 31, '1500': 7, '2000': 2, '3000': 25, '2500': 1}, 'ours_mean': 2163.0, 'shadow_field_mean': 531.0}`; split `{'ours_pct': {'1-5': 8.0, '2-4': 22.0, '3-3': 38.7, '4-2': 27.3, '5-1': 4.0}, 'shadow_field_pct': {'1-5': 59.9, '2-4': 35.0, '3-3': 4.8, '4-2': 0.3}}`
- 196438555: **11 lineup(s) contain a player this shadow field never rosters -- their dupe estimates are UNDERSTATED, not evidence of uniqueness**
- 196438555: dupes exact `{'mean': 0.0, 'max': 0.0, 'n_over_guardrail': 0, 'guardrail': 20}` product `{'mean': 0.06, 'max': 0.62}`; salary left `{'ours': {'0': 12, '500': 3, '2500': 1, '3000': 4}, 'ours_mean': 2815.0, 'shadow_field_mean': 531.0}`; split `{'ours_pct': {'1-5': 5.0, '2-4': 30.0, '3-3': 40.0, '4-2': 25.0}, 'shadow_field_pct': {'1-5': 59.9, '2-4': 35.0, '3-3': 4.8, '4-2': 0.3}}`
- 196438556: **11 lineup(s) contain a player this shadow field never rosters -- their dupe estimates are UNDERSTATED, not evidence of uniqueness**
- 196438556: dupes exact `{'mean': 0.0, 'max': 0.0, 'n_over_guardrail': 0, 'guardrail': 20}` product `{'mean': 0.06, 'max': 0.62}`; salary left `{'ours': {'0': 12, '500': 3, '2500': 1, '3000': 4}, 'ours_mean': 2815.0, 'shadow_field_mean': 531.0}`; split `{'ours_pct': {'1-5': 5.0, '2-4': 30.0, '3-3': 40.0, '4-2': 25.0}, 'shadow_field_pct': {'1-5': 59.9, '2-4': 35.0, '3-3': 4.8, '4-2': 0.3}}`
  - CPT/FLEX ownership (150): Dak Prescott 40.7/45.7; CeeDee Lamb 20.8/52.5; George Pickens 15.2/54.3; Ryan Flournoy 2.0/64.2; Brandon Aubrey 3.8/58.8; Kenny Gainwell 2.3/59.4; Javonte Williams 12.3/42.7; KaVontae Turpin 0.1/23.9; Jalon Daniels 1.3/19.4; Ted Hurst III 0.1/19.8; Cade Otton 0.2/19.2; Jake Ferguson 0.7/16.9
### BLEND (sigma 0.25, anchor RMSE 21.48)
- 196438543: **16 lineup(s) contain a player this shadow field never rosters -- their dupe estimates are UNDERSTATED, not evidence of uniqueness**
- 196438543: dupes exact `{'mean': 197.6, 'max': 8941.2, 'n_over_guardrail': 40, 'guardrail': 20}` product `{'mean': 52.41, 'max': 995.23}`; salary left `{'ours': {'0': 64, '1000': 20, '500': 31, '1500': 7, '2000': 2, '3000': 25, '2500': 1}, 'ours_mean': 2163.0, 'shadow_field_mean': 401.0}`; split `{'ours_pct': {'1-5': 8.0, '2-4': 22.0, '3-3': 38.7, '4-2': 27.3, '5-1': 4.0}, 'shadow_field_pct': {'1-5': 25.9, '2-4': 42.9, '3-3': 27.0, '4-2': 4.2, '5-1': 0.0}}`
- 196438555: **2 lineup(s) contain a player this shadow field never rosters -- their dupe estimates are UNDERSTATED, not evidence of uniqueness**
- 196438555: dupes exact `{'mean': 81.9, 'max': 734.1, 'n_over_guardrail': 7, 'guardrail': 20}` product `{'mean': 11.46, 'max': 75.31}`; salary left `{'ours': {'0': 12, '500': 3, '2500': 1, '3000': 4}, 'ours_mean': 2815.0, 'shadow_field_mean': 401.0}`; split `{'ours_pct': {'1-5': 5.0, '2-4': 30.0, '3-3': 40.0, '4-2': 25.0}, 'shadow_field_pct': {'1-5': 25.9, '2-4': 42.9, '3-3': 27.0, '4-2': 4.2, '5-1': 0.0}}`
- 196438556: **2 lineup(s) contain a player this shadow field never rosters -- their dupe estimates are UNDERSTATED, not evidence of uniqueness**
- 196438556: dupes exact `{'mean': 81.9, 'max': 734.1, 'n_over_guardrail': 7, 'guardrail': 20}` product `{'mean': 11.46, 'max': 75.31}`; salary left `{'ours': {'0': 12, '500': 3, '2500': 1, '3000': 4}, 'ours_mean': 2815.0, 'shadow_field_mean': 401.0}`; split `{'ours_pct': {'1-5': 5.0, '2-4': 30.0, '3-3': 40.0, '4-2': 25.0}, 'shadow_field_pct': {'1-5': 25.9, '2-4': 42.9, '3-3': 27.0, '4-2': 4.2, '5-1': 0.0}}`
  - CPT/FLEX ownership (150): CeeDee Lamb 37.3/47.2; Dak Prescott 33.7/50.1; Cade Otton 3.7/57.5; Javonte Williams 9.9/41.7; Brandon Aubrey 3.3/47.2; Ryan Flournoy 0.5/38.7; George Pickens 3.9/30.0; Bucky Irving 2.9/28.7; Jalon Daniels 2.1/27.0; Kenny Gainwell 0.4/23.8; Jake Ferguson 1.5/21.7; KaVontae Turpin 0.0/19.3

### DUPE STACK (MC-DUPE-1 / MC-FIELD-1: PRODUCTION_CANDIDATE, NOT PROMOTED)
- E1 independent product x N; E2 E1 x ETR-seeded correlation factors (SEEDED_NOT_FITTED); E3 copies in the archetype-first generated field x N/K (linear scaling; "<x" = below resolution); E4 copies in the optimizer field x N/K_opt. Flag when E1 and E3 differ by more than 2x.
- **FC_ONLY** archetype-field calibration residual (pts) by phi `{'50.0': {'cpt': 0.739, 'flex': 4.176}, '200.0': {'cpt': 0.248, 'flex': 3.485}, '1000.0': {'cpt': 0.222, 'flex': 3.534}}`; salary left `{'mean': 1657, 'p50': 1200.0, 'share_0': 0.082, 'share_le_900': 0.393, 'share_1000_1900': 0.287}`
  - 196438543: mean `{'E1': 16.47, 'E2': 26.0, 'E3_lower_bound_mean': 23.34, 'E4': 58.35}`; flags `{'PLAYER_ABSENT_FROM_FIELD_TARGETS': 56, 'None': 73, 'E3_BELOW_RESOLUTION_E1_NOT': 10, 'E1_E3_DISAGREE_GT_2X': 11}`; E3 mean by phi `{'50.0': 22.93, '200.0': 23.34, '1000.0': 25.88}`
  - 196438555: mean `{'E1': 0.06, 'E2': 0.06, 'E3_lower_bound_mean': 0.0, 'E4': 0.0}`; flags `{'PLAYER_ABSENT_FROM_FIELD_TARGETS': 11, 'None': 9}`; E3 mean by phi `{'50.0': 0.1, '200.0': 0.0, '1000.0': 0.0}`
  - 196438556: mean `{'E1': 0.06, 'E2': 0.06, 'E3_lower_bound_mean': 0.0, 'E4': 0.0}`; flags `{'PLAYER_ABSENT_FROM_FIELD_TARGETS': 11, 'None': 9}`; E3 mean by phi `{'50.0': 0.1, '200.0': 0.0, '1000.0': 0.0}`
- **BLEND** archetype-field calibration residual (pts) by phi `{'50.0': {'cpt': 0.39, 'flex': 2.93}, '200.0': {'cpt': 0.213, 'flex': 2.462}, '1000.0': {'cpt': 0.065, 'flex': 2.247}}`; salary left `{'mean': 1549, 'p50': 1100.0, 'share_0': 0.062, 'share_le_900': 0.453, 'share_1000_1900': 0.256}`
  - 196438543: mean `{'E1': 52.41, 'E2': 78.9, 'E3_lower_bound_mean': 71.72, 'E4': 197.65}`; flags `{'None': 90, 'E1_E3_DISAGREE_GT_2X': 34, 'E3_BELOW_RESOLUTION_E1_NOT': 10, 'PLAYER_ABSENT_FROM_FIELD_TARGETS': 16}`; E3 mean by phi `{'50.0': 65.32, '200.0': 71.72, '1000.0': 68.89}`
  - 196438555: mean `{'E1': 11.46, 'E2': 19.61, 'E3_lower_bound_mean': 41.5, 'E4': 81.87}`; flags `{'None': 8, 'E1_E3_DISAGREE_GT_2X': 8, 'PLAYER_ABSENT_FROM_FIELD_TARGETS': 2, 'E3_BELOW_RESOLUTION_E1_NOT': 2}`; E3 mean by phi `{'50.0': 52.62, '200.0': 41.5, '1000.0': 39.24}`
  - 196438556: mean `{'E1': 11.46, 'E2': 19.61, 'E3_lower_bound_mean': 41.5, 'E4': 81.87}`; flags `{'None': 8, 'E1_E3_DISAGREE_GT_2X': 8, 'PLAYER_ABSENT_FROM_FIELD_TARGETS': 2, 'E3_BELOW_RESOLUTION_E1_NOT': 2}`; E3 mean by phi `{'50.0': 52.62, '200.0': 41.5, '1000.0': 39.24}`

### DUPE SALARY-LEFT SENSITIVITY (Cycle 1 FC-08 / FC-09 field-side anchors; SENSITIVITY, not a fitted model)
- NOT_RUN

## EXTERNAL
- Hard Rock: NOT CAPTURED HERE -- only after the football freeze, by the networked agent (docs/AGENT_OUTBOX.md); never fed back into the projection; no wager is recommended
- FC comparison (largest gaps; FC is never an input):
  - George Pickens (DAL WR): ours 11.7 vs FC 17.97 (ROLE_OR_VOLUME)
  - Bucky Irving (TB RB): ours 16.5 vs FC 10.31 (ROLE_OR_VOLUME)
  - CeeDee Lamb (DAL WR): ours 28.28 vs FC 22.11 (ROLE_OR_VOLUME)
  - Emeka Egbuka (TB WR): ours 11.99 vs FC 7.64 (ROLE_OR_VOLUME)
  - Kenny Gainwell (TB RB): ours 4.57 vs FC 8.92 (ROLE_OR_VOLUME)
  - Cade Otton (TB TE): ours 11.57 vs FC 7.28 (ROLE_OR_VOLUME)
  - Ryan Flournoy (DAL WR): ours 5.43 vs FC 9.31 (ROLE_OR_VOLUME)
  - KaVontae Turpin (DAL WR): ours 1.12 vs FC 4.53 (ROLE_OR_VOLUME)
  - Tyler Goodson (DAL RB): ours 4.43 vs FC 1.13 (ROLE_OR_VOLUME)
  - Payne Durham (TB TE): ours 2.73 vs FC 0.0 ()
  - Tez Johnson (TB WR): ours 1.07 vs FC 3.73 ()
  - Brevyn Spann-Ford (DAL TE): ours 2.54 vs FC 0.0 ()
- video claims: NOT_PROVIDED_FOR_THIS_SLATE

## FILES
- `nfl/dfs/salaries/showdown_tb_dal/OFFICIAL/SHOWDOWN_TB_DAL_DK_UPLOAD_196438543.csv` -- 150 rows, sha256 `fa0e8d4c80219c1551862f37113011921c1b1c10ec4c958d90a10e9703757b24`
- `nfl/dfs/salaries/showdown_tb_dal/OFFICIAL/SHOWDOWN_TB_DAL_DK_UPLOAD_196438555.csv` -- 20 rows, sha256 `827d8b71a6a87b92d3e70cc62b49d0e1e6f7496ccd5b7b658bd6d9ca590200e9`
- `nfl/dfs/salaries/showdown_tb_dal/OFFICIAL/SHOWDOWN_TB_DAL_DK_UPLOAD_196438556.csv` -- 20 rows, sha256 `2764194c16ad3b71b131e75c1b08bf9dd75e4895ad8256b11ef056dec5f541fc`
- verifier: `{"n_rows": 190, "violations": []}`

nothing here enters a contest or uploads to DraftKings; PROJECTION_SYSTEM_STATE NOT_VALIDATED; no wager is recommended
