"""D1 estimation on the DEVELOPMENT season 2024 only (PREREG_D1_TARGET_SHRINK.md + amendment 1). Picks w on a fixed
grid by week-blocked unconditional MAE and writes D1_ESTIMATE_2024.json, which freezes w* BEFORE 2025 is read.

    python3.12 nfl/research/benchmark/d1_estimate.py > nfl/research/benchmark/D1_ESTIMATE_2024.json
"""
import collections
import json
import sys

sys.path.insert(0, '.')
from nfl.tools import forward_chain as F, player_prior as P  # noqa: E402

GRID = [round(0.1 * i, 1) for i in range(11)]
po = P.load_panel()
panel, pos_of = po.value, P.position_index()


def run(w):
    F.VINTAGE[0], F.APPLY_APPEARANCE[0], F.D1_W[0] = 'STRICT', True, w
    F.PER_PLAYER_SINK, F.PER_PLAYER_SINK_DFS = [], []
    F.evaluate(panel, pos_of, [2024], [('PROD', 1.0, None)])
    return [(s, wk, g, pos, pr, a, ap) for (s, wk, _l, g, pos, pr, a, ap, _c) in F.PER_PLAYER_SINK_DFS]


inc = run(None)
res = {'artifact': 'D1_ESTIMATE', 'season': 2024, 'scope': 'DEVELOPMENT ONLY; 2025 not read', 'grid': GRID, 'by_w': {}}
golden = run(0.0)
res['GOLDEN_w0_identical_to_incumbent'] = golden == inc
by_w = {}
for w in GRID:
    rows = golden if w == 0.0 else run(w)
    by = collections.defaultdict(list)
    for (s, wk, g, pos, pr, a, ap) in rows:
        by[(s, wk)].append(abs(pr - a))
    mae = sum(map(sum, by.values())) / sum(map(len, by.values()))
    top = sorted(rows, key=lambda r: r[4])[int(0.9 * len(rows)):]
    wrte = [r for r in top if r[3] in ('WR', 'TE') and r[6]]
    by_w[w] = {'mae_unconditional': round(mae, 5), 'n': len(rows),
               'top_decile_wr_te_level_given_play': round(sum(r[4] for r in wrte) / sum(r[5] for r in wrte), 4) if wrte else None}
res['by_w'] = by_w
w_star = min(GRID, key=lambda w: (by_w[w]['mae_unconditional'], w))
res['w_star'] = w_star
res['FROZEN'] = 'w_star is fixed by this file; the 2025 holdout is read once, with this value, after this file is committed'
print(json.dumps(res, indent=1))
