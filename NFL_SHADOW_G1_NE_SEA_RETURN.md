# Game 1 shadow evaluation — NE @ SEA, 2026-09-10

**Exploratory. Nothing here is promoted, nothing is prospective evidence, and
every observation below is classified `POST_V1_REFINEMENT`.** V1 remains frozen;
`nfl/production` is untouched by this work. G0A remains 11/12 and NFL-1 remains
NOT AUTHORIZED. The SF@LA adjudication is still a separate scheduled task.

Final score SEA 13, NE 10.

## 0. What was sealed, and in what order

The forecast was produced, written to disk, hashed and **committed to git before
the outcome file was opened**. The order is the evidence, so it is recorded
rather than asserted:

| step | artifact | sha256 |
|---|---|---|
| outcome downloaded, unread | `pbp2026.csv.gz` | `ca02541038a1519d28a862157b031b6bc98f1ebb0b5d21341ac40cfcc22a582b` |
| forecast sealed (commit `bba6f0b`) | `forecast_artifact.json` | `ada5b3dc4e496245e1898bbc72d36f367c092380c2f64d96dacc4fa1cda0f04f` |
| joint draws | `player_draws.npz.gz` | `8a5a759a97cdb8899b824e07bc181a1e1ed62e8b61b25f62c6e7a78711d8be95` |

`nfl/research/shadow/score.py` refuses to run unless every sealed file still
hashes to its recorded value, and unless the outcome file hashes to the value
recorded when it was downloaded.

**Information set.** Latest content observed strictly before the
2026-09-10T00:20:00Z kickoff, selected by observation time — not by file size or
row count. The newest such observation is **2026-09-08T17:06:03Z, 31.2 hours
before kickoff**. `written_at` 2026-09-08T17:10:00Z. Seven sources present;
`snap_counts`, `pbp_participation` and `official_transactions` named absent
rather than dropped.

This is a **T−31h** information set, not a T−90m one. There is no capture
anywhere on 2026-09-09 — the same gap that leaves G0A at 11/12. The official
inactives that would have resolved Questionable to 0/1 do not exist for this
game, and no choice of `written_at` could have recovered them.

Run status **SEALED**: `V1_CANDIDATE`, arm A, seed 20260908, 1000 joint draws
on a shared index. R2, C0, A3G, A1 and SC1 applied; **C3 not reached**.

## 1. Team environment — forecast against actual

Six quantities can be compared like for like. Four cannot, and are marked so
rather than scored against a near-miss.

| team | metric | mean | 90% interval | actual | mid-PIT | CRPS |
|---|---|---|---|---|---|---|
| NE | team_carries | 29.29 | [19.0, 37.7] | **31** | 0.571 | 1.86 |
| NE | team_targets | 26.98 | [18.0, 38.0] | **31** | 0.734 | 3.13 |
| NE | team_rz_carries | 4.18 | [1.2, 7.2] | **0** | **0.024** | 2.79 |
| SEA | team_carries | 27.66 | [18.3, 37.6] | **22** | 0.249 | 3.32 |
| SEA | team_targets | 27.63 | [18.9, 38.4] | **24** | 0.367 | 1.76 |
| SEA | team_rz_carries | 5.45 | [2.1, 11.3] | **3** | 0.254 | 1.19 |

Five of six inside the 90% interval. The exception is **New England's red-zone
carries: forecast a mean of 4.2, actual 0.** New England ran 31 times and not
once from inside the 20.

`team_off_snaps` and `team_dropbacks_part` are **not scored**. Their estimands
are defined against `snap_counts` and the participation feed, both of which
return BLOCKED here, and neither is reconstructable from play-by-play. The
nearest play-by-play quantities are reported as labelled surrogates only — NE
85 plays against a 64.5 forecast mean, SEA 69 against 63.6, and NE 42 dropbacks
excluding two-point attempts against 34.0. Those are suggestive of a
higher-volume game than forecast for New England, and they are not evidence,
because a CRPS against a different quantity would look like evidence and be
none.

## 2. Quarterback opportunity and efficiency

### Drake Maye — the model's best result of the night

| metric | mean | 90% interval | actual | mid-PIT |
|---|---|---|---|---|
| dropbacks | 30.07 | [0, 47] | **42** | 0.886 |
| attempts | 24.80 | [0, 39] | **33** | 0.844 |
| completions | 17.10 | [0, 28] | **23** | 0.821 |
| passing yards | 194.21 | [0, 347] | **178** | 0.413 |
| passing TD | 1.33 | [0, 4] | **1** | 0.455 |
| interceptions | 0.60 | [0, 2] | **3** | **0.987** |
| sacks | 2.29 | [0, 5] | **3** | 0.680 |
| scrambles | 2.98 | [0, 7] | **6** | 0.919 |
| rush opportunities | 3.82 | [0, 8] | **7** | 0.896 |
| rushing yards | 24.48 | [0, 63] | **47** | 0.876 |

Ten of eleven quantities inside 90%. Passing yards landed at mid-PIT 0.413 —
close to the centre of the distribution. Every volume quantity landed high
(0.82–0.92), consistently, which is the same signal the New England snap
surrogate carries: it was a higher-volume game for New England than forecast,
and the quarterback line inherited that.

**The one genuine miss is three interceptions.** The model gave P(more than 2.5)
= 2.4%. It is a 2.4% tail event that occurred, inside the sample support — not
an outcome the model ruled out.

### Seattle: the QB change, and what it does and does not tell us

Sam Darnold was injured on a sack at 12:27 of the first quarter — the
play-by-play says so in terms: *"SEA-14-S.Darnold was injured during the
play."* He threw 3 pass plays. Drew Lock took over from 6:22 of the first
quarter and finished the game with 24 dropbacks.

Individually both forecasts are badly wrong, and both for the same reason:

| player | metric | mean | actual | mid-PIT |
|---|---|---|---|---|
| Darnold | dropbacks | 27.71 | 3 | 0.067 |
| Darnold | passing yards | 177.45 | 13 | 0.069 |
| Lock | dropbacks | 2.32 | 24 | 0.981 |
| Lock | passing yards | 13.52 | 187 | 0.989 |

**Summed within each draw — which the shared draw index makes legitimate — the
picture inverts completely.** Seattle's quarterback room, taken as one:

| metric | mean | 90% interval | actual | mid-PIT |
|---|---|---|---|---|
| dropbacks | 30.97 | [18, 49] | **27** | 0.319 |
| attempts | 27.44 | [16, 42] | **24** | 0.323 |
| completions | 17.43 | [9, 28] | **17** | 0.520 |
| passing yards | 197.46 | [85, 361] | **200** | 0.579 |
| passing TD | 1.18 | [0, 3] | **1** | 0.494 |
| interceptions | 0.78 | [0, 3] | **0** | 0.237 |
| sacks | 2.10 | [0, 5] | **2** | 0.528 |
| scrambles | 1.43 | [0, 4] | **1** | 0.426 |
| rush opportunities | 2.34 | [0, 5] | **1** | 0.233 |
| rushing yards | 12.65 | [0, 35] | **14** | 0.668 |

**All eleven inside the 50% interval.** The model got Seattle's quarterback
environment right and got the identity of the quarterback wrong, because the
quarterback got hurt eleven minutes into the game. Darnold appears on no
pre-kickoff injury report — the 2026-09-08T16:06Z report covers eleven players
across the two teams and he is not among them. Nothing in the information set
pointed at this.

New England's aggregate, for the same treatment: 21 of 22 aggregate quantities
across both teams covered at 90%; the single exception is New England's
interceptions, which is Maye's 3 seen again at team level rather than a
separate failure.

### Backups who did not play

Three of the six forecast quarterbacks never took a snap. Their actual is a
realised **zero**, not a missing observation, and they are scored: mid-PIT 0.377
to 0.413 across dropbacks, attempts and yards, all covered. The model put most
of its mass at zero for backups and was right to.

## 3. Rushing and receiving opportunity — NOT PRODUCED

**The engine produced no player-level receiving or rushing forecast for this
game.** The `appearance` stage returned `INJURY_REPORT_CHRONOLOGY_FAILURE` and
the whole non-QB chain — participation, targets_carries, conversion, td_layer —
followed as `NOT_APPLICABLE`. The C3 candidate component was `NOT_REACHED` for
the same reason.

That refusal is **correct as a refusal and wrong as an answer**, and the cause
is precise. `nfl/production/nonqb/readiness.py:team_report_history` takes each
team's injury block from the newest capture **on disk**, with no vintage cut,
and `team_readiness` then checks that block's timestamp against `written_at`.
Disk now holds captures from 2026-09-10T13:37Z, so the check fails — while a
legitimate pre-kickoff report for exactly these two teams sits unused in
`injuries.1bf460ad261559a8.csv.gz`, observed 2026-09-08T16:06:25Z, 32.2 hours
before kickoff, carrying 11 rows for NE and SEA and no other team. The guard is
doing its job; the selector never looks for a valid earlier capture. No choice
of `written_at` rescues it.

The outcomes are recorded in the ledger against an explicitly absent forecast,
so that the game does not read as though it contained only what was modelled:

- **JSN: 11 targets of Seattle's 24 — a 45.8% share — 8 receptions, 122 yards,
  1 TD.** Extreme concentration, and the project has an open finding
  (`RB1↔RB2 at flat week-1 priors`) that says concentration is where the
  current allocation is weakest. No forecast exists to test it against.
- **Stevenson: 18 of New England's 31 carries — 58.1% — 51 rushing yards, plus
  6 targets, 5 receptions, 44 yards.**
- **New England's RB2 on the pre-kickoff depth chart, TreVeyon Henderson
  (`00-0040734`), was listed Did Not Participate In Practice with an ankle on
  that same pre-kickoff report, and recorded zero carries and zero targets.**
  The signal that would have moved Stevenson's workload was in the information
  set and the engine never read it.

That is the single most valuable thing this replay produced.

## 4. Distributional validity

Tallies, with the caveat that matters more than the numbers: **this is one
game.** The quantities are not independent — attempts, completions and yards
for one passer are near-deterministic functions of each other, and both teams
share one game script. Project rule 9 applies with full force. These are
descriptions of one observation, not calibration evidence.

| group | n | 50% | 80% | 90% | 95% | mean CRPS | median mid-PIT |
|---|---|---|---|---|---|---|---|
| team environment (exact) | 6 | 66.7% | 83.3% | 83.3% | 100% | 2.34 | 0.367 |
| team-level QB aggregate | 22 | 68.2% | 95.5% | 95.5% | 100% | 3.83 | 0.528 |
| individual QB | 66 | 66.7% | 80.3% | 90.9% | 90.9% | 7.03 | 0.468 |
| individual QB, ex. the injured room | 44 | 84.1% | 97.7% | 97.7% | 97.7% | 1.47 | 0.468 |

**A structural caveat on the individual-QB row, and it is not a small one:
every individual quarterback's 90% interval has a lower bound of zero.**
Appearance uncertainty dominates the individual marginals, so those intervals
are effectively one-sided and 90% coverage there is a weak test that is hard to
fail. The team-level aggregate intervals are genuinely two-sided (NE dropbacks
[22, 47], SEA passing yards [85, 361]) and are the row worth reading. They are
also **wide** — which is honest, and which is the discrimination question
restated, not answered.

Full percentiles at 1/5/10/25/50/75/90/95/99, exact CRPS, the non-randomised
PIT bracket `[F(y−), F(y)]` with its mass at the actual, and coverage at
50/80/90/95 are stored per quantity in
`nfl/research/shadow/g1_ne_sea/EVALUATION.json`. Nothing was reduced to four
quantiles; the 1000 joint draws are kept.

## 5. Hypothetical prop-threshold probabilities

Thresholds are round half-point lines stepped around each metric's forecast
median by a rule fixed in advance. **No book price entered this file and none
may.** No wager is recommended, and market information does not enter football
forecasting in this project.

Drake Maye:

| line | P(over) | actual |
|---|---|---|
| attempts 25.5 | 0.52 | 33 ✓ over |
| attempts 30.5 | 0.24 | ✓ over |
| completions 20.5 | 0.30 | 23 ✓ over |
| passing yards 175.5 | 0.60 | 178 ✓ over |
| passing yards 200.5 | 0.49 | ✗ under |
| passing TD 0.5 | 0.70 | 1 ✓ over |
| interceptions 2.5 | **0.024** | 3 ✓ over |
| rush opportunities 4.5 | 0.35 | 7 ✓ over |
| rushing yards 35.5 | 0.22 | 47 ✓ over |

The interceptions row is the honest one to sit with: the model priced three
picks at 2.4% and three picks happened.

## 6. Genuine miss, in-game change, or missing input

The separation is a **stated predicate evaluated on the data**, not a judgement
made after seeing the errors, and it is tested — because the first version of
the rule was wrong. It keyed an in-game change to whether the play-by-play
named *that* quarterback as injured, which credited the departing starter and
recorded **Lock**, whose forecast the same event wrecked far more, as a model
miss; and it fired for third-string quarterbacks on nothing but their team
having used two passers. The rule now asks whether a quarterback threw but was
not his team's passer throughout — true of the starter who leaves and the
replacement who enters, false of a backup who never appeared.

193 ledger rows:

| class | n |
|---|---|
| `NO_FORECAST_MISSING_PREGAME_INPUT` | 95 |
| `WITHIN_DISTRIBUTION` | 69 |
| `IN_GAME_STATE_CHANGE` | 22 |
| `NOT_CLASSIFIED_SURROGATE_ACTUAL` | 4 |
| **`MODEL_MISS`** | **3** |

The three misses are **two distinct events**: New England's zero red-zone
carries, and Maye's three interceptions (counted once individually and once in
the New England aggregate).

## 7. Observations — all `POST_V1_REFINEMENT`

Nothing below was acted on. V1 is frozen and no threshold was changed after
seeing the outcome.

1. **`TEAM_VOLUME_DRAW_COUNT_TRUNCATES_SILENTLY`.** `team_volume_v1.forecast`
   ends with `V.draw(...)[:, :m]`, and `p4b_volume.draw` always returns exactly
   `M_DRAWS = 1000` columns. The `m` argument can only truncate; it cannot
   resize. A caller asking for 4000 silently receives 1000. **Caught by the B13
   shared-draw-index guard**, which refused the run with
   `DRAW_INDEX_RAGGED` — the guard is load-bearing and it worked. Found before
   any outcome was opened; the replay ran at 1000, the count the engine can
   actually deliver.
2. **`READINESS_INJURY_READER_HAS_NO_VINTAGE_CUT`.** Detailed in §3. Cost: the
   entire non-QB chain, hence all player-level receiving and rushing, hence C3.
   This is the highest-value item here.
3. **`REHEARSAL_ROSTER_SELECTOR_CAN_PICK_A_POST_KICKOFF_VINTAGE`.**
   `rehearsal/run_slate.py:roster` selects the roster vintage with the most
   week-1 rows. For week 1 that is `weekly_rosters.0b005c45d924a541`, first
   observed **2026-09-10T05:05:18Z — after this kickoff**, and it is the vintage
   named in the committed `slate_inventory.json`. A bigger file is not a
   pre-kickoff file. That driver is a rehearsal harness rather than the
   forecasting architecture, and the shadow replay declined to inherit the
   defect rather than repairing it.
4. **`INDIVIDUAL_QB_INTERVALS_ARE_ONE_SIDED`.** Every individual quarterback's
   90% interval has a lower bound of zero. Interval coverage at the individual
   level is therefore a weak test, and aggregate-level coverage is the one to
   read.
5. **`TEAM_VOLUME_METRICS_NOT_VERIFIABLE_FROM_PBP`.** Four of ten
   team-environment quantities cannot be scored at all without `snap_counts`
   and `pbp_participation`, both BLOCKED. Two of the five metrics the team
   model actually forecasts are among them.
6. **New England's red-zone carries** and **the interception tail** are the two
   real misses. Neither supports a change on one game.

## An operational discovery, reported rather than acted on

**Outbound HTTPS works from this container.** A request to the nflverse release
endpoint returned HTTP 200 and 65,119 bytes. The project has been treating
egress as universally 403 and `pbp_sources()` still returns BLOCKED. That belief
is what made this evaluation look impossible in the first place, and it is the
same failure mode `docs/AGENT_OUTBOX.md` exists to prevent: something recorded
blocked for both agents when it was only unavailable to one. I have not changed
any source or connector on the strength of it. It is stated here because it
changes what is genuinely blocked.

## Overall first-game grade

**B−, and the grade is mostly about what could not be tested.**

What earns the mark: the team-level quarterback environment for both teams was
forecast well — 21 of 22 aggregate quantities inside 90%, Seattle's entire
quarterback room inside the 50% interval, Seattle's passing yards 200 against a
forecast mean of 197. Drake Maye's line was good across ten of eleven
quantities. Backups who did not play were correctly given most of their mass at
zero. The pipeline sealed a real artifact with 1000 joint draws and a verified
hash chain, and two separate guards — the draw-index guard and the chronology
guard — refused rather than passing something broken.

What holds it down. **Roughly half the game was never forecast at all**: no
player-level receiving or rushing, no C3, because a reader with no vintage cut
refused an input that existed. The information set was T−31h rather than T−90m,
with no inactives, because of the same capture gap that leaves G0A at 11/12.
Four of ten team-environment quantities are unverifiable here. And the
aggregate intervals that did land are wide — one game says nothing about
whether they are wide because the world is uncertain or because the model is
not discriminating, which remains the open question this project exists to
answer.

One game is one game. **This is a single, exploratory observation and it is not
evidence of forecasting skill.** It is worth exactly what it cost: it found two
concrete defects in the path around the model, and it says the quarterback
volume layer looked sane once against reality.

V1 remains frozen. Nothing is promoted. The SF@LA G0A adjudication remains the
next scheduled task.

---

## Appendix — the test suite is FAILING, and not because of this work

`python3.12 nfl/tests/run_suite.py`, run after the shadow evaluation:

```
modules 55  test functions 591  checks 3322  FAILING CHECKS 3  RAISED 2
SUITE FAIL
```

**Both failing modules reproduce identically at `34b59a2`, the commit before any
shadow work existed.** Verified in a clean worktree, not assumed. Neither is
mine, and neither is fixed here, because this task's instruction is not to
modify V1. Both need an owner ruling.

### A. `test_full_slate_rehearsal` — an unnamed raise inside the production entrypoint

```
FAIL  every game seals               1 of 16 REFUSED
FAIL  and no game reports an unnamed failure
      targets_carries  STAGE_RAISED  KeyError: 'add_pool'
```

The cause is not `add_pool` being missing from the frozen parameters — it is
present, and `p4c_params.params('targets', 2026)` returns it. **The production
entrypoint passes empty placeholders instead of parameters.**
`run_forecast.py:433`:

```python
o = LY.targets_carries(pa, 'targets', [], [], ([], []), [], {}, ...)
```

That final `{}` is the parameter dict, and the two lists before it are the
player frames. `receiving_conversion` (line 445) and `td_layer` (line 453) are
wired the same way.

**The non-QB chain in the canonical entrypoint has never executed.** It has
always been `NOT_APPLICABLE` — blocked upstream by `appearance` — so nothing
ever reached the empty arguments. The newest injury captures cover 30 teams,
NE and SEA are now `READY`, `appearance` passes for the first time, the stage
is reached, and it raises.

This is precisely the defect class this project pays for most: **a stage that
looked wired because it was skipped for an unrelated reason.** It is the same
root as §3 of this report seen from the other side — the reason the shadow
replay produced no receiving or rushing forecast is that this chain refused
upstream, and had it not refused, it would have raised.

I have not touched it. In substance it is a V1 blocker rather than a refinement,
and it is an owner call, so it is stated plainly rather than filed under the
classification this task asked for.

### B. `test_football_engine_r4::test_F_one_missing_report_does_not_change_another_game`

```
FAIL  a team that filed is not dragged down by one that did not
      READY / INJURY_REPORT_INCOMPLETE
```

The test hardcodes `ARI == 'INJURY_REPORT_NOT_YET_FILED'`. Arizona has since
filed 7 rows, so its state is now `INJURY_REPORT_INCOMPLETE`. **The code is
right and the test asserts a transient data state** — the same defect as the
earlier `test_preflight` hardcoding `2026_01_NE_SEA`, which was repaired by
asserting the property instead of the value. The fix here is the same shape:
assert that ARI's state is *not* driven by NE or SEA, rather than naming the
state ARI happened to be in on the day the test was written.
