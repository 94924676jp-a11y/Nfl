# Stage 2 pre-declaration — route / participation adequacy

Written 2026-09-08, **before any comparative predictive result existed**. HEAD
at writing: `0b8b5d1`. Departures will be labelled where they occur.

This is not a target model, not a receiving-yard model, and not a fantasy
model. It answers one question and stops.

## 1. The question

Is the currently available lawful, chronology-defensible participation
representation adequate enough to support a scientifically interpretable
receiving-target decomposition?

## 2. What the fields are, stated before they are used

The nflverse `route` column in `part_*.csv` is the **targeted receiver's route
classification on that play**. It is populated on 36–42% of plays, which is
about one per pass play. It is **not routes run per player** and will not be
called that anywhere in this study.

**True routes run are not available in this project.** They are not
manufactured. What is available is per-play on-field participation
(`offense_players`), from which a defensible proxy is built and reported as a
proxy.

These are kept apart and never used as synonyms:

| term | meaning here |
|---|---|
| appearance | the player took any offensive snap in the game |
| snaps | offensive plays with the player on the field |
| offensive snap share | snaps / team offensive plays |
| pass snaps | plays with the player on the field **and** the play was a dropback |
| route participation | pass snaps expressed as a share of team dropbacks — an **upper bound** on routes run, because a player on the field for a dropback may block |
| routes run | **NOT AVAILABLE** |
| targeted-route classification | the `route` column: what route the targeted man ran. Not a participation measure |
| alignment / slot-wide / personnel | formation and personnel columns; inventoried, not modelled here |
| availability | pregame injury/roster status, from P2/P3, unchanged |

## 3. The estimand

For player *i* in team-game *g*, the **participation share**

```
P_i = pass_snaps_i / team_dropbacks_i        (participation-derived denominators)
```

conditional on appearance. This is the quantity a target decomposition would
need, because target share factors as `S_i = P_i x R_i` with `R_i` the target
rate per participated dropback.

Evaluation is next-game, strict walk-forward, seasons 2022–2025 evaluated
separately, fitted on strictly earlier games only.

## 4. Baselines, fixed now

No complicated model is built unless simple evidence warrants it.

- league-and-position mean
- last observation
- EWMA over prior appeared games, half-lives 2, 3 and 5
- expanding player mean
- prior-season player mean

The incumbent comparison is the EWMA half-life 3 that P1–P3 accepted for
conditional share, applied here to participation.

## 5. Metrics

MAE, RMSE, correlation, R², bias, SD ratio, and interval coverage where a
distribution is produced. Reported pooled **and per season**, by position
(WR / TE / RB separately), and on these pre-declared cohorts:

- prior appeared games: <4 / 4–9 / 10–24 / 25+
- appearance probability: <0.25 / 0.25–0.50 / 0.50–0.80 / 0.80–0.95 / ≥0.95
- role change: prior participation step ≥ 0.15 in absolute value, versus stable

## 6. THE ADEQUACY RULE — fixed before any comparative result

Five conditions. Each is checked independently and reported whether or not it
is convenient.

**PA-1 — skill over a trivial baseline.** The best chronology-safe forecast
beats the league-and-position mean on pooled MAE by **≥ 10% relative**, in
**≥ 3 of the 4** evaluation seasons, **separately for WR and for TE**.

**PA-2 — discrimination.** Pooled forecast-versus-realised correlation
**r ≥ 0.70**, and SD ratio `sd_pred / sd_actual` **≥ 0.50**, for WR and for TE.
Below that the forecast explains under half the variance, and a decomposition
would attribute to participation what is really noise.

**PA-3 — no cohort catastrophe.** In every pre-declared cohort of §5 with
n ≥ 200, cohort MAE is **≤ 2.5x** the pooled MAE for that position.

**PA-4 — coverage.** The participation representation is present for **≥ 90%**
of eligible WR/TE/RB player-games in **every** evaluation season, and zero is
distinguishable from not-applicable.

**PA-5 — chronology.** Every feature passes a masking audit: blank all outcome
fields at ordinal ≥ k, rebuild the features, and require the features at
ordinal == k to be bit-identical. Any movement is a failure.

## 7. The decision table — fixed now, no post-hoc reading

| condition | conclusion |
|---|---|
| PA-1…PA-5 all pass | **ADEQUATE_FOR_TARGET_DECOMPOSITION** |
| PA-4 or PA-5 fails | **DATA_BLOCKED** |
| PA-1 fails for every position | **INFORMATION_CONSTRAINED** |
| PA-1 passes somewhere but PA-2 fails everywhere | **UPSTREAM_INADEQUATE** |
| PA-1…PA-5 pass for some positions or cohorts and not others | **ADEQUATE_WITH_LIMITATIONS**, scoped explicitly to those that pass |

`ADEQUATE_WITH_LIMITATIONS` must name, in the return, what a target
decomposition is and is not allowed to conclude. A vague PASS is not one of the
available answers.

If the conclusion is anything other than the first or a scoped version of the
last, **Stage 4 is BLOCKED**.

**No threshold in §6 is changed after results are seen.**

## 8. Forbidden here

Current-game participation as a predictor of itself. Future participation.
Postgame roster state. `weekly_rosters.status`. Future teammate state.
Observed current-game target data anywhere upstream. Model-derived fields whose
fit window is unknown. Silent treatment of an ambiguous zero as a real zero.
Corrupted or substituted denominators. Fuzzy name matching. 2026 outcomes.
Market data.

## 9. Adversarial

Seeded probes: current-game participation; future participation; postgame
roster state; forbidden status field; future teammate state; identifier
leakage; observed current-game target data upstream; a model-derived field with
an unknown fit window; ambiguous zero versus N/A; denominator corruption.

At least **two load-bearing guard-deletion proofs** where feasible. A probe
that cannot fire is reported UNRESOLVED, never PASS, and no materiality
threshold is lowered after it is observed. Materiality for a seeded
participation leak is fixed now at **10% relative MAE improvement**.

## 10. What would count as a negative result

- If no method beats the position mean, the return says the available
  representation carries no usable next-game participation signal, in those
  words, and Stage 4 is blocked as INFORMATION_CONSTRAINED.
- If participation is only forecastable for established starters, the return
  says so and scopes the limitation rather than reporting a pooled average that
  hides it.
- If the proxy's gap from true routes cannot be bounded, the return says the
  gap is unbounded rather than assuming it is small.
