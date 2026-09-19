# NFL Full-Slate DFS Lineup Construction: Evidence, Disagreements, and an Implementation Blueprint

Scope: DraftKings Classic and FanDuel Classic main/full NFL slates. Single-game, Showdown, Captain, and MVP formats are out of scope except where an explicit contrast is needed. Every claim below is labeled by evidence class. Football prediction and DFS portfolio strategy are kept separate throughout, because they are different estimation problems with different validation requirements.

## Section I: Evidence classes and how to read this report

Every substantive claim in this report carries one of the following labels.

| Label | Meaning |
|---|---|
| `PRIMARY_RULE` | Taken from an operator's own rules page or machine-readable rules endpoint |
| `MEASURED_HERE` | Computed in this engagement from archived nflverse play-by-play, with method stated |
| `PRO_STATEMENT` | A direct statement from a named person who plays or analyzes DFS professionally |
| `INDUSTRY_CONVENTION` | A default embedded in commercial optimizer or simulator products |
| `QUANT_EXTERNAL` | A statistical or academic result produced outside this engagement |
| `COMMUNITY` | A widely repeated heuristic with no traceable measurement |
| `SYNTHESIS` | An inference drawn in this report, not asserted by any cited source |
| `HYPOTHESIS` | A testable proposition where the evidence is currently too weak to act on |
| `UNKNOWN` | Could not be verified with available sources |

Two standing project constraints govern everything that follows. Sportsbook prices and DFS ownership are never predictive football inputs. They may enter only downstream of the football model, as contest-environment variables inside the portfolio layer. Second, no parameter may be selected using information from a week later than the week being predicted.

## Section II: What was measured in this engagement, and how

Most publicly cited NFL DFS correlation numbers are either unsourced or derived with role labels that are not available at lineup-lock time. This report therefore measures the correlation structure directly from archived play-by-play for the 2024 and 2025 regular seasons, using two labeling schemes so the difference between them can be quantified.

Method, `MEASURED_HERE`:

- Source files: `nfl/vintage/pbp_2024.23370d5d10f8104d.csv.gz` and `nfl/vintage/pbp_2025.2f135887790a013f.csv.gz`, regular season only, 272 games per season.
- Per player-game offensive stat lines were rebuilt from play level: passing yards, passing touchdowns, interceptions thrown, rushing yards, rushing touchdowns, receptions, receiving yards, receiving touchdowns, fumbles lost, successful two-point conversions, and return touchdowns.
- Fantasy points were computed twice per player-game, once under DraftKings Classic scoring and once under FanDuel Classic scoring, using the values in Section III.
- Team defense points were rebuilt from sacks, interceptions, fumble recoveries, safeties, defensive and return touchdowns, and a points-allowed figure assembled from the opponent's offensive and special-teams scoring only. The points-allowed reconstruction excludes touchdowns scored by the opponent's defense, consistent with the operator rule, but does not subtract the extra point that follows such a touchdown. That is a known, small, stated approximation.
- Role labels were assigned two ways. The `ex_ante` scheme ranks each team's players using only prior weeks of the same season: the quarterback is the player with the most prior pass attempts, `PC1` through `PC3` are the three players with the most prior targets, and `RUSH1` and `RUSH2` are the two players with the most prior carries. The `realized` scheme applies the same ranking rules to the current game's own usage. Week 1 has no prior history and is therefore absent from the `ex_ante` panel, giving 512 team-games per season rather than 544.
- Correlations are Pearson coefficients on fantasy points. Joint-tail lift is the empirical probability that both members of a pair land at or above their own 80th percentile, divided by the product of the marginal probabilities. Stack ceiling inflation compares the 95th percentile of the actual summed stack against the 95th percentile of a 200,000-draw independent resample of the same marginals.
- Scripts and full result files are included alongside this report as `measure_dfs_correlations.py`, `measure_tails.py`, `dfs_correlation_results.json`, and `dfs_tail_results.json`.

Stated limitations, `MEASURED_HERE`:

- Play-by-play does not carry a position field, and the only archived depth-chart file in the repository is a single 2026-09-17 snapshot with no season or week history. Wide receiver and tight end therefore cannot be separated in this panel. `PC1` through `PC3` are usage-ranked pass catchers regardless of nominal position. Any claim in the literature that is specifically about tight ends rather than about second and third pass catchers is `UNKNOWN` against this measurement.
- Two seasons is a small sample for tail statistics. Every tail number below is reported per season precisely so the year-to-year instability is visible rather than averaged away.
- Usage-rank labels are a proxy for the roles a DFS player actually chooses among. A real system should label by projected role from the football model, which is closer to `ex_ante` than to `realized` but not identical to either.

## Part 1: Site rules and structural differences

### DraftKings Classic, `PRIMARY_RULE`

From the DraftKings machine-readable rules endpoint at [api.draftkings.com](https://api.draftkings.com/rules-and-scoring/RulesAndScoring.json):

- Nine roster slots: one QB, two RB, three WR, one TE, one FLEX taking RB, WR, or TE, and one DST.
- Salary cap of $50,000.
- Lineups must include players from at least two different NFL games.
- No kicker in the Classic format.

The [DraftKings Classic overview article](https://support.draftkings.com/dk/en-us/game-style-classic-overview?id=kb_article_view&sysparm_article=KB0010665) states the $50,000 cap and a requirement of athletes from at least two different teams, and does not list NFL roster slots or scoring.

DraftKings scoring, from the same endpoint: passing touchdown 4, passing yards 0.04 per yard, 300-plus passing yard game bonus 3, interception thrown -1, rushing touchdown 6, rushing yards 0.1 per yard, 100-plus rushing yard game bonus 3, receiving touchdown 6, receiving yards 0.1 per yard, 100-plus receiving yard game bonus 3, reception 1, punt/kickoff/field-goal return touchdown 6, fumble lost -1, two-point conversion 2, offensive fumble recovery touchdown 6.

DraftKings DST scoring: sack 1, interception 2, fumble recovery 2, any return or blocked-kick return touchdown 6, safety 2, blocked kick 2, two-point conversion or extra-point return 2. Points allowed: 0 gives 10, 1 to 6 gives 7, 7 to 13 gives 4, 14 to 20 gives 1, 21 to 27 gives 0, 28 to 34 gives -1, 35-plus gives -4. The endpoint states that points allowed counts only points surrendered while the DST is on the field and lists the specific scoring plays that count against it.

### FanDuel Classic, `PRIMARY_RULE`

From [fanduel.com/rules](https://www.fanduel.com/rules):

- Most contests require players from at least three different teams.
- No more than four players from the same team.
- Team lineup restrictions apply at the time of drafting the roster only.

From the [FanDuel fantasy football strategy page](https://www.fanduel.com/research/fantasy-football-strategy): nine roster slots being one QB, two RB, three WR, one TE, one FLEX taking RB, WR, or TE, and one DST, with a salary cap of $60,000.

FanDuel scoring, from [fanduel.com/rules](https://www.fanduel.com/rules): reception 0.5, receiving yards 0.1 per yard, 100-plus receiving yard bonus 3, receiving touchdown 6, rushing yards 0.1 per yard, 100-plus rushing yard bonus 3, rushing touchdown 6, passing yards 0.04 per yard, 300-plus passing yard bonus 3, passing touchdown 4, interception thrown -1, return touchdown 6, fumble lost -2, own-fumble-recovery touchdown 6, two-point conversion 2. FanDuel DST scoring matches DraftKings on sacks, interceptions, fumble recoveries, safeties, return touchdowns, and the seven points-allowed tiers, and additionally awards 2 for a blocked punt. FanDuel publishes the points-allowed formula explicitly as \( 6 \times (\text{RushTD} + \text{RecTD} + \text{OwnFumRecTD}) + 2 \times \text{2PT} + \text{XP} + 3 \times \text{FG} \), and also publishes second-half-only and fourth-quarter-only DST tables for other formats.

### The structural differences that actually change construction

| Dimension | DraftKings Classic | FanDuel Classic | Construction consequence |
|---|---|---|---|
| Salary cap | $50,000 | $60,000 | Not comparable directly; compare salary as a share of cap |
| Reception value | 1.0 | 0.5 | FanDuel compresses the gap between volume receivers and big-play receivers |
| Fumble lost | -1 | -2 | FanDuel penalizes high-carry and high-target roles slightly more |
| Minimum diversity | At least two different games | At least three different teams | Binding constraint differs in kind, not degree |
| Maximum per team | None stated | Four | FanDuel caps the maximum stack at QB plus three teammates |
| Kicker | None in Classic | None in Classic | No kicker modeling needed for full slates on either site |
| Bonuses | 3 at 300 pass, 100 rush, 100 rec | Identical | Both sites have identical threshold nonlinearity |

Two of these deserve emphasis because they are frequently stated loosely.

First, the DraftKings minimum is expressed in **games**, not teams. A DraftKings lineup drawn entirely from two teams that face each other satisfies "at least two different games" only if a second game is represented. A lineup of nine players from a single game is illegal on DraftKings Classic; a lineup of nine players from two teams in two different games is legal. `SYNTHESIS`. [DFS Hero's NFL rules page](https://dfshero.com/help/sports/nfl) states the DraftKings minimum as at least two games and the FanDuel minimums as at least three teams with at most four per team, which matches both operators' own pages.

Second, the FanDuel four-per-team maximum is the single most important rules asymmetry for stacking, and it is a hard constraint rather than a preference. On FanDuel, the largest legal single-team block is QB plus three teammates. A QB plus four teammates, which is a legal and occasionally optimal DraftKings structure, cannot be entered on FanDuel at all. Any optimizer that does not encode this will emit infeasible FanDuel lineups. `SYNTHESIS` from `PRIMARY_RULE`.

The prior second-opinion work in this project found that the repository's DraftKings Showdown solver had no both-teams constraint, and that on a single-game slate the practical impact was small, with only 56 of 8,000 sealed worlds having an illegal optimum and a maximum `p_optimal` change of 0.0009. The classic-slate analogue is not small. On a full slate the DraftKings two-game minimum is nearly never binding, but the FanDuel three-team minimum and four-per-team maximum bind constantly, because concentrated game stacks are exactly the structures tournament play wants. `SYNTHESIS`.

### Late swap, `PRIMARY_RULE`

DraftKings, from the [contest rules and scoring overview](https://support.draftkings.com/dk/en-us/fantasy-sports-contest-rules-scoring-overview?id=kb_article_view&sysparm_article=KB0010560): late-swap contests allow edits until each athlete's individual lock time, which falls "anywhere from 5 to 15 minutes before" that athlete's game. A locked athlete can be neither added nor removed. An early real-life start locks every athlete in that game. Editing after a player's game has started causes disqualification and refund. Critically, opponent lineups remain hidden until that athlete's game locks, on both late-swap and non-late-swap contests. The [late swap overview](https://support.draftkings.com/dk/en-us/late-swap-overview?id=kb_article_view&sysparm_article=KB0010786) adds that swaps must preserve the minimum number of teams represented and stay under the cap.

FanDuel, from [fanduel.com/late-swap](https://www.fanduel.com/late-swap): contests are offered with and without late swap, late-swap contests are marked with an unlocked padlock icon, a slot locks when that player's individual game starts, and swaps must stay under the cap.

The practical difference is that FanDuel's team-count and team-maximum constraints must be re-checked after every swap, whereas DraftKings only needs a two-game check that is almost always already satisfied. `SYNTHESIS`.

## Part 2: A correlation taxonomy, with measured values

The single most common modeling error in this domain is treating correlation as one static matrix. The measurements below show why that is wrong: the same pair has different signs depending on what is being conditioned on, and the mechanism that produces a positive unconditional correlation is often not within-game co-movement at all.

### 2.1 Six distinct mechanisms

`SYNTHESIS`, with measured support noted per mechanism.

1. **Shared-event correlation.** Two players score from the same physical event. A quarterback's touchdown pass and his receiver's touchdown reception are one event scored twice. This is the strongest and most reliable mechanism, and it is the only one that survives conditioning on game environment.
2. **Volume-pool correlation.** Two players draw from the same finite pool of plays. Two running backs splitting carries, or two receivers splitting targets, are negatively linked through the pool even when the pool itself grows.
3. **Game-environment correlation.** Both players benefit from the same slate-level condition, typically total plays and total scoring. This is a between-game effect: it raises the unconditional correlation of almost every pair in a game while contributing nothing within a fixed game total.
4. **Role-substitution correlation.** One player's production is conditional on another player's absence or diminished role. This is a discrete, injury-driven mechanism, not a smooth linear one, and it is badly served by a Pearson matrix.
5. **Score-state correlation.** Game script changes play-type mix. Trailing teams pass more, leading teams run more and the clock compresses. This produces correlations that flip sign between the leading and trailing team.
6. **Defense-offense correlation.** A team defense scores partly from the opponent's failure, making it mechanically opposed to the opponent's offense and weakly related to its own.

### 2.2 Measured ex-ante correlations, DraftKings scoring

`MEASURED_HERE`. Pearson correlation of DraftKings fantasy points, ex-ante usage-rank role labels, regular season, \( n = 512 \) team-games per season.

| Pair | 2024 | 2025 | Dominant mechanism |
|---|---:|---:|---|
| QB with PC1 | 0.368 | 0.274 | Shared event |
| QB with PC2 | 0.296 | 0.318 | Shared event |
| QB with PC3 | 0.208 | 0.259 | Shared event |
| QB with RUSH1 | 0.109 | 0.050 | Game environment, offset by volume pool |
| QB with RUSH2 | 0.118 | 0.117 | Game environment |
| PC1 with PC2 | -0.024 | 0.120 | Shared event against volume pool |
| PC1 with PC3 | -0.000 | 0.088 | Shared event against volume pool |
| PC2 with PC3 | 0.036 | -0.000 | Shared event against volume pool |
| PC1 with RUSH1 | 0.034 | 0.162 | Game environment against volume pool |
| PC3 with RUSH1 | 0.238 | 0.318 | Game environment |
| RUSH1 with RUSH2 | -0.121 | -0.104 | Volume pool |
| QB with own DST | -0.030 | -0.107 | Weak, mixed |
| RUSH1 with own DST | 0.139 | 0.019 | Score state, unstable |
| Team offense with own DST | -0.009 | -0.096 | Weak, mixed |
| QB with opposing DST | -0.375 | -0.371 | Defense-offense |
| Team offense with opposing DST | -0.347 | -0.391 | Defense-offense |
| RUSH1 with opposing DST | -0.294 | -0.250 | Defense-offense |
| PC1 with opposing DST | -0.114 | -0.143 | Defense-offense, diluted |
| Own DST with opposing DST | -0.229 | -0.248 | Defense-offense, both sides |
| QB with opposing QB | 0.088 | 0.180 | Game environment only |
| QB with opposing PC1 | 0.108 | 0.105 | Game environment only |
| QB with opposing PC2 | 0.036 | 0.079 | Game environment only |
| QB with opposing PC3 | 0.045 | 0.127 | Game environment only |
| QB with opposing RUSH1 | -0.021 | 0.128 | Mixed, unstable |
| PC1 with opposing PC1 | 0.094 | 0.096 | Game environment only |
| PC1 with opposing PC2 | 0.051 | 0.086 | Game environment only |
| RUSH1 with opposing RUSH1 | -0.123 | -0.067 | Score state, opposed |
| Team offense with opposing offense | 0.083 | 0.186 | Game environment |

### 2.3 The same correlations under FanDuel scoring

`MEASURED_HERE`. FanDuel half-point receptions and the larger fumble penalty change correlation magnitudes by less than 0.02 on nearly every pair. Examples: QB with PC1 is 0.378 and 0.280 on FanDuel against 0.368 and 0.274 on DraftKings; QB with PC2 is 0.307 and 0.315 against 0.296 and 0.318; PC1 with PC2 is -0.015 and 0.108 against -0.024 and 0.120; RUSH1 with RUSH2 is -0.120 and -0.082 against -0.121 and -0.104.

This is a load-bearing negative result. The correlation **structure** is not a meaningful DraftKings-versus-FanDuel difference. One correlation model can serve both sites. What differs between sites is the scoring level, the marginal distributions it induces, the roster and team constraints, and therefore which players are worth rostering. `SYNTHESIS`.

### 2.4 Realized-label inflation: a leakage warning

`MEASURED_HERE`. Re-running the identical pipeline with role labels assigned from the current game's own usage inflates exactly the correlations the industry quotes.

| Pair | Ex-ante 2024 | Realized 2024 | Ex-ante 2025 | Realized 2025 |
|---|---:|---:|---:|---:|
| QB with PC1 | 0.368 | 0.420 | 0.274 | 0.438 |
| QB with PC2 | 0.296 | 0.409 | 0.318 | 0.352 |
| PC1 with PC2 | -0.024 | 0.207 | 0.120 | 0.182 |
| PC1 with opposing PC1 | 0.094 | 0.161 | 0.096 | 0.163 |
| RUSH1 with RUSH2 | -0.121 | 0.016 | -0.104 | -0.030 |

The `PC1` with `PC2` row is the clearest case. Under realized labels, two pass catchers on the same team look positively correlated at roughly 0.18 to 0.21. Under prediction-time labels, that relationship is approximately zero in 2024 and modest in 2025. The realized-label version is not a measurement of a tradeable relationship; it is partly a measurement of the labeling rule, because a receiver only becomes `PC1` in that scheme by having produced. Any correlation matrix calibrated on realized labels and then used inside a pre-lock simulator is importing this bias. `SYNTHESIS`.

### 2.5 Conditional correlation: the static matrix is the wrong object

`MEASURED_HERE`. Splitting into terciles of realized combined game points, with correlations computed within tercile.

| Pair | Season | Low total | Mid total | High total | Unconditional |
|---|---|---:|---:|---:|---:|
| QB with opposing QB | 2024 | -0.204 | -0.131 | -0.138 | 0.088 |
| QB with opposing QB | 2025 | -0.021 | -0.137 | -0.048 | 0.180 |
| QB with PC1 | 2024 | 0.318 | 0.249 | 0.329 | 0.368 |
| QB with PC1 | 2025 | 0.188 | 0.285 | 0.091 | 0.274 |
| QB with RUSH1 | 2024 | 0.096 | 0.007 | 0.027 | 0.109 |
| QB with RUSH1 | 2025 | 0.020 | -0.050 | -0.101 | 0.050 |
| PC1 with PC2 | 2024 | -0.140 | -0.068 | -0.035 | -0.024 |
| PC1 with PC2 | 2025 | 0.024 | 0.072 | 0.072 | 0.120 |
| QB with opposing DST | 2024 | -0.418 | -0.287 | -0.321 | -0.375 |
| QB with opposing DST | 2025 | -0.403 | -0.257 | -0.277 | -0.371 |

The first two rows are the most important measurement in this report. Unconditionally, opposing quarterbacks are positively correlated. **Within a game total, they are negatively correlated in every tercile of both seasons.** The entire positive coupling between opposing offenses is a between-game effect: high-scoring games lift both sides, and once the level of the game is fixed, the two quarterbacks compete for a fixed amount of scoring.

This has a direct construction implication that differs from how the mechanism is usually described. A bring-back is not a bet that two quarterbacks will both erupt in the same game conditional on that game's scoring. It is a bet on the game's total scoring level itself, purchased through two teams instead of one. `SYNTHESIS`. That reframing changes what the correlation layer must represent: a shared game-level latent factor plus within-game competition, not a flat pairwise coefficient.

The `QB with RUSH1` rows show the score-state mechanism cleanly. In 2025, quarterback and lead rusher move from mildly positive in low-scoring games to -0.101 in the highest-scoring tercile. Shootouts are pass-heavy, and the lead back's share of a high-scoring game is smaller than his share of a low-scoring one.

### 2.6 Joint tails, which is what tournaments actually pay for

Pearson correlation is a poor summary of what a top-heavy payout structure rewards. The relevant question is whether two players hit large outcomes together.

`MEASURED_HERE`. Joint-tail lift at the 80th percentile, DraftKings scoring, ex-ante labels. A lift of 1.0 means the pair's joint tail behaves as if independent.

| Pair | 2024 lift | 2025 lift |
|---|---:|---:|
| QB with PC1 | 1.859 | 1.559 |
| QB with PC2 | 1.810 | 1.721 |
| QB with PC3 | 1.550 | 1.706 |
| QB with RUSH1 | 1.163 | 1.023 |
| PC1 with PC2 | 0.947 | 0.947 |
| RUSH1 with RUSH2 | 0.578 | 0.996 |
| QB with opposing QB | 1.362 | 1.378 |
| QB with opposing PC1 | 0.930 | 1.072 |
| PC1 with opposing PC1 | 1.544 | 1.420 |
| QB with own DST | 0.839 | 0.828 |
| RUSH1 with own DST | 1.381 | 0.891 |
| QB with opposing DST | 0.373 | 0.471 |

Four results here do not follow from the Pearson table.

- `QB with PC2` has essentially the same joint-tail lift as `QB with PC1`, and in 2025 a higher one. The secondary pass catcher is not a discounted version of the primary for ceiling purposes.
- `PC1 with PC2` shows a lift of 0.947 in both seasons. Two pass catchers on the same team co-boom slightly **less** often than independence implies, in both years, despite a positive Pearson coefficient in 2025. Double-stacking two receivers without the quarterback buys no joint-ceiling benefit.
- `PC1 with opposing PC1` has a lift of 1.544 and 1.420, higher than `QB with opposing PC1`. The cross-game pass-catcher pair is a better joint-tail structure than the quarterback-to-opposing-receiver pair that the industry usually names as the canonical bring-back.
- `QB with opposing DST` at 0.373 and 0.471 is the strongest avoidance signal in the entire panel. Those two hitting together is roughly a third to a half as likely as independence.

### 2.7 How much ceiling does stacking actually add?

`MEASURED_HERE`. The 95th percentile of the actual summed stack, against the 95th percentile of an independent resample of the same marginals.

| Structure | 2024 actual | 2024 independent | 2024 inflation | 2025 actual | 2025 independent | 2025 inflation |
|---|---:|---:|---:|---:|---:|---:|
| QB + PC1 | 57.08 | 54.50 | 4.74% | 56.28 | 53.20 | 5.80% |
| QB + PC1 + PC2 | 75.57 | 70.70 | 6.89% | 72.55 | 68.18 | 6.41% |
| QB + PC1 + PC2 + PC3 | 89.52 | 83.68 | 6.98% | 88.61 | 82.18 | 7.83% |
| QB + PC1 + RUSH1 | 76.71 | 73.66 | 4.14% | 77.19 | 73.30 | 5.31% |
| QB + PC1 + opposing PC1 | 79.38 | 74.14 | 7.07% | 77.29 | 72.50 | 6.61% |
| QB + PC1 + PC2 + opposing PC1 | 96.55 | 89.68 | 7.66% | 91.97 | 86.74 | 6.02% |
| QB + PC1 + own DST | 65.80 | 63.88 | 3.01% | 64.67 | 63.08 | 2.51% |

The effect is real, consistent in sign across both seasons, and smaller than commonly advertised. A two-player stack buys roughly 5% at the 95th percentile. Adding a second pass catcher and a bring-back raises that to roughly 6% to 8%. [DFS Degen's correlation deep dive](https://dfsdegen.com/blog/dfs-correlation-deep-dive) states a 15% to 20% ceiling boost at \( \rho = 0.55 \). That figure is internally consistent with its own premise, but the premise does not hold here: the measured prediction-time \( \rho \) is closer to 0.3, and the resulting inflation is correspondingly smaller. `SYNTHESIS`.

The correct reading is not that stacking is overrated. It is that the mechanism through which stacking wins tournaments is only partly the ceiling boost. The larger part is the duplication and field-overlap effect covered in Parts 7 and 8: a correlated block concentrates a lineup's outcomes into a small number of worlds, and if the field is not in those worlds, the payout is not shared. `SYNTHESIS`.

### 2.8 Where the published numbers disagree with this measurement

| Pair | Published value | Source and evidence class | Measured ex-ante here | Assessment |
|---|---|---|---:|---|
| QB with WR1 | 0.57 | [The Fantasy Footballers](https://www.thefantasyfootballers.com/dfs/nfl-dfs-strategy-optimal-roster-construction-for-tournaments/), citing FantasyLabs data since 2014, `QUANT_EXTERNAL` | 0.368 / 0.274 | Directionally right, magnitude well above prediction-time value |
| QB with WR (same team) | approximately 0.55 | [DFS Degen](https://dfsdegen.com/blog/dfs-correlation-deep-dive), no method stated, `COMMUNITY` | 0.368 / 0.274 | Unsupported at this magnitude |
| QB with WR1 | approximately +0.45 | [Odds Reference](https://oddsreference.com/dfs/tools/dfs-correlation-tool), no method stated, `COMMUNITY` | 0.368 / 0.274 | Closer, still above |
| QB with TE (same team) | approximately 0.45 to 0.51 | DFS Degen and The Fantasy Footballers | `UNKNOWN` | Cannot be evaluated; tight ends are not separable in this panel |
| QB with RB (same team) | approximately 0.15 | DFS Degen, `COMMUNITY` | 0.109 / 0.050 | Roughly consistent for 2024, high for 2025 |
| QB with own DST | approximately -0.3 | DFS Degen, `COMMUNITY` | -0.030 / -0.107 | Not supported; the relationship is much weaker than stated |
| QB with opposing DST | approximately +0.2 | DFS Degen, `COMMUNITY` | -0.375 / -0.371 | Sign appears to be reversed relative to the measurement; treat the published figure as unreliable |
| Opposing WR1 with QB | 0.39 | The Fantasy Footballers, citing FantasyLabs, `QUANT_EXTERNAL` | 0.108 / 0.105 | Large disagreement; the published figure is roughly four times the measured value |
| QB with WR1 versus QB with WR3 | WR1 higher by 0.13; WR2 and TE1 higher than WR3 by 0.05 | [4for4](https://www.4for4.com/2018/preseason/definitive-guide-stacking-draftkings), 2013 to 2017, projection-based labels, `QUANT_EXTERNAL` | QB-PC1 minus QB-PC3 is 0.160 and 0.015 | Ordering confirmed; gap size unstable |
| RB1 with own DST | mild positive; QB-WR1 is more than four times as large | 4for4, `QUANT_EXTERNAL` | 0.139 / 0.019 | Sign confirmed in 2024, essentially absent in 2025 |
| Opposing QBs positively correlated | "especially positive" | 4for4, `QUANT_EXTERNAL` | +0.088 / +0.180 unconditional, negative in every tercile | Correct unconditionally, wrong about the mechanism |

The two largest disagreements, on `QB with opposing DST` and `QB with opposing PC1`, matter operationally. The first would, if believed, invert a hard-avoid into a mild positive. The second would, if believed, make a bring-back look roughly as valuable as a same-team second pass catcher, when the measurement says the same-team second pass catcher is far stronger on both Pearson and joint-tail terms. `SYNTHESIS`.

### 2.9 The long pairing list

`MEASURED_HERE` where a value is given, otherwise `SYNTHESIS` or `UNKNOWN` as marked.

Positive, same team: QB with PC1; QB with PC2; QB with PC3; QB with RUSH2 as a pass-catching back proxy; PC3 with RUSH1, which is the strongest non-quarterback same-team pair measured at 0.238 and 0.318 and is probably a game-volume artifact rather than a shared-event effect; PC1 with RUSH1 weakly and unstably.

Positive, cross team: team offense with opposing offense; QB with opposing QB, unconditionally only; QB with opposing PC1 through PC3, unconditionally only and weakly; PC1 with opposing PC1, which has the second-highest joint-tail lift of any cross-team pair measured.

Negative, same team: RUSH1 with RUSH2; PC1 with PC2 conditional on game total in 2024; QB with own DST weakly; team offense with own DST weakly.

Negative, cross team: QB with opposing DST, the strongest negative measured; team offense with opposing DST; RUSH1 with opposing DST; own DST with opposing DST; RUSH1 with opposing RUSH1; PC1 with opposing DST.

Conditional or sign-flipping: QB with RUSH1, positive in low-total games and negative in high-total games; own DST with own RUSH1, positive in 2024 and absent in 2025; role-substitution pairs such as a backup running back with the starter he replaces, which are not representable as a fixed coefficient at all and are `UNKNOWN` in this panel because the ex-ante labeling assigns roles before the injury is known.

Structures rather than pairs: three-player same-team blocks, four-player same-team blocks, which are legal on DraftKings but not on FanDuel, full game stacks spanning both teams, and the double-bring-back structure of QB plus two teammates plus two opponents.
## Part 3: Quarterback stacking theory

### 3.1 What winning lineups actually look like

`QUANT_EXTERNAL`. [The Fantasy Footballers](https://www.thefantasyfootballers.com/dfs/nfl-dfs-strategy-optimal-roster-construction-for-tournaments/) analyzed two years of winning DraftKings Millionaire Maker Sunday main-slate lineups and reported that 89% contained a team stack, 83% contained a game stack, and 89% paired the quarterback with at least one pass catcher from his own team. The same analysis states that every other structural trend it tested appeared in 60% or less of winning lineups.

This is a winners-only sample and therefore has a selection problem that the source does not address: it reports \( P(\text{structure} \mid \text{win}) \), not \( P(\text{win} \mid \text{structure}) \). If 60% of all entries stack their quarterback, then an 89% rate among winners is a real but much smaller edge than the raw number suggests. `SYNTHESIS`.

The denominator is available from a second source. [Stokastic's how-to-win article](https://www.stokastic.com/articles/nfl-dfs/how-to-win-at-nfl-dfs) states, from its own research, that the field is approximately 45% quarterback plus one pass catcher, 25% quarterback plus two, 5% quarterback plus three, roughly 25% including a bring-back, and roughly 25% with no stack at all. `INDUSTRY_CONVENTION`.

Combining those two figures: the field stacks a quarterback with at least one pass catcher roughly 75% of the time, and winners do so 89% of the time. The implied lift is approximately \( 0.89 / 0.75 = 1.19 \). That is a real edge and it is nowhere near the "you must always stack" framing the raw 89% invites. `SYNTHESIS`.

### 3.2 Naked quarterback through quarterback plus three

| Structure | Measured ex-ante ceiling inflation, 2024 / 2025 | Field frequency | Assessment |
|---|---|---|---|
| Naked QB, no pass catcher | baseline | approximately 25% of the field has no stack at all | Defensible in cash games and in small-field contests where duplication risk is low; structurally weak in large-field GPPs because it wastes the one mechanism that reliably concentrates outcomes |
| QB + 1 pass catcher | 4.74% / 5.80% at p95 | approximately 45% | The default. Sufficient in cash and in single-entry mid-field play |
| QB + 2 pass catchers | 6.89% / 6.41% | approximately 25% | The best marginal step measured. The second pass catcher adds roughly 2 points of p95 inflation and, per Section 2.6, has nearly the same joint-tail lift with the quarterback as the first |
| QB + 3 pass catchers | 6.98% / 7.83% | approximately 5% | Diminishing on ceiling inflation but sharply differentiating on ownership. Legal on DraftKings; on FanDuel this consumes the entire four-per-team allowance |
| QB + 4 teammates | not measured | rare | Legal on DraftKings only. `PRIMARY_RULE`. Not measured here |

`PRO_STATEMENT`. Alex Baker, writing for Stokastic in [How I Won the $1M Milly Maker](https://www.stokastic.com/articles/nfl-dfs/how-i-won-1m-nfl-dfs), won with a quarterback plus three same-team skill players, specifically Russell Wilson at approximately 1.7% ownership with Metcalf, Lockett, and Penny, plus an Amon-Ra St. Brown bring-back at approximately 3.6%. He states plainly: "I run quarterback-plus-three-skill-player stacks a lot." He also entered approximately 25 lineups rather than the maximum, and capped himself at five lineups per quarterback.

That single data point is worth reading carefully for what it actually demonstrates. It is one tournament win, which is the noisiest possible evidence. What it does establish is that the structure is entered deliberately by at least one successful player, at low ownership, and in a portfolio of moderate size with an explicit per-quarterback cap. The per-quarterback cap is the part most likely to generalize, and it aligns with Stokastic's own stated exposure default. `SYNTHESIS`.

`INDUSTRY_CONVENTION`. [Stokastic's lineup-building article](https://www.stokastic.com/articles/nfl-dfs/how-to-build-nfl-dfs-lineups) gives quarterback exposure caps of approximately 20% and DST exposure of 10% to 20%, and describes the top-projected 150-lineup set as over-exposed, weakly correlated, and chalk-heavy, with one running back potentially appearing in more than 90% of lineups and one quarterback in 80%. Its stated GPP base structure is quarterback plus two pass catchers plus a bring-back.

### 3.3 Should the stack partner be the top pass catcher?

`MEASURED_HERE`. No, not automatically. The joint-tail table in Section 2.6 shows `QB with PC2` at 1.810 and 1.721 against `QB with PC1` at 1.859 and 1.559. On Pearson terms, 2025 actually favors `PC2` at 0.318 against `PC1` at 0.274. [4for4](https://www.4for4.com/2018/preseason/definitive-guide-stacking-draftkings) reaches a different conclusion, finding the primary receiver strongest by 0.13 over the next receiver, using 2013 to 2017 data and projection-based rather than usage-rank labels.

The reconciliation is that a primary receiver's advantage is in his marginal expectation, which the football model already captures, not in his correlation with his quarterback. The correlation layer should not be used as a second reason to prefer him. `SYNTHESIS`.

### 3.4 Bring-back or not

`MEASURED_HERE`. A bring-back raises the four-player p95 inflation from 6.89% and 6.41% (QB + PC1 + PC2) to 7.66% and 6.02% (QB + PC1 + PC2 + opposing PC1). That is inside the noise between the two seasons. On three-player structures the picture is clearer: QB + PC1 + opposing PC1 at 7.07% and 6.61% beats QB + PC1 + RUSH1 at 4.14% and 5.31%.

Conclusion, `SYNTHESIS`: the bring-back is a better third slot than a same-team running back, but it is not an unambiguous improvement over a second same-team pass catcher. The Section 2.5 tercile result explains why: the bring-back is buying game-total exposure, which is a different and partly redundant purchase once the quarterback and two pass catchers already carry that exposure.

## Part 4: Bring-backs specifically

### 4.1 What a bring-back actually is

`MEASURED_HERE` plus `SYNTHESIS`. The conventional description is that a bring-back captures "both sides of a shootout," implying that the two offenses move together. The tercile measurement contradicts that description while confirming the conclusion. Opposing quarterbacks are positively correlated unconditionally at +0.088 and +0.180, but negatively correlated inside every tercile of realized combined game points in both seasons, at values from -0.021 to -0.204. Team offense with opposing offense is +0.083 and +0.186 unconditionally.

Therefore: a bring-back is a leveraged bet on the game's total scoring level, not on the two offenses co-moving at a given level. Within a fixed total, the two sides compete. `SYNTHESIS`.

### 4.2 Which bring-back

`MEASURED_HERE`. Joint-tail lift, cross-team pairs:

| Bring-back structure | 2024 lift | 2025 lift |
|---|---:|---:|
| Own PC1 with opposing PC1 | 1.544 | 1.420 |
| Own QB with opposing QB | 1.362 | 1.378 |
| Own QB with opposing PC1 | 0.930 | 1.072 |

The pass-catcher-to-pass-catcher pairing is the strongest cross-team joint tail measured. The quarterback-to-opposing-pass-catcher pairing that most strategy content names as the canonical bring-back is the weakest of the three, at or barely above independence. This is a direct disagreement with the framing in most published guidance and with the FantasyLabs figures reported by The Fantasy Footballers, which put opposing WR1 with QB at 0.39. `SYNTHESIS`.

### 4.3 Bring-back from a losing team

`HYPOTHESIS`. The score-state mechanism predicts that the trailing team's pass catchers gain volume while the leading team's rusher gains volume, so the highest-value bring-back should be the pass catcher from the team the market expects to trail. This is not measured here, because doing it properly requires pre-game market-implied favorite status, and project constraints prohibit sportsbook prices as predictive inputs. The football model's own win-probability and score-differential distribution is the permitted substitute, and Part 22 specifies the test.

## Part 5: Mini-correlations and secondary stacks

`SYNTHESIS` with measured support.

A mini-correlation is a two-player relationship that is not a quarterback stack. Measured candidates, ex ante, DraftKings, 2024 / 2025:

| Mini-structure | Measured value | Reading |
|---|---:|---|
| PC3 with RUSH1, same team | 0.238 / 0.318 | The strongest non-quarterback same-team pair measured. Probably a pure team-volume effect: both are secondary usage that scales with total plays |
| PC1 with RUSH1, same team | 0.034 / 0.162 | Weak and unstable |
| RUSH1 with own DST | 0.139 / 0.019 | The classic "blowout stack". Present in 2024, absent in 2025. Joint-tail lift 1.381 and 0.891, also unstable |
| PC1 with PC2, no quarterback | -0.024 / 0.120, tail lift 0.947 both seasons | Provides no joint-ceiling benefit. Should not be treated as a stack at all |
| Two rushers, same team | -0.121 / -0.104, tail lift 0.578 / 0.996 | Actively harmful as a ceiling structure |

`STATAtl`, writing at [One Week Season](https://oneweekseason.com/late-swap-article/), explicitly includes "lower-owned players, mini-correlations, and one-offs" in a late-swap evaluation checklist, which is direct evidence that the concept is used in practice by someone playing 10 to 20 rosters on main slates. `PRO_STATEMENT`.

The measurement supports a narrower conclusion than the industry's use of the term. Of the commonly named mini-correlations, only `PC3 with RUSH1` is both positive and stable across both seasons, and its most likely mechanism is game volume rather than anything structural. The two-receiver secondary stack and the running-back-plus-defense stack do not survive measurement. `SYNTHESIS`.

## Part 6: Negative correlation tolerance

The rule "never play negatively correlated players" is wrong, and the measurements show precisely why and precisely where it is right.

`SYNTHESIS`. Three distinct cases:

**Case 1: negative correlation that destroys the structure.** QB with opposing DST, measured at -0.375 and -0.371 with a joint-tail lift of 0.373 and 0.471. This is the strongest relationship in the entire panel, stronger in magnitude than QB with PC1, and it is negative in every tercile. A lineup containing a quarterback and the defense facing him has purchased two assets whose joint large outcome is roughly a third to a half as likely as independence would suggest. In a top-heavy tournament, where only the joint tail is paid, this is close to a structural veto. `MEASURED_HERE`.

**Case 2: negative correlation that is acceptable because it is not in the payout-relevant tail.** RUSH1 with RUSH2 has a Pearson coefficient of -0.121 and -0.104, but the 2025 joint-tail lift is 0.996, essentially independent. The negative relationship lives in the middle of the distribution, where the two backs trade carries, and largely disappears in the tail, where a high-scoring offense can support two productive backs. Rostering two backs from one team is a mediocre structure, not a forbidden one. `MEASURED_HERE`.

**Case 3: negative correlation that is deliberately desirable.** Two independent or mildly opposed blocks in a large portfolio reduce the portfolio's variance without reducing any individual lineup's ceiling. A 150-entry portfolio wants its lineups to be as close to independent of each other as the player pool permits, because the objective is \( P(\text{at least one entry wins}) \) rather than the expected score of the average entry. Negative correlation **across** lineups is the goal; negative correlation **within** a lineup is usually a cost. `SYNTHESIS`, with the mathematical basis in [Hunter, Vielma, and Zaman](https://arxiv.org/abs/1604.01455), whose formulation explicitly maximizes the expected score of an entry subject to a lower bound on its variance and an upper bound on its correlation with previously constructed entries.

The operational rule that follows is not a prohibition but a hierarchy, `SYNTHESIS`:

1. Never pair a quarterback with the defense facing him, on either site.
2. Avoid pairing any offensive player with the defense facing him; team offense with opposing DST measures -0.347 and -0.391.
3. Tolerate within-team volume-pool negatives when the marginal projection justifies them, because they are much weaker in the tail than in the middle.
4. Seek negative correlation between lineups in a multi-entry portfolio.
5. Treat own-team defense pairings as approximately neutral rather than as either a positive stack or a negative: QB with own DST measures -0.030 and -0.107, with a joint-tail lift of 0.839 and 0.828.

Point 5 is a disagreement with widely repeated guidance in both directions. DFS Degen states QB with own DST at approximately -0.3, which the measurement does not support. 4for4 reports RB1 with own DST as a mild positive, which 2024 supports at 0.139 and 2025 does not at 0.019. The honest reading is that the own-defense relationships are weak and year-unstable, and should be represented with wide uncertainty rather than a point estimate. `SYNTHESIS`.

## Part 7: Ownership and leverage

### 7.1 The decomposition

The commonly stated frame is Projection times Ownership times Correlation times Duplication. That product form is a mnemonic rather than a computation, and treating it as a formula is one of the failure modes in Part 23. The quantity that a tournament actually pays is `SYNTHESIS`:

\[ \text{EV}(\ell) = \sum_{w} P(w) \cdot \frac{\text{Payout}(\text{rank}(\ell, w))}{\text{Copies}(\ell, w)} \]

where \( w \) indexes simulated football worlds, \( \text{rank}(\ell, w) \) is the lineup's rank against a simulated field in world \( w \), and \( \text{Copies} \) is the number of duplicate entries sharing the payout. Projection enters through \( P(w) \) and the lineup's score. Correlation enters through the joint distribution over \( w \). Ownership enters only through the simulated field, and duplication only through \( \text{Copies} \). None of the four is a multiplicative factor on the others, and none of them except projection has any football content.

That distinction is the project's standing constraint restated: ownership is a property of the opponent population, not of football. It belongs in the field model and nowhere upstream of it.

### 7.2 Is ownership predictable?

`PRO_STATEMENT`. Jonathan Bales, in [a FantasyLabs article on ownership projection accuracy](https://www.fantasylabs.com/articles/bales-look-fantasylabs-nfl-ownership-projection-accuracy/), compared projected and actual ownership across all positions on DraftKings and FanDuel for the 2016 season, in the Millionaire Maker and Sunday Million, and states the projections were "on point." He presents this as evidence that predicting ownership is easier than forecasting on-field performance.

That claim is plausible on mechanism grounds and unverifiable as stated: the article is from October 2016, reports no error metric, and describes its own product. `SYNTHESIS`. The mechanism argument is sound, though, and is worth stating independently: ownership is a prediction about a large population of humans responding to widely shared public information, which has far more autocorrelation and far less irreducible noise than a football outcome. Treat "ownership is more predictable than production" as a well-motivated `HYPOTHESIS` with a specified test in Part 22, not as an established result.

### 7.3 Leverage is a property of structures, not of players

`INDUSTRY_CONVENTION`. [Stokastic's leverage and game-theory article](https://www.stokastic.com/articles/nfl-dfs/nfl-dfs-leverage-game-theory) makes the arithmetic point directly: a 40%-owned player who reaches his ceiling separates the roster from only 60% of the field, while an 8%-owned player who does so gains on 92%. The same source states that "the richest leverage is not a single low-owned name; it is a low-owned stack."

`SYNTHESIS`. The measurement in this report supports the second statement more strongly than the source does. Joint ownership of a correlated block is the product of correlated individual ownerships, which the field's own stacking conventions make far lower than naive independence would imply for unusual combinations. Stokastic's own field distribution of 45% / 25% / 5% for one, two, and three pass catchers implies that a quarterback-plus-three structure is entered by roughly one entry in twenty regardless of which quarterback it is. Stacking three pass catchers is therefore an ownership decision at least as much as a correlation decision, and the ceiling-inflation table shows the correlation component is the smaller of the two effects.

[KC Joyner, writing at RotoWire](https://www.rotowire.com/football/article/common-nfl-optimizer-mistakes-roi-125401), states that blindly maximizing projected points without factoring in ownership produces chalk-heavy lineups that win only small amounts in most contests and may return nothing in large-field GPPs, and that low-ownership leverage plays improve ROI when they hit. `PRO_STATEMENT`.

### 7.4 What leverage is not

`SYNTHESIS`. Low ownership is a necessary but not sufficient condition. [SimSlate's dupe calculator documentation](https://simslate.com/tools/dupe-calculator/) states explicitly that popularity alone does not determine whether leverage is worth it. A player is low-owned for reasons, and those reasons are usually partly correct. A leverage play is only a leverage play when the football model's own distribution disagrees with the field's implied distribution. If the football model agrees with the field, low ownership is simply a worse player.

The clean formulation, `SYNTHESIS`: leverage requires a measurable gap between the model's implied probability that a player finishes in a payout-relevant outcome band, and the field's ownership of that player. Ownership alone is one half of a ratio.

## Part 8: Duplication and uniqueness

### 8.1 Duplication is quantitatively large

The best quantified duplication evidence available is from golf rather than football, and its external validity must be flagged rather than assumed.

`QUANT_EXTERNAL`, golf. [Dan Back at RotoGrinders](https://rotogrinders.com/articles/draftkings-milly-maker-strategy-avoiding-lineup-duplication-748722) reports a single roster duplicated 122 times in one event and 121 in another, with almost 30% of lineups duplicated when $0 salary remained, and gives an example of a duplicated winner receiving $8,196 instead of $1 million.

`QUANT_EXTERNAL`, golf. [A RotoGrinders Masters lineup analysis by @nicks523](https://rotogrinders.com/articles/draftkings-milly-maker-masters-lineup-analysis-1258937) reports 205,732 entries against 229,885 theoretically possible lineups, of which only 149,657 were unique, giving 72.7% uniqueness. It reports 73,321 users averaging 2.8 lineups and $56, with 80 users at the 200-lineup maximum, and a second-most-used lineup entered 162 times. Most importantly, it reports that lineups spending all available salary had a 65.5% chance of uniqueness against 89% to 98% when leaving $500 to $1,000 unspent, and that 8 of the top 10 most-used lineups spent the entire $50,000.

Why golf does not transfer directly, `SYNTHESIS`: golf DFS has six roster slots drawn from a field of roughly 150 with no positional structure, no team constraints, and no correlation structure worth modeling. NFL Classic has nine slots across five position groups drawn from roughly 400 to 500 rostered players, with a FLEX slot and site-specific team constraints. The combinatorial space is orders of magnitude larger, so the base duplication rate must be much lower. The **mechanism** transfers, and the direction of the salary finding almost certainly transfers, but the magnitudes do not. The 72.7% uniqueness figure should never be quoted as an NFL number.

`PRO_STATEMENT`. [Justin Van Zuiden at RotoGrinders](https://rotogrinders.com/lessons/how-much-salary-can-we-leave-on-the-table-2709704), writing in 2018 in an NBA frame and citing Dan Back's golf data, reports that 54% of Masters lineups and 53% of U.S. Open lineups had $100 or less remaining, and roughly 75% had $500 or less, so leaving $600 or more competes with only about 25% of the field. He explicitly states there is "no rigid requirement here, especially in tournament formats."

### 8.2 Duplication metrics in commercial products

`INDUSTRY_CONVENTION`. [SimSlate's dupe calculator](https://simslate.com/tools/dupe-calculator/) takes nine ownership percentages, computes joint ownership, and reports expected copies, probability of uniqueness, expected first-place share, and a "dupe tax." It states calibration against a simulated 10,000-lineup field, while the full simulator builds a 50,000-lineup field and plays the tournament 50,000 times with correlated non-normal outcomes, ranking lineups by expected ROI including the dupe tax.

`INDUSTRY_CONVENTION`. [DFS Hero's DupeChance glossary entry](https://dfshero.com/help/glossary/dupechance) defines the metric as the likelihood that a lineup will be duplicated at least five times in a contest, with 100% or higher indicating a popular lineup subject to chopped payouts, and below 100% indicating relative uniqueness. The page notes the metric is particularly relevant in Showdown or small-slate contests and names no author.

### 8.3 The independence baseline and why it is wrong

`SYNTHESIS`. The naive expected-copies estimate multiplies the nine ownership percentages and scales by field size:

\[ E[\text{copies}] \approx N \cdot \prod_{i=1}^{9} o_i \]

This is wrong in both directions and the errors do not cancel. It understates duplication because opponent lineups are not independent draws over players: the field's own stacking conventions, salary-efficiency heuristics, and shared projection sources make certain combinations vastly more likely than the product of marginals. It overstates duplication for structurally unusual combinations, because the product form assigns positive probability to combinations that no realistic field-building process would generate.

The correct object is a generative field model that produces whole lineups, discussed in Part 14. Expected copies is then read off the simulated field directly. `SYNTHESIS`.

### 8.4 Salary as a duplication lever

`SYNTHESIS` from golf `QUANT_EXTERNAL`. The uniqueness gain from leaving salary unspent is the most actionable duplication finding available, and it is also the one most likely to be misapplied. The correct framing is a tradeoff with an explicit price: leaving \( \$s \) unspent costs roughly \( s \times \) (marginal points per dollar at the relevant salary tier) in expected score, and buys a measurable increase in the probability of not sharing the payout. That tradeoff is contest-specific. In a top-heavy large-field GPP where first place pays 20% to 30% of the prize pool, the uniqueness purchase is likely worth it. In a double-up where payouts are flat and duplication is irrelevant, it is pure cost.

The mechanism by which leaving salary helps is worth stating, because it is not obvious: salary-maximizing lineups cluster because the salary constraint is nearly binding at the optimum and the set of lineups that exactly exhaust the cap while remaining near-optimal is small. Deliberately under-spending moves a lineup off that ridge into a sparser region. `SYNTHESIS`.

## Part 9: Salary allocation

`SYNTHESIS` throughout, with cited anchors.

The two sites are not comparable in dollar terms and must be compared as a share of cap. [Stokastic's DraftKings-versus-FanDuel article](https://www.stokastic.com/articles/nfl-dfs/draftkings-vs-fanduel-nfl-dfs), authored by Jake Hari on 2026-07-15, notes that a $9,000 DraftKings player consumes 18% of the $50,000 cap, and that the DraftKings 3-point bonus is worth roughly 30 receiving yards. `PRO_STATEMENT` for the framing, arithmetic verifiable from `PRIMARY_RULE`.

Structural facts that constrain allocation:

- Both sites have nine slots. Average salary per slot is $5,555 on DraftKings and $6,666 on FanDuel.
- DST is the cheapest slot on both sites and the slot with the lowest projection-to-salary information content, since DST outcomes are dominated by turnover and return-touchdown events that are close to unforecastable at the game level.
- Both sites have identical 100-yard and 300-yard bonuses, which means both have a scoring nonlinearity at the same place. A player whose distribution straddles 100 receiving yards has a discontinuous jump in his scoring function, which increases his variance relative to his mean and makes him disproportionately valuable in tournaments. This is a genuine scoring-adapter concern, not a heuristic.
- FanDuel's half-point reception compresses the value of high-volume, low-yardage receivers relative to DraftKings. A slot receiver projected for 8 receptions and 55 yards is worth 13.5 DraftKings points and 9.5 FanDuel points from the same line, a 30% reduction, whereas a deep threat projected for 3 receptions and 75 yards is worth 10.5 and 9.0, a 14% reduction. That differential is computable exactly from `PRIMARY_RULE` and should be applied mechanically rather than as a heuristic.

Allocation approaches, with assessment:

| Approach | Description | Assessment |
|---|---|---|
| Stars and scrubs | Two or three maximum-salary players plus minimum-salary fillers | A variance-increasing structure, not a value-finding one. Defensible in large-field GPPs only, and only when the minimum-salary players have genuine role uncertainty in the model's favor |
| Balanced | Every slot near the average | Appropriate in cash games. In tournaments it tends to produce the modal lineup and therefore the highest duplication |
| Leave salary unspent | Deliberate under-spend for uniqueness | Supported in direction by golf data; contest-dependent in size; see Part 8.4 |
| Points-per-dollar maximization | Rank by projection divided by salary | A trap. It systematically overweights minimum-salary players whose projections are small, because the ratio is scale-dependent. The correct object is the constrained optimum, which an integer program finds directly |

## Part 10: Positional strategy

### Quarterback

`SYNTHESIS`. The quarterback is the only slot whose choice determines the lineup's correlation structure, because the quarterback is the hub of every same-team stack that measures positive. The decision is therefore not "which quarterback scores most" but "which game environment and which stack." Exposure caps in the 20% range are `INDUSTRY_CONVENTION` from Stokastic and are consistent with Alex Baker's `PRO_STATEMENT` cap of 5 lineups per quarterback across roughly 25 entries, which is 20%.

### Running back

`MEASURED_HERE`. Running backs are the weakest correlation partners measured. QB with RUSH1 is 0.109 and 0.050, and turns negative in high-scoring games in 2025 at -0.101. RUSH1 with RUSH2 is negative. RUSH1 with own DST is unstable across seasons. The running-back slot is therefore best treated as a marginal-projection decision with almost no correlation content, which is a simplification rather than a limitation: it means running-back selection can be delegated almost entirely to the football model.

The one structural exception, `SYNTHESIS`: because RUSH1 with opposing DST measures -0.294 and -0.250, a running back is a meaningful negative against the defense facing him, and a lead back on a team expected to be blown out is a compounding negative through the score-state channel.

### Wide receiver and pass catchers generally

`MEASURED_HERE`. Three of the nine DraftKings slots are receiver slots and the FLEX is usually a fourth pass catcher, so pass catchers dominate the roster and therefore dominate correlation structure. The measurement says: pair them with their quarterback, do not pair two of them without their quarterback, and prefer a cross-team pass-catcher pair over a quarterback-to-opposing-pass-catcher pair when building game exposure.

### Tight end

`UNKNOWN` in this engagement's measurement. Tight ends cannot be separated from wide receivers in the available play-by-play, because it carries no position field and the only archived depth-chart file is a single undated-by-week snapshot. Every tight-end-specific correlation claim in the literature is therefore unevaluated here, and that gap should be closed before any tight-end-specific rule enters the system.

External guidance, `INDUSTRY_CONVENTION`. [Stokastic's tight end strategy article](https://www.stokastic.com/articles/nfl-dfs/nfl-dfs-tight-end-strategy) states that cash games want an every-down tight end with high target share and high route participation whose reception count holds "almost regardless of game script," while tournaments want ceiling and leverage through a red-zone specialist the field has faded, a punt tight end in a strong matchup at low ownership, or an elite tight end whose matchup is a genuine outlier. It identifies implied team total as the key game-environment input, contrasting an offense implied for 27 points against one implied for 17, and offers a hypothetical punt tight end at 11.4 projected points and 6% ownership against a chalk elite tight end at 34%.

That guidance uses market-implied team totals, which project constraints prohibit as predictive inputs. The football model's own team-scoring distribution is the permitted substitute and should replace implied total wherever this kind of reasoning is encoded. `SYNTHESIS`.

### Defense and special teams

`INDUSTRY_CONVENTION`. [Stokastic's defense strategy article](https://www.stokastic.com/articles/nfl-dfs/nfl-dfs-defense-strategy), dated 2026-07-19, states that in cash games DST is "a pure floor-and-value decision," selecting the cheapest defense facing an opponent implied under 18 points with a favorable offensive-line matchup and spending the savings on a higher-floor skill player. In tournaments it treats DST as a leverage tool, pivoting to a low-owned defense in an equally good matchup. Its stated ideal profile is "a cheap defense across from the lowest implied team total on the slate, attacking a bad line, with its own team favored." It gives opponent-implied-total bands: under approximately 18 is a prime spot, 18 to 21 is playable, 21 to 24 is marginal, and over 24 should be avoided.

`MEASURED_HERE`. The measurement adds three things that guidance does not. First, QB with opposing DST at -0.375 and -0.371 is the strongest relationship in the panel, which makes the DST slot a hard constraint on the rest of the lineup rather than an independent value pick. Second, own DST with opposing DST at -0.229 and -0.248 means a DST is also a negative against the opposing DST, so DST-versus-DST pairings in a portfolio are naturally diversifying. Third, QB with own DST at -0.030 and -0.107 with a joint-tail lift of 0.839 and 0.828 means pairing a quarterback with his own defense is mildly bad in the tail, contradicting neither a "stack your own defense" nor an "avoid your own defense" heuristic strongly enough to justify either as a rule.

Again, the implied-total machinery in the external guidance must be replaced with model-derived team-scoring distributions to satisfy project constraints. `SYNTHESIS`.

## Part 11: Cash games versus tournaments

These are different optimization problems and mixing their principles is a category error.

| Dimension | Cash games | Large-field GPP |
|---|---|---|
| Objective | Maximize \( P(\text{score} > \text{cash line}) \) | Maximize \( P(\text{at least one entry finishes in the top payout tiers}) \), net of duplication |
| Payout shape | Approximately binary at roughly 50% of the field, per Levitan | Top-heavy; [Fantasy Alarm's DraftKings-versus-FanDuel guide](https://www.fantasyalarm.com/articles/nfl/fantasy-football-draft-guide/2026-draftkings-vs-fanduel-dfs-strategy-guide/191484) describes top-heavy structures as paying 20% to 30% to first |
| Correlation | Optional and mildly harmful, because stacking raises variance | Required, because only the joint tail is paid |
| Ownership | Irrelevant. Levitan's `PRO_STATEMENT` cash-lineup instruction is explicit that ownership is not a consideration | Central |
| Duplication | Irrelevant, because payouts are flat | Central |
| Salary | Spend it all; there is no uniqueness benefit | A tradeable lever |
| Right statistical target | Median and floor | Upper quantiles and joint tails |

`PRO_STATEMENT`. Adam Levitan, in the [2022 ETR DFS Strategy Guide](https://cdn.establishtherun.com/wp-content/uploads/2022/09/23110421/2022-DFS-Strategy-Guide.pdf), defines cash games as contests paying roughly 50% of the field, naming head-to-heads, double-ups, and 50/50s, and prescribes a single cash lineup built without ownership as a consideration.

`SYNTHESIS`. The measured ceiling-inflation table is a cash-game argument against stacking as much as it is a tournament argument for it. A structure that raises the 95th percentile by 5% to 8% necessarily raises variance, which lowers \( P(\text{score} > \text{median-ish cash line}) \) for a fixed mean. The same number is a benefit in one contest type and a cost in the other.

## Part 12: Contest size and entry limits

`PRO_STATEMENT`. Levitan's stated position in the ETR guide is that game selection is the easiest and fastest way to increase ROI and, in his view, the most important factor in DFS success, to which he devoted roughly half a book. He states that "at least 90%" of NFL DFS analysis is about picking players and that almost all of it ignores game selection. His prescribed priorities are the smallest available rake, understanding field size and adjusting lineups for it, examining the payout structure, and finding the softest opponents. He recommends adding cash games, smaller-field tournaments, and weekly contest identification while often avoiding lottery-style extreme large-field GPPs, and notes that playing an entire bankroll in the DraftKings Millionaire Maker every week is difficult to sustain.

His published $100 weekly DraftKings portfolio is concrete and worth recording exactly, `PRO_STATEMENT`: one cash lineup built without regard to ownership; twenty large-field tournament lineups that should be correlated with thoughtful leverage; one single-entry medium-field lineup; three 3-max medium-field lineups. Those are entered as $15 across three 3-max entries in the $5 Nickel at 11,890 entries with 15.9% rake and a minimum cash of 2x, $9 across the $3 Triple Option at 15,854 entries, $20 across twenty entries in the $1 First Down at 297,265 entries and a 20-max limit which he describes as a soft tournament and practice for the Millionaire Maker, and $12 on a single entry in the smaller $12 Fair Catch at 4,901 entries where leverage is created against the field.

`SYNTHESIS`. Two things in that portfolio are more informative than its specific contests. First, rake is quoted as a first-class selection criterion at 15.9%, which is a direct deduction from expected ROI and dwarfs most construction edges. Second, the majority of entries by count go into the largest, softest, cheapest contest, while the majority of thought per entry goes into the single-entry contest. That is a rational allocation of a scarce resource and is itself a strategic statement.

### Contest tiers

`INDUSTRY_CONVENTION`. [Fantasy Alarm's 2026 DraftKings-versus-FanDuel guide](https://www.fantasyalarm.com/articles/nfl/fantasy-football-draft-guide/2026-draftkings-vs-fanduel-dfs-strategy-guide/191484), whose author is not named on the page, defines large-field GPPs as 10,000 to more than 100,000 entries with huge prizes, tiny win odds, and soft fields at $5 to $20 buy-ins; mid-field as 1,000 to 10,000 entries with $50,000 to $250,000 prizes against a mixed field; and small-field as 100 to 1,000 entries with better win odds, $10,000 to $50,000 prizes, and a sharper field. It states a preference for single-entry mid-field GPPs in the 2,000 to 5,000-entry range, recommends spreading entries across 2 to 4 GPPs per week, says large fields require maximum differentiation while small fields reward precision over wild differentiation, describes a $5 GPP at around 10% rake as about as good as it gets, and recommends avoiding lobbies crowded with max-entry sharks.

### Strategy by entry limit

| Format | Objective | Key structural implication |
|---|---|---|
| Single-entry | Maximize \( P(\text{this lineup wins}) \) | Score and uniqueness are optimized jointly in one object, not traded off across a portfolio |
| 3-max | Three near-independent shots | Overlap between the three entries is the binding cost. Three lineups sharing seven players is effectively one entry |
| 20-max | Portfolio behavior begins | Per-player and per-stack exposure caps become the primary control surface |
| 150-max | Full portfolio optimization | The objective is a set-level submodular function, not a sum of individual lineup values |
| Small-field, under 1,000 | Sharper opponents, flatter payouts | Differentiation for its own sake is negative expected value; precision dominates |
| Massive-field, over 100,000 | Duplication and extreme tails dominate | The payout is effectively \( P(\text{perfect-ish week}) \); structural uniqueness matters more than marginal projection accuracy |

`INDUSTRY_CONVENTION`. [Stokastic's single-entry GPP article](https://www.stokastic.com/articles/nfl-dfs/single-entry-gpp-strategy-nfl) states that single-entry play optimizes score and uniqueness together whereas multi-entry play optimizes exposure percentages, gives an example of a chalk quarterback at approximately 45% ownership against a pivot at approximately 5%, and asserts that single-entry fields are softer than max-entry fields.

`PRO_STATEMENT`. KC Joyner at RotoWire states that more lineups do not automatically mean more profit, that many players over-enter slates relative to bankroll, that over-entering spreads assets too thinly across low-conviction lineups and can crush profit potential, and that entry volume should be adjusted relative to bankroll size. Jake Letarski, in the same RotoWire article, states that the default optimizer lineup is only a starting point, that a player should at minimum make one switch or build around one stack to become unique, and that entering the default lineup verbatim will likely result in shared winnings even if it wins.
## Part 13: Portfolio construction for multi-entry

The central claim, and it is correct: 150 individually optimal lineups are not an optimal 150-lineup portfolio.

`QUANT_EXTERNAL`. [Hunter, Vielma, and Zaman](https://arxiv.org/abs/1604.01455) formalize exactly this. For contests with top-heavy payoff structures the relevant objective is the probability that at least one entry wins. They state that this objective is submodular and can be approximated using pairwise marginal probabilities under a certain structure on the joint distribution, and that their integer-programming formulation maximizes the expected score of an entry subject to a lower bound on its variance and an upper bound on its correlation with previously constructed entries.

Three consequences follow directly and are the mathematical backbone of this part. `SYNTHESIS`:

1. **Submodularity means greedy sequential construction has a provable quality guarantee.** The marginal value of adding a lineup to a portfolio decreases as the portfolio grows. A portfolio built one lineup at a time, each time adding the lineup with the highest marginal contribution to \( P(\text{at least one wins}) \), is a principled algorithm rather than a heuristic.
2. **The per-lineup constraint set is not just "be good."** It is "be good, be volatile enough, and be sufficiently decorrelated from what is already in the portfolio." The variance lower bound is the part most often omitted in practice, and omitting it produces a portfolio of high-mean low-variance lineups that collectively cannot win a top-heavy contest.
3. **Pairwise lineup correlation is the tractable proxy for portfolio-level dependence.** Exact set-level joint probabilities are intractable for 150 lineups; the paper's pairwise approximation is the practical route.

`QUANT_EXTERNAL`. [Management Science, "How to Play Fantasy Sports Strategically (and Win)"](https://pubsonline.informs.org/doi/10.1287/mnsc.2019.3528) develops a risk-neutral formulation maximizing expected reward subject to feasibility, treats double-up and top-heavy settings separately, relates the problem to mean-variance optimization and to outperformance of stochastic benchmarks, and reduces it to a series of binary quadratic programs. Its multiple-entry algorithm is motivated by the submodularity of the objective and by results from parimutuel betting. Critically for Part 14, it models opponents' team selections with a Dirichlet-multinomial data-generating process whose parameters are estimated by Dirichlet regressions. It also estimates the value of insider trading and collusion.

`QUANT_EXTERNAL`. [Sarah Newell's Kansas State thesis, advised by Todd W. Easton, May 2017](https://krex.k-state.edu/items/e723f351-6128-4bfc-929e-1022641d65c6) presents MMIP, a stochastic integer program claimed to be the first model to optimize the expected payout of a tiered DFS contest. It assumes normally distributed player performance and therefore normal team totals, approximates team standard deviation with a piecewise linear function, and computes cumulative payout probabilities. It concludes that DFS is not a game of chance.

The normality assumption is the reason that thesis should be read for its formulation and not adopted for its distributions. `SYNTHESIS`. [SimSlate's published methodology](https://simslate.com/methodology/) states the opposite position explicitly, fitting a right-skewed shifted lognormal per player simultaneously to mean, standard deviation, ceiling, boom probability, and bust probability, capping tails at realistic NFL maxima, and asserting that "no player is normal." It imposes correlations through a Gaussian copula in latent normal space kept positive semi-definite, and calibrates boom and bust thresholds position by position from slate data rather than using a fixed 5x-salary rule.

### Practical portfolio controls

`INDUSTRY_CONVENTION` and `PRO_STATEMENT`, assembled:

| Control | Value cited | Source |
|---|---|---|
| Quarterback exposure cap | approximately 20% | Stokastic, `INDUSTRY_CONVENTION` |
| DST exposure cap | 10% to 20% | Stokastic, `INDUSTRY_CONVENTION` |
| Lineups per quarterback | 5 of approximately 25 entries, so 20% | Alex Baker, `PRO_STATEMENT` |
| Entry count | 10 to 20 rosters on the main slate | STATAtl, `PRO_STATEMENT` |
| Entry count | approximately 25, deliberately not the maximum | Alex Baker, `PRO_STATEMENT` |
| Week-5 stack allocation | 38.4% on one quarterback and team stack across 14 rosters | STATAtl, `PRO_STATEMENT` |
| Entries per week | spread across 2 to 4 GPPs | Fantasy Alarm, `INDUSTRY_CONVENTION` |
| Volume warning | over-entering relative to bankroll crushes profit potential | KC Joyner, `PRO_STATEMENT` |

`SYNTHESIS`. Note the internal disagreement in that table. Stokastic's stated 20% quarterback cap and Alex Baker's 20% are consistent, but STATAtl's reported 38.4% single-quarterback allocation across 14 rosters is nearly double it. Both are direct statements from people who play. The reconciliation is probably portfolio size: with 14 entries the granularity is coarse and the field-overlap cost of concentration is lower than with 150. Exposure caps should therefore scale with portfolio size rather than being a fixed percentage, which is a testable proposition rather than an established one.

## Part 14: Field modeling

### 14.1 Player-ownership model against full-lineup field model

`SYNTHESIS`. These are not two levels of effort at the same task; they answer different questions.

A player-ownership model predicts marginal ownership \( o_i \) for each player. It is sufficient to compute the leverage of an individual player and nothing else. It cannot compute duplication, cannot compute the probability that a specific lineup beats a specific number of opponents, and cannot represent the fact that the field's lineups are internally correlated.

A full-lineup field model generates \( N \) complete opponent lineups. From it, everything else follows mechanically: marginal ownership is a summary statistic of the generated field, expected duplicates is a count, and the rank of a candidate lineup in any simulated football world is a sort. A contest simulator without a lineup-level field model is not simulating a contest.

`INDUSTRY_CONVENTION`. SimSlate states it builds a 50,000-lineup field and plays the tournament 50,000 times, with its dupe calculator calibrated against a 10,000-lineup simulated field. [Stokastic's contest simulator](https://www.stokastic.com/articles/nfl-dfs/nfl-dfs-contest-simulator) describes a base package of 500 lineups and a top 10,000, simulating tens of thousands of contests and ranking by simulated ROI, with a percent-to-first selector of approximately 5% to 10% for double-ups and 20% to 30% for top-heavy contests.

### 14.2 How to generate a realistic field

`SYNTHESIS`, informed by the Management Science Dirichlet-multinomial approach.

The field is not a random draw over legal lineups. It is the output of thousands of people running a small number of similar processes on a small number of shared projection sources. A credible generative model therefore needs at least the following components:

1. **A marginal ownership target per player**, calibrated so the generated field reproduces it.
2. **A stack-structure prior** matching observed field structure. Stokastic's stated 45% / 25% / 5% / 25% split across quarterback-plus-one, quarterback-plus-two, quarterback-plus-three, and no-stack is the best publicly available anchor, with roughly 25% including a bring-back.
3. **A salary-usage distribution.** The golf data indicates the field concentrates heavily near the cap, and the same pressure exists in NFL. The generated field should reproduce a salary-remaining distribution, not spend uniformly.
4. **An entrant-heterogeneity structure.** Golf data shows 73,321 users averaging 2.8 lineups with 80 users at the 200 maximum. A field that treats every entry as an independent draw from one process will understate duplication among casual entries and understate structural diversity among max-entry portfolios. Entries should be generated per simulated entrant with a per-entrant portfolio process.
5. **A correlated-choice mechanism.** The Dirichlet-multinomial specification in Management Science is the cleanest published option, because it produces overdispersed, correlated selections rather than independent multinomial draws.

### 14.3 Validation of a field model

`SYNTHESIS`. A field model is validated against realized contest data, not against intuition. The observable quantities are post-contest ownership percentages, which operators publish, and post-contest lineup data where available. The checks are: calibration of marginal ownership, calibration of the salary-remaining distribution, calibration of stack-structure frequencies, and calibration of the duplication distribution including its upper tail. The duplication tail is the hardest and most important: a field model that matches mean duplicates but understates the maximum duplicate count will systematically mis-price the most popular lineups, which are exactly the ones a naive optimizer wants to build.

## Part 15: Contest simulation

### 15.1 The structure

`SYNTHESIS`. A correct contest simulation has a strict ordering that must not be shortcut:

1. Simulate \( W \) correlated football worlds from the football model. A world is a complete set of player stat lines for every player on the slate, jointly drawn with the correct dependence.
2. Map each world through the site's scoring adapter to fantasy points. Two adapters, one per site, over the same worlds.
3. Score the generated field's lineups and the candidate lineups in each world.
4. Rank, apply the payout table, divide by duplicate count.
5. Average over worlds to get expected payout per entry, and over the portfolio to get portfolio expected payout and \( P(\text{at least one entry in the top tier}) \).

Step 1 must be joint across the whole slate, not per game. Team offense with opposing offense measures +0.083 and +0.186, and the prior second-opinion work in this project found the repository's sealed simulation produced a club-versus-opponent offensive correlation of **-0.128** where archived play-by-play gives **+0.1201** for 2024 and **+0.2034** for 2025 across 272 games each, a sign error. The new panel independently reproduces the positive real-world value. Club-with-game-total was 0.7592 and 0.7572 in the real data against 0.6502 in the simulation. Any contest simulation built on a world generator with that sign error will systematically misprice every game stack and every bring-back on the slate.

### 15.2 Do simulations actually work? The only honest external test found

`QUANT_EXTERNAL`, and unusually candid. [Establish The Run's "Putting the Sims to the Test"](https://establishtherun.com/nfl-dfs-putting-the-sims-to-the-test/) evaluates Game Changer single-entry contests at a $1,500 buy-in with approximately 275 entrants, paying just under 22% of the field with a minimum payout of $2,500, over a 35-contest sample. Reported results: the average lineup had a simulated ROI of -5.3% purely from rake, and 60% of lineups simulated negative. Contest winners averaged +9.0% simulated ROI, and 23 of 35 winners, or 65.7%, had positive simulated ROI, which the author frames as 1.65 times random expectation. The author's own realized ROI over 22 entries was -57.6%, specifically $33,000 staked against $14,000 returned.

The article states its own limitations: the simulations do not account for wrong mean projections, post-lock projection changes, or late-swap dynamics.

`SYNTHESIS`. This is the most useful single external result in the entire literature reviewed, for three reasons. First, it is a genuine out-of-sample test with a stated sample size and a stated negative personal result, which is rare in this content category. Second, 1.65 times random expectation is a real but modest signal, consistent with simulation adding value at the margin rather than transforming expectation. Third, the -57.6% realized ROI against a positive simulated edge over 22 entries is a direct demonstration that 22 entries in a 275-entrant top-heavy contest is nowhere near enough sample to distinguish skill from noise. Any internal evaluation of this project's own portfolio output must account for that: the variance of realized DFS ROI is so large that a season of results is a weak test of a construction method, and the primary validation must be at the component level rather than at the bankroll level.

### 15.3 What number of worlds and lineups is enough

`SYNTHESIS`. Commercial anchors are 50,000 worlds and a 50,000-lineup field at SimSlate, and tens of thousands of contests with a 500-lineup base at Stokastic. The binding consideration is not the world count but the resolution required in the payout tail. To estimate \( P(\text{first place}) \) in a 100,000-entry contest to within a useful relative error, the number of worlds must be large enough that the candidate lineup finishes first in a countable number of them. This is the argument for importance sampling over brute-force simulation in massive-field contests, and it should be treated as an engineering requirement rather than an optimization.

## Part 16: Late swap

`PRIMARY_RULE` for the mechanics, in Part 1. The strategic content follows.

`INDUSTRY_CONVENTION`. [Stokastic's late-swap article](https://www.stokastic.com/articles/nfl-dfs/nfl-dfs-late-swap) frames the decision as comparing the locked score plus the median projection for open slots against the pace needed to reach a target finish, and describes a "two-way lever": chase leverage when behind, bank safety when ahead. It also asserts that most opponents set lineups Sunday morning and never edit.

`PRO_STATEMENT`. STATAtl at [One Week Season](https://oneweekseason.com/late-swap-article/) gives a concrete procedure used on 10 to 20 main-slate rosters. He opens any large-field GPP within the first 30 minutes of lock, approximately 1:30 pm for a 1 pm start, and evaluates: how the field is doing; how the early games played out as a whole; how the highest-owned plays performed; whether the highest-owned early-game stack hit; the ownership of the 2 to 3 highest-scoring players; whether he rostered those players; whether he played an early-game stack; whether his rostered players are on pace for 4x; and how lower-owned players, mini-correlations, and one-offs performed. When a roster is performing well he recommends considering a pivot from a lower-owned late-game play to a chalky late-game play, explicitly in order to block players likely to score well. When behind, he recommends a lower-owned late-game stack or a direct leverage play away from a highly owned play. His documented examples include a 10,000-entry $12 single-entry contest where a roster finished 21st, 11 points out of first, and a 4,300-entry $27 single-entry contest that reached a minimum cash.

`SYNTHESIS`. Three points that the sources do not make explicitly.

First, the DraftKings rule that opponent lineups stay hidden until an athlete's game locks is the binding informational constraint, `PRIMARY_RULE`. Late swap is therefore not "optimize against the observed field." It is "optimize against a posterior over the field, conditioned on the observed early-game outcomes." The field model must be re-run conditionally, not replaced with observed data.

Second, the "block chalk when ahead" tactic is mathematically the correct move and is easy to state precisely: when a roster is already in a payout position, the objective shifts from maximizing its own score to minimizing the number of opponents who pass it. Rostering a highly owned late-game player moves the roster and a large fraction of the field together, which preserves relative position. This is the one case in tournament play where high ownership is actively desirable, and it is a genuine exception to every leverage principle in Part 7.

Third, late swap systematically breaks the ceiling-inflation logic of stacking. A stack whose quarterback has locked and whose pass catcher has not is no longer a correlated block for decision purposes; the quarterback's outcome is now a known constant. The correlation layer must therefore support conditioning on realized outcomes, which is a structural requirement on the simulator, not an add-on.

Fourth, and least appreciated: late-swap value is an argument for deliberately building lineups with late-game flexibility. If a portfolio's open slots are all in the 1 pm window, the late-swap option has no value. Building with a bias toward late-window players in swappable slots buys a real option whose value can be estimated by simulation. `HYPOTHESIS`, with a test in Part 22.

## Part 17: The correlation and structure table

`MEASURED_HERE` values are this engagement's ex-ante DraftKings measurements for 2024 and 2025. DraftKings and FanDuel relevance columns reflect rule-driven differences, since Section 2.3 established that correlation magnitudes differ by under 0.02 between sites.

| Pair or structure | Typical correlation sign | Football reason | DFS consequence | When useful | When harmful | DK relevance | FD relevance | Confidence |
|---|---|---|---|---|---|---|---|---|
| QB with PC1, same team | Positive, 0.368 / 0.274; tail lift 1.859 / 1.559 | Touchdown pass and reception are one event scored twice | Raises stack p95 by 4.74% / 5.80% | Any GPP; the default correlated block | Cash games, where added variance lowers the probability of clearing a flat line | Full 1-point reception amplifies pass-catcher share of the block | Half-point reception slightly reduces the pass catcher's contribution | High |
| QB with PC2, same team | Positive, 0.296 / 0.318; tail lift 1.810 / 1.721 | Same shared-event channel through a secondary target | Best marginal addition measured; raises p95 to 6.89% / 6.41% | Large-field GPPs needing differentiation | Cash games | Legal without constraint | Consumes 3 of the 4-per-team allowance with the QB | High |
| QB with PC3, same team | Positive, 0.208 / 0.259; tail lift 1.550 / 1.706 | Shared event, diluted usage | Raises p95 to 6.98% / 7.83%; large ownership differentiation | Massive-field GPPs | Anywhere duplication is not the binding cost | Legal; 4-player same-team block permitted | Exactly exhausts the 4-per-team maximum | Medium |
| QB with RUSH1, same team | Weak positive, 0.109 / 0.050; negative in high-scoring games | Game volume against a shared-play pool; shootouts are pass-heavy | Adds almost nothing; p95 inflation only 4.14% / 5.31% | Rarely; when the back is a genuine pass-catching role | When treated as a stack partner instead of a marginal-projection pick | Neutral | Neutral | Medium |
| PC1 with PC2, no QB | Approximately zero, -0.024 / 0.120; tail lift 0.947 both seasons | Shared event offset by a finite target pool | No joint-ceiling benefit at all | Never as a stack; only if both are independently the best plays | Whenever it is believed to be a stack | Neutral | Neutral | High |
| RUSH1 with RUSH2, same team | Negative, -0.121 / -0.104; tail lift 0.578 / 0.996 | Direct carry-share competition | Poor ceiling structure; the negative lives mid-distribution | Rarely; when both roles are genuinely independent | As a deliberate structure | Neutral | Neutral | Medium |
| PC3 with RUSH1, same team | Positive, 0.238 / 0.318 | Probably pure team-volume scaling of secondary usage | The strongest non-QB same-team pair measured | Secondary correlation in a portfolio needing variety | When mistaken for a shared-event relationship | Neutral | Neutral | Low; mechanism unverified |
| QB with own DST | Approximately zero, -0.030 / -0.107; tail lift 0.839 / 0.828 | Weak and mixed; own defense's stops both help field position and shorten the game | Mildly negative in the tail; effectively neutral | Not a reason either way | When used as a rule in either direction | Neutral | Neutral | Medium; contradicts published -0.3 |
| RUSH1 with own DST | Unstable, 0.139 / 0.019; tail lift 1.381 / 0.891 | Blowout script: leading teams run, trailing teams score less | The "blowout stack"; present in one season, absent in the other | Only with an explicit model-derived blowout distribution | As a standing structure | Neutral | Neutral | Low |
| QB with opposing DST | Strong negative, -0.375 / -0.371; tail lift 0.373 / 0.471; negative in every tercile | The defense scores from the quarterback's failures | Strongest relationship in the panel; near-veto in top-heavy contests | Never | Always in GPPs | Neutral | Neutral | High |
| Team offense with opposing DST | Strong negative, -0.347 / -0.391 | Same channel, aggregated | Any offensive player is a negative against the defense facing him | Never | Always in GPPs | Neutral | Neutral | High |
| RUSH1 with opposing DST | Negative, -0.294 / -0.250 | Stuffed runs generate no defensive points but no fantasy points either | Second-strongest offense-against-defense negative | Never | Always | Neutral | Neutral | High |
| Own DST with opposing DST | Negative, -0.229 / -0.248 | Both defenses cannot succeed against each other simultaneously | Naturally diversifying across a portfolio | Across lineups in a portfolio | Within one lineup, which is impossible anyway | Neutral | Neutral | Medium |
| QB with opposing QB | Positive unconditionally, 0.088 / 0.180; negative in every tercile, -0.021 to -0.204; tail lift 1.362 / 1.378 | Between-game total scoring lifts both; within a total they compete | A bet on game total, not on co-movement | Game-stack exposure in GPPs | When described as within-game co-movement | Neutral | Neutral | High for the measurement, high for the reframing |
| QB with opposing PC1 | Weak positive, 0.108 / 0.105; tail lift 0.930 / 1.072 | Game-environment only | The conventionally named bring-back is the weakest of the three cross-team options measured | Only as game exposure | When preferred to a same-team second pass catcher | Neutral | Neutral | High; contradicts the published 0.39 |
| PC1 with opposing PC1 | Weak positive, 0.094 / 0.096; tail lift 1.544 / 1.420 | Game-environment plus both benefiting from pass-heavy scripts | Strongest cross-team joint tail measured | Preferred bring-back structure | Rarely harmful; cheaper on the team-count constraint | Neutral | Helps satisfy the 3-team minimum | Medium |
| RUSH1 with opposing RUSH1 | Negative, -0.123 / -0.067 | Only one team can lead and control the clock | Weak negative; not a veto | Rarely | As a deliberate structure | Neutral | Neutral | Medium |
| Team offense with opposing offense | Positive, 0.083 / 0.186 | The game-environment latent factor itself | This is the quantity the world generator must get right | Always, as a modeling requirement | Never; a sign error here mis-prices the entire slate | Neutral | Neutral | High; independently reproduced |
| Full game stack, 4 or more players across both teams | Positive through the game-total factor | Maximum exposure to one latent variable | p95 inflation 7.66% / 6.02% for QB + PC1 + PC2 + opposing PC1 | Massive-field GPPs | Cash and small-field | 5 or more from one game legal | Legal but capped at 4 from either single team | Medium |
| QB + 4 teammates | Positive, not measured | Maximum same-team concentration | Extreme ownership differentiation | Massive-field GPPs only | Everywhere else | Legal | **Illegal** | High for the rules, `UNKNOWN` for the value |
| Role substitution, backup with injured starter | Discrete, not linear | Availability-conditional usage transfer | Cannot be represented by a Pearson coefficient at all | When the availability distribution is explicitly modeled | Whenever compressed into a static matrix | Neutral | Neutral | `UNKNOWN` in this panel |
| Any same-team pair, conditional on game total | Attenuates or flips | Conditioning removes the game-environment component | A static matrix is the wrong object | Always, as a modeling requirement | Never | Neutral | Neutral | High |

## Part 18: Professional guidance, classified

`SYNTHESIS` for every classification; the underlying claims are cited to their sources.

### Widely supported

| Claim | Support |
|---|---|
| Stack the quarterback with at least one pass catcher in GPPs | The Fantasy Footballers' 89% of winning Millionaire Maker lineups; Stokastic's stated base structure; `MEASURED_HERE` p95 inflation of 4.74% / 5.80% and tail lift of 1.859 / 1.559 |
| Never roster a quarterback with the defense facing him | `MEASURED_HERE` -0.375 / -0.371 with tail lift 0.373 / 0.471, negative in every tercile |
| Cash and tournaments are different problems | Levitan; Stokastic; `MEASURED_HERE` variance argument |
| Contest and game selection matter more than most construction decisions | Levitan's `PRO_STATEMENT` that it is the single most important factor; rake of 15.9% quoted directly |
| Ownership must enter the decision somewhere | KC Joyner; Stokastic; Jake Letarski; the ETR sim test |
| Do not enter the raw optimizer output | Jake Letarski explicitly; Stokastic's over-exposure critique of the top-projected 150 |
| Duplication meaningfully reduces realized payouts | Dan Back's 122-duplicate example and $8,196-instead-of-$1M case; the 72.7% golf uniqueness figure, with external validity flagged |
| Player outcome distributions are right-skewed, not normal | SimSlate's stated shifted-lognormal fit and "no player is normal"; the Newell thesis's normality assumption is the counterexample |

### Situational

| Claim | Condition under which it holds |
|---|---|
| Use a bring-back | Holds as game-total exposure in large-field GPPs. `MEASURED_HERE` shows it is not a clear improvement over a second same-team pass catcher at four players |
| Leave salary unspent for uniqueness | Holds in top-heavy contests where duplication is priced. Pure cost in double-ups and flat payouts |
| Play a cheap DST facing a low-scoring offense | Holds for cash games per Stokastic. In GPPs the DST choice is constrained by which quarterbacks are in the lineup |
| Cap quarterback exposure at approximately 20% | Holds for portfolios of roughly 25 or more. STATAtl's 38.4% across 14 rosters is a direct counterexample at small portfolio size |
| Block chalk when leading in late swap | Holds only when already in a payout position; inverts the standard leverage logic |
| Stars and scrubs | Holds only when the minimum-salary players have genuine model-favorable role uncertainty |
| Large-field play requires maximum differentiation | Holds per Fantasy Alarm for 10,000-plus fields; the same source says small fields reward precision instead |

### Controversial

| Claim | The disagreement |
|---|---|
| Exact QB-to-WR1 correlation magnitude | FantasyLabs data reported at 0.57 and DFS Degen at approximately 0.55 against `MEASURED_HERE` 0.368 / 0.274 ex ante and 0.420 / 0.438 with leaky realized labels. The realized-label figure is much closer to the published one, which suggests the published figures may be computed on realized labels |
| Opposing-team correlation magnitude | FantasyLabs-reported 0.38 to 0.40 for opposing WR1, WR2, TE1, and RB1, all "basically the same," against `MEASURED_HERE` 0.094 to 0.108 |
| QB with own DST | DFS Degen's approximately -0.3 against `MEASURED_HERE` -0.030 / -0.107 |
| QB with opposing DST sign | DFS Degen's approximately +0.2 against `MEASURED_HERE` -0.375 / -0.371 |
| Ceiling boost from stacking | DFS Degen's 15% to 20% at \( \rho = 0.55 \) against `MEASURED_HERE` 4.74% to 7.83% depending on structure |
| Does simulation actually add edge | ETR's own test found winners at 1.65 times random expectation on positive simulated ROI, while the author's own realized ROI was -57.6% over 22 entries |
| Optimal entry count | Levitan's 20-max-or-smaller emphasis and KC Joyner's over-entry warning against the existence of 150-max contests and the portfolio theory that justifies them |
| Exposure caps as fixed percentages | Stokastic's 20% against STATAtl's 38.4%; likely a function of portfolio size rather than a genuine disagreement |

### Probably outdated

| Claim | Why |
|---|---|
| Any correlation matrix from 2013 to 2017 | 4for4's guide is from 2018 on 2013 to 2017 data. NFL passing-rate, play-count, and pace environments have changed. The measurement here is 2024 to 2025 |
| Golf duplication percentages applied to NFL | The 72.7% uniqueness figure comes from a 229,885-lineup combinatorial space. NFL Classic's space is orders of magnitude larger |
| Ownership projection accuracy from 2016 | Bales' claim is from October 2016 with no error metric; the field, tools, and information environment have all changed |
| Fixed 5x-salary boom thresholds | SimSlate explicitly rejects this in favor of position-by-position calibration from slate data |
| Naive multiplied parlay-style independence assumptions in DFS | Superseded by copula-based approaches, per SimSlate's published method |
| Normal-distribution DFS optimization | The Newell thesis assumes normality; the skewed-marginal literature and SimSlate's method both reject it |

## Part 19: DraftKings against FanDuel

`PRO_STATEMENT`. Jake Hari at Stokastic recommends building separately for each site, and notes the 3-point DraftKings bonus is worth roughly 30 receiving yards and that a $9,000 player is 18% of the DraftKings cap.

`MEASURED_HERE`. Correlation structure is **not** a site differentiator. Every pair measured differs by under 0.02 between DraftKings and FanDuel scoring. The differentiators are, in descending order of practical impact, `SYNTHESIS`:

1. **The four-per-team maximum on FanDuel.** A hard constraint that eliminates the quarterback-plus-four structure entirely and makes the quarterback-plus-three structure exhaust a team's whole allowance. Every large-stack strategy must be re-derived for FanDuel rather than transplanted.
2. **The three-team minimum on FanDuel against the two-game minimum on DraftKings.** These are different constraint types. The FanDuel version binds on concentrated builds; the DraftKings version almost never binds on a full slate.
3. **Half-point against full-point receptions.** Reduces the value of high-volume, low-yardage pass catchers on FanDuel by roughly twice as much as it reduces the value of low-volume, high-yardage ones, computable exactly.
4. **Double fumble penalty on FanDuel.** A small but systematic penalty on high-touch roles.
5. **Cap level.** $60,000 against $50,000, which changes nothing once salary is normalized as a share of cap, but changes everything if it is not.
6. **Late-swap availability.** DraftKings publishes a standing late-swap policy with per-athlete locks 5 to 15 minutes before game time; FanDuel offers late swap on a per-contest basis, indicated by an unlocked padlock. A portfolio strategy that depends on late swap is not portable across FanDuel contests without checking the contest.

`SYNTHESIS`. The single most common site-transfer error to guard against in code is treating the FanDuel team constraints as soft preferences. They are feasibility constraints, and an optimizer that treats them as penalties will produce unenterable lineups.

## Part 20: What belongs in code, by module

`SYNTHESIS` throughout. Classification is by the requested module taxonomy.

### FOOTBALL_SIMULATOR

Responsibilities: generate \( W \) joint worlds of player stat lines for the whole slate. Owns all football content and nothing else.

- Per-player marginal distributions over stat components, right-skewed, not normal.
- A slate-level and game-level latent factor structure reproducing team offense with opposing offense at approximately +0.08 to +0.19, and reproducing the within-game competition that makes opposing quarterbacks negatively correlated at a fixed game total.
- Availability and role-substitution modeling as a discrete mechanism, upstream of the continuous distributions.
- Play-count and pace modeling, since almost every measured "correlation" is mediated through team volume.
- Score-state dynamics sufficient to reproduce the sign flip in QB with RUSH1 between low-total and high-total games.
- **Contains no DFS content whatsoever.** No salaries, no ownership, no site scoring, no contest structure.

### DFS_SCORING_ADAPTER

Responsibilities: pure deterministic function from a stat line to fantasy points, one implementation per site.

- DraftKings and FanDuel values exactly as in Part 1, sourced from the operators' own pages, with the source URL and retrieval timestamp recorded next to each constant.
- Threshold bonuses implemented as genuine step functions, not linear approximations, because the 100-yard and 300-yard steps materially affect upper quantiles.
- DST points-allowed implemented per site formula, including the DraftKings rule that only points surrendered while the DST is on the field count.
- Zero inference. This module must be exactly testable against known box scores.

### LINEUP_OPTIMIZER

Responsibilities: find lineups maximizing a specified objective subject to site feasibility.

- Site-specific feasibility: slot structure, cap, DraftKings two-game minimum, FanDuel three-team minimum and four-per-team maximum, all as hard integer-program constraints.
- Support for objectives beyond expected points: expected points subject to a variance floor and a correlation ceiling against an existing portfolio, per the Hunter, Vielma, and Zaman formulation.
- Support for explicit structural constraints: stack specifications, forced and banned pairs, salary-remaining floors.
- Deterministic and reproducible given a fixed input and seed.

### FIELD_MODEL

Responsibilities: generate a realistic population of opponent lineups.

- Per-entrant generation with an entrant-count and entries-per-entrant distribution.
- Stack-structure priors calibrated to observed field frequencies.
- Salary-remaining distribution calibrated to observed contest data.
- Correlated player-selection mechanism, with Dirichlet-multinomial as the reference specification.
- Calibration harness against published post-contest ownership.

### CONTEST_SIMULATOR

Responsibilities: play the contest.

- Payout table ingestion per contest, including the exact tier boundaries.
- Ranking with correct tie handling and duplicate-payout division.
- Importance sampling or equivalent tail resolution for massive-field contests.
- Outputs per candidate lineup: expected payout, \( P(\text{first}) \), \( P(\text{cash}) \), expected duplicates.

### PORTFOLIO_OPTIMIZER

Responsibilities: choose the set of entries.

- Greedy submodular maximization of \( P(\text{at least one entry in the target tier}) \), with pairwise lineup-correlation approximation.
- Exposure constraints per player, per stack, per game, and per quarterback, with caps that scale with portfolio size.
- Contest allocation across multiple contests with different field sizes and payout shapes.

### GOVERNANCE_VALIDATION

Responsibilities: enforce the project's own rules in code, not in documentation.

- A static check that no sportsbook price, no market-implied total, and no ownership figure appears anywhere in the dependency closure of `FOOTBALL_SIMULATOR`. This is the single most important guard in the system given the standing constraint, and it must be a test that fails the build, not a convention.
- A forward-chain check that no parameter was fit using data from a week later than the week being predicted.
- A leakage check that role labels used in correlation calibration are prediction-time labels. The measured gap between ex-ante and realized labels, up to 0.23 on PC1 with PC2, is the magnitude of the error this check prevents.
- Feasibility validation of every emitted lineup against the live site rules, per site.
- Scoring-adapter regression tests against archived box scores.
- Provenance recording: raw bytes, retrieval timestamp, and hash for every rules page and every data pull.

## Part 21: What must not be hardcoded

`SYNTHESIS`.

| Must not be hardcoded | Why | What to do instead |
|---|---|---|
| Any correlation coefficient | Every measured pair moved materially between 2024 and 2025, and several flipped sign under conditioning | Generate correlation as an emergent property of the world model; measure it as a diagnostic, never set it as a parameter |
| A single static correlation matrix | The tercile results show sign reversal under conditioning | Latent-factor plus competition structure |
| Site scoring constants | Operators change them | Load from a versioned, timestamped, hash-recorded fetch of the operator's own rules source |
| Roster slots, cap, team and game constraints | Site-specific and revisable | Same; and re-validate feasibility at submission time |
| Ownership estimates | A property of a changing opponent population | Fit weekly; never persist as constants |
| Field stack-structure frequencies | Stokastic's 45% / 25% / 5% / 25% is one source's snapshot | Calibrate from post-contest data each week |
| Exposure caps | Stokastic's 20% against STATAtl's 38.4% suggests dependence on portfolio size | Derive from the portfolio objective; treat published caps as sanity bounds |
| Boom and bust thresholds | SimSlate explicitly rejects fixed 5x salary | Calibrate per position from slate data |
| Duplication percentages | The available quantified data is from golf, not NFL | Read expected duplicates off a generated field |
| Salary-remaining targets | The uniqueness benefit is contest-specific | Optimize per contest against the payout shape |
| "Always stack" and "never pair negatively" rules | The measurements show both need conditions | Encode as objective terms, not as filters |
| Implied team totals | Prohibited as predictive inputs by project constraint | Use the football model's own team-scoring distribution |
| Position labels inferred from usage rank | This report's own panel could not separate tight ends from wide receivers | Carry a real, week-versioned position and depth-chart source; treat rank-based roles as a fallback flagged `UNKNOWN` |

## Part 22: Empirical test plan

`SYNTHESIS`. Each test below specifies estimand, historical population, prediction-time inputs, outcome, confounders, leakage risks, scoring metric, and prospective validation. All parameter selection is forward-chain: week \( t \) predictions use only data through week \( t-1 \).

### Test 1: Is the quarterback-to-pass-catcher correlation stable and prediction-time realizable?

- Estimand: Pearson correlation and 80th-percentile joint-tail lift of DraftKings points between a team's projected passer and its projected primary receiver.
- Population: all team-games, 2019 to 2025 regular season, excluding week 1 of each season.
- Prediction-time inputs: prior-week usage only, or the football model's projected role, never realized usage.
- Outcome: the pair of realized fantasy-point values.
- Confounders: team pass rate, pace, opponent quality, injuries to the primary receiver.
- Leakage risks: realized-label assignment, which this report measured as inflating the coefficient by up to 0.16.
- Metric: correlation estimate with a block bootstrap by team-season for the confidence interval; tail lift with the same bootstrap.
- Prospective validation: pre-declare the 2026 in-season estimate before week 1 and compare against realized, with the pre-declaration timestamped and hashed.

### Test 2: Is the opposing-quarterback relationship purely between-game?

- Estimand: the difference between the unconditional correlation and the average within-tercile correlation of opposing quarterbacks' points.
- Population: all games, 2019 to 2025.
- Prediction-time inputs: for the descriptive version, none. For the tradeable version, the conditioning variable must be the football model's own **predicted** game-total distribution, not realized points. This report's tercile analysis used realized game points and is therefore descriptive only, a limitation stated explicitly.
- Outcome: realized quarterback points for both sides.
- Confounders: pace, weather, defensive quality of both teams.
- Leakage risks: conditioning on realized totals, which this report does and flags.
- Metric: difference in correlations with bootstrap interval; and a variance decomposition into between-game and within-game components.
- Prospective validation: build predicted-total terciles in advance from model output and verify the within-tercile negative correlation holds out of sample.

### Test 3: Does stacking improve tournament outcomes, not just ceilings?

- Estimand: the difference in expected payout between a stacked and an unstacked lineup at matched projected points.
- Population: historical slates with published contest results, 2019 to 2025.
- Prediction-time inputs: projections and a field model built from information available before lock.
- Outcome: realized contest payout.
- Confounders: the stacked lineup will differ in projected points; matching must be explicit. Contest selection differences.
- Leakage risks: using realized ownership to build the field model for a retrospective test. Post-contest ownership is only available after the fact and must be excluded from the prediction-time field model, though it may be used to validate the field model separately.
- Metric: difference in mean payout per dollar staked, with contest as a random effect. Realized ROI has enormous variance, as the -57.6% over 22 entries in the ETR test demonstrates, so the design must be matched-pair rather than a naive comparison of averages.
- Prospective validation: pre-declare paired stacked and unstacked portfolios of equal size and cost for a full season.

### Test 4: Is ownership more predictable than production?

- Estimand: the ratio of out-of-sample \( R^2 \) for ownership prediction against \( R^2 \) for fantasy-point prediction, on the same player-weeks.
- Population: all player-weeks in contests with published ownership.
- Prediction-time inputs: salary, prior usage, and the model's own projections. Explicitly not sportsbook prices.
- Outcome: realized ownership percentage and realized fantasy points.
- Confounders: the two targets have different scales and different irreducible noise floors; the comparison must be on a normalized skill score, not raw \( R^2 \).
- Leakage risks: using industry consensus projections published after lock.
- Metric: continuous ranked probability score for both targets, normalized against a naive baseline for each.
- Prospective validation: weekly out-of-sample scoring across a full season.

### Test 5: Does leaving salary unspent increase uniqueness in NFL?

- Estimand: probability of a lineup being unique as a function of salary remaining, in NFL Classic contests.
- Population: contests with published full lineup data.
- Prediction-time inputs: salary remaining.
- Outcome: realized duplicate count.
- Confounders: salary remaining correlates with using cheap players, who are themselves lower-owned. The effect must be estimated conditional on the lineup's joint ownership.
- Leakage risks: none structural; this is a descriptive estimate on realized contest data.
- Metric: calibration curve plus the logistic coefficient on salary remaining, controlling for product-of-ownership.
- Prospective validation: none needed; this is a field-model calibration target rather than a predictive claim. Note explicitly that the currently available quantified evidence is from golf and does not transfer.

### Test 6: Does the field model reproduce the duplication tail?

- Estimand: the difference between the simulated and realized distributions of duplicate counts, especially the maximum.
- Population: contests with published lineup data.
- Prediction-time inputs: the field model's own inputs only.
- Outcome: realized duplicate-count distribution.
- Confounders: field size and buy-in.
- Leakage risks: fitting the field model to the same contest used for validation.
- Metric: Kolmogorov-Smirnov on the duplicate-count distribution, plus a specific check on the 99th percentile and maximum.
- Prospective validation: weekly.

### Test 7: Does late-swap flexibility have measurable option value?

- Estimand: the difference in expected payout between a portfolio built with a late-window bias in swappable slots and one built without, holding projected points equal.
- Population: historical slates with a multi-window structure.
- Prediction-time inputs: game start times and the football model.
- Outcome: simulated payout under an explicit late-swap policy, then realized payout prospectively.
- Confounders: late-window games systematically differ in quality and market attention.
- Leakage risks: evaluating the swap decision with knowledge of late-game outcomes. The conditional field posterior must use only early-game information.
- Metric: difference in expected payout, and the realized frequency with which the swap option was exercised profitably.
- Prospective validation: pre-declare the swap policy as code before the season and log every decision.

### Test 8: Does the world generator reproduce the measured correlation structure?

- Estimand: the full pairwise correlation matrix and joint-tail-lift matrix produced by the simulator, against the archived measurement.
- Population: simulated worlds against 2024 and 2025 archived play-by-play.
- Prediction-time inputs: not applicable; this is a model-diagnostic test.
- Outcome: the matrices themselves.
- Confounders: role-labeling scheme must match between simulator output and archived measurement.
- Leakage risks: tuning the simulator to match the same seasons used for validation. Hold out a season.
- Metric: maximum absolute deviation per cell, with hard failure on any sign disagreement. The prior second-opinion finding of a -0.128 simulated value against a +0.1201 and +0.2034 measured value is exactly the defect class this test exists to catch.
- Prospective validation: re-run against each new season's archive.

## Part 23: Optimizer failure modes

`PRO_STATEMENT` and `SYNTHESIS`, combined.

| Failure mode | Description | Source or basis |
|---|---|---|
| Chalk convergence | Maximizing projected points produces the modal lineup, which is the most duplicated | KC Joyner; Jake Letarski; Stokastic's over-exposure critique |
| Entering the default lineup | The raw optimizer output shares winnings because thousands of entrants use similar projections | Jake Letarski, explicitly |
| Exposure blow-out in a 150-lineup set | One running back in over 90% of lineups, one quarterback in 80% | Stokastic |
| Over-entering relative to bankroll | Spreads assets across low-conviction lineups and crushes profit potential | KC Joyner |
| Unadjusted defaults | Stacking rules, exposure limits, and correlation settings left at defaults | KC Joyner |
| Points-per-dollar ranking | Scale-dependent ratio systematically overweights minimum-salary players | `SYNTHESIS` |
| Correlation as a filter instead of an objective | "Must stack" or "never pair" constraints discard lineups that the objective would rank highly | `SYNTHESIS` |
| Realized-label correlation calibration | Inflates QB-PC1 by up to 0.16 and turns PC1-PC2 from approximately zero into +0.2 | `MEASURED_HERE` |
| Sign errors in the world generator | Club-versus-opponent offensive correlation of -0.128 against a real +0.12 to +0.20 mis-prices every game stack on the slate | Prior second-opinion work in this project, reproduced by this panel |
| Missing site feasibility constraints | The repository's Showdown solver had no both-teams constraint; the classic analogue is the FanDuel three-team and four-per-team rules | Prior second-opinion work; `PRIMARY_RULE` |
| Universe errors | The Showdown `p_optimal` universe contained 28 players with no kickers and no DST, yet the delivered portfolio rostered a kicker at 22.5% | Prior second-opinion work in this project |
| Normal-distribution assumptions | Understates tails, which is the only region a top-heavy contest pays | Newell thesis as the example; SimSlate's stated rejection |
| Independent-duplication estimates | The product of nine marginal ownerships both understates and overstates duplication depending on the structure | `SYNTHESIS` |
| Optimizing per lineup in a portfolio | Ignores the submodular set-level objective and the pairwise-correlation constraint | Hunter, Vielma, and Zaman |
| Simulating without a lineup-level field | Cannot compute rank or duplication, so cannot compute expected payout | `SYNTHESIS` |
| Treating sims as a solved problem | ETR's own test: winners at 1.65 times random expectation, author's realized ROI -57.6% over 22 entries, and sims do not account for wrong means, post-lock changes, or late swap | Establish The Run, explicitly |
| Ignoring rake | 15.9% rake quoted in one of Levitan's own recommended contests exceeds most construction edges | Levitan |
| Stale rules constants | Operators revise scoring and constraints | `SYNTHESIS` |
| Market data leaking into the football model | Implied team totals appear throughout published guidance and are prohibited here | Project constraint; Stokastic's DST and tight-end articles are built on implied totals |

## Part 24: Blueprint for this project's system

`SYNTHESIS`. The pipeline order is fixed and each arrow is a hard interface boundary.

Football evidence to simulation to distributions to site scoring to salary and universe to field model to contest simulation to lineup expected value to portfolio optimization.

The single most important architectural property is that the boundary between the football layer and the DFS layer is one-directional. Nothing downstream of the scoring adapter may influence anything upstream of it. That is what makes the standing constraint on sportsbook prices and ownership enforceable rather than aspirational.

### Module interfaces

| Module | Inputs | Outputs | Must not see |
|---|---|---|---|
| Slate ingestion | Operator slate file, game times, team assignments | Canonical slate object with per-player identity resolved and per-game start time | Ownership, prices |
| Site rules | Versioned fetch of operator rules with hash and timestamp | Slot structure, cap, team and game constraints, scoring constants, late-swap policy | Anything else |
| Salary universe | Slate ingestion plus operator salary file | Player set with salaries, normalized as a share of cap | Football model internals |
| Football-world generator | Historical data, prior-week features only | \( W \) joint stat-line worlds for the full slate | Salaries, ownership, sportsbook prices, site scoring |
| Football-world scoring | Worlds plus site rules | \( W \times P \) fantasy-point matrix per site | Ownership |
| Stack representation | Slate plus site rules | Enumerated legal stack structures per team and per game, per site | Ownership |
| Correlation representation | The world generator itself | A diagnostic report of emergent pairwise correlations and joint-tail lifts, compared against the archived measurement | Must not be an input anywhere |
| Lineup generation | Fantasy-point matrix, salary universe, site feasibility, structural constraints | Candidate lineup pool | Ownership at this stage; leverage enters later |
| Ownership model | Salaries, projections, prior-week field behavior | Per-player projected ownership with uncertainty | Must not feed the football model |
| Field lineup generator | Ownership model, stack priors, salary-remaining distribution, entrant structure | \( N \) complete opponent lineups | Candidate lineups, to avoid circularity |
| Duplication model | Generated field plus candidate lineup | Expected copies and \( P(\text{unique}) \) | None |
| Contest payout engine | Contest payout table | Rank-to-payout mapping with tie and duplicate handling | None |
| Single-lineup expected value | Fantasy-point matrix, generated field, payout engine, duplication model | Expected payout, \( P(\text{first}) \), \( P(\text{cash}) \) per candidate | None |
| Portfolio optimizer | Candidate pool with expected values, pairwise lineup correlations, exposure constraints | Final entry set per contest | None |
| Late swap | Locked outcomes, conditional field posterior, remaining feasibility | Swap decisions per entry | Post-lock opponent lineups for locked-out games, which are not observable anyway |
| Validation and governance | Everything | Pass or fail gates, provenance records | None |

### Where this project already stands

The repository under study contains `nfl/research/v4/p7/P7_DEPENDENCY_DAG_SPEC.md` as a specification only, `nfl/production/pipeline.py` with 14 stages, `nfl/product/orchestrator.py`, `nfl/research/cs2/predeclaration_cs2.md`, and `nfl/tests/run_suite.py`, which is a tally-based runner with a `blocked()` escape hatch, across 169 test files. `SYSTEM_STATE.json` is absent and `CURRENT_STATE.md` is stale as of 2026-09-07. The OAS1 `GO_NO_GO.md` records NO-GO on gates 3, 4, and 5. A Contract 4 mismatch remains open: the pre-declaration states "18 of 20" while `nfl/tools/draw_contract3.py:27-28` sets `BATCH_AGREEMENT = 19`.

Against the blueprint above, the honest assessment is that the football layer exists in partial form with a documented sign error in its game-environment coupling, the scoring adapter exists for both sites with FanDuel constants relayed by an operator rather than fetched, and the DFS layer above the scoring adapter is essentially absent: there is no field model, no contest simulator, no duplication model, and no portfolio optimizer. The Showdown solver that does exist had a missing feasibility constraint and a universe defect that allowed a kicker into a portfolio built from a kicker-free universe. `SYNTHESIS`.

The implication for sequencing is that building a full-slate optimizer before fixing the world generator's correlation sign would produce a system that is confidently wrong about exactly the structures that matter most.

### Implementation notes for Claude Code

- Put the scoring adapters first and make them exactly testable. Fetch the DraftKings rules JSON at `https://api.draftkings.com/rules-and-scoring/RulesAndScoring.json` and store the raw bytes with a hash and timestamp. FanDuel's `fanduel.com/rules-scoring`, `fanduel.com/games/nfl-fantasy-football-scoring`, and `support.fanduel.com` all refuse programmatic fetch with 403 or robots exclusions, while `fanduel.com/rules` and `fanduel.com/research/fantasy-football-strategy` do fetch successfully. Use the latter two and record which URL each constant came from.
- Implement site feasibility as integer-program constraints in a single shared module, parameterized by site, so that no solver can accidentally omit one. Add a test that asserts a quarterback-plus-four-teammates lineup is accepted on DraftKings and rejected on FanDuel.
- Add the static dependency-closure test for the football simulator before adding any ownership code. It is much harder to retrofit.
- Build the correlation diagnostic as a first-class report that runs on every simulator change and compares against the archived 2024 and 2025 measurement in this directory, failing on any sign disagreement.
- Do not add a correlation matrix as a configurable parameter. If the world generator needs one internally as a copula input, it must be derived from the latent-factor specification and reported, not tuned.
- Represent stacks as explicit enumerated structures rather than as post-hoc filters on generated lineups, so that structural exposure can be constrained directly in the portfolio optimizer.
- The field model should be a separate process writing a lineup file, so that the contest simulator can be tested against a fixed field.

## Part 25: Priority roadmap

`SYNTHESIS`.

### Must have before building a full-slate optimizer

1. Fix the game-environment coupling sign error in the world generator. A simulator producing -0.128 where the archive gives +0.12 to +0.20 cannot price any game stack correctly.
2. Site feasibility as shared hard constraints, including the FanDuel three-team minimum and four-per-team maximum and the DraftKings two-game minimum. Test both sites explicitly.
3. Scoring adapters for both sites with provenance-recorded constants and box-score regression tests.
4. A universe-integrity gate that makes it impossible for a player outside the declared universe to appear in an emitted lineup.
5. The static governance test that no market or ownership data reaches the football simulator.
6. Right-skewed marginal distributions. Normal marginals are disqualifying for tournament work.
7. The correlation diagnostic report, comparing simulator output against the archived measurement, with sign disagreement as a hard failure.
8. Resolve the open Contract 4 mismatch between the pre-declared "18 of 20" and `BATCH_AGREEMENT = 19` in `nfl/tools/draw_contract3.py:27-28`. The standing constraint against retroactively modifying Contract 3 applies; the resolution must not weaken the pre-declared gate.

### Must have before entering 150-max contests

9. A full-lineup field model, not a player-ownership model.
10. A duplication model reading expected copies off the generated field.
11. A contest payout engine with correct duplicate-payout division.
12. A portfolio optimizer implementing greedy submodular maximization with a pairwise lineup-correlation constraint and a per-lineup variance floor.
13. Exposure constraints at player, stack, game, and quarterback level, with caps derived from the objective rather than hardcoded.
14. Field-model calibration against published post-contest ownership, including the duplication tail.

### Nice to have

15. Late-swap policy as code, with a conditional field posterior.
16. Importance sampling for tail resolution in massive-field contests.
17. Contest-allocation optimization across multiple contests in one week.
18. A week-versioned depth-chart and position source, which would close the tight-end gap that makes every tight-end-specific claim in this report `UNKNOWN`.
19. Salary-remaining optimization per contest payout shape.

### Research only

20. Role-substitution and availability modeling as a discrete mechanism rather than a correlation.
21. Predicted-total conditioning of the correlation structure, replacing this report's realized-total terciles with a prediction-time conditioning variable.
22. Whether exposure caps should scale with portfolio size, which the Stokastic-against-STATAtl disagreement suggests.
23. Whether late-window flexibility carries measurable option value.
24. Whether ownership is genuinely more predictable than production, on a normalized skill score.

### Do not implement without evidence

25. Any hardcoded correlation coefficient, including every published figure this report found to disagree with measurement.
26. Tight-end-specific correlation rules, until tight ends can be separated from wide receivers in the data.
27. The running-back-plus-own-defense blowout stack, which measured 0.139 in 2024 and 0.019 in 2025.
28. The two-pass-catcher secondary stack without a quarterback, which measured a joint-tail lift of 0.947 in both seasons.
29. Golf-derived duplication percentages applied to NFL.
30. Implied-team-total logic anywhere in the football layer, regardless of how ubiquitous it is in published guidance.
31. Any exposure cap, boom threshold, or salary-remaining target taken from a strategy article as a constant.

## Section III: Standing caveats on this report's own measurements

Stated plainly rather than buried, because the measurements above are used to contradict widely cited figures and must not be over-claimed.

- Roles are usage-rank labels from prior-week usage, not nominal positions or projected roles. A production system would label by projected role, which is closer to the ex-ante scheme than the realized one but not identical.
- Tight ends cannot be separated from wide receivers. Every tight-end claim is `UNKNOWN`.
- The panel is two seasons, 1,024 ex-ante team-games. Tail statistics at this sample size are noisy, which is why every figure is reported per season rather than pooled.
- The DST points-allowed reconstruction excludes opponent defensive touchdowns per the operator rule but does not subtract the extra points attached to them.
- The tercile conditioning uses realized combined game points. It is descriptive evidence that the correlation structure is state-dependent, not a prediction-time input. Test 2 in Part 22 specifies the prediction-time version.
- Joint-tail lift at the 80th percentile is a compromise between relevance and sample size. Tournament payouts depend on far higher quantiles, which two seasons cannot estimate reliably.
- These measurements do not settle any of the disputes in Section 2.8. They establish that the published figures are not reproducible under prediction-time labeling on recent data, and they give this project a forward-chain-compatible baseline of its own.
