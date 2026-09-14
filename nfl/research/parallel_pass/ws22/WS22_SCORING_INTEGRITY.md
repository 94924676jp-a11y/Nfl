# WS22 — Postgame scoring path: evaluation-integrity audit

CODE CHANGED: NO. Repo HEAD 57d38ad. Every figure below was re-derived by
running the repository's own modules against its own stored artifacts on
python3.12. Nothing was fitted, tuned, promoted or written outside this file.
No sportsbook data was used.

Scope: `nfl/research/postgame.py`, `nfl/research/shadow/actuals.py`,
`nfl/research/shadow/score.py`, `nfl/research/shadow/ledger.py`,
`nfl/research/sealed_index.py`, `nfl/research/same_day_retrospective.py`,
`nfl/product/model_health.py`.

---

## 1. Verdict table

| # | Item | Verdict | Basis |
|---|---|---|---|
| 1 | Outcome timestamps | **PARTIAL** | Only a RETRIEVAL clock is asserted and the provenance says so in words (`postgame.py:203-206`). But `shadow/score.py:286` writes the literal `'outcome_downloaded_before_forecast': True` — a hardcoded claim, not a check — and it is now frozen into `shadow/g1_ne_sea/EVALUATION.json:5309`. |
| 2 | Outcome source and authority | **CONFIRMED** | One scoreable source, rank 1, nflverse pbp (`postgame.py:86-99`). Rank 9 transcription is `scoreable: False`. Content-addressed blob + sibling provenance; `stored_outcome` re-hashes the bytes rather than trusting the provenance file (`postgame.py:236-244`). Fetch failure returns BLOCKED and scores nothing. |
| 3 | Identity matching | **PARTIAL** | `identity_of` (`postgame.py:443-476`) carries forecast_id / candidate / cutoff / run_id / outcome_hash / namespace — genuinely sufficient to count a unit. Two gaps: (a) a team-code join failure is a **silent `continue`** with no named refusal (`postgame.py:586-589`); (b) `_row_key` (`postgame.py:920-927`) omits `arm` while `VERSION_IDENTITY` (`postgame.py:815`) includes it, so if two arms were ever written through `append_rows` the second would be silently deduplicated away. Latent only — Q9 writes its own ledger (`nfl/prospective/q9shadow/ledger.py:66`). |
| 4 | Player join | **CONFIRMED** | gsis_id throughout; draw row recovered by position in `manifest.layers[<layer>].row_ids` (`postgame.py:414-424`). `names()` is read from the outcome AFTER the seal and used for display only (`actuals.py:236-246`). |
| 5 | Team join | **FALSIFIED for the QB-room path** | See leakage L2 below. Team-volume rows join on `posteam`, which is correct; the **qb_room** aggregate derives team membership from realised play-by-play. |
| 6 | DNP handling | **CONFIRMED in `postgame.py`, FALSIFIED in `same_day_retrospective.py`** | `postgame.score_game:557-561` maps an absent player to `0.0 / ZERO_BY_COMPLETION` — verified live: 1,676 of 3,230 ledger rows carry that basis. `same_day_retrospective.py:186-192` does the opposite. See leakage L1. |
| 7 | Inactive handling | **FALSIFIED (absent)** | No scorer reads an inactives feed. `cutoff_regime` PRE/POST_INACTIVES is carried on the row (`sealed_index.py:118-122`) so the two are never pooled, but a declared-inactive player and a healthy player who simply never touched the ball are handled identically. Measured over the 127 discovered seals: 60 PRE, 45 POST, 22 UNLABELLED. |
| 8 | Missing-forecast handling | **PARTIAL** | `NO_FORECAST_MISSING_PREGAME_INPUT` is generated (`postgame.py:547-550`) but only `o.value['scored']` reaches the ledger (`postgame.py:1042`). Per-row detail of missing forecasts and of refused estimands is **never persisted** — only a per-(game, seal) count survives in `POSTGAME_STATUS.json`. |
| 9 | Missing-outcome handling | **CONFIRMED** | `OUTCOME_NOT_YET_PUBLISHED` deferred, not refused, not zeroed (`postgame.py:1015-1021`). `actuals.load` raises `OUTCOME_EMPTY` on an empty read rather than returning a zero game (`actuals.py:55-60`). |
| 10 | CRPS | **CONFIRMED** | Two independent implementations, both exact, both agreeing. `shadow/score.py:crps` uses `E|X-y| - sum_i x_i(2i-n+1)/n^2`; `same_day_retrospective.crps_sample` uses the 1-based form `t1 - sum(2i-n-1)x_i/n^2`. Algebraically identical and equal to the standard empirical CRPS. Neither resamples. Both refuse a 9-percentile input by construction (`postgame.py:521-525`, `same_day_retrospective.py:154-158`). |
| 11 | PIT | **FALSIFIED for `same_day_retrospective`; CONFIRMED for `postgame`** | `postgame` uses `shadow/score.pit` — an honest non-randomised bracket `{F_below, F_at_or_below, mid_pit, p_mass_at_actual}`. `same_day_retrospective.pit_of:90` constructs `np.random.default_rng(20260913)` **inside the function** and draws one uniform, so **every row in the whole run receives the identical u = 0.21444212299020937**. Verified: `pit_of(d,2)` returns 0.36907368716503486 on every call. That is not randomisation, it is a constant shift of −0.2856 × (atom mass) applied to every PIT. `pit_mean = 0.5749` in `SUNDAY_1PM_OUTCOME_AUDIT.json` is a biased statistic and the PIT quartiles are not interpretable. The two scorers also use different PIT definitions and their PIT numbers must never be compared. |
| 12 | Interval coverage | **PARTIAL** | Computed per row from stored draws at 50/80/90 (and 95 in `postgame`). Endpoints come from `np.quantile`/`np.percentile` with linear interpolation on a **discrete count** sample, so nominal levels are approximate for low-count metrics; no equivalence margin or test is declared anywhere, and none of the artifacts claims one. |
| 13 | Bias | **CONFIRMED as a definition, CONTAMINATED as a number** | `bias = mean(draws) - actual` and `error_actual_minus_mean = actual - mean(draws)` are both stamped (`postgame.py:433-436`). The bias figures published in `SUNDAY_1PM_OUTCOME_AUDIT.json` and `MODEL_HEALTH_2026-09-13.json` are computed on an outcome-conditional subset — see L1; their **signs flip** when the subset is corrected. |
| 14 | MODEL_MISS / EVENT_SHOCK / DATA_LIMITATION classification | **PARTIAL — it exists, and it is NOT WIRED INTO THE SCORING PATH** | A taxonomy with exactly these three concepts lives in `nfl/research/shadow/ledger.py:113-127`: `MODEL_MISS`, `IN_GAME_STATE_CHANGE` / `IN_GAME_ROLE_CHANGE_NO_INJURY_RECORDED` (the event-shock class), `NO_FORECAST_MISSING_PREGAME_INPUT` and `NOT_CLASSIFIED_SURROGATE_ACTUAL` (the data-limitation classes). **Nothing imports it except `nfl/tests/test_shadow_evaluation.py:23`.** `postgame.py` imports `shadow.actuals` and `shadow.score` and not `shadow.ledger`. So: **no row on `PROSPECTIVE_LEDGER.jsonl` carries any MODEL_MISS / EVENT_SHOCK / DATA_LIMITATION verdict, and `same_day_retrospective.py` emits none either.** `postgame.qb_room_aggregate` carries a single hand-rolled substitute, `in_game_replacement` + `IN_GAME_REPLACEMENT_NOT_PREGAME_ALLOCATION` (`postgame.py:695-707`), which covers QB replacement only. Note also that `MODEL_MISS` is defined by `covered90`, i.e. by the realised outcome; it is a per-row label, and stratifying on it would itself be outcome-conditioning. |
| 15 | Estimand matching — exact-only, refuse the rest by name | **CONFIRMED** | 12 exact estimands (`postgame.py:101-118`); 7 refusals by name with a reason string attached to every row (`postgame.py:121-147`). `actuals.team_actuals` labels `team_off_snaps` and `team_dropbacks_part` `SURROGATE` with the relation stated (`actuals.py:92-105`). Both surrogates are in `REFUSED_ESTIMANDS`. Team rows additionally re-check `got['basis'] != 'EXACT'` at scoring time (`postgame.py:590-594`), so the refusal does not depend on the constant list staying in sync. Live ledger: all 3,230 rows carry `estimand == 'EXACT'`; 12 distinct metrics; **no row scores a forecast of one quantity against a realisation of another.** `shadow/score.py:196-204` independently strips `crps`/`pit`/`coverage` from any SURROGATE row. |
| 16 | Accounting — 3,230 rows, no admissibility verdict, no evidence unit | **CONFIRMED, exactly** | See §3. |
| 17 | Units reported separately; a row count can never be a sample size | **CONFIRMED** | `EVIDENCE_UNITS` (`postgame.py:718-738`), `FLOOR_UNIT = 'distinct_games'`, `PAIRED_NOTE`, and `prospective_sample_size` carries `unit: 'GAME'` with the note that `scoring_rows` is not that number (`postgame.py:790-795`). Enforced by `test_postgame_guards` tests d, e, f, g. |
| 18 | Finality — five signals, all fire; in-progress yields zero rows; OT handled | **CONFIRMED** | See §4. |

---

## 2. LEAKAGE FOUND

### L1 — `same_day_retrospective.py:186-192` drops every row whose realised value is zero (SEVERE)

```
src = qb.get(pid) if family == 'qb' else rr.get(pid)
if src is None or src.get(field) is None:
    refused.append({... 'reason': 'NO_REALISED_VALUE_FOR_THIS_PLAYER',
                    'detail': 'the player has no row in the authoritative
                               play-by-play for this estimand. Not imputed.'})
    continue
```

`actuals.receiving_rushing_actuals` and `actuals.qb_actuals` return a record
only for a player who recorded at least one target, carry or pass. So
`src is None` means **the player's realised value is zero** — the game is
complete, the observation exists, and it is 0. The scorer deletes exactly
those rows.

This is the defect `postgame.py:552-561` was written to fix, in the same
repository, quoted in its own comment: *"A MISSING FIELD IS A MAPPING BUG. A
MISSING PLAYER IS A ZERO."* The diagnostic scorer reintroduces it under the
banner of conservatism ("Not imputed"). Refusing to impute an unknown is
conservative; deleting a known zero is selection on the outcome.

It is a *selection* leak, not a peeking leak: the evaluator decides **which
forecasts to grade** using information (who touched the ball) that did not
exist at forecast time. Every deleted row is a row where the model forecast
positive volume and got nothing — the over-forecasts.

**Reproduction** (re-ran the module's own logic over the 7 seals named in
`nfl/research/SUNDAY_1PM_OUTCOME_AUDIT.json`, against
`nfl/research/postgame/pbp_2026.1415dd98ba7f701a.csv.gz`):

```
KEPT   (what the code scores)  n= 268  mean_signed= -5.7911  MAE=9.2373  CRPS=7.0245  cov50=0.679  above=113 below=155
DROPPED(realised zero)         n= 369  mean_signed= +4.4865  MAE=4.4865  CRPS=1.4908  cov50=0.995  above=356 below=  0
ALL    (zero-by-completion)    n= 637  mean_signed= +0.1625  MAE=6.4853  CRPS=3.8189  cov50=0.862  above=469 below=155
```

`n=268` and `n_refused=369` reproduce the published artifact's `n_rows: 268`
and its seven `n_refused` values summing to 369 **exactly**, so this is the
artifact's own arithmetic, not a re-implementation.

Per metric, kept-subset versus zero-restored:

```
metric                       n_kept  cov50_k  n_all cov50_all   bias_k  bias_all
qb/att                           16   0.6250     55    0.8909   -5.823    +0.759
qb/cmp                           16   0.7500     55    0.9273   -4.617    +0.207
qb/db                            16   0.6875     55    0.9091   -6.950    +0.730
qb/int                           16   0.8125     55    0.9455   +0.005    +0.068
qb/ptd                           16   0.8125     55    0.9455   -0.375    -0.009
qb/pyds                          16   0.6250     55    0.8909  -67.413    -2.093
qb/sacks                         16   0.8125     55    0.9455   -0.522    +0.020
receiving/receiving_yards        48   0.5833     78    0.7436   -2.520    +1.505
receiving/receptions             48   0.6667     78    0.7949   -0.264    +0.109
receiving/targets                48   0.7292     78    0.8333   -0.258    +0.248
rushing/carries                  12   0.4167     18    0.5000   -2.909    -1.348
```

The receiving and rushing `n_kept` / `cov50_k` columns match
`MODEL_HEALTH_2026-09-13.json` cell for cell (48/0.5833, 48/0.6667,
48/0.7292, 12/0.4167), confirming the health artifact is built on the leaked
subset.

**What it manufactures.** The published headline —
`mean_signed_error: -1.1597`, `n_model_below_actual: 86` against
`n_model_above_actual: 70` — reads as "the model under-forecasts". With the
realised zeros restored the sign reverses on 9 of 11 metrics and the pooled
count becomes 469 above versus 155 below. `qb/pyds` moves from −67.4 to −2.1.
Coverage moves from below-nominal to above-nominal on every metric, which
means the `COVERAGE_BELOW_NOMINAL` warning in `model_health.py:78-81` is
being raised off a statistic the selection created.

**Secondary damage.** `MODEL_HEALTH_2026-09-13.json` reports
`n_refused_rows: 0` for all 11 metrics. The 369 dropped rows are invisible in
the artifact whose stated job is to expose what the model must be distrusted
on. And `receiving/targets` is the **single** `ranking_eligible: true` metric
in that file, on `cov50 = 0.7292` drawn from the leaked subset.

**Not a leak:** the module's role-tier claim. `role_tiers`
(`same_day_retrospective.py:104-130`) reads
`board['players'][*]['metrics'][metric]['mean']` — the forecast's own
projected targets / carries — sorts descending within club, and assigns
PRIMARY / SECONDARY / DEPTH by rank. No realised quantity enters. **The
docstring's claim is CONFIRMED in code.** But the `by_role_tier` table is
still computed over the L1-filtered rows, so the strata are clean and their
contents are not.

### L2 — `postgame.py:677-681` assigns QB-room membership from the realised play-by-play (MODERATE)

```
def _team_of(rows, pid):
    for r in rows:
        if r.get('passer_player_id') == pid:
            return r.get('posteam')
    return None
```

called at `postgame.py:644`:
`by_team[_team_of(rows, pid) or 'UNKNOWN'].append(pid)`, with
`postgame.py:648` skipping `UNKNOWN`.

A forecast quarterback who **never threw a pass** has no `passer_player_id`
row, so he resolves to `UNKNOWN` and is dropped from his team's room. The
room's *forecast distribution* is therefore composed after the outcome is
known. `shadow/score.py:251-256` does the same job correctly, from
`sealed['depth_chart']` — a pregame object — so the correct construction
already exists in the repository and `postgame` regressed from it.

**Reproduction** (game `2026_01_NE_SEA`, seal
`nfl/research/shadow/g1_ne_sea`, blob `pbp_2026.d9e442ae17ba88e7.csv.gz`):

```
forecast QB row_ids : 00-0038476 00-0039851 00-0041123 00-0034869 00-0035704 00-0040673
_team_of(pbp)       : None       NE         None       SEA        SEA        None
depth_chart (seal)  : NE         NE         NE         SEA        SEA        SEA

qb/att   NE: pregame-room n=3 mean= 27.783 | realised-room n=1 mean= 24.799 | actual= 33.0
qb/pyds  NE: pregame-room n=3 mean=212.459 | realised-room n=1 mean=194.208 | actual=178.0
qb/db    NE: pregame-room n=3 mean= 33.692 | realised-room n=1 mean= 30.065 | actual= 42.0
qb/att  SEA: pregame-room n=3 mean= 27.438 | realised-room n=2 mean= 26.583 | actual= 24.0
qb/pyds SEA: pregame-room n=3 mean=197.461 | realised-room n=2 mean=190.974 | actual=200.0
qb/db   SEA: pregame-room n=3 mean= 30.969 | realised-room n=2 mean= 30.023 | actual= 27.0
```

The realised value is unchanged either way (a QB who did not play contributes
0 to both sums). Only the **forecast** changes, always downward, by an amount
set by who played. On NE/pyds the leak halves the error (+34.5 → +16.2); on
SEA/pyds it worsens it (−2.5 → −9.0). The direction is not the point — the
estimand is chosen after seeing the result, which is the defect. 114 qb_room
rows on the live ledger are built this way.

The row's own justification makes this worse: `postgame.py:626-637` argues
the room exists *because the room is forecastable pregame while the split is
not*. Composing the room postgame removes the property the row was created
for.

### L3 — seal selection is a post-hoc operator choice (MINOR, structural)

`same_day_retrospective.py:363-369`: `--seal first|last|all`. Nothing records
the choice as predeclared, and nothing prevents running all three and
reporting the best. The published artifact used `"seal_selection": "last"`.
The chronology gate itself (`same_day_retrospective.py:143-148`,
`written_at < kickoff`) is real and fires; only the *choice among* valid
pregame seals is ungoverned.

`postgame.py` has **no chronology gate at all** — `completed_with_seals`
filters on `kickoff < now` only, and `score_game` never compares `written_at`
to `kickoff_utc`. Measured: 0 of the 127 discovered seals currently violate
it, so this is an absent guard rather than a live defect.

### Not leakage, checked and cleared

- The seal is chosen before the outcome is read in `postgame.run`; the
  outcome hash is stamped on every row; a restatement creates a new row
  rather than overwriting one (`postgame.py:826-850`).
- `versioned` derives CURRENT/SUPERSEDED from append-only file order, not
  from a rewrite. Live ledger: 3,230 identities, 3,230 CURRENT, 0 superseded,
  0 revised.
- Admissibility is re-evaluated on **every** `score_game` call against
  today's contract and is explicitly not cacheable (`postgame.py:491-513`).
- Names are pulled from the outcome for readability only and no forecast
  depends on them (`actuals.py:236-238`).

---

## 3. Accounting: the 3,230 rows

Re-derived from `nfl/research/postgame/PROSPECTIVE_LEDGER.jsonl` and from
`postgame.accounting(current_rows(load_ledger()))`:

```
rows_on_ledger                             3230
rows_without_admissibility_verdict         3230
scoring_rows                                  0
graded_metrics                                0
distinct_games                                0
distinct_team_games                           0
distinct_player_games                         0
distinct_candidate_forecasts                  0
prospective_sample_size            {'value': 0, 'unit': 'GAME'}
```

`currently_admissible` is `None` on all 3,230 rows (Counter: `{None: 3230}`).
`POSTGAME_STATUS.json` reports the identical numbers, so the artifact is not
overstating itself.

Composition of those rows: 2 games (`2026_01_SF_LA` 3,130, `2026_01_NE_SEA`
100), 19 forecast_ids across 19 sealed dirs, 12 metrics, 1 outcome hash
(`d9e442ae17ba88e7`), entities 3,078 player / 114 qb_room / 38 team, bases
1,676 `ZERO_BY_COMPLETION` / 1,402 `OBSERVED` / 152 none (team + room rows),
estimand `EXACT` on all 3,230.

**What it means for any claim of graded evidence.** The gate in
`accounting` (`postgame.py:758-764`) filters to
`currently_admissible is True` and no row on disk carries that stamp, because
the stamp post-dates them. Therefore:

- **There is currently zero graded prospective evidence in this repository.**
  Not "a small amount". Zero, in every unit.
- Any statement of the form "3,230 graded rows" is wrong twice over: the rows
  carry no admissibility verdict, and even if they did, `scoring_rows` is
  declared a **bookkeeping count and never a sample size**
  (`postgame.py:719-721`). The floor unit is `distinct_games`.
- The two games behind those rows would be **2 GAME**, not 3,230 — and 19 of
  the forecasts are candidate variants of those same 2 games, which
  `PAIRED_NOTE` (`postgame.py:744-747`) correctly labels paired comparisons.
- `POSTGAME_STATUS.json` also shows the live run refusing everything else:
  15 completed games discovered, 115 seals found, **0 games scored**, 79
  deferred (the majority `POSTGAME_ARTIFACT_NOT_CURRENTLY_ADMISSIBLE`, three
  mandatory controls), 0 rows added. Discovery has since grown to 127 seals,
  so the stored status artifact is stale in its counts but not in its verdict.
- `LEDGER_MIGRATION.json` records the v1→v2 migration as lossless: 3,230 in,
  3,230 out, 0 rows unreproduced, 0 values changed. Its `evidence_after`
  block still shows the pre-gate numbers (`distinct_games: 2`), which is a
  historical record and not a current claim.

Separately: the DIAGNOSTIC numbers in `SUNDAY_1PM_OUTCOME_AUDIT.json`
(268 rows, 7 games) are correctly stamped `DIAGNOSTIC ONLY … clears no
blocker`, and the module refuses to write a ledger row. That firewall holds
in `same_day_retrospective.py`. **It does not hold downstream**:
`MODEL_HEALTH_2026-09-13.json` carries those diagnostic statistics into a
product gate that decides `ranking_eligible`, with no DIAGNOSTIC stamp of its
own on the metric rows.

---

## 4. Finality

All five signals were negative-tested by mutating the END GAME row of a real
final game (`2026_01_NE_SEA`) one field at a time. Every one fires:

```
baseline (unmutated)                     final=True   unmet=[]
desc 'END GAME' -> 'TIMEOUT'             unmet=['END_GAME_MARKER_PRESENT']
game_seconds_remaining 0 -> 120 (reg)    unmet=['GAME_CLOCK_EXPIRED']
qtr 4 -> 3                               unmet=['REGULATION_OR_LATER_COMPLETE']
result -> ''                             unmet=['FINAL_RESULT_POPULATED','SCOREBOARD_AGREES_WITH_RESULT']
total_home_score -> 99                   unmet=['SCOREBOARD_AGREES_WITH_RESULT']
rows = []                                unmet=['NO_PLAY_ROWS']  code=POSTGAME_NOT_FINAL
```

**Partial publication yields zero scoring rows.** Truncating the game to its
first 60% of play rows gives
`unmet=['END_GAME_MARKER_PRESENT','GAME_CLOCK_EXPIRED','REGULATION_OR_LATER_COMPLETE','SCOREBOARD_AGREES_WITH_RESULT']`,
and `score_game` on that returns
`BLOCKED[POSTGAME_NOT_FINAL] n_scored=0`. The gate is inside `score_game`
(`postgame.py:485-490`), not only in `run`, so a direct caller cannot route
around it.

**Overtime is fixed, and the fix is verified against real data.**

- `qtr >= 5` with a readable clock is FINAL: the mutation `qtr=5,
  gsr=243` gives `final=True, unmet=[]`. `qtr=5` with an unreadable clock
  still refuses (`GAME_CLOCK_EXPIRED`).
- Across the whole stored 2021 blob: 285 games, 285 FINAL, of which 23 are
  overtime games (END GAME row at `qtr >= 5`) and **23 of 23 are FINAL**.
  Under the old `secs == 0` rule all 23 would have been refused.
- Direct evidence of the historical defect and its repair:
  `SUNDAY_1PM_OUTCOME_AUDIT.json` records
  `2026_01_NO_DET  POSTGAME_NOT_FINAL  unmet=['GAME_CLOCK_EXPIRED']`.
  Re-running today's `game_finality` on the same game in
  `pbp_2026.1415dd98ba7f701a.csv.gz` gives `final=True, unmet=[], qtr=5.0,
  game_seconds_remaining=94.0`. The published artifact is a snapshot of the
  defect; the code no longer has it.

**Residual weakness (PARTIAL, not a defect).** Four of the five signals are
read from a single row — the last END GAME row — so they are correlated
rather than five independent proofs. A source that emitted a premature END
GAME row with a populated, self-consistent `result` would satisfy all five.
This is the strongest statement the bytes support and the code is honest that
it is proven "from the source", but it should not be described as five
independent confirmations.

`python3.12 nfl/tests/run_suite.py --only test_postgame_guards` →
`modules 1  test functions 14  checks 107  FAILING CHECKS 0  RAISED 0  SUITE PASS`.

---

## 5. Test coverage of the scoring path

`test_postgame_guards.py` covers finality (a, b, c), unit-of-evidence
(d, e, f, g), supersession (h, i, j), current inadmissibility (k), migration
losslessness (l), seal identity (m).

Not covered anywhere in `nfl/tests/`:

- `same_day_retrospective.py` — **zero test files reference it**, and none
  references `role_tiers` or `NO_REALISED_VALUE`.
- `ZERO_BY_COMPLETION` — no test asserts that an absent player scores as a
  realised zero rather than being dropped, which is precisely the property L1
  violates in the sibling module.
- `qb_room_aggregate` / `_team_of` — no test asserts room membership comes
  from a pregame source.
- `REFUSED_ESTIMANDS` — no test asserts a surrogate cannot reach a CRPS.
- `model_health.py` has no caller in the repository; the published artifact
  was produced by something not in the tree.

---

## 6. Evidence ceiling

What this audit can and cannot support.

- **Can support.** The presence and behaviour of the two leakage paths: both
  are deterministic properties of the code, reproduced by executing the
  repository's own functions on its own stored artifacts, and L1's row counts
  reproduce the published artifact exactly (268 / 369). Structural findings
  — what is stamped, what is refused, what is wired, what is not — are
  verified by reading and by execution.
- **Cannot support.** Any statement about model quality. The corrected
  columns in §2 are **not** a corrected evaluation: they are the same
  DIAGNOSTIC rows with the deleted zeros put back. They come from 7 games on
  one slate, from nested candidate variants, with no clustering by game or by
  player-game, no interval, no predeclared margin and no test. One slate is
  not a sample. Reading "the model over-forecasts" out of the corrected
  column would be the same error as reading "the model under-forecasts" out
  of the published one.
- **Cannot support.** That correcting L1 would change the health warnings in
  a specified direction. The warning predicates were not re-run, and their
  inputs include market-derived terms this audit did not touch.
- **Hard ceiling on everything downstream.** Graded prospective evidence is
  **0 rows, 0 games, 0 in every declared unit**. No forecast-quality claim in
  this repository is currently supported by graded prospective evidence, and
  no amount of scoring-path correctness changes that until admissible
  artifacts exist to score.
- **Not examined.** `REUSE.assert_currently_admissible` internals, the
  market-comparison half of `model_health` (sportsbook data, out of scope by
  instruction), `nfl/research/market_outcome_audit.py`, and the full
  `sealed_index` namespace-migration surface.

CODE CHANGED: NO.
