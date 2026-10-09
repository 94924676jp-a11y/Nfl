# Week 5 role-change review: CIN, WAS, PIT (owner Decision 1, 2026-10-09)

The tie-order repair (`39340321`, `a8efedae`) is **provisionally retained, with a rollback path**: revert those two
commits. This review checks the players the repair moved against football evidence rather than the depth chart alone.

**Usage source:** pregame 2026 play-by-play, retrieved 2026-10-07 (`nfl/research/postgame/pbp_2026.2b3e9f2c6f92123f.csv.gz`,
weeks 1–4), plus the snap-count capture. Computed table: `research_projection/W5_ROLE_REVIEW_USAGE.json`.
Route data is **not available** in this repository (no participation or route feed is captured), so route
participation is UNKNOWN, not inferred.

## Before / after / research (DK points, band / ceiling, P(plays))

| Player | Before repair | After repair (production) | RC-1 research | FC | Availability (OFFICIAL practice) |
|---|---|---|---|---|---|
| Ja'Marr Chase | 14.81 SECONDARY / SECONDARY, p 0.861 | **18.70** ALPHA / ALPHA, p 1.0 | 18.03 | 23.47 | **Limited, concussion** (SECONDARY: in protocol, needs a full practice) |
| Tee Higgins | 21.09 ALPHA / ALPHA, p 1.0 | **16.77** SECONDARY / SECONDARY, p 0.861 | 17.46 | 17.14 | DNP Wednesday, Limited Thursday |
| Terry McLaurin | 9.82 SECONDARY, p 0.861 | **13.77** ALPHA, p 1.0 | 13.25 | 13.22 | **DNP Wed and Thu** (hamstring; missed W4) |
| Stefon Diggs | 14.70 ALPHA, p 1.0 | **11.74** SECONDARY, p 0.861 | 11.52 | 12.04 | **DNP Wed and Thu** (official); SECONDARY sources conflict |
| Pat Freiermuth | 10.49 ALPHA, p 1.0 | 10.49 (unchanged; TE usage-first) | n/a* | 8.74 | not on the report |
| Darnell Washington | 3.99 SECONDARY, p 0.579 | 3.99 (unchanged) | n/a* | 7.33 | not on the report |

\* The RC-1 arm ran before the tight-end follow-up, so its PIT numbers reflect the superseded chart-first order and are
not comparable.

## Football evidence, weeks 1–4

**CIN.** In the weeks both were healthy (W1–W3):

| | Targets | Target share by week | Air yards | Snaps |
|---|---|---|---|---|
| Chase | 25 | 0.11 / 0.29 / 0.32 | 214 | 88–100% |
| Higgins | 23 | 0.17 / 0.32 / 0.19 | 302 | 72–93% |

In W4, Chase left with the concussion after 20% of snaps, and Higgins took 16 targets (0.30).

**Verdict: the ordering is defensible, but both numbers are unreliable.** Chase's healthy-week share edges Higgins's,
so Chase first is consistent with the evidence. But these are co-starters, and two defects distort the pair:

1. **Higgins is capped as a backup.** The WR2 ceiling (RC-1, research) and the club-slot P(plays) of 0.861 (W5-G16)
   both apply to him, though he played every week at 72–93% of snaps.
2. **Chase's real availability risk is not represented.** He is limited with a concussion, yet carries P(plays) 1.0.

The engine puts the availability discount on the wrong player.

**Scenario, Chase out:** Higgins **25.07**, Gesicki +1.9, Chase Brown +1.0, Meyers +3.1. Higgins's jump is
partly the slot mechanics: at rank 1 his P(plays) goes 0.861 → 1.0 and his ceiling SECONDARY → ALPHA.

**WAS.**

| | Healthy-week target share | Snaps |
|---|---|---|
| McLaurin (W2–W3) | 0.26, 0.29 | — |
| Diggs (W1–W4) | 0.27, 0.17, 0.23, 0.24 | 51–66% |

Antonio Williams rose to 0.22 in W4, when McLaurin was out.

**Verdict: unreliable until the Friday designations.** On healthy-role evidence, McLaurin first is defensible. Both
receivers missed Wednesday and Thursday practice, and McLaurin missed W4 with the same hamstring. Availability, not
ordering, decides these numbers.

| Scenario | Effect |
|---|---|
| McLaurin out | Diggs **16.48**, A. Williams +3.7, Burks +2.3 |
| Diggs out | McLaurin **15.91**, A. Williams +4.0 |

**PIT TE.**

| | Target share | Snaps |
|---|---|---|
| Freiermuth | 0.12 every week | 60–75% |
| Washington | 0.05, 0.05, 0.12, 0.12 | 53–76% |

**Verdict: supported.** Usage-first for tight ends keeps the receiving TE first, and production is unchanged from
before the repair.

## What this means for Sunday

- The repair removed an arbitrary choice. It did **not** fix the WR2 cap or the slot-based P(plays), which together
  produce swings of 4–8 points when a player moves between rank 1 and rank 2.
- Treat **Chase, Higgins, McLaurin and Diggs as provisional**:
  - read each with its scenario;
  - confirm with the Friday designation and Sunday inactives.
- Freiermuth and Washington stand.
- RC-1 (position-aware ceiling) and AP-1 (player appearance history) stay preregistered prospective candidates.
  Neither is applied for Sunday.
