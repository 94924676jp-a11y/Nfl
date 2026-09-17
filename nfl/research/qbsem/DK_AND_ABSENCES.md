## DraftKings points — the column BOARD.md does not render

Unconditional over all 8,000 worlds, the same contract as every other
published mean. `V` = V1_CANDIDATE_R9_W1P_GSVU (provisional leader),
`Q` = V1_CANDIDATE_R9_W1P_GSVUQ (QBSEM, WITHDRAWN — shown for the delta only).

| Player | Tm | Pos | DK mean (V) | P10 | P50 | P90 | P(0 pts) | DK mean (Q) | Δ |
|---|---|---|--:|--:|--:|--:|--:|--:|--:|
| Jahmyr Gibbs | DET | RB | **22.27** | 9.2 | 21.7 | 36.2 | 0.0471 | 22.35 | +0.08 |
| Josh Allen | BUF | QB | **22.00** | 9.1 | 20.8 | 36.5 | 0.0044 | 22.75 | +0.75 |
| Amon-Ra St. Brown | DET | WR | **18.60** | 6.0 | 16.5 | 33.9 | 0.0135 | 18.70 | +0.10 |
| Jared Goff | DET | QB | **17.39** | 7.7 | 16.2 | 28.6 | 0.0039 | 18.04 | +0.65 |
| Khalil Shakir | BUF | WR | **11.54** | 0.0 | 9.5 | 25.7 | 0.1288 | 11.64 | +0.11 |
| Jameson Williams | DET | WR | **10.69** | 0.5 | 8.6 | 23.5 | 0.0915 | 10.69 | +0.00 |
| Sam LaPorta | DET | TE | **9.61** | 1.3 | 8.0 | 20.1 | 0.0901 | 9.57 | -0.04 |
| James Cook | BUF | RB | **8.83** | 0.0 | 6.5 | 22.4 | 0.3718 | 8.82 | -0.01 |
| DJ Moore | BUF | WR | **8.09** | 0.0 | 6.0 | 19.0 | 0.1601 | 8.03 | -0.06 |
| Ray Davis | BUF | RB | **7.04** | 0.0 | 4.5 | 18.1 | 0.1914 | 7.07 | +0.03 |
| Keon Coleman | BUF | WR | **6.10** | 0.0 | 3.8 | 15.7 | 0.2797 | 6.09 | -0.01 |
| Dalton Kincaid | BUF | TE | **5.85** | 0.0 | 3.9 | 14.9 | 0.3108 | 5.75 | -0.10 |
| Josh Palmer | BUF | WR | **4.90** | 0.0 | 2.5 | 13.4 | 0.3545 | 4.86 | -0.04 |
| Dawson Knox | BUF | TE | **4.65** | 0.0 | 2.3 | 12.7 | 0.3995 | 4.72 | +0.07 |
| Frank Gore Jr. | BUF | RB | **4.25** | 0.0 | 1.4 | 12.9 | 0.4073 | 4.17 | -0.08 |
| Brock Wright | DET | TE | **3.91** | 0.0 | 2.1 | 10.5 | 0.3359 | 3.92 | +0.01 |
| Isaac TeSlaa | DET | WR | **3.49** | 0.0 | 1.4 | 10.6 | 0.4891 | 3.46 | -0.03 |
| Skyler Bell | BUF | WR | **3.47** | 0.0 | 1.1 | 10.6 | 0.4933 | 3.45 | -0.03 |
| Sione Vaki | DET | RB | **3.27** | 0.0 | 0.7 | 9.9 | 0.4330 | 3.30 | +0.03 |
| Jackson Hawes | BUF | TE | **2.89** | 0.0 | 0.0 | 9.2 | 0.5389 | 2.90 | +0.01 |
| Keleki Latu | BUF | TE | **2.50** | 0.0 | 0.0 | 8.0 | 0.5607 | 2.52 | +0.02 |
| Tyler Conklin | DET | TE | **2.28** | 0.0 | 0.0 | 7.5 | 0.5639 | 2.29 | +0.01 |
| Tay Martin | DET | WR | **1.73** | 0.0 | 0.0 | 6.0 | 0.7834 | 1.70 | -0.02 |
| Jackson Meeks | DET | TE | **1.67** | 0.0 | 0.0 | 5.6 | 0.6685 | 1.71 | +0.04 |
| Joshua Dobbs | DET | QB | **0.99** | 0.0 | 0.0 | 1.7 | 0.7953 | 0.26 | -0.72 |
| Kyle Allen | BUF | QB | **0.83** | 0.0 | 0.0 | 1.3 | 0.7991 | 0.22 | -0.61 |
| Tom Kennedy | DET | WR | **0.69** | 0.0 | 0.0 | 1.8 | 0.8734 | 0.72 | +0.03 |
| Greg Dortch | BUF | WR | **0.14** | 0.0 | 0.0 | 0.0 | 0.9496 | 0.15 | +0.01 |
| Jacob Saylors | DET | RB | **0.00** | 0.0 | 0.0 | 0.0 | 1.0000 | 0.00 | +0.00 |

## What this board does NOT produce, named rather than estimated

| Requested quantity | State | Why |
|---|---|---|
| **Kicking** (FGA, FGM, XPA, XPM, kicker DK) | **MODELLED BUT NOT PUBLISHED** | ~~ABSENT — no kicker is in the room~~ **That was wrong and is withdrawn.** The `kicking` layer carries TWO rows with full distributions; `board["players"]` omits them, so `BOARD.md` renders no kicking section. The numbers are in `KICKING_CORRECTION.md`. |
| **Rushing yards for RB / WR / TE** | **UNAVAILABLE** | `RUSHING_CONVERSION_CONTROL_UNDEFINED`. No governed control exists for carry → rushing yards; three owner decisions are open. `carries × YPC` is named in `layers.py` as the prohibited implementation and is not computed. |
| **Passer rating** | **UNAVAILABLE** | `NO_RATE_COMPOSITE_LAYER`. A composite of forecast components is not itself a forecast distribution. |
| **Air yards / aDOT** | **UNAVAILABLE** | `NO_AIR_YARDS_LAYER`. V1 forecasts no air-yards distribution. |

Quarterback rushing yards ARE produced (`qb/ryds`) and are marked provisional:
the QB layer draws yards per rush from the passer`s own history mixed with the
positional pool, which is adjudicated, unlike the RB control.

## Provisional layers carried on every row that uses them

- **Passing TD**, **Receiving TD**, **Rushing TD** — TD2 pooled positional control, governance `HOLD_TENTATIVE`
- **Receiving yards** — RC1 baseline, frozen governance `SIGNAL_WEAK` with a declared `CALIBRATION_DEFECT`
- **QB rushing yards** — provisional as above
