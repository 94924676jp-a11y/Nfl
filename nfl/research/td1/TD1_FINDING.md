# TD1 finding — touchdown / red-zone decomposition

Pre-registration sha256
`8effcb5a95ec1cfe721dde743c3f394889135c3e8c423156163e34ad849f2d6c`, committed
before any result existed.

**EXPLORATORY.** 2022–2025 are heavily mined. Nothing is promoted.

## Result

Identity `TD = (TeamOpp × Share) × [Z·k_rz + (1−Z)·k_nrz]`. **All four oracled
reproduces the realised TD count exactly** — max |error| 2.2e-16 to 4.4e-16 in
every season, both kinds. Shapley efficiency gap **0.00e+00**.

### Receiving TD — n 22,521, mean TD 0.1371, baseline CRPS 0.13562, Brier(TD≥1) 0.10104

| component | Shapley CRPS | share | 95% CI |
|---|---|---|---|
| `V` team scoring environment | 0.00365 | **2.69%** | [0.00327, 0.00397] |
| `S` player opportunity share | 0.01055 | **7.78%** | [0.00968, 0.01139] |
| `Z` red-zone allocation | 0.01760 | **12.98%** | [0.01577, 0.01935] |
| **`K` conversion** | **0.10382** | **76.55%** | [0.10153, 0.10607] |

### Rushing TD — n 22,521, mean TD 0.0682, baseline CRPS 0.06104, Brier(TD≥1) 0.04337

| component | Shapley CRPS | share | 95% CI |
|---|---|---|---|
| `V` team scoring environment | 0.00271 | **4.45%** | [0.00238, 0.00306] |
| `S` player opportunity share | 0.00482 | **7.90%** | [0.00421, 0.00551] |
| `Z` red-zone allocation | 0.00768 | **12.59%** | [0.00660, 0.00867] |
| **`K` conversion** | **0.04582** | **75.07%** | [0.04442, 0.04713] |

## Diagnosis

**Both TD layers are conversion-dominated, and they agree to within 1.5
percentage points** — 76.55% receiving, 75.07% rushing. Opportunity in all its
forms (`V + S + Z`) is 23.45% and 24.93%.

**That is the opposite of receiving yards**, where RC1 measured opportunity at
53.86% and conversion at 46.14%. Same players, same games, same season set — a
different outcome layer with a different structure.

The ordering inside opportunity is stable across both kinds: red-zone
allocation `Z` (≈13%) matters more than a player's share of team opportunity
`S` (≈8%), which matters more than the team's scoring environment `V` (3–4%).
**Where you get the ball matters more than how often**, once conversion is held
aside.

## The caveat that governs how this may be read

**A large oracle share does not imply modelability, and here there is a
structural reason to expect `K` to overstate what any forecaster could reach.**

TD is a rare, near-binary event: mean 0.137 receiving and 0.068 rushing per
player-game. Oracling `K` means being handed the player's realised conversion
rate *for that game* — and conditional on the realised opportunity count, that
is very close to being handed the outcome itself. For a Bernoulli-ish outcome
the conversion "rate" and the result are nearly the same object.

Contrast RC1's `V`, yards per reception: a continuous quantity averaged over
several catches, where an oracle genuinely supplies information distinct from
the total.

**So the honest reading is: TD variance lives overwhelmingly downstream of
opportunity, and most of that is irreducible per-game randomness rather than a
modelling target.** The recoverable portion has **not** been measured — §3.4's
ladder and §3.5's composition were not run in this session (see below) — so no
claim about modelability is made in either direction.

## State classification

**`DECOMPOSED`** — not `CONVERSION_DOMINATED` as a research verdict, because
that phrase would smuggle in the modelability claim the caveat above forbids.

The decomposition is complete and the identity is exact. The recoverability
ladder (§3.4) and the composition test (§3.5) were **not run** and are recorded
as open. Until they are, this layer is decomposed and not characterised, and it
would be an error to fund conversion modelling on the 75% figure alone —
precisely the mistake RC1 was designed to prevent.

## Provenance notes carried forward

- **End-zone targets are UNAVAILABLE.** `yardline_100` is the line of
  scrimmage, not target depth. Marked unavailable rather than proxied.
- Named exclusions, measured: `no_play` 26,592; `yardline_100` NULL 4,806
  (composition measured as `no_play` plus blank play_type — never a live
  scrimmage play, and **excluded rather than coerced to 0**, since 0 reads as
  the 1-yard line); kneel/spike 2,931; two-point 794; defensive TD 388;
  recovery and blocked-kick TD 45.
- Scrambles carry `rusher_player_id` on 4,091 of 4,380 and `passer_player_id`
  on **zero**, preserving the project's standing warning.

Nothing is promoted. G0A 11/12. NFL-1 NOT AUTHORIZED.
