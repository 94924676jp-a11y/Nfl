"""Before-and-after diagnostic for the Stage-6 current-season repair.

SAME pre-kickoff evidence cut, SAME fixture, SAME seed, SAME arm. One declared
change: the candidate mode, `V1_CANDIDATE_R9_W1P_GSVUCY` -> `...GSVUCYS`.

THIS IS A DIAGNOSTIC, NOT A VERDICT. The new run is not better because it
resembles the completed game. The NYG@LAR result is not read here and is not
admissible at this stage. What the table can say is which quantities moved,
by how much, and whether the movement is consistent with the evidence the new
Stage 6 can now see.

Both artifacts are opened through the gated loader's explicitly
NON-PUBLISHABLE inspection path, because both runs REFUSED at sealing -- the
baseline and the candidate alike, on the same declared `denom_panel` block.
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production.review import gated_projection as GP            # noqa: E402
from nfl.production.universe import player_universe as PU           # noqa: E402

BEFORE = 'nfl/research/showdown_fixture/run_post/d90d80c0b4a7f95e'
CUT = '2026-09-21T23:05:00Z'
GAME = '2026_02_NYG_LA'

METRICS = (('rushing/carries', 'carries'),
           ('receiving/targets', 'targets'),
           ('dk_scoring/dk_points', 'dk_points'),
           ('team_volume/team_carries', 'team_carries'),
           ('team_volume/team_targets', 'team_targets'))


def means(draws_dir, review_dir):
    o = GP.load(draws_dir, review_dir, inspect_refused_non_publishable=True)
    if o.state.name != 'PASS':
        raise SystemExit(f'{o.code}: {o.detail}')
    arr, lay = o.value['arrays'], o.value['layers']
    out = {}
    for key, name in METRICS:
        layer = key.split('/')[0]
        M = arr.get(key)
        ids = (lay.get(layer) or {}).get('row_ids') or []
        if M is None or len(ids) != M.shape[0]:
            continue
        out[name] = {pid: float(M[i].mean()) for i, pid in enumerate(ids)}
    return out, o.value.get('run_id'), o.value.get('draw_digest')


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--after', required=True)
    ap.add_argument('--review', default='nfl/research/player_review/'
                                        '2026_02_NYG_LA')
    ap.add_argument('--out', default='nfl/research/engine_repair/'
                                     'CS6_BEFORE_AFTER.json')
    a = ap.parse_args(argv)

    b, b_id, b_dig = means(_REPO / BEFORE, _REPO / a.review)
    n, n_id, n_dig = means(_REPO / a.after, _REPO / a.review)

    u = PU.build(2026, 2, GAME, CUT)
    rows = u.value['rows'] if isinstance(u.value, dict) else u.value
    name = {r['gsis_id']: (r.get('display_name'), r.get('team'),
                           r.get('roster_position'),
                           r.get('offensive_depth_rank')) for r in rows}

    print(f'BEFORE {b_id}  {b_dig[:16]}...')
    print(f'AFTER  {n_id}  {n_dig[:16]}...')
    print('\nNOT A VERDICT. The completed game is not read here.\n')

    report = {'artifact': 'CS6_BEFORE_AFTER_DIAGNOSTIC',
              'is_a_diagnostic_not_a_verdict': True,
              'game_outcome_not_used': True,
              'before': {'run_id': b_id, 'digest': b_dig, 'dir': BEFORE},
              'after': {'run_id': n_id, 'digest': n_dig, 'dir': a.after},
              'metrics': {}}

    for _k, m in METRICS:
        if m not in b or m not in n:
            continue
        both = sorted(set(b[m]) & set(n[m]))
        if not both:
            continue
        d = {p: n[m][p] - b[m][p] for p in both}
        tot_b, tot_n = sum(b[m].values()), sum(n[m].values())
        report['metrics'][m] = {
            'n_players': len(both),
            'total_before': round(tot_b, 4), 'total_after': round(tot_n, 4),
            'total_delta': round(tot_n - tot_b, 4),
            'mean_abs_delta': round(float(np.mean([abs(v) for v in d.values()])), 4),
            'largest_moves': [
                {'gsis_id': p, 'name': (name.get(p) or (p,))[0],
                 'team': (name.get(p) or (None, None))[1],
                 'pos': (name.get(p) or (None, None, None))[2],
                 'depth': (name.get(p) or (None, None, None, None))[3],
                 'before': round(b[m][p], 4), 'after': round(n[m][p], 4),
                 'delta': round(d[p], 4)}
                for p in sorted(both, key=lambda x: -abs(d[x]))[:12]],
        }
        print(f'== {m}: total {tot_b:.3f} -> {tot_n:.3f} '
              f'({tot_n - tot_b:+.3f}), mean |delta| '
              f'{report["metrics"][m]["mean_abs_delta"]:.4f}')
        for row in report['metrics'][m]['largest_moves'][:8]:
            print(f'   {str(row["name"])[:20]:22}{str(row["team"]):4}'
                  f'{str(row["pos"]):4} d{str(row["depth"]):4} '
                  f'{row["before"]:8.3f} -> {row["after"]:8.3f}  '
                  f'{row["delta"]:+.3f}')

    # ROLE ORDERING inside each club's backfield, which is the property the
    # repair was supposed to change.
    order = {}
    for club in ('NYG', 'LA'):
        backs = [p for p in b.get('carries', {})
                 if (name.get(p) or (None, None, None))[2] in ('RB', 'FB')
                 and (name.get(p) or (None, None))[1] == club]
        order[club] = {
            'before': [(name[p][0], round(b['carries'][p], 3))
                       for p in sorted(backs, key=lambda x: -b['carries'][x])],
            'after': [(name[p][0], round(n['carries'][p], 3))
                      for p in sorted(backs, key=lambda x: -n['carries'].get(x, 0))
                      if p in n.get('carries', {})],
        }
    report['backfield_order'] = order
    print('\n== backfield carry order')
    for club, v in order.items():
        print(f'   {club} before: {v["before"]}')
        print(f'   {club} after : {v["after"]}')

    p = _REPO / a.out
    p.write_text(json.dumps(report, indent=1, sort_keys=True, default=str))
    print(f'\nwrote {p}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
