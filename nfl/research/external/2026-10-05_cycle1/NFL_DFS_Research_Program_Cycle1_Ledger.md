# NFL Forecasting + DFS External Research Program: Cycle 1 Evidence Ledger

Compiled Monday, October 5, 2026, by Perplexity Computer (external discovery and evidence). This is the first cycle of the master assignment. It is not a strategy memo. Every finding is a ledger record in the required schema. Machine-readable copies: `ledger.jsonl` and `ledger.csv` (one row per claim).

**What this cycle covers**
- 69 ledger records: 40 P0, 15 P1, 9 P2, 5 P3.
- All 69 quotes were checked against the source text: word for word for YouTube, and with normalized matching for web pages.
  - Web pages: the quote was matched against the full page text, ignoring case, punctuation and line breaks.
  - YouTube: 13 new videos, transcripts pulled in full, 98 of 128 candidate quotes matched exactly; only matched quotes are used. Timestamps link to the exact second.
- Source hierarchy was applied when choosing among sources. Independence problems are flagged per record (field `independence_note`).
- No hard rules are proposed. Market variables appear only as field-behavior or diagnostic variables.

---

## 1. Most valuable outcome: raw historical data paths

The single biggest finding is that raw DraftKings Showdown fields are obtainable. Claude doesn't need more commentary for the P0 questions; it needs these files.

| Path | What it gives | Coverage | Cost / terms | Verdict |
|---|---|---|---|---|
| **DraftKings official CSV, contests you did NOT enter** (DATA-01) | Every lineup, rank, points, and %drafted per player and roster slot | Any DK contest, but only during the CSV window | Free. Manual export only: DK's Fair Play Commitment says "The use of automation tools such as browser scripts or bots is prohibited." (DATA-11) | **Primary path. Start tonight.** The help page lists the steps under "Watch Live"; whether completed contests you didn't enter stay exportable is not stated. Test this. |
| **DraftKings CSV retention window** (DATA-02) | Same | 10 days after the contest ends | Free | The 9/28 PHI@CHI and 10/1 PIT@CLE Showdowns should still be inside the window, until roughly 10/8 and 10/11. Export them this week if accessible. |
| **stat-api.com historical archive** (DATA-03, DATA-12) | Full DK contest lineups, ranks, payouts and real ownership; field vs top-1% | DK contests with lineups since 2021. NFL: 28.6K contests, 6.4K with full results (vendor-stated) | Pro plan listed at $99/mo (promo; was $199). One user only; "No plan permits reselling or redistributing the data"; an Enterprise license is required if anyone else uses the data or tools built on it | **Highest-value shadow source, owner decision required.** How they collect DK data is not stated. Validate first against our own 10/4 CSVs using the free 5-row preview. |
| **FantasyTeamAdvice ownership history** (DATA-05, DATA-06) | Actual DK ownership with separate CPT Own / FLEX Own per Showdown | Partial; Showdown coverage has gaps (vendor-stated) | Free top rows; rest locked | Secondary cross-check source |
| **DFS Hero contest results** (DATA-07) | Leaderboards with every DK lineup, real ownership, per-lineup "Dupes" count | Not stated | Subscription; export terms not stated | Ask the vendor for export terms |
| **SaberSim Contest Flashback** (DATA-08) | All real DK lineups re-simulated | DK only; partial early-season loads (stated in video) | In-app only | Not ingestible |
| **Open-source scraper notebooks** (DATA-10) | CSV schemas | n/a | They automate collection against DK's prohibition | **Prohibited.** Schema reference only |

**Owner decisions this creates**
1. Approve a manual capture SOP: export every NFL Showdown contest tier after lock and again after final, hash it into the sealed archive, and log it before the 10-day deadline.
2. Decide whether to buy one month of stat-api Pro as a research-only, single-user archive, after the free-preview cross-check against our 10/4 CSVs passes. The vendor's provenance is unknown, which is a lawful-acquisition question for you.
3. Never automate DraftKings collection.

---

## 2. P0 answers in one place

### CPT vs FLEX ownership (DATA-04/05/06, OWN-05/06)
- **No public CPT-vs-FLEX dataset or model exists.** The data does exist as lineups (DK CSV, stat-api), so we can build it ourselves.
- Real points found so far (CPT : FLEX ratio):

| Player | Slate | CPT | FLEX | Ratio |
|---|---|---|---|---|
| Bijan Robinson | ATL Showdown, 238K lineups | 25.4% | 50.5% | 0.50 |
| Hurts | PHI@CHI 9/28 | 23.7% | 61.9% | 0.38 |
| Warren | PIT@CLE 10/1 | 27.4% | 51.1% | 0.54 |
| Watson | PIT@CLE 10/1 | 13.4% | 57.1% | 0.23 |
| Rodgers | PIT@CLE 10/1 | 6.1% | 50.9% | 0.12 |

- The ratio clearly isn't constant. It varies widely by player, so the "CPT = 0.5 × FLEX" default is falsified as a general rule.
- CPT points are exactly 1.5× FLEX points in the same simulated game (OWN-05); CPT ownership has no such fixed relationship.

### Duplication calibration (DUP-01 to DUP-08)
- Single-variable fits from ETR's database:
  - product ownership R² .43 (earlier addendum)
  - salary used R² .16, nonlinear (DUP-01)
  - CPT ownership alone: "minimal correlation" (DUP-02)
- The only published formula is the independent-product / geomean threshold (DUP-03). No public out-of-sample dupe model was found.

### Salary-left to duplication curve
- **The requested bucketed curve ($0, $100–500, $500–1k, $1k–2k, $2k+) is not published in text anywhere we found.** ETR's chart exists, but its values are in an image (DUP-01).
- What does exist, by bucket, is the **optimal-lineup** salary-left distribution (FC-02: $0 7.4%, $100–900 31.3%, $1,000–1,900 22.7%, $2,000–2,900 9.8%, $3,000+ 28.8%). That's an optimal-lineup statistic, not a dupe function.
- Field-side anchors:
  - About 90% of entered lineups use ≥$49,500 vs 45% of winners (FC-08)
  - An expert estimate that about 80% of the field spends max salary (FC-09)
- **We have to fit this curve ourselves from captured CSVs.**

### Contest-specific ownership (OWN-01 to OWN-03, FC-05, FC-06)
- Measured cohort difference: max-entry vs single-entry Showdown players differ in CPT RB use (31.1% vs 24.9%) and sub-5% CPT use (16.3% vs 25.4%) (FC-05).
- Contest-type ownership gaps (e.g., 23% MME vs 41% high-stakes single entry) are vendor model outputs, not measured.

### Historical field construction (FC-01 to FC-10)
- Optimal / winner / top-3 distributions exist from four non-independent practitioner datasets.
- Field-side distributions (what the whole field did) are almost never published. The exception is ETR's field-vs-top-1% CPT table in the earlier addendum.

### Inactive / news propagation (NEWS-01 to NEWS-05)
- Only mechanisms are public: redistribute the scratched player's ownership, regenerate the field, and check update timestamps against news.
- There are no published measurements of how much ownership moves to whom after a scratch, or how fast. This is a capture task for us: snapshot ownership at T-90/T-30/T-10, then compare to actual.

---

## 3. Conflict register (kept unresolved by design)

| Question | Side A | Side B | Why they may differ | Resolving test |
|---|---|---|---|---|
| Optimal / winning CPT position | FTA 163 slates (optimal): WR 33.1, RB 28.2, QB 20.9 | Occupy 142 winners: RB 32.4; DFS Army 2018 top-3: RB 35.76 | Optimal vs winner vs top-3; different eras | Recompute all three definitions on one archive |
| Does the field over-captain QBs? | FTA: QB is "the most popular captain in almost every showdown field" | ETR: field makes "very few mistakes" by position | FTA gives no field data; ETR uses field vs top-1% | Field CPT share vs optimal/top-1% share on archive |
| Does $49,900 reduce dupes? | SaberSim: max-salary lineups "the most duplicated" (DUP-06) | ETR: $50,000→$49,900 "hardly improves" uniqueness (DUP-01) | Both can be true: max-salary lineups are most duplicated, but $100 under isn't enough | Dupes at exactly $50,000 vs $49,900 vs $49,500, controlling for product ownership |
| Target redistribution after injury | GWTTKB: top beneficiary median 63% (concentrated) | FPL: "frequently disperses across 3 or 4 players" (ROLE-03) | Scoring gain vs target share; sample unknown | Herfindahl of target gains on nflverse participation data |
| QB–RB1 correlation | Spikeweek 0.09 (2018–23) | FantasyLabs 0.38 | Definitions, scoring, era | Recompute on nflverse with DK scoring |
| Showdown fields are DK-downloadable but FanDuel? | SaberSim: FanDuel doesn't allow download (DATA-09) | stat-api documents "FanDuel contest capture" | Undisclosed vendor method | Out of scope (DK only) |

## 4. Independence notes
- Lineup Science repeats ETR Showdown 101 figures verbatim ($13,012 CPT salary, .09 D/ST R², dupes 5.1→10.1), so it isn't independent of ETR.
- The two ETR "Playing Like a Pro" and "What Are the Sims Saying" articles share one dataset: The Solver post-lock sims, 33 slates, 49,146 lineups. Count them once.
- The SaberSim help docs and the SaberSim videos are one source family.

---

## 5. Coverage matrix for all 26 assignment topics

Status: **Covered** = primary/quantitative evidence logged; **Partial** = mechanism or vendor output only; **Thin** = weak or single source; **Next** = queued for cycle 2.

| # | Topic | Status | Records | What's missing |
|---|---|---|---|---|
| 1 | CPT vs FLEX ownership | Partial (data path found) | DATA-01..06, OWN-05/06 | Multi-season table; build from CSVs |
| 2 | Dupe counts and predictors | Partial | DUP-01..08 | Out-of-sample model |
| 3 | Salary left vs dupes | Thin | DUP-01, FC-02, FC-08, FC-09 | Bucketed curve (must fit ourselves) |
| 4 | Ownership by field size / stakes / entry limit | Partial | OWN-01..03, FC-05 | Measured same-slate differences |
| 5 | Field construction distributions | Partial | FC-01..10 | Field-side (not winner) distributions |
| 6 | Ownership after inactives / news | Thin | NEWS-01..05 | Any measured propagation study |
| 7 | Within-game role redistribution | Partial | ROLE-01..03 (+ earlier addendum) | Game-level participation study |
| 8 | QB-specific receiver usage | Thin | QB-01 | QB-identity-conditional TPRR study |
| 9 | Coherent play/possession simulation | Partial | SIM-01..03 | Peer-reviewed player-allocation sim |
| 10 | Distribution models | Thin | DIST-01/02 | Negative-binomial / zero-inflated / Dirichlet-multinomial papers on NFL usage (cycle 2) |
| 11 | Correlation structure | Partial | COR-01/02 | Game-environment-conditioned correlations |
| 12 | Field simulator validation | Partial | FSV-01, OWN-04 | Any vendor ownership-error metric |
| 13 | Portfolio optimization | Partial | PORT-01..05, PAY-01 | NFL Showdown-specific backtests |
| 14 | 150 / 20 / 2-entry objective | Thin | PORT-04, OWN-01 | Formal objective comparison |
| 15 | DST modeling | Next | none | Search returned only scoring pages |
| 16 | Kicker modeling | Thin | K-01, WX-01 | Drive-level FG-opportunity model |
| 17 | Coaching changes | Thin | COACH-01 | Quantified coordinator-change effects |
| 18 | OL injury effects | Thin | OL-01 | Direct OL-injury → pressure study |
| 19 | Weather effect sizes | Covered | WX-01/02 | Independent replication |
| 20 | Cold-start priors | Thin | DIST-01/02 | Rookie/backup prior studies |
| 21 | Calibration / scoring rules | Covered | CAL-01, FSV-01 | Sports-specific CRPS applications |
| 22 | Model vs market disagreement | Thin | MKT-01 | Diagnostic-only literature |
| 23 | Late-swap decision theory | Partial | LS-01/02 | Not applicable to single-game Showdown |
| 24 | Payout-aware contest sim | Partial | PAY-01, PORT-04 | Ties / top-heavy utility papers |
| 25 | Historical optimizer behavior | Partial | OPT-01, FC-08, FC-09 | Overproduced lineup-family study |
| 26 | Open-source repositories | Partial | DATA-10, SIM-03 (+ chanzer0, tburger101 in addendum) | Code audit pass |

---

## 6. Tests Claude can run on our own data

These are ordered by what's possible tonight versus after more capture. None of them changes the football projection.

1. **Tonight (ATL@NO), manual capture:** export the flagship Showdown and at least one small-field and one 20-max Showdown after lock and after final. That's observation #2 for field and dupe work.
2. **Using the archived lineups**, compute:
   - per-player CPT and FLEX ownership
   - CPT:FLEX ratio by position, salary rank and favorite flag
   - exact-lineup dupe counts
   - salary-left buckets
   - team split, QB count and K/DST count
   - field vs top-1% vs winner vs hindsight-optimal
3. **Dupe calibration:** for every lineup, compare actual dupes against (a) N × product of slot ownership, (b) the geomean threshold, and (c) generated-field empirical counts. Make a log-scale calibration plot. Falsify (a) if it's biased by more than 2× in the top chalk decile.
4. **Salary-left curve:** partial effect of the salary-left bucket on dupes after controlling for product ownership and CPT/stack features (DUP-01 falsification).
5. **Ownership snapshots:** projected ownership at T-90/T-30/T-10 with news-event IDs; MAE by ownership tier against actual (NEWS-03/05).
6. **Correlation recovery:** compare the joint sim's emergent QB–WR, QB–TE, RB–DST and opposing-WR correlations to the COR-01/COR-02 ranges. This is a validation target only, never an imposed copula.
7. **Contest-sim calibration:** a predicted-vs-actual reliability table for cash, top-1% and win (FSV-01 template).

## 7. Cycle 2 research queue
- DST and kicker drive-level models (topics 15–16).
- Peer-reviewed count models for NFL targets and carries, plus Dirichlet-multinomial share models (topic 10).
- Measured ownership movement after inactives. Search archived ownership-report pages before and after news on specific dates (topic 6).
- Code audit of the open-source field/dupe/portfolio repos (chanzer0, tburger101, NFLSimulatoR, dlm1223, gacolitti draft.kings).
- Remaining YouTube transcripts with methodology phrases ("backtested", "historical database", "we ran X contests", "captain ownership", "after inactives").

---

## Appendix A. Full evidence ledger

Each record follows the program schema. "not stated" means the source didn't report it; nothing was inferred.

### P0 records


#### DATA-01: raw data: official DK contest CSV (contests not entered)

**Claim.** DraftKings officially documents a manual path to export the full-field standings CSV for contests the user is NOT entered in (Lobby > Sport > Watch Live > Export Lineups to CSV).

> "To download a CSV of the contest you are NOT participating in: 1. Go to the Contest Lobby. 2. Click on Sport. 3. Click Watch Live. 4. Select the contest. 5. Click Export Lineups to CSV."  
> [DraftKings Help KB0010448 (v3.0, modified 2026-06-22)](https://support.draftkings.com/dk/en/how-do-i-download-a-csv-to-see-gamecenter-standings-for-a-contest?id=kb_article_view&sysparm_article=KB0010448) — quote verified against source text: yes

- Topic: raw data: official DK contest CSV (contests not entered)
- Source type: official docs
- Date: 2026-06-22
- Site: DraftKings
- Format: all (Classic and Showdown)
- Sample size: not stated
- Time period: not stated
- Outcome definition: not stated
- Method / formula: manual export from GameCenter
- Features / data: Rank, Entry ID, Entry Name, Points, full lineup; athlete roster position, %drafted, FPTS
- Result / effect size: not stated
- Limitations: Page says 'Watch Live'; whether completed not-entered contests remain exportable is not stated. Manual only: DK Fair Play Commitment prohibits 'automation tools such as browser scripts or bots'.
- Conflicting evidence: none found
- Code / data availability: CSV, manual download
- Reproducibility: high (primary source; we already hold 3 such CSVs)
- Layer affected: ownership / field / duplication / evaluation
- Claim tag: EMPIRICAL_HISTORICAL_EVIDENCE
- Allowed use: evidence (data acquisition path)
- Test on our data: Tonight: manually export the ATL@NO flagship Showdown plus 2-4 other Showdown contests of different size/entry-limit after lock, then again after final.
- Falsification: Export button absent for non-entered contests, or CSV truncated vs. stated entry count.
- Implementation candidate: Capture SOP: manual post-lock + post-final export of every NFL Showdown contest tier, hashed into the sealed archive within the 10-day window.


#### DATA-02: raw data: DK CSV retention

**Claim.** Completed-contest CSVs are only available for 10 days after the contest ends.

> "CSV downloads are available for 10 days after the contest ends."  
> [DraftKings Help KB0010448](https://support.draftkings.com/dk/en/how-do-i-download-a-csv-to-see-gamecenter-standings-for-a-contest?id=kb_article_view&sysparm_article=KB0010448) — quote verified against source text: yes

- Topic: raw data: DK CSV retention
- Source type: official docs
- Date: 2026-06-22
- Site: DraftKings
- Format: not stated
- Sample size: not stated
- Time period: not stated
- Outcome definition: not stated
- Method / formula: not stated
- Features / data: not stated
- Result / effect size: not stated
- Limitations: not stated
- Conflicting evidence: none found
- Code / data availability: not stated
- Reproducibility: not stated
- Layer affected: evaluation / data governance
- Claim tag: EMPIRICAL_HISTORICAL_EVIDENCE
- Allowed use: evidence
- Test on our data: Check whether the 9/28 PHI@CHI and 10/1 PIT@CLE Showdown contests are still exportable (window closes ~10/8 and ~10/11).
- Falsification: n/a (policy statement)
- Implementation candidate: Calendar-driven capture deadline (T+10d) in the archive manifest.


#### DATA-03: raw data: commercial DK historical contest archive

**Claim.** stat-api reports an NFL archive of 28.6K contests (257M entries), 6.4K with full results including lineups, scores, payouts and real ownership, downloadable as CSV/JSON.

> "28.6K contests with 257M entries, 6.4K of them with full results: lineups, scores, payouts and real ownership, downloadable as CSV or JSON."  
> [stat-api.com Daily Fantasy page](https://stat-api.com/daily-fantasy/) — quote verified against source text: yes

- Topic: raw data: commercial DK historical contest archive
- Source type: vendor
- Date: 2026-09-20
- Site: DraftKings and FanDuel
- Format: Classic and Showdown
- Sample size: 28.6K NFL contests; 6.4K with full results
- Time period: DraftKings contests with lineups since 2021 (FAQ)
- Outcome definition: not stated
- Method / formula: not stated
- Features / data: per-lineup slots, points, rank, payout; field and top-1% ownership
- Result / effect size: not stated
- Limitations: Collection method for DraftKings data not stated. License: one user, no redistribution; Enterprise license required if anyone else uses the data or derived tools. Download ownership is per player, not per slot ('his CPT/MVP row and his FLEX row carry the same values'), so CPT vs FLEX must be recomputed from lineups.
- Conflicting evidence: none found
- Code / data availability: API: GET /api/v1/dfs/contests/{id}/download (CSV/JSON); Pro plan $99/mo listed (50% promo; was $199)
- Reproducibility: medium: vendor-held; verifiable by spot-matching against our own DK CSVs
- Layer affected: ownership / field / duplication
- Claim tag: EXTERNAL_MODEL_OUTPUT
- Allowed use: shadow candidate (data source pending owner/legal decision)
- Test on our data: Pull the same contest IDs we captured on 10/4 (196208416/7/8) via the free 5-row preview; diff against our CSVs before any purchase.
- Falsification: Row counts, lineups or ownership disagree with our DK CSVs for the same contest IDs.
- Implementation candidate: If validated and licensed: bulk-ingest all DK NFL Showdown contests 2021-2026 into a read-only research archive (never into the football layer).


#### DATA-04: CPT vs FLEX ownership: ATL Showdown example

**Claim.** A displayed DK NFL Showdown contest (238K lineups) shows Bijan Robinson at 25.4% captain / 50.5% flex ownership, Drake London 13.3% / 36.3%, Michael Penix Jr. 2.8% / 34.0%.

> "|Bijan Robinson|RB|$11,800|25.4%|50.5%|38.30| |Jordan Love|QB|$10,000|11.6%|58.6%|22.48| |Christian Watson|WR|$9,800|14.2%|37.0%|22.60| |Drake London|WR|$8,800|13.3%|36.3%|31.40|"  
> [stat-api.com Daily Fantasy page (sample table)](https://stat-api.com/daily-fantasy/) — quote verified against source text: yes

- Topic: CPT vs FLEX ownership: ATL Showdown example
- Source type: vendor
- Date: 2026-09-20
- Site: DraftKings
- Format: Showdown
- Sample size: 1 contest, 238K lineups
- Time period: not stated (player pool implies 2026 GB-ATL)
- Outcome definition: ownership (actual)
- Method / formula: not stated
- Features / data: not stated
- Result / effect size: not stated
- Limitations: Single contest; contest ID and date not printed; salaries indicate an ATL vs GB slate.
- Conflicting evidence: none found
- Code / data availability: not stated
- Reproducibility: not stated
- Layer affected: ownership
- Claim tag: EMPIRICAL_HISTORICAL_EVIDENCE
- Allowed use: evidence (field-behavior calibration point)
- Test on our data: Compare tonight's actual Bijan CPT/FLEX split with this prior ATL slate; record CPT:FLEX ratio by player.
- Falsification: n/a (single observation)
- Implementation candidate: Seed row for a CPT/FLEX ratio table keyed by position x salary rank x favorite flag.


#### DATA-05: CPT vs FLEX ownership: free actual-ownership history

**Claim.** FantasyTeamAdvice publishes actual DK GPP ownership with separate FLEX Own and CPT Own for some Showdown slates (e.g., PHI@CHI 9/28/2026: Hurts 61.9% FLEX / 23.7% CPT).

> "|Jalen Hurts| |QB|$10,800|61.9%|23.7%|"  
> [FantasyTeamAdvice NFL DFS Ownership History](https://fantasyteamadvice.com/nfl/dfs-ownership/history?date=2026-09-28&site=dk&slate=5554) — quote verified against source text: yes

- Topic: CPT vs FLEX ownership: free actual-ownership history
- Source type: vendor
- Date: 2026-09-28
- Site: DraftKings only
- Format: Showdown and Classic
- Sample size: slate-level; top players free, rest locked
- Time period: not stated
- Outcome definition: not stated
- Method / formula: not stated
- Features / data: not stated
- Result / effect size: not stated
- Limitations: Coverage gaps: feed covers classic far better than Showdown; missing slate must not be read as 0%. Which contest the ownership comes from is not stated.
- Conflicting evidence: none found
- Code / data availability: web page; MCP-compatible agent access advertised
- Reproducibility: medium
- Layer affected: ownership
- Claim tag: EMPIRICAL_HISTORICAL_EVIDENCE
- Allowed use: evidence
- Test on our data: Cross-check FTA values for any Showdown slate we export ourselves.
- Falsification: FTA values differ materially (>2 pts) from DK CSV %Drafted for the same contest.
- Implementation candidate: Secondary ownership source with explicit contest-identity caveat.


#### DATA-06: CPT vs FLEX ownership: PIT@CLE 10/1/2026

**Claim.** For the 10/1/2026 PIT@CLE DK Showdown, actual ownership: Jaylen Warren 51.1% FLEX / 27.4% CPT; Deshaun Watson 57.1% / 13.4%; Aaron Rodgers 50.9% / 6.1%.

> "Jaylen Warren| |RB|$9,600|51.1%|27.4%| Deshaun Watson| |QB|$9,400|57.1%|13.4%| Aaron Rodgers| |QB|$9,800|50.9%|6.1%|"  
> [FantasyTeamAdvice NFL DFS Ownership History](https://fantasyteamadvice.com/nfl/dfs-ownership/history?date=2026-10-01&site=dk&slate=5709) — quote verified against source text: yes

- Topic: CPT vs FLEX ownership: PIT@CLE 10/1/2026
- Source type: vendor
- Date: 2026-10-01
- Site: DraftKings
- Format: Showdown
- Sample size: 34-player slate, 3 players shown
- Time period: not stated
- Outcome definition: not stated
- Method / formula: not stated
- Features / data: not stated
- Result / effect size: Warren CPT:FLEX 0.54; Watson 0.23; Rodgers 0.12
- Limitations: Values from prompt extraction of a table; not re-verified verbatim. QB CPT share low relative to FLEX in this slate.
- Conflicting evidence: Conflicts with the common assumption CPT = 0.5 x FLEX (chanzer0 default) for QBs: Rodgers 0.12.
- Code / data availability: not stated
- Reproducibility: not stated
- Layer affected: ownership
- Claim tag: EMPIRICAL_HISTORICAL_EVIDENCE
- Allowed use: evidence
- Test on our data: Export this contest from DK if still within 10 days and verify.
- Falsification: DK CSV disagrees.
- Implementation candidate: none (evidence only)


#### DATA-07: raw data: other archives

**Claim.** DFS Hero stores the final leaderboard of every contest it can reach, with every DraftKings lineup, real ownership and a per-lineup 'Dupes' count; FanDuel results carry standings without rosters.

> "After a slate finishes, DFS Hero collects the final leaderboard of every contest it can reach and stores it with the slate."  
> [DFS Hero Help: Contest results](https://dfshero.com/help/results/contest-results) — quote verified against source text: yes

- Topic: raw data: other archives
- Source type: vendor
- Date: 2026-09-06
- Site: DraftKings (full), FanDuel (standings only)
- Format: Classic and Showdown
- Sample size: not stated
- Time period: not stated
- Outcome definition: not stated
- Method / formula: not stated
- Features / data: not stated
- Result / effect size: not stated
- Limitations: Coverage start date, export and licensing not stated; quote from prompt extraction (not re-verified verbatim).
- Conflicting evidence: none found
- Code / data availability: not stated
- Reproducibility: not stated
- Layer affected: duplication / field
- Claim tag: EXTERNAL_MODEL_OUTPUT
- Allowed use: shadow candidate (data source)
- Test on our data: Ask vendor for export terms; compare a dupe count against our own CSV-derived count.
- Falsification: Dupe counts disagree with exact-lineup counting on DK CSV.
- Implementation candidate: none (evidence only)


#### DATA-08: raw data: SaberSim Contest Flashback

**Claim.** SaberSim Contest Flashback takes all real lineups from completed DraftKings contests and re-runs them through 100,000 slate simulations; DraftKings only.

> "After a DraftKings contest completes, SaberSim takes all of the real lineups that were actually played in that contest."  
> [SaberSim Help: Using Contest Flashback](https://support.sabersim.com/en/articles/12079605-using-contest-flashback) — quote verified against source text: yes

- Topic: raw data: SaberSim Contest Flashback
- Source type: documented commercial-tool methodology
- Date: 2025-10-10
- Site: DraftKings
- Format: not stated
- Sample size: not stated
- Time period: not stated
- Outcome definition: not stated
- Method / formula: not stated
- Features / data: not stated
- Result / effect size: not stated
- Limitations: In-app only; no export stated. Speaker notes early-season coverage was partial (only Milly Makers loaded for first weeks).
- Conflicting evidence: none found
- Code / data availability: not stated
- Reproducibility: not stated
- Layer affected: field / evaluation
- Claim tag: EXTERNAL_MODEL_OUTPUT
- Allowed use: evidence
- Test on our data: n/a (closed tool)
- Falsification: n/a
- Implementation candidate: none (evidence only)


#### DATA-09: raw data: FanDuel contest data not downloadable

**Claim.** SaberSim states FanDuel does not allow anyone to download contest data, so Flashback is DraftKings-only.

> "okay so two things on this so number one uh it is right that Fel doesn't have the actual contest ownership and the reason for that is that FanDuel does not allow anybody for that matter to download their contest data okay so like the same way we're able to do flashback for DraftKings we can't do it for FanDuel"  
> [DFS Q&A: How do you recommend filtering out lineups for NFL Showdown? (SaberSim DFS - Daily Fantasy Sports Strategy)](https://www.youtube.com/watch?v=hTUUH0mfpfU&t=265s) — quote verified against source text: yes

- Topic: raw data: FanDuel contest data not downloadable
- Source type: YouTube
- Date: 2025-01-15
- YouTube timestamp: 4:25 (265s)
- Site: FanDuel
- Format: not stated
- Sample size: not stated
- Time period: not stated
- Outcome definition: not stated
- Method / formula: not stated
- Features / data: not stated
- Result / effect size: not stated
- Limitations: not stated
- Conflicting evidence: stat-api documents a 'FanDuel contest capture' with full standings and lineups (method undisclosed).
- Code / data availability: not stated
- Reproducibility: not stated
- Layer affected: data governance
- Claim tag: EXPERT_OPINION
- Allowed use: evidence
- Test on our data: n/a
- Falsification: n/a
- Implementation candidate: none (evidence only)


### P3 records


#### DATA-10: open-source capture code

**Claim.** Public notebook collects entry results and per-contest player ownership for every NFL DK contest; author notes DK removes data after ~4 days and ran it 2-3x/week.

> "DraftKings removes data after ~4 days! I ran this notebook 2-3 times a week throughout the season."  
> [JamesChapmanNV/DraftKings_Scraper (GitHub)](https://github.com/JamesChapmanNV/DraftKings_Scraper) — quote verified against source text: yes

- Topic: open-source capture code
- Source type: GitHub
- Date: 2025-03-05
- Site: DraftKings
- Format: all NFL
- Sample size: not stated
- Time period: not stated
- Outcome definition: not stated
- Method / formula: not stated
- Features / data: not stated
- Result / effect size: not stated
- Limitations: Automated collection conflicts with DK Fair Play Commitment ('automation tools such as browser scripts or bots is prohibited'); the ~4-day figure conflicts with DK's official 10-day retention. Audit only; do not run.
- Conflicting evidence: AshtonO/DraftkingsContestScraper README states such tools directly violate DK Terms of Service.
- Code / data availability: Jupyter notebook; output schemas contestResults.csv / contestOwnership.csv / contests.csv
- Reproducibility: not stated
- Layer affected: data governance
- Claim tag: PROHIBITED_DIRECT_INPUT
- Allowed use: prohibited (automation); schema reference only
- Test on our data: Use its CSV schemas as a reference for our manual-capture normalizer.
- Falsification: n/a
- Implementation candidate: none (evidence only)


### P0 records


#### DATA-11: acquisition constraint: DK automation prohibition

**Claim.** DraftKings' Fair Play Commitment prohibits automation tools such as browser scripts or bots.

> "The use of automation tools such as browser scripts or bots is prohibited."  
> [DraftKings Fantasy Fair Play Commitment](https://www.draftkings.com/fantasy-fair-play-commitment) — quote verified against source text: yes

- Topic: acquisition constraint: DK automation prohibition
- Source type: official docs
- Date: not stated
- Site: DraftKings
- Format: not stated
- Sample size: not stated
- Time period: not stated
- Outcome definition: not stated
- Method / formula: not stated
- Features / data: not stated
- Result / effect size: not stated
- Limitations: not stated
- Conflicting evidence: none found
- Code / data availability: not stated
- Reproducibility: not stated
- Layer affected: data governance
- Claim tag: EMPIRICAL_HISTORICAL_EVIDENCE
- Allowed use: evidence (binding constraint on capture method)
- Test on our data: n/a
- Falsification: n/a
- Implementation candidate: Capture SOP is manual export only; no scripted DK collection in our pipeline.


#### DATA-12: acquisition constraint: stat-api license

**Claim.** stat-api: DraftKings contests with lineups start in 2021; plans are single-user; no plan permits redistributing the data, and an Enterprise license is required if anyone besides the subscriber uses the data or what is built on it.

> "No plan permits reselling or redistributing the data as a feed, API, export or database."  
> [stat-api FAQ](https://stat-api.com/faq/) — quote verified against source text: yes

- Topic: acquisition constraint: stat-api license
- Source type: vendor
- Date: not stated
- Site: not stated
- Format: not stated
- Sample size: not stated
- Time period: not stated
- Outcome definition: not stated
- Method / formula: not stated
- Features / data: not stated
- Result / effect size: not stated
- Limitations: How stat-api obtains DraftKings data is not stated; provenance/ToS posture of the vendor is unknown.
- Conflicting evidence: none found
- Code / data availability: not stated
- Reproducibility: not stated
- Layer affected: data governance
- Claim tag: EMPIRICAL_HISTORICAL_EVIDENCE
- Allowed use: evidence (owner decision input)
- Test on our data: n/a
- Falsification: n/a
- Implementation candidate: none (evidence only)


#### FC-01: optimal CPT position by game environment

**Claim.** Across 163 DK Showdown slates (Sep 2024-Feb 2026), the hindsight-optimal CPT was WR 33.1%, RB 28.2%, QB 20.9%, TE 9.2%, DST 5.5%, K 3.1%; low totals tilt to RB (46%), high totals to WR (47%).

> "Nut lineup captain by position 163 DraftKings showdown slates, 2024 and 2025 seasons WR 33.1% RB 28.2% QB 20.9% TE 9.2% DST 5.5% K 3.1%"  
> [FTA NFL DFS Showdown Study](https://fantasyteamadvisors.com/nfl-dfs-showdown-study/) — quote verified against source text: yes

- Topic: optimal CPT position by game environment
- Source type: practitioner research with disclosed sample
- Date: 2026-08-04
- Site: DraftKings
- Format: Showdown
- Sample size: 163 slates
- Time period: Sep 2024 - Feb 2026
- Outcome definition: optimal (hindsight 'nut' lineup)
- Method / formula: Hindsight MILP on actual DK points; total/spread from closing lines
- Features / data: not stated
- Result / effect size: WR 33.1 / RB 28.2 / QB 20.9 / TE 9.2 / DST 5.5 / K 3.1; Grind(<=42) RB 46 WR 31 QB 12; Shootout(>=49) WR 47 RB 19 QB 17
- Limitations: Optimal, not winner/top-1%; position rates unstable by season (WR CPT 40% in 2024 vs 28% in 2025, stated by the authors).
- Conflicting evidence: DFS Army 2019 winners: RB 35.76% CPT; Occupy Fantasy 142 winners: RB 32.4%; ETR top-1%: WR 32.8%. Different outcome definitions.
- Code / data availability: not available
- Reproducibility: reproducible with DK salaries + actual points (we can recompute)
- Layer affected: field / portfolio
- Claim tag: EMPIRICAL_HISTORICAL_EVIDENCE
- Allowed use: evidence (do not convert to CPT rules)
- Test on our data: Recompute the nut lineup for every Showdown we archive; compare optimal CPT position share vs field CPT ownership share by total bucket.
- Falsification: On our archive, optimal CPT share by position is indistinguishable from the field's CPT share (no mispricing).
- Implementation candidate: Evaluation metric: field CPT-position allocation error vs optimal, by total/spread bucket.


#### FC-02: optimal salary left

**Claim.** Only 7.4% of nut lineups used the full $50,000; median unspent was $1,400; 28.8% left $3,000+.

> "Only 7.4 percent of nut lineups used the full $50,000. The median left $1,400 on the table and nearly three in ten left $3,000 or more."  
> [FTA NFL DFS Showdown Study](https://fantasyteamadvisors.com/nfl-dfs-showdown-study/) — quote verified against source text: yes

- Topic: optimal salary left
- Source type: practitioner research with disclosed sample
- Date: 2026-08-04
- Site: DraftKings
- Format: Showdown
- Sample size: 163 slates
- Time period: not stated
- Outcome definition: optimal
- Method / formula: not stated
- Features / data: not stated
- Result / effect size: $0: 7.4% / $100-900: 31.3% / $1,000-1,900: 22.7% / $2,000-2,900: 9.8% / $3,000+: 28.8%
- Limitations: Optimal lineup salary is not a dupe function; full-cap share fell from 12% (2024) to 4% (2025).
- Conflicting evidence: DFS Army 2019 winners avg $48,518 (7% full cap); Occupy: 45% of winners used >=$49,500 vs ~90% of entered lineups; One Week Season: optimal median $1,550 left vs winners $600.
- Code / data availability: not stated
- Reproducibility: not stated
- Layer affected: field / duplication
- Claim tag: EMPIRICAL_HISTORICAL_EVIDENCE
- Allowed use: evidence
- Test on our data: Salary-left histogram: field vs top-1% vs winner vs optimal on each archived Showdown.
- Falsification: Field salary-left distribution matches optimal's (no structural over-spending).
- Implementation candidate: none (evidence only)


#### FC-03: optimal team split and K/DST

**Claim.** A 3-3 or 4-2 favorite split covered 65.7% of nut lineups; kickers appeared in 40.5%, defenses in 31.3%, and K/DST was CPT in 8.6%.

> "A three or four split covers 65.7 percent of nut lineups. Going five or six deep on one side hit 10.4 percent of the time and going one deep hit 2.5 percent."  
> [FTA NFL DFS Showdown Study](https://fantasyteamadvisors.com/nfl-dfs-showdown-study/) — quote verified against source text: yes

- Topic: optimal team split and K/DST
- Source type: practitioner research with disclosed sample
- Date: 2026-08-04
- Site: DraftKings
- Format: Showdown
- Sample size: 163 slates
- Time period: not stated
- Outcome definition: optimal
- Method / formula: not stated
- Features / data: not stated
- Result / effect size: favorite count 1:2.5% 2:21.5% 3:34.4% 4:31.3% 5:10.4%
- Limitations: not stated
- Conflicting evidence: DFS Army 2019 winners: 4-2 ~51%, 3-3 ~31%, 5-1 18% (team split, not favorite split). Occupy 142 winners: 3-3 33.8%, 4-2 24.6%, 5-1 19.0%.
- Code / data availability: not stated
- Reproducibility: not stated
- Layer affected: field
- Claim tag: EMPIRICAL_HISTORICAL_EVIDENCE
- Allowed use: evidence
- Test on our data: Archetype frequency table: field vs top-1% vs winner vs optimal.
- Falsification: n/a (descriptive)
- Implementation candidate: none (evidence only)


#### FC-04: optimal lineup ownership

**Claim.** Median nut-lineup total projected ownership was 167.4% (range 83-239); median optimal CPT was projected 10.9%; 41.1% of nut lineups contained a sub-3% projected player.

> "Median total was 167.4 percent across six roster spots, with a full range from 83 to 239. Captain ownership tells the same story: the median optimal captain was projected for 10.9 percent, but 27.6 percent of slates had a captain projected under 5 percent and 16 percent had one over 20 percent."  
> [FTA NFL DFS Showdown Study](https://fantasyteamadvisors.com/nfl-dfs-showdown-study/) — quote verified against source text: yes

- Topic: optimal lineup ownership
- Source type: practitioner research with disclosed sample
- Date: 2026-08-04
- Site: DraftKings
- Format: Showdown
- Sample size: 163 slates
- Time period: not stated
- Outcome definition: optimal
- Method / formula: not stated
- Features / data: not stated
- Result / effect size: not stated
- Limitations: Uses pregame FTA projected ownership, not contest-final ownership.
- Conflicting evidence: ETR: average CPT ownership for winning lineups 10.3% (winner, actual ownership) - consistent direction.
- Code / data availability: not stated
- Reproducibility: not stated
- Layer affected: ownership / portfolio
- Claim tag: EMPIRICAL_HISTORICAL_EVIDENCE
- Allowed use: evidence
- Test on our data: Same metrics on our archive using actual ownership.
- Falsification: n/a
- Implementation candidate: none (evidence only)


#### FC-05: contest-type construction differences (max-entry vs single-entry)

**Claim.** In 33 primetime Showdowns (2025, $333/$444, 37-max), max-entry players used CPT RB 31.1% vs 24.9% for single-entry; single-entry over-indexed sub-5% CPTs (25.4% vs 16.3%).

> "Max-entry players use CPT RB in 31.1% of their lineups compared to 24.9% from single-entry players."  
> [ETR: NFL Showdown: Playing Like a Pro](https://establishtherun.com/nfl-showdown-playing-like-a-pro/) — quote verified against source text: yes

- Topic: contest-type construction differences (max-entry vs single-entry)
- Source type: practitioner research with disclosed sample
- Date: 2026-09-07
- Site: DraftKings
- Format: Showdown
- Sample size: 33 slates; 49,146 lineups (companion article)
- Time period: 2025 Week 5 - Super Bowl
- Outcome definition: sim ROI, cash rate, top-1% rate, actual ROI
- Method / formula: Post-lock sims from The Solver + ETR projections
- Features / data: not stated
- Result / effect size: not stated
- Limitations: High-stakes small fields (1,000-1,500 entries); sim ROI is model-dependent; 'remarkably small sample' per ETR.
- Conflicting evidence: none found
- Code / data availability: not stated
- Reproducibility: not stated
- Layer affected: field / portfolio
- Claim tag: EMPIRICAL_HISTORICAL_EVIDENCE
- Allowed use: evidence (contest-bucket field priors)
- Test on our data: Split our archived fields by entrant entry count (1 vs 2-20 vs 21-150) and compare CPT position and sub-5% CPT use.
- Falsification: No construction difference between single- and max-entry cohorts in our archive.
- Implementation candidate: Field generator: entrant-cohort mixture (single/limited/max-entry) with cohort-specific archetype priors.


#### FC-06: single-entry ALL SKILL construction

**Claim.** Single-entry players default to an ALL SKILL lineup (no K, no D/ST) 53.9% of the time for a -32% actual ROI.

> "the construction single-entry players default to 53.9% of the time for a -32% actual ROI."  
> [Lineup Science: The Nucleus](https://lineupscience.com/nucleus) — quote verified against source text: yes

- Topic: single-entry ALL SKILL construction
- Source type: vendor
- Date: not stated
- Site: DraftKings
- Format: Showdown
- Sample size: not stated
- Time period: not stated
- Outcome definition: not stated
- Method / formula: not stated
- Features / data: not stated
- Result / effect size: not stated
- Limitations: No sample, period or method stated.
- Conflicting evidence: none found
- Code / data availability: not stated
- Reproducibility: not stated
- Layer affected: field
- Claim tag: FIELD_BEHAVIOR_HYPOTHESIS
- Allowed use: hypothesis
- Test on our data: Share of no-K/no-DST lineups among single-entry entrants in our archive.
- Falsification: Single-entry no-K/DST share far from ~54% across archived slates.
- Implementation candidate: none (evidence only)
- Independence note: Lineup Science repeats several ETR Showdown 101 figures verbatim ($13,012 CPT salary, .09 D/ST R2, 5.1->10.1 dupes); treat as NOT independent of ETR.


#### FC-07: winning lineup salary / QB count (2018)

**Claim.** Across 165 top-3 Showdown lineups (2018 primetime slates), average salary was $48,518; 7% used the full cap; ~33% used two QBs.

> "I looked at 165 lineups which included a whopping 990 players (though not all different players). The average lineup salary was $48518 or about $1500 under the max salary."  
> [DFS Army: DraftKings NFL Showdown Winning Lineup Construction](https://www.dfsarmy.com/2019/09/draftkings-nfl-showdown-winning-lineup-construction.html) — quote verified against source text: yes

- Topic: winning lineup salary / QB count (2018)
- Source type: practitioner research with disclosed sample
- Date: 2019-09-02
- Site: DraftKings
- Format: Showdown
- Sample size: 165 lineups
- Time period: 2018 season
- Outcome definition: top-3 finishers
- Method / formula: not stated
- Features / data: not stated
- Result / effect size: not stated
- Limitations: Old roster rules era; small n; top-3 not top-1%.
- Conflicting evidence: none found
- Code / data availability: not stated
- Reproducibility: not stated
- Layer affected: field
- Claim tag: EMPIRICAL_HISTORICAL_EVIDENCE
- Allowed use: evidence
- Test on our data: Recompute on 2021-2026 archive.
- Falsification: n/a
- Implementation candidate: none (evidence only)


#### FC-08: field vs winners salary used

**Claim.** Since 2018, 45% of winning large DK single-game GPP lineups used at least $49,500, compared with nearly 90% of entered lineups.

> "Dating back to the beginning of the 2018 season, just 45 percent of winning lineups in the big DraftKings single game GPPs have used $49,500 or more salary. On average, nearly 90 percent of lineups entered into a single game GPP use $49,500 or more salary. See the edge? Just about 70 percent of all winning GPP lineups during that time were duplicated (more than one user entered the same lineup). In those duplicated lineups, the median salary usage was … $49,500."  
> [Occupy Fantasy: The CPT Spot (eBook)](https://occupyfantasy.com/wp-content/uploads/woocommerce_uploads/2020/09/Updated-eBook-The-CPT-Spot-NFL-Showdown-DFS-Strategy-Guide-jcnc3f.pdf) — quote verified against source text: yes

- Topic: field vs winners salary used
- Source type: practitioner research with disclosed sample
- Date: 2020
- Site: DraftKings
- Format: Showdown
- Sample size: 142 slates (winners)
- Time period: not stated
- Outcome definition: winner vs entered field
- Method / formula: not stated
- Features / data: not stated
- Result / effect size: not stated
- Limitations: Field-salary figure method not stated; quote from prompt extraction.
- Conflicting evidence: none found
- Code / data availability: not stated
- Reproducibility: not stated
- Layer affected: field / duplication
- Claim tag: EMPIRICAL_HISTORICAL_EVIDENCE
- Allowed use: evidence
- Test on our data: Share of field lineups >= $49,500 vs winners on our archive.
- Falsification: Field share far below ~90%.
- Implementation candidate: none (evidence only)


#### FC-09: field salary spending (expert estimate)

**Claim.** AceMind speaker estimates ~80% of the field spends max salary and ~10% spends $100-200 below, and says their sims mimic that.

> "80% of the field probably spends Max salary another you know 10% spends you know1 or $200 below that it's sort of exponential the way it you know people play more salary it's just kind of human nature our our Sims mimic that"  
> [AceMind Catch up-----NFL showdown and other best practices using their sims. (TrueDFS)](https://www.youtube.com/watch?v=yle0xQ2cuq8&t=992s) — quote verified against source text: yes

- Topic: field salary spending (expert estimate)
- Source type: YouTube
- Date: 2024-12-05
- YouTube timestamp: 16:32 (992s)
- Site: DraftKings
- Format: Showdown
- Sample size: not stated
- Time period: not stated
- Outcome definition: not stated
- Method / formula: not stated
- Features / data: not stated
- Result / effect size: not stated
- Limitations: not stated
- Conflicting evidence: Occupy Fantasy: ~90% of entered lineups used >=$49,500 (different threshold).
- Code / data availability: not stated
- Reproducibility: not stated
- Layer affected: field / duplication
- Claim tag: EXPERT_OPINION
- Allowed use: hypothesis
- Test on our data: Field salary-used histogram on archived Showdowns.
- Falsification: Max-salary share in archived fields well below 80%.
- Implementation candidate: none (evidence only)


#### FC-10: winning salary left (DFS Army video)

**Claim.** DFS Army reports the average salary used by a Showdown winner was $48,849 and that spending under $45,000 won 19% of the time (FanDuel/DK mix not separated in the clip).

> "the average salary left for a winner was 48 849 so under 49 000 uh which is counter intuitive to everything that we do right if we have more salary left what do we want to do we want to use all that salary because we can get a perceived better player"  
> [A Data Driven Look at How to Win NFL Showdown Contests on Fanduel and Draftkings (DFS Army - Daily Fantasy Sports )](https://www.youtube.com/watch?v=ofyXOG5XlbA&t=2200s) — quote verified against source text: yes

- Topic: winning salary left (DFS Army video)
- Source type: YouTube
- Date: 2020-09-07
- YouTube timestamp: 36:40 (2200s)
- Site: not stated
- Format: Showdown
- Sample size: not stated
- Time period: not stated
- Outcome definition: not stated
- Method / formula: not stated
- Features / data: not stated
- Result / effect size: not stated
- Limitations: Spoken figure; transcript reads 'under 55 000' for the second statistic, which is not a valid DK cap figure - treat as unverified.
- Conflicting evidence: none found
- Code / data availability: not stated
- Reproducibility: not stated
- Layer affected: field
- Claim tag: EMPIRICAL_HISTORICAL_EVIDENCE
- Allowed use: evidence
- Test on our data: Recompute on archive.
- Falsification: n/a
- Implementation candidate: none (evidence only)


#### DUP-01: salary used vs duplication

**Claim.** Salary used vs number of duplicates is weak (R-squared .16) and nonlinear: $50,000->$49,900 barely helps; dupes fall as salary is restricted further, then plateau.

> "used and the number of times your lineup is duplicated is relatively weak (.16 rsq) and the relationship is nonlinear. Using the chart below, you can see that simply decreasing your salary spent from $50,000 to $49,900 hardly improves your chances of building a unique lineup. However, we do notice serious results in reducing our average duplicates as we start restricting salary more. Eventually, we hit a threshold where continuing to use less salary no longer has a big impact and we just end up building worse versions of similarly duplicated lineups."  
> [ETR: How to Create Unique Showdown Lineups](https://establishtherun.com/how-to-create-unique-showdown-lineups/) — quote verified against source text: yes

- Topic: salary used vs duplication
- Source type: practitioner research with disclosed sample
- Date: 2021-09-03
- Site: DraftKings
- Format: Showdown
- Sample size: not stated
- Time period: 2019-20 data (stated for prior version)
- Outcome definition: duplicate count
- Method / formula: Bivariate fit; chart (values not printed)
- Features / data: not stated
- Result / effect size: R2 = .16; nonlinear; plateau threshold shown only in chart
- Limitations: The bucketed curve values are in an image, not text; we cannot extract the $0/$100-500/$500-1k/$1k-2k/$2k+ curve from public text.
- Conflicting evidence: SaberSim/VC2Sx7DGMFE: max-salary lineups 'the most duplicated' (consistent); ETR 101: product ownership R2 .43 (stronger single predictor).
- Code / data availability: not stated
- Reproducibility: not stated
- Layer affected: duplication
- Claim tag: EMPIRICAL_HISTORICAL_EVIDENCE
- Allowed use: evidence
- Test on our data: Fit dupes ~ f(salary_left bucket) + product ownership on archived Showdown CSVs; report partial effect of salary left given product ownership.
- Falsification: Salary-left adds no explained variance once product ownership and CPT/stack features are included.
- Implementation candidate: Dupe model term: piecewise salary-left effect (buckets $0, $100-500, $500-1k, $1k-2k, $2k+), fit on our data only.


#### DUP-02: CPT ownership vs dupes

**Claim.** ETR finds minimal correlation between CPT ownership and the number of duplicates.

> "More importantly, there’s minimal correlation between CPT ownership and the number of duplicates. In other words, as long as you’re being mindful of the remainder of your roster construction, a popular CPT by itself isn’t likely to result in heavily duplicated lineups."  
> [ETR: NFL Showdown 101](https://establishtherun.com/nfl-showdown-101/) — quote verified against source text: yes

- Topic: CPT ownership vs dupes
- Source type: practitioner research with disclosed sample
- Date: 2026-09-05
- Site: DraftKings
- Format: Showdown
- Sample size: every DK flagship Showdown lineup since 2020 (stated by ETR)
- Time period: not stated
- Outcome definition: duplicate count
- Method / formula: not stated
- Features / data: not stated
- Result / effect size: not stated
- Limitations: not stated
- Conflicting evidence: SaberSim hTUUH0mfpfU: 'the more ownership the more likely a lineup is to be duplicated' (lineup-level, not CPT-only).
- Code / data availability: not stated
- Reproducibility: not stated
- Layer affected: duplication
- Claim tag: EMPIRICAL_HISTORICAL_EVIDENCE
- Allowed use: evidence
- Test on our data: Regress dupes on CPT ownership alone vs product of FLEX ownership.
- Falsification: CPT ownership has R2 comparable to product ownership on our archive.
- Implementation candidate: none (evidence only)


#### DUP-03: geomean dupe threshold formula

**Claim.** SaberSim's dupe filter: geomean threshold = (target dupes / contest entries)^(1/6) for a DK Showdown lineup (6 players).

> "you would pick a number of dupes that you want to shoot for like maybe I don't want to play anything D more than 20 times so it' be parentheses 20 divided by you know say you're playing a 20,000 entry contest 20,000 to the power and then you would say one divided by six here where six is the number of players in a DraftKings Showdown lineup uh it could be five for FanDuel"  
> [DFS Q&A: What are the optimal filters for NFL Showdown? (SaberSim DFS - Daily Fantasy Sports Strategy)](https://www.youtube.com/watch?v=hFDu4Yx4VrY&t=478s) — quote verified against source text: yes

- Topic: geomean dupe threshold formula
- Source type: YouTube
- Date: 2024-09-07
- YouTube timestamp: 7:58 (478s)
- Site: DraftKings
- Format: Showdown
- Sample size: not stated
- Time period: not stated
- Outcome definition: not stated
- Method / formula: (D/N)^(1/6) compared to the lineup's geometric-mean ownership
- Features / data: not stated
- Result / effect size: not stated
- Limitations: Assumes independence across slots (product ownership); no validation reported.
- Conflicting evidence: none found
- Code / data availability: not stated
- Reproducibility: not stated
- Layer affected: duplication
- Claim tag: EXTERNAL_MODEL_OUTPUT
- Allowed use: shadow candidate (baseline estimator)
- Test on our data: Compute N x product(slot ownership) for every archived lineup; compare to actual dupe counts (calibration plot, log-scale).
- Falsification: Independent-product estimator biased by >2x in the high-chalk decile.
- Implementation candidate: Baseline estimator #1 in the dupe stack.


#### DUP-04: geomean target (AceMind)

**Claim.** AceMind: for 10-or-fewer dupes 'you'd be looking for a geomean of 22'.

> "if you wanted to say like uh a number of dupes say 10 or less you'd be looking for a geome of 22 you guys can just figure this this is a very simple formula you guys can figure this out"  
> [AceMind Catch up-----NFL showdown and other best practices using their sims. (TrueDFS)](https://www.youtube.com/watch?v=yle0xQ2cuq8&t=2058s) — quote verified against source text: yes

- Topic: geomean target (AceMind)
- Source type: YouTube
- Date: 2024-12-05
- YouTube timestamp: 34:18 (2058s)
- Site: not stated
- Format: Showdown
- Sample size: not stated
- Time period: not stated
- Outcome definition: not stated
- Method / formula: not stated
- Features / data: not stated
- Result / effect size: not stated
- Limitations: Contest size not stated in clip.
- Conflicting evidence: none found
- Code / data availability: not stated
- Reproducibility: not stated
- Layer affected: duplication
- Claim tag: EXPERT_OPINION
- Allowed use: hypothesis
- Test on our data: Check implied relation on archive.
- Falsification: n/a
- Implementation candidate: none (evidence only)


#### DUP-05: dupe variance (AceMind)

**Claim.** AceMind reports Sim dupes as an average across five generated fields plus median and standard deviation, emphasizing a range of possible duplications.

> "so I guess Sim dupes would be it's it's an average that's the average amount of times yeah of the five and and 244 would be the median dupes yeah and that's why we sort of included like a median and a standard deviation so you you could understand that there's a range right of possible duplications"  
> [AceMind Catch up-----NFL showdown and other best practices using their sims. (TrueDFS)](https://www.youtube.com/watch?v=yle0xQ2cuq8&t=1926s) — quote verified against source text: yes

- Topic: dupe variance (AceMind)
- Source type: YouTube
- Date: 2024-12-05
- YouTube timestamp: 32:06 (1926s)
- Site: not stated
- Format: Showdown
- Sample size: not stated
- Time period: not stated
- Outcome definition: not stated
- Method / formula: not stated
- Features / data: not stated
- Result / effect size: not stated
- Limitations: not stated
- Conflicting evidence: none found
- Code / data availability: not stated
- Reproducibility: not stated
- Layer affected: duplication
- Claim tag: EXTERNAL_MODEL_OUTPUT
- Allowed use: shadow candidate
- Test on our data: Report dupe estimate intervals, not points; score with interval coverage.
- Falsification: Interval coverage < nominal on archive.
- Implementation candidate: Dupe estimator outputs a distribution (mean, median, p10/p90).


#### DUP-06: max-salary dupes (SaberSim)

**Claim.** SaberSim: max-salary-cap lineups are going to be the most duplicated; suggests capping at $49,900.

> "basically just ignore Max salary cap lineups like set the max salary cap to 49900 instead of 50,000 here a lot of people building by hand are going to try and use as much salary as possible and so I think that you know Max salary lineup are going to be the the most duplicated lineups that you can build here"  
> [DFS Q&A: Preventing Duplication in NFL Showdown (SaberSim DFS - Daily Fantasy Sports Strategy)](https://www.youtube.com/watch?v=VC2Sx7DGMFE&t=193s) — quote verified against source text: yes

- Topic: max-salary dupes (SaberSim)
- Source type: YouTube
- Date: 2023-10-17
- YouTube timestamp: 3:13 (193s)
- Site: DraftKings
- Format: Showdown
- Sample size: not stated
- Time period: not stated
- Outcome definition: not stated
- Method / formula: not stated
- Features / data: not stated
- Result / effect size: not stated
- Limitations: not stated
- Conflicting evidence: ETR DUP-01: $50,000->$49,900 'hardly improves' uniqueness.
- Code / data availability: not stated
- Reproducibility: not stated
- Layer affected: duplication
- Claim tag: EXPERT_OPINION
- Allowed use: hypothesis
- Test on our data: Compare mean dupes at exactly $50,000 vs $49,900 vs $49,500 controlling for product ownership.
- Falsification: No difference at $49,900.
- Implementation candidate: none (evidence only)


#### DUP-07: portfolio dupes vs results (Milly Makers)

**Claim.** SaberSim reviewed Milly Maker Showdowns via Flashback: the two most negative sim-ROI portfolios were one with almost all unique lineups and one with the most average dupes.

> "the two lowest like most negative Sim Roi portfolios in a given Showdown contest was from two players one of them had like almost all of their lineups were unique and then one of them had like the most dupes the most average dupes on the Slate and they were both terrible right"  
> [DFS Q&A: Preventing Duplication in NFL Showdown (SaberSim DFS - Daily Fantasy Sports Strategy)](https://www.youtube.com/watch?v=VC2Sx7DGMFE&t=478s) — quote verified against source text: yes

- Topic: portfolio dupes vs results (Milly Makers)
- Source type: YouTube
- Date: 2023-10-17
- YouTube timestamp: 7:58 (478s)
- Site: DraftKings
- Format: Showdown
- Sample size: 'a couple weeks of Milly makers'
- Time period: not stated
- Outcome definition: sim ROI
- Method / formula: not stated
- Features / data: not stated
- Result / effect size: not stated
- Limitations: Anecdotal; sim ROI is model-dependent.
- Conflicting evidence: none found
- Code / data availability: not stated
- Reproducibility: not stated
- Layer affected: duplication / portfolio
- Claim tag: EXPERT_OPINION
- Allowed use: hypothesis
- Test on our data: Relationship between portfolio mean dupes and realized ROI across many entrants in our archive.
- Falsification: Monotone relation (not U-shaped).
- Implementation candidate: none (evidence only)


#### DUP-08: dupes by sim-ROI tier

**Claim.** SaberSim: top sim-ROI Showdown lineups tend to have about five or fewer dupes; negative sim-ROI lineups more like five to ten.

> "At the top, it's like five and below. When we get into like negative SIM ROI territory, we start to see more like five to 10. So, I think that you need to account for duplication a little bit, but I don't think you need to account for duplication a lot"  
> [DFS Q&A: Understanding Sim ROI Results (SaberSim DFS - Daily Fantasy Sports Strategy)](https://www.youtube.com/watch?v=d883hjQvUCc&t=1015s) — quote verified against source text: yes

- Topic: dupes by sim-ROI tier
- Source type: YouTube
- Date: 2025-12-25
- YouTube timestamp: 16:55 (1015s)
- Site: not stated
- Format: Showdown
- Sample size: not stated
- Time period: not stated
- Outcome definition: not stated
- Method / formula: not stated
- Features / data: not stated
- Result / effect size: not stated
- Limitations: not stated
- Conflicting evidence: none found
- Code / data availability: not stated
- Reproducibility: not stated
- Layer affected: duplication
- Claim tag: EXPERT_OPINION
- Allowed use: hypothesis
- Test on our data: n/a until our contest sim exists
- Falsification: n/a
- Implementation candidate: none (evidence only)


#### OWN-01: ownership by contest type (SaberSim example)

**Claim.** SaberSim example: a player ~23% owned in flagship MME projects to 41% in high-stakes single entry.

> "all of these have different inputs different uh things that go into them that affect the ownership projections right so like for instance I'm looking at Flagship mme chage is about 23% owned and what if I go look at high stake single entry okay well he goes up to 41% right so there's a big fluctuation between the different contest types here"  
> [DFS Q&A: How do you recommend filtering out lineups for NFL Showdown? (SaberSim DFS - Daily Fantasy Sports Strategy)](https://www.youtube.com/watch?v=hTUUH0mfpfU&t=131s) — quote verified against source text: yes

- Topic: ownership by contest type (SaberSim example)
- Source type: YouTube
- Date: 2025-01-15
- YouTube timestamp: 2:11 (131s)
- Site: not stated
- Format: not stated
- Sample size: not stated
- Time period: not stated
- Outcome definition: not stated
- Method / formula: not stated
- Features / data: not stated
- Result / effect size: not stated
- Limitations: not stated
- Conflicting evidence: none; consistent with SaberSim docs (65% SE vs 41% MME example).
- Code / data availability: not stated
- Reproducibility: not stated
- Layer affected: ownership
- Claim tag: EXTERNAL_MODEL_OUTPUT
- Allowed use: evidence (contest-bucket effect exists)
- Test on our data: Measure same-slate ownership across our 150/20/2-entry contest captures.
- Falsification: Ownership identical across buckets within noise.
- Implementation candidate: Bucket-specific ownership model (P150/P20/P2).


#### OWN-02: ownership by contest type (ETR)

**Claim.** ETR (Levitan) states the 'best plays' carry higher ownership in single-entry than 150-max tournaments.

> "The differences are in field size and projected ownership (expect the “best plays” to be more owned in these kinds of tournaments vs. the 150-max tournaments)."  
> [ETR: Levitan's DFS Game Selection](https://establishtherun.com/levitans-dfs-game-selection-which-contests-to-play/) — quote verified against source text: yes

- Topic: ownership by contest type (ETR)
- Source type: practitioner
- Date: 2026-09-01
- Site: DraftKings
- Format: not stated
- Sample size: not stated
- Time period: not stated
- Outcome definition: not stated
- Method / formula: not stated
- Features / data: not stated
- Result / effect size: not stated
- Limitations: not stated
- Conflicting evidence: none found
- Code / data availability: not stated
- Reproducibility: not stated
- Layer affected: ownership
- Claim tag: EXPERT_OPINION
- Allowed use: hypothesis
- Test on our data: Same as OWN-01.
- Falsification: Same as OWN-01.
- Implementation candidate: none (evidence only)


#### OWN-03: contest archetypes and field generator defaults (Stokastic)

**Claim.** Stokastic's Contest Generator uses three archetypes (Low Stakes <$3, Marquee incl. 150-max/Milly, High Stakes >=$100); default field stack mix QB+1 45%, QB+2 25%, QB+3 5%, runback ~25%, ~25% no stack; Showdown pool up to 50,000 lineups.

> "Low Stakes is roughly anything under a $3 buy-in. - Marquee covers the majority of contests, including the big-field 150-max tournaments and the Milly Maker. If you are unsure, this is usually the right pick. - High Stakes is generally anything with a $100 or higher buy-in."  
> [Stokastic: How To Win At NFL DFS In 2026](https://www.stokastic.com/articles/nfl-dfs/how-to-win-at-nfl-dfs) — quote verified against source text: yes

- Topic: contest archetypes and field generator defaults (Stokastic)
- Source type: documented commercial-tool methodology
- Date: 2026-07-19
- Site: DraftKings and FanDuel
- Format: Classic (stack mix); Showdown (pool size)
- Sample size: not stated
- Time period: not stated
- Outcome definition: not stated
- Method / formula: not stated
- Features / data: not stated
- Result / effect size: not stated
- Limitations: Defaults, not measured field data; no validation reported.
- Conflicting evidence: none found
- Code / data availability: not stated
- Reproducibility: not stated
- Layer affected: field
- Claim tag: EXTERNAL_MODEL_OUTPUT
- Allowed use: shadow candidate (priors)
- Test on our data: Measure archived classic field stack mix (10/4 contests) vs these defaults.
- Falsification: Archived stack mix differs by >10 pts.
- Implementation candidate: none (evidence only)


#### OWN-04: ownership = exposure of generated field (SaberSim)

**Claim.** SaberSim's ownership projections are the exposures of its built field lineups; custom ownership has no effect on contest sims unless a custom field is generated.

> "adjusting the you know the exposures in the ownership build of the field lineups here end up becoming the ownership projections right so for instance flarey 40.8% exposure in the flagship mme field lineups I go to the homepage I see fl's ownership 40.82 right so that number matches so this is what's happening um these are where the ownership projections come from they come from the ownership build"  
> [DFS Q&A: Which is better, running a contest sim against the field lineups or your own lineups? (SaberSim DFS - Daily Fantasy Sports Strategy)](https://www.youtube.com/watch?v=FbQSwk4Kfmg&t=578s) — quote verified against source text: yes

- Topic: ownership = exposure of generated field (SaberSim)
- Source type: YouTube
- Date: 2024-08-10
- YouTube timestamp: 9:38 (578s)
- Site: not stated
- Format: not stated
- Sample size: not stated
- Time period: not stated
- Outcome definition: not stated
- Method / formula: not stated
- Features / data: not stated
- Result / effect size: not stated
- Limitations: not stated
- Conflicting evidence: none found
- Code / data availability: not stated
- Reproducibility: not stated
- Layer affected: ownership / field
- Claim tag: EXTERNAL_MODEL_OUTPUT
- Allowed use: evidence (architecture pattern)
- Test on our data: n/a (design)
- Falsification: n/a
- Implementation candidate: Ownership is reported as a statistic of our generated field; the field, not a %, feeds the contest sim.


#### OWN-05: CPT projection handling

**Claim.** SaberSim: captain projections are just 1.5x the FLEX projections; upload FLEX projections only.

> "so you shouldn't upload Captain projection so and the reason for that is Captain projections are just 1.5x the flex projections"  
> [DFS Q&A: What are the optimal filters for NFL Showdown? (SaberSim DFS - Daily Fantasy Sports Strategy)](https://www.youtube.com/watch?v=hFDu4Yx4VrY&t=1841s) — quote verified against source text: yes

- Topic: CPT projection handling
- Source type: YouTube
- Date: 2024-09-07
- YouTube timestamp: 30:41 (1841s)
- Site: DraftKings
- Format: Showdown
- Sample size: not stated
- Time period: not stated
- Outcome definition: not stated
- Method / formula: not stated
- Features / data: not stated
- Result / effect size: not stated
- Limitations: True for points mean; CPT ownership is NOT a fixed multiple of FLEX ownership (see DATA-04/05/06).
- Conflicting evidence: none found
- Code / data availability: not stated
- Reproducibility: not stated
- Layer affected: football -> DK scoring
- Claim tag: EXTERNAL_MODEL_OUTPUT
- Allowed use: evidence
- Test on our data: Unit test: CPT draw = 1.5 x same-world FLEX draw.
- Falsification: n/a
- Implementation candidate: none (evidence only)


#### OWN-06: CPT vs FLEX ownership projected separately (DFS Army)

**Claim.** DFS Army projects the incidence of a player being captain separately from the incidence of being flex for every primetime Showdown.

> "within the domination station optimizer at dfs army next to every player name including in showdowns for every prime time showdown we have ownership projections we project the incident of a player being the captain we predict the incidence of them being the flex"  
> [A Data Driven Look at How to Win NFL Showdown Contests on Fanduel and Draftkings (DFS Army - Daily Fantasy Sports )](https://www.youtube.com/watch?v=ofyXOG5XlbA&t=3409s) — quote verified against source text: yes

- Topic: CPT vs FLEX ownership projected separately (DFS Army)
- Source type: YouTube
- Date: 2020-09-07
- YouTube timestamp: 56:49 (3409s)
- Site: not stated
- Format: Showdown
- Sample size: not stated
- Time period: not stated
- Outcome definition: not stated
- Method / formula: not stated
- Features / data: not stated
- Result / effect size: not stated
- Limitations: not stated
- Conflicting evidence: none found
- Code / data availability: not stated
- Reproducibility: not stated
- Layer affected: ownership
- Claim tag: EXTERNAL_MODEL_OUTPUT
- Allowed use: evidence
- Test on our data: n/a
- Falsification: n/a
- Implementation candidate: none (evidence only)


#### NEWS-01: ownership redistribution after a late scratch (SaberSim)

**Claim.** SaberSim describes redistributing a scratched player's ownership (e.g., 10%) 'amongst the most likely candidates whose games have not started', then re-running ownership.

> "Let's assume they're 10% owned, which is kind of high, but I'm just going to use that as a number. Well, that 10% has to go somewhere, right? It doesn't just disappear. So what we would do is, okay, hey, we know that Godette had a 10% ownership. We need to redistribute that amongst the most likely candidates whose games have not started, right? So then we would rerun ownership. This is the live fields and basically assign that ownership to the most likely candidates."  
> [DFS Q&A: Understanding Sim ROI Results (SaberSim DFS - Daily Fantasy Sports Strategy)](https://www.youtube.com/watch?v=d883hjQvUCc&t=634s) — quote verified against source text: yes

- Topic: ownership redistribution after a late scratch (SaberSim)
- Source type: YouTube
- Date: 2025-12-25
- YouTube timestamp: 10:34 (634s)
- Site: DraftKings
- Format: not stated
- Sample size: not stated
- Time period: not stated
- Outcome definition: not stated
- Method / formula: not stated
- Features / data: not stated
- Result / effect size: not stated
- Limitations: Mechanism of 'most likely candidates' not specified; NBA example in clip.
- Conflicting evidence: none found
- Code / data availability: not stated
- Reproducibility: not stated
- Layer affected: ownership
- Claim tag: EXTERNAL_MODEL_OUTPUT
- Allowed use: shadow candidate
- Test on our data: For each archived slate with a late inactive, compare pre-news projected vs actual ownership of the direct backup and next-best same-salary options.
- Falsification: Ownership shifts are not concentrated on the role-replacement player.
- Implementation candidate: Ownership re-solve triggered by football-layer role-state change; field regenerated, not patched.


#### NEWS-02: SaberSim live ownership after lock

**Claim.** After lock a new sim runs ~10 minutes later and a 'SaberSim ownership live' source appears; NFL has live ownership for late swap.

> "slate uh slate locks and then a new sim runs 10 minutes after okay well after that new sim runs then you're going to see a new ownership Source in this gear icon and it's going to say saber Sim ownership and then there's going to be a second one it's going to say saber Sim ownership live you have to come in here and then go and switch to the the corresponding live option"  
> [DFS Q&A: How do you recommend filtering out lineups for NFL Showdown? (SaberSim DFS - Daily Fantasy Sports Strategy)](https://www.youtube.com/watch?v=hTUUH0mfpfU&t=338s) — quote verified against source text: yes

- Topic: SaberSim live ownership after lock
- Source type: YouTube
- Date: 2025-01-15
- YouTube timestamp: 5:38 (338s)
- Site: not stated
- Format: not stated
- Sample size: not stated
- Time period: not stated
- Outcome definition: not stated
- Method / formula: not stated
- Features / data: not stated
- Result / effect size: not stated
- Limitations: not stated
- Conflicting evidence: none found
- Code / data availability: not stated
- Reproducibility: not stated
- Layer affected: ownership / late swap
- Claim tag: EXTERNAL_MODEL_OUTPUT
- Allowed use: evidence
- Test on our data: n/a
- Falsification: n/a
- Implementation candidate: none (evidence only)


#### NEWS-03: final rebuild timing

**Claim.** SaberSim recommends a final rebuild within 15 minutes of slate start because news changes ownership and projections dramatically.

> "I would for sure do a final rebuild 15 minutes within 15 minutes of the slate starting is is would be my uh recommendations because news can just change so dramatically."  
> [DFS Q&A: Should You Adjust Minimum Salary for Classic and Showdown Slates? (SaberSim DFS - Daily Fantasy Sports Strategy)](https://www.youtube.com/watch?v=wpV5KCr2lAg&t=1046s) — quote verified against source text: yes

- Topic: final rebuild timing
- Source type: YouTube
- Date: 2025-11-20
- YouTube timestamp: 17:26 (1046s)
- Site: not stated
- Format: not stated
- Sample size: not stated
- Time period: not stated
- Outcome definition: not stated
- Method / formula: not stated
- Features / data: not stated
- Result / effect size: not stated
- Limitations: not stated
- Conflicting evidence: none found
- Code / data availability: not stated
- Reproducibility: not stated
- Layer affected: ownership / operations
- Claim tag: EXPERT_OPINION
- Allowed use: hypothesis
- Test on our data: Snapshot projected ownership at T-90, T-30, T-10 and compare each to actual.
- Falsification: No accuracy gain closer to lock.
- Implementation candidate: none (evidence only)


#### NEWS-04: projected vs actual ownership miss (example)

**Claim.** SaberSim example: McCaffrey projected 31% ownership, actual 21%.

> "McCaffrey projected for 31% ownership. He actually came in at 21% ownership. So, his ownership uh deviated from what we expected. And uh looks like the field got that one wrong. they probably should have rostered him more because he had a pretty solid day."  
> [DFS Q&A: Should You Adjust Minimum Salary for Classic and Showdown Slates? (SaberSim DFS - Daily Fantasy Sports Strategy)](https://www.youtube.com/watch?v=wpV5KCr2lAg&t=256s) — quote verified against source text: yes

- Topic: projected vs actual ownership miss (example)
- Source type: YouTube
- Date: 2025-11-20
- YouTube timestamp: 4:16 (256s)
- Site: not stated
- Format: not stated
- Sample size: 1
- Time period: not stated
- Outcome definition: not stated
- Method / formula: not stated
- Features / data: not stated
- Result / effect size: not stated
- Limitations: not stated
- Conflicting evidence: none found
- Code / data availability: not stated
- Reproducibility: not stated
- Layer affected: ownership / evaluation
- Claim tag: EMPIRICAL_HISTORICAL_EVIDENCE
- Allowed use: evidence (anecdote)
- Test on our data: Ownership error distribution (MAE, by ownership tier) per slate.
- Falsification: n/a
- Implementation candidate: none (evidence only)


#### NEWS-05: news timestamps (Stokastic)

**Claim.** Stokastic advises checking projection and ownership update timestamps against late inactive announcements.

> "If news broke, a starter ruled out an hour before kickoff, and the projections updated *after* that news, the field you are about to build will account for it. If they updated before, it will not, and you would be spending a minute modeling a world that no longer exists."  
> [Stokastic: How To Win At NFL DFS In 2026](https://www.stokastic.com/articles/nfl-dfs/how-to-win-at-nfl-dfs) — quote verified against source text: yes

- Topic: news timestamps (Stokastic)
- Source type: documented commercial-tool methodology
- Date: 2026-07-19
- Site: not stated
- Format: not stated
- Sample size: not stated
- Time period: not stated
- Outcome definition: not stated
- Method / formula: not stated
- Features / data: not stated
- Result / effect size: not stated
- Limitations: not stated
- Conflicting evidence: none found
- Code / data availability: not stated
- Reproducibility: not stated
- Layer affected: ownership / governance
- Claim tag: EXPERT_OPINION
- Allowed use: evidence
- Test on our data: Every ownership snapshot carries as_of timestamp and the news-event ledger it reflects.
- Falsification: n/a
- Implementation candidate: Point-in-time ownership snapshots keyed to news-event IDs.


### P1 records


#### FSV-01: contest-sim calibration (actual vs predicted cash)

**Claim.** On 49,146 Showdown lineups across 33 slates, lineups in the 18-21% predicted-cash bucket cashed 20.8%; lineups predicted 30%+ cashed 31.1%.

> "As predicted cash rate increased, actual cash rate increased as well. For example, lineups in the 18-21% sim cash rate bucket cashed 20.8% of the time, while lineups that were predicted to cash at a 30+% clip cashed 31.1% of the time."  
> [ETR: NFL Showdown DFS: What Are the Sims Saying?](https://establishtherun.com/nfl-showdown-dfs-what-are-the-sims-saying/) — quote verified against source text: yes

- Topic: contest-sim calibration (actual vs predicted cash)
- Source type: practitioner research with disclosed sample
- Date: 2026-09-04
- Site: DraftKings
- Format: Showdown
- Sample size: 49,146 lineups; 33 slates
- Time period: not stated
- Outcome definition: cash rate
- Method / formula: Bucketed predicted vs actual cash rate (reliability table)
- Features / data: not stated
- Result / effect size: not stated
- Limitations: Only 33 slates; one sim vendor; small high-stakes fields.
- Conflicting evidence: none found
- Code / data availability: not stated
- Reproducibility: not stated
- Layer affected: evaluation / field
- Claim tag: EMPIRICAL_HISTORICAL_EVIDENCE
- Allowed use: evidence (validation method template)
- Test on our data: Reliability table for our contest sim: predicted cash/top-1%/win prob vs realized, bucketed.
- Falsification: Our predicted-vs-actual slope significantly different from 1.
- Implementation candidate: Contest-sim calibration report as a promotion gate.


#### PORT-01: portfolio optimization (academic)

**Claim.** Picking Winners (Hunter/Vielma/Zaman lineage) constructs portfolios to maximize the expected score of the best-performing lineup; in 10 hockey scenarios the proposed 20-lineup method scored highest.

> "Specifically, our method produces solutions with the highest score among the three methods in all the ten scenarios tested when m = 20."  
> [Picking Winners: Diversification through Portfolio Optimization (NUS IORA PDF)](https://iora.nus.edu.sg/wp-content/uploads/2024/04/PickingWinners.pdf) — quote verified against source text: yes

- Topic: portfolio optimization (academic)
- Source type: paper
- Date: not stated
- Site: not stated
- Format: Classic (hockey)
- Sample size: 10 scenarios
- Time period: not stated
- Outcome definition: best-lineup score
- Method / formula: not stated
- Features / data: not stated
- Result / effect size: not stated
- Limitations: Hockey; multivariate normal assumption; no opponent field.
- Conflicting evidence: none found
- Code / data availability: not stated
- Reproducibility: not stated
- Layer affected: portfolio
- Claim tag: PRODUCTION_CANDIDATE
- Allowed use: shadow candidate
- Test on our data: Compare greedy marginal-EV portfolio vs max-best-lineup objective on our contest sim.
- Falsification: No improvement over greedy marginal EV.
- Implementation candidate: none (evidence only)


#### PORT-02: portfolio optimization with simulated covariance (ITOR)

**Claim.** ITOR (2024) simulates matches to estimate player mean/covariance and uses a mixed-integer quadratic program; reported 34%+ ROI over the last 8 EPL weeks of 2018/19 on FanTeam.

> "First, the model simulates tournament matches to obtain the predictions of players' mean fantasy points and the covariance matrix. These statistics are then passed to an optimization solver, which solves our mixed-integer quadratic program and produces a portfolio of lineups."  
> [International Transactions in Operational Research, itor.13344](https://onlinelibrary.wiley.com/doi/10.1111/itor.13344) — quote verified against source text: yes

- Topic: portfolio optimization with simulated covariance (ITOR)
- Source type: paper
- Date: not stated
- Site: FanTeam
- Format: Classic (soccer)
- Sample size: 8 game weeks
- Time period: not stated
- Outcome definition: ROI
- Method / formula: not stated
- Features / data: not stated
- Result / effect size: not stated
- Limitations: Tiny out-of-sample period; soccer.
- Conflicting evidence: none found
- Code / data availability: data in a public repository (stated)
- Reproducibility: not stated
- Layer affected: portfolio
- Claim tag: EMPIRICAL_HISTORICAL_EVIDENCE
- Allowed use: evidence
- Test on our data: n/a
- Falsification: n/a
- Implementation candidate: none (evidence only)


#### PORT-03: portfolio selection by correlation (SaberSim Portfolio)

**Claim.** SaberSim's Portfolio looks at how lineups correlate with each other, accounting for win equity while minimizing downside, adding lineups sequentially.

> "It's trying to account for win equity while also minimizing downside. And then it's saying, hey, you know, play these two first and then add this one and then add this one and then add this one. and then it's building out this set of lineups that effectively plays better together."  
> [DFS Q&A: Does Late Swap Use Live Ownership? (SaberSim DFS - Daily Fantasy Sports Strategy)](https://www.youtube.com/watch?v=Qymh4oizKdM&t=877s) — quote verified against source text: yes

- Topic: portfolio selection by correlation (SaberSim Portfolio)
- Source type: YouTube
- Date: 2026-02-28
- YouTube timestamp: 14:37 (877s)
- Site: not stated
- Format: not stated
- Sample size: not stated
- Time period: not stated
- Outcome definition: not stated
- Method / formula: not stated
- Features / data: not stated
- Result / effect size: not stated
- Limitations: not stated
- Conflicting evidence: none found
- Code / data availability: not stated
- Reproducibility: not stated
- Layer affected: portfolio
- Claim tag: EXTERNAL_MODEL_OUTPUT
- Allowed use: shadow candidate
- Test on our data: Greedy marginal contest-EV selection over sealed worlds with an overlap/downside term.
- Falsification: Greedy marginal EV beats it out of sample.
- Implementation candidate: none (evidence only)


#### PORT-04: backtest ranking of sort metrics

**Claim.** SaberSim says its backtesting showed Portfolio Plus (contest-sim with actual payout structures) is the strongest sorting metric for 150-max.

> "Uh next question. This will go with the above. Do you recommend running strictly portfolio plus when maxing when doing the max 150 lineups? Uh I do. uh our back testing showed that portfolio plus is the strongest sorting metric that we have in the in you know the options here currently."  
> [DFS Q&A: How Can You Reduce Dupes in NFL Showdown? (SaberSim DFS - Daily Fantasy Sports Strategy)](https://www.youtube.com/watch?v=r44AIMlrnmk&t=1293s) — quote verified against source text: yes

- Topic: backtest ranking of sort metrics
- Source type: YouTube
- Date: 2025-11-25
- YouTube timestamp: 21:33 (1293s)
- Site: not stated
- Format: not stated
- Sample size: not stated
- Time period: not stated
- Outcome definition: not stated
- Method / formula: not stated
- Features / data: not stated
- Result / effect size: not stated
- Limitations: No backtest metrics disclosed.
- Conflicting evidence: none found
- Code / data availability: not stated
- Reproducibility: not stated
- Layer affected: portfolio
- Claim tag: EXTERNAL_MODEL_OUTPUT
- Allowed use: hypothesis
- Test on our data: Ablation: payout-aware vs payout-agnostic portfolio on archive.
- Falsification: No difference.
- Implementation candidate: none (evidence only)


#### PORT-05: field-aware optimizer fades high-variance chalk

**Claim.** SaberSim: high-variance highly owned players are faded more aggressively by its sim-based optimizer than low-variance highly owned players.

> "It's actually much more powerful than that because high variance highly owned players are going to be faded more aggressively by the optimizer automatically than low variance highly owned players."  
> [DFS Lineup Optimizers Are Obsolete. You Need a Simulator. (SaberSim DFS - Daily Fantasy Sports Strategy)](https://www.youtube.com/watch?v=07ukRKU0LoI&t=1081s) — quote verified against source text: yes

- Topic: field-aware optimizer fades high-variance chalk
- Source type: YouTube
- Date: 2021-09-07
- YouTube timestamp: 18:01 (1081s)
- Site: not stated
- Format: not stated
- Sample size: not stated
- Time period: not stated
- Outcome definition: not stated
- Method / formula: not stated
- Features / data: not stated
- Result / effect size: not stated
- Limitations: not stated
- Conflicting evidence: none found
- Code / data availability: not stated
- Reproducibility: not stated
- Layer affected: portfolio
- Claim tag: EXPERT_OPINION
- Allowed use: hypothesis
- Test on our data: Emergent check in our contest-EV optimizer.
- Falsification: n/a
- Implementation candidate: none (evidence only)


#### SIM-01: play-by-play game simulation (commercial)

**Claim.** SaberSim describes its engine as simulating a full game one play at a time while tracking score, clock and other factors that influence play calling.

> "we have the only complete game simulator. And that means that we're simming out a full game one play at a time, keeping track of the score, the clock, and dozens of other factors that influence play calling and performance."  
> [DFS Lineup Optimizers Are Obsolete. You Need a Simulator. (SaberSim DFS - Daily Fantasy Sports Strategy)](https://www.youtube.com/watch?v=07ukRKU0LoI&t=28s) — quote verified against source text: yes

- Topic: play-by-play game simulation (commercial)
- Source type: YouTube
- Date: 2021-09-07
- YouTube timestamp: 0:28 (28s)
- Site: not stated
- Format: not stated
- Sample size: not stated
- Time period: not stated
- Outcome definition: not stated
- Method / formula: not stated
- Features / data: not stated
- Result / effect size: not stated
- Limitations: not stated
- Conflicting evidence: none found
- Code / data availability: not stated
- Reproducibility: not stated
- Layer affected: football (joint simulation)
- Claim tag: EXTERNAL_MODEL_OUTPUT
- Allowed use: evidence (architecture pattern)
- Test on our data: n/a
- Falsification: n/a
- Implementation candidate: none (evidence only)


#### SIM-02: Markov play-sequence simulation (academic)

**Claim.** A Markov model over (yard line, down, distance, possession) estimated from 467,199 plays (2002-2013) simulates play sequences to produce a score-difference distribution.

> "We used an aggregated dataset of play-by-play data from the 2002-2013 NFL seasons [8][9][10]. The processed dataset contains a total of 467,199 plays in total. The 2012 and 2013 NFL seasons were separated to be used as our test set, and were not used for training our model."  
> [Blanc, Luxenberg, Xie - NFL Score Difference Prediction with Markov Modeling (Stanford CS229)](https://cs229.stanford.edu/proj2016/report/BlancLuxenbergXie-NFLScoreDifferencePredictionWithMarkovModeling-report.pdf) — quote verified against source text: yes

- Topic: Markov play-sequence simulation (academic)
- Source type: paper (course project)
- Date: not stated
- Site: not stated
- Format: not stated
- Sample size: 467,199 plays
- Time period: 2002-2013 (2012-13 held out)
- Outcome definition: not stated
- Method / formula: not stated
- Features / data: not stated
- Result / effect size: test mean log-likelihood -2.9692; avg squared error 51.3062
- Limitations: Course project; team-level only; no player allocation.
- Conflicting evidence: none found
- Code / data availability: not stated
- Reproducibility: not stated
- Layer affected: football (joint simulation)
- Claim tag: PRODUCTION_CANDIDATE
- Allowed use: shadow candidate
- Test on our data: Possession/state-transition sim vs our current team-volume model on held-out games (CRPS on points, plays).
- Falsification: No CRPS gain.
- Implementation candidate: none (evidence only)


#### SIM-03: open-source drive simulators

**Claim.** Open-source NFL drive/play simulators exist: NFLSimulatoR (R; samples plays from nflfastR data) and dlm1223/nfl-simulation (state-sampled drives, ~300 states, 10,000 drives).

> "The intent of NFLSimulatoR (version 0.1.0) is to enable the simulation of plays/drives and evaluate game-play strategies in the National Football League (NFL)."  
> [GitHub rtelmore/NFLSimulatoR; dlm1223/nfl-simulation](https://github.com/rtelmore/NFLSimulatoR) — quote verified against source text: yes

- Topic: open-source drive simulators
- Source type: GitHub
- Date: 2019-11-07
- Site: not stated
- Format: not stated
- Sample size: not stated
- Time period: not stated
- Outcome definition: not stated
- Method / formula: not stated
- Features / data: not stated
- Result / effect size: not stated
- Limitations: Strategy-evaluation tools; no player allocation; validation qualitative.
- Conflicting evidence: none found
- Code / data availability: public code
- Reproducibility: not stated
- Layer affected: football (joint simulation)
- Claim tag: PRODUCTION_CANDIDATE
- Allowed use: code to audit
- Test on our data: Audit state definitions vs ours.
- Falsification: n/a
- Implementation candidate: none (evidence only)


#### COR-01: single-game fantasy correlations

**Claim.** 2018-2023 single-game correlations: QB-WR1 0.542, QB-WR2 0.514, QB-TE1 0.366, QB-RB1 0.09; WR1-same-team WR2 0.345 vs WR1-opposing WR1 0.56; receiving-centric RB-QB 0.118 vs run-centric 0.034.

> "From 2018 to 2023, when having the overall WR1 in a game, the correlation coefficient for the WR1 and the WR2 on the same team (“team stack”) was 0.345. In contrast, the correlation coefficient for the WR1 and the opposing WR1 (“game stack”) was 0.56. Additionally, the distribution of combined points for the game stack was shifted to the right of the team stack."  
> [Spikeweek: Visualizing Single Game Correlation](https://spikeweek.com/visualizing-single-game-correlation/) — quote verified against source text: yes

- Topic: single-game fantasy correlations
- Source type: practitioner research
- Date: 2024-06-28
- Site: not stated
- Format: not stated
- Sample size: not stated
- Time period: 2018-2023
- Outcome definition: not stated
- Method / formula: Pearson correlations
- Features / data: not stated
- Result / effect size: not stated
- Limitations: Scoring system and sample not stated; unconditional (not conditioned on game environment).
- Conflicting evidence: FantasyLabs table: QB-RB1 0.38, QB-WR1 0.54, QB-TE1 0.49 (different definitions/era). Subvertadown: QB-WR strongest, QB-TE second.
- Code / data availability: not stated
- Reproducibility: not stated
- Layer affected: football (correlation) / evaluation
- Claim tag: EMPIRICAL_HISTORICAL_EVIDENCE
- Allowed use: evidence (validation target, never an input)
- Test on our data: Compare correlations emergent from our joint sim to historical correlations by role and game total bucket.
- Falsification: Our sim's emergent correlations fall outside historical CIs.
- Implementation candidate: Correlation-recovery test in the simulation acceptance suite (no copula imposed).


#### COR-02: positional correlation matrix (FantasyLabs)

**Claim.** FantasyLabs NFL correlation table: QB with RB1 0.38, WR1 0.54, WR2 0.48, TE1 0.49, own DST 0.07, opposing DST -0.16.

> "|QB|1.00|0.38|0.25|0.54|0.48|0.49|0.07|0.48|0.34|0.21|0.34|0.34|0.32|-0.16|"  
> [FantasyLabs Correlations](https://www.fantasylabs.com/nfl/correlations-by-sport/) — quote verified against source text: yes

- Topic: positional correlation matrix (FantasyLabs)
- Source type: vendor
- Date: 2011-07-02
- Site: DraftKings (implied)
- Format: not stated
- Sample size: not stated
- Time period: not stated
- Outcome definition: not stated
- Method / formula: not stated
- Features / data: not stated
- Result / effect size: not stated
- Limitations: No sample/era stated; QB-RB 0.38 far above Spikeweek 0.09.
- Conflicting evidence: COR-01.
- Code / data availability: not stated
- Reproducibility: not stated
- Layer affected: football (correlation)
- Claim tag: EXTERNAL_MODEL_OUTPUT
- Allowed use: evidence (validation target)
- Test on our data: Same as COR-01.
- Falsification: n/a
- Implementation candidate: none (evidence only)


### P2 records


#### DIST-01: cold-start prior weighting

**Claim.** Fantasy Projection Lab says volume metrics outweigh the prior at ~6-8 NFL games while rate metrics need closer to a full season; <4 games is prior-dominated.

> "At roughly 6–8 NFL games, most volume-based metrics (targets, carries) reach a threshold where the observed data begins to outweigh the prior meaningfully. Rate-based metrics (yards per carry, catch rate) require larger samples — closer to a full season — to stabilize."  
> [Fantasy Projection Lab: Sample Size and Projection Reliability](https://fantasyprojectionlab.com/sample-size-and-projection-reliability/) — quote verified against source text: yes

- Topic: cold-start prior weighting
- Source type: practitioner
- Date: not stated
- Site: not stated
- Format: not stated
- Sample size: not stated
- Time period: not stated
- Outcome definition: not stated
- Method / formula: not stated
- Features / data: not stated
- Result / effect size: not stated
- Limitations: No data or method disclosed.
- Conflicting evidence: none found
- Code / data availability: not stated
- Reproducibility: not stated
- Layer affected: football (priors)
- Claim tag: EXPERT_OPINION
- Allowed use: hypothesis
- Test on our data: Estimate stabilization points (split-half reliability) for route rate, TPRR, carry share on nflverse participation data.
- Falsification: Our stabilization points differ materially.
- Implementation candidate: Empirical-Bayes shrinkage with stat-specific prior strength.


#### DIST-02: Bayesian weekly updating from ADP prior

**Claim.** Nathan Braun's commercial weekly projections used a Gamma model with ADP-based priors updated by weekly results; he notes the fixed-beta design forced monotonic rankings.

> "Starting in 2013, I sold weekly fantasy projections from a Bayesian model I built. The model used preseason draft rankings as priors, then incorporated weekly results for an updated posterior. I ran the site for four seasons"  
> [Nathan Braun: Bayesian Fantasy Football writeup](https://nathanbraun.com/bayesian-fantasy-football) — quote verified against source text: yes

- Topic: Bayesian weekly updating from ADP prior
- Source type: practitioner
- Date: not stated
- Site: not stated
- Format: not stated
- Sample size: not stated
- Time period: not stated
- Outcome definition: not stated
- Method / formula: not stated
- Features / data: not stated
- Result / effect size: not stated
- Limitations: not stated
- Conflicting evidence: none found
- Code / data availability: not stated
- Reproducibility: not stated
- Layer affected: football (priors)
- Claim tag: EXPERT_OPINION
- Allowed use: evidence (design lesson)
- Test on our data: n/a
- Falsification: n/a
- Implementation candidate: none (evidence only)


### P1 records


#### ROLE-01: snap share -> target volume

**Claim.** Across 1,336 WR player-seasons, under 25% pass-snap share: median 9 targets, 0% reached 80; 85%+ snap share: median 132 targets, 98.4% reached 80.

> "|Under 25%|484|9|0.0%| |25-50%|265|42|4.5%| |50-70%|197|65|27.9%| |70-85%|206|96|78.6%| |85%+|184|132|98.4%|"  
> [Get Inside The Lab: The Two Doors of Fantasy Relevance](https://getinsidethelab.com/the-two-doors-of-fantasy-relevance-what-every-drafted-wide-receiver-since-2008-reveals-about-getting-on-the-field-and-getting-the-ball/) — quote verified against source text: yes

- Topic: snap share -> target volume
- Source type: practitioner research with disclosed sample
- Date: 2026-08-19
- Site: not stated
- Format: not stated
- Sample size: 1,336 player-seasons
- Time period: 2016-2025 (Table 3)
- Outcome definition: not stated
- Method / formula: not stated
- Features / data: nflverse participation (pass-snap share, not routes)
- Result / effect size: not stated
- Limitations: Season level, not game level.
- Conflicting evidence: none found
- Code / data availability: not stated
- Reproducibility: not stated
- Layer affected: football (role)
- Claim tag: EMPIRICAL_HISTORICAL_EVIDENCE
- Allowed use: evidence
- Test on our data: Game-level route participation -> targets mapping on nflverse participation.
- Falsification: n/a
- Implementation candidate: none (evidence only)


#### ROLE-02: leading-WR departure and first feed season

**Claim.** Among 805 at-risk player-seasons, first-feed rate was 12.5% when the team's leading receiver departed vs 4.9% with no departure (OR 2.79, p=0.0011).

> "That is an odds ratio of 2.79 with p = 0.0011."  
> [Get Inside The Lab](https://getinsidethelab.com/the-two-doors-of-fantasy-relevance-what-every-drafted-wide-receiver-since-2008-reveals-about-getting-on-the-field-and-getting-the-ball/) — quote verified against source text: yes

- Topic: leading-WR departure and first feed season
- Source type: practitioner research with disclosed sample
- Date: 2026-08-19
- Site: not stated
- Format: not stated
- Sample size: 805 player-seasons
- Time period: not stated
- Outcome definition: not stated
- Method / formula: not stated
- Features / data: not stated
- Result / effect size: not stated
- Limitations: not stated
- Conflicting evidence: Yards Per Fantasy: season vacated targets adj. R2 < .01 with WR group points (different outcome: group points vs individual feed).
- Code / data availability: not stated
- Reproducibility: not stated
- Layer affected: football (role)
- Claim tag: EMPIRICAL_HISTORICAL_EVIDENCE
- Allowed use: evidence
- Test on our data: n/a (season level)
- Falsification: n/a
- Implementation candidate: none (evidence only)


#### ROLE-03: target redistribution dispersion

**Claim.** Fantasy Projection Lab claims target redistribution after a receiver injury frequently disperses across 3 or 4 players rather than concentrating in one.

> "In NFL passing offenses, target share redistribution after a receiver injury frequently disperses across 3 or 4 players rather than concentrating in one, flattening the upside of any individual beneficiary. Components of a complete injury adjustment workflow, in operational sequence: Cross-reference adjusted projection against snap count and target share data for the most recent completed game as a reality check"  
> [Fantasy Projection Lab: Injury Adjustments](https://fantasyprojectionlab.com/injury-adjustments-in-fantasy-projections/) — quote verified against source text: yes

- Topic: target redistribution dispersion
- Source type: practitioner
- Date: not stated
- Site: not stated
- Format: not stated
- Sample size: not stated
- Time period: not stated
- Outcome definition: not stated
- Method / formula: not stated
- Features / data: not stated
- Result / effect size: not stated
- Limitations: not stated
- Conflicting evidence: GWTTKB: across 165 absence events the top beneficiary captured a median 63% of the scoring gain (concentration). Same vendor elsewhere: top remaining WR absorbs ~40-50%.
- Code / data availability: not stated
- Reproducibility: not stated
- Layer affected: football (role)
- Claim tag: EXPERT_OPINION
- Allowed use: hypothesis
- Test on our data: Within-game redistribution after WR absence using nflverse participation: Herfindahl of target gains among remaining players.
- Falsification: Median top-beneficiary share > 50% (concentration) on our data.
- Implementation candidate: Dirichlet-multinomial within-team shares over active set; concentration is estimated, not assumed.


#### QB-01: QB archetype and WR production

**Claim.** Across 2016-2025, only WR YAC differed significantly by QB archetype (Dual-Threat > Pocket, ANOVA F=7.034, p=0.0019); FPG, touches, TDs, air yards and yards/target did not reach p<0.05.

> "YAC (Yards After Catch) was the only metric with a statistically significant difference across archetypes: ANOVA: F = 7.034, p = 0.0019 Tukey HSD: Dual-Threat significantly outperformed Pocket passers (p = 0.0012). Other pairwise comparisons were not significant."  
> [Science of Fantasy Football: QB Archetypes and WR Production](https://www.scienceoffantasyfootball.com/pre-season-previous-materials/the-impact-of-quarterback-archetypes-on-wide-receiver-production-a-10-year) — quote verified against source text: yes

- Topic: QB archetype and WR production
- Source type: practitioner research with disclosed sample
- Date: 2022-08-09
- Site: not stated
- Format: not stated
- Sample size: not stated
- Time period: 2016-2025
- Outcome definition: not stated
- Method / formula: one-way ANOVA + Tukey HSD
- Features / data: not stated
- Result / effect size: not stated
- Limitations: Archetype by rushing share; not QB identity; season level.
- Conflicting evidence: none found
- Code / data availability: not stated
- Reproducibility: not stated
- Layer affected: football (QB-conditional usage)
- Claim tag: EMPIRICAL_HISTORICAL_EVIDENCE
- Allowed use: evidence
- Test on our data: QB-identity-conditional TPRR / aDOT / route rate with hierarchical partial pooling (QB x receiver).
- Falsification: QB identity adds no predictive value out of sample.
- Implementation candidate: none (evidence only)


### P2 records


#### WX-01: weather effect sizes

**Claim.** Over Under Weather reports QB passing falls ~1.6 yards per extra mph of wind; games lose ~2.6 points at 10-15 mph and ~4 at 15-20 mph; FG accuracy falls ~0.32 pts per mph; below 20F QBs lose 21.7 yards.

> "Passing output falls about 1.6 yards per extra mph of wind. At 10–15 mph a starter throws 6.4 fewer yards, 0.17 fewer yards per attempt and completes 0.94% less than his own season form. Interceptions and sacks do not move."  
> [Over Under Weather: Research](https://overunderweather.com/research) — quote verified against source text: yes

- Topic: weather effect sizes
- Source type: practitioner research with disclosed sample
- Date: not stated
- Site: not stated
- Format: not stated
- Sample size: 4,555 outdoor QB starts; 3,474 outdoor games; 11,697 FG attempts
- Time period: not stated
- Outcome definition: not stated
- Method / formula: Own-season-baseline comparisons with t-stats per band; archived game-window weather
- Features / data: not stated
- Result / effect size: not stated
- Limitations: Vendor; observational; method summary only.
- Conflicting evidence: none found
- Code / data availability: not stated
- Reproducibility: not stated
- Layer affected: football (environment)
- Claim tag: EMPIRICAL_HISTORICAL_EVIDENCE
- Allowed use: evidence
- Test on our data: Replicate wind bands on nflfastR + archived weather; compare effect sizes.
- Falsification: Our replication CI excludes theirs.
- Implementation candidate: Wind/temperature terms in pass efficiency and FG make-probability submodels.


#### WX-02: weather and RB volume

**Claim.** In 159 heavy-rain games lead backs averaged +1.26 carries (t=2.61) and +9.1 yards vs own baseline; 20+ mph wind teams +2.17 rush attempts (t=2.21).

> "The team view agrees and extends the picture: in 20 mph+ wind teams run +2.17 more times than the season average across 80 team games (t = 2.21), while the yardage gain stays inside noise."  
> [Over Under Weather: NFL RB Rushing in Wind & Rain](https://overunderweather.com/research/nfl-rb-weather-rushing-study) — quote verified against source text: yes

- Topic: weather and RB volume
- Source type: practitioner research with disclosed sample
- Date: 2026-09-22
- Site: not stated
- Format: not stated
- Sample size: 3,416 lead-back games
- Time period: not stated
- Outcome definition: not stated
- Method / formula: not stated
- Features / data: not stated
- Result / effect size: not stated
- Limitations: not stated
- Conflicting evidence: none found
- Code / data availability: not stated
- Reproducibility: not stated
- Layer affected: football (environment)
- Claim tag: EMPIRICAL_HISTORICAL_EVIDENCE
- Allowed use: evidence
- Test on our data: Replicate.
- Falsification: Replication fails.
- Implementation candidate: none (evidence only)


#### OL-01: pressure rate and QB injury

**Claim.** QBs in the most-pressured group were twice as likely to miss the next game (p=0.051); mean pressure rate difference (23.9% vs 21.3%) was not significant.

> "We also see, using a Fisher’s exact test, the difference is statistically significant at the 90% level (p = 0.051). In other words, those who are pressured most often are twice as likely to miss the next game compared with other QBs who face little pressure."  
> [Edward Egros Substack: The True Importance of Pass Protection](https://edwithsports.substack.com/p/the-true-importance-of-pass-protection) — quote verified against source text: yes

- Topic: pressure rate and QB injury
- Source type: practitioner
- Date: 2026-09-19
- Site: not stated
- Format: not stated
- Sample size: not stated
- Time period: 2020-2025
- Outcome definition: not stated
- Method / formula: not stated
- Features / data: not stated
- Result / effect size: not stated
- Limitations: Weak significance; not an OL-injury study.
- Conflicting evidence: none found
- Code / data availability: not stated
- Reproducibility: not stated
- Layer affected: football (participation)
- Claim tag: EMPIRICAL_HISTORICAL_EVIDENCE
- Allowed use: evidence (weak)
- Test on our data: Pressure rate as a feature in QB next-game availability hazard.
- Falsification: No out-of-sample lift.
- Implementation candidate: none (evidence only)


#### K-01: FG make probability

**Claim.** Yale Sports Analytics logistic model on 2009-2017 FGs: only distance and season were significant (distance coef -0.1024).

> "I fit a regression model over all field goals attempted to look at which variables were statistically significant."  
> [Yale Undergraduate Sports Analytics: NFL Kicker Evaluation](https://sports.sites.yale.edu/nfl-kicker-evaluation) — quote verified against source text: yes

- Topic: FG make probability
- Source type: practitioner (student)
- Date: 2019-02-18
- Site: not stated
- Format: not stated
- Sample size: 8,924 attempts
- Time period: not stated
- Outcome definition: not stated
- Method / formula: not stated
- Features / data: not stated
- Result / effect size: not stated
- Limitations: No weather/altitude; old era.
- Conflicting evidence: none found
- Code / data availability: not stated
- Reproducibility: not stated
- Layer affected: football (kicker)
- Claim tag: EMPIRICAL_HISTORICAL_EVIDENCE
- Allowed use: evidence
- Test on our data: Kicker submodel: drive-end-state x FG attempt decision x make prob (distance, wind, dome).
- Falsification: n/a
- Implementation candidate: none (evidence only)


#### COACH-01: coordinator change and team tendencies

**Claim.** ETR notes 21 NFL teams had a new offensive coordinator in 2025, making prior-season pass-rate/PROE less useful; play volume and pass rate are the two key team-volume variables.

> "The two key variables for projecting team-level volume output are play volume and pass rate. ETR pace guru Pat Thorman is the best in the business at forecasting pace (and his team-level pace previews will be a must-read), but that’s only one side of the coin. Pass rate is also critical, and simply looking at seasonal pass rate or even seasonal Pass Rate Over Expectation lacks the key context of how teams evolve throughout the season."  
> [ETR: Team Play-Calling Trends From the 2025 Season](https://establishtherun.com/team-play-calling-trends-from-the-season/) — quote verified against source text: yes

- Topic: coordinator change and team tendencies
- Source type: practitioner
- Date: 2026-04-19
- Site: not stated
- Format: not stated
- Sample size: not stated
- Time period: not stated
- Outcome definition: not stated
- Method / formula: not stated
- Features / data: not stated
- Result / effect size: not stated
- Limitations: not stated
- Conflicting evidence: none found
- Code / data availability: not stated
- Reproducibility: not stated
- Layer affected: football (team volume)
- Claim tag: EXPERT_OPINION
- Allowed use: evidence
- Test on our data: Play-caller identity as a hierarchical grouping for PROE/pace priors.
- Falsification: Play-caller grouping adds no out-of-sample lift.
- Implementation candidate: none (evidence only)


#### CAL-01: calibration and sharpness

**Claim.** Gneiting, Balabdaoui & Raftery (2007): maximize sharpness subject to calibration; uniform PIT is necessary but not sufficient; CRPS is a proper score generalizing absolute error.

> "Hence, the uniformity of the PIT is a necessary condition for the forecaster to be ideal, and checks for its uniformity have formed a corner-stone of forecast evaluation."  
> [Gneiting et al., JRSS-B 2007](https://sites.stat.washington.edu/raftery/Research/PDF/Gneiting2007jrssb.pdf) — quote verified against source text: yes

- Topic: calibration and sharpness
- Source type: peer-reviewed paper
- Date: not stated
- Site: not stated
- Format: not stated
- Sample size: not stated
- Time period: not stated
- Outcome definition: not stated
- Method / formula: not stated
- Features / data: not stated
- Result / effect size: not stated
- Limitations: not stated
- Conflicting evidence: none found
- Code / data availability: not stated
- Reproducibility: not stated
- Layer affected: evaluation
- Claim tag: PRODUCTION_CANDIDATE
- Allowed use: evidence (evaluation standard)
- Test on our data: CRPS + PIT histograms + interval coverage for every player stat distribution and DK points.
- Falsification: n/a
- Implementation candidate: Evaluation suite: CRPS, log score, PIT, coverage at 50/80/95, marginal calibration.


#### MKT-01: structural model vs closing price

**Claim.** A 2026 preprint reports a structural model better calibrated than the market on home-win margin (slopes 0.995 vs 1.103) while less sharp.

> "The structural model is better calibrated than the market on the home-win margin (slope 0.995 versus 1.103) while clearly less sharp: the market's advantage is discrimination rather than honesty, which accuracy alone cannot distinguish."  
> [alphaXiv 2608.11505: Does a Structural Model Add Anything to the Closing Price?](https://www.alphaxiv.org/abs/2608.11505) — quote verified against source text: yes

- Topic: structural model vs closing price
- Source type: paper (preprint)
- Date: 2026-08-11
- Site: not stated
- Format: not stated
- Sample size: 7,220
- Time period: not stated
- Outcome definition: not stated
- Method / formula: not stated
- Features / data: not stated
- Result / effect size: not stated
- Limitations: Preprint; sport/league not captured in extraction.
- Conflicting evidence: none found
- Code / data availability: not stated
- Reproducibility: not stated
- Layer affected: evaluation (diagnostic)
- Claim tag: EMPIRICAL_HISTORICAL_EVIDENCE
- Allowed use: diagnostic only (markets never enter the football forecast)
- Test on our data: Post-hoc calibration-slope comparison vs closing lines, diagnostic only.
- Falsification: n/a
- Implementation candidate: none (evidence only)


### P3 records


#### LS-01: late swap mechanics

**Claim.** SaberSim late swap locks started players, draws new sims for unstarted players, and fills the best players into eligible positions with remaining salary.

> "Uh the only difference is is that we are locking in the players who have already started, grabbing new Sims for the players and games that haven't started, and then filling in the best players based on the sim results into the eligible positions while using what is left of your salary cap."  
> [DFS Q&A: Should You Adjust Minimum Salary for Classic and Showdown Slates? (SaberSim DFS - Daily Fantasy Sports Strategy)](https://www.youtube.com/watch?v=wpV5KCr2lAg&t=1716s) — quote verified against source text: yes

- Topic: late swap mechanics
- Source type: YouTube
- Date: 2025-11-20
- YouTube timestamp: 28:36 (1716s)
- Site: not stated
- Format: not stated
- Sample size: not stated
- Time period: not stated
- Outcome definition: not stated
- Method / formula: not stated
- Features / data: not stated
- Result / effect size: not stated
- Limitations: not stated
- Conflicting evidence: none found
- Code / data availability: not stated
- Reproducibility: not stated
- Layer affected: late swap
- Claim tag: EXTERNAL_MODEL_OUTPUT
- Allowed use: evidence (not applicable to single-game Showdown, where all players lock together)
- Test on our data: n/a for Showdown
- Falsification: n/a
- Implementation candidate: none (evidence only)


#### LS-02: Showdown backtesting has no live-data leakage

**Claim.** SaberSim: in Showdown all players lock at once, so backtests are not at risk of using live data.

> "combine that with the games that have not happened. Right? So since all of the players lock at the same time for showdown, there are you are not at risk of ever using the live data and getting skewed results. Okay, I just wanted to be very clear about that. So there's nothing special you need to do in terms of like avoiding the live data or anything like that."  
> [DFS Q&A: How Can You Backtest Slates You Didn’t Play? (SaberSim DFS - Daily Fantasy Sports Strategy)](https://www.youtube.com/watch?v=wMa_RECsegY&t=274s) — quote verified against source text: yes

- Topic: Showdown backtesting has no live-data leakage
- Source type: YouTube
- Date: 2026-03-20
- YouTube timestamp: 4:34 (274s)
- Site: not stated
- Format: Showdown
- Sample size: not stated
- Time period: not stated
- Outcome definition: not stated
- Method / formula: not stated
- Features / data: not stated
- Result / effect size: not stated
- Limitations: not stated
- Conflicting evidence: none found
- Code / data availability: not stated
- Reproducibility: not stated
- Layer affected: evaluation
- Claim tag: EXPERT_OPINION
- Allowed use: evidence
- Test on our data: n/a
- Falsification: n/a
- Implementation candidate: none (evidence only)


#### PAY-01: payout-threshold stochastic IP

**Claim.** A K-State thesis models DK NFL Milly payouts with independent normal player points and payout-point thresholds (avg 158.29 pts to cash, 253.76 for the top prize, 2016-17).

> "The tiered estimated point thresholds are the average of points needed to win the lowest payout available and the million dollar prize for each week of the 2016-2017 NFL season on DraftKings®."  
> [K-State thesis: Optimizing DFS contests through stochastic integer programming](https://krex.k-state.edu/server/api/core/bitstreams/1d781389-90fe-4e9d-931a-507ea81031fc/content) — quote verified against source text: yes

- Topic: payout-threshold stochastic IP
- Source type: paper (thesis)
- Date: not stated
- Site: DraftKings
- Format: Classic
- Sample size: not stated
- Time period: 2016-17 weeks 6-17
- Outcome definition: not stated
- Method / formula: not stated
- Features / data: not stated
- Result / effect size: not stated
- Limitations: Independence assumption; no opponents.
- Conflicting evidence: none found
- Code / data availability: not stated
- Reproducibility: not stated
- Layer affected: portfolio / payout
- Claim tag: EMPIRICAL_HISTORICAL_EVIDENCE
- Allowed use: evidence
- Test on our data: n/a
- Falsification: n/a
- Implementation candidate: none (evidence only)


#### OPT-01: projection->optimizer baseline performance

**Claim.** A neural-net projection + MILP optimal lineup (2018 NFL) landed around the 31st percentile (median) versus real DK user lineups.

> "The generated lineups were then compared to real-world lineups from users on DraftKings. The generated lineups generally fell in approximately the 31st percentile (median)."  
> [arXiv 2309.15253: Method and Validation for Optimal Lineup Creation for DFS](https://arxiv.org/abs/2309.15253) — quote verified against source text: yes

- Topic: projection->optimizer baseline performance
- Source type: paper (preprint)
- Date: 2023-09-26
- Site: DraftKings
- Format: Classic
- Sample size: not stated
- Time period: not stated
- Outcome definition: not stated
- Method / formula: not stated
- Features / data: not stated
- Result / effect size: not stated
- Limitations: not stated
- Conflicting evidence: none found
- Code / data availability: not stated
- Reproducibility: not stated
- Layer affected: portfolio / evaluation
- Claim tag: EMPIRICAL_HISTORICAL_EVIDENCE
- Allowed use: evidence (the 'projection -> optimizer' architecture underperforms)
- Test on our data: n/a
- Falsification: n/a
- Implementation candidate: none (evidence only)

## Appendix B. New YouTube videos used this cycle

| Video | Channel | Date | Verified quotes used |
|---|---|---|---|
| [DFS Q&A: How is adjusted ownership calculated?](https://www.youtube.com/watch?v=LBFruLksiSU) | SaberSim DFS - Daily Fantasy Sports Strategy | not stated | 0 in ledger / 4 verified |
| [DFS Q&A: Does Late Swap Use Live Ownership?](https://www.youtube.com/watch?v=Qymh4oizKdM) | SaberSim DFS - Daily Fantasy Sports Strategy | 2026-02-28 | 1 in ledger / 8 verified |
| [DFS Q&A: How Can You Reduce Dupes in NFL Showdown?](https://www.youtube.com/watch?v=r44AIMlrnmk) | SaberSim DFS - Daily Fantasy Sports Strategy | 2025-11-25 | 1 in ledger / 6 verified |
| [DFS Q&A: Preventing Duplication in NFL Showdown](https://www.youtube.com/watch?v=VC2Sx7DGMFE) | SaberSim DFS - Daily Fantasy Sports Strategy | 2023-10-17 | 2 in ledger / 9 verified |
| [DFS Q&A: Should You Adjust Minimum Salary for Classic and Showdown Slates?](https://www.youtube.com/watch?v=wpV5KCr2lAg) | SaberSim DFS - Daily Fantasy Sports Strategy | 2025-11-20 | 3 in ledger / 8 verified |
| [DFS Q&A: How do you recommend filtering out lineups for NFL Showdown?](https://www.youtube.com/watch?v=hTUUH0mfpfU) | SaberSim DFS - Daily Fantasy Sports Strategy | 2025-01-15 | 3 in ledger / 9 verified |
| [DFS Q&A: What are the optimal filters for NFL Showdown?](https://www.youtube.com/watch?v=hFDu4Yx4VrY) | SaberSim DFS - Daily Fantasy Sports Strategy | 2024-09-07 | 2 in ledger / 9 verified |
| [A Data Driven Look at How to Win NFL Showdown Contests on Fanduel and Draftkings](https://www.youtube.com/watch?v=ofyXOG5XlbA) | DFS Army - Daily Fantasy Sports  | 2020-09-07 | 2 in ledger / 10 verified |
| [DFS Q&A: How Can You Backtest Slates You Didn’t Play?](https://www.youtube.com/watch?v=wMa_RECsegY) | SaberSim DFS - Daily Fantasy Sports Strategy | 2026-03-20 | 1 in ledger / 4 verified |
| [DFS Q&A: Which is better, running a contest sim against the field lineups or your own lineups?](https://www.youtube.com/watch?v=FbQSwk4Kfmg) | SaberSim DFS - Daily Fantasy Sports Strategy | 2024-08-10 | 1 in ledger / 11 verified |
| [DFS Q&A: Understanding Sim ROI Results](https://www.youtube.com/watch?v=d883hjQvUCc) | SaberSim DFS - Daily Fantasy Sports Strategy | 2025-12-25 | 2 in ledger / 8 verified |
| [DFS Lineup Optimizers Are Obsolete. You Need a Simulator.](https://www.youtube.com/watch?v=07ukRKU0LoI) | SaberSim DFS - Daily Fantasy Sports Strategy | 2021-09-07 | 2 in ledger / 5 verified |
| [AceMind Catch up-----NFL showdown and other best practices using their sims.](https://www.youtube.com/watch?v=yle0xQ2cuq8) | TrueDFS | 2024-12-05 | 3 in ledger / 7 verified |

Verification method: full transcripts were pulled with timestamp markers. Candidate quotes were compared after lowercasing and stripping punctuation, and kept only if the full quote appeared contiguously in the transcript. Timestamps were recomputed from the transcript's own markers.