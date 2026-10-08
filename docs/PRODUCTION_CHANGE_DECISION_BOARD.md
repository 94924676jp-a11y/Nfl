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

### SC-OWN-ROTATION-2, B4/B3S, appearance successor

**Label:** SHADOW ONLY (unchanged). Prospective evaluation continues from TB@DAL; N ≥ 4 slates before any verdict.

## Owner decisions open

1. **The scenario-response finding** (`TB_DAL_ISOLATION_AND_FIREWALL_AUDIT_2026-10-08.md`).
   - TB team volume, scoring and receiver targets do not respond to which QB starts. The model has no such pathway, and
     the registered repair would not add one.
   - Under the owner's rule this blocks READY unless the owner accepts the limitation.
2. **Merging the reviewed A and B rows** as the production baseline for future slates.
3. **Whether C1, C4 and F2/F3 enter shadow evaluation.**
