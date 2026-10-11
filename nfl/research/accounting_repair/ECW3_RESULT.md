# ECW-3 result (2026-10-11, 20:02 UTC): structural acceptance NOT MET (receiver dispersion); cause located upstream

Two CORRECTED_V1 replays of the W5 2026-10-11 slate on the 16:17Z state, in separate overlays: with participation, and
without it (control). The world builder is `event_consistent_worlds` version 3 (`f23c6113`, account fields `6a7f0f05`).
They were checked with `ecw2_acceptance.py` (C2 measure, `92e2bbe1`). The worlds are byte-identical across two runs of
each arm (19:51Z and 19:57Z).

| criterion (PREREG_ECW2 s.2 with PREREG_ECW3 C2) | ECW-2 control | ECW-3 control | ECW-3 with participation | bar |
|---|---|---|---|---|
| accounting violations, all laws | 0 | **0** | **0** | 0 |
| tie share, max game | 0.25% | 0.30% | 0.30% | ≤ 0.6% |
| receiver yards CV / history 0.4514, worlds with > 2 catches | 1.369 | **1.229** | **1.236** | [0.85, 1.15] |
| the same, all worlds (ECW-2's measure, decides nothing) | 1.666 | 1.553 | 1.571 | — |

## Verdict

- **NOT MET**, on receiver dispersion.
- Accounting and ties pass.
- C1 did what it was derived to do: every club's factor CV went from about 0.27 to its target of 0.08-0.17. The
  receiver ratio moved from 1.37 to 1.23. The rest of the excess is not in the club factor.

## Not a population artefact (diagnostic only; the registered measure above decides)

History's benchmark population is player-seasons with at least six games of more than 2 catches, and the slate's is
receivers with a mean of more than 2. History was binned by mean catches in those games, and each simulated receiver
was compared with its own bin:

| mean catches | history yards CV | sim yards CV (control) | history catches CV | sim catches CV (control) |
|---|---|---|---|---|
| 3.5-4.5 | 0.450 (n 300) | 0.557 (n 20) | 0.265 | 0.320 |
| 4.5-5.5 | 0.458 (n 224) | 0.564 (n 22) | 0.327 | 0.373 |
| > 5.5 | 0.441 (n 158) | 0.548 (n 20) | 0.345 | 0.384 |

The bin-matched median ratio is 1.234 in both arms. That is the same as the registered figure, so the population
does not explain it.

## Where the remaining excess is, measured

History: 2021-2025 REG play-by-play, games with > 2 catches, player-seasons with at least six such games (n 719).
Sim: control arm, worlds with > 2 catches (n 62 receivers). Values are medians.

| quantity | history | ECW-3 sim | ratio |
|---|---|---|---|
| club targets per game, CV about the club(-season) mean | 0.225 (2,718 club-games) | 0.224 | 1.00 |
| player target **share** of club targets, CV | 0.287 | 0.314 | 1.10 |
| player targets, CV | 0.299 | 0.342 | 1.14 |
| player catches, CV | 0.304 | 0.371 | 1.22 |
| player receiving yards, CV | 0.451 | 0.555 | 1.23 |

- **Club volume is right.**
- The excess starts at the **per-player share of targets**, and grows at **catches given targets**.
- Both come from the raw simulator (`nfl/sim/game.py` target allocation and the catch draw), upstream of the world
  builder. The share family and concentration there are the incumbent's measured ones, and the incumbent carries the
  same excess (like-for-like 1.445).
- No rescaling inside ECW can repair it honestly, and none is attempted here.

## What follows

- ECW-3 stands as recorded. It is the CORRECTED_V1 arm's world builder (`classic_slate_run.ECW_VERSION = 3`), and is
  shadow only.
- New defect **SIM-D9**: per-player target share and catch-given-target dispersion exceed history by about 10% and
  about 7% respectively (compounded: catches 1.22).
  - It is in the shared raw simulator, so it affects the incumbent too.
  - Its repair needs its own pre-registration. That registration must measure the share-dispersion component on the
    same conditioning the simulator's concentration was estimated on, before any change is made.
- The receiver-dispersion check in `test_contract45_integration.py` (06b) **fails** on this fixture, and is left
  failing. It is not skipped.
