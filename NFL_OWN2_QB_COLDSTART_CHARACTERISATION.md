# OWN-2 — characterising the quarterbacks QB V1 cannot forecast

**Mission:** before building an estimator, characterise the population that
currently fails QB V1. Rule out data and identity defects **first**. Determine
whether "no usable history" is one state or several. Quantify how often each
occurs and how much allocation it carries. Establish the minimum causal inputs
available before kickoff.

**No estimator was fitted. Nothing was scored. No 2026 outcome was touched.**

**Four findings.**

1. **There is no data or identity defect.** Zero of the 35 quarterbacks on the
   live slate, and **zero of 275** historical cases, have prior play-by-play
   dropbacks the frame cannot see. The first requirement of the ruling is
   satisfied decisively — a cold-start model would not be papering over an
   ingestion or join failure.
2. **Depth rank carries the signal; the cold-start class label does not.**
   Conditional on rank the four states are not empirically distinguishable at
   the available sample sizes. That argues directly for the aggressively shrunk
   simple baselines the ruling asks for, against a multi-state model.
3. **The evidence base is 30 played weeks.** Across three seasons, 275
   unforecastable player-weeks produced **30** with a dropback. Any candidate is
   learning from thirty positive observations.
4. **The rank-1 cell is the whole risk, and it is n = 6.** Every unforecastable
   rank-1 quarterback played, and played a full game — **P(dropback) = 1.000,
   mean 42.67 dropbacks**. Six rows in three seasons.

**I found and corrected two defects in my own OWN-2 code before reporting**, both
of the class this audit exists to catch. §5.

Governance unchanged: `QB_ALLOCATION_SHARE_UNCONSUMED` remains **fail-closed**,
`PATH_C_STATE.json` untouched, G0A **11/12**, NFL-1 **NOT AUTHORIZED**,
A3/QB3/C3 rehearsal-only, `SHARED_PASS_DEFAULT` off.

---

## 1. The exclusion rule being characterised

`qb_v1.slate_prospective` keeps `rows = [r for r in pros if r['h_games'] >= 1]`,
and `h_games` counts prior rows **in the panel QB frame** carrying `db > 0`.

So the rule is not "he has never dropped back". It is "**the frame** shows no
prior dropback", and those are different statements. Distinguishing them is the
whole of the identity check. Identity matching throughout is by `gsis_id` only —
no fuzzy name matching, ever.

---

## 2. Data and identity defects: ruled out

The independent view is raw play-by-play (`qb_dropback == 1`, passer or scrambling
rusher), at **week granularity**. A quarterback is a data defect if play-by-play
shows him dropping back **strictly before** the row in question and the frame
does not.

| population | n | data / identity defects |
|---|---|---|
| 2026 week-1 live slate | 35 | **0** |
| historical depth-chart rows, 2022–2024 | 275 excluded of 4,414 | **0** |

Not one case. Every excluded quarterback genuinely has no prior NFL dropback the
frame could have used. **This is a cold-start problem and not an ingestion
problem**, and that is now measured rather than assumed.

---

## 3. Is it one state or several?

### The live slate, 2026 week 1

| state | n | dropback share | % of league |
|---|---|---|---|
| **TRUE_DEBUT** — entered 2026, nothing anywhere | **20** | 1.0222 | **3.19%** |
| **PRIOR_ENTRANT_NO_NFL_APPEARANCE** — entered 2023–25, never on an NFL field | **12** | 0.5955 | **1.86%** |
| APPEARED_WITHOUT_A_DROPBACK — on the field, never dropped back | 2 | 0.0614 | 0.19% |
| PRE_WINDOW_ENTRANT_HISTORY_UNVERIFIED — entered 2019 | 1 | 0.0223 | 0.07% |
| DATA_OR_IDENTITY_DEFECT | **0** | — | — |
| **total** | **35** | **1.7014** | **5.32%** |

The largest single exposure is **Cade Klubnik (NYJ), share 0.3037** — a true
debutant holding 30% of a team's dropbacks.

### Historically, 2022–2024

2020 and 2021 are **burn-in and are not scored**: a player cannot be shown to be
new when the coverage itself is new. That is the same left-boundary trap the
OWN-1 addendum had to correct after the fact, excluded here by construction.

| segment | rows | excluded | rate | APPEARED | PRIOR_ENTRANT | DEBUT_LIKE |
|---|---|---|---|---|---|---|
| week 1, rank 1 | 98 | 6 | 6.12% | 0 | 0 | 6 |
| week 1, rank 2 | 96 | 9 | 9.38% | 0 | 1 | 8 |
| week 1, rank 3+ | 38 | 18 | 47.37% | 1 | 4 | 13 |
| **week 2+, rank 1** | 1,731 | **0** | **0.00%** | 0 | 0 | 0 |
| week 2+, rank 2 | 1,764 | 78 | 4.42% | 20 | 56 | 2 |
| week 2+, rank 3+ | 687 | 164 | 23.87% | 6 | 151 | 7 |
| **pooled** | **4,414** | **275** | **6.23%** | **27** | **212** | **36** |

**Week 2+, rank 1 is 0 of 1,731.** The starting quarterback is never
unforecastable after week 1 — a sharper version of the 0.07% in OWN-1's
addendum, on a frame built specifically for this question.

Historically the population is dominated by **PRIOR_ENTRANT_NO_NFL_APPEARANCE
(212 of 275, 77%)**: a retained backup who has never taken an NFL snap. The 2026
slate inverts that mix toward debutants because it is week 1 of a new season.

### The states are not distinguishable once rank is held

| class \| rank | n | played | **P(dropback)** | mean db given played |
|---|---|---|---|---|
| **ALL \| rank 1** | **6** | **6** | **1.0000** | **42.67** |
| ALL \| rank 2 | 87 | 13 | 0.1494 | 13.00 |
| ALL \| rank 3+ | 182 | 11 | 0.0604 | 23.36 |
| APPEARED_WITHOUT \| rank 2 | 20 | 3 | 0.1500 | 13.00 |
| PRIOR_ENTRANT \| rank 2 | 57 | 9 | 0.1579 | 14.33 |
| DEBUT_LIKE \| rank 2 | 10 | 1 | 0.1000 | 1.00 |
| APPEARED_WITHOUT \| rank 3+ | 7 | 0 | 0.0000 | — |
| PRIOR_ENTRANT \| rank 3+ | 155 | 11 | 0.0710 | 23.36 |
| DEBUT_LIKE \| rank 3+ | 20 | 0 | 0.0000 | — |

At rank 2 the three classes give **0.150, 0.158, 0.100** on n of 20, 57 and 10.
Those are not separable. **Depth rank moves P(dropback) by a factor of about
17 (1.000 → 0.060); the class label moves it within noise.**

**Read that as a constraint on complexity, not as proof the classes are
identical.** The samples are far too small to reject a difference; what they
cannot do is support one. A four-state model would be fitting labels the data
cannot see.

---

## 4. Minimum causal inputs available before kickoff

For a quarterback with no prior NFL dropback, **every player-specific input is a
static career marker**. There is no performance history by definition.

| input | available for the 35 | note |
|---|---|---|
| depth-chart rank | 35 / 35 | captured, chronology-checked; carries the signal |
| entry year | 35 / 35 | |
| years of experience | 35 / 35 | |
| weight | 35 / 35 | |
| college, height, birth date | 32 / 35 (91.4%) | |
| **draft number / club** | **18 / 35 (51.4%)** | **17 undrafted or unrecorded, holding 0.6313 of the 1.7014 share** |
| prior NFL performance | **0 / 35** | by definition of the population |

Team-level inputs remain available and are not player-specific: D1's team
dropback forecast, coach, and the **injury and practice report for the whole
quarterback room** — which is the actual causal driver, since a backup takes
dropbacks when the man ahead of him does not.

**Draft number is the only player-specific input with any prior-evidence claim,
and it is missing for half the population, weighted toward the undrafted.** A
candidate leaning on it must state what it does for the other 17, and "impute
the mean" is not an answer — that is the silent-constant rule.

---

## 5. Two defects in my own OWN-2 code, found and corrected before reporting

Recorded rather than quietly fixed, because both are the project's own worst
class.

**5.1 A file's coverage limit read as an absent attribute.** The first
classifier tested "was he on an NFL roster before this season" against
`weekly_rosters`. That file in this checkout holds **only 2026**, so the branch
could never fire, and fourteen quarterbacks landed in a bucket named
`NO_PRIOR_AND_NO_CAREER_MARKER` when they had perfectly good career markers
(entry years 2023–2025, one to three years of experience). The prior-presence
test now uses `panel_p3`, which spans 2020–2025.

**5.2 A season-granular history answering a within-season question.** The first
`pbp_passer_history` aggregated dropbacks to the **season** and the historical
classifier then placed each season's total at week 1 of that season. A
quarterback whose debut came in week 5 was therefore credited with prior
dropbacks in weeks 2 through 4. That version reported **172 of 275 excluded rows
as DATA_OR_IDENTITY_DEFECT — 62.5%, and it was entirely my bug.** Every one of
the 172 sat in exactly the affected window. Keyed by week, the count is **zero**.

Had I reported the first number, the mission would have been redirected from
cold-start research to hunting an ingestion defect that does not exist.

---

## 6. What this implies for the estimator, stated before any is built

Not a design, and not a fit. Constraints the characterisation puts on whatever
comes next:

1. **Two margins, not one.** A candidate must give `P(takes a dropback)` and the
   **distribution** of dropbacks given he does. The first is the mass that
   currently disappears; the second is what a point estimate would destroy —
   the defect class this project has now found five times.
2. **Rank-conditioned, aggressively shrunk.** Rank moves the probability by 17×;
   the class label does not move it measurably. Simple must be the control.
3. **Thirty positive observations.** With n = 6 in the decisive rank-1 cell, a
   candidate with more than a couple of free parameters cannot be supported.
4. **Closure is the point, not accuracy.** The core invariant is that allocated
   probability mass reaches a modelled state or triggers refusal. A candidate
   that forecasts well but leaks mass fails; one that forecasts crudely and
   closes exactly is doing the job asked of it.
5. **The week-1 / week-2 asymmetry is structural.** Rank 1 is 0 of 1,731 from
   week 2 onward. A candidate is a **week-1 and backup** instrument; it must not
   become a general-purpose replacement for QB V1.
6. **Half the population has no draft number.** Any candidate using it must say
   what it does for the other half, by name.

---

## 7. Next step

Pre-register OWN-3: the cold-start estimator comparison. Candidates to include a
rank-only pooled baseline and a rank + career-marker alternative, with the
simplest-wins order declared in advance, chronological evaluation on historical
cases reproducing the live information state, and the closure and accounting
invariants as gates rather than scores. Development evidence may reject; it may
not promote.

Until it clears, `QB_ALLOCATION_SHARE_UNCONSUMED` stays fail-closed.

## 8. Files

| File | Role |
|---|---|
| `nfl/research/own2/characterise_coldstart.py` | every number here; refuses without the independent play-by-play view |
| `nfl/research/own2/own2_population.json` | the live population, historical incidence, outcomes by class |
