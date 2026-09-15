# P5 — repair 6: the Q7 scramble construction

Repair of `nfl/research/q7/panel.py`. Research only. No market quantity is an
input, nothing is promoted, no wager is recommended, and DEN@KC is not used:
its realized outcome is not in this repository and no number below was chosen
by looking at it.

**Headline.** The defect is real, it is fixed, and the guard that would have
caught it is now in the build. Re-running Q7's own forward chain on the
corrected panel moves **588 of 1,003** published quantities, but **not one of
the 60 significance flags, and not one verdict**. Every published Q7 finding
survives. Two published *numbers* change materially and are named in §6.

---

## 1. The failing test, shown failing first

`nfl/tests/test_q7_panel_nondegeneracy.py`, written before the fix and run
against the shipped artifact:

```
modules 1  test functions 6  checks 11  FAILING CHECKS 8  RAISED 1

FAIL no qb-panel count column is degenerate over 4025 rows
       {'scr': {'total': 1, 'nonzero_rows': 1, 'n_rows': 4025}}
FAIL panel.assert_not_degenerate exists, so the BUILD fails rather than
     the artifact shipping                                     missing
FAIL the panel dropback total sits above nflverse by exactly the attempt
     rows nflverse does not flag, and by nothing else
       panel 116190 - nflverse 122044 = -5854; unexplained -5863
FAIL the panel and nflverse agree on which QB-games exist
       panel 4025  nflverse 4055  matched 4024
FAIL every matched QB-game carries the same dropback count
       2506 of 4024 disagree
FAIL the panel scramble total matches the play-by-play
       panel 1 vs pbp 5865
FAIL   and matches per QB-game, not only in total
       2507 of 4024 disagree
FAIL panel.py names the artifact it supersedes             missing
SUITE FAIL
```

Measured, not recalled. The 1-scramble figure and the 4.80 % dropback
shortfall reproduce exactly. Only **1,518 of 4,024** matched QB-games agreed
with nflverse on dropbacks; the prior study's 1,514 of 4,009 differs only by
frame scoping.

The module asserts three things the old one could not.

1. **Non-degeneracy.** Any built count column whose total is 0 or 1, or which
   is non-zero on at most one row, fails. Proved both ways: it fires on a
   seeded fixture, and it fires on the shipped v1 artifact —

   ```
   Q7_DEGENERATE_COUNT_COLUMN_IN_QB_PANEL_V1:
     {"scr": {"total": 1, "nonzero_rows": 1, "n_rows": 4025}}
   ```

2. **External reconciliation** against nflverse's own `qb_dropback`,
   re-derived inside the test from the six raw files rather than read from any
   artifact the builder wrote, so the builder cannot certify itself.

3. **Supersession** — the v1 artifact is still on disk and the corrected panel
   is a different file.

---

## 2. Why the old check could not see it

`panel.py` v1 composed `db = att + sacks + scr` and then asserted
`att + sacks + scr == db`. That identity is true of any three numbers
whatsoever, including a zero. It is not a weak test, it is not a test: it has
no power against any defect in any of its three inputs. And it displaced the
one check that would have worked — nflverse publishes `qb_dropback` and v1
never compared against it.

The composition stays, because consumers depend on the identity. It is no
longer the only check.

---

## 3. The fix

One structural change, in `reduce_season`:

```python
# v1 — every QB counter inside `if pid:` with pid = passer_player_id
if scr:
    c['scr'] += 1          # never reached: a scramble carries no passer id

# v2
if scr and not sack and ndb and rid:
    qb[(gid, off, rid)]['scr'] += 1
```

`rusher_player_id`, because nflverse charges a scramble to the man who ran.
Gated on `qb_dropback` exactly as the existing sack branch already is, and on
`not sack` because one row in six seasons carries both flags —
`2020_16_PHI_DAL`, a Jalen Hurts scramble reversed to a sack on replay. A play
cannot be both; the panel counts it as the sack. That single row is also the
*only* scramble v1 ever recorded, and v1 double-counted it, adding one to
`sacks` and one to `scr` for the same play.

**The frozen definitions are unchanged**: `attempt = pass_attempt & !sack &
!spike`, `completion` an attempt that completed, `dropback = attempts + sacks
+ scrambles`.

`READ` gains `rusher_player_id` and `rusher_player_name`. Both pass the
forbidden-substring market check.

---

## 4. Before and after, panel against `qb_dropback`

| | v1 (superseded) | v2 (corrected) | nflverse reference |
|---|--:|--:|--:|
| QB-games | 4,025 | 4,056 | 4,055 |
| scrambles | **1** | **5,864** | 5,864 |
| dropbacks | 116,190 | 122,053 | 122,044 |
| shortfall vs nflverse | **−5,854 (−4.80 %)** | +9 | — |
| player-games agreeing with nflverse | 1,518 / 4,024 | **4,047 / 4,056** | — |
| **unexplained player-games** | 2,506 | **0** | — |

Scrambles by season, corrected: 2020 863, 2021 910, 2022 905, 2023 1,035,
2024 1,062, 2025 1,089.

**The +9 residual is derived, not tolerated.** It is exactly the set of rows
that satisfy the frozen `attempt` definition while nflverse leaves
`qb_dropback` at 0, and every one is enumerated in
`nfl/research/q7/Q7_DROPBACK_RECONCILIATION.json`:

* **7 two-point conversion passes.** nflverse sets `pass_attempt` and
  `complete_pass` on a two-point try and leaves `qb_dropback` at 0. This
  divergence is **inherited, not introduced** — v1 counted them in `att` and
  `cmp` the same way. Recorded rather than repaired, because repairing it moves
  `att` and everything conditioned on it, which needs its own before-and-after.
* **1** replay-reversed sack inside a penalty `no_play` (`2025_02_SEA_PIT`).
* **1** blocked field goal carrying `pass_attempt = 1`, charged to the kicker
  (`2025_03_LA_PHI`) — the one panel QB-game nflverse does not recognise at all.

A further **388** `qb_scramble` rows are excluded because they are penalty
`no_play` rows: nflverse sets `qb_dropback = 0` and carries no rusher id on
them. That count is published too.

The build now refuses to write on any *unexplained* difference
(`Q7_DROPBACK_RECONCILIATION_FAILED`), and publishes the residual either way
rather than folding it into a tolerance.

### What actually changed in the panel

Only two columns. `att`, `cmp`, `sacks`, `pyds`, `ptd`, `int` are identical
row for row; `db` and `scr` change on 2,507 existing rows, and 31 rows are new.

All 31 new rows are scramble-only (`att = 0`, `scr = 1`). 25 belong to players
who already had a passing row; 6 do not, and **6 of the 31 are not
quarterbacks** (B.Aiyuk, E.St. Brown, G.Larvadain, J.Hightower, M.Palardy,
X.Hutchinson) — trick plays nflverse flags as `qb_scramble` with a non-QB
rusher. Stated rather than filtered: separating them needs a roster join the
panel does not carry, and 31 rows of 4,056 carrying 31 of 5,864 scrambles is
better reported than silently dropped.

**The receiver panel is byte-identical decompressed.** That is the control: the
repair touched the QB side and nothing else.

---

## 5. The generalised guard

`panel.assert_not_degenerate(rows, columns, where)` runs over every built
count column of both panels *before a byte is written* and raises
`Q7_DEGENERATE_COUNT_COLUMN_IN_<where>`. This repository has produced this
failure mode twice — `nfl/research/qb2/build_qb.py` names the first, this panel
was the second — and the third now fails the build.

Two smaller guards went in with it:

* `load()` raises a named `Q7_PANEL_NOT_BUILT` when a panel file is absent,
  and **deliberately does not fall back** to the superseded artifact. Ten
  modules outside Q7 call `load_recv`; a silent fallback is how a corrected
  build quietly stops being the thing that runs.
* The panels are written with `mtime = 0`, so the recorded sha256 is a content
  hash. Rebuilding reproduces `234c3453…` and `319c90f1…` exactly.

---

## 6. Q7's own conclusions, re-run on the corrected panel

`nfl/research/v4/p5/rerun_q7.py` calls `forward_chain.run` and
`analyse.summarise` — the same two functions `analyse.main` calls — and writes
beside the Q7 artifacts instead of over them. **Neither `forward_chain.py` nor
`analyse.py` was modified.** Two runs: one with the loader pointed at the
superseded panel, one at the corrected one.

### The harness check comes first

The re-run on the superseded panel reproduces the published
`Q7_FORWARD_CHAIN_RESULTS.json` on **1,003 of 1,003** compared quantities,
including `n_scored_rows = 93,961`. Without that, the after column would be
measuring the driver. It also rules out contamination from the seven other
modules other agents have modified in this working tree.

### What moved

| | count |
|---|--:|
| quantities compared | 1,003 |
| moved at all | 588 |
| moved by < 0.5 % relative | 407 |
| **significance flags that moved** | **0 of 60** |
| **verdicts that moved** | **0 of 4** |

### Conclusion by conclusion

**SURVIVES — Finding 1, the conditional mean is badly wrong at high volume.**
`pyds|cmp` BASELINE bias by attempt regime: `<20` +0.891 → +0.885, `20-29`
−3.923 → −3.932, `30-39` +4.496 → +4.486, `40+` **+19.802 → +19.801**.
Calibration slopes 1.029 / 0.990 / 0.755 / 0.728 → 1.029 / 0.989 / 0.754 /
0.728. The twenty-yard over-prediction and the 0.73 slope at `40+` are intact.

**SURVIVES — Finding 2, the width defect is real and monotone.** RMSE ÷
predictive SD, BASELINE: 1.4604 / 0.8792 / 0.7384 / 0.7103 → 1.4611 / 0.8795 /
0.7385 / 0.7103. The published 2.06-fold spread is 2.056 → 2.057; `Q7_WIDTH`
collapses it to 1.091 in both runs.

**SURVIVES — Finding 3, flattening it buys nothing on a proper score.**
`pyds|cmp` `Q7_BOTH` ΔCRPS by regime −0.182 / +1.208 / −0.507 / +0.004 % →
−0.167 / +1.201 / −0.505 / +0.004 %, with the same significance in every cell
(`20-29` significantly worse, `30-39` significantly better) and the overall
interval still spanning zero.

**SURVIVES, and is exactly unchanged — Finding 4, the inherited constant.**
All eight estimated-K cells are identical to five decimals (2022 3.35047 /
2.98253, 2023 5.41397 / 3.44783, 2024 5.22710 / 3.34283, 2025 4.98243 /
3.49947), as are the player counts. `estimate_k` requires a non-zero
denominator, so the scramble-only rows never enter it. `Q7_SHRINK` remains
significantly worse on `pyds|cmp` (+0.300 % → +0.295 %).

**SURVIVES — Finding 5, passing-TD efficiency is the worst-calibrated QB
quantity.** Slope 0.81173 → 0.81160, PIT χ² 267.0 → 266.9, 50 % coverage 0.794
unchanged. `Q7_SHRINK` −0.325 → −0.328 % and `Q7_BOTH` −0.358 → −0.359 %, both
still significant; `Q7_WIDTH` −0.163 → −0.166 %, not significant in either run.

**SURVIVES, bit for bit — Finding 6, most of RC2's receiving defect is not an
efficiency error.** Every receiving cell is byte-identical: `rec_yds|rec` bias
+0.60226, `rec_yds|targets` +0.77931, and the target-regime table
(+0.510 / 0.935 / 1.213 at 1-2 targets through +2.538 / 0.855 / 1.017 at 10+)
reproduces the published table exactly in both runs. The 72 % claim is
untouched.

**SURVIVES — the decision.** All three arms REJECT, with the same estimands
improved (3/4, 2/4, 3/4), the same regime counts (10/16, 7/16, 10/16) and the
same significantly-worse sets, including `pyds|cmp@20-29` and `pyds|att@20-29`.

### The two things that DO change, named

**1. The COMPOSED decomposition.** This is the one place a scramble-only row
changes an input: `_decompose` predicts attempts as the mean over the previous
eight games, and a scramble-only game contributes `att = 0`.

| quantity | published & v1 re-run | corrected panel |
|---|--:|--:|
| mean opportunity error | +0.81624 | **+0.73383** (−10.1 %) |
| mean combined error | +9.35592 | **+8.77230** (−6.2 %) |
| mean \|opportunity error\| | 8.72588 | 8.70074 |
| mean \|combined error\| | 71.00918 | 70.81599 |
| SAME_SIGN / OFFSETTING / ZERO | 1,241 / 1,351 / 61 | 1,243 / 1,351 / 59 |
| offsetting rate | 0.50923 | **0.50923** |

`Q7_DECISION.md`'s "+0.816 attempts" and "+9.356 yards" should now read +0.734
and +8.772. **The claim they support does not change**: the offsetting rate is
identical to five decimals, so "half of QB passing-yard forecasts have their
two components pulling opposite ways (50.9 %)" stands exactly. The ISOLATED
efficiency contribution moves +4.15018 → +4.13959.

**2. The sample-depth (cold-start) table**, because prior-game counts change
for 96 rows and 69 scored rows (2.6 % of 2,653).

`pyds|cmp` BASELINE:

| depth | n | bias | RMSE ÷ SD |
|---|--:|--:|--:|
| 0 | 101 → **98** | +7.210 → **+7.084** | 1.364 → 1.371 |
| 1-3 | 195 | +5.267 → **+5.961** (+13.2 %) | 0.847 → 0.828 |
| 4-8 | 254 → 255 | +3.294 → **+2.943** (−10.6 %) | 0.765 → 0.780 |
| 9-16 | 307 → 308 | +0.954 → **+0.847** (−11.2 %) | 0.762 → 0.763 |
| 17+ | 1,796 → 1,797 | +3.794 → +3.790 | 0.856 → 0.856 |

`Q7_DECISION.md`'s "0 prior games, bias +7.21, RMSE ÷ SD 1.364; at 9–16 games,
bias +0.95 and 0.762" should read +7.08 / 1.371 and +0.85 / 0.763. The claim —
that cold start carries both defects at once and both ease with depth — is
unchanged and, if anything, slightly cleaner.

### And one capability restored

The scramble / rush-opportunity layer that `AUTOPSY_DEN_KC.md` §5.3 recorded as
"not computable from that panel at all" is computable now. Nothing in this
report computes it; it is named as available.

---

## 7. Supersession, not overwrite

Nothing was deleted or edited. The v1 artifacts keep their names, bytes and
timestamps, and `nfl/research/q7/Q7_PANEL_SUPERSESSION.json` records the
defect, why the old check could not see it, the sha256 of each superseded file,
and the four published artifacts that rest on it. Deleting the broken panel
would delete the audit trail of every conclusion drawn from it.

| written | what |
|---|---|
| `nfl/research/q7/q7_qb_game_r2.csv.gz` | corrected QB panel, sha256 `234c3453…`, 4,056 rows |
| `nfl/research/q7/q7_recv_game_r2.csv.gz` | receiver panel, sha256 `319c90f1…`, 25,966 rows, decompressed-identical to v1 |
| `nfl/research/q7/Q7_RAW_PROVENANCE_R2.json` | spec `q7-panel-2`, six source hashes, artifact hashes, check list |
| `nfl/research/q7/Q7_DROPBACK_RECONCILIATION.json` | the external check, with all 9 residual rows named |
| `nfl/research/q7/Q7_PANEL_SUPERSESSION.json` | the supersession record |
| `nfl/research/v4/p5/Q7_RESULTS_{OLD,NEW}_PANEL.json` | the two re-runs |
| `nfl/research/v4/p5/Q7_SCORED_ROWS_{OLD,NEW}.csv.gz` | 93,961 scored rows each |
| `nfl/research/v4/p5/Q7_DIAGNOSTICS_{OLD,NEW}.csv` | 2,653 composed rows each |
| `nfl/research/v4/p5/P5_Q7_BEFORE_AFTER.json` | all 1,003 compared quantities |

**Q7's published artifacts were not touched.** `Q7_DECISION.md`,
`Q7_FORWARD_CHAIN_RESULTS.json`, `Q7_SCORED_ROWS.csv.gz` and
`Q7_DIAGNOSTICS.csv` are as they were. §6 says which of their numbers a
re-issue would change; re-issuing them is not this repair's call to make.

---

## 8. Blast radius — the brief's statement was incomplete

The brief said only Q7's own builder and one research study read the panel.
Verified, and it is not the whole list. Ten modules outside Q7 import
`nfl.research.q7.panel`:

`q8/repair.py`, `q8/audit.py`, `q9/hurdle.py`, `q9b/family.py`,
`q9b/identify.py`, `q9b/production_parity.py`, `prospective/q9shadow/shadow.py`,
`complete.py`, `live_features.py`, `seal.py`.

**Every one of them calls `load_recv()` and none touches the QB panel**, and
the receiver panel is decompressed-identical, so no number any of them produces
can move. The only other QB-panel reader is `nfl/research/v3/h1/h1_frame.py`,
which pins the superseded path literally and therefore still reads v1 — correct
for a historical study, and noted so nobody is surprised.

`nfl/production/` and `nfl/product/` read the panel nowhere. The sealed board's
`qb__scr` is non-degenerate. Production is unaffected; that part of the brief
holds.

**A pre-existing gap this touched but did not create.** `code_identity.py`'s
own `RESIDUAL_GAPS` names `nfl.research.q7.panel` as a module the sealing path
imports that is in neither B nor E of the candidate identity — so a change to
this file does not register in `candidate.identity`'s `module_source_sha16`,
which hashes seven named modules and not this one. That is the repository's
own recorded defect, with its own recorded remedy, and it is not mine to fix.

---

## 9. Tests run

| module | result |
|---|---|
| `test_q7_panel_nondegeneracy` (new) | **PASS** — 23 checks, 0 failing (was 8 failing, 1 raised) |
| `test_q7_efficiency_calibration` | **PASS** — 77 checks, 0 failing |
| `test_q8_target_opportunity` | **PASS** — 88 checks |
| `test_q9_prospective_shadow` | **PASS** — 254 checks |
| `test_q9_target_hurdle` | **PASS** — 109 checks |
| `test_q9b_model_family` | **PASS** — 78 checks |

The last four are the downstream `load_recv` consumers, run because the loader
default moved even though the bytes did not.

`test_q9_live_feature_builder` fails on four `no candidate drift` checks and one
stored-parity count (`record 482/0 vs run 481/0`). **Measured, not argued:**
recomputing `candidate.identity_sha256(candidate.identity(2024))` with the
loader pointed at the corrected panel and then at the superseded one returns
the same digest both times —

```
corrected  fe5dd3ac4e20982a9f73388e3e7c1506819bca4d376bc84360085098522472b5
superseded fe5dd3ac4e20982a9f73388e3e7c1506819bca4d376bc84360085098522472b5
```

so the panel repoint cannot be the cause. Consistent with the mechanism:
`identity` hashes seven named modules, none of them `panel.py`, and its fitted
blocks read only the decompressed-identical receiver panel. Seven production
modules are modified in this shared working tree by other agents. The failure
is real and is not mine to repair.

---

## 10. What I did not do

* Did not touch `Q7_DECISION.md` or any published Q7 result artifact.
* Did not modify `forward_chain.py` or `analyse.py`, or any file owned by
  another agent.
* Did not repair the two-point-conversion divergence in `att`, which is
  inherited from v1 and needs its own experiment.
* Did not filter the 31 non-QB scramble rows; reported them instead.
* Did not tune anything to DEN@KC, whose outcome is not in this repository.
* Did not commit or push.
