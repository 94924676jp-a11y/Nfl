# L2 — Candidate B: freeze, proofs, and the live-evaluation decision

**Ruling being executed.** RULING 1: Candidate B is authorised to advance
immediately as the official repair candidate for the leaking appearance model.
This document is the evidence for whether it may run tonight and under what
label. It authorises nothing beyond `CANDIDATE_B_LIVE_EVALUATION`.

Repository `/home/user/nfl`, branch `claude/nfl-greenfield-architecture-stsxmk`,
HEAD `9c3c29a83310970fc0f0c43fdb974d3fe317ced9`, interpreter python3.12.

**Freeze artifact** `nfl/research/remediation/l2/CANDIDATE_B_FREEZE.json`
sha256 `32ea294a98145b242e2cd8a7e5e702626bb85f5375c170068975f679e24797f6`
(76,966 bytes).

**Tonight's sealed run**
`nfl/research/remediation/l2/L2_LIVE_DEN_KC_APPEARANCE.json`
sha256 `0fc4138c33b11532e9279a0a5c5475c17ad05386516d323f4688f0a9b386fd33`.

**Preregistration** `nfl/research/remediation/ws_a/PREREG_appearance_leak.md`,
sha256 `b14738a0a4a262cccba416b6d76e3b80db4340b46f1ab144d0546bfe8f368dda`,
re-verified on disk in this session.

---

## 0. The decision, stated first

**Candidate B clears for `CANDIDATE_B_LIVE_EVALUATION` tonight.** Six of the
seven proofs pass outright. The seventh — train/serve feature parity — passes
on the claim it exists to test and fails a secondary comparison that cannot be
run at tonight's sample size; that split is set out in full in §4 and is not
smoothed over.

**The decision is sealed before kickoff (2026-09-15T00:15:00Z) and tonight's
outcome must not be used to decide whether B was good.** Forty-seven scorable
players in one game cannot separate two appearance models. Reading tonight's
result as a verdict on B would be reading a coin flip as a validation, and it
would also be conditioning a defect definition on a realised outcome, which
manufactures fake defects for any forecaster including a perfect one. The game
is graded under the standing ledger like every other game and is not fed back
into this ruling.

**Nothing here is CONFIRMED and nothing is PROMOTED.** The incumbent remains
the default arm. Both words are declared states in the switch and both refuse.

---

## 1. The seven proofs

| # | Proof | Verdict |
|---|---|---|
| 1 | Candidate B identity frozen and hashed | **PASS** |
| 2 | Preregistered evaluation rerun cleanly | **PASS** — reproduces the committed artifact field for field |
| 3 | Train/serve feature-availability parity | **PASS on the basis; PARTIAL overall** — see §4 |
| 4 | No label-dependent feature presence, structurally | **PASS**, with one named and measured residual that B did not introduce |
| 5 | Chronology | **PASS** |
| 6 | Pathological examples | **PASS on five of six; one cell still misbehaves; one cell is not constructible tonight** |
| 7 | Tonight's live player universe | **PASS** — ran on `2026_01_DEN_KC` against L1's newest lawful committed vintage |

---

## 2. Proof 1 — the frozen identity

| field | value |
|---|---|
| spec version | `appearance-b-union-candidate-universe-1` |
| module | `nfl/production/nonqb/appearance_b.py` sha256 `a3a1d5679314fb8c…` |
| switch | `nfl/production/nonqb/appearance_arm.py` sha256 `bd7b284bbb2f7b85…` |
| basis | `U_UNION_CANDIDATE_UNIVERSE` |
| features | **76**, named in order in the freeze |
| featuriser | `appearance_r8.featurise` sliced to its first 76 columns |
| estimator | `stage_a.fit_logistic`, `l2 = 1.0`, `iters = 300`, `lr = 0.5` — inherited from R8, not chosen here |
| k (2026 fit) | **1.217589**, cut `202600`, estimated as within/between player-season variance |
| training seasons | 2020–2025 |
| training rows | **59,539** (245 dropped as the `no_history_and_not_depth_listed` cell) |
| frame rows | **59,784**; 6,158 synthetic union rows added to the panel |
| coefficient vector sha256 | `88664d345948aed3403f9333f6e30bc8907157b3782f0e187280800d3cce4d69` |
| standardisation mean / sd sha256 | in the freeze |

**The feature names are checked, not asserted.** A name list nobody verified is
a comment, and a wrong comment on a coefficient vector is worse than none. Ten
probes perturb one input at a time and assert the exact SET of columns that
moves; all ten match.

**One column is removed from the incumbent and it is proved to be the right
one.** A row whose `v1` is `None` and a row whose `v1` is an empty dict take
identical paths through every other line of `R8.featurise`, because
`blk = r.get('v1') or {}` maps both to `{}`. The two outputs therefore may
differ in exactly one position. Measured: they differ in column **76 only**,
with values `1.0` and `0.0`. That column is the V1-presence indicator, it is
identically zero on this basis, and a constant column is not a feature.
Candidate B **calls** R8's featuriser and slices it; it does not restate it. A
second copy of a featuriser is how a production model quietly stops being the
accepted one.

**No constant is hand-set.** Every coefficient comes from the same estimator R8
uses with the same hyperparameters; `k` is estimated; no threshold, cutoff or
weight is introduced by this module.

Module source hashes for the whole execution path, the decompressed input-leaf
hashes from `INPUT_MANIFEST.json`, and the live vintage blob hashes are all in
the freeze.

---

## 3. Proof 2 — the clean rerun

`build_blocks.py` was rebuilt from scratch into a fresh cache and
`evaluate.py`'s `main()` was run against it, with output redirected to the
scratchpad so the committed artifact was never written. The result was then
compared field by field against
`nfl/research/remediation/ws_a/WS_A_RESULTS.json`.

**It reproduces exactly.** Every field except `elapsed_seconds` is identical.
Total 708.9 s.

The preregistered numbers, restated from that artifact — 40,593 evaluation
rows, 2,174 game clusters, 72 date clusters, 1,000 bootstrap reps at seed
20260914, Bonferroni α = 0.025 per candidate, observed appearance rate 0.628803:

| arm | Brier | 95% CI (game-clustered) | AUC | calib-in-large | TOST at ±0.02 |
|---|---|---|---|---|---|
| BASE_INFRAME | 0.090094 | [0.088123, 0.091916] | 0.941528 | +0.005925 | rejects both nulls |
| BASE_SERVE | 0.158523 | [0.155599, 0.161450] | 0.823726 | +0.088958 | does not |
| Candidate A | 0.158345 | [0.155340, 0.161317] | 0.817401 | +0.083797 | does not |
| **Candidate B** | **0.111806** | [0.109746, 0.113920] | **0.915341** | **+0.013830** | **rejects both nulls** |
| A0 (no V1 block) | 0.115114 | [0.113044, 0.117290] | 0.908833 | +0.016600 | rejects both nulls |

Paired against the pre-repair arm on the same resampled clusters:
**B − BASE_SERVE = −0.046717**, 95% CI [−0.049130, −0.044332] game-clustered
and [−0.054398, −0.038761] date-clustered; one-sided upper 97.5th percentile
−0.044332, so superior at α = 0.025 and non-inferior at the +0.005 margin.
Candidate A is −0.000178 with a CI spanning zero: falsified, and not revisited.

**The leak in one number, and its removal.** Top 5% by prediction:

| arm | predicted | observed |
|---|---|---|
| BASE_INFRAME | 0.99196 | 0.98866 |
| BASE_SERVE | 0.99423 | **0.57565** |
| Candidate A | 0.99758 | **0.39773** |
| **Candidate B** | 0.98911 | **0.98571** |

**Two things in this table that do not flatter B, reported because they are
true.** First, A0 — the control that deletes the V1 block entirely — reaches
Brier 0.115114 and AUC 0.908833 against B's 0.111806 and 0.915341. Most of B's
gain over the pre-repair arm is the removal of the leak, not the V1 block
earning its place; the block's residual contribution is about 0.0033 Brier.
Second, the presence bit alone scored AUC 0.639408 **in training** and is a
constant at serve, which is exactly the shape of the defect.

**Every score above is EXPLORATORY.** The hypothesis was selected from the same
historical panel every score was computed on. Freezing the data does not make
it a holdout and writing the preregistration first does not restore
independence. §9 says what would.

---

## 4. Proof 3 — train/serve feature-availability parity

This proof splits, and the split matters, so it is stated in two parts rather
than averaged into one word.

### 4a. Block presence — the quantity Candidate B changes. **PASS.**

| | training | serve |
|---|---|---|
| **incumbent** V1 block present | 53,381 / 59,539 = **0.896572** | **1.000000** |
| **Candidate B** V1 block present | 59,539 / 59,539 = **1.000000** | **1.000000** |

The incumbent's column is a variable in training and a constant at serve.
Candidate B's is a constant in both, equal to four decimals, which is the S3
condition in the preregistration.

### 4b. The feature values themselves — parity proved by bit-identity. **PASS.**

The strongest available test is not a distributional comparison but an
identity: run the **serve path** on a historical week and check whether it
reproduces the **training basis** row by row. It does.

| replayed week | candidates | single-row candidates | bit-identical | differing |
|---|---|---|---|---|
| 2024 week 1 | 703 | 561 | **561** | 0 |
| 2022 week 1 | 761 | 587 | **587** | 0 |
| 2023 week 9 | 469 | 463 | **463** | 6 (all duplicate-ordinal, §5) |

On the two week-1 replays every one of the twelve V1 numerics plus the four
derived columns has a standardised mean difference of **exactly 0.000000** and
an identical presence rate, because the two vectors are the same vectors. That
is parity demonstrated at n = 561 and n = 587, not asserted.

This is the property that had to be engineered rather than inherited. Training
on the union basis while serving on the panel basis would have swapped one
train/serve skew for a subtler one, so `_prospective_union` extends the panel
with the same union synthetic rows before appending the target week's
prospective rows. `assert_prospective_matches_frozen` runs the identical code
path with the extension switched off and requires the V1 blocks to come back
bit-identical to `appearance_model.prospective_feature_rows`, so the union
extension is provably the only difference from the accepted walk.

### 4c. Tonight's 47 players against the pooled training population. **FAILS the declared threshold, and this is reported rather than explained away.**

Comparing the 47 players scored tonight against the 4,163 week-1 training rows,
**12 of 17** V1 quantities exceed the preregistered SMD < 0.10 threshold — for
example `f_rate3` 0.6932 vs 0.5470 (SMD 0.3517) and `f_weeks_since_appear`
1.899 vs 4.944 (SMD 0.4907). Two further reported failures,
`f_practice_improving` and `f_practice_worsening`, are an artefact of a zero
pooled standard deviation where both means are identical at 0.0; those two are
in parity.

Cold-start share is the honest driver of part of it: 22.77% of week-1 training
rows carry no prior appearance history against 17.02% tonight, and pooled
across all weeks the training figure is 1.86%.

**What this comparison can and cannot say.** It is 47 rows from a *single game
cluster* against sixty game-weeks. Games are not independent observations, and
at one cluster the difference between "these two clubs" and "the basis does not
match" is not identified. The bit-identity result in §4b is the same question
asked at n = 561 and n = 587 and answered cleanly. So the honest verdict is:
**the basis is in parity and is demonstrated so; tonight's two-team population
is not the pooled population and no test at n = 47 from one cluster can tell us
whether that matters.** It is recorded as PARTIAL, not as PASS.

---

## 5. Proof 4 — no label-dependent feature presence

### The claim as asked, structurally. **PASS.**

On Candidate B's basis, **0 of 59,784** union frame rows lack a V1 block. The
presence rate is **1.0000**, so `P(appeared | block absent)` is **undefined for
want of any such row** — not small, not estimated, undefined. Feature presence
is a constant, and a constant cannot be a function of anything, including the
outcome. The same holds at serve by construction, and `predict` raises
`B_SERVE_BLOCK_ABSENT` rather than imputing if it ever does not.

For contrast, measured in the same run on the incumbent's frame: block present
on 53,626 rows at appearance rate **0.711875**, absent on 6,158 rows at
appearance rate **0.000000** exactly.

### The stronger property — label-flip invariance. **PASS with a named residual.**

Recomputing the whole union walk with every target-week row's `did_not_appear`
flipped and requiring every target-week V1 value to be bit-identical:

| week | target-week rows | moved | moved with a **single** row that week |
|---|---|---|---|
| 2022 w1 | 1,141 | 107 | **0** |
| 2024 w1 | 1,048 | 98 | **0** |
| 2023 w9 | 714 | 3 | **0** |
| 2025 w18 | 971 | 0 | **0** |

**Every row that moved is a player holding more than one frame row in that
week.** None with a single row moved, in any week tested.

**The residual, named.** `appearance_model._walk` orders rows by `ord` alone,
and the union frame key is `(season, week, team, gsis_id)`. Where a player is
carried by two clubs in one week he has two rows at the same ordinal, and the
first in list order becomes history for the second, so the first row's label
reaches the second row's features. Measured: **1,747 cells, 3,498 rows, 5.85%
of the frame** (the panel itself is 4.82%). This is a property of the frozen
walk and of the frame key. It is present in R7 and R8 identically, Candidate B
neither introduces nor repairs it, and it does **not** touch a live serve,
where every target-week label is `None`.

**Does it matter? Measured, not assumed.** Forward-chained on 2025, fitting with
and without the duplicate cell and scoring the same non-duplicate rows: Brier
0.126783 → 0.123862, a difference of −0.002921; AUC 0.898283 → 0.899654; mean
absolute prediction difference 0.033662, maximum 0.275184. So the residual is
worth roughly 6% of B's headline improvement over the pre-repair arm and is not
negligible. The direction is consistent with the sibling label harming
generalisation, but a single fold cannot establish that and this is reported as
a sensitivity, not a diagnosis. **It is logged as an open defect against the
frozen walk, not against Candidate B, and it is not fixed here** — repairing the
ordering in `appearance_model._walk` changes the incumbent as well and is a
separate change under a separate baseline.

---

## 6. Proof 5 — chronology. **PASS.**

Per forecast season, fitted in this session:

| forecast season | training seasons | rows | k | k cut | coef sha256 |
|---|---|---|---|---|---|
| 2022 | 2020–2021 | 18,946 | 1.371990 | 202200 | `6310b09485405129` |
| 2023 | 2020–2022 | 28,954 | 1.344730 | 202300 | `ae46208fada6ff71` |
| 2024 | 2020–2023 | 38,681 | 1.290632 | 202400 | `270990b6d2650317` |
| 2025 | 2020–2024 | 48,343 | 1.270713 | 202500 | `120f9a8a47d8021b` |
| **2026** | **2020–2025** | **59,539** | **1.217589** | **202600** | **`88664d345948aed3`** |

Every training season is strictly earlier than its forecast season and every
reliability constant is cut at the season start, so the constant a forecast
consumes was never computed from the season it forecasts.

Chronology is a **refusal, not a filter**, in three places, each with its own
named code: `B_TRAINING_LEAKAGE` if a forecast-season row reaches the fit;
`B_HISTORY_NOT_STRICTLY_EARLIER` if any historical row sits at or after the
target week at serve; and `B_REPLAY_NO_HISTORY` if truncation leaves nothing.
The truncation needed to replay a historical serve is behind an explicit
`replay=True` flag rather than applied silently, because at a real serve there
is nothing at or after the target week to truncate and a truncation that fired
there would be hiding a frame that had moved.

**This game's snap share is never a feature.** It was one for exactly one run of
R8 and scored an in-sample Brier of 0.04101 — a number good enough to be the bug
report. `predict` sets `r['snap'] = None` with the reason on the line above it,
and a test asserts both.

**No sportsbook input, no postgame input in a pregame feature.** The feature
name list is checked against the forbidden-input list; the module source is
checked for `odds`, `vegas`, `spread`, `moneyline`, `total_line`, `hardrock`.
Zero market inputs were opened by anything in this work.

---

## 7. Proof 6 — the pathological examples

### On labelled historical weeks (40,593 rows)

| cell | n | observed | pre-repair predicted (gap) | **Candidate B predicted (gap)** | Brier: pre-repair → B |
|---|---|---|---|---|---|
| clear RB1 | 1,773 | 0.8252 | 0.8446 (+0.0195) | **0.8239 (−0.0012)** | 0.0992 → 0.0854 |
| WR1 | 1,695 | 0.8130 | 0.8457 (+0.0327) | **0.8280 (+0.0150)** | 0.1058 → 0.0966 |
| long absence, `cm_carried ≥ 9` | 64 | 0.4062 | 0.9344 (+0.5281) | **0.6179 (+0.2117)** | 0.5646 → 0.3450 |
| long absence, `app_ewma < 0.05` | 2,260 | 0.1301 | 0.8336 (+0.7035) | **0.1922 (+0.0621)** | 0.6461 → 0.1206 |
| practice-squad / reserve (`rank ≥ 4`, `n_prior < 4`) | 1,089 | 0.5207 | 0.8976 (+0.3769) | **0.5564 (+0.0357)** | 0.4236 → 0.1737 |
| unlisted with history | 6,489 | 0.2040 | 0.2539 (+0.0499) | **0.2507 (+0.0467)** | 0.1346 → **0.1538** |
| week-1 cold start, listed | 357 | 0.5238 | 0.9792 (+0.4554) | **0.5574 (+0.0336)** | 0.4513 → 0.2357 |
| designated Out / Doubtful | 1,015 | 0.0010 | 0.0165 (+0.0155) | **0.0121 (+0.0111)** | 0.0032 → 0.0019 |

### The known governing inactive — replayed

TB@CIN 2026 week 1 is the only ingested governing inactive list in this
repository carrying skill positions. Replayed with a clock of
2026-09-13T16:16:00Z, before that game's 17:00Z kickoff, on 43 scorable players:

| | incumbent | **Candidate B** |
|---|---|---|
| Jack Endries (CIN TE, `00-0041116`), **officially inactive** | **0.99197**, rank **3 of 43** | **0.46417**, rank **25 of 43** |
| mean p over the 43 | 0.658562 | 0.517206 |

The incumbent's 0.99197 reproduces WS04's 0.9920 to four decimals, which is
what makes the replay trustworthy. **Neither arm reads the inactive list** — it
is applied a layer later in `layers.py`, and Candidate B does not change that
and does not claim to. What changes is that a depth-listed cold-start player is
no longer driven to near-certainty by the leak and is no longer the
third-most-certain player in the game. Ke'Shawn Williams could not be resolved
to a `gsis_id` in the roster blob lawful at that clock, so his figure is not
reported rather than guessed.

### What still misbehaves, plainly

1. **Long absence, `cm_carried ≥ 9`.** B predicts 0.6179 against an observed
   0.4062 on n = 64. That is a +0.21 gap. It is a large improvement on the
   pre-repair +0.53 and it is still the worst-calibrated cell in the table.
2. **Unlisted players with history.** B's Brier is **0.1538 against the
   pre-repair arm's 0.1346** — B is *worse* here, on 6,489 rows, despite a
   similar mean gap. This is the one substantial cell where the candidate
   loses.
3. **Two smaller cells** where B is marginally worse on Brier: prior
   participation in [0.5, 0.95) (0.1112 vs 0.1087) and in [0.95, 1]
   (0.0442 vs 0.0432).
4. **A predeclared sign is not recovered.** The preregistration declares
   `pearson(cm_carried, p)` must be **negative** among listed, non-designated
   rows. Pre-repair it is +0.0568; **B gives +0.00438** — moved almost to zero
   but not negative. The companion sign is recovered:
   `pearson(app_ewma, p)` is +0.8882 against a predeclared positive, up from
   +0.5456. One of the two predeclared signs is met and one is not.

---

## 8. Proof 7 — tonight's live universe, `2026_01_DEN_KC`

Kickoff 2026-09-15T00:15:00Z. Information set resolved at written_at
**2026-09-14T16:21:04Z**, which is before kickoff and before now.

**Vintages used — L1's newest lawful committed capture, `20260914T161625Z`:**

| source | blob |
|---|---|
| weekly_rosters | `nfl/vintage/weekly_rosters.bdab6ecee12d44a4.raw.csv.gz` (observed 16:16:25Z) |
| depth_charts | `nfl/vintage/depth_charts.f66f0c2583dba463.raw.csv.gz` (observed 16:16:25Z) |
| injuries | `nfl/vintage/injuries.66e960ec81fccc6e.csv.gz` (observed 2026-09-13T15:45:56Z) |

L1's concurrent capture had landed rosters and depth charts minutes before this
run and they were used. The injuries feed is the 2026-09-13 archive mirror;
`official_injury_report`, `official_inactives` and `espn_injuries_json` are all
`BLOCKED / NO_EGRESS` at that capture, so **no governing injury or inactive
source exists for this game**, which constrains both arms equally and is L1's
declared downgrade, not something this work can close.

**Universe.** 180 roster players (KC 92, DEN 88), all carrying a `gsis_id`, 58
at skill positions. **47 scored, 133 declined** by name into the
`no_history_and_not_depth_listed` cell under both arms — that cell's appearance
rate in this repository is 1.0000 with zero variance, which is a construction,
not an estimate, so it is declined rather than scored.

| | incumbent | **Candidate B** |
|---|---|---|
| scored / declined | 47 / 133 | 47 / 133 |
| mean p | 0.717500 | **0.501694** |
| median | 0.838782 | 0.523597 |
| sd | 0.330228 | 0.314037 |
| p > 0.99 | **10** | **1** |
| p > 0.95 | 15 | 2 |
| p < 0.05 | 4 | 10 |
| top-5% mean predicted | 0.994513 | 0.981555 |
| coef sha256 | `557725f24fdc18ee` | `88664d345948aed3` |

Paired over the same 47 players: mean B − incumbent **−0.2158**, median
−0.0728, range [−0.7911, +0.0105]; B is lower for 41 and higher for 6. For
orientation, B's week-1 historical bucket predicted 0.5515 against an observed
0.5037, so a mean near 0.50 on a week-1 universe weighted toward deep reserves
is the shape the historical fit predicts.

### Live pathological cells

| cell | n | incumbent mean | **B mean** |
|---|---|---|---|
| long absence, `cm_carried ≥ 9` | 9 | 0.4944 | **0.1287** |
| reserve listed, `rank ≥ 4`, thin history | 9 | 0.9364 | **0.4248** |
| unlisted with history | 10 | 0.1705 | **0.0134** |
| week-1 cold start, listed | 8 | 0.9884 | **0.4125** |
| clear RB1 | **0** | — | — |
| WR1 | **0** | — | — |

**The RB1 and WR1 cells are EMPTY tonight, and that is reported as empty rather
than filled with the wrong players.** The `espn_daily` vendor ranks
**offence-wide**, not within position: each club has exactly one rank 1 and
both clubs' rank 1 is a tight end. `depth_vintage` reports
`pos_slot_available: False` and 98 normalisation rank collisions. So "clear
RB1" is not constructible from tonight's chart, and the historical table in §7
is where that question is answered.

**A caution about tonight's chart that applies under either arm.** Only 37 of
the 58 skill-position players are listed, so "unlisted" tonight partly means
the chart is short rather than that the player is off the roster. Both arms
drive unlisted players to near zero — B's ten unlisted-with-history players run
0.0107 to 0.0202. A DEN running back with 79 prior frame rows and no carried
absence sits at 0.0201 under B and 0.0096 under the incumbent purely because
he is not on an 18-name chart. Neither arm is doing anything unreasonable given
its inputs; the input is thin, and that is a capture-coverage matter for L1.

### The configuration switch, and how the arm is recorded per row

**Switch name:** `nfl/production/nonqb/appearance_arm.py`.
**Selector:** `appearance_arm.predict(arm, season, week, players, injuries_rows, …)`
with `arm` one of four declared states.

| state | behaviour |
|---|---|
| `INCUMBENT_KNOWN_DEFECTIVE` | runs `appearance_r8`. **The default** (`DEFAULT_ARM`). |
| `CANDIDATE_B_LIVE_EVALUATION` | runs `appearance_b`. Recorded as an evaluation. |
| `CANDIDATE_B_CONFIRMED` | **BLOCKED**, `cause=Cause.GOVERNANCE` — confirmation needs games that took no part in selecting the hypothesis. |
| `CANDIDATE_B_PROMOTED` | **BLOCKED**, `cause=Cause.GOVERNANCE` — promotion is an owner decision in an owner artifact; no code path produces one. |

The last two exist as **named refusals** rather than absent options on purpose:
an unknown name is a typo, while a declared name that refuses with its reason is
a statement about what has and has not been established.

**How the arm reaches the row.** `predict` returns, per player, a dict rather
than a bare float — a float separates from its provenance the first time anyone
puts it in a table:

```
"00-0030506": {
  "p_appear": 0.9907286182954358,
  "appearance_arm": "CANDIDATE_B_LIVE_EVALUATION",
  "appearance_arm_governance": "LIVE EVALUATION -- authorised to run and to be
                                recorded. NOT promoted, NOT confirmed. ...",
  "appearance_spec_version": "appearance-b-union-candidate-universe-1",
  "appearance_coef_sha256": "88664d345948aed3",
  "appearance_module_sha256": "a3a1d5679314fb8c"
}
```

Both arms were run on the same universe with the same information set and both
are recorded, row by row, in
`nfl/research/remediation/l2/L2_LIVE_DEN_KC_APPEARANCE.json`.

**Nothing falls back.** An unrecognised arm is a `FAIL`, not the default. A
candidate arm's failure is returned as that arm's failure. `mod.predict` appears
exactly once in the switch and there is no `except` around it. A fallback would
put the promoted model behind a requested candidate name, which fails in the
dangerous direction: the operator believes they are evaluating B and is reading
the incumbent's defect.

**The incumbent is not touched.** `layers.py` knows nothing about either new
module, neither new module imports `layers`, and nothing in the existing
production chain imports `appearance_arm`. `B.union_frame` copies every row out
of R8's module-level cache rather than replacing `v1` in place, and a test
asserts zero shared objects — replacing them in place would have changed what
the incumbent predicts by aliasing rather than by intent.

---

## 9. What would make any of this confirmatory

Nothing available today. The hypothesis was selected from the same historical
panel every score was computed on, and §3's numbers are labelled EXPLORATORY by
the preregistration's own section 6. A confirmatory comparison needs untouched
games: a forward-chained future window, a sealed holdout, or nested cross-
fitting with every design decision made outside the evaluation fold. The
structural results in §4a and §5 are the exception, and they are exceptions
because they are properties of a construction rather than estimates — a
presence rate of exactly 1.0000 and bit-identical features under a label flip do
not become more or less true on a different sample.

Two further things are owed and are stated as owed rather than worked around:

* **The universe is still not the roster.** A union frame row is
  panel-or-depth-listed. A player with history who is not depth-listed and does
  not play still produces no frame row. Closing this needs weekly 53-man roster
  membership for 2020–2025, which is not in this checkout and is a request for
  the networked agent, not a candidate here.
* **The duplicate-ordinal ordering in `appearance_model._walk`** (§5) is an open
  defect against the frozen walk affecting 5.85% of frame rows, worth −0.0029
  Brier on the 2025 fold. Repairing it changes the incumbent too and belongs in
  its own baseline-then-one-change cycle.

---

## 10. Test suite

`python3.12 nfl/tests/run_suite.py --only test_appearance_candidate_b`

```
modules 1  test functions 22  checks 90  FAILING CHECKS 0  RAISED 0
ZERO-CHECK FUNCTIONS 0  BLOCKED FUNCTIONS 0
SUITE PASS
```

Three of the 22 are guards rather than demonstrations and are the ones to keep
if anything is ever cut: `test_the_incumbent_defect_is_still_there` (if it stops
finding the defect, every comparison here is measuring something else),
`test_the_switch_never_falls_back`, and `test_layers_py_is_untouched`.

---

## 11. Q9 hash check

| file | expected | actual | verdict |
|---|---|---|---|
| `nfl/production/nonqb/layers.py` | `481f005f682cd721…` | `481f005f682cd72129e6bf02e55cba86913ddffd7d88367743c616e3e11c0108` | **UNCHANGED** |

Verified at the start and at the end of this work. `nfl/capture/**`,
`nfl/vintage*`, `nfl/production/authorization.py` and `nfl/tools/make_board.py`
were not touched either.

**Files created by L2** (no existing file was modified):

```
nfl/production/nonqb/appearance_b.py
nfl/production/nonqb/appearance_arm.py
nfl/tests/test_appearance_candidate_b.py
nfl/research/remediation/l2/CANDIDATE_B_FREEZE.json
nfl/research/remediation/l2/L2_LIVE_DEN_KC_APPEARANCE.json
nfl/research/remediation/l2/L2_CANDIDATE_B_VALIDATION.md
```

Nothing was committed, added, stashed or pushed.

---

## 12. The clearance, restated

**Candidate B clears to run tonight as `CANDIDATE_B_LIVE_EVALUATION`**, as a
selectable configuration alongside the incumbent, with the arm stamped on every
row. It is not confirmed. It is not promoted. The incumbent remains the default.

**The decision is sealed as of this document, before the 2026-09-15T00:15:00Z
kickoff, and tonight's realised outcome is not evidence about whether Candidate
B was good.**
