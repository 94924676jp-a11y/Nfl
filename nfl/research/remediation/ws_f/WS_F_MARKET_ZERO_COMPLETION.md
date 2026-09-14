# WS-F, second repair — the market grader chose its comparisons with the outcome

**SEPARATE COMMIT, SEPARATE REPORT, ON INSTRUCTION.** This is not folded into
the retrospective diff. Companion to
`nfl/research/remediation/ws_f/WS_F_ZERO_COMPLETION.md`; either repair can be
reverted without the other.

**CODE CHANGED: YES, EVALUATION-ONLY.** No projection, no draw, no
probability, no price and no board moves. The repair governs **which
comparisons are graded**, nothing about **what is compared**. A price remains
an external disagreement diagnostic on a sealed pregame forecast — never a
target, a label, a prior, or a calibration anchor. Nothing here optimises
toward a line and no wager is recommended.

Files changed by this repair, and only these:

| path | what |
|---|---|
| `nfl/research/market_outcome_audit.py` | the repair, spec `1.0.0` → `2.0.0` |
| `nfl/tests/test_market_outcome_zero_completion.py` | NEW — 11 functions, 71 checks |
| `nfl/research/model_health/SUNDAY_MARKET_OUTCOME_1PM_ZERO_COMPLETED.{csv,summary.json}` | NEW — regenerated |
| `nfl/research/model_health/SUNDAY_MARKET_OUTCOME_1PM_LEGACY_SELECTION_REPRO.{csv,summary.json}` | NEW — the leak reproduced |

Also touched, and belonging to the coordinator's two rulings rather than to
this repair: `nfl/product/model_health.py` (spec → `1.1.0`),
`nfl/research/model_health/build_health.py` (market basis must now be
*declared*, not assumed), `nfl/research/model_health/CORRECTIONS.json`,
`nfl/research/model_health/MODEL_HEALTH_2026-09-14_ZERO_COMPLETED.json`.

---

## 1. DEFECT

`nfl/research/market_outcome_audit.py:184-186`, spec `market-outcome-audit/1.0.0`:

```
src = (qa if fam == 'qb' else rr).get(p['gsis_id'])
if src is None or src.get(field) is None:
    rows.append(_refusal(slate, gid, k, q, 'NO_REALISED_VALUE', 'not imputed'))
    continue
```

The same defect as the retrospective, in the same shape, with the same
justification string. `actuals` emits a record only for a player who recorded
at least one target, carry or dropback, so in a **completed** game an absent
record is the observed value **zero**, and the quote is gradable.

## 2. THE DIRECTION, WHICH IS THE WHOLE POINT ON THIS PATH

**A priced player who recorded nothing settles UNDER at every line the book
offered on him.** And the model's selected side on such a player is very often
**OVER**, because the forecast that put volume on him is precisely what
generated the disagreement the row exists to record.

So the deleted set is **enriched in comparisons the model loses**. Every
statistic the audit publishes — the hit rate, the mean probability gap, the
gap-bucket table, the over/under split — computed on the survivors reads
**better than the same statistic over every comparison the model actually
made**. The failure is silent, one-directional, and lands on the one number
anybody would quote.

Stated plainly, as instructed: **a market-disagreement statistic computed on
surviving rows only will systematically flatter us.**

The test module asserts the mechanism rather than asserting it in prose: an
OVER selection on a zero outcome is a LOSS at every line, an UNDER selection is
a WIN, and deleting the zero-outcome rows from a mixed set raises the hit rate.

## 3. MEASURED EXPOSURE: ZERO, AND I AM NOT INFLATING IT

Reproduced against the frozen 1 PM snapshot (`hardrock_1pm_props_2026-09-13_FROZEN.csv`,
sha16 `98dbe0713d56d27d`, 343 quotes) and stored blob
`pbp_2026.1415dd98ba7f701a.csv.gz`, 8 games:

```
quotes reaching the realised-value check : 161
quotes carrying a record                 : 161
quotes that would have been deleted      :   0
```

**The refusal never fired.** The published refusal ledger confirms it
independently — the 182 refusals are 142 `QUOTE_PLAYER_NOT_ON_BOARD`, 25
`ESTIMAND_NOT_SCOREABLE`, 10 `MARKET_NOT_MAPPED`, 5
`MARKET_QUOTE_TEAM_UNRESOLVED`, and **no `NO_REALISED_VALUE` at all**.

Why it did not bite here: the leak requires a player who recorded *nothing* —
no target, no carry, no dropback. A receiver targeted once who caught nothing
*has* a record, so his zero receptions are read correctly as `OBSERVED`. Every
one of the 161 priced, board-listed, draw-identified players touched the ball.

**So the defect was real in code and latent in effect, and the published market
figures are not contaminated by it.** This also corrects one implication of my
own first report, and I withdraw it: I wrote that the carried market columns
"are themselves outcome-selected", which overstates the case. The grader
*could* have deleted such rows and did not declare that it had not; on this
slate it deleted none. The provenance criticism stands; the contamination claim
does not.

It is repaired anyway. "It has not bitten yet" is not a property of the code.
The first priced player who is declared inactive, ejected, or simply never
touches the ball triggers it silently and in one direction — and week 1 is the
slate where that is *least* likely, because the book prices players it expects
to play and the boards had already refused 142 quotes for players not on them.

## 4. REPAIR

Same standard as the first repair, point for point.

1. **Reproduce before fixing.** `--legacy-outcome-selection` reproduces the old
   rule and stamps the run `SELECTED_ON_REALISED_VALUE` with a leak warning
   naming the direction of the bias. It reproduces the published
   `SUNDAY_MARKET_OUTCOME_AUDIT.json` exactly (§5).
2. **Derive, do not globally convert.** The four-class classification is
   **imported** from `same_day_retrospective.ABSENCE_SEMANTICS`, not copied —
   two scorers disagreeing about what an absent record means is how this defect
   reached two files. A test asserts every exact estimand resolves to the same
   class in both modules.
3. **Require proven finality.** The branch ladder is extracted into
   `resolve_realised(src, field, metric, final, legacy=…)`, which raises
   `ZERO_COMPLETION_WITHOUT_PROVEN_FINALITY` rather than inheriting completion
   from the caller's control flow. The game-level finality gate above it was
   already correct; the licence is now local to the line that uses it.
4. **Name every refusal.** `REALISED_VALUE_UNOBSERVED_NOT_ZERO`,
   `ESTIMAND_NOT_APPLICABLE_TO_THIS_ROW`, `ABSENCE_SEMANTICS_UNRESOLVED`,
   `ESTIMAND_FIELD_NOT_IN_ACTUALS`, and `NO_REALISED_VALUE` retained as the
   legacy-only code. The `balanced` invariant (clean + contaminated + refused
   == quotes in snapshot) is preserved and still checked.
5. **A missing field is still a mapping bug** — refused, never zeroed.
6. **Cluster the SEs, and refuse the naive one.** §6.
7. **Version the spec:** `market-outcome-audit/1.0.0` → **`2.0.0`**. Breaking,
   even though the numbers are unchanged on this slate, because the rule
   deciding which comparisons exist is different.
8. **`--outcome-blob`**, so the reproduction does not need the network and
   cannot silently grade against restated upstream bytes.
9. **Named errors on empty or partial output**:
   `EMPTY_MARKET_AUDIT_RESULT`, `MARKET_AUDIT_SCHEMA_INCOMPLETE`.
10. **Every graded row declares its basis** — `actual_basis` and
    `absence_class` are published columns; the summary carries
    `outcome_selection_basis` and `n_zero_by_completion`.

## 5. POST-REPAIR RESULT: IDENTICAL, AND THAT IS THE FINDING

| | legacy (leak) | repaired |
|---|---|---|
| quotes in snapshot | 343 | 343 |
| clean / contaminated / refused | 81 / 80 / 182 | 81 / 80 / 182 |
| balanced | true | true |
| rows zero-completed | 0 | **0** |
| clean W–L–P | 36–45–0 | 36–45–0 |
| clean hit rate | 0.4444 | 0.4444 |

All 343 CSV rows are byte-identical between the two runs; the summaries are
identical apart from the selection stamp. Every cell of the published
`SUNDAY_MARKET_OUTCOME_AUDIT.json` 1 PM clean result reproduces exactly —
n 81, 12 over / 69 under, pct_under 0.8519, 36–45–0, hit 0.4444, mean model
probability 0.6481, mean no-vig 0.5065, mean gap 14.1597 — as does every
`by_market` cell (Receiving Yards 36 / 0.4722, Receptions 37 / 0.4324, Rushing
Attempts 8 / 0.375).

**The 4:25 slate is unchanged and still DEFERRED**, not refused: the
authoritative source carries 10 games and none of ARI_LAC, GB_MIN, MIA_LV,
WAS_PHI.

## 6. CLUSTERING — and the number a quote count was hiding

`perf()` now emits cluster-robust SEs of the hit rate over **decided**
comparisons only (a push is not a trial), reusing `SDR._cluster_se` so both
modules share one convention. **No naive binomial SE is emitted as a number.**

| stratum | decided | hit rate | naive (refused) | game-clustered | clusters | player-game-clustered | clusters |
|---|---:|---:|---:|---:|---:|---:|---:|
| clean | 81 | 0.4444 | 0.0552 | **0.0724** | **4** | 0.0631 | 37 |
| contaminated QB3 | 80 | 0.5375 | 0.0557 | **0.0905** | **8** | 0.0724 | 16 |
| Receiving Yards | 36 | 0.4722 | 0.0832 | 0.1484 | 4 | — degenerate | 36 |
| Receptions | 37 | 0.4324 | 0.0814 | 0.0702 | 4 | — degenerate | 37 |
| Rushing Attempts | 8 | 0.3750 | 0.1712 | 0.1786 | 4 | — degenerate | 8 |

Three things this exposes that "n = 81" concealed:

* **The clean stratum has four game clusters, not eight.** The graded non-QB
  markets exist in only four of the eight audited games. A hit rate quoted on
  81 quotes is a statistic on four afternoons.
* **Clustering widens the clean interval by 1.31×** and the contaminated one by
  1.62×. It does not move in one direction — `Receptions` *narrows* to 0.86×,
  because its errors are more consistent across games than across rows, the
  same effect WS17 documented for carries.
* **Player-game clustering genuinely binds here**, unlike in the per-metric
  retrospective tables: Receptions and Receiving Yards on the same player-game
  are two views of one afternoon, so the clean stratum has 37 player-game
  clusters for 81 quotes. Where it degenerates (one decided comparison per
  player-game) the row says so and says the figure *is* the naive SE.

No equivalence margin was predeclared and no two-one-sided test was run. On
four clusters no interval here is trustworthy at its nominal level, and none of
these hit rates is evidence about anything.

## 7. TEST

`nfl/tests/test_market_outcome_zero_completion.py` — 11 functions, **71 checks,
0 failing, 0 raised**, `--only`. Nothing reads a price, a snapshot or a live
artifact; `resolve_realised` is exercised directly on synthetic records.

Because the leak never fired on live data, **these tests are the only thing
between the repair and a silent regression** — no artifact would notice.

Covers: absent player grades at 0 on all eleven exact estimands; a record that
exists is read (including a genuine observed 0, which must *not* be labelled
`ZERO_BY_COMPLETION`); the direction of the bias, asserted as a mechanism;
`MISSING_IF_ABSENT` / `NOT_APPLICABLE` / `UNRESOLVED` refused by name;
unclassified estimand refused; missing field on an existing record refused;
finality required in three forms; the legacy rule still reproducible and
self-stamping; **both scorers resolve every exact estimand to the same class**;
clustering emitted, naive refused, pushes excluded; and the published schema.

I also ran the two adjacent market suites I do not own, read-only, to confirm I
broke nothing: `test_market_quote_accounting` (34 checks) and
`test_qb_pyds_market_eligibility` (41 checks) both PASS, as does
`test_retrospective_zero_completion` (62 checks).

## 8. BLAST RADIUS AND IDENTITY

* **Numerically none on existing artifacts.** The regenerated market audit
  equals the published one cell for cell.
* `market-outcome-audit/1.0.0` → **`2.0.0`**; a hit rate from one is not
  comparable with one from the other in general.
* `nfl/research/SUNDAY_MARKET_OUTCOME_AUDIT.json` is **not modified** (sha16
  `69cb6c45c8ce5c33`, WS-F does not own `nfl/research/`); corrected and
  leak-reproduction artifacts sit beside it under `model_health/` and are
  linked from `CORRECTIONS.json`.
* **Consequence for the health artifact.** Because the repaired grader declares
  a complete selection *and* reproduces the carried columns exactly,
  `build_health.py` can now be told so — with a **written justification it
  refuses to run without** (`MODEL_HEALTH_UNJUSTIFIED_MARKET_BASIS`) — and
  `MARKET_STATS_OUTCOME_SELECTED` clears on all nine metrics carrying market
  columns. **Ranking eligibility is unchanged at 1 of 11**: no metric was
  promoted by the clearing. An undeclared basis still blocks ranking, so the
  default remains the safe one.
* No freeze, fingerprint, parameter hash or production module is touched.
* Baselines re-verified byte-identical after all work:
  `MODEL_HEALTH_2026-09-13.json` `4639ff1a0fdcb8a6`,
  `SUNDAY_1PM_OUTCOME_AUDIT.json` `82f706127181238d`,
  `SUNDAY_MARKET_OUTCOME_AUDIT.json` `69cb6c45c8ce5c33`,
  frozen snapshot `98dbe0713d56d27d`.
* No `git add`, `commit`, `stash` or `push`. Full suite not run.

## 9. ONE FOLLOW-UP I DELIBERATELY DID NOT FOLD IN

The **classification** is single-sourced, but the **branch ladder** now exists
twice: inline in `same_day_retrospective.score_seal`, and as
`market_outcome_audit.resolve_realised`. They are asserted equivalent by test,
which is not the same as being one function.

Collapsing them — moving `resolve_realised` into `same_day_retrospective` and
having both scorers call it — is the right end state and is cheap. I did not do
it here because it would have put a refactor of already-reviewed retrospective
code inside the market commit, against the instruction to keep the two
separate. It is a third, small, behaviour-preserving commit whenever you want
it.

## 10. WHAT THIS DOES NOT ESTABLISH

Nothing here is evidence about the model. One slate, four game clusters on the
clean stratum, no predeclared equivalence margin, no two-one-sided test. The
sportsbook remains a second comparator and never truth: a market that beat us
on a Sunday has not been shown to be right. No threshold was selected because
it would have won today, no cutoff was optimised, and no wager is recommended.
