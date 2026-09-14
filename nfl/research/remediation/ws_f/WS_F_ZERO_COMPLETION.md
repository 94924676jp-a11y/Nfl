# WS-F — zero-by-completion: the scored set was being chosen by the outcome

**CODE CHANGED: YES, and it is EVALUATION-ONLY.** Nothing in this repair moves
a projection, a draw, a probability, a price, a board, a freeze or a ledger
row. The only thing that changes is **which already-produced forecasts get
graded, and against what realised value**. `nfl/production/**`,
`nfl/prospective/**`, every `FREEZE_*.json` and every sealed
`player_draws.npz` are untouched. No sportsbook data was read.

Repo `/home/user/nfl`, branch `claude/nfl-greenfield-architecture-stsxmk`,
baseline HEAD `837d52f`, interpreter `python3.12`.

Files changed by WS-F, and only these:

| path | what |
|---|---|
| `nfl/research/same_day_retrospective.py` | the repair, spec `1.0.0` -> `2.0.0` |
| `nfl/product/model_health.py` | the health contract now asks how rows were selected |
| `nfl/research/model_health/build_health.py` | NEW — the health artifact had no build script |
| `nfl/tests/test_retrospective_zero_completion.py` | NEW — 9 functions, 62 checks |
| `nfl/research/model_health/RETROSPECTIVE_2026-09-14_ZERO_COMPLETED.{csv,summary.json}` | NEW — corrected retrospective |
| `nfl/research/model_health/RETROSPECTIVE_2026-09-14_LEGACY_SELECTION_REPRO.{csv,summary.json}` | NEW — the leak reproduced at matched scope |
| `nfl/research/model_health/MODEL_HEALTH_2026-09-14_ZERO_COMPLETED.json` | NEW — corrected health artifact |
| `nfl/research/model_health/CORRECTIONS.json` | NEW — superseded -> corrected link, with shas |

Read but not edited: `nfl/research/postgame.py`, `nfl/research/shadow/actuals.py`
(WS-G), `nfl/research/market_outcome_audit.py` (unowned — see "handed over").

---

## 1. DEFECT

`nfl/research/same_day_retrospective.py:186-192`, spec `same-day-retrospective/1.0.0`:

```
src = qb.get(pid) if family == 'qb' else rr.get(pid)
if src is None or src.get(field) is None:
    refused.append({... 'reason': 'NO_REALISED_VALUE_FOR_THIS_PLAYER',
                    'detail': '... Not imputed.'})
    continue
```

`actuals.receiving_rushing_actuals` and `actuals.qb_actuals` emit a record only
for a player who recorded at least one target, carry or dropback. In a
**completed** game `src is None` therefore means the realised value **is zero**
— the observation exists and it is 0. The scorer deleted exactly those rows,
and every one of them is a row where the model forecast positive volume and the
player produced nothing: **the over-forecasts**.

This is **selection on the outcome**, not a peeking leak. No future information
entered a forecast. What entered was the decision about *which forecasts to
grade*, taken using a fact — who touched the ball — that did not exist at
forecast time.

Two workstreams found it independently: WS22 §2 (L1) and WS17 §0. Both
reproductions are re-derived here from the repository's own modules and stored
bytes, and both land exactly.

---

## 2. ROOT CAUSE

Two facts were conflated under one condition, `src is None or src.get(field) is None`:

* **a missing PLAYER** — the record does not exist, because no counter was ever
  incremented. In a completed game that is an observed zero.
* **a missing FIELD** — the record exists but does not carry the key. That is a
  broken estimand map and must never become a zero.

`postgame.score_game:552-561` already separates them, in this repository, with
the comment the repair now follows: *"A MISSING FIELD IS A MAPPING BUG. A
MISSING PLAYER IS A ZERO."* 1,676 of 3,230 rows on the live prospective ledger
carry the resulting `ZERO_BY_COMPLETION` basis. The diagnostic scorer regressed
from a correct pattern that already existed twelve files away, and the
regression was defended in its own refusal string ("Not imputed"), which reads
as conservatism. Refusing to impute an unknown is conservative. Deleting a
known zero is selection.

A contributing cause, structural: the old loop asked the **outcome** first and
the **forecast** second. Whether a row is gradable was therefore decided
downstream of the result.

---

## 3. REPAIR

1. **Order reversed.** The draw row is resolved first — `NO_IDENTIFIED_DRAW_ROW`
   is now a refusal on the *forecast* side, decided by what existed pregame.
   Only then is the realised value consulted.
2. **Absence is classified per estimand, from the estimand's own definition,
   with the derivation written down** (`ABSENCE_SEMANTICS`, and two further
   tables for estimands refused upstream and for derived rates). There is **no
   global missing-to-zero conversion**; that would be a second defect wearing
   the first one's clothes. Table in §8.
3. **`ZERO_BY_COMPLETION` is licensed by completion.** `score_seal` now
   requires the caller to hand it the `postgame.game_finality` result and
   raises `ZERO_COMPLETION_WITHOUT_PROVEN_FINALITY` otherwise. In a
   part-published game an absent player is an unknown, not a zero.
4. **A missing field on an existing record is refused by name**
   (`ESTIMAND_FIELD_NOT_IN_ACTUALS`), never zeroed — the Nacua defect
   (74 receiving yards scored as 0) stays fixed.
5. **Every row declares its basis** — `actual_basis` is `OBSERVED` or
   `ZERO_BY_COMPLETION`, `absence_class` carries the classification — and every
   summary declares `outcome_selection_basis`.
6. **The old rule stays reachable and stamps itself.**
   `--legacy-outcome-selection` reproduces the superseded artifacts and writes
   `SELECTED_ON_REALISED_VALUE` plus a leak warning into the output. That is
   how the pre-repair numbers in this report were re-derived rather than quoted.
7. **`--outcome-blob`** scores against an already-stored, hash-verified blob, so
   the correction reproduces without a network and without risk of scoring
   against restated upstream bytes.
8. **Empty and partial outputs are named errors**: `EMPTY_RETROSPECTIVE_RESULT`
   and `RETROSPECTIVE_SCHEMA_INCOMPLETE`.
9. **Clustered standard errors, and no naive one.** `_stats` emits
   game-clustered and player-game-clustered SEs with their cluster counts and a
   stated convention; no naive SE is emitted as a number anywhere.
10. **The health contract now asks how rows were selected.** An undeclared
    selection basis is treated as an outcome-conditional one and blocks ranking
    eligibility.

Spec version moved `1.0.0` -> `2.0.0`, not `1.0.1`: which rows are scored is
part of what the number means, so a `2.0.0` statistic may not be compared with a
`1.0.0` one.

---

## 4. WHY THIS REPAIR

Because the alternative repairs are worse, and one of them is the obvious one.

* **"Just treat missing as zero everywhere"** is wrong. A player with zero
  carries has zero rushing *yards* — a sum over an empty set — but his
  *yards per carry* is 0/0, undefined, and reporting 0 would assert he was
  maximally inefficient when he was never measured. A team with no key in
  `actuals` is a join failure, not a club that ran no plays; zeroing it converts
  a data defect into a realised outcome, which is the same class of error as the
  one being repaired. Hence four classes, not a boolean, and a named refusal for
  anything not derived.
* **"Keep refusing, it is conservative"** is what the defect already claimed to
  be doing. A refusal rule whose trigger is the outcome is not conservative in
  any direction that matters: it is one-sided, and the side it removes is the
  side the model loses on.
* **"Repair it and the PIT and the market path at once"** would have made the
  before/after uninterpretable. Exactly one thing changed. The PIT defect
  (WS22 item 11: `pit_of` seeds an RNG per call and draws one uniform, so every
  row in a run gets the identical u = 0.21444212299020937) is **left unrepaired
  on purpose** and every `pit_mean` published here carries
  `pit_interpretable: false` and a named `pit_defect`. It is handed over, not
  hidden.

The reference implementation was not invented: it is `postgame.py:552-561`,
already live, already carrying 1,676 rows.

---

## 5. PRE-REPAIR FAILURE — reproduced, not quoted

Every number below was re-derived on `python3.12` from the repository's own
modules against stored blob
`nfl/research/postgame/pbp_2026.1415dd98ba7f701a.csv.gz`
(sha256 `1415dd98ba7f701a…`, 1,738 rows, hash re-verified at load).

**Rows deleted by the selection**, by scope:

| scope | games | graded before | graded after | rows restored | share deleted |
|---|---:|---:|---:|---:|---:|
| audit scope (the superseded `SUNDAY_1PM_OUTCOME_AUDIT.json`) | 7 | 268 | 637 | **369** | 57.9% |
| health-artifact QB scope | 8 | 335 | 778 | **443** | 56.9% |
| **primary: every seal-carrying, proven-final game** | 9 | 415 | 925 | **510** | **55.1%** |

The 7-game legacy run returns `n_rows = 268` and seven `n_refused` values
summing to **369**, reproducing the published artifact's own arithmetic exactly,
and reproduces every published cell of its `overall`, `by_metric` and
`by_role_tier` blocks to four decimal places. The 8-game legacy run reproduces
the seven QB rows of `MODEL_HEALTH_2026-09-13.json` cell for cell.

**WS22's three-way split, reproduced (7-game scope, all rows):**

```
KEPT    n=268  mean_signed=-5.7911  MAE=9.2373  CRPS=7.0245  cov50=0.6791
DROPPED n=369  mean_signed=+4.4865  MAE=4.4865  CRPS=1.4908  cov50=0.9946
ALL     n=637  mean_signed=+0.1625  MAE=6.4853  CRPS=3.8189  cov50=0.8619
```

Every dropped row has `mean_signed > 0` and `MAE == mean_signed`, because the
realised value is 0 and the forecast was positive. The deleted set is not
merely correlated with the over-forecasts; it **is** the over-forecasts.

**WS17's 55%, reproduced:** 510 of 925 rows on the 9-game scope; pooled coverage
`0.6434 / 0.8892 / 0.9398` before against WS17's `0.643 / 0.889 / 0.940`, and
`0.8368 / 0.9503 / 0.9730` after against WS17's `0.837 / 0.950 / 0.973`.

**A second defect found while correcting.** `MODEL_HEALTH_2026-09-13.json` mixes
**two game populations**: its four receiving/rushing rows reproduce a 7-game run
(n = 48, 48, 48, 12), its seven QB rows reproduce an 8-game run (n = 18). No
field in the artifact says so, and the artifact had **no build script anywhere
in the repository** — `nfl/product/model_health.py` is imported by nothing. Any
comparison across layers in that file compares different samples.

---

## 6. POST-REPAIR RESULT

### 6.1 Pooled, 9-game primary scope

| stratum | n rows | game clusters | bias | game-clustered z | MAE | CRPS | cov 50/80/90 | above / below |
|---|---:|---:|---:|---:|---:|---:|---|---|
| all rows, before | 415 | 9 | −4.8034 | — | 8.7704 | 6.6860 | 0.6434 / 0.8892 / 0.9398 | 226 / 189 |
| all rows, **after** | 925 | 9 | **−0.0655** | — | 6.0244 | 3.6546 | **0.8368 / 0.9503 / 0.9730** | 635 / 243 |
| ex-QB3-contaminated, before | 268 | 5 | −1.5446 | −1.67 | 6.2840 | 4.7944 | 0.6418 / 0.8881 / 0.9515 | 115 / 153 |
| ex-QB3-contaminated, **after** | 428 | 5 | **+0.0868** | **+0.13** | 4.9888 | 3.2812 | 0.7687 / 0.9299 / 0.9696 | 235 / 153 |
| QB3-contaminated, before | 147 | 9 | −10.7448 | −3.78 | 13.3033 | 10.1348 | 0.6463 / 0.8912 / 0.9184 | 57 / 90 |
| QB3-contaminated, **after** | 497 | 9 | **−0.1966** | −0.22 | 6.9162 | 3.9762 | 0.8954 / 0.9678 / 0.9759 | 400 / 90 |

The `below` counts are **identical before and after** in every stratum. That is
the signature of the defect: no row was removed by the repair, only added, and
every added row is an over-forecast.

### 6.2 Per metric — superseded cell, scope-matched repair, regenerated artifact

`before` is the superseded `MODEL_HEALTH_2026-09-13.json` cell, re-derived at
its own scope (7-game for receiving/rushing, 8-game for QB, as pinned in §5).
`after (selection only)` is the same scope with only the selection rule changed
— the single-change comparison. `@9-game` is the regenerated artifact.

| metric | scope | n before → after | zero rows restored | bias before | bias after (selection only) | bias @9-game | z_game @9 | game clusters |
|---|---|---|---:|---:|---:|---:|---:|---:|
| qb/att | 8 | 18 → 63 | 45 | −7.2284 | **+0.1907** | +0.1909 | +0.33 | 9 |
| qb/cmp | 8 | 18 → 63 | 45 | −5.3504 | **−0.1000** | −0.0953 | −0.29 | 9 |
| qb/db | 8 | 18 → 63 | 45 | −8.3627 | **+0.1425** | +0.1947 | +0.32 | 9 |
| qb/int | 8 | 18 → 63 | 45 | −0.0422 | +0.0478 | +0.0360 | +1.06 | 9 |
| qb/ptd | 8 | 18 → 63 | 45 | −0.4570 | −0.0379 | −0.0352 | −0.47 | 9 |
| qb/pyds | 8 | 18 → 63 | 45 | −69.3754 | **−3.6702** | **−1.7179** | −0.33 | 9 |
| qb/sacks | 8 | 18 → 63 | 45 | −0.5655 | −0.0036 | +0.0502 | +0.63 | 9 |
| receiving/receiving_yards | 7 | 48 → 78 | 30 | −2.5197 | **+1.5045** | +0.8521 | +0.51 | 5 |
| receiving/receptions | 7 | 48 → 78 | 30 | −0.2640 | **+0.1093** | −0.0652 | −0.40 | 5 |
| receiving/targets | 7 | 48 → 78 | 30 | −0.2580 | **+0.2480** | **−0.0744** | −0.28 | 5 |
| rushing/carries | 7 | 12 → 18 | 6 | −2.9086 | −1.3479 | **−1.7775** | **−3.39** | 5 |

Coverage at 50%, same ordering: qb/att 0.5556 → 0.8730 → 0.8592; qb/pyds
0.6111 → 0.8889 → 0.8732; receiving/targets 0.7292 → 0.8333 → 0.8106;
rushing/carries 0.4167 → 0.5000 → 0.5625. **Nine of eleven metrics flip the sign
of their bias.** Coverage rises at every level on every metric.

### 6.3 The three consequences I was asked to confirm or refute

| claim | verdict | my measurement |
|---|---|---|
| targets bias −0.690 → −0.075 | **CONFIRMED exactly** | −0.6893 → −0.0744, n 82 → 132, 5 game clusters, z_game −0.28 |
| qb/pyds −56.1 → −1.72 | **CONFIRMED exactly** | −56.0944 → −1.7179, n 21 → 71, 9 game clusters, z_game −0.33 |
| coverage@50 0.643 → 0.837 | **CONFIRMED exactly** | pooled 0.6434 → 0.8368 (all 925 rows, 9 games) |
| carries is the only surviving bias, −1.777, game-clustered z −3.73 on 5 clusters | **point estimate CONFIRMED exactly; z differs by convention, and my measurement is the one I stand behind** | −1.7775 on n = 32, 5 game clusters. Game-clustered **z = −3.39** under the convention written into `_cluster_se` (CRVE with the G/(G−1) finite-cluster correction). Without the correction −3.79; from the spread of per-game cluster means −3.65. I could not reproduce −3.73 under any of the three. The direction, the magnitude and the conclusion are the same under all of them, and nothing in this report turns on which is used. |

**Carries is indeed the only metric whose bias survives zero-completion.** At
the 9-game scope every other metric has |z_game| ≤ 1.06; carries is −3.39.
WS17 attributes it to the C1 double-subtraction diagnosed in `3f5fc82`; I did
not test that attribution and do not endorse it here.

**This is not an adequacy claim about the other ten metrics.** No equivalence
margin was predeclared, no two-one-sided test was run, and five or nine clusters
from one slate cannot support one. "Its bias no longer reaches |z| = 2" is the
whole claim.

### 6.4 Where the restored rows went — role tiers, 7-game scope

| tier | before | after | restored |
|---|---|---|---:|
| PRIMARY_RECEIVER | n=18, +5.981, 16 above / 2 below | **unchanged** | 0 |
| SECONDARY_RECEIVER | n=36, −1.333, 15 / 21 | **unchanged** | 0 |
| DEPTH_RECEIVER | n=90, **−2.285**, 36 / 54 | n=180, **+0.475**, 114 / 54 | 90 |
| PRIMARY_RUSHER | n=6, −4.172, 1 / 5 | **unchanged** | 0 |
| SECONDARY_RUSHER | n=6, −1.645, 2 / 4 | n=11, **+0.070**, 7 / 4 | 5 |

Every primary played; **the deletions fell entirely on the depth and secondary
tiers**. That is the mechanism behind the audit's "primary over-forecast, depth
under-forecast" contrast, and the contrast does not survive: with the zeros
restored both tiers are over-forecast.

### 6.5 Ranking eligibility

`n_ranking_eligible` is **1 of 11 before and 1 of 11 after**, and it is the same
metric, `receiving/targets`. **The repair did not loosen the gate** — which it
would have, left alone: `COVERAGE_BELOW_NOMINAL` was the only warning on
`rushing/carries` and `qb/pyds` that the corrected numbers clear, because the
warning is one-sided and coverage moved from below nominal to above it. That
those two stay ineligible is due to market-side warnings, not to anything the
repair preserved, so two tightenings were added to the contract:

* `OUTCOME_CONDITIONAL_SELECTION` — an undeclared or outcome-conditional
  selection basis blocks ranking. Applied retroactively this would have made
  **all eleven** metrics ineligible in the superseded artifact.
* `MARKET_STATS_OUTCOME_SELECTED` — fires on the nine metrics carrying market
  columns, because the market grader carries the same leak (see §9).

A warning the rebuild cannot recompute is **carried, not dropped**
(`MARKET_GAP_ANTICALIBRATED` is raised from probability buckets this build has
no input for). A rebuild that silently loosens a gate is worse than no rebuild.

**A residual concern I am flagging rather than deciding:** `receiving/targets`
is ranking-eligible on **5 game clusters from one slate**, and
`MIN_N_FOR_A_WARNING = 8` is applied to a *row* count, not a cluster count. The
health row now publishes `n_game_clusters` beside `n_scored` so the unit is
visible. Changing the threshold to count clusters is a policy decision and is
the coordinator's, not mine.

---

## 7. CLUSTERING

Unit: **GAME** (`game_id`), 9 clusters pooled, 5 for the non-QB layers, which
produced no rows in 4 of the 9 games. Player-game is carried as a second
clustering **and labelled where it degenerates**: within a single metric each
player-game holds exactly one row, so the player-game SE there *is* the naive SE
and is flagged `player_game_clustering_degenerate: true`. It binds only in the
pooled strata, where a quarterback contributes seven rows and a receiver three.

`_stats` emits **no naive SE as a number**, by construction, with the reason
stated on the block. The convention is written out in `_cluster_se`:
`se = sqrt( G/(G−1) · Σ_g ( Σ_{i∈g} (x_i − x̄) )² ) / n`. Fewer than two
clusters returns `None` rather than a naive number wearing a clustered label.

At G = 5 and G = 9 none of these intervals is trustworthy at its nominal level.
The cluster count travels beside every number so that is visible.

---

## 8. METRIC CLASSIFICATION TABLE

Four classes, one per estimand, each derived from the estimand's own definition.
Full derivations are in `ABSENCE_SEMANTICS` in the module and in the summary
artifacts; the reasoning is summarised here.

### Scored estimands

| estimand | class | derivation |
|---|---|---|
| `qb/att` | ZERO_IF_ABSENT | count of throws (pass_attempt rows that are not sacks). The count of an empty set is 0. |
| `qb/cmp` | ZERO_IF_ABSENT | count of completions on throws; bounded by attempts, which are 0. |
| `qb/ptd` | ZERO_IF_ABSENT | count of pass touchdowns on throws. |
| `qb/int` | ZERO_IF_ABSENT | count of interceptions on throws. |
| `qb/sacks` | ZERO_IF_ABSENT | count of sack rows charged to the passer. |
| `qb/db` | ZERO_IF_ABSENT | identity `db = att + sacks + scr` (`actuals.py:154`, enforced `qb_v1.py:267`). All three terms are 0, so the identity gives 0. |
| `qb/pyds` | ZERO_IF_ABSENT | **sum** of passing_yards over the passer's throws. An empty sum is 0 — no division, no rate. Note the asymmetry: a QB who *did* throw has a record, so this branch never fires for him and his zero or negative yardage is read as OBSERVED. |
| `rushing/carries` | ZERO_IF_ABSENT | count of rush_attempt rows with this player as rusher. |
| `receiving/targets` | ZERO_IF_ABSENT | count of pass_attempt rows naming this player as receiver. |
| `receiving/receptions` | ZERO_IF_ABSENT | count of completions on targets; bounded by targets, which are 0. |
| `receiving/receiving_yards` | ZERO_IF_ABSENT | **sum** of receiving_yards over targets. This is the case that looks like it needs a rate and does not: yards *per target* would be undefined, total yards is a sum. |
| `team_volume/team_carries` | **MISSING_IF_ABSENT** | team aggregate. Every completed game has offensive rows for both clubs, so an absent team key is a **join or ingestion failure**, not a club that ran zero plays. Zeroing it would convert a data defect into a realised outcome — the same class of error being repaired. (Not reached: team rows are scored by `postgame.score_game`.) |

### Estimands refused upstream — classified anyway, so the answer is written down

| estimand | class | note |
|---|---|---|
| `rushing/rushing_yards` | ZERO_IF_ABSENT | semantics settled (empty sum), but `NOT_MODELLED` upstream, so there is no forecast to pair with the zero. Classified, not scored. |
| `receiving/receiving_td` | ZERO_IF_ABSENT | semantics settled (count); refused upstream on unreconciled TD attribution. |
| `rushing/rushing_td` | ZERO_IF_ABSENT | as above. |
| `team_volume/team_targets` | MISSING_IF_ABSENT | team aggregate; estimand match also unverified upstream. |
| `team_volume/team_rz_carries` | MISSING_IF_ABSENT | team aggregate. |
| `team_volume/team_off_snaps` | **NOT_APPLICABLE** | a snap count from a different feed, not derivable from play-by-play at all. Absence in `actuals` says nothing about the realised value. |
| `team_volume/team_dropbacks_part` | **NOT_APPLICABLE** | participation-matched count; only a SURROGATE upper bound is computable, so no absence rule applies to the estimand actually forecast. The participation feed is blocked. |

### Derived rates — not forecast today, classified because they are the trap

`derived/yards_per_target`, `derived/catch_rate`, `derived/yards_per_carry`,
`derived/yards_per_attempt`, `derived/completion_rate`,
`derived/yards_per_dropback` — all **MISSING_IF_ABSENT**: a ratio with a
realised denominator leaves 0/0 when there are no events, which is undefined,
not zero. Reporting 0 would assert maximal inefficiency for a player who was
never measured.

`derived/target_share` — **MISSING_IF_ABSENT**, for a different reason: its
denominator *is* observed, so the value would be 0/team_targets = 0, but a share
is only meaningful against a stated denominator and this module does not
forecast one. Left missing rather than computed on the side.

**UNRESOLVED** is not empty as a category: any estimand absent from these tables
is refused at scoring time as `ABSENCE_SEMANTICS_UNRESOLVED` rather than
guessed. A test asserts every reachable estimand is classified, that every class
is one of the four, and that every classification carries a written derivation.

---

## 9. INVALIDATED CONCLUSIONS

Each of these was computed on the outcome-selected subset. Nothing here says the
model is better than was thought; it says these particular statements were not
supported by what they were computed on.

1. **"The model under-forecasts volume."** `SUNDAY_1PM_OUTCOME_AUDIT.json`
   headline `mean_signed_error: -1.1597`, 86 below against 70 above.
   **INVALIDATED.** At matched scope: **+0.4800**, 153 above against the *same*
   86 below. Pooled over all rows the count is 635 above / 243 below. The model
   forecasts roughly the right total and puts too much of it on players who then
   record nothing.

2. **"QB passing yards are 67 yards low, 13 of 16 below actual, consistent with
   the QB3 specification defect."** (`under_over_note_on_qb`.)
   **INVALIDATED as a bias statement.** qb/pyds is **−1.7179** on 71 rows,
   9 game clusters, z_game −0.33. **This does not clear the QB3 problem** — it
   relocates it. The error is in *allocation*, not in the level: WS17 §1
   measures 25.0% of forecast dropback mass sitting on quarterbacks who took
   zero dropbacks. The −67 figure was that allocation error made invisible by
   grading only the quarterbacks who played. The QB3 contamination stratum is
   unchanged and those rows remain non-evidence about the layer.

3. **`RUSHING_ATTEMPT_LEVEL_DEFECT_SUSPECTED`, evidence bullet:** *"the ONLY
   metric with coverage BELOW nominal at both levels (50% → 0.417, 80% →
   0.750). Every other metric is at or above nominal."* **INVALIDATED.**
   Corrected: 0.5625 / 0.8125 at the 9-game scope, both at or above nominal.
   The bullet must be struck. **The classification survives**: the direction
   (−1.7775, z_game −3.39) and the compression evidence (slope 1.3606, sd ratio
   0.6311, essentially unmoved) hold, and `INSUFFICIENT_EVIDENCE` remains the
   right verdict on 5 clusters.

4. **`RECEIVING_COMPRESSION_SUSPECTED`, evidence-against bullet 1:**
   *"PRIMARY_RECEIVER +5.981 with 16 of 18 rows ABOVE actual; DEPTH_RECEIVER
   −2.285 with 54 of 90 below … the primary/depth pattern RUNS THE OTHER WAY."*
   **INVALIDATED.** DEPTH_RECEIVER moves to **+0.475** (114 above / 54 below);
   PRIMARY_RECEIVER is unchanged at +5.981 because every primary played. Both
   tiers are over-forecast and the contrast the bullet rests on does not exist.
   The other two bullets survive: receiving coverage is still at or above
   nominal (more so), and the sd ratios still sit below 1 (targets 0.724 →
   0.694). The verdict `INSUFFICIENT_EVIDENCE` therefore survives on different
   evidence than it was given.

5. **`COVERAGE_BELOW_NOMINAL` on `rushing/carries` and `qb/pyds`.**
   **INVALIDATED** — raised off a statistic the selection created, exactly as
   WS22 predicted. Both metrics remain ranking-ineligible on market-side
   warnings.

6. **`n_refused_rows: 0` on all eleven metrics of
   `MODEL_HEALTH_2026-09-13.json`.** **FALSE.** 369 rows (its receiving/rushing
   scope) and 443 rows (its QB scope) were refused and were invisible in the one
   artifact whose stated job is to expose what the model must be distrusted on.

7. **`receiving/targets` as the single ranking-eligible metric, on
   `coverage_50 = 0.7292`.** The **verdict** survives (0.8106 corrected, still
   eligible) but its **basis is invalidated** — the number it was granted on was
   a property of the selection. See §6.5 for the residual 5-cluster concern.

8. **Any cross-layer comparison inside `MODEL_HEALTH_2026-09-13.json`.**
   **INVALIDATED** on separate grounds: its QB rows and its non-QB rows come
   from different game populations (8 games against 7) and nothing in the file
   said so.

9. **Anything downstream of these diagnostics.** There is nothing.
   `nfl/product/model_health.py` is imported by no module in the repository and
   `assert_ranking_admissible` has no caller, so no published ranking was ever
   filtered by these warnings. `RANKING_ELIGIBLE` in `daily_board.py` is a
   row-level flag from a different source and is untouched. The leak's
   practical damage was to the published health *statement*, not to a live card.

---

## 10. BLAST RADIUS

**Nothing computational.** No projection, draw, probability, price, board,
freeze, ledger row, sample floor or blocker moves. `SIM`-side and production
modules are untouched; `nfl/production/nonqb/layers.py` — hashed by the Q9
freeze — was not opened.

* `nfl/research/same_day_retrospective.py` — diagnostic scorer. Sole consumer of
  its output was the health artifact, regenerated here.
* `nfl/product/model_health.py` — **orphaned**: no importer, no caller. The
  contract change cannot break a consumer because there is none. Both files were
  previously **untested**; they now have 62 checks.
* Baseline artifacts are **byte-identical after this work**, re-verified:
  `MODEL_HEALTH_2026-09-13.json` `4639ff1a0fdcb8a6`,
  `SUNDAY_1PM_OUTCOME_AUDIT.json` `82f706127181238d`. Neither was rewritten;
  `CORRECTIONS.json` carries the superseded → corrected link, both shas, and the
  reason.
* Suite: `python3.12 nfl/tests/run_suite.py --only test_retrospective_zero_completion`
  → 9 test functions, **62 checks, 0 failing, 0 raised**. The full suite was not
  run, per instruction.

### Handed over, not repaired

1. **`nfl/research/market_outcome_audit.py:184-186`** carries the **same leak**:
   `if src is None or src.get(field) is None: … 'NO_REALISED_VALUE', 'not
   imputed'`. A prop on a player who recorded nothing is a graded loss for the
   over side, and dropping it measures the hit rate on survivors. WS-F does not
   own that file and did not touch it. Every carried market column in the
   regenerated health artifact is flagged `MARKET_STATS_OUTCOME_SELECTED`.
   **The patch is the same shape as this one and I will write it on request.**
2. **The PIT defect** (WS22 item 11) is left unrepaired by design, flagged
   `pit_interpretable: false` on every stats block.
3. **`MIN_N_FOR_A_WARNING` counts rows, not clusters** — a policy call for the
   coordinator, flagged not changed.
4. **No patch is owed to WS-G.** `postgame.py` and `shadow/actuals.py` were read
   and are correct on this axis; `postgame.py:552-561` is the pattern this
   repair copied.

---

## 11. IDENTITY IMPACT

* `same-day-retrospective/1.0.0` → **`2.0.0`**. A statistic from one may not be
  compared with a statistic from the other; the selection rule is part of the
  estimand.
* `model-health/1.0.0` is **unchanged as a version string**, but `FIELDS` gained
  four entries and `WARNINGS` gained two. Flagged for the coordinator: if the
  contract version is meant to move with the contract, this is where it moves.
  I did not move it unilaterally because the published artifact quotes it.
* **No freeze, no fingerprint, no parameter hash and no module hashed by
  `Q9_PROSPECTIVE_FREEZE.json` is touched.** `nfl/production/nonqb/layers.py`
  (`481f005f682cd721`) was not opened.
* Outcome bytes are pinned by hash on every row (`outcome_sha256`), and
  `--outcome-blob` re-derives the digest at load rather than trusting the
  provenance file, so the correction reproduces offline and cannot silently
  score against restated upstream bytes.
* Reproduction command for the corrected artifact:

```
python3.12 nfl/research/same_day_retrospective.py \
  --games 2026_01_ATL_PIT,2026_01_BAL_IND,2026_01_BUF_HOU,2026_01_CHI_CAR,\
2026_01_CLE_JAX,2026_01_NO_DET,2026_01_NYJ_TEN,2026_01_SF_LA,2026_01_TB_CIN \
  --outcome-blob nfl/research/postgame/pbp_2026.1415dd98ba7f701a.csv.gz \
  --out nfl/research/model_health/RETROSPECTIVE_2026-09-14_ZERO_COMPLETED.csv

python3.12 nfl/research/model_health/build_health.py \
  --summary nfl/research/model_health/RETROSPECTIVE_2026-09-14_ZERO_COMPLETED.summary.json \
  --rows    nfl/research/model_health/RETROSPECTIVE_2026-09-14_ZERO_COMPLETED.csv \
  --supersedes nfl/research/model_health/MODEL_HEALTH_2026-09-13.json \
  --date 2026-09-14 \
  --out nfl/research/model_health/MODEL_HEALTH_2026-09-14_ZERO_COMPLETED.json
```

Add `--legacy-outcome-selection` to the first command to reproduce the
pre-repair numbers; the output stamps itself as a known leak and is not a
measurement.

---

## 12. WHAT THIS DOES NOT ESTABLISH

One slate. Five or nine game clusters. No predeclared equivalence margin and no
two-one-sided test anywhere in this work. No metric is called unbiased, stable,
closed or correct, and a bias that no longer reaches |z| = 2 on nine clusters
has **not** been shown to be absent. This is a diagnostic: not prospective
evidence, counts toward no sample floor, clears no blocker, and recommends no
wager.

---

## 13. ADDENDUM, 2026-09-14 — three corrections to this report

Appended rather than edited in place, so what this report said when it was
filed stays legible. Each item names the section it supersedes.

**A. §9 item 9 and §10 item 1 — I overstated the market contamination, and I
withdraw it.** I wrote that the carried market columns "are themselves
outcome-selected by `market_outcome_audit.py:184-186`". The leak is real in
that file, but I had not measured whether it fired. It did not. On the frozen
1 PM snapshot **161 quotes reached the realised-value check and all 161 carried
a record, so zero rows were deleted** — confirmed independently by the
published refusal ledger, which contains no `NO_REALISED_VALUE` entry at all.
The provenance criticism stands (the grader could have deleted such rows and
did not declare that it had not); the contamination claim does not. The
published market figures are **not** contaminated by it.

**B. §6.5 — `MARKET_STATS_OUTCOME_SELECTED` no longer fires.** The market
grader is now repaired (spec `market-outcome-audit/2.0.0`) and reproduces the
carried columns cell for cell, so their basis is declared complete with a
written justification that `build_health.py` refuses to run without.
**Ranking eligibility is unchanged at 1 of 11** — no metric was promoted by the
clearing, and an undeclared basis still blocks ranking.

**C. §11 — the `model-health` version is ruled, not open.** Coordinator ruling,
2026-09-14: **`1.0.0` → `1.1.0`**, additive. `FIELDS` gained four entries and
`WARNINGS` gained two; no existing field changed meaning or was removed, so
this is not the `1.0.0 → 2.0.0` break the retrospective spec correctly took,
and leaving it at `1.0.0` would have let a consumer read a different schema
under the same name. `MODEL_HEALTH_2026-09-13.json` still publishes `1.0.0` and
is **not** rewritten; `CORRECTIONS.json` records what changed under that name.

**Also now settled, not open:** the provenance hole in §5 — the two-population
mix and the absent build script — is **recorded and not fixed**, on ruling. An
artifact no code can regenerate is a finding, not a task, and
`build_health.py` builds the *corrected* artifact from one run over one
population rather than reconstructing how the superseded file was made.

The market repair is a **separate commit with its own report**:
`nfl/research/remediation/ws_f/WS_F_MARKET_ZERO_COMPLETION.md`.
