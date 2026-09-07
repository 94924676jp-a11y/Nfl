# P4 — team play volume and pass/run environment

**Date:** 2026-09-07 · **Repository:** `94924676jp-a11y/nfl`
**Track:** quarantined historical research. G0A untouched at **11/12**.
NFL-1 not executed. **2026 outcomes used: none.**

---

## The answer, up front

**We cannot forecast the size of the pie. We can forecast its composition a
little, and neither is improved much by modelling.**

| Question | Answer |
|---|---|
| **A.** Team plays better than simple baselines? | **No.** r = 0.093–0.167. The **league mean** is the best baseline in 2 of 4 seasons. |
| **B.** Pass/run tendency better than persistence? | **No.** Ridge fails to beat the best baseline in **4 of 4** seasons for both `pass_rate` and `neutral_pass_rate`. |
| **C.** Does PROE add next-game value beyond raw pass rate? | **PROE is far more *reliable* but adds almost nothing predictively.** See §13. |
| **D.** Does plays × pass-rate beat direct dropback persistence? | **No.** Both are weak; the product inherits the plays error. |
| **E.** Incremental value of play caller, QB, opponent? | **Play caller is the largest, and it is real.** `coach_prior` is the single best simple baseline more often than any other. |
| **F.** What is too noisy to model beyond shrinkage? | **Team plays, team rush attempts, and non-QB rush attempts.** |

This is a **largely negative return**, and it is the honest one. P1 found team
dropbacks weak from QB history (r ≈ 0.10–0.22). P4 asked whether team-level,
pace, tendency, coaching and opponent information could fix that. **It cannot.**
Team offensive volume is close to a coin flip around a stable team-and-coach
level, and the residual is game script — which is not knowable pregame without
the market data this project forbids.

---

## 1–6. HEAD, commits, tests, sources, samples

| | |
|---|---|
| HEAD at task start | `231a6d4` |
| G0A suite | 1,230 assertions, 0 failing — **unchanged by this work** |
| Seasons | **2016–2025** regular season (P1–P3 used 2020–2025; deepened for coach priors) |
| Team-games | **5,278** |
| Play-state rows for the xPass fit | **332,906** |
| Evaluation seasons | 2022, 2023, 2024, 2025 (544 team-games each) |
| Sources | nflverse `pbp` 2016–2025, captured `schedules` snapshot |

---

## 7. Target definitions, with denominators stated

P1 already lost a result to `pass_attempt` silently including sacks, so every
count names what it counts.

| target | definition |
|---|---|
| `plays` | offensive plays with a `posteam`, excluding two-point attempts, that are a dropback, rush or pass attempt |
| `dropbacks` | `qb_dropback == 1` — **includes sacks and scrambles** |
| `pass_att_ex_sacks` | `pass_attempt == 1 AND sack == 0` |
| `sacks` / `scrambles` | `sack == 1` / `qb_scramble == 1`, charged to the **rusher** |
| `designed_qb_rush` | QB rush that is not a scramble |
| `nonqb_rush_att` | `rush_att` − scrambles − designed QB rushes |
| `pass_rate` | `dropbacks / plays` |
| `neutral_pass_rate` | same, restricted to `abs(score_diff) ≤ 8`, quarters 1–3, `down ≤ 2` |
| `early_down_pass_rate` | same, `down ∈ {1,2}` |
| `sec_per_play` | mean gap between that team's consecutive plays, neutral filter, ≥5 observations |

## 8–9. Features and chronology

Every feature is built from games **strictly before** the row's own
`(season, week)`. Classification fixed before use:

| class | fields |
|---|---|
| observed primitive | play type, dropback, rush/pass attempt, sack, scramble, down, distance, field position, clock |
| derived from past games | all EWMA / rolling / expanding team and coach histories, PROE |
| pregame schedule fact | `rest`, `home`, `div_game`, `roof`, `surface`, opponent identity |
| **model-derived, QUARANTINED** | nflfastR `xpass`, `pass_oe`, `wp`, `epa`, `cpoe` |
| **market-derived, FORBIDDEN** | `spread_line`, `total_line` |
| **postgame, FORBIDDEN** | `result`, `total`, scores |
| **observed weather, FORBIDDEN** | `temp`, `wind` — no point-in-time forecast analogue exists |

**The QB-identity decision was split rather than assumed.** `home_qb_id` records
who *actually* started, which for most games is announced days ahead and for a
game-time decision is not. Arm A uses prior-game QB identity only; Arm B allows
current-game identity and is labelled as assuming the announced starter is
known. Arm B's gain over Arm A is reported as the value of that knowledge, not
as a free feature.

---

## 10–12. Baselines and the plays / pass-rate results

Eight baselines per target: league mean · team expanding mean · last game ·
rolling-3 · rolling-5 · EWMA · previous-season team mean · coach prior.
Uncertainty is a **team-block bootstrap** (400 resamples, seed 20260907) —
a team's games are not independent, so the resampling unit is the team.

### Q1 — team offensive plays: not forecastable

| Season | n | best baseline | its MAE | ridge MAE | ridge r | ridge − best |
|---|---|---|---|---|---|---|
| 2022 | 542 | `coach_prior` | 6.5151 | 6.4413 | **0.167** | −0.0704 [−0.2203, +0.0721] ✗ |
| 2023 | 544 | **`league_mean`** | 6.6594 | 6.6296 | **0.100** | −0.0286 [−0.1649, +0.1256] ✗ |
| 2024 | 544 | **`league_mean`** | 6.7311 | 6.6381 | **0.093** | −0.0910 [−0.1908, +0.0135] ✗ |
| 2025 | 544 | `team_expanding` | 6.8555 | 6.7219 | **0.160** | −0.1373 [−0.2715, −0.0124] ✓ |

**In two of four seasons the best simple baseline is the league mean** — team
history carries no usable information about next-game play count. Correlation
peaks at 0.167. The ridge beats the best baseline in one season of four, by
about a seventh of a play.

**Team offensive plays are effectively unforecastable beyond a league constant.**

### Q2 — pass tendency: not better than persistence

| Target | Season | best baseline | its MAE | ridge MAE | ridge r | verdict |
|---|---|---|---|---|---|---|
| `pass_rate` | 2022 | `ewma` | 0.0874 | 0.0856 | 0.322 | ✗ |
| | 2023 | `coach_prior` | 0.0802 | 0.0806 | 0.201 | ✗ |
| | 2024 | `ewma` | 0.0839 | 0.0821 | 0.307 | ✗ |
| | 2025 | `coach_prior` | 0.0825 | 0.0818 | 0.219 | ✗ |
| `neutral_pass_rate` | 2022 | `ewma` | 0.0855 | 0.0841 | 0.441 | ✗ |
| | 2023 | `league_mean` | 0.0877 | 0.0857 | 0.236 | ✗ |
| | 2024 | `ewma` | 0.0843 | 0.0818 | 0.248 | ✗ |
| | 2025 | `league_mean` | 0.0858 | 0.0838 | 0.250 | ✗ |

**Zero of eight.** Every bootstrap interval spans zero. Pass tendency is
somewhat more predictable than volume (r up to 0.44 for the neutral rate), but
nothing in the feature set beats an EWMA or a coach prior.

### Q3/Q4 — dropbacks and rushing volume

| Target | Season | best baseline | its MAE | ridge MAE | ridge r | verdict |
|---|---|---|---|---|---|---|
| `dropbacks` | 2022 | `coach_prior` | 6.7783 | 6.6571 | 0.341 | ✗ |
| | 2023 | `coach_prior` | 6.2403 | 6.2717 | 0.165 | ✗ |
| | 2024 | `league_mean` | 6.6224 | 6.4009 | 0.220 | **✓** |
| | 2025 | `ewma` | 6.5855 | 6.4935 | 0.239 | ✗ |
| `rush_att` | 2022–2025 | `ewma` / `coach_prior` | 5.87–6.16 | 5.84–6.05 | 0.163–0.300 | ✗ all four |
| `nonqb_rush_att` | 2022–2025 | mixed | 5.43–5.62 | 5.40–5.56 | 0.141–0.227 | ✗ all four |
| `designed_qb_rush` | 2022–2025 | `ewma` / `coach_prior` | 1.30–1.61 | 1.30–1.61 | **0.394–0.531** | ✗ all four |
| `sacks` | 2023–2025 | `ewma` / `coach_prior` | 1.22–1.26 | 1.23–1.25 | 0.342–0.418 | ✗ all four |

**Designed QB rushes are the most predictable quantity in the whole study**
(r ≈ 0.39–0.53) — unsurprisingly, since it is close to "is this a running
quarterback". It is still not improved by modelling: an EWMA already captures
it.

**Rushing volume is not a residual and was not treated as one.** Modelled
directly, it is as unforecastable as plays.

---

## 13. PROE — rebuilt, not borrowed, and the answer is a split verdict

### Why it was rebuilt

nflfastR ships `xpass` and `pass_oe`. **Their fitting window is not documented
in the artifact**, so a model fitted on 2016–2024 would make the 2024 column
partly a function of 2024 — exactly the leakage the directive forbids. Both are
quarantined and never read. (Verified mechanically: §21 greps for actual reads,
not mentions.)

### The reconstruction, documented per §PROE

**Formula.** `xPass_hat = σ(w · x)`, logistic.

**Inputs**, all observed at the snap: down indicators (1–4); `ydstogo` capped at
25; `yardline_100`; score differential clipped to ±28, plus its square;
`game_seconds_remaining`; first-half indicator; posteam timeouts; and two
interactions (distance × 3rd down, clock × score differential).

**Fitting procedure.** Fitted separately for each evaluation season on plays
from **seasons strictly before it** — 197,300 plays for 2022 rising to 299,579
for 2025. Base dropback rate 0.603–0.606; training Brier 0.2004–0.2010.

**No same-game or future outcome enters the feature.** Two separate questions,
kept apart and both tested in §21: (a) the xPass *model* never sees the
evaluation season — guard-deletion 2; (b) a team-game's PROE is used only as a
lagged feature for later games — guard-deletion 1.

### Reliability — PROE is clearly the better-behaved quantity

| | PROE | raw pass rate |
|---|---|---|
| split-half (within team, n=32) | **+0.8913** | +0.7306 |
| week-to-week (n=4,958) | **+0.2970** | +0.1620 |
| year-over-year (n=288) | **+0.4136** | +0.3823 |

**PROE nearly doubles week-to-week reliability.** Removing game state from the
pass rate leaves something substantially more stable.

### Next-game predictive value — almost none

That reliability does **not** convert. `pass_rate` and `neutral_pass_rate`
ridge models — which include PROE EWMA and PROE rolling-3 — fail to beat the
best simple baseline in **8 of 8** target-seasons. And in the ablation, removing
the PROE block changes MAE by a negligible amount (§19).

**This is the R1 finding #8 and P1's own discipline demonstrated on our data:
reliability and next-game predictive value are different properties, and PROE
is the cleanest example of the gap either project has produced.** A quantity can
be highly self-consistent and still tell you nothing new about the next game,
because the thing it is consistent about is already in the team's recent pass
rate.

**Verdict: PROE is available and leakage-safe in our reconstruction, and it does
not earn a place in a next-game team-volume model.** It is not returned as
`PROE UNAVAILABLE` — the implementation is sound; the feature simply does not
help.

---

## 21–22. Adversarial tests and guard-deletion proofs

**26 checks, 0 failing.** Seeded positives must light up before negatives mean
anything.

| probe | result |
|---|---|
| 1 same-game plays **[seeded]** | **LEAK DETECTED** |
| 2 same-game dropbacks **[seeded]** | **LEAK DETECTED** |
| 3 realized score differential **[seeded]** | **LEAK DETECTED**, ΔMAE −3.78, r → 0.903 |
| 4a current-week PROE vs *plays* | no gain — **correct**, see below |
| **4b current-week PROE vs *pass rate*** | **LEAK DETECTED**, ΔMAE −0.0251, **r 0.307 → 0.751** |
| 5 future-week pace | no gain ✓ |
| 6 prior-game plays (legitimate) | no gain ✓ |
| 7 rest days · 8 home indicator | no gain ✓ |
| `spread_line`, `total_line`, `temp`, `wind`, `result`, `total` | present in the source, **absent from the panel** ✓ |
| `spread_line`, `total_line`, `temp`, `wind`, `pass_oe`, `xpass` | **never read** in P4 code ✓ |

**Probe 4 failed on the first run and was right to.** I seeded
`proe × plays` against the *plays* target and expected a leak. PROE is a
pass-**tendency** residual, so it barely encodes play **count** — the probe
correctly found nothing. The mis-seeding was mine, and the fix was to seed it
against `pass_rate`, where PROE is very nearly the outcome. It now lights up
hard. **A probe that fails to detect a leak it was never capable of detecting is
a badly built probe, not a passing guard**, and it is recorded as such.

A second failure was also mine: the forbidden-field check matched the word
`pass_oe` inside my own comment *explaining that it is quarantined*. It now
checks for actual reads (`['field']`, `.get('field')`), not mentions.

### Guard-deletion 1 — chronology in `attach_history`

Append each game's value to its own history **before** reading it, and rerun:

| | MAE | r |
|---|---|---|
| with the guard | 6.6381 | **0.0927** |
| **bypassed** | **0.0111** | **1.0000** |

A perfect model. That is what the chronology guard is holding back, and it is
the clearest possible demonstration that the honest r ≈ 0.09 is a property of
the football and not of a broken pipeline.

### Guard-deletion 2 — the xPass training window

| xPass fitted on | Brier on 2024 plays |
|---|---|
| prior seasons only (the guard) | 0.20134 |
| including 2024 (bypassed) | 0.20128 |

The gap is **+0.00006** — tiny, and that is itself informative: the xPass model
is extremely stable across seasons, so this particular leak would have bought
almost nothing. The guard stays because *demonstrating* a leak is small is not
the same as being entitled to take it.

---

## 16–18. Play caller, opponent, and QB change

### Play caller is the largest single source of signal, and it is a *baseline*

Across 36 target-seasons, how often each simple baseline was the best:

| baseline | times best |
|---|---|
| `ewma` | **14** |
| **`coach_prior`** | **13** |
| `league_mean` | 6 |
| `team_expanding` | 3 |

**A head-coach prior — the mean of that coach's prior games, at any team — is the
single best simple predictor almost as often as a team EWMA.** That is a real
answer to Q5: offensive tendencies persist by *coach* at least as strongly as by
*franchise*, and it holds without any modelling.

But note what it is: a *baseline*, not a model gain. When the play-caller block
is added to the ridge, its ablation contribution is between +0.0000 and +0.0014
— the information is already in the coach prior, and the ridge does not extract
more from it.

### Opponent contributes nothing

The opponent block's ablation contribution is **−0.0000 to +0.0000** on every
target. Removing it does not hurt. Opponent pace, opponent plays faced and
opponent pass rate faced are all in the design, and none of them helps.

### QB change: knowing the announced starter is worth almost nothing

Arm B (current-game QB identity allowed) minus Arm A (prior-game only), across
36 target-seasons, produced **four** significant differences — and **two of them
favour the strict arm**:

| target | season | Arm B − Arm A |
|---|---|---|
| `plays` | 2025 | **−0.0202** [−0.0344, −0.0046] (B better) |
| `pass_rate` | 2025 | +0.0002 [+0.0000, +0.0004] (A better) |
| `nonqb_rush_att` | 2022 | +0.0329 [+0.0089, +0.0590] (A better) |
| `scrambles` | 2025 | +0.0034 [+0.0002, +0.0070] (A better) |

**Knowing who is actually starting buys essentially nothing for team volume.**
That is worth stating plainly because it is counter-intuitive, and because it
means P4's conclusions do not depend on the one field whose pregame status was
questionable.

The QB-change *subgroup* is harder for everything, as expected — `dropbacks` MAE
6.62 → 7.62 under the league mean — and it is the one cohort where **the ridge
is actively worse than the baseline** (7.93 vs 7.62). With 71 games it is a
small sample, but the direction is consistent with P1–P3: novel situations are
where models degrade.

## 19. Ablation table

Mean change in MAE when each block is removed (positive = load-bearing):

| block | plays | pass_rate | neutral_pass_rate | dropbacks | rush_att |
|---|---|---|---|---|---|
| **pace** | **+0.0193** | +0.0000 | +0.0000 | **+0.0091** | +0.0067 |
| **proe** | −0.0000 | +0.0001 | **+0.0009** | **+0.0082** | −0.0034 |
| qb | +0.0033 | +0.0000 | +0.0000 | +0.0028 | +0.0000 |
| team_history | +0.0020 | +0.0001 | +0.0000 | +0.0000 | **+0.0111** |
| regime_change | +0.0000 | +0.0001 | +0.0000 | +0.0000 | **+0.0109** |
| play_caller | +0.0000 | +0.0000 | +0.0001 | +0.0014 | +0.0000 |
| **opponent** | **−0.0000** | **−0.0000** | **−0.0000** | **−0.0000** | +0.0000 |

**Pace is the only block that consistently earns its place**, and it earns about
two hundredths of a play. Everything else is at or below the noise floor. The
honest reading of this table is not "pace matters most" — it is **"nothing in
this feature set matters much, and pace matters least-little"**.

## 20. Subgroups

`plays`, 2024 (best baseline = league mean): coach-stable 6.735 → 6.635;
QB-stable 6.655 → 6.567; QB-change 7.238 → 7.110. The ridge is uniformly a
hair better and nowhere materially better.

`dropbacks`, 2024: QB-stable 6.472 → 6.171 (the ridge's best showing);
**QB-change 7.625 → 7.930 (the ridge is worse)**.

## 23. Failures and negative findings

Stated plainly, since they are most of the return:

1. **Team offensive plays cannot be forecast** beyond a league constant plus a
   little team level. r = 0.093–0.167; the league mean wins outright in half the
   evaluation seasons.
2. **Pass tendency cannot be improved on persistence.** 0 of 8 target-seasons.
3. **Dropbacks are not fixed by the plays × pass-rate decomposition.** Both
   factors are weak and the product inherits the plays error. 1 of 4 seasons.
4. **Rush volume is as unforecastable as plays**, modelled directly rather than
   as a residual.
5. **Opponent information is worthless here** — measured at exactly zero.
6. **PROE is much more reliable than raw pass rate and adds nothing predictive.**
7. **Knowing the announced starting QB buys essentially nothing** for team
   volume.
8. **Two of my adversarial probes failed on the first run and both were my
   construction errors** — a PROE leak seeded against the wrong target, and a
   forbidden-field check that matched its own explanatory comment. Recorded in
   §21 rather than quietly fixed.

**P1's weakness is not fixable with the information P4 was allowed to use.** The
residual in team volume is game script — how the game actually unfolds — and the
only pregame proxy for that is the market, which this project forbids and I did
not touch.

## 24. Unresolved data debts

| debt | state |
|---|---|
| game-script proxy without market data | **open, and this is the binding constraint** |
| observed weather has no forecast analogue | **open** — `temp`/`wind` remain forbidden |
| nflfastR `xpass`/`pass_oe` fitting window undocumented | **open** — worked around by rebuilding |
| actual play-caller identity (vs head coach) | **open** — only `home_coach`/`away_coach` exist |
| offensive coordinator identity | **open** — not in any captured source |
| coach field is a final-file value | **open** — same R1 caveat as the injury rows |
| (carried) `PLAYER_GSIS_UNMAPPED`, 2025 injury vintage, intraweek practice, zero-history cohort | unchanged |

## 25. Files and report path

```
A  nfl/research/p4/predeclaration_p4.md      written before any model was fitted
A  nfl/research/p4/build_team_panel.py       5,278 team-games, 332,906 play states
A  nfl/research/p4/p4lib.py                  baselines, ridge, logistic, bootstrap
A  nfl/research/p4/run_proe.py               xPass reconstruction + reliability
A  nfl/research/p4/run_p4.py                 Q1-Q5, ablations, subgroups
A  nfl/research/p4/run_p4_adversarial.py     26 probes + 2 guard-deletion proofs
A  nfl/research/p4/*.json, *.log             every metric and run log
A  TASK_REPORT_2026-09-07_P4.md              this file
```

Report path: `TASK_REPORT_2026-09-07_P4.md`, repository root.

## 26. Recommendation for the next research question only

**The next question is not another team-volume model. It is whether the
opportunity system can be made useful *given* that the pie size is
unforecastable.**

P1–P3 forecast each player's *share* reasonably well (snap share r ≈ 0.78
conditional). P4 shows the *total* is close to noise (r ≈ 0.10–0.17). A player's
absolute opportunity is share × total, so the error in any absolute projection
is now known to be dominated by a term we cannot forecast.

**The single next question: does a share-based projection, with team volume
deliberately left as a wide distribution rather than a point estimate, produce
better-calibrated player opportunity intervals than one that pretends to know
the total?**

That is answerable with what we already have, needs no new acquisition, and
turns P4's negative result into a design decision rather than a dead end.

**What I would not do next:** a bigger team-volume model, boosted trees on these
features, or any route to game script that runs through the market.

---

## Governance

Quarantined historical research. Nothing is promoted for having improved a
retrospective metric and no promotion is requested. **G0A remains 11/12**, Item 1
PARTIAL / PENDING REAL EVENT, NFL-1 unexecuted. The T−90 capture track was not
modified. 2026 outcomes were not consumed and no frozen 2026 artifact was
touched. No fantasy points, no touchdowns, no efficiency modelling, no joint
simulator, no sportsbook data, no DFS, no lineup optimization. No wager is
recommended or discussed.
