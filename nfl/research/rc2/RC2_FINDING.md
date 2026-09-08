# RC2 finding — `CALIBRATION_DEFECT_CONFIRMED`

Pre-registration sha256
`65c5e295ba864a1dc5b82f39f29667c295b100a66a80e4602129b6fc8f74db0e`, committed
before any repair was implemented or scored.

**EXPLORATORY.** 2022–2025 are heavily mined. Nothing is promoted.

## Result

| arm | CRPS | MAE | bias | r | cov50 (all / q25>0) | PIT χ² |
|---|---|---|---|---|---|---|
| **R0** control | 11.1798 | 17.298 | **+2.1801** | 0.6019 | 0.650 / 0.496 | 178.9 |
| **R1** draw-centring on `T` | **11.1545** | 17.141 | +1.6702 | **0.6031** | 0.638 / 0.481 | **135.9** |
| **R2** zero-mass recalibration | 11.2522 | 17.141 | **+0.8078** | 0.5960 | 0.681 / 0.532 | 76.6 |
| **R3** variance calibration | 11.4172 | 17.318 | +2.2420 | 0.6020 | 0.406 / 0.358 | **12,420.0** |
| **R4** all three | 11.4706 | **17.049** | **+0.4138** | 0.5959 | 0.426 / 0.367 | 11,409.6 |

Against the four predeclared criteria — `|bias| < 1.00`, CRPS not worse by more
than 0.5%, r not down more than 0.01, randomized PIT not worse:

| arm | bias | CRPS | r | PIT | verdict |
|---|---|---|---|---|---|
| R1 | ✗ 1.67 | ✓ **+0.226%** | ✓ +0.0012 | ✓ | **FAILS** (bias only) |
| R2 | ✓ 0.81 | ✗ −0.647% | ✓ −0.0059 | ✓ | **FAILS** |
| R3 | ✗ 2.24 | ✗ −2.124% | ✓ +0.0001 | ✗ | **FAILS** |
| R4 | ✓ 0.41 | ✗ −2.601% | ✓ −0.0060 | ✗ | **FAILS** |

**State: `CALIBRATION_DEFECT_CONFIRMED`.** The defect is real and located. The
predeclared repair family does not fix it inside the bounds that protect
discrimination and CRPS.

## What each arm actually showed

**R1 is the near miss, and it is the informative one.** It improves CRPS
(+0.226%), MAE, Pearson r (+0.0012) and randomized PIT (178.9 → 135.9)
*simultaneously* — every metric moves the right way — and cuts bias from 2.18 to
1.67. It fails on one criterion only, and that criterion was fixed in advance at
`< 1.00`. It is not promoted, and the bar is not moved to admit it.

**R1's fitted factors expose a two-sided defect the diagnosis only half saw.**

| history cohort | 2022 | 2023 | 2024 | 2025 |
|---|---|---|---|---|
| `<4` | 0.885 | 0.865 | 0.849 | 0.836 |
| `4-9` | 0.970 | 0.953 | 0.957 | 0.953 |
| `10-24` | 1.026 | 1.016 | 1.017 | 1.017 |
| `25+` | 1.054 | 0.983 | 0.945 | 0.940 |

Short-history rows need their target draws scaled **down ~15%**. That is the
opposite sign from the pre-registration's §1b table, and both are correct
measurements of different things:

- a short-history player's **own** prior-target mean **under**-predicts him (−0.345);
- but the **simulator** leans on the position pool for exactly those rows, and
  the pool mean (WR 4.103) badly **over**-predicts a low-usage player (actual 1.708).

The pool mixture's over-prediction dominates the own-history under-prediction.
Two real effects pointing opposite ways, and the net is a 15% over-prediction of
low-history players. Neither was visible without fitting the factor.

**R3 vindicates the pre-registration's refusal to target the coverage headline.**
R3 is exactly the "squeeze the intervals to move 0.650 toward 0.500" repair that
§1d argued would be attacking an artifact. It moved cov50 from 0.650 to 0.406 —
overshooting straight through nominal — and made randomized PIT **70× worse**
(178.9 → 12,420). CRPS fell 2.1%. Had the study targeted the coverage number
instead of the mechanism, R3 would have looked like the winner on the metric it
was aimed at while destroying the distribution.

**R2 buys bias with CRPS.** It reaches |bias| 0.81 and improves PIT to 76.6 —
the best PIT of any arm — but costs 0.647% of CRPS and 0.0059 of r. That is the
trade criterion 2 exists to catch, and it is reported as a loss rather than a win.

## What this does not say

It does not say the baseline cannot be repaired. It says **this closed family,
under bounds fixed in advance, does not repair it.** R1's direction is
promising and every one of its metrics improved; a future study would need its
own pre-registration and would have to explain why a factor fitted per history
cohort is calibration rather than a model change.

Nothing is promoted. P4C, ABC_MPR, Stage 2 `ewma_hl2` untouched. G0A 11/12.
NFL-1 NOT AUTHORIZED.
