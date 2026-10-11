# Week 5 Early Only: 16-club availability board (2026-10-11, assembled 16:00–16:10Z)

How this was gathered:
- RotoWire (`lineups.php`, `inactives.php`) does not resolve from this executor (DNS ENOTFOUND).
- The repository's official-inactives capture returned SOURCE_HAS_NO_ROWS_YET at 14:56Z and 15:33Z.
- So this board comes from web search of team sites and of outlets relaying the club lists.

Evidence tiers:
- OFFICIAL_RELEASE: a team site.
- AGGREGATOR: an outlet relaying the club list.

Nothing here is an official capture. The `inactives_coverage` gate stays BLOCKED by design.

Only offensive skill players and QBs in the DraftKings pool were applied. Defensive and OL inactives are listed for completeness only.

| Club | Inactive (DK-relevant in bold) | Questionable → status | Starting QB | Sources (tier) |
|---|---|---|---|---|
| CHI | **QB Caleb Williams**, **RB Kyle Monangai**, OT Trapilo, LB Elliott, DE Kromah, DT Loving | Williams inactive | **Tyson Bagent** | Shaw Local, NBC Sports, Windy City Gridiron, Yahoo live (AGG) |
| GB | OL Monk, G Banks, OL Jennings, DT Campbell | Bullard (S) active | Jordan Love | packers.com (OFFICIAL) |
| CIN | S Dugger, C Lew, OT Hinton, **TE Jack Endries**, **WR Colbie Young**, DT Robinson | **Chase ACTIVE, Higgins ACTIVE** | Joe Burrow | Yahoo, The Phinsider, Schefter on X (AGG) |
| MIA | **WR Caleb Douglas**, EDGE Beal, CB Taylor, **TE Justin Joly**, **RB Kaytron Allen**, G Campbell, OT Godrick | Jaylen Wright active (not listed) | Malik Willis | SI All Dolphins, Yahoo (AGG) |
| CLE | **WR Tylan Wallace**, **TE Carsen Ryan**, DT Hall, G Jenkins, DT Graham, **QB Taylen Green** (3rd), G Brailsford | — | Deshaun Watson | Yahoo, NBC Sports (AGG) |
| NYJ | **RB Breece Hall**, LB Mauigoa, OL Parham, **WR Adonai Mitchell**, EDGE Lynn, CB Wright | Tim Patrick active (roster capture still RES, so upload-blocked) | Geno Smith | The Jet Press, Yahoo (AGG) |
| HOU | CB Wright, DE Braswell, DE Harsh, LB Fisher, G Nwaiwu, T Thomas, **TE Marlin Klein** | — | C.J. Stroud | Athlon (AGG) |
| TEN | **RB Nick Singleton**, **RB Michael Carter**, S Hooker, CB Jones, T Crenshaw-Dickson, **TE David Martin-Robinson**, DT Marshall | **Carnell Tate ACTIVE** | Cam Ward | Athlon, NBC Sports (AGG) |
| IND | LB Carlies, **WR Ashton Dulin**, **WR Darius Slayton**, **QB Riley Leonard** (3rd), G Tucker | **Keenan Allen ACTIVE** | Daniel Jones | colts.com (OFFICIAL) |
| PIT | CB Dean, **RB Rico Dowdle**, **QB Will Howard**, **QB Drew Allar**, **RB Eli Heidenreich**, DT Jobity, CB Smith | Dowdle inactive; Pittman on IR | Aaron Rodgers | Steelers Depot, CBS (AGG) |
| LV | **WR Jalen Nailor**, **QB Aidan O'Connell** (3rd), S McCollum, **RB Roman Hemby**, S Johnson, OL Zuhn, DT Pegues | **Jeanty ACTIVE**: workload unverified, missed Friday practice | Kirk Cousins | Yahoo, NBC Sports, Athlon (AGG; Raiders list single-source) |
| NE | CB Gonzalez, CB Davis, CB Canada, CB Prunty, OT Crownover, **QB Behren Morton** (3rd) | **Stevenson ACTIVE** | Drake Maye | patriots.com (OFFICIAL) |
| MIN | **WR Jordan Addison**, **WR Odell Beckham Jr.**, OT Darrisaw (**list PARTIAL**) | **Jefferson ACTIVE**; Yurosek unresolved | Kyler Murray | DraftSharks, Star Tribune, Yahoo, NBC (AGG) |
| NO | EDGE Jennings, S Reid, LB Elliss, OL Wright, DL Broughton, DL Shepherd (Zach Wilson emergency 3rd QB) | **Kamara ACTIVE**; Barion Brown active | Tyler Shough | NBC Sports (AGG) |
| NYG | OL Davis, **QB Jake Haener** (3rd), DL Jamison-Travis, S Pinnock, CB Reed, **RB Devin Singletary** | — | Jameis Winston (McCarthy QB2) | giants.com (OFFICIAL), SI |
| WAS | **WR Stefon Diggs**, **QB Marcus Mariota**, S Owens, S Cross, S Butler, OG Togiai, DE Omenihu | **McLaurin ACTIVE: "likely not a full go", limited snaps (Garafolo). The restriction is NOT MODELLED.** | Jayden Daniels | NBC Sports, SI (AGG) |

Packet: `evidence_packets/2026W5_SUNDAY_CUMULATIVE_1610Z.json`, 34 items.

Workload restrictions the engine cannot apply: McLaurin (limited), Jeanty (unclear), Jefferson (ankle; none reported). They are flagged in the release report; no ad hoc projection edits were made.
