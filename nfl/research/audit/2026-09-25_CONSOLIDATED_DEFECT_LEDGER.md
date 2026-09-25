# Consolidated defect ledger — full audit, 2026-09-25

HEAD at audit time: `8d63b6c`. Every number below was produced by a command in
this repository and is reproducible by the command named with it. Machine-
readable companion: `nfl/research/audit/CROSS_LAYER_INVENTORY.json`. Detector:
`nfl/tools/cross_layer_audit.py`.

**The audit was built so the kicker defect would appear on its own.** It does,
as `UNIVERSE_MISMATCH kicking -> dk_scoring`, one row among four relation kinds.
Nobody had to remember kickers.

## Headline counts

| measure | value | how |
|---|---|---|
| Declared draw families | 10 | contract registry |
| PARTIAL_JOIN modules | **18** | `cross_layer_audit.py` |
| UNIVERSE_MISMATCH | **1** (kicking, 2 of 2 rows) | same |
| ORPHANED_OUTPUT families | 1 (`rush_player_pool`) | same |
| Modules pinned to a single-game fixture | **35** | same |
| Governance modules with **zero** non-test consumers | **9** | grep, verified individually |
| Refusal codes in non-research code | 949 | regex scan |
| …with **no test reference at all** | **524 (55%)** | same |
| Production files able to discover outside the pinned cut | **25 of 124**, 42 hits | `discovery_audit.scan()` |
| `vintage_manifest.jsonl` | **53.55 MB**, +0.81 MB/day | `git cat-file -s` over 15 commits |
| Forecast cut ledger rows | **1** | `wc -l` |

## The pattern that produces most of this

Three distinct shapes, and the second is the dangerous one:

1. **A component exists and the next stage does not consume it.** 18
   PARTIAL_JOIN rows, 9 orphaned modules, 1 orphaned family.
2. **A component exists, consumes correctly, and is pinned to a game that is
   not this one.** 35 modules. This is worse than shape 1 because the code
   reads as production, imports production, is unit-tested, and is
   nevertheless unreachable for any new slate. Yesterday's kicker failure was
   shape 2, not shape 1, and I reported it as shape 1.
3. **A step returns something partial and the caller reads it as complete.**
   Named in the project's own doctrine; still the largest single cause.

---

# Subsystem state matrix

Derived mechanically, not judged. `EXEC` is YES when a non-test module
references it, FIXTURE when it resolves inputs from a single-game literal,
ORPHAN when nothing outside tests references it. `REFUS` is refusal codes
referenced in tests over codes declared. `PROSPECTIVELY_VALIDATED` and
`PROMOTED` are NO for every row and are omitted rather than printed as a column
of NOs. `SUCC` means a test file references the module — **not** that a suite
run passed (A-12).

| subsystem | IMPL | EXEC | consumers | SUCC | REFUS | ADVERS |
|---|---|---|---|---|---|---|
| evidence/run_input | YES | via orphans only | 3 | YES | 5/7 | YES |
| evidence/pinned_contract | YES | YES | 20 | YES | n/a | NO |
| availability/feed | YES | YES | 1 | YES | 7/19 | NO |
| availability/inactives | YES | YES | 4 | YES | 19/26 | YES |
| availability/roster_status | YES | YES | 2 | YES | 6/11 | NO |
| identity/crosswalk | YES | **ORPHAN** | 0 | YES | n/a | YES |
| identity/kicker | YES | **FIXTURE** | 1 | YES | **0/6** | NO |
| model/qb_allocation | YES | YES | 8 | YES | 23/30 | NO |
| model/gadget_rush | YES | YES | 1 | YES | **1/14** | NO |
| model/kicking | YES | YES | 1 | YES | 5/15 | NO |
| model/team_volume | YES | YES | 13 | YES | 10/20 | NO |
| model/role_state | YES | YES | 8 | YES | 18/31 | NO |
| dfs/universe | YES | **FIXTURE** | 13 | YES | **0/7** | NO |
| dfs/universe_contract | YES | **FIXTURE** | 0 | YES | 4/14 | NO |
| dfs/research_portfolio | YES | **ORPHAN** | 0 | YES | n/a | NO |
| dfs/lineup_integrity | YES | **ORPHAN** | 0 | YES | 10/12 | NO |
| dfs/classic_optimizer | YES | YES | 3 | YES | 5/13 | NO |
| market/evaluate | YES | YES | 2 | YES | **1/9** | NO |
| prospective/cut_ledger | YES | **ORPHAN** | 0 | YES | n/a | YES |
| prospective/artifact | YES | YES | 31 | YES | 22/32 | YES |
| postgame/grade_portfolios | YES | **FIXTURE** | 0 | YES | 2/3 | NO |
| postgame/outcome | YES | **FIXTURE** | 5 | YES | **2/16** | NO |
| gov/source_validity | YES | **ORPHAN** | 0 | YES | 4/4 | YES |
| gov/source_census | YES | **ORPHAN** | 0 | YES | 9/9 | YES |
| gov/pregame_readiness | YES | **ORPHAN** | 0 | YES | 12/14 | NO |
| gov/conditioning | YES | **ORPHAN** | 0 | YES | 8/10 | NO |
| gov/discovery_audit | YES | **ORPHAN** | 0 | YES | n/a | NO |
| gov/unavail_owns_nothing | YES | YES | 3 | YES | 5/10 | YES |

**Read the ORPHAN column first.** Nine rows, every one of them a gate or a
contract, every one written in the last two days, none of them called by
anything that runs. That is the single largest finding in this audit and it is
not a subtle one.

---

# TRACK A — correctness, integrity, sealing, provenance

## A-01 · DFS/postgame/market surface is pinned to Week-2 fixtures
* **Subsystem** dfs, postgame, market
* **File** `nfl/dfs/showdown/universe.py:31` — `FROZEN = _REPO / 'nfl/research/dfs/DET_BUF_2026W2/frozen'`; 34 further modules listed in the inventory
* **Evidence** `python3.12 nfl/tools/cross_layer_audit.py` → `FIXTURE_PINNED (35)`. `universe.py::build()` joins the kicking layer by gsis_id, refuses ambiguous names, and tags DST `UNSUPPORTED` — it is **correct** and it **cannot be pointed at ATL/GB**.
* **Severity** CRITICAL
* **Affects** future slates (and explains last night)
* **Changes** product completeness; not forecast correctness
* **Smallest fix** thread `game_id` through `load()`/`build()` as a required argument and resolve `FROZEN` from it; keep the Week-2 path as a test fixture
* **Changes model behaviour** no
* **Owner approval** no
* **Required test** build for two different game_ids in one process and assert the universes differ
* **Prospective requirement** none; this is plumbing

## A-02 · Nine governance modules have zero consumers
* **Subsystem** governance
* **Files** `identity_crosswalk`, `research_portfolio`, `lineup_integrity`, `cut_ledger`, `source_validity`, `source_census`, `pregame_readiness`, `conditioning_contract`, `discovery_audit`
* **Evidence** `grep -rln <mod> nfl --include=*.py | grep -v /tests/ | grep -v /<mod>.py` → 0 for each
* **Note** all nine were written in the last 48 hours. They are unit-tested and nothing that runs calls any of them. `nfl/truth/run_input.py` reaches production **only** through three of them, so the evidence-contract subtree has no root consumer either.
* **Severity** CRITICAL — a gate nothing calls is documentation
* **Affects** both
* **Changes** sealing and semantics
* **Smallest fix** one composition point (`pregame_readiness`) invoked by the forecast entry point before expensive simulation, returning BLOCK on any hard failure
* **Changes model behaviour** no, unless a gate fires — which is the point
* **Owner approval** **yes** for promoting `unavailable_owns_nothing` DIAGNOSTIC → HARD
* **Required test** entry point refuses when a gate is seeded to fail
* **Prospective requirement** first governed run must record which gates evaluated, not merely that it passed

## A-03 · 524 of 949 refusal codes have no test reference
* **Subsystem** all
* **Evidence** regex scan over non-research code vs the whole `nfl/tests` corpus. The scan counts a code as tested if the literal appears anywhere in tests, so 55% is a **lower bound** on the gap.
* **Worst offenders** `dfs/showdown/universe.py` 0/7 · `showdown/kicker_identity.py` 0/6 · `market/evaluate.py` 1/9 · `nonqb/gadget_rush.py` 1/14 · `postgame/outcome.py` 2/16
* **Severity** HIGH
* **Affects** both
* **Changes** sealing — an untested refusal is an untested guarantee
* **Smallest fix** a ratchet test asserting the untested count never rises, plus real tests for the five worst modules
* **Changes model behaviour** no
* **Owner approval** no
* **Required test** the ratchet itself
* **Prospective requirement** none

## A-04 · 18 modules join only part of the scoring layers
* **Subsystem** dfs, postgame, tools
* **Evidence** `cross_layer_audit.py` → `PARTIAL_JOIN (18)`
* **Two that matter most** `nfl/tools/post_inactive_verify.py` reads `dk_scoring` and never `kicking` — the availability verification I wrote yesterday cannot see a kicker. `nfl/postgame/grade_projections.py` likewise — postgame grading cannot grade a kicker.
* **Severity** HIGH
* **Affects** both
* **Changes** product completeness and semantics
* **Smallest fix** a single `player_universe()` helper that joins every gsis-axis scoring layer and refuses when a declared layer is absent; every consumer calls it
* **Changes model behaviour** no
* **Owner approval** no
* **Required test** the helper's universe equals the union of declared layers; a removed layer raises
* **Prospective requirement** none

## A-05 · Kicker rows exist in no dk_scoring row
* **Subsystem** draw artifact
* **Evidence** `UNIVERSE_MISMATCH kicking -> dk_scoring`, 2 of 2 rows (`00-0025565`, `00-0040899`). The 30 `dk_scoring` rows contain no kicker, and no `dk_scoring` row is identically zero, so the mismatch is structural rather than a zeroed placeholder.
* **Severity** HIGH — this is the root of A-04's worst cases
* **Affects** both
* **Changes** semantics: "the DK universe" means two different sets depending on which layer you read
* **Smallest fix** do **not** merge kickers into `dk_scoring` (their scoring rules differ); instead declare in the manifest that `dk_scoring` is *non-kicking* DK points and have the contract refuse a consumer that treats it as the full slate
* **Changes model behaviour** no
* **Owner approval** no
* **Required test** manifest semantic field asserted; consumer without a kicking join fails the contract
* **Prospective requirement** none

## A-06 · 25 of 124 production files can discover evidence outside the pinned cut
* **Subsystem** evidence boundary
* **Evidence** `discovery_audit.scan()` → 42 hits, `glob=34, sorted_index=4, rglob=2, newest_lawful=2`; worst `nfl/production/pipeline.py` (5), `nonqb/rushing_conversion.py` (4), `nonqb/availability_feed.py` (3), `nonqb/current_season_panel.py` (3)
* **Correction to a prior claim** I said yesterday this was "8 vintage-globbing modules". Measured, it is 25 files. The earlier figure was wrong and understated.
* **Severity** HIGH
* **Affects** both
* **Changes** sealing — a second information clock after bundle freeze
* **Smallest fix** convert each to resolve from the pinned partition set; the auditor already ratchets the count
* **Changes model behaviour** **possibly** — a module currently reading newest-local may change inputs. Must be done one module at a time with a before/after fingerprint.
* **Owner approval** no, but the baseline must be snapshotted first
* **Required test** ratchet (exists) plus per-module determinism proof
* **Prospective requirement** yes — any input change invalidates comparison across the boundary

## A-07 · `vintage_manifest.jsonl` is past GitHub's advisory limit
* **Subsystem** storage
* **Evidence** 53,549,801 bytes over 6,757 lines (7.9 KB/line). Sizes at 15 commits give +0.81 MB/day over the last 4 days. `.git` is 1.1 GB.
* **Dates** already past the 50 MB advisory. At the measured rate the 100 MB hard rejection lands **≈ 2026-11-21**.
* **Correction to a prior claim** my ticket said "around 9 October". That is **not reproduced** by measurement; treat the ticket's date as stale. The risk is real, the date was wrong, and the 4-day rate may itself be unrepresentative because manifest growth is slate-driven.
* **Severity** MEDIUM now, CRITICAL on the day a push is rejected
* **Affects** future slates
* **Changes** nothing about correctness; it stops work entirely when it fires
* **Smallest fix** shard by season/week and leave a pointer index
* **Changes model behaviour** no
* **Owner approval** **yes** — every consumer that assumes one monolithic file must be enumerated first
* **Required test** a consumer census, then round-trip equality pre/post shard
* **Prospective requirement** none

## A-08 · Forecast cut ledger has one row and no refusal state
* **Subsystem** prospective
* **File** `nfl/prospective/FORECAST_CUT_LEDGER.jsonl`, `nfl/prospective/cut_ledger.py`
* **Evidence** `wc -l` → 1. Row keys carry no `state`/`status` field, so a refused or blocked cut has nowhere to be recorded.
* **Severity** HIGH — this is the ledger the whole evaluation loop depends on
* **Affects** both
* **Changes** sealing; creates survivorship bias by construction
* **Smallest fix** add a required `state` enum (`REGISTERED` / `REFUSED` / `BLOCKED`) with the refusal code, and register every eligible pre-kickoff cut including the ones that refuse
* **Changes model behaviour** no
* **Owner approval** no
* **Required test** a refused cut appears in the ledger; a second registration for one game_id still refuses
* **Prospective requirement** this **is** the prospective requirement for everything else

## A-09 · No postgame grading is wired; today's grade was manual
* **Subsystem** postgame
* **File** `nfl/postgame/grade_portfolios.py` — fixture-pinned (A-01) and **0 non-test consumers**
* **Evidence** the ATL/GB grade in `2026-09-25_DAY_AUDIT_ATL_GB.md` was assembled by hand from search snippets four hours after the whistle, and is partial for 8 of 26 players
* **Severity** HIGH
* **Affects** both
* **Changes** product completeness; blocks the evaluation loop entirely
* **Smallest fix** game-parameterise `grade_portfolios` (falls out of A-01) and call it from an outcome-ingest entry point
* **Changes model behaviour** no
* **Owner approval** no
* **Required test** grade a fixture game end to end; refuse on a partial box score (`outcome.require()` already does this — it is untested at 2/16)
* **Prospective requirement** the first automatic grade must reproduce the manual one where they overlap

## A-10 · The owner's availability vocabulary does not exist in code
* **Subsystem** availability truth
* **Evidence** `grep -rn "ACTIVE_FOR_GAME\|RESERVE_EXEMPT\|SUSPENDED" nfl --include=*.py` → no production hit. `OFFICIAL_INACTIVE` appears only under `nfl/research/`.
* **Consequence** the distinction that caught Josh Jacobs — official-inactive versus reserve/exempt versus not-established — is enforced nowhere. "Absent from the inactive list" can still reach a consumer as available.
* **Severity** HIGH
* **Affects** both
* **Changes** forecast correctness and product completeness
* **Smallest fix** one enum in `nfl/production/nonqb/` with `NOT_ESTABLISHED` as the default, and `availability_feed.states()` returning it; no inference from absence
* **Changes model behaviour** **yes** — players currently implicitly available become NOT_ESTABLISHED
* **Owner approval** **yes**
* **Required test** an exempt-list player is never ACTIVE_FOR_GAME; absence from a feed yields NOT_ESTABLISHED, never available
* **Prospective requirement** yes, forward-chained: the change moves allocation

## A-11 · Cross-player correlation computed from independent streams, unguarded
* **Subsystem** dfs semantics
* **File** `nfl/dfs/showdown/build_showdown.py:115-119` — `_corr(a, b)` over two players' draw arrays
* **Evidence** the draw manifest's own `draw_index_semantics` says a cross-row correlation on this axis "measures the generator's lack of coupling, not a football quantity". `_corr` has no such guard and its output is emitted into the artifact.
* **Related** `build_showdown.py:147`, `build_gpp20.py:44`, `showdown/candidates.py:121` emit lineup p90 without the lower-bound label that `research_portfolio.py` carries. `dfs/classic/optimizer.py` by contrast documents the problem and measures it.
* **Severity** HIGH — output looks more certain than the evidence supports, which is the mandate's own test
* **Affects** both
* **Changes** semantics
* **Smallest fix** `_corr` refuses unless the manifest declares `SHARED_FOOTBALL_WORLD`; quantile fields renamed to carry `_indep_lower_bound`
* **Changes model behaviour** no
* **Owner approval** no
* **Required test** a manifest declaring independent streams makes `_corr` refuse
* **Prospective requirement** none

## A-12 · `run_suite.py` produces nothing for the whole of a run
* **Subsystem** test harness
* **Evidence** started at 04:33Z, 0 bytes of stdout at 45 s, 102 s and 155 s while the process was alive (pid confirmed, not `pgrep`)
* **Severity** MEDIUM — it makes every other classification unverifiable within a working session
* **Affects** both
* **Changes** nothing directly; it blocks evidence
* **Smallest fix** flush per suite and write a partial JSON after each
* **Owner approval** no
* **Required test** a killed run leaves a readable partial result

## A-13 · Production imports a DFS module
* **Subsystem** layering
* **File** `nfl/production/review/gated_projection.py:217` → `from nfl.dfs import eligibility_integrity`
* **Evidence, and a deliberate downgrade** I checked whether this leaks market data into a predictive path: `grep -n "salary\|ownership\|price\|odds" nfl/dfs/eligibility_integrity.py` returns nothing. It is a **direction violation, not a leak.** No other production or truth module imports `nfl.market` or `nfl.dfs`.
* **Severity** LOW
* **Affects** future slates
* **Changes** nothing today; it is the seam a future leak would enter through
* **Smallest fix** move the eligibility check under `nfl/production/`
* **Required test** an import-direction test forbidding `nfl.production` → `nfl.dfs`

## A-14 · `rush_player_pool` is produced for research only
* **Subsystem** draw artifact
* **Evidence** `ORPHANED_OUTPUT`: consumers are all under `nfl/research/`
* **Severity** LOW — may be entirely intended
* **Smallest fix** a one-line declaration in the registry that this family is diagnostic, so the auditor stops reporting it
* **Owner approval** no

---

# TRACK B — predictive and product capability

Ranked by expected effect on unseen-game forecasting or tournament decisions.
None of these is a correctness defect; all are missing capability.

## B-01 · No shared football world (highest value on this track)
Measured cost, from last night: restricted to the ten players whose actual DK
score is verified, a legal lineup scoring **131.4** existed at lock, captained by
Drake London — **ranked tenth of ten** by our objective. The shape that won was
one correlated Atlanta blowout. Independent per-player streams cannot represent
it, so the selector never saw it. Same marginals, coupling only: p90 +39.3%, p95
+51.1%, p99 +67.7%. This is no longer a caveat; it is a measured 29-point gap.
**Existing task B3.** Owner approval to prioritise: yes.

## B-02 · No DST model at all
No DST layer exists in the draw artifact; `universe.py` correctly tags DST
`UNSUPPORTED`. Two priced DSTs were unsearchable last night. In Showdown a DST
reaches optimal lineups regularly. Requires a new layer, not a join.

## B-03 · The QB universe can silently omit a rostered QB
`qb` layer carried 6 rows; Kedon Slovis was priced at $6,000 and absent from all
30 `dk_scoring` rows. `nfl/production/pool_audit.py:730` already emits
`POSITION_NOT_MODELLED`, and it has 4 consumers, none of which is a DFS selector.
A rostered, priced, active player can disappear between layers with no refusal
reaching the product.

## B-04 · Kyle Pitts-class over-projection
Mean 7.95 against a player with two catches in three games. Receiving zero-mass
(existing **B5**) is the named mechanism.

## B-05 · No ownership, duplication or field model
`C4a` remains unstarted, so "optimise the chance one entry wins" cannot be
formulated even with B-01 solved — there is no field to win against.

## B-06 · No exact CDF at a market line
`graded_prediction_means` requires probabilities from stored draws or a dense
CDF. Draws are stored, so this is reachable; nothing computes it.

---

# Regression classification against current HEAD

Not one of these is taken from a `repaired: true` field; each was re-derived.

| prior claim | class | proof at HEAD `8d63b6c` |
|---|---|---|
| "8 vintage-globbing modules" | **STILL_PRESENT**, understated | 25 files, 42 hits |
| "vintage manifest blocks pushes ~9 Oct" | **SUPERSEDED** | 53.55 MB, +0.81 MB/day → ≈21 Nov |
| "the model cannot project kickers" | **SUPERSEDED (false)** | `kicking` layer, 22 consumers, Folk 8.26→10.0 actual |
| "the kicking join was never made" | **SUPERSEDED** | `universe.py::build()` joins it correctly; it is fixture-pinned |
| "suite produces nothing on timeout" | **STILL_PRESENT** | 0 bytes at 155 s with the process alive |
| DFS-1 "universe stale against live contest" | **STILL_PRESENT** | 35 fixture-pinned modules |
| "bytes we do not have" (outbox, ×2) | **SUPERSEDED** | search reachable; every content-bearing host 403 |
| A1 "evidence boundary holds at the contract" | **STILL_PRESENT** | holds at the contract, and 25 files can still discover around it |
| ADV-1 adversarial battery | **FIXED** for its 14 inputs | 7 of 28 subsystems carry an adversarial test; the rest do not |

---

# Priority order A — correctness, integrity, sealing, provenance

1. **A-02** wire the nine orphaned gates to one composition point. Everything
   else in this ledger was already detectable; nothing was obliged to listen.
2. **A-01** game-parameterise the DFS/postgame surface. Unblocks A-04, A-09.
3. **A-08** cut-ledger state field and register refusals. Without it no later
   evidence is admissible.
4. **A-10** availability enum with `NOT_ESTABLISHED` as default. *Owner.*
5. **A-04 / A-05** one joined player universe, and a manifest that says what
   `dk_scoring` means.
6. **A-06** convert the 25 discovering modules, one at a time, fingerprinted.
7. **A-11** refuse cross-player correlation under independent streams.
8. **A-03** refusal-code ratchet plus the five worst modules.
9. **A-07** manifest sharding. *Owner — consumer census first.*
10. **A-12**, **A-13**, **A-14**.

# Priority order B — predictive and product improvement

1. **B-01** minimal shared football world. The only item with a measured cost.
2. **B-03** refuse a contest the model cannot cover, and surface
   `POSITION_NOT_MODELLED` to the selector.
3. **B-02** DST layer.
4. **B-04** receiving zero mass.
5. **B-05** ownership and field model.
6. **B-06** exact CDF at a line.

These two orders are deliberately not merged. A-02 outranks B-01 because a
system whose gates nothing calls cannot be trusted to report whether B-01
worked.

# What this audit did not establish

* **The suite's current pass/fail classification.** It was running and silent at
  the time of writing (A-12). Every SUCCESS_TESTED cell below rests on a test
  file existing and referencing the module, not on a green run.
* **ADVERSARIAL_TESTED for 21 of 28 subsystems** — not checked rather than
  absent.
* **PROSPECTIVELY_VALIDATED is NO for every subsystem in the matrix**, because
  the cut ledger holds one row and nothing has been graded automatically.
* **PROMOTED is NO for every subsystem.** No candidate has been promoted.
* Whether any of the 35 fixture pins is deliberate. Each needs an answer in
  writing; the tool does not know intent.

V2 NOT YET EARNED
