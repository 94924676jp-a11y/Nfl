# Week-3 Early Only — game-by-game, player-by-player study

Built from held evidence at `observed_before = 2026-09-27T04:00:00Z`, kickoff `2026-09-27T17:00:00Z`. Spec `slate-study-1`.

**This document contains no projection and no recommendation.** Every number is an observed historical quantity or a DK fact. The production feature builder is unimplemented and the board pipeline refuses, so no lawful projection exists to show. Nothing here ranks players for selection.

## Three caveats that change how every row reads

**No 2026 information.** The builder runs arm A: history is restricted to seasons strictly before the forecast season. trail_snap, own_share and every h_* value is measured through 2025 and earlier, so a role change this September does not appear and a rookie has no history at all. Columns below say `prior` for exactly this reason.

**Injury blanks are UNKNOWN.** inj_available is 1 if an injury ROW exists, not if the player is available. An absent row is UNKNOWN_NO_INJURY_ROW and is never healthy. 518 of 692 injury rows carry no report_status.

**`role_rank` is snap share, not target share.** role_rank_basis is TRAILING_SNAP_SHARE, so the ranking is by time on the field and NOT by receiving volume. Concretely, in CIN: Drew Sample ranks TE1 on 0.573 trailing snap share with 0.038 target share, while Mike Gesicki is TE2 on 0.349 snaps with 0.092 target share -- the blocking tight end outranks the receiving one, which is correct for what the column measures and wrong for anyone reading it as a depth chart of who gets the ball. Read role_rank beside the target-share column, never instead of it.

**`fringe` is an artifact for anyone with no prior history.** Every one of the rows with a feature row but no trailing history is classed role_class=fringe, and that is a property of the classifier rather than a judgement about the player: with no prior-season snap share there is nothing to rank him on, so he cannot come out anywhere else. Because arm A excludes the forecast season, a rookie whose only NFL snaps are in 2026 is indistinguishable here from a practice-squad body. DK prices several of them between $4,300 and $5,300, which is not depth-tail pricing. This is the largest blind spot in the study and it compounds after inactives, because the replacement for an inactive starter is frequently one of these players.

**Coverage is partial by position.** 268 of 457 DK rows carry features; 189 do not — every QB, every DST, and the RB/WR/TE depth tail. Uncovered rows are listed as `NO_FEATURES` rather than dropped, because dropping them is how a depth player who becomes relevant after inactives disappears.


---

## CAR @ CLE

### CAR — 25 DK rows, $2500–$6100

14 with prior history · 1 rostered but no history · 10 no features

Depth chart consumed: `2026-09-24T06:01:34Z`, 69.97h before the clock, 18 listed.


| pos | player | $ | role | rank | trail snap (prior) | tgt share (prior, n) | part. EWMA (prior) | injury |
|---|---|---|---|---|---|---|---|---|
| QB | Bryce Young | 5600 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| QB | Kenny Pickett | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| QB | Haynes King | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| RB | Chuba Hubbard | 6100 | starter | 1 | 0.375 | 0.081 (78) | 0.995 | UNKNOWN_NO_INJURY_ROW |
| RB | Jonathon Brooks | 4600 | rotational | 3 | 0.047 | 0.024 (3) | 0.327 | UNKNOWN_NO_INJURY_ROW |
| RB | AJ Dillon | 4000 | rotational | 2 | 0.058 | 0.011 (65) | 0.492 | UNKNOWN_NO_INJURY_ROW |
| RB | Trevor Etienne | 4000 | fringe | 4 | 0.016 | 0.011 (11) | 0.308 | UNKNOWN_NO_INJURY_ROW |
| RB | Ahmani Marshall | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| RB | Anthony Tyus III | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| WR | Tetairoa McMillan | 6000 | starter | 1 | 0.854 | 0.237 (17) | 1.000 | UNKNOWN_NO_INJURY_ROW |
| WR | Jalen Coker | 5500 | rotational | 2 | 0.743 | 0.175 (22) | 1.000 | ROW_NO_STATUS: Limited Participation in Practice |
| WR | Xavier Legette | 3500 | fringe | 4 | 0.605 | 0.117 (31) | 1.000 | UNKNOWN_NO_INJURY_ROW |
| WR | Brycen Tremayne | 3000 | fringe | 5 | 0.160 | 0.027 (18) | 0.522 | UNKNOWN_NO_INJURY_ROW |
| WR | John Metchie III | 3000 | rotational | 3 | 0.626 | 0.184 (44) | 0.935 | UNKNOWN_NO_INJURY_ROW |
| WR | Chris Brazzell II | 3000 | fringe *(no history)* | 18 | — | — | — | UNKNOWN_NO_INJURY_ROW |
| WR | Ja'seem Reed | 3000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| WR | Casey Washington | 3000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| WR | David Moore | 3000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| WR | E.J. Williams Jr. | 3000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| TE | Darren Waller | 3400 | fringe | 4 | 0.281 | 0.145 (57) | 0.934 | ROW_NO_STATUS: Did Not Participate In Practice |
| TE | Tommy Tremble | 2500 | starter | 1 | 0.610 | 0.070 (78) | 0.890 | UNKNOWN_NO_INJURY_ROW |
| TE | Mitchell Evans | 2500 | rotational | 2 | 0.401 | 0.067 (17) | 0.830 | UNKNOWN_NO_INJURY_ROW |
| TE | Feleipe Franks | 2500 | fringe | 5 | 0.006 | 0.010 (14) | 0.263 | UNKNOWN_NO_INJURY_ROW |
| TE | Ja'Tavion Sanders | 2500 | rotational | 3 | 0.374 | 0.087 (28) | 0.862 | UNKNOWN_NO_INJURY_ROW |
| DST | Panthers | 3000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |

### CLE — 24 DK rows, $2500–$5500

11 with prior history · 4 rostered but no history · 9 no features

Depth chart consumed: `2026-09-24T06:01:34Z`, 69.97h before the clock, 19 listed.


| pos | player | $ | role | rank | trail snap (prior) | tgt share (prior, n) | part. EWMA (prior) | injury |
|---|---|---|---|---|---|---|---|---|
| QB | Deshaun Watson | 4700 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| QB | Shedeur Sanders | 4200 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| QB | Taylen Green | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| QB | Dillon Gabriel | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| RB | Quinshon Judkins | 5500 | starter | 1 | 0.401 | 0.103 (14) | 0.881 | UNKNOWN_NO_INJURY_ROW |
| RB | Raheim Sanders | 4500 | fringe | 4 | 0.129 | 0.043 (4) | 0.829 | UNKNOWN_NO_INJURY_ROW |
| RB | Jaleel McLaughlin | 4000 | rotational | 3 | 0.147 | 0.026 (41) | 0.578 | UNKNOWN_NO_INJURY_ROW |
| RB | Dylan Sampson | 4000 | rotational | 2 | 0.237 | 0.106 (15) | 0.880 | UNKNOWN_NO_INJURY_ROW |
| RB | Eric Gray | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| RB | Michael Burton | 4000 | fringe | 5 | 0.076 | 0.017 (74) | 0.358 | UNKNOWN_NO_INJURY_ROW |
| WR | Denzel Boston | 4500 | fringe *(no history)* | 5 | — | — | — | UNKNOWN_NO_INJURY_ROW |
| WR | KC Concepcion Jr. | 4300 | fringe *(no history)* | 9 | — | — | — | UNKNOWN_NO_INJURY_ROW |
| WR | Jerry Jeudy | 3800 | starter | 1 | 0.837 | 0.202 (91) | 1.000 | UNKNOWN_NO_INJURY_ROW |
| WR | Isaiah Bond | 3000 | rotational | 2 | 0.426 | 0.070 (16) | 0.840 | UNKNOWN_NO_INJURY_ROW |
| WR | Tylan Wallace | 3000 | fringe | 4 | 0.114 | 0.025 (49) | 0.473 | UNKNOWN_NO_INJURY_ROW |
| WR | Malachi Corley | 3000 | rotational | 3 | 0.310 | 0.057 (19) | 0.786 | UNKNOWN_NO_INJURY_ROW |
| WR | Bub Means | 3000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| WR | Jimmy Horn Jr. | 3000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| TE | Harold Fannin Jr. | 4000 | starter | 1 | 0.688 | 0.252 (16) | 1.000 | UNKNOWN_NO_INJURY_ROW |
| TE | Blake Whiteheart | 2500 | rotational | 2 | 0.292 | 0.015 (26) | 0.560 | UNKNOWN_NO_INJURY_ROW |
| TE | Carsen Ryan | 2500 | fringe *(no history)* | 13 | — | — | — | UNKNOWN_NO_INJURY_ROW |
| TE | Joe Royer | 2500 | fringe *(no history)* | 17 | — | — | — | UNKNOWN_NO_INJURY_ROW |
| TE | Messiah Swinson | 2500 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| DST | Browns | 2500 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |


---

## CIN @ PIT

### CIN — 24 DK rows, $2500–$8100

10 with prior history · 3 rostered but no history · 11 no features

Depth chart consumed: `2026-09-24T06:01:34Z`, 69.97h before the clock, 15 listed.


| pos | player | $ | role | rank | trail snap (prior) | tgt share (prior, n) | part. EWMA (prior) | injury |
|---|---|---|---|---|---|---|---|---|
| QB | Joe Burrow | 6600 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| QB | Joe Flacco | 4400 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| QB | Josh Johnson | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| QB | Sean Clifford | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| RB | Chase Brown | 6600 | starter | 1 | 0.672 | 0.146 (44) | 1.000 | UNKNOWN_NO_INJURY_ROW |
| RB | Samaje Perine | 4100 | rotational | 2 | 0.301 | 0.046 (91) | 0.892 | UNKNOWN_NO_INJURY_ROW |
| RB | Tahj Brooks | 4000 | rotational | 3 | 0.062 | 0.009 (7) | 0.386 | UNKNOWN_NO_INJURY_ROW |
| RB | Kentrel Bullock | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| RB | Kendall Milton | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| WR | Ja'Marr Chase | 8100 | starter | 1 | 0.821 | 0.290 (78) | 1.000 | UNKNOWN_NO_INJURY_ROW |
| WR | Tee Higgins | 6100 | rotational | 3 | 0.560 | 0.180 (85) | 1.000 | UNKNOWN_NO_INJURY_ROW |
| WR | Andrei Iosivas | 3000 | rotational | 2 | 0.724 | 0.095 (49) | 0.987 | ROW_NO_STATUS: Did Not Participate In Practice |
| WR | Colbie Young | 3000 | fringe *(no history)* | 11 | — | — | — | UNKNOWN_NO_INJURY_ROW |
| WR | Dohnte Meyers | 3000 | fringe *(no history)* | 12 | — | — | — | UNKNOWN_NO_INJURY_ROW |
| WR | Ke'Shawn Williams | 3000 | fringe | 4 | 0.040 | 0.004 (7) | 0.204 | UNKNOWN_NO_INJURY_ROW |
| WR | Jordan Moore | 3000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| WR | Noah Thomas | 3000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| TE | Mike Gesicki | 3300 | rotational | 2 | 0.349 | 0.092 (96) | 0.958 | UNKNOWN_NO_INJURY_ROW |
| TE | Drew Sample | 2600 | starter | 1 | 0.573 | 0.038 (86) | 0.786 | UNKNOWN_NO_INJURY_ROW |
| TE | Erick All Jr. | 2500 | rotational | 3 | 0.194 | 0.086 (9) | 0.963 | UNKNOWN_NO_INJURY_ROW |
| TE | Jack Endries | 2500 | fringe *(no history)* | 13 | — | — | — | UNKNOWN_NO_INJURY_ROW |
| TE | William Wagner | 2500 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| TE | Tanner Hudson | 2500 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| DST | Bengals | 2900 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |

### PIT — 25 DK rows, $2500–$5700

9 with prior history · 5 rostered but no history · 11 no features

Depth chart consumed: `2026-09-24T06:01:34Z`, 69.97h before the clock, 18 listed.


| pos | player | $ | role | rank | trail snap (prior) | tgt share (prior, n) | part. EWMA (prior) | injury |
|---|---|---|---|---|---|---|---|---|
| QB | Aaron Rodgers | 5000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| QB | Mason Rudolph | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| QB | Will Howard | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| QB | Drew Allar | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| RB | Jaylen Warren | 5700 | rotational | 2 | 0.434 | 0.078 (64) | 0.785 | ROW_NO_STATUS: Limited Participation in Practice |
| RB | Rico Dowdle | 4700 | starter | 1 | 0.627 | 0.136 (53) | 0.972 | ROW_NO_STATUS: Did Not Participate In Practice |
| RB | Eli Heidenreich | 4000 | fringe *(no history)* | 13 | — | — | — | UNKNOWN_NO_INJURY_ROW |
| RB | Lew Nichols | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| RB | Travis Homer | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| RB | Riley Nowakowski | 4000 | fringe *(no history)* | 5 | — | — | — | UNKNOWN_NO_INJURY_ROW |
| WR | DK Metcalf | 5400 | rotational | 2 | 0.634 | 0.231 (96) | 1.000 | UNKNOWN_NO_INJURY_ROW |
| WR | Michael Pittman Jr. | 4700 | starter | 1 | 0.868 | 0.173 (95) | 1.000 | ROW_NO_STATUS: Limited Participation in Practice |
| WR | Germie Bernard | 3900 | fringe *(no history)* | 14 | — | — | — | UNKNOWN_NO_INJURY_ROW |
| WR | Roman Wilson | 3400 | rotational | 3 | 0.179 | 0.075 (14) | 0.713 | UNKNOWN_NO_INJURY_ROW |
| WR | Ben Skowronek | 3000 | fringe | 4 | 0.120 | 0.018 (61) | 0.488 | UNKNOWN_NO_INJURY_ROW |
| WR | Kaden Wetjen | 3000 | fringe *(no history)* | 17 | — | — | — | UNKNOWN_NO_INJURY_ROW |
| WR | Cole Burgess | 3000 | fringe *(no history)* | 18 | — | — | — | UNKNOWN_NO_INJURY_ROW |
| WR | Brandon Johnson | 3000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| WR | Brandon Smith | 3000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| WR | Isaiah Hodgins | 3000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| TE | Pat Freiermuth | 3800 | starter | 1 | 0.521 | 0.096 (78) | 0.925 | UNKNOWN_NO_INJURY_ROW |
| TE | Darnell Washington | 2800 | rotational | 2 | 0.503 | 0.099 (50) | 0.946 | UNKNOWN_NO_INJURY_ROW |
| TE | Robert Tonyan | 2500 | rotational | 3 | 0.060 | 0.003 (76) | 0.094 | UNKNOWN_NO_INJURY_ROW |
| TE | Lake McRee | 2500 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| DST | Steelers | 2700 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |


---

## HOU @ IND

### HOU — 27 DK rows, $2500–$7000

14 with prior history · 1 rostered but no history · 12 no features

Depth chart consumed: `2026-09-24T06:01:34Z`, 69.97h before the clock, 18 listed.


| pos | player | $ | role | rank | trail snap (prior) | tgt share (prior, n) | part. EWMA (prior) | injury |
|---|---|---|---|---|---|---|---|---|
| QB | C.J. Stroud | 5500 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| QB | Davis Mills | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| QB | Graham Mertz | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| RB | David Montgomery | 6000 | rotational | 2 | 0.330 | 0.042 (89) | 0.870 | UNKNOWN_NO_INJURY_ROW |
| RB | Woody Marks | 5000 | starter | 1 | 0.515 | 0.062 (16) | 0.993 | UNKNOWN_NO_INJURY_ROW |
| RB | British Brooks | 4000 | rotational | 3 | 0.073 | 0.000 (7) | 0.000 | UNKNOWN_NO_INJURY_ROW |
| RB | Noah Whittington | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| RB | Jawhar Jordan | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| WR | Nico Collins | 7000 | starter | 1 | 0.670 | 0.235 (66) | 1.000 | ROW_NO_STATUS: Did Not Participate In Practice |
| WR | Kayshon Boutte | 4500 | fringe | 4 | 0.432 | 0.110 (34) | 1.000 | UNKNOWN_NO_INJURY_ROW |
| WR | Xavier Hutchinson | 4000 | rotational | 3 | 0.488 | 0.116 (47) | 0.914 | UNKNOWN_NO_INJURY_ROW |
| WR | Jaylin Noel | 3600 | fringe | 6 | 0.232 | 0.049 (17) | 0.729 | UNKNOWN_NO_INJURY_ROW |
| WR | Jared Wayne | 3100 | fringe | 7 | 0.055 | 0.013 (4) | 0.342 | UNKNOWN_NO_INJURY_ROW |
| WR | Tank Dell | 3000 | fringe | 5 | 0.331 | 0.185 (25) | 0.992 | UNKNOWN_NO_INJURY_ROW |
| WR | Jayden Higgins | 3000 | rotational | 2 | 0.616 | 0.162 (17) | 1.000 | UNKNOWN_NO_INJURY_ROW |
| WR | Josh Kelly | 3000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| WR | Mitch Tinsley | 3000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| WR | Daniel Sobkowicz | 3000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| WR | Lewis Bond | 3000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| WR | Bryce Oliver | 3000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| TE | Dalton Schultz | 4200 | starter | 1 | 0.725 | 0.194 (97) | 1.000 | ROW_NO_STATUS: Did Not Participate In Practice |
| TE | Foster Moreau | 2500 | rotational | 3 | 0.305 | 0.038 (91) | 0.730 | UNKNOWN_NO_INJURY_ROW |
| TE | Marlin Klein | 2500 | fringe *(no history)* | 12 | — | — | — | UNKNOWN_NO_INJURY_ROW |
| TE | Cade Stover | 2500 | rotational | 2 | 0.424 | 0.051 (24) | 0.710 | UNKNOWN_NO_INJURY_ROW |
| TE | Brevin Jordan | 2500 | fringe | 4 | 0.242 | 0.068 (35) | 0.806 | UNKNOWN_NO_INJURY_ROW |
| TE | Zaire Mitchell-Paden | 2500 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| DST | Texans | 3200 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |

### IND — 27 DK rows, $2500–$7600

12 with prior history · 3 rostered but no history · 12 no features

Depth chart consumed: `2026-09-24T06:01:34Z`, 69.97h before the clock, 19 listed.


| pos | player | $ | role | rank | trail snap (prior) | tgt share (prior, n) | part. EWMA (prior) | injury |
|---|---|---|---|---|---|---|---|---|
| QB | Daniel Jones | 5000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| QB | Anthony Richardson Sr. | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| QB | Riley Leonard | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| RB | Jonathan Taylor | 7600 | starter | 1 | 0.834 | 0.115 (84) | 0.914 | ROW_NO_STATUS: Limited Participation in Practice |
| RB | Seth McGowan | 4100 | fringe *(no history)* | 8 | — | — | — | UNKNOWN_NO_INJURY_ROW |
| RB | DJ Giddens | 4000 | rotational | 2 | 0.083 | 0.011 (6) | 0.327 | UNKNOWN_NO_INJURY_ROW |
| RB | Anderson Castle | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| RB | Davon Booth | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| WR | Josh Downs | 5700 | rotational | 3 | 0.609 | 0.173 (47) | 1.000 | UNKNOWN_NO_INJURY_ROW |
| WR | Alec Pierce | 5600 | starter | 1 | 0.907 | 0.161 (64) | 1.000 | ROW_NO_STATUS: Did Not Participate In Practice |
| WR | Keenan Allen | 4600 | fringe | 4 | 0.554 | 0.208 (85) | 1.000 | ROW_NO_STATUS: Limited Participation in Practice |
| WR | Darius Slayton | 3500 | rotational | 2 | 0.677 | 0.168 (92) | 1.000 | UNKNOWN_NO_INJURY_ROW |
| WR | Deion Burks | 3300 | fringe *(no history)* | 17 | — | — | — | UNKNOWN_NO_INJURY_ROW |
| WR | Ashton Dulin | 3200 | fringe | 6 | 0.107 | 0.038 (66) | 0.492 | ROW_NO_STATUS: Did Not Participate In Practice |
| WR | Laquon Treadwell | 3100 | fringe | 7 | 0.060 | 0.014 (30) | 0.163 | ROW_NO_STATUS: Full Participation in Practice |
| WR | D.J. Montgomery | 3000 | fringe | 5 | 0.198 | 0.033 (9) | 0.373 | UNKNOWN_NO_INJURY_ROW |
| WR | Nick Westbrook-Ikhine | 3000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| WR | Anthony Gould | 3000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| WR | Eli Pancol | 3000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| TE | Tyler Warren | 5300 | starter | 1 | 0.865 | 0.229 (17) | 1.000 | UNKNOWN_NO_INJURY_ROW |
| TE | Mo Alie-Cox | 2500 | rotational | 2 | 0.364 | 0.051 (100) | 0.770 | UNKNOWN_NO_INJURY_ROW |
| TE | Drew Ogletree | 2500 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| TE | Will Mallory | 2500 | fringe | 4 | 0.034 | 0.025 (24) | 0.631 | UNKNOWN_NO_INJURY_ROW |
| TE | Carson Towt | 2500 | fringe *(no history)* | 16 | — | — | — | UNKNOWN_NO_INJURY_ROW |
| TE | Pharaoh Brown | 2500 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| TE | Kenny Fletcher Jr. | 2500 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| DST | Colts | 2500 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |


---

## KC @ MIA

### KC — 27 DK rows, $2500–$7400

11 with prior history · 6 rostered but no history · 10 no features

Depth chart consumed: `2026-09-24T06:01:34Z`, 69.97h before the clock, 20 listed.


| pos | player | $ | role | rank | trail snap (prior) | tgt share (prior, n) | part. EWMA (prior) | injury |
|---|---|---|---|---|---|---|---|---|
| QB | Patrick Mahomes | 6200 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| QB | Justin Fields | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| QB | Garrett Nussmeier | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| RB | Kenneth Walker III | 7400 | starter | 1 | 0.494 | 0.108 (58) | 0.980 | UNKNOWN_NO_INJURY_ROW |
| RB | Emmett Johnson | 4400 | fringe *(no history)* | 9 | — | — | — | UNKNOWN_NO_INJURY_ROW |
| RB | Brashard Smith | 4000 | rotational | 2 | 0.175 | 0.068 (17) | 0.713 | UNKNOWN_NO_INJURY_ROW |
| RB | Ben VanSumeren | 4000 | fringe *(no history)* | 4 | — | — | — | UNKNOWN_NO_INJURY_ROW |
| RB | Nate Carter | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| RB | Jaydn Ott | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| WR | Rashee Rice | 6400 | rotational | 2 | 0.487 | 0.292 (28) | 0.967 | ROW_NO_STATUS: Full Participation in Practice |
| WR | Xavier Worthy | 4400 | starter | 1 | 0.685 | 0.162 (31) | 0.992 | UNKNOWN_NO_INJURY_ROW |
| WR | Cyrus Allen | 3600 | fringe *(no history)* | 15 | — | — | — | UNKNOWN_NO_INJURY_ROW |
| WR | Tyquan Thornton | 3300 | rotational | 3 | 0.193 | 0.046 (42) | 0.776 | UNKNOWN_NO_INJURY_ROW |
| WR | Jalen Royals | 3000 | fringe | 4 | 0.130 | 0.025 (4) | 0.342 | UNKNOWN_NO_INJURY_ROW |
| WR | Nikko Remigio | 3000 | fringe | 6 | 0.014 | 0.048 (8) | 0.158 | UNKNOWN_NO_INJURY_ROW |
| WR | Jeff Caldwell | 3000 | fringe *(no history)* | 19 | — | — | — | UNKNOWN_NO_INJURY_ROW |
| WR | Jimmy Holiday | 3000 | fringe | 5 | 0.020 | 0.000 (1) | 0.000 | UNKNOWN_NO_INJURY_ROW |
| WR | Omari Evans | 3000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| WR | Andrew Armstrong | 3000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| TE | Travis Kelce | 4500 | starter | 1 | 0.879 | 0.224 (96) | 1.000 | UNKNOWN_NO_INJURY_ROW |
| TE | Noah Gray | 3000 | rotational | 2 | 0.402 | 0.065 (82) | 0.750 | UNKNOWN_NO_INJURY_ROW |
| TE | Jake Briningstool | 2500 | fringe *(no history)* | 12 | — | — | — | UNKNOWN_NO_INJURY_ROW |
| TE | Jared Wiley | 2500 | rotational | 3 | 0.061 | 0.004 (10) | 0.151 | UNKNOWN_NO_INJURY_ROW |
| TE | John Michael Gyllenborg | 2500 | fringe *(no history)* | 17 | — | — | — | UNKNOWN_NO_INJURY_ROW |
| TE | James Winchester | 2500 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| TE | Thomas Odukoya | 2500 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| DST | Chiefs | 3700 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |

### MIA — 26 DK rows, $2000–$6500

8 with prior history · 7 rostered but no history · 11 no features

Depth chart consumed: `2026-09-24T06:01:34Z`, 69.97h before the clock, 18 listed.


| pos | player | $ | role | rank | trail snap (prior) | tgt share (prior, n) | part. EWMA (prior) | injury |
|---|---|---|---|---|---|---|---|---|
| QB | Malik Willis | 4900 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| QB | Kyle McCord | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| QB | Brady Cook | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| RB | De'Von Achane | 6500 | starter | 1 | 0.627 | 0.173 (44) | 0.995 | UNKNOWN_NO_INJURY_ROW |
| RB | Jaylen Wright | 4000 | rotational | 2 | 0.229 | 0.042 (25) | 0.579 | ROW_NO_STATUS: Limited Participation in Practice |
| RB | Ollie Gordon II | 4000 | rotational | 3 | 0.206 | 0.005 (17) | 0.330 | UNKNOWN_NO_INJURY_ROW |
| RB | DJ Herman | 4000 | fringe *(no history)* | 5 | — | — | — | UNKNOWN_NO_INJURY_ROW |
| RB | Jarquez Hunter | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| RB | Carlos Washington Jr. | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| WR | Malik Washington | 4200 | starter | 1 | 0.562 | 0.139 (31) | 0.999 | UNKNOWN_NO_INJURY_ROW |
| WR | Caleb Douglas | 3900 | fringe *(no history)* | 8 | — | — | — | ROW_NO_STATUS: Did Not Participate In Practice |
| WR | Chris Bell | 3400 | fringe *(no history)* | 12 | — | — | — | ROW_NO_STATUS: Limited Participation in Practice |
| WR | Ryan Miller | 3200 | rotational | 3 | 0.039 | 0.003 (23) | 0.167 | ROW_NO_STATUS: Limited Participation in Practice |
| WR | Kevin Coleman Jr. | 3000 | fringe *(no history)* | 15 | — | — | — | UNKNOWN_NO_INJURY_ROW |
| WR | Jalen Tolbert | 3000 | rotational | 2 | 0.179 | 0.056 (53) | 0.788 | UNKNOWN_NO_INJURY_ROW |
| WR | Will Sheppard | 3000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| WR | Jalen Reagor | 3000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| TE | Greg Dulcich | 3000 | starter | 1 | 0.448 | 0.158 (30) | 0.908 | UNKNOWN_NO_INJURY_ROW |
| TE | Will Kacmarek | 2500 | fringe *(no history)* | 9 | — | — | — | UNKNOWN_NO_INJURY_ROW |
| TE | Seydou Traore | 2500 | fringe *(no history)* | 13 | — | — | — | ROW_NO_STATUS: Full Participation in Practice |
| TE | Justin Joly | 2500 | fringe *(no history)* | 14 | — | — | — | UNKNOWN_NO_INJURY_ROW |
| TE | Cole Turner | 2500 | rotational | 2 | 0.044 | 0.014 (21) | 0.521 | UNKNOWN_NO_INJURY_ROW |
| TE | Cal Adomitis | 2500 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| TE | Tre Watson | 2500 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| TE | Luke Basso | 2500 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| DST | Dolphins | 2000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |


---

## LAC @ BUF

### LAC — 26 DK rows, $2200–$6800

15 with prior history · 1 rostered but no history · 10 no features

Depth chart consumed: `2026-09-24T06:01:34Z`, 69.97h before the clock, 18 listed.


| pos | player | $ | role | rank | trail snap (prior) | tgt share (prior, n) | part. EWMA (prior) | injury |
|---|---|---|---|---|---|---|---|---|
| QB | Justin Herbert | 5800 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| QB | Trey Lance | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| QB | DJ Uiagalelei | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| RB | Omarion Hampton | 6800 | fringe | 4 | 0.254 | 0.126 (9) | 1.000 | UNKNOWN_NO_INJURY_ROW |
| RB | Keaton Mitchell | 4300 | fringe | 5 | 0.224 | 0.057 (24) | 0.489 | UNKNOWN_NO_INJURY_ROW |
| RB | Kimani Vidal | 4000 | starter | 1 | 0.509 | 0.049 (23) | 0.798 | UNKNOWN_NO_INJURY_ROW |
| RB | Scott Matlock | 4000 | rotational | 3 | 0.292 | 0.010 (33) | 0.154 | UNKNOWN_NO_INJURY_ROW |
| RB | Alec Ingold | 4000 | rotational | 2 | 0.394 | 0.020 (91) | 0.513 | UNKNOWN_NO_INJURY_ROW |
| RB | Gregory Desrosiers | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| RB | Amar Johnson | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| WR | Ladd McConkey | 5900 | starter | 1 | 0.666 | 0.183 (32) | 1.000 | ROW_NO_STATUS: Full Participation in Practice |
| WR | Quentin Johnston | 4900 | rotational | 3 | 0.560 | 0.169 (46) | 0.959 | UNKNOWN_NO_INJURY_ROW |
| WR | Tre' Harris | 3900 | rotational | 2 | 0.588 | 0.119 (17) | 0.987 | UNKNOWN_NO_INJURY_ROW |
| WR | Brenen Thompson | 3000 | fringe *(no history)* | 15 | — | — | — | ROW_NO_STATUS: Did Not Participate In Practice |
| WR | Derius Davis | 3000 | fringe | 6 | 0.106 | 0.012 (38) | 0.604 | UNKNOWN_NO_INJURY_ROW |
| WR | Gary Jennings | 3000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| WR | KeAndre Lambert-Smith | 3000 | fringe | 5 | 0.121 | 0.041 (10) | 0.861 | UNKNOWN_NO_INJURY_ROW |
| WR | Theo Wease Jr. | 3000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| WR | Marquez Valdes-Scantling | 3000 | fringe | 4 | 0.364 | 0.090 (84) | 0.971 | UNKNOWN_NO_INJURY_ROW |
| TE | Oronde Gadsden II | 3500 | starter | 1 | 0.627 | 0.143 (15) | 1.000 | UNKNOWN_NO_INJURY_ROW |
| TE | David Njoku | 2700 | rotational | 3 | 0.218 | 0.101 (82) | 0.870 | UNKNOWN_NO_INJURY_ROW |
| TE | Hayden Rucci | 2500 | fringe | 4 | 0.085 | 0.000 (4) | 0.000 | UNKNOWN_NO_INJURY_ROW |
| TE | Charlie Kolar | 2500 | rotational | 2 | 0.348 | 0.025 (43) | 0.607 | ROW_NO_STATUS: Did Not Participate In Practice |
| TE | Evan Svoboda | 2500 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| TE | Patrick Herbert | 2500 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| DST | Chargers | 2200 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |

### BUF — 23 DK rows, $2500–$8000

11 with prior history · 1 rostered but no history · 11 no features

Depth chart consumed: `2026-09-24T06:01:34Z`, 69.97h before the clock, 15 listed.


| pos | player | $ | role | rank | trail snap (prior) | tgt share (prior, n) | part. EWMA (prior) | injury |
|---|---|---|---|---|---|---|---|---|
| QB | Josh Allen | 8000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| QB | Kyle Allen | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| QB | Shane Buechele | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| RB | James Cook III | 6900 | starter | 1 | 0.542 | 0.093 (66) | 0.749 | UNKNOWN_NO_INJURY_ROW |
| RB | Ray Davis | 4400 | rotational | 3 | 0.169 | 0.038 (33) | 0.726 | UNKNOWN_NO_INJURY_ROW |
| RB | Ty Johnson | 4000 | rotational | 2 | 0.310 | 0.100 (79) | 0.825 | ROW_NO_STATUS: Full Participation in Practice |
| RB | Frank Gore Jr. | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| RB | Brock Lampe | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| WR | DJ Moore | 5800 | starter | 1 | 0.865 | 0.155 (100) | 1.000 | ROW_NO_STATUS: Limited Participation in Practice |
| WR | Khalil Shakir | 4800 | rotational | 2 | 0.519 | 0.201 (62) | 1.000 | UNKNOWN_NO_INJURY_ROW |
| WR | Keon Coleman | 4300 | fringe | 5 | 0.263 | 0.134 (26) | 0.836 | ROW_NO_STATUS: Did Not Participate In Practice |
| WR | Joshua Palmer | 3500 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| WR | Skyler Bell | 3000 | fringe *(no history)* | 14 | — | — | — | UNKNOWN_NO_INJURY_ROW |
| WR | Tyrell Shavers | 3000 | rotational | 3 | 0.469 | 0.054 (19) | 0.667 | UNKNOWN_NO_INJURY_ROW |
| WR | Greg Dortch | 3000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| WR | Trent Sherfield Sr. | 3000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| WR | Ja'Mori Maclin | 3000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| WR | Stephen Gosnell | 3000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| TE | Dalton Kincaid | 5500 | rotational | 3 | 0.151 | 0.144 (41) | 1.000 | UNKNOWN_NO_INJURY_ROW |
| TE | Dawson Knox | 2800 | starter | 1 | 0.613 | 0.143 (87) | 0.991 | UNKNOWN_NO_INJURY_ROW |
| TE | Jackson Hawes | 2500 | rotational | 2 | 0.444 | 0.041 (17) | 0.761 | UNKNOWN_NO_INJURY_ROW |
| TE | Keleki Latu | 2500 | fringe | 4 | 0.146 | 0.028 (5) | 0.421 | UNKNOWN_NO_INJURY_ROW |
| DST | Bills | 2800 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |


---

## NE @ JAX

### NE — 26 DK rows, $2500–$6100

13 with prior history · 4 rostered but no history · 9 no features

Depth chart consumed: `2026-09-24T06:01:34Z`, 69.97h before the clock, 20 listed.


| pos | player | $ | role | rank | trail snap (prior) | tgt share (prior, n) | part. EWMA (prior) | injury |
|---|---|---|---|---|---|---|---|---|
| QB | Drake Maye | 6100 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| QB | Tommy DeVito | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| QB | Behren Morton | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| RB | Rhamondre Stevenson | 5400 | rotational | 2 | 0.419 | 0.105 (70) | 0.999 | UNKNOWN_NO_INJURY_ROW |
| RB | TreVeyon Henderson | 5200 | starter | 1 | 0.557 | 0.075 (17) | 0.575 | UNKNOWN_NO_INJURY_ROW |
| RB | Corey Kiner | 4000 | fringe | 4 | 0.133 | 0.027 (4) | 0.342 | UNKNOWN_NO_INJURY_ROW |
| RB | Myles Montgomery | 4000 | fringe *(no history)* | 16 | — | — | — | UNKNOWN_NO_INJURY_ROW |
| RB | Lan Larison | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| RB | Reggie Gilliam | 4000 | rotational | 3 | 0.158 | 0.008 (74) | 0.271 | ROW_NO_STATUS: Limited Participation in Practice |
| WR | Romeo Doubs | 5100 | rotational | 2 | 0.636 | 0.160 (59) | 1.000 | UNKNOWN_NO_INJURY_ROW |
| WR | Mack Hollins | 4200 | rotational | 3 | 0.588 | 0.221 (91) | 0.978 | UNKNOWN_NO_INJURY_ROW |
| WR | DeMario Douglas | 3700 | fringe | 5 | 0.220 | 0.071 (48) | 0.886 | UNKNOWN_NO_INJURY_ROW |
| WR | Kyle Williams | 3400 | fringe | 4 | 0.414 | 0.062 (17) | 0.628 | UNKNOWN_NO_INJURY_ROW |
| WR | Efton Chism III | 3000 | fringe | 6 | 0.145 | 0.022 (6) | 0.493 | UNKNOWN_NO_INJURY_ROW |
| WR | A.J. Brown | 3000 | starter | 1 | 0.785 | 0.300 (89) | 1.000 | UNKNOWN_NO_INJURY_ROW |
| WR | Jeremiah Webb | 3000 | fringe *(no history)* | 20 | — | — | — | UNKNOWN_NO_INJURY_ROW |
| WR | Kyle Dixon | 3000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| WR | Chandler Brayboy | 3000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| WR | Cameron Dorner | 3000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| TE | Hunter Henry | 3900 | starter | 1 | 0.782 | 0.187 (94) | 1.000 | UNKNOWN_NO_INJURY_ROW |
| TE | Eli Raridon | 2900 | fringe *(no history)* | 9 | — | — | — | ROW_NO_STATUS: Limited Participation in Practice |
| TE | Cameron Latu | 2500 | rotational | 3 | 0.112 | 0.000 (12) | 0.000 | UNKNOWN_NO_INJURY_ROW |
| TE | Tanner Arkin | 2500 | fringe *(no history)* | 15 | — | — | — | UNKNOWN_NO_INJURY_ROW |
| TE | Julian Hill | 2500 | rotational | 2 | 0.452 | 0.048 (45) | 0.748 | UNKNOWN_NO_INJURY_ROW |
| TE | Tanner Conner | 2500 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| DST | Patriots | 2700 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |

### JAX — 25 DK rows, $2500–$6000

10 with prior history · 4 rostered but no history · 11 no features

Depth chart consumed: `2026-09-24T06:01:34Z`, 69.97h before the clock, 16 listed.


| pos | player | $ | role | rank | trail snap (prior) | tgt share (prior, n) | part. EWMA (prior) | injury |
|---|---|---|---|---|---|---|---|---|
| QB | Trevor Lawrence | 5700 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| QB | Quinn Ewers | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| QB | Nick Mullens | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| QB | Joey Aguilar | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| RB | Bhayshul Tuten | 5600 | rotational | 3 | 0.161 | 0.028 (15) | 0.544 | UNKNOWN_NO_INJURY_ROW |
| RB | Chris Rodriguez Jr. | 4600 | starter | 1 | 0.319 | 0.020 (27) | 0.570 | UNKNOWN_NO_INJURY_ROW |
| RB | LeQuint Allen Jr. | 4000 | rotational | 2 | 0.225 | 0.013 (17) | 0.310 | ROW_NO_STATUS: Limited Participation in Practice |
| RB | Ameer Abdullah | 4000 | fringe | 4 | 0.114 | 0.055 (83) | 0.921 | UNKNOWN_NO_INJURY_ROW |
| RB | J'Mari Taylor | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| WR | Parker Washington | 6000 | rotational | 2 | 0.568 | 0.213 (40) | 0.991 | UNKNOWN_NO_INJURY_ROW |
| WR | Jakobi Meyers | 4800 | starter | 1 | 0.651 | 0.244 (92) | 1.000 | ROW_NO_STATUS: Limited Participation in Practice |
| WR | Brian Thomas Jr. | 4600 | rotational | 3 | 0.554 | 0.163 (31) | 1.000 | UNKNOWN_NO_INJURY_ROW |
| WR | Travis Hunter | 3100 | fringe | 4 | 0.360 | 0.175 (7) | 1.000 | UNKNOWN_NO_INJURY_ROW |
| WR | Josh Cameron | 3000 | fringe *(no history)* | 14 | — | — | — | UNKNOWN_NO_INJURY_ROW |
| WR | CJ Williams | 3000 | fringe *(no history)* | 16 | — | — | — | UNKNOWN_NO_INJURY_ROW |
| WR | Tim Jones | 3000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| WR | Austin Trammell | 3000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| WR | Michael Wortham | 3000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| WR | Trebor Pena | 3000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| TE | Brenton Strange | 3400 | starter | 1 | 0.667 | 0.150 (43) | 0.996 | UNKNOWN_NO_INJURY_ROW |
| TE | Nate Boerkircher | 2500 | fringe *(no history)* | 8 | — | — | — | UNKNOWN_NO_INJURY_ROW |
| TE | Quintin Morris | 2500 | rotational | 2 | 0.329 | 0.044 (47) | 0.622 | UNKNOWN_NO_INJURY_ROW |
| TE | Tanner Koziol | 2500 | fringe *(no history)* | 13 | — | — | — | UNKNOWN_NO_INJURY_ROW |
| TE | Brenden Bates | 2500 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| DST | Jaguars | 2900 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |


---

## NYJ @ DET

### NYJ — 27 DK rows, $2100–$6400

13 with prior history · 4 rostered but no history · 10 no features

Depth chart consumed: `2026-09-24T06:01:34Z`, 69.97h before the clock, 19 listed.


| pos | player | $ | role | rank | trail snap (prior) | tgt share (prior, n) | part. EWMA (prior) | injury |
|---|---|---|---|---|---|---|---|---|
| QB | Geno Smith | 4900 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| QB | Cade Klubnik | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| QB | Bailey Zappe | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| QB | Will Levis | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| RB | Breece Hall | 6400 | starter | 1 | 0.591 | 0.083 (56) | 0.980 | UNKNOWN_NO_INJURY_ROW |
| RB | Braelon Allen | 4400 | rotational | 3 | 0.116 | 0.027 (21) | 0.550 | UNKNOWN_NO_INJURY_ROW |
| RB | Isaiah Davis | 4000 | rotational | 2 | 0.225 | 0.043 (25) | 0.804 | UNKNOWN_NO_INJURY_ROW |
| RB | Andrew Beck | 4000 | rotational | 3 | 0.121 | 0.024 (61) | 0.536 | UNKNOWN_NO_INJURY_ROW |
| RB | Kene Nwangwu | 4000 | fringe | 4 | 0.066 | 0.010 (16) | 0.307 | ROW_NO_STATUS: Did Not Participate In Practice |
| RB | Chip Trayanum | 4000 | fringe *(no history)* | 17 | — | — | — | UNKNOWN_NO_INJURY_ROW |
| RB | Al-Jay Henderson | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| WR | Garrett Wilson | 6300 | fringe | 4 | 0.154 | 0.328 (58) | 1.000 | UNKNOWN_NO_INJURY_ROW |
| WR | Adonai Mitchell | 4300 | starter | 1 | 0.594 | 0.245 (33) | 1.000 | UNKNOWN_NO_INJURY_ROW |
| WR | Isaiah Williams | 3300 | rotational | 2 | 0.569 | 0.138 (15) | 0.885 | UNKNOWN_NO_INJURY_ROW |
| WR | Arian Smith | 3000 | fringe | 5 | 0.144 | 0.027 (16) | 0.735 | UNKNOWN_NO_INJURY_ROW |
| WR | Tim Patrick | 3000 | rotational | 3 | 0.379 | 0.080 (62) | 0.858 | UNKNOWN_NO_INJURY_ROW |
| WR | Omar Cooper Jr. | 3000 | fringe *(no history)* | 18 | — | — | — | UNKNOWN_NO_INJURY_ROW |
| WR | Malik McClain | 3000 | fringe *(no history)* | 14 | — | — | — | UNKNOWN_NO_INJURY_ROW |
| WR | Tyler Johnson | 3000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| WR | Jamaal Pritchett | 3000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| WR | Sterling Shepard | 3000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| TE | Kenyon Sadiq | 3500 | fringe *(no history)* | 4 | — | — | — | UNKNOWN_NO_INJURY_ROW |
| TE | Mason Taylor | 2500 | rotational | 2 | 0.390 | 0.175 (13) | 1.000 | ROW_NO_STATUS: Did Not Participate In Practice |
| TE | Jeremy Ruckert | 2500 | starter | 1 | 0.544 | 0.076 (51) | 0.714 | UNKNOWN_NO_INJURY_ROW |
| TE | Jelani Woods | 2500 | fringe | 4 | 0.113 | 0.085 (18) | 0.838 | UNKNOWN_NO_INJURY_ROW |
| TE | Cody Hardy | 2500 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| DST | Jets | 2100 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |

### DET — 22 DK rows, $2500–$8800

12 with prior history · 2 rostered but no history · 8 no features

Depth chart consumed: `2026-09-24T06:01:34Z`, 69.97h before the clock, 16 listed.


| pos | player | $ | role | rank | trail snap (prior) | tgt share (prior, n) | part. EWMA (prior) | injury |
|---|---|---|---|---|---|---|---|---|
| QB | Jared Goff | 6300 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| QB | Joshua Dobbs | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| QB | Luke Altmyer | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| RB | Jahmyr Gibbs | 8800 | starter | 1 | 0.741 | 0.199 (49) | 1.000 | UNKNOWN_NO_INJURY_ROW |
| RB | Sione Vaki | 4300 | fringe | 4 | 0.001 | 0.010 (8) | 0.215 | UNKNOWN_NO_INJURY_ROW |
| RB | Jacob Saylors | 4000 | rotational | 3 | 0.014 | 0.000 (1) | 0.000 | UNKNOWN_NO_INJURY_ROW |
| RB | Isiah Pacheco | 4000 | rotational | 2 | 0.271 | 0.068 (51) | 0.485 | UNKNOWN_NO_INJURY_ROW |
| RB | Jabari Small | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| WR | Amon-Ra St. Brown | 7900 | rotational | 2 | 0.827 | 0.314 (83) | 1.000 | UNKNOWN_NO_INJURY_ROW |
| WR | Jameson Williams | 5400 | starter | 1 | 0.927 | 0.212 (50) | 1.000 | UNKNOWN_NO_INJURY_ROW |
| WR | Isaac TeSlaa | 3400 | rotational | 3 | 0.591 | 0.069 (17) | 0.947 | UNKNOWN_NO_INJURY_ROW |
| WR | Tom Kennedy | 3000 | fringe | 4 | 0.092 | 0.036 (23) | 0.443 | UNKNOWN_NO_INJURY_ROW |
| WR | Tay Martin | 3000 | fringe | 5 | 0.064 | 0.027 (6) | 0.529 | UNKNOWN_NO_INJURY_ROW |
| WR | Kendrick Law | 3000 | fringe *(no history)* | 16 | — | — | — | UNKNOWN_NO_INJURY_ROW |
| WR | Dominic Lovett | 3000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| WR | Lucky Jackson | 3000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| TE | Sam LaPorta | 4300 | starter | 1 | 0.461 | 0.178 (42) | 1.000 | UNKNOWN_NO_INJURY_ROW |
| TE | Brock Wright | 2500 | rotational | 2 | 0.331 | 0.075 (69) | 0.789 | UNKNOWN_NO_INJURY_ROW |
| TE | Tyler Conklin | 2500 | rotational | 3 | 0.084 | 0.035 (91) | 0.785 | UNKNOWN_NO_INJURY_ROW |
| TE | Jackson Meeks | 2500 | fringe *(no history)* | 14 | — | — | — | UNKNOWN_NO_INJURY_ROW |
| TE | Thomas Gordon | 2500 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| DST | Lions | 3500 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |


---

## SEA @ WAS

### SEA — 26 DK rows, $2500–$8600

15 with prior history · 2 rostered but no history · 9 no features

Depth chart consumed: `2026-09-24T06:01:34Z`, 69.97h before the clock, 20 listed.


| pos | player | $ | role | rank | trail snap (prior) | tgt share (prior, n) | part. EWMA (prior) | injury |
|---|---|---|---|---|---|---|---|---|
| QB | Sam Darnold | 5400 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| QB | Drew Lock | 5200 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| QB | Jalen Milroe | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| RB | Jadarian Price | 5300 | fringe *(no history)* | 5 | — | — | — | ROW_NO_STATUS: Limited Participation in Practice |
| RB | Emanuel Wilson | 4900 | rotational | 2 | 0.397 | 0.034 (40) | 0.590 | UNKNOWN_NO_INJURY_ROW |
| RB | George Holani | 4500 | fringe | 4 | 0.033 | 0.022 (6) | 0.224 | ROW_NO_STATUS: Limited Participation in Practice |
| RB | Zach Charbonnet | 4000 | starter | 1 | 0.469 | 0.067 (49) | 0.830 | UNKNOWN_NO_INJURY_ROW |
| RB | Jacardia Wright | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| RB | Brady Russell | 4000 | fringe | 5 | 0.010 | 0.004 (9) | 0.236 | ROW_NO_STATUS: Limited Participation in Practice |
| RB | Velus Jones Jr. | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| RB | Robbie Ouzts | 4000 | rotational | 3 | 0.195 | 0.000 (12) | 0.000 | UNKNOWN_NO_INJURY_ROW |
| WR | Jaxon Smith-Njigba | 8600 | starter | 1 | 0.845 | 0.332 (51) | 1.000 | UNKNOWN_NO_INJURY_ROW |
| WR | Rashid Shaheed | 4200 | rotational | 3 | 0.359 | 0.102 (51) | 1.000 | UNKNOWN_NO_INJURY_ROW |
| WR | Cooper Kupp | 4000 | rotational | 2 | 0.795 | 0.147 (81) | 1.000 | ROW_NO_STATUS: Limited Participation in Practice |
| WR | Tory Horton | 3000 | fringe | 4 | 0.258 | 0.106 (8) | 0.951 | UNKNOWN_NO_INJURY_ROW |
| WR | Montorie Foster Jr. | 3000 | fringe *(no history)* | 18 | — | — | — | UNKNOWN_NO_INJURY_ROW |
| WR | Irvin Charles | 3000 | fringe | 6 | 0.014 | 0.010 (12) | 0.313 | UNKNOWN_NO_INJURY_ROW |
| WR | Jake Bobo | 3000 | fringe | 5 | 0.090 | 0.004 (45) | 0.147 | UNKNOWN_NO_INJURY_ROW |
| WR | Ricky White III | 3000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| WR | Julian Hicks | 3000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| WR | Emmanuel Henderson Jr. | 3000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| TE | AJ Barner | 3100 | starter | 1 | 0.794 | 0.172 (34) | 0.964 | UNKNOWN_NO_INJURY_ROW |
| TE | Eric Saubert | 2500 | rotational | 2 | 0.246 | 0.028 (76) | 0.548 | UNKNOWN_NO_INJURY_ROW |
| TE | Elijah Arroyo | 2500 | fringe | 4 | 0.154 | 0.079 (13) | 1.000 | UNKNOWN_NO_INJURY_ROW |
| TE | Nick Kallerup | 2500 | rotational | 3 | 0.176 | 0.010 (8) | 0.061 | UNKNOWN_NO_INJURY_ROW |
| DST | Seahawks | 3800 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |

### WAS — 27 DK rows, $2300–$6000

13 with prior history · 2 rostered but no history · 12 no features

Depth chart consumed: `2026-09-24T06:01:34Z`, 69.97h before the clock, 18 listed.


| pos | player | $ | role | rank | trail snap (prior) | tgt share (prior, n) | part. EWMA (prior) | injury |
|---|---|---|---|---|---|---|---|---|
| QB | Jayden Daniels | 6000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| QB | Marcus Mariota | 4500 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| QB | Athan Kaliakmanis | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| QB | Sam Hartman | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| RB | Jacory Croskey-Merritt | 5300 | rotational | 3 | 0.345 | 0.004 (17) | 0.193 | UNKNOWN_NO_INJURY_ROW |
| RB | Rachaad White | 5100 | starter | 1 | 0.461 | 0.073 (67) | 0.996 | UNKNOWN_NO_INJURY_ROW |
| RB | Kaytron Allen | 4300 | fringe *(no history)* | 11 | — | — | — | ROW_NO_STATUS: Limited Participation in Practice |
| RB | Jeremy McNichols | 4000 | rotational | 2 | 0.350 | 0.077 (62) | 0.938 | UNKNOWN_NO_INJURY_ROW |
| RB | Robert Henry Jr. | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| RB | Craig Reynolds | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| WR | Stefon Diggs | 5500 | starter | 1 | 0.539 | 0.205 (91) | 1.000 | UNKNOWN_NO_INJURY_ROW |
| WR | Terry McLaurin | 5100 | rotational | 3 | 0.534 | 0.245 (93) | 1.000 | UNKNOWN_NO_INJURY_ROW |
| WR | Antonio Williams | 4100 | fringe *(no history)* | 10 | — | — | — | UNKNOWN_NO_INJURY_ROW |
| WR | Dyami Brown | 3200 | fringe | 6 | 0.090 | 0.042 (77) | 0.520 | UNKNOWN_NO_INJURY_ROW |
| WR | Jaylin Lane | 3000 | fringe | 5 | 0.175 | 0.083 (14) | 0.830 | ROW_NO_STATUS: Limited Participation in Practice |
| WR | Treylon Burks | 3000 | rotational | 2 | 0.537 | 0.125 (35) | 0.987 | UNKNOWN_NO_INJURY_ROW |
| WR | Luke McCaffrey | 3000 | fringe | 4 | 0.228 | 0.076 (24) | 0.914 | UNKNOWN_NO_INJURY_ROW |
| WR | Jaden Bradley | 3000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| WR | Van Jefferson | 3000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| WR | River Cracraft | 3000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| TE | Chig Okonkwo | 3600 | starter | 1 | 0.591 | 0.161 (68) | 0.996 | ROW_NO_STATUS: Did Not Participate In Practice |
| TE | Ben Sinnott | 2600 | rotational | 3 | 0.404 | 0.069 (32) | 0.785 | UNKNOWN_NO_INJURY_ROW |
| TE | John Bates | 2500 | rotational | 2 | 0.576 | 0.044 (81) | 0.661 | UNKNOWN_NO_INJURY_ROW |
| TE | Colson Yankoff | 2500 | fringe | 4 | 0.119 | 0.013 (14) | 0.260 | UNKNOWN_NO_INJURY_ROW |
| TE | Tyler Ott | 2500 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| TE | Jack Westover | 2500 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| DST | Commanders | 2300 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |


---

## TEN @ NYG

### TEN — 24 DK rows, $2400–$5400

11 with prior history · 2 rostered but no history · 11 no features

Depth chart consumed: `2026-09-24T06:01:34Z`, 69.97h before the clock, 16 listed.


| pos | player | $ | role | rank | trail snap (prior) | tgt share (prior, n) | part. EWMA (prior) | injury |
|---|---|---|---|---|---|---|---|---|
| QB | Cam Ward | 5100 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| QB | Mitchell Trubisky | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| QB | Hendon Hooker | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| RB | Tony Pollard | 5400 | starter | 1 | 0.532 | 0.062 (97) | 0.782 | ROW_NO_STATUS: Did Not Participate In Practice |
| RB | Tyjae Spears | 4900 | rotational | 2 | 0.466 | 0.142 (42) | 0.981 | ROW_NO_STATUS: Did Not Participate In Practice |
| RB | Julius Chestnut | 4000 | rotational | 3 | 0.013 | 0.009 (22) | 0.241 | UNKNOWN_NO_INJURY_ROW |
| RB | Nick Singleton | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| RB | Kalel Mullings | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| RB | Michael Carter | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| WR | Carnell Tate | 5000 | fringe *(no history)* | 4 | — | — | — | UNKNOWN_NO_INJURY_ROW |
| WR | Wan'Dale Robinson | 4500 | starter | 1 | 0.814 | 0.372 (54) | 1.000 | UNKNOWN_NO_INJURY_ROW |
| WR | Calvin Ridley | 4000 | fringe | 4 | 0.003 | 0.171 (61) | 1.000 | UNKNOWN_NO_INJURY_ROW |
| WR | Elic Ayomanor | 3300 | rotational | 2 | 0.703 | 0.176 (16) | 1.000 | UNKNOWN_NO_INJURY_ROW |
| WR | Chimere Dike | 3000 | rotational | 3 | 0.661 | 0.168 (17) | 0.990 | UNKNOWN_NO_INJURY_ROW |
| WR | Xavier Restrepo | 3000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| WR | Tyren Montgomery | 3000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| WR | K.J. Osborn | 3000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| TE | Gunnar Helm | 2900 | rotational | 2 | 0.531 | 0.122 (16) | 1.000 | UNKNOWN_NO_INJURY_ROW |
| TE | Daniel Bellinger | 2500 | starter | 1 | 0.595 | 0.054 (60) | 0.750 | UNKNOWN_NO_INJURY_ROW |
| TE | David Martin-Robinson | 2500 | fringe | 4 | 0.190 | 0.020 (15) | 0.515 | UNKNOWN_NO_INJURY_ROW |
| TE | Kylen Granson | 2500 | rotational | 3 | 0.203 | 0.028 (76) | 0.316 | UNKNOWN_NO_INJURY_ROW |
| TE | Jaren Kanak | 2500 | fringe *(no history)* | 16 | — | — | — | UNKNOWN_NO_INJURY_ROW |
| TE | Joel Wilson | 2500 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| DST | Titans | 2400 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |

### NYG — 26 DK rows, $2500–$6500

13 with prior history · 1 rostered but no history · 12 no features

Depth chart consumed: `2026-09-24T06:01:34Z`, 69.97h before the clock, 16 listed.


| pos | player | $ | role | rank | trail snap (prior) | tgt share (prior, n) | part. EWMA (prior) | injury |
|---|---|---|---|---|---|---|---|---|
| QB | Jaxson Dart | 5900 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| QB | Jameis Winston | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| QB | Jake Haener | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| RB | Cam Skattebo | 6200 | fringe | 4 | 0.275 | 0.129 (8) | 1.000 | UNKNOWN_NO_INJURY_ROW |
| RB | Najee Harris | 4700 | fringe | 5 | 0.016 | 0.060 (71) | 0.732 | UNKNOWN_NO_INJURY_ROW |
| RB | Devin Singletary | 4200 | rotational | 3 | 0.359 | 0.062 (98) | 0.664 | UNKNOWN_NO_INJURY_ROW |
| RB | Tyrone Tracy Jr. | 4100 | starter | 1 | 0.639 | 0.122 (32) | 0.963 | UNKNOWN_NO_INJURY_ROW |
| RB | Patrick Ricard | 4000 | rotational | 2 | 0.416 | 0.011 (90) | 0.314 | UNKNOWN_NO_INJURY_ROW |
| RB | Phil Mafah | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| RB | Grant Finley | 4000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| WR | Malik Nabers | 6500 | rotational | 2 | 0.397 | 0.315 (19) | 1.000 | ROW_NO_STATUS: Limited Participation in Practice |
| WR | Malachi Fields | 4400 | fringe *(no history)* | 9 | — | — | — | UNKNOWN_NO_INJURY_ROW |
| WR | Darnell Mooney | 4100 | starter | 1 | 0.807 | 0.161 (91) | 1.000 | UNKNOWN_NO_INJURY_ROW |
| WR | Odell Beckham Jr. | 3300 | fringe | 5 | 0.104 | 0.066 (44) | 0.948 | UNKNOWN_NO_INJURY_ROW |
| WR | Braxton Berrios | 3000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| WR | Calvin Austin III | 3000 | rotational | 3 | 0.309 | 0.103 (48) | 1.000 | UNKNOWN_NO_INJURY_ROW |
| WR | Gunner Olszewski | 3000 | fringe | 4 | 0.190 | 0.051 (47) | 0.500 | UNKNOWN_NO_INJURY_ROW |
| WR | Dalen Cambre | 3000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| WR | Jalin Hyatt | 3000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| WR | Charlie Jones | 3000 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| TE | Isaiah Likely | 4700 | rotational | 2 | 0.539 | 0.115 (63) | 0.754 | UNKNOWN_NO_INJURY_ROW |
| TE | Theo Johnson | 2700 | starter | 1 | 0.674 | 0.188 (27) | 0.997 | UNKNOWN_NO_INJURY_ROW |
| TE | Chris Manhertz | 2500 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| TE | Thomas Fidone II | 2500 | rotational | 3 | 0.033 | 0.000 (2) | 0.000 | UNKNOWN_NO_INJURY_ROW |
| TE | Ben Mann | 2500 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |
| DST | Giants | 3400 | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | **NO_FEATURES** | NO_FEATURE_ROW |

