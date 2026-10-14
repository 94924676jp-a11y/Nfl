"""D1 ONE-LOOK HOLDOUT on 2025 (PREREG_D1_TARGET_SHRINK.md; w* frozen in D1_ESTIMATE_2024.json @d464f4b1).

    python3.12 nfl/research/benchmark/d1_holdout.py > nfl/research/benchmark/D1_HOLDOUT_2025.json

Applies the pre-registered pass rule verbatim. The caller appends the look to HOLDOUT_LOOKS.jsonl."""
import collections
import json
import random
import statistics
import sys

sys.path.insert(0, '.')
from nfl.tools import forward_chain as F, player_prior as P  # noqa: E402

W_STAR = json.load(open('nfl/research/benchmark/D1_ESTIMATE_2024.json'))['w_star']
SEASON, B, SEED = 2025, 10000, 20261014
po = P.load_panel()
panel, pos_of = po.value, P.position_index()


def run(w):
    F.VINTAGE[0], F.APPLY_APPEARANCE[0], F.D1_W[0] = 'STRICT', True, w
    F.PER_PLAYER_SINK, F.PER_PLAYER_SINK_DFS = [], []
    F.evaluate(panel, pos_of, [SEASON], [('PROD', 1.0, None)])
    return ({(s, wk, g): (pos, pr, a, ap) for (s, wk, _l, g, pos, pr, a, ap, _c) in F.PER_PLAYER_SINK_DFS},
            {(s, wk, g): (pos, pr, a) for (s, wk, _l, g, pos, pr, a) in F.PER_PLAYER_SINK})


inc_u, inc_c = run(None)
d1_u, d1_c = run(W_STAR)
F.D1_W[0] = None
assert set(inc_u) == set(d1_u), 'row sets differ'

hist = collections.defaultdict(list)
cw = collections.defaultdict(set)
for g, ss in panel['players'].items():
    for s, ws in ss.items():
        for w, r in ws.items():
            if r.get('team'):
                hist[g].append((int(s), int(w), F.actual_dk(r)))
                cw[(r['team'], int(s))].add(int(w))


def naive_u(g, s, wk):
    prior = [p for (ss, w, p) in hist[g] if ss == s and w < wk]
    clubs = {r.get('team') for w_, r in (panel['players'][g].get(str(s)) or {}).items() if int(w_) < wk and r.get('team')}
    played = max((len([w for w in cw[(c, s)] if w < wk]) for c in clubs), default=0)
    return (statistics.fmean(prior) * len(prior) / played) if (prior and played) else None


def blocked(keys, f):
    by = collections.defaultdict(list)
    for k in keys:
        by[(k[0], k[1])].append(f(k))
    blocks = list(by.values())
    tot = sum(map(sum, blocks)) / sum(map(len, blocks))
    rg = random.Random(SEED)
    bs = sorted(sum(map(sum, s)) / sum(map(len, s)) for s in ([blocks[rg.randrange(len(blocks))] for _ in blocks] for _ in range(B)))
    return {'diff': round(tot, 4), 'ci95': [round(bs[int(.025 * B)], 4), round(bs[int(.975 * B) - 1], 4)], 'n_weeks': len(blocks), 'n_rows': sum(map(len, blocks))}


K = sorted(inc_u)
res = {'artifact': 'D1_HOLDOUT', 'season': SEASON, 'w_star': W_STAR, 'frozen_at': 'D1_ESTIMATE_2024.json @d464f4b1',
       'n_unconditional': len(K)}
res['unconditional_D1_minus_incumbent'] = blocked(K, lambda k: abs(d1_u[k][1] - d1_u[k][2]) - abs(inc_u[k][1] - inc_u[k][2]))
res['mae'] = {'incumbent': round(statistics.fmean(abs(inc_u[k][1] - inc_u[k][2]) for k in K), 4),
              'D1': round(statistics.fmean(abs(d1_u[k][1] - d1_u[k][2]) for k in K), 4)}
KC = sorted(set(inc_c) & set(d1_c))
res['conditional_D1_minus_incumbent'] = blocked(KC, lambda k: abs(d1_c[k][1] - d1_c[k][2]) - abs(inc_c[k][1] - inc_c[k][2]))
res['by_position_unconditional'] = {p: blocked([k for k in K if inc_u[k][0] == p],
                                               lambda k: abs(d1_u[k][1] - d1_u[k][2]) - abs(inc_u[k][1] - inc_u[k][2]))
                                    for p in ('QB', 'RB', 'WR', 'TE')}
KN = [k for k in K if naive_u(k[2], k[0], k[1]) is not None]
res['vs_naive_STD_U'] = {'n': len(KN),
                         'D1_minus_naive': blocked(KN, lambda k: abs(d1_u[k][1] - d1_u[k][2]) - abs(naive_u(k[2], k[0], k[1]) - d1_u[k][2])),
                         'incumbent_minus_naive': blocked(KN, lambda k: abs(inc_u[k][1] - inc_u[k][2]) - abs(naive_u(k[2], k[0], k[1]) - inc_u[k][2]))}


def top_level(d, keys):
    seg = sorted(keys, key=lambda k: d[k][1])[int(0.9 * len(keys)):]
    seg = [k for k in seg if d[k][0] in ('WR', 'TE')]
    return round(sum(d[k][1] for k in seg) / sum(d[k][2] for k in seg), 4) if seg else None


std = {}
for k in KC:
    prior = [p for (ss, w, p) in hist[k[2]] if ss == k[0] and w < k[1]]
    if prior:
        std[k] = (inc_c[k][0], statistics.fmean(prior), inc_c[k][2])
res['top_decile_wr_te_level_given_play'] = {'incumbent': top_level(inc_c, KC), 'D1': top_level(d1_c, KC),
                                            'naive_control_STD': top_level(std, list(std))}
u = res['unconditional_D1_minus_incumbent']['ci95'][1]
worse = [p for p, v in res['by_position_unconditional'].items() if v['ci95'][0] > 0]
lv = res['top_decile_wr_te_level_given_play']
toward = (lv['D1'] is not None and lv['naive_control_STD'] is not None
          and abs(lv['D1'] - lv['naive_control_STD']) < abs(lv['incumbent'] - lv['naive_control_STD']))
res['PASS_RULE'] = {'upper95_unconditional_below_0': u < 0, 'no_position_worse': not worse, 'positions_worse': worse,
                    'top_decile_level_moves_toward_naive_control': toward}
res['VERDICT'] = 'PASS' if (u < 0 and not worse and toward) else 'FAIL'
print(json.dumps(res, indent=1))
