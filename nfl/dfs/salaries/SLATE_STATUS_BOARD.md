# Slate status board

**SLATE STATUS: FALLBACK**  
Generated 2026-09-28T01:13:25Z · entry file `/home/user/nfl/nfl/dfs/salaries/raw/DKEntries_EARLY_ONLY_2026W3_62.csv`

## Projection coverage

| pos | rosterable | projected | % |
|---|--:|--:|--:|
| QB | 60 | 18 | 30.0% |
| RB | 107 | 37 | 34.6% |
| WR | 172 | 70 | 40.7% |
| TE | 100 | 29 | 29.0% |
| DST | 18 | 18 | 100.0% |

## Pipeline

| stage | state | code |
|---|---|---|
| ingest_slate | **PASS** | `SLATE_INGESTED` |
| verify_identity | **PASS** | `IDENTITY_VERIFIED` |
| availability | **PASS** | `AVAILABILITY_RESOLVED` |
| current_role | **PASS** | `ROLE_RESOLVED` |
| projections | **PASS** | `PROJECTIONS_READY` |
| candidate_generation | **PASS** | `CANDIDATES_GENERATED` |
| portfolio_selection | **PASS** | `PORTFOLIO_SELECTED` |
| legality_validation | **PASS** | `PORTFOLIO_LEGAL` |
| dk_upload_csv | **PASS** | `CSV_WRITTEN` |

## Portfolio

**48 legal lineups.** salary 46900–50000, projected total 140.37–150.45, max pairwise overlap 6/9 (mean 1.52), bring-back rate 50.0%.

QB exposure: {'Trevor Lawrence': '25.0%', 'Deshaun Watson': '20.8%', 'Patrick Mahomes': '16.7%', 'C.J. Stroud': '8.3%', 'Joe Burrow': '8.3%', 'Bryce Young': '6.2%', 'Drake Maye': '4.2%', 'Josh Allen': '2.1%', 'Justin Herbert': '2.1%', 'Aaron Rodgers': '2.1%', 'Malik Willis': '2.1%', 'Geno Smith': '2.1%'}

Stack sizes: {1: 31, 2: 17}

## Honesty

CORRELATION_HEURISTIC_NOT_SIMULATION. Structure comes from declared rules -- a quarterback with 1-2 of his own pass catchers, an optional opposing bring-back, never a team defence against our own quarterback. It does NOT come from simulated football, so ceiling, duplication and expected payout are UNKNOWN rather than estimated.

UNKNOWN by design: lineup_ceiling, duplication_probability, expected_payout, first_place_probability, projected_ownership

## Saturday rule

If the system cannot autonomously produce a complete legal lineup portfolio from a slate file by Saturday, it is not production-ready for Sunday. This run DID produce one.
