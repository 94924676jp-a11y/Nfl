# TB@DAL prelock strategy comparison: our frozen engine against the Stokastic presenters

**Sources of the numbers.** Our numbers come from the OFFICIAL frozen worlds:
- 2,000 worlds, seed 20261005, written 23:08Z, before the 00:15Z kickoff;
- the R1 candidate pool that was actually entered (5,387 lineups, each scored in every world);
- the sealed prelock ownership forecasts.

**Their numbers are their model outputs.** Nothing of theirs is an input here.

**HINDSIGHT** lines use the result. They are not evidence for either process.

**Monte Carlo precision.** The standard error is about ±1.0 pp at p = 0.25 and about ±0.5 pp at p = 0.05.

**Accounting caveat (D-05).**
- In 65-68 worlds per club, club points are below 6 x the offensive TDs on the stat lines.
- So TD-based and points-based probabilities come from partly inconsistent accounting.
- The event-consistent repair arm is postgame SHADOW work and is not used here.

## Headline numbers, ours against theirs (all pregame)

| Quantity | Ours (frozen) | Theirs (their model) | Substantial disagreement? |
|---|---|---|---|
| Lamb P(anytime TD) | 0.534 | ~0.51 | no |
| Pickens P(anytime TD) | 0.322 | ~0.44 (ambiguous) | **yes (-12 pp)** |
| Irving P(TD) / P(2+ TD) | 0.427 / 0.116 | 0.41-0.43 / ~0.10 | no |
| P(Javonte TD and Goodson TD) | 0.150 (independence product 0.151) | 0.13-0.139 | no |
| P(DAL wins by 20+) | 0.218 | 0.23 | no |
| P(TB wins) | 0.192 | 0.24-0.26 | **yes (-5 to -7 pp)** |
| P(Daniels 50+ rush yds) | 0.102 | 0.38 | **yes (D-03)** |
| P(Daniels < 15 pass att) | 0.0025 | 0.019 | both tiny |
| P(Egbuka 100+ rec yds) | 0.091 (0.016 if Daniels <= 27 att) | 0.035 | **yes (D-02 volume centre)** |
| P(Goodson first TD) | not computable (no event order) | 0.041 | n/a |
| Daniels DK mean | 13.99 | 18.4 | yes |

## Optimal frequency in our worlds (R1 pool) against sealed ownership forecasts, 150-max

**Column definitions.**
- **opt** = the share of worlds in which the player is in the best lineup of the R1 pool.
- **BLEND** = the shadow ownership forecast.
- **FCprop** = the no-fit baseline: share proportional to the FC FLEX projection. It was computed postgame, but only from the pregame FC file.
- **ACTUAL** = DK %Drafted, the answer key.

**Reproduction check.** The opt CPT column reproduces `OFFICIAL_ELIGIBILITY_FIX_R1/SHOWDOWN_TB_DAL_CPT_BOARD.csv` p_world_optimal_captain to 4 dp.

| Player | opt CPT | our CPT exp | BLEND CPT | FCprop CPT | ACTUAL CPT | opt FLEX | our rostered | BLEND FLEX | FCprop FLEX | ACTUAL FLEX |
|---|---|---|---|---|---|---|---|---|---|---|
| CeeDee Lamb | 36.8 | 22.0 | 37.3 | 11.5 | 17.08 | 43.5 | 50.0 | 47.2 | 57.4 | 42.49 |
| George Pickens | 2.4 | 4.0 | 3.9 | 9.3 | 12.04 | 17.6 | 30.0 | 30.0 | 46.7 | 28.28 |
| Dak Prescott | 13.5 | 12.0 | 33.7 | 11.7 | 16.38 | 60.6 | 50.0 | 50.1 | 58.7 | 61.42 |
| Javonte Williams | 11.5 | 21.3 | 9.9 | 9.7 | 15.07 | 34.9 | 50.0 | 41.7 | 48.7 | 36.97 |
| Jalon Daniels | 3.1 | 7.3 | 2.1 | 6.3 | 10.18 | 31.7 | 48.7 | 27.0 | 31.4 | 45.34 |
| Bucky Irving | 11.5 | 7.3 | 2.9 | 5.4 | 5.48 | 38.2 | 50.0 | 28.7 | 26.8 | 23.95 |
| Tyler Goodson | 0.7 | 0 | 0.0 | 0.6 | 0.22 | 18.6 | 14.0 | 4.5 | 2.9 | 8.79 |
| Ryan Flournoy | 0.7 | 0.7 | 0.5 | 4.8 | 3.52 | 14.8 | 14.0 | 38.7 | 24.2 | 29.06 |
| Brandon Aubrey | 2.2 | 2.7 | 3.3 | 5.8 | 1.88 | 27.8 | 42.7 | 47.2 | 29.2 | 30.34 |
| Cowboys | 0.1 | 0 | 0.0 | 1.8 | 2.03 | 4.3 | 4.7 | 0.0 | 9.1 | 16.91 |
| Buccaneers | 1.0 | 5.3 | 0.0 | 1.6 | 0.39 | 17.7 | 22.7 | 2.3 | 7.9 | 7.56 |
| Emeka Egbuka | 3.2 | 5.3 | 0.3 | 4.0 | 3.26 | 23.3 | 44.0 | 6.5 | 19.8 | 14.38 |
| Cade Otton | 7.5 | 3.3 | 3.7 | 3.8 | 2.28 | 44.1 | 46.7 | 57.5 | 18.9 | 27.47 |
| Chris Godwin Jr. | 1.7 | 3.3 | 0.1 | 3.6 | 2.5 | 13.4 | 32.0 | 2.7 | 17.8 | 14.97 |
| Jake Ferguson | 2.2 | 2.7 | 1.5 | 4.9 | 4.28 | 24.9 | 33.3 | 21.7 | 24.5 | 19.87 |
| Kenny Gainwell | 0.1 | 0 | 0.4 | 4.6 | 0.97 | 8.1 | 8.7 | 23.8 | 23.2 | 16.88 |
| Ted Hurst III | 0.2 | 0.7 | 0.1 | 2.9 | 0.86 | 10.9 | 10.0 | 18.1 | 14.5 | 18.48 |
| Tez Johnson | 0.0 | 0 | 0.0 | 1.9 | 0.28 | 1.6 | 0 | 1.3 | 9.7 | 11.58 |
| Chase McLaughlin | 0.9 | 0 | 0.3 | 3.4 | 0.55 | 26.2 | 25.3 | 15.3 | 16.9 | 17.74 |
| Payne Durham | 0.2 | 0 | 0.0 | 0.0 | 0.01 | 18.9 | 14.0 | 16.5 | 0.0 | 1.3 |
| KaVontae Turpin | 0.1 | 0 | 0.0 | 2.4 | 0.14 | 3.6 | 1.3 | 19.3 | 11.8 | 7.91 |
| Sean Tucker | 0.1 | 0.7 | 0 | 0.0 | 0.16 | 3.3 | 0.7 | 0 | 0.0 | 6.16 |
| Brevyn Spann-Ford | 0.1 | 1.3 | 0 | 0.0 | 0.05 | 8.6 | 7.3 | 0 | 0.0 | 4.03 |

**Notes on the table.**
- "our rostered" is the share of lineups rostering the player in any slot, CPT included.
- DK FLEX % counts the FLEX slot only.
- SC-OWN-2 and FC_ONLY columns are in `SUPPORT_OWNERSHIP_FORECAST_VS_ACTUAL.json`.

## Topics and the owner's seven questions

### Lamb vs Pickens

**Our frozen numbers:** `{"Lamb": {"mean_dk": 28.28, "P_anytime_TD": 0.534, "P_2plus_TD": 0.182, "mean_targets": 12.14, "P_dk_lt5": 0.0045, "p10_dk": 14.09, "p90_dk": 43.15}, "Pickens": {"mean_dk": 11.7, "P_anytime_TD": 0.322, "P_2plus_TD": 0.055, "mean_targets": 6.31, "P_dk_lt5": 0.1515, "p10_dk": 3.79, "p90_dk": 21.51}, "projected_target_share": {"Lamb": 0.314, "Pickens": 0.163, "source": "TB_DAL_DEFECT_REGISTER D-04"}, "efficiency_factor_Lamb_rec_yards": 1.4095, "prelock_usage_fact": "targets wk1-4 Lamb 8/9/8/21, Pickens 6/8/11/3; weeks 1-3 equal (25 each)"}`

**Theirs:** {"P_TD": "Lamb ~51%, Pickens ~44% (ambiguous)", "leverage": "Pickens positive CPT and FLEX; Lamb most negative"}

- **1. Does our engine model it?** YES for volume, efficiency and TD from opportunity. NO between-game share volatility (D-04). NO credible dud tail: P(Lamb <5 DK) 0.45% in our worlds vs 6.6% [4.0, 9.5] empirical for 20+ ppg WRs (D-01).
- **2. In code or only discussed?** In code: target share pooled by target count, proj_v1.py:277-303 (_combine) and :306-345 (current_season_shares); per-world efficiency factor, classic_slate_run.py:85 (efficiency_worlds); share dispersion is a Dirichlet-multinomial or logistic-normal, game.py:382-408.
- **3. Does the final optimizer consume it?** YES. The draws feed the hit-proxy objective. Lamb was the best captain in 36.8% of worlds and sat at the 50% player cap in every contest.
- **4. Can its output be verified?** YES. P(TD) and dud rates can be graded by tail PIT across slates; one game cannot grade them.
- **5. Did our frozen numbers substantially disagree with theirs?** YES on Pickens (P(TD) 32% vs ~44%) and on leverage sign. Agreed on Lamb P(TD) (53% vs ~51%). Our mean gap (28.3 vs 11.7 DK) was far wider than FC's (22.1 vs 18.0).
- **6. Would it have identified a meaningful portfolio risk?** NOT AS BUILT. The worlds understated Lamb's bad-game tail about 10x, so concentration risk at the cap was invisible. A calibrated tail (D-01) plus share volatility (D-04) is what would have exposed it. Their argument rested on the equal weeks 1-3 targets, a fact our pooled share gave one game's worth of weight against.
- **7. Research / implementation needed** D-01 star-dud tail and D-04 share volatility; decompose our-vs-FC gap into volume and efficiency for WR1s (D-11); acceptance by tail PIT on held-out 2025 replay.

*HINDSIGHT ONLY:* Lamb 2.9 DK (5 targets, in-game injury, returned Q4); Pickens 31.0 DK (13 targets, 1 TD). One outcome. It is not evidence that the equal-share reading was right.

### Captain ownership and ceiling

**Our frozen numbers:** `{"optimal_captain_share": {"CeeDee Lamb": {"opt_CPT": 0.368, "cpt_salary": 17700}, "Dak Prescott": {"opt_CPT": 0.135, "cpt_salary": 15600}, "Javonte Williams": {"opt_CPT": 0.115, "cpt_salary": 16200}, "Bucky Irving": {"opt_CPT": 0.1145, "cpt_salary": 12600}, "Cade Otton": {"opt_CPT": 0.0755, "cpt_salary": 6600}, "Jalon Daniels": {"opt_CPT": 0.031, "cpt_salary": 12900}, "Emeka Egbuka": {"opt_CPT": 0.032, "cpt_salary": 12300}, "George Pickens": {"opt_CPT": 0.024, "cpt_salary": 14100}}, "cpt_p95_from_CPT_BOARD": {"Lamb": 72.41, "Dak": 54.56, "Javonte": 50.64, "Irving": 45.9, "Daniels": 38.19, "Pickens": 37.99, "Egbuka": 37.03, "Otton": 35.07}, "share_worlds_optimal_cpt_is_top_scorer": 0.754, "P_DST_optimal_CPT": 0.0115, "P_TB_pass_catcher_optimal_CPT": 0.129}`

**Theirs:** {"CPT_ownership": "Pickens ~7-8% (A), 12-20% for Dak/Pickens/Javonte/Lamb (B), Pickens > Lamb (B)", "Daniels_CPT": "~8% in their sims"}

- **1. Does our engine model it?** Ceiling: YES (per-world CPT = 1.5 x FLEX). Captain ownership: SHADOW ONLY (BLEND, FC_ONLY, SC-OWN-2), never in selection.
- **2. In code or only discussed?** Ceiling in code (DRAWS CPT_RULE; CPT_BOARD). Ownership in code as shadow: field/showdown_shadow_field.py, research/ownership/sc_own_rotation_2.py; selection never reads it (showdown_portfolio.py:18-29; showdown_next_slate.py:395-462).
- **3. Does the final optimizer consume it?** Ceiling YES (through the worlds). Ownership NO.
- **4. Can its output be verified?** YES. Sealed CPT forecasts are graded against DK %Drafted: CPT MAE BLEND 1.83, FC_ONLY 1.56, SC-OWN-2 1.80, no-fit FC-proportional 1.09 (Spearman 0.93).
- **5. Did our frozen numbers substantially disagree with theirs?** YES. Our BLEND forecast put Lamb 37.3 and Dak 33.7 (actual 17.1 and 16.4), about 2x too high on chalk captains. Their 12-20% band was correct. Our FC-proportional baseline (computed postgame from the pregame FC file) put both at about 11.6, too low.
- **6. Would it have identified a meaningful portfolio risk?** Only if ownership entered selection. Our 22% Lamb CPT against a true 17% field is not a large overweight. The risk was correlated chalk (Lamb plus Dak) and duplication, not captain ownership by itself.
- **7. Research / implementation needed** T1 ownership_v2 must beat the FC-proportional baseline on CPT MAE, STAR-bucket bias and log score leave-one-slate-out, then on 3 of 4 prospective slates. STAR-bucket CPT MAE is 9-11 pp for every model.

*HINDSIGHT ONLY:* Top-1% captains were Irving 49% and Pickens 49%; our CPT exposure was Irving 7.3%, Pickens 4.0%.

### Daniels rushing

**Our frozen numbers:** `{"mean_carries": 3.33, "mean_rush_yds": 19.4, "P_rush_yds_50plus": 0.1015, "P_rush_yds_45_5_plus": 0.1255, "rush_yds_p90": 50.5, "mean_pass_att": 34.61, "P_pass_att_lt15": 0.0025, "mean_dk": 13.99}`

**Theirs:** {"P_50plus_rush": 0.38, "P_lt15_att": 0.019, "projection": 18.4}

- **1. Does our engine model it?** WEAKLY. QB rushing comes from a generic cohort prior pooled with relief appearances (D-03), and team pass volume has no QB argument (D-02).
- **2. In code or only discussed?** In code: proj_v1.py:1295-1298 (hierarchical/cohort prior), :277-303 (_combine), :167 (team_volume, QB-independent). Root cause documented in docs/QB_REGIME_ROOT_CAUSE_2026-10-08.md section 1 and QB_REGIME_AUDIT_PRECOMPUTE_TBQB_DANIELS_R10.json. A QB-conditioned model is a separate active workstream, NOT_VALIDATED.
- **3. Does the final optimizer consume it?** YES, as projected (3.3 carries), so too low.
- **4. Can its output be verified?** YES. Rush-yard PIT per QB start, and scramble rate under starter vs relief, graded across starts.
- **5. Did our frozen numbers substantially disagree with theirs?** YES, materially: 10.2% vs 38% for 50+ rush yds. The pregame evidence (8 carries, 6 scrambles, 55 yds in his one start; 27 attempts) pointed their way, and our own prelock audit flagged it.
- **6. Would it have identified a meaningful portfolio risk?** YES, if fixed. Fewer TB pass attempts and more Daniels rushing lowers TB receivers (Egbuka, Otton, Godwin were 44%, 47% and 32% rostered by us) and raises Daniels' floor.
- **7. Research / implementation needed** Partially pooled QB-start rushing model (repair program section G steps 2-3); pass-rate conditioning on QB identity; acceptance on held-out QB changes 2021-2025.

*HINDSIGHT ONLY:* Daniels: 7 carries, 23 yds, 25 attempts (beat 11% of our attempt simulations).

### Irving opportunity and receiving role

**Our frozen numbers:** `{"mean_targets": 4.01, "P_0_targets": 0.0265, "mean_carries": 16.35, "P_anytime_TD": 0.427, "P_2plus_TD": 0.1155, "mean_dk": 16.5, "opt_FLEX": 0.382, "opt_CPT": 0.1145}`

**Theirs:** {"P_TD": "~41-43%", "P_2TD": "~10%", "hypothesis": "Daniels runs instead of checking down, so Irving gets fewer targets"}

- **1. Does our engine model it?** Rushing role YES. Receiving role is pooled across QBs. No QB-dependency of RB target share.
- **2. In code or only discussed?** Only discussed (D-02; QB_REGIME audit). No code path conditions RB targets on QB identity.
- **3. Does the final optimizer consume it?** YES (4.0 targets baked into the draws).
- **4. Can its output be verified?** Across many QB changes only. Week 4 (0 targets) is n = 1.
- **5. Did our frozen numbers substantially disagree with theirs?** NO on P(TD), which agreed. Their target hypothesis is not reflected in our model.
- **6. Would it have identified a meaningful portfolio risk?** Small. Irving's value in our worlds came from carries; the receiving share was a minor part.
- **7. Research / implementation needed** Historical QB-change panel: RB target share and QB scramble rate before and after starter changes, 2016-2025, clustered by team.

*HINDSIGHT ONLY:* Irving 21 carries / 165 yds, 3 targets, 2 TD, 34.5 DK. The checkdown hypothesis was neither confirmed nor refuted (3 targets).

### Javonte goal-line

**Our frozen numbers:** `{"P_anytime_TD": 0.679, "P_2plus_TD": 0.295, "mean_TD": 1.093, "mean_carries": 15.23, "joint_TD_with_Goodson": {"P_Javonte_TD_and_Goodson_TD": 0.15, "P_Javonte_TD": 0.679, "P_Goodson_TD": 0.222, "product_if_independent": 0.1507, "corr_TD_indicators": -0.004, "corr_carries": -0.04, "corr_dk": -0.034, "n_worlds_both": 300}, "prelock_fact": "13 inside-10 / 11 inside-5 carries wk1-4; 11 of 12 DAL inside-5 carries"}`

**Theirs:** {"P_both_TD": "~13% (A), 13.9% (B)"}

- **1. Does our engine model it?** PARTIALLY. Red-zone (inside 20) intensity is modelled. Goal-line (inside 5) share is computed and discarded. TD allocation within a club uses fixed shares independent of per-world carries.
- **2. In code or only discussed?** gl_carry_share computed at proj_v1.py:338-339 and never consumed (no comb('gl_carry_share')); rz_intensity at proj_v1.py:663-681; TD shares fixed at showdown_draws.py:111; allocation at game.py:481-490.
- **3. Does the final optimizer consume it?** Inside-20 only, via TD shares.
- **4. Can its output be verified?** YES. Rush-TD calibration by goal-line share bucket across 2021-2025 replay.
- **5. Did our frozen numbers substantially disagree with theirs?** NO. Joint 15.0% vs 13-14%. Our backs' TD events are uncorrelated (r = -0.004).
- **6. Would it have identified a meaningful portfolio risk?** Low on this slate. Our Javonte P(TD) of 68% already reflected his role.
- **7. Research / implementation needed** Test whether adding gl_carry_share improves rush-TD log score over rz_intensity alone (pre-registered, LOSO by season). Make TD allocation conditional on per-world carries.

*HINDSIGHT ONLY:* Javonte 1 rush TD (1-yd). Goodson no stats.

### DAL-heavy vs TB-heavy builds

**Our frozen numbers:** `{"optimal_split_TB_DAL": {"1-5": 0.116, "2-4": 0.3115, "3-3": 0.364, "4-2": 0.1905, "5-1": 0.018}, "our_entered_150max_split": {"1-5": 0.073, "2-4": 0.227, "3-3": 0.353, "4-2": 0.293, "5-1": 0.053}, "pregame_BLEND_field_split_forecast": {"1-5": 25.9, "2-4": 42.9, "3-3": 27.0, "4-2": 4.2, "5-1": 0.0}, "P_TB_win": 0.192}`

**Theirs:** {"claim": "TB 4-2 low owned, 5-1 nearly unowned; most-duped lineups DAL-heavy; any TB lean is naturally leveraged"}

- **1. Does our engine model it?** Football side YES (worlds). Field split: SHADOW ONLY (shadow board team_split).
- **2. In code or only discussed?** Structural split computed at showdown_portfolio.py:216-232 (tie-break only). Field split forecast at field/showdown_shadow_board.py.
- **3. Does the final optimizer consume it?** Only as a tie-break (structural duplication index, +1 for a 5-1).
- **4. Can its output be verified?** YES. Actual field split from standings: 1-5 22.0%, 2-4 35.4%, 3-3 29.4%, 4-2 11.5%, 5-1 1.7%.
- **5. Did our frozen numbers substantially disagree with theirs?** NO on direction. Our BLEND forecast also had DAL-heavy chalk, though it under-predicted 4-2 (4.2 vs 11.5).
- **6. Would it have identified a meaningful portfolio risk?** Our entered portfolio was already TB-leaning (34.6% 4-2 or 5-1 vs field 13.2%), as a by-product of world coverage. No leverage was computed.
- **7. Research / implementation needed** Field-split model in T2, with split leverage reported per contest.

*HINDSIGHT ONLY:* Field top 1%: 3-3 58%, 4-2 18%, 2-4 21%.

### Salary utilisation

**Our frozen numbers:** `{"optimal_lineup_salary_band_share": {"48000-49400": 0.412, "<48000": 0.122, "49500-49900": 0.381, "50000": 0.085}, "our_entered": {"mean_salary": 48470, "share_le_48000": 0.187}, "pregame_BLEND_field_salary_left_mean": 401}`

**Theirs:** {"claim": "most-duped lineups sit at or near the cap and \"make sense\""}

- **1. Does our engine model it?** Our worlds YES. Field salary use only as a shadow (salary_left).
- **2. In code or only discussed?** showdown_portfolio.py:216-232 (cap salary +1 in the duplication tie-break); B4 duplication model uses salary-left features (DUPE_SHADOW_B4 theta sal_0 1.72, sal_100-500 1.51 ...).
- **3. Does the final optimizer consume it?** Tie-break only.
- **4. Can its output be verified?** YES. Actual 150-max: 10.3% of entries at $50,000, 41.5% at $49,500-49,900, 9.5% below $48,000; mean $49,142; mean salary left $858 vs BLEND forecast $401.
- **5. Did our frozen numbers substantially disagree with theirs?** NO. Duplication by salary band is verified: 112 to 124 other copies per entry at $49,500-50,000 vs 9.8 below $48,000.
- **6. Would it have identified a meaningful portfolio risk?** YES, if duplication were modelled. Cap-adjacent chalk builds are the most shared.
- **7. Research / implementation needed** Fit salary-left propensity for T2 from other slates (LOSO); report the duplication by salary band of our lineups prelock.

*HINDSIGHT ONLY:* Field top 1%: mean salary $49,457; 3.5% at or below $48,000.

### Low-owned FLEX

**Our frozen numbers:** `{"opt_FLEX_vs_BLEND_forecast": {"Tyler Goodson": [18.6, 4.5], "Buccaneers": [17.7, 2.3], "Emeka Egbuka": [23.3, 6.5], "Chris Godwin Jr.": [13.4, 2.7], "Brevyn Spann-Ford": [8.6, 0], "Payne Durham": [18.9, 16.5], "Sean Tucker": [3.3, 0], "Tez Johnson": [1.6, 1.3]}}`

**Theirs:** {"claim": "Goodson nearly unowned; Flournoy 6th-highest FLEX; Egbuka ~15%"}

- **1. Does our engine model it?** Football side YES. Ownership shadow only.
- **2. In code or only discussed?** SC-OWN-ROTATION-2 (research/ownership/sc_own_rotation_2.py) targets exactly the cheap-rotation bucket. Prospective slate 1 of 4: FAILS (cheap |bias| 5.74 vs 2.59; total FLEX MAE +2.55 pp). Its candidate also forecast Payne Durham FLEX at 94.5% against an actual 1.3%.
- **3. Does the final optimizer consume it?** NO.
- **4. Can its output be verified?** YES. Cheap-bucket FLEX MAE and bias per slate.
- **5. Did our frozen numbers substantially disagree with theirs?** Goodson: they said about 10% (field), our BLEND 4.5%, actual 8.8%. Flournoy: our BLEND 38.7%, actual 29.1%; their rank was right.
- **6. Would it have identified a meaningful portfolio risk?** Limited. Low-owned FLEX matters for duplication and leverage, which we do not model.
- **7. Research / implementation needed** Fix the SC-OWN-2 candidate failure mode (the punt-TE explosion); keep FC-proportional as the incumbent.

*HINDSIGHT ONLY:* Tez Johnson (11.6% owned, 7.4 DK) was in the hindsight optimum; our worlds had him optimal in 1.6%.

### Leverage

**Our frozen numbers:** `{"definition_used": "pregame leverage = our optimal frequency minus our sealed ownership forecast (BLEND) and minus the FC-proportional baseline; exposure leverage = our exposure minus forecast", "CPT_opt_minus_BLEND": {"CeeDee Lamb": -0.5, "Dak Prescott": -20.2, "Javonte Williams": 1.6, "George Pickens": -1.5, "Bucky Irving": 8.6, "Jalon Daniels": 1.0, "Cade Otton": 3.8}, "CPT_opt_minus_FCprop": {"CeeDee Lamb": 25.3, "Dak Prescott": 1.8, "Javonte Williams": 1.8, "George Pickens": -6.9, "Bucky Irving": 6.1, "Jalon Daniels": -3.2, "Cade Otton": 3.7}}`

**Theirs:** {"claim": "CPT: Dak most positive, Javonte and Pickens positive, Lamb most negative; FLEX: Goodson, Dak, DAL DST, Javonte, Gainwell, Daniels, Flournoy positive; Lamb, Aubrey, Irving negative"}

- **1. Does our engine model it?** NO. Computed on shadow boards only (SHADOW_LEVERAGE_*.csv), against the OFFICIAL exposures, never in selection.
- **2. In code or only discussed?** field/showdown_shadow_board.py (leverage = our exposure - shadow ownership). No optimal-frequency-vs-ownership leverage exists in code; the numbers here were computed for this report.
- **3. Does the final optimizer consume it?** NO.
- **4. Can its output be verified?** Partly. Ownership forecasts are gradeable. Whether leverage improves payout needs payout tables and many contests.
- **5. Did our frozen numbers substantially disagree with theirs?** YES. Against FC-proportional, Lamb was our MOST positive captain (+25.3) and Pickens negative (-6.9), the reverse of theirs. Against BLEND, Dak was very negative (-20.2) because BLEND over-forecast Dak CPT.
- **6. Would it have identified a meaningful portfolio risk?** Depends on the ownership model, which on this slate was miscalibrated about 2x on chalk captains. Leverage built on a bad ownership forecast is noise.
- **7. Research / implementation needed** Define leverage with uncertainty (forecast intervals); test only after T1 beats the baseline.

*HINDSIGHT ONLY:* Against actual CPT ownership: Lamb +19.7, Pickens -9.6, Dak -2.9.

### Winning-lineup scenarios

**Our frozen numbers:** `{"game_script_board_R1": "TB leads 19.2%; DAL blowout >=14 37.4%; one-score 34.6%; grinder 25.1%; shootout 25.0%; TB pass-heavy comeback 20.1%", "P_DAL_le16_and_TB_ge24": 0.022, "candidate_pool_proxy_coverage_150max": "about 0.99 in every script"}`

**Theirs:** {"claim": "many winning builds DAL 5-1/4-2 (their sims); TB receiver CPT only if TDs scarce"}

- **1. Does our engine model it?** YES. Scripts are labels over the same worlds (GAME_SCRIPT_BOARD).
- **2. In code or only discussed?** showdown_portfolio.py game-script board and audit (by_best_game_script).
- **3. Does the final optimizer consume it?** Implicitly. Coverage of worlds covers scripts.
- **4. Can its output be verified?** Script frequencies are gradeable over many games. Winning composition needs the field.
- **5. Did our frozen numbers substantially disagree with theirs?** Mild. Our TB-win share (19%) was lower than theirs (24-26%).
- **6. Would it have identified a meaningful portfolio risk?** NO. A lineup that wins a script in our worlds may be shared by hundreds of entries, and the objective cannot see that.
- **7. Research / implementation needed** T4: rank in the simulated field per world.

*HINDSIGHT ONLY:* TB 24-16; the hindsight-best lineup averaged 77.4 in our worlds (p95 113.0) and was in no candidate pool.

### Duplication and uniqueness

**Our frozen numbers:** `{"B4_sealed_prediction_our_lineups": {"median_copies": 1.3, "spearman_vs_actual": 0.708, "sum_actual_over_pred": 0.16}, "shadow_board_exact": {"median": 0.0, "spearman": 0.254}}`

**Theirs:** {"claim": "most-duped lineup ~79 dupes (Dak, Aubrey, Lamb, DAL DST, Daniels, Flournoy); build unique lineups around popular players"}

- **1. Does our engine model it?** SHADOW ONLY (B4 maxent, B3S, shadow-board exact and product).
- **2. In code or only discussed?** field/showdown_dupe_shadow.py (B4), field/showdown_dupe_research.py, field/showdown_shadow_board.py.
- **3. Does the final optimizer consume it?** NO (D-06). Only the structural tie-break.
- **4. Can its output be verified?** YES. Actual copies per lineup from standings.
- **5. Did our frozen numbers substantially disagree with theirs?** Their named lineup had 295 actual copies (Dak CPT, $50,000) in the 150-max. Our B4 sealed artifact priced only our own lineups, so we have no pregame number for it.
- **6. Would it have identified a meaningful portfolio risk?** YES, if it were calibrated. Our lineups averaged 40 field copies (max 455), and B4 ranked them well (Spearman 0.71). Its level was wrong in both directions: median under-predicted about 9x, a few heavy-chalk lineups over-predicted by orders of magnitude.
- **7. Research / implementation needed** FIELD_AND_DUPLICATION_MODEL_SPEC (this package): recalibrate the level and tail; price any lineup, not only ours.

*HINDSIGHT ONLY:* Winning lineup shared by 18 entries (150-max).

### Game-script probabilities

**Our frozen numbers:** `{"P_DAL_win": 0.808, "P_TB_win": 0.192, "P_DAL_by_20_plus": 0.218, "P_DAL_by_10_plus": 0.5055, "mean_margin_DAL_minus_TB": 10.37, "mean_total": 49.86, "mean_DAL_pts": 30.12, "mean_TB_pts": 19.74}`

**Theirs:** {"P_DAL_by_20plus": 0.23, "P_TB_win": "0.24 (B), 0.26 (A)"}

- **1. Does our engine model it?** YES. A football-only scoring centre (own-offence blend) with empirical total and margin residuals.
- **2. In code or only discussed?** sim/football_points.py (centre; no opponent adjustment by owner instruction); game.py:300-316 (draws).
- **3. Does the final optimizer consume it?** YES, through the worlds.
- **4. Can its output be verified?** YES over many games (win-probability calibration). One game is one draw.
- **5. Did our frozen numbers substantially disagree with theirs?** P(DAL by 20+) agrees (21.8% vs 23%). P(TB win) is lower (19.2% vs 24-26%). The DAL defence's EPA rank of 32 is not in our centre.
- **6. Would it have identified a meaningful portfolio risk?** Modestly. A higher TB-win probability shifts optimal captains toward TB.
- **7. Research / implementation needed** Opponent-adjusted football centre as a pre-registered shadow arm (currently NOT_MODELLED by owner instruction item 9, so this needs an owner ruling).

*HINDSIGHT ONLY:* TB won 24-16. The exact scoreline region occurred in 2.2% of our worlds; one draw.

