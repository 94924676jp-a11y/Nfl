# Perplexity Phase One × task #45: crosswalk, readiness and one integrated plan

- **Written:** 2026-10-11 17:12 UTC (1:12 PM ET).
- **Repository HEAD:** `4c80a712`. The bundle inspected `b88200de`; zero `.py` files changed in between.
- **Inputs:**
  - the step A audit: `AUDIT_45_AT_e21176c9.md`;
  - the bundle's own verifier receipt: `PHASE1_BUNDLE_VERIFIER_RECEIPT.json` (state PASS, exit 0, manifest `ae0a42cf…`);
  - the reconciliation of each finding: `INDUSTRY_PHASE1_CURRENT_HEAD_RECONCILIATION.json`. That file covers 13 Perplexity findings and 7 from the audit, each line range re-read at HEAD.
- **Read-only.** Nothing in production, the live Week-5 files or the uploaded lineups changed.
- **Not authorized by the bundle.** It grants no promotion, purchase or policy change.

## C. Crosswalk: experiment → what exists → its real consumer → gap → gate

| exp | what the repo already has | actual consumer today | gap | depends on | data / rights | offline test to write first | prospective validation |
|---|---|---|---|---|---|---|---|
| **E00** metric and reader contract | corrected readers `contest_intelligence.build`, `standings_addendum` (F02) | postgame reports | legacy `classic_week.standings` overwrites per slot and per contest (F01, `classic_week.py:233-236`); optimal-rate labels conflated (F03) | none | owner CSVs in repo | 32.52% + 6.36% = 38.88% through the real loader → report; two contests stay separate; empty lineup counted in the denominator | not applicable (correctness) |
| **E01** point-in-time contest archive | `nfl/dfs/history/contracts.py`, `nfl/field/showdown_field_archive.py`, freeze manifests | research only | joins of salary, identity and payout incomplete; profile keyed by owner entry count (F08) | E00 | 318 postgame-only pairs (bundle, not committed: owner contest data) | wrong-slate pool or a late snapshot invalidates the result; missing payout stays missing | not applicable |
| **E02** ownership | `nfl/field/ownership.py` (structural, not calibrated), `contest_ownership.py`, SC-OWN-ROTATION-2 | **none in selection** | no calibrated Classic ownership | E00, E01 | 4 Showdown slates + 1 Classic slate of labels | missing CPT ownership is never 0.5 × FLEX; timestamps verified | existing bars, ≥3 of 4 prospective slates |
| **E03** legal joint field | `showdown_shadow_field`, `showdown_archetype_field`, `contest_intelligence` | **none in selection** | no Classic field generator | E00, E01 | same | every generated roster legal; personal exposure caps cannot move the field | held-out field distance |
| **E04** duplication | B4/B3S `showdown_dupe_shadow` | shadow only, after upload | level and tail failed: sum ratio 0.16 (F04, frozen) | E00, E01, E03 | same | new challenger id; TB@DAL failure stays visible | per-fold ratio [1/1.5, 1.5], Spearman ≥ 0.6 |
| **E05** QB-conditioned offence + world integrity | QBCTX (failed its bar), `event_consistent_worlds` (SC-COH-1 failed its bar), `world_accounting_check` | **production worlds** (`classic_slate_run.efficiency_worlds`, F06) | W5-G18; 30,281 / 2,000 / 1,809 / 1,068 / 76 violations | E00 | in repo (pbp 2024-2026) | **this is task #45 clauses 3-4; not run as a separate track** (P1 below) | registered predictive gates on untouched weeks |
| **E06** stacks / bring-backs | declared `QB_STACK_MIN`, reported stack rates | production selection (declared rule) | no matched policy comparison | E00, E01, E03, E05 | in repo | a no-stack candidate is legal in the research arm; no double-counted correlation | unseen real slates |
| **E07** payout / multi-entry utility | fieldless quantile proxy (F10) | production selection | no payout tables; no field | E00-E05 | payouts not archived | ties across paid and unpaid ranks; payout shape alone can change rankings | ≥8 prospective contests |
| **E08** late swap | none (G-2) | none | everything | E00, E01, E03, E05, E07 | lock-time snapshots missing | — | — |
| **E09** public-code audit | none | none | licence unresolved | E00 | rights unresolved | — | — |

**Already satisfied:** F02 and F07 (reuse them). Nothing else in E00-E09 is satisfied at its real consumer.

**Overlap with the old evidence ledger.** C20, C36, C45, C47, C50 and C51 keep their recorded verdicts (`existing-claim-crosswalk.jsonl`). They are not new evidence.

## D. Readiness, in #45 dependency order, then the research prerequisites

| # | item | status | evidence |
|---|---|---|---|
| A | #45 audit at HEAD | **VERIFIED** | `AUDIT_45_AT_e21176c9.md` (`4c80a712`) |
| B | bundle integrity | **VERIFIED** (package only) | `PHASE1_BUNDLE_VERIFIER_RECEIPT.json` |
| P0-1 | tests cannot write the live or tracked tree | **FAIL** | 3 tracked files written by direct runs (audit section 6) |
| P0-2 | lineage: state hash checked; evidence after the projection marks it stale; release record (run id, commit, seed, packet hash, chain); release state in code; verifier reads tagged files | **FAIL** | L03, L04, L05 |
| P0-3 | final-world accounting is a pipeline gate that decides the release state | **FAIL** | L06; check exists, not wired |
| P0-4 | each contest optimised independently; the two 20-max sets distinct by default | **FAIL** | L01 |
| P0-5 | one governed entry point; fresh timezone-aware clock and lock check before any rebuild | **FAIL** | the orchestrator exists but was bypassed today; finalize reads a kickoff string, not a clock |
| P0-6 | event-triggered rebuild, bounded, with run lock and crash recovery | **FAIL** (missing) | no workflow or watcher runs Classic |
| P1-1 | participation state in the evidence schema (full / limited / questionable / early-exit risk / inactive) | **FAIL** | L02 |
| P1-2 | participation probabilities measured, not invented | **UNVERIFIED**: needs data (decision E1) | 2026 injury reports only; no snap or participation history in repo |
| P1-3 | per-world participation drives opportunities, teammates, QB, team volume and efficiency | **FAIL** | `p_plays` folded into mean shares (`showdown_draws.py:103`) |
| P1-4 | QB identity conditions team volume, receivers and the opposing DST | **FAIL** | W5-G18, `proj_v1.py:167` |
| P1-5 | final worlds satisfy box-score laws | **FAIL** | 30,281 violations; repair candidate failed its predictive bar |
| P1-6 | depth table on a consistent universe (L4/H3) | **PLANNED** | H3 preregistered, weeks 6-11 |
| E00 | metric contract at the real loader | **FAIL** (F01) | — |
| E01 | point-in-time contest archive | **UNVERIFIED** | joins incomplete |
| E02-E04 | ownership, field, duplication | **PLANNED**, after E00/E01 | shadow only |
| E06-E09 | stacks, payout, late swap, code audit | **PLANNED**, later | — |

## The integrated plan: one sequence, no duplicate tracks

**Rule: production code changes come before forecast-changing candidates.**

- P0 changes no number. It decides what a number is allowed to be called and where it may go.
- P1 changes forecasts, so each P1 piece runs as a declared arm beside the incumbent until its registered evaluation passes.
- E00/E01 are reporting and data work. They can run beside P1 because they share no files with it.

1. **P0-1 isolation guard.** A test may write only under a temporary root. `run_suite` already isolates; direct runs must refuse.
   - *Accept:* every module run directly inside the overlay leaves the upper layer empty of tracked paths.
2. **P0-2 lineage and release states,** as one module that every stage writes to and the verifier reads.
   - *Accept:* executable fixtures for each of these:
     - stale state;
     - evidence newer than the projection;
     - an exclusion run with no rebuild, which is labelled `SELECTION_ONLY_OVERRIDE` in the release record and next to the CSV;
     - a tagged file verified;
     - a release record carrying the full hash chain.
3. **P0-3 accounting gate.** `world_accounting_check` runs on the final worlds in the pipeline.
   - Any violation makes `CURRENT_AND_CERTIFIED` impossible: the result is `CURRENT_BUT_UNCERTIFIED`, with the counts.
   - *Accept:* today's 16:08 worlds, replayed as a fixture, come out `CURRENT_BUT_UNCERTIFIED`, never certified.
4. **P0-4 per-contest independence.** Each contest gets its own candidate draw and a selection that excludes lineups already chosen for an equal-size contest.
   - *Accept:* on the Week-5 fixture the two 20-max sets share 0 lineups.
   - The verifier fails equal-size contests that share more than a declared k (default 0).
5. **P0-5 one entry point.** `classic_slate_pipeline` gains these stages: accounting gate, release record, and a lock check from a fresh UTC clock against each game's kickoff.
   - The hand-run five-tool route becomes a refusal unless it is labelled.
6. **P0-6 trigger.** A watcher on new evidence packets and inbox items starts the pipeline under a run lock, with a bounded runtime estimate. If the estimate overruns the lock, it refuses and says so.
7. **P1-1 participation schema.** No forecast changes when no player is limited.
8. **P1-2 participation measurement** (needs decision E1).
   - From historical designations joined to per-play participation, measure:
     - P(inactive);
     - the distribution of share of normal snaps;
     - P(early exit) by designation, practice status, position and injury class.
   - Preregistered, with the held-out weeks declared.
9. **P1-3 participation in the worlds.**
   - Each world draws the player's participation.
   - The club's opportunity shares in that world mix the "present" and "absent" allocations by the share of snaps he played.
   - Team volume and efficiency move by the measured association. They are not fixed, and the effect is not invented.
   - *Accept:* the owner's fixtures.
     - A limited McLaurin yields several participation states.
     - Washington's QB and receivers move.
     - An inactive player is zero in every world.
     - Team totals reconcile.
10. **P1-4 QB conditioning** (QBCTX successor, new id).
    - *Accept:* the clean CHI counterfactual changes receiver targets and yards and the GB DST.
11. **P1-5 coherent final worlds** (successor to SC-COH-1, new id).
    - Every law is at 0 by construction.
    - The predictive gates are taken from the failed predecessor, unchanged.
12. **P1-6 H3**, prospective weeks 6-11, already registered.
13. **E00, then E01**, beside steps 7-11.
14. **E02 → E03 → E04 → E06 → E07**, in dependency order, after E00/E01 and once P1-5 has produced credible worlds.
15. **E08, E09** last.

## E. Decisions that need the owner (real boundaries only)

1. **E1: network acquisition of historical football data** for P1-2. Nothing has been downloaded or kept.

   | source | content | terms recorded in `nfl/research/integrations/PLATFORM_TERMS_AND_APIS.md` |
   |---|---|---|
   | nflverse `pbp_participation` 2016-2025 | who was on the field each play; FTN, CC-BY-SA 4.0 | the cleanest rights |
   | nflverse `injuries` 2016-2025 | Wednesday-Friday practice status and game designation | the upstream NFL terms apply; row is UNKNOWN |
   | nflverse `snap_counts` | per-game snap counts | sourced from Pro Football Reference, whose terms are PROHIBITED_BY_TERMS for tools built on the data. **Recommend not using.** Participation gives snaps directly. |

   - **Recommendation:** approve participation plus injuries, store them with provenance under `nfl/vintage`, and do not use snap counts.
   - Without E1, P1-2 stays UNVERIFIED and no limited-player probability is produced. The schema (P1-1) and the mechanism (P1-3) can still be built and tested on declared fixtures. A fixture is not a forecast, and it will be labelled that way.

2. **E2: what replaces the incumbent while P1 candidates are unvalidated.** This is a conflict between two standing instructions:
   - "treat accounting and QB defects as required work";
   - "no promotion without gates". Both earlier repair candidates failed their predictive bars.

   **Recommendation:**
   - build P1 completely, with the integration tests passing;
   - from week 6 run it beside the incumbent;
   - publish both portfolios with their release states, and you choose which to upload;
   - promote only when its registered evaluation passes.

   Until then no file can be `CURRENT_AND_CERTIFIED`.

3. **No other boundary is crossed.**
   - P0 changes no forecast and has standing direction ("make these enforced properties of the working system").
   - The 20-max independence default was set by you (clause 6).
