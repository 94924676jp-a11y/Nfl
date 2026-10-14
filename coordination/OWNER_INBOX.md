# OWNER_INBOX — the paste-once fallback

**This is a fallback, not the steady state.** The intended flow is
repository-native: the owner (or ChatGPT on the owner's behalf) writes a file
into `CHATGPT_OUTBOX/` and Claude reads it. This file exists for the case
where the writing side has read access but not write access, and a directive
has to be pasted in once by hand.

## Contract

1. **Append. Never edit above.** A directive already in this file is a
   historical record. Claude will not silently rewrite one, and
   `validate_coordination.py` treats a vanished directive ID the way it
   treats a vanished owner decision.
2. **Every directive gets an ID** on its heading line: `## OD-NNN · short
   title`. IDs are monotonic and never reused.
3. **Claude ingests, it does not authorize.** On reading a new directive,
   Claude converts it into the correct artifact — a queue task, an
   `OWNER_DECISIONS.md` entry, or a file in `CHATGPT_OUTBOX/` — records the
   directive ID in `HANDOFF_LOG.jsonl`, and marks the heading `[INGESTED
   <commit>]`. **Creating a queue row is not authorizing it**: a new task
   arrives `authorized=false`, and only an explicit owner authorization in
   the directive text sets it true.
4. **An owner decision is only created or changed by a directive that says
   so.** Claude does not infer a ruling from a task description.

## Template

```
## OD-007 · short title

AUTHORIZE: ENG-004            (optional; omit and the task stays unauthorized)
DECISION: D-12 <one-line ruling>   (optional; creates an OWNER_DECISIONS entry)
QUEUE: ENG-013 <title>        (optional; creates a DRAFT task)

<body — objective, acceptance tests, what is explicitly NOT authorized>
```

The line that matters most is the one naming what is **not** authorized.
Every large slice in this project that went wrong went wrong by expansion.

## Ingested directives

## OD-001 · NFL permanent repair, cycle 2: policy decisions and priority order  [INGESTED: see HANDOFF_LOG]

Pasted by the owner in the engineering session, 2026-10-14 (UTC). Recorded here because
`coordination/OWNER_DECISIONS.md` is `always_denied` to agents under `MODE_POLICY.json`; the D-12 entry below
must be written by the owner (or the owner layer). Until then this directive is the record.

DECISION: D-12 (pending owner write to OWNER_DECISIONS.md)

1. Classic practice-squad eligibility: preserve uncertainty in pregame modeling, but a confirmed non-elevated
   practice-squad player must not receive active-game opportunity. Use dated roster evidence and transaction/elevation
   records. If eligibility remains unresolved, do not silently classify the player as active. Align Classic and
   Showdown through a shared, tested policy.
2. ENG-014: Certified Showdown forecasts and portfolios must require valid, sufficiently current roster evidence. A
   direct run without this evidence may operate only in explicitly labeled diagnostic mode and must never produce a
   releasable upload. Runs after kickoff must not be represented as prelock forecasts.
3. ENG-017: Approved. Every run must record the effective forecast arm, selector version, candidate-generator version,
   contest-overlap policy, exposure and relaxation configuration, input vintages, hashes, cutoff, and release status.
   Environment variables cannot silently determine undocumented production behavior.
4. Maintain the existing governed incumbent as the production reference. SEL-2 and corrected forecasting remain
   experimental unless explicitly promoted through the registered gates. Do not interpret this as approval to release
   an incumbent that fails safety checks.
5. Do not use an uncertain data license as authorization for retention, public publication, or model training.
   Continue read-only permissions review and permitted research.

AUTHORIZE: ENG-014, ENG-017 (by decisions 2 and 3)

PRIORITY: P0-A PIT-D1 fail-closed + audit of all Classic and Showdown replay paths; P0-B authoritative full-suite
baseline at current HEAD, every red module identified, zero-check functions eliminated, test runs may not corrupt
tracked evidence; P1-A shared roster-eligibility contract in both pipelines, ineligible simulated usage zero before
selection; P1-B production-call-path and provenance gaps, load-bearing vs test-only guards; P2 the pre-registered CG-1
as shadow. The 55-entry issue ledger and the engineering queue are the source of truth; no competing backlog.

NOT AUTHORIZED: production promotion, money actions, new external permissions, material strategy changes; claiming
the system is fully repaired, predictively superior or production-certified without the evidence.

## OD-002 · Cycle 2 roster policy and acceptance (owner, 2026-10-14, relayed in chat ~15:00Z)

Recorded verbatim in substance by the engineering agent; the authoritative OWNER_DECISIONS.md entry is the owner's to
write (always_denied to agents).

DECISION: approve the shared three-state eligibility contract, clarified (ELIG-D3):

1. CONFIRMED INELIGIBLE: exclude from participation and opportunity projections when sufficiently authoritative,
   game-specific evidence establishes ineligibility -- consistently for reserve, exempt, released and non-elevated
   practice-squad players, in Classic and Showdown alike. Lack of a corroboration list must not silently override
   clear roster evidence. Conflicting sources produce a refusal until resolved.
2. CONFIRMED ELIGIBLE: include where valid roster/transaction evidence establishes eligibility, subject to normal
   playing-time and role uncertainty. Eligibility does not guarantee participation.
3. UNRESOLVED: missing elevation records or incomplete roster captures are not proof of ineligibility. Preserve the
   classification and record exactly which evidence is missing. Do not invent an arbitrary probability of eligibility.
   Non-releasable research may use separately labelled scenarios only if supported by registered historical evidence.
   Certified production must not silently convert unresolved players into confirmed active or confirmed out: enforce an
   evidence-completeness gate appropriate to the contest and release cutoff.
4. Audit the 99 withheld W5 players as a coverage problem (truly ineligible vs unresolved; team-opportunity distortion).
5. P0-A: PIT-D1 is not closed until replay entry points, import-time bindings, derived caches, week-level filtering,
   fitted parameters and final artifacts are covered; pit_exempt states are NOT_POINT_IN_TIME, barred from release and
   from predictive-performance claims; verify no production path can use the exemption.
6. P0-B: full suite and production gate reported separately; the gate is not made green by excluding known
   production-critical failures, skipping checks or weakening assertions. PERF-D1 kept only with output equivalence,
   correct invalidation and no cross-slate or point-in-time contamination.
7. Then an evidence-backed readiness report (HEAD and commits, fixed vs open, both test results, Classic and Showdown
   integration evidence, eligibility coverage and roster-source freshness, PIT negative controls, release blockers,
   deployed vs overlay).

NOT AUTHORIZED: promoting forecast arms, altering real-money strategy, claiming production certification.

