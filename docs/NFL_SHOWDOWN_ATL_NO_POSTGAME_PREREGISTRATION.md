# ATL @ NO Showdown (2026-10-05) — post-game pre-registration for the shadow field / ownership / dupe methods

Written before kickoff and before any outcome, ownership or standings for this slate exists. It is committed before
lock (00:15Z). Its purpose is to fix, in advance, what tonight's three standings files will be used to measure, so the
first Showdown observation cannot be read selectively.

Source of the methods: `nfl/research/external/2026-10-05_addendum/METHOD_CANDIDATES.json` (MC-OWN-1, MC-FIELD-1,
MC-DUPE-1, MC-ROLE-1). All are **PRODUCTION_CANDIDATE, NOT PROMOTED**. Owner ruling 2026-10-05: promotion requires
post-game AND multi-slate validation. **One slate promotes nothing.** Tonight is observation #1 for Showdown.

## What is frozen tonight (the predictions being scored)

Per scenario directory actually used for the final upload (BASE or FANT_OUT, whichever the official inactives select):

| Artifact | What it predicts |
|---|---|
| `SHADOW_<scen>/SHOWDOWN_ATL_NO_SHADOW_OWNERSHIP.csv` | FC_ONLY optimizer-exposure field: CPT and FLEX ownership per player |
| `SHADOW_<scen>_BLEND/SHOWDOWN_ATL_NO_SHADOW_OWNERSHIP.csv` | BLEND (mean of FC and ours) optimizer-exposure field: CPT and FLEX ownership |
| `<scen>/SHOWDOWN_ATL_NO_DUPE_STACK_{FC_ONLY,BLEND}.json` | per production lineup: E1 independent product, E2 ETR-seeded adjusted, E3 archetype-field count, E4 optimizer-field count; archetype-field salary-left distribution |
| `<scen>/SHOWDOWN_ATL_NO_SHADOW_BOARD_{FC_ONLY,BLEND}.json` | team-split distribution of each shadow field |

Their sha256 are recorded in the final prelock board. Nothing is re-run after lock to "improve" them.

## Measurements (all three contests separately: 196285137 P150, 196285160 P20, 196285161 P2)

1. **Ownership, CPT and FLEX separately.** For FC_ONLY and BLEND: RMSE and MAE in percentage points against DK
   %Drafted, Spearman rank correlation, and the share-weighted log-loss of predicted against actual shares. Players
   above 5% actual ownership reported individually. The archetype field reproduces BLEND or FC_ONLY marginals by
   construction, so it is not scored separately on ownership.
2. **Duplication.** For each of our lineups, and for the 50 most-duplicated lineups in each contest: actual copies vs
   E1, E2, E3 (both phi values beyond 200 as sensitivity), E4. Metric: median absolute log-ratio
   `|log((pred+1)/(actual+1))|`, Spearman, and the share of `E1_E3_DISAGREE_GT_2X` flags where the actual count sits
   closer to E3 than to E1 (the flag's own claim).
3. **Archetypes.** Actual field rates of team split (5-1 … 1-5), QB count, K+DST count and CPT pass-catcher with own QB
   against the optimizer-field prior used tonight.
4. **Salary left.** Actual field distribution ($0, ≤$900, $1,000–1,900, ≥$2,000) against the archetype field and the
   optimizer field.
5. **Conflicts from the addendum.** CF-1: CPT position share, field vs top 1%. CF-2: R² of log(product ownership) vs
   log(dupes+1). CF-3: dupes regressed on CPT ownership vs FLEX product ownership. Reported as one slate's numbers,
   not as a resolution.

## Rules fixed now

- Results are recorded as observation #1 in a per-slate ledger; nothing is promoted, retuned or re-labelled on them.
- No coefficient (phi, ETR seeds, archetype priors) is refitted on tonight and then scored on tonight.
- The football model is graded by the existing post-game process; MC-ROLE-1 is not evaluated tonight.
- The minimum number of Showdown slates before any promotion decision is the owner's to set. Proposal only: at least
  8 Showdown slates, with the Dirichlet ownership model (MC-OWN-1) required to beat the optimizer-exposure baseline
  out of sample before it replaces it.
- Standings must be captured with provenance (raw file, sha256) under `nfl/postgame/raw/`, never overwriting a capture.
