# Q9 live pregame feature builder

Written 2026-09-12. `nfl/prospective/q9shadow/live_features.py`.

**A production/live feature builder, not a research refit.** No coefficient is
fitted here and the candidate is untouched: the 25-feature schema hashes
`f620eeed09d0dd6e`, which is the hash the frozen Q9 candidate was frozen
against, and `assert_feature_schema_matches_freeze` refuses the build if it
ever stops matching.

| requirement | state |
|---|---|
| no 2026 outcomes | **MET** — history window is seasons strictly `< season`, all season long |
| pregame-known inputs only | **MET** — depth-chart vintage, official injury feed, committed prior-season panel |
| same 25-feature schema / hash | **MET** — `f620eeed09d0dd6e`, checked against the freeze on every build |
| exact timestamp provenance on every source | **MET** — `sha256` + `retrieved_at` + the **named basis** for each |
| no `weekly_rosters.status == INA` | **MET** — the roster file is never opened; the pool comes from the depth chart |
| no postgame roster state | **MET** — refused by source table and by a descriptor-field guard |
| projection guards preserved | **MET** — the ten-key projection is unchanged and re-asserted at build time |
| reproduces the historical builder where both are defined | **MET — EXACT** (see §3) |

It **runs on a real 2026 game today**: CHI week 1, 14 RB/WR/TE from the depth
vintage, all 14 with a depth rank, history from 6 prior seasons, arm **A**.

---

## 1. Parity is by construction, not by care

The obvious implementation is a second pipeline that recomputes trailing
target frequency, participation EWMA, share-given-positive, prior depth,
trailing snap share and role class for a live team-week. That is a
reimplementation, and a reimplementation drifts.

This builder recomputes none of them. It appends **live-shaped rows** to the
historical panel — one per player, pregame inputs only, with `appeared`,
`snap`, `targets`, `carries`, `share_targets`, `share_carries`, `den_targets`
and `den_carries` all explicitly `None` — and then runs the historical
builder's own attach functions over the union:

| function | supplies |
|---|---|
| `Q6F.attach_role_class` | trailing snap share, then depth rank |
| `AUD._own_history` | trailing target share (`own_share`, `own_n`) |
| `Q9.attach_hurdle_history` | the four `h_*` features and `prior_depth_bucket` |

Each walks in `(season, week, team, player)` order, reads strictly earlier
rows, and appends to its history **only when `appeared` is truthy**. A live row
therefore receives exactly what the historical builder would have given it,
and contributes nothing to anyone else's history.

### The one place the union is not enough, and it is a real defect avoided

`Q6F.attach_opportunity` assigns `targets = 0` with basis
`ZERO_BY_ABSENCE_FROM_PANEL` to any row with no panel entry. For a historical
row that is correct — a player absent from the panel took no part. For an
**unplayed** game it would fabricate a realised zero for a game that has not
happened.

So opportunity is attached to the historical rows **only**, and live rows carry
`opportunity_basis = 'UNPLAYED_NO_OPPORTUNITY'`. `assert_no_live_outcome`
then requires every realised field to be **present and `None`** — present,
because a field that is merely absent lets a later `.get(f, 0)` default it, and
that is how an unplayed game acquires a result.

---

## 2. What may and may not be read

**May:** depth-chart vintage (rank, position, team) selected point-in-time by
`DV.captured`; the official injury feed (`report_status`, `practice_status`)
via `AM.parse_injuries_rows`; the committed panel for seasons strictly before
the forecast season.

**May not**, refused by name with the measurement behind it:

| source | refusal |
|---|---|
| `weekly_rosters` | `status == INA` is game-day information: of 3,438 INA player-games, **0** recorded a snap. On the frozen candidate's `FORBIDDEN_INPUTS`. |
| `official_inactives` | published inside 90 minutes of kickoff. An appearance-layer input under its own governance, never a stage-1 feature. |
| `pbp`, `player_stats` | the outcome. |

Two guards, because they fail differently: `assert_sources_permitted` refuses a
source not on the permitted table (an undeclared source cannot be audited), and
`assert_no_roster_status` refuses a supplied player descriptor carrying any of
`status / roster_status / game_status / inactive / is_inactive / ina / active`.

**The pool comes from the depth chart, not the roster file.** The safest way
not to read a forbidden column is not to open the file it lives in.

---

## 3. Parity, measured

`Q9_LIVE_FEATURE_PARITY.json`, 2024, 96 team-games (weeks 1–3).

| question | answer |
|---|---|
| **BUILDER_PARITY** inside the window where both builders are defined | **EXACT** — 482 players compared, **0 differing** |
| **WINDOW_DIVERGENCE** outside it | 634 of 947 differ, and the divergence is **confined to the 12 history features** — the 13 source features are untouched |
| **SOURCE_AGREEMENT** — 2026 depth vintage vs a historical panel rank | 27 of 291 agree (9.3%). A **data** comparison across seasons, reported so a feed difference is never read as a builder defect |

### Why the window is week 1, and why that is not a defect

The historical builder's history window is every strictly earlier row in the
panel, **including earlier weeks of the same season**. The live builder's
window is seasons strictly before the forecast season — because the
requirement is *no 2026 outcomes*, and an earlier 2026 week **is** a 2026
outcome.

At week 1 those two windows are the same set, and parity is exact. From week 2
they are different sets **by construction**, and the live builder is required
to be the smaller one. Widening it to obtain parity would consume the forecast
season's outcomes.

The containment check is what makes this legible rather than a shrug: every
differing feature is one of the twelve driven by the history walk
(`prior_*`, `recent_participation*`, `is_cold_start`, `role_*`), and none of
the thirteen driven by the live sources (`rank_*`, `pos_*`, `inj_*`,
`expected_team_budget_standardised`, `intercept`) differs anywhere. A
difference outside that block would have been a defect.

**The `HISTORY_FEATURES` list is derived from the schema, not typed.** The
first version typed nine names, misspelled one
(`recent_participation_ewma_missing` for `recent_participation_missing`) and
omitted the three `role_*` features — so the containment check read `False` for
a divergence that was in fact entirely inside the history block. The role class
comes from **trailing snap share**, which is history, and only falls back to the
depth chart when no trail exists; it belongs there.

### An open owner decision, recorded rather than taken

- **Arm A (implemented, per the directive):** prior-seasons-only all season.
  No 2026 outcome ever enters coefficients or features. Cost: a week-8 feature
  vector is built on 2025-and-earlier history, so it goes stale as the season
  progresses, and parity with the historical builder holds only at week 1.
- **Arm B (not implemented):** a frozen prequential rule admitting
  strictly-earlier weeks of the forecast season. Parity at every week, features
  stay current — and it consumes forecast-season outcomes, which this directive
  forbids.

This changes what the candidate's evidentiary status *is*, so it is put to the
owner rather than chosen in code.

### Same-week duplicate players are excluded, and counted

Measured: the union frame carries a player under **both** teams in a
transaction week — `00-0035215` appears in 2024 week 1 as BAL and as BUF.
`Q9.attach_hurdle_history` walks `(season, week, team, player)` and appends to
a player's history as soon as it passes an appeared row, so the BAL row counts
as prior history for the BUF row **in the same week**: 42 prior appeared games
against 43.

That is the frozen historical builder's behaviour. It is **not repaired**:
`attach_hurdle_history` sits inside the frozen candidate's hashed module, and
changing it would be a candidate mutation, which this directive forbids. 348
such player-rows were excluded from the parity comparison (259 distinct
player-weeks in 2024) and the exclusion is counted so it cannot hide a real
mismatch.

---

## 4. Exact timestamp provenance, and the guard that got it wrong first

Every source carries `sha256`, `retrieved_at` and — the part that matters —
the **named basis** of that clock: `retrieved_at` when the manifest recorded
one, `capture_id` when it did not and the capture instant was used, and
`COMMITTED_ARTIFACT_IN_THIS_CHECKOUT` for the panel.

The first version parsed the capture manifest itself and required
`value.retrieved_at`. It refused **every** build with
`Q9_LIVE_SOURCE_WITHOUT_PROVENANCE`, because all 128 PASS `injuries` captures
carry `retrieved_at: null`. The clock was not missing — the capture id encodes
it, and `nfl/research/shadow/information_set.py` already falls back to it and
records which basis it used. A second copy of that logic was strictly worse
than the one that existed, so selection, the fallback and the basis are all
delegated to it. What this module adds is the refusal: a source with no usable
clock, or no blob behind its hash, does not enter a feature.

---

## 5. What the injury feed currently supplies, stated plainly

On CHI week 1, **1 of 14** players has an injury row at all, and the selected
capture carries **159** rows whose `report_status` is unfilled.

`parse_injuries_rows` stores an unfilled designation as `report_status: ''`, so
the frozen featuriser sets `inj_report_available = 1` and none of
`inj_Out / inj_Doubtful / inj_Questionable`. That is the honest encoding of *on
the report, no designation filed* — and it is the frozen candidate's behaviour,
not something this builder chose. `injury_rows` returns **every** row of the
capture, including the unfilled ones, and reports the count: dropping them
would turn an unfiled designation into an absent injury row, which is a
different and false claim.

The appearance layer refuses upstream on the same condition
(`INJURY_REPORT_INCOMPLETE`), so no live seal happens regardless. That blocker
is unchanged and is **not** cleared by this builder landing.

---

## 6. Arm A, corrected from arm B

The sealed artifact now declares `model_arm = 'A'` — *static pre-2026
benchmark, consumes no 2026 outcome at any point in the season*.

The earlier reasoning for B was that a week-8 forecast "would have weeks 1–7 in
its training window". It would not: `shadow.fit_for` trains on
`r['s'] < season` — strictly prior **seasons**, for every week — and this
builder's history window is the same set. Neither the coefficients nor the
features ever see a 2026 result. That is arm A's definition exactly, and A is
the **stronger** evidentiary status, so the correction matters.

---

## 7. Blockers are independent, and this is the worked example

The live feature builder is implemented. A live seal is still blocked. Nothing
about the first fact clears the second:

| blocker | state after this work |
|---|---|
| `LIVE_PREGAME_FEATURE_BUILD_UNIMPLEMENTED` | **implemented**; parity EXACT in-window |
| `INJURY_REPORT_INCOMPLETE` | **unchanged** — needs bytes from outside |
| `COMPLETE_ARTIFACT_LAYERS_ABSENT` | **unchanged** — see `Q9_COMPLETE_SHADOW_PARITY.json` |
| `G0A_11_OF_12` | **unchanged** — see `Q9_G0A_REMAINING_ITEM.json` |

The live seal path (`seal._seal_live`) now runs the **real** chain — depth
vintage, injury vintage, `appearance_r8.predict` — and records each game's
**actual** refusal and the stage it came from, rather than one blanket code. So
when a blocker clears, the refusal census changes without anyone editing a
status string.

---

## 8. How to run it

```
python3.12 -m nfl.prospective.q9shadow.live_features                      # schema check
python3.12 -m nfl.prospective.q9shadow.live_features --parity --season 2024 --team-games 96
python3.12 -c "from nfl.prospective.q9shadow import live_features as L; \
print(L.build_team_week(2026, 1, 'CHI', '2026-09-12T00:00:00Z', '2026-09-13T17:00:00Z'))"
python3.12 -m nfl.prospective.q9shadow.seal --season 2026                 # the real live path
```
