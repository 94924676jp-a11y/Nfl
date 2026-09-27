# Week-3 Early Only — TODAY-STATE descriptive evidence

`PRE_OFFICIAL_INACTIVES / CURRENT_HELD_STATE` · generated 2026-09-27T15:28:34+00:00 · spec `dk-today-state-1`

**No projection. No recommendation. No wager.** The production board remains blocked; nothing here is a Week-3 forecast.

## What each layer may be read as

| layer | provenance | may be read as |
|---|---|---|
| DK export | AUTHORITATIVE | the contest universe, 457 rows |
| Q9 arm-A features | PRIOR_HISTORY | pre-2026 usage. **never** today's role |
| snaps + play-by-play | OBSERVED_2026 | what actually happened in weeks 1–2 |
| depth chart | held vintage | what a list said on Wednesday |
| availability | UNKNOWN | nothing authoritative held |
| FantasyCruncher | EXTERNAL_FC_CONTEXT_ONLY | membership only |
| QB layer | PRE-R2 conditional | not an expectation |

## Unavailable, and not estimated

routes and route_participation are UNKNOWN_SOURCE_UNAVAILABLE: pbp_participation_2026 returned 404 at every probe through 2026-09-27T06:34:57Z and per-play on-field presence exists nowhere else. Not inferred from targets or snaps.

## Zero is not unknown

a player with a snap row and no pbp row carries OBSERVED_ZERO_TOUCHES -- he was on the field and did not touch the ball, which is a real zero. A player with no row in either source carries UNKNOWN_NO_ROW_EITHER_SOURCE. The two are never merged.

## Coverage

457 DK rows · {'NO_FEATURES': 189, 'FEATURES_WITH_PRIOR_HISTORY': 215, 'FEATURES_NO_PRIOR_HISTORY': 53}

**182 materially active in observed 2026** at the declared thresholds ({'offense_pct_at_or_above': 0.25, 'touches_at_or_above': 3, 'note': 'declared here so the counts are reproducible; either week qualifying is enough'}).

**19 of the 53 no-prior-history rows are materially active**, so their `fringe` label is materially misleading and is flagged per row with `historical_role_class_valid_for_current_role: false`.

| $ | pos | player | team | mean snap % | targets | carries |
|---|---|---|---|---|---|---|
| 5300 | RB | Jadarian Price | SEA | 0.41 | 4.0 | 23.0 |
| 5000 | WR | Carnell Tate | TEN | 0.815 | 11.0 | — |
| 4500 | WR | Denzel Boston | CLE | 0.925 | 11.0 | — |
| 4400 | RB | Emmett Johnson | KC | 0.27 | 4.0 | 10.0 |
| 4400 | WR | Malachi Fields | NYG | 0.765 | 10.0 | — |
| 4300 | RB | Kaytron Allen | WAS | 0.09 | — | 9.0 |
| 4300 | WR | KC Concepcion Jr. | CLE | 0.675 | 11.0 | 4.0 |
| 4100 | WR | Antonio Williams | WAS | 0.43 | 7.0 | — |
| 4000 | RB | DJ Herman | MIA | — | 3.0 | — |
| 3900 | WR | Germie Bernard | PIT | 0.415 | 8.0 | — |
| 3900 | WR | Caleb Douglas | MIA | 0.885 | 10.0 | — |
| 3500 | TE | Kenyon Sadiq | NYJ | 0.39 | 6.0 | 1.0 |
| 3400 | WR | Chris Bell | MIA | 0.465 | 3.0 | — |
| 3000 | WR | Josh Cameron | JAX | 0.25 | 2.0 | — |
| 3000 | WR | Kevin Coleman Jr. | MIA | 0.375 | 2.0 | — |
| 3000 | WR | Brenen Thompson | LAC | 0.18 | 3.0 | — |
| 2900 | TE | Eli Raridon | NE | 0.37 | 2.0 | — |
| 2500 | TE | Nate Boerkircher | JAX | 0.53 | 1.0 | — |
| 2500 | TE | Will Kacmarek | MIA | 0.36 | 2.0 | — |


---

## CAR@CLE

### CAR — 10 materially active in 2026 (1 of them with no Q9 features)

- **QB (pass attempts, wk1+2):** Bryce Young 77.0, Kenny Pickett 1.0
- **Backfield (carries):** Chuba Hubbard 22.0, Jonathon Brooks 9.0, AJ Dillon 8.0
- **WR (targets):** Tetairoa McMillan 18.0, Jalen Coker 18.0, Xavier Legette 6.0
- **TE (targets):** Tommy Tremble 7.0, Darren Waller 5.0, Mitchell Evans 3.0

### CLE — 9 materially active in 2026 (1 of them with no Q9 features)

- **QB (pass attempts, wk1+2):** Deshaun Watson 59.0
- **Backfield (carries):** Quinshon Judkins 24.0, Raheim Sanders 3.0, Jaleel McLaughlin 1.0
- **WR (targets):** Denzel Boston 11.0, KC Concepcion Jr. 11.0, Jerry Jeudy 5.0, Isaiah Bond 1.0, Jimmy Horn Jr. 1.0
- **TE (targets):** Harold Fannin Jr. 9.0, Blake Whiteheart 3.0

**Historical label vs observed 2026 — disagreements:**

  - Denzel Boston ($4500): historical `fringe`, observed mean snap share 0.925. history calls him fringe ONLY for want of prior-season snaps; 2026 shows a substantial role. The label is materially misleading for him.
  - KC Concepcion Jr. ($4300): historical `fringe`, observed mean snap share 0.675. history calls him fringe ONLY for want of prior-season snaps; 2026 shows a substantial role. The label is materially misleading for him.


---

## CIN@PIT

### CIN — 9 materially active in 2026 (1 of them with no Q9 features)

- **QB (pass attempts, wk1+2):** Joe Burrow 72.0
- **Backfield (carries):** Chase Brown 36.0, Samaje Perine 7.0
- **WR (targets):** Tee Higgins 16.0, Ja'Marr Chase 13.0, Andrei Iosivas 4.0, Dohnte Meyers 2.0, Colbie Young 1.0
- **TE (targets):** Mike Gesicki 7.0, Drew Sample 3.0, Erick All Jr. 3.0

### PIT — 9 materially active in 2026 (1 of them with no Q9 features)

- **QB (pass attempts, wk1+2):** Aaron Rodgers 85.0, Mason Rudolph 1.0
- **Backfield (carries):** Jaylen Warren 21.0, Rico Dowdle 15.0, Travis Homer 2.0
- **WR (targets):** DK Metcalf 19.0, Roman Wilson 12.0, Germie Bernard 8.0, Michael Pittman Jr. 3.0, Ben Skowronek 1.0
- **TE (targets):** Pat Freiermuth 10.0, Darnell Washington 4.0


---

## HOU@IND

### HOU — 11 materially active in 2026 (1 of them with no Q9 features)

- **QB (pass attempts, wk1+2):** C.J. Stroud 98.0
- **Backfield (carries):** David Montgomery 26.0, Woody Marks 17.0
- **WR (targets):** Xavier Hutchinson 15.0, Nico Collins 10.0, Jared Wayne 8.0, Kayshon Boutte 7.0, Jaylin Noel 7.0
- **TE (targets):** Dalton Schultz 22.0, Foster Moreau 4.0, Marlin Klein 1.0

### IND — 8 materially active in 2026 (1 of them with no Q9 features)

- **QB (pass attempts, wk1+2):** Daniel Jones 64.0
- **Backfield (carries):** Jonathan Taylor 43.0, Seth McGowan 2.0
- **WR (targets):** Josh Downs 13.0, Keenan Allen 11.0, Alec Pierce 7.0, Laquon Treadwell 4.0, Ashton Dulin 1.0
- **TE (targets):** Tyler Warren 12.0


---

## KC@MIA

### KC — 8 materially active in 2026 (1 of them with no Q9 features)

- **QB (pass attempts, wk1+2):** Patrick Mahomes 78.0
- **Backfield (carries):** Kenneth Walker III 47.0, Emmett Johnson 10.0
- **WR (targets):** Xavier Worthy 13.0, Rashee Rice 8.0, Tyquan Thornton 5.0, Jalen Royals 2.0, Cyrus Allen 1.0
- **TE (targets):** Travis Kelce 16.0, Noah Gray 2.0, Jake Briningstool 1.0

### MIA — 10 materially active in 2026 (1 of them with no Q9 features)

- **QB (pass attempts, wk1+2):** Malik Willis 59.0
- **Backfield (carries):** De'Von Achane 31.0, Jaylen Wright 3.0, Ollie Gordon II 3.0
- **WR (targets):** Malik Washington 13.0, Caleb Douglas 10.0, Chris Bell 3.0, Kevin Coleman Jr. 2.0, Ryan Miller 1.0
- **TE (targets):** Greg Dulcich 5.0, Will Kacmarek 2.0

**Historical label vs observed 2026 — disagreements:**

  - Caleb Douglas ($3900): historical `fringe`, observed mean snap share 0.885. history calls him fringe ONLY for want of prior-season snaps; 2026 shows a substantial role. The label is materially misleading for him.


---

## LAC@BUF

### BUF — 8 materially active in 2026 (1 of them with no Q9 features)

- **QB (pass attempts, wk1+2):** Josh Allen 65.0
- **Backfield (carries):** James Cook III 34.0, Ray Davis 1.0, Frank Gore Jr. 1.0
- **WR (targets):** Khalil Shakir 12.0, DJ Moore 8.0, Keon Coleman 8.0
- **TE (targets):** Dalton Kincaid 14.0, Dawson Knox 3.0

### LAC — 11 materially active in 2026 (1 of them with no Q9 features)

- **QB (pass attempts, wk1+2):** Justin Herbert 60.0
- **Backfield (carries):** Omarion Hampton 35.0, Keaton Mitchell 9.0
- **WR (targets):** Quentin Johnston 11.0, Ladd McConkey 10.0, Tre' Harris 9.0, Brenen Thompson 3.0, Derius Davis 2.0
- **TE (targets):** David Njoku 8.0, Oronde Gadsden II 4.0, Charlie Kolar 3.0

**Historical label vs observed 2026 — disagreements:**

  - Kimani Vidal ($4000): historical `starter`, observed mean snap share 0.085. history calls him a starter; observed 2026 snap share is low. Role may have moved, or he may have missed time -- held evidence does not separate those.
  - Oronde Gadsden II ($3500): historical `starter`, observed mean snap share 0.31. history calls him a starter; observed 2026 snap share is low. Role may have moved, or he may have missed time -- held evidence does not separate those.


---

## NE@JAX

### NE — 12 materially active in 2026 (1 of them with no Q9 features)

- **QB (pass attempts, wk1+2):** Drake Maye 61.0
- **Backfield (carries):** Rhamondre Stevenson 24.0, TreVeyon Henderson 16.0, Corey Kiner 8.0
- **WR (targets):** DeMario Douglas 9.0, Romeo Doubs 7.0, Mack Hollins 7.0, A.J. Brown 4.0, Kyle Williams 2.0
- **TE (targets):** Hunter Henry 8.0, Eli Raridon 2.0

### JAX — 12 materially active in 2026 (2 of them with no Q9 features)

- **QB (pass attempts, wk1+2):** Trevor Lawrence 55.0
- **Backfield (carries):** Bhayshul Tuten 28.0, Chris Rodriguez Jr. 12.0, Ameer Abdullah 7.0
- **WR (targets):** Parker Washington 18.0, Brian Thomas Jr. 11.0, Jakobi Meyers 3.0, Josh Cameron 2.0, Travis Hunter 1.0
- **TE (targets):** Brenton Strange 5.0, Quintin Morris 2.0, Nate Boerkircher 1.0

**Historical label vs observed 2026 — disagreements:**

  - Chris Rodriguez Jr. ($4600): historical `starter`, observed mean snap share 0.31. history calls him a starter; observed 2026 snap share is low. Role may have moved, or he may have missed time -- held evidence does not separate those.
  - Nate Boerkircher ($2500): historical `fringe`, observed mean snap share 0.53. history calls him fringe ONLY for want of prior-season snaps; 2026 shows a substantial role. The label is materially misleading for him.


---

## NYJ@DET

### DET — 8 materially active in 2026 (1 of them with no Q9 features)

- **QB (pass attempts, wk1+2):** Jared Goff 82.0
- **Backfield (carries):** Jahmyr Gibbs 45.0, Sione Vaki 3.0
- **WR (targets):** Amon-Ra St. Brown 27.0, Jameson Williams 13.0, Isaac TeSlaa 6.0
- **TE (targets):** Sam LaPorta 15.0, Brock Wright 1.0

### NYJ — 10 materially active in 2026 (1 of them with no Q9 features)

- **QB (pass attempts, wk1+2):** Geno Smith 68.0
- **Backfield (carries):** Breece Hall 38.0, Braelon Allen 15.0
- **WR (targets):** Adonai Mitchell 15.0, Garrett Wilson 14.0, Isaiah Williams 7.0, Arian Smith 1.0, Omar Cooper Jr. 1.0
- **TE (targets):** Kenyon Sadiq 6.0, Mason Taylor 3.0, Jeremy Ruckert 3.0


---

## SEA@WAS

### WAS — 15 materially active in 2026 (2 of them with no Q9 features)

- **QB (pass attempts, wk1+2):** Jayden Daniels 53.0, Marcus Mariota 16.0
- **Backfield (carries):** Jacory Croskey-Merritt 28.0, Rachaad White 14.0, Kaytron Allen 9.0
- **WR (targets):** Stefon Diggs 15.0, Terry McLaurin 13.0, Dyami Brown 8.0, Antonio Williams 7.0, Jaylin Lane 1.0
- **TE (targets):** John Bates 4.0, Chig Okonkwo 3.0, Ben Sinnott 1.0

### SEA — 11 materially active in 2026 (1 of them with no Q9 features)

- **QB (pass attempts, wk1+2):** Drew Lock 50.0, Sam Darnold 3.0
- **Backfield (carries):** Jadarian Price 23.0, Emanuel Wilson 23.0, George Holani 12.0
- **WR (targets):** Jaxon Smith-Njigba 22.0, Rashid Shaheed 9.0, Cooper Kupp 5.0
- **TE (targets):** AJ Barner 3.0, Eric Saubert 1.0, Elijah Arroyo 1.0


---

## TEN@NYG

### NYG — 12 materially active in 2026 (3 of them with no Q9 features)

- **QB (pass attempts, wk1+2):** Jaxson Dart 36.0, Jameis Winston 29.0
- **Backfield (carries):** Cam Skattebo 30.0, Devin Singletary 9.0, Najee Harris 4.0, Tyrone Tracy Jr. 2.0
- **WR (targets):** Malik Nabers 13.0, Malachi Fields 10.0, Darnell Mooney 5.0
- **TE (targets):** Isaiah Likely 18.0, Theo Johnson 5.0

**Historical label vs observed 2026 — disagreements:**

  - Tyrone Tracy Jr. ($4100): historical `starter`, observed mean snap share 0.025. history calls him a starter; observed 2026 snap share is low. Role may have moved, or he may have missed time -- held evidence does not separate those.
  - Malachi Fields ($4400): historical `fringe`, observed mean snap share 0.765. history calls him fringe ONLY for want of prior-season snaps; 2026 shows a substantial role. The label is materially misleading for him.

### TEN — 9 materially active in 2026 (1 of them with no Q9 features)

- **QB (pass attempts, wk1+2):** Cam Ward 57.0
- **Backfield (carries):** Tony Pollard 21.0, Tyjae Spears 10.0
- **WR (targets):** Carnell Tate 11.0, Wan'Dale Robinson 7.0, Elic Ayomanor 6.0, Calvin Ridley 2.0, Chimere Dike 1.0
- **TE (targets):** Gunnar Helm 7.0, Daniel Bellinger 2.0

**Historical label vs observed 2026 — disagreements:**

  - Carnell Tate ($5000): historical `fringe`, observed mean snap share 0.815. history calls him fringe ONLY for want of prior-season snaps; 2026 shows a substantial role. The label is materially misleading for him.


---

## Rerun after official inactives

python3.12 nfl/tools/today_state.py --write writes THIS artifact. After authoritative inactives arrive, store them via nfl/production/nonqb/inactives.py (store -> parse -> resolve -> sets), then rerun with a post-inactives output path and diff with nfl/dfs/salaries/baseline_diff.py. Do NOT overwrite this file: the whole point is a measurable before and after.

