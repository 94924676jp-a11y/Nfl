#!/usr/bin/env python3.12
"""Attach FantasyCruncher comparison columns to a FROZEN owner board, in a clean process.

    python3.12 nfl/tools/classic_fc_compare.py 2026W4

ORDER IS THE FIREWALL. Every proprietary column on the board was written by classic_owner_board.py
before this runs; this process imports no proprietary module (fc_context refuses otherwise), reads
the board as data, and writes ONLY the fc_* columns and the comparison list. A material gap is
reported with OUR stat line beside it. Nothing here is fed back into any projection.
"""
from __future__ import annotations

import csv
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import fc_context as FC  # noqa: E402

OUT_DIR = _REPO / 'nfl/dfs/salaries'


def likely_source(x, fc):
    """Why two projections differ, read from FC's own depth label against our role facts. Diagnostic only."""
    out = []
    fd = fc.get('pDepth')
    fc_rank = int(''.join(ch for ch in str(fd) if ch.isdigit()) or 0) if fd not in (None, '') else None
    st = str(x.get('starter_state') or '')
    our_rank = int(st.rsplit('_', 1)[-1]) if st.startswith('DEPTH_RANK_') and st.rsplit('_', 1)[-1].isdigit() else None
    if (x.get('fc_proj') or 0) == 0 and (x.get('sim_mean') or 0) >= 3:
        out.append(f"availability: FC projects 0 (treats him as not playing); our evidence is designation "
                   f"{x.get('designation') or 'none'}")
    if st == 'DEPTH_CHART_NEXT_HEALTHY_AFTER_REPORTED_OUT':
        out.append(f'starter state: we start him off the depth chart behind an OUT starter; FC depth {fd}')
    elif fc_rank and our_rank and fc_rank != our_rank:
        out.append(f'depth/role: FC lists {fd}, we rank him {x["pos"]}{our_rank}')
    if x.get('designation') in ('QUESTIONABLE', 'DOUBTFUL'):
        out.append(f"injury uncertainty: designated {x['designation']}")
    if not out:
        out.append('volume/efficiency/TD expectation: no structural difference found; our projection has no '
                   'opponent term, so a matchup adjustment on their side is one candidate')
    return out


def main() -> int:
    slate = sys.argv[1]
    bp = OUT_DIR / f'DK_{slate}_EARLY_OWNER_BOARD.json'
    board = json.loads(bp.read_text())
    o = FC.load(slate)
    if o.state.value != 'PASS':
        print(f'{o.state.value}[{o.code}] {o.detail}')
        return 1
    players = {x['dk_id']: {'name': x['player'], 'team': x['team'], 'position': x['pos']} for x in board['players']}
    joined, fc_only, dk_only = FC.join_to_dk(o.value, players)
    cmp_rows = []
    for x in board['players']:
        fc = (joined.get(x['dk_id']) or {}).get(FC.CONTEXT_KEY) or {}
        x['fc_proj'], x['fc_floor'], x['fc_ceiling'] = fc.get('FC Proj'), fc.get('Floor'), fc.get('Ceiling')
        x['fc_diff'] = (round(x['sim_mean'] - x['fc_proj'], 2)
                        if x['fc_proj'] is not None and x['sim_mean'] is not None else None)
        if x['fc_diff'] is None or x['classification'] in ('inactive', 'non-playable'):
            continue
        if abs(x['fc_diff']) >= 3.0 or (x['fc_proj'] >= 8 and abs(x['fc_diff']) / x['fc_proj'] >= 0.3):
            cmp_rows.append({'player': x['player'], 'team': x['team'], 'pos': x['pos'], 'salary': x['salary'],
                             'ours_sim_mean': x['sim_mean'], 'fc_proj': x['fc_proj'], 'diff': x['fc_diff'],
                             'our_volume': {'targets': x['targets'], 'carries': x['carries'],
                                            'pass_attempts': x['pass_attempts']},
                             'our_role': x['role'], 'our_starter_state': x['starter_state'],
                             'designation': x['designation'], 'our_key_reason': x['key_reason'],
                             'fc_floor': x['fc_floor'], 'fc_ceiling': x['fc_ceiling'], 'fc_depth': fc.get('pDepth'),
                             'likely_source': likely_source(x, fc),
                             'READING': 'a diagnostic about two opinions, not a correction to ours'})
    cmp_rows.sort(key=lambda z: -abs(z['diff']))
    board['fc'] = {'state': 'ATTACHED', 'sha256': o.evidence.get('sha256'), 'n_fc_rows': len(o.value),
                   'n_joined': len(joined), 'fc_only': fc_only, 'NOT_A_MODEL_INPUT': FC.NOT_A_MODEL_INPUT}
    board['fc_comparison'] = cmp_rows
    bp.write_text(json.dumps(board, indent=1, default=str))
    cols = list(board['players'][0].keys())
    with open(OUT_DIR / f'DK_{slate}_EARLY_PLAYER_BOARD.csv', 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for x in board['players']:
            w.writerow(x)
    print(f'PASS[FC_COMPARISON_ATTACHED] {len(joined)} joined, {len(fc_only)} FC-only, {len(cmp_rows)} material gaps')
    return 0


if __name__ == '__main__':
    sys.exit(main())
