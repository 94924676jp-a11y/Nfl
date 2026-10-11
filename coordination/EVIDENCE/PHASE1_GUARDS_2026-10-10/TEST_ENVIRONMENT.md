# Reproducible test environment (Phase 1, owner priority 4)

## The defect (found 2026-10-10, D5)

A fresh worktree of this repository has no `nfl/derived/` and no `nfl_vintage/raw/`: both are git-ignored. The suite
did not say "environment incomplete". In the Phase 1 worktree, before remediation:

| Module | Clean checkout with data | Fresh worktree, no data | What it looked like |
|---|---|---|---|
| `test_sunday_prelock_p0.py` | 4 fn, 11 checks | 2 checks, **4 functions raised** TypeError | a code regression |
| `test_detectors_have_controls.py` | 15 checks | 13 checks, silently | fewer checks, no reason given |
| `test_showdown_run_guards.py` | 33 checks | 31 checks, silently | fewer checks, no reason given |

A regression comparison between such a checkout and the main one measures missing data, not code.

## Remediation (in this branch)

1. **Named, explicit report.** `python3.12 nfl/tools/test_env_check.py [--json OUT]` checks every git-ignored input the
   suite reads, by hash, and exits 0 `COMPLETE` or 2 `INCOMPLETE`. States: `OK`, `MISSING`, `MISMATCH`,
   `UNVERIFIABLE` (a raw file with no manifest row naming its hash). Only `OK` counts as present: an input with no
   provenance is not complete. Tests: `nfl/tests/test_test_env_check.py`.
2. **Tests report BLOCKED with a cause** instead of raising or dropping checks: `test_sunday_prelock_p0.py`
   (`STATE[code]` from the refused state build) and `test_showdown_run_guards.py` (usage panel not PASS, scenario
   states absent). The runner already counts these as BLOCKED FUNCTIONS, so a missing input is visible in the totals.
3. **Rebuilt, not copied.** The Phase 1 worktree's `nfl/derived/` was rebuilt with `bash nfl/tools/rebuild_derived.sh`
   from committed inputs and verified against `nfl/production/DERIVED_REBUILD_MANIFEST.json` (generation 2, 6
   artifacts, all MATCH). A copy taken from the main checkout earlier was set aside, not used.

## How each input is reproduced, and its provenance

| Input | Reproduce with | Verified against | Provenance |
|---|---|---|---|
| `nfl/derived/<6 artifacts>` | `bash nfl/tools/rebuild_derived.sh` (exit 4 on any hash mismatch) | `nfl/production/DERIVED_REBUILD_MANIFEST.json` sha256, generation recorded | built from committed inputs; generation 2 adds 2026 week-4 play-by-play |
| `nfl_vintage/raw/<source>.<sha16>.<ext>` | re-run the scheduled capture; or copy from a checkout that has them, then run the check | the sha16 in the file name, and the `PASS` row of `nfl/vintage_manifest.jsonl` with that sha256 | nflverse public release files; the manifest row records URL, retrieval time and HTTP status |
| `numpy`, `pandas` | `PYLIB=<dir> bash nfl/tools/rebuild_derived.sh` installs them | import succeeds | PyPI |

## Licensing and protected state

- The check reads and hashes; it writes nothing but `--json`. It never edits a sealed run, a freeze, a manifest or an
  entry file.
- **Licensing is not asserted by this check.** The raw captures come from nflverse release URLs recorded in the
  manifest. The repository's own feasibility audit (`docs/INTEGRATION_FEASIBILITY_AUDIT_2026-10-09.md`) records
  per-source terms (for example the FTN participation file as CC-BY-SA). Copying captures between checkouts of
  the same repository for testing does not redistribute them. Anything beyond that is the owner's call under OD-3.
- Nothing from a licensed or terms-restricted source (NFL.com pages, DraftKings exports, FantasyCruncher) is
  needed by the suite modules measured here.

## Measured state

| Checkout | Verdict | Inputs | Evidence |
|---|---|---|---|
| `/home/user/nfl-phase1` (Phase 1 worktree) | COMPLETE | 17 OK | `TEST_ENV_CHECK_WORKTREE.json` |
| `/home/user/nfl` (main checkout) | COMPLETE | 17 OK | re-run 2026-10-10 |

## Residual

- A CI or cloud checkout still starts without these inputs. The check makes that explicit; it does not supply
  the data. Supplying it automatically (a cached artifact store keyed by manifest hash) is a Phase 2 candidate
  (P2-ENV).
- `test_detectors_have_controls::test_05` passes a constant True when `DETECTOR_VALIDATION.json` is absent
  (pre-existing, D5b). It is a verification-machinery test, so it is listed for an owner-approved fix and has not
  been changed here.
