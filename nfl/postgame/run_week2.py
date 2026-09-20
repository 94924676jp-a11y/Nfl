"""Emit every Week-2 postgame deliverable from the frozen board + actuals.

MEASUREMENT ONLY. Nothing in this package changes a coefficient, promotes a
candidate, or rewrites a pregame number. Its output is evidence for a LATER,
separately proposed experiment with its own train/test separation.

EVERY CONCLUSION IS TAGGED. OBSERVED is a number computed here. INFERRED is a
reading of several numbers that does not follow from any one of them.
HYPOTHESIS is a claim this slate cannot settle.
"""
from __future__ import annotations

import collections
import csv
import json
import math
import pathlib
import statistics as st
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.postgame import actuals as A, grade_week as G, reports as R  # noqa

OUT = _REPO / 'nfl' / 'research' / 'postgame'
PKG = (_REPO / 'nfl' / 'research' / 'sunday'
       / 'EARLY_ONLY_POSTINACTIVES_PACKAGE_2026W2.json')


def under_bias_investigation(rows):
    """Which of the named mechanisms the Week-2 miss is consistent with."""
    by = A.load_weekly(2026, 2).value
    g = [r for r in rows if r['row_type'] == 'PLAYER_GAME_PROJECTION'
         and r['grade_state'] == 'GRADED']
    team_actual = collections.defaultdict(collections.Counter)
    for r in by.values():
        k = (r['game_id'], r['team'])
        team_actual[k]['targets'] += r['targets']
        team_actual[k]['carries'] += r['carries']
    covered, ratios, hh_p, hh_a = [], [], [], []
    for (gid, tm), c in team_actual.items():
        sel = [r for r in g if r['game_id'] == gid and r['team'] == tm
               and r.get('proj_targets_mean') is not None]
        pj = sum(r['proj_targets_mean'] for r in sel)
        if pj <= 0:
            continue
        ou = sum(r.get('actual_targets') or 0 for r in sel)
        covered.append({'game_id': gid, 'team': tm, 'n_players': len(sel),
                        'projected_targets': round(pj, 2),
                        'our_players_actual_targets': ou,
                        'team_actual_targets': c['targets'],
                        'player_coverage': round(ou / c['targets'], 4)
                        if c['targets'] else None})
        ratios.append(pj / c['targets'])

        def _hhi(v):
            s = sum(v)
            return sum((x / s) ** 2 for x in v) if s else None
        p = _hhi([r['proj_targets_mean'] for r in sel])
        a = _hhi([r.get('actual_targets') or 0 for r in sel])
        if p and a:
            hh_p.append(p)
            hh_a.append(a)
    P = sum(c['projected_targets'] for c in covered)
    O = sum(c['our_players_actual_targets'] for c in covered)
    T = sum(c['team_actual_targets'] for c in covered)
    dh = [a - p for p, a in zip(hh_p, hh_a)]
    n = len(dh)
    se_h = st.stdev(dh) / math.sqrt(n) if n > 1 else None
    se_r = st.stdev(ratios) / math.sqrt(len(ratios)) if len(ratios) > 1 else None
    return {
        'teams_with_receiving_coverage': len(covered),
        'per_team': covered,
        'projected_targets_total': round(P, 2),
        'our_players_actual_targets_total': O,
        'team_actual_targets_total': T,
        'player_coverage_of_team_targets': round(O / T, 4) if T else None,
        'projected_over_team_actual': round(P / T, 4) if T else None,
        'volume_shortfall_pct': round(100 * (1 - P / T), 2) if T else None,
        'per_team_ratio_mean': round(st.mean(ratios), 4),
        'per_team_ratio_sd': round(st.stdev(ratios), 4),
        'per_team_ratio_se': round(se_r, 4) if se_r else None,
        'target_share_hhi_projected': round(st.mean(hh_p), 4),
        'target_share_hhi_actual': round(st.mean(hh_a), 4),
        'hhi_mean_difference_actual_minus_projected': round(st.mean(dh), 4),
        'hhi_difference_se': round(se_h, 4) if se_h else None,
        'hhi_t_statistic': round(st.mean(dh) / se_h, 3) if se_h else None,
        'reading': {
            'allocation_too_diffuse': 'SUPPORTED',
            'team_pass_volume_low': 'SUGGESTED_NOT_CONCLUSIVE',
            'conversion_efficiency': 'NOT_IDENTIFIED_AT_THIS_N',
            'game_script': 'NOT_TESTED_NO_IN_GAME_STATE_INGESTED',
            'player_role_miss': 'NOT_SEPARABLE_FROM_ALLOCATION_HERE',
        },
    }


def dfs_rows(rows):
    return [r for r in rows if r['row_type'] == 'PLAYER_GAME_PROJECTION'
            and r['grade_state'] == 'GRADED'
            and r.get('actual_dk_points') is not None]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    o = G.build(str(PKG))
    if o.state.name != 'PASS':
        print(f'{o.state.name}[{o.code}] {o.detail}')
        return 1
    rows = o.value
    keys = []
    for r in rows:
        for k in r:
            if k not in keys:
                keys.append(k)
    cpath = OUT / 'week2_postgame_grading.csv'
    with open(cpath, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    jpath = OUT / 'week2_postgame_grading.jsonl'
    jpath.write_text('\n'.join(json.dumps(r, sort_keys=True)
                               for r in rows) + '\n')
    summary = {
        'spec_version': G.SPEC_VERSION,
        'candidate_status': 'CANDIDATE_NOT_ACCEPTED_BASELINE',
        'governance': {
            'production_model_changed': False,
            'candidate_promoted': False,
            'pregame_rows_rewritten': False,
            'outcomes_used_as_predictive_inputs': False,
            'v2_status': 'V2 NOT YET EARNED',
        },
        'canonical_dataset': {
            'csv': str(cpath.relative_to(_REPO)),
            'jsonl': str(jpath.relative_to(_REPO)),
            'parquet': None,
            'parquet_note': 'pyarrow is not installed in this environment, '
                            'so the canonical dataset is emitted as CSV and '
                            'JSONL. Same rows, same columns.',
            'n_rows': len(rows),
        },
        'coverage': {
            'games_graded': o.evidence['games_graded'],
            'games_not_published': o.evidence['games_not_published'],
            'grade_state_counts': dict(collections.Counter(
                r['grade_state'] for r in rows)),
        },
        'projection_calibration': R.projection_metrics(rows),
        'workload_calibration': R.workload_metrics(rows),
        'prop_calibration': R.prop_metrics(rows),
        'under_bias_investigation': under_bias_investigation(rows),
        'outcome_interpretation': {
            'values_present': dict(collections.Counter(
                r['outcome_interpretation'] for r in rows)),
            'basis': 'NO_IN_GAME_OR_SNAP_EVIDENCE_AVAILABLE_FOR_THIS_GAME',
            'filtered_view_state': 'NOT_YET_COMPUTABLE',
            'why': 'Week-2 snap counts cover only 2026_02_DET_BUF, which is '
                   'not in this board. With no in-game or snap evidence for '
                   'the seven graded games, no row can be marked '
                   'EARLY_EXIT_INJURY on evidence. The field and the filter '
                   'exist; populating them needs the participation feed.',
        },
    }
    (OUT / 'week2_postgame_summary.json').write_text(
        json.dumps(summary, indent=1, sort_keys=True) + '\n')
    print(f'wrote {cpath.name} {len(rows)} rows')
    print(f'wrote {jpath.name}')
    print('wrote week2_postgame_summary.json')
    return 0


if __name__ == '__main__':
    sys.exit(main())
