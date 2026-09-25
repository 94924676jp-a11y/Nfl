# Correction: capture is healthy, the extractor is not, and I measured a checkout

Written 2026-09-25 ~13:40Z. This withdraws a finding I filed two hours earlier
and replaces it with a worse one.

## What I got wrong

I reported `GLOBAL_CAPTURE_STALL`: every source 25-31 h behind a measured 0.5 h
cadence, therefore the capture runner had stopped.

**It had not.** `NFL vintage capture` run 893 succeeded at 2026-09-25T13:07Z,
eleven minutes before I filed the claim, and has been succeeding every ~30
minutes throughout. What was stale was **my checkout**. Captures commit to
`capture-prod`; this development branch had never pulled them.

Two compounding errors of my own, both previously recorded in this audit as
classes I was cataloguing in other people's code:

1. **A liveness check that reads a git working copy measures the working copy.**
   `capture_cadence.assess()` read `nfl/vintage_manifest.jsonl` from disk and
   reported an outage. Fixed: `lineage_ok()` establishes that the checkout is on
   `capture-prod`, and when it cannot, every staleness verdict reads
   `LINEAGE_NOT_ESTABLISHED` and `global_stall` is `None` rather than `True`.
2. **`git fetch origin main` updates `FETCH_HEAD`, not `refs/remotes/origin/main`.**
   I read the stale remote-tracking ref and believed it. This is the *second*
   time this exact mistake has cost something in two days; the first was a false
   alarm about unpushed commits.

## Three lineages, diverging in both directions

| branch | size | rows |
|---|---|---|
| **`capture-prod`** (live) | **69.69 MB** | 8,951 |
| `main` | 29.84 MB | 4,311 |
| dev branch | 53.55 MB | 6,757 |

These are not versions of one file. Any tool reading the working copy measures
whichever lineage it happens to sit on. Filed as DEF-048.

## What survives, and it is worse than what I withdrew

Read from `capture-prod`, six polled sources are **CURRENT at 0.3 h**. One is not:

```
official_inactives   age 236.4h   last attempt 0.3h ago
   EXPECTED_CAPTURE_CADENCE_VIOLATION, ASYMMETRIC_SOURCE_SILENCE
```

907 attempts. The most recent, 2026-09-25T13:08:23Z:

> `DEFERRED / SOURCE_HAS_NO_ROWS_YET — official_inactives: HTTP 200, 409086
> bytes that render and carry 37 occurrence(s) of ('inactive'...`

**This is not an outage. The page is up, it is being fetched every thirty
minutes, it returns 409 KB that renders, the content contains 37 occurrences of
the target term, and the extractor yields zero rows.** It has done so for 9.8
days, across the Week 3 game days and across ATL @ GB.

`SOURCE_HAS_NO_ROWS_YET` is the correct verdict for a Saturday morning with
nothing posted. It is not a defensible verdict for ten days spanning multiple
game days. The code is reporting an empty source; what it has is a parser that
cannot read a live page.

**This is the direct cause of the ATL/GB inactives gap**, and it is live right
now. DEF-012 is raised to CRITICAL and its diagnosis rewritten: extraction
failure, not egress failure.

## Storage urgency materially changed

My A-07 projection used the dev branch's 53.55 MB. The live lineage is **69.69
MB** and grows every thirty minutes. That is 30 MB from GitHub's hard rejection,
not 46. APPROVAL-002 is re-escalated to `BLOCKING_NOW` on that basis — one of
the four conditions that earn a second mention.

## The pattern, for the third time today

My own tooling produced a confident false alarm because it read a local artifact
as if it were the world. The auditors needed a self-exclusion rule; the liveness
checker needed a lineage rule. The general form is that **a measurement of the
environment must establish what it is measuring before it reports a verdict**,
and every instance of this I have fixed today was found by accident rather than
by a contract.
