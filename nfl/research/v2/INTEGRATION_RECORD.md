# DEN@KC rebuild — integration record

**Coordinator.** Cutoff `2026-09-14T20:58:33Z`, kickoff `2026-09-15T00:15:00Z`,
1,000 draws, seed 20260908, `dry_run=False`.

---

## 1. Three boards, one cutoff, and why there are three

| arm | configuration | tree | run id | path |
|---|---|---|---|---|
| **V1 sealed** | `V1_CANDIDATE_R8` | pre-repair | `f91342d6787a66a1` | `nfl/research/live/2026_01_DEN_KC/PRELIMINARY_PROVISIONAL_V1_CANDIDATE_R8/` |
| **Arm A** | `V1_CANDIDATE_R8` | repaired | `a6e6bd223a211d39` | `nfl/research/v2/integration/ARM_A_R8_REPAIRED_TREE/` |
| **Arm B** | `V1_CANDIDATE_R9` | repaired | `d1e2727743c93990` | `nfl/research/live/2026_01_DEN_KC/PRELIMINARY_PROVISIONAL_V1_CANDIDATE_R9/` |

Arm A exists because without it the comparison is uninterpretable. Five repairs
landed today and four of them (R2's eligibility gate, R3's depth ordering, R4's
counts and categories, the R6-CLOCK repair) are not the quarterback room. Had I
built only V1-versus-R9, every number would carry all five changes at once and
the headline could have been claimed for the wrong repair. Arm A holds the
configuration constant and moves only the tree; Arm B holds the tree constant
and moves only the allocator. **V1 → A is the structural repairs. A → B is the
quarterback room, alone.**

`V1_CANDIDATE_R9` is a NEW registered mode in `candidate_mode.py`, not an edit
to R8. R8's flags, components and identity are untouched and still resolve.

**The sealed V1 board is byte-identical.** `board_pointer.verify_seal` returns
`PASS SEAL_INTACT`, draws sha256 `53fc6fed…` recomputed equal to declared,
`draw_content_digest` `86e3707d…`.

## 2. What the decomposition shows

**The quarterback change is entirely R9's.** Arm A reproduces the sealed
board's `qb/db` and `qb/att` to **0.00 on every one of the six quarterbacks**.
Not approximately: exactly. So none of the structural repairs moved a
quarterback, and the table below is the allocator and nothing else.

| KC | V1 & Arm A | Arm B | |
|---|--:|--:|---|
| Mahomes P(zero dropbacks) | 0.4120 | **0.0090** | |
| Mahomes dropbacks | 22.82 | **39.16** | +16.34 |
| Mahomes attempts | 20.20 | **34.77** | +14.56 |
| Mahomes completions | 13.29 | **22.77** | +9.48 |
| Mahomes passing yards | 144.02 | **245.27** | +101.25 |
| Fields dropbacks | 13.20 | 1.72 | −11.48 |
| Nussmeier dropbacks | 5.47 | 0.61 | −4.86 |
| Nix P(zero dropbacks) | 0.0480 | **0.0080** | |
| Nix dropbacks | 34.06 | 35.32 | +1.26 |

**The team totals are unchanged.** KC's three quarterbacks held 41.49 dropbacks
before and 41.49 after. Conservation was never the defect — the *identity* of
who held the ball was. That is worth saying precisely, because a reader seeing
Mahomes gain 101 passing yards will reasonably ask where they came from, and
the answer is: from Justin Fields and Garrett Nussmeier, who were never going
to throw them.

**And the root cause, traced to a single fact.** `previous_primary_from_panel`
records `00-0037324` — Chris Oladokun — as KC's primary passer in 2025 weeks
16, 17 and 18. Mahomes therefore entered tonight flagged *not the previous
primary*, which places him in a cell whose unconditional pool is 47.35% zeros.
R8 gave a healthy depth-chart QB1 a 41% chance of never taking a snap because
the model's reference point for Kansas City was a quarterback who is on
injured reserve and is not playing tonight. Oladokun is `ROSTER_RES` /
`EXCLUDED_DETERMINISTIC` in R2's snapshot, and R1's `legal_room` removes him
from the room entirely — but the *feature* built from him survived, because it
is a fact about last season, not about tonight's roster.

**The structural repairs, V1 → Arm A.** No quarterback moved. The receivers
and backs did:

| | V1 | Arm A | Arm B |
|---|--:|--:|--:|
| Kenneth Walker III, carries | 10.918 | 8.233 | 8.345 |
| Emmett Johnson, carries | 5.287 | 8.227 | 8.420 |
| Brashard Smith, carries | 3.314 | 3.034 | 3.052 |
| Cyrus Allen, targets | 1.85 | 3.52 | 3.61 |
| Rashee Rice, targets | 8.49 | 7.68 | 7.96 |

This is R3's depth repair landing. It also produces a result worth flagging
rather than celebrating: **Kansas City's two lead backs come out at parity** —
8.233 against 8.227 in Arm A, and in Arm B the order actually reverses, 8.345
against 8.420. R3 reported that the KC backfield inversion "IS the defect and
the repair removes it", and it does; but what replaces it is a coin flip
between Walker and Johnson, which is a strong football claim about a committee
and is a consequence of the tie mechanism, not of any evidence that the two
are equal. `depth_team` ties (2,396 of 2,432 WR rooms carry 2–4 players tied
at rank 1) plus little or no trailing history gives both men the same anchor
and therefore the same score, and the residual difference is Monte Carlo
noise. **This needs a tiebreaker or an explicit declaration that the model has
no view. It should not ship as though it were a measurement.**

## 3. Suite

`python3.12 nfl/tests/run_suite.py` on the integrated tree: 116 modules, 1,459
test functions, 8,326 checks. Four modules failed; two were real and are fixed,
two are a governance escalation and are NOT fixed.

**Fixed — `test_r5_active_pool` (2 checks).** My eligibility-gate patch grew the
`active_roster_only` branch from 900 to 2,580 characters, and the test sliced a
fixed `src[i:i+900]` window. Both refusal assertions fell off the end of the
window while every line they looked for was still present and still correct a
few hundred characters below. The window is now sliced to the branch's own last
statement, and I added checks that the gate's `snapshot` refusal is also fatal
and that `RS.active_pool(nonqb` is gone. 8 functions, 24 checks, PASS.

**Fixed — `test_refbands` (1 check).** The invariant "no projection path can
reach a band" was implemented as a text grep for `refbands` over
`nfl/production` and `nfl/product`. It caught `stat_contract.py` for a
**docstring** citing `REFERENCE_BANDS.json` as the source of a measured 2.4356
per-QB1 gap — a sentence whose whole purpose is to warn a reader off comparing
a forecast against a band built on the other definition of a pass attempt. The
test was penalising its own documentation, and the cheapest way to go green
would have been to delete the warning. It now parses the AST for imports,
attribute access and non-docstring string constants. Verified against seeded
violations: an import, a path literal and an attribute reach are all caught; a
docstring mention is not. 14 functions, 124 checks, PASS.

**NOT fixed, and deliberately — `test_c1_denominator` (1) and
`test_q9_live_feature_builder` (5).** See section 4.

## 4. ESCALATION — the Q9 frozen candidate is no longer the candidate that was frozen

I asked an agent to find out why `coefficient_sha16` had moved, stating my
hypothesis that it was non-determinism in the fit. **The hypothesis was wrong
and so was the diagnosis I had accepted from R4.**

- It is not non-determinism. `fitted_parameter_hashes` returns the identical
  hash across two in-process calls and separate processes at `OMP`/`OPENBLAS`/
  `MKL_NUM_THREADS` of 1, 2, 4 and default. `stage_a.fit_logistic` is
  fixed-step gradient descent from a zero init over exactly 300 iterations with
  no RNG and no convergence test.
- The cause is **R3's repair to `depth_vintage.py`**, which *is* in the Q9
  import closure via `q6.frame → appearance_r7/r8 → depth_vintage`. Substituting
  HEAD's `depth_vintage` back into `sys.modules` and changing nothing else
  reproduces the sealed hash exactly. R4 was right about `depth_vintage`; R4
  and I were both wrong that `qb_allocation.py` or `role_prior.py` were
  implicated — neither is in the closure.
- **My "exactly one field differs" was an artifact of the seal.**
  `SEALED_FORECAST.json` records only 10 of the 17 identity fields, and
  `standardiser_sha16` is not among them, so it could not have been compared.
  Against the committed `Q9_PROSPECTIVE_CANDIDATE.json`, which records all 17,
  **three** fitted blocks moved — coefficients, standardiser and class prior —
  and `n_training_rows` fell 50,965 → 50,924. My inference that identical
  inputs were producing different weights does not survive.

Magnitude, season 2024, 22,815 rows matched row-for-row: the three depth
columns and the three role columns move and nothing else does; `rank_r1` mean
0.2388 → 0.4291; **52.21% of rows change at least one depth feature**; the
outcome `y` is identical on every single row, so this is a feature change and
not an outcome change. `‖dw‖/‖w‖ = 0.0664` and the `rank_r23` coefficient
**changes sign**. Fitted `P(targeted | appears)` has correlation 0.9916 and an
unchanged mean to five decimals, but individual players move by up to **30
percentage points**.

**Why the board may still be built.** Nothing under `nfl/production` or
`nfl/product` imports `q9shadow`, `research.q9` or anything named `hurdle` —
zero grep matches. Q9 is shadow-only in fact, not merely by declaration, and
the hashes that moved are consumed only by the shadow ledger.

**Why it is an escalation and not a fix.** R3's repair makes the frozen Q9
candidate a *different* candidate, which needs a new freeze and new dry-run
seals. Re-sealing the artifact to match the current tree is the one move that
is forbidden: it would be rewriting evidence to make a test green. Leaving
the checks failing is the correct state until an owner ruling. **They are
reported as failures, not as noise, and the board is not claimed to pass a
green suite.**

Read the reverse direction too, because it is the useful one: the check did its
job. It is the only thing in the tree holding a sealed hash of a fit built on
those features, and it detected a production-path input change that nothing
else noticed.

## 5. Quality gates — the rebuild is better and still WITHHELD

`quality_gates.evaluate`, hard findings fired:

| gate | V1 | Arm A | Arm B |
|---|--:|--:|--:|
| `IDENTITY_DEPTH_ROLE_CONFLICT` | 20 | 20 | 20 |
| `COUNT_SUPPORT_FAILURE` | 3 | 0 | **0** |
| `QB_ROOM_SPLIT_ANOMALY` | 2 | 2 | 2 |
| `ROLE_STATE_SOURCE_CONFLICT` | 2 | 2 | 2 |
| `UNATTRIBUTED_OPPORTUNITY_MASS` | 2 | 2 | 2 |
| `HEALTHY_QB1_ZERO_OPPORTUNITY_ANOMALY` | 1 | 1 | **0** |
| `RUSH_ACCOUNTING_FAILURE` | 1 | 1 | 1 |
| **total hard fired** | **31** | **28** | **27** |
| rows withheld | 22 | 19 | 19 |
| soft flags | 6 | 6 | 5 |

Two gates cleared: R4's counts repair closed `COUNT_SUPPORT_FAILURE`, and R9's
room closed the healthy-QB1 anomaly that was this whole exercise's headline.

**`board_state` is `WITHHELD` on all three.** The rebuild is materially better
and it has not earned the pointer. It will not get it on my say-so; the gate
decides, and the gate currently says no.

## 6. What is left, and who has it

- **`IDENTITY_DEPTH_ROLE_CONFLICT` × 20** — every row renders a `gsis_id`
  where a person belongs. `names.py` exists and the board never calls it; the
  reduced roster vintage drops `full_name`. 20 of 27 findings and a pure
  product defect. **Assigned.**
- **`UNATTRIBUTED_OPPORTUNITY_MASS` × 2** — Denver publishes a 27.55 carry
  pool and a 33.75 target pool and seals **zero** Denver player rows. 19 rows
  against an intended 33, all 14 missing are DEN. **Assigned, diagnose-first:
  a genuine data gap and a correct refusal is an acceptable answer; inventing
  14 Denver players is not.**
- **`RUSH_ACCOUNTING_FAILURE` × 1** — 149 of 1,000 draws deal KC's named rush
  owners more carries than the team's own level, by up to 9.69. Was 390/1,000
  on V1, so a 2.6× improvement that is still an arithmetic impossibility.
  **Assigned, with no clipping permitted.**
- **`QB_ROOM_SPLIT_ANOMALY` × 2** — two-passer probability DEN 0.0860, KC
  0.0980 against base rates of 0.078 (weeks 2+) and 0.039 (week 1). R1
  declared this open before I found it: 9.8% against a realised 3.12%, five
  times better than R8's 48% and still high. Research, not tonight.
- **`ROLE_STATE_SOURCE_CONFLICT` × 2** — no official inactive list has been
  ingested. **Blocked on egress and not fixable here**; see section 7.

## 7. The inactives did NOT arrive, contrary to what I was told

R4 reported that its re-run "carries `official_inactives` and
`official_injury_report` hashes that the sealed run did not have" and I nearly
repeated that as "the inactives landed". They have not. Every capture attempt
in `nfl/vintage_manifest.jsonl`, including `20260914T161625Z` and
`20260914T173936Z` today, returns `BLOCKED` / `NO_EGRESS`:

> `curl: (56) CONNECT tunnel failed, response 403` … `targets: []`

What R4 saw were the recorded *failed* attempts appearing in
`capture_validation`, which is the capture discipline working — bytes are
refused, the refusal is stored, and nothing is stubbed. The DEN@KC inactives
window opens at about T−90, i.e. ≈ `2026-09-14T22:45Z`, and this executor has
no egress to reach it.

**The board is therefore `PRELIMINARY_PROVISIONAL` and `FINAL` is not
reachable from here.** Per the owner's first ruling the escalation ladder is
NFL → club → PRELIMINARY, and we are at PRELIMINARY because the first two rungs
need bytes from outside this checkout.

## 8. Operational — a 20 GB temp leak took the machine down mid-integration

`appearance_model.stage_inputs` (`nfl/production/nonqb/appearance_model.py:84`)
calls `tempfile.mkdtemp(prefix='nfl-appearance-')` once per process and never
removes the directory. 617 of them, 33 MB each, filled the disk to 100% with
1.5 MB free. It stopped an agent's measurements and invalidated a full suite
run that was in flight; that run was discarded and re-run from scratch rather
than reported.

Cleared 593 directories older than an hour with the owner's approval, leaving
the recent ones in case a live process held them — 20 GB recovered, 48% used.
**The leak itself is NOT repaired.** The right fix is a content-addressed
staging directory, which is safe because every staged leaf is already hash-
checked against a manifest, so reuse cannot change what is computed. It is
recorded here rather than bundled into tonight's changes.
