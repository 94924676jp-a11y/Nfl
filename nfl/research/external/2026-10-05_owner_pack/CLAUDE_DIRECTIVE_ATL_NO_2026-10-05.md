# CONSOLIDATED EXECUTION DIRECTIVE — ATL @ NO DK SHOWDOWN (MNF, 2026-10-05, LOCK 8:15 PM ET)

Repository: `94924676jp-a11y/Nfl` (working branch: `claude/nfl-greenfield-architecture-stsxmk` unless you record a reason to branch).
This directive replaces every earlier DFS/Showdown prompt. Start executing immediately. Do not reply with a plan, a research summary, or "what I learned." Reply only with commits, artifacts, gate verdicts, and the final return block in §11.

---

## 0. Priority order (non-negotiable)

1. **Tonight's product ships.** A valid, gated ATL–NO portfolio for all three contests beats any amount of architecture work. Architecture work never delays a production checkpoint in §9.
2. **Governance holds.** The football firewall, chronology sealing, and fail-closed authorization stay intact. A shortcut that breaks them is a defect, not a speedup.
3. **The DFS intelligence layer gets built as tested machinery.** Each piece runs tonight in whatever validated state it reaches, labeled with that state.
4. **Yesterday becomes prospective observation #1. Tonight becomes #2.** Both stay immutable after they're sealed.

---

## 1. Frozen inputs (verify hashes first; any mismatch = STOP and report)

Commit these under `nfl/research/dfs/ATL_NO_2026W4_MNF/inputs/` (raw bytes, no edits), plus the evidence pack under `nfl/research/external/youtube_dfs_evidence_2026-10-05/`.

| File | SHA-256 | What it is |
|---|---|---|
| `DKEntries-2026-10-05T111816.801.csv` | `fd0c1faa2271ca6622d3ecea4a1decf6843729a8e3a5c624466d5788df2d65a8` | Tonight's DK entries file plus the DK player/ID block (56 players × CPT/FLEX = 112 rows) |
| `draftkings_showdown_NFL_2026-week-4_players-2.csv` | `330fdd518c66ea57651f799022af152f9997d1925097224edb2a527888da8b7a` | FantasyCruncher ATL–NO export (34 players × CPT/FLEX; first row blank). **EXTERNAL MODEL OUTPUT. Prohibited as a football input.** |
| `contest-standings-196208416.zip` | `d82d89a9e64df3d0ca03ab9a4c2e9dbf8997db961f61497c602ca3903e54619d` | Yesterday's (2026-10-04) Early Only classic 150-max standings: 35,671 entries, 4,151 users, full lineups plus %Drafted/FPTS block |
| `contest-standings-196208417.zip` | `ec2a2bba48487d5e63496527a3590f7455d66624a34c5a97c46cf4b8ec74128f` | Yesterday's 20-max standings: 14,268 entries, 3,377 users |
| `contest-standings-196208418.zip` | `86ff2e4c093897832cca41d5253542c92f220e2bd5a5578001ab3120c2244484` | Yesterday's third contest: 11,890 entries, 2,913 users. **Entry tags show a 20-entry max, not 3-entry. Read the true contest name and entry limit from the data or from the owner, and record it before using it.** |
| `NFL_DFS_YouTube_Transcript_Evidence.md` | `399bac58c3876cd7f41b77f369899dd9defda0220fea0b18551a0ff4b99a6b60` | 66-video research pack: 63 transcripts, 480 verified excerpts. **EXTERNAL RESEARCH, frozen, read-only.** |

**Tonight's contests** (from the entries file):

| Contest | ID | Fee | Our entries | Portfolio key |
|---|---|---|---|---|
| NFL Showdown $100K mini-MAX [150 Entry Max] (ATL @ NO) | 196285137 | $0.50 | 150 | `P150` |
| NFL Showdown $10K Quarter Jukebox (ATL @ NO) | 196285160 | $0.25 | 20 | `P20` |
| NFL Showdown $5K Dime Package (ATL @ NO) | 196285161 | $0.10 | 2 | `P2` |

**CRITICAL:** all 172 entries currently hold one identical placeholder lineup: CPT Bijan Robinson; FLEX Nick Folk, Kendre Miller, Kyle Pitts Sr., Spencer Rattler, Cooper Rush. Unreplaced, that is 172 duplicate entries built around backup QBs. Replacing it is the minimum deliverable.

**DK username for identifying our entries in yesterday's standings:** `<<OWNER FILLS IN>>`. If it's absent, our-entry analysis is BLOCKED; field-level analysis still proceeds.

**Other referenced inputs** (ingest only if present in the repo or supplied by the owner; otherwise mark `NOT_SUPPLIED` and continue):
- NFL autonomous-production constitution: the governing document. If it conflicts with this directive, the constitution wins on governance and this directive wins on tonight's scope. Log every conflict.
- Yesterday's original lineups, original projections, original exposures, and sealed run artifacts (repo).
- Stokastic "Falcons-Saints Showdown Strategy MNF Week 4" (https://www.youtube.com/watch?v=2NTS1Dn33BU). No transcript existed as of 1:20 PM ET. If one appears, capture it with a timestamp; otherwise record `TRANSCRIPT_UNAVAILABLE`.
- ETR tournament-meta video, DFS Army historical Showdown video (likely https://www.youtube.com/watch?v=65HDqKemR88), and the projection-engineering tutorial: owner to confirm exact URLs.
- Hard Rock ATL–NO lines/props: downstream comparison only (§4).

---

## 2. Claim taxonomy (mandatory on every external claim you touch)

Every claim pulled from the evidence pack, FC, Stokastic, ETR, DFS Army, Hard Rock, or any video gets exactly one tag in a committed ledger (`EXTERNAL_CLAIMS_LEDGER.jsonl`: claim_id, source, URL+timestamp, verbatim text, tag, intended use, test status):

| Tag | Meaning | Allowed use |
|---|---|---|
| `EMPIRICAL_HISTORICAL_EVIDENCE` | Counted historical result with a stated sample (e.g., "WR optimal CPT 33.1% across 163 slates") | Prior or benchmark only. Sample, definition ("nut" vs "winner" vs "top 1%"), site (DK vs FD), and possible vendor bias recorded |
| `EXTERNAL_MODEL_OUTPUT` | Another system's numbers (FC projections, Stokastic sims, SaberSim ownership) | Post-seal comparison or benchmark only |
| `EXPERT_OPINION` | Practitioner judgment with no counted sample | Hypothesis generation only |
| `FIELD_BEHAVIOR_HYPOTHESIS` | A testable claim about what opponents do | Becomes a feature or test in the field model; must be scored against our historical standings |
| `PRODUCTION_CANDIDATE` | A method we've implemented and that is undergoing testing (e.g., product-ownership dupe estimator) | Runs tonight labeled with its validation state; promoted only by evidence |
| `PROHIBITED_DIRECT_INPUT` | Anything that would contaminate the football model (FC projections, sportsbook lines/props, other providers' projections) | Never upstream of the sealed football projection |

**Anti-cargo-cult rule:** no external finding becomes a hard optimizer constraint. "WR optimal CPT 33.1%" may become a prior or a diagnostic ("our CPT mix vs historical vs field"). It must never become "force 33.1% WR CPT." Tonight's distributions, ownership, script, and salary structure decide. Any hard constraint must be a DK legality rule or a written owner decision.

Known caveats from the pack (carry into the ledger):
- FTA, DFS Army, and 925 Sports are vendors.
- 925's K/DST figures appear to share FTA's dataset, so they are not independent confirmation.
- DFS Army's 2020 MVP split and $55K figure are FanDuel.
- No validated out-of-sample dupe model exists. ETR's R² 0.55 vs 0.26 is a single-variable comparison.

---

## 3. Target architecture (build this, not `projection → optimizer → 150 CSV`)

```
football simulation (shared joint worlds)
  → DK Showdown scoring (CPT 1.5x points, 1.5x salary)
  → slot-specific ownership prediction (CPT% and FLEX% per player, per contest)
  → field lineup generator (actual opponent lineups, per contest)
  → conditional/combinatorial ownership + predicted duplication
  → contest simulation (our candidates vs generated field, real payout tables)
  → portfolio optimization (P150, P20, P2 independently)
  → gates → DK upload files
```

Layer contracts:
- **Football layer:** sees no DFS ownership, salary-as-signal, FC, Stokastic, or sportsbook data. Ever.
- **DFS research/field layer:** may use historical and current market variables (spread, total, favorite/underdog) only as `FIELD_BEHAVIOR` features describing what opponents do, and only in historical lineup-cohort studies. Those variables must never flow back into football projections. Enforce this with an import/dataflow test, not by convention.
- **Shared worlds:** the latest audit found the sealed draws `INDEPENDENT_STREAMS_COLUMN_ALIGNED`. Tonight's single-game joint simulation must produce coherent shared worlds: one game script drives every player's line, and QB yards equal the sum of receiver yards. Prove that with tests (§6). If you can't, every correlation-dependent output (stack value, CPT+own-QB pairing, dupe correlation adjustment) is labeled `LOWER_BOUND/UNVALIDATED`.

---

## 4. Workstream A — Tonight's football production (starts now, runs in parallel)

1. **Repo audit (≤30 min, time-boxed).** Inventory what exists for Showdown: the exact per-game DP, scoring contract, gate enforcement (`nfl/dfs/gate_enforcement.py`), `DFS_150_MAX_AUTHORIZATION`, OwnershipModel/FieldSimulator stubs, and late-swap/export code. Write `REPO_AUDIT_ATL_NO.md` covering what's reusable, what's broken, and what's missing. No refactors during the audit.
2. **Universe reconciliation.** Build the canonical ATL–NO universe from the DK block (56 players, IDs, CPT/FLEX salaries). Reconcile it with the FC file (34 players), which is only a coverage cross-check. Every DK player gets a status: `ACTIVE_PROJECTED`, `ZERO_ROLE`, `QUESTIONABLE`, `INACTIVE`, or `UNRESOLVED`. `UNRESOLVED` blocks that player, not the slate. Note FC flags Noah Fant with "!", so verify his status.
3. **Current evidence gathering, all timestamped, with source URLs, chronology-sealed:** rosters, injury reports and practice participation, projected starters, depth charts, role/usage history (snaps, routes, targets, carries, red zone), OL changes, QB status for both teams (Shough, Rattler, Rush on NO; ATL QB room), weather/venue (dome), kicker/DST context, and official inactives (~6:45 PM ET).
4. **Independent football projection** → sealed with run ID, input vintages, written time, and draw digest.
5. **Coherent joint simulation** of ATL–NO: N ≥ 20,000 worlds (state N), shared game script, DK Showdown fantasy points per player per world.
6. **Only after sealing:** compare with FC and Hard Rock (`POST_SEAL_COMPARISON.md`). Large disagreements trigger an audit note (role assumption, injury, script). They never trigger silent adjustment. Any post-seal change requires a new sealed run with the reason logged, and the comparison sources are never inputs.

---

## 5. Workstream B — DFS intelligence layer (build as tested machinery)

### B1. Prospective observation #1 (yesterday, immutable)
- Parse all three standings files into a sealed dataset: every entry's lineup, score, rank, the %Drafted/FPTS block, and per-entrant entry counts.
- If the username is supplied, join our original lineups, projections, and exposures to the actual results. Never regenerate yesterday's projections. Hindsight versions, if ever made, live in a separate, labeled directory.
- From the field, compute: actual ownership vs our projected ownership (if we had it), stack/construction frequencies, salary-used distribution, duplicate counts per unique lineup, and the duplication-vs-ownership relationship.
- Use this as the first evaluation set for B3 and B4. It's a classic slate, not Showdown. Label any transfer to Showdown `CROSS_FORMAT_TRANSFER_UNVALIDATED`.

### B2. Slot-specific ownership (per contest)
- Output CPT% and FLEX% per player, separately for P150, P20, and P2. Per-player CPT% sums to 100%; FLEX% sums to 500%.
- Candidate method (tag `PRODUCTION_CANDIDATE`): many high-variance optimizer builds off a field-like projection, with exposures read off per slot, plus contest-size condensation (chalk concentrates in smaller fields). Features may include salary, projection, value, role news, game environment (`FIELD_BEHAVIOR` market variables allowed here only), and position-at-CPT tendencies (field overweights QB CPT per the pack).
- Uncertainty is required: give an interval per player-slot, not a point.
- Validation tonight: internal consistency only. Calibration is scored post-game (§10).

### B3. Field lineup generator
- Generate actual opponent lineups per contest (target sizes: the true entry counts of 196285137, 196285160, and 196285161, or documented estimates). Respect DK legality, salary-used behavior, construction frequencies (5-1, 4-2, 3-3, 2-4, 1-5), QB-count behavior, and K/DST frequency.
- Diagnostics: generated-field slot ownership must reproduce the B2 targets within a stated tolerance. Report the error.

### B4. Combinatorial ownership and duplication
- Baseline candidate: `E[dupes] ≈ field_size × Π slot_ownership`, modified by a correlation adjustment × salary-left adjustment × construction-frequency adjustment.
- Required: compare the baseline formula with the empirical dupe count from the B3 generated field. Report where they diverge (correlated pairs like WR CPT + own QB break independence).
- Backtest on B1 (classic, cross-format): product vs geomean vs total ownership as dupe predictors, reported as rank correlation and R². Report whatever comes out, even if it contradicts ETR's 0.55/0.26.

### B5. Contest simulation
- Each candidate lineup vs the generated field across the shared football worlds, with real payout tables per contest (pull from DK contest detail; if unavailable, state the assumption). Ties split per DK rules. Output ROI, P(first), P(top 1%), cash rate, and expected dupes.

### B6. Portfolio optimization (three independent optimizations)
- One football world, three separate ownership/field/payout contexts. P20 and P2 are not subsets of P150 unless the optimizer independently selects the same lineups. Report overlap.
- Optimize the portfolio, not isolated lineups: marginal contribution to portfolio EV/top-finish probability, scenario coverage across game-script clusters, exposure and overlap controls, and a duplication penalty scaled to contest size.
- Concentration and dupe tolerance differ by contest. P150 is the most diversified and most dupe-averse. P20 is moderate. P2 is near-optimal with mild uniqueness levers. All three are decisions driven by the contest sim, not fixed numbers.
- Pack-derived priors (CPT position mix, K/DST rates, salary-left, 5-1 leverage) appear only as diagnostic comparisons in the board, never as constraints.

---

## 6. Required tests (must pass before any file is labeled final)

- DK Showdown legality: 6 players, 1 CPT, salary ≤ $50,000, ≥1 player from each team, no player in both CPT and FLEX, every ID in the DK block, CPT uses the CPT ID.
- Scoring contract: the CPT 1.5x multiplier is applied to points, and CPT salary matches the DK block.
- Shared-world coherence: per-world team passing yards = sum of receiving yards; team TDs consistent across players; nonzero, signed QB–own-WR correlation measured in fantasy points.
- Firewall: a dataflow test proving FC, Hard Rock, and ownership modules are unreachable from the football projection inputs.
- Ownership integrity: CPT% sums to 100% and FLEX% to 500% per contest; field generator reproduces targets within tolerance.
- Inactive gate: zero exposure to any `INACTIVE` player in every file (hard gate; `unavailable_owns_nothing` must be HARD for tonight's export, not DIAGNOSTIC).
- Export round-trip: re-parse each upload file and confirm the Entry IDs match the original entries file exactly (150 / 20 / 2), with no missing, extra, or reordered IDs.
- Determinism: same seed + inputs → identical files (hash recorded).

---

## 7. Gating and authorization (fail-closed)

Per-contest verdict: `AUTHORIZED` or `BLOCKED` with the failing gates listed. No third state is hidden inside prose.

Gates:
1. Universe reconciled
2. Inactives ingested (official, timestamped)
3. Football run sealed
4. Shared-world coherence passed
5. Scoring certified
6. Legality passed
7. Inactive hard gate passed
8. Export round-trip passed
9. Ownership/field/dupe layers run, with their validation state labeled

Gate 9 can pass as `RAN_UNVALIDATED`. Unvalidated intelligence layers don't block tonight, but they must be labeled.

**Owner decision on BLOCKED** (pick one before sending; see the prep note):
- Option A, strict: BLOCKED means no upload file is produced. The placeholder lineup stays in place.
- Option B, best-available: BLOCKED still produces a clearly named `NOT_AUTHORIZED_BEST_AVAILABLE` file plus the failing-gate list, and the owner decides whether to upload. Legality, inactive, and export gates are never waivable under either option.

---

## 8. Production-only mode (pre-lock)

At **6:30 PM ET**, all architecture work stops. From then on:
1. Ingest official inactives and late news.
2. Re-run the sealed football projection.
3. Re-run the joint sims.
4. Re-run ownership.
5. Re-run the field.
6. Re-run dupes and the contest sim.
7. Re-optimize P150, P20, and P2.
8. Run gates and export.

If a step's rerun fails, fall back to the last sealed passing version of that step, label it, and continue. Never ship an unrun step's stale output unlabeled.

---

## 9. Checkpoints (ET)

| Time | Required state |
|---|---|
| 2:00 PM | Inputs hashed and committed; repo audit committed; universe reconciled; claims ledger started |
| 3:30 PM | Baseline sealed football run plus joint sims; **fallback upload files for all 3 contests that pass legality, inactive, and export gates** (replaces the placeholder risk) |
| 5:30 PM | B2–B5 running end to end at whatever validation state; v1 portfolios plus boards |
| 6:30 PM | Production-only mode (§8) |
| ~6:45 PM | Official inactives ingested |
| 7:40 PM | Final files, boards, and gate verdicts committed |
| 7:55 PM | Hard stop. Owner uploads. No changes after this without owner instruction |
| 8:15 PM | Lock |

If a checkpoint is missed, drop scope from Workstream B, never from Workstream A or the gates.

---

## 10. Post-game loop (prospective observation #2)

After the game ends and DK posts standings (the owner supplies the three standings exports):
- Seal actuals.
- Score these against the sealed pre-lock artifacts, never against reruns:
  - **Football:** proper scoring rules per player, calibration of intervals, joint/stack outcomes.
  - **CPT% and FLEX% ownership:** error and interval coverage per contest.
  - **Construction:** predicted vs actual mix of 5-1/4-2/3-3, QB count, K/DST, salary-left.
  - **Duplication:** predicted vs actual dupe counts.
  - **Portfolio outcomes:** ROI, best finish, rank distribution vs contest-sim expectation.
- Append to the observation registry as #2 alongside #1, and keep the two formats (classic vs Showdown) distinguished.
- No method is promoted on one observation. Record evidence; promotion follows the existing promotion standard.

---

## 11. Return block (exact format, final message)

```
ATL_NO_2026W4_MNF RETURN
commit: <sha>   branch: <name>
inputs_verified: 6/6 sha256 match | mismatches: <list or none>
football_run: <run_id> sealed_at <ET> inputs_vintage <ET> draws <N> digest <hash>
shared_world_coherence: PASS|FAIL (<tests>)
inactives: official_ingested_at <ET> | inactive players: <list>
firewall_test: PASS|FAIL
ownership_model: <state: VALIDATED|RAN_UNVALIDATED|NOT_RUN> per contest
field_generator: <state> | target-reproduction error: <metric>
dupe_model: <state> | baseline vs generated-field divergence: <summary>
contest_sim: <state> | payout tables: <source or assumption>
P150: AUTHORIZED|BLOCKED|NOT_AUTHORIZED_BEST_AVAILABLE | file <path> sha <hash> | gates failed: <list>
P20:  same
P2:   same
boards: exposure (CPT/FLEX), projected CPT%/FLEX% per contest, dupe estimates, salary-left distribution, construction mix, P150↔P20↔P2 overlap, priors-vs-ours diagnostic
post_seal_comparison: FC <summary> | Hard Rock <summary>
claims_ledger: <n> claims | by tag: <counts>
observation_1: sealed <path> | our-entry join: DONE|BLOCKED(<reason>)
constitution_conflicts: <list or none>
open_owner_decisions: <list>
FINAL VERDICT: <one line>
```

Stop conditions:
- Input hash mismatch
- Firewall test failure in the football layer
- Any inability to produce legal, inactive-clean, round-trip-verified files by 7:40 PM, reported immediately with the best legal state reached

Do not ask clarifying questions mid-run unless a stop condition is hit. Log assumptions and continue.
