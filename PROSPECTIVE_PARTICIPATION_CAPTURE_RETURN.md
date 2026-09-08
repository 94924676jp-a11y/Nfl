# PROSPECTIVE PARTICIPATION CAPTURE RETURN

Infrastructure to **detect and capture** the participation inputs prospectively.
No data was manufactured. Nothing was used predictively. Nothing was promoted.

Executed 2026-09-08.

---

## Canonical state

| | |
|---|---|
| Start HEAD | `a993fa6` — receiving information gap return |
| Implementation commit | `8e9409a` — all code, tests, workflow and the live preflight row |
| Final HEAD | the commit stamping these hashes into this table, one commit later |
| Repository | `94924676jp-a11y/Nfl`, branch `main` |
| G0A | unchanged, **11/12** |
| NFL-1 | unchanged, **NOT AUTHORIZED** |

Files added:

| File | Role |
|---|---|
| `nfl/capture/availability.py` | the five availability states, schema fingerprint, first-seen ledger, record verification, eligibility record, four named guards |
| `nfl/tools/watch_availability.py` | the probe: raw-before-parse, content-addressed, append-only |
| `.github/workflows/nfl-availability.yml` | the unattended watch |
| `nfl/tests/test_availability_watch.py` | 114 assertions, 20 sections, 4 guard-deletion proofs |
| `nfl/availability_manifest.jsonl` | the append-only observation log |

Files changed:

| File | Change |
|---|---|
| `nfl/capture/registry.py` | two `watch_only=True` specs; `can_discharge` refuses watch-only for every kind |
| `nfl/tools/capture_vintage.py` | skips watch-only specs; reports them as deliberately elsewhere rather than as silence |

---

## Sources

| | `pbp_participation` | `snap_counts` |
|---|---|---|
| URL | `…/releases/download/pbp_participation/pbp_participation_{season}.csv` | `…/releases/download/snap_counts/snap_counts_{season}.csv` |
| Canonical location | the project's existing nflverse release host, unchanged | same |
| Authority | `INDEPENDENT_MIRROR`, rank 20 | same |
| Licence | nflverse-data is **CC BY 4.0** (read from `LICENSE.md`) | same |
| Serves capture kinds | **none** | **none** |
| `watch_only` | **True** | **True** |
| Historical coverage | published and populated **2016–2025** | published **2016–2025** |
| Accepted schemas | **two**: 20 columns 2016–2022, 26 columns 2023–2025 (a strict superset appending the six `offense_names`…`defense_numbers` fields) | **one**: 16 columns, stable across every season |

Both are registered because they are what the P component is built from, and
neither was in the capture set before today.

---

## Current live state

Measured 2026-09-08 by running the actual workflow.

| Source | HTTP | Availability | Source clock | Bytes | Schema |
|---|---|---|---|---|---|
| `pbp_participation` 2026 | **404** | **`NOT_PUBLISHED`** | **none — and none claimed** | none | n/a |
| `snap_counts` 2026 | **404** | **`NOT_PUBLISHED`** | **none — and none claimed** | none | n/a |

The origin answered: `HTTP/1.1 404 Not Found`, `content-type: text/plain`,
`content-length: 9`, `Date: Tue, 08 Sep 2026 13:28:42 GMT`. That Date is
recorded as `probe_response_date` — the clock of the **error response** — and
**not** as `source_timestamp`. A file that does not exist has no
`Last-Modified`, and stamping the error's clock onto the artifact would be the
same substitution the V7 weather defect was. *(This was a real defect in my
first version, found by reading the emitted row and fixed before commit; a test
now asserts the absence.)*

To prove the `AVAILABLE` path is exercised on real bytes rather than only on
synthetic ones, the same workflow was run against **2025**, which is published.
Written to a scratch store, deliberately not committed:

| Source | HTTP | Bytes | Cols | Rows | `Last-Modified` | sha256 |
|---|---|---|---|---|---|---|
| `pbp_participation` 2025 | 200 | 49,094,943 | 26 | 45,184 | 2026-02-10T18:54:08Z | `59069adfee7b0f46…` |
| `snap_counts` 2025 | 200 | 2,401,193 | 16 | 26,612 | 2026-02-09T13:39:50Z | `80b02a6e511aa202…` |

Both verified (`RECORD_VERIFIED`), both first-seen recorded, both
`authorized=False`. Re-running immediately produced `content unchanged` and
`FIRST_SEEN_ALREADY_RECORDED` — append-only and write-once hold against real
bytes, not just seeded ones.

---

## Capture semantics

**Order of operations.** `request → bytes arrive → RAW BYTES STORED → hash →
parse`. The blob is written before anything reads it, so a parser defect cannot
destroy the evidence of what arrived, and a later parser can be re-run against
the original artifact. `parser_version` is recorded downstream of the blob and
never upstream of it.

**Recorded per observation:** source, season, URL, HTTP status, full final-block
response headers, `requested_at`, `retrieved_at`, `probe_response_date`,
`source_timestamp` + which header supplied it, content length, `n_bytes`,
sha256 of the uncompressed bytes, blob path, sidecar path, schema fingerprint,
row count, execution identity (`watch_id`), and `parser_version`.

**Clocks, kept apart.**

| Clock | Meaning here |
|---|---|
| `requested_at` | when we started asking |
| `retrieved_at` | **when the bytes arrived** — never stamped before the request, because the origin's own Date then reads later than our retrieval and provenance validation correctly refuses that as impossible |
| `source_timestamp` | the artifact's `Last-Modified`, attached **only** on a path where an artifact arrived |
| `probe_response_date` | the error response's own clock, under its own name |
| `cache_timestamp` | `None` — this always fetches; recorded rather than omitted so "live" and "unknown" cannot read alike |
| `generated_at` | the wrapper |
| `effective_for_date` | the **season**, never a date derived from the file's own clock |

**Do not restamp cache hits.** Every blob carries a write-once sidecar holding
`first_retrieved_at`. It is written when the bytes are first seen and never
touched again. The **current** retrieval time lives on the manifest row, which
is a different fact. Merging them would make every re-observation look like a
fresh arrival. Independently, `provenance.validate` still refuses a record that
was served from a cache while claiming a fresh retrieval
(`CACHE_RETRIEVAL_CONFLATED`), and that is asserted directly.

**Immutability.** Blobs are content-addressed (`{source}_{season}.{sha16}.csv.gz`)
and gzipped; compression is lossless so the recorded sha256 is still the digest
of the original bytes. A digest already on disk is not rewritten. Identical
bytes seen again produce a **new manifest row and no new blob** — that is a
measurement, not a duplicate. Changed bytes produce a second blob and the first
survives.

**Schema fingerprint:** ordered column names, an order digest, inferred types
per column (int / float / str / empty), row count, and a substantive digest over
the sorted body. The digest is over **ordered names, not a count** — a
column-count check is what let `injuries_2025.csv` drop `date_modified` while
keeping 16 columns.

---

## Availability watcher

| | |
|---|---|
| Workflow | `.github/workflows/nfl-availability.yml` |
| Schedule | `17 6,18 * * *` — twice daily |
| Question | "Has the 2026 source become published, or changed?" |
| Discharge permissions | **NONE.** No G0A item, no T-90 target, no capture kind. |

Why twice daily and not `*/30`: the question is whether an annual artifact has
appeared, which does not change on a 30-minute timescale, and a slower poll keeps
this visibly distinct from the perishable cascade. A missed firing only delays an
observation and cannot lose one — the artifact is still there next time. That is
the opposite of the T-90 windows, where a missed firing loses the state forever.

**The separation from T-90 is enforced three independent ways, not asserted:**

1. the registry marks both sources `watch_only`, so `capture_vintage._sources()`
   never fetches them — proven by test J2;
2. `serves_kinds` is empty **and** `can_discharge` returns False for watch-only
   sources regardless, so a kind added by mistake cannot arm one;
3. `assert_no_discharge` FAILS any record carrying `discharges`,
   `discharge_claims`, `serves_kinds` or `execution_target`, and the workflow
   **runs the test file before it probes anything** — if the separation ever
   breaks, the watch does not run.

The emitted row carries `discharges: []`, `watch_kind:
periodic_availability_probe`, and **no `game_id`**. It is not attributed to a
game, so it cannot even be argued into a coverage claim. `nfl-capture.yml`
already had a coverage-in-time argument corrected once for doing exactly that.

---

## Predictive eligibility

`availability.eligibility_record()` returns **two answers that are deliberately
not merged**:

| Field | What it is |
|---|---|
| `ordering_ok` | a fact about clocks: `retrieved_at < forecast.written_at < kickoff`, **plus** record verification (the blob exists and hashes as claimed) and the future-clock check |
| `authorized` | **always `False`**, code `NOT_AUTHORIZED_BY_OWNER` |

Merging them is how "the timestamps line up" becomes "the model may read it",
which is a promotion nobody made. A satisfied ordering is explicitly tested to
leave `authorized=False` (section C2).

With no forecast supplied, `ordering_ok` is `None` with code
`NO_FORECAST_TO_JUDGE` — **UNEVALUATED, which is not the same as satisfied.**

**Required later, not now:** an authorised forecast-time record, the standing
provenance requirements, and an owner authorization that this task does not
grant and does not anticipate. **NOT authorized now:** any model consumption of
either source, any P feature built from 2026 bytes, any promotion.

---

## Historical-vintage guard

Proof that no final-file timestamp is treated as point-in-time evidence:

- Both watched specs declare `narrow_to_kind = None` and `narrow_method = None`.
  They derive **no** date interval from their own `Last-Modified`. By contrast
  `injuries` and `schedules` **do** narrow that way — so the difference is a
  recorded decision, not an absence. Asserted in section L.
- `narrow_evidence` on each states why, in the artifact itself.
- Measured: `pbp_participation_2025.csv` reads `10 Feb 2026` and
  `pbp_participation_2024.csv` reads `04 Sep 2025`. Both are **after** their
  seasons. Both are final writes and neither says anything about in-season
  availability in either direction.
- `effective_for_date` is the **season string**, never a derived date.
- **No backfilled vintages.** The first-seen ledger is write-once; a backdated
  entry cannot displace a real observation, and that is asserted with a seeded
  2020 date against a real 2026 one.
- Historical final files are used for **one** thing: reading the accepted column
  names into `ACCEPTED_SCHEMAS`. That use is legitimate precisely because it is a
  claim about column names and carries no timestamp — asserted in section L.

---

## Adversarial tests

`nfl/tests/test_availability_watch.py` — **114 assertions, 20 sections, 0
failures.** No network: `subprocess` is replaced inside the module under test,
so every HTTP state is seeded rather than waited for.

| Required case | Section | Result |
|---|---|---|
| 404 becomes NOT_PUBLISHED, not PASS | A | `DEFERRED` / `NOT_PUBLISHED`, debt owed, no bytes and **no artifact clock** claimed |
| 200 HTML/error body rejected as data | B | `BODY_IS_HTML_NOT_DATA`, `BODY_IS_ERROR_TEXT` |
| empty file | B | `EMPTY_PAYLOAD_200` |
| malformed CSV | B2 | `CSV_RAGGED_ROWS` — see the finding below |
| schema drift | E | `SCHEMA_CHANGED`, fails closed, raw preserved |
| reordered columns | E | `SCHEMA_CHANGED` — same names, different order is drift |
| duplicate identical bytes | F | new manifest row, no new blob, one blob on disk |
| changed bytes same source clock | F2 | second blob, both survive, change visible without trusting the clock |
| cache hit does not restamp retrieved_at | F3 | sidecar keeps the original; row carries the current; `CACHE_RETRIEVAL_CONFLATED` also asserted |
| source clock later than retrieval | G | `PROBE_PROVENANCE_INVALID` / `PROVENANCE_IMPOSSIBLE`; bytes stored anyway |
| parser cannot alter raw SHA | C, F | sha256 is of the uncompressed bytes, computed before parsing; blob re-hashes to it |
| first-seen only once | I | `FIRST_SEEN_ALREADY_RECORDED` |
| later source update preserves first-seen | I | stored value is still the first date and first digest |
| periodic capture cannot discharge T-90 | J | `discharges: []`, no `game_id`, no `execution_target`, guard confirms |
| participation cannot discharge injury/inactive | J, J2 | `can_discharge` False for practice / final_status / inactives |
| wrong season | D | season on the row, URL carries that season only |
| wrong source | D | unregistered → `BLOCKED`; registered-but-not-watch-only → `WATCHED_SOURCE_NOT_WATCH_ONLY` |
| future retrieved_at | G2 | `RETRIEVED_AT_IN_FUTURE` |
| manually forged availability record | H, A2 | `RECORD_DIGEST_MISMATCH`; `UNAVAILABLE_RECORD_CARRIES_BYTES` |
| raw blob missing | H | `RAW_BLOB_MISSING` |

Plus, beyond the required list: header-only payloads, header-plus-blank-lines,
`AVAILABLE` with no evidence named at all, and both accepted participation
schemas accepted without a false drift alarm.

### Two defects found in my own code by these tests, and fixed

1. **A malformed CSV passed as `AVAILABLE`.** Python's `csv` reader does **not**
   raise on an unterminated quote — it swallows the rest of the file into one
   field and returns a single tidy-looking row, so my `csv.Error` handler never
   fired. Fixed by comparing every row's field count against the header:
   `CSV_RAGGED_ROWS`. A reader that took the first *n* fields of each row would
   have silently mis-assigned every column after the break.
2. **A 404 row carried `source_timestamp`** taken from the error response's
   `Date` header, giving a file that does not exist a clock. Fixed as described
   under *Current live state*.

Both are recorded rather than quietly corrected, because a test suite that finds
nothing is usually a test suite that is not looking.

Repository-wide: **234 test functions, 0 failures** (was 214 before this work).

---

## Guard deletions

Four load-bearing proofs, above the required minimum of two. Each asserts both
halves: the seeded violation is caught with the guard in place, and is **not**
caught with the guard bypassed.

| Guard | Seeded violation | With guard | Bypassed |
|---|---|---|---|
| `assert_body_is_data` | HTTP 200 whose body is `Not Found` | `BODY_IS_ERROR_TEXT` | passes through and a blob is stored over an error page |
| `assert_schema_accepted` | a 27th column appended | `SCHEMA_CHANGED`, fails closed | the unknown file is recorded `AVAILABLE` |
| `assert_not_future` | `retrieved_at` one day ahead, on an otherwise verifiable record | `RETRIEVED_AT_IN_FUTURE` | the ordering check proceeds as if the clock were sane |
| `assert_no_discharge` | a row carrying `discharges: ['inactives']` | `AVAILABILITY_WATCH_CLAIMED_A_DISCHARGE` | the claim stands |

The `assert_body_is_data` case is not hypothetical. Measured 2026-09-08 on this
very release host: `nextgen_stats/ngs_receiving.csv.gz` answers **HTTP 200 with a
body of `Not Found`**. A byte-count check passes it.

---

## Live preflight

Run as `python3.12 nfl/tools/watch_availability.py --season 2026`:

```
availability watch 20260908T132841Z  season 2026
  kind=periodic_availability_probe  discharges: NOTHING (no G0A item, no T-90 target, no capture kind)
  DEFERRED       NOT_PUBLISHED   pbp_participation   SOURCE_NOT_YET_PUBLISHED
  DEFERRED       NOT_PUBLISHED   snap_counts         SOURCE_NOT_YET_PUBLISHED
appended 2 row(s) to nfl/availability_manifest.jsonl
```

Exit code 0. Two rows appended. **No `nfl/availability_first_seen.json` exists
and no `nfl/availability_raw/` directory exists** — because nothing has been
observed available. Absence is recorded as absence, and neither file is created
speculatively.

The infrastructure is complete. The source is unpublished. Those are different
statements and the second is not a defect in the first.

---

## FINAL STATE

### `CAPTURE_PATH_READY_SOURCE_UNPUBLISHED`

The capture path is built, tested against 20 adversarial cases with four
guard-deletion proofs, run live against both sources, and separately proven
end-to-end on real bytes via the 2025 files. Both 2026 sources return 404 and are
recorded as `NOT_PUBLISHED`, which is the expected valid result today.

---

## OWNER DECISION NEEDED

**One decision, and it has to be made before the source publishes, because the
first capture is the one that cannot be redone.**

> **What retention policy applies to participation blobs once 2026 publishes?**

The measured facts. One distinct snapshot pair costs **3.4 MB** committed —
`pbp_participation` 2.9 MB gzipped (49.1 MB raw), `snap_counts` 0.5 MB (2.4 MB
raw). The repository's `.git` is currently **65 MB**. In-season these files grow
weekly, and only *changed* content creates a blob, so the cost depends entirely
on how often upstream rewrites them — which is **not known** and which the watch
will measure. Weekly rewrites over an 18-week season is roughly **+61 MB**, about
doubling the repo. Daily rewrites is roughly **+430 MB**.

Three options, and the registry already carries the machinery for the second:

- **`commit_raw`** — keep every distinct version. Full fidelity, unbounded
  growth. This is what the code does today, and it is what I would leave in
  place if the answer is "decide later", because dropping bytes is the only
  irreversible choice here.
- **`reduce`** — commit a column projection, keep the full bytes ephemeral. What
  `depth_charts` already does. Cheap, and it makes a later full re-derivation
  depend on upstream still holding the history.
- **newest-N** — keep the last N versions. Bounded, and it silently discards the
  early-season vintages, which are the ones a point-in-time study would most
  want.

I am not choosing. Fidelity against repository size is a value judgement, and the
irreversible half of it is the owner's.
