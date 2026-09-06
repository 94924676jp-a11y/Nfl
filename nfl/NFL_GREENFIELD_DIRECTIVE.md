# NFL Greenfield Architecture Directive

**Issued:** 2026-09-06
**Branch:** `claude/nfl-greenfield-architecture-stsxmk`
**Status:** research pass. **No NFL predictive production code is written under
this directive.**

## Why this exists, in one paragraph

NFL is being started as a **greenfield sibling product on a shared scientific
platform**, not as MLB V8 with football nouns. The owner's instruction is that
NFL begins with the architecture we now wish MLB had started with: immutable
information vintages, complete execution identity, lossless simulation draws,
a Skill → Opportunity → Environment decomposition, and prospective evaluation
before any claim of edge. The point of starting NFL now is that it is the one
place where the MLB lessons can be applied *before* the architectural debt
accumulates rather than after.

## The scope limit, stated first because it is the thing most likely to erode

This pass determines the **foundation and the experimental roadmap**. It does
not build a model, a simulator, or a feature pipeline. The reason is recorded in
`CLAUDE.md`: architecture that gets decided accidentally while code is being
written is how MLB acquired the constraints it now has to work around.

Measurement scripts that establish a fact are expected — that is how a claim
earns the label VERIFIED — but they are evidence, not deliverables.

## The labelling rule every worker operates under

Every substantive claim carries exactly one label:

| Label | Meaning |
|---|---|
| `VERIFIED` | a command was run or a file opened, and it is cited |
| `DERIVED` | follows from something VERIFIED, with the derivation shown |
| `UNVERIFIED-RECALL` | believed from training, **not** checked here |

An unlabelled claim is a defect in the output. This project has twice paid for
recalled figures presented as measured ones — see `CLAUDE.md`, "Claims you may
encounter that are FALSE", where a stated r of 0.0625 was really 0.1101 and an
entire quoted results table was wrong in every cell.

`UNVERIFIED-RECALL` is permitted and useful. What is forbidden is letting it
become the silent basis of a design commitment.

## What was established before the workers were briefed

The lead probed the execution environment rather than assuming its limits, and
the assumption in `CLAUDE.md` that this agent has no usable egress turned out to
be **too strong**. Recorded reproducibly in `nfl/NFL_DATA_AVAILABILITY.json`,
produced by `nfl/tools/probe_nfl_sources.py`: 27 targets, **22 PASS, 1 BLOCKED,
4 FAIL**.

The boundary is specific: `raw.githubusercontent.com` and
`github.com/<owner>/<repo>/releases/download/...` answer 200, while
pro-football-reference, the ESPN API, the Sleeper API and the GitHub API for
other owners do not. The negative controls are in the audit deliberately, so the
boundary is demonstrated rather than asserted.

The consequence is large: **the nflverse public data stack is fully readable
from inside this container**, including play-by-play (372 columns), play
participation (routes, personnel, pressure, coverage), FTN charting, snap
counts, injuries, depth charts, rosters and officials, for 2024 and 2025.

This is why NFL-0 is not blocked, and why most of this directive's questions
were answerable with measurement rather than assignment.

## The eight workers

Each read `nfl/research/_GROUNDING.md` first, then the governance artifacts
named in their brief. Each wrote one document and touched nothing else.

| # | Worker | Core question | Output |
|---|---|---|---|
| 1 | Data & provenance | What can be captured, with which clocks, joined on what keys, and what leaks? | `research/W1_DATA_PROVENANCE.md` |
| 2 | QB / passing | What is separable into skill vs opportunity, and what stabilises? | `research/W2_QB_PASSING.md` |
| 3 | RB / rushing | How is backfield opportunity distributed, and how does it redistribute on absence? | `research/W3_RB_RUSHING.md` |
| 4 | Receiver opportunity | Are routes, target share and TPRR computable, and which are reliable? | `research/W4_RECEIVER_OPPORTUNITY.md` |
| 5 | Team & environment | What sets game volume, and how much between-game spread is available? | `research/W5_TEAM_ENVIRONMENT.md` |
| 6 | Defense & matchup | How much of defensive adjustment is real signal? | `research/W6_DEFENSE_MATCHUP.md` |
| 7 | Injury & news | What does a designation actually imply about snap share? | `research/W7_INJURY_NEWS.md` |
| 8 | Benchmark & DFS | Where is the forecast/DFS/market boundary, and what needs the networked agent? | `research/W8_BENCHMARK_DFS.md` |

Worker 8 operates under a tightened constraint: it cannot reach any commercial
source, so its claims about DFS sites, books and public projection systems are
required to be labelled `UNVERIFIED-RECALL` and routed to the networked agent
rather than stated as fact.

## Governance inherited, not reinvented

NFL adopts the existing machinery by reference. Workers were instructed not to
coin parallel vocabulary.

- **Rule 001 five states** — `PASS` / `FAIL` / `BLOCKED` / `DEFERRED` /
  `NOT_APPLICABLE`, from `sportsplatform/governance/outcome.py`. `DEFERRED` is the one
  routinely left out, and leaving it out is what aborted MLB's first live batch
  when "lineups have not posted yet" was filed as a fatal bug. The NFL analogue
  — "Wednesday's injury report is not published yet" — is the same condition and
  must not repeat the error.
- **Rule 002 clocks** — `sportsplatform/governance/provenance.py` already keeps five clocks
  apart by construction and refuses an unqualified age. The owner's four NFL
  clocks (event / available / ingested / prediction) map onto it.
- **Rule 003 leakage**, **004/004a baseline and frozen metrics**, **005 no
  cherry-picking** (r, SD ratio and calibration slope are algebraically one
  fact), **006 no promotion from development data** — `v8/V8_SYSTEM_CONSTITUTION.md`.
- **Failure taxonomy** — `v8/V8_FAILURE_TAXONOMY.md`, Class A "absence read as
  success" being the dominant class.
- **Feature lifecycle** — `v8/FEATURE_REGISTRY.md`: CORE / SECONDARY /
  EXPERIMENTAL / DESCRIPTIVE / REJECTED, and nothing rises above EXPERIMENTAL
  without citing the experiment that earned it. **Every NFL feature starts at
  EXPERIMENTAL or lower**, because no NFL experiment has run.

## Version naming

Per the owner's 2026-09-02 ruling on V9: a version number is earned after the
evidence exists, not applied in advance to work that hopes to earn it. This work
is the **NFL Greenfield Track**. The first frozen NFL baseline takes a name
chosen when it is frozen, and it does not inherit the name M0 — that name
belongs to a specific, preserved, non-reproducible MLB artifact.

## What the lead produces from the eight returns

1. `nfl/NFL_FOUNDATION_AND_MODEL_ARCHITECTURE.md` — the integrated architecture.
2. `nfl/NFL_EXPERIMENTAL_ROADMAP.md` — NFL-0 through NFL-5, with the gate each
   phase must pass before the next begins.
3. An assignment block appended to `docs/AGENT_OUTBOX.md` for everything that
   genuinely requires the networked agent — per `docs/AGENT_PROTOCOL.md` DEC-029,
   **not blocked, assigned**.

Disagreements between worker returns are resolved by opening the artifact and
citing it, per Rule 2 of the agent protocol, and the resolution is recorded in
the integration document rather than averaged away.
