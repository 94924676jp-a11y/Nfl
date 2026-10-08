# Production change decision board (deliverable E), 2026-10-08

None of these labels is a production approval. "Eligible for owner review" means the evidence is ready for a
decision; it is not the decision.

## Rows

### A1 – A3: false READY, starter-state guard, explicit environment (`69fceb0d`)

**Label:** SAFE VALIDATION FIX — **ELIGIBLE FOR OWNER REVIEW**. The code is already on the branch.

**Evidence:**
- **Fixtures:** 13 READY/QB fixture conditions moved from fail to pass; the valid controls still pass; with the guards
  bypassed they fail again.
- **Actual entrypoint:** the real-entrypoint refusal probe and the R6 receipt run.
- **TB@DAL:** 26/26 checks byte-identical.
- **ATL@NO:** at point-in-time, the uploads equal production.

**Rollback:** `git revert 69fceb0d`.

### A4: certificate refuses added arrays (`69fceb0d`)

**Label:** SAFE VALIDATION FIX — ELIGIBLE FOR OWNER REVIEW.

**Evidence:**
- **Fixture:** `PUB-added_array` passes.
- **Classic path:** `run_forecast` adds every layer before it certifies, so a legitimate classic run cannot be refused.
- **Showdown:** not on the Showdown path.

### B1: per-scenario work directories, global lock, tree-diff guard (`66990085`, `d0cd2672`)

**Label:** CONTAINMENT plus SAFE EXECUTION FIX — ELIGIBLE FOR OWNER REVIEW.

**Evidence:**
- **Equivalence:** R3 vs R4 byte-identical.
- **Guard proven in action:**
  - it caught `SOURCE_MEASUREMENT_CACHE.json` writing during a build;
  - the lock refused a concurrent run.
- **Permanent track:** scenario transactions.

### B2: content-bound cache keys; role state bound to its own slate state (`0ea3bc21`)

**Label:** SAFE EXECUTION / VALIDATION FIX — ELIGIBLE FOR OWNER REVIEW.

**Evidence:**
- **TB@DAL:** Daniels and Mayfield are both 26/26 identical.
- **ATL@NO:** at point-in-time, identical.
- **Fixtures:** `DATA-kicking_cache` and `DATA-measurement_cache` pass.

### C1: conditional pass keeps `_chart_rank`

**Label:** SHADOW CANDIDATE / INSUFFICIENT EVIDENCE. **Not in production.**

**Evidence:**
- **What moves:** only `dk_points_if_plays` and conditional volume, in the intended TE-order direction.
- **What doesn't:** the draws (except floating-point rounding) and the portfolio, on both slates.
- **Effect in the current pipeline:** none on DFS.
- **When it would matter:** only once a consumer of conditional volume is promoted, such as the appearance successor.
- **To promote it:** prospective evidence, together with that consumer.

### C2: appearance / `p_plays` successor

**Label:** FAILED TEST (gate, registered) / SHADOW CANDIDATE (rates). **Not in production.**

**Evidence:** registered result. Rates and gate must be fixed together; 2025 has been read three times, so it is not
a holdout.

### C3: event-linked world coherence repair

**Label:** SHADOW CANDIDATE / INSUFFICIENT EVIDENCE.

**Evidence:**
- SC-COH-1 clean evaluation: it fails superiority on energy and variogram scores and non-inferiority on team CRPS.
- Not portfolio-runnable yet.
- The QB = receiving-yards break (registered defect R1) stays open.

### C4: PBP de-duplication

**Label:** INSUFFICIENT EVIDENCE for the classic path; NOT APPLICABLE to Showdown.

**Evidence:** it changes an approved classic fit (619 vs 259 distinct 2026 FG attempts). It needs its own classic A/B
and owner approval.

### C5: cohort-cache panel binding

**Label:** CONTAINMENT deferred.

**Evidence:** no live effect, since one panel is loaded per process. The fix re-stamps role lineage, so it waits for a
quiet window.

### F1: game resolution checks the export's kickoff date

**Label:** SAFE VALIDATION FIX (proposed).

**Evidence:** none tonight; to be implemented and regression-tested after TB@DAL. TB@DAL is unaffected.

### F2 / F3: roster and PBP capture selected by capture time at the slate's cutoff

**Label:** proposed; class B, which may change outputs where captures disagree.

**Evidence:**
- **TB@DAL:** 0 slate players affected by roster order; the newest PBP is pre-lock.
- **Historical replay:** required for any replay to be cutoff-correct.
- **Before release:** needs its own matched regression.

### F2 / F3 (eligibility half): point-in-time data-selection contract (`e1e6d755`, `da99c5de`)

**Label:** SAFE VALIDATION / EXECUTION FIX, opt-in — **ELIGIBLE FOR OWNER REVIEW**. Live mode is the identity.

**Evidence** (`docs/POINT_IN_TIME_CONTRACT_2026-10-08.md`):
- **Tests:** `test_point_in_time` 32/32, including the injection, the negative control and the backstop.
- **ATL@NO, from today's full tree under a sealed manifest, nothing deleted:**
  - the derived caches rebuilt 6/6 identical to the generation-1 pins;
  - the replay reproduces upload `8f4d9a77` and all three per-contest uploads;
  - 26/26 matched checks are identical to the historical baseline.
- **Defect found and fixed on the way:** `kicker_model` leaked week 4 through an unarmed process.
- **Injection:** post-lock data with forged clocks leaves the sealed replay 26/26 identical. The no-manifest
  negative control refuses.
- **TB@DAL live:** matched regression R7 vs R9 is **26/26 identical**. R8 was refused by the tree-diff guard (my edit
  during the build) and is recorded as invalid.

**Not included:** ordering by capture time (F2's second half) and the game-date check (F1). Both are separate
changes, each needing its own regression.

### F4: a refused re-run overwrote the original scenario's run ledger (`73008ae0`)

**Label:** SAFE EXECUTION FIX — ELIGIBLE FOR OWNER REVIEW.

**Evidence:**
- **Found:** a `SCENARIO_EXISTS` refusal rewrote `RUN_LEDGER_PRECOMPUTE_TBQB_DANIELS_R7.json`. It was restored
  byte-identical in `0684bdfd`.
- **Fix:** the refusal now writes its own `.REFUSED_<UTC>` ledger.
- **Test:** added to `test_showdown_next_slate` (35/35).

### QB-replacement pathway (SC-QB-ENV-1)

**Label:** DESIGNED, NOT IMPLEMENTED. SHADOW ONLY when built.

**Evidence** (`docs/QB_DEPENDENCY_AUDIT_2026-10-08.md`):
- **Dependency graph:** stages 4/5 (club volume, scoring centre) and 8/11 (team passing efficiency) ignore QB identity.
- **Measured effect, 2021–2025:** in-season replacements score −1.06 [−2.06, −0.02] points against the QB-blind
  centre, and rush +0.92 [+0.12, +1.67].
- **Readiness:** TB@DAL Daniels is `FOOTBALL_MODEL_INCOMPLETE_QB_ENVIRONMENT`, not READY.

### Six unverified P0 integration obligations

**Label:** STILL UNVERIFIED.

**Blocker:** the production entrypoints write to fixed repository paths. The pack's sandboxed bridge needs a
scratch-output root that the pipeline does not yet have. The point-in-time scratch root is run-scoped but covers
resolved inputs only, not outputs.

**Not claimed:** none of these is claimed closed by documentation alone.

### C1 published-world accounting checker (`world_accounting_check`)

**Label:** SAFE VALIDATION TOOL, report-only. **Not a gate.**

**Evidence** (`docs/FOOTBALL_INTELLIGENCE_AUDIT_2026-10-08.md` §2):
- Tests 9/9.
- **Every published world measured violates ordinary-event laws:**
  - passer vs receiver yards;
  - catchless receiving yards and TDs;
  - INTs not taken away by the opposing DST;
  - points below 6 × TDs.
- **This covers ATL@NO's live portfolio worlds too.**

**Owner decision:** a gate now would refuse every slate.

### SC-OWN-ROTATION-2, B4/B3S, appearance successor

**Label:** SHADOW ONLY (unchanged). Prospective evaluation continues from TB@DAL; N ≥ 4 slates before any verdict.

## Owner decisions open

1. **The scenario-response finding** (`TB_DAL_ISOLATION_AND_FIREWALL_AUDIT_2026-10-08.md`).
   - TB team volume, scoring and receiver targets do not respond to which QB starts. The model has no such pathway, and
     the registered repair would not add one.
   - Under the owner's rule this blocks READY unless the owner accepts the limitation.
2. **Merging the reviewed A and B rows** as the production baseline for future slates.
3. **Whether C1, C4 and F2/F3 enter shadow evaluation.**
