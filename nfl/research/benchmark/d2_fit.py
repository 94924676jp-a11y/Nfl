"""D2 parameter fit on TRAINING VINTAGES 2022-2023 ONLY (PREREG_D2_APPEARANCE.md @554eb007).

    python3.12 nfl/research/benchmark/d2_fit.py > nfl/research/benchmark/D2_PARAMS.json

Production settings (STRICT, appearance ON, D1 off, D2 off), with the D2 feature sink on. Each scored unconditional
pool row (the PER_PLAYER_SINK_DFS universe) is joined to its pregame D2 features. m_role is the observed appearance
rate in the role (fewer than 30 rows -> the position's rate); kappa is the grid value minimising training Brier.
2024 and 2025 are not read."""
import collections
import json
import statistics
import sys

sys.path.insert(0, '.')
from nfl.tools import forward_chain as F, player_prior as P  # noqa: E402

TRAIN, GRID, MIN_ROLE_ROWS = (2022, 2023), (0.5, 1, 2, 3, 5, 8, 13, 21), 30
F.VINTAGE[0], F.APPLY_APPEARANCE[0], F.D1_W[0], F.D2_ARM[0] = 'STRICT', True, None, None
F.PER_PLAYER_SINK_DFS, F.D2_FEATURE_SINK = [], []
po = P.load_panel()
panel, pos_of = po.value, P.position_index()
F.evaluate(panel, pos_of, list(TRAIN), [('PROD', 1.0, None)])
feat = {(s, wk, g): (pos, role, n, N) for (s, wk, g, pos, role, n, N) in F.D2_FEATURE_SINK}
rows = []
for (s, wk, _l, g, pos, _pr, _a, ap, _c) in F.PER_PLAYER_SINK_DFS:
    f = feat.get((s, wk, g))
    assert s in TRAIN, f'NON_TRAINING_SEASON_READ {s}'
    if f is not None:
        rows.append((f[0], f[1], f[2], f[3], 1.0 if ap else 0.0))
assert rows, 'D2_FIT_NO_TRAINING_ROWS'
pooled = statistics.fmean(r[4] for r in rows)
by_pos = collections.defaultdict(list)
by_role = collections.defaultdict(list)
for r in rows:
    by_pos[r[0]].append(r[4])
    by_role[r[1]].append(r[4])
m_pos = {p: round(statistics.fmean(v), 6) for p, v in by_pos.items()}
m_role = {k: round(statistics.fmean(v), 6) for k, v in by_role.items() if len(v) >= MIN_ROLE_ROWS}


def brier(kappa, mfun):
    return statistics.fmean(((n + kappa * mfun(r)) / (N + kappa) - y) ** 2 for r in rows for (n, N, y) in [(r[2], r[3], r[4])])


grid_shrink = {k: round(brier(k, lambda r: pooled), 6) for k in GRID}
grid_role = {k: round(brier(k, lambda r: m_role.get(r[1], m_pos[r[0]])), 6) for k in GRID}
k_shrink = min(grid_shrink, key=grid_shrink.get)
k_role = min(grid_role, key=grid_role.get)
print(json.dumps({
    'artifact': 'D2_PARAMS', 'prereg': 'PREREG_D2_APPEARANCE.md @554eb007', 'training_seasons': list(TRAIN),
    'n_training_rows': len(rows), 'n_feature_rows': len(feat),
    'training_role_counts': {k: len(v) for k, v in sorted(by_role.items())},
    'SHRINK': {'kappa': k_shrink, 'm_pooled': round(pooled, 6), 'training_brier_grid': grid_shrink},
    'ROLE': {'kappa': k_role, 'm_role': dict(sorted(m_role.items())), 'm_pos': m_pos, 'min_role_rows': MIN_ROLE_ROWS,
             'training_brier_grid': grid_role},
    'FROZEN': 'written before 2024 is scored with D2; nothing is re-fitted afterwards'}, indent=1))
