# The receiver-dispersion benchmark is a small-sample statistic (ACC-D1); measure C3 registered for later builds

- **Written:** 2026-10-11 at about 20:12 UTC.
- **Order of events.** This was found AFTER the ECW-3 W5 result (`ECW3_RESULT.md`) and after SIM-D9's fit, decision
  and hold-out (`SIMD9_*.json`). ECW-3's W5 verdict (**NOT MET**) is not re-scored, and neither is ECW-2's.

## 1. SIM-D9 (PREREG_SIMD9.md): no simulator change

| target share band (s̄) | fit 2021-23 R (95%) | hold-out 2024-25 R | ECW-3 control worlds R |
|---|---|---|---|
| 0.10-0.18 | 1.155 [1.097, 1.211] | 1.142 | 1.150 |
| 0.18-0.25 | 1.197 [1.120, 1.282] | 1.150 | 1.189 |
| ≥ 0.25 | 1.121 [1.020, 1.225] | 1.128 | 1.188 |

R is the per-game target variance against a multinomial at the player's expected share.

- **H1 is REJECTED** by its pre-registered rule. No high-share interval lies below 1.205.
- The simulator's own R, measured the same way on its worlds, lies inside the fit intervals in every band that
  carries the receiver benchmark.
- **H2** (catches less dispersed than binomial) holds in the lowest-share band on the fit set (0.916). On the
  hold-out it holds in the lowest two bands (0.864, 0.885). The simulator draws catches binomially (0.96-1.00).
  - This is recorded as **SIM-D10, open**.
  - It is small, and it is not the cause of the receiver gap (see 2).

So the game-level dispersion of targets and catches is, on this measure, as history's.

## 2. Why the CV ratio still read 1.23: the benchmark's estimator

The benchmark (0.4514) is, for each player-season, the population SD over mean of receiving yards across his games
with > 2 catches, then the median. Those player-seasons have a **median of 10 such games** (mean 10.0, n 719).

- An SD from 10 values is biased low: pstdev has a factor of about sqrt(9/10) on top of c4. A median of small-sample
  CVs is lower again.
- The simulated CV was taken over about 1,000-2,000 worlds per receiver, so it is not biased.
- The ratio compared an unbiased number with a biased one.

Recomputed with the benchmark's own estimator at its own sample sizes: k worlds, k drawn from history's game counts,
pstdev over mean, median over 400 draws.

| worlds | registered C2 ratio | C3 ratio, same estimator and sample size | bar |
|---|---|---|---|
| incumbent 16:17Z (production) | 1.445 | 1.259 | [0.85, 1.15] |
| ECW-3 control | 1.229 | **1.085** | [0.85, 1.15] |
| ECW-3 with participation | 1.236 | **1.082** | [0.85, 1.15] |

- History's player-season CV also contains real week-to-week role change, which the simulator's fixed projection
  does not. That pushes the true ratio **lower** still, so C3 is conservative.

## 3. Registered now

- **C3.** The structural receiver-dispersion measure is the simulated CV computed with the benchmark's estimator at
  the benchmark's sample sizes. It is implemented in `ecw2_acceptance.py` as
  `receiver_cv_ratio_median_c3_history_sample_size` and `receivers_ok_c3`. The game counts are stored in
  `ECW2_INPUTS.json`; every other input there is unchanged.
- **Applies to:** builds after this registration (W6 onward). It never applies to W5.
- **Plainly:** C3 was chosen after the W5 numbers were seen. A W6 pass under it is **not independent evidence**.
  The world builder is unchanged, so it will very likely read about 1.08 again. C3 is a correction of the
  measurement, not a test of the model.
- The model's independent test is still PREREG_ECW2 section 3: prospective per-player CRPS, weeks 6-11, paired against
  the incumbent.
- `ALL_OK` in the acceptance output keeps using the registered C2 measure for W5.
