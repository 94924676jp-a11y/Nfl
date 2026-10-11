# PM-2 result (2026-10-11, about 19:26 UTC): VOID (degenerate participation factor) and a REUSED calibration failure

Protocol: `PREREG_PM2_PARTICIPATION.md` (`69fa882b`). Code: `pm2.py`. First and only run.

## 1. The participation factor φ is degenerate: VOID

- Every cell's φ quantiles came out 1.0.
- **Cause.** The registered running maximum starts at grid level u = 0. There the ratio is
  min(designated sample) / min(control sample), two unstable extremes, and it is ≥ 1 in every cell. So the running
  maximum is pinned at 1.
- The rule was implemented exactly as registered, and the rule is flawed.
- Under PM-2 section 5, changing the φ construction voids PM-2. The successor is PM-3.

## 2. REUSED 2024-2025 check

These seasons were read once before, for PM-1. Declared non-decisive.

| endpoint | estimate | 95% interval | bar |
|---|---|---|---|
| H-a: Brier improvement | 0.2227 | [0.1976, 0.2477] | met |
| H-c: CRPS improvement | 0.0920 | [0.0799, 0.1049] | met |
| H-b: calibration slope | **0.619** | **[0.430, 0.900]** | **not met: excludes 1** |
| H-b: calibration intercept | -0.048 | [-0.261, 0.189] | met |

- Splitting P(no participation) by role band makes the probabilities **overconfident** out of sample.
- PM-1, on the same seasons, gave slope 0.902 [0.692, 1.120].

## 3. What this decides, and the disclosure that goes with it

- PM-3 keeps **PM-1's P(no participation)**, which is validated, and uses the role band **only for φ**.
- **Disclosure:** keeping PM-1's P(no participation) instead of PM-2's was decided **after** reading PM-2's REUSED
  calibration. That choice is therefore informed by 2024-2025.
- PM-3's evidence for P(no participation) remains PM-1's held-out result, plus the in-season proxy check.
- PM-3's φ has no held-out evidence yet. Its primary evaluation is prospective (2026 weeks 6-11), with no REUSED
  score claimed for it.
