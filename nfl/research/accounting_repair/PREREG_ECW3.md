# ECW-3 pre-registration: ECW-2 with the club efficiency factor at its measured spread

- **Written:** 2026-10-11 at about 19:48 UTC, after ECW-2's structural acceptance was not met (`ECW2_RESULT.md`).
  The commit time is authoritative.
- **Status:** PRE-REGISTERED, SHADOW ONLY. The CORRECTED_V1 arm's world builder, beside the incumbent.

## Change from ECW-2 (section 1 and amendment A1 otherwise unchanged)

### C1. Club factor spread

In every club, the per-world club efficiency factor is rescaled about 1:

    club_w' = 1 + (club_w - 1) × (cv_target / cv_raw)

| term | definition |
|---|---|
| cv_raw | that club's factor CV across worlds |
| cv_target | sqrt(max(0, 0.2346² - 0.85093² / m_c)), clipped to [0, cv_raw] |
| 0.2346 | the measured club-game yards-per-target CV (`ECW2_INPUTS.json` `club_game_ypt`) |
| 0.85093 | the measured single-catch CV (`catch_shape`) |
| m_c | the club's mean catches per world |

- This is a derivation from two measured spreads, not a fit.
- History's club-game spread already contains catch-level noise. The simulator adds catch noise separately, so only
  the remainder belongs in the club factor.

### C2. Acceptance computed like-for-like

The history benchmark (0.451) is the CV over games with more than 2 catches. The simulated CV for each receiver with
mean > 2 catches is therefore taken over the worlds in which he has more than 2 catches.

- This corrects how ECW-2's bar was computed; the bar itself, [0.85, 1.15], is unchanged.
- ECW-2's verdict is not re-scored. On the corrected measure it would still fail (1.37).

## Acceptance and evaluation

- PREREG_ECW2 sections 2 and 3, with C2.
- Voids: as PREREG_ECW2 section 4.
