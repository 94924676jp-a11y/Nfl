# WS21 — How a player ENTERS the forecast pool

**CODE CHANGED: NO.** Research only. Nothing outside
`nfl/research/parallel_pass/ws21/` was written. Repo HEAD `57d38ad`.
All measurements `python3.12`, read-only, against the sealed 2026 week-1
boards under `nfl/research/live/2026_01_*/` and the committed vintages.

---

## 0. The one-sentence answer

A non-QB enters the pool if and only if the roster vintage gives him a
`gsis_id`, a `position` string in `('WR','TE','RB')`, a `team`, and a `status`
that is **not** one of `{DEV, RES, CUT, EXE}`. A QB enters if and only if the
roster vintage gives him a `gsis_id` and `position == 'QB'`. **Nothing else is
required of either** — not a depth listing, not a prior NFL snap, not a
current-week transaction, not an eligibility signal of any kind. Measured on
all 14 boards, the sealed receiving layer equals that filter **exactly**
(L4 == L6 on every completed board, below), so no later stage removes anybody.

---

## 1. Entry-path inventory

The pool is built once, at `nfl/tools/make_board.py:149-157`, and then only
narrowed. Every path below is a way into that set, or a way past a narrowing.

### P0 — the source set: whole roster vintage, both teams, no filter
`nfl/tools/make_board.py:149` (`roster_blob = info['sources']['weekly_rosters']['blob']`)
→ `:151-153` (rows filtered to season/week/team only)
→ `:156-157` (`players = [{'gsis_id','position','team'} for r in rows]`).

* **Requires:** the row exists in the reduced roster vintage for that season,
  week and team.
* **Does NOT require:** status, depth listing, prior activity, eligibility,
  transaction, snap history, or that the player is even a football player of
  that position today. The reduced vintage carries **only**
  `season, week, team, gsis_id, position` — verified on all seven
  `nfl/vintage/weekly_rosters.*.reduced.csv.gz` blobs.
* **Observed:** 178–196 rows per game for two clubs (a 53-man limit is 106).
  Full funnel in §2.
* **Severity: HIGH** — this is the root of every path below.

### P1 — `identity_resolution`: a missing gsis_id is excluded, bounded at 1%
`nfl/production/run_forecast.py:450` (`bad = [q for q in players if not q.get('gsis_id')]`),
limit `EXCLUSION_LIMIT = 0.01` at `:51`, enforced `:461`.

* **Requires:** a non-empty `gsis_id`.
* **Does NOT require:** that the id is resolvable to anything, or that the
  excluded player is unimportant.
* **Observed:** exactly one blank-gsis row exists in *every* 2026-w1 roster
  vintage — **NYJ RB Al-Jay Henderson (DEV)**. It is excluded on
  `2026_01_NYJ_TEN` (`excluded_unidentified: [{"position":"RB","team":"NYJ",
  "reason":"NO_GSIS_ID"}]`), 1/190 = 0.53% < 1%.
* **Severity: LOW** — the mechanism behaves as documented and names its
  exclusion in the seal.

### P2 — non-QB frame check: same policy, two fields wider
`run_forecast.py:553-554` (`need = ('gsis_id','position','team')`), `:585`
(`keep`), team-emptied refusal `:589-600`.

* **Requires:** all three fields non-empty.
* **Does NOT require:** that `position` is a *real* or *current* position — any
  non-empty string passes; `RECEIVING_POS` membership is tested later as a
  plain string comparison.
* **Observed:** zero exclusions on all 14 boards (L1 == L2 everywhere).
* **Severity: LOW** as a filter, **MEDIUM** as a false assurance: passing this
  check is often read as "the frame is good", and it only means three strings
  are non-empty.

### P3 — R5 `active_roster_only`: the only eligibility filter, and it EXEMPTS QBs
`run_forecast.py:630-654`. The split is `:638-639`:
```
nonqb = [q for q in players if q.get('position') != 'QB']
qbs   = [q for q in players if q.get('position') == 'QB']
pool  = RS.active_pool(nonqb, st.value)          # :640
players = qbs + pool.value                        # :644
```
* **Requires (non-QB):** a raw roster capture observed strictly before
  `written_at` and before kickoff, carrying no `INA` row for either club
  (`roster_status.py:118-218`), and a status not in
  `EXCLUDED = {DEV, RES, CUT, EXE}` (`roster_status.py:77-80`).
* **Requires (QB): nothing.** The QB list bypasses `active_pool` entirely.
* **Observed:** 29 distinct non-ACT quarterbacks entered a sealed QB room
  across the 14 pre-inactives boards — **15 DEV (practice squad), 7 CUT
  (released), 5 RES (reserve/IR), 2 RET (retired)**. Named in §3.
* **Severity: CRITICAL.** They are not inert: §3 measures the dropback mass.

### P3a — R5 keeps any status code it does not recognise
`roster_status.py:240-249`: an unlisted code is appended to
`unrecognised` and the player is **kept** (`keep.append(q)`), reported as
`kept_unrecognised_status`.

* **Requires:** nothing beyond P0/P2.
* **Does NOT require:** that the code means "available". `RET` (retired) is not
  in `EXCLUDED`.
* **Observed, reproduced exactly by re-running `RS.status_map` +
  `RS.active_pool` on the boards' own inputs:** `kept_unrecognised_status:
  {"RET": 1}` for DAL/NYG; RET kept on **10 of 14 games** (1–5 players each).
  Two RET players reached a sealed **receiving** layer:
  **Parris Campbell (DAL WR, RET)** — 1.19% of DAL targets — and
  **Ja'Lynn Polk (NO WR, RET)** — 0.44% of NO targets.
* **Severity: HIGH.** The conservative default ("keep and name") is defensible
  as a rule, but `RET` has been sitting in the live feed for a week and nobody
  added it, and the naming does not reach the seal (P3c).

### P3b — R5 keeps any player the status map does not describe
`roster_status.py:228-234`: `st is None` → `unknown.append(...); keep.append(q)`.

* **Observed:** `n_unknown_status_kept == 0` on all 14 boards, because the raw
  and reduced vintages happen to be the same capture. **This is luck, not
  design** — see P3d.
* **Severity: MEDIUM (latent).**

### P3c — R5's own evidence never reaches the seal
`run_forecast.py:645-653` writes `fx['_r5']` (source blob, observed_at,
`dropped_by_status`, `n_unknown_status_kept`, `kept_unrecognised_status`) into
the pipeline fixture dict. **Grepped for `dropped_by_status`,
`kept_unrecognised_status`, `n_unknown_status_kept`, `active_roster`,
`roster_status` in `forecast_artifact.json`, `run_status.json` and
`board.json` of a sealed board: absent from all three.** Only the token `'R5'`
survives, via `fx['_r5_applied']` at `:654` → `:811-812`.

* **Consequence:** from a sealed artifact alone you cannot tell who was
  dropped, under what code, which roster-status vintage was consulted, or that
  a retired player was knowingly retained.
* **Severity: HIGH (auditability).**

### P3d — the pool vintage and the eligibility vintage are selected independently
The pool comes from the **reduced** blob chosen by `IS.build`
(`make_board.py:143-149`). The statuses come from a **raw** blob chosen by
`roster_status._raw_rosters()` (`roster_status.py:106-107`, `:118`, `:136-147`),
globbing `nfl_vintage/raw/weekly_rosters.*.csv` — a **different and smaller**
file population: 7 reduced vintages exist, only 4 raw ones are retained.

* **Demonstrated:** `RS.status_map(2026, 1, ['SF','LA'],
  observed_before='2026-09-10T10:00:00Z')` → PASS on
  `weekly_rosters.5ec59c5228198f57.csv`, **observed 2026-09-06T18:50:51Z**,
  while `IS.build` at the same clock selects the reduced blob
  `0b005c45d924a541` observed **2026-09-10T05:05:18Z**. A 3.6-day-stale
  eligibility map against a same-day roster, with **no refusal and no warning**.
* Not triggered on the 14 sealed boards (both selectors landed on
  `cef497eaeddef07b` / `3b0d5d40dc7816f7`), so this is **latent, not realised**.
* **Severity: HIGH (latent).**

### P4 — `RECEIVING_POS` / `CARRY_POS`: a bare string comparison on a coarse field
`nfl/production/nonqb/football_engine.py:49-50`, `:262`
(`recv = [q for q in players if q.get('position') in RECEIVING_POS]`), `:502`
(`rb = [q for q in recv if q['position'] in CARRY_POS]`).

* **Requires:** `weekly_rosters.position ∈ ('WR','TE','RB')`.
* **Does NOT require:** agreement with the depth chart, with
  `weekly_rosters.depth_chart_position`, or with what the player actually does.
* **Observed:** `position != depth_chart_position` on **1,941 of 2,963** rows
  of the consumed vintage. For skill players the collapse that bites is
  **FB → RB**: four fullbacks entered the *carry* pool and compete for the
  running-back budget on the same simplex —
  **Alec Ingold (LAC), Hunter Luepke (DAL), Patrick Ricard (NYG),
  Kyle Juszczyk (SF)**, each depth-charted `FB1`.
* **Severity: MEDIUM.**

### P5 — `participation_frame`: narrows, never adds; narrowed nothing here
`football_engine.py:349-393`. Players without an appearance draw are excluded
by name; a team emptied by that is a refusal.

* **Observed:** `L4 == L6` on all seven completed boards, i.e. the frame
  narrowed **zero** players. `excluded_no_appearance` empty everywhere.
* **Severity: NONE observed.** Working as documented.

### P6 — the QB room: every rostered QB, rank 3 by default
`nfl/production/run_forecast.py:270-271`
(`qbp = [q for q in fx['players'] if q.get('position') == 'QB' and
q.get('gsis_id')]`) → `:293` `FE.QA.allocate(...)` →
`nfl/production/nonqb/qb_allocation.py:456-458` (`by_team` built from every
supplied QB) → `:472-475`:
```
r = room.get(pid)
if r is None:
    ev['unranked_players'] += 1
    r = 3
```
* **Requires:** `position == 'QB'` and a `gsis_id`.
* **Does NOT require:** a depth listing, a status, a prior appearance, or
  membership of the active roster. An unranked QB is **ranked 3**, which is a
  real cell with real mass (`(3,0)`: n=1100, p_primary 0.0282), not a null.
* **Observed:** 27 of 111 QB-layer rows across the 23 sealed boards carry
  `depth_rank = None`; every one of them was modelled at rank 3.
* **Severity: CRITICAL** (with P3 and P7).

### P7 — the incumbent bit: keyed on LAST SEASON'S team, not this week's roster
`qb_allocation.py:193 previous_primary` / `:117 previous_primary_detail`, used
at `:476` (`int(prev.get(t) == pid)`).

Re-running `QA.previous_primary_detail(2026, 1)` and joining to the consumed
roster vintage: **5 of 32 teams' declared incumbent is not an ACT member of
that team**, and **4 more have an incumbent who has changed clubs**:

| team | declared incumbent | where he actually is in 2026 w1 |
|---|---|---|
| DAL | Joe Milton III | **DAL, DEV (practice squad)** |
| KC | Chris Oladokun | KC, **RES** |
| WAS | Josh Johnson | **CIN**, DEV |
| GB | `00-0038582` | on no 2026 w1 roster |
| TEN | `00-0032434` | on no 2026 w1 roster |
| ATL | Kirk Cousins | LV |
| BUF | Mitchell Trubisky | TEN |
| MIA | Quinn Ewers | JAX |
| NYJ | Brady Cook | MIA |

* **Requires:** that the player started his club's week-18 game last season.
* **Does NOT require:** that he is on the club now, on any roster, or active.
* **Observed cost, both directions:**
  * *Bit lands on the wrong man:* DAL's practice-squad Milton is the incumbent
    at clipped rank 3 → cell `('2+',1)`, p_primary 0.6167 → **53.32% of DAL's
    modelled dropbacks**, against Dak Prescott's 41.32%.
  * *Bit lands nowhere:* BUF, ATL, MIA, NYJ, GB, TEN lose the bit entirely
    because the incumbent left. BUF's Josh Allen is `(1,0)` not `(1,1)` —
    pools whose `P(share=0)` differ 0.4735 vs 0.0736, a factor of 6.4 — and
    BUF's practice-squad QB3 Shane Buechele collects **13.28%**.
* **Severity: CRITICAL.**

### P8 — the QB room's depth chart is chosen by FILENAME ORDER, not by clock
`qb_allocation.py:88` `fs = sorted(glob.glob(.../'depth_charts.*.csv.gz'))`,
`:93` `p = fs[-1]`. The stem is a **content hash**, so `[-1]` is lexicographic
over a hash.

* **Measured:** the last filename is `depth_charts.f57ef0724d907160`, inner
  `dt = 2026-09-08T11:56:57Z`. The **sealed artifacts declare**
  `depth_charts.a14e8dfe865a4b03`, `retrieved_at 2026-09-13T15:45:56Z`. So the
  QB room ran on a chart **five days staler than the one the seal names**.
* **Four QB rank cells differ between the two:**

| team | player | rank USED (09-08) | rank DECLARED (09-13) |
|---|---|---|---|
| JAX | Nick Mullens (ACT) | **unranked → default 3** | 3 |
| JAX | Carter Bradley (RES) | 3 | **unranked** |
| MIN | J.J. McCarthy (ACT, incumbent) | **2** | 3 |
| MIN | Carson Wentz (ACT) | 3 | **2** |

  The MIN swap moves the incumbent between cells `(2,1)` and `(3,1)`; the JAX
  swap puts a reserve/IR quarterback on the chart and demotes the active one.
* The chronology guard at `:444-451` compares the chosen file's `retrieved_at`
  to kickoff/`written_at`. It passes here **only because the lexicographic
  winner happens to be old**. It cannot detect staleness, only lateness.
* **Severity: CRITICAL** (silent stale input + provenance mismatch with the
  seal).

### P9 — R6's tier depth map is a MIXED-VINTAGE union
`run_forecast.py:680-685` calls `nfl.product.board.depth_rank(season, week,
teams)` with **no `blob`**. `nfl/product/board.py:55-77` then iterates every
`depth_charts.*.reduced.csv.gz`, takes each file's own newest `dt` slice, and
**overwrites** `out` key by key without breaking (`if blob: break` at `:76`
never fires).

* **Measured for (DAL,NYG):** the returned map has **123 entries and matches no
  single vintage** — the newest single chart has 122, the oldest 118. It is a
  union across six capture days, so a player who has since fallen off the chart
  keeps a rank from an older capture.
* The same function called **with** `blob` (from `make_board.py:187`, for the
  board display) is correct. Two call styles, one correct, one not.
* The `except Exception: dr = {}` at `:684-685` silently degrades to *no depth
  ranks at all* if that read raises.
* **Severity: HIGH.**

### P9a — three different depth-chart selectors in one run
| consumer | selector | correct? |
|---|---|---|
| appearance R8 | `depth_vintage.captured()` — pools all blobs, picks newest inner `dt` strictly before the clock | **yes** |
| QB room | `qb_allocation.captured_depth_chart()` — `sorted(glob)[-1]` | **no** (P8) |
| R6 tiers | `product.board.depth_rank(blob=None)` — union with overwrite | **no** (P9) |
| the seal's declared provenance | `IS.build` — newest observation before `written_at` | yes, but **nothing consumed it** |

### P10 — cold start: a player with zero career games, at a real share
`appearance_r8.py:474-479` declines only the cell `n_prior == 0 AND rank is
None` (`appearance_r7.py:309-311 is_unsupported`). A zero-history player **with
a depth listing is scored normally** (`state_of` → `NO_HISTORY`,
`appearance_r7.py:302-306`).

* **Observed:** **Camden Brown (DAL WR)** — roster `years_exp = 0`,
  `entry_year 2026`, undrafted, therefore `n_prior = 0` by construction —
  depth-charted WR6 and therefore scored. He took **7.26% of DAL's modelled
  targets, fifth of fourteen DAL receivers and ahead of RB1 Javonte Williams
  (4.98%)**. The prior audit
  (`nfl/research/live/2026_01_DAL_NYG/DAL_NYG_PARTICIPATION_ROOT_CAUSE_AUDIT.md`,
  finding 4) reports his appearance probability as **0.9895, the highest on the
  DAL roster**. I did not re-run the appearance layer (see §6), so that figure
  is quoted, not re-measured; the target share above **is** re-measured from
  the sealed draws.
* **Severity: HIGH.**

### P11 — the QB stat frame and the QB allocation room are built by different filters
`qb_v1.slate_prospective:192-205` drops `h_games < 1` quarterbacks unless the
C0 flag is set; `QA.allocate` (`run_forecast.py:293`) is handed the **whole**
`qbp` list regardless. With C0 off, share is allocated to a QB who has no stat
row — the module's own comment records the consequence: **5.3168% of allocated
team dropbacks reached nobody** on this very slate (OWN-1). C0 is ON in
`V1_CANDIDATE_R8` (confirmed in `candidate_components_applied` on all 14
boards), so it is not live here, but the two owners of "who is a QB this week"
remain.
* **Severity: MEDIUM (mitigated by flag, structural).**

### P12 — no transactions feed exists at all
`nfl/capture/registry.py:262-273`: `official_transactions` has
`url_template=None`, `reachability=PENDING_ENDPOINT_VERIFICATION`,
`source_status=UNVERIFIED`, `serves_kinds=()`. `nfl/ingest/eligibility.py:11`,
`:45` carry it as the open `PREDICTION_TIME_ELIGIBILITY_UNAVAILABLE` debt.
Nothing matching `transact` exists in `nfl/vintage/`.

* **Both directions of error follow from this one gap.** Practice-squad
  **standard elevations** are routine and weekly. Because no feed reports them:
  every `DEV` player is **excluded** by R5 whether or not he was elevated
  (false negative), and every `DEV` **quarterback** is **included** by the R5
  exemption whether or not he was (false positive).
* **Severity: CRITICAL (root cause of P3).**

### P13 — the rehearsal driver selects the roster by ROW COUNT
`nfl/production/rehearsal/run_slate.py:66-73`, `if len(r) > len(rows)`.

* Picks `weekly_rosters.3b0d5d40dc7816f7` (2,963 rows) with **no clock test at
  all**. Already documented against itself in
  `nfl/research/shadow/information_set.py:8-14`, which records that for
  `2026_01_NE_SEA` the row-count rule resolves to a vintage first observed
  **four hours after kickoff**.
* **Not on the sealed path** (the live boards go through `make_board`), so this
  is a rehearsal-harness defect, confirmed and contained.
* **Severity: MEDIUM (off the production path).**

---

## 2. Per-board census

Funnel rebuilt from each board's **own** declared `weekly_rosters` blob and its
own `written_at`/`kickoff_utc`, re-running `RS.status_map` + `RS.active_pool`.
Sealed counts read from `manifest['layers'][layer]['row_ids']` by id, never
positionally.

* **L0** roster rows, both clubs · **L1** after `identity_resolution`
* **L2** after the non-QB frame check · **L3** after R5 (QBs + active non-QBs)
* **L4** R5 pool ∩ `RECEIVING_POS` · **L6** sealed `receiving` row_ids
* **rush** sealed `rushing` row_ids · **QB** sealed `qb` row_ids

| game (pre_inactives) | L0 | L1 | L2 | L3 | L4 | L6 | rush | QB | R5 dropped | R5 kept unrecognised |
|---|--:|--:|--:|--:|--:|--:|--:|--:|---|---|
| ARI_LAC | 183 | 183 | 183 | 108 | 26 | 26 | 7 | 6 | CUT 27, DEV 33, RES 15 | — |
| ATL_PIT | 180 | 180 | 180 | 109 | 24 | 24 | 5 | 8 | CUT 24, DEV 31, RES 16 | RET 1 |
| BAL_IND | 184 | 184 | 184 | 114 | 26 | 26 | 6 | 8 | CUT 26, DEV 34, RES 10 | RET 3 |
| BUF_HOU | 182 | 182 | 182 | 112 | 27 | 0 | 0 | 7 | CUT 22, DEV 31, RES 17 | — |
| CHI_CAR | 189 | 189 | 189 | 113 | 27 | 0 | 0 | 8 | CUT 20, DEV 33, RES 23 | RET 2 |
| CLE_JAX | 193 | 193 | 193 | 117 | 28 | 0 | 0 | 9 | CUT 30, DEV 32, RES 14 | RET 5 |
| DAL_NYG | 178 | 178 | 178 | 112 | 30 | 30 | 9 | 6 | CUT 21, DEV 30, RES 15 | RET 1 |
| GB_MIN | 189 | 189 | 189 | 113 | 28 | 0 | 0 | 7 | CUT 27, DEV 28, EXE 1, RES 20 | RET 2 |
| MIA_LV | 196 | 196 | 196 | 112 | 29 | 0 | 0 | 8 | CUT 32, DEV 35, RES 17 | RET 2 |
| NO_DET | 189 | 189 | 189 | 112 | 26 | 26 | 7 | 8 | CUT 23, DEV 31, RES 23 | RET 1 |
| NYJ_TEN | 190 | **189** | 189 | 111 | 27 | 0 | 0 | 7 | CUT 30, DEV 30, RES 18 | — |
| SF_LA | 181 | 181 | 181 | 107 | 28 | 28 | 7 | 8 | CUT 19, DEV 34, EXE 1, RES 20 | — |
| TB_CIN | 179 | 179 | 179 | 114 | 28 | 28 | 7 | 8 | CUT 32, DEV 26, RES 7 | — |
| WAS_PHI | 181 | 181 | 181 | 112 | 27 | 0 | 0 | 8 | CUT 21, DEV 33, RES 15 | RET 4 |

**Read three things off this table.**

1. **L4 == L6 on every board that produced a receiving layer.** The sealed
   receiving pool is *exactly* "roster row, skill position, status not in
   {DEV,RES,CUT,EXE}". No later stage — appearance, participation, targets —
   removes a single player. The filter in §0 is the whole story.
2. **Six of fourteen games produced NO non-QB layer at all**
   (BUF_HOU, CHI_CAR, CLE_JAX, GB_MIN, MIA_LV, NYJ_TEN, WAS_PHI — seven boards
   counting phases; `absent_layers` lists `targets_carries`, `conversion`,
   `td_layer`, and for five of them `appearance` and `participation` too,
   `completeness: PARTIAL_PLAYER_COVERAGE`). Those boards are QB-only, so the
   non-QB pool census for them is the *counterfactual* L4, not a sealed count.
3. **`2026_01_NYJ_TEN` shows `R5`, `R6`, `R8` in NEITHER
   `candidate_components_applied` NOR `candidate_components_not_reached`.**
   Applied is `['A1','A3G','C0','R2','SC1']`, not-reached is `[]`. Per the
   brief's own rule, ACTIVE must not be inferred from omission — and here the
   omission is on both lists at once, which is not a state the artifact
   vocabulary can express. **UNRESOLVED**, flagged for whoever owns the
   component manifest.

### Sealed layer membership by roster status

Across the 14 `pre_inactives_V1_CANDIDATE_R8` boards (all 23 boards in
parentheses):

| layer | ACT | DEV | RES | CUT | RET |
|---|--:|--:|--:|--:|--:|
| qb | 82 (111 total rows) | **15** (27) | **5** (7) | **7** (13) | **2** (3) |
| receiving | 186 | 0 | 0 | 0 | **2** (3) |
| rushing | 55 | 0 | 0 | 0 | 0 |

29 non-ACT quarterbacks and 2 retired receivers entered sealed layers.

---

## 3. What the non-ACT quarterbacks were actually worth

Mean dropbacks and team share read from each board's own `qb/db` draw matrix,
rows resolved through `manifest['layers']['qb']['row_ids']`.

| game | team | status | player | mean DB | team share | P(DB ≥ 10) |
|---|---|---|---|--:|--:|--:|
| DAL_NYG | DAL | **DEV** | Joe Milton III | 21.67 | **0.5332** | 0.6012 |
| GB_MIN | GB | DEV | Kedon Slovis | 4.57 | 0.1370 | 0.2170 |
| BUF_HOU | BUF | DEV | Shane Buechele | 4.82 | 0.1328 | 0.2670 |
| NYJ_TEN | NYJ | DEV | Bailey Zappe | 4.45 | 0.1276 | 0.2860 |
| NYJ_TEN | TEN | DEV | Hendon Hooker | 4.03 | 0.1025 | 0.1380 |
| MIA_LV | MIA | **CUT** | Cam Miller | 3.66 | 0.0996 | 0.0960 |
| NYJ_TEN | TEN | **CUT** | Will Levis | 3.78 | 0.0961 | 0.1190 |
| WAS_PHI | WAS | DEV | Sam Hartman | 3.35 | 0.0961 | 0.0870 |
| NO_DET | DET | **RET** | Teddy Bridgewater | 1.03 | 0.0284 | 0.0290 |
| CHI_CAR | CAR | **RET** | Will Grier | 0.85 | 0.0250 | 0.0090 |
| DAL_NYG | NYG | DEV | Jake Haener | 1.02 | 0.0311 | 0.0355 |
| *(18 further rows, all 0.019–0.028)* | | | | | | |

**Aggregate, 28 team-sides on the 14 pre-inactives boards:**
22 sides carry non-zero non-ACT quarterback mass; mean 6.51%, median 2.95%,
max 53.32%; total 1.8234 team-share units — i.e. **the equivalent of almost two
entire teams' dropbacks** allocated to quarterbacks who were on a practice
squad, on reserve, released, or retired. Eight sides exceed 5%: DAL 0.5332,
TEN 0.1986, GB 0.1370, BUF 0.1328, NYJ 0.1276, MIA 0.0996, WAS 0.0961,
DET 0.0546.

**Both named cases verified.** Jake Haener (NYG QB3, DEV, unranked → rank 3,
`prev=0`) = **0.0311**. Joe Milton III (DAL, **DEV/practice squad**, unranked →
rank 3, but `was_prev_primary = 1`) = **0.5332**. The difference between them
is P7 alone: same status, same default rank, opposite incumbent bit.

**Parris Campbell generalises.** He is not the only pool member with no depth
rank in the chart the board declares: `2026_01_DAL_NYG`'s receiving layer holds
three — Campbell (RET), **Darius Slayton (NYG WR, ACT)** at 0.81% of targets,
and **Chris Manhertz (NYG TE, ACT)** at 0.04%. Across the 23 boards, **27 of
111 QB rows** carry no depth rank in the vintage the QB layer actually reads.
Rank `None` is never a barrier: for receivers it is simply a feature bucket
(`appearance_r7.py:321-325`, bucket `'unlisted'`), for quarterbacks it is
silently promoted to rank 3.

---

## 4. Identity hazards

Measured on the consumed vintage `weekly_rosters.cef497eaeddef07b` (2026 w1,
2,963 rows) and `depth_charts.a14e8dfe865a4b03`, plus all seven roster
vintages.

| hazard | result | severity |
|---|---|---|
| **duplicate `gsis_id` across teams in one week** | **0** in every one of the seven roster vintages | none |
| **same player on two rosters in one week** | **0** | none |
| **duplicate row for one player on one team** | **0** | none |
| **duplicate row id inside a sealed layer** | **0** across all 23 boards × 3 layers | none |
| **rushing ⊄ receiving, or QB ∩ receiving** | **0** — layer nesting is clean | none |
| **blank `gsis_id`** | **exactly 1** in every vintage: NYJ RB Al-Jay Henderson (DEV). Handled by P1 | low |
| **alias collision (one name, two `gsis_id`)** | **8 pairs league-wide**, e.g. *Justin Jefferson* (MIN WR `00-0036322` / CLE LB `00-0041075`), *DeVonta Smith* (PHI WR / CAR DB), *Cam Miller* (MIA QB / CAR DB), *Devin Neal* (NO RB / JAX DB). **All eight are cross-team.** `inactives.resolve` (`nfl/production/nonqb/inactives.py:460-509`) keys on `(team, normalised_name)` and refuses on ambiguity, so team scoping defends every one. **Same-team collisions: 0** on both the exact and suffix-stripped key. | **latent**, defended this week by data luck, not by construction |
| **position disagreement, roster vs depth chart** | 1,307 of 1,962 depth-charted players — but almost all are defensive alignment tokens (`LDE`, `WLB`, `RCB`). Restricted to skill: **roster-skill with no skill depth slot = 0; depth-skill with non-skill roster position = 0.** The real skill-position hazard is the coarse roster field: `position != depth_chart_position` on **1,941 of 2,963** rows, and FB→RB puts 4 fullbacks in the carry pool (P4) | medium |
| **team disagreement, roster vs depth chart** | **1**: Bryce Cabeldue, rostered **SEA**, depth-charted **LV** | low (not in a week-1 board's two clubs) |
| **QB set disagreement** | 119 QBs by roster vs 92 by depth chart; **27 roster-QBs have no QB depth row** → all promoted to rank 3 (P6). Zero depth-QBs missing from the roster | high |
| **non-`gsis`-shaped ids in the depth chart** | **3**: `WAS569019` (**LV, RB, rank 2**), `BAI173035` (NYJ LDE2), `THO581952` (SF RDT2). The LV one matters: LV's real RB2 is almost certainly **Mike Washington Jr. `00-0040878` (ACT)**, who carries **no depth row at all** — so the rank exists in the feed and can never join to the pool | high |
| **blank `gsis_id` in the depth chart** | **5** rows at the newest `dt`, including **CHI QB4** and **NYG TE3**. CHI's board shows *Miller Moss (CHI QB, ACT)* with `depth_rank = None` — the orphaned QB4 row | high |
| **depth-charted but absent from the roster vintage** | **9**, including `00-0036261` listed **SF WR8** | medium |

---

## 5. Finding table

| # | claim | status | evidence |
|---|---|---|---|
| 1 | Jake Haener (NYG QB3) received 3.1% of NYG dropbacks | **CONFIRMED** | 0.0311 from `qb/db` of `pre_inactives_V1_CANDIDATE_R8/3dddf9f62c9260b0`; DEV status from `weekly_rosters.cef497eaeddef07b` raw |
| 2 | Joe Milton III (practice squad) received 53.3% of DAL dropbacks | **CONFIRMED** | 0.5332, same board. Mechanism = P3 (QB R5 exemption) × P7 (incumbent bit) |
| 3 | Camden Brown (n_prior = 0) drew the highest appearance probability on the DAL roster | **PARTIAL** | Zero career games confirmed independently (`years_exp 0`, `entry_year 2026`, undrafted). Target share 7.26%, 5th of 14, ahead of RB1, re-measured from sealed draws. The 0.9895 probability itself is **quoted** from the DAL_NYG root-cause audit, not re-measured here |
| 4 | Parris Campbell had depth rank None yet entered the pool | **CONFIRMED, and generalised** | Entry mechanism identified precisely: `RET ∉ EXCLUDED` → `kept_unrecognised_status {"RET": 1}`, reproduced by re-running `RS.active_pool`. Two more no-depth-rank receivers on the same board; 27 of 111 QB rows have no rank |
| 5 | The R5 `active_roster_only` block exempts QBs | **CONFIRMED** | `run_forecast.py:638-639`; 29 non-ACT QBs in sealed rooms; 1.8234 team-share units of dropbacks |
| 6 | `EXCLUSION_LIMIT` lets an unidentifiable player through silently | **FALSIFIED** | The one blank-gsis row is excluded AND named in `excluded_unidentified` in the seal. The mechanism is sound and auditable |
| 7 | The `participation_frame` narrowing silently drops real players | **FALSIFIED** | Narrowed zero players on all seven completed boards; `L4 == L6` exactly |
| 8 | Duplicate `gsis_id`s / two-roster players / duplicate layer rows exist | **FALSIFIED** | 0 in all seven roster vintages and all 23 boards |
| 9 | Alias collisions can write the wrong man onto an inactive list | **PARTIAL** | 8 collisions exist, all cross-team; `resolve` is team-scoped and refuses on ambiguity; 0 same-team collisions this week. Real but not realised |
| 10 | The QB room reads a different depth-chart vintage than the seal declares | **CONFIRMED** | `qb_allocation.py:88,93` → `f57ef0724d907160` (09-08); artifacts declare `a14e8dfe865a4b03` (09-13). 4 QB rank cells differ (JAX ×2, MIN ×2) |
| 11 | R6's tier depth map is a single vintage | **FALSIFIED — it is a mixed-vintage union** | `board.depth_rank(blob=None)` returns 123 entries for (DAL,NYG); no single vintage has 123 (newest has 122) |
| 12 | `previous_primary` tracks the club, not the player's current roster | **CONFIRMED** | 5 of 32 teams' incumbent is not an ACT member of that team; 4 more have departed to other clubs |
| 13 | R5's exclusion evidence is recorded in the sealed artifact | **FALSIFIED** | `dropped_by_status`, `kept_unrecognised_status`, `n_unknown_status_kept`, `roster_status_source` absent from artifact, run_status and board |
| 14 | The pool and eligibility vintages are pinned to the same capture | **FALSIFIED (latent)** | 7 reduced vs 4 retained raw; at `written_at 2026-09-10T10:00Z` the two selectors are 3.6 days apart, with no refusal. Not triggered on any sealed board |
| 15 | A practice-squad elevation can be seen before kickoff | **FALSIFIED** | No transactions feed exists (`registry.py:262-273`, `url_template=None`). Root cause of P3 in both directions |
| 16 | The rehearsal driver selects the roster by clock | **FALSIFIED** | `run_slate.py:71` selects by row count; already self-documented at `information_set.py:8-14` |
| 17 | Fullbacks are excluded from the running-back carry pool | **FALSIFIED** | 4 FBs (Ingold, Luepke, Ricard, Juszczyk) enter via `position == 'RB'` on the coarse roster field |
| 18 | `2026_01_NYJ_TEN` ran with R5/R6/R8 | **UNRESOLVED** | The components appear on neither the applied nor the not-reached list. Cannot be settled from the artifact, and must not be inferred from omission |
| 19 | An excluded DEV player actually played in week 1 (R5 false negative) | **UNRESOLVED** | Not testable — no box-score participation data exists for these games (§6) |

---

## 6. Evidence ceiling

1. **No box scores.** Only `2026_01_SF_LA` carries a `REALIZED_OUTCOMES.json`,
   and its own provenance block calls it
   `OWNER_SUPPLIED_SUMMARY` — 6 named actors, not a box score, explicitly
   `NOT a fetched, hashed artifact`. `snap_counts_2026` holds 93 rows and
   **0 for SF or LA**. So the **false-negative direction of R5** — an elevated
   practice-squad player who actually took snaps and was excluded from the pool
   — **cannot be tested anywhere in this repository**. Finding 19 stays
   UNRESOLVED, and that is a data gap, not a null result.
2. **The appearance layer was not re-run.** It costs ~76s per board and other
   agents hold the tree. Every appearance probability in this document is
   quoted from `DAL_NYG_PARTICIPATION_ROOT_CAUSE_AUDIT.md` and labelled as
   quoted; every *share* figure is re-measured from the sealed draw matrices.
3. **Seven of 14 games have no sealed non-QB layer.** Their L4 column is a
   re-derivation of what the pool *would* have been, not a sealed count.
4. **Statuses are only recoverable where a raw capture was retained** — 4 of 7
   vintages. Both vintages the 14 boards actually consumed
   (`cef497eaeddef07b`, `3b0d5d40dc7816f7`) are retained, so every status in
   this document is read from the board's **own** vintage. One ad-hoc
   intermediate dump in the working notes mixed `cef497` statuses into the
   SF/LA rows and showed spurious `INA` codes; the census tables above do not,
   and the SF/LA row uses `3b0d5d40`.
5. **No postgame information entered any pregame reasoning here.** The single
   realised-outcome read in §6.1 was a *frame-coverage* check (did the pool
   contain everyone who produced?) and returned nothing usable at n=6.
6. **No sportsbook data was opened.**

---

## 7. Severity roll-up

**CRITICAL** — P3 (QB exemption from the only eligibility filter), P7 (incumbent
bit keyed on last season's club), P8 (QB depth chart chosen by filename hash),
P12 (no transactions feed).

**HIGH** — P0 (whole-roster source set), P3a (unrecognised status kept), P3c
(R5 evidence never sealed), P3d (pool and eligibility vintages selected
independently), P9 (mixed-vintage tier map), P10 (cold start at a real share),
and the depth-chart identity hazards (orphaned `WAS569019`/blank-id rows,
27 unranked QBs).

**MEDIUM** — P2, P4 (FB→RB), P11 (two owners of "who is a QB"), P13 (rehearsal
row-count selection), alias collisions (latent).

**LOW / NONE** — P1, P5, and every duplicate-identity check.

**CODE CHANGED: NO.**
