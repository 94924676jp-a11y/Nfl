# Showdown tournament system: audit, measured bottlenecks, implementation plan (2026-10-09)

Owner directive 2026-10-09, after the TB@DAL standings.

**Evidence base:**
- `nfl/research/field_study/TB_DAL_2026W5_FIELD_STUDY.json`
- `nfl/research/field_study/TB_DAL_2026W5_SEALED_FORECAST_GRADES.json`
- `nfl/postgame/showdown_tb_dal_2026W5/TB_DAL_2026W5_STANDINGS.json`

**Every forecast graded here was frozen before kickoff.** DK standings are the answer key only.

## 1. How the optimizer selects lineups today (`nfl/tools/showdown_portfolio.py`)

| Stage | What it does | Where | Provenance of its constants |
|---|---|---|---|
| Candidates | exact per-world optima, then 8 captain-exclusion and 10 flex-core-drop rounds within a 0.10 loss band; plus a forced-captain exact solve for every person over the 25% of worlds where his own score is top quartile, keeping ≤120 per captain | `showdown_to_portfolio.py:110-130`; `showdown_portfolio.py:160,195`, `:63` | compute bounds, not estimates |
| Hit proxy | a lineup "hits" a world when it scores ≥ 0.9 × that world's exact optimum | `:740-741` | "policy not estimate … nothing has measured the right band" (`showdown_to_portfolio.py:104-109`) |
| Objective | greedy maximise E_w[min(hits, m)]; m = 1 for n ≥ 100 or n ≤ 2, else 2; m escalates when saturated | `:287-351`, `depth_m :296` | declared policy |
| Constraints | player 50%, captain 30%, overlap ≤ 4 of 6; relaxation ladder (overlap +1, then player +15 pp, then captain +15 pp) | `showdown_to_portfolio.py:136-138`; `LADDER :275-284` | declared, not measured |
| Polish | 1-swap hill climb on the same objective | `swap_polish :372-420` | compute budget |
| Tie-break | structural duplication index (cap salary, top-mean captain, chalk count, QB double stack, 5-1 split) | `:216-232` | heuristic; only a tie-break |
| **Field, ownership, duplication, payout** | **absent from selection.** "Ownership enters nowhere" (`:18-29`); the audit reports P(top 1%) and payout UNAVAILABLE (`:998-1000`, `:1030`) | — | — |

Shadow field models run after the upload is written and are never read by selection (`showdown_next_slate.py:395-462`).

**What the objective rewards.** It rewards being near the best lineup in many of *our* simulated worlds. It does not
reward beating the field, avoiding shared prizes, or the shape of the payout table. A player who is the best captain
in many of our worlds is pushed to the caps whatever the field does. Lamb was the best captain in 36.8% of our worlds
and sat at the 50% player cap in every contest.

## 2. What TB@DAL measured (one slate: descriptive, not a validated comparison)

### Duplication (150-max, 237,812 entries)

- **The field itself is highly duplicated.** 23,645 distinct lineups for 236,900 non-owner entries. The median field
  entry shares its exact lineup with **42** others, and only 4.1% are unique.
- **We were less duplicated than the field.** The median lineup of ours was shared with **13.5** field entries, and
  18.7% were unique.
- In the 20-max contests the medians are 12 (field) against 8.5–11 (ours).
- **The winning lineup was shared by 18 entries.** Duplication matters most at the top, and that is exactly where
  nothing models it.

### Who won: the field's top 1% (2,403 entries)

- Captain was **Irving 49% / Pickens 49%**.
- Both QBs: **54%** (ours 16%, field 41%).
- With a kicker: 28% (ours 56%, field 46%).
- Salary at or under $48,000: 3.5% (ours 18.7%, field 10.4%).
- Away/home 3–3 split: 58%.

These describe one outcome. Optimizing toward them would be fitting yesterday.

### Ownership forecasts, frozen before kickoff, graded (150-max; the 20-max contests agree)

| Model | CPT MAE (pp) | CPT Spearman | FLEX MAE |
|---|---|---|---|
| Shadow BLEND (`showdown_shadow_field`) | 1.83 | 0.83 | 4.28 |
| Shadow FC_ONLY | 1.56 | 0.70 | 6.58 |
| SC-OWN-ROTATION-2 candidate (sealed 23:30Z) | 1.80 | — | 6.66 |
| SC-OWN-ROTATION-2 baseline (sealed 23:30Z) | 1.55 | — | 4.11 |
| **No-fit baseline: share ∝ FC FLEX projection** | **1.09** | **0.93** | **2.88** |

**A model with no fitted parameter beat every fitted ownership model on this slate.** STAR players are the problem:
SC-OWN-2 star FLEX MAE was 16.4 and its bias −10.5.

**SC-OWN-ROTATION-2, prospective slate 1 of its preregistered 4: FAILS this slate.**
- Cheap FLEX MAE: 5.74 against 5.79 (marginally better, as required).
- But the cheap |bias| got worse: 5.74 against 2.59.
- And total FLEX MAE was +2.55 pp, against a +1.0 pp allowance.

### Duplication forecasts, frozen before kickoff, graded

| Model | Spearman (150-max) | Predicted median copies | Actual median | Σ actual / Σ predicted | Within 2× |
|---|---|---|---|---|---|
| Shadow board exact | 0.25 | 0 | 11 | — | — |
| **B4 maxent** (sealed 23:30Z) | **0.71** | 1.3 | 11.5 | **0.16** | 43% |
| B3S | 0.71 | 1.2 | 11.5 | 0.16 | 42% |

- **B4/B3S rank lineups usefully, but their level is wrong.** They under-predict typical lineups about 9× and
  over-predict a few heavy-chalk lineups by orders of magnitude.
- **That fails the preregistered calibration bar** (actual/predicted within [1/1.5, 1.5]).
- **The defect to fix is the level and the tail, not the ranking.**

### Did we choose badly before kickoff, or lose? The honest answer is: not determinable from one slate.

- What *is* determinable: the objective cannot tell those apart, because it never sees the field or the payout.
- **Ex ante**, the hindsight-best lineup averaged 77.4 points in our worlds, with a 95th percentile of 113.0. It was in
  no candidate pool.
- The other frozen portfolios ranked differently. That is not a strategy.

## 3. What has to be true before money depends on it

**Payout tables are required.** The standings exports carry none. Without them:
- no expected-value objective can be computed;
- no ROI claim can be made, whether verified or modelled.

**Request:** the DK contest-detail payout structure for each entered contest, captured before lock. The owner's
winnings figure for TB@DAL settles that slate's realised net.

## 4. Implementation plan: isolated research track, nothing promoted without the bars in §5

| # | Work item | Code path | Inputs (prelock only) | Output | Compute |
|---|---|---|---|---|---|
| T1 | **Ownership incumbent = the no-fit FC-proportional baseline**, plus a calibrated successor: hierarchical model on salary, projection rank, value, position, captain premium, news flags; shrinkage per bucket | new `nfl/field/ownership_v2.py` (shadow) | DK pool, FC projection, our projection, injury/news flags | CPT/FLEX % per player, with intervals | seconds |
| T2 | **Field simulator**: sample N legal lineups from a structural model (captain choice, team split, salary use, stack and K/DST propensities) whose marginals match T1. B4's legal-lineup maxent is the starting point; its level is recalibrated with an explicit chalk-concentration term | extend `nfl/field/showdown_dupe_shadow.py` (B4) or a new `field_sim.py` | T1 marginals; structural rates from **other** slates only (LOSO) | lineup counts for the full field | about 1–5 min for 240k lineups (vectorised sampling, no solver) |
| T3 | **Duplication estimator**: copies of each candidate lineup in the simulated field (exact match), with a mixture term for very common chalk lineups | same | T2 | expected copies and interval per lineup | seconds per lineup batch |
| T4 | **Contest EV objective**: for each world w and lineup L, rank of L's score among simulated field scores (T2 field scored in world w); prize from the payout table, split among the tied duplicates (T3) | new `nfl/tools/showdown_ev.py` (shadow) | our worlds (2,000), T2 field, payout table | E[payout], P(top 1%), P(cash) per lineup; portfolio EV with own-entry cannibalisation | field scoring 2,000 × 240k = 4.8e8 lineup-world sums, reduced with a 20k-lineup field sample per world (stratified), about 2–4 min vectorised |
| T5 | **Contest-specific portfolio selection**: greedy plus swap on portfolio E[payout] (a 150-max uses many top-heavy slots; a 20-max uses fewer); exposure caps become soft penalties with declared provenance | new arm in `showdown_portfolio.py` behind a flag, default OFF | T4 | an alternative portfolio, scored side by side with the incumbent | marginal-gain evaluation over about 8k candidates × 2,000 worlds, minutes |
| T6 | **Separate 20-max portfolios** (D-07): the two 20-max contests currently get identical lineups | `showdown_portfolio.py` | — | distinct portfolios | negligible |
| T7 | **Lower-tail volatility in the worlds** (D-01): T4's EV depends on the tails our worlds currently mis-state | the simulation track, separate | — | — | — |

**Measured bottlenecks:**
- **Ownership:** the incumbent field models are beaten by a no-fit baseline.
- **Duplication:** the level is miscalibrated about 6–9×.
- **Payout:** tables are missing.
- **Objective:** it ignores all three.
- **Compute is not the bottleneck.** Exact solves (about 36 s each) are needed only for candidates, which already
  exist.

## 5. Validation and promotion criteria

**Data:**
- **4 Showdown slates with standings exist:** PHI@CHI, PIT@CLE, ATL@NO and TB@DAL; 3 of them have pregame salaries.
- **8 contests.**
- **Classic:** week 4, 3 contests.
- **Every new slate adds one fold.**

**Ownership (T1).** On leave-one-slate-out folds and then prospectively, beat the FC-proportional baseline on:
- CPT MAE and FLEX MAE;
- STAR-bucket bias;
- smoothed log score.

It must win on at least 3 of 4 prospective slates. A model that cannot beat a no-fit baseline is not promoted.

**Duplication (T2/T3):**
- Σ actual / Σ predicted within [1/1.5, 1.5] on the top-1,000 predicted lineups and on our own lineups (the
  preregistration bar);
- Spearman ≥ 0.6;
- calibration of the share of lineups that are unique.

All per fold, with no tuning on the fold being scored.

**EV objective (T4/T5).**
- **Shadow first:** each week both portfolios are frozen before lock and scored on actual results and actual standings.
- **Promotion** requires all of the following, across at least 8 prospective contests, clustered by slate:
  - the EV arm's realised payout ≥ the incumbent's, with a bootstrap interval that excludes a loss larger than a
    declared margin;
  - its predicted P(top 1%) calibrated within its interval;
  - payout tables captured for every contest counted.
- One slate never promotes anything.

**Separation:**
- Pregame ownership forecasts are frozen before kickoff, as they were for TB@DAL.
- Actual ownership (DK %Drafted) is read only by the postgame grader (`contest_ownership.py` enforces this).
- Fitting uses only folds other than the one being scored.

**Not touched by this track:** the accepted baseline portfolio, the football simulation, the accounting repair arm,
and the QB-conditioning work. Each is a separate, active workstream.
