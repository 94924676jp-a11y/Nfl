# WITHDRAWN: the QB over-hedge is already measured, better, elsewhere

**Raised 2026-09-24. Withdrawn the same day, before anyone worked it.**

## Why this is withdrawn

I opened this ticket proposing a pre-registered study of whether the QB room
is over-hedged, on the evidence that ATL's play probabilities sum to 1.232 and
two or more QBs throw in 21.8% of its simulated worlds.

`nfl/production/qb_v1.py:KNOWN_LIMITATIONS['multi_qb_over_prediction']`
already measures exactly this, on **n = 699 team-games**, and names the
mechanism. My evidence was two team-games from one game. The existing record
is better in every respect and the question it answers is the same one.

What is already established there:

| | |
|---|---|
| measured pass-yards bias, multi-QB team-games | **+79.89** |
| single-QB bias | -13.81 |
| 90% coverage, multi-QB | 0.794 |
| 90% coverage, single-QB | 0.961 |
| n | 699 |

and the 2024 dropback measurement: multi-QB team-games **draw 62.51 team
dropbacks against a realised 36.61**, +25.90; single-QB team-games draw 34.45
against 36.80, -2.35.

The mechanism is stated, not left open:

> prior-only dropback shares are not normalised within a team-game

That is precisely the sum-above-one I observed and proposed to investigate. It
is not an open question. The cause is recorded too -- *"the prior-only
dropback share of a QB later pulled is necessarily too high; no pregame
information in this project resolves it"* -- and the standing policy is
*"reported on every run, never smoothed away"*, which is why
`qb_known_limitations` shows FAIL on every run including this one.

**So the honest status is: known, quantified, mechanism identified, policy
set.** Nothing in my observation adds to it, and leaving this ticket open
would have invited someone to re-measure on worse data a thing already
measured on better.

## The one line worth carrying forward

The recorded cause says no **pregame** information in this project resolves
which quarterback is pulled. Official game-day inactives are pregame
information that resolves part of it: a quarterback on the inactive list
cannot be the one who starts and is later pulled, and his dropback share
should go to zero rather than being hedged.

That does not fix the within-team normalisation, which is the real mechanism
and applies just as much to two healthy quarterbacks. But it does mean the
post-inactive rerun is the one lever this project currently holds on the
measured bias, and it is worth watching tonight for that reason rather than
only for the roster change.

## What survives from the original ticket and has moved

The conditional-versus-unconditional reporting defect is separate, is not
covered by `KNOWN_LIMITATIONS`, and stands. It is implemented in
`nfl/research/unsealed/conditionality.py` and written up in
`nfl/research/findings/2026-09-24_QB_ALLOCATION_AND_CONDITIONALITY.md`.
It changes no projection.
