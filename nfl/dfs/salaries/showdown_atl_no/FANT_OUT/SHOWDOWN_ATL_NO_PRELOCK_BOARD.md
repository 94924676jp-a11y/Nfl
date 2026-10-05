# ATL @ NO Showdown -- PRE-LOCK board (FANT_OUT)

**NOT_READY** -- blockers: OFFICIAL_INACTIVES_NOT_INCORPORATED

## FOOTBALL
- official inactives: `NOT YET INCORPORATED`
- starters: `{'Michael Penix Jr.': 'ATL', 'Tyler Shough': 'NO'}` (PUBLIC_DEPTH_CHART_AND_SNAPS_CITED)
- state counts: `{'PROJECTED': 29, 'ZERO_OPPORTUNITY': 5, 'INACTIVE': 22}`
- football sanity: `{"state": "PASS", "code": "FOOTBALL_SANITY_PASS", "detail": "56 rows, 2 clubs, no football contradiction", "flags": null}`

| player | team | pos | salary | state | availability | desig | depth | mean | p90 | P(0) |
|---|---|---|---|---|---|---|---|---|---|---|
| Bijan Robinson | ATL | RB | 11800 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 1 | 26.24 | 39.11 | 0.0 |
| Chris Olave | NO | WR | 10800 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 1 | 25.55 | 39.29 | 0.0 |
| Tyler Shough | NO | QB | 9600 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 1 | 22.23 | 33.48 | 0.0 |
| Drake London | ATL | WR | 10000 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 1 | 20.13 | 33.65 | 0.0 |
| Juwan Johnson | NO | TE | 7400 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 1 | 15.94 | 27.86 | 0.001 |
| Michael Penix Jr. | ATL | QB | 9000 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 1 | 15.3 | 24.11 | 0.0 |
| Alvin Kamara | NO | RB | 7000 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 1 | 13.98 | 22.73 | 0.0 |
| Devaughn Vele | NO | WR | 7800 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 2 | 11.18 | 20.44 | 0.004 |
| Daniel Carlson | NO | K | 4800 | PROJECTED | UNKNOWN_ACTIVE_STATE |  |  | 8.53 | 15.0 | 0.02 |
| Nick Folk | ATL | K | 5400 | PROJECTED | UNKNOWN_ACTIVE_STATE |  |  | 8.17 | 15.0 | 0.051 |
| Saints | NO | DST | 4200 | PROJECTED | UNKNOWN_ACTIVE_STATE |  |  | 6.55 | 13.55 | 0.056 |
| Falcons | ATL | DST | 3600 | PROJECTED | UNKNOWN_ACTIVE_STATE |  |  | 5.61 | 12.4 | 0.129 |
| Kyle Pitts Sr. | ATL | TE | 5800 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 1 | 5.15 | 10.43 | 0.024 |
| Brian Robinson Jr. | ATL | RB | 3800 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 2 | 4.74 | 9.26 | 0.009 |
| Jahan Dotson | ATL | WR | 3000 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 2 | 4.06 | 8.51 | 0.046 |
| Kendre Miller | NO | RB | 5000 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 2 | 3.77 | 8.22 | 0.014 |
| Austin Hooper | ATL | TE | 2800 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 1 | 3.6 | 8.46 | 0.128 |
| Bryce Lance | NO | WR | 1800 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 3 | 2.68 | 6.61 | 0.172 |
| Olamide Zaccheaus | ATL | WR | 2000 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 3 | 2.45 | 6.0 | 0.171 |
| Treyton Welch | NO | TE | 200 | PROJECTED | UNKNOWN_ACTIVE_STATE |  |  | 1.57 | 4.58 | 0.395 |

## PORTFOLIO
### 196285137 (150 entries)
- objective `{'m': 3, 'value': 2.9665, 'MEANING': 'E[min(entries at the first-place proxy, m)] per world'}`; proxy coverage 0.9995; method GREEDY_THEN_1SWAP_POLISH; polish `{'rounds': 22, 'lineups_changed': 21, 'objective_greedy': 2.9455, 'objective_final': 2.9665, 'coverage_greedy': 1.0, 'coverage_final': 0.9995}`
- distinct captains 16; effective hypotheses 64.1; shared players between pairs `{'max': 5, 'distribution': {0: 68, 1: 1380, 2: 4197, 3: 3999, 4: 1354, 5: 177}}`
- captain exposure `{'Bijan Robinson': 26.0, 'Chris Olave': 20.7, 'Drake London': 14.0, 'Tyler Shough': 8.7, 'Juwan Johnson': 6.0, 'Alvin Kamara': 5.3, 'Devaughn Vele': 4.7, 'Daniel Carlson': 3.3, 'Falcons': 2.0, 'Saints': 2.0, 'Michael Penix Jr.': 2.0, 'Brian Robinson Jr.': 1.3, 'Jahan Dotson': 1.3, 'Austin Hooper': 1.3, 'Kyle Pitts Sr.': 0.7, 'Nick Folk': 0.7}`
- player exposure `{'Tyler Shough': 65.3, 'Bijan Robinson': 64.7, 'Chris Olave': 58.7, 'Drake London': 52.0, 'Alvin Kamara': 44.7, 'Juwan Johnson': 44.0, 'Michael Penix Jr.': 39.3, 'Daniel Carlson': 35.3, 'Falcons': 28.0, 'Saints': 27.3, 'Nick Folk': 27.3, 'Devaughn Vele': 27.3, 'Treyton Welch': 17.3, 'Brian Robinson Jr.': 14.0, 'Jahan Dotson': 12.7}`
- RELAXATION: level 2; rungs L0 caps {'player': 75, 'captain': 45, 'overlap': 4} built 139/150 EHC 74.7; L1 caps {'player': 75, 'captain': 45, 'overlap': 5} built 143/150 EHC 68.8; L2 caps {'player': 98, 'captain': 45, 'overlap': 5} built 150/150 EHC 63.1
  - above the original cap: `{'Chris Olave': {'n': 88, 'final_pct': 58.7, 'orig_cap_n': 75, 'orig_cap_pct': 50.0}, 'Bijan Robinson': {'n': 97, 'final_pct': 64.7, 'orig_cap_n': 75, 'orig_cap_pct': 50.0}, 'Tyler Shough': {'n': 98, 'final_pct': 65.3, 'orig_cap_n': 75, 'orig_cap_pct': 50.0}, 'Drake London': {'n': 78, 'final_pct': 52.0, 'orig_cap_n': 75, 'orig_cap_pct': 50.0}}`; captains `{}`
  - lineups not in the level-0 build: 112; clusters `{'by_origin': {'SWAP_POLISH': 21, 'RELAXATION': 91}, 'by_captain': {'Bijan Robinson': 26, 'Chris Olave': 23, 'Drake London': 15, 'Tyler Shough': 10, 'Juwan Johnson': 8, 'Devaughn Vele': 6, 'Alvin Kamara': 6, 'Daniel Carlson': 5, 'Falcons': 3, 'Michael Penix Jr.': 3, 'Brian Robinson Jr.': 2, 'Saints': 2, 'Jahan Dotson': 1, 'Austin Hooper': 1, 'Nick Folk': 1}, 'by_split': {'2-4': 35, '3-3': 33, '1-5': 21, '4-2': 19, '5-1': 4}, 'by_salary_band': {'49500-49900': 60, '49000-49400': 23, '48000-48900': 14, '50000': 14, '<48000': 1}}`
  - why: level 0 built 139/150: under a 75-entry player cap, a 45-entry captain cap and at most 4 shared players, the lawful pool near the top-tail runs out of lineups that avoid the core (Tyler Shough, Bijan Robinson, Chris Olave, Drake London)
  - effective hypotheses (rungs are GREEDY rebuilds, before the swap polish): last unfilled rung 68.8 -> filled rung 63.1; final polished portfolio 64.1
- salary-relief slots used: `{'CJ Donaldson': 1, 'Kevin Austin Jr.': 6, 'Zachariah Branch': 1, 'Nick Muse': 1}`
### 196285160 (20 entries)
- objective `{'m': 2, 'value': 1.373, 'MEANING': 'E[min(entries at the first-place proxy, m)] per world'}`; proxy coverage 0.815; method GREEDY_THEN_1SWAP_POLISH; polish `{'rounds': 11, 'lineups_changed': 9, 'objective_greedy': 1.3205, 'objective_final': 1.373, 'coverage_greedy': 0.774, 'coverage_final': 0.815}`
- distinct captains 6; effective hypotheses 15.8; shared players between pairs `{'max': 5, 'distribution': {1: 14, 2: 65, 3: 58, 4: 50, 5: 3}}`
- captain exposure `{'Bijan Robinson': 30.0, 'Chris Olave': 25.0, 'Drake London': 20.0, 'Tyler Shough': 15.0, 'Juwan Johnson': 5.0, 'Alvin Kamara': 5.0}`
- player exposure `{'Chris Olave': 65.0, 'Bijan Robinson': 65.0, 'Tyler Shough': 65.0, 'Drake London': 60.0, 'Juwan Johnson': 55.0, 'Alvin Kamara': 55.0, 'Treyton Welch': 50.0, 'Daniel Carlson': 40.0, 'Falcons': 30.0, 'Michael Penix Jr.': 30.0, 'Saints': 25.0, 'Nick Folk': 20.0, 'Devaughn Vele': 15.0, 'Bryce Lance': 10.0, 'Austin Hooper': 5.0}`
- RELAXATION: level 2; rungs L0 caps {'player': 10, 'captain': 6, 'overlap': 4} built 17/20 EHC 14.3; L1 caps {'player': 10, 'captain': 6, 'overlap': 5} built 17/20 EHC 12.2; L2 caps {'player': 13, 'captain': 6, 'overlap': 5} built 20/20 EHC 14.0
  - above the original cap: `{'Chris Olave': {'n': 13, 'final_pct': 65.0, 'orig_cap_n': 10, 'orig_cap_pct': 50.0}, 'Bijan Robinson': {'n': 13, 'final_pct': 65.0, 'orig_cap_n': 10, 'orig_cap_pct': 50.0}, 'Juwan Johnson': {'n': 11, 'final_pct': 55.0, 'orig_cap_n': 10, 'orig_cap_pct': 50.0}, 'Tyler Shough': {'n': 13, 'final_pct': 65.0, 'orig_cap_n': 10, 'orig_cap_pct': 50.0}, 'Alvin Kamara': {'n': 11, 'final_pct': 55.0, 'orig_cap_n': 10, 'orig_cap_pct': 50.0}, 'Drake London': {'n': 12, 'final_pct': 60.0, 'orig_cap_n': 10, 'orig_cap_pct': 50.0}}`; captains `{}`
  - lineups not in the level-0 build: 11; clusters `{'by_origin': {'SWAP_POLISH': 7, 'RELAXATION': 4}, 'by_captain': {'Bijan Robinson': 3, 'Chris Olave': 3, 'Tyler Shough': 2, 'Juwan Johnson': 1, 'Alvin Kamara': 1, 'Drake London': 1}, 'by_split': {'2-4': 6, '4-2': 3, '1-5': 2}, 'by_salary_band': {'49500-49900': 8, '50000': 2, '49000-49400': 1}}`
  - why: level 0 built 17/20: under a 10-entry player cap, a 6-entry captain cap and at most 4 shared players, the lawful pool near the top-tail runs out of lineups that avoid the core (Chris Olave, Bijan Robinson, Tyler Shough, Drake London)
  - effective hypotheses (rungs are GREEDY rebuilds, before the swap polish): last unfilled rung 12.2 -> filled rung 14.0; final polished portfolio 15.8
- salary-relief slots used: `{}`
### 196285161 (2 entries)
- objective `{'m': 1, 'value': 0.322, 'MEANING': 'E[min(entries at the first-place proxy, m)] per world'}`; proxy coverage 0.322; method GREEDY_THEN_1SWAP_POLISH; polish `{'rounds': 1, 'lineups_changed': 0, 'objective_greedy': 0.322, 'objective_final': 0.322, 'coverage_greedy': 0.322, 'coverage_final': 0.322}`
- distinct captains 2; effective hypotheses 2.0; shared players between pairs `{'max': 4, 'distribution': {4: 1}}`
- captain exposure `{'Chris Olave': 50.0, 'Tyler Shough': 50.0}`
- player exposure `{'Chris Olave': 100.0, 'Juwan Johnson': 100.0, 'Treyton Welch': 100.0, 'Tyler Shough': 100.0, 'Bijan Robinson': 50.0, 'Daniel Carlson': 50.0, 'Alvin Kamara': 50.0, 'Drake London': 50.0}`
- RELAXATION: level 0; rungs L0 caps {'player': 2, 'captain': 2, 'overlap': 4} built 2/2 EHC 2.0
  - above the original cap: `{}`; captains `{}`
  - lineups not in the level-0 build: 0; clusters `{'by_origin': {}, 'by_captain': {}, 'by_split': {}, 'by_salary_band': {}}`
  - why: no relaxation needed: level 0 built 2/2
  - effective hypotheses (rungs are GREEDY rebuilds, before the swap polish): last unfilled rung None -> filled rung 2.0; final polished portfolio 2.0
- salary-relief slots used: `{}`
- **CPT Chris Olave** + Bijan Robinson, Daniel Carlson, Juwan Johnson, Treyton Welch, Tyler Shough -- $50000, mean 112.84, proxy 0.2105
- **CPT Tyler Shough** + Alvin Kamara, Chris Olave, Drake London, Juwan Johnson, Treyton Welch -- $49800, mean 110.51, proxy 0.17

## FIELD (EXTERNAL_RESEARCH_SHADOW, UNVALIDATED)
- NOT_PROMOTED. Both field projections are EXTERNAL_RESEARCH_SHADOW and UNVALIDATED; the blend fits five unverified anchors better, which is not validation. Neither feeds the football or the production portfolio.
### FC_ONLY (sigma 0.6, anchor RMSE 13.75)
- 196285137: **63 lineup(s) contain a player this shadow field never rosters -- their dupe estimates are UNDERSTATED, not evidence of uniqueness**
- 196285137: dupes exact `{'mean': 29.8, 'max': 376.5, 'n_over_guardrail': 45, 'guardrail': 20}` product `{'mean': 24.73, 'max': 368.82}`; salary left `{'ours': {'0': 89, '500': 42, '1000': 12, '1500': 4, '2000': 2, '2500': 1}, 'ours_mean': 467.0, 'shadow_field_mean': 1567.0}`; split `{'ours_pct': {'1-5': 16.7, '2-4': 28.0, '3-3': 35.3, '4-2': 16.7, '5-1': 3.3}, 'shadow_field_pct': {'1-5': 14.3, '2-4': 37.6, '3-3': 33.1, '4-2': 13.0, '5-1': 2.0}}`
- 196285160: **11 lineup(s) contain a player this shadow field never rosters -- their dupe estimates are UNDERSTATED, not evidence of uniqueness**
- 196285160: dupes exact `{'mean': 3.8, 'max': 18.8, 'n_over_guardrail': 0, 'guardrail': 20}` product `{'mean': 3.91, 'max': 24.77}`; salary left `{'ours': {'0': 17, '500': 3}, 'ours_mean': 280.0, 'shadow_field_mean': 1567.0}`; split `{'ours_pct': {'1-5': 30.0, '2-4': 35.0, '3-3': 20.0, '4-2': 15.0}, 'shadow_field_pct': {'1-5': 14.3, '2-4': 37.6, '3-3': 33.1, '4-2': 13.0, '5-1': 2.0}}`
- 196285161: **2 lineup(s) contain a player this shadow field never rosters -- their dupe estimates are UNDERSTATED, not evidence of uniqueness**
- 196285161: dupes exact `{'mean': 0.0, 'max': 0.0, 'n_over_guardrail': 0, 'guardrail': 20}` product `{'mean': 0.0, 'max': 0.0}`; salary left `{'ours': {'0': 2}, 'ours_mean': 100.0, 'shadow_field_mean': 1567.0}`; split `{'ours_pct': {'1-5': 100.0}, 'shadow_field_pct': {'1-5': 14.3, '2-4': 37.6, '3-3': 33.1, '4-2': 13.0, '5-1': 2.0}}`
  - CPT/FLEX ownership (150): Tyler Shough 22.5/45.9; Bijan Robinson 21.2/44.3; Chris Olave 13.2/39.7; Kevin Austin Jr. 1.7/50.9; Michael Penix Jr. 9.2/39.7; Alvin Kamara 7.4/39.7; Drake London 7.8/34.6; Juwan Johnson 5.7/32.7; Daniel Carlson 3.0/32.3; Devaughn Vele 4.1/28.0; Olamide Zaccheaus 0.8/25.3; Kyle Pitts Sr. 1.5/20.1
### BLEND (sigma 0.6, anchor RMSE 11.21)
- 196285137: **2 lineup(s) contain a player this shadow field never rosters -- their dupe estimates are UNDERSTATED, not evidence of uniqueness**
- 196285137: dupes exact `{'mean': 49.9, 'max': 470.6, 'n_over_guardrail': 75, 'guardrail': 20}` product `{'mean': 37.14, 'max': 282.69}`; salary left `{'ours': {'0': 89, '500': 42, '1000': 12, '1500': 4, '2000': 2, '2500': 1}, 'ours_mean': 467.0, 'shadow_field_mean': 1004.0}`; split `{'ours_pct': {'1-5': 16.7, '2-4': 28.0, '3-3': 35.3, '4-2': 16.7, '5-1': 3.3}, 'shadow_field_pct': {'1-5': 14.6, '2-4': 36.6, '3-3': 34.2, '4-2': 12.7, '5-1': 1.8}}`
- 196285160: dupes exact `{'mean': 16.0, 'max': 47.1, 'n_over_guardrail': 6, 'guardrail': 20}` product `{'mean': 8.73, 'max': 36.04}`; salary left `{'ours': {'0': 17, '500': 3}, 'ours_mean': 280.0, 'shadow_field_mean': 1004.0}`; split `{'ours_pct': {'1-5': 30.0, '2-4': 35.0, '3-3': 20.0, '4-2': 15.0}, 'shadow_field_pct': {'1-5': 14.6, '2-4': 36.6, '3-3': 34.2, '4-2': 12.7, '5-1': 1.8}}`
- 196285161: dupes exact `{'mean': 41.2, 'max': 47.1, 'n_over_guardrail': 2, 'guardrail': 20}` product `{'mean': 7.19, 'max': 7.45}`; salary left `{'ours': {'0': 2}, 'ours_mean': 100.0, 'shadow_field_mean': 1004.0}`; split `{'ours_pct': {'1-5': 100.0}, 'shadow_field_pct': {'1-5': 14.6, '2-4': 36.6, '3-3': 34.2, '4-2': 12.7, '5-1': 1.8}}`
  - CPT/FLEX ownership (150): Tyler Shough 19.9/44.0; Bijan Robinson 19.4/43.2; Chris Olave 17.3/40.7; Drake London 10.3/37.7; Alvin Kamara 7.1/39.0; Juwan Johnson 7.9/37.2; Michael Penix Jr. 7.8/36.9; Daniel Carlson 2.6/33.6; Kevin Austin Jr. 0.3/35.5; Devaughn Vele 3.3/25.4; Nick Folk 1.3/21.2; Olamide Zaccheaus 0.6/20.1

## EXTERNAL
- Hard Rock: NOT CAPTURED HERE -- only after the football freeze, by the networked agent (docs/AGENT_OUTBOX.md); never fed back into the projection; no wager is recommended
- FC comparison (largest gaps; FC is never an input):
  - Kevin Austin Jr. (NO WR): ours 0.78 vs FC 8.4 (ROLE_OR_VOLUME)
  - Chris Olave (NO WR): ours 25.55 vs FC 20.85 (EFFICIENCY_OR_TD)
  - Olamide Zaccheaus (ATL WR): ours 2.45 vs FC 6.6 (ROLE_OR_VOLUME)
  - Austin Hooper (ATL TE): ours 3.6 vs FC 0.0 (DEPTH_OR_DATA (FC zero is not an inactive signal))
  - Kyle Pitts Sr. (ATL TE): ours 5.15 vs FC 8.72 (ROLE_OR_VOLUME)
  - Drake London (ATL WR): ours 20.13 vs FC 16.91 (EFFICIENCY_OR_TD)
  - Tyler Shough (NO QB): ours 22.23 vs FC 25.2 ()
  - Charlie Woerner (ATL TE): ours 0.33 vs FC 2.55 ()
  - Michael Penix Jr. (ATL QB): ours 15.3 vs FC 17.37 ()
  - Juwan Johnson (NO TE): ours 15.94 vs FC 14.0 ()
  - Daniel Carlson (NO K): ours 8.53 vs FC 10.45 ()
  - Zachariah Branch (ATL WR): ours 0.76 vs FC 2.65 ()
- video claims compared: 20 (UNVERIFIED_EXTERNAL)

## FILES
- `nfl/dfs/salaries/showdown_atl_no/FANT_OUT/SHOWDOWN_ATL_NO_DK_UPLOAD_196285137.csv` -- 150 rows, sha256 `25a623b077cbb4ca83a96d0f964a310cb304d364110e25ce2df075a377464a79`
- `nfl/dfs/salaries/showdown_atl_no/FANT_OUT/SHOWDOWN_ATL_NO_DK_UPLOAD_196285160.csv` -- 20 rows, sha256 `fbc6a9e11b29dd740afb71b1f1be7e61587e5c4f844f6f42dc016544a2ccdf47`
- `nfl/dfs/salaries/showdown_atl_no/FANT_OUT/SHOWDOWN_ATL_NO_DK_UPLOAD_196285161.csv` -- 2 rows, sha256 `d706e7f38ca38fb625dc4431c22c7808fa99fe688b360b73a5e672d92d2dd1b3`
- verifier: `{"n_rows": 172, "violations": []}`

nothing here enters a contest or uploads to DraftKings; PROJECTION_SYSTEM_STATE NOT_VALIDATED; no wager is recommended
