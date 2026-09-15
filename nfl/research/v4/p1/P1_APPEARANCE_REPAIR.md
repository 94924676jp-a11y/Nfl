# P1 — the two appearance-path repairs from `AUTOPSY_DEN_KC.md` section 4

Date 2026-09-15. Files changed: `nfl/production/nonqb/appearance_r8.py`,
`nfl/production/nonqb/depth_vintage.py`, `nfl/production/candidate_mode.py`
(one new registered mode), `nfl/tests/test_p1_appearance_repair.py` (new), and
this directory. `nfl/production/nonqb/layers.py` is unchanged and still hashes
to `481f005f682cd72129e6bf02e55cba86913ddffd7d88367743c616e3e11c0108`,
verified at the start and the end of the work and asserted by a test.

Nothing was committed. No sportsbook price entered any part of this. No
realized DEN@KC outcome was read, sought, or used as a target anywhere.

---

## 0. Summary

Both defects are real and both reproduce exactly as described **as code
properties**. One claim in the autopsy does not survive as a *population*
statement and is corrected in section 6: on the historical cohort, R8 does
**not** on average penalise having a history. The perverse direction is a
property of the specific cold-start cell the DEN@KC board sat in, not of the
model everywhere, and the difference matters for how much the repair is
expected to buy.

The repair is registered as **`V1_CANDIDATE_R10`**, a successor to R9. R8's
and R9's coefficients are byte-identical after the change, verified season by
season. The mechanism is callable but **not wired into a board**: routing it
through a run needs a line in `nonqb/layers.py` (frozen) and one in
`run_forecast.py`, neither of which this repair owns. That is stated on the
candidate row itself rather than left for a reader to discover.

---

## 1. The failing tests, before any production code changed

`nfl/tests/test_p1_appearance_repair.py`, first run:

```
modules 1  test functions 12  checks 22  FAILING CHECKS 6  RAISED 1
    FAIL depth_vintage names a within-position rank scale  attribute missing
    FAIL an unknown rank scale is a named refusal  attribute missing
    FAIL candidate_mode registers the successor V1_CANDIDATE_R10  attribute missing
    FAIL featurise_r10 is monotone in f_weeks_since_appear  attribute missing
    FAIL appearance_r8 exposes the repaired featuriser featurise_r10  attribute missing
    FAIL relabelling the players cannot move a within-position rank  attribute missing
SUITE FAIL
```

The other 16 checks in that first run are **characterisation** checks and they
PASSED before the repair — they are the reproduction. They assert the defects
exist, and they must keep passing afterwards, because R8 and the offence-wide
depth scale are frozen lineage that this work does not edit:

```
  ok   R8 moves exactly one column with f_weeks_since_appear, no flag
  ok     None and 9 are the same number in R8
  ok     a real 0 is encoded as the MAXIMUM in R8, not the minimum
  ok     so R8 is not monotone in its own quantity
  ok   all twelve V1_NUMERIC features move a value AND a flag
  ok   four pos_rank-1 players receive four DIFFERENT ordinals
  ok     the club's RB1 is not ordinal 1
  ok     and the ordinal is decided by gsis_id alphabetical order
```

After the repair the same module runs 14 functions / 44 checks, 0 failing.

### Defect 1 as measured on the real frame (n = 59,742 union-frame rows)

| `f_weeks_since_appear` | n | R8 encodes | realised appearance rate |
|---|--:|--:|--:|
| 1 | 37,819 | 0.1111 | 0.8271 |
| 2 | 6,459 | 0.2222 | 0.4395 |
| 3 | 3,589 | 0.3333 | 0.2120 |
| 4 | 2,805 | 0.4444 | 0.1772 |
| 5 | 1,539 | 0.5556 | 0.9493 |
| 9 | 9 | **1.0000** | 0.8889 |
| 10–11 | 2 | **1.0000** | 0.0000 |
| `None` | 1,273 | **1.0000** | **1.0000** |
| v1 block absent | 6,116 | — | — |

**One correction to the autopsy, and it is in the project's favour.** The
autopsy's table lists `0` (appeared last week) as encoding to 1.0000. That is
true of the expression and **false of the data**: the generator is 1-based
(`next((i + 1 for ...)))` in `appearance_model.py:375` and `stage_a.py:148`),
so `0` never occurs in a stored row. The 0-collision is a **latent hazard**,
not an occurring one. The collision that *does* occur is `None` against 9+,
where 1,273 rows that appeared at rate 1.0000 are encoded identically to 11
rows that appeared at 0.5455. The repair closes both, structurally, rather
than arguing the latent one away.

### Defect 2 as measured on the real frame

Appearance rate by depth bucket, by vendor era:

| bucket | weekly era 2020-24 (n=48,543) | daily era 2025 (n=11,199) |
|---|--:|--:|
| r1 | 0.8930 (n=16,428) | 0.9136 (n=544) |
| r2 | 0.7018 (n=14,438) | 0.9357 (n=544) |
| r3 | 0.5186 (n=8,937) | 0.8805 (n=544) |
| r4+ | — (max rank 3) | 0.5648 (n=8,544) |
| unlisted | 0.2706 (n=8,740) | 0.0596 (n=1,023) |

The weekly era is monotone and tops out at rank 3 because
`depth_vintage.weekly` emits a **group inside (season, week, club, position)**.
The daily era runs to rank 27 with exactly 544 rows at each ordinal — 32 clubs
× 17 weeks, one player per ordinal — and is **flat across r1/r2/r3**, because
those buckets are the three alphabetically-first `pos_rank == 1` players on the
club, not roles. Rank-1 position mix in the daily era: QB 211, RB 143, TE 125,
WR 65.

**So the defect is worse than "the ordinal is contaminated": one column of one
design row held two different quantities in two eras.**

---

## 2. The fix

### `depth_vintage.py` — a second scale supplied, the first untouched

`daily(text, scale=OFFENCE_WIDE)` and
`captured(teams, observed_before, blobs=None, scale=OFFENCE_WIDE)`. Under
`WITHIN_POSITION` the ordinal is built inside `(team, dt, normalised position)`
using the *same* sort key — vendor `pos_rank`, then the (absent) `pos_slot`,
then `gsis_id`. Nothing new decides an order; what changes is who is compared.
An unknown scale is `FAIL DEPTH_DAILY_RANK_SCALE_UNKNOWN`, never a default.

**The default is unchanged, and this was proved rather than asserted.** The
pre-repair module was loaded from `git show HEAD:` beside the new one and run
on the real 2025 leaf and the six captured blobs: `daily()` values **identical**,
`captured()` values **identical**; the only evidence difference is the added
`rank_scale_name` key, and the `rank_scale` prose for the default is
byte-identical.

On the within-position scale each team-snapshot has exactly one rank-1 player
per position (7,066–7,071 of each of QB/RB/WR/TE across the 2025 leaf), and
re-labelling the players cannot move a rank.

### `appearance_r8.py` — a successor beside R8, not an edit of it

Everything above the new banner is untouched. Added:
`SPEC_VERSION_R10`, `RANK_SCALE_R10`, `within_position_overlay`,
`enriched_frame_r10`, `featurise_r10`, `N_FEATURES_R10` (78 = 77 + 1),
`fit_r10`, `predict_r10`.

* **Repair 1** — `f.append(0.0 if v is None else min(max(float(v), 0.0), 9.0) / 9.0)`
  then `f.append(1.0 if v is None else 0.0)`. Value then flag, exactly the
  treatment the twelve `V1_NUMERIC` features already get; an explicit
  `is None` test rather than a falsy one; monotone non-decreasing across the
  whole range with a real 0 at the **minimum**.
* **Repair 2** — the frame carries a NEW key `rank_pos`; `rank` is not mutated
  on any row, and rows are copied rather than annotated so R7, R8 and
  `pool_audit` cannot see the new key. Weekly-era rows need no overlay (their
  rank is already the within-position quantity); 11,199 daily-era rows are
  rescaled, of which **9,586 move**. The overlay refuses by name if the two
  scales ever disagree about *who is listed* (`R10_OVERLAY_LISTEDNESS_DISAGREES`)
  — they do not: 10,176 listed either way, 1,023 unlisted either way.
* `featurise_r10` **raises `R10_RANK_SCALE_MISSING`** on a row with no
  `rank_pos`, and `predict_r10` **refuses** a caller-supplied depth chart that
  does not declare `within_position`. A silent fall-back to `rank` would
  reintroduce the train/serve break through a keyword argument.

### `candidate_mode.py` — `V1_CANDIDATE_R10`

`R10_FLAGS = R9_FLAGS - {appearance_r8} + {appearance_r10: True}`; the R9
quarterback room is carried over unchanged. One appearance mechanism per
configuration, the same rule R8 applied to R7. `R10_REPAIR` records the defect,
the evidence, that it refits, that it introduces no constant, that it is
EXPLORATORY, and that it is **not wired to a board**.

**Old seals preserved — measured, not asserted.** R8 `coef_sha256` before and
after the change, on identical data:

| fit season | before | after |
|---|---|---|
| 2022 | `efa220d9c7c67a96` | `efa220d9c7c67a96` |
| 2023 | `1a364aaed2220119` | `1a364aaed2220119` |
| 2024 | `eab453701a9dc386` | `eab453701a9dc386` |
| 2025 | `b8ed98895f033251` | `b8ed98895f033251` |
| 2026 | `3cc23577a3d234ba` | `3cc23577a3d234ba` |

R8 `SPEC_VERSION` and `N_FEATURES` (77) unchanged. R10's 2026 fit hashes to
`5fe9fb485a260e3f` — a different model, as it must be. The 2026 comparison is
pinned in the test module so a future edit to R8 fails loudly.

---

## 3. The cohort: forward-chained, 2022–2025

`nfl/research/v4/p1/cohort.py` → `P1_COHORT_EVIDENCE.json`. Same construction
R8's own evidence used: train on seasons strictly earlier, score that season,
identical rows, identical `is_unsupported` exclusion, identical l2 = 1.0, and
the **same** `k` in both arms (`k` is estimated from appearance outcomes alone
and neither repair touches it). 40,579 scored rows, base rate 0.6290.

| pooled | R8 | R10 |
|---|--:|--:|
| Brier | 0.08931 | **0.08880** |
| log loss | 0.28731 | **0.28597** |
| AUC | 0.94269 | 0.94294 |
| ECE (10 bins) | 0.01699 | **0.01555** |

Paired Brier difference, **bootstrapped over team-weeks** (2,174 blocks, 2,000
resamples — players inside a team-week appear or sit together, so a row-level
interval would pretend 40,000 correlated rows are 40,000 observations):
**−0.000512, 95% CI [−0.000718, −0.000317]**.

That interval excludes zero and the effect is **small**: 0.6% of the Brier
score. It should not be dressed up as more.

By season, which is where the story is:

| eval season | R8 Brier | R10 Brier | paired diff [95% CI] |
|---|--:|--:|---|
| 2022 | 0.09055 | 0.09041 | −0.000137 [−0.000219, −0.000048] |
| 2023 | 0.08527 | 0.08527 | +0.000004 [−0.000114, +0.000116] |
| 2024 | 0.08402 | 0.08388 | −0.000139 [−0.000223, −0.000057] |
| **2025** | 0.09629 | **0.09467** | **−0.001616 [−0.002308, −0.000923]** |

2025 is the only daily-vendor season — the only one the depth repair can
touch — and it carries almost all of the effect.

**Ablation (diagnostic only; the two repairs remain one candidate because both
move the coefficients and neither is a control for the other).** Brier, and
week-1 Brier, by arm:

| season | R8 | weeks repair only | rank repair only | R10 |
|---|--:|--:|--:|--:|
| 2022 | 0.090551 | 0.090414 | 0.090551 | 0.090414 |
| 2023 | 0.085267 | 0.085271 | 0.085267 | 0.085271 |
| 2024 | 0.084022 | 0.083883 | 0.084022 | 0.083883 |
| 2025 | 0.096288 | 0.096228 | **0.094695** | 0.094672 |
| 2025 week 1 | 0.077031 | 0.076895 | **0.064358** | **0.064600** |

The rank repair is exactly inert before 2025, as it must be. In 2025 week 1 —
the cold-start regime the DEN@KC board sits in — it moves Brier
**0.0770 → 0.0646, a 16% relative improvement**.

**Calibration, honestly.** Pooled ECE improves. In 2025 alone it **worsens**,
0.02047 → 0.02519, while Brier and log loss improve — the repaired model is
sharper and slightly less well centred in that season. The reliability tables
for both arms are in the JSON; the two curves are close, with R10 moving mass
into the top bin (15,296 → 15,910 rows at p ≥ 0.9, realised 0.9746 vs 0.9723).
Neither arm is "well calibrated" in any tested sense: no equivalence margin was
predeclared and no TOST was run, so this paragraph reports numbers and claims
nothing.

---

## 4. With a history versus without

Predeclared split on `n_prior` (prior frame rows), pooled over 2022–2025:

| history | n | realised | mean p R8 | mean p R10 | Brier R8 | Brier R10 |
|---|--:|--:|--:|--:|--:|--:|
| none (0) | 431 | 0.4780 | 0.4774 | 0.4780 | 0.00011 | 0.00014 |
| short (1–7) | 3,512 | 0.5433 | 0.5350 | 0.5384 | 0.08669 | 0.08611 |
| medium (8–15) | 3,823 | 0.5883 | 0.5765 | 0.5799 | 0.10152 | 0.10100 |
| long (16+) | 32,813 | 0.6449 | 0.6462 | 0.6516 | 0.08934 | 0.08883 |

Both arms are close to the realised rate in every bucket. R10 is slightly
better in three of four and slightly worse in the smallest.

By week bucket (for comparison with the table in R8's own docstring):

| bucket | n | realised | Brier R8 | Brier R10 |
|---|--:|--:|--:|--:|
| w1 | 2,936 | 0.5037 | 0.05416 | **0.05091** |
| w2–4 | 8,548 | 0.5240 | 0.08962 | 0.08900 |
| w5–9 | 10,010 | 0.6765 | 0.09141 | 0.09146 |
| w10–18 | 19,085 | 0.6703 | 0.09348 | 0.09315 |

---

## 5. The Walker/Johnson counterfactual, at the sealed cutoff

`nfl/research/v4/p1/counterfactual.py` → `P1_COUNTERFACTUAL_EVIDENCE.json`.
Cutoff `2026-09-14T20:58:33Z`, roster and injury vintages both selected
point-in-time through `vintage_selector.clock`, 58 KC/DEN skill players,
182 injury rows.

**The replay reproduces the sealed board's appearance layer exactly.** R8 at
this cutoff returns RB1 **0.723664**, RB2 **0.992530**, RB3 **0.762094** —
the three numbers in the autopsy to six decimals.

The allocation step is **replicated**, not run (`layers.py` is frozen): each
draw keeps player *i* with probability *p*, and the class weights `C` are
renormalised over the survivors, 200,000 draws. The replication is checked
against two facts the sealed board already fixes:

* at `p = 1` it returns the normalised carry prior **exactly** (max error
  0.00000);
* at the sealed R8 probabilities it returns 0.3920 / 0.4403 / 0.1677 against
  the sealed board's 0.4133 / 0.4170 / 0.1511 — max error **0.0233**, with the
  same inversion. (The autopsy prints the three sealed shares unlabelled and
  not in the order of the table above them; they are assigned here from the
  sealed carry means 8.345 / 8.420 in the same document. That reading is
  recorded on the artifact.)

| | carry prior (normalised) | R8 p | R8 expected share | R10 p | R10 expected share |
|---|--:|--:|--:|--:|--:|
| RB1 (long history, new club) | 0.5142 | 0.723664 | 0.3920 | **0.969951** | **0.5282** |
| RB2 (no NFL history) | 0.3166 | 0.992530 | 0.4403 | 0.995362 | 0.3454 |
| RB3 (short history) | 0.1692 | 0.762094 | 0.1677 | 0.723450 | 0.1264 |

**Verdict: the corrected layer preserves the pregame carry prior.** R8 inverts
the order (RB2 ahead of RB1) with a maximum departure of 0.1237; R10 keeps the
prior's order with a maximum departure of 0.0428, and the largest single
departure is now RB3 losing 0.043, not RB1 losing 0.122.

**What the repair does NOT do, stated plainly.** R10 still gives the
historyless back a marginally *higher* appearance probability than the
veteran — 0.9954 against 0.9700. The gap falls from 0.2689 to 0.0254, and at
those levels the binarise-and-renormalise step barely distorts the prior, which
is why the ordering is restored. But the sign of that small gap is unchanged,
and a claim that "the perverse direction is gone" is only true of the
consequence, not of the probability. There is also **no lawful pregame evidence
to depart from the prior here**: no injury row exists for any of the three
backs at the cutoff (checked, 11 KC rows, none of them a back), and the depth
chart lists them 1/2/3 within the RB room.

---

## 6. Where the autopsy overstates, and it matters

The autopsy says, of defect 1: *"Having a history is being penalised."* On the
**historical cohort that claim does not hold as a population statement.**
Predeclared cells, pooled 2022–2025, depth-listed at rank 1 within their own
position room:

| cell | n | realised | mean p R8 | mean p R10 |
|---|--:|--:|--:|--:|
| rank 1, no history | 28 | 0.8214 | 0.8291 | 0.8308 |
| rank 1, long history (16+) | 9,782 | 0.9001 | 0.8867 | 0.8867 |
| **long − none** | | **+0.0787** | **+0.0576** | **+0.0559** |

R8's sign is the same as the realised sign. So R8 does not, on average, punish
history; the ablation agrees, since the weeks-encoding repair alone is worth
only ~0.0001 Brier in every season.

Both statements are true at once, and the distinction is the useful part: the
**encoding defect is real** (`None` and 9+ are one number, and no flag
separates them), and its **population-level cost is small**, while the cell it
damages badly is the one the DEN@KC board was in — a week-1 cold start where
the missing-history category is the whole signal. The measured 39% of the
logit gap in that cell and the ~0.0001 Brier across 40,579 rows are not in
conflict; they are the same defect seen at two magnifications. The repair is
justified as a **correctness** fix with a small measured benefit, not as a
performance win, and the write-up should not have to be re-litigated later
because it promised more than the cohort shows.

---

## 7. Governance

**EXPLORATORY, and it cannot be otherwise.** Both defects were found by reading
a sealed board built from these same seasons, and the repair was designed with
the frame in front of me. Forward chaining controls parameter leakage; it says
nothing about specification leakage. A confirmatory claim needs games nobody
has looked at.

No constant is introduced by either repair. `k` is untouched and identical in
both arms. No threshold was loosened, no floor or clip exists anywhere in the
new code, and no realised outcome is a target in any script here.

### Suites run (`python3.12 nfl/tests/run_suite.py --only <module>`)

| module | result |
|---|---|
| `test_p1_appearance_repair` (new) | PASS — 14 functions, 44 checks |
| `test_r8_synthesis` | PASS — 69 checks |
| `test_r7_appearance_frame` | PASS — 67 checks |
| `test_nonqb_r3` | PASS — 129 checks |
| `test_pool_audit` | PASS — 38 checks, 1 declared BLOCKED (pre-existing) |
| `test_appearance_candidate_b` | PASS — 90 checks |
| `test_may_publish` | PASS — 94 checks |
| `test_r5_active_pool` | PASS — 24 checks |
| `test_r6_role_prior` | PASS — 24 checks |
| `test_v1_scramble_coherence` | PASS — 24 checks |

### Still owed, and not done here

* **R10 is not wired to a board.** `layers._run_real` dispatches on
  `appearance_spec` and `run_forecast._appearance_spec` maps the flags; both
  files are outside this repair (`layers.py` is frozen at
  `481f005f682cd721`). Until an owner of those files adds the `r10` branch, no
  sealed board can run this mechanism.
* `f_n_teammates_out` in the same block still reads `or 0.0`, folding "no v1
  block" into "zero teammates out". It is not non-monotone and is out of scope
  here, but it is the same class of defect one column over.
