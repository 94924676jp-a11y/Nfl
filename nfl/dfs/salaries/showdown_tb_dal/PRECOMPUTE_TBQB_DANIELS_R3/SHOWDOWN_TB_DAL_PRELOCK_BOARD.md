# ATL @ NO Showdown -- PRE-LOCK board (PRECOMPUTE_TBQB_DANIELS_R3)

**NOT_READY** -- blockers: OFFICIAL_INACTIVES_NOT_INCORPORATED

## FOOTBALL
- official inactives: `NOT YET INCORPORATED`
- starters: `{'Jalon Daniels': 'TB', 'Dak Prescott': 'DAL'}` (SCENARIO_HYPOTHESIS_NOT_CONFIRMED)
- state counts: `{'PROJECTED': 30, 'ZERO_OPPORTUNITY': 20, 'PROJECTED_WITH_UNCERTAINTY': 1, 'INACTIVE': 1}`
- football sanity: `{"state": "PASS", "code": "FOOTBALL_SANITY_PASS", "detail": "52 rows, 2 clubs, no football contradiction", "flags": null}`
- **SHOWDOWN_COHERENCE_WARNING** (measured, not fixed tonight): `{"ours_by_team": {"DAL": {"corr_team_td_vs_team_off_dk": 0.6, "corr_team_points_vs_team_off_dk": 0.546}, "TB": {"corr_team_td_vs_team_off_dk": 0.673, "corr_team_points_vs_team_off_dk": 0.588}}, "ours_corr_home_points_vs_away_points": 0.057, "ours_corr_home_off_dk_vs_away_off_dk": 0.193, "history_2021_2025": {"corr_team_td_vs_team_off_dk": 0.811, "corr_team_points_vs_team_off_dk": 0.763, "corr_home_points_vs_away_points": -0.038, "corr_home_off_dk_vs_away_off_dk": 0.181, "team_games": 2718}, "FINDING": "DEFECT-COHERENCE (measured 2026-10-05): within a simulated world, a team's offensive DK points track its touchdowns and points far more loosely than in 2021-25 games (see the numbers). The TD identity holds, so this is not broken accounting: yardage/receptions are drawn too independently of scoring. Effect: same-team boom-together is understated, so stacks are undervalued in the top tail. NOT fixed tonight (no validated fix before lock; the sealed football model is preserved); registered as the first post-lock football item."}`

| player | team | pos | salary | state | availability | desig | depth | mean | p90 | P(0) |
|---|---|---|---|---|---|---|---|---|---|---|
| CeeDee Lamb | DAL | WR | 11800 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 1 | 28.07 | 43.33 | 0.0 |
| Dak Prescott | DAL | QB | 10400 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 1 | 22.43 | 32.74 | 0.0 |
| Javonte Williams | DAL | RB | 10800 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 1 | 18.77 | 29.77 | 0.0 |
| Bucky Irving | TB | RB | 8400 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 1 | 15.95 | 25.7 | 0.0 |
| Jalon Daniels | TB | QB | 8600 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 1 | 14.06 | 22.92 | 0.0 |
| Emeka Egbuka | TB | WR | 8200 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 1 | 12.13 | 21.33 | 0.001 |
| George Pickens | DAL | WR | 9400 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 2 | 11.83 | 21.82 | 0.005 |
| Cade Otton | TB | TE | 4400 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 1 | 11.41 | 19.81 | 0.001 |
| Jake Ferguson | DAL | TE | 6400 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 1 | 10.43 | 18.88 | 0.004 |
| Brandon Aubrey | DAL | K | 5400 | PROJECTED | UNKNOWN_ACTIVE_STATE |  |  | 9.37 | 16.0 | 0.002 |
| Chris Godwin Jr. | TB | WR | 7200 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 2 | 8.69 | 15.59 | 0.011 |
| Chase McLaughlin | TB | K | 5000 | PROJECTED | UNKNOWN_ACTIVE_STATE |  |  | 8.1 | 14.1 | 0.033 |
| Ryan Flournoy | DAL | WR | 3800 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 3 | 5.4 | 11.65 | 0.053 |
| Kenny Gainwell | TB | RB | 4000 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 2 | 4.52 | 9.39 | 0.013 |
| Buccaneers | TB | DST | 3000 | PROJECTED | UNKNOWN_ACTIVE_STATE |  |  | 4.31 | 12.54 | 0.274 |
| Tyler Goodson | DAL | RB | 2000 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 2 | 4.26 | 9.16 | 0.017 |
| Cowboys | DAL | DST | 4800 | PROJECTED | UNKNOWN_ACTIVE_STATE |  |  | 3.91 | 7.77 | 0.074 |
| Ted Hurst III | TB | WR | 2800 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 3 | 3.82 | 8.6 | 0.095 |
| Payne Durham | TB | TE | 200 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 2 | 2.69 | 7.02 | 0.213 |
| Brevyn Spann-Ford | DAL | TE | 1600 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 2 | 2.55 | 6.78 | 0.269 |
| Sean Tucker | TB | RB | 2400 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 3 | 1.32 | 6.0 | 0.364 |
| KaVontae Turpin | DAL | WR | 1200 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 4 | 1.2 | 4.1 | 0.52 |
| Emari Demercado | DAL | RB | 400 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 3 | 1.15 | 3.29 | 0.379 |
| Tez Johnson | TB | WR | 2200 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 4 | 1.02 | 3.25 | 0.525 |

## PORTFOLIO
### 196438543 (150 entries)
- objective `{'m': 1, 'value': 1.0, 'MEANING': 'E[min(entries at the first-place proxy, m)] per world'}`; proxy coverage 1.0; method GREEDY_THEN_1SWAP_POLISH; polish `{'rounds': 2, 'lineups_changed': 1, 'objective_greedy': 0.9995, 'objective_final': 1.0, 'coverage_greedy': 0.9995, 'coverage_final': 1.0}`
- distinct captains 13; effective hypotheses 94.3; shared players between pairs `{'max': 4, 'distribution': {0: 295, 1: 1959, 2: 4282, 3: 3373, 4: 1266}}`
- captain exposure `{'CeeDee Lamb': 22.0, 'Javonte Williams': 16.7, 'Bucky Irving': 11.3, 'Dak Prescott': 10.0, 'Emeka Egbuka': 8.0, 'George Pickens': 6.7, 'Jalon Daniels': 6.7, 'Cade Otton': 5.3, 'Brandon Aubrey': 4.7, 'Buccaneers': 4.0, 'Jake Ferguson': 2.0, 'Chris Godwin Jr.': 2.0, 'Chase McLaughlin': 0.7}`
- player exposure `{'CeeDee Lamb': 50.0, 'Bucky Irving': 50.0, 'Cade Otton': 50.0, 'Dak Prescott': 50.0, 'Javonte Williams': 50.0, 'Jalon Daniels': 48.7, 'Emeka Egbuka': 42.0, 'Brandon Aubrey': 39.3, 'Chase McLaughlin': 35.3, 'George Pickens': 34.0, 'Jake Ferguson': 30.7, 'Chris Godwin Jr.': 23.3, 'Buccaneers': 20.0, 'Tyler Goodson': 14.0, 'Ryan Flournoy': 14.0}`
- RELAXATION: level 0; rungs L0 caps {'player': 75, 'captain': 45, 'overlap': 4} built 150/150 EHC 94.6
  - above the original cap: `{}`; captains `{}`
  - lineups not in the level-0 build: 60; clusters `{'by_origin': {'SWAP_POLISH': 1, 'RELAXATION': 59}, 'by_captain': {'Javonte Williams': 12, 'Bucky Irving': 7, 'CeeDee Lamb': 7, 'Dak Prescott': 6, 'George Pickens': 5, 'Emeka Egbuka': 5, 'Jalon Daniels': 5, 'Buccaneers': 4, 'Cade Otton': 3, 'Brandon Aubrey': 3, 'Jake Ferguson': 2, 'Chris Godwin Jr.': 1}, 'by_split': {'3-3': 22, '4-2': 19, '2-4': 11, '1-5': 6, '5-1': 2}, 'by_salary_band': {'49500-49900': 22, '<48000': 13, '49000-49400': 12, '50000': 7, '48000-48900': 6}}`
  - why: no relaxation needed: level 0 built 150/150
  - effective hypotheses (rungs are GREEDY rebuilds, before the swap polish): last unfilled rung None -> filled rung 94.6; final polished portfolio 94.3
- salary-relief slots used: `{'KaVontae Turpin': 3, 'Luke Schoonmaker': 1, 'Camden Brown': 1, 'CJ Dippre': 1}`
### 196438555 (20 entries)
- objective `{'m': 2, 'value': 1.0895, 'MEANING': 'E[min(entries at the first-place proxy, m)] per world'}`; proxy coverage 0.6855; method GREEDY_THEN_1SWAP_POLISH; polish `{'rounds': 3, 'lineups_changed': 2, 'objective_greedy': 1.068, 'objective_final': 1.0895, 'coverage_greedy': 0.675, 'coverage_final': 0.6855}`
- distinct captains 9; effective hypotheses 17.5; shared players between pairs `{'max': 4, 'distribution': {0: 13, 1: 43, 2: 44, 3: 54, 4: 36}}`
- captain exposure `{'CeeDee Lamb': 30.0, 'Javonte Williams': 30.0, 'Jalon Daniels': 10.0, 'Dak Prescott': 5.0, 'Cade Otton': 5.0, 'Bucky Irving': 5.0, 'George Pickens': 5.0, 'Brandon Aubrey': 5.0, 'Emeka Egbuka': 5.0}`
- player exposure `{'CeeDee Lamb': 50.0, 'Bucky Irving': 50.0, 'Cade Otton': 50.0, 'Dak Prescott': 50.0, 'Jalon Daniels': 50.0, 'Javonte Williams': 50.0, 'Brandon Aubrey': 50.0, 'Emeka Egbuka': 45.0, 'Jake Ferguson': 35.0, 'Chase McLaughlin': 35.0, 'Tyler Goodson': 30.0, 'George Pickens': 30.0, 'Buccaneers': 20.0, 'Payne Durham': 15.0, 'Chris Godwin Jr.': 15.0}`
- RELAXATION: level 0; rungs L0 caps {'player': 10, 'captain': 6, 'overlap': 4} built 20/20 EHC 17.3
  - above the original cap: `{}`; captains `{}`
  - lineups not in the level-0 build: 3; clusters `{'by_origin': {'SWAP_POLISH': 2, 'RELAXATION': 1}, 'by_captain': {'CeeDee Lamb': 1, 'Bucky Irving': 1, 'Jalon Daniels': 1}, 'by_split': {'4-2': 2, '2-4': 1}, 'by_salary_band': {'49500-49900': 1, '50000': 1, '<48000': 1}}`
  - why: no relaxation needed: level 0 built 20/20
  - effective hypotheses (rungs are GREEDY rebuilds, before the swap polish): last unfilled rung None -> filled rung 17.3; final polished portfolio 17.5
- salary-relief slots used: `{}`
### 196438556 (20 entries)
- objective `{'m': 2, 'value': 1.0895, 'MEANING': 'E[min(entries at the first-place proxy, m)] per world'}`; proxy coverage 0.6855; method GREEDY_THEN_1SWAP_POLISH; polish `{'rounds': 3, 'lineups_changed': 2, 'objective_greedy': 1.068, 'objective_final': 1.0895, 'coverage_greedy': 0.675, 'coverage_final': 0.6855}`
- distinct captains 9; effective hypotheses 17.5; shared players between pairs `{'max': 4, 'distribution': {0: 13, 1: 43, 2: 44, 3: 54, 4: 36}}`
- captain exposure `{'CeeDee Lamb': 30.0, 'Javonte Williams': 30.0, 'Jalon Daniels': 10.0, 'Dak Prescott': 5.0, 'Cade Otton': 5.0, 'Bucky Irving': 5.0, 'George Pickens': 5.0, 'Brandon Aubrey': 5.0, 'Emeka Egbuka': 5.0}`
- player exposure `{'CeeDee Lamb': 50.0, 'Bucky Irving': 50.0, 'Cade Otton': 50.0, 'Dak Prescott': 50.0, 'Jalon Daniels': 50.0, 'Javonte Williams': 50.0, 'Brandon Aubrey': 50.0, 'Emeka Egbuka': 45.0, 'Jake Ferguson': 35.0, 'Chase McLaughlin': 35.0, 'Tyler Goodson': 30.0, 'George Pickens': 30.0, 'Buccaneers': 20.0, 'Payne Durham': 15.0, 'Chris Godwin Jr.': 15.0}`
- RELAXATION: level 0; rungs L0 caps {'player': 10, 'captain': 6, 'overlap': 4} built 20/20 EHC 17.3
  - above the original cap: `{}`; captains `{}`
  - lineups not in the level-0 build: 3; clusters `{'by_origin': {'SWAP_POLISH': 2, 'RELAXATION': 1}, 'by_captain': {'CeeDee Lamb': 1, 'Bucky Irving': 1, 'Jalon Daniels': 1}, 'by_split': {'4-2': 2, '2-4': 1}, 'by_salary_band': {'49500-49900': 1, '50000': 1, '<48000': 1}}`
  - why: no relaxation needed: level 0 built 20/20
  - effective hypotheses (rungs are GREEDY rebuilds, before the swap polish): last unfilled rung None -> filled rung 17.3; final polished portfolio 17.5
- salary-relief slots used: `{}`

## FIELD (EXTERNAL_RESEARCH_SHADOW, UNVALIDATED)
- NOT_PROMOTED. Both field projections are EXTERNAL_RESEARCH_SHADOW and UNVALIDATED; the blend fits five unverified anchors better, which is not validation. Neither feeds the football or the production portfolio.
### FC_ONLY (sigma 0.25, anchor RMSE 21.48)
- 196438543: **55 lineup(s) contain a player this shadow field never rosters -- their dupe estimates are UNDERSTATED, not evidence of uniqueness**
- 196438543: dupes exact `{'mean': 39.8, 'max': 1788.2, 'n_over_guardrail': 11, 'guardrail': 20}` product `{'mean': 15.4, 'max': 445.75}`; salary left `{'ours': {'0': 76, '500': 34, '1000': 5, '1500': 6, '2000': 3, '3000': 24, '2500': 2}, 'ours_mean': 1757.0, 'shadow_field_mean': 522.0}`; split `{'ours_pct': {'1-5': 8.0, '2-4': 22.0, '3-3': 37.3, '4-2': 26.7, '5-1': 6.0}, 'shadow_field_pct': {'1-5': 53.1, '2-4': 39.4, '3-3': 7.0, '4-2': 0.5}}`
- 196438555: **10 lineup(s) contain a player this shadow field never rosters -- their dupe estimates are UNDERSTATED, not evidence of uniqueness**
- 196438555: dupes exact `{'mean': 0.0, 'max': 0.0, 'n_over_guardrail': 0, 'guardrail': 20}` product `{'mean': 0.49, 'max': 6.35}`; salary left `{'ours': {'0': 12, '500': 4, '1500': 1, '3000': 3}, 'ours_mean': 1755.0, 'shadow_field_mean': 522.0}`; split `{'ours_pct': {'2-4': 40.0, '3-3': 30.0, '4-2': 30.0}, 'shadow_field_pct': {'1-5': 53.1, '2-4': 39.4, '3-3': 7.0, '4-2': 0.5}}`
- 196438556: **10 lineup(s) contain a player this shadow field never rosters -- their dupe estimates are UNDERSTATED, not evidence of uniqueness**
- 196438556: dupes exact `{'mean': 0.0, 'max': 0.0, 'n_over_guardrail': 0, 'guardrail': 20}` product `{'mean': 0.49, 'max': 6.35}`; salary left `{'ours': {'0': 12, '500': 4, '1500': 1, '3000': 3}, 'ours_mean': 1755.0, 'shadow_field_mean': 522.0}`; split `{'ours_pct': {'2-4': 40.0, '3-3': 30.0, '4-2': 30.0}, 'shadow_field_pct': {'1-5': 53.1, '2-4': 39.4, '3-3': 7.0, '4-2': 0.5}}`
  - CPT/FLEX ownership (150): Dak Prescott 40.2/45.9; CeeDee Lamb 21.1/51.6; George Pickens 14.9/53.4; Ryan Flournoy 2.2/63.4; Kenny Gainwell 2.6/61.0; Brandon Aubrey 3.4/56.1; Javonte Williams 12.4/41.4; Jalon Daniels 1.5/21.6; KaVontae Turpin 0.1/22.2; Ted Hurst III 0.1/20.5; Cade Otton 0.3/19.8; Jake Ferguson 0.7/16.3
### BLEND (sigma 0.25, anchor RMSE 21.48)
- 196438543: **11 lineup(s) contain a player this shadow field never rosters -- their dupe estimates are UNDERSTATED, not evidence of uniqueness**
- 196438543: dupes exact `{'mean': 157.8, 'max': 4705.9, 'n_over_guardrail': 43, 'guardrail': 20}` product `{'mean': 42.7, 'max': 648.15}`; salary left `{'ours': {'0': 76, '500': 34, '1000': 5, '1500': 6, '2000': 3, '3000': 24, '2500': 2}, 'ours_mean': 1757.0, 'shadow_field_mean': 399.0}`; split `{'ours_pct': {'1-5': 8.0, '2-4': 22.0, '3-3': 37.3, '4-2': 26.7, '5-1': 6.0}, 'shadow_field_pct': {'1-5': 24.7, '2-4': 42.2, '3-3': 28.3, '4-2': 4.8, '5-1': 0.0}}`
- 196438555: dupes exact `{'mean': 70.6, 'max': 677.6, 'n_over_guardrail': 6, 'guardrail': 20}` product `{'mean': 14.82, 'max': 91.66}`; salary left `{'ours': {'0': 12, '500': 4, '1500': 1, '3000': 3}, 'ours_mean': 1755.0, 'shadow_field_mean': 399.0}`; split `{'ours_pct': {'2-4': 40.0, '3-3': 30.0, '4-2': 30.0}, 'shadow_field_pct': {'1-5': 24.7, '2-4': 42.2, '3-3': 28.3, '4-2': 4.8, '5-1': 0.0}}`
- 196438556: dupes exact `{'mean': 70.6, 'max': 677.6, 'n_over_guardrail': 6, 'guardrail': 20}` product `{'mean': 14.82, 'max': 91.66}`; salary left `{'ours': {'0': 12, '500': 4, '1500': 1, '3000': 3}, 'ours_mean': 1755.0, 'shadow_field_mean': 399.0}`; split `{'ours_pct': {'2-4': 40.0, '3-3': 30.0, '4-2': 30.0}, 'shadow_field_pct': {'1-5': 24.7, '2-4': 42.2, '3-3': 28.3, '4-2': 4.8, '5-1': 0.0}}`
  - CPT/FLEX ownership (150): CeeDee Lamb 36.9/47.0; Dak Prescott 33.8/49.4; Cade Otton 4.0/57.1; Javonte Williams 9.8/40.9; Brandon Aubrey 3.1/46.1; Ryan Flournoy 0.5/37.6; George Pickens 3.9/29.6; Jalon Daniels 2.2/28.8; Bucky Irving 2.8/27.7; Kenny Gainwell 0.5/25.1; Jake Ferguson 1.6/23.5; KaVontae Turpin 0.0/19.3

### DUPE STACK (MC-DUPE-1 / MC-FIELD-1: PRODUCTION_CANDIDATE, NOT PROMOTED)
- E1 independent product x N; E2 E1 x ETR-seeded correlation factors (SEEDED_NOT_FITTED); E3 copies in the archetype-first generated field x N/K (linear scaling; "<x" = below resolution); E4 copies in the optimizer field x N/K_opt. Flag when E1 and E3 differ by more than 2x.
- **FC_ONLY** archetype-field calibration residual (pts) by phi `{'50.0': {'cpt': 0.465, 'flex': 3.995}, '200.0': {'cpt': 0.29, 'flex': 4.014}, '1000.0': {'cpt': 0.162, 'flex': 3.711}}`; salary left `{'mean': 1670, 'p50': 1200.0, 'share_0': 0.076, 'share_le_900': 0.392, 'share_1000_1900': 0.286}`
  - 196438543: mean `{'E1': 15.4, 'E2': 17.46, 'E3_lower_bound_mean': 11.39, 'E4': 39.84}`; flags `{'PLAYER_ABSENT_FROM_FIELD_TARGETS': 55, 'None': 77, 'E3_BELOW_RESOLUTION_E1_NOT': 10, 'E1_E3_DISAGREE_GT_2X': 8}`; E3 mean by phi `{'50.0': 12.52, '200.0': 11.39, '1000.0': 11.83}`
  - 196438555: mean `{'E1': 0.49, 'E2': 0.82, 'E3_lower_bound_mean': 0.09, 'E4': 0.0}`; flags `{'PLAYER_ABSENT_FROM_FIELD_TARGETS': 10, 'None': 8, 'E1_E3_DISAGREE_GT_2X': 1, 'E3_BELOW_RESOLUTION_E1_NOT': 1}`; E3 mean by phi `{'50.0': 0.1, '200.0': 0.09, '1000.0': 0.0}`
  - 196438556: mean `{'E1': 0.49, 'E2': 0.82, 'E3_lower_bound_mean': 0.09, 'E4': 0.0}`; flags `{'PLAYER_ABSENT_FROM_FIELD_TARGETS': 10, 'None': 8, 'E1_E3_DISAGREE_GT_2X': 1, 'E3_BELOW_RESOLUTION_E1_NOT': 1}`; E3 mean by phi `{'50.0': 0.1, '200.0': 0.09, '1000.0': 0.0}`
- **BLEND** archetype-field calibration residual (pts) by phi `{'50.0': {'cpt': 0.323, 'flex': 2.865}, '200.0': {'cpt': 0.191, 'flex': 2.507}, '1000.0': {'cpt': 0.167, 'flex': 2.231}}`; salary left `{'mean': 1530, 'p50': 1100.0, 'share_0': 0.066, 'share_le_900': 0.462, 'share_1000_1900': 0.257}`
  - 196438543: mean `{'E1': 42.7, 'E2': 58.74, 'E3_lower_bound_mean': 48.15, 'E4': 157.81}`; flags `{'None': 84, 'E1_E3_DISAGREE_GT_2X': 40, 'E3_BELOW_RESOLUTION_E1_NOT': 15, 'PLAYER_ABSENT_FROM_FIELD_TARGETS': 11}`; E3 mean by phi `{'50.0': 50.63, '200.0': 48.15, '1000.0': 49.0}`
  - 196438555: mean `{'E1': 14.82, 'E2': 27.4, 'E3_lower_bound_mean': 36.05, 'E4': 70.58}`; flags `{'None': 12, 'E1_E3_DISAGREE_GT_2X': 7, 'E3_BELOW_RESOLUTION_E1_NOT': 1}`; E3 mean by phi `{'50.0': 32.74, '200.0': 36.05, '1000.0': 37.45}`
  - 196438556: mean `{'E1': 14.82, 'E2': 27.4, 'E3_lower_bound_mean': 36.05, 'E4': 70.58}`; flags `{'None': 12, 'E1_E3_DISAGREE_GT_2X': 7, 'E3_BELOW_RESOLUTION_E1_NOT': 1}`; E3 mean by phi `{'50.0': 32.74, '200.0': 36.05, '1000.0': 37.45}`

### DUPE SALARY-LEFT SENSITIVITY (Cycle 1 FC-08 / FC-09 field-side anchors; SENSITIVITY, not a fitted model)
- NOT_RUN

## EXTERNAL
- Hard Rock: NOT CAPTURED HERE -- only after the football freeze, by the networked agent (docs/AGENT_OUTBOX.md); never fed back into the projection; no wager is recommended
- FC comparison (largest gaps; FC is never an input):
  - CeeDee Lamb (DAL WR): ours 28.07 vs FC 21.74 (ROLE_OR_VOLUME)
  - George Pickens (DAL WR): ours 11.83 vs FC 17.64 (ROLE_OR_VOLUME)
  - Bucky Irving (TB RB): ours 15.95 vs FC 10.51 (ROLE_OR_VOLUME)
  - Kenny Gainwell (TB RB): ours 4.52 vs FC 9.09 (ROLE_OR_VOLUME)
  - Emeka Egbuka (TB WR): ours 12.13 vs FC 7.79 (ROLE_OR_VOLUME)
  - Cade Otton (TB TE): ours 11.41 vs FC 7.37 (ROLE_OR_VOLUME)
  - Ryan Flournoy (DAL WR): ours 5.4 vs FC 9.19 (ROLE_OR_VOLUME)
  - KaVontae Turpin (DAL WR): ours 1.2 vs FC 4.41 (ROLE_OR_VOLUME)
  - Tyler Goodson (DAL RB): ours 4.26 vs FC 1.11 (ROLE_OR_VOLUME)
  - Tez Johnson (TB WR): ours 1.02 vs FC 3.77 ()
  - Payne Durham (TB TE): ours 2.69 vs FC 0.0 ()
  - Brevyn Spann-Ford (DAL TE): ours 2.55 vs FC 0.0 ()
- video claims: NOT_PROVIDED_FOR_THIS_SLATE

## FILES
- `nfl/dfs/salaries/showdown_tb_dal/PRECOMPUTE_TBQB_DANIELS_R3/SHOWDOWN_TB_DAL_DK_UPLOAD_196438543.csv` -- 150 rows, sha256 `1ecd0ddd656de884bccbb48a5990be2faffec6355034ec56c9431118b2f6250c`
- `nfl/dfs/salaries/showdown_tb_dal/PRECOMPUTE_TBQB_DANIELS_R3/SHOWDOWN_TB_DAL_DK_UPLOAD_196438555.csv` -- 20 rows, sha256 `55a6f4f168be76b23ab48f07c1baa5f3617a1b778b844b1d79118997f3a2c1ca`
- `nfl/dfs/salaries/showdown_tb_dal/PRECOMPUTE_TBQB_DANIELS_R3/SHOWDOWN_TB_DAL_DK_UPLOAD_196438556.csv` -- 20 rows, sha256 `c762416687e3501f220ef4f59574df7da728c8a418c5469c431dcedd9686db29`
- verifier: `{"n_rows": 190, "violations": []}`

nothing here enters a contest or uploads to DraftKings; PROJECTION_SYSTEM_STATE NOT_VALIDATED; no wager is recommended
