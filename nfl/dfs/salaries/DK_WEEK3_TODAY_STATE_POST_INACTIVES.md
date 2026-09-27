# DK Week 3 Early Only — POST-INACTIVES football state

**State:** `POST_REPORTED_INACTIVES / NO_OFFICIAL_DOCUMENT_CAPTURED`  
**Built:** 2026-09-27T16:24:41Z · **Kickoff:** 2026-09-27T17:00:00Z  
**Spec:** `dk-post-inactives-state-1`

## Read this before quoting anything below

**What this is.** the football state after a post-inactives research pass, snapshot 2026-09-27 12:04 ET. Fifteen absences and eight availabilities are named and each carries the sentence and the URL it came from.

**What this is not.** a capture of any official game-day inactive list. Zero bytes of any NFL or club release for 2026-09-27 are held in this repository, so NO player carries CONFIRMED_INACTIVE or CONFIRMED_ACTIVE. The source asked for exactly this distinction: everything from RotoWire stays REPORTED_HIGH_CONFIDENCE rather than CONFIRMED_OFFICIAL until matched to an NFL or team release.

**The gap that dominates everything else.** The source states RotoWire now displays populated inactive lists for all nine games, and it relays the names that matter for football. It does not relay the complete contents of any list. So a DK player who is simply not mentioned is NOT established as not-on-the-list: he is unresolved. Treating silence as activation is the same defect as treating missing as zero, and it would wrongly activate roughly 420 rows.

| lists populated per the source | 9 |
|---|---|
| lists enumerated to this repository | **0** |
| `UNKNOWN_NOT_RELAYED` | 437 |
| `REPORTED_INACTIVE_HIGH_CONFIDENCE` | 10 |
| `REPORTED_ACTIVE_NOT_ON_LIST` | 7 |
| `REPORTED_INACTIVE_OFFICIAL_RELEASE_CITED` | 3 |

## PRE → POST semantic diff

20 players changed availability state. A further 437 had only their status STRING change, from UNKNOWN to the more specific UNKNOWN_NOT_RELAYED, which is a naming improvement and not a football event. Quote the first number, never the sum.

This is **not** `baseline_diff.py`. That module compares DraftKings salary, roster position, club and display name, and raises `IDENTITY_REGRESSED` as a FAIL — point it at a post-inactives comparison and a roster churn reads as a defect in our own chain while a salary move sits in the same list as a player being ruled out. This comparator separates availability, role, opportunity, redistribution, newly-relevant and environment, and quarantines every DraftKings or third-party field change with `football_change: false`.

| club | player | $ | from | to | tier | document held |
|---|---|--:|---|---|---|---|
| HOU | Nico Collins | 7000 | `UNKNOWN` | `REPORTED_INACTIVE_OFFICIAL_RELEASE_CITED` | OFFICIAL_TEAM_RELEASE_CITED | **no** |
| WAS | Jayden Daniels | 6000 | `UNKNOWN` | `REPORTED_INACTIVE_HIGH_CONFIDENCE` | AGGREGATOR_REPORTED | **no** |
| BUF | DJ Moore | 5800 | `UNKNOWN` | `REPORTED_ACTIVE_NOT_ON_LIST` | AGGREGATOR_REPORTED | **no** |
| PIT | Jaylen Warren | 5700 | `UNKNOWN` | `REPORTED_ACTIVE_NOT_ON_LIST` | AGGREGATOR_REPORTED | **no** |
| IND | Alec Pierce | 5600 | `UNKNOWN` | `REPORTED_INACTIVE_HIGH_CONFIDENCE` | AGGREGATOR_REPORTED | **no** |
| CAR | Jalen Coker | 5500 | `UNKNOWN` | `REPORTED_ACTIVE_NOT_ON_LIST` | AGGREGATOR_REPORTED | **no** |
| SEA | Sam Darnold | 5400 | `UNKNOWN` | `REPORTED_ACTIVE_NOT_ON_LIST` | OFFICIAL_TEAM_RELEASE_CITED | **no** |
| TEN | Tyjae Spears | 4900 | `UNKNOWN` | `REPORTED_ACTIVE_NOT_ON_LIST` | AGGREGATOR_REPORTED | **no** |
| PIT | Michael Pittman Jr. | 4700 | `UNKNOWN` | `REPORTED_ACTIVE_NOT_ON_LIST` | AGGREGATOR_REPORTED | **no** |
| PIT | Rico Dowdle | 4700 | `UNKNOWN` | `REPORTED_INACTIVE_HIGH_CONFIDENCE` | AGGREGATOR_REPORTED | **no** |
| NYJ | Adonai Mitchell | 4300 | `UNKNOWN` | `REPORTED_INACTIVE_HIGH_CONFIDENCE` | AGGREGATOR_REPORTED | **no** |
| BUF | Keon Coleman | 4300 | `UNKNOWN` | `REPORTED_ACTIVE_NOT_ON_LIST` | AGGREGATOR_REPORTED | **no** |
| NYG | Devin Singletary | 4200 | `UNKNOWN` | `REPORTED_INACTIVE_HIGH_CONFIDENCE` | AGGREGATOR_REPORTED | **no** |
| MIA | Jaylen Wright | 4000 | `UNKNOWN` | `REPORTED_INACTIVE_HIGH_CONFIDENCE` | AGGREGATOR_REPORTED | **no** |
| WAS | Chig Okonkwo | 3600 | `UNKNOWN` | `REPORTED_INACTIVE_HIGH_CONFIDENCE` | AGGREGATOR_REPORTED | **no** |
| IND | Darius Slayton | 3500 | `UNKNOWN` | `REPORTED_INACTIVE_HIGH_CONFIDENCE` | AGGREGATOR_REPORTED | **no** |
| CAR | Xavier Legette | 3500 | `UNKNOWN` | `REPORTED_INACTIVE_HIGH_CONFIDENCE` | AGGREGATOR_REPORTED | **no** |
| IND | Ashton Dulin | 3200 | `UNKNOWN` | `REPORTED_INACTIVE_OFFICIAL_RELEASE_CITED` | OFFICIAL_TEAM_RELEASE_CITED | **no** |
| NE | Eli Raridon | 2900 | `UNKNOWN` | `REPORTED_INACTIVE_HIGH_CONFIDENCE` | AGGREGATOR_REPORTED | **no** |
| NYJ | Mason Taylor | 2500 | `UNKNOWN` | `REPORTED_INACTIVE_OFFICIAL_RELEASE_CITED` | OFFICIAL_TEAM_RELEASE_CITED | **no** |

**Quarantined non-football changes: 0.** **Opportunity drift: 0** — observed weeks 1–2 is history and must be identical across both passes, so a non-zero count here would be a builder defect rather than football.

### Guards

- `rows_preserved` → **PASS** `DK_ROWS_PRESERVED`
- `pre_intact` → **PASS** `PRE_ARTIFACT_INTACT`
- `no_unauthorised_promotion` → **PASS** `NO_UNAUTHORISED_PROMOTION`

## Redistribution

No share of any vacancy is assigned to anybody. Every tree carries `UNRESOLVED_DISTRIBUTION`, a candidate ranking whose basis is stated, and the non-player sinks that compete with every candidate.

| vacancy | pos | $ | vacated (observed W1–2) | same-group ranked | competing sinks |
|---|---|--:|---|---|--:|
| **CAR:Xavier Legette** | WR | 3500 | 69 snaps · 0 car · 6 tgt · 1 rz · 0 gl · routes UNKNOWN | Tetairoa McMillan, Jalen Coker, Brycen Tremayne | 3 |
| **HOU:Nico Collins** | WR | 7000 | 57 snaps · 1 car · 10 tgt · 2 rz · 0 gl · routes UNKNOWN | Xavier Hutchinson, Kayshon Boutte, Jaylin Noel | 3 |
| **IND:Alec Pierce** | WR | 5600 | 49 snaps · 0 car · 7 tgt · 1 rz · 0 gl · routes UNKNOWN | Josh Downs, Keenan Allen, Laquon Treadwell | 3 |
| **IND:Ashton Dulin** | WR | 3200 | 10 snaps · 0 car · 1 tgt · 0 rz · 0 gl · routes UNKNOWN | Josh Downs, Keenan Allen, Laquon Treadwell | 3 |
| **IND:Darius Slayton** | WR | 3500 | **UNKNOWN_NO_OBSERVED_ROW** (not zero) | Josh Downs, Keenan Allen, Laquon Treadwell | 3 |
| **MIA:Jaylen Wright** | RB | 4000 | 7 snaps · 3 car · 0 tgt · 2 rz · 0 gl · routes UNKNOWN | De'Von Achane, Ollie Gordon II, Carlos Washington Jr. | 3 |
| **NE:Eli Raridon** | TE | 2900 | 49 snaps · 0 car · 2 tgt · 1 rz · 1 gl · routes UNKNOWN | Hunter Henry, Cameron Latu, Julian Hill | 2 |
| **NYG:Devin Singletary** | RB | 4200 | 40 snaps · 9 car · 5 tgt · 3 rz · 0 gl · routes UNKNOWN | Cam Skattebo, Patrick Ricard, Najee Harris | 3 |
| **NYJ:Adonai Mitchell** | WR | 4300 | 107 snaps · 0 car · 15 tgt · 1 rz · 0 gl · routes UNKNOWN | Garrett Wilson, Isaiah Williams, Omar Cooper Jr. | 3 |
| **NYJ:Mason Taylor** | TE | 2500 | 78 snaps · 0 car · 3 tgt · 0 rz · 0 gl · routes UNKNOWN | Kenyon Sadiq, Jeremy Ruckert, Jelani Woods | 2 |
| **PIT:Rico Dowdle** | RB | 4700 | 57 snaps · 15 car · 7 tgt · 1 rz · 0 gl · routes UNKNOWN | Jaylen Warren, Riley Nowakowski, Travis Homer | 3 |
| **WAS:Chig Okonkwo** | TE | 3600 | 39 snaps · 0 car · 3 tgt · 0 rz · 0 gl · routes UNKNOWN | Ben Sinnott, John Bates, Colson Yankoff | 2 |
| **WAS:Jayden Daniels** | QB | 6000 | 109 snaps · 12 car · 0 tgt · 4 rz · 0 gl · routes UNKNOWN | Marcus Mariota, Athan Kaliakmanis, Sam Hartman | 2 |

**Newly relevant (reserve, the role may not exist):** Athan Kaliakmanis, Brycen Tremayne, Cameron Latu, Carlos Washington Jr., Colson Yankoff, Julian Hill, Malik McClain, Najee Harris, Ollie Gordon II, Omar Cooper Jr., Riley Nowakowski, Sam Hartman, Travis Homer

**Concentration gainers (established, the role may get denser):** Ben Sinnott, Cam Skattebo, Dalton Schultz, Darren Waller, De'Von Achane, Garrett Wilson, Hunter Henry, Isaiah Williams, Jalen Coker, Jared Wayne, Jaylen Warren, Jaylin Noel, Jelani Woods, Josh Downs, Kayshon Boutte, Keenan Allen, Kenyon Sadiq, Laquon Treadwell, Malik Willis, Marcus Mariota, Tetairoa McMillan, Tommy Tremble, Tyler Warren, Xavier Hutchinson

newly_relevant_players are reserves below the 0.25 observed snap threshold who are now plausibly in line -- a role that may not exist at all. concentration_gainers are established contributors whose existing role may get denser. A first cut lumped them and returned 128 names, which is a roster rather than a finding.

## Environment

| game | change | detail |
|---|---|---|
| CAR@CLE | MOVED | spread CAR -2 → CAR -1.5; total 42.5 → 41.5; away_implied 22.25 → 21.5; home_implied 20.25 → 20.0 |
| CIN@PIT | MOVED | spread CIN -3.5 → CIN -3; away_implied 23.0 → 22.75; home_implied 19.5 → 19.75 |
| HOU@IND | UNCHANGED | — |
| KC@MIA | MOVED | spread KC -10.5 → KC -9.5; total 45.5 → 45.0; away_implied 28.0 → 27.25; home_implied 17.5 → 17.75 |
| LAC@BUF | MOVED | total 50.0 → 50.5; away_implied 21.5 → 21.75; home_implied 28.5 → 28.75 |
| NE@JAX | UNCHANGED | — |
| NYJ@DET | UNCHANGED | — |
| SEA@WAS | MOVED | spread SEA -7.5 → SEA -8.5; total 40.0 → 40.5; away_implied 23.75 → 24.5; home_implied 16.25 → 16.0 |
| TEN@NYG | UNCHANGED | — |

The market moved on five of nine games. That is information about the market. There is no projection of ours for it to agree or disagree with.

## The nine games

### CAR@CLE

CAR -1.5 · total 41.5 · implied 21.5 / 20.0 · Outdoor; 67F, 15 mph north wind

**CAR** — 23 DK rows still unresolved

| reported OUT | pos | $ | tier |
|---|---|--:|---|
| Xavier Legette | WR | 3500 | AGGREGATOR_REPORTED |

reported available: Jalen Coker ($5500, LIMITED)

observed W1–2 — carries: Chuba Hubbard 22, Jonathon Brooks 9, AJ Dillon 8, Bryce Young 3, Kenny Pickett 2

observed W1–2 — targets: Tetairoa McMillan 18, Jalen Coker 18, Tommy Tremble 7, Xavier Legette 6, Chuba Hubbard 5, Darren Waller 5

*CAR:Xavier Legette* vacates 69 snaps · 0 car · 6 tgt · 1 rz · 0 gl · routes UNKNOWN → ranked Tetairoa McMillan, Jalen Coker, Brycen Tremayne; inheritance `UNRESOLVED_DISTRIBUTION`
  newly relevant: Brycen Tremayne

**CLE** — 24 DK rows still unresolved

observed W1–2 — carries: Quinshon Judkins 24, Deshaun Watson 13, Raheim Sanders 3, Jaleel McLaughlin 1

observed W1–2 — targets: Denzel Boston 11, KC Concepcion Jr. 11, Harold Fannin Jr. 9, Quinshon Judkins 7, Jerry Jeudy 5, Raheim Sanders 4

**Remaining uncertainty**
- CAR: 23 DK rows still UNKNOWN_NOT_RELAYED
- CAR:Xavier Legette: inheritance UNRESOLVED_DISTRIBUTION across 4 same-group candidates
- CAR Jalen Coker: reported available AND reported limited -- availability resolved, workload not
- CLE: 24 DK rows still UNKNOWN_NOT_RELAYED
- routes and route participation UNKNOWN_SOURCE_UNAVAILABLE for every player in this game

**Correlation mechanisms** (mechanisms only — no recommendation, and no joint distribution held to weigh them)
- *CAR* — CAR pass volume links its quarterback to ['Tetairoa McMillan', 'Jalen Coker', 'Tommy Tremble'] through shared team dropbacks. They also compete for the same targets and the same touchdowns, so the link is positive on volume and negative on allocation at the same time.
- *CAR* — CAR quarterback and ['Chuba Hubbard', 'Jonathon Brooks'] share goal-line and short-yardage carries, so their scoring paths overlap rather than simply add.
- *CAR* — Chuba Hubbard and the CAR DST both express the same branch -- CAR leads, CLE throws, pressure and turnovers rise, carries follow. That link is only real where the back's opportunity is rushing-led rather than receiving-led.
- *CAR* — a CLE player supports a CAR stack only in the branch where CLE scores enough to keep CAR throwing. Which CLE player depends on the script, and is not automatically the running back.
- *CLE* — CLE pass volume links its quarterback to ['Denzel Boston', 'KC Concepcion Jr.', 'Harold Fannin Jr.'] through shared team dropbacks. They also compete for the same targets and the same touchdowns, so the link is positive on volume and negative on allocation at the same time.
- *CLE* — CLE quarterback and ['Quinshon Judkins', 'Deshaun Watson'] share goal-line and short-yardage carries, so their scoring paths overlap rather than simply add.
- *CLE* — Quinshon Judkins and the CLE DST both express the same branch -- CLE leads, CAR throws, pressure and turnovers rise, carries follow. That link is only real where the back's opportunity is rushing-led rather than receiving-led.
- *CLE* — a CAR player supports a CLE stack only in the branch where CAR scores enough to keep CLE throwing. Which CAR player depends on the script, and is not automatically the running back.

### CIN@PIT

CIN -3 · total 42.5 · implied 22.75 / 19.75 · Outdoor; 69F, 15 mph NNW wind

**CIN** — 24 DK rows still unresolved

observed W1–2 — carries: Chase Brown 36, Samaje Perine 7, Joe Burrow 6

observed W1–2 — targets: Tee Higgins 16, Ja'Marr Chase 13, Chase Brown 11, Mike Gesicki 7, Samaje Perine 4, Andrei Iosivas 4

**PIT** — 22 DK rows still unresolved

| reported OUT | pos | $ | tier |
|---|---|--:|---|
| Rico Dowdle | RB | 4700 | AGGREGATOR_REPORTED |

reported available: Jaylen Warren ($5700, LIMITED); Michael Pittman Jr. ($4700, LIMITED)

observed W1–2 — carries: Jaylen Warren 21, Rico Dowdle 15, Aaron Rodgers 4, Travis Homer 2, Mason Rudolph 1

observed W1–2 — targets: DK Metcalf 19, Roman Wilson 12, Jaylen Warren 10, Pat Freiermuth 10, Germie Bernard 8, Rico Dowdle 7

*PIT:Rico Dowdle* vacates 57 snaps · 15 car · 7 tgt · 1 rz · 0 gl · routes UNKNOWN → ranked Jaylen Warren, Riley Nowakowski, Travis Homer; inheritance `UNRESOLVED_DISTRIBUTION`
  newly relevant: Riley Nowakowski, Travis Homer

**Remaining uncertainty**
- CIN: 24 DK rows still UNKNOWN_NOT_RELAYED
- PIT: 22 DK rows still UNKNOWN_NOT_RELAYED
- PIT:Rico Dowdle: inheritance UNRESOLVED_DISTRIBUTION across 4 same-group candidates
- PIT Jaylen Warren: reported available AND reported limited -- availability resolved, workload not
- PIT Michael Pittman Jr.: reported available AND reported limited -- availability resolved, workload not
- routes and route participation UNKNOWN_SOURCE_UNAVAILABLE for every player in this game

**Correlation mechanisms** (mechanisms only — no recommendation, and no joint distribution held to weigh them)
- *CIN* — CIN pass volume links its quarterback to ['Tee Higgins', "Ja'Marr Chase", 'Chase Brown'] through shared team dropbacks. They also compete for the same targets and the same touchdowns, so the link is positive on volume and negative on allocation at the same time.
- *CIN* — CIN quarterback and ['Chase Brown', 'Samaje Perine'] share goal-line and short-yardage carries, so their scoring paths overlap rather than simply add.
- *CIN* — Chase Brown and the CIN DST both express the same branch -- CIN leads, PIT throws, pressure and turnovers rise, carries follow. That link is only real where the back's opportunity is rushing-led rather than receiving-led.
- *CIN* — a PIT player supports a CIN stack only in the branch where PIT scores enough to keep CIN throwing. Which PIT player depends on the script, and is not automatically the running back.
- *PIT* — PIT pass volume links its quarterback to ['DK Metcalf', 'Roman Wilson', 'Jaylen Warren'] through shared team dropbacks. They also compete for the same targets and the same touchdowns, so the link is positive on volume and negative on allocation at the same time.
- *PIT* — PIT quarterback and ['Jaylen Warren', 'Aaron Rodgers'] share goal-line and short-yardage carries, so their scoring paths overlap rather than simply add.
- *PIT* — Jaylen Warren and the PIT DST both express the same branch -- PIT leads, CIN throws, pressure and turnovers rise, carries follow. That link is only real where the back's opportunity is rushing-led rather than receiving-led.
- *PIT* — a CIN player supports a PIT stack only in the branch where CIN scores enough to keep PIT throwing. Which CIN player depends on the script, and is not automatically the running back.

### HOU@IND

HOU -1.5 · total 42.5 · implied 22.0 / 20.5 · Dome

**HOU** — 26 DK rows still unresolved

| reported OUT | pos | $ | tier |
|---|---|--:|---|
| Nico Collins | WR | 7000 | OFFICIAL_TEAM_RELEASE_CITED |

observed W1–2 — carries: David Montgomery 26, Woody Marks 17, C.J. Stroud 5

observed W1–2 — targets: Dalton Schultz 22, Xavier Hutchinson 15, Nico Collins 10, Jared Wayne 8, Woody Marks 7, Kayshon Boutte 7

*HOU:Nico Collins* vacates 57 snaps · 1 car · 10 tgt · 2 rz · 0 gl · routes UNKNOWN → ranked Xavier Hutchinson, Kayshon Boutte, Jaylin Noel; inheritance `UNRESOLVED_DISTRIBUTION`

**IND** — 24 DK rows still unresolved

| reported OUT | pos | $ | tier |
|---|---|--:|---|
| Alec Pierce | WR | 5600 | AGGREGATOR_REPORTED |
| Darius Slayton | WR | 3500 | AGGREGATOR_REPORTED |
| Ashton Dulin | WR | 3200 | OFFICIAL_TEAM_RELEASE_CITED |

observed W1–2 — carries: Jonathan Taylor 43, Daniel Jones 4, Seth McGowan 2

observed W1–2 — targets: Josh Downs 13, Tyler Warren 12, Keenan Allen 11, Jonathan Taylor 8, Alec Pierce 7, Laquon Treadwell 4

*IND:Alec Pierce* vacates 49 snaps · 0 car · 7 tgt · 1 rz · 0 gl · routes UNKNOWN → ranked Josh Downs, Keenan Allen, Laquon Treadwell; inheritance `UNRESOLVED_DISTRIBUTION`

*IND:Ashton Dulin* vacates 10 snaps · 0 car · 1 tgt · 0 rz · 0 gl · routes UNKNOWN → ranked Josh Downs, Keenan Allen, Laquon Treadwell; inheritance `UNRESOLVED_DISTRIBUTION`

*IND:Darius Slayton* vacates **UNKNOWN_NO_OBSERVED_ROW** (not zero) → ranked Josh Downs, Keenan Allen, Laquon Treadwell; inheritance `UNRESOLVED_DISTRIBUTION`

**Remaining uncertainty**
- HOU: 26 DK rows still UNKNOWN_NOT_RELAYED
- HOU:Nico Collins: inheritance UNRESOLVED_DISTRIBUTION across 4 same-group candidates
- IND: 24 DK rows still UNKNOWN_NOT_RELAYED
- IND:Alec Pierce: inheritance UNRESOLVED_DISTRIBUTION across 4 same-group candidates
- IND:Ashton Dulin: inheritance UNRESOLVED_DISTRIBUTION across 4 same-group candidates
- IND:Darius Slayton: inheritance UNRESOLVED_DISTRIBUTION across 4 same-group candidates
- routes and route participation UNKNOWN_SOURCE_UNAVAILABLE for every player in this game

**Correlation mechanisms** (mechanisms only — no recommendation, and no joint distribution held to weigh them)
- *HOU* — HOU pass volume links its quarterback to ['Dalton Schultz', 'Xavier Hutchinson', 'Jared Wayne'] through shared team dropbacks. They also compete for the same targets and the same touchdowns, so the link is positive on volume and negative on allocation at the same time.
- *HOU* — HOU quarterback and ['David Montgomery', 'Woody Marks'] share goal-line and short-yardage carries, so their scoring paths overlap rather than simply add.
- *HOU* — David Montgomery and the HOU DST both express the same branch -- HOU leads, IND throws, pressure and turnovers rise, carries follow. That link is only real where the back's opportunity is rushing-led rather than receiving-led.
- *HOU* — a IND player supports a HOU stack only in the branch where IND scores enough to keep HOU throwing. Which IND player depends on the script, and is not automatically the running back.
- *IND* — IND pass volume links its quarterback to ['Josh Downs', 'Tyler Warren', 'Keenan Allen'] through shared team dropbacks. They also compete for the same targets and the same touchdowns, so the link is positive on volume and negative on allocation at the same time.
- *IND* — IND quarterback and ['Jonathan Taylor', 'Daniel Jones'] share goal-line and short-yardage carries, so their scoring paths overlap rather than simply add.
- *IND* — Jonathan Taylor and the IND DST both express the same branch -- IND leads, HOU throws, pressure and turnovers rise, carries follow. That link is only real where the back's opportunity is rushing-led rather than receiving-led.
- *IND* — a HOU player supports a IND stack only in the branch where HOU scores enough to keep IND throwing. Which HOU player depends on the script, and is not automatically the running back.

### KC@MIA

KC -9.5 · total 45.0 · implied 27.25 / 17.75 · Outdoor; 84F, light wind

**KC** — 27 DK rows still unresolved

observed W1–2 — carries: Kenneth Walker III 47, Emmett Johnson 10, Patrick Mahomes 9

observed W1–2 — targets: Kenneth Walker III 16, Travis Kelce 16, Xavier Worthy 13, Rashee Rice 8, Tyquan Thornton 5, Emmett Johnson 4

**MIA** — 25 DK rows still unresolved

| reported OUT | pos | $ | tier |
|---|---|--:|---|
| Jaylen Wright | RB | 4000 | AGGREGATOR_REPORTED |

observed W1–2 — carries: De'Von Achane 31, Malik Willis 8, Jaylen Wright 3, Ollie Gordon II 3

observed W1–2 — targets: Malik Washington 13, De'Von Achane 11, Caleb Douglas 10, Greg Dulcich 5, DJ Herman 3, Chris Bell 3

*MIA:Jaylen Wright* vacates 7 snaps · 3 car · 0 tgt · 2 rz · 0 gl · routes UNKNOWN → ranked De'Von Achane, Ollie Gordon II, Carlos Washington Jr.; inheritance `UNRESOLVED_DISTRIBUTION`
  newly relevant: Ollie Gordon II, Carlos Washington Jr.

**Remaining uncertainty**
- KC: 27 DK rows still UNKNOWN_NOT_RELAYED
- MIA: 25 DK rows still UNKNOWN_NOT_RELAYED
- MIA:Jaylen Wright: inheritance UNRESOLVED_DISTRIBUTION across 4 same-group candidates
- routes and route participation UNKNOWN_SOURCE_UNAVAILABLE for every player in this game

**Correlation mechanisms** (mechanisms only — no recommendation, and no joint distribution held to weigh them)
- *KC* — KC pass volume links its quarterback to ['Kenneth Walker III', 'Travis Kelce', 'Xavier Worthy'] through shared team dropbacks. They also compete for the same targets and the same touchdowns, so the link is positive on volume and negative on allocation at the same time.
- *KC* — KC quarterback and ['Kenneth Walker III', 'Emmett Johnson'] share goal-line and short-yardage carries, so their scoring paths overlap rather than simply add.
- *KC* — Kenneth Walker III and the KC DST both express the same branch -- KC leads, MIA throws, pressure and turnovers rise, carries follow. That link is only real where the back's opportunity is rushing-led rather than receiving-led.
- *KC* — a MIA player supports a KC stack only in the branch where MIA scores enough to keep KC throwing. Which MIA player depends on the script, and is not automatically the running back.
- *MIA* — MIA pass volume links its quarterback to ['Malik Washington', "De'Von Achane", 'Caleb Douglas'] through shared team dropbacks. They also compete for the same targets and the same touchdowns, so the link is positive on volume and negative on allocation at the same time.
- *MIA* — MIA quarterback and ["De'Von Achane", 'Malik Willis'] share goal-line and short-yardage carries, so their scoring paths overlap rather than simply add.
- *MIA* — De'Von Achane and the MIA DST both express the same branch -- MIA leads, KC throws, pressure and turnovers rise, carries follow. That link is only real where the back's opportunity is rushing-led rather than receiving-led.
- *MIA* — a KC player supports a MIA stack only in the branch where KC scores enough to keep MIA throwing. Which KC player depends on the script, and is not automatically the running back.

### LAC@BUF

BUF -7 · total 50.5 · implied 21.75 / 28.75 · Outdoor; 67F, 16 mph NNE wind  ·  **weather MONITOR**

**LAC** — 26 DK rows still unresolved

observed W1–2 — carries: Omarion Hampton 35, Keaton Mitchell 9, Justin Herbert 8

observed W1–2 — targets: Quentin Johnston 11, Ladd McConkey 10, Tre' Harris 9, David Njoku 8, Oronde Gadsden II 4, Brenen Thompson 3

**BUF** — 21 DK rows still unresolved

reported available: DJ Moore ($5800); Keon Coleman ($4300)

observed W1–2 — carries: James Cook III 34, Josh Allen 20, Ray Davis 1, Frank Gore Jr. 1

observed W1–2 — targets: Dalton Kincaid 14, Khalil Shakir 12, DJ Moore 8, Keon Coleman 8, James Cook III 7, Dawson Knox 3

**Remaining uncertainty**
- LAC: 26 DK rows still UNKNOWN_NOT_RELAYED
- BUF: 21 DK rows still UNKNOWN_NOT_RELAYED
- routes and route participation UNKNOWN_SOURCE_UNAVAILABLE for every player in this game

**Correlation mechanisms** (mechanisms only — no recommendation, and no joint distribution held to weigh them)
- *LAC* — LAC pass volume links its quarterback to ['Quentin Johnston', 'Ladd McConkey', "Tre' Harris"] through shared team dropbacks. They also compete for the same targets and the same touchdowns, so the link is positive on volume and negative on allocation at the same time.
- *LAC* — LAC quarterback and ['Omarion Hampton', 'Keaton Mitchell'] share goal-line and short-yardage carries, so their scoring paths overlap rather than simply add.
- *LAC* — Omarion Hampton and the LAC DST both express the same branch -- LAC leads, BUF throws, pressure and turnovers rise, carries follow. That link is only real where the back's opportunity is rushing-led rather than receiving-led.
- *LAC* — a BUF player supports a LAC stack only in the branch where BUF scores enough to keep LAC throwing. Which BUF player depends on the script, and is not automatically the running back.
- *BUF* — BUF pass volume links its quarterback to ['Dalton Kincaid', 'Khalil Shakir', 'DJ Moore'] through shared team dropbacks. They also compete for the same targets and the same touchdowns, so the link is positive on volume and negative on allocation at the same time.
- *BUF* — BUF quarterback and ['James Cook III', 'Josh Allen'] share goal-line and short-yardage carries, so their scoring paths overlap rather than simply add.
- *BUF* — James Cook III and the BUF DST both express the same branch -- BUF leads, LAC throws, pressure and turnovers rise, carries follow. That link is only real where the back's opportunity is rushing-led rather than receiving-led.
- *BUF* — a LAC player supports a BUF stack only in the branch where LAC scores enough to keep BUF throwing. Which LAC player depends on the script, and is not automatically the running back.

### NE@JAX

JAX -3 · total 46.0 · implied 21.5 / 24.5 · Outdoor; 83F, light wind

**NE** — 25 DK rows still unresolved

| reported OUT | pos | $ | tier |
|---|---|--:|---|
| Eli Raridon | TE | 2900 | AGGREGATOR_REPORTED |

observed W1–2 — carries: Rhamondre Stevenson 24, TreVeyon Henderson 16, Drake Maye 11, Corey Kiner 8

observed W1–2 — targets: DeMario Douglas 9, Rhamondre Stevenson 8, Hunter Henry 8, Romeo Doubs 7, Mack Hollins 7, A.J. Brown 4

*NE:Eli Raridon* vacates 49 snaps · 0 car · 2 tgt · 1 rz · 1 gl · routes UNKNOWN → ranked Hunter Henry, Cameron Latu, Julian Hill; inheritance `UNRESOLVED_DISTRIBUTION`
  newly relevant: Cameron Latu, Julian Hill

**JAX** — 25 DK rows still unresolved

observed W1–2 — carries: Bhayshul Tuten 28, Chris Rodriguez Jr. 12, Ameer Abdullah 7, Trevor Lawrence 4, Nick Mullens 3

observed W1–2 — targets: Parker Washington 18, Brian Thomas Jr. 11, Brenton Strange 5, Bhayshul Tuten 3, Jakobi Meyers 3, Ameer Abdullah 2

**Remaining uncertainty**
- NE: 25 DK rows still UNKNOWN_NOT_RELAYED
- NE:Eli Raridon: inheritance UNRESOLVED_DISTRIBUTION across 4 same-group candidates
- JAX: 25 DK rows still UNKNOWN_NOT_RELAYED
- routes and route participation UNKNOWN_SOURCE_UNAVAILABLE for every player in this game

**Correlation mechanisms** (mechanisms only — no recommendation, and no joint distribution held to weigh them)
- *NE* — NE pass volume links its quarterback to ['DeMario Douglas', 'Rhamondre Stevenson', 'Hunter Henry'] through shared team dropbacks. They also compete for the same targets and the same touchdowns, so the link is positive on volume and negative on allocation at the same time.
- *NE* — NE quarterback and ['Rhamondre Stevenson', 'TreVeyon Henderson'] share goal-line and short-yardage carries, so their scoring paths overlap rather than simply add.
- *NE* — Rhamondre Stevenson and the NE DST both express the same branch -- NE leads, JAX throws, pressure and turnovers rise, carries follow. That link is only real where the back's opportunity is rushing-led rather than receiving-led.
- *NE* — a JAX player supports a NE stack only in the branch where JAX scores enough to keep NE throwing. Which JAX player depends on the script, and is not automatically the running back.
- *JAX* — JAX pass volume links its quarterback to ['Parker Washington', 'Brian Thomas Jr.', 'Brenton Strange'] through shared team dropbacks. They also compete for the same targets and the same touchdowns, so the link is positive on volume and negative on allocation at the same time.
- *JAX* — JAX quarterback and ['Bhayshul Tuten', 'Chris Rodriguez Jr.'] share goal-line and short-yardage carries, so their scoring paths overlap rather than simply add.
- *JAX* — Bhayshul Tuten and the JAX DST both express the same branch -- JAX leads, NE throws, pressure and turnovers rise, carries follow. That link is only real where the back's opportunity is rushing-led rather than receiving-led.
- *JAX* — a NE player supports a JAX stack only in the branch where NE scores enough to keep JAX throwing. Which NE player depends on the script, and is not automatically the running back.

### NYJ@DET

DET -6.5 · total 48.5 · implied 21.0 / 27.5 · Dome

**NYJ** — 25 DK rows still unresolved

| reported OUT | pos | $ | tier |
|---|---|--:|---|
| Adonai Mitchell | WR | 4300 | AGGREGATOR_REPORTED |
| Mason Taylor | TE | 2500 | OFFICIAL_TEAM_RELEASE_CITED |

observed W1–2 — carries: Breece Hall 38, Braelon Allen 15, Geno Smith 11

observed W1–2 — targets: Adonai Mitchell 15, Garrett Wilson 14, Breece Hall 7, Isaiah Williams 7, Kenyon Sadiq 6, Mason Taylor 3

*NYJ:Adonai Mitchell* vacates 107 snaps · 0 car · 15 tgt · 1 rz · 0 gl · routes UNKNOWN → ranked Garrett Wilson, Isaiah Williams, Omar Cooper Jr.; inheritance `UNRESOLVED_DISTRIBUTION`
  newly relevant: Omar Cooper Jr., Malik McClain

*NYJ:Mason Taylor* vacates 78 snaps · 0 car · 3 tgt · 0 rz · 0 gl · routes UNKNOWN → ranked Kenyon Sadiq, Jeremy Ruckert, Jelani Woods; inheritance `UNRESOLVED_DISTRIBUTION`

**DET** — 22 DK rows still unresolved

observed W1–2 — carries: Jahmyr Gibbs 45, Jared Goff 5, Sione Vaki 3

observed W1–2 — targets: Amon-Ra St. Brown 27, Sam LaPorta 15, Jahmyr Gibbs 13, Jameson Williams 13, Isaac TeSlaa 6, Sione Vaki 2

**Remaining uncertainty**
- NYJ: 25 DK rows still UNKNOWN_NOT_RELAYED
- NYJ:Adonai Mitchell: inheritance UNRESOLVED_DISTRIBUTION across 4 same-group candidates
- NYJ:Mason Taylor: inheritance UNRESOLVED_DISTRIBUTION across 4 same-group candidates
- DET: 22 DK rows still UNKNOWN_NOT_RELAYED
- routes and route participation UNKNOWN_SOURCE_UNAVAILABLE for every player in this game

**Correlation mechanisms** (mechanisms only — no recommendation, and no joint distribution held to weigh them)
- *NYJ* — NYJ pass volume links its quarterback to ['Garrett Wilson', 'Breece Hall', 'Isaiah Williams'] through shared team dropbacks. They also compete for the same targets and the same touchdowns, so the link is positive on volume and negative on allocation at the same time.
- *NYJ* — NYJ quarterback and ['Breece Hall', 'Braelon Allen'] share goal-line and short-yardage carries, so their scoring paths overlap rather than simply add.
- *NYJ* — Breece Hall and the NYJ DST both express the same branch -- NYJ leads, DET throws, pressure and turnovers rise, carries follow. That link is only real where the back's opportunity is rushing-led rather than receiving-led.
- *NYJ* — a DET player supports a NYJ stack only in the branch where DET scores enough to keep NYJ throwing. Which DET player depends on the script, and is not automatically the running back.
- *DET* — DET pass volume links its quarterback to ['Amon-Ra St. Brown', 'Sam LaPorta', 'Jahmyr Gibbs'] through shared team dropbacks. They also compete for the same targets and the same touchdowns, so the link is positive on volume and negative on allocation at the same time.
- *DET* — DET quarterback and ['Jahmyr Gibbs', 'Jared Goff'] share goal-line and short-yardage carries, so their scoring paths overlap rather than simply add.
- *DET* — Jahmyr Gibbs and the DET DST both express the same branch -- DET leads, NYJ throws, pressure and turnovers rise, carries follow. That link is only real where the back's opportunity is rushing-led rather than receiving-led.
- *DET* — a NYJ player supports a DET stack only in the branch where NYJ scores enough to keep DET throwing. Which NYJ player depends on the script, and is not automatically the running back.

### SEA@WAS

SEA -8.5 · total 40.5 · implied 24.5 / 16.0 · Outdoor; 54% rain, 61F, 16 mph NW wind  ·  **weather MATERIAL**

**SEA** — 25 DK rows still unresolved

reported available: Sam Darnold ($5400)

observed W1–2 — carries: Jadarian Price 23, Emanuel Wilson 23, George Holani 12, Drew Lock 2

observed W1–2 — targets: Jaxon Smith-Njigba 22, Rashid Shaheed 9, Cooper Kupp 5, Jadarian Price 4, AJ Barner 3, George Holani 2

**WAS** — 25 DK rows still unresolved

| reported OUT | pos | $ | tier |
|---|---|--:|---|
| Jayden Daniels | QB | 6000 | AGGREGATOR_REPORTED |
| Chig Okonkwo | TE | 3600 | AGGREGATOR_REPORTED |

observed W1–2 — carries: Jacory Croskey-Merritt 28, Rachaad White 14, Jayden Daniels 12, Kaytron Allen 9, Marcus Mariota 1

observed W1–2 — targets: Stefon Diggs 15, Terry McLaurin 13, Rachaad White 8, Dyami Brown 8, Antonio Williams 7, John Bates 4

*WAS:Chig Okonkwo* vacates 39 snaps · 0 car · 3 tgt · 0 rz · 0 gl · routes UNKNOWN → ranked Ben Sinnott, John Bates, Colson Yankoff; inheritance `UNRESOLVED_DISTRIBUTION`
  newly relevant: Colson Yankoff

*WAS:Jayden Daniels* vacates 109 snaps · 12 car · 0 tgt · 4 rz · 0 gl · routes UNKNOWN → ranked Marcus Mariota, Athan Kaliakmanis, Sam Hartman; inheritance `UNRESOLVED_DISTRIBUTION`
  newly relevant: Athan Kaliakmanis, Sam Hartman

**Remaining uncertainty**
- SEA: 25 DK rows still UNKNOWN_NOT_RELAYED
- WAS: 25 DK rows still UNKNOWN_NOT_RELAYED
- WAS:Chig Okonkwo: inheritance UNRESOLVED_DISTRIBUTION across 4 same-group candidates
- WAS:Jayden Daniels: inheritance UNRESOLVED_DISTRIBUTION across 3 same-group candidates
- routes and route participation UNKNOWN_SOURCE_UNAVAILABLE for every player in this game
- weather MATERIAL: 54% precipitation, 16 mph, source confidence MEDIUM

**Correlation mechanisms** (mechanisms only — no recommendation, and no joint distribution held to weigh them)
- *SEA* — SEA pass volume links its quarterback to ['Jaxon Smith-Njigba', 'Rashid Shaheed', 'Cooper Kupp'] through shared team dropbacks. They also compete for the same targets and the same touchdowns, so the link is positive on volume and negative on allocation at the same time.
- *SEA* — SEA quarterback and ['Jadarian Price', 'Emanuel Wilson'] share goal-line and short-yardage carries, so their scoring paths overlap rather than simply add.
- *SEA* — Jadarian Price and the SEA DST both express the same branch -- SEA leads, WAS throws, pressure and turnovers rise, carries follow. That link is only real where the back's opportunity is rushing-led rather than receiving-led.
- *SEA* — a WAS player supports a SEA stack only in the branch where WAS scores enough to keep SEA throwing. Which WAS player depends on the script, and is not automatically the running back.
- *WAS* — WAS pass volume links its quarterback to ['Stefon Diggs', 'Terry McLaurin', 'Rachaad White'] through shared team dropbacks. They also compete for the same targets and the same touchdowns, so the link is positive on volume and negative on allocation at the same time.
- *WAS* — WAS quarterback and ['Jacory Croskey-Merritt', 'Rachaad White'] share goal-line and short-yardage carries, so their scoring paths overlap rather than simply add.
- *WAS* — Jacory Croskey-Merritt and the WAS DST both express the same branch -- WAS leads, SEA throws, pressure and turnovers rise, carries follow. That link is only real where the back's opportunity is rushing-led rather than receiving-led.
- *WAS* — a SEA player supports a WAS stack only in the branch where SEA scores enough to keep WAS throwing. Which SEA player depends on the script, and is not automatically the running back.

### TEN@NYG

NYG -2.5 · total 37.5 · implied 17.5 / 20.0 · Outdoor; 53% rain, 64F, 17 mph NE wind  ·  **weather MATERIAL**

**TEN** — 23 DK rows still unresolved

reported available: Tyjae Spears ($4900)

observed W1–2 — carries: Tony Pollard 21, Tyjae Spears 10, Cam Ward 8

observed W1–2 — targets: Carnell Tate 11, Wan'Dale Robinson 7, Gunnar Helm 7, Tyjae Spears 6, Elic Ayomanor 6, Tony Pollard 3

**NYG** — 25 DK rows still unresolved

| reported OUT | pos | $ | tier |
|---|---|--:|---|
| Devin Singletary | RB | 4200 | AGGREGATOR_REPORTED |

observed W1–2 — carries: Cam Skattebo 30, Jaxson Dart 11, Devin Singletary 9, Najee Harris 4, Jameis Winston 2

observed W1–2 — targets: Isaiah Likely 18, Malik Nabers 13, Malachi Fields 10, Devin Singletary 5, Darnell Mooney 5, Theo Johnson 5

*NYG:Devin Singletary* vacates 40 snaps · 9 car · 5 tgt · 3 rz · 0 gl · routes UNKNOWN → ranked Cam Skattebo, Patrick Ricard, Najee Harris; inheritance `UNRESOLVED_DISTRIBUTION`
  newly relevant: Najee Harris

**Remaining uncertainty**
- TEN: 23 DK rows still UNKNOWN_NOT_RELAYED
- NYG: 25 DK rows still UNKNOWN_NOT_RELAYED
- NYG:Devin Singletary: inheritance UNRESOLVED_DISTRIBUTION across 4 same-group candidates
- routes and route participation UNKNOWN_SOURCE_UNAVAILABLE for every player in this game
- weather MATERIAL: 53% precipitation, 17 mph, source confidence MEDIUM

**Correlation mechanisms** (mechanisms only — no recommendation, and no joint distribution held to weigh them)
- *TEN* — TEN pass volume links its quarterback to ['Carnell Tate', "Wan'Dale Robinson", 'Gunnar Helm'] through shared team dropbacks. They also compete for the same targets and the same touchdowns, so the link is positive on volume and negative on allocation at the same time.
- *TEN* — TEN quarterback and ['Tony Pollard', 'Tyjae Spears'] share goal-line and short-yardage carries, so their scoring paths overlap rather than simply add.
- *TEN* — Tony Pollard and the TEN DST both express the same branch -- TEN leads, NYG throws, pressure and turnovers rise, carries follow. That link is only real where the back's opportunity is rushing-led rather than receiving-led.
- *TEN* — a NYG player supports a TEN stack only in the branch where NYG scores enough to keep TEN throwing. Which NYG player depends on the script, and is not automatically the running back.
- *NYG* — NYG pass volume links its quarterback to ['Isaiah Likely', 'Malik Nabers', 'Malachi Fields'] through shared team dropbacks. They also compete for the same targets and the same touchdowns, so the link is positive on volume and negative on allocation at the same time.
- *NYG* — NYG quarterback and ['Cam Skattebo', 'Jaxson Dart'] share goal-line and short-yardage carries, so their scoring paths overlap rather than simply add.
- *NYG* — Cam Skattebo and the NYG DST both express the same branch -- NYG leads, TEN throws, pressure and turnovers rise, carries follow. That link is only real where the back's opportunity is rushing-led rather than receiving-led.
- *NYG* — a TEN player supports a NYG stack only in the branch where TEN scores enough to keep NYG throwing. Which TEN player depends on the script, and is not automatically the running back.

## What is still blocked

**No projection board exists.** `STAGE_DECLARED_UNIMPLEMENTED`. feature_build is DEFERRED and does not halt the pipeline; player_draws then FAILs DECLARED_DRAW_ARTIFACT_INCOMPLETE because the receiving and rushing layers are CONTRACT_DECLARED_LAYER_ABSENT, which traces to participation_prior BLOCKED PARTICIPATION_HISTORY_STALE, which traces to pbp_participation_2026 404. No projection is produced here and none is simulated.

So the 48-entry portfolio stops here, at the scientific stop condition the instructions themselves set: a defensible player-outcome model, a joint game simulator, an ownership model and a contest-field model are all unavailable, and FantasyCruncher is not a substitute for any of them.

## Preserved corrections

historical role labels are stale for a number of players who were materially active in weeks 1-2. 19 of 53 FEATURES_NO_PRIOR_HISTORY players cleared the material-activity thresholds, so their historical "fringe" classification is not valid for their current role.  Named examples: Carnell Tate, Denzel Boston, Caleb Douglas, Malachi Fields, KC Concepcion Jr., Jadarian Price. current opportunity is described from observed 2026 usage, never from a historical role label. Every row carries historical_role_class_valid_for_current_role so the two cannot be confused. Q9 itself is untouched by this artifact.

## Identity

- **IDC-01** — CLOSED_BY_MEASUREMENT. NOT A CONFLICT. The authoritative DK contest file carries the same clubs and the same salaries -- Kenneth Walker III KC 7400, David Montgomery HOU 6000, Michael Pittman Jr. PIT 4700, Carnell Tate TEN 5000, Jadarian Price SEA 5300, Malachi Fields NYG 4400. Three sources agree; there is nothing to reconcile.
- **IDC-02** — OPEN_RECORDED_NOT_RESOLVED. NO SUCH PLAYER in the DK 457. The universe carries Malik McClain, NYJ WR, 3000. A first-name substitution is the most likely reading but it is not established, so the name is NOT silently rewritten.
- **IDC-03** — CLOSED_BY_MEASUREMENT. none of these is in the DK 457. They are real football facts with no DK player row, so they enter the team-efficiency and DST layers only.

