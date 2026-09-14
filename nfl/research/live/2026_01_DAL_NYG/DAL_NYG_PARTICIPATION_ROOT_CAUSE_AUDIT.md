# DAL_NYG_PARTICIPATION_ROOT_CAUSE_AUDIT

**AUDIT ONLY. No repair was implemented. No candidate projection was produced.
No market data was opened.** Both sealed artifacts were read and neither was
rewritten: `pre_inactives_V1_CANDIDATE_R8/3dddf9f62c9260b0` and
`FORENSIC_CORRECTED_RESEARCH/4b186a21b83a49ec`.

---

## The finding table

| # | finding | status | exact code path | exact data evidence | earliest failure point | repair class |
|---|---|---|---|---|---|---|
| 1 | The DAL/NYG QB split is produced mechanically by ONE bit, `was_prev_primary` | **CONFIRMED_MECHANISM** | `qb_allocation.py:193` → `qb3_lib.py:130 cell_of` → `:157 allocate` | Reproduction matches the seal to ≤0.004 on all six QBs. Counterfactual: flipping that bit alone moves Prescott 0.5474 → 0.8937 | `previous_primary()` resolves the incumbent by ordinal ACROSS the season boundary; in week 1 it returns the prior season's week-18 starter | SPECIFICATION_DEFECT |
| 2 | The QB draw is a pregame starter-selection mixture, not contingent replacement | **CONFIRMED_MECHANISM** | `qb3_lib.py:171` (identity drawn first) → `:182` (bimodal pool resampled) → `:186-192` (remainder to "the others") | 86% of draws put one QB at 31+ dropbacks and the other at exactly 0; corr = −0.9240; P(exactly one >10) = 0.9795; P(Dak = 0) = 0.4273 | `qb3_lib.fit()` builds the share pool over ALL depth-charted QB-games in a cell, mixing "did not start" (share 0) with "started and finished" (share 1) | SPECIFICATION_DEFECT |
| 3 | Skill-player zero mass is an INDEPENDENT per-player Bernoulli with no shared latent | **CONFIRMED_MECHANISM (answer B)** | `football_engine.py:314` → `layers.py:84 appearance` → `appearance_r8.py:405-440` → `layers.py` `A = (A > 0)` | Max pairwise zero-indicator correlation 0.0228; every joint matches the independent product to 3 dp | The appearance draw carries no team or game latent | SPECIFICATION_DEFECT |
| 4 | Appearance probabilities are INVERTED: the two officially inactive players rank highest, the RB1 near lowest | **CONFIRMED_MECHANISM** | `appearance_r8.py:263 featurise`, fields `n_prior`, `cm_carried` | Camden Brown (INACTIVE, `n_prior`=0) **0.9895**; Abanikanda (INACTIVE, `cm_carried`=13) **0.9465**; Lamb 0.8760; Javonte Williams (RB1) **0.6580** | cold-start default sits at the TOP of the range; carried absence is unused or wrong-signed | SPECIFICATION_DEFECT |
| 5 | No pregame eligibility signal exists at all | **CONFIRMED_MECHANISM** | `weekly_rosters.cef497eaeddef07b.reduced.csv.gz`; `ingest/allowlist.py`; `capture/delivered_injuries.py:113` | The vintage carries exactly `season, week, team, gsis_id, position`. No status column | `weekly_rosters.status` is quarantined POSTHOC — correctly — and nothing replaced it | DATA_GAP / SPECIFICATION_GAP |
| 6 | The QB pool is EXEMPT from the one eligibility filter that does exist | **CONFIRMED_MECHANISM** | `run_forecast.py` R5 block: `nonqb = [q for q in players if q.get('position') != 'QB']` | Jake Haener (0.0311) and Joe Milton III (0.5332 in the sealed PRE) reached the room without passing it | the declared R5 exemption | SPECIFICATION_DEFECT |
| 7 | `role_certainty` measures MAGNITUDE of share, never uncertainty | **CONFIRMED_MECHANISM** | `confidence.py:121 _role()` | `min(1.0, sh/0.8)` for QB, `min(1.0, sh/0.25)` for skill. No variance, IQR, entropy or P(zero) term appears | the dimension was specified as a share rescaling | SPECIFICATION_DEFECT |
| 8 | `role_certainty`'s denominator is the GAME, not the team, contradicting its own docstring | **CONFIRMED_MECHANISM** | `confidence.py:121`, `tot.sum(0)` over every row of the array | Docstring says "his own team's opportunity"; stored reason says "40% of the game's quarterback dropbacks"; 22.02/(40.65+32.80)=0.2999 | `tot` spans both teams | IMPLEMENTATION_DEFECT |
| 9 | Governance tokens are free text and gate nothing | **CONFIRMED_MECHANISM** | stage `spec_version` strings; `warnings` lists; `artifact.py:84-115` class table | `conversion` is PASS carrying `SIGNAL_WEAK; governance HOLD_CHARACTERIZED + CALIBRATION_DEFECT` in a spec string | `state = PASS` means "the stage ran", never "the model is sound" | SPECIFICATION_DEFECT |
| 10 | Team volume is NOT downward-biased and DAL/NYG are not unusually low | **FALSIFIED** (as a defect) | `team_volume` layer, graded via `research/postgame.py` | 18 team-games: carries z=+0.02, targets z=+0.07, dropbacks z=+0.46. DAL sits ABOVE the slate mean on carries (+0.72), targets (+2.90) and dropbacks (+4.01) | n/a | NO_REPAIR — preserve |
| 11 | Hypothesis 1's proposed chain runs through Stage2 ewma_hl2. It does not. | **FALSIFIED** (as stated) | `qb3_lib` never reads the non-QB participation stage | `Stage2 ewma_hl2; governance INFORMATION_CONSTRAINED` is the spec_version of the NON-QB stage | n/a | RECLASSIFY — two separate participation mechanisms, both defective, for different reasons |
| 12 | *Incidental*: the committed Q9 dry-run proof asserts DETERMINISTIC, which re-running falsifies | **CONFIRMED_MECHANISM** | `q9shadow/dryrun.py:163` | Re-run today: 9/10, two seals differ on `artifact_id`, `forecast_id`, `seal_payload_sha256`, `identity_fingerprint` (draw and spec hashes match) | a stale proof artifact is read as evidence of a property that no longer holds | IMPLEMENTATION_DEFECT (out of scope here, reported not repaired) |

---

## Hypothesis 1 — historical realised participation as forward probability

### Verdict: PARTIAL_MECHANISM

**Confirmed.** The two clubs' splits are produced mechanically, and the
reproduction from stored inputs through code is exact:

| | reproduced | sealed |
|---|--:|--:|
| DAL Prescott | 0.4176 | 0.4132 |
| DAL Howell | 0.0515 | 0.0536 |
| DAL Milton | 0.5309 | 0.5332 |
| NYG Dart | 0.8916 | 0.8914 |
| NYG Winston | 0.0769 | 0.0774 |
| NYG Haener | 0.0315 | 0.0311 |
| DAL 2-QB (forensic) Prescott | 0.5474 | 0.5416 |
| DAL 2-QB (forensic) Howell | 0.4526 | 0.4584 |

### Every numerical intermediate

**Step 1 — `previous_primary_detail()`**

| team | pid | name | ordinal | is_season_opener |
|---|---|---|--:|---|
| DAL | 00-0039398 | **Joe Milton III** | 202518 | true |
| NYG | 00-0040691 | **Jaxson Dart** | 202518 | true |

**Step 2 — captured depth chart**, retrieved `2026-09-08T11:56:57Z`:
DAL Prescott=1, Howell=2. NYG Dart=1, Winston=2.

**Step 3 — the triples production builds** `(pid, min(rank,3), was_prev)`:
DAL Prescott(1,0), Howell(2,0), Milton(3,1). NYG Dart(1,1), Winston(2,0), Haener(3,0).

**Step 4 — `cell_of()` and the fitted pool each lands in**

| cell | n | p_primary | mean_share | P(share=0) | P(share=1) | holder |
|---|--:|--:|--:|--:|--:|---|
| (1, 0) | 321 | 0.4922 | 0.4946 | **0.4735** | 0.4424 | Dak Prescott |
| (2, 0) | 2436 | 0.0686 | 0.0794 | 0.8120 | 0.0435 | Howell / Winston |
| ('2+', 1) | 240 | 0.6167 | 0.5979 | 0.3458 | 0.5083 | Joe Milton III |
| (1, 1) | 2349 | 0.9046 | 0.8919 | **0.0736** | 0.7765 | Jaxson Dart |
| (3, 0) | 1100 | 0.0282 | 0.0323 | 0.9318 | 0.0173 | Jake Haener |

**Step 5 — P(drawn primary), normalised**: DAL [0.4180, 0.0582, 0.5237];
NYG [0.9034, 0.0685, 0.0281].

### What is confirmed, and what is not

**Confirmed.** The entire difference between the two clubs is ONE input.
Prescott and Dart are both the rank-1 charted QB1 of their club. The only
thing separating them is who started their club's week-18 game last season.
That routes Prescott into cell (1,0) and Dart into cell (1,1) — pools whose
P(share=0) differ by a factor of **6.4**.

**The counterfactual settles it.** Holding the room, the seed, the draw index
and everything else fixed, and flipping only `was_prev_primary` 0→1 for
Prescott:

```
as sealed:        Prescott 0.5474   Howell 0.4526
was_prev = 1:     Prescott 0.8937   Howell 0.1063
```

One bit is worth 35 points of Dak Prescott's dropbacks.

**Not confirmed — and this is why the verdict is PARTIAL.** It is *not*
"Dallas's historical QB churn" in any diffuse sense. Dallas's roster history,
Prescott's own participation record and Howell's are **not inputs to the split
at all**. `cell_of()` reads exactly two things: the clipped depth rank and the
incumbent bit. And using realised participation to estimate a forward
probability is not itself the error — empirical frequencies over comparable
cells are a legitimate estimator. The defects are *which cell* (H1) and *what
the pool pools* (H2).

**A correction to the hypothesis as posed.** The proposed chain runs through
`Stage2 ewma_hl2`. It does not. That string is the `spec_version` of the
**non-QB** participation stage; `qb3_lib` never reads it. There are two
separate participation mechanisms and both are defective, for different
reasons — see H3.

---

## Hypothesis 2 — starter-selection mixture, not contingent replacement

### Verdict: CONFIRMED_MECHANISM

From the 8,000 stored draws of `FORECAST 4b186a21b83a49ec` (2-QB room):

| QB | mean | share | P(0) | P(1–10) | P(11–20) | P(21–30) | P(31+) |
|---|--:|--:|--:|--:|--:|--:|--:|
| Dak Prescott | 22.02 | 0.5416 | **0.4273** | 0.0189 | 0.0141 | 0.0426 | **0.4971** |
| Sam Howell | 18.63 | 0.4584 | 0.4850 | 0.0484 | 0.0089 | 0.0419 | 0.4159 |

Conditional on playing: Prescott mean 38.44 (p10 25, p50 39, p90 54); Howell
mean 36.18 (p10 14, p50 36, p90 49). **Both look like full-game starters when
they appear at all.**

Sealed PRE (3-QB room): Prescott 16.80 / P(0)=0.4700; Howell 2.18 /
P(0)=0.5131; Milton 21.67 / P(0)=0.3695.
NYG: Dart 29.24 / P(0)=0.0696; Winston 2.54 / P(0)=0.7519; Haener 1.02 /
P(0)=0.7645.

### The joint distribution settles it

DAL, forensic run, fraction of 8,000 draws:

| Dak \ Howell | 0 | 1–10 | 11–20 | 21–30 | 31+ |
|---|--:|--:|--:|--:|--:|
| **0** | 0.0000 | 0.0000 | 0.0000 | 0.0232 | **0.4040** |
| 1–10 | 0.0000 | 0.0000 | 0.0019 | 0.0089 | 0.0081 |
| 11–20 | 0.0000 | 0.0010 | 0.0019 | 0.0080 | 0.0032 |
| 21–30 | 0.0293 | 0.0097 | 0.0014 | 0.0018 | 0.0005 |
| **31+** | **0.4557** | 0.0376 | 0.0037 | 0.0000 | 0.0000 |

- The two corner cells alone hold **0.8597** of all draws.
- **corr(Dak, Howell) = −0.9240**
- P(exactly one of them > 10 dropbacks) = **0.9795**; P(both > 10) = 0.0205

This is *choose a QB identity, then give him the near-full game*. There is
essentially no mass representing "started and was replaced": the 11–20 and
21–30 bins together hold 0.0567 for Prescott and 0.0508 for Howell.

**P(Dak Prescott takes ZERO dropbacks) = 0.4273.** The QB participation causal
audit measured the realised rate for an established incumbent at **0 of 1,700
team-games**. Dart's 0.0696 reproduces cell (1,1)'s P(share=0)=0.0736 — the
same defect, two orders smaller because his cell is the clean one.

### Why

`qb3_lib.allocate` step 2 RESAMPLES the primary's share from the cell's
empirical pool. Cell (1,0) is bimodal *by construction*: P(share=0)=0.4735,
P(share=1)=0.4424, with only 0.084 of mass in between. The pool **mixes two
populations** — team-games in which the charted QB1 did not start, and
team-games in which he started and finished. Resampling it per draw converts a
*pregame selection event* into a *within-game share*.

The repository already says so, at `qb_allocation.py:497`: *"`Q.allocate`
samples the primary's share from an empirical pool whose modal value is exactly
1.0 — 77.7% of the (rank 1, previous primary) pool and 44.2% of (rank 1, not
previous primary). Those draws are ONE-HOT."*

---

## Hypothesis 3 — independent skill-player zero inflation

### Verdict: CONFIRMED_MECHANISM — answer **B**, independent player appearance Bernoulli

Pairwise correlation of zero indicators, forensic run, 8,000 draws:

| | Dak | Lamb | Ferguson | Pickens | Javonte |
|---|--:|--:|--:|--:|--:|
| **Dak** (0 db) | +1.0000 | −0.0077 | +0.0064 | +0.0049 | +0.0149 |
| **Lamb** (0 tgt) | −0.0077 | +1.0000 | +0.0003 | −0.0056 | +0.0175 |
| **Ferguson** (0 tgt) | +0.0064 | +0.0003 | +1.0000 | −0.0220 | −0.0047 |
| **Pickens** (0 tgt) | +0.0049 | −0.0056 | −0.0220 | +1.0000 | −0.0228 |
| **Javonte** (0 car) | +0.0149 | +0.0175 | −0.0047 | −0.0228 | +1.0000 |

Maximum absolute off-diagonal: **0.0228**. And every joint matches the
independent product:

| pair | observed | independent would give |
|---|--:|--:|
| Dak=0 & Lamb=0 | 0.0536 | 0.0549 |
| Dak=0 & Ferguson=0 | 0.0746 | 0.0734 |
| Dak=0 & Pickens=0 | 0.1017 | 0.1007 |
| Dak=0 & Javonte=0 | 0.1472 | 0.1438 |

**There is no shared QB/team latent.** The model can and does draw games in
which Prescott plays every snap and CeeDee Lamb sees zero targets.

### The appearance probabilities themselves — the larger finding

Recomputed through the production path (`appearance_r8`, the arm
`V1_CANDIDATE_R8` names) at the sealed evidence clock:

| player | p_app | rank | n_prior | prev_app | cm_carried |
|---|--:|--:|--:|--:|--:|
| **Camden Brown** (WR6, **OFFICIALLY INACTIVE**) | **0.9895** | 18 | **0** | None | 0 |
| **Israel Abanikanda** (RB3, **OFFICIALLY INACTIVE**) | **0.9465** | 10 | 27 | 0 | **13** |
| CeeDee Lamb (WR1) | 0.8760 | 2 | 101 | 1 | 0 |
| Ryan Flournoy | 0.8650 | 12 | 34 | 1 | 0 |
| Jake Ferguson (TE1) | 0.8635 | 4 | 68 | 1 | 0 |
| George Pickens (WR2) | 0.7795 | 7 | 72 | 1 | 0 |
| **Javonte Williams (RB1)** | **0.6580** | 3 | 80 | 0 | 1 |
| Parris Campbell | 0.1600 | None | 70 | 0 | 5 |

**The two players declared officially inactive carry the two highest
appearance probabilities on the roster, and the lead back one of the lowest.**

The arithmetic closes: Javonte Williams P(carries=0) in the draws = 0.3365
against 1 − 0.6580 = 0.3420. Lamb P(targets=0) = 0.1285 against 1 − 0.8760 =
0.1240. **The appearance Bernoulli IS the zero mass.**

Drivers, from the captured feature rows: Camden Brown is a pure **cold start**
(`n_prior` = 0) and the cold-start default sits at the *top* of the range;
Abanikanda carries **13 consecutive missed games across the season boundary**
(`cm_carried` = 13) and is rated near-certain to play, so that field is either
unused or wrong-signed.

### A correction to my own first trace

I initially named `par['q_zero']` (WR 0.1713, TE 0.3062, RB 0.3093) as the
zero mechanism. It is **not on production's path**: `gen_weights` returns at
the system-`C` branch (`p4c_build.py:283`) before reaching it; `q_zero` belongs
to a D-family generator. The second, smaller zero source is the clip
`np.clip(C + residual, 0, 1)`, which for a WR at C=0.232 fires in only 0.0019
of draws — but at C=0.010 fires in 0.4919, so it dominates deep on the bench
and not at the top.

---

## Eligibility gate

Two distinct causes. **Neither is a crosswalk or join defect.**

**Cause 1 — no pregame eligibility signal exists.** The roster vintage
production reads,
`nfl/vintage/weekly_rosters.cef497eaeddef07b.reduced.csv.gz`, carries exactly
five columns: `season, week, team, gsis_id, position`. There is **no status
column**. `weekly_rosters.status` is quarantined POSTHOC in
`nfl/ingest/allowlist.py`, and correctly — after a team plays the vendor
re-partitions ACT/INA into *who dressed* (measured: SF ACT 53 before playing,
NE ACT 48 + INA 7 after), so a retrospective ACT predicts snaps at 0.9715
almost tautologically. `delivered_injuries.py:113` lists it in
`ROSTER_FORBIDDEN_COLUMNS`.

Consequence: **active-53, practice squad, reserve lists, elevations and
releases are all indistinguishable pregame.** Haener, Slayton, Campbell,
Camden Brown, Abanikanda and Milton each appear as one identical roster row.

**Cause 2 — the QB pool is exempt from the filter that does exist.** R5 in
`run_forecast.py`: `nonqb = [q for q in players if q.get('position') != 'QB']`,
with the comment *"The QB pool is untouched."* So Jake Haener reached the room
without passing even the roster-membership filter, and so did Joe Milton III,
who held 53.3% of Dallas's dropbacks in the sealed PRE artifact. The stated
justification for that exemption — *"its shares are already correct, the
starters hold 88–91%"* — is exactly what this audit falsifies for a DISAGREE
room.

| player | earliest defect | on official inactive list | share |
|---|---|---|--:|
| Jake Haener (NYG QB3) | R5 QB exemption | no | 0.0311 of NYG dropbacks |
| Darius Slayton (NYG WR) | no active-53 signal exists; passes R5 as a roster member | no | 0.004 of game targets |
| Parris Campbell (DAL WR) | same | no | 0.008 of game targets |

For Slayton and Campbell the gate behaved **as specified**. A rostered WR with
a small share is not by itself a defect; whether either should be in the pool
cannot be answered from governed pregame data at all.

**The gate that should own this does not exist.** There is no pregame
eligibility layer keyed on active-53 / practice-squad / reserve status. The
only governed game-day eligibility evidence in the system is the official
inactive list, which arrives ~90 minutes out and is per game.

---

## Team volume

**Verdict: FALSIFIED as a defect. Do not classify DAL/NYG team volume as
defective, and do not widen or shift the layer.**

Calibration of the estimator against authoritative play-by-play, 2026 week-1
early window, 18 team-games:

| quantity | projected | actual | bias | se | z | basis |
|---|--:|--:|--:|--:|--:|---|
| team_carries | 27.48 | 27.44 | +0.037 | 1.618 | **+0.02** | EXACT |
| team_targets | 30.29 | 30.17 | +0.128 | 1.868 | **+0.07** | EXACT |
| team_dropbacks_part | 36.88 | 35.94 | +0.939 | 2.036 | **+0.46** | SURROGATE (upper bound) |

**Are the DAL/NYG values unusually low relative to the estimator's own
distribution? No — three of four DAL quantities sit ABOVE the slate mean.**

| | DAL | NYG | slate mean of projections |
|---|--:|--:|--:|
| team_carries | 28.20 | 31.51 | 27.48 |
| team_targets | 33.19 | 28.18 | 30.29 |
| team_dropbacks_part | 40.89 | 32.89 | 36.88 |
| team_off_snaps | 69.67 | 65.52 | — |

DAL vs slate: carries **+0.72**, targets **+2.90**, dropbacks **+4.01**.

### The two labels must stay distinct

- **`team_volume_is_near_unforecastable`** is a statement about
  **discrimination and dispersion**. The predictive intervals are genuinely
  wide — DAL team_carries sd 5.89, p05 19.43 to p95 45.29 — and the estimator
  cannot tell one game from another. That is what the label means and it is
  honest.
- **`MODEL_VOLUME_BIAS`** is a statement about the **mean**. It is **not
  supported**: z = +0.02, +0.07, +0.46, all positive if anything.

Conflating them would license shifting the team layer on evidence that does
not exist. The layer's weakness is that it is *uninformative*, not that it is
*low*.

---

## Confidence layer

**Verdict: CONFIRMED — `role_certainty` measures the MAGNITUDE of the
projected share and contains no uncertainty term of any kind.**

`confidence.py:121 _role()`:

```
QB    : sh = mean(this player's qb/db) / mean(sum over ALL qb/db rows)
        score = min(1.0, sh / 0.8)
skill : sh = mean(this player's metric) / mean(sum over ALL rows)
        score = min(1.0, sh / 0.25)
```

Inputs used: the player's mean draw, and the array-wide mean.
Inputs **not** used: variance, IQR, entropy, P(zero), any quantile.

### A second defect in the same function

The docstring says *"Share of his own team's opportunity, per draw."* The code
computes `tot = fc.arrays.get('qb__db')` then `tot.sum(0)` — which sums **every
row in the array, spanning both teams**. Prescott's stored reason string reads
*"40% of the game's quarterback dropbacks"*: 22.02 / (40.65 + 32.80) = 0.2999
of the game, against 22.02 / 40.65 = 0.5416 of his team. The board carries the
game-wide figure and calls it role.

### Why Dak can score lower than a committee back

1. The two scales differ and neither is uncertainty: QB divides by 0.8, skill
   by 0.25.
2. Both denominators are game-wide, which structurally halves every
   quarterback — a QB taking 100% of his team's dropbacks reaches only ~0.5 of
   the game's, capping his `role_certainty` near 0.625.
3. So a back holding 25% of the **game's** carries scores 1.0000, while
   Prescott holding 54% of his **team's** dropbacks scores 0.4976 — even
   though P(Prescott = 0 dropbacks) is 0.4273 and the back's role is
   comparatively settled.

A player whose share is bimodal 0-or-everything and one whose share is a
stable 12% are indistinguishable to this dimension.

**No score was changed.**

---

## Governance audit

### How a stage carrying a governance token is still PASS

The tokens live in **free-text `spec_version` strings** and **`warnings`
lists**. No code reads either as a condition.

```
participation      PASS  'Stage2 ewma_hl2; governance INFORMATION_CONSTRAINED'
targets_carries    PASS  'P4C system C; governance DATA_BLOCKED'
conversion         PASS  'RC1 baseline; SIGNAL_WEAK; governance
                          HOLD_CHARACTERIZED + CALIBRATION_DEFECT'
td_layer           PASS  'TD2 pooled positional control; governance HOLD_TENTATIVE'
team_environment   PASS  warnings ['known limitation:
                          team_volume_is_near_unforecastable']
```

`state = PASS` means **the stage executed and returned a value**. It is not a
statement about the soundness of the model inside it.

### The five levels that genuinely exist

| level | carriers | effect |
|---|---|---|
| **1 informational annotation** | `spec_version` substrings, `warnings` lists | none — documentation |
| **2 degradation warning** | `unavailable_metrics`, `absent_layers`, `completeness = PARTIAL_PLAYER_COVERAGE`, DIAGNOSTIC-class verdicts | recorded every run, never smoothed away, explicitly **not** a gate (`artifact.py:89`) |
| **3 ranking gate** | `unavailable_metrics` removing a metric outright; model-health metric eligibility | the number is not shown or not rankable |
| **4 publication gate** | `promoted`, `prospective_eligible`, `NFL1_NOT_AUTHORIZED`, the three admissibility controls | the artifact may not COUNT as evidence |
| **5 hard refusal** | HARD-class invariants in FAIL/BLOCKED (`HARD_REFUSING_STATES`); a stage returning BLOCKED/FAIL | nothing seals |

### Warnings currently treated as documentation that should affect a gate

1. **`CALIBRATION_DEFECT` on the conversion layer** — level 1 today, a
   substring. Receiving yards are published to one decimal and ranked against
   each other while the layer producing them is declared to have a calibration
   defect. **Should be level 3 (ranking gate).** Either the defect is real and
   those numbers should not be ranked at face value, or the token should go.
2. **`QB3_WEEK1_SEASON_BOUNDARY` / `week1_specification_defect = true`** —
   level 2 today, a boolean. The board publishes `qb/pyds`, `qb/att` and
   `qb/cmp` for a room this audit has now shown is a starter-selection mixture
   with P(QB1 = 0 dropbacks) = 0.4273. The 4:25 repair made the equivalent
   blocker fail closed for **market quotes**; the **board** was never gated.
   **Should be level 3 at minimum, arguably level 4 for QB metrics.**
3. **`qb_inactive_ownership.enforced = false`** — level 2, a field. A board
   whose inactive-QB ownership is unenforced still publishes QB numbers at full
   precision. **Should be level 3 or 4 for QB metrics.**
4. **`NONQB_LAYERS_UNAVAILABLE`, DIAGNOSTIC class, state FAIL** — the class
   table defines DIAGNOSTIC as *"a provider/model DISAGREEMENT or a
   characterised limitation"*. A stage that did not run is neither. It is
   already carried by `absent_layers` and `completeness`. **Reclassify rather
   than re-gate.**

---

## What this audit does not establish

- It does not establish that any proposed repair improves a forecast. Nothing
  was implemented and nothing was evaluated.
- It does not establish that Slayton or Campbell should be excluded. It
  establishes that governed pregame data cannot say whether they should be.
- The appearance probabilities were **recomputed** through the production path
  at the sealed evidence clock. They reproduce the sealed zero mass to within
  0.006, but they are a recomputation: **the appearance latent is not persisted
  in the artifact**, which is itself a gap — a reader cannot audit it from the
  sealed bytes.
- Nine graded games and one audited game are not a sample. Every rate quoted
  from the 2026 slate is descriptive.

---

## The smallest architecture change that would fix each CONFIRMED defect

**Not implemented. For owner review only.**

| # | defect | smallest change |
|---|---|---|
| 1 | week-1 incumbent crosses the season boundary | Make `previous_primary()` return a THIRD state — `NO_COMPARABLE_PRIOR_GAME` — at a season boundary, instead of reaching back to week 18. A three-valued incumbent signal needs a third cell, not a new model. |
| 2 | bimodal pool conflates selection with share | Split the estimand in two, which is exactly the frozen QB3-AB preregistration (`07b36d0e`): fit `P(starts)` on the full cell, and fit the share pool **conditional on having taken the first snap**. No new parameter; the same rows partitioned once. |
| 3 | no shared latent across players | Introduce ONE team-game availability draw that the per-player Bernoulli conditions on, so a club's skill players share a game. This is a draw-index change, not a new model — the layers already share one draw index. |
| 4 | appearance ordering inverted | Two field-level corrections in `appearance_r8`: give `n_prior == 0` an explicit cold-start prior rather than letting it land at the top of the range, and carry `cm_carried` with the same sign as `cm_within`. Both are already computed and sitting on the row. |
| 5 | no pregame eligibility signal | Acquire a feed that carries active-53 / practice-squad / reserve **before** kickoff, and add one eligibility layer upstream of R5. This needs bytes from outside the checkout; it is an evidence request, not a code change. |
| 6 | QB pool exempt from R5 | Delete the exemption — one line — once (5) exists. Deleting it before (5) exists would filter QBs on membership only, which Milton already satisfied, so it buys nothing on its own. |
| 7 | `role_certainty` has no uncertainty term | Add a dispersion term to the dimension (the machinery exists — `dispersion()` and `_score_width` are already in the same file), or rename the dimension to `role_magnitude` and stop calling it certainty. The rename is smaller and honest. |
| 8 | game-wide denominator | One-line fix: restrict `tot` to the player's own team's rows, matching the docstring. |
| 9 | governance tokens gate nothing | Promote the tokens from free text to a declared enum with a level, in one table, the way `INVARIANT_CLASSES` already works. Nothing needs re-deciding; the levels above just need somewhere to live. |
| 12 | stale determinism proof | Make the test RE-RUN the proof rather than read its artifact, then fix whatever the re-run exposes (the two seals differ on payload hash and fingerprint, consistent with a wall clock inside the payload). |
