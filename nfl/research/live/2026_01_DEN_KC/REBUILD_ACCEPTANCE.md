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

**The full suite HAS now been run against the final tree** (post-kickoff,
2026-09-15T01:43Z), closing the gap this section previously recorded as open.
117 modules, 1,473 test functions, **8,384 checks, 6 failing** — and the six
are exactly the Q9 governance escalation described below. It went 25 failing
to 6; what the other 19 were, and what they cost, is section 12.

`test_stat_contract` is now green: the fence was re-frozen at 104 runs /
394,000 carry cells with the rationale recorded in the file. The number that
matters did not move — **non-integer carry cells stayed at exactly 243,766**,
and both new boards contribute zero, which is the counts repair working.

`test_c1_denominator` (1 check) and `test_q9_live_feature_builder` (5) are
left FAILING on purpose — see the integration record. R3's `depth_vintage`
repair sits inside the Q9 import closure, so the frozen Q9 candidate is no
longer the candidate that was frozen. Re-sealing to match the tree would be
rewriting evidence to make a test green. It needs a new freeze and an owner
ruling.

## 11. Nothing here is a wager

No sportsbook data entered any of this work, no price was consulted, and no
recommendation to stake money is made or implied.


---

## 12. After kickoff: what the full suite found, and one real defect

The board above is historical now — kickoff was 2026-09-15T00:15Z. This
section records what running the full suite against the final tree turned up,
because three of the findings are about the rebuild itself.

**25 failing checks, reduced to 6.** The six that remain are the Q9
escalation in section 10. The other nineteen fell into four groups.

### 12.1 Conservation was silently unchecked on both new boards

The worst of them, and it was invisible. A1's carry partition now reaches the
artifact as `rush_category` and `rush_player_pool`, both declaring
`row_axis: "team"`. `conservation.team_rows` exempted `team_volume` **by name**
and demanded `gsis_id` of everything else, so every board carrying the new
layers returned `BLOCKED[CONSERVATION_ROW_AXIS_UNKNOWN]` — meaning the
conservation invariant stopped being evaluated at the moment the new layers
arrived, on the DEN@KC boards among others. A refusal is the safe failure and
it is still a failure: nothing announced that the check had stopped running.
Exactly the defect class this repository names as its most expensive — *a step
that returned nothing was read as success.*

Repaired: a team-axis layer joins by team, because its row ids **are** team
codes. An axis the module does not understand is still refused by name. With
conservation actually running, both boards resolve
(`CONSERVATION_ROWS_RESOLVED`) and **exact closure holds at zero failures**.

### 12.2 A pathological draw, registered as D19 rather than absorbed

With the fence live, one new coherence finding appeared: board
`d1e2727743c93990`, Bo Nix, draw 885 — **16 completions on 30 attempts for
−32 passing yards.**

Negative passing yardage is legitimate here and is deliberately not clipped.
Sixteen completions averaging about −2 yards each is not. It is a pathological
tail of the yards-per-completion draw, not the ordinary short-loss completion
the no-clipping policy protects, and the honest move was **not** to widen the
count fence around it. It is filed as **D19** in `OPEN_DEFECTS.json`,
UNDIAGNOSED and UNREPAIRED, and the check is pinned at exactly 1 so a second
one fails. **The fix is not to clip**: it is to find why the draw reaches −32
at 16 completions, after which the count returns to 0 by construction.
Tonight's final board `96954efc523bd7d3` carries no such cell.

### 12.3 L6's scoping repair was built for a defect that did not exist

Eight checks in `test_appearance_team_scope` failed. L6 exists because DEN@KC
deferred Kansas City's thirteen skill players for a gap in Denver's injury
filing. The readiness repair showed that gap was a misreading, so Denver is
READY and **DEN@KC is no longer a mixed game at any lawful clock** — earlier
clocks make both clubs INCOMPLETE or both STALE, never one of each.

The mechanism is still right and still needed; it lost its live example. The
tests now **search the slate** for a genuinely mixed game rather than asserting
one particular game is mixed, and record `blocked()` with a named cause when
none exists. As of today none does: New England and Seattle are the only clubs
still `INJURY_REPORT_INCOMPLETE` and they play each other. The guard itself is
still demonstrated on a real refused pair (NE/SEA defers whole). One test was
renamed — `..._still_refuses_denver` asserted in its own name a fact that had
stopped being true.

### 12.4 Calendar assertions, and the miss

Three checks failed because time passed: `test_preflight` and
`test_discharge_identity` asserted that a week-1 inactives window still lay
ahead. The last one closed at 00:05Z. `test_preflight` had already learned
this lesson once — its own comment reads "THE PROPERTY, NOT THE CALENDAR" —
and the fix had not been applied to the other three functions in the file, so
they raised `StopIteration` on the passage of time. They are now clock-aware:
full assertions when a window is open, `blocked()` with a named cause when not,
and `not_yet_due` is checked for *agreement* with whether a next window exists
rather than pinned to a number.

**The DEN@KC inactives window closed unfilled**, and the obligation ledger now
records it: covered 15, missed 48. **Zero capture attempts were made inside the
window** — the executor is halted, and the last attempt of any kind was 17:39Z
returning proxy 403. It is not backfilled. Bytes fetched now would be
post-kickoff and could not have informed a pregame board; writing them in
afterwards would convert a real miss into a fake capture.

### 12.5 Corpus fences re-frozen, with every delta attributed

Four fences count artifacts on disk and moved because two boards were added.
Each was re-frozen with its measurement recorded in the file, and in every case
the number that matters held:

| fence | corpus | the defect count |
|---|---|---|
| `test_stat_contract` | 102→104 runs | non-integer carry cells **243,766 → 243,766** |
| `test_draw_coherence` | 102→104 runs | every violation count **unchanged** |
| `test_conservation` | 204→208 team-runs | **closure failures 0 → 0** |

On conservation I predicted the breaching-game count would rise by one and
**the fence rejected my re-freeze and printed the nine games**: DEN@KC was
already breaching, so the new boards add breaching team-runs inside a game that
was already breaching. The wrong prediction is left in the file next to the
correction, because a re-freeze that quietly absorbs a bad guess is the exact
failure the fence exists to catch.

The new boards' contribution to the QB-rush containment breach is **1 violating
cell per board in 1,000 draws**, against a corpus rate near 6 per breaching
team-run — milder than the corpus, still a breach, still open, and still the
same defect the product gate reports as `RUSH_ACCOUNTING_FAILURE` whose repair
was written but never wired or verified and is therefore not enabled.
