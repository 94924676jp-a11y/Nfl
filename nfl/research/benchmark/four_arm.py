"""Four-arm evaluation (PREREG_FOUR_ARM.md @0361f6de; owner OD-003): A naive, B1/B2 naive + the slate's own news,
C incumbent prelock forecast, D challenger (NOT_EVALUABLE before W6). Same players, same actuals, same news.

    python3.12 nfl/research/benchmark/four_arm.py SLATES > FOUR_ARM.json      SLATES = EXPLORATORY (2026 W4-W5, inspected)

Writes nothing else. Kickers and team defences are not scored (no panel actuals)."""
import collections
import hashlib
import json
import pathlib
import random
import statistics
import sys

import numpy as np

sys.path.insert(0, '.')
from nfl.tools import availability as AV, forward_chain as F, player_prior as P  # noqa: E402
from nfl.tools.roster_eligibility import CLUB  # noqa: E402

EXPLORATORY = [  # (slate, format, week, state, draws, actuals, game_id or None)
    ('2026W5_SHOWDOWN_TB_DAL', 'SHOWDOWN', 5, 'nfl/dfs/salaries/showdown_tb_dal/OFFICIAL/SHOWDOWN_TB_DAL_2026W5_STATE.json',
     'nfl/dfs/salaries/showdown_tb_dal/OFFICIAL/SHOWDOWN_TB_DAL_2026W5_DRAWS.json',
     'nfl/postgame/showdown_tb_dal_2026W5/TB_DAL_2026W5_POSTGAME.json', '2026_05_TB_DAL'),
    ('2026W4_SHOWDOWN_ATL_NO', 'SHOWDOWN', 4, 'nfl/dfs/salaries/showdown_atl_no/RW_INACTIVES_CHARTFIX/SHOWDOWN_ATL_NO_2026W4_STATE.json',
     'nfl/dfs/salaries/showdown_atl_no/RW_INACTIVES_CHARTFIX/SHOWDOWN_ATL_NO_2026W4_DRAWS.json', 'PANEL', '2026_04_ATL_NO'),
    ('2026W4_SHOWDOWN_PIT_CLE', 'SHOWDOWN', 4, 'nfl/dfs/salaries/SHOWDOWN_TONIGHT_STATE.json',
     'nfl/dfs/salaries/SHOWDOWN_TONIGHT_DRAWS.json', 'PANEL', '2026_04_PIT_CLE'),
    ('2026W4_CLASSIC_EARLY', 'CLASSIC', 4, 'nfl/dfs/salaries/DK_2026W4_EARLY_STATE.json',
     'nfl/dfs/salaries/DK_2026W4_EARLY_DRAWS.json', 'PANEL', None),
]
B, SEED = 10000, 20261014
ARMS = ('A', 'B1', 'B2', 'B3', 'C')

po = P.load_panel()
assert po.state.name == 'PASS', po
panel = po.value['players']
ix, pos_of = P.name_index(), P.position_index()
_cw = {}


def gsis_for(name, club):
    c = CLUB.get(club, club)
    hits = [g for g, (pos, cl, _s) in (ix.get(name) or {}).items() if cl == c]
    return hits[0] if len(hits) == 1 else None


def club_weeks(club):
    c = CLUB.get(club, club)
    if c not in _cw:
        _cw[c] = {int(w) for g, ss in panel.items() for w, r in (ss.get('2026') or {}).items() if r.get('team') == c}
    return _cw[c]


def naive(g, club, week):
    """(per-appearance mean, appearance rate, source) from 2026 weeks before the slate, else 2025."""
    ss = (panel.get(g) or {}).get('2026') or {}
    prior = [F.actual_dk(r) for w, r in ss.items() if int(w) < week and r.get('team')]
    played = len([w for w in club_weeks(club) if w < week])
    if prior and played:
        return statistics.fmean(prior), min(1.0, len(prior) / played), '2026'
    prev = [F.actual_dk(r) for r in ((panel.get(g) or {}).get('2025') or {}).values() if r.get('team')]
    if prev:
        return statistics.fmean(prev), min(1.0, len(prev) / 17.0), '2025'   # 17 = the 2025 regular-season game count
    return 0.0, 0.0, 'NONE'


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


def slate_rows(slate, fmt, week, state_p, draws_p, act_src, game_id):
    st, dr = json.load(open(state_p)), json.load(open(draws_p))
    sha = hashlib.sha256(pathlib.Path(state_p).read_bytes()).hexdigest()
    bound = dr.get('state_sha256') in (None, sha)
    status = {f"{p['name']}|{p['team']}": (p.get('current_availability') or {}).get('status') for p in st['players'].values()}
    desig = {f"{p['name']}|{p['team']}": (p.get('current_availability') or {}).get('designation') for p in st['players'].values()}
    qb_rank = {f"{p['name']}|{p['team']}": p.get('depth_rank') for p in st['players'].values() if p.get('position') == 'QB'}
    post = json.load(open(act_src))['player_actuals'] if act_src != 'PANEL' else None
    club2game = {}
    for gid, v in (dr.get('per_game') or {}).items():
        for c in (v.get('away'), v.get('home')):
            if c:
                club2game[c] = gid
    rows, skipped = [], collections.Counter()
    keys = set(dr['draws']) | {k for k in status}          # players the forecast drew OR the state carried
    for key in sorted(keys):
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
            r = ((panel.get(g) or {}).get('2026') or {}).get(str(week))
            y = F.actual_dk(r) if (r and r.get('team')) else 0.0
        mean, rate, src = naive(g, club, week)
        absent = status.get(key) in AV.ABSENT_STATUSES
        x = dr['draws'].get(key)
        rows.append({'slate': slate, 'format': fmt, 'game': game_id or club2game.get(club, club), 'player': key, 'pos': pos,
                     'actual': y, 'status': status.get(key), 'designation': desig.get(key), 'naive_source': src,
                     'A': mean * rate, 'B1': 0.0 if absent else mean * rate, 'B2': 0.0 if absent else mean,
                     # AMENDMENT 1: the state's QB depth rank is news too; a QB not ranked 1 by the chart scores 0
                     'B3': 0.0 if (absent or (pos == 'QB' and qb_rank.get(key) not in (1, None))) else mean,
                     'C': float(np.mean(x)) if x is not None else 0.0, 'C_has_draws': x is not None})
    return rows, {'state_bound_to_draws': bound, 'state_sha256': sha[:16], 'skipped': dict(skipped)}


def compare(rows):
    out = {'n_players': len(rows), 'n_games': len({r['game'] for r in rows})}
    out['mae'] = {a: round(statistics.fmean(abs(r[a] - r['actual']) for r in rows), 4) for a in ARMS}
    for a in ('A', 'B1', 'B2', 'B3'):
        out[f'C_minus_{a}'] = blocked(rows, lambda r, a=a: abs(r['C'] - r['actual']) - abs(r[a] - r['actual']))
    out['B2_minus_A'] = blocked(rows, lambda r: abs(r['B2'] - r['actual']) - abs(r['A'] - r['actual']))
    return out


rows, meta = [], {}
for spec in EXPLORATORY:
    r, m = slate_rows(*spec)
    rows += r
    meta[spec[0]] = {**m, **compare(r)}
srt = sorted(rows, key=lambda r: r['C'])
terc = {f'T{i + 1}': compare(srt[i * len(srt) // 3:(i + 1) * len(srt) // 3]) for i in range(3)}
res = {'artifact': 'FOUR_ARM', 'prereg': 'nfl/research/benchmark/PREREG_FOUR_ARM.md @0361f6de + AMENDMENT 1 (B3)',
       'LABEL': 'EXPLORATORY: 2026 W4-W5 slates were inspected before this pre-registration; nothing here is confirmatory',
       'D': 'NOT_EVALUABLE: no prelock challenger forecast exists for these slates',
       'pooled': compare(rows), 'by_slate': meta, 'by_C_tercile': terc,
       'by_position': {p: compare([r for r in rows if r['pos'] == p]) for p in ('QB', 'RB', 'WR', 'TE')},
       'by_format': {f: compare([r for r in rows if r['format'] == f]) for f in ('CLASSIC', 'SHOWDOWN')},
       'by_designation': {d: compare(v) for d, v in (lambda g: g)(
           {k: [r for r in rows if (r['designation'] or 'NONE') == k] for k in sorted({(r['designation'] or 'NONE') for r in rows})}).items() if len(v) >= 10},
       'naive_source_counts': dict(collections.Counter(r['naive_source'] for r in rows)),
       'with_2026_history': {'MEANING': 'players whose naive baseline rests on 2026 games (no fallback)',
                             **compare([r for r in rows if r['naive_source'] == '2026'])},
       'with_2026_history_by_position': {p: compare([r for r in rows if r['naive_source'] == '2026' and r['pos'] == p])
                                         for p in ('QB', 'RB', 'WR', 'TE')}}
print(json.dumps(res, indent=1, default=str))
