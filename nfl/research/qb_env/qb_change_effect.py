#!/usr/bin/env python3.12
"""How much does a club's offence move when it starts a QB whose club environment is not his? Research only.

    python3.12 nfl/research/qb_env/qb_change_effect.py [--out QB_CHANGE_EFFECT.json]

Owner directive 2026-10-08 (QB-replacement pathway). The production club environment -- team volume
(proj_v1.team_volume) and the scoring centre (nfl/sim/football_points.expected_points) -- is a club-level blend of the
club's history and does not know who starts. This MEASURES, on 2021-2025 regular seasons only (all before any 2026
slate's cutoff), the residual of realised team outcomes against those QB-blind centres, split by whether the starter's
pre-game blended share of the club's pass attempts is a majority (showdown_run_guards.qb_environment_share, the
runner's own rule) or not.

STARTER, without conditioning on the outcome more than unavoidable: the QB with the most attempts in the game. A
club-game is EXCLUDED when a second QB threw >= 10 attempts (a mid-game change, which would select on in-game
events) or the starter threw < 10. The exclusion is reported.

Measured per club-game: points minus the football centre; pass attempts, rush attempts and passing yards per attempt
minus the club's blended (current season before the week + prior season at 4 pseudo-games) values.
Uncertainty: cluster bootstrap over (season, week) dates, 2,000 resamples, seed 20261008 (games in one week share a
date; CLAUDE.md rule 9). Nothing here changes a projection; it sizes the missing dependency.
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import random
import statistics
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.sim import football_points as FP  # noqa: E402
from nfl.tools import player_prior as PP  # noqa: E402
from nfl.tools import showdown_run_guards as G  # noqa: E402

SEASONS = range(2021, 2026)
PRIOR_GAMES = 4.0
MIDGAME_MIN = 10
SEED = 20261008
B = 2000


def _blend(panel, club, season, week, field, per_attempt=None):
    def per(yr, wk):
        wks = {w: v for w, v in (panel['teams'].get(club, {}).get(str(yr)) or {}).items() if wk is None or int(w) < wk}
        if not wks:
            return None, 0
        if per_attempt:
            num = sum(sum((pw.get(field) or 0) for pw in _qb_weeks(panel, club, yr, int(w))) for w in wks)
            den = sum(v.get('pass_attempts') or 0 for v in wks.values())
            return (num / den if den else None), len(wks)
        return sum(v.get(field) or 0 for v in wks.values()) / len(wks), len(wks)
    c, n = per(season, week)
    p, _ = per(season - 1, None)
    parts = [(n, c), (PRIOR_GAMES, p)]
    den = sum(w for w, x in parts if x is not None)
    return sum(w * x for w, x in parts if x is not None) / den if den else None


_QB_INDEX = {}


def _qb_weeks(panel, club, yr, wk):
    k = (club, yr, wk)
    if k not in _QB_INDEX:
        _QB_INDEX[k] = [v for g, s in panel['players'].items() for v in [((s.get(str(yr)) or {}).get(str(wk)))]
                        if v and v.get('team') == club and (v.get('pass_attempts') or 0) > 0]
    return _QB_INDEX[k]


def measure():
    panel = PP.load_panel().value
    table = FP.club_points_table(FP._rows())
    # index QB weeks once: (club, season, week) -> [(gsis, week-record)]
    qbs = collections.defaultdict(list)
    for g, seasons in panel['players'].items():
        for yr, weeks in seasons.items():
            if int(yr) not in SEASONS:
                continue
            for wk, v in weeks.items():
                if (v.get('pass_attempts') or 0) > 0 and v.get('team'):
                    qbs[(v['team'], int(yr), int(wk))].append((g, v))
    _QB_INDEX.update({k: [v for _g, v in lst] for k, lst in qbs.items()})
    rows, excluded = [], collections.Counter()
    for (club, yr, wk), lst in sorted(qbs.items()):
        if wk > 18:
            continue
        lst = sorted(lst, key=lambda t: -(t[1].get('pass_attempts') or 0))
        g, s = lst[0]
        att = s.get('pass_attempts') or 0
        if att < MIDGAME_MIN:
            excluded['STARTER_UNDER_10_ATTEMPTS'] += 1
            continue
        if len(lst) > 1 and (lst[1][1].get('pass_attempts') or 0) >= MIDGAME_MIN:
            excluded['MIDGAME_QB_CHANGE'] += 1
            continue
        pts = (table.get(club, {}).get(yr) or {}).get(wk)
        centre, _b = FP.expected_points(table, club, yr, wk)
        if pts is None or centre is None:
            excluded['NO_POINTS_OR_CENTRE'] += 1
            continue
        sh = G.qb_environment_share(panel, club, g, yr, wk, PRIOR_GAMES)['blended_share']
        team = (panel['teams'].get(club, {}).get(str(yr)) or {}).get(str(wk)) or {}
        pa_b = _blend(panel, club, yr, wk, 'pass_attempts')
        ra_b = _blend(panel, club, yr, wk, 'rush_attempts')
        ypa_b = _blend(panel, club, yr, wk, 'pass_yards', per_attempt=True)
        tpa = team.get('pass_attempts') or 0
        tpy = sum(v.get('pass_yards') or 0 for v in _QB_INDEX[(club, yr, wk)])
        if sh is None or pa_b is None or ypa_b is None or not tpa:
            excluded['NO_BLEND'] += 1
            continue
        rows.append({'club': club, 'season': yr, 'week': wk, 'share': sh,
                     'group': 'CHANGE' if sh <= G.QB_ENV_MAJORITY else 'INCUMBENT',
                     'd_points': pts - centre, 'd_pass_att': tpa - pa_b,
                     'd_rush_att': (team.get('rush_attempts') or 0) - (ra_b or 0), 'd_ypa': tpy / tpa - ypa_b})
    return rows, excluded


def summarise(rows):
    rng = random.Random(SEED)
    dates = sorted({(r['season'], r['week']) for r in rows})
    by_date = collections.defaultdict(list)
    for r in rows:
        by_date[(r['season'], r['week'])].append(r)
    out = {}
    for f in ('d_points', 'd_pass_att', 'd_rush_att', 'd_ypa'):
        def diff(sample):
            c = [r[f] for r in sample if r['group'] == 'CHANGE']
            i = [r[f] for r in sample if r['group'] == 'INCUMBENT']
            return (statistics.fmean(c) - statistics.fmean(i)) if c and i else None
        point = diff(rows)
        boots = []
        for _ in range(B):
            s = [r for d in (rng.choice(dates) for _ in dates) for r in by_date[d]]
            v = diff(s)
            if v is not None:
                boots.append(v)
        boots.sort()
        out[f] = {'CHANGE_mean': round(statistics.fmean(r[f] for r in rows if r['group'] == 'CHANGE'), 3),
                  'INCUMBENT_mean': round(statistics.fmean(r[f] for r in rows if r['group'] == 'INCUMBENT'), 3),
                  'difference': round(point, 3),
                  'ci95_date_clustered': [round(boots[int(0.025 * len(boots))], 3), round(boots[int(0.975 * len(boots)) - 1], 3)]}
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--out')
    a = ap.parse_args()
    rows, excl = measure()
    n = collections.Counter(r['group'] for r in rows)
    res = {'ARTIFACT': 'QB_CHANGE_EFFECT', 'LAYER': 'RESEARCH_ONLY -- changes no projection', 'seasons': [min(SEASONS), max(SEASONS)],
           'n_club_games': dict(n), 'excluded': dict(excl), 'rule': f'CHANGE = starter pre-game blended share <= {G.QB_ENV_MAJORITY}',
           'effects_CHANGE_minus_INCUMBENT': summarise(rows), 'seed': SEED, 'bootstrap': B,
           'CAVEATS': ['starter identified from most attempts in the game (mid-game changes excluded)',
                       'no opponent adjustment; centres are own-offence, as in production',
                       'a CHANGE start is not random: it follows injury, benching or rest, which can also move the offence']}
    if a.out:
        pathlib.Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(a.out).write_text(json.dumps(res, indent=1) + '\n')
    print(json.dumps({k: res[k] for k in ('n_club_games', 'excluded', 'effects_CHANGE_minus_INCUMBENT')}, indent=1))
