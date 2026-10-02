# Prospective ledger: what exists, why it is empty, and what unblocks the first admissible row

Audit of 2026-10-02, opened on the owner's instruction to build the grading ledger first. The
finding is that the ledger exists, has worked once, and is **correctly empty of admissible
prospective evidence** under today's contract. Nothing below was rebuilt; everything was read and
measured.

## 1. There are two ledgers, and they are different objects

| Ledger | Granularity | Writer | Contents today |
|---|---|---|---|
| `PROSPECTIVE_EVALUATION_LEDGER.jsonl` | one block per slate, two-phase (`AWAITING_OUTCOME` → `GRADED`) | `nfl/postgame/ledger.py` | 3 blocks: DET_BUF W2 registered and graded; **PIT_CLE W4 showdown registered tonight** |
| `PROSPECTIVE_LEDGER.jsonl` | one row per player-stat, with CRPS / PIT / coverage / bias | `nfl/research/postgame.py` (`--season`, `--blob`) | 3,230 rows, **2 games**, both week 1, one of them under five candidate labels |

The row ledger is the one the section-4 sample floors are counted in. The block ledger has no
candidate-identity control, which is why tonight could be registered there and not in the row one.

## 2. 133 sealed forecasts are discoverable; 0 are admissible

`sealed_index.discover_all()` finds 133 seals: week 1 — 121 live + 3 shadow + 6 product across 16
games; week 2 — 3 (DET_BUF); **week 3 — zero**; **week 4 — zero**. The three week-3 production runs
under `nfl/production/runs/` carry `SEAL.json` but no `player_draws_manifest.json` and live outside
every namespace, so week 3 was never sealed in a gradeable form. Tonight's showdown was not either.

Scoring against your weeks 1–3 play-by-play (isolated dry run, real ledger untouched):
17 completed games discovered, 133 seals found, finality passed on all, **0 scored, 133 deferred
`POSTGAME_ARTIFACT_NOT_CURRENTLY_ADMISSIBLE`**. The Sep 23 run had deferred them
`OUTCOME_NOT_YET_PUBLISHED`; your upload moved every seal past that gate to the next one.

## 3. The admissibility contract, and the three blockers refusing everything

`nfl/prospective/q9shadow/reuse.py` evaluates seven mandatory controls; `LEGACY_UNVERIFIED` does
not pass. Three refuse every seal on disk:

| Control | Why it refuses | Owner per ledger | Needs outside bytes |
|---|---|---|---|
| `completeness_evidence_class` | artifact `completeness != COMPLETE` (all are `PARTIAL_PLAYER_COVERAGE`) | production forecast path | no |
| `current_blocker_state` | three repository-wide blockers `BLOCKED` (below) | — | — |
| `prospective_evidence_eligibility` | every artifact carries `prospective_eligible: false` | — | — |

The three repository-wide blockers:

**`COMPLETE_ARTIFACT_LAYERS_ABSENT`.** The Q9 paired build produces the four *arm* layers (targets,
receptions, receiving yards, TD allocation) and is "demonstrable on the LIVE season"; the five
*shared* layers (team volume, three QB layers, carries) are **hard-coded**
`NOT_MODELED_IN_PAIRED_RESEARCH_SLICE` in `complete.py:295` with no hook to take them from a
production seal. The most complete production seal on disk (DET_BUF `R9_W1P_GA`, 54 verified
matrices) carries the verdict `PRODUCED:qb_layer | ABSENT: appearance, participation,
targets_carries, conversion, td_layer` — its non-QB chain never ran to credit.

**`INJURY_REPORT_INCOMPLETE`.** 692 rows, 518 without `report_status`. **This is a definition
defect, not a data gap** — see `nfl/tests/test_injury_blocker_semantics.py` (6 checks). All 518
carry a `practice_status`; none is blank on both. The evaluator (`live_features.py:454`) is a pure
blank count and refuses every week that has a designation-free practice row, which is every week.
It is structurally unclearable. Two facts are merged inside the 518: weeks 1–2 (267 blanks in
completed weeks = final "no designation") and week 3 (251 blank vs 8 filled = captured Sep 24,
before Friday designations existed). A corrected rule — unfilled only when *both* statuses are
blank, week incomplete by its own filled share — clears weeks 1–2 and still refuses week 3.
**Not applied: redefining a governance control changes what counts as evidence.**

**`G0A_11_OF_12`.** Remaining item: "kickoff-anchored vintage capture scheduled and demonstrably
running. Root cause EGRESS." This is your item 3, verbatim.

The ledger declares the three `independent_of` one another. In dependency terms they are not: the
production seal's `appearance` layer is refused `INJURY_REPORT_INCOMPLETE` on 12 of 13 week-1 games,
and every shared layer downstream of appearance is absent *because of it*. Completeness cannot be
reached while the injury blocker stands, and the injury blocker cannot clear as written.

## 4. A structural fact about the showdown line

`candidate_freeze_identity` recognises only the frozen Q9 target-allocation mechanism, by module
hash. The showdown pipeline (`proj_v1` + `nfl/sim/game.py` joint simulator) is a different model
family. It can never carry that identity honestly, so **under the current contract the showdown and
production lines cannot produce admissible prospective evidence however complete they become.**
Either the contract registers other model families as candidates, or those lines are graded
descriptively only. That is a what-counts-as-evidence decision.

## 5. What was done tonight

- Truthful provenance sidecar written for your uploaded play-by-play blob
  (`pbp_2026.79b02496d26004ee.csv.provenance.json`, byte-identical to the upload, retrieval method
  `OWNER_RELAYED_UPLOAD` stated rather than hidden). The scorer now accepts it.
- `PIT_CLE_2026W4_SHOWDOWN` registered `AWAITING_OUTCOME` in the block ledger, pinning both sealed
  versions (baseline-A 400 draws at `6e6c82dd`, corrected 2,000 draws at `b05e476a`, both
  committed before kickoff) so the starter-state repair is gradeable as a declared treatment on one
  game — descriptive, n=1.
- The injury-blocker characterisation tests above.

## 6. Decisions only you can make

1. **Injury blocker semantics** — adopt the both-blank rule (recommended; the tests show it is not
   a loosening), or keep the blank count and accept the blocker never clears.
2. **Candidate identity scope** — extend the control so model families other than frozen Q9 can be
   registered as candidates, or confine admissible evidence to the Q9 line.
3. **Market data** (unchanged from the earlier audit) — second arm, not a swap.

Items 1 and 2 are the gate on every future admissible row. Item 3 of your program (scheduled
acquisition) is the gate on G0A and on fresh injury captures, and it is where I go next.
