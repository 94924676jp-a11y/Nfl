# Session issue log — 2026-09-20

Everything that went wrong, in the order it bit. Written so the next person
does not rediscover any of it. My own mistakes are in here with the same
detail as everyone else's, because the ones I made cost the most time.

Scope: the 1PM Early Only slate, the 4PM slate, the Week-2 postgame grading
build, and the IND@KC Showdown work. Repo `94924676jp-a11y/Nfl`, branch
`claude/nfl-greenfield-architecture-stsxmk`.

---

## A. Defects in code I wrote this session

### A1. De-vig key names were guessed, and every edge silently vanished

**Severity: high. Shipped to the owner before it was caught.**

`nfl/market/odds.py::devig()` returns `novig_p_over`, `novig_p_under`,
`devig_status`. The prop board read `dv.get('p_over')`, `dv.get('p_under')`,
`dv.get('code')`.

All three names were wrong, so all three returned `None`. Every one of the
136 supported prop rows came back with `novig_p_over: null` and **no edge at
all**, on markets that were in fact two-sided on all 136. The failure reads
as *"the book gave no price"* when the truth was *"the key was guessed"*.

This is the same failure class as the historical export that wrote 7,926 rows
with every meaningful column blank because field names were guessed rather
than read from the schema.

Fix: names taken from the module. The board additionally carries `book_hold`
and `devig_method`. Commit `3c682ca`.

### A2. A kicker's DK distribution is not in `dk_scoring`

**Severity: high in a Showdown, where a kicker is a legitimate captain.**

Kickers carry their DK points under `kicking/dk_points`, not
`dk_scoring/dk_points`. The Showdown builder read only the first key and
**dropped both kickers entirely** — the coverage table read `K: 0` for both
clubs and the board still said USABLE.

Fix: both sources are read, and `K` was added to the gated position list so
the same omission cannot pass quietly again.

### A3. The package writer crashed when no inactive evidence existed

`KeyError: 'provenance'` — the inactive-evidence block assumed the state file
was always present. Fine for the 1PM slate, fatal on the first 4PM dry run.
It now emits `NO_OFFICIAL_INACTIVE_EVIDENCE` instead of dying.

### A4. "Identity unresolved" was filed as if the forecast were missing

The Ogletree case was recorded under `IDENTITY_UNRESOLVED` inside
`dk_universe_vs_emitted`, which reads as *"the model has nothing for this
player"*. Untrue: the run emits `00-0037292` in four layers at DK mean
1.0965. What could not be attached was his DraftKings **price**.

Those are different problems — no price is an optimiser problem, no forecast
is a football problem — and collapsing them turns a present projection into
an apparent hole. Split into `DK_SALARY_ROW_IDENTITY_UNRESOLVED`. Commit
`b50ca0a`.

### A5. A movement column keyed on the wrong field name

The market-movement block was written against a column called `change` while
the file uses `delta_status`. It returned `None` on every row **while still
emitting a movement section** — which reads as "nothing moved" when the truth
is "nothing was read". Fixed with a comment naming the failure mode.

### A6. Unreadable code shipped into a generator

The correlation table in `write_showdown_md.py` was written with a
`chr(109)+chr(101)+...` expression to dodge an f-string quoting problem. It
worked and it was garbage. Rewritten as two plain locals before commit.

---

## B. Defects found in pre-existing repo code

### B1. The inactive gate certified boards on which nothing was checked

**Severity: high — a governance gate that passes vacuously is worse than no
gate.**

`assert_no_inactive_in_playable` returned `PASS` with code
`0_OFFICIALLY_INACTIVE_PLAYERS_IN_PLAYABLE_BOARD` when the inactive map was
**empty**. With nothing to compare against, `survivors` is empty because no
comparison happened — not because the board was found clean.

The module's own docstring forbids exactly that collapse: *"an empty inactive
list and a verified-empty one are different facts"*. The 1PM slate never
reached the branch because it had real evidence; any slate whose inactives
have not published reaches it on **every call**.

Fix: returns `NO_OFFICIAL_INACTIVE_EVIDENCE` / `NOT_CERTIFIED`. The 1PM
audits were re-verified byte-identical afterwards.

### B2. `emit_package.py` hardcoded one slate

Runs glob, game list, market board, inactive state and output name were all
constants. Now environment-overridable with the 1PM values as defaults; the
1PM package was verified to reproduce its football board, DFS board and prop
rows identically, with three additive provenance keys.

### B3. The carry class has no positional or depth guard

The subject of the separate KC backfield diagnosis. `CLASSES['carries']['pos']`
is `('RB',)`; history enters the tier-conditional prior only through panel
rows whose **panel position** is in that class. Ben VanSumeren is carried as
`position RB` on the 2026 roster so he enters the rush pool, but **0 of his
10 panel rows** are in class (all labelled `LB`), so he draws a cold-start
default — one that sits near a lead back's workload. Kenneth Walker III, with
**67 of 67** in-class rows at a measured ~0.41 carry share, finished behind
him.

The captured `depth_chart_position` field is read elsewhere but is **not an
input to carry allocation**.

---

## C. Model findings that are defects, not noise

### C1. PHI@TEN emitted no skill-position layer at all, while reporting PASS

The run emitted **no** `receiving`, `rushing`, `rush_category`,
`rush_player_pool` or `gadget_rush` layer — six rows total, four QBs and two
kickers — while reporting `PASS` on appearance, participation,
targets_carries, conversion and td_layer. A stage reporting success while
emitting nothing is the most expensive defect class in this project.

`MIN@CHI` has a one-sided version: every CHI skill player carries only
`gadget_rush` keys and no `receiving` row, while MIN players carry both.

**The package disclosed this correctly** in
`audits.position_support_per_game` (`RB 0, TE 0, WR 0`). See F1 — I did not
read it.

### C2. Prop probabilities were overconfident and the book beat them

Week-2 grading, 263 graded markets over 7 games: mean predicted **0.6315**
against realised **0.5361**, a gap of **−0.0953** with a game-clustered SE of
**0.0419**. Brier 0.2494 vs the book's 0.2467; log loss 0.6917 vs 0.6865.
Both proper scores favour the market.

Clustering inflates the SE by **1.36×**. A naive SE would have overstated the
precision of that statement.

### C3. The UNDER lean is one bias repeated, not many signals

203 UNDER / 60 OVER on the graded board; 323/107 on the IND@KC board. Target
share concentration was **0.1588 projected vs 0.1889 realised** (+0.0301, SE
0.0133, t = 2.26 over 11 teams): the allocation is too diffuse. Team target
volume ran 16.8% short but at 0.8810 ± 0.0688 per team that is suggested, not
established. The two are confounded and must be tested apart.

### C4. What held, so it is not lost in the list

DK point projections: bias **−0.1088** against a clustered SE of 0.3697,
**r = 0.693**, and p90/p95 coverage **above** nominal rather than below. No
equivalence margin was predeclared, so that is a failure to detect bias, not
proof of its absence.

---

## D. Environment and infrastructure

### D1. The container clock jumped 3.5 hours mid-session

At one report the container read 16:44Z with uptime 37m; later it read
20:11Z with uptime 4h04m. Both readings are internally consistent, so real
time genuinely passed — but it meant **the 4:05 ET games had already kicked
off** while I was still reporting precompute status against a 3:35 ET target.

Verify the clock against uptime before trusting any deadline arithmetic.
The proxy strips `Date` headers, so an external HTTP timestamp is not
available as a cross-check.

### D2. A stale remote-tracking ref after a container restart

`origin/claude/...` read a commit from two days earlier. `git ls-remote` is
authoritative; corrected with `git update-ref`.

### D3. `pkill -f "run_forecast.py --season"` killed my own shell

Exit 144. The pattern matched the shell running it. Target PIDs explicitly.

### D4. Four processes launched in the same instant lost one game

In the 4PM smoke, JAX@DEN produced **no run directory at all** while the
other three completed. Run alone it completed every stage in 365 s. The
appearance stage materialises a content-addressed stage tree and simultaneous
cold creation is the plausible collision. A 5-second stagger between launches
costs nothing against a ~400 s run.

I first reported this as a possible game-level failure. It was my launch
pattern.

### D5. Concurrency was measured, not guessed

One run holds ~91% of **one** core and ~835 MB on a 4-core box. Serial
execution was leaving three cores idle. Four concurrent is saturation, not
oversubscription.

### D6. 87% of runtime is one stage

Per-stage on a real game: `appearance` **352 s of 405 s**, `player_draws`
50 s, everything else ~0. Serial execution was never the cost. I deliberately
did **not** touch it during a production window.

### D7. `ast.literal_eval` on `'b' * 64` raises, and a bare except hid it

`literal_eval` accepts `+`/`-` between numbers only. The raise was swallowed
by `except: continue`, and the audit reported a placeholder hash ABSENT while
it sat in the file.

### D8. An AST import check collected only `ImportFrom.module`

It reported `fixture_assembler` absent when it was imported as
`from x import fixture_assembler`. Fixed by also collecting
`f'{module}.{alias}'`.

### D9. No `pyarrow`

The canonical grading dataset is emitted as CSV + JSONL instead of parquet.
Same rows, same columns, stated in the summary rather than silently
substituted.

### D10. Egress is narrow but not closed

`nfl.com`, `rotowire.com`, ESPN and `api.weather.gov` all fail. **GitHub is
reachable**, and with it the nflverse data releases — play-by-play, weekly
player stats, snap counts, rosters, depth charts. The governed capture tool
still reports `official_inactives: NO_EGRESS` and
`official_injury_report: NO_EGRESS`.

### D11. nflverse asset gotchas

* `releases/download/player_stats/<file>` **404s**. The working weekly asset
  is `releases/download/stats_player/stats_player_week_2026.csv`.
* The `pass` flag is a **dropback** flag: 1 on sacks *and* on QB scrambles,
  with `rush` 0 on scrambles. Counting carries from the `rush` flag silently
  loses every scramble. Count `play_type == "run"`.
* Filter `season_type == "REG"` and drop `no_play` rows; penalty rows carry
  player names and inflate usage.
* pbp files are rewritten in place as games finish, so an unpinned
  re-download is a different input.

### D12. `panel_enriched.pkl` is gitignored

`nfl/research/p4b/panel_enriched.pkl` is not in the checkout. It is staged at
runtime into `/tmp/nfl-p4c-*`, which is why runs succeed and a direct
`load_panel()` from the repo does not.

---

## E. Evidence and data availability

### E1. Sunday snap counts were not published in time

`snap_counts_2026` week 2 covered **only** `2026_02_DET_BUF`. So
`OUTCOME_INTERPRETATION` reads `NORMAL` on every graded row with the basis
stated, and the injury-filtered calibration view is reported
`NOT_YET_COMPUTABLE` rather than silently equal to the unfiltered one.

### E2. CLE@TB results were not published at grading time

7 of 8 games graded. The eighth is `GAME_RESULT_NOT_PUBLISHED` and excluded
from every metric rather than scored as losses.

### E3. No closing-line board exists for Week 2

The 16:35Z capture **is** the frozen comparison snapshot and no later one was
taken, so CLV is not computable. Capture a near-kickoff board next week.

### E4. The submitted 73-lineup entry set was never written here

The lineup half of the DFS postmortem — stacks, bring-backs, salary used,
overlap, exposures — is **not computable**. Nothing was estimated. One file
would unblock it: eight roster slots per lineup by DK player id, plus contest.

### E5. Inputs the owner had to supply, which I cannot fetch

A 4PM Hard Rock board, a 4PM DraftKings salary file, and official inactives.
Without them the prop section emits `NO_MARKET_BOARD_SUPPLIED_FOR_SLATE` by
name and the board is not inactive-certified.

### E6. An alias that cannot be verified cleanly

DraftKings lists **"Drew Ogletree"**; the roster vintage carries
`full_name: "Andrew Ogletree"` and `football_name: "Andrew"`. Neither field
contains "Drew". No edit-distance matching is permitted, so it stays
unresolved. Non-core: DK mean 1.0965, p95 6.6, third among IND tight ends.

### E7. The inactive evidence tier was a screenshot, not official bytes

Recorded as `OWNER_SUPPLIED_SCREENSHOT_OF_GAME_PAGE` with `governing: true`
and `is_official_nfl_bytes: false`. Applied in full; only the tier is stated
accurately rather than upgraded.

### E8. `pbp_participation_2026` is 404

Not published. `pbp_participation_2025` returns 200/49 MB, which proves the
path and reachability rather than leaving it ambiguous.

---

## F. Reporting errors — mine, to the owner

### F1. I delivered a board missing a game's skill players and called it complete

**The most consequential mistake of the session**, because that board went
downstream to build lineups.

I reported the 7-game and 8-game packages by **row totals only** and did not
read `audits.position_support_per_game`. `PHI@TEN` showed `RB 0, TE 0, WR 0`.
The artifact was honest; my summary of it was not.

Lesson: a package that carries its own coverage audit is worth nothing if the
delivery note quotes the row count instead.

### F2. I reported a smoke-test "failure" that was my own launch pattern

See D4. JAX@DEN was healthy.

### F3. I reported precompute progress against a deadline that had passed

See D1. The 4:05 games had kicked off.

### F4. An original Early Only audit missed `dry_run` and a placeholder hash

I reported the sealing refusal and a 13.5 h staleness but never read the
runs' own status files. All 15 carried `dry_run: true`,
`prospective_eligible: false`, and `run_slate.py` satisfied
`capture_validation` with a literal `'b' * 64` placeholder.

### F5. A hypothesis I held and withdrew

That Walker was suppressed as a cross-team acquisition (SEA → KC).
`f_team_change` is set, but his in-class history is complete and his measured
share is high. The cold-start account explains the inversion without it.

---

## G. Still open

| # | Item | State |
|---|---|---|
| G1 | PHI@TEN / MIN@CHI missing skill layers | **Root cause not found.** Fix before further calibration work — it silently removes teams from every aggregate |
| G2 | KCB-1 depth-chart-conditional cold start | Designed, pre-registration written, **not run** |
| G3 | `appearance` at 87% of runtime | Real target, wrong week. Not a production-window change |
| G4 | Injury-filtered calibration view | Blocked on the participation feed (E1) |
| G5 | CLV | Blocked on a near-kickoff capture (E3) |
| G6 | DFS portfolio postmortem | Blocked on the entry set (E4) |
| G7 | `Davon Booth` | **Not inactive.** Active and unsupported by the model — a coverage gap, and he sits in every row of the owner's saved entry template |
| G8 | Board remains UNSEALED | `denom_panel`, `team_volume_history`. Every run stops at `artifact_sealing` |

---

## The pattern worth keeping

Most of section A and all of B1 are **one failure mode**: a step that
returned nothing, or something partial, read as success. A guessed key
returning `None`. An empty comparison returning `PASS`. A movement block
built on a column that does not exist. A gate that only fires where evidence
already exists.

The generalising fix is not more review. It is that every stage asserts its
output is non-empty and schema-correct before returning, and raises a
**named** error otherwise — and that the delivery note quotes the gate, not
the row count.

`CANDIDATE_NOT_ACCEPTED_BASELINE`. **V2 NOT YET EARNED.**
