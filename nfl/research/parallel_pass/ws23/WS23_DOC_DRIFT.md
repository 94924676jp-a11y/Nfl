# WS23 — declared architecture versus actual production code

**Workstream 23, parallel NFL engineering pass. Repo `/home/user/nfl` @ `57d38ad`.
Research only. CODE CHANGED: NO.**

What was compared: `CLAUDE.md`, `README.md`, `CURRENT_STATE.md`,
`NFL_DECISION_LEDGER.md`, `NFL_PRODUCT_LAYER.md`, `NFL_MKT1_MARKET_DIAGNOSTIC.md`,
`NFL_V1_*`, `nfl/NFL_G0A_CHECKLIST.md`, `nfl/NFL_FEATURE_REGISTRY.md`,
`nfl/research/PATH_C_STATE.json`, and the module docstrings of every file under
`nfl/production/`, `nfl/product/`, `nfl/prospective/`, `nfl/identity/`,
`nfl/ingest/`, `nfl/accounting/` and `nfl/capture/` — against the code in those
same files.

The repository's documentation is unusually honest at the *module* level: most
docstrings name their own defects, and several (`capture/coverage.py`,
`qb_accounting.reconcile_team`, `metrics.UNSUPPORTED`, `board._shares`) are
models of the behaviour this pass was asked to look for. The drift is
concentrated in three places: **the top-level status documents**, **the
vocabulary of the product layer's scoring dimensions**, and **declared gates
with no caller**.

---

## 1. Mismatch table, sorted by severity

### CRITICAL

| # | Layer | DOCUMENTED BEHAVIOUR | ACTUAL IMPLEMENTATION | MISMATCH |
|---|---|---|---|---|
| **C1** | Metric status vocabulary — `nfl/product/metrics.py:23` | `MODELED = 'a governed layer produced a full distribution'`. 13 of the 20 `SUPPORTED` entries carry it, including `qb/db`, `qb/pyds`, `receiving/targets`, `receiving/receptions`, `rushing/carries`. | The governance artifact that `nfl/production/nonqb/eligibility.py:1` declares **authoritative** records every one of those layers as non-production. Ran `eligibility.matrix()` 2026-09-14: `team_volume` HOLD_CHARACTERIZED, `appearance` INFORMATION_CONSTRAINED, `route_participation` INVESTIGATE, `target_allocation` **DATA_BLOCKED**, `receiving_conversion` HOLD_CHARACTERIZED, `rushing_conversion` HOLD_CHARACTERIZED, `td_red_zone` HOLD_TENTATIVE, `joint_dependence` INVESTIGATE. **All ten pipeline layers return `production_role: None` and `publication_eligible: False`.** | The word `MODELED` asserts a governance property the governance artifact denies for every metric that carries it. `daily_board.eligibility()` (`daily_board.py:238`) gates ranking on `metric_status in ('MODELED','PROVISIONAL')` — so the governance state has no path to the gate. A board reader sees the system's *top* status on a layer recorded as DATA_BLOCKED. |
| **C2** | Ingest quarantine — `README.md` "Ingest quarantine — … columns refused for forecast use", `CLAUDE.md` Layout, G0A items 6–8 | `nfl/ingest/allowlist.py` (`assert_columns_allowed`, `forecast_safe_columns`), `nfl/ingest/validate.py` (denominator-aware validation), `nfl/ingest/eligibility.require_prediction_time_eligibility` — "A component that needs gameday eligibility REFUSES until a prediction-time source exists … the debt blocks exactly what it should and nothing else." | **Zero callers outside `nfl/tests/`.** Repo-wide grep: `allowlist` appears in production only as two *comments* in `roster_status.py:6` and `:84` describing it. `ingest.validate` is imported only by `test_denominator_validation.py`. `require_prediction_time_eligibility` is called only by `test_identifier_mapping.py`. The research panel builders (`p3/build_panel_p3.py`, `p4b`, `p4c`) read source CSVs directly. | Three declared ingest gates, none wired. The debt blocks nothing. A reader of the README believes columns are refused at ingest; nothing asks. |
| **C3** | Stale-label guard — `nfl/production/nonqb/eligibility.py:12` "`assert_no_stale_labels` fails the suite if a production string ever claims ACCEPTED or PROMOTED for a subsystem the governance artifact does not." | `:161-192`. Requires a case-sensitive `\b(ACCEPTED\|PROMOTED)\b` **and** a pipeline-layer name (`targets_carries`, `appearance`, …) **on the same line**, and defaults to scanning **one file**, `run_forecast.py`. Called only from `test_nonqb_r3.py`. | Measured: ran it against `p4c_params.py` (line 1 reads *"the ACCEPTED P4C fit"* while `target_allocation` is DATA_BLOCKED), `layers.py` and `metrics.py` → **PASS on all three**. Lower-case "accepted" (`participation_prior.py:3,57,113`; `layers.py:258`; `frozen_priors.py:19`) can never match. A guard that cannot fire. |
| **C4** | `nfl/identity/` — `README.md` and `CLAUDE.md` Layout: "execution identity, forecast sealing, effective scope"; `NFL_G0A_CHECKLIST.md` credits it with items 4, 5, 11, 12 | **No module under `nfl/production/` or `nfl/product/` imports `nfl.identity`.** `run_forecast.py:88` defines its own `execution_identity()`; sealing is local plus `nfl/product/store.py`. `nfl.identity.seal` / `execution_identity` are consumed only by `nfl/prospective/q9shadow/` (the shadow path) and `nfl.identity.effective_scope` only by `capture/registry.py` and `parse/injury_report.py`. | Two sealing mechanisms and two execution-identity mechanisms under one set of names, and the one the architecture documents is **not the one on the production path**. `registry.bound_from_series`, cited by `NFL_G0A_CHECKLIST.md:94-102` as what *closes* item 4, has zero callers (see §3). |

### HIGH

| # | Layer | DOCUMENTED BEHAVIOUR | ACTUAL IMPLEMENTATION | MISMATCH |
|---|---|---|---|---|
| **H1** | `role_certainty` — `nfl/product/confidence.py:121` docstring: *"Share of his own team's opportunity, per draw."* | `_role` sums `tot.sum(0)` over the whole `{layer}__{key}` matrix, which spans **both teams**, with no team filter anywhere in the function. The result is then divided by a hardcoded `0.8` (QB) or `0.25` (skill) and clipped to 1.0. | Denominator is the game, not the team (measured elsewhere in this pass: 73.456 game vs 40.654 DAL). Worse for the name: there is **no uncertainty term at all** — `role_certainty` is a rescaled point estimate of share *magnitude*. The reason strings (`"%d%% of the game's %s"`) and `board._shares` (`board.py:245`, "share of his **game's** opportunity pool") are both **true**; the docstring at `:122` is the single false statement. |
| **H2** | `status_certainty` — `confidence.py:92` *"from the readiness contract, not from a guess"*; `READY_WITH_COMPLETE_INPUT → 1.0, 'every contract field filed'` | `board.py:209` passes `ready.get(team)` — **one readiness state per team**, identical for all ~25 players on it. `readiness.GAME_STATES` (`readiness.py:190`) are states of the **injury-report capture**: filed / incomplete / stale / chronology-failure / clock-unresolved. | A dimension named for a *player's* status carries a *team's feed-completeness*. A questionable player on a team whose injury block is fully filed scores `status_certainty = 1.0`, "every contract field filed". Note also `GAME_STATES` is a football term of art (score/time/down) used here for injury-feed status. |
| **H3** | `input_completeness` — `confidence.py:75` *"did every source this run declares arrive?"*; reason string *"N source capture(s) validated"* | `:78` — `inputs = 1.0 if len(caps) >= 5 else (0.6 if caps else 0.0)`. It counts the length of `art['source_captures']` against an undeclared literal `5`. It never compares against what the run declared, and validates nothing. | The docstring promises a declared-versus-arrived comparison; the code is a list-length threshold. "validated" in the published reason string is false. |
| **H4** | Silent constants inside the confidence module — `WEIGHTS_NOTE`: *"a fitted weighting with nothing behind it would be a silent constant"* | Undeclared literals in the same file: `5` (input threshold), `0.6`, `1.5` (width slope), `0.8` and `0.25` (role scale caps), and the whole `_status` table `1.0 / 0.85 / 0.4 / 0.4 / 0.15 / 0.0`. Only the `1.5` is flagged ("Linear, declared, not fitted"); none has a derivation. | The module states the project's no-silent-constants rule and then carries eight of them. Weights are flat *by design*; the per-dimension scales are not, and nothing says where they came from. |
| **H5** | "There is no market feed in this system" — `confidence.py:10-12`; `thresholds.py:4` *"If a market feed does not exist — and none does"*; `NFL_MKT1_MARKET_DIAGNOSTIC.md:9* "This lives in `nfl/research/mkt1/`, **never** `nfl/product/`" | `nfl/vintage/hardrock_market_snapshot.3d9b22dc39e12e54.csv.gz` exists. `nfl/product/daily_board.py` loads it, de-vigs it and computes consensus quotes; `nfl/product/market_cdf.py`, `nfl/product/market_names.py` and `nfl/product/model_health.py` (17 `market_*` fields) all live in `nfl/product/`. | **The false statement is published.** `CONF.board()` emits `'no_market_feed': 'ranking by sportsbook edge is not possible and is not attempted; no price exists in this system'` onto every board payload. |
| **H6** | `NFL_PRODUCT_LAYER.md:44` — *"`test_no_sportsbook_number_can_enter_the_product` greps **the whole product layer**"* | `nfl/tests/test_product_layer.py:82` concatenates exactly four files: `thresholds.py`, `board.py`, `render.py`, `confidence.py`. | The four market-carrying modules in `nfl/product/` are precisely the ones the scan does not cover. The test name and the doc both overstate the boundary. Also `NFL_PRODUCT_LAYER.md:1-3` "imports no model layer … **computes no projection**" — `market_cdf` and `daily_board` compute new numbers (de-vig, consensus, push atoms), they do not only read. |
| **H7** | "participation" — `layers.participation` declares spec `Stage2 ewma_hl2`; `participation_prior.py` frozen `ewma_hl2` | `participation_prior.POSITIONS` and `s2_lib.POSITIONS` are both `('WR','TE','RB')`. The QB dropback share comes from `qb3_lib` via `qb_allocation` and never reads this module — grep for `participation` in `qb_v1.py` and `qb_allocation.py` returns **nothing**. | Two mechanisms, one word. Compounded by `eligibility.LAYER_SUBSYSTEM`, which maps `'participation' → 'appearance'` (no subsystem of its own) and `'qb_layer' → None`, `'qb_allocation' → None`. **The governance check exempts exactly the two layers carrying the largest measured defects**: QB V1 multi-QB over-prediction +79.89 pass yards (n=699, `qb_v1.KNOWN_LIMITATIONS`) and the QB3 week-1 DISAGREE bias −0.4420 (`qb_allocation.qb3_configuration`). |
| **H8** | R5 "THE ALLOCATION POOL, **FILTERED TO THE ACTIVE ROSTER**" — `run_forecast.py:619` | `roster_status.py:25` states it plainly itself: *"R5 uses the PREGAME quantity, which is **roster membership**"* — pregame ACT is the 53-man roster, not the 48 who dress. QBs are exempted outright (`run_forecast.py:632-638`). **New:** `EXCLUDED = {DEV, RES, CUT, EXE}` — `RET` is **not** in it, and the raw capture carries **23 `RET` rows**, so a *retired* player survives `active_pool()` under `kept_unrecognised_status`; `status is None` is also kept by design (`:229-234`). | "ACTIVE ROSTER" in the production comment promises gameday-active. The module's own docstring corrects it; the entrypoint comment does not. The kept-on-unknown rule is deliberate and defensible — the *name* above it is what overstates. |

### MEDIUM

| # | Layer | DOCUMENTED BEHAVIOUR | ACTUAL IMPLEMENTATION | MISMATCH |
|---|---|---|---|---|
| **M1** | `model_health.assert_ranking_admissible:136` — *"THE GATE. This is the rule the product exists to enforce."* | Zero callers repo-wide (AST scan + grep, .py and .md). | The gate is computed and enforces nothing. *Independently found by WS16 and WS14; confirmed here.* |
| **M2** | `nfl/research/PATH_C_STATE.json` — declared **authoritative** by `production/nonqb/eligibility.py:1` | `registered_utc 2026-09-08T00:45:00Z`, file mtime 2026-09-08. Carries 12 subsystems and no entry for QB V1, QB3, SC1, R5–R8, or Q6/Q7/Q8/Q9/Q9B — all adjudicated since, per `NFL_DECISION_LEDGER.md`. `gates` still read `{"G0A": "11/12", "NFL_1": "NOT AUTHORIZED"}`. | The authority is six days behind the code that cites it. `NFL_V1_RESEARCH_LEDGER.md:103` flagged it as "~5 days behind" on 2026-09-09 and it has not moved. |
| **M3** | `qb_accounting.reconcile_team` | Returns `Outcome.ok('QB_TEAM_ACCOUNTING_**MEASURED**')` even when `per_team_dropback_closure.status == 'NOT_MEASURED'`. | Minor, and the *only* naming lapse in an otherwise exemplary function — the payload itself says *"This is not evidence that it holds."* Listed for completeness, not as a defect worth a change. |

---

## 2. Overloaded-vocabulary findings

Every word on the hunt list, checked against its uses in `nfl/production/`,
`nfl/product/`, `nfl/prospective/`, `nfl/identity/`, `nfl/ingest/`,
`nfl/accounting/`.

| Word | Where | Does the name promise more than the code delivers? | Would a board/artifact reader be misled? |
|---|---|---|---|
| **certainty** | `confidence.DIMENSIONS` — `role_certainty`, `status_certainty` | **YES, both.** Neither carries an uncertainty term. `role_certainty` is a rescaled point share; `status_certainty` is a team-level feed-completeness lookup. | **YES.** Both are published per-player in `row['confidence']['parts']`. |
| **confidence** | `nfl/product/confidence.py` | **No.** The docstring leads with "HIGH CONFIDENCE DOES NOT MEAN THE OUTCOME IS LIKELY" and every payload carries `'means': 'confidence in the model and its inputs, NOT in the outcome'`. Best-defended name in the repo. | No. |
| **participation** | `layers.participation`, `participation_prior`, `inputs.PARTICIPATION_CONTRACT` | **YES** — one word, two mechanisms; QB never reads it (H7). Partly mitigated: `KNOWN_LIMITATION` correctly says pass-snaps is an *upper bound* on routes run, and the warning travels on the Outcome. | Partly — the artifact declares one spec for a stage that does not govern the QB half. |
| **calibration** | `model_health.WARNINGS`, `metrics` caveat "CALIBRATION_DEFECT" | **No.** Used as a named, sourced condition on measured evidence; `WARNINGS` explicitly says "A HEALTH WARNING IS NOT A SCORE." | No — but see M1: nothing consumes it. |
| **eligibility** | `ingest/eligibility.py`, `nonqb/eligibility.py`, `daily_board.eligibility`, `run_forecast._eligibility`, `prospective/registries.eligibility` | **YES — five unrelated meanings.** (1) prediction-time gameday availability debt (uncalled, C2); (2) governance production-role per layer; (3) ranking admissibility of a board row; (4) an artifact verdict string; (5) a feature-registry status. | **YES.** `eligibility_verdict: 'PASS'` on a sealed artifact means *sense 4* (completeness of player coverage) and nothing about senses 1–3. |
| **game state** | `readiness.GAME_STATES` | **YES.** In football this names score/time/down; here it names the state of a team's injury-report capture. Track 1 ("game-state-conditioned offense") was REJECTed and no game-state model exists in production — grep confirms. | Yes, for anyone arriving from the football literature. |
| **available / active** | `roster_status.ACTIVE`, `inactives.ROSTER_ACTIVE` / `GAME_ACTIVE`, `metrics.UNAVAILABLE` | **Mixed.** `inactives.py:74-76` is exemplary: three distinct names for three distinct things, with the rule "ACT may never become GAME_ACTIVE" written into `allowlist.py:127`. `metrics.UNAVAILABLE` is exemplary. The lapse is the single word "ACTIVE ROSTER" in the R5 comment (H8) and `RET` surviving the filter. | Only at H8. |
| **ready** | `readiness.GAME_STATES` `READY` / `READY_WITH_COMPLETE_INPUT` | **YES.** "Ready" = the injury feed filed its contract fields, not that the team or the forecast is ready. Feeds `status_certainty` (H2). | Yes. |
| **complete** | `run_forecast._completeness`, `q9shadow/complete.py`, `inactives.COMPLETE` | **No.** `research/completeness.LAYERS` exists precisely because "a twelve-game slate once reported 'complete' while carrying only the quarterback layer", and `complete.py` refuses to relabel a partial artifact. Correction is visible in the code. | No. |
| **validated** | `confidence.py:77` reason string "N source capture(s) validated" | **YES.** Nothing is validated; the list length is counted (H3). | Yes — it is a published reason string. |
| **verified** | `derived.DERIVED_ARTIFACTS_VERIFIED`, `draws_artifact.DRAW_ARTIFACT_VERIFIED` | **No.** Both are sha256 checks against a pinned hash and say so. `qb_accounting` even emits `QB_COMPOSITION_RATE_FIDELITY_UNVERIFIED` when it cannot check. | No. |
| **proven** | `NFL_G0A_CHECKLIST.md` "Item 5 — proven, not yet exercised by a production run"; commit `24966f4` "qb/pyds proven end to end" | **YES, stale rather than false.** The checklist's reason ("nothing has consumed it end to end because NFL-1 has not executed") no longer holds — production runs have executed and sealed. | Yes, for anyone reading the gate status. |
| **closure** | `qb_accounting` `per_team_dropback_closure`, `rushing_a1.closure_exact`, `NFL_V1_PRODUCT_PATH_CLOSURE.md` | **No** in code — closure is integer-exact by construction and `NOT_MEASURED` is reported as not-evidence. The document title "CLOSURE" is a verdict about engineering readiness, and it says so in its first line. | No. |
| **reconciled** | `accounting/invariants.py`, `joint.py` | **No.** The docstring's whole argument is that a reconciliation which clips is worse than none, and residuals are returned. But `reconcile_team_player` itself has zero callers (§3). | No — though the module is less live than it reads. |
| **frozen** | `frozen_priors.py`, `p4c_params` "FROZEN", `SPEC_VERSION` `*-frozen-1` | **No.** `participation_prior._ewma` actively asserts against `s2_lib.HALFLIVES` drift and refuses; `p4c_params` hash-verifies its regenerated artifacts. Genuinely frozen. | No. |
| **deterministic** | `draws_artifact`, `rushing_a1:186`, `depth_vintage:83` | **No.** Each names the mechanism (sha256 over a seed contract, sorted tie-break). `layers.targets_carries` even records the repair of `hash(cls) % 9973`, which was *not* deterministic across processes. | No. |
| **authoritative** | `nonqb/eligibility.py:1` "PATH_C_STATE.json is authoritative"; `forecast_stage` "after the authoritative list is ingested" | **YES for PATH_C_STATE** — it is authoritative and six days stale (M2). No for the inactives list. | Yes — a reader takes the artifact as current. |
| **exact** | `market_cdf` "Exact model-vs-market probabilities", `qb_accounting.closes_exactly`, `invariants` EXACT table | **No.** `market_cdf`'s whole docstring is an argument for counting draws instead of approximating, and the `invariants` EXACT claims are each measured on 2020–2025 pbp with the one lateral exception named and counted (76 of 3,230). | No. |

---

## 3. Dead code that reads like live code

Full AST scan of every public function in `nfl/production`, `nfl/product`,
`nfl/prospective`, `nfl/identity`, `nfl/ingest`, `nfl/accounting`,
`nfl/capture`, `nfl/parse`, `nfl/adapters`, `nfl/scoring` — 398 public
functions — cross-referenced against `Name`, `Attribute` and string-literal
uses across all 415 `.py` files in the checkout, then each hit re-checked by
grep over `.py` and `.md`.

**Seven of 398 have zero references anywhere:**

| Function | Why a reader assumes it is live |
|---|---|
| `nfl/product/model_health.py:136` `assert_ranking_admissible` | Its own docstring: *"THE GATE. This is the rule the product exists to enforce."* The module exists for this function. |
| `nfl/capture/registry.py:506` `bound_from_series` | `nfl/NFL_G0A_CHECKLIST.md:94,102` cites it twice as what **CLOSES G0A item 4** — "`bound_from_series` closes the interval from the vintage series". `capture/volatility.py:25` describes it as live. Nothing calls it. |
| `nfl/accounting/invariants.py:120` `reconcile_team_player` | Sits inside the module whose docstring is the repo's anti-clipping spine, and is the only function there that builds the residual map the docstring describes. |
| `nfl/product/evaluator.py:264` `cumulative` | `NFL_PRODUCT_LAYER.md:19` lists `evaluator.py` as *"postgame scoring and the **permanent cumulative ledger**"*. `load()` and `summarise()` are called; the cumulative roll-up — including `refinement_candidates` — is not. |
| `nfl/production/nonqb/qb_allocation.py:193` `previous_primary` | Byte-for-byte the same walk as `previous_primary_detail` (`:117`), which *is* the live path (`qb_allocation.py:452`, `product/forecast_stage.py:117`, `research/same_day_retrospective.py:172`). Two functions, one differing in return shape; a reader picking the shorter name gets dead code. |
| `nfl/product/distributions.py:112` `team_vector` | Sits beside `vector()`, which is on every board path. The team-volume draws it reads are real and stored. |
| `nfl/production/derived.py:190` `reset` | Reads as the cache-invalidation half of `_READY`; nothing invalidates. |

**Limit of this method:** it cannot see dynamic dispatch (`getattr`,
`importlib`), and it did not parse `.github/workflows/*.yml`, `run_suite.py`
shell invocations, or `.json` config for entry-point names. A function called
only from a workflow YAML would read as dead here. All seven were confirmed by
grep across `.py` **and** `.md`.

---

## 4. Stale documentation — true when written, false now

| Statement | Where | Why it is now false |
|---|---|---|
| **"No predictive model exists. NFL-1 is not authorised."** | `CLAUDE.md:21`, `README.md:7`, `CURRENT_STATE.md:4`, `SESSION_RECORD_2026-09-06.md:9` | `nfl/production/` holds a full forecast engine — `run_forecast.py` 1,701 lines, `nonqb/` 11,006 lines across 24 modules — with sealed boards, scored games and a market comparator. `NFL_V1_RESEARCH_LEDGER.md:101-102` recorded this contradiction on **2026-09-09**; five days later all three files are unchanged. **`CLAUDE.md` is the file an agent is told to read first.** |
| Test counts — five different figures, none current | `CLAUDE.md` "911 assertions"; `README.md` "1,137 assertions, 16 files" *and* "1,230 assertions across 19 suites"; `CURRENT_STATE.md` "1,230 across 19"; `NFL_V1_PRODUCT_PATH_CLOSURE.md` "56 modules, 600 test functions, 3,362 checks"; `NFL_DECISION_LEDGER.md` (latest) "79 modules, 873 test functions, 4,834 checks" | Filesystem today: **86** `nfl/tests/test_*.py` + **4** `sportsplatform/governance/test_*.py` = **90 files**. The suite was **not run** (other agents concurrent), so these are file counts, not executed results. `README.md` itself warns that "a count in prose goes stale the moment a suite is added" — and then carries two conflicting counts three lines apart. |
| Quarantine counts "47 model-derived, 8 market, 5 outcome, 11 post-hoc" | `CURRENT_STATE.md:§6` | Measured from `allowlist.QUARANTINE`: **47 MODEL_DERIVED / 14 MARKET / 9 OUTCOME / 12 POSTHOC**. Three of four are wrong; only the 47 (which has a named constant, `N_QUARANTINED_MODEL_DERIVED`, and a test) survived. |
| "Nothing NFL-related is running on a schedule" | `CURRENT_STATE.md:§2` | `.github/workflows/` exists; `NFL_V1_RESEARCH_LEDGER.md:97` records four workflows running. |
| MLB `nfl/` drift **RESOLVED** (§1) vs **open, owner: You** (§5) | `CURRENT_STATE.md` | Self-contradictory within one file, as `NFL_V1_RESEARCH_LEDGER.md:96` already noted. |
| "no parser exists" for the nfl.com injury page | `CLAUDE.md:89` | `nfl/parse/injury_report.py` exists, with `nfl/tests/test_injury_parser.py`. |
| "Item 5 — proven, not yet exercised by a production run … nothing has consumed it end to end because NFL-1 has not executed" | `nfl/NFL_G0A_CHECKLIST.md` | Production runs have executed and sealed artifacts. |
| "This lives in `nfl/research/mkt1/`, **never** `nfl/product/`. The product layer has a tested boundary that no sportsbook number may cross." | `NFL_MKT1_MARKET_DIAGNOSTIC.md:9-11` | Four market-handling modules now live in `nfl/product/` (H5), and the boundary test covers four *other* files (H6). |
| `NFL_DECISION_LEDGER.md` "contains only 2026-09-09 entries" | `NFL_V1_RESEARCH_LEDGER.md:106` | Now stale in the other direction — the ledger runs to 2026-09-12. Recorded because it shows the pattern: prose counts in this repo go stale within days, in both directions. |
| "Nothing is CORE, and nothing can be, because no NFL experiment has run." | `nfl/NFL_FEATURE_REGISTRY.md` | Q6–Q9B, R5–R8, SC1, QB3 and TD2 have all run and are adjudicated in `NFL_DECISION_LEDGER.md`. The registry's own rule — "a status above EXPERIMENTAL must cite the experiment that earned it" — is now un-exercised rather than satisfied. |

---

## 5. What the documentation gets right (calibration, so this is not one-sided)

Recorded deliberately: a drift audit that lists only failures teaches the wrong
lesson about this repository.

- `nfl/capture/coverage.py` exists **because** `registry.unmet_targets` was the
  optimistic answer and the runner printed it. The docstring states what
  "covered" does and does not mean, in those words.
- `qb_accounting.reconcile_team` returns
  `{'status': 'NOT_MEASURED', 'why': '… This is not evidence that it holds.'}`
  when no budget was supplied. That is the exact behaviour this audit was
  hunting for the absence of.
- `metrics.UNSUPPORTED` names rushing yards **absent** and names
  `carries × yards_per_carry` as the prohibited substitute. It is the strongest
  anti-fabrication control in the tree.
- `board._shares:245` says "his **game's** opportunity pool" — true — which is
  what isolates `confidence._role:122` as the one false docstring rather than a
  systemic error.
- `inactives.py:74-76` keeps `ROSTER_ACTIVE`, `GAME_ACTIVE` and
  `OFFICIAL_INACTIVE` as three separate names for three separate things.
- `qb_v1.KNOWN_LIMITATIONS` publishes its own +79.89-yard multi-QB bias,
  `int_discrimination` r = 0.0348, and the discrete-interval over-coverage,
  "reported on every run, never smoothed away".

---

## 6. Evidence ceiling

1. **The test suite was not run** (instructed; other agents concurrent). Every
   test figure here is a filesystem count or a quotation from a document, never
   an executed result. I make no claim about pass/fail state.
2. **Caller analysis** is a static AST scan over `Name`/`Attribute`/string
   literals across all 415 `.py` files, plus grep over `.py` and `.md`. It
   cannot see `getattr`/`importlib` dispatch, shell or YAML entry points. Seven
   "dead" names could in principle be reached that way; none was found to be.
3. **The governance matrix result (C1)** comes from actually calling
   `eligibility.matrix()` on 2026-09-14. `PATH_C_STATE.json` is dated
   2026-09-08, so "all ten layers non-production" is **the artifact's state**,
   not necessarily the owner's current view. If the artifact is simply stale,
   C1 is a *reconciliation* debt rather than an overstatement — but either way
   the two documents disagree and `metrics.py` is the one a board reader sees.
4. **No forecast was executed.** The `role_certainty` denominator figures
   (73.456 game vs 40.654 DAL) are carried from the pass brief and confirmed
   here by code reading only — `_role` has no team filter, which is the
   load-bearing fact and is verifiable by inspection.
5. **Market-feed findings (H5, H6)** rest on file existence, imports and the
   test body, not on a run of `daily_board`.
6. I read module docstrings as specification, per the brief. Where a docstring
   and a comment disagree (H8), I recorded both rather than picking one.

---

**CODE CHANGED: NO.** No file outside
`nfl/research/parallel_pass/ws23/` was created, modified or deleted. The only
executions were read-only: `eligibility.matrix()`,
`eligibility.assert_no_stale_labels()`, a column count over
`allowlist.QUARANTINE`, a `csv.DictReader` status tally over one retained raw
roster capture, and the AST caller scan (run from `/tmp`).
