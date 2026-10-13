# Reconciliation: the owner-supplied DFS education package against HEAD (2026-10-13, 19:41 UTC onward)

- **What the package is:** an educational reference plus a static comparison of nine files. It was pinned at `3f04bd76`
  and reconciled at `44f1b54e`.
- **It is not a work order.** Its contents are **not** committed here. This file records only the reconciliation.
- **Package integrity:** all 79 manifest hashes matched.
- **Its examples:** 25 synthetic fixtures, standard library only. They were run here in a fresh directory with
  Python 3.12 and passed 25/25. The results equal the package's recorded baseline once timing and environment fields
  are excluded.
- **Scope of that pass:** synthetic only. It is not a pass of any production boundary.

## Version reconciliation (HEAD `b8d3389b`)

Eight of the nine pinned files are unchanged. The one that changed is `nfl/tools/showdown_portfolio.py`, by SEL-2
(`81e78264`):

- the constants are at `:389`;
- the branch is in `ladder` at `:463`;
- every line reference after `:389` in the package has shifted by 21 lines (+23 −2).

## The package's boundary claims, checked against the code

| id | package claim | finding at HEAD | action |
|---|---|---|---|
| B01 | `classic/rules.py` does not show the two-game minimum | **True of `rules.py`, but the rule is enforced at both production boundaries:** the builder (`nfl/opt/classic_portfolio.py:260`, tested at `test_classic_portfolio.py:78`) and the final upload verifier (`nfl/tools/classic_upload_verify.py:120`). **The upload verifier's check had no test.** | **Added:** a one-game refusal, plus its legal twin (exactly 2 games passes), in `test_classic_upload_verify.py`. **Mutation-checked:** removing the rule turns the test red. |
| B03 | the QB stack counts RBs without a receiving-role predicate | **True of `nfl/dfs/classic/optimizer.py:317`**, whose comment said "pass catchers". **That module is not the production lineup builder.** Production builds with `nfl/opt/classic_portfolio.py` → `nfl/opt/exact.py:326` (`qb_stack_positions=('WR', 'TE')`). `dfs/classic/optimizer.py` supplies only the `Player` type and rules to `dfs/classic/pool.py`, plus research and benchmark code. | **Truthful-label fix:** the comment now states that RBs count and that the production builder counts WR/TE only. No behaviour changed. |
| B04 | minimum exposure is reported, not enforced | **True of `dfs/classic/optimizer.py:773`**, which reports `unmet_min_exposure`. The production builder (`nfl/opt`) has **no minimum-exposure option at all**, so nothing promises a hard minimum. | **None.** If a hard minimum is ever offered, it must refuse on violation and distinguish a greedy shortfall from infeasibility. |
| B02, B05, B06, B07, B10-B13 | existing boundaries are present | unchanged blobs; no new counter-evidence found | none |
| B08 | selector stability: compare at a fixed policy and keep an incumbent | `RESULT_SEL2_FIXED_POLICY.md`: a fixed level removes the cap-level jumps, but the sequential GLOBAL exclusion remains a discontinuity. SEL-2 missed promotion on one contest, BUF $5K (spread 0.037 against 0.032). | the next selector challenger is pre-registered before it is run |
| B09, B14 | cross-contest policy is the owner's; SEL-1's failure is preserved | unchanged; SEL-1 stays opt-in and failed; SEL-2 is opt-in, pending an owner ruling | none |

## Portable idea worth keeping

**The package's EDU02.** Adding one attractive candidate lowers the greedy utility from 12 to 10, while the exhaustive
optimum stays 12.

- This is the same class of failure as PORT-D4: the selector is not monotone in the pool.
- It supplies a small exact oracle for the next selector challenger. The test would be: on a nested superset pool, at a
  fixed policy, the selection-world objective never falls below the incumbent's.
- It is a test design. It is not evidence about our selector.

## Not done here

- No production run.
- No portfolio change.
- No change to cross-contest or cap policy.
- No vendor data was ingested.
- No Fantasy Cruncher access. The package records that automated navigation was stopped under the provider's terms.

## Part 2 (20:00 UTC): implementable rows mapped to code, and what is actually actionable

**Scope.** Four read-only agents mapped the implementable tables to `file:line`, each row labelled PROD, NONPROD,
PARTIAL, MISSING or NA. The tables:

| table | rows |
|---|---|
| 01 features | 68 |
| 02 controls | 59 |
| 03 player evaluation | 30 |
| 04 Classic rules | 15 |
| 05 Showdown rules | 24 |
| 06 stacking | 18 |
| 07 exposure | 20 |
| 08 ownership | 19 |
| 12 research questions | 20 |

The other tables (glossary, evidence, citations, priorities) hold nothing implementable.

**Labels are not the result.** Below are only the rows that survive a production-impact check. Each is marked
**VERIFIED** (re-read by me at HEAD) or **AGENT-REPORTED** (cited, not re-read).

### Corrections to how the code had been described

- **AGENT-REPORTED:** `nfl/opt/contest.py` is not on the Classic production path; only tests import it.
- **AGENT-REPORTED:** most of `nfl/opt/constraints.py` (the registry `solve_governed` uses) has no production caller.
  Production calls `exact.solve_structured` with `qb_stack_min=1` and the DST-facing-QB ban only.

### Actionable, by priority

| # | gap | evidence | production impact | where it goes |
|---|---|---|---|---|
| 1 | **Selector instability** (greedy ladder jumps; sequential GLOBAL exclusion; non-monotone in the pool) | VERIFIED: SEL-1, SEL-2 and the package's EDU02 | the cap level and objective move with pool composition | `PREREG_SEL2_PROSPECTIVE_W6.md` (`2f510449`), harness `sel2/sel2_paired.py` |
| 2 | **Candidates and selection on the same worlds** (EP16) | VERIFIED: `showdown_portfolio.py:909-918` | the board's coverage figures are in-sample, and the pool is fitted to the worlds it is scored on | CG-1, the candidate-generator experiment. It must generate on worlds disjoint from evaluation and fix the pool size and budget. |
| 3 | **A QB change does not propagate to team volume, receiver efficiency or the opposing DST** (P13/R02) | AGENT-REPORTED: P1-4 recorded FAIL | QB-switch slates are mis-forecast | the existing QB-regime track |
| 4 | **The participation mixture (Questionable, limited snaps) exists only in the CORRECTED_V1 arm** (P08/P09/P30) | AGENT-REPORTED | Questionable players are unpriced in production | its own W6+ prospective grading is the gate |
| 5 | **Role signals in the warehouse but unused:** goal-line share, air yards (P11/P16/P22) | AGENT-REPORTED | TD and target-depth allocation rest on share only | a held-out forward-chain challenger, pre-registered before it is run (the PROJ-FIX-1 template) |
| 6 | **Field, duplication and payout:** code exists in shadow; production says UNAVAILABLE (OS02/OS13/OS14) | AGENT-REPORTED | no field-relative selection | blocked on prize tables and archived contest fields, which are owner inputs |
| 7 | **Showdown `verify_upload` hardening:** inactive check by name only, `inactive_keys` unused, no header check, contest name and fee not compared | VERIFIED: `showdown_portfolio.py:1219-1279`; the caller refuses when rows ≠ paid entries (`:1123`) | **not a live hole:** names come from the same DK export | small test-first fix, low priority |
| 8 | **Classic final verify has no lock-time refusal; cross-profile lineup repeats are reported, not refused** | AGENT-REPORTED | a late re-run is not refused locally (DK itself rejects locked edits); repeat policy is the owner's | record only; the repeat rule is an owner policy |

### Checked and not gaps

- **B03/B04:** in the non-production optimizer.
- **Stacking correlation:** comes from shared simulated worlds, not hand-set coefficients.
- **Classic games simulated independently:** by design.
- **Vendor UI conveniences** (grids, column views, save and load, thumbs): NA.
- **Conditional boosts, preference overlays, uploaded projections:** excluded by the football-only rule.
