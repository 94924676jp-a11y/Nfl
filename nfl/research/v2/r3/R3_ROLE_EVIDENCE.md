# R3 — role evidence: the two repairs, measured

**Repo** `/home/user/nfl`, branch `claude/nfl-greenfield-architecture-stsxmk`,
HEAD at start `2dc44ab`. `python3.12`. Written 2026-09-14, before kickoff.

**Files changed, and only these:** `nfl/production/nonqb/depth_vintage.py`,
`nfl/production/nonqb/role_prior.py`, new `nfl/tests/test_role_evidence.py`.
Nothing under `nfl/product/`, `layers.py`, `qb_*`, `football_engine.py`,
`rushing_a1.py` or the eligibility modules was opened for writing. No commit,
no add, no stash, no push. No sportsbook data was read. No floor, no tuning
toward any external number.

**Q9 hash check.** `sha256(nfl/production/nonqb/layers.py)` =
`481f005f682cd72129e6bf02e55cba86913ddffd7d88367743c616e3e11c0108`, sha16
`481f005f682cd721`. Matches the Q9 frozen identity exactly. Verified twice,
before and after all edits. Unchanged.

**Suites, `run_suite.py --only <module>` only:**

| suite | result |
|---|---|
| `test_role_evidence` (new) | PASS — 16 functions, 67 checks, 0 failing, 0 blocked |
| `test_r6_role_prior` | PASS — 8 functions, 24 checks |
| `test_r7_appearance_frame` | PASS — 20 functions, 67 checks |
| `test_vintage_selector` | PASS — 24 functions, 131 checks |
| `test_product_attribution` | PASS — 17 functions, 71 checks |

---

## 0. The short version

Defect 1 is repaired and it was biting hard historically. Repairing it exposes
something the contamination had been hiding: **the 2020-2024 weekly vendor does
not publish a WR1/WR2/WR3 order at all.** 98.5% of WR rooms list two or three
players at `depth_team 1` with nothing to separate them. The module now emits a
depth GROUP and says so, rather than manufacturing an ordinal.

Defect 2 is repaired structurally — the two-pass ordering is gone, not patched.
On tonight's board it moves nothing above tier 2, exactly as D2 predicted.

**One finding disagrees with D4 and I am reporting it rather than defending the
repair.** D4's cohort of 47 does not reproduce from the artifact, and on the
cohort that does reproduce the realised target share is 0.0659, not 0.1031. The
repair is still right, and §3.3 gives the number that actually carries it.

---

## 1. Defect 1 — the receiver ordering was a special-teams ordering

### 1.1 What the old code did

`depth_vintage.weekly` took each player's MINIMUM `depth_team` across **all** of
his listed slots, then ordered the room by `(depth_team, depth_position)`.
`depth_position` is a string and `KOR < KR < PR < WR` alphabetically, so the
returner sorted first.

### 1.2 The 68.5%, reproduced — and a definitional correction

Staged leaves `dc_2021…dc_2024`, `game_type == REG`, `position in SKILL`.
**2,432 WR team-weeks and 2,432 RB team-weeks, matching D5 exactly.**

| position | rank-1 slot was a return slot (KR/PR/KOR) | rank-1 slot was not the plain offensive slot |
|---|--:|--:|
| WR | 1,649 / 2,432 = **0.6780** | 1,665 / 2,432 = **0.6846** |
| RB | 616 / 2,432 = 0.2533 | 1,553 / 2,432 = 0.6386 (incl. `FB` 796 = 0.3273) |
| TE | 0 / 2,431 = 0.0000 | 70 / 2,431 = 0.0288 |
| QB | 4 / 2,431 = 0.0016 | 19 / 2,431 = 0.0078 |

**The 68.5% in `D5_ZERO_MASS_AUDIT.md` line 462 is the second column, not the
first.** `2,432 − 767 = 1,665` and `767/2,432 = 0.3154` is D5's own "genuine
`WR` slot only 31.5%". The 16-row gap between 1,649 and 1,665 is 9 blank slots
and 7 `LWR` rows — `LWR` is an offensive slot, so it is not return
contamination. D5's component figures (PR 44.1%, KR 21.0%, KOR 2.7%; RB KR
18.7%, PR 3.4%, KOR 3.3%, FB 32.7%, RB 36.1%) reproduce to the digit. Only the
two headline aggregates differ, and D5's RB headline (26.9%) is inconsistent
with D5's own components, which sum to 25.4% and match my 25.33%. Not worth an
escalation; worth not quoting either headline as a return-slot rate.

### 1.3 The repair

`weekly` now builds the offensive ordering from `formation == 'Offense'` rows
only, and **the slot string is no longer in the sort key at all** — an alphabet
is not a depth chart. The row counts are on the artifact:
35,983 `Offense`, 8,734 `Special Teams`, 51 `Defense` across 2021-2024.

`RETURN_SLOTS = ('KR', 'PR', 'KOR')` is now a module constant policing both
feeds, and a return slot filed under the offensive formation is excluded too
(measured 0 on 2021-2024; counted so a vendor change is visible rather than
silent). `SPEC_VERSION` is bumped to `depth-vintage-pit-2-offensive-role-only`,
because the old string described a different quantity.

A leaf without a `formation` column is **refused by name**
(`DEPTH_WEEKLY_LEAF_MISSING`, `seasons_without_formation_column`). Without that
column the only construction available is the contaminated one, and falling
back to it silently is the defect wearing a permit.

### 1.4 What the repair exposes — the uncertainty I left explicit

After removing the contamination there is, for receivers, **almost no ordering
underneath it**:

| position | rooms | rooms with >1 player sharing `depth_team 1` | size of that top group |
|---|--:|--:|---|
| WR | 2,432 | **2,396 (0.9852)** | 2 in 1,144, 3 in 1,250, 4 in 2 |
| RB | 2,432 | 943 (0.3877) | 2 in 888, 3 in 55 |
| TE | 2,431 | 519 (0.2135) | 2 in 519 |
| QB | 2,431 | 9 (0.0037) | 2 in 9 |

So `weekly` now returns a **depth GROUP**, not a unique ordinal. All three
players the chart calls first-team carry group 1; `detail=True` returns
`tie_size` and `resolved` per player. Nothing invents 1/2/3 out of a three-way
tie — inventing it is what produced the defect.

A player listed **only** on special teams gets no offensive rank at all
(115 such players over 2021-2024, counted on the artifact as
`n_players_listed_only_off_offence`). "The chart lists him as a returner" and
"the chart does not list him" are different facts and the old key rendered them
the same.

Evidence now carried on every `weekly` outcome: `ordering_key`,
`n_offensive_rows`, `n_special_teams_rows_excluded`,
`n_return_slot_rows_under_offence_excluded`, `n_rooms`,
`n_rooms_with_unresolved_top_group`, `top_group_size_histogram`,
`n_players_listed_only_off_offence`, `uncertainty`, `value_is`.

### 1.5 The realised zero-target rate — old ordering versus new

Panel joined to 2,174 played team-games, 2021-2024, WR.

**All charted players (D5's basis — a chart row with no panel row counts as
zero targets):**

| chart position | OLD ordinal | n | NEW offensive group | n |
|---|--:|--:|--:|--:|
| 1 | **0.3528** | 2,174 | **0.1263** | 5,446 |
| 2 | 0.1559 | 2,174 | 0.4429 | 4,696 |
| 3 | 0.1567 | 2,170 | 0.6480 | 1,551 |
| 4 | 0.3085 | 2,120 | — | — |
| 5+ | 0.5496 | 3,102 | — | — |

The OLD column reproduces D5 line 472-473 (0.3520 / 0.1570 / 0.1572) to within
0.001. **OLD is non-monotone at the top; NEW is strictly monotone.**

**Appeared players only:**

| chart position | OLD | n | NEW | n |
|---|--:|--:|--:|--:|
| 1 | 0.1914 | 1,740 | **0.0319** | 4,915 |
| 2 | 0.0438 | 1,919 | 0.2700 | 3,582 |
| 3 | 0.0620 | 1,951 | 0.3886 | 893 |

Also monotone, and for reference D5's usage-tier lens gives 0.0892 / 0.1486 /
0.2548. The repaired chart group now discriminates zero-target risk **more
sharply than the usage tier does**, which is the opposite of the prior state.

**RB, appeared only:** OLD 0.3236 / 0.2182 / 0.2946 / 0.4104 (non-monotone,
dips at 2) → NEW 0.2391 / 0.2795 / 0.4483 (monotone).

Group sizes are large because a group is a set: ~2.3 first-team receivers per
team-game. That is the honest shape of this vendor's chart.

### 1.6 What I did NOT repair, and why — read this before tonight

**The daily (ESPN, 2025-2026) path does not carry the return contamination, and
I verified that rather than assuming it.** `KR` and `PR` are `pos_abb` values in
that feed, so `pos not in SKILL` already drops them. Across the six persisted
blobs, 1,238 return rows are read and 0 reach a rank. Now recorded as
`n_return_slot_rows_excluded` / `return_slot_pos_abb_seen`.

**But that path has a different contamination, and I left it in place.**
`daily` keys its snapshot on `(team, dt)` and ordinals **across all skill
positions at once**, so a club's `pos_rank == 1` QB, RB, WR and TE compete for
one ordinal and are separated only by `gsis_id`. Measured over the 224
team-snapshots held: rank 1 is a **QB in 90, RB in 63, TE in 57, WR in only
14**. Tonight KC's emitted rank-1 is a tight end and every KC receiver lands in
the `r4plus` bucket.

I did not change it, for one reason and it is not timidity: the appearance
layer's rank-bucket coefficients were **fitted on this scale**, and moving the
serve-time scale without refitting would manufacture a train/serve skew three
hours before kickoff — a worse defect than the one it fixes, and in a layer I do
not own the consequences of. It is now **declared on the artifact**
(`rank_scale`, `rank_1_position_mix`) so no consumer can read `rank` as "WR1"
without seeing that it is not. **This is a live open defect and it is handed
back, not closed.** The repair is a within-`pos_abb` ordinal plus a refit, and
it belongs to a sequenced change, not to tonight.

**A latent one for whoever owns `nfl/product/board.py`.** `board.depth_rank`
(`:216`) writes `out[r['gsis_id']] = (r['pos_abb'], int(r['pos_rank']))` with no
position filter, so **the last row for a player wins** — a receiver who is also
`PR1` can have his board depth rank replaced by his punt-return rank. Measured
on tonight's selected chart: **KC 0 players affected, DEN 1 (`00-0038552`, an
`RCB1` who is also `PR2`, not a skill player and not in the `assign_tiers`
room). So it does not bite tonight.** The one-line fix is to skip rows whose
`pos_abb` is in `depth_vintage.RETURN_SLOTS`, or to prefer the offensive row.
I do not own that file and have not touched it.

---

## 2. Defect 2 — stale history could not be outranked

### 2.1 What the old code did

`assign_tiers` sorted everyone **with** a trailing snap share, then appended
everyone else starting at `start = len(known)` (`role_prior.py:170`). A player
the current chart ranks first but with no trailing history sat below **every**
veteran with any history at all, however little. `role_prior.weight` returns the
tier mean **exactly** at `n_own = 0`, so for those players the tier was not a
prior on a history — it was the entire forecast.

### 2.2 The repair — one scale, no ladder

The two passes are **gone**. Every player in a `(team, position)` room is placed
by one expected snap share:

```
score = w * own_trailing_snap + (1 - w) * anchor,     w = n / (n + k_snap)
```

* `anchor` is the **measured** mean snap share of the tier his **current** depth
  listing puts him in. Estimated in `build` by the same construction the class
  prior already uses (appeared rows, ≥50-observation floor). At cut 202601:
  WR 0.8150 / 0.7406 / 0.5970 / 0.3271, TE 0.7115 / 0.4512 / 0.3049 / 0.2290,
  RB 0.5981 / 0.3768 / 0.2377 / 0.1964.
* `k_snap` is the empirical-Bayes within/between-player variance ratio **of snap
  share** — not reused from the class-share `k`, because a target share and a
  snap share are different quantities and reusing one constant for both is the
  silent-constant defect this module exists to end. At cut 202601:
  WR 0.800, TE 0.671, RB 0.882.
* `n` is how many trailing observations the player actually has.
* No listing → anchor on the **deepest measured tier**. That is the old
  behaviour made continuous instead of categorical.

**There is no promotion rule.** No ladder, no "rank 1 gets tier 1", no player or
team named. Which of two players ends up higher is decided by that arithmetic in
both directions, and the guard test asserts both directions: a no-history chart
leader can rise, **and** an established starter is not displaced by one.

`build` now **refuses by name** (`ROLE_PRIOR_SNAP_ANCHOR_UNIDENTIFIED`) if
either anchor is unidentified, so production cannot silently fall back. A prior
of the old shape still works, but returns `degraded: True` with
`degraded_reason` naming exactly what was missing — the legacy path exists and
can never be reached quietly.

### 2.3 The 47-of-47 cohort, re-run — and where I disagree with D4

Replayed on week 1 of 2021-2024, WR/TE/RB, `TRAIL = 8`, charts `dc_2021…2024`.

**What reproduces exactly:** **384 `(team, position)` rooms** and **1,344 week-1
skill rows** — both of D4's structural figures, on the population "appeared
week-1 panel rows". So I am on D4's population.

**What does not reproduce: the 47.** On that population the cohort of
chart-rank-1 players with no trailing history is **19**, not 47. I swept twelve
definitions — normalised vs raw position, REG-only vs all, "no trailing snap" vs
"no class history" vs "no prior panel row", absolute vs room-relative rank-1,
panel-appeared vs chart-listed vs their intersection — and the largest cohort I
can construct from the artifact's stated inputs is 43 (chart-listed universe,
un-normalised positions), which contradicts D4's own 384 rooms / 1,344 rows.
**D4 does not publish the cohort's ids, so the 47 is not reconstructible from
the artifact.** This is the same class of gap D2 named on the board rows, one
level up.

**And the 0.1031 does not survive either, for a reason that matters.** On the
19-player cohort as the OLD chart defines it, realised week-1 target share is
**0.0659**, not 0.1031 — because under the OLD chart "rank 1" is largely the
*returner*, and returners genuinely do not draw targets. The two defects were
entangled: D4's cohort was selected by the contaminated chart.

**So here is the number that actually carries the repair.** Define the cohort by
the **repaired offensive** chart — the players the offensive chart calls
first-team who have no trailing history. n = 30 over the four openers.

| | legacy assigner | repaired assigner |
|---|--:|--:|
| below tier 1 | **30 of 30 (1.0000)** | 15 of 30 |
| assigned tiers | 2:3, 3:9, 4:8, 5:8, 6+:2 | 1:15, 2:12, 3:3 |
| implied target share | **0.0616** | 0.1550 |
| realised target share | **0.1289** | 0.1289 |
| error | **−0.0673 (−52.2%)** | +0.0261 (+20.2%) |

**The 100%-below-tier-1 rate reproduces exactly, the direction reproduces, and
the magnitude is worse than D4 reported — 52% understated, not 41%.** The repair
overshoots by 20% in the other direction; absolute error falls by 61%. I am not
claiming the overshoot is zero and I would not tune it away: it is the honest
output of an estimated anchor, and it is now visible on the artifact.

### 2.4 Population-level scoring, all 1,344 week-1 rows

Two treatments, each isolated. **Bias cannot move here and that is structural,
not a bug:** the tiers assigned inside a room are always a permutation of
`1..n`, so the multiset of implied values per room — and hence the population
mean — is invariant. Only the matching of value to player changes. MAE and
concordance are the metrics that can move.

| chart | assigner | MAE (implied vs realised target share) | within-room concordance (tier order vs realised order) |
|---|---|--:|--:|
| old | legacy | 0.06095 | 0.7348 (n=1,697 pairs) |
| old | **repaired** | 0.05966 | 0.7496 |
| **new** | legacy | 0.06088 | 0.7384 |
| **new** | **repaired** | **0.05967** | **0.7566** |

Both repairs move it the right way, they compose, and neither is large. This is
**exploratory**: these four openers selected nothing here, but the panel is the
same one the priors are fitted from, and a confirmatory claim needs games no
part of this pipeline has seen.

---

## 3. Tonight — DEN and KC, before and after

Prior built at `ordinal_cut = 202601`. Depth ranks from
`board.depth_rank_outcome(2026, 1, ('KC','DEN'), as_of='2026-09-15T00:15:00Z')`,
`DEPTH_RANK_OK`. Assignment run both ways on the same rooms. Nothing was
re-sealed and no board was rewritten.

### 3.1 On the rooms the sealed board actually carries (D2's screen)

| room | player | chart | old tier | new tier |
|---|---|--:|--:|--:|
| KC RB | Kenneth Walker III | RB1 | 1 | 1 |
| KC RB | **Emmett Johnson** | RB2 | 3 | **2** |
| KC RB | **Brashard Smith** | RB3 | 2 | **3** |
| KC TE | Travis Kelce | TE1 | 1 | 1 |
| KC TE | Noah Gray | TE2 | 2 | 2 |
| KC TE | **Jake Briningstool** | TE4 | 4 | **3** |
| KC TE | **Jared Wiley** | TE3 | 3 | **4** |
| KC WR | Xavier Worthy | WR2 | 1 | 1 |
| KC WR | Rashee Rice | WR1 | 2 | 2 |
| KC WR | **Cyrus Allen** | WR4 | 6 | **3** |
| KC WR | **Tyquan Thornton** | WR3 | 3 | **4** |
| KC WR | **Jalen Royals** | WR5 | 4 | **5** |
| KC WR | **Nikko Remigio** | WR6 | 5 | **6** |

**Tier 1 and tier 2 are unchanged in every room.** D2's caution holds exactly:
0 rank-1 displaced before, 0 after.

**D2's three mild inversions are now attributable, which D2 said the artifact
could not do.**

1. **KC RB — Emmett Johnson, chart RB2, model rank 3 behind chart RB3 Brashard
   Smith. This one IS the defect, and the repair removes it.** Johnson has no
   trailing history, so the old code appended him after Smith regardless.
   Repaired: Johnson scores the measured RB2 anchor 0.3768, Smith scores
   0.1812 from eight games at 17.5% snap share. Johnson moves above. Chart-order
   inversions in that room: **1 → 0**.
2. **KC TE — Jared Wiley (TE3) behind Jake Briningstool (TE4). NOT the defect,
   and the repair keeps the inversion.** Wiley's own eight games at 16.5% snap
   share score 0.1758 against the measured TE4 anchor 0.2290. The chart says
   Wiley is ahead; his own record says otherwise, and now the artifact carries
   the number rather than leaving it unattributable. Room inversions 0 → 1 —
   the repair makes this room *disagree* with the chart more, on evidence.
3. **KC WR — Tyquan Thornton (WR3) behind Cyrus Allen (WR4). NOT the defect,
   and near-tied.** Thornton 0.3009 (eight games at 27.1%) against the WR4
   anchor 0.3271. Room inversions 3 → 2.

### 3.2 On the full eligible pool (51 skill players, 14 KC WR / 11 DEN WR)

Same result at the top, movement below it. Named movers, old → new tier:

* **KC WR** — Worthy 1→1, Rice 2→2, Brownlee 3→3 unchanged. Then
  Thornton 4→11, Royals 5→12, Remigio 6→13, Holiday 7→14 all fall, while
  Armstrong 10→4, Allen 8→5, Caldwell 9→6, Evans 11→7, De Jesus 12→8,
  Loyd 13→9, Weimer 14→10 all rise.
* **KC TE** — Kelce 1→1, Gray 2→2 unchanged; Wiley 3→7 falls; Odukoya 6→3,
  Pline 7→4, Briningstool 4→5, Gyllenborg 5→6.
* **KC RB** — Walker 1→1 unchanged; **Emmett Johnson 3→2**; Brashard Smith 2→7;
  VanSumeren 4→3, Carter 5→4, Ott 6→5, Smith(EJ) 7→6.
* **DEN WR** — Sutton 1→1, Waddle 2→2, Bryant 3→3, Franklin 4→4,
  Humphrey 5→5, Mims 6→6 **all unchanged**; Bandy 7→11 falls; Katsis 8→7,
  Key 9→8, Manjack 10→9, Ross 11→10 rise.
* **DEN TE** — Trautman 1→1, Engram 2→2, Krull 3→3, Adkins 4→4 unchanged;
  Lohner 6→5, Bentley 5→6 swap.
* **DEN RB** — Harvey 1→1, Dobbins 2→2, Prentice 3→3 unchanged;
  **Coleman 6→4**, Badie 4→5, Schrader 5→6.

The pattern is one sentence: **every starter holds, and the movement is entirely
in the tail**, where players with no history stop being filed behind veterans
whose measured snap share is lower than the tier the chart puts the newcomer in.
That is the intended shape of the repair and it is what D2 predicted for this
slate.

**DEN carries no receiving rows on the sealed board tonight**
(`missing_all_from: DEN`, `APPEARANCE_TEAM_DEFERRED_DEN`), so the DEN ordering
above does not reach a published number. It is reported because it is the DEN
half of what was asked and because it is what would appear if DEN un-defers.

---

## 4. What I left as explicit uncertainty

1. **There is no weekly WR1/WR2/WR3.** 2,396 of 2,432 WR rooms share
   `depth_team 1` among 2-4 players. `weekly` emits a group with `tie_size` and
   `resolved`, and refuses to manufacture an ordinal. §1.4.
2. **A special-teams-only player has no offensive rank**, and that is counted
   (115 over 2021-2024) rather than collapsed into "unlisted". §1.4.
3. **The daily vendor's ordinal is offence-wide and is not a role rank.**
   Declared on the artifact with the measured rank-1 position mix; NOT repaired,
   with the reason stated. Open, handed back. §1.6.
4. **`board.depth_rank` can overwrite a skill player's offensive rank with a
   return rank.** Measured 0 KC / 1 non-skill DEN tonight. Latent, not mine,
   one-line fix supplied. §1.6.
5. **D4's 47 is not reconstructible** from the artifact's stated inputs, and its
   0.1031 was selected by the contaminated chart. §2.3.
6. **The repaired assigner overshoots the cold-start cohort by +20%** where the
   legacy one undershot by −52%. Recorded, not tuned.
7. **Every result in §2 is exploratory.** The priors are fitted from the same
   panel these openers come out of. A confirmatory claim needs unseen games.

---

## 5. Patch handed to whoever owns the board (I did not apply it)

D2 asked for `tier` and `basis` on the board row, and `assign_tiers` now returns
everything needed: `detail[gsis_id]` carries `tier`, `basis`, `score`,
`own_trailing`, `n_trailing`, `depth_rank`, `anchor_tier`, `anchor`,
`anchor_source`, `shrinkage_w`, `k_snap`, `room_size`. `run_forecast.py:899`
currently keeps only a basis counter:

```python
# nfl/production/run_forecast.py, after `at = RP.assign_tiers(...)`
tiers = at['tier']
fx['_r6']['tier_basis'] = dict(_c.Counter(at['basis'].values()))
fx['_r6']['tier_detail'] = at['detail']          # ADD
fx['_r6']['tier_ordering'] = at['ordering']      # ADD
fx['_r6']['tier_degraded'] = at['degraded']      # ADD — must be False
```

and `nfl/product/board.py:216`, to close §1.6 item 4:

```python
for r in rows_by_team[t]:
    if (r.get('pos_abb') or '').upper() in DV.RETURN_SLOTS:
        continue                                  # ADD
    try:
        out[r['gsis_id']] = (r['pos_abb'], int(r['pos_rank']))
```

Neither is applied. `tier_degraded` being anything but `False` on a live run
means the repaired ordering did not execute and the run should be treated as
carrying the old defect.
