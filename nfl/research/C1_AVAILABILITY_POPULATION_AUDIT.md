# C1 — Availability population audit: what population produced P(play) = 0.943, and what a production system must condition on before using it

**Pass:** NFL greenfield **correction** pass. Research and measurement only. No predictive
production code was written. No file outside this one was created or modified.
**Date of measurement:** 2026-09-06, all figures measured in this container on this date.
**Audit target:** `nfl/research/W7_INJURY_NEWS.md` §1.1 (the 0.9430 cell) and §3 (the state
table at `W7_INJURY_NEWS.md:582` and the sentence at `:593`).
**Documents read first:** `nfl/research/_GROUNDING.md` in full **including its corrections
section C1–C6**; `W7_INJURY_NEWS.md` §0, §1, §3, §6; `CLAUDE.md`.

**Labelling.** Every substantive claim carries exactly one of `VERIFIED` (a command was run
here and is shown), `DERIVED` (arithmetic or logic from something VERIFIED, derivation shown),
`UNVERIFIED-RECALL` (believed from training, not checked here).

---

## 0. Headline — stated first, because it is the whole finding

`VERIFIED` — **the 0.9430 reproduces exactly, and it is not the number the state table uses it
as.** The population that produced n = 3,386 and P(play) = 0.9430 is:

> **rows physically present in `injuries_2024.csv` whose `report_status` field is blank.**

Every one of those 3,386 rows is a player **named on his team's injury report** that week, with
a **populated `practice_primary_injury` and a populated `practice_status`**. He is on the
report. He simply carries no *game* designation on the final (Friday) version.

`VERIFIED` — the state table at `W7_INJURY_NEWS.md:582` assigns the code
`PLAYER_NOT_ON_REPORT` to the condition *"team has published, this player is not on it"*, and
`W7_INJURY_NEWS.md:593` then says that state **"is a positive observation worth 0.943 P(play)
(§1.1)"**. Those are two different populations wearing one number. The players in §1.1's cell
are **on** the report; the players the code names are **off** it.

`VERIFIED` — measured on the population the code actually names, REG 2024:

| Population the number is applied to | n | P(≥1 snap) | error of a flat 0.943 |
|---|---:|---:|---:|
| **W7 §1.1 source cell** — on report, blank `report_status` | 3,386 | **0.9430** | — (this is the cell) |
| Off the report, **restricted to the gameday-eligible pool** (`status ∈ {ACT, INA}`) | 24,101 | **0.8876** | **+0.0554** |
| Off the report, **any player on that week's roster file** | 38,524 | **0.5553** | **+0.3877** |
| Off the report, practice squad (`status = DEV`) | 8,305 | **0.0000** | **+0.9430** |

`DERIVED` — the owner's instruction is correct and the correction is not cosmetic. Applied
unconditionally to "every rostered player", the 0.943 prior is **wrong by +0.39 in the mean**,
and by **+0.94** on the single largest sub-population it would silently sweep in (the practice
squad, 15.3 players per team-game, of whom **zero** took a snap).

`DERIVED` — and the second half, which is larger: even where 0.943 is nearly right for
*dressing*, it is nowhere near right for *playing a role*. Among gameday-eligible skill players
off the report, P(≥1 snap) = 0.8427 while **P(≥50% of team offensive snaps) = 0.3546** — a
ratio of 0.42. Availability and opportunity are different random variables and this document
keeps them separate throughout.

---

## 1. Data, joins, and the reconstruction of the 3,386 cell

### 1.1 Files

`VERIFIED` — all from the shared cache
`/tmp/claude-0/-home-user-mlb-prop-system-v7/8de98087-4781-5a10-ae09-ef74590f8116/scratchpad`,
except the two weekly-roster files, which my brief authorised.

| File | Rows (excl. header) | Source |
|---|---:|---|
| `inj2024.csv` | 6,215 | pre-cached; `injuries/injuries_2024.csv` |
| `inj2025.csv` | 6,068 | pre-cached |
| `snaps2024.csv` | 26,615 | pre-cached; `snap_counts/snap_counts_2024.csv` |
| `snaps2025.csv` | 26,612 | pre-cached |
| `players_players.csv` | 24,828 | pre-cached; the `gsis_id ↔ pfr_id` crosswalk |
| `depth_charts_depth_charts_2024.csv` | 37,312 | pre-cached |
| `c1/wr2024.csv` | 46,579 | **downloaded by C1**, 14,926,918 B |
| `c1/wr2025.csv` | 46,849 | **downloaded by C1**, 15,385,661 B |

`VERIFIED` — download command, both files:

```
curl -sS -L -o wr2024.csv \
  "https://github.com/nflverse/nflverse-data/releases/download/weekly_rosters/roster_weekly_2024.csv"
```

`VERIFIED` — no `pbp` or `pbp_participation` file was downloaded or re-downloaded. Total new
bytes 30.3 MB, both files authorised by my brief ("you may download … weekly_rosters").

`VERIFIED` — `weekly_rosters` schema, 35 columns, header read directly:
`season, team, position, depth_chart_position, jersey_number, status, full_name, …, gsis_id,
…, pfr_id, …, week, game_type, status_description_abbr, …`. Keys on **both** `gsis_id` and
`pfr_id`, which removes the crosswalk step W7 needed. **Zero duplicate
`(season, week, team, gsis_id)`** in 46,579 rows; 7 rows carry a null `gsis_id`.

### 1.2 The reconstruction — exact, first attempt

`VERIFIED` — the inclusion rule that reproduces the cell is a **one-line filter on the injury
file itself**, before any join:

```
python3.12 -c "
import pandas as pd
inj=pd.read_csv('inj2024.csv',dtype=str)
print(inj.report_status.value_counts(dropna=False))"
```
```
report_status
NaN             3386      <-- the cell
Questionable    1513
Out             1116
Doubtful         194
Note               6
```

`VERIFIED` — so **n = 3,386 is not the output of any join, any roster filter, or any snap-count
filter. It is the count of blank `report_status` values in `injuries_2024.csv`**, all game
types (REG 5,954 + postseason 261).

`VERIFIED` — the numerator reproduces on W7's own join (pfr-id key ∪ normalised-name key,
NFKD → ASCII → lower → strip non-alpha, matched on `(season, week, team, ·)`), script
`c1/r1.py`:

```
matched pfr 4188  name 4023  union 4190
               size   sum         p
(none)         3386  3193  0.943001
Doubtful        194     0  0.000000
Note              6     5  0.833333
Out            1116     1  0.000896
Questionable   1513   991  0.654990
```

`DERIVED` — 3,193 / 3,386 = **0.943001**, and the three join counts 4,188 / 4,023 / 4,190
match `W7_INJURY_NEWS.md` §0.2 to the row. **W7's arithmetic is correct and its join is
correct. Nothing in §1.1 is a measurement error.** The defect is entirely one of population
labelling downstream.

`VERIFIED` — an independent second reconstruction using `gsis_id` end-to-end (the weekly-roster
crosswalk instead of `pfr_id`), REG only, gives **0.9435 on n = 3,203**, and 2025 gives
**0.9379 on n = 3,107** (`c1/r11.py`). The cell is robust to the join method and to the season.

### 1.3 What the 3,386 rows actually are — the decisive composition check

`VERIFIED` — REG 2024 subset, n = 3,203:

| field | value |
|---|---|
| `report_primary_injury` null | **3,203 / 3,203** (100%) |
| `practice_primary_injury` null | **1 / 3,203** (0.03%) |
| `practice_status` = Full Participation | 2,502 |
| `practice_status` = Limited Participation | 463 |
| `practice_status` = Did Not Participate | 238 |
| `practice_status` null | **0** |

`DERIVED` — the cell is **not** "healthy players". It is *"named on the practice report with a
specific ailment or a rest day, and cleared of any game designation by Friday"*. That is a
population selected on **two** things at once: (a) something happened to him this week, and
(b) the medical staff resolved it. A player never named at all satisfies (a) vacuously and has
never been through (b).

`DERIVED` — this is why the sentence at `W7_INJURY_NEWS.md:593` cannot stand as written. The
label "no designation" is true of both populations; the *measurement* was taken on only one.

---

## 2. Quantifying the selection — the key number

### 2.1 The denominator W7 never had

`VERIFIED` — REG 2024, `weekly_rosters` restricted to `game_type == REG`: 44,473 rows across
**544 team-games**, exactly matching the 544 team-games in `snap_counts` and confirming the
roster file carries **no bye-week rows** (so byes cannot contaminate a rate computed on it).

`VERIFIED` — the injury report covers a small minority of the pool. Of the 29,559
gameday-eligible player-team-weeks (§3), **5,458 (18.46%)** carry an injury-report row of any
kind. Mean injury rows per team-week = **10.97**. Distinct players appearing on any 2024 report
= **1,433**, against **2,263** distinct players in the gameday-eligible pool.

`DERIVED` — **81.5% of the population a production system must price is invisible to §1.1's
denominator.** The 0.943 was measured on the 18.5% minority that the report selects, and that
minority is selected on being a rotation regular (§2.3).

### 2.2 THE KEY NUMBER — P(play) for roster players never on that week's report

`VERIFIED` — script `c1/r5.py` / `c1/r6.py`, REG 2024, "played" = appears in `snap_counts` for
that week-team with ≥ 1 snap (the same predicate W7 used; `VERIFIED` — exactly 1 of 26,615 snap
rows has total snaps = 0, so membership and "took a snap" are the same event). CIs are
non-parametric bootstrap over **`(week, team)` clusters**, 1,500 replicates,
`numpy.random.default_rng(20260906)`. **No naive binomial SE appears in this document**
(`CLAUDE.md` rule 9).

| Population — REG 2024 | n | clusters | **P(≥1 snap)** | 95% CI (clustered) |
|---|---:|---:|---:|---|
| **On report, blank designation** *(the W7 cell)* | 3,141 | 532 | **0.9621** | [0.9528, 0.9697] |
| **Gameday-eligible, never on that week's report** | 24,101 | 544 | **0.8876** | [0.8848, 0.8906] |
| **Any roster-file row, never on that week's report** | 38,524 | 544 | **0.5553** | [0.5512, 0.5593] |
| On report, `Questionable` | 1,351 | 452 | 0.7091 | [0.6830, 0.7323] |
| On report, `Out` | 795 | 421 | 0.0013 | [0.0000, 0.0039] |
| On report, `Doubtful` | 166 | 115 | 0.0000 | [0.0000, 0.0000] |

`DERIVED` — **the answer to the owner's question is 0.8876, not 0.9430, and only if the system
already knows the player is in the gameday-eligible pool.** If it knows only "he is on a roster
file", the answer is **0.5553**. The confidence intervals do not overlap in either comparison,
by a wide margin.

`VERIFIED` — 2025 out-of-sample, identical code, `c1/r11.py`:

| Population | 2024 | 2025 | 2025 n |
|---|---:|---:|---:|
| On report, blank designation | 0.9621 | **0.9614** | 3,031 |
| Gameday-eligible, off report | 0.8876 | **0.8924** | 24,274 |
| Any roster row, off report | 0.5553 | **0.5566** | 38,915 |
| On report, `Questionable` | 0.7091 | **0.6999** | 1,143 |

`DERIVED` — every cell replicates within 0.005 on a season W7 did not use to form the estimate.
The separation is a structural property of the data, not a 2024 artefact.

### 2.3 Where the 0.943−0.888 gap comes from — it is mostly role, not health

`VERIFIED` — depth-chart-rank composition of the two populations differs sharply:

| depth rank (2024 depth chart, min rank in week) | on report, blank | off report, eligible | off report, any roster row |
|---|---:|---:|---:|
| 1 (starter) | **67.6%** | 43.7% | 27.7% |
| 2 | 22.2% | 35.7% | 22.6% |
| 3 | 5.1% | 11.3% | 7.3% |
| no depth-chart entry | 5.2% | 9.3% | **42.4%** |

`VERIFIED` — direct standardisation, `c1` standardisation script:

| comparison | crude | standardised |
|---|---:|---:|
| off-report eligible, **reweighted to the on-report depth mix** | 0.8876 | **0.9326** |
| on-report blank, **reweighted to the off-report depth mix** | 0.9621 | **0.9439** |

`DERIVED` — the crude gap is 0.0745. Standardising on depth rank alone closes **0.0450 of it
(60%)**. `DERIVED` — **most of what looks like "being named on the injury report is good news"
is the injury report over-sampling starters.** The residual ≈ 0.02–0.03 is the only part that
can even be a candidate for genuine health information, and this design cannot separate it from
the remaining role variation the depth chart does not capture.

`DERIVED` — corollary that matters for design: 0.943 is neither a floor nor a ceiling for
off-report players. Conditioned on role it runs from **0.7189** (depth-3, eligible, off report)
to **0.9893** (depth-1, eligible, off report). It is the **marginal of a mixture**, and a
mixture marginal is the one number that is correct for **no** individual member of the mixture.

---

## 3. The four-way separation the owner asked for

`VERIFIED` — census per team-game, REG 2024, 544 team-games (`c1/r10.py`). "P≥50%" is the share
of the cell with `offense_pct ≥ 0.50`, i.e. at least half of the team's offensive snaps.

### (a) Roster membership — `weekly_rosters.status`

| `status` | n | per team-game | **P(≥1 snap)** | P(off% ≥ 50) |
|---|---:|---:|---:|---:|
| **ACT** | 26,121 | **48.02** | **0.9715** | 0.2255 |
| **INA** | 3,438 | **6.32** | **0.0000** | 0.0000 |
| DEV (practice squad) | 8,306 | 15.27 | 0.0004 | 0.0000 |
| RES (reserve / IR / PUP) | 5,184 | 9.53 | 0.0000 | 0.0000 |
| CUT | 1,018 | 1.87 | 0.0000 | 0.0000 |
| RET / EXE / TRC / TRD / E01 | 406 | 0.75 | 0.0000 | 0.0000 |
| **all rows** | 44,473 | 81.75 | 0.5706 | 0.1325 |

**`VERIFIED` — and this is a leakage finding that must be recorded before anything else uses
this file: `weekly_rosters.status` is a POST-HOC gameday outcome, not a pre-game roster state.**
`ACT` → 0.9715 took a snap; `INA` → **0 of 3,438** took a snap; `DEV` → **3 of 8,306**. A field
that separates the outcome that cleanly *is* the outcome. `DERIVED` — `status == 'ACT'` is the
gameday **actives list**, published ~90 minutes before kickoff. Under `_GROUNDING.md`'s
inherited Rule 003 (leakage) it must be **quarantined at ingest** exactly as `spread_line` and
`vegas_wp` are, and may be used **only** as a grading label, never as a feature. It is the same
shape of hazard as C5 in the grounding brief: a column whose presence invites the wrong use.

`VERIFIED` — the gameday active limit is **48**, read from data, not recalled:
`status == 'ACT'` per team-week has median 48, mean 48.02, sd 0.34, min 44, max 52 over 544
team-games. `VERIFIED` — distinct players recording ≥ 1 snap per team-game: median 47, mean
46.69, min 34, max 49. `DERIVED` — the ~1.3 gap between 48 actives and 46.7 snap-takers is
actives who never took a snap (third QB, emergency linemen).
`UNVERIFIED-RECALL` — the league rule is 48 actives with 8+ offensive linemen dressed, else 47;
the measured median of 48 is consistent with it, but the rule itself was not read here.

### (b) Expected game-day participation universe

`DERIVED` — the pre-game-knowable analogue of §3(a) is **`ACT ∪ INA`**: the set from which the
inactives are drawn. `VERIFIED` — 29,559 rows, **54.34 per team-game**
(`UNVERIFIED-RECALL` — 53-man roster plus standard-elevation practice-squad call-ups would give
~54–55; the measured 54.34 is consistent, the rule was not read here).

`VERIFIED` — **P(≥1 snap | gameday-eligible) = 0.8585**, n = 29,559.

`VERIFIED` — composition of the 3,438 gameday inactives:

| that week's injury-report state | count | share of INA |
|---|---:|---:|
| **not on the report at all** | **2,030** | **59.0%** |
| `Out` | 794 | 23.1% |
| `Questionable` | 376 | 10.9% |
| `Doubtful` | 160 | 4.7% |
| blank designation | 78 | 2.3% |

`DERIVED` — **the majority of gameday inactives never appear on the injury report.** They are
healthy scratches. Any model that reasons "no injury row ⇒ available" is structurally blind to
59% of the event it is trying to predict. This alone disqualifies the unconditional prior.

### (c) Injury-report presence / absence, within the eligible pool

| cell | n | per team-game | P(dressed) | **P(≥1 snap)** | P(off% ≥ 50) |
|---|---:|---:|---:|---:|---:|
| **not on the report** | 24,101 | 44.30 | 0.9158 | **0.8876** | 0.1899 |
| on report, blank designation | 3,141 | 5.78 | 0.9752 | **0.9621** | 0.3375 |
| on report, `Questionable` | 1,351 | 2.48 | 0.7217 | **0.7091** | 0.1880 |
| on report, `Out` | 795 | 1.46 | 0.0013 | **0.0013** | 0.0000 |
| on report, `Doubtful` | 166 | 0.31 | 0.0361 | **0.0000** | 0.0000 |

`VERIFIED` — 6 `Doubtful` players were listed among the gameday actives and **none of them took
a snap**. That is the only cell in the whole table where P(dressed) and P(snap) differ
materially in the *downward* direction.

### (d) Football role — depth-chart rank

`VERIFIED` — `c1/r9.py`, gameday-eligible pool, rank = minimum `depth_team` for that player in
that team-week across all formations.

| injury state | depth rank | n | P(dressed) | **P(≥1 snap)** | P(off% ≥ 50) |
|---|---|---:|---:|---:|---:|
| **not on report** | 1 starter | 10,533 | 0.9933 | **0.9893** | 0.3382 |
| | 2 | 8,595 | 0.8980 | **0.8450** | 0.0937 |
| | 3 | 2,729 | 0.7413 | **0.7189** | 0.0322 |
| | no entry | 2,244 | 0.8324 | **0.7781** | 0.0539 |
| **on report, blank** | 1 starter | 2,122 | 0.9953 | **0.9849** | 0.4237 |
| | 2 | 698 | 0.9470 | **0.9241** | 0.1590 |
| | 3 | 159 | 0.8868 | **0.8679** | 0.0440 |
| | no entry | 162 | 0.9198 | **0.9198** | 0.2654 |
| **on report, `Questionable`** | 1 starter | 757 | 0.7133 | **0.7028** | 0.2695 |
| | 2 | 308 | 0.7110 | **0.6981** | 0.0682 |
| | 3 | 93 | 0.5699 | **0.5591** | 0.0645 |

`DERIVED` — the ordering W7 §1.3 reported survives on the correct denominator and is
strengthened: a **`Questionable` starter (0.7028) is more likely to play than a healthy
third-stringer (0.7189 — now nearly a tie) and far more likely to play a meaningful offensive
role (0.2695 vs 0.0322, a factor of 8.4).** Role dominates designation for the quantity a prop
actually depends on.

### 3.1 The 2×2 the owner's separation implies

`VERIFIED` — gameday-eligible pool, REG 2024:

| | on injury report | not on injury report |
|---|---|---|
| **depth rank 1** | n = 3,453 (6.35/tg) · P(snap) **0.7608** · P(off≥50) 0.3197 | n = 10,533 (19.36/tg) · P(snap) **0.9893** · P(off≥50) 0.3382 |
| **not rank 1** | n = 2,005 (3.69/tg) · P(snap) **0.6778** · P(off≥50) 0.1052 | n = 13,568 (24.94/tg) · P(snap) **0.8086** · P(off≥50) 0.0747 |

`DERIVED` — the four cells span 0.678 → 0.989 on P(snap) and 0.075 → 0.338 on P(role). A single
scalar prior cannot represent this table, and 0.943 sits inside none of the four cells'
intervals except by coincidence.

---

## 4. What production must condition on — and the bucket table that proves it

The owner asked specifically for `P(play)` by prior-week snap-share bucket, for players with no
designation. Here it is, for **both** off-report and blank-designation players, so the two are
directly comparable.

`VERIFIED` — `c1/r8.py`. Weeks 2–18 (week 1 has no prior week), gameday-eligible pool.
Bucket = the player's `offense_pct` in **week − 1** on his own roster row, i.e. information
available at prediction time. "rostered, no snap last wk" means he was on a roster file in
week − 1 and recorded no snap.

**Off the injury report entirely (`PLAYER_NOT_ON_REPORT` — the code the state table names):**

| prior-week bucket | n | P(dressed) | **P(≥1 snap)** | P(off ≥ 25%) | **P(off ≥ 50%)** | median off% given snap |
|---|---:|---:|---:|---:|---:|---:|
| not on a roster last wk | 1,469 | 0.9074 | 0.8816 | 0.2464 | 0.1831 | 0.00 |
| **rostered, no snap last wk** | **14,153** | 0.8837 | **0.8505** | 0.0175 | **0.0098** | 0.00 |
| prev off% 0–10 | 929 | 0.9505 | 0.8934 | 0.1184 | 0.0592 | 0.05 |
| prev off% 10–25 | 897 | 0.9766 | 0.9431 | 0.3367 | 0.0870 | 0.19 |
| prev off% 25–50 | 1,221 | 0.9910 | 0.9779 | 0.7453 | 0.2334 | 0.36 |
| prev off% 50–75 | 941 | 0.9883 | 0.9851 | 0.9416 | 0.7311 | 0.62 |
| prev off% 75–100 | 2,932 | 0.9966 | **0.9905** | 0.9543 | **0.9325** | 1.00 |

**On the report with a blank designation (the population that produced 0.943):**

| prior-week bucket | n | P(dressed) | **P(≥1 snap)** | P(off ≥ 25%) | **P(off ≥ 50%)** |
|---|---:|---:|---:|---:|---:|
| not on a roster last wk | 188 | 0.9734 | 0.9628 | 0.3511 | 0.3085 |
| rostered, no snap last wk | 1,678 | 0.9654 | 0.9523 | 0.0721 | **0.0548** |
| prev off% 0–10 | 44 | 0.9545 | 0.9091 | 0.1818 | 0.1136 |
| prev off% 10–25 | 87 | 0.9655 | 0.9655 | 0.3563 | 0.1264 |
| prev off% 25–50 | 122 | 0.9754 | 0.9426 | 0.7623 | 0.4016 |
| prev off% 50–75 | 215 | 1.0000 | 1.0000 | 0.9581 | 0.8093 |
| prev off% 75–100 | 687 | 1.0000 | 0.9913 | 0.9665 | 0.9447 |

`DERIVED` — **this is the owner's point, measured.** Inside the *same* injury state, P(≥1 snap)
moves 0.8505 → 0.9905 across prior-workload buckets while **P(off ≥ 50%) moves 0.0098 → 0.9325,
a factor of 95.** The deep-bench player with no designation is 0.85 to *dress* and **0.010** to
play a meaningful offensive role. A system that used 0.943 for him would be roughly right about
the wrong quantity and catastrophically wrong about the right one.

`VERIFIED` — skill positions only (QB/RB/WR/TE), off report, weeks 2–18, the sharpest case:

| prior-week bucket | n | P(dressed) | P(≥1 snap) | P(off ≥ 25%) | P(off ≥ 50%) |
|---|---:|---:|---:|---:|---:|
| rostered, no snap last wk | 1,460 | **0.6795** | **0.4685** | 0.0781 | **0.0288** |
| prev off% 0–10 | 622 | 0.9389 | 0.8746 | 0.1061 | 0.0386 |
| prev off% 10–25 | 781 | 0.9782 | 0.9424 | 0.3380 | 0.0640 |
| prev off% 25–50 | 1,142 | 0.9921 | 0.9790 | 0.7592 | 0.2250 |
| prev off% 50–75 | 872 | 0.9897 | 0.9862 | 0.9518 | 0.7294 |
| prev off% 75–100 | 1,219 | 0.9992 | 0.9902 | 0.9688 | 0.9352 |

`DERIVED` — a skill-position player with no designation who took zero snaps last week is
**0.4685** to take a snap this week, not 0.943. The prior overstates him by **+0.47**.

### 4.1 Miscalibration of the flat prior, scored

`VERIFIED` — `c1/r12.py`, flat p = 0.9430 scored against each population, REG 2024:

| population the prior is applied to | n | actual | **bias (p − actual)** | Brier | log loss |
|---|---:|---:|---:|---:|---:|
| W7 source cell (on report, blank) | 3,141 | 0.9621 | −0.0191 | 0.0368 | 0.1650 |
| gameday-eligible, off report | 24,101 | 0.8876 | **+0.0554** | 0.1029 | 0.3742 |
| all roster rows, off report | 38,524 | 0.5553 | **+0.3877** | 0.3973 | 1.3066 |
| eligible, off report, depth rank 3 | 2,729 | 0.7189 | **+0.2241** | 0.2523 | 0.8473 |
| all roster rows, off report, no depth entry | 16,340 | 0.1069 | **+0.8361** | 0.7946 | 2.5649 |
| practice squad (`DEV`), off report | 8,305 | 0.0000 | **+0.9430** | 0.8892 | 2.8647 |

`DERIVED` — the prior is well calibrated on exactly one population: the one it was measured on.
Every widening of the population degrades it monotonically, and the degradation reaches
**2.86 nats** of log loss — worse than an uninformative intercept — on the practice squad.

### 4.2 The conditioning contract a production system must satisfy

`DERIVED` throughout. Before any availability prior may be read, the system must have
established, at prediction time and from prediction-time-legal sources:

| # | Precondition | Source available pre-game | If unresolved |
|---|---|---|---|
| **P1** | Player is under contract to this team in this week | `weekly_rosters` **identity fields only** — never `status` | `NOT_APPLICABLE` / `PLAYER_NOT_ROSTERED`, no prior |
| **P2** | Player is in the **gameday-eligible** pool, not practice squad / IR / reserve | **not directly available pre-game** — must be derived from transaction feed; `weekly_rosters.status` is post-hoc and is quarantined | `DEFERRED` / `ELIGIBILITY_UNKNOWN`; **no availability prior may be emitted** |
| **P3** | The team has **published** a report for this game-week | injury feed, per team-week | `DEFERRED` / `REPORT_NOT_YET_PUBLISHED` (W7's state is correct here) |
| **P4** | Player's presence or absence **on that published report**, with designation | injury feed | `FAIL` if the report published and the parse dropped rows (Class A) |
| **P5** | Player's **role**: depth rank at prediction-time vintage **and** prior-week snap share | daily depth charts (W7 §3.3); `snap_counts` from completed weeks | `NOT_APPLICABLE` / `ROLE_UNKNOWN`; the prior falls back to the marginal and must be flagged as such |

`DERIVED` — **P2 is the binding constraint and it is currently unsatisfied.** The only field in
the stack that cleanly separates the gameday-eligible pool is `weekly_rosters.status`, and §3(a)
shows that field *is the outcome*. Until a prediction-time eligibility source exists, the
honest state for an arbitrary rostered player is **`DEFERRED`, not a 0.943 prior**. This is
assignment-shaped, not blocked-shaped (`docs/AGENT_PROTOCOL.md` DEC-029): a transaction feed
with dated rows would resolve it, and it should be requested rather than approximated.

`DERIVED` — the prior itself is then a **table**, not a scalar. The minimum key is
`(injury_report_state × eligibility × role bucket)`. §3(d) and §4 give the 2024 values for
every cell of it. The smallest defensible cell size here is ~90 rows; cells thinner than that
must shrink toward the row margin rather than be quoted.

---

## 5. P(dressed) versus P(plays a meaningful role) — both measured

`VERIFIED` — three nested events, gameday-eligible pool, REG 2024 (`c1/r7.py`, `c1/r13.py`):

**All positions:**

| injury state | n | P(dressed) | P(≥1 snap) | P(off ≥ 10%) | P(off ≥ 25%) | P(off ≥ 50%) | P(off ≥ 75%) |
|---|---:|---:|---:|---:|---:|---:|---:|
| not on report | 24,101 | 0.9158 | 0.8876 | 0.2960 | 0.2498 | 0.1899 | 0.1409 |
| on report, blank | 3,141 | 0.9752 | 0.9621 | 0.4218 | 0.3875 | 0.3375 | 0.2598 |
| `Questionable` | 1,351 | 0.7217 | 0.7091 | 0.2635 | 0.2346 | 0.1880 | 0.1429 |
| `Out` | 795 | 0.0013 | 0.0013 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| `Doubtful` | 166 | 0.0361 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |

**Skill positions (QB/RB/WR/TE) only — the population props are written on:**

| injury state | n | P(dressed) | P(≥1 snap) | P(off ≥ 25%) | P(off ≥ 50%) | median off% given snap | share who snap but log 0 offensive snaps |
|---|---:|---:|---:|---:|---:|---:|---:|
| not on report | 6,969 | 0.9095 | **0.8427** | 0.5447 | **0.3546** | 0.40 | 0.0623 |
| on report, blank | 927 | 0.9741 | **0.9525** | 0.7627 | **0.6106** | 0.65 | 0.0227 |
| `Questionable` | 398 | 0.6608 | **0.6432** | 0.4523 | **0.3141** | 0.48 | 0.0547 |

`DERIVED` — the ratio P(off ≥ 50%) / P(≥1 snap) is **0.421** for off-report skill players and
**0.641** for blank-designation skill players. `DERIVED` — **using P(play) as if it were
P(contributes) overstates the second by 1.6× to 2.4× even inside the narrow population where
the 0.943 is correct.** A prop projection multiplies a rate by an opportunity count; feeding it
0.943 as the availability factor imports the wrong factor twice over.

`VERIFIED` — the sharpest single illustration is QB. Off report, gameday-eligible:
**P(dressed) = 0.9095 · P(≥1 snap) = 0.4783 (n = 1,177)**. `DERIVED` — backup quarterbacks
dress almost always and play almost never. The event "is available" and the event "is on the
field" diverge by 43 points in the same cell, and no scalar availability prior can carry that.

---

## 6. Disposition, and what should change

### 6.1 What is withdrawn

`DERIVED` — I am **not** withdrawing W7 §1.1. Its table reproduces exactly (§1.2) and its stated
denominator — *"rows on the official injury report carrying that designation"* — is accurate, and
its row label *"(no designation, but on the report)"* is accurate. W7 also measured the correct
contrast itself in §1.3, where "not on the injury report at all" scores **0.7794** on a
depth-chart denominator.

`DERIVED` — what must be withdrawn is **one sentence**: `W7_INJURY_NEWS.md:593`, which attaches
the 0.943 to the state code `PLAYER_NOT_ON_REPORT`. That sentence takes a number measured on the
on-report population and hands it to the off-report population. **Correct replacement, measured
here:**

> A player absent from a **published** report is `NOT_APPLICABLE` / `PLAYER_NOT_ON_REPORT`, and it
> is a positive observation **only once eligibility and role are established**. Measured REG 2024
> (2025 in brackets): **P(≥1 snap) = 0.8876 [0.8924]** given gameday-eligible, **0.5553 [0.5566]**
> given only roster membership, and it ranges **0.7189 → 0.9893** across depth rank and
> **0.4685 → 0.9902** across prior-week snap share within the eligible skill-position pool. It is
> **not** 0.943; that figure belongs to the on-report, blank-designation cell.

`DERIVED` — W7's structural point survives intact and is worth restating: storing "absent from a
published report" as a **missing row** rather than as an observed state destroys the largest cell
in the table. That was right. It is the *value* attached to the state that was wrong.

### 6.2 New finding this audit produced, which belongs in the leakage quarantine

`VERIFIED` — **`weekly_rosters.status` is a post-hoc gameday outcome** (`ACT` → 0.9715 snap,
`INA` → 0/3,438, `DEV` → 3/8,306). `DERIVED` — it must join `spread_line`, `total_line`,
`vegas_wp` in the ingest quarantine and be usable only as a grading label. It is more dangerous
than the market columns, because its name reads like a roster attribute rather than a result.

### 6.3 Open items, stated as assignments rather than blocks

`DERIVED`, per `docs/AGENT_PROTOCOL.md` DEC-029 and `CLAUDE.md` ("blocked for both of us, or it
is assigned"):

- **C1-A1 — prediction-time eligibility.** A dated transaction / roster-move feed is needed to
  reconstruct the gameday-eligible pool *before* kickoff. Without it, precondition P2 cannot be
  satisfied and no availability prior is licensed for an arbitrary rostered player. Not blocked
  by me — I have not stubbed it, mocked it, or approximated it with the leaking `status` field.
- **C1-A2 — depth-chart vintage.** §3(d) used the 2024 archive depth chart, which is a weekly
  end-state. W7 §3.3 records that `depth_charts_2026.csv` is a daily-vintage series; the role
  bucket in §4.2 P5 should be built on that, and the numbers here re-measured on it before any
  production use. The 2024 figures are a research-grade proxy, not a production coefficient.
- **C1-A3 — the residual 0.02–0.03.** After standardising on depth rank, a small on-report
  advantage survives (§2.3). Whether that is genuine health information or unmodelled role is
  **not identified by this design**. It is a pre-registration candidate, not a finding, and it
  must not be turned into a coefficient.

### 6.4 What must not be concluded from this document

`DERIVED` — three guards, in the spirit of `CLAUDE.md`'s withdrawn-claims discipline:

1. **0.8876 is not a replacement scalar prior.** It is the marginal of the same mixture, one
   layer out. It varies 0.719 → 0.989 by depth rank and 0.469 → 0.990 by prior workload within
   skill positions. Substituting it for 0.943 fixes the label and keeps the defect.
2. **Nothing here is confirmatory.** 2024 and 2025 are complete-population measurements of a
   descriptive contrast, not an out-of-sample test of a fitted model. No model was fitted. The
   2025 replication establishes stability, not predictive validity.
3. **"Played" here means ≥ 1 snap in `snap_counts`.** It is not "was on the 46/48", it is not
   "was healthy", and for prop purposes it is not "contributed" — §5 gives that separately, and
   the two differ by up to 43 points in the same cell.

---

## 7. Reproduction

`VERIFIED` — every table above is produced by scripts in
`/tmp/…/scratchpad/c1/`, run under `python3.12` (`CLAUDE.md`: 3.12 is the floor):

| script | produces |
|---|---|
| `c1/r1.py` | §1.2 exact reconstruction of 3,386 / 0.943001 on W7's join |
| `c1/r3.py`, `c1/r5.py` | §3(a) roster-status table; the leakage finding |
| `c1/r6.py` | §2.2 clustered bootstrap CIs |
| `c1/r7.py`, `c1/r13.py` | §5 dressed / snap / role ladder |
| `c1/r8.py` | §4 prior-week snap-share buckets |
| `c1/r9.py` | §3(d) depth-rank conditioning |
| `c1/r10.py` | §3 census and the 2×2 |
| `c1/r11.py` | §2.2 2025 replication |
| `c1/r12.py` | §4.1 flat-prior scoring |

`VERIFIED` — these are throwaway measurement scripts in the scratchpad. Per `_GROUNDING.md`
("Hard scope limit"), they are evidence, not deliverables, and **nothing was written to `nfl/`
except this file**.
