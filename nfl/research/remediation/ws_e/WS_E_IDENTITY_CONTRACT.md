# WS-E — The execution identity contract

**Defect class: SPECIFICATION REPAIR.** There was no identity contract. There was
one string, assembled in one function, that three different things were reading
as if it meant three different things. The implementation change below follows
from the contract; it is not the repair.

Repo `/home/user/nfl`, branch `claude/nfl-greenfield-architecture-stsxmk`, HEAD
`837d52f`, interpreter `python3.12` (CPython 3.12.3, numpy 2.5.3).
Written 2026-09-14.

---

## 0. The defect, in one paragraph

`nfl/prospective/q9shadow/seal.py:_code_commit()` returned the commit sha with
**a count of the lines of `git status --porcelain`** appended:
`<sha>+dirty[31]`. That count is a property of the working tree at the instant
of the call, and **the sealing path's own output files change it**. `code_commit`
sits inside the sealed body, inside `artifact_id`'s `REQUIRED` field list, and
inside `ExecutionIdentity.code_version`, so it moved `forecast_id`,
`seal_payload_sha256`, `artifact_id` and `identity_fingerprint` together. **The
identity of a forecast was a function of that forecast's own side effects.**
WS01, WS18 (finding F3) and WS19 found this independently; WS18 measured two
different execution identities for two *bit-identical* draw sets in one process,
seconds apart. Separately, WS19 read every sealed run in the tree and classified
working-tree state, interpreter version and library versions **NOT_RECOVERABLE**
from the sealed bytes.

Measured on this checkout before the repair:

| call | value |
|---|---|
| before writing anything | `837d52f…+dirty[30]` |
| after one output directory | `837d52f…+dirty[31]` |
| after a second output directory | `837d52f…+dirty[32]` |
| after deleting both | `837d52f…+dirty[30]` |

Nothing about the forecast changed in any of those four calls.

**A count has a second failure, in the opposite direction, and it is worse.** A
count does not identify anything. Any two working trees with the same *number* of
dirty paths produce the same string, so a tree with an edited `layers.py` and a
tree with an unrelated scratch note are indistinguishable in the sealed bytes.
The artifact said *that* the tree was dirty and never said *how*.

---

## 1. The contract — six identities, separated

Each row says what the identity is, what answers it, where it is stored, and
whether it is inside the run fingerprint.

| | Identity | What it is | Value | In `identity_fingerprint`? | In `artifact_id`? |
|---|---|---|---|---|---|
| **A** | Committed source | Which committed snapshot of the repository | `git rev-parse HEAD`, 40 hex | **yes**, via `code_version` | **yes**, via `code_commit` |
| **B** | Dirty source **content** | What the working tree holds that the commit does not, **by content** | sha256 over the canonical list of in-scope dirty source files, each with its own sha256, **plus the scope declaration itself** | **yes**, via `code_version` | **yes**, via `code_commit` |
| **C** | Runtime / environment | Interpreter and numeric library versions that can change a number | `implementation=CPython+python_version=3.12.3+numpy_version=2.5.3` | **yes**, via `interpreter` | **no** — see §6 |
| **D** | Generated artifact state | A run's own outputs: sealed dirs, proofs, ledgers, npz, derived caches | recorded where it is written; **not an identity input anywhere** | **no, by construction** | **no** |
| **E** | Predictive candidate | The mechanism, features, coefficients and frozen parameters | `spec_sha256` = `candidate.identity_sha256`, containing `module_source_sha16` | **yes**, via `spec_sha256` | **yes**, via `spec_hash` |
| **F** | Execution / run | The whole run: everything above plus the consumed input hashes | `ExecutionIdentity.fingerprint()` → `NFLFP-…`; `forecast_id`; `artifact_id` | — | — |

### The invariant

> **A run must not change its own identity by writing its own outputs.**
>
> F = f(A, B, C, E, consumed inputs)   and   **∂F/∂D = 0**

D is excluded from A, B and C by a **declared scope**, which is what makes the
partial derivative zero rather than merely small.

### A and B as one string, in one format

```
<40-hex commit> + "+src1[" + <first 16 hex of the B digest> + "]"
```

One format whether or not the tree is dirty. A string that reads `<sha>` when
clean and `<sha>+something` when dirty invites a parser with two branches, and
the branch nobody exercises is the one that is wrong. A clean tree is not absent
from the format; it is the digest of the empty entry list, computed rather than
typed in — `44aa01d03783de18…` under the current scope declaration.

---

## 2. What counts as source, and why the scope is inside the digest

`SOURCE_ROOTS` × `SOURCE_SUFFIXES` − `EXCLUDED_SUBTREES`, declared in
`nfl/identity/code_identity.py`:

* **Roots**: `nfl/production`, `nfl/prospective`, `nfl/identity`, `nfl/product`,
  `nfl/schema`, `nfl/tools`, `sportsplatform`.
* **Suffixes**: `.py` only. A `.json` written next to a module is an artifact,
  not source. This single rule is what keeps every run product out of B even when
  it lands inside a source root.
* **Excluded subtrees**: `nfl/prospective/q9shadow/dryrun`,
  `…/q9shadow/sealed`, `nfl/production/runs`, `nfl/derived`, `nfl/research`,
  `nfl/vintage`. The suffix rule already covers today's contents; the list is the
  belt to that braces, and it is what stops a future generated `.py` — a
  scratch script beside a proof — from silently re-entering the identity.

**The scope declaration is hashed into the digest.** A later widening or
narrowing of the scope therefore cannot produce a digest that aliases to one
computed under the old rule. Changing what identity *means* changes the identity.

### `-uall` is load-bearing

`git status --porcelain` **collapses an untracked directory to one line**. A new
`.py` inside an already-untracked directory would be invisible — silently, and
exactly for new code. The resolver uses `--porcelain -z -uall`, which enumerates
every file.

This is also why the **pre-repair dry-run proof's `DETERMINISTIC` check passed
while the defect was live**: the proof writes into
`nfl/prospective/q9shadow/dryrun/proof/`, and the collapsing meant the count
often did not move between the two seals. The check was not wrong; it was inert
against this defect, for a reason that had nothing to do with what it was
testing. That is worth recording next to the regenerated proof.

### `nfl/research/**` is out of scope — the decision and the why

Research modules are **not** uniformly irrelevant. `nfl.research.q9.hurdle`,
`nfl.research.q9b.family` and `nfl.research.q9b.production_parity` are causal for
the Q9 candidate. They are **already hashed individually and by content** into
`module_source_sha16`, which is inside `spec_sha256` (**E**), which is inside the
fingerprint (**F**). *A change to a causal research module already moves the run
identity — through E, not through B.*

Putting all of `nfl/research/**` into B would instead add several thousand
non-causal files — write-ups, one-off scripts, every workstream's notes — whose
churn would move every run id for no causal reason. **That is the same defect
class as the dirty count, arriving more slowly.** So: out of scope, by decision,
stated here rather than left to be inferred from a glob.

`nfl/tests/**` is out of scope on the same reasoning: a test cannot change a
forecast's numbers. A practical consequence worth naming — **WS-N's test edits do
not move any run id.**

---

## 3. The ruling on dirty state

**Three options were available. The failure mode of each:**

**(1) Dirty state alters execution identity.**
*Failure mode:* if the scope is drawn wrongly, the identity becomes
self-referential — which is precisely the defect being repaired. Scope, not
hashing, is the whole risk. A second cost: the identity moves whenever anyone
edits in-scope source, so two runs from two working sessions are formally
incomparable even when the edit was a comment. That is correct but noisy.

**(2) Sealing is blocked while the tree is dirty.**
*Failure mode:* **fatal here, and not hypothetically.** This checkout is
permanently dirty — 29 pre-existing entries at Wave 0, 45 today, including
uncommitted q9shadow work dated 2026-09-12 that is not this pass's to commit. A
gate that refuses every seal is a gate that gets disabled or routed around, which
is strictly worse than no gate because it leaves a control that everyone believes
is running. It also conflates two different things: *uncommitted* and
*unidentified*. Uncommitted source that is content-hashed is fully identified.

**(3) Dirty state is recorded separately, outside the identity.**
*Failure mode:* **this is the MLB M0 failure mode**, and `execution_identity.py`'s
own docstring already says so for inputs: "Recording a sha256 next to a run is
the easy half and does not help. The hash has to be inside the identity that the
fingerprint is computed over." A value recorded *beside* the identity cannot make
the fingerprint move when the thing changes. Two runs from materially different
source would share a fingerprint, and the recorded block would be the only place
that disagreed. For the one thing that most directly changes a number — the
source — that is unacceptable.

### Ruling: **(1), scoped — with (3) alongside for the material, and (2) narrowed to one unresolvable case.**

* **(1) is adopted.** The dirty **source-content** digest is inside
  `code_version`, inside the fingerprint. Its failure mode is managed by making
  the scope an explicit, versioned, hashed declaration that a test holds — not by
  trusting whoever writes the next glob.
* **(3) is adopted *additionally*, not instead.** The per-file material — every
  in-scope dirty path with its own sha256 and byte count, the scope rule, the
  full runtime block — is persisted into the sealed artifact as `code_identity`.
  A digest nobody can reconstruct is a number you can compare and cannot audit,
  and WS19's finding was precisely that the sealed bytes could not answer the
  question at all. The digest is the gate; the material is the audit.

  **But (3) has a boundary, and the first version of this repair crossed it.**
  The block originally kept the demoted whole-tree count as
  `n_dirty_tree_entries_recorded_not_hashed`, on the reasoning that a value
  outside the digest, outside `code_version` and outside `ExecutionIdentity` is
  outside the identity. **The regenerated Q9 dry-run proof failed and was
  right to.** The block is written into the artifact as `code_identity`, and the
  artifact minus two keys *is* the sealed payload — so the count reached
  `seal_payload_sha256` and `forecast_id`. Measured, not argued: run 1 wrote its
  outputs, run 2 sealed ARI as `Q9SH-440b173d2f5a2556` where run 1 had sealed
  `Q9SH-67ccb0832ee54741`, for bit-identical draws, while `artifact_id` and
  `identity_fingerprint` stayed equal. The generalised rule is therefore
  stronger than "keep it out of the digest":

  > **Nothing that reads generated artifact state (D) may enter the sealed
  > body** — whether or not it is hashed into the fingerprint — because the body
  > is hashed into an identity of its own.

  The count survives as `Outcome` evidence (`n_dirty_tree_entries_observed`),
  where it is a diagnostic and not a sealed byte. Section A of the test now
  compares the **whole canonicalised block**, not just `code_version`; that
  check was verified load-bearing by re-adding the withdrawn field in memory and
  confirming it fails.
* **(2) is adopted only where the identity is genuinely unknowable.** If `git`
  cannot be run, A and B do not exist, and the old behaviour — substituting the
  literal string `UNKNOWN` and sealing anyway — produced an artifact asserting an
  identity it did not have. That now refuses:
  `CODE_IDENTITY_NO_COMMIT` / `CODE_IDENTITY_NO_WORKTREE_STATE`, both
  `BLOCKED(cause=ENVIRONMENT)`, surfaced by the seal path as
  `Q9_SHADOW_CODE_IDENTITY_UNRESOLVED`. It does not trigger in this checkout.

**The demoted count is recorded as a diagnostic only** — in the resolver's
`Outcome` evidence as `n_dirty_tree_entries_observed`, never in the sealed
block. See the boundary case above for why that distinction had to be made the
hard way.

---

## 4. Runtime identity (C) — what is hashed and what is only recorded

**Hashed** (`RUNTIME_HASHED_KEYS`): `implementation`, `python_version`,
`numpy_version`. These can change a number and a rerun can hold them fixed. The
interpreter is in because the sibling MLB engine does not even *parse* on 3.11 —
that is how cheap an interpreter difference can be. numpy is in because the draws
come out of `numpy.random` and its reductions.

**Recorded, not hashed**, each for a stated reason:

* `platform` — hashing it makes **every machine a different identity by
  construction**, which would *define away* the cross-machine reproduction
  question WS18 calls its largest evidence gap. You cannot demonstrate two
  machines agreeing if agreement is impossible by definition. Recorded so a
  machine difference is visible; not hashed so it stays a question.
* `thread_env` (`OMP_NUM_THREADS`, `MKL_NUM_THREADS`, `OPENBLAS_NUM_THREADS`,
  …) — thread count can change BLAS reduction order and therefore the last bits
  of a float. **Plausible and not measured here.** Hashing an unmeasured cause
  puts a silent constant inside the identity. Promote it if and when a measured
  draw difference is attributed to it; not before.

`ExecutionIdentity.interpreter` already existed and held `python3.12` — a value
so coarse that WS19 classified interpreter and library versions NOT_RECOVERABLE
on every run it read. No schema change was needed for C; the field was
under-populated, not absent.

---

## 5. What changed, file by file and hunk by hunk

`nfl/prospective/q9shadow/seal.py` **was already dirty** with pre-existing
uncommitted work dated 2026-09-12 (`pre_existing_diff_sha256`
`9ced29bcb739140da7540095da086e2816a8e13eb2c7e40d4e996f893625ba76`, 7 files,
1272 insertions, 68 deletions). **None of that is WS-E's and none of it was
reverted, stashed or tidied.** WS-E's hunks in that file are these four and no
others:

| Hunk | Location | Change |
|---|---|---|
| **WS-E-1** | `@@ -55,7 +55,6 @@ import gzip` | removed `import subprocess`, which this file no longer uses |
| **WS-E-2** | `@@ -67,13 +66,16 @@ if str(_REPO) not in sys.path:` | added **one line**, `from nfl.identity import code_identity as CI`. **This hunk is shared**: the `… import complete as COMPLETE` and `… import timebasis as TB` lines in it are pre-existing 2026-09-12 work, not WS-E's |
| **WS-E-3** | `@@ -144,20 +159,39 @@ def _now():` | `_code_commit()` **deleted**, replaced by `_code_identity() -> Outcome` delegating to `code_identity.code_identity()`. The withdrawn implementation is quoted verbatim in the comment above it with the four measured values |
| **WS-E-4** | `@@ -321,11 +369,28 @@ def seal_team_game(...)` | resolve the identity first and refuse on non-PASS (`Q9_SHADOW_CODE_IDENTITY_UNRESOLVED`); `code_version=ci['code_version']`, `interpreter=ci['runtime_token']` |
| **WS-E-5** | `@@ -366,6 +441,13 @@ def seal_team_game(...)` | in the `art` dict immediately after `'code_commit'`, added `'code_identity': ci` — the digest material |

**Those five hunks and no others.** `git diff` on this file shows thirteen
hunks; the other eight are pre-existing 2026-09-12 work — including the
`MODEL_ARM` B→A correction, `GOVERNED_APPEARANCE_INTERFACE`, the completeness
matrix, the time-basis block and the `seal_path` block — and none of it was
touched, reverted or tidied. Every WS-E line is identifiable by the literal
string `WS-E`, `code_identity`, or the removal of `import subprocess`. **WS-E-2
is the one hunk with mixed authorship**, and only its `code_identity as CI` line
is WS-E's.

Other files:

| File | Change |
|---|---|
| `nfl/identity/code_identity.py` | **NEW.** The contract: scope declaration, resolver, digest, runtime block, refusals, `RESIDUAL_GAPS` |
| `nfl/identity/execution_identity.py` | docstring section naming the contract; import of `KEYS_ON_COUNT_MARKER`; `validate()` now refuses a `+dirty[` `code_version` by name (`IDENTITY_CODE_VERSION_KEYS_ON_COUNT`) |
| `nfl/tests/test_execution_identity.py` | **NEW.** 13 test functions, 51 checks |
| `nfl/prospective/q9shadow/Q9_PROSPECTIVE_DRYRUN_PROOF.json` | regenerated (see §7) |
| `nfl/prospective/q9shadow/superseded/Q9_PROSPECTIVE_DRYRUN_PROOF.da58aec.json` | **NEW.** The prior proof preserved byte-for-byte |
| `nfl/prospective/q9shadow/superseded/SUPERSESSION.json` | **NEW.** Why the identity contract changed, with both hashes |

Nothing under `nfl/production/`, `nfl/product/`, `nfl/tests/run_suite.py`,
`test_q9_prospective_shadow.py`, `test_q9b_model_family.py`,
`test_q9_live_feature_builder.py`, `run_forecast.py`, `football_engine.py`,
`artifact.py`, `readiness.py`, `depth_vintage.py`, `roster_status.py`,
`board.py` or — above all — `nfl/production/nonqb/layers.py` was touched.

---

## 6. Proof

`python3.12 nfl/tests/run_suite.py --only test_execution_identity` →
**modules 1, test functions 13, checks 51, FAILING CHECKS 0, RAISED 0.**
`--only test_seal_ordering` (the other consumer of `nfl/identity/**`) →
**97 checks, 0 failing.**

| Required property | Section | Result |
|---|---|---|
| identical source + inputs + RNG → identical run identity | B, B2 | PASS — and each of `code_version`, `interpreter`, `seed`, input sha256 is shown to move it when changed |
| writing output files during execution **cannot** alter later identity | A | PASS — two generated output directories created and removed around the resolver; identity constant throughout |
| modifying one relevant production **source** byte **does** change identity | C | PASS — and changing a single byte of that file changes it *again* |
| modifying only a **generated artifact** does **not** | C2 | PASS — for every entry of `GENERATED_SUBTREES`, including the nastiest case: a `.py` written *inside* a generated subtree |
| unrelated non-production research files do **not** | C3 | PASS — and §2 states why this is a declared decision, with the complement shown: a *causal* research module still reaches F through E |
| the withdrawn form is refused | D | PASS — `IDENTITY_CODE_VERSION_KEYS_ON_COUNT` |
| the material is auditable | D2 | PASS — `source_scope_sha256` recomputes from the stored entries alone, and every stored per-file sha256 re-hashes |
| **Q9 predictive identity unchanged** | E | PASS — see §8 |
| the tree is restored | E2 | PASS — no probe path survives |

**Section A2 is the load-bearing half, and without it the rest is vacuous.**
Owner Directive 3 §8: a guard is not demonstrated because compliant data passes
it. So the test **reconstructs the withdrawn `_code_commit()` verbatim** and
**requires it to fail** the same scenario the repair passes. If the withdrawn
form ever stops moving under that scenario, section A2 fails and says the
scenario has gone inert — rather than quietly reporting a green.

The scenario uses **two separate top-level directories** on purpose, because git
collapses an untracked directory to one porcelain line: a scenario that wrote two
files into *one* directory would not move the old count and would have shown a
false green against the withdrawn implementation.

### A consequence worth stating: the proof needs a quiescent tree

`code_version` now moves when **in-scope source** changes — which is the point,
and which has a cost in a checkout twenty-four workstreams are writing to at
once. Measured during this pass, the in-scope dirty source count went
9 → 20 in under an hour as other workstreams edited `nfl/production/**` and
`nfl/product/**`. If a source file changes **between** the two seals of the
dry-run proof, `DETERMINISTIC` fails — correctly, because the two runs really
did execute different source, but for a reason that is a property of the shared
checkout rather than of the sealing path.

**How to tell the two apart from the proof output alone**, which is the part
worth carrying forward:

| what differs between run1 and run2 | diagnosis |
|---|---|
| `artifact_id` **and** `identity_fingerprint` **and** `forecast_id` | in-scope **source** changed between the seals. Re-run on a quiescent tree |
| `forecast_id` / `seal_payload_sha256` **only** | something in the sealed **body** reads state outside the identity — the failure mode of §3's boundary case |
| the draw hashes (`draw_content_sha256`, `draw_artifact_sha256`) | a genuine predictive nondeterminism. None has ever been observed |

### Coverage this repair does not have

* **C reaches `identity_fingerprint` and `forecast_id`, but not `artifact_id`.**
  `artifact_id` hashes `artifact.REQUIRED`, which carries `code_commit` (A+B) and
  `spec_hash` (E) but has no runtime field. `nfl/prospective/artifact.py` is
  WS-B's file and `REQUIRED` is not WS-E's to change. Stated, not worked around.
* **One repository, one machine, one interpreter.** Cross-machine reproduction is
  untestable from here — WS18's largest gap, unchanged by this repair.
* **The four `RESIDUAL_GAPS`** declared in `code_identity.py`: research modules
  the sealing path imports that are not among the four in `module_source_sha16`
  (`nfl.research.q7.panel`, `nfl.research.q8.audit` are the live examples) are in
  neither B nor E; non-`.py` frozen parameter files under a source root are not
  in B (for Q9 they are covered by E; WS18's F1 is the general remedy); thread
  environment is recorded and not hashed; staged and unstaged edits of identical
  bytes are one identity, deliberately.

---

## 7. The dry-run proof

The repair changes `code_commit`, which is inside the sealed body, so every
`forecast_id`, `seal_payload_sha256`, `artifact_id` and `identity_fingerprint` in
`Q9_PROSPECTIVE_DRYRUN_PROOF.json` moves. That is the repair working, not a
regression — those ids were previously a function of the working tree's file
count.

**History was not rewritten.** The prior proof is preserved byte-for-byte at
`nfl/prospective/q9shadow/superseded/Q9_PROSPECTIVE_DRYRUN_PROOF.da58aec.json`
(sha256 `4a11c0726b0588fbf2d278bbe86ef40f2e8dc0fa50c7164b2e3178a40eb2350c`,
committed at `da58aec`, 2026-09-12), with
`superseded/SUPERSESSION.json` recording why the identity contract changed, which
fields moved, which did not, and both hashes. The live proof was **regenerated**
by re-running `python3.12 -m nfl.prospective.q9shadow.dryrun`, not edited. New
sha256 `3b5c098c4b03cfbb4d305b16e1fbf022f0a8e55d0968bd4501b60fde9797f7cb`.

**Result: `DRY_RUN_PROOF_HOLDS`, 10/10, `DETERMINISTIC` PASS, run1 == run2 on
every compared hash.**

| | ARI old → new | BUF old → new |
|---|---|---|
| `forecast_id` | `Q9SH-e3409bbd50a1ff42` → `Q9SH-5a1c4bda73424345` | `Q9SH-f8df992212a4d4d6` → `Q9SH-7237c5c5552c8f39` |
| `artifact_id` | `5d9816f0…` → `61dccfa1…` | `bc562ce2…` → `a06861c5…` |
| `identity_fingerprint` | `NFLFP-06081ed8e38ddd22` → `NFLFP-94ff8f28ef0f47fc` | same pair |
| `spec_hash` | `82c8b526…` **unchanged** | **unchanged** |
| `draw_content_sha256` | `8c195431…` **unchanged** | `9ff7c5e6…` **unchanged** |
| `draw_artifact_sha256` | `b370646b…` **unchanged** | `58b74c59…` **unchanged** |
| `feature_set_hash` | `f620eeed09d0dd6e` **unchanged** | **unchanged** |

Every hash that moved is a **run** identity. Every hash that stayed is a
**predictive** identity. That split is the whole claim of this repair, and it is
the measured result rather than an intention.

**One side effect, recorded rather than tidied.** `Q9_SHADOW_DRYRUN_SEAL_LEDGER.jsonl`
is append-only and the proof seals four forecasts, so regenerating it appended
rows — 12 committed rows to 25 today, part from the pre-existing 2026-09-12 work
and part from these runs. No row was edited or removed. That file is one of the
seven pre-existing modified files in `WAVE0_BASELINE`; WS-E **appended to it by
running the generator** and did not edit it.

---

## 8. Identity impact — what moved and what did not

**MOVED** (run identity, by design):
`code_commit`, `ExecutionIdentity.code_version`, `ExecutionIdentity.interpreter`,
`identity_fingerprint`, `forecast_id`, `seal_payload_sha256`, `seal_sha256`,
`artifact_id`, and the corresponding rows regenerated in
`Q9_PROSPECTIVE_DRYRUN_PROOF.json`.

**NOT MOVED** (predictive identity — checked, not assumed; section E of the test
asserts each against the Wave 0 baseline):

| Element | Baseline | Now |
|---|---|---|
| `mechanism_spec_version` | `q9-target-hurdle-1` | unchanged |
| `nfl.research.q9.hurdle` | `bb51133641338547` | unchanged |
| `nfl.research.q9b.family` | `5b411b4f00e28e6f` | unchanged |
| `nfl.research.q9b.production_parity` | `1f320b1ee3170e64` | unchanged |
| `nfl.production.nonqb.layers` | `481f005f682cd721` | unchanged |
| `Q9_PROSPECTIVE_FREEZE.json` sha16 | `a28e8832430b1420` | unchanged |
| `spec_hash` / `draw_artifact_sha256` / `draw_content_sha256` / `feature_set_hash` | — | unchanged |

**No draw changed.** Nothing in this repair is on a path that produces a number.

---

## 9. What this implies for other workstreams — not done here

`nfl/production/run_forecast.py:104-127` carries **the same defect**, in its own
`code_commit()`, feeding its own `execution_identity`. That file is **WS-D's** and
was not touched. `ExecutionIdentity.validate()` now refuses the count-keyed form,
so if `run_forecast` adopts this class it will be told, by name, rather than
silently inheriting the defect. The contract module is importable as
`nfl.identity.code_identity` and is repository-wide, not Q9-specific — it was put
in `nfl/identity/` rather than in `q9shadow/` for exactly that reason.
