# BUF opportunity-allocation diagnostic (P2)

**Verdict: MIXED — a ROLE_ALLOCATION_DEFECT and a DATA_STATE_DEFECT, with
distinct mechanisms and distinct fixes.**

Model-internal only. No sportsbook line, no fantasy projection and no market
quantity is used as a target anywhere below. The market comparison supplied
the *question*; every number here comes from the sealed draws
(`c3probe_V1_CANDIDATE_R9_W1P_GSVUC/d709e67b82d5b01c`, 8,000 draws) and from
2026 week-1 play-by-play. **No forecast was altered.**

## The one finding that contradicts the obvious story

The obvious explanation is "BUF has worse role data than DET". **It does not.**

| Team | non-QB mean `role_certainty` | STARTERS (WR1/TE1/RB1) mean |
|---|---|---|
| BUF | **0.2726** | **0.4417** |
| DET | 0.2456 | **0.6335** |

BUF's room is *better* resolved on average. The asymmetry is entirely at the
**starter tier**, and it is driven by two specific rows: Gibbs at 1.0000 and
St. Brown at 0.5841, against DJ Moore (WR1) at 0.2922 and Dalton Kincaid (TE1)
at 0.2014. A one-line summary of "BUF data is bad" would be wrong and would
send the repair to the wrong place.

## 1. Per-player allocation, sealed model

BUF (`P(0 opp)` is P(targets + carries = 0)):

| Player | Depth | P(app) | P(0 opp) | mean tgt | mean rec | mean recv yds | mean car | mean rush yds | tgt share | carry share | role_certainty |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Khalil Shakir | WR2 | 0.864 | 0.136 | 5.55 | 4.15 | 48.6 | – | 1.5 | 0.181 | – | 0.3543 |
| DJ Moore | WR1 | 0.898 | 0.102 | 4.57 | 2.82 | 37.6 | – | 0.3 | 0.149 | – | **0.2922** |
| Keon Coleman | WR3 | 0.780 | 0.220 | 3.46 | 2.00 | 28.6 | – | 0.6 | 0.113 | – | 0.2212 |
| Dalton Kincaid | TE1 | 0.731 | 0.269 | 3.15 | 2.29 | 24.8 | – | 0.0 | 0.103 | – | **0.2014** |
| Josh Palmer | WR4 | 0.703 | 0.297 | 2.76 | 1.77 | 22.3 | – | 0.2 | 0.090 | – | 0.1766 |
| Dawson Knox | TE2 | 0.644 | 0.355 | 2.66 | 1.81 | 20.6 | – | 0.1 | 0.087 | – | 0.1698 |
| Skyler Bell | WR5 | 0.591 | 0.409 | 2.03 | 1.28 | 15.9 | – | – | 0.066 | – | 0.1295 |
| **James Cook** | **RB1** | **0.628** | **0.372** | 1.52 | 1.21 | 10.8 | 9.58 | 41.2 | 0.050 | **0.454** | 0.8315 |
| **Ray Davis** | **RB2** | **0.820** | **0.180** | 1.39 | 1.16 | 11.3 | 6.99 | 29.8 | 0.045 | **0.331** | 0.6065 |
| Jackson Hawes | TE3 | 0.489 | 0.511 | 1.35 | 1.10 | 12.4 | – | 0.0 | 0.044 | – | 0.0865 |
| Keleki Latu | TE4 | 0.457 | 0.543 | 1.21 | 1.05 | 9.9 | – | 0.0 | 0.040 | – | 0.0773 |
| Frank Gore Jr. | – | 0.603 | 0.397 | 0.89 | 0.70 | 5.1 | 4.53 | 19.5 | 0.029 | 0.215 | 0.3930 |
| Greg Dortch | – | 0.018 | 0.982 | 0.06 | 0.05 | 0.4 | – | 0.3 | 0.002 | – | 0.0039 |

DET, for contrast: St. Brown 0.986 / 0.286 share, Williams 0.937 / 0.166,
LaPorta 0.931 / 0.155, **Gibbs 0.953 P(app) and 0.895 carry share**, Vaki
0.584 / 0.105.

**Team conservation holds exactly.** BUF mean targets 30.60, mean carries
21.09; DET 32.02 and 24.98. Target-share sum **1.0000** and carry-share sum
**1.0000** on both teams. The allocation is internally conservative; the
question is only how it is distributed.

Red-zone and goal-line share, snap share and route share are **NOT
AVAILABLE** as per-player model inputs in this artifact: the sealed draws
carry `team_volume/team_rz_carries` at team level only, and no route or snap
array exists per player. Reporting a number for them would be inventing one.

## 2. Against week-1 football evidence

Week-1 games were played 2026-09-13/14, **before** the 2026-09-16 seal, so this
information existed at forecast time. (Caveat: the pbp vintage this repository
holds was captured 2026-09-17, after the seal. The *content* pre-dates the
seal; this particular *capture* does not prove availability at that instant.)

BUF, team week-1 totals 29 targets / 21 carries:

| Player | W1 tgt | W1 share | model share | Δ | W1 car | W1 share | model share | Δ |
|---|---|---|---|---|---|---|---|---|
| DJ Moore | 8 | 0.276 | 0.149 | **−0.126** | 0 | – | – | – |
| Khalil Shakir | 6 | 0.207 | 0.181 | −0.026 | 0 | – | – | – |
| Dalton Kincaid | 6 | 0.207 | 0.103 | **−0.104** | 0 | – | – | – |
| James Cook | 4 | 0.138 | 0.050 | −0.088 | 13 | 0.619 | 0.454 | **−0.165** |
| Keon Coleman | 2 | 0.069 | 0.113 | +0.044 | 0 | – | – | – |
| Dawson Knox | 1 | 0.034 | 0.087 | +0.052 | 0 | – | – | – |
| **Ray Davis** | 0 | 0.000 | 0.045 | +0.045 | **1** | **0.048** | **0.331** | **+0.284** |

DET: Gibbs carry share model 0.895 against week-1 0.879 (**+0.016**);
St. Brown −0.073, Williams −0.064, LaPorta −0.050. DET's allocation tracks
week-1 usage closely. **BUF's does not, and Ray Davis is the largest single
error in either team.**

Restricted to the RB room, week 1 was Cook 13 / Davis 1 / Gore 1 — shares
**0.867 / 0.067 / 0.067**. The model says **0.454 / 0.331 / 0.215**.

## 3. The eight tests

| # | Test | Verdict | Evidence |
|---|---|---|---|
| 1 | Starter shares over-shrunk toward room averages | **YES, at the starter tier only** | BUF starter `role_certainty` 0.4417 vs DET 0.6335 while BUF's room mean is *higher*. Moore (WR1) 0.2922 and Kincaid (TE1) 0.2014 are the two low rows, and they are two of the three underprojected starters |
| 2 | Backup appearance probability too high | **YES, and inverted** | Cook (RB1) P(carries = 0) = **0.375**; Ray Davis (RB2) = **0.292**. The RB1 is absent *more often* than his backup. DET: Gibbs 0.049, Vaki 0.577 — the correct ordering |
| 3 | Current-season refresh reached non-QB role allocation | **NO — it cannot** | CS1's spec is `current-season-qb-panel-1`, 30 clubs, 35 rows. It is a **quarterback** panel by construction. No non-QB role allocation reads it, so week-1 receiving and rushing usage never entered the non-QB path |
| 4 | Historical survivorship inflating backup roles | **PARTLY, and there is a named mechanism** | Ty Johnson (BUF RB) was **removed as Out**, and the artifact states his share is not reassigned by hand but dealt among the remaining players by the A1 multinomial. With Cook also carrying a 0.375 absence mass, that vacated share lands disproportionately on Davis and Gore |
| 5 | Route/target proxy flattening starter/backup differences | **YES** | BUF target shares 0.181 / 0.149 / 0.113 / 0.103 / 0.090 / 0.087 / 0.066 — near-flat. DET 0.286 / 0.166 / 0.155 / 0.136. No per-player route or snap array exists in the sealed draws to anchor the difference |
| 6 | Carry and target allocation independently plausible but jointly over-dispersed | **NO on conservation, YES on dispersion** | Both share sums are exactly 1.0000, so nothing is lost or invented. The defect is the shape of the split, not its total |
| 7 | Zero-inflation excessive for Cook receiving | **YES, and it is upstream of receiving** | P(recv yds = 0) = 0.5576 decomposes as **0.5231 from P(targets = 0)** (93.8% of the mass), 0.0293 from conversion (5.2%), 0.0053 from yardage (0.9%). Exact reconstruction to four decimals |
| 8 | BUF and DET on materially different role priors / fallback paths | **YES, at the starter tier** | See test 1. DET has an anchor at `role_certainty` 1.0000 (Gibbs); BUF's highest non-RB starter is 0.3543 |

## 4. James Cook, specifically

`P(receiving yards = 0) = 0.5576`, mean 10.85, median 0.0.

| Cause | Probability | Share of the zero mass |
|---|---|---|
| **Zero targets** (appearance / target count) | **0.5231** | **93.8%** |
| Zero receptions given targets > 0 (conversion) | 0.0293 | 5.2% |
| Zero yards given receptions > 0 (efficiency) | 0.0053 | 0.9% |

Reconstruction: 0.5231 + 0.4769 × 0.0613 + … = **0.5576**, matching the
observed value exactly. **It is not a reception-conversion problem and not a
yards-per-catch problem. It is an opportunity problem.**

The same mechanism on the ground game:

- Cook carry share **unconditional 0.454**, but **conditional on appearing 0.692**
- Ray Davis mean carries **4.11 when Cook appears**, **11.78 when Cook does not**
- Davis gains **+7.67 carries** in the 37.5% of worlds where Cook is absent

Conditional on appearing, Cook's 0.692 is far closer to the week-1 evidence
(0.867 RB-only) than his unconditional 0.454. **The absence mass is doing
almost all of the damage, and no football evidence supports it:** Cook played
week 1 with 13 carries, is RB1 on the depth chart, and carries no injury
designation — the only BUF removal in the availability feed is Ty Johnson.

## 5. Verdict

**MIXED.**

**ROLE_ALLOCATION_DEFECT** — the appearance inversion. A depth-chart RB1 with
week-1 usage and no injury designation must not carry a higher zero-opportunity
probability than his backup. Cook 0.375 against Davis 0.292 is not a plausible
football state, and it is the dominant cause of every Cook divergence.

**DATA_STATE_DEFECT** — CS1 is a quarterback panel. The current-season refresh
that fixed the QB season-boundary problem has no non-QB counterpart, so
week-1 receiving and rushing usage — which existed before the seal — never
reached role allocation. BUF's starters are consequently priced off prior-season
and depth-chart evidence alone, which for a reshaped receiving room (Moore,
Palmer) is exactly where it is weakest.

**NOT a defect:** conservation. Target and carry shares sum to 1.0000 on both
teams; nothing is lost, duplicated or invented. The totals are right and the
split is wrong.

## 6. What this does NOT establish

The market is not evidence of truth and is not used as one here. Week-1 is
**one game**: Cook's 13 carries and Moore's 8 targets are a small sample, and
the correct reading is that the model's allocation is inconsistent with the
only current-season football evidence there is, not that week-1 shares are the
right answer. No correction is implemented in this pass.

**MARKET IS DIAGNOSTIC EVIDENCE ONLY, NOT A TARGET**

**V2 NOT YET EARNED**
