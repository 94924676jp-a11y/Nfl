"""OD-003 diagnosis, DEVELOPMENT SEASON ONLY (2024; PREREG_FOUR_ARM data separation): decompose the production
projection's error into participation, opportunity and efficiency, for the player-weeks where lineups are built.

    python3.12 nfl/research/benchmark/decompose_dev.py > DECOMPOSE_2024.json

The forward chain runs at production settings (STRICT vintage, appearance ON). Per player-week we have the projected
components (targets, receptions, yards, TDs, carries, pass volume) and the realised box score. Decomposition, given that
the player PLAYED:
  opportunity  projected targets (or carries, or pass attempts) / actual
  efficiency   projected points per opportunity / actual points per opportunity
  touchdowns   projected TDs / actual TDs
  yards        projected yards per target (receivers) / actual
Products of ratios are reported as ratios of SUMS over the segment (not means of ratios), so one player with one target
cannot dominate. 2025 is NOT touched by this script."""
import collections
import json
import sys

sys.path.insert(0, '.')
from nfl.tools import forward_chain as F, player_prior as P  # noqa: E402

F.VINTAGE[0] = 'STRICT'
F.APPLY_APPEARANCE[0] = True
F.PER_PLAYER_SINK, F.PROJ_COMPONENT_SINK = [], []
po = P.load_panel()
panel = po.value
F.evaluate(panel, P.position_index(), [2024], [('PROD', 1.0, None)])
proj = {(r['season'], r['week'], r['gsis']): r for r in F.PROJ_COMPONENT_SINK}
rows = []
for (season, week, label, g, pos, pts, actual) in F.PER_PLAYER_SINK:     # conditional: he played
    c = proj.get((season, week, g))
    a = panel['players'][g][str(season)][str(week)]
    if c is None:
        continue
    rows.append({'pos': pos, 'proj': pts, 'actual': actual, 'p': c, 'a': a})


def ratio(seg, f_p, f_a):
    sp, sa = sum(f_p(r) or 0.0 for r in seg), sum(f_a(r) or 0.0 for r in seg)
    return {'proj_sum': round(sp, 2), 'actual_sum': round(sa, 2), 'ratio': round(sp / sa, 4) if sa else None}


def decompose(seg, pos):
    p, a = (lambda r, k: r['p'].get(k)), (lambda r, k: r['a'].get(k))
    out = {'n': len(seg), 'points': ratio(seg, lambda r: r['proj'], lambda r: r['actual'])}
    if pos in ('WR', 'TE', 'RB'):
        out['targets'] = ratio(seg, lambda r: p(r, 'targets'), lambda r: a(r, 'targets'))
        out['receptions'] = ratio(seg, lambda r: p(r, 'receptions'), lambda r: a(r, 'receptions'))
        out['rec_yards'] = ratio(seg, lambda r: p(r, 'rec_yards'), lambda r: a(r, 'rec_yards'))
        out['rec_td'] = ratio(seg, lambda r: p(r, 'rec_td'), lambda r: a(r, 'rec_td'))
        t = out['targets']
        if t['proj_sum'] and t['actual_sum']:
            out['catch_rate'] = {'proj': round(out['receptions']['proj_sum'] / t['proj_sum'], 4),
                                 'actual': round(out['receptions']['actual_sum'] / t['actual_sum'], 4)}
            out['yards_per_target'] = {'proj': round(out['rec_yards']['proj_sum'] / t['proj_sum'], 3),
                                       'actual': round(out['rec_yards']['actual_sum'] / t['actual_sum'], 3)}
            out['points_per_target_ex_rush'] = {
                'proj': round(sum((p(r, 'receptions') or 0) + 0.1 * (p(r, 'rec_yards') or 0) + 6 * (p(r, 'rec_td') or 0) for r in seg) / t['proj_sum'], 3),
                'actual': round(sum((a(r, 'receptions') or 0) + 0.1 * (a(r, 'rec_yards') or 0) + 6 * (a(r, 'rec_td') or 0) for r in seg) / t['actual_sum'], 3),
                'NOTE': 'DK receiving scoring 1/rec + 0.1/yd + 6/TD, bonuses excluded'}
    if pos in ('RB', 'QB'):
        out['carries'] = ratio(seg, lambda r: p(r, 'carries'), lambda r: a(r, 'carries'))
        out['rush_yards'] = ratio(seg, lambda r: p(r, 'rush_yards'), lambda r: a(r, 'rush_yards'))
        out['rush_td'] = ratio(seg, lambda r: p(r, 'rush_td'), lambda r: a(r, 'rush_td'))
    if pos == 'QB':
        out['pass_attempts'] = ratio(seg, lambda r: p(r, 'pass_attempts'), lambda r: a(r, 'pass_attempts'))
        out['pass_yards'] = ratio(seg, lambda r: p(r, 'pass_yards'), lambda r: a(r, 'pass_yards'))
        out['pass_td'] = ratio(seg, lambda r: p(r, 'pass_td'), lambda r: a(r, 'pass_td'))
    return out


res = {'artifact': 'DECOMPOSE_DEV', 'season': 2024, 'scope': 'DEVELOPMENT ONLY; conditional on playing; production settings',
       'n_rows': len(rows), 'by_position_and_projection_decile': {}}
for pos in ('QB', 'RB', 'WR', 'TE'):
    seg = sorted((r for r in rows if r['pos'] == pos), key=lambda r: r['proj'])
    n = len(seg)
    res['by_position_and_projection_decile'][pos] = {
        'all': decompose(seg, pos),
        'top_decile': decompose(seg[int(0.9 * n):], pos),
        'top_quintile': decompose(seg[int(0.8 * n):], pos),
        'middle': decompose(seg[int(0.4 * n):int(0.6 * n)], pos)}
print(json.dumps(res, indent=1))
