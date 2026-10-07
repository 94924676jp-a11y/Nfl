# Appearance successor (SC-APPEAR-1 rates + strict hurdle + field-specific pi) — return, 2026-10-07

Status: **SHADOW_ONLY. No production file edited. Not on the execution path. Not prospectively scored.**
Nothing committed by this session (the coordinating agent commits).

## Asked
Owner directive 2026-10-07, priority 2: finish the appearance-propagation successor with the SC-APPEAR-1 rates and a
draw-level gate whose zero mass provably enters the simulated worlds; keep it shadow-only; pre-register; seal 2026
week 5 before the first kickoff (2026_05_TB_DAL, 2026-10-09T00:15Z); write a grader; test it.

## Done
| File | What |
|---|---|
| `nfl/research/appearance/appearance_successor.py` | core: field-specific pi fit (<= 2024), hurdle simulator (production `nfl/sim/game.py` + 4 in-memory substitutions), end-to-end chain, pregame harness |
| `docs/NFL_APPEARANCE_SUCCESSOR_PREREGISTRATION.md` (444) + `nfl/prospective/appearance/APPEARANCE_SUCCESSOR_PREREG_LOCK.json` (444) | prereg sha256 `792fe9100fb6e7835fd5057e6227098b180e7eb9eefc66a044c1d9908aa9724d`, locked 2026-10-07T15:13:20Z, before any new score and before the seal |
| `nfl/prospective/appearance/seal_appearance_w5.py` | the seal writer (any week via `--week`; refuses at/after kickoff, refuses overwrite, refuses a prereg that no longer matches its lock) |
| `nfl/prospective/appearance/APPEARANCE_SUCCESSOR_W5_SEAL.json` (444) | **written 2026-10-07T15:22:07Z**, 15/15 week-5 games, 437 player-field units, 339 players; `seal_sha256` `03f18d4abbaa47983bcea9e63f03bd3346af89b4789d3cff5f80fc217b5be1b3` (file bytes sha256 `ed417cfb6fc4c8ffe52e27e55b1d3a379495106d21894e9b4bdaa80591d40b22`) |
| `nfl/research/appearance/grade_appearance_seal.py` | postgame grader (not run on real outcomes) |
| `nfl/research/appearance/appearance_successor_dev.py` → `APPEARANCE_SUCCESSOR_DEV_2025.json` | 2025 DEVELOPMENT scoring |
| `nfl/tests/test_appearance_successor.py` | 16 functions, 89 checks; direct run and `run_suite.py --modules test_appearance_successor`: 0 failing |

## Hurdle design
Gate per club-world from a separate stream; one uniform per player (an RB's two gates comonotone). Closed → weight 0
in the field and its TD share. Open → the production Dirichlet-multinomial draw is conditioned on every open gated
player getting >= 1 (rejection, <= 200 redraws, then a counted reservation fallback). So **P(N_f = 0) = 1 − pi_f
exactly**, except worlds where the club total is below the number of open gated players (counted). Positive-part
weights solved from the beta-binomial marginal so the truncated mean matches the allocation's conditional mean;
ghost weight held at production's; a target mean <= 1 reserves exactly one unit (mean rises to pi). pi is
field-specific by (position, field, h = games with >= 1 in the club's last 3 games present), fitted on 2024; h = 3 is
exactly the SC-APPEAR-1 rate. Gated: RB carries, RB/WR/TE targets; QB and WR/TE carries untouched. Disabled →
byte-identical to production; all pi = 1 → declared NOT identical (P(0) = 0 exactly), and tested as such.

## Measured
**End-to-end zero mass** (spec → simulate_game_centred → efficiency_worlds → DST step → DK): count is 0 in exactly the
worlds whose gate is closed (0 mismatches, 26 player-fields x 3,000 worlds); zero shares within 4 binomial SE of
1 − pi (worst 2.51 SE synthetic, 1.93 SE on the real 2026-W4 ATL@NO harness game, max 3.32 SE over the 437 sealed
units at 2,000 worlds); every gated allocation players + ghost = club total; per world player counts + ghost =
club_worlds; post-steps leave every count unchanged; DK < 0.01 in zero-opportunity worlds except 1 in 60,000
(production yard dust from `split()`'s 1e-9 floor). On 2025: mean (successor P0 − (1 − pi)) = +0.0002 over 6,589 units.

**2025 — DEVELOPMENT ONLY (fourth read of 2025; not confirmatory).** 220 games, 6,589 units, 15 week blocks, 32 clubs,
1,000 worlds per arm (4 games refused, SIMULATION_REFUSED).
- Primary, draw-zero Brier current − successor: **+0.0685 week-blocked (SE 0.0040, z 17.0); +0.0676 club-blocked
  (SE 0.0080, z 8.4)**. Brier 0.2123 → 0.1442.
- Positive-count conditional CRPS, current − successor: +0.130 club-blocked (SE 0.045, z 2.9).
  **But successor is worse than the ungated SC-APPEAR-1 candidate on it: −0.194 club-blocked (SE 0.014, z −13.7)**,
  concentrated in h = 0 cells (e.g. TE targets h0 2.96 vs 0.83) — the zero-truncated positive part with mean-floor
  binding is a worse conditional shape for fringe players.
- Rank-1: −0.0027 club-blocked (SE 0.0077, z −0.35) — inside the no-regression bar, not an improvement; rank-1 mean
  P0 0.179 against observed 0.081 (rank-1 players with h < 3).
- Successor vs ungated candidate on draw-zero Brier: +0.0354 club-blocked (z 6.0).
- The prereg bar applied descriptively to 2025 passes; that is not the verdict.
- Correction recorded in the artifact: the grader's t table stopped at df 13 and fell back to 1.96; fixed (df 1-30,
  refuses otherwise); the 2025 descriptive check is unchanged (t 17.0 > 2.145).

## Audit ladder
IMPLEMENTED, SUCCESS_TESTED, REFUSAL_TESTED, ADVERSARIAL_TESTED (research). ON_EXECUTION_PATH: NO.
PROSPECTIVE: sealed, **ungraded** — a verdict needs >= 4 graded weeks, >= 1,500 units, >= 25 clubs, one look.

## Open / needs the other agent
- Week 4 is MISSING_FROM_REPO in the panel (seal uses weeks 1-3, declared). Later seals need the refreshed panel.
- Grading needs 2026 nflverse `snap_counts` (dressed) and the panel with week-5 rows. Not in this checkout. I could
  not append to `docs/AGENT_OUTBOX.md` (tracked file, outside my write scope); the coordinator should file it.
- Weeks 6+ need their own seals before kickoff (`seal_appearance_w5.py --week W`); the core library must stay at the
  hash recorded in the W5 seal (a test enforces this).

## Limitations
Snap-count dressing hides active zero-snap players; simulator constants fitted including 2025; pi constant within
(position, field, h), so its zero mass discriminates only through h; MEAN_FLOOR_BINDING lifts low-share means; 9% of
gated allocations in the seal used the reservation fallback (shape differs from exact conditioning, P(0) unaffected);
prospective pools include future inactives and miss late joiners; harness, not the live Showdown path; the newest
schedule disagrees with 61 older captures on CHI@GB's kickoff (newest used, disagreement recorded in the seal).

## Tracked files changed by this session
None by hand. `nfl/tests/_suite_progress.jsonl` is written by `run_suite.py` (it, and `nfl/production/READINESS.json`,
were already modified in the working tree before this session's runner call).
