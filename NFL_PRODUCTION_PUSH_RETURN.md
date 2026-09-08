# NFL PRODUCTION PUSH RETURN

**G0A remains 11/12. NFL-1 remains NOT AUTHORIZED. Nothing has been promoted
from mined historical evidence.**

| | |
|---|---|
| **Starting HEAD** | `536fd7a` |
| **Final HEAD** | see §3 — the capture bot rebases this branch, so commit titles are the stable identity |
| **Repository tests** | **302 functions, 0 failures** (from 285) |

## 1. What changed in posture

Research continues to return weak signals — RC1 `SIGNAL_WEAK`, RC2
`CALIBRATION_DEFECT_CONFIRMED`, and now TD2 `SIGNAL_WEAK`. **That is not a
reason to withhold a baseline.** This push builds the machinery to ship the
most rigorous defensible baseline, and stops precisely at the gate.

## 2. TD2 — the minimum blocking science (§5A)

Completed and returned separately in `TD2_TOUCHDOWN_RECOVERABILITY_RETURN.md`.
Pre-registration sha256 `31e75d823c0027a9a4f623670a2cf104de6a1eccde8adf4027ae3d2b0f250f83`.

**State: `SIGNAL_WEAK`, receiving and rushing.** Best rung gains +0.043% log
loss (receiving) and **loses** 0.125% (rushing) against a pooled positional
baseline, on a 1% bar. Receiving's gain carries **negative resolution** — it is
shrinkage, not signal. Composition CIs span zero. **The family recovered 0.15%
and 0.55% of the measured TD conversion oracle opportunity.**

**Persistence is the decisive result:** opportunity persists far more than
conversion at every horizon — split-half +0.944 / +0.970 against +0.291 /
+0.459; game level +0.591 / +0.676 against +0.083 / +0.122.

**TD production decision: keep the accepted control.** No candidate
distinguishably beats it; switching would be a promotion from mined data. **No
production change required.**

## 3. Commits, by stable title

| # | title |
|---|---|
| 1 | TD2 pre-registration: touchdown recoverability and downstream composition |
| 2 | TD2: touchdown recoverability — SIGNAL_WEAK, receiving and rushing |
| 3 | Production push: readiness contract, entrypoint, orchestrator, refusals, joint baseline |
| 4 | (this return) |

## 4. Repository-wide tests

**302 test functions, 0 failures** — up from 285, adding 68 production
assertions and 52 TD2 assertions with 4 new guard-deletion proofs.

## 5. Production architecture

`nfl/production/`:

| module | role |
|---|---|
| `PRODUCTION_READINESS_CONTRACT.md` + `production_readiness.json` | the twelve capabilities, machine-checkable; **10 GREEN, 2 PARTIAL** |
| `run_forecast.py` | the canonical entrypoint |
| `pipeline.py` | 14-stage orchestrator; per-stage state, hashes, spec version, warnings, refusal code, timing |
| `refusal.py` | **17 named refusal codes**, persisted append-only |
| `authorization.py` | the publication gate |
| `joint.py` | minimum-viable production coupling |
| `RELEASE_CHECKLIST.md` | GREEN NOW / BLOCKED BY G0A / BLOCKED EXTERNAL / NON-BLOCKING DEBT |

**Two structural rules, enforced not promised:** no stage may declare a
postgame field as an input (`assert_no_postgame_inputs`, guard-deletion
proved), and a stage with no production model returns `STAGE_NOT_IMPLEMENTED`
rather than a fabricated number.

## 6. Production entrypoint

```
python3.12 -m nfl.production.run_forecast \
    --season 2026 --week 1 --game-id 2026_01_NE_SEA \
    --arm A --written-at 2026-09-09T22:00:00Z --out-dir DIR [--dry-run]
```

`--written-at` is **required**. There is no wall-clock default for a scientific
clock, and a test asserts it.

## 7–9. QB and joint production decisions

**QB (§5B): production uses a shrinkage baseline, and the QB oracle
decomposition was NOT run in this session.** The QB1 audit established what any
decomposition must do first, and it is the part that changes the answer:
`pass_attempt` includes **every sack (5,308/5,308) and every spike (278/278)**,
so `dropbacks = pass_attempts + scrambles − spikes` and the naive form errs by
**5,586 plays**. Scrambles carry `rusher_player_id` on 4,091 of 4,091 and
`passer_player_id` on **zero**. Building a QB model on the naive identity would
have been wrong from the first line. This is recorded as `DEBT-QB-LAYER`, and
the production stage declares itself a baseline rather than a model.

**Joint (§5C): a production baseline, explicitly not a dependence claim.** It
preserves accepted marginals, reconciles team totals **per draw index** (a
mean-level reconciliation leaves individual draws incoherent, which is what a
joint artifact exists to prevent), removes impossible combinations **and counts
them**, and couples players through a shared team volume — a mechanism, not a
fitted correlation. Where dependence is a known open debt (WR1↔RB1, TE1↔RB1,
the 2024 carry rank1↔rank2 anomaly) the coupling is left **neutral**, and
tuning to those anomalies is forbidden. The marginal shift caused by
reconciliation is **measured and returned**, because reconciliation that
cosmetically improves physical validity while degrading marginal calibration is
the documented failure mode.

## 10–11. Dry run and adversarial refusals

`nfl/tests/test_production_pipeline.py` — **68 assertions, 0 failures.** All
ten required cases plus six more, each failing with the **right** code:

| case | refusal |
|---|---|
| normal complete game | **SEALED** |
| game with QB change | **SEALED** |
| player missing identity | `IDENTITY_UNRESOLVED` |
| source timestamp too late | `SOURCE_TOO_LATE` |
| missing raw artifact | `SOURCE_MISSING` |
| changed schema | `SCHEMA_DRIFT` |
| incomplete player set | `IDENTITY_UNRESOLVED` |
| joint reconciliation failure | `JOINT_RECONCILIATION_FAILURE` |
| arm A consuming 2026 outcomes | `ARM_RULE_VIOLATION` |
| artifact rewrite attempt | `ARTIFACT_MUTATED` |
| raw hash mismatch | `RAW_HASH_MISMATCH` |
| unauthorized input | `UNAUTHORIZED_INPUT` |
| cold-start violation | `COLD_START_VIOLATION` |
| model artifact missing / hash mismatch | `MODEL_ARTIFACT_MISSING` / `MODEL_HASH_MISMATCH` |
| stage not implemented | `STAGE_NOT_IMPLEMENTED` |
| written at/after kickoff | `SOURCE_CHRONOLOGY_FAILURE` |

Every dry run is tagged `dry_run: true` and `prospective_eligible: false`.
**A clean, fully sealed run still reports `publication: NFL1_NOT_AUTHORIZED`.**

## 12. Determinism

Same inputs → same `run_id`, same execution identity, **bit-identical
artifact**. Changing **one** input hash, the arm, or the seed changes the
execution identity. All asserted.

## 13. Runtime baseline

| | |
|---|---|
| orchestrator, per game | **3.3 ms** median (3.1–8.3 ms) |
| projected 16-game slate | ~52 ms of orchestration |
| peak RSS | 19.6 MB |
| forecast artifact | 4,671 bytes |
| run status | 4,580 bytes |

**The orchestrator is not the bottleneck — draw generation is.** Measured this
session: the receiving simulator is ~7 s per season-arm at 2,000 draws over
~5,600 player-games; TD1 ran 16 coalitions × 4 seasons in 134 s. The safe
optimization is **caching immutable intermediates by hash**; reducing draws to
hit a speed target is forbidden without recording the scientific effect.

## 14. Release checklist

`nfl/production/RELEASE_CHECKLIST.md`. **15 items GREEN NOW**, 4 BLOCKED BY
G0A, 3 BLOCKED EXTERNAL, 6 NON-BLOCKING RESEARCH DEBT.

## 15. Deployment readiness (§12)

`.github/workflows/nfl-production-forecast.yml` is **built and deliberately not
activated**: **no `schedule:` trigger**, manual dispatch only, tagged
non-prospective. The authorization step runs before any forecast step and exits
neutrally while NFL-1 is unauthorized. The forecast step is **unreachable**
today. Guard-deletion proof: bypassing `may_publish` is what makes an
unauthorized run report as publishable.

## 16. T−90 integration (§13)

The pipeline can consume a legitimate T−90 artifact and verifies event-target
identity, authorized source, `retrieved_at` in window, raw-before-parse, SHA,
anchored workflow identity and coverage obligation. **No proof was manufactured
or simulated. G0A stays 11/12.**

## 17. Remaining hard blockers

1. **The real T−90 capture** — NE @ SEA, kickoff 2026-09-10 00:20 UTC, window
   **22:50 → 00:10 UTC**. Anchored workflow only; a manual dispatch can never
   discharge it.
2. **Owner authorization for NFL-1** — a decision, not a computation.
3. **True routes** and **2026 participation** — external.

## 18. Exact actions the moment G0A reaches 12/12

1. Owner records an authorization at `nfl/NFL1_OWNER_AUTHORIZATION.json` with
   `basis: OWNER_DECISION` and a decision id, and updates
   `PATH_C_STATE.gates.NFL_1`. **Nothing else can flip it.**
2. Re-run `nfl/tests/test_production_pipeline.py` and
   `test_prospective_contract.py`.
3. Dispatch the workflow with `dry_run: false`, a real `--written-at` strictly
   before kickoff, and arm **A** first.
4. Confirm `publication: PUBLICATION_AUTHORIZED` and the artifact seals.
5. Register the artifact under the prospective evaluation protocol. **Week 1 is
   not backfillable** — a forecast not genuinely live before its game never
   becomes eligible.

## 19. Non-blocking research debts

Receiving calibration (`R1` direction promising, missed its bar), receiving
conversion, TD conversion, QB decomposition, joint dependence beyond volume
coupling, the 2024 carry anomaly. **All in
`nfl/TECHNICAL_DEBT_REGISTRY.json`. None blocks shipping a baseline.**

---

**G0A remains 11/12. NFL-1 remains NOT AUTHORIZED. P4C unchanged. ABC_MPR
unchanged and not promoted. No candidate promoted from mined historical
evidence. No 2026 outcomes used. No FTN used. No DFS, props, market or
portfolio work begun.**
