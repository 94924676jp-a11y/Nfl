# Session summary — 2026-09-07

**Repository:** `94924676jp-a11y/nfl` · **HEAD at writing:** `aa2a5d1` (plus bot
capture commits since)
**G0A:** **11 / 12** throughout. Item 1: PARTIAL / PENDING REAL EVENT.
**NFL-1:** never authorized, never executed, never requested.
**2026 outcomes consumed:** none.

Six owner directives were worked in this session: **Directive 6** (close G0A
Item 1 by evidence), **Directive 7** (build the event-anchored T−90 path),
**P1** (opportunity forecasting baseline), **P2** (appearance × conditional
usage), **P3** (availability quality, role transition, identifier integrity,
selective mixture), and the **P3 R1 addendum**.

---

## The short version

Two tracks ran in parallel and neither contaminated the other.

**The G0A capture track** got the piece it was missing: an execution that knows
which game it is for. A T−90 workflow is now generated from real kickoff times,
every capture declares its target set *before* it fetches, and coverage verifies
the whole chain from persisted artifacts. Nothing is claimed as discharged —
the first real window opens **2026-09-09T22:50Z**, ~55 hours out, and the
system currently and correctly reports `covered=0`.

**The research track** established, in order: opportunity is predictable mostly
by persistence (P1); "who plays" and "how much" are different problems that a
single model gets wrong (P2); and the information feeding the appearance model
is the binding constraint, not model capacity (P3).

**Six errors of mine were found and corrected in place**, four of them by
results that looked *too good*. They are listed in full at the end, because a
summary that reports only the wins is the failure mode this project exists to
prevent.

---

## 1. Directive 6 — closing G0A Item 1 by evidence

### The parser, built from captured bytes

`nfl/parse/injury_report.py`, written against a real 328,961-byte nfl.com
artifact rather than remembered markup. Output: **11 rows, 2026 week 1, 16
games**, identical across all captures of that page.

Attribution is earned, never assumed:

| Level | How | Authority |
|---|---|---|
| season / week | the selected `<option>` **and** the `<title>`, which must agree | two agreeing signals |
| team | the page's **own** matchup strips (abbreviation and full name adjacent) | derived deterministic |
| game | each strip names two teams; a section's team must belong to its pair | derived deterministic |
| player | profile slug + display name only | source-provided, unresolved |

**85 adversarial assertions** covering the directive's fourteen requirements,
plus **four guard-deletion proofs** — delete the control, replay the same seeded
violation, and confirm it now gets through.

### The T−90 false green, found and killed

`registry.unmet_targets` reported **all three perishable targets MET** while the
earliest window was two days away and not one capture carried a `game_id`. It
answers "was this kind ever captured at all" — no time dimension, no game
dimension. Meanwhile `schedule._clears` was already refusing exactly that. Two
modules, opposite answers, and the runner printed the optimistic one.

`nfl/capture/coverage.py` made the game-anchored answer the printed one. The
guard-deletion proof is stark: reduce `_clears` to a timing check and **one
unattributed capture "covers" 16 targets**.

### Corrections to my own claims

The parser docstring said the page carries no kickoff time. **It does** — 79
`StartTime` values and 79 `GameId` UUIDs in an embedded broadcast payload. The
parser still does not consume it (79 entries against 16 matchup strips; the
correspondence is nowhere stated on the page), but that is now a named open item
rather than a claimed absence.

---

## 2. Directive 7 — the event-targeted capture path

### What §6 caught in what I had just built

`attribution.claims_for` computed a capture's target set from `retrieved_at` — a
clock that exists only *after* the bytes arrive. Every claim was a post-hoc
reading of a timestamp, and a capture that wandered into a window by coincidence
produced the same record as one taken because the window was open.

`nfl/capture/execution.py` declares the target set **at run start, before any
fetch**. `attribution.py` is retired to a stub that raises — a stub rather than a
deletion, because a deleted file can be re-added by someone who remembers it
working.

### Four scopes kept apart, never one field

| scope | meaning |
|---|---|
| `source_artifact_scope` | the page is `LEAGUE_WIDE` however it was fetched |
| `execution_target_scope` | the obligations this run set out to satisfy — **where a game_id lives** |
| parsed-row applicability | parser territory, not decided at capture |
| `coverage_obligation` | what this capture is *permitted* to discharge |

### Discharge is fail-closed

Only `SCHEDULED_WINDOW_ANCHORED` — the generated workflow, fired by the
scheduler — can discharge. A periodic sweep cannot (§5). **A manual dispatch
cannot either**: a mechanism that let me dispatch during a live window and
record a discharge would be a way to hand-write the result of the one test this
gate exists for. Unknown workflows fall back to the non-discharging class.

**This reversed something I had told the owner** the day before, when I said a
baseline run landing in a window "counts exactly the same". It does not.

### Coverage now opens the file

§5 requires a real persisted raw artifact, so coverage gunzips each blob and
rehashes it rather than believing the row. That immediately surfaced **30 rows
failing `RAW_SHA256_MISMATCH`** — the known `.reduced` naming weakness,
previously prose, now caught by a verifier. All three official sources verify
6/6.

### Verified on real runners

Workflow registered as *NFL T-90 anchored capture*, `state: active`. Both live
executions classified themselves correctly and **neither can discharge**: my
dispatch as `OPERATOR_TARGETED`, the baseline as `PERIODIC_SWEEP`. The only
thing that will be able to is a `schedule` event inside a real window.

`nfl/tools/preflight_t90.py` runs §10 as a command — **10 checks, 0 failing** —
and `test_preflight.py` breaks each one on purpose to confirm it notices.

---

## 3. P1 — opportunity forecasting baseline

Frame: nflverse **2020–2025**, 57,670 player-games over 3,230 team-games and
2,234 players, extended to 83,144 with pregame-identifiable non-appearances.
`pbp_2024` and `part_2024` md5s match those recorded in the repo's earlier W4
research exactly.

### The main result is a disagreement between two arms

| | Unconditional | Conditional on appearing |
|---|---|---|
| `snap_share` | persistence wins, 4/4 seasons | **EWMA wins, 4/4** |
| `rpr` | persistence wins, 4/4 | **EWMA wins, 3/4** |
| `carry_share` | persistence wins | **EWMA wins, 4/4** |
| `pass_att_as_passer` | persistence wins, 4/4 | **EWMA wins, 4/4** |

Unconditionally, persistence wins by exploiting **absence carryover** — a player
who did not play last week has `lag1 = 0` and mostly stays there. Pooling the
two questions does not merely hide a subgroup; **it inverts a model-selection
decision**.

### Other findings

- **Role change** is ~27% of player-games and roughly doubles error:
  `snap_share` MAE 0.123 → 0.233, r 0.80 → 0.45.
- **Team dropbacks are near-unforecastable** from a QB's own history:
  r **0.10–0.22**, and last week's value is *worse than the league mean*. That
  term multiplies every player projection.
- **Vacated opportunity does not transfer proportionally.** 285 events, 4,231
  surviving teammate games: proportional MAE **0.0453** against **0.0384** for
  assuming no transfer, winning **14.8%** of the time. The rule everyone builds
  is worse than doing nothing.

---

## 4. P2 — appearance × conditional usage

**Stage A works.** AUC **0.85–0.87** for "will he take a snap", **0.92** for
"will he play more than half the snaps". Meaningful workload is *more*
predictable than mere presence — the opposite of the intuitive expectation.

**A×C raises correlation in 20 of 20 target-seasons** but beats the P1 incumbent
on MAE in only 11 of 20.

### 2025 is the finding, not an anomaly

| | 2024 | 2025 |
|---|---|---|
| injury feature | available | **absent** |
| Stage A Brier / AUC | 0.1288 / 0.8715 | 0.1544 / 0.8126 |
| A×C vs U on snap share | **−0.0078 ✓** | **+0.0069 ✗** |

A weaker appearance probability multiplied into a good conditional forecast is
worse than not multiplying at all. **This is the strongest empirical argument
for the T−90 capture track**: it is the input that decides whether the two-stage
model is worth having.

### Two directive expectations contradicted by measurement

- **Shrinkage for low-history players is monotonically harmful** on every target
  and season — unshrunk 0.107–0.145 against 0.180–0.227 shrunk. Between-player
  variance in role exceeds sampling noise in a 1–3 game share.
- **Redistribution has no single mechanism.** Backup-weighting cuts snap and
  route error 11%; for targets, red-zone and third-down work **no rule beat
  doing nothing**. Proportional is worst or near-worst in all six classes.

---

## 5. P3 — availability, role transition, identifiers, selective mixture

### Q3 — identifier repair is the clearest result in the session

| | rows | with snap share | missing | loss |
|---|---|---|---|---|
| P1/P2 name+team join | 57,670 | 55,000 | 2,670 | **4.630%** |
| **P3 identifier join** | 57,670 | **57,594** | **76** | **0.132%** |

Through the repository's **own** `Crosswalk` on nflverse `players.csv` (22,653
pairs, injective). **No fuzzy matching** — `map_by_name` exists and refuses by
construction. The `weekly_rosters.pfr_id` alternative was measured and
**rejected**: 77.51% coverage, two real collisions.

**Where both joins fire they never disagree** in ~55,000 rows. The old join was
*incomplete*, not *wrong* — but 4.6% of the population was silently absent from
every snap-share number, rising to 6.1% by 2025.

### Q1 — the headline is a data fact, not a model result

The directive asks whether a practice **sequence** beats a final designation.
**It cannot be tested.** The injuries file holds **exactly one row per
player-week with one timestamp** (2022: 5,450 rows / 5,450 player-weeks). The
Wed→Thu→Fri progression does not exist historically. My cross-week substitute
contributes **between −0.0005 and +0.0008 Brier: nothing.**

Stage A improves 0.1286 → 0.1257 from teammate availability and role volatility
— both an order of magnitude below the injury designation P2 already had.

### Q2 — role transition is predictable asymmetrically

| | AUC |
|---|---|
| `from_starter` (losing a role) | **0.839** |
| `to_starter` (gaining one) | 0.769 |
| `down_20` | **0.820** |
| `up_20` | 0.786 |

The predeclared stability rule selected `pos_specific` (AUC 0.794, sd 0.0135)
**over the higher-AUC `from_starter`** — recorded rather than quietly improved
on.

### Q4 — the selective policy's value is defensive

Beats plain U on 6 of 8 test-season comparisons, mechanical A×C on 3, never
loses. What it reliably does is **decline the mixture when the information is
absent**: in 2025, `P2_info_quality` uses A×C on **0% of rows** and turns P2's
2025 regression into a tie.

| 2025 | snap_share | rpr |
|---|---|---|
| U | 0.1551 | 0.1564 |
| mechanical A×C | 0.1574 (**worse**) | 0.1609 (**worse**) |
| selective | **0.1551 (= U)** | **0.1564 (= U)** |

**The price of predeclaration is reported rather than taken**: the post-hoc
oracle would have scored 0.1508 on 2025 `snap_share`, a 0.0043 gap I gave up by
fixing the policy on the tuning seasons.

### 2025 archival injuries

**UNAVAILABLE — NO TRUSTWORTHY HISTORICAL VINTAGE FOUND** from this executor.
GitHub keeps only current release assets; archive.org returns 000 through the
proxy. The Wayback path is documented for the networked agent. Nothing was
backfilled.

**28 adversarial checks, 0 failing**, including four seeded leaks that all light
up and both required guard-deletion proofs.

---

## 6. P3 addendum — the R1 review, and a correction it caught

The owner's clock-taxonomy qualification landed on a real overclaim. P2 and P3
called the injury feature "chronology-proven" and "provably pregame". What I
established is narrower: the **surviving** row's own `date_modified` precedes
kickoff **in the final file** — *retrospective chronology defensibility*, not
*prospective capture integrity*.

The 2024 file demonstrates the difference: its two duplicate player-weeks are
both mid-week revisions, **Questionable → Out hours apart**. Since the file
normally keeps one row, where a revision happened the survivor is the later
state — one that did not exist at an earlier forecast time.

**Measured exposure, which sharpens and rehabilitates the feature:** of 27,600
rows 2020–2024, **99.09% are stamped more than 24h before kickoff** and **not
one inside the final 90 minutes**. Strong for a T−90 forecast; still not proof
of prospective integrity, which only a captured artifact with its own
`retrieved_at` can have.

**An assumption I never stated, now stated:** Stage A implicitly assumes a
forecast time at or after the final pregame filing (~T−24h).

R1's findings are recorded as concordance, **not adopted** — no external number
enters any model, feature, threshold or report. R2, R3, Benchmark Capture and
DFS Historical Capture are logged as backlog; none executed.

---

## Six errors of mine, corrected in place

Four were caught by results that looked **too good**.

| # | Error | How it surfaced |
|---|---|---|
| 1 | `snap_share` divided by 100 twice — `offense_pct` is already a fraction | Reported MAE **0.0015** against a true 0.152; the most forecastable quantity in the study by two orders of magnitude |
| 2 | `scrambles` charged to the passer, but `passer_player_id` is NULL on all 1,134 scramble plays | Column structurally zero; baselines "predicted" it with MAE **0.0000** |
| 3 | Role-change model scoring **AUC 0.9999** | P1's label is a function of prior games only — a definition predicting itself. Reframed to include game *t*; honest AUC 0.74–0.79 |
| 4 | Target share denominated on `pass_attempt`, which includes all 1,314 sacks | Ratio 0.8896 instead of 1.0 — offensive-line noise injected into a receiver metric |
| 5 | **A subgroup table written from expectation, not read from the results file** | Caught before publishing; the real numbers say close to the opposite |
| 6 | Selective policy chosen **per evaluation season** — after the outcome | Fixed to tuning seasons only; the 0.0043 oracle gap is now reported |

Plus two process failures worth recording: I misread a hardcoded log line as a
filename and my own `mv` overwrote the repaired panel (caught by checking
contents, not the message), and two of my concurrent background rebuilds raced
and one deleted the other's output. Neither reached a reported number.

---

## Current state

| | |
|---|---|
| G0A | **11 / 12** — unchanged by any research work |
| Item 1 | PARTIAL / PENDING REAL EVENT |
| Test suite | **1,230 assertions, 19 suites, 0 failing** |
| Pre-flight | **10 checks, 0 failing** |
| First T−90 window | `2026_01_NE_SEA`, **2026-09-09T22:50Z → 00:10Z**, ~55h out |
| Coverage now | `DEFERRED[NO_WINDOW_HAS_CLOSED_YET]` — covered **0**, missed 0, pending 63 |
| Live captures | 45 captures, 327 manifest rows, 118 content-addressed blobs |
| NFL-1 | not authorized, not executed |

Three G0A tests went red during the session as the live capture series grew past
the snapshots I had written them against. Each was a correct failure and each was
fixed by keying the assertion to the durable property rather than to the
snapshot — most recently by selecting test pairs on content instead of sort
order.

---

## Reports produced

| File | Directive |
|---|---|
| `TASK_REPORT_2026-09-07_G0A_ITEM1.md` | Directive 6 |
| `TASK_REPORT_2026-09-07_T90_ANCHORING.md` | first T−90 authorization |
| `TASK_REPORT_2026-09-07_DIRECTIVE7.md` | Directive 7 |
| `TASK_REPORT_2026-09-07_P1_OPPORTUNITY.md` | P1 |
| `TASK_REPORT_2026-09-07_P2_APPEARANCE_USAGE.md` | P2 |
| `TASK_REPORT_2026-09-07_P3.md` | P3 |
| `NFL_P3_ADDENDUM_R1.md` | P3 R1 addendum |
| `SESSION_SUMMARY_2026-09-07.md` | this file |

Research code and every metric are under `nfl/research/p1/`, `p2/`, `p3/`,
including the three pre-declarations written before their results existed.

---

*No wager was recommended or discussed at any point. No parlay was discussed. No
DFS, ownership, lineup, market or fantasy-point work was done. 2026 outcomes were
not consumed and no frozen 2026 artifact was modified.*
