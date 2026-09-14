# WS-K — PERSISTED PROVENANCE

**Defect class: ARTIFACT / PROVENANCE CHANGE. No projection moves and no price
moves.** Nothing in this workstream touches a model, a feature, a coefficient,
a market or a probability. It changes what a manifest row *says about the file
it stored*, and it changes *when* a file is allowed to enter the durable store.
No coverage verdict changes either — see BLAST RADIUS, where that is measured
rather than asserted.

Measured 2026-09-14 UTC, `python3.12`, branch `claude/nfl-greenfield-architecture-stsxmk`,
baseline HEAD `837d52f`.

---

## 1. DEFECT

**Every persisted `depth_charts` and `weekly_rosters` blob fails its own
manifest hash — 368 of 1,061 PASS rows, 34.7%.** Reproduced here from the
manifest in this checkout, not carried over from WS13:

```
PASS rows with durability "reduce"   368   (depth_charts 184 + weekly_rosters 184)
distinct cited blob paths             15   (13 distinct blobs; 2 cited twice, with and without .gz)
coverage._blob_ok verdict, unchanged file:
    RAW_SHA256_MISMATCH                366
    RAW_ARTIFACT_MISSING_ON_DISK         2
    OK                                   0
```

Zero of 368 verified. The recorded `sha256`, `n_bytes` and `n_lines` describe
the **full upstream file**; the file actually persisted is a column-reduced
subset whose hash was never recorded anywhere. `sha256_is_of: "uncompressed_bytes"`
is asserted on 366 of them and is **false as written** — the bytes it names
were never stored.

`coverage._blob_ok` re-hashes the blob and refuses all 368, so the rows
self-exclude from discharge. Nothing was corrupt and nothing was lost. **A
claim was made about a different object from the one stored.**

---

## 2. ROOT CAUSE

`_persist` supports three durabilities. Two of them (`commit_raw`, `ephemeral`)
retain the upstream bytes verbatim, so one digest honestly covers both the
fetched object and the stored object. The third, `reduce`, writes a
transformation of the upstream file — five columns, and for `depth_charts` the
newest `dt` slice only — and then reused the **same field** to carry the
**upstream** digest.

One field that means the fetched object on two code paths and the stored object
on nowhere, while sitting next to a `blob` key that names the stored object, is
the whole defect. There was no digest of the reduced bytes anywhere, so nothing
in the system could have caught it: the reduction's output was never checked
against any claim at all, and the claim that existed was about its input.

This is the project's dominant defect class in provenance form — **a reduction
step whose output was never checked against a claim made about a different
object** — and it is the same shape as the export that wrote 7,926 rows with
every meaningful column blank, and the connector read that dropped the
provenance block and then reported provenance missing.

---

## 3. REPAIR

### 3a. Three digests, three objects, three names

`nfl/tools/capture_vintage.py`, `_persist`. Every durable row now carries:

| field | the object it covers |
|---|---|
| `upstream_content_sha256` | the bytes the origin served |
| `persisted_content_sha256` | the uncompressed bytes actually retained at `blob` |
| `blob_file_sha256` | the file on disk, gzip container included |

`sha256` **keeps its existing meaning** — the upstream digest — and is *not*
repointed. That was a deliberate decision against the obvious move, for a
measured reason: `sha256` is the content address embedded in every blob
filename, and `nfl/research/shadow/information_set.blob_for` resolves blobs by
globbing `f'{source}.{sha256[:16]}.'`. Repointing it would silently break blob
resolution for every vintage already stored, which is a *second* silent
redefinition of a field — the defect, not the repair.

`sha256_is_of` now names the object it covers on every path. The sentence that
was false on 366 rows is gone:

```
commit_raw / ephemeral  "upstream_bytes_which_are_also_the_persisted_uncompressed_bytes"
reduce                  "upstream_bytes_only__blob_is_a_reduction"
```

`commit_raw` records the two content digests as **explicitly equal** rather
than omitting one. Absence is not a statement; equality is.

### 3b. The reduction is auditable, not merely declared

The reduction was an anonymous block inside `_persist`. It is now
`_reduce_frame`, a named pure function, extracted **verbatim** — verified by
re-running it over the seven surviving upstream files and reproducing all seven
stored blobs byte-for-byte. Every reduce row now carries:

```
transform_id          nfl-vintage-column-reduce
transform_version     reduce-2
code_sha256           5e4eb7a9257ea44c999b39b078be29acbc9ab80bd897196a21778cb482027456
code_symbol           nfl.tools.capture_vintage._reduce_frame
input_sha256 / input_n_bytes        the upstream file
output_sha256 / output_n_bytes      the persisted blob
output_columns / requested_columns / missing_columns
row_filter / row_filter_value / rows_in_file / rows_kept
deterministic: true   reversible: false   + an irreversibility note
```

`code_sha256` is a measurement, not a claim: if someone edits the reduction
without bumping `transform_version`, rows written afterwards still say so.

### 3c. The reduction now runs on every capture, including unchanged ones

It used to be skipped when the blob already existed, which is why 179 of 186
`depth_charts` captures recorded nothing about the object they were
re-observing. It is now always computed and always compared against the stored
blob. **This closes WS13 evidence-ceiling item 2 by measurement** for the local
half: whether the retained reduction is still exactly what this transformation
produces from these upstream bytes is now checked every run, rather than
assumed. Cost: ~5.0 s per capture for the 49 MB `depth_charts` file, against a
download of the same file — see BLAST RADIUS.

`reduce_recoverability_checked` stays `false`, correctly. It is a claim about
**upstream** retaining its `dt` history, and nothing here tests that. A new
field `persisted_artifact_verified_against_upstream_bytes: true` records the
half that *is* now checked, under its own name.

### 3d. Every persisted blob self-verifies, checked at write time

`_verify_persisted` reads the bytes **back off disk** and hashes them before
any row is written. Not from the variable still in memory — that would prove
only that the program has a variable. A mismatch raises `PersistIntegrityError`
and `fetch` returns `FAIL[PERSISTED_ARTIFACT_SELF_VERIFICATION_FAILED]`. There
is no PASS-with-a-caveat path.

Gzip writing is now deterministic (`mtime=0`, no embedded filename), which is
what makes `blob_file_sha256` a stable quantity rather than a timestamp.

### 3e. WS-J's invariant, built here, from the capture side

**A blob cannot be written without its manifest row.** The guard that existed
raised *after* the blobs were already in `nfl/vintage`, so it converted a
silent orphan into a loud one without preventing it. Ordering fixes what a
check could not:

```
durable bytes  ->  staged in the gitignored ephemeral store
                ->  _assert_no_pass_without_capture(rows)
                ->  _flush(manifest, rows)          rows land first
                ->  _promote_staging(staged)        bytes land second
```

A crash, a raise, or a zero-row flush purges staging and leaves **nothing** in
the tracked tree. This is by construction, not by assertion.

**A manifest cannot claim PASS when no qualifying capture exists.**
`_assert_no_pass_without_capture` reads each row exactly as a later auditor
would, with no access to the variables that built it, and refuses to append a
PASS row that names no artifact, carries no digest of the persisted bytes, or
carries a malformed one.

`content_unchanged` is now staging-aware: a staged blob is bytes we hold, so a
second observation of identical content inside one run is still a measurement,
not a second write.

---

## 4. WHY THIS REPAIR

Three alternatives were considered and rejected on evidence.

**Repoint `sha256` to the persisted bytes.** Rejected: measured that
`information_set.blob_for` derives the blob filename from it. This would have
been a second silent field redefinition and would have broken blob resolution
for all 447 stored vintages.

**Hash the blobs on disk and backfill the manifest.** Rejected on the merits,
and this is the important one. It would make all 368 rows self-consistent in
one line and would establish **nothing**. Self-verification ("does the row
describe the blob") and faithfulness ("is the blob the correct reduction of the
attested upstream file") are different properties, and a digest taken from an
unattested blob is circular — it attests that the file has not changed since
the moment we looked, which is not the question anyone is asking.

**Rewrite the historical rows.** Rejected: the manifest is append-only and its
rows are the record of what was believed when they were written. A
repaired-looking history cannot be told from a history that never had the
defect. The migration is a **sidecar**, `nfl/vintage_provenance_recovery.jsonl`,
joined on `value.blob`; every original row is intact and a test asserts it.

---

## 5. PRE-REPAIR FAILURE

Run against the unchanged manifest, with `coverage._blob_ok` unchanged (it is
WS-J's file):

```
368 reduce PASS rows
  OK                              0
  RAW_SHA256_MISMATCH           366
  RAW_ARTIFACT_MISSING_ON_DISK    2   (path cited without .gz; the bytes exist)
```

Worked example, first occurrence `20260906T201020Z`:

```
blob      nfl/vintage/depth_charts.76d7bcb384ec11e3.reduced.csv.gz
declared  sha256 76d7bcb384ec11e3…   n_bytes 47,641,094   n_lines 501,069
actual    stored content is 2,177 lines over 5 columns, hashing to b610bbc735f54c0c…
```

---

## 6. POST-REPAIR RESULT

### New captures

Self-verifying by construction. The digest is computed from the persisted
bytes, read back off disk and compared before the row exists, and the row
cannot be written if they disagree.

### The 368 historical rows

| | rows | blobs |
|---|---|---|
| **now self-verifying** | **216** | 9 cited paths / 7 distinct vintages |
| **lawfully recoverable from retained raw bytes** | **216** | same — recovery *is* the mechanism |
| **permanently unverifiable** | **152** | 6 |

```
POST:  PASS[PERSISTED_ARTIFACT_SELF_VERIFIES]   216
       BLOCKED[PERSISTED_DIGEST_ABSENT]         152
       FAIL                                       0
       216 + 152 = 368
```

**Nothing came back FAIL.** No stored blob contradicts a digest. The 152 are
BLOCKED rather than FAIL deliberately: nothing is known to be *wrong* with
those bytes, they simply cannot be checked, and that is a different fact and
gets a different word. Collapsing the two would make the BLOCKED bucket a place
to hide damage.

### What "lawfully recoverable" required

A closed chain, re-run in full and re-run again by the test on every suite run:

```
1. the manifest row declares an upstream sha256
2. a retained raw file in nfl_vintage/raw/ hashes to EXACTLY that digest
3. _reduce_frame over those bytes reproduces the stored blob BYTE-FOR-BYTE
```

All three, or no digest is recorded. Seven full-byte files survive; all seven
close the chain; all seven match exactly.

**Caveat recorded with the recovery, because it is real:** the transformation
run is *today's* code. That is sufficient, and the reason is worth stating — a
byte-exact match proves the stored blob **is** this reduction of the attested
input, whatever code first produced it. It does not prove the historical code
was identical, and nothing here claims it was.

### What the 152 are, and why they stay unverifiable

Six vintages, named and final:

```
depth_charts    ecc4973e8715d866 (44 rows)  f57ef0724d907160 (11)  361f1c69443cba69 (21)
weekly_rosters  e157129706145664 (44)       125c300ff066d314 (11)  0b005c45d924a541 (21)
```

The upstream bytes are not in the ephemeral store, and **a re-fetch would not
help even with egress**: nflverse restamps these files continuously, so the
bytes that hash to those digests are not obtainable from the origin any more.
The reduction is irreversible — columns discarded, and for `depth_charts` every
prior `dt` slice — so the blob cannot reconstruct its own input either.

For each, the sidecar records `persisted_content_sha256: null`, a specific
`why_unverifiable`, and a digest of the blob as it stands today under the name
`unattested_blob_digest_at_migration`, explicitly annotated as attesting *"that
these bytes have not changed since 2026-09-14. **NOT** that they are a faithful
reduction of the upstream file the row names."* It is a tamper baseline and it
never sets `verification_state`.

### The loss has a mechanism, and it is not the source or the date

WS-L's RL-9 finding reproduces here **with no exceptions**, measured
independently from the manifest in this checkout:

| raw bytes | observed by | vintages |
|---|---|---|
| **LOST** | GitHub Actions **only** | **6 of 6** |
| kept | both, or non-Actions only | **7 of 7** |

`nfl_vintage/raw/` is gitignored and Actions runners are ephemeral, so the raw
store never leaves the runner. **Raw retention is currently a property of which
machine happened to look.** That is why the split is a clean 6/7 rather than a
scatter, and it is worth naming as a *second, independent* failure mode of the
Actions path: the runner that stopped running is also the runner whose evidence
never survived. Recorded per blob as `loss_mechanism`, `observed_by_executors`
and `actions_only`.

RL-9 applied to this repair itself: the recovered digests are governance
evidence, so their home must not be the untracked store they came from.
`nfl/vintage_provenance_recovery.jsonl` is tracked and a test asserts it is not
gitignored. **The digests survive the raw store; the ability to re-derive them
does not.** If `nfl_vintage/raw/` is cleared, the 216 recoveries remain recorded
and cited but stop being independently re-runnable — the same shape as M0-A
holding while M0-C does not.

---

## 7. TEST

`nfl/tests/test_persisted_provenance.py` — new, mine.

```
python3.12 nfl/tests/run_suite.py --only test_persisted_provenance
modules 1  test functions 14  checks 87  FAILING CHECKS 0  RAISED 0
           ZERO-CHECK FUNCTIONS 0  BLOCKED FUNCTIONS 0        SUITE PASS
```

Forward: the two digests exist, differ, and match the bytes on disk; the
transformation block carries identity, version, code digest, input digest,
output digest, selected schema and row filter; `commit_raw` records them equal;
staging means no blob is in the durable store before its row; a purged run
leaves the store empty; a PASS row that cannot name what it retained is
refused, in four distinct malformed shapes; write-time verification refuses a
wrong digest; gzip containers are byte-reproducible; and the row-before-blob
ordering is asserted **structurally, in the source text**, so a later edit that
reverses it fails.

Historical: the live manifest still carries all 368 rows unaltered and **not
one** carries a backfilled digest (this is the no-silent-rewrite lock); the
false `sha256_is_of` is preserved on its 366 rows as evidence rather than
edited; every recorded recovery is **re-derived from the raw bytes during the
test**, not trusted; the 6 unrecovered blobs claim no digest, say why in more
than 80 characters, and carry the anti-misreading annotation; the six named
losses are pinned so a later "recovery" of one has to explain itself rather
than appear; self-verification is a three-way answer and a tampered blob comes
back FAIL not BLOCKED; and the pre-repair failure is **reproduced**, not
recalled — 0 of 368, 366 by hash mismatch, 2 by a missing `.gz`.

No network. No sportsbook data. Every write goes to a temporary root; the
tamper probe uses an absolute path outside the repository, because writing a
probe blob into the live store — even one deleted a line later — would create
exactly the orphan this workstream exists to prevent.

---

## 8. BLAST RADIUS

### Files changed

| file | change | owner |
|---|---|---|
| `nfl/tools/capture_vintage.py` | the repair | **WS-K (mine)** |
| `nfl/capture/persisted_provenance.py` | **new** — verifier + migration | WS-K |
| `nfl/tests/test_persisted_provenance.py` | **new** | WS-K |
| `nfl/vintage_provenance_recovery.jsonl` | **new artifact**, additive sidecar | WS-K |
| `nfl/tests/test_capture_states.py` | see below | test of my module |

`nfl/capture/registry.py` is unchanged. `nfl/vintage_manifest.jsonl` is
unchanged — not one byte, not one row. **Nothing under `.github/workflows/`,
`nfl/capture/coverage.py`, `nfl/tools/preflight_t90.py`,
`nfl/tools/check_retention.py`, `docs/AGENT_OUTBOX.md`, `nfl/production/`,
`nfl/prospective/q9shadow/` or the WS-F/WS-G scorers was touched.**

### `test_capture_states.py` — disclosed in full

Two checks there read `nfl/vintage` directly and broke, because staging changed
*when* blobs land. That is the deliberate contract change, so the tests were
updated rather than the contract weakened. **Every existing check is preserved
verbatim**; the change adds a `_land()` helper performing the promotion step a
real run performs, and adds one **new, stronger** check — that bytes are *not*
in the durable store before the manifest row is written. Net: 107 → 108 checks,
0 failing. If the coordinator prefers this file be routed to its owner, the
edit is a self-contained 4-hunk patch.

### Suites re-run (module-scoped only, never the full suite)

```
test_persisted_provenance        14 fn   87 checks   0 failing   PASS
test_capture_states              11 fn  108 checks   0 failing   PASS
test_capture_manifest_integrity  10 fn   29 checks   0 failing   PASS
test_source_registry              9 fn  136 checks   0 failing   PASS
test_execution_target            19 fn   86 checks   0 failing   PASS
test_discharge_identity          12 fn   55 checks   0 failing   PASS
test_perishable_immutability     13 fn   42 checks   0 failing   PASS
test_attribution                  3 fn   11 checks   0 failing   PASS
test_inactives_propagation       19 fn   43 checks   0 failing   PASS
test_t90_synthetic_eligibility   10 fn   24 checks   0 failing   PASS
```

**`test_coverage` fails (1 failing check, 2 raised, `KeyError: 'covered'`) and
it is NOT mine.** `nfl/capture/coverage.py` carries 194 uncommitted insertions
from its owner restructuring `coverage()`'s evidence dict — the WS13 W5 schema
work. `test_coverage.py` does not reference `capture_vintage`,
`persisted_provenance` or the new sidecar. Reported, not touched.

### Runtime

The reduction now runs on every capture rather than only on new content:
**+5.0 s** per capture run for the 49 MB `depth_charts` file (measured), against
a download of that same file in the same run. `weekly_rosters` is 0.94 MB and
immaterial. Flagging it to WS-J because the T-90 workflow's cadence is theirs.

---

## 9. IDENTITY IMPACT

**None on any frozen identity.** `SIM_FORMULA`-equivalent freezes,
`Q9_PROSPECTIVE_FREEZE.json`, `FREEZE_V1_*`, `nfl/production/nonqb/layers.py`
and every `module_source_sha16` in `WAVE0_BASELINE.json` are untouched. No
projection, no feature, no coefficient, no probability, no price.

**No coverage verdict moves, and this is measured, not assumed.** All 368
reduce rows carry `discharge_eligibility.n_eligible = 0` — every one of them,
without exception. `depth_charts` and `weekly_rosters` are not an authorised
source for `practice`, `final_status` or `inactives`, so they discharge nothing
and never could. Repairing their verifiability **cannot convert a MISSED window
into a COVERED one.** The 47 missed week-1 targets stay missed. Past missed
windows stay MISSED.

**Manifest schema identity does change, for rows written from here on.** New
PASS rows carry `upstream_content_sha256`, `persisted_content_sha256`,
`persisted_n_bytes`, `persisted_is_upstream_verbatim`, `blob_file_sha256`,
`self_verifying`, `upstream_n_bytes`, `upstream_n_lines` and, on reduce rows, a
`transformation` block. Existing fields keep their existing meanings. Readers
that key off `value.sha256` — `coverage._blob_ok`, `execution.eligibility`,
`research/shadow/information_set`, `research/s5/readiness_t90` — are unaffected,
which is the point of not repointing it.

**Gzip container bytes change for newly written blobs** (deterministic `mtime=0`).
Uncompressed content and blob filenames are unchanged, so no content address
and no existing blob moves.

---

## 10. HANDED TO WS-J — the `coverage.py` patch

I own the capture side; `coverage.py` is WS-J's. The 216 recovered rows do not
become verified in `coverage.py` until this lands there:

```python
def _blob_ok(value: dict) -> tuple:
    blob = (value or {}).get("blob")
    if not blob:
        return False, "RAW_ARTIFACT_NOT_PERSISTED"

    # Prefer a digest that covers the bytes ACTUALLY PERSISTED.
    sha = (value or {}).get("persisted_content_sha256")
    if not sha:
        from nfl.capture.persisted_provenance import load_recovery
        rec = load_recovery().get(blob)
        if rec and rec.get("persisted_content_sha256"):
            sha = rec["persisted_content_sha256"]

    if not sha:
        if (value or {}).get("durability") == "reduce":
            # DO NOT FALL BACK TO value["sha256"] HERE. On a reduce row that
            # field describes the upstream file, which was never stored. Using
            # it is the defect. A distinct code so the 152 read as
            # "cannot be checked", never as "wrong".
            return False, "PERSISTED_DIGEST_ABSENT_HISTORICAL"
        sha = (value or {}).get("sha256")

    if not sha or len(sha) != 64:
        return False, "RAW_SHA256_ABSENT_OR_MALFORMED"

    # Also resolves the 2 rows that cite `...reduced.csv` when only
    # `...reduced.csv.gz` exists (WS13 §3c).
    from nfl.capture.persisted_provenance import resolve_blob, read_blob
    path, _how = resolve_blob(blob)
    if path is None:
        return False, f"RAW_ARTIFACT_MISSING_ON_DISK:{blob}"
    if hashlib.sha256(read_blob(path)).hexdigest() != sha:
        return False, "PERSISTED_CONTENT_SHA256_MISMATCH"
    return True, None
```

Expected effect on the 368: **216 verify, 152 return
`PERSISTED_DIGEST_ABSENT_HISTORICAL`, 0 mismatch.** Expected effect on coverage:
**none** — `n_eligible = 0` on all 368.

Also for WS-J, from the coordinator's RL-8: `assert_no_orphan_blobs` must read
`value.delivery.raw_evidence_blobs` as well as `value.blob`, or
`nfl/vintage/delivered_injury_evidence.df1dd90380b8d720.html.gz` becomes a 49th,
false orphan. Not mine to write.

---

## 11. ESCALATION — RL-7, and it is not mine to resolve

`NFL_PARTICIPATION_RETENTION_DECISION.json` requirement **R7** forbids *"no
reduction / newest-N retention policy"*. `depth_charts` and `weekly_rosters` are
`durability="reduce"` and the depth reducer's recorded strategy is literally
`newest_dt_slice`. **The guard and the policy disagree about whether reduction
is permitted at all.**

This lands squarely on my repair and I am deliberately not resolving it in
either direction. I have made reduction **auditable**; I have not made it
**authorised**, and the two are different questions. Specifically:

- I did **not** widen `reduce_cols` in `registry.py`, even though WS-L shows the
  reduction drops `status` and `pos_slot`, which production consumes — and
  `roster_status.py` reads `status` only from the gitignored raw store. Widening
  the reduction is a change to what is persisted and it collides head-on with a
  policy that may forbid reducing at all.
- If the owner rules reduction **forbidden**, the correct follow-on is to retire
  `durability="reduce"` for these two sources, and the `transformation` block I
  added becomes the record of a practice being ended rather than governed. The
  368 rows stay as historical evidence either way.
- If the owner rules reduction **permitted**, the reduction is now identified,
  versioned, code-hashed and verified against its input on every run, and the
  open question narrows to the one thing still untested:
  `reduce_recoverability_assumption` — whether upstream retains the `dt` history
  — which needs egress and is not mine.

**Owner ruling requested. Do not resolve it by editing either side.**

---

## 12. WHAT THIS PASS CANNOT ESTABLISH

1. **Whether the 6 lost vintages were faithful reductions.** Not recoverable at
   any price: the raw bytes are gone, upstream has restamped, and the reduction
   is irreversible. The 152 rows stay unverifiable and say so. No remedy exists;
   the repair prevents recurrence only.
2. **Whether upstream retains its `dt` history.** Needs a fetch this executor
   cannot make. `reduce_recoverability_checked` stays `false`, correctly. If the
   coordinator wants it closed, it is an outbox item for the networked agent —
   filed through the coordinator, since `docs/AGENT_OUTBOX.md` is WS-J's.
3. **Whether the historical reduction code was identical to today's.** The
   byte-exact match proves the stored blob *is* today's reduction of the
   attested input, which is what verification needs. It does not prove the code
   never changed, and the recovery records that distinction rather than eliding
   it.
4. **Whether the 216 stay re-derivable.** They stay *recorded* — the sidecar is
   tracked. They stay *re-runnable* only while `nfl_vintage/raw/` survives, and
   that store is gitignored and, on the Actions path, ephemeral. This is RL-9
   and it is unresolved in the general case.
