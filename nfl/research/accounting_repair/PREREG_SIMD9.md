# SIM-D9 pre-registration: per-player target-share and catch dispersion by role, measured before any change

- **Written:** 2026-10-11 at about 20:08 UTC, after `ECW3_RESULT.md` and before any of the measurements below were
  computed. The commit time is authoritative.
- **Defect:** in the published worlds, the per-player target share, conditioned on > 2 catches, has CV 0.314 against
  history's 0.287 (1.10x). Catches have CV 0.371 against 0.304 (1.22x). Club target volume is right (0.224 against
  0.225).
- **Status:** PRE-REGISTERED, SHADOW ONLY. Any change applies to the CORRECTED_V1 arm alone. The incumbent is not
  edited.

## 1. Hypotheses (written before measuring)

| | hypothesis | where it lives |
|---|---|---|
| **H1** | One Dirichlet concentration for every receiver (150.6, `VARIANCE_COMPONENTS.json`, all player-seasons pooled) is wrong by role. Low-share receivers are over-dispersed against the multinomial and high-share receivers less so, or under-dispersed, while the benchmark population is the high-share end. | `nfl/sim/game.py` `alloc`, `model.share_conc_tgt` |
| **H2** | Catches given targets are less dispersed than binomial(targets, catch rate) for the same population. | `nfl/sim/game.py` catch draw (`_binom(tgt, catch_rate)`) |

## 2. Measurement

- **Data:** 2021-2023 REG play-by-play (`nfl/research/postgame/pbp_<season>`) is the **fit** set. 2024-2025 is
  **held out** and read once, after section 3 is fixed. No 2026 game is read.
- **Unit:** a player-game with ≥ 1 target, in a club-game with ≥ 15 targets. The player's season mean share s̄ (target
  share of club targets) is his expected share.
- **Bands of s̄:** < 0.10, 0.10-0.18, 0.18-0.25, ≥ 0.25. These are fixed here.
- **H1 statistic, per band:** the over-dispersion ratio R_b is Σ(t − n·s̄)² over Σ n·s̄(1 − s̄), where t is the
  player's targets and n the club's targets in that game. It is the variance against a multinomial at the player's
  expected share, the same form `variance_components.py` uses pooled.
  - The concentration is a_b = (n̄_b − R_b) / (R_b − 1).
  - When R_b ≤ 1, no Dirichlet reproduces it. That band is recorded as **UNDER_DISPERSED**, and the multinomial is the
    nearest admissible draw: the concentration is infinite, which means no share noise.
- **H2 statistic, per band:** Σ(c − t·r̄)² over Σ t·r̄(1 − r̄), where c is catches and r̄ the player-season catch rate.
- **Uncertainty:** a club-season block bootstrap, B = 2,000, seed 20261011, 95% intervals.
- **Within-season role drift** inflates both ratios, because s̄ is a season mean and not a per-game expectation. The
  direction is known and declared: these ratios are upper bounds on true game-level dispersion.

## 3. Change, conditional on the fit (fixed now)

- If H1 holds on the fit set (the high-share bands' R_b interval lies below the pooled 1.205):
  - the CORRECTED_V1 arm draws each receiver's share with his band's concentration (by his projected share);
  - a band that is UNDER_DISPERSED draws it with no share noise.
  - Otherwise H1 is rejected and nothing changes.
- If H2 holds (a ratio interval below 1 in any band), the catch draw is not changed here. A less-than-binomial
  catch draw needs its own model, which is declared as open.

## 4. Acceptance

- The held-out 2024-2025 band ratios fall inside the fit intervals, or the change is VOID.
- The ECW structural acceptance (PREREG_ECW2 s.2 with PREREG_ECW3 C2) is re-run on the W5 replay, both arms, with
  the bar unchanged: [0.85, 1.15].
- The incumbent replay stays byte-identical in projections and worlds.

## 5. Voids

- Reading 2024-2025 before section 3's decision is recorded.
- Any change to the bands, the statistic or the bar after the fit is computed.
