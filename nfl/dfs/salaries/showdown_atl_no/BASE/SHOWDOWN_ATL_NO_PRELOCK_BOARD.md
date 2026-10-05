# ATL @ NO Showdown -- PRE-LOCK board (BASE)

**NOT_READY** -- blockers: OFFICIAL_INACTIVES_NOT_INCORPORATED

## FOOTBALL
- official inactives: `NOT YET INCORPORATED`
- starters: `{'Michael Penix Jr.': 'ATL', 'Tyler Shough': 'NO'}` (PUBLIC_DEPTH_CHART_AND_SNAPS_CITED)
- state counts: `{'PROJECTED': 27, 'ZERO_OPPORTUNITY': 7, 'INACTIVE': 21, 'PROJECTED_WITH_UNCERTAINTY': 1}`
- football sanity: `{"state": "PASS", "code": "FOOTBALL_SANITY_PASS", "detail": "56 rows, 2 clubs, no football contradiction", "flags": null}`

| player | team | pos | salary | state | availability | desig | depth | mean | p90 | P(0) |
|---|---|---|---|---|---|---|---|---|---|---|
| Bijan Robinson | ATL | RB | 11800 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 1 | 26.49 | 39.62 | 0.0 |
| Chris Olave | NO | WR | 10800 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 1 | 24.17 | 37.6 | 0.0 |
| Tyler Shough | NO | QB | 9600 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 1 | 22.17 | 33.31 | 0.0 |
| Drake London | ATL | WR | 10000 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 1 | 19.96 | 33.69 | 0.0 |
| Michael Penix Jr. | ATL | QB | 9000 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 1 | 15.35 | 24.21 | 0.0 |
| Juwan Johnson | NO | TE | 7400 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 1 | 15.32 | 26.38 | 0.0 |
| Alvin Kamara | NO | RB | 7000 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 1 | 13.28 | 21.36 | 0.0 |
| Devaughn Vele | NO | WR | 7800 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 2 | 10.49 | 18.89 | 0.002 |
| Daniel Carlson | NO | K | 4800 | PROJECTED | UNKNOWN_ACTIVE_STATE |  |  | 8.65 | 15.0 | 0.011 |
| Nick Folk | ATL | K | 5400 | PROJECTED | UNKNOWN_ACTIVE_STATE |  |  | 8.21 | 15.0 | 0.055 |
| Saints | NO | DST | 4200 | PROJECTED | UNKNOWN_ACTIVE_STATE |  |  | 6.55 | 13.53 | 0.058 |
| Falcons | ATL | DST | 3600 | PROJECTED | UNKNOWN_ACTIVE_STATE |  |  | 5.61 | 12.38 | 0.114 |
| Kyle Pitts Sr. | ATL | TE | 5800 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 1 | 4.98 | 9.88 | 0.021 |
| Noah Fant | NO | TE | 4400 | PROJECTED_WITH_UNCERTAINTY | UNKNOWN_ACTIVE_STATE | QUESTIONABLE | 2 | 4.92 | 10.19 | 0.056 |
| Brian Robinson Jr. | ATL | RB | 3800 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 2 | 4.9 | 9.67 | 0.007 |
| Jahan Dotson | ATL | WR | 3000 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 2 | 4.04 | 8.54 | 0.041 |
| Austin Hooper | ATL | TE | 2800 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 1 | 3.74 | 8.45 | 0.115 |
| Kendre Miller | NO | RB | 5000 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 2 | 3.58 | 7.9 | 0.021 |
| Bryce Lance | NO | WR | 1800 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 3 | 2.58 | 6.44 | 0.191 |
| Olamide Zaccheaus | ATL | WR | 2000 | PROJECTED | UNKNOWN_ACTIVE_STATE |  | 3 | 2.37 | 6.04 | 0.189 |

## PORTFOLIO
### 196285137 (150 entries)
- objective `{'m': 3, 'value': 2.9595, 'MEANING': 'E[min(entries at the first-place proxy, m)] per world'}`; proxy coverage 0.9995; method GREEDY_THEN_1SWAP_POLISH; polish `{'rounds': 24, 'lineups_changed': 22, 'objective_greedy': 2.934, 'objective_final': 2.9595, 'coverage_greedy': 1.0, 'coverage_final': 0.9995}`
- distinct captains 15; effective hypotheses 68.6; shared players between pairs `{'max': 5, 'distribution': {0: 85, 1: 1484, 2: 4309, 3: 3879, 4: 1287, 5: 131}}`
- captain exposure `{'Bijan Robinson': 25.3, 'Drake London': 19.3, 'Chris Olave': 15.3, 'Tyler Shough': 14.0, 'Juwan Johnson': 7.3, 'Alvin Kamara': 4.0, 'Falcons': 2.7, 'Devaughn Vele': 2.7, 'Michael Penix Jr.': 2.7, 'Daniel Carlson': 2.0, 'Noah Fant': 1.3, 'Saints': 1.3, 'Nick Folk': 0.7, 'Austin Hooper': 0.7, 'Brian Robinson Jr.': 0.7}`
- player exposure `{'Tyler Shough': 65.3, 'Bijan Robinson': 62.0, 'Chris Olave': 58.0, 'Drake London': 52.0, 'Michael Penix Jr.': 43.3, 'Alvin Kamara': 42.0, 'Juwan Johnson': 41.3, 'Daniel Carlson': 34.0, 'Falcons': 32.7, 'Nick Folk': 28.7, 'Saints': 27.3, 'Devaughn Vele': 22.0, 'Brian Robinson Jr.': 18.0, 'Austin Hooper': 15.3, 'Bryce Lance': 12.7}`
- RELAXATION: level 2; rungs L0 caps {'player': 75, 'captain': 45, 'overlap': 4} built 141/150 EHC 80.5; L1 caps {'player': 75, 'captain': 45, 'overlap': 5} built 144/150 EHC 70.7; L2 caps {'player': 98, 'captain': 45, 'overlap': 5} built 150/150 EHC 66.3
  - above the original cap: `{'Chris Olave': {'n': 87, 'final_pct': 58.0, 'orig_cap_n': 75, 'orig_cap_pct': 50.0}, 'Bijan Robinson': {'n': 93, 'final_pct': 62.0, 'orig_cap_n': 75, 'orig_cap_pct': 50.0}, 'Tyler Shough': {'n': 98, 'final_pct': 65.3, 'orig_cap_n': 75, 'orig_cap_pct': 50.0}, 'Drake London': {'n': 78, 'final_pct': 52.0, 'orig_cap_n': 75, 'orig_cap_pct': 50.0}}`; captains `{}`
  - lineups not in the level-0 build: 103; clusters `{'by_origin': {'SWAP_POLISH': 18, 'RELAXATION': 85}, 'by_captain': {'Bijan Robinson': 23, 'Chris Olave': 18, 'Drake London': 17, 'Tyler Shough': 15, 'Juwan Johnson': 8, 'Alvin Kamara': 6, 'Devaughn Vele': 4, 'Michael Penix Jr.': 3, 'Saints': 2, 'Daniel Carlson': 2, 'Nick Folk': 1, 'Falcons': 1, 'Austin Hooper': 1, 'Brian Robinson Jr.': 1, 'Noah Fant': 1}, 'by_split': {'3-3': 35, '2-4': 28, '4-2': 24, '1-5': 13, '5-1': 3}, 'by_salary_band': {'49500-49900': 52, '49000-49400': 27, '50000': 14, '48000-48900': 8, '<48000': 2}}`
  - why: level 0 built 141/150: under a 75-entry player cap, a 45-entry captain cap and at most 4 shared players, the lawful pool near the top-tail runs out of lineups that avoid the core (Tyler Shough, Bijan Robinson, Chris Olave, Drake London)
  - effective hypotheses (rungs are GREEDY rebuilds, before the swap polish): last unfilled rung 70.7 -> filled rung 66.3; final polished portfolio 68.6
- salary-relief slots used: `{'Treyton Welch': 4, 'Charlie Woerner': 3, 'Kevin Austin Jr.': 6, 'Nick Muse': 3}`
### 196285160 (20 entries)
- objective `{'m': 2, 'value': 1.3025, 'MEANING': 'E[min(entries at the first-place proxy, m)] per world'}`; proxy coverage 0.7705; method GREEDY_THEN_1SWAP_POLISH; polish `{'rounds': 10, 'lineups_changed': 6, 'objective_greedy': 1.2345, 'objective_final': 1.3025, 'coverage_greedy': 0.7275, 'coverage_final': 0.7705}`
- distinct captains 6; effective hypotheses 15.7; shared players between pairs `{'max': 5, 'distribution': {1: 10, 2: 66, 3: 81, 4: 32, 5: 1}}`
- captain exposure `{'Drake London': 30.0, 'Bijan Robinson': 25.0, 'Chris Olave': 20.0, 'Tyler Shough': 15.0, 'Juwan Johnson': 5.0, 'Alvin Kamara': 5.0}`
- player exposure `{'Chris Olave': 65.0, 'Bijan Robinson': 65.0, 'Tyler Shough': 65.0, 'Drake London': 60.0, 'Juwan Johnson': 55.0, 'Alvin Kamara': 55.0, 'Daniel Carlson': 45.0, 'Michael Penix Jr.': 35.0, 'Saints': 30.0, 'Falcons': 30.0, 'Bryce Lance': 25.0, 'Nick Folk': 20.0, 'Treyton Welch': 15.0, 'Nick Muse': 10.0, 'Jahan Dotson': 10.0}`
- RELAXATION: level 2; rungs L0 caps {'player': 10, 'captain': 6, 'overlap': 4} built 18/20 EHC 14.3; L1 caps {'player': 10, 'captain': 6, 'overlap': 5} built 17/20 EHC 12.6; L2 caps {'player': 13, 'captain': 6, 'overlap': 5} built 20/20 EHC 14.0
  - above the original cap: `{'Chris Olave': {'n': 13, 'final_pct': 65.0, 'orig_cap_n': 10, 'orig_cap_pct': 50.0}, 'Bijan Robinson': {'n': 13, 'final_pct': 65.0, 'orig_cap_n': 10, 'orig_cap_pct': 50.0}, 'Juwan Johnson': {'n': 11, 'final_pct': 55.0, 'orig_cap_n': 10, 'orig_cap_pct': 50.0}, 'Tyler Shough': {'n': 13, 'final_pct': 65.0, 'orig_cap_n': 10, 'orig_cap_pct': 50.0}, 'Alvin Kamara': {'n': 11, 'final_pct': 55.0, 'orig_cap_n': 10, 'orig_cap_pct': 50.0}, 'Drake London': {'n': 12, 'final_pct': 60.0, 'orig_cap_n': 10, 'orig_cap_pct': 50.0}}`; captains `{}`
  - lineups not in the level-0 build: 10; clusters `{'by_origin': {'SWAP_POLISH': 5, 'RELAXATION': 5}, 'by_captain': {'Bijan Robinson': 3, 'Drake London': 3, 'Chris Olave': 2, 'Tyler Shough': 1, 'Juwan Johnson': 1}, 'by_split': {'3-3': 5, '2-4': 2, '1-5': 2, '4-2': 1}, 'by_salary_band': {'49500-49900': 6, '50000': 3, '49000-49400': 1}}`
  - why: level 0 built 18/20: under a 10-entry player cap, a 6-entry captain cap and at most 4 shared players, the lawful pool near the top-tail runs out of lineups that avoid the core (Chris Olave, Bijan Robinson, Tyler Shough, Drake London)
  - effective hypotheses (rungs are GREEDY rebuilds, before the swap polish): last unfilled rung 12.6 -> filled rung 14.0; final polished portfolio 15.7
- salary-relief slots used: `{'Treyton Welch': 3, 'Kevin Austin Jr.': 1, 'Charlie Woerner': 1, 'Nick Muse': 2}`
### 196285161 (2 entries)
- objective `{'m': 1, 'value': 0.2715, 'MEANING': 'E[min(entries at the first-place proxy, m)] per world'}`; proxy coverage 0.2715; method GREEDY_THEN_1SWAP_POLISH; polish `{'rounds': 1, 'lineups_changed': 0, 'objective_greedy': 0.2715, 'objective_final': 0.2715, 'coverage_greedy': 0.2715, 'coverage_final': 0.2715}`
- distinct captains 2; effective hypotheses 2.0; shared players between pairs `{'max': 4, 'distribution': {4: 1}}`
- captain exposure `{'Chris Olave': 50.0, 'Tyler Shough': 50.0}`
- player exposure `{'Chris Olave': 100.0, 'Juwan Johnson': 100.0, 'Treyton Welch': 100.0, 'Tyler Shough': 100.0, 'Bijan Robinson': 50.0, 'Daniel Carlson': 50.0, 'Alvin Kamara': 50.0, 'Drake London': 50.0}`
- RELAXATION: level 0; rungs L0 caps {'player': 2, 'captain': 2, 'overlap': 4} built 2/2 EHC 2.0
  - above the original cap: `{}`; captains `{}`
  - lineups not in the level-0 build: 0; clusters `{'by_origin': {}, 'by_captain': {}, 'by_split': {}, 'by_salary_band': {}}`
  - why: no relaxation needed: level 0 built 2/2
  - effective hypotheses (rungs are GREEDY rebuilds, before the swap polish): last unfilled rung None -> filled rung 2.0; final polished portfolio 2.0
- salary-relief slots used: `{'Treyton Welch': 2}`
- **CPT Chris Olave** + Bijan Robinson, Daniel Carlson, Juwan Johnson, Treyton Welch, Tyler Shough -- $50000, mean 109.17, proxy 0.1835
  - **Treyton Welch: SALARY RELIEF -- not a football conviction** (LOW_OPPORTUNITY_SALARY_RELIEF; mean 0.29, scores in 15% of worlds; proxy 0.173 when he scores 0 vs 0.2418 when he scores); unlocks ['Bijan Robinson', 'Juwan Johnson', 'Tyler Shough']
  - best realistic alternative without him: ['Chris Olave', 'Bijan Robinson', 'Daniel Carlson', 'Juwan Johnson', 'Nick Muse', 'Tyler Shough'] (proxy 0.174, mean 108.9); difference proxy +0.0095, mean points +0.27
- **CPT Tyler Shough** + Alvin Kamara, Chris Olave, Drake London, Juwan Johnson, Treyton Welch -- $49800, mean 106.28, proxy 0.1285
  - **Treyton Welch: SALARY RELIEF -- not a football conviction** (LOW_OPPORTUNITY_SALARY_RELIEF; mean 0.29, scores in 15% of worlds; proxy 0.1175 when he scores 0 vs 0.1895 when he scores); unlocks ['Alvin Kamara', 'Chris Olave', 'Drake London', 'Juwan Johnson']
  - best realistic alternative without him: ['Tyler Shough', 'Bijan Robinson', 'Chris Olave', 'Juwan Johnson', 'Nick Folk', 'Nick Muse'] (proxy 0.144, mean 107.46); difference proxy -0.0155, mean points -1.18
  - portfolio test without_these ['Treyton Welch']: objective -0.011, coverage -1.1 pts (SE 0.99), mean points -0.28; alternative lineups [['Chris Olave', 'Bijan Robinson', 'Daniel Carlson', 'Juwan Johnson', 'Nick Muse', 'Tyler Shough'], ['Tyler Shough', 'Alvin Kamara', 'Chris Olave', 'Drake London', 'Juwan Johnson', 'Nick Muse']]
  - portfolio test without_any_low_opportunity_or_filler ['Barion Brown', 'CJ Donaldson', 'Charlie Woerner', 'Chris Blair', 'Cooper Rush', 'Jack Strand', 'Kevin Austin Jr.', 'Nick Muse', 'Oscar Delp', 'Spencer Rattler', 'Treyton Welch', 'Tua Tagovailoa', 'Zach Wilson', 'Zachariah Branch']: objective -0.053, coverage -5.3 pts (SE 0.99), mean points -1.05; alternative lineups [['Juwan Johnson', 'Bijan Robinson', 'Bryce Lance', 'Chris Olave', 'Daniel Carlson', 'Tyler Shough'], ['Tyler Shough', 'Alvin Kamara', 'Bijan Robinson', 'Bryce Lance', 'Chris Olave', 'Saints']]

## FIELD (EXTERNAL_RESEARCH_SHADOW, UNVALIDATED)
- NOT_PROMOTED. Both field projections are EXTERNAL_RESEARCH_SHADOW and UNVALIDATED; the blend fits five unverified anchors better, which is not validation. Neither feeds the football or the production portfolio.
### FC_ONLY (sigma 0.6, anchor RMSE 13.6)
- 196285137: **52 lineup(s) contain a player this shadow field never rosters -- their dupe estimates are UNDERSTATED, not evidence of uniqueness**
- 196285137: dupes exact `{'mean': 28.2, 'max': 329.4, 'n_over_guardrail': 47, 'guardrail': 20}` product `{'mean': 25.5, 'max': 188.92}`; salary left `{'ours': {'0': 93, '1000': 13, '500': 40, '2000': 1, '3000': 1, '1500': 2}, 'ours_mean': 434.0, 'shadow_field_mean': 1554.0}`; split `{'ours_pct': {'1-5': 13.3, '2-4': 26.0, '3-3': 33.3, '4-2': 22.0, '5-1': 5.3}, 'shadow_field_pct': {'1-5': 15.5, '2-4': 37.9, '3-3': 32.9, '4-2': 12.3, '5-1': 1.4}}`
- 196285160: **6 lineup(s) contain a player this shadow field never rosters -- their dupe estimates are UNDERSTATED, not evidence of uniqueness**
- 196285160: dupes exact `{'mean': 8.9, 'max': 84.7, 'n_over_guardrail': 2, 'guardrail': 20}` product `{'mean': 5.9, 'max': 32.54}`; salary left `{'ours': {'0': 16, '500': 3, '1000': 1}, 'ours_mean': 275.0, 'shadow_field_mean': 1554.0}`; split `{'ours_pct': {'1-5': 25.0, '2-4': 20.0, '3-3': 45.0, '4-2': 10.0}, 'shadow_field_pct': {'1-5': 15.5, '2-4': 37.9, '3-3': 32.9, '4-2': 12.3, '5-1': 1.4}}`
- 196285161: **2 lineup(s) contain a player this shadow field never rosters -- their dupe estimates are UNDERSTATED, not evidence of uniqueness**
- 196285161: dupes exact `{'mean': 0.0, 'max': 0.0, 'n_over_guardrail': 0, 'guardrail': 20}` product `{'mean': 0.0, 'max': 0.0}`; salary left `{'ours': {'0': 2}, 'ours_mean': 100.0, 'shadow_field_mean': 1554.0}`; split `{'ours_pct': {'1-5': 100.0}, 'shadow_field_pct': {'1-5': 15.5, '2-4': 37.9, '3-3': 32.9, '4-2': 12.3, '5-1': 1.4}}`
  - CPT/FLEX ownership (150): Tyler Shough 22.5/45.7; Bijan Robinson 20.8/45.2; Chris Olave 13.1/38.9; Kevin Austin Jr. 1.7/49.5; Michael Penix Jr. 9.3/39.3; Alvin Kamara 7.3/39.3; Drake London 8.1/34.0; Juwan Johnson 5.8/32.8; Daniel Carlson 2.6/31.8; Devaughn Vele 4.0/27.3; Olamide Zaccheaus 0.7/23.5; Kyle Pitts Sr. 1.5/19.5
### BLEND (sigma 0.6, anchor RMSE 10.92)
- 196285137: **3 lineup(s) contain a player this shadow field never rosters -- their dupe estimates are UNDERSTATED, not evidence of uniqueness**
- 196285137: dupes exact `{'mean': 48.9, 'max': 423.5, 'n_over_guardrail': 71, 'guardrail': 20}` product `{'mean': 37.1, 'max': 191.69}`; salary left `{'ours': {'0': 93, '1000': 13, '500': 40, '2000': 1, '3000': 1, '1500': 2}, 'ours_mean': 434.0, 'shadow_field_mean': 1010.0}`; split `{'ours_pct': {'1-5': 13.3, '2-4': 26.0, '3-3': 33.3, '4-2': 22.0, '5-1': 5.3}, 'shadow_field_pct': {'1-5': 15.6, '2-4': 37.1, '3-3': 34.0, '4-2': 11.6, '5-1': 1.7}}`
- 196285160: **2 lineup(s) contain a player this shadow field never rosters -- their dupe estimates are UNDERSTATED, not evidence of uniqueness**
- 196285160: dupes exact `{'mean': 18.4, 'max': 56.5, 'n_over_guardrail': 6, 'guardrail': 20}` product `{'mean': 10.64, 'max': 34.45}`; salary left `{'ours': {'0': 16, '500': 3, '1000': 1}, 'ours_mean': 275.0, 'shadow_field_mean': 1010.0}`; split `{'ours_pct': {'1-5': 25.0, '2-4': 20.0, '3-3': 45.0, '4-2': 10.0}, 'shadow_field_pct': {'1-5': 15.6, '2-4': 37.1, '3-3': 34.0, '4-2': 11.6, '5-1': 1.7}}`
- 196285161: dupes exact `{'mean': 47.0, 'max': 58.8, 'n_over_guardrail': 2, 'guardrail': 20}` product `{'mean': 4.38, 'max': 4.47}`; salary left `{'ours': {'0': 2}, 'ours_mean': 100.0, 'shadow_field_mean': 1010.0}`; split `{'ours_pct': {'1-5': 100.0}, 'shadow_field_pct': {'1-5': 15.6, '2-4': 37.1, '3-3': 34.0, '4-2': 11.6, '5-1': 1.7}}`
  - CPT/FLEX ownership (150): Tyler Shough 19.7/44.1; Bijan Robinson 20.6/43.0; Chris Olave 16.3/39.8; Drake London 10.5/37.3; Michael Penix Jr. 8.1/37.1; Alvin Kamara 6.9/38.1; Juwan Johnson 7.5/36.6; Daniel Carlson 2.8/34.6; Kevin Austin Jr. 0.3/34.1; Devaughn Vele 3.0/24.3; Nick Folk 1.3/21.5; Olamide Zaccheaus 0.5/18.5

## EXTERNAL
- Hard Rock: NOT CAPTURED HERE -- only after the football freeze, by the networked agent (docs/AGENT_OUTBOX.md); never fed back into the projection; no wager is recommended
- FC comparison (largest gaps; FC is never an input):
  - Kevin Austin Jr. (NO WR): ours 0.65 vs FC 8.4 (ROLE_OR_VOLUME)
  - Olamide Zaccheaus (ATL WR): ours 2.37 vs FC 6.6 (ROLE_OR_VOLUME)
  - Kyle Pitts Sr. (ATL TE): ours 4.98 vs FC 8.72 (ROLE_OR_VOLUME)
  - Austin Hooper (ATL TE): ours 3.74 vs FC 0.0 (DEPTH_OR_DATA (FC zero is not an inactive signal))
  - Chris Olave (NO WR): ours 24.17 vs FC 20.85 (EFFICIENCY_OR_TD)
  - Drake London (ATL WR): ours 19.96 vs FC 16.91 (EFFICIENCY_OR_TD)
  - Tyler Shough (NO QB): ours 22.17 vs FC 25.2 (EFFICIENCY_OR_TD)
  - Devaughn Vele (NO WR): ours 10.49 vs FC 13.01 ()
  - Charlie Woerner (ATL TE): ours 0.37 vs FC 2.55 ()
  - Michael Penix Jr. (ATL QB): ours 15.35 vs FC 17.37 ()
  - Zachariah Branch (ATL WR): ours 0.74 vs FC 2.65 ()
  - Daniel Carlson (NO K): ours 8.65 vs FC 10.45 ()
- video claims compared: 20 (UNVERIFIED_EXTERNAL)

## FILES
- `nfl/dfs/salaries/showdown_atl_no/BASE/SHOWDOWN_ATL_NO_DK_UPLOAD_196285137.csv` -- 150 rows, sha256 `8905ab7bd7c4cb287f714daade0e56fc0e8e7d0c07087d25c9a64de49d256e9a`
- `nfl/dfs/salaries/showdown_atl_no/BASE/SHOWDOWN_ATL_NO_DK_UPLOAD_196285160.csv` -- 20 rows, sha256 `daec8b9f1859772a215922ee998d1a7672d9e60b871557d77257fa23676215ed`
- `nfl/dfs/salaries/showdown_atl_no/BASE/SHOWDOWN_ATL_NO_DK_UPLOAD_196285161.csv` -- 2 rows, sha256 `d706e7f38ca38fb625dc4431c22c7808fa99fe688b360b73a5e672d92d2dd1b3`
- verifier: `{"n_rows": 172, "violations": []}`

nothing here enters a contest or uploads to DraftKings; PROJECTION_SYSTEM_STATE NOT_VALIDATED; no wager is recommended
