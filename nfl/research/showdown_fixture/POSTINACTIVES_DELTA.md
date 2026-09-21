# Post-inactives refresh, NYG@LAR, 2026-09-21T23:05Z

Official inactives applied: **13 of 13 resolved**, 0 unresolved, 0 ambiguous.
Resolution is declared suffix-strip (Jr/Sr/II/III/IV/V) plus exact surname,
club and first initial. **No edit-distance matching.** `T. Fidone` failed the
first pass because the roster surname token is the suffix `II`; that is a
suffix rule, not a similarity guess, and it is declared.

Evidence tier: **OWNER_SUPPLIED_SCREENSHOT**. No URL, no publisher retrieval
timestamp, no content hash of a fetched page. Recorded at its true tier. The
network-capable agent holds `official_inactives`.

## What changed

| | Pre | Post |
|---|---|---|
| Credible-workload players | 22 | **21** |
| Candidate lineups | 12 | 12 |
| Lineups identical | — | **YES** |

Exactly one player left the credible pool: **Puka Nacua**, $11,400. The other
twelve inactives were already outside it — Fidone, Daniels, Simpson and
Whittington as ROLE_UNCERTAIN or ROLE_UNSUPPORTED, the rest defensive or
offensive line and never in the skill universe.

## The finding is that nothing changed, and that is wrong

The twelve lineups are **byte-identical** before and after the news. Nacua
never appeared in them (his median was 2.20, below the seed pool cut), so
removing him moved nothing.

That is not the board absorbing the news correctly. It is the board being
**unable to absorb it at all**, because the draws are frozen from a simulation
run while Nacua was still in the game. Deleting a row from a completed
simulation does not redistribute what that row was holding.

The evidence is on the two players the news actually promoted:

| Listed LAR WR starter | Median DK points | P(zero opportunity) | Role |
|---|---|---|---|
| Davante Adams | 9.50 | 0.054 | STARTER |
| **Konata Mumpfield** | **0.00** | 0.416 | SECONDARY_ROTATION |
| **Xavier Smith** | **0.50** | 0.463 | SECONDARY_ROTATION |

Mumpfield and Smith are on the official starting lineup. The frozen draws give
them a median of zero and half a point, because they were simulated behind
Nacua. A DFS board built on these numbers would be most wrong in exactly the
place the news moved.

**The correct response to an inactive is to re-simulate, not to filter.**
`allocation.assert_redistribution_supported` already refuses the shortcut: it
returns REDISTRIBUTION_UNSUPPORTED because no validated model says where a
departed player's opportunity goes. That gate was built for this case and it
is doing its job here.

## Why Nacua's 0.498 was not a defect, contrary to what I reported earlier

I recorded P(zero opportunity) = 0.498 as a model anomaly. It was not.
The lawful injury vintage carries him:

    Puka Nacua  report_status='Questionable'  practice='Did Not Participate'  injury='Hip'

A Questionable, did-not-practice player is close to a coin flip on appearing,
and the availability layer encoding that is the layer working. I called it a
defect without reading the designation first. Jordan Whittington was
`Doubtful / DNP / Quadricep` in the same vintage and the role engine had
already flagged him INJURY_CONTRADICTS_ROLE.

The Tyrone Tracy anomaly stands and is unexplained: 3% measured snap share,
BACKUP role, and the fifth-highest median in the pool at 8.00, above the
listed starter Cam Skattebo at 6.10. That is an ordering inversion of the kind
`nonqb/role_invariants.py` exists to catch.

## Gate state after the refresh

Unchanged and correctly so. Every scope reads RESEARCH_ONLY with 0 usable
entities, because no gate has been evaluated. The draws remain from a run
REFUSED at `artifact_sealing` on `current_season_input_freshness`.

Nothing here is a projection, a recommendation or a wager.
