# Point-in-time data-selection contract, 2026-10-08

**Owner directive:** a historical run must never take in information published after its authorized cutoff.
- Authorized vintages are selected through explicit immutable manifests. Raw evidence is not deleted.
- Tests must include historical replays, negative controls, and deliberate post-cutoff injection that cannot affect a
  valid sealed replay.

**Code:**
- `nfl/warehouse/point_in_time.py`
- tests: `nfl/tests/test_point_in_time.py`

**Status:** IMPLEMENTED, TESTED, REPLAY-PROVEN on ATL@NO.
- **Live path:** opt-in. With `NFL_PIT_MANIFEST` unset, every call is the identity. The matched regression is in
  section 5.
- **Not done:** the ordering change (F2) and the game-date check (F1). See section 6.

## 1. What it replaces

The ATL@NO baseline replay (`SHOWDOWN_BASELINE_REPRODUCTION.md`) reproduced production only after three post-lock
files were **deleted** in a worktree, and `TEAM_GAME.json` was **overwritten** with its lock-time version. Each
defect was "the newest file on disk" standing in for "what was known at the cutoff":

| Defect | Where | Effect on the ATL@NO replay |
|---|---|---|
| F1 | `showdown_slate_state` read today's `TEAM_GAME` | the export resolved to the week-17 rematch, and the run refused |
| F2 | `player_prior` reads every roster capture ever taken, last one wins | post-lock positions changed group shares, depth shares and bonus rates |
| F3 | DST and kicker models read the largest play-by-play capture | that capture held ATL@NO itself |

## 2. The contract

**The cutoff.**
- A cutoff is an explicit aware UTC instant with a stated basis, such as the production commit time or kickoff.
- There is no default. A cutoff without a timezone or a basis is refused (`PIT_CUTOFF_UNRESOLVED`,
  `PIT_CUTOFF_BASIS_MISSING`).

**Capture classification.** Every capture under a guarded root is classified once, at build time, by its
**retrieval clock**:

| Guarded root | Clock source | Basis recorded |
|---|---|---|
| `nfl/vintage/*.<16hex>.*` | earliest PASS row for that content id in `nfl/vintage_manifest.jsonl` | `VINTAGE_MANIFEST_FIRST_PASS` |
| `nfl_vintage/raw/*.<16hex>.*` | same | same |
| `nfl/research/postgame/pbp_*.csv.gz` | the capture's provenance sidecar `retrieved_at` | `PROVENANCE_SIDECAR` |
| any of the above with no such record, but committed | the commit that first added the file | `GIT_FIRST_COMMIT`: an upper bound on retrieval, so it can only admit too late |

- A capture retrieved at or before the cutoff is **ADMITTED** and pinned by sha256.
- A later one is `REFUSED_AFTER_CUTOFF`.
- One with no clock at all is `REFUSED_UNCLOCKED`; it is never assumed early.

**Fixed-path derived artifacts** are **resolved**, never overwritten.
- `nfl/warehouse/TEAM_GAME.json` resolves to the last commit of that path at or before the cutoff (basis
  `COMMIT_TIME`).
- That version is materialized from git into a run-scoped, git-ignored scratch directory and pinned by sha256.

**`nfl/derived` caches** are admitted only against declared pins, for example
`DERIVED_REBUILD_MANIFEST.ATL_NO_REPRO_2026-10-07.json`.
- An unpinned derived cache is refused in a sealed run (`PIT_DERIVED_UNPINNED`).
- A cache built from other vintages is refused too (`PIT_DERIVED_VINTAGE_MISMATCH`).

**Explicit per-slate inputs** (DK export, designations, depth chart, starters, inactives):
- pinned by sha256;
- carry the capture clock their slate `PROVENANCE.jsonl` records, or `CLOCK_UNRECORDED`;
- bound a second time by the runner's FREEZE seal.

**The seal.** The manifest's seal is the sha256 of its canonical JSON without the seal field.
- It is written once, to `PIT_MANIFEST.<label>.<seal16>.json`.
- Editing it after sealing is refused (`PIT_MANIFEST_SEAL_BROKEN`).
- An admitted file that has changed is refused (`PIT_ADMITTED_FILE_CHANGED`), and so is one that has gone missing
  (`PIT_ADMITTED_FILE_MISSING`).

## 3. Enforcement, in two layers

**1. Selection.** Every reader that lists captures passes its candidate list through `admit(paths, family)`. This
keeps the reader's own order and drops what the manifest does not admit. Fixed paths pass through `resolve(path)`.

| Data family | Wired readers |
|---|---|
| play-by-play | `dst_model._capture`, `kicking` (fit), `td_rates`, `usage_history`, `warehouse.sources.select` (which feeds `kicker_model`, `team_game` and every other registry consumer) |
| weekly rosters | `player_prior` (position, name and team indexes), `kicking` (kicker roster) |
| schedules, depth charts | `warehouse.sources.select` |
| `TEAM_GAME` | `showdown_slate_state`, `sim.football_points`, `sim.shared_state`, `sim.dst`, `sim.pair_correlations`, `market_response`, `opt.contest`, `warehouse.market_volume` |

**2. Backstop.** With a manifest active, an audit hook (`sys.addaudithook`) refuses any `open` of a guarded file the
manifest does not admit (`PIT_UNAUTHORIZED_READ`). It also refuses any direct read of today's `TEAM_GAME`
(`PIT_UNRESOLVED_READ`).
- **Where it is armed:** in `nfl/__init__.py`, so every process that imports anything from `nfl` is covered.
- **Why there:** the first sealed rebuild found the gap. `kicker_model` reached play-by-play through
  `warehouse.sources`, its process never imported a wired module, and `KICKER_RATES` took in week 4, which is
  ATL@NO itself.
- **Consequence:** a reader that was never wired fails loudly instead of leaking.

## 4. Evidence

### Unit and fixture tests: `nfl/tests/test_point_in_time.py`, 32/32

Each case runs against synthetic stores in a throwaway git repository, so every clock is controlled.
- **Classification:** all four clock kinds; recaptures collapse to the earliest observation; the build is
  deterministic (same seal).
- **Seal:** tampering, a missing timezone and a missing basis are all refused.
- **Live identity:** with no manifest, `admit` and `resolve` are the identity and no read is refused.
- **Selection under a manifest:** `dst_model._capture` picks the pre-cutoff capture over the larger post-lock one.
- **Injection:** an injected capture whose sidecar claims a pre-cutoff clock cannot reach the reader.
- **NEGATIVE CONTROL:** the same injection with no manifest **does** move the reader, so the test can detect a leak.
- **Backstop:** unwired opens of a post-cutoff or injected capture, a direct read of today's `TEAM_GAME`, and an
  unpinned derived cache are all refused.
- **Resolution:** `TEAM_GAME` resolves to the lock-time bytes.
- **Pins:** a pinned derived cache that matches passes; one rebuilt from other vintages is refused.
- **Real ATL@NO cutoff:** it refuses exactly the post-lock play-by-play (`2b3e9f2c`) and roster captures (`efd424c8`,
  `dba8eeff`) that the hand-built replay deleted, and it resolves `TEAM_GAME` to `8feac0f3`.
  - Its first capture had 0 unclocked files.
  - `import nfl` alone arms the backstop.
  - `warehouse.sources` selects a pre-lock 2026 capture.

### Historical replay: ATL@NO from today's full tree, nothing deleted or overlaid

**Setup.**
- Worktree `/home/user/p0work/atl-pit-e1e6d755` at `da99c5de`.
- Manifest `PIT_MANIFEST.ATL_NO_2026W4.1294f0dc638d95c9.json`. Its cutoff is `2026-10-05T23:47:26Z`, the commit time
  of production commit `9736516d`.
- 3,637 captures admitted, 14 refused after the cutoff, `TEAM_GAME` resolved to `8feac0f3`.

| Step | Result |
|---|---|
| Rebuild all six `nfl/derived` caches **under the manifest** | **6/6 byte-identical to the generation-1 pins.** Before the backstop fix: 5/6, with `KICKER_RATES` leaking week 4 |
| Sealed Showdown replay (`PIT_SEALED`) | uploads **`8f4d9a77`** (all), `4047a189`, `17e397b4` and `a30f529f` (per contest) are **exactly production's**. 474 s |
| Matched regression vs the historical baseline (`HIST_BASELINE_B0A2`) | see `nfl/postgame/showdown_atl_no_2026W4/ab/REPRO_PIT_SEALED_vs_b0a2b57b.json` |
| Injection (`PIT_SEALED_INJECTED`) | see section 5 |

## 5. Injection, negative control, live regression

Recorded in `nfl/postgame/showdown_atl_no_2026W4/ab/PIT_INJECTION_EVIDENCE.json` and
`nfl/dfs/salaries/showdown_tb_dal/REGRESSION_DANIELS_R7_vs_R8_PIT.json`. The numbers are filled in from those
artifacts below.

## 6. What this does not do, stated so it is not assumed

- **Ordering is unchanged.**
  - Inside the admitted set, each reader keeps its legacy rule: glob (hash) order with the last one winning for
    rosters, the largest file for DST.
  - Selecting by capture time (finding F2's proposal) is a separate change. It can move outputs where captures
    disagree, so it needs its own matched regression. One change at a time.
- **F1, the game-date check, is not implemented.** With `TEAM_GAME` resolved to its cutoff version, a sealed replay
  resolves the right game. The live path is unaffected for TB@DAL.
- **Retrieval time is an evidence ceiling.**
  - Every 2021–2025 capture was fetched in 2026, so none is admitted for a cutoff in those seasons.
  - Historical replays of earlier seasons would need a published-at clock with stated authority, which this contract
    does not invent.
- **Unguarded data.** The backstop covers the guarded roots, `TEAM_GAME` and `nfl/derived`. Other derived warehouse
  tables are not resolved, for example `MARKET_VOLUME.json`. The read inventory of a sealed run is how they are found;
  see section 5.
- **`vintage_selector`** (injuries, depth charts, schedules for the non-QB pipeline) keeps its own clock. Under a
  manifest its blob opens still pass through the backstop.
