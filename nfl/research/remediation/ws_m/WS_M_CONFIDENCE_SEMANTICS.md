# WS-M — What "confidence" is allowed to mean, and how each part of it would be scored

**CODE CHANGED: NO.** Nothing outside `nfl/research/remediation/ws_m/` was
written. `nfl/product/confidence.py`, `render.py`, `daily_board.py` and
everything under `nfl/production/` were opened read-only. No suite was run. No
sportsbook file was opened, and no price appears anywhere in this design — a
price is an external comparison and never an input to a confidence measure.

Repo `/home/user/nfl`, branch `claude/nfl-greenfield-architecture-stsxmk`,
HEAD `837d52f`. Interpreter `python3.12`. Evidence run
`nfl/research/live/2026_01_DAL_NYG/FORENSIC_CORRECTED_RESEARCH/4b186a21b83a49ec/`
(8,000 draws, 36 board players). Every player addressed by `gsis_id` through
`Forecast.row_index()`, which reads the artifact's own `draws_ref.row`. No row
taken positionally. Reproduction: `ws_m_probe.py` in this directory.

**This document specifies semantics and validation. It proposes no replacement
formula and asks for no product edit.** Section 9 recommends that no product
change be made until Wave 1 lands, and says why in numbers.

---

## 0. Why the denominator is not the bug worth fixing first

`_role()` divides by a game-wide pool while its docstring says own-team
(`confidence.py:122` against `:127`/`:143`), and κ_QB = 0.8 / κ_skill = 0.25
are constants dimensioned for the denominator the docstring describes. WS06
confirmed all of that and it is not re-derived here.

Changing the denominator would produce a differently-wrong number. The field
has no estimand. Nothing in the repository states what quantity
`role_certainty` is an estimate *of*, so there is no statement that could be
checked, no sample on which it could be checked, and no result that would
count as it failing. `confidence.py:1-13` describes a *purpose* ("how much the
model and its inputs can be relied on"); a purpose is not an estimand.

The test that matters: **name the event or quantity, say what a reader may
conclude, and say what measurement would show the number was wrong.** Every
concept below is specified in that order, and any concept that cannot complete
the third clause is classified as a gate or an annotation, never as a score.

---

## 1. The separated concepts

Seven concepts are currently entangled. They differ in *what they are about*
(the information set, the forecast, or the software), in *what varies them*
(run, team, position, player), and in *whether an outcome can contradict them*.

| # | Concept | Estimand — the quantity it is an estimate of | Varies by | Refutable by an outcome? | Class |
|---|---|---|---|---|---|
| **C1** | **Input completeness** | Fraction of the source families this run *declares required* that arrived and passed validation at the run's own cutoff | run | **No** — it is an audit fact about files | **GATE** |
| **C2** | **Status certainty** | P(this player's gameday availability designation is both known and current as of the cutoff) | team | **Partly** — the designation's later state is observable, the player's outcome is not the same event | **GATE + annotation** |
| **C3** | **Role uncertainty** | Dispersion of the player's share of **his own team's** opportunity pool, decomposed into presence and allocation (§4) | player | **Yes** — realised own-team share is observed | **SCORE** |
| **C4** | **Distributional uncertainty** | Width of the predictive distribution of the player's own primary metric, on its own scale | player | **Yes** — via coverage and PIT | **SCORE** |
| **C5** | **Model calibration confidence** | For this layer/metric, does a stated probability match the realised frequency? | layer × metric | **Yes — it is defined by outcomes** | **SCORE (absent today)** |
| **C6** | **Data freshness** | Movement in the published number under the next-oldest admissible vintage of each governing capture | run × team × family | **No** — it is a sensitivity, not a forecast | **ANNOTATION** |
| **C7** | **Structural / model-health confidence** | Whether the layers serving this player ran, at what declared status, and whether an accepted audit names a defect in kind | position × layer | **No** — it is a statement about the software | **GATE** |

### What a reader is entitled to conclude from each

* **C1 high** — the files this run said it needed are on disk and parsed. *Not*
  that they are the right files, that they are fresh (that is C6), or that the
  model using them works (C5). Measured in the evidence run: `input_completeness
  = 1.0` for all 36 players, from `len(source_captures) = 7 >= 5`. **It carries
  no player-level information and cannot rank anything.**
* **C2 high** — a game-designation report exists, is chronology-valid, and the
  clock that selected it resolved. *Not* that the player will play.
  Measured: `0.85` for all 36 players, both teams. **Team-constant; carries no
  player-level information.**
* **C3 low** — the model does not know how much of his team's work this player
  takes. This is the one concept that answers "is his role settled".
* **C4 narrow** — conditional on the role being what the model thinks, the
  metric is tightly determined. *Not* that the projection will be close; a
  narrow distribution that is centred wrong misses by more, not less. That is
  C5's question, not C4's.
* **C5** — and **only** C5 — licenses "expect a smaller miss". It is the sole
  concept on the list whose truth conditions are stated in terms of realised
  outcomes. It does not exist in the product today. WS16 classifies the
  relevant layers `INSUFFICIENT_EVIDENCE`, and §8 below shows the joinable
  sample is presently **zero rows**.
* **C6** — how much the published number would move if the pipeline had read
  the previous admissible capture instead. WS04 #14 measured exactly this and
  found `p_app` mean moving 0.7585 → 0.7017 across four clocks on one game.
  An age in hours is not this quantity and must not be published as though it
  were.
* **C7 fail** — the projection should not be published for this player at all.

---

## 2. Which of these may be combined, and which may not

The current field is `(1/5)·(C1 + C3 + C4 + C2 + C7)` (`confidence.py:104`,
`WEIGHTS` at `:27`). Four separate reasons that arithmetic is not available.

**2a. Lying in [0, 1] is not commensurability.** C1 is a fraction of files.
C2 is an ordinal readiness state mapped to reals by an undeclared table
(`confidence.py:154-165`: 1.0 / 0.85 / 0.4 / 0.15 / 0.0, none of them
estimated). C3 would be a normalised variance ratio. C4 is a ratio of a
quantile spread to a location. C7 is a fraction of layers. Adding a fraction
of files to a variance ratio produces a number whose units are nothing. The
shared interval is a coincidence of construction, and it is precisely the
coincidence that made the average look reasonable.

**2b. A gate averaged with a score becomes a discount.** C1, C2 and C7 are
gates: they answer "may this be published", which has no intermediate value
that means anything. Averaged in, they instead *subtract a fixed amount* and
leave the row on the board. This is the mechanism behind WS06 F13, which
reproduces here exactly: Joe Milton III has `P(dropbacks = 0) = 1.0000` in all
8,000 draws, role 0.0000, width 0.0000, and publishes **0.5427** — above eight
players with real distributions, because C1 + C2 + C7 contribute
(1.0 + 0.85 + 0.8636)/5 = 0.5427 regardless of anything he does. The constant
floor is 0.5427 for QB and 0.5200 for RB/WR/TE. Six players in this game have
identically-zero distributions and all six publish at the floor.

**2c. C3 and C4 are not independent addends; C3 propagates into C4.** Role
uncertainty is *one of the sources* of the metric's predictive width. A player
whose share is a coin flip has, for that reason, a wide metric distribution.
Adding the two gives partial weight to the same uncertainty twice, in a way
that depends on how much of the width the role channel supplied — which
varies by player and is not constant across the board. They may be published
side by side. They may not be averaged.

**2d. C5 is a multiplier on the others' meaning, not a term beside them.**
"The role is settled and the interval is narrow" means something very
different in a layer whose intervals are known to cover at nominal than in one
that has never been scored. C5 conditions the reading of C3 and C4; it does
not add to them.

### The combination rule this yields

```
C7 gate  -> PUBLISH or REFUSE (named refusal code, never a number)
C1, C2   -> PUBLISH or REFUSE, plus a printed provenance line
C6       -> printed sensitivity, per governing family, never summed
C3, C4   -> two numbers, published separately, never averaged with each other
C5       -> per layer/metric, printed beside C3 and C4 as what they are worth
```

**No scalar.** If one ordering is nonetheless wanted, it must be an ordering
*within* a single concept (rank by C3 alone, or by C4 alone), declared as
such in the column header. The measured cost of not doing this is in WS06 F14
and reproduces here: Tyrone Tracy Jr. (depth chart RB3) outranks Cam Skattebo
(RB1) on the published scalar, 0.7906 to 0.7741, and §5c below shows the two
concepts disagree about them in opposite directions.

---

## 3. Role uncertainty: what the model actually generates

The measure should follow the mechanism, and the mechanism is two-stage. For
non-QB, `football_engine.py:314` calls `layers.appearance`, which draws an
independent Bernoulli per player (`layers.py:222`), and the survivors are then
allocated on a simplex (`p4c_lib.py:107-139`). WS04 #3 measured that the
appearance Bernoulli supplies 93.7–103.2% of `P(X = 0)` for high-share players
and 0.8–5.2% for deep bench players.

So a player's own-team share `s = x_i / Σ_{j ∈ own team} x_j` carries two
different uncertainties:

* **presence** — whether he is on the field at all: `P(x_i = 0)`;
* **allocation** — given that he is, how much of the team's work he takes:
  the distribution of `s | x_i > 0`.

**These are different questions with different answers, and collapsing them is
the error one level up from the denominator bug.** Measured on this run:

| Player | Depth | Metric | published score | published role | **P(absent)** | **E[s \| present]** | **sd(s \| present)** |
|---|---|---|--:|--:|--:|--:|--:|
| Jaxson Dart | QB1 | qb/db | 0.7553 | 0.4976 | **0.0696** | 0.9581 | 0.1275 |
| Dak Prescott | QB1 | qb/db | 0.6177 | 0.3747 | **0.4273** | **0.9458** | 0.1781 |
| Sam Howell | QB2 | qb/db | 0.6061 | 0.3171 | **0.4850** | **0.8899** | 0.2763 |
| Javonte Williams | RB1 | rushing/carries | 0.7200 | **1.0000** | **0.3365** | 0.7656 | 0.1909 |
| Cam Skattebo | RB1 | rushing/carries | 0.7741 | 0.7896 | 0.0453 | 0.3789 | 0.1642 |
| Tyrone Tracy Jr. | RB3 | rushing/carries | **0.7906** | 0.8637 | 0.1075 | **0.4438** | 0.1436 |
| Hunter Luepke | FB1 | rushing/carries | 0.6288 | 0.2969 | **0.5256** | 0.3222 | 0.3211 |
| CeeDee Lamb | WR1 | receiving/targets | 0.6880 | 0.5067 | 0.1285 | 0.2560 | 0.1218 |

Read the Prescott row. WS06 reported his per-draw own-team share as sd 0.4869,
[p10, p90] = [0.000, 1.000], and called it maximal role uncertainty. The split
says something more useful and less alarming: **conditional on playing he is
unambiguously the starter** (0.9458, sd 0.178), and essentially all of the
0.4869 is presence uncertainty. "We do not know whether he plays" and "we do
not know how the work is split when he does" are different statements to put
in front of a reader, and only the first is true of him.

And the Javonte Williams row is the current field's sharpest failure. He is the
only player in the game with `role_certainty = 1.0000` — the maximum the scale
admits — while carrying a **33.7% chance of recording no carry at all**.

---

## 4. Own-team denominators, and one property that is definitional rather than measured

Every measure specified below uses the player's own team as the denominator.
**The denominator rule, stated once.** A player's own *opportunity metric*
follows `_role()`'s branching — a back's role is his carries, not his targets.
His *denominator* is every team-mate carrying a row for that layer/key, backs
included. These are different questions and conflating them undercounts a
receiving pool by the running backs' targets: on this run it moves CeeDee
Lamb's own-team share from 0.2231 to 0.2580. The wide reading is used
throughout, and it reconciles with the own-team shares WS06 computed
independently (Lamb 0.2231 here against 0.2234 there; Dart 0.8914 exactly;
Skattebo 0.3618 against 0.3625).

Using the own team at all removes the opponent contamination WS06 F5 recorded. Reproduced here
by rescaling the stored DAL dropback rows and recomputing Jaxson Dart:

| DAL volume | game-pool share (published basis) | own-team share | P(absent) | sd(own-team share) |
|---|--:|--:|--:|--:|
| ×0.70 | 0.4773 | 0.8914 | 0.0696 | 0.2731 |
| ×0.85 | 0.4341 | 0.8914 | 0.0696 | 0.2731 |
| ×1.00 | 0.3981 | 0.8914 | 0.0696 | 0.2731 |
| ×1.15 | 0.3676 | 0.8914 | 0.0696 | 0.2731 |
| ×1.30 | 0.3414 | 0.8914 | 0.0696 | 0.2731 |

The same perturbation on the Dallas lead quarterback, varying the Giants' volume: game-pool share 0.3461 → 0.2643 across ×0.70 → ×1.30, own-team share fixed at 0.5416, `P(absent)` fixed at 0.4273, `sd(s)` fixed at 0.4869.

**State the status of this honestly.** Invariance of an own-team statistic to a
post-hoc rescaling of the other team's rows is **definitional, not empirical** —
those rows do not enter the arithmetic, so they cannot move it. What the table
establishes is the size of the contamination in the *current* basis (0.4773 →
0.3414, a 28.4% relative swing driven entirely by Dallas), not a property of
the proposed one. A genuinely empirical opponent-invariance claim would require
re-running the *forecast* under a different opponent, which is a simulation
experiment and is not attempted here.

**A definitional hazard that must be handled by a named state.** The own-team
denominator is zero in some draws. In this run the modelled DAL rushing pool is
zero in **7.25%** of the 8,000 draws (`share_defined = 0.9275`). The share is
undefined there. It must not be imputed, dropped silently, or filled with zero;
it requires a reported fraction and a named code, in the same spirit as
`dispersion()` returning `None` at `iqr <= 0` — the one guard WS06 found
working (F15).

---

## 5. Candidate role-uncertainty measures

Notation: `x` the player's draws on his opportunity metric; `s` his per-draw
own-team share where defined; `w̄` the vector of team-mates' mean shares.

### 5a. The property table

| Measure | What it measures | Degenerate (`x ≡ 0`) | Zero-inflated | Opponent-invariant | Scale-free | Entangled with mean? |
|---|---|---|---|---|---|---|
| **P(absent)** = `(x <= 0).mean()` | Presence: probability the player records no opportunity | **1.0 — exactly the right answer**, and it is the only candidate that is fully informative on a degenerate row | it *is* the zero-inflation parameter | yes (definitional) | yes, already a probability | **yes**, ρ = −0.848 vs mean share; unavoidable and acceptable, because presence risk genuinely *is* lower for larger-share players |
| **sd(s)**, unconditional | Total share dispersion | undefined (`s` undefined) | conflates presence and allocation | yes (definitional) | yes | **yes, severely: ρ = +0.941.** See 5b |
| **IQR(s)** | Robust share spread | undefined | **collapses to 0** whenever >25% of mass is at zero — the same trap as the current `distribution_width`. Measured: NYG QB2 has `IQR(s) = 0.0000` with `P(absent) = 0.7519` | yes | yes | yes, ρ = +0.848 |
| **Var(s) / (μ(1−μ))** | Share dispersion as a fraction of the maximum attainable at that mean | undefined → must route to a named state | does not collapse; NYG QB2 scores 0.5506 where IQR gives 0 | yes | yes | **least entangled scalar measured: ρ = +0.305.** But saturates at 1 for *any* two-point share, so a 7% absence risk (Dart, 0.7703) is not well separated from a coin flip (Prescott, 0.9551) |
| **E[s \| present], sd(s \| present)** | Allocation, with presence removed | undefined, `n_cond = 0` → named state | separated by construction | yes | yes | sd ρ = +0.878, CV ρ = −0.676 vs conditional mean — **entangled in opposite directions**; see 5b |
| **Normalised entropy of `s`** (binned) | Spread of the share distribution | 0.0 — same value as a perfectly settled role, which is the wrong collapse | sees it | yes | partly: binning is a chosen constant | yes, ρ = +0.806 |
| **Bimodality coefficient of `s`** | Two-regime shape | undefined | flags it | yes | yes | **no: ρ = −0.150** — the only magnitude-free shape statistic measured. But it reads 0.9435 for Dart (7% absence) and 0.9688 for Prescott (43%), and 0.8359 for a deep bench WR: in practice a zero-mass detector with extra steps, not a discriminator |
| **Team HHI / effective number of opportunity-takers** (`exp H(w̄)`) | Team-level: how many players share this pool | unaffected by one zero row | robust | yes | yes | not a player-level measure at all |
| **Normalised MI between draw and taker identity** | Team-level: how much of the allocation spread is *uncertainty about who*, rather than a genuine split | robust | robust | yes | yes | **no** — see 5c |

### 5b. The finding that changes the WS06 recommendation

WS06 §5 named "(P(x = 0), per-draw own-team share sd)" as its sharpest
separator. The first half survives. **The second half does not, and it fails
for exactly the reason this workstream exists.**

A share lies in [0, 1], so `Var(s) <= μ(1−μ)`. Almost every player on a board
has μ well below 0.5. The standard deviation of a bounded variable is therefore
mechanically increasing in its mean over the range where boards live, and
`sd(s)` reproduces the defect it was proposed to fix:

```
Spearman(candidate, mean own-team share), n = 36 board players
  sd(s)                    +0.9411      <- WS06's proposed separator
  published role_certainty +0.9547      <- the field it was proposed to replace
  published score          +0.8934
  IQR(s)                   +0.8476
  normalised entropy of s  +0.8059
  Var(s)/(mu(1-mu))        +0.3050
  bimodality coeff of s    -0.1497
```

`sd(s)` is 0.941-correlated with the mean; the field it replaces is 0.955. That
is not a repair, it is the same quantity with a different label.

**Generalise it, because the specific fix is not the lesson.** *Every* scalar
dispersion statistic of a bounded share is entangled with its mean in one
direction or the other — `sd` and `Var` upward, `CV` downward (ρ = −0.676
against the conditional mean), and normalising by `μ(1−μ)` reduces the
entanglement to +0.305 without removing it. There is no clever ratio that
escapes this. The two available responses are:

1. **Publish the pair, not the scalar** — a location and a dispersion, so the
   reader can see that Prescott's 0.4869 is presence and Luepke's 0.3211 is
   allocation; or
2. **Score against a mean-matched reference** — state the dispersion relative
   to what a declared reference distribution at the same mean would give, which
   is what `Var/(μ(1−μ))` is, with its saturation limitation named.

Response 1 is what this specification recommends. Response 2 is admissible as
an *auxiliary* column, never as the ordering.

### 5c. Two team-level entropies that disagree, and only one of them is asking the right question

An obvious candidate for "is the role settled" is the entropy of the allocation
across team-mates. There are two ways to compute it and they give opposite
verdicts on the clearest case in this game.

| Team / metric | H(E[w]) across draws | E[H(w)] within a draw | MI = difference | **MI / H(E[w])** | eff. takers (marginal) | eff. takers (within-draw) |
|---|--:|--:|--:|--:|--:|--:|
| **DAL qb/db** | 0.6897 | 0.0354 | 0.6543 | **0.9487** | 1.993 | **1.036** |
| **NYG qb/db** | 0.4087 | 0.1336 | 0.2751 | 0.6731 | 1.505 | 1.187 |
| DAL rushing/carries | 0.9853 | 0.3957 | 0.5896 | 0.5984 | 2.678 | 1.485 |
| NYG rushing/carries | 1.1986 | 0.9392 | 0.2594 | 0.2164 | 3.315 | 2.558 |
| DAL receiving/targets | 2.1762 | 1.5948 | 0.5814 | 0.2672 | 8.812 | 4.927 |
| NYG receiving/targets | 2.2539 | 1.8105 | 0.4434 | 0.1967 | 9.525 | 6.114 |

The Dallas quarterback room is the most uncertain role on the board: Prescott
and Howell have per-draw dropback correlation −0.924 (WS06) and absence
probabilities 0.4273 and 0.4850. **The within-draw entropy rates it as the most
settled group in the game** — effective takers 1.036, *more* concentrated than
the Giants' 1.187 — because within any single draw exactly one quarterback
plays. It is measuring concentration on the wrong axis, and would publish the
coin flip as certainty.

The marginal entropy gets the ordering right (1.993 vs 1.505), and the
difference between the two is the mutual information between the draw and the
identity of the opportunity-taker: **normalised MI = 0.9487 for Dallas**, i.e.
95% of the allocation spread in that room is uncertainty about *who*, against
0.27 and 0.20 for the two receiving groups, where the spread is a genuine committee.

This is a named, non-ad-hoc quantity that answers the exact question the label
"role certainty" claims to answer, at the level the question is actually about
(the group, not the individual). **Per-draw allocation entropy is rejected as a
candidate measure on this evidence.**

### 5d. The recommended measurement set, stated as a proposal and nothing more

Not a product change and not adopted here. Per player, per opportunity metric,
own-team denominator:

1. `P(absent)` — presence.
2. `E[s | present]` and `sd(s | present)` — allocation, as a pair.
3. `share_defined` — the fraction of draws in which the denominator is positive.
4. A named state (`ROLE_DEGENERATE`, `ROLE_UNDEFINED`) whenever 1–3 do not
   exist, published as the state and not as a number.

Per team-metric group: `eff. takers (marginal)` and `normalised MI`. Auxiliary
only: `Var(s)/(μ(1−μ))`, with its saturation stated in the column note.

**Bimodality coefficient, per-draw allocation entropy, IQR of the share, and
unconditional `sd(s)` are each rejected above, with the measurement that
rejects them.**

---

## 6. Distributional uncertainty (C4), briefly

Not this workstream's focus, but it must be separated from C3 rather than left
entangled. Two properties are already established and are not re-derived:
`IQR/median` is unstable when zero mass pushes the median toward zero (WS06
F10: Howell's absolute IQR 237.00 is *smaller* than Prescott's 270.00, yet his
`IQR/median` is 25.947 against 1.731), and the resulting score is floored at
zero for 21 of 36 players with zero players reaching 1.0 (F11).

The semantic requirement is the same as for C3: **a degenerate distribution is
not a narrow one**, and the two must reach a reader as different states rather
than as the same number. The existing `dispersion() -> None` guard
(`confidence.py:49-50`) already encodes that, and it is the one part of the
current module that is doing its job.

---

## 7. Validation, per measure

A confidence field that is never scored against outcomes is a decoration.
**Every measure below carries a predeclared test, a cluster unit, and a floor;
a measure that cannot name all three is not published.** The repository already
declares the cluster unit for exactly this reason: `evaluator.py` sets
`CLUSTER_UNIT = 'game'` and `MIN_GAMES_FOR_CANDIDATE = 4`, with the docstring
"player-metrics inside one game are not independent observations of anything".
Everything here inherits that and never resamples rows.

**Clustering, stated once and applying to every row below.** The resampling
unit is the **game**. Block bootstrap over games, 2,000 resamples, and every
interval quoted from the game-block distribution. Player-metric rows within a
game are not independent — attempts, completions and yards for one passer are
near-deterministic functions of each other, and both teams share one game
script. Additionally, `P(absent)` rows within a team share the readiness state
and, after the Wave 1 repair, may share an availability latent; where a claim
is about presence the secondary cluster is **team-game** and the reported
interval is the wider of the two.

| Measure | Predeclared test | Sample / floor | Cluster | What would show it is wrong |
|---|---|---|---|---|
| **`P(absent)`** | It is a probability forecast of a binary event — did the player record ≥1 opportunity on the metric. Brier score against a base-rate reference; reliability curve in 5 predeclared bins [0,.1,.3,.5,.7,1]; log score | **≥ 100 games** for a 5-bin curve with ≥ 30 player-rows per bin; below that, publish the count and refuse the curve | game, and team-game for the interval | A bin whose realised rate sits outside its game-block interval; Brier not beating a depth-chart-only reference |
| **`E[s \| present]`, `sd(s \| present)`** | PIT of the realised own-team share against the predicted conditional share distribution, on games where the player appeared. Uniformity assessed on the PIT histogram with game-block resampling | **≥ 60 games** with ≥ 200 appeared player-rows | game | A PIT histogram whose deviation from uniform exceeds the game-block band; systematic U or ∩ shape |
| **Does role uncertainty predict a worse projection?** — the claim the field implicitly makes | Rank correlation between the role-uncertainty pair and scale-normalised CRPS on the primary metric, game-block bootstrapped. Predeclare the direction: higher uncertainty → higher normalised CRPS | **≥ 60 games**; report the interval, never a point | game | An interval covering zero, or the opposite sign. **This is the test that decides whether the concept earns publication at all** |
| **`normalised MI`, `eff. takers`** | Group-level: does a high-MI group show a larger realised identity surprise — log score of the realised top-taker identity against the predicted `w̄`? | **≥ 40 team-game groups per position pool** | game | Predicted `w̄` not beating a uniform-over-listed reference on log score |
| **`share_defined`** | Not scored against outcomes — it is an audit count of the draws. Reported, never ranked | n/a | n/a | n/a |
| **C4 distributional width** | Interval coverage and PIT **conditional on the width bin**. Predeclare an equivalence margin on coverage — proposed **±5 percentage points** at each of 50/80/90/95 — and run a **TOST** per bin. Winkler interval score as the proper-scoring companion | **≥ 60 games**, ≥ 150 rows per width bin | game | Narrow-bin coverage failing the TOST, i.e. narrow intervals bought by under-coverage |
| **C5 calibration confidence** | PIT uniformity, coverage, CRPS and log score per layer × metric, exactly as `evaluator.py` already computes them, accumulated | **≥ 4 games** to raise a refinement candidate (the repo's own declared floor); **≥ 40** before a per-layer calibration statement | game | Its own PIT and coverage |
| **C6 freshness** | Rerun with the next-oldest admissible vintage per family and publish the movement, as WS04 #14 did (`p_app` mean 0.7585 → 0.7017 over four clocks). Not scored against outcomes | every run, per governing family | n/a — it is a sensitivity | Nothing; it is not a forecast. Publishing an *age* in place of the movement is the defect to avoid |
| **C1, C2, C7** | **Not scored.** They are audit facts and gates. A gate is validated by checking it fires when its condition holds, which is a test-suite matter, not a ledger matter | n/a | n/a | The gate failing to fire on a constructed case |

**Language discipline, since this section is where it usually slips.** No
measure above may be reported as "unbiased", "stable", "closed" or "correct".
Where adequacy is the claim, the equivalence margin is predeclared and a TOST
is run; failing to reject a null is not evidence of adequacy and is reported as
"did not reject", with the sample.

**Two predeclarations that must be written down before any data is seen**, or
the tests above are not confirmatory: the direction of each expected effect,
and the bin edges. Both are stated in the table. They are stated *now*, before
a validation sample exists, which is the only time that statement is worth
anything.

---

## 8. The precondition everything in §7 rests on, and it is not met

**The confidence field is not stored in a form that can be joined to an
outcome, and it is not reconstructible from the seal.**

* `nfl/product/EVALUATION_LEDGER.jsonl` holds **33 rows**: one game
  (`2026_01_NE_SEA`), three players, eleven `qb/*` metrics each. Its 25 keys
  include `crps`, `pit`, `coverage`, `miss_class` — and **no confidence field
  of any kind**.
* The run those rows scored, `f5830230e5416b55`, resolves to
  `nfl/research/shadow/g1_ne_sea/`, which carries `forecast_artifact.json`,
  `player_draws.npz.gz`, `SEAL_SHA256.txt` and `EVALUATION.json` — **and no
  `board.json`**. The confidence values for the only graded game in the
  repository were never written down.
* They cannot be recovered by recomputation either: `score_player()` requires
  `readiness`, and the sealed artifact has **no `readiness` key** (its 28 keys
  are listed in `forecast_artifact.json`). `status_certainty` is therefore not
  reconstructible from the seal, and reconstructing a pregame field after the
  outcome is known is what the seal discipline in `evaluator.py:1-8` exists to
  prevent.

**The joinable sample for validating any confidence measure today is zero
rows.** Not small — zero. Every number in §7 describes an experiment that
cannot start until the field is sealed with the forecast.

The change that unblocks it is a **storage** change, not a design change: write
the confidence parts, their input values, and the readiness state into the
sealed artifact so that a forward ledger accumulates joinable rows from the
next run onward. That belongs to the governance transport (WS-D) and is named
here as a dependency, not attempted.

---

## 9. Sequencing against Wave 1 — recommendation

**Recommendation: do not redesign the confidence field until the Wave 1
blockers land.** Five reasons, four of them numeric.

1. **The presence component is a function of a leaking model.** WS04 #7
   established that `appearance_r8`'s V1 feature block carries the label:
   training rows with V1 present have appearance rate 0.7106 (n = 53,381) and
   rows with V1 absent have **0.0000** (n = 6,158), while at serve V1 is
   present for 30/30, 24/24 and 28/28 players. In-sample week-1 mean predicted
   0.5438 against actual 0.5371; served 2026 week-1 mean **0.7996**, cold start
   **0.9920**. WS04 #3 then established that this Bernoulli supplies 93.7–103.2%
   of `P(X = 0)` for high-share players. **Every `P(absent)` in §3 — Prescott
   0.4273, Williams 0.3365, Dart 0.0696 — is an output of that model.** The
   repair moves them, in a direction that is knowable in sign for the
   cold-start and high-`cm_carried` cells and unknown in magnitude. Calibrating
   a presence measure now means calibrating against leaked numbers.
2. **The QB role denominator is one of the arrays with impossible states.**
   `WAVE0_BASELINE.json` records 5,278 `cmp > att` cells, 731 `ptd > cmp` and
   11,616 `pyds ≠ 0 with cmp = 0` across 838,000 QB cells, in 33 of 101 runs.
   The QB role measure divides by `qb__db`. A repair to the QB layer moves the
   exact array §3's QB rows are computed from.
3. **Two of the seven concepts are defined against an unclocked selector.**
   WS12 rates injury reports **PROVEN_LEAKING** (L1, L2): the gate cuts at
   `min(written_at, kickoff)` while the feed the model eats
   (`layers.py:145 → readiness.latest_injuries_rows`) applies no bound and
   silently takes the newest capture on disk. C2 (status certainty) and C6
   (freshness) are *about* that selector. Specifying a measure of a quantity
   whose selection rule is about to change is specifying the wrong quantity.
4. **There is no sample to judge a redesign on.** §8: zero joinable rows. A
   design chosen now would be selected by inspecting one game — the same
   36-player run WS06 used and this document uses. That is exploratory work and
   would have to be labelled as such in every artifact that quoted it. The
   honest version of "which measure is better" cannot be answered until the
   storage change in §8 has produced a forward sample.
5. **The storage change rides on the governance transport (WS-D).** The
   precondition is owned elsewhere and is already sequenced ahead.

### What does not have to wait

* **This document.** The semantics are structural. §2's combination rule, §5b's
  entanglement result and §5c's entropy rejection are properties of the
  arithmetic, not of the current numbers, and Wave 1 will not move them.
* **The storage requirement in §8**, as a requirement placed on WS-D's
  transport rather than as an edit here.
* **Suppression or relabelling of the published scalar**, if the coordinator
  wants a product action before Wave 1. Its justification is structural — a
  constant floor of 0.5427 publishing an all-zero distribution above eight real
  players (§2b), a κ dimensioned for a denominator the code does not use, a
  scale no quarterback can reach — and none of those arguments depends on a
  number Wave 1 will move. **Suppression is available now; redesign is not.**

### What would change this recommendation

If Wave 1 slips far enough that a forward validation sample would otherwise not
begin accumulating at all, the §8 storage change should be split out and taken
early on its own, because it is additive, changes no projection, and every
experiment in §7 is blocked behind it. That is a coordinator decision, and it
is the only part of this workstream with a real cost to delay.

---

## 10. Reproduction

`nfl/research/remediation/ws_m/ws_m_probe.py`, `python3.12`, imports repository
modules read-only and writes nothing. It regenerates §3, §4, §5b and §5c from
the sealed run named at the top. Draw rows are resolved through
`Forecast.row_index()` and the manifest's `row_ids`; no positional indexing is
used.

**CODE CHANGED: NO.**
