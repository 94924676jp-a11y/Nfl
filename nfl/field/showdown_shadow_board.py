#!/usr/bin/env python3.12
"""SHADOW field / duplication diagnostic board for a staged scenario. EXTERNAL_RESEARCH_SHADOW. Not validated.

    python3.12 nfl/field/showdown_shadow_board.py EXPORT SCENARIO_DIR SHADOW_DIR

Reads our staged portfolio (FINAL_LINEUPS) and the shadow field (showdown_shadow_field.py). Writes, per contest:
our CPT/FLEX exposure beside shadow CPT/FLEX ownership (leverage), predicted duplicates per lineup (exact and
product estimators, scaled to the ESTIMATED field size), the salary-left and team-split distributions, and a
SHADOW comparison portfolio: the same objective rebuilt with lineups predicted above the 20-copy guardrail
(SaberSim 19:12) removed. The comparison never replaces production; the owner decides.
"""
from __future__ import annotations

import collections
import csv
import json
import math
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.field import showdown_shadow_field as SF  # noqa: E402
from nfl.tools import showdown_portfolio as SP, showdown_portfolio_audit as PA  # noqa: E402

GUARDRAIL = 20     # predicted copies; SaberSim's stated 20-25 guardrail, lower end. Reporting/comparison only.


def run(export, sd, shadow_dir):
    sd, shadow_dir = pathlib.Path(sd), pathlib.Path(shadow_dir)
    doc = json.loads((shadow_dir / 'SHOWDOWN_ATL_NO_SHADOW_FIELD.json').read_text())
    lines = np.load(shadow_dir / 'shadow_field_lineups.npy', allow_pickle=True)
    field = [(r[0], tuple(sorted(r[1:]))) for r in lines]
    k = len(field)
    exact = collections.Counter(field)
    own = SF.ownership(field, None)
    R = PA.rebuild(export, sd)
    by, cands, hit = R['by'], R['cands'], R['hit']
    seats_of = [[c] + list(f) for c, f in cands]
    sizes = doc['field_size_estimates']
    # earlier FC-only fields describe their source in prose; only the blend carries the MEAN_OF_FC_AND_OURS tag
    src = 'BLEND' if doc.get('field_projection') == 'MEAN_OF_FC_AND_OURS' else 'FC_ONLY'
    board = {'ARTIFACT': 'SHOWDOWN_SHADOW_BOARD', 'label': SF.LABEL, 'VALIDATED': False, 'sigma': doc['sigma_chosen'],
             'field_projection': doc.get('field_projection', 'FC_ONLY'), 'shadow_dir': str(shadow_dir),
             'anchor_rmse': doc['sigma_sweep'][str(doc['sigma_chosen'])]['rmse'],
             'PROMOTION_STATUS': 'NOT_PROMOTED (both field projections kept side by side)',
             'field_size_estimates': sizes, 'contests': {}}
    rows_own = []
    for cid, chosen in R['finals'].items():
        n = len(chosen)
        N = sizes.get(cid, 50000)
        ours = [cands[i] for i in chosen]
        d = SF.lineup_dupes(ours, own, exact, k, N)
        cexp = collections.Counter(c for c, _ in ours)
        fexp = collections.Counter(x for _, f in ours for x in f)
        lev = []
        for key in sorted(set(cexp) | set(fexp) | {x for x in own if own[x]['total'] >= 5}, key=lambda x: -own.get(x, {}).get('total', 0)):
            o = own.get(key, {'cpt': 0, 'flex': 0})
            lev.append({'player': by[key]['name'] if key in by else key, 'shadow_cpt': round(o['cpt'], 1),
                        'our_cpt': round(100 * cexp[key] / n, 1), 'cpt_leverage': round(100 * cexp[key] / n - o['cpt'], 1),
                        'shadow_flex': round(o['flex'], 1), 'our_flex': round(100 * fexp[key] / n, 1),
                        'flex_leverage': round(100 * fexp[key] / n - o['flex'], 1)})
        sal = [SP.CAP - (by[c]['cpt_salary'] + sum(by[x]['salary'] for x in f)) for c, f in ours]
        split = collections.Counter('-'.join(str(sum(1 for x in [c] + list(f) if by[x]['team'] == t))
                                             for t in (R['L']['slate']['away'], R['L']['slate']['home'])) for c, f in ours)
        fsplit = collections.Counter('-'.join(str(sum(1 for x in [c] + list(f) if by.get(x, {}).get('team') == t))
                                              for t in (R['L']['slate']['away'], R['L']['slate']['home'])) for c, f in field)
        over = [i for i, x in zip(chosen, d) if x['pred_dupes_exact'] > GUARDRAIL]
        # SHADOW comparison: same objective and ladder, candidates above the guardrail removed
        cand_d = SF.lineup_dupes(cands, own, exact, k, N)
        keep = [j for j, x in enumerate(cand_d) if x['pred_dupes_exact'] <= GUARDRAIL]
        sub_hit = hit[keep]
        sub_seats = [seats_of[j] for j in keep]
        sub_cr = [{'first_place_proxy': float(h.mean()), 'structural_duplication_index': 0} for h in sub_hit]
        Pn, log = SP.ladder(sub_hit, sub_cr, sub_seats, n, hit.shape[1])
        shadow_sel = [keep[j] for j in Pn['chosen']]
        board['contests'][cid] = {
            'n': n, 'field_size_estimate': N,
            'pred_dupes_exact': {'mean': round(float(np.mean([x['pred_dupes_exact'] for x in d])), 1),
                                 'max': max(x['pred_dupes_exact'] for x in d),
                                 'n_over_guardrail': len(over), 'guardrail': GUARDRAIL},
            'lineups_with_player_absent_from_shadow_field': sum(1 for x in d if x.get('players_absent_from_shadow_field')),
            'pred_dupes_product': {'mean': round(float(np.mean([x['pred_dupes_product'] for x in d])), 2),
                                   'max': max(x['pred_dupes_product'] for x in d)},
            'geomean_ownership_median': float(np.median([x['geomean_ownership'] for x in d])),
            'salary_left': {'ours': dict(collections.Counter(min(s // 500 * 500, 3000) for s in sal)),
                            'ours_mean': round(float(np.mean(sal)), 0), 'shadow_field_mean': doc['salary_left']['mean']},
            'team_split_away_home': {'ours_pct': {s: round(100 * v / n, 1) for s, v in sorted(split.items())},
                                     'shadow_field_pct': {s: round(100 * v / k, 1) for s, v in sorted(fsplit.items())}},
            'leverage': lev,
            'shadow_portfolio_comparison': {
                'built': len(shadow_sel), 'relaxation_level': Pn['relaxation_level'],
                'proxy_coverage': round(Pn['coverage'], 4),
                'production_proxy_coverage': round(float(hit[chosen].any(axis=0).mean()), 4),
                'lineups_shared_with_production': len(set(shadow_sel) & set(chosen)),
                'STATUS': 'COMPARISON ONLY -- production is not replaced without an owner ruling'},
            'lineups': [{'captain': by[c]['name'], 'flex': [by[x]['name'] for x in f], **x}
                        for (c, f), x in zip(ours, d)],
        }
        for e in lev:
            rows_own.append({'contest': cid, **e})
    # one file per field projection, so FC_ONLY and BLEND sit side by side and neither overwrites the other
    (sd / f'SHOWDOWN_ATL_NO_SHADOW_BOARD_{src}.json').write_text(json.dumps(board, indent=1, default=str))
    with (sd / f'SHOWDOWN_ATL_NO_SHADOW_LEVERAGE_{src}.csv').open('w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows_own[0]))
        w.writeheader()
        w.writerows(rows_own)
    return board


if __name__ == '__main__':
    b = run(sys.argv[1], sys.argv[2], sys.argv[3])
    for c, v in b['contests'].items():
        print(c, {k: v[k] for k in ('pred_dupes_exact', 'pred_dupes_product', 'geomean_ownership_median', 'salary_left',
                                    'team_split_away_home', 'shadow_portfolio_comparison')})
        print('  leverage', v['leverage'][:10])
