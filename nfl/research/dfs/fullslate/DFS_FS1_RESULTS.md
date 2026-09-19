# DFS-FS1: prediction-time dependence baseline

Artifact: `DFS_FS1_DEPENDENCE_PANEL.json` · Module: `dependence_panel.py`

**These are descriptive validation targets for the world generator. Not one of
them may become a lineup rule, an exposure cap, or a simulator correlation
input.** The artifact carries `FS1_NOT_A_LINEUP_RULE` and a test enforces that
no value here appears as a code literal in production.

## 1. The panel is clean, and that is checked rather than claimed

| property | result |
|---|---|
| team-games per panel | **512** per season per site (544 minus the 32 week-1 games) |
| week 1 present | **no** — no prior history exists, and it is not back-filled |
| role collisions | **none**, all four panels |
| leakage mismatches | **0 of 512**, all four panels |

The leakage guarantee is *verified*, not asserted. Every role label is
re-derived from a history truncated strictly before its own week and required
to match. The external packet's method permitted one player to hold two roles —
26.2% of team-games had the quarterback also ranked as his own second carrier —
and a player correlated with himself at r = 1 means the panel is partly
measuring its own labelling. Roles here are mutually exclusive by construction,
assigned in a declared order: quarterback, then pass catchers by prior targets,
then rushers by prior carries, each drawn from players not already taken.

## 2. Same-team dependence: real, positive for QB with pass catchers

DraftKings, Pearson with 95% cluster-bootstrap intervals over **games** —
because the two team-games of one game share its scoring environment and are
not two independent draws.

| pair | 2024 | 2025 |
|---|---|---|
| QB · PC1 | **+0.207** [+0.103, +0.304] | **+0.170** [+0.070, +0.264] |
| QB · PC2 | **+0.250** [+0.158, +0.338] | **+0.174** [+0.082, +0.262] |
| QB · PC3 | **+0.108** [+0.020, +0.190] | **+0.145** [+0.056, +0.231] |
| QB · RUSH1 | **+0.104** [+0.021, +0.189] | **+0.133** [+0.043, +0.220] |
| QB · RUSH2 | +0.078 [−0.014, +0.176] | +0.049 [−0.043, +0.140] |
| RUSH1 · RUSH2 | **−0.118** [−0.197, −0.035] | **−0.179** [−0.259, −0.094] |
| PC1 · PC2 | −0.014 [−0.108, +0.079] | +0.072 [−0.020, +0.165] |

**Five pairs exclude zero in both seasons** — QB with each of PC1, PC2, PC3 and
RUSH1, and the negative RUSH1·RUSH2. Stability across two independent seasons
matters more than the count: these are the pairs a simulator has to reproduce.

**Two pass catchers on the same team are not a dependent pair.** PC1·PC2 spans
zero in both seasons. Whatever a QB-less two-receiver structure is, it is not
supported by same-team dependence.

## 3. Cross-team dependence: not distinguishable from zero

| | Pearson intervals excluding zero | tail-lift intervals excluding 1.0 |
|---|---|---|
| **same-team** (20 pair-seasons) | **10** | 6 |
| **cross-team** (16 pair-seasons) | **1** | **0** |

The single cross-team exception is `QB · opposing PC1` in 2025, +0.141
[+0.047, +0.227] — one in sixteen, which is roughly what a 95% interval
produces by chance.

Opposing quarterbacks specifically:

| | Pearson | tail lift |
|---|---|---|
| 2024 | +0.053 [−0.097, +0.190] | 1.255 [0.663, 1.737] |
| 2025 | +0.086 [−0.046, +0.211] | 1.041 [0.568, 1.641] |

**Both intervals contain zero; both tail intervals contain 1.0.** The external
packet reported +0.088 and +0.180 without intervals and built bring-back
reasoning on their positivity. At 256 games per season this panel cannot
distinguish that correlation from nothing. That is a statement about power, not
a claim that the effect is absent — but it means cross-team structure is not
currently an evidenced basis for anything.

## 4. Pearson and tail dependence are different quantities

They are computed and reported separately, never combined into one ranking, and
**they disagree in sign on four pair-panels**:

| panel | pair | Pearson | tail lift |
|---|---|---:|---:|
| DK 2024 | PC1·PC2 | −0.014 | 1.022 |
| DK 2025 | PC2·PC3 | +0.010 | 0.965 |
| FD 2024 | PC1·PC2 | −0.002 | 1.078 |
| FD 2025 | PC1·PC2 | +0.075 | 0.956 |

A pair can be linearly negative and jointly heavy in the upper tail, or the
reverse. Ranking structures by Pearson alone would order these wrongly. This is
the evidence for DFS-H4, produced by the panel rather than asserted.

## 5. DraftKings and FanDuel

Maximum absolute difference in Pearson across **every** pair, both seasons,
same-team and cross-team: **0.0153**, at QB·PC2 in 2024.

The dependence structure is effectively shared. One world generator can serve
both sites; what differs is scoring level, the marginal distributions it
induces, and the roster rules. This is the highest-leverage architectural
finding available from the panel, and it survives the canonical re-measurement.

## 6. What is not measured, and why it is named

**Every DST pair** — RB with own and opposing DST, QB with DST, PC1 with
opposing DST — returns `NOT_MEASURABLE` under code `FS1_DST_SCORING_ABSENT`.
There is no DST scoring adapter in this repository (`statline.NOT_SIMULATED`:
"the engine produces no team-defence outputs at all"), and DraftKings
points-allowed tiers cannot be verified without network access. The pairs are
listed in the artifact rather than omitted: a pair that silently vanishes is
indistinguishable from one that was measured and found uninteresting. Unblocked
by the site-rules request in `docs/AGENT_OUTBOX.md`.

## 7. The simulator comparison is PENDING, and it is specified

`simulator_comparison.state = PENDING`, blocked by the absence of a full-slate
joint-world generator — the only sealed worlds are one single-game board.

When it exists: score each simulated world with the same certified adapters,
form the same role panel, and compare the **sign and ordering** of Pearson and
of tail lift, separately. **Magnitudes are not comparable.** History is one
observation per game and carries between-matchup variation; a sealed board is
many observations of one fixture. That caveat is P5's, it predates this work,
and it survives it.

## 8. Honesty about declaration order

This is not a blind pre-registration. The role-assignment rule and the pair
list were chosen knowing the reproduction results at `06bc006`, on these same
two seasons. What was fixed before any number here was computed, and is listed
in `SPEC['declared_before_measurement']`: the cluster bootstrap over games with
2,000 resamples and seed 20260919, the 0.80 tail quantile, the separation of
Pearson from tail dependence, and reporting seasons separately rather than
pooling them.

Two seasons remains a small sample for tail statistics, which is why every
season is reported on its own line and no average is taken.

**V2 NOT YET EARNED**
