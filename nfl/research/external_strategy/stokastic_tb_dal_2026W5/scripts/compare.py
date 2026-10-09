import json
S = '/tmp/claude-0/-home-user-mlb-prop-system-v7/8de98087-4781-5a10-ae09-ef74590f8116/scratchpad/stokastic/'
F = json.load(open(S + 'out/SUPPORT_OUR_FROZEN_WORLD_NUMBERS.json'))
O = json.load(open(S + 'out/SUPPORT_OUR_OPTIMAL_FREQUENCY.json'))['R1_ENTERED_POOL']
W = {r['player']: r for r in json.load(open(S + 'out/SUPPORT_OWNERSHIP_FORECAST_VS_ACTUAL.json'))['rows']}
pl = F['players']; g = F['game_script']; of = O['player_optimal_frequency']

def own(p):
    r = W[p]
    return {k: r[k] for k in ('opt_CPT_pct', 'opt_FLEX_pct', 'our_CPT_exposure_pct_R1', 'our_rostered_exposure_pct_R1',
                              'blend_CPT_pct', 'blend_FLEX_pct', 'fconly_CPT_pct', 'fconly_FLEX_pct', 'scown2_cand_CPT_pct',
                              'scown2_cand_FLEX_pct', 'fcprop_CPT_pct', 'fcprop_FLEX_pct', 'ACTUAL_field_CPT_pct', 'ACTUAL_field_FLEX_pct')}

T = []
def topic(name, ours, theirs, q, hindsight, ownership=None):
    T.append({'topic': name, 'our_frozen_pregame_numbers': ours, 'their_stated_numbers': theirs,
              'ownership_and_exposure_pct': ownership, 'seven_questions': q, 'HINDSIGHT_ONLY': hindsight})

topic('Lamb vs Pickens',
      {'Lamb': {k: pl['CeeDee Lamb'][k] for k in ('mean_dk', 'P_anytime_TD', 'P_2plus_TD', 'mean_targets', 'P_dk_lt5', 'p10_dk', 'p90_dk')},
       'Pickens': {k: pl['George Pickens'][k] for k in ('mean_dk', 'P_anytime_TD', 'P_2plus_TD', 'mean_targets', 'P_dk_lt5', 'p10_dk', 'p90_dk')},
       'projected_target_share': {'Lamb': 0.314, 'Pickens': 0.163, 'source': 'TB_DAL_DEFECT_REGISTER D-04'},
       'efficiency_factor_Lamb_rec_yards': 1.4095,
       'prelock_usage_fact': 'targets wk1-4 Lamb 8/9/8/21, Pickens 6/8/11/3; weeks 1-3 equal (25 each)'},
      {'P_TD': 'Lamb ~51%, Pickens ~44% (ambiguous)', 'leverage': 'Pickens positive CPT and FLEX; Lamb most negative'},
      {'1_engine_models_it': 'YES for volume, efficiency and TD from opportunity. NO between-game share volatility (D-04). NO credible dud tail: P(Lamb <5 DK) 0.45% in our worlds vs 6.6% [4.0, 9.5] empirical for 20+ ppg WRs (D-01).',
       '2_code_or_discussed': 'In code: target share pooled by target count, proj_v1.py:277-303 (_combine) and :306-345 (current_season_shares); per-world efficiency factor, classic_slate_run.py:85 (efficiency_worlds); share dispersion is a Dirichlet-multinomial or logistic-normal, game.py:382-408.',
       '3_optimizer_consumes': 'YES. The draws feed the hit-proxy objective. Lamb was the best captain in 36.8% of worlds and sat at the 50% player cap in every contest.',
       '4_verifiable': 'YES. P(TD) and dud rates can be graded by tail PIT across slates; one game cannot grade them.',
       '5_disagreed_with_them': 'YES on Pickens (P(TD) 32% vs ~44%) and on leverage sign. Agreed on Lamb P(TD) (53% vs ~51%). Our mean gap (28.3 vs 11.7 DK) was far wider than FC\'s (22.1 vs 18.0).',
       '6_would_flag_portfolio_risk': 'NOT AS BUILT. The worlds understated Lamb\'s bad-game tail about 10x, so concentration risk at the cap was invisible. A calibrated tail (D-01) plus share volatility (D-04) is what would have exposed it. Their argument rested on the equal weeks 1-3 targets, a fact our pooled share gave one game\'s worth of weight against.',
       '7_research_needed': 'D-01 star-dud tail and D-04 share volatility; decompose our-vs-FC gap into volume and efficiency for WR1s (D-11); acceptance by tail PIT on held-out 2025 replay.'},
      'Lamb 2.9 DK (5 targets, in-game injury, returned Q4); Pickens 31.0 DK (13 targets, 1 TD). One outcome. It is not evidence that the equal-share reading was right.',
      {'Lamb': own('CeeDee Lamb'), 'Pickens': own('George Pickens')})

cb = {p: {'opt_CPT': of[p]['CPT'], 'cpt_salary': of[p]['cpt_salary']} for p in ['CeeDee Lamb', 'Dak Prescott', 'Javonte Williams', 'Bucky Irving', 'Cade Otton', 'Jalon Daniels', 'Emeka Egbuka', 'George Pickens']}
topic('Captain ownership and ceiling',
      {'optimal_captain_share': cb, 'cpt_p95_from_CPT_BOARD': {'Lamb': 72.41, 'Dak': 54.56, 'Javonte': 50.64, 'Irving': 45.9, 'Daniels': 38.19, 'Pickens': 37.99, 'Egbuka': 37.03, 'Otton': 35.07},
       'share_worlds_optimal_cpt_is_top_scorer': O['share_worlds_optimal_captain_is_world_top_scorer'],
       'P_DST_optimal_CPT': 0.0115, 'P_TB_pass_catcher_optimal_CPT': 0.129},
      {'CPT_ownership': 'Pickens ~7-8% (A), 12-20% for Dak/Pickens/Javonte/Lamb (B), Pickens > Lamb (B)', 'Daniels_CPT': '~8% in their sims'},
      {'1_engine_models_it': 'Ceiling: YES (per-world CPT = 1.5 x FLEX). Captain ownership: SHADOW ONLY (BLEND, FC_ONLY, SC-OWN-2), never in selection.',
       '2_code_or_discussed': 'Ceiling in code (DRAWS CPT_RULE; CPT_BOARD). Ownership in code as shadow: field/showdown_shadow_field.py, research/ownership/sc_own_rotation_2.py; selection never reads it (showdown_portfolio.py:18-29; showdown_next_slate.py:395-462).',
       '3_optimizer_consumes': 'Ceiling YES (through the worlds). Ownership NO.',
       '4_verifiable': 'YES. Sealed CPT forecasts are graded against DK %Drafted: CPT MAE BLEND 1.83, FC_ONLY 1.56, SC-OWN-2 1.80, no-fit FC-proportional 1.09 (Spearman 0.93).',
       '5_disagreed_with_them': 'YES. Our BLEND forecast put Lamb 37.3 and Dak 33.7 (actual 17.1 and 16.4), about 2x too high on chalk captains. Their 12-20% band was correct. Our FC-proportional baseline (computed postgame from the pregame FC file) put both at about 11.6, too low.',
       '6_would_flag_portfolio_risk': 'Only if ownership entered selection. Our 22% Lamb CPT against a true 17% field is not a large overweight. The risk was correlated chalk (Lamb plus Dak) and duplication, not captain ownership by itself.',
       '7_research_needed': 'T1 ownership_v2 must beat the FC-proportional baseline on CPT MAE, STAR-bucket bias and log score leave-one-slate-out, then on 3 of 4 prospective slates. STAR-bucket CPT MAE is 9-11 pp for every model.'},
      'Top-1% captains were Irving 49% and Pickens 49%; our CPT exposure was Irving 7.3%, Pickens 4.0%.',
      {p: own(p) for p in ['CeeDee Lamb', 'Dak Prescott', 'Javonte Williams', 'George Pickens', 'Jalon Daniels', 'Bucky Irving']})

d = pl['Jalon Daniels']
topic('Daniels rushing',
      {k: d[k] for k in ('mean_carries', 'mean_rush_yds', 'P_rush_yds_50plus', 'P_rush_yds_45_5_plus', 'rush_yds_p90', 'mean_pass_att', 'P_pass_att_lt15', 'mean_dk')},
      {'P_50plus_rush': 0.38, 'P_lt15_att': 0.019, 'projection': 18.4},
      {'1_engine_models_it': 'WEAKLY. QB rushing comes from a generic cohort prior pooled with relief appearances (D-03), and team pass volume has no QB argument (D-02).',
       '2_code_or_discussed': 'In code: proj_v1.py:1295-1298 (hierarchical/cohort prior), :277-303 (_combine), :167 (team_volume, QB-independent). Root cause documented in docs/QB_REGIME_ROOT_CAUSE_2026-10-08.md section 1 and QB_REGIME_AUDIT_PRECOMPUTE_TBQB_DANIELS_R10.json. A QB-conditioned model is a separate active workstream, NOT_VALIDATED.',
       '3_optimizer_consumes': 'YES, as projected (3.3 carries), so too low.',
       '4_verifiable': 'YES. Rush-yard PIT per QB start, and scramble rate under starter vs relief, graded across starts.',
       '5_disagreed_with_them': 'YES, materially: 10.2% vs 38% for 50+ rush yds. The pregame evidence (8 carries, 6 scrambles, 55 yds in his one start; 27 attempts) pointed their way, and our own prelock audit flagged it.',
       '6_would_flag_portfolio_risk': 'YES, if fixed. Fewer TB pass attempts and more Daniels rushing lowers TB receivers (Egbuka, Otton, Godwin were 44%, 47% and 32% rostered by us) and raises Daniels\' floor.',
       '7_research_needed': 'Partially pooled QB-start rushing model (repair program section G steps 2-3); pass-rate conditioning on QB identity; acceptance on held-out QB changes 2021-2025.'},
      'Daniels: 7 carries, 23 yds, 25 attempts (beat 11% of our attempt simulations).')

i = pl['Bucky Irving']
topic('Irving opportunity and receiving role',
      {'mean_targets': i['mean_targets'], 'P_0_targets': F['irving_targets_dist']['P_0_targets'], 'mean_carries': i['mean_carries'], 'P_anytime_TD': i['P_anytime_TD'], 'P_2plus_TD': i['P_2plus_TD'], 'mean_dk': i['mean_dk'], 'opt_FLEX': of['Bucky Irving']['FLEX'], 'opt_CPT': of['Bucky Irving']['CPT']},
      {'P_TD': '~41-43%', 'P_2TD': '~10%', 'hypothesis': 'Daniels runs instead of checking down, so Irving gets fewer targets'},
      {'1_engine_models_it': 'Rushing role YES. Receiving role is pooled across QBs. No QB-dependency of RB target share.',
       '2_code_or_discussed': 'Only discussed (D-02; QB_REGIME audit). No code path conditions RB targets on QB identity.',
       '3_optimizer_consumes': 'YES (4.0 targets baked into the draws).',
       '4_verifiable': 'Across many QB changes only. Week 4 (0 targets) is n = 1.',
       '5_disagreed_with_them': 'NO on P(TD), which agreed. Their target hypothesis is not reflected in our model.',
       '6_would_flag_portfolio_risk': 'Small. Irving\'s value in our worlds came from carries; the receiving share was a minor part.',
       '7_research_needed': 'Historical QB-change panel: RB target share and QB scramble rate before and after starter changes, 2016-2025, clustered by team.'},
      'Irving 21 carries / 165 yds, 3 targets, 2 TD, 34.5 DK. The checkdown hypothesis was neither confirmed nor refuted (3 targets).',
      {'Irving': own('Bucky Irving')})

j = pl['Javonte Williams']
topic('Javonte goal-line',
      {'P_anytime_TD': j['P_anytime_TD'], 'P_2plus_TD': j['P_2plus_TD'], 'mean_TD': j['mean_TD'], 'mean_carries': j['mean_carries'], 'joint_TD_with_Goodson': F['joint'], 'prelock_fact': '13 inside-10 / 11 inside-5 carries wk1-4; 11 of 12 DAL inside-5 carries'},
      {'P_both_TD': '~13% (A), 13.9% (B)'},
      {'1_engine_models_it': 'PARTIALLY. Red-zone (inside 20) intensity is modelled. Goal-line (inside 5) share is computed and discarded. TD allocation within a club uses fixed shares independent of per-world carries.',
       '2_code_or_discussed': 'gl_carry_share computed at proj_v1.py:338-339 and never consumed (no comb(\'gl_carry_share\')); rz_intensity at proj_v1.py:663-681; TD shares fixed at showdown_draws.py:111; allocation at game.py:481-490.',
       '3_optimizer_consumes': 'Inside-20 only, via TD shares.',
       '4_verifiable': 'YES. Rush-TD calibration by goal-line share bucket across 2021-2025 replay.',
       '5_disagreed_with_them': 'NO. Joint 15.0% vs 13-14%. Our backs\' TD events are uncorrelated (r = -0.004).',
       '6_would_flag_portfolio_risk': 'Low on this slate. Our Javonte P(TD) of 68% already reflected his role.',
       '7_research_needed': 'Test whether adding gl_carry_share improves rush-TD log score over rz_intensity alone (pre-registered, LOSO by season). Make TD allocation conditional on per-world carries.'},
      'Javonte 1 rush TD (1-yd). Goodson no stats.',
      {'Javonte': own('Javonte Williams'), 'Goodson': own('Tyler Goodson')})

topic('DAL-heavy vs TB-heavy builds',
      {'optimal_split_TB_DAL': O['optimal_split_TB_DAL'], 'our_entered_150max_split': {'1-5': 0.073, '2-4': 0.227, '3-3': 0.353, '4-2': 0.293, '5-1': 0.053},
       'pregame_BLEND_field_split_forecast': {'1-5': 25.9, '2-4': 42.9, '3-3': 27.0, '4-2': 4.2, '5-1': 0.0}, 'P_TB_win': g['P_TB_win']},
      {'claim': 'TB 4-2 low owned, 5-1 nearly unowned; most-duped lineups DAL-heavy; any TB lean is naturally leveraged'},
      {'1_engine_models_it': 'Football side YES (worlds). Field split: SHADOW ONLY (shadow board team_split).',
       '2_code_or_discussed': 'Structural split computed at showdown_portfolio.py:216-232 (tie-break only). Field split forecast at field/showdown_shadow_board.py.',
       '3_optimizer_consumes': 'Only as a tie-break (structural duplication index, +1 for a 5-1).',
       '4_verifiable': 'YES. Actual field split from standings: 1-5 22.0%, 2-4 35.4%, 3-3 29.4%, 4-2 11.5%, 5-1 1.7%.',
       '5_disagreed_with_them': 'NO on direction. Our BLEND forecast also had DAL-heavy chalk, though it under-predicted 4-2 (4.2 vs 11.5).',
       '6_would_flag_portfolio_risk': 'Our entered portfolio was already TB-leaning (34.6% 4-2 or 5-1 vs field 13.2%), as a by-product of world coverage. No leverage was computed.',
       '7_research_needed': 'Field-split model in T2, with split leverage reported per contest.'},
      'Field top 1%: 3-3 58%, 4-2 18%, 2-4 21%.')

topic('Salary utilisation',
      {'optimal_lineup_salary_band_share': O['optimal_salary_band'], 'our_entered': {'mean_salary': 48470, 'share_le_48000': 0.187}, 'pregame_BLEND_field_salary_left_mean': 401},
      {'claim': 'most-duped lineups sit at or near the cap and "make sense"'},
      {'1_engine_models_it': 'Our worlds YES. Field salary use only as a shadow (salary_left).',
       '2_code_or_discussed': 'showdown_portfolio.py:216-232 (cap salary +1 in the duplication tie-break); B4 duplication model uses salary-left features (DUPE_SHADOW_B4 theta sal_0 1.72, sal_100-500 1.51 ...).',
       '3_optimizer_consumes': 'Tie-break only.',
       '4_verifiable': 'YES. Actual 150-max: 10.3% of entries at $50,000, 41.5% at $49,500-49,900, 9.5% below $48,000; mean $49,142; mean salary left $858 vs BLEND forecast $401.',
       '5_disagreed_with_them': 'NO. Duplication by salary band is verified: 112 to 124 other copies per entry at $49,500-50,000 vs 9.8 below $48,000.',
       '6_would_flag_portfolio_risk': 'YES, if duplication were modelled. Cap-adjacent chalk builds are the most shared.',
       '7_research_needed': 'Fit salary-left propensity for T2 from other slates (LOSO); report the duplication by salary band of our lineups prelock.'},
      'Field top 1%: mean salary $49,457; 3.5% at or below $48,000.')

topic('Low-owned FLEX',
      {'opt_FLEX_vs_BLEND_forecast': {p: (W[p]['opt_FLEX_pct'], W[p]['blend_FLEX_pct']) for p in ['Tyler Goodson', 'Buccaneers', 'Emeka Egbuka', 'Chris Godwin Jr.', 'Brevyn Spann-Ford', 'Payne Durham', 'Sean Tucker', 'Tez Johnson']}},
      {'claim': 'Goodson nearly unowned; Flournoy 6th-highest FLEX; Egbuka ~15%'},
      {'1_engine_models_it': 'Football side YES. Ownership shadow only.',
       '2_code_or_discussed': 'SC-OWN-ROTATION-2 (research/ownership/sc_own_rotation_2.py) targets exactly the cheap-rotation bucket. Prospective slate 1 of 4: FAILS (cheap |bias| 5.74 vs 2.59; total FLEX MAE +2.55 pp). Its candidate also forecast Payne Durham FLEX at 94.5% against an actual 1.3%.',
       '3_optimizer_consumes': 'NO.',
       '4_verifiable': 'YES. Cheap-bucket FLEX MAE and bias per slate.',
       '5_disagreed_with_them': 'Goodson: they said about 10% (field), our BLEND 4.5%, actual 8.8%. Flournoy: our BLEND 38.7%, actual 29.1%; their rank was right.',
       '6_would_flag_portfolio_risk': 'Limited. Low-owned FLEX matters for duplication and leverage, which we do not model.',
       '7_research_needed': 'Fix the SC-OWN-2 candidate failure mode (the punt-TE explosion); keep FC-proportional as the incumbent.'},
      'Tez Johnson (11.6% owned, 7.4 DK) was in the hindsight optimum; our worlds had him optimal in 1.6%.',
      {p: own(p) for p in ['Tyler Goodson', 'Ryan Flournoy', 'Emeka Egbuka', 'Tez Johnson', 'Payne Durham']})

topic('Leverage',
      {'definition_used': 'pregame leverage = our optimal frequency minus our sealed ownership forecast (BLEND) and minus the FC-proportional baseline; exposure leverage = our exposure minus forecast',
       'CPT_opt_minus_BLEND': {p: W[p].get('pregame_CPT_leverage_opt_minus_blend') for p in ['CeeDee Lamb', 'Dak Prescott', 'Javonte Williams', 'George Pickens', 'Bucky Irving', 'Jalon Daniels', 'Cade Otton']},
       'CPT_opt_minus_FCprop': {p: W[p].get('pregame_CPT_leverage_opt_minus_fcprop') for p in ['CeeDee Lamb', 'Dak Prescott', 'Javonte Williams', 'George Pickens', 'Bucky Irving', 'Jalon Daniels', 'Cade Otton']}},
      {'claim': 'CPT: Dak most positive, Javonte and Pickens positive, Lamb most negative; FLEX: Goodson, Dak, DAL DST, Javonte, Gainwell, Daniels, Flournoy positive; Lamb, Aubrey, Irving negative'},
      {'1_engine_models_it': 'NO. Computed on shadow boards only (SHADOW_LEVERAGE_*.csv), against the OFFICIAL exposures, never in selection.',
       '2_code_or_discussed': 'field/showdown_shadow_board.py (leverage = our exposure - shadow ownership). No optimal-frequency-vs-ownership leverage exists in code; the numbers here were computed for this report.',
       '3_optimizer_consumes': 'NO.',
       '4_verifiable': 'Partly. Ownership forecasts are gradeable. Whether leverage improves payout needs payout tables and many contests.',
       '5_disagreed_with_them': 'YES. Against FC-proportional, Lamb was our MOST positive captain (+25.3) and Pickens negative (-6.9), the reverse of theirs. Against BLEND, Dak was very negative (-20.2) because BLEND over-forecast Dak CPT.',
       '6_would_flag_portfolio_risk': 'Depends on the ownership model, which on this slate was miscalibrated about 2x on chalk captains. Leverage built on a bad ownership forecast is noise.',
       '7_research_needed': 'Define leverage with uncertainty (forecast intervals); test only after T1 beats the baseline.'},
      'Against actual CPT ownership: Lamb +19.7, Pickens -9.6, Dak -2.9.')

topic('Winning-lineup scenarios',
      {'game_script_board_R1': 'TB leads 19.2%; DAL blowout >=14 37.4%; one-score 34.6%; grinder 25.1%; shootout 25.0%; TB pass-heavy comeback 20.1%',
       'P_DAL_le16_and_TB_ge24': g['P_DAL_le16_and_TB_ge24'], 'candidate_pool_proxy_coverage_150max': 'about 0.99 in every script'},
      {'claim': 'many winning builds DAL 5-1/4-2 (their sims); TB receiver CPT only if TDs scarce'},
      {'1_engine_models_it': 'YES. Scripts are labels over the same worlds (GAME_SCRIPT_BOARD).',
       '2_code_or_discussed': 'showdown_portfolio.py game-script board and audit (by_best_game_script).',
       '3_optimizer_consumes': 'Implicitly. Coverage of worlds covers scripts.',
       '4_verifiable': 'Script frequencies are gradeable over many games. Winning composition needs the field.',
       '5_disagreed_with_them': 'Mild. Our TB-win share (19%) was lower than theirs (24-26%).',
       '6_would_flag_portfolio_risk': 'NO. A lineup that wins a script in our worlds may be shared by hundreds of entries, and the objective cannot see that.',
       '7_research_needed': 'T4: rank in the simulated field per world.'},
      'TB 24-16; the hindsight-best lineup averaged 77.4 in our worlds (p95 113.0) and was in no candidate pool.')

topic('Duplication and uniqueness',
      {'B4_sealed_prediction_our_lineups': {'median_copies': 1.3, 'spearman_vs_actual': 0.708, 'sum_actual_over_pred': 0.16},
       'shadow_board_exact': {'median': 0.0, 'spearman': 0.254}},
      {'claim': 'most-duped lineup ~79 dupes (Dak, Aubrey, Lamb, DAL DST, Daniels, Flournoy); build unique lineups around popular players'},
      {'1_engine_models_it': 'SHADOW ONLY (B4 maxent, B3S, shadow-board exact and product).',
       '2_code_or_discussed': 'field/showdown_dupe_shadow.py (B4), field/showdown_dupe_research.py, field/showdown_shadow_board.py.',
       '3_optimizer_consumes': 'NO (D-06). Only the structural tie-break.',
       '4_verifiable': 'YES. Actual copies per lineup from standings.',
       '5_disagreed_with_them': 'Their named lineup had 295 actual copies (Dak CPT, $50,000) in the 150-max. Our B4 sealed artifact priced only our own lineups, so we have no pregame number for it.',
       '6_would_flag_portfolio_risk': 'YES, if it were calibrated. Our lineups averaged 40 field copies (max 455), and B4 ranked them well (Spearman 0.71). Its level was wrong in both directions: median under-predicted about 9x, a few heavy-chalk lineups over-predicted by orders of magnitude.',
       '7_research_needed': 'FIELD_AND_DUPLICATION_MODEL_SPEC (this package): recalibrate the level and tail; price any lineup, not only ours.'},
      'Winning lineup shared by 18 entries (150-max).')

topic('Game-script probabilities',
      {k: g[k] for k in ('P_DAL_win', 'P_TB_win', 'P_DAL_by_20_plus', 'P_DAL_by_10_plus', 'mean_margin_DAL_minus_TB', 'mean_total', 'mean_DAL_pts', 'mean_TB_pts')},
      {'P_DAL_by_20plus': 0.23, 'P_TB_win': '0.24 (B), 0.26 (A)'},
      {'1_engine_models_it': 'YES. A football-only scoring centre (own-offence blend) with empirical total and margin residuals.',
       '2_code_or_discussed': 'sim/football_points.py (centre; no opponent adjustment by owner instruction); game.py:300-316 (draws).',
       '3_optimizer_consumes': 'YES, through the worlds.',
       '4_verifiable': 'YES over many games (win-probability calibration). One game is one draw.',
       '5_disagreed_with_them': 'P(DAL by 20+) agrees (21.8% vs 23%). P(TB win) is lower (19.2% vs 24-26%). The DAL defence\'s EPA rank of 32 is not in our centre.',
       '6_would_flag_portfolio_risk': 'Modestly. A higher TB-win probability shifts optimal captains toward TB.',
       '7_research_needed': 'Opponent-adjusted football centre as a pre-registered shadow arm (currently NOT_MODELLED by owner instruction item 9, so this needs an owner ruling).'},
      'TB won 24-16. The exact scoreline region occurred in 2.2% of our worlds; one draw.')

doc = {'ARTIFACT': 'TB_DAL_PRELOCK_STRATEGY_COMPARISON',
       'SEPARATION': 'All our_frozen_pregame_numbers come from the OFFICIAL worlds and R1 candidates, written before kickoff. Ownership forecasts are the sealed prelock files. ACTUAL_* fields and HINDSIGHT_ONLY are postgame answer key. Their numbers are their model outputs and are not inputs.',
       'MC_precision': 'SE of a 2,000-world probability near 0.25 is about 0.010; near 0.05 about 0.005.',
       'world_accounting_caveat': 'D-05: in 65-68 worlds per club, points < 6 x offensive TDs from the stat lines; points/TD correlation 0.87. TD-based and points-based probabilities come from partly inconsistent accounting. The event-consistent repair arm (commit bd895bb3) is postgame SHADOW work and was not used.',
       'topics': T}
json.dump(doc, open(S + 'out/TB_DAL_PRELOCK_STRATEGY_COMPARISON.json', 'w'), indent=1)

md = ['# TB@DAL prelock strategy comparison: our frozen engine against the Stokastic presenters', '',
      '**Sources of the numbers.** Our numbers come from the OFFICIAL frozen worlds:',
      '- 2,000 worlds, seed 20261005, written 23:08Z, before the 00:15Z kickoff;',
      '- the R1 candidate pool that was actually entered (5,387 lineups, each scored in every world);',
      '- the sealed prelock ownership forecasts.', '',
      '**Their numbers are their model outputs.** Nothing of theirs is an input here.', '',
      '**HINDSIGHT** lines use the result. They are not evidence for either process.', '',
      '**Monte Carlo precision.** The standard error is about ±1.0 pp at p = 0.25 and about ±0.5 pp at p = 0.05.', '',
      '**Accounting caveat (D-05).**',
      '- In 65-68 worlds per club, club points are below 6 x the offensive TDs on the stat lines.',
      '- So TD-based and points-based probabilities come from partly inconsistent accounting.',
      '- The event-consistent repair arm is postgame SHADOW work and is not used here.', '',
      '## Headline numbers, ours against theirs (all pregame)', '',
      '| Quantity | Ours (frozen) | Theirs (their model) | Substantial disagreement? |', '|---|---|---|---|',
      f"| Lamb P(anytime TD) | {pl['CeeDee Lamb']['P_anytime_TD']:.3f} | ~0.51 | no |",
      f"| Pickens P(anytime TD) | {pl['George Pickens']['P_anytime_TD']:.3f} | ~0.44 (ambiguous) | **yes (-12 pp)** |",
      f"| Irving P(TD) / P(2+ TD) | {pl['Bucky Irving']['P_anytime_TD']:.3f} / {pl['Bucky Irving']['P_2plus_TD']:.3f} | 0.41-0.43 / ~0.10 | no |",
      f"| P(Javonte TD and Goodson TD) | {F['joint']['P_Javonte_TD_and_Goodson_TD']:.3f} (independence product {F['joint']['product_if_independent']:.3f}) | 0.13-0.139 | no |",
      f"| P(DAL wins by 20+) | {g['P_DAL_by_20_plus']:.3f} | 0.23 | no |",
      f"| P(TB wins) | {g['P_TB_win']:.3f} | 0.24-0.26 | **yes (-5 to -7 pp)** |",
      f"| P(Daniels 50+ rush yds) | {pl['Jalon Daniels']['P_rush_yds_50plus']:.3f} | 0.38 | **yes (D-03)** |",
      f"| P(Daniels < 15 pass att) | {pl['Jalon Daniels']['P_pass_att_lt15']:.4f} | 0.019 | both tiny |",
      f"| P(Egbuka 100+ rec yds) | {pl['Emeka Egbuka']['P_100plus_rec_yds']:.3f} (0.016 if Daniels <= 27 att) | 0.035 | **yes (D-02 volume centre)** |",
      '| P(Goodson first TD) | not computable (no event order) | 0.041 | n/a |',
      f"| Daniels DK mean | {pl['Jalon Daniels']['mean_dk']:.2f} | 18.4 | yes |",
      '', '## Optimal frequency in our worlds (R1 pool) against sealed ownership forecasts, 150-max', '',
      '**Column definitions.**',
      '- **opt** = the share of worlds in which the player is in the best lineup of the R1 pool.',
      '- **BLEND** = the shadow ownership forecast.',
      '- **FCprop** = the no-fit baseline: share proportional to the FC FLEX projection. It was computed postgame, but only from the pregame FC file.',
      '- **ACTUAL** = DK %Drafted, the answer key.', '',
      '**Reproduction check.** The opt CPT column reproduces `OFFICIAL_ELIGIBILITY_FIX_R1/SHOWDOWN_TB_DAL_CPT_BOARD.csv` p_world_optimal_captain to 4 dp.', '',
      '| Player | opt CPT | our CPT exp | BLEND CPT | FCprop CPT | ACTUAL CPT | opt FLEX | our rostered | BLEND FLEX | FCprop FLEX | ACTUAL FLEX |', '|---|---|---|---|---|---|---|---|---|---|---|']
for p, r in W.items():
    md.append(f"| {p} | {r['opt_CPT_pct']} | {r['our_CPT_exposure_pct_R1']} | {r['blend_CPT_pct']} | {r['fcprop_CPT_pct']} | {r['ACTUAL_field_CPT_pct']} | {r['opt_FLEX_pct']} | {r['our_rostered_exposure_pct_R1']} | {r['blend_FLEX_pct']} | {r['fcprop_FLEX_pct']} | {r['ACTUAL_field_FLEX_pct']} |")
md += ['', '**Notes on the table.**',
       '- "our rostered" is the share of lineups rostering the player in any slot, CPT included.',
       '- DK FLEX % counts the FLEX slot only.',
       '- SC-OWN-2 and FC_ONLY columns are in `SUPPORT_OWNERSHIP_FORECAST_VS_ACTUAL.json`.', '',
       '## Topics and the owner\'s seven questions', '']
QN = {'1_engine_models_it': '1. Does our engine model it?', '2_code_or_discussed': '2. In code or only discussed?', '3_optimizer_consumes': '3. Does the final optimizer consume it?',
      '4_verifiable': '4. Can its output be verified?', '5_disagreed_with_them': '5. Did our frozen numbers substantially disagree with theirs?',
      '6_would_flag_portfolio_risk': '6. Would it have identified a meaningful portfolio risk?', '7_research_needed': '7. Research / implementation needed'}
for t in T:
    md += [f"### {t['topic']}", '', '**Our frozen numbers:** `' + json.dumps(t['our_frozen_pregame_numbers'])[:900] + '`', '',
           '**Theirs:** ' + json.dumps(t['their_stated_numbers']), '']
    for k, v in t['seven_questions'].items():
        md.append(f'- **{QN[k]}** {v}')
    md += ['', f"*HINDSIGHT ONLY:* {t['HINDSIGHT_ONLY']}", '']
open(S + 'out/TB_DAL_PRELOCK_STRATEGY_COMPARISON.md', 'w').write('\n'.join(md) + '\n')
print('ok', len(T))
