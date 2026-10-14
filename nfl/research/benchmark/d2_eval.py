"""D2 evaluation (PREREG_D2_APPEARANCE.md @554eb007; parameters frozen in D2_PARAMS.json @f8c5be88).

    python3.12 nfl/research/benchmark/d2_eval.py 2024 > nfl/research/benchmark/D2_DEV_2024.json      # all four arms
    python3.12 nfl/research/benchmark/d2_eval.py 2025 > nfl/research/benchmark/D2_LOOK_2025.json     # D2-ROLE only

2024 is DEVELOPMENT (descriptive). 2025 is the single logged look, PREVIOUSLY_INSPECTED_SEASON, and applies the
registered pass rule verbatim; the caller appends the look to HOLDOUT_LOOKS.jsonl."""
import collections
import json
import math
import random
import statistics
import sys

sys.path.insert(0, '.')
from nfl.tools import forward_chain as F, player_prior as P  # noqa: E402

SEASON = int(sys.argv[1])
assert SEASON in (2024, 2025), 'D2_EVAL_SEASON_NOT_REGISTERED'
ARMS = ('NONE', 'CURRENT', 'SHRINK', 'ROLE') if SEASON == 2024 else ('ROLE',)
PARAMS = json.load(open('nfl/research/benchmark/D2_PARAMS.json'))
B, SEED = 10000, 20261014
po = P.load_panel()
panel, pos_of = po.value, P.position_index()


def run(arm):
    F.VINTAGE[0], F.APPLY_APPEARANCE[0], F.D1_W[0] = 'STRICT', True, None
    F.D2_ARM[0], F.D2_PARAMS[0] = arm, (PARAMS if arm else None)
    F.PER_PLAYER_SINK, F.PER_PLAYER_SINK_DFS, F.PROJ_COMPONENT_SINK = [], [], []
    F.D2_FEATURE_SINK = [] if arm is None else None
    F.evaluate(panel, pos_of, [SEASON], [('PROD', 1.0, None)])
    u = {(s, wk, g): (pos, pr, a, ap) for (s, wk, _l, g, pos, pr, a, ap, _c) in F.PER_PLAYER_SINK_DFS}
    c = {(s, wk, g): (pos, pr, a) for (s, wk, _l, g, pos, pr, a) in F.PER_PLAYER_SINK}
    comp = {(r['season'], r['week'], r['gsis']): r for r in F.PROJ_COMPONENT_SINK}
    feats = ({(s, wk, g): (pos, role, n, N) for (s, wk, g, pos, role, n, N) in F.D2_FEATURE_SINK}
             if F.D2_FEATURE_SINK is not None else None)
    return u, c, comp, feats


inc_u, inc_c, inc_comp, FEATS = run(None)
arms = {a: run(a)[:2] for a in ARMS}
F.D2_ARM[0], F.D2_PARAMS[0], F.D2_FEATURE_SINK = None, None, None
for a, (u, _c) in arms.items():
    assert set(u) == set(inc_u), f'row sets differ for {a}'
K = sorted(inc_u)

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
    if not blocks:
        return None
    tot = sum(map(sum, blocks)) / sum(map(len, blocks))
    rg = random.Random(SEED)
    bs = sorted(sum(map(sum, s)) / sum(map(len, s)) for s in ([blocks[rg.randrange(len(blocks))] for _ in blocks] for _ in range(B)))
    return {'diff': round(tot, 4), 'ci95': [round(bs[int(.025 * B)], 4), round(bs[int(.975 * B) - 1], 4)],
            'n_weeks': len(blocks), 'n_rows': sum(map(len, blocks))}


def p_inc(k):
    pp = (inc_comp.get(k) or {}).get('p_plays') or {}
    v = [x for x in pp.values() if isinstance(x, (int, float))]
    return max(v) if v else None


def q_of(arm, k):
    f = FEATS.get(k)
    if f is None:
        return None
    if arm == 'CURRENT':
        return p_inc(k)
    return F.d2_q(arm, PARAMS, f[0], f[1], f[2], f[3])


def last_flag(k):
    f = FEATS.get(k)
    return None if f is None else f[1].endswith('|1')


def top_level(d, keys):
    seg = sorted(keys, key=lambda k: d[k][1])[int(0.9 * len(keys)):]
    seg = [k for k in seg if d[k][0] in ('WR', 'TE')]
    return round(sum(d[k][1] for k in seg) / sum(d[k][2] for k in seg), 4) if seg else None


def ae(d, k):
    return abs(d[k][1] - d[k][2])


KA = [k for k in K if p_inc(k) is not None and FEATS.get(k) is not None]
KN = [k for k in K if naive_u(k[2], k[0], k[1]) is not None]
KC = sorted(inc_c)
std = {}
for k in KC:
    prior = [p for (ss, w, p) in hist[k[2]] if ss == k[0] and w < k[1]]
    if prior:
        std[k] = (inc_c[k][0], statistics.fmean(prior), inc_c[k][2])


def brier(fp, keys):
    return round(statistics.fmean((fp(k) - (1.0 if inc_u[k][3] else 0.0)) ** 2 for k in keys), 5)


def logloss(fp, keys, eps=0.01):
    cl = lambda x: min(max(x, eps), 1 - eps)  # noqa: E731
    return round(-statistics.fmean((1.0 if inc_u[k][3] else 0.0) * math.log(cl(fp(k)))
                                   + (0.0 if inc_u[k][3] else 1.0) * math.log(1 - cl(fp(k))) for k in keys), 5)


res = {'artifact': f'D2_{"DEV" if SEASON == 2024 else "LOOK"}_{SEASON}', 'season': SEASON,
       'prereg': 'PREREG_D2_APPEARANCE.md @554eb007', 'params': 'D2_PARAMS.json @f8c5be88',
       'status': ('DEVELOPMENT: descriptive; 2024 diagnosed APPEAR-D1 and cannot confirm the fix' if SEASON == 2024 else
                  'ONE LOGGED LOOK, PREVIOUSLY_INSPECTED_SEASON (2025 aggregates seen in PLAYER_SCORECARD and the D1 look)'),
       'n_unconditional': len(K), 'n_appeared_rows': len(KC), 'n_appearance_rows': len(KA),
       'mae_unconditional': {'incumbent': round(statistics.fmean(ae(inc_u, k) for k in K), 4),
                             **{a: round(statistics.fmean(ae(u, k) for k in K), 4) for a, (u, _c) in arms.items()}},
       'appearance_incumbent': {'brier': brier(p_inc, KA), 'log_loss_clip_0_01': logloss(p_inc, KA)},
       'naive_STD_U_mae': round(statistics.fmean(abs(naive_u(k[2], k[0], k[1]) - inc_u[k][2]) for k in KN), 4),
       'top_decile_wr_te_level_given_play': {'incumbent': top_level(inc_c, KC), 'naive_control_STD': top_level(std, list(std))},
       'arms': {}}
for a, (u, c) in arms.items():
    KCa = sorted(set(inc_c) & set(c))
    e = {'unconditional_minus_incumbent': blocked(K, lambda k: ae(u, k) - ae(inc_u, k)),
         # the SAME unconditional projection scored only where the player appeared: an outcome-selected subset, so it
         # is a diagnostic (it rewards raising the players who turn out); not PLAYER_SCORECARD's appearance-OFF object
         'appeared_rows_minus_incumbent_DIAGNOSTIC': blocked(KCa, lambda k: ae(c, k) - ae(inc_c, k)),
         'by_position_unconditional': {p: blocked([k for k in K if inc_u[k][0] == p], lambda k: ae(u, k) - ae(inc_u, k))
                                       for p in ('QB', 'RB', 'WR', 'TE')},
         'by_last_game_stratum_unconditional': {
             s: blocked([k for k in K if last_flag(k) is v], lambda k: ae(u, k) - ae(inc_u, k))
             for s, v in (('appeared_last_club_game', True), ('missed_last_club_game', False))},
         'minus_naive_STD_U': blocked(KN, lambda k: ae(u, k) - abs(naive_u(k[2], k[0], k[1]) - u[k][2])),
         'top_decile_wr_te_level_given_play': top_level(c, KCa)}
    if a != 'NONE':
        e['appearance'] = {'brier': brier(lambda k: q_of(a, k), KA), 'log_loss_clip_0_01': logloss(lambda k: q_of(a, k), KA),
                           'brier_minus_incumbent': blocked(KA, lambda k: (q_of(a, k) - (1.0 if inc_u[k][3] else 0.0)) ** 2
                                                            - (p_inc(k) - (1.0 if inc_u[k][3] else 0.0)) ** 2)}
    res['arms'][a] = e
res['incumbent_minus_naive_STD_U'] = blocked(KN, lambda k: ae(inc_u, k) - abs(naive_u(k[2], k[0], k[1]) - inc_u[k][2]))
if SEASON == 2025:
    e = res['arms']['ROLE']
    up = e['unconditional_minus_incumbent']['ci95'][1]
    worse = [p for p, v in e['by_position_unconditional'].items() if v and v['ci95'][0] > 0]
    br = e['appearance']['brier'] < res['appearance_incumbent']['brier']
    res['PASS_RULE'] = {'upper95_unconditional_below_0': up < 0, 'no_position_worse': not worse, 'positions_worse': worse,
                        'appearance_brier_below_incumbent': br}
    res['VERDICT'] = 'PASS' if (up < 0 and not worse and br) else 'FAIL'
    res['CONFIRMATION'] = 'NOT_CONFIRMED whatever the verdict: only a prelock prospective arm (W6 onward) can confirm'
print(json.dumps(res, indent=1))
