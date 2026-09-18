"""FanDuel NFL scoring, as a mechanical adapter over the SAME StatLine.

NO SEPARATE PROJECTION MODEL EXISTS AND NONE MAY. FanDuel points here are the
same simulated football worlds read through different arithmetic. Nothing in
this file reaches back into the engine, and nothing in the engine knows this
file exists.

PROVENANCE, CORRECTED 2026-09-18

An earlier version of this module carried UNVERIFIED_FROM_RECOLLECTION
coefficients and REFUSED to let them reach a portfolio. The gate was right and
the recollection was wrong: external research against the official FanDuel
Rules & Scoring page (retrieved 2026-09-17) shows FanDuel pays the SAME +3
yardage bonuses DraftKings does -- 300 passing, 100 rushing, 100 receiving --
where the recalled table had all three at zero.

That error was not small. It was three points on exactly the outcomes a DFS
lineup is built to catch, and it would have depressed every ceiling on the
board asymmetrically: a receiver who breaks 100 yards is precisely the player a
tournament lineup needs, and the recalled table charged him three points for
doing it.

WHAT ACTUALLY SEPARATES THE TWO SITES, now that the bonuses agree

Exactly one rule: 0.5 points per reception against DraftKings' 1.0. Every other
scored quantity this simulation produces is identical. So for any player in any
world:

    FD = DK - 0.5 * receptions

That identity is asserted as a test over all 29 players and all 8,000 worlds.
It is a much stronger check than comparing two hand-built lines, because it
would fail if either adapter drifted on any term.
"""
from __future__ import annotations

import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402
from nfl.dfs.scoring import statline as SL                           # noqa: E402

SPEC_VERSION = 'nfl-dfs-scoring-fanduel-2'
SITE = 'FANDUEL'

UNVERIFIED = 'UNVERIFIED_FROM_RECOLLECTION'
VERIFIED = 'VERIFIED_AGAINST_SOURCE'

RULES_ARTIFACT = _REPO / 'nfl/dfs/scoring/FANDUEL_RULES_VERIFIED.json'

SOURCE = ('official FanDuel Rules & Scoring page, retrieved 2026-09-17, '
          'relayed by the operator')

RULES = {
    'pass_yard': 0.04, 'pass_td': 4.0, 'interception': -1.0,
    'rush_yard': 0.1, 'rush_td': 6.0,
    'rec_yard': 0.1, 'reception': 0.5, 'rec_td': 6.0,
    'fumble_lost': -2.0,          # NOT SIMULATED -- see statline.NOT_SIMULATED
    'two_point_scored': 2.0,      # NOT SIMULATED
    'two_point_thrown': 2.0,      # NOT SIMULATED
    'return_td': 6.0,             # NOT SIMULATED
    'fg_made_under_40': 3.0, 'fg_made_40s': 4.0, 'fg_made_50_plus': 5.0,
    'xp_made': 1.0,
}

#: CORRECTED. These were 0.0 and that was wrong. Kept as an explicit mapping
#: rather than folded into RULES so the correction stays visible.
BONUSES = {'bonus_300_pass_yards': 3.0, 'bonus_100_rush_yards': 3.0,
           'bonus_100_rec_yards': 3.0}

RULE_PROVENANCE = {k: VERIFIED for k in list(RULES) + list(BONUSES)}

#: What changed, and what it was. A correction that erases the wrong value
#: teaches nobody anything.
CORRECTIONS_2026_09_18 = {
    'bonus_300_pass_yards': {'was': 0.0, 'now': 3.0},
    'bonus_100_rush_yards': {'was': 0.0, 'now': 3.0},
    'bonus_100_rec_yards': {'was': 0.0, 'now': 3.0},
    'why': 'the recalled table assumed FanDuel pays no yardage bonuses. It '
           'pays the same +3 DraftKings does. Recollection was wrong on the '
           'three coefficients that had been flagged HIGHEST_RISK_IF_WRONG, '
           'which is the argument for the gate rather than against it.',
}

#: The ONLY rule that now separates the two sites on anything this simulation
#: produces.
ONLY_DIFFERENCE_FROM_DRAFTKINGS = 'reception: 0.5 here against 1.0 on DraftKings'


def score(sl: SL.StatLine) -> np.ndarray:
    s = (RULES['pass_yard'] * sl.pass_yards
         + RULES['pass_td'] * sl.pass_td
         + RULES['interception'] * sl.interceptions
         + RULES['rush_yard'] * sl.rush_yards
         + RULES['rush_td'] * sl.rush_td
         + RULES['rec_yard'] * sl.rec_yards
         + RULES['reception'] * sl.receptions
         + RULES['rec_td'] * sl.rec_td)
    s = s + BONUSES['bonus_300_pass_yards'] * (sl.pass_yards >= 300)
    s = s + BONUSES['bonus_100_rush_yards'] * (sl.rush_yards >= 100)
    s = s + BONUSES['bonus_100_rec_yards'] * (sl.rec_yards >= 100)
    return s


def score_kicker(sl: SL.StatLine) -> np.ndarray:
    """0-39 / 40-49 / 50+ at 3 / 4 / 5, identical banding to DraftKings."""
    b = sl.fg_made_by_bucket
    if b:
        return (RULES['fg_made_under_40'] * (b.get('FG<20', 0)
                                             + b.get('FG20s', 0)
                                             + b.get('FG30s', 0))
                + RULES['fg_made_40s'] * b.get('FG40s', 0)
                + RULES['fg_made_50_plus'] * b.get('FG50+', 0)
                + RULES['xp_made'] * sl.xp_made)
    return RULES['fg_made_under_40'] * sl.fg_made + RULES['xp_made'] * sl.xp_made


def rules_state() -> Outcome:
    if RULES_ARTIFACT.exists():
        return Outcome.ok(
            'FANDUEL_RULES_VERIFIED', value=VERIFIED,
            detail=f'scoring verified against {SOURCE}; the single remaining '
                   f'difference from DraftKings is '
                   f'{ONLY_DIFFERENCE_FROM_DRAFTKINGS}',
            spec_version=SPEC_VERSION, source=SOURCE,
            corrections=CORRECTIONS_2026_09_18,
            outbox_item='OUT-022A RESOLVED')
    return Outcome.blocked(
        'FANDUEL_RULES_UNVERIFIED',
        f'{RULES_ARTIFACT.name} is absent, so the coefficients in this module '
        f'carry no recorded source.', cause=Cause.NETWORK,
        spec_version=SPEC_VERSION)
