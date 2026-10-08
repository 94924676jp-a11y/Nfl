# Historical Showdown replay feasibility (deliverable A), 2026-10-08

Sources:
- A read-only repository inventory, delegated and then spot-checked. The production upload hashes, the generation-1
  cache hashes and the PIT@CLE owner entries were each re-verified by a command in this session.
- The replay environment built in this session, described below.

Nothing here was fabricated: no salary file, prelock input, payout, ownership or field composition was invented. A
**payout ladder is absent for every slate**. DraftKings standings exports carry rank, points and lineup, not the
prize table.

## Inventory

| Slate | Contest(s) with full-field standings | Prelock inputs | Prelock outputs | Production portfolio | Class |
|---|---|---|---|---|---|
| **ATL@NO** 2026 W4, kickoff 2026-10-06 00:15Z | 196285137 (150-max, 237,812 entries), 196285160 (20-max, 47,562), 196285161 (2-max, 59,453), all in `nfl/postgame/raw/showdown_history/` | All present and committed before kickoff: DKEntries `fd0c1faa…` (172 entries), FC `330fdd51…`, depth chart `1e6aa643…`, designations V4, inactives (RotoWire list, owner-verified official), starters, snaps | 7 complete scenario directories (STATE, PROJ, DRAWS, WORLDS, lineups, uploads) | `RW_INACTIVES_CHARTFIX` (v2), commit `9736516d` at 23:47Z, upload `8f4d9a77…` (per contest `4047a189`, `17e397b4`, `a30f529f`). Reconciled 172/172 against the owner's played entries. | **FULL_REPLAY_ELIGIBLE** |
| **PIT@CLE** 2026 W4, kickoff 2026-10-02 00:15Z | 196187080 only (20-max, 47,562 entries); its 3 sibling contests have none | DKEntries `67229d91…` (78 entries, 4 contests), vendor sheet, relayed inactives (`REPORTED_INACTIVE_HIGH_CONFIDENCE`, no official document). No designations file and no raw depth or snaps capture. No derived-cache manifest. | Flat files only: `SHOWDOWN_TONIGHT_{STATE,PROJ,DRAWS}.json`, upload `bf7d03e3…` (b05e476a). No WORLDS npz. | **Not what was played.** All 20 owner entries in 196187080 are one hand lineup (CPT Deshaun Watson, 90.94 points; verified). It appears in no committed system upload. | **PORTFOLIO_ONLY_REPLAY_ELIGIBLE** for the system's own prelock board (counterfactual scoring only); **SCORING_ONLY** for what was entered |
| **PHI@CHI** 2026 W3 | 196036243 (20-max) | None. No salary file (outbox request open). | None | The owner played one hand lineup (74.53 points) | **INCOMPLETE_EVIDENCE**: field and scoring only |
| IND_KC, NYG_LAR 2026 W2 | none | DKEntries only | not inventoried | — | **INCOMPLETE_EVIDENCE**: no standings |
| TB@DAL 2026 W5 | none yet | complete | precomputes | not played yet | prospective |

## Cutoff integrity, and the two findings it produced

1. **The derived cache.**
   - Today's cache (generation 2) holds week-4 play-by-play, and week 4 includes ATL@NO itself. **Using it for an
     ATL@NO replay would leak the outcome.**
   - Generation 1 is pinned in `DERIVED_REBUILD_MANIFEST.ATL_NO_REPRO_2026-10-07.json`. It was rebuilt in an isolated
     worktree at `b0a2b57b` from that commit's own tracked inputs, which hold no week-4 play-by-play, and **all 6
     artifacts match the pinned hashes**.
   - Every ATL@NO replay here uses that generation-1 cache.
2. **Game resolution depends on the current schedule (a latent defect).**
   - Today's code resolved the ATL@NO DraftKings export to `2026_17_NO_ATL`, the week-17 rematch, then refused
     `SLATE_STATE_NO_IMPLIED_TOTAL`.
   - The cause is in `showdown_slate_state.build`. It picks any unplayed same-season game between the two clubs from
     the latest `TEAM_GAME`, and it never checks that game's date against the export's kickoff.
   - It is harmless for TB@DAL (a single unplayed meeting).
   - It makes historical replay on current code depend on a point-in-time `TEAM_GAME`.
   - **Proposal, a validation-only class-A fix:** refuse `SLATE_STATE_GAME_DATE_MISMATCH` when the game's date
     differs from the export's kickoff date.
   - For the replays, `TEAM_GAME.json` as committed at the ATL@NO lock (`9736516d`, last changed `8feac0f3`
     2026-10-01; week 4 unplayed, implied ATL 21.0 / NO 24.5) is overlaid in the replay worktree only. It is recorded
     as part of the replay environment.

## Replay environments (isolated worktrees under /home/user/p0work; none touches the live checkout)

| Worktree | Code | Derived cache | `TEAM_GAME` | Purpose |
|---|---|---|---|---|
| `hist-b0a2b57b` | `b0a2b57b`, the code of the recorded 2026-10-07 reproduction | generation 1, rebuilt and matched 6/6 | as committed | historical baseline reproduction |
| `atl-66990085` | `66990085`, today's incumbent before P0 | generation 1 (copied, hashes match) | lock-time overlay | incumbent drift check |
| `atl-0ea3bc21` | `0ea3bc21`, P0 repairs | generation 1 (copied, hashes match) | lock-time overlay | P0 A/B |

## Comparisons each slate can support

| Comparison | ATL@NO | PIT@CLE | PHI@CHI |
|---|---|---|---|
| Baseline reproduction of the production portfolio | yes | no (no WORLDS; system board not played) | no |
| One-change A/B with matched seed | yes | only if its 2026-10-01 code reproduces from the DRAWS JSON (not attempted tonight) | no |
| Exact rank of any lineup against the full field (DraftKings tie rule: equal points share a rank) | yes, all 3 contests | 196187080 only | 196036243 only |
| Dollar payout | **not exact.** Only a conservative curve from the owner's own graded entries (`showdown_atl_no_portfolio_study.py`); capped above the best observed entry; unavailable for the 2-entry contest | rank only | rank only |
| Independent (held-out) evaluation | no. ATL@NO has already been used for development (the post-game study, the TE-order fix, SC-OWN-ROTATION-1) | no | no |

Any historical A/B here is therefore **retrospective development evidence**, not held-out validation. Held-out
evidence has to come from untouched future slates, TB@DAL onward.
