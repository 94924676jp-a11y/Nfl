# Successor specification: conditional substitution. Design only.

**Nothing here is implemented and no number in this document is a
coefficient.** It is the specification a fit would have to satisfy, written
after A2 was falsified and before anything replaces the proportional
allocator, so that the replacement is constrained by what the measurement
actually showed rather than by what it felt like.

**The proportional allocator stays in production until a successor beats it
out of sample.** A falsified default is not automatically worse than an
unfitted replacement.

## What the measurement constrains

Three things the successor must handle, each one a measured result rather than
an intuition:

1. **The room is not closed.** 6–23% of vacated opportunity goes to players
   with no trailing-window share at all. A model whose support is the trailing
   room cannot express that, and pricing it at zero is what made the default's
   total log score collapse.
2. **Already-large survivors absorb less than proportionally.** Excess
   absorption at share-rank distance −1 and −2 is negative with
   cluster-bootstrap intervals excluding zero in all four rooms. The nearest
   neighbour, by contrast, absorbs about his proportional share.
3. **The rooms differ.** Carries show a clean magnitude error (slope 0.50).
   Targets show a sign error (slope −0.16). One rule across both is refused by
   the data.

## The shape a successor must have

```
P(opportunity unit -> player j | i absent)
    = f( j's trailing share,
         j's rank distance from i,
         room identity (carries | targets | rz_carries | rz_targets),
         room size,
         AND an explicit OUT_OF_ROOM mass )
```

**`OUT_OF_ROOM` is a first-class outcome, not a residual.** It must carry its
own probability and be scored like any other, because it is 6–23% of the
answer.

## What may NOT be done

- **No hand-designed substitution matrix.** Every weight is fitted from
  forward-chained folds or it does not exist. This is a standing constraint,
  not a preference.
- **No coefficient carried over from `A2_REDISTRIBUTION.json`.** The numbers
  in that artifact are a *diagnosis*. Installing them would be fitting on the
  evaluation set.
- **No monotonicity imposed** on absorption in rank distance. The measurement
  shows rd = 0 near zero excess and rd = −1 strongly negative; whether that is
  monotone is a question, not an assumption to encode.
- **No pooling of carries and targets** to gain sample. Their slopes have
  opposite signs.

## Open choices that must be preregistered BEFORE the fit

Each of these changes the answer, and none is settled by the A2 measurement:

| choice | why it is not settled |
|---|---|
| the conditioning window | A2 used 3 club games because a role state needs recent evidence; 2 and 4 are equally defensible and would change which shocks qualify |
| the materiality threshold | `MIN_SHARE 0.10` defines what counts as a shock at all |
| position in the cell key | position is not in the play-by-play rows A2 reads; a join is needed, and a join is a decision |
| whether `OUT_OF_ROOM` is one bucket or several | an elevated practice-squad back and a healthy WR5 are different men |
| the estimator family | Dirichlet-multinomial with covariates, a multinomial logit over survivors plus an out-of-room class, or a hierarchical shrinkage over rooms |
| partial absence | A2 scored only ZERO opportunity. A man who plays at half his usual share is a different and more common event |

## Acceptance

Forward-chained on the same cohort construction, scored **in-room and total
separately** as A2 scores them, against three comparators declared in advance:
`PROPORTIONAL`, `ROOM_UNIFORM`, and `NO_TRANSFER`. Scored on **opportunity**,
never on yards.

**A measured negative is a result.** If the successor does not beat
`PROPORTIONAL` out of sample on both the in-room and total scores, it does not
ship, the grid is not widened, and `A2` stays falsified with the proportional
allocator still in place — which is a coherent state, not a contradiction: the
default being wrong does not oblige anyone to install something worse.

## What would move A2 back to SUPPORTED

Nothing available. The falsification rests on 1,257 forward-chained events
with cluster-robust intervals. A2 could only return to `SUPPORTED` if that
measurement were shown to be wrong — a defect in the cohort construction, the
scoring, or the clustering — and that would be a new artifact, not an edit to
this one.

**V2 NOT YET EARNED**
