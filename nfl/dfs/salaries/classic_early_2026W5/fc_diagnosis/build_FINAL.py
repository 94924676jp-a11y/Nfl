import json, sys
import pandas as pd
from load_FINAL import *
from usage_FINAL import usage
inj = pd.read_csv('/home/user/nfl/nfl/dfs/salaries/raw/classic_early_2026W5/NFLVERSE_INJURIES_2026.21e35d2a84353248.slate16.csv.gz')
inj = inj[(inj.season == 2026) & (inj.week == 5)]
old = {r['player']: r for r in json.load(open('FC_DISAGREEMENT_DIAGNOSIS.json'))['rows']}
rbx = {(norm(r['player']), r['team']): r for r in rb}
evx = {(norm(r['player']), r['team']): r for r in ev}

# player -> (primary, secondary, defects{id: note}, scenario_applies, verdict, football_evidence, note)
K = {}
G16 = 'W5-G16 slot P(plays)'; RC1 = 'RC-1 WR2/formation ceiling'; G18 = 'W5-G18 QB identity not consumed'
K["Tyson Bagent"] = ("AVAILABILITY_ASSUMPTION", ["VOLUME_OR_EFFICIENCY_MODEL"],
  {G18: "material: production starts Caleb Williams (captured chart QB1) and gives Bagent the QB2 slot P(plays) 0.138; also team volume is QB-blind in the scenario", "W5-G15": "open; schedule capture lists Bagent and is not consumed"},
  "CHI_BAGENT_STARTS = 19.01",
  "OUR_NUMBER_UNRELIABLE (production assumes Williams starts; every source, including the schedule capture, has Bagent; use CHI_BAGENT_STARTS 19.01, itself provisional under W5-G18)",
  "W4: 34 att, 4 carries, 100% snaps, 9.82 DK (his only start); W2 relief 9 att; QB verification: Bagent expected starter, REPORTED_SECONDARY_CONSISTENT, 0 of 16 clubs officially confirmed",
  "The scenario number (19.01) is 5.9 above FC and 3x his only-start output (9.82); with team volume QB-blind it should not be read as supported either.")
K["Caleb Williams"] = ("AVAILABILITY_ASSUMPTION", [],
  {G18: "material: engine has him starting from captured chart QB1", "W5-G15": "open"},
  "CHI_BAGENT_STARTS = 0",
  "OUR_NUMBER_UNRELIABLE (Grade 2 hamstring, DNP all week, coach-relayed ruling that Bagent starts; production still projects him at p_plays 1.0)",
  "2026: W1-2 only (29, 26 att), 22.99 DK avg; official practice DNP (hamstring); FC omits him",
  "Conditional on playing the number tracks his W1-2 output; the problem is entirely who starts.")
K["Braelon Allen"] = ("AVAILABILITY_ASSUMPTION", ["ROLE_JUDGEMENT"],
  {G16: "applies: RB2 slot P(plays) 0.635 although he had carries in 4/4 weeks; AP-1 arm 5.65 (+0.93)"},
  "none in the final set (no NYJ Hall-out scenario); pre-repair research scenario with Hall out gave 10.56",
  "OUR_NUMBER_PROVISIONAL (depends on Breece Hall, DNP Wed+Thu and reported 'essentially out'; if Hall sits our 4.72 is too low and no final-run scenario quantifies it)",
  "carries 10/5/4/14, car share 0.26/0.19/0.21/1.00 (W4 Hall absent), snaps 40/31/52/94%; 6.47 DK avg",
  "FC tags him RB1, i.e. FC's number is a Hall-out number.")
K["Mason Taylor"] = ("FC_SPECIFIC", ["ROLE_JUDGEMENT"],
  {G16: "applies at TE3 slot (0.12) but AP-1 does not (he missed W3-4): A3 0.36", RC1: "A2 arm 2.37 (+1.99)"},
  "none",
  "OUR_NUMBER_PROVISIONAL (repair now orders NYJ TEs usage-first, so Ruckert, who played every week, is TE2 although the captured chart lists Taylor TE2; Taylor practised Full after missing W3-4)",
  "targets 3/0/-/-, snaps 66/46/-/- (thumb, missed W3-W4); Ruckert 34-44% snaps every week, 4.7 DK avg; official practice Full (thumb)",
  "FC 8.19 is ~9x his 2026 average; even the most generous research arm (2.37) is far from it. The disputable part is TE2 vs TE3, worth ~2 DK.")
K["Malik McClain"] = ("FC_SPECIFIC", ["AVAILABILITY_ASSUMPTION"],
  {G16: "formally (WR4 slot 0.266) but AP-1 does not apply (no measure in W1-2)"},
  "none (Mitchell-out would lift him; pre-repair research scenario 1.66)",
  "OUR_NUMBER_SUPPORTED (0 targets in 2026, snaps 27% and 3%)",
  "W3-4 only: 0 targets, 0 carries, snaps 27/3%",
  "FC's row is internally inconsistent: proj 8.17 with floor 0 and ceiling 0.")
K["TreVeyon Henderson"] = ("FC_SPECIFIC", ["ROLE_JUDGEMENT"],
  {G16: "applies: RB2 slot 0.635 though active W2-W4; AP-1 arm 5.63 (+0.30)"},
  "none",
  "OUR_NUMBER_SUPPORTED (conditional 7.48 matches his 7.23 average; slot P(plays) costs at most ~0.3 per AP-1)",
  "carries -/16/8/14, car share -/0.57/0.31/0.40, snaps -/60/37/37%, 3 targets total; Stevenson chart RB1 (limited, knee)",
  "Tie with Stevenson now resolved by chart (Stevenson RB1), same outcome as before.")
K["Rico Dowdle"] = ("FC_SPECIFIC", ["ROLE_JUDGEMENT", "AVAILABILITY_ASSUMPTION"],
  {G16: "applies (RB2 slot 0.635); AP-1 does not (no game W3-W4): A3 5.54"},
  "none",
  "OUR_NUMBER_PROVISIONAL (returning from a dislocated toe, official Limited; his share against Warren is unknown)",
  "carries 8/7/-/-, car share 0.38/0.30, snaps 58/26%, 5.25 DK avg; official practice Limited (toe)",
  "FC splits PIT almost evenly (Warren 13.28 / Dowdle 12.79); we follow the W1-4 pooled share.")
K["Jauan Jennings"] = ("FC_SPECIFIC", ["ROLE_JUDGEMENT"],
  {RC1: "applies (WR3 capped ROTATIONAL): A2 2.29 (+0.40)", G16: "formally (WR3 slot 0.587); AP-1 does not (no target W2)"},
  "none",
  "OUR_NUMBER_SUPPORTED (1/0/2/1 targets on 48/-/80/95% snaps; 0.97 DK avg)",
  "targets 1/0/2/1, tgt share 0.04/0/0.08/0.03, snaps 48/-/80/95%",
  "FC prices his history. The rising snap share is the one signal for more; it has not produced targets.")
K["Kyle Monangai"] = ("ROLE_JUDGEMENT", ["AVAILABILITY_ASSUMPTION"],
  {G16: "material: RB2 slot 0.635 though 10+ carries every week; AP-1 arm 9.08 (+1.47)", G18: "CHI_BAGENT_STARTS 7.92 (+0.31)"},
  "CHI_BAGENT_STARTS = 7.92",
  "OUR_NUMBER_PROVISIONAL (turf toe, official DNP Wed+Thu, 'in doubt'; if he plays, W4 usage and Swift's fumble benching argue above our capped RB2 share)",
  "carries 10/10/10/30, car share 0.26/0.32/0.29/0.56, snaps 43/34/31/54%, 8 RZ opps W4; 16.32 DK avg; official DNP (thumb, toe)",
  "Two opposite errors partly cancel: slot P(plays) cuts him as if a backup, which accidentally resembles his real injury risk.")
K["Kevin Austin Jr."] = ("FC_SPECIFIC", [],
  {G16: "formally (WR4 slot 0.266); AP-1 arm 0.73", RC1: "A2 1.80 (+1.03)"},
  "none",
  "OUR_NUMBER_SUPPORTED (1 target all season on 6-14% snaps)",
  "targets 0/1/0/0, snaps 6/7/14/12%, 0.42 DK avg",
  "")
K["Theo Johnson"] = ("FC_SPECIFIC", ["ROLE_JUDGEMENT"],
  {G16: "applies (TE2 slot 0.579, played 4/4); AP-1 arm 2.69 (+0.33)"},
  "none",
  "OUR_NUMBER_SUPPORTED (6 targets in 4 games behind Likely's 0.32 share; 2.5 DK avg)",
  "targets 1/4/0/1, snaps 46/28/17/33%; Likely target share 0.315",
  "FC may be redistributing for Nabers / Najee Harris practice absences, which we do not consume.")
K["Jaylin Noel"] = ("ROLE_EVIDENCE_DEFECT", ["ROLE_JUDGEMENT"],
  {G16: "material: WR5 slot P(plays) 0.077 for a player who recorded targets in 4/4 weeks; AP-1 arm 3.71 (+3.23)", RC1: "A2 0.56", "ordinal re-index": "still present after the repair: supplied rank 4 (chart WR4) becomes position rank 5 behind Jared Wayne (chart WR5) because the Collins/Hutchinson tie consumes a slot"},
  "none",
  "OUR_NUMBER_UNRELIABLE (rests on W5-G16: P(plays) 0.077 against targets in every game at 26-62% snaps)",
  "targets 2/5/2/3, carries 0/1/1/1, snaps 30/60/26/62%, 7.28 DK avg",
  "Our conditional number (5.83) is essentially FC's (5.91); the gap is P(plays) alone.")
K["Jaylen Warren"] = ("VOLUME_OR_EFFICIENCY_MODEL", ["ROLE_JUDGEMENT"],
  {G16: "concentration: AP-1 arm 16.20 (-2.18) when backups keep their own appearance rate"},
  "none",
  "OUR_NUMBER_PROVISIONAL (TD expectation 0.63/game against 0 TDs in 2026, PIT rush TD pool scale 1.69; carry share pooled over Dowdle-absent W3-4)",
  "carries 10/11/17/17, car share 0.48/0.48/0.74/0.90 (Dowdle out W3-4), targets 6/4/4/6, snaps 37/71/90/97%, 0 TDs",
  "Volume matches his average; the excess is touchdowns plus the slot concentration.")
K["Chris Olave"] = ("FC_SPECIFIC", ["AVAILABILITY_ASSUMPTION"],
  {},
  "none",
  "OUR_NUMBER_PROVISIONAL (volume and production support it, 12 targets/game, 24.77 avg; but a new foot injury, official Limited Thursday, is not represented)",
  "targets 13/10/13/12, tgt share 0.25/0.31/0.33/0.26, snaps 86/84/84/86%",
  "Engine state still carries the Wednesday DNP line (W5-G14); neither moves P(plays).")
K["T.J. Hockenson"] = ("FC_SPECIFIC", ["VOLUME_OR_EFFICIENCY_MODEL"],
  {G18: "not material (Murray is the verified starter and started W3-4)", G16: "concentration: AP-1 arm 12.46 (-0.71)"},
  "none",
  "OUR_NUMBER_SUPPORTED (6.5 targets/game, 0.26 share, 12.62 avg)",
  "targets 5/4/4/13, tgt share 0.22/0.21/0.16/0.39, snaps 66/69/85/83%",
  "FC is 5 below his own average.")
K["Romeo Doubs"] = ("VOLUME_OR_EFFICIENCY_MODEL", ["FC_SPECIFIC"],
  {G16: "concentration: AP-1 arm 12.58 (-2.21)", RC1: "A2 14.23"},
  "none",
  "OUR_NUMBER_PROVISIONAL (we project 7.0 targets against 5.0/game: ALPHA prior plus NE renormalisation and slot concentration)",
  "targets 3/4/4/9, tgt share 0.10/0.19/0.13/0.25, snaps 56/67/73/64%; Hollins (same share) DNP",
  "FC is also 2 below his average.")
K["Malik Washington"] = ("VOLUME_OR_EFFICIENCY_MODEL", ["FC_SPECIFIC"],
  {G16: "concentration: AP-1 arm 13.17 (-1.17)"},
  "none",
  "OUR_NUMBER_PROVISIONAL (share 0.315 vs 0.27 observed after MIA claims are scaled x1.31; 0.41 TD/game vs 0 in 2026)",
  "targets 8/5/10/5, tgt share 0.30/0.22/0.29/0.29, snaps 98/73/86/87%, 0 TDs, QB Malik Willis",
  "Our number is 4.6 above his production, FC 1.6 below it.")
K["Michael Pittman"] = ("AVAILABILITY_ASSUMPTION", ["ROLE_JUDGEMENT"],
  {G16: "WR2 slot 0.861 (not the issue)", RC1: "applies (WR2 capped SECONDARY): A2 8.47"},
  "none in the final set (pre-repair research scenario set him out)",
  "OUR_NUMBER_UNRELIABLE (latest official capture DNP Thursday, foot; reported aggravated and 'expected to miss multiple weeks'; projection assumes he plays at 0.861)",
  "targets 3/-/5/4, snaps from W1/W3/W4 only, 5.3 DK avg; latest official practice line DNP (foot) -- the evidence board and engine state still show Limited",
  "Even if he plays, 7.97 sits above his 2026 output.")
K["Breece Hall"] = ("AVAILABILITY_ASSUMPTION", [],
  {},
  "none in the final set (pre-repair research scenario set him out)",
  "OUR_NUMBER_UNRELIABLE as an expectation (official DNP Wed+Thu, quad, reported 'essentially out', yet P(plays) 1.0); conditional on playing it is supported",
  "carries 22/16/13/-, car share ~0.5-0.6, missed W4; 15.17 DK avg; official DNP (quadricep)",
  "")
K["Adonai Mitchell"] = ("AVAILABILITY_ASSUMPTION", ["ROLE_JUDGEMENT"],
  {RC1: "applies (WR2 capped SECONDARY): A2 8.53 (+0.44)", G16: "WR2 slot 0.861"},
  "none in the final set (pre-repair research scenario set him out)",
  "OUR_NUMBER_UNRELIABLE as an expectation (official DNP Wed+Thu, finger, reported 'essentially out')",
  "targets 3/12/-/-, missed W3-4; 10.65 DK avg; official DNP (finger)",
  "")

big = [r for r in ev if r.get('ours_minus_benchmark') is not None and abs(r['ours_minus_benchmark']) >= 5]
omit = [r for r in ev if not r['in_benchmark_export'] and r['our_dk_points'] >= 4]
assert len(big) == 16, len(big)
rows = []
for e in sorted(big, key=lambda r: r['ours_minus_benchmark']) + omit:
    key = (norm(e['player']), e['team']); pid = I[key]
    p = prod['rows'][pid]; s = st['players'][pid]; r = rs['states'][pid]
    nm = p['name']
    k = K.get(e['player']) or K[nm]
    cv = p.get('conditional_volume') or {}
    il = inj[inj.gsis_id == p['gsis_id']]
    off = ({'practice_status': il.practice_status.iloc[0], 'injury': il.practice_primary_injury.iloc[0],
            'secondary_injury': (None if pd.isna(il.practice_secondary_injury.iloc[0]) else il.practice_secondary_injury.iloc[0]),
            'game_designation': (None if pd.isna(il.report_status.iloc[0]) else il.report_status.iloc[0])}
           if len(il) else {'practice_status': 'NOT ON WEEK-5 REPORT', 'injury': None})
    off['source'] = 'NFLVERSE_INJURIES_2026.21e35d2a84353248 (capture 2026-10-09T13:30Z of the club report)'
    off['board_practice_status'] = e.get('practice_status')
    off['engine_practice_status'] = e.get('practice_status_in_engine_state')
    rr = rbx.get(key)
    q = qbv.get(e['team'], {})
    scen = dict(e.get('scenario_dk_points') or {})
    for sk in ('CIN_CHASE_OUT', 'WAS_MCLAURIN_OUT', 'WAS_DIGGS_OUT'):
        sp = SCN[sk]['rows'].get(pid); scen[sk] = (round(sp['dk_points'], 2) if sp and sp.get('dk_points') is not None else None)
    o = old.get(nm) or old.get(e['player']) or {}
    rows.append({
        'player': nm, 'team': e['team'], 'pos': e['pos'],
        'ours': round(p['dk_points'], 2), 'ours_if_plays': round(p['dk_points_if_plays'], 2),
        'fc': (e.get('benchmark_fc') or {}).get('proj'), 'gap': e.get('ours_minus_benchmark'),
        'ours_previous_diagnosis': o.get('ours'),
        'p_plays': p['p_plays'].get('targets') if e['pos'] != 'QB' else p['p_plays'].get('pass_attempts'),
        'p_plays_source': (e.get('EVIDENCE_CONSUMED_BY_ENGINE') or {}).get('p_plays_source'),
        'projected_volume_if_plays': {kk: round(cv.get(kk) or 0, 2) for kk in ('targets', 'carries', 'pass_attempts')},
        'role': {'band': p['role_band'], 'ceiling': p['askable_ceiling'], 'evidence': r.get('evidence'),
                 'position_rank': r.get('depth_rank'), 'supplied_rank': s.get('depth_rank'),
                 'usage_rank': s.get('depth_usage_rank'), 'chart': e.get('depth_chart_captured'),
                 'historical_band': r.get('historical_band'), 'cap_reason': r.get('cap_reason')},
        'football_evidence': {
            'summary': k[5],
            'usage_by_week_2026': usage(p['gsis_id'], nm, e['team']),
            'dk_avg_2026': ((rr or {}).get('estimates') or {}).get('dk_avg_2026', (o.get('observed_2026') or {}).get('dk_avg')),
            'games_played_2026': ((rr or {}).get('estimates') or {}).get('games_played_2026', (o.get('observed_2026') or {}).get('games_played')),
            'official_practice': off,
            'qb_situation': {'engine_starter': e.get('club_qb_engine_starter'), 'expected_starter': q.get('expected_starter'),
                             'verification_status': q.get('status'), 'scenario_needed': q.get('scenario_needed')},
        },
        'primary_cause': k[0], 'secondary_causes': k[1],
        'known_engine_defects': k[2],
        'rests_on_known_defect': any(('material' in v) for v in k[2].values()),
        'scenario_applies': k[3], 'scenario_dk_points': scen,
        'verdict': k[4], 'note': k[6],
    })
from collections import Counter
meta = {'ARTIFACT': 'FC_DISAGREEMENT_DIAGNOSIS_FINAL', 'as_of': '2026-10-09',
        'production_run': F + 'RESEARCH_STATE_2026W5', 'scenarios': sorted(SCN),
        'evidence_board': EB + 'WEEK5_EVIDENCE_BOARD.json',
        'usage_source': 'pbp_2026.2b3e9f2c6f92123f (W1-4 REG, no 2-pt) + NFLVERSE_SNAP_COUNTS_2026.fd2656dbe119dfe4',
        'FC_IS': 'benchmark only; agreement is not a target and nothing was taken from it',
        'PRIMARY_RULE': 'largest measured or bounded share of ours-minus-FC',
        'research_arms_in_board': 'RESEARCH_A2_FORMATION_CEILING = RC-1, RESEARCH_A3_APPEARANCE = AP-1 (both preregistered, not production)',
        'n_rows': len(rows),
        'counts_by_primary_cause': dict(Counter(x['primary_cause'] for x in rows)),
        'counts_by_verdict': dict(Counter(x['verdict'].split(' ')[0] for x in rows))}
json.dump({'meta': meta, 'rows': rows}, open('FC_DISAGREEMENT_DIAGNOSIS_FINAL.json', 'w'), indent=1, default=str)
md = ['# FC disagreement diagnosis, final Week 5 numbers', '',
      f"Production run `{F}RESEARCH_STATE_2026W5`. FC is a benchmark, not a target. {len(rows)} rows: 16 with |ours - FC| >= 5 plus FC-omitted players we project >= 4.", '',
      '| Player | Ours | FC | Gap | Primary cause | Known defect relied on | Scenario | Verdict |', '|---|---|---|---|---|---|---|---|']
for x in rows:
    d = '; '.join(kk for kk, v in x['known_engine_defects'].items() if 'material' in v) or '-'
    md.append(f"| {x['player']} ({x['team']} {x['pos']}) | {x['ours']} | {x['fc'] if x['fc'] is not None else 'omitted'} | {x['gap'] if x['gap'] is not None else '-'} | {x['primary_cause']} | {d} | {x['scenario_applies']} | {x['verdict']} |")
md += ['', f"Counts by cause: {meta['counts_by_primary_cause']}", f"Counts by verdict: {meta['counts_by_verdict']}", '',
       'Football evidence per player (usage by week, snaps, official practice line, QB situation) is in the JSON.']
open('FC_DISAGREEMENT_DIAGNOSIS_FINAL.md', 'w').write('\n'.join(md) + '\n')
print(meta)
for x in rows: print(x['player'], x['ours'], x['fc'], x['gap'], x['primary_cause'], x['football_evidence']['official_practice']['practice_status'], '| board', x['football_evidence']['official_practice']['board_practice_status'], '|', x['verdict'][:40])
