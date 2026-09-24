# Why the engine cannot rank a 10-entry portfolio tonight, quantified

**Date:** 2026-09-24, against the live DK Showdown $4K Dime Package,
ATL @ GB, ~47,562 entries, 10 of 20 max entered, lock ~00:15Z.
**This is a measurement, not a hedge.** It is the number that decides whether
the directive's objective can be served today.

## The mean survives the correlation gap. The tail does not.

A Showdown lineup's score is the sum of six correlated contributions. The
draws declare `INDEPENDENT_STREAMS_COLUMN_ALIGNED`, so every covariance term
is modelled as zero. To size what that costs, the same five modelled players
were summed twice from the **same marginal draws**, changing only the
dependence structure — column-aligned (independent) against comonotonic
(each player's draws sorted, i.e. perfect rank coupling):

| | mean | sd | p50 | p90 | p95 | p99 | max |
|---|---|---|---|---|---|---|---|
| independent | 64.36 | 22.91 | 62.8 | 94.7 | 104.5 | 125.2 | 193.9 |
| comonotonic | 64.36 | 47.34 | 52.5 | 131.9 | 157.8 | 209.9 | 372.9 |

**The mean is identical to the cent, and it must be** — dependence cannot move
the expectation of a sum. Everything else moves enormously:

| quantity | independent -> comonotonic |
|---|---|
| p90 | 94.7 -> 131.9 (**+39.3%**) |
| p95 | 104.5 -> 157.8 (**+51.1%**) |
| p99 | 125.2 -> 209.9 (**+67.7%**) |
| sd | 22.91 -> 47.34 (**+106.7%**) |

Comonotonic is an extreme upper bound, not an estimate — real same-game
correlation is positive but nowhere near perfect. The true ceiling sits
somewhere inside that bracket, and **the modelled value sits at the bottom of
it**. At p99 the bracket spans a factor of 1.68.

## What that licenses and what it forbids

**Licensed today.** Relative comparison by mean or median. Those are robust to
the dependence gap because the gap does not touch them. Per-player marginals,
salary and identity integrity, availability risk.

**Forbidden today.** Any ranking that depends on ceiling, tail, stacking value,
"probability this lineup is optimal", or portfolio-level P(one of ten wins).
Every one of those is a function of the covariance the artifact sets to zero
and whose true value is bracketed above by a factor approaching two. Ranking
ten lineups on that is not a close call.

Which is exactly what the directive's own honesty clause says: *"Do not claim
exact lineup-winning probabilities unless the joint simulation semantics
support that claim."* They do not.

## Two findings about the live contest, from tonight's actual entry

**1. A player in the lineup is not in our universe at all.** The entered
lineup carries `P. Strong Jr.` in a FLEX slot. Pierre Strong (GB, RB,
`00-0038098`) appears in our truth snapshot with roster status **DEV**,
`on_depth_chart: false`, and he is **absent from every one of the ten draw
layers**. The engine has no projection for him — not a small one, none. He is
also absent from all 958 rows of the DK week-3 salary file captured at
13:34Z today, so DK added him to the pool after our snapshot, which is what a
practice-squad elevation looks like.

So one of six slots is a player the model deliberately excluded (the
`active_roster_only` filter holding a DEV player is correct behaviour) and
which the live contest has priced and made available. **Our DFS player
universe is stale against the live contest**, and nothing in the pipeline
noticed.

**2. The Captain abbreviation is ambiguous in a way that matters.** DK renders
`B. Robinson`, and Atlanta rosters two: Bijan Robinson (CPT $17,700) and Brian
Robinson (CPT $6,600). The salary arithmetic implies Bijan — the other four
modelled players cost $31,400, and only the Bijan construction leaves a
min-salary slot for a late elevation — but that is an inference from price,
not a read of the entry. A DFS system must resolve this from the contest
export, never from a rendered abbreviation.

**3. A third of the lineup's slots carry unresolved availability.** Michael
Penix Jr. has P(any modelled opportunity) = 0.327 and an unconditional mean of
4.63 DK points against 14.16 conditional on playing. For DFS the
**unconditional number is the correct one** — an inactive player scores zero,
so the 4.63 already integrates over the two-in-three chance he contributes
nothing. That is a genuine leverage construction if he starts and a dead slot
if he does not, and the official inactive list that resolves it publishes
around 22:45Z, roughly 90 minutes before lock.

## What this makes the roadmap

B3 (minimal shared-football-world candidate) is no longer an architectural
option; it is the gating dependency of the DFS product, because the quantity
the directive optimises is the one the current generator cannot express. C4
(ownership, field, duplication) is the second gate. Until both exist, the
honest DFS deliverable is marginals, integrity and availability risk — real
and worth shipping, and never to be presented as a portfolio ranked by win
probability.
