# Sunday runbook — 2026-09-20, NFL Week 2

Written 2026-09-19 against the tree at `04f9069`. Every number in it was read
out of the repository today; where something is unverified it says so.

**Read this first: there is no card tomorrow.** The production entrypoint
refuses the entire slate at two named gates, and both refusals are correct.
This runbook is therefore about *capturing evidence that cannot be
reconstructed afterwards* and *recording the refusal honestly*, not about
producing plays. `nfl/SUNDAY_READINESS.md` has the full subsystem table and
the evidence behind that sentence.

---

## The slate

Fourteen games Sunday, one Monday. DET@BUF already played on Thursday.

| kickoff (UTC) | games |
|---|---|
| 15:30 → 16:50 window | CAR@ATL, CIN@HOU, CLE@TB, GB@NYJ, MIN@CHI, NO@BAL, PHI@TEN, PIT@NE |
| 18:35 → 19:55 window | JAX@DEN, LV@LAC |
| 18:55 → 20:15 window | MIA@SF, SEA@ARI, WAS@DAL |
| 22:50 → 00:10 window | IND@KC |
| 09-21 22:45 → 00:05 | NYG@LA |

The window is the T-90 capture window, not the kickoff.

---

## T-12h and Saturday night — DONE, with one thing outstanding

- [x] Capture surface ingested. `capture-prod` merged at `8b8555b`; six core
      sources last captured 2026-09-19T15:05:38Z.
- [x] T-90 crons regenerated for week 2 (`f9148b0`). Six windows, sixteen
      entries.
- [ ] **OUTSTANDING AND TIME-CRITICAL — `nfl-t90.yml` must reach the
      repository's default branch before 15:30Z.** GitHub schedules workflows
      from the default branch, so the correct file on
      `claude/nfl-greenfield-architecture-stsxmk` changes nothing about what
      fires. This is **OUT-026** and it is the single highest-value action
      left. If it does not happen, eight games' inactives windows close with
      no anchored executor.
- [ ] The participation availability watch (`nfl-availability.yml`) has not
      run since 2026-09-15T06:37:05Z and still pushes to `main` while the
      capture surface moved to `capture-prod`. **OUT-024.** Not urgent for
      tomorrow — it buys provenance, not a forecast input.

## Sunday morning, before 15:00Z

1. **Place the tree before believing any freshness number.**

       python3.12 nfl/production/capture_freshness.py --verify-surface

   It reports `CAPTURE_TREE_BEHIND_SURFACE` with a measured commit distance
   whenever this checkout is behind `capture-prod`. A freshness reading taken
   without this is a reading of a branch, not of the system — that error was
   made on 2026-09-19 and cost most of a morning.

   If it reports behind, merge `capture-prod` before reading anything else.

2. **Re-read the gap registry's horizons.**

       python3.12 nfl/tools/discovery.py --write

   `GAP-2026-PARTICIPATION` will surface as `ASSIGNED_PAST_HORIZON` until the
   availability watch runs again. That is correct and expected; it is not a
   new finding and does not need re-reporting.

3. **Do not attempt to seal a board.** It will refuse. See below.

## T-3h to T-2h per window

Nothing to run by hand if OUT-026 landed: the anchored workflow fires inside
each window. Verify afterwards rather than during —

    python3.12 -c "import json,collections;
    rows=[json.loads(l) for l in open('nfl/vintage_manifest.jsonl') if l.strip()];
    print(collections.Counter((r['source'],r['state']) for r in rows
          if r['source']=='official_inactives' and r['capture_id'][:8]=='20260920'))"

If OUT-026 did **not** land, the fallback is a manual capture of the official
inactives page inside each window, attributed to a game_id. The endpoint
correction in OUT-016 applies. A missed window is recorded as closed unfilled;
it is never backfilled from a later file, because a final file is not
point-in-time evidence and dressing it as one is the defect this project
audits itself for.

## T-90 per window

The inactives file does not exist before roughly T-90 and is final once it
does. This is the only irreversible moment in the day. Everything else can be
redone tomorrow; this cannot.

## Final freeze

**There is no freeze tomorrow, and this is not a step that was skipped.**

`run_forecast` refuses every game in the slate. Measured on the full week-2
slate, both under `PRODUCTION_BASELINE` and under
`V1_CANDIDATE_R9_W1P_GSVUCY`:

- `feature_build` → `DEFERRED[STAGE_DECLARED_UNIMPLEMENTED]`, 15 of 16 games.
  The accepted research baseline has no production implementation and is
  declared as debt rather than reported as a forecast.
- `artifact_sealing` → `BLOCKED[ARTIFACT_SEALING_FAILURE]`, 15 of 16, on
  `current_season_input_freshness`. `denom_panel` is
  BLOCKED-BY-DECLARATION (`CURRENT_SEASON_SOURCE_UNVERIFIED`) and
  `team_volume_history` is `CURRENT_SEASON_INPUT_STALE` — both read
  `denom_panel.csv.gz`, whose newest ordinal is **202518** against a required
  **202601**. There are zero 2026 rows in it.
- DET@BUF → `BLOCKED[SOURCE_CHRONOLOGY_FAILURE]`, correctly: a forecast
  written at 2026-09-20T12:00Z is not before a 2026-09-18T00:15Z kickoff.

`panel_p3` is the one current-season input that is **fresh** — the
current-season QB panel resolves 30 of 32 clubs from week-1 play-by-play and
snap counts, missing DEN and KC.

So the correct Sunday artifact is the refusal itself, sealed with the evidence
behind it, and that is what `nfl/SUNDAY_READINESS.md` records.

## After the games

1. Capture the authoritative outcomes (assigned — this executor has no
   network; see the outbox).
2. Grade nothing that was not forecast. There is no board, so there is no
   prospective row for week 2, and the evaluation ledger must not gain one.
3. **Never edit a frozen artifact.** A correction is a successor artifact.

---

## What would change this picture

One thing, and it is not a model change: **a 2026 denominator panel**.
`denom_panel.csv.gz` holds 3,230 rows from 202001 to 202518 and nothing for
2026. Until a current-season source for it is established, the freshness gate
will refuse every board of the season, correctly. `feature_build` is the
second blocker and is a genuine implementation gap, not a data one.

Neither is a threshold to loosen. An empty card is a valid result.
