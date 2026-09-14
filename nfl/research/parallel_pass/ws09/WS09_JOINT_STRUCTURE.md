# WS09 — Joint simulation structure, audited from the stored draws

**CODE CHANGED: NO.** Research only. No file outside
`nfl/research/parallel_pass/ws09/` was created or modified. Nothing in
`nfl/production/` was run in a way that writes. Every number below was read out
of a sealed `player_draws.npz` or out of source; none is recalled.

## 0. What was measured, and how rows were addressed

Four sealed runs, all `model_configuration = V1_CANDIDATE_R8`, all with
`candidate_components_applied = [A1, A3G, C0, C3, R2, R5, R6, R8, SC1]` and
`candidate_components_not_reached = []`:

| Game | Arm / config | Run id | n_draws | qb rows | receiving rows | rushing rows |
|---|---|---|--:|--:|--:|--:|
| 2026_01_DAL_NYG | FORENSIC_CORRECTED_RESEARCH | `4b186a21b83a49ec` | 8000 | 6 | 30 | 9 |
| 2026_01_ATL_PIT | pre_inactives_V1_CANDIDATE_R8 | `f67d72ab0701d211` | 1000 | 8 | 24 | 5 |
| 2026_01_TB_CIN  | post_inactives_V1_CANDIDATE_R8 | `e92b9e19466d27bd` | 1000 | 8 | 28 | 7 |
| 2026_01_NO_DET  | post_inactives_V1_CANDIDATE_R8 | `b5b02f6365ead28f` | 1000 | 8 | 26 | 7 |

Every array was addressed by `manifest['layers'][layer]['row_ids']`
(`row_axis='gsis_id'`; `team_volume` uses `row_axis='team'`). No positional
indexing was used anywhere in the analysis: the loader builds
`{row_id -> index}` from the manifest and refuses an unknown id. Player team,
position and depth-chart slot came from `board.json['players']`, joined on
`gsis_id`.

**The manifest's own warning is load-bearing and is quoted here in full**
(`player_draws_manifest.json -> draw_index_semantics`, written by
`nfl/production/draws_artifact.py:97-99`):

> `within_row_across_metrics: SAME_SIMULATED_WORLD`;
> `across_rows: INDEPENDENT_STREAMS_COLUMN_ALIGNED`; "column j is the same
> iteration of one row's stream for every metric of that row, so cross-metric
> dependence on this axis is real. Rows are seeded independently, so a
> CROSS-ROW correlation read off the same axis measures the generator's lack of
> coupling, not a football quantity."

That declaration is **true of the `qb` layer and false of the `receiving` and
`rushing` layers**, and the manifest itself says so one field away: the `qb`
layer's `rng_stream` is `numpy default_rng([seed, ord, gsis_id]) -- one stream
per row`, while `receiving` is `P4C simplex allocation and RC1 conversion on
the shared game draw index` and `rushing` is `P4C simplex allocation over the
A1 running-back budget on the shared game draw index`. A blanket
`ACROSS_ROWS = INDEPENDENT_STREAMS_COLUMN_ALIGNED` constant
(`draws_artifact.py:98`) is stamped on every layer regardless. A reader who
obeyed the top-level note would discard the real receiver competition measured
in §3 as a generator artefact. **Finding J-0 below.**

Monte-Carlo noise floor on a correlation at the null: +/- 0.0219 (95%) at
n=8000, +/- 0.0621 at n=1000. Nothing under those bands is read as a signal.

---

## 1. Team-level accounting matrix (all 8 team-sides)

`r` is the draw-level Pearson correlation over the whole draw index. `exact` is
the fraction of draws where the two quantities are bit-equal.

| Relation | r (range over 8 team-sides) | mean(a-b) | exact | Reading |
|---|---|---|---|---|
| sum(QB pyds) vs sum(receiver receiving_yards) | **+1.0000** all 8 | 0.0000 | **100.00%** | hard identity, C3 |
| sum(QB cmp) vs sum(receiver receptions) | **+1.0000** all 8 | 0.0000 | **100.00%** | hard identity, C3 |
| sum(QB db) vs (att + sacks + scr) | **+1.0000** all 8 | 0.0000 | **100.00%** | QB dropback identity |
| sum(QB db) vs `team_dropbacks_part` | +0.9994 … +0.9996 | -0.24 … +0.13 | 0.00% | integerisation only |
| sum(QB att) vs sum(receiver targets) | +0.9566 … +0.9759 | +1.46 … +1.98 | 20 – 29% | C3 count identity (see below) |
| sum(QB att) vs **`team_volume/team_targets`** | +0.8075 … +0.8815 | -0.60 … +3.78 | 0.00% | **two owners — §5** |
| `team_volume/team_targets` vs sum(receiver targets) | +0.7879 … +0.8401 | -2.06 … +2.06 | 0.00% | **two owners — §5** |
| `team_volume/team_carries` vs sum(RB carries) | +0.5373 … +0.8469 | +8.28 … +11.39 | 0.00% | A1 partition + §6 |
| `team_volume/team_carries` vs sum(QB rush_opp) | **-0.2110 … -0.0084** | — | — | **§7** |
| `team_off_snaps` vs `team_targets` | +0.4986 … +0.7437 | — | — | real |
| `team_targets` vs `team_carries` (same team) | -0.3023 … -0.1655 | — | — | pass/run tradeoff |

**The attempts-vs-targets gap is an identity, not a leak.** `sum(QB att) -
sum(receiver targets)` is >= 0 in **100.00% of draws on all eight team-sides**
(min 0, max 15–32, mean +1.46 to +1.98). That residual is exactly the
`untargeted + other` pool C3 defines at `football_engine.py:453-477`
(`sum_i targets_i + other == targeted`, and `targeted = attempts - untargeted`).
Checked and clean.

**The yards and completions identities are exact, and that is the single
strongest joint property in the artifact.** The engine's own comment at
`football_engine.py:408-418` records the pre-C3 state it replaced:
`corr(team passing yards, team receiving yards) = +0.001` with the yard
identity violated in 12,800 of 12,800 draws. Measured today: r = 1.0000,
violated in 0 of 8000 (DAL_NYG) and 0 of 1000 (each other game).

---

## 2. QB <-> receiver, player level

`r(QB1 att, player targets)` and `r(QB1 pyds, player receiving_yards)`, top
five receivers by mean targets on each team-side (abbreviated; full sweep ran
on all 8 sides):

| Game / team | receiver | r(QB1 att, tgts) | r(team att, tgts) | r(QB1 pyds, rec yds) | r(team pyds, rec yds) |
|---|---|--:|--:|--:|--:|
| DAL_NYG DAL | WR1 | +0.1196 | +0.3113 | +0.1755 | +0.4351 |
| DAL_NYG DAL | WR2 | +0.0954 | +0.2573 | +0.1785 | +0.4757 |
| DAL_NYG DAL | RB1 | +0.0650 | +0.1551 | +0.0374 | +0.0639 |
| DAL_NYG NYG | WR1 | +0.3105 | +0.4837 | +0.3804 | +0.5060 |
| ATL_PIT PIT | WR1 | +0.2674 | +0.4257 | +0.4098 | +0.5166 |
| TB_CIN CIN | WR1 | +0.1891 | +0.3522 | +0.3921 | +0.5208 |
| TB_CIN TB | TE1 | +0.2498 | +0.3680 | +0.3089 | +0.3680 |
| NO_DET DET | WR1 | +0.3087 | +0.4872 | +0.3792 | +0.5156 |
| NO_DET NO | WR1 | +0.2277 | +0.3580 | +0.3545 | +0.4453 |

Range across all eight sides: `r(QB1 att, WR1 targets)` +0.0767 … +0.3105;
`r(team att, WR1 targets)` +0.1996 … +0.4872; `r(QB1 pyds, WR1 yards)` +0.0731
… +0.4098.

Two things are visible. First, **team-level attempts correlate with a
receiver's targets roughly twice as strongly as the named QB1's own attempts
do**, because the C3 budget is the *room's* attempts and the room is split (§4).
DAL is the extreme case: QB1 att -> WR1 targets is only +0.1196 while team att
-> WR1 targets is +0.3113, because the DAL quarterback room is a near coin-flip
(§4). A consumer pricing "QB1 passing yards over" against "WR1 receiving yards
over" on the same ticket would be reading +0.18, not +0.44.

Second, the **individual QB1-pyds/receiver-yards correlations cap out near
+0.41 even though the team sums are an exact identity**, because the multinomial
deal plus per-row RC1 conversion inject a large amount of receiver-specific
noise between the team total and the player.

**Cross-team (opponent) receiver targets vs QB1 attempts: -0.0847 … +0.0295**,
i.e. at or just outside the n=1000 noise band and well inside it at n=8000.
This is the only channel by which one team's passing game touches the other's,
and it runs entirely through A3G (§8).

---

## 3. Teammates competing for the same opportunity pool

**Raw pairwise correlation of teammate targets is not a usable read, and this
was very nearly a false finding.** Raw, the sign flips by team: DAL, ATL, CIN
and NO show WR1~WR2 at -0.111 … -0.175, while NYG, PIT, TB and DET show
+0.002 … +0.086. One might conclude four of eight teams have no receiver
competition modelled.

Conditioning on the team's realised target budget resolves it. **Partial
correlation given the team targeted budget is negative on every pair of every
team-side, without exception:**

| Game / team | WR1~WR2 raw | WR1~WR2 partial | range of partial over all top-4 pairs |
|---|--:|--:|---|
| DAL_NYG DAL | -0.175 | **-0.290** | -0.142 … -0.290 |
| DAL_NYG NYG | +0.002* | **-0.221** | -0.109 … -0.221 |
| ATL_PIT ATL | -0.111 | **-0.223** | -0.109 … -0.325 |
| ATL_PIT PIT | +0.023 | **-0.183** | -0.066 … -0.183 |
| TB_CIN CIN | -0.136 | **-0.287** | -0.012 … -0.287 |
| TB_CIN TB | +0.018 | **-0.169** | -0.154 … -0.193 |
| NO_DET DET | -0.037 | **-0.307** | -0.130 … -0.307 |
| NO_DET NO | -0.135 | **-0.274** | -0.104 … -0.332 |

\* NYG WR1~WR3; NYG has no WR2 in the top four.

The mechanism is `p4c_lib.allocate` mode `simplex`
(`nfl/research/p4c/p4c_lib.py:109-139`):
`S_i = w_i A_i (1 - w_other) / sum_g(w A)`. A normalised share vector is
negatively dependent by construction; multiplying it by a common budget adds a
positive common factor. The two nearly cancel, and which one wins is a property
of the ratio SD(budget)/mean(budget) on that team, not a property of the
competition. **Consumers reading raw teammate correlation off this artifact
will misread four of eight teams.**

**RB carries are negative raw as well as partial**, because the A1 running-back
budget is tighter relative to its own spread:

| Game / team | RB1~RB2 | other pairs |
|---|--:|---|
| DAL_NYG DAL | **-0.423** | RB1~FB1 -0.330, RB2~FB1 -0.161 |
| DAL_NYG NYG | -0.072 (RB3~RB1) | -0.050 … -0.147 |
| ATL_PIT ATL | **-0.446** | (only two rushers) |
| ATL_PIT PIT | -0.353 | RB1~RB3 -0.206, RB2~RB3 -0.159 |
| TB_CIN CIN | -0.353 | RB1~RB3 -0.220, RB2~RB3 -0.067 |
| TB_CIN TB | -0.096 | RB1~RB4 -0.113, RB2~RB4 -0.032 |
| NO_DET DET | **-0.386** | — |
| NO_DET NO | -0.168 (RB1~RB3) | RB1~RB4 -0.096, RB3~RB4 +0.029 |

`nan` pairs are players whose entire draw matrix is zero (official inactives
zeroed at `layers.py:224-240`) — correctly zero, not missing.

**Same player across pools** (`r(carries, targets)` for a back who is in both
layers) ranges +0.0068 … +0.4279 and is positive in 22 of 24 non-degenerate
cases. That is the shared appearance indicator and the shared team environment,
not a modelled pass-catching-back effect.

**Pooled summary over every receiver pair with non-zero variance:**

| Game | within-team pairs | mean r | mean abs r | cross-team pairs | mean r | mean abs r | max abs r |
|---|--:|--:|--:|--:|--:|--:|--:|
| DAL_NYG | 144 | -0.0216 | 0.0297 | 156 | -0.0079 | 0.0122 | 0.0366 |
| ATL_PIT | 133 | -0.0222 | 0.0330 | 143 | -0.0086 | 0.0304 | 0.1273 |
| TB_CIN | 132 | -0.0190 | 0.0350 | 144 | -0.0112 | 0.0242 | 0.0950 |
| NO_DET | 121 | -0.0200 | 0.0346 | 132 | -0.0143 | 0.0295 | 0.0985 |

---

## 4. Starter vs backup quarterback — the largest structural finding

| Game / team | QB1 mean att (P(att>0)) | QB2 mean att (P) | r(QB1,QB2) att | r(play indicators) | P(both play) |
|---|---|---|--:|--:|--:|
| DAL_NYG DAL | 20.09 (**0.573**) | 16.05 (**0.513**) | **-0.9183** | -0.8407 | 0.0862 |
| DAL_NYG NYG | 24.48 (0.930) | 2.26 (0.242) | -0.6668 | -0.4804 | 0.1730 |
| ATL_PIT ATL | 18.05 (**0.624**) | 7.34 (**0.543**) | -0.8749 | -0.7038 | 0.1690 |
| ATL_PIT PIT | 32.51 (0.927) | 2.09 (0.256) | -0.6700 | -0.4520 | 0.1860 |
| TB_CIN CIN | 33.39 (0.942) | 2.20 (0.239) | -0.7341 | -0.4327 | 0.1820 |
| TB_CIN TB | 29.80 (0.943) | 1.84 (0.228) | -0.7078 | -0.4524 | 0.1710 |
| NO_DET DET | 29.77 (0.922) | 2.10 (0.246) | -0.7451 | -0.4919 | 0.1700 |
| NO_DET NO | 29.30 (0.929) | 2.34 (0.228) | -0.7231 | -0.4994 | 0.1580 |

Starter-vs-backup anti-correlation is strong, real and mechanistically
justified: the shares sum to 1 in every draw
(`qb3_lib.allocate`, `nfl/research/qb3/qb3_lib.py:157-198`).

**The defect is one level down. Backups are strongly POSITIVELY correlated with
each other:**

| Game / team | backup pairs | r(att) | r(play ind.) | P(both play) | P(neither) |
|---|---|--:|--:|--:|--:|
| DAL_NYG NYG | QB2~QB3 | **+0.8963** | +0.6490 | 0.1668 | 0.7085 |
| ATL_PIT ATL | QB2~QB3 / QB2~QB4 / QB3~QB4 | **+0.9091 / +0.8759 / +0.9010** | +0.65 … +0.79 | 0.467 … 0.520 | 0.358 … 0.377 |
| ATL_PIT PIT | QB2~QB3 | +0.8736 | +0.7262 | 0.1950 | 0.7030 |
| TB_CIN CIN | QB2~QB3 | **+0.9170** | +0.6609 | 0.1650 | 0.7160 |
| TB_CIN TB | QB3~QB4 | **+0.9622** | +0.8062 | 0.2000 | 0.7300 |
| NO_DET DET | QB2~QB3 | +0.9065 | +0.6239 | 0.1650 | 0.7000 |

**Code path.** `nfl/research/qb3/qb3_lib.py:183-192`:

```
# 3. the remainder among the others, in proportion to their cell weight
tot = S.sum(0); rem = np.maximum(1.0 - tot, 0.0)
w = np.tile(pp[:, None], (1, m)); w[who, np.arange(m)] = 0.0
frac = np.where(ws > 0, w / np.maximum(ws, 1e-12), 0.0)
S = S + frac * rem[None, :]
```

`who` selects ONE primary per draw. Everything the primary did not take
(`rem`) is then fanned out **deterministically, in fixed proportion, to every
other quarterback in the room simultaneously**. There is no second selection.
So one latent scalar per draw drives QB2, QB3 and QB4 together, which is why
their pairwise correlations sit at +0.87 … +0.96 and why every team's backup
carries P(att > 0) in a narrow 0.21 – 0.26 band.

Two consequences, both measured:

1. **ATL's marginal contains a four-quarterback committee.** All four ATL
   passers have P(att>0) between 0.543 and 0.624, with mean attempts
   18.05 / 7.34 / 3.27 / 2.95 and P(QB3 and QB4 both throw) = 0.520. Football
   does not do this; a fixed-proportion remainder does.
2. **QB2 and QB3 props are near-duplicates of each other.** At r = +0.90 a
   consumer treating them as two positions is holding one.

This is the clearest single item on list (b).

---

## 5. `team_volume/team_targets` is a stored quantity the game did not use

`football_engine.py:485` sets, in the C3 evidence block,
`'d1_team_targets_unused': True`, and the comment at 408-418 is explicit that
`T = share x D1.team_targets` "multiplied a share by a SEPARATELY DRAWN count
of the same football quantity -- two owners of one number". Under C3 the budget
is the quarterbacks' attempts.

**But the npz still stores the unused D1 draw under the name
`team_volume/team_targets`, on the same draw index, with no marker.**
`run_forecast.py:1242-1255` builds the `team_volume` layer from
`fx['_team_volume']`, which is the raw `TV.forecast` output.

Measured: stored `team_targets` against the target count the game actually
dealt is r = **+0.7879 … +0.8401**, with per-draw differences up to 30.97
targets and exact agreement in **0.00%** of draws on all eight team-sides. It
is a plausible-looking, well-correlated, wrong number sitting in a field whose
name says it is the team's targets.

## 6. `team_volume/team_carries` is likewise not the level the game ran on

`run_forecast.py:750-766` computes the SC1-permuted carry level and hands it to
the engine as `team_carries_override` (line 782); `football_engine.py:256-260`
routes every carry read through `_team_carries()` so "the coupled level and the
raw D1 level can never both be live in the same game". That guarantee holds
*inside* the engine and does not extend to the artifact:
`fx['_team_volume']` — the pre-SC1 vector — is what gets written.

SC1 is a permutation (`scramble_coherence.py`, docstring), so the marginal is
identical and the mismatch is only detectable through the joint. It is
detectable:

| Game / team | draws with stored tc < QB scrambles | draws with stored tc < scr + RB carries | max excess |
|---|--:|--:|--:|
| DAL_NYG DAL | 0 | 2 (0.03%) | +0.397 |
| DAL_NYG NYG | 0 | 14 (0.17%) | +0.452 |
| ATL_PIT ATL | 0 | 1 (0.10%) | +0.097 |
| ATL_PIT PIT | 0 | 0 | — |
| TB_CIN CIN | 0 | 2 (0.20%) | +0.344 |
| **TB_CIN TB** | **1** | 5 (0.50%) | **+5.543** |
| NO_DET DET | 0 | 0 | — |
| NO_DET NO | 0 | 0 | — |

SC1 guarantees `carries >= scrambles` in **every** draw by construction. One
draw in the TB artifact has a stored carry level 5.54 below that draw's
scramble count. That single cell is a proof, not a tolerance: the stored vector
is a different permutation from the one the rushing layer partitioned.

## 7. QB rushing sits outside the team carry pool it should live in

| Game / team | r(team_carries, QB rush_opp) | r(team_carries, QB scr) | r(RB carries, QB rush_opp) |
|---|--:|--:|--:|
| DAL_NYG DAL | -0.0316 | -0.0230 | -0.1137 |
| DAL_NYG NYG | -0.1793 | -0.1391 | -0.2836 |
| ATL_PIT ATL | -0.0823 | -0.0776 | -0.1425 |
| ATL_PIT PIT | -0.0179 | -0.0486 | -0.1357 |
| TB_CIN CIN | -0.0958 | -0.0809 | -0.1659 |
| TB_CIN TB | -0.2110 | -0.1791 | -0.2910 |
| NO_DET DET | -0.2027 | -0.1596 | -0.1994 |
| NO_DET NO | -0.0084 | -0.0130 | -0.1175 |

Against the *stored* carry vector, QB rushing volume is at or barely outside
the noise band, and the sign is negative rather than the historical positive
the SC1 docstring quotes (`+0.1802` historically; `+0.0299` measured in the
model before SC1). SC1 permutes only far enough to remove the impossible tail;
it does not install the positive association. Note the comparison is partly
contaminated by §6, so this is reported as **PARTIAL**, not as a clean measure
of the coupled level.

QB within-row coherence is by contrast strong and correct (row-internal, which
the manifest declares real):

| Game / team QB1 | att~pyds | cmp~pyds | rush_opp~ryds | att~rush_opp | ptd~pyds | rtd~rush_opp |
|---|--:|--:|--:|--:|--:|--:|
| DAL_NYG DAL | +0.9470 | +0.9610 | +0.7957 | +0.7223 | +0.6704 | +0.3427 |
| DAL_NYG NYG | +0.8378 | +0.8885 | +0.7148 | +0.6182 | +0.3757 | +0.4141 |
| ATL_PIT ATL | +0.9455 | +0.9621 | +0.7197 | +0.6245 | +0.6033 | +0.2213 |
| ATL_PIT PIT | +0.8593 | +0.8971 | +0.7362 | +0.3431 | +0.4600 | +0.3002 |
| TB_CIN CIN | +0.8527 | +0.8951 | +0.5856 | +0.4475 | +0.4364 | +0.2632 |
| TB_CIN TB | +0.8551 | +0.8891 | +0.6981 | +0.4078 | +0.4349 | +0.2720 |
| NO_DET DET | +0.8659 | +0.8998 | +0.6923 | +0.3325 | +0.4426 | +0.2528 |
| NO_DET NO | +0.8521 | +0.9041 | +0.5868 | +0.5199 | +0.3981 | +0.2988 |

`att ~ rush_opp` is **positive** (+0.33 … +0.72). Within a fixed snap budget a
quarterback's dropbacks and designed runs compete; here they co-move because
both scale with his drawn share of the room. Flagged, not fixed.

## 8. Opposing team volume and game total (A3G)

| Game | off_snaps | targets | carries | dropbacks_part | rz_carries |
|---|--:|--:|--:|--:|--:|
| DAL_NYG (DAL,NYG) | **-0.4683** | -0.1775 | -0.1284 | -0.2059 | -0.0049 |
| ATL_PIT (ATL,PIT) | **-0.4584** | -0.2565 | -0.0579 | -0.1859 | -0.0457 |
| TB_CIN (CIN,TB) | **-0.4685** | -0.1902 | -0.1010 | -0.2188 | -0.0536 |
| NO_DET (DET,NO) | **-0.4657** | -0.2595 | +0.0141 | -0.3044 | +0.0440 |

A3G `off_snaps` is live, stable at r ~= -0.466 across all four games, and it
propagates only weakly to the metrics anyone prices:

| Game | SD(total off_snaps) | SD if independent | ratio | SD(total targets) | ratio | SD(total carries) | ratio |
|---|--:|--:|--:|--:|--:|--:|--:|
| DAL_NYG | 10.040 | 13.705 | **0.733** | 9.254 | 0.907 | 9.175 | 0.936 |
| ATL_PIT | 9.264 | 12.563 | **0.737** | 9.815 | 0.867 | 9.448 | 0.971 |
| TB_CIN | 9.542 | 13.010 | **0.734** | 10.579 | 0.900 | 10.207 | 0.949 |
| NO_DET | 9.494 | 12.884 | **0.737** | 9.218 | 0.861 | 9.512 | **1.007** |

Game-total receiver targets and receiving yards, built from the player draws:

| Game | cross-team r(sum targets) | cross-team r(sum rec yds) | SD(total tgts) vs indep | SD(total yds) vs indep |
|---|--:|--:|---|---|
| DAL_NYG | -0.1831 | -0.0841 | 9.551 / 10.568 | 104.97 / 109.61 |
| ATL_PIT | -0.1832 | -0.0714 | 10.610 / 11.699 | 110.92 / 115.07 |
| TB_CIN | -0.2066 | -0.1002 | 10.242 / 11.496 | 108.69 / 114.54 |
| NO_DET | -0.2578 | -0.1115 | 9.366 / 10.872 | 111.08 / 117.79 |

The A3G comment (`football_engine.py:279-289`) claims SD(total plays)
12.271 -> 9.269 against a historical 9.265. Reproduced: 12.563 -> 9.264 on
ATL_PIT and equivalents elsewhere. That specific claim stands.

**What is absent is any positive game-level latent.** The only cross-team
channel is a *negative* rank copula on snaps. Total receiving yards are
*narrower* than two independent teams, in all four games. There is no
shootout/blowout/pace state that lifts or suppresses both offences. Whether
that is right is an empirical question this artifact cannot answer and this
workstream did not fit — it is listed in (a) as a structural absence with its
code path, not proposed as a change.

## 9. Conversion, touchdowns, and rushing yards

Within-row receiving coherence is correct and violation-free (top four
receivers per game shown; `viol(receptions > targets) = 0` in every row of
every game):

| Game / player | tgts~rec | rec~yds | tgts~yds |
|---|--:|--:|--:|
| DAL_NYG DAL WR1 | +0.9399 | +0.8921 | +0.8408 |
| ATL_PIT ATL WR1 | +0.9161 | +0.9115 | +0.8342 |
| TB_CIN CIN WR1 | +0.9373 | +0.8615 | +0.7991 |
| NO_DET NO WR1 | +0.9209 | +0.8810 | +0.8213 |

Touchdowns against their own opportunity are real:
`r(carries, rushing_td)` +0.1834 … +0.4747; `r(receptions, receiving_td)`
+0.2334 … +0.3554; `r(receiving_yards, receiving_td)` +0.1682 … +0.3712,
over all 24 dual-layer backs.

**`r(rushing_td, receiving_td)` for the same player: -0.0434 … +0.0781, mean
+0.0093 over 24 backs — indistinguishable from zero at every n.** A back's
rushing and receiving touchdowns share a red-zone and game-script latent in
football; here they share nothing.

**Rushing yards for RB/WR/TE is UNAVAILABLE by declaration and is correctly
absent.** `board.json['unavailable_metrics']` carries
`{'metric': 'rushing/rushing_yards', 'code': 'RUSHING_CONVERSION_CONTROL_UNDEFINED',
'affects': ['RB','WR','TE'], 'status': 'UNAVAILABLE'}`, and
`layers.rushing_conversion` (`layers.py:597-637`) returns
`Outcome.deferred('RUSHING_CONVERSION_CONTROL_UNDEFINED', ...)` and names
`carries x yards_per_carry` as the prohibited implementation. The npz contains
no `rushing/rushing_yards` array. **The carries <-> rushing-yards correlation
asked for in this brief is not measurable and must not be estimated.** QB
rushing yards do exist (`qb/ryds`) and are covered in §7.

## 10. Appearance indicators

Using `indicator_j = 1{targets_j + receptions_j + receiving_yards_j > 0}` on
every receiver with an interior rate (0.02 < p < 0.98) — 11 to 13 such players
per team-side:

Pairwise correlations across all such pairs ran **-0.0888 … +0.0817**, with
almost every value inside the n=1000 noise band and every DAL_NYG value inside
the tighter n=8000 band (max abs 0.0393 there). **Teammate availability is
independent.**

**Code path.** `layers.py:221-223`:

```
rng = np.random.default_rng(parts)
draws = {pid: rng.binomial(1, float(np.clip(pv, 0.0, 1.0)), size=m)
         for pid, pv in o.value.items()}
```

One generator per game, one independent Bernoulli vector per player, marginal
probability from the frozen/R8 logistic. Nothing conditions one player's
availability on another's, on the opponent, or on any game state. Official
inactives are applied afterwards as a hard zero (`layers.py:224-240`), which is
correct and is where the `nan`-variance rows in §3 come from.

---

## 11. (a) INDEPENDENT draws that should plausibly share latent state

Listed with the code path that makes them independent. **Each is an
observation about the current joint structure, not a recommendation to add
correlation.** None should be changed without its own pre-registration; the
brief's instruction to prove the structure before adding anything is taken
literally here.

| # | Independent pair | Measured | Code path that makes it independent |
|---|---|---|---|
| a1 | A player's **rushing TD** and **receiving TD** | r = -0.043 … +0.078, mean +0.009 (24 backs) | `layers.py:518` and `layers.py:569` each draw `binomial` on a per-row generator; no shared red-zone or script state exists to condition on. No term links them. |
| a2 | **Teammate appearance indicators** | pairwise -0.089 … +0.082, at noise | `layers.py:221-223` — one `rng.binomial(1, p, size=m)` per player from a single game stream; no team-level availability latent, no opponent, no weather. |
| a3 | **Appearance and game environment** | appearance vectors carry no dependence on `team_off_snaps` by construction | same path; `appearance` is called at `football_engine.py:311-317` before and independently of `tv`. |
| a4 | **The two teams' scoring environments** (total receiving yards) | cross-team r = -0.084 … -0.112; SD of the game total is *below* independence in all four games | the only cross-team channel is A3G's rank copula on `team_off_snaps` (`team_volume_v1.py:540-553`, `coupling_scores` at 323-333). There is no positive pace/shootout latent anywhere in the engine. |
| a5 | **Opposing-team red-zone carries** | r = -0.005 … +0.044, at noise in all four games | `team_rz_carries` is outside the `off_snaps` coupling score (`team_volume_v1.py:329-333` couples on that residual only), so it inherits nothing. |
| a6 | **One team's QB room and the other's** | QB1 att vs opponent receiver targets -0.085 … +0.030 | `qb3_lib.allocate:165-167` seeds on `[seed, ordinal, team]` — the key contains the **team but not the game**, so the two rooms in a game are two unrelated streams. |
| a7 | **A back's carries and his own receiving efficiency** | r(carries, receiving_yards) tracks r(carries, targets) only; no separate channel | `layers.receiving_conversion:428` resamples per-catch yardage from a pool with a per-row generator that never sees the rushing layer. |
| a8 | **QB designed-run volume and the team carry pool** | -0.211 … -0.008 (§7) | `rushing_a1.allocate` partitions the budget; SC1 (`scramble_coherence.couple`) permutes only enough to remove infeasible draws, installing no association. PARTIAL — see §6 contamination. |

## 12. (b) SHARED draws that create ARTIFICIAL dependence

| # | Shared draw | Measured consequence | Code path |
|---|---|---|---|
| **b1** | **One `rem` scalar fans out to every non-primary QB in fixed proportion.** | backup~backup r = **+0.87 … +0.96**; every backup carries P(att>0) in 0.21–0.26; ATL shows four passers each over 0.54 with P(QB3 & QB4 both throw) = 0.520 | `nfl/research/qb3/qb3_lib.py:183-192`. `who` picks one primary; the remainder is split by fixed cell weights across **all** others at once, with no second selection. |
| **b2** | **Three non-QB layers share one generator key per player.** `_row_rng(seed, ordinal, pid)` is called with **identical arguments** by `receiving_conversion`, `td_layer` and `rushing_td`, all with `ordinal = season*100 + week`. | Today ~0: r(rushTD,recTD) = +0.009 mean. Verified numerically that the escape is accidental — same key, same `n`, different `p` gives **r = +0.554**; same key, different `n` gives r = -0.015. The layers are desynchronised only because `n` differs (targets vs receptions vs carries). | `layers.py:382-386` (`_row_rng`), consumed at `layers.py:428`, `layers.py:518`, `layers.py:569`; all three called from `football_engine.py:628-637` with the same `ordinal`. A change that equalised the counts would silently install a +0.55 correlation. |
| **b3** | **Stored `team_volume/team_targets` is a second, unused draw of a quantity C3 re-owns.** | r = +0.788 … +0.840 against the dealt targets, exact in **0.00%** of draws, per-draw gap up to 30.97 | budget replaced at `football_engine.py:407-455` (`d1_team_targets_unused: True` at line 485); the unused vector is nonetheless written by `run_forecast.py:1242-1255` from `fx['_team_volume']`. |
| **b4** | **Stored `team_volume/team_carries` is the pre-SC1 permutation, not the level the rushing layer partitioned.** | 1 draw in TB with stored carries **5.543 below** that draw's scrambles — impossible under SC1; 0–0.50% of draws per team-side violate `tc >= scr + RB carries` | engine uses `team_carries_override` (`run_forecast.py:766, 782`; `football_engine.py:256-260`); the artifact writes the raw `fx['_team_volume']` (`run_forecast.py:1242-1247`). |
| **b5** | **The manifest stamps `ACROSS_ROWS = INDEPENDENT_STREAMS_COLUMN_ALIGNED` on layers where cross-row dependence is real.** | The declaration would have a reader discard the -0.07 … -0.33 receiver competition of §3 and the -0.42 RB competition as generator artefacts | `draws_artifact.py:98` sets the constant once and `add_layer` applies it to every layer; the per-layer `rng_stream` string one field away says the opposite for `receiving` and `rushing`. |
| **b6** | **QB attempts and QB designed runs co-move through the shared room share.** | `r(att, rush_opp)` = +0.333 … +0.722 | allocation share multiplies both branches of the same QB row (`qb3_lib.allocate` share applied at the R2 level, `football_engine.apply_r2_level`), so playing-time drives both in the same direction with no competing snap constraint. |

Items b3, b4 and b5 are **artifact-layer** defects: the engine internally does
the right thing and the published draws do not carry it. b1 and b6 are
**model-structure**. b2 is a **latent hazard** with no measured effect today.

---

## 13. Finding table

| ID | Finding | Verdict |
|---|---|---|
| J-1 | C3 closes exactly at team level: `sum(QB pyds) == sum(receiver yards)` and `sum(QB cmp) == sum(receptions)` in 100.00% of draws, all 8 team-sides | **CONFIRMED** |
| J-2 | C3 target-count identity `sum att - sum targets = untargeted + other >= 0` holds in 100.00% of draws | **CONFIRMED** |
| J-3 | QB dropback identity `db == att + sacks + scr` exact in 100.00% of draws | **CONFIRMED** |
| J-4 | Teammate receivers compete for one pool | **CONFIRMED** at partial level (-0.07 … -0.33 on every pair of every team-side); **FALSIFIED as a raw read** — raw sign flips on 4 of 8 team-sides |
| J-5 | Teammate RBs compete for one carry pool | **CONFIRMED** (raw -0.03 … -0.45, negative on every non-degenerate pair) |
| J-6 | Rushing yards for RB/WR/TE are absent by declaration, not by omission | **CONFIRMED** — no array, explicit `UNAVAILABLE` record, explicit refusal in code |
| J-7 | A back's rushing TD and receiving TD are independent | **CONFIRMED** (r = +0.009 mean over 24 backs) |
| J-8 | Teammate appearance indicators are independent | **CONFIRMED** (max abs 0.0393 at n=8000) |
| J-9 | Backup QBs enter the game together rather than alternatively | **CONFIRMED** (+0.87 … +0.96), mechanism located at `qb3_lib.py:183-192` |
| J-10 | A3G couples the two teams, negatively, on snaps only | **CONFIRMED** (r ~= -0.466 in all four games; SD ratio 0.733–0.737, matching the engine's own claimed 12.271 -> 9.269) |
| J-11 | The coupling propagates to priced player metrics | **FALSIFIED** — cross-team receiving-yard r is -0.07 … -0.11 and the game total is *narrower* than independence |
| J-12 | Stored `team_volume/team_targets` is the quantity the game used | **FALSIFIED** — r = 0.79–0.84, exact in 0.00% of draws |
| J-13 | Stored `team_volume/team_carries` is the level the rushing layer partitioned | **FALSIFIED** — one draw violates SC1's construction guarantee by 5.543 carries |
| J-14 | `_row_rng` key reuse across three layers creates measurable dependence today | **FALSIFIED today, PARTIAL as a hazard** — measured ~0; same-key/same-`n` reproduces r = +0.554 |
| J-15 | QB rushing volume is coupled to the team rush pool | **PARTIAL** — measured -0.21 … -0.01 against the stored vector, which J-13 shows is the wrong vector |
| J-16 | The manifest's `across_rows` declaration describes all four layers | **FALSIFIED** — true for `qb`, false for `receiving` and `rushing` |
| J-17 | There is a game-level pace/shootout latent shared by both offences | **FALSIFIED** — none exists; the only cross-team term is a negative snap copula |
| J-18 | Whether the missing latents in list (a) would improve forecasts | **UNRESOLVED** — no outcome data was touched; this workstream measured structure only |
| J-19 | Whether SC1's permutation should install the historical `+0.1802` scramble/carry association | **UNRESOLVED** — cannot be separated from J-13 until the coupled vector is what is stored |

## 14. Evidence ceiling

What this evidence can and cannot carry:

1. **Four games, one configuration, one week.** All four runs are
   `V1_CANDIDATE_R8` with the same nine components applied and the same seed
   protocol (`per-row seed 20260908`). Nothing here separates a property of the
   configuration from a property of the engine, and nothing distinguishes
   week 1 from any other week. Eight team-sides is the real sample for a
   team-level claim; 24 dual-layer backs for a back-level claim.
2. **Draw count.** Three of four runs carry 1000 draws, where the 95% band on a
   null correlation is +/- 0.062. Every finding in §11 and §12 that rests on a
   near-zero measurement is supported at n=8000 on DAL_NYG as well, except a5
   and a6, which are only measured at n=1000 on three games and at n=8000 on
   one. Treat those two as the weakest rows.
3. **These are structural measurements, not forecasting claims.** Nothing was
   compared to a realised outcome. No statement here says the joint structure
   is right or wrong as a description of football; it says what the structure
   *is*. Whether independence at a1–a8 costs accuracy is untested and must stay
   untested until it is pre-registered against unseen games.
4. **No equivalence test was run.** Per the project's own rule, the words
   unbiased / stable / closed / correct are not used of any measurement here
   except where a quantity is an exact bit-level identity in 100% of draws
   (J-1, J-2, J-3), which is a construction rather than a statistical claim.
   "At noise" means "inside the stated Monte-Carlo band", not "equal to zero".
5. **The §6 / §7 contamination is not separable from this artifact.** The
   correct SC1-coupled carry vector is not stored anywhere. Quantifying how far
   QB rushing sits from the pool it actually occupied requires either storing
   that vector or re-running the game, neither of which is in this
   workstream's scope.
6. **The §4 backup-QB finding is the one that would most change prices**, and
   it is also the one with the least ambiguity: it is a deterministic fan-out
   readable in nine lines of source and reproduced in all eight quarterback
   rooms.
7. Draw artifacts were read by content digest
   (`c3347111c976adcce3bec731a5f546f7faaa583cdc9d2ef0e6a2254d86a16ea0` for
   DAL_NYG) and every row was addressed through `row_ids`. No positional
   indexing was used at any point, which is the defect class this brief names.

**CODE CHANGED: NO.**
