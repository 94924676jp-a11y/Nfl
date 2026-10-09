#!/usr/bin/env python3.12
"""Compose DST_K_SCORING_AUDIT_2026-10-09.json from the measurement files. Reads only; writes the one JSON.

    python3.12 nfl/research/dst_scoring/compose.py CLASSIC_RESEARCH_STATE_DIR
"""
from __future__ import annotations

import gzip
import json
import pathlib
import subprocess
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
D = _REPO / 'nfl/research/dst_scoring'
STATS = ('mean', 'sd', 'p_le_0', 'p_ge_15', 'non_integer_share')


def _avg(rows, key):
    v = [r[key] for r in rows]
    return round(sum(v) / len(v), 4)


def main(classic_dir):
    hist = json.loads((D / 'DST_K_HISTORY_2021_2025.json').read_text())
    slates = {t: json.loads((D / 'measurements' / f'{t}.json').read_text())
              for t in ('TB_DAL_2026W5', 'ATL_NO_2026W4', 'CLASSIC_EARLY_2026W5')}
    cproj = json.loads(gzip.open(pathlib.Path(classic_dir) / 'PROJ.json.gz').read())
    crows = {f"{r['name']}|{r['team']}": r for r in cproj['rows'].values()}
    per_dst, stage_rows = [], {'S0_raw_simulator': [], 'S1_published_after_anchor': [], 'FIX_EVENTS': [],
                               'FIX_PROJECTION': []}
    for tag, m in slates.items():
        for k, v in m['dst'].items():
            items = v.get('projection_event_items') or crows[k]['dst']['event_items']
            ev, pr = v['FIX']['EVENTS'], v['FIX']['PROJECTION']
            a = ev['account']
            free_proj = sum(items[x] for x in ('sack', 'fumble_recovery', 'return_td', 'safety', 'blocked_kick'))
            per_dst.append({
                'slate': tag, 'dst': k, 'projection': v['projection_dk_points'],
                'S0_raw_mean': v['S0_raw_simulator']['mean'], 'S0_non_integer': v['S0_raw_simulator']['non_integer_share'],
                'S1_published_mean': v['S1_published_after_anchor']['mean'],
                'S1_non_integer': v['S1_published_after_anchor']['non_integer_share'],
                'anchor_factor': v.get('anchor_factor') or v['S1_published_after_anchor'].get('anchor_factor_recorded'),
                'FIX_EVENTS_mean': ev['summary']['mean'], 'FIX_PROJECTION_mean': pr['summary']['mean'],
                'FIX_PROJECTION_state': pr['account']['state'],
                'FIX_PROJECTION_multiplier': pr['account']['multiplier_on_free_rates'],
                'mean_change_vs_published': v['mean_change_vs_published'],
                'events_minus_projection_decomposed': {
                    'points_allowed_tier': round(a['expected_tier_points'] - items['points_allowed'], 4),
                    'interceptions': round(a['expected_int_points'] - items['interception'], 4),
                    'free_components_band_effect': round(a['expected_free_points_at_m1'] - free_proj, 4),
                    'NOTE': 'expected values; the realised EVENTS mean adds Monte Carlo noise (MCSE ~0.1)'},
                'all_fix_checks_pass': all(ev['checks'].values()) and all(pr['checks'].values()),
            })
            stage_rows['S0_raw_simulator'].append(v['S0_raw_simulator'])
            stage_rows['S1_published_after_anchor'].append(v['S1_published_after_anchor'])
            stage_rows['FIX_EVENTS'].append(ev['summary'])
            stage_rows['FIX_PROJECTION'].append(pr['summary'])
    h = hist['dst_dk_rule_A']
    hrow = {s: h[s] for s in STATS if s != 'non_integer_share'}
    hrow['non_integer_share'] = round(1 - h['integer_share'], 4)
    dist = {'HISTORY_2021_2025_rule_A (per club-game, unconditional)': hrow}
    for st, rows in stage_rows.items():
        dist[f'{st} (average over {len(rows)} DST-slates of the per-DST statistic)'] = {s: _avg(rows, s) for s in STATS}
    kick = []
    for tag in ('TB_DAL_2026W5', 'ATL_NO_2026W4'):
        for k, v in slates[tag]['kickers'].items():
            kick.append({'slate': tag, 'kicker': k, **{s: v['published'][s] for s in STATS},
                         'reproduced': v['reproduced_draw_for_draw'],
                         'rescored_through_dk_scoring_equals_published': v['rescored_through_dk_scoring_equals_published'],
                         'point_projection_kicker_model_miss_minus_1': v['point_projection_kicker_model'],
                         'share_6td_plus_xp_plus_3fg_exceeds_rounded_club_points':
                             v['share_6td_plus_xp_plus_3fg_exceeds_rounded_club_points'],
                         'share_offensive_td_points_exceed_club_points': v['share_offensive_td_points_exceed_club_points']})
    kh = hist['kicker_dk_rule_A']
    commit = subprocess.run(['git', '-C', str(_REPO), 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
    doc = {
        'ARTIFACT': 'DST_K_SCORING_AUDIT', 'date': '2026-10-09', 'base_commit': commit,
        'STATUS': 'SHADOW ONLY. Nothing promoted; no production file changed. Development data, exploratory.',
        'ROOT_CAUSE': {
            'what': 'an expected-value anchor applied to an already-scored realised DST draw: the raw simulator DST '
                    'score is an integer in 100% of worlds; one multiplicative factor per DST, applied after scoring, '
                    'makes it non-integer in 92-98% of worlds',
            'where': ['nfl/tools/classic_slate_run.py:150 anchor_means: out[k] = [x * f for x in v]',
                      'nfl/tools/showdown_slate_run.py:113-114 dst = {...not skill, not kicker}; CR.anchor_means(dst, targets)',
                      'nfl/tools/classic_slate_run.py:276-277 rest = {...not skill} (DST: no stat line); anchor_means(rest, targets)'],
            'not_the_cause': ['nfl/sim/dst.py:242-254 DstModel.draw_components (integer tier + integer tuples)',
                              'nfl/sim/game.py:323-324 (stores the raw integer draw)',
                              'nfl/product/dk_scoring.py dst_points / kicker_points (pure adapters)'],
            'reconstruction': 'published == S0 x factor to <= 3.6e-15 for all 4 Showdown DSTs; Classic replay reproduces '
                              'all 266 published draws exactly (max |diff| 0.0) and S0 equals the raw draw for all 16 DSTs',
        },
        'per_dst': per_dst, 'distribution_vs_history': dist,
        'kickers': {'per_kicker': kick, 'history_2021_2025_rule_A': {s: kh.get(s) for s in STATS if s != 'non_integer_share'}
                    | {'non_integer_share': round(1 - kh['integer_share'], 4)}},
        'downstream': {t: m['downstream'] for t, m in slates.items()},
        'secondary_findings': {
            k: {'tier_convention_disagreement': v['tier_convention_disagreement'],
                'incumbent_interception_consistency': v['incumbent_interception_consistency'],
                'opponent_points': v['opponent_points']}
            for t in ('TB_DAL_2026W5', 'ATL_NO_2026W4') for k, v in slates[t]['dst'].items()},
        'history': {k: hist[k] for k in ('n_dst_club_games', 'dst_dk_rule_A', 'dst_dk_rule_B',
                                          'dst_component_means_per_club_game', 'pa_tier_points_mean_rule_A',
                                          'kicker_dk_rule_A', 'dispersion_within_club_season', 'bands_rule_A')},
        'inputs': {'TB_DAL_2026W5': slates['TB_DAL_2026W5']['scenario'],
                   'ATL_NO_2026W4': slates['ATL_NO_2026W4']['scenario'] + ' (kickers re-drawn under '
                   'NFL_PIT_MANIFEST=nfl/warehouse/pit_manifests/PIT_MANIFEST.ATL_NO_2026W4.1294f0dc638d95c9.json)',
                   'CLASSIC_EARLY_2026W5': slates['CLASSIC_EARLY_2026W5']['research_state']},
    }
    out = D / 'DST_K_SCORING_AUDIT_2026-10-09.json'
    out.write_text(json.dumps(doc, indent=1) + '\n')
    print(json.dumps(dist, indent=1))
    for r in per_dst:
        print(f"{r['slate'][:7]} {r['dst']:16s} proj {r['projection']:.2f} S0 {r['S0_raw_mean']:.2f} S1 {r['S1_published_mean']:.2f} "
              f"EV {r['FIX_EVENTS_mean']:.2f} PR {r['FIX_PROJECTION_mean']:.2f} m {r['FIX_PROJECTION_multiplier']:.2f} "
              f"dec {r['events_minus_projection_decomposed']['points_allowed_tier']:+.2f} "
              f"{r['events_minus_projection_decomposed']['interceptions']:+.2f} "
              f"{r['events_minus_projection_decomposed']['free_components_band_effect']:+.2f} ok {r['all_fix_checks_pass']}")


if __name__ == '__main__':
    main(sys.argv[1])
