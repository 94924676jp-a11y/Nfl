# DET @ BUF, 2026 week 2 — sealed model against a frozen Hard Rock Bet snapshot

**MARKET IS EVALUATION DATA, NOT PREDICTIVE DATA.** Nothing in this artifact
was read back into a projection, a mean, a distribution, a parameter, CS1 or
OAS1. The forecast was sealed 30 hours before the snapshot and has not been
regenerated since.

## 1. Chronology, which is the thing that makes this prospective

| Event | Time (UTC) |
|---|---|
| Forecast SEALED | **2026-09-16T15:45:14Z** |
| Earliest market line timestamp | 2026-09-17T15:23:40.526596Z |
| Latest market line timestamp | 2026-09-17T21:43:28.420272Z |
| Snapshot retrieved | 2026-09-17T21:44:31Z, 2026-09-17T21:45:02Z |
| Kickoff | 2026-09-18T00:15:00Z |

Forecast precedes market: **True**.
Market precedes kickoff: **True**.
No forecast regenerated after reading market data: **True**.

## 2. Provenance

**Forecast** `c3probe_V1_CANDIDATE_R9_W1P_GSVUC/d709e67b82d5b01c` — status SEALED, 8,000 draws,
54 matrices, draws sha256 `c24d9dccbe6d76f25c9643ba3dcf0f19…`,
code commit `b62a71ff90805141e808557111ee0ada013f7eb8…`.

**Market** Hard Rock Bet, fixture `202609189BE34D3B`, DET @ BUF, week 2.

| Item | Value |
|---|---|
| CSV sha256 | `99700dc341322482cc6c3ce8118366cb1b925058f788be35802cf1f3da40c290` |
| CSV | 550,738 bytes, 922 rows × 26 columns |
| ZIP sha256 | `478866d840679da09d4d497bd141bf3a7caa1a89511ecca28ee7f3defabcfac3` |
| ZIP | 201,804 bytes, 28 entries, preserved unchanged |
| Player-prop rows | 599 |
| Main lines / alternates | 78 / 844 |
| Duplicate market_id | 902 |
| Distinct line timestamps | 162 |

Row counts reconcile: 922 = 599 player-prop +
323 game/team. Status:
open_one_sided_over 120, open_one_sided_under 8, open_single_selection 178, open_two_sided 616.
Push rule: no push, half-point line 784, push on exact line 138.

**Alternates are not collapsed** and **line timestamps are not replaced by the
retrieval time** — each row keeps its own `line_timestamp_utc`, spanning
162 distinct values from 15:23Z to 21:43Z.

**Feed limitation, recorded explicitly.** Hard Rock via OpticOdds shows two-sided or one-sided AVAILABILITY. It cannot distinguish a market that was explicitly SUSPENDED from one that was removed or never posted. An absent market is therefore absent, and no inference about suspension is drawn from it.

## 3. Coverage — every one of the 922 rows lands in exactly one state

| State | Rows |
|---|---|
| `EXACT_MODEL_SUPPORTED` | 438 |
| `MODEL_STAT_NOT_AVAILABLE` | 36 |
| `PLAYER_NOT_IN_MODEL_UNIVERSE` | 21 |
| `IDENTITY_UNRESOLVED` | 2 |
| `ONE_SIDED_MARKET` | 102 |
| `NON_PLAYER_MARKET` | 323 |
| **TOTAL** | **922** |

Exact among main lines: 43 of 78.
Exact among alternates: 395 of 844.

**A correction made during this pass.** The two kickers first classified as
`PLAYER_NOT_IN_MODEL_UNIVERSE`. That was wrong: the sealed draws carry a
`kicking` layer with one row per club (`00-0036162` BUF, `00-0039172` DET), so
the model universe *does* contain a kicker for each team. What is missing is
the name-to-id mapping — the board's 29 named players omit both kicking rows.
That is `IDENTITY_UNRESOLVED`. The join was **not** completed by (team,
position): each club has exactly one kicking row and exactly one PK in the
market, so it would almost certainly be right, and "almost certainly right" is
how a silent mis-attribution enters a prospective artifact.

## 4. Main-line board — 43 exactly evaluated rows

| Player | Market | Line | Odds | Model mean | Median | P(over) | No-vig | Edge | EV over | EV under |
|---|---|---|---|---|---|---|---|---|---|---|
| Jared Goff | Interceptions | 0.5 | -110/-120 | 0.56 | 0.0 | 0.426 | 0.490 | -0.064 | -0.186 | +0.052 |
| Josh Allen | Interceptions | 0.5 | 125/-160 | 0.65 | 0.0 | 0.464 | 0.419 | +0.044 | +0.043 | -0.128 |
| Jared Goff | Passing Attempts | 36.5 | -105/-125 | 30.67 | 32.0 | 0.258 | 0.480 | -0.222 | -0.496 | +0.335 |
| Josh Allen | Passing Attempts | 31.5 | -105/-125 | 29.16 | 30.0 | 0.432 | 0.480 | -0.048 | -0.157 | +0.023 |
| Jared Goff | Passing Completions | 23.5 | -130/100 | 20.82 | 21.0 | 0.370 | 0.531 | -0.161 | -0.345 | +0.260 |
| Josh Allen | Passing Completions | 20.5 | -125/-105 | 19.31 | 20.0 | 0.454 | 0.520 | -0.067 | -0.183 | +0.067 |
| Jared Goff | Passing Touchdowns | 1.5 | -150/115 | 1.45 | 1.0 | 0.426 | 0.563 | -0.137 | -0.290 | +0.234 |
| Josh Allen | Passing Touchdowns | 1.5 | -200/145 | 1.37 | 1.0 | 0.400 | 0.620 | -0.221 | -0.401 | +0.471 |
| Jared Goff | Passing Yards | 260.5 | -115/-115 | 241.48 | 242.8 | 0.423 | 0.500 | -0.077 | -0.208 | +0.078 |
| Josh Allen | Passing Yards | 255.5 | -115/-115 | 224.31 | 224.0 | 0.375 | 0.500 | -0.125 | -0.298 | +0.168 |
| Amon-Ra St. Brown | Receiving Yards | 80.5 | -120/-110 | 77.29 | 70.0 | 0.409 | 0.510 | -0.101 | -0.250 | +0.129 |
| Brock Wright | Receiving Yards | 5.5 | -120/-110 | 14.57 | 8.0 | 0.546 | 0.510 | +0.036 | +0.001 | -0.133 |
| DJ Moore | Receiving Yards | 65.5 | -115/-115 | 37.62 | 28.0 | 0.195 | 0.500 | -0.305 | -0.636 | +0.505 |
| Dalton Kincaid | Receiving Yards | 53.5 | -115/-115 | 24.77 | 17.0 | 0.149 | 0.500 | -0.351 | -0.721 | +0.591 |
| Dawson Knox | Receiving Yards | 12.5 | -120/-110 | 20.59 | 10.0 | 0.463 | 0.510 | -0.047 | -0.150 | +0.024 |
| Isaac TeSlaa | Receiving Yards | 17.5 | -115/-115 | 16.76 | 4.0 | 0.344 | 0.500 | -0.156 | -0.356 | +0.226 |
| Jahmyr Gibbs | Receiving Yards | 31.5 | -115/-115 | 27.13 | 22.0 | 0.347 | 0.500 | -0.153 | -0.351 | +0.221 |
| James Cook | Receiving Yards | 18.5 | -120/-110 | 10.85 | 0.0 | 0.211 | 0.510 | -0.299 | -0.613 | +0.506 |
| Jameson Williams | Receiving Yards | 59.5 | -115/-115 | 53.11 | 43.0 | 0.363 | 0.500 | -0.137 | -0.320 | +0.190 |
| Keon Coleman | Receiving Yards | 14.5 | -115/-115 | 28.59 | 17.0 | 0.525 | 0.500 | +0.025 | -0.018 | -0.112 |
| Khalil Shakir | Receiving Yards | 44.5 | -115/-115 | 48.65 | 39.0 | 0.452 | 0.500 | -0.048 | -0.154 | +0.024 |
| Sam LaPorta | Receiving Yards | 46.5 | -115/-115 | 40.89 | 35.0 | 0.364 | 0.500 | -0.136 | -0.319 | +0.188 |
| Amon-Ra St. Brown | Receptions | 7.5 | -110/-120 | 6.74 | 6.0 | 0.367 | 0.490 | -0.123 | -0.300 | +0.161 |
| DJ Moore | Receptions | 4.5 | -115/-115 | 2.82 | 2.0 | 0.210 | 0.500 | -0.289 | -0.606 | +0.476 |
| Dalton Kincaid | Receptions | 4.5 | 125/-165 | 2.29 | 2.0 | 0.167 | 0.417 | -0.250 | -0.625 | +0.338 |
| Dawson Knox | Receptions | 1.5 | 125/-160 | 1.81 | 1.0 | 0.450 | 0.419 | +0.030 | +0.012 | -0.106 |
| Isaac TeSlaa | Receptions | 1.5 | -120/-110 | 1.16 | 1.0 | 0.302 | 0.510 | -0.208 | -0.445 | +0.332 |
| Jahmyr Gibbs | Receptions | 4.5 | 110/-145 | 3.48 | 3.0 | 0.300 | 0.446 | -0.146 | -0.370 | +0.183 |
| James Cook | Receptions | 2.5 | -115/-115 | 1.21 | 0.0 | 0.193 | 0.500 | -0.307 | -0.640 | +0.510 |
| Jameson Williams | Receptions | 3.5 | -160/120 | 3.26 | 3.0 | 0.404 | 0.575 | -0.171 | -0.344 | +0.311 |
| Keon Coleman | Receptions | 1.5 | 140/-180 | 2.00 | 2.0 | 0.503 | 0.393 | +0.109 | +0.207 | -0.226 |
| Khalil Shakir | Receptions | 4.5 | 115/-150 | 4.15 | 4.0 | 0.407 | 0.437 | -0.029 | -0.124 | -0.012 |
| Sam LaPorta | Receptions | 4.5 | -105/-125 | 3.66 | 3.0 | 0.328 | 0.480 | -0.152 | -0.360 | +0.210 |
| Jahmyr Gibbs | Rushing + Receiving Yards | 123.5 | -120/-110 | 122.78 | 122.0 | 0.487 | 0.510 | -0.023 | -0.107 | -0.020 |
| James Cook | Rushing + Receiving Yards | 102.5 | -115/-115 | 52.09 | 46.0 | 0.180 | 0.500 | -0.320 | -0.663 | +0.533 |
| Jahmyr Gibbs | Rushing Attempts | 18.5 | -115/-115 | 22.36 | 23.0 | 0.709 | 0.500 | +0.209 | +0.326 | -0.457 |
| James Cook | Rushing Attempts | 17.5 | -125/-105 | 9.58 | 9.0 | 0.220 | 0.520 | -0.300 | -0.604 | +0.522 |
| Jahmyr Gibbs | Rushing Yards | 88.5 | -115/-115 | 95.65 | 94.0 | 0.551 | 0.500 | +0.051 | +0.029 | -0.160 |
| James Cook | Rushing Yards | 80.5 | -115/-115 | 41.24 | 32.0 | 0.193 | 0.500 | -0.307 | -0.640 | +0.509 |
| Jared Goff | Rushing Yards | 0.5 | 125/-165 | 3.93 | 1.8 | 0.568 | 0.417 | +0.152 | +0.285 | -0.310 |
| Josh Allen | Rushing Yards | 32.5 | -120/-110 | 30.82 | 24.3 | 0.367 | 0.510 | -0.143 | -0.326 | +0.207 |
| Ray Davis | Rushing Yards | 8.5 | -120/-110 | 29.83 | 15.0 | 0.591 | 0.510 | +0.081 | +0.084 | -0.219 |
| Sione Vaki | Rushing Yards | 4.5 | -120/-110 | 11.48 | 0.0 | 0.344 | 0.510 | -0.166 | -0.370 | +0.253 |

Full machine-readable output: `MAIN_LINE_BOARD.csv`, `FULL_LADDER_BOARD.csv`
(395 exact alternate rows),
`ALL_ROWS.csv` (all 922), `PROVENANCE.json`.

## 5. Unsupported markets, refused by name

| Market | Rows | Why |
|---|---|---|
| Player Touchdowns | 13 | a touchdown ladder needs each player`s TOTAL touchdowns in the same simulated world. Receiving, rushing and passing touchdowns live in three separate  |
| Player Rushing Attempts | 9 | no declared mapping to a sealed array |
| Player Longest Reception | 8 | settles on the MAXIMUM single reception. The sealed world holds per-game receiving totals and per-catch atoms are not exported in this artifact, so a  |
| Player Kicking Points | 2 | requires the kicker`s scoring construction (field goals by distance bucket plus extra points) resolved to a point total in the same draw. The arrays e |
| Player Longest Passing Completion | 2 | settles on the maximum single completion; not present as an event-level quantity. |
| Player Longest Rush | 2 | settles on the maximum single carry; the sealed world holds per-game rushing totals only. |

Nothing was manufactured. A maximum cannot be recovered from a sum, so the
three longest-* markets stay unsupported. `Player Touchdowns` needs each
player's total touchdowns in the same simulated world; receiving, rushing and
passing touchdowns live in three layers with different row sets and combining
them is a construction this artifact has not verified. `Player Kicking Points`
has the arrays but not a verified scoring composition. **Unsupported is
preferable to approximation.**

## 6. Goff passing attempts, 35.5 → 36.5

The line moved between 21:42Z and 21:44Z. The model did not move; only the
threshold it is evaluated at did. This is the demonstration of why an exact
CDF-at-line export matters.

Model: mean 30.6747, median 32.0, sd 11.4190, n = 8,000.

| Threshold | Price | Model P(over) | MCSE | No-vig P(over) | Edge | EV over | EV under |
|---|---|---|---|---|---|---|---|
| 35.5 (21:42, superseded) | −130/+100 | 0.3093 | 0.0052 | 0.5306 | −0.2214 | −0.4529 | +0.3815 |
| **36.5 (21:44, official)** | −105/−125 | **0.2581** | 0.0049 | 0.4797 | **−0.2216** | −0.4960 | +0.3354 |

Two things worth stating. P(over) falls by exactly **0.0511**, which is
precisely `P(attempts = 36) = 0.0511` — the atom sitting between the two
half-point lines, readable only from the draws. And the **edge is unchanged**
to four decimals (−0.2214 vs −0.2216): the model's disagreement here is a
disagreement about the level, not an artifact of where the threshold sits. The
line movement is not treated as information.

## 7. Largest model-vs-market probability differences

| Player | Market | Line | Main | Model P(over) | No-vig | Edge |
|---|---|---|---|---|---|---|
| James Cook | Rushing Yards | 40.5 | alt | 0.445 | 0.867 | -0.422 |
| Dalton Kincaid | Receiving Yards | 33.5 | alt | 0.298 | 0.720 | -0.422 |
| James Cook | Rushing Yards | 50.5 | alt | 0.373 | 0.793 | -0.420 |
| James Cook | Rushing Yards | 45.5 | alt | 0.412 | 0.831 | -0.419 |
| James Cook | Rushing Yards | 39.5 | alt | 0.451 | 0.868 | -0.417 |
| James Cook | Rushing Yards | 35.5 | alt | 0.481 | 0.897 | -0.416 |
| James Cook | Rushing Yards | 30.5 | alt | 0.512 | 0.927 | -0.415 |
| Dalton Kincaid | Receiving Yards | 28.5 | alt | 0.355 | 0.768 | -0.413 |
| James Cook | Rushing Yards | 49.5 | alt | 0.382 | 0.794 | -0.412 |
| Dalton Kincaid | Receiving Yards | 38.5 | alt | 0.253 | 0.663 | -0.409 |
| James Cook | Rushing Yards | 55.5 | alt | 0.338 | 0.742 | -0.405 |
| Dalton Kincaid | Receiving Yards | 39.5 | alt | 0.244 | 0.649 | -0.404 |

## 8. Largest price-specific EV

**A comparison statistic, not a recommendation, and not a validated edge.**
Every one of these is a long-odds alternate line on a player the model already
disagrees with at the main line — the same disagreement priced at longer odds,
not an independent finding. See section 10.

| EV/unit | Side | Player | Market | Line | Odds | Model p |
|---|---|---|---|---|---|---|
| +5.347 | under | James Cook | Rushing Yards | 30.5 | 1200 | 0.488 |
| +4.511 | under | Dalton Kincaid | Receiving Yards | 8.5 | 1300 | 0.394 |
| +3.674 | under | James Cook | Rushing Yards | 35.5 | 800 | 0.519 |
| +3.119 | under | DJ Moore | Receiving Yards | 15.5 | 1100 | 0.343 |
| +2.913 | under | Dalton Kincaid | Receiving Yards | 13.5 | 750 | 0.460 |
| +2.883 | under | James Cook | Rushing Yards | 40.5 | 600 | 0.555 |
| +2.841 | under | James Cook | Rushing Yards | 39.5 | 600 | 0.549 |
| +2.552 | under | Josh Allen | Passing Yards | 145.5 | 1750 | 0.192 |
| +2.505 | under | DJ Moore | Receiving Yards | 20.5 | 750 | 0.412 |
| +2.459 | over | Ray Davis | Rushing Yards | 53.5 | 1600 | 0.203 |
| +2.386 | under | Dalton Kincaid | Receiving Yards | 18.5 | 550 | 0.521 |
| +2.234 | under | James Cook | Rushing Yards | 45.5 | 450 | 0.588 |

## 9. Monte Carlo uncertainty

8,000 draws per market. MCSE on P(over): min 0.00121, median
0.00478, max 0.00559. Worst case at p = 0.5 is
0.00559.

**19 of 438** exact rows have an absolute edge inside 2 MCSE —
indistinguishable from the market at this draw count. The remaining
419 are larger than simulation noise, which says they are real
disagreements, **not** that they are correct.

## 10. Model pathologies found while evaluating thresholds

These are the most valuable output of this exercise, and they are findings
about the MODEL, not about the book.

**P1 — systematic under-projection, not a set of independent edges.** Across
all 438 exact rows the mean `edge_over` is **-0.1000**, median
-0.0851, negative in **77.9%** of rows. On the
43 main lines: mean -0.1174, negative in 79.1%.
A model merely noisy about the book would scatter around zero.

**P2 — the error is team- and role-asymmetric, which localises it.** Ratio of
model mean to the posted main line, by player:

| Player | Team | mean / line |
|---|---|---|
| Dalton Kincaid | BUF | 0.486 |
| James Cook | BUF | 0.527 |
| DJ Moore | BUF | 0.600 |
| Sam LaPorta | DET | 0.846 |
| Isaac TeSlaa | DET | 0.866 |
| Jameson Williams | DET | 0.912 |
| Amon-Ra St. Brown | DET | 0.929 |
| Jahmyr Gibbs | DET | 0.984 |
| Josh Allen | BUF | 0.986 |
| Khalil Shakir | BUF | 1.008 |
| Dawson Knox | BUF | 1.426 |
| Keon Coleman | BUF | 1.652 |
| Jared Goff | DET | 2.099 |
| Sione Vaki | DET | 2.551 |
| Brock Wright | DET | 2.649 |
| Ray Davis | BUF | 3.509 |

Buffalo's starters sit far **below** the market — Kincaid 0.486, Cook 0.527,
Moore 0.600 — while Buffalo's backups sit far **above** it — Ray Davis 3.509,
Keon Coleman 1.652, Dawson Knox 1.426. Detroit clusters near 1.0 (Gibbs 0.984,
St. Brown 0.929, Williams 0.912). That is the signature of **opportunity being
spread away from Buffalo's starters onto its backups**, not of a uniformly
pessimistic model. It is a concrete place to look.

**P3 — large zero atoms beside non-trivial means.** Several receivers carry
P(exactly 0) above 0.55 with a positive mean: James Cook receiving yards mean
10.85 with P(0) = 0.558 and median 0.0; Sione Vaki rushing yards mean 11.48
with P(0) = 0.583. A half-point line near zero therefore sits on a very steep
part of the CDF, and the mean is a poor summary of it — which is exactly why
these were evaluated from draws.

**P4 — strong right skew on main lines.** Ray Davis rushing yards mean 29.83
against median 15.0; Isaac TeSlaa receiving yards mean 16.76 against median
4.0. A half-point line sits near the median, so a mean-based comparison would
have reported a different and wrong answer.

**P5 — the large EV figures are a consequence of P1, not independent edges.**
51 rows show EV above +1.0 per unit stake and they concentrate in ten players,
with James Cook (11), DJ Moore (9), Dalton Kincaid (9) and Ray Davis (8)
accounting for 37 of them. These are the same four disagreements from P2,
re-priced at long odds down the alternate ladder.

## What is NOT claimed

The market is not "wrong" anywhere in this document. A divergence is a
divergence. **No apparent edge is validated**, no play is recommended, and the
sealed forecast is unchanged by everything above. On this evidence the model's
disagreements are more likely to be P2 than to be opportunity.

**MARKET IS EVALUATION DATA, NOT PREDICTIVE DATA**

**V2 NOT YET EARNED**

