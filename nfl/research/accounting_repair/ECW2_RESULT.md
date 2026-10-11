# ECW-2 result (2026-10-11, about 19:47 UTC): structural acceptance NOT MET (receiver dispersion)

Two CORRECTED_V1 replays of the W5 2026-10-11 slate, on the 16:17Z state, in overlays: with participation, and
without it (control). Checked with `ecw2_acceptance.py`.

| criterion (PREREG_ECW2 section 2) | incumbent 16:08Z | ECW-2 control | ECW-2 with participation | bar |
|---|---|---|---|---|
| accounting violations, all laws | 35,234 | **0** | **0** | 0 |
| tie share, max game | 0.10% | 0.25% | 0.25% | ≤ 0.6% |
| receiver single-game yards CV / history 0.451, all worlds (as the bar was computed) | 1.63 | 1.67 | 1.70 | [0.85, 1.15] |
| the same, **like-for-like**: worlds with > 2 catches, as history is | 1.445 | 1.369 | — | — |

## Verdict

- **NOT MET**, on receiver dispersion.
- Accounting and ties pass.
- On the like-for-like measure ECW-2 is narrower than the incumbent: 1.37 against 1.45. ECW-1 was wider than the
  incumbent.

## Cause, measured

| quantity | value |
|---|---|
| club yards per target across worlds (CV) | 0.377 |
| the same in history, club-game against club-season mean | 0.235 (2,697 club-games, 2021-2025) |
| catch-level noise inside the historical figure (0.85 / sqrt(about 21 catches)) | about 0.19 |
| implied pure club-efficiency factor | about sqrt(0.235² - 0.19²) ≈ 0.14 |

ECW-2 draws the club factor from the raw simulator's per-world ratio. Its spread is roughly 2.7 times that.

## What follows

- ECW-2 stands as recorded.
- ECW-3 (`PREREG_ECW3.md`) changes the club factor's spread to the derived value, and fixes how the bar is computed
  to match the benchmark's conditioning.
