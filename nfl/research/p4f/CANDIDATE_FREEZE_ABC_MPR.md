# Frozen candidate — `ABC_MPR`

**Candidate frozen for prospective evaluation; NOT promoted.**

P4C system C remains the accepted carry-allocation architecture and is not
modified by this document. Nothing here is a production change.

Frozen 2026-09-08 under `predeclaration_p4f.md` §12, after the P4F return.

## Why it is frozen rather than promoted

2022–2025 have already exposed the exploratory mean-preserving result, so no
result on those seasons can promote this candidate. It survived the
mechanistic requirements and the adversarial suite, which is what §12 asks
a freeze to establish — not that it is better, but that it is well defined,
reproducible and not leaking.

## Algorithm

P4C system C reconciliation, unchanged, applied to a pre-reconciliation weight whose centre is a ridge fit on prior-only features and whose draws are shifted by a deterministic mean-preserving rectification.

## Feature set

Base share history:

- `g_sh_ewma`
- `g_sh_mean`
- `g_sh_last4`
- `g_sh_last8`
- `g_sh_sd`

Block **A**:

- `g_n_games`
- `g_n_app`
- `g_car_career`
- `g_car_prev_season`
- `g_car_last4`
- `g_car_last8`
- `g_car_last10`

Block **B**:

- `g_prev_rank`
- `g_rank_persist`
- `g_rank_sd`
- `g_top_share_prev`

Block **C**:

- `g_team_hhi`
- `g_team_entropy`
- `g_n_rb_used`
- `g_teammate_share_sum`
- `g_n_competitors`
- `g_teammate_hist_depth`
- `g_teammate_app_rate`

No other block. Blocks D (role change) and E (carry/snap) were evaluated in
P4E and contribute nothing; they are excluded by this freeze, not omitted by
oversight.

## Solver

| field | value |
|---|---|
| `method` | bisection on the IVT bracket |
| `bracket_lo` | C + min_m eps - (hi - lo) |
| `bracket_hi` | C + max_m eps |
| `iterations` | 80 |
| `dtype` | float64 |
| `tolerance_abs` | 1e-09 |
| `degenerate_flag` | DEGENERATE_SOLUTION_SET at C in {0,1} |
| `infeasible_flag` | INFEASIBLE_ROW, never silently altered |

## Residual construction

out-of-fold, expanding-window replay inside the training block; residual pool resampled per position with the same generator seed as the control, so candidate and control share a draw sequence

## Ridge

- penalty grid: [0.03, 0.1, 0.3, 1.0, 3.0, 10.0, 30.0, 100.0]
- selection: inner validation on the last training season, never the evaluation season

## Seeds and draw protocol

| field | value |
|---|---|
| `M_DRAWS` | `1000` |
| `base_seed` | `20260907` |
| `weights` | `SEED + 3034` |
| `mass` | `SEED + 5002` |
| `appearance` | `SEED + 1009` |
| `scoring` | `SEED + 31` |

## Artifact hashes

Source files, as frozen:

| file | sha256 |
|---|---|
| `p4f_mpr.py` | `eb479d2e10fd43dc6b034233a44b259bf97b748aa4a81124929c644f2012a13e` |
| `p4f_common.py` | `754646463c0e412dbfe0a15f16925e7217db7a6f1ae268e14114f154ed3f67ab` |
| `run_p4f.py` | `0d322da675e647e4fd02d6c5ce4412753818f5c964e6819c1e1bf961a69a166f` |
| `p4e_build.py` | `3263b11cfbd67ad8d8ace46f88f5408bb54e262431e1a86b66e79de8e9a75d59` |
| `p4e_fit.py` | `8b85d3907347cc29c43dda9437a898768cbd856e7ed17945233a96de5fd37ae5` |
| `p4c_build.py` | `831cce1a3d68461c9281430e1f7f0f6c43583cbda375cac34f51d27aa3593375` |
| `p4c_lib.py` | `f61f76e53850c1d05f0a02cbdab03d2054d22058a247b2ed3e52b78dfa31195b` |
| `p4c_results.json` | `5d8d34c22c01203e52534a1281a14bc6f078b59149d56bb28dce43b8e30845c3` |

Input artifacts. **These are not in the repository** — the same debt P4B and
P4C carry. A prospective run must verify these hashes before it may claim to
be the same experiment; if it cannot, it is a new input generation and this
freeze does not describe it.

| artifact | sha256 | in repository |
|---|---|---|
| `panel_enriched.pkl` | `7bbc8cb255dc0c0e9545f3ffb01bfe9b7416aecd3707f70dcf420c43f74c50e9` | False |
| `volume_store.npy` | `c47a52903bb038cec0088f243fb431623c4c8a093a62020e8e3f11caf7633365` | False |

## Eligibility rules

1. evaluation seasons 2022-2025 are development data and can never promote this candidate
2. promotion requires prospective evidence under a separately pre-declared rule
3. the appearance model, team-volume draw and reconciliation are frozen imports and may not change without re-freezing
4. no market data, no observed weather, no weekly_rosters.status, no present-week depth-chart state, no 2026 outcomes
5. the accepted P4C production and research architecture is not modified by this freeze

## Development-sample record, for reference only

Carried here so a future prospective run has something to compare against.
**It is not evidence of quality**: these seasons selected this candidate.

| quantity | value |
|---|---|
| pooled carry CRPS | 1.9831 |
| delta against P4C | -0.0376 |
| seasons better than P4C | 4/4 |
| solver max abs centre error | 5.6e-16 |
| infeasible rows | 0 |
| degenerate-solution rows (flagged) | 367 |
| randomised PIT by season | [18.3, 8.4, 11.4, 11.4] |
| RB1–RB2 matched criterion | PASS |
| adversarial FAIL | 0 |
| residual allocation ceiling | 96.3% of P4C's |

