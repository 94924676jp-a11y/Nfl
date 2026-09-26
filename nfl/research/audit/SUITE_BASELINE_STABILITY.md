# The baseline's 140 is a distribution, not a number

Recorded 2026-09-26, after a second complete run over the same tree plus four
fixes. Raw output: `SUITE_2026-09-26_AFTER_FIXES.txt`.

| | baseline `1bc3e59` | after fixes `4d84c85` |
|---|---|---|
| modules | 266 | 268 |
| test functions | 2819 | 2828 |
| checks | 14343 | 14369 |
| **FAILING CHECKS** | **140** | **140** |
| RAISED | 41 | 42 |
| BLOCKED FUNCTIONS | 23 | 23 |

Failing held at 140, and the per-module diff shows why that is not "no change":

| module | before | after | cause |
|---|---|---|---|
| `test_orchestrator` | 1 | 0 | **fixed** — the mock fixture impersonation (DEF-068) |
| `test_appearance_candidate_b` | 1 | 0 | **not fixed by anyone** — run-to-run variation |
| `test_artifact_claim` | 0 | 2 | **not caused by anyone** — timing-dependent |

So one check improved for a reason, and two moved for no reason at all.

## `test_artifact_claim::test_C_the_sigpipe_case_reproduced_not_mocked`

The test runs `generator | head -5` and asserts the generator died on SIGPIPE
**before** writing `board.json`: the file must be absent and `AC.verify` must
refuse `ARTIFACT_CLAIM_WITHOUT_VERIFIED_FILE`. Whether that holds is a race
between the generator reaching its write and `head` exiting.

Observed on **unchanged code, within minutes**:

| condition | result |
|---|---|
| full suite, 2026-09-26 baseline | 0 failing |
| isolated, six consecutive runs | 2 failing, every time |
| isolated, 8 busy loops on 4 cores | 2 failing |
| isolated, immediately after killing the load | 0 failing |

It uses a `TemporaryDirectory`, so a leftover file is ruled out. Six identical
results in a row are not determinism, they are correlated conditions — which is
exactly how a timing-dependent check gets mistaken for a stable one. My first
hypothesis was that load made it pass; the measurement says the opposite, and
recording the failed hypothesis matters more than the direction.

**The consequence is the point.** This check cannot tell "the SIGPIPE
protection works" from "the race went my way". Its PASS is not evidence the
protection holds, and its FAIL is not evidence the protection broke. A test
named `reproduced_not_mocked` is inherently racy, and reproduction was the
right instinct — but a race needs to be forced, not hoped for.

## What this does to the baseline

`140` is the count of one draw from a distribution, not a property of the tree.
At least two of its 43 modules move between runs with nothing changed. So:

* A change is a regression only if it moves a check **for a stated reason**, not
  because the total went up.
* `test_appearance_candidate_b` and `test_artifact_claim` are
  `ENVIRONMENT_OR_TIMING_SENSITIVE`, by observation of both outcomes rather
  than by inference from file overlap.
* The remaining 138 are still **NOT_ESTABLISHED**. Nothing here converts them
  to PRE_EXISTING; that still needs a run at `853a55c`.

And the reason my `--only` evidence has been weaker than I treated it, twice
over: modules that depend on generated artifacts (`test_full_slate_rehearsal`
wants the gitignored `nfl/research/p4b/panel_enriched.pkl`) behave differently
in isolation, and modules that depend on timing behave differently under load.
Neither is visible from a green `--only` run.
