# Week 4 Early Only — postgame forensic review (graded against the lock)

**Lock:** commit `039cfd0e`, upload sha256 `bf50aaee…ca06899`, forecast seal 2026-10-04 16:01Z (kickoff 17:00Z).
Every pregame object was read from the lock commit; no projection or lineup was regenerated.

**Results:** nflverse `stats_player_week_2026.csv` (release `stats_player`) and nfldata `games.csv`, both retrieved
by this machine 2026-10-05, stored read-only under `nfl/postgame/raw/2026W4/` with sha256 and provenance. The eight
final scores match the owner's cross-check exactly. Our DraftKings scoring reproduces nflverse's fantasy points for
all 182 skill rows after the documented rule differences (0 mismatches). **DraftKings standings: not yet ingested**, so
finish, cash, ROI, field ownership and the winner's lineup are not graded here.

Machine-readable: `DK_2026W4_EARLY_POSTGAME.json`, `…_POSTGAME_REPORT.json`, and the CSVs beside this file.
One slate is eight correlated games: everything below is an observation for the ledger, not a calibration or skill estimate.

## 1. Projections (201 projected players)

| | n | MAE | RMSE | bias (actual − proj) | Spearman |
|---|---|---|---|---|---|
| ALL | 201 | 4.45 | 6.46 | +0.22 | 0.68 |
| QB | 17 | 5.28 | 5.97 | −0.30 | 0.44 |
| RB | 55 | 3.93 | 6.11 | −0.06 | 0.73 |
| WR | 71 | 5.74 | 8.10 | +1.19 | 0.56 |
| TE | 42 | 3.59 | 4.75 | −0.82 | 0.46 |
| DST | 16 | 1.85 | 2.79 | +0.17 | 0.36 |

Centres were essentially unbiased (+0.22 overall).

## 2. Role allocation — the pre-lock hypothesis

**Verdict: CONFIRM_TARGET_CONCENTRATION_DEFECT.** Tested on each club's SHARE of its own realised targets, bands from
the model's own pregame ordering, 90% intervals from a bootstrap over the eight games:

| band | proj targets | actual | proj share | actual share | share gap / club | 90% |
|---|---|---|---|---|---|---|
| WR1 | 143.7 | 122 | 30.8% | 24.4% | −6.4 pts | [−12.6, −0.2] |
| WR2 | 81.0 | 93 | 17.2% | 18.8% | +1.6 | [−1.5, +4.7] |
| WR3+ | 35.7 | 78 | 4.4% | 9.1% | **+8.3** | [+4.2, +12.2] |
| TE1 | 103.6 | 93 | 22.3% | 19.9% | −2.4 | [−7.4, +2.6] |
| TE2+ | 20.5 | 27 | 3.1% | 4.0% | +1.3 | [0.0, +2.6] |
| RB1 | 55.6 | 56 | 11.9% | 10.1% | −1.9 | [−4.1, +0.3] |
| RB2+ | 26.5 | 26 | 3.2% | 2.9% | −0.5 | [−1.9, +0.7] |

WR1+TE1 together: −8.8 share points per club [−14.7, −3.0]; WR2+WR3+: +9.9 [+5.1, +14.7]. Both exclude zero.
WR3+ received more than twice the targets we gave them. Team volume was mixed, not inflated (e.g. LA 34→50,
CIN 32→46, NYJ 27→15): the defect is within-club allocation.

Named players: Boutte 0.7→4 targets, Noel 0.2→3 (11.9 DK), Flournoy 3.1→5; Raymond 3.6→2 (against the hypothesis).
Concentration side: Washington 10.2→3, Wilson 11.8→4, Egbuka 8.2→4, Gesicki 6.4→5 — but Lamb 10.1→**21**.
Henderson's carries 7→14 (an RB2 under-allocation of the same shape on the ground).

## 3. Simulation calibration (actual located in the frozen 2,000 worlds)

| | n | ≤p50 | ≤p75 | ≤p90 | ≤p95 | below p10 | above p90 |
|---|---|---|---|---|---|---|---|
| nominal | | 50% | 75% | 90% | 95% | 10% | 10% |
| ALL | 201 | 50.2% | 67.7% | 78.6% | 83.1% | 12.9% | 20.9% |
| QB | 17 | 58.8 | 64.7 | 88.2 | 94.1 | 5.9 | 5.9 |
| RB | 55 | 61.8 | 72.7 | 81.8 | 89.1 | 12.7 | 18.2 |
| WR | 71 | 43.7 | 62.0 | 74.6 | 77.5 | 16.9 | 25.4 |
| TE | 42 | 45.2 | 66.7 | 71.4 | 76.2 | 14.3 | 28.6 |
| high-exposure (≥20% of 150) | 13 | 53.8 | 69.2 | 84.6 | 84.6 | 38.5 | 15.4 |

**Tails too narrow**, concentrated in WR/TE: 34% of actuals fell outside p10–p90 against 20% nominal; 21% beat their
p90. Centres were fine. This is the distributional face of §2: a receiver whose role can move from 3 to 21 targets
was simulated with role volume too tight.

## 4. Portfolios (independent DK scoring of the locked 173)

| | best | mean | median | p75 | p90 | p95 | worst |
|---|---|---|---|---|---|---|---|
| 150-max | **207.50** | 129.41 | 127.87 | 149.69 | 165.98 | 173.81 | 55.26 |
| 20-max | 191.08 | 132.33 | 126.75 | 148.45 | 166.22 | 172.10 | 66.12 |
| 3-entry | 171.10 | 157.13 | 161.02 | 166.06 | 169.08 | 170.09 | 139.28 |

Our 207.50 reproduces the owner's DraftKings figure exactly. Owner-relayed: 19th place; first 225.38 (gap 17.88).
Finish, cash rate, fees, winnings, ROI: **need the standings exports.**

**Best 150 lineup (entry 5279820055, pregame sim mean 144.3):** Dak Prescott 21.1 · Javonte Williams 31.3 ·
Rhamondre Stevenson 18.4 · CeeDee Lamb 44.3 · Nico Collins 33.8 · Zay Flowers 28.8 · Brenton Strange 16.5 · FLEX Mack
Hollins 8.3 · Buccaneers 5.0. A DAL@HOU (64-point game) QB+2 with a Collins bring-back.

**Hindsight optimal (actual stats, locked salaries, $49,500): 262.92** — Burrow 28.7, K. Williams 36.7, Javonte
Williams 31.3, Monangai 31.0, Lamb 44.3, Collins 33.8, Keon Coleman 26.6, Strange 16.5, Giants 14.0.
Owner best / optimal 0.789; winner / optimal 0.857 (owner-relayed winner). The optimal lineup is a postgame object:
Monangai and Coleman were projected 6.9 and 5.0, and nothing pregame said they would be the slate's best plays.

Best vs optimal, by slot: QB −7.6 (Dak vs Burrow), RB2 −18.3 (Stevenson vs K. Williams), FLEX −22.7 (Hollins vs
Monangai), DST −9.0, WR3 +2.2. The FLEX and RB gaps are exactly the secondary-role players the concentration defect
under-projects. **The 17.88-point gap to first place cannot be decomposed until the winner's lineup is ingested.**

## 5. Construction (150-max, mean / max lineup points)

- QB+1 130.8 / 195.8 (96) · QB+2 125.6 / **207.5** (50) · QB+3 143.1 / 170.9 (4)
- bring-back 1: 131.3 / 207.5 (57) · none: 129.0 / 178.3 (84) · 2: 120.8 / 176.0 (9)
- QB families: Stroud 152.3, Prescott 148.3 (DAL@HOU 150.0 mean), Jackson 136.0 … Bagent 124.9 (24 lineups), Allen 116.5
- salary: $50,000 lineups 133.4 vs $49,500 128.7. Core-player count: 1–2 core players 105–111; 3–5 about 131–132.

None of this is a strategy rule after one slate.

## 6. Exposure quality (150-max)

Good overweights: K. Williams (35%, 36.7), Lamb (26%, 44.3), Collins (25%, 33.8), Nacua (31%, 30.7), Flowers (31%,
28.8), Gesicki (29%, 13.0 but in high-scoring builds). Bad overweights: Washington (38%, 2.0), Irving (33%, 6.1),
Swift (29%, 8.4), Wilson (29%, 5.7), Burden (29%, 11.4), Watson (25%, 7.7), Tuten (23%, 11.1). Six good, seven bad:
the top of the exposure table was a coin flip this week. Bad underweights: Tee Higgins 29.7, Malik Nabers 26.2,
Carnell Tate 25.5 (all ≤3%). Never rostered: Monangai 31.0, Keon Coleman 26.6. Field ownership: not ingested.

## 7. FC disagreement (pre-lock snapshot only; FC is never truth)

On the 34 material disagreements FC's number was closer 24 times, ours 9, 1 tie. The automatic labels
(`…_POSTGAME_FC_AUDIT.csv`) are a first pass; by hand: Lamb (ours closer, and he doubled even our volume — direction
right, size variance); Washington, Wilson, Egbuka, DJ Moore, Kincaid, Irving, Swift (FC closer — the concentration
defect); Noel, Boutte, Monangai (FC closer — the same defect on the other side); Bagent (volume right at 34 attempts,
efficiency far below our prior — FC efficiency edge); Kyren Williams, Flowers (TD-driven variance). We do not score
either model "better" from one slate.

## 8. Process vs outcome

| finding | classification |
|---|---|
| Inactive ingestion, redistribution, 173/173 legality, scope gate | PROCESS_GOOD_OUTCOME_GOOD |
| Centres unbiased (+0.22), RB ranking 0.73 | PROCESS_GOOD_OUTCOME_GOOD |
| Within-club target concentration (declared pre-lock, unvalidated) | PROCESS_BAD_OUTCOME_BAD — confirmed |
| Narrow WR/TE tails | PROCESS_BAD_OUTCOME_BAD |
| Low-sample QB efficiency prior (Bagent 18.9 → 9.8 on the projected volume) | PROCESS_BAD_OUTCOME_BAD |
| DAL@HOU stack + Collins bring-back producing the best lineup | PROCESS_GOOD_OUTCOME_GOOD, one observation |
| Lamb at 26% via a concentration-inflated projection | PROCESS_BAD_OUTCOME_GOOD — do not reinforce |
| Shipping with the known defect rather than an untested lock-time change | PROCESS_GOOD (outcome not attributable) |

## 9. Priorities (hypotheses and tests only; no production promotion)

- **P0 — role/usage allocation.** Confirmed this week. Replace the depth-rank curve with a within-club share model
  (target, carry and route shares, teammate-absence redistribution); pre-register and forward-chain it on weeks 1–4
  with the WR3+/TE2+ share gap as the primary metric.
- **P1 — role-volume uncertainty in the simulator.** WR/TE tails are too narrow; widen role (volume) variance, not
  efficiency noise, and test coverage of p10/p90 on held-out weeks.
- **P2 — low-sample and backup QB efficiency priors**, propagated to their receivers and the opposing DST.
- **P3 — field data.** Ingest the three DraftKings standings exports for finish/ROI, winner forensics and real
  ownership, which seeds the duplication and field models.

The R8 / currently accepted baseline and all governance stay as they are.
