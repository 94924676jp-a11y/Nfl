# Early Only pre-lock verdict — 2026-09-20, 1:00 PM ET slate

**STOP CONDITION REACHED. No upload-ready portfolio may be produced today.**

The controlling condition is the owner's own: *"Do NOT create an upload-ready
portfolio if SUN-5 remains unresolved… required players are unsupported… DST
cannot be modeled legitimately."* All three hold, and a fourth blocker that
was not on the list turned out to cost the most.

---

## The blocker that matters most, and it was not SUN-5

The real non-dry production run exposed it. **`participation_prior` refuses
`PARTICIPATION_HISTORY_STALE`**, and that refusal propagates to five stages:

| stage | state |
|---|---|
| appearance | `NOT_APPLICABLE[SLATE_FITS_UNAVAILABLE]` |
| participation | `NOT_APPLICABLE[SLATE_FITS_UNAVAILABLE]` |
| targets_carries | `NOT_APPLICABLE[SLATE_FITS_UNAVAILABLE]` |
| conversion | `NOT_APPLICABLE[SLATE_FITS_UNAVAILABLE]` |
| td_layer | `NOT_APPLICABLE[SLATE_FITS_UNAVAILABLE]` |

**Consequence, measured from the emitted draws:** the board carries
`qb`, `kicking`, `rushing_total`, `team_volume` and `dk_scoring` — and
**no `receiving` layer and no per-player `rushing` layer at all.** 8 QB rows
and 2 kicker rows per game.

**There are no RB, WR or TE distributions.** A DraftKings Classic lineup needs
two RBs, three WRs, a TE and a FLEX. Seven of nine roster slots have no
modelled player behind them. That is the `required players are unsupported`
stop condition, and it is not close.

Root cause: `pbp_participation_2026` has never been captured, and `pass_snaps`
needs per-play on-field presence. `offense_players`, `offense_personnel`,
`defense_players` and `n_offense` are all absent from the play-by-play —
checked, not assumed.

`nfl/production/nonqb/panel_2026w1.py` exists and would inject 2026 week-1
rows, but it is **`R9_W1P only`**, it is not in R8, and it says of itself that
`pass_snaps` is APPROXIMATED as `offense_snaps × (team_dropbacks /
team_offense_plays)` and is *"systematically wrong for exactly the players it
matters for: a blocking tight end and an early-down back are over-credited…
a third-down back and a slot receiver under-credited."* The candidate registry
is explicit that running it under the accepted name would be *"the accepted arm
impersonated by an approximation."*

---

## PHASE 1 — SUN-5, answered per input

Raw 2026 week-1 evidence **does exist in governed captures.** It is not enough.

### `panel_p3`

| question | answer |
|---|---|
| upstream raw sources | `pbp` (governed vintage), `snap_counts` (availability store) |
| week-1 2026 evidence exists? | **YES** — `pbp_2026.b69f55a172965e16.csv.gz`, 16 games, 32 clubs, 372 columns, PASS in the manifest |
| transformation code exists? | **YES** — `nonqb/current_season_panel.rows_before` |
| regenerable lawfully now? | **YES, and I did.** 37 rows at ordinal **202601**, 32 of 32 clubs |
| spec change or materialisation? | **Materialisation** of declared data — *except* that consuming it requires the `CS1` component, which is declared only in `V1_CANDIDATE_R9_W1P_GSVUC` and `GSVUCY` and **not in R8, the accepted baseline.** Adding CS1 to R8 is a specification change to a frozen accepted arm and was not done. |

**Repair made:** the panel was reading the smaller of two stores. It considered
only `nfl/research/postgame/pbp_*.csv.gz` (10 and 2 games) and skipped the
governed 16-game vintage capture, because that one's provenance lives in the
manifest rather than a sidecar. DEN and KC were reported as clubs with no
current-season evidence; they have 32 and 29 dropbacks in the governed capture.
Both stores are considered now, widest **lawful** wins, clock unchanged.

### `denom_panel`

| question | answer |
|---|---|
| upstream raw sources | `panel_p3.csv` → `research/p4b/mk_denom.py` → `denom_panel.csv.gz`; needs `snap_counts` for `offense_snaps`/`offense_pct` |
| week-1 2026 evidence exists? | **PARTIALLY.** `snap_counts_2026`: **15 of 16 games, 30 of 32 clubs.** `2026_01_DEN_KC` absent |
| transformation code exists? | YES |
| regenerable lawfully now? | **NO** |
| spec change or materialisation? | **Would be a specification change.** It carries `declared_blocked: CURRENT_SEASON_SOURCE_UNVERIFIED` |

The declaration states its own precondition: the 2026 source's *"vintage,
completeness, coverage, field definitions and identity behaviour"* must be
established. Measured today:

| property | `pbp_2026` | `snap_counts_2026` |
|---|---|---|
| vintage | ✅ manifest PASS, capture id, `retrieved_at` | ✅ content-addressed, `first_retrieved_at` |
| completeness | ✅ 16 of 16 games | ❌ **15 of 16** |
| coverage | ✅ 32 of 32 clubs | ❌ **30 of 32** |
| field definitions | ✅ 372 columns, header identical to the 2025 capture | ❓ **uncheckable — no historical snap capture exists in this repository** |
| identity behaviour | ✅ **314 of 314** ids join the canonical roster | ✅ 0 bridge failures reported on week 1 |

Two properties fail and one cannot be checked. **The declared block stands on
measurement, not on the clock running out.** Lifting it would have been editing
a governance declaration whose stated precondition is unmet.

### `team_volume_history`

Same file, same blocker. Newest ordinal 202518 because `denom_panel.csv.gz` has
zero 2026 rows, and regenerating it requires the above.

---

## PHASE 2 — SUN-6 `feature_build`

**Not implemented, deliberately, and it would not have helped.**

- `feature_build` is `DEFERRED`, not `BLOCKED`. It does **not** halt the run.
  Sealing refuses on `current_season_input_freshness` alone.
- The "accepted research specification" is the string
  `'prior-only, ordinal prefix cut'` at `run_forecast.py:1940`. Searched the
  tree: **there is no frozen specification document for it.** Implementing from
  a one-line label is inventing a model layer, which the directive forbids and
  which a deadline does not license.

---

## PHASE 3 — FIX-ROSTER-GLOB ✅ **DONE**

`run_slate.roster()` globbed `weekly_rosters.*.reduced.csv.gz` and kept
whichever file held the **most rows**. Row count and glob order are two of the
five inputs `vintage_selector` names as FORBIDDEN for choosing a vintage.

It now reads the blob the run **declares**, via `fixture_assembler`. A caller
with no run cut is **refused** (`ROSTER_CUT_REQUIRED`) rather than handed a
glob — there is no lawful vintage without an instant to be lawful at.

`test_roster_vintage_selection` (12 checks) proves the old path is gone **by
AST rather than grep**, because a glob assembled from parts survives a text
search. It also proves the cut moves the answer: at a 2026-09-12 cut the
selector takes `weekly_rosters.fb79560b5c4738a2`, at the live cut
`weekly_rosters.8bcf6ee6af93cc8b`. The glob would have taken the larger file at
either cut and said nothing.

---

## PHASE 4 — official inactives

**Path ready. Bytes not published.**

Newest `official_inactives` PASS capture is `20260917T234100Z` — Thursday's
DET@BUF. Nothing for the 1 PM Sunday games exists yet; inactives publish around
T-90, roughly **2026-09-20T15:30Z**. The ingestion path is proven (402 PASS
captures) and needs network, which this executor does not have. Assigned, not
blocked — see the outbox.

Ingestion would be append-only with provenance, both teams, raw bytes
preserved, and **no ACTIVE inferred from omission.** Redistribution would run
through the football model, never by adding points to beneficiaries. None of
that can start until the bytes exist.

---

## PHASE 5 — DST, classified against what the engine emits

| DK DST scoring component | classification | evidence |
|---|---|---|
| sacks | **`DERIVABLE_FROM_EXISTING_WORLD`** | `qb__sacks` exists per world per QB; sum the opposing QBs |
| interceptions | **`DERIVABLE_FROM_EXISTING_WORLD`** | `qb__int` exists per world per QB |
| fumble recoveries | `REQUIRES_NEW_FOOTBALL_LAYER` | `NOT_SIMULATED: fumbles_lost` — no fumble model |
| defensive touchdowns | `REQUIRES_NEW_FOOTBALL_LAYER` | not simulated |
| return touchdowns | `REQUIRES_NEW_FOOTBALL_LAYER` | `NOT_SIMULATED: return_td` — no return model |
| safeties | `REQUIRES_NEW_FOOTBALL_LAYER` | not simulated |
| **points allowed** | **`UNAVAILABLE`** | the engine produces **no score at all**. `scenarios.py`: *"no score, no margin, no win probability and no drive outcome"* |

Points allowed is the largest DST scoring term, and it is not merely missing a
layer — the simulation produces no scoreboard for a ladder to read. The DK
points-allowed tier boundaries are also part of the Classic contract this
repository does not hold (OUT-025).

**No legitimate DST layer can be completed before lock.** Two of seven
components are derivable; the dominant one is unavailable. Nothing was
manufactured to make lineups legal.

---

## PHASES 6–12 — not started, and correctly so

DK Classic contract, `CLASSIC_PORTFOLIO_BRIDGE_V1`, the 73-lineup portfolio and
the upload CSV are all barred by the stop conditions above. Building any of
them would mean emitting lineups for seven roster slots that have no modelled
player behind them, with a fabricated DST.

---

## What was completed

| item | state |
|---|---|
| Owner entry file preserved | ✅ byte-identical, mode 444. **73 entries, 73 unique Entry IDs**, 3 contests. sha256 `d89da321…350be4d05` |
| DK-3 / DK-4 (earlier today) | ✅ first slate run with `bytes_verified: true` |
| Eight-game non-dry production run | ✅ 8,000 draws each, `DECLARED_BYTES_VERIFIED_AGAINST_VINTAGE_MANIFEST` |
| `current_season_panel` store repair | ✅ 30 → **32 clubs**, ordinal 202601 |
| FIX-ROSTER-GLOB | ✅ done, proven by AST test |
| SUN-5 five-property verification | ✅ measured; two fail, one uncheckable |
| DST inventory | ✅ classified |

## What is needed, in order

1. **`pbp_participation_2026`** — the single named missing input behind the
   non-QB chain. Network; assigned.
2. **`snap_counts_2026` refreshed to 16 games** — `2026_01_DEN_KC` only.
   Network; assigned. This is a stale watch, not a missing source.
3. Official 1 PM inactives at ~T-90. Network; assigned.
4. A decision on whether CS1 and the 2026 week-1 panel enter the **accepted**
   arm. That is an owner ruling about a frozen specification, not an
   engineering call, and not one to take against a clock.

**V2 NOT YET EARNED**
