# Return: NFL Greenfield — Owner Directive 3 (G0A build)

**Date:** 2026-09-06 · **Branch:** `claude/nfl-greenfield-architecture-stsxmk` · **Head:** `686ca88`
**NFL-1 was not executed.** No opportunity, skill, simulator, DFS or market
predictive code was written. `board_config.json` was not modified.

---

## 12. Does G0A pass 12/12? — answered first, because it gates everything

**Yes — 12 of 12 PASS, with three residuals named rather than waived, and one
verdict I am flagging as reasonably overrulable.**

Test evidence: **484 assertions across six files, 0 failing**, written by agents
that did not write the code under test.

**The verdict most open to challenge is item 1.** The capture is scheduled and
running for every source reachable from this environment — but `injuries` is
`DEFERRED` (nflverse 404 for 2026) and `official_injury_report` is `BLOCKED /
NO_EGRESS` (nfl.com measured at 000). What is demonstrably running is
`schedules`, `depth_charts`, `weekly_rosters`. **If you read item 1 as requiring
the official cascade, it is a FAIL until the networked agent owns it**, and I
would not argue. The binding constraint is egress, not cadence — a finer poll
does not fix it.

---

## 1. Revised G0A checklist

`nfl/NFL_G0A_CHECKLIST.md` revision 2. Revision 1 (2 PASS / 10 FAIL) preserved.

| # | Requirement | State |
|---|---|---|
| 1 | Kickoff-anchored capture scheduled and running | **PASS** ¹ |
| 2 | Raw bytes before parse | **PASS** |
| 3 | Append-only / content-addressed | **PASS** (rev-1 durability defect resolved) |
| 4 | Complete five-clock provenance | **PASS** ² |
| 5 | sha256 inside execution identity | **PASS** ³ |
| 6 | Leakage quarantine at ingest | **PASS** |
| 7 | Replay test fails if guard removed | **PASS** (10 load-bearing proofs) |
| 8 | Denominator-aware non-null validation | **PASS** |
| 9 | Named `PFR_ID_UNMAPPED` + replay test | **PASS** |
| 10 | Draw-archive schema frozen incl. `cross_game_dependence` | **PASS** |
| 11 | `written_at`/`captured_at`/kickoff ordering | **PASS** |
| 12 | Seal a forecast immutably before kickoff | **PASS** |

**Residuals:** ¹ the official cascade is unreachable here (above); ² 
`effective_for_date` carries the season string, not a game date, so
`assert_usable_for` needs a narrowing step; ³ the identity machinery is proven by
test but not yet exercised by a production run — inherent to a gate that runs
*before* execution, and G1 is its first real exercise.

---

## 2. Implementation manifest

| Artifact | Status | Closes |
|---|---|---|
| `nfl/ingest/allowlist.py` | new | 6 |
| `nfl/ingest/validate.py` | new | 8 |
| `nfl/ingest/identifiers.py` | new | 9 |
| `nfl/ingest/eligibility.py` | new | Directive 3 §6 |
| `nfl/identity/execution_identity.py` | new | 5 |
| `nfl/identity/seal.py` | new | 11, 12 |
| `nfl/capture/schedule.py` | new | 1 |
| `nfl/schema/draw_archive.schema.json` + `DRAW_ARCHIVE_FREEZE.json` | new, frozen `04114a4f…` | 10 |
| `nfl/tools/capture_vintage.py` | **rewritten** | 1–4 |
| `nfl/tests/bypass.py` | new | test standard |
| `nfl/tests/test_{quarantine,denominator_validation,identifier_mapping,seal_ordering,capture_schedule,capture_states}.py` | new | 7 + all |
| `nfl/NFL_EVALUATION_ARMS.md` | new | Correction A |
| `nfl/NFL_COLDSTART_FREEZE_CORRECTION_01.json` | new, **appended** | Correction A |
| `nfl/NFL_G0A_CHECKLIST.md`, `nfl/NFL_EXPERIMENTAL_ROADMAP.md` | revised | — |
| Scheduled trigger `trig_01WvoJ…` | created, 6-hourly | 1 |

---

## 3. Negative-test matrix

Every row is a **seeded violation that must be rejected**. All pass.

| Seeded violation | Required outcome |
|---|---|
| `spread_line` reaches a FORECAST read | `FAIL / MARKET_COLUMN_ACCESS` |
| `result` reaches a FORECAST read | `FAIL / OUTCOME_COLUMN_ACCESS` |
| `weekly_rosters.status` reaches a FORECAST read | `FAIL / POSTHOC_COLUMN_ACCESS` |
| `qb_epa` reaches a FORECAST read | `FAIL / MODEL_DERIVED_COLUMN_ACCESS` |
| Same columns read for ARCHIVE / DESCRIPTIVE | **PASS** (the purpose axis is the point) |
| Unregistered source | `BLOCKED / SOURCE_NOT_REGISTERED`; helper **raises** |
| Column empty on its own denominator | `FAIL / COLUMN_EMPTY_ON_DENOMINATOR` |
| Column blank only where **undefined**, correctly scoped | **PASS** (reverse defect) |
| Column below its floor | `FAIL / COLUMN_BELOW_NONNULL_FLOOR` |
| Denominator selects nothing | `BLOCKED / DENOMINATOR_EMPTY` — says nothing about the column |
| Unmapped pfr id | `FAIL / PFR_ID_UNMAPPED`; row not dropped, not guessed |
| Name-based fallback attempted | `BLOCKED / NAME_FALLBACK_REFUSED` |
| Two pfr ids → one gsis id | `FAIL / CROSSWALK_NOT_INJECTIVE` |
| One pfr id → two gsis ids | `FAIL / CROSSWALK_NOT_WELL_DEFINED` |
| **Partition retrieved after forecast written** | `FAIL / CAPTURE_AFTER_WRITE` |
| Forecast written at **or after** kickoff | `FAIL / WRITE_AFTER_KICKOFF` |
| Cache hit restamped as fresh retrieval | `FAIL / …CACHE_RETRIEVAL_CONFLATED`, five clocks intact |
| Consumed partition absent from identity | `FAIL / PARTITION_NOT_IN_IDENTITY` |
| **Any consumed partition's sha256 altered by one char** | **fingerprint changes** |
| Re-seal same id, different content | `FAIL / SEAL_IMMUTABLE_VIOLATION` |
| HTTP 200, zero bytes | `FAIL / EMPTY_PAYLOAD_200` |
| Header + blank lines, no data rows | `FAIL / HEADER_ONLY_PAYLOAD` |
| 200 with no own `Last-Modified` (even if a redirect carried one) | `FAIL / SOURCE_TIMESTAMP_ABSENT` |
| 404 on a **required** source | `DEFERRED / SOURCE_NOT_YET_PUBLISHED`, owed |
| 404 on an **optional** source | `NOT_APPLICABLE` with mandatory reason |
| No HTTP response | `BLOCKED / NO_EGRESS`, cause NETWORK |
| Eligibility closed with `weekly_rosters.status` | `FAIL / ELIGIBILITY_SOURCE_NOT_RECOGNISED` |
| Missed due capture | surfaced as debt, not silent absence |
| Unschedulable row + `through` filter | debt survives the filter |

**Load-bearing proofs (10).** Each re-runs its path with the guard stubbed out
and asserts the detection *vanishes*. `nfl/tests/bypass.py` is itself tested to
reject a test that would pass with the guard deleted.

---

## 4. Corrected clock / provenance specification

**Enforced order:** `source / effective → retrieved_at (captured_at) → written_at → kickoff`

Minimum, per consumed partition: `retrieved_at ≤ written_at < kickoff`, and no
partition retrieved after `written_at` may appear in the execution identity.

The earlier `written_at < captured_at` was backwards and would have licensed a
forecast to consume bytes that had not arrived.

**The five clocks are not collapsed.** `source_timestamp`, `effective_for_date`,
`retrieved_at`, `generated_at`, `cache_timestamp` stay distinct; per-partition
consistency — including the cache-restamp case — delegates to
`v8/governance/provenance.py`, which already encodes it and carries the V7
weather defect as a replay test. An absent source clock is
`SOURCE_TIMESTAMP_ABSENT`, **never backfilled from `retrieved_at`**.

Tested: timezone-offset laundering (`13:00-04:00` against a `17:00Z` kickoff) is
refused; `>=` at exactly kickoff is refused.

---

## 5. Live capture schedule

Anchored to **each game's kickoff**, never a universal daily assumption.
Deadlines at **16:00 America/New_York**; inactives at **kickoff − 90 min**; DST
handled (Friday deadline is `20:00Z` in September, `21:00Z` in December).

| Game day | Practice reports | Final status | Confirmed? |
|---|---|---|---|
| **Sunday** | Wed, Thu (K−4, K−3) | Fri (K−2) | **yes** — externally reported |
| **Monday** | Wed, Thu (K−5, K−4) | Fri (K−3) | no — DERIVED |
| **Thursday** | Mon, Tue (K−3, K−2) | Wed (K−1) | no — DERIVED |
| **Saturday** | Wed, Thu (K−3, K−2) | Fri (K−1) | no — DERIVED |
| **Midweek** | K−2 | K−1 | no — DERIVED fallback |

Only the Sunday pattern and the two fixed times were externally reported;
everything else is flagged `confirmed=False` in every plan entry it produces, so
an inference is never presented as the official calendar.

Poll cadence is **6-hourly** (`trig_01WvoJ…`), with the kickoff-anchored plan
determining what is due and `missed_captures` surfacing gaps as debts. **The
T−90min inactives capture is not reliably reachable at that cadence**, and its
source is unreachable here regardless — assigned.

---

## 6. Durable storage policy, by source

| Source | Policy | Per capture |
|---|---|---|
| `injuries` | **commit raw bytes**, gzipped | ~0.2 MB |
| `official_injury_report` | **commit raw bytes** when a capable agent runs it | — |
| `schedules` | **commit raw bytes**, gzipped | 0.50 MB |
| `depth_charts` | hash + **newest-`dt` slice**, gzipped | 0.012 MB |
| `weekly_rosters` | hash + reduced projection, gzipped | 0.013 MB |

**Total 532 KB per capture**, against 23 MB before. Gzip is lossless, so the
recorded sha256 remains the digest of the **original** bytes.

Depth charts and rosters re-ship their whole history every capture; storing them
whole daily would retain the same rows ~170 times. The reduction rests on an
assumption recorded in every manifest row as
`reduce_recoverability_assumption` with `reduce_recoverability_checked: false` —
**it is stated and unverified, not silently relied on.**

Git is not treated as durable in principle; it is the durable store this
environment has, and the policy is sized so using it stays honest.

---

## 7. Arm A — static fixed prospective holdout

`nfl/NFL_EVALUATION_ARMS.md`.

The frozen specification held at **`g = 0` for the entire season**, which sets
`θ_off = θ_def = 0` **exactly** and leaves only the prior-season component:

```
mu_off_i = L + lambda_off * (OFF_i - L)
mu_def_i = L + lambda_def * (DEF_i - L)
forecast(i vs j) = mu_off_i with mu_def_j, ± h/2
```

Consumes prior-season finals from the frozen `games.csv` snapshot, the franchise
map and the frozen constants. **No 2026 result, ever.** Every symbol is already
defined in the frozen spec — **no new constant, no re-parameterisation**.

Its forecast for a team is the same number in Week 1 and Week 18. It will lose to
Arm B on accuracy; that is not its job. Its job is to be the one arm whose result
cannot be explained by within-season adaptation. Cost: one number per team.

## 8. Arm B — frozen-specification prequential

The already-frozen `θ_g = g/(g+M)` transition (`M_off = 8.8764`,
`M_def = 23.2199`), consuming 2026 results from strictly earlier weeks **only by
the rule fixed before Week 1**, with every forecast restricted to information
available before its own timestamp — enforced structurally by
`nfl/identity/seal.py`.

**Described as "frozen-specification prequential evidence over the 2026 season."
Never as an untouched 272-game fixed holdout.**

**The A-vs-B contrast is worth more than either alone:** identical constants,
differing *only* in whether the season's own results are consumed. Their
difference is a clean estimate of what the within-season update is worth — a
comparison unavailable if only B is run.

---

## 9. Confirmation: the freeze was not silently rewritten

**Verified cryptographically, not asserted.** `nfl/NFL_COLDSTART_FREEZE.json` was
**not edited**. A correction record was **appended** as
`nfl/NFL_COLDSTART_FREEZE_CORRECTION_01.json`.

```
spec sha256 at original freeze : b356ecaabd49125b0286b1c1...
spec sha256 after correction   : b356ecaabd49125b0286b1c1...
IDENTICAL                      : True
```

**No constant in `C3_COLD_START_SPEC.md` §7.2 was altered.** T1 (retain the 2002
floor) and T3 (retain `h`) are recorded as owner-resolved and closed.

---

## 10. ffopportunity classification — A3 can be closed

**Repository evidence agrees with the external finding**, and the two were
reached independently: W8 flagged that its oracle framing rested on *schema
inference, not documentation*, and named this as the claim it most wanted
checked. The networked researcher's source review answers exactly that —
expected-points does not consume the realised numeric outcome of the same play,
but does consume realised **opportunity identity and context**: who actually
received the target or carry is already known.

**Classification: `REALIZED-OPPORTUNITY ORACLE BENCHMARK`.**

- **Useful for** bounding the conversion layer *conditional on realised
  opportunity* — which is what makes W8's bracket (prior-weeks-mean r = 0.5907
  below, expected-points r = 0.8419 pooled / 0.6853 within-player above)
  meaningful, and it supports the finding that the hard part is projecting
  opportunity rather than converting it.
- **Not** a deployable forecasting feature. **Not** a promotion gate.

**A3 is closed.** Recommend recording it as `REJECTED — ORACLE INPUT` in the
feature registry, so it is not re-proposed as an untested feature.

---

## 11. `PREDICTION_TIME_ELIGIBILITY_UNAVAILABLE` — status

**Implemented** (`nfl/ingest/eligibility.py`) and **open as a declared debt**.
Returns `BLOCKED` with cause `DEPENDENCY`.

- Any NFL-2 component needing gameday eligibility **refuses**.
- **NFL-1's team baseline is declared outside the debt** and is not blocked — it
  consumes prior-season team scores only. The debt blocks what it should and
  nothing else.
- Closes only via a **declared** source: official inactives, official
  transactions, or the official gameday designation at its publication time.

**The escape hatch was a real defect and is fixed.** The function previously
accepted **any** non-empty string as a closing source — including
`weekly_rosters.status`, the exact post-hoc field its own docstring quarantines.
Found by adversarial test; it now validates against the declared list and returns
`ELIGIBILITY_SOURCE_NOT_RECOGNISED`. That one line was the only place the
substitution Directive 3 §6 forbids was actually available.

---

## What the adversarial tests found, and why it is the main result

The tests found **twelve real defects in the controls I had just built**. None
was worked around. Three reproduced the exact failure classes this repository
catalogues — *inside the guards written to prevent them*:

1. **`is_null` did not recognise `float('nan')`**, which is what pandas yields
   for a blank numeric cell. Fed the real motivating case — `ngs_air_yards`, 0
   non-null of 45,919 — through a pandas reader, the validator returned **PASS at
   1.0 non-null**. Class A, inside the Class A guard.
2. **`HEADER_ONLY_PAYLOAD` counted newlines, not data rows**, so a header padded
   with blank lines became a recorded vintage with a durable blob written.
3. **The model-derived count said 45 over a tuple of 41 while the provenance
   audit said 31.** Three copies, three numbers, nothing comparing them. Class C.

Plus: 13 leaking columns missing from the quarantine (including `qb_epa`, at
availability 1.0000 on dropbacks — precisely what a QB model reaches for); the
eligibility escape hatch; an "injectivity" check that tested well-definedness, so
a crosswalk merging two players into one loaded as PASS with the word *injective*
in its detail; a redirect hop's `Last-Modified` stamped onto a payload carrying
none; and a `through` filter that dropped the unschedulable debt it exists to
raise.

**The seal was the one control that survived unchanged: 97 of 97**, including the
test that matters most — a one-character change to any consumed partition's
sha256 moves the execution identity fingerprint. That is the property
`SIM_FORMULA` lacked, and it is why MLB's M0 can be substituted without detection.

---

## One factual disagreement with the external research, recorded

The networked researcher reports the nflverse injury stream "died after the 2024
season". **Measured here: `injuries_2025.csv` is complete — 6,068 rows across all
18 REG weeks.** Directive 3's instruction is robust either way and I followed it
(capture the official source; treat nflverse as reconciliation), so nothing in
the build depends on resolving this. But the premise as stated is contradicted by
the file on disk, and it should be reconciled before anyone plans around it.
They may be reading a status page I cannot reach.

---

## What is still owed

- **NFL-1 remains blocked** and was not executed. Returning for authorisation.
- **Item 1's residual** is yours to judge; I have flagged it as reasonably
  overrulable.
- **Assigned, not blocked** (outbox §33 + new): the official injury cascade,
  official inactives and transactions, prediction-time eligibility, and Hard Rock
  NFL market list and ladder depth.
