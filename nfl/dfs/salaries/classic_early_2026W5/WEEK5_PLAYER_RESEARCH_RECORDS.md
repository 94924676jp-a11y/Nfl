# Week 5 player research records (positive-projection rows)

Confirmed facts come from captures in `nfl/dfs/salaries/raw/classic_early_2026W5/PROVENANCE.json`. Estimates are computed from those facts. Reported news is a secondary web-search supplement and carries its own tag. Our projection is not built yet, because the DK DKEntries export is missing. FC is a benchmark only.

## CHI vs GB

### D'Andre Swift (RB, $6200)
- **Eligibility:** ELIGIBLE (ACT). Practice: Limited Participation in Practice (Hip, Knee). Designation: NOT_YET_ISSUED (designations are issued Friday; absence is not health). Depth: ['RB1'].
- **2026:** 4 games, DK average 17.12, last game 8.4 (week 4).
- **What drives his production:** 2026 target share 9%, carry share 46%; red zone 2026: 1 targets, 19 carries; snap share trend -10 pp (last 2 vs first 2 games); game total 45.5 (nflverse schedule line), away, roof outdoors, rest 7 days; club QB: Tyson Bagent (attempt leaders by week {'1': 'C.Williams', '2': 'C.Williams', '3': 'C.Keenum', '4': 'T.Bagent'}); teammates with availability doubt: Kyle Monangai.
- **Reported [CONFIRMED]:** RB D'Andre Swift (hip/knee): DNP Wednesday, limited Thursday. (https://athlonsports.com/nfl/chicago-bears/bears-packers-thursday-injury-report-latest-updates-and-analysis-for-week-5)
- **Reported [CONFIRMED]:** W4: Monangai had 30 carries, 146 yds, 2 TD; Swift had 15 carries, 58 yds. Johnson called Swift's second-half fumble 'egregious' and denied the benching was injury-related. The Sun-Times says the fumble 'could cost him vs. Packers'. (https://www.nbcsports.com/fantasy/football/player-news/2026-10-04/ben-johnson-denies-benching-swift)
- **Benchmark FC:** 17.72 (floor 6.32, ceiling 32.92). Our projection: NOT BUILT.
- **Missing model dependencies:** QB-conditioned team volume / shares NOT consumed by the engine (W5-G1); practice participation does not change a projection until a designation; no partial-workload model (W5-G4); lower-tail volatility under-stated for high-mean players (D-01).
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### Kyle Monangai (RB, $5200)
- **Eligibility:** ELIGIBLE (ACT). Practice: Did Not Participate In Practice (Thumb, Toe). Designation: NOT_YET_ISSUED (designations are issued Friday; absence is not health). Depth: ['RB2'].
- **2026:** 4 games, DK average 16.32, last game 31.0 (week 4).
- **What drives his production:** 2026 target share 4%, carry share 36%; red zone 2026: 1 targets, 14 carries; snap share trend +4 pp (last 2 vs first 2 games); game total 45.5 (nflverse schedule line), away, roof outdoors, rest 7 days; club QB: Tyson Bagent (attempt leaders by week {'1': 'C.Williams', '2': 'C.Williams', '3': 'C.Keenum', '4': 'T.Bagent'}).
- **Reported [CONFIRMED]:** RB Kyle Monangai (thumb/toe): DNP Wednesday and Thursday. ESPN's Jeremy Fowler reports turf toe, which puts Week 5 in doubt. Johnson had earlier said the thumb is 'not an issue'. (https://athlonsports.com/nfl/chicago-bears/bears-packers-thursday-injury-report-latest-updates-and-analysis-for-week-5)
- **Reported [CONFIRMED]:** W4: Monangai had 30 carries, 146 yds, 2 TD; Swift had 15 carries, 58 yds. Johnson called Swift's second-half fumble 'egregious' and denied the benching was injury-related. The Sun-Times says the fumble 'could cost him vs. Packers'. (https://www.nbcsports.com/fantasy/football/player-news/2026-10-04/ben-johnson-denies-benching-swift)
- **Benchmark FC:** 13.94 (floor 1.34, ceiling 30.74). Our projection: NOT BUILT.
- **Flags:** DID_NOT_PRACTICE
- **Missing model dependencies:** QB-conditioned team volume / shares NOT consumed by the engine (W5-G1); practice participation does not change a projection until a designation; no partial-workload model (W5-G4); accounting repair pending (D-05) affects all players.
- **Next research action:** capture Friday designation; if OUT, check redistribution to same-position teammates.

### Tyson Bagent (QB, $4700)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['QB2'].
- **2026:** 2 games, DK average 5.99, last game 9.82 (week 4).
- **What drives his production:** red zone 2026: 0 targets, 4 carries; game total 45.5 (nflverse schedule line), away, roof outdoors, rest 7 days; club QB: Tyson Bagent (attempt leaders by week {'1': 'C.Williams', '2': 'C.Williams', '3': 'C.Keenum', '4': 'T.Bagent'}); teammates with availability doubt: Kyle Monangai.
- **Reported [CONFIRMED]:** Tyson Bagent will start Week 5 at GB. Ben Johnson on ESPN 1000 Monday: 'Tyson will be the guy.' Caleb Williams (Grade 2 hamstring) is out. (https://chicago.suntimes.com/bears/2026/10/05/bears-rule-out-qb-caleb-williams-vs-packers-will-start-backup-tyson-bagent-again)
- **Reported [REPORTED]:** QB by week: Williams started W1 and W2 and was hurt in the W2 9-3 loss to MIN. Case Keenum was reported as the W3 MNF starter vs PHI (pre-game reports; Bagent had just cleared concussion protocol). Bagent started W4 (W 23-12 vs NYJ; 25/34, 268 yds, 1 INT). Keenum is the Week 5 backup. (https://www.nfl.com/news/bears-qb-caleb-williams-injury-vikings)
- **Benchmark FC:** 13.14 (floor 3.69, ceiling 25.74). Our projection: NOT BUILT.
- **Flags:** FC_VS_RECENT_PRODUCTION: FC 13.14 vs 2026 DK avg 5.99 | QB_REGIME_CHANGE: listed starter is not the dominant passer of the modelling window | THIN_STARTER_EVIDENCE: 1 2026 start(s) by the listed starter | QB_CHURN: 3 different attempt leaders in 4 games
- **Missing model dependencies:** QB-conditioned team volume / shares NOT consumed by the engine (W5-G1); QB rushing from a generic cohort prior, starts pooled with relief (D-03); accounting repair pending (D-05) affects all players.
- **Next research action:** confirm the starter from a team source; run the QB shadow candidate for this club; decompose FC vs recent production: volume, efficiency or availability assumption.

### Luther Burden III (WR, $4900)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['WR2'].
- **2026:** 4 games, DK average 11.97, last game 11.4 (week 4).
- **What drives his production:** 2026 target share 24%, carry share 2%; red zone 2026: 6 targets, 1 carries; snap share trend -6 pp (last 2 vs first 2 games); game total 45.5 (nflverse schedule line), away, roof outdoors, rest 7 days; club QB: Tyson Bagent (attempt leaders by week {'1': 'C.Williams', '2': 'C.Williams', '3': 'C.Keenum', '4': 'T.Bagent'}); teammates with availability doubt: Kyle Monangai.
- **Benchmark FC:** 12.42 (floor 1.62, ceiling 26.82). Our projection: NOT BUILT.
- **Missing model dependencies:** QB-conditioned team volume / shares NOT consumed by the engine (W5-G1); accounting repair pending (D-05) affects all players.
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### Colston Loveland (TE, $4600)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['TE1'].
- **2026:** 4 games, DK average 5.03, last game 11.7 (week 4).
- **What drives his production:** 2026 target share 15%; red zone 2026: 6 targets, 0 carries; snap share trend -1 pp (last 2 vs first 2 games); game total 45.5 (nflverse schedule line), away, roof outdoors, rest 7 days; club QB: Tyson Bagent (attempt leaders by week {'1': 'C.Williams', '2': 'C.Williams', '3': 'C.Keenum', '4': 'T.Bagent'}); teammates with availability doubt: Kyle Monangai.
- **Benchmark FC:** 12.04 (floor 0.0, ceiling 28.64). Our projection: NOT BUILT.
- **Flags:** FC_VS_RECENT_PRODUCTION: FC 12.04 vs 2026 DK avg 5.03
- **Missing model dependencies:** QB-conditioned team volume / shares NOT consumed by the engine (W5-G1); accounting repair pending (D-05) affects all players.
- **Next research action:** decompose FC vs recent production: volume, efficiency or availability assumption.

### Rome Odunze (WR, $4700)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['WR1'].
- **2026:** 4 games, DK average 9.32, last game 15.4 (week 4).
- **What drives his production:** 2026 target share 16%; red zone 2026: 2 targets, 0 carries; snap share trend +21 pp (last 2 vs first 2 games); game total 45.5 (nflverse schedule line), away, roof outdoors, rest 7 days; club QB: Tyson Bagent (attempt leaders by week {'1': 'C.Williams', '2': 'C.Williams', '3': 'C.Keenum', '4': 'T.Bagent'}); teammates with availability doubt: Kyle Monangai.
- **Benchmark FC:** 11.47 (floor 0.0, ceiling 27.07). Our projection: NOT BUILT.
- **Flags:** ROLE_CHANGE: snap share up 21 pp
- **Missing model dependencies:** QB-conditioned team volume / shares NOT consumed by the engine (W5-G1); 4-game pooled usage does not separate a role change from a one-game anomaly (W5-G8); accounting repair pending (D-05) affects all players.
- **Next research action:** read the last two games: is the snap change a role change, an injury exit or game script?.

### Kalif Raymond (WR, $3900)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['WR3'].
- **2026:** 4 games, DK average 12.25, last game 2.6 (week 4).
- **What drives his production:** 2026 target share 20%; red zone 2026: 4 targets, 0 carries; snap share trend +2 pp (last 2 vs first 2 games); game total 45.5 (nflverse schedule line), away, roof outdoors, rest 7 days; club QB: Tyson Bagent (attempt leaders by week {'1': 'C.Williams', '2': 'C.Williams', '3': 'C.Keenum', '4': 'T.Bagent'}); teammates with availability doubt: Kyle Monangai.
- **Benchmark FC:** 7.8 (floor 0.0, ceiling 18.6). Our projection: NOT BUILT.
- **Flags:** FC_VS_RECENT_PRODUCTION: FC 7.8 vs 2026 DK avg 12.25
- **Missing model dependencies:** QB-conditioned team volume / shares NOT consumed by the engine (W5-G1); accounting repair pending (D-05) affects all players.
- **Next research action:** decompose FC vs recent production: volume, efficiency or availability assumption.

### Bears (DST, $2900)
- **Eligibility:** ELIGIBLE_BY_CONSTRUCTION. Practice: not on report. Designation: n/a. Depth: None.
- **What drives his production:** opponent GB QB Jordan Love; opponent QB flags []; game total 45.5.
- **Benchmark FC:** 6.21 (floor 0.0, ceiling 18.01). Our projection: NOT BUILT.
- **Missing model dependencies:** opponent QB identity not consumed by DST model (D-02); turnovers not event-linked (D-05).
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### Cole Kmet (TE, $2600)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['TE2'].
- **2026:** 4 games, DK average 3.7, last game 3.3 (week 4).
- **What drives his production:** 2026 target share 6%; snap share trend +4 pp (last 2 vs first 2 games); game total 45.5 (nflverse schedule line), away, roof outdoors, rest 7 days; club QB: Tyson Bagent (attempt leaders by week {'1': 'C.Williams', '2': 'C.Williams', '3': 'C.Keenum', '4': 'T.Bagent'}); teammates with availability doubt: Kyle Monangai.
- **Benchmark FC:** 5.54 (floor 0.0, ceiling 17.94). Our projection: NOT BUILT.
- **Missing model dependencies:** QB-conditioned team volume / shares NOT consumed by the engine (W5-G1); accounting repair pending (D-05) affects all players.
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### Zavion Thomas (WR, $3000)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['WR4'].
- **2026:** 4 games, DK average 0.28, last game 0.0 (week 4).
- **What drives his production:** 2026 target share 1%; snap share trend +9 pp (last 2 vs first 2 games); game total 45.5 (nflverse schedule line), away, roof outdoors, rest 7 days; club QB: Tyson Bagent (attempt leaders by week {'1': 'C.Williams', '2': 'C.Williams', '3': 'C.Keenum', '4': 'T.Bagent'}); teammates with availability doubt: Kyle Monangai.
- **Benchmark FC:** 0.54 (floor 0.0, ceiling 1.54). Our projection: NOT BUILT.
- **Missing model dependencies:** QB-conditioned team volume / shares NOT consumed by the engine (W5-G1); accounting repair pending (D-05) affects all players.
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

## CIN vs MIA

### JaMarr Chase (WR, $8100)
- **Eligibility:** ELIGIBLE (ACT). Practice: Limited Participation in Practice (Concussion). Designation: NOT_YET_ISSUED (designations are issued Friday; absence is not health). Depth: ['WR1'].
- **2026:** 4 games, DK average 15.05, last game 5.7 (week 4).
- **What drives his production:** 2026 target share 20%; red zone 2026: 4 targets, 0 carries; snap share trend -31 pp (last 2 vs first 2 games); game total 42.5 (nflverse schedule line), away, roof outdoors, rest 7 days; club QB: Joe Burrow (attempt leaders by week {'1': 'J.Burrow', '2': 'J.Burrow', '3': 'J.Burrow', '4': 'J.Burrow'}); teammates with availability doubt: Tee Higgins, Colbie Young, Joe Flacco.
- **Reported [CONFIRMED]:** WR Ja'Marr Chase (concussion, in protocol): DNP Wednesday, limited Thursday. He needs a full practice to clear protocol. (https://www.bengals.com/news/bengals-dolphins-week-5-2026-injury-report)
- **Benchmark FC:** 23.47 (floor 4.57, ceiling 48.67). Our projection: NOT BUILT.
- **Flags:** ROLE_CHANGE: snap share down 31 pp | FC_VS_RECENT_PRODUCTION: FC 23.47 vs 2026 DK avg 15.05
- **Missing model dependencies:** 4-game pooled usage does not separate a role change from a one-game anomaly (W5-G8); practice participation does not change a projection until a designation; no partial-workload model (W5-G4); lower-tail volatility under-stated for high-mean players (D-01).
- **Next research action:** decompose FC vs recent production: volume, efficiency or availability assumption; read the last two games: is the snap change a role change, an injury exit or game script?.

### Joe Burrow (QB, $6900)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['QB1'].
- **2026:** 4 games, DK average 20.91, last game 28.72 (week 4).
- **What drives his production:** red zone 2026: 0 targets, 6 carries; snap share trend +0 pp (last 2 vs first 2 games); game total 42.5 (nflverse schedule line), away, roof outdoors, rest 7 days; club QB: Joe Burrow (attempt leaders by week {'1': 'J.Burrow', '2': 'J.Burrow', '3': 'J.Burrow', '4': 'J.Burrow'}); teammates with availability doubt: Tee Higgins, Colbie Young, Joe Flacco.
- **Reported [REPORTED]:** Joe Burrow has no injury designation for Week 5 (tracker checked Oct 8) and has not missed a game this season. Treat him as the expected starter; I found no explicit team statement. (https://statchasers.com/nfl/players/joe-burrow/injury/)
- **Benchmark FC:** 22.07 (floor 8.72, ceiling 39.87). Our projection: NOT BUILT.
- **Missing model dependencies:** lower-tail volatility under-stated for high-mean players (D-01).
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### Chase Brown (RB, $6900)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['RB1'].
- **2026:** 4 games, DK average 14.5, last game 19.1 (week 4).
- **What drives his production:** 2026 target share 15%, carry share 70%; red zone 2026: 1 targets, 7 carries; snap share trend +4 pp (last 2 vs first 2 games); game total 42.5 (nflverse schedule line), away, roof outdoors, rest 7 days; club QB: Joe Burrow (attempt leaders by week {'1': 'J.Burrow', '2': 'J.Burrow', '3': 'J.Burrow', '4': 'J.Burrow'}); teammates with availability doubt: Tee Higgins, Colbie Young, Joe Flacco.
- **Benchmark FC:** 20.06 (floor 7.16, ceiling 37.26). Our projection: NOT BUILT.
- **Flags:** FC_VS_RECENT_PRODUCTION: FC 20.06 vs 2026 DK avg 14.5
- **Missing model dependencies:** lower-tail volatility under-stated for high-mean players (D-01).
- **Next research action:** decompose FC vs recent production: volume, efficiency or availability assumption.

### Tee Higgins (WR, $7100)
- **Eligibility:** ELIGIBLE (ACT). Practice: Did Not Participate In Practice (Groin, Neck). Designation: NOT_YET_ISSUED (designations are issued Friday; absence is not health). Depth: ['WR2'].
- **2026:** 4 games, DK average 18.52, last game 29.7 (week 4).
- **What drives his production:** 2026 target share 25%; red zone 2026: 2 targets, 0 carries; snap share trend +14 pp (last 2 vs first 2 games); game total 42.5 (nflverse schedule line), away, roof outdoors, rest 7 days; club QB: Joe Burrow (attempt leaders by week {'1': 'J.Burrow', '2': 'J.Burrow', '3': 'J.Burrow', '4': 'J.Burrow'}); teammates with availability doubt: Colbie Young, Joe Flacco.
- **Reported [CONFIRMED]:** WR Tee Higgins (groin/neck; W4 adductor): DNP Wednesday and Thursday, after Zac Taylor had said he would be limited. (https://www.bengals.com/news/bengals-dolphins-week-5-2026-injury-report)
- **Benchmark FC:** 17.14 (floor 2.74, ceiling 36.34). Our projection: NOT BUILT.
- **Flags:** DID_NOT_PRACTICE
- **Missing model dependencies:** practice participation does not change a projection until a designation; no partial-workload model (W5-G4); lower-tail volatility under-stated for high-mean players (D-01).
- **Next research action:** capture Friday designation; if OUT, check redistribution to same-position teammates.

### Bengals (DST, $3500)
- **Eligibility:** ELIGIBLE_BY_CONSTRUCTION. Practice: not on report. Designation: n/a. Depth: None.
- **What drives his production:** opponent MIA QB Malik Willis; opponent QB flags []; game total 42.5.
- **Benchmark FC:** 9.63 (floor 1.98, ceiling 19.83). Our projection: NOT BUILT.
- **Missing model dependencies:** opponent QB identity not consumed by DST model (D-02); turnovers not event-linked (D-05).
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### Mike Gesicki (TE, $4100)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['TE1'].
- **2026:** 4 games, DK average 11.12, last game 13.0 (week 4).
- **What drives his production:** 2026 target share 10%; red zone 2026: 3 targets, 0 carries; snap share trend +22 pp (last 2 vs first 2 games); game total 42.5 (nflverse schedule line), away, roof outdoors, rest 7 days; club QB: Joe Burrow (attempt leaders by week {'1': 'J.Burrow', '2': 'J.Burrow', '3': 'J.Burrow', '4': 'J.Burrow'}); teammates with availability doubt: Tee Higgins, Colbie Young, Joe Flacco.
- **Benchmark FC:** 8.55 (floor 0.0, ceiling 22.15). Our projection: NOT BUILT.
- **Flags:** ROLE_CHANGE: snap share up 22 pp
- **Missing model dependencies:** 4-game pooled usage does not separate a role change from a one-game anomaly (W5-G8); accounting repair pending (D-05) affects all players.
- **Next research action:** read the last two games: is the snap change a role change, an injury exit or game script?.

### Dohnte Meyers (WR, $3500)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['WR4'].
- **2026:** 4 games, DK average 6.22, last game 15.2 (week 4).
- **What drives his production:** 2026 target share 9%, carry share 1%; snap share trend +56 pp (last 2 vs first 2 games); game total 42.5 (nflverse schedule line), away, roof outdoors, rest 7 days; club QB: Joe Burrow (attempt leaders by week {'1': 'J.Burrow', '2': 'J.Burrow', '3': 'J.Burrow', '4': 'J.Burrow'}); teammates with availability doubt: Tee Higgins, Colbie Young, Joe Flacco.
- **Reported [REPORTED]:** WRs Colbie Young and Andrei Iosivas are also out injured; Dohnte Meyers and Mitchell Tinsley are the healthy WRs. (https://www.newsweek.com/sports/nfl/bengals-get-concerning-injury-updates-on-jamarr-chase-and-tee-higgins-12526631)
- **Benchmark FC:** 6.14 (floor 0.0, ceiling 17.34). Our projection: NOT BUILT.
- **Flags:** ROLE_CHANGE: snap share up 56 pp
- **Missing model dependencies:** 4-game pooled usage does not separate a role change from a one-game anomaly (W5-G8); accounting repair pending (D-05) affects all players.
- **Next research action:** read the last two games: is the snap change a role change, an injury exit or game script?.

### Drew Sample (TE, $2600)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['TE2'].
- **2026:** 4 games, DK average 1.48, last game 0.0 (week 4).
- **What drives his production:** 2026 target share 4%; red zone 2026: 1 targets, 0 carries; snap share trend -24 pp (last 2 vs first 2 games); game total 42.5 (nflverse schedule line), away, roof outdoors, rest 7 days; club QB: Joe Burrow (attempt leaders by week {'1': 'J.Burrow', '2': 'J.Burrow', '3': 'J.Burrow', '4': 'J.Burrow'}); teammates with availability doubt: Tee Higgins, Colbie Young, Joe Flacco.
- **Benchmark FC:** 3.67 (floor 0.0, ceiling 10.07). Our projection: NOT BUILT.
- **Flags:** ROLE_CHANGE: snap share down 24 pp
- **Missing model dependencies:** 4-game pooled usage does not separate a role change from a one-game anomaly (W5-G8); accounting repair pending (D-05) affects all players.
- **Next research action:** read the last two games: is the snap change a role change, an injury exit or game script?.

### Samaje Perine (RB, $4400)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['RB2'].
- **2026:** 4 games, DK average 3.57, last game 0.7 (week 4).
- **What drives his production:** 2026 target share 6%, carry share 16%; red zone 2026: 0 targets, 3 carries; snap share trend +0 pp (last 2 vs first 2 games); game total 42.5 (nflverse schedule line), away, roof outdoors, rest 7 days; club QB: Joe Burrow (attempt leaders by week {'1': 'J.Burrow', '2': 'J.Burrow', '3': 'J.Burrow', '4': 'J.Burrow'}); teammates with availability doubt: Tee Higgins, Colbie Young, Joe Flacco.
- **Benchmark FC:** 3.3 (floor 0.0, ceiling 14.9). Our projection: NOT BUILT.
- **Missing model dependencies:** accounting repair pending (D-05) affects all players.
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### Colbie Young (WR, $3600)
- **Eligibility:** ELIGIBLE (ACT). Practice: Full Participation in Practice (Knee). Designation: NOT_YET_ISSUED (designations are issued Friday; absence is not health). Depth: ['WR3'].
- **2026:** 3 games, DK average 0.97, last game 1.2 (week 3).
- **What drives his production:** 2026 target share 2%; snap share trend -6 pp (last 2 vs first 2 games); game total 42.5 (nflverse schedule line), away, roof outdoors, rest 7 days; club QB: Joe Burrow (attempt leaders by week {'1': 'J.Burrow', '2': 'J.Burrow', '3': 'J.Burrow', '4': 'J.Burrow'}); teammates with availability doubt: Tee Higgins, Joe Flacco.
- **Reported [REPORTED]:** WRs Colbie Young and Andrei Iosivas are also out injured; Dohnte Meyers and Mitchell Tinsley are the healthy WRs. (https://www.newsweek.com/sports/nfl/bengals-get-concerning-injury-updates-on-jamarr-chase-and-tee-higgins-12526631)
- **Benchmark FC:** 2.06 (floor 1.76, ceiling 2.46). Our projection: NOT BUILT.
- **Flags:** MISSED_LAST_GAME: no participation in week 4
- **Missing model dependencies:** accounting repair pending (D-05) affects all players.
- **Next research action:** verify return status and any snap limit; compare to pre-injury usage.

## CLE vs NYJ

### Deshaun Watson (QB, $5100)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['QB1'].
- **2026:** 4 games, DK average 17.48, last game 14.92 (week 4).
- **What drives his production:** red zone 2026: 0 targets, 5 carries; snap share trend -0 pp (last 2 vs first 2 games); game total 39.5 (nflverse schedule line), away, roof outdoors, rest 10 days; club QB: Deshaun Watson (attempt leaders by week {'1': 'D.Watson', '2': 'D.Watson', '3': 'D.Watson', '4': 'D.Watson'}); teammates with availability doubt: Shedeur Sanders, Tylan Wallace.
- **Reported [REPORTED]:** Deshaun Watson is the expected starter. He won the job over Shedeur Sanders in August and has held it since W1 (115 att, 855 yds, 6 TD, 2 INT; team 3-1). He took first-team reps Oct 7. Monken said starting QB isn't a week-to-week issue. (https://www.forbes.com/sites/johncassillo/2026/10/08/nfl-week-5-storylines-can-browns-match-best-start-since-1999-return/)
- **Benchmark FC:** 20.94 (floor 6.84, ceiling 39.74). Our projection: NOT BUILT.
- **Missing model dependencies:** lower-tail volatility under-stated for high-mean players (D-01).
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### Harold Fannin Jr. (TE, $4400)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['TE1'].
- **2026:** 4 games, DK average 12.57, last game 11.7 (week 4).
- **What drives his production:** 2026 target share 20%; red zone 2026: 3 targets, 0 carries; snap share trend +4 pp (last 2 vs first 2 games); game total 39.5 (nflverse schedule line), away, roof outdoors, rest 10 days; club QB: Deshaun Watson (attempt leaders by week {'1': 'D.Watson', '2': 'D.Watson', '3': 'D.Watson', '4': 'D.Watson'}); teammates with availability doubt: Shedeur Sanders, Tylan Wallace.
- **Reported [REPORTED]:** DNP Wed and Thu: DT Mason Graham (knee/ankle), DT Mike Hall Jr. (ankle). DT Kalia Davis (quad, off IR) LP/DNP. DE Derek Barnett (ankle) DNP/LP. DNP Thursday: G Teven Jenkins (back), WR Tylan Wallace (knee). Full Thursday: QB Dillon Gabriel (back), C Elgton Jenkins (concussion), S Grant Delpit (shoulder). No Week 5 listing found for RB Quinshon Judkins. (https://247sports.com/nfl/cleveland-browns/article/browns-injury-report-mason-graham-mike-hall-jr-update-before-jets-291014889/)
- **Benchmark FC:** 14.3 (floor 3.95, ceiling 28.1). Our projection: NOT BUILT.
- **Missing model dependencies:** accounting repair pending (D-05) affects all players.
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### Denzel Boston (WR, $5200)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['WR1'].
- **2026:** 4 games, DK average 13.85, last game 12.9 (week 4).
- **What drives his production:** 2026 target share 19%; red zone 2026: 3 targets, 0 carries; snap share trend -0 pp (last 2 vs first 2 games); game total 39.5 (nflverse schedule line), away, roof outdoors, rest 10 days; club QB: Deshaun Watson (attempt leaders by week {'1': 'D.Watson', '2': 'D.Watson', '3': 'D.Watson', '4': 'D.Watson'}); teammates with availability doubt: Shedeur Sanders, Tylan Wallace.
- **Benchmark FC:** 12.1 (floor 5.5, ceiling 20.9). Our projection: NOT BUILT.
- **Missing model dependencies:** accounting repair pending (D-05) affects all players.
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### Quinshon Judkins (RB, $5700)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['RB1'].
- **2026:** 4 games, DK average 12.08, last game 21.6 (week 4).
- **What drives his production:** 2026 target share 13%, carry share 57%; red zone 2026: 3 targets, 9 carries; snap share trend -8 pp (last 2 vs first 2 games); game total 39.5 (nflverse schedule line), away, roof outdoors, rest 10 days; club QB: Deshaun Watson (attempt leaders by week {'1': 'D.Watson', '2': 'D.Watson', '3': 'D.Watson', '4': 'D.Watson'}); teammates with availability doubt: Shedeur Sanders, Tylan Wallace.
- **Reported [REPORTED]:** DNP Wed and Thu: DT Mason Graham (knee/ankle), DT Mike Hall Jr. (ankle). DT Kalia Davis (quad, off IR) LP/DNP. DE Derek Barnett (ankle) DNP/LP. DNP Thursday: G Teven Jenkins (back), WR Tylan Wallace (knee). Full Thursday: QB Dillon Gabriel (back), C Elgton Jenkins (concussion), S Grant Delpit (shoulder). No Week 5 listing found for RB Quinshon Judkins. (https://247sports.com/nfl/cleveland-browns/article/browns-injury-report-mason-graham-mike-hall-jr-update-before-jets-291014889/)
- **Benchmark FC:** 10.57 (floor 0.97, ceiling 23.37). Our projection: NOT BUILT.
- **Missing model dependencies:** accounting repair pending (D-05) affects all players.
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### KC Concepcion (WR, $4200)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['WR2'].
- **2026:** 4 games, DK average 7.82, last game 11.4 (week 4).
- **What drives his production:** 2026 target share 24%, carry share 4%; red zone 2026: 3 targets, 0 carries; snap share trend +22 pp (last 2 vs first 2 games); game total 39.5 (nflverse schedule line), away, roof outdoors, rest 10 days; club QB: Deshaun Watson (attempt leaders by week {'1': 'D.Watson', '2': 'D.Watson', '3': 'D.Watson', '4': 'D.Watson'}); teammates with availability doubt: Shedeur Sanders, Tylan Wallace.
- **Benchmark FC:** 10.32 (floor 5.67, ceiling 16.52). Our projection: NOT BUILT.
- **Flags:** ROLE_CHANGE: snap share up 22 pp
- **Missing model dependencies:** 4-game pooled usage does not separate a role change from a one-game anomaly (W5-G8); accounting repair pending (D-05) affects all players.
- **Next research action:** read the last two games: is the snap change a role change, an injury exit or game script?.

### Jerry Jeudy (WR, $3700)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['WR3'].
- **2026:** 4 games, DK average 2.8, last game 6.6 (week 4).
- **What drives his production:** 2026 target share 8%; snap share trend -16 pp (last 2 vs first 2 games); game total 39.5 (nflverse schedule line), away, roof outdoors, rest 10 days; club QB: Deshaun Watson (attempt leaders by week {'1': 'D.Watson', '2': 'D.Watson', '3': 'D.Watson', '4': 'D.Watson'}); teammates with availability doubt: Shedeur Sanders, Tylan Wallace.
- **Benchmark FC:** 8.44 (floor 0.0, ceiling 24.24). Our projection: NOT BUILT.
- **Flags:** ROLE_CHANGE: snap share down 16 pp | FC_VS_RECENT_PRODUCTION: FC 8.44 vs 2026 DK avg 2.8
- **Missing model dependencies:** 4-game pooled usage does not separate a role change from a one-game anomaly (W5-G8); accounting repair pending (D-05) affects all players.
- **Next research action:** decompose FC vs recent production: volume, efficiency or availability assumption; read the last two games: is the snap change a role change, an injury exit or game script?.

### Raheim Sanders (RB, $4700)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['RB2'].
- **2026:** 4 games, DK average 5.1, last game 3.6 (week 4).
- **What drives his production:** 2026 target share 10%, carry share 6%; snap share trend +12 pp (last 2 vs first 2 games); game total 39.5 (nflverse schedule line), away, roof outdoors, rest 10 days; club QB: Deshaun Watson (attempt leaders by week {'1': 'D.Watson', '2': 'D.Watson', '3': 'D.Watson', '4': 'D.Watson'}); teammates with availability doubt: Shedeur Sanders, Tylan Wallace.
- **Reported [REPORTED]:** Deshaun Watson is the expected starter. He won the job over Shedeur Sanders in August and has held it since W1 (115 att, 855 yds, 6 TD, 2 INT; team 3-1). He took first-team reps Oct 7. Monken said starting QB isn't a week-to-week issue. (https://www.forbes.com/sites/johncassillo/2026/10/08/nfl-week-5-storylines-can-browns-match-best-start-since-1999-return/)
- **Benchmark FC:** 5.37 (floor 2.37, ceiling 9.37). Our projection: NOT BUILT.
- **Missing model dependencies:** accounting repair pending (D-05) affects all players.
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### Browns (DST, $2800)
- **Eligibility:** ELIGIBLE_BY_CONSTRUCTION. Practice: not on report. Designation: n/a. Depth: None.
- **What drives his production:** opponent NYJ QB Geno Smith; opponent QB flags []; game total 39.5.
- **Benchmark FC:** 5.09 (floor 0.0, ceiling 16.29). Our projection: NOT BUILT.
- **Missing model dependencies:** opponent QB identity not consumed by DST model (D-02); turnovers not event-linked (D-05).
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### Isaiah Bond (WR, $3000)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['WR4'].
- **2026:** 4 games, DK average 0.8, last game 1.2 (week 4).
- **What drives his production:** 2026 target share 2%; snap share trend -2 pp (last 2 vs first 2 games); game total 39.5 (nflverse schedule line), away, roof outdoors, rest 10 days; club QB: Deshaun Watson (attempt leaders by week {'1': 'D.Watson', '2': 'D.Watson', '3': 'D.Watson', '4': 'D.Watson'}); teammates with availability doubt: Shedeur Sanders, Tylan Wallace.
- **Benchmark FC:** 2.97 (floor 0.0, ceiling 8.97). Our projection: NOT BUILT.
- **Missing model dependencies:** accounting repair pending (D-05) affects all players.
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

## GB vs CHI

### Christian Watson (WR, $6400)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['WR1'].
- **2026:** 4 games, DK average 20.03, last game 7.7 (week 4).
- **What drives his production:** 2026 target share 22%; red zone 2026: 7 targets, 0 carries; snap share trend -9 pp (last 2 vs first 2 games); game total 45.5 (nflverse schedule line), home, roof outdoors, rest 7 days; club QB: Jordan Love (attempt leaders by week {'1': 'J.Love', '2': 'J.Love', '3': 'J.Love', '4': 'J.Love'}); teammates with availability doubt: Chris Brooks.
- **Benchmark FC:** 17.55 (floor 4.05, ceiling 35.55). Our projection: NOT BUILT.
- **Missing model dependencies:** lower-tail volatility under-stated for high-mean players (D-01).
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### Jordan Love (QB, $5700)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['QB1'].
- **2026:** 4 games, DK average 18.71, last game 14.08 (week 4).
- **What drives his production:** red zone 2026: 0 targets, 1 carries; snap share trend +0 pp (last 2 vs first 2 games); game total 45.5 (nflverse schedule line), home, roof outdoors, rest 7 days; club QB: Jordan Love (attempt leaders by week {'1': 'J.Love', '2': 'J.Love', '3': 'J.Love', '4': 'J.Love'}); teammates with availability doubt: Chris Brooks.
- **Reported [REPORTED]:** No 2026 result shows Jordan Love injured, absent from a Week 5 report, or replaced. A Sept 27 tracker showed no designation for him. I found no source confirming he started W4 (at TB, Oct 4). (https://legionreport.com/is-jordan-love-playing/)
- **Benchmark FC:** 17.03 (floor 4.43, ceiling 33.83). Our projection: NOT BUILT.
- **Missing model dependencies:** lower-tail volatility under-stated for high-mean players (D-01).
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### Tucker Kraft (TE, $4700)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['TE1'].
- **2026:** 4 games, DK average 9.03, last game 16.5 (week 4).
- **What drives his production:** 2026 target share 16%, carry share 1%; red zone 2026: 4 targets, 1 carries; snap share trend +2 pp (last 2 vs first 2 games); game total 45.5 (nflverse schedule line), home, roof outdoors, rest 7 days; club QB: Jordan Love (attempt leaders by week {'1': 'J.Love', '2': 'J.Love', '3': 'J.Love', '4': 'J.Love'}); teammates with availability doubt: Chris Brooks.
- **Benchmark FC:** 13.06 (floor 1.81, ceiling 28.06). Our projection: NOT BUILT.
- **Flags:** FC_VS_RECENT_PRODUCTION: FC 13.06 vs 2026 DK avg 9.03
- **Missing model dependencies:** accounting repair pending (D-05) affects all players.
- **Next research action:** decompose FC vs recent production: volume, efficiency or availability assumption.

### MarShawn Lloyd (RB, $4800)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['RB1'].
- **2026:** 4 games, DK average 6.75, last game 9.9 (week 4).
- **What drives his production:** 2026 target share 8%, carry share 42%; red zone 2026: 3 targets, 9 carries; snap share trend +4 pp (last 2 vs first 2 games); game total 45.5 (nflverse schedule line), home, roof outdoors, rest 7 days; club QB: Jordan Love (attempt leaders by week {'1': 'J.Love', '2': 'J.Love', '3': 'J.Love', '4': 'J.Love'}); teammates with availability doubt: Chris Brooks.
- **Benchmark FC:** 10.63 (floor 5.98, ceiling 16.83). Our projection: NOT BUILT.
- **Flags:** FC_VS_RECENT_PRODUCTION: FC 10.63 vs 2026 DK avg 6.75
- **Missing model dependencies:** accounting repair pending (D-05) affects all players.
- **Next research action:** decompose FC vs recent production: volume, efficiency or availability assumption.

### Matthew Golden (WR, $5700)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['WR2'].
- **2026:** 4 games, DK average 15.25, last game 11.7 (week 4).
- **What drives his production:** 2026 target share 24%, carry share 1%; red zone 2026: 5 targets, 0 carries; snap share trend +1 pp (last 2 vs first 2 games); game total 45.5 (nflverse schedule line), home, roof outdoors, rest 7 days; club QB: Jordan Love (attempt leaders by week {'1': 'J.Love', '2': 'J.Love', '3': 'J.Love', '4': 'J.Love'}); teammates with availability doubt: Chris Brooks.
- **Benchmark FC:** 8.3 (floor 0.0, ceiling 20.7). Our projection: NOT BUILT.
- **Flags:** FC_VS_RECENT_PRODUCTION: FC 8.3 vs 2026 DK avg 15.25
- **Missing model dependencies:** accounting repair pending (D-05) affects all players.
- **Next research action:** decompose FC vs recent production: volume, efficiency or availability assumption.

### Jonnu Smith (TE, $2700)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['TE2'].
- **2026:** 4 games, DK average 3.38, last game 2.9 (week 4).
- **What drives his production:** 2026 target share 4%; red zone 2026: 1 targets, 0 carries; snap share trend -7 pp (last 2 vs first 2 games); game total 45.5 (nflverse schedule line), home, roof outdoors, rest 7 days; club QB: Jordan Love (attempt leaders by week {'1': 'J.Love', '2': 'J.Love', '3': 'J.Love', '4': 'J.Love'}); teammates with availability doubt: Chris Brooks.
- **Benchmark FC:** 4.92 (floor 0.0, ceiling 17.32). Our projection: NOT BUILT.
- **Missing model dependencies:** accounting repair pending (D-05) affects all players.
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### Packers (DST, $2700)
- **Eligibility:** ELIGIBLE_BY_CONSTRUCTION. Practice: not on report. Designation: n/a. Depth: None.
- **What drives his production:** opponent CHI QB Tyson Bagent; opponent QB flags ['QB_REGIME_CHANGE: listed starter is not the dominant passer of the modelling window', 'THIN_STARTER_EVIDENCE: 1 2026 start(s) by the listed starter', 'QB_CHURN: 3 different attempt leaders in 4 games']; game total 45.5.
- **Benchmark FC:** 2.77 (floor 0.0, ceiling 13.37). Our projection: NOT BUILT.
- **Missing model dependencies:** opponent QB identity not consumed by DST model (D-02); turnovers not event-linked (D-05).
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### Kaleb Johnson (RB, $4600)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['RB2'].
- **2026:** 4 games, DK average 2.25, last game 3.2 (week 4).
- **What drives his production:** 2026 target share 2%, carry share 30%; red zone 2026: 0 targets, 2 carries; snap share trend +18 pp (last 2 vs first 2 games); game total 45.5 (nflverse schedule line), home, roof outdoors, rest 7 days; club QB: Jordan Love (attempt leaders by week {'1': 'J.Love', '2': 'J.Love', '3': 'J.Love', '4': 'J.Love'}); teammates with availability doubt: Chris Brooks.
- **Benchmark FC:** 2.13 (floor 0.33, ceiling 4.53). Our projection: NOT BUILT.
- **Flags:** ROLE_CHANGE: snap share up 18 pp
- **Missing model dependencies:** 4-game pooled usage does not separate a role change from a one-game anomaly (W5-G8); accounting repair pending (D-05) affects all players.
- **Next research action:** read the last two games: is the snap change a role change, an injury exit or game script?.

### Skyy Moore (WR, $3200)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['WR3'].
- **2026:** 4 games, DK average 2.38, last game 0.8 (week 4).
- **What drives his production:** 2026 target share 8%; red zone 2026: 4 targets, 0 carries; snap share trend +24 pp (last 2 vs first 2 games); game total 45.5 (nflverse schedule line), home, roof outdoors, rest 7 days; club QB: Jordan Love (attempt leaders by week {'1': 'J.Love', '2': 'J.Love', '3': 'J.Love', '4': 'J.Love'}); teammates with availability doubt: Chris Brooks.
- **Benchmark FC:** 1.52 (floor 0.0, ceiling 7.92). Our projection: NOT BUILT.
- **Flags:** ROLE_CHANGE: snap share up 24 pp
- **Missing model dependencies:** 4-game pooled usage does not separate a role change from a one-game anomaly (W5-G8); accounting repair pending (D-05) affects all players.
- **Next research action:** read the last two games: is the snap change a role change, an injury exit or game script?.

### Bo Melton (WR, $3000)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['WR4'].
- **2026:** 4 games, DK average 0.5, last game 0.0 (week 4).
- **What drives his production:** 2026 target share 3%; snap share trend +12 pp (last 2 vs first 2 games); game total 45.5 (nflverse schedule line), home, roof outdoors, rest 7 days; club QB: Jordan Love (attempt leaders by week {'1': 'J.Love', '2': 'J.Love', '3': 'J.Love', '4': 'J.Love'}); teammates with availability doubt: Chris Brooks.
- **Benchmark FC:** 1.18 (floor 0.0, ceiling 12.98). Our projection: NOT BUILT.
- **Missing model dependencies:** accounting repair pending (D-05) affects all players.
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

## HOU vs TEN

### Nico Collins (WR, $7500)
- **Eligibility:** ELIGIBLE (ACT). Practice: Limited Participation in Practice (Not injury related - resting player). Designation: NOT_YET_ISSUED (designations are issued Friday; absence is not health). Depth: ['WR1'].
- **2026:** 2 games, DK average 27.5, last game 33.8 (week 4).
- **What drives his production:** 2026 target share 29%, carry share 2%; red zone 2026: 3 targets, 0 carries; game total 37.5 (nflverse schedule line), away, roof outdoors, rest 7 days; club QB: C.J. Stroud (attempt leaders by week {'1': 'C.Stroud', '2': 'C.Stroud', '3': 'C.Stroud', '4': 'C.Stroud'}); teammates with availability doubt: Marlin Klein.
- **Reported [REPORTED]:** WR Nico Collins: limited Wednesday (NIR rest). He missed 2 games with a hamstring and returned in W4. WR Tank Dell (knee) LP/LP. Edge Will Anderson Jr. (ankle) DNP to LP. LB Azeez Al-Shaair (groin) LP/LP. Jadeveon Clowney, Logan Hall, Kayden McDonald, Braden Smith LP to FP. OL Aireontae Ersery, Blake Fisher, Ed Ingram DNP Thursday (illness). Texans Wire lists rest designations for Collins, Schultz and Trent Brown not shown in the team tables. (https://athlonsports.com/nfl/texans-titans-thursday-injury-report)
- **Benchmark FC:** 21.28 (floor 7.18, ceiling 40.08). Our projection: NOT BUILT.
- **Missing model dependencies:** practice participation does not change a projection until a designation; no partial-workload model (W5-G4); lower-tail volatility under-stated for high-mean players (D-01).
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### C.J. Stroud (QB, $5900)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['QB1'].
- **2026:** 4 games, DK average 19.06, last game 26.08 (week 4).
- **What drives his production:** snap share trend +0 pp (last 2 vs first 2 games); game total 37.5 (nflverse schedule line), away, roof outdoors, rest 7 days; club QB: C.J. Stroud (attempt leaders by week {'1': 'C.Stroud', '2': 'C.Stroud', '3': 'C.Stroud', '4': 'C.Stroud'}); teammates with availability doubt: Marlin Klein.
- **Reported [REPORTED]:** C.J. Stroud is on no Week 5 report. W4 vs DAL: 21/31, 347 yds, 2 TD; no INTs this season; 1,141 yds through 4 games. I found no QB change. (https://www.sharpfootballanalysis.com/fantasy/texans-titans-week-5-fantasy-football-preview-nfl-worksheet-rich-hribar-2026/amp/)
- **Benchmark FC:** 19.71 (floor 8.31, ceiling 34.91). Our projection: NOT BUILT.
- **Missing model dependencies:** lower-tail volatility under-stated for high-mean players (D-01).
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### Dalton Schultz (TE, $4000)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['TE1'].
- **2026:** 4 games, DK average 11.35, last game 2.9 (week 4).
- **What drives his production:** 2026 target share 17%; red zone 2026: 2 targets, 0 carries; snap share trend -8 pp (last 2 vs first 2 games); game total 37.5 (nflverse schedule line), away, roof outdoors, rest 7 days; club QB: C.J. Stroud (attempt leaders by week {'1': 'C.Stroud', '2': 'C.Stroud', '3': 'C.Stroud', '4': 'C.Stroud'}); teammates with availability doubt: Marlin Klein.
- **Reported [REPORTED]:** WR Nico Collins: limited Wednesday (NIR rest). He missed 2 games with a hamstring and returned in W4. WR Tank Dell (knee) LP/LP. Edge Will Anderson Jr. (ankle) DNP to LP. LB Azeez Al-Shaair (groin) LP/LP. Jadeveon Clowney, Logan Hall, Kayden McDonald, Braden Smith LP to FP. OL Aireontae Ersery, Blake Fisher, Ed Ingram DNP Thursday (illness). Texans Wire lists rest designations for Collins, Schultz and Trent Brown not shown in the team tables. (https://athlonsports.com/nfl/texans-titans-thursday-injury-report)
- **Benchmark FC:** 13.4 (floor 3.35, ceiling 26.8). Our projection: NOT BUILT.
- **Missing model dependencies:** accounting repair pending (D-05) affects all players.
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### Woody Marks (RB, $4800)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['RB2'].
- **2026:** 4 games, DK average 7.7, last game 8.2 (week 4).
- **What drives his production:** 2026 target share 6%, carry share 32%; red zone 2026: 2 targets, 4 carries; snap share trend -9 pp (last 2 vs first 2 games); game total 37.5 (nflverse schedule line), away, roof outdoors, rest 7 days; club QB: C.J. Stroud (attempt leaders by week {'1': 'C.Stroud', '2': 'C.Stroud', '3': 'C.Stroud', '4': 'C.Stroud'}); teammates with availability doubt: Marlin Klein.
- **Benchmark FC:** 10.43 (floor 1.28, ceiling 22.63). Our projection: NOT BUILT.
- **Missing model dependencies:** accounting repair pending (D-05) affects all players.
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### Texans (DST, $3400)
- **Eligibility:** ELIGIBLE_BY_CONSTRUCTION. Practice: not on report. Designation: n/a. Depth: None.
- **What drives his production:** opponent TEN QB Cam Ward; opponent QB flags []; game total 37.5.
- **Reported [REPORTED]:** WR Nico Collins: limited Wednesday (NIR rest). He missed 2 games with a hamstring and returned in W4. WR Tank Dell (knee) LP/LP. Edge Will Anderson Jr. (ankle) DNP to LP. LB Azeez Al-Shaair (groin) LP/LP. Jadeveon Clowney, Logan Hall, Kayden McDonald, Braden Smith LP to FP. OL Aireontae Ersery, Blake Fisher, Ed Ingram DNP Thursday (illness). Texans Wire lists rest designations for Collins, Schultz and Trent Brown not shown in the team tables. (https://athlonsports.com/nfl/texans-titans-thursday-injury-report)
- **Benchmark FC:** 9.46 (floor 0.46, ceiling 21.46). Our projection: NOT BUILT.
- **Missing model dependencies:** opponent QB identity not consumed by DST model (D-02); turnovers not event-linked (D-05).
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### Xavier Hutchinson (WR, $4000)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['WR2'].
- **2026:** 4 games, DK average 7.25, last game 7.6 (week 4).
- **What drives his production:** 2026 target share 19%, carry share 2%; red zone 2026: 1 targets, 0 carries; snap share trend -26 pp (last 2 vs first 2 games); game total 37.5 (nflverse schedule line), away, roof outdoors, rest 7 days; club QB: C.J. Stroud (attempt leaders by week {'1': 'C.Stroud', '2': 'C.Stroud', '3': 'C.Stroud', '4': 'C.Stroud'}); teammates with availability doubt: Marlin Klein.
- **Benchmark FC:** 7.74 (floor 1.74, ceiling 15.74). Our projection: NOT BUILT.
- **Flags:** ROLE_CHANGE: snap share down 26 pp
- **Missing model dependencies:** 4-game pooled usage does not separate a role change from a one-game anomaly (W5-G8); accounting repair pending (D-05) affects all players.
- **Next research action:** read the last two games: is the snap change a role change, an injury exit or game script?.

### David Montgomery (RB, $5800)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['RB1'].
- **2026:** 4 games, DK average 11.1, last game 4.3 (week 4).
- **What drives his production:** 2026 target share 5%, carry share 50%; red zone 2026: 1 targets, 8 carries; snap share trend +9 pp (last 2 vs first 2 games); game total 37.5 (nflverse schedule line), away, roof outdoors, rest 7 days; club QB: C.J. Stroud (attempt leaders by week {'1': 'C.Stroud', '2': 'C.Stroud', '3': 'C.Stroud', '4': 'C.Stroud'}); teammates with availability doubt: Marlin Klein.
- **Benchmark FC:** 7.49 (floor 0.0, ceiling 23.09). Our projection: NOT BUILT.
- **Missing model dependencies:** accounting repair pending (D-05) affects all players.
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### Kayshon Boutte (WR, $3900)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['WR3'].
- **2026:** 4 games, DK average 5.12, last game 6.6 (week 4).
- **What drives his production:** 2026 target share 10%; red zone 2026: 2 targets, 0 carries; snap share trend +6 pp (last 2 vs first 2 games); game total 37.5 (nflverse schedule line), away, roof outdoors, rest 7 days; club QB: C.J. Stroud (attempt leaders by week {'1': 'C.Stroud', '2': 'C.Stroud', '3': 'C.Stroud', '4': 'C.Stroud'}); teammates with availability doubt: Marlin Klein.
- **Benchmark FC:** 6.71 (floor 4.31, ceiling 9.91). Our projection: NOT BUILT.
- **Missing model dependencies:** accounting repair pending (D-05) affects all players.
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### Jaylin Noel (WR, $3200)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['WR4'].
- **2026:** 4 games, DK average 7.28, last game 11.9 (week 4).
- **What drives his production:** 2026 target share 9%, carry share 4%; snap share trend -1 pp (last 2 vs first 2 games); game total 37.5 (nflverse schedule line), away, roof outdoors, rest 7 days; club QB: C.J. Stroud (attempt leaders by week {'1': 'C.Stroud', '2': 'C.Stroud', '3': 'C.Stroud', '4': 'C.Stroud'}); teammates with availability doubt: Marlin Klein.
- **Benchmark FC:** 5.91 (floor 0.0, ceiling 15.11). Our projection: NOT BUILT.
- **Missing model dependencies:** accounting repair pending (D-05) affects all players.
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### Foster Moreau (TE, $2500)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['TE2'].
- **2026:** 4 games, DK average 4.68, last game 1.1 (week 4).
- **What drives his production:** 2026 target share 7%; red zone 2026: 2 targets, 0 carries; snap share trend +10 pp (last 2 vs first 2 games); game total 37.5 (nflverse schedule line), away, roof outdoors, rest 7 days; club QB: C.J. Stroud (attempt leaders by week {'1': 'C.Stroud', '2': 'C.Stroud', '3': 'C.Stroud', '4': 'C.Stroud'}); teammates with availability doubt: Marlin Klein.
- **Benchmark FC:** 4.96 (floor 0.0, ceiling 13.36). Our projection: NOT BUILT.
- **Missing model dependencies:** accounting repair pending (D-05) affects all players.
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

## IND vs PIT

### Jonathan Taylor (RB, $7800)
- **Eligibility:** ELIGIBLE (ACT). Practice: Full Participation in Practice (Not injury related - resting player). Designation: NOT_YET_ISSUED (designations are issued Friday; absence is not health). Depth: ['RB1'].
- **2026:** 4 games, DK average 21.8, last game 22.7 (week 4).
- **What drives his production:** 2026 target share 12%, carry share 78%; red zone 2026: 1 targets, 16 carries; snap share trend -14 pp (last 2 vs first 2 games); game total 44.5 (nflverse schedule line), away, roof outdoors, rest 7 days; club QB: Daniel Jones (attempt leaders by week {'1': 'D.Jones', '2': 'D.Jones', '3': 'D.Jones', '4': 'D.Jones'}); teammates with availability doubt: Keenan Allen, Ashton Dulin.
- **Reported [CONFLICTING]:** RB Jonathan Taylor (NIR/rest): full Thursday. His Wednesday status conflicts: DNP rest (one source) vs limited (another). (https://steelersdepot.com/2026/10/colts-week-5-thursday-injury-report-keenan-allen-remains-limited-starting-center-upgraded/)
- **Benchmark FC:** 20.96 (floor 4.46, ceiling 42.96). Our projection: NOT BUILT.
- **Missing model dependencies:** lower-tail volatility under-stated for high-mean players (D-01).
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### Daniel Jones (QB, $5000)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['QB1'].
- **2026:** 4 games, DK average 10.81, last game 9.92 (week 4).
- **What drives his production:** red zone 2026: 0 targets, 3 carries; snap share trend +0 pp (last 2 vs first 2 games); game total 44.5 (nflverse schedule line), away, roof outdoors, rest 7 days; club QB: Daniel Jones (attempt leaders by week {'1': 'D.Jones', '2': 'D.Jones', '3': 'D.Jones', '4': 'D.Jones'}); teammates with availability doubt: Keenan Allen, Ashton Dulin.
- **Reported [REPORTED]:** Daniel Jones is the expected starter: he gave the Week 5 press conference and is not on the injury report. He is back from a December Achilles tear; 7 turnovers this season; W4 in London: 34 attempts, 143 yds (W 30-13 vs WAS). No explicit team confirmation found. (https://www.colts.com/video/daniel-jones-colts-vs-steelers-week-5)
- **Benchmark FC:** 14.89 (floor 2.14, ceiling 31.89). Our projection: NOT BUILT.
- **Flags:** FC_VS_RECENT_PRODUCTION: FC 14.89 vs 2026 DK avg 10.81
- **Missing model dependencies:** accounting repair pending (D-05) affects all players.
- **Next research action:** decompose FC vs recent production: volume, efficiency or availability assumption.

### Keenan Allen (WR, $4300)
- **Eligibility:** ELIGIBLE (ACT). Practice: Limited Participation in Practice (Not injury related - resting player, Groin). Designation: NOT_YET_ISSUED (designations are issued Friday; absence is not health). Depth: ['WR2'].
- **2026:** 3 games, DK average 9.67, last game 18.3 (week 3).
- **What drives his production:** 2026 target share 21%; red zone 2026: 3 targets, 0 carries; snap share trend +3 pp (last 2 vs first 2 games); game total 44.5 (nflverse schedule line), away, roof outdoors, rest 7 days; club QB: Daniel Jones (attempt leaders by week {'1': 'D.Jones', '2': 'D.Jones', '3': 'D.Jones', '4': 'D.Jones'}); teammates with availability doubt: Ashton Dulin.
- **Reported [CONFIRMED]:** WR Keenan Allen (groin/rest): limited; missed W4. WR Alec Pierce on IR. WR Ashton Dulin (hamstring) DNP Thursday. C Tanor Bortolini (ankle) DNP to limited. DE Arden Key (hamstring) and LB Jaylon Carlies (ribs) DNP; DT Grover Stewart DNP (rest). TE Will Mallory returned to practice off IR (thumb). (https://steelersdepot.com/2026/10/colts-week-5-thursday-injury-report-keenan-allen-remains-limited-starting-center-upgraded/)
- **Reported [REPORTED]:** With Pierce on IR, Allen is slotted as the top WR. The Colts are on a rest disadvantage after London. (https://steelersdepot.com/2026/10/colts-week-5-thursday-injury-report-keenan-allen-remains-limited-starting-center-upgraded/)
- **Benchmark FC:** 12.94 (floor 0.0, ceiling 32.74). Our projection: NOT BUILT.
- **Flags:** MISSED_LAST_GAME: no participation in week 4
- **Missing model dependencies:** practice participation does not change a projection until a designation; no partial-workload model (W5-G4); accounting repair pending (D-05) affects all players.
- **Next research action:** verify return status and any snap limit; compare to pre-injury usage.

### Tyler Warren (TE, $5000)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['TE1'].
- **2026:** 4 games, DK average 12.13, last game 9.1 (week 4).
- **What drives his production:** 2026 target share 22%, carry share 2%; red zone 2026: 3 targets, 0 carries; snap share trend -2 pp (last 2 vs first 2 games); game total 44.5 (nflverse schedule line), away, roof outdoors, rest 7 days; club QB: Daniel Jones (attempt leaders by week {'1': 'D.Jones', '2': 'D.Jones', '3': 'D.Jones', '4': 'D.Jones'}); teammates with availability doubt: Keenan Allen, Ashton Dulin.
- **Benchmark FC:** 12.63 (floor 6.03, ceiling 21.43). Our projection: NOT BUILT.
- **Missing model dependencies:** accounting repair pending (D-05) affects all players.
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### Josh Downs (WR, $6000)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['WR1'].
- **2026:** 4 games, DK average 9.3, last game 4.6 (week 4).
- **What drives his production:** 2026 target share 22%; red zone 2026: 4 targets, 0 carries; snap share trend -14 pp (last 2 vs first 2 games); game total 44.5 (nflverse schedule line), away, roof outdoors, rest 7 days; club QB: Daniel Jones (attempt leaders by week {'1': 'D.Jones', '2': 'D.Jones', '3': 'D.Jones', '4': 'D.Jones'}); teammates with availability doubt: Keenan Allen, Ashton Dulin.
- **Benchmark FC:** 10.87 (floor 1.87, ceiling 22.87). Our projection: NOT BUILT.
- **Missing model dependencies:** accounting repair pending (D-05) affects all players.
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### Mo Alie-Cox (TE, $2500)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['TE2'].
- **2026:** 4 games, DK average 0.65, last game 0.0 (week 4).
- **What drives his production:** 2026 target share 1%; snap share trend +10 pp (last 2 vs first 2 games); game total 44.5 (nflverse schedule line), away, roof outdoors, rest 7 days; club QB: Daniel Jones (attempt leaders by week {'1': 'D.Jones', '2': 'D.Jones', '3': 'D.Jones', '4': 'D.Jones'}); teammates with availability doubt: Keenan Allen, Ashton Dulin.
- **Benchmark FC:** 4.04 (floor 0.0, ceiling 13.04). Our projection: NOT BUILT.
- **Flags:** FC_VS_RECENT_PRODUCTION: FC 4.04 vs 2026 DK avg 0.65
- **Missing model dependencies:** accounting repair pending (D-05) affects all players.
- **Next research action:** decompose FC vs recent production: volume, efficiency or availability assumption.

### Colts (DST, $2500)
- **Eligibility:** ELIGIBLE_BY_CONSTRUCTION. Practice: not on report. Designation: n/a. Depth: None.
- **What drives his production:** opponent PIT QB Aaron Rodgers; opponent QB flags []; game total 44.5.
- **Reported [REPORTED]:** With Pierce on IR, Allen is slotted as the top WR. The Colts are on a rest disadvantage after London. (https://steelersdepot.com/2026/10/colts-week-5-thursday-injury-report-keenan-allen-remains-limited-starting-center-upgraded/)
- **Benchmark FC:** 2.98 (floor 0.0, ceiling 14.18). Our projection: NOT BUILT.
- **Missing model dependencies:** opponent QB identity not consumed by DST model (D-02); turnovers not event-linked (D-05).
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### Ashton Dulin (WR, $3000)
- **Eligibility:** ELIGIBLE (ACT). Practice: Did Not Participate In Practice (Hamstring). Designation: NOT_YET_ISSUED (designations are issued Friday; absence is not health). Depth: ['WR4'].
- **2026:** 2 games, DK average 2.95, last game 5.9 (week 4).
- **What drives his production:** 2026 target share 12%; game total 44.5 (nflverse schedule line), away, roof outdoors, rest 7 days; club QB: Daniel Jones (attempt leaders by week {'1': 'D.Jones', '2': 'D.Jones', '3': 'D.Jones', '4': 'D.Jones'}); teammates with availability doubt: Keenan Allen.
- **Reported [CONFIRMED]:** WR Keenan Allen (groin/rest): limited; missed W4. WR Alec Pierce on IR. WR Ashton Dulin (hamstring) DNP Thursday. C Tanor Bortolini (ankle) DNP to limited. DE Arden Key (hamstring) and LB Jaylon Carlies (ribs) DNP; DT Grover Stewart DNP (rest). TE Will Mallory returned to practice off IR (thumb). (https://steelersdepot.com/2026/10/colts-week-5-thursday-injury-report-keenan-allen-remains-limited-starting-center-upgraded/)
- **Benchmark FC:** 2.79 (floor 0.0, ceiling 9.39). Our projection: NOT BUILT.
- **Flags:** DID_NOT_PRACTICE
- **Missing model dependencies:** practice participation does not change a projection until a designation; no partial-workload model (W5-G4); accounting repair pending (D-05) affects all players.
- **Next research action:** capture Friday designation; if OUT, check redistribution to same-position teammates.

### Laquon Treadwell (WR, $3600)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['WR3'].
- **2026:** 4 games, DK average 5.32, last game 9.2 (week 4).
- **What drives his production:** 2026 target share 9%; red zone 2026: 2 targets, 0 carries; snap share trend +28 pp (last 2 vs first 2 games); game total 44.5 (nflverse schedule line), away, roof outdoors, rest 7 days; club QB: Daniel Jones (attempt leaders by week {'1': 'D.Jones', '2': 'D.Jones', '3': 'D.Jones', '4': 'D.Jones'}); teammates with availability doubt: Keenan Allen, Ashton Dulin.
- **Benchmark FC:** 2.52 (floor 0.0, ceiling 10.32). Our projection: NOT BUILT.
- **Flags:** ROLE_CHANGE: snap share up 28 pp
- **Missing model dependencies:** 4-game pooled usage does not separate a role change from a one-game anomaly (W5-G8); accounting repair pending (D-05) affects all players.
- **Next research action:** read the last two games: is the snap change a role change, an injury exit or game script?.

### Seth McGowan (RB, $4300)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['RB2'].
- **2026:** 4 games, DK average 1.8, last game 4.8 (week 4).
- **What drives his production:** 2026 target share 3%, carry share 10%; red zone 2026: 0 targets, 3 carries; snap share trend +14 pp (last 2 vs first 2 games); game total 44.5 (nflverse schedule line), away, roof outdoors, rest 7 days; club QB: Daniel Jones (attempt leaders by week {'1': 'D.Jones', '2': 'D.Jones', '3': 'D.Jones', '4': 'D.Jones'}); teammates with availability doubt: Keenan Allen, Ashton Dulin.
- **Benchmark FC:** 1.14 (floor 0.0, ceiling 4.74). Our projection: NOT BUILT.
- **Missing model dependencies:** accounting repair pending (D-05) affects all players.
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

## LV vs NE

### Ashton Jeanty (RB, $7200)
- **Eligibility:** ELIGIBLE (ACT). Practice: Limited Participation in Practice (Ankle, Foot). Designation: NOT_YET_ISSUED (designations are issued Friday; absence is not health). Depth: ['RB1'].
- **2026:** 4 games, DK average 19.23, last game 18.6 (week 4).
- **What drives his production:** 2026 target share 18%, carry share 66%; red zone 2026: 6 targets, 15 carries; snap share trend -2 pp (last 2 vs first 2 games); game total 45.5 (nflverse schedule line), away, roof outdoors, rest 7 days; club QB: Kirk Cousins (attempt leaders by week {'1': 'K.Cousins', '2': 'K.Cousins', '3': 'K.Cousins', '4': 'K.Cousins'}); teammates with availability doubt: Jalen Nailor.
- **Reported [CONFIRMED]:** Wed/Thu: TE Brock Bowers (knee) LP/FP; RB Ashton Jeanty (ankle) FP/LP (a Thursday downgrade); WR Jalen Nailor (concussion) DNP/DNP; WR Cody White (ankle) LP/LP; WR Dont'e Thornton Jr. (hamstring, off IR) FP/FP; WR Dareke Young (shoulder) full Thursday. G Jackson Powers-Johnson and DT Folorunso Fatukasi LP/FP; G Spencer Burford and G Trey Zuhn III LP/LP. (https://www.raiders.com/news/las-vegas-raiders-new-england-patriots-week-5-injury-report-2026)
- **Benchmark FC:** 16.16 (floor 1.76, ceiling 35.36). Our projection: NOT BUILT.
- **Missing model dependencies:** practice participation does not change a projection until a designation; no partial-workload model (W5-G4); lower-tail volatility under-stated for high-mean players (D-01).
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### Kirk Cousins (QB, $5400)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['QB1'].
- **2026:** 4 games, DK average 21.46, last game 26.6 (week 4).
- **What drives his production:** snap share trend +0 pp (last 2 vs first 2 games); game total 45.5 (nflverse schedule line), away, roof outdoors, rest 7 days; club QB: Kirk Cousins (attempt leaders by week {'1': 'K.Cousins', '2': 'K.Cousins', '3': 'K.Cousins', '4': 'K.Cousins'}); teammates with availability doubt: Jalen Nailor.
- **Reported [CONFIRMED]:** Kirk Cousins is the starter; Kubiak named him over No. 1 pick Fernando Mendoza in August. Through 4 starts: 1,026 yds, 11 TD, 4 INT; team 3-1, W4 loss to KC. Previews treat him as the Week 5 starter, though no game-week confirmation was found. (https://www.nfl.com/news/raiders-name-kirk-cousins-starting-fernando-mendoza-officially-backup)
- **Benchmark FC:** 16.07 (floor 3.62, ceiling 32.67). Our projection: NOT BUILT.
- **Missing model dependencies:** lower-tail volatility under-stated for high-mean players (D-01).
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### Brock Bowers (TE, $7000)
- **Eligibility:** ELIGIBLE (ACT). Practice: Full Participation in Practice (Knee). Designation: NOT_YET_ISSUED (designations are issued Friday; absence is not health). Depth: ['TE1'].
- **2026:** 2 games, DK average 25.6, last game 20.6 (week 4).
- **What drives his production:** 2026 target share 33%; red zone 2026: 4 targets, 0 carries; game total 45.5 (nflverse schedule line), away, roof outdoors, rest 7 days; club QB: Kirk Cousins (attempt leaders by week {'1': 'K.Cousins', '2': 'K.Cousins', '3': 'K.Cousins', '4': 'K.Cousins'}); teammates with availability doubt: Jalen Nailor.
- **Reported [CONFIRMED]:** Wed/Thu: TE Brock Bowers (knee) LP/FP; RB Ashton Jeanty (ankle) FP/LP (a Thursday downgrade); WR Jalen Nailor (concussion) DNP/DNP; WR Cody White (ankle) LP/LP; WR Dont'e Thornton Jr. (hamstring, off IR) FP/FP; WR Dareke Young (shoulder) full Thursday. G Jackson Powers-Johnson and DT Folorunso Fatukasi LP/FP; G Spencer Burford and G Trey Zuhn III LP/LP. (https://www.raiders.com/news/las-vegas-raiders-new-england-patriots-week-5-injury-report-2026)
- **Benchmark FC:** 15.0 (floor 0.9, ceiling 33.8). Our projection: NOT BUILT.
- **Flags:** FC_VS_RECENT_PRODUCTION: FC 15.0 vs 2026 DK avg 25.6
- **Missing model dependencies:** lower-tail volatility under-stated for high-mean players (D-01).
- **Next research action:** decompose FC vs recent production: volume, efficiency or availability assumption.

### Tre Tucker (WR, $4800)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['WR1'].
- **2026:** 4 games, DK average 11.82, last game 8.4 (week 4).
- **What drives his production:** 2026 target share 17%; red zone 2026: 1 targets, 0 carries; snap share trend -3 pp (last 2 vs first 2 games); game total 45.5 (nflverse schedule line), away, roof outdoors, rest 7 days; club QB: Kirk Cousins (attempt leaders by week {'1': 'K.Cousins', '2': 'K.Cousins', '3': 'K.Cousins', '4': 'K.Cousins'}); teammates with availability doubt: Jalen Nailor.
- **Benchmark FC:** 8.43 (floor 0.0, ceiling 23.63). Our projection: NOT BUILT.
- **Missing model dependencies:** accounting repair pending (D-05) affects all players.
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### Michael Mayer (TE, $3500)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['TE2'].
- **2026:** 4 games, DK average 10.72, last game 16.2 (week 4).
- **What drives his production:** 2026 target share 17%; red zone 2026: 2 targets, 0 carries; snap share trend +5 pp (last 2 vs first 2 games); game total 45.5 (nflverse schedule line), away, roof outdoors, rest 7 days; club QB: Kirk Cousins (attempt leaders by week {'1': 'K.Cousins', '2': 'K.Cousins', '3': 'K.Cousins', '4': 'K.Cousins'}); teammates with availability doubt: Jalen Nailor.
- **Benchmark FC:** 7.21 (floor 0.0, ceiling 17.01). Our projection: NOT BUILT.
- **Missing model dependencies:** accounting repair pending (D-05) affects all players.
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### Mike Washington Jr. (RB, $4200)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['RB2'].
- **2026:** 4 games, DK average 4.72, last game 2.7 (week 4).
- **What drives his production:** 2026 target share 2%, carry share 21%; red zone 2026: 0 targets, 4 carries; snap share trend -0 pp (last 2 vs first 2 games); game total 45.5 (nflverse schedule line), away, roof outdoors, rest 7 days; club QB: Kirk Cousins (attempt leaders by week {'1': 'K.Cousins', '2': 'K.Cousins', '3': 'K.Cousins', '4': 'K.Cousins'}); teammates with availability doubt: Jalen Nailor.
- **Reported [CONFIRMED]:** Wed/Thu: TE Brock Bowers (knee) LP/FP; RB Ashton Jeanty (ankle) FP/LP (a Thursday downgrade); WR Jalen Nailor (concussion) DNP/DNP; WR Cody White (ankle) LP/LP; WR Dont'e Thornton Jr. (hamstring, off IR) FP/FP; WR Dareke Young (shoulder) full Thursday. G Jackson Powers-Johnson and DT Folorunso Fatukasi LP/FP; G Spencer Burford and G Trey Zuhn III LP/LP. (https://www.raiders.com/news/las-vegas-raiders-new-england-patriots-week-5-injury-report-2026)
- **Reported [CONFIRMED]:** WR Dont'e Thornton Jr. designated to return from IR (after 4 weeks on IR). (https://www.raiders.com/video/andrew-janocko-kirk-cousins-patriots-nfl-week-5-2026-season)
- **Benchmark FC:** 6.4 (floor 0.0, ceiling 0.0). Our projection: NOT BUILT.
- **Missing model dependencies:** accounting repair pending (D-05) affects all players.
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### Raiders (DST, $2500)
- **Eligibility:** ELIGIBLE_BY_CONSTRUCTION. Practice: not on report. Designation: n/a. Depth: None.
- **What drives his production:** opponent NE QB Drake Maye; opponent QB flags []; game total 45.5.
- **Reported [REPORTED]:** K Matt Gay is listed as the Raiders kicker for this game. (https://www.rotoballer.com/2026-fantasy-football-kicker-rankings-week-5-start-sit-kickers/1961202)
- **Benchmark FC:** 5.94 (floor 0.0, ceiling 15.94). Our projection: NOT BUILT.
- **Missing model dependencies:** opponent QB identity not consumed by DST model (D-02); turnovers not event-linked (D-05).
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### Jalen Nailor (WR, $3600)
- **Eligibility:** ELIGIBLE (ACT). Practice: Did Not Participate In Practice (Concussion). Designation: NOT_YET_ISSUED (designations are issued Friday; absence is not health). Depth: ['WR2'].
- **2026:** 4 games, DK average 2.55, last game 0.0 (week 4).
- **What drives his production:** 2026 target share 9%; red zone 2026: 1 targets, 0 carries; snap share trend -20 pp (last 2 vs first 2 games); game total 45.5 (nflverse schedule line), away, roof outdoors, rest 7 days; club QB: Kirk Cousins (attempt leaders by week {'1': 'K.Cousins', '2': 'K.Cousins', '3': 'K.Cousins', '4': 'K.Cousins'}).
- **Reported [CONFIRMED]:** Wed/Thu: TE Brock Bowers (knee) LP/FP; RB Ashton Jeanty (ankle) FP/LP (a Thursday downgrade); WR Jalen Nailor (concussion) DNP/DNP; WR Cody White (ankle) LP/LP; WR Dont'e Thornton Jr. (hamstring, off IR) FP/FP; WR Dareke Young (shoulder) full Thursday. G Jackson Powers-Johnson and DT Folorunso Fatukasi LP/FP; G Spencer Burford and G Trey Zuhn III LP/LP. (https://www.raiders.com/news/las-vegas-raiders-new-england-patriots-week-5-injury-report-2026)
- **Benchmark FC:** 5.87 (floor 0.0, ceiling 18.07). Our projection: NOT BUILT.
- **Flags:** DID_NOT_PRACTICE | ROLE_CHANGE: snap share down 20 pp | FC_VS_RECENT_PRODUCTION: FC 5.87 vs 2026 DK avg 2.55
- **Missing model dependencies:** 4-game pooled usage does not separate a role change from a one-game anomaly (W5-G8); practice participation does not change a projection until a designation; no partial-workload model (W5-G4); accounting repair pending (D-05) affects all players.
- **Next research action:** capture Friday designation; if OUT, check redistribution to same-position teammates; decompose FC vs recent production: volume, efficiency or availability assumption; read the last two games: is the snap change a role change, an injury exit or game script?.

### Cody White (WR, $3300)
- **Eligibility:** ELIGIBLE (ACT). Practice: Limited Participation in Practice (Ankle). Designation: NOT_YET_ISSUED (designations are issued Friday; absence is not health). Depth: ['WR3'].
- **2026:** 4 games, DK average 7.85, last game 7.6 (week 4).
- **What drives his production:** 2026 target share 7%; red zone 2026: 4 targets, 0 carries; snap share trend +28 pp (last 2 vs first 2 games); game total 45.5 (nflverse schedule line), away, roof outdoors, rest 7 days; club QB: Kirk Cousins (attempt leaders by week {'1': 'K.Cousins', '2': 'K.Cousins', '3': 'K.Cousins', '4': 'K.Cousins'}); teammates with availability doubt: Jalen Nailor.
- **Reported [CONFIRMED]:** Wed/Thu: TE Brock Bowers (knee) LP/FP; RB Ashton Jeanty (ankle) FP/LP (a Thursday downgrade); WR Jalen Nailor (concussion) DNP/DNP; WR Cody White (ankle) LP/LP; WR Dont'e Thornton Jr. (hamstring, off IR) FP/FP; WR Dareke Young (shoulder) full Thursday. G Jackson Powers-Johnson and DT Folorunso Fatukasi LP/FP; G Spencer Burford and G Trey Zuhn III LP/LP. (https://www.raiders.com/news/las-vegas-raiders-new-england-patriots-week-5-injury-report-2026)
- **Benchmark FC:** 3.41 (floor 0.0, ceiling 12.61). Our projection: NOT BUILT.
- **Flags:** ROLE_CHANGE: snap share up 28 pp | FC_VS_RECENT_PRODUCTION: FC 3.41 vs 2026 DK avg 7.85
- **Missing model dependencies:** 4-game pooled usage does not separate a role change from a one-game anomaly (W5-G8); practice participation does not change a projection until a designation; no partial-workload model (W5-G4); accounting repair pending (D-05) affects all players.
- **Next research action:** decompose FC vs recent production: volume, efficiency or availability assumption; read the last two games: is the snap change a role change, an injury exit or game script?.

### Dareke Young (WR, $3000)
- **Eligibility:** ELIGIBLE (ACT). Practice: Full Participation in Practice (Shoulder). Designation: NOT_YET_ISSUED (designations are issued Friday; absence is not health). Depth: ['WR4'].
- **2026:** 4 games, DK average 1.4, last game 1.9 (week 4).
- **What drives his production:** 2026 target share 2%; snap share trend -2 pp (last 2 vs first 2 games); game total 45.5 (nflverse schedule line), away, roof outdoors, rest 7 days; club QB: Kirk Cousins (attempt leaders by week {'1': 'K.Cousins', '2': 'K.Cousins', '3': 'K.Cousins', '4': 'K.Cousins'}); teammates with availability doubt: Jalen Nailor.
- **Reported [CONFIRMED]:** Wed/Thu: TE Brock Bowers (knee) LP/FP; RB Ashton Jeanty (ankle) FP/LP (a Thursday downgrade); WR Jalen Nailor (concussion) DNP/DNP; WR Cody White (ankle) LP/LP; WR Dont'e Thornton Jr. (hamstring, off IR) FP/FP; WR Dareke Young (shoulder) full Thursday. G Jackson Powers-Johnson and DT Folorunso Fatukasi LP/FP; G Spencer Burford and G Trey Zuhn III LP/LP. (https://www.raiders.com/news/las-vegas-raiders-new-england-patriots-week-5-injury-report-2026)
- **Benchmark FC:** 1.19 (floor 0.0, ceiling 4.39). Our projection: NOT BUILT.
- **Missing model dependencies:** accounting repair pending (D-05) affects all players.
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

## MIA vs CIN

### Malik Willis (QB, $4600)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['QB1'].
- **2026:** 4 games, DK average 11.42, last game 3.5 (week 4).
- **What drives his production:** red zone 2026: 0 targets, 1 carries; snap share trend +0 pp (last 2 vs first 2 games); game total 42.5 (nflverse schedule line), home, roof outdoors, rest 7 days; club QB: Malik Willis (attempt leaders by week {'1': 'M.Willis', '2': 'M.Willis', '3': 'M.Willis', '4': 'M.Willis'}); teammates with availability doubt: Caleb Douglas, Justin Joly.
- **Reported [REPORTED]:** Malik Willis has been the starter since being named on Sept 8, with 4 games (712 yds, 1 TD, 2 INT; 85 yds in the W4 15-10 loss to MIN). I found no Week 5 change or injury for him. (https://fantasynerds.com/news/story/2026/09/08/malik-willis-named-dolphins-starting-qb-reflects-on-journey-1617255)
- **Benchmark FC:** 18.02 (floor 5.27, ceiling 35.02). Our projection: NOT BUILT.
- **Flags:** FC_VS_RECENT_PRODUCTION: FC 18.02 vs 2026 DK avg 11.42
- **Missing model dependencies:** lower-tail volatility under-stated for high-mean players (D-01).
- **Next research action:** decompose FC vs recent production: volume, efficiency or availability assumption.

### Caleb Douglas (WR, $3900)
- **Eligibility:** ELIGIBLE (ACT). Practice: Did Not Participate In Practice (Ankle). Designation: NOT_YET_ISSUED (designations are issued Friday; absence is not health). Depth: ['WR2'].
- **2026:** 2 games, DK average 9.15, last game 3.9 (week 2).
- **What drives his production:** 2026 target share 20%; red zone 2026: 1 targets, 0 carries; game total 42.5 (nflverse schedule line), home, roof outdoors, rest 7 days; club QB: Malik Willis (attempt leaders by week {'1': 'M.Willis', '2': 'M.Willis', '3': 'M.Willis', '4': 'M.Willis'}); teammates with availability doubt: Justin Joly.
- **Reported [REPORTED]:** Wednesday: DNP Rob Beal Jr. (hamstring), WR Caleb Douglas (ankle), CB Reese/Reece Taylor (quad), Jackson Woodard (ankle). Limited: Tucker Addington (shoulder), Chris Bell (knee), CB JuJu Brents (heel), DT Kenneth Grant (toe), T Austin Jackson (knee), S Dante Trader Jr. (shin). Full: CB Storm Duck (knee, PUP). (https://sports.yahoo.com/articles/dolphins-11-players-first-injury-204853114.html)
- **Reported [REPORTED]:** Thursday: RB Jaylen Wright (toe) limited; five Dolphins DNP. Rookie WR Caleb Douglas, who missed 2 games, is 'day-to-day' per Jeff Hafley. Headline 'Caleb Douglas Remains Out'. (https://www.si.com/nfl/dolphins/onsi/new-injury-issues-for-dolphins-what-to-know-about-even-more-tryouts-01m4etchb9dv)
- **Benchmark FC:** 10.19 (floor 2.39, ceiling 20.59). Our projection: NOT BUILT.
- **Flags:** DID_NOT_PRACTICE | MISSED_LAST_GAME: no participation in week 4
- **Missing model dependencies:** practice participation does not change a projection until a designation; no partial-workload model (W5-G4); accounting repair pending (D-05) affects all players.
- **Next research action:** capture Friday designation; if OUT, check redistribution to same-position teammates; verify return status and any snap limit; compare to pre-injury usage.

### Malik Washington (WR, $4600)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['WR1'].
- **2026:** 4 games, DK average 9.78, last game 12.0 (week 4).
- **What drives his production:** 2026 target share 27%, carry share 5%; red zone 2026: 1 targets, 2 carries; snap share trend +1 pp (last 2 vs first 2 games); game total 42.5 (nflverse schedule line), home, roof outdoors, rest 7 days; club QB: Malik Willis (attempt leaders by week {'1': 'M.Willis', '2': 'M.Willis', '3': 'M.Willis', '4': 'M.Willis'}); teammates with availability doubt: Caleb Douglas, Justin Joly.
- **Reported [REPORTED]:** Oct 5: RB Carlos Washington waived. Oct 7: DT Kenneth Grant designated to return from IR. Oct 8: EDGE Amari Gainer signed to the practice squad; DL Keith Cooper Jr. released from it. Brought in an ex-Saints RB after Wright landed on the report (headline only). (https://www.profootballrumors.com/2026/10/minor-nfl-transactions-10-5-26)
- **Benchmark FC:** 8.16 (floor 2.46, ceiling 15.76). Our projection: NOT BUILT.
- **Missing model dependencies:** accounting repair pending (D-05) affects all players.
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### Greg Dulcich (TE, $3100)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['TE1'].
- **2026:** 4 games, DK average 4.5, last game 0.0 (week 4).
- **What drives his production:** 2026 target share 10%; red zone 2026: 2 targets, 0 carries; snap share trend -8 pp (last 2 vs first 2 games); game total 42.5 (nflverse schedule line), home, roof outdoors, rest 7 days; club QB: Malik Willis (attempt leaders by week {'1': 'M.Willis', '2': 'M.Willis', '3': 'M.Willis', '4': 'M.Willis'}); teammates with availability doubt: Caleb Douglas, Justin Joly.
- **Benchmark FC:** 7.94 (floor 1.49, ceiling 16.54). Our projection: NOT BUILT.
- **Flags:** FC_VS_RECENT_PRODUCTION: FC 7.94 vs 2026 DK avg 4.5
- **Missing model dependencies:** accounting repair pending (D-05) affects all players.
- **Next research action:** decompose FC vs recent production: volume, efficiency or availability assumption.

### Ollie Gordon II (RB, $5300)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['RB1'].
- **2026:** 4 games, DK average 9.05, last game 21.0 (week 4).
- **What drives his production:** 2026 target share 5%, carry share 29%; red zone 2026: 0 targets, 6 carries; snap share trend +57 pp (last 2 vs first 2 games); game total 42.5 (nflverse schedule line), home, roof outdoors, rest 7 days; club QB: Malik Willis (attempt leaders by week {'1': 'M.Willis', '2': 'M.Willis', '3': 'M.Willis', '4': 'M.Willis'}); teammates with availability doubt: Caleb Douglas, Justin Joly.
- **Reported [CONFIRMED]:** De'Von Achane is out for the season (torn ACL, W3 vs KC). Ollie Gordon II took over in W4 (about 100 yds and a TD; carry count differs between sources, 9 vs 12). Rotoworld expects Gordon to start Week 5 over Wright. (https://www.nbcsports.com/fantasy/football/player-news/2026-10-04/gordon-takes-over-dolphins-backfield-in-week-5)
- **Benchmark FC:** 5.74 (floor 0.0, ceiling 17.74). Our projection: NOT BUILT.
- **Flags:** ROLE_CHANGE: snap share up 57 pp | FC_VS_RECENT_PRODUCTION: FC 5.74 vs 2026 DK avg 9.05
- **Missing model dependencies:** 4-game pooled usage does not separate a role change from a one-game anomaly (W5-G8); accounting repair pending (D-05) affects all players.
- **Next research action:** decompose FC vs recent production: volume, efficiency or availability assumption; read the last two games: is the snap change a role change, an injury exit or game script?.

### DJ Herman (RB, $4000)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: NOT_ON_LATEST_DEPTH_CHART.
- **2026:** 4 games, DK average 0.7, last game 0.0 (week 4).
- **What drives his production:** 2026 target share 3%; snap share trend +16 pp (last 2 vs first 2 games); game total 42.5 (nflverse schedule line), home, roof outdoors, rest 7 days; club QB: Malik Willis (attempt leaders by week {'1': 'M.Willis', '2': 'M.Willis', '3': 'M.Willis', '4': 'M.Willis'}); teammates with availability doubt: Caleb Douglas, Justin Joly.
- **Benchmark FC:** 5.69 (floor 5.69, ceiling 5.69). Our projection: NOT BUILT.
- **Flags:** ROLE_CHANGE: snap share up 16 pp | FC_VS_RECENT_PRODUCTION: FC 5.69 vs 2026 DK avg 0.7
- **Missing model dependencies:** 4-game pooled usage does not separate a role change from a one-game anomaly (W5-G8); accounting repair pending (D-05) affects all players.
- **Next research action:** decompose FC vs recent production: volume, efficiency or availability assumption; read the last two games: is the snap change a role change, an injury exit or game script?.

### Chris Bell (WR, $3600)
- **Eligibility:** ELIGIBLE (ACT). Practice: Limited Participation in Practice (Knee). Designation: NOT_YET_ISSUED (designations are issued Friday; absence is not health). Depth: ['WR3'].
- **2026:** 4 games, DK average 3.55, last game 0.0 (week 4).
- **What drives his production:** 2026 target share 12%; snap share trend +30 pp (last 2 vs first 2 games); game total 42.5 (nflverse schedule line), home, roof outdoors, rest 7 days; club QB: Malik Willis (attempt leaders by week {'1': 'M.Willis', '2': 'M.Willis', '3': 'M.Willis', '4': 'M.Willis'}); teammates with availability doubt: Caleb Douglas, Justin Joly.
- **Reported [REPORTED]:** Wednesday: DNP Rob Beal Jr. (hamstring), WR Caleb Douglas (ankle), CB Reese/Reece Taylor (quad), Jackson Woodard (ankle). Limited: Tucker Addington (shoulder), Chris Bell (knee), CB JuJu Brents (heel), DT Kenneth Grant (toe), T Austin Jackson (knee), S Dante Trader Jr. (shin). Full: CB Storm Duck (knee, PUP). (https://sports.yahoo.com/articles/dolphins-11-players-first-injury-204853114.html)
- **Benchmark FC:** 5.2 (floor 0.0, ceiling 14.0). Our projection: NOT BUILT.
- **Flags:** ROLE_CHANGE: snap share up 30 pp
- **Missing model dependencies:** 4-game pooled usage does not separate a role change from a one-game anomaly (W5-G8); practice participation does not change a projection until a designation; no partial-workload model (W5-G4); accounting repair pending (D-05) affects all players.
- **Next research action:** read the last two games: is the snap change a role change, an injury exit or game script?.

### Dolphins (DST, $2000)
- **Eligibility:** ELIGIBLE_BY_CONSTRUCTION. Practice: not on report. Designation: n/a. Depth: None.
- **What drives his production:** opponent CIN QB Joe Burrow; opponent QB flags []; game total 42.5.
- **Reported [REPORTED]:** Thursday: RB Jaylen Wright (toe) limited; five Dolphins DNP. Rookie WR Caleb Douglas, who missed 2 games, is 'day-to-day' per Jeff Hafley. Headline 'Caleb Douglas Remains Out'. (https://www.si.com/nfl/dolphins/onsi/new-injury-issues-for-dolphins-what-to-know-about-even-more-tryouts-01m4etchb9dv)
- **Benchmark FC:** 4.41 (floor 0.0, ceiling 17.41). Our projection: NOT BUILT.
- **Missing model dependencies:** opponent QB identity not consumed by DST model (D-02); turnovers not event-linked (D-05).
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### Jaylen Wright (RB, $4800)
- **Eligibility:** ELIGIBLE (ACT). Practice: Limited Participation in Practice (Foot). Designation: NOT_YET_ISSUED (designations are issued Friday; absence is not health). Depth: ['RB2'].
- **2026:** 3 games, DK average 0.57, last game 0.7 (week 4).
- **What drives his production:** 2026 target share 0%, carry share 13%; 2026 carry share 13%; red zone 2026: 0 targets, 2 carries; snap share trend +12 pp (last 2 vs first 2 games); game total 42.5 (nflverse schedule line), home, roof outdoors, rest 7 days; club QB: Malik Willis (attempt leaders by week {'1': 'M.Willis', '2': 'M.Willis', '3': 'M.Willis', '4': 'M.Willis'}); teammates with availability doubt: Caleb Douglas, Justin Joly.
- **Reported [REPORTED]:** Thursday: RB Jaylen Wright (toe) limited; five Dolphins DNP. Rookie WR Caleb Douglas, who missed 2 games, is 'day-to-day' per Jeff Hafley. Headline 'Caleb Douglas Remains Out'. (https://www.si.com/nfl/dolphins/onsi/new-injury-issues-for-dolphins-what-to-know-about-even-more-tryouts-01m4etchb9dv)
- **Reported [REPORTED]:** Oct 5: RB Carlos Washington waived. Oct 7: DT Kenneth Grant designated to return from IR. Oct 8: EDGE Amari Gainer signed to the practice squad; DL Keith Cooper Jr. released from it. Brought in an ex-Saints RB after Wright landed on the report (headline only). (https://www.profootballrumors.com/2026/10/minor-nfl-transactions-10-5-26)
- **Reported [CONFIRMED]:** De'Von Achane is out for the season (torn ACL, W3 vs KC). Ollie Gordon II took over in W4 (about 100 yds and a TD; carry count differs between sources, 9 vs 12). Rotoworld expects Gordon to start Week 5 over Wright. (https://www.nbcsports.com/fantasy/football/player-news/2026-10-04/gordon-takes-over-dolphins-backfield-in-week-5)
- **Benchmark FC:** 4.32 (floor 0.0, ceiling 13.12). Our projection: NOT BUILT.
- **Flags:** FC_VS_RECENT_PRODUCTION: FC 4.32 vs 2026 DK avg 0.57
- **Missing model dependencies:** practice participation does not change a projection until a designation; no partial-workload model (W5-G4); accounting repair pending (D-05) affects all players.
- **Next research action:** decompose FC vs recent production: volume, efficiency or availability assumption.

### Will Kacmarek (TE, $2500)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['TE2'].
- **2026:** 4 games, DK average 0.97, last game 2.5 (week 4).
- **What drives his production:** 2026 target share 5%; snap share trend +16 pp (last 2 vs first 2 games); game total 42.5 (nflverse schedule line), home, roof outdoors, rest 7 days; club QB: Malik Willis (attempt leaders by week {'1': 'M.Willis', '2': 'M.Willis', '3': 'M.Willis', '4': 'M.Willis'}); teammates with availability doubt: Caleb Douglas, Justin Joly.
- **Benchmark FC:** 2.91 (floor 1.41, ceiling 4.91). Our projection: NOT BUILT.
- **Flags:** ROLE_CHANGE: snap share up 16 pp
- **Missing model dependencies:** 4-game pooled usage does not separate a role change from a one-game anomaly (W5-G8); accounting repair pending (D-05) affects all players.
- **Next research action:** read the last two games: is the snap change a role change, an injury exit or game script?.

## MIN vs NO

### Aaron Jones (RB, $6500)
- **Eligibility:** ELIGIBLE (ACT). Practice: Limited Participation in Practice (Not injury related - resting player). Designation: NOT_YET_ISSUED (designations are issued Friday; absence is not health). Depth: ['RB1'].
- **2026:** 4 games, DK average 13.62, last game 16.8 (week 4).
- **What drives his production:** 2026 target share 13%, carry share 64%; red zone 2026: 2 targets, 6 carries; snap share trend +13 pp (last 2 vs first 2 games); game total 41.5 (nflverse schedule line), away, roof dome, rest 7 days; club QB: Kyler Murray (attempt leaders by week {'1': 'C.Wentz', '2': 'C.Wentz', '3': 'K.Murray', '4': 'K.Murray'}); teammates with availability doubt: Justin Jefferson, Carson Wentz.
- **Benchmark FC:** 18.83 (floor 4.43, ceiling 38.03). Our projection: NOT BUILT.
- **Flags:** FC_VS_RECENT_PRODUCTION: FC 18.83 vs 2026 DK avg 13.62
- **Missing model dependencies:** QB-conditioned team volume / shares NOT consumed by the engine (W5-G1); practice participation does not change a projection until a designation; no partial-workload model (W5-G4); lower-tail volatility under-stated for high-mean players (D-01).
- **Next research action:** decompose FC vs recent production: volume, efficiency or availability assumption.

### Kyler Murray (QB, $5200)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['QB1'].
- **2026:** 3 games, DK average 7.84, last game 11.48 (week 4).
- **What drives his production:** red zone 2026: 0 targets, 3 carries; snap share trend +42 pp (last 2 vs first 2 games); game total 41.5 (nflverse schedule line), away, roof dome, rest 7 days; club QB: Kyler Murray (attempt leaders by week {'1': 'C.Wentz', '2': 'C.Wentz', '3': 'K.Murray', '4': 'K.Murray'}); teammates with availability doubt: Justin Jefferson, Carson Wentz.
- **Reported [CONFIRMED]:** Kyler Murray is expected to start Week 5; he is not on the Week 5 injury report. QB by week: Murray started W1 and left with a concussion; Carson Wentz finished W1 (W vs GB) and started W2 at CHI; Murray started W3 (at TB) and W4. J.J. McCarthy has since been traded to NYG. (https://www.mprnews.org/story/2026/09/18/vikings-will-start-carson-wentz-at-qb-vs-bears-with-kyler-murray-still-in-concussion-protocol)
- **Benchmark FC:** 16.19 (floor 3.89, ceiling 32.59). Our projection: NOT BUILT.
- **Flags:** ROLE_CHANGE: snap share up 42 pp | FC_VS_RECENT_PRODUCTION: FC 16.19 vs 2026 DK avg 7.84 | QB_REGIME_CHANGE: listed starter is not the dominant passer of the modelling window
- **Missing model dependencies:** QB-conditioned team volume / shares NOT consumed by the engine (W5-G1); QB rushing from a generic cohort prior, starts pooled with relief (D-03); 4-game pooled usage does not separate a role change from a one-game anomaly (W5-G8); lower-tail volatility under-stated for high-mean players (D-01).
- **Next research action:** confirm the starter from a team source; run the QB shadow candidate for this club; decompose FC vs recent production: volume, efficiency or availability assumption; read the last two games: is the snap change a role change, an injury exit or game script?.

### Justin Jefferson (WR, $7300)
- **Eligibility:** ELIGIBLE (ACT). Practice: Limited Participation in Practice (Ankle). Designation: NOT_YET_ISSUED (designations are issued Friday; absence is not health). Depth: ['WR1'].
- **2026:** 3 games, DK average 14.97, last game 5.2 (week 3).
- **What drives his production:** 2026 target share 26%; red zone 2026: 3 targets, 0 carries; snap share trend -40 pp (last 2 vs first 2 games); game total 41.5 (nflverse schedule line), away, roof dome, rest 7 days; club QB: Kyler Murray (attempt leaders by week {'1': 'C.Wentz', '2': 'C.Wentz', '3': 'K.Murray', '4': 'K.Murray'}); teammates with availability doubt: Carson Wentz.
- **Reported [CONFLICTING]:** WR Justin Jefferson (right ankle sprain): limited Wednesday; practicing for the first time since the sprain and expects to play. One preview says he may miss a second full game. (https://www.startribune.com/minnesota-vikings-justin-jefferson-injury-update-new-orleans-saints-week-5-news-jordan-addison/601896085)
- **Benchmark FC:** 14.83 (floor 0.0, ceiling 36.23). Our projection: NOT BUILT.
- **Flags:** MISSED_LAST_GAME: no participation in week 4 | ROLE_CHANGE: snap share down 40 pp
- **Missing model dependencies:** QB-conditioned team volume / shares NOT consumed by the engine (W5-G1); 4-game pooled usage does not separate a role change from a one-game anomaly (W5-G8); practice participation does not change a projection until a designation; no partial-workload model (W5-G4); accounting repair pending (D-05) affects all players.
- **Next research action:** read the last two games: is the snap change a role change, an injury exit or game script?; verify return status and any snap limit; compare to pre-injury usage.

### Vikings (DST, $3100)
- **Eligibility:** ELIGIBLE_BY_CONSTRUCTION. Practice: not on report. Designation: n/a. Depth: None.
- **What drives his production:** opponent NO QB Tyler Shough; opponent QB flags []; game total 41.5.
- **Benchmark FC:** 10.19 (floor 1.04, ceiling 22.39). Our projection: NOT BUILT.
- **Missing model dependencies:** opponent QB identity not consumed by DST model (D-02); turnovers not event-linked (D-05).
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### Jauan Jennings (WR, $4100)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['WR3'].
- **2026:** 3 games, DK average 0.97, last game 1.8 (week 4).
- **What drives his production:** 2026 target share 5%; snap share trend +24 pp (last 2 vs first 2 games); game total 41.5 (nflverse schedule line), away, roof dome, rest 7 days; club QB: Kyler Murray (attempt leaders by week {'1': 'C.Wentz', '2': 'C.Wentz', '3': 'K.Murray', '4': 'K.Murray'}); teammates with availability doubt: Justin Jefferson, Carson Wentz.
- **Benchmark FC:** 8.26 (floor 0.0, ceiling 24.46). Our projection: NOT BUILT.
- **Flags:** ROLE_CHANGE: snap share up 24 pp | FC_VS_RECENT_PRODUCTION: FC 8.26 vs 2026 DK avg 0.97
- **Missing model dependencies:** QB-conditioned team volume / shares NOT consumed by the engine (W5-G1); 4-game pooled usage does not separate a role change from a one-game anomaly (W5-G8); accounting repair pending (D-05) affects all players.
- **Next research action:** decompose FC vs recent production: volume, efficiency or availability assumption; read the last two games: is the snap change a role change, an injury exit or game script?.

### Jordan Addison (WR, $5800)
- **Eligibility:** ELIGIBLE (ACT). Practice: Limited Participation in Practice (Hamstring). Designation: NOT_YET_ISSUED (designations are issued Friday; absence is not health). Depth: ['WR2'].
- **2026:** 4 games, DK average 8.3, last game 9.1 (week 4).
- **What drives his production:** 2026 target share 22%, carry share 1%; red zone 2026: 1 targets, 0 carries; snap share trend +12 pp (last 2 vs first 2 games); game total 41.5 (nflverse schedule line), away, roof dome, rest 7 days; club QB: Kyler Murray (attempt leaders by week {'1': 'C.Wentz', '2': 'C.Wentz', '3': 'K.Murray', '4': 'K.Murray'}); teammates with availability doubt: Justin Jefferson, Carson Wentz.
- **Reported [CONFIRMED]:** WR Jordan Addison (hamstring) DNP Wednesday, limited Thursday. LT Christian Darrisaw (concussion) DNP both days. RT Brian O'Neill (knee) limited. CB Chuck Demmings (hamstring) DNP Wednesday, limited Thursday. (https://www.vikings.com/news/saints-injury-report-week-5-2026-nfl-season)
- **Benchmark FC:** 8.13 (floor 0.0, ceiling 26.53). Our projection: NOT BUILT.
- **Missing model dependencies:** QB-conditioned team volume / shares NOT consumed by the engine (W5-G1); practice participation does not change a projection until a designation; no partial-workload model (W5-G4); accounting repair pending (D-05) affects all players.
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### T.J. Hockenson (TE, $4800)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['TE1'].
- **2026:** 4 games, DK average 12.62, last game 27.9 (week 4).
- **What drives his production:** 2026 target share 24%; red zone 2026: 5 targets, 0 carries; snap share trend +16 pp (last 2 vs first 2 games); game total 41.5 (nflverse schedule line), away, roof dome, rest 7 days; club QB: Kyler Murray (attempt leaders by week {'1': 'C.Wentz', '2': 'C.Wentz', '3': 'K.Murray', '4': 'K.Murray'}); teammates with availability doubt: Justin Jefferson, Carson Wentz.
- **Benchmark FC:** 7.66 (floor 0.0, ceiling 23.06). Our projection: NOT BUILT.
- **Flags:** ROLE_CHANGE: snap share up 16 pp | FC_VS_RECENT_PRODUCTION: FC 7.66 vs 2026 DK avg 12.62
- **Missing model dependencies:** QB-conditioned team volume / shares NOT consumed by the engine (W5-G1); 4-game pooled usage does not separate a role change from a one-game anomaly (W5-G8); accounting repair pending (D-05) affects all players.
- **Next research action:** decompose FC vs recent production: volume, efficiency or availability assumption; read the last two games: is the snap change a role change, an injury exit or game script?.

### Tai Felton (WR, $3000)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['WR4'].
- **2026:** 4 games, DK average 0.6, last game 2.4 (week 4).
- **What drives his production:** 2026 target share 3%; snap share trend +54 pp (last 2 vs first 2 games); game total 41.5 (nflverse schedule line), away, roof dome, rest 7 days; club QB: Kyler Murray (attempt leaders by week {'1': 'C.Wentz', '2': 'C.Wentz', '3': 'K.Murray', '4': 'K.Murray'}); teammates with availability doubt: Justin Jefferson, Carson Wentz.
- **Benchmark FC:** 0.79 (floor 0.0, ceiling 2.59). Our projection: NOT BUILT.
- **Flags:** ROLE_CHANGE: snap share up 54 pp
- **Missing model dependencies:** QB-conditioned team volume / shares NOT consumed by the engine (W5-G1); 4-game pooled usage does not separate a role change from a one-game anomaly (W5-G8); accounting repair pending (D-05) affects all players.
- **Next research action:** read the last two games: is the snap change a role change, an injury exit or game script?.

### DeeJay Dallas (RB, $4000)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['RB2'].
- **2026:** 4 games, DK average 1.57, last game 2.0 (week 4).
- **What drives his production:** 2026 target share 3%, carry share 3%; snap share trend +3 pp (last 2 vs first 2 games); game total 41.5 (nflverse schedule line), away, roof dome, rest 7 days; club QB: Kyler Murray (attempt leaders by week {'1': 'C.Wentz', '2': 'C.Wentz', '3': 'K.Murray', '4': 'K.Murray'}); teammates with availability doubt: Justin Jefferson, Carson Wentz.
- **Benchmark FC:** 0.63 (floor 0.0, ceiling 8.63). Our projection: NOT BUILT.
- **Missing model dependencies:** QB-conditioned team volume / shares NOT consumed by the engine (W5-G1); accounting repair pending (D-05) affects all players.
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

## NE vs LV

### Drake Maye (QB, $6300)
- **Eligibility:** ELIGIBLE (ACT). Practice: Full Participation in Practice (Shoulder). Designation: NOT_YET_ISSUED (designations are issued Friday; absence is not health). Depth: ['QB1'].
- **2026:** 4 games, DK average 14.19, last game 28.16 (week 4).
- **What drives his production:** red zone 2026: 0 targets, 3 carries; snap share trend -10 pp (last 2 vs first 2 games); game total 45.5 (nflverse schedule line), home, roof outdoors, rest 7 days; club QB: Drake Maye (attempt leaders by week {'1': 'D.Maye', '2': 'D.Maye', '3': 'D.Maye', '4': 'D.Maye'}); teammates with availability doubt: Mack Hollins, Tommy DeVito, Reggie Gilliam, Tanner Arkin.
- **Reported [CONFIRMED]:** Drake Maye (right shoulder, 'dinged' in the W3 35-6 loss to JAX) had no designation in W4 vs BUF and played. Week 5: listed with the shoulder, full participant Thursday. (https://www.bostonglobe.com/2026/10/02/sports/mike-vrabel-drake-maye-shoulder/)
- **Benchmark FC:** 15.99 (floor 5.19, ceiling 30.39). Our projection: NOT BUILT.
- **Missing model dependencies:** lower-tail volatility under-stated for high-mean players (D-01).
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### TreVeyon Henderson (RB, $5000)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['RB2'].
- **2026:** 3 games, DK average 7.23, last game 4.2 (week 4).
- **What drives his production:** 2026 target share 3%, carry share 43%; red zone 2026: 0 targets, 2 carries; snap share trend -12 pp (last 2 vs first 2 games); game total 45.5 (nflverse schedule line), home, roof outdoors, rest 7 days; club QB: Drake Maye (attempt leaders by week {'1': 'D.Maye', '2': 'D.Maye', '3': 'D.Maye', '4': 'D.Maye'}); teammates with availability doubt: Mack Hollins, Tommy DeVito, Reggie Gilliam, Tanner Arkin.
- **Benchmark FC:** 12.79 (floor 0.0, ceiling 31.79). Our projection: NOT BUILT.
- **Flags:** FC_VS_RECENT_PRODUCTION: FC 12.79 vs 2026 DK avg 7.23
- **Missing model dependencies:** accounting repair pending (D-05) affects all players.
- **Next research action:** decompose FC vs recent production: volume, efficiency or availability assumption.

### Rhamondre Stevenson (RB, $5500)
- **Eligibility:** ELIGIBLE (ACT). Practice: Limited Participation in Practice (Knee). Designation: NOT_YET_ISSUED (designations are issued Friday; absence is not health). Depth: ['RB1'].
- **2026:** 4 games, DK average 11.07, last game 18.4 (week 4).
- **What drives his production:** 2026 target share 13%, carry share 36%; red zone 2026: 0 targets, 2 carries; snap share trend -2 pp (last 2 vs first 2 games); game total 45.5 (nflverse schedule line), home, roof outdoors, rest 7 days; club QB: Drake Maye (attempt leaders by week {'1': 'D.Maye', '2': 'D.Maye', '3': 'D.Maye', '4': 'D.Maye'}); teammates with availability doubt: Mack Hollins, Tommy DeVito, Reggie Gilliam, Tanner Arkin.
- **Reported [CONFIRMED]:** DNP Wednesday: WR Mack Hollins (calf), CB Christian Gonzalez (shoulder; 5 straight missed practices), CB Carlton Davis III (neck), CB Karon Prunty (hamstring). FB Reggie Gilliam (ankle/knee) went limited to DNP Thursday. Limited: RB Rhamondre Stevenson (knee), DT Christian Barmore (shoulder), LB Christian Elliss (chest), S Craig Woodson (shoulder). SI headline: 'Offensive starter returns, top CBs remain out.' (https://www.patspulpit.com/new-england-patriots-news/139791/patriots-vs-raiders-wednesday-injury-report-mack-hollins-christian-gonzalez-carlton-davis-karon-prunty-sidelined)
- **Benchmark FC:** 11.42 (floor 0.0, ceiling 28.02). Our projection: NOT BUILT.
- **Missing model dependencies:** practice participation does not change a projection until a designation; no partial-workload model (W5-G4); accounting repair pending (D-05) affects all players.
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### Mack Hollins (WR, $4200)
- **Eligibility:** ELIGIBLE (ACT). Practice: Did Not Participate In Practice (Calf). Designation: NOT_YET_ISSUED (designations are issued Friday; absence is not health). Depth: ['WR3'].
- **2026:** 4 games, DK average 8.97, last game 8.3 (week 4).
- **What drives his production:** 2026 target share 17%; red zone 2026: 4 targets, 0 carries; snap share trend -12 pp (last 2 vs first 2 games); game total 45.5 (nflverse schedule line), home, roof outdoors, rest 7 days; club QB: Drake Maye (attempt leaders by week {'1': 'D.Maye', '2': 'D.Maye', '3': 'D.Maye', '4': 'D.Maye'}); teammates with availability doubt: Tommy DeVito, Reggie Gilliam, Tanner Arkin.
- **Reported [CONFIRMED]:** DNP Wednesday: WR Mack Hollins (calf), CB Christian Gonzalez (shoulder; 5 straight missed practices), CB Carlton Davis III (neck), CB Karon Prunty (hamstring). FB Reggie Gilliam (ankle/knee) went limited to DNP Thursday. Limited: RB Rhamondre Stevenson (knee), DT Christian Barmore (shoulder), LB Christian Elliss (chest), S Craig Woodson (shoulder). SI headline: 'Offensive starter returns, top CBs remain out.' (https://www.patspulpit.com/new-england-patriots-news/139791/patriots-vs-raiders-wednesday-injury-report-mack-hollins-christian-gonzalez-carlton-davis-karon-prunty-sidelined)
- **Benchmark FC:** 9.59 (floor 1.34, ceiling 20.59). Our projection: NOT BUILT.
- **Flags:** DID_NOT_PRACTICE
- **Missing model dependencies:** practice participation does not change a projection until a designation; no partial-workload model (W5-G4); accounting repair pending (D-05) affects all players.
- **Next research action:** capture Friday designation; if OUT, check redistribution to same-position teammates.

### Romeo Doubs (WR, $5000)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['WR1'].
- **2026:** 4 games, DK average 11.07, last game 23.8 (week 4).
- **What drives his production:** 2026 target share 17%; red zone 2026: 4 targets, 0 carries; snap share trend +7 pp (last 2 vs first 2 games); game total 45.5 (nflverse schedule line), home, roof outdoors, rest 7 days; club QB: Drake Maye (attempt leaders by week {'1': 'D.Maye', '2': 'D.Maye', '3': 'D.Maye', '4': 'D.Maye'}); teammates with availability doubt: Mack Hollins, Tommy DeVito, Reggie Gilliam, Tanner Arkin.
- **Benchmark FC:** 9.05 (floor 0.0, ceiling 22.05). Our projection: NOT BUILT.
- **Missing model dependencies:** accounting repair pending (D-05) affects all players.
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### Hunter Henry (TE, $3700)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['TE1'].
- **2026:** 4 games, DK average 6.32, last game 11.2 (week 4).
- **What drives his production:** 2026 target share 14%; red zone 2026: 1 targets, 0 carries; snap share trend -16 pp (last 2 vs first 2 games); game total 45.5 (nflverse schedule line), home, roof outdoors, rest 7 days; club QB: Drake Maye (attempt leaders by week {'1': 'D.Maye', '2': 'D.Maye', '3': 'D.Maye', '4': 'D.Maye'}); teammates with availability doubt: Mack Hollins, Tommy DeVito, Reggie Gilliam, Tanner Arkin.
- **Benchmark FC:** 8.72 (floor 0.0, ceiling 21.32). Our projection: NOT BUILT.
- **Flags:** ROLE_CHANGE: snap share down 16 pp
- **Missing model dependencies:** 4-game pooled usage does not separate a role change from a one-game anomaly (W5-G8); accounting repair pending (D-05) affects all players.
- **Next research action:** read the last two games: is the snap change a role change, an injury exit or game script?.

### Patriots (DST, $3000)
- **Eligibility:** ELIGIBLE_BY_CONSTRUCTION. Practice: not on report. Designation: n/a. Depth: None.
- **What drives his production:** opponent LV QB Kirk Cousins; opponent QB flags []; game total 45.5.
- **Benchmark FC:** 6.5 (floor 0.0, ceiling 20.1). Our projection: NOT BUILT.
- **Missing model dependencies:** opponent QB identity not consumed by DST model (D-02); turnovers not event-linked (D-05).
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### Demario Douglas (WR, $3500)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['WR2'].
- **2026:** 4 games, DK average 4.3, last game 3.5 (week 4).
- **What drives his production:** 2026 target share 14%; red zone 2026: 2 targets, 0 carries; snap share trend -2 pp (last 2 vs first 2 games); game total 45.5 (nflverse schedule line), home, roof outdoors, rest 7 days; club QB: Drake Maye (attempt leaders by week {'1': 'D.Maye', '2': 'D.Maye', '3': 'D.Maye', '4': 'D.Maye'}); teammates with availability doubt: Mack Hollins, Tommy DeVito, Reggie Gilliam, Tanner Arkin.
- **Benchmark FC:** 4.35 (floor 0.0, ceiling 14.15). Our projection: NOT BUILT.
- **Missing model dependencies:** accounting repair pending (D-05) affects all players.
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### Efton Chism III (WR, $3200)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['WR4'].
- **2026:** 3 games, DK average 4.91, last game 12.2 (week 4).
- **What drives his production:** 2026 target share 8%; red zone 2026: 1 targets, 0 carries; snap share trend +14 pp (last 2 vs first 2 games); game total 45.5 (nflverse schedule line), home, roof outdoors, rest 7 days; club QB: Drake Maye (attempt leaders by week {'1': 'D.Maye', '2': 'D.Maye', '3': 'D.Maye', '4': 'D.Maye'}); teammates with availability doubt: Mack Hollins, Tommy DeVito, Reggie Gilliam, Tanner Arkin.
- **Reported [CONFIRMED]:** DNP Wednesday: WR Mack Hollins (calf), CB Christian Gonzalez (shoulder; 5 straight missed practices), CB Carlton Davis III (neck), CB Karon Prunty (hamstring). FB Reggie Gilliam (ankle/knee) went limited to DNP Thursday. Limited: RB Rhamondre Stevenson (knee), DT Christian Barmore (shoulder), LB Christian Elliss (chest), S Craig Woodson (shoulder). SI headline: 'Offensive starter returns, top CBs remain out.' (https://www.patspulpit.com/new-england-patriots-news/139791/patriots-vs-raiders-wednesday-injury-report-mack-hollins-christian-gonzalez-carlton-davis-karon-prunty-sidelined)
- **Benchmark FC:** 3.28 (floor 0.0, ceiling 12.68). Our projection: NOT BUILT.
- **Missing model dependencies:** accounting repair pending (D-05) affects all players.
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

## NO vs MIN

### Tyler Shough (QB, $6100)
- **Eligibility:** ELIGIBLE (ACT). Practice: Full Participation in Practice (Hand). Designation: NOT_YET_ISSUED (designations are issued Friday; absence is not health). Depth: ['QB1'].
- **2026:** 4 games, DK average 23.58, last game 15.94 (week 4).
- **What drives his production:** red zone 2026: 0 targets, 5 carries; snap share trend +0 pp (last 2 vs first 2 games); game total 41.5 (nflverse schedule line), home, roof dome, rest 6 days; club QB: Tyler Shough (attempt leaders by week {'1': 'T.Shough', '2': 'T.Shough', '3': 'T.Shough', '4': 'T.Shough'}); teammates with availability doubt: Noah Fant.
- **Reported [CONFIRMED]:** Tyler Shough has started W1-W4 (W4: 30/48, 286 yds, 1 TD in the 45-24 MNF loss to ATL; team 1-3). He hurt his non-throwing left hand in W4 and says it won't limit him. Thursday: full per one summary. (https://fieldlevelmedia.com/news/saints-qb-tyler-shough-dealing-with-sore-left-hand-expects-to-play-sunday/)
- **Reported [CONFLICTING]:** Shough's Wednesday practice status: limited (SI headline, Fantasy Footballers, AtoZ) vs full ('FP', Vikings.com copy of the Saints report) vs sat out (another summary). (https://www.si.com/nfl/saints/onsi/saints-injury-report-shough-limited-kamara-sidelined-ahead-of-vikings-01m4c8j54fy9)
- **Benchmark FC:** 21.12 (floor 9.27, ceiling 36.92). Our projection: NOT BUILT.
- **Missing model dependencies:** lower-tail volatility under-stated for high-mean players (D-01).
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### Chris Olave (WR, $7700)
- **Eligibility:** ELIGIBLE (ACT). Practice: Limited Participation in Practice (Not injury related - resting player, Foot). Designation: NOT_YET_ISSUED (designations are issued Friday; absence is not health). Depth: ['WR1'].
- **2026:** 4 games, DK average 24.77, last game 22.6 (week 4).
- **What drives his production:** 2026 target share 28%; red zone 2026: 5 targets, 0 carries; snap share trend +0 pp (last 2 vs first 2 games); game total 41.5 (nflverse schedule line), home, roof dome, rest 6 days; club QB: Tyler Shough (attempt leaders by week {'1': 'T.Shough', '2': 'T.Shough', '3': 'T.Shough', '4': 'T.Shough'}); teammates with availability doubt: Noah Fant.
- **Reported [CONFIRMED]:** RB Alvin Kamara (back): DNP Wednesday, limited Thursday. WR Chris Olave: rest day Wednesday, limited Thursday with a new foot injury. Barion Brown (thigh) returned Thursday. Rookie OL Jeremiah Wright limited (in concussion protocol). (https://sports.yahoo.com/articles/thursday-saints-vs-vikings-injury-220030228.html)
- **Benchmark FC:** 18.17 (floor 6.47, ceiling 33.77). Our projection: NOT BUILT.
- **Missing model dependencies:** practice participation does not change a projection until a designation; no partial-workload model (W5-G4); lower-tail volatility under-stated for high-mean players (D-01).
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### Alvin Kamara (RB, $5400)
- **Eligibility:** ELIGIBLE (ACT). Practice: Limited Participation in Practice (Back). Designation: NOT_YET_ISSUED (designations are issued Friday; absence is not health). Depth: ['RB1'].
- **2026:** 3 games, DK average 11.7, last game 22.8 (week 4).
- **What drives his production:** 2026 target share 12%, carry share 34%; red zone 2026: 1 targets, 5 carries; snap share trend +4 pp (last 2 vs first 2 games); game total 41.5 (nflverse schedule line), home, roof dome, rest 6 days; club QB: Tyler Shough (attempt leaders by week {'1': 'T.Shough', '2': 'T.Shough', '3': 'T.Shough', '4': 'T.Shough'}); teammates with availability doubt: Noah Fant.
- **Reported [CONFIRMED]:** RB Alvin Kamara (back): DNP Wednesday, limited Thursday. WR Chris Olave: rest day Wednesday, limited Thursday with a new foot injury. Barion Brown (thigh) returned Thursday. Rookie OL Jeremiah Wright limited (in concussion protocol). (https://sports.yahoo.com/articles/thursday-saints-vs-vikings-injury-220030228.html)
- **Benchmark FC:** 12.21 (floor 0.0, ceiling 33.01). Our projection: NOT BUILT.
- **Missing model dependencies:** practice participation does not change a projection until a designation; no partial-workload model (W5-G4); accounting repair pending (D-05) affects all players.
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### Juwan Johnson (TE, $4500)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['TE1'].
- **2026:** 4 games, DK average 15.3, last game 11.9 (week 4).
- **What drives his production:** 2026 target share 16%; red zone 2026: 7 targets, 0 carries; snap share trend +2 pp (last 2 vs first 2 games); game total 41.5 (nflverse schedule line), home, roof dome, rest 6 days; club QB: Tyler Shough (attempt leaders by week {'1': 'T.Shough', '2': 'T.Shough', '3': 'T.Shough', '4': 'T.Shough'}); teammates with availability doubt: Noah Fant.
- **Benchmark FC:** 11.78 (floor 2.78, ceiling 23.78). Our projection: NOT BUILT.
- **Missing model dependencies:** accounting repair pending (D-05) affects all players.
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### Devaughn Vele (WR, $5200)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['WR2'].
- **2026:** 4 games, DK average 13.9, last game 17.4 (week 4).
- **What drives his production:** 2026 target share 18%; red zone 2026: 6 targets, 0 carries; snap share trend -5 pp (last 2 vs first 2 games); game total 41.5 (nflverse schedule line), home, roof dome, rest 6 days; club QB: Tyler Shough (attempt leaders by week {'1': 'T.Shough', '2': 'T.Shough', '3': 'T.Shough', '4': 'T.Shough'}); teammates with availability doubt: Noah Fant.
- **Benchmark FC:** 11.68 (floor 2.83, ceiling 23.48). Our projection: NOT BUILT.
- **Missing model dependencies:** accounting repair pending (D-05) affects all players.
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### Kevin Austin Jr. (WR, $3000)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['WR4'].
- **2026:** 4 games, DK average 0.42, last game 0.0 (week 4).
- **What drives his production:** 2026 target share 1%; snap share trend +6 pp (last 2 vs first 2 games); game total 41.5 (nflverse schedule line), home, roof dome, rest 6 days; club QB: Tyler Shough (attempt leaders by week {'1': 'T.Shough', '2': 'T.Shough', '3': 'T.Shough', '4': 'T.Shough'}); teammates with availability doubt: Noah Fant.
- **Benchmark FC:** 7.02 (floor 1.47, ceiling 14.42). Our projection: NOT BUILT.
- **Flags:** FC_VS_RECENT_PRODUCTION: FC 7.02 vs 2026 DK avg 0.42
- **Missing model dependencies:** accounting repair pending (D-05) affects all players.
- **Next research action:** decompose FC vs recent production: volume, efficiency or availability assumption.

### Saints (DST, $2600)
- **Eligibility:** ELIGIBLE_BY_CONSTRUCTION. Practice: not on report. Designation: n/a. Depth: None.
- **What drives his production:** opponent MIN QB Kyler Murray; opponent QB flags ['QB_REGIME_CHANGE: listed starter is not the dominant passer of the modelling window']; game total 41.5.
- **Reported [CONFLICTING]:** Shough's Wednesday practice status: limited (SI headline, Fantasy Footballers, AtoZ) vs full ('FP', Vikings.com copy of the Saints report) vs sat out (another summary). (https://www.si.com/nfl/saints/onsi/saints-injury-report-shough-limited-kamara-sidelined-ahead-of-vikings-01m4c8j54fy9)
- **Reported [REPORTED]:** Saints played Monday Night (W4), so this is a short week. (https://fieldlevelmedia.com/news/saints-qb-tyler-shough-dealing-with-sore-left-hand-expects-to-play-sunday/)
- **Benchmark FC:** 5.42 (floor 0.0, ceiling 17.22). Our projection: NOT BUILT.
- **Missing model dependencies:** opponent QB identity not consumed by DST model (D-02); turnovers not event-linked (D-05).
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### Noah Fant (TE, $3000)
- **Eligibility:** ELIGIBLE (ACT). Practice: Limited Participation in Practice (Abdomen). Designation: NOT_YET_ISSUED (designations are issued Friday; absence is not health). Depth: ['TE2'].
- **2026:** 3 games, DK average 10.87, last game 19.3 (week 3).
- **What drives his production:** 2026 target share 8%; red zone 2026: 3 targets, 0 carries; snap share trend +8 pp (last 2 vs first 2 games); game total 41.5 (nflverse schedule line), home, roof dome, rest 6 days; club QB: Tyler Shough (attempt leaders by week {'1': 'T.Shough', '2': 'T.Shough', '3': 'T.Shough', '4': 'T.Shough'}).
- **Benchmark FC:** 4.99 (floor 0.0, ceiling 15.99). Our projection: NOT BUILT.
- **Flags:** MISSED_LAST_GAME: no participation in week 4 | FC_VS_RECENT_PRODUCTION: FC 4.99 vs 2026 DK avg 10.87
- **Missing model dependencies:** practice participation does not change a projection until a designation; no partial-workload model (W5-G4); accounting repair pending (D-05) affects all players.
- **Next research action:** decompose FC vs recent production: volume, efficiency or availability assumption; verify return status and any snap limit; compare to pre-injury usage.

### Kendre Miller (RB, $4900)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['RB2'].
- **2026:** 3 games, DK average 5.27, last game 2.9 (week 4).
- **What drives his production:** 2026 target share 5%, carry share 27%; red zone 2026: 1 targets, 2 carries; snap share trend -2 pp (last 2 vs first 2 games); game total 41.5 (nflverse schedule line), home, roof dome, rest 6 days; club QB: Tyler Shough (attempt leaders by week {'1': 'T.Shough', '2': 'T.Shough', '3': 'T.Shough', '4': 'T.Shough'}); teammates with availability doubt: Noah Fant.
- **Benchmark FC:** 4.19 (floor 0.0, ceiling 11.79). Our projection: NOT BUILT.
- **Missing model dependencies:** accounting repair pending (D-05) affects all players.
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### Bryce Lance (WR, $3000)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['WR3'].
- **2026:** 4 games, DK average 2.67, last game 1.7 (week 4).
- **What drives his production:** 2026 target share 7%; red zone 2026: 1 targets, 0 carries; snap share trend +4 pp (last 2 vs first 2 games); game total 41.5 (nflverse schedule line), home, roof dome, rest 6 days; club QB: Tyler Shough (attempt leaders by week {'1': 'T.Shough', '2': 'T.Shough', '3': 'T.Shough', '4': 'T.Shough'}); teammates with availability doubt: Noah Fant.
- **Benchmark FC:** 3.27 (floor 0.0, ceiling 8.67). Our projection: NOT BUILT.
- **Missing model dependencies:** accounting repair pending (D-05) affects all players.
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

## NYG vs WAS

### Jameis Winston (QB, $4800)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['QB1'].
- **2026:** 3 games, DK average 9.89, last game 20.0 (week 4).
- **What drives his production:** snap share trend +6 pp (last 2 vs first 2 games); game total 42.5 (nflverse schedule line), away, roof outdoors, rest 7 days; club QB: Jameis Winston (attempt leaders by week {'1': 'J.Dart', '2': 'J.Winston', '3': 'J.Winston', '4': 'J.Winston'}); teammates with availability doubt: Devin Singletary.
- **Reported [CONFIRMED]:** Jameis Winston is the starter; Harbaugh: 'He'll be the starter.' Jaxson Dart started W1 and W2, then hurt his left knee (MCL/PCL/meniscus) on the opening drive of the W2 MNF loss at LAR and is out for the regular season. Winston started W3 (vs TEN) and W4 (W 36-24 vs ARI; 18/29, 250 yds, 3 TD). (https://www.giants.com/news/jaxson-dart-to-miss-rest-of-regular-season-jameis-winston-to-start-quarterback-injury-john-harbaugh)
- **Benchmark FC:** 15.8 (floor 1.1, ceiling 35.4). Our projection: NOT BUILT.
- **Flags:** FC_VS_RECENT_PRODUCTION: FC 15.8 vs 2026 DK avg 9.89
- **Missing model dependencies:** lower-tail volatility under-stated for high-mean players (D-01).
- **Next research action:** decompose FC vs recent production: volume, efficiency or availability assumption.

### Cam Skattebo (RB, $6000)
- **Eligibility:** ELIGIBLE (ACT). Practice: Limited Participation in Practice (Shoulder). Designation: NOT_YET_ISSUED (designations are issued Friday; absence is not health). Depth: ['RB1'].
- **2026:** 4 games, DK average 11.05, last game 7.6 (week 4).
- **What drives his production:** 2026 target share 9%, carry share 58%; red zone 2026: 0 targets, 11 carries; snap share trend +10 pp (last 2 vs first 2 games); game total 42.5 (nflverse schedule line), away, roof outdoors, rest 7 days; club QB: Jameis Winston (attempt leaders by week {'1': 'J.Dart', '2': 'J.Winston', '3': 'J.Winston', '4': 'J.Winston'}); teammates with availability doubt: Devin Singletary.
- **Reported [CONFLICTING]:** RB Cam Skattebo (shoulder) limited Wednesday in a no-contact jersey. Thursday: 'shed' the jersey (Newsweek) vs limited both days (Bolavip). RB Najee Harris missed for personal reasons, then was full Thursday. DL Chauncey Golston is seeking second opinions on a possible long-term injury. (https://www.newsweek.com/sports/nfl/giants-get-positive-cam-skattebo-malik-nabers-injury-news-12543334)
- **Benchmark FC:** 14.12 (floor 3.47, ceiling 28.32). Our projection: NOT BUILT.
- **Missing model dependencies:** practice participation does not change a projection until a designation; no partial-workload model (W5-G4); accounting repair pending (D-05) affects all players.
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### Malik Nabers (WR, $6300)
- **Eligibility:** ELIGIBLE (ACT). Practice: Limited Participation in Practice (Knee). Designation: NOT_YET_ISSUED (designations are issued Friday; absence is not health). Depth: ['WR1'].
- **2026:** 4 games, DK average 11.95, last game 26.2 (week 4).
- **What drives his production:** 2026 target share 24%; red zone 2026: 3 targets, 0 carries; snap share trend +14 pp (last 2 vs first 2 games); game total 42.5 (nflverse schedule line), away, roof outdoors, rest 7 days; club QB: Jameis Winston (attempt leaders by week {'1': 'J.Dart', '2': 'J.Winston', '3': 'J.Winston', '4': 'J.Winston'}); teammates with availability doubt: Devin Singletary.
- **Reported [CONFIRMED]:** WR Malik Nabers (knee soreness) DNP Wednesday, limited Thursday; he says 'We'll see.' LT Andrew Thomas (groin) DNP to limited (weekly maintenance pattern). (https://www.giants.com/news/giants-vs-commanders-week-5-injury-report-malik-nabers-andrew-thomas-cam-skattebo)
- **Benchmark FC:** 13.21 (floor 0.0, ceiling 34.21). Our projection: NOT BUILT.
- **Missing model dependencies:** practice participation does not change a projection until a designation; no partial-workload model (W5-G4); accounting repair pending (D-05) affects all players.
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### Isaiah Likely (TE, $4300)
- **Eligibility:** ELIGIBLE (ACT). Practice: Limited Participation in Practice (Knee, Groin). Designation: NOT_YET_ISSUED (designations are issued Friday; absence is not health). Depth: ['TE1'].
- **2026:** 4 games, DK average 13.25, last game 13.6 (week 4).
- **What drives his production:** 2026 target share 31%; red zone 2026: 6 targets, 0 carries; snap share trend +16 pp (last 2 vs first 2 games); game total 42.5 (nflverse schedule line), away, roof outdoors, rest 7 days; club QB: Jameis Winston (attempt leaders by week {'1': 'J.Dart', '2': 'J.Winston', '3': 'J.Winston', '4': 'J.Winston'}); teammates with availability doubt: Devin Singletary.
- **Benchmark FC:** 12.08 (floor 1.88, ceiling 25.68). Our projection: NOT BUILT.
- **Flags:** ROLE_CHANGE: snap share up 16 pp
- **Missing model dependencies:** 4-game pooled usage does not separate a role change from a one-game anomaly (W5-G8); practice participation does not change a projection until a designation; no partial-workload model (W5-G4); accounting repair pending (D-05) affects all players.
- **Next research action:** read the last two games: is the snap change a role change, an injury exit or game script?.

### Theo Johnson (TE, $2600)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['TE2'].
- **2026:** 4 games, DK average 2.5, last game 8.1 (week 4).
- **What drives his production:** 2026 target share 5%; red zone 2026: 1 targets, 0 carries; snap share trend -12 pp (last 2 vs first 2 games); game total 42.5 (nflverse schedule line), away, roof outdoors, rest 7 days; club QB: Jameis Winston (attempt leaders by week {'1': 'J.Dart', '2': 'J.Winston', '3': 'J.Winston', '4': 'J.Winston'}); teammates with availability doubt: Devin Singletary.
- **Benchmark FC:** 8.23 (floor 0.58, ceiling 18.43). Our projection: NOT BUILT.
- **Flags:** FC_VS_RECENT_PRODUCTION: FC 8.23 vs 2026 DK avg 2.5
- **Missing model dependencies:** accounting repair pending (D-05) affects all players.
- **Next research action:** decompose FC vs recent production: volume, efficiency or availability assumption.

### Giants (DST, $2600)
- **Eligibility:** ELIGIBLE_BY_CONSTRUCTION. Practice: not on report. Designation: n/a. Depth: None.
- **What drives his production:** opponent WAS QB Jayden Daniels; opponent QB flags ['QB_DIFFERS_FROM_LAST_GAME: week 4 passer A.Kaliakmanis, listed Jayden Daniels', 'QB_CHURN: 3 different attempt leaders in 4 games']; game total 42.5.
- **Benchmark FC:** 7.74 (floor 0.0, ceiling 19.54). Our projection: NOT BUILT.
- **Missing model dependencies:** opponent QB identity not consumed by DST model (D-02); turnovers not event-linked (D-05).
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### Malachi Fields (WR, $4300)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['WR2'].
- **2026:** 4 games, DK average 6.65, last game 13.2 (week 4).
- **What drives his production:** 2026 target share 13%; red zone 2026: 1 targets, 0 carries; snap share trend -9 pp (last 2 vs first 2 games); game total 42.5 (nflverse schedule line), away, roof outdoors, rest 7 days; club QB: Jameis Winston (attempt leaders by week {'1': 'J.Dart', '2': 'J.Winston', '3': 'J.Winston', '4': 'J.Winston'}); teammates with availability doubt: Devin Singletary.
- **Benchmark FC:** 7.46 (floor 1.76, ceiling 15.06). Our projection: NOT BUILT.
- **Missing model dependencies:** accounting repair pending (D-05) affects all players.
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### Darnell Mooney (WR, $3800)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['WR3'].
- **2026:** 4 games, DK average 4.1, last game 0.0 (week 4).
- **What drives his production:** 2026 target share 9%, carry share 1%; snap share trend -15 pp (last 2 vs first 2 games); game total 42.5 (nflverse schedule line), away, roof outdoors, rest 7 days; club QB: Jameis Winston (attempt leaders by week {'1': 'J.Dart', '2': 'J.Winston', '3': 'J.Winston', '4': 'J.Winston'}); teammates with availability doubt: Devin Singletary.
- **Benchmark FC:** 6.92 (floor 0.0, ceiling 20.72). Our projection: NOT BUILT.
- **Flags:** ROLE_CHANGE: snap share down 15 pp
- **Missing model dependencies:** 4-game pooled usage does not separate a role change from a one-game anomaly (W5-G8); accounting repair pending (D-05) affects all players.
- **Next research action:** read the last two games: is the snap change a role change, an injury exit or game script?.

### Najee Harris (RB, $4500)
- **Eligibility:** ELIGIBLE (ACT). Practice: Full Participation in Practice (Not injury related - personal matter). Designation: NOT_YET_ISSUED (designations are issued Friday; absence is not health). Depth: ['RB2'].
- **2026:** 3 games, DK average 3.27, last game 4.0 (week 4).
- **What drives his production:** 2026 target share 0%, carry share 26%; 2026 carry share 26%; red zone 2026: 0 targets, 6 carries; snap share trend +2 pp (last 2 vs first 2 games); game total 42.5 (nflverse schedule line), away, roof outdoors, rest 7 days; club QB: Jameis Winston (attempt leaders by week {'1': 'J.Dart', '2': 'J.Winston', '3': 'J.Winston', '4': 'J.Winston'}); teammates with availability doubt: Devin Singletary.
- **Reported [CONFLICTING]:** RB Cam Skattebo (shoulder) limited Wednesday in a no-contact jersey. Thursday: 'shed' the jersey (Newsweek) vs limited both days (Bolavip). RB Najee Harris missed for personal reasons, then was full Thursday. DL Chauncey Golston is seeking second opinions on a possible long-term injury. (https://www.newsweek.com/sports/nfl/giants-get-positive-cam-skattebo-malik-nabers-injury-news-12543334)
- **Benchmark FC:** 4.87 (floor 0.0, ceiling 19.87). Our projection: NOT BUILT.
- **Missing model dependencies:** accounting repair pending (D-05) affects all players.
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### Charlie Jones (WR, $3000)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['WR4'].
- **2026:** 1 games, DK average 0.0, last game 0.0 (week 4).
- **What drives his production:** 2026 target share 0%; game total 42.5 (nflverse schedule line), away, roof outdoors, rest 7 days; club QB: Jameis Winston (attempt leaders by week {'1': 'J.Dart', '2': 'J.Winston', '3': 'J.Winston', '4': 'J.Winston'}); teammates with availability doubt: Devin Singletary.
- **Benchmark FC:** 0.11 (floor 0.0, ceiling 3.51). Our projection: NOT BUILT.
- **Missing model dependencies:** accounting repair pending (D-05) affects all players.
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

## NYJ vs CLE

### Geno Smith (QB, $5000)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['QB1'].
- **2026:** 4 games, DK average 15.92, last game 8.76 (week 4).
- **What drives his production:** red zone 2026: 0 targets, 1 carries; snap share trend +0 pp (last 2 vs first 2 games); game total 39.5 (nflverse schedule line), home, roof outdoors, rest 7 days; club QB: Geno Smith (attempt leaders by week {'1': 'G.Smith', '2': 'G.Smith', '3': 'G.Smith', '4': 'G.Smith'}); teammates with availability doubt: Mason Taylor, Jamaal Pritchett.
- **Reported [REPORTED]:** Geno Smith is the starter (902 yds, 72.7%, 5 TD per NFL.com). W4 loss at CHI: 8/15, 119 yds, 1 TD, 5 sacks; W3: 321 yds, 3 TD vs DET. I found no change for Week 5. (https://www.nbcsports.com/fantasy/football/player-news/2026-10-04/geno-has-8-completions-in-week-4-loss)
- **Benchmark FC:** 16.81 (floor 4.36, ceiling 33.41). Our projection: NOT BUILT.
- **Missing model dependencies:** lower-tail volatility under-stated for high-mean players (D-01).
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### Garrett Wilson (WR, $6600)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['WR1'].
- **2026:** 4 games, DK average 16.5, last game 5.7 (week 4).
- **What drives his production:** 2026 target share 28%; red zone 2026: 1 targets, 0 carries; snap share trend +16 pp (last 2 vs first 2 games); game total 39.5 (nflverse schedule line), home, roof outdoors, rest 7 days; club QB: Geno Smith (attempt leaders by week {'1': 'G.Smith', '2': 'G.Smith', '3': 'G.Smith', '4': 'G.Smith'}); teammates with availability doubt: Mason Taylor, Jamaal Pritchett.
- **Reported [REPORTED]:** RB Breece Hall (quad), WR Adonai Mitchell, G Dylan Parham, LB Kiko (Francisco) Mauigoa: DNP Wednesday and Thursday, read as 'essentially' out for Week 5. CB Jarvis Brownlee Jr. (concussion) DNP to limited. Edge Kingsley Enagbare (knee) limited both days. No Week 5 listing found for WR Garrett Wilson. (https://www.newyorkjets.com/news/jets-injury-report-week-5-vs-browns-thursday-10-07-20268)
- **Benchmark FC:** 15.99 (floor 4.14, ceiling 31.79). Our projection: NOT BUILT.
- **Flags:** ROLE_CHANGE: snap share up 16 pp
- **Missing model dependencies:** 4-game pooled usage does not separate a role change from a one-game anomaly (W5-G8); lower-tail volatility under-stated for high-mean players (D-01).
- **Next research action:** read the last two games: is the snap change a role change, an injury exit or game script?.

### Braelon Allen (RB, $5400)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['RB2'].
- **2026:** 4 games, DK average 6.47, last game 8.7 (week 4).
- **What drives his production:** 2026 target share 7%, carry share 41%; red zone 2026: 3 targets, 5 carries; snap share trend +38 pp (last 2 vs first 2 games); game total 39.5 (nflverse schedule line), home, roof outdoors, rest 7 days; club QB: Geno Smith (attempt leaders by week {'1': 'G.Smith', '2': 'G.Smith', '3': 'G.Smith', '4': 'G.Smith'}); teammates with availability doubt: Mason Taylor, Jamaal Pritchett.
- **Benchmark FC:** 13.13 (floor 6.68, ceiling 21.73). Our projection: NOT BUILT.
- **Flags:** ROLE_CHANGE: snap share up 38 pp | FC_VS_RECENT_PRODUCTION: FC 13.13 vs 2026 DK avg 6.47
- **Missing model dependencies:** 4-game pooled usage does not separate a role change from a one-game anomaly (W5-G8); accounting repair pending (D-05) affects all players.
- **Next research action:** decompose FC vs recent production: volume, efficiency or availability assumption; read the last two games: is the snap change a role change, an injury exit or game script?.

### Kenyon Sadiq (TE, $3800)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['TE1'].
- **2026:** 4 games, DK average 10.4, last game 0.0 (week 4).
- **What drives his production:** 2026 target share 18%, carry share 1%; red zone 2026: 0 targets, 1 carries; snap share trend +24 pp (last 2 vs first 2 games); game total 39.5 (nflverse schedule line), home, roof outdoors, rest 7 days; club QB: Geno Smith (attempt leaders by week {'1': 'G.Smith', '2': 'G.Smith', '3': 'G.Smith', '4': 'G.Smith'}); teammates with availability doubt: Mason Taylor, Jamaal Pritchett.
- **Benchmark FC:** 11.07 (floor 0.0, ceiling 31.47). Our projection: NOT BUILT.
- **Flags:** ROLE_CHANGE: snap share up 24 pp
- **Missing model dependencies:** 4-game pooled usage does not separate a role change from a one-game anomaly (W5-G8); accounting repair pending (D-05) affects all players.
- **Next research action:** read the last two games: is the snap change a role change, an injury exit or game script?.

### Mason Taylor (TE, $2500)
- **Eligibility:** ELIGIBLE (ACT). Practice: Full Participation in Practice (Thumb). Designation: NOT_YET_ISSUED (designations are issued Friday; absence is not health). Depth: ['TE2'].
- **2026:** 2 games, DK average 0.9, last game 0.0 (week 2).
- **What drives his production:** 2026 target share 6%; game total 39.5 (nflverse schedule line), home, roof outdoors, rest 7 days; club QB: Geno Smith (attempt leaders by week {'1': 'G.Smith', '2': 'G.Smith', '3': 'G.Smith', '4': 'G.Smith'}); teammates with availability doubt: Jamaal Pritchett.
- **Benchmark FC:** 8.19 (floor 0.69, ceiling 18.19). Our projection: NOT BUILT.
- **Flags:** MISSED_LAST_GAME: no participation in week 4 | FC_VS_RECENT_PRODUCTION: FC 8.19 vs 2026 DK avg 0.9
- **Missing model dependencies:** accounting repair pending (D-05) affects all players.
- **Next research action:** decompose FC vs recent production: volume, efficiency or availability assumption; verify return status and any snap limit; compare to pre-injury usage.

### Malik McClain (WR, $3000)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['WR4'].
- **2026:** 2 games, DK average 0.0, last game 0.0 (week 4).
- **What drives his production:** 2026 target share 0%; game total 39.5 (nflverse schedule line), home, roof outdoors, rest 7 days; club QB: Geno Smith (attempt leaders by week {'1': 'G.Smith', '2': 'G.Smith', '3': 'G.Smith', '4': 'G.Smith'}); teammates with availability doubt: Mason Taylor, Jamaal Pritchett.
- **Benchmark FC:** 8.17 (floor 0.0, ceiling 0.0). Our projection: NOT BUILT.
- **Flags:** FC_VS_RECENT_PRODUCTION: FC 8.17 vs 2026 DK avg 0.0
- **Missing model dependencies:** accounting repair pending (D-05) affects all players.
- **Next research action:** decompose FC vs recent production: volume, efficiency or availability assumption.

### Isaiah Williams (WR, $3700)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['WR3'].
- **2026:** 4 games, DK average 7.72, last game 15.3 (week 4).
- **What drives his production:** 2026 target share 12%, carry share 1%; red zone 2026: 1 targets, 0 carries; snap share trend +20 pp (last 2 vs first 2 games); game total 39.5 (nflverse schedule line), home, roof outdoors, rest 7 days; club QB: Geno Smith (attempt leaders by week {'1': 'G.Smith', '2': 'G.Smith', '3': 'G.Smith', '4': 'G.Smith'}); teammates with availability doubt: Mason Taylor, Jamaal Pritchett.
- **Benchmark FC:** 7.24 (floor 0.79, ceiling 15.84). Our projection: NOT BUILT.
- **Flags:** ROLE_CHANGE: snap share up 20 pp
- **Missing model dependencies:** 4-game pooled usage does not separate a role change from a one-game anomaly (W5-G8); accounting repair pending (D-05) affects all players.
- **Next research action:** read the last two games: is the snap change a role change, an injury exit or game script?.

### Jets (DST, $2700)
- **Eligibility:** ELIGIBLE_BY_CONSTRUCTION. Practice: not on report. Designation: n/a. Depth: None.
- **What drives his production:** opponent CLE QB Deshaun Watson; opponent QB flags []; game total 39.5.
- **Benchmark FC:** 4.97 (floor 0.0, ceiling 16.17). Our projection: NOT BUILT.
- **Missing model dependencies:** opponent QB identity not consumed by DST model (D-02); turnovers not event-linked (D-05).
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### Isaiah Davis (RB, $4200)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['RB3'].
- **2026:** 4 games, DK average 0.0, last game 0.0 (week 4).
- **What drives his production:** 2026 target share 0%; 2026 carry share 0%; snap share trend +3 pp (last 2 vs first 2 games); game total 39.5 (nflverse schedule line), home, roof outdoors, rest 7 days; club QB: Geno Smith (attempt leaders by week {'1': 'G.Smith', '2': 'G.Smith', '3': 'G.Smith', '4': 'G.Smith'}); teammates with availability doubt: Mason Taylor, Jamaal Pritchett.
- **Benchmark FC:** 3.05 (floor 0.0, ceiling 12.65). Our projection: NOT BUILT.
- **Flags:** FC_VS_RECENT_PRODUCTION: FC 3.05 vs 2026 DK avg 0.0
- **Missing model dependencies:** accounting repair pending (D-05) affects all players.
- **Next research action:** decompose FC vs recent production: volume, efficiency or availability assumption.

## PIT vs IND

### Aaron Rodgers (QB, $5300)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['QB1'].
- **2026:** 4 games, DK average 16.54, last game 23.96 (week 4).
- **What drives his production:** snap share trend +2 pp (last 2 vs first 2 games); game total 44.5 (nflverse schedule line), home, roof outdoors, rest 10 days; club QB: Aaron Rodgers (attempt leaders by week {'1': 'A.Rodgers', '2': 'A.Rodgers', '3': 'A.Rodgers', '4': 'A.Rodgers'}); teammates with availability doubt: Rico Dowdle, Mason Rudolph, Eli Heidenreich.
- **Reported [REPORTED]:** Aaron Rodgers is on no Week 5 report and is expected to face IND. W4 (TNF Oct 1, L 27-24 vs CLE): 22/40, 299 yds, 3 TD, 2 INT; team 2-2. I found no QB change. (https://www.nbcsports.com/fantasy/football/player-news/2026-10-01/aaron-rodgers-steelers-fall-to-2-2-in-loss-to-cle)
- **Benchmark FC:** 18.29 (floor 5.39, ceiling 35.49). Our projection: NOT BUILT.
- **Missing model dependencies:** lower-tail volatility under-stated for high-mean players (D-01).
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### DK Metcalf (WR, $5400)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['WR1'].
- **2026:** 4 games, DK average 11.57, last game 19.5 (week 4).
- **What drives his production:** 2026 target share 23%; red zone 2026: 1 targets, 0 carries; snap share trend -0 pp (last 2 vs first 2 games); game total 44.5 (nflverse schedule line), home, roof outdoors, rest 10 days; club QB: Aaron Rodgers (attempt leaders by week {'1': 'A.Rodgers', '2': 'A.Rodgers', '3': 'A.Rodgers', '4': 'A.Rodgers'}); teammates with availability doubt: Rico Dowdle, Mason Rudolph, Eli Heidenreich.
- **Benchmark FC:** 16.31 (floor 4.16, ceiling 32.51). Our projection: NOT BUILT.
- **Flags:** FC_VS_RECENT_PRODUCTION: FC 16.31 vs 2026 DK avg 11.57
- **Missing model dependencies:** lower-tail volatility under-stated for high-mean players (D-01).
- **Next research action:** decompose FC vs recent production: volume, efficiency or availability assumption.

### Jaylen Warren (RB, $6700)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['RB1'].
- **2026:** 4 games, DK average 15.05, last game 15.6 (week 4).
- **What drives his production:** 2026 target share 14%, carry share 65%; red zone 2026: 4 targets, 3 carries; snap share trend +40 pp (last 2 vs first 2 games); game total 44.5 (nflverse schedule line), home, roof outdoors, rest 10 days; club QB: Aaron Rodgers (attempt leaders by week {'1': 'A.Rodgers', '2': 'A.Rodgers', '3': 'A.Rodgers', '4': 'A.Rodgers'}); teammates with availability doubt: Rico Dowdle, Mason Rudolph, Eli Heidenreich.
- **Benchmark FC:** 13.28 (floor 4.13, ceiling 25.48). Our projection: NOT BUILT.
- **Flags:** ROLE_CHANGE: snap share up 40 pp
- **Missing model dependencies:** 4-game pooled usage does not separate a role change from a one-game anomaly (W5-G8); accounting repair pending (D-05) affects all players.
- **Next research action:** read the last two games: is the snap change a role change, an injury exit or game script?.

### Rico Dowdle (RB, $4700)
- **Eligibility:** ELIGIBLE (ACT). Practice: Limited Participation in Practice (Toe). Designation: NOT_YET_ISSUED (designations are issued Friday; absence is not health). Depth: ['RB2'].
- **2026:** 2 games, DK average 5.25, last game 6.4 (week 2).
- **What drives his production:** 2026 target share 10%, carry share 34%; red zone 2026: 0 targets, 1 carries; game total 44.5 (nflverse schedule line), home, roof outdoors, rest 10 days; club QB: Aaron Rodgers (attempt leaders by week {'1': 'A.Rodgers', '2': 'A.Rodgers', '3': 'A.Rodgers', '4': 'A.Rodgers'}); teammates with availability doubt: Mason Rudolph, Eli Heidenreich.
- **Reported [CONFIRMED]:** RB Rico Dowdle (toe; dislocated W2, hasn't played since) limited. CB Jamel Dean (ankle) DNP both days and 'tracking to miss' per McCarthy. CB Jalen Ramsey (wrist) DNP to limited. S DeShon Elliott (knee, IR-designated for return) limited. DT Cam Heyward rest DNP to full. (https://steelersdepot.com/2026/10/steelers-week-five-thursday-injury-report-two-players-dnp-three-others-limited/)
- **Benchmark FC:** 12.79 (floor 0.19, ceiling 29.59). Our projection: NOT BUILT.
- **Flags:** MISSED_LAST_GAME: no participation in week 4 | FC_VS_RECENT_PRODUCTION: FC 12.79 vs 2026 DK avg 5.25
- **Missing model dependencies:** practice participation does not change a projection until a designation; no partial-workload model (W5-G4); accounting repair pending (D-05) affects all players.
- **Next research action:** decompose FC vs recent production: volume, efficiency or availability assumption; verify return status and any snap limit; compare to pre-injury usage.

### Roman Wilson (WR, $3700)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['WR3'].
- **2026:** 4 games, DK average 11.2, last game 16.4 (week 4).
- **What drives his production:** 2026 target share 17%; red zone 2026: 2 targets, 0 carries; snap share trend -32 pp (last 2 vs first 2 games); game total 44.5 (nflverse schedule line), home, roof outdoors, rest 10 days; club QB: Aaron Rodgers (attempt leaders by week {'1': 'A.Rodgers', '2': 'A.Rodgers', '3': 'A.Rodgers', '4': 'A.Rodgers'}); teammates with availability doubt: Rico Dowdle, Mason Rudolph, Eli Heidenreich.
- **Benchmark FC:** 9.08 (floor 0.0, ceiling 21.48). Our projection: NOT BUILT.
- **Flags:** ROLE_CHANGE: snap share down 32 pp
- **Missing model dependencies:** 4-game pooled usage does not separate a role change from a one-game anomaly (W5-G8); accounting repair pending (D-05) affects all players.
- **Next research action:** read the last two games: is the snap change a role change, an injury exit or game script?.

### Pat Freiermuth (TE, $3900)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['TE2'].
- **2026:** 4 games, DK average 9.7, last game 10.7 (week 4).
- **What drives his production:** 2026 target share 13%, carry share 2%; red zone 2026: 3 targets, 0 carries; snap share trend -2 pp (last 2 vs first 2 games); game total 44.5 (nflverse schedule line), home, roof outdoors, rest 10 days; club QB: Aaron Rodgers (attempt leaders by week {'1': 'A.Rodgers', '2': 'A.Rodgers', '3': 'A.Rodgers', '4': 'A.Rodgers'}); teammates with availability doubt: Rico Dowdle, Mason Rudolph, Eli Heidenreich.
- **Benchmark FC:** 8.74 (floor 0.34, ceiling 19.94). Our projection: NOT BUILT.
- **Missing model dependencies:** accounting repair pending (D-05) affects all players.
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### Steelers (DST, $3300)
- **Eligibility:** ELIGIBLE_BY_CONSTRUCTION. Practice: not on report. Designation: n/a. Depth: None.
- **What drives his production:** opponent IND QB Daniel Jones; opponent QB flags []; game total 44.5.
- **Reported [REPORTED]:** K Chris Boswell has had 3 FG attempts in each Steelers win. (https://www.nbcsports.com/fantasy/football/news/fantasy-football-kicker-streamers-the-3-best-pickups-for-week-5)
- **Benchmark FC:** 7.41 (floor 0.0, ceiling 19.21). Our projection: NOT BUILT.
- **Missing model dependencies:** opponent QB identity not consumed by DST model (D-02); turnovers not event-linked (D-05).
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### Darnell Washington (TE, $2900)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['TE1'].
- **2026:** 4 games, DK average 6.72, last game 11.7 (week 4).
- **What drives his production:** 2026 target share 9%; red zone 2026: 2 targets, 0 carries; snap share trend +15 pp (last 2 vs first 2 games); game total 44.5 (nflverse schedule line), home, roof outdoors, rest 10 days; club QB: Aaron Rodgers (attempt leaders by week {'1': 'A.Rodgers', '2': 'A.Rodgers', '3': 'A.Rodgers', '4': 'A.Rodgers'}); teammates with availability doubt: Rico Dowdle, Mason Rudolph, Eli Heidenreich.
- **Reported [REPORTED]:** Oct 6: CB Terrell Smith signed off Washington's practice squad. Oct 8: S DeShon Elliott designated to return from IR. (https://www.profootballrumors.com/2026/10/minor-nfl-transactions-10-6-26)
- **Benchmark FC:** 7.33 (floor 2.68, ceiling 13.53). Our projection: NOT BUILT.
- **Flags:** ROLE_CHANGE: snap share up 15 pp
- **Missing model dependencies:** 4-game pooled usage does not separate a role change from a one-game anomaly (W5-G8); accounting repair pending (D-05) affects all players.
- **Next research action:** read the last two games: is the snap change a role change, an injury exit or game script?.

### Germie Bernard (WR, $3400)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['WR4'].
- **2026:** 4 games, DK average 3.25, last game 3.1 (week 4).
- **What drives his production:** 2026 target share 8%; red zone 2026: 2 targets, 0 carries; snap share trend -8 pp (last 2 vs first 2 games); game total 44.5 (nflverse schedule line), home, roof outdoors, rest 10 days; club QB: Aaron Rodgers (attempt leaders by week {'1': 'A.Rodgers', '2': 'A.Rodgers', '3': 'A.Rodgers', '4': 'A.Rodgers'}); teammates with availability doubt: Rico Dowdle, Mason Rudolph, Eli Heidenreich.
- **Benchmark FC:** 5.94 (floor 2.49, ceiling 10.54). Our projection: NOT BUILT.
- **Missing model dependencies:** accounting repair pending (D-05) affects all players.
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### Ben Skowronek (WR, $3000)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['WR5'].
- **2026:** 4 games, DK average 3.05, last game 1.7 (week 4).
- **What drives his production:** 2026 target share 3%; red zone 2026: 1 targets, 0 carries; snap share trend +4 pp (last 2 vs first 2 games); game total 44.5 (nflverse schedule line), home, roof outdoors, rest 10 days; club QB: Aaron Rodgers (attempt leaders by week {'1': 'A.Rodgers', '2': 'A.Rodgers', '3': 'A.Rodgers', '4': 'A.Rodgers'}); teammates with availability doubt: Rico Dowdle, Mason Rudolph, Eli Heidenreich.
- **Benchmark FC:** 1.38 (floor 0.0, ceiling 8.78). Our projection: NOT BUILT.
- **Missing model dependencies:** accounting repair pending (D-05) affects all players.
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

## TEN vs HOU

### Cam Ward (QB, $4900)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['QB1'].
- **2026:** 4 games, DK average 14.68, last game 16.58 (week 4).
- **What drives his production:** red zone 2026: 0 targets, 6 carries; snap share trend +0 pp (last 2 vs first 2 games); game total 37.5 (nflverse schedule line), home, roof outdoors, rest 7 days; club QB: Cam Ward (attempt leaders by week {'1': 'C.Ward', '2': 'C.Ward', '3': 'C.Ward', '4': 'C.Ward'}); teammates with availability doubt: David Martin-Robinson, Kylen Granson.
- **Reported [REPORTED]:** Cam Ward started W4 at BAL (20/31, 222 yds, 1 TD, 1 INT). I found no Week 5 injury listing or QB change for him. (https://fantasydata.com/nfl/boxscore/19504-tennessee-titans-vs-baltimore-ravens-week-4-2026)
- **Benchmark FC:** 13.87 (floor 6.37, ceiling 23.87). Our projection: NOT BUILT.
- **Missing model dependencies:** accounting repair pending (D-05) affects all players.
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### Carnell Tate (WR, $5300)
- **Eligibility:** ELIGIBLE (ACT). Practice: Limited Participation in Practice (Back). Designation: NOT_YET_ISSUED (designations are issued Friday; absence is not health). Depth: ['WR1'].
- **2026:** 4 games, DK average 12.7, last game 25.5 (week 4).
- **What drives his production:** 2026 target share 30%; red zone 2026: 1 targets, 0 carries; snap share trend +4 pp (last 2 vs first 2 games); game total 37.5 (nflverse schedule line), home, roof outdoors, rest 7 days; club QB: Cam Ward (attempt leaders by week {'1': 'C.Ward', '2': 'C.Ward', '3': 'C.Ward', '4': 'C.Ward'}); teammates with availability doubt: David Martin-Robinson, Kylen Granson.
- **Reported [CONFIRMED]:** RB Tony Pollard (foot) DNP to FP. Rookie WR Carnell Tate (back) added Thursday as limited. TE David Martin-Robinson (hamstring) FP to DNP. S Amani Hooker (concussion) DNP/DNP. DL Jeffery Simmons and John Franklin-Myers (back) DNP to LP. (https://www.tennesseetitans.com/news/week-5-injury-report-titans-vs-texans)
- **Benchmark FC:** 11.61 (floor 0.06, ceiling 27.01). Our projection: NOT BUILT.
- **Missing model dependencies:** practice participation does not change a projection until a designation; no partial-workload model (W5-G4); accounting repair pending (D-05) affects all players.
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### Wan'Dale Robinson (WR, $4500)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['WR2'].
- **2026:** 4 games, DK average 10.1, last game 11.0 (week 4).
- **What drives his production:** 2026 target share 19%, carry share 1%; red zone 2026: 4 targets, 0 carries; snap share trend -2 pp (last 2 vs first 2 games); game total 37.5 (nflverse schedule line), home, roof outdoors, rest 7 days; club QB: Cam Ward (attempt leaders by week {'1': 'C.Ward', '2': 'C.Ward', '3': 'C.Ward', '4': 'C.Ward'}); teammates with availability doubt: David Martin-Robinson, Kylen Granson.
- **Reported [CONFIRMED]:** RB Tony Pollard (foot) DNP to FP. Rookie WR Carnell Tate (back) added Thursday as limited. TE David Martin-Robinson (hamstring) FP to DNP. S Amani Hooker (concussion) DNP/DNP. DL Jeffery Simmons and John Franklin-Myers (back) DNP to LP. (https://www.tennesseetitans.com/news/week-5-injury-report-titans-vs-texans)
- **Benchmark FC:** 11.09 (floor 0.74, ceiling 24.89). Our projection: NOT BUILT.
- **Missing model dependencies:** accounting repair pending (D-05) affects all players.
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### Tony Pollard (RB, $5600)
- **Eligibility:** ELIGIBLE (ACT). Practice: Full Participation in Practice (Foot). Designation: NOT_YET_ISSUED (designations are issued Friday; absence is not health). Depth: ['RB1'].
- **2026:** 4 games, DK average 9.62, last game 13.0 (week 4).
- **What drives his production:** 2026 target share 10%, carry share 60%; red zone 2026: 0 targets, 17 carries; snap share trend -0 pp (last 2 vs first 2 games); game total 37.5 (nflverse schedule line), home, roof outdoors, rest 7 days; club QB: Cam Ward (attempt leaders by week {'1': 'C.Ward', '2': 'C.Ward', '3': 'C.Ward', '4': 'C.Ward'}); teammates with availability doubt: David Martin-Robinson, Kylen Granson.
- **Reported [CONFIRMED]:** RB Tony Pollard (foot) DNP to FP. Rookie WR Carnell Tate (back) added Thursday as limited. TE David Martin-Robinson (hamstring) FP to DNP. S Amani Hooker (concussion) DNP/DNP. DL Jeffery Simmons and John Franklin-Myers (back) DNP to LP. (https://www.tennesseetitans.com/news/week-5-injury-report-titans-vs-texans)
- **Benchmark FC:** 10.63 (floor 0.0, ceiling 26.43). Our projection: NOT BUILT.
- **Missing model dependencies:** accounting repair pending (D-05) affects all players.
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### Tyjae Spears (RB, $4600)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['RB2'].
- **2026:** 4 games, DK average 3.88, last game 1.6 (week 4).
- **What drives his production:** 2026 target share 7%, carry share 17%; red zone 2026: 0 targets, 2 carries; snap share trend -2 pp (last 2 vs first 2 games); game total 37.5 (nflverse schedule line), home, roof outdoors, rest 7 days; club QB: Cam Ward (attempt leaders by week {'1': 'C.Ward', '2': 'C.Ward', '3': 'C.Ward', '4': 'C.Ward'}); teammates with availability doubt: David Martin-Robinson, Kylen Granson.
- **Benchmark FC:** 6.74 (floor 0.0, ceiling 18.94). Our projection: NOT BUILT.
- **Missing model dependencies:** accounting repair pending (D-05) affects all players.
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### Elic Ayomanor (WR, $3000)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['WR3'].
- **2026:** 4 games, DK average 5.58, last game 3.2 (week 4).
- **What drives his production:** 2026 target share 10%; red zone 2026: 5 targets, 0 carries; snap share trend +18 pp (last 2 vs first 2 games); game total 37.5 (nflverse schedule line), home, roof outdoors, rest 7 days; club QB: Cam Ward (attempt leaders by week {'1': 'C.Ward', '2': 'C.Ward', '3': 'C.Ward', '4': 'C.Ward'}); teammates with availability doubt: David Martin-Robinson, Kylen Granson.
- **Benchmark FC:** 5.6 (floor 0.0, ceiling 13.6). Our projection: NOT BUILT.
- **Flags:** ROLE_CHANGE: snap share up 18 pp
- **Missing model dependencies:** 4-game pooled usage does not separate a role change from a one-game anomaly (W5-G8); accounting repair pending (D-05) affects all players.
- **Next research action:** read the last two games: is the snap change a role change, an injury exit or game script?.

### Gunnar Helm (TE, $2800)
- **Eligibility:** ELIGIBLE (ACT). Practice: Limited Participation in Practice (Knee). Designation: NOT_YET_ISSUED (designations are issued Friday; absence is not health). Depth: ['TE1'].
- **2026:** 4 games, DK average 4.25, last game 3.5 (week 4).
- **What drives his production:** 2026 target share 11%; red zone 2026: 3 targets, 0 carries; snap share trend -4 pp (last 2 vs first 2 games); game total 37.5 (nflverse schedule line), home, roof outdoors, rest 7 days; club QB: Cam Ward (attempt leaders by week {'1': 'C.Ward', '2': 'C.Ward', '3': 'C.Ward', '4': 'C.Ward'}); teammates with availability doubt: David Martin-Robinson, Kylen Granson.
- **Benchmark FC:** 4.37 (floor 0.0, ceiling 11.57). Our projection: NOT BUILT.
- **Missing model dependencies:** practice participation does not change a projection until a designation; no partial-workload model (W5-G4); accounting repair pending (D-05) affects all players.
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### Titans (DST, $2100)
- **Eligibility:** ELIGIBLE_BY_CONSTRUCTION. Practice: not on report. Designation: n/a. Depth: None.
- **What drives his production:** opponent HOU QB C.J. Stroud; opponent QB flags []; game total 37.5.
- **Benchmark FC:** 3.7 (floor 0.0, ceiling 14.1). Our projection: NOT BUILT.
- **Missing model dependencies:** opponent QB identity not consumed by DST model (D-02); turnovers not event-linked (D-05).
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### Daniel Bellinger (TE, $2500)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['TE2'].
- **2026:** 4 games, DK average 1.62, last game 1.2 (week 4).
- **What drives his production:** 2026 target share 5%; snap share trend +10 pp (last 2 vs first 2 games); game total 37.5 (nflverse schedule line), home, roof outdoors, rest 7 days; club QB: Cam Ward (attempt leaders by week {'1': 'C.Ward', '2': 'C.Ward', '3': 'C.Ward', '4': 'C.Ward'}); teammates with availability doubt: David Martin-Robinson, Kylen Granson.
- **Benchmark FC:** 2.83 (floor 0.0, ceiling 10.83). Our projection: NOT BUILT.
- **Missing model dependencies:** accounting repair pending (D-05) affects all players.
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### Calvin Ridley (WR, $3500)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['WR4'].
- **2026:** 4 games, DK average 1.95, last game 2.3 (week 4).
- **What drives his production:** 2026 target share 5%; snap share trend -23 pp (last 2 vs first 2 games); game total 37.5 (nflverse schedule line), home, roof outdoors, rest 7 days; club QB: Cam Ward (attempt leaders by week {'1': 'C.Ward', '2': 'C.Ward', '3': 'C.Ward', '4': 'C.Ward'}); teammates with availability doubt: David Martin-Robinson, Kylen Granson.
- **Benchmark FC:** 2.66 (floor 0.0, ceiling 21.66). Our projection: NOT BUILT.
- **Flags:** ROLE_CHANGE: snap share down 23 pp
- **Missing model dependencies:** 4-game pooled usage does not separate a role change from a one-game anomaly (W5-G8); accounting repair pending (D-05) affects all players.
- **Next research action:** read the last two games: is the snap change a role change, an injury exit or game script?.

## WAS vs NYG

### Jayden Daniels (QB, $6000)
- **Eligibility:** ELIGIBLE (ACT). Practice: Full Participation in Practice (Elbow). Designation: NOT_YET_ISSUED (designations are issued Friday; absence is not health). Depth: ['QB1'].
- **2026:** 2 games, DK average 16.2, last game 14.74 (week 2).
- **What drives his production:** red zone 2026: 0 targets, 4 carries; game total 42.5 (nflverse schedule line), home, roof outdoors, rest 7 days; club QB: Jayden Daniels (attempt leaders by week {'1': 'J.Daniels', '2': 'J.Daniels', '3': 'M.Mariota', '4': 'A.Kaliakmanis'}); teammates with availability doubt: Terry McLaurin, Stefon Diggs, Rachaad White, Luke McCaffrey.
- **Reported [CONFIRMED]:** Jayden Daniels (left elbow dislocated W2 at DAL) returns Week 5: full Wednesday and Thursday. OC David Blough: 'full go'; Dan Quinn expects him to start barring setback. He will wear a brace all season. QB by week: Daniels W1-W2; Marcus Mariota W3 (W 33-31 vs SEA) and W4 (London vs IND, L 30-13; hurt early, rookie Athan Kaliakmanis finished). (https://www.commanders.com/news/commanders-vs-giants-week-5-injury-report)
- **Benchmark FC:** 20.83 (floor 7.78, ceiling 38.23). Our projection: NOT BUILT.
- **Flags:** MISSED_LAST_GAME: no participation in week 4 | QB_DIFFERS_FROM_LAST_GAME: week 4 passer A.Kaliakmanis, listed Jayden Daniels | QB_CHURN: 3 different attempt leaders in 4 games
- **Missing model dependencies:** QB-conditioned team volume / shares NOT consumed by the engine (W5-G1); QB rushing from a generic cohort prior, starts pooled with relief (D-03); lower-tail volatility under-stated for high-mean players (D-01).
- **Next research action:** confirm the starter from a team source; run the QB shadow candidate for this club; verify return status and any snap limit; compare to pre-injury usage.

### Terry McLaurin (WR, $5300)
- **Eligibility:** ELIGIBLE (ACT). Practice: Did Not Participate In Practice (Hamstring). Designation: NOT_YET_ISSUED (designations are issued Friday; absence is not health). Depth: ['WR1'].
- **2026:** 3 games, DK average 10.03, last game 19.7 (week 3).
- **What drives his production:** 2026 target share 23%; red zone 2026: 2 targets, 0 carries; snap share trend -6 pp (last 2 vs first 2 games); game total 42.5 (nflverse schedule line), home, roof outdoors, rest 7 days; club QB: Jayden Daniels (attempt leaders by week {'1': 'J.Daniels', '2': 'J.Daniels', '3': 'M.Mariota', '4': 'A.Kaliakmanis'}); teammates with availability doubt: Jayden Daniels, Stefon Diggs, Rachaad White, Luke McCaffrey.
- **Reported [CONFIRMED]:** WR Terry McLaurin (hamstring): DNP Wednesday and Thursday; missed W4. (https://www.commanders.com/news/commanders-vs-giants-week-5-injury-report)
- **Benchmark FC:** 13.22 (floor 1.67, ceiling 28.62). Our projection: NOT BUILT.
- **Flags:** DID_NOT_PRACTICE | MISSED_LAST_GAME: no participation in week 4
- **Missing model dependencies:** QB-conditioned team volume / shares NOT consumed by the engine (W5-G1); practice participation does not change a projection until a designation; no partial-workload model (W5-G4); accounting repair pending (D-05) affects all players.
- **Next research action:** capture Friday designation; if OUT, check redistribution to same-position teammates; verify return status and any snap limit; compare to pre-injury usage.

### Stefon Diggs (WR, $5500)
- **Eligibility:** ELIGIBLE (ACT). Practice: Did Not Participate In Practice (Hamstring). Designation: NOT_YET_ISSUED (designations are issued Friday; absence is not health). Depth: ['WR2'].
- **2026:** 4 games, DK average 13.25, last game 8.5 (week 4).
- **What drives his production:** 2026 target share 24%; red zone 2026: 4 targets, 0 carries; snap share trend +6 pp (last 2 vs first 2 games); game total 42.5 (nflverse schedule line), home, roof outdoors, rest 7 days; club QB: Jayden Daniels (attempt leaders by week {'1': 'J.Daniels', '2': 'J.Daniels', '3': 'M.Mariota', '4': 'A.Kaliakmanis'}); teammates with availability doubt: Jayden Daniels, Terry McLaurin, Rachaad White, Luke McCaffrey.
- **Reported [CONFLICTING]:** WR Stefon Diggs (hamstring): official report DNP both days vs ESPN 'returned to practice Thursday'. Both list him questionable-leaning. (https://www.commanders.com/news/commanders-vs-giants-week-5-injury-report)
- **Benchmark FC:** 12.04 (floor 0.0, ceiling 31.04). Our projection: NOT BUILT.
- **Flags:** DID_NOT_PRACTICE
- **Missing model dependencies:** QB-conditioned team volume / shares NOT consumed by the engine (W5-G1); practice participation does not change a projection until a designation; no partial-workload model (W5-G4); accounting repair pending (D-05) affects all players.
- **Next research action:** capture Friday designation; if OUT, check redistribution to same-position teammates.

### Jacory Croskey-Merritt (RB, $4900)
- **Eligibility:** ELIGIBLE (ACT). Practice: Limited Participation in Practice (Groin). Designation: NOT_YET_ISSUED (designations are issued Friday; absence is not health). Depth: ['RB1'].
- **2026:** 4 games, DK average 7.67, last game 7.0 (week 4).
- **What drives his production:** 2026 target share 5%, carry share 47%; red zone 2026: 1 targets, 6 carries; snap share trend +8 pp (last 2 vs first 2 games); game total 42.5 (nflverse schedule line), home, roof outdoors, rest 7 days; club QB: Jayden Daniels (attempt leaders by week {'1': 'J.Daniels', '2': 'J.Daniels', '3': 'M.Mariota', '4': 'A.Kaliakmanis'}); teammates with availability doubt: Jayden Daniels, Terry McLaurin, Stefon Diggs, Rachaad White, Luke McCaffrey.
- **Benchmark FC:** 8.58 (floor 0.0, ceiling 23.58). Our projection: NOT BUILT.
- **Missing model dependencies:** QB-conditioned team volume / shares NOT consumed by the engine (W5-G1); practice participation does not change a projection until a designation; no partial-workload model (W5-G4); accounting repair pending (D-05) affects all players.
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### Rachaad White (RB, $5100)
- **Eligibility:** ELIGIBLE (ACT). Practice: Limited Participation in Practice (Shoulder). Designation: NOT_YET_ISSUED (designations are issued Friday; absence is not health). Depth: ['RB2'].
- **2026:** 3 games, DK average 10.03, last game 11.1 (week 3).
- **What drives his production:** 2026 target share 9%, carry share 23%; red zone 2026: 2 targets, 4 carries; snap share trend +1 pp (last 2 vs first 2 games); game total 42.5 (nflverse schedule line), home, roof outdoors, rest 7 days; club QB: Jayden Daniels (attempt leaders by week {'1': 'J.Daniels', '2': 'J.Daniels', '3': 'M.Mariota', '4': 'A.Kaliakmanis'}); teammates with availability doubt: Jayden Daniels, Terry McLaurin, Stefon Diggs, Luke McCaffrey.
- **Benchmark FC:** 8.56 (floor 0.0, ceiling 21.96). Our projection: NOT BUILT.
- **Flags:** MISSED_LAST_GAME: no participation in week 4
- **Missing model dependencies:** QB-conditioned team volume / shares NOT consumed by the engine (W5-G1); practice participation does not change a projection until a designation; no partial-workload model (W5-G4); accounting repair pending (D-05) affects all players.
- **Next research action:** verify return status and any snap limit; compare to pre-injury usage.

### Commanders (DST, $2900)
- **Eligibility:** ELIGIBLE_BY_CONSTRUCTION. Practice: not on report. Designation: n/a. Depth: None.
- **What drives his production:** opponent NYG QB Jameis Winston; opponent QB flags []; game total 42.5.
- **Benchmark FC:** 7.27 (floor 0.0, ceiling 17.47). Our projection: NOT BUILT.
- **Missing model dependencies:** opponent QB identity not consumed by DST model (D-02); turnovers not event-linked (D-05).
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### Antonio Williams (WR, $3800)
- **Eligibility:** ELIGIBLE (ACT). Practice: not on report. Designation: n/a. Depth: ['WR3'].
- **2026:** 4 games, DK average 7.6, last game 5.1 (week 4).
- **What drives his production:** 2026 target share 14%; red zone 2026: 2 targets, 0 carries; snap share trend +12 pp (last 2 vs first 2 games); game total 42.5 (nflverse schedule line), home, roof outdoors, rest 7 days; club QB: Jayden Daniels (attempt leaders by week {'1': 'J.Daniels', '2': 'J.Daniels', '3': 'M.Mariota', '4': 'A.Kaliakmanis'}); teammates with availability doubt: Jayden Daniels, Terry McLaurin, Stefon Diggs, Rachaad White, Luke McCaffrey.
- **Benchmark FC:** 7.13 (floor 0.0, ceiling 17.33). Our projection: NOT BUILT.
- **Missing model dependencies:** QB-conditioned team volume / shares NOT consumed by the engine (W5-G1); accounting repair pending (D-05) affects all players.
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### Chigoziem Okonkwo (TE, $3300)
- **Eligibility:** ELIGIBLE (ACT). Practice: Limited Participation in Practice (Hamstring). Designation: NOT_YET_ISSUED (designations are issued Friday; absence is not health). Depth: ['TE1'].
- **2026:** 2 games, DK average 3.05, last game 2.5 (week 4).
- **What drives his production:** 2026 target share 11%; game total 42.5 (nflverse schedule line), home, roof outdoors, rest 7 days; club QB: Jayden Daniels (attempt leaders by week {'1': 'J.Daniels', '2': 'J.Daniels', '3': 'M.Mariota', '4': 'A.Kaliakmanis'}); teammates with availability doubt: Jayden Daniels, Terry McLaurin, Stefon Diggs, Rachaad White, Luke McCaffrey.
- **Benchmark FC:** 6.75 (floor 0.0, ceiling 15.75). Our projection: NOT BUILT.
- **Flags:** FC_VS_RECENT_PRODUCTION: FC 6.75 vs 2026 DK avg 3.05
- **Missing model dependencies:** QB-conditioned team volume / shares NOT consumed by the engine (W5-G1); practice participation does not change a projection until a designation; no partial-workload model (W5-G4); accounting repair pending (D-05) affects all players.
- **Next research action:** decompose FC vs recent production: volume, efficiency or availability assumption.

### Treylon Burks (WR, $3200)
- **Eligibility:** ELIGIBLE (ACT). Practice: Full Participation in Practice (Shoulder). Designation: NOT_YET_ISSUED (designations are issued Friday; absence is not health). Depth: ['WR4'].
- **2026:** 3 games, DK average 7.0, last game 11.7 (week 4).
- **What drives his production:** 2026 target share 6%; red zone 2026: 1 targets, 0 carries; snap share trend +14 pp (last 2 vs first 2 games); game total 42.5 (nflverse schedule line), home, roof outdoors, rest 7 days; club QB: Jayden Daniels (attempt leaders by week {'1': 'J.Daniels', '2': 'J.Daniels', '3': 'M.Mariota', '4': 'A.Kaliakmanis'}); teammates with availability doubt: Jayden Daniels, Terry McLaurin, Stefon Diggs, Rachaad White, Luke McCaffrey.
- **Benchmark FC:** 5.24 (floor 0.0, ceiling 14.44). Our projection: NOT BUILT.
- **Missing model dependencies:** QB-conditioned team volume / shares NOT consumed by the engine (W5-G1); accounting repair pending (D-05) affects all players.
- **Next research action:** no flag fired; re-check after Friday designations and Sunday inactives.

### Ben Sinnott (TE, $2500)
- **Eligibility:** ELIGIBLE (ACT). Practice: Full Participation in Practice (Rib). Designation: NOT_YET_ISSUED (designations are issued Friday; absence is not health). Depth: ['TE2'].
- **2026:** 4 games, DK average 0.4, last game 0.0 (week 4).
- **What drives his production:** 2026 target share 2%; snap share trend -4 pp (last 2 vs first 2 games); game total 42.5 (nflverse schedule line), home, roof outdoors, rest 7 days; club QB: Jayden Daniels (attempt leaders by week {'1': 'J.Daniels', '2': 'J.Daniels', '3': 'M.Mariota', '4': 'A.Kaliakmanis'}); teammates with availability doubt: Jayden Daniels, Terry McLaurin, Stefon Diggs, Rachaad White, Luke McCaffrey.
- **Benchmark FC:** 4.09 (floor 0.34, ceiling 9.09). Our projection: NOT BUILT.
- **Flags:** FC_VS_RECENT_PRODUCTION: FC 4.09 vs 2026 DK avg 0.4
- **Missing model dependencies:** QB-conditioned team volume / shares NOT consumed by the engine (W5-G1); accounting repair pending (D-05) affects all players.
- **Next research action:** decompose FC vs recent production: volume, efficiency or availability assumption.

