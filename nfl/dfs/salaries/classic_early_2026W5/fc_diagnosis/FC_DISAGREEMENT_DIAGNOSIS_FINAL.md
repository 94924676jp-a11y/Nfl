# FC disagreement diagnosis, final Week 5 numbers

Production run `/home/user/nfl/nfl/dfs/salaries/runs/w5_final/RESEARCH_STATE_2026W5`. FC is a benchmark, not a target. 20 rows: 16 with |ours - FC| >= 5 plus FC-omitted players we project >= 4.

| Player | Ours | FC | Gap | Primary cause | Known defect relied on | Scenario | Verdict |
|---|---|---|---|---|---|---|---|
| Tyson Bagent (CHI QB) | 0.07 | 13.14 | -13.07 | AVAILABILITY_ASSUMPTION | W5-G18 QB identity not consumed | CHI_BAGENT_STARTS = 19.01 | OUR_NUMBER_UNRELIABLE (production assumes Williams starts; every source, including the schedule capture, has Bagent; use CHI_BAGENT_STARTS 19.01, itself provisional under W5-G18) |
| Braelon Allen (NYJ RB) | 4.72 | 13.13 | -8.41 | AVAILABILITY_ASSUMPTION | - | none in the final set (no NYJ Hall-out scenario); pre-repair research scenario with Hall out gave 10.56 | OUR_NUMBER_PROVISIONAL (depends on Breece Hall, DNP Wed+Thu and reported 'essentially out'; if Hall sits our 4.72 is too low and no final-run scenario quantifies it) |
| Mason Taylor (NYJ TE) | 0.38 | 8.19 | -7.81 | FC_SPECIFIC | - | none | OUR_NUMBER_PROVISIONAL (repair now orders NYJ TEs usage-first, so Ruckert, who played every week, is TE2 although the captured chart lists Taylor TE2; Taylor practised Full after missing W3-4) |
| Malik McClain (NYJ WR) | 0.62 | 8.17 | -7.55 | FC_SPECIFIC | - | none (Mitchell-out would lift him; pre-repair research scenario 1.66) | OUR_NUMBER_SUPPORTED (0 targets in 2026, snaps 27% and 3%) |
| TreVeyon Henderson (NE RB) | 5.33 | 12.79 | -7.46 | FC_SPECIFIC | - | none | OUR_NUMBER_SUPPORTED (conditional 7.48 matches his 7.23 average; slot P(plays) costs at most ~0.3 per AP-1) |
| Rico Dowdle (PIT RB) | 6.38 | 12.79 | -6.41 | FC_SPECIFIC | - | none | OUR_NUMBER_PROVISIONAL (returning from a dislocated toe, official Limited; his share against Warren is unknown) |
| Jauan Jennings (MIN WR) | 1.89 | 8.26 | -6.37 | FC_SPECIFIC | - | none | OUR_NUMBER_SUPPORTED (1/0/2/1 targets on 48/-/80/95% snaps; 0.97 DK avg) |
| Kyle Monangai (CHI RB) | 7.61 | 13.94 | -6.33 | ROLE_JUDGEMENT | W5-G16 slot P(plays) | CHI_BAGENT_STARTS = 7.92 | OUR_NUMBER_PROVISIONAL (turf toe, official DNP Wed+Thu, 'in doubt'; if he plays, W4 usage and Swift's fumble benching argue above our capped RB2 share) |
| Kevin Austin Jr. (NO WR) | 0.77 | 7.02 | -6.25 | FC_SPECIFIC | - | none | OUR_NUMBER_SUPPORTED (1 target all season on 6-14% snaps) |
| Theo Johnson (NYG TE) | 2.36 | 8.23 | -5.87 | FC_SPECIFIC | - | none | OUR_NUMBER_SUPPORTED (6 targets in 4 games behind Likely's 0.32 share; 2.5 DK avg) |
| Jaylin Noel (HOU WR) | 0.48 | 5.91 | -5.43 | ROLE_EVIDENCE_DEFECT | W5-G16 slot P(plays) | none | OUR_NUMBER_UNRELIABLE (rests on W5-G16: P(plays) 0.077 against targets in every game at 26-62% snaps) |
| Jaylen Warren (PIT RB) | 18.38 | 13.28 | 5.1 | VOLUME_OR_EFFICIENCY_MODEL | - | none | OUR_NUMBER_PROVISIONAL (TD expectation 0.63/game against 0 TDs in 2026, PIT rush TD pool scale 1.69; carry share pooled over Dowdle-absent W3-4) |
| Chris Olave (NO WR) | 23.49 | 18.17 | 5.32 | FC_SPECIFIC | - | none | OUR_NUMBER_PROVISIONAL (volume and production support it, 12 targets/game, 24.77 avg; but a new foot injury, official Limited Thursday, is not represented) |
| T.J. Hockenson (MIN TE) | 13.17 | 7.66 | 5.51 | FC_SPECIFIC | W5-G18 QB identity not consumed | none | OUR_NUMBER_SUPPORTED (6.5 targets/game, 0.26 share, 12.62 avg) |
| Romeo Doubs (NE WR) | 14.79 | 9.05 | 5.74 | VOLUME_OR_EFFICIENCY_MODEL | - | none | OUR_NUMBER_PROVISIONAL (we project 7.0 targets against 5.0/game: ALPHA prior plus NE renormalisation and slot concentration) |
| Malik Washington (MIA WR) | 14.34 | 8.16 | 6.18 | VOLUME_OR_EFFICIENCY_MODEL | - | none | OUR_NUMBER_PROVISIONAL (share 0.315 vs 0.27 observed after MIA claims are scaled x1.31; 0.41 TD/game vs 0 in 2026) |
| Michael Pittman (PIT WR) | 7.97 | omitted | - | AVAILABILITY_ASSUMPTION | - | none in the final set (pre-repair research scenario set him out) | OUR_NUMBER_UNRELIABLE (latest official capture DNP Thursday, foot; reported aggravated and 'expected to miss multiple weeks'; projection assumes he plays at 0.861) |
| Breece Hall (NYJ RB) | 15.0 | omitted | - | AVAILABILITY_ASSUMPTION | - | none in the final set (pre-repair research scenario set him out) | OUR_NUMBER_UNRELIABLE as an expectation (official DNP Wed+Thu, quad, reported 'essentially out', yet P(plays) 1.0); conditional on playing it is supported |
| Adonai Mitchell (NYJ WR) | 8.09 | omitted | - | AVAILABILITY_ASSUMPTION | - | none in the final set (pre-repair research scenario set him out) | OUR_NUMBER_UNRELIABLE as an expectation (official DNP Wed+Thu, finger, reported 'essentially out') |
| Caleb Williams (CHI QB) | 21.92 | omitted | - | AVAILABILITY_ASSUMPTION | W5-G18 QB identity not consumed | CHI_BAGENT_STARTS = 0 | OUR_NUMBER_UNRELIABLE (Grade 2 hamstring, DNP all week, coach-relayed ruling that Bagent starts; production still projects him at p_plays 1.0) |

Counts by cause: {'AVAILABILITY_ASSUMPTION': 6, 'FC_SPECIFIC': 9, 'ROLE_JUDGEMENT': 1, 'ROLE_EVIDENCE_DEFECT': 1, 'VOLUME_OR_EFFICIENCY_MODEL': 3}
Counts by verdict: {'OUR_NUMBER_UNRELIABLE': 6, 'OUR_NUMBER_PROVISIONAL': 8, 'OUR_NUMBER_SUPPORTED': 6}

Football evidence per player (usage by week, snaps, official practice line, QB situation) is in the JSON.
