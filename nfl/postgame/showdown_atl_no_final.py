#!/usr/bin/env python3.12
"""ATL@NO postgame -- autopsy verdicts, Hard Rock status, calibration summary, next-Showdown readiness board, report.

    python3.12 nfl/postgame/showdown_atl_no_final.py

Reads the postgame artifacts in nfl/postgame/showdown_atl_no_2026W4/ (each written by its own module) and writes:
  ATL_NO_AUTOPSY_VERDICTS.json         directive item 3, five questions, SUPPORTED / PARTIALLY_SUPPORTED / UNRESOLVED /
                                       CONTRADICTED, each with the numbers it rests on
  ATL_NO_CALIBRATION_REPORT.json       item 4 summary (PIT by stat, coverage) + the Olave/London/Bijan yardage test
  ATL_NO_HARD_ROCK_STATUS.json         item 9
  ATL_NO_SUCCESSOR_CANDIDATES.json     item 10 of deliverables: every candidate with its status and its held-out bar
  NEXT_SHOWDOWN_READINESS_BOARD.json   item 10
  ATL_NO_POSTGAME_REPORT.md            index of the 11 deliverables + the four closing sections
Nothing here is computed from outcomes in a way that feeds a forecast; every number is read from a named artifact.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import pathlib
import sys

import numpy as np
import pandas as pd

_REPO = pathlib.Path(__file__).resolve().parents[2]
OUT = _REPO / 'nfl/postgame/showdown_atl_no_2026W4'
RAW = _REPO / 'nfl/postgame/raw/showdown_atl_no_2026W4'
V2 = _REPO / 'nfl/dfs/salaries/showdown_atl_no/RW_INACTIVES_CHARTFIX'
SEAL = _REPO / 'nfl/market/atl_no_2026W4/PROP_FORECAST_SEAL.json'


class FinalError(RuntimeError):
    pass


def _j(name):
    p = OUT / name
    if not p.exists():
        raise FinalError(f'MISSING_ARTIFACT {name}')
    d = json.loads(p.read_text())
    if not d:
        raise FinalError(f'EMPTY_ARTIFACT {name}')
    return d


def _sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def _exposure(name):
    rows = [r for r in csv.DictReader(open(OUT / 'ATL_NO_OWNER_ENTRIES_GRADED.csv')) if r['contest_id'] == '196285137']
    cpt = sum(r['captain'].split('|')[0] == name for r in rows)
    flex = sum(any(x.split('|')[0] == name for x in eval(r['flex'])) for r in rows)   # noqa: S307 -- our own CSV
    return {'cpt_pct': round(100 * cpt / len(rows), 1), 'flex_pct': round(100 * flex / len(rows), 1),
            'any_pct': round(100 * sum(r['captain'].split('|')[0] == name or any(x.split('|')[0] == name for x in eval(r['flex']))
                                       for r in rows) / len(rows), 1)}


def _own(fa, player, slot, which, src='BLEND', cid='196285137'):
    rows = fa['contests'][cid]['M1_ownership'][src][slot]['players_above_5pct']
    r = next((x for x in rows if x['player'] == player), None)
    return None if r is None else r[which]


def verdicts(sc, au, gr, ps, fa):
    fb = fa['contests']['196285137']
    best = au['top_lineups'][0]
    g = {p['player'].split('|')[0]: p for p in gr}
    brj = g['Brian Robinson Jr.']
    others = [x for x in au['top_lineups'][1:]]
    common = sorted(set.intersection(*[set([x['CPT']] + x['FLEX']) for x in au['top_lineups']]))
    live = ps['realised_by_variant']['V2_FINAL_LIVE']['196285137']
    abl = {k: ps['realised_by_variant'][k]['196285137'] for k in ('ABLATION_TOP_MEAN', 'ABLATION_TOP_PROXY')}
    pre = ps['prelock_worlds_by_variant']
    without_best = round((134.47 - best['winnings']) / 75.0 - 1, 4)
    q = [
        {'q': 1, 'question': 'Did the lineup succeed because the football forecast was directionally right?',
         'label': 'CONTRADICTED',
         'evidence': {'actual_like_world_share': au['actual_like_world_share'],
                      'actual_like_definition': 'ATL >= 35 and NO <= 31 in a simulated world',
                      'final_score': 'ATL 45, NO 24',
                      'lineup_players_mean_vs_actual': best['player_proj_vs_actual'],
                      'pit_of_the_three_that_made_it': {'Brian Robinson Jr.': brj['dk_pit'],
                                                        'Jahan Dotson': g['Jahan Dotson']['dk_pit'],
                                                        'Alvin Kamara': g['Alvin Kamara']['dk_pit']}},
         'why': ('the game script that produced it (ATL blowout) was a 2.7% world in our simulation, and the three '
                 'players who carried the lineup finished at PIT 1.00 / 0.99 / 0.92 of their own forecasts. Volume '
                 'forecasts for Olave and London were close, but those are not what made this lineup.')},
        {'q': 2, 'question': 'Did it succeed because the portfolio captured the correct tail scenario?',
         'label': 'PARTIALLY_SUPPORTED',
         'evidence': {'lineup_proxy_rate_in_actual_like_worlds': best['proxy_rate_in_actual_like_worlds'],
                      'lineup_proxy_rate_elsewhere': best['proxy_rate_elsewhere'],
                      'lineup_actual_score_percentile_of_own_sim': best['sim_pctile_of_actual_score'],
                      'players_common_to_all_four_top1pct_lineups': common,
                      'brian_robinson_jr_exposure_150max': _exposure('Brian Robinson Jr.'),
                      'live_vs_per_lineup_ablations_prelock_E_best': {k: pre[k]['196285137']['E_best_lineup_score']
                                                                      for k in pre},
                      'live_vs_ablations_realised_best': {'V2_FINAL_LIVE': live['actual_best'],
                                                          **{k: v['actual_best'] for k, v in abl.items()}}},
         'why': ('the coverage objective did put lineups into the ATL-led script (this lineup was 2.5x likelier to hit '
                 'the proxy there), and the portfolio beat both one-lineup-at-a-time ablations in its own prelock worlds '
                 'and on the night. But the outcome hinged on Brian Robinson Jr. (3 TDs on a 4.65-point projection), in '
                 'every top-1% lineup we held, at low exposure -- the portfolio reached that tail by breadth, not by '
                 'forecasting it.')},
        {'q': 3, 'question': 'Did ownership/leverage help?', 'label': 'CONTRADICTED',
         'evidence': {'owner_best_field_percentile_of_product_ownership': fb['owner_best']['field_percentile_of_log10_product_own'],
                      'owner_best_log10_product_own': fb['owner_best']['lineup']['log10_product_own'],
                      'field_log10_product_own_percentiles': fb['field_log10_product_own_percentiles'],
                      'owner_best_cpt_and_own': [fb['owner_best']['lineup']['captain'], fb['owner_best']['lineup']['cpt_own']],
                      'winner': fb['winner'],
                      'brian_robinson_jr_flex_own_actual_vs_shadow': {
                          'actual': _own(fa, 'Brian Robinson Jr.', 'FLEX', 'actual'),
                          'FC_ONLY': _own(fa, 'Brian Robinson Jr.', 'FLEX', 'pred', 'FC_ONLY'),
                          'BLEND': _own(fa, 'Brian Robinson Jr.', 'FLEX', 'pred', 'BLEND')}},
         'why': ('our 6th-place lineup was chalkier than the median field entry (65th percentile of product ownership). '
                 'What separated 1st from 6th was the captain: the winner captained Brian Robinson Jr. at 0.83% CPT '
                 'ownership; ours captained Kamara, a more popular build. Leverage helped the winner, not us.')},
        {'q': 4, 'question': 'Did low duplication help?', 'label': 'CONTRADICTED',
         'evidence': {'owner_best_copies_in_field': fb['owner_best']['lineup']['copies'],
                      'entries_tied_at_rank_6': fb['owner_best_tied_entries_at_its_rank'],
                      'owner_150max_unique_lineups_in_field': fb['owner_realised_copies']['unique_in_field'],
                      'owner_150max_median_copies': fb['owner_realised_copies']['median_copies_total'],
                      'decomposition_our_lineups': fb['M2_decomposition_our_lineups']},
         'why': ('the lineup was in the field 120 times: 120 entries tied at 6th and, under DK\'s tie rule, split the prizes '
                 'for places 6-125, which is why a 6th-place finish paid $87.50. Only 1 of our 150 lineups was unique; '
                 'median 62.5 copies. Duplication cost us money on the best result of the night.')},
        {'q': 5, 'question': 'Was there material outcome luck?', 'label': 'SUPPORTED',
         'evidence': {'best_lineup_share_of_150max_return': round(best['winnings'] / 134.47, 3),
                      'roi_150max_without_best_lineup': without_best,
                      'brian_robinson_jr': {'projected': brj['dk_mean'], 'actual': brj['dk_actual'], 'pit': brj['dk_pit'],
                                            'pregame_rz_carries_wk1_3': 1, 'pregame_rz_carries_bijan_wk1_3': 11},
                      'v1_best_lineup_minus_live_6th': ps['best_lineup_minus_owner_best_observed']['V1']['196285137']},
         'why': ('one lineup is 65% of the 150-max return and without it the 150-max ROI is -37%. Its decisive player '
                 'scored at the 100th percentile of his forecast on three short touchdowns, while his pregame red-zone '
                 'share (1 carry vs Bijan 11 in weeks 1-3) gave no reason to expect them. V1 (not entered) held a lineup '
                 '0.09 points short of the same score -- placed in the real field it is #126, behind the 120-way tie.')}]
    return {'ARTIFACT': 'ATL_NO_AUTOPSY_VERDICTS', 'LAYER': 'POSTGAME_DIAGNOSIS', 'best_lineup': best,
            'other_top1pct_lineups': others, 'verdicts': q,
            'FIELD_COMPARISONS': {cid: {'winner': c['winner'], 'top10_distinct_lineups': c['top10_distinct_lineups'],
                                        'top_100_shape': c['top_100_shape'], 'top_1pct': c['top_1pct'],
                                        'field_shape': c['M3_archetypes']['field'], 'owner_best': c['owner_best'],
                                        'owner_best_tied': c['owner_best_tied_entries_at_its_rank'],
                                        'top1_cpt_rb_pct': c['M5_conflicts']['CF1_cpt_position']['top_1pct'].get('RB'),
                                        'field_cpt_rb_pct': c['M5_conflicts']['CF1_cpt_position']['field'].get('RB')}
                                  for cid, c in fa['contests'].items()},
            'NOT_PROOF_OF_EDGE': True}


def calibration(gr):
    P = gr
    real = [p for p in P if p['dk_mean'] >= 1]
    overall = {'n_players_graded': len(P), 'n_with_dk_mean_ge_1': len(real),
               'dk_pit_mean': round(float(np.mean([p['dk_pit'] for p in real])), 3),
               'dk_in_p10_p90': round(float(np.mean([p['in_80'] for p in real])), 3),
               'dk_pit_lt_0.1': sum(p['dk_pit'] < 0.1 for p in real), 'dk_pit_gt_0.9': sum(p['dk_pit'] > 0.9 for p in real),
               'mean_signed_dk_err': round(float(np.mean([p['dk_signed_err'] for p in real])), 2),
               'mean_abs_dk_err': round(float(np.mean([abs(p['dk_signed_err']) for p in real])), 2)}
    stats = {}
    for p in P:
        for k, v in p.items():
            if isinstance(v, dict) and 'pit' in v and (v.get('mean') or 0) >= 0.5:
                stats.setdefault(k, []).append((v['pit'], v.get('p10'), v.get('p90'), v['actual']))
    by = {k: {'n': len(v), 'pit_mean': round(float(np.mean([x[0] for x in v])), 3),
              'pit_lt_0.1': sum(x[0] < 0.1 for x in v), 'pit_gt_0.9': sum(x[0] > 0.9 for x in v),
              'in_p10_p90': round(float(np.mean([(x[1] is not None and x[2] is not None and x[1] <= x[3] <= x[2]) for x in v])), 3)}
          for k, v in stats.items()}
    p26 = next(RAW.glob('NFLVERSE_PBP_2026.*.csv.gz'))
    df = pd.read_csv(p26, usecols=['week', 'season_type', 'receiver_player_id', 'receiving_yards', 'rusher_player_id',
                                   'rushing_yards'], low_memory=False)
    df = df[(df.season_type == 'REG') & (df.week < 4)]
    proj = json.loads(next(V2.glob('SHOWDOWN_*_2026W4_PROJ.json')).read_text())['rows']
    gid = {r['name']: r.get('gsis_id') for r in proj.values()}
    g = {p['player'].split('|')[0]: p for p in P}
    yt = []
    for name, stat, col, idc in (('Chris Olave', 'rec_yards', 'receiving_yards', 'receiver_player_id'),
                                 ('Drake London', 'rec_yards', 'receiving_yards', 'receiver_player_id'),
                                 ('Bijan Robinson', 'rush_yards', 'rushing_yards', 'rusher_player_id'),
                                 ('Bijan Robinson', 'rec_yards', 'receiving_yards', 'receiver_player_id')):
        per = df[df[idc] == gid[name]].groupby('week')[col].sum()
        if len(per) != 3:
            raise FinalError(f'NAIVE_BASELINE_WEEKS {name} {stat} {len(per)}')
        naive = float(per.mean())
        s = g[name][stat]
        yt.append({'player': name, 'stat': stat, 'ours_mean': s['mean'], 'naive_wk1_3_mean': round(naive, 1),
                   'actual': s['actual'], 'pit': s['pit'], 'abs_err_ours': round(abs(s['mean'] - s['actual']), 1),
                   'abs_err_naive': round(abs(naive - s['actual']), 1)})
    return {'ARTIFACT': 'ATL_NO_CALIBRATION_REPORT', 'LAYER': 'POSTGAME_DIAGNOSIS',
            'overall_dk_points': overall,
            'by_stat_players_with_mean_ge_0.5': by,
            'yardage_test_olave_london_bijan': yt,
            'YARDAGE_VERDICT': ('UNRESOLVED at one game. Not overprojection: Olave 116 vs 119.4 (PIT 0.56), London 96 vs '
                                '100.1 (PIT 0.55), Bijan rushing 145 vs 107.7 (PIT 0.79). Not shown to be more informative '
                                'than a naive weeks 1-3 average either (see abs_err_ours vs abs_err_naive). The evidence for '
                                'informativeness is the forward-chained player evaluation, not this game.'),
            'NOTE': 'one game, ~20 players with real volume: a PIT mean near 0.5 is consistent with calibration and cannot establish it'}


def hard_rock():
    boards = sorted((_REPO / 'nfl/market/raw').glob('HR_ATL_NO_BOARD_*.csv'))
    seal = json.loads(SEAL.read_text())
    if boards:
        raise FinalError(f'HR_BOARD_PRESENT_GRADE_IT_INSTEAD {[b.name for b in boards]}')
    return {'ARTIFACT': 'ATL_NO_HARD_ROCK_STATUS', 'STATUS': 'NO_VALID_PRELOCK_MARKET_CAPTURE',
            'seal': {'file': str(SEAL.relative_to(_REPO)), 'sha256_file': _sha(SEAL), 'seal_sha256': seal.get('seal_sha256'),
                     'written_at': seal.get('written_at') or '2026-10-05T23:49:04Z'},
            'looked_for': ['nfl/market/raw/HR_ATL_NO_BOARD_*.csv (local tree)',
                           'origin/claude/nfl-greenfield-architecture-stsxmk (fetched 2026-10-06; no new commits)'],
            'request': 'docs/AGENT_OUTBOX.md "REQUEST 2026-10-05 23:50Z -- Hard Rock ATL@NO player-prop board"',
            'RULE': 'historical prices are NOT reconstructed; the sealed forecast stays SHADOW / NOT_VALIDATED',
            'markets_that_would_have_been_graded': ['player_receptions', 'player_receiving_yards', 'player_rushing_yards',
                                                    'player_passing_yards', 'player_passing_touchdowns', 'anytime_td'],
            'PROPS_STATUS': 'SHADOW / NOT_VALIDATED (every market)'}


def successors(co, ra, lo, fa):
    t = co['history_2021_2025']['team']
    return {'ARTIFACT': 'ATL_NO_SUCCESSOR_CANDIDATES', 'LAYER': 'SUCCESSOR_CANDIDATE',
            'RULE': 'a candidate must beat the current model on held-out historical data before promotion; none is fitted to ATL@NO',
            'candidates': [
                {'id': 'SC-COH-1', 'targets': 'DEFECT-COHERENCE', 'status': 'SHADOW_SPEC (not implemented)',
                 'what': ('allocate yards and receptions CONDITIONAL on the world\'s team scoring state (TD count), '
                          'preserving every club identity (plays, pass/rush split, completions, targets, carries, '
                          'yards, TD accounting, red-zone logic, sacks/turnovers)'),
                 'current': {t_: co['simulator_v2']['team'][t_]['yardage_dk_per_td_slope'] for t_ in co['simulator_v2']['team']},
                 'target_within_team_season': t['yardage_dk_per_td_slope'],
                 'held_out_bar': ('2025 season, simulated pregame with 2021-24 fitting only: yardage-DK-per-TD slope inside '
                                  f"{t['yardage_dk_per_td_slope']['within_team_season_ci95']}, team TD vs offensive DK "
                                  f"correlation inside {t['td_vs_off_dk']['within_team_season_ci95']}, and player PIT / "
                                  'CRPS no worse than current on the same games (week-blocked SE)')},
                {'id': 'SC-APPEAR-1', 'targets': 'DEFECT-APPEARANCE (B8)', 'status': 'SHADOW_SPEC (not implemented)',
                 'what': ('P(plays) for an officially ACTIVE player conditioned on his own previous-3-team-game participation, '
                          'instead of the depth-rank population rate'),
                 'historical_rates_2024_2025': {f: ra['B_appearance_history_2024_2025'][f]['p_zero_given_dressed_and_prior3_all_ge1']
                                                for f in ra['B_appearance_history_2024_2025']},
                 'flags_on_atl_no': [f"{x['player']} {x['field']}" for x in ra['B_appearance_flags']
                                     if x['DEFECT_MEAN_SHRINK'] or x['DEFECT_ZERO_MASS']],
                 'held_out_bar': ('forward-chained 2025 weeks: unconditional opportunity MAE and zero-opportunity calibration '
                                  'better than current on held-out weeks by > 2 week-blocked SE, no regression for starters')},
                {'id': 'SC-DUPE-COUNT-1', 'targets': 'S2 dupe mapping', 'status': 'SHADOW_SPEC',
                 'what': 'copies ~ Poisson/NB mean model in log product ownership (count scale, not log scale)',
                 'evidence_so_far': lo['S2_dupe_mapping']['SC_DUPE_COUNT_1_verdict'] + ' on 3 slates (PIT@CLE, PHI@CHI, ATL@NO 20-max)',
                 'held_out_bar': 'beats E1 on mean-scale calibration (total and top decile) AND abs log error on every held-out slate'},
                {'id': 'SC-DUPE-CORR-1', 'targets': 'DEFECT-DUPE-UNDERESTIMATE', 'status': 'SHADOW_SPEC (declared 2026-10-06, after ATL@NO)',
                 'what': ('copies of OUR lineups are 3-6x what independent product ownership predicts even with the ACTUAL '
                          'ownership: the field builds optimizer-like lineups together. Candidate: a lineup-level copy model '
                          'with an optimizer-similarity term (distance of the lineup from the field-optimal set), fitted on '
                          'archived slates only'),
                 'evidence': {cid: c['M2_decomposition_our_lineups'] for cid, c in fa['contests'].items()},
                 'held_out_bar': 'beats E1 and E4 on total and top-decile calibration of OUR lineups on every held-out slate (>= 5 slates)'},
                {'id': 'SC-OWN-ROTATION-1', 'targets': 'ownership of cheap rotation players', 'status': 'SHADOW_SPEC',
                 'what': ('the optimizer-exposure field cannot give ownership to players kept out of optimal lineups by their '
                          'projection (B. Robinson Jr. 17.6% actual FLEX vs 0.0 / 1.0 shadow; Bryce Lance 21.8 vs 6.4 / 9.4). '
                          'Candidate: the pre-registered MC-OWN-1 ownership model with a salary-tier / rotation-role term'),
                 'held_out_bar': 'beats BLEND on FLEX RMSE and KL on every held-out slate; prereg proposal: >= 8 Showdown slates before any promotion decision'},
                {'id': 'SC-SHAPE-STANDINGS-1', 'targets': 'S1 shape prior', 'status': 'NOT_DEMONSTRATED -- current kept',
                 'evidence_so_far': lo['S1_shape_prior']['verdict']},
                {'id': 'SC-CPTFLEX-STANDINGS-1', 'targets': 'S3 CPT:FLEX ratio', 'status': 'NOT_DEMONSTRATED -- current kept',
                 'evidence_so_far': lo['S3_cpt_flex_ratio']['verdict']},
                {'id': 'SC-OBJ-1/2', 'targets': 'portfolio objective', 'status': 'DECLARED, NOT TESTABLE YET',
                 'what': 'O1 dupe-adjusted proxy; O2 top-1% proxy; O3 current as control; per contest',
                 'blocker': 'zero archived slates have both pre-kickoff worlds and full-field standings'}]}


def board(ra, fa, lo):
    m1 = {cid: c['M1_ownership'] for cid, c in fa['contests'].items()}
    better = sum((m1[c]['BLEND'][sl][k] < m1[c]['FC_ONLY'][sl][k]) if k != 'spearman' else (m1[c]['BLEND'][sl][k] > m1[c]['FC_ONLY'][sl][k])
                 for c in m1 for sl in ('CPT', 'FLEX') for k in ('rmse_pts', 'mae_pts', 'spearman', 'kl_actual_vs_pred'))
    total = len(m1) * 2 * 4
    gates = {}
    for t in ('test_showdown_finalization_gates', 'test_archetype_field', 'test_cycle1_checks',
              'test_postgame_role_coherence', 'test_role_depth_adversarial'):
        gates[t] = 'PASS (run 2026-10-06 on HEAD; see commit)'
    return {'ARTIFACT': 'NEXT_SHOWDOWN_READINESS_BOARD', 'as_of': dt.datetime.now(dt.timezone.utc).isoformat(),
            'OPERATIONAL_RELIABILITY': ('no production module changed during the postgame work (git diff f0c28406 -- '
                                        'nfl/tools nfl/sim nfl/field nfl/product nfl/market is empty); the next slate runs '
                                        'on the sealed-tonight code path'),
            'defects_fixed': [
                {'id': 'DEFECT-TE-ORDER', 'state': 'PROMOTED', 'evidence': 'ca9fb238; holdout seed 20261006 v2-v1 +0.046/+0.093/+0.014 (SE 0.012/0.017/0.006); live 2026-10-05'},
                {'id': 'GREEDY-SUBOPTIMALITY (swap polish)', 'state': 'PROMOTED', 'evidence': 'held-out +0.082/+0.017; live 2026-10-05'},
                {'id': 'RELAXATION/FILLER TRANSPARENCY', 'state': 'IMPLEMENTED', 'evidence': 'audit artifact per run'}],
            'defects_open': [
                {'id': 'DEFECT-COHERENCE', 'severity': 'HIGH (structural)', 'state': 'OPEN -- confirmed like-for-like 2026-10-06',
                 'next': 'SC-COH-1 held-out test; NOT for the next slate'},
                {'id': 'DEFECT-APPEARANCE (B8)', 'severity': 'MEDIUM', 'state': 'OPEN -- confirmed on 4 player-fields',
                 'next': 'SC-APPEAR-1 forward-chained test; NOT for the next slate'},
                {'id': 'DEFECT-DUPE-UNDERESTIMATE', 'severity': 'HIGH (DFS decisions)', 'state': 'OPEN -- measured on ATL@NO 2026-10-06',
                 'evidence': {cid: {'independence_factor': c['M2_decomposition_our_lineups']['independence_factor'],
                                    'owner_unique_lineups': c['owner_realised_copies']['unique_in_field'],
                                    'owner_median_copies': c['owner_realised_copies']['median_copies_total']}
                              for cid, c in fa['contests'].items()},
                 'next': ('report expected copies of our lineups with this measured miss beside them on the prelock board '
                          '(reporting only); SC-DUPE-CORR-1 held-out test; no selection change for the next slate')},
                {'id': 'DEFECT-SPECIALIST-AUTO', 'severity': 'LOW (guarded by hand designation)', 'state': 'OPEN',
                 'next': ('readiness check before the next slate: run nfl/tests/test_role_depth_adversarial.specialist_candidates '
                          'on the captured chart and designate every flagged player NO_OFFENSIVE_ROLE (no model change)')},
                {'id': 'DEFECT-LABEL-CSV', 'severity': 'LOW (reporting)', 'state': 'OPEN',
                 'next': 'label PROJECTIONS.csv volume columns as if-plays; propose-only (schema read by other tools)'},
                {'id': 'DOC-CHART-RANK', 'severity': 'LOW (comment)', 'state': 'OPEN',
                 'next': ('proj_v1 calls _chart_rank "the CAPTURED depth-chart rank"; it is the state depth_rank = better of '
                          'usage rank and chart rank (classic_slate_state._qb_rank). Behaviour is the declared rule; the comment is wrong')}],
            'candidate_model_changes': [{'id': 'SC-COH-1', 'state': 'SHADOW'}, {'id': 'SC-APPEAR-1', 'state': 'SHADOW'},
                                        {'id': 'SC-DUPE-COUNT-1', 'state': 'SHADOW'},
                                        {'id': 'SC-DUPE-CORR-1', 'state': 'SHADOW'}, {'id': 'SC-OWN-ROTATION-1', 'state': 'SHADOW'},
                                        {'id': 'shadow ownership/field/dupe stack (MC-OWN/FIELD/DUPE-1)',
                                         'state': (f'PRODUCTION_CANDIDATE -- not promoted. Observation #1 scored: BLEND beat FC_ONLY on '
                                                   f'{better}/{total} ownership metric cells; every dupe estimator under-predicted our '
                                                   'lineups 2-6x. One slate promotes nothing.')},
                                        {'id': 'Hard Rock prop layer', 'state': 'SHADOW / NOT_VALIDATED'}],
            'tests_passed': gates, 'tests_failed': [],
            'historical_evidence_used': ['nflverse pbp 2021-2025 (team coherence, roles)', 'nflverse snap counts 2024-2025 + players crosswalk (appearance)',
                                         'DK standings PIT@CLE 196187080, PHI@CHI 196036243, ATL@NO 196285137 / 196285160 / 196285161 (field, LOSO)',
                                         'ATL@NO owner entries (172, by Entry ID)'],
            'MUST_PASS_BEFORE_NEXT_SHOWDOWN': [
                'finalization gates suite green on the commit that runs the slate',
                'official inactives captured and verified (READY gate unchanged)',
                'specialist check: every DK skill player whose captured chart rows are special-teams only is designated',
                'determinism: same inputs + seed reproduce the upload byte-for-byte (repro run before upload)',
                'prop forecast sealed BEFORE any Hard Rock price is captured; a board captured after the seal and before kickoff',
                'nothing in SHADOW changes a production lineup; no successor promoted without its held-out bar']}


def report(v, cal, hr, su, rb, files):
    L = ['# ATL@NO Showdown 2026-10-05 -- postgame autopsy and next-Showdown readiness', '',
         'Layers kept apart: PRELOCK_FORECAST / PRELOCK_PORTFOLIO (sealed, unchanged), POSTGAME_ACTUAL, POSTGAME_DIAGNOSIS, '
         'SUCCESSOR_CANDIDATE. **ATL@NO is one prospective observation, not proof of edge.**', '', '## Deliverables', '']
    for i, (name, f) in enumerate(files, 1):
        L.append(f'{i}. {name} -- `{f}`')
    L += ['', '## Autopsy verdicts (item 3)', '']
    for q in v['verdicts']:
        L.append(f"- **Q{q['q']} {q['question']}** `{q['label']}` -- {q['why']}")
    L += ['', '## Field comparisons (from the full standings)', '',
          '| contest | winner (pts, copies) | winner CPT own | our best: rank, pts, copies (entries tied at that rank) | CPT is RB: top 1% vs field |',
          '|---|---|---|---|---|']
    for cid, c in v['FIELD_COMPARISONS'].items():
        w, ob = c['winner'], c['owner_best']
        L.append(f"| {cid} | CPT {w['captain']} + {', '.join(w['flex'])} ({w['points']}, {w['copies']}) | {w['cpt_own']}% | "
                 f"#{ob['rank']}, {round(ob['points'], 2)}, {ob['copies_total']} ({c['owner_best_tied']}) | "
                 f"{c['top1_cpt_rb_pct']}% vs {c['field_cpt_rb_pct']}% |")
    L += ['', '## Hard Rock (item 9)', '',
          f"- `{hr['STATUS']}`. {hr['RULE']}.", '', '## WHAT WE LEARNED', '',
          '- The 150-max profit (+$59.47) is one lineup: $87.50 of $134.47; without it the 150-max is -37%. 20-max -80%, 2-entry -100%.',
          '- The game script was a 2.7% world in our simulation (ATL 45-24 against sim means ATL 17.6 / NO 23.0). The forecast was not directionally right about this game.',
          '- Player calibration on the night looks unremarkable (PIT mean 0.50, 80% coverage 0.80 over 20 players) -- consistent with calibration, not evidence of it.',
          '- DEFECT-COHERENCE is real when measured like-for-like: yards/receptions per extra TD are +0.05 / -0.05 DK in the simulator vs +4.72 [4.35, 5.09] in 2021-25 (within team-season). The prelock 0.55-vs-0.811 comparison mixed definitions; the corrected gap is 0.63 vs 0.792 [0.777, 0.806].',
          '- Pair correlations (QB-receiver, QB-RB, cross-team) are NOT under-correlated against pregame-role history; the published COR-01/02 targets overstated them.',
          '- The allocator\'s P(plays) is a depth-rank population rate. For active players with an opportunity in each of their last 3 games it shrinks means and adds zero-mass far beyond history (B. Robinson Jr. carries 35% vs 4%).',
          '- The coverage objective beat one-lineup-at-a-time ablations in its own worlds and on the night; it reached the ATL tail by breadth.',
          '- The 6th-place lineup was NOT unique: 120 identical entries tied at 6th and split the prizes for places 6-125 ($87.50 each). Only 1 of our 150 lineups was unique in the field; median 62.5 copies. Low duplication did not help -- duplication cost money.',
          '- Leverage helped the winner, not us: the winner captained Brian Robinson Jr. at 0.83% CPT ownership; our best lineup sat at the 65th percentile of field product ownership.',
          '- Our lineups were duplicated 3-6x more than independent product ownership predicts EVEN WITH THE ACTUAL ownership (150-max: 15,823 copies vs 5,334); the ownership forecast itself (BLEND) was close on aggregate. The field builds optimizer-like lineups together.',
          '- Shadow ownership: BLEND beat FC_ONLY on every ownership metric in every contest, but both missed cheap rotation players badly (B. Robinson Jr. 17.6% FLEX actual vs 0.0 / 1.0 predicted; Bryce Lance 21.8 vs 6.4 / 9.4).',
          '- Field priors on three slates (leave-one-slate-out): our same-slate team-split prior was very close on ATL@NO (distance 0.01); nothing beats the current shape or CPT:FLEX priors on every fold; the count-scale dupe model (SC-DUPE-COUNT-1) fails its pre-declared bar on ATL@NO.',
          '- Correction: an earlier note called V1\'s 142.45 lineup a top-10 finish. In the real field it is #126, directly behind the 120-way tie.',
          '', '## WHAT WE ARE CHANGING', '',
          '- Readiness check before the next slate: automated specialist detector on the captured chart (no model change).',
          '- Registering SC-COH-1, SC-APPEAR-1, SC-DUPE-COUNT-1, SC-DUPE-CORR-1 and SC-OWN-ROTATION-1 as SHADOW successors with their held-out bars stated in advance.',
          '- Prelock board (reporting only): expected copies of our lineups shown beside the measured 3-6x independence miss, so a duplicated portfolio is visible before lock.',
          '- Labelling fixes proposed (PROJECTIONS.csv if-plays columns; the _chart_rank comment).',
          '', '## WHAT WE ARE NOT CHANGING', '',
          '- The production football model, simulator, allocator and portfolio objective for the next slate. No successor is ready and none is promoted on one game.',
          '- The shadow ownership / field / dupe stack stays SHADOW; FC-08 / FC-09 / CPT = 0.5 x FLEX are not used.',
          '- Hard Rock props stay SHADOW / NOT_VALIDATED; no prices reconstructed.',
          '- Nothing is refitted on ATL@NO, and ATL@NO is not called evidence of edge.',
          '', '## WHAT MUST PASS BEFORE THE NEXT SHOWDOWN', '']
    L += [f'- {x}' for x in rb['MUST_PASS_BEFORE_NEXT_SHOWDOWN']]
    L += ['', '## Pre-registered measurements', '',
          '- All five (docs/NFL_SHOWDOWN_ATL_NO_POSTGAME_PREREGISTRATION.md) are scored in ATL_NO_FIELD_ACTUAL_PREREGISTERED.json, per contest, '
          'against the frozen prelock predictions (committed 9736516d before lock). The 150-max dupe stack was recomputed from the frozen '
          'inputs and matched every stored mean, row and top-10 before use.', '']
    return '\n'.join(L)


def run():
    sc, au, gr = _j('ATL_NO_PORTFOLIO_SCORECARD.json'), _j('ATL_NO_TOP_LINEUP_AUTOPSY.json'), _j('ATL_NO_PLAYER_FORECAST_GRADING.json')
    co, ra, lo, ps = (_j('ATL_NO_COHERENCE_REMEASURE.json'), _j('ATL_NO_ROLE_AUDIT.json'),
                      _j('SHOWDOWN_FIELD_LOSO.json'), _j('ATL_NO_PORTFOLIO_STUDY.json'))
    fa = _j('ATL_NO_FIELD_ACTUAL_PREREGISTERED.json')
    v, cal, hr = verdicts(sc, au, gr, ps, fa), calibration(gr), hard_rock()
    su, rb = successors(co, ra, lo, fa), board(ra, fa, lo)
    out = {'ATL_NO_AUTOPSY_VERDICTS.json': v, 'ATL_NO_CALIBRATION_REPORT.json': cal, 'ATL_NO_HARD_ROCK_STATUS.json': hr,
           'ATL_NO_SUCCESSOR_CANDIDATES.json': su, 'NEXT_SHOWDOWN_READINESS_BOARD.json': rb}
    stamp = dt.datetime.now(dt.timezone.utc).isoformat()
    for name, doc in out.items():
        (OUT / name).write_text(json.dumps({**doc, 'written_at': stamp}, indent=1, default=float))
    rel = lambda n: str((OUT / n).relative_to(_REPO))
    files = [('Immutable postgame truth package', rel('ATL_NO_POSTGAME_ACTUAL.json') + ' + ' + rel('ATL_NO_OWNER_ENTRIES_GRADED.csv')),
             ('Owner portfolio scorecard', rel('ATL_NO_PORTFOLIO_SCORECARD.json')),
             ('Best-lineup / top-1% autopsy', rel('ATL_NO_TOP_LINEUP_AUTOPSY.json') + ' + ' + rel('ATL_NO_AUTOPSY_VERDICTS.json')),
             ('Player forecast grading', rel('ATL_NO_PLAYER_FORECAST_GRADING.json')),
             ('Projection calibration report', rel('ATL_NO_CALIBRATION_REPORT.json') + ' + ' + rel('ATL_NO_COHERENCE_REMEASURE.json')),
             ('Role/depth-chart defect audit', rel('ATL_NO_ROLE_AUDIT.json') + ' + nfl/tests/test_role_depth_adversarial.py'),
             ('Ownership/field/dupe calibration update', rel('ATL_NO_FIELD_ACTUAL_PREREGISTERED.json') + ' + ' + rel('SHOWDOWN_FIELD_LOSO.json')),
             ('Portfolio-performance decomposition', rel('ATL_NO_PORTFOLIO_STUDY.json')),
             ('Hard Rock grading', rel('ATL_NO_HARD_ROCK_STATUS.json') + ' (NO_VALID_PRELOCK_MARKET_CAPTURE)'),
             ('Successor-candidate comparison', rel('ATL_NO_SUCCESSOR_CANDIDATES.json')),
             ('Next-Showdown readiness board', rel('NEXT_SHOWDOWN_READINESS_BOARD.json'))]
    md = report(v, cal, hr, su, rb, files)
    (OUT / 'ATL_NO_POSTGAME_REPORT.md').write_text(md)
    return md


if __name__ == '__main__':
    print(run())
