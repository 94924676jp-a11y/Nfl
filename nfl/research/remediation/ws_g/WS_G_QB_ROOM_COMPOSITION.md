# WS-G — QB-room composition is read from the seal, not from who threw a pass

Branch `claude/nfl-greenfield-architecture-stsxmk`, baseline HEAD `837d52f`.
Interpreter `python3.12`. **CODE CHANGED: YES**, in two files, plus one new
test module. No commit was made; the coordinator integrates.

**CHANGE CLASS: EVALUATION-ONLY.** No projection moves and no price moves.
Every sealed forecast distribution is read exactly as sealed and no number
inside one is altered. What changes is (a) *which* sealed distributions are
summed into a QB-room row, and (b) whether a join failure on the team rows is
named or silent. No sportsbook data was read or written.

The paired evidence below carries its own proof of that claim: the realised
side of every room row is **identical** before and after — paired delta
`0.0000` with a game-clustered standard error of `0.0000` on all three metrics
— while the forecast side moves. Only the composition of the forecast changed.

---

## 1. DEFECT

WS22 verdict item 5, and its leakage L2. `postgame.qb_room_aggregate` composed
each team's quarterback room by asking the **realised play-by-play** who threw
a pass:

```python
def _team_of(rows, pid):                       # postgame.py, pre-repair
    for r in rows:
        if r.get('passer_player_id') == pid:
            return r.get('posteam')
    return None
...
by_team[_team_of(rows, pid) or 'UNKNOWN'].append(pid)
...
if team == 'UNKNOWN':
    continue
```

A quarterback who was **forecast to play and recorded zero pass attempts** has
no `passer_player_id` row anywhere in the outcome. He resolved to `'UNKNOWN'`
and was deleted from his own team's room. The **forecast population was
therefore selected after the result was known.**

This is selection on the outcome, not a measurement choice. The realised value
of a deleted member is a **known zero**, not an unknown: the game is complete
and he appears on no qualifying play. Deleting known zeros is the same defect
class as WS-F's zero-dropping in the adjacent scorer, occurring one layer up,
on the composition of an aggregate rather than on the retention of a row. It
is derived here independently; WS-F's classification of *his* metrics is not
imported and is not assumed to transfer.

It also destroys the property the room row was created for. `postgame.py`'s own
justification says the room exists *because the room is forecastable pregame
while the split inside it is not when a quarterback is replaced mid-game*. A
room composed postgame is not a pregame-forecastable object at all.

**A second, smaller instance of the project's dominant defect class** sat on
the team rows: a team-code join failure was an unexplained `continue`.

```python
x = _vec(draws, manifest, metric, t)
got = (team.get(t) or {}).get(field)
if x is None or got is None:
    continue                                   # postgame.py, pre-repair
```

Two different facts were collapsed into one silent drop: *the seal carries no
forecast for this team and metric*, and *the team code on the sealed row axis
does not appear as any `posteam` in the realised outcome*. The second is how a
relocation or abbreviation change (LA/LAR, OAK/LV, SD/LAC) deletes an entire
team's rows while every count downstream still reads as a success.

---

## 2. ROOT CAUSE

The seal already carries forecast room membership and the scorer did not read
it. `manifest['layers']['qb']` declares `row_axis: 'gsis_id'` and `row_ids` —
the forecast QB room, addressed by id — and each seal separately carries the
team each id belonged to at seal time:

| Source inside the seal | Shape | Seals carrying it |
|---|---|---|
| `SEALED_FORECAST.json` → `depth_chart` | keys `'TEAM|POS|rank'` → gsis_id, stamped `depth_chart_as_of` | 2 of 127 |
| `board.json` → `players[*]` | `{'gsis_id': ..., 'team': ...}` | 125 of 127 |

Measured across **all 127 discovered seals: 0 QB `row_ids` are unresolvable
from pregame bytes.** The information was never missing. `shadow/score.py`
already composed correctly from `sealed['depth_chart']`; `postgame.py`
regressed from a construction that existed in the same repository.

---

## 3. REPAIR

Three functions added to `nfl/research/postgame.py`, one rewritten, one
refusal split in two.

**`pregame_room_membership(seal_dir, manifest, layer='qb') -> Outcome`** —
composition from sealed bytes alone. Its argument list is the guarantee: it is
not given the outcome, so it cannot condition on it. Members are addressed by
`gsis_id`, never by position.

**`_pregame_team_claims(seal_dir)`** — gathers every `(pid -> team)` claim every
pregame source in the seal makes, with the source named against each claim. **No
precedence is applied on purpose.** A precedence rule resolves a disagreement
silently; a disagreement between two pregame sources about which team a
quarterback belongs to is a fact the caller must refuse on.

**`pregame_room_from_seal(seal_dir, layer='qb') -> Outcome`** — the
recoverability proof in executable form: given only the bytes in the seal
directory, the forecast room reconstructs.

**`room_digest(membership)`** — a stable 16-hex hash of a composition, sorted by
team then by id, so two compositions are comparable and dict ordering is
invisible.

**`qb_room_aggregate` rewritten** to compose from the seal and to return
`(rows, refusals)` rather than a bare list, so a refusal cannot be dropped by
its caller. `score_game` now does `refused.extend(agg_refused)`.

Every room row is stamped with its own composition provenance:
`room_composition_source: 'PREGAME_SEAL'`, `room_composition_inputs` (the
sealed files actually read), `room_composition_digest`, `room_row_axis`,
`room_members`, `n_quarterbacks_with_realised_attempt`, and
`n_quarterbacks_zero_attempt_retained`.

`_team_of` survives, demoted to a **diagnostic**: it produces
`n_quarterbacks_with_realised_attempt`, which records how many members would
have survived the old composition. It cannot add or remove a member — proved
below by sabotaging it.

**Named refusals introduced** (each a new module constant, so a reader greps a
name rather than a sentence):

| Code | Fires when |
|---|---|
| `PREGAME_ROOM_MEMBER_TEAM_UNRESOLVED` | a sealed member has no team in any pregame source. The **whole room** is refused, not the member dropped. |
| `PREGAME_ROOM_MEMBERSHIP_CONFLICT` | two pregame sources claim different teams for one member. |
| `PREGAME_ROOM_MEMBERSHIP_SOURCE_ABSENT` | the seal carries no pregame membership source at all. It is **not** composed from the realised play-by-play instead. |
| `ROOM_MEMBER_MISSING_FROM_SEALED_DRAWS` | a sealed member has no draw row for a metric. The room is refused rather than summed over the survivors. |
| `TEAM_CODE_NOT_IN_REALISED_OUTCOME` | a sealed team code joins to no `posteam`. Carries the codes the outcome *did* hold. |
| `NO_FORECAST_MISSING_PREGAME_INPUT` | the seal carries no draw row for a team and metric (routed to `no_forecast`, not to `refused`). |

`nfl/research/shadow/actuals.py` was examined and **left unchanged**. Membership
does not originate there: `qb_actuals` is keyed by realised passer, which is
correct for an *actual* and is never the forecast population. Changing it was
not needed and would have widened the blast radius for nothing.

---

## 4. WHY THIS REPAIR

The alternative — keep composing from play-by-play but add back anyone the seal
lists — produces the same room on today's data and leaves the defect structural:
the outcome would still be an input to composition, and a future edit could
re-narrow it without any test noticing. Reading the seal removes the outcome
from the call signature entirely, which is a property of the code rather than a
property of one slate.

The refuse-the-whole-room rule follows from the estimand. A room missing a
member it was forecast with is a **different quantity** from the room that was
forecast; scoring it as though it were the same is exactly the substitution
this repair exists to end. Summing the survivors would have been the defect
with a different justification.

---

## 5. PRE-REPAIR FAILURE

Reproduced by running the repository's own modules over its own stored bytes:
`nfl/research/postgame/pbp_2026.1415dd98ba7f701a.csv.gz`
(sha256 `1415dd98ba7f701a...`), 10 games, against all **84 sealed forecasts**
this repository holds for those games (76 `live`, 6 `product`, 2 `shadow`).

**Restored QB room memberships, per game.** Each row is summed over every seal
for that game. "Members" counts one metric (`qb/att`); all three room metrics
compose identically, so the all-metric figure is three times this.

| Game | Seals | Room rows (unchanged) | Members, contaminated | Members, repaired | **Restored** |
|---|---|---|---|---|---|
| 2026_01_ATL_PIT | 6 | 36 | 12 | 48 | **+36** |
| 2026_01_BAL_IND | 5 | 30 | 10 | 40 | **+30** |
| 2026_01_BUF_HOU | 13 | 78 | 26 | 91 | **+65** |
| 2026_01_CHI_CAR | 5 | 30 | 15 | 40 | **+25** |
| 2026_01_CLE_JAX | 5 | 30 | 10 | 45 | **+35** |
| 2026_01_NE_SEA | 2 | 12 | 6 | 12 | **+6** |
| 2026_01_NO_DET | 10 | 60 | 20 | 80 | **+60** |
| 2026_01_NYJ_TEN | 10 | 60 | 20 | 70 | **+50** |
| 2026_01_SF_LA | 18 | 108 | 54 | 144 | **+90** |
| 2026_01_TB_CIN | 10 | 60 | 20 | 80 | **+60** |
| **POOLED** | **84** | **504** | **193** | **650** | **+457** |

**457 of 650 sealed QB room memberships — 70.3% — were being deleted by the
realised outcome.** Across the three room metrics that is **1,371 restored
member-contributions**. The mean room went from **1.15** quarterbacks to
**3.85**.

**Room ROW counts are unchanged at 504.** That is a property of this slate, not
a guarantee: a room vanishes entirely under the old code whenever no sealed
member of a team recorded a pass attempt, and nothing in the old path refused
or reported that. On these ten games at least one sealed member threw for every
team, so no room row disappeared. Where both paths resolved a team, the two
agreed on the team code in **every** case (0 disagreements), so the contamination
here is purely deletion, not misassignment.

**On the committed ledger.** `nfl/research/postgame/PROSPECTIVE_LEDGER.jsonl`
holds **114 `qb_room` rows** across 19 sealed dirs and 2 games, every one with
`n_quarterbacks` of 1 or 2. Their sealed pregame rooms hold **444** memberships
against the **171** recorded — **273 memberships missing from rows already on
disk**. See the residual in §8: those rows are not rewritten by this repair.

---

## 6. POST-REPAIR RESULT

Paired at the level of (seal × team × metric), **clustered by game** — games are
not independent observations, and the 84 seals are candidate variants of only
10 games. Each cell is the mean of 10 per-game means; the SE is the
between-game SE of the **paired delta**, G = 10.

`bias` is `mean(draws) - actual`, as `postgame.py` defines it.

### qb/att — 168 paired room rows, G = 10

| Aggregate | Repaired | Contaminated | Paired delta | Game-clustered SE |
|---|---|---|---|---|
| n_quarterbacks | 3.8500 | 1.1500 | +2.7000 | 0.1700 |
| forecast mean | 32.1885 | 24.5898 | +7.5987 | 1.7008 |
| forecast sd | 7.6089 | 11.5140 | −3.9051 | 0.7418 |
| bias | 0.5886 | −7.0102 | +7.5987 | 1.7008 |
| abs(bias) | 6.1491 | 8.7143 | −2.5651 | 1.1876 |
| CRPS | 4.3170 | 6.2705 | −1.9535 | 0.6985 |
| **actual** | **31.6000** | **31.6000** | **+0.0000** | **0.0000** |
| mid-PIT | 0.4568 | 0.6427 | −0.1858 | 0.0499 |
| coverage 50% | 0.5000 | 0.6000 | −0.1000 | 0.1000 |
| coverage 80% | 0.8500 | 0.8500 | +0.0000 | 0.0745 |
| coverage 90% | 0.9500 | 0.9000 | +0.0500 | 0.0500 |
| coverage 95% | 0.9500 | 0.9000 | +0.0500 | 0.0500 |

### qb/pyds — 168 paired room rows, G = 10

| Aggregate | Repaired | Contaminated | Paired delta | Game-clustered SE |
|---|---|---|---|---|
| n_quarterbacks | 3.8500 | 1.1500 | +2.7000 | 0.1700 |
| forecast mean | 231.6195 | 177.8523 | +53.7671 | 12.1903 |
| forecast sd | 82.9983 | 98.5679 | −15.5695 | 4.1622 |
| bias | −5.0805 | −58.8477 | +53.7671 | 12.1903 |
| abs(bias) | 56.2896 | 70.6805 | −14.3908 | 9.1784 |
| CRPS | 41.1778 | 56.4246 | −15.2468 | 4.6443 |
| **actual** | **236.7000** | **236.7000** | **+0.0000** | **0.0000** |
| mid-PIT | 0.5148 | 0.6698 | −0.1550 | 0.0474 |
| coverage 50% | 0.6000 | 0.6050 | −0.0050 | 0.0717 |
| coverage 80% | 0.9000 | 0.8000 | +0.1000 | 0.0667 |
| coverage 90% | 0.9150 | 0.8500 | +0.0650 | 0.0506 |
| coverage 95% | 0.9150 | 0.8650 | +0.0500 | 0.0500 |

### qb/db — 168 paired room rows, G = 10

| Aggregate | Repaired | Contaminated | Paired delta | Game-clustered SE |
|---|---|---|---|---|
| n_quarterbacks | 3.8500 | 1.1500 | +2.7000 | 0.1700 |
| forecast mean | 36.4244 | 27.8850 | +8.5394 | 1.8958 |
| forecast sd | 8.3063 | 12.9597 | −4.6534 | 0.8734 |
| bias | 0.4744 | −8.0650 | +8.5394 | 1.8958 |
| abs(bias) | 6.1410 | 10.0870 | −3.9460 | 1.1425 |
| CRPS | 4.5965 | 7.1369 | −2.5404 | 0.8155 |
| **actual** | **35.9500** | **35.9500** | **+0.0000** | **0.0000** |
| mid-PIT | 0.4689 | 0.6492 | −0.1803 | 0.0477 |
| coverage 50% | 0.5000 | 0.6500 | −0.1500 | 0.0764 |
| coverage 80% | 0.8500 | 0.8500 | +0.0000 | 0.0745 |
| coverage 90% | 0.9500 | 0.9000 | +0.0500 | 0.0500 |
| coverage 95% | 0.9500 | 0.9000 | +0.0500 | 0.0500 |

**Per-game bias, qb/pyds** — the contaminated column is negative on 8 of 10
games and the repaired column on 4 of 10. Seven games change sign.

| Game | Repaired | Contaminated |
|---|---|---|
| 2026_01_ATL_PIT | +62.052 | −55.184 |
| 2026_01_BAL_IND | −19.260 | −90.470 |
| 2026_01_BUF_HOU | −58.584 | −122.874 |
| 2026_01_CHI_CAR | −111.095 | −129.462 |
| 2026_01_CLE_JAX | +3.243 | −75.429 |
| 2026_01_NE_SEA | +15.960 | +3.591 |
| 2026_01_NO_DET | −62.115 | −88.230 |
| 2026_01_NYJ_TEN | +50.931 | −53.695 |
| 2026_01_SF_LA | +51.780 | +32.854 |
| 2026_01_TB_CIN | +16.283 | −9.577 |

### What may and may not be read out of these tables

**May be read.** The contaminated column is arithmetic on a population chosen
by the outcome. A room forecast to hold four quarterbacks and scored as one
forecasts a smaller number against an unchanged realisation, and the deficit it
shows is the deleted members' forecasts, not the model's error. That is a
deterministic property of the code, reproduced by executing the repository's own
functions on its own stored bytes.

**May NOT be read.** *Anything about model quality.* These are ten games on one
slate, from 84 nested candidate variants of those ten games, with no predeclared
equivalence margin and no test. The words "unbiased", "stable", "closed" and
"correct" are not used of any number here, and the repaired column is **not** a
corrected evaluation — it is the same sealed forecasts with the deleted members
put back. Reading "the model is well calibrated on rooms" out of the repaired
column would be the same error as reading "the model under-forecasts rooms" out
of the contaminated one.

Note also that the contaminated column was never *scored* evidence: every
`qb_room` row on the live ledger carries no admissibility verdict, and
`accounting` counts the prospective sample at **0 games** (WS22 §3). This repair
does not move that number and does not claim to.

---

## 7. TEST

`nfl/tests/test_qb_room_composition.py` — **new, 7 test functions, 58 checks**.

```
python3.12 nfl/tests/run_suite.py --only test_qb_room_composition
modules 1  test functions 7  checks 58  FAILING CHECKS 0  RAISED 0
SUITE PASS
```

**(a) A QB forecast to play with zero realised attempts remains in the room.**
On the chosen fixture, **5 of 8** forecast quarterbacks recorded no pass
attempt; all 5 are room members after the repair, and the 8 sealed `row_ids`
partition exactly across the rooms. The retained count is asserted as a
*counted field*, not as prose.

**(b) The realised outcome cannot determine forecast composition —
structurally, three independent ways.**

1. *The argument list.* `pregame_room_membership` takes exactly
   `(seal_dir, manifest, layer)`. Its source is asserted never to contain
   `passer_player_id`, `posteam`, `_team_of` or `qb_act`. A function cannot
   condition on what it is not given; this holds on every slate, not one.
2. *Mutate the outcome.* The room is recomposed with (i) every
   `passer_player_id` erased, (ii) every `posteam` relabelled `ZZZ`, (iii) the
   outcome removed entirely. In all three the composition is **byte-identical**
   — digest, members, count, forecast mean, forecast sd and all nine stored
   percentiles. The test also asserts the *realised* half **does** move under
   the same mutation, so the comparison is not vacuous.
3. *Sabotage the old composer.* `PG._team_of` is monkeypatched to return a
   fabricated team for every id. Composition is unchanged, and the diagnostic
   count correctly collapses to zero — which is how the test proves `_team_of`
   is now reachable only as a label.

**(c) Pregame identity is recoverable from the seal.** `pregame_room_from_seal`
is run against **all 127 discovered seals**: every one reconstructs, **956
memberships total, 0 failures**. Then the harder version: a seal is copied to a
temporary directory with every outcome-bearing file removed, and reconstructs
to the **identical digest and identical member-for-member mapping**. The digest
is shown to be a real discriminator (15 distinct values across the seals), to
change when one member moves team, and not to change under dict reordering.

**(d) An unresolvable member refuses the whole room by name.** A copied seal has
one member's pregame team deleted → `BLOCKED[PREGAME_ROOM_MEMBER_TEAM_UNRESOLVED]`
naming the gsis_id, `qb_room_aggregate` returns **zero rows and exactly one
named refusal**, and the untouched copy still composes.

**(e) Two pregame sources disagreeing is its own named refusal.** A conflicting
`depth_chart` claim is injected → `BLOCKED[PREGAME_ROOM_MEMBERSHIP_CONFLICT]`,
a distinct code, naming the member and **both** claimants with the file each
came from.

**(f) The team-code join failure is named, not dropped.** Every `posteam` in a
real outcome is relabelled `ZZZ` so no sealed team code joins. `score_game`
now emits `TEAM_CODE_NOT_IN_REALISED_OUTCOME` once per sealed team row and
metric, carrying the codes the outcome did hold, and scores no team row on an
unjoined code. The unmutated outcome is scored in the same test and produces
team rows with no such refusal, so the check is not vacuous.

*Declared scaffold:* `score_game` refuses every real seal today on
current-contract admissibility (WS22 §3), so that gate is stood down
**test-locally** for this one call and restored in a `finally`, with the
restoration itself asserted. Nothing is written to any store.

**(g) The defect cannot return by editing one line.** The old composition
expression and the `'UNKNOWN'` bucket are asserted absent from
`qb_room_aggregate`; the 2-tuple return is asserted so a caller cannot drop a
refusal; and `score_game` is asserted to extend `refused` with it.

### Regression, on the modules that exercise the changed file

Run per module as instructed, never the full suite.

| Module | Result |
|---|---|
| `test_qb_room_composition` (new) | 7 functions, **58 checks, 0 failing, 0 raised** — SUITE PASS |
| `test_postgame_guards` | 14 functions, **107 checks, 0 failing, 0 raised** |
| `test_postgame_ingestion` | 9 functions, **41 checks, 0 failing, 0 raised** |
| `test_shadow_evaluation` | 12 functions, 24 checks, 0 failing — SUITE PASS |
| `test_schema_and_scoring` | 8 functions, 38 checks, 0 failing — SUITE PASS |
| `test_q7_efficiency_calibration` | 13 functions, 77 checks, 0 failing — SUITE PASS |
| `test_accounting_invariants` | 8 functions, 41 checks, 0 failing — SUITE PASS |
| `test_prospective_contract` | 8 functions, 63 checks, 0 failing — SUITE PASS |

`test_postgame_guards` and `test_postgame_ingestion` print `SUITE FAIL` on a
**pre-existing** runner rule, not on anything in this diff: each has a
`test_zz_every_check_passed` summary function that records zero checks, and the
runner now refuses a function that measured nothing. **Control:
`--only test_sealed_index`, a module I did not touch, reports the identical
`ZERO-CHECK FUNCTIONS: 1 ... SUITE FAIL`.** `nfl/tests/run_suite.py` is
currently modified in the working tree by another workstream, which is the
likely origin. Both postgame modules report **FAILING CHECKS 0 / RAISED 0**,
matching WS22's recorded 107/0/0 for `test_postgame_guards` exactly.

**Not measured: `test_q9_prospective_shadow`.** It was launched and did not
complete or emit a single line within the time available. It is WS-E's module
and is dirty in the working tree right now, so a result from it would measure
WS-E's in-flight edits as much as mine. **Reporting it as "passed" would be the
failure mode this project names Class A**, so it is reported as not run, with
the cause stated. The coordinator should re-run it once WS-E's edits settle.

---

## 8. BLAST RADIUS

**Files changed (2, plus 1 new):**

| File | Change |
|---|---|
| `nfl/research/postgame.py` | +297 / −12. Composition from the seal; four new named refusal codes and two split out of one `continue`; `qb_room_aggregate` returns `(rows, refusals)`; room rows carry composition provenance. |
| `nfl/tests/test_qb_room_composition.py` | NEW, 7 functions, 58 checks. |
| `nfl/research/remediation/ws_g/WS_G_EVIDENCE.json` | NEW. The machine-readable version of §5 and §6. |

`nfl/research/shadow/actuals.py` — **owned, examined, unchanged.**

**Callers.** `qb_room_aggregate` and `_team_of` have **no caller outside
`postgame.py`** (checked across the whole tree). The signature change is
therefore contained. `postgame` is imported by `same_day_retrospective.py`
(WS-F), `market_outcome_audit.py`, `qb3/qb_participation_audit.py`,
`q9shadow/ledger.py` (WS-E) and five test modules; none of them touches the
room path.

**Stored artifacts.** **None were regenerated, because none changed.** Verified
by re-hashing after the repair:

| Artifact | sha16 | Baseline |
|---|---|---|
| `nfl/research/SUNDAY_1PM_OUTCOME_AUDIT.json` | `82f706127181238d` | matches |
| `nfl/research/model_health/MODEL_HEALTH_2026-09-13.json` | `4639ff1a0fdcb8a6` | matches |
| `nfl/research/slate_audit/C1_EVALUATION.json` | `a79772b4cc3c1e37` | matches |
| `nfl/research/live/OPEN_DEFECTS.json` | `6921d226530f4d27` | matches |
| `nfl/research/PATH_C_STATE.json` | `ebd1274086ec9c81` | matches |
| `nfl/research/postgame/PROSPECTIVE_LEDGER.jsonl` | `9fbc20f04edbb7e1` | untouched |

`SUNDAY_1PM_OUTCOME_AUDIT.json` is produced by `same_day_retrospective.py`,
which emits no room rows and which I did not edit; it is unaffected by
construction as well as by measurement.

**RESIDUAL, and it needs the coordinator's decision.** `_row_key`
(`postgame.py`) keys a row on `(game_id, entity, gsis_id, team, metric,
sealed_dir, forecast_id, outcome_sha16)`. Composition is not in the key, so
**re-scoring the same outcome bytes will not supersede the 114 contaminated
`qb_room` rows already on the ledger** — it will be a no-op on them. Verified
directly: the key is unchanged when `n_quarterbacks` and the composition stamps
change. Those 114 rows hold 171 memberships where the seal holds 444 (**273
missing**).

I did **not** change `_row_key`. Adding a field to it changes the key of all
3,230 existing rows, which would make the next run append 3,230 duplicates —
a much larger and worse blast radius than the defect. The rows are currently
inert (no admissibility verdict, counted as 0 games in every unit), so nothing
downstream reads them as evidence today. **Recommended handling: a supersession
pass that stamps the 114 rows with a correction link**, which is a ledger
operation and the coordinator's to schedule, not mine to perform inside an
evaluation-only repair. Flagging, not fixing.

**Not examined.** Whether any non-QB layer has the same composition pattern;
the `arm` gap in `_row_key` (WS22 item 3b, latent); the chronology gate absent
from `postgame.py` (WS22 L3).

---

## 9. IDENTITY IMPACT

Nothing frozen is touched. `nfl/production/nonqb/layers.py` is untouched; no
production module is touched; no fitted parameter, coefficient, standardiser or
seed is read or written. `Q9_PROSPECTIVE_FREEZE.json` hashes
`nfl.research.q9.hurdle`, `nfl.research.q9b.family`,
`nfl.research.q9b.production_parity` and `nfl.production.nonqb.layers` — none of
them is in this diff.

`postgame.py` is **not** named in any freeze file, and `SPEC_VERSION` is left at
`postgame-ingestion-1`: the scored quantities and their estimand definitions are
unchanged, so bumping it would assert a contract change that did not occur.

**What *does* change identity, and deliberately.** Every `qb_room` row written
from here carries `room_composition_source`, `room_composition_inputs`,
`room_composition_digest`, `room_row_axis` and `room_members`. A room row can
now be re-derived from its own stamps and its seal without the outcome, and two
room rows are comparable only when their digests match. Room rows written
before this repair carry none of those fields, which is how a reader tells the
two populations apart.

---

## 10. WHAT THIS DOES NOT ESTABLISH

- No claim of improved forecast quality. The repaired column is the estimand
  that was forecast; it is not evidence that the forecast is good.
- No equivalence claim of any kind. No predeclared margin, no TOST, therefore
  no use of "unbiased", "stable", "closed" or "correct".
- Graded prospective evidence remains **0 rows, 0 games, 0 in every declared
  unit** (WS22 §3). Correcting a scorer does not create evidence to score.
- WS-F's repair and this one are the same defect *class* in two different
  scorers. The numbers here are derived only from the rooms in `postgame.py`.
  Nothing from WS-F's classification is imported, and these figures should not
  be pooled with his without the coordinator deciding they are poolable.
