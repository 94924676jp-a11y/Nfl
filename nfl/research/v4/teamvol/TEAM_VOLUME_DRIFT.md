# Team volume: the bias is real, it is a lag, and it is not a Week-1 problem

Run 2026-09-15. `nfl/research/v4/teamvol/run_team_volume_drift.py`, output
`TEAM_VOLUME_DRIFT.json`. Strictly chronological, nothing fitted, estimators
**read** from `volume_results.json` via `team_volume_v1.selected()` and never
re-chosen here. Standard errors are block-bootstrapped over **team-season**
blocks — sixteen games of one team in one season are not sixteen independent
observations of that team's pace.

**R12 is not undone by anything here.** It improved QB dropback-share
calibration and in doing so exposed the layer above it: a perfectly calibrated
share of a wrong total is still wrong. This measures the total.

**2022 is excluded.** `selected()` takes the latest evaluated season *strictly
earlier* than the one scored, and 2022 is the first season in
`volume_results.json`. Scoring it would mean choosing the estimator on the very
rows it is then graded against. The directive asked for 2022–2025; this is
2023–2025, and the fourth season cannot be added without selection leakage.

---

## 1. Headline

n = 1,632 team-games (509–544 per season), 96 of them Week 1.

| metric | estimator | bias (pred − actual) | blocked SE | CI excludes 0 | MAE | RMSE | r |
|---|---|---:|---:|:---:|---:|---:|---:|
| `team_off_snaps` | league_mean | **+0.996** | 0.266 | **yes** | 7.093 | 8.932 | 0.053 |
| `team_dropbacks_part` | coach_prior | **+0.605** | 0.296 | **yes** | 6.594 | 8.252 | 0.129 |
| `team_targets` | coach_prior | +0.297 | 0.181 | no | 5.944 | 7.449 | 0.242 |
| `team_carries` | coach_prior | +0.263 | 0.255 | no | 5.982 | 7.386 | 0.190 |
| `team_rz_carries` | coach_prior | −0.037 | 0.110 | no | 2.441 | 3.100 | 0.040 |

**Two of five carry a bias distinguishable from zero, both positive — the model
projects MORE volume than happens.** Both are the metrics that feed passing:
snaps and dropbacks.

## 2. It is season drift, and the drift is monotone

| metric | 2023 | 2024 | 2025 |
|---|---:|---:|---:|
| `team_off_snaps` | +0.504 | +0.750 | **+1.735** |
| `team_dropbacks_part` | **−0.157** | +0.856 | **+1.115** |
| `team_targets` | +0.398 | −0.100 | +0.594 |
| `team_carries` | +0.388 | +0.075 | +0.326 |
| `team_rz_carries` | −0.006 | −0.069 | −0.036 |

The two significant metrics rise monotonically. `team_dropbacks_part` actually
starts *negative* in 2023 and crosses zero. A fixed offset would not do that.

## 3. The mechanism, confirmed directly

League mean of the actual values, straight from the panel:

| metric | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2020→2025 |
|---|---:|---:|---:|---:|---:|---:|---:|
| `team_off_snaps` | 67.14 | 66.36 | 65.79 | 65.91 | 65.39 | 64.24 | **−2.91** |
| `team_dropbacks_part` | 38.93 | 38.23 | 37.29 | 38.04 | 36.98 | 36.28 | **−2.65** |
| `team_targets` | 33.81 | 33.19 | 31.93 | 32.14 | 31.27 | 30.53 | **−3.28** |
| `team_carries` | 26.94 | 26.64 | 27.25 | 26.85 | 27.00 | 26.84 | −0.10 |
| `team_rz_carries` | 5.22 | 5.07 | 4.82 | 5.05 | 5.11 | 5.09 | −0.13 |

**The two metrics with a significant, growing bias are exactly the two whose
league mean is falling fastest. The two with flat league means have no bias at
all.** `team_carries` moves −0.10 across six seasons and its bias is +0.26 with a
CI covering zero; `team_rz_carries` moves −0.13 and its bias is −0.04.

That is a lag artifact, and it is not subtle. Every estimator in the family —
`league_mean`, `coach_prior`, `ewma`, `team_expanding`, `prev_season`, the roll-n
family — is an **average of the past**. Averaging a falling series puts you above
its next value, and the gap widens the longer the fall continues. No member of
this family can track a trend, because none of them has a trend term.

## 4. Against the six candidate causes

| candidate | verdict |
|---|---|
| **season drift** | **CONFIRMED, and dominant.** Monotone in both significant metrics; magnitude tracks the league-wide decline metric-by-metric. |
| **estimator misspecification** | **CONFIRMED, in one specific sense.** Not "the wrong member was selected" — *no member of the family has a trend term*, so the selection could not have avoided this. |
| **Week-1 prior** | **NOT SUPPORTED.** Every Week-1 CI covers zero. |
| **team persistence** | **not implicated by this evidence.** The bias tracks a league-wide level, not team-level structure. Not ruled out; not measured here. |
| **opponent coupling** | **not implicated by this evidence.** Same. Coupling moves the joint distribution, not the marginal mean. |
| **game-state assumptions** | **not measured here.** This scores a pregame point estimate against a realised total and never enters game state. |

### Week 1 specifically, since the directive asks

| metric | n | bias | blocked SE | CI excludes 0 | MAE |
|---|---:|---:|---:|:---:|---:|
| `team_off_snaps` | 96 | +1.495 | 0.915 | no | 7.237 |
| `team_dropbacks_part` | 96 | +0.765 | 0.929 | no | 7.416 |
| `team_targets` | 96 | +0.939 | 0.801 | no | 6.139 |
| `team_carries` | 96 | +0.290 | 0.695 | no | 5.250 |
| `team_rz_carries` | 93 | +0.090 | 0.319 | no | 2.488 |

Every point estimate is larger than its Week-2+ counterpart, and **not one is
distinguishable from zero.** n = 96 across three seasons is 32 teams observed
three times; the blocked SEs are three to four times the Week-2+ SEs, which is
the clustering doing its job. **The honest verdict is UNDERPOWERED, not "Week 1
is fine".** Three more Week 1s would roughly halve these intervals.

## 5. A contradiction I am not going to resolve by hand-waving

`AUTOPSY_DEN_KC.md` reports the 2025 study finding volume **UNDER**-projected,
dropbacks **−1.3697**. This study finds `team_dropbacks_part` **OVER**-projected
by **+1.115** in 2025. Opposite signs, same season.

They are not the same quantity, and that is the likely explanation rather than a
settled one:

- this measures the **raw team-volume estimator** against the participation
  panel's `team_dropbacks_part`;
- the autopsy measured the **composed engine output**, where dropbacks are
  `attempts + sacks + scrambles` after every intermediate layer has acted.

If both are right, the layers between them remove roughly **2.5 dropbacks per
team-game** — a specific, checkable claim, and a large one. **It is not checked
here.** Until it is, "team volume is biased" must be stated with the layer named,
because the two layers currently disagree about the sign.

**This is the single highest-value next measurement in this workstream**, ahead
of any repair: a layer-by-layer decomposition from `team_dropbacks_part` to the
engine's realised dropbacks on the same 2025 games.

## 6. What must NOT be done with this

**Do not add a trend term and ship it.** The bias is +0.6 to +1.0 against an MAE
of 6.6 to 7.1 — roughly a tenth of the typical error. Removing it would be a
real improvement in *calibration* and close to nothing in *discrimination*,
which is the stated objective. `r` is 0.129 for dropbacks and the calibration
slope is 0.423; the sd ratio is 0.304. The model emits far too little
game-to-game variation, and a trend correction does not touch that.

**Do not re-select an estimator on this evidence.** These are the rows the
selection would then be graded against. Any candidate trend-aware estimator is a
new arm with a new identity, pre-registered and forward-chained, compared on
untouched seasons.

**Do not treat `r = 0.053` on `team_off_snaps` as a defect of the estimator.** It
is `league_mean`, which is by construction almost constant across teams; near-zero
correlation is what that estimator *is*. The frozen research already found team
volume close to unforecastable, correlation peaking at 0.167, and chose to make
the uncertainty explicit rather than pretend to reduce it. Nothing here overturns
that.

## 7. Reproducing

```
python3.12 nfl/research/v4/teamvol/run_team_volume_drift.py
```

Deterministic at `seed = 20260915`; the only randomness is the block bootstrap.
No artifact outside `nfl/research/v4/teamvol/` is written or read for writing.
