# ATL @ NO Showdown -- PRE-LOCK board (PRECOMPUTE_TBQB_MAYFIELD_R4)

**NOT_READY** -- blockers: OFFICIAL_INACTIVES_NOT_INCORPORATED

## FOOTBALL
- official inactives: `NOT YET INCORPORATED`
- starters: `{'Baker Mayfield': 'TB', 'Dak Prescott': 'DAL'}` (SCENARIO_HYPOTHESIS_NOT_CONFIRMED)
- state counts: `{'PROJECTED': 31, 'ZERO_OPPORTUNITY': 20, 'PROJECTED_WITH_UNCERTAINTY': 1}`
- football sanity: `{"state": "PASS", "code": "FOOTBALL_SANITY_PASS", "detail": "52 rows, 2 clubs, no football contradiction", "flags": null}`
- **SHOWDOWN_COHERENCE_WARNING** (measured, not fixed tonight): `{"ours_by_team": {"DAL": {"corr_team_td_vs_team_off_dk": 0.55, "corr_team_points_vs_team_off_dk": 0.486}, "TB": {"corr_team_td_vs_team_off_dk": 0.614, "corr_team_points_vs_team_off_dk": 0.541}}, "ours_corr_home_points_vs_away_points": 0.021, "ours_corr_home_off_dk_vs_away_off_dk": 0.139, "history_2021_2025": {"corr_team_td_vs_team_off_dk": 0.811, "corr_team_points_vs_team_off_dk": 0.763, "corr_home_points_vs_away_points": -0.038, "corr_home_off_dk_vs_away_off_dk": 0.181, "team_games": 2718}, "FINDING": "DEFECT-COHERENCE (measured 2026-10-05): within a simulated world, a team's offensive DK points track its touchdowns and points far more loosely than in 2021-25 games (see the numbers). The TD identity holds, so this is not broken accounting: yardage/receptions are drawn too independently of scoring. Effect: same-team boom-together is understated, so stacks are undervalued in the top tail. NOT fixed tonight (no validated fix before lock; the sealed football model is preserved); registered as the first post-lock football item."}`

| player | team | pos | salary | state | availability | desig | depth | mean | p90 | P(0) |
|---|---|---|---|---|---|---|---|---|---|---|
| CeeDee Lamb | DAL | WR | 11800 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 1 | 28.47 | 43.8 | 0.0 |
| Dak Prescott | DAL | QB | 10400 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 1 | 22.49 | 32.76 | 0.0 |
| Javonte Williams | DAL | RB | 10800 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 1 | 18.94 | 29.8 | 0.0 |
| Baker Mayfield | TB | QB | 9600 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 1 | 17.21 | 27.36 | 0.0 |
| Bucky Irving | TB | RB | 8400 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 1 | 15.24 | 25.24 | 0.0 |
| Emeka Egbuka | TB | WR | 8200 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 1 | 12.32 | 21.61 | 0.001 |
| Cade Otton | TB | TE | 4400 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 1 | 11.71 | 20.58 | 0.001 |
| George Pickens | DAL | WR | 9400 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 2 | 11.7 | 21.82 | 0.003 |
| Jake Ferguson | DAL | TE | 6400 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 1 | 10.1 | 18.17 | 0.004 |
| Brandon Aubrey | DAL | K | 5400 | PROJECTED | UNKNOWN_ACTIVE_STATE |  |  | 9.25 | 16.0 | 0.003 |
| Chris Godwin Jr. | TB | WR | 7200 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 2 | 8.76 | 16.15 | 0.011 |
| Chase McLaughlin | TB | K | 5000 | PROJECTED | UNKNOWN_ACTIVE_STATE |  |  | 7.99 | 14.0 | 0.035 |
| Ryan Flournoy | DAL | WR | 3800 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 3 | 5.35 | 11.21 | 0.043 |
| Kenny Gainwell | TB | RB | 4000 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 2 | 4.53 | 9.4 | 0.016 |
| Tyler Goodson | DAL | RB | 2000 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 2 | 4.38 | 9.49 | 0.014 |
| Buccaneers | TB | DST | 3000 | PROJECTED | UNKNOWN_ACTIVE_STATE |  |  | 4.31 | 11.68 | 0.284 |
| Cowboys | DAL | DST | 4800 | PROJECTED | UNKNOWN_ACTIVE_STATE |  |  | 3.91 | 8.0 | 0.085 |
| Ted Hurst III | TB | WR | 2800 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 3 | 3.9 | 8.73 | 0.089 |
| Payne Durham | TB | TE | 200 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 2 | 2.69 | 6.65 | 0.214 |
| Brevyn Spann-Ford | DAL | TE | 1600 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 2 | 2.51 | 6.57 | 0.259 |
| Sean Tucker | TB | RB | 2400 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 3 | 1.28 | 6.0 | 0.363 |
| KaVontae Turpin | DAL | WR | 1200 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 4 | 1.11 | 3.65 | 0.533 |
| Emari Demercado | DAL | RB | 400 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 3 | 1.1 | 3.28 | 0.393 |
| Tez Johnson | TB | WR | 2200 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 4 | 1.02 | 3.19 | 0.525 |

## PORTFOLIO
### 196438543 (150 entries)
- objective `{'m': 1, 'value': 0.9995, 'MEANING': 'E[min(entries at the first-place proxy, m)] per world'}`; proxy coverage 0.9995; method GREEDY_THEN_1SWAP_POLISH; polish `{'rounds': 1, 'lineups_changed': 0, 'objective_greedy': 0.9995, 'objective_final': 0.9995, 'coverage_greedy': 0.9995, 'coverage_final': 0.9995}`
- distinct captains 14; effective hypotheses 90.7; shared players between pairs `{'max': 4, 'distribution': {0: 307, 1: 2026, 2: 4322, 3: 3335, 4: 1185}}`
- captain exposure `{'Javonte Williams': 25.3, 'CeeDee Lamb': 23.3, 'Baker Mayfield': 11.3, 'Dak Prescott': 8.7, 'Bucky Irving': 8.0, 'Emeka Egbuka': 5.3, 'Brandon Aubrey': 4.7, 'Chris Godwin Jr.': 2.7, 'Buccaneers': 2.7, 'George Pickens': 2.0, 'Jake Ferguson': 2.0, 'Chase McLaughlin': 2.0, 'Cade Otton': 1.3, 'Ted Hurst III': 0.7}`
- player exposure `{'CeeDee Lamb': 50.0, 'Dak Prescott': 50.0, 'Javonte Williams': 50.0, 'Baker Mayfield': 50.0, 'Bucky Irving': 50.0, 'Cade Otton': 46.0, 'Brandon Aubrey': 42.7, 'Emeka Egbuka': 41.3, 'George Pickens': 32.0, 'Chase McLaughlin': 30.7, 'Jake Ferguson': 28.7, 'Chris Godwin Jr.': 25.3, 'Buccaneers': 20.7, 'Tyler Goodson': 20.0, 'Ryan Flournoy': 13.3}`
- RELAXATION: level 0; rungs L0 caps {'player': 75, 'captain': 45, 'overlap': 4} built 150/150 EHC 90.7
  - above the original cap: `{}`; captains `{}`
  - lineups not in the level-0 build: 0; clusters `{'by_origin': {}, 'by_captain': {}, 'by_split': {}, 'by_salary_band': {}}`
  - why: no relaxation needed: level 0 built 150/150
  - effective hypotheses (rungs are GREEDY rebuilds, before the swap polish): last unfilled rung None -> filled rung 90.7; final polished portfolio 90.7
- salary-relief slots used: `{'KaVontae Turpin': 1, 'Garrett Greene': 1}`
### 196438555 (20 entries)
- objective `{'m': 2, 'value': 1.097, 'MEANING': 'E[min(entries at the first-place proxy, m)] per world'}`; proxy coverage 0.693; method GREEDY_THEN_1SWAP_POLISH; polish `{'rounds': 1, 'lineups_changed': 0, 'objective_greedy': 1.097, 'objective_final': 1.097, 'coverage_greedy': 0.693, 'coverage_final': 0.693}`
- distinct captains 8; effective hypotheses 17.2; shared players between pairs `{'max': 4, 'distribution': {0: 14, 1: 40, 2: 48, 3: 54, 4: 34}}`
- captain exposure `{'CeeDee Lamb': 30.0, 'Javonte Williams': 20.0, 'Bucky Irving': 15.0, 'Dak Prescott': 10.0, 'Brandon Aubrey': 10.0, 'Baker Mayfield': 5.0, 'Buccaneers': 5.0, 'Jake Ferguson': 5.0}`
- player exposure `{'CeeDee Lamb': 50.0, 'Cade Otton': 50.0, 'Dak Prescott': 50.0, 'Javonte Williams': 50.0, 'Baker Mayfield': 50.0, 'Bucky Irving': 50.0, 'Brandon Aubrey': 50.0, 'Emeka Egbuka': 45.0, 'Jake Ferguson': 35.0, 'Chase McLaughlin': 30.0, 'Tyler Goodson': 30.0, 'Buccaneers': 30.0, 'Payne Durham': 25.0, 'Chris Godwin Jr.': 20.0, 'George Pickens': 10.0}`
- RELAXATION: level 0; rungs L0 caps {'player': 10, 'captain': 6, 'overlap': 4} built 20/20 EHC 17.2
  - above the original cap: `{}`; captains `{}`
  - lineups not in the level-0 build: 1; clusters `{'by_origin': {'RELAXATION': 1}, 'by_captain': {'Jake Ferguson': 1}, 'by_split': {'3-3': 1}, 'by_salary_band': {'<48000': 1}}`
  - why: no relaxation needed: level 0 built 20/20
  - effective hypotheses (rungs are GREEDY rebuilds, before the swap polish): last unfilled rung None -> filled rung 17.2; final polished portfolio 17.2
- salary-relief slots used: `{}`
### 196438556 (20 entries)
- objective `{'m': 2, 'value': 1.097, 'MEANING': 'E[min(entries at the first-place proxy, m)] per world'}`; proxy coverage 0.693; method GREEDY_THEN_1SWAP_POLISH; polish `{'rounds': 1, 'lineups_changed': 0, 'objective_greedy': 1.097, 'objective_final': 1.097, 'coverage_greedy': 0.693, 'coverage_final': 0.693}`
- distinct captains 8; effective hypotheses 17.2; shared players between pairs `{'max': 4, 'distribution': {0: 14, 1: 40, 2: 48, 3: 54, 4: 34}}`
- captain exposure `{'CeeDee Lamb': 30.0, 'Javonte Williams': 20.0, 'Bucky Irving': 15.0, 'Dak Prescott': 10.0, 'Brandon Aubrey': 10.0, 'Baker Mayfield': 5.0, 'Buccaneers': 5.0, 'Jake Ferguson': 5.0}`
- player exposure `{'CeeDee Lamb': 50.0, 'Cade Otton': 50.0, 'Dak Prescott': 50.0, 'Javonte Williams': 50.0, 'Baker Mayfield': 50.0, 'Bucky Irving': 50.0, 'Brandon Aubrey': 50.0, 'Emeka Egbuka': 45.0, 'Jake Ferguson': 35.0, 'Chase McLaughlin': 30.0, 'Tyler Goodson': 30.0, 'Buccaneers': 30.0, 'Payne Durham': 25.0, 'Chris Godwin Jr.': 20.0, 'George Pickens': 10.0}`
- RELAXATION: level 0; rungs L0 caps {'player': 10, 'captain': 6, 'overlap': 4} built 20/20 EHC 17.2
  - above the original cap: `{}`; captains `{}`
  - lineups not in the level-0 build: 1; clusters `{'by_origin': {'RELAXATION': 1}, 'by_captain': {'Jake Ferguson': 1}, 'by_split': {'3-3': 1}, 'by_salary_band': {'<48000': 1}}`
  - why: no relaxation needed: level 0 built 20/20
  - effective hypotheses (rungs are GREEDY rebuilds, before the swap polish): last unfilled rung None -> filled rung 17.2; final polished portfolio 17.2
- salary-relief slots used: `{}`

## FIELD (EXTERNAL_RESEARCH_SHADOW, UNVALIDATED)
- NOT_PROMOTED. Both field projections are EXTERNAL_RESEARCH_SHADOW and UNVALIDATED; the blend fits five unverified anchors better, which is not validation. Neither feeds the football or the production portfolio.
### FC_ONLY (sigma 0.25, anchor RMSE 21.48)
- 196438543: **107 lineup(s) contain a player this shadow field never rosters -- their dupe estimates are UNDERSTATED, not evidence of uniqueness**
- 196438543: dupes exact `{'mean': 23.5, 'max': 1647.1, 'n_over_guardrail': 6, 'guardrail': 20}` product `{'mean': 7.26, 'max': 484.12}`; salary left `{'ours': {'0': 98, '500': 24, '1500': 9, '1000': 6, '2000': 1, '2500': 1, '3000': 11}, 'ours_mean': 1191.0, 'shadow_field_mean': 522.0}`; split `{'ours_pct': {'1-5': 4.7, '2-4': 27.3, '3-3': 40.0, '4-2': 22.7, '5-1': 5.3}, 'shadow_field_pct': {'1-5': 53.1, '2-4': 39.4, '3-3': 7.0, '4-2': 0.5}}`
- 196438555: **15 lineup(s) contain a player this shadow field never rosters -- their dupe estimates are UNDERSTATED, not evidence of uniqueness**
- 196438555: dupes exact `{'mean': 0.0, 'max': 0.0, 'n_over_guardrail': 0, 'guardrail': 20}` product `{'mean': 0.13, 'max': 2.39}`; salary left `{'ours': {'0': 11, '500': 3, '1000': 2, '3000': 4}, 'ours_mean': 2825.0, 'shadow_field_mean': 522.0}`; split `{'ours_pct': {'2-4': 30.0, '3-3': 40.0, '4-2': 25.0, '5-1': 5.0}, 'shadow_field_pct': {'1-5': 53.1, '2-4': 39.4, '3-3': 7.0, '4-2': 0.5}}`
- 196438556: **15 lineup(s) contain a player this shadow field never rosters -- their dupe estimates are UNDERSTATED, not evidence of uniqueness**
- 196438556: dupes exact `{'mean': 0.0, 'max': 0.0, 'n_over_guardrail': 0, 'guardrail': 20}` product `{'mean': 0.13, 'max': 2.39}`; salary left `{'ours': {'0': 11, '500': 3, '1000': 2, '3000': 4}, 'ours_mean': 2825.0, 'shadow_field_mean': 522.0}`; split `{'ours_pct': {'2-4': 30.0, '3-3': 40.0, '4-2': 25.0, '5-1': 5.0}, 'shadow_field_pct': {'1-5': 53.1, '2-4': 39.4, '3-3': 7.0, '4-2': 0.5}}`
  - CPT/FLEX ownership (150): Dak Prescott 40.2/45.9; CeeDee Lamb 21.1/51.6; George Pickens 14.9/53.4; Ryan Flournoy 2.2/63.4; Kenny Gainwell 2.6/61.0; Brandon Aubrey 3.4/56.1; Javonte Williams 12.4/41.4; Jalon Daniels 1.5/21.6; KaVontae Turpin 0.1/22.2; Ted Hurst III 0.1/20.5; Cade Otton 0.3/19.8; Jake Ferguson 0.7/16.3
### BLEND (sigma 0.25, anchor RMSE 21.48)
- 196438543: **3 lineup(s) contain a player this shadow field never rosters -- their dupe estimates are UNDERSTATED, not evidence of uniqueness**
- 196438543: dupes exact `{'mean': 178.8, 'max': 8282.3, 'n_over_guardrail': 30, 'guardrail': 20}` product `{'mean': 43.2, 'max': 1152.33}`; salary left `{'ours': {'0': 98, '500': 24, '1500': 9, '1000': 6, '2000': 1, '2500': 1, '3000': 11}, 'ours_mean': 1191.0, 'shadow_field_mean': 426.0}`; split `{'ours_pct': {'1-5': 4.7, '2-4': 27.3, '3-3': 40.0, '4-2': 22.7, '5-1': 5.3}, 'shadow_field_pct': {'1-5': 29.4, '2-4': 47.0, '3-3': 21.2, '4-2': 2.4, '5-1': 0.0}}`
- 196438555: dupes exact `{'mean': 54.6, 'max': 856.5, 'n_over_guardrail': 4, 'guardrail': 20}` product `{'mean': 8.37, 'max': 83.01}`; salary left `{'ours': {'0': 11, '500': 3, '1000': 2, '3000': 4}, 'ours_mean': 2825.0, 'shadow_field_mean': 426.0}`; split `{'ours_pct': {'2-4': 30.0, '3-3': 40.0, '4-2': 25.0, '5-1': 5.0}, 'shadow_field_pct': {'1-5': 29.4, '2-4': 47.0, '3-3': 21.2, '4-2': 2.4, '5-1': 0.0}}`
- 196438556: dupes exact `{'mean': 54.6, 'max': 856.5, 'n_over_guardrail': 4, 'guardrail': 20}` product `{'mean': 8.37, 'max': 83.01}`; salary left `{'ours': {'0': 11, '500': 3, '1000': 2, '3000': 4}, 'ours_mean': 2825.0, 'shadow_field_mean': 426.0}`; split `{'ours_pct': {'2-4': 30.0, '3-3': 40.0, '4-2': 25.0, '5-1': 5.0}, 'shadow_field_pct': {'1-5': 29.4, '2-4': 47.0, '3-3': 21.2, '4-2': 2.4, '5-1': 0.0}}`
  - CPT/FLEX ownership (150): CeeDee Lamb 38.8/48.0; Dak Prescott 32.9/53.1; Cade Otton 4.1/62.7; Javonte Williams 11.0/46.2; Brandon Aubrey 2.9/47.1; Ryan Flournoy 0.5/39.4; George Pickens 3.8/33.3; Bucky Irving 2.8/28.7; Kenny Gainwell 0.3/25.9; Jake Ferguson 1.8/22.5; Ted Hurst III 0.1/20.9; Chase McLaughlin 0.3/18.7

### DUPE STACK (MC-DUPE-1 / MC-FIELD-1: PRODUCTION_CANDIDATE, NOT PROMOTED)
- E1 independent product x N; E2 E1 x ETR-seeded correlation factors (SEEDED_NOT_FITTED); E3 copies in the archetype-first generated field x N/K (linear scaling; "<x" = below resolution); E4 copies in the optimizer field x N/K_opt. Flag when E1 and E3 differ by more than 2x.
- **FC_ONLY** archetype-field calibration residual (pts) by phi `{'50.0': {'cpt': 0.465, 'flex': 3.995}, '200.0': {'cpt': 0.29, 'flex': 4.014}, '1000.0': {'cpt': 0.162, 'flex': 3.711}}`; salary left `{'mean': 1670, 'p50': 1200.0, 'share_0': 0.076, 'share_le_900': 0.392, 'share_1000_1900': 0.286}`
  - 196438543: mean `{'E1': 7.26, 'E2': 9.27, 'E3_lower_bound_mean': 4.61, 'E4': 23.53}`; flags `{'PLAYER_ABSENT_FROM_FIELD_TARGETS': 107, 'None': 34, 'E1_E3_DISAGREE_GT_2X': 7, 'E3_BELOW_RESOLUTION_E1_NOT': 2}`; E3 mean by phi `{'50.0': 5.27, '200.0': 4.61, '1000.0': 6.02}`
  - 196438555: mean `{'E1': 0.13, 'E2': 0.13, 'E3_lower_bound_mean': 0.0, 'E4': 0.0}`; flags `{'PLAYER_ABSENT_FROM_FIELD_TARGETS': 15, 'None': 4, 'E3_BELOW_RESOLUTION_E1_NOT': 1}`; E3 mean by phi `{'50.0': 0.0, '200.0': 0.0, '1000.0': 0.0}`
  - 196438556: mean `{'E1': 0.13, 'E2': 0.13, 'E3_lower_bound_mean': 0.0, 'E4': 0.0}`; flags `{'PLAYER_ABSENT_FROM_FIELD_TARGETS': 15, 'None': 4, 'E3_BELOW_RESOLUTION_E1_NOT': 1}`; E3 mean by phi `{'50.0': 0.0, '200.0': 0.0, '1000.0': 0.0}`
- **BLEND** archetype-field calibration residual (pts) by phi `{'50.0': {'cpt': 0.235, 'flex': 3.103}, '200.0': {'cpt': 0.291, 'flex': 2.579}, '1000.0': {'cpt': 0.137, 'flex': 2.332}}`; salary left `{'mean': 1579, 'p50': 1100.0, 'share_0': 0.059, 'share_le_900': 0.451, 'share_1000_1900': 0.259}`
  - 196438543: mean `{'E1': 43.2, 'E2': 66.28, 'E3_lower_bound_mean': 53.3, 'E4': 178.83}`; flags `{'E1_E3_DISAGREE_GT_2X': 28, 'E3_BELOW_RESOLUTION_E1_NOT': 13, 'None': 106, 'PLAYER_ABSENT_FROM_FIELD_TARGETS': 3}`; E3 mean by phi `{'50.0': 58.63, '200.0': 53.3, '1000.0': 59.73}`
  - 196438555: mean `{'E1': 8.37, 'E2': 14.45, 'E3_lower_bound_mean': 20.18, 'E4': 54.59}`; flags `{'E1_E3_DISAGREE_GT_2X': 5, 'E3_BELOW_RESOLUTION_E1_NOT': 2, 'None': 13}`; E3 mean by phi `{'50.0': 23.43, '200.0': 20.18, '1000.0': 23.9}`
  - 196438556: mean `{'E1': 8.37, 'E2': 14.45, 'E3_lower_bound_mean': 20.18, 'E4': 54.59}`; flags `{'E1_E3_DISAGREE_GT_2X': 5, 'E3_BELOW_RESOLUTION_E1_NOT': 2, 'None': 13}`; E3 mean by phi `{'50.0': 23.43, '200.0': 20.18, '1000.0': 23.9}`

### DUPE SALARY-LEFT SENSITIVITY (Cycle 1 FC-08 / FC-09 field-side anchors; SENSITIVITY, not a fitted model)
- NOT_RUN

## EXTERNAL
- Hard Rock: NOT CAPTURED HERE -- only after the football freeze, by the networked agent (docs/AGENT_OUTBOX.md); never fed back into the projection; no wager is recommended
- FC comparison (largest gaps; FC is never an input):
  - Baker Mayfield (TB QB): ours 17.21 vs FC 0.0 (DEPTH_OR_DATA (FC zero is not an inactive signal))
  - Jalon Daniels (TB QB): ours 0.06 vs FC 12.25 (ROLE_OR_VOLUME)
  - CeeDee Lamb (DAL WR): ours 28.47 vs FC 21.74 (ROLE_OR_VOLUME)
  - George Pickens (DAL WR): ours 11.7 vs FC 17.64 (ROLE_OR_VOLUME)
  - Bucky Irving (TB RB): ours 15.24 vs FC 10.51 (ROLE_OR_VOLUME)
  - Kenny Gainwell (TB RB): ours 4.53 vs FC 9.09 (ROLE_OR_VOLUME)
  - Emeka Egbuka (TB WR): ours 12.32 vs FC 7.79 (ROLE_OR_VOLUME)
  - Cade Otton (TB TE): ours 11.71 vs FC 7.37 (ROLE_OR_VOLUME)
  - Ryan Flournoy (DAL WR): ours 5.35 vs FC 9.19 (ROLE_OR_VOLUME)
  - KaVontae Turpin (DAL WR): ours 1.11 vs FC 4.41 (ROLE_OR_VOLUME)
  - Tyler Goodson (DAL RB): ours 4.38 vs FC 1.11 (ROLE_OR_VOLUME)
  - Tez Johnson (TB WR): ours 1.02 vs FC 3.77 ()
- video claims: NOT_PROVIDED_FOR_THIS_SLATE

## FILES
- `nfl/dfs/salaries/showdown_tb_dal/PRECOMPUTE_TBQB_MAYFIELD_R4/SHOWDOWN_TB_DAL_DK_UPLOAD_196438543.csv` -- 150 rows, sha256 `41ba84a759a5a1ce4944ae4dfacc048bdd911232d48ab203635678e749361b2f`
- `nfl/dfs/salaries/showdown_tb_dal/PRECOMPUTE_TBQB_MAYFIELD_R4/SHOWDOWN_TB_DAL_DK_UPLOAD_196438555.csv` -- 20 rows, sha256 `6f337e39ee7f545d7db39984cfdaf3a5f1ab232d9c777415f56d05e78fa45800`
- `nfl/dfs/salaries/showdown_tb_dal/PRECOMPUTE_TBQB_MAYFIELD_R4/SHOWDOWN_TB_DAL_DK_UPLOAD_196438556.csv` -- 20 rows, sha256 `faae6a2146a6069e286d4e7d6f0c1b0d5c0a568795f8866b2886d780ab151339`
- verifier: `{"n_rows": 190, "violations": []}`

nothing here enters a contest or uploads to DraftKings; PROJECTION_SYSTEM_STATE NOT_VALIDATED; no wager is recommended
