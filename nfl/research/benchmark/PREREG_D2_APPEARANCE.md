# Pre-registration D2: player-level appearance probability, hierarchical and role-conditioned (mandate b0540a52)

**Written** 2026-10-14, after FORECAST_ERROR_ATLAS (2024 dev) and **before any D2 code exists**. The commit time is
authoritative.

## Diagnosis this rests on (2024 development only)

**APPEAR-D1.** The incumbent's P(plays) is a depth-slot occupancy rate assigned to the player predicted at rank k.
- It is 1.0 on 93.4% of pool rows, while 60.4% appear.
- Appearance Brier: incumbent 0.372, naive own-history rate 0.196.
- Among players who appeared in their club's last game, the incumbent says 0.97 and 0.77 appear.

## Challenger

**Scope.** Every pool player, every volume field: targets, carries, pass attempts.

**Rule.** After `allocate_opportunity` and before `finalize`, the appearance factor is replaced. For field f, with
incumbent factor `p_i = p_plays[f] > 0` and new factor `q_i`:

    u_i = r_i[f] × q_i / p_i
    r_i'[f] = M_f × u_i / Σ_j u_j

- `M_f` = Σ_j r_j[f] over the club's pool players with `p_j > 0`, so every club total is preserved exactly.
- A player with `p_i = 0` or no factor is left unchanged.
- Touchdowns follow the opportunities, as in the incumbent (D1 amendment 1). The club TD pool and the rates are
  untouched.

**The new factor.** A beta-binomial posterior mean:

    q_i = (n_i + κ × m_role(i)) / (N_i + κ)

- `n_i`: his appearances (a box-score row with a club) in the evaluated season, in weeks before W.
- `N_i`: the number of games his pool club played before W in the panel, floored at `n_i`.
- `role(i)`: (position, predicted depth rank in the allocation — 1, 2, 3, or 4 and beyond —, appeared in the club's
  most recent game before W: yes or no).
  - The rank is the allocator's own `depth_rank_in_group` on the position's table field (QB pass attempts, RB
    carries, WR/TE targets).
  - Every element is known before the game.

**Ablations.** All are scored on the same rows. Each is reported; none is selected on a holdout.

| arm | q_i |
|---|---|
| D2-NONE | 1 (no appearance discount, still scored unconditionally) |
| D2-CURRENT | p_i (the incumbent; golden: must reproduce it exactly) |
| D2-SHRINK | m_role = one pooled rate for all roles |
| **D2-ROLE** (the registered challenger) | m_role by role, as defined above |

**Parameters, estimated on training vintages 2022–2023 only.**
- **m_role:** the observed appearance rate of forward-chain pool rows in that role (STRICT vintage, production
  settings). A role with fewer than 30 training rows falls back to its position's pooled rate.
- **κ:** a single value per arm, from the grid {0.5, 1, 2, 3, 5, 8, 13, 21}, minimising training-row Brier of `q`
  against appearance.
- Both are written to `D2_PARAMS.json` **before 2024 is scored with D2**. Nothing is re-fitted afterwards.

## Evaluation

| step | rule |
|---|---|
| **2024 development** | All four arms against the incumbent and the naive STD_U baseline. Unconditional DK MAE (primary), conditional MAE, appearance Brier and log loss, by position and by the last-game stratum. Week-blocked bootstrap, 10,000, seed 20261014. Descriptive: 2024 diagnosed the problem, so it cannot confirm the fix. |
| **2025, one look, logged** (`HOLDOUT_LOOKS.jsonl` look 2) | D2-ROLE against the incumbent, same metrics. **Labelled PREVIOUSLY_INSPECTED_SEASON:** 2025 aggregates were seen in PLAYER_SCORECARD (2024–25 pooled) and in the D1 look, so this is a first look at D2 on a non-pristine season, not a clean holdout. **Pass**, identical to D1 with no margin: the upper 95% bound of D2-ROLE − incumbent unconditional MAE is below 0, **and** no position is worse with an interval excluding 0, **and** appearance Brier is below the incumbent's. |
| **Confirmatory, W6 onward** | Only a prelock prospective arm can confirm. That needs a shadow implementation on the slate path, which does not exist; it is queued as engineering. Until it exists, D2 is **NOT_CONFIRMED** whatever 2025 shows. |
| **Failure** | Recorded and preserved. A different role definition or grid is a new pre-registration. |

**What this is.** An equal-information (no-news) test of the football core's appearance probability. It says nothing
about how D2 would interact with production's injury and roster evidence. That interaction is part of the prospective
design.

**Not authorized here.** Promotion. Any production default. `proj_v1.py` is not edited; D2 is an opt-in
forward-chain arm.
