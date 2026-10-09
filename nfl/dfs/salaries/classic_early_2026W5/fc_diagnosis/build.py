import sys, json, pathlib
sys.path.insert(0, '/home/user/nfl')
from load import *
from nfl.tools import classic_week_research as C
import pandas as pd
stw = pd.read_csv(C._load(pathlib.Path('/home/user/nfl/nfl/dfs/salaries/raw/classic_early_2026W5'),
                          'NFLVERSE_STATS_PLAYER_WEEK_2026')[0], low_memory=False)
rs_s = json.load(open(RUN + 'scenario_reported_outs/ROLE_STATE.json'))
I = idx(inc['rows'])
rbx = {(norm(r['player']), r['team']): r for r in rb}

def obs26(gsis):
    s = stw[(stw.player_id == gsis) & (stw.season == 2026)].sort_values('week')
    n = len(s)
    if not n: return {'games_played': 0}
    f = lambda c: float(s[c].fillna(0).sum()) if c in s.columns else 0.0
    dk = [C.dk_points(r.to_dict()) for _, r in s.iterrows()]
    return {'games_played': n, 'weeks': [int(w) for w in s.week],
            'dk_by_week': dk, 'dk_avg': round(sum(dk) / n, 2),
            'targets_pg': round(f('targets') / n, 2), 'carries_pg': round(f('carries') / n, 2),
            'pass_att_pg': round(f('attempts') / n, 2),
            'td_pg': round((f('rushing_tds') + f('receiving_tds')) / n, 2),
            'pass_td_pg': round(f('passing_tds') / n, 2)}

C_ = {}  # classification: player -> (primary, secondaries, evidence_line, defect, contradicted, note)
C_["JaMarr Chase"] = ("FC_SPECIFIC", ["ROLE_EVIDENCE_DEFECT", "AVAILABILITY_ASSUMPTION", "VOLUME_OR_EFFICIENCY_MODEL"],
  "2026 DK avg 15.05 (W1-3 healthy 18.17, W4 concussion exit 20% snaps/3 tgts); ours 14.81 (if-plays 16.48 x p_plays 0.86); FC 23.47 = full-health WR1; in concussion protocol, 'needs a full practice to clear' [CONFIRMED]",
  True, True,
  "W5-G13 present and contradicts captured chart: Chase chart WR1, Higgins chart WR2, both supplied rank 1 (min(usage,chart)); id 00-0036410 < 00-0036900 gives Higgins position rank 1, Chase DEPTH_RANK_2 -> SECONDARY ceiling, prior discounted to PLAYER_OWN_OFF_ROLE, allocation rank 2 -> p_plays 0.86 (rank-2 base rate, not a concussion model). TIE-1 measured effect only +0.09 (one-ALPHA rule then picks Higgins by observed share; allocation rank stays 2). Pooled 4-week share 0.18 includes the W4 injury exit (W5-G8). Largest piece of the gap is FC pricing ~5.3 above his healthy 2026 average while he is in protocol. Engine practice line lags (DNP Wed) vs board (Limited Thu), W5-G14.")
C_["Chris Olave"] = ("FC_SPECIFIC", ["AVAILABILITY_ASSUMPTION"],
  "2026: 4 gp, 12.0 tgt/g, DK avg 24.77; ours 11.75 tgt, 23.49 (p_plays 1.0); FC 18.17; new foot injury, limited Thu [CONFIRMED] not consumed",
  False, False,
  "Our number tracks his 2026 volume and production; FC discounts ~6.6 below his average, plausibly for the new foot injury, which we do not consume (W5-G4, no designation yet). Engine state still carries Wednesday DNP line (W5-G14).")
C_["Kyle Monangai"] = ("ROLE_JUDGEMENT", ["AVAILABILITY_ASSUMPTION", "VOLUME_OR_EFFICIENCY_MODEL"],
  "chart RB2, depth_rank 2 -> DEPTH_RANK_2 ceiling SECONDARY (observed PRIMARY, rush share 0.377; W4 30 car vs Swift 15); p_plays 0.635 = RB rank-2 base rate though 4/4 gp; cond. 11.75 car vs 15.0/g; ours 7.63, FC 13.94, 2026 avg 16.32",
  False, False,
  "Role call: chart RB2 caps him SECONDARY and the rank-2 appearance base rate removes 3.3 DK, while 2026 usage (and Swift's W4 fumble benching [CONFIRMED]) argue a larger share. Cuts the other way: turf toe, DNP Wed+Thu, 'Week 5 in doubt' [CONFIRMED], not consumed. CHI QB identity (Williams vs Bagent) not consumed; scenario moves him only +0.31 (W5-G1).")
C_["Jaylen Warren"] = ("VOLUME_OR_EFFICIENCY_MODEL", ["ROLE_JUDGEMENT"],
  "volume matches 2026 (13.3 car/4.9 tgt vs 13.75/5.0 per g) but TD expectation 0.63/g (rush 0.42 + rec 0.20; PIT rush TD pool scale 1.69) vs 0 TDs in 2026; ours 18.38 vs 2026 avg 15.05, FC 13.28",
  False, False,
  "Excess over his own production is touchdowns: the PIT rush pool scale of 1.69 says measured rates and club volume disagree, and Warren absorbs it. Secondary role question: pooled W1-4 carry share 0.64 includes Dowdle-absent W3-4 (0.74/0.895); with Dowdle W1-2 it was 0.48. Dowdle is now limited (returning). Net PIT RB pair: ours 24.75 vs FC 26.07, so the split is disputed, not the total.")
C_["Tyson Bagent"] = ("AVAILABILITY_ASSUMPTION", ["VOLUME_OR_EFFICIENCY_MODEL"],
  "engine starts Caleb Williams (captured chart QB1, no designation); nflverse schedule capture lists Bagent; [CONFIRMED] Sun-Times 2026-10-05: Williams (Grade 2 hamstring) out, Bagent starts; Bagent p_plays 0.138 -> 0.07; scenario 19.03",
  False, True,
  "Our number rests on Williams starting, which captured evidence contradicts (schedule listing + CONFIRMED news + Williams DNP). Known open gap W5-G15 (by rule, news and schedule listing are not consumed until an OUT designation); a design gap rather than a code defect. In the scenario our Bagent (19.03) exceeds FC (13.14) by 5.9; his 2026 DK avg is 5.99 over 2 appearances (one start, 9.82), and team volume is QB-blind (W5-G1).")
C_["Braelon Allen"] = ("AVAILABILITY_ASSUMPTION", ["ROLE_JUDGEMENT", "VOLUME_OR_EFFICIENCY_MODEL"],
  "Breece Hall projected at p_plays 1.0 despite DNP Wed+Thu, 'essentially out' [REPORTED]; FC omits Hall and tags Allen RB1; Allen rank 2 p_plays 0.635 -> 4.72; scenario (Hall out) 10.56; FC 13.13",
  False, True,
  "FC's number is a Hall-out number. Setting Hall out moves Allen 4.72 -> 10.56 (closes 5.8 of 8.4). Residual 2.6: band stays SECONDARY from his own history/usage (ceiling lifts to ALPHA via the W5-G12 fix) and Hall's carries are spread club-wide pro rata (W5-G11). Practice evidence is captured; the 'out' reading is REPORTED tier only.")
C_["TreVeyon Henderson"] = ("FC_SPECIFIC", ["ROLE_JUDGEMENT", "ROLE_EVIDENCE_DEFECT"],
  "2026: 3 gp, 12.7 car/g, 3.71 ypc, DK avg 7.23; ours if-plays 7.48 x p_plays 0.635 = 5.33; FC 12.79 (+5.6 over his average); tie with Stevenson at rank 1 broken by id",
  False, False,
  "W5-G13 tie present (Henderson usage 1/chart RB2, Stevenson usage 2/chart RB1, both rank 1) but the id order happens to match the captured chart, and TIE-1 moves him -0.01. Our conditional number matches his 2026 production; the rank-2 appearance base rate (0.635) costs 2.2 DK although he played every week since W2. FC is the outlier against his production.")
C_["Rico Dowdle"] = ("FC_SPECIFIC", ["ROLE_JUDGEMENT", "AVAILABILITY_ASSUMPTION"],
  "dislocated toe W2, no game since, limited [CONFIRMED]; 2026: 2 gp, 7.5 car/g, 2.47 ypc, DK avg 5.25; ours 6.38 (if-plays 9.13, p 0.635, DEPTH_RANK_2 cap SECONDARY, history PRIMARY); FC 12.79",
  False, False,
  "Our number sits slightly above his 2026 production; FC treats PIT as a near-even committee (Warren 13.28 / Dowdle 12.79). The real disagreement is the PIT split (see Warren); our RB2 SECONDARY cap is a defensible but disputable call for a returning back with PRIMARY history.")
C_["Romeo Doubs"] = ("VOLUME_OR_EFFICIENCY_MODEL", ["FC_SPECIFIC"],
  "target share 0.243 (7.02 tgt) vs 2026 0.169 (5.0/g): blend with ALPHA prior 0.257 at 1/3 weight -> claim 0.199, then NE target claim_sum 0.819 renormalises x1.22; plus 2.29 carries with 0 carries in 2026; ours 14.70 vs avg 11.07, FC 9.05",
  True, True,
  "Volume excess is prior plus club renormalisation (missing claim mass, largely from rank-based p_plays < 1 on NE depth 2+, is spread pro rata onto p=1 starters). Minor suspected defect: his carries field has claim 0 yet final share 0.078 because the WR depth table (measured on targets) is read as a club share of carries (LEGACY_TABLE_SHARE_READ_AS_CLUB_SHARE, CROSS_FIELD_PRIOR_SCOPE=QB_ONLY): about 0.3 DK, contradicted by zero 2026 carries. FC is also 2.0 below his 2026 average.")
C_["Jauan Jennings"] = ("FC_SPECIFIC", ["ROLE_JUDGEMENT", "VOLUME_OR_EFFICIENCY_MODEL"],
  "2026: 3 gp, 1.3 tgt/g, share 0.04, DK avg 0.97 (snaps 48/80/95%); chart WR3 -> DEPTH_RANK_3 ROTATIONAL, history ALPHA conflict; ours 1.89 (p 0.587, if-plays 3.06); FC 8.26",
  False, False,
  "FC prices his ALPHA history (49ers); every 2026 signal except snap share says a low-target role. Rank-3 appearance base rate (0.587) is low for a 95%-snap player but immaterial to the gap. MIN QB regime (Murray W3-4) not consumed (W5-G1); Addison DNP not consumed.")
C_["Theo Johnson"] = ("FC_SPECIFIC", ["ROLE_JUDGEMENT", "AVAILABILITY_ASSUMPTION"],
  "2026: 4 gp, 1.5 tgt/g, share 0.054, DK avg 2.5; chart TE2 behind Likely (share 0.315) -> DEPTH_RANK_2 SECONDARY, history ALPHA; ours 2.33 (p 0.579, if-plays 3.85); FC 8.23",
  False, False,
  "FC is 3.3x his 2026 average; possibly FC redistributes for Nabers / Najee Harris (both DNP, undesignated, not consumed by us). Our number is consistent with his 2026 role.")
C_["Mason Taylor"] = ("FC_SPECIFIC", ["ROLE_EVIDENCE_DEFECT", "AVAILABILITY_ASSUMPTION"],
  "captured chart TE2 (Ruckert TE3) but engine ties Taylor (chart 2, no usage) with Ruckert (usage 2) at rank 2; id 00-0037805 < 00-0040736 puts Taylor at position rank 3 -> ROTATIONAL, p_plays 0.12 -> 0.38; TIE-1 gives 2.46 (p 0.579); 2026 avg 0.9 in 2 gp; FC 8.19",
  True, True,
  "Demonstrable W5-G13 defect against captured evidence: the id tie-break inverts the club's own chart order and costs 2.08 DK (TIE-1 measured). Even repaired, FC is ~5.7 above anything his 2026 usage supports, so by magnitude the gap is FC's (likely a Hall/Mitchell-out redistribution). Scenario keeps the tie (0.45). He practised Full (thumb).")
C_["Malik McClain"] = ("FC_SPECIFIC", ["AVAILABILITY_ASSUMPTION"],
  "2026: 2 gp (snaps 27%, 3%), 0 targets, DK avg 0.0; chart WR4 -> FRINGE, p 0.266; ours 0.62; scenario (Mitchell out) 1.66; FC 8.17 with floor 0.0 and ceiling 0.0",
  False, False,
  "FC tags him WR3 (Mitchell-out promotion) and its own row is internally inconsistent (proj 8.17, floor 0, ceiling 0). No 2026 evidence of a receiving role.")
C_["Malik Washington"] = ("VOLUME_OR_EFFICIENCY_MODEL", ["FC_SPECIFIC"],
  "target share 0.315 (8.3 tgt) vs 2026 0.2745 (7.0/g): blended claim 0.241 x (1/MIA target claim_sum 0.764 = 1.31); TD expectation 0.41/g vs 0 TDs in 2026; ours 14.34 vs avg 9.78; FC 8.16",
  False, False,
  "MIA has the lowest target claim_sum on the slate (0.764), so every MIA claim is scaled up 31%; the alpha absorbs most. Ours +4.6 over his production, FC -1.6 under it. Not shown to be a defect: renormalisation is declared, but its size here deserves a check of what the missing 24% is.")
C_["T.J. Hockenson"] = ("FC_SPECIFIC", ["VOLUME_OR_EFFICIENCY_MODEL"],
  "2026: 4 gp, 6.5 tgt/g, share 0.26, DK avg 12.62; ours 6.73 tgt, 13.17; FC 7.66 (-5.0 under his average)",
  False, False,
  "Our number matches his 2026 volume and production. MIN QB regime change (Murray W3-4) is not consumed (W5-G1), which could matter either way.")
C_["Kevin Austin Jr."] = ("FC_SPECIFIC", ["ROLE_JUDGEMENT"],
  "2026: 4 gp, snaps 6-14%, 1 target total, DK avg 0.42; chart WR4 -> FRINGE (history PRIMARY conflict), p 0.266, if-plays 2.82; ours 0.77; FC 7.02",
  False, False,
  "Even at p_plays 1.0 we would be 2.8. FC is the outlier against every 2026 signal.")
C_["Jaylin Noel"] = ("ROLE_EVIDENCE_DEFECT", ["ROLE_JUDGEMENT"],
  "4/4 gp, 3.0 tgt/g, snaps 30/60/26/62%, DK avg 7.28; supplied rank 4 (chart WR4) re-indexed to position rank 5 after the Collins/Hutchinson rank-1 tie, behind Jared Wayne (chart WR5, usage 3); p_plays 0.077 -> 0.48; if-plays 5.83 vs FC 5.91",
  True, True,
  "The whole gap is P(plays): our conditional 5.83 equals FC's 5.91. Two compounding mechanisms: (a) ordinal re-indexing after a tie (sorted (1,1,2,3,4) -> 1..5) demotes everyone below a tie by one slot, which W5-G13 does not name and TIE-1 (competition rank 1,1,3,4,5) does not fix; rank 4 would give p 0.266 (~+1.1 DK); (b) P(plays) comes only from a league base rate by depth rank (measured on realised-volume ranks) and ignores his own 4/4 appearance record. Suspected defect, needs a failing test.")
C_["Michael Pittman"] = ("AVAILABILITY_ASSUMPTION", ["ROLE_EVIDENCE_DEFECT"],
  "FC omits him; [CONFIRMED] aggravated foot, limited Wed, DNP Thu, 'expected to miss multiple weeks', IR not announced; engine p_plays 0.86 (rank-2 base rate) -> 7.97; 2026: 3 gp, 4.0 tgt/g, DK avg 5.3",
  False, True,
  "Our number assumes he plays against CONFIRMED-tier news (no designation captured yet, so by rule not consumed). Even if he plays, 7.97 is above his 2026 production (history ALPHA, prior PLAYER_OWN_OFF_ROLE). W5-G13 tie with Roman Wilson at rank 2 broken by id, consistent with chart (Pittman WR2, Wilson WR3); harmless here.")
C_["Breece Hall"] = ("AVAILABILITY_ASSUMPTION", [],
  "FC omits him; DNP Wed+Thu (quad), 'essentially out' [REPORTED]; engine p_plays 1.0 -> 15.00; 2026: 3 gp, 17.0 car/g, DK avg 15.17",
  False, True,
  "Conditional on playing, our number matches his 2026 production. The disagreement is only whether he plays. Practice DNP is captured; the 'out' reading is REPORTED tier.")
C_["Adonai Mitchell"] = ("AVAILABILITY_ASSUMPTION", ["ROLE_JUDGEMENT"],
  "FC omits him; DNP Wed+Thu (finger), 'essentially out' [REPORTED]; engine p_plays 0.86 (rank-2 base rate) -> 8.09; 2026: 2 gp, 7.5 tgt/g, DK avg 10.65",
  False, True,
  "Disagreement is whether he plays. If he plays, our number is below his 2-game production (DEPTH_RANK_2 SECONDARY cap, history ALPHA conflict).")
C_["Caleb Williams"] = ("AVAILABILITY_ASSUMPTION", ["VOLUME_OR_EFFICIENCY_MODEL"],
  "FC omits him; [CONFIRMED] Chicago Sun-Times 2026-10-05: ruled out (Grade 2 hamstring), Bagent starts; nflverse schedule capture lists Bagent; DNP; engine starts him from captured chart QB1 at p_plays 1.0 -> 21.96; 2026: 2 gp, DK avg 22.99",
  False, True,
  "The strongest contradiction on the board: our number assumes a starter whom CONFIRMED news and the captured schedule listing both say will not play. Open gap W5-G15; every CHI and GB projection is conditioned on him.")

big = [r for r in ev if r.get('ours_minus_benchmark') is not None and abs(r['ours_minus_benchmark']) >= 5]
extra = [r for r in ev if r['player'] in ('Breece Hall', 'Caleb Williams', 'Michael Pittman', 'Adonai Mitchell')]
out = []
for e in sorted(big, key=lambda r: r['ours_minus_benchmark']) + extra:
    pid = I[(norm(e['player']), e['team'])]
    p = inc['rows'][pid]; s = st['players'][pid]; r = rs['states'][pid]
    tp = tie['rows'][pid]; sp = scn['rows'].get(pid)
    cv = p.get('conditional_volume') or {}
    li = p.get('dk_points_if_plays_line_items') or {}
    opp = sum((cv.get(k) or 0) for k in ('targets', 'carries', 'pass_attempts'))
    o = obs26(p['gsis_id'])
    rr = rbx.get((norm(e['player']), e['team']))
    prim, sec, line, defect, contra, note = C_[e['player']]
    fc = e.get('benchmark_fc') or {}
    out.append({
        'player': p['name'], 'team': e['team'], 'pos': e['pos'],
        'ours': round(p['dk_points'], 2), 'ours_if_plays': round(p['dk_points_if_plays'], 2),
        'fc': fc.get('proj'), 'fc_floor': fc.get('floor'), 'fc_ceiling': fc.get('ceiling'), 'fc_depth_tag': fc.get('depth_tag'),
        'diff': e.get('ours_minus_benchmark'),
        'p_plays': p['p_plays'],
        'volume': {
            'unconditional': {k: round(p.get(k) or 0, 2) for k in ('targets', 'carries', 'pass_attempts')},
            'if_plays': {k: round(cv.get(k) or 0, 2) for k in ('targets', 'carries', 'pass_attempts')},
            'final_club_share': {f: ((p.get('allocation') or {}).get(f) or {}).get('final_share') for f in ('targets', 'carries', 'pass_attempts')},
            'claims_before_normalising': p.get('claims'),
            'club_claim_sum_before_normalising': {f: inc['allocation_account'][e['team']][f]['claim_sum_before_normalising'] for f in ('targets', 'carries', 'pass_attempts')},
        },
        'efficiency': {
            'dk_per_opportunity_if_plays': round(p['dk_points_if_plays'] / opp, 3) if opp else None,
            'rates': {k: (round(v, 3) if isinstance(v, (int, float)) else v) for k, v in (p.get('efficiency') or {}).items()},
            'prior_tier': p.get('prior_tier'), 'prior_confidence': p.get('prior_confidence'),
            'prior_effective_obs': p.get('prior_effective_obs'),
        },
        'td_expectation_if_plays': {
            'rush_td': round((li.get('rush_td') or 0) / 6, 3), 'rec_td': round((li.get('rec_td') or 0) / 6, 3),
            'pass_td': round((li.get('pass_td') or 0) / 4, 3),
            'club_pool_scale': {k: v for k, v in (p.get('td') or {}).items() if 'scale' in k}},
        'observed_2026': {
            'games_played': ((rr or {}).get('estimates') or {}).get('games_played_2026', o.get('games_played')),
            'dk_avg': ((rr or {}).get('estimates') or {}).get('dk_avg_2026', o.get('dk_avg')),
            'dk_avg_source': ('research board (snap-based participation)' if rr else 'nflverse stat rows (player not on FC-derived research board)'),
            'engine_weeks_played': (s.get('observed_2026') or {}).get('weeks_played'),
            'engine_observed_share': (s.get('observed_2026') or {}).get('combined'),
            'per_stat_row_game': o,
            'research_board_estimates': (rr or {}).get('estimates')},
        'availability': {'state': (s.get('current_availability') or {}).get('status'),
                         'practice_engine_state': (s.get('current_availability') or {}).get('practice_status'),
                         'practice_board_latest': e.get('practice_status'), 'injury': e.get('injury')},
        'role_band': p['role_band'], 'ceiling': p['askable_ceiling'],
        'evidence_for_ceiling': {
            'evidence': r.get('evidence'), 'depth_rank_supplied': s.get('depth_rank'),
            'depth_usage_rank': s.get('depth_usage_rank'), 'depth_chart_captured': e.get('depth_chart_captured'),
            'depth_source': s.get('depth_source'), 'position_rank': r.get('depth_rank_within_position'),
            'historical_band': r.get('historical_band'), 'observed_band': r.get('observed_band'),
            'observed_share': r.get('observed_share'), 'capped': r.get('capped'), 'cap_reason': r.get('cap_reason'),
            'role_evidence_conflict': (r.get('role_evidence_conflict') and {k: r['role_evidence_conflict'][k] for k in ('kind', 'history_band', 'assigned_band', 'evidence', 'ceiling')}),
            'stored_not_consumed': e.get('STORED_NOT_CONSUMED')},
        'tie1_arm_value': round(tp['dk_points'], 2),
        'tie1_arm_band_ceiling': [tp.get('role_band'), tp.get('askable_ceiling')],
        'scenario_value': (round(sp['dk_points'], 2) if sp and sp.get('dk_points') is not None else None),
        'scenario_note': (None if sp and sp.get('dk_points') is not None else 'set OUT in scenario_reported_outs (no projection)'),
        'primary_cause': prim, 'secondary_causes': sec,
        'evidence_line': line, 'defect_suspected': defect,
        'assumption_contradicted_by_captured_evidence': contra,
        'note': note,
    })
meta = {'ARTIFACT': 'FC_DISAGREEMENT_DIAGNOSIS', 'as_of': '2026-10-09',
        'read_only_sources': {'incumbent': RUN + 'incumbent', 'tie1': RUN + 'tie1', 'scenario': RUN + 'scenario_reported_outs',
                              'evidence_board': EB + 'WEEK5_EVIDENCE_BOARD.json', 'research_board': EB + 'WEEK5_FULL_PLAYER_RESEARCH_BOARD.json',
                              'stats_2026': 'raw/classic_early_2026W5/NFLVERSE_STATS_PLAYER_WEEK_2026 (scored with classic_week_research.dk_points)'},
        'FC_IS': 'an independent benchmark only; agreement with FC is not a target',
        'PRIMARY_RULE': 'primary = the cause accounting for the largest measured or bounded share of ours-minus-FC; demonstrable defects are flagged by defect_suspected regardless of size',
        'observed_2026_IS_NOT': 'an outcome of the predicted game; it is pre-kickoff input evidence, 2-4 games, noisy'}
from collections import Counter
meta['counts_by_primary_cause'] = dict(Counter(x['primary_cause'] for x in out))
meta['n_rows'] = len(out)
meta['structural_pattern'] = ('all 5 rows where we exceed FC are club rank-1 players with p_plays 1.0; all 12 where we trail FC have p_plays < 1 '
    '(depth rank >= 2). Against their own 2026 production, rank-1 Warren/Doubs/Washington sit +3.3/+3.6/+4.6 above while depth-2+ '
    'Allen/Henderson/Monangai/Noel sit below. Hypothesis, not a finding: rank-only P(plays) removes volume from depth 2+ and club '
    'renormalisation (claim_sum < 1) returns it pro rata, concentrating it on starters.')
json.dump({'meta': meta, 'rows': out}, open('FC_DISAGREEMENT_DIAGNOSIS.json', 'w'), indent=1, default=float)
print(meta['counts_by_primary_cause'], len(out))
for x in out: print(f"{x['player']:20s} {x['ours']:6.2f} {str(x['fc']):6s} {x['primary_cause']:28s} tie1 {x['tie1_arm_value']} scn {x['scenario_value']} o26 {x['observed_2026'].get('dk_avg')} gp {x['observed_2026'].get('games_played')} defect {x['defect_suspected']}")
