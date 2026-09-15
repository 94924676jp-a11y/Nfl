# V2 refinement — morning report

Covering the overnight directive. Branch
`claude/nfl-greenfield-architecture-stsxmk`, HEAD `787e3e4`, twelve commits.

**Suite at close: 129 modules, 1,581 test functions, 8,779 checks, 30 failing,
6 declared blocked. Every one of the 30 is a deliberate reproduction or a
declared escalation, listed in §5. None is an unexplained regression.**

**Every seal intact.** `board_pointer.verify_seal(V1_SEALED)` → `PASS
SEAL_INTACT` at every checkpoint. `layers.py` `481f005f682cd721` unchanged.
Nothing was written into `nfl/research/live/`.

---

## 0. The honest headline

**Nothing here earns the word "better".** Four new candidate identities exist
and not one is promoted. Of the two that were scored out of time, one improves
its own layer and does not improve the published quantity, and the other
improves the published quantity while exposing a larger error underneath it.
The night's actual product is **structural correctness plus a much better
account of what this system does not know** — which is what the directive asked
for, and is worth more than a candidate that looks good on development data.

The single most valuable finding is a **confirmed leak** that had been live and
invisible on every production run.

---

## 1. Every defect inspected

| # | defect | reproduced? | root cause | repair | candidate |
|---|---|---|---|---|---|
| 1 | Depth-chart chronology guard never executed | YES | `run_forecast:501` passed neither `kickoff_utc` nor `written_at`; both default `None`, so `if bound` was false on every run | armed at both call sites | — |
| 2 | Depth chart selected by content-hash order | YES | `sorted(glob())[-1]` on hash-named files, called "newest" | clocked selector, refuses `DEPTH_CHART_NO_LAWFUL_VINTAGE` | — |
| 3 | `f_weeks_since_appear` no missingness flag | YES | value-only encoding; `None` and 9+ both → 1.0000 | `featurise_r10`, value + flag, monotone | **R10** |
| 4 | Depth rank train/serve scale break | YES | `weekly` groups within position, `daily` ranks offence-wide | `scale=` parameter, unknown scale refuses | **R10** |
| 5 | QB dropback share miscalibrated | YES | share pool includes backup QB-games; conditioning on primary selects its top | both mixture components on one conditioning basis | **R12** |
| 6 | QB rush composition over-allocates | YES | three causes, all at the call site, none in A1's estimator | `compose_rush_ownership` | **R11** |
| 7 | Passing-yard tails impossible | YES | `PY = CMP × ypc_d` — scale non-exchangeability | resample completions, not games | **R13** |
| 8 | Old passing-credit function | YES | completions split on ATTEMPT share, yards independent of the completion draw | 42 of 50 boards migrated; 8 unmigratable, named | — |
| 9 | Corpus fences scanned 104 of 121 | YES | glob hard-codes three path levels | shared content discovery | — |
| 10 | Conservation declined 5 boards | YES | literal `player_draws.npz` presence check | either encoding accepted | — |
| 11 | Board readers scanned 104 of 121 | YES | `cfg.glob('*/board.json')`, one level | `sealed_board_dirs`, imported not copied | — |
| 12 | Q7 scrambles structurally zero | YES | counted against `passer_player_id`, which a scramble lacks | charged to `rusher_player_id` | — |
| 13 | `recon_error` a tautology | YES | `abs(multinomial(n,p).sum() − n)` is identically 0 | **OPEN** | — |
| 14 | Published team-target ≠ partitioned | YES | D1's continuous draw sealed under a count's name | **OPEN** (R14 reserved) | — |
| 15 | Masquerade guard skipped R9/R10/R11 | YES | hand-written mode list | `CANDIDATE_MODES` derived from `MODES` | — |
| 16 | Staging leak, 617 dirs / 20 GB | YES | `mkdtemp` per process, never removed | content-addressed by manifest digest | — |
| 17 | `track1` scrambles zero in 4,023/4,024 | YES | third instance of #12 | **OPEN** | — |
| 18 | `h1_frame` reads superseded panel | YES | supersession listed artifacts, not code | **OPEN** | — |
| 19 | Grep invariants penalising documentation | YES ×2 | text search over source; comments trip them | parse the AST | — |
| 20 | Windowed assertions, polarity | YES ×2 | fixed-width slice; a NEGATIVE one passes when the file grows | slice to the function | — |

**Not reproduced / withdrawn:** the rush category partition "non-closure"
(8.4278 / 10.2027) — my comparison omitted scrambles and skipped integerising;
it closes at **0.000000**. The `stored_team_targets` check — correctly
specified for what it measures, wrongly read by me as a closure failure. The
"DEN@KC backfield coin flip" — no tie exists; the carry prior separated the
backs 1.62 : 1 and the appearance layer inverted it.

## 2. Historical before/after, and calibration

**R10 appearance**, forward-chained 2022–2025, 40,579 rows:
Brier .08931 → .08880, log loss .28731 → .28597, ECE .01699 → .01555, paired
−0.000512 [−0.000718, −0.000317] team-week-blocked. Concentrated in 2025, the
only daily-vendor season; 2025 week-1 Brier .0770 → .0646.
**Counterweight: 2025 ECE WORSENS .02047 → .02519.** No equivalence margin was
predeclared, so no adequacy claim is made.

**R12 QB share**, 540 forward-chained 2025 starting-QB games:
randomized PIT χ²(9) 32.481 → **8.667** (p = 0.469), signed bias −0.0778 →
−0.0190, end-to-end passing-yard CRPS 43.042 → **41.744**, paired
**−1.298 [−2.198, −0.436]**. Both sides of the two-sided bar clear.
**And the cost: passing-yard bias moves from −5.922 (contains zero) to +7.538
(does not).** The `V` draw is bit-identical between arms. The incumbent's
apparent accuracy was two errors cancelling — a share ~2.8 dropbacks too low
against a team layer ~1.6 too high. **`team_volume_v1`'s +1.6369 drift is now
the binding error on QB passing volume.**

**R13 passing-yard tails**, 635 forward-chained 2025 QB-games:
max 2,898 → **772**, min −238 → **−3**, rate above the 554-yard record
5.260e-03 → **5.102e-04** (inside the derived bound 7.907e-04), D19's exact
state 938 cells → **0**, out-of-support 13,803 → 112.
**CRPS 48.855 → 49.103, paired +0.248 [−0.074, +0.524] — the interval contains
zero.** This cohort does not establish that either arm forecasts better, and
R13 is not offered as one that does. The 1–4 completion band gets worse.

**R11 rush composition**: over-allocation 149 → **0** (DEN) and 148 → **0**
(KC), max excess +6.12 and +9.69 → **0.0000**. Gate FIRED → PASS both clubs.

**All four are EXPLORATORY.** 2025 is development data in this project;
forward chaining controls parameter leakage, not specification leakage. A
confirmatory result needs untouched games.

## 3. Candidate identities created

| id | repair | inherits | promoted |
|---|---|---|---|
| `V1_CANDIDATE_R10` | appearance encoding + within-position rank | R9 | NO |
| `V1_CANDIDATE_R11` | single-owner rush composition | R9 | NO |
| `V1_CANDIDATE_R12` | QB dropback-share conditioning | R9 | NO |
| `V1_CANDIDATE_R13` | completion-block passing yards | R9 | NO |
| `V1_CANDIDATE_R14` | reserved, target published level | R9 | not registered |

None inherits another: stacking unvalidated mechanisms makes pairwise
differences unattributable. R8 and R9 were never edited. `CANDIDATE_MODES` is
now derived, so a new mode cannot escape the masquerade guard by omission.

## 4. Invalidated

- **Q7's two published numbers** — the COMPOSED decomposition and the
  cold-start table — need re-issuing in `Q7_DECISION.md`. Every Q7
  **conclusion** survives: 588 of 1,003 quantities move, **0 of 60 significance
  flags and 0 of 4 verdicts**.
- **`recon_error = 0.0` on 385,446 rows** measured nothing and must not be
  cited as reconciliation evidence.
- **`D7_ROWS_ALL_SEALS_2026W1.csv`** was built from 104 of 121 boards.
- **Three figures I published**: PIT χ² 929.0 and "79% above P90" (instrument
  artifacts on an atom — 78.89% of shares are exactly 1.0; real figure 32.481);
  27,564 impossible cells (reproduces from no corpus; 36,587 / 27,301 / 9,286
  by scope).
- **The frozen Wave-0 baseline comparison** is recorded
  `WAVE0_BASELINE_CORPUS_NOT_RECONSTRUCTIBLE`: it declares 101 runs but no
  membership list, and was taken when a different board set existed.

## 5. The 30 failing checks, all deliberate

| module | n | why |
|---|--:|---|
| `test_p6_false_greens` | 19 | one reproduction per ACTIVE false green; they pass when the defect is repaired, never by weakening |
| `test_q9_live_feature_builder` | 5 | Q9 frozen candidate no longer the candidate that was frozen — owner ruling |
| `test_passer_credit_migration` | 3 | declared residuals on 8 unmigratable boards + the QB-only upper tail |
| `test_c1_denominator` | 1 | same Q9 escalation |
| `test_p7_data_plane` | 1 | `coaches()` reads an orphan blob with no manifest row |
| `test_stat_contract` | 1 | non-integer carries on boards predating the counts repair |

## 6. Unresolved information gaps

| gap | outbox |
|---|---|
| DEN@KC realized outcome — capture predates kickoff, zero DEN/KC rows | OUT-014 |
| Official inactives, all of week 1 — proxy 403; window closed unfilled, recorded MISSED (15 covered / 48 missed), never backfilled | OUT-013 |
| Preseason / coaching-usage signal — no such source family captured | OUT-015 |
| `official_transactions` — 177 consecutive BLOCKED, never captured once | standing |

## 7. Owner decisions needed

1. **Q9 re-freeze.** R3's `depth_vintage` repair moved three fitted blocks
   inside the Q9 import closure. Six checks fail on purpose. Re-sealing to
   match the tree would be rewriting evidence.
2. **Promotion order for four candidates**, or whether any is promoted. Each
   forfeits a frozen coefficient vector. R12 improves the published quantity
   and exposes a team-layer error; R13 improves structure and not score.
3. **48 orphan schedule blobs** with no manifest row — unattributable to any
   cut. Delete, or attribute retroactively with a declared basis?
4. **`REPLAY_C1`** excluded from corpus fences by name. Confirm intended.
5. **Eight unmigratable boards** — leave marked, or rebuild from source?

## 8. V2 architecture after the night

**Data plane.** 12 declared sources; `vintage_selector.FAMILIES` enforces a
clock for 4, the depth chart is now a 5th, and the remaining 7 are reached by
globbing — which is why every leak finding is glob-shaped. Bitemporal
assertions and a freshness monitor exist and are tested; the dependency DAG is
**specified, not built**.

**Discovery.** One content-based entry point (`sealed_index.live_draw_files`),
109 boards under `live/` excluding `REPLAY_C1` by name. Three fences, three
board readers and conservation now share it.

**Generation.** Causal chain unchanged and still has duplicate owners in
places; R11 removed one (designed QB runs). `compose_pass_event_ownership`
exists and is **verified inert** — rebuilding tonight's board gives a
byte-identical `draw_content_digest` — but nothing consumes its vectors yet.

**Governance.** Four new candidates, none promoted, none inheriting another.
The masquerade guard is derived rather than typed. An invariant-execution
manifest exists with a `NOT_CERTIFIED` verdict distinct from pass and fail:
first run found 57 declared-but-unevaluated check sites and **377 of 823 named
refusal codes never constructed by any test**.

**Product.** The board is `PRELIMINARY_PROVISIONAL` and `WITHHELD`. `FINAL` is
unreachable without an authoritative inactive list. K and DST surfaces do not
exist.

## 9. Next ten, by value

1. **`recon_error` tautology** — still published as 0.0 on 385,446 rows.
2. **R14 target published level** — 926/1000 KC draws exceed the sealed figure;
   three of four identity vectors sealed nowhere. Wiring is specified.
3. **`team_volume_v1` drift** — now the binding error on QB passing volume,
   exposed by R12 and previously masked by it.
4. **`track1` scrambles** — third instance of the Q7 defect.
5. **Wire R10 to a board** — registered, callable, unreachable.
6. **The 377 unconstructed refusal codes** — 46% of named refusals never
   exercised.
7. **Eight unmigratable boards** — need an SC1-style coupling.
8. **Tier-0 game-day board validation** — fast enough to run before kickoff.
9. **Phase 7 K and DST surfaces**, unsupported outputs null with a reason.
10. **A confirmatory frame** — every result above is exploratory, and nothing
    can be promoted until untouched games exist to test on.

## 10. Process, including my own failures

Fourteen agents ran. **Ten corrected me on something material**, and I verified
every load-bearing claim before relaying it — which is how three of my own
published figures were withdrawn.

My own errors this night: `git add -A` swept an agent's in-progress files into
a commit; **three separate briefs contradicted themselves** (register a
candidate in a file the same brief forbade editing) and three agents caught it
rather than guessing; I wrote a string-comparison bug into a fix and then
copied it into that fix's own test, where it reported 0 lawful vintages of 7
when there were 5; I placed a `resolve()` branch after the function's terminal
return, where it parsed and imported fine as dead code; and a test I wrote
carried the exact brittle-window defect I had sent an agent hunting.

The recurring lesson, paid for three times: **when a fence is repaired, the
readers behind it are not.** Fixing three corpus globs did not fix
conservation's presence check, and fixing that did not fix three board readers.

**No market data entered any part of this work. Nothing here is a wager.**

---

# ADDENDUM — 2026-09-15 afternoon

Written at HEAD `af72f67`. The morning report above stands; this records what
changed after it.

## The day's defects, and they share one shape

| | what | state |
|---|---|---|
| **D20** | `nfl.com/inactives/` served an empty page for nine days; 374 captures passed; 15 of Week 1's 63 coverage targets were credited to it | **repaired** |
| **D21** | the reconciliation statistic restates numpy's contract — 385,446 rows of zero, one of them feeding a boolean named `exact` | statistic built, **not wired** |
| **D22** | the json and csv guards count the envelope; ESPN's document scores 35 against 800 real entries and still scores 35 when emptied | **repaired** |
| **D23** | a `written_at` cutoff does not pin an input set when the manifest is append-only | **diagnosed, not repaired** |
| **D24** | the persisted-digest guard is on the branch that does not capture | **diagnosed, not repaired** |

**Four of the five are the same failure.** Not "a check was missing" — a check
existed, was well-reasoned, and was answering a different question than the one
its result was read as answering. D20's marker count answered *does the word
appear*. D21's statistic answered *does numpy conserve*. D22's row count answered
*did bytes arrive*. D24's guard answered *does this branch refuse bad rows*. Each
was correct. Each was read as evidence about football, or about production, or
about the corpus.

## And the distance problem, three times in one day

- D20's fact was **known on 2026-09-10**, written into one game's provenance
  block in a field called `what_this_is_not`, and never reached the registry,
  the capture guard or the coverage reader.
- "main stopped capturing on 09-11" came from a **stale tracking ref** rather
  than from main, and was load-bearing in `OUT-011` and seven test assertions
  for four days.
- D24's repair protects nothing in production while a test asserts it holds.

The defect was not in the analysis. It was in the distance between where a thing
was established and where it was needed.

## Five claims of mine that were wrong, in order

1. "The DEN@KC window closed with zero attempts." Eight lawful attempts.
2. "main carries in-window PASS captures, so the window was filled." They are
   empty — **and I committed this one** before decompressing a blob.
3. "The blast radius is 37 captures." It is 374 over nine days.
4. "No positive control exists, so the D22 repair is blocked." The injury report
   is 374 of them, on the same code path.
5. "No miss holds uncredited bytes" — written into a test as `== 0`. That `0`
   was **produced by a defect of my own**: my first cut suppressed the 18
   delivered markdown captures, the only genuine inactive lists in the store. A
   repair aimed at evidence quality was deleting the evidence, and it looked
   like a cleaner number.

Plus one inside a test: the first cut of D23's section C grepped for a field
name and counted a **constructor argument** as a consumer, reporting the defect
repaired — a textual false green inside the test written to catch textual false
greens.

## What the model work found

**Team volume is biased, and it is a lag.** Snaps `+0.996 ± 0.266` and dropbacks
`+0.605 ± 0.296`, team-season blocked, both CIs excluding zero, both feeding
passing. Monotone by season — dropbacks `−0.157 → +0.856 → +1.115`, *crossing
zero*. Confirmed against the panel: the league mean of actuals falls 2.91 and
2.65 since 2020, while the two metrics with flat league means carry **no bias at
all**. No estimator in the family has a trend term.

**The repair is not recommended.** The bias is a tenth of the MAE. Removing it
buys calibration and nothing for discrimination, which is the objective. `r` is
0.129, slope 0.423, sd ratio 0.304 — the model still emits far too little
game-to-game variation, and that is the actual problem.

**An open contradiction:** the autopsy has 2025 dropbacks *under*-projected by
−1.3697; this has them *over*-projected by +1.115. Different layers. Until that
is decomposed, "team volume is biased" must name the layer.

## Not done

QB cold-start ownership, R14 pass-event single ownership, R10 to a board, track1
scramble repair, h1_frame, Tier-0 validation, the data-plane DAG, the stacked V2
challenger, and the D21 successor candidate itself.

**Nothing promoted. R10 through R13 have zero boards between them.**
