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
