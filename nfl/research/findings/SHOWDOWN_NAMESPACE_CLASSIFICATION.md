# `nfl/dfs/showdown/` — classification of all 21 modules

DEF-062 continuation, 2026-09-25. Measured, not recalled: importer map,
fixture-pin counts, and an import-safety probe run on every module.

**I previously said "17 modules". Counted from the filesystem there are 22
files, 21 modules plus `__init__.py`.** A count written in prose goes stale;
this one was enumerated.

## The finding that decides the classification

`nfl/dfs/showdown/` reads as a generic DraftKings Showdown library. It is not.
It holds **one production module and three different historical slates' one-off
scripts**:

| Slate | Modules | Evidence |
|---|---|---|
| DET/BUF 2026W2 | `universe`, `kicker_identity`, `universe_contract`, `captain_metrics`, `correlation`, `scenarios`, `optimal_worlds` | `DET_BUF` literals |
| IND@KC | `build_showdown`, `eval_props_indkc`, `write_props_md`, `write_showdown_md`, `dk_universe_showdown` | `IND@KC` literals, 6/7/3/3/1 |
| NYG@LAR | `cleanup_pool`, `select_no_tracy`, `select_scale_invariant`, `resolve_inactives`, `run_research_fixture`, `research_fixture` | all read `nfl/research/showdown_fixture/`, whose artifacts are `NYG_LAR_SHOWDOWN_FIXTURE.json` and `DKEntries_UPLOAD_NYG_LAR_20.csv` |

The owner's concern is exactly right and is stronger than it looks: the
location does not merely *imply* that this code is generic, it implies these
21 modules are **one** thing. They are four things, and two of the slates are
not the slate every other part of the audit has been reasoning about.

## Import-safety probe — 5 of 21 modules cannot be imported at all

Each was imported in a fresh interpreter. These are not failures at call time;
they are failures at **import** time, because the scripts do their work at
module level with no `if __name__ == '__main__'` guard.

| Module | Result |
|---|---|
| `resolve_inactives` | `IndexError` — reads `sys.argv[1]` at module level |
| `run_research_fixture` | `IndexError` — same |
| `cleanup_pool` | `UPSTREAM_RUN_REFUSED` at stage `artifact_sealing` |
| `select_no_tracy` | `UPSTREAM_RUN_REFUSED` — same |
| `select_scale_invariant` | `UPSTREAM_RUN_REFUSED` — same |

The other 16 import cleanly. **One of those 16 is a false pass and matters
more than the five failures.**

### `build_gpp20.py` — passes only by accident

It imports clean. Its inputs are:

    pool = json.load(open('/tmp/claude-0/pool.json'))
    D    = np.load('/tmp/claude-0/draws.npy')

Both files exist, dated 2026-09-21, in the session scratch directory. They are
not in version control, not in the evidence bundle, and are reclaimed when the
container is. At module level it then runs a 50,000-lineup GPP build. So a
module in the production namespace: has zero importers, executes a heavy
computation on import, and sources its entire input from an ephemeral temp
directory. **Its "clean import" is a property of a leftover file, not of the
code.** This is the Phase-1 defect class in its purest form — a step that
succeeds by reading something nobody knows is there.

## Classification

### A. Reusable production capability — stays in `nfl/dfs/` (9)

| Module | Importers | Pin | Note |
|---|---|---|---|
| `universe` | **16**, incl. `grade_projections`, `grade_props`, `grade_portfolios`, `dual_board` | 2 `DET_BUF` | genuinely production; the pins are what DEF-062 must remove |
| `kicker_identity` | `universe` + 2 tests | 1 | |
| `universe_contract` | 1 test | 1 | contract, not a script |
| `candidates` | `portfolio_report` + test | 0 | already generic |
| `portfolio_report` | 1 test | 0 | already generic |
| `captain_metrics` | 1 test | 1 | CPT is a scoring rule, slate-independent |
| `correlation` | none (has `__main__`) | 1 | generic mechanism |
| `scenarios` | none (has `__main__`) | 1 | generic mechanism |
| `optimal_worlds` | 2 research + 1 test | 1 | generic optimiser |

`research_fixture` is a tenth candidate: 0 pins and a generic shape, but its
only caller is the NYG@LAR runner. Classified with that slate below until a
second caller establishes it as generic — **one caller is not reuse.**

### B. Slate-specific research — leaves `nfl/dfs/` (11)

IND@KC (5): `build_showdown`, `eval_props_indkc`, `write_props_md`,
`write_showdown_md`, `dk_universe_showdown`.
NYG@LAR (6): `cleanup_pool`, `select_no_tracy`, `select_scale_invariant`,
`resolve_inactives`, `run_research_fixture`, `research_fixture`.

None is imported by anything outside its own slate's scripts and its tests.

### C. Obsolete / superseded (1)

`build_gpp20` — /tmp inputs, no importers, no entry guard, superseded by
`optimal_worlds`.

### D. Frozen reference (0)

Nothing here carries a freeze marker. `dossier_reference.py`, the one module
declared frozen in this audit, is elsewhere.

## What is NOT claimed

- That the 11 research modules are correct. They were classified by
  reachability and pin content, not re-derived.
- That moving them changes any number. It changes what their location asserts.
- That the 9 production modules are game-parameterised. Only `universe` has
  been traced to production consumers; the other 8 are reachable from tests and
  research and their pins are still in place.
