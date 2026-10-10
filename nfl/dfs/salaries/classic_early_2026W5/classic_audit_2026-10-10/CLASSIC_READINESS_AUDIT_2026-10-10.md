# Week 5 Early Only Classic: does the Showdown work carry over? (audit, 2026-10-10 evening)

HEAD `4a4d8658`, branch `claude/nfl-greenfield-architecture-stsxmk`. Read-only audit: no entry file, sealed run, projection
of record or portfolio was changed, and nothing was uploaded. Every number below comes from a file or a command named
next to it.

## 0. Bottom line

| Area | Verdict | One-line reason |
|---|---|---|
| Entry file read and contests derived | **PASS** | 190 entries, 190 distinct entry ids, 3 contests (150 + 20 + 20), $82.00 in fees |
| All 190 entries structurally valid | **PASS (structure only)** | one legal lineup ($41,400, 5 games); but see the next row |
| Entries are a usable portfolio | **FAIL** | all 190 hold the **same** lineup, which rosters a practice-squad RB (Grant Finley) and has about 75 projected points |
| DK player pool for this slate | **PASS** | 425 rows, the 8 Early Only games, one 1:00 ET kickoff, legal positions, unique ids |
| DK identity mapping | **FAIL (5 names)** | 249 mapped (6 via the declared suffix rule, 1 alias); 155 explained by the roster; **5 unknown to our roster capture** |
| Projections reflect latest verified availability | **UNVERIFIED** | Friday designations plus the admitted Bears starter; no Sunday inactives yet; FC now disagrees on the CHI QB |
| Fantasy Cruncher export matched | **PASS** | 411 of 416 rows match DK name + club with **identical salaries**; FC stays comparison-only |
| Classic simulations statistically coherent | **FAIL** | passing ≠ receiving yards in 30,790 of 32,000 club-worlds; receiving yards with no catch in 2,000 of 2,000 worlds; 96% of DST worlds non-integer |
| QB change reaches receivers | **FAIL** | Bagent → Williams moves CHI receiving yards by +0.25 and targets by +0.01 (W5-G18) |
| Classic production pipeline runnable for Week 5 | **BLOCKED** | four Week-4-only declarations (section 1.3); the pool route exists only through `rebuild.py` |
| Classic optimizer | **UNVERIFIED for W5** | tests pass (40 fn / 104 checks) but it has never run on this slate; no ownership, no duplication model |
| Two 20-entry contests get distinct portfolios | **FAIL** | the shared candidate cache plus deterministic selection give both the **same 20 lineups** (section 2, row 26) |
| Portfolio strategy independently validated | **FAIL / not validated** | no out-of-sample contest evidence for any Classic objective, cap or stack rule |
| Upload-ready | **BLOCKED** | no portfolio built; no Sunday inactives; pool identity gap; finalize scope is Week 4 only |

## 1. The two production paths, traced

Traced from the entry points to the CSV. Detailed citations: the two trace reports summarised here, and each claim below
re-checked against the code by grep (commands in section 8).

### 1.1 Entry points

* **Classic:** `nfl/tools/classic_slate_pipeline.py` `stages()` (:55-79): state → run → book → portfolios (with reproA/reproB) →
  verify → book_with_exposures → board → fc → props → audit → prelock → changes → finalize → page. Each stage is a separate process.
* **Showdown (TB@DAL, the latest):** `nfl/tools/showdown_next_slate.py run SLATE.json` → `showdown_tonight.py` →
  `showdown_slate_state.build` → `showdown_slate_run.run` → `showdown_portfolio.run` → `final_verify`.

### 1.2 Stage by stage

| Area | Classic | Showdown | Shared? |
|---|---|---|---|
| Ingestion | `early_only.pool/slate` (header-found pool, single kickoff, manifest sha) | `showdown_to_portfolio.s1_ingest`, `showdown_portfolio.dk_input_gate` | **Separate** |
| Freshness | `world_clock.for_target` (classic_slate_state.py:264) | none; relies on freeze hashes and the unplayed-game check | **Classic only** |
| Identity | `proj_v1.resolve_slate_identities` (exact → alias → suffix); unresolved carried as not projected | the same resolver; unresolved refuses | **Shared resolver**, different refusal |
| Club transfer | other-club usage stripped (classic_slate_state.py:328-337, fd25431f) | none | **Classic only** |
| Specialists (LS/P/K listed as skill) | none (only a chart-lift limit) | `specialist_class` (showdown_slate_state.py:218-233) | **Showdown only** |
| Injuries | captured official report by gsis (`pool_audit.injury_rows`) + Sunday evidence packet | hand-supplied designations JSON + inactives file | **Separate**; vocabulary `DESIGNATION_MAP` shared |
| Absent → no opportunity | `role_state.assign` NOT_PLAYING; proj_v1 skips | same | **Shared** |
| Team environment | `showdown_slate_state.environment_for`; football-only arm (classic_slate_run.py:212, 217) | same; showdown_slate_run.py:81, 86 | **Shared** |
| QB → team volume / receivers | not conditioned (proj_v1 `team_volume`, receiver priors) | not conditioned | **Shared defect** (W5-G18) |
| Redistribution | `proj_v1.allocate_opportunity` renormalises survivors | same | **Shared** |
| Simulation | `showdown_draws.build` per game, merged on one world index, games independent | `showdown_draws.build` | **Shared simulator** |
| Post-sim efficiency + INT + DST anchor | `classic_slate_run.efficiency_worlds`, `anchor_means` | the same functions, imported from classic_slate_run | **Shared** (source of the accounting failures) |
| Published-world accounting check | **not run** | `world_accounting_check` at showdown_next_slate.py:382-391 (reported, not blocking) | **Showdown only** |
| Fantasy scoring | `classic_slate_run.dk_from_stats`; DST `nfl/sim/dst.py` | same + captain 1.5× + kicker | Shared base |
| Candidates | `nfl/opt/classic_portfolio.candidates` → `nfl/opt/exact.solve_structured` | `near_optimal_candidates`, forced-captain rounds, `optimal_worlds.solve` | **Separate** |
| Selection | greedy E_w[max_i (S_iw − T_w)+], q = 0.01 | ladder + E[min(depth, m)] + swap polish | **Separate** |
| CSV verify | `classic_upload_verify` | `showdown_portfolio.verify_upload`, `final_verify` | **Separate**; roster-eligibility gate **shared** |
| Release | `classic_finalize` (binary) | release classification READY / PROVISIONAL / NOT_READY | **Separate** |

### 1.3 Week-5 blockers inside the Classic pipeline (verified by grep)

1. `early_only.SLATES['2026W5']` declares no pool, entries or roster capture (early_only.py:88-89). `pool(None, None)` falls
   back to the **Week 3** file (early_only.py:194), so the state stage would refuse on the kickoff check.
2. `classic_finalize.EARLY_ONLY_GAMES` declares only 2026W4 (classic_finalize.py:55-56), so finalize refuses Week 5.
3. `classic_production_audit` reads **`DK_2026W4_*` file names whatever slate it is given** (classic_production_audit.py:454-461,
   477). Run for Week 5, its reproducibility verdict would describe Week 4's files. This is a correctness defect in the
   audit itself, not just a missing declaration.
4. `classic_upload_verify` fails closed with `ROSTER_ELIGIBILITY_UNVERIFIED` because Week 5 declares no `roster_capture`
   (classic_upload_verify.py:154-162). That is correct behaviour; it needs a declaration, not a bypass.

## 2. Showdown defects: do they reach Classic?

Status words:
- **SHARED-FIXED**: the code is shared and the fix reaches Classic.
- **SHARED-DEFECTIVE**: the code is shared and the defect is live in Classic.
- **SHOWDOWN-ONLY**: the fix exists only in Showdown code, and Classic has no equivalent.
- **CLASSIC-SPECIFIC**: Classic has its own version.
- **N/A**: the item does not exist in Classic.
- **UNVERIFIED**: not established either way.

**Proof:** a suite named here was run by the authoritative runner tonight (`SUITE_LOG_CLASSIC_2026-10-10.txt`), or the
measurement was run on the current Week 5 worlds (section 5).

| # | Showdown finding (where found) | Code it lives in | Classic status | Proof / note |
|---|---|---|---|---|
| 1 | False READY: a green run without a current receipt and clean replay (R1, `69fceb0d`) | `showdown_next_slate.final_verify`, `showdown_run_guards.write/verify_receipt` | **SHOWDOWN-ONLY; Classic's own equivalent is defective** | Classic has no receipt. Its reproducibility gate (`classic_production_audit.reproducibility`) hardcodes `DK_2026W4_*` paths (:454-461), so it cannot certify Week 5 |
| 2 | Starter-state integrity before projection (R2, `69fceb0d`) | `showdown_run_guards.verify_starter_state` | **SHOWDOWN-ONLY** | Classic relies on the evidence packet plus `classic_prelock`. `test_sunday_prelock_p0` 4 fn / 11 checks PASS covers the packet starter and Williams-not-absent, not the full guard |
| 3 | Inherited environment variables (R3) | `showdown_next_slate.env_for` | **N/A** | Classic stages take no env-var context |
| 4 | Certificate added-key gap (R4) | `coherence_certificate` | **N/A** | not called by the DK Classic pipeline. The R4 note "Classic path is safe" refers to the older `run_forecast` path, not this one |
| 5 | Content-bound cache keys (R5, `0ea3bc21`) | `kicking.fit`, `sources.measure` | **SHARED-FIXED where used** | kicking is not on Classic |
| 6 | Foreign role artifact and scenario isolation (R6 `0ea3bc21`, isolation audit 2026-10-08) | `role_state.OUT` / `proj_v1.ROLE` = `nfl/derived/ROLE_STATE.json`, `dst_model.OUT` = `nfl/derived/DST_RATES.json` | **SHARED-DEFECTIVE in the Classic production run** | `showdown_slate_run.py:50-79` redirects both and refuses a foreign role file. `classic_slate_run.py:205` writes the shared files. Classic **scenarios** (`classic_scenarios.py:76-84`) and `rebuild.py:291` redirect the role file; neither redirects DST_RATES |
| 7 | Run lock and shared-write tree diff | `showdown_next_slate.py:240-285` | **SHOWDOWN-ONLY** | Classic has no lock and no shared-path guard |
| 8 | Market firewall | structural arm (shared); measured proof `market_firewall_check.py` | **Structural SHARED-FIXED; measured UNVERIFIED** | Classic sets and asserts FOOTBALL_ONLY (`classic_slate_run.py:212, 217`; `classic_portfolio.py:142`). The byte-identity proof has never been run on a Classic slate |
| 9 | Published-world accounting failures (TB@DAL: FAIL) | `classic_slate_run.efficiency_worlds`, `anchor_means` (Showdown imports them) | **SHARED-DEFECTIVE** | measured tonight on Week 5: section 5 table. Classic never runs the checker |
| 10 | Accounting repair (event-consistent worlds) | shadow `bd895bb3`, evaluation `bc446603` | **Not promoted anywhere** | failed its integration evaluation (W5-G17) |
| 11 | DST non-integer worlds (W5-G19, `5e21aed2`) | multiplicative DST anchor (shared) | **SHARED-DEFECTIVE** | 30,769 of 32,000 Week 5 DST worlds non-integer. The shadow integer scorer is default OFF |
| 12 | QB change does not reach receivers or team volume (TB@DAL Daniels/Mayfield; W5-G18) | `proj_v1.team_volume`, receiver priors (shared) | **SHARED-DEFECTIVE** | CHI Bagent → Williams: receivers' yards +0.25, targets +0.01 (section 5). QBCTX shadow failed its preregistered bar (`d990493e`) |
| 13 | QB-environment completeness status | `showdown_run_guards.football_model_status` | **SHOWDOWN-ONLY** | Classic has no such status. CHI is exactly the case it was built for |
| 14 | Ineligible lineups in an upload (TB@DAL OFFICIAL: 11) | `showdown_run_guards.upload_roster_eligibility`, `roster_eligibility.classify` | **SHARED-FIXED (gate); needs a Week 5 declaration** | `classic_upload_verify.py:153-163` calls the same gate and fails closed (`ROSTER_ELIGIBILITY_UNVERIFIED`) until 2026W5 declares a roster capture. `test_classic_roster_gate` 3 fn / 9 PASS. On Showdown the gate also feeds selection; on Classic it is a verifier only |
| 15 | Tied depth rank broken by player id (W5-G13, `39340321`, `a8efedae`) | `role_state` (shared) | **SHARED-FIXED** (provisionally retained by owner ruling) | `test_role_state_tie_order` 8 fn / 11 PASS |
| 16 | Absent starter's replacement capped below his ceiling (W5-G12, `8d7c9822`) | `role_state` (shared) | **SHARED-FIXED** | `test_role_state_absent_rank` 7 fn / 34 PASS |
| 17 | Specialists listed as skill players (LS/P/K) | `showdown_slate_state.specialist_class` | **SHOWDOWN-ONLY; low-impact defect live in Classic** | Week 4 Classic projected four long snappers as PROJECTED at about 0.02 pts each (Mann, Underwood, Deckers, Wagner). The STANDARD pool filter drops them |
| 18 | `p_plays` emitted but not consumed by the draws (SC-APPEAR-1) | `proj_v1` → `showdown_draws` (shared) | **SHARED-DEFECTIVE** (research only) | Questionable players carry full workload in the worlds |
| 19 | Conditional pass drops `_chart_rank` (FEATURE-chart_rank) | `proj_v1.py:1328` (shared) | **SHARED-DEFECTIVE** (proposal, owner) | not applied |
| 20 | Rank-ceiling lift on promotion (RC-1) | `role_state` (shared) | **SHARED-DEFECTIVE** (preregistered, not promoted) | |
| 21 | Accounting checker read the first game's points (W5-G20, `8e10cc5f`) | `world_accounting_check` | **FIXED for multi-game files** | `test_world_accounting_check` 5 fn / 11 PASS. The checker is still not in the Classic pipeline |
| 22 | Secondary-source inactives cannot be READY (TB@DAL RotoWire) | Showdown release blocker | **CLASSIC-SPECIFIC equivalent** | `classic_finalize` requires state `APPLIED`; the new coverage gate requires all 16 clubs inside 15:30Z+ |
| 23 | Captain 1.5×, kicker world, forced captains, ladder, duplication index, cheap-ownership successor | Showdown optimizer | **N/A** | Classic has its own optimizer and none of these. It has **no ownership or duplication model at all** |
| 24 | Other-club usage across a transfer (Kaytron Allen, `fd25431f`) | `classic_slate_state` | **CLASSIC-ONLY** (the reverse gap: Showdown lacks it) | `test_sunday_prelock_p0` PASS |
| 25 | Freshness gate | `world_clock.for_target` | **CLASSIC-ONLY** (the reverse gap) | `test_world_clock_slate` 4 fn / 4 PASS |
| 26 | **Two same-size contests get identical portfolios** (Showdown D-07, OPEN) | `classic_portfolio.build`: one candidate cache per pool (:395-405), and a deterministic `select` (:265-296) | **CLASSIC CARRIES IT, and it bites this week** | Week 5 has two 20-entry contests (Quarter Jukebox and Dime Package). Both map to MAX20, use the same cached candidates and the same policy, so `select` returns the same 20 lineups for both. Week 4 never hit it (150/20/3). Only reported, never prevented (upload_verify :121-126) |
| 27 | QB pass-attempt share leaking into the target prior (DEFECT-QBTGT, `f0245113`) | `proj_v1.allocate_opportunity` `CROSS_FIELD_PRIOR_SCOPE='QB_ONLY'` (shared) | **SHARED-FIXED** | the Week 5 Rodgers row shows `cross_field_prior_scope: QB_ONLY`, targets 0.013 |
| 28 | Within-band order by claim size (DEFECT-TE-ORDER, `ca9fb238`, promoted) | `proj_v1` `CHART_RANK_ORDER` (shared) | **SHARED-FIXED** | `test_role_depth_adversarial`: 8 of 9 fn pass. The one failure is the baseline `SLATE_STATE_NO_IMPLIED_TOTAL` |
| 29 | Missing lineup feed read as "not the starter" (PIT@CLE, `56999bf3`) | appearance gate in `proj_v1` (shared) | **SHARED-FIXED** | Classic reaches it through chart rank and packets (Bagent rank 1, no discount) |
| 30 | The simulator drew its own club volume (11b, `e47f310b`); QB carries missing from the worlds (11a, `d85c1384`) | `showdown_draws` / `sim/game` (shared) | **SHARED-FIXED** | `classic_slate_run.py:243` uses the projection-centred arm |
| 31 | OUT player's volume spread pro rata club-wide (W5-G11) and partly to the QB (W5-G22) | `proj_v1.allocate_opportunity` (shared) | **SHARED-DEFECTIVE** | section 5: Maye +1.13 and Shough +2.11 carries when their RB is out |
| 32 | Other-club weeks counted in the current club's share (W5-G24) | `proj_v1.current_season_shares` (shared) | **SHARED-DEFECTIVE** (patch proposed; your decision) | about 0.10 DK on Kaytron Allen this slate |
| 33 | Star lower tail about 10× too thin (D-01, W5-G5) | `showdown_draws` / `efficiency_worlds` (shared) | **SHARED-DEFECTIVE** | `world_audit/WEEK5_WORLD_CORRECTNESS_AUDIT.md`: star P(<5) 6–20× too thin |
| 34 | Market presence gate: no implied total, no state (`SLATE_STATE_NO_IMPLIED_TOTAL`) | `showdown_slate_state.environment_for:97-102` (shared) | **SHARED-DEFECTIVE** (availability tied to a book line existing) | the number is not consumed by the football arm, but its absence refuses the build |
| 35 | No ownership, field or payout model (D-06); duplication underestimated 3–6× (DEFECT-DUPE-UNDERESTIMATE) | Showdown optimizer | **Classic has no model at all** | `OWNERSHIP: UNAVAILABLE` in every Classic portfolio |

**Suite run tonight** (36 Classic-relevant modules, `--modules`, so **not** a full-suite result): 289 functions,
1,006 checks, 4 failing checks, 6 raised.

| Module | Failure | Status |
|---|---|---|
| `test_classic_slate_state` | the Week 4 state no longer builds, because its games are now played | matches the 2026-10-09 certificate baseline |
| `test_role_depth_adversarial` | `SLATE_STATE_NO_IMPLIED_TOTAL` | matches the certificate baseline |
| `test_v1_projection` | the defence-layer fixture | matches the certificate baseline |
| `test_draw_coherence` | the missing DET_BUF fixture | registered pre-existing as `P2-03-PREEXISTING-SUITE-FAILURES` |

None of these four modules imports `nfl/integrations` (grep), the only code changed in the working tree.

**What the passing tests do and do not prove.** `test_classic_optimizer` (40 fn / 104 checks), `test_classic_portfolio`,
`test_classic_upload_verify` and `test_classic_finalize` pass on fixtures and Week 4 artifacts. They prove the code does what its
tests assert. They do **not** prove the Week 5 pipeline runs (section 1.3 says it cannot, today), and no test asserts the
published-world accounting laws on Classic worlds.

## 3. The 190 entries (from `DKEntries_64.csv`, sha256 `f2bc2d72…`)

Command: `entries_audit.py` in this folder → `ENTRIES_AUDIT.json`.

* **Contests:**

  | Contest | Id | Fee | Entries |
  |---|---|---|---|
  | NFL $20K mini-MAX [150 Max Entry] (Early Only) | 196461814 | $0.50 | 150 |
  | NFL $3K Quarter Jukebox (Early Only) | 196461815 | $0.25 | 20 |
  | NFL $1K Dime Package (Early Only) | 196461816 | $0.10 | 20 |

  The fees total $82.00. This is **not** the Week 4 mix (150 / 20 / **3**). The Dime Package is now a 20-entry contest, and
  `classic_portfolio.PROFILE_BY_ENTRY_COUNT` would map it to the MAX20 profile, the same as the Quarter Jukebox.
* **Roster format:** QB, RB, RB, WR, WR, WR, TE, FLEX, DST. The salary cap is $50,000 (`nfl/dfs/classic/rules.py`).
* **Pool coverage:** DK's own block in the file has 425 rows across the 8 games at 10/11/2026 01:00PM ET:

  | Position | Count |
  |---|---|
  | WR | 158 |
  | RB | 100 |
  | TE | 96 |
  | QB | 55 |
  | DST | 16 |

* **Lineups:** there is **1 distinct lineup in all 190 entries**:

  | Slot | Player | Club | Salary | Our sim mean |
  |---|---|---|---|---|
  | QB | Drake Maye | NE | $6,300 | 20.76 |
  | RB | Grant Finley | NYG | $4,000 | — (practice squad, upload BLOCKED) |
  | RB | Patrick Ricard | NYG | $4,000 | 0.00 |
  | WR | Keenan Allen | IND | $4,300 | 10.80 (Questionable) |
  | WR | Germie Bernard | PIT | $3,400 | 3.41 |
  | WR | Darius Slayton | IND | $3,300 | 0.67 (Questionable) |
  | TE | T.J. Hockenson | MIN | $4,800 | 13.00 |
  | FLEX | Jonathan Taylor | IND | $7,800 | 18.56 |
  | DST | Bengals | CIN | $3,500 | 8.07 |

  The lineup is legal: correct shape, $41,400 under the cap, 5 games, every id in the pool and every slot eligible. It is
  **not playable as a portfolio**:
  * one player is on NYG's practice squad (`DEV` in the week-5 roster capture);
  * it has no QB stack, which our own stack rule (`QB_STACK_MIN=1`) would never produce;
  * it is projected at about 75 points;
  * it is 190 identical copies, against W4's 150 / 20 / 3 unique lineups.

  It reads as DraftKings' placeholder fill, not a constructed lineup.
* **Unfilled or invalid:** no unfilled slots and no ids missing from the pool. The DST cell is DK's own `Bengals  (44419221)`,
  which carries a trailing space in DK's Name column. That is a formatting detail, not an error.

## 4. Fantasy Cruncher (`draftkings_NFL_2026-week-5_players_1.csv`, sha256 `7c9fcf80…`)

Command: `fc_vs_ours.py` → `FC_VS_OURS.json`. It is a separate process, reads our files as data, and writes nothing back.

* **Matched to the right slate:**
  * 416 rows, the same 16 clubs;
  * 411 rows match a DK pool row by name + club, with **0 salary differences**;
  * the 5 unmatched are FC name variants: Chigoziem/Chig Okonkwo, Mitchell/Mitch Tinsley, Nick Westbrook(-Ikhine),
    Andrew/Drew Ogletree, Ben Mason.

  The export carries no timestamp of its own. Its time basis is our ingest time, recorded in `nfl/dfs/inbox/INBOX_LEDGER.jsonl`.
* **What changed versus the previous FC export** (28 players by at least 1 point):
  * FC zeroed Monangai, Diggs, Douglas, Hollins, Nailor, Dulin and Kevin Austin, matching our OUT list.
  * FC raised Swift (+4.9), Olave and McLaurin.
  * FC **dropped Bagent 13.14 → 0.00 and lists Caleb Williams as QB1 at 23.52.**
* **Largest disagreements, with the reason for each:**

  | Player | FC | Ours (sim mean) | Reason |
  |---|---|---|---|
  | Caleb Williams | 23.52 | 0.20 | QB change. We start Bagent from the admitted Bears release; FC starts Williams. **FC contradicts the evidence we hold. It is a discovery signal to verify before lock, not evidence.** |
  | Tyson Bagent | 0.00 | 20.41 | same |
  | TreVeyon Henderson | 13.3 | 5.5 | role. FC treats him as the lead back; we have him second to Stevenson |
  | Mason Taylor, Cole Kmet, Theo Johnson, Drew Sample, Ben Sinnott | 4.8–8.6 | 0.3–2.5 | role. Our TE2s get almost no routes |
  | Rico Dowdle | 12.73 | 6.39 | injury and role (Questionable; we rank him RB2) |
  | Jaylen Warren | 13.20 | 19.17 | injury and role (the other side of Dowdle) |
  | Romeo Doubs, Malik Washington, Garrett Wilson | 8–14 | 14–20 | receiving opportunity. We concentrate targets on WR1s more than FC does |
  | Mike Gesicki, Hockenson, Greg Dulcich | 7.7–8.6 | 11–14 | receiving opportunity, same pattern at TE1 |
  | Tim Patrick (NYJ) | 5.53 | not projected | roster. NYJ's week-5 capture lists him `RES` (reserve). FC thinks he plays. Verify |

  The position-level mean gap (FC minus ours, FC ≥ 3) is QB +2.06, RB +0.59, WR +0.54, TE +0.58. Mean absolute gap is 2.4–2.9 at
  every position.
* **Uncertainty:** FC's Floor and Ceiling are FC's own. Our spread comes from the 2,000 worlds (sd and p90 in the JSON), and the
  thin-left-tail defect (star P(<5) too thin, `world_audit/`) still applies to it.
* **Nothing from FC entered a forecast.**

## 5. Football correctness on the current Classic worlds

Worlds: `runs/w5_prelock_2026-10-10/BASE_BUILD/WORLDS.npz` (sha256 `5310dd3a…`), the projection of record (253 × 2,000).
Command: `world_accounting_check.py` on those files. It is the Showdown checker, never wired into Classic, run here by hand.

| Law | Violations | Verdict |
|---|---|---|
| Club passing yards = receiving yards | **30,790 of 32,000 club-worlds**. Systematic: CHI −22.3 yd mean gap, MIA +40.9 | **FAIL** |
| Passing TD = receiving TD | 58 club-worlds | **FAIL** |
| Receiving yards require a reception | **2,000 of 2,000 worlds** have at least one such player | **FAIL** |
| Receiving TD requires a reception | 1,764 of 2,000 worlds | **FAIL** |
| Club points ≥ 6 × offensive TDs | 1,149 club-worlds | **FAIL** |
| Targets ≤ attempts | 1 (WAS) | **FAIL (marginal)** |
| Receptions ≤ targets, INT ≤ attempts | 0 | PASS |
| Inactive players record no events | 0 | PASS |
| Optimizer's DK points = recomputed from the stat line | 0 | PASS |
| INT thrown ≤ opposing DST takeaways | **not executed**: Classic draws do not store DST components | **UNVERIFIED** |
| DST worlds are integers (DK DST scoring is integer) | **30,769 of 32,000 non-integer** | **FAIL** (W5-G19; shadow fix default OFF) |

Behavioural checks, from `research_projection/scenarios_2026-10-10_prelock/SCENARIO_ANALYSIS.json` (17 scenarios, one vintage):

* **A QB change does not reach receivers.** Bagent → Williams changes CHI pass attempts by −0.19, targets by +0.01 and
  receiving yards by +0.25. Only the two quarterbacks and the RBs' carries move. **FAIL (W5-G18).**
* **Ineligible players keep no opportunity.** In all 17 scenarios the absent player is gone from state, role, projection and
  worlds, and `INACTIVE_NO_EVENTS` = 0. **PASS.**
* **Team volume after absences is invariant by construction.** Club pass attempts move by ≤ 0.65 in every scenario.
  * Redistribution goes to the next men: Stevenson out gives Henderson +6.5 carries; Jeanty out gives Washington +11.6.
  * **The QB also picks up the absent RB's carries:** Maye +1.13, Shough +2.11 (W5-G22). **FAIL (known, unrepaired).**
  * Survivors are renormalised. Nothing models a changed game plan.
* **Correlations:** games are simulated **independently** (`CROSS_GAME_DEPENDENCE: NONE`). Within a game, QB and receivers share
  the club's pass yards before the efficiency step, and the efficiency step's independent per-player factors then break that.
  Stack correlation in the published worlds is therefore weaker than the raw simulator's.

## 6. Classic optimizer (`nfl/opt/classic_portfolio.py`, measured on Week 4, never run on Week 5)

* **Candidates are separate from worlds.**
  * The 150-max had **589 candidates** (130-player pool, 360 sampled worlds × 2 blends + the mean optimum).
  * The 20-max and 3-entry shared **385 candidates** (101-player pool, 240 sampled worlds).
  * Selection then scores every candidate on all **2,000** worlds.
  * Each candidate is a proven optimum of its sampled world, so the search is narrow: at most 721 lineups, all near-optimal on
    some world. Nothing explores deliberately sub-optimal, low-duplication lineups.
* **Stacks:**
  * QB + at least 1 same-team WR/TE (`QB_STACK_MIN=1`);
  * no DST against your own QB;
  * bring-backs are **reported, not required**;
  * RB + DST from the same team is allowed and reported;
  * DST against your other skill players is not forbidden.
* **Multi-game correlation:** none between games (independent simulation).
* **Ownership and leverage:** `OWNERSHIP: UNAVAILABLE`. Duplication risk is **not modelled**, and FC ownership is never read.
* **Uniqueness:** distinct within a contest. The same lineup may appear in two contests, and that is reported only.
* **Exposure and overlap:**

  | Profile | Player cap | QB cap | DST cap | Max shared with any chosen lineup |
  |---|---|---|---|---|
  | MAX150 | 45% | 35% | 30% | 6 of 9 |
  | MAX20 | 65% | 50% | 45% | 7 of 9 |

  The docstring itself says all of these are declared choices, not measurements.
* **Salary:** $50,000 cap and **no minimum**. Week 4 used $47,500–$50,000. The two-game rule is checked after selection, not
  in the solver.
* **Contest objective:** one objective for every profile, E[max over entries of (score − the 99th-percentile candidate score
  in that world)]. The 150-max and 20-max differ only in pool, caps and overlap; there is no field-size or payout-structure
  model.
* **Week-5 specifics:**
  * both 20-entry contests map to MAX20 and share one candidate cache, so a deterministic `select` gives them **identical**
    20-lineup portfolios (row 26);
  * cross-contest duplication is allowed and reported.

## 7. Is any updated version "better"?

Nothing was rebuilt in this audit, so there is no portfolio comparison to report. What changed since the Week 5 baseline, by
category:

* **A. Eligibility improvements (real, verified mechanically):**
  * the CHI starter packet;
  * the Kaytron Allen transfer guard;
  * the DK pool check, including the team-conflict code;
  * the coverage gate for inactives.
* **B. Projection improvements:**
  * none validated;
  * the tie-order repair (W5-G13) is provisionally retained by owner ruling;
  * the Allen share patch (W5-G24) awaits you.
* **C. Statistical-accounting improvements:** **none in Classic.**
  * The event-consistent repair is a shadow, not promoted, and failed its integration evaluation (W5-G17).
  * The DST integer scorer is default OFF (W5-G19).
* **D. Portfolio-selection improvements:** none. The Showdown portfolio work (ladder, depth objective, forced captains,
  duplication index) does not apply to Classic, which has its own optimizer.
* **E. Verified predictive or contest value:** **none.** No Classic objective, cap or stack rule has out-of-sample contest
  evidence. A higher simulated score inside worlds that fail the accounting laws above is not evidence of DFS value.

## 8. The smallest safe changes before lock (proposed, NOT applied: each needs your yes)

None of these changes a projection, a world or a price. Each is separable and reversible by one revert. In line with
"validation and production never in the same commit", each goes in its own commit with its own test.

| # | Change | Kind | Why it is safe | Effect if not done |
|---|---|---|---|---|
| S1 | Register 2026W5 in `early_only.SLATES`. `entries_blob` and `pool_blob` = the ingested DKEntries blob (`nfl/dfs/inbox/store/DK_ENTRIES.f2bc2d72d22b0d35.csv.gz`, sha256 `f2bc2d72…`); `roster_capture` = the week-5 roster capture | declaration | data registration, hash-checked on every read | the Classic pipeline reads the **Week 3** files for this slate (state refuses; the portfolio stage would read Week 3 entries) |
| S2 | Declare the eight 2026W5 games in `classic_finalize.EARLY_ONLY_GAMES` | declaration | a scope list | finalize refuses Week 5 |
| S3 | Parameterise `classic_production_audit` by slate instead of `DK_2026W4_*` | validation bug fix, plus a test that a Week 5 run cannot read Week 4 files | read-only tool | the reproducibility verdict would describe Week 4 |
| S4 | Give the second 20-entry contest a distinct portfolio: select the two MAX20 contests jointly (one 40-lineup selection split 20/20), or exclude the first contest's lineups from the second | portfolio policy | **material: your approval**; caps and overlap rules unchanged | 40 entries hold 20 lineups twice |
| S5 | Run `world_accounting_check` in the Classic pipeline as a reported, non-blocking stage (as Showdown does) | validation, report-only | changes no lineup | the accounting failures stay invisible on every Classic board |
| S6 | Per-slate `ROLE_STATE.json` and `DST_RATES.json` in `classic_slate_run` (mirror `showdown_slate_run.paths`) | isolation | paths only; the PROJ must come out byte-identical (checked) | a concurrent Showdown or scenario run can feed this slate a foreign role file |
| S7 | Resolve the 5 unknown DK names and Tim Patrick (OUT-047), and verify the CHI starter against FC's contrary signal (OUT-047 item 2) | evidence | no code | 5 players stay blocked (all $2,500–$4,000), and the CHI QB stays relayed evidence only |

**Not before lock** (unvalidated or failed their preregistered bars):
* QB-conditioned volume (QBCTX failed);
* the event-consistent accounting repair (W5-G17 damage);
* the integer DST scorer (needs your mean decision);
* an ownership or duplication model;
* bring-back requirements;
* the W5-G24 share patch (yours; about 0.10 DK).

**Order on Sunday if S1–S7 are approved:**
1. 15:30Z inactives paste → coverage gate (16/16);
2. rebuild on the DK pool with the Sunday packet;
3. accounting check (report);
4. portfolios (the original projection of record and this audit are preserved);
5. upload verify;
6. your review.

Nothing is uploaded by this system.

## 9. Commands (reproduce any number above)

```
PYTHONPATH=. python3.12 nfl/integrations/inbox.py                                   # ingest both files
PYTHONPATH=. python3.12 nfl/integrations/dk_pool_check.py 2026W5 --raw-dir nfl/dfs/salaries/raw/classic_early_2026W5 \
    --state nfl/dfs/salaries/classic_early_2026W5/research_projection/rebuild_2026-10-10_prelock/STATE.json --out DK_POOL_CHECK.json
PYTHONPATH=. python3.12 <this folder>/entries_audit.py DKEntries_64.csv DK_POOL_CHECK.json ENTRIES_AUDIT.json
python3.12 -I <this folder>/fc_vs_ours.py FC_NEW.csv FC_OLD.csv <prelock build> FC_VS_OURS.json
python3.12 nfl/tools/world_accounting_check.py <dir with *_WORLDS.npz, *_DRAWS.json, *_STATE.json links> --out WORLD_ACCOUNTING_PRELOCK.json
python3.12 nfl/tests/run_suite.py --modules <36 Classic-relevant modules>             # SUITE_LOG_CLASSIC_2026-10-10.txt
```
