# NFL Greenfield — complete session record

**Date:** 2026-09-06 · **Session:** one continuous working session
**Output:** 26 commits on `mlb-prop-system-v7@claude/nfl-greenfield-architecture-stsxmk`,
2 commits on the new `94924676jp-a11y/nfl`
**Tests:** 904 assertions across 12 files, 0 failing (811 NFL + 93 platform)
**Subagents:** 14 — 8 research workers, 3 correction workers, 3 adversarial test writers

**Where it ended:** NFL-0 evidence system built and tested. **No predictive model
exists. NFL-1 is not authorised.** G0A stands at **11 of 12**, failing on one
external dependency.

---

## 1. What was asked

Start NFL as a **greenfield sibling product on a shared scientific platform** —
not a fork of the MLB engine with football nouns substituted. Run an
eight-worker architecture pass, research only, and return the foundation and
experimental roadmap before any predictive code is written.

Five owner directives followed, each correcting the last.

---

## 2. The five directives

| # | Directive | Outcome |
|---|---|---|
| 1 | Greenfield architecture pass, 8 workers | Foundation + roadmap + outbox assignments |
| 2 | Correction pass — 8 required items | G0A/G0B split, cold-start freeze, three corrections of mine |
| 3 | **Authorise G0A build** | 7 controls built; adversarial tests found 12 defects in them |
| 4 | Owner override: 10/12, close items 1 and 4 | Item 4 closed; item 1 external |
| 5 | External evidence integration | Executor question settled; **11/12 final** |

Plus, unprompted by a directive: the NFL work was extracted into its own
repository at the owner's instruction.

---

## 3. The organising result

**Opportunity is predictable. Efficiency mostly is not.** Reached independently
by three workers, from three position groups, on identical random game splits.

| Position | Opportunity | r | Efficiency | r |
|---|---|---|---|---|
| WR/TE (n=219) | pass-play participation | **0.948** | catch rate | 0.300 |
| | target share | **0.915** | yards per target | 0.253 |
| | air-yards share | **0.887** | TD per target | 0.167 |
| RB (n=92) | carry share | **0.926** | yards per carry | 0.385 |
| QB (n=40–46) | designed rushes/game | **0.911** | interception rate | 0.212 (CI spans 0) |

**The sharpest form, and the thesis of the whole architecture:** prior-form
prediction of QB game passing yards reaches **r = 0.136**. The *same rate model*,
handed the **realised** dropback count, reaches **r = 0.636**. Prior dropbacks
predict realised dropbacks at only **+0.147**.

That gap is not model quality — it is the volume forecast. Nearly all available
discrimination sits in a quantity the system does not yet predict, and 0.136
lands essentially on top of MLB's 0.1101 baseline.

Forward-chained, RB efficiency scores **negative R² against the pooled mean** —
carrying a back's own prior efficiency forward is worse than a constant. For
receivers, predicting touchdowns from a player's own prior TD rate gives RMSE
**1.771** against **1.269** for ignoring the player entirely.

---

## 4. Five parts of the proposed design the data did not support

| Proposed | Measured reality |
|---|---|
| Targets per route run | `participation.route` is **one scalar per play** — the *targeted* receiver's route. Per-player routes-run is not derivable from any reachable feed. Found independently by two workers. |
| Slot / wide alignment | `offense_positions` is alphabetically sorted on **45,919/45,919** rows. Not recoverable. |
| Receiver vs specific corner | Opposing defence explains **0.66%** of receiver-game yardage residual, placebo p = 0.113. REJECTED — SOURCE INSUFFICIENT. |
| The goal-line back | Own goal-line share adds **+0.5%** over overall carry share. The **third-down** role is the real one (+13.3%). |
| Backup absorbs the vacated role | "Next-man-up takes all" is the **worst** of five rules. Only **~47%** of removed share returns to the position group — renormalising over-projects the backup **~2×**. |

---

## 5. Results that bound ambition

**The SD ratio is not a dial.** At calibration slope 1.0, `slope = r·SD_act/SD_pred`
collapses to `SD_pred/SD_act = r`. A calibrated model's SD ratio **equals its own
discrimination**. MLB's 0.18 was never a ceiling — it was a slope of 0.61.
Estimated NFL ceiling: 0.34–0.46.

**The baseline bar is high.** A trivial **market-free** forward-chained baseline
reaches **r = 0.339, slope 1.021** on team points — roughly 3× MLB's. Game totals
are the *harder* target: the book itself manages only 0.305 there vs 0.501 on margin.

**Volume is not a team trait.** Plays per game: split-half 0.220, **shrunk ICC
0.000**. Drives per team-game: **0.001**. Pace predicts next-half play count at
**r = −0.099** — the wrong sign.

**Game script supplies the variance instead.** Q4 pass rate spans 0.284–0.878 by
score state against a 0.042 between-team SD (~3×), while total plays barely move
(+0.100). Pass and rush attempts are anti-correlated *through the scoreboard*, so
independent marginal draws would reproduce every marginal and get the joint wrong.

---

## 6. The availability table

Cluster-bootstrapped by team-week, replicated out-of-sample on 2025:

| Designation | n | P(play) 2024 | P(play) 2025 |
|---|---|---|---|
| Out | 1,116 | 0.0009 | 0.0000 |
| Doubtful | 194 | 0.0000 | 0.0000 |
| Questionable | 1,513 | **0.6550** | 0.6518 |

The conventional reading of Doubtful ≈ 25% and Questionable ≈ 50% is **wrong by
25 and 15 points**.

**Role given active is the larger half.** Within the off-report population,
P(≥1 snap) moves 0.8505 → 0.9905 across prior-snap buckets — but
**P(offense_pct ≥ 50%) moves 0.0098 → 0.9325, a factor of 95.**

---

## 7. What was built (G0A controls)

| Artifact | Purpose |
|---|---|
| `nfl/ingest/allowlist.py` | Column quarantine with a **purpose axis** — ARCHIVE/DESCRIPTIVE read freely, FORECAST refuses. 47 model-derived, 8 market, 5 outcome, 11 post-hoc columns. |
| `nfl/ingest/validate.py` | Non-null validation that **requires a denominator**, so a correctly-scoped null is not read as data loss. |
| `nfl/ingest/identifiers.py` | `PFR_ID_UNMAPPED` named failure; name-matching **refused by design**. |
| `nfl/ingest/eligibility.py` | `PREDICTION_TIME_ELIGIBILITY_UNAVAILABLE` as an explicit debt. |
| `nfl/identity/execution_identity.py` | Input hashes **inside** the fingerprint — the half MLB's M0 omitted. |
| `nfl/identity/seal.py` | Immutable pre-kickoff seal; corrected clock order. |
| `nfl/identity/effective_scope.py` | Game-level applicability, content-checked not label-checked. |
| `nfl/capture/schedule.py` | Kickoff-anchored windows; inactives **T−90 → T−10, 80 min**. |
| `nfl/capture/registry.py` | Three-axis source model: authority × source status × executor access. |
| `nfl/tools/capture_vintage.py` | Append-only vintage capture, five clocks, raw-bytes-first. |
| `nfl/tests/bypass.py` | Proves a guard is **load-bearing** — the test must fail when the guard is bypassed. |

**Frozen artifacts:** cold-start specification (`b356ecaa…`, before any 2026
outcome existed), draw-archive schema (`04114a4f…`), and the three-arm evaluation
taxonomy.

---

## 8. Corrections — the part worth reading

Sixteen substantive corrections were made, most of them to my own work.

### Mine, caught by workers or by measurement

| # | Claim | Correction |
|---|---|---|
| 1 | "~1,131 games with threefold clustering" | Treated an SE ratio as a sample multiplier. Withdrawn. |
| 2 | `route` supports targets-per-route-run | It is one scalar per play. **Withdrawn**; two workers found it independently. |
| 3 | NGS receiving is 404 | Wrong extension — it is `.csv.gz`, 2016–2025. |
| 4 | `ngs_air_yards` is usable | **0 non-null of 45,919.** REJECTED — SOURCE EMPTY. |
| 5 | `pass_attempt` as completion denominator | **Includes sacks.** Gives 0.6072 vs 0.6555 — an error larger than the entire between-QB spread. |
| 6 | `PLAYER_NOT_ON_REPORT` = P(play) 0.943 | Measured on the **opposite population**. Correct figures: 0.8876 / 0.5553 / 0.0000. |
| 7 | "2,000–3,000 game-equivalents / 7–11 seasons" | A **unit error**: a game count × a row-level DEFF on a calibration statistic. The repo had already diagnosed this exact defect. |
| 8 | Market gate "3 weeks, 369 player-games" | 369 was never per-market. Binding constraint is `min_distinct_dates = 10`. |
| 9 | G0A 12/12 | **Owner overruled to 10/12.** I marked item 4 PASS because all five fields existed — schema-correctness standing in for semantic-correctness. |
| 10 | Item 4 fixed | **Defeated by relabelling**: a season string labelled `DATE_INTERVAL` certified any game. The gate read the label, not the content. |
| 11 | "Capture scheduled and demonstrably running" | **It had never run.** Zero scheduled captures completed. A false green. |
| 12 | nfl.com "measured at 000 / unreachable" | It is a **local proxy `CONNECT` 403**. DNS resolves. The source answers 200 externally. |
| 13 | Manifest recorded every source | It **omitted every BLOCKED source** — the durable record contradicted the console. |
| 14 | "No unattended executor exists" | **Wrong.** A repo-attached session runs clean; the blocks were a repo/auth artefact. |

### Found by adversarial tests, in controls I had just written

**12 defects in the G0A build**, three reproducing the repository's own catalogued
failure classes *inside the guards written to prevent them*:

- `is_null` did not recognise `float('nan')` — so fed the real motivating case
  through a pandas reader, the validator returned **PASS at 1.0 non-null**.
- `HEADER_ONLY_PAYLOAD` counted newlines, not data rows — a header padded with
  blank lines became a recorded vintage.
- The model-derived count said **45** over a tuple of **41** while the provenance
  audit said **31**. Three copies, three numbers, nothing comparing them.

Plus **4 more** in the item-4 fix, including the relabelling bypass.

---

## 9. Current state

### G0A: 11 PASS / 1 FAIL

**Item 1 fails on egress alone.** The perishable official cascade — practice
participation, final game status, inactives — is not captured.

- nfl.com answers **HTTP 200 externally**; this environment's proxy answers
  **403 to `CONNECT www.nfl.com:443`**. DNS resolves to 151.101.65.55.
- Verified in a *second* cloud session: same 403. The policy is environment-level.
- Every capture run prints its own gap:
  `UNMET CAPTURE TARGETS: ['final_status', 'inactives', 'practice']`

**The scheduled-capture gap, stated precisely:** `create_session` can attach a
repository source but does not recur; `create_trigger` recurs but cannot attach
one. A scheduled, unattended, repo-attached capture is **not expressible with the
tools available**. The trigger is disabled for that reason.

### Open debts

| Debt | State |
|---|---|
| `PREDICTION_TIME_ELIGIBILITY_UNAVAILABLE` | OPEN — may not be closed with `weekly_rosters.status` (post-hoc: INA → 0 snaps of 3,438) |
| `NFLVERSE_INJURY_SOURCE_STATUS_CONFLICT` | RESOLVED by appended record — documentation stale, upstream replaced, 2025 artifact retroactive |
| A3 ffopportunity | CLOSED — `REALIZED-OPPORTUNITY ORACLE BENCHMARK`, non-deployable |
| Six of eight scheduler cadences | `confirmed=False` — inferred, not externally verified |

---

## 10. Repository layout

The NFL work now lives at **`github.com/94924676jp-a11y/nfl`**.

```
sportsplatform/governance/   Outcome, Provenance, Scorecard + 3 replay tests
nfl/ingest/ identity/ capture/ tools/ tests/
nfl/research/                12 worker documents (~380 KB measured research)
nfl/vintage/                 durable gzipped capture blobs
returns/                     5 owner return records
```

The package is `sportsplatform`, **not** `platform`: a top-level `platform/`
shadows the stdlib module of that name, which `governance/environment.py` imports.

`PLATFORM_PROVENANCE.json` pins the MLB source commit and records the drift
hazard: these modules now exist in two repositories and nothing compares them.

---

## 11. Outstanding, awaiting the owner

1. **The MLB repo still contains the full `nfl/` tree** — a duplicate of the new
   repository, and the drift problem in concrete form. Retiring it is a
   deliberate act I have not taken.
2. **NFL-1 is not authorisable** under the existing gate without an explicit
   waiver naming Item 1. G0A is 11/12 and the gate requires 12/12.
3. **What would close Item 1** is not code in either repository: an executor with
   egress to nfl.com that can run at T−90, and a scheduled mechanism that can
   attach a repository source.
4. **T1 and T3** are closed by owner ruling (retain the 2002 floor; retain the
   home term). The cold-start constants must not be revisited after the first
   2026 outcome.

---

## 12. The standard applied throughout

> The goal is not to make the checklist green. The goal is to make a false green
> state difficult to produce.

Every control carries a positive test, a seeded-violation test, and — for
critical guards — a **load-bearing** test that fails when the guard is bypassed.
Fourteen of the corrections above are to my own claims. **The honest result is
11/12, and 11/12 is what is recorded.**
