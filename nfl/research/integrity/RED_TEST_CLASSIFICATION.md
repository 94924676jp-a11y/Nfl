# Pre-existing red tests, classified

Owner ruling 2026-09-23: *"Do not classify existing red tests as harmless
merely because they predate these commits... UNKNOWN remains UNKNOWN until
classified."*

**Measured** from a full `nfl/tests/run_suite.py -v` run at `fef1230`, the
commit before the draw-coherence promotion:

| | |
|---|---|
| modules discovered | 218 |
| test functions | 2,442 |
| checks | 12,687 |
| **failing checks** | **104** |
| **raised** | **39** |
| blocked functions | 22 |
| **modules carrying red** | **42** |

That is the honest size of the surface. It is larger than any single slice,
which is why this file exists as an inventory rather than as a repair.

## Categories used

- **REAL_PRODUCTION_DEFECT** — the test is right and production is wrong.
- **MISSING_ARTIFACT** — the invariant is fine; the artifact it reads was
  never produced or never committed.
- **STALE_FIXTURE** — the test's own inputs no longer match how production is
  called.
- **OBSOLETE_CONTRACT** — the test reads a key or shape the producer stopped
  emitting.
- **UNKNOWN** — not established. Stays UNKNOWN.

## Root causes, and the modules each explains

### 1. Two sealed DET-BUF runs never produced a `board.json` — ~~MISSING_ARTIFACT~~ **WRONG, CORRECTED 2026-09-23**

**This classification was wrong and the evidence was in the runs' own status
files.** See `LANE1_INVESTIGATIONS_2026-09-23.md` for the corrected finding:
`fced077d0db6ab41` carries `status: REFUSED` with a named sealing refusal, so
it never reached board generation; and
`post_inactives_V1_CANDIDATE_R9_W1P_GA_OFFICIAL` is not a run directory at all
but a derived zero-delta artifact whose own `WHAT_THIS_IS_NOT` field says
reporting it as a board "would be the false green this project exists to
refuse". Nothing is missing. The defect is in the discovery contract, which
treats any directory holding `player_draws.npz` as a sealed board.
Correct category: **EXPECTED_GOVERNANCE_FAILURE + TEST_BUG.**

The original text follows, struck through, because a wrong classification that
was acted on should stay visible.

#### ~~Original (wrong)~~

`post_inactives_V1_CANDIDATE/fced077d0db6ab41` and
`post_inactives_V1_CANDIDATE_R9_W1P_GA_OFFICIAL` carry
`player_draws.npz`, `player_draws_manifest.json`, `refusals.jsonl` and
`run_status.json`, and **no `board.json`**. Verified: `git log --all` for that
path is empty, so it was never committed; every `pre_inactives` run in the
same slate has one. The runs sealed draws and never produced a board.

Explains: `test_draw_coherence` (3 raises), `test_p8_tails_and_counts` (1),
`test_publication_semantics` (1), `test_sealed_corpus_census` (1),
`test_conservation` (2 of 3 — `CONSERVATION_RUN_INCOMPLETE` names exactly
those two run ids).

**Owner:** run_forecast / publication. **Disposition:** decide whether those
two runs are meant to be complete. If yes, this is a real publication defect
and the boards are missing; if no, they must be marked as draws-only so the
census stops treating them as sealed boards. **Not a test defect either way.**

### 2. `nonqb/layers.py` no longer hashes to the Q9 frozen identity — REAL_PRODUCTION_DEFECT or OBSOLETE_CONTRACT, UNRESOLVED

`b081a5b2fa45be25…` against the expected `481f005f682cd721…`. Five modules
assert the frozen artifact still reproduces and all five disagree.

Explains: `test_appearance_candidate_b`, `test_appearance_team_scope`,
`test_c1_denominator`, `test_p1_appearance_repair`,
`test_qb_eligibility_den_kc`.

**Owner:** Q9 promotion state. **Disposition: UNKNOWN, and deliberately so.**
Either the frozen candidate identity is stale, or a promoted artifact changed
under a seal. Those have opposite repairs and the difference matters. The
standing instruction is not to modify Q9 promotion state, so this is
escalated, not touched.

### 3. The deployed capture surface does not match the approved release — REAL_PRODUCTION_DEFECT

`CAPTURE_EXECUTOR_SURFACE_MISMATCH`: running surface `efab90d6a01d8b2d…`
against a different approved release sha.

Explains: `test_capture_deployment_integrity` (1),
`test_capture_prod_deployment` (5), `test_preflight` (2, `WORKFLOW_STALE`).

**Owner:** capture deployment. **Disposition:** already tracked as D24-R1,
D24-R2, D24-R3. These tests are working.

### 4. `test_p6_false_greens` — REAL_PRODUCTION_DEFECT, deliberately fenced

18 failing checks, and the module says so itself: *"18 P6 reproduction(s) are
still failing. That is the reported state of the repository, not a defect in
this file."* A red test doing exactly its job.

**Disposition:** leave red until the reproductions are fixed. Turning it green
would be the defect.

### 5. `test_stat_contract` — REAL_PRODUCTION_DEFECT, **fence correctly held**

**Refined 2026-09-23** by measurement, in
`LANE1_INVESTIGATIONS_2026-09-23.md`: the +27,925 is five previously-unscanned
PRE-REPAIR week-1 boards, not new corruption. All 39 affected runs are 2026
week 1; every post-repair board has zero non-integer carry cells. The fence
should NOT be moved — the repair is to the boards. Original text follows.

#### ~~Original (said "move the fence")~~

543,000 carry cells across 114 sealed runs; 243,766 non-integer (50.04%) is
the fenced size and the measurement now returns **271,691**. The defect is
real and it has GROWN since the fence was set.

**Disposition:** re-measure and move the fence to the current number, with the
growth recorded. Do not widen it silently.

### 6. `ROSTER_CUT_REQUIRED` raised in a rehearsal fixture — STALE_FIXTURE

`test_full_slate_rehearsal` (2 fail, 5 raise): *"a roster vintage cannot be
chosen without a run cut. Pass written_at; do not fall back to a glob."* The
guard was added after the fixture; the fixture still calls the old way.

**Disposition:** pass `written_at` in the fixture. The guard is correct.

### 7. Producers stopped emitting keys tests read — OBSOLETE_CONTRACT

`KeyError: 'single_adjustment_ownership_verified'` (`test_gate_ids`,
`test_ownership_audit`), `KeyError: 'n_files_scanned'`
(`test_ownership_audit`), `KeyError: 'items'` (`test_system_state`).

**Disposition:** reconcile each test against what its producer emits today.
Cheap, and each one currently hides whatever else that module would check.

### 8. Regenerable inventories have drifted — STALE_FIXTURE, remedy stated

`test_system_state` (*"regenerate: python3.12 nfl/tools/system_state.py
--write"*), `test_p7_dag` (*"regenerate: python3.12
nfl/production/pipeline.py --write-read-inventory"*).

**Disposition:** regenerate and commit. **But `test_p7_dag` also carries
`UNDECLARED_VINTAGE_READ` on `universe/usage_vintage.py`, which is a
leakage-adjacent governance finding and is NOT regenerable away.** That part
is REAL and must be looked at before the inventory is refreshed.

### 9. A module outside `nfl/identity/` shells to git — REAL_PRODUCTION_DEFECT

`test_determinism_proof`: `sportsplatform/governance/commit_claim.py` calls
git for working-tree state.

**Disposition:** route it through the identity layer. Small, real.

### 10. Everything else — UNKNOWN until examined

`test_agent_state` (5 raises), `test_capture_obligations` (4),
`test_execution_identity` (1), `test_football_engine_r4` (2),
`test_governance_transport` (1), `test_harness_audit` (1 — three modules with
zero test functions; **verified not caused by `nfl/tests/governed_draws.py`**,
which does not match the `test_*.py` glob the audit discovers),
`test_inactives_substance` (4), `test_kicker_resolution` (1 — NYJ,
`KICKER_ELIGIBILITY_DISAGREES_ACROSS_VINTAGES`),
`test_live_capture_den_kc` (1), `test_non_g0a_isolation` (2),
`test_nonqb_r3` (1), `test_p7_data_plane` (3),
`test_product_orchestration` (1), `test_q9_live_feature_builder` (5),
`test_qb2_production` (13), `test_r5_active_pool` (2),
`test_readiness_vintage_cut` (2), `test_replay_pins_its_inputs` (1),
`test_sc2_interception_reservation` (1 — the open SC2-A task),
`test_v1_draw_artifact` (3), `test_v1_rushing_a1` (3).

**Disposition: UNKNOWN. Each needs its own look, and none may be called
harmless because it predates a commit.** `test_qb2_production` at 13 failing
checks and `test_q9_live_feature_builder` at 5 are the two largest and should
be examined first.

## What this file is not

It is not a claim that the repository is fine. 104 failing checks and 39
raises is a large red surface, and the second-largest cluster — the Q9 frozen
identity — is UNKNOWN in a way that could mean a sealed artifact changed
underneath a promotion. That is the one an owner should look at first.

V2 NOT YET EARNED.
