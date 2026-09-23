# Owner decisions

**This file is the record of what the owner ruled, not what anyone inferred.**
An entry appears here only when the owner stated it. Where an agent proposed
something and the owner did not answer, it belongs in a queue as OPEN, not
here as a decision.

Each entry carries the date, the ruling in the owner's terms, and where it is
enforced — because a ruling with no enforcement point is a preference, and a
preference drifts.

---

## 2026-09-23 — Draw coherence is promoted, with applicability that proves itself

`SIMULATION_DRAW_COHERENCE_VIOLATED` moves to `ADVERTISED_INTEGRITY`. For a
governed publishable simulation artifact, draw coherence is a **required**
invariant, and a missing evaluation may not be treated as equivalent to a
pass.

**Fix the fixtures, not the rule.** A fixture blocked by promotion is repaired
into a governed artifact, or declares explicitly that it holds no publishable
simulation population. Not grandfathered, not turned into a hard-coded PASS,
no fabricated certificate, no weakened checker.

**Applicability semantics.** `APPLICABLE_AND_CHECKED`,
`APPLICABLE_BUT_NOT_CHECKED`, `NOT_APPLICABLE`. The middle one BLOCKS.
`NOT_APPLICABLE` requires evidence that the governed artifact does not contain
the population being checked — an absent array is not evidence, and an
artifact that claims to be a full NFL simulation is applicable even without a
quarterback row.

*Enforced by:* `nfl/production/integrity/contract.py` (`Applicability` refuses
NOT_APPLICABLE without evidence), `review/gate.py::assert_producer_coverage`,
`nfl/tests/test_conservation_integrity.py`.

## 2026-09-23 — One integrity code means one invariant, owned by one producer

Keep `OPPORTUNITY_CONSERVATION_FAILURE`, `OPPORTUNITY_CONSUMER_OUT_OF_SCOPE`
and `SIMULATION_DRAW_COHERENCE_VIOLATED` separate. Do not merge them.

*Enforced by:* `IntegrityReport.compose` refusing a code claimed by two
producers; `nfl/production/conservation_integrity.py`.

## 2026-09-23 — The chain→review bridge transports, it does not recompute

Review consumes a stored governed verdict and its certificate. Review must not
recompute from partial inputs. A malformed or mismatched certificate blocks; a
missing verdict is `NOT_CHECKED`. The bridge must not create a second
authority for conservation — the authoritative producer remains the existing
owner.

*Enforced by:* `nfl/production/universe/conservation_bridge.py`,
`review/gated_projection.py`.

## 2026-09-23 — Advertise only what production actually executes

An integrity code is restored from RELINQUISHED to ADVERTISED only after:
producer exists **AND** the production path executes it **AND** stored evidence
reaches review **AND** `NOT_CHECKED` blocks **AND** a corrupted fixture fails
end to end.

*Status:* the allocation codes remain RELINQUISHED. `run_chain.run` has no
orchestrating caller, so nothing places a bridge beside a forecast review.

## 2026-09-23 — Ruling 1: the Q9 pin is a reproduction contract

Classified `POST_FREEZE_DEPENDENCY_DRIFT`, frozen candidate remains
reproducible. The assertion must prove the pin was correct at freeze time, the
blob is still retrievable, the candidate is reproducible from the pinned
dependency set, and reproduction reads the frozen bytes rather than the
working tree.

**Do not move the pin. Do not rewrite the Q9 identity. Do not revert
`layers.py`.** Working-tree divergence is a separate diagnostic and is
informational governance evidence, not evidence the candidate is invalid.

*Enforced by:* `nfl/production/frozen_candidate.py`;
`nfl/research/q9b/FREEZE_PIN_DIVERGED.md` corrected in place with the original
preserved.

## 2026-09-23 — Ruling 2: a sealed board is what the artifact declares

A governed sealed board is **not** "a directory containing
`player_draws.npz`". Discovery honours the artifact's own machine-readable
declarations. A REFUSED run is not a publishable board and stays discoverable
for audit. An artifact declaring it is not a board is not promoted because it
holds draws. Missing or contradictory declarations **fail closed**.

This is a truth-model correction, not a test-only exception.

*Enforced by:* `nfl/research/sealed_index.py::artifact_kind`,
`nfl/tests/test_artifact_kind.py`.

## 2026-09-23 — Ruling 3: `run_suite` is the authoritative execution path

Direct `python3.12 module.py` execution is **not** a passing test result
unless the module implements that contract. A module containing checks that
the runner discovers as zero executable checks is reported
`TEST_MODULE_NOT_EXECUTED` and fails the suite.

*Enforced by:* `nfl/tests/run_suite.py`, `nfl/tests/test_harness_audit.py`.

## 2026-09-23 — Sequencing

1. Finish Lane 1 and resolve the serious UNKNOWN reds and the Q9 mismatch.
2. Build the HistoricalArtifactManifest vertical slice — **blocked until
   `REPLAY_RE_SELECTS` is corrected**.
3. Scale historical recovery only after the slice proves the contracts.
4. Start SimulationCalibration A/B/C/D.

Do not start SimulationCalibration. Do not start the manifest until R14 is
fixed.

## 2026-09-23 — The red suite acceptance standard

The goal is not "all tests green at any cost". Every red test is either
repaired because the product was wrong, repaired because the test was wrong,
or **intentionally red with a documented governance or historical reason**.
UNKNOWN must trend toward zero, and may remain UNKNOWN where evidence is
insufficient. Do not force a classification for cosmetic completion.

## 2026-09-22 — DFS archival, and what stays unbuilt

Build only the durable historical DFS archival foundation. **Do not build**
`OwnershipModel`, `FieldSimulator`, `PayoutEV` or `PortfolioOptimizer`.
Manual acquisition only until automation permission is resolved. Raw bytes are
evidence; derivatives are generated separately.

## 2026-09-22 — The sign-error target is retracted

The simulated team-vs-opponent value of −0.128 is **UNVERIFIED** and is not a
calibration target. Historical across-game correlation and within-game
across-world correlation are different estimands and their numerical equality
is not a target. Every dependence metric must name its population,
conditioning state, random dimension, outcome definition and aggregation
level.

*Enforced by:* `nfl/production/dependence.py`.

## 2026-09-22 — Replay evidence is a cut-level verdict

`PIT_SAFE` / `HISTORICAL_RECONSTRUCTION_ONLY` / `UNRECOVERABLE_FOR_CUT`. A cut
carrying an unrecoverable requirement **may not be presented as a backtest**.

*Enforced by:* `dependence.ReplayEvidenceStatus`, `dependence.for_cut`.

## Standing, unchanged

`G0A` 11/12. `NFL-1` NOT AUTHORIZED. `V2` NOT YET EARNED. Q9 promotion state
untouched. Historical reconstruction, however good, cannot satisfy a genuine
unattended event-anchored prospective T−90 requirement.
