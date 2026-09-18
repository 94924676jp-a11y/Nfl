# Contract 4 — threshold reconciliation

**Successor record, 2026-09-18.** This file does not edit
`DIAGNOSIS_AND_PREDECLARATION.md` and does not restate its correction. It
records the chronology the correction did not carry, states what the
repository contains today, and names what was still missing until now.

## The chronology, traced to commits rather than recalled

| when (UTC) | commit | what happened |
|---|---|---|
| 2026-09-16 16:20:19 | `b390fa0` | `nfl/tools/draw_contract2.py` written with `N_BATCHES = 20` and `BATCH_AGREEMENT = 19`. |
| 2026-09-16 18:30:24 | `030b615` | `nfl/tools/draw_contract3.py` carries the same pair. |
| 2026-09-17 14:25:34 | `14a5257` | The Contract 4 pre-declaration is created stating `a >= 0.90`, "at least 18 of 20 batches agree", **and asserting that 0.90 is the same agreement `BATCH_AGREEMENT` already uses.** It is not; the constant had read 19 for twenty hours. |
| 2026-09-17 15:45:33 | `340d581` | Corrected to `a >= 0.95`, 19 of 20, by **append**: the original wording is quoted inside the document, not deleted. Found by external review against `887f4f2`. |
| 2026-09-17 16:00:04 | `d7bcec4` | The final Contract 4 spec is pre-registered carrying the corrected threshold. |

**The window was eighty minutes and Contract 4 had not run once inside it.**
No result was scored under 0.90 and none was reinterpreted. That is the fact
that keeps this a near miss rather than a retracted finding.

## What the repository contains today, measured 2026-09-18

| | value | where |
|---|---|---|
| `draw_contract2.N_BATCHES` | 20 | `nfl/tools/draw_contract2.py:33` |
| `draw_contract2.BATCH_AGREEMENT` | 19 | `nfl/tools/draw_contract2.py:32` |
| `draw_contract3.N_BATCHES` | 20 | `nfl/tools/draw_contract3.py:27` |
| `draw_contract3.BATCH_AGREEMENT` | 19 | `nfl/tools/draw_contract3.py:28` |
| `DRAW_COUNT_CONTRACT_2.md` prose | 19 of 20 | line 60 |
| `DRAW_COUNT_CONTRACT_3.md` prose | 19 of 20 | lines 48–49 |
| Contract 4 pre-declaration prose | 19 of 20, `a >= 0.95` | `DIAGNOSIS_AND_PREDECLARATION.md` §4 |

**Prose and code agree everywhere.** Every remaining "18 of 20" in the Contract
4 document is inside the quotation of the withdrawn wording, or inside the
sentence forbidding its reuse as precedent.

## A correction to a claim in this repository

`nfl/research/reviews/REPO_REVIEW_2026-09-18.json` carries, at severity
`GOVERNANCE_DEFECT`:

> "Predeclaration text says 18/20 while executable code currently requires
> 19/20."

**That claim is stale.** It describes the state between `14a5257` and
`340d581` on 2026-09-17, which ended the day before the review is dated. The
likely reading is that line 116 of the document — inside the quoted original —
was taken for live text.

The review artifact is **not edited**. It was a reasonable reading of an
unmarked quotation and it is preserved as written; this file is the appended
correction. What the repository owed, and the review was right to want, was a
way to tell a live threshold from a quoted one without a human judging it.

## What was actually still missing

Not a number. A check.

The 2026-09-17 correction fixed one threshold in one document and added no
guard, so the same divergence could recur in any contract document and would
again depend on someone happening to read the paragraph. Eighty minutes was
luck.

Three things close it:

1. **`nfl/tests/test_contract_text_matches_code.py`**, whose central function
   is `test_contract_text_and_executable_constant_must_agree`. For each
   contract document it imports the module the document governs, reads
   `BATCH_AGREEMENT` and `N_BATCHES` from code, and fails on any live prose
   statement of `N of M batches` or `a >= x` that disagrees. It names both
   values and repairs neither: which side is right is a governed decision, and
   the review that raised this said in terms that neither may be silently
   moved to match the other.

2. **An explicit superseded-block convention.** A withdrawn passage is wrapped
   in `<!-- SUPERSEDED-BEGIN why --> … <!-- SUPERSEDED-END -->`. These are HTML
   comments: no rendered word changes and no historical text is altered, which
   is why this is an acceptable edit to a document under the append-only rule.
   Deciding by heuristic whether a sentence is live or quoted is how a real
   disagreement gets waved away as "that's just the quote".

3. **A cross-check between the two contract modules**, because two constants
   that are supposed to be the same number are a second place to drift.

## What this does not claim

That prose and code agree anywhere else in the repository. Three documents are
registered in `CONTRACTS`; every other document is unchecked, and adding one is
a line in that tuple. The guard is a bound on the documents named, not a
property of the tree.
