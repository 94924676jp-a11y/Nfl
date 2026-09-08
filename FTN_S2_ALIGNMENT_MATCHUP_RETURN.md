# FTN-S2 — ALIGNMENT + MATCHUP INCREMENTAL VALUE TEST

**Date** 2026-09-08 · **Repo** `94924676jp-a11y/Nfl` · **Branch** `main`
**Pre-analysis freeze** `nfl/research/ftns2/FREEZE_BEFORE_ANALYSIS.json`,
recorded on clean tree `bdc9fcb` before the new primitives were inspected.
**Sample** `56fc32e2…` — unchanged, re-verified.

## DECISION: `FTN_SAMPLE_TOO_SMALL_TO_RESOLVE`

**Not the same answer as FTN-S1, and the difference matters.** Routes were a
*structural* null — WR route participation is 0.989, so there was nothing to
correct where 70% of our error lives. Alignment is not structurally null: it
varies genuinely within players, and it produces an effect of the right sign
and a plausible size when fitted. What one game cannot do is tell us whether
that effect is real.

A larger sample request **is** justified, and it is small: **~10 games**.

Nothing bought, promoted or modified. The FTN-S1 route null is frozen and was
not revisited. G0A remains 11/12. NFL-1 remains NOT AUTHORIZED.

---

## 1. Coverage of the new primitives (§C)

67 dropbacks (`pass` + charted scrambles, `nopl` excluded), **311 route-plays,
53 charted targets, 66 plays with a target opportunity.**

| primitive | coverage | pre/post snap | prospectively available? | leakage |
|---|---|---|---|---|
| **offensive alignment** (`WR`/`SLT`/`HB`/`H-TE`/`Y-TE`/`FB`) | 311/311 route-plays, **100%** | pre-snap | **NO — see §5** | none as used |
| **matchup** (offense↔defense pair) | 327/327, **100%**; 120 of 156 plays | assignment, resolved post-snap | **NO** | none as used |
| defender position (`CB` 127, `SCB` 56, `LB` 54, `SLB` 31, `FS` 19, `OLB` 17, `SS` 6) | 310/311 | as above | NO | none |
| motion (`mot`) | 36 plays | pre-snap | NO | none |
| `sep`, `trg_sep`, `cball`, `yac`, `yaco`, `drp` | 29–52 each | **post-snap outcome** | **NO** | **would leak** — excluded |
| `pres` (pressure) | 36 | post-snap | NO | excluded |
| `advanced_stats` (DVOA/ALY) | team-level | — | — | excluded per §B |

Post-outcome fields were excluded outright rather than used as diagnostics,
because none of them could enter a forecast and including them would only
inflate an in-sample number.

### Alignment is genuinely play-varying — the mechanism routes lacked

**15 of 20 eligible players changed alignment across dropbacks.**

| player | alignment distribution |
|---|---|
| Jake Ferguson | SLT 16, Y-TE 5, H-TE 4, WR 3 |
| Dallas Goedert | SLT 13, H-TE 6, WR 5, Y-TE 4 |
| Jahan Dotson | WR 12, SLT 10 |
| CeeDee Lamb | WR 21, SLT 9 |
| DeVonta Smith | SLT 23, WR 9 |
| Saquon Barkley | HB 24, WR 4 |

This is real information our architecture does not carry. It is exactly what
ROUTE-BB1 identified as the only kind of thing that *can* help — variation
within a player, not a level. That is why this packet could not be answered by
the route result.

---

## 2. Primary test — honest out-of-sample (§D–§F)

Raw target rates by alignment (WR 0.184, SLT 0.144, HB 0.122, H-TE 0.267,
Y-TE 0.300) are **not reported as value**, per §D: they are confounded by which
players line up where.

The test is **leave-one-player-out**. The alignment (or matchup) adjustment is
estimated on the other 19 players and applied to the held-out one, so no
player's own plays inform his own adjustment. Play-clustered bootstrap, 4,000
resamples — targets within a play are mutually exclusive, so plays are the
cluster.

| arm | Brier | ΔBrier vs control | 95% CI | verdict |
|---|---|---|---|---|
| **CONTROL** | 0.14219 | — | — | — |
| **FTN-A** alignment | 0.14970 | **+0.00751** | [+0.0038, +0.0111] | **worse** |
| **FTN-M** matchup | 0.14762 | +0.00543 | [−0.00002, +0.0112] | not distinguishable |
| **FTN-AM** both | 0.15642 | +0.01423 | [+0.0072, +0.0213] | **worse** |

Out of sample, both arms **degrade** prediction.

### That is overfitting, not a broken arm — checked, not assumed

| arm | Brier **in-sample** | Δ |
|---|---|---|
| control | 0.14219 | — |
| alignment | 0.13961 | **−0.00258** |
| matchup | 0.13829 | **−0.00390** |

The machinery fits when allowed to. The out-of-sample degradation is genuine
non-generalisation across players, which is what 53 targets buys you.

The fitted adjustments show why they do not travel:

    alignment  WIDE 0.89 (n=125)  SLOT 0.79 (n=111)  BACK 0.82 (n=50)  TE_INLINE 1.43 (n=25)
    matchup    CB   0.88 (n=127)  SCB  0.39 (n=56)   LB   1.18 (n=103) S 1.06 (n=25)

`SCB = 0.39` and `TE_INLINE = 1.43` are large effects estimated off a handful
of targets. They are the kind of number that reverses on the next game.

### Downstream, under the most generous possible test

Aggregated to player-game targets, **fitting the adjustment on this very game**
— i.e. deliberately cheating in FTN's favour:

| arm | MAE | bias | ρ |
|---|---|---|---|
| CONTROL | 1.5982 | +0.3795 | — |
| FTN-A alignment | 1.4397 | +0.0074 | **+0.0992** [−0.0624, +0.2471] |
| FTN-M matchup | 1.4787 | +0.0515 | +0.0748 [−0.1501, +0.2791] |

So the **ceiling** on alignment from this game is ρ ≈ 0.10 — about **9% target
CRPS** on the frozen ROUTE-BB1 curve — and the **honest** figure is negative.
The truth is somewhere between, and 19 player-games cannot say where.

Worth noting: alignment removes almost all of the control's bias (+0.3795 →
+0.0074). That is suggestive rather than evidence, and it is the single most
interesting thing in this packet.

---

## 3. Attribution (§G)

Stated as the packet requires, not as "FTN helps":

- **alignment: UNRESOLVED.** Out-of-sample worse; in-sample ρ ≈ 0.10; mechanism
  present and plausible (15/20 players vary).
- **matchup: UNRESOLVED, and weaker.** Out-of-sample not distinguishable from
  control; in-sample ρ ≈ 0.07; wider interval.
- **coverage (defender position): tested as part of matchup**, same verdict.
- **motion: NOT TESTED** — 36 plays is too few to carry its own arm, and
  testing it would have been a feature search.
- **route participation: frozen null from FTN-S1**, not revisited or retuned.

---

## 4. One-game limitation (§H)

**Observed sample effect:** out-of-sample alignment and matchup adjustments are
worse than control; in-sample they fit, with ρ ≈ 0.10 and 0.07.

**Uncertain league-wide effect:** whether alignment carries a real target-rate
signal beyond player identity. The mechanism exists; the estimate does not
generalise at this size.

**Additional games required**, from bootstrapping over players:

| primitive | in-sample ρ | 95% CI | games for ±5pp |
|---|---|---|---|
| **alignment** | +0.0992 | [−0.0624, +0.2471] | **~10** |
| matchup | +0.0748 | [−0.1501, +0.2791] | ~18 |

---

## 5. The structural caveat that would survive any sample size

Even if a larger sample showed alignment carries real signal, **alignment is
not known before a game is played.** To use it in a forecast we would have to
predict each player's alignment distribution from his history — which is a
player-level tendency, and ROUTE-BB1 established that a player-constant
multiplier cancels out of this architecture entirely.

So the prospective value depends on a narrower thing than the diagnostic value:
**does a player's alignment mix vary from game to game in a way predictable
from prior games?** This sample cannot answer that — it contains one game, and
the question is by definition about between-game variation.

I am flagging this now rather than after a 10-game request, because it changes
what to ask for: **the games should be spread across weeks and teams, not
consecutive**, so between-game variation in alignment is observable at all. A
10-game block from one week would answer the diagnostic question and leave the
prospective one exactly where it is.

---

## 6. Recommendation

**A larger sample request is justified, and it is cheap: ~10 games, spread
across different weeks and teams.** That resolves alignment to ±5pp and, if
they are drawn from different weeks, gives the first look at whether alignment
mix is predictable game to game.

I would not spend $5,000 on this evidence, and §H told me not to — the effect
is neither extraordinarily large nor yet structurally coherent.

**What I would say to FTN:** the sample was useful and specific follow-up would
be decisive. Ask for ~10 games across at least 5 different weeks. That is a
normal pre-sale request and it costs them very little.

If the 10 games come back null on alignment too, then on the evidence available
I would be comfortable saying: **do not spend $5,000 on FTN.** Routes are
already a structural null; alignment and matchup would then be an empirical
null on a sample large enough to see a ρ ≈ 0.10 effect. That is a defensible
"no" rather than a one-game one.

Perplexity is still not useful yet — there is no confirmed valuable primitive
to ask about replicating.

---

## 7. Explicit restatements

- **The FTN-S1 route null is frozen** and was not revisited, retuned or
  re-scored. Its hash is in the freeze artifact.
- **No parameter of the control was refit.** Control hash unchanged;
  `rbb1_lib.py` `56eb6a3c…`, panel `6cb51092…`.
- **No feature search.** Only the predeclared primitives were tested; motion
  was declared untested rather than quietly tried.
- **No post-outcome field was used** — `sep`, `cball`, `yac`, `pres` and the
  rest were excluded, not used as "diagnostics".
- **Nothing bought, nothing promoted, no production model touched.**
  **G0A remains 11/12. NFL-1 remains NOT AUTHORIZED.**

**THEN STOP.**

### Files

| path | what |
|---|---|
| `nfl/research/ftns2/FREEZE_BEFORE_ANALYSIS.json` | hashes and rules before inspection |
| `nfl/research/ftns2/ftns2_results.json` | every number in this return |
