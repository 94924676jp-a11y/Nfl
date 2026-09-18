# STATE DECLARATIONS

Statements about this system that a generator reading this repository **cannot
measure**. `SYSTEM_STATE.json` carries them in a section of their own, marked
as declarations, so that a reader of `CURRENT_STATE.md` can always tell which
lines were measured at generation time and which were asserted by somebody.

The previous `CURRENT_STATE.md` mixed the two freely. It stated
"1,230 assertions across 19 suites, 0 failing" beside "DNS resolves to
151.101.65.55" beside "the routine says the run succeeded" — a measurement, an
observation made elsewhere, and a report from a system this repository cannot
see, all in one voice. Eleven days later the first of those was wrong by a
factor of eight and nothing in the file could say so.

## Required fields

Each declaration carries:

- **claim** — what is asserted, in one sentence
- **declared_by** — who asserted it
- **declared_at** — when
- **why_not_measurable** — the specific reason a repository read cannot settle it
- **what_would_verify** — the concrete thing that would turn it into a measurement
- **status** — `STANDING` or `SUPERSEDED`

A declaration is **never** deleted. When it stops being true it is marked
`SUPERSEDED` and the successor is appended beneath it, because "we used to
believe this" is information and an edited file destroys it.

---

## ID: EGRESS_DENIED
- **claim**: This executor has no outbound network. The egress proxy returns
  403 on every outbound request, including to nfl.com, measured from two
  separate cloud sessions rather than inferred from one.
- **declared_by**: agent (this checkout), corroborated by a second session
- **declared_at**: 2026-09-07
- **why_not_measurable**: a repository read cannot establish a network fact,
  and a generator that tried would be measuring the moment it ran rather than
  the standing policy.
- **what_would_verify**: an executor with egress to nfl.com that can run at
  kickoff−90 minutes.
- **status**: STANDING

## ID: NETWORKED_AGENT_EXISTS
- **claim**: A second agent on this project has network, holds the live
  sportsbook odds connector, can see project storage outside this git
  checkout, and can run long simulations.
- **declared_by**: owner
- **declared_at**: 2026-09-07
- **why_not_measurable**: the other agent's capabilities are not recorded in
  this tree.
- **what_would_verify**: nothing here; it is a standing fact about the team.
  Its operational consequence is written down instead: a task blocked only for
  this executor is **assigned**, not blocked, and the request goes into
  `docs/AGENT_OUTBOX.md` before anything is marked blocked.
- **status**: STANDING

## ID: REAL_MONEY_NOT_ENABLED
- **claim**: No money has been staked and none may be. Real money is NOT
  ENABLED and the weekly exposure cap is deliberately UNSET.
- **declared_by**: owner
- **declared_at**: standing
- **why_not_measurable**: a governance decision, not a repository property.
  The repository can show the flag; it cannot show the intent behind it.
- **what_would_verify**: an owner ruling changing it. Until then the cap stays
  unstated and is not filled in.
- **status**: STANDING

## ID: V2_NOT_EARNED
- **claim**: V2 is not earned. A version number follows evidence; it is not a
  label applied in advance to work that hopes to earn it.
- **declared_by**: owner
- **declared_at**: standing
- **why_not_measurable**: promotion is a decision.
- **what_would_verify**: a methodological change large enough to justify it,
  demonstrated on data that selected none of it.
- **status**: STANDING

## ID: FANDUEL_PROVENANCE
- **claim**: FanDuel single-game rules are recorded at provenance
  `VERIFIED_RULE_VALUE_RELAYED_SOURCE`. They were relayed, not read from a
  FanDuel document by this executor, and the provenance is not upgraded.
- **declared_by**: agent, on the relay
- **declared_at**: 2026-09-16
- **why_not_measurable**: the repository holds the values; it cannot hold the
  fact of having seen the source.
- **what_would_verify**: a FanDuel slate export or rules page retrieved with
  provenance. Until then OUT-022C stays open and no salary is inferred from
  DraftKings.
- **status**: STANDING

## ID: MARKET_IS_EVALUATION_ONLY
- **claim**: Sportsbook prices may evaluate a forecast and may never feed one.
  DFS ownership and contest behaviour never flow backward into football
  prediction.
- **declared_by**: owner
- **declared_at**: standing
- **why_not_measurable**: the repository can be audited for a market column
  reaching a model — and the P7 dependency DAG now does exactly that for the
  `schedules` blob's price columns — but the rule itself is a decision.
- **what_would_verify**: nothing; it is the rule. The DAG's
  `EDGE_DECLARES_MARKET_FIELD` refusal is its enforcement, not its source.
- **status**: STANDING

## ID: SCHEDULED_CAPTURE_STATE
- **claim**: The state of any GitHub-hosted capture routine — enabled,
  disabled, last fired — is not knowable from this checkout.
- **declared_by**: agent
- **declared_at**: 2026-09-18
- **why_not_measurable**: routines live in a scheduler this executor cannot
  query. The previous `CURRENT_STATE.md` asserted a routine was DISABLED and
  recorded, in the same file, that a later firing reported success with no
  commit ever reaching the branch — an unresolved contradiction that it
  presented as state.
- **what_would_verify**: a scheduler query by an agent that can make one, or a
  commit arriving on the branch from a runner. What this repository CAN say is
  measured instead: whether any capture is recorded in the manifest and when
  the newest one was retrieved.
- **status**: STANDING
