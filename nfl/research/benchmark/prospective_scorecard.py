"""Benchmark mandate (2026-10-14): score the PRELOCK forecasts this system actually produced in 2026 against realised DK
points, with a naive baseline built from the same information the forecast had.

    python3.12 nfl/research/benchmark/prospective_scorecard.py > PROSPECTIVE.json

Slates: the inventory's EVALUABLE incumbent forecasts (prelock by the artifact's own clock AND by git first-commit;
nfl/research/benchmark/DATA_INVENTORY.json). Research-arm runs (ATL@GB arm A, DET@BUF V1 candidate, NYG@LA arm C) are
scored in a separate block because they are not the production forecast.

Actual DK points: the usage panel's 2026 player-week rows (forward_chain.actual_dk, the same scoring the held-out study
uses) for weeks 1-4; for TB@DAL (week 5, not in the panel) the graded postgame file's dk_A. A drawn skill player with no
panel row that week recorded no opportunity and scores 0 (flagged no_row). Kickers and team defences are NOT scored here
(no panel actuals): they are counted and excluded.

Per player: error of the draw mean, CRPS from the draws (E|X-y| - E|X-X'|/2 with X' an independent permutation),
central 50/80/90% interval coverage, PIT. Baseline STD_U: his 2026 per-appearance mean before the week x his appearance
rate before the week (club weeks). Uncertainty: GAME-blocked bootstrap (players in one game are not independent)."""
import collections
import json
import pathlib
import random
import statistics
import sys

import numpy as np

sys.path.insert(0, '.')
from nfl.tools import forward_chain as F, player_prior as P  # noqa: E402
from nfl.tools.roster_eligibility import CLUB  # noqa: E402  (DK -> nflverse club codes)

INC = [  # (slate, game_id, week, draws path, actual source)
    ('2026W5_SHOWDOWN_TB_DAL', ['2026_05_TB_DAL'], 5, 'nfl/dfs/salaries/showdown_tb_dal/OFFICIAL/SHOWDOWN_TB_DAL_2026W5_DRAWS.json',
     'nfl/postgame/showdown_tb_dal_2026W5/TB_DAL_2026W5_POSTGAME.json'),
    ('2026W4_SHOWDOWN_ATL_NO', ['2026_04_ATL_NO'], 4,
     'nfl/dfs/salaries/showdown_atl_no/RW_INACTIVES_CHARTFIX/SHOWDOWN_ATL_NO_2026W4_DRAWS.json', 'PANEL'),
    ('2026W4_SHOWDOWN_PIT_CLE', ['2026_04_PIT_CLE'], 4, 'nfl/dfs/salaries/SHOWDOWN_TONIGHT_DRAWS.json', 'PANEL'),
    ('2026W4_CLASSIC_EARLY', None, 4, 'nfl/dfs/salaries/DK_2026W4_EARLY_DRAWS.json', 'PANEL'),
]
B, SEED = 10000, 20261014

po = P.load_panel()
assert po.state.name == 'PASS', po
panel = po.value['players']
ix = P.name_index()
pos_of = P.position_index()


def gsis_for(name, club):
    c = CLUB.get(club, club)
    hits = [g for g, (pos, cl, _s) in (ix.get(name) or {}).items() if cl == c]
    return hits[0] if len(hits) == 1 else None


def club_weeks(club, season=2026):
    c = CLUB.get(club, club)
    return {int(w) for g, ss in panel.items() for w, r in (ss.get(str(season)) or {}).items() if r.get('team') == c}


_CW = {}


def baseline(g, club, week):
    ss = (panel.get(g) or {}).get('2026') or {}
    prior = [F.actual_dk(r) for w, r in ss.items() if int(w) < week and r.get('team')]
    cw = _CW.setdefault(club, club_weeks(club))
    played = len([w for w in cw if w < week])
    if not prior or not played:
        return None
    return statistics.fmean(prior) * (len(prior) / played)


def crps(x, y, rng):
    x = np.asarray(x, float)
    return float(np.mean(np.abs(x - y)) - 0.5 * np.mean(np.abs(x - rng.permutation(x))))


def score_slate(slate, games, week, draws_p, actual_src):
    d = json.load(open(draws_p))
    draws = d['draws']
    post = json.load(open(actual_src))['player_actuals'] if actual_src != 'PANEL' else None
    rng = np.random.default_rng(SEED)
    rows, skipped = [], collections.Counter()
    for key, x in draws.items():
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
            y, no_row = float(a['dk_A']), False
        else:
            r = ((panel.get(g) or {}).get('2026') or {}).get(str(week))
            y, no_row = (F.actual_dk(r), False) if (r and r.get('team')) else (0.0, True)
        x = np.asarray(x, float)
        q = np.quantile(x, [0.05, 0.10, 0.25, 0.75, 0.90, 0.95])
        game = (games[0] if games else f"{club}")   # classic: the club, mapped to its game below
        rows.append({'slate': slate, 'player': key, 'pos': pos, 'club': club, 'game': game, 'mean': float(x.mean()),
                     'actual': y, 'no_row': no_row, 'crps': crps(x, y, rng), 'pit': float((x < y).mean() + 0.5 * (x == y).mean()),
                     'in50': bool(q[2] <= y <= q[3]), 'in80': bool(q[1] <= y <= q[4]), 'in90': bool(q[0] <= y <= q[5]),
                     'STD_U': baseline(g, club, week)})
    if games is None:   # Classic: one cluster per game, from the draws' per_game block
        club2game = {}
        for gid, v in (d.get('per_game') or {}).items():
            for c in (v.get('away'), v.get('home')):
                if c:
                    club2game[c] = gid
        for r in rows:
            r['game'] = club2game.get(r['club'], r['club'])
    return rows, dict(skipped), {'n_sims': d.get('n_sims'), 'market_arm': d.get('market_arm'),
                                 'projection_sha256': d.get('projection_sha256')}


def blocked(rows, f):
    by = collections.defaultdict(list)
    for r in rows:
        by[r['game']].append(f(r))
    blocks = list(by.values())
    tot = sum(map(sum, blocks)) / sum(map(len, blocks))
    rg = random.Random(SEED)
    bs = sorted(sum(map(sum, s)) / sum(map(len, s)) for s in
                ([blocks[rg.randrange(len(blocks))] for _ in blocks] for _ in range(B)))
    return {'value': round(tot, 4), 'ci95': [round(bs[int(.025 * B)], 4), round(bs[int(.975 * B) - 1], 4)],
            'n_games': len(blocks), 'n_players': sum(map(len, blocks))}


def summary(rows):
    both = [r for r in rows if r['STD_U'] is not None]
    pit = [r['pit'] for r in rows]
    return {'n_players': len(rows), 'n_games': len({r['game'] for r in rows}),
            'mae_mean': blocked(rows, lambda r: abs(r['mean'] - r['actual'])),
            'bias_mean': blocked(rows, lambda r: r['mean'] - r['actual']),
            'crps': blocked(rows, lambda r: r['crps']),
            'coverage': {'nominal50': round(statistics.fmean(r['in50'] for r in rows), 3),
                         'nominal80': round(statistics.fmean(r['in80'] for r in rows), 3),
                         'nominal90': round(statistics.fmean(r['in90'] for r in rows), 3)},
            'pit_deciles': [round(sum(1 for p in pit if i / 10 <= p < (i + 1) / 10 or (i == 9 and p == 1.0)) / len(pit), 3)
                            for i in range(10)],
            'vs_naive_STD_U': {'n_players': len(both),
                               'mae_forecast_minus_naive': blocked(both, lambda r: abs(r['mean'] - r['actual']) - abs(r['STD_U'] - r['actual'])),
                               'mae_naive': round(statistics.fmean(abs(r['STD_U'] - r['actual']) for r in both), 4) if both else None,
                               'MEANING': 'positive = the forecast mean was further from the result than the naive baseline'},
            'n_no_row_zero': sum(r['no_row'] for r in rows)}


allrows, meta = [], {}
for slate, games, week, dp, src in INC:
    rows, skipped, m = score_slate(slate, games, week, dp, src)
    allrows += rows
    meta[slate] = {**m, 'draws': dp, 'actuals': src, 'skipped': skipped, **summary(rows)}
out = {'artifact': 'PROSPECTIVE_SCORECARD', 'spec': 'benchmark-prospective-1',
       'scope': 'INCUMBENT prelock forecasts, 2026 W4-W5, skill positions; kickers and DST excluded',
       'LIMITS': ['few games: game-blocked intervals are wide and a single slate is anecdote, not evidence',
                  'actuals for W4 from the usage panel (skill opportunity rows); TB@DAL from its graded postgame file',
                  'naive baseline uses only 2026 weeks before the slate; it has no injury information (the forecast did)'],
       'pooled': summary(allrows),
       'by_forecast_tercile': {f'T{i + 1}': summary(seg) for i, seg in enumerate(
           (lambda rs: [rs[k * len(rs) // 3:(k + 1) * len(rs) // 3] for k in range(3)])(sorted(allrows, key=lambda r: r['mean'])))},
       'DIAGNOSTIC_ONLY_played_only': {
           'NOT_CALIBRATION_EVIDENCE': ('selected on the OUTCOME (he played): removing realised zeros pushes outcomes '
                                        'into the tails by construction. Coverage here is not evidence of dispersion; use '
                                        'by_forecast_tercile, which is defined on the prediction.'),
           **summary([r for r in allrows if not r['no_row']])},
       'by_slate': meta,
       'by_position': {p: summary([r for r in allrows if r['pos'] == p]) for p in ('QB', 'RB', 'WR', 'TE')
                       if sum(r['pos'] == p for r in allrows) >= 10}}
# cross-check: panel actuals vs the ATL@NO graded postgame file (same scoring?)
pa = json.load(open('nfl/postgame/showdown_atl_no_2026W4/ATL_NO_POSTGAME_ACTUAL.json'))['player_actuals']
chk = [(r['player'], r['actual'], pa[r['player']]['dk_A']) for r in allrows
       if r['slate'] == '2026W4_SHOWDOWN_ATL_NO' and r['player'] in pa]
out['actuals_crosscheck_ATL_NO'] = {'n': len(chk), 'max_abs_diff': round(max(abs(a - b) for _, a, b in chk), 3) if chk else None,
                                    'mismatches': [c for c in chk if abs(c[1] - c[2]) > 0.05][:10]}
print(json.dumps(out, indent=1, default=str))
