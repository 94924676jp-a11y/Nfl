# The player-review gate as an enforced production dependency

Follows `PLAYER_REVIEW_STAGE.md`, which built the review. This document
records making it **stop** something.

Candidate identity unchanged: `CANDIDATE_NOT_ACCEPTED_BASELINE`. No model
value was changed. No NYG@LAR result was used anywhere.

---

## 1. Gate policy

```
raw evidence -> player universe -> role/participation/opportunity
   -> projection generation -> player dossier -> projection audit
   -> PLAYER-REVIEW GATE -> simulation publication -> optimizer
```

Three verdicts and no fourth:

| Verdict | Meaning |
|---|---|
| `PASS` | reviewed, nothing material contradicts the numbers |
| `PASS_WITH_WARNINGS` | reviewed, annotations recorded, publication continues |
| `BLOCKED` | a material contradiction; publication and optimization stop |

Two states are **refusals to issue a verdict**, not verdicts, and they are
returned under their own names rather than collapsed into `BLOCKED`:

- `PLAYER_REVIEW_NOT_RUN` — no review artifact for this slate.
- `PLAYER_REVIEW_STALE` — the review audited a different draw artifact than
  the one being consumed, proven by sha256 of the npz.

Both still report `verdict: BLOCKED` so nothing downstream proceeds. The
distinction matters because "the review blocked it" sends a reader hunting for
a conflict, and "the review cannot speak about this" sends them to re-run the
review. An earlier version of the loader collapsed them and was wrong.

### Enforcement is structural, not polite

A gate consumers *may* call is not a gate. `gated_projection.load()` is now
the only sanctioned way to obtain draw arrays for publication or DFS; it reads
the verdict before it opens the npz.
`test_review_enforcement.test_no_publication_path_bypasses_the_gated_loader`
greps the tree and **fails** on a direct load inside a publication directory.

The boundary is stated, not assembled from whatever happened to pass:

| Directory class | Rule | Why |
|---|---|---|
| `nfl/dfs/`, `nfl/product/`, `nfl/production/` | **must** use the loader | these turn draws into something a person acts on |
| `nfl/tools/`, `nfl/research/`, `nfl/postgame/` | may read directly | they compute statistics about draws and publish nothing; gating them would mean a blocked slate could not be diagnosed |

One exception inside a publication directory, named in the test:
`review/dossier.py` reads the same file because the review must read the
projection it is reviewing, before any verdict exists. It produces no lineup.

Measurement readers are **pinned at 12**, so a thirteenth has to be classified
deliberately rather than appearing unnoticed.

---

## 2. Blocking vs warning taxonomy

**BLOCKING — 14 codes, by category**

| Category | Codes |
|---|---|
| availability integrity | `INACTIVE_PLAYER_OWNS_OPPORTUNITY`, `INACTIVE_PLAYER_IN_SIMULATION_OR_OPTIMIZER_POOL`, `IDENTITY_UNRESOLVED_BLOCKS_INACTIVE_APPLICATION` |
| unsupported published role | `UNSUPPORTED_ROLE_PUBLISHED` |
| role/opportunity inversion | `ROOM_OPPORTUNITY_ORDER_INVERTS_ROLE_ORDER` |
| cold-start dominance | `COLD_START_CARRIES_MATERIAL_PROJECTION` |
| role-axis contamination | `SPECIAL_TEAMS_ONLY_PLAYER_CARRIES_OFFENSIVE_LOAD` |
| contradicted evidence claim | `UNAVAILABLE_EVIDENCE_CLAIMED_AS_MEASURED` |
| integrity | `ACTIVE_PLAYER_NOT_EMITTED_BY_MODEL`, `DUPLICATE_PLAYER_IDENTITY`, `MISSING_ROW_IDS`, `SIMULATION_ROW_MISMATCH`, `OPPORTUNITY_CONSERVATION_FAILURE`, `FORBIDDEN_EXTERNAL_INPUT_IN_PREDICTIVE_FEATURES` |

**WARNING — never blocking at any magnitude**

| Category | Code |
|---|---|
| optional source unavailable | `RECEIVING_ROLE_RESTS_ON_RAW_SNAPS_ONLY` |
| conservative disagreement | `DECLARED_STARTER_PROJECTED_AT_ZERO` |
| redistribution disclosure | `REDISTRIBUTED_OPPORTUNITY_DOMINATES_MEASURED` |

**An unregistered code BLOCKS.** A code in neither table is `unregistered_code`
and stops the slate. Governance failures are created exactly by a new code
appearing and defaulting to harmless.

**Materiality-exempt codes** block whatever their size: the integrity and
availability codes. A duplicated identity or a row-axis mismatch corrupts every
number in the artifact, so asking whether *this row* is material is the wrong
question.

---

## 3. The materiality rule, exactly

A conflict is MATERIAL when the row it sits on could change a published
projection, a lineup, or a market comparison. It is the **OR of five
independent tests** — any one is enough to reach an outcome.

| Test | Threshold | Provenance |
|---|---|---|
| `dk_points` | ≥ 2.0 | DECLARED REVIEW CHOICE. One reception plus a few yards; below it an error cannot reorder a six-player Showdown lineup. |
| `opportunity` | ≥ 2.0 | DECLARED REVIEW CHOICE. Two expected touches separates a rotational role from a spectator. The **audit** raises a conflict at 1.0; the **gate** blocks at 2.0, so noticing is cheaper than stopping, deliberately. |
| `team_opportunity_share` | ≥ 0.05 | DECLARED REVIEW CHOICE. ~3 plays a game; a role that small cannot invert a room. |
| `projection_disagreement` | ≥ 1.5 | DECLARED REVIEW CHOICE. The magnitude of the conflicting quantity itself. Below the opportunity floor on purpose: a large ordering error between two small projections still reveals the mechanism. |
| `captain_exposure` | in optimizer pool | **DraftKings contest rule, not a model constant.** A rostered player can be captain at 1.5×, so eligibility alone makes a row able to change a lineup. |

**Evidence-grade modifier.** A row resting on `PRIOR` / `COLD_START` /
`HISTORICAL` evidence is material at **half** these thresholds: the same number
carries less warrant, so a smaller error is worth stopping for.

**Not fitted, not tunable.** No threshold is estimated from any outcome and
none may be moved to clear a slate.

**Forbidden inputs are forbidden by signature.** `materiality()` takes
`(dossier, conflict, in_optimizer_pool, rule)`. There is no market, price,
odds, ownership or external-projection argument to pass — not one it ignores,
one that does not exist. A test asserts the signature.

A blocking code on an immaterial row becomes a warning with
`immaterial_blocking_code: true` and is **counted** in
`immaterial_blocking_codes_held_as_warnings`, so nobody can claim it was
hidden.

---

## 4. The five unsupported-role players — one shared cause

Traced individually; the cause is architectural and identical.

| Player | Club | Depth | 2026 snaps | 2026 usage | Why role_state refused | Published |
|---|---|---|---|---|---|---|
| Najee Harris | NYG | RB2 | **0 games** | 0 carries | no measured participation + `DEPTH_IMPLIES_WORKLOAD_WITHOUT_PARTICIPATION` | 5.25 carries |
| Jameis Winston | NYG | QB2 | **0 games** | — | no measured participation | 2.43 attempts |
| Max Klare | LA | TE5 | **0 games** | 0 targets | no measured participation (rookie) | 1.21 targets |
| Tutu Atwell | LA | WR6 | **0 games** | 0 targets | no measured participation | 1.31 targets |
| Patrick Ricard | NYG | FB1 (no RB rank) | 1 game, 54% | targets only, 0.0345 | `USAGE_CHANNEL_MISMATCH` — measured only in the targets channel while placed in the carries room | 0.87 carries |

**The shared path, and it is not five bugs.**

`role_state` and `run_forecast` are **two parallel role systems with no
connection between them.** `role_state` is the governing module and is not
wired into `run_forecast` at all. `run_forecast` builds its own opportunity
centre through `role_prior.assign_tiers` → `p4c_params.class_point_forecast` →
`role_prior.weight`, in which:

```python
if own_ewma is None or not n_own:
    return float(tm)          # tm = the tier mean implied by the DEPTH RANK
```

So for a player with no history the opportunity centre is **entirely the
depth-rank anchor**. A depth listing — which `role_state` explicitly calls "a
statement of intent that does not establish a role" — is load-bearing for
workload in production, and the refusal has no channel to reach it.

Four of the five are that path exactly. Ricard is the same architecture seen
from the other side: he has participation, and the channel it was measured in
disagrees with the room he was placed in.

---

## 5. Skattebo / Tracy: the numeric path

All pre-kickoff. Reproduce with
`python3.12 nfl/research/engine_repair/backfield_attribution.py`.

| Stage | Skattebo | Tracy | Singletary | Harris |
|---|---|---|---|---|
| 1 measured snap share 2026 | **0.61** | **0.03** | 0.36 | none |
| 2 measured carries 2026 | **18** | **2** | 6 | 0 |
| 2b measured carry share 2026 | **0.4865** | **0.0541** | 0.1622 | 0 |
| 3 offensive depth rank (production) | RB1 | RB4 | RB3 | RB2 |
| 4 tier | 2 | 1 | 4 | 5 |
| 4b tier basis | shrunk_trailing_and_depth | same | same | same |
| 5 panel rows (**pre-2026 only**) | 8 | 32 | 98 | 71 |
| 5b own ewma (2025 and older) | 0.3933 | **0.4751** | 0.2873 | 0.3335 |
| 5c tier-mean anchor | 0.2645 | 0.5051 | 0.111 | 0.111 |
| 5d shrinkage w | 0.9149 | **0.9773** | 0.9925 | 0.9896 |
| **6 C = opportunity centre** | **0.3824** | **0.4758** | 0.2860 | 0.3312 |
| 10 final carries (sealed) | **6.1444** | **8.0939** | 4.3762 | 5.2494 |

### The cause

**`p4c_build.load_panel()` spans ordinals 202001 → 202518 and contains ZERO
2026 rows.** Verified: `sum(1 for r in panel if r['ord'] >= 202601) == 0`.

So stage 6 computes the opportunity centre from **2025 and older football
only**. Tracy's C of 0.4758 is his 2025 lead-back carry share, held almost
unchanged because 32 prior rows drive the shrinkage weight to 0.977.
Skattebo's 18 carries and 61% snap share from 2026 week 1 **never enter stage 6
at all**. The C ratio 1.244 carries straight through to the final carry ratio
1.317.

This is the same `current_season_input_freshness` HARD invariant that made the
run **REFUSE at artifact sealing** (`denom_panel`, `team_volume_history` at
2025 week 18). The run was already known-bad at that gate, and the draws were
consumed downstream regardless. That is precisely the hole this gate closes.

### Ablations — no existing input removes the inversion

| Ablation | Skattebo | Tracy | Result |
|---|---|---|---|
| as run | 0.3824 | 0.4758 | **Tracy > Skattebo** |
| remove historical prior | 0.2645 | 0.5051 | **Tracy > Skattebo** (worse) |
| remove depth prior (tier) | 0.3693 | 0.4668 | **Tracy > Skattebo** |
| prior-only, no tier | 0.3693 | 0.4668 | **Tracy > Skattebo** |
| tier-only, no history | 0.2645 | 0.5051 | **Tracy > Skattebo** |
| **counterfactual: measured-only** | **0.3918** | **0.2465** | correct order |
| **counterfactual: panel + measured** | **0.4038** | **0.3908** | correct order |

Removing the historical prior makes it *worse*, because the tier anchors are
themselves 2025-derived. **No ablation of the existing inputs fixes it**, and
both counterfactuals that connect 2026 evidence do.

The inversion is therefore **not a weighting error in any one component**. It
is stage 6 having no 2026 input path. The measurement exists — `role_state`
reads it — and is simply not connected.

**No repair was applied.** Connecting the 2026 panel is a model change and this
directive is about enforcement and tracing.

---

## 6. Depth-row determinism

`select_listings` picks the offensive row and the special-teams row
independently under a total ordering (`dt` descending, then rank, then group
name). Tested:

- **Byte-identical under input order.** For each dual-role case, `[offensive,
  special]` and `[special, offensive]` serialise identically.
- **Stable under every permutation.** 60 shuffles → exactly 1 distinct result.
- **Equal timestamps never make file order meaningful.** Each fixture
  deliberately ties on `dt`, which is the real defect condition.

Cases: RB1+PR2, RB4+KR2, WR5+PR1, DB(LCB1)+KR1. The defensive case asserts the
opposite outcome — no offensive row at all — so no rank is borrowed into an
offensive room.

---

## 7. Route / personnel data gap

Unchanged and correct: **do not synthesize.** A standing governed request is
now open in `docs/AGENT_OUTBOX.md` for routes run, routes per dropback,
pass-blocking snaps, run-blocking snaps, personnel packages and alignment, with
point-in-time requirements (publication timestamp, per player per game, a
`gsis_id`-joinable key, no edit-distance matching).

The disposition is deliberate and two-sided:

- **Unavailable is a WARNING.** 21 receivers on this slate carry
  `RECEIVING_ROLE_RESTS_ON_RAW_SNAPS_ONLY`. A slate does not stop because an
  optional source is absent.
- **A claim on unavailable evidence BLOCKS.**
  `UNAVAILABLE_EVIDENCE_CLAIMED_AS_MEASURED` is registered as blocking. An
  absent source is a disclosed limitation; a claim resting on one is a false
  statement about the evidence.

---

## 8. `guard_rank_map` production wiring

Wired at `run_forecast.py:1491`, replacing `dr[k] = v[1]` — which kept the rank
and discarded the group, so a fullback listed FB1, a guard listed LG2 and a
defender listed RDE1 all entered the backfield and receiver rooms as rank-1
evidence.

**Measured before wiring**, on 2026_02_NYG_LA at cut 2026-09-21T23:05Z:

| | |
|---|---|
| entries in | 119 |
| kept | 36 |
| refused | 83 |
| kept ranks whose value changed | **0** |
| tier changes, carries room | **0** |
| tier changes, targets room | **0** |

A no-op on this slate's output that removes 83 cross-room ranks which are not
no-ops in general. Refusals are returned by name in
`fx['_r6']['depth_rank']['guard']`, so the narrowing is evidence rather than a
silent filter.

A test asserts the call exists, that the unguarded assignment is gone from the
**code** (an earlier version of the test failed on its own explanatory
comment), and that the map the forecast consumes is the guarded one.

---

## 9. Artifacts

```
nfl/research/player_review/<slate_key>/
    player_dossiers/<gsis_id>.json    156 files
    slate_review_report.json
    projection_audit.json
    review_gate.json
```

`review_gate.json` for 2026_02_NYG_LA:

```
verdict                                       BLOCKED
reviewed_player_count                         156
publishable_player_count                      28
blocking_conflict_count                       17
warning_count                                 21
blocking_by_category   role_opportunity_inversion 8
                       unsupported_published_role 5
                       cold_start_dominance       4
warning_by_category    optional_source_unavailable 21
immaterial_blocking_codes_held_as_warnings    {}
blocking_players       Darnell Mooney, Jameis Winston, Konata Mumpfield,
                       Max Klare, Najee Harris, Patrick Ricard, Theo Johnson,
                       Tutu Atwell, Tyrone Tracy Jr., Xavier Smith
```

Plus `nfl/research/engine_repair/BACKFIELD_ATTRIBUTION.{json,txt}` and the
script that regenerates them.

---

## 10. Remaining blockers

1. **Stage 6 has no 2026 input.** The single highest-value repair, and the one
   this trace identifies. It is a model change and was not made.
2. **`role_state` is still not wired into `run_forecast`.** The governing
   module's refusals reach the gate but not the generator, so the engine
   continues to publish roles the governor rejects and the gate continues to
   stop the slate afterwards. Correct as a safety property, wasteful as a
   pipeline.
3. **Routes, blocking splits and personnel remain unavailable.** Assigned.
4. **The gate is not yet called from inside `run_forecast` itself**, only from
   the publication and DFS consumers. A refused slate still costs a full 318s
   engine run before anything says so.
5. Two pre-existing suite failures, unchanged by this work and verified at
   baseline: `test_determinism_proof` (`commit_claim.py` calls git) and
   `test_draw_coherence` (missing DET_BUF board fixture).
