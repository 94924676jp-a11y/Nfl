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

---

# Gate table after the ownership tranche — 2026-09-17, HEAD `df5fd88`

Every row is YES or NO. Nothing here is "partial"; where a thing is genuinely
undecided it says so in its own row and is not counted as a pass.

| # | Gate | Status | Evidence |
|---|---|---|---|
| 1 | Governed `pbp` capture with at least one hashed 2026 capture | **YES** | 3 content-addressed blobs; 2026 `b69f55a172965e16`, 2025 `2f135887790a013f`, 2024 `23370d5d10f8104d`; re-verified by hash in preflight check `pbp_capture_hashes` |
| 2 | `epa` target-only exemption, written, tested, limited to target use | **YES** | `OAS1_EPA_TARGET_ADMITTED` for the target; general quarantine still returns `MODEL_DERIVED_COLUMN_ACCESS`; a non-authorised caller still refused. Preflight `epa_target_only_authorisation` |
| 3 | Prior-season OAS1 fit supplying `theta_prev` | **YES** | `OAS1_PRIOR_2025.json`, season 2025, 128 unit rows, sha256 `64a49ffa1937a607`; pass rank 64/66 deficiency 2, rush rank 64/66 deficiency 2 |
| 4 | B0–B5 implemented and forward-chain-clean | **YES** | 18 folds per class, both classes, `OAS1_BASELINE_CHAIN.json` sha256 `2703f2d91e569ccb`, `candidate_fitted: false`. Max training ordinal 202601 < forecast ordinal 202602 |
| 5 | Pre-declaration committed with literal thresholds a test reads from code | **YES** | commit `150c62a`, committed **before** any Week-2 number exists; preflight `preregistration_commit` resolves it and asserts `declared_before_any_week2_fit` |
| 6 | Team normalization total across both seasons in scope | **YES** | 32 observed codes → 32 clubs, unresolved `[]`, over the actual Week-2 fit frame |
| 7 | Evaluator supports continuous targets — MAE, RMSE, CRPS | **YES** | `evaluator.SCORERS` = brier, log_loss, crps, mae, rmse; `crps` is the imported product implementation, not re-derived |
| 8 | Adjustment registry with a double-counting test | **YES** | 9 governed effects, 9 declared fields each, 6 HARD refusal codes, 65 checks including a production-approved control, a bypass-detection case, and test H, which exists because two refusals this table asserted were not actually refusing |
| 9 | Freshness invariant registered and blocking | **YES** | `current_season_input_freshness` is HARD and still refuses live boards today (`denom_panel`, `team_volume_history` at 202518 against 202601) |
| 10 | 2026 `pbp` available with the required fields | **YES** | 2,756 × 372, week 1, REG, 16 games, 32 clubs |
| 11 | Pressure data available in-season | **NO** | `was_pressure` is 404 for 2026 and publishes after the postseason. **Not required for V1** and not a research-fit gate; registered as `ol_pass_protection_v1`, status `NOT_AVAILABLE`, so it has an owner before it has a consumer |
| 12 | Commercial-use licensing resolved | **NO — UNDECIDED** | an owner decision, not an engineering one. Unchanged. Not a research-fit gate |

**Research-fit gates are 1–10 and all ten are YES.** Gates 11 and 12 are
downstream gates and neither has moved; neither is being counted as passed.

## The three lawfulness flags, now enforced by code rather than prose

| Flag | Value | Where it is enforced |
|---|---|---|
| `WEEK2_OAS1_FIT_LAWFUL` | **YES_RESEARCH_ONLY** | `fit_week2.py --dry-run` passes 13 preflight checks; the non-dry-run path raises because no fit is authorised |
| `WEEK2_OAS1_DOWNSTREAM_LAWFUL` | **NO** | `adjustment_registry`: both opponent ids are `RESEARCH_ONLY` with permitted consumers `('diagnostics', 'research')`. Applying either from `team_volume` under the production purpose returns `ADJUSTMENT_NOT_PRODUCTION_APPROVED`; `team_volume` reading either returns `ADJUSTMENT_CONSUMER_NOT_PERMITTED`. **Both were verified by running them** — both returned PERMITTED until `b60bcf7` |
| `SINGLE_ADJUSTMENT_OWNERSHIP` | **NO — not yet true of the system** | the registry now *declares* one owner per effect and refuses a second application, but only the effects it governs are covered. It is a contract that now exists, not a property the whole pipeline has been proven to have |

The third is deliberately still NO. A registry that refuses double application
is the mechanism; asserting that every adjustment in the system passes through
it is a separate claim needing a separate audit, and writing YES because the
mechanism exists is the exact substitution this registry was built to stop.

## Strata

`COLD_START_VALIDATION = NOT_EVALUATED`. Zero cold-start plays in both classes;
the stratum is **empty, not passing**, and nothing converts it into a PASS.

## One correction to this table's own method

Two rows of the previous draft asserted a refusal that the code did not
perform. They were caught because the claim was executed before it was
written, not reviewed after. `assert_may_apply` did not read `status` at all,
and `assert_consumer` unioned the applying layer into the permitted set
unconditionally — which cancelled the single restriction both OAS1 entries
were written to express. Sixty-five checks were green over both, because each
one drove a helper rather than the contract. Fixed and re-tested at `b60bcf7`.

**A gate table is evidence only if every row in it was run.** Rows 1–10 above
were each produced by executing the check named in the evidence column, in this
session, at this HEAD.

## Verdict

`WEEK2_OAS1_FIT_READY_TO_EXECUTE = YES` — **research-only, and not executed.**
All ten research-fit gates are YES and the dry run is clean. The fit has not
been run and the fitting body is not implemented; the runner raises rather than
guessing at one. No downstream consumer may read the result when it exists.

**V2 NOT YET EARNED**
