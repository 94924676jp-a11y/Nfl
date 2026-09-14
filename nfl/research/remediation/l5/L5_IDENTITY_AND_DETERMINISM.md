# L5 — identity sweep and the determinism proof harness

Branch `claude/nfl-greenfield-architecture-stsxmk`, HEAD `9c3c29a`, python3.12
(CPython 3.12.3, numpy 2.5.3). Written 2026-09-14, kickoff `2026_01_DEN_KC`
2026-09-15T00:15:00Z.

Two jobs. Job 1 is an audit and its answer is **the requirement is met**. Job 2
is a tool, `nfl/tools/determinism_proof.py`, which ran green on a committed
historical game and, separately and on its way to green, correctly classified a
live in-flight source edit as cause (1) rather than raising a determinism alarm.

---

## Job 1 — is there a third legacy `+dirty[n]` implementation?

**No. The owner's requirement — "there must not be a second legacy `+dirty[n]`
implementation remaining in a live run path" — is MET.**

Stated precisely, because the sentence has two readings and both are now true:

* there is **no** count-keyed implementation on any live run path;
* there is **exactly one** implementation of code identity anywhere in the
  repository's declared SOURCE scope, `nfl/identity/code_identity.py`, and it is
  content-keyed.

### How the sweep was done

Four passes, because one search shape would have missed at least one of these:

1. the literal marker `+dirty[` across `*.py`, `*.md`, `*.json`;
2. `git status --porcelain` in any `.py`;
3. `rev-parse` in any `.py`, and every `def` producing a commit-like string;
4. every identity/fingerprint/`seal_payload` producer, read by hand, plus every
   `glob`/`iterdir`/`listdir` in `nfl/production`, `nfl/prospective`,
   `nfl/product`, `nfl/identity`, `nfl/tools`, `sportsplatform`, looking for the
   subtler shape — an identity field reading **generated** state rather than
   content.

### Every hit, with file:line and classification

**Producers — the only two, both repaired**

| file:line | what it is | path | state |
|---|---|---|---|
| `nfl/identity/code_identity.py:401` `code_version()` | the one implementation. Emits `<40-hex>+src1[<16 hex>]` in one format clean or dirty | **live** | content-keyed, correct |
| `nfl/production/run_forecast.py:167` `code_commit()` | delegates to `CI.code_identity()`; returns `UNRESOLVED[<code>]` on refusal rather than a fabricated string | **live** | repaired |
| `nfl/prospective/q9shadow/seal.py:192` `_code_identity()` | delegates to `CI.code_identity()` | **live** | repaired |

No other function in the repository produces a code-version string. Verified
both by reading and, now, by a standing test (below).

**Refusal machinery — the marker named so it can be refused**

| file:line | note |
|---|---|
| `nfl/identity/code_identity.py:414` | `KEYS_ON_COUNT_MARKER = '+dirty['` — a declaration, not a construction |
| `nfl/identity/code_identity.py:417` | `refuses_count_keyed()` |
| `nfl/identity/execution_identity.py:121` | `validate()` refuses `IDENTITY_CODE_VERSION_KEYS_ON_COUNT` |

**Prose recording the withdrawn implementation — correct, leave alone**

`nfl/identity/code_identity.py:19-32`, `nfl/production/run_forecast.py:172-186`,
`nfl/prospective/q9shadow/seal.py:163-190`,
`nfl/tests/test_execution_identity.py:8`,
`nfl/tests/test_q9_prospective_shadow.py:696-745`,
`nfl/research/remediation/ws_e/WS_E_IDENTITY_CONTRACT.md`,
`nfl/research/remediation/ws_n/WS_N_EXECUTABLE_PROOFS.md`. Each writes the
string out to explain what it replaced. Deleting the prose to satisfy a text
search would delete the only place the defect is explained — this matters
concretely, and is why the sweep test below reads the AST rather than the text.

**Readers of legacy artifacts — research path, not defects**

| file:line | classification |
|---|---|
| `nfl/research/forensic_corrected.py:65,159-206` | **research**, read-only. Splits the stored `code_commit` on `+` to compare the committed base, and records the differing dirty counts (33 vs 40) as a named unresolved caveat rather than asserting them away. Correct handling of a legacy artifact. |
| ~40 stored artifacts under `nfl/research/**` carrying `"code_commit": "<sha>+dirty[n]"` | **dead**. Historical sealed records. They are evidence of what was believed then and must not be rewritten. |

**Stale claims that the withdrawn contract is current — patches attached**

| file:line | classification | why it matters |
|---|---|---|
| `nfl/tests/test_product_orchestration.py:111-128` | **test path**, live and wrong | See patch A. It calls `git status --porcelain` itself, gates the run-id comparison on the whole tree being clean, and — because the tree is never clean — records `check(..., True)` for a comparison that never ran. A PASS for work not done, inside the determinism proof. |
| `NFL_BOARD_AUTOMATION.md:78` | **documentation**, stale | "The run id embeds a `+dirty[n]` counter of uncommitted files." It no longer does. Documentation follows code. |
| `NFL_V1_PRODUCT_PATH_CLOSURE.md:230`, `NFL_V1_FREEZE_RETURN.md:99` | **documentation**, historical | Dated write-ups describing runs made under the old contract. Accurate about their own runs; leave. |

### The subtle shape — a sealed-body field reading generated state

The rule that made the first repair incomplete: *nothing that reads generated
artifact state may enter the sealed body, hashed or not,* because the artifact
minus two keys **is** the sealed payload. I looked for recurrences of that shape
rather than for the string, and found none. What I checked and what it says:

* `nfl/identity/seal.py:145-155` — the `Seal` carries `payload_sha256`, the
  identity and the consumed partition ids. No path, no count, no clock beyond
  the two declared ones.
* `nfl/prospective/q9shadow/seal.py:604-612` — `SEAL_BODY_EXCLUDED =
  ('draw_artifact', 'draw_artifact_sha256')`; the output **location** is
  excluded and the draws are identified by content. This is the earlier fix of
  exactly this shape and it holds.
* `nfl/prospective/artifact.py:544` `artifact_id()` — hashes `REQUIRED` only.
  `draw_artifact` is in `OPTIONAL` and therefore outside the id.
* `nfl/production/run_forecast.py:90` `execution_identity()` — an explicit
  payload: season, week, game_id, arm, written_at, seed, code_commit,
  model_configuration, source hashes. No output path reaches it.
* `nfl/production/draws_artifact.py:240` `content_digest()` — arrays and
  `row_ids` only. `run_id` is in the manifest but outside the digest, which is
  what makes the digest a legitimate cross-run comparator.
* `nfl/product/store.py:49` `input_fingerprint()`, `nfl/research/warm_session.py:60`
  and `nfl/production/nonqb/appearance_r7.py:120` `_dependency_fingerprint()` —
  all content hashes over declared **inputs**. No counts, no directory listings.
* Every `glob`/`iterdir` in the live packages enumerates **capture vintages**
  (`nfl/vintage`, `nfl_vintage/raw`) or renders a board. None feeds an identity.

One finding worth naming: **this class of defect recurred in my own tool and the
sweep caught it.** The first draft of `determinism_proof.py` shelled out to
`git status --porcelain` and assembled `f'{head}+dirty[{n}]'` so the proof could
print the withdrawn identity verbatim. That is a third implementation, in
`nfl/tools`, which is inside the identity's SOURCE scope, where the next person
needing a code version would find it. It was removed rather than exempted: the
harness now takes the count from `code_identity()`'s own Outcome evidence
(`n_dirty_tree_entries_observed`) and never assembles the string. **No module in
the repository outside `nfl/identity/` now calls git for working-tree state.**

### The audit is now a standing test

An audit is a statement about a moment. Two sweep tests make it durable, in
`nfl/tests/test_determinism_proof.py` (a file I own, so it is live now; it would
sit just as well next to `test_execution_identity.py` and I have no objection to
it being moved there):

* `test_v_only_the_identity_module_reads_working_tree_state` — no `.py` in the
  declared SOURCE scope outside `nfl/identity/` **calls** git for working-tree
  state. Both the positive and negative detectors are asserted, so the test
  cannot pass by never firing.
* `test_w_nothing_in_scope_constructs_the_count_keyed_identity` — no in-scope
  module **constructs** `+dirty[`, detected on the AST across f-strings, `+`
  concatenation, `%` and `.format()`, so that *declaring* the marker is
  distinguishable from *building* it. Without that distinction the rule would
  have to exempt `code_identity.py` by name, and then it would not be checking
  the identity module.

Both rules are scoped by subtree, not by a list of exempted filenames. There is
deliberately no allow-list: an exemption list is how a silent skip comes back
wearing a permit.

**What the sweep cannot decide.** Whether a given field reads generated state
into a sealed body is not statically decidable. That part of Job 1 was done by
reading, is recorded above, and should be re-read whenever a new field is added
to a sealed body.

---

## Job 2 — the determinism proof harness

`nfl/tools/determinism_proof.py`, with `nfl/tests/test_determinism_proof.py`
(25 test functions, 58 checks, SUITE PASS).

### Interface

```
python3.12 nfl/tools/determinism_proof.py \
    --game-id 2026_01_DEN_KC --season 2026 --week 1 \
    --cutoff <written_at, e.g. 2026-09-14T23:30:00Z> \
    --out-root-a <dir A> --out-root-b <dir B> \
    --draws 1000 --seed 20260908 \
    --model-configuration V1_CANDIDATE \
    [--input-manifest <frozen manifest json>] \
    --proof-out nfl/research/remediation/l5/PROOF_DEN_KC.json
```

`--write-manifest <path>` resolves and writes the frozen input manifest at the
cutoff and exits without running anything, so the manifest can be pinned before
the two runs and passed back in with `--input-manifest`.

**PASS requires both halves**: every equality green **and** an empty finding
list. Six green equalities with an open `CAUSE_1` is a coincidence, not a
property, and it happened twice on 2026-09-14. Exit code 0 on PASS, 1 on FAIL, and it prints the six properties, the
counterfactual flag, the classification and `proof_body_sha256`.

Importable as `prove(...) -> Outcome` for use from another tool.

### What it does

* Runs the forecast **twice** through `make_board.build_one`, into two separate
  **top-level** output roots. It **refuses** (`DP_OUTPUT_ROOTS_NOT_SEPARATE`,
  BLOCKED/GOVERNANCE) if the roots are the same directory or one contains the
  other — WS-E's point that a single root shows a false green.
* Freezes the input manifest once, before run A, and asserts both runs against
  **it** as well as against each other. Two runs that agree with each other and
  disagree with the manifest consumed the same wrong bytes; that is reported
  separately from determinism.
* Compares every array **bit-for-bit** — the float64 bytes, not `==` and not
  `np.array_equal`, because those call NaN ≠ NaN and −0.0 == 0.0, which are
  wrong in opposite directions. Rows are addressed by
  `manifest['layers'][<layer>]['row_ids']` with the manifest's own `row_axis`
  (`gsis_id`; `team` for `team_volume`), **never positionally**. A reordered row
  set produces no array difference and is still reported; a row present in only
  one run is a row-set defect naming the id. Zero cells compared is **not** a
  pass.
* Compares the identity quintuple: predictive arrays · candidate identity
  (`spec_hash`, `feature_set_hash`, components, freeze identity) · execution
  identity (`execution_identity`, `run_id`, `code_commit`,
  `code_identity.source_scope_sha256`, `runtime_token`) · model configuration ·
  input hashes.
* Proves `dF/dD = 0`: identity A+B+C is observed at three points —
  `before_run_a`, `between_runs`, `after_run_b` — and run B computes its identity
  with run A's **entire output tree already on disk**. The claim itself reads the
  identity-resolution interval (`before_run_a` → `between_runs`), because
  `run_forecast.build` resolves its identity once before writing anything; a
  change landing *during* run B is carried as a separate field
  (`source_scope_stable_through_run_b`), reported and verdict-affecting, but it
  does not turn the dF/dD line red — a reader seeing "generated output altered
  the second run's identity" would be reading a sentence that is false. It also reports whether
  the withdrawn count **would** have moved across those points
  (`counterfactual_discriminating`), so a green on a tree that happened not to
  move is reported as the weaker demonstration it is rather than claimed as the
  stronger one.
* Emits a hashable proof artifact. The artifact has the same two-part shape as
  `q9shadow/seal.py`: `PROOF_BODY_EXCLUDED` names every key that reads generated
  state, the clock or the machine, and `proof_body_sha256` is computed over the
  artifact **without** them, so the proof's own hash is reproducible.
  `proof_signature = sha256(proof_body_sha256 + ':' + proof_tool_sha256)`, and
  `proof_tool_sha256` is this module's own bytes, so the proof names the code
  that produced it. `write_proof` refuses to overwrite a different proof at the
  same path.

### Failure classification

Every failure is classified against the identity contract, first match winning,
because an earlier cause explains every later symptom:

| cause | meaning |
|---|---|
| `CAUSE_0_INPUTS_NOT_FROZEN` | the information set moved; the premise failed and nothing downstream is evidence |
| `CAUSE_1_IN_SCOPE_SOURCE_CHANGED` | a file in the declared SOURCE scope changed between the runs — **the expected cause tonight**. Reports the per-point scope digests and names the files |
| `CAUSE_2_SEALED_BODY_READS_D` | arrays identical, an identity moved anyway, source and inputs constant |
| `CAUSE_3_PREDICTIVE_NONDETERMINISM` | everything else constant and the draws differ. Never observed in this repository |

Plus `UNCLASSIFIED`, named rather than dropped, because "no cause found" reads
as a pass to a skim.

`test_l_cause_1_OUTRANKS_cause_3` is the test worth reading: source moved **and**
the draws differ, both true, and the harness must report the source change. A
confident wrong answer about determinism at 00:10Z is worse than no answer.

### Results on the historical game

`2026_01_SF_LA`, season 2026 week 1, cutoff `2026-09-10T21:18:56Z`, 40 draws,
two top-level roots `dp_proof_A/` and `dp_proof_B/` at the repository root (both
removed afterwards). A committed historical game deliberately, so the harness's
own correctness does not depend on tonight's capture.

Ten executions were taken across the afternoon while other agents were writing
to `nfl/production/**`. Three outcomes occurred and all three are stored,
because the two non-green ones are the evidence that the classifier works.

**1. Full green on the current build —
`nfl/research/remediation/l5/PROOF_SF_LA_PASS_CURRENT_BUILD.json`**

```
identical_predictive_arrays                             PASS
identical_candidate_identity                            PASS
identical_execution_identity                            PASS
identical_model_configuration                           PASS
identical_input_hashes                                  PASS
generated_output_did_not_alter_second_run_identity      PASS
counterfactual_discriminating                           true
classification                                          no findings
verdict                                                 PASS
```

22 arrays, 12,000 draw cells, 4 layers (qb, receiving, rushing, team_volume),
7 frozen input sources. Both runs produced run id `4db178dda4a2b0ab`, code
version `9c3c29a8…+src1[10ce87f8dcd7fac6]` and draw content digest
`bfad4efe0931a41d…`. Source scope digest `10ce87f8dcd7fac6…` identical at all
three observation points **while the working-tree count went 132 → 141 → 148**.

That is the WS-E demonstration made directly, and it is the reason the
counterfactual is computed at all: the withdrawn `<sha>+dirty[N]` form would
have produced three different identities across those three points, for a
forecast that did not change by one bit. The content digest produced one.
`proof_body_sha256 6f4b794fabdfce4e…`, `proof_tool_sha256 c103ad27…`.

**1b. An earlier green on an earlier tool build —
`nfl/research/remediation/l5/PROOF_SF_LA_PASS.json`**

Kept because it carries a fact the single green does not. It was produced hours
earlier by tool build `44d1e837…`, under a different working-tree state
(counterfactual counts 29 → 32 → 34 rather than 132 → 141 → 148), and it
reports the **same draw content digest `bfad4efe0931a41d…`**. The draws
reproduced across the whole afternoon, across two tool builds and across a
working tree that gained a hundred paths in between. That was not the experiment
and it is one observation, not a claim about the engine — but it is worth the
line.

Re-evaluated under the current verdict rule its stored contents still pass
(`verdict_is_pass(equalities, findings)` returns True). It was not re-run on the
current build, which is why the current-build green above is the one to cite.

**2. All six green, verdict FAIL, open CAUSE_1 —
`nfl/research/remediation/l5/PROOF_SF_LA_ALL_GREEN_OPEN_CAUSE1.json`**

The case the harness was refined for, and it occurred live:

```
all six equalities                                      PASS
source_scope_stable_at_identity_resolution              true
source_scope_stable_through_run_b                       false
files_not_dirty_at_every_point   ['nfl/production/run_forecast.py']
counterfactual counts            125 -> 133 -> 141
verdict                                                 FAIL (CAUSE_1)
```

The two runs agreed on everything, and `nfl/production/run_forecast.py` became
dirty **while run B was executing**. The identity B resolves once before a run
writes anything, so run B's recorded identity could not move — which is why the
dF/dD line correctly stays green — but the code underneath the run did move, so
this is a coincidence and not a property, and the verdict says so. A verdict
read off the equalities alone would have certified it. `verdict_is_pass` is a
function precisely so that rule is tested (`test_x`).

**3. FAIL with the file named —
`nfl/research/remediation/l5/PROOF_SF_LA_FAIL_CAUSE1_LIVE_EDIT.json`**

```
identical_predictive_arrays                             PASS
identical_candidate_identity                            FAIL
identical_execution_identity                            FAIL
identical_model_configuration                           PASS
identical_input_hashes                                  PASS
primary cause   CAUSE_1_IN_SCOPE_SOURCE_CHANGED
files_whose_content_changed   ['nfl/production/pool_audit.py']
```

The draws were **bit-identical**; only the identities moved, because another
agent was writing `pool_audit.py`. The harness named the file and said *"another
agent edited in-scope source while this proof was running. Re-run when the tree
is quiescent; do not report a determinism defect on this evidence."*

That is the behaviour asked for, demonstrated against a real concurrent edit
rather than a simulated one. **Note the shape across all nine executions: the
predictive arrays were bit-identical every single time, including on every
FAIL.** Nothing observed here is predictive nondeterminism. What moved was the
code identity, and it moved because the code moved.

### How to invoke it tonight

1. Freeze the inputs at the chosen cutoff, before anything else:

   ```
   python3.12 nfl/tools/determinism_proof.py --game-id 2026_01_DEN_KC \
       --season 2026 --week 1 --cutoff <cutoff> \
       --out-root-a /unused --out-root-b /unused2 \
       --write-manifest nfl/research/remediation/l5/FROZEN_DEN_KC.json
   ```

2. Run the proof against that pinned manifest, at production draw count:

   ```
   python3.12 nfl/tools/determinism_proof.py --game-id 2026_01_DEN_KC \
       --season 2026 --week 1 --cutoff <cutoff> \
       --input-manifest nfl/research/remediation/l5/FROZEN_DEN_KC.json \
       --out-root-a dp_DEN_KC_A --out-root-b dp_DEN_KC_B \
       --draws <production draws> \
       --proof-out nfl/research/remediation/l5/PROOF_DEN_KC.json
   ```

   Two runs at 40 draws took 105 s total; at production draw count budget
   accordingly and start before the tree is frozen only if you are willing to
   read a `CAUSE_1`.

3. Read the verdict line. If it is `CAUSE_1_IN_SCOPE_SOURCE_CHANGED`, the named
   files tell you who is still writing; wait for quiescence and re-run. **Do not
   report a determinism defect on a `CAUSE_1`.** If it is `CAUSE_2` or `CAUSE_3`,
   escalate — neither has been observed here.

4. `counterfactual_discriminating: false` is not a failure; it means the working
   tree did not move during the proof (both roots outside the repository, say),
   so that execution does not discriminate between the old and new forms. Put
   at least one root **inside** the repository if you want the stronger
   demonstration. The proof artifacts above used `dp_proof_A/` and `dp_proof_B/`
   at the repository root and both were removed afterwards.

---

## Patch handed over — one file I do not own

### Patch A — `nfl/tests/test_product_orchestration.py` lines 111-128

Diff: `nfl/research/remediation/l5/patch_A_test_product_orchestration.diff`
(`git apply` from the repository root). Patched file parses under python3.12;
I did not run the suite on it because I do not own the file.

**The defect.** The block gates the run-id comparison on `git status
--porcelain` being empty, and in the else-branch calls `check(..., True)` — a
recorded PASS for a comparison that did not happen. The tree is never clean in
this repository, so that comparison has been inert on **every** execution this
test has ever had, and the inertness was reported as green. It is the
project's own Class A failure mode — absence read as success — sitting inside
the determinism proof.

It is also asking the wrong question now. Identity B is a content digest over
in-scope dirty **source**; an untracked note, a generated board and a research
artifact do not move it. Whole-tree cleanliness is both too strict and beside
the point.

**The patch.** Compares the code identity **now** against the code identity that
produced the stored board (read from `board.json`), and prints `N/A` with the
reason when they differ instead of recording a pass. It also handles the case
that is actually live: the stored board at
`nfl/product/boards/2026_01_SF_LA/20260911T002550Z__fec4038e15735841/board.json`
carries `"code_commit": "9d7a3d70…+dirty[7]"` — the withdrawn form — which no
contract-form run can ever reproduce, so that branch is detected by name via
`CI.refuses_count_keyed()` and reported as not applicable. The draw comparison
below it, which is the actual determinism claim, is unchanged and was never
skipped.

### Not a patch, a note — `NFL_BOARD_AUTOMATION.md:78`

"The run id embeds a `+dirty[n]` counter of uncommitted files, so the test
requires it to match only when the tree is clean." Both halves are now false.
Whoever owns that document should correct it; documentation follows code. I did
not edit it because it is not mine and the change is not urgent for tonight.

---

## Files I wrote

| path | what |
|---|---|
| `nfl/tools/determinism_proof.py` | the harness |
| `nfl/tests/test_determinism_proof.py` | 25 functions, 58 checks, SUITE PASS — includes the two standing sweep guards |
| `nfl/research/remediation/l5/PROOF_SF_LA_PASS_CURRENT_BUILD.json` | the full green, current tool build — **cite this one** |
| `nfl/research/remediation/l5/PROOF_SF_LA_PASS.json` | an earlier green, earlier build, same draw digest |
| `nfl/research/remediation/l5/PROOF_SF_LA_ALL_GREEN_OPEN_CAUSE1.json` | six green equalities, verdict FAIL, source moved during run B |
| `nfl/research/remediation/l5/PROOF_SF_LA_FAIL_CAUSE1_LIVE_EDIT.json` | the live `CAUSE_1` classification with the file named |
| `nfl/research/remediation/l5/patch_A_test_product_orchestration.diff` | the handover patch |
| `nfl/research/remediation/l5/L5_IDENTITY_AND_DETERMINISM.md` | this file |

Nothing was committed, added, stashed or pushed. `dp_proof_A/` and `dp_proof_B/`
were removed after each run. No file outside my declared ownership was edited.

## What I did not establish

* The green above is one game at 40 draws on one machine. It is not a statement
  about the slate, about production draw counts, or about a second machine —
  `platform` is recorded and deliberately not hashed, so cross-machine
  reproduction remains the open question WS-E names.
* `CAUSE_3` has never been observed here and this work does not make it less
  likely; it only makes it distinguishable from the three things that look like
  it.
* Whether a sealed-body field reads generated state is not statically decidable.
  Job 1's answer on that shape rests on reading, not on a test.
