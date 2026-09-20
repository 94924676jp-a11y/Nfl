# 1 PM inactives window — what arrived, what did not, and the verdict

Window opened ~15:30Z. This record written 16:12Z. Lock 17:00Z.

## Headline

**`RB_WR_TE_PLAYER_DISTRIBUTIONS_STILL_UNAVAILABLE`**

Tested, not assumed. Re-ran `2026_02_CAR_ATL` after the snap refresh at
`written_at 2026-09-20T15:55:00Z`, run `562697d7ef6ad42d`. Layers emitted:
`dk_scoring`, `kicking`, `qb`, `rushing_total`, `team_volume`. **No
`receiving` layer. No per-player `rushing` layer.**

**Exact blocker:** `participation_prior` → `BLOCKED[PARTICIPATION_HISTORY_STALE]`
→ propagates to appearance, participation, targets_carries, conversion,
td_layer as `NOT_APPLICABLE[SLATE_FITS_UNAVAILABLE]`.

The refusal condition, read out of the source rather than inferred:

```python
if week >= 2 and (newest is None or newest < season * 100):
    ... 'pbp_participation_{season} is the missing input.'
```

## Egress: measured, and it decided the window

| host | result |
|---|---|
| `www.nfl.com` | **403 at the CONNECT tunnel** — unreachable |
| `www.rotowire.com` | **403 at the CONNECT tunnel** — unreachable |
| `github.com` (nflverse) | **reachable** — real HTTP statuses returned |

This is why one OUT-032 item was discharged and two were not.

## OUT-032, item by item

### 1. `pbp_participation_2026` — **ANSWERED, AND IT IS A NEGATIVE**

| URL | status |
|---|---|
| `…/pbp_participation/pbp_participation_2026.csv` | **404**, 9-byte body |
| `…/pbp_participation/pbp_participation_2025.csv` | **200**, 49,094,943 bytes |

Same path, same executor, same release channel. The 2026 file **is not
published**. This is not a capture gap and no retry changes it. It is the
single named missing input behind the RB/WR/TE blocker.

### 2. `snap_counts_2026` — **DISCHARGED ✅**

Captured through the governed availability watch, `20260920T155133Z`.

| | held before | captured now |
|---|---|---|
| bytes | 125,550 | **142,445** |
| rows | 1,397 | **1,585** |
| games | 15 | **17** |
| clubs | 30 | **32** |
| `2026_01_DEN_KC` | absent | **present** |

Week split: 1,492 rows week 1 (16 of 16 games), 93 rows week 2
(`2026_02_DET_BUF`, Thursday, already played). Blob content-addressed,
append-only, first-seen sidecar not restamped.

**What it fixed:** two of `denom_panel`'s five declared preconditions.
Completeness is now 16 of 16 week-1 games and coverage 32 of 32 clubs.

**What it did not fix:** anything downstream, measured above. Snap counts carry
`offense_snaps` and `offense_pct`; they do not carry per-play on-field
presence, which is what `pass_snaps` needs. The third precondition — field
definitions checked against a prior season — remains uncheckable, because no
historical snap capture exists anywhere in this repository.

### 3. Official 1 PM inactives — **NOT RETRIEVABLE HERE**

`official_inactives` is `https://www.nfl.com/inactives/`, and that host is 403
at the tunnel. No capture on any remote branch is newer than `20260917T234100Z`
— Thursday's DET@BUF. **Assigned, not blocked for both.**

RotoWire was not used and could not have been: it is also 403, and the
directive is explicit that it is discovery and corroboration only, never
governing. **No inactive status was inferred from any secondary source, and no
ACTIVE was inferred from omission.**

## Per game — the eight 1 PM games

The ingestion-then-rerun sequence never became applicable, because no official
inactive evidence arrived for any of the eight. Nothing was ingested, so
nothing was appended to the vintage and no older evidence was touched.

| field | PHI@TEN · PIT@NE · MIN@CHI · CAR@ATL · GB@NYJ · NO@BAL · CIN@HOU · CLE@TB |
|---|---|
| official inactive evidence source | **none retrieved** — host 403 |
| raw hash | n/a |
| retrieval / publication clocks | n/a |
| inactive players | **unknown, and left unknown** |
| identity reconciliation | n/a |
| expected starter/role change | **not determinable** |
| opportunity redistributed | **no** — nothing ingested, nothing to redistribute |
| pipeline status | REFUSED |
| first blocker | `participation_prior[PARTICIPATION_HISTORY_STALE]` at `appearance` |
| **QB distributions** | **YES** — `qb`: att, cmp, db, int, ptd, pyds, rtd, rush_opp, ryds, sacks, scr |
| **RB distributions** | **NO** |
| **WR distributions** | **NO** |
| **TE distributions** | **NO** |
| **DST** | **remains unsupported** — engine emits no team-defence outputs |

Kicker distributions exist (`kicking`, distance-bucketed). DraftKings Classic
does not roster a kicker.

One game was re-run as the probe rather than all eight. The blocker is a
league-wide participation-panel staleness that is upstream of, and identical
for, every game; eight runs at 8,000 draws would have produced eight identical
stage verdicts and consumed the window. The freshness verdict is unchanged on
all three inputs: `denom_panel` `CURRENT_SEASON_SOURCE_UNVERIFIED`, `panel_p3`
and `team_volume_history` `CURRENT_SEASON_INPUT_STALE`, all at newest ordinal
**202518**.

## Stop conditions — every one of them still fires

| condition | state |
|---|---|
| RB/WR/TE unsupported | **FIRES** — measured above |
| denominator / current-season freshness blocks the board | **FIRES** — 3 inputs, 202518 |
| DST illegitimate | **FIRES** — points allowed `UNAVAILABLE`, no scoreboard |
| Classic legality uncertifiable | **FIRES** — no `DRAFTKINGS_CLASSIC` contract (OUT-025) |
| any lineup would need a third-party or fabricated projection | **FIRES** — seven of nine slots |

**No portfolio was generated. The owner's 73 Entry IDs are untouched.**

## Completed in this window

- Egress boundary measured rather than assumed — three hosts, three results.
- `snap_counts_2026` refreshed and captured through the governed path;
  32 of 32 clubs, DEN-KC recovered.
- `pbp_participation_2026` established as **not published**, with the 2025
  control proving the path and the reachability.
- The RB/WR/TE blocker **re-tested after the refresh** and confirmed unmoved.
- Owner entry file still byte-identical, mode 444, sha256
  `d89da321…350be4d05`. 73 entries, 73 unique Entry IDs.

## What would change the answer

One thing, and it is not in this repository's gift: **`pbp_participation_2026`
being published**, or an owner ruling that the `R9_W1P` 2026 week-1 panel —
whose `pass_snaps` is an approximation its own module calls *"systematically
wrong for exactly the players it matters for"* — may enter the accepted arm.

The second is a decision about a frozen specification. It is not one to take
against a clock, and forty-eight minutes before lock is the worst moment
anyone will ever have to take it.

**V2 NOT YET EARNED**
