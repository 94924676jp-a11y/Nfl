# OAS1 — Opponent-Adjusted Team Strength V1

**Pre-registered before implementation. Nothing built.** This is a **build, not
an integration**: opponent adjustment, matchup strength and OL/DL were verified
absent from **research as well as production**. There is no asset to wire up.

## 1. What exists, verified

| item | state |
|---|---|
| any opponent-strength term in `nfl/production/**` | **ABSENT** — zero hits for `opponent_adj`, `def_adj`, `sos`, `strength_of` |
| any in `nfl/research/**` | **ABSENT** — same search, same result |
| `epa` / `success_rate` as exact tokens in production | **ABSENT** |
| historical play-by-play | `nfl/research/postgame/pbp_*.csv.gz`, with `.provenance.json` carrying `source_url`, `retrieved_at`, `sha256`, `n_bytes` and the game list |
| 2026 play-by-play | 10 games / 20 clubs, retrieved 2026-09-14T00:25:56Z |

**Data availability is the first gate, and it is not yet passed.** Before any
estimator is fitted, the multi-season play-by-play corpus must be shown to carry
`epa`, `posteam`, `defteam`, `play_type`, `week`, `season` and a usable
pass/rush classification for **every** season in the training window, with
per-season row counts and provenance recorded. **If the corpus is incomplete for
a season, that season is excluded and named — never partially used.**

## 2. The four unit strengths

`off_pass`, `off_rush`, `def_pass`, `def_rush` — one value per club per week,
each published **with its uncertainty**. A strength without an interval is not
usable by a downstream layer that has to propagate it.

## 3. Estimator

**Ridge regression on EPA/play**, pass and rush fitted **separately**, offense
and defense estimated **jointly** within each.

For each play `p` of type `t ∈ {pass, rush}`:

```
epa_p  =  mu_t  +  home_p * h_t  +  off_{t, posteam(p)}  +  def_{t, defteam(p)}  +  e_p
```

- **Identification.** Offense and defense enter additively and are not separately
  identified without a constraint. **Sum-to-zero within each family**:
  `sum_c off_{t,c} = 0` and `sum_c def_{t,c} = 0`. A strength is therefore a
  deviation from league average **by construction**, which is also what makes
  "opponent-adjusted" mean something.
- **`mu_t` and `h_t` are unpenalised.** Shrinking an intercept or a home effect
  toward zero shrinks the league mean, which is not the quantity ridge is there
  to regularise.
- **`lambda` is selected ONLY through forward chaining** — never by in-sample
  CV, never by a grid inspected against the final result. One `lambda` per unit
  type, selected on the chain, refitted within it.

## 4. Priors, blending and decay — all fitted, none chosen

- **Prior-season strength shrunk toward the league mean**, shrinkage weight
  **fitted** on the chain.
- **In-season blend** between the prior-season value and current-season
  evidence, weight a **fitted** function of observed plays, not a chosen
  constant.
- **Within-season decay** fitted **prospectively**.

**No coefficient in this model is chosen by hand.** Any number that cannot be
fitted on the chain or cited to a source is a silent constant and is a bug here.

## 5. The single-adjustment registry

> **A football effect may be opponent-adjusted exactly once.**

Asserted as an invariant, not a convention. Each downstream consumer declares
which unit strength it consumes and for which effect; a second adjustment of the
same effect is a **refusal**, not a warning.

This is the most likely way the architecture fails. Pace enters volume, unit
strength enters volume **and** efficiency, and a composite rating is tempting to
add as a third feature. **Double-counted adjustment shrinks predicted spread
toward the league mean — producing exactly the wide-and-similar distributions
already diagnosed — while every accounting check passes.**

Detection, beyond the registry: a synthetic test that **doubles one club's
strength** and checks the downstream response against the analytically expected
magnitude. A response larger than predicted means it was applied twice.

**No composite Elo on top of unit strength.** It may be tested as an
**alternative** candidate; it may never be added as another feature.

## 6. Baselines — built FIRST, deliberately

Building the comparator after the candidate invites motivated evaluation, so
the baselines are implemented and scored **before** OAS1 exists.

| baseline | why it is here |
|---|---|
| league prior | the floor. [Prior finding] a league prior beat every own-history team-volume baseline |
| prior-season strength | tests whether current-season data adds anything |
| rolling mean, last k | the naive incumbent |
| EWMA, half-life fitted **inside** the chain | the strongest simple recency model |
| **simple opponent-adjusted** — rolling mean plus one opponent unit term | **the decisive comparator.** If ridge cannot beat this, the complexity is unpaid for |

## 7. Evaluation protocol

- **Forward-chained by week.** For each season and each week `W` from a declared
  minimum: fit strictly before `W`, predict `W`, walk forward. **Every
  hyperparameter refitted inside the chain.** No random split.
- **Assert `max(training ordinal) < forecast ordinal`** — the same assertion as
  the freshness rule pointed the other way, and they should share one
  implementation.
- **Clustered intervals**, resampling **clusters** by game and separately by
  club, both reported, `R_BOOT = 2000`. Never resample player-games
  independently: teammates share a game, and an iid interval was measured
  threefold too narrow here.
- **Populations reported separately, never pooled into one headline:** all rows;
  established-role players; low-volume players; cold-start; and by position.
  Pooling lets a large easy stratum hide failure in the one that matters — the
  QB participation result gained +0.0128 overall while being −0.0027 in its own
  cell and +0.4747 in the sparse one.

## 8. Promotion gates — all must hold, forward-chained, out of sample

1. Beats **every** baseline in §6 on the primary proper score for its class
   (CRPS for count and continuous; Brier and log loss for binary).
2. The clustered 95% interval against the **strongest** baseline excludes zero.
   Beating the weakest is not evidence.
3. Interval coverage within a declared tolerance of nominal at **all four**
   levels.
4. **Sharpness at matched empirical coverage no worse than the strongest
   baseline.** This is what stops wide-and-similar distributions from being
   promoted on items 1–3 alone.
5. Calibration slope within a declared band of 1.
6. **Within-slate rank correlation exceeds the strongest baseline's**, clustered
   interval excluding zero. **This is the discrimination gate** and it is the
   one the current model would fail.
7. Every requirement holds in each reported population, or the failing
   population is named and the promotion scoped to exclude it.

**Complexity is not evidence.** A candidate that adds structure without
improving a proper score against the strongest baseline is rejected and the
negative result is preserved. **If a baseline wins, the baseline is production.**

## 9. Declared successor, not the first implementation

State-space / hierarchical Bayesian strength with a time-varying latent is the
successor. Ridge first because it is identifiable, cheap to forward-chain, and
its failure is interpretable.

## 10. What would make OAS1 wrong

- **The corpus lacks EPA or a usable pass/rush split for some season** — §1 is a
  gate, not a formality.
- **Sum-to-zero is the wrong identification** if a season's schedule is not
  connected enough to identify all 32 clubs jointly. Connectivity must be
  checked, not assumed.
- **EPA is itself a model output**, not an observation. Adjusting for opponent
  on a modelled target inherits that model's assumptions, and this
  pre-registration does not pretend otherwise.

**V2 NOT YET EARNED**
