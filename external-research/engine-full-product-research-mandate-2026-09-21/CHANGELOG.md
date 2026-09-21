# Change log: revision 2 of the full product research packet, responding to the external review

Date: 2026-09-21. Scope: `external-research/engine-full-product-research-mandate-2026-09-21/`. Status of the engine after this revision: unchanged. CANDIDATE_NOT_ACCEPTED_BASELINE / V2 NOT YET EARNED. Nothing in this revision promotes the model, evaluates a gate, or changes the eight-rule promotion standard. Research completion does not constitute model acceptance, promotion or production readiness.

## Repository verification requested by the reviewer

The reviewer stated that the claimed repository save and the prior reports were not verified. Verification from the project file checkout, read-only git:

| Item | Evidence |
|---|---|
| Revision 1 of this packet | commit `57b2077` "Full product deep research mandate packet (Parts I to L): component specs, source registry, schemas, validation protocol, gate matrix, backlog, gap register, combined mandate" |
| Engine rebuild research packet referenced throughout | commit `3216ff8`, path `external-research/engine-rebuild-research-packet-2026-09-21/nfl-engine-rebuild-research-packet.pplx.md`, sections 1 to 23 present (section 5 game simulation architecture comparison, section 9 probability calibration, section 14 data-source matrix verified 2026-09-21T04:05Z) |
| DFS construction report referenced by Blocks XXIX and XXXI | commit `dea047e` dated 2026-09-18 22:05:33 UTC, path `external-research/nfl-fullslate-dfs-construction-2026-09-18/nfl-fullslate-dfs-lineup-construction.pplx.md`, Parts 1 to 25 plus Sections I to III present |
| Revision 2 (this change) | commit `0b63561` |

## Files in this revision

| File | Change |
|---|---|
| `nfl-full-product-research-packet.pplx.md` | revised in place (findings 1 to 11 below) |
| `source_registry.csv` | 31 to 33 rows; two Open-Meteo rows added; paid-source wording corrected (finding 10) |
| `implementation_backlog.csv` | 30 to 34 tasks; T-31 to T-34 added |
| `gate_matrix.csv` | new: 60 gates with block, component, class, statistic, baseline, evaluation unit, dependence handling, pass rule, reason code |
| `scope_gate_dependencies.csv` | new: 27 scopes with dependency scopes, required gates, blocking and non-blocking reason codes, market comparison gate |
| `verdict_engine.py` | new: executable verdict precedence over the two CSVs |
| `test_verdict_engine.py` | new: 9 tests, all passing on the shipped CSVs (no real gate results exist yet; the tests use synthetic gate statuses) |
| `mandate_combined.md` | unchanged; the continuation piece remains RECONSTRUCTED (gap E-16) |
| `CHANGELOG.md` | this file |

## Per-finding record

### Finding 1: active-status inference

Reviewer: Block I introduced PRESUMED_ACTIVE_PENDING_GAMEBOOK, which infers a status from absence.

Position: agreed; the state violated the mandate rule that active must never be silently inferred from absence from an inactive list.

Correction: Block I now defines exactly three authoritative pre-kickoff game-day values, INACTIVE_LISTED, ACTIVE_LISTED and GAMEDAY_STATUS_UNKNOWN, with the sub-flag `absent_from_inactives_capture` recorded separately. Any estimated P(active) exists only in the Block XIV availability output and is never written into `player_state_at_cut`; the schema example in Section 3.2 was changed accordingly and the reason code GAMEDAY_STATUS_UNKNOWN:<player_id> was added to the typed namespace.

Evidence: mandate Part on chronology ("Never silently infer ACTIVE from absence from an inactive list") in `mandate_combined.md`; REPO Week 2 inactives captures in `external-research/` show that Tier 1 captures are per club and arrive at different times, which is why an unknown state must exist.

Affected files: packet Block I, Section 3.2, Section 4.3; `gate_matrix.csv` (G-I-1 to G-I-3); `scope_gate_dependencies.csv` (GAMEDAY_STATUS_UNKNOWN blocking for F scopes, display-only for N2).

Unresolved: whether a club's published active list (as opposed to the inactive list) is reliably captured for all 32 clubs at the same time; until measured, ACTIVE_LISTED before kickoff will be rare and most players will carry GAMEDAY_STATUS_UNKNOWN until the gamebook.

### Finding 2: contradictory calibration recommendations

Reviewer: Section 1.2 said event-probability calibration with raw distributions untouched; Block XIX said recalibrate distributions first; independently transforming marginals does not guarantee coherent worlds.

Position: agreed on both counts. The two statements were inconsistent, and neither design preserved accounting or joint probabilities.

Correction: a single design, PROPOSAL, replaces both: worlds are never altered; one non-negative weight vector per release is fit by raking (iterative proportional fitting) so weighted marginals meet family calibration targets estimated forward-chain, with a weight-ratio cap and an effective-sample-size floor; every consumer (props, SGP, DFS, ownership inputs) reads the same weighted worlds, so accounting identities hold by construction and joint probabilities share the weights. Post-hoc event calibration (isotonic or beta) is a diagnostic only and is never applied to exposed outputs. New reason code CALIBRATION_INFEASIBLE:<family>. Schemas 3.5 and 3.6 gained `param_draw_id`, `scenario_draw_id` and `world_weight` columns; the manifest gained `world_weights_sha256`.

Evidence: [Gneiting 2007](https://sites.stat.washington.edu/raftery/Research/PDF/Gneiting2007jrssb.pdf) for calibration and sharpness; [Kull et al](https://proceedings.mlr.press/v54/kull17a.html) for beta calibration as diagnostic; [Wei and Held 2014](https://www.zora.uzh.ch/id/eprint/102586/1/4-WeiHeld-cailibration2014.pdf) for the discrete PIT bins used as raking targets. No NFL-specific source in context validates world reweighting; it is labeled PROPOSAL and gated (G-XIX-1 to G-XIX-4).

Affected files: packet Section 1.2, Blocks XVIII, XIX, XLV, Sections 3.4 to 3.6; `implementation_backlog.csv` T-32; `gate_matrix.csv`.

Unresolved: raking with many families and few worlds can collapse the effective sample size; the interaction between the weight-ratio cap and calibration attainment must be measured, and if it fails routinely the only coherent alternative is to recalibrate upstream component parameters and re-simulate, which is slower.

### Finding 3: chronology example invalid

Reviewer: the Section 3.4 manifest example showed a September 20 cut with an asset retrieved September 21 and no publication timestamp.

Position: agreed; the example contradicted G-XVII-1.

Correction: manifest schema 1.1.0 adds `release_kind` (LIVE or RECONSTRUCTION), `admissibility` (PROVEN or UNPROVEN) and per-input `availability_proof` (RETRIEVED_BEFORE_CUT, PUBLISHED_BEFORE_CUT_EXACT, UNPROVEN). LIVE requires every input retrieved at or before the cut. RECONSTRUCTION requires proof that the exact version was available at the cut. UNPROVEN releases are analyzable but never count toward prospective evidence or DEPLOYABLE (reason code RELEASE_UNPROVEN, implemented in `verdict_engine.py` and tested). The example dates were corrected.

Evidence: nflverse release assets (registry rows) expose update times at the asset level only, which is why a separate proof field is needed; REPO inactives capture reports in `external-research/` record retrieval times per capture.

Affected files: packet Sections 3.4, 4.1, 4.3; `scope_gate_dependencies.csv`; `verdict_engine.py`.

Unresolved: for nflverse parquet assets, a self-archived vintage is the only proof available for past cuts, so most historical releases before the self-archive starts will be RECONSTRUCTION with UNPROVEN inputs unless the asset's `dt` columns are accepted as publication proxies; that acceptance is an owner decision.

### Finding 4: verdict drift

Reviewer: 4.3 required passing gates to earn RESEARCH_ONLY; Section 5 introduced UNSUPPORTED as a football verdict.

Position: agreed.

Correction: exactly three verdicts. RESEARCH_ONLY is the default whenever analyzable output exists and any required gate is not PASS, or a blocking reason code applies; it is not earned. UNSUPPORTED remains only as an evidence-status label in Section 1 and as typed reason codes (namespace listed in 4.3). NO_SUPPORTED_EDGE is confined to betting and DFS scopes with all gates passing and a market or payout interval including zero. Non-betting scopes cannot be NO_SUPPORTED_EDGE (asserted in tests). Verdicts are computed by `verdict_engine.py` from `gate_result` records and reason codes; prose cannot override them.

Evidence: mandate verdict rule ("three machine verdicts only; no prose may override") in `mandate_combined.md`.

Affected files: packet Sections 1 legend, 4.3, 5; `gate_matrix.csv`; `scope_gate_dependencies.csv`; `verdict_engine.py`; `test_verdict_engine.py`.

Unresolved: none on logic. Open on data: no gate has real results yet, so every scope's current verdict is RESEARCH_ONLY with GATE_NOT_EVALUATED codes, which the default test asserts.

### Finding 5: simulation specification unresolved

Reviewer: the engine labeled drive-level samples plays; specify the state-transition algorithm.

Position: agreed; the label was wrong and the algorithm was absent.

Correction: Block X now specifies a play-level state-transition engine with a reduced play-outcome model (Option C-reduced): the state vector, per-world context draws, pseudocode for play call, dropback branch (sack, scramble, target, air yards, completion, YAC, interception), rush branch, fumbles, field position and scoring resolution, PAT decision, clock elapsed and tick, kneel-down policy, overtime module, and the accounting identities that hold by construction. Component distribution families and the situational requirements of mandate Part X are mapped to algorithm steps. The drive-level Markov engine is retained as a benchmarked fallback (G-X-4). Section 1.2, Block XXXIV and the Part XLIX disagreement record were updated to match.

Evidence: [Goldner](https://supermariogiacomazzo.github.io/STOR538_WEBSITE/Articles/Football/Football_Goldner.pdf) for the absorbing Markov drive baseline; [NFLSimulatoR](https://github.com/rtelmore/NFLSimulatoR) as an open-source play-level precedent on nflfastR data; [SportsLine](https://www.sportsline.com/insiders/how-do-we-produce-player-projections/) as a public statement that roster-based Monte Carlo game simulation is a production practice elsewhere (no method details implied). REPO `external-research/system-review-2026-09-14/NFL_FORECASTING_SYSTEM_ADVERSARIAL_REVIEW.md` section B4 (dropback chain: sack, scramble, attempt; scrambles never allocated twice).

Affected files: packet Section 1.2, Blocks X, XXXIV, XLV, Section 8 disagreements; `gate_matrix.csv` G-X-1 to G-X-4.

Unresolved: the reduced outcome model's component families are proposals until G-X-2 is evaluated; per-play compute cost (about 10^8 plays per full slate at 10^5 worlds per game) is an estimate, not a measurement.

### Finding 6: DST points allowed wrong

Reviewer: DraftKings excludes points surrendered by the offense from DST points allowed; compute from attributed scoring events; verify in the rules JSON.

Position: agreed; verified. The JSON scoring notes state that Points Allowed only includes points surrendered while the DST is on the field and does not include points given up by the team's offense (for example points off offensive turnovers), enumerate the plays that count, and award a fumble recovery to the DST when the team's offense recovers a fumble by the opposing defense after an offensive turnover ([DraftKings RulesAndScoring.json](https://api.draftkings.com/rules-and-scoring/RulesAndScoring.json)).

Correction: Block XXII defines PA_T as a functional over attributed scoring events with the DK enumerated set and unit tags; the engine's event log must tag scoring_unit and conceding_unit_on_field; schema 3.6 replaces `points_allowed (from opponent row)` with `dst_points_allowed_dk` plus `opponent_points_total` and adds a `world_scoring_events` table; G-XXII-3 and a stricter G-XXIV-1 (exact reconciliation) were added; backlog T-33.

Affected files: packet Blocks XXII, XXIV, XLV, Section 3.6; `gate_matrix.csv`; `implementation_backlog.csv`.

Unresolved: the JSON was retrieved on 2026-09-21; DK may change rule text without notice, hence the rules hash in the manifest. FanDuel's equivalent rule was not inspected in this session and is UNKNOWN.

### Finding 7: placeholders (portfolio, Classic, competitors)

Reviewer: Block XXIX lacked formulas, Block XXXI said "As REPO", nine competitors were not inspected.

Position: agreed.

Correction: Block XXIX now states objectives per contest type (top-heavy: probability at least one entry reaches the top tier via greedy submodular construction with pairwise lineup correlation; double-up: weighted probability of clearing the simulated cash line; risk: expected payout minus lambda times CVaR with owner-set parameters; bankroll fraction downstream only), inputs, outputs, benchmark and gates. Block XXXI now carries the exact versioned dependency (path plus commit `dea047e`, Parts 1 to 6, 9, 16, 20, 21, 23) and the DK Classic rules from the JSON (roster, two-game minimum, $50,000 cap, lock at game start, pool adjustment up to 48 hours before lock, Non Late Swap variant). Block XLVII now covers all fifteen named products with exposed features, disclosed methodology and what remains proprietary, without ranking. Gap E-12 closed.

Evidence: [Hunter, Vielma, Zaman](https://arxiv.org/abs/1604.01455) and [Management Science](https://pubsonline.informs.org/doi/10.1287/mnsc.2019.3528) as recorded in the REPO DFS report Part 13; [DraftKings RulesAndScoring.json](https://api.draftkings.com/rules-and-scoring/RulesAndScoring.json); competitor pages: [RotoGrinders FAQ](https://rotogrinders.com/pages/rotogrinders-daily-fantasy-projections-faq-129417), [THE BLITZ](https://rotogrinders.com/the-blitz), [NumberFire](https://www.numberfire.com/info/how-it-works/), [FantasyLabs glossary](https://support.fantasylabs.com/hc/en-us/articles/214870428-Glossary-of-Terms-NFL), [Stokastic](https://www.stokastic.com/nfl), [Fantasy Points DFS](https://www.fantasypoints.com/nfl/projections/dfs), [SportsLine](https://www.sportsline.com/insiders/how-do-we-produce-player-projections/), [Action Network](https://www.actionnetwork.com/nfl/prop-projections), [Props.Cash](https://props.cash/), [BettingPros](https://www.bettingpros.com/nfl/props/).

Affected files: packet Blocks XXIX, XXX, XXXI, XLVII, Section 7 (E-12).

Unresolved: most products disclose no methodology; the RotoGrinders FAQ is dated 2015 and may not describe current practice; the SportsLine betting-line adjustment is recorded because it conflicts with this project's rule, not as a finding about its accuracy.

### Finding 8: gate matrix abbreviated

Reviewer: deliver an exhaustive machine-readable dependency map with gate ids and executable verdict precedence.

Position: agreed.

Correction: `gate_matrix.csv` (60 gates), `scope_gate_dependencies.csv` (27 scopes: F1 to F5, P1 times 13 families, P2, D1 to D5, N1 to N3), `verdict_engine.py` and `test_verdict_engine.py`. The tests assert: every referenced gate exists; no scope gate is orphaned (COMPONENT_INCLUSION gates G-XII-1 and G-XIII-1 are exempt because they decide whether an optional component enters a release, not whether a scope is deployable); everything unevaluated is RESEARCH_ONLY; football scopes can be DEPLOYABLE while betting scopes need a favorable market interval; an upstream exact-gate failure propagates only to dependent scopes; an identity failure on the salary axis blocks DFS scopes and is display-only for football and prop scopes (mandate Deliverable 6); RELEASE_UNPROVEN blocks every scope except the evidence viewer; non-betting scopes are never NO_SUPPORTED_EDGE.

Affected files: new files listed above; packet Section 5 rewritten to point at them.

Unresolved: statistical thresholds (levels, fractions, floors) are deliberately absent from `gate_matrix.csv` pass rules and refer to the Section 4.2 derivation procedure, per the mandate's prohibition on inventing thresholds; the CSV will need a `threshold_ref` column once those derivations exist.

### Finding 9: Open-Meteo Single Runs API not inspected

Reviewer: the Single Runs API (ECMWF IFS from March 2024, others from April 2026) was not inspected; verify publication latency.

Position: agreed; inspected in this revision.

Correction: Block XI records the Single Runs API (`run=` UTC initialisation parameter; ECMWF IFS HRES 9 km from March 2024; most other models from 2026-04-02) and the Previous Runs API (lead-time offsets 1 to 7 days; most models from January 2024; GFS 2 m temperature from March 2021), and the model-updates guidance to wait 10 minutes after an update. Publication latency per run is not stated statically on the pages inspected (the update table is rendered dynamically) and is recorded as UNKNOWN; the admissibility rule is init time plus measured latency at or before the cut, with WEATHER_PROXY until latency is measured (backlog T-31). Two registry rows added; gap E-04 rewritten; gap E-17 added for licence terms.

Evidence: [Open-Meteo Single Runs API](https://open-meteo.com/en/docs/single-runs-api), [Open-Meteo Previous Runs API](https://open-meteo.com/en/docs/previous-runs-api), [Open-Meteo model updates](https://open-meteo.com/en/docs/model-updates).

Affected files: packet Section 1.2, Block XI, Section 7; `source_registry.csv`; `implementation_backlog.csv`.

Unresolved: per-model publication latency; licence and commercial-use terms; whether archived single runs are identical to what was served live at the time (needed for RECONSTRUCTION proof).

### Finding 10: paid-source exclusion

Reviewer: the mandate requests free-versus-paid research; any restriction needs an exact governing reference.

Position: partial disagreement, with the reviewer's demand for the exact reference satisfied. The restriction is real but it is an owner instruction, not a project-wide rule, and it does not forbid researching paid sources. The governing text is the owner's message of 2026-09-14 18:51 UTC (session turn 125): "We do NOT want to depend on commercial NFL data vendors. Do not recommend purchasing Sportradar, PFF, Stats Perform, SIS, FantasyPoints Data, TruMedia, or another provider as the solution. You may study what capabilities those systems expose only to identify capability gaps we need to reproduce independently." The project instructions themselves only require preserving report terminology and not blending this thread with the separate FTN, PFF and SportsDataIO vendor-qualification thread. Revision 1 wrote "excluded by project rule" in two registry rows, which overstated the restriction and gave no reference.

Correction: registry rows for Sportradar and FTN now state "not adopted as a dependency per owner instruction of 2026-09-14 18:51 UTC (session turn 125)" with the study-only clause quoted, and remain fully documented for the free-versus-paid comparison; packet Section 0.4 was rewritten to the same effect; gap E-18 records that adopting a paid source for a specific unsupported capability (in-season routes, alignment) is an owner decision item.

Affected files: packet Section 0.4, Section 7 (E-18); `source_registry.csv`.

Unresolved: whether the owner wants the 2026-09-14 instruction to apply to this mandate unchanged, given that the mandate itself asks for paid-source research (decision item).

### Finding 11: Monte Carlo variance under nesting

Reviewer: independent-draw formulas were used although the nested design shares parameter draws.

Position: agreed.

Correction: Block XV specifies the nested design (M parameter draws, K scenario draws, N worlds per cell) and the ANOVA estimator Var(Y_bar) equals s_M^2 divided by M plus s_K^2 divided by (M K) plus s_N^2 divided by (M K N), with the conservative parameter-level alternative, guidance to grow M before N when the parameter component dominates, common random numbers for differences, and separate reporting of predictive variance components versus Monte Carlo error. Block X's draw-count procedure now references this estimator. G-XV-3 added; backlog T-34.

Evidence: standard nested ANOVA variance decomposition; no external URL is cited for a textbook identity. REPO `methodology/simulation_calibration.md` covers clustered bootstrap for evaluation and is unaffected.

Affected files: packet Blocks X, XV, XXI; `gate_matrix.csv`; `implementation_backlog.csv`.

Unresolved: the scenario level (availability and role draws) may be better treated as part of the world level when K is large and cheap; the choice changes the estimator's grouping but not its logic.

## Convention check

No em dashes, en dashes or exclamation points in any file in this folder (checked with `rg`). All URLs in the packet and this log appear in the session's evidence records.

## What this revision does not do

It does not evaluate any gate, produce any release, run the simulator, or change the engine's acceptance status. Every recommendation labeled PROPOSAL remains a proposal. The mandate is not marked complete: gaps E-01 to E-18 remain open except E-12, and the continuation piece of the mandate is still reconstructed rather than verbatim (E-16).
