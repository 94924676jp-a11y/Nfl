# Stage 6 — the opportunity centre now consumes the current season

Candidate identity: `V1_CANDIDATE_R9_W1P_GSVUCYS` (CS6). The baseline
`V1_CANDIDATE_R9_W1P_GSVUCY` is untouched and stays reproducible as the other
half of the comparison. No model value was hand-edited, no scaling factor
applied, no external projection or price used. Q9 not promoted.

---

## 1. Stage 6, old call graph

```
run_forecast
  └─ role_prior.build(panel, share, positions, cut)      panel = load_panel()
  └─ role_prior.assign_tiers(players, prior, depth_rank) tier from 2025 snaps
  └─ football_engine.slate_fits
       └─ p4c_params.class_point_forecast(cls, season, week, players,
                                          role_prior, tiers)
            hist = [r for r in load_panel() if r.ord < cut and r.appeared]
            v    = role_prior.weight(pid, pos, ewma(hist, hl=3.0),
                                     len(hist), tier, prior)
            C[pid] = v * participation_prior
```

`load_panel()` spans ordinals **202001 → 202518** and carries **zero 2026
rows**. Every input above is 2025-or-older. `role_state` existed, measured the
current season correctly, and was connected to none of it.

## 2. Stage 6, new call graph

```
run_forecast
  ├─ current_season_evidence.collect(season, week, as_of)
  │     usage_vintage.usage_season(..., before_week=week)   widest lawful pbp
  │     role_state.load_snaps(season, week)                 PFR, weeks < week
  │     assert_pit(...)                                     re-derives the cut
  ├─ current_season_evidence.assert_fresh(...)  ── REFUSES BEFORE SIMULATION
  ├─ player_universe.build + role_state.assign  ── the GOVERNED role
  ├─ depth_role.guard_rank_map(...)             ── same-room ranks only
  └─ football_engine.slate_fits(..., current_season=, role_by_id=, depth_rank=)
       └─ p4c_params.class_point_forecast_cs(...)
            └─ opportunity_centre.build_centres(...)
                 └─ opportunity_centre.centre(...)  per player
                      weights  = recency × season × team × opportunity
                      n_eff    = (Σw)² / Σw²
                      retention= Σw / Σw_undiscounted
                      centre   = w·mean(evidence) + (1-w)·target
                      w        = n_eff·retention / (n_eff·retention + k)
            C[pid] = centre × participation_prior
```

`class_point_forecast` (historical-only) is **still there, unchanged**. The new
path is selected by the caller supplying `current_season`; there is no implicit
switch, so the baseline reproduces byte-for-byte.

## 3. Current-season source and PIT contract

**Source: `usage_vintage.usage_season`, not `current_season_nonqb_panel`.**
They implement the same counting rules — the former imports them from the
latter by reference — but read different stores. Measured at cut
2026-09-21T23:05Z:

| | games | clubs |
|---|---|---|
| `current_season_nonqb_panel` (globs `nfl/research/postgame/`) | 10 | 20 |
| `usage_vintage` (also reads the governed vintage store) | **16** | **32** |

**`2026_01_DAL_NYG` is one of the six the narrower source cannot see.** On it,
Cam Skattebo's 18 carries do not exist, and the repair would have failed
silently on the very player it was built for. Absence from a corpus is not zero
usage.

Snaps come from the PFR file (`offense_pct`, `offense_snaps`, `st_pct`), kept
as a **separate axis** — how much of the offence he was on the field for is a
different question from how much of it came to him.

**The PIT contract.** For a forecast at week N only weeks **strictly less than
N** may contribute. Enforced twice: `before_week=N` in the selector, then
`assert_pit()` re-derives the maximum week present and refuses
`CURRENT_SEASON_EVIDENCE_LEAKS_FORWARD` if anything at or after N survived. The
assertion deliberately does not trust the filter — a silent filter that works
today and stops working tomorrow is the defect class this project pays for
most.

## 4. Weighting and the evidence hierarchy

Seven tiers are reported per player: `CURRENT_SEASON_MEASURED`,
`RECENT_MEASURED`, `CURRENT_GAME_ROLE`, `PRIOR_SEASON_MEASURED`,
`CAREER_HISTORY`, `DEPTH_DERIVED_PRIOR`, `COLD_START_PRIOR`.

**There is no "latest game wins" rule and no branch that privileges 2026.** A
current-season observation is simply the most recent one, so its recency weight
is `lam⁰ = 1` and its season decay `sd⁰ = 1`. It dominates a stale prior
because it is not stale, arithmetically, under the same formula that governs
every other row. A test asserts that a 2026 row and a historical row with the
same season and week produce an **identical centre** — the source label changes
the reported grade, never the arithmetic.

One game does not erase thirty-two: it outweighs each individually and is
outweighed by their sum until the decay has worked. That is what the formula
gives for free and what a threshold rule would have had to fake.

### The parameters were estimated, not chosen

Preregistered in `nfl/research/cs2/PREREGISTRATION_STAGE2.md` before any result
was seen. Forward-chained on 2022–2025, RB/WR/TE, appeared rows only, every
input from `ord < t`. Primary loss **MAE** (chosen in advance because the share
distribution is right-skewed and zero-inflated, so squared error would let a
handful of lead-back rows choose the parameter for everyone). Uncertainty by
**bootstrap blocked by player**, 400 resamples. Selection: lowest MAE, then the
**simplest** grid point whose interval overlaps it.

This closes `stage2_state()`, which had refused with
`PREREGISTRATION_INCOMPLETE` naming exactly three missing quantities:

| Named missing | Resolution |
|---|---|
| `half_life` | **estimated** on the grid {1,2,3,4,6,8,12,∞} |
| `shrinkage_target` | **estimated** over {positional mean, club-room mean} |
| `min_opportunity` | **declared NOT REQUIRED**, with a measurement behind it — see below |

`min_opportunity` was deliberately kept off the grid as a hard cut. A threshold
invents a cliff (2 carries counts fully, 1 counts not at all) that nothing in
the football justifies. The continuous form — an opportunity **exponent** on
the weight — was estimated instead. If it comes back 0.0, the answer is that
opportunity count does not belong in the weight, and the threshold is not
needed rather than being set to something convenient.

### Retention: a rule that is declared, not fitted, and says so

The obvious design was wrong and the tests now pin why. The season and
team-change discounts are **multiplicative**, and both the weighted mean and
`n_eff = (Σw)²/Σw²` are **scale-invariant**. So for a player whose every
observation is at another club — exactly the player the team-change rule exists
for — halving every weight cancels and changes the centre by nothing at all.
Najee Harris has 71 rows, all at PIT and LAC, none at NYG; the discount left
him identical.

`retention = Σw / Σw_undiscounted` is the fraction of evidence weight that
**survives** the staleness and context discounts: 1.0 for a player whose
history is current and at this club, falling toward the discount itself for one
whose history is entirely old or entirely elsewhere. Scaling `n_eff` by it
makes such a player shrink harder toward the prior.

**It is a governance rule, not an estimate.** The forward-chained fit selected
the WEIGHTS by predictive accuracy on the weighted mean; it did not evaluate
this. The claim is "evidence from another context is worth less, so lean harder
on the prior", stated with its reasoning rather than measured. Where this
document says a number was estimated it was; this one was not.

## 5. `role_state` integration — the governor reaches the generator

The split is closed. When the governed role is `ROLE_UNSUPPORTED` or
`ROLE_UNCERTAIN`, **the depth anchor is withheld**: the centre cannot be built
from the listing, the shrinkage target falls back to the positional mean (which
carries no claim about this player's place in a depth chart), and the row is
marked `GOVERNED_ROLE_REFUSED_NO_DEPTH_ANCHOR` so the audit and the gate both
see it.

`run_forecast` builds the governed role itself and **refuses**
`GOVERNED_ROLE_UNAVAILABLE` if it cannot — CS6 may not silently degrade to the
depth-only generator, because that is the defect it exists to close.

| Governed state | Centre from | Basis |
|---|---|---|
| supported + current-season evidence | weighted evidence | `EVIDENCE_SUPPORTED` |
| supported, no current, has history | season-decayed history, shrunk to depth tier | `HISTORICAL_SUPPORTED` |
| supported, declared starter, thin history | history, and the declaration is **not** counted as measurement | `DECLARED_STARTER_THIN_HISTORY` |
| supported, nothing measured | depth-tier anchor | `DEPTH_PRIOR` |
| **refused or uncertain** | **no depth anchor**; positional mean or floor | `GOVERNED_ROLE_REFUSED_NO_DEPTH_ANCHOR` |
| nothing anywhere, no anchor | measured cold-start floor | `COLD_START_FLOOR` |

## 6. Cold starts and rookies

The floor is **measured, not chosen**: the class share a player actually took
in his **first appeared game**, over every such player in the panel
(`nfl/research/cs2/COLD_START_FLOOR.json`, regenerated by
`derive_cold_start_floor.py`). **Median, not mean** — same reason the
preregistration scores on MAE: RB first-game carry share has mean 0.165 against
median 0.095, and the mean is pulled up by the few who debut in a lead role.

| Case | Behaviour |
|---|---|
| rookie, one measured 2026 game | `EVIDENCE_SUPPORTED` on that game; it moves him off the positional mean |
| rookie, several games | same path; `n_eff` rises, shrinkage falls, centre moves further toward what he has done |
| veteran on a new team | history retained, discounted by context; retention lowers his effective n |
| veteran, zero current-season snaps | `HISTORICAL_SUPPORTED`, graded `PRIOR_SEASON_MEASURED` |
| practice-squad elevation / recently activated | no measured rows → depth anchor if the role is supported, else the floor |
| declared starter, no measured history | `DECLARED_STARTER_THIN_HISTORY`; the declaration is named and explicitly not treated as measurement |

Connecting the current season did **not** create a rookie failure mode: a
rookie with one 2026 game is evidence-supported, where before he had no history
at all and fell to a positional or depth prior.

## 7. Team changes — the actual rule

1. **Workload/role history is discounted**, by the estimated
   `team_change_discount`, applied per observation recorded at another club.
2. **Effective evidence is reduced** by `retention`, so a full team-changer
   shrinks harder toward the prior. This is what makes (1) bite at all.
3. **Efficiency history is not touched here.** Yards per carry and catch rate
   are different quantities living in different layers; this module governs
   opportunity share only, and says so on the row.
4. The panel already carries mid-season moves as **two rows** for the same
   (player, ordinal) — old club `appeared=0`, new club `appeared=1`. 2,001 such
   pairs exist and every one differs in team. Stage 6 filters on `appeared`, so
   the stale zero never enters.

## 8. Freshness gate placement

`current_season_input_freshness` already refused the old run — at **artifact
sealing**, after 318 seconds of worlds nobody could use. The same protection
now runs **before simulation**, in `run_forecast`, immediately after the
evidence is collected:

- A run that claims current-season opportunity and cannot see week N−1 stops
  with `CURRENT_SEASON_INPUT_STALE`.
- Week 1 is `CURRENT_SEASON_EVIDENCE_ABSENT_NO_PRIOR_WEEK` and **passes** —
  nothing is stale about evidence that cannot exist yet.
- A run that does not claim current-season opportunity reports
  `NOT_APPLICABLE`, not a pass.

## 9. Refusal propagation

`gated_projection.run_status()` reads the run's own `run_status.json` and
refuses `UPSTREAM_RUN_REFUSED` on `REFUSED` / `BLOCKED` / `FAILED`, naming the
stage and code that refused. A **missing** status is `RUN_STATUS_ABSENT`, not
presumed fine: an artifact with no record of how its run ended is
indistinguishable from one whose run refused.

This is checked **before** the review gate, and that order is deliberate — a
refused run is not a forecast, so whether its review passed is moot.

Measurement and debugging paths pass `inspect_refused_non_publishable=True`.
The arrays come back, `publishable` is `False` and `verdict` is `None`, so a
blocked slate can still be diagnosed and nothing can mistake the result for a
forecast.

## 10. What was deliberately not done

- **No global scaling.** No 1.39 multiplier, no regression intercept. The
  underprojection diagnostic must be **re-measured** after this structural fix,
  not compensated for before it.
- **No individual projection edited.** Skattebo and Tracy were not touched.
- **No tuning to Fantasy Cruncher, to a sportsbook, or to the completed game.**
  The NYG@LAR result is not read anywhere in this work.

---

## 11. Before and after — a diagnostic, not a verdict

Same evidence cut, same fixture, same seed, same arm. One declared change:
`V1_CANDIDATE_R9_W1P_GSVUCY` → `...GSVUCYS`.

| | before | after |
|---|---|---|
| run id | `d90d80c0b4a7f95e` | **`5dd61c7b2f318d3e`** |
| npz digest | `d73aa88a9a026ad3…` | `a243521cea17321e…` |
| status | REFUSED at sealing | REFUSED at sealing, **same declared `denom_panel` block** |

Both artifacts were opened through the gated loader's explicitly
**non-publishable** inspection path, because both runs refused.

| metric | total before | total after | Δ | mean abs Δ |
|---|---|---|---|---|
| team_carries | 58.145 | 58.145 | **0.000** | 0.0000 |
| team_targets | 58.146 | 58.146 | **0.000** | 0.0000 |
| player carries | 47.691 | 47.675 | −0.015 | 0.7700 |
| player targets | 57.477 | 57.495 | +0.018 | 0.3259 |
| DK points | 159.510 | 159.512 | **+0.003** | 0.5148 |

**This is a redistribution, not a rescaling.** Team volume is untouched and DK
total moves by 0.003 across the whole slate. That is what the repair was
supposed to do: it governs who gets the opportunity, not how much there is.

### Backfield carry order

```
NYG before:  Tracy 8.094 | Skattebo 6.144 | Harris 5.249 | Singletary 4.376 | Ricard 0.869
NYG after :  Skattebo 7.214 | Tracy 6.628 | Harris 4.806 | Singletary 3.693 | Ricard 2.382
LA  before:  Kyren 12.202 | Corum 7.508 | Rivers 3.248
LA  after :  Kyren 11.706 | Corum 7.922 | Rivers 3.323
```

### Player review

| | before | after |
|---|---|---|
| verdict | BLOCKED | BLOCKED |
| blocking conflicts | 17 | **14** |
| blocked players | 10 | **9** |
| role_opportunity_inversion | 8 | 7 |
| unsupported_published_role | 5 | 4 |
| cold_start_dominance | 4 | 3 |
| cleared | — | Max Klare, Theo Johnson |
| newly flagged | — | Davis Allen |

### Three results that are worse or unresolved, stated plainly

1. **Tracy still out-carries Singletary** (6.628 vs 3.693) and still blocks.
   The Skattebo inversion — the named fixture case — is corrected. This one is
   not, and the reason is legible: Tracy's 2025 share (ewma ≈ 0.52 over his
   last rows) is genuinely higher than Singletary's (≈ 0.27), and one week-1
   game does not overturn a season for both men at once. **The audit calls it
   "not supported by any axis the review can read", and that sentence is now
   wrong**: the prior-season share IS the supporting axis, and the audit
   cannot read it. Teaching the audit to read the Stage-6 attribution is the
   next repair, and it is item 5's whole point.
2. **Patrick Ricard rises from 0.869 to 2.382 carries** — a blocking fullback
   whose role the governor refuses. Withholding his depth anchor moved his
   shrinkage target to the positional RB mean, which is *higher* than a
   blocking back deserves. The governed refusal made him more prominent, not
   less. That is a defect in the refusal fallback and it is not fixed here.
3. **Davis Allen is newly flagged.** A conflict the repair created, not one it
   cleared, and it is counted as such above.

### What this comparison may not be used for

The NYG@LAR result is not read anywhere in this work and is not admissible at
this stage. The new run is **not** better because it resembles the completed
game. What the table supports is narrower and sufficient: the quantities that
moved are the ones the new evidence bears on, team volume did not move at all,
and no global level change occurred.
