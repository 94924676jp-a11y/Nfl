# D3 — hierarchical reference bands

**Diagnostics only. Nothing here is wired into a projection path, and
`nfl/tests/test_refbands.py` reads the tree to prove it rather than asserting
it.** A band answers one question — *is this player's conditional projection
unusually low or high against his own, his team's, or his role's history* — and
it is never a floor, a cap, a correction, or a model input. A projection outside
a band may be the model working; the band knows nothing about tonight.

Branch `claude/nfl-greenfield-architecture-stsxmk`, HEAD `afefd39`,
`python3.12`. No commits, no staging. Nothing under `nfl/production/`,
`nfl/product/`, `nfl/research/baselines/` or any sealed artifact was touched.

## 1. What was built

| Path | What it is |
|---|---|
| `nfl/research/refbands/refbands.py` | the library: chronology guard, usage panel, role assignment, adequacy and shrinkage, clustered bootstrap |
| `nfl/research/refbands/build_refbands.py` | the driver; one command rebuilds every artifact |
| `nfl/research/refbands/USAGE_PANEL.csv.gz` | the consumed frame itself, 21,558 player-team-game rows, sha256 `d1dcad681bc82228…` |
| `nfl/research/refbands/REFERENCE_BANDS.jsonl.gz` | **46,089 band records**, every level, every metric, n on every one |
| `nfl/research/refbands/REFERENCE_BANDS.json` | headline bands, definitions, the two rules, clustered intervals |
| `nfl/research/refbands/RECENT_2025_SUPPLEMENT.json` | the lawful 2025 season, on the reduced metric set that is derivable for it |
| `nfl/research/refbands/TONIGHT_DEN_KC_PLACEMENT.json` | the six placements, each as a full ladder |
| `nfl/tests/test_refbands.py` | 14 functions, **123 checks, 0 failing, 0 blocked** |

```
python3.12 nfl/research/refbands/build_refbands.py     # ~55s
python3.12 nfl/tests/run_suite.py --only refbands      # SUITE PASS
```

The panel is committed on purpose. A band whose input is not on disk is a
number nobody can re-derive, which is the exact failure the sibling MLB
project's lost `v7/corpus/` records.

## 2. The frame, and chronology

Primary frame: `nfl/research/postgame/pbp_202[1-4].*.csv.gz`, `season_type ==
'REG'`. **2,174 team-games across 1,087 games**, 21,558 player-team-game rows.
Grouped by `(game_id, posteam)`, never by `game_id`.

`pbp_2026.*.csv.gz` **is on disk in this repository**, which is why the
chronology guard is load-bearing rather than decorative: a wildcard accessor
would not fail loudly, it would succeed quietly. There is therefore no wildcard
season accessor in the module. `pbp_path()` takes an integer and
`assert_lawful_season()` refuses anything at or after 2026 before touching the
filesystem. The suite seeds the violation by asking for 2026 by name and
requires the refusal.

**2025 is lawful and I used it, separately and labelled.** Every 2025 REG game
finished in January 2026, eight months before the `2026-09-14T17:40:19Z` cutoff.
It is outside the frame you stated, so it is never merged into a
play-by-play-derived band; it lives in `RECENT_2025_SUPPLEMENT.json`. Reject it
and nothing else in this return changes. See §9 for why it matters anyway.

## 3. Definitions — and the one that produces a disagreement

Counter names follow this repository's own `nfl/research/qb2/build_qb.py`, so
that a band and the board it reads are the same statistic.

| Name | Definition | QB1 mean / team-game |
|---|---|--:|
| `attempts` | `pass_attempt & !sack & !qb_spike` — **the board's `qb/att`** | 32.57 |
| `att_raw` | nflverse `pass_attempt`, **includes sacks and spikes** | 35.00 |
| `dropbacks` | `att_raw + scrambles - spikes` | 36.61 |
| `carries` | `rush_attempt & !qb_kneel` | — |
| `targets` | `pass_attempt` with a `receiver_player_id` | — |
| `route_proxy` | `ROUTE_PROXY_PASS_PARTICIPATION` — `panel_p3.pass_snaps`, presence on the field for a team dropback | — |

`att_raw - attempts = 2.4356` per QB1 team-game. The suite pins
`att_raw == attempts + sacks + spikes` in every one of the 21,558 rows, so a
future edit that swaps one for the other fails in the tests rather than in a
write-up.

**On routes.** There is no route count in this repository. `pass_snaps` from the
committed `panel_p3` leaf is derived from nflverse participation
(`offense_players` on dropback plays) and is an **upper bound** on routes run —
a receiver on the field may stay in to block, and for RB and TE that gap is
large and unmeasured here. It is published as a proxy with its bias named, never
as a route count, and a test enforces the wording. It is populated for 21,544 of
21,558 rows (99.94%).

## 4. Reproduction of the broad bands

All four reproduce from the committed panel. Of the 20 published quantile cells,
19 are identical under all five numpy interpolation methods and reproduce
exactly. One is not:

- `QB1 / passing yards / p10` is **136.3** under `method='linear'` (declared
  here), **136.0** under `lower` or `nearest`, 137.0 under `higher`. Your table
  says 136.0. The published bands did not declare an interpolation method and
  this is the only cell in which it can be seen. Not a defect in either
  direction; declared now so it cannot become one.

Means reproduce: 35.00 / 230.89 / 15.26 / 6.50. `RUSH2` n is **2,168**, not
2,174: six team-games had only one ball-carrier.

## 5. The hierarchy, and n at every level

| Level | Key shape | Records | Parent | Typical n |
|---|---|--:|---|---|
| `position` | `pos:QB`, `pos:WR`, `pos:ANYRUSHER` | 18 | — (no shrinkage) | 3.9k–21.5k |
| `role` | `role:QB1`, `role:RUSH2`, `role:WR3` | 54 | position | 39–2,174 |
| `role_season` | `role:QB1\|season:2024` | 216 | role | 542–544 |
| `role_team` | `role:QB1\|team:KC` | 1,710 | role | 66–68 |
| `role_starter` | `role:RB1\|starter:STARTER` | 196 | role | 4–2,113 |
| `player_role` | `player:00-0033873\|role:QB1` | 10,957 | role | 1–68 |
| `player_role_season` | `…\|season:2024` | 21,981 | player_role | 1–18 |
| `player_role_recent` | `…\|last8` | 10,957 | player_role | 1–8 |

Roles are **observed within-team-game usage ranks**, not depth-chart ranks:
`RB1` means the back who led his team in carries in that game. That is the right
frame for a band and the wrong frame for a forecast — tonight's lead back is not
yet observed — and the artifact says so.

`RUSH1`/`RUSH2` are position-agnostic, matching your "lead rusher". 62 of the
2,174 `RUSH1` holders are quarterbacks. `RB1` is the lead back among `RB`/`FB`
only; the two bands differ slightly and both are published.

Starter status is two different things and is labelled as such. For a
quarterback it is `FIRST_DROPBACK` vs `RELIEF`, taken from the passer or
scrambler on his team's first dropback — an actual fact about the game. For
everyone else it is a snap-share class from `offense_pct` (STARTER ≥ 0.55,
ROTATIONAL 0.25–0.55, RESERVE < 0.25, UNKNOWN when the share is missing), which
is a proxy for starting and not a start.

Selected metrics: QB attempts / att_raw / dropbacks / passing yards /
completions; RB and lead-rusher carries, targets, receptions, route proxy;
WR1–4 and TE1–3 targets, receptions, receiving yards, route proxy. 54 role-level
bands in all.

## 6. The shrinkage rule, and why it has no fitted parameter

Two declarations only — `alpha = 0.05` and the published quantile levels
(10, 25, 50, 75, 90). Everything numeric follows by formula.

**Adequacy gate.** For a reported level with tail mass `t = min(p, 1-p)`, the
probability that a sample of n contains an observation at or beyond that tail is
`1 - (1-t)^n`. Require it to reach `1 - alpha`:

```
n_min(t) = ceil( ln(alpha) / ln(1-t) )      ->  p10/p90: 29,  p25/p75: 11,  p50: 5
```

Below `n_min`, the empirical quantile at that level is not an estimate from data
in the region — it is an extrapolation from the nearest point that happens to
exist. Each level is labelled `OK` or `INSUFFICIENT_EVIDENCE` **per quantile**,
so a group can legitimately publish its own median and be refused its own p10.
`N_FLOOR = n_min(50) = 5`: below five observations a group gets no own band at
any level.

**Shrinkage.** `w = n / (n + n0)`, `band = w·own + (1-w)·parent`, with
**`n0 = n_min(10) = 29`**.

`n0` is not fitted and no outcome was consulted in choosing it. It is the sample
size at which the widest quantile pair this module publishes first becomes
estimable, so a group reaches equal weight with its parent exactly where its own
widest band stops being an extrapolation. Publish a different quantile pair and
`n0` moves by the same formula. The suite re-derives `n_min` from its own
probability statement rather than restating 29, 11 and 5, so a constant that
drifts away from its derivation fails there.

A convex blend of two monotone bands is monotone, so a shrunk band cannot cross
itself; tested at n ∈ {1, 3, 8, 29, 400}. The tests also pin the limits: w = ½
exactly at n = 29, parent-dominant at n = 1, own-dominant as n → ∞, and a no-op
when parent equals child.

`RECENT_WINDOW = 8` is declared, and chosen so the level is honest by
construction: 8 clears `N_FLOOR` but not `n_min(25) = 11`, so a recent-window
band can **never** publish its own p25/p75 or p10/p90 and is always shrunk at
w = 8/37 = 0.216 toward the player's full history. A recent window that could
publish a confident tail would be the defect, not the feature.

## 7. What is INSUFFICIENT_EVIDENCE

**26,685 of 46,089 records (57.9%).** That is the honest result at these levels,
not a fault to engineer away.

| Level | Records | INSUFFICIENT | Share |
|---|--:|--:|--:|
| `position` | 18 | 0 | 0.000 |
| `role` | 54 | 0 | 0.000 |
| `role_season` | 216 | 0 | 0.000 |
| `role_team` | 1,710 | 66 | 0.039 |
| `role_starter` | 196 | 30 | 0.153 |
| `player_role` | 10,957 | 5,634 | 0.514 |
| `player_role_recent` | 10,957 | 5,634 | 0.514 |
| `player_role_season` | 21,981 | 15,321 | 0.697 |

Every `INSUFFICIENT_EVIDENCE` record states *why* and carries the parent band it
falls back to; a test refuses a silent one. Separately, no group under
`n_min(10) = 29` is allowed to present an unqualified p10 or p90 even when it
does have an own band — 51% of `player_role` records are in that position.

A worked case: **Emmett Johnson (KC RB2) is a rookie and has zero lawful
player-games.** All six of his player-level rungs return
`INSUFFICIENT_EVIDENCE` with n = 0. He is not given a band anyway; he is handed
a named coarser one, `role:RB2|team:KC` (n = 66).

## 8. Uncertainty is clustered

Games are not independent observations. Every interval here resamples **games**,
not rows: the two team-games inside one game share pace, score state and
weather. At role level that is 1,087 clusters behind 2,174 rows, and the test
requires the clustered interval to be no narrower than a row-level bootstrap.
Every published band carries `n` and `n_clusters`.

Selected role-level bands (own quantiles; 95% clustered interval on the median):

| Band | n | p10 | p25 | p50 | p75 | p90 | mean | 95% CI on p50 |
|---|--:|--:|--:|--:|--:|--:|--:|---|
| QB1 attempts | 2,174 | 22 | 27 | 32 | 38 | 43 | 32.57 | [32.0, 33.0] |
| QB1 att_raw | 2,174 | 24 | 29 | 35 | 41 | 46 | 35.00 | [34.0, 35.0] |
| QB1 dropbacks | 2,174 | 25 | 30 | 36 | 42 | 48 | 36.61 | [36.0, 37.0] |
| QB1 passing yards | 2,174 | 136.3 | 179 | 228 | 279 | 328 | 230.89 | [224.0, 232.0] |
| RUSH1 carries | 2,174 | 9 | 11 | 15 | 19 | 23 | 15.26 | [14.0, 15.0] |
| RUSH2 carries | 2,168 | 3 | 4 | 6 | 9 | 11 | 6.50 | [6.0, 6.0] |
| RB1 carries | 2,174 | 9 | 11 | 14 | 19 | 23 | 15.19 | [14.0, 15.0] |
| RB1 targets | 2,174 | 0 | 1 | 3 | 5 | 6 | 3.31 | [3.0, 3.0] |
| RB2 carries | 2,085 | 2 | 3 | 5 | 8 | 11 | 5.73 | [5.0, 5.0] |
| WR1 targets | 2,174 | 5 | 7 | 8 | 11 | 13 | 8.87 | [8.0, 9.0] |
| WR1 route proxy | 2,174 | 22 | 27 | 33 | 39 | 44 | 32.84 | [32.0, 33.0] |
| WR2 targets | 2,173 | 3 | 4 | 5 | 7 | 9 | 5.61 | [5.0, 5.0] |
| WR3 targets | 2,115 | 1 | 2 | 3 | 4 | 6 | 3.28 | [3.0, 3.0] |
| TE1 targets | 2,163 | 2 | 3 | 5 | 7 | 9 | 5.21 | [5.0, 5.0] |
| TE1 route proxy | 2,163 | 14 | 21 | 28 | 35 | 41 | 27.79 | [27.0, 28.0] |

Starter status separates real mass. QB1 `FIRST_DROPBACK` attempts (n = 2,113)
runs 22 / 32 / 43 against `RELIEF` (n = 61) at 15 / 24 / 34. RB1 carries by snap
class: STARTER (n = 1,469) 10 / 16 / 24, ROTATIONAL (n = 684) 8 / 12 / 18,
RESERVE (n = 21, shrunk) 5 / 9 / 11.

System matters too. QB1 attempts per team-game, 2021–2024, n = 67–68 each: TB
38.2, KC 37.3, LAC 36.7 at the top; TEN 28.7, CHI 28.7, SF 29.0 at the bottom —
a 9.5-attempt spread between systems against a league p25–p75 of 27–38. Lead
rusher carries: IND 19.0 and TEN 18.9 at the top, NYJ 12.7, BUF 13.0 and **DEN
13.1** at the bottom.

## 9. Tonight, against the finest lawful band with support

`nfl/research/live/2026_01_DEN_KC/PRELIMINARY_PROVISIONAL_V1_CANDIDATE_R8/f91342d6787a66a1`.
Full ladders are in `TONIGHT_DEN_KC_PLACEMENT.json`; the percentile shown is the
projection's position **within that rung's own sample**.

### Patrick Mahomes — 34.36 attempts

| Rung | n | p10/p90 admissible | own p10 / p50 / p90 | percentile |
|---|--:|---|---|--:|
| `player\|QB1\|last8` | 8 | no | 35.8 / 38.5 / 42.9 | **12.5** |
| `player\|QB1\|2024` | 16 | no | 27.5 / 37.5 / 43.0 | 31.2 |
| **`player\|QB1` (finest with p10/p90 support)** | **66** | **yes** | **28.5 / 37.0 / 44.5** | **31.8** |
| `role:QB1\|team:KC` | 68 | yes | 28.0 / 37.0 / 44.3 | 33.8 |
| `role:QB1` (broad) | 2,174 | yes | 22.0 / 32.0 / 43.0 | 60.9 |

Inside p10–p90 at every rung from `player|QB1` outward. **Below his own last-8
p10.** The finest supported reading is the 32nd percentile of his own 66 starts —
not the middle of the distribution the broad band suggests.

### Patrick Mahomes — 244.92 passing yards

Finest supported: `player|QB1`, n = 66, own 190.5 / 269.5 / 356.0 →
**30.3rd percentile**. KC system (n = 68): 32.4. Broad: 59.3. Inside p10–p90
throughout, including the last-8 rung.

### Bo Nix — 32.08 attempts

His own history is **17 games** — one season. That clears `n_min(25) = 11` but
not `n_min(10) = 29`, so his own p10/p90 are refused and the rung is shrunk at
w = 0.370.

| Rung | n | own p10 / p50 / p90 | percentile |
|---|--:|---|--:|
| `player\|QB1\|last8` | 8 | 29.7 / 33.0 / 40.6 | 37.5 |
| `player\|QB1` (p25–p75 only) | 17 | 26.0 / 33.0 / 40.8 | 35.3 |
| **`role:QB1\|team:DEN` (finest with p10/p90 support)** | **68** | **22.0 / 32.0 / 40.3** | **52.9** |
| `role:QB1` (broad) | 2,174 | 22.0 / 32.0 / 43.0 | 51.6 |

### Bo Nix — 212.56 passing yards

`player|QB1` (n = 17, p25–p75 only): own 134.8 / 219.0 / 299.2 → 29.4th
percentile. DEN system (n = 68): 36.8. Broad: 40.9. Below his own last-8 median
(268.0) at the 12.5th percentile of those eight games, but inside p10–p90.

### Kenneth Walker III (KC RB1) — 12.85 carries

| Rung | n | own p10 / p50 / p90 | percentile |
|---|--:|---|--:|
| `player\|RB1\|last8` | 8 | 8.7 / 14.0 / 18.7 | 25.0 |
| **`player\|RB1` (finest with p10/p90 support)** | **34** | **9.0 / 16.5 / 25.7** | **29.4** |
| `role:RB1\|team:KC` | 68 | 8.0 / 14.0 / 20.3 | 38.2 |
| `role:RUSH1` (broad) | 2,174 | 9.0 / 15.0 / 23.0 | 34.3 |

**Read the team rung with care.** `role:RB1|team:KC` describes Kansas City's
lead-back workload 2021–2024, held by different players. It is a band about the
system, and it is being applied to a back who arrived from Seattle. The
player-level and team-level rungs are answering different questions and neither
substitutes for the other.

### Emmett Johnson (KC RB2) — 6.36 carries

No lawful player-games. Finest supported rung is `role:RB2|team:KC`,
n = 66, own 1.5 / 5.0 / 9.5 → **72.7th percentile**. `role:RUSH2|team:KC`
(n = 68, 3.0 / 5.0 / 10.0) → 70.6. Broad `RUSH2`: 54.6.

## 10. Where I disagree with the broad bands

**All six of your percentiles reproduce to the decimal.** 59.3, 40.9, 34.3 and
54.6 reproduce under my definitions directly. 49.1 and 39.8 reproduce **only**
against `att_raw`.

**One definitional disagreement, and it is material.**

> The QB1 band labelled *"pass attempts"* is `att_raw` — nflverse
> `pass_attempt`, which **includes sacks and spikes**. That is not the quantity
> the sealed board projects. The board's `qb/att` is
> `pass_attempt & !sack & !qb_spike`, which is this repository's own
> `build_qb.py` definition, and the board lists sacks taken as a separate line.

The gap is 2.4356 per QB1 team-game — most of an interquartile step — and it
moves both quarterbacks' readings in the same direction:

| Projection | vs `attempts` (board's metric) | vs `att_raw` (your band) | vs `dropbacks` |
|---|--:|--:|--:|
| Mahomes 34.36 | **60.9** | 49.1 | 41.7 |
| Nix 32.08 | **51.6** | 39.8 | 33.0 |

Band shift: `attempts` is 22 / 27 / 32 / 38 / 43 against `att_raw`'s
24 / 29 / 35 / 41 / 46. The passing-yards, lead-rusher and second-rusher bands
are unaffected. The statement "all inside p10–p90" survives under every
definition; the percentiles do not.

**Two placement disagreements from the finer bands.**

1. **Mahomes is not mid-distribution, he is in the lower third of his own
   history** — 31.8th percentile on attempts and 30.3rd on passing yards against
   his own 66 starts, and below his own last-8 attempts p10. The broad band's
   49.1 and 59.3 read as ordinary because the broad band pools him with every
   starting quarterback in the league, including systems that throw 9 fewer
   times a game than Kansas City. This is a *diagnostic observation and not a
   reason to move anything*; the board itself gives Mahomes only 29.0% of KC's
   dropbacks under an unresolved QB-room question, and a conditional projection
   in the lower third of a player's history is exactly what a model that thinks
   something is different should produce.

2. **The KC RB2 projection is high against the KC system, not middling.** 72.7th
   percentile of Kansas City's own second-back carries (median 5.0, p75 7.0)
   against 54.6 on the broad band. KC's backfield ran a low-volume committee over
   the frame; the broad band averages that away.

Nix's readings move less: 52.9 (DEN system) and 51.6 (broad) on attempts, 36.8
and 40.9 on yards. Walker's move from 34.3 (broad) to 29.4 (his own history) to
38.2 (KC's system) — a 9-point spread across three defensible bands, which is
itself the point of building the hierarchy.

## 11. Two data findings other agents should have

**`panel_p3.dropbacks_as_passer` is not a dropback column.** It equals
`pass_att_as_passer` in **all 57,670 rows** of the leaf. Scrambles are charged to
the rusher, so no scramble ever reaches the passer's column, and sacks are
already inside `pass_attempt`. Anyone building a "dropbacks" feature from that
leaf is building `att_raw` under a second name. Recorded in
`RECENT_2025_SUPPLEMENT.json`.

**The play-by-play corpus has no 2025.** `nfl/research/postgame/` holds 2021,
2022, 2023, 2024 and 2026 — there is no `pbp_2025` blob. 2025 is entirely lawful
for this board, and it is the season closest to tonight. Without it, passing
yards, official attempts, receptions and receiving yards are not derivable for
2025 in this repository at all, and every "recent window" in the primary
hierarchy is stale by a full season. This is the single highest-value missing
lawful input for this workstream. It is not blocked for me to *ask*; it is
outside this checkout, so it is the other agent's to fetch.

What the 2025 leaf does support, and why it changes readings:

| | 2021–2024 (pbp) | 2025 (panel_p3) |
|---|---|---|
| Mahomes att_raw | n=66, p50 39.0, mean 39.52 | n=14, p50 37.0, mean 38.14 |
| Nix att_raw | n=17, p50 35.0, mean 34.82 | n=17, p50 **39.0**, mean **37.24** |
| Walker carries (RB1 role) | n=34, p50 16.5, mean 16.53 | n=17, p50 **13.0**, mean **13.00** |

Nix's volume rose in 2025 and Walker's fell. **Walker's 12.85 sits essentially
at his 2025 median (13.0), while the 2021–2024 frame puts it at the 29th
percentile of his history.** The stale window is not a rounding issue. Mahomes
appears in 14 of Kansas City's 17 games in 2025 (weeks 1–9 and 11–15; KC's bye
was week 10, so the three absences are weeks 16–18). Nix played all 17 for
Denver and Walker all 17 for **Seattle** — his 2025 band is a Seattle band, not
a Kansas City one.

**Cross-source reconciliation.** The pbp panel and `panel_p3` were built
independently and are compared on their overlap: 21,544 rows matched, 14 pbp
rows absent from `panel_p3`. Mean pbp-minus-p3 differences: `att_raw` +0.0298
(543 rows differ, max 4), `carries` −0.0699 (1,100 differ, max 6), `targets`
+0.0164 (347 differ, max 2). Small, not zero, and stored rather than assumed
away. I did not chase the residual; the likely cause is lateral and aborted-play
attribution, and it is below the resolution of any band published here.

## 12. What this does not establish

- These are **marginal, unconditional historical summaries**. They say nothing
  about tonight's opponent, script, weather or health, and a projection that
  differs from them is not thereby wrong.
- Roles are assigned from **realised** usage, so a band describes the
  distribution of a role, not a prediction of who will hold it.
- The route metric is **participation, not routes**, and its bias is largest for
  the positions that block.
- Nothing is tested for calibration or discrimination here; a band is not a
  forecast and cannot be scored as one.
- I did not compute a band for receiving yards at player level for tonight
  because no receiving projection was handed to this workstream. The bands exist
  in `REFERENCE_BANDS.jsonl.gz` if they are wanted.

## 13. Open for the coordinator

1. **Rename or re-cut the broad QB1 attempts band.** It is `att_raw`, and either
   the label or the definition should move. My recommendation is the definition,
   so that the band and the board's `qb/att` are the same statistic.
2. **Declare a quantile interpolation method** in the broad bands. One cell of
   twenty is currently ambiguous.
3. **`pbp_2025` from the other agent.** Everything in §11 improves immediately.
4. Do you want the 2025 supplement folded into the primary hierarchy once a
   `pbp_2025` blob exists, or kept as a separate frame? I have kept it separate
   and merged nothing.
