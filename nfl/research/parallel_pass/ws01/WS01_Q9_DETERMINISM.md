# WS01 — Q9 prospective dry-run: why DETERMINISTIC fails

**CODE CHANGED: NO**

Research only. No file outside `nfl/research/parallel_pass/ws01/` was created or
edited. The repair below is a literal diff that was **not applied**. It was
verified by monkey-patching the replacement function at runtime, in-process,
which leaves the file on disk untouched.

Investigated at repo `/home/user/nfl`, branch `claude/nfl-greenfield-architecture-stsxmk`,
HEAD `57d38ad`, interpreter `python3.12`. Note that at investigation time
`nfl/prospective/q9shadow/seal.py`, `shadow.py`, `ledger.py` and
`nfl/tests/test_q9_prospective_shadow.py` all carried **uncommitted changes from
concurrent agents** (304 added lines in `seal.py` alone). Every measurement below
is against the working tree as it stood, not against `HEAD`.

---

## Answer in one paragraph

The model is deterministic. The **draws are bit-identical**, byte for byte, across
runs, across processes, and across the commit boundary. What is not deterministic
is one field of run metadata: `art['code_commit']`, produced by
`seal._code_commit()`, which appends **a count of the lines of `git status
--porcelain`** to the commit hash. That count is a property of the working tree at
the instant of the call — and **the sealing path's own output files change it**.
Run 1 writes `dryrun/proof/...`, which adds an untracked entry, so run 2 (and even
the *second team of run 1*) observes a different count and therefore a different
`code_commit`. `code_commit` is inside the sealed body, inside `artifact_id`'s
`REQUIRED` field list, and inside `ExecutionIdentity.code_version`, so it moves
`forecast_id`, `seal_payload_sha256`, `artifact_id` and `identity_fingerprint`
together, and nothing else. The identity of a forecast is a function of that
forecast's own side effects. That is the defect.

---

## Classification table

| # | Sub-question | Classification |
|---|---|---|
| 1 | Exact differing serialized fields and their JSON paths | **CONFIRMED** |
| 2 | Where each differing value originates in code | **CONFIRMED** |
| 3 | Does wall-clock / runtime metadata enter the sealed payload | **CONFIRMED** (one channel, named; wall-clock and PID: FALSIFIED) |
| 4 | Are the predictive draws bit-identical | **CONFIRMED** — identical |
| 5 | Model deterministic while only sealing is not | **CONFIRMED** |
| 6 | Are the fingerprint SEMANTICS wrong, or the IMPLEMENTATION | **PARTIAL** — semantics right in principle, one term of them wrong; implementation wrong |
| 7 | Is `test_q9_prospective_shadow.py` FALSE-GREEN | **CONFIRMED** |
| — | Can the committed proof's hashes be reproduced today | **UNRESOLVED** (evidence ceiling, below) |

---

## 1. The exact differing fields — CONFIRMED

Two seals of identical inputs were run in one process, into two output roots,
with `written_at='2026-09-12T12:00:00Z'`, `n_draws=120`, `n_games=1`,
`source=HISTORICAL_FRAME`, `dry_run=True` — the exact call
`dryrun._seal_once` makes. Both sealed artifacts were flattened to leaf JSON
paths and compared key by key. **No key was present in one and absent in the
other.** Exactly seven leaves differed, for the `ARI` team-game:

| JSON path inside the written artifact | run 1 | run 2 |
|---|---|---|
| `.code_commit` | `57d38ad…d17+dirty[30]` | `57d38ad…d17+dirty[31]` |
| `.forecast_id` | `Q9SH-60cfbaee8c263576` | `Q9SH-e0865f5b0069760f` |
| `.artifact_id` | `ca176e3b45596501…` | `9111f1d900165d9f…` |
| `.seal.payload_sha256` | `60cfbaee8c263576…` | `e0865f5b0069760f…` |
| `.seal.seal_sha256` | `9bbe3a10319f8bda…` | `a7e854b70dfd40bd…` |
| `.seal.identity_fingerprint` | `NFLFP-79b99c7e3f9302fa` | `NFLFP-aa356b1bc81f3001` |
| `.draw_artifact` | `…/ws01/_probe/run1/2024_01_ARI_BUF/ARI/shadow_target_draws.npz` | `…/run2/…` |

**`.code_commit` is the only independent difference.** The five hash fields are
deterministic functions of it. `.draw_artifact` is the output path, and it is
already excluded from both hashes (see §3), so it differs harmlessly.

**Inside the sealed payload specifically, exactly one path differs: `code_commit`.**
The payload is `json.dumps(art minus {draw_artifact, draw_artifact_sha256},
sort_keys=True, default=str)` — `seal.py:574-577`. `artifact_id` is computed over
`artifact.REQUIRED` only (`nfl/prospective/artifact.py:465-469`), and that tuple
(`artifact.py:62-65`) contains `'code_commit'` and does **not** contain
`draw_artifact`. So the output path reaches neither hash; `code_commit` reaches
both.

**The pattern is diagnostic in itself.** Of the two team-games sealed per run,
only **ARI** — the *first* seal of the *first* run — differed. `BUF` was identical
in both runs. A nondeterministic model would not produce that pattern; a
first-call-only environment change would, and does.

## 2. Origin in code — CONFIRMED

```
nfl/prospective/q9shadow/seal.py:162-175   def _code_commit()
nfl/prospective/q9shadow/seal.py:170-172       git status --porcelain, len(lines)
nfl/prospective/q9shadow/seal.py:175          return rev + (f'+dirty[{n}]' if n else '')
nfl/prospective/q9shadow/seal.py:356          ExecutionIdentity(code_version=_code_commit(), ...)
nfl/prospective/q9shadow/seal.py:407          art['code_commit'] = identity.code_version
nfl/prospective/q9shadow/seal.py:574-577      body = json.dumps(art minus 2 keys); forecast_id = 'Q9SH-'+sha256(body)[:16]
nfl/prospective/q9shadow/seal.py:586          art['artifact_id'] = ART.artifact_id(art)
nfl/prospective/artifact.py:62-65             REQUIRED includes 'code_commit'
nfl/prospective/artifact.py:465-469           artifact_id = sha256 over REQUIRED
nfl/identity/execution_identity.py:60,69      ExecutionIdentity.code_version, in as_dict()
nfl/identity/execution_identity.py:77-81      fingerprint() = 'NFLFP-' + sha256(as_dict())[:16]
```

The verbatim defect, `seal.py:170-175`:

```python
        st = subprocess.run(['git', 'status', '--porcelain'], cwd=str(_REPO),
                            capture_output=True, text=True, timeout=20)
        n = len([x for x in st.stdout.splitlines() if x.strip()])
    except (OSError, subprocess.SubprocessError):
        n = -1
    return rev + (f'+dirty[{n}]' if n else '')
```

### The self-reference, measured

`dryrun.run()` was executed with `_code_commit` wrapped in a tracer that also
recorded `len(git status --porcelain)` and whether `PROOF_ROOT` existed. The
seal ledger was redirected to a scratch path so no repository file was appended
to. Four seals, four calls:

```
call 0  (run1/ARI)  code_commit=57d38ad…+dirty[31]  status_lines=31  proof_root_exists=False
call 1  (run1/BUF)  code_commit=57d38ad…+dirty[32]  status_lines=32  proof_root_exists=True
call 2  (run2/ARI)  code_commit=57d38ad…+dirty[32]  status_lines=32  proof_root_exists=True
call 3  (run2/BUF)  code_commit=57d38ad…+dirty[32]  status_lines=32  proof_root_exists=True
DETERMINISTIC: FAIL     n_failed 1  ['DETERMINISTIC']
```

The mechanism, exactly:

1. `dryrun.py:133-134` — `shutil.rmtree(PROOF_ROOT)` removes
   `nfl/prospective/q9shadow/dryrun/proof/`, so that untracked entry is **gone**.
2. `seal.py:356` — run1/ARI calls `_code_commit()`. `dirty[31]`.
3. `seal.py:363-371` — run1/ARI then does `out_dir.mkdir(parents=True)` and
   `np.savez_compressed(...)`, **re-creating** `dryrun/proof/`.
4. Every subsequent `_code_commit()` sees one more untracked line. `dirty[32]`.

The order matters and is the whole bug: the identity is sampled **before** the
artifact is written, and the artifact's own writing changes what the next sample
returns.

### Why the committed proof says PASS — CONFIRMED

`git log` shows `Q9_PROSPECTIVE_DRYRUN_PROOF.json`, `seal.py` and
`dryrun/2025_01_ARI_NO/` were **all introduced in the same commit `da58aec`**. So
at the moment the proof was generated, the whole `nfl/prospective/q9shadow/`
subtree was untracked, and `git status --porcelain` **collapses an untracked
directory to a single line**. Creating `dryrun/proof/` inside an already-collapsed
untracked parent adds nothing to the count. Demonstrated on this tree:

```
$ git status --porcelain | grep parallel_pass
?? nfl/research/parallel_pass/
$ mkdir -p nfl/research/parallel_pass/ws01/_probe/deep/deeper
$ echo x > nfl/research/parallel_pass/ws01/_probe/deep/deeper/y.txt
$ git status --porcelain | grep -c .
31                       # unchanged
```

So the committed `PASS` was not a determinism result. It was an artefact of git's
untracked-directory collapsing, which held while those files were uncommitted and
stopped holding the moment they were committed. **The check has never tested the
property it is named after.**

## 3. Wall-clock, temp paths, PIDs, iteration order — CONFIRMED (one channel only)

Grepped across the whole sealing chain (`seal.py`, `inputs.py`, `shadow.py`,
`candidate.py`, `nfl/prospective/artifact.py`, `nfl/identity/seal.py`) for
`getpid`, `time.time()`, `tempfile`, `uuid`, `random.`, `datetime.now`, `utcnow`.

* **PID: FALSIFIED.** No `os.getpid` anywhere in the chain.
* **tempfile / uuid: FALSIFIED.** Not used.
* **Unseeded RNG: FALSIFIED.** `shadow.py:220,258,283` all construct
  `np.random.default_rng(_stream_parts(seed, season, week, team, …))` — fully
  keyed, no entropy source.
* **Wall clock: FALSIFIED for the dry-run path.** `seal.py:157-159 _now()` is used
  only as the *default* for `written_at` (`seal.py:818 written_at = written_at or
  _now()`) and for the live eligibility cutoff (`seal.py:253`). `dryrun.py:78`
  passes `WRITTEN_AT = '2026-09-12T12:00:00Z'` explicitly, and the synthetic
  kickoff is derived from it. `nfl/identity/seal.py:83` has the same defaulting
  and is also passed an explicit value from `seal.py:581`. Empirically confirmed:
  `written_at`, `kickoff_utc`, `cutoff`, `time_basis` and every
  `source_captures[*].retrieved_at` were **identical** across the two runs.
  `retrieved_at` is read from the vintage manifest (`inputs.py:249-250`), not from
  a clock.
* **Iteration order: FALSIFIED.** `inputs.partitions` iterates `sorted(...)`
  (`inputs.py:246`); `ExecutionIdentity.as_dict` sorts partitions by
  `partition_id` (`execution_identity.py:73-74`); every `json.dumps` in the chain
  uses `sort_keys=True`.
* **Temp/output path: CONFIRMED present in the written artifact, EXCLUDED from
  both hashes.** `art['draw_artifact']` (`seal.py:431`) is the output location. It
  is in `SEAL_BODY_EXCLUDED` (`seal.py:573`) so it is out of the payload, and it
  is in `artifact.OPTIONAL` not `REQUIRED` so it is out of `artifact_id`. This was
  already fixed once — the comment at `seal.py:558-572` describes exactly this
  earlier determinism failure. The fix was correct and still holds.
* **Working-tree state: CONFIRMED, and it is the only channel.** `+dirty[n]`.

## 4. Are the predictive draws bit-identical? — CONFIRMED

Two independent tests, both pass:

```
draws ARI: file_bytes_identical=True  arrays_bit_identical=True  n_arrays=8
           sha256=b370646ba04674c8 / b370646ba04674c8
draws BUF: file_bytes_identical=True  arrays_bit_identical=True  n_arrays=8
           sha256=58b74c59ec8d25b3 / 58b74c59ec8d25b3
```

* `p1.read_bytes() == p2.read_bytes()` — the whole `.npz` container is byte-equal.
* `np.array_equal(z1[k], z2[k]) and z1[k].dtype == z2[k].dtype` for all 8 arrays
  (`{production,candidate}__targets`, `{production,candidate}__receiving_yards`,
  `budget`, `appearance`, `p_hurdle`, `base_share`) — equal values **and** equal
  dtypes, so this is not float-coercion equality.

Stronger still, and this is the load-bearing cross-check: the draw hashes I
measure today are **identical to the ones in the committed proof**, which was
generated on a different day, in a different process, before commit `da58aec`,
and before 304 lines of uncommitted change landed in `seal.py`:

| | committed proof | measured today |
|---|---|---|
| ARI `draw_artifact_sha256` | `b370646ba04674c8cabce444…` | same |
| ARI `draw_content_sha256` | `8c19543182ab87ec84fd5514…` | same |
| BUF `draw_artifact_sha256` | `58b74c59ec8d25b359b4aab7…` | same |
| BUF `draw_content_sha256` | `9ff7c5e688c82b4db3567cd6…` | same |
| `spec_hash` (both) | `82c8b52699bbeb00e656a3d5…` | same |
| `feature_set_hash` (both) | `f620eeed09d0dd6e` | same |

## 5. Model determinism vs sealing determinism — CONFIRMED, they separate cleanly

| Quantity | Reproducible in-process | Reproducible across processes | Reproducible across the commit boundary |
|---|---|---|---|
| draws (`.npz` bytes) | YES | YES | YES |
| `draw_content_sha256` | YES | YES | YES |
| `spec_hash` | YES | YES | YES |
| `feature_set_hash` | YES | YES | YES |
| `distributions`, `player_summary`, `reconciliation`, `fallback_counters` | YES | YES | not compared |
| `code_commit` | **NO** | **NO** | **NO** |
| `forecast_id` / `artifact_id` / `seal_payload_sha256` / `identity_fingerprint` | **NO** | **NO** | **NO** |

Every failing row is downstream of `code_commit` and of nothing else. The
separation was confirmed constructively: with `_code_commit` pinned so that all
four seals share one value, `dryrun.run()` returns

```
DETERMINISTIC: PASS    n_failed 0  []
run1 == run2: True
```

with no other change to any code or data. That isolates the cause to a single
term.

**This distinction already exists elsewhere in the repository and Q9 did not
inherit it.** `nfl/tests/test_product_orchestration.py:89-106` makes exactly this
separation, in a comment that reads:

> `# THE RUN ID IS NOT THE DETERMINISM CLAIM. It hashes the execution`
> `# identity, which includes` `code_commit()` `-- and that carries a`
> `# ` `+dirty[n]` `counter of uncommitted files. Editing anything in the tree`
> `# moves the run id while the forecast is untouched, which is the counter`
> `# working. The claim being proven is that the DRAWS reproduce, so the run`
> `# id is only required to match when the tree is clean enough for it to be`
> `# a fair comparison.`

and it then skips the run-id comparison when `git status --porcelain` is
non-empty. `nfl/research/forensic_corrected.py:159-163` records the same hazard as
a named caveat ("the dirty counts differed (33 against 40)") and
`forensic_corrected.py:175` strips everything after `+` before comparing. So two
other modules already treat `+dirty[n]` as **not part of a comparable identity**.
Q9's `DETERMINISTIC` check puts it inside one.

## 6. Semantics or implementation? — PARTIAL

Split into three claims, because they have different answers.

**(a) "The fingerprint should include the code version." SEMANTICS CORRECT.**
This is the whole point of `nfl/identity/execution_identity.py`, whose docstring
is written against MLB's M0 failure; `test_seal_ordering.py:560-561` asserts that
a changed `code_version` moves the fingerprint. Removing code identity from the
fingerprint would be a regression. Do not do it.

**(b) "The dirty marker should be a count of `git status --porcelain` lines."
SEMANTICS WRONG.** A count is not an identity — two different edits that touch the
same number of paths collide — and, decisively, the quantity being counted is
*not code*. It counts modified data artifacts, appended ledgers, fetched
play-by-play captures, other agents' scratch directories, and the seal's own
outputs. Empirically on this tree: 31 total status lines, of which **9** touch a
`.py` file. Twenty-two of the thirty-one terms in Q9's "code version" are not code.

**(c) The implementation is WRONG, independently of (b), and in a way that
(b) alone does not describe.** Even granting a count, sampling it *inside* the
function whose own side effects change it makes the value self-referential. A
forecast's identity must not be a function of that forecast having been written.
This is the same class as `sealed_index._rel` and as the `draw_artifact`
exclusion the module already documents at `seal.py:558-572` — a machine property
leaking into evidence — caught twice and missed on the third channel.

**So: the semantics of including code identity are right; the semantics of the
`+dirty[n]` term are wrong; and the implementation is wrong on top of that.**

## 7. Is `test_q9_prospective_shadow.py` FALSE-GREEN? — CONFIRMED

`test_21_the_dry_run_proof_holds` never re-runs the proof. It reads the stored
JSON and asserts on the number the file itself reports. Exact lines, verbatim:

```python
664: def test_21_the_dry_run_proof_holds():
665:     print('\n-- the dry-run proof artifact --')
666:     pr = _load('Q9_PROSPECTIVE_DRYRUN_PROOF.json')
667:     check('the proof artifact exists', pr is not None)
...
676:     check('all ten checks hold', pr['n_failed'] == 0 and pr['n_checks'] == 10,
677:           f"{pr['n_checks'] - pr['n_failed']}/{pr['n_checks']} "
678:           f"{pr['failed']}")
```

with, at lines 76-78:

```python
76: def _load(name):
77:     p = CAND.HERE / name
78:     return json.loads(p.read_text()) if p.exists() else None
```

`nfl.prospective.q9shadow.dryrun` is **not imported anywhere in the test module** —
`grep -n dryrun nfl/tests/test_q9_prospective_shadow.py` returns only `_load`
call sites and `SEAL.DRYRUN` path uses. So `pr['n_failed'] == 0` asserts that a
JSON file contains a zero, not that any property holds.

The remaining checks in `test_21` are the same shape. Line 677-679 checks that
`'draw_content_sha256'` appears in the stored `identity_keys_compared` **list** —
i.e. that the proof *claims* to have compared the content hash. It does not
compare anything.

**Demonstrated, not just read.** `test_21` was executed in-process with `_load`
patched to return the **committed** proof JSON (`git show HEAD:…`), at a moment
when the live property was independently known to FAIL:

```
committed proof says n_failed = 0 | DETERMINISTIC = PASS
  ok   the proof artifact exists
  ok   it is not evidence about accuracy
  ok   nothing is promoted
  ok   all ten checks hold  10/10 []
  ok   determinism compared the draw CONTENT hash
  ok   every named outcome reader was poisoned  6
  ok   the schedule check is not vacuous: the raw capture DOES carry outcome columns
  ok   the feature check is not vacuous: the panel row DOES carry realised columns
  ok   the proof ran on a historical slice, not on 2026  2024
test_21 result: PASSED=9 FAILED=0
```

Nine green checks over a claim that is false in the tree they were run against.
That is the definition of false-green.

`test_22_the_sealed_artifact_passes_the_governed_contract` (lines 693-743) *does*
call `SEAL.seal_season` — but **once**. A single seal cannot detect a
between-seal difference, so it cannot catch this either, and it does not claim to.

**Nothing between `HEAD` and the suite re-runs the ten checks.** The only thing
that does is `python3.12 -m nfl.prospective.q9shadow.dryrun`, which is not invoked
by the suite and which overwrites the committed artifact when it is.

---

## The smallest valid repair — PROPOSED, NOT APPLIED

### What I deliberately did NOT propose

**Rejected: `@functools.lru_cache` on `_code_commit`.** It would make all four
seals in one process agree and turn `DETERMINISTIC` green — and it would fix
nothing, because two *separate* invocations of the proof would still disagree.
That is making the check pass rather than making the property true, which is the
move this project does not make.

**Rejected: relaxing the `DETERMINISTIC` check to skip the identity keys when the
tree is dirty** (the `test_product_orchestration.py:98-106` treatment). Defensible
for a *test*, but here it would loosen the only gate that noticed, and it would
leave the self-reference in the production sealing path, where it silently
corrupts the identity of every live forecast.

**Rejected: removing `code_version` from `ExecutionIdentity`.** Regression; see §6(a).

### The repair

Scope the dirty measurement to **source files only**, and disable git's
untracked-directory collapsing so the scoping is exact. Artifacts, ledgers,
draw files, fetched captures and other agents' scratch directories then cannot
move a forecast's identity — and the seal cannot move its own.

```diff
--- a/nfl/prospective/q9shadow/seal.py
+++ b/nfl/prospective/q9shadow/seal.py
@@ -159,7 +159,36 @@
         timespec='seconds').replace('+00:00', 'Z')
 
 
+# WHAT "DIRTY" IS ALLOWED TO MEAN, AND WHY IT IS NOT "EVERY UNCOMMITTED PATH".
+#
+# This returned `len(git status --porcelain)` over the WHOLE tree, and that
+# count is inside `code_commit`, which is inside the sealed payload, inside
+# `artifact.REQUIRED`, and inside `ExecutionIdentity.code_version`. So it moved
+# forecast_id, artifact_id, seal_payload_sha256 and identity_fingerprint.
+#
+# It also counted the seal's OWN OUTPUT. `seal_team_game` samples the identity
+# at line 356 and writes the draws at line 371, so writing one forecast added
+# an untracked path and changed the identity the NEXT forecast recorded. Two
+# seals of byte-identical inputs therefore differed -- measured: run1/ARI got
+# `+dirty[31]` and every later seal got `+dirty[32]`, because `dryrun/proof/`
+# did not exist when the first identity was sampled and did exist afterwards.
+# A forecast's identity must not be a function of that forecast having been
+# written. Same class as the `draw_artifact` exclusion below and as
+# `sealed_index._rel`, caught a third time on a third channel.
+#
+# It passed when it was written only because `git status` COLLAPSES an
+# untracked directory to one line, and the whole q9shadow subtree was
+# untracked then. Committing it is what exposed this.
+#
+# The fix is to measure the thing the field claims to name. `-- '*.py'`
+# restricts the census to source; `--untracked-files=all` stops the collapsing
+# so the pathspec actually applies inside untracked directories. A concurrent
+# edit to a .py file still moves it, which is correct: that IS a code change.
+_SOURCE_PATHSPEC = ('--', '*.py')
+
+
 def _code_commit():
     try:
         out = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=str(_REPO),
                              capture_output=True, text=True, timeout=20)
         rev = out.stdout.strip() or 'UNKNOWN'
     except (OSError, subprocess.SubprocessError):
         return 'UNKNOWN'
     try:
-        st = subprocess.run(['git', 'status', '--porcelain'], cwd=str(_REPO),
-                            capture_output=True, text=True, timeout=20)
+        st = subprocess.run(['git', 'status', '--porcelain',
+                             '--untracked-files=all', *_SOURCE_PATHSPEC],
+                            cwd=str(_REPO),
+                            capture_output=True, text=True, timeout=20)
         n = len([x for x in st.stdout.splitlines() if x.strip()])
     except (OSError, subprocess.SubprocessError):
         n = -1
     return rev + (f'+dirty[{n}]' if n else '')
```

And one line in the proof, so a future divergence names its own cause instead of
presenting two bare hashes:

```diff
--- a/nfl/prospective/q9shadow/dryrun.py
+++ b/nfl/prospective/q9shadow/dryrun.py
@@ -78,7 +78,7 @@
 WRITTEN_AT = '2026-09-12T12:00:00Z'
 
 IDENTITY_KEYS = ('artifact_id', 'spec_hash', 'draw_artifact_sha256',
-                 'draw_content_sha256', 'feature_set_hash', 'forecast_id')
+                 'draw_content_sha256', 'feature_set_hash', 'forecast_id',
+                 'code_commit')
```

`code_commit` is already a top-level key of the artifact, so `dryrun._ident`
(lines 123-128) picks it up with no further change, and a failure then prints the
differing code version beside the differing hashes.

### Verification of the repair — run, not asserted

`_code_commit` was replaced at runtime with the repaired body (file on disk
untouched) and `dryrun.run(keep=False)` was executed with the seal ledger
redirected to scratch:

```
DETERMINISTIC: PASS
n_failed 0  []
code_commit per seal: ['57d38ad…+dirty[10]', '57d38ad…+dirty[10]',
                       '57d38ad…+dirty[10]', '57d38ad…+dirty[10]']
run1 == run2: True
```

All ten checks hold, all four seals share one code version, and no other check
regressed. Independently confirmed that a non-`.py` write does not move the
scoped count while it does move the unscoped one:

```
$ git status --porcelain --untracked-files=all -- '*.py' | grep -c .
9
$ touch nfl/research/parallel_pass/ws01/_probe/zzz.json
$ git status --porcelain --untracked-files=all -- '*.py' | grep -c .
9                                   # unchanged, as required
```

### Does this change Q9's frozen identity? NO

Checked directly rather than assumed.

* `nfl/research/q9b/Q9_PROSPECTIVE_FREEZE.json` has top-level keys
  `['artifact','candidate_identity','consumption_note','decision_metrics_at_freeze',
  'fallback_counters_at_freeze','feature_schema','frozen_at_season',
  'no_future_outcome_consumed','parameter_hashes','production_interface',
  'promoted','prospective_plan','spec_version']`. **`code_commit` appears
  nowhere in it.**
* `spec_hash` (`= CAND.identity_sha256(ident)`) measured today is
  `82c8b52699bbeb00e656a3d543f995bac7034e9a89ff2a8d783e27b6fdc8422e`, byte-equal
  to the committed proof's, and byte-equal across every run above including the
  repaired one.
* `feature_set_hash` `f620eeed09d0dd6e` likewise.

**Caveat the coordinator must weigh, because it is not nothing.** The repair does
change the *value* of every future `forecast_id`, `artifact_id`,
`seal_payload_sha256` and `identity_fingerprint`, and therefore the
`Q9_PROSPECTIVE_DRYRUN_PROOF.json` hashes and any already-appended row of
`Q9_SHADOW_DRYRUN_SEAL_LEDGER.jsonl`. Those are dry-run rows stamped
`dry_run: true` / `prospective_evidence: false`, so nothing that counts as
evidence moves — but the proof artifact does have to be regenerated, and that
regeneration is a repository write, not a research act. **No live sealed forecast
exists to be invalidated** (`Q9_SHADOW_SEAL_LEDGER.jsonl` is the live ledger and
the live path is still refused at the readiness gate). If the coordinator's
"Q9 frozen identity" means the candidate spec freeze, this is safe. If it means
the stored dry-run hashes, this changes them and needs a ruling. **Flagging
rather than deciding.**

---

## Executable regression proof

Written to `nfl/research/parallel_pass/ws01/test_q9_seal_determinism.py.proposed`
— `.proposed` so `run_suite.py` does not collect it. It proves four separate
things and, importantly, **proves them in a way that the current defect makes
fail**, which is the property `test_21` lacks:

1. Two seals of identical inputs, in one process, into two output roots, agree on
   every identity key — **and the test forces a repository write between them**,
   so a self-referential identity cannot slip through.
2. The draws are byte-identical and array-identical with matching dtypes.
3. `code_commit` does not move when a non-source file is created.
4. `_code_commit()` is invariant across the seal's own side effects — checked
   directly, so a future regression names the field rather than a hash.

### It was run, and it found a bug in itself

Executed in-process against a runtime copy with the scratch directories
redirected into `ws01/` (so nothing was written outside my allowed area) and
with the repaired `_code_commit` bound:

```
43 passed, 1 failed
```

All 43 substantive checks pass under the repair: both team-games agree on
`code_commit`, `spec_hash`, `feature_set_hash`, `draw_artifact_sha256`,
`draw_content_sha256`, `forecast_id`, `artifact_id`, `seal_payload_sha256` and
`identity_fingerprint`; both `.npz` containers are byte-identical with all 8
arrays equal in value and dtype; and all `_code_commit` samples within a run are
one value.

The first draft of this test was **broken and running it is what found it**. Its
`check()` returned `None`, so every `if not check(...): return` guard fired
unconditionally — the suite printed one green line per test and exercised
nothing, reporting `6 passed, 0 failed`. That is the same false-green shape as
`test_21`, produced accidentally in the very file written to prevent it. Fixed:
`check()` now returns the verdict, and the docstring records why.

### The one remaining failure is the guard working, and it matters

```
FAIL  the perturbation produced a NEW git status line (non-vacuity: without
      this the test cannot detect the defect it exists for)
      29 -> 29 status line(s); scratch=…/nfl/research/parallel_pass/ws01/_determinism_probe
```

This is correct behaviour, and it is the most important line the test prints.
Because I was confined to `ws01/`, the scratch directory landed inside
`nfl/research/parallel_pass/`, which `git status` already collapses to one `??`
line — so creating files in it changes nothing, and **the test cannot see the
defect from there**. Confirmed by running it both ways: repaired and unrepaired
both give `43 passed, 1 failed`, identically. From that location the test is
blind.

In the file's **intended** home the guard is satisfied and the test bites.
`nfl/prospective/q9shadow/dryrun/` is partially tracked, so a new subdirectory of
it gets its own status line — directly observable on this tree right now:

```
$ git status --porcelain | grep "dryrun/"
?? nfl/prospective/q9shadow/dryrun/2024_01_ARI_BUF/
```

So `dryrun/_determinism_probe/` would add line 30, `_code_commit` would move, and
the nine identity checks per team would fail against the unrepaired code. **This
is why the non-vacuity check exists and why it must not be deleted to make the
run green.** I could not demonstrate the failing direction myself without writing
outside `ws01/`, and I did not. Whoever adopts the test should run it once
against unrepaired `seal.py` from `nfl/tests/` and confirm it fails, before
applying the repair.

---

## Evidence ceiling

State plainly what this work does **not** establish.

1. **The committed proof's specific hashes were not reproduced, and I could not
   determine why.** `forecast_id Q9SH-e3409bbd50a1ff42` / `artifact_id
   5d9816f0…` were brute-forced against a bit-exact reconstruction of the
   sealed body (self-check: the harness reproduces my own observed
   `Q9SH-60cfbaee8c263576` exactly) over 40 commits × `dirty[0..199]` — **no
   match**. The most likely reason is that `seal.py` currently carries 304
   uncommitted added lines from a concurrent agent, which change other fields of
   the artifact body. I did not attempt a `git stash`-style isolation because
   that would modify the working tree of a repository other agents are actively
   editing. So the claim "the committed hashes differ from today's *only* by
   `code_commit`" is **UNRESOLVED**. The claim that today's two runs differ only
   by `code_commit` is CONFIRMED and does not depend on it.
2. **One game, two team-games, 120 draws, season 2024.** That is the proof's own
   frozen slice, not a sample. Nothing here says anything about determinism at
   the production draw count or on other slates.
3. **The live sealing path was never exercised.** `_seal_live` is refused
   upstream at the readiness gate. Everything above is the `HISTORICAL_FRAME`
   dry-run branch. `_code_commit` is shared by both, so the defect is present in
   the live path by construction, but that is inference, not measurement.
4. **`nfl/production/run_forecast.py:104 code_commit()` is a second, independent
   implementation of the same idea** and its docstring shows it also counts the
   whole tree. I did **not** test it. If it has the same self-reference it is a
   larger problem than this one, because that path produces live boards. Out of
   WS01's scope; flagged for whoever owns it.
5. **`git status` is the wrong instrument for a content identity even after the
   repair.** A *count* of source files still collides — two different edits
   touching the same number of files produce the same marker. Replacing the count
   with a digest of `git diff HEAD -- '*.py'` plus the contents of untracked
   `.py` files is the correct end state. I did not propose it here because it is
   larger than the minimal repair and it deserves its own declared change.
6. **Concurrent-agent interference is real and was observed.** Mid-investigation,
   `Q9_PROSPECTIVE_DRYRUN_PROOF.json` changed under me from the committed `PASS`
   to a `FAIL` written by another agent's `dryrun` run, and later back again. My
   probes never wrote it: they call `dryrun.run()` directly, and only
   `dryrun.main()` writes the file. All my seals appended to a scratch ledger via
   a runtime rebind of `SEAL.DRYRUN_SEAL_LEDGER`, never to the repository's. I
   did not `git checkout` the file when I saw it changed, because reverting
   another agent's in-flight work is itself a modification and my brief forbids
   modifications.
7. **The proposed regression test was verified only in the passing direction.**
   It was run under the repair (43/1, the 1 being the non-vacuity guard) and
   without it (43/1, identically), because from inside `ws01/` — the only place
   I may write — the perturbation is swallowed by git's untracked-directory
   collapsing. So "this test fails against the unrepaired code" is **reasoned
   from the collapsing mechanism, not measured**. It must be confirmed from
   `nfl/tests/` before the repair is applied, or the test is being adopted on
   trust.
8. **One process-hygiene error, disclosed.** I ran
   `python3.12 nfl/tests/run_suite.py --help`; `run_suite.main` has no `--help`
   handling (it parses `-v` and `--only SUBSTR` positionally, lines 46-62), so it
   began a full-suite run. I stopped it within ~3 minutes. `git status` before and
   after shows no file changed as a result. The brief's prohibition on full-suite
   runs was breached by accident, not by design, and it is recorded here rather
   than omitted.

---

## Files read

```
nfl/prospective/q9shadow/seal.py                     (973 lines, read in full via targeted ranges)
nfl/prospective/q9shadow/dryrun.py                   (382 lines, read in full)
nfl/prospective/q9shadow/inputs.py                   (293 lines)
nfl/prospective/artifact.py                          (lines 62-68, 465-490)
nfl/identity/execution_identity.py                   (lines 55-112)
nfl/identity/seal.py                                 (lines 78-120)
nfl/tests/test_q9_prospective_shadow.py              (lines 1-80, 655-760)
nfl/tests/test_product_orchestration.py              (lines 85-112)
nfl/research/forensic_corrected.py                   (lines 150-200)
nfl/production/run_forecast.py                       (lines 100-120)
nfl/research/q9b/Q9_PROSPECTIVE_FREEZE.json
nfl/prospective/q9shadow/Q9_PROSPECTIVE_DRYRUN_PROOF.json  (working tree and HEAD)
nfl/tests/run_suite.py                               (lines 46-62)
```

**CODE CHANGED: NO**
