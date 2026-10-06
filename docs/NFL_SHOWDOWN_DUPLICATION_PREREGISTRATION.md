# Showdown complete-lineup duplication — pre-registration (DEFECT-DUPE-UNDERESTIMATE)

Written 2026-10-06 **before any model below was fitted or scored**. Committed before the evaluation code runs.
Status of everything here: **SHADOW_ONLY**. Nothing changes the football forecast, the DFS portfolio objective,
the readiness rules or any production lineup.

Evidence being explained: `nfl/postgame/showdown_atl_no_2026W4/evidence/DEFECT_DUPE_UNDERESTIMATE.json` (immutable).

## Contamination, stated first

The defect was discovered on ATL@NO, and the candidate features below were chosen after seeing it. Every ATL@NO fold
is therefore **development data**. The PIT@CLE and PHI@CHI folds are less contaminated (their fields were not used to
choose the hypothesis) but the feature list was still written after ATL@NO. **All results are EXPLORATORY.** The
confirmatory test is prospective: the next-slate shadow comparison (section 6), scored after that slate.

## 1. Slates and strict separation

| slate | contest(s) | filled entries | salaries | public projections (FC) |
|---|---|---|---|---|
| PIT_CLE | 196187080 (20-max) | 47,329 | yes (DK pool) | yes (context file) |
| PHI_CHI | 196036243 (20-max) | 47,333 | **no** | **no** |
| ATL_NO | 196285160 (20-max, training slate), 196285137 (150-max) and 196285161 (2-entry): test only | 47,308 / 237,105 / 59,083 | yes | yes |

A slate's field is never used to fit anything scored on that slate. Models needing salaries or FC projections can only
be tested PIT_CLE <-> ATL_NO (two folds); salary-free models are tested on all three (train on the other two).

## 2. Support (the lineup universe)

Per test contest: the 32 players with the most entry appearances; every lineup of 1 CPT + 5 distinct FLEX from them;
salary <= $50,000 where salaries exist. Entries using any other player are outside the universe; their share is
reported and they are excluded from the log score. Unplayed lineups (0 copies) are in the universe, so calibration is
scored on zeros as well as on observed lineups (the earlier observed-only analysis was truncated).

## 3. Ownership input

**ORACLE** (the test contest's actual slot shares) for the dependence question: given perfect ownership, how wrong is
each ownership-to-lineup mapping? **FORECAST** (frozen prelock BLEND and FC_ONLY ownership, ATL@NO only) for the
decomposition into ownership-forecast error versus dependence error.

## 4. Model ladder (simplest first)

| id | model | structural parameters |
|---|---|---|
| B0 | E1 independence, N x CPT share x product of FLEX shares (current) | none |
| B0n | B0 renormalised over the feasible universe | none |
| B5 | B0 x one inflation constant (training sum actual / sum B0) | 1 |
| B6 | B0 x inflation by salary-left bucket | 5 |
| B1 | MAXENT: q proportional to exp(a_cpt + sum b_flex) on the feasible universe, a, b matched exactly to the slot marginals | none |
| B2 | B1 + salary-left buckets (0 / 100-500 / 600-900 / 1000-1900 / 2000+) | 4 |
| B3 | B2 + construction: CPT WR/TE with own QB; both QBs; team split; any K or DST | +5 |
| B3' | B1 + construction only (salary-free; all three slates) | 5 |
| B4 | B3 + optimizer term: lineup FC projection minus the best feasible FC projection (points), and top-100-FC indicator | +2 |
| B7 | Poisson regression of copies on the universe: log B0 + B4's features, no marginal constraint | 12 |
| E3 | existing archetype generator, scored only where already computed; not refitted | - |

Structural parameters are fitted by maximum likelihood of the TRAINING field, with the training slate's own a, b
re-solved to its own marginals at each step. On the test slate a, b come from the test slate's ownership only (the
ownership input), never from its lineup counts.

## 5. Metrics (per held-out contest) and bars

Metrics: (a) log score per in-universe entry, normalised models (B0n stands in for B0); (b) calibration of total
predicted vs actual copies in predicted-copy bins [0, 0.1), [0.1, 1), [1, 3), [3, 10), [10, 30), [30, 100), [100, inf);
(c) high-duplication tail: median |log((pred+1)/(actual+1))| on the 50 most-duplicated lineups, and actual / predicted
over the 1,000 highest-predicted lineups; (d) optimizer lineups: actual / predicted summed over the 150 best feasible
lineups by FC projection, and on ATL@NO over OUR 150 / 20 / 2 lineups; (e) the same split by salary-left bucket,
captain position and (ATL@NO) contest size; plus self-duplicates (same user) vs cross-user duplicates.

A model is a **CANDIDATE** only if, on EVERY held-out fold available to it: (1) its log score beats B0n and B1;
(2) actual / predicted over the top-1,000 predicted lineups is within [1/1.5, 1.5]; (3) actual / predicted over the
optimizer lineups (d) is within [1/1.5, 1.5]; (4) it beats B5 (the one-constant baseline) on (2) and (3). A
CANDIDATE stays SHADOW_ONLY until it also passes the prospective next-slate test and the owner approves promotion.
Failing is a valid result; no threshold is loosened afterwards.

## 6. Portfolio decision test (frozen ATL@NO worlds)

Candidate pool: the sealed v2 candidates (5,000). Selection on the sealed worlds (seed 20261005); evaluation on the
held-out worlds (`HOLDOUT_SEED2`, seed 20261006). Contests separate (150 / 20 / 2). Payout: an ASSUMED top-heavy
prize curve per contest (power law in place, scaled to the contest's stated prize pool, fitted to the owner's observed
cash points), with DK's tie rule (tied entries split the prizes of the places they occupy). Field: (F-oracle) the
realised field composition of that contest, and (F-model) a field drawn from the best dupe model with the FROZEN
prelock BLEND ownership (what was knowable before lock).

| id | objective |
|---|---|
| O0 | current production portfolio (frozen v2, E[min(hits, m)]) |
| O1 | greedy expected split-payout value |
| O2 | current proxy with each hit divided by (1 + predicted copies) |
| O3 | O1 with copies set to zero (separates "expected value" from "split") |

Reported separately: projected lineup strength (E[best score], mean projection), predicted duplication, scenario
coverage (share of worlds where any lineup reaches the first-place proxy), distinct captains, and expected
split-payout value. The realised ATL@NO outcome is reported as one draw and is never used to choose an objective.

## 7. Next-slate shadow comparison (the confirmatory test)

Before lock on the next Showdown, record for every production lineup the predicted copies under B0 and under the
best model from section 5 (frozen ownership forecast), and the O0 vs O1 portfolio differences. Score after the
slate's standings arrive. One slate is one observation; promotion needs the owner's rule (proposal: >= 5 slates).

## 8. Known limitations

Three slates, two of one contest type; PHI@CHI has no salaries or projections; ownership is oracle in the dependence
test; the universe drops 0.2-0.7% of entries; payout curves are assumed, not exported; ATL@NO is development data.
