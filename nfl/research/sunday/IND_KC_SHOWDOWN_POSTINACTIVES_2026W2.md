# IND@KC Showdown — POSTINACTIVES_CURRENT

**USABLE FOR PREINACTIVES SAFE SHOWDOWN CONSTRUCTION: YES**

Run `12eda64603a377d7` · 8,000 draws · information cut `2026-09-20T23:05:00Z` · generated 2026-09-20T23:11:56Z

Inactive gate: **0_OFFICIALLY_INACTIVE_PLAYERS_IN_PLAYABLE_BOARD**. 13 declared inactive ids were intersected with the 30 gsis_id rows the run actually emitted. 0 survived.

CANDIDATE_NOT_ACCEPTED_BASELINE. The run stops at artifact_sealing on two stale registered inputs (denom_panel, team_volume_history). Every football layer upstream of that stop passed. DST_UNSUPPORTED: the engine emits no team-defence outputs, so the two DST salary rows have no projection here and none was invented. V2 NOT YET EARNED.

## Blockers and uncertain roles — read before pricing anything

### Role assumptions the depth chart does not support

| player | team | flag | projected carries | depth chart |
|---|---|---|---|---|
| **Ben VanSumeren** | KC | `FULLBACK_GIVEN_RUSHING_WORKLOAD` | 9.41 | FB |
| **Ben VanSumeren** | KC | `NON_RB_PROJECTED_ABOVE_DEPTH_CHART_RB1` | 9.41 | FB |

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
| IND | 2 | 2 | 6 | 3 | 1 |
| KC | 2 | 4 | 6 | 3 | 1 |

Skill-layer gate: **ALL_SKILL_POSITIONS_HAVE_ROWS** 

DK offers 52 skill FLEX rows; **23** have no emitted projection. Every one is a minimum-salary bench or special-teams name the model gave no role. Absent is absent — none was filled in.

## Top FLEX by model mean

| player | team | pos | mean | p75 | p90 | p95 | ceiling | P(>=20) | P(>=30) |
|---|---|---|---|---|---|---|---|---|---|
| Patrick Mahomes | KC | QB | **18.58** | 24.5 | 30.9 | 35.0 | 68.0 | 0.420 | 0.113 |
| Daniel Jones | IND | QB | **16.01** | 21.4 | 28.3 | 33.1 | 71.8 | 0.295 | 0.077 |
| Rashee Rice | KC | WR | **15.39** | 21.2 | 29.3 | 34.4 | 90.3 | 0.286 | 0.091 |
| Jonathan Taylor | IND | RB | **14.23** | 19.4 | 25.7 | 29.6 | 59.2 | 0.233 | 0.048 |
| Travis Kelce | KC | TE | **11.89** | 16.0 | 23.3 | 28.4 | 66.3 | 0.155 | 0.037 |
| Ben VanSumeren | KC | RB | **10.53** | 14.2 | 19.7 | 23.6 | 53.1 | 0.096 | 0.015 |
| Tyler Warren | IND | TE | **9.21** | 12.9 | 18.4 | 22.5 | 58.8 | 0.079 | 0.014 |
| Keenan Allen | IND | WR | **8.88** | 12.7 | 18.5 | 22.8 | 61.9 | 0.080 | 0.015 |
| Harrison Butker | KC | K | **8.11** | 11.0 | 14.0 | 16.0 | 30.0 | 0.014 | 0.000 |
| Spencer Shrader | IND | K | **8.09** | 11.0 | 14.0 | 16.0 | 27.0 | 0.016 | 0.000 |
| Kenneth Walker III | KC | RB | **8.05** | 11.8 | 16.8 | 20.3 | 45.7 | 0.054 | 0.006 |
| Alec Pierce | IND | WR | **7.52** | 10.8 | 18.1 | 23.2 | 54.7 | 0.075 | 0.015 |
| Josh Downs | IND | WR | **7.27** | 10.8 | 15.9 | 19.9 | 48.5 | 0.050 | 0.011 |
| Cyrus Allen | KC | WR | **6.32** | 9.4 | 14.7 | 19.1 | 48.0 | 0.043 | 0.009 |
| Seth McGowan | IND | RB | **6.30** | 8.8 | 13.6 | 17.1 | 55.0 | 0.031 | 0.006 |
| Xavier Worthy | KC | WR | **6.25** | 9.3 | 14.6 | 18.7 | 57.1 | 0.041 | 0.007 |
| Noah Gray | KC | TE | **3.55** | 5.3 | 9.6 | 12.6 | 45.3 | 0.009 | 0.000 |
| Emmett Johnson | KC | RB | **3.39** | 4.9 | 8.8 | 11.3 | 37.2 | 0.006 | 0.001 |

## Top CPT candidates by model ceiling (CPT p95 = 1.5x FLEX p95)

| player | team | pos | CPT mean | CPT p90 | CPT p95 | CPT P(>=30) | corr. to own QB |
|---|---|---|---|---|---|---|---|
| Patrick Mahomes | KC | QB | 27.88 | 46.4 | **52.5** | 0.420 | Patrick Mahomes +1.000 |
| Rashee Rice | KC | WR | 23.08 | 44.0 | **51.6** | 0.286 | Patrick Mahomes +0.370 |
| Daniel Jones | IND | QB | 24.02 | 42.5 | **49.7** | 0.295 | Daniel Jones +1.000 |
| Jonathan Taylor | IND | RB | 21.35 | 38.5 | **44.4** | 0.233 | Justin Fields -0.011 |
| Travis Kelce | KC | TE | 17.83 | 35.0 | **42.6** | 0.155 | Patrick Mahomes +0.336 |
| Ben VanSumeren | KC | RB | 15.79 | 29.6 | **35.4** | 0.096 | Patrick Mahomes +0.123 |
| Alec Pierce | IND | WR | 11.27 | 27.1 | **34.8** | 0.075 | Daniel Jones +0.303 |
| Keenan Allen | IND | WR | 13.32 | 27.8 | **34.2** | 0.080 | Daniel Jones +0.280 |
| Tyler Warren | IND | TE | 13.82 | 27.6 | **33.8** | 0.079 | Daniel Jones +0.326 |
| Kenneth Walker III | KC | RB | 12.08 | 25.2 | **30.4** | 0.054 | Patrick Mahomes +0.115 |
| Josh Downs | IND | WR | 10.90 | 23.9 | **29.9** | 0.050 | Daniel Jones +0.281 |
| Cyrus Allen | KC | WR | 9.48 | 22.1 | **28.6** | 0.043 | Patrick Mahomes +0.239 |
| Xavier Worthy | KC | WR | 9.37 | 21.9 | **28.1** | 0.041 | Patrick Mahomes +0.220 |
| Justin Fields | KC | QB | 3.35 | 10.6 | **27.2** | 0.043 | Justin Fields +1.000 |
| Seth McGowan | IND | RB | 9.45 | 20.4 | **25.6** | 0.031 | Daniel Jones +0.025 |

## Top FLEX by ceiling value (DOWNSTREAM METADATA — salary never touched the model)

| player | team | pos | FLEX p95 | salary | p95 per $1k | mean per $1k |
|---|---|---|---|---|---|---|
| Ben VanSumeren | KC | RB | 23.6 | 200 | **118.00** | 52.63 |
| Anthony Gould | IND | WR | 11.1 | 200 | **55.50** | 10.41 |
| Brashard Smith | KC | RB | 10.3 | 400 | **25.75** | 5.52 |
| Deion Burks | IND | WR | 11.4 | 1000 | **11.40** | 2.54 |
| Nikko Remigio | KC | WR | 5.5 | 800 | **6.88** | 0.95 |
| Cyrus Allen | KC | WR | 19.1 | 2800 | **6.82** | 2.26 |
| Jake Briningstool | KC | TE | 9.5 | 1600 | **5.94** | 1.28 |
| Jalen Royals | KC | WR | 6.4 | 1200 | **5.33** | 0.80 |
| Seth McGowan | IND | RB | 17.1 | 3400 | **5.03** | 1.85 |
| Travis Kelce | KC | TE | 28.4 | 6200 | **4.58** | 1.92 |
| Mo Alie-Cox | IND | TE | 10.5 | 2400 | **4.38** | 1.01 |
| Noah Gray | KC | TE | 12.6 | 3000 | **4.20** | 1.18 |
| Keenan Allen | IND | WR | 22.8 | 5600 | **4.07** | 1.59 |
| Laquon Treadwell | IND | WR | 7.5 | 2000 | **3.75** | 0.60 |
| Rashee Rice | KC | WR | 34.4 | 9400 | **3.66** | 1.64 |

## Correlation structure, counted from the 8,000 draws

| player | team | mean corr. same team | mean corr. opposing |
|---|---|---|---|
| Patrick Mahomes | KC | +0.1099 | -0.0216 |
| Daniel Jones | IND | +0.1126 | -0.0234 |
| Rashee Rice | KC | +0.0094 | -0.0168 |
| Jonathan Taylor | IND | -0.0562 | -0.0071 |
| Travis Kelce | KC | +0.0191 | -0.0176 |
| Ben VanSumeren | KC | -0.0051 | -0.0175 |
| Tyler Warren | IND | +0.0255 | -0.0141 |
| Keenan Allen | IND | +0.0194 | -0.0162 |
| Harrison Butker | KC | +0.0135 | +0.0120 |
| Spencer Shrader | IND | +0.0143 | +0.0083 |
| Kenneth Walker III | KC | -0.0121 | -0.0083 |
| Alec Pierce | IND | +0.0209 | -0.0119 |
| Josh Downs | IND | +0.0173 | -0.0097 |
| Cyrus Allen | KC | +0.0079 | -0.0112 |

Every correlation above is a Pearson correlation between two players' DK point draws in the same simulated games. None of it comes from a stacking heuristic.

## What did NOT enter the football model

No sportsbook price, DraftKings salary, ownership estimate, optimiser metric or third-party projection entered the football model. The third-party sheet supplied with this request carries VegasPts, FC Proj, My Proj, Floor, Ceiling and an exposure column; it is preserved as evidence and is never parsed by this pipeline.

Third-party sheet handling: `PRESERVED_NEVER_PARSED`.

## When official inactives arrive

The same pipeline reruns against the same fixture with the inactive list applied, and emits `POSTINACTIVES_CURRENT` so the already-built candidate lineup universe can be rescored rather than rebuilt.
