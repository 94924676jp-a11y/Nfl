# Week 5 (2026) Classic: world-correctness audit

Read-only. Inputs: `nfl/dfs/salaries/runs/w5_final/RESEARCH_STATE_2026W5/` (266 players: 250 skill players and 16 DST, 2,000 worlds, 8 games).
`PROJ.json` sha256 `16cf8340…` and `STATE.json` sha256 `837f33c6…` match the hashes recorded in `DRAWS.json`. These numbers are RESEARCH output (FOOTBALL_ONLY arm, not validated). Nothing in the repo was changed. Nothing here recommends a lineup or a wager.
Machine-readable copy: `WEEK5_WORLD_CORRECTNESS_AUDIT.json`. Scripts: `audit.py` and `build_final.py`. Raw checker output: `checker_raw.json`.

## 1. Conditional projection, unconditional projection, and what the worlds contain

- `dk_points` is **unconditional**: P(plays) × what he does if he plays, after a second allocation. `dk_points_if_plays` is **conditional**. The worlds are centred on the unconditional number.
- **Gaps between the mean of the worlds and the projection.** 21 of 266 players are flagged: 14 are more than 0.5 DK apart and 19 are more than 3 Monte Carlo SE apart. The largest are Tyler Shough +1.22 (6.5 SE), Romeo Doubs +1.15, Juwan Johnson +0.98, Drake Maye +0.93 and Hunter Henry +0.85. Running the other way are Kyler Murray −0.71, Deshaun Watson −0.65 and Quinshon Judkins −0.60.
  - The cause is the club touchdown count. The efficiency anchor rescales yards only and leaves TDs as simulated. Simulated minus projected offensive TDs per club: NO +0.24, PIT +0.22, NE +0.17, WAS +0.16, CLE −0.28, MIN −0.23, MIA −0.20.
  - So NO and NE players are worth more in the worlds than in the projection, and CLE and MIN players are worth less.
- **The worlds have no appearance process for players with p_plays < 1.** 157 non-QB skill players carry p_plays < 1 taken straight from the club-slot table (WR2 0.8605, RB2 0.6349, WR3 0.5865, TE2 0.579). The share of a player's worlds with zero opportunities minus (1 − p_plays) averages **−0.135** (minimum −0.497). For example, Monangai has 0.05% zero worlds where 1 − p_plays implies 36.5%.
  - The discount is therefore spread over every world as reduced volume. It is not a set of zero worlds plus a set of full-role worlds. No player's worlds carry his conditional distribution.
  - Backup QBs look as if they have the right number of zero worlds (Bagent 88.3% against 86.2% implied), but only because a tiny share of club volume rarely produces an opportunity. When he does get one, his mean is 0.51 DK against 7.22 if he plays. **No world is a backup-starts game.**
- `dk_points_if_plays` summed over a club is **28–59% higher** than the unconditional club sum. Conditional numbers are per-player and must not be summed or used jointly.
- Role ceilings: no row is banded above its `askable_ceiling`, and no club-position has two ALPHA players (114 capped, 0 demoted).

## 2. World accounting (16 clubs × 2,000 = 32,000 club-worlds)

| Law | Violating club-worlds | Notes |
|---|---|---|
| Club receiving yards = QB passing yards | **30,641** | Mean receiving minus passing yards by club: CHI +28.4, GB +14.5, MIN +13.1, NYG +7.3; MIA −25.6, NYJ −12.6, LV −9.3, NE −8.3; PIT 0.0, HOU −0.2 |
| Receiving yards only with a reception | **17,192** | 23,623 player-cells, mean 8.9 yds, max 231.7 |
| Receiving TD only with a reception | **4,151** | 4,433 cells; Raridon NE 167, Ayomanor TEN 105, C. White LV 103, S. Moore GB 102 |
| Rushing TD ≤ carries | **1,367** | Burrow CIN 138, Homer PIT 114, Ward TEN 70 |
| Club points ≥ 6 × offensive TDs | **1,155** | Shortfall up to 10.9 points |
| Passing TDs = receiving TDs | 51 | WAS 20, NE 10 |
| Receptions ≤ targets; targets ≤ attempts | 0; 0 | |
| Opposing DST ≥ 2 × INTs − 4 | **977** | corr(opposing DST, INTs thrown) is −0.02 to +0.05 in every club: the DST is not tied to the world's interceptions. It is tied to points (r ≈ −0.67 to −0.72) |

Other findings in the worlds:

- **Values beyond the NFL single-game records:** 93 player-world cells with more than 554 passing yards (maximum 867.3) and 42 with more than 336 receiving yards (maximum 495.7).
- **Club points are a continuous draw.** 95.6–99.65% of club-worlds are non-integer, 0.1–1.35% round to 1 point (not a reachable score), and 2.65–4.1% of games tie on rounded points.
- **The DK points the optimizer scores reproduce from the published stat line:** 0 violations out of 500,000 cells.
- **Defect in `world_accounting_check.py`:** POINTS_GE_6_PER_TD reads `pts[0]`, the first game, for every club. That is right on a Showdown file and wrong on Classic. Its GB (81) and CHI (63) counts agree with this audit; every other club is compared against CHI@GB points (for MIA the checker reports 325, this audit 59). I did not repair it.

## 3. DST and kickers

- **DST:** 96.35% of worlds are non-integer pooled (94.65–98.2% per unit). DK DST scoring only produces integers, so the multiplicative anchor causes this.
  - Anchor factors run from 0.563 (NYJ: the raw simulation gives 8.81, the projection 4.96) to 1.338 (MIN) and 1.336 (PIT).
  - Worlds below the DK floor of −4: PIT 4.0%, MIN 2.65%, LV 1.65%, CHI 1.35%. The maximum is 42.8 (MIN).
  - Means equal the projection by construction.
- **Kickers:** none exist. DK Classic has no K slot and the universe holds no K rows. Field goals appear only implicitly inside the continuous club points.
- **Impossible values:** no NaN anywhere. 15 skill players have negative worlds (backup QBs, minimum −1.0), and every one is explained by an interception. **Fumbles are not modelled** (`proj_v1.py:419`), so every ball-carrier's mean is slightly high.

## 4. Distributions, top 40 projected skill players

- **All 40 of the top 40** have P(DK < 5) below the lower 95% bound of the historical rate for their bin (`STAR_DUD_RATE_2021_2025.json`).
- **Players projected for 20 or more:** mean simulated P(<5) is 0.62%, against 4.92% historically (20+ ALL) and **6.57% for 20+ ppg WR** (n=350, 95% interval [4.01, 9.49]).
  - Chris Olave: 0.75%, a shortfall of 5.82 percentage points (8.8× too thin).
  - Nico Collins: 1.10%, 5.47 pp (6.0×).
  - Caleb Williams 0.35% (14×), Shough 0.25% (20×), Burrow 0.65% (7.6×).
- **Players projected 15–20:** mean simulated P(<5) is 2.34% against 10.26% historically.
- The comparator bins on realised ppg, so these shortfalls are lower bounds.
- One identified source: the worlds carry no in-game injury or early-exit process, so starters have about 0 zero-opportunity worlds.

Full p10/p50/p90/sd table: JSON `section4_distributions_top40`.

## 5. Effect on optimizer decisions

| Defect | Week 5 players most affected | Direction of optimizer bias | Repairable before Sunday? |
|---|---|---|---|
| D-01 thin star lower tail | Olave, Collins, C. Williams, Shough, Burrow, Maye, Daniels, Jeanty | TOWARD stars and stacks built on them: bust risk is understated 3–23×, so floors and any variance penalty make them look safer than they are | **No.** The P2 volatility repair reshapes every distribution and has not been validated. Means are unaffected |
| D-05 world accounting | CHI receivers (+28 yds the QB did not throw), GB, MIN; MIA receivers (−26), NYJ, LV, NE; fringe TEs/WRs with TDs and no catch | TOWARD CHI/GB/MIN pass-catchers and their stacks, AWAY from MIA/NYJ receivers. A QB paired with the DST facing him is not penalised. Punts get false TD-ceiling worlds | **No.** The event-consistent repair (W5-G17) failed integration. Changing the anchor mode reintroduces the W4 mean gaps |
| DST non-integer (anchor) | MIN ×1.34, PIT ×1.34, LV ×1.07; NYJ ×0.56, MIA ×0.59, TEN ×0.66, GB ×0.69 | Mean-based optimizers: no effect. Distribution-based: TOWARD MIN/PIT/LV DST (inflated ceilings), AWAY from NYJ/MIA/TEN/GB DST | **No.** Another agent is investigating, and every candidate fix (rounding, additive shift, event re-simulation) moves the mean or is unvalidated |
| W5-G16 slot-table appearance | Higgins −1.76 versus if-plays, Burden −1.74, Golden −1.58, Vele −1.51, Diggs −1.26; Monangai −3.31, R. White −3.41, Dowdle −2.75, Hollins −4.30, Raymond −3.59; Noel 0.48 versus 5.83 | AWAY from active depth-2/3 players in every world (the discount is reduced volume, not zero worlds), and so TOWARD depth-1 teammates by comparison | **No.** AP-1 is preregistered for W6–W11; promoting it now spends that test |
| W5-G18 QB identity ignored | CHI: Swift, Odunze, Burden, Loveland, Monangai, Raymond. WAS: McLaurin, Diggs, Croskey-Merritt, R. White, Okonkwo | If Bagent, Mariota or Kaliakmanis starts, the receivers keep starter-QB volume (TOWARD them). A stack with a backup QB cannot be valued, because no world is a backup-starts game | **No.** QBCTX failed its bar. The only lever before Sunday is the official designation entering STATE, which moves only the QB |

Also noted: `scoring_centre.home_spread` means home-minus-away margin (CHI@GB −6.35), while the STATE `home_spread` is a market spread (−1.5, GB favoured). Same name, opposite conventions.
