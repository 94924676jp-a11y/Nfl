# Task #45 audit: the Classic pipeline against the owner's production contract

- **Repository HEAD audited:** `e21176c9da6afe773bccbf0f59380e96196716e4` (branch `claude/nfl-greenfield-architecture-stsxmk`).
- **Started:** 2026-10-11 17:01:58 UTC (1:01:58 PM ET), after the 17:00 UTC Early-Only lock. The clock was read with `date -u` before starting.
- **Read-only.** No live Week-5 artifact, uploaded lineup or money-facing output was changed. Tests ran inside a copy-on-write overlay of the checkout (section 6); hashes of every live `DK_2026W5_EARLY_*` file were recorded before and checked after.
- **The contract audited.**
  - The ten clauses are from the owner's message of 2026-10-11 16:28 UTC.
  - The ten acceptance fixtures are from the owner's message of 16:40 UTC (item 8).
  - The release states are from the same message.

Status words used below:

| word | meaning |
|---|---|
| **IMPLEMENTED** | the behaviour exists in the code on the path that produced today's lineups |
| **PARTIAL** | some of the clause exists; what is missing is named |
| **DEFECTIVE** | code exists and produces a wrong result, with the measurement |
| **MISSING** | no code does it |
| **BYPASSED** | code exists but today's lineups did not go through it |

---

## 1. Two pipelines, and why they are separate

| | "production" path | "research" Classic path (what made every Week-5 lineup) |
|---|---|---|
| entry | `nfl/production/run_forecast.py`, reached through `nfl/product/orchestrator.py` and `nfl-product-board.yml` (cron `7,27,47 * * * *`) | five tools run in sequence: `classic_slate_state.py` → `classic_slate_run.py` → `classic_research_book.py` → `nfl/opt/classic_portfolio.py` → `classic_upload_verify.py` |
| unit | one game (`--game-id`, `run_forecast.py:136`) | one DraftKings Classic slate, with portfolios per contest |
| output | a sealed per-game board | lineups mapped to the owner's DK entry ids |
| boards produced in 2026 | **one**, `nfl/product/boards/2026_01_SF_LA` | every Classic upload this season |
| publication gate | `nfl/production/authorization.may_publish`; NFL-1 is NOT AUTHORIZED, and `nfl-production-forecast.yml` is deliberately unscheduled | none |

**Why the production path cannot produce a Classic portfolio.**

1. Its `feature_build` stage has no producer. `run_forecast.py:2297-2318` returns `Outcome.deferred('STAGE_DECLARED_UNIMPLEMENTED')`.
2. Its non-QB stages need 2026 `pbp_participation`, which nflverse publishes only after the season. It is recorded in the manifest as `WATCH_ONLY_SOURCE_NOT_CAPTURED_HERE` (traced in `nfl/research/audit/2026-09-27_FEATURE_BUILD_BLOCKER.md`).
3. It has no slate, contest, entry-id or portfolio concept at all.

**Why the research path became the de-facto production path.**

- It was built on 2026-10-03 (owner priority 17) to produce lineups while the production path was blocked.
- It was never promoted through the production gates. It runs no publication authorization and no point-in-time manifest (`grep NFL_PIT_MANIFEST nfl/tools/classic_*.py`: no match).
- The owner's lineups therefore come from a path that the repository's own governance does not call production.

**A third layer: the governed orchestrator for the research path exists and was not used today.**

- `nfl/tools/classic_slate_pipeline.py` runs fifteen stages in order with a ledger. The stages are: snapshot, state, run, book, portfolios (with two reproducibility builds), verify, book with exposures, owner board, FC comparison, props, independent production audit, prelock verdict, change log, finalize, and page.
- **No Week-5 run ledger exists:** `nfl/dfs/salaries/DK_2026W5_EARLY_RUN_LEDGER.json` is absent, and so is `runs/2026W5/`.
- Every Week-5 build today was the five tools above, run by hand. So today's lineups skipped the snapshot, the reproducibility builds, the independent audit, the prelock verdict, the change log and the finalize gate.
- **BYPASSED.**

---

## 2. Clause by clause (owner message 16:28 UTC)

### Clause 1: the newest point-in-time evidence snapshot — **PARTIAL**

What exists:
- Evidence packets, `nfl/tools/sunday_evidence.py`. Each item carries a source tier, a `received_at` time and a packet id. Provenance is never upgraded (`test_sunday_evidence` 01).
- The state builder takes an evidence packet and an `--as-of` time (`classic_slate_state.py:221`). It reads the injury report and the depth chart lawful at that time (`:286`, `:297`).
- The exact DK slate is a hash-pinned entries blob (`nfl/dfs/salaries/early_only.py`, `SLATES['2026W5']`).

What is missing or wrong:
- **No limited, restricted or questionable-playing state.** A packet item's status must be `ACTIVE` or `INACTIVE` (`sunday_evidence.py:91`). At 16:10 UTC the McLaurin restriction reached the state only as free text. The text reads: `'LIMITED: "likely not a full go", Garafolo: limited snaps. Restriction NOT MODELLED'` (`DK_2026W5_EARLY_STATE.json`, player 44418755, `current_availability.resolution.note`). His status was `REPORTED_ACTIVE_NOT_ON_LIST`, with p_plays 1.0 in every field.
- **No research-sourced tier.** Sources are `OWNER_RELAYED | OFFICIAL_CAPTURED | REHEARSAL` (`sunday_evidence.py:48`). Today's web-searched inactives had to be entered as owner-relayed.
- **The clock is not verified.** `--as-of` is typed by the operator. Freshness checks only that earlier games are scored (`classic_slate_state.py:264`, `world_clock.for_target`). Nothing measures how old the news is.
- **No point-in-time manifest** on this path (section 1).
- Official inactives have not been captured automatically since 2026-09-15: `SOURCE_HAS_NO_ROWS_YET` in 815 manifest rows, as measured in `CURRENT_STATE_AUDIT.md` (d)2.

### Clause 2: determine what the evidence affects and invalidate it — **PARTIAL**

What exists:
- The draws record the projection's hash and the state's hash (`classic_slate_run.py:298-299`).
- The portfolio refuses draws that were not built from the current projection (`classic_portfolio.py:145-147`).
- It refuses a research book built from a different projection or draws (`:125-130`).

What is missing:
- **No consumer checks the state's hash.** `state_sha256` is written at `classic_slate_run.py:299`, and no Classic consumer reads it (grep over `nfl/tools/classic_*`, `nfl/opt`).
  - A state rebuilt after the projection is therefore not detected.
  - Nor is the projection checked against the state it was built from.
- **No dependency graph.** Nothing decides which games, players or contests a new evidence item affects. Every run recomputes everything, which is safe but unbounded.
- **Evidence received after the projection does not mark it stale.** The McLaurin restriction arrived in the 16:10 UTC packet, and nothing refused or labelled the 16:07 UTC projection that did not model it.

### Clause 3: recompute team environments and opportunities, football-aware — **DEFECTIVE**

What exists:
- An absent player gets no role, no projection and no draws (`role_state.py:198-205`, `proj_v1.py:1214-1220`).
- His volume is re-shared because each club pool is renormalised (`proj_v1.py:773` onward).
- 47 absent players were zero in the 16:07 projection and the 16:08 worlds.

Defects:
- **Team volume does not depend on who plays.** `proj_v1.team_volume(panel, env, market_response_enabled)` (`proj_v1.py:167`) takes no quarterback and no availability argument.
  - Measured on the 10-10 CHI scenarios: `team_volume['CHI']` is byte-identical when the starting quarterback changes, and CHI receiver targets and yards are identical (`CURRENT_STATE_AUDIT.md` (d)3). Defect W5-G18, OPEN.
- **Redistribution is pro rata across the whole club.** The quarterback also absorbs running-back carries (W5-G22, OPEN).
- **A limited player cannot be represented** (clause 1). Questionable and doubtful players carry the full projection.
- `p_plays` is folded into each player's mean share and never drawn per world (`showdown_draws._shares`, `:103`, using the unconditional `targets`).
- 44 reserve-list players keep volume under the narrowed reserve rule (F-6).
- The depth table is built on survivors only (L4): backups are understated. Example: Jennings 2.9 against FC 10.1.

### Clause 4: new, coherent joint simulations — **DEFECTIVE** (fresh and reproducible, not coherent)

What exists:
- The worlds are regenerated on every run and tied to the projection hash.
- The seeds are fixed (`SEED + game index`, `classic_slate_run.py:228`), so the randomness is reproducible.
- Club volumes reconcile to the projection within 3 Monte Carlo standard errors (`game.py` `simulate_game_centred`). The book's team accounting gate passes.

Defects. Measured on the 16:08 UTC worlds that produced the uploaded lineups (`prelock_2026-10-11/final_16team_1617Z/WORLD_ACCOUNTING_1608Z.json`):

| law | violations | where it breaks |
|---|---:|---|
| club passing yards = receiving yards | 30,281 of 32,000 club-worlds | two causes: `classic_slate_run.py:113` gives the QB and each receiver independent efficiency factors; `game.py:383` puts yards in an unallocated bucket |
| receiving yards need a catch | 2,000 of 2,000 worlds | yards are split over targets (`game.py:472`) and catches are drawn independently (`:515`) |
| receiving TD needs a catch | 1,809 of 2,000 | TDs are allocated independently of catches (`game.py:487`) |
| club points ≥ 6 × offensive TDs | 1,068 | TDs are inverted from a continuous points draw (`game.py:360`) |
| passing TD = receiving TD | 86 | unallocated TD bucket |
| inactive player has no events | 0 | holds |

- The accounting check is **not run by the Classic pipeline** (`grep world_accounting nfl/tools/classic_* nfl/opt`: no match). It was run by hand today.
- A repair exists as a shadow: `nfl/sim/event_consistent_worlds.py` (`bd895bb3`), zero violations on TB@DAL. It is wired into neither Classic nor production.

### Clause 5: recompute the full DFS decision layer — **PARTIAL**

What exists:
- Fantasy distributions per player come from the worlds.
- Stack rules are declared, and stack frequencies are reported (`classic_portfolio.py`).

What is missing:
- **No ownership or field model:** the artifact itself says `OWNERSHIP: UNAVAILABLE ... Duplication risk is not modelled`.
- No contest-specific objective beyond a declared quantile.
- No sensitivity stage in the pipeline. Today's McLaurin sensitivity scaled only his draws, teammates were not adjusted, and it was a scratch script.

### Clause 6: each contest optimised independently — **DEFECTIVE**

- The two 20-max contests (196461815 and 196461816) receive **identical** lineups.
- Cause: `classic_portfolio.py:397-410`. Candidates are cached per pool (`cand_cache[key]`), and `select()` is deterministic with the same profile, so both contests get the same 20.
- `classic_upload_verify` counts overlap only between a smaller contest and a larger one (`test_classic_upload_verify` 01). It does not fail two equal-size contests that share every lineup.

### Clause 7: a fully verified CSV with complete lineage — **PARTIAL**

What exists:
- `classic_upload_verify.py` independently re-checks the following against the hash-verified owner export:
  - header and entry-id mapping;
  - slots, salary and games;
  - players reported OUT;
  - roster eligibility.
- It records the upload's hash and the entries hash (`:166-167`).

What is missing:
- A run id, the code commit, the simulation seed, the evidence-packet hash and the chain of state, projection, draws, book and portfolio hashes in one release record.
- The verifier is hard-wired to the production file name (`classic_upload_verify.py:141`), so it **cannot verify a tagged file**. The 16:32 UTC alternative the owner uploaded was checked with a scratch script outside the repository (`/tmp/claude-0/trackb/verify_tagged.py`).

### Clause 8: pre/post change report — **BYPASSED**

- `classic_change_log.py` exists. It reports per player old and new projection, cause, exposure and lineup turnover against the pipeline's snapshot.
- It was not run today, because the pipeline was not run. Today's change reports were hand-written text files in `prelock_2026-10-11/`.

### Clause 9: event-triggered invalidation and rebuild, bounded, lock-aware — **MISSING**

- No workflow runs the Classic path (`grep classic_slate .github/workflows/*.yml`: no match).
- The T-90 workflow (`77590da4` on main) captures evidence only.
- Lock awareness:
  - `classic_finalize.py:72` checks that the kickoff string names the 1 PM ET window. It never reads a clock.
  - Nothing refuses to start a rebuild that cannot finish before lock.
- No crash recovery and no run lock: R-4, where the Classic run writes the shared `nfl/derived/ROLE_STATE.json` and `DST_RATES.json`.

### Clause 10: expose failures, never call it certified — **PARTIAL**

What exists:
- Every stage returns an `Outcome` with a named state.
- The portfolio refuses a failed sanity gate, a failed team accounting check or stale draws.
- `classic_finalize` refuses unless every gate passes.

What is missing:
- **The release states exist only in a document.** `CURRENT_AND_CERTIFIED`, `CURRENT_BUT_UNCERTIFIED`, `STALE_FORECAST`, `SELECTION_ONLY_OVERRIDE` and `BLOCKED` appear in `WEEK5_SUNDAY_PRELOCK_BOARD.md` (`e21176c9`) and in no `.py` file.
- Nothing stops an export from being presented as current and coherent while the world accounting fails.

---

## 3. Where the 16:32 UTC McLaurin-excluded file bypassed the process

| step the contract requires | what happened | evidence |
|---|---|---|
| evidence becomes a versioned participation state | became free text, "Restriction NOT MODELLED" | state file, player 44418755 |
| football state and projection rebuilt | **not rebuilt**: same state, projection and draws as 16:17 | `PORTFOLIOS.NO_MCLAURIN_1623Z.json` `inputs_sha256` equals production's: state `1645717d…`, projection `87f826b1…`, draws `5dbe7836…` |
| teammates and QB respond | McLaurin kept his 15.31 projection; no teammate changed | same hashes |
| new worlds | none | same draws hash |
| portfolio re-optimised | yes, but only with one id removed from every pool | `classic_portfolio.build(exclude=('44418755',), tag='NO_MCLAURIN_1623Z')`, `:360-366`, `:391-394` |
| labelled as an override | only inside the JSON (`doc['sensitivity']`, `:445`); the CSV header is identical to production's | `sensitivity/DK_2026W5_EARLY_UPLOAD.NO_MCLAURIN_1623Z.csv` line 1 |
| independently verified | by a scratch script, because the verifier cannot read tagged files | `classic_upload_verify.py:141` |

The code made this possible because `exclude` + `tag` is an ordinary path through `classic_portfolio.build`, with no release state attached.

---

## 4. The owner's ten acceptance fixtures (16:40 UTC, item 8): existing coverage

| fixture | covered today? | evidence |
|---|---|---|
| an inactive player is zero in every world | **checker only**: `world_accounting_check` has `INACTIVE_NO_EVENTS`, tested on synthetic worlds (`test_world_accounting_check`). Not a pipeline gate | section 2, clause 4 |
| teammate roles recomputed | **no test** | — |
| a limited McLaurin creates multiple participation scenarios | **impossible today** (no state) | clause 1 |
| Washington's QB and receiver distributions react | **no** | clause 3 |
| a QB change affects teammates | **fails** (W5-G18, measured) | clause 3 |
| dependent simulations invalidated and regenerated | **partial**: projection → draws only | clause 2 |
| the entire portfolio reconsidered | **yes** for a full run; an exclusion run is also a full re-selection | clause 6 |
| stale artifact consumption blocked | **partial**: projection and draws only, state not checked | clause 2 |
| invalid football worlds fail certification | **no**: worlds with 30,281 violations reached the upload | clause 4 |
| every released lineup traceable to the evidence snapshot | **no**: no release record carrying the packet hash and the chain | clause 7 |

## 5. The owner's five claims, for today's uploaded file

| claim | status |
|---|---|
| freshly executed pipeline | **partly**: the 16:17 stages ran fresh; the uploaded 16:32 file reused them with one exclusion, and the governed orchestrator was not used |
| mathematically coherent football simulation | **no** (clause 4) |
| statistically validated forecast | **no**: no out-of-sample evidence for Classic projections |
| ownership- and field-aware tournament optimizer | **no** (clause 5) |
| proven competitive advantage | **no** |

## 6. Test execution (isolated)

- **How the tests were run.**
  - 33 test modules touching Classic, availability, evidence, lineage, portfolio and world accounting.
  - They ran inside a kernel overlay whose lower layer is the real checkout; every write lands in a scratch upper layer.
  - Each module ran as a script under `python3.12` (2026-10-11, 17:04-17:07 UTC).
  - The two modules without a `__main__` block produced zero output that way. Zero output is not a pass, so they were re-run through `nfl/tests/run_suite.py --modules`.
- **Live Week-5 files unchanged.** `sha256sum` of the 12 `DK_2026W5_EARLY_*` files and 2 sensitivity files, plus `git status`, were identical before and after.

| result | modules |
|---|---|
| **PASS (30)** | availability_retention 70, availability_watch 114, classic_dfs_reasoning 6, classic_equivalence 19, classic_failure_injection 24, classic_fc_diff 5, classic_finalize 17, classic_optimizer 104, classic_pipeline 15, classic_portfolio 16, classic_prop_compare 19, classic_research_book 24, classic_roster_gate, classic_slate_run_anchor 26, classic_staging 9, classic_upload_verify 16, contest_portfolio 7, dfs_portfolio_guard 26, evidence_layers 17, lineage 8, portfolio_frontier 11, postgame_classic_week 15, research_portfolio 27, roster_reserve_absent 16, showdown_to_portfolio 19, slate_to_portfolio 8, sunday_evidence 19, world_accounting_check 11, sunday_prelock_p0 11 (via run_suite), role_evidence 67 (via run_suite) |
| **FAIL: data missing (1)** | `test_availability_semantics`: `nfl/vintage/weekly_rosters.197453cb51cb7383.raw.csv.gz` is not in the checkout; only the `.reduced` blob is. Not caused by the overlay. |
| **FAIL: time-dependent fixture (1)** | `test_classic_slate_state`, 1 check: "the week-4 state builds with a packet" now refuses `CLASSIC_STATE_GAME_NOT_IN_WAREHOUSE`, because week 4 has been played. The test reads the live warehouse, so it is not hermetic in time. |
| **FAIL: environment (1)** | `test_execution_lineage`, 1 of 55: the local `origin/main` ref is stale (`214438e1` against remote `77590da4`). Needs a fetch, not a code change. |

**What the passing tests do not cover.** None of the 30 passing modules tests any clause-level behaviour that section 4 marks missing. They are unit tests of components that exist; the contract's behaviours are not among them.

**Test isolation defect (R-7), reproduced.** Run directly, the modules wrote these files inside the checkout. The overlay absorbed the writes.

| file | status |
|---|---|
| `nfl/dfs/salaries/DK_UPLOAD_GENERATED.csv` | **tracked** |
| `nfl/dfs/salaries/SLATE_STATUS_BOARD.json` | **tracked** |
| `nfl/dfs/salaries/SLATE_STATUS_BOARD.md` | **tracked** |
| `nfl/derived/SOURCE_MEASUREMENT_CACHE.json` | ignored |
| `nfl/tests/_control_hits.jsonl` | ignored |

- Under `run_suite.py` the state root is isolated ("boundary CLEAN"). So the runner protects the tree; running a test file directly does not.
- Running `test_sunday_prelock_p0.py` directly outside an overlay can still overwrite the live `DK_2026W5_EARLY_STATE.json` (`classic_slate_state.build`, `write=True`).

## 7. Summary verdict

| clause | verdict |
|---|---|
| 1 evidence snapshot | PARTIAL: no limited state, clock not verified, no PIT manifest |
| 2 dependency invalidation | PARTIAL: projection→draws enforced; state hash written, never checked; no stale-on-new-evidence |
| 3 football recompute | DEFECTIVE: QB-blind team volume (W5-G18); pro-rata reallocation; no participation distributions |
| 4 coherent simulations | DEFECTIVE: 30,281 / 2,000 / 1,809 / 1,068 / 76 violations; check not wired |
| 5 DFS layer | PARTIAL: no ownership/field model |
| 6 per-contest optimisation | DEFECTIVE: identical 20-max sets |
| 7 verified CSV with lineage | PARTIAL: no release record; tagged files unverifiable by the verifier |
| 8 change report | BYPASSED: tool exists, not run |
| 9 event-triggered orchestration | MISSING |
| 10 explicit failure / release states | PARTIAL: release states exist only in a document |

The order of the repair work follows from this. It is set out in the step C/D plan, not here.
