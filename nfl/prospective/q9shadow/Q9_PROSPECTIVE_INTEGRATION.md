# Q9 prospective shadow deployment — integration report

Written 2026-09-12. **Nothing is promoted. Zero live forecasts are sealed, and
the three reasons are named and measured below.**

| flag | value |
|---|---|
| `promoted` | **false** |
| `prospective_candidate` | **true** |
| `shadow_only` | **true** |

Candidate identity `6310f67ccb8b0edf`, matching the pre-season freeze on all
17 identity fields. Dry-run proof: **10 of 10 checks hold.** Suite: 207 checks
in the new module, 0 failing.

---

## 1. The headline, before the detail

The frozen Q9 target-hurdle candidate is integrated into the prospective
shadow-forecast path. The sealing path is complete, identity-gated,
deterministic, and provably unable to read an outcome. It has produced **no
live 2026 seal**, and that is not a defect in this work — three things stand
upstream of Q9, each named, each refused rather than routed around:

| blocker | whose | measured |
|---|---|---|
| `LIVE_PREGAME_FEATURE_BUILD_UNIMPLEMENTED` | this repository | `nfl/research/q6/frame.py:109` refuses any 2026 row by design (`Q9_LIVE_SEASON_IN_FRAME`); production reports `feature_build: STAGE_DECLARED_UNIMPLEMENTED`. All **270** REG games ahead of the clock refuse here |
| `INJURY_REPORT_INCOMPLETE` | the agent with network | **12 of the 13** week-1 games still ahead of kickoff on 2026-09-12 carry `NOT_APPLICABLE[INJURY_REPORT_INCOMPLETE]` at the appearance stage; the 13th (`2026_01_NYJ_TEN`) carries `NOT_APPLICABLE[NONQB_PLAYER_FRAME_INCOMPLETE]`. Requested in `docs/AGENT_OUTBOX.md` |
| `G0A_11_OF_12` | governance | `authorization.gate_state()` → `{'G0A': '11/12'}`; protocol §1 says no forecast written before G0A is discharged counts toward promotion |

The first is mine and is **assigned, not blocked** — it needs no bytes from
outside. The second needed bytes and is in the outbox. The third is an owner
matter.

Every count above is re-derivable:

```
python3.12 -m nfl.prospective.q9shadow.ledger --state
```

---

## 2. What the directive asked to be sealed, and where each item is

| directive item | where it lives in the sealed artifact |
|---|---|
| exact Q9 candidate hash | `candidate.identity_sha256`, and `spec_hash`, compared field by field against `Q9_PROSPECTIVE_FREEZE.json` before anything is written |
| all input hashes | `source_captures[]`, and the same partitions **inside** `ExecutionIdentity`, so the fingerprint moves when an input is swapped |
| feature-schema hash | `feature_set_hash` / `candidate.feature_schema_sha16` |
| coefficient hash | `candidate.coefficient_sha16` |
| upstream appearance artifact / hash | `candidate.appearance_artifact`, `candidate.appearance_spec_sha16` |
| team-budget artifact / hash | `candidate.budget_point_sha16`, `candidate.budget_residual_pool_sha16`, `candidate.budget_estimator` |
| RNG seed / draw count | `seed_protocol` |
| forecast `written_at` | `written_at` |
| kickoff | `kickoff_utc` |
| cutoff basis | `cutoff.cutoff_basis` (+ `cutoff_basis_note`, `newest_input_observed_at`) |
| fallback counters | `fallback_counters`, both named Q9 fallbacks **and** the baseline's own degenerate case |
| production interface version | `candidate.production_interface_sha16` |

`retrieved_at <= written_at < kickoff` is enforced **twice**, by two modules
written for different reasons and neither written for this task:
`nfl/identity/seal.py::seal_forecast` against the execution identity's
partitions, and `nfl/prospective/artifact.py::validate` against the artifact's
own source captures. Nothing is reimplemented.

No post-kickoff mutation is possible: `append_seal` refuses a second seal of
one `forecast_id` with different content (`SEAL_IMMUTABLE_VIOLATION`), and
`artifact.assert_not_mutated` refuses an in-place edit (`ARTIFACT_MUTATED`).
The only lawful correction is a new artifact naming `supersedes`.

---

## 3. The frozen prohibitions, made structural

The directive forbids refitting coefficients, changing features, altering the
one-target floor, altering fallback logic, altering thresholds, and tuning on
any 2026 result — "any such change creates a new candidate and requires a new
freeze."

That is a sentence. `candidate.assert_identical_to_freeze` is a gate: it
compares 17 declared identity fields against the pre-season freeze and refuses
with the differing fields **named**. The test module mutates each of
`coefficient_sha16`, `feature_schema_sha16`, `one_target_floor`,
`named_fallbacks` and `share_shrinkage_k` in turn and asserts each refuses.
Dropping a module the freeze recorded also refuses.

Two deliberate non-inclusions, each with a reason:

- **The seed and draw count are not part of the mechanism identity.** A seed
  is an execution parameter. Two runs at different seeds are the same
  candidate, and reusing the Q9B research seed would make the prospective
  draws a replay of the development result rather than an independent sample
  from the same frozen mechanism. The prospective seed is `20260912`,
  `N_DRAWS = 1000`, declared in one place.
- **The module hash set is a required subset, not an exact match.** The freeze
  hashed four modules; the live identity hashes seven, adding `q6.frame`,
  `q6.forward_chain` and `q8.audit` — the modules that build the features and
  the team budget, which are part of the execution path whether or not the
  freeze wrote them down. Every module the freeze recorded must be present and
  unchanged; additions strengthen an identity and cannot weaken one.

---

## 4. The side-by-side, and one deliberate difference from Q9B

Both arms consume **one** set of upstream draws:

| shared | per-arm |
|---|---|
| appearance draws, through the real `layers.appearance` interface | the allocation stream, keyed by arm name through **crc32** |
| the team budget vector | |
| the draw index — column *j* is one iteration in both arms | |
| the player frame and its order | |
| the input capture bundle and its hashes | |

Q9B seeded each arm's stream with the arm name, so the two arms drew
**different** appearance matrices and **different** budgets. That is
defensible for a four-season average and indefensible for a prospective test
on a handful of games: at that size the arms would differ by their upstream
noise as much as by their mechanism. The shared-upstream policy is a property
of the comparison harness, not of the candidate — features, coefficients, the
floor, the fallbacks and the thresholds are read from the frozen module and
hash-checked.

`crc32`, not `hash()`. Python randomises `str` hashing per process; the test
module runs `_stream_parts` under three `PYTHONHASHSEED` values in subprocesses
and asserts one answer.

Verified on the 2024 slice, per team-game: both arms reconcile to the drawn
budget exactly on every draw; both sit on one draw index; both allocate the
same budget vector; the two arms differ (the mechanism does something); and a
player who did not appear in draw *j* receives nothing in draw *j*.

---

## 5. Three guards against reading an outcome, because they fail differently

1. **No outcome reader in the sealing path's namespace.**
   `assert_no_outcome_reader_imported` refuses if any of six named readers is
   bound in `seal`, `shadow`, `inputs` or `candidate`. The check is shown
   non-vacuous by pointing it at `postgame` itself, which it refuses.
2. **An outcome-shaped input is refused by name.** A play-by-play source or a
   realised key (`actual_`, `final_score`, `home_score`, `postgame`, …) fails
   the bundle with `Q9_SHADOW_OUTCOME_SHAPED_INPUT`.
3. **The feature row is projected.** The historical panel row necessarily
   carries `targets` — that is what a panel is for. The frozen featuriser is
   handed a dictionary of exactly the **ten** keys it reads, and that key set
   is *derived from the featuriser's own source*, not typed out. A realised
   column cannot reach the model because it is not in the dictionary.

Plus the schedule: the capture carries `home_score`, `away_score`, `result`,
`total`, `overtime`, `spread_line`, `total_line` and both moneylines in the
same row as `gameday`. Only 12 named pregame columns are lifted out. The proof
asserts the raw capture carries **9** banned columns and the projection
carries **0** — the first number is what stops the second from being vacuous.

### The substring trap, hit again by the person who wrote the warning

The first draft of the outcome-source guard contained `'weekly'` matched with
`in`, and refused the entire input bundle on `weekly_rosters` — a roster feed,
not a result. Same defect as Track 1's market guard matching `yardline_100` on
`_line`, three tasks later. Sources are now matched **exactly**, against a
`frozenset`, and the test asserts `weekly_rosters` is not refused.

`weekly_rosters` is instead `RESTRICTED`: `status == INA` is game-day
information that Q9 names in `FORBIDDEN_INPUTS`, yet the R8 appearance pool
legitimately reads the same file for its ACT filter. Refusing the bundle would
refuse the production arm too. The control is guard 3 — none of the ten
feature keys is sourced from that file — and the restriction is recorded on
every passing bundle rather than left implicit.

---

## 6. The ledger: four counts, never one

`Q9_PROSPECTIVE_LEDGER_SCHEMA.json` — **33 row fields**, each justified in the
schema by what breaks without it. Row identity: candidate, arm, forecast_id,
artifact_id, game_id, team, entity, player_id, position, metric, cutoff_utc,
cutoff_basis, written_at, kickoff_utc, outcome_hash, outcome_source,
finality_code.

Counting is delegated to `postgame.accounting`, not recomputed:

| unit | what it means |
|---|---|
| ROW | one metric × one sealed forecast × one outcome version. **Never a sample size** |
| PLAYER_GAME | one player in one game. Not independent across teammates |
| TEAM_GAME | one team in one game — the unit a target budget is allocated within |
| GAME | the independent unit, and the floor unit |

Four rows from two arms × two players of one game count as 4 ROWS, 2
PLAYER_GAMES, 1 TEAM_GAME, 1 GAME. **A paired second arm adds no
player-game.** `TEAM_GAME` was added to the governed `EVIDENCE_UNITS` for this
work; it did not exist before.

**Finality gates scoring.** `postgame.game_finality` proves completion from
the authoritative bytes; a game that cannot prove it produces zero rows under
`POSTGAME_NOT_FINAL`. An outcome revision is a **new** row; the older one
stops being current without being deleted, and carries
`superseded_by_outcome_hash`.

**Metrics.** Primary: zero-target Brier, zero-target log loss (clip `1e-6`,
declared), zero-mass calibration gap, marginal target CRPS, positive-target
CRPS. Diagnostic only: randomized PIT, mid-PIT, and downstream receiving-yard
CRPS — the last is preserved for diagnosis and is **never** a promotion
criterion, as Q9 already declared.

**Uncertainty.** Paired block bootstrap over whole `game_id` and whole
`game_id|team` clusters, 1,000 resamples, seed `20260913`. Naive intervals are
forbidden by protocol §6 and the schema says so.

**Absence is not a zero.** A player missing from the outcome produces no row;
a player present with a null target count produces no row. That substitution
turned a 74-yard game into a scored zero once already.

---

## 7. The stop rule, and the branch that applies

The directive: *"If the repo already contains a governed
prospective-evidence threshold, use it. If not, explicitly report
PROSPECTIVE_SAMPLE_NOT_YET_GOVERNED rather than improvising one."*

**It does.** `nfl/prospective/PROSPECTIVE_EVALUATION_PROTOCOL.md` §4, written
2026-09-08 before any eligible 2026 result existed:

| purpose | floor |
|---|---|
| any reported metric | ≥ 200 eligible player-game forecasts |
| any benchmark comparison | ≥ 400 forecasts **and** ≥ 8 eligible weeks |
| any promotion decision | ≥ 800 forecasts **and** ≥ 12 eligible weeks |
| any position-stratified claim | ≥ 200 within that position |

Transcribed into `ledger.FLOORS` and asserted against the protocol text by the
test module. **`PROSPECTIVE_SAMPLE_NOT_YET_GOVERNED` is not the applicable
state and is not reported.** No numeric minimum was invented.

Current state: **0 forecasts, 0 weeks — `UNDERPOWERED` on all four floors.**
Below a floor a comparison is not a small result; it is not a result.

---

## 8. Two defects this work found, both in code that already existed

### 8.1 The sealed `forecast_id` depended on the output directory

The first version hashed the whole artifact dict, which carries
`draw_artifact` — the path the draws were written to. Two seals of
byte-identical inputs into two different directories produced two different
`forecast_id`s. **The dry-run proof caught it as a determinism failure**,
which is what the proof is for.

It was not the forecast that differed; it was the output location, a property
of the machine that ran the seal. Same lesson as `sealed_index._rel`. The
sealed body now excludes `draw_artifact` and `draw_artifact_sha256`, and
carries `draw_content_sha256` — a hash of the draw **values** — instead. Both
file-level and content-level hashes are kept in the written artifact, because
they answer different questions.

*Measured aside:* `np.savez_compressed` was checked for wall-clock dependence
across 3-second gaps and is byte-stable. The content hash is carried anyway,
so the determinism claim does not depend on a container format.

### 8.2 `VERSION_IDENTITY` was missing `arm`, and would have discarded one arm of every pair

`postgame.VERSION_IDENTITY` was `(forecast_id, game_id, entity, metric,
player_id, team)`. This harness seals **both** arms inside one forecast
artifact, so both arms shared all six fields — and `versioned` read the second
arm as a **revision** of the first and marked it `SUPERSEDED`. Of four rows
(two arms × two outcome versions) only **one** came back CURRENT. The scoring
machinery would have silently discarded one arm of every paired comparison.

It never surfaced before because each candidate variant had its own
`forecast_id`. `arm` is now part of the identity. A row with no `arm` key
resolves to the empty string exactly as before, so every ledger row already on
disk keeps the identity it had — asserted by a new check in
`test_postgame_guards.py`, alongside checks that two arms are not revisions of
each other and that a restated outcome for **one** arm still supersedes.

### 8.3 The kickoff clock was approximated, and would have been an hour wrong on a game day

The first version derived `kickoff_utc` from nflverse's US/Eastern `gametime`
using a hand-rolled DST range (14 March to 1 November). US DST actually ends on
the **first Sunday in November** — which in 2026 is 1 November, a Sunday with a
full slate. Sunday-afternoon kickoffs that day are EST (+5), and the range gave
+4.

An hour of slack on `kickoff_utc` is an hour in which a forecast written
**after** kickoff would pass `written_at < kickoff` — the one clock this whole
package rests on. It now uses `zoneinfo.ZoneInfo('America/New_York')`, and the
derived kickoff is **validated against every production-sealed record**: 14
game ids compared, 0 mismatches. Offsets across the 2026 regular season split
108 at +4 and 164 at +5.

### 8.4 Two smaller repairs

`artifact.assert_hard_invariants` now reports `hard_not_applicable` and
`hard_evaluated_and_held` separately. Without it an artifact could mark every
hard invariant `NOT_APPLICABLE` and its verdict would read exactly like a clean
run.

`postgame.EVIDENCE_UNITS` gained `distinct_team_games`, which the directive's
four required counts need and which did not exist.

---

## 9. The dry-run proof

`Q9_PROSPECTIVE_DRYRUN_PROOF.json` — 10 checks, 10 hold. Run on a frozen 2024
slice, 1 game, 120 draws, under `dryrun/` and **never** under `sealed/`, with
a labelled synthetic kickoff.

| check | what it shows |
|---|---|
| `DETERMINISTIC` | two seals of identical inputs agree on `artifact_id`, `spec_hash`, `draw_artifact_sha256`, `draw_content_sha256`, `feature_set_hash`, `forecast_id`, the seal payload hash and the identity fingerprint |
| `OUTCOME_READERS_POISONED` | all **6** named outcome readers replaced by functions that raise; the seal completes without touching one |
| `OUTCOME_SHAPED_INPUT_REFUSED` | a pbp source and a realised key each refused; a bundle with only a RESTRICTED source passes and records the restriction |
| `SCHEDULE_PROJECTED` | 9 banned columns in the raw capture, 0 in the projection |
| `FEATURE_PROJECTED` | 6 realised columns on the panel row, 0 in the projected row |
| `NO_READER_IN_NAMESPACE` | no sealing module can reach an outcome reader at all |
| `MUTATION_REFUSED` | in-place edit refused; a correction naming `supersedes` accepted |
| `RESEAL_REFUSED` | identical re-record says so; different content under one `forecast_id` refused |
| `POST_KICKOFF_REFUSED` | `written_at == kickoff` refused; an input retrieved after `written_at` refused |
| `DRY_RUN_NOT_EVIDENCE` | the ledger refuses a dry-run row as evidence |

**A dry run is not evidence, and the label is load-bearing.** It writes under
`dryrun/`, appends to its own seal ledger, stamps `dry_run: true` and
`prospective_evidence: false`, and its candidate identity is explicitly **not**
compared to the 2026 freeze — a dry run at season *Y* fits on seasons `< Y` and
therefore holds different coefficients by construction. Asserting parity would
be false; skipping the comparison silently would be worse, so it is recorded as
`NOT_APPLICABLE[Q9_DRY_RUN_IDENTITY_NOT_COMPARED_TO_FREEZE]`.

`ledger.accounting` reads those two flags: dry-run rows are stored, counted in
`scoring_rows_including_non_evidence`, excluded from every evidence unit, and
the exclusion itself is counted.

---

## 10. Three governance items. One is resolved by construction; two are not mine

### 10.1 §9.6 randomized PIT vs Q9B's mid-PIT — resolved by construction

Protocol §9.6 requires that **randomized** PIT be *not worse*. Q9B measured
**mid**-PIT (χ² 8,821 → 8,913, worse). Those are different statistics, so §9.6
was **not evaluable** on the development evidence. The ledger emits the
randomized version — seeded per row through crc32 so it reproduces exactly —
and records mid-PIT beside it so the two are never confused again. §9.6 becomes
evaluable the moment rows exist.

### 10.2 §2 `completeness == COMPLETE` vs a single-layer artifact — needs an owner ruling

§2 defines an *eligible forecast* as one with `completeness == COMPLETE`. A Q9
shadow artifact forecasts RB/WR/TE receiving targets for one team-game and
nothing else, so the truthful label is `PARTIAL_PLAYER_COVERAGE` — which §2
also defines, as "scored only over the players it actually covers, and the
shortfall reported alongside every metric."

The two clauses are in tension for a single-layer artifact. The label is set
truthfully and the consequence — that these artifacts are **scored but are not
"eligible forecasts" in §2's sense** — is recorded in the artifact, in the
ledger schema, and here. **Loosening a gate to admit one's own candidate is the
one move this project never makes.** This changes what counts as evidence, so
it is an owner ruling.

### 10.3 G0A 11/12

Protocol §1: no forecast written before G0A is discharged counts toward
promotion. Item 1 remains not cleared
(`NFL_G0A_ADJUDICATION_2026-09-10.md`). Recorded, not worked around.

---

## 11. What is not claimed

- **No accuracy claim.** No 2026 outcome has been read by anything in this
  package. The dry-run proof is about the code path and says so in its own
  artifact (`is_evidence_about_accuracy: false`).
- **No promotion, and no path to one from here.** Promotion needs every §9
  condition including an explicit owner decision, which no code path can
  produce.
- **No comparison result.** The comparison machinery runs and reports
  `COMPARISON_UNDERPOWERED`; on 0 rows there is nothing to report.
- **No claim that Q9 is better.** Q9B's development finding stands as it was,
  on mined seasons, labelled exploratory.
- **The arms are never pooled**, and `artifact.assert_arms_not_pooled` exists
  for the A/B/C arm classes as before. This candidate is registered arm **B**:
  its stage-1 coefficients are fitted on seasons strictly earlier than the
  forecast season by a rule frozen in advance. It is deliberately **not** arm
  A, which consumes no 2026 outcome all season.

---

## 12. How to run it

```
python3.12 -m nfl.prospective.q9shadow.candidate          # identity + freeze gate
python3.12 -m nfl.prospective.q9shadow.inputs             # bundle + guards
python3.12 -m nfl.prospective.q9shadow.shadow  --season 2024 --games 4
python3.12 -m nfl.prospective.q9shadow.seal    --season 2026            # live: refuses, by name
python3.12 -m nfl.prospective.q9shadow.seal    --season 2024 --dry-run  # the dry-run path
python3.12 -m nfl.prospective.q9shadow.dryrun                            # the 10-check proof
python3.12 -m nfl.prospective.q9shadow.ledger  --schema --state --report
python3.12 nfl/tests/test_q9_prospective_shadow.py
```

When the injury bytes land and the pregame feature builder exists, the live
path runs with **no change to this package** — `--season 2026` stops refusing
and starts sealing.

## 13. Files

| file | what |
|---|---|
| `nfl/prospective/registries.py` | Q9 registered; two new refusals for an incoherent shadow status |
| `nfl/prospective/q9shadow/candidate.py` | the identity and the freeze gate |
| `nfl/prospective/q9shadow/inputs.py` | the bundle, the three guards, the derived feature projection |
| `nfl/prospective/q9shadow/shadow.py` | the side-by-side on shared upstream draws |
| `nfl/prospective/q9shadow/seal.py` | eligibility, the schedule projection, the seal |
| `nfl/prospective/q9shadow/ledger.py` | schema, four-unit accounting, floors, metrics, state |
| `nfl/prospective/q9shadow/dryrun.py` | the 10-check proof |
| `nfl/research/postgame.py` | `arm` added to `VERSION_IDENTITY`; `distinct_team_games` added |
| `nfl/prospective/artifact.py` | `NOT_APPLICABLE` hard invariants reported rather than silently passing |
| `nfl/tests/test_q9_prospective_shadow.py` | 207 checks |
| `nfl/tests/test_postgame_guards.py` | +3 checks for the `arm` identity repair |
| `docs/AGENT_OUTBOX.md` | the one request that needs bytes from outside |
