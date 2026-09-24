# Owner product directive — DFS / Showdown philosophy

**Issued 2026-09-24 by the owner. Governing spec for the whole DFS side.**
Recorded verbatim in substance because it is a product philosophy, not a
lineup-generation instruction, and it must outlive any one session.

## The north star

> Don't optimize the lineup. Optimize the chance that one of our entries wins.

## The objective, stated exactly

> Select the 10 legal lineups that give my 10-entry portfolio the strongest
> modeled chance of producing a tournament-winning outcome in this specific
> contest.

Projection is an INPUT, not the objective. The highest-projected lineup may
also be the best tournament lineup — especially in a one-game Showdown — but
that must be an **outcome of the full decision process, not the objective
itself**.

The target is not "what are the 10 highest median projections". The target is
"if I only have 10 bullets, which 10 lineups give me the strongest
portfolio-level chance of winning this tournament".

## What the decision process must weigh

ceiling and extreme-tail outcomes · Captain leverage · ownership · duplication
risk · salary construction · likely field behaviour · game-script diversity ·
role uncertainty · correlation **only where supported by valid model
semantics** · probability a lineup is optimal or near-optimal in plausible
game states · portfolio overlap and whether a new lineup actually adds a
different winning path.

**Do not create differentiation for differentiation's sake.** A chalky,
highly-projected lineup still belongs in the portfolio if its raw winning
probability justifies it.

But actively search for: the field over-owning a popular construction; a
lower-owned Captain with similar ceiling; salary left unused materially
reducing duplication; an unusual but football-coherent construction that wins
in a meaningful share of plausible worlds; two lineups with similar
projections where one has a materially better path to first because of
ownership or duplication.

## Required per final lineup

1. Captain and FLEX players
2. total salary and salary remaining
3. projected mean and relevant ceiling/tail metrics
4. estimated ownership where available
5. estimated duplication / uniqueness risk where available
6. the game-state or construction thesis under which it wins
7. why it belongs instead of the nearest alternative
8. what assumptions would cause it to fail

## Required portfolio-level summary

Captain exposure · player exposure · game-script exposure · salary-left
distribution · chalk vs leverage balance · duplication profile · concentration
risk · which lineups are intentionally related · which create genuinely
different winning paths.

## The honesty clause, in the owner's own words

> Do not claim exact lineup-winning probabilities unless the joint simulation
> semantics support that claim. The current independent player streams are not
> a validated shared football world, so any current correlation or
> lineup-optimality estimates must be labeled according to the evidence
> actually available.

This is not a caveat bolted on. It is part of the directive, and it is the
clause that decides what may be shipped today.

## The destination

The DFS product consumes **validated shared football worlds plus an opponent
field model**, so that we can estimate:

> P(at least one of our 10 lineups wins or reaches the extreme top tail of the
> actual contest field)

## Why the engine cannot yet serve the objective

Three of the objective's load-bearing inputs do not exist in this repository
today. Naming them is not an excuse; it is the work list.

| Required by the directive | State |
|---|---|
| Valid cross-player correlation (ceiling, tail, stacking) | **ABSENT.** 351/351 sealed draw artifacts declare `INDEPENDENT_STREAMS_COLUMN_ALIGNED`; zero declare `SHARED_FOOTBALL_WORLD`. |
| Ownership projection | **ABSENT.** No estimator exists. |
| Field / duplication model | **ABSENT.** No opponent-field generator exists. |

**The correlation gap is not a rounding error on this objective, it is the
objective.** A Showdown lineup's score is the sum of six correlated players.
With independent streams, `Var(sum)` is modelled as the sum of the variances
and the covariance terms are dropped. Real same-game lineups — a quarterback
with his own receiver above all — carry strongly positive covariance, so the
modelled distribution is **too narrow in exactly the tail the tournament is
decided in**. Ceiling is the quantity that matters most here and it is the
quantity currently least trustworthy.

So a ranked 10-lineup portfolio produced today would be ranking on a number
the artifact's own manifest says must not be read that way. That is the one
thing the directive's honesty clause forbids.

## What this changes about the roadmap

B3 (minimal shared-football-world candidate) stops being an architectural
nice-to-have and becomes the **gating dependency of the entire DFS product**.
C4 (ownership, field, duplication, portfolio EV) is the second. Until both
land, DFS output is restricted to quantities that survive independent streams:
per-player marginals, conditional-vs-unconditional means, salary and identity
integrity, and availability risk.

Those are real and they are worth shipping. They are not a portfolio ranked by
win probability, and they must never be presented as one.
