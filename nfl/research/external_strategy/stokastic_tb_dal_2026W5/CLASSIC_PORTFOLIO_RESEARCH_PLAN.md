# Week 5 Classic: portfolio research plan (Sunday 1:00 ET, 8 games)

**Games:** CHI@GB, CIN@MIA, LV@NE, MIN@NO, CLE@NYJ, IND@PIT, HOU@TEN, NYG@WAS.
Source: `nfl/dfs/salaries/classic_early_2026W5/WEEK5_SUNDAY_DECISION_BOARD.md`.

**What this plan is and is not.**
- It carries the TB@DAL Showdown lessons over to a multi-game slate.
- **Nothing is imported from Stokastic.** Their claims are not inputs, priors or benchmarks.
- FantasyCruncher (FC) remains an external comparison and the stand-in for "what the field sees". It is never a
  football input.
- No wager is recommended. Nothing is submitted.

## 0. State today (read from the repository, 2026-10-09)

**Readiness: `NOT_READY`** (`WEEK5_CLASSIC_PORTFOLIO_READINESS.json`). The blockers:
- no DK DKEntries export (ids, contests, fees);
- Friday designations not captured;
- Sunday inactives at about 11:30 ET;
- the CHI, MIN and WAS starting QBs not confirmed by a team source.

**Optimizer.**
- `nfl/opt/classic_portfolio.py` exists.
- Objective: `E_w[max_i (S_iw − T_w)+]`, where `T_w` is a candidate-set quantile used as a field proxy.
- The **20-max is built as its own portfolio**, unlike the Showdown D-07 defect.
- It reads no ownership, so duplication is NOT MODELLED. The artifact says so.

**Research projection.** `research_projection/incumbent/`: 266 players, 2,000 worlds. It is research only until the
export arrives.

**Release gates.**
- Roster eligibility: wired for Classic (W5-G2, fixed).
- Accounting: D-05, FAIL, disclosed.
- QB-conditioned model: NOT_VALIDATED.

**Ownership forecast declared before the slate** (`WEEK5_OWNERSHIP_AND_DUPLICATION_RESEARCH_BOARD.md`):
- incumbent: proportional to FC;
- challenger: proportional to FC².

## 1. Research questions, in Classic form

| # | Topic | What carries over from TB@DAL (measured, one slate) | Classic-specific question | Measurement |
|---|---|---|---|---|
| C1 | **Multi-game stacking** | Same-club QB~WR1 r = +0.42 and WR1~WR2 +0.17 (measured 2000-2026); our worlds under-state WR1~WR2 (+0.02 for Lamb-Pickens) | Do our joint worlds reproduce QB-stack and bring-back correlations **within each of 8 games**, and zero correlation across games? | Per-game pair correlations from the incumbent worlds vs `nfl/sim/PAIR_CORRELATIONS.json`, with game-blocked intervals |
| C2 | **Ownership concentration** | No-fit ∝FC beat every fitted Showdown model. In W4 Classic, ∝FC under-predicted the top-12 owned by 14.3 pp, and ∝FC² cut that to 10.8 | Is Classic chalk more concentrated than proportional? | Grade ∝FC and ∝FC² prospectively on W5 (already declared). Report the top-12 error, by position, with DST separately (W4 DST Spearman only 0.35) |
| C3 | **Salary allocation** | Showdown field: 10.3% at exactly the cap; duplication collapses below $48k | The salary-left distribution of the Classic field; its relation to duplication | W4 Classic standings (3 contests, 35,671 entries in the largest), `nfl/field/contest_intelligence.py`, computed now as **development data** |
| C4 | **Positional opportunity** | Opportunity is predictable and efficiency mostly is not. Our biggest TB@DAL misses were volume and QB-regime driven (D-02/D-03/D-04) | Which W5 clubs have QB-regime changes (CHI, MIN, WAS per W5-G1), and how much of each projection depends on QB-independent team volume? | `WEEK5_QB_REGIME_BOARD.json` plus the sensitivity of player means to a QB-conditioned volume scenario. Shadow, reported, not selected on. |
| C5 | **Late injuries** | D-08: ineligible players were selectable, now fixed; availability is binary, with no partial workload (W5-G4) | Exposure to players with practice DNP or limited weeks (Chase, Jefferson, Higgins, McLaurin, Diggs per W5-G4) | Exposure report by availability state; a swap plan for the 1:00 ET game window, using the roster gate. No probability of a partial workload is invented. |
| C6 | **Portfolio correlation** | Lamb at the 50% cap in every contest; lineups with Lamb averaged 69.6 against 87.8 without | Concentration by player, game and stack; effective number of independent lineups | Pairwise lineup-score correlation across worlds; the worlds' concentration of top-proxy hits; the max-player-exposure binding report (D-09 fix prints relaxation) |
| C7 | **Contest-specific leverage** | Leverage built on a 2x-miscalibrated ownership forecast is noise | Only after C2 grades: optimal frequency minus ownership by contest | `OF` and `own` as defined in the spec, section 4, with intervals. **Descriptive on W5; never selection.** |
| C8 | **Duplication** | Showdown was 4% unique; Classic is believed far less duplicated (9 slots), but no Classic duplication model has been graded | How duplicated is the Classic field, and are our lineups unique? | W4 standings now (development data); W5 standings after the slate. Count exact copies of our lineups and the field's distribution of copy counts. |

## 2. Feasible by Sunday, and what is not

**Feasible by Sunday.** All of these are descriptive or shadow and frozen prelock. They are conditional on the DK
export arriving.

1. **Freeze the ownership forecasts** (∝FC incumbent, ∝FC² challenger) from the latest prelock FC capture, with a
   sha256 seal, before 17:00Z Sunday.
2. **Classic field duplication on W4** with `contest_intelligence.py` and the standings in
   `nfl/postgame/raw/2026W4_standings*`.
   - Measure: the copy-count distribution, the salary-left distribution, and stack rates.
   - **Label it development data.** Week 4 is not a holdout.
3. **Per-lineup prelock diagnostics** on whatever `classic_portfolio.py` produces:
   - geometric-mean ownership under both forecasts;
   - game-stack ownership;
   - salary left;
   - the cap-binding and relaxation report.
   - None of it is used for selection.
4. **World-correlation check (C1)** on the incumbent research worlds, within and across games, against the measured
   pair table.
5. **Late-injury protocol (C5).**
   - Roster gate PASS is required before any upload file is written.
   - Official inactives are captured at about 11:30 ET; a SECONDARY source is labelled as such (as TB@DAL's RotoWire
     capture was).
   - The exposure report is re-emitted after inactives.
6. **The SIMULATION_QUERY_CAPABILITY_SPEC tool**, if delivered by the other agent, for conditional checks. Examples:
   P(QB stack hits | game total ≥ X), and exposure by script.

**Not feasible by Sunday.** Each needs code, folds or data that do not exist:
- a Classic field simulator, meaning an F2 analogue on a 9-slot, 8-game universe, which cannot be enumerated;
- a duplication estimator with calibrated level;
- an EV objective (no payout tables);
- a QB-conditioned volume model (section G);
- the D-01 tail repair;
- the D-05 accounting repair promoted.

## 3. Later (research track, ordered)

1. **Classic field generator** (`nfl/field/opponent.py` extended, or a new `classic_field_sim.py`). Classic cannot
   enumerate its universe, so the generator is sampling-based:
   - stack-first construction: QB plus n pass catchers plus an optional bring-back;
   - salary-left propensity;
   - position-slot FLEX choice;
   - a public-projection noisy-optimizer component, as in the Showdown spec.
   - Duplication then comes from exact matching in a large sample with importance weights, or analytically for the
     chalk core.
2. **Calibrate on the W4 and W5 Classic standings**, leave one slate out. The bars are the same as the Showdown spec,
   section 7. Classic copy counts are small, so the bars on our own lineups use P(unique) calibration as the primary
   measure.
3. **Payout capture** for every entered Classic contest, prelock. This is the networked agent's task.
4. **EV objective arm**, behind a flag, default OFF. It is scored side by side with the incumbent over at least 8
   prospective contests, clustered by slate.
5. **Portfolio correlation control.** Replace the fixed exposure caps with a declared penalty on concentration, once
   C6 has measured how concentration relates to outcomes across slates.

## 4. Rules that apply on Sunday whatever is built

- One slate grades nothing. W5 results go to the cross-slate ledgers, never into a parameter.
- An empty card is valid. No threshold is loosened to manufacture lineups.
- Ownership never enters football projection. Actual %Drafted is read only by the postgame grader
  (`contest_ownership.py`).
- Every portfolio summary prints its relaxation level and caps (D-09 fix).
