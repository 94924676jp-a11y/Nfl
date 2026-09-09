# Target-volume ownership audit

**Mission:** trace every producer and consumer of the throw-state quantities,
establish the exact historical accounting, and find where the simulator assigns
duplicate causal ownership. Measurement and architecture only — no new
estimator, and `team_targets` was not touched.

**Three findings, in order of size.**

1. **`team_targets` is not an independent quantity. It is targeted throws** —
   identical in **3,230 of 3,230** team-games, and itself a deterministic
   function of the QB terminal-state chain, exact in **3,229 of 3,230**.
   It is redundant under C3 and no production component needs it there.
2. **I was wrong about the −9.2%, and about the level gap generally.** Every one
   of these quantities is in monotonic decline; XL1 compared a 2026 forecast
   against a **six-season mean**. Against **2025** the target error is **−4.4%**,
   not −9.2%, and passing yards are **−2.8%**, not −8.0%.
3. **The QB terminal-state mix is not defective — and chasing it found a real
   leak instead.** Chronology-clean, the mix reproduces the prior-only rate of
   the exact quarterbacks on the slate. The `0.833` figure was
   `0.877 × 0.947`, and the `0.947` is **5.32% of every team's dropbacks
   allocated to quarterbacks nobody forecasts, leaving the system with no
   refusal**. 23 of 32 teams. Miami loses 33.1%, the Jets 30.4%. That defect is
   mine, from R4.

Governance unchanged: `PATH_C_STATE.json` untouched, G0A **11/12**, NFL-1 **NOT
AUTHORIZED**, `SHARED_PASS_DEFAULT` off, C3 not promoted, no 2026 outcomes.
Suite **42 modules, 446 test functions, 2,586 checks, 0 failing**.

---

## 1. The exact historical accounting

REG 2020–2025, **3,230 team-games**, measured from play-by-play.

```
dropbacks (37.6111)
    = throws (33.5492) + sacks (2.3799) + scrambles (1.9359) − excluded (0.2536)

throws (33.5492) = targeted (32.1294) + untargeted (1.4198)

targeted = dropbacks − sacks − scrambles + excluded − untargeted
    EXACT in 3,229 / 3,230 team-games, worst residual 1
```

**The `excluded` term is fully identified, with nothing left over.** 819 plays
across six seasons that are a throw, sack or scramble but carry
`qb_dropback == 0`: **429 spikes**, **389 nullified plays** (`no_play`) and **1** offsetting
field-goal play. That is precisely the spike / penalty /
nullified-play treatment the accounting taxonomy demands, and it is now named
rather than absorbed.

### D1's three metrics are the play-by-play quantities. Not proxies.

| D1 metric | play-by-play quantity | exact match |
|---|---|---|
| `team_targets` | targeted throws | **3,230 / 3,230** |
| `team_dropbacks_part` | `qb_dropback` count | **3,230 / 3,230** |
| `team_carries` | `rush_attempt` count | **3,230 / 3,230** |

Not "closely related". Byte-identical in every team-game. `mk_denom.py:75`
builds `team_targets` as `+= r['targets']`, a **sum of the same player-level
quantity the receiving layer allocates**.

---

## 2. The dependency graph

**Producers**

| quantity | producer | how |
|---|---|---|
| `team_dropbacks_part` | D1 `team_volume_v1`, ewma | participation dropback count |
| `team_targets` | **D1, independently, ewma** | sum of panel player targets |
| `team_carries` | D1, ewma | rush attempts |
| QB dropbacks | QB V1 × QB3 share × D1 `team_dropbacks_part` | composition |
| attempts / sacks / scrambles | QB V1 chained multinomial on dropbacks | closes exactly |
| targeted / untargeted throws | **C3 only**, from QB attempts | untargeted rate 0.042320 |
| player targets | allocation simplex × a budget | B0 uses D1; C3 uses throws |

**Consumers of `team_targets`**

| consumer | kind | needs it under C3? |
|---|---|---|
| `football_engine.py:181` `tgt_vol` | production, `T = S × tgt_vol` | **no** — C3 replaces this |
| `accounting.reconcile_nonqb` closure | production guard | **no** — closes against the dealt budget |
| `p4b_lib`, `p4c_lib`, `p4c/accounting.py`, `p4b_panel.py` | **fitting denominator** | **no** — see below |
| `audit_real.py` `team_targets_eq_sum_player_targets` | realised-data invariant | unaffected |
| `p1s`, `r1`, `p4b` adversarial | research diagnostics | unaffected |

**The fitting question is the one that could have killed C3, and it does not.**
The target shares were fitted as `s_targets = y_targets / team_targets`. C3
applies them to targeted throws. If those were different denominators the
fitted shares would be invalid. They are the **same quantity, exactly**, so the
shares remain valid without refitting. That is a real coherence result for C3
and it was not obvious in advance.

The fitting frame needs the **realised** historical `team_targets` as a
denominator. That is untouched by anything here — it is data, not a forecast.

---

## 3. The owner's five questions

### Q1 — legitimate upstream latent quantity, or redundant?

**Redundant.** It is not latent and it is not upstream. It is targeted throws,
identical in 3,230/3,230, and a deterministic function of dropbacks, sacks,
scrambles, the excluded pool and the untargeted pool — all of which the QB layer
already owns. Forecasting it independently is a **second causal owner for one
quantity**: the same defect class XL1 just removed one level down.

### Q2 — under C3, which components still require it?

**None in production.** The `tgt_vol` consumption at `football_engine.py:181` is
exactly what C3 replaces. The accounting closure is against whatever budget was
dealt. The fitted shares survive because the denominator is the same quantity.
Only the historical fitting frame uses it, as realised data.

### Q3 — would demoting it improve coherence without losing signal?

**Coherence: yes, unambiguously.** It removes a duplicate owner and makes the
throw process the single source of the target budget.

**Signal: not established, and it needs a pre-registration.** D1's ewma on the
target series could in principle forecast better than composing dropbacks
through the throw rates. What can be said now is structural: on the 2026 week-1
slate D1 forecasts dropbacks to **+0.7% of 2025** and targets to **−4.4%**, so
its implied targeted share of dropbacks is **0.799** against 2025's **0.842**.
Its own two metrics disagree with each other about the throw process by about
five points. A quantity drawn independently of its siblings and inconsistent
with them is carrying independent **error**; whether it also carries independent
signal is the empirical question, and I am not answering it by inspection.

**Recommended migration path — and it is deliberately not a deletion:**

1. Keep D1 emitting `team_targets`. Deleting it would break the fitting frame's
   denominator and every historical diagnostic for no gain.
2. Under C3, stop **consuming** the drawn `team_targets` as the receiving
   budget. That is already true — C3 does not read it.
3. Add a **coherence guard**, not a repair: refuse when D1's drawn
   `team_targets` and the throw-derived targeted budget disagree by more than a
   declared margin. The disagreement is the signal; hiding it is not.
4. Demote it in `PATH_C_STATE` from a forecast metric to a derived one **only on
   an owner ruling**, and only after the pre-registered comparison in §5.

### Q4 — is the −9.2% an estimator defect, or inconsistency with the throw process?

**Mostly neither: it was my measurement error, and I am correcting it.**

Every quantity here is in monotonic decline:

| season | targets | completions | passing yards | passing TD | throws/dropbacks |
|---|---|---|---|---|---|
| 2020 | 33.81 | 22.96 | 254.88 | 1.701 | 0.9040 |
| 2021 | 33.19 | 22.28 | 244.12 | 1.544 | 0.8997 |
| 2022 | 31.93 | 21.41 | 234.38 | 1.384 | 0.8941 |
| 2023 | 32.14 | 21.71 | 236.34 | 1.386 | 0.8851 |
| 2024 | 31.27 | 21.38 | 233.50 | 1.487 | 0.8854 |
| **2025** | **30.53** | **20.62** | **225.02** | **1.491** | **0.8837** |
| 6-season mean | 32.13 | 21.71 | 237.88 | 1.497 | 0.8920 |

XL1 compared a 2026 forecast against the **six-season mean**. Corrected against
2025:

| metric | XL1 said | against 2025 |
|---|---|---|
| D1 `team_targets` | −9.2% | **−4.4%** |
| B0 team passing yards | −8.0% | **−2.8%** |
| B0 team completions | −9.0% | **−4.2%** |
| B0 team passing TD | −9.0% | **−8.6%** |
| C3 team passing yards | −10.0% | **−4.9%** |
| C3 team completions | −10.0% | **−5.2%** |

**Roughly half of the "8–10% level gap" XL1 reported was a stale baseline.**
`history_levels.json` now carries per-season levels and states that a level
comparison must use `by_season[most_recent_season]`; only the identities, which
do not trend, may use the pooled mean.

What survives after the correction: **passing TD at −8.6%**, which is the one
metric that is *not* in monotonic decline (it fell to 1.384 and recovered to
1.491). That is the genuine remaining level gap and it is now the only one.

The residual −4.4% on targets is the inconsistency the question names: dropbacks
right, targets low, throw share implied at 0.799 against 0.842.

### Q5 — is the larger problem the QB terminal-state mix?

**No. Diagnosed chronology-cleanly, the mix is right.**

Strictly prior history of the **84 quarterbacks actually on the 2026 week-1
slate**, n = **97,761 dropbacks**, no 2026 information:

| | sack + scramble share of dropbacks |
|---|---|
| pooled prior history of these 84 passers | **0.1153** |
| dropback-share-weighted (toward likely starters) | **0.1253** |
| **simulator, pre-allocation** | **0.1215** |
| league 2025 | 0.1163 |
| league 2020–2025 | 0.1147 |

The simulator reproduces the share-weighted prior rate of these exact
quarterbacks to within **0.004**. The population weighting explains the move
from 0.115 to 0.125, and the model lands on 0.122. **The terminal-state mix is
not a defect and the owner's warning was the right one** — the headline
comparison would have had me repairing a model that is behaving correctly.

---

## 4. What chasing Q5 actually found: OWN-1, and it is mine

`0.8318 = 0.8785 x 0.9468`, against the 0.833 XL1 reported. The first factor
is the correct throw share. The second is a leak.

`football_engine.run_game` composes QB dropbacks as
`team_dropbacks_part × QB3 share`. It handles a forecast row the allocation does
not name — that row is zeroed. **It had no counterpart for the reverse.** QB V1
refuses a passer with no prior appearance, which is correct and is reported by
name in `slate_prospective`'s `no_history` evidence. Nothing then checked that
the allocation's share mass had all reached somebody.

Measured on the real 2026 week-1 slate, 32 teams, 400 draws:

| | |
|---|---|
| quarterbacks in the depth-chart allocation, absent from QB V1's rows | **35** |
| teams leaking share | **23 of 32** |
| share units reaching nobody | **1.7014 of 32.0000** |
| **fraction of every team's dropbacks lost** | **5.3168%** |
| worst | **MIA 33.1%**, **NYJ 30.4%**, **WAS 19.6%**, ATL 10.0%, TB 9.4% |

An absence read as success — the project's own worst defect class — in code I
wrote in R4, at the one place that had both sides of the join.

**And it very nearly accounts for the whole remaining level gap.** C3's
completions are −5.2% against 2025; the leak is −5.32%. Removing it would put
C3's targeted throws at roughly **30.8 against 2025's 30.53** and its
completions at about **20.65 against 20.62**.

### What was done about it, and what deliberately was not

`qb_accounting.reconcile_allocation_share` now refuses
`QB_ALLOCATION_SHARE_UNCONSUMED`, naming every leaking team and every
unforecastable passer, and it is wired into `run_game` at the one place holding
both sides. Nine checks, including the bypass proof.

**It does not renormalise the survivors.** Rescaling the incumbents to absorb a
backup's share would be generating a fallback allocation — forbidden — and it
would erase the one number that reveals the gap. Deciding what a team does with
an unforecastable quarterback's share is a **modelling question**, and three
answers are defensible:

- **refuse the team** — honest, halts 23 of 32;
- **a cold-start passer prior** — new estimator, needs its own pre-registration;
- **route the share to the positional pool** — plausible, and still a model.

That is an owner decision. The guard makes it visible and costs nothing.

---

## 5. Pre-registration required before any repair

Two comparisons are now identified. Neither may be run before its
pre-registration is committed.

**XL2 — derived versus independently forecast target budget.** Does composing
the target budget through the throw process forecast better than D1's ewma on
the target series? Strictly chronological, 2020–2025, identical issuance
populations, CRPS on the team target count, clustered by game and by team.
Development data, so it can **reject** the derived budget and can never promote
it. This is the study that settles Q3's signal half.

**C3 retrospective falsification** — authorized by the owner and still
unstarted. Strictly chronological B0 versus C3 on 2020–2025: player target-count
CRPS, receiving-yard CRPS, receiving-TD calibration, teammate-vector energy
score, interval coverage, pairwise dependence, exact accounting, clustered
uncertainty, identical issuance populations. It may not promote C3.

**Both should run after OWN-1 is resolved**, because a 5.3% leak in the throw
budget would contaminate every C3 arm and would be scored as a C3 property.

---

## 6. Queue

1. **OWN-1** — the 5.32% allocation leak. Owner decision on the three options in
   §4. Largest measured actionable defect, and it blocks the two studies.
2. **Passing TD at −8.6% against 2025** — the one level gap that survives the
   baseline correction and the one metric not in decline.
3. **XL2** — derived versus forecast target budget (pre-registration first).
4. **C3 retrospective falsification** (authorized; run after OWN-1).
5. Opposing-team / game-level dependence — simulator +0.001 against −0.535.
6. Role-aware availability reallocation.
7. P5A rectification. 8. QB3b week-1 incumbency. 9. Lateral realised-outcome
   exception.

---

## 7. Files

| File | Role |
|---|---|
| `nfl/research/xl1/build_history_levels.py`, `history_levels.json` | now carries per-season levels and refuses a pooled-mean level comparison |
| `nfl/research/own1/audit_ownership.py`, `own1_results.json` | §1–§4, every number here |
| `nfl/production/qb_accounting.py` | `reconcile_allocation_share`, the OWN-1 guard |
| `nfl/production/nonqb/football_engine.py` | the guard wired in, and its evidence on every game |
| `nfl/tests/test_xl1_shared_pass.py` | +9 checks for the guard, with the bypass proof |
