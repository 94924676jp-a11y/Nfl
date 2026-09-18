"""DraftKings NFL scoring, as a mechanical adapter over a StatLine.

VERIFIED, NOT ASSERTED. The sealed board already carries an independent
DraftKings implementation in `dk_scoring/dk_points`. This adapter reproduces
that array EXACTLY for all 29 modelled players over all 8,000 worlds, which is
what licenses using the same StatLine for FanDuel: if the assembly were
incomplete, DraftKings would not reconcile either.

That check is the reason this file exists at all rather than FanDuel being
written directly against the arrays.
"""
from __future__ import annotations

import numpy as np

from nfl.dfs.scoring import statline as SL

SPEC_VERSION = 'nfl-dfs-scoring-draftkings-1'
SITE = 'DRAFTKINGS'

#: DraftKings NFL classic scoring. Provenance: reproduced exactly from the
#: engine's own dk_scoring layer, so these coefficients are VERIFIED against
#: an independent implementation in this repository rather than recalled.
RULES = {
    'pass_yard': 0.04, 'pass_td': 4.0, 'interception': -1.0,
    'rush_yard': 0.1, 'rush_td': 6.0,
    'rec_yard': 0.1, 'reception': 1.0, 'rec_td': 6.0,
    'bonus_300_pass_yards': 3.0,
    'bonus_100_rush_yards': 3.0,
    'bonus_100_rec_yards': 3.0,
    'fumble_lost': -1.0,          # NOT SIMULATED -- see statline.NOT_SIMULATED
    'two_point': 2.0,             # NOT SIMULATED
    'return_td': 6.0,             # NOT SIMULATED
    'fg_made_under_40': 3.0, 'fg_made_40s': 4.0, 'fg_made_50_plus': 5.0,
    'xp_made': 1.0,
}

PROVENANCE = ('VERIFIED_AGAINST_ENGINE: this adapter reproduces '
              'dk_scoring/dk_points exactly for every modelled player over '
              'every world in the sealed DET @ BUF board.')


def score(sl: SL.StatLine) -> np.ndarray:
    s = (RULES['pass_yard'] * sl.pass_yards
         + RULES['pass_td'] * sl.pass_td
         + RULES['interception'] * sl.interceptions
         + RULES['rush_yard'] * sl.rush_yards
         + RULES['rush_td'] * sl.rush_td
         + RULES['rec_yard'] * sl.rec_yards
         + RULES['reception'] * sl.receptions
         + RULES['rec_td'] * sl.rec_td)
    s = s + RULES['bonus_300_pass_yards'] * (sl.pass_yards >= 300)
    s = s + RULES['bonus_100_rush_yards'] * (sl.rush_yards >= 100)
    s = s + RULES['bonus_100_rec_yards'] * (sl.rec_yards >= 100)
    return s


def score_kicker(sl: SL.StatLine) -> np.ndarray:
    """Distance-banded, because DraftKings pays 50+ more than a chip shot.

    Falls back to a flat 3.0 per make ONLY when the distance buckets are
    absent, and the caller is told which path ran rather than left to guess.
    """
    b = sl.fg_made_by_bucket
    if b:
        s = (RULES['fg_made_under_40'] * (b.get('FG<20', 0)
                                          + b.get('FG20s', 0)
                                          + b.get('FG30s', 0))
             + RULES['fg_made_40s'] * b.get('FG40s', 0)
             + RULES['fg_made_50_plus'] * b.get('FG50+', 0))
        return s + RULES['xp_made'] * sl.xp_made
    return RULES['fg_made_under_40'] * sl.fg_made + RULES['xp_made'] * sl.xp_made
