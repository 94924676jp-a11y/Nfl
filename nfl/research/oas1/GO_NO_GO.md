# OAS1 Go / No-Go, after tranche 1

**HEAD at measurement: `638af4f`, plus the uncommitted tranche-1 work.**
Everything below was measured on 2026-09-17, on files this repository now
holds. **Fitting Week-2 OAS1 is NOT YET LAWFUL: three of the six blocking
gates are still NO.**

## The table

| # | Gate | Before | After tranche 1 | Evidence |
|---|---|---|---|---|
| 1 | Governed `pbp` capture exists with at least one hashed 2026 capture | NO | **YES** | 3 captures: 2026 `b69f55a172965e16` (2,756×372), 2025 `2f135887790a013f` (48,771×372), 2024 `23370d5d10f8104d` (49,492×372). Blob round-trip verified by hash |
| 2 | `epa` target-only exemption, written, tested, limited to target use | NO | **YES** | `allowlist.assert_oas1_epa_target`, three independent guards; general quarantine untouched |
| 3 | A prior-season OAS1 fit supplying `theta_prev` | NO | **NO** | not built. Its input now exists and is proven identified (one graph component, rank 64/66) |
| 4 | Baselines B0–B5 implemented and forward-chain-clean | NO | **NO** | not built |
| 5 | Pre-declaration committed with literal thresholds a test reads from code | NO | **NO** | not written |
| 6 | Team normalization total across both seasons in scope | NO | **YES** | total over all 3 pbp captures and over 1999-onward schedules; 42/42 checks |
| 7 | Evaluator supports continuous targets, MAE/RMSE/CRPS | NO (package) | **PARTIAL** | CRPS exists and is imported, not duplicated. MAE/RMSE for a continuous target are not in `SCORERS` |
| 8 | Adjustment registry with the doubling test | NO | **NO** | not blocking for research-only OAS1; blocking before any downstream consumer |
| 9 | Freshness invariant registered and blocking | PARTIAL (package) | **YES** | `current_season_input_freshness` is HARD and refuses live boards today |
| 10 | 2026 pbp available with the required fields | YES | **YES** | confirmed; see the correction below on which file |
| 11 | Pressure data available in-season | NO | **NO** | not required for V1; not re-verified this pass |
| 12 | Commercial-use licensing resolved | UNCLEAR | **UNCLEAR** | owner decision, not an engineering one. Unchanged |

**Verdict: NO-GO on fitting Week-2 OAS1.** Gates 3, 4 and 5 remain, and gate 5
must be committed before any fitted number exists.

## What the package got right, verified at HEAD

- **Zero `pbp` captures.** 4,492 manifest records, 12 sources, no `pbp`. The
  only pbp-adjacent entry was `pbp_participation`, 380 times, as
  `NOT_APPLICABLE / WATCH_ONLY_SOURCE_NOT_CAPTURED_HERE`. Exact.
- **`epa` refused for `Purpose.FORECAST`** with `MODEL_DERIVED_COLUMN_ACCESS`,
  along with `success`, `qb_epa`, `air_epa`, `yac_epa`, `cp`, `cpoe`, `xpass`,
  `wp`; `spread_line` and `total_line` refused as `MARKET_COLUMN_ACCESS`.
- **The identification collapse, reproduced to the number.** 66 design
  columns, rank 32, deficiency 34, and an offense-defense graph of exactly 32
  components of 2 nodes — **independently for both play classes**.
- **The 2026 frame.** 2,756 rows, 372 columns, 2026 only, week 1 only, REG
  only, 16 games, 32 clubs, 32 null `epa`. Every cell of its §B.1 table.
- **The GitHub redirect artifact.** Observed live: an HTML block with
  `Content-Length: 0` precedes the real `200 OK` with `Content-Length:
  1077501`.

## Four corrections, each measured

**1. `LAR` does not exist in either captured source, and `OAK`/`SD`/`STL` do.**
The package calls inconsistent `LA` vs `LAR` usage the hazard that "blocks any
multi-season join". Measured: `pbp` 2024, 2025 and 2026 carry **exactly the
same 32 codes** with no `LAR`; `schedules` (1999 onward) carries **35** codes,
the extras being `OAK`, `SD` and `STL`, and **still no `LAR`**. The real
hazards are the three relocations, and they bite only if OAS1's scope reaches
2019 or earlier. **At the declared V1 scope (2025 + 2026) normalization is the
identity map**, which is worth saying plainly rather than implying work was
done. `LAR` is kept in the table defensively and labelled NOT OBSERVED so its
presence is never read as evidence it occurred.

**2. There are TWO structural redundancies, not one.** The package says ridge
resolves "the dummy-variable redundancy", singular. On the full 2025 regular
season, 19,982 pass plays, fully connected:

| design | cols | rank | deficiency |
|---|---|---|---|
| intercept + 32 off + 32 def + home | 66 | 64 | **2** |
| no intercept, 32 + 32 + home | 65 | 64 | 1 |
| intercept + 32 + 32, no home | 65 | 63 | 2 |

Every play has exactly one offense and exactly one defense, so both dummy
families sum to 1 on every row and each is collinear with the intercept.
Dropping the intercept removes one; the second survives because the families
are then collinear with each other. This makes the Week-1 arithmetic **exact**:

    34 = 32 unidentified within-component splits + 2 structural redundancies

**3. The primary source is the `.csv.gz` release, not the parquet.** The
parquet is real and reachable (200, 1,355,784 bytes) but reading it needs
`pyarrow`, which is absent and not installable here — this interpreter is an
externally-managed environment and `pip install` exits under PEP 668.
`play_by_play_2026.csv.gz` (1,077,501 bytes) was verified to carry the
identical frame, and it is the format every existing capture already uses. The
parquet URL is recorded in every manifest row as the sibling that was *not*
fetched.

**4. Play counts differ from the package's, and the vintage is why.** Using the
package's own §K.1 `play_class` rule the modelling subset is **1,952** rows
(1,150 pass, 802 rush) against its 1,911 (1,069 / 842), and scrambles are
**79** against its 75. Two causes, not one: the rule catches plays whose
`play_type` is null or `no_play` but which still carry a `pass_attempt` or
`rush_attempt` flag, which `play_type in {pass, run}` misses; and the file was
republished — the capture's `Last-Modified` is 2026-09-17T14:17:35Z while the
package measured earlier the same day. **Neither changes the identification
result**, which is identical.

## What tranche 1 built

| Module | What it is |
|---|---|
| `nfl/ingest/pbp_capture.py` | fetch, validate, archive verbatim, decide the vintage, append one manifest row |
| `nfl/ingest/allowlist.py` (extended) | `assert_oas1_epa_target`, `assert_no_epa_in_features`, `EPA_DERIVED` |
| `nfl/research/oas1/normalize_teams.py` | one table, `normalize`, `assert_total`, `assert_thirty_two` |
| `nfl/tests/test_pbp_capture.py` | 67 checks, every one a refusal |
| `nfl/tests/test_oas1_team_normalization.py` | 42 checks, over the real blobs |
| `nfl/tests/test_oas1_identification.py` | 29 checks, the collapse frozen |

## Two defects the work found in itself

**A capture identity with one-second resolution.** `capture_id` was a bare
`%Y%m%dT%H%M%SZ` stamp, matching the existing captures. Two captures of
*different* bytes inside the same second collided and the second — a genuinely
new vintage — was refused as an overwrite. The partial-week test hit it
immediately, which is the case that matters, since nflverse republishes the
running season several times a day. Now sub-second plus the digest, and the
guard narrowed to what it actually protects: re-using an identity for
different bytes.

**A silently dropped provenance timestamp.** The first live 2026 capture
recorded `source_timestamp: None` while the server had sent `Last-Modified:
Thu, 17 Sep 2026 14:17:35 GMT`. The header dump was truncated to 4,000
characters for storage and then parsed from the truncated copy; through a
GitHub redirect the real asset's headers come last, and `Last-Modified` sat at
character 5,547 of 6,108. Parsing now happens on the full text before
truncation. **Both capture rows are preserved** — the first as the record of
the defect, marked `last_mod=None`; the second complete and
`content_unchanged: true`, confirming identical bytes and a single
content-addressed blob.

## Standing constraints honoured

No sportsbook column is read; `spread_line` and `total_line` remain refused and
the capture module cannot reach the allowlist to widen anything. No commercial
projection is used. CS1 untouched. No promotion, no gate weakened, no seal
rewritten. The general `epa` quarantine is intact and still refuses feature use.

## Next tranche, in the package's own order

Gate 3 (prior-season OAS1 fit on the now-captured, now-proven-identified 2025
season), then gate 4 (B0–B5, before the candidate), then gate 5 (the
pre-declaration with literal thresholds, committed before any fitted number).

**The expected outcome stays on the record in advance:** OAS1 most likely beats
B0 and B1 comfortably, beats B2 and B3 modestly, and does not clearly beat B5
in the first weeks. If that happens, B5 ships and OAS1 is recorded as a
measured negative for early-season weeks.

**V2 NOT YET EARNED**
