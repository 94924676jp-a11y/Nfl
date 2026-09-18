# A1 successor specification — what would un-falsify appearance certainty

**Status: SPECIFICATION. Nothing here is measured, and the measurement it
specifies cannot run in this repository today. §5 says why, with the number.**

`A1_APPEARANCE_CERTAINTY` is FALSIFIED and CRITICAL. A2 — falsified the same
day and only MATERIAL — received a successor specification; A1 did not, and
`nfl/tools/discovery.py` surfaced that gap under
`CRITICAL_ASSUMPTION_FALSIFIED_WITHOUT_SUCCESSOR`. This closes it.

## 1. What was falsified, precisely

> A non-QB skill player whose prior-season appearance rate is 1.0, and who has
> taken opportunity in every current-season week so far, will take opportunity
> in the next week with probability exactly 1.0.

Measured over 2022–2025, weeks 2–18, club having played: **n = 1,702, failures
117, rate 0.93126, Wilson 95% [0.91824, 0.94233]**. Both declared limbs fired —
the upper bound is below 1.0 and failures were observed. The claim is dead and
is not revived here.

**What that leaves is 6.87 percentage points of unexplained absence** in a
cohort the estimator was asserting certainty about. A Beta posterior mean is
exactly 1.0 for a man who has never missed; on the 2026 week-1 carries room
that was 13 of 196 rows at exactly 1.0 and 77 at exactly 0.0.

## 2. The successor claim, stated so it can fail

> **A1S**: for the previously-certain cohort, appearance is conditionally
> predictable from information observable before kickoff. Specifically, the
> official injury designation observable at the forecast cut carries
> information about the 6.87% failure rate.

This is deliberately narrower than "appearance is predictable". It names one
conditioning variable, which is the one that newly became available.

## 3. Estimand

P(opportunity > 0 in week W | cohort membership, designation `d` observed from
a vintage whose `learned_at` precedes the cut), by designation level, against
the pooled cohort rate 0.93126.

Levels, declared in advance and not merged after seeing counts:
`OUT`, `DOUBTFUL`, `QUESTIONABLE`, `LISTED_NO_STATUS`, `NOT_LISTED`.

## 4. Falsifier

**A1S is falsified if the designation-stratified rates do not differ from the
pooled rate** — concretely, if every level's 95% interval contains 0.93126 and
the levels' intervals overlap each other, on a sample meeting §5's power
requirement.

If A1S is falsified, the 6.87% is **not** explained by pre-kickoff injury
designation, and the correct recording is that the residual is unexplained. It
may not then be modelled as certainty, and it may not be papered over with a
floor, a clip, or a shrinkage constant chosen to make the number look right.
**No hand-selected constant is permitted under this specification**, which is
the same rule A1's own falsification was found under.

## 5. Why this cannot be measured here yet, with the number

`nfl/research/assumptions/a1_successor_feasibility.py`, artifact
`A1_SUCCESSOR_FEASIBILITY.json`:

> `BLOCKED[A1_SUCCESSOR_CONDITIONING_VARIABLE_HAS_NO_CONTRAST]` — the A1 cohort
> at week 2 is **59 players** and **none** carries an Out, Doubtful or
> Questionable designation: `{'LISTED_NO_STATUS': 13, 'NOT_LISTED': 46}`.

The conditioning variable takes **one effective value across the entire
cohort**. Its effect is not estimable at any sample size. That is a fact about
the data, not a result about football, and running the test anyway would
produce a failure to reject that looks identical to a finding — which this
project's rules already forbid reading as adequacy.

There is a second, independent block: **the week-2 outcome is not captured
either.** The 2026 play-by-play holds week 1 only, so even a cohort with
contrast could not be graded.

## 6. What would make it measurable

**The efficient path is historical injury captures.** This repository holds
`injuries` for **2026 only** — 1,145 rows across 9 content-addressed vintages,
weeks 1 and 2. The falsification cohort was n = 1,702 over 2022–2025. With
2022–2025 injury data the successor test runs against the same population that
falsified A1, which is the correct comparison and is available at adequate n
immediately.

The prospective path works too and is slow: at roughly 59 cohort members per
week and near-zero designated among them, accumulating contrast takes many
weeks, and the cohort shrinks as members miss.

**Both are bytes outside this checkout.** The request is in
`docs/AGENT_OUTBOX.md`. This is ASSIGNED, not blocked for both agents.

## 7. What this specification does not claim

That injury designation is the right conditioning variable — only that it is
the one newly available and the cheapest to test. The week-2 count is a hint
and not a finding, but it is worth stating: **none of the 59 previously-certain
players was designated at all**, which is weak evidence that this cohort's
absences may arise from causes a pre-kickoff designation does not see —
in-game injury, a late scratch, or a role change. If A1S is falsified, those
are the successor's successors, and each needs its own specification.

## 8. Governance

A1 stays FALSIFIED. This specification does not settle it, does not move its
status, and rewrites no prior record. The production path that depends on it
stays blocked. Promotion remains impossible while a CRITICAL assumption is
falsified, and that is the gate working.

**V2 NOT YET EARNED**
