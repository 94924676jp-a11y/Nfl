# Owed: the HARD invariant that would have graded QY1's gate 2 does not run

**Status: NOT_EXECUTED. Not passed, not failed, not waived.**

## What gate 2 asked for

`nfl/research/qb_yards/predeclaration_signed_deal.md` §6 gate 2:

> `qb_cross_layer_reconciliation` still passes: team passing yards **equals**
> player receiving yards.

## What actually happens

`nfl/production/qb_accounting.py:382` `reconcile_cross_layer(D, receiving=None,
receiving_td=None)` returns

```
DEFERRED[CROSS_LAYER_RECONCILIATION_NOT_RUN]
```

whenever `receiving is None`, and says so in its own words: *"a check that did
not run has not passed."*

`nfl/production/run_forecast.py:2029` calls it with
`receiving=fx.get('receiving_yard_draws')`. **Nothing in `run_forecast.py`
ever sets `receiving_yard_draws`.** Measured on the 2026 week-2 DET-BUF run of
2026-09-17, the artifact records:

```
{"invariant": "qb_cross_layer_reconciliation", "class": "HARD",
 "state": "DEFERRED", "code": "CROSS_LAYER_RECONCILIATION_NOT_RUN"}
```

So the governed invariant named in gate 2 has **never run on any board**, and
the QY1 arm did not change that. This is the same defect class as the bullpen
label and the dormant `qb_inactive_ownership_enforced` before it: an artifact
that is written, correct, wired at one end, and fed by nobody.

## Why it is recorded rather than fixed here

Feeding it is a behaviour change to **every** arm, not to QY1. A HARD
invariant that currently answers DEFERRED would start answering PASS or FAIL,
and if it answers FAIL on the incumbent share path — which divides an integer
team total and therefore does **not** reproduce the receiving sum exactly —
then wiring it inside a QY1 commit would look like QY1 breaking a gate it
actually repairs. Separate change, separate commit, separate before/after.

## What was measured instead, and what that is worth

The identity gate 2 asserts was evaluated **directly from the sealed draw
arrays**, joined on `gsis_id` from each run's own manifest, and reported in
`nfl/research/qb_yards/QY1_RESULT.md`. That is a real measurement of the real
quantity. It is **not** the governed invariant, it does not gate sealing, and
it must not be quoted as `qb_cross_layer_reconciliation` passing.

## The work

1. Set `fx['receiving_yard_draws']` and `fx['receiving_td_draws']` from the
   conversion and TD layers, aligned to the same team-games and draw indices.
2. Run it on a frozen arm FIRST and record what it says, before any candidate
   claims it.
3. Preserve `LATERAL_EXCEPTION`: a lateral makes team passing yards and player
   receiving yards legitimately differ, and `reconcile_cross_layer` already
   carries that exception. It is not a tolerance to widen.

**V2 NOT YET EARNED**
