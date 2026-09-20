# IND@KC Showdown — PREINACTIVES_SAFE_CANDIDATE

**USABLE FOR PREINACTIVES SAFE SHOWDOWN CONSTRUCTION: YES**

Run `44fccb9d9f0458a6` · 8,000 draws · information cut `2026-09-20T22:35:00Z` · generated 2026-09-20T23:06:01Z

Inactive gate: **PREINACTIVES_NOT_CERTIFIED**. Official inactives are not available at this information cut. No player was excluded on availability grounds. Presence in a DraftKings salary file is NOT evidence of activity and absence from one is NOT evidence of inactivity.

CANDIDATE_NOT_ACCEPTED_BASELINE. The run stops at artifact_sealing on two stale registered inputs (denom_panel, team_volume_history). Every football layer upstream of that stop passed. DST_UNSUPPORTED: the engine emits no team-defence outputs, so the two DST salary rows have no projection here and none was invented. V2 NOT YET EARNED.

## Blockers and uncertain roles — read before pricing anything

### Role assumptions the depth chart does not support

| player | team | flag | projected carries | depth chart |
|---|---|---|---|---|
| **Ben VanSumeren** | KC | `FULLBACK_GIVEN_RUSHING_WORKLOAD` | 9.384 | FB |
| **Ben VanSumeren** | KC | `NON_RB_PROJECTED_ABOVE_DEPTH_CHART_RB1` | 9.384 | FB |

These are MODEL ROLE ASSUMPTIONS, not usage forecasts. The engine carries no depth-chart prior, so it can hand a fullback a lead back's workload. Salary was deliberately not used to judge this — letting price referee a projection is the contamination this pipeline exists to prevent.

### In your saved entry template with NO projection

| player | team | pos | state |
|---|---|---|---|
| **Davon Booth** | IND | RB | `NO_EMITTED_ROW` |

An optimiser starting from that template would carry this player forward with nothing behind him.

### Alias left unresolved — Drew Ogletree (IND)

State: `LEFT_UNRESOLVED_BY_OWNER_RULING` · blocking: **False**

The roster vintage carries full_name "Andrew Ogletree" and football_name "Andrew". Neither field contains "Drew", so the alias CANNOT be verified cleanly from the authoritative source held here and was not assumed.

**Materiality: NON_CORE. The model does emit a row for 00-0037292: DK mean 1.0965, p95 6.6, third among IND tight ends behind Tyler Warren (9.05 / 22.7) and Mo Alie-Cox (2.47 / 10.5). That is not a meaningful ceiling, so the unresolved salary link changes no Showdown decision.**

Note the distinction this package now keeps: an unresolved DraftKings salary row is NOT a missing forecast. The model carries this player under the club-declared name; what is missing is the link to his DK price, and for a non-core player that changes no decision.

## Coverage audit

| club | QB | RB | WR | TE | K |
|---|---|---|---|---|---|
| IND | 3 | 3 | 7 | 3 | 1 |
| KC | 3 | 4 | 6 | 4 | 1 |

Skill-layer gate: **ALL_SKILL_POSITIONS_HAVE_ROWS** 

DK offers 52 skill FLEX rows; **18** have no emitted projection. Every one is a minimum-salary bench or special-teams name the model gave no role. Absent is absent — none was filled in.

## Top FLEX by model mean

| player | team | pos | mean | p75 | p90 | p95 | ceiling | P(>=20) | P(>=30) |
|---|---|---|---|---|---|---|---|---|---|
| Patrick Mahomes | KC | QB | **18.18** | 24.3 | 30.8 | 34.8 | 65.8 | 0.403 | 0.115 |
| Daniel Jones | IND | QB | **15.60** | 21.1 | 28.0 | 32.5 | 72.8 | 0.288 | 0.072 |
| Rashee Rice | KC | WR | **15.10** | 20.7 | 28.9 | 34.2 | 79.0 | 0.270 | 0.087 |
| Jonathan Taylor | IND | RB | **13.35** | 18.1 | 24.3 | 28.4 | 57.9 | 0.194 | 0.038 |
| Travis Kelce | KC | TE | **11.66** | 15.6 | 22.6 | 27.7 | 54.7 | 0.148 | 0.034 |
| Ben VanSumeren | KC | RB | **10.44** | 14.2 | 19.8 | 23.6 | 45.1 | 0.098 | 0.015 |
| Tyler Warren | IND | TE | **9.05** | 12.6 | 18.7 | 22.7 | 51.0 | 0.082 | 0.013 |
| Keenan Allen | IND | WR | **8.76** | 12.5 | 18.3 | 22.4 | 60.2 | 0.079 | 0.015 |
| Harrison Butker | KC | K | **8.18** | 11.0 | 14.0 | 16.0 | 29.0 | 0.014 | 0.000 |
| Kenneth Walker III | KC | RB | **8.15** | 11.8 | 16.8 | 20.5 | 44.6 | 0.056 | 0.007 |
| Spencer Shrader | IND | K | **8.07** | 11.0 | 14.0 | 16.0 | 29.0 | 0.013 | 0.000 |
| Alec Pierce | IND | WR | **7.41** | 10.8 | 18.0 | 22.1 | 49.7 | 0.069 | 0.013 |
| Josh Downs | IND | WR | **7.00** | 10.3 | 15.8 | 19.9 | 54.3 | 0.050 | 0.009 |
| Cyrus Allen | KC | WR | **6.22** | 9.3 | 14.6 | 18.7 | 46.5 | 0.041 | 0.007 |
| Xavier Worthy | KC | WR | **6.18** | 9.2 | 14.7 | 18.6 | 56.8 | 0.040 | 0.006 |
| Seth McGowan | IND | RB | **5.96** | 8.5 | 13.2 | 16.3 | 51.9 | 0.022 | 0.004 |
| Noah Gray | KC | TE | **3.47** | 5.1 | 9.6 | 12.7 | 40.5 | 0.010 | 0.001 |
| Emmett Johnson | KC | RB | **3.38** | 4.9 | 8.8 | 11.3 | 37.4 | 0.005 | 0.000 |

## Top CPT candidates by model ceiling (CPT p95 = 1.5x FLEX p95)

| player | team | pos | CPT mean | CPT p90 | CPT p95 | CPT P(>=30) | corr. to own QB |
|---|---|---|---|---|---|---|---|
| Patrick Mahomes | KC | QB | 27.26 | 46.3 | **52.2** | 0.403 | Patrick Mahomes +1.000 |
| Rashee Rice | KC | WR | 22.65 | 43.4 | **51.3** | 0.270 | Patrick Mahomes +0.347 |
| Daniel Jones | IND | QB | 23.41 | 42.0 | **48.7** | 0.288 | Daniel Jones +1.000 |
| Jonathan Taylor | IND | RB | 20.02 | 36.5 | **42.6** | 0.194 | Justin Fields -0.013 |
| Travis Kelce | KC | TE | 17.49 | 33.9 | **41.6** | 0.148 | Patrick Mahomes +0.313 |
| Ben VanSumeren | KC | RB | 15.66 | 29.7 | **35.4** | 0.098 | Patrick Mahomes +0.104 |
| Tyler Warren | IND | TE | 13.57 | 28.1 | **34.0** | 0.082 | Daniel Jones +0.313 |
| Keenan Allen | IND | WR | 13.14 | 27.4 | **33.6** | 0.079 | Daniel Jones +0.275 |
| Alec Pierce | IND | WR | 11.11 | 27.0 | **33.2** | 0.069 | Daniel Jones +0.284 |
| Kenneth Walker III | KC | RB | 12.23 | 25.2 | **30.8** | 0.056 | Patrick Mahomes +0.104 |
| Josh Downs | IND | WR | 10.49 | 23.7 | **29.9** | 0.050 | Daniel Jones +0.267 |
| Cyrus Allen | KC | WR | 9.33 | 21.9 | **28.1** | 0.041 | Patrick Mahomes +0.249 |
| Xavier Worthy | KC | WR | 9.27 | 22.1 | **27.9** | 0.040 | Patrick Mahomes +0.197 |
| Justin Fields | KC | QB | 3.04 | 8.7 | **25.0** | 0.039 | Justin Fields +1.000 |
| Seth McGowan | IND | RB | 8.95 | 19.8 | **24.4** | 0.022 | Daniel Jones +0.023 |

## Top FLEX by ceiling value (DOWNSTREAM METADATA — salary never touched the model)

| player | team | pos | FLEX p95 | salary | p95 per $1k | mean per $1k |
|---|---|---|---|---|---|---|
| Ben VanSumeren | KC | RB | 23.6 | 200 | **118.00** | 52.21 |
| Anthony Gould | IND | WR | 10.7 | 200 | **53.50** | 10.06 |
| Jared Wiley | KC | TE | 6.3 | 200 | **31.52** | 4.88 |
| Brashard Smith | KC | RB | 10.3 | 400 | **25.75** | 5.50 |
| Deion Burks | IND | WR | 11.1 | 1000 | **11.10** | 2.52 |
| Nikko Remigio | KC | WR | 6.2 | 800 | **7.75** | 1.01 |
| Ashton Dulin | IND | WR | 1.4 | 200 | **7.00** | 1.00 |
| Cyrus Allen | KC | WR | 18.7 | 2800 | **6.68** | 2.22 |
| Jake Briningstool | KC | TE | 9.5 | 1600 | **5.94** | 1.29 |
| DJ Giddens | IND | RB | 7.6 | 1400 | **5.43** | 0.96 |
| Jalen Royals | KC | WR | 6.4 | 1200 | **5.33** | 0.80 |
| Seth McGowan | IND | RB | 16.3 | 3400 | **4.79** | 1.75 |
| Travis Kelce | KC | TE | 27.7 | 6200 | **4.47** | 1.88 |
| Mo Alie-Cox | IND | TE | 10.5 | 2400 | **4.38** | 1.03 |
| Noah Gray | KC | TE | 12.7 | 3000 | **4.23** | 1.16 |

## Correlation structure, counted from the 8,000 draws

| player | team | mean corr. same team | mean corr. opposing |
|---|---|---|---|
| Patrick Mahomes | KC | +0.0810 | -0.0202 |
| Daniel Jones | IND | +0.0722 | -0.0175 |
| Rashee Rice | KC | +0.0088 | -0.0126 |
| Jonathan Taylor | IND | -0.0418 | -0.0174 |
| Travis Kelce | KC | +0.0169 | -0.0146 |
| Ben VanSumeren | KC | -0.0121 | -0.0166 |
| Tyler Warren | IND | +0.0211 | -0.0116 |
| Keenan Allen | IND | +0.0184 | -0.0109 |
| Harrison Butker | KC | +0.0112 | +0.0055 |
| Kenneth Walker III | KC | -0.0124 | -0.0092 |
| Spencer Shrader | IND | +0.0114 | +0.0081 |
| Alec Pierce | IND | +0.0178 | -0.0112 |
| Josh Downs | IND | +0.0129 | -0.0125 |
| Cyrus Allen | KC | +0.0066 | -0.0105 |

Every correlation above is a Pearson correlation between two players' DK point draws in the same simulated games. None of it comes from a stacking heuristic.

## What did NOT enter the football model

No sportsbook price, DraftKings salary, ownership estimate, optimiser metric or third-party projection entered the football model. The third-party sheet supplied with this request carries VegasPts, FC Proj, My Proj, Floor, Ceiling and an exposure column; it is preserved as evidence and is never parsed by this pipeline.

Third-party sheet handling: `PRESERVED_NEVER_PARSED`.

## When official inactives arrive

The same pipeline reruns against the same fixture with the inactive list applied, and emits `POSTINACTIVES_CURRENT` so the already-built candidate lineup universe can be rescored rather than rebuilt.
