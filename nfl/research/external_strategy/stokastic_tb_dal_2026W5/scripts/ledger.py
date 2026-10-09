import json
S = '/tmp/claude-0/-home-user-mlb-prop-system-v7/8de98087-4781-5a10-ae09-ef74590f8116/scratchpad/stokastic/'
ex = json.load(open(S + 'VIDEO_STRATEGY_CLAIMS_EXTRACTION.json'))['claims']

PBP = 'nfl/research/postgame/pbp_2026.2b3e9f2c6f92123f.csv.gz (nflverse, retrieved 2026-10-07T16:59Z, weeks 1-4, pre-kickoff)'
SNAP = 'nfl/postgame/raw/showdown_atl_no_2026W4/SNAP_COUNTS_2026.125e7bfba67b6b13.csv.gz (retrieved 2026-10-06T15:09Z, weeks 1-4)'
PWK = 'nfl/postgame/raw/showdown_tb_dal_2026W5/NFLVERSE_STATS_PLAYER_WEEK_2026.8304933b6ee2bc2e.csv (captured 2026-10-09 post-kickoff; weeks 1-4 rows used only as a cross-check)'
WORLDS = 'nfl/dfs/salaries/showdown_tb_dal/OFFICIAL/SHOWDOWN_TB_DAL_2026W5_WORLDS.npz + _DRAWS.json (frozen 23:08Z, before kickoff 00:15Z)'
CAND = 'OFFICIAL_ELIGIBILITY_FIX_R1/SHOWDOWN_TB_DAL_CANDIDATES.csv (5,387 candidates) scored in the 2,000 frozen worlds'
STAND = 'nfl/postgame/showdown_tb_dal_2026W5/TB_DAL_2026W5_STANDINGS.json ownership[] (DK %Drafted, 150-max 196438543) -- ANSWER KEY ONLY'
RAWST = 'nfl/postgame/raw/showdown_tb_dal_2026W5/DK_STANDINGS_*.csv.gz (owner upload 2026-10-09T13:17Z) -- ANSWER KEY ONLY'
SAL = 'nfl/dfs/salaries/raw/showdown_tb_dal_2026W5/DKEntries_TB_DAL_SHOWDOWN_2026W5.5d559e413e680cae.csv'
INACT = 'nfl/dfs/salaries/raw/showdown_tb_dal_2026W5/ROTOWIRE_INACTIVES_TB_DAL_2026W5.json (SECONDARY, RotoWire screenshot, received 23:06Z)'
OWNF = 'OFFICIAL/SHOWDOWN_TB_DAL_SHADOW_BOARD_BLEND.json (23:22Z), _FC_ONLY.json (23:23Z), research/ownership/predictions/SC_OWN_ROTATION_2_TB_DAL_2026W5_OFFICIAL.json (sealed 23:30Z)'

L = {}
def c(i, cls, verdict, data, ours=None, theirs=None, cite=None, hindsight=None, tags=None):
    L[i] = dict(classification=cls, verdict=verdict, what_the_data_shows=data, our_frozen_number=ours,
                their_stated_number=theirs, cite=cite or [], hindsight_note=hindsight, secondary_tags=tags or [])

c(1, 'THEIR_MODEL_OUTPUT', 'EVENT_VERIFIED; GAME NAME CORRECTED',
  'The Monday week-4 game was ATL@NO (2026_04_ATL_NO, 2026-10-05), not ATL@WAS. Play-by-play: Br.Robinson (Brian Robinson Jr.) 3 TD, Kamara 2 TD, so the described outcome occurred. Our own frozen ATL@NO worlds (RW_INACTIVES_CHARTFIX and RW_INACTIVES runs) gave Brian Robinson Jr. 3+ TD in 0 of 2,000 worlds (P(1+ TD) 8.2%); Bijan Robinson 3+ TD 3.95%. Both their model and ours treated it as a near-impossible tail; ours was thinner. Consistent with D-01 (thin tails), but one event cannot grade tail calibration.',
  ours='Brian Robinson Jr. P(3+ TD) = 0/2000 (upper 95% bound ~0.15%)', theirs='~56/10,000 (0.56%); joint with Kamara TD ~0.0%',
  cite=[PBP, 'nfl/dfs/salaries/showdown_atl_no/RW_INACTIVES_CHARTFIX/SHOWDOWN_ATL_NO_2026W4_WORLDS.npz', 'TB_DAL_DEFECT_REGISTER.json D-01'], tags=['TAIL_CALIBRATION'])
c(2, 'THEIR_MODEL_OUTPUT', 'AGREE_ON_LAMB; DISAGREE_ON_PICKENS',
  'Our frozen worlds: P(anytime TD) Lamb 53.4%, Pickens 32.2% (MC SE ~1.1pp). Agreement on Lamb (theirs ~51%); we were ~12pp lower on Pickens (theirs ~44%; presenter flagged the figure as ambiguous). Our TD expectation follows red-zone opportunity: weeks 1-4 DAL red-zone targets Lamb 6, Pickens 3 of 22.',
  ours='Lamb 0.534, Pickens 0.322', theirs='Lamb ~0.51, Pickens ~0.44', cite=[WORLDS, PBP],
  hindsight='HINDSIGHT: Pickens scored 1 TD, Lamb 0. One outcome grades neither model.')
c(3, 'OPINION', 'NOT_SUPPORTED_BY_OUR_MODEL',
  '"Public perception" is not measured anywhere in our data. Our own model put a 21pp gap between Lamb and Pickens P(TD), i.e. our engine sided with the "perception" they argue against. Field CPT ownership (answer key) Lamb 17.1% vs Pickens 12.0%.',
  ours='gap 0.212', theirs='gap ~0.07', cite=[WORLDS, STAND], tags=['THEIR_MODEL_OUTPUT'])
c(4, 'THEIR_MODEL_OUTPUT', 'OUR_ENGINE_DISAGREES',
  'Salaries VERIFIED: Pickens FLEX $9,400 / CPT $14,100 vs Lamb $11,800 / $17,700. Leverage is THEIR optimal minus THEIR ownership. Ours: Pickens optimal CPT 2.4% vs our sealed BLEND CPT forecast 3.9% (-1.5) and vs the no-fit FC-proportional baseline 9.3% (-6.9); optimal FLEX 17.6% vs BLEND 30.0% (-12.4). Our engine had Pickens NEGATIVELY leveraged.',
  ours='opt CPT 2.4%, opt FLEX 17.6%', theirs='positive leverage at CPT and FLEX', cite=[SAL, CAND, OWNF],
  hindsight='HINDSIGHT: actual field Pickens CPT 12.0%, FLEX 28.3%; he was a top-1% captain (49% of top-1% lineups).', tags=['VERIFIED_FACT (salaries)'])
c(5, 'VERIFIED_FACT', 'VERIFIED_EXACTLY',
  'Targets by week (pbp, two-point tries and sacks excluded): Lamb 8, 9, 8, 21; Pickens 6, 8, 11, 3. Lamb week 4 = 21 (nflverse weekly stats agree: 21 targets, 17 rec, 189 yds). Pickens week 4 = 3 at 86% of snaps; weeks 1-3 = 25. Weeks 1-3 Lamb 25 = Pickens 25: equal.',
  cite=[PBP, PWK, SNAP])
c(6, 'OWNERSHIP_FORECAST', 'CONTRADICTED_BY_ACTUAL',
  'Actual 150-max: Pickens FLEX 28.3% ranked 7th (Dak 61.4, Daniels 45.3, Lamb 42.5, Javonte 37.0, Aubrey 30.3, Flournoy 29.1); CPT 12.0% ranked 4th (Lamb 17.1, Dak 16.4, Javonte 15.1). Their forecast ranks (3rd FLEX, 2nd CPT) were too high. Our sealed BLEND forecast had Pickens FLEX 30.0% (close) but CPT 3.9% (far too low).',
  ours='BLEND CPT 3.9 / FLEX 30.0; FC_ONLY 15.2 / 54.3', theirs='3rd FLEX, 2nd CPT', cite=[STAND, OWNF], tags=['CONTRADICTED_BY_DATA'])
c(7, 'PRINCIPLE', 'MEASURABLE; OUR OPTIMIZER DOES NOT CONSUME IT',
  'Measured after the fact: our 150 lineups shared their exact build with 40.2 field entries on average (max 455); the field median entry shared with 42. Lineups containing the most popular players were the most duplicated. Our optimizer has no duplication term (D-06; showdown_portfolio.py:18-29).',
  cite=[STAND, 'nfl/tools/showdown_portfolio.py:18-29'], tags=['CAPABILITY_GAP'])
c(8, 'OWNERSHIP_FORECAST', 'VERIFIED (ownership part); conditional part is OPINION',
  'Actual field team split (TB-DAL players, 150-max): 1-5 22.0%, 2-4 35.4%, 3-3 29.4%, 4-2 11.5%, 5-1 1.7%. TB-heavy builds were indeed low-owned. Our pregame BLEND field forecast had 4-2 at 4.2% and 5-1 at 0.0% (too low). Our worlds put TB-heavy (4-2 or 5-1) optimal in 20.8% of worlds; our entered portfolio was 29.3% 4-2 and 5.3% 5-1.',
  ours='optimal split 4-2 19.1%, 5-1 1.8%', cite=[RAWST, 'OFFICIAL/SHOWDOWN_TB_DAL_SHADOW_BOARD_BLEND.json team_split_away_home', CAND],
  hindsight='HINDSIGHT: field top 1% was 3-3 in 58%, 4-2 in 18%.')
c(9, 'OWNERSHIP_FORECAST', 'PARTLY CONTRADICTED',
  'Actual CPT: Lamb 17.1, Dak 16.4, Javonte 15.1, Pickens 12.0, Daniels 10.2. The set of popular captains named is right. Pickens ~7-8% was too low (actual 12.0). Our forecasts: BLEND Pickens 3.9, FC_ONLY 15.2, FC-proportional 9.3.',
  theirs='Pickens ~7-8%', cite=[STAND, OWNF])
c(10, 'OPINION', 'PARTLY VERIFIED',
  'TB defence weeks 1-4: EPA/play allowed -0.059, 6th best of 32 ("good on paper" holds by EPA). Points allowed 33, 23, 23, 17 (24.0/game against a league mean of 23.1 ppg), so by points it is not good. Opponent offences by EPA/play rank: CIN 10, CLE 17, MIN 27, GB 26, so mostly weak. Our engine has NO opponent adjustment of any kind (football_points.py docstring: "OWN-OFFENCE centre ... no opponent adjustment (NOT_MODELLED by owner instruction, item 9)").',
  cite=[PBP, 'nfl/sim/football_points.py:11-17'], tags=['VERIFIED_FACT (numbers)', 'CAPABILITY_GAP'])
c(11, 'VERIFIED_FACT', 'VERIFIED with one correction',
  'Javonte Williams weeks 1-4: 13 carries inside the 10 and 11 inside the 5; 5 rush TD + 1 rec TD (pbp; nflverse weekly agrees). Inside-5: tied for the league lead with D. Henry (11). Inside-10: NOT tied with Henry. Henry leads with 17; Williams is tied 2nd (13) with Swift and Pollard. Vulturing: other DAL carries inside the 5 = 1 (Prescott); inside the 10 = 3 (Prescott 2, Turpin 1). Our engine computes gl_carry_share (proj_v1.py:338-339) but never consumes it; TD allocation uses inside-20 red-zone intensity (proj_v1.py:663-681) and fixed rush_td_share (showdown_draws.py:111; game.py:489-490).',
  ours='Javonte P(anytime TD) 0.679, P(2+ TD) 0.295, mean TD 1.09', cite=[PBP, PWK, 'nfl/tools/proj_v1.py:338-339,663-681', 'nfl/warehouse/player_game.py:161-164'],
  hindsight='HINDSIGHT: Javonte 1 rush TD (1-yd run).', tags=['CONTRADICTED_BY_DATA (inside-10 tie)'])
c(12, 'THEIR_MODEL_OUTPUT', 'DESCRIPTIVE ONLY', 'Their portfolio exposure. Ours for comparison (150-max, R1): Javonte CPT 21.3%, rostered 50.0% (at cap).', ours='CPT 21.3%, rostered 50%', theirs='CPT ~23%, 46% overall', cite=['OFFICIAL_ELIGIBILITY_FIX_R1/SHOWDOWN_TB_DAL_CPT_EXPOSURES.csv'])
c(13, 'CAPABILITY', 'OUR WORLDS CAN ANSWER IT; NO TOOL EXPOSES IT',
  'Conditional/joint queries over worlds are computable from our per-world stat lines. Demonstration: P(DAL by 10+ AND Goodson 10+ rush yds AND Daniels < 2 pass TD) = 26.8% (535/2000). Betting use is out of scope. See SIMULATION_QUERY_CAPABILITY_SPEC (being implemented by another agent).',
  ours='0.2675', cite=[WORLDS], tags=['NOT a betting input'])
c(14, 'VERIFIED_FACT', 'VERIFIED (facts); hypothesis NOT_VERIFIABLE_HERE',
  'Goodson FLEX $2,000 (verified). Snaps: 11 (15%) week 3, 16 (21%) week 4. Carries: 6 vs BAL (wk 3), 3 vs HOU (wk 4); 0 in weeks 1-2. "Short rest + big favourite -> more split" is a hypothesis with no data here. Our frozen projection: 4.92 carries, 20.1 rush yds, P(10+ rush yds) 64%. "3x the field" is their exposure, not checkable.',
  ours='4.92 carries; FLEX optimal 18.6%', cite=[PBP, SNAP, SAL, WORLDS],
  hindsight='HINDSIGHT: Goodson recorded no stats (0.0 DK); actual FLEX ownership 8.8%.', tags=['OPINION (hypothesis)'])
c(15, 'THEIR_MODEL_OUTPUT', 'AGREE',
  'Our worlds: P(Javonte TD AND Goodson TD) = 15.0% (300/2000); the independence product is 15.1%, so in our engine the two backs\' TD events are uncorrelated (r = -0.004). Theirs ~13%.',
  ours='0.150', theirs='~0.13', cite=[WORLDS], hindsight='HINDSIGHT: Goodson did not score.')
c(16, 'THEIR_MODEL_OUTPUT', 'DESCRIPTIVE ONLY',
  'Their exposures. Ours (150-max R1): Dak rostered 50% / CPT 12.0%; Javonte 50%; Daniels 48.7% / 7.3%; Lamb CPT 22.0%. They called Lamb most negatively leveraged; our sealed BLEND forecast and our optimal frequency were level on Lamb CPT (36.8 vs 37.3).',
  ours='Lamb CPT 22.0%', theirs='Lamb CPT 12%', cite=['OFFICIAL_ELIGIBILITY_FIX_R1/SHOWDOWN_TB_DAL_EXPOSURES.csv', OWNF])
c(17, 'VERIFIED_FACT', 'VERIFIED',
  'Aubrey DK by week (pbp, DK kicker rules as in nfl/product/dk_scoring.py; missed FG = 0): 2, 16, 11, 12, so double digits in 3 of 4. FLEX $5,400 vs the other kicker (McLaughlin) $5,000. Field FLEX ownership 30.3% (answer key), so their 25% was under the field. Aubrey CPT field 1.9%.',
  ours='Aubrey mean 9.3 (projection); optimal FLEX 27.8%, CPT 2.2%', cite=[PBP, PWK, SAL, STAND], hindsight='HINDSIGHT: Aubrey 5.0 DK.')
c(18, 'PRINCIPLE', 'CONSISTENT WITH OUR WORLDS (model property, not a fact)',
  'In our worlds a DST is the optimal captain in 23/2000 worlds (1.15%). In those worlds the mean game total is 31.7 (vs 50.1 otherwise) and the best skill-player score is 21.5 DK (vs 32.7). Cowboys DST CPT optimal in 0.15% of worlds. Our worlds reproduce the argued conditional structure.',
  ours='P(DST optimal CPT) 0.0115', cite=[CAND])
c(19, 'OWNERSHIP_FORECAST', 'VERIFIED',
  'Field team split (TB-DAL): 1-5 22.0%, 2-4 35.4%, 3-3 29.4%, 4-2 11.5%, 5-1 1.7%. Of the 100 most-duplicated field lineups: 2-4 42, 1-5 33, 3-3 23, 4-2 2, 5-1 0. Dallas-heavy duplication is verified. Their "many winning-build candidates are DAL 5-1/4-2" is THEIR model output. Ours: DAL-heavy (1-5 or 2-4) optimal in 42.8% of worlds.',
  ours='optimal split 1-5 11.6%, 2-4 31.2%', cite=[RAWST, CAND], tags=['VERIFIED_FACT (field)'])
c(20, 'PRINCIPLE', 'CONSISTENT; OUR OBJECTIVE IS BUILT ON THE OPPOSITE PREMISE',
  'Our objective counts worlds in which a lineup reaches >= 0.9x the world optimum (showdown_portfolio.py:736-741). Measured: the hindsight optimum (136.99) was in no candidate pool; the actual winner (136.59) was shared by 18 entries. Whether near-optimal coverage tracks finishing rank is untested: we have no rank-vs-proxy study.',
  cite=['nfl/tools/showdown_portfolio.py:736-741', 'TB_DAL_POSTGAME_REPORT.md D', 'TB_DAL_2026W5_FIELD_STUDY.json'], tags=['RESEARCH_GAP'])
c(21, 'THEIR_MODEL_OUTPUT', 'MIXED; ONE OWNERSHIP NUMBER VERIFIED',
  'Flournoy field FLEX ownership actual 29.1% (their ~30%: verified). Leverage signs are their model\'s. Ours, optimal FLEX minus BLEND forecast: Goodson +14.1, Dak +10.5, Cowboys DST +4.3, Javonte -6.8, Daniels +4.7, Flournoy -23.9, Gainwell -15.7; Lamb -3.7, Aubrey -19.4, Irving +9.5. Against their board, ours disagrees on Javonte, Flournoy, Gainwell and Irving.',
  cite=[CAND, OWNF, STAND], tags=['OWNERSHIP_FORECAST (Flournoy 30%)'])
c(22, 'OPINION', 'CONTRADICTED_BY_MEASUREMENT for QB-receiver pairs; consistent for RB-RB',
  'Measured 2000-2026 same-club DK correlations (block bootstrap by game): QB1~WR1 +0.42 [0.39, 0.46], QB1~TE1 +0.37, WR1~WR2 +0.17 [0.13, 0.22], RB1~RB2 0.00 [-0.04, 0.05]. Our TB@DAL worlds: Dak-Lamb +0.46, Dak-Pickens +0.34, Daniels-Egbuka +0.36, Lamb-Pickens +0.02. Correlation is material for QB stacks. Our worlds under-state WR1~WR2 (0.02 vs 0.17 measured), which is a possible engine gap.',
  ours='Dak-Lamb 0.46; Lamb-Pickens 0.02', cite=['nfl/sim/PAIR_CORRELATIONS.json same_club', 'OFFICIAL_ELIGIBILITY_FIX_R1/SHOWDOWN_TB_DAL_CORRELATION.csv', WORLDS], tags=['CONTRADICTED_BY_DATA'])
c(23, 'VERIFIED_FACT', 'VERIFIED (approximately)',
  'Flournoy $3,800 (verified). Offensive snap share 71%, 76%, 66%, 74% (about 75%, with week 3 lower). Targets 4, 6, 8, 5 = 23 in 4 games (verified exactly; nflverse weekly agrees).',
  ours='projected 3.29 targets, 5.4 DK (target share well below his 23/4 = 5.75 per game)', cite=[SNAP, PBP, PWK, SAL], hindsight='HINDSIGHT: 4 targets, 90 yds, 12.0 DK.')
c(24, 'OWNERSHIP_FORECAST', 'VERIFIED (broadly)',
  'Field 150-max: 91% of entries rostered at least 2 of {Lamb, Dak, Javonte, Pickens} (38% had 3). TB FLEX slots averaged $5,823 against $8,002 for DAL. 52.5% of TB FLEX slots cost <= $5,000. But the most-rostered TB player was Daniels ($8,600, 45.3%).',
  cite=[RAWST])
c(25, 'CONTRADICTED_BY_DATA', 'APPROXIMATELY TRUE; LITERALLY FALSE BY 0.3',
  'Egbuka DK by week (pbp; nflverse PPR agrees): 11.3, 10.3, 11.2, 3.3. Two games are slightly above 11. FLEX $8,200 verified. Our frozen projection 12.0 DK; P(100+ rec yds) 9.2%.',
  ours='mean 12.0 DK', cite=[PBP, PWK, SAL], hindsight='HINDSIGHT: 17.2 DK (jet-sweep TD).')
c(26, 'VERIFIED_FACT', 'VERIFIED EXACTLY',
  'DAL points allowed: wk1 @NYG 28, wk2 WAS 20, wk3 BAL 34, wk4 @HOU 30 (mean 28.0). DAL defensive EPA/play allowed +0.201, 32nd of 32. Our engine does not use it: the scoring centre is own-offence only (football_points.py:11-17), so TB\'s expected points (20.7) carry no adjustment for facing the league\'s worst defence by EPA.',
  ours='TB expected 20.68 pts (own-offence centre)', cite=[PBP, 'nfl/sim/football_points.py:11-17', 'OFFICIAL DRAWS scoring_centre'], hindsight='HINDSIGHT: TB scored 24.', tags=['CAPABILITY_GAP'])
c(27, 'VERIFIED_FACT', 'VERIFIED with one discrepancy',
  'TB week 4 targets (pbp; nflverse weekly agrees): Godwin 7 (claim 6), Otton 6, Egbuka 4, Hurst 3, K. Johnson 2 (the "C. Johnson" in the transcript is almost certainly Kameron Johnson), Tez Johnson 2, Gainwell 2, Irving 0.',
  cite=[PBP, PWK], tags=['CONTRADICTED_BY_DATA (Godwin 7 not 6)'])
c(28, 'NOT_VERIFIABLE_HERE', 'DATA-CONSISTENT ANECDOTE (n = 1 start)',
  'Irving targets 7, 4, 4 under Mayfield (wks 1-3), then 0 under Daniels (wk 4); Daniels had 8 carries (6 scrambles). One start cannot separate a QB effect from game script. Our engine has no QB argument in target allocation (D-02); our frozen Irving projection was 4.01 targets with P(0 targets) 2.7%.',
  ours='Irving 4.01 targets', cite=[PBP, 'TB_DAL_DEFECT_REGISTER.json D-02'], hindsight='HINDSIGHT: Irving 3 targets, 1 rec TD in week 5.', tags=['OPINION (hypothesis)'])
c(29, 'THEIR_MODEL_OUTPUT', 'AGREE',
  'Our worlds: Irving P(anytime TD) 42.7%, P(2+ TD) 11.6%.', ours='0.427 / 0.116', theirs='~0.41-0.43 / ~0.10', cite=[WORLDS], hindsight='HINDSIGHT: Irving scored 2 TD (34.5 DK).')
c(30, 'THEIR_MODEL_OUTPUT', 'WE WERE LOWER ON TB',
  'Our worlds: P(TB win) 19.2% (DAL 80.8%); mean margin DAL +10.4. Theirs 26% (8.5-pt underdog). Our scoring centre is own-offence (no opponent adjustment, no market). One game cannot grade win probability.',
  ours='0.192', theirs='0.26', cite=[WORLDS], hindsight='HINDSIGHT: TB won 24-16; the exact scoreline region occurred in 2.2% of our worlds.')
c(31, 'VERIFIED_FACT', 'VERIFIED AT SECONDARY TIER',
  'Joey Porter Jr. is on the captured DAL inactive list (along with Cobie Durant, DeMarvion Overshown, James Houston and others), but the source is a SECONDARY RotoWire screenshot, not an official NFL document; "illness" is not in our data. Our DST draws depend only on opponent points (dst.py docstring; game.py:318-324), so defensive inactives do not move them.',
  cite=[INACT, 'nfl/dfs/salaries/showdown_tb_dal/OFFICIAL/SCENARIO.json official_inactives', 'nfl/sim/dst.py:1-30', 'nfl/sim/game.py:318-324'], tags=['CAPABILITY_GAP'])
c(32, 'OPINION', 'NOT TESTABLE AS STATED',
  'Partly checkable: DAL offence 30.5 ppg (wk 1-4), DAL defence EPA allowed rank 32/32, TB defence rank 6/32. "TB offence unknown" reflects the QB change (Daniels: 1 start).', cite=[PBP])
c(33, 'OWNERSHIP_FORECAST', 'VERIFIED', 'See C19: the most-duplicated actual lineups slant DAL (TB-DAL 2-4 or 1-5 in 75 of the top 100). TB-leaning builds (4-2, 5-1) were 13.2% of field entries.', cite=[RAWST])
c(34, 'THEIR_MODEL_OUTPUT', 'AGREE on DAL 20+; WE WERE LOWER on TB win',
  'Our worlds: P(DAL by 20+) 21.8%, P(TB win) 19.2%.', ours='0.218 / 0.192', theirs='0.23 / 0.24', cite=[WORLDS], hindsight='HINDSIGHT: TB won by 8.')
c(35, 'THEIR_MODEL_OUTPUT', 'DESCRIPTIVE ONLY', 'Theirs: Daniels CPT ~8% (sims). Ours: Daniels optimal CPT 3.1%, our CPT exposure 7.3% (150-max) / 20% (20-max). Field actual (answer key) 10.2%.', ours='opt CPT 3.1%', theirs='~8%', cite=[CAND, STAND])
c(36, 'VERIFIED_FACT', 'SALARY VERIFIED; RUSHING YARDS CORRECTED',
  'Daniels FLEX $8,600 (verified). Week 4 (his only start before this game): 8 carries (6 scrambles) for 55 yds (pbp; nflverse weekly 55), not 45. Week 3 relief: 1 carry. Our engine projected 3.33 carries / 19.4 rush yds from a generic QB cohort prior (D-03).',
  ours='3.33 carries, 19.4 rush yds, P(50+) 10.2%', cite=[PBP, PWK, SAL, 'TB_DAL_DEFECT_REGISTER.json D-03', 'docs/QB_REGIME_ROOT_CAUSE_2026-10-08.md'],
  hindsight='HINDSIGHT: 7 carries, 23 yds.', tags=['CONTRADICTED_BY_DATA (45 vs 55 yds)'])
c(37, 'NOT_VERIFIABLE_HERE', 'SAME AS C28 (n = 1)', 'See C28. The data are consistent with the claim but one start cannot establish it.', cite=[PBP])
c(38, 'THEIR_MODEL_OUTPUT', 'MATERIAL DISAGREEMENT',
  'Our worlds: P(Daniels 50+ rush yds) 10.2% (p90 50.5 yds; P(45.5+) 12.6%). Theirs 38%. Pregame evidence (8 carries/55 yds in his one start) leans toward theirs. This is defect D-03 (QB rushing from a cohort prior).',
  ours='0.102', theirs='0.38', cite=[WORLDS, PBP], hindsight='HINDSIGHT: 23 rush yds (under 50); that does not settle which number was better.')
c(39, 'THEIR_MODEL_OUTPUT', 'DESCRIPTIVE ONLY', 'Their FLEX exposures. Ours (150-max R1): Irving 50%, Javonte 50%, Pickens 30%. Field actual: Irving 24.0%, Javonte 37.0%, Pickens 28.3%.', cite=['OFFICIAL_ELIGIBILITY_FIX_R1/SHOWDOWN_TB_DAL_EXPOSURES.csv', STAND])
c(40, 'OWNERSHIP_FORECAST', 'FLOURNOY VERIFIED; GOODSON "nearly unowned" CONTRADICTED; USAGE VERIFIED',
  'Actual FLEX: Flournoy 29.1%, exactly 6th-highest (verified). Goodson 8.8% FLEX / 0.2% CPT, which is low but not "nearly unowned" (their 10% was about field). Goodson weeks 3-4: 9 carries + 2 targets = 11 opportunities (verified). Our BLEND forecast for Goodson: 4.5% FLEX.',
  ours='Goodson BLEND FLEX 4.5%; optimal FLEX 18.6%', cite=[STAND, PBP, OWNF])
c(41, 'THEIR_MODEL_OUTPUT', 'RECORD ONLY (market content excluded)',
  'Sportsbook props are prohibited model inputs here and are recorded only as a capability. Their projection 18.4 vs ours 14.0 (FC 12.1). Price gap VERIFIED: Daniels $8,600 vs Pickens $9,400 = $800.',
  ours='Daniels 13.99 DK', theirs='18.4', cite=[SAL, 'OFFICIAL/SHOWDOWN_TB_DAL_PROJECTIONS.csv'], hindsight='HINDSIGHT: 13.86 DK.', tags=['MARKET_CONTENT_NOT_USED'])
c(42, 'OPINION', 'PARTLY SUPPORTED BY OPPORTUNITY DATA',
  'Pickens weeks 1-4: 28 targets, 0 TD; red-zone targets 3 of DAL\'s 22 (Lamb 6, Flournoy 5, Ferguson 4). Zero TDs on 28 targets is below expectation, but his red-zone role is small, so "regress up" is only partly supported. Our opportunity-based TD expectation was 0.38 per game.',
  ours='mean TD 0.381', cite=[PBP, WORLDS], hindsight='HINDSIGHT: 1 TD.')
c(43, 'OWNERSHIP_FORECAST', 'VERIFIED', 'Actual CPT: Dak 16.4, Pickens 12.0, Javonte 15.1, Lamb 17.1. All four sit in 12-20%. Our sealed BLEND had Dak 33.7 and Lamb 37.3 (about 2x too high), Javonte 9.9 and Pickens 3.9 (too low).', cite=[STAND, OWNF])
c(44, 'OWNERSHIP_FORECAST', 'CONTRADICTED_BY_ACTUAL', 'Lamb out-owned Pickens at CPT: 17.1% vs 12.0% (150-max); 17.6 vs 11.1 and 17.8 vs 10.4 in the 20-max contests.', cite=[STAND, 'TB_DAL_2026W5_FIELD_STUDY.json'], tags=['CONTRADICTED_BY_DATA'])
c(45, 'PRINCIPLE', 'TESTABLE ONLY ACROSS MANY SLATES',
  'Our 20-max portfolios had 50% TB captains (Irving 4, Daniels 4, Otton 1, Buccaneers 1 of 20); the 150-max had 27% TB captains. The rule was satisfied without being coded. Our optimizer has no rule of this kind; captain diversity arises only from world coverage plus the 30% captain cap.',
  cite=['OFFICIAL_ELIGIBILITY_FIX_R1/SHOWDOWN_TB_DAL_CPT_EXPOSURES.csv', 'nfl/tools/showdown_to_portfolio.py:136-138'])
c(46, 'PRINCIPLE', 'PARTLY CONSISTENT WITH OUR WORLDS',
  'A TB pass catcher is the optimal CPT in 12.9% of our worlds. In those worlds TB throws more (38.8 vs 34.0 attempts) and the best skill score elsewhere is lower (28.6 vs 33.2 DK), but the game total is unchanged (50.5 vs 49.8). That supports "nobody else explodes" but not "TDs scarce, drives stall".',
  ours='P(TB pass-catcher optimal CPT) 0.129', cite=[CAND])
c(47, 'PRINCIPLE', 'CONSISTENT WITH OUR WORLDS',
  'In 24.6% of our worlds the optimal lineup\'s captain is NOT the world\'s top DK scorer.', ours='0.246', cite=[CAND],
  hindsight='HINDSIGHT: the hindsight optimum used Irving (34.5) as CPT, who was the top scorer; the "Olave Monday" reference is to ATL@NO and was not re-checked here.')
c(48, 'PRINCIPLE', 'TRUE BY CONSTRUCTION', 'CPT scores 1.5x FLEX points at 1.5x salary (DK rule; DRAWS CPT_RULE). Arithmetic identity, encoded in our scorer.', cite=['OFFICIAL/SHOWDOWN_TB_DAL_2026W5_DRAWS.json CPT_RULE', SAL])
c(49, 'THEIR_MODEL_OUTPUT', 'DESCRIPTIVE ONLY', 'Theirs: Otton CPT 5.3% vs ~2% field. Field actual CPT 2.3% (their field estimate held). Ours: Otton CPT 3.3% (150-max), optimal 7.5%.', cite=[STAND, CAND], tags=['OWNERSHIP_FORECAST (~2%)'])
c(50, 'THEIR_MODEL_OUTPUT', 'OWNERSHIP VERIFIED; SIM DISAGREES; DEPENDENCY CONFIRMED IN OUR WORLDS',
  'Egbuka actual FLEX 14.4% (their ~15%: verified). Our P(Egbuka 100+ rec yds) 9.2% vs their 3.5%; driven by our TB pass-volume centre (Daniels 34.6 att vs 27 in his one start; D-02). Inside our worlds, Egbuka DK correlates +0.35 with Daniels attempts; conditional on Daniels <= 27 attempts, P(100+) = 1.6%, close to theirs. First-TD probability is not measurable (no event order in our worlds).',
  ours='P(100+) 0.092; |att<=27: 0.016', theirs='0.035', cite=[STAND, WORLDS, 'TB_DAL_DEFECT_REGISTER.json D-02'], hindsight='HINDSIGHT: 38 rec yds; Daniels 25 attempts.')
c(51, 'OPINION', 'NOT SUPPORTED IN AGGREGATE; THE CONDITIONAL VERSION IS UNTESTED',
  'Measured RB1~RB2 same-club DK correlation is 0.00 [-0.04, 0.05]; our worlds give Javonte-Goodson -0.03 (DK) and -0.04 (carries). Script-conditional co-movement has not been measured. In our engine, TD allocation does not follow per-world carries (rush_td_share is fixed, game.py:489-490), so a world with more Goodson carries does not raise his TD chance. That is a modelling simplification.',
  ours='corr DK -0.034', cite=['nfl/sim/PAIR_CORRELATIONS.json RB1~RB2', WORLDS, 'nfl/sim/game.py:481-490'], tags=['CAPABILITY_GAP'])
c(52, 'THEIR_MODEL_OUTPUT', 'AGREE (prediction-market figure excluded)', 'Ours 15.0%; theirs 13.9%. The prediction-market price is betting content and is recorded only.', ours='0.150', theirs='0.139', cite=[WORLDS], tags=['MARKET_CONTENT_NOT_USED'])
c(53, 'NOT_VERIFIABLE_HERE', 'PARTLY CONTRADICTED; MECHANISM SPECULATIVE',
  'TB week 4 maximum targets was 7 (Godwin), not 6. Hurst had 3 targets vs Egbuka 4 (1 fewer: verified) on 25 snaps vs 59 (34 fewer, not ~25; Hurst himself played 25). Backup-QB familiarity is speculation; nothing in the repo measures it.',
  cite=[PBP, SNAP], tags=['CONTRADICTED_BY_DATA (max 7)'])
c(54, 'THEIR_MODEL_OUTPUT', 'BOTH TINY; OURS SMALLER', 'Our worlds: P(Daniels < 15 pass attempts) 0.25% (5/2000); mean 34.6 attempts.', ours='0.0025', theirs='0.019', cite=[WORLDS], hindsight='HINDSIGHT: 25 attempts.')
c(55, 'THEIR_MODEL_OUTPUT', 'OUR ENGINE DISAGREES ON LAMB AND DAK',
  'Our CPT optimal minus sealed BLEND forecast: Dak -20.2 (BLEND forecast 33.7% far above our 13.5% optimal), Javonte +1.6, Pickens -1.5, Lamb -0.5. Against the FC-proportional baseline: Lamb +25.3 (most positive), Dak +1.8, Javonte +1.8, Pickens -6.9. Their board had Lamb most negative.',
  cite=[CAND, OWNF], hindsight='HINDSIGHT: against actual CPT ownership, Lamb +19.7, Pickens -9.6, Dak -2.9.')
c(56, 'NOT_VERIFIABLE_HERE', 'NOT MEASURABLE IN OUR WORLDS', 'Our worlds carry per-game TD counts with no ordering, so "first TD" cannot be computed. Goodson P(any TD) 22.2%.', ours='not computable', theirs='0.041', cite=[WORLDS], tags=['CAPABILITY_GAP'])
c(57, 'OWNERSHIP_FORECAST', 'LINEUP FOUND; LEVEL HIGHER THAN THEIR FORECAST; CAP CLUSTERING VERIFIED',
  'The six-player set {Dak, Aubrey, Lamb, Cowboys DST, Daniels, Flournoy} appears in the 150-max 352 times across captains. With Dak as CPT ($50,000 exactly, the only arrangement at "about 50K"): 295 copies, the 29th most-duplicated lineup. Daniels CPT ($49,100) 36; Aubrey CPT 8; Flournoy CPT 7; Cowboys CPT 6; Lamb CPT would cost $50,700 (illegal). In the 20-max contests the Dak-CPT version had 144 and 124 copies (ranks 7 and 9). Their figure (79) does not name a contest. If it was the 150-max, actual was about 3.7x higher. Cap clustering is verified: the 25 most-duplicated lineups all cost $49,500-$50,000; mean other-copies per entry is 112 at $50,000 and 124 at $49,500-49,900, against 9.8 below $48,000.',
  theirs='79 dupes', cite=[RAWST, SAL], tags=['VERIFIED_FACT (field)'])
c(58, 'OPINION', 'PROHIBITED PROCESS HERE', 'Manual boosting is not allowed in our system (no silent constants). The legitimate analogue is a declared scenario-conditional portfolio arm frozen before lock.', cite=['CLAUDE.md governing rule 2'])
c(59, 'PRINCIPLE', 'CONSISTENT WITH OUR PROCESS', 'Our OFFICIAL run used the post-inactives roster (inactives received 23:06Z, worlds written 23:08Z, kickoff 00:15Z).', cite=['OFFICIAL/SCENARIO.json', INACT])
c(60, 'POSTKICKOFF_EXCLUDED', 'EXCLUDED', 'In-game content (B 58:26 onward) is excluded from every prelock comparison.', cite=[])

def phase(x):
    if x['source'] == 'B' and x['timestamp'].startswith('58:26'):
        return 'POSTKICKOFF'
    return 'PRELOCK_A_MORNING' if x['source'] == 'A' else 'PRELOCK_B_AFTER_INACTIVES'

rows = []
for i, x in enumerate(ex, 1):
    r = {'id': f'C{i:02d}', 'source': x['source'], 'timestamp': x['timestamp'], 'phase': phase(x), 'extraction_kind': x['kind'], 'claim': x['claim']}
    r.update(L[i])
    rows.append(r)
assert len(rows) == 60 and all(i in L for i in range(1, 61))
from collections import Counter
doc = {'ARTIFACT': 'VIDEO_STRATEGY_EVIDENCE_LEDGER', 'slate': 'TB@DAL 2026 Week 5 Showdown (2026_05_TB_DAL)',
       'READING': 'Presenter statements are claims. Their sim numbers are THEIR model outputs, and their ownership numbers are THEIR forecasts. Nothing here enters our model. One slate is a diagnostic, not a dataset. HINDSIGHT notes use postgame data and are never evidence for or against a pregame process.',
       'third_video': {'url': 'https://www.youtube.com/watch?v=6uh5wC3Lecw', 'status': 'NO TRANSCRIPT; one web search (2026-10-09) returned nothing identifying this video ID. Title/topic UNKNOWN. SECONDARY/UNVERIFIED; no content inferred.'},
       'classification_counts': dict(Counter(r['classification'] for r in rows)),
       'data_sources': {'pbp_prelock': PBP, 'snaps_prelock': SNAP, 'weekly_stats_crosscheck': PWK, 'worlds': WORLDS, 'candidates': CAND, 'actual_ownership': STAND, 'raw_standings': RAWST, 'salaries': SAL, 'inactives': INACT, 'our_ownership_forecasts': OWNF},
       'claims': rows}
json.dump(doc, open(S + 'out/VIDEO_STRATEGY_EVIDENCE_LEDGER.json', 'w'), indent=1)
print(doc['classification_counts'])

md = ['# Video strategy evidence ledger: TB@DAL 2026 Week 5 Showdown', '',
      '**What this is.** All 60 claims from the two owner-supplied transcripts. Each claim is classified and, wherever',
      'the repository has the data, checked against it.', '',
      '**How to read it.**',
      '- Their sim numbers are their model outputs. Their ownership numbers are their forecasts.',
      '- Nothing here enters our model.',
      '- Notes marked **HINDSIGHT** use postgame data. They are never evidence about a pregame process.',
      '- One slate is a diagnostic, not a dataset.', '',
      '- **A** = morning strategy show.',
      '- **B** = live-before-lock, after inactives.',
      '- Content from B 58:26 is in-game and excluded.', '',
      '**Video C** (https://www.youtube.com/watch?v=6uh5wC3Lecw):',
      '- No transcript was supplied.',
      '- One web search found nothing identifying it.',
      '- Its title and topic are **UNKNOWN**. Nothing about its contents is inferred.', '',
      '**Prelock data used:**',
      f'- play-by-play: `{PBP}`',
      f'- snap counts: `{SNAP}`',
      f'- frozen worlds: `{WORLDS}`', '',
      '**Answer key only:**',
      f'- `{STAND}`',
      f'- `{RAWST}`', '',
      '**Classification counts:** ' + ', '.join(f'{k} {v}' for k, v in sorted(doc['classification_counts'].items())), '',
      '**Verdict labels.** A row\'s verdict column refines its classification. Examples:',
      '- `VERIFIED with one correction`',
      '- `PARTLY CONTRADICTED`', '',
      '| ID | Src/time | Claim (abridged) | Class | Verdict | What the data shows | Ours | Theirs | Cite |',
      '|---|---|---|---|---|---|---|---|---|']
def esc(s):
    return (s or '').replace('|', '/').replace('\n', ' ')
for r in rows:
    data = r['what_the_data_shows'] + (f" **{r['hindsight_note']}**" if r['hindsight_note'] else '')
    md.append(f"| {r['id']} | {r['source']} {r['timestamp']} | {esc(r['claim'][:140])} | {r['classification']} | {esc(r['verdict'])} | {esc(data)} | {esc(r['our_frozen_number'])} | {esc(r['their_stated_number'])} | {esc('; '.join(r['cite'][:3]))} |")
md += ['', '## What the checks found', '',
       '**Verified usage facts:**',
       '- Lamb had 21 targets in week 4.',
       '- Pickens had 3 targets in week 4 and 25 over weeks 1-3; weeks 1-3 were equal at 25 each.',
       '- Javonte had 13 carries inside the 10, 11 inside the 5, 5 rush TD and 1 rec TD.',
       '- Goodson had 16 snaps in week 4 and carries of 6 and 3.',
       '- Flournoy had 23 targets at roughly 75% of snaps.',
       '- Aubrey scored double digits in 3 of 4 weeks.',
       '- DAL allowed 28, 20, 34 and 30 points.',
       '- Irving had 0 targets in week 4.',
       '- Flournoy was the 6th-highest-owned FLEX.',
       '- The popular captains were in the 12-20% band.',
       '- The field was Dallas-heavy.',
       '- The most-duplicated lineups sat at the salary cap.', '',
       '**Contradicted or corrected:**',
       '- The Monday game was ATL@NO, not ATL@WAS.',
       '- Javonte was not tied with Henry inside the 10: Henry had 17, Williams 13. Inside the 5 they were tied.',
       '- Egbuka\'s best game was 11.3 DK, not "none above 11".',
       '- Godwin had 7 week-4 targets, not 6; the maximum TB target count was 7, not 6.',
       '- Daniels ran for 55 yards in week 4, not 45.',
       '- Pickens was not the 2nd-highest-owned captain (he was 4th) or the 3rd-highest FLEX (he was 7th).',
       '- Pickens did not out-own Lamb at captain.',
       '- Goodson was not "nearly unowned": he was 8.8% FLEX.',
       '- "Correlation barely matters" is contradicted for QB-receiver pairs.', '',
       '**Their model against ours, before kickoff:**',
       '- Agreement: Lamb P(TD), Irving P(TD) and P(2+ TD), P(DAL by 20+), and the joint Javonte and Goodson TD.',
       '- Material disagreement: Pickens P(TD) (ours 32% vs ~44%), Daniels 50+ rush yards (ours 10% vs 38%), Egbuka 100+ receiving yards (ours 9% vs 3.5%), P(TB win) (ours 19% vs 24-26%) and the leverage signs on Lamb and Pickens.']
open(S + 'out/VIDEO_STRATEGY_EVIDENCE_LEDGER.md', 'w').write('\n'.join(md) + '\n')
