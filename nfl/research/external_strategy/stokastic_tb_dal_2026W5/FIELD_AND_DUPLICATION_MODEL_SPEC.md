# Field and duplication model: specification (research track, SHADOW, nothing promoted)

**Status.** This is a design. Nothing in it is implemented, and nothing in it may enter lineup selection before the
bars in section 7 are met.

**Measurements.** Every number quoted from TB@DAL is a measurement on one slate. It shows the shape the model must
reproduce. It does not fit any parameter.

**Sources.**
- The plan this extends: `docs/NFL_SHOWDOWN_TOURNAMENT_PLAN_2026-10-09.md`, items T1 to T5.
- The TB@DAL field facts: `SUPPORT_ACTUAL_FIELD_STRUCTURE_TB_DAL.json` (owner-uploaded DK standings, our 190 entries
  excluded).

**Simulation queries.** The query tool (`SIMULATION_QUERY_CAPABILITY_SPEC`) is being built by another agent. This
spec only consumes world-level outputs.

## 0. Two simulations, kept apart

| | Football-outcome simulation (W) | Opponent-lineup simulation (F) |
|---|---|---|
| Question | What can happen on the field? | What will other entrants submit? |
| Code | `nfl/sim/` (`game.py`, `football_points.py`, `dst.py`) and `nfl/tools/proj_v1.py`, `showdown_draws.py` | `nfl/field/` only |
| Inputs | Football evidence. No market prices, no ownership. | DK pool and salaries, public projections (FC as a stand-in for what the field sees), news flags, contest metadata. Our projection may be a **declared** feature. |
| Output | 2,000 joint worlds of per-player stat lines and DK points | A population (or weighted universe) of legal lineups with copy counts |
| May read the other? | **Never.** `nfl/field/__init__.py` says "Nothing in this package may be read by a projection." | Reads no world outcome. A field is fixed before kickoff. |

**Where they meet.** The two meet only in the contest-evaluation layer, the planned `nfl/tools/showdown_ev.py`
(T4). There each field lineup and each of our lineups is scored in each world.

**Independence.** Because F is fixed before lock and W carries no ownership, the two are independent given the
pregame information. That independence is a design invariant. Test it by asserting by AST that `nfl/sim` and
`proj_v1` never import `nfl.field`.

## 1. What TB@DAL says a field model must reproduce (150-max, 236,900 non-owner entries)

| Property | Measured value |
|---|---|
| Distinct lineups | 23,645 (**4.1% of entries unique**; median entry shares its exact lineup with 42 others) |
| Entry share by its lineup's total copies | 1: 4.1%; 2-5: 8.8%; 6-20: 19.9%; 21-100: 40.5%; >100: 26.8% |
| Concentration | top 1 lineup 0.40% of entries; top 10 2.3%; top 100 11.8%; top 1,000 45.5% |
| Salary | p10 $48,000, median $49,500, p90 $50,000; mean $49,142 |
| Salary bands | **10.3% at exactly $50,000**, 41.5% at $49,500-49,900, 21.6% at $49,000-49,400, 17.1% at $48,000-48,900, 9.5% below $48,000 |
| Duplication by salary band (mean other copies per entry) | $50,000: 112; $49,500-49,900: 124; $49,000-49,400: 62; $48,000-48,900: 31; below $48,000: **9.8** |
| Team split (TB-DAL) | 1-5 22.0%, 2-4 35.4%, 3-3 29.4%, 4-2 11.5%, 5-1 1.7% |
| Team split of the 100 most-duplicated lineups | 2-4 42, 1-5 33, 3-3 23, 4-2 2 |
| Captains | Lamb 17.1, Dak 16.4, Javonte 15.1, Pickens 12.0, Daniels 10.2, Irving 5.5 |
| Captain team | DAL 73.0%, TB 27.0% |
| Construction | both QBs 40.6%; a kicker 45.5%; a DST 25.8%; at least 2 of {Lamb, Dak, Javonte, Pickens} 91% |
| Entrant mix | 11,282 users; **74% of entries come from users with ≥100 entries**; 1.7% from single-entry users |
| Within-user identical entries | 3.2% of entries. Duplication is overwhelmingly **across** users (shared tools), not repeat entries. |
| 20-max contests | 47.3k entries each; 10-11% unique; median 12 copies; within-user duplication 5.5-7.6% |

### The "most-duped" lineup named on air (B 48:25)

The named set is {Dak, Aubrey, Lamb, Cowboys DST, Daniels, Flournoy}. The captain was not stated, so every captain
assignment was checked.

| Captain | Salary | 150-max copies (rank) | 20-max A | 20-max B |
|---|---|---|---|---|
| Dak | **$50,000** | **295 (#29)** | 144 (#7) | 124 (#9) |
| Daniels | $49,100 | 36 | 9 | 10 |
| Aubrey | $47,500 | 8 | 1 | 1 |
| Flournoy | $46,700 | 7 | 3 | 2 |
| Cowboys | $47,200 | 6 | 0 | 0 |
| Lamb | $50,700 | illegal | - | - |

**How this compares with what was said on air.**
- "About 50K" matches only the Dak-captain version.
- Their stated figure was 79 copies, with no contest named. If they meant the 150-max, the actual was about 3.7x
  higher.
- The most-duplicated actual lineup had **937** copies: Lamb CPT with Otton, Dak, Javonte, Flournoy and Hurst, at
  $49,900.
- All 25 most-duplicated lineups cost between $49,500 and $50,000. "Most-duped lineups sit at or near the cap" is
  verified.

### Our sealed pregame forecasts, graded (answer key)

**Ownership.**
- The shadow BLEND forecast's CPT MAE was 1.83 pp.
- It over-forecast Lamb and Dak captaincy by about 2x.
- The no-fit FC-proportional baseline did better: CPT MAE 1.09, Spearman 0.93.

**Duplication (B4 maxent).**
- Spearman 0.71: it ranks lineups usefully.
- Median predicted copies were 1.3 against 11.5 actual.
- Summed actual over summed predicted was 0.16: a few heavy-chalk lineups were predicted in the thousands.
- The **level and tail are wrong; the ranking is useful.**

**Coverage.** The sealed B4 artifact priced **only our own lineups**, so it has no number for the named lineup or for
the field's top lineups. Fixing that is requirement R3 below.

## 2. Model structure

### F1. Ownership marginals, CPT and FLEX separately: new `nfl/field/ownership_v2.py` (T1)

**Incumbent.** The no-fit FC-proportional baseline:
- `own_FLEX(p) = 500 · proj_FC(p) / Σ proj_FC`
- `own_CPT(p) = 100 · proj_FC(p) / Σ proj_FC`

The two carry separate error profiles and are graded separately.

**Challenger.** A hierarchical multinomial-logit share model per slot `s ∈ {CPT, FLEX}`:
`own_s(p) ∝ exp(β_s·x_p + u_bucket(p),s)`.
- Features `x_p`: salary, public projection rank, value (projection per $1k), position, captain premium
  (projection×1.5 per CPT dollar), news and role flags (opened starter, injury replacement), and team implied by public
  projection share.
- Bucket random effects use the five buckets already defined in `SC_OWN_ROTATION_2`: STAR, MIDRANGE,
  CHEAP_ACTIVE_ROTATION, PUNT_FRINGE, K_DST.
- Shrinkage is toward the incumbent: the incumbent is the prior mean, not zero.
- **Uncertainty.** Represent the forecast as a Dirichlet over slot shares, concentration `κ_s`. `κ_s` is estimated
  from leave-one-slate-out residuals, never from the scored slate. This supplies the ownership intervals used in
  section 5.
- **Known failure to design against.** The SC-OWN-2 candidate gave Payne Durham ($200 TE) **94.5%** FLEX against an
  actual 1.3%. A punt-tier player whose own projection is near zero must not inherit share from the optimizer
  universe. Clamp it with a hard plausibility test: FLEX share at most the bucket's historical maximum, declared.

### F2. Lineup generator (T2): extend `nfl/field/showdown_dupe_shadow.py` (B4) and `nfl/field/showdown_archetype_field.py`

A two-component mixture over the **legal universe** 𝓛. 𝓛 is all 1 CPT + 5 distinct FLEX lineups, both teams
represented, salary at most $50,000. It is built as in `showdown_dupe_research.py`, which enumerates the most-entered
players; SC-OWN-2 reports 5.3M lineups for TB@DAL.

`q(L) = (1-π) · q_maxent(L) + π · q_opt(L)`

**The `q_maxent(L)` component.**
- Its form: `q_maxent(L) ∝ exp( Σ_{p∈L} a_{slot(p),p} + θ·φ(L) )`.
- `φ(L)` carries:
  - **salary-cap clustering**: salary-left bands 0, 100-500, 600-900, 1000-1900, ≥2000. These are B4's existing
    features. Measured: duplication collapses below $48,000.
  - **team split**: 5-1, 4-2, 3-3 indicators per side.
  - **correlated construction**: CPT is the QB's own pass catcher; QB plus ≥2 own pass catchers; bring-back
    (opponent skill player with a QB stack); both QBs (40.6% measured); any K (45.5%); any DST (25.8%); RB plus own
    DST.
  - **chalk count**: number of the top-k public-projection players.
- The `a` terms are solved by iterative proportional fitting, so the CPT and FLEX marginals of `q` reproduce F1.
- `θ` is fitted on other slates only.

**The `q_opt(L)` component.** The "optimizer population".
- Each draw is the exact optimum of a public projection under lognormal noise:
  `exp(σz − σ²/2)`, solved by `optimal_worlds.solve`.
- This is what `nfl/field/showdown_shadow_field.py` already does.
- It produces the heavy, near-identical chalk mass at the cap. The measured concentration (top 1,000 lineups hold
  45.5% of entries) and the 937-copy lineup are exactly that mass.
- `π` and `σ` are fitted leave-one-slate-out against the copy-count distribution in section 1.
- This is the "explicit chalk-concentration term" the plan names. A single exponential family has been shown to
  get the tail wrong in both directions.

**Contest-type behaviour.** `π`, `σ` and `θ_salary` carry a contest-class index: 150-max, 20-max, 3-max, single
entry.
- Measured: the 150-max is 74% from ≥100-entry users and only 4% unique.
- The 20-max contests are about 10% unique.
- Multi-entry users are modelled as portfolios: one user's entries are drawn without within-user duplicates except at
  the measured within-user rate (3.2% in the 150-max, 5.5-7.6% in the 20-max).
- Field size comes from the contest page, captured prelock, or is declared as an estimate.

### F3. Duplication estimator (T3)

For any lineup L, our own or not, in a contest with N entries:
- **Expected other copies:** `E[D(L)] = (N_other) · q(L)`.
- **Distribution:** `D(L) | q ~ Poisson(N_other·q(L))` within one field draw. Over the parameter posterior,
  `D(L) ~ Σ_k w_k Poisson(N_other·q_k(L))`. The draws `q_k` come from (a) the Dirichlet ownership draws, (b) the
  bootstrap over training slates of `θ, π, σ`.
- **Report:** median, 10-90% interval, and P(D = 0).
- **Requirement R3:** the estimator must price **any** lineup in 𝓛, including the field's predicted top-1,000. The
  current sealed artifact prices only ours.

### F4. Prize splitting among duplicates (T4)

**Payout rule.** In world w, every entry's DK score is known: field draw, our portfolio and duplicates alike.
- Let L score `s` and let `c_w(L)` = number of entries with score exactly `s`. That counts L's copies, ours and the
  field's, plus coincidental ties.
- Let `r` be the best rank of that tie block.
- Each tied entry receives `Prize(L,w) = (1/c_w) · Σ_{k=r}^{r+c_w−1} P_k`, where `P_k` is the payout table.
- This is DK's tie rule (prizes for the tied positions are pooled and split equally). Verify it against the contest
  rules text captured prelock before relying on it.

**Our own copies.** If we enter m copies of L, all m sit in the same block, so splitting cannibalises our own
return.

**Prerequisite.** Payout tables are required and are **not captured**. The standings exports carry none. This is a
capture task for the networked agent: the contest-detail payout structure, prelock, per contest. It is already in the
plan's section 3.

## 3. Reuse map: what exists in `nfl/field/` and what changes

| Module | Today | Role in this spec |
|---|---|---|
| `showdown_shadow_field.py` | Public-projection noisy-optimizer field; CPT/FLEX ownership (BLEND, FC_ONLY) | Becomes the `q_opt` component of F2 |
| `showdown_archetype_field.py` | Archetype-first generator (away count, QB count, K/DST) | Source of the archetype features in `φ(L)`; retire as a separate estimator after F2 |
| `showdown_dupe_shadow.py` | B4 / B3S maxent, prelock, sealed | Extend to the mixture; add universe-wide pricing (R3) and intervals |
| `showdown_dupe_research.py` | Universe build, model ladder, LOSO | Training and LOSO harness for F2 |
| `showdown_history_calibration.py` | PHI@CHI and PIT@CLE historical calibration | Two of the LOSO folds |
| `showdown_field_archive.py` | Ingest, reconcile, grade sealed shadows | Grading door for every fold |
| `contest_ownership.py` | The single door to realised ownership; refuses when absent | The only postgame reader; F1 and F2 must never import it |
| `showdown_cheap_ownership_research.py`, `research/ownership/sc_own_rotation_2.py` | Cheap-bucket ownership successor (fails slate 1 of 4) | Bucket definitions reused; candidate kept as a challenger only |
| `showdown_shadow_board.py` | Leverage and duplicate board (shadow) | Rewritten to report the section-4 metrics with intervals |
| `ownership.py`, `opponent.py`, `build.py`, `contest_intelligence.py` | Classic field (uncalibrated; Week 4 standings exist) | Classic analogue; see the Classic plan |
| `postgame/showdown_standings.py`, `postgame/showdown_field_loso.py`, `research/field_study/showdown_field_study.py` | Standings parse, LOSO, field study | Answer-key side only |
| **new** `nfl/field/ownership_v2.py`, `nfl/field/field_sim.py`, `nfl/tools/showdown_ev.py` | - | F1, F2/F3, F4 respectively |

## 4. Metric definitions (precise)

**Notation.**
- Worlds `w = 1..W` (W = 2,000), our frozen football simulation.
- `S_w(L) = 1.5·x_w(cpt) + Σ_{p∈flex} x_w(p)`, the DK score of lineup L in world w.
- 𝓛 = the legal universe; 𝓒 ⊂ 𝓛 = a candidate pool. Every metric states which set it uses.
- `F_k` = a field draw under parameter draw k = 1..K.

| Metric | Formula | Notes |
|---|---|---|
| World-optimal lineup | `L*_w = argmax_{L∈𝓛} S_w(L)` (or over 𝓒; ties split equally) | On TB@DAL the R1 pool reproduces `CPT_BOARD.p_world_optimal_captain` exactly; the true 𝓛-optimum was not in the pool in hindsight |
| **Player optimal frequency** | `OF(p) = (1/W) Σ_w 1[p ∈ L*_w]` | any slot |
| **CPT optimal frequency** | `OF_CPT(p) = (1/W) Σ_w 1[cpt(L*_w) = p]` | sums to 1 |
| **FLEX optimal frequency** | `OF_FLEX(p) = (1/W) Σ_w 1[p ∈ flex(L*_w)]` | sums to 5 |
| **Simulated ownership** | `own_CPT(p) = E_k[(1/N) Σ_{e∈F_k} 1[cpt(e)=p]]`; `own_FLEX(p) = E_k[(1/N) Σ_e 1[p∈flex(e)]]` | Forecast, with interval over k. DK %Drafted is the realised counterpart, read only by the grader. |
| **Leverage** | `lev_s(p) = OF_s(p) − own_s(p)`, s ∈ {CPT, FLEX}; exposure leverage `x_s(p) − own_s(p)`, where `x` is our portfolio exposure | Report the interval from `own`'s posterior. Its sign is not interpretable when the interval spans 0. |
| **Lineup win probability** | `P_win(L) = (1/W) Σ_w E_k[ 1[S_w(L) ≥ M_w,k] / (1 + T_w,k(L)) ]` | `M_w,k` is the best field score; `T` counts the other entries tied at the top |
| **Top-q probability** | `P_top q(L) = (1/W) Σ_w E_k[ 1[rank_w,k(L) ≤ ⌈qN⌉] ]` | rank among field ∪ our entries |
| **Expected payout** | `EP(L) = (1/W) Σ_w E_k[Prize(L,w,k)]` | section F4; needs payout table P |
| **Duplication-adjusted expected return** | `DAER(L) = EP(L) − fee`, with `Prize` computed using `c_w ≥ 1 + D_k(L) + m(L)` | The duplication enters **through** the split. Report also `EP_nodup(L)` (c = coincidental ties only); the gap `EP_nodup − EP` is the duplication cost. |
| Portfolio expected return | `Σ_i EP(L_i) − n·fee`, all our entries placed in the same simulated contest | Captures self-cannibalisation and self-splitting |
| Near-optimal hit rate (incumbent proxy) | `H(L) = (1/W) Σ_w 1[S_w(L) ≥ 0.9·S_w(L*_w)]` | Defined at `showdown_portfolio.py:736-741`; not a probability of winning |

**How the two kinds of uncertainty propagate.** Football uncertainty is carried by w. Field uncertainty is carried
by k: ownership Dirichlet draws times generator parameter draws. Every metric is a double average.

For each metric, report:
- the point value;
- the **field-uncertainty interval**: the spread across k of the w-average;
- the **football Monte Carlo error**: SE across w;
- the decomposition `Var = E_k[Var_w] + Var_k[E_w]`, so it is visible which uncertainty dominates.

Football-forecast miscalibration (D-01 thin tails, D-02/D-03 QB volume) is **not** captured by Monte Carlo error. It
biases every metric, and it must be reported as a disclosed limitation until fixed.

**Compute.**
- 2,000 worlds × a stratified 20k-lineup field sample per world: about 2-4 minutes vectorised (plan T4).
- Duplicates come from the exact universe weights, not the sample.

## 5. Interfaces

- `field_sim.py` writes `FIELD_<slate>_<contest>.json`, containing:
  - the contest class, N, π, σ, θ and the k-draw seeds;
  - per-player CPT/FLEX ownership with 10/50/90 percentiles;
  - the top-5,000 lineups by `q` with expected copies and intervals;
  - salary-band and split marginals.
- Each artifact is sealed with sha256 before lock, like the existing B4 shadow.
- `showdown_ev.py` reads worlds and the field artifact. It writes per-lineup `P_win`, `P_top1%`, `EP`, `DAER`,
  `E[D]`, and a portfolio summary.
- **Default OFF in selection** (T5 flag). It is scored side by side with the incumbent each slate.

## 6. Refusals (Phase-1 discipline: empty is an error)

These conditions raise a named error:
- `FIELD_SIZE_UNKNOWN`
- `PAYOUT_TABLE_ABSENT`: EP and DAER are refused rather than reported as 0.
- `OWNERSHIP_MARGINALS_NOT_REPRODUCED`: IPF residual above tolerance.
- `UNIVERSE_TRUNCATED_BELOW_DECLARED_COVERAGE`
- `ACTUAL_OWNERSHIP_READ_PRELOCK`: import guard on `contest_ownership`.
- `SCORED_FOLD_IN_TRAINING`

## 7. Validation and promotion bars (declared before fitting)

**Folds.**
- Showdown slates with standings: PHI@CHI, PIT@CLE, ATL@NO, TB@DAL. Three have pregame salaries.
- Leave-one-slate-out (LOSO) on those, then each new slate prospectively.
- **4 slates is very few.** Results are reported per fold. No pooled significance claim is made, and games are
  clustered by slate.

**Ownership (F1).** In LOSO and then prospectively, it must beat the FC-proportional baseline on all of:
- CPT MAE;
- FLEX MAE;
- STAR-bucket |bias|;
- smoothed log score.

It must win on at least 3 of 4 prospective slates. A model that cannot beat the no-fit baseline is not promoted.

**Duplication (F2/F3).** Every condition holds per fold:
- Σactual/Σpredicted within **[1/1.5, 1.5]** on the top-1,000 predicted lineups, **and** on our own lineups
  (TB@DAL B4: 0.16, a fail);
- Spearman(predicted, actual copies) **≥ 0.6** (TB@DAL B4: 0.71, a pass);
- predicted share of unique entries within ±50% relative of actual (actual 4.1% in the 150-max, about 10% in the
  20-max);
- entry share by copy-count bin (1, 2-5, 6-20, 21-100, >100): total-variation distance ≤ 0.10;
- salary-band and team-split marginals: total-variation distance ≤ 0.05.

Calibration of predicted copies is checked by binning lineups by predicted copies. Σactual/Σpred per bin must sit
within [1/1.5, 1.5] in every bin holding at least 50 lineups.

**Coverage of the interval.** The 80% interval of `D(L)` must contain the actual copy count for 70-90% of lineups.

**EV objective (F4/T5).**
- Shadow for at least 8 prospective contests, clustered by slate.
- Realised payout ≥ the incumbent, with the bootstrap interval excluding a loss larger than a declared margin.
- Predicted P(top 1%) calibrated within its interval.
- Payout tables captured for every contest counted.
- **One slate never promotes anything.**

## 8. Tests the implementation must carry

All are registered with `nfl/tests/_registry.py:emit()` and confirmed counted by `run_suite.py`:

1. **IPF reproduces given marginals.** Positive test, plus a seeded violation: a player with share > 1 is refused.
2. **Legality.** Every generated lineup obeys the cap, has distinct players, and includes both teams. A seeded
   illegal $50,700 lineup is rejected. The named Lamb-CPT version is exactly this case.
3. **No outcome leakage.** `field_sim` imports neither `contest_ownership` nor any postgame module, checked by AST.
   The bypass test via `nfl/tests/bypass.py` must fail when the guard is removed.
4. **Tie-split arithmetic** on a synthetic payout table: c tied entries over positions r..r+c−1.
5. **Universe pricing.** For a lineup outside our portfolio, a copy estimate is returned, not `NOT_PRICED`.
6. **Determinism.** Same seed gives a byte-identical artifact, under normal, `--reverse` and `--shuffle` suite order.
7. **Refusal tests** for every named error in section 6.
