#!/usr/bin/env python3.12
"""Historical same-game coherence targets (2021-2025 regular season, local nflverse pbp, the kicker_world captures).

    python3.12 nfl/research/coherence/team_coherence_history.py

Per team-game: the correlation of offensive TDs and of final points with the team's summed offensive DK points
(0.04 / pass yd, 0.1 / rush or rec yd, 1 / reception, 4+6 per passing TD, 6 per rushing TD, -1 per INT and fumble
lost; no yardage bonuses), and the cross-team correlations of points and of offensive DK. These are VALIDATION
TARGETS for the joint simulator (Cycle 1 ledger test 6). Writes TEAM_COHERENCE_2021_2025.json beside this file.
"""
import json, pathlib, sys
import numpy as np, pandas as pd
_REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO))
from nfl.tools import kicker_world as KW  # noqa: E402
cols = ['game_id', 'posteam', 'defteam', 'season_type', 'play_type', 'passing_yards', 'rushing_yards', 'receiving_yards', 'complete_pass', 'pass_touchdown', 'rush_touchdown', 'interception', 'posteam_score_post', 'total_home_score', 'total_away_score', 'home_team', 'away_team', 'two_point_conv_result', 'fumble_lost']


def run():
    frames = []
    for s, p in KW._pbp_paths().items():
        df = pd.read_csv(p, usecols=lambda c: c in cols, low_memory=False)
        frames.append(df[df.season_type == 'REG'])
    df = pd.concat(frames)
    f = df.fillna(0)
    f['dk'] = (0.04 * f.passing_yards + 0.1 * f.receiving_yards + 0.1 * f.rushing_yards + 1.0 * f.complete_pass
               + 10 * f.pass_touchdown + 6 * f.rush_touchdown - 1 * f.interception - 1 * f.fumble_lost)
    f['td'] = f.pass_touchdown + f.rush_touchdown
    g = f.groupby(['game_id', 'posteam']).agg(dk=('dk', 'sum'), td=('td', 'sum')).reset_index()
    fin = df.groupby('game_id').agg(home=('home_team', 'first'), away=('away_team', 'first'),
                                   hs=('total_home_score', 'max'), as_=('total_away_score', 'max')).reset_index()
    g = g.merge(fin, on='game_id')
    g['pts'] = np.where(g.posteam == g.home, g.hs, g.as_)
    g['opp_pts'] = np.where(g.posteam == g.home, g.as_, g.hs)
    g = g[g.posteam != 0]
    pass
    h = g[g.posteam == g.home][['game_id', 'pts', 'dk']].merge(g[g.posteam == g.away][['game_id', 'pts', 'dk']], on='game_id', suffixes=('_h', '_a'))
    doc = {'ARTIFACT': 'TEAM_COHERENCE_HISTORY', 'seasons': sorted(KW._pbp_paths()), 'team_games': int(len(g)), 'games': int(len(h)),
           'sources': {str(s): str(p.relative_to(_REPO)) for s, p in KW._pbp_paths().items()},
           'corr_team_td_vs_team_off_dk': round(float(g.td.corr(g.dk)), 3),
           'corr_team_points_vs_team_off_dk': round(float(g.pts.corr(g.dk)), 3),
           'corr_home_points_vs_away_points': round(float(h.pts_h.corr(h.pts_a)), 3),
           'corr_home_off_dk_vs_away_off_dk': round(float(h.dk_h.corr(h.dk_a)), 3),
           'USE': 'validation target for the joint simulator; never an imposed copula'}
    (pathlib.Path(__file__).resolve().parent / 'TEAM_COHERENCE_2021_2025.json').write_text(json.dumps(doc, indent=1))
    return doc


if __name__ == '__main__':
    print(json.dumps(run(), indent=1))
