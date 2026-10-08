#!/usr/bin/env python3.12
"""GAP 3, evidence layer: what same-game correlation actually looks like, measured.

WHY THIS COMES BEFORE THE SIMULATOR

The mandate's instruction on correlation is "do not hand-add arbitrary correlation bonuses once
the simulator can produce them". A simulator can only be held to that if there is something to
hold it to, so this measures the correlations from history first. The simulator is then judged
on whether its output reproduces these numbers, rather than on whether its internals look
plausible.

HOW THE PAIRS ARE DEFINED, AND THE TRAP AVOIDED

A pair like "quarterback and his number one receiver" needs a definition of number one that does
not peek at the game being measured. Ranking receivers by the targets they got THAT game would
manufacture correlation out of nothing: the player who happened to be targeted most is by
construction the one who had the most productive day. So ranks come from ROLE_HISTORY's pregame
depth rank for that season and week, never from the realised stat line.

Games are not independent observations and players inside a game are less so, so every interval
here is a block bootstrap resampling whole GAMES, not player-pairs.
"""
from __future__ import annotations

import collections
import json
import math
import pathlib
import random
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402
from nfl.warehouse import point_in_time as PIT  # noqa: E402

PG = _REPO / 'nfl/warehouse/PLAYER_GAME.json'
RH = _REPO / 'nfl/warehouse/ROLE_HISTORY.json'
TG = PIT.resolve(_REPO / 'nfl/warehouse/TEAM_GAME.json')   # as of the cutoff in a sealed run
OUT = _REPO / 'nfl/sim/PAIR_CORRELATIONS.json'

# same-club pairs, then cross-club. (position, rank) on each side.
SAME_CLUB = [
    ('QB1', 'WR1'), ('QB1', 'WR2'), ('QB1', 'WR3'), ('QB1', 'TE1'), ('QB1', 'RB1'),
    ('WR1', 'WR2'), ('WR1', 'TE1'), ('RB1', 'WR1'), ('RB1', 'RB2'), ('RB1', 'TE1'),
]
CROSS_CLUB = [
    ('QB1', 'QB1'), ('QB1', 'WR1'), ('QB1', 'RB1'), ('WR1', 'WR1'), ('RB1', 'RB1'),
    ('RB1', 'WR1'),
]
MIN_PAIRS = 60
BOOT = 600


def _rows(path, key='rows'):
    a = json.loads(path.read_text())
    r = a[key]
    return (r if isinstance(r, list) else list(r.values())), a


def _pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 0 or syy <= 0:
        return None
    return sxy / math.sqrt(sxx * syy)


def _block_bootstrap(by_game, reps=BOOT, seed=17):
    """Resample whole games. Players inside a game are the opposite of independent."""
    games = list(by_game)
    if len(games) < 8:
        return None
    rng = random.Random(seed)
    out = []
    for _ in range(reps):
        xs, ys = [], []
        for _ in games:
            g = games[rng.randrange(len(games))]
            for x, y in by_game[g]:
                xs.append(x)
                ys.append(y)
        r = _pearson(xs, ys)
        if r is not None:
            out.append(r)
    if len(out) < reps // 3:
        return None
    out.sort()
    return {'lo': round(out[int(0.025 * len(out))], 4), 'hi': round(out[int(0.975 * len(out))], 4),
            'n_reps': len(out)}


def build() -> Outcome:
    if not PG.exists() or not RH.exists():
        return Outcome.blocked('PAIRS_SOURCE_ABSENT', 'player-game or role-history table missing',
                               cause=Cause.DATA, player_game=PG.exists(), role_history=RH.exists())
    pg, _ = _rows(PG)
    rh, _ = _rows(RH)

    # pregame depth rank: (season, week, player_id) -> (position, rank)
    #
    # Two join defects were found here and both produced ZERO pairs rather than a wrong number,
    # which is why they were caught at all. First, `week` is an int in ROLE_HISTORY and a string
    # in PLAYER_GAME, so every key missed; both sides are coerced now. Second, ROLE_HISTORY
    # carries one row per MEASURE, so a back appears ranked by carries and again by targets --
    # taking whichever row came last silently ranked receivers by carries. The measure is now
    # chosen to match the position.
    RANK_MEASURE = {'QB': 'pass_attempts', 'RB': 'carries', 'WR': 'targets', 'TE': 'targets'}
    rank = {}
    for r in rh:
        dr = r.get('depth_rank')
        pos = r.get('position')
        if not isinstance(dr, (int, float)) or RANK_MEASURE.get(pos) != r.get('measure'):
            continue
        rank[(int(r['season']), int(r['week']), r['player_id'])] = (pos, int(dr))

    # market context per club-game, for the conditional split
    total_of, spread_of = {}, {}
    if TG.exists():
        tg, _ = _rows(TG)
        for r in tg:
            if r.get('total_line') is not None:
                total_of[(r['game_id'], r['club'])] = r['total_line']
            if r.get('club_spread') is not None:
                spread_of[(r['game_id'], r['club'])] = r['club_spread']

    # slot every player into (game, club, POSn)
    slot = collections.defaultdict(dict)
    unranked = 0
    for r in pg:
        key = (int(r['season']), int(r['week']), r['player_id'])
        pr = rank.get(key)
        if pr is None:
            unranked += 1
            continue
        pos, k = pr
        if k > 3:
            continue
        slot[(r['game_id'], r['club'])][f'{pos}{k}'] = float(r['dk_points_current_rules'])

    clubs_in_game = collections.defaultdict(list)
    for (gid, club) in slot:
        clubs_in_game[gid].append(club)

    def collect(pairs, cross):
        out = {}
        for a, b in pairs:
            by_game = collections.defaultdict(list)
            for gid, clubs in clubs_in_game.items():
                if cross:
                    if len(clubs) != 2:
                        continue
                    c1, c2 = clubs
                    for x_club, y_club in ((c1, c2), (c2, c1)):
                        xa = slot[(gid, x_club)].get(a)
                        yb = slot[(gid, y_club)].get(b)
                        if xa is not None and yb is not None:
                            by_game[gid].append((xa, yb))
                        if a == b:
                            break  # unordered pair, count once
                else:
                    for club in clubs:
                        d = slot[(gid, club)]
                        if a in d and b in d:
                            by_game[gid].append((d[a], d[b]))
            xs = [x for g in by_game for x, _ in by_game[g]]
            ys = [y for g in by_game for _, y in by_game[g]]
            if len(xs) < MIN_PAIRS:
                out[f'{a}~{b}'] = {'state': 'NOT_IDENTIFIED_TOO_FEW_PAIRS', 'n_pairs': len(xs)}
                continue
            r = _pearson(xs, ys)
            ci = _block_bootstrap(by_game)
            out[f'{a}~{b}'] = {
                'r': None if r is None else round(r, 4),
                'n_pairs': len(xs), 'n_games': len(by_game),
                'ci95_game_blocked': ci,
                'SIGN_ESTABLISHED': bool(ci and ((ci['lo'] > 0) or (ci['hi'] < 0))),
            }
        return out

    same = collect(SAME_CLUB, cross=False)
    cross = collect(CROSS_CLUB, cross=True)

    # the conditional question the research item asks: does correlation move with the total?
    def conditional(a, b, cross_club, lo_hi):
        by_game = collections.defaultdict(list)
        for gid, clubs in clubs_in_game.items():
            for club in clubs:
                t = total_of.get((gid, club))
                if t is None or not (lo_hi[0] <= t < lo_hi[1]):
                    continue
                if cross_club:
                    if len(clubs) != 2:
                        continue
                    other = [c for c in clubs if c != club][0]
                    xa, yb = slot[(gid, club)].get(a), slot[(gid, other)].get(b)
                else:
                    xa, yb = slot[(gid, club)].get(a), slot[(gid, club)].get(b)
                if xa is not None and yb is not None:
                    by_game[gid].append((xa, yb))
        xs = [x for g in by_game for x, _ in by_game[g]]
        ys = [y for g in by_game for _, y in by_game[g]]
        if len(xs) < MIN_PAIRS:
            return {'state': 'NOT_IDENTIFIED_TOO_FEW_PAIRS', 'n_pairs': len(xs)}
        return {'r': round(_pearson(xs, ys), 4), 'n_pairs': len(xs), 'n_games': len(by_game),
                'ci95_game_blocked': _block_bootstrap(by_game)}

    bands = {'total_under_44': (0, 44), 'total_44_to_49': (44, 49), 'total_49_plus': (49, 99)}
    by_total = {}
    for lbl, (a, b) in (('QB1~WR1', ('QB1', 'WR1')), ('QB1~QB1_opp', ('QB1', 'QB1'))):
        by_total[lbl] = {k: conditional(a, b, lbl.endswith('_opp'), v) for k, v in bands.items()}

    art = {
        'ARTIFACT': 'PAIR_CORRELATIONS',
        'PURPOSE': ('the correlation structure a joint game simulator must reproduce. Measured '
                    'from history, so that correlation is never hand-added as a bonus.'),
        'n_player_games': len(pg), 'n_games': len(clubs_in_game),
        'n_player_games_without_pregame_rank': unranked,
        'RANKS_ARE_PREGAME': ('depth rank comes from ROLE_HISTORY for that season and week, not '
                              'from the stat line being measured. Ranking by realised targets '
                              'would manufacture correlation by construction.'),
        'INTERVALS': 'block bootstrap over whole games, 600 reps, players within a game are not '
                     'independent observations',
        'same_club': same,
        'cross_club': cross,
        'conditional_on_total': by_total,
        'MIN_PAIRS': MIN_PAIRS,
    }
    OUT.write_text(json.dumps(art, indent=2))
    ident = [k for k, v in {**same, **cross}.items() if v.get('SIGN_ESTABLISHED')]
    return Outcome.ok('PAIR_CORRELATIONS_MEASURED', value={
        'n_pairs_with_established_sign': len(ident),
        'n_pair_types': len(same) + len(cross),
        'artifact': str(OUT.relative_to(_REPO)),
        'same_club': same, 'cross_club': cross, 'conditional_on_total': by_total,
    })


if __name__ == '__main__':
    o = build()
    print(o.state.value, o.code)
    if o.value:
        for grp in ('same_club', 'cross_club'):
            print(f'--- {grp}')
            for k, v in o.value[grp].items():
                if 'r' in v:
                    ci = v['ci95_game_blocked'] or {}
                    print(f"  {k:14s} r={v['r']:+.4f}  n={v['n_pairs']:5d} games={v['n_games']:4d} "
                          f"ci[{ci.get('lo')},{ci.get('hi')}] sign={'YES' if v['SIGN_ESTABLISHED'] else 'no'}")
                else:
                    print(f"  {k:14s} {v['state']} n={v['n_pairs']}")
        print('--- conditional on total (QB1~WR1 same club)')
        for k, v in o.value['conditional_on_total']['QB1~WR1'].items():
            print(f"  {k:16s} {v.get('r')} n={v.get('n_pairs')}")
    raise SystemExit(0 if o.state.value == 'PASS' else 1)
