#!/usr/bin/env python3.12
"""Run the seven projection guards against V1 and emit the acceptance board.

The guards were written against V0's observed defects BEFORE V1 existed, which is the only
order in which a guard means anything. They are not re-tuned here to let V1 through.

ON THE LEVEL GUARD AND THE EXTERNAL BASELINE. That guard compares our board's level against
FantasyCruncher on several slices. FC is a COMPARISON, never an input and never a target: no V1
constant was chosen by looking at this ratio, and the firewall in fc_context.py still fails any
build in which a proprietary module imports the FC reader. The band is a tripwire that says
'go and look', which is what the owner sanctioned in calling FC 'a median to what a solid
projection should be around'. A board that matched FC exactly would not thereby be good, and a
board that differs from it is not thereby wrong.
"""
from __future__ import annotations

import collections
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Outcome  # noqa: E402

V1 = _REPO / 'nfl/dfs/salaries/DK_WEEK3_PROJ_V1.json'
POST = _REPO / 'nfl/dfs/salaries/DK_WEEK3_TODAY_STATE_POST_INACTIVES.json'
ROLE = _REPO / 'nfl/derived/ROLE_STATE.json'
OUT = _REPO / 'nfl/dfs/salaries/DK_WEEK3_V1_ACCEPTANCE.json'


def to_guard_records(v1, post):
    """Adapt V1 rows to the record shape the guards were written against."""
    recs = {}
    for dk_id, r in v1['rows'].items():
        td = r.get('td') or {}
        tot_td = sum(v for k, v in td.items()
                     if k in ('rec_td', 'rush_td') and isinstance(v, (int, float)))
        if r['position'] == 'QB':
            tot_td += (td.get('pass_td') or 0.0)
        obs = r.get('observed_volume') or None
        recs[dk_id] = {
            'player': r.get('name'), 'position': r.get('position'), 'team': r.get('team'),
            'salary': r.get('salary'),
            'mean': r.get('dk_points'),
            'opportunity': {
                'proj_targets': r.get('targets'), 'proj_carries': r.get('carries'),
                'proj_pass_attempts': r.get('pass_attempts'),
                'observed_target_share': (r.get('observed_shares') or {}).get('target_share'),
                'target_share_used': (r.get('claims') or {}).get('targets'),
                'observed_carry_share': (r.get('observed_shares') or {}).get('carry_share'),
                'carry_share_used': (r.get('claims') or {}).get('carries'),
            },
            'scoring': {'proj_td': tot_td if r.get('dk_points') is not None else None},
            'observed_volume_for_guard': obs,
        }
    return recs


def main() -> int:
    from nfl.tools import projection_guards as G
    from nfl.tools import fc_context
    if not V1.exists():
        print('BLOCKED: V1 artifact not built'); return 1
    v1 = json.loads(V1.read_text())
    post = json.loads(POST.read_text())
    role = json.loads(ROLE.read_text())['states']
    players = {k: {'name': p['name'], 'position': p['position'], 'team': p['team'],
                   'salary': p.get('salary')} for k, p in post['players'].items()}
    recs = to_guard_records(v1, post)

    # external comparison only
    fc = fc_context.load()
    external = {}
    if getattr(fc, 'state', None) and fc.state.name == 'PASS':
        joined, fc_only, dk_only = fc_context.join_to_dk(fc.value, players)
        ctx = fc_context.CONTEXT_KEY
        for dk_id, row in joined.items():
            v = (row.get(ctx) or {}).get('FC Proj')
            if isinstance(v, (int, float)):
                external[dk_id] = v

    predicted_starters = {(v['name'], v['team']) for v in role.values()
                          if v.get('in_predicted_group')}
    conflicts = post.get('identity_conflicts') or []

    res = G.run_all(recs, players, external, predicted_starters, conflicts)
    board = {}
    for name, o in res.items():
        board[name] = {'state': o.state.name, 'code': o.code,
                       'detail': getattr(o, 'detail', None),
                       'evidence': {k: v for k, v in (getattr(o, 'evidence', {}) or {}).items()
                                    if k != 'slices'}}
        if o.code in ('PROJECTION_LEVEL_IN_BAND', 'PROJECTION_LEVEL_OUT_OF_BAND'):
            board[name]['slices'] = (getattr(o, 'evidence', {}) or {}).get('slices')
    art = {'artifact': 'DK_WEEK3_V1_ACCEPTANCE', 'guards': board,
           'n_external_joined': len(external),
           'EXTERNAL_IS_COMPARISON_ONLY': (
               'FantasyCruncher is a comparison baseline for the level tripwire. It is not an '
               'input to any projection and no V1 constant was selected by looking at it.'),
           'summary': v1.get('summary'), 'identity_failures': v1.get('identity_failures')}
    OUT.write_text(json.dumps(art, indent=1, sort_keys=True, default=str))
    fails = [k for k, v in board.items() if v['state'] == 'FAIL']
    for k, v in board.items():
        print(f"  {v['state']:14s} {k:36s} {v['code']}")
        if v['state'] == 'FAIL':
            print(f"       {str(v['detail'])[:300]}")
        if v.get('slices'):
            for sl in v['slices']:
                print(f"       {sl['slice']:22s} ratio {sl['ratio']:.4f} ours {sl['ours_mean']:6.2f} "
                      f"ext {sl['external_mean']:6.2f} n={sl['n']:3d} in_band {sl['in_band']}")
    print(f'\n  {len(board)-len(fails)} of {len(board)} guards pass; failing: {fails}')
    print(f'  -> {OUT.relative_to(_REPO)}')
    return 0 if not fails else 1


if __name__ == '__main__':
    raise SystemExit(main())
