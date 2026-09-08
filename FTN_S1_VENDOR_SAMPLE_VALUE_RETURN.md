# FTN-S1 — VENDOR SAMPLE INCREMENTAL VALUE TEST

**Date** 2026-09-08 · **Repo** `94924676jp-a11y/Nfl` · **Branch** `main`
**Sample** `56fc32e21cb130c1e14a8b3817f0c43491b310e69cfd4663b5bbd5d973ccffa4`
— verified to match the ROUTE-BB1 seal **exactly** before opening.
**Pre-unseal freeze** `nfl/research/ftns1/FREEZE_BEFORE_UNSEAL.json`, committed
`10d5a36` before the sample was read.

## DECISION: `FTN_SAMPLE_NO_MATERIAL_VALUE`

**ρ_FTN = +0.0062**, 95% CI **[−0.0705, +0.0916]** — indistinguishable from
zero. Mapped onto the frozen ROUTE-BB1 curve that is a CRPS gain of about
**0.6%**, against a measured placebo floor of **−0.87%**.

Nothing was bought, promoted or modified. No parameter was trained or tuned on
the sample. G0A remains 11/12. NFL-1 remains NOT AUTHORIZED.

---

## 1. Authorization, stated once and not re-argued

ROUTE-BB1 §7 found the supplied contract grants no written permitted use: it is
an **unsigned draft**, §6.1 licenses only a *Client* under an executed
agreement, §5.2 restricts data to Client property, and there is no evaluation
or sample clause. You directed the evaluation on the basis of your own vendor
relationship — FTN supplied the sample to you, and whether to evaluate a
vendor's sample before buying is your commercial call. That is recorded in the
freeze artifact so the basis is visible. I proceeded on it.

---

## 2. The taxonomy, as observed (§1)

156 plays, DAL@PHI, 2025-09-04, FTN event `30351`. Offensive role vocabulary,
**raw and uncollapsed**:

| role | count | reading |
|---|---|---|
| `rte` | 310 | route |
| `rbl` | 227 | run block |
| `pas` | 71 | passer |
| `run` | 47 | ball carrier |
| `brte` | 22 | route (blocking-release variant) |
| `ppro` | 16 | **pass protection** |
| `frte` | 10 | route (fake//play-action variant) |
| `fho` | 6 | fake handoff |
| `scbl` | 4 | screen block |
| `fpro` | 1 | protection variant |
| `None` | 899 | uncharted — overwhelmingly offensive linemen |

Route set = `{rte, brte, frte}`. Protection set = `{ppro, scbl, fpro}`.
`advanced_stats` is **team-level DVOA/ALY**, not player route information;
`matchups` is player-vs-player. Neither bears on the primitive.

### One correction that mattered

FTN classifies a **scramble as `play_type = "rush"`**, and this project's
binding QB1 identity counts a scramble as a dropback. Taking FTN's `pass` plays
at face value would have understated the dropback set by ~13% and made our
`pass_snaps` look far worse than it is.

Corrected dropback set = `pass` + rush-with-charted-passer-and-routes, with
`nopl` excluded to match our own `no_play` convention. Result:

| | DAL | PHI |
|---|---|---|
| **FTN dropbacks** | **34** | **33** |
| **our `team_dropbacks_part`** | **34** | **33** |

**Exact agreement on both teams.** An independent vendor's charting reproduces
our dropback definition precisely — the first outside validation this project
has had of that primitive, and worth more than it cost.

---

## 3. FTN truth vs our representation (§2–§3)

Join: exact full-name equality within team. **20 of 20 FTN eligible receivers
matched, 20 of 20 panel players matched, no residual.** No fuzzy matching was
used or needed.

| position | n | FTN routes | FTN protection | our `pass_snaps` | routes / pass_snaps | pass_snaps overstates by |
|---|---|---|---|---|---|---|
| WR | 8 | 182 | 1 | 184 | **0.989** | **1.1%** |
| TE | 6 | 75 | 7 | 85 | **0.882** | **11.8%** |
| RB | 6 | 54 | 8 | 66 | **0.818** | **18.2%** |
| **all** | 20 | **311** | **16** | **335** | **0.928** | **7.2%** |

So the accepted representation is wrong in the direction we expected and by a
**smaller margin than assumed**. ROUTE-BB1 assumed WR 0.90 / TE 0.70 / RB 0.40;
measured here it is 0.989 / 0.882 / 0.818. Our denominator was already close to
right, especially where it matters most.

(311 + 16 = 327 against 335 pass snaps: **8 player-plays** were on the field
with no charted role. Named, not absorbed — they are 2.4% and do not change any
conclusion.)

---

## 4. Primary test — does FTN information fix our errors? (§4–§5)

Control: `pass_snaps × prior targets-per-pass-snap`, prior-only history from
2020 through 2024, shrinkage K = 4, exactly as frozen.
FTN-informed: `FTN routes × prior targets-per-route`, the same history, the
same shrinkage, **nothing retrained**. The substitution's whole effect is the
player's deviation from position-average route participation *in this game* —
which ROUTE-BB1 predicted, before the sample was opened, is the only thing that
can matter.

| | control | FTN-informed |
|---|---|---|
| MAE | 1.4681 | 1.4590 |
| bias | +0.5465 | +0.5622 |
| Σ\|error\| | 29.363 | 29.181 |

**ρ_FTN = +0.0062**, 95% CI **[−0.0705, +0.0916]** (bootstrap over 20 players).

| position | n | ρ | 95% CI |
|---|---|---|---|
| WR | 8 | **−0.0086** | [−0.0325, +0.0154] |
| TE | 6 | **+0.1720** | [−0.2883, +0.3447] |
| RB | 6 | −0.1059 | [−0.5231, +0.3598] |

Of 20 players, FTN improved 7 and worsened 12.

### Why it is near zero, and this is the mechanism not an excuse

| position | share of targets | share of our error | route participation |
|---|---|---|---|
| WR | 52.8% | **69.9%** | **0.989** |
| TE | 30.2% | 15.8% | 0.882 |
| RB | 17.0% | 14.2% | 0.818 |

**Seventy percent of our error sits on WRs, and WRs run routes on 98.9% of
their pass snaps.** There is almost nothing there for route data to correct.
The positions where the denominator *is* wrong carry 30% of the error between
them. The ceiling on the whole exercise is therefore low regardless of how good
the charting is.

### The decomposition that settles it

| | share of control error |
|---|---|
| irreducible by **any** route denominator | 24.6% |
| addressable in principle by a **perfect** denominator | **75.4%** |
| **actually captured by FTN's real routes** | **0.6%** |

ROUTE-BB1 computed this ceiling as **75.6%** on 22,348 player-games using
*assumed* route levels, before the sample existed. Here it is **75.4%** on the
FTN game using *measured* levels. Two independent routes to the same number is
a real check, and it passed.

The gap between 75.4% and 0.6% is the whole finding: **knowing the true routes
is not the same as choosing the optimal denominator.** The routes are what they
are, and they barely differ from pass snaps.

---

## 5. Attribution (§6)

| primitive | value observed |
|---|---|
| **true routes run** | the only primitive tested; **+0.6%**, indistinguishable from zero |
| **pass-protection distinction** | this *is* the route/protect split — same +0.6% |
| alignment | present as `WR / SLT / HB / Y-TE / H-TE / FB`; **not tested** |
| route-role subtype (`rte`/`brte`/`frte`) | collapsed to route; sub-types not separately tested |
| matchup / coverage | `matchups` populated on 120 plays; **not tested** |
| team DVOA / ALY (`advanced_stats`) | team-level, not a participation primitive |

No feature search was run, per §6. The untested primitives are recorded as
untested rather than as absent — alignment in particular is a genuinely
different primitive and this packet says nothing about it.

---

## 6. One-game limitation (§7)

**OBSERVED_IN_THIS_SAMPLE**
- role taxonomy and its 11 values;
- FTN dropbacks equal our `team_dropbacks_part` exactly, 34/34 and 33/33;
- route participation 0.989 / 0.882 / 0.818 (WR/TE/RB);
- pass snaps overstate routes by 7.2% overall;
- ρ_FTN = +0.006 [−0.071, +0.092].

**PLAUSIBLE_LEAGUE_VALUE**
- that WR route participation is near-total league-wide, and therefore that the
  denominator error is structurally concentrated in TE and RB;
- that the bulk of target error is rate error, not denominator error.

**UNPROVEN_WITH_ONE_GAME**
- the TE point estimate of +0.172. Its interval spans zero and it rests on
  **six players**;
- everything about RB (interval spans half the range);
- any seasonal, scheme or team variation whatsoever.

---

## 7. What would settle it

| question | player-games needed for ±5pp on ρ | ≈ games |
|---|---|---|
| pooled ρ | ~3× this sample | **~3 games** |
| **TE-only ρ** | ~36× | **~36 games** |
| RB-only ρ | ~69× | ~69 games |

The pooled answer is nearly settled already: three more games would put ρ
within ±5pp, and it is currently centred on 0.6% with a tight, structurally
explained null on the position carrying 70% of the error.

**If you want to chase the TE signal specifically**, that is ~36 games and it
is a different and much narrower purchase question than the one asked. On the
frozen curve, even if TE's +0.172 survived, TEs carry 15.8% of our error, so
the pooled gain would be ≈ 0.172 × 0.158 ≈ **2.7% of target CRPS**.

---

## 8. Recommendation

**Do not buy on this evidence, and do not proceed to the Perplexity step for
route participation.** The primitive you set out to price does not move our
model, and the reason is structural rather than a sampling accident: our
denominator is already 98.9% correct where 70% of our error lives.

That also answers the sequencing question you set. Step 2 was "identify which
FTN primitives created the value." On this sample, **route participation
created no value**, so there is nothing about it to hand to Perplexity. Asking
whether route data can be reproduced independently is now a question about
something we have measured to be worth ~0.6%.

Three things are worth saying plainly:

1. **The sample was still worth having.** It independently validated our
   dropback definition to the play, corrected our assumed route-participation
   levels (which were badly off for RB — 0.818 measured against 0.40 assumed),
   and converted the central unknown from unmeasured to measured. That is a
   good outcome for a free sample.
2. **If you want a defensible "no", three more games gets you there** at ±5pp
   on the pooled figure. That is a reasonable thing to ask FTN for before
   declining.
3. **The untested primitives are the live question now, not routes.**
   Alignment and coverage/matchup fields are in this sample, populated, and
   were not evaluated because you scoped this packet to route participation. If
   FTN is to be bought, on this evidence it would be for those — and that is a
   different experiment.

**I would not run it without you deciding that**, because it is a new scope and
the last three packets have all been "then stop".

---

## 9. Explicit restatements

- **Nothing was bought.** No commitment, no contract action.
- **No parameter was trained, fitted or tuned on the sample.** The control was
  hashed on a clean tree before unsealing and is unchanged: `rbb1_lib.py`
  `56eb6a3c…`, HEAD `ba2dfff`.
- **The ROUTE-BB1 necessity curve was not recomputed or adjusted** after seeing
  FTN. ρ_FTN was mapped onto it as frozen.
- **No FTN system was accessed or scraped.** Only the supplied file was read.
- **G0A remains 11/12. NFL-1 remains NOT AUTHORIZED. No production model was
  touched. Nothing was promoted.**

**THEN STOP** — and the T−90 and production work is untouched by this packet.

### Files

| path | what |
|---|---|
| `nfl/research/ftns1/FREEZE_BEFORE_UNSEAL.json` | hashes and rules recorded before opening |
| `nfl/research/ftns1/ftns1_results.json` | every number in this return |
| `nfl/research/rbb1/` | the frozen control and necessity curve |
