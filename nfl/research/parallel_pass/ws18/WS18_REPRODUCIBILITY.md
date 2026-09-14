# WS18 — Reproducibility and nondeterminism audit of every simulation path

**CODE CHANGED: NO.** Nothing outside `nfl/research/parallel_pass/ws18/` was
written, and nothing inside the repository was modified. The one file this
workstream added besides this report is
`test_ws18_reproducibility.py.proposed`, named so the suite does not collect
it.

Repo `/home/user/nfl`, HEAD `57d38ad`, `python3.12` (3.12.3), numpy 2.5.3.
Measured 2026-09-14.

---

## 0. The answer in one paragraph

**No predictive nondeterminism was found.** Across six processes, three
`PYTHONHASHSEED` settings and four full board builds, every draw this
repository produces was bit-identical: 35 function-level digests and all 22
arrays of `player_draws.npz`, byte for byte. The only differences observed
anywhere were **metadata**: wall-clock timings inside `run_status.json`, and
the run id / `code_commit` / `spec_hash` triple, which moved because another
concurrent workstream changed the *number* of dirty files in the working tree.
Three real weaknesses were found and none of them is a nondeterminism: an
execution identity that keys on a **count** of dirty files rather than their
content (F3), a team-volume layer whose draws depend on **which other teams are
on the slate** (F2), and a fitted-parameter file resolved from an **untracked
cache** whose path and hash never reach the sealed artifact (F1).

**Predictive vs metadata, stated once and used throughout.** A *predictive*
nondeterminism means two runs of the same declared experiment produce different
numbers; it destroys every comparison the project makes and is the severe
class. A *metadata* nondeterminism means only ids, hashes or timestamps differ
while the numbers are identical; it is a bookkeeping problem, which can still
be serious — F3 is one — but it does not put a different model behind an
accepted model's name.

---

## 1. LEVEL 1 — function level

Every draw-producing function in the predictive path, called twice with
identical arguments, arrays compared **bitwise** (sha256 over
`ascontiguousarray(...).tobytes()`, with dtype and shape). Comparing means or
correlations would not have been a test: two different streams agree on the
mean.

Covered: `seeds.stream_id` (all 11 declared streams), `seeds.game_component`,
`rushing_a1.team_component` / `.stream_component`, `layers.appearance`,
`layers.participation`, `layers.targets_carries` (both classes),
`layers.receiving_conversion`, `layers.td_layer`, `p4c_build.gen_weights`,
`p4c_build.mass_draws`, `p4c_lib.block_boot`, `qb3_lib.allocate`. 35 digests.

| Condition | Differing digests |
|---|---|
| repeat inside one process | **0 / 35** |
| second process, `PYTHONHASHSEED` unset | **0 / 34** (+control) |
| third process, `PYTHONHASHSEED` unset | **0 / 34** (+control) |
| `PYTHONHASHSEED=0` | **0 / 34** (+control) |
| `PYTHONHASHSEED=0`, repeated | **0 / 34** (+control) |
| `PYTHONHASHSEED=12345` | **0 / 34** (+control) |

**The positive control is the part that makes the table mean anything.** Each
process also reported `hash('targets') % 9973` — the exact expression
`nfl/production/seeds.py` exists to remove. It read
`2165 / 9153 / 2238 / 7217 / 7217 / 4300`: it varied freely with the hash seed
unset, and it was identical at two runs of `PYTHONHASHSEED=0`. So the harness
demonstrably *can* see per-process hash randomisation, and the 34 zeros are
evidence rather than an assertion that nothing was looked at.

## 2. LEVEL 2 — game level

`nfl/tools/make_board.py build_one(2026, 1, '2026_01_ATL_PIT',
'2026-09-13T15:46:51Z', <tmp>, 1000, 20260908, 'V1_CANDIDATE_R8')`, four
independent builds into four separate output directories, plus one process that
called `build_one` twice.

| Pair | `player_draws.npz` arrays bit-identical |
|---|---|
| A vs B (both `PYTHONHASHSEED` unset) | **22 / 22** |
| A vs C (`PYTHONHASHSEED=0`) | **22 / 22** |
| A vs D (`PYTHONHASHSEED=12345`) | **22 / 22** |
| C vs D | **22 / 22** |
| two `build_one` calls in ONE process | **22 / 22** |

The last row matters on its own: `layers`, `rushing_a1`, `team_volume_v1` and
`readiness` all hold in-process memo caches (`_PARAM_CACHE`, `_FIT_CACHE`,
`RD.cache_clear()`, `NM.cache_clear()`), so a second call in a warm process
takes a different code path through them. It produces the same draws.

Digests as of 2026-09-14, HEAD `57d38ad`, so a later run can be compared
against a written number rather than against a memory:

| array | shape | dtype | sha256 (first 32) |
|---|---|---|---|
| `qb/att` | [8, 1000] | int16 | `f017eff88d91552f596b0be4a10f05bf` |
| `qb/cmp` | [8, 1000] | int16 | `43629a854789f994d74c91c886b2752f` |
| `qb/db` | [8, 1000] | int16 | `487cc9df2d57e9f0983f5d4bbfad6e81` |
| `qb/int` | [8, 1000] | int16 | `b76ee9cd5bf31aee1208ca2141470568` |
| `qb/ptd` | [8, 1000] | int16 | `d096f2d27a4536332537ebf14d3696c9` |
| `qb/pyds` | [8, 1000] | float64 | `34ba0d46ae95b68029a8bd42ec4759c6` |
| `qb/rtd` | [8, 1000] | int16 | `c054f2d9655fa82600783426f3d63628` |
| `qb/rush_opp` | [8, 1000] | int16 | `b49b9eeaa8fc3374a30e9ca58e273b7b` |
| `qb/ryds` | [8, 1000] | float64 | `bb0837dba68439edbe2c56d6db1b7b72` |
| `qb/sacks` | [8, 1000] | int16 | `b4be5736e2880c1fd26e71002850f8ca` |
| `qb/scr` | [8, 1000] | int16 | `ca9640412a03a4ee5df2182c81654ba8` |
| `receiving/receiving_td` | [24, 1000] | int16 | `fce1e679e3bc6cfc9a5b4d2c4fc3d001` |
| `receiving/receiving_yards` | [24, 1000] | int16 | `a424c3811fd1931bd1d85a15265d0564` |
| `receiving/receptions` | [24, 1000] | int16 | `73cbc277647a31cc1e6707ede164c555` |
| `receiving/targets` | [24, 1000] | int16 | `f354e8ff58675841c143dc1da34c7e74` |
| `rushing/carries` | [5, 1000] | float64 | `2fee787a3869df9a4295d84dd7ac5be8` |
| `rushing/rushing_td` | [5, 1000] | int16 | `3f2a646f7320804e477fcccf5b76234c` |
| `team_volume/team_carries` | [2, 1000] | float64 | `0c1fb0358922cc04ec030049ff9e5ddf` |
| `team_volume/team_dropbacks_part` | [2, 1000] | float64 | `79fed15f072e52d091c4fe9909387c6d` |
| `team_volume/team_off_snaps` | [2, 1000] | int16 | `fe10aa9147d8a96c4b968961a7ffc1ff` |
| `team_volume/team_rz_carries` | [2, 1000] | float64 | `09f59b0520fcca24069086a538932d06` |
| `team_volume/team_targets` | [2, 1000] | float64 | `4c9b173d450e8c976104da1bd216e0c0` |

## 3. LEVEL 3 — sealed artifact

`forecast_artifact.json` flattened to leaves and compared field by field, then
`run_status.json`, `board.json`, `BOARD.md`, `player_draws_manifest.json` and
`BOARD_SHA256.txt` compared by file hash.

| Pair | artifact leaves | differing | which |
|---|---|---|---|
| A vs B | 2,166 | **0** | — |
| A vs D | 2,166 | **0** | — |
| A vs C | 2,166 | **3** | `code_commit`, `spec_hash`, `draw_artifact/run_id` |

| file | A vs B | A vs D | A vs C |
|---|---|---|---|
| `forecast_artifact.json` | identical | identical | 3 fields (above) |
| `board.json` (8,289 leaves) | identical | identical | 2: `code_commit`, `run_id` |
| `BOARD.md` | identical | identical | differs **only** by run id, verified by substituting the id and re-diffing: empty |
| `player_draws_manifest.json` (186 leaves) | identical | identical | 1: `run_id` |
| `BOARD_SHA256.txt` | identical | identical | differs (it hashes BOARD.md, which carries the id) |
| `run_status.json` (227 leaves) | **15 differ** | 15 differ | 15 differ |

### Which fields legitimately differ, and which must not

**Legitimately differ — metadata only, zero predictive content:**

* `run_status.json` `/elapsed_s` and `/stages[0..13]/elapsed_s`. All 15
  differing leaves in every pair were wall-clock durations and nothing else —
  e.g. `/stages[4]/elapsed_s` 115.02 vs 102.24 seconds. `run_status.json` is
  not hashed into any other artifact, so this leaks nowhere.
* `code_commit`, `spec_hash`, `draw_artifact/run_id`, `board.json/run_id`,
  `BOARD_SHA256.txt` — **only** by way of the dirty-file counter. See F3;
  "legitimate" here means "explained", not "harmless".

**Must not differ, and did not:** every entry of `distributions` (mean, p10,
p50, p90 and `draws_ref/content_digest` for 32 players), `draw_artifact` and
its 22 per-array sha256s, `draw_artifact_sha256`, `feature_set_hash`,
`source_captures` and their retrieval times, `eligibility_verdict`,
`candidate_components_applied`, `player_ids`, `team_draw_row_index`,
`accounting_verdicts`, `qb_team_dropback_closure`, and the whole
`information_set` block of `board.json`.

Worth stating explicitly because it is the thing that could most easily have
gone wrong: `written_at`, `kickoff_utc` and every `retrieved_at` are read from
captures and the caller's argument, never from the wall clock, so they are
stable. The only wall-clock read on the sealing path is the
`WRITTEN_AT_IN_THE_FUTURE` guard at `nfl/tools/make_board.py:135`, which
compares against `now` and stores nothing.

## 4. PYTHONHASHSEED

`PYTHONHASHSEED` is set nowhere in this repository (confirmed across `.py`,
`.yml`, `.sh`, `.toml`, `.cfg`), so production runs at a random per-process
value. **Draws do not change.** Tested at unset (three distinct observed hash
values), `0` (twice) and `12345`, at function level (34 digests each) and at
game level (22 arrays each): zero differences. The `seeds.py` contract holds
end to end, not only at the two sites its own tests cover.

`nfl/tests/test_v1_game_dependence.py:256` and
`nfl/tests/test_q9_prospective_shadow.py:394` already test `PYTHONHASHSEED` at
the stream-component level. What WS18 adds is that the property survives the
whole layer stack and reaches an identical sealed artifact.

---

## 5. Grep findings

`reaches a draw?` means: can this change a number in `player_draws.npz`.

| file:line | pattern | reaches a draw? | severity |
|---|---|---|---|
| *(repo-wide)* | `np.random.seed` / any global `np.random.*` draw | — | **none — zero occurrences anywhere** |
| *(repo-wide)* | `multiprocessing`, `threading`, `concurrent.futures` under `production/`, `product/`, `prospective/`, `tools/` | — | **none — zero occurrences; the pipeline is single-threaded** |
| `nfl/production/seeds.py:66,119` | explicit stream table + sha256 game component, `hash()` refused by contract | yes | **none — this is the fix** |
| `nfl/production/nonqb/layers.py:171,221,330,385` | `default_rng([seed, ordinal, stream_id, game_component])` | yes | none |
| `nfl/production/nonqb/football_engine.py:436,880` | `default_rng([... game_component ..., 0xC3 / 0xC301])` | yes | none |
| `nfl/production/nonqb/rushing_a1.py:827` | `default_rng([seed, ordinal, game, team, stream])` | yes | none |
| `nfl/production/team_volume_v1.py:496,569` | `default_rng([seed, ordinal, sid])` — **no game component**; rows consumed sequentially at `nfl/research/p4b/p4b_volume.py:185-190` | **yes** | **medium — F2** |
| `nfl/production/nonqb/rushing_a1.py:566-580` | env `NFL_A1_PARAMS`, then untracked `nfl/derived/` cache, then committed frozen `.gz`; chosen path and sha256 not sealed | **yes** | **medium/high — F1** |
| `nfl/production/derived.py:57` | env `NFL_DERIVED_DIR` redirects that cache | **yes** (via F1) | medium — F1 |
| `nfl/production/run_forecast.py:104-127` | `code_commit` = `HEAD + '+dirty[' + COUNT + ']'`, fed to `execution_identity` | no | **medium — F3** |
| `nfl/research/rbb1/rbb1_lib.py:152` | **live `hash(arm) % 97` in a seed vector** | no — research only, imported by nothing under `production/` | **medium — F4** |
| `nfl/research/j1/run_j1.py:58-59` | **live `hash(r['team']) % 9973, hash(arm) % 7919`** | no — research only | **medium — F4** |
| `nfl/production/pipeline.py:97,103,126,137,157,164,190`; `refusal.py:64`; `qb_v1.py:233,241`; `derived.py:146`; `appearance_model.py:157` | `time.time()` / `perf_counter()` / `datetime.now()` | no — durations only, into `run_status.json` | none (this is the 15-leaf diff of §3) |
| `nfl/production/run_forecast.py:80`; `nfl/identity/seal.py:83`; `nfl/product/{evaluator.py:181, market_cdf.py:225, daily_board.py:571, orchestrator.py:40}` | `datetime.now()` defaults | no | none — none is on the `build_one` path |
| `nfl/product/daily_board.py:444` | `for pid in set(qb_ids) | set(...)` — **the only unordered set iteration in `production/`, `product/`, `prospective/`** | no — orders report rows, post-draw | **low** |
| `nfl/product/daily_board.py:169,172,186` | `list(dir.glob(...))[0]` — unsorted glob, first hit | no — selects which sealed dir to read; mitigated by `newest_board_dir` at :179-184 | **low** |
| `nfl/production/derived.py:147`; `appearance_model.py:84`; `product/orchestrator.py:131` | `tempfile.mkdtemp(prefix=...)` — random names | no — verified: no temp path appears in any artifact, and A/B/D artifacts are byte-identical | none |
| `nfl/production/{roster_status.py:107, qb_allocation.py:88, depth_vintage.py:231}`, `team_volume_v1.py:92`, `rushing_a1.py:277`, `product/{board.py:39,59, names.py:65,80}`, `q9shadow/{dryrun.py:208, seal.py:180}` | glob, **all wrapped in `sorted()`** | yes (input selection) | none |
| `nfl/research/p3/p3_features.py:141` | `groups = set(FEATURE_GROUPS)` reaches the frozen appearance fit | membership tests only — feature order is fixed by a literal `if` sequence at :143-156 | none |
| `nfl/research/p4c/p4c_lib.py:228-232` | `collections.defaultdict` grouping then `idx.values()` | yes | none — insertion-ordered from a list |
| `nfl/production/qb_accounting.py:704` (site `football_engine.py:734`) | `default_rng([seed, ordinal, player_bytes, 0x04])` — no game component | yes | low — a player appears for one team per week, so no collision is reachable; flagged for completeness |
| `nfl/research/infogap/check_leak.py:57`, `check_leak2.py:35` | `random.seed(...)` before `random.shuffle` | no — leak checks | none — explicitly seeded |
| `nfl/prospective/q9shadow/ledger.py:269`; `team_volume_v1.py:230`; `q6/forward_chain.py:295` | `zlib.crc32`, not `hash()` | yes | none |

### F1 — a fitted parameter file resolved from an untracked cache

`nfl/production/nonqb/rushing_a1.py:562-580` resolves the A1 parameters in this
order: an explicit path, `$NFL_A1_PARAMS`, `nfl/derived/rushing_a1_params_
2026w01.json`, then the committed `frozen/....json.gz`. The third entry wins on
this machine and `nfl/derived/` is gitignored, so **production draws are
currently taken from an untracked file**. Neither the chosen path nor its
sha256 appears in `forecast_artifact.json` or `run_status.json` — I searched
both for the string and for any `*sha256*` key carrying it and found nothing.

Measured today the two are byte-identical: both 743,202 bytes, sha256
`9d56c2604832cff7c76b6bb2…`. **So this is a reproducibility hazard, not an
observed divergence, and it is reported as such.** The defect is that if they
ever diverge, two runs would produce different draws under the same run id and
nothing in the artifact would say which file was read.

### F2 — team volume draws depend on the slate, not the game

`team_volume_v1.forecast` seeds `[seed, ordinal, stream_id]` with **no game
component** (:496, :569), and `p4b_volume.draw` consumes one generator row by
row (`for i, r in enumerate(rows): out[i] = p[rng.integers(...)]`,
`p4b_volume.py:185-190`). Rows are sorted by `(ord, team)`, so a team's draws
depend on how many teams sort before it.

Measured directly, `m=64`, real fitted data:

| call | result |
|---|---|
| `forecast(2026, 1, ['ATL','PIT'])` vs `forecast(2026, 1, ['ATL','PIT','SF','LA'])` | **5 of 10 shared keys differ** — every `PIT` metric changed; every `ATL` metric identical |
| `['ATL','PIT','SF','LA']` vs `['SF','LA','ATL','PIT']` | **0 differ** — argument order is irrelevant, the internal sort handles it |

`ATL` sorts first among `ATL, LA, PIT, SF` and is unaffected; `PIT` is not.
This is exactly the sequential-consumption signature.

This is **not** a nondeterminism: it is fully determined by the declared team
set, and `team_ids` is sealed in the artifact, so a run is reproducible from
what it records. It is a comparability hazard — the same game sealed alone and
sealed inside a slate carries different team-volume numbers, and nothing labels
that. It is also the one place where the per-game stream separation that
`seeds.py` and `layers.py` established does not reach.

### F3 — the execution identity keys on a count, not on content

`run_forecast.code_commit()` (:104-127) returns `HEAD` plus
`'+dirty[' + str(n) + ']'` where `n` is the **number of lines** from
`git status --porcelain`. That string goes into `execution_identity`, so it
determines `run_id`, `spec_hash` and the output directory name.

Two consequences, in opposite directions, and the second is the worse one:

1. **The run id moves for reasons unrelated to the model.** Observed live, not
   argued: run C sealed at `dirty[32]` and got `9c67f1d2632b99a9` while runs A,
   B and D sealed at `dirty[31]` and got `cad791b9ccb99e5e`. The draws were
   bit-identical in all four. Sharper still, the two-`build_one`-calls-in-one-
   process test produced `9c67f1d2632b99a9` and then `cad791b9ccb99e5e` —
   **two different execution identities for two bit-identical draw sets, in one
   process, seconds apart**, because a concurrent workstream's file appeared
   and vanished.
2. **A count is not a digest.** Any two working trees with the same number of
   dirty files produce the same `code_commit` string and therefore the same
   `run_id`. A tree with 31 uncommitted lines of `layers.py` and a tree with 31
   untracked notes are indistinguishable in the artifact. The docstring's own
   claim — "the artifact was not reproducible from the commit it named and said
   nothing about it" — is only partly discharged: the artifact now says *that*
   the tree was dirty, not *how*.

I did not demonstrate (2) by mutating the working tree, because WS18 may not
modify repository files. It is demonstrated instead by reading :125 and by
calling `execution_identity` directly with two identical and two differing
`code_commit` strings (test §5). The natural repair is a sha256 over the
porcelain output — content, not cardinality — but that is a production change
and not WS18's to make.

*Incidentally:* this workstream's own writes did not perturb anyone else's run
ids, because `nfl/research/parallel_pass/` already collapses to a single `??`
line in `git status --porcelain`.

### F4 — two live instances of the historical defect, in research

`nfl/research/rbb1/rbb1_lib.py:152` and `nfl/research/j1/run_j1.py:58-59` still
put Python `hash()` inside a seed vector — the identical expression
`nfl/production/seeds.py` was written to eliminate. Neither module is imported
by anything under `nfl/production/`, so **no production draw is affected** and
this is not a predictive nondeterminism in the shipped path.

It is still worth reporting, for one specific reason: `team_volume_v1.py:173`
cites `nfl/research/j1/J1_FINDING.md` as the basis for the joint-residual
default that production uses. A finding produced by a run whose stream cannot
be reproduced across processes is weaker evidence than it appears, and the
weakness is invisible from the production side. WS18 did not re-run J1 and
makes no claim about whether its conclusion would change.

---

## 6. The proposed regression test

`nfl/research/parallel_pass/ws18/test_ws18_reproducibility.py.proposed` —
12 checks, all passing, runtime about 40 seconds.

```
python3.12 nfl/research/parallel_pass/ws18/test_ws18_reproducibility.py.proposed
```

1. 35 digests reproduce inside one process, bitwise.
2. The same digests reproduce in child processes at `PYTHONHASHSEED=0` and
   `12345`.
3. **The positive control**: `hash('targets') % 9973` must *differ* between
   those children and must be *stable* across two children at the same seed.
   Without both halves the test is vacuous — a guard is not demonstrated
   because compliant data passes it.
4. An **AST** scan (not grep, so a comment about `hash()` cannot trip it and a
   real call cannot hide behind one) for any live `hash()` under
   `nfl/production/` and `nfl/prospective/`, plus a self-check that the scanner
   detects a planted `default_rng([s, hash('carries') % 9973])`.
5. Two **characterisation locks** on F2 and F3. They assert what the code does
   today so a silent change becomes visible; they are not endorsements. If F2
   or F3 is repaired the corresponding check fails on purpose, and its failure
   message says to update this document rather than delete the check.

It deliberately does **not** run `build_one` — two minutes a build is too slow
for a suite. Levels 2 and 3 stay in this document as measured evidence.

---

## 7. Evidence ceiling

What this audit does **not** establish, stated so nobody quotes it further than
it goes.

* **One game.** `2026_01_ATL_PIT`, 2026 week 1, one `written_at`, one seed
  (20260908), one configuration (`V1_CANDIDATE_R8`), 1,000 draws. Not a slate,
  not a second week, not a second season. F2 is precisely the kind of defect
  that a one-game test is weakest against, and it was found by reading the code
  and then testing the layer directly, not by the board comparison.
* **One machine, one environment.** Python 3.12.3, numpy 2.5.3, single host.
  Cross-machine and cross-numpy-version reproducibility is **untested and
  cannot be tested from here** — there is no second machine and no network.
  Floating-point reduction order in BLAS can differ with thread count;
  `OMP_NUM_THREADS`, `MKL_NUM_THREADS` and `OPENBLAS_NUM_THREADS` were all
  unset for every run, so a machine with a different core count is outside this
  evidence. This is the largest single gap.
* **Four builds, not a distribution.** Four board builds and six function-level
  processes show no divergence. They cannot bound the *rate* of a rare
  nondeterminism. "No difference in four runs" is not "cannot differ", and this
  document does not use the words unbiased, stable, closed or correct about any
  of it.
* **F3(2) is read, not run.** The claim that two different trees with equal
  dirty counts alias to one run id follows from `run_forecast.py:125` and from
  `execution_identity` being a pure function of the string; it was not produced
  by mutating the tree, which WS18 is forbidden to do.
* **F1 is a mechanism, not an observation.** The cache and the frozen file are
  byte-identical today. No divergence was observed and none is claimed.
* **Concurrency was present and was not used as an explanation.** Up to 23
  other workstreams were writing to this checkout throughout. Every difference
  observed was traced to a specific cause before being reported: the 15
  `run_status.json` leaves are wall-clock durations, and the id differences were
  traced to `git status --porcelain | wc -l` moving 31 → 32 → 31, which I read
  directly. Nothing was attributed to "concurrency" as such, and no
  nondeterminism finding rests on a difference that concurrency could explain.
* **Paths not exercised.** The `build_one` run did not reach
  `nfl/prospective/q9shadow/` (shadow/dry-run sealing), `product/daily_board.py`
  or `product/evaluator.py`. Those were audited by reading only; the two `low`
  findings against `daily_board.py` are unmeasured.

---

## 8. What would close the gaps

Not done here, and none of it is WS18's to do.

1. Repeat level 2 and level 3 on a **full slate** and on a second week, which is
   the only thing that turns F2 from a layer-level measurement into a statement
   about production boards.
2. Replace the `dirty[N]` counter with a sha256 over the porcelain output (F3).
3. Seal the resolved A1 parameter path and its sha256 into the artifact (F1) —
   one field, no change to any number.
4. Run the same comparison on a second machine, or at a pinned
   `OMP_NUM_THREADS`, to close the BLAS gap.
5. Decide whether F2 is a defect or an intended slate-level property, and either
   add a game component to `team_volume_v1`'s seed vector or record the decision
   where a reader of a single-game board will meet it.
