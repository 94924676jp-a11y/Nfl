# DEN@KC rebuild — acceptance record

Run `96954efc523bd7d3`, `V1_CANDIDATE_R9`, cutoff `2026-09-14T23:27:47Z`,
kickoff `2026-09-15T00:15:00Z` (47 minutes), 1,000 draws, seed 20260908,
`dry_run=False`. Commit `f326a6d`.

---

## 1. The headline, and it was not targeted

| Patrick Mahomes | sealed V1 | rebuild |
|---|--:|--:|
| Pass attempts | 20.20 | **34.77** |
| Completions | 13.29 | **22.84** |
| Passing yards | 144.02 | **246.45** |
| P(zero dropbacks) | 0.4120 | **0.0090** |

Nothing in the fitted module refers to a board value, and no floor, clip or
minimum exists in it. The zero mass falls because the starter is *defined* as
the taker of dropback one, which makes `P(dropbacks = 0 | started)` an
identity rather than an estimate.

Bo Nix: 31.71 attempts, 20.42 completions, 213.89 passing yards, P(zero)
0.0080.

## 2. Why the number moved, traced to one fact

`previous_primary_from_panel` records `00-0037324` — Chris Oladokun — as Kansas
City's primary passer in 2025 weeks 16, 17 and 18. Mahomes therefore entered
tonight flagged *not the previous primary*, and `qb3_lib.allocate` draws the
primary's identity and then resamples that man's share from the cell's
**unconditional** pool, 47.35% of which is exactly zero in the (rank 1, not
previous primary) cell. The two steps contradict each other by construction.

Oladokun is `ROSTER_RES` / `EXCLUDED_DETERMINISTIC` and is not playing
tonight. The old board's central claim about Patrick Mahomes rested on a
quarterback who will not be on the field.

## 3. The decomposition — three boards on one cutoff, not two

Five repairs landed today and four of them are not the quarterback room, so a
straight V1-versus-rebuild comparison would have credited the wrong repair.

| arm | configuration | tree | run |
|---|---|---|---|
| V1 sealed | `R8` | pre-repair | `f91342d6787a66a1` |
| Arm A | `R8` | repaired | `a6e6bd223a211d39` |
| Arm B | `R9` | repaired | `d1e2727743c93990` → final `96954efc523bd7d3` |

**Arm A reproduces the sealed board's `qb/db` and `qb/att` to 0.00 on every one
of the six quarterbacks.** Not approximately — exactly. So section 1 is the
allocator alone, and the structural repairs moved no quarterback.

**Team dropbacks are unchanged at 41.49.** Conservation was never the defect.
Mahomes' extra 102 passing yards came from Justin Fields and Garrett
Nussmeier, who were never going to throw them.

## 4. Cohort acceptance — the check that could have failed

Week-1 depth-chart QB1s, 2021–2024: **n = 128, realised zero-dropback games
0/128.**

| arm | n | mean P(zero) | max | ≥ 0.25 |
|---|--:|--:|--:|--:|
| R8, forward-chained | 128 | 0.1982 | 0.456 | 39.8% |
| **R9, forward-chained** | 96 | **0.0278** | **0.137** | **0.0%** |

R9 did not achieve this by shrinking everywhere. On in-season rank-1
not-previous-primary (realised zero rate 0.7315) it assigns **more** than R8 —
0.5441 against 0.3946 — with a better Brier, 0.2381 against 0.3171. Overall
Brier 0.1305 → 0.1148.

**This is EXPLORATORY.** The season-boundary hypothesis was selected on this
same historical panel before the module existed. Forward chaining controls
parameter leakage and says nothing about specification leakage, and freezing a
cohort does not make it a holdout. A confirmatory result needs untouched games.

## 5. Both teams' universes

19 rows on one team → **33 player rows, KC 16 and DEN 17**; draw layers qb 6,
receiving 27, rushing 7, plus `rush_category` and `rush_player_pool` for both
clubs.

Denver was not missing data. The readiness gate could not distinguish "no
designation filed yet" from "the club has stated it has none" — the nflverse
schema spells both the same way — and it deferred exactly
**{DEN, HOU, MIA, MIN, WAS}**, which is precisely the set of clubs carrying an
explicit captured statement. I verified that independently before keeping the
repair: Denver's statement reads *"No injury designations"*, source
`NFL_final_report`, game date 2026-09-14, sha256 `df1dd903…`, retrieved
2026-09-13T12:47:00Z — lawfully before both the cut and kickoff.

The gate was reading **evidence of health as absence of evidence**. The new
state `READY_BY_EXPLICIT_NO_DESIGNATION` is kept distinct from `READY` so the
basis is never lost, and it clears neither `INJURY_REPORT_NOT_YET_FILED` nor
`INJURY_REPORT_STALE` — those are statements about the capture, not the club.

Board rows now carry human-readable names with per-row provenance, resolved
from the weekly-roster blob the board had already opened. **19 of 19 resolved,
0 fallbacks**, all agreeing with the independent eligibility snapshot.

## 6. Quality gates

| | V1 | Arm A | final |
|---|--:|--:|--:|
| hard findings fired | 31 | 28 | **6** |
| rows withheld | 22 | 19 | **0** |
| soft flags | 6 | 6 | 6 |

Cleared: `IDENTITY_DEPTH_ROLE_CONFLICT` 20 → 0, `COUNT_SUPPORT_FAILURE` 3 → 0,
`UNATTRIBUTED_OPPORTUNITY_MASS` 2 → 0, `HEALTHY_QB1_ZERO_OPPORTUNITY_ANOMALY`
1 → 0.

**`board_state` is `WITHHELD` and the active pointer has NOT been moved.** The
rebuild is five times better on this measure and it has not earned
publication. The gate decides that, not me.

## 7. What is still wrong, stated plainly

**`RUSH_ACCOUNTING_FAILURE` × 2 — an arithmetic impossibility, unrepaired.**
149 of 1,000 DEN draws and 148 of 1,000 KC draws deal the named rush owners
MORE carries than the team's own carry level, by up to 6.12 and 9.69
respectively. On the sealed V1 board the KC figure was 390/1,000, so it has
improved 2.6× — and that improvement came from the counts repair, **not** from
the workstream assigned to this defect, which was killed by a rate limit
before it could wire and verify its candidate fix. That code is in the tree
but is **not enabled**, and I did not enable it: pushing an unverified repair
to a production path thirty minutes before kickoff is the failure mode this
process exists to prevent. The family is honestly quarantined.

**`QB_ROOM_SPLIT_ANOMALY` × 2.** Two-passer probability DEN 0.0860 and KC
0.0980 against base rates of 0.078 (weeks 2+) and 0.039 (week 1), realised
0.000 in 2026 week 1. R9 declared this open before the gate found it: 9.8%
against a realised 3.12% is five times better than R8's 48% and still high.
Research, not a patch.

**`ROLE_STATE_SOURCE_CONFLICT` × 2 — blocked, not deferred.** No official
inactive list exists for this game. Every capture attempt today returned
`curl: (56) CONNECT tunnel failed, response 403`, and no attempt has been made
since 17:39Z because the capture executor is halted. The window opened at
22:45Z and closes at 00:05Z and **will close unfilled**. It is recorded as a
miss and will not be backfilled; the request is lodged in
`docs/AGENT_OUTBOX.md`.

**Board finality: `PRELIMINARY_PROVISIONAL`. `FINAL` is not reachable from
this executor** — the ladder is NFL → club → PRELIMINARY and the first two
rungs need bytes from outside this checkout.

**Six soft `DEGENERATE_DISTRIBUTION_WIDTH` flags**, all on backup
quarterbacks whose middle half of draws is identical. Soft flags change no
distribution.

**A finding, not a win: Kansas City's backfield comes out at parity.** Walker
8.233 against Johnson 8.227 carries in Arm A, and in the rebuild the order
reverses. The depth repair removed a real inversion and what replaced it is a
coin flip, produced by the tie mechanism — `depth_team` ties plus little
trailing history give both men the same anchor and therefore the same score —
and not by any evidence that the two backs are equal. It needs a tiebreaker or
an explicit declaration that the model has no view. It should not be read as a
measurement.

## 8. Reproducibility

`determinism_proof.py`, same cutoff, two independent runs:

    PASS[DETERMINISM_PROVEN] 2026_01_DEN_KC: all six properties hold
      PASS identical_predictive_arrays
      PASS identical_candidate_identity
      PASS identical_execution_identity
      PASS identical_model_configuration
      PASS identical_input_hashes
      PASS generated_output_did_not_alter_second_run_identity
      proof_body_sha256 1199b821937cb04d67990e28b8815b838b71031b62588dfc44367222f47a0040

The tool reports `counterfactual_discriminating: False`, which is its own
honesty flag and is repeated here rather than dropped: the proof shows the two
runs agree, and does not demonstrate that it would have detected a
counterfactual difference.

## 9. The sealed V1 board is untouched

`board_pointer.verify_seal` → `PASS SEAL_INTACT`, draws sha256 `53fc6fed…`
recomputed equal to declared, `draw_content_digest` `86e3707d…`. It stays as
prospective evidence and was never rebuilt or overwritten.

## 10. Tests — what ran and what did not

Targeted suites on the final tree, all PASS: `test_qb_room_v2` (14/58),
`test_r5_active_pool` (8/24), `test_refbands` (14/124), `test_v1_rushing_a1`
(27/148), `test_vintage_selector` (24/131), `test_board_row_identity` (9/38),
`test_quality_gates` (253 checks).

**The full 116-module suite was NOT re-run against this final tree.** The last
complete run was against the tree as it stood before the Denver, names and
rush workstreams landed. That is a gap and it is stated rather than papered
over; it must be run before any of this is promoted.

`test_stat_contract` carries one failing check — a frozen count of sealed runs
on disk, which my own new boards moved. The *defect* count it fences did not
move, which is the check that matters: every board built after the counts
repair contributes zero non-integer carry cells. The fence needs re-freezing
with that rationale, and I did not re-freeze it under time pressure.

`test_c1_denominator` (1 check) and `test_q9_live_feature_builder` (5) are
left FAILING on purpose — see the integration record. R3's `depth_vintage`
repair sits inside the Q9 import closure, so the frozen Q9 candidate is no
longer the candidate that was frozen. Re-sealing to match the tree would be
rewriting evidence to make a test green. It needs a new freeze and an owner
ruling.

## 11. Nothing here is a wager

No sportsbook data entered any of this work, no price was consulted, and no
recommendation to stake money is made or implied.
