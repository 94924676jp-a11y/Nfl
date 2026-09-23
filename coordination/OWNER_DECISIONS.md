# Owner decisions

**Active rulings. This file is written only by an OWNER task.** No agent edits
it on its own initiative; `validate_coordination.py` fails if a decision
heading disappears without a superseding entry.

Each ruling carries the date, the ruling, and **where it is enforced** — a
ruling with no enforcement point is a preference, and preferences drift.

---

## D-01 · A frozen identity means the frozen bytes reproduce, not that the working tree is current

The Q9 pin is a **reproduction contract**. It asserts that these exact bytes
produced this candidate's numbers and that a re-run must use them. It does not
assert that the file may never change — forbidding that would freeze the
repository rather than the candidate.

What must be proved: the pin was correct at freeze time; the exact blob is
still retrievable; the candidate reproduces from the pinned dependency set;
reproduction reads the **frozen** bytes, not the working tree.

Working-tree divergence is a separate, informational diagnostic
(`WORKING_TREE_DIVERGED_FROM_FROZEN_CANDIDATE`). It is governance evidence
about the tree, never evidence that the candidate is invalid.

*Do not move the pin. Do not rewrite the Q9 identity. Do not revert
`layers.py`.*

**Enforced by:** `nfl/production/frozen_candidate.py`;
`nfl/research/q9b/FREEZE_PIN_DIVERGED.md`.

## D-02 · A REFUSED artifact is not a sealed board

A run whose authoritative status is `REFUSED` did not seal and is not a
publishable board. It stays discoverable as a refused run for audit.

**Enforced by:** `nfl/research/sealed_index.py::artifact_kind`;
`nfl/tests/test_artifact_kind.py`.

## D-03 · A non-board artifact is not discovered as a board because draw files exist

A governed sealed board is **not** "a directory containing
`player_draws.npz`". Discovery honours the artifact's own machine-readable
declarations, a declared non-board wins over a seal marker, overlay and
zero-delta artifacts are treated by their declared type, and missing or
contradictory declarations **fail closed** rather than being guessed into a
board.

This is a truth-model correction, not a test-only exception.

**Enforced by:** `sealed_index.artifact_kind` / `sealed_boards` /
`classify_live`; `nfl/tests/test_artifact_kind.py`.

## D-04 · Recovered historical content is not PIT-admissible content

`CONTENT_RECOVERED` ≠ `AVAILABLE_BY_CUT_PROVEN`. Discovery, acquisition,
parsing, identity resolution and PIT admission are separate stages, and no
later stage may be inferred from an earlier one.

A printed "as of" date does not establish publication time. A model
initialization time does not establish availability. A first-observed time is
not a first-published time. An artifact recovered after a cut does not become
admissible retroactively.

**Enforced by:** `nfl/production/dependence.py` (replay evidence states);
to be extended by ENG-008.

## D-05 · `state_at_cut` excludes PIT-unproved historical evidence

Evidence that was recovered but whose availability by the cut is unproven does
not enter the state a forecast is built from. It is recorded as
`RECOVERED_CONTENT_PIT_UNPROVED`, which is truthful historical reconstruction
evidence and is **not** failure — but it is not admissible input either.

A cut cannot become `PIT_SAFE` because some subset of its evidence is.

**Enforced by:** `dependence.ReplayEvidenceStatus`, `dependence.for_cut`
(`PIT_SAFE` / `HISTORICAL_RECONSTRUCTION_ONLY` / `UNRECOVERABLE_FOR_CUT`);
to be extended by ENG-008.

## D-06 · Canonical facts are OBSERVED, DERIVED, PROXY or UNAVAILABLE

A canonical fact carries which of the four it is. `UNAVAILABLE` is a real
value and stays one; it is never resolved by inference, and absence of
evidence is never evidence of absence.

**Enforced by:** `nfl/production/review/evidence.py` grades;
`nfl/production/state/` canonical facts.

## D-07 · LATENT estimates are model outputs, not canonical historical truth

A latent quantity the model estimates does not enter canonical state. Canonical
state carries what was observed, derived or proxied from evidence that existed
at the cut. A model's estimate of an unobserved quantity is an output, and
writing it back into canonical truth would make the model its own evidence.

**Enforced by:** the canonical-state boundary; `PregameSlateState` is the one
lawful reader.

## D-08 · Sportsbook information is downstream diagnostic only

Sportsbook prices must not become predictive inputs into the football model.
Ownership, `% Drafted`, field composition, duplication, payout structure,
optimizer metrics and Vegas-derived fields must not flow backward into player
projections, team volume, role, efficiency, appearance, game simulation or
touchdown probability.

**Enforced by:** `nfl/tests/test_dfs_history.py` (structural isolation);
`nfl/production/DFS_ARCHITECTURE.md` (one-directional arrow).

## D-09 · SimulationCalibration is not authorized for implementation

Registered as the next scientific workstream. Not started, not authorized.
Recorded requirements: A/B/C/D arms; marginal CRPS; randomized PIT; accounting
invariants; energy score; variogram score; prespecified joint-exceedance
events; deterministic hierarchical RNG streams; saved shared-world causal
trace.

**Variogram score is a required diagnostic, never a standalone promotion
criterion.** No simulator is promoted because one score improved.

**Enforced by:** `ENGINEERING_QUEUE.json` ENG-012 `authorized=false`;
`nfl/production/dependence.py`.

## D-10 · HistoricalArtifactManifest waits on replay-selection correctness

The manifest is not begun until `REPLAY_RE_SELECTS` is corrected. Building a
historical manifest on a replay that re-selects against today's manifest would
put the contract on top of the defect it exists to prevent.

**Enforced by:** `ENGINEERING_QUEUE.json` ENG-008 `depends_on: [ENG-001]`,
`authorized=false`.

## D-11 · V2 NOT YET EARNED

`G0A` 11/12. `NFL-1` NOT AUTHORIZED. Accepted baseline **R8**. Q9 candidate
identity `6310f67ccb8b0edf`, **unpromoted**. Historical reconstruction,
however good, cannot satisfy a genuine unattended event-anchored prospective
T−90 requirement.

**Enforced by:** `nfl/production/authorization.py`.

---

## Supporting rulings, same standing

- **A required invariant that nobody evaluated is not a passing invariant.**
  `NOT_APPLICABLE` requires evidence that the artifact lacks the population
  being checked; an absent array is not evidence.
- **One integrity code means one invariant owned by one authoritative
  producer.**
- **Advertise only what production executes.** Producer exists AND production
  executes it AND evidence survives transport AND review consumes the stored
  result AND `NOT_CHECKED` blocks AND a corrupted fixture fails end to end.
- **`run_suite` is the authoritative test execution path.** A zero exit code
  from direct module invocation is not a test result.
- **The red suite standard is not "green at any cost."** Every red test is
  repaired because the product was wrong, repaired because the test was wrong,
  or intentionally red with a documented reason. UNKNOWN trends toward zero and
  may remain UNKNOWN where evidence is insufficient.
- **Fix the fixtures, not the rule.** No hard-coded PASS, no fabricated
  certificate, no weakened checker.
