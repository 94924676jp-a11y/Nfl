# Showdown duplication directive -- root cause, models, calibration, decisions

Status of everything here: **SHADOW_ONLY**. Pre-registration: `docs/NFL_SHOWDOWN_DUPLICATION_PREREGISTRATION.md` (committed 2318d267 before any model was fitted). Evidence: `nfl/postgame/showdown_atl_no_2026W4/evidence/DEFECT_DUPE_UNDERESTIMATE.json` (write-once, hash-pinned). **ATL@NO is development data** -- the defect was found there and the features were chosen after seeing it -- so every result is exploratory; the confirmatory test is the next slate.

## 1. Root cause (oracle ownership: the mapping from ownership to complete lineups)

| contest | entries | duplicate entries that are same-user repeats | independent-product mass over legal lineups (x field) | top-200 lineups: actual / independent / max-entropy |
|---|---|---|---|---|
| PIT_CLE | 47,329 | 7.0% | 5.68 | 13,683 / 5,515 / 7,388 |
| PHI_CHI | 47,333 | 7.0% | 7.74 | 15,507 / 5,024 / 1,364 |
| ATL_NO_160 | 47,308 | 6.7% | 6.14 | 13,729 / 2,356 / 7,751 |
| ATL_NO_137 | 237,105 | 3.4% | 6.36 | 47,195 / 11,975 / 30,515 |
| ATL_NO_161 | 59,083 | 10.2% | 6.14 | 16,461 / 2,796 / 9,180 |

Actual / max-entropy (exact ownership + legal lineups) by lineup structure -- what remains after ownership and legality are respected:

| structure | PIT_CLE | PHI_CHI | ATL_NO_160 | ATL_NO_137 | ATL_NO_161 |
|---|---|---|---|---|---|
| stack_cpt_pc_own_qb | 1.30 | 1.27 | 1.36 | 1.37 | 1.35 |
| split_5-1 | 1.78 | 1.54 | 1.34 | 1.49 | 1.31 |
| split_3-3 | 0.86 | 0.85 | 0.90 | 0.87 | 0.92 |
| both_qbs | 1.00 | 0.90 | 0.91 | 0.88 | 0.93 |
| any_k_dst | 0.94 | 0.98 | 0.94 | 0.97 | 0.92 |
| salary_left_0 | 1.31 | - | 1.06 | 1.02 | 1.10 |
| salary_left_1000-1900 | 0.76 | - | 0.81 | 0.86 | 0.78 |
| fc_rank_1_100 | 1.36 | - | 1.51 | 1.44 | 1.49 |
| fc_rank_101_1000 | 0.98 | - | 1.21 | 1.19 | 1.21 |

**What the root cause is, in order:**

1. **The current estimator has the wrong shape, not too little mass.** N x CPT share x product of FLEX shares is not a probability: summed over legal lineups it predicts 5.7-7.7 times more entries than exist, yet it under-predicts the 200 most-duplicated lineups 2.5-5.9x. It spreads weight over the long tail of ordinary lineups and starves the popular ones.
2. **Legality and exact ownership fix most of it.** A maximum-entropy model that matches every player's CPT and FLEX share exactly over the legal-lineup universe (salary cap, distinct players, both teams) and adds nothing else (B1) moves the log score by +1.3 to +2.2 nats per entry on every salary slate (+0.28 on PHI@CHI, where the cap cannot be applied).
3. **The rest is lineup construction, consistently across all five contests:** CPT WR/TE stacked with his own QB (x1.27-1.37), 5-1 game-script splits (x1.31-1.78) at the expense of 3-3 splits (x0.85-0.92), the top-100 public-optimizer lineups (x1.36-1.51), and avoiding $1,000-1,900 of unused salary (x0.76-0.86).
4. **Duplication is convergence across users, not repetition:** only 3.4-10.2% of duplicate entries are a user re-entering his own lineup.
5. **Player-pair dependence beyond those structures is small:** median absolute log pair lift 0.06-0.11 (specific pairs to +/-50-90%, e.g. QB with his own WR1, QB with the opposing DST, both kickers).
6. **Ownership forecast error is a separate, second factor:** on ATL@NO the frozen BLEND forecast was close in aggregate but gave Brian Robinson Jr. 1.0% FLEX against 17.6% actual.

## 2-3. Candidate model comparison and historical calibration (leave-one-slate-out, never fit and scored on the same contest)

| held-out contest | trained on | model | log score / entry | top-1,000 predicted: actual / pred | public-optimizer top-150: actual / pred | OUR lineups: actual / pred | top-50 actual: median abs log ratio |
|---|---|---|---|---|---|---|---|
| PIT_CLE | PHI_CHI, ATL_NO_160 | B0 | -10.179 | 0.54 | 1.75 | - | 1.17 |
| PIT_CLE | PHI_CHI, ATL_NO_160 | B5 | -10.179 | 3.77 | 12.17 | - | 2.96 |
| PIT_CLE | PHI_CHI, ATL_NO_160 | B1 | -8.916 | 1.07 | 1.23 | - | 0.69 |
| PIT_CLE | PHI_CHI, ATL_NO_160 | B3S | -8.848 | 1.06 | 1.44 | - | 0.63 |
| PIT_CLE | PHI_CHI, ATL_NO_160 | B2 | -8.872 | 0.98 | 1.14 | - | 0.53 |
| PIT_CLE | PHI_CHI, ATL_NO_160 | B3 | -8.805 | 0.98 | 1.31 | - | 0.51 |
| PIT_CLE | PHI_CHI, ATL_NO_160 | B4 | -8.801 | 0.98 | 0.96 | - | 0.57 |
| PIT_CLE | PHI_CHI, ATL_NO_160 | B6 | -9.229 | 0.56 | 1.20 | - | 0.48 |
| PIT_CLE | PHI_CHI, ATL_NO_160 | B7 | -9.092 | 0.52 | 0.61 | - | 0.42 |
| PHI_CHI | PIT_CLE, ATL_NO_160 | B0 | -10.767 | 0.28 | - | - | 1.36 |
| PHI_CHI | PIT_CLE, ATL_NO_160 | B5 | -10.767 | 1.65 | - | - | 3.02 |
| PHI_CHI | PIT_CLE, ATL_NO_160 | B1 | -10.488 | 0.94 | - | - | 2.52 |
| PHI_CHI | PIT_CLE, ATL_NO_160 | B3S | -10.420 | 0.91 | - | - | 2.47 |
| ATL_NO_160 | PIT_CLE, PHI_CHI | B0 | -10.957 | 0.85 | 2.87 | 5.10 | 1.90 |
| ATL_NO_160 | PIT_CLE, PHI_CHI | B5 | -10.957 | 5.71 | 19.23 | 34.21 | 3.45 |
| ATL_NO_160 | PIT_CLE, PHI_CHI | B1 | -8.748 | 1.03 | 1.35 | 1.39 | 0.49 |
| ATL_NO_160 | PIT_CLE, PHI_CHI | B3S | -8.688 | 1.02 | 1.38 | 1.02 | 0.53 |
| ATL_NO_160 | PIT_CLE, PHI_CHI | B2 | -8.734 | 1.00 | 1.33 | 1.35 | 0.44 |
| ATL_NO_160 | PIT_CLE, PHI_CHI | B3 | -8.676 | 0.99 | 1.37 | 1.04 | 0.54 |
| ATL_NO_160 | PIT_CLE, PHI_CHI | B4 | -8.674 | 0.98 | 1.03 | 1.05 | 0.53 |
| ATL_NO_160 | PIT_CLE, PHI_CHI | B6 | -9.074 | 1.83 | 3.72 | 3.68 | 1.55 |
| ATL_NO_160 | PIT_CLE, PHI_CHI | B7 | -8.968 | 1.68 | 1.70 | 2.21 | 1.27 |
| ATL_NO_137 | PIT_CLE, PHI_CHI | B0 | -11.048 | 0.77 | 2.48 | 2.94 | 1.54 |
| ATL_NO_137 | PIT_CLE, PHI_CHI | B5 | -11.048 | 5.15 | 16.66 | 19.74 | 3.35 |
| ATL_NO_137 | PIT_CLE, PHI_CHI | B1 | -9.096 | 1.03 | 1.30 | 1.40 | 0.48 |
| ATL_NO_137 | PIT_CLE, PHI_CHI | B3S | -9.022 | 1.00 | 1.32 | 1.10 | 0.35 |
| ATL_NO_137 | PIT_CLE, PHI_CHI | B2 | -9.088 | 0.96 | 1.26 | 1.29 | 0.40 |
| ATL_NO_137 | PIT_CLE, PHI_CHI | B3 | -9.025 | 0.94 | 1.29 | 1.02 | 0.30 |
| ATL_NO_137 | PIT_CLE, PHI_CHI | B4 | -9.024 | 0.94 | 0.97 | 1.02 | 0.30 |
| ATL_NO_137 | PIT_CLE, PHI_CHI | B6 | -9.366 | 1.47 | 3.11 | 2.28 | 1.25 |
| ATL_NO_137 | PIT_CLE, PHI_CHI | B7 | -9.255 | 1.19 | 1.24 | 1.60 | 0.63 |
| ATL_NO_161 | PIT_CLE, PHI_CHI | B0 | -11.006 | 0.92 | 2.83 | 5.83 | 1.96 |
| ATL_NO_161 | PIT_CLE, PHI_CHI | B5 | -11.006 | 6.20 | 18.95 | 39.13 | 3.53 |
| ATL_NO_161 | PIT_CLE, PHI_CHI | B1 | -8.816 | 1.04 | 1.31 | 1.42 | 0.68 |
| ATL_NO_161 | PIT_CLE, PHI_CHI | B3S | -8.765 | 1.02 | 1.35 | 0.78 | 0.62 |
| ATL_NO_161 | PIT_CLE, PHI_CHI | B2 | -8.799 | 1.01 | 1.29 | 1.26 | 0.62 |
| ATL_NO_161 | PIT_CLE, PHI_CHI | B3 | -8.745 | 0.99 | 1.34 | 0.71 | 0.58 |
| ATL_NO_161 | PIT_CLE, PHI_CHI | B4 | -8.744 | 0.99 | 1.00 | 0.71 | 0.56 |
| ATL_NO_161 | PIT_CLE, PHI_CHI | B6 | -9.132 | 1.84 | 3.61 | 3.22 | 1.61 |
| ATL_NO_161 | PIT_CLE, PHI_CHI | B7 | -9.028 | 1.71 | 1.66 | 1.22 | 1.36 |

Salary- and projection-conditioned models on the PIT_CLE fold were trained on ATL_NO only, and on the ATL folds on PIT_CLE only (PHI_CHI has no salaries). Full per-bin calibration: `DUPE_CALIBRATION_TABLE.csv`.

### Pre-registered candidate bars (section 5)

| model | folds | verdict |
|---|---|---|
| B0 | PIT_CLE:fail, PHI_CHI:fail, ATL_NO_160:fail, ATL_NO_137:fail, ATL_NO_161:fail | BASELINE |
| B0n | PIT_CLE:fail, PHI_CHI:fail, ATL_NO_160:fail, ATL_NO_137:fail, ATL_NO_161:fail | BASELINE |
| B1 | PIT_CLE:fail, PHI_CHI:fail, ATL_NO_160:fail, ATL_NO_137:fail, ATL_NO_161:fail | BASELINE |
| B2 | PIT_CLE:pass, ATL_NO_160:pass, ATL_NO_137:pass, ATL_NO_161:pass | CANDIDATE (still SHADOW_ONLY) |
| B3 | PIT_CLE:pass, ATL_NO_160:pass, ATL_NO_137:pass, ATL_NO_161:pass | CANDIDATE (still SHADOW_ONLY) |
| B3S | PIT_CLE:pass, PHI_CHI:pass, ATL_NO_160:pass, ATL_NO_137:pass, ATL_NO_161:pass | CANDIDATE (still SHADOW_ONLY) |
| B4 | PIT_CLE:pass, ATL_NO_160:pass, ATL_NO_137:pass, ATL_NO_161:pass | CANDIDATE (still SHADOW_ONLY) |
| B5 | PIT_CLE:fail, PHI_CHI:fail, ATL_NO_160:fail, ATL_NO_137:fail, ATL_NO_161:fail | NOT_A_CANDIDATE |
| B6 | PIT_CLE:fail, ATL_NO_160:fail, ATL_NO_137:fail, ATL_NO_161:fail | NOT_A_CANDIDATE |
| B7 | PIT_CLE:fail, ATL_NO_160:fail, ATL_NO_137:fail, ATL_NO_161:fail | NOT_A_CANDIDATE |

## 4. Falsification results

- **FALSIFIED: "independence under-counts because mass is wasted on illegal lineups."** It over-allocates mass (5.7-7.7x) and is too flat. (This was my own working hypothesis; withdrawn.)
- **FALSIFIED: "duplication is mostly users repeating their own lineups."** 90-97% is cross-user.
- **FALSIFIED as fixes: simple inflation (B5 one constant, B6 by salary bucket) and a Poisson regression on log E1 (B7).** All fail the bars on every fold -- correcting the level of the wrong shape does not correct it.
- **NOT FALSIFIED (passes every available fold): B2, B3, B3S, B4.** B4 (legal-lineup max-entropy + salary-left + construction + public-optimizer terms) has the best log score; B3S (construction only, no salaries) is the only candidate tested on all three slates.
- **UNRESOLVED: PHI@CHI tail.** Without salaries the universe cannot apply the cap; every model still misses its top-50 lineups ~2.5x there. Requested in the outbox (PHI@CHI draftables).
- **UNRESOLVED: contest-type differences.** The same structural coefficients fit the 150-max, 20-max and 2-entry ATL@NO fields within the bars; same-user repeats rise with fewer entries per user (3.4% 150-max, 10.2% 2-entry). One slate cannot separate contest type from slate.

## 5. Portfolio decisions on frozen worlds (selection seed 20261005, evaluation held-out seed 20261006)

Field model for F-model: B4, structure fitted on PIT_CLE only, ownership FROZEN prelock BLEND (SHADOW_RW_INACTIVES_CHARTFIX_BLEND). Prize curve ASSUMED (1st $10,070 in the 150-max, fitted to the owner's cash points, the 6th-place tie average and the pool).

| contest | field | objective | held-out E[payout] | kept from selection worlds | P(any lineup near-optimal) | E[best score] | mean predicted copies | distinct CPTs |
|---|---|---|---|---|---|---|---|---|
| 196285137 | F_oracle | O0_production_frozen | $116.77 | 0.76 | 0.988 | 135.8 | 105.5 | 16 |
| 196285137 | F_oracle | O0R_objective_no_ladder | $169.64 | 0.86 | 0.965 | 135.6 | 136.3 | 10 |
| 196285137 | F_oracle | O1_ev_split | $143.06 | 0.18 | 0.860 | 131.7 | 1.1 | 15 |
| 196285137 | F_oracle | O2_hits_over_1_plus_copies | $108.90 | 0.31 | 0.911 | 132.0 | 0.5 | 19 |
| 196285137 | F_oracle | O3_ev_ignoring_copies | $176.70 | 0.62 | 0.962 | 135.9 | 121.7 | 9 |
| 196285137 | F_model | O0_production_frozen | $261.97 | 0.82 | 0.988 | 135.8 | 69.4 | 16 |
| 196285137 | F_model | O0R_objective_no_ladder | $619.58 | 0.94 | 0.965 | 135.6 | 107.3 | 10 |
| 196285137 | F_model | O1_ev_split | $822.84 | 0.52 | 0.911 | 133.9 | 1.6 | 13 |
| 196285137 | F_model | O2_hits_over_1_plus_copies | $452.92 | 0.68 | 0.935 | 133.4 | 0.4 | 18 |
| 196285137 | F_model | O3_ev_ignoring_copies | $572.52 | 0.59 | 0.956 | 135.7 | 90.5 | 9 |
| 196285160 | F_oracle | O0_production_frozen | $9.10 | 0.90 | 0.793 | 131.2 | 51.4 | 5 |
| 196285160 | F_oracle | O0R_objective_no_ladder | $10.76 | 0.89 | 0.769 | 130.8 | 44.1 | 5 |
| 196285160 | F_oracle | O1_ev_split | $16.66 | 0.55 | 0.611 | 127.6 | 0.7 | 7 |
| 196285160 | F_oracle | O2_hits_over_1_plus_copies | $13.66 | 0.70 | 0.688 | 129.1 | 0.0 | 5 |
| 196285160 | F_oracle | O3_ev_ignoring_copies | $12.59 | 0.90 | 0.689 | 129.3 | 65.7 | 4 |
| 196285160 | F_model | O0_production_frozen | $13.39 | 0.78 | 0.793 | 131.2 | 28.0 | 5 |
| 196285160 | F_model | O0R_objective_no_ladder | $18.41 | 0.90 | 0.769 | 130.8 | 20.4 | 5 |
| 196285160 | F_model | O1_ev_split | $35.02 | 0.73 | 0.564 | 127.1 | 0.5 | 5 |
| 196285160 | F_model | O2_hits_over_1_plus_copies | $24.48 | 0.85 | 0.677 | 129.5 | 0.0 | 6 |
| 196285160 | F_model | O3_ev_ignoring_copies | $27.53 | 0.74 | 0.646 | 128.6 | 10.0 | 4 |
| 196285161 | F_oracle | O0_production_frozen | $0.64 | 0.87 | 0.305 | 119.3 | 47.0 | 2 |
| 196285161 | F_oracle | O0R_objective_no_ladder | $0.64 | 0.87 | 0.305 | 119.3 | 47.0 | 2 |
| 196285161 | F_oracle | O1_ev_split | $0.94 | 0.47 | 0.250 | 118.3 | 1.0 | 2 |
| 196285161 | F_oracle | O2_hits_over_1_plus_copies | $0.91 | 0.50 | 0.245 | 118.1 | 0.0 | 2 |
| 196285161 | F_oracle | O3_ev_ignoring_copies | $0.53 | 0.89 | 0.230 | 116.6 | 73.0 | 2 |
| 196285161 | F_model | O0_production_frozen | $0.85 | 0.80 | 0.305 | 119.3 | 21.5 | 2 |
| 196285161 | F_model | O0R_objective_no_ladder | $0.85 | 0.80 | 0.305 | 119.3 | 21.5 | 2 |
| 196285161 | F_model | O1_ev_split | $2.56 | 0.69 | 0.229 | 115.3 | 0.2 | 1 |
| 196285161 | F_model | O2_hits_over_1_plus_copies | $2.64 | 0.91 | 0.282 | 119.1 | 0.0 | 2 |
| 196285161 | F_model | O3_ev_ignoring_copies | $0.72 | 0.55 | 0.252 | 118.3 | 17.0 | 2 |

**Reading this table correctly.** The held-out worlds come from OUR football model -- the same model that chose the lineups -- and that model has no demonstrated forecasting edge. In its own worlds every portfolio beats a field that does not share its projections, so the absolute ROIs (+50% to +1,000%) measure the model's self-confidence, not money. Only differences between objectives on the same worlds are informative, and even those inherit the model's beliefs.

**Findings.** (1) In the 150-max, expected-payout objectives are noise-chasing: with a ~$10,000 first prize and 237,812 entries, 2,000 worlds cannot estimate a lineup's expected payout -- the split-aware EV portfolio keeps only 18-52% of its selected value on held-out worlds, against 86-94% for the coverage objective re-implemented without the exposure ladder (O0R) and 76-82% for the frozen production portfolio. The duplication-aware variants are not better there under the realised field. (2) In the 20-max and 2-entry, the duplication-aware objectives earn more on held-out worlds under both fields; in the 20-max that costs 8-9 points of scenario coverage and 1.3-1.8 points of best-lineup score, in the 2-entry the cost is mixed (coverage -6 to +2 points). (3) **No duplication-aware objective is demonstrated better** given the self-evaluation problem. The realised ATL@NO result (one draw, reported, never used):

- 196285137: O0_production_frozen $134.27 (best rank 6); O0R_objective_no_ladder $121.39 (best rank 6); O1_ev_split $55.25 (best rank 938); O2_hits_over_1_plus_copies $41.23 (best rank 372); O3_ev_ignoring_copies $21.75 (best rank 6581)
- 196285160: O0_production_frozen $1.00 (best rank 9748); O0R_objective_no_ladder $1.00 (best rank 9748); O1_ev_split $1.27 (best rank 2543); O2_hits_over_1_plus_copies $2.39 (best rank 1938); O3_ev_ignoring_copies $1.80 (best rank 2543)
- 196285161: O0_production_frozen $0.00 (best rank 29262); O0R_objective_no_ladder $0.00 (best rank 29262); O1_ev_split $0.00 (best rank 29262); O2_hits_over_1_plus_copies $0.00 (best rank 29262); O3_ev_ignoring_copies $0.00 (best rank 17305)

## 6. Next-slate shadow comparison (the confirmatory test)

Tool: `nfl/field/showdown_dupe_shadow.py` (write-once, self-sealed, never read by selection). Dry run on the frozen ATL@NO inputs with ATL@NO excluded from training (model B4, trained on PIT_CLE):

| contest | our lineups | actual copies by others | current B0 | B4 (prelock-knowable) |
|---|---|---|---|---|
| 196285137 | 150 | 15,823 | 4,886.0 (3.2x low) | 10,417.2 (1.5x low) |
| 196285160 | 20 | 1,028 | 207.4 (5.0x low) | 559.9 (1.8x low) |
| 196285161 | 2 | 94 | 6.6 (14.2x low) | 43.1 (2.2x low) |

The remaining 1.5-2.2x is mostly ownership-forecast error (the forecast gave Brian Robinson Jr. ~1% FLEX; he was 17.6%) plus structure fitted on one slate.

## 7. Ranked recommendation

1. **Run the B4 shadow comparison before lock on the next Showdown** and commit it before kickoff (B3S as well if the slate lacks a public projection file). This is the pre-registered confirmatory test; it changes nothing.
2. **Report predicted copies of our lineups on the prelock board under B4 beside B0** (reporting only). The portfolio objective and lineups stay as they are.
3. **Do not adopt a duplication-aware objective yet.** The decision test cannot separate duplication value from trust in our own football model, and EV objectives are not estimable at 2,000 worlds in the 150-max. Before re-testing: an evaluation world source independent of the selection model, and a variance-controlled payout target (e.g. probability of a top-0.1% finish rather than expected payout).
4. **Ownership of cheap rotation players (SC-OWN-ROTATION-1) is the next largest lever** -- B4 with perfect ownership predicts our copies within 5% in the 150-max and 20-max (the 2-entry has only 2 lineups); with the frozen forecast it is 1.5-2.2x low.
5. Promotion of B4 requires the pre-registered bars on the prospective slates plus the owner's rule (proposal: >= 5 slates).

## 8. Separate successor tests, continued

- **SC-APPEAR-1 (playing-time probability): passes both halves of its held-out bar on 2025** (fit on 2024). Qualifying active players: Brier 0.1292 -> 0.05989 (week-blocked z 12.46); backups among them 0.24659 -> 0.0969; starters z -1.77 (inside the no-regression tolerance). Volume half: PASS under a PROXY if-plays volume (the production conditional volume was not replayed). Still SHADOW; promotion is the owner's decision and the allocator is unchanged.
- **SC-COH-1 (football-world coherence): NOT STARTED in this round** -- it needs a simulator change and a 2025 held-out simulation run, which could not be completed and validated before the next Showdown without risking the production path. Explicitly UNRESOLVED; the defect stays open on the readiness board.

## 9. Limitations

- Three slates, two of one contest type; PHI@CHI has no salaries or projections.
- ATL@NO is development data for every claim here.
- Ownership is ORACLE in the dependence test; prelock forecasts are tested only on ATL@NO.
- The universe (32 players) drops 0.2-0.7% of entries.
- Prize curves are assumed; self-competition between our own entries is ignored in the portfolio test.
- The portfolio test evaluates in our own model's worlds.
