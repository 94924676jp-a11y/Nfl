# Week 5 Classic: ownership and duplication research board (status 2026-10-09)

**Nothing on this board enters selection.** The Classic optimizer (`nfl/opt/classic_portfolio.py`) does not read
ownership, and the Showdown path does not either (TB@DAL audit, D-06).

## What has been measured, using pregame forecasts against the actual field only

| Slate | Field | Forecast | Rank correlation with actual %Drafted | MAE (percentage points) | Note |
|---|---|---|---|---|---|
| TB@DAL Showdown, 150-max | 237,812 | **no-fit: share ∝ FC projection** | **0.93** (captain) | **1.09** (captain) / 2.88 (FLEX) | beat every fitted model below |
| TB@DAL Showdown | | shadow BLEND / FC_ONLY / SC-OWN-2 | 0.83 / 0.70 / — | 1.83 / 1.56 / 1.80 | SC-OWN-2 fails its first prospective slate |
| W4 Early Classic, 196208416 | 35,671 | **no-fit: ∝ FC projection** | **0.83** overall (QB 0.87, RB 0.93, WR 0.88, TE 0.82, DST 0.35) | 3.48 | **top-12-owned error 14.3 pp: chalk is under-predicted** |
| W4 Early Classic | | no-fit: ∝ FC² | 0.83 | 3.30 | top-12 error 10.8 pp, so concentration matters |

**Week 4 was development data.** The FC file used was the post-inactives FC capture
(`THIRDPARTY_players_EARLY_ONLY_2026W4_SUN1600Z_POSTINACTIVES`), which is a legitimate prelock input. But choosing
between ∝FC and ∝FC² *on* week 4 is fitting week 4. For Week 5 the incumbent forecast is **∝FC, declared now, before
the slate**. ∝FC² is recorded as a challenger, and both are graded on Week 5 actuals.

## Duplication

| Contest | What we know |
|---|---|
| Showdown TB@DAL (measured) | The field is highly duplicated: median 42 copies per field entry; only 4.1% unique. Ours: median 13.5, 18.7% unique. B4 maxent ranks lineups well (Spearman 0.71) but its level is about 6× off (Σ actual / Σ predicted 0.16) |
| Classic | No Classic duplication model has been graded. The W4 Early standings (35,671 entries) can measure the field's own duplication. Classic lineups duplicate far less than Showdown (9 slots, a larger pool) |

## Week 5 plan, all pregame
1. Freeze an ownership forecast before lock: ∝FC as the incumbent, ∝FC² as the challenger. The FC export of record is
   the latest pre-lock capture.
2. Report each of our lineups' geometric-mean ownership and the field's likely chalk stacks. This is descriptive, not
   used for selection.
3. After the slate, grade both forecasts against the actual standings with `showdown_standings.py`, generalised to
   Classic. Add the result to the cross-slate ledger.

**No ROI or expected-return claim is made.** Payout tables are not captured.
