# NFL Forecasting Engine: Full Product Deep Research Packet (Parts I to L)

Prepared 2026-09-21 for Claude Code implementation. Revision 2 (2026-09-21, after external review); see `CHANGELOG.md` for every finding, correction, evidence and open question. Status of the engine under review: CANDIDATE_NOT_ACCEPTED_BASELINE / V2 NOT YET EARNED. Research completion in this packet does not constitute model acceptance, promotion or production readiness.

## 0. How to read this packet

### 0.1 Mandate provenance and combination

The mandate arrived in two pieces. Piece 1 is the uploaded file `pasted_text_1790015535.txt` (Parts I to XLVIII, cut off inside Part XLVIII). Piece 2 is the user's continuation message (remainder of Part XLVIII, Part XLIX synthesis, Part L required deliverables, research execution rules, final acceptance standard). Both pieces are combined in `mandate_combined.md` in this folder; Parts I to XLVIII are verbatim from the upload, and the continuation is reconstructed from the continuation message as preserved in the session record, marked as reconstructed rather than verbatim where the exact wording could not be recovered.

### 0.2 Coverage map to the eight required deliverables

| Deliverable | Where |
|---|---|
| 1 Executive architecture recommendation | Section 1 of this file |
| 2 Machine-readable source registry | `source_registry.csv` (33 sources, 22 fields, UNKNOWN where unverified) |
| 3 Component specifications for Parts I to XLVIII | Section 2 of this file (48 numbered blocks, none omitted) |
| 4 Typed schema proposals | Section 3 of this file |
| 5 Validation and promotion protocol | Section 4 of this file |
| 6 Product gate matrix and verdict precedence | Section 5 of this file plus `gate_matrix.csv`, `scope_gate_dependencies.csv`, `verdict_engine.py`, `test_verdict_engine.py` |
| 7 Engineering backlog | `implementation_backlog.csv` (34 tasks) plus Section 6 summary |
| 8 Unresolved evidence and access register | Section 7 of this file |

### 0.3 Evidence labels used throughout

- ESTABLISHED: general statistical or engineering result with primary literature cited.
- NFL_DOCUMENTED: a documented NFL application or data fact with a cited primary or secondary page.
- PROPOSAL: architecture or method proposed here; requires validation under Section 4 before any product depends on it.
- UNSUPPORTED: evidence-status label only (not a product verdict): no adequate evidence or no lawful data path found; product scopes depending on it receive verdict RESEARCH_ONLY with a typed reason code (Section 4.3).
- REPO: fact taken from the project's own prior reports or the `94924676jp-a11y/Nfl` repository; distinguished from external research.

Cross-references to prior project reports use checkout-relative paths under `external-research/`. Prior reports are not duplicated here; this packet adds what they did not cover and reconciles where they disagree.

### 0.4 Standing constraints honored

Sportsbook prices, DraftKings salaries, ownership projections, contest results, optimizer outputs, bankroll information and betting decisions are treated as downstream only. Commercial NFL data vendors are researched for the free-versus-paid comparison the mandate requires, but none is adopted as a dependency: the governing instruction is the owner's message of 2026-09-14 18:51 UTC (session turn 125), which states that commercial systems may be studied only to identify capability gaps to reproduce independently. Registry rows for paid sources carry that adoption status explicitly rather than an unexplained exclusion. No universal minimum sample sizes or promotion thresholds are invented; Section 4 gives the procedure for deriving them. No caveats are left as prose: each becomes a component, a gate or an unsupported state.

## 1. Deliverable 1: Executive architecture recommendation

### 1.1 Recommendation in one paragraph

Build the engine as a strictly layered, vintaged pipeline in which every layer consumes only artifacts whose publication time is at or before the declared information cut, and in which the game simulator is the single source of all football distributions consumed by props and DFS. The recommended production simulator for the current stage is a play-level state-transition engine with a reduced play-outcome model (Option C-reduced, specified as an algorithm in Block X), with a drive-level Markov engine kept as the fallback baseline and an aggregate team-total engine kept only as a benchmark. The earlier label Option B is withdrawn because the engine samples individual plays. Availability, role and allocation are modeled as separate stochastic layers so that a QB or role uncertainty produces a mixture over worlds rather than a point adjustment. Validation is chronological only, verdicts are machine-generated from typed gate results, and every product scope has an explicit precedence rule over which gate failures block it.

### 1.2 What is established, what is documented for NFL, what is a proposal, what is unsupported

| Item | Label | Evidence |
|---|---|---|
| Rolling-origin (forward-chain) evaluation as the only admissible validation for time-ordered data | ESTABLISHED | [Hyndman, evaluation on a rolling forecasting origin](https://robjhyndman.com/hyndsight/tscv/) |
| Maximize sharpness subject to calibration; PIT histograms; proper scoring rules | ESTABLISHED | [Gneiting, Balabdaoui, Raftery 2007](https://sites.stat.washington.edu/raftery/Research/PDF/Gneiting2007jrssb.pdf) |
| Count-forecast calibration needs discrete-aware tests (randomized PIT, CEP regression) | ESTABLISHED | [Wei and Held 2014](https://www.zora.uzh.ch/id/eprint/102586/1/4-WeiHeld-cailibration2014.pdf) |
| Model risk framework: conceptual soundness, ongoing monitoring, outcomes analysis, effective challenge, inventory, change control | ESTABLISHED (non-sports) | [SR 11-7 attachment](https://www.federalreserve.gov/boarddocs/srletters/2011/sr1107a1.pdf) |
| Drive-level Markov and survival models of NFL possessions | NFL_DOCUMENTED | [Goldner, Markov model of football](https://supermariogiacomazzo.github.io/STOR538_WEBSITE/Articles/Football/Football_Goldner.pdf) and [Weitzenfeld, Bayesian NFL drive modeling](http://danielweitzenfeld.github.io/passtheroc/posts/bayes-nfl.html) |
| nflverse asset inventory, cadence, identifiers and license status | NFL_DOCUMENTED | [nflverse data schedule](https://nflreadr.nflverse.com/articles/nflverse_data_schedule.html), [load_players](https://nflreadr.nflverse.com/reference/load_players.html), [load_participation](https://nflreadr.nflverse.com/reference/load_participation.html) |
| Depth-chart vintages exist natively from 2025 onward | NFL_DOCUMENTED | [depth charts dictionary](https://nflreadr.nflverse.com/articles/dictionary_depth_charts.html); 188 `dt` vintages verified in `depth_charts_2026.parquet` |
| Questionable and Doubtful empirical play rates | NFL_DOCUMENTED (secondary) | [Footballguys 2017 to 2024](https://www.footballguys.com/article/2025-chance-to-play-questionable-vs-doubtful), [TeamRankings 2008 to 2009](https://www.teamrankings.com/blog/nfl/nfl-injury-analysis-how-often-do-hurt-players-actually-play-1-of-4) |
| Field goal logistic model with distance, cold, turf, altitude terms | NFL_DOCUMENTED | [Clark, Johnson, Stimpson 2013](https://aaronwj.engin.umich.edu/wp-content/uploads/sites/546/2021/09/Clark-Johnson-Stimpson-2013.pdf) |
| DraftKings scoring constants | NFL_DOCUMENTED (official) | [DraftKings RulesAndScoring.json](https://api.draftkings.com/rules-and-scoring/RulesAndScoring.json) |
| Dirichlet-multinomial field ownership generation | NFL_DOCUMENTED (academic) | [Haugh and Singal](https://arxiv.org/abs/1806.03142) |
| Separate availability, role, allocation and efficiency layers with mixture-over-worlds | PROPOSAL | This packet, Section 2 blocks V, VII, VIII, X |
| Play-level state-transition simulator with a reduced play-outcome model (Option C-reduced) as the production choice; drive-level Markov engine retained as the fallback baseline | PROPOSAL | Section 2 block X |
| Coherence-preserving calibration by world reweighting (worlds never altered; one weight vector per release; props, SGP and DFS read the same weighted worlds) | PROPOSAL | Section 2 block XIX |
| In-season route participation | UNSUPPORTED | `pbp_participation_2026` returns 404 in season; FTN routes are paid; Section 2 block III |
| Point-in-time transaction timestamps from NFL.com | UNSUPPORTED (as observed) | [NFL transactions page](https://www.nfl.com/transactions/) rendered without server-side content in this session |
| Historical as-issued pre-kickoff weather forecasts | SUPPORTED WITH LIMITS | [Open-Meteo Single Runs API](https://open-meteo.com/en/docs/single-runs-api) returns the exact run by `run=` initialisation time; ECMWF IFS HRES from March 2024, other models from 2026-04-02; publication latency of each run must still be measured before a run is admitted at a cut |
| Machine-readable OL and pass-rush win rates | UNSUPPORTED | ESPN publishes articles only ([ESPN win rates](https://www.espn.com/nfl/story/_/id/49672562/nfl-new-pass-block-push-rush-win-rates-formula-takeaways-analytics)) |

### 1.3 Layer order (restated from the prior packet and reconciled with the mandate causal chain)

EVIDENCE (Part I, II, XXXVIII) to AVAILABILITY (XIV, VIII) to ROLE (III, IV, V) to TEAM VOLUME (VI, XI, XII, XIII) to ALLOCATION (VII) to EFFICIENCY (IX) to WORLDS (X, XV) to DISTRIBUTIONS (XXXV) to PROPS (XVIII to XXI) and DFS (XXII to XXXI). Validation (XVI, XVII, XIX, XXXII) and platform (XXXVII to XLIV) wrap every layer. UX (XLVI) reads verdicts only.

### 1.4 Decisions the owner must make (not decided here)

- Whether the football forecast product may ship for any scope while the identity axis for salaries is incomplete (Section 5 says yes for football scopes, blocked for DFS scopes).
- Which reporter accounts, if any, are admitted at Tier 5 and under what capture standard (Section 2 block I).
- Whether to acquire the GSIS XML gamebook by arrangement (Section 7).

## 2. Deliverable 3: Component specifications, Parts I to XLVIII

Each block has: Findings (with URLs or REPO paths), Recommendation, Method or equations, I/O contract, Benchmark, Gates, Unsupported states and blocked scopes, Complexity and uncertainty. Where a prior project report already covers a topic, the block gives the delta and the path.

### Block I: Authoritative NFL truth layer

Findings.
- Twenty-eight source types were requested. Verified publisher and timing facts: game-day inactives are published by the league and clubs about 90 minutes before kickoff, and the emergency third quarterback is listed on the Gameday Administration Report at the 90-minute meeting ([NFL emergency QB Q&A](https://www.nfl.com/news/nfl-emergency-third-quarterback-rule-questions-and-answers)). Practice-squad elevations: at most two per player per League Year under the standard rule, at most two per club per game, and automatic reversion at 4:00 pm New York time on the first business day after the game ([CBA Article 33 Section 5 via Over The Cap](https://overthecap.com/collective-bargaining-agreement/article/33/section/5)); later amendments to the per-player count were not verified in this session and are marked UNKNOWN. Injury report categories since 2016: DNP, Limited (less than 100 percent of normal reps), Full; game status Questionable (uncertain), Doubtful (unlikely), Out (will not play); Probable eliminated ([NFL competition committee revision](https://www.nfl.com/news/competition-committee-approves-revisions-to-injury-report-0ap3000000688693)).
- Gamebooks: the GSIS PDF game book link appears within minutes after each game, and an XML game book is available to organizations on request ([NFLGSIS About](https://www.nflgsis.com/Help/About.html)); URL pattern observed `https://www.nflgsis.com/2025/REG/15/60059/Gamebook.pdf`.
- Rosters, depth charts and practice reports are built by the nflverse-rosters workflows and pushed to nflverse-data releases; the README does not name the upstream systems and data was archived away from that repo as of 2022-08-01 ([nflverse-rosters](https://github.com/nflverse/nflverse-rosters)); older snapshots live in [nflverse-data-archives releases](https://github.com/nflverse/nflverse-data-archives/releases). Roster data updates daily at 07:00 UTC ([nflverse schedule](https://nflreadr.nflverse.com/articles/nflverse_data_schedule.html)).
- Depth charts since 2025 come from ESPN with an ISO 8601 `dt` load timestamp and are appended, giving native vintages ([depth charts dictionary](https://nflreadr.nflverse.com/articles/dictionary_depth_charts.html)). ESPN depth charts are unofficial.
- Transactions: the NFL.com page exposes categories Trades, Signings, Reserve List, Waivers, Terminations, Other but rendered no records server-side in this session ([NFL transactions](https://www.nfl.com/transactions/)); per-transaction timestamps are UNKNOWN. Team changes, position changes, jersey and name changes, aliases and rookie entries are covered by the identity layer (Block II) via [load_players](https://nflreadr.nflverse.com/reference/load_players.html).
- Coaching announcements and beat reporters: no lawful machine-readable archive with publication timestamps was found; see REPO `external-research/nfl-intel-2-information-frontier.pplx.md` for the information-class taxonomy.
- REPO capture standard for inactives (raw bytes, sha256, retrieval time, parsed index) is in `external-research/inactives/nfl-wk2-1pm-official-inactives-2026-09-20/` and the point-in-time capability audit is `external-research/own-nfl-data-network-2026-09-14/own-nfl-data-network.pplx.md` sections 5.1 to 5.17.

Recommendation (PROPOSAL). Adopt the following evidence hierarchy, ordered by authority for the question "will this player be active and in what capacity at kickoff", and record for every fact the tuple (source_id, publisher_class, published_at or UNKNOWN, retrieved_at, sha256 of raw bytes, parser_version).

| Tier | Source type | Answers | Availability relative to kickoff |
|---|---|---|---|
| 1 | Official game-day inactive list (league article, club post, gamebook after the game) | active or inactive | about T minus 90 min; gamebook after game |
| 2 | Official roster and transaction events (reserve lists, IR, PUP, NFI, suspensions, elevations, signings, waivers) | roster membership and eligibility | as filed, usually by 4:00 pm NY on transaction days |
| 3 | Official injury report game status (Out, Doubtful, Questionable) and practice participation (DNP, LP, FP) | expected participation | Wed, Thu, Fri (Fri game status); Sat for Monday games |
| 4 | Official team depth chart (team site) | intended role order | weekly, team dependent, UNKNOWN cadence |
| 5 | Trusted reporters and coaching announcements | intent and expectations | continuous; must be captured with timestamps to be admissible |
| 6 | Unofficial aggregations (ESPN depth charts via nflverse, aggregator injury pages) | role order, corroboration | daily 07:00 UTC for nflverse |
| 7 | Model inference (absence-from-list, historical play rates) | probability only | any time; never asserted as fact |

Authoritative state versus estimated probability (corrected after review). Authoritative game-day status has exactly three typed values before kickoff: INACTIVE_LISTED (Tier 1 capture present and player listed), ACTIVE_LISTED (Tier 1 capture present, player on the 47 or 48 active list or explicitly confirmed active, or gamebook after the game), and GAMEDAY_STATUS_UNKNOWN (no Tier 1 capture yet, or capture present but player not resolvable). Absence from a captured inactive list does not produce an active state; it produces GAMEDAY_STATUS_UNKNOWN with a sub-flag `absent_from_inactives_capture = true`. Any estimated participation probability P(active) lives only in the availability model output (Block XIV) and is never written into `player_state_at_cut`. Downstream products read both fields separately and the UX shows them separately.

Conflict handling without guessing: a higher tier fact overrides a lower tier fact for the same question only when its publication time is known and later than or equal to the lower tier fact's publication time; when publication time is UNKNOWN for either side, the state becomes CONFLICT_UNRESOLVED and the affected player is carried as a two-world mixture (Block VIII) with the conflict logged. Absence from an inactive list never implies ACTIVE; the authoritative state stays GAMEDAY_STATUS_UNKNOWN until an active list, a club confirmation or the gamebook resolves it. Injury designation, roster membership, practice status, transaction status, depth chart rank and game-day inactive status are separate typed fields and are never coerced into one another.

I/O contract. Input: raw captures. Output: `player_state_at_cut` records (Section 3.2) keyed by (gsis_id, game_id, information_cut). Benchmark: post-game gamebook truth for active status and starters. Gates: G-I-1 every Tier 1 fact has raw bytes and hash; G-I-2 no record with published_at UNKNOWN is used above Tier 6; G-I-3 gamebook reconciliation error rate reported per week (target set by Section 4 procedure, not invented). Unsupported: pre-2025 depth chart vintages (blocks historical backtests that need depth charts before 2025 unless self-archived data exists); transaction timestamps (blocks Tier 2 recency logic for backtests). Complexity: medium; uncertainty: high on Tier 5 admissibility.

### Block II: Player identity and entity resolution

Findings.
- `players.parquet` carries gsis_id (primary), esb_id, nfl_id, pfr_id, pff_id, otc_id, espn_id, smart_id and five name variants including football_name and suffix ([load_players](https://nflreadr.nflverse.com/reference/load_players.html)); the build merges basis (GSIS), draft, OTC, PFF, PFR via gsis_id and ESPN via gsis_id ([nflverse-players](https://github.com/nflverse/nflverse-players)). Season rosters add sportradar_id, yahoo_id, rotowire_id and sleeper_id. The DynastyProcess crosswalk uses mfl_id as the primary key and adds sportradar_id (UUID), fantasypros_id, sleeper_id, cbs_id, rotowire_id and others ([ff_playerids dictionary](https://nflreadr.nflverse.com/articles/dictionary_ff_playerids.html)). No dataset in context carries DraftKings or FanDuel identifiers; those must be built from salary files.
- Sportradar documents a Player Profile with draft data and a `seasons[]` stint array and a Daily Change Log ([Sportradar NFL rosters](https://developer.sportradar.com/football/docs/nfl-ig-rosters)); this is a paid vendor and is not adopted, documented only for identifier semantics.
- REPO: the IND at KC handoff recorded a failed inference where a position map mislabeled McGowan; it is preserved in `research-data/ind-kc-snf-baseline-projections-2026-09-20/HANDOFF_data_acquisition_for_claude_code.md`.

Recommendation (PROPOSAL). Two identity axes with separate namespaces: football axis keyed by gsis_id with alias table (name variants, suffix, accent-folded, jersey history, team history, position history) and provenance; salary and market axis keyed by (platform, platform_player_id or platform_name, slate_id) with a resolution record to gsis_id carrying a confidence class: EXACT_ID (shared id such as sportradar_id or espn_id), STRONG (name plus team plus position match with unique candidate), WEAK (name-only unique candidate), AMBIGUOUS (multiple candidates), UNRESOLVED. Only EXACT_ID and STRONG are used automatically; AMBIGUOUS and UNRESOLVED block the downstream product record for that player and never modify the football state. Trades and team changes are handled by roster vintages, not by identity.

Equations: none; deterministic resolution with an audit log. Benchmark: hand-labeled resolution set built from prior slates (REPO `uploaded_attachments` DK and FD Week 1 salary files). Gates: G-II-1 football-axis coverage of all players appearing in pbp for the cut equals 100 percent, else the game's worlds are not produced and F1 carries reason code NO_OUTPUT; G-II-2 salary-axis unresolved rate reported per slate and each unresolved player blocks only DFS scopes. Unsupported: sportsbook player identifiers (none in context). Complexity: low to medium.

### Block III: Snap and participation data and models

Findings.
- Snap counts (PFR) from 2012, keyed by pfr_player_id only, updated at 0, 6, 12, 18 UTC dependent on PFR ([load_snap_counts](https://nflreadr.nflverse.com/reference/load_snap_counts.html)). Per-play participation (players on field, formation, personnel, route, coverage) exists 2016 to 2025, published after the postseason, FTN-sourced from 2023 under CC-BY-SA 4.0, and `pbp_participation_2026.parquet` returns 404 in season ([load_participation](https://nflreadr.nflverse.com/reference/load_participation.html)). The FTN charting subset (motion, play action, screens, RPO, pass rushers, box count) is charted within 48 hours and is available for 2026 ([load_ftn_charting](https://nflreadr.nflverse.com/reference/load_ftn_charting.html)). PFR advanced passing adds pressure, blitz, drop and on-target counts ([PFR passing dictionary](https://nflreadr.nflverse.com/articles/dictionary_pfr_passing.html)). Gamebooks provide starters and participation post-game ([NFLGSIS About](https://www.nflgsis.com/Help/About.html)). The paid FTN catalog documents route and alignment fields but is excluded by project rule ([FTN catalog](https://ftnfantasy.com/ftn-data-nfl-catalog)). PFF describes more than 200 fields per play but discloses no downloadable participation data ([PFF grades](https://www.pff.com/grades)).
- Consequence: in-season route counts are UNSUPPORTED from lawful free sources. A route proxy from pbp (targets, pass plays while on field inferred from snap share) is the only in-season path and must be labeled PROXY.
- REPO: hurdle and zero-inflated structure, compositional allocation, hierarchical pooling and HMM role states are specified in `external-research/participation-allocation-methodology-2026-09-14.md`; QB participation in `system-review-2026-09-14/qb_participation.md`.

Recommendation (PROPOSAL). Two-stage participation: stage 1 appearance hurdle P(offense_snaps greater than 0 or above a role floor) from a hierarchical logistic model on availability state, depth rank, prior snap share and week; stage 2 snap share given appearance as beta regression with team-position random effects and an EWMA-smoothed prior, with a change-point detector on snap share to reset the prior after role breaks (injury return, trade, coaching change). Beta-binomial is preferred over beta regression when team snap totals are simulated (share applied to a sampled count). HMM role states (starter, committee, backup, inactive) are retained as the research alternative from the REPO methodology and evaluated against the two-stage model chronologically; neither is production-proven.

Equations. Stage 1: logit P(appear) = a_team_pos + b1 depth_rank + b2 prior_share + b3 status_code. Stage 2: share ~ Beta(mu phi, (1 minus mu) phi), logit mu = c_team_pos + d1 prior_share_ewma + d2 depth_rank + d3 days_since_role_change. Snap count = round(share times team_offense_snaps_world).

I/O: input availability state (Block XIV), depth rank vintages, snap history; output per-world snap count and route proxy count. Benchmark: post-game PFR snap counts; participation file after season for route truth. Gates: G-III-1 PIT uniformity of snap-share predictive distributions per position (Wei and Held discrete-aware where counts); G-III-2 hurdle Brier and reliability per status code. Unsupported: in-season routes (blocks any route-based product claim); pass-block and run-block snaps in season. Complexity: medium; uncertainty: high for committees and returning players.

### Block IV: Depth-aware cold start

Findings. Draft capital with gsis_id, pfr_player_id and cfb_player_id is available in the draft picks asset; career columns in that file are future information and must be excluded ([draft picks dictionary](https://nflreadr.nflverse.com/articles/dictionary_draft_picks.html)); nfldata draft_picks joins pre-2000 by name ([nfldata DATASETS](https://github.com/nflverse/nfldata/blob/master/DATASETS.md)). Depth rank vintages exist from 2025 ([depth charts dictionary](https://nflreadr.nflverse.com/articles/dictionary_depth_charts.html)). College play-by-play exists via CFBD ([cfbfastR cfbd_pbp_data](https://cfbfastr.sportsdataverse.org/reference/cfbd_pbp_data.html)) but the cfb_player_id bridge to CFBD athlete ids is UNKNOWN. No NFL literature on rookie snap-share priors conditional on depth rank was found in this session; recorded as an evidence gap.

Recommendation (PROPOSAL). Empirical-Bayes prior for a player with fewer than k games on the current team: prior mean share = weighted blend of position-and-depth-rank league mean (from 2025 to present depth vintages joined to snap counts), draft-capital bucket mean (round 1, 2, 3, 4 to 7, undrafted), and room-composition adjustment (number of players at the same depth slot with prior share above a floor). Shrink toward the prior with weight n0 chosen by the Section 4 procedure, not fixed. Positional archetype (slot, inline, satellite) is UNSUPPORTED in season without alignment data and is recorded as a proxy from prior seasons only.

Benchmark: chronological error of rookie and new-team snap share versus a naive depth-rank-only baseline. Gates: G-IV-1 prior must not use any column dated after the cut. Unsupported: college usage translation until the id bridge is resolved. Complexity: low to medium.

### Block V: Role state model

Findings. REPO `participation-allocation-methodology-2026-09-14.md` specifies HMM role states and hidden Markov play-call work ([arXiv 2003.10791](https://arxiv.org/pdf/2003.10791.pdf)). Coaching changes: nflanalytic found 198 head coach changes 2000 to 2026 and used cluster-robust standard errors by team-season ([nflanalytic new coach effect](https://nflanalytic.com/explainer-new-coach-effect.html)); the explainer is a descriptive analysis, not a rule.

Recommendation (PROPOSAL). Discrete role state per player-week in {STARTER, COMMITTEE_LEAD, COMMITTEE_SHARE, BACKUP, SPECIALIST, INACTIVE_EXPECTED} with a transition model conditioned on availability events of the player and of teammates at the same position. Role state is a latent variable sampled per world so that role uncertainty produces bimodal snap-share mixtures rather than a shrunken mean. Change-point detection (CUSUM on weekly share) flags regime changes and triggers a prior reset. Coaching change enters as a covariate that widens the transition distribution, not as a fixed effect size.

I/O: input Blocks I, III, IV; output role-state distribution per player-week. Benchmark: post-game snap share bucketed to role. Gates: G-V-1 role-state log loss compared with a persistence baseline chronologically. Unsupported: first-series usage and drive-by-drive participation in season (no lawful source). Complexity: medium to high.

### Block VI: Team offensive volume

Findings. Plays per game, pace and pass rate over expected are derivable from pbp; `xpass` and `pass_oe` are model-derived nflfastR columns and must not be used as inputs without a declared exemption ([nflfastR](https://nflfastr.com/articles/nflfastR.html)). PROE definitions are documented by ETR ([ETR PROE](https://establishtherun.com/pass-rate-over-expectation/)). Sportsbook totals and spreads are not admitted as inputs (mandate Part VI). REPO: opponent-adjusted team strength with forward-chain tuning is `external-research/oas1-opponent-adjusted-strength-2026-09-17/`.

Recommendation (PROPOSAL). Team volume is an emergent quantity of the simulator (Block X) driven by three team-level latent rates: neutral pace (seconds per play in neutral score and clock), neutral pass rate, and situational modifiers (score differential, time remaining, down and distance) estimated as opponent-adjusted hierarchical effects with forward-chain shrinkage. Volume is never forecast directly for use as a downstream input; it is checked as an output against pbp totals.

Equations: plays_per_drive and drives_per_game emerge from drive sampling; neutral pass rate logit = team_off + opp_def + coach_effect + season_drift with random walks by week.

Benchmark: team attempts, plays and drives per game from pbp, chronologically. Gates: G-VI-1 team plays and pass attempts PIT uniformity; G-VI-2 no market columns in the feature manifest (static check). Unsupported: none beyond market exclusion. Complexity: medium.

### Block VII: Opportunity allocation

Findings. REPO `participation-allocation-methodology-2026-09-14.md` covers compositional (Dirichlet-multinomial) allocation and hierarchical pooling; the prior packet covers concentration metrics (top-1, top-2, top-3 share, HHI, entropy, Gini) and Dirichlet estimation ([Dirichlet MLE, arXiv 1405.0099](https://arxiv.org/pdf/1405.0099.pdf)).

Recommendation (PROPOSAL). Given a world's team pass attempts and designed rushes, allocate targets and carries by sampling from a Dirichlet-multinomial whose concentration vector is a function of role state (Block V), snap share (Block III) and route proxy, with a separate allocation for red-zone and goal-line attempts because concentration differs by field zone. Rookies and new-team players enter with Block IV priors. Concentration metrics are diagnostics for gates, not inputs.

I/O: input world team counts and role states; output per-player targets, carries, red-zone opportunities per world. Benchmark: post-game targets and carries; concentration metrics of realized versus simulated. Gates: G-VII-1 realized top-1 share and HHI fall inside the simulated interval at the nominal rate; G-VII-2 sum of player counts equals team counts in every world (exact invariant). Complexity: medium.

### Block VIII: Absence and redistribution

Findings. REPO `own-nfl-data-network-2026-09-14/own-nfl-data-network.pplx.md` Section 9 specifies an absence and replacement database; empirical play rates for Questionable and Doubtful are cited under Block XIV. Elevation rules constrain who can replace whom ([CBA Article 33 Section 5](https://overthecap.com/collective-bargaining-agreement/article/33/section/5)); the emergency QB cannot be an elevated practice squad player ([NFL emergency QB Q&A](https://www.nfl.com/news/nfl-emergency-third-quarterback-rule-questions-and-answers)).

Recommendation (PROPOSAL). Redistribution is not a fixed table. Each world samples availability for every player (Block XIV), then reruns role and allocation conditioned on the sampled active set. Historical redistribution is learned as the change in Dirichlet concentration under absence of a same-position player of a given role, pooled hierarchically by position and role pair. Team-level volume response to QB absence is a separate learned effect on neutral pass rate and pace, with explicit uncertainty.

Gates: G-VIII-1 out-of-sample redistribution error measured only on weeks where the absence was known before the cut. Unsupported: absence types with no historical analogue on the team (state NO_ANALOGUE, widened prior, flagged). Complexity: medium to high.

### Block IX: Player efficiency

Findings. Efficiency columns in pbp are raw (yards, air_yards, yards_after_catch, completion, touchdown); EPA, CPOE and success are model-derived ([nflfastR](https://nflfastr.com/articles/nflfastR.html)). PFR advanced passing offers pressure and accuracy counts ([PFR passing dictionary](https://nflreadr.nflverse.com/articles/dictionary_pfr_passing.html)). nflWAR documents a multilevel approach to player value ([nflWAR](https://arxiv.org/pdf/1802.00998.pdf)).

Recommendation (PROPOSAL). Efficiency parameters per player are per-opportunity distributions (yards per carry, yards per target, catch rate, TD rate by field zone) with hierarchical shrinkage to position, team and league means and forward-chain drift. Distribution families per Block XXXV. Efficiency depends on matchup covariates from Blocks XI and XII only where those covariates pass their own gates.

Gates: G-IX-1 per-opportunity predictive PIT and CRPS chronologically versus a position-mean baseline. Complexity: medium.

### Block X: Game simulation architecture

Findings. The prior packet (`external-research/engine-rebuild-research-packet-2026-09-21/nfl-engine-rebuild-research-packet.pplx.md`, section 5) compares aggregate, drive and play simulators without settling the choice. Documented NFL possession models: Goldner's Markov chain over down, distance and field position with 340 transient and 9 absorbing states ([Goldner](https://supermariogiacomazzo.github.io/STOR538_WEBSITE/Articles/Football/Football_Goldner.pdf)) and Weitzenfeld's Bayesian drive modeling ([Weitzenfeld](http://danielweitzenfeld.github.io/passtheroc/posts/bayes-nfl.html)). Open-source play-level strategy simulation from nflfastR data exists in [NFLSimulatoR](https://github.com/rtelmore/NFLSimulatoR). SportsLine states publicly that its player projections come from a Monte Carlo model in which virtual teams built from active rosters play the game thousands of times, with player statistics tracked per simulation ([SportsLine](https://www.sportsline.com/insiders/how-do-we-produce-player-projections/)); no method details are disclosed and none are implied here. No NFL literature in context prescribes a draw count; draw counts are set from target Monte Carlo error (Section 4.2 and Block XV).

Decision (PROPOSAL, corrected after review). The production engine is a play-level state-transition simulator with a reduced play-outcome model, referred to as Option C-reduced. It is play-level because the unit of transition is one play and every counting stat is emitted by a play. It is reduced because the play-outcome model is a small set of conditional component distributions estimated hierarchically, not a full play-design or tracking-level model. The drive-level Markov engine (Goldner-style absorbing chain over drive outcomes) is retained as the fallback baseline for benchmarking and as a sanity check on drive-outcome frequencies. The aggregate team-total engine is kept only as a benchmark.

State-transition algorithm.

State vector at play t:
S_t = (poss, q, clock_s, down, dist, yl100, score_home, score_away, to_home, to_away, half_flags, drive_id, play_idx_in_drive)
where poss is the team with the ball, q the quarter (5 for overtime), clock_s seconds remaining in the quarter, yl100 yards to the opponent goal line, to_* timeouts remaining.

Per-world context drawn once per world before play 1: active set A (Block XIV sampled availability), role states R (Block V), allocation concentrations alpha (Block VII), team latent rates theta (Block VI: pace, neutral pass rate, situational modifiers), efficiency parameters phi (Block IX), environment E (Block XI at the cut), matchup adjustments (Block XII if gated in).

```text
world(seed):
  draw A, R, alpha, theta, phi from their posteriors (parameter draw index m) and scenario draw index k
  S <- kickoff_state(coin_toss ~ Bernoulli(0.5), q=1, clock=900)
  while not game_over(S):
    if S.play_type_forced in {KICKOFF, PAT, FG_ATTEMPT, PUNT}: outcome <- special_teams_model(S, phi); S <- apply(S, outcome); continue
    # 1. play call
    call ~ Categorical(p_pass(S, theta), p_rush(S, theta), p_kneel(S), p_spike(S), p_fg(S, phi_k), p_punt(S))
    # 2. dropback branch
    if call == PASS:
      sack ~ Bernoulli(p_sack(S, phi_qb, phi_ol, phi_def))
      if sack: yards ~ SackYards(phi); emit(sack_taken to QB, sack to DST_def); go to clock
      scramble ~ Bernoulli(p_scramble(S, phi_qb))
      if scramble: yards ~ ScrambleYards(phi_qb); emit(carry and rushing_yards to QB, accounted as rush); go to clock
      target ~ Categorical(alpha_targets(A, R, zone(S)))          # Block VII allocation
      air ~ AirYards(phi_qb, phi_target, S); complete ~ Bernoulli(p_comp(air, phi_qb, phi_target, phi_def, E))
      if not complete: intercepted ~ Bernoulli(p_int(air, phi)); emit(attempt to QB, target to receiver, INT if intercepted with return yards ~ ReturnYards)
      else: yac ~ YAC(phi_target, phi_def, S); yards = air + yac; emit(attempt, completion, passing_yards to QB; target, reception, receiving_yards to receiver)
    elif call == RUSH:
      carrier ~ Categorical(alpha_carries(A, R, zone(S)))
      yards ~ RushYards(phi_carrier, phi_ol, phi_def, S, E); emit(carry, rushing_yards)
    fumble ~ Bernoulli(p_fumble(play, phi)); if fumble: lost ~ Bernoulli(p_lost); emit accordingly
    # 3. resolve field position and scoring
    S' <- advance(S, yards, turnover, out_of_bounds ~ Bernoulli(p_oob(play)))
    if touchdown(S'): emit(TD to scorer; passing_td to QB if pass); PAT decision ~ Categorical(p_xp, p_2pt(S'))
    if first_down(S'): reset down and dist
    if fourth_down_failed(S'): change possession
    # 4. clock
    elapsed ~ Elapsed(theta_pace, play, S, incomplete, out_of_bounds, timeout ~ TimeoutPolicy(S))
    S <- tick(S', elapsed); handle end of quarter, half, two-minute logic, kneel-down policy when leading and clock permits
  overtime per configured rule module if tied at end of q4
  return per-play event log
```

Player and team stats are the column sums of the per-play event log, so the accounting identities of Block XLIV hold by construction: every passing TD has exactly one receiver; team passing yards equal the sum of receiver receiving yards; team rush attempts equal the sum of carries including QB scrambles and kneel-downs (kneel-downs are tagged so downstream can include or exclude them per accounting convention); DST events are attributed to the defensive unit on the field for that play (Block XXII).

Component distribution families (each validated separately under Block XXXV): p_pass and p_sack logistic in state features and latent rates; AirYards and YAC as discretized two-part distributions (point mass at or below zero plus positive part) fit per player with shrinkage; RushYards as a discretized heavy-tailed mixture; Elapsed as a lognormal or gamma in pace and play type; all estimated forward-chain from nflverse pbp. Scrambles and sacks arise only from the dropback chain and are never re-allocated as rushes (REPO `external-research/system-review-2026-09-14/NFL_FORECASTING_SYSTEM_ADVERSARIAL_REVIEW.md`, section B4 and its rule that nothing is sampled twice). The exact nflverse pbp encoding of scrambles across the `pass`, `rush` and `qb_scramble` columns must be verified against the data dictionary before estimation; it is UNKNOWN here.

Situational structure required by the mandate and where it lives: possession alternation (change of possession rules), drives (drive_id increments on possession change), clock (Elapsed and tick), score state (in S and in theta modifiers), changing pass and run tendency (p_pass depends on score, clock, down, distance), red-zone entry (zone(S) switches allocation concentrations), touchdowns, field goals (p_fg and the kicker module, Block XXIII), punts, turnovers, sacks, scrambles, garbage time (theta modifiers as a function of score margin and time), kneel-downs (policy), overtime (module).

Draw-count procedure: N worlds per parameter draw are chosen so that the Monte Carlo standard error of the least stable exposed quantity is below the fraction of predictive standard deviation set in Section 4.2, computed with the nested-variance estimator of Block XV, not the independent-draw formula. Common random numbers are used across scenario comparisons, and seeds derive from the release manifest (Block XXXVIII).

Complexity of the reduced play model: per-play cost is a handful of categorical and scalar draws; a 16-game slate at 10^5 worlds per game is on the order of 10^8 plays, feasible on CPU with compiled kernels (Block XLII); this is an estimate, not a measurement.

Gates: G-X-1 accounting invariants exact in every world; G-X-2 simulated drives per game, plays per drive, drive-outcome frequencies and team totals reproduce chronological distributions (PIT and CEP); G-X-3 nested Monte Carlo SE reported for all exposed outputs; G-X-4 the drive-level baseline is run on the same releases and the play-level engine must not be worse on drive-outcome frequencies. Complexity: high. Uncertainty: high until G-X-2 is evaluated.

### Block XI: Weather, stadium, environment

Findings. Observed weather: ERA5 hourly 1940 to present at 0.25 degrees and ERA5-Land at 0.1 degrees with a 5-day delay ([Open-Meteo Historical Weather](https://open-meteo.com/en/docs/historical-weather-api)); NOAA ISD hourly observations for more than 14,000 active stations ([NOAA ISD](https://www.ncei.noaa.gov/products/land-based-station/integrated-surface-database)); Meteostat hourly with 2 to 3 hour delay and 30-day request limit ([Meteostat hourly](https://dev.meteostat.net/api/stations/hourly.html)). Forecasts as they existed before kickoff: Open-Meteo Historical Forecast API archives model runs from 2021 or 2022 onward as a stitched series ([Historical Forecast API](https://open-meteo.com/en/docs/historical-forecast-api)); this approximates a nowcast, not the forecast issued at T minus 72 hours. Roof and surface are in nflverse games.csv ([nfldata DATASETS](https://github.com/nflverse/nfldata/blob/master/DATASETS.md)). Effect sizes: the prior packet cites Wharton and Claremont weather studies; FG success falls with cold and rises with altitude and turf ([Clark, Johnson, Stimpson 2013](https://aaronwj.engin.umich.edu/wp-content/uploads/sites/546/2021/09/Clark-Johnson-Stimpson-2013.pdf)). Copying internet rules such as fixed wind penalties is prohibited by the mandate.

Correction after review: Open-Meteo documents a Single Runs API that returns the full forecast horizon of one individual model run selected by its UTC initialisation time with the `run=` parameter (example `run=2025-09-01T00:00`), preserving run structure for backtesting; ECMWF IFS HRES at 9 km is archived from March 2024 and most other models from 2026-04-02 ([Open-Meteo Single Runs API](https://open-meteo.com/en/docs/single-runs-api)). The Previous Runs API exposes fixed lead-time offsets of 1 to 7 days (for example `temperature_2m_previous_day1`), most models archived from January 2024 and GFS 2 m temperature back to March 2021 ([Open-Meteo Previous Runs API](https://open-meteo.com/en/docs/previous-runs-api)). Open-Meteo states that models are processed as soon as national services release them, that servers are eventually consistent, and that users should wait an additional 10 minutes after an update before treating it as available ([Open-Meteo model updates](https://open-meteo.com/en/docs/model-updates)); the per-run publication latency (initialisation time to availability) is displayed on that page dynamically and was not captured in this session, so it is UNKNOWN and must be measured before any run is admitted at a cut.

Recommendation (PROPOSAL). Two weather variables per game: observed (for training labels of efficiency effects, post-game only) and pre-kickoff forecast at the information cut (feature). For a cut C, the admissible run is the latest run with initialisation time t_init such that t_init plus measured availability latency L_model is at or before C; L_model is estimated from a self-collected log of (initialisation time, first-seen time) per model, and until that log exists the run is admitted only with `admissibility = UNPROVEN` and the feature is labeled WEATHER_PROXY. Historical reconstructions before the archive start (March 2024 for ECMWF IFS, April 2026 for others) fall back to the Previous Runs API offsets, also labeled WEATHER_PROXY. Usage licence and commercial terms for these APIs are shown on the pages as a form field and were not captured; they are UNKNOWN (registry rows). Effects are estimated as hierarchical coefficients on pass efficiency, pass rate, FG make probability and fumble rate, with roof interaction; effect sizes are learned, not imposed. Begin self-archiving forecasts for every stadium at fixed horizons (T minus 96, 72, 48, 24, 6 hours) immediately.

Gates: G-XI-1 weather features carry a horizon and source tag; G-XI-2 no observed weather column enters a pre-kickoff feature manifest. Unsupported: as-issued forecast history before the Open-Meteo archive start for the chosen model; unmeasured run latency. Complexity: low to medium.

### Block XII: Offensive line and defensive matchups

Findings. ESPN pass block and pass rush win rates use NGS tracking, a 2.5 second threshold and weak-link unit logic; data is published only in articles ([ESPN win rates 2026](https://www.espn.com/nfl/story/_/id/49672562/nfl-new-pass-block-push-rush-win-rates-formula-takeaways-analytics), [ESPN original FAQ](https://www.espn.com/nfl/story/_/id/24892208/creating-better-nfl-pass-blocking-pass-rushing-stats-analytics-explainer-faq-how-work)). Lawful machine-readable proxies: PFR pressure, blitz and hurry counts ([PFR passing dictionary](https://nflreadr.nflverse.com/articles/dictionary_pfr_passing.html)), FTN subset pass rushers, blitzers and box counts ([load_ftn_charting](https://nflreadr.nflverse.com/reference/load_ftn_charting.html)), and post-season participation coverage type ([load_participation](https://nflreadr.nflverse.com/reference/load_participation.html)). OL starter identity per week is available only post-game from gamebooks and snap counts; pre-game OL availability comes from Blocks I and XIV.

Recommendation (PROPOSAL). Unit-level latent strength for pass protection and run blocking estimated from pressure rate allowed, sack rate allowed and rush yards before contact proxies, adjusted for opponent, with availability of the five expected starters as a covariate. Defensive counterpart symmetric. Matchup enters efficiency (Block IX) only.

Gates: G-XII-1 incremental CRPS improvement over the no-matchup model chronologically; if not demonstrated, the component stays RESEARCH_ONLY. Unsupported: player-level pass-block win rates. Complexity: medium.

### Block XIII: Coaching and scheme

Findings. Coaches per game are in nflverse games.csv (home_coach, away_coach) ([nfldata DATASETS](https://github.com/nflverse/nfldata/blob/master/DATASETS.md)). New-coach effect analysis exists as a descriptive explainer with cluster-robust inference ([nflanalytic](https://nflanalytic.com/explainer-new-coach-effect.html)). Scheme indicators (motion, play action, RPO, screens, shotgun, no huddle) are in the FTN subset and pbp ([load_ftn_charting](https://nflreadr.nflverse.com/reference/load_ftn_charting.html)). Offensive coordinator histories are not in any dataset in context (UNKNOWN).

Recommendation (PROPOSAL). Coach identity as a random effect on pace, neutral pass rate and concentration, carried across teams with heavy shrinkage; a coaching change resets team random effects toward the coach's prior with widened variance. Scheme features are descriptive covariates for Blocks VI and IX, never forced rules.

Gates: G-XIII-1 forward-chain evidence of improvement over team-only effects. Unsupported: coordinator-level effects. Complexity: low.

### Block XIV: Injury modeling

Findings. Category semantics per the 2016 revision ([NFL revision](https://www.nfl.com/news/competition-committee-approves-revisions-to-injury-report-0ap3000000688693)). Empirical play rates for QB, RB, WR, TE 2017 to 2024 over more than 2,000 injuries: Questionable played 70.7 percent, Doubtful 6.9 percent ([Footballguys](https://www.footballguys.com/article/2025-chance-to-play-questionable-vs-doubtful)); an older 2008 to 2009 sample over more than 4,000 listings: Probable 68.27, Questionable 48.70, Doubtful 27.78 percent, with starters at 73.35, 57.85 and 31.14 ([TeamRankings](https://www.teamrankings.com/blog/nfl/nfl-injury-analysis-how-often-do-hurt-players-actually-play-1-of-4)). Both are secondary; the regime changed in 2016. nflverse injuries carries report and practice status with date_modified ((registry row nflverse_injuries)); the Wed to Fri progression is not preserved unless self-archived.

Recommendation (PROPOSAL). Availability model with two outputs per player-game: P(active) and a limitation distribution given active (share multiplier). Features: game status, practice pattern (DNP, LP, FP sequence), injury type, days since designation, team tendency, position, role. Estimation: hierarchical logistic with team and injury-type random effects, forward-chain only, with the two secondary sources used solely as sanity references, never as priors. IR, PUP, NFI and suspension are deterministic Tier 2 facts with return-eligibility rules, not probabilities. Post-return limitation is learned from snap share in the first two games back.

Gates: G-XIV-1 reliability of P(active) by status code and practice pattern; G-XIV-2 every Questionable player present as a two-world mixture in the simulator. Unsupported: player-level practice reports before the self-archive start for any day other than the final report. Complexity: medium.

### Block XV: Uncertainty decomposition and nested Monte Carlo error

Findings. ESTABLISHED: predictive uncertainty decomposes into aleatoric (within-world sampling), parameter (posterior over efficiency and rates), structural (availability, role and world-state mixtures) and Monte Carlo error. REPO `methodology/simulation_calibration.md` covers proper scores and clustered bootstrap. Correction after review: the earlier text quoted independent-draw formulas (sd divided by sqrt(N); sqrt(p(1 minus p) divided by N)); those are invalid for the nested design in which N worlds share one parameter draw, because worlds within a parameter draw are positively dependent.

Recommendation (PROPOSAL). Nested design with M parameter draws (index m), K scenario draws per parameter draw (index k; availability and role), and N worlds per (m, k) cell (index n). For any exposed quantity defined by an indicator or statistic Y_mkn (for example 1[X greater than line], or DK points), the estimator is the grand mean Y_bar. Its Monte Carlo variance is estimated by the ANOVA decomposition of the cell means, not by the pooled independent-draw formula:

Var_hat(Y_bar) = s_M^2 divided by M plus s_K^2 divided by (M K) plus s_N^2 divided by (M K N)

where s_M^2 is the sample variance of the M parameter-level means (each averaged over its K N worlds), s_K^2 the pooled within-parameter variance of the K scenario-level means, and s_N^2 the pooled within-cell variance of worlds. When M is small, report the parameter component with a t-based interval and increase M before increasing N, since the parameter component does not shrink with N. Equivalently, the conservative estimator treats the M parameter-level means as the independent units and reports s_M^2 divided by M; the finer decomposition shows which level to expand. The predictive variance components reported to the UX are the law-of-total-variance components (between parameter draws, between scenarios within parameter draw, within world), and the Monte Carlo error is reported separately as the standard error of the grand mean. Common random numbers across scenario comparisons reduce the variance of differences; for differences, the variance is computed on paired cell differences with the same decomposition.

Gates: G-XV-1 variance components sum to total within numerical tolerance; G-XV-2 the Monte Carlo standard error of every exposed probability is below the Section 4.2 fraction of its predictive standard deviation; G-XV-3 M is large enough that the parameter component's own standard error is below a declared fraction of the component. Complexity: low to medium.

### Block XVI: Probabilistic forecast validation

Findings. ESTABLISHED: proper scoring rules (log score, CRPS, Brier), PIT histograms, probabilistic versus marginal calibration ([Gneiting, Balabdaoui, Raftery 2007](https://sites.stat.washington.edu/raftery/Research/PDF/Gneiting2007jrssb.pdf)); for counts, randomized PIT and CEP logistic tests with quantile offsets, with the caution that CEP tests are less powerful than score-based tests ([Wei and Held 2014](https://www.zora.uzh.ch/id/eprint/102586/1/4-WeiHeld-cailibration2014.pdf)). REPO: `methodology/simulation_calibration.md`.

Recommendation. Evaluate every distributional output with CRPS and log score against named baselines; PIT diagnostics per family; CEP tests for counts at the Wei and Held quantile set; cluster standard errors by game and by team-week since player outcomes within a game are dependent. Report score differences with block-bootstrap intervals, not point improvements.

Gates: G-XVI-1 no gate passes on a point estimate alone; interval must exclude the baseline. Complexity: low to medium.

### Block XVII: Chronological and prospective validation

Findings. ESTABLISHED: rolling-origin evaluation with training only on observations before each test origin ([Hyndman](https://robjhyndman.com/hyndsight/tscv/)). The mandate forbids random splits. REPO: forward-chain tuning in `oas1-opponent-adjusted-strength-2026-09-17/`; certificate gates and falsification tests in the prior packet.

Recommendation. Every parameter, hyperparameter and calibration map is fit on data with publication time before the origin; the origin advances weekly; prospective (frozen before kickoff, scored after) logs are the only evidence admissible for DEPLOYABLE. Backtests are admissible for RESEARCH_ONLY. Section 4 gives the protocol.

Gates: G-XVII-1 manifest proves no artifact used has a publication time after the cut; G-XVII-2 prospective log has the required number of independent weeks, determined by the Section 4 power procedure. Complexity: low, but pervasive.

### Block XVIII: Prop modeling

Findings. Props are functionals of simulated draws: P(X greater than line), P(X less than line), P(X equals line) for integer lines. Unabated exposes a simulator that turns user projections into outcome distributions ([Unabated props simulator](https://unabated.com/tools/core/props-simulator)); Pinnacle publishes educational material on NFL prop value ([Pinnacle NFL props](https://www.pinnacle.com/betting-resources/en/educational/how-to-find-value-in-nfl-player-props)); Action Network shows a projection, the best available price, and an edge whose formula is not disclosed ([Action Network prop projections](https://www.actionnetwork.com/nfl/prop-projections)); Props.Cash scans lines and shows correlated hit rates without disclosing a model ([Props.Cash](https://props.cash/)); BettingPros shows a star Bet Rating without disclosed methodology ([BettingPros NFL props](https://www.bettingpros.com/nfl/props/)). None discloses distributional forms. No Gaussian shortcut is permitted without family-specific validation (mandate Part XVIII). REPO Hard Rock captures with timestamps establish the sportsbook timestamping standard.

Recommendation (PROPOSAL). Compute every prop probability from the same weighted world set (weights from Block XIX, uniform before calibration): P_over = sum over worlds of w_i 1[X_i greater than L]; P_under and P_push analogously; half lines have zero push; alternate lines reuse the same functional at other L; longest reception uses the per-play event log. Vig removal and hold are market-side computations for evaluation only (Block XX). Line movement and stale lines are evaluation-side timestamps: each market observation carries the sportsbook timestamp and the capture time, and a comparison is valid only if the release cut is at or before the market timestamp used.

I/O: input weighted worlds and market lines (evaluation only); output `prop_probability` records with MC SE (Block XV). Gates: G-XVIII-1 identical world ids and weight vector hash feed props, SGP and DFS in a release; G-XVIII-2 per-family PIT and CEP pass before the family is exposed; G-XVIII-3 monotonicity of P_over in L and over plus under plus push equals 1 in every record. Complexity: low given Block X.

### Block XIX: Prop calibration

Findings. ESTABLISHED: isotonic, Platt and beta calibration for binary probabilities ([Kull et al beta calibration](https://proceedings.mlr.press/v54/kull17a.html)); calibration and sharpness paradigm ([Gneiting 2007](https://sites.stat.washington.edu/raftery/Research/PDF/Gneiting2007jrssb.pdf)); discrete-aware PIT and CEP tests for counts ([Wei and Held 2014](https://www.zora.uzh.ch/id/eprint/102586/1/4-WeiHeld-cailibration2014.pdf)). Question posed by the mandate: calibrate raw stat distributions or event probabilities.

Decision (PROPOSAL, corrected after review; replaces the contradictory earlier text). Neither independent per-player marginal recalibration nor independent per-prop event recalibration is acceptable as an applied transform, because transforming marginals independently destroys the coherence of worlds: a receiver's recalibrated yards would no longer sum to the team's passing yards, and joint probabilities (SGP, DFS lineups) would no longer be consistent with the marginals. The design that preserves accounting and joint probabilities is world reweighting. Worlds are never altered; a single non-negative weight vector w over the worlds of a release is fit forward-chain so that the weighted marginal distributions satisfy calibration constraints, and every consumer (props, SGP, DFS scoring, ownership inputs) reads the same weighted worlds. Because each world remains an internally consistent game, every accounting identity holds under any weights, and joint probabilities are computed from the same weights as marginals.

Method. Let families f (for example receiving yards for WR) and calibration bins b (PIT deciles or exceedance quantiles at the Wei and Held quantile set). From past releases at origins strictly before the evaluation origin, estimate the miscalibration map per family as target bin masses pi_fb (uniform PIT implies pi_fb equals 1 divided by B). For the current release, find w minimizing the Kullback-Leibler divergence from uniform weights subject to, for each family and bin, the weighted mass of worlds whose realized-analogue statistic falls in bin b equalling pi_fb within tolerance; this is iterative proportional fitting (raking) over families with the family maps as targets. Regularize by capping weight ratios and by shrinking the family maps toward identity with a hierarchical prior across players and seasons. Post-hoc event-probability calibration (isotonic or beta on P_over) is computed as a diagnostic only and must be close to identity for the family to be DEPLOYABLE; it is never applied to exposed outputs. Where the raking constraints cannot be met within the weight-ratio cap, the family is not calibrated for that release and the reason code CALIBRATION_INFEASIBLE is emitted.

Minimum sample size per family is derived by the Section 4.2 precision procedure (width of the calibration-map interval that would change a verdict), not fixed here.

I/O: input worlds and past-release PIT records; output weight vector (hash recorded in the manifest) and per-family calibration state. Gates: G-XIX-1 post-hoc diagnostic calibration slope interval contains 1 and intercept contains 0 after reweighting; G-XIX-2 family maps fit on origins strictly before evaluation origins; G-XIX-3 weight-ratio cap respected and effective sample size of weighted worlds above the Section 4.2 floor; G-XIX-4 accounting identities re-verified on weighted aggregates (they hold by construction; the test guards implementation errors). Complexity: medium.

### Block XX: Market comparison

Findings. No-vig conversion and expected value formulas are documented by market tool vendors ([OddsJam no-vig](https://oddsjam.com/betting-education/no-vig-fair-odds)). Pinnacle is treated as a sharp reference by such tools. Market data is evaluation data only (mandate Part XX). REPO: de-vig benchmark in `methodology/simulation_calibration.md`; Hard Rock capture files record sportsbook timestamps.

Recommendation. Compare model P_over with de-vigged market P_over per book and timestamp; report log-score difference and a closing-line comparison only as a benchmark table; never feed market probability into any football layer (static manifest check). Push handling and alternate lines use the same functional.

Gates: G-XX-1 market columns absent from football manifests; G-XX-2 model versus de-vig market score reported with intervals. Complexity: low.

### Block XXI: Same game parlay and correlation

Findings. REPO `nfl-fullslate-dfs-construction-2026-09-18/` Part 2 gives a correlation taxonomy with measured values. Joint probabilities emerge from worlds; SGP prices from books are correlation-adjusted and are evaluation-only.

Recommendation. P(leg1 and leg2) = mean over worlds of the product of indicators; report MC SE, which grows for rare joints; require a draw count sufficient for the joint (Section 4). Correlation is a diagnostic, not an input.

Gates: G-XXI-1 joint probability MC SE below threshold derived from Section 4. Complexity: low.

### Block XXII: Native DST model

Findings (corrected after review). DraftKings DST scoring: sack 1, interception 2, fumble recovery 2, punt or kickoff or FG return TD 6, interception or fumble return TD 6, blocked punt or FG return TD 6, safety 2, blocked kick 2, 2-point conversion or extra-point return 2; points allowed brackets 0:plus 10, 1 to 6:plus 7, 7 to 13:plus 4, 14 to 20:plus 1, 21 to 27:0, 28 to 34:minus 1, 35 plus:minus 4. The scoring notes state that Points Allowed only includes points surrendered while the DST is on the field and does not include points given up by the team's offense, for example points off offensive turnovers; the enumerated plays that count as points allowed are rushing TDs, passing TDs, offensive fumble recovery TDs, punt return TDs, kick return TDs, FG return TDs, blocked FG TDs, blocked punt TDs, 2-point conversions, 2-point conversion or extra-point returns, extra points and field goals; and a fumble recovery is awarded to a DST if the team's offense recovers a fumble by the opposing defense after an offensive turnover ([DraftKings RulesAndScoring.json](https://api.draftkings.com/rules-and-scoring/RulesAndScoring.json)). The earlier text that took points allowed from the opponent's total score was wrong.

Recommendation. Points allowed is a scoring-rule-specific functional of attributed scoring events in the world's play log, not the opponent's score. For DST of team T in a world: PA_T = sum over opponent scoring events e of points(e) times 1[e is in the DK enumerated set] times 1[unit on field for T at e is DST], where the enumerated set excludes opponent defensive or special-teams scores against T's offense (pick-six, fumble-return TD, safety on T's offense) and any conversion attempts following them. The engine's event log must therefore tag each scoring play with the scoring unit (offense, defense, special teams) of the scoring team and the on-field unit of the conceding team. Sacks, interceptions, fumble recoveries (including the offense-recovers-after-turnover case), return TDs, safeties and blocked kicks are emitted by the play model and attributed to the DST unit. Rules constants and text are versioned by hash of the JSON capture, since a rules change would change the functional.

Gates: G-XXII-1 sack, INT, FR and return-TD rates PIT chronologically; G-XXII-2 points-allowed bracket reliability computed with the enumerated-set functional against DK contest CSV DST points (Block XXIV gate G-XXIV-1 must reconcile DST points exactly); G-XXII-3 unit tagging present on every scoring event. Complexity: medium.

### Block XXIII: Kicker model

Findings. FG make probability from 11,896 attempts 2000 to 2011: distance coefficient minus 0.106 per yard, cold below 50F minus 0.341, artificial turf plus 0.299, altitude at least 4,000 feet plus 0.694, constant 5.953 ([Clark, Johnson, Stimpson 2013](https://aaronwj.engin.umich.edu/wp-content/uploads/sites/546/2021/09/Clark-Johnson-Stimpson-2013.pdf)). Kicker attempts depend on drive end states.

Recommendation (PROPOSAL). Re-estimate the logistic model forward-chain with kicker random effects and current-era data from pbp; attempts and distances emerge from Block X; the published coefficients are a sanity reference, not production parameters.

Gates: G-XXIII-1 make probability reliability by distance bucket. Complexity: low.

### Block XXIV: DFS projection transformation

Findings. Classic scoring constants and Showdown captain 1.5x multiplier are in the same JSON ([DraftKings RulesAndScoring.json](https://api.draftkings.com/rules-and-scoring/RulesAndScoring.json)). Bonuses (300 passing, 100 rushing, 100 receiving) are threshold events and make DK points a nonlinear functional of the stat vector.

Recommendation. Apply the scoring transform per world to the stat vector so that bonus probabilities and DST dependencies are exact; never transform means. Rules are versioned per season in the manifest.

Gates: G-XXIV-1 recomputed points, including DST points allowed via the Block XXII enumerated-set functional, match DK contest CSV points on historical contests exactly (rounding to two decimals). Complexity: low.

### Block XXV: DFS ownership model

Findings. Contest standings CSVs include Rank, Points, Lineup, Roster Position, %Drafted and FPTS, downloadable after lock, live and final ([DraftKings transparency KB](https://support.draftkings.com/dk/en-us/how-does-draftkings-keep-fantasy-sports-contests-transparent?id=kb_article_view&sysparm_article=KB0010720)). Dirichlet-multinomial field generation is documented ([Haugh and Singal](https://arxiv.org/abs/1806.03142)). REPO `nfl-fullslate-dfs-construction-2026-09-18/` Part 7.

Recommendation. Ownership model consumes football outputs plus salaries and slate structure, downstream only; labels from self-archived contest CSVs. Ownership never touches football layers.

Gates: G-XXV-1 ownership calibration by salary tier; G-XXV-2 salary identity unresolved rate blocks only DFS scopes. Complexity: medium.

### Block XXVI: Field lineup generation

Findings. Haugh and Singal Dirichlet-multinomial with constraint sampling; SaberSim and SimSlate describe ownership-faithful field processes without formulas ([SimSlate duplication](https://simslate.com/edge/dfs-lineup-duplication/)). REPO Part 14.

Recommendation. Generate field lineups by constrained sampling from the ownership distribution with stacking propensities learned from contest CSVs; validate against realized field lineup features.

Gates: G-XXVI-1 realized stack rates and ownership marginals inside simulated intervals. Complexity: medium.

### Block XXVII: Duplication model

Findings. SimSlate describes duplication as a function of joint ownership of all nine players and a crowd-width across 50,000 simulated contests, with no published formula ([SimSlate](https://simslate.com/edge/dfs-lineup-duplication/)). REPO Part 8.

Recommendation (PROPOSAL). Expected duplicates of lineup l in a field of size F = F times P_field(l), where P_field(l) is the field generator's probability of exactly l; estimate by field simulation, calibrate against realized duplicates from contest CSVs.

Gates: G-XXVII-1 predicted versus realized duplicate counts on held-out contests chronologically. Complexity: medium.

### Block XXVIII: Contest simulation

Findings. REPO Part 15. Contest payout structures are per contest and downstream.

Recommendation. Joint simulation: the same worlds score both our lineups and the field; payouts split across duplicates; report distribution of ROI with MC SE.

Gates: G-XXVIII-1 realized finish percentile PIT across entered contests. Complexity: medium.

### Block XXIX: Portfolio optimization

Findings. REPO `external-research/nfl-fullslate-dfs-construction-2026-09-18/nfl-fullslate-dfs-lineup-construction.pplx.md` (commit dea047e, 2026-09-18) Part 13 records: Hunter, Vielma and Zaman formalize top-heavy contests as maximizing the probability that at least one entry wins, show the objective is submodular so greedy sequential construction has a quality guarantee, and use pairwise lineup marginals as the tractable proxy for portfolio dependence ([Hunter, Vielma, Zaman](https://arxiv.org/abs/1604.01455)); a risk-neutral formulation for double-up versus top-heavy settings appears in [Management Science, How to Play Fantasy Sports Strategically (and Win)](https://pubsonline.informs.org/doi/10.1287/mnsc.2019.3528); Part 13 also records industry exposure-cap conventions as PRO_STATEMENT and INDUSTRY_CONVENTION, not as rules.

Recommendation (PROPOSAL). Objective is chosen per contest type and evaluated on the same weighted worlds and field simulation as Block XXVIII. Let L be candidate lineups, s_l(i) the DK points of lineup l in world i (Block XXIV), F_i the simulated field in world i (Block XXVI), pay(rank, contest) the payout table, and w_i the world weights.

Top-heavy: maximize over portfolio P of size E the quantity sum over i of w_i times 1[max over l in P of payout_i(l) at least top tier], approximated by greedy sequential addition of the lineup with the largest marginal gain, with pairwise lineup correlation computed from the world scores as the dependence proxy per Hunter, Vielma and Zaman; per-lineup constraints: expected points floor, variance floor, maximum overlap with lineups already in P, salary cap and roster rules, exposure caps as tunable constraints rather than fixed percentages.

Double-up and cash: maximize sum over i of w_i times 1[s_l(i) at least cash line_i], where cash line_i is the simulated field's payout-line score in world i; single lineup or a small set with minimum overlap.

Risk objective across a slate: maximize expected payout minus lambda times CVaR_alpha of loss over worlds, with lambda and alpha as owner-set product parameters, never model inputs. Bankroll fraction is a downstream parameter (fractional Kelly on the simulated payout distribution is one admissible rule) and never touches football layers.

I/O: input world lineup scores, field simulation, payout table; output portfolio, expected payout distribution, exposure report, MC SE (Block XV). Benchmark: realized payout of the portfolio versus the realized payout of the top-E individually optimal lineups on the same slates, chronologically. Gates: G-XXIX-1 portfolio objective evaluated on the same weighted worlds hash as props (coherence); G-XXIX-2 realized-payout PIT across entered contests; inherits all D1 to D4 gates. Complexity: medium.

### Block XXX: Showdown theory

Findings. Captain earns 1.5x the standard point value for each statistic and costs more salary; FLEX eligibility is QB, WR, RB, TE, K, DST; a player cannot be both Captain and FLEX in one lineup ([DraftKings RulesAndScoring.json](https://api.draftkings.com/rules-and-scoring/RulesAndScoring.json)); ETR publishes Showdown primers ([ETR Showdown 101](https://establishtherun.com/nfl-showdown-101/)). Descriptive patterns are not rules to force (mandate Part XXX).

Recommendation. Showdown is the same weighted worlds with the Showdown scoring transform (captain multiplier applied per world to the chosen captain's stat vector, including bonuses) and roster constraint; captain choice and lineup construction are evaluated by simulated contest outcomes (Block XXVIII), not heuristics. Because a Showdown slate is one game, field duplication is far higher and the duplication model (Block XXVII) is a required gate for D2.

### Block XXXI: Classic DFS

Findings and dependency (versioned). Site rules from the DK JSON: 9 roster spots, 1 QB, 2 RB, 3 WR, 1 TE, 1 FLEX (RB, WR, TE), 1 DST; players from at least two games; $50,000 cap; players lock at their game start; player pools may be adjusted up to 48 hours before lock; a Non Late Swap variant exists (game type 107) ([DraftKings RulesAndScoring.json](https://api.draftkings.com/rules-and-scoring/RulesAndScoring.json)). The correlation taxonomy with measured values, stacking theory, bring-backs, negative-correlation tolerance, salary allocation, late swap, optimizer failure modes and module list are in REPO `external-research/nfl-fullslate-dfs-construction-2026-09-18/nfl-fullslate-dfs-lineup-construction.pplx.md` (commit dea047e) Parts 1 to 6, 9, 16, 20, 21 and 23; that report's own standing caveats (its Section III) apply and are not repeated here.

Recommendation. Correlations are not inputs: they emerge from the worlds, and the REPO measured values are gate targets (G-XXXI-1 simulated QB-to-WR1 and QB-to-opposing-WR correlations fall inside the REPO measured intervals chronologically). Late swap consumes availability events from Block XXXVII: on a lock-time event the unlocked roster spots are re-optimized against re-simulated worlds with the same release lineage. Salary allocation constraints are expressed as constraints in Block XXIX, not as rules of thumb.

### Block XXXII: Benchmarks

Findings. Baselines hierarchy: persistence and position means (internal), de-vigged market (external, evaluation only), and independent public projections for reference only; commercial projections must not be labels (standing rule). REPO `system-review-2026-09-14/industry_benchmark.md` and `ADDENDUM_FANTASY_CRUNCHER_BENCHMARK.md`.

Recommendation. Every gate names its baseline; improvements are reported as score differences with intervals.

### Block XXXIII: Feature engineering

Findings. Feature manifests with publication times are required (Block XXXVIII). Model-derived pbp columns are exempted only by declaration.

Recommendation. Feature store keyed by (entity, as_of_cut) with source_id and published_at per feature; static linter rejects features whose source_class is market or whose published_at exceeds the cut.

### Block XXXIV: Machine learning model families

Findings. Hierarchical GLMs for rates, beta and Dirichlet-multinomial for shares, gradient boosting as a challenger with monotone constraints; ML for betting is reviewed in the literature ([systematic review](https://arxiv.org/html/2410.21484v1)) with no NFL-specific superiority established.

Recommendation. Interpretable hierarchical models as champions; boosted models as challengers under the same forward-chain protocol; no promotion based on complexity.

### Block XXXV: Distributional modeling

Findings. Count families: Poisson, negative binomial, zero-inflated and hurdle variants; yards: mixtures or per-play sampling; discrete-aware calibration ([Wei and Held](https://www.zora.uzh.ch/id/eprint/102586/1/4-WeiHeld-cailibration2014.pdf)). Under the play-level engine of Block X, player yardage distributions emerge from per-play draws rather than a parametric family, which is the preferred path; parametric families are used for per-play components only.

Gates: family choice is validated per component by CRPS and PIT.

### Block XXXVI: Interpretability

Recommendation. Every projection carries a decomposition: availability contribution, role contribution, volume contribution, allocation contribution, efficiency contribution, matchup contribution, each with its source facts; UX renders this per Block XLVI. No SHAP-style post hoc explanation replaces the structural decomposition.

### Block XXXVII: Update and event engine

Findings. REPO `own-nfl-data-network` Section 10 (live inactives) and the Week 2 capture reports. Elevation reversion timing and inactive timing are fixed by rule ([CBA Article 33 Section 5](https://overthecap.com/collective-bargaining-agreement/article/33/section/5)).

Recommendation (PROPOSAL). Event-sourced state: every capture is an immutable event; a projection release is a materialized view at a cut; late events (inactives at T minus 90) trigger re-simulation of affected games only, with a new release id; downstream products receive the release id and must re-verify their gates.

Gates: G-XXXVII-1 release id embedded in every output row; G-XXXVII-2 re-simulation latency budget measured.

### Block XXXVIII: Data vintaging and reproducibility

Findings. nflverse assets are overwritten in place with no native vintages except depth charts; stat corrections land Wed to Thu ([nflverse schedule](https://nflreadr.nflverse.com/articles/nflverse_data_schedule.html)). Prior packet covers DVC, Great Expectations, pandera, Dagster, OpenLineage, SLSA, numpy SeedSequence.

Recommendation. Content-addressed raw store (sha256), manifest per release listing every input asset with retrieval time, size, hash and declared published_at; seeds derived from the manifest hash; parquet sinks partitioned by season and week ([Polars sinks](https://docs.pola.rs/user-guide/lazy/sources_sinks/)).

### Block XXXIX: Model registry and promotion

Findings. SR 11-7 defines model risk as adverse consequences from incorrect or misused outputs and prescribes inventory, documentation, independent validation and effective challenge ([SR 11-7](https://www.federalreserve.gov/boarddocs/srletters/2011/sr1107a1.pdf)). REPO: eight-rule promotion standard is not replaced or renumbered; Contract 3 is not modified retroactively.

Recommendation. Registry entries carry: component id, version, manifest hash, gate results with intervals, verdict, owner decision items; promotion only through Section 4 protocol.

### Block XL: Observability

Recommendation. Per release: gate dashboard, freshness by source (retrieved_at versus expected cadence), MC SE, calibration drift, identity unresolved counts, event latency. Alerts are gate transitions, not thresholds on raw metrics.

### Block XLI: Data quality gates

Findings. Row-count and schema expectations (Great Expectations, pandera in prior packet); nflverse stat corrections change bytes mid-week.

Recommendation. Per asset: schema, row count band, hash change log, null-rate band per key column, key uniqueness, referential integrity to identity; any failure marks the asset STALE_OR_INVALID and blocks scopes that depend on it.

### Block XLII: Performance and compute

Findings. Polars lazy scans push projection and predicate into readers and sinks stream to partitioned parquet ([Polars](https://docs.pola.rs/user-guide/lazy/sources_sinks/)). Prior packet lists NumPy, Numba, JAX options.

Recommendation. Vectorize worlds as arrays (world, play) with Numba kernels for the drive loop; store per-world player stats as long parquet; target a full slate of 16 games at N worlds within the latency budget set by Block XXXVII; no GPU dependency at this stage.

### Block XLIII: Storage and schemas

See Section 3.

### Block XLIV: Testing strategy

Recommendation. Invariant tests (accounting identities, sum constraints, monotonicity of P_over in line, push plus over plus under equals 1), golden manifests, leakage tests (published_at greater than cut must fail), replay tests on frozen captures, property-based tests on the scoring transform against DK contest CSV points.

### Block XLV: Known NFL modeling failure modes

Recorded, with the preventing gate: absence-implies-active (G-I-2); scramble accounting (`pass` equals 1 and `rush` equals 0 on scrambles in nflverse pbp; REPO handoff) (G-X-1); stat corrections mid-week (G-XLI hash log); using current rosters for past weeks (G-XVII-1); using model-derived columns as inputs (manifest linter); Gaussian shortcuts (G-XVIII-2); market leakage (G-XX-1); confusing accounting improvements with forecasting gains (Block XXXII baselines); independent marginal recalibration that breaks world coherence (G-XIX-4 and the reweighting design); DST points allowed taken from the opponent's score (G-XXII-3); using a weather run before its publication latency is known (WEATHER_PROXY reason code); manual player tuning (prohibited by standing rule; no gate can be satisfied by manual edits since edits change the manifest hash without a validated component).

### Block XLVI: Product UX and decision layer

Recommendation. Verdict first, then projection, distribution, uncertainty decomposition, evidence list with timestamps, reason codes, data freshness, calibration state, blockers, last update. Non-sports precedent: SR 11-7 reporting component and effective challenge ([SR 11-7](https://www.federalreserve.gov/boarddocs/srletters/2011/sr1107a1.pdf)).

### Block XLVII: Competitive landscape (not ranked)

All fifteen named products were inspected on at least one public page in this session (nine of them in revision 2). The table records exposed features, disclosed methodology, and what remains proprietary; it does not rank. Observed marketing claims are not treated as validation.

| Product | Publicly exposed features | Disclosed methodology | Proprietary or unknown |
|---|---|---|---|
| PFF | per-play grades 0 to 100, more than 200 fields per play ([PFF grades](https://www.pff.com/grades)) | plus or minus 2 per play, position rubrics, adjustment and normalization described in prose | grader identity, inter-rater reliability, data access |
| FTN | charting glossary and paid catalog with PBP and charting feeds ([FTN data points](https://www.ftndata.com/data-points), [FTN catalog](https://ftnfantasy.com/ftn-data-nfl-catalog)) | field definitions | charting protocol, QA |
| Establish The Run | rankings, PROE, Showdown primers ([ETR rankings FAQ](https://establishtherun.com/establish-the-run-nfl-rankings-faq/)) | process descriptions | projection model |
| RotoGrinders | site-specific projections, $ per point value, ownership (pOWN%), THE BLITZ projection system ([RotoGrinders FAQ](https://rotogrinders.com/pages/rotogrinders-daily-fantasy-projections-faq-129417), [THE BLITZ](https://rotogrinders.com/the-blitz)) | algorithm per sport tuned by staff and adjusted daily by hand for news (FAQ last updated 2015) | algorithm; manual adjustment protocol |
| NumberFire | player projections, matchup analysis ([NumberFire how it works](https://www.numberfire.com/info/how-it-works/)) | similarity-based: historical comparable players, comparable team styles, combined similarity weighting into a projection algorithm | similarity metric, algorithm |
| FantasyLabs | Plus/Minus (actual minus salary-based expectation), Pro Trends, Consistency, Upside, Leverage, ownership projections ([FantasyLabs glossary](https://support.fantasylabs.com/hc/en-us/articles/214870428-Glossary-of-Terms-NFL)) | expectation is a function of salary from a historical salary and performance database | projection sources, trend weighting |
| Stokastic | projections updated hourly on game day, projected field ownership, boom and bust probabilities, top stacks, contest simulations, downloadable data ([Stokastic NFL](https://www.stokastic.com/nfl)) | states that it simulates entire contests; no model description | all modeling |
| SaberSim | contest sims ([SaberSim](https://support.sabersim.com/en/articles/12079199-how-contest-sims-work)) | ownership-faithful field process described in prose | field generator |
| Fantasy Points | DK and FD DFS projections and rankings ([Fantasy Points DFS](https://www.fantasypoints.com/nfl/projections/dfs)) | built on Fantasy Points Data and advanced statistics; rankings by points per dollar | projection model |
| SportsLine | player projections, props, fantasy points, outcome probability tiers ([SportsLine](https://www.sportsline.com/insiders/how-do-we-produce-player-projections/)) | Monte Carlo simulation with virtual teams from active rosters played thousands of times; a Vegas Line Expectation adjusts fantasy projections toward the betting line (a practice this project forbids upstream) | simulator internals |
| Action Network | prop projections, best price across tracked books, edge ([Action Network](https://www.actionnetwork.com/nfl/prop-projections)) | projections attributed to a named analyst; edge scaled by statistic; no formula | projection method, edge formula |
| Unabated | props simulator turning projections into distributions ([Unabated](https://unabated.com/tools/core/props-simulator)) | user-supplied projections | distribution family |
| OddsJam | positive EV and no-vig tools ([OddsJam no-vig](https://oddsjam.com/betting-education/no-vig-fair-odds)) | fair-odds formulas | sharp-book weighting |
| Props.Cash | line scanning across books, real-time injury and lineup updates, correlated prop hit rates, filters ([Props.Cash](https://props.cash/)) | none beyond expected-value language | any model |
| BettingPros | prop analyzer with line, over and under odds, pick, star Bet Rating ([BettingPros](https://www.bettingpros.com/nfl/props/)) | none disclosed on the analyzer page | rating method |
| SimSlate | duplication calculator and 50,000-contest sims ([SimSlate](https://simslate.com/edge/dfs-lineup-duplication/)) | joint ownership drives duplication | formula |

Product gaps common to the inspected pages: none exposes per-projection point-in-time provenance, explicit unsupported states, a single world set powering props and DFS, prospective calibration logs or machine verdicts. Two disclosed practices conflict with this project's rules and are recorded as such: SportsLine's betting-line adjustment of projections and RotoGrinders' manual news adjustment.

### Block XLVIII: Professional sportsbook and quant processes

Findings. No primary talk or paper from a sportsbook trading desk disclosing internal NFL prop pricing methodology was found in this session; vendor educational pages exist ([Pinnacle NFL props](https://www.pinnacle.com/betting-resources/en/educational/how-to-find-value-in-nfl-player-props)). Applicable non-sports practice: SR 11-7 separation of model development, independent validation and ongoing outcomes analysis; documented model inventory; change control ([SR 11-7](https://www.federalreserve.gov/boarddocs/srletters/2011/sr1107a1.pdf)); forecasting practice of calibration and sharpness ([Gneiting 2007](https://sites.stat.washington.edu/raftery/Research/PDF/Gneiting2007jrssb.pdf)). Do not imply access to proprietary methods (mandate Part XLVIII).

Recommendation. Adopt the separation of model, pricing and risk as an organizational invariant: the football model has no access to prices; the market-comparison layer reads prices and model outputs; a validation function independent of the component author signs gates. Evidence gap recorded in Section 7.

## 3. Deliverable 4: Typed schema proposals (PROPOSAL)

Conventions for every table: `schema_version` (semver string); all timestamps are UTC ISO 8601 with explicit suffix `_utc`; `published_at_utc` is the source's own publication time or null with `published_at_status` in {EXACT, PAGE_METADATA, UNKNOWN}; `retrieved_at_utc` is always present; identity namespaces are prefixed (`gsis:`, `espn:`, `pfr:`, `dk:`, `fd:`); units are stated in column names (`_yards`, `_seconds`, `_mph`, `_f`); missing values use null plus a companion `_status` enum, never sentinel numbers; `world_id` and `release_id` align every downstream row to one simulation release; accounting conventions follow nflverse pbp field names with explicit overrides (`scramble_is_rush = true` in the engine's canonical stats).

### 3.1 raw_capture

```json
{"schema_version":"1.0.0","capture_id":"cap_01J...","source_id":"nfl_inactives_article","url":"https://www.nfl.com/news/nfl-week-2-inactives-players-ruled-out-sunday-14-games-2026","retrieved_at_utc":"2026-09-20T16:31:07Z","published_at_utc":null,"published_at_status":"PAGE_METADATA","sha256":"9c1f...","bytes":184233,"content_type":"text/html","parser_version":"inactives_html@0.3.1","storage_uri":"raw/2026/09/20/9c1f....html"}
```

### 3.2 player_state_at_cut

```json
{"schema_version":"1.0.0","player_id":"gsis:00-0036XXX","team":"IND","game_id":"2026_02_IND_KC","information_cut_utc":"2026-09-20T22:30:00Z","roster_status":{"value":"ACT","tier":2,"capture_id":"cap_...","published_at_status":"UNKNOWN"},"injury_game_status":{"value":"QUESTIONABLE","tier":3,"capture_id":"cap_..."},"practice_pattern":{"value":["DNP","LP","FP"],"tier":3},"depth_rank":{"value":2,"pos_grp":"RB","source":"nflverse_depth_charts","dt_utc":"2026-09-20T12:14:30Z","tier":6},"gameday_status":{"value":"GAMEDAY_STATUS_UNKNOWN","absent_from_inactives_capture":false,"tier":1},"conflicts":[],"note":"estimated P(active) is not stored here; see availability output"}
```

### 3.3 identity_resolution

```json
{"schema_version":"1.0.0","axis":"salary","platform":"dk","slate_id":"dk:12345","platform_name":"Tyler Goodson","platform_player_id":null,"resolved_player_id":"gsis:00-0037XXX","confidence":"STRONG","evidence":["name_exact","team_match","position_match","unique_candidate"],"resolved_at_utc":"2026-09-20T15:00:00Z","blocks_scopes":[]}
```

Confidence enum: EXACT_ID, STRONG, WEAK, AMBIGUOUS, UNRESOLVED. WEAK, AMBIGUOUS and UNRESOLVED set `blocks_scopes` to the DFS scopes for that slate only.

### 3.4 release_manifest (corrected after review)

Two release kinds are distinguished. LIVE releases are produced at the cut from inputs whose `retrieved_at_utc` is at or before the cut. RECONSTRUCTION releases are produced later for backtesting and must prove, for every input, that the exact version used was available at the cut: either a native publication timestamp at or before the cut (`published_at_status = EXACT`), or a self-archived vintage whose retrieval time is at or before the cut. An input lacking either proof sets `admissibility = UNPROVEN` for the whole release; UNPROVEN releases may be analyzed but never count toward prospective evidence or DEPLOYABLE verdicts. The earlier example (a September 20 cut using an asset retrieved September 21 with no publication timestamp) is exactly the pattern this field rejects.

```json
{"schema_version":"1.1.0","release_id":"rel_2026w02_live_003","release_kind":"LIVE","information_cut_utc":"2026-09-20T16:35:00Z","admissibility":"PROVEN","inputs":[{"source_id":"nflverse_depth_charts","asset":"depth_charts_2026.parquet","vintage_filter":"dt <= 2026-09-20T16:35:00Z","sha256":"706d57ecaa6c...","retrieved_at_utc":"2026-09-20T16:20:11Z","published_at_utc":"2026-09-20T12:14:30Z","published_at_status":"EXACT","availability_proof":"RETRIEVED_BEFORE_CUT"},{"source_id":"nfl_inactives_article","capture_id":"cap_01J...","sha256":"9c1f...","retrieved_at_utc":"2026-09-20T16:31:07Z","published_at_status":"PAGE_METADATA","availability_proof":"RETRIEVED_BEFORE_CUT"}],"component_versions":{"availability":"0.4.0","role":"0.2.1","simulator":"C-reduced-0.1.0","calibration_weights":"0.1.0"},"world_weights_sha256":"...","seed_root":"sha256(manifest without this field)","n_param_draws":50,"n_scenario_draws":20,"n_worlds_per_cell":2000,"code_commit":"a4c5cadb"}
```

availability_proof enum: RETRIEVED_BEFORE_CUT, PUBLISHED_BEFORE_CUT_EXACT, UNPROVEN. A RECONSTRUCTION release lists the same fields and sets `release_kind = RECONSTRUCTION`.

### 3.5 world_player_stats (long, one row per world, player)

Columns: release_id, param_draw_id (uint16), scenario_draw_id (uint16), world_id (uint32), world_weight (float64, from Block XIX), game_id, player_id, team, snaps_offense (int), routes_proxy (int, status enum), targets, receptions, receiving_yards, receiving_td, carries, rushing_yards, rushing_td, pass_attempts, completions, passing_yards, passing_td, interceptions, sacks_taken, scrambles, fumbles_lost, longest_reception_yards, two_pt, fg_attempts, fg_made, xp_made. Invariants: sums by team equal world_team_stats; scrambles counted as carries.

### 3.6 world_team_stats

Columns: release_id, param_draw_id, scenario_draw_id, world_id, world_weight, game_id, team, points, drives, plays, pass_attempts, rushes, sacks_allowed, turnovers, td, fg_made, punts, time_of_possession_seconds, dst_points_allowed_dk (enumerated-set functional of Block XXII, not the opponent's score), opponent_points_total, dst_sacks, dst_int, dst_fr, dst_td, dst_safety, dst_blocked_kick, dst_2pt_return. A companion `world_scoring_events` table holds one row per scoring play with scoring_team, scoring_unit (OFFENSE, DEFENSE, SPECIAL_TEAMS), conceding_unit_on_field, points, and play_id.

### 3.7 prop_probability

```json
{"schema_version":"1.0.0","release_id":"rel_2026w02_001","player_id":"gsis:...","family":"receiving_yards","line":62.5,"p_over":0.512,"p_under":0.488,"p_push":0.0,"mc_se":0.0011,"calibration_state":"FAMILY_CALIBRATED_v0.1.0","verdict":"RESEARCH_ONLY","reason_codes":["PROSPECTIVE_WEEKS_INSUFFICIENT"],"uncertainty":{"aleatoric":0.71,"parameter":0.18,"structural":0.11}}
```

### 3.8 gate_result

```json
{"schema_version":"1.0.0","release_id":"rel_...","gate_id":"G-X-1","component":"simulator","status":"PASS","statistic":0.0,"interval":[0.0,0.0],"baseline":"exact_invariant","evaluated_on":"worlds","evaluated_at_utc":"2026-09-21T02:00:00Z","evidence_uri":"gates/rel_.../G-X-1.json"}
```

Status enum: PASS, FAIL, NOT_EVALUATED, NOT_APPLICABLE, INSUFFICIENT_DATA.

### 3.9 weather_at_cut

Columns: game_id, stadium_id, horizon_hours, source_id, issued_at_utc (or null with status), valid_at_utc, wind_speed_10m_mph, wind_gust_mph, temp_f, precip_prob, precip_mm, roof, surface, is_proxy (bool, true for stitched historical forecasts).

### 3.10 dfs_slate and dfs_lineup (downstream only)

dfs_slate: platform, slate_id, game_type (CLASSIC, SHOWDOWN), rules_version (hash of DK rules JSON capture), salary rows keyed by platform identity with identity_resolution reference. dfs_lineup: release_id, lineup_id, entries, projected_points_distribution reference (world set), ownership_estimate, duplication_estimate, contest_sim reference, verdict.

## 4. Deliverable 5: Validation and promotion protocol

### 4.1 Four classes of check

| Class | Definition | Example gates | Passing criterion |
|---|---|---|---|
| Exact correctness | Deterministic identities that must hold in every record | G-X-1 accounting invariants, G-VII-2 sums, monotone P_over in line, over plus under plus push equals 1, manifest published_at not after cut (G-XVII-1) | zero violations |
| Statistical validity | Distributional agreement with realized outcomes on chronological origins | PIT uniformity, CEP tests for counts, CRPS and log-score differences versus named baselines with block-bootstrap intervals | interval excludes baseline in the improving direction; PIT tests not rejected at the declared level with the declared power |
| Freshness and completeness | Inputs present, recent and complete relative to their expected cadence | source retrieved within cadence window, identity coverage, hash change log reviewed | all required sources FRESH for the scope |
| Unsupported state detection | Conditions under which no supported answer exists | NO_ANALOGUE absence, CONFLICT_UNRESOLVED, IDENTITY_UNRESOLVED, WEATHER_PROXY on a weather-dependent scope, routes PROXY on a route-dependent claim | the state is emitted and the affected scope is blocked; this is a correct outcome, not a failure |

### 4.2 How sample sizes and thresholds are determined (no universal numbers)

For each gate: (1) state the estimand (for example, difference in mean CRPS between candidate and baseline for the receiving-yards family); (2) state the product risk as the loss from a false promotion in that scope; (3) estimate the outcome dependence structure (players within a game, games within a week) and compute the effective sample size with cluster-robust or block-bootstrap methods, following the clustered inference practice used in the coaching-change explainer ([nflanalytic](https://nflanalytic.com/explainer-new-coach-effect.html)); (4) fix the tolerable type I error from product risk and compute the number of weeks needed for the desired power to detect the minimum improvement worth deploying; (5) record the resulting minimum prospective weeks in the gate definition with its derivation. For calibration maps (Block XIX), the minimum sample is the size at which the calibration slope interval width falls below the width that would change a verdict. For Monte Carlo draws, N is set so that MC SE is below a stated fraction of the predictive standard deviation for the least stable exposed quantity.

### 4.3 Promotion ladder and the three verdicts (corrected after review)

The product verdict set is exactly the mandate's three values and nothing else: DEPLOYABLE, RESEARCH_ONLY, NO_SUPPORTED_EDGE. Unsupported conditions, stale inputs and gate failures are typed reason codes attached to a verdict, not verdicts. RESEARCH_ONLY is the default verdict for any scope for which analyzable output exists and at least one required readiness gate is FAIL, NOT_EVALUATED, INSUFFICIENT_DATA or blocked by a reason code; it is not earned by passing gates. DEPLOYABLE for a scope requires every required gate PASS on a prospective log of PROVEN releases of the length derived in Section 4.2. NO_SUPPORTED_EDGE applies only to betting and DFS scopes and only when all required gates PASS and the model-versus-market comparison interval does not exclude zero. When no analyzable output exists for a scope (for example the simulator did not run because F1 exact-correctness failed), the scope has verdict RESEARCH_ONLY with reason code NO_OUTPUT and the affected output rows are absent rather than displayed. Any gate FAIL demotes the scope immediately to RESEARCH_ONLY; there is no grace period.

Reason code namespace (typed, machine-readable; per-gate codes in `gate_matrix.csv` column `reason_code_on_fail`): COMPONENT_NOT_INCLUDED:<gate_id> (optional component excluded from a release; never demotes a scope), GATE_FAIL:<gate_id>, GATE_NOT_EVALUATED:<gate_id>, GATE_INSUFFICIENT_DATA:<gate_id>, STALE_INPUT:<source_id>, RELEASE_UNPROVEN, CONFLICT_UNRESOLVED:<player_id>, GAMEDAY_STATUS_UNKNOWN:<player_id>, IDENTITY_UNRESOLVED:<platform>:<name>, NO_ANALOGUE:<player_id>, WEATHER_PROXY:<game_id>, ROUTES_PROXY, CALIBRATION_INFEASIBLE:<family>, PROSPECTIVE_WEEKS_INSUFFICIENT:<scope>, NO_OUTPUT, MARKET_INTERVAL_INCLUDES_ZERO.

The existing eight-rule promotion standard governs component promotion within the repository and is not replaced, renumbered or weakened by this protocol; this protocol adds scope-level verdict logic on top of it. Research completion, including this revision, does not change the engine's status.

### 4.4 Independence and change control

Following the model risk practice of independent validation and effective challenge ([SR 11-7](https://www.federalreserve.gov/boarddocs/srletters/2011/sr1107a1.pdf)), gate evaluation code is owned separately from component code, every promotion records the manifest hash, and any change to a component, calibration map or data source resets the prospective log for the affected scopes.

## 5. Deliverable 6: Product gate matrix and verdict precedence

The exhaustive, machine-readable matrix is delivered in three files in this folder: `gate_matrix.csv` (every gate id with component, class, statistic, baseline, evaluation unit, dependence handling, reason code on fail), `scope_gate_dependencies.csv` (every scope with its required gates, blocking reason codes and non-blocking reason codes), and `verdict_engine.py` (executable precedence: loads both CSVs plus a `gate_result` set and emits a verdict and reason codes per scope, with unit tests in `test_verdict_engine.py`). The prose below summarizes; the files govern.

### 5.1 Scopes

Football scopes: F1 team totals and game worlds; F2 player volume (snaps, targets, carries); F3 player yardage and TD distributions; F4 kicker; F5 DST events and DK points allowed. Prop scopes: P1.<family> one scope per family (passing_yards, passing_attempts, completions, passing_td, interceptions, rushing_attempts, rushing_yards, receptions, receiving_yards, targets, longest_reception, anytime_td, kicking_points); P2 SGP joints. DFS scopes: D1 Classic projections; D2 Showdown projections; D3 ownership; D4 field and duplication; D5 contest simulation and portfolio. Non-betting scopes: N1 research dashboards; N2 evidence and state viewer; N3 explainability views.

### 5.2 Precedence rules (implemented in `verdict_engine.py`)

1. Verdict domain is {DEPLOYABLE, RESEARCH_ONLY, NO_SUPPORTED_EDGE}. Non-betting scopes can only be DEPLOYABLE or RESEARCH_ONLY.
2. For each scope, collect required gates transitively through its dependency scopes. Any gate with status FAIL, NOT_EVALUATED or INSUFFICIENT_DATA yields RESEARCH_ONLY with the corresponding typed reason code. Exact-correctness gates are evaluated first; when one fails in F1, all scopes depending on F1 additionally carry reason code NO_OUTPUT if no worlds were produced.
3. Reason codes from downstream axes (IDENTITY_UNRESOLVED on the salary axis, ownership label absence, contest CSV absence, rules_version mismatch) attach only to D scopes; football and prop scopes ignore them by construction of `scope_gate_dependencies.csv` (mandate Deliverable 6 requirement).
4. RELEASE_UNPROVEN forces RESEARCH_ONLY for every scope of that release.
5. STALE_INPUT:<source_id> attaches to scopes whose dependency list includes the source; it yields RESEARCH_ONLY.
6. If all required gates PASS and prospective weeks are sufficient, football and non-betting scopes are DEPLOYABLE. Betting and DFS scopes are additionally evaluated on the market or realized-payout comparison gate: interval excludes zero in the favorable direction yields DEPLOYABLE, otherwise NO_SUPPORTED_EDGE with reason code MARKET_INTERVAL_INCLUDES_ZERO.
7. Prose never overrides a verdict; the UX renders verdict and reason codes from `gate_result` and the engine output only.

## 6. Deliverable 7: Engineering backlog summary

The full backlog with task_id, objective, dependencies, required_sources, implementation_outline, output_artifacts, acceptance_criteria, validation_plan, blocked_product_scopes and research_uncertainty is `implementation_backlog.csv` (34 tasks, T-01 to T-34). Ordering follows the layer order: capture and vintaging (T-01 to T-06), identity (T-07, T-08), availability and role (T-09 to T-13), volume and allocation (T-14 to T-16), simulator (T-17 to T-20), validation platform (T-21 to T-24), props (T-25, T-26), DFS (T-27 to T-29), UX (T-30). No task is authorized as production by this packet; each ends in a gate evaluation, and NFL-1 remains not authorized per REPO `CURRENT_STATE.md`.

## 7. Deliverable 8: Unresolved evidence and access register

| Gap id | Gap | Product consequence | Resolution path |
|---|---|---|---|
| E-01 | NFL.com transactions page returned no server-rendered records; per-transaction timestamps UNKNOWN ([NFL transactions](https://www.nfl.com/transactions/)) | Tier 2 recency logic for backtests unsupported; live use requires capture with retrieval time only | Inspect the page's network calls in a browser session; if a JSON endpoint exists, register it with terms review; otherwise capture club transaction posts |
| E-02 | Practice-report daily progression not preserved historically | P(active) features limited to final report in backtests | Start daily self-archive of nflverse injuries and club reports; label backtests FINAL_REPORT_ONLY |
| E-03 | In-season route participation unavailable from lawful free sources | Route-dependent claims UNSUPPORTED in season | Proxy from pbp and snap share, labeled; revisit after postseason participation publication |
| E-04 | Open-Meteo Single Runs API provides exact runs by initialisation time (ECMWF IFS from March 2024, others from 2026-04-02) but per-run publication latency and the usage licence were not captured ([Single Runs API](https://open-meteo.com/en/docs/single-runs-api), [model updates](https://open-meteo.com/en/docs/model-updates)) | A run cannot be admitted at a cut until its availability latency is measured; pre-archive backtests carry WEATHER_PROXY | Backlog T-31: log initialisation and first-seen times per model for four weeks; capture licence text; then define L_model |
| E-05 | nflverse license for derived assets UNKNOWN on inspected pages | Redistribution of derived data in a product is unverified | Fetch repository LICENSE files and nflverse terms; record in registry |
| E-06 | Team-site official depth chart cadence and structure per club UNKNOWN | Tier 4 evidence unavailable at scale | Build per-club URL registry with capture standard; measure publication lag |
| E-07 | Tier 5 reporter admissibility and capture standard undefined | Intent information not usable | Owner decision; if admitted, timestamped capture with source account whitelist |
| E-08 | GSIS XML gamebook access terms UNKNOWN ([NFLGSIS About](https://www.nflgsis.com/Help/About.html)) | PDF parsing required for post-game truth | Owner decision to request XML access |
| E-09 | cfb_player_id to CFBD athlete id bridge unverified | College usage priors UNSUPPORTED | Test join coverage on one draft class |
| E-10 | Practice-squad elevation limit amendments after the 2020 CBA text not verified | Roster rules engine may encode a stale limit | Verify on NFL Football Operations rules pages |
| E-11 | No primary disclosure of sportsbook prop-pricing methodology found | Part XLVIII remains an evidence gap; no proprietary method is implied | Continue literature search for conference talks; treat as permanent gap if none found |
| E-12 | Resolved in revision 2: all fifteen named products inspected on public pages (Block XLVII); methodology remains undisclosed for most | None | Closed; reopen only if a product publishes methodology |
| E-13 | DraftKings contest CSV bulk historical access UNKNOWN | Ownership and duplication labels limited to entered contests | Begin per-slate archive of entered contests; record terms |
| E-14 | Draw-count and minimum-weeks values not set | Gates cannot be evaluated until Section 4.2 derivations are run per family | Backlog T-22 |
| E-15 | nflverse injuries date_modified semantics and capture cadence UNKNOWN | published_at_status UNKNOWN for Tier 3 | Compare successive daily downloads for one week |
| E-16 | The continuation piece of the mandate (Parts XLVIII remainder to L) is reconstructed, not verbatim, in `mandate_combined.md` | Wording-sensitive requirements may be paraphrased | Owner pastes the original continuation; replace the RECONSTRUCTED section |
| E-17 | Open-Meteo usage licence and commercial-use terms for Single Runs, Previous Runs and Historical APIs not captured (form field on page) | Redistribution and commercial use unverified | Fetch terms page; record in registry |
| E-18 | Owner instruction of 2026-09-14 forbids adopting commercial vendors; the mandate requests free-versus-paid research. Revision 2 documents paid sources without adopting them; whether any paid source may be adopted for a specific gap is an owner decision | Paid-only capabilities (in-season routes, alignment) remain unsupported | Owner decision item; registry rows carry adoption status |

## 8. Part XLIX synthesis: five component groups

Per-component fields (problem, dependencies, sources, inputs and outputs, method, benchmark, validation, failure and unsupported states, blocked scopes, complexity, uncertainty) are given in the Section 2 blocks; this table assigns each block to a group and states its current evidence status. Nothing here is prioritized around any kickoff.

| Group | Blocks | Status summary |
|---|---|---|
| 1 Foundations | I truth layer, II identity, XXXVIII vintaging, XLI data quality, XLIII storage, XXXVII event engine | Sources verified; capture standard exists in REPO; transaction timestamps and daily practice progression are gaps (E-01, E-02, E-15) |
| 2 Football forecasting | III participation, IV cold start, V role, VI volume, VII allocation, VIII redistribution, IX efficiency, X simulation, XI weather, XII matchups, XIII coaching, XIV injury, XV uncertainty, XXII DST, XXIII kicker, XXXIII features, XXXIV model families, XXXV distributions, XXXVI interpretability | All PROPOSAL; documented NFL inputs exist for participation, depth vintages, draft capital, injury semantics, FG modeling; routes in season and OL win rates UNSUPPORTED (E-03); weather forecasts partial (E-04) |
| 3 Validation and deployment | XVI probabilistic validation, XVII chronological validation, XIX calibration, XXXII benchmarks, XXXIX registry, XL observability, XLII compute, XLIV testing, XLV failure modes | Methods ESTABLISHED; thresholds and minimum weeks to be derived per Section 4.2 (E-14) |
| 4 Downstream | XVIII props, XX market comparison, XXI SGP, XXIV DFS transform, XXV ownership, XXVI field, XXVII duplication, XXVIII contest sim, XXIX portfolio, XXX Showdown, XXXI Classic, XLVI UX | Scoring constants official; ownership and duplication labels depend on contest CSV archive (E-13); all consume worlds only |
| 5 Experimental | college usage translation (IV), coordinator effects (XIII), player-level OL win rates (XII), full (non-reduced) play engine with tracking-derived components (X), Tier 5 reporter evidence (I) | No adequate lawful evidence path yet; recorded in Section 7 |

Disagreements recorded rather than resolved: (a) REPO participation methodology favors an HMM role model while this packet proposes a two-stage hurdle and beta model as champion with HMM as challenger; both remain unvalidated. (b) The prior packet's simulator comparison leaves drive-level versus play-level open; revision 1 of this packet labeled its choice drive-level while describing play sampling, which the external review flagged; revision 2 specifies a play-level engine with a reduced play-outcome model and keeps the drive-level Markov engine as the benchmarked fallback. (c) Empirical Questionable play rates differ materially between the 2008 to 2009 and 2017 to 2024 samples; neither is adopted as a prior.
