# WS19 — Can a sealed forecast reconstruct its own identity?

**CODE CHANGED: NO.** Research only. Nothing outside
`nfl/research/parallel_pass/ws19/` was written. No existing repository file was
modified. Every number below was recomputed from the bytes on disk during this
pass; nothing is quoted from another document.

Interpreter: `python3.12`. Repo HEAD at time of audit: `57d38ad`.

## The question, stated precisely

For a sealed run, can a reader who holds **only the sealed bytes** recover the
run's identity exactly? Three classifications are used:

| Label | Meaning |
|---|---|
| **STORED_EXPLICITLY** | The value is a literal in the sealed bytes. Reading it cannot drift. |
| **RECONSTRUCTED_INDIRECTLY** | Recoverable only by re-running code, re-reading a file outside the run directory, or inferring from something else. All three can drift. |
| **NOT_RECOVERABLE** | Not present and not derivable from the sealed bytes at all. |

A fourth property is tracked separately because it is not the same question:
**VERIFIABLE** — whether a stored value can be *checked* against the thing it
claims to describe, rather than merely read.

## Runs tested

| Col | Run | Files |
|---|---|---|
| **R1** | `nfl/research/live/2026_01_DAL_NYG/FORENSIC_CORRECTED_RESEARCH/4b186a21b83a49ec/` | board.json, forecast_artifact.json, player_draws.npz, player_draws_manifest.json, run_status.json, BOARD.md, BOARD_SHA256.txt |
| **R2** | `nfl/research/live/2026_01_DAL_NYG/pre_inactives_V1_CANDIDATE_R8/3dddf9f62c9260b0/` | same seven |
| **R3** | `nfl/research/live/2026_01_ATL_PIT/pre_inactives_V1_CANDIDATE_R8/f67d72ab0701d211/` | same seven |
| **R4** | `nfl/prospective/q9shadow/dryrun/2024_01_ARI_BUF/ARI/SEALED_FORECAST.json` | SEALED_FORECAST.json, shadow_target_draws.npz (**two files only** — no board, no run_status) |

R1 and R2 are the same game, same clock, same sources, same configuration; R1 is
the eligibility-corrected rerun of R2. R4 is a different contract entirely.

---

## 1. Per-element classification

| Identity element | R1 | R2 | R3 | R4 (Q9) |
|---|---|---|---|---|
| **Code identity** — commit sha | STORED_EXPLICITLY | STORED_EXPLICITLY | STORED_EXPLICITLY | STORED_EXPLICITLY |
| **Code identity** — uncommitted working tree | NOT_RECOVERABLE | NOT_RECOVERABLE | NOT_RECOVERABLE | NOT_RECOVERABLE |
| **Code identity** — interpreter / library versions | NOT_RECOVERABLE | NOT_RECOVERABLE | NOT_RECOVERABLE | NOT_RECOVERABLE |
| **Candidate identity** — configuration name | STORED_EXPLICITLY | STORED_EXPLICITLY | STORED_EXPLICITLY | STORED_EXPLICITLY |
| **Candidate identity** — component descriptions | STORED_EXPLICITLY | STORED_EXPLICITLY | STORED_EXPLICITLY | STORED_EXPLICITLY |
| **Candidate identity** — predeclaration hashes | PARTIAL (6 of 9) | PARTIAL (6 of 9) | PARTIAL (6 of 9) | STORED_EXPLICITLY |
| **Candidate identity** — run-time estimated coefficients | NOT_RECOVERABLE | NOT_RECOVERABLE | NOT_RECOVERABLE | STORED_EXPLICITLY |
| **Source vintages** — which capture | STORED_EXPLICITLY | STORED_EXPLICITLY | STORED_EXPLICITLY | STORED_EXPLICITLY |
| **Source vintages** — where the bytes live | STORED_EXPLICITLY (board.json only) | STORED_EXPLICITLY (board.json only) | STORED_EXPLICITLY (board.json only) | STORED_EXPLICITLY |
| **Source hashes** | STORED_EXPLICITLY | STORED_EXPLICITLY | STORED_EXPLICITLY | STORED_EXPLICITLY |
| **Source retrieval times** | STORED_EXPLICITLY | STORED_EXPLICITLY | STORED_EXPLICITLY | STORED_EXPLICITLY |
| **Cutoff clock** | STORED_EXPLICITLY | STORED_EXPLICITLY | STORED_EXPLICITLY | STORED_EXPLICITLY |
| **RNG seed** — scalar | STORED_EXPLICITLY | STORED_EXPLICITLY | STORED_EXPLICITLY | STORED_EXPLICITLY |
| **RNG seed** — per-row stream derivation | RECONSTRUCTED_INDIRECTLY | RECONSTRUCTED_INDIRECTLY | RECONSTRUCTED_INDIRECTLY | RECONSTRUCTED_INDIRECTLY |
| **Configuration** — draw count, arm, dry-run, promotion | STORED_EXPLICITLY | STORED_EXPLICITLY | STORED_EXPLICITLY | STORED_EXPLICITLY |
| **Feature versions** | NOT_RECOVERABLE | NOT_RECOVERABLE | NOT_RECOVERABLE | STORED_EXPLICITLY |
| **Model components** — layer labels | STORED_EXPLICITLY | STORED_EXPLICITLY | STORED_EXPLICITLY | STORED_EXPLICITLY |
| **Model components** — fitted-artifact hashes | NOT_RECOVERABLE | NOT_RECOVERABLE | NOT_RECOVERABLE | STORED_EXPLICITLY |
| **Warnings / refusals / verdicts** | STORED_EXPLICITLY | STORED_EXPLICITLY | STORED_EXPLICITLY | STORED_EXPLICITLY |
| **Eligibility state** — layer completeness | STORED_EXPLICITLY | STORED_EXPLICITLY | STORED_EXPLICITLY | STORED_EXPLICITLY |
| **Eligibility state** — player set actually excluded | NOT_RECOVERABLE | NOT_RECOVERABLE | NOT_RECOVERABLE | STORED_EXPLICITLY |
| **Appearance latent** — per-player P(appear) | NOT_RECOVERABLE | NOT_RECOVERABLE | NOT_RECOVERABLE | STORED_EXPLICITLY |

### Notes behind the table

**Code identity.** All four store a commit plus a dirty marker:
`d954110bcfafed627006cd9adbc6e6aace6a78fe+dirty[40]` (R1),
`...+dirty[33]` (R2), `f9e47185059f233a6915e132a9be701c6f004746+dirty[32]` (R3),
`da58aec35c84032cd50004569d1fabe4289ec090+dirty[25]` (R4). Read at
`nfl/production/run_forecast.py:113-127`, the suffix is
`len([x for x in git status --porcelain if x.strip()])` — a **count of dirty
paths, not a hash of their content**. Two different working trees with the same
number of modified files produce the same code identity string. Section 3 shows
this is not hypothetical.

No run records the interpreter or the numpy version. The only string containing
`numpy` in any sealed file is the generator label
`"numpy.random.default_rng (PCG64)"`. `nfl/identity/seal.py` does carry an
`interpreter` field in its identity dict, but see section 4 — the identity dict
for R4 is not on disk anywhere.

**Candidate identity — the partial row.** `forecast_artifact.candidate_components`
carries nine entries. Six (A1, A3G, C0, C3, R2, SC1) carry
`predeclaration` + `predeclaration_sha256`. Three (R5, R6, R8) carry neither
key: their predeclaration is described in prose and not hash-pinned.

**Candidate identity — run-time coefficients.** The R8 entry's `k` field is a
static sentence ending `k = 1.2176`. But `run_forecast.py:706-713` computes a
run-specific `k` via `appearance_r8.reliability_k(..., cut=args.season * 100)`
and stores it in `fx['_r8']['k']` with a `k_state`. Neither reaches any sealed
file. The number the run actually used is not the number the artifact prints,
and only re-running the estimator recovers it.

**Source vintages.** All seven captures in R1 resolve: every
`information_set.sources[*].blob` exists on disk and every `blob_sha256`
recomputes exactly (7/7). But the location lives **only in `board.json`**.
`forecast_artifact.json` carries `{source, sha256, retrieved_at}` and no path,
so a reader holding the artifact alone cannot find the bytes. R4 is better here:
each capture carries `partition_id` and `url`.

**Cutoff clock.** R1–R3 store `written_at`, `kickoff_utc`, and in board.json an
`information_set` with `observed_before`, `newest_observation`,
`oldest_observation` and the full `selection_rule` sentence. R4 stores a
dedicated `cutoff` block naming `cutoff_basis: information_set.observed_before`.
The lead is answered: **yes, retrieval times and content hashes are both carried,
on every run tested.**

**RNG seed — the protocol.** The scalar is stored
(`20260908` for R1–R3, `20260912` for R4) along with generator and a protocol
string. But the protocol is prose: `"numpy default_rng([seed, ord, gsis_id])
-- one stream per row"`. The per-row `ord` is not stored, so reproducing one
player's stream means re-deriving the ordinal by running the code. That is the
definition of RECONSTRUCTED_INDIRECTLY.

**Feature versions.** `feature_set_hash` is computed at
`run_forecast.py:1543-1544` as
`sha256(json.dumps(sorted(src)))[:32]` — a hash of the **sorted list of source
names**, with no content and no feature information in it. Recomputed and
confirmed. The observable consequence: R1, R2 and R3 all carry
`feature_set_hash = 4d2eda3e88818e2ad5a78e146c4e2f48`, **identical across two
different games, two different clocks, two different code commits and two
different draw counts**, because all three read the same seven source names. A
field named for features that is invariant to the features is worse than an
absent field, because it reads as coverage.

**Model components — fitted artifacts.** `run_status.stages[*].input_hashes` is
populated for exactly one stage: `capture_validation`. Every model stage
(`team_environment`, `appearance`, `participation`, `targets_carries`,
`conversion`, `td_layer`, `qb_layer`) records `input_hashes: {}`. The pipeline
*does* check a model hash — `QBV1.artifact_hash()` at `run_forecast.py:972` —
and then discards the value. The artifact a run consumed cannot be identified
from the run.

One label defect found: `run_forecast.py:920` hard-codes the appearance stage's
`spec_version` as the literal `'P3 appearance'`. All three live runs applied R8
(`eligibility_verdict` says `APPLIED:...,R8,...`) and all three report
`"spec_version": "P3 appearance"` on the appearance stage. Which appearance
mechanism ran is recoverable only from the eligibility string, not from the
stage that ran it.

**Eligibility state — the sharpest gap.** See section 3.

---

## 2. Integrity results — all pass

Every check below was recomputed from the bytes, using the hashing recipes read
out of `nfl/production/draws_artifact.py` and `nfl/prospective/q9shadow/seal.py`.

| Check | R1 | R2 | R3 | R4 |
|---|---|---|---|---|
| `BOARD_SHA256.txt` == sha256(BOARD.md) | PASS | PASS | PASS | n/a (no board) |
| npz file sha256 == manifest `file.sha256` | PASS | PASS | PASS | PASS |
| npz file sha256 == artifact `draw_artifact_sha256` | PASS | PASS | PASS | PASS |
| npz file sha256 == `run_status.draw_artifact.sha256` | PASS | PASS | PASS | n/a |
| npz byte length == manifest `file.bytes` | PASS | PASS | PASS | n/a |
| per-array sha256 recomputes (canonical float64 form) | PASS 22/22 | PASS 22/22 | PASS 22/22 | n/a (no per-array manifest) |
| artifact's array table == manifest's array table | PASS | PASS | PASS | n/a |
| content digest recomputes from the npz | PASS | PASS | PASS | PASS |
| content digest agrees across artifact / manifest / run_status | PASS | PASS | PASS | n/a |
| `spec_hash` == `run_id` == manifest run_id == directory name | PASS | PASS | PASS | n/a |
| **execution identity recomputes from stored bytes alone** | **PASS** | **PASS** | **PASS** | n/a |
| `feature_set_hash` recomputes | PASS | PASS | PASS | n/a |
| Q9 `payload_sha256` recomputes | n/a | n/a | n/a | PASS |
| Q9 `forecast_id` recomputes from payload | n/a | n/a | n/a | PASS |
| Q9 `draw_content_sha256` recomputes | n/a | n/a | n/a | PASS |
| Q9 `seal_sha256` recomputes | n/a | n/a | n/a | **NOT VERIFIABLE** |

Detail on the two that matter most.

**Execution identity is self-verifying on the live path, and that is a real
strength.** Rebuilding the payload of `run_forecast.execution_identity` from the
sealed bytes only — season and week parsed from `game_id`, arm, `written_at`,
seed from `draw_artifact.rng.seed`, `code_commit`, `model_configuration`, and
`{source: {sha256, retrieved_at}}` from `source_captures` — reproduces the run
id exactly:

```
4b186a21b83a49ec  recomputed == stored spec_hash, and the full 64-hex
3dddf9f62c9260b0  recomputed == stored spec_hash, digest equals
f67d72ab0701d211  recomputed == stored spec_hash, run_status.execution_identity
```

All three also match `run_status.execution_identity` at full length. This is the
best-audited element in the system: a reader can prove the run id was not typed
in by hand.

**Q9 `seal_sha256` cannot be checked.** `Seal.seal_sha256()`
(`nfl/identity/seal.py:72-76`) hashes a dict that includes
`identity: ExecutionIdentity.as_dict()` — the full partition list with
provenance. That dict is **not written into `SEALED_FORECAST.json`**. It is
written to the append-only ledger
`nfl/prospective/q9shadow/Q9_SHADOW_DRYRUN_SEAL_LEDGER.jsonl`. R4's
`forecast_id` `Q9SH-0215becbfe930a47` **is not in that ledger**, and neither is
its sibling `Q9SH-1381167432ba8074` (BUF). The ledger holds 18 rows and none
carries code version `da58aec…+dirty[25]`. So for the two most recent Q9 dry-run
seals on disk, the identity dict exists nowhere and `seal_sha256` is a stored
number that nothing can confirm. The two older seals
(`2025_01_ARI_NO`, `Q9SH-d53fcb0fabb325f7` and `Q9SH-d8bbaec21c8a6c0f`) **are**
in the ledger.

**A second Q9 tamper-evidence gap.** `payload_sha256` covers `art` as it stood
before fourteen keys were appended (`seal.py:585-656`). Everything added
afterwards sits outside the payload hash: `candidate` (which is where every
model-identity hash lives — `coefficient_sha16`, `feature_schema_sha16`,
`appearance_spec_sha16`, `budget_point_sha16`, `budget_residual_pool_sha16`),
`cutoff`, `arms`, `fallback_counters`, `reconciliation`, `seal_path`,
`input_bundle_sha256`, `absent_input_sources`, `player_summary`, `season`,
`team`. Editing `candidate.coefficient_sha16` leaves `payload_sha256` verifying
cleanly. The comment at `seal.py:559-571` explains why `draw_artifact` was
excluded — a good reason — but the keys written *after* the seal were not part
of that reasoning and were never brought back under it.

**Nothing hashes the JSON.** On the live path, `BOARD_SHA256.txt` covers
`BOARD.md` and only `BOARD.md`. `forecast_artifact.json`, `board.json` and
`run_status.json` carry no self-hash and appear in no manifest. The draws are
tamper-evident; the numbers rendered from them are not.

---

## 3. The finding that costs the most: the identity does not separate the runs

R1 and R2 are the same game. Recomputed from their bytes:

- `source_captures` **identical** (all seven entries, byte for byte)
- `written_at` identical (`2026-09-13T23:12:33Z`)
- `model_configuration` identical (`V1_CANDIDATE_R8`)
- `model_arm`, seed, `n_draws` (8000), `feature_set_hash`, `player_ids` (178) all identical
- committed base commit identical (`d954110b…`)
- **`draw_artifact.content_digest` DIFFERENT** — `c3347111c976adcc` vs `39f9f4934ba8d00a`

The declared treatment between them, per
`nfl/research/live/2026_01_DAL_NYG/DAL_NYG_FORENSIC_CORRECTED_RESEARCH.json`,
is *"player eligibility set (6 identities removed)"*. **That treatment appears
in no field of the execution identity.** The only payload field that differs is
`code_commit`, and it differs only in the dirty-file count. Recomputing the run
id with the dirty count as the sole variable:

```
d954110b…+dirty[40] -> 4b186a21b83a49ec   (R1, eligibility corrected)
d954110b…+dirty[33] -> 3dddf9f62c9260b0   (R2, pre-inactives)
d954110b…  (clean)  -> 380cfa270765fc65   (both, had the tree been clean)
```

Two forecasts with materially different numbers are separated by an incidental
count of modified files. Had both trees carried the same number of dirty paths —
or had the tree been clean, which is the *intended* state — both runs would have
computed run id `380cfa270765fc65`, written to the same output directory, and
the second would have overwritten the first with no check objecting.

The repository already names half of this. R1's research artifact records a
`caveat_working_tree` block with `"unresolved": true` and the note that the
corrected run "was executed with more uncommitted files present… this WEAKENS
the comparison". That caveat is honest and correctly withheld from dismissal.
What it does not say is the stronger thing: the dirty counter is not a weakness
in the comparison, it is the *only* thing carrying the comparison, and it is
carrying it by accident.

### The exclusions are invisible in the sealed bytes

The six identities the correction removed are
`00-0036893` (Najee Harris), `00-0038389` (Israel Abanikanda),
`00-0039398` (Joe Milton III), `00-0040225` (Thomas Fidone II),
`00-0040431` (Dalen Cambre), `00-0040930` (Camden Brown). Measured in R1:

- all six are still in `player_ids`
- all six are still in `distributions`
- all six still occupy rows in the draw matrices
- `excluded_unidentified` is `[]`
- `run_status.qb_inactive_ownership.inactive_qbs_excluded` names **one** of them
  (`00-0039398`, the QB) and `enforced` is `false`
- the other five appear in no exclusion field anywhere in the run directory

The exclusion is expressed **only as zero mass in the draws**. Measured:

| player | layer/metric | R1 nonzero fraction | R2 nonzero fraction |
|---|---|---|---|
| 00-0036893 | rushing/carries | 0.0000 | 0.9597 |
| 00-0038389 | rushing/carries | 0.0000 | 0.8130 |
| 00-0039398 | qb/att | 0.0000 | 0.6291 |
| 00-0040225 | receiving/receiving_td | 0.0000 | 0.0217 |
| 00-0040431 | receiving/receiving_td | 0.0000 | 0.0147 |
| 00-0040930 | receiving/receiving_td | 0.0000 | 0.1116 |

Scanning every modelled player for an all-zero row across all non-team layers:
R1 has 6 of 36, R2 has 0 of 36, R3 has 0 of 32. In this instance the all-zero
set happens to equal the ruling set exactly — but that is a consequence, not a
record. A reader of R1's bytes can see that six players drew nothing. They
cannot see **that a ruling was applied**, **which six the ruling named**, or
**on what basis**. The bases differ and matter: five were `OFFICIAL_INACTIVE`
and one (`00-0039398`) was `NOT_ON_ACTIVE_53_PRACTICE_SQUAD`. That distinction
exists only in a research JSON one directory up, which is not part of the seal
and carries no hash binding it to the run.

### The appearance latent, confirmed

The lead is correct and the contrast with Q9 makes it concrete.

**Live path (R1–R3):** the string `appear` occurs 3–4 times per sealed file and
every occurrence is a stage label, a governance sentence, or prose inside the R8
component description. There is **no per-player P(appear)** — not in the
artifact, not in board.json, not in run_status, and not as an array in the npz
(the 22 matrices are exactly the four layers' output metrics). A reader cannot
audit where the zero mass came from.

**Q9 path (R4):** `shadow_target_draws.npz` carries eight arrays, and four of
them are latents, not outputs:

```
appearance   (200, 19) int64   min 0 max 1     <- the realised appearance draw
p_hurdle     (19,)     float64 0.00275 .. 0.98891
base_share   (19,)     float64 0.01111 .. 0.25524
budget       (200,)    int64   6 .. 64
```

and `player_summary` carries per player `p_appear_drawn`, `p_hurdle`,
`base_share`, `role_class`, `appearance_certainty`, `prior_depth_bucket`,
`zero_probability`. The zero mass in R4 is fully auditable. The same project
solved this problem on the shadow path and did not carry it to the live path.

---

## 4. What should be stored explicitly and is not

Ordered by how much an audit loses without it. These are observations, not
changes; nothing here was implemented.

1. **The eligibility set the run actually applied**, as an explicit list of
   identities with a per-identity basis code, inside the sealed artifact. Today
   a ruling that zeroed six players leaves no record of itself. This is also the
   fix that makes the R1/R2 pair legible.
2. **The eligibility set as a field of the execution identity.** While it is
   outside the identity payload, two runs that differ only by a ruling can
   collide on one run id and one output directory.
3. **Per-player appearance probability and the realised appearance draw**, on
   the live path — the Q9 shape (`appearance` matrix plus `p_appear_drawn`)
   already exists and already works.
4. **A content hash of the code, not a count of dirty files.** A tree hash, or
   a hash of the diff, or a refusal to seal a non-TEST run from a dirty tree.
   `+dirty[n]` is a flag that something was uncommitted; it is not an identity.
5. **The interpreter and library versions.** `CLAUDE.md` records that the MLB
   sibling engine will not even import below 3.12 and that suites classify
   differently by interpreter. No live NFL seal says which Python drew its
   numbers.
6. **Fitted-model artifact hashes, per stage.** `input_hashes` already exists on
   every stage record and is empty on every model stage. `QBV1.artifact_hash()`
   is already computed and already discarded.
7. **A real `feature_set_hash`, or a renamed one.** The present value hashes
   source *names* and is identical across different games. Either bind it to
   feature content and schema (Q9's `feature_schema_sha16` is the model) or
   rename it `source_name_set_hash` so it stops reading as coverage it does not
   provide.
8. **The run-time R8 `k` and its state.** Computed per run, printed nowhere; the
   artifact shows a different, static number.
9. **`predeclaration_sha256` for R5, R6 and R8**, matching the six components
   that already carry one.
10. **The appearance stage's real `spec_version`.** Hard-coded `'P3 appearance'`
    while R8 ran, in all three live runs.
11. **A self-hash for `forecast_artifact.json`, `board.json` and
    `run_status.json`.** Only `BOARD.md` is covered today.
12. **Q9: bring the post-seal keys under `payload_sha256`**, or hash them
    separately. `candidate` — which holds every model-identity hash — is
    currently unprotected.
13. **Q9: close the ledger gap.** Two seals on disk are absent from the
    append-only ledger, so their `seal_sha256` is unverifiable. Either the
    artifact should carry the identity dict, or a seal whose ledger append did
    not land should not be left presenting a `seal_sha256`.
14. **The source blob path inside `forecast_artifact.json`.** Today it exists
    only in `board.json`, so the artifact alone cannot locate its own inputs.
    Q9 already carries `url` per capture.

---

## 5. Evidence ceiling

What this audit can and cannot support.

- **Four runs, three of them from one pipeline and one game-week.** R1 and R2
  are the same game; R3 is a second game on the same contract. This is a
  characterisation of the `nfl-forecast-artifact-1` contract as exercised in
  2026 week 1, not a survey of every sealed artifact in the repository.
  `nfl/research/sealed_index.py` exists precisely because artifacts live in
  several namespaces; namespaces other than the two sampled here were not
  opened.
- **Every integrity recomputation used a recipe read out of the code.** The
  digests verify that the bytes are internally consistent with the code
  currently at `57d38ad`. They do **not** verify that the bytes were produced by
  that code — that claim reduces to `code_commit`, and section 3 shows what
  `code_commit` is worth on a dirty tree.
- **"All integrity checks pass" is not "the artifact is correct".** It means the
  npz matches its manifest, the manifest matches the artifact, the board matches
  its hash, and the run id matches its inputs. It says nothing about whether the
  numbers inside are right, and nothing about forecast quality.
- **The R1/R2 collision is demonstrated by construction, not observed.** The two
  runs did not in fact collide; the dirty counts differed. What is measured is
  that every other identity field is identical and that equal dirty counts yield
  one id (`380cfa270765fc65`). No collision event is being reported.
- **The all-zero row scan is a one-game measurement.** In R1 the all-zero set
  equals the ruled-out set. That six-for-six agreement is a single observation
  and is not evidence that zero mass generally identifies exclusions — it is the
  reason it *cannot* be relied on, since nothing in the format makes the two
  coincide.
- **The Q9 ledger gap was checked against the working-tree ledger**
  (18 rows; 12 committed at HEAD plus 6 uncommitted). The `2024_01_ARI_BUF`
  dry-run directory is untracked. A ledger row for these seals may exist
  somewhere outside this checkout; within it, there is none.
- **Nothing here was re-run.** No forecast was regenerated, no suite was
  executed, and no repair was applied. Reproducing a run and diffing its bytes
  against a stored one would test a claim this audit only characterises: that
  the stored identity is sufficient to reproduce the run. It is not tested and
  should not be reported as tested.

---

**CODE CHANGED: NO.**
