"""JOINT_CALIBRATION_SCORECARD (mandate b0540a52 phase 4): do the PRELOCK joint worlds get club totals, QB stacks and
QB-receiver dependence right against what happened?

    python3.12 nfl/research/benchmark/joint_calibration.py > nfl/research/benchmark/JOINT_CALIBRATION_SCORECARD.json

Slates: the four incumbent prelock forecasts scored in PROSPECTIVE_SCORECARD (same draws, same actual sources). The
draws are world-aligned (index i is one simulated world for every player; declared by `world_points` on the showdown
files, and visible as non-zero within-club correlation on all four).

Units, all defined before the game from the draws' own player set:
  CLUB   the sum of a club's scored skill players' DK points (players with a resolved identity and an actual)
  STACK  the club's QB with the most mean DK points plus his two pass catchers (WR/TE) with the most mean DK points
  PAIR   that QB with each of those two pass catchers
Scores:
  PIT, central 50/80/90% coverage of CLUB and STACK sums
  CRPS of the JOINT sum minus CRPS of the same sum with every player's draws permuted independently (dependence
       removed, marginals unchanged); negative = the simulated dependence improves the forecast of the sum
  PAIR dependence: the simulated Spearman correlation vs the realised mean product of normal scores
       z = Phi^-1(PIT) of the two players (one observation per pair; its mean estimates the copula correlation)
Uncertainty: GAME-blocked bootstrap, 10,000, seed 20261014. Exploratory: these slates were inspected before.
Kickers and team defences are not scored (no actuals)."""
import collections
import json
import random
import statistics
import sys
from statistics import NormalDist

import numpy as np

sys.path.insert(0, '.')
from nfl.tools import forward_chain as F, player_prior as P  # noqa: E402
from nfl.tools.roster_eligibility import CLUB  # noqa: E402

INC = [
    ('2026W5_SHOWDOWN_TB_DAL', ['2026_05_TB_DAL'], 5, 'nfl/dfs/salaries/showdown_tb_dal/OFFICIAL/SHOWDOWN_TB_DAL_2026W5_DRAWS.json',
     'nfl/postgame/showdown_tb_dal_2026W5/TB_DAL_2026W5_POSTGAME.json'),
    ('2026W4_SHOWDOWN_ATL_NO', ['2026_04_ATL_NO'], 4,
     'nfl/dfs/salaries/showdown_atl_no/RW_INACTIVES_CHARTFIX/SHOWDOWN_ATL_NO_2026W4_DRAWS.json', 'PANEL'),
    ('2026W4_SHOWDOWN_PIT_CLE', ['2026_04_PIT_CLE'], 4, 'nfl/dfs/salaries/SHOWDOWN_TONIGHT_DRAWS.json', 'PANEL'),
    ('2026W4_CLASSIC_EARLY', None, 4, 'nfl/dfs/salaries/DK_2026W4_EARLY_DRAWS.json', 'PANEL'),
]
B, SEED = 10000, 20261014
ND = NormalDist()
po = P.load_panel()
assert po.state.name == 'PASS', po
panel = po.value['players']
ix = P.name_index()
pos_of = P.position_index()


def gsis_for(name, club):
    c = CLUB.get(club, club)
    hits = [g for g, (pos, cl, _s) in (ix.get(name) or {}).items() if cl == c]
    return hits[0] if len(hits) == 1 else None


def pit(x, y):
    return float((x < y).mean() + 0.5 * (x == y).mean())


def crps(x, y, rng):
    return float(np.mean(np.abs(x - y)) - 0.5 * np.mean(np.abs(x - rng.permutation(x))))


def cover(x, y):
    q = np.quantile(x, [0.05, 0.10, 0.25, 0.75, 0.90, 0.95])
    return {'in50': bool(q[2] <= y <= q[3]), 'in80': bool(q[1] <= y <= q[4]), 'in90': bool(q[0] <= y <= q[5])}


def spearman(a, b):
    ra, rb = np.argsort(np.argsort(a)), np.argsort(np.argsort(b))
    return float(np.corrcoef(ra, rb)[0, 1])


rng = np.random.default_rng(SEED)
units, pairs, skipped, meta = [], [], collections.Counter(), {}
for slate, games, week, dp, src in INC:
    d = json.load(open(dp))
    post = json.load(open(src))['player_actuals'] if src != 'PANEL' else None
    club2game = {}
    for gid, v in (d.get('per_game') or {}).items():
        for c in (v.get('away'), v.get('home'), *gid.split('_')[2:4]):   # BENCH-D4: clubs from the game id
            if c:
                club2game[c] = gid
    by_club = collections.defaultdict(list)
    for key, x in d['draws'].items():
        name, club = key.rsplit('|', 1)
        g = gsis_for(name, club)
        pos = pos_of.get(g) if g else None
        if pos not in ('QB', 'RB', 'WR', 'TE'):
            skipped['not_skill_or_unresolved'] += 1
            continue
        if post is not None:
            a = post.get(key)
            if a is None:
                skipped['no_postgame_row'] += 1
                continue
            y = float(a['dk_A'])
        else:
            r = (((panel.get(g) or {}).get('2026') or {}).get(str(week)))
            y = F.actual_dk(r) if (r and r.get('team')) else 0.0
        by_club[club].append({'key': key, 'pos': pos, 'x': np.asarray(x, float), 'y': y})
    meta[slate] = {'n_sims': d.get('n_sims'), 'n_clubs': len(by_club), 'draws': dp}
    for club, pl in by_club.items():
        game = games[0] if games else club2game[club]   # BENCH-D4: never a club-sized cluster
        lens = {len(p['x']) for p in pl}
        assert len(lens) == 1, f'WORLDS_NOT_ALIGNED {slate} {club} {lens}'
        qbs = sorted([p for p in pl if p['pos'] == 'QB'], key=lambda p: -p['x'].mean())
        rec = sorted([p for p in pl if p['pos'] in ('WR', 'TE')], key=lambda p: -p['x'].mean())
        groups = {'CLUB': pl}
        if qbs and len(rec) >= 2:
            groups['STACK'] = [qbs[0]] + rec[:2]
            for rc in rec[:2]:
                zq = ND.inv_cdf(min(max(pit(qbs[0]['x'], qbs[0]['y']), 1e-3), 1 - 1e-3))
                zr = ND.inv_cdf(min(max(pit(rc['x'], rc['y']), 1e-3), 1 - 1e-3))
                pairs.append({'slate': slate, 'game': game, 'qb': qbs[0]['key'], 'rec': rc['key'],
                              'sim_spearman': spearman(qbs[0]['x'], rc['x']), 'realised_z_product': zq * zr})
        for kind, members in groups.items():
            xj = np.sum([p['x'] for p in members], axis=0)
            xi = np.sum([rng.permutation(p['x']) for p in members], axis=0)
            y = sum(p['y'] for p in members)
            units.append({'slate': slate, 'game': game, 'club': club, 'kind': kind, 'n_players': len(members),
                          'mean': float(xj.mean()), 'actual': y, 'pit': pit(xj, y), **cover(xj, y),
                          'crps_joint': crps(xj, y, rng), 'crps_independent': crps(xi, y, rng),
                          'sd_joint': float(xj.std()), 'sd_independent': float(xi.std())})


def blocked(rows, f):
    by = collections.defaultdict(list)
    for r in rows:
        by[r['game']].append(f(r))
    blocks = list(by.values())
    tot = sum(map(sum, blocks)) / sum(map(len, blocks))
    rg = random.Random(SEED)
    bs = sorted(sum(map(sum, s)) / sum(map(len, s)) for s in ([blocks[rg.randrange(len(blocks))] for _ in blocks] for _ in range(B)))
    return {'value': round(tot, 4), 'ci95': [round(bs[int(.025 * B)], 4), round(bs[int(.975 * B) - 1], 4)],
            'n_games': len(blocks), 'n_units': sum(map(len, blocks))}


def summarise(rows):
    p = [r['pit'] for r in rows]
    return {'n_units': len(rows), 'n_games': len({r['game'] for r in rows}),
            'bias_mean': blocked(rows, lambda r: r['mean'] - r['actual']),
            'coverage': {f'nominal{k}': round(statistics.fmean(r[f'in{k}'] for r in rows), 3) for k in (50, 80, 90)},
            'pit_quintiles': [round(sum(1 for v in p if i / 5 <= v < (i + 1) / 5 or (i == 4 and v == 1.0)) / len(p), 3) for i in range(5)],
            'pit_mean': round(statistics.fmean(p), 4),
            'crps_joint_minus_independent': blocked(rows, lambda r: r['crps_joint'] - r['crps_independent']),
            'sd_ratio_joint_over_independent_mean': round(statistics.fmean(r['sd_joint'] / r['sd_independent'] for r in rows if r['sd_independent'] > 0), 4)}


out = {'artifact': 'JOINT_CALIBRATION_SCORECARD', 'mandate': 'b0540a52 phase 4',
       'LABEL': 'EXPLORATORY: 2026 W4-W5 prelock worlds, already inspected',
       'slates': meta, 'skipped': dict(skipped),
       'CLUB': summarise([u for u in units if u['kind'] == 'CLUB']),
       'STACK_QB_plus_top2_pass_catchers': summarise([u for u in units if u['kind'] == 'STACK']),
       'PAIR_QB_pass_catcher': {'n_pairs': len(pairs), 'n_games': len({p['game'] for p in pairs}),
                                'mean_simulated_spearman': round(statistics.fmean(p['sim_spearman'] for p in pairs), 4),
                                'realised_mean_z_product': blocked(pairs, lambda p: p['realised_z_product']),
                                'simulated_minus_realised': blocked(pairs, lambda p: p['sim_spearman'] - p['realised_z_product']),
                                'MEANING': ('realised_mean_z_product estimates the copula (normal-scores) correlation from one '
                                            'outcome per pair; compare it with the simulated rank correlation')},
       'NOT_SCORED': {'K_DST': 'no panel actuals', 'game_totals_points': 'club fantasy sums are scored; real scorelines are not joined here'},
       'units': units, 'pairs': pairs}
print(json.dumps(out, indent=1))
