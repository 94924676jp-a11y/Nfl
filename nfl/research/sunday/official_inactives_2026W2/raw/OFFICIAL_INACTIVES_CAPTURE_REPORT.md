# NFL Week 2 (2026-09-20) 1 PM ET slate: official game-day inactives evidence package

Scope: eight DraftKings Early Only games. Content: official game-day INACTIVE declarations only. No projections, lineups, or prop recommendations. ACTIVE is never inferred from omission; where a team site explicitly states a player is active, the statement is preserved in `role_and_roster_evidence.csv` with its URL.

Capture window (UTC): start 2026-09-20T16:05Z approx; NFL.com article retrieved 2026-09-20T16:10:52.440815Z; team pages retrieved 2026-09-20T16:14:07.559867Z to 2026-09-20T16:14:07.602938Z. Kickoff 17:00Z. All listed inactives were published before kickoff.

## Governing sources

1. Official NFL page (league): https://www.nfl.com/news/nfl-week-2-inactives-players-ruled-out-sunday-14-games-2026 (datePublished 2026-09-20T15:40:23.31Z, dateModified 2026-09-20T15:54:29.746Z, raw HTML sha256 57822f63314c176d897d4ec087eb384764c56a2afe3532abfb3a31934a39507d, 875489 bytes). Reached via the link on https://www.nfl.com/inactives/ (raw saved). NFL.com listed the CIN@HOU venue as "Reliant Stadium (Houston)" in its article header; preserved as written, not corrected.
2. Official team website inactives posts for 15 of 16 clubs (raw HTML + extracted body text + JSON-LD datePublished/dateModified).
3. Chicago Bears: NO inactives post found on chicagobears.com (news index and site search checked; game-center page contains no inactives markup). Bears list is governed by the NFL.com official page and corroborated by the opponent official site (vikings.com, section "Bears Inactives"). Flag: CHI_TEAM_SITE_NOT_FOUND. No secondary media source was used.

## Cross-source result

98 declarations across 16 clubs. Every player on the NFL.com list appears on the corresponding team-official (or, for CHI, opponent-official) list and vice versa: 0 membership conflicts. 11 rows carry display-form flags (spelling, suffix, apostrophe encoding, jersey number) which are listed verbatim in the CSV `flags` column and below; none was reconciled by guess. Because the underlying player set is identical, these are labeled DISPLAY_NAME_VARIANT rather than SOURCE_CONFLICT; ingestion should treat both strings as the displayed forms and resolve identity downstream.

| club | NFL.com displayed | team-official displayed | opponent-official displayed | flag |
|---|---|---|---|---|
| CAR | Bobby Brown | Bobby Brown | n/a | TEAM_BODY_TEXT_LONG_FORM(Bobby Brown III);NFL_INJURY_REPORT_LONG_FORM(Bobby Brown III) |
| CAR | Pat Jones | Pat Jones | n/a | TEAM_BODY_TEXT_LONG_FORM(Patrick Jones II);NFL_INJURY_REPORT_LONG_FORM(Patrick Jones II) |
| ATL | Billy Bowman Jr. | Billy Bowman Jr. | CB Billy Bowman | OPPONENT_SITE_NAME_VARIANT |
| ATL | Malcolm DeWalt IV | Malcolm DeWalt IV | CB Malcom Dewalt IV | OPPONENT_SITE_NAME_VARIANT |
| BAL | Andrew Voorhees | Andrew Vorhees | No. 72 Guard Andrew Vorhees | NAME_FORM_DIFFERS;DISPLAY_NAME_VARIANT |
| NE | Carlton Davis | Carlton Davis III (neck) | No. 7 CB Carlton Davis | DISPLAY_NAME_VARIANT;OPPONENT_SITE_NAME_VARIANT |
| CLE | Toriano Pride Jr. | Toriano Pride Jr. | CB Toriano Pride | OPPONENT_SITE_NAME_VARIANT |
| TEN | Atonio Mafi | Atonio Mafi | G Antonio Mafi / 70 | OPPONENT_SITE_NAME_VARIANT |
| TEN | Brandon Crenshaw-Dickson | Brandon Crenshaw-Dickson | T Brandon Crenshaw-Dickson / 79 | OPPONENT_SITE_JERSEY_NUMBER_DIFFERS(78_vs_79) |
| TEN | Cor’Dale Flott | Cor'Dale Flott | CB Cor'Dale Flott / 18 | APOSTROPHE_ENCODING_DIFFERS |

## Per-game blocks

```
GAME: PHI @ TEN (2026-09-20 17:00Z, 1:00 PM ET)
OFFICIAL SOURCE: NFL.com official inactives article (league) + official team websites
SOURCE URL (league): https://www.nfl.com/news/nfl-week-2-inactives-players-ruled-out-sunday-14-games-2026
PUBLICATION TIME (league): datePublished 2026-09-20T15:40:23.31Z; dateModified 2026-09-20T15:54:29.746Z
RETRIEVAL TIME UTC (league): 2026-09-20T16:10:52.440815Z
SOURCE URL (PHI TEAM_OFFICIAL_SITE): https://www.philadelphiaeagles.com/news/eagles-at-titans-inactives-week-2-2026-nfl-regular-season
PUBLICATION TIME (PHI): datePublished 2026-09-20T15:30:00Z; dateModified 2026-09-20T15:59:55.109Z
RETRIEVAL TIME UTC (PHI): 2026-09-20T16:14:07.599072Z
SOURCE URL (TEN TEAM_OFFICIAL_SITE): https://www.tennesseetitans.com/news/game-inactives-week-2-titans-vs-eagles
PUBLICATION TIME (TEN): datePublished 2026-09-20T15:30:09.048Z; dateModified 2026-09-20T15:33:24.513Z
RETRIEVAL TIME UTC (TEN): 2026-09-20T16:14:07.602938Z
TEAM 1 INACTIVES (PHI, 5 players; NFL.com form | team-source form):
  QB Cole Payton | QB | 18 Cole Payton
  WR Elijah Moore | WR | 19 Elijah Moore
  OLB Jonathan Greenard | OLB | 52 Jonathan Greenard
  G Micah Morris | G | 76 Micah Morris
  QB Tanner McKee [emergency third QB] | QB | 16 Tanner McKee (3rd QB)
TEAM 2 INACTIVES (TEN, 6 players; NFL.com form | team-source form):
  G Atonio Mafi | G (70) Atonio Mafi | FLAG: OPPONENT_SITE_NAME_VARIANT
  OT Brandon Crenshaw-Dickson | T (78) Brandon Crenshaw-Dickson | FLAG: OPPONENT_SITE_JERSEY_NUMBER_DIFFERS(78_vs_79)
  CB Cor’Dale Flott | CB (18) Cor'Dale Flott | FLAG: APOSTROPHE_ENCODING_DIFFERS
  DT Jackie Marshall | DT (96) Jackie Marshall
  LB James Williams Sr. | LB (52) James Williams Sr.
  TE Kylen Granson | TE (86) Kylen Granson
RAW EVIDENCE:
  raw/nflart_https_www_nfl_com_news_nfl_week_2_inactives_players_ruled_out_sunday_14_games_2026.html
  raw/team_https_www_philadelphiaeagles_com_news_eagles_at_titans_inactives_week_2_2026_nfl_regular_s.html  (+ .body.txt extracted text)
  raw/team_https_www_tennesseetitans_com_news_game_inactives_week_2_titans_vs_eagles.html  (+ .body.txt extracted text)
HASH (sha256 of raw HTML):
  57822f63314c176d897d4ec087eb384764c56a2afe3532abfb3a31934a39507d  raw/nflart_https_www_nfl_com_news_nfl_week_2_inactives_players_ruled_out_sunday_14_games_2026.html
  aac906b1b560494936e4db176e645758a91393d32b75ef75a5551f6b9766b917  raw/team_https_www_philadelphiaeagles_com_news_eagles_at_titans_inactives_week_2_2026_nfl_regular_s.html
  a14de8982c3857accb84b4f1391aa9128beb62140bde9331d0f12fba29997a2a  raw/team_https_www_tennesseetitans_com_news_game_inactives_week_2_titans_vs_eagles.html
STATUS: COMPLETE_OFFICIAL_INACTIVES
```

```
GAME: PIT @ NE (2026-09-20 17:00Z, 1:00 PM ET)
OFFICIAL SOURCE: NFL.com official inactives article (league) + official team websites
SOURCE URL (league): https://www.nfl.com/news/nfl-week-2-inactives-players-ruled-out-sunday-14-games-2026
PUBLICATION TIME (league): datePublished 2026-09-20T15:40:23.31Z; dateModified 2026-09-20T15:54:29.746Z
RETRIEVAL TIME UTC (league): 2026-09-20T16:10:52.440815Z
SOURCE URL (PIT TEAM_OFFICIAL_SITE): https://www.steelers.com/news/steelers-inactives-for-week-2-vs-patriots-x2429
PUBLICATION TIME (PIT): datePublished 2026-09-20T15:30:00Z; dateModified 2026-09-20T15:35:50.209Z
RETRIEVAL TIME UTC (PIT): 2026-09-20T16:14:07.586206Z
SOURCE URL (NE TEAM_OFFICIAL_SITE): https://www.patriots.com/news/inactives-analysis-rb-treveyon-henderson-to-make-season-debut-wr-efton-chism-iii-active-vs-steelers
PUBLICATION TIME (NE): datePublished 2026-09-20T15:32:27.557Z; dateModified 2026-09-20T15:37:55.9Z
RETRIEVAL TIME UTC (NE): 2026-09-20T16:14:07.587526Z
TEAM 1 INACTIVES (PIT, 7 players; NFL.com form | team-source form):
  QB Drew Allar | QB (No. 16) Drew Allar
  DE Gabriel Rubio | DE (No. 96) Gabriel Rubio
  G Gennings Dunker | G (No. 73) Gennings Dunker
  CB Joey Porter Jr. | CB (No. 24) Joey Porter Jr.
  DL Kevin Jobity Jr. | DL (No. 92) Kevin Jobity Jr.
  WR Michael Pittman Jr. | WR (No. 11) Michael Pittman Jr.
  QB Will Howard [emergency third QB] | QB (No. 18) Will Howard (3rd QB)
TEAM 2 INACTIVES (NE, 6 players; NFL.com form | team-source form):
  QB Behren Morton [emergency third QB] | QB Behren Morton (emergency third quarterback)
  CB Carlton Davis | CB Carlton Davis III (neck) | FLAG: DISPLAY_NAME_VARIANT;OPPONENT_SITE_NAME_VARIANT
  OT Dametrious Crownover | OT Dametrious Crownover (knee)
  DT Leonard Taylor | DT Leonard Taylor
  TE Tanner Arkin | TE Tanner Arkin
  OT Walter Rouse | OT Walter Rouse
RAW EVIDENCE:
  raw/nflart_https_www_nfl_com_news_nfl_week_2_inactives_players_ruled_out_sunday_14_games_2026.html
  raw/team_https_www_steelers_com_news_steelers_inactives_for_week_2_vs_patriots_x2429.html  (+ .body.txt extracted text)
  raw/team_https_www_patriots_com_news_inactives_analysis_rb_treveyon_henderson_to_make_season_debut_.html  (+ .body.txt extracted text)
HASH (sha256 of raw HTML):
  57822f63314c176d897d4ec087eb384764c56a2afe3532abfb3a31934a39507d  raw/nflart_https_www_nfl_com_news_nfl_week_2_inactives_players_ruled_out_sunday_14_games_2026.html
  97f83fa169f5c705c64b3c0c4c96ba09a1f9d9ebe453bd50be500eb91b43bf26  raw/team_https_www_steelers_com_news_steelers_inactives_for_week_2_vs_patriots_x2429.html
  5edb89211c378cb332a00529357ff5c8df86478ba6396f6844cba7a74fd8c130  raw/team_https_www_patriots_com_news_inactives_analysis_rb_treveyon_henderson_to_make_season_debut_.html
STATUS: COMPLETE_OFFICIAL_INACTIVES
```

```
GAME: MIN @ CHI (2026-09-20 17:00Z, 1:00 PM ET)
OFFICIAL SOURCE: NFL.com official inactives article (league) + official team websites
SOURCE URL (league): https://www.nfl.com/news/nfl-week-2-inactives-players-ruled-out-sunday-14-games-2026
PUBLICATION TIME (league): datePublished 2026-09-20T15:40:23.31Z; dateModified 2026-09-20T15:54:29.746Z
RETRIEVAL TIME UTC (league): 2026-09-20T16:10:52.440815Z
SOURCE URL (MIN TEAM_OFFICIAL_SITE): https://www.vikings.com/news/inactives-bears-week-2-2026
PUBLICATION TIME (MIN): datePublished 2026-09-20T15:30:00Z; dateModified 2026-09-20T15:34:19.153Z
RETRIEVAL TIME UTC (MIN): 2026-09-20T16:14:07.574228Z
SOURCE URL (CHI OPPONENT_OFFICIAL_SITE): https://www.vikings.com/news/inactives-bears-week-2-2026
PUBLICATION TIME (CHI): datePublished 2026-09-20T15:30:00Z; dateModified 2026-09-20T15:34:19.153Z
RETRIEVAL TIME UTC (CHI): 2026-09-20T16:14:07.574228Z
TEAM 1 INACTIVES (MIN, 7 players; NFL.com form | team-source form):
  OT Caleb Tiernan | Tackle Caleb Tiernan
  DL Elijah Williams | Defensive lineman Elijah Williams
  S Jakobe Thomas | Safety Jakobe Thomas
  WR Jauan Jennings | Receiver Jauan Jennings
  QB Kyler Murray | Quarterback Kyler Murray
  C Nick Samac | Center Nick Samac
  CB Zemaiah Vaughn | Cornerback Zemaiah Vaughn
TEAM 2 INACTIVES (CHI, 5 players; NFL.com form | team-source form):
  QB Case Keenum [emergency third QB] | Quarterback Case Keenum (3rd QB)
  DL Jamree Kromah | Defensive lineman Jamree Kromah
  DL Jayden Loving | Defensive lineman Jayden Loving
  OL Jordan McFadden | Offensive lineman Jordan McFadden
  OL Ozzy Trapilo | Offensive lineman Ozzy Trapilo
RAW EVIDENCE:
  raw/nflart_https_www_nfl_com_news_nfl_week_2_inactives_players_ruled_out_sunday_14_games_2026.html
  raw/team_https_www_vikings_com_news_inactives_bears_week_2_2026.html  (+ .body.txt extracted text)
  raw/team_https_www_vikings_com_news_inactives_bears_week_2_2026.html  (+ .body.txt extracted text)
HASH (sha256 of raw HTML):
  57822f63314c176d897d4ec087eb384764c56a2afe3532abfb3a31934a39507d  raw/nflart_https_www_nfl_com_news_nfl_week_2_inactives_players_ruled_out_sunday_14_games_2026.html
  34fd39fa162a4ca187f5bf93e3f49b6b07effba90231534514f4e8fa78384597  raw/team_https_www_vikings_com_news_inactives_bears_week_2_2026.html
  34fd39fa162a4ca187f5bf93e3f49b6b07effba90231534514f4e8fa78384597  raw/team_https_www_vikings_com_news_inactives_bears_week_2_2026.html
STATUS: COMPLETE_OFFICIAL_INACTIVES (CHI list from NFL.com official page + vikings.com opponent-official cross-listing; chicagobears.com post NOT FOUND)
```

```
GAME: CAR @ ATL (2026-09-20 17:00Z, 1:00 PM ET)
OFFICIAL SOURCE: NFL.com official inactives article (league) + official team websites
SOURCE URL (league): https://www.nfl.com/news/nfl-week-2-inactives-players-ruled-out-sunday-14-games-2026
PUBLICATION TIME (league): datePublished 2026-09-20T15:40:23.31Z; dateModified 2026-09-20T15:54:29.746Z
RETRIEVAL TIME UTC (league): 2026-09-20T16:10:52.440815Z
SOURCE URL (CAR TEAM_OFFICIAL_SITE): https://www.panthers.com/news/week-2-inactives-at-atlanta-pat-jones-out-for-falcons-game-bobby-brown-panthers-falcons
PUBLICATION TIME (CAR): datePublished 2026-09-20T15:33:02.066Z; dateModified 2026-09-20T15:33:02.066Z
RETRIEVAL TIME UTC (CAR): 2026-09-20T16:14:07.559867Z
SOURCE URL (ATL TEAM_OFFICIAL_SITE): https://www.atlantafalcons.com/news/atlanta-falcons-week-2-inactives-vs-carolina-panthers
PUBLICATION TIME (ATL): datePublished 2026-09-20T15:28:34.761Z; dateModified 2026-09-20T15:28:34.761Z
RETRIEVAL TIME UTC (ATL): 2026-09-20T16:14:07.562401Z
TEAM 1 INACTIVES (CAR, 7 players; NFL.com form | team-source form):
  OT Albert Reese | OT Albert Reese
  DT Bobby Brown | DT Bobby Brown | FLAG: TEAM_BODY_TEXT_LONG_FORM(Bobby Brown III);NFL_INJURY_REPORT_LONG_FORM(Bobby Brown III)
  CB Chau Smith-Wade | CB Chau Smith-Wade
  QB Haynes King [emergency third QB] | QB Haynes King (emergency third)
  TE Ja'Tavion Sanders | TE Ja'Tavion Sanders
  OLB Pat Jones | OLB Pat Jones | FLAG: TEAM_BODY_TEXT_LONG_FORM(Patrick Jones II);NFL_INJURY_REPORT_LONG_FORM(Patrick Jones II)
  LB Tyrel Dodson | LB Tyrel Dodson
TEAM 2 INACTIVES (ATL, 5 players; NFL.com form | team-source form):
  DB Billy Bowman Jr. | DB Billy Bowman Jr. | FLAG: OPPONENT_SITE_NAME_VARIANT
  OL Ethan Onianwa | OL Ethan Onianwa
  DB Malcolm DeWalt IV | DB Malcolm DeWalt IV | FLAG: OPPONENT_SITE_NAME_VARIANT
  QB Michael Penix Jr. | QB Michael Penix Jr.
  QB Tua Tagovailoa | QB Tua Tagovailoa
RAW EVIDENCE:
  raw/nflart_https_www_nfl_com_news_nfl_week_2_inactives_players_ruled_out_sunday_14_games_2026.html
  raw/team_https_www_panthers_com_news_week_2_inactives_at_atlanta_pat_jones_out_for_falcons_game_bob.html  (+ .body.txt extracted text)
  raw/team_https_www_atlantafalcons_com_news_atlanta_falcons_week_2_inactives_vs_carolina_panthers.html  (+ .body.txt extracted text)
HASH (sha256 of raw HTML):
  57822f63314c176d897d4ec087eb384764c56a2afe3532abfb3a31934a39507d  raw/nflart_https_www_nfl_com_news_nfl_week_2_inactives_players_ruled_out_sunday_14_games_2026.html
  98e2120fc11bdf059f8298b56ea9363d564800cab45eea10a66b128e8c4a9894  raw/team_https_www_panthers_com_news_week_2_inactives_at_atlanta_pat_jones_out_for_falcons_game_bob.html
  07f4aec9abcf544d1964daf534c6f22575ac6230f53a15623748a16156f611f0  raw/team_https_www_atlantafalcons_com_news_atlanta_falcons_week_2_inactives_vs_carolina_panthers.html
STATUS: COMPLETE_OFFICIAL_INACTIVES
```

```
GAME: GB @ NYJ (2026-09-20 17:00Z, 1:00 PM ET)
OFFICIAL SOURCE: NFL.com official inactives article (league) + official team websites
SOURCE URL (league): https://www.nfl.com/news/nfl-week-2-inactives-players-ruled-out-sunday-14-games-2026
PUBLICATION TIME (league): datePublished 2026-09-20T15:40:23.31Z; dateModified 2026-09-20T15:54:29.746Z
RETRIEVAL TIME UTC (league): 2026-09-20T16:10:52.440815Z
SOURCE URL (GB TEAM_OFFICIAL_SITE): https://www.packers.com/news/packers-jets-week-2-inactives-sept-20-2026
PUBLICATION TIME (GB): datePublished 2026-09-20T15:30:00Z; dateModified 2026-09-20T15:38:26.914Z
RETRIEVAL TIME UTC (GB): 2026-09-20T16:14:07.589197Z
SOURCE URL (NYJ TEAM_OFFICIAL_SITE): https://www.newyorkjets.com/news/jets-vs-packers-game-inactives-09-20-2026
PUBLICATION TIME (NYJ): datePublished 2026-09-20T15:30:00Z; dateModified 2026-09-20T15:50:10.139Z
RETRIEVAL TIME UTC (NYJ): 2026-09-20T16:14:07.590172Z
TEAM 1 INACTIVES (GB, 5 players; NFL.com form | team-source form):
  CB Benjamin St-Juste | CB (21) Benjamin St-Juste
  DT Javon Hargrave | DT (98) Javon Hargrave
  OL John Williams | OL (73) John Williams
  OL Travis Glover | OL (79) Travis Glover
  DT Warren Brinson | DT (91) Warren Brinson
TEAM 2 INACTIVES (NYJ, 6 players; NFL.com form | team-source form):
  K Blake Grupe | K Blake Grupe
  CB D'Angelo Ponds | CB D'Angelo Ponds
  Edge Joseph Ossai | Edge Joseph Ossai
  RB Kene Nwangwu | RB Kene Nwangwu
  S Minkah Fitzpatrick | S Minkah Fitzpatrick
  LB Trevin Wallace | LB Trevin Wallace
RAW EVIDENCE:
  raw/nflart_https_www_nfl_com_news_nfl_week_2_inactives_players_ruled_out_sunday_14_games_2026.html
  raw/team_https_www_packers_com_news_packers_jets_week_2_inactives_sept_20_2026.html  (+ .body.txt extracted text)
  raw/team_https_www_newyorkjets_com_news_jets_vs_packers_game_inactives_09_20_2026.html  (+ .body.txt extracted text)
HASH (sha256 of raw HTML):
  57822f63314c176d897d4ec087eb384764c56a2afe3532abfb3a31934a39507d  raw/nflart_https_www_nfl_com_news_nfl_week_2_inactives_players_ruled_out_sunday_14_games_2026.html
  c1d59939bcfd8642b8f0e72f0ca9ecefa8db7ab5b623aa6f0a9b1353ae63bc36  raw/team_https_www_packers_com_news_packers_jets_week_2_inactives_sept_20_2026.html
  84fbe443ea4152e354d1ec415d830aaffe24c14bb59b05316f51e1c9271f13f7  raw/team_https_www_newyorkjets_com_news_jets_vs_packers_game_inactives_09_20_2026.html
STATUS: COMPLETE_OFFICIAL_INACTIVES
```

```
GAME: NO @ BAL (2026-09-20 17:00Z, 1:00 PM ET)
OFFICIAL SOURCE: NFL.com official inactives article (league) + official team websites
SOURCE URL (league): https://www.nfl.com/news/nfl-week-2-inactives-players-ruled-out-sunday-14-games-2026
PUBLICATION TIME (league): datePublished 2026-09-20T15:40:23.31Z; dateModified 2026-09-20T15:54:29.746Z
RETRIEVAL TIME UTC (league): 2026-09-20T16:10:52.440815Z
SOURCE URL (NO TEAM_OFFICIAL_SITE): https://www.neworleanssaints.com/news/new-orleans-saints-inactives-baltimore-ravens-2026-nfl-week-2-gameday
PUBLICATION TIME (NO): datePublished 2026-09-20T15:32:07.208Z; dateModified 2026-09-20T15:36:35.003Z
RETRIEVAL TIME UTC (NO): 2026-09-20T16:14:07.568350Z
SOURCE URL (BAL TEAM_OFFICIAL_SITE): https://www.baltimoreravens.com/news/ravens-inactives-saints-ronnie-stanley-carson-vinson
PUBLICATION TIME (BAL): datePublished 2026-09-20T15:42:20.655Z; dateModified 2026-09-20T15:42:20.655Z
RETRIEVAL TIME UTC (BAL): 2026-09-20T16:14:07.570693Z
TEAM 1 INACTIVES (NO, 7 players; NFL.com form | team-source form):
  DL Christen Miller | Defensive lineman (No. 52) Christen Miller
  CB Decamerion Richardson | Cornerback (No. 25) Decamerion Richardson
  LB Isaiah Stalbird | Linebacker (No. 44) Isaiah Stalbird
  DL John Ridgeway III | Defensive lineman (No. 95) John Ridgeway III
  RB Kendre Miller | Running back (No. 5) Kendre Miller
  OL Mason Murphy | Tackle (No. 74) Mason Murphy
  QB Zach Wilson [emergency third QB] | Quarterback (No. 11) Zach Wilson (designated third QB)
TEAM 2 INACTIVES (BAL, 6 players; NFL.com form | team-source form):
  G Andrew Voorhees | G Andrew Vorhees | FLAG: NAME_FORM_DIFFERS;DISPLAY_NAME_VARIANT
  OT Gerad Lichtenhan | T Gerad Lichtenhan
  QB Joe Fagnano [emergency third QB] | QB Joe Fagnano (3rd QB)
  DT Nnamdi Madubuike | DT Nnamdi Madubuike
  LB Teddye Buchanan | ILB Teddye Buchanan
  WR Zay Flowers | WR Zay Flowers
RAW EVIDENCE:
  raw/nflart_https_www_nfl_com_news_nfl_week_2_inactives_players_ruled_out_sunday_14_games_2026.html
  raw/team_https_www_neworleanssaints_com_news_new_orleans_saints_inactives_baltimore_ravens_2026_nfl.html  (+ .body.txt extracted text)
  raw/team_https_www_baltimoreravens_com_news_ravens_inactives_saints_ronnie_stanley_carson_vinson.html  (+ .body.txt extracted text)
HASH (sha256 of raw HTML):
  57822f63314c176d897d4ec087eb384764c56a2afe3532abfb3a31934a39507d  raw/nflart_https_www_nfl_com_news_nfl_week_2_inactives_players_ruled_out_sunday_14_games_2026.html
  6f6a8af9c77658aabc76323ff0f3a5a420bacc98c7fc5d86d86900f96d44b2af  raw/team_https_www_neworleanssaints_com_news_new_orleans_saints_inactives_baltimore_ravens_2026_nfl.html
  da1f2d57093247f89f599e3f38d9e5ec47a3911a2f101a6f90d4e5e82058f3e8  raw/team_https_www_baltimoreravens_com_news_ravens_inactives_saints_ronnie_stanley_carson_vinson.html
STATUS: COMPLETE_OFFICIAL_INACTIVES
```

```
GAME: CIN @ HOU (2026-09-20 17:00Z, 1:00 PM ET)
OFFICIAL SOURCE: NFL.com official inactives article (league) + official team websites
SOURCE URL (league): https://www.nfl.com/news/nfl-week-2-inactives-players-ruled-out-sunday-14-games-2026
PUBLICATION TIME (league): datePublished 2026-09-20T15:40:23.31Z; dateModified 2026-09-20T15:54:29.746Z
RETRIEVAL TIME UTC (league): 2026-09-20T16:10:52.440815Z
SOURCE URL (CIN TEAM_OFFICIAL_SITE): https://www.bengals.com/news/bengals-texans-inactives-week-2-2026
PUBLICATION TIME (CIN): datePublished 2026-09-20T15:30:23.604Z; dateModified 2026-09-20T15:32:56.871Z
RETRIEVAL TIME UTC (CIN): 2026-09-20T16:14:07.580983Z
SOURCE URL (HOU TEAM_OFFICIAL_SITE): https://www.houstontexans.com/news/texans-inactives-week-2-vs-cincinnati-bengals
PUBLICATION TIME (HOU): datePublished 2026-09-20T15:30:08.007Z; dateModified 2026-09-20T15:35:18.101Z
RETRIEVAL TIME UTC (HOU): 2026-09-20T16:14:07.584877Z
TEAM 1 INACTIVES (CIN, 7 players; NFL.com form | team-source form):
  DT B.J. Hill | DT (92) B.J. Hill
  C Connor Lew | C (65) Connor Lew
  QB Josh Johnson | QB (11) Josh Johnson
  CB Josh Newton | CB (28) Josh Newton
  WR Ke'Shawn Williams | WR (12) Ke'Shawn Williams
  DT Landon Robinson | DT (96) Landon Robinson
  OT Myles Hinton | OT (77) Myles Hinton
TEAM 2 INACTIVES (HOU, 7 players; NFL.com form | team-source form):
  TE Brevin Jordan | TE No. 9 Brevin Jordan
  CB Collin Wright | CB No. 37 Collin Wright
  G Ed Ingram | G No. 69 Ed Ingram
  DE Jadeveon Clowney | DE No. 90 Jadeveon Clowney
  LB Jake Hummel | LB No. 33 Jake Hummel
  OT Nate Thomas | T No. 78 Nate Thomas
  WR Nico Collins | WR No. 12 Nico Collins
RAW EVIDENCE:
  raw/nflart_https_www_nfl_com_news_nfl_week_2_inactives_players_ruled_out_sunday_14_games_2026.html
  raw/team_https_www_bengals_com_news_bengals_texans_inactives_week_2_2026.html  (+ .body.txt extracted text)
  raw/team_https_www_houstontexans_com_news_texans_inactives_week_2_vs_cincinnati_bengals.html  (+ .body.txt extracted text)
HASH (sha256 of raw HTML):
  57822f63314c176d897d4ec087eb384764c56a2afe3532abfb3a31934a39507d  raw/nflart_https_www_nfl_com_news_nfl_week_2_inactives_players_ruled_out_sunday_14_games_2026.html
  f07e575523ccdf37e9e6059fc4f6fd9c95267c194e32ebde09649423e823f93f  raw/team_https_www_bengals_com_news_bengals_texans_inactives_week_2_2026.html
  5d305765c7fba252e4b0e958ead963838c0bc38e7b9a1e753df88cb4b4ae2c01  raw/team_https_www_houstontexans_com_news_texans_inactives_week_2_vs_cincinnati_bengals.html
STATUS: COMPLETE_OFFICIAL_INACTIVES
```

```
GAME: CLE @ TB (2026-09-20 17:00Z, 1:00 PM ET)
OFFICIAL SOURCE: NFL.com official inactives article (league) + official team websites
SOURCE URL (league): https://www.nfl.com/news/nfl-week-2-inactives-players-ruled-out-sunday-14-games-2026
PUBLICATION TIME (league): datePublished 2026-09-20T15:40:23.31Z; dateModified 2026-09-20T15:54:29.746Z
RETRIEVAL TIME UTC (league): 2026-09-20T16:10:52.440815Z
SOURCE URL (CLE TEAM_OFFICIAL_SITE): https://www.clevelandbrowns.com/news/browns-announce-inactives-for-week-2-vs-buccaneers
PUBLICATION TIME (CLE): datePublished 2026-09-20T15:30:18.89Z; dateModified 2026-09-20T15:30:18.89Z
RETRIEVAL TIME UTC (CLE): 2026-09-20T16:14:07.592378Z
SOURCE URL (TB TEAM_OFFICIAL_SITE): https://www.buccaneers.com/news/browns-bucs-inactives-jacob-parrish-ruled-out
PUBLICATION TIME (TB): datePublished 2026-09-20T15:30:00Z; dateModified 2026-09-20T15:37:31.987Z
RETRIEVAL TIME UTC (TB): 2026-09-20T16:14:07.595345Z
TEAM 1 INACTIVES (CLE, 6 players; NFL.com form | team-source form):
  S Daniel Thomas | S Daniel Thomas
  LB Justin Jefferson | LB Justin Jefferson
  C Parker Brailsford | C Parker Brailsford
  QB Taylen Green [emergency third QB] | QB Taylen Green (3QB)
  G Teven Jenkins | G Teven Jenkins
  CB Toriano Pride Jr. | CB Toriano Pride Jr. | FLAG: OPPONENT_SITE_NAME_VARIANT
TEAM 2 INACTIVES (TB, 6 players; NFL.com form | team-source form):
  CB Ayden Garnes | CB Ayden Garnes
  G Billy Schrauth | G Billy Schrauth
  DL DeMonte Capehart | DL DeMonte Capehart
  DL Elijah Simmons | DL Elijah Simmons
  CB Jacob Parrish | CB Jacob Parrish
  G Luke Haggard | G Luke Haggard
RAW EVIDENCE:
  raw/nflart_https_www_nfl_com_news_nfl_week_2_inactives_players_ruled_out_sunday_14_games_2026.html
  raw/team_https_www_clevelandbrowns_com_news_browns_announce_inactives_for_week_2_vs_buccaneers.html  (+ .body.txt extracted text)
  raw/team_https_www_buccaneers_com_news_browns_bucs_inactives_jacob_parrish_ruled_out.html  (+ .body.txt extracted text)
HASH (sha256 of raw HTML):
  57822f63314c176d897d4ec087eb384764c56a2afe3532abfb3a31934a39507d  raw/nflart_https_www_nfl_com_news_nfl_week_2_inactives_players_ruled_out_sunday_14_games_2026.html
  3301a69d304992a26906c9bf5f23f820b1f4981aa6fd32fc70e5b8b3eeade1de  raw/team_https_www_clevelandbrowns_com_news_browns_announce_inactives_for_week_2_vs_buccaneers.html
  50cf34f03c69f7d1cf2a9e658cb4be171b8ceb96badcce50eccefec44dd658db  raw/team_https_www_buccaneers_com_news_browns_bucs_inactives_jacob_parrish_ruled_out.html
STATUS: COMPLETE_OFFICIAL_INACTIVES
```

## Final summary

- Games complete (both clubs on the official NFL page and at least one official club site): 8 of 8
- Games incomplete: 0
- Missing clubs: none on the league page. Club-site gap: CHI (no chicagobears.com inactives post located; covered by NFL.com + vikings.com)
- SOURCE_CONFLICT (membership): 0. Display-form variants: 11 rows (see table)
- Emergency third QB designations preserved as displayed (CAR Haynes King, NO Zach Wilson, BAL Joe Fagnano, CHI Case Keenum, PIT Will Howard, NE Behren Morton, CLE Taylen Green, PHI Tanner McKee); the third QB dresses and is eligible only under the emergency rule, per the source notes

## Files

- `NFL_wk2_1pm_official_inactives_merged_2026-09-20.csv`: 98 rows, one per declaration, NFL.com and team-source forms side by side with URLs, timestamps, hashes, flags
- `NFL_wk2_1pm_official_inactives_nflcom_2026-09-20.csv`: NFL.com-only parse (98 rows)
- `role_and_roster_evidence.csv`: explicit team-site statements (active confirmations, starters, elevations, IR moves) with URLs and timestamps; statements only, no inference
- `nfl_injury_report_reg2.txt`: text extraction of https://www.nfl.com/injuries/league/2026/reg2 (Friday designations; NOT inactive status)
- `raw/`: all raw HTML (nfl_*, nflart_*, idx_* team news indexes, team_*, extra_*) and extracted `.body.txt`; `SHA256SUMS`; `manifest_*.json` (url, file, bytes, sha256, retrieved_utc, JSON-LD dates)
- Known irrelevant capture: raw/team_*chicagobears*activate_ozzy_trapilo*.html is a 2026-08-16 roster move (stale); kept for completeness of the fetch log