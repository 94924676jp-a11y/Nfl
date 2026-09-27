# Week-3 Early Only — the QB layer, and exactly what it consumed

Spec `qb-v1-aggregate-then-allocate-1`, study `qb-layer-study-1`, 200 draws, seed 20260908. QB frame sha256 `e2de51d345502a2717a64e584f5e883a64eb3ed51ff97e5f42e406a0ddba0c54`.

## This is an intermediate quantity, not a projection

qb_slate returns draws, a distribution. Downstream apply_r2_level RE-RUNS QB V1 at the level D1 and QB3 own, apportioned from the team budget by largest remainder, so the level here is QB V1 own draw and NOT the level a sealed board would carry. Nothing here is sealed: the run refuses at player_draws before sealing. Quote as "the QB layer pre-R2 draws", never as the model projection.

## It contains no 2026 information

The frame spans 202001 to 202518 and holds zero 2026 rows, while the guard would permit 202601 and 202602. So this is pre-2026 by DATA ABSENCE, not by policy -- unlike Q9 arm A, which excludes the forecast season by design. It cannot know anything about weeks 1 and 2 or about today. If 2026 QB rows existed the layer would consume them with no code change.

Measured: 6388 frame rows, ordinals **202001 → 202518**, **0 rows from 2026**. Forecast ordinal 202603.

## Read this before quoting any number

These are NOT per-player expectations. Every rostered quarterback is drawn as though he played, with no start-probability weighting, so each row reads only as "if this man played the whole game". Measured consequence: the mean team attempt sum is 67.3 against a plausible real team value of roughly 30-35, and it scales with how many quarterbacks DK listed rather than with football -- CIN lists four and sums to 110.1, MIA lists two and sums to 45.7. This is the declared multi_qb_over_prediction limitation, quantified. It is also exactly what apply_r2_level repairs downstream by apportioning the level from the team dropback budget, which is why "pre-R2" is the whole story and not a pedantic note.

| team | QB with a row | sum att mean | sum dropback mean | top QB share |
|---|---|---|---|---|
| BUF | 3 | 81.7 | 93.5 | 41% |
| CAR | 2 | 52.3 | 60.1 | 55% |
| CIN | 4 | 110.1 | 121.2 | 31% |
| CLE | 3 | 81.2 | 95.6 | 38% |
| DET | 2 | 63.6 | 70.0 | 56% |
| HOU | 2 | 57.2 | 64.2 | 56% |
| IND | 3 | 77.8 | 88.2 | 37% |
| JAX | 3 | 86.0 | 95.3 | 39% |
| KC | 2 | 65.6 | 78.3 | 54% |
| LAC | 2 | 54.8 | 62.6 | 65% |
| MIA | 2 | 45.7 | 55.0 | 65% |
| NE | 2 | 47.2 | 58.2 | 56% |
| NYG | 3 | 68.9 | 80.7 | 42% |
| NYJ | 3 | 90.5 | 103.3 | 36% |
| PIT | 2 | 53.3 | 58.0 | 59% |
| SEA | 2 | 54.3 | 61.2 | 51% |
| TEN | 3 | 69.0 | 78.3 | 43% |
| WAS | 2 | 52.9 | 63.9 | 53% |

**Implausible upper tails, recorded not clipped.** Rows whose p95 passing yards exceed 500 are recorded rather than clipped. A 1,036-yard p95 on a fourth-string passer is the declared discrete_low_count_intervals limitation showing itself on a thin history; clipping it would hide the limitation instead of reporting it.

- CIN Sean Clifford ($4000): mean 288.1, p95 **1036** passing yards

## Coverage

45 of 60 DK quarterbacks have a QB-layer row; **15 do not**. 15 of 60 DK quarterbacks have no row. If one of them starts today the layer has nothing for the position that matters most. Listed by name, never dropped.

Declared limitations: multi_qb_over_prediction, int_discrimination, discrete_low_count_intervals.

Metrics produced: `att`, `cmp`, `db`, `drush`, `int`, `ptd`, `pyds`, `rtd`, `rush_opp`, `ryds`, `sacks`, `scr`. Of these, the sealed contract declares `att`, `cmp`, `pyds`, `ptd`, `int`.


## Quarterbacks with a QB-layer row

Mean and 5th–95th percentile over the draws. Pre-R2 level, pre-2026.

| team | opp | player | $ | att | cmp | pass yds | pass TD | int |
|---|---|---|---|---|---|---|---|---|
| BUF | LAC | Josh Allen | 8000 | 33.4 [18–48] | 21.9 [12–34] | 248.6 [128–426] | 2.1 [0–5] | 0.9 [0–3] |
| BUF | LAC | Kyle Allen | 4000 | 21.8 [1–46] | 14.3 [1–31] | 166.0 [9–451] | 0.9 [0–3] | 0.4 [0–2] |
| BUF | LAC | Shane Buechele | 4000 | 26.6 [4–45] | 16.4 [2–27] | 190.6 [14–371] | 1.1 [0–3] | 0.5 [0–2] |
| CAR | CLE | Bryce Young | 5600 | 29.0 [13–42] | 17.7 [9–27] | 169.5 [39–299] | 1.1 [0–3] | 0.6 [0–2] |
| CAR | CLE | Kenny Pickett | 4000 | 23.3 [2–43] | 14.9 [1–27] | 142.5 [9–324] | 0.7 [0–2] | 0.5 [0–2] |
| CIN | PIT | Joe Burrow | 6600 | 33.9 [14–45] | 23.2 [9–33] | 250.7 [94–402] | 1.9 [0–4] | 0.6 [0–2] |
| CIN | PIT | Joe Flacco | 4400 | 31.6 [2–48] | 19.1 [1–31] | 197.4 [8–347] | 1.4 [0–4] | 0.9 [0–3] |
| CIN | PIT | Josh Johnson | 4000 | 21.1 [1–44] | 14.2 [1–29] | 151.5 [3–376] | 1.0 [0–4] | 0.5 [0–2] |
| CIN | PIT | Sean Clifford | 4000 | 23.4 [1–46] | 16.8 [0–34] | 288.1 [0–1036] | 0.9 [0–3] | 0.4 [0–2] |
| CLE | CAR | Deshaun Watson | 4700 | 30.2 [9–46] | 19.7 [5–31] | 224.3 [59–405] | 1.5 [0–4] | 0.5 [0–2] |
| CLE | CAR | Shedeur Sanders | 4200 | 30.5 [16–44] | 18.3 [9–28] | 208.9 [84–363] | 1.2 [0–3] | 1.1 [0–3] |
| CLE | CAR | Dillon Gabriel | 4000 | 20.4 [1–44] | 12.5 [0–28] | 101.1 [0–260] | 0.7 [0–3] | 0.3 [0–2] |
| DET | NYJ | Jared Goff | 6300 | 35.4 [23–53] | 24.3 [15–37] | 280.1 [141–466] | 1.8 [0–4] | 0.7 [0–2] |
| DET | NYJ | Joshua Dobbs | 4000 | 28.2 [2–51] | 17.6 [1–32] | 169.9 [9–360] | 1.0 [0–3] | 0.7 [0–2] |
| HOU | IND | C.J. Stroud | 5500 | 32.0 [20–45] | 20.5 [10–30] | 236.3 [91–421] | 1.5 [0–4] | 0.7 [0–2] |
| HOU | IND | Davis Mills | 4000 | 25.2 [1–44] | 15.7 [0–30] | 163.6 [0–318] | 1.0 [0–3] | 0.6 [0–2] |
| IND | HOU | Daniel Jones | 5000 | 28.9 [13–42] | 19.1 [10–28] | 195.9 [93–337] | 0.8 [0–3] | 0.7 [0–2] |
| IND | HOU | Anthony Richardson Sr. | 4000 | 26.9 [2–44] | 14.3 [1–25] | 187.5 [10–426] | 0.9 [0–3] | 1.0 [0–3] |
| IND | HOU | Riley Leonard | 4000 | 22.0 [1–46] | 13.6 [0–29] | 152.6 [0–360] | 0.8 [0–3] | 0.8 [0–3] |
| JAX | NE | Trevor Lawrence | 5700 | 33.5 [22–47] | 21.1 [13–31] | 231.0 [117–383] | 1.2 [0–3] | 0.8 [0–2] |
| JAX | NE | Quinn Ewers | 4000 | 28.6 [6–47] | 18.7 [3–31] | 206.0 [31–382] | 1.2 [0–3] | 0.9 [0–3] |
| JAX | NE | Nick Mullens | 4000 | 23.9 [1–47] | 16.1 [1–33] | 182.4 [3–448] | 0.9 [0–3] | 0.9 [0–3] |
| KC | MIA | Patrick Mahomes | 6200 | 35.7 [25–47] | 23.6 [15–33] | 259.2 [147–397] | 2.0 [0–4] | 0.7 [0–2] |
| KC | MIA | Justin Fields | 4000 | 29.9 [16–41] | 18.0 [9–26] | 198.8 [75–357] | 1.1 [0–3] | 0.8 [0–3] |
| LAC | BUF | Justin Herbert | 5800 | 35.5 [22–50] | 23.6 [14–34] | 261.3 [142–409] | 1.6 [0–4] | 0.6 [0–2] |
| LAC | BUF | Trey Lance | 4000 | 19.3 [1–43] | 11.1 [0–25] | 119.9 [0–333] | 0.6 [0–2] | 0.4 [0–2] |
| MIA | KC | Malik Willis | 4900 | 16.1 [1–38] | 11.0 [1–27] | 142.6 [6–445] | 0.7 [0–3] | 0.3 [0–1] |
| MIA | KC | Brady Cook | 4000 | 29.6 [4–46] | 18.0 [3–30] | 168.8 [34–313] | 0.8 [0–2] | 0.9 [0–3] |
| NE | JAX | Drake Maye | 6100 | 26.4 [7–42] | 18.2 [4–30] | 208.1 [50–375] | 1.4 [0–3] | 0.6 [0–2] |
| NE | JAX | Tommy DeVito | 4000 | 20.7 [2–36] | 13.5 [1–24] | 117.5 [-4–272] | 0.8 [0–3] | 0.3 [0–2] |
| NYG | TEN | Jaxson Dart | 5900 | 29.2 [12–45] | 18.8 [7–30] | 204.2 [52–387] | 1.2 [0–3] | 0.3 [0–2] |
| NYG | TEN | Jameis Winston | 4000 | 25.6 [1–42] | 15.8 [1–28] | 195.1 [11–410] | 1.3 [0–3] | 0.8 [0–3] |
| NYG | TEN | Jake Haener | 4000 | 14.1 [1–37] | 7.9 [0–21] | 89.7 [0–265] | 0.5 [0–2] | 0.3 [0–2] |
| NYJ | DET | Geno Smith | 4900 | 33.0 [19–49] | 22.3 [13–34] | 247.6 [126–421] | 1.5 [0–4] | 0.8 [0–2] |
| NYJ | DET | Bailey Zappe | 4000 | 26.7 [7–49] | 17.1 [3–31] | 180.2 [31–367] | 1.1 [0–3] | 0.9 [0–3] |
| NYJ | DET | Will Levis | 4000 | 30.9 [9–49] | 18.7 [6–30] | 216.7 [64–406] | 1.1 [0–3] | 0.8 [0–3] |
| PIT | CIN | Aaron Rodgers | 5000 | 31.5 [18–47] | 21.2 [11–33] | 232.1 [103–374] | 1.9 [0–5] | 0.6 [0–2] |
| PIT | CIN | Mason Rudolph | 4000 | 21.8 [1–45] | 14.4 [1–30] | 139.2 [6–344] | 0.8 [0–3] | 0.5 [0–2] |
| SEA | WAS | Sam Darnold | 5400 | 27.7 [3–42] | 17.8 [2–28] | 199.1 [22–353] | 1.3 [0–4] | 0.7 [0–2] |
| SEA | WAS | Drew Lock | 5200 | 26.6 [4–44] | 15.6 [2–27] | 172.2 [15–344] | 0.9 [0–3] | 0.8 [0–2] |
| TEN | NYG | Cam Ward | 5100 | 29.6 [12–42] | 18.1 [7–28] | 190.6 [55–337] | 0.9 [0–2] | 0.4 [0–2] |
| TEN | NYG | Mitchell Trubisky | 4000 | 21.6 [1–42] | 14.3 [0–29] | 167.7 [0–350] | 1.0 [0–3] | 0.6 [0–2] |
| TEN | NYG | Hendon Hooker | 4000 | 17.8 [2–41] | 11.3 [1–27] | 126.5 [9–361] | 0.4 [0–2] | 0.3 [0–1] |
| WAS | SEA | Jayden Daniels | 6000 | 28.1 [13–44] | 18.8 [6–31] | 200.8 [42–374] | 1.4 [0–4] | 0.5 [0–2] |
| WAS | SEA | Marcus Mariota | 4500 | 24.8 [1–45] | 15.6 [1–30] | 176.1 [0–394] | 1.2 [0–4] | 0.7 [0–3] |

## Quarterbacks with NO QB-layer row — UNKNOWN, not zero

| team | player | $ | why |
|---|---|---|---|
| CAR | Haynes King | 4000 | no row in the QB frame: no pre-2026 history and include_cold_start is False. UNKNOWN, not zero. |
| CLE | Taylen Green | 4000 | no row in the QB frame: no pre-2026 history and include_cold_start is False. UNKNOWN, not zero. |
| DET | Luke Altmyer | 4000 | no row in the QB frame: no pre-2026 history and include_cold_start is False. UNKNOWN, not zero. |
| HOU | Graham Mertz | 4000 | no row in the QB frame: no pre-2026 history and include_cold_start is False. UNKNOWN, not zero. |
| JAX | Joey Aguilar | 4000 | no row in the QB frame: no pre-2026 history and include_cold_start is False. UNKNOWN, not zero. |
| KC | Garrett Nussmeier | 4000 | no row in the QB frame: no pre-2026 history and include_cold_start is False. UNKNOWN, not zero. |
| LAC | DJ Uiagalelei | 4000 | no row in the QB frame: no pre-2026 history and include_cold_start is False. UNKNOWN, not zero. |
| MIA | Kyle McCord | 4000 | no row in the QB frame: no pre-2026 history and include_cold_start is False. UNKNOWN, not zero. |
| NE | Behren Morton | 4000 | no row in the QB frame: no pre-2026 history and include_cold_start is False. UNKNOWN, not zero. |
| NYJ | Cade Klubnik | 4000 | no row in the QB frame: no pre-2026 history and include_cold_start is False. UNKNOWN, not zero. |
| PIT | Will Howard | 4000 | no row in the QB frame: no pre-2026 history and include_cold_start is False. UNKNOWN, not zero. |
| PIT | Drew Allar | 4000 | no row in the QB frame: no pre-2026 history and include_cold_start is False. UNKNOWN, not zero. |
| SEA | Jalen Milroe | 4000 | no row in the QB frame: no pre-2026 history and include_cold_start is False. UNKNOWN, not zero. |
| WAS | Athan Kaliakmanis | 4000 | no row in the QB frame: no pre-2026 history and include_cold_start is False. UNKNOWN, not zero. |
| WAS | Sam Hartman | 4000 | no row in the QB frame: no pre-2026 history and include_cold_start is False. UNKNOWN, not zero. |

