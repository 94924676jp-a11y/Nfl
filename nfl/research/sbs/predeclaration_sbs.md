# SBS pre-registration — a week-2 game is not a season opener

**Written before implementation.** §1 measures already-frozen components
against already-captured evidence and fits nothing. No board is sealed, no
prior candidate is touched, and **QBSEM and its failed pre-registration are not
altered**. This is a **new candidate identity**.

---

## 1. The defect, measured

`qb_allocation.previous_primary_detail(season, week)` returns, per club, the
previous primary passer and whether the club is crossing a season boundary.
Its logic is correct: it takes the most recent ordinal **strictly before** the
cut, and derives `is_season_opener` from the gap rather than from `week == 1`.

**The defect is in the data it reads.** `qb3_lib.load_qb_panel()` reads
`nfl/research/inputs/panel_p3.csv.gz`, whose QB rows are:

| season | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|
| rows | 640 | 672 | 638 | 680 | 664 | 677 | **0** |

Maximum ordinal **202518**. So for a 2026 **week 2** forecast:

- **32 of 32 clubs carry previous ordinal `202518`** — 2025 week 18.
- **32 of 32 clubs are classed `is_season_opener = True`** for a week-2 game.

Both are wrong for every club that played in week 1, which is every club.

### How wrong the incumbency signal is, where it can be checked

2026 week-1 play-by-play covers 10 games / 20 clubs. Against it:

**7 of 20 clubs (35%) currently carry the wrong previous primary** — ATL, BUF,
CLE, IND, NYJ, SEA, TEN. Buffalo is one: the current signal names
`00-0033869`, and Josh Allen (`00-0034857`) took **32 dropbacks in week 1**.
Detroit is not: Goff is the previous primary either way.

The cause is the one already recorded as `QB3_WEEK1_SEASON_BOUNDARY` — week 18
is the game a club is most likely to rest its starter in, and 40.1% of
team-seasons end with a primary who is not that season's modal starter.

### What it costs downstream, measured on the fitted model

`starter_cell(rank_bucket, was_prev_primary, is_opener)` is the cell, and the
two wrong components put the DET–BUF room in cells with a twenty-fifth of the
support:

| QB | cell now | n | `p_start` now | cell repaired | n | `p_start` repaired | Δ |
|---|---|---|---|---|---|---|---|
| Josh Allen | (1,0,1) | 90 | 0.9945 | **(1,1,0)** | **2,290** | **0.9282** | **−0.0663** |
| Jared Goff | (1,1,1) | 70 | 0.9930 | **(1,1,0)** | **2,290** | **0.9282** | **−0.0648** |
| Kyle Allen | (2,0,1) | 133 | 0.0037 | **(2,0,0)** | **2,301** | **0.0545** | **+0.0508** |
| Joshua Dobbs | (2,0,1) | 133 | 0.0037 | **(2,0,0)** | **2,301** | **0.0545** | **+0.0508** |

The model currently asserts Josh Allen starts **99.45%** of the time on the
strength of 90 opener rows in which no rank-1 quarterback ever failed to start.
On the cell his club is actually in, backed by 2,290 rows, it is **92.82%**.

**This is stated as an effect on an input, not as an improvement.** Whether
0.9282 forecasts better than 0.9945 for this game is not something this
pre-registration claims, and §4 says what would establish it.

---

## 2. Every consumer of season-boundary state

Found by searching for `previous_primary`, `prev_primary`, `was_prev`,
`is_season_opener`, `is_opener` and `use_opener` across the tree.

### Production — AUTHORITATIVE, and there is exactly one source

| consumer | what it reads | label |
|---|---|---|
| `qb_allocation.previous_primary_detail` | the panel | **AUTHORITATIVE — the single repair point** |
| `qb_allocation.allocate` → `trip[i][2]` | `prev[t] == pid` | consumer: `was_prev_primary` into the room |
| `qb_allocation._v2_shares` → `allocate_dropbacks(is_opener=…)` | `prev_detail[t]['is_season_opener']` | consumer: `is_opener` into the cell |
| `qb_room_v2.starter_cell` | both | consumer: `p_start`, and `p_relief_given_not_starter` on arms that use it |
| `qb_allocation.qb3_configuration` | both | consumer: artifact diagnosis only, changes no probability |
| `tools/market_product_export.py` | the artifact's recorded value | **read-only passthrough** |
| `product/forecast_stage.py` | a recorded value | **read-only passthrough** |

**Every production path reaches season-boundary state through
`previous_primary_detail`. One function is the repair point.**

### Research — not repaired here, and not silently left to drift

`research/qb3/qb3_lib.py` (the historical frame builder),
`qb_room_v2.previous_primary_from_panel`/`prev_primary_at` (the training
frame), `research/v2/r1/*`, `research/v2/d7/*`, `research/v3/h1/h1_analyse.py`,
`research/qb3/wk1_incumbent_audit.py`, `research/same_day_retrospective.py`,
`research/forensic_corrected.py`, `research/own3/run_own3.py`,
`research/baselines/*`.

**These build the TRAINING frame over 2020–2025 and are CORRECT as they
stand** — inside a completed season the panel has every week, so the previous
ordinal is the previous week and the opener flag is right. The defect is
specific to serving a season the panel does not yet contain.

### Not a consumer, and this matters

**R8 appearance does not read season-boundary state at all.** It reads
appearance history (`f_prev_snap`, `f_rate3`, `f_rate5`, `f_rate_ewma`,
`app_ewma`), and its 2026 week-1 rows already arrive through the W1 union
panel. **The repair does not touch R8's inputs and must not be reported as
improving R8.** The separately recorded rest-state limitation stands unchanged.

---

## 3. The repair — SBS

Give `previous_primary_detail` **current-season evidence** for weeks the panel
does not cover, in a declared order of preference, and never silently fall back.

1. **The frozen panel**, where it has a row for the season. Unchanged, and it
   remains the only source used for 2020–2025.
2. **Current-season play-by-play** — `qb_dropback == 1` grouped by
   `posteam` and `passer_player_id`, the **same definition** `primary_of` uses
   on the panel. Covers 20 clubs for 2026 week 1.
3. **Current-season snap counts** — the QB with the most `offense_snaps`.
   A **PROXY**, covering 10 further clubs, and recorded as a proxy on every row
   that uses it.
4. **Nothing.** A club with no current-season evidence keeps the panel's answer
   and is **COUNTED and NAMED** as `SBS_NO_CURRENT_SEASON_EVIDENCE`. For 2026
   week 2 that is exactly **DEN and KC**.

### On the proxy, and its measured agreement

On the 20 clubs where both sources exist the snap leader and the dropback
primary agree **20 of 20**, with **0** snap rows failing the
`pfr_id → gsis_id` bridge. Name matching is forbidden, as in
`appearance_panel_2026`.

**20 of 20 is n = 20 and is not a validated rate.** No historical snap-count
capture exists in this repository, so the proxy cannot be checked on 2020–2025.
Its risk case is a mid-game change where the starter leaves early: snaps and
dropbacks can then disagree. Play-by-play is preferred wherever it exists
precisely for this reason, and the proxy is used only to extend coverage.

### No coefficient is added

There is no rate, no threshold and no tuning knob. The repair changes **which
bytes answer an existing question**.

---

## 4. Acceptance — every gate must pass

1. **Clock.** Every current-season capture consumed must carry a retrieval
   instant **strictly before** the forecast `written_at`, enforced in code and
   refused otherwise — not asserted in prose. For this board: pbp
   `2026-09-14T00:25:56Z` and snaps `2026-09-14T18:33:36Z` against
   `2026-09-16T15:45:14Z`.
2. **Current-season only.** The repair may read **no ordinal at or after the
   forecast ordinal**. A week-2 forecast may read week 1 and must not read
   week 2. Asserted behaviourally on a seeded later-week row, not by reading
   the line.
3. **2020–2025 is bit-identical.** `previous_primary_detail` for every
   (season, week) the panel covers must return exactly what it returns today.
   The training frame must not move.
4. **Coverage is counted, never silent.** The Outcome names, per club, which
   source answered — panel, play-by-play, snap proxy, or none — and the count
   of each. A club with no evidence is NAMED.
5. **Conservation is untouched.** `sum_i db_i == V` in every draw, and team
   attempts, sacks, scrambles and rushing opportunities conserve.
6. **R8 is unchanged.** Every R8 appearance probability on the board must be
   **identical** to the unrepaired arm. If any moves, the repair has reached a
   consumer this pre-registration says it does not reach, and that is a defect.
7. **No market information.** Asserted by inspection of the diff and by the
   existing leakage test's term list.

**If any gate fails, SBS is withdrawn** and the defect stands recorded.

## 5. What this pre-registration does NOT claim

- **It does not claim a better forecast.** It claims the model is being fed the
  state that is true rather than one that is nine months stale. Whether that
  forecasts better is an out-of-sample question this board cannot answer, and
  the honest test is a forward-chained replay of weeks 2–18 across past seasons
  with the week-1 panel withheld. That is not run here.
- **It does not revive QBSEM.** QBSEM stays withdrawn. The repair happens to
  move both DET–BUF starters into a cell that *has* non-starting rows — 0 → 164
  — which is the condition that made QBSEM fall back. **That is recorded as a
  consequence and is not acted on.** No QBSEM arm is re-run under this
  candidate.
- **It does not touch Contract 3**, which is not amended.

## 6. What would make SBS wrong

- **The snap proxy is unvalidated beyond n = 20.** If it names the wrong
  primary for a club, that club's room gets a wrong cell — the same class of
  error as today, from a different cause.
- **Serve-time and training-time feature construction differ** for the 10 clubs
  on the proxy: the training frame's `was_prev_primary` is always a dropback
  primary. Small, and declared.
- **`is_opener` was measured as a mixture indicator on a frame where it was
  always correct.** Making it correct at serve time changes which mixture
  component a club draws from; if the historical estimate of that component is
  itself biased, the repair moves the error rather than removing it.
- **DEN and KC keep the stale answer** and no fix here reaches them.

**V2 NOT YET EARNED**
