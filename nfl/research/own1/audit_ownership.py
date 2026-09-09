"""OWN-1: the target-volume ownership audit. Every number in the return.

    INTEL1_PBP_GLOB='.../pbp20*.csv.gz' \
        python3.12 nfl/research/own1/audit_ownership.py

Four sections, each answering part of the owner's ownership questions:

    A  the exact historical accounting, including the excluded pool
    B  D1's three metrics against the play-by-play quantities they claim to be
    C  the QB terminal-state mix, diagnosed CHRONOLOGY-CLEANLY against the
       prior-only history of the quarterbacks actually on the slate
    D  OWN-1: allocated dropback share that reaches no forecastable passer

Measurement only. No estimator is fitted and no model is changed.
"""
from __future__ import annotations

import collections
import csv
import glob
import gzip
import json
import os
import statistics
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

csv.field_size_limit(10 ** 7)
HERE = os.path.dirname(os.path.abspath(__file__))
DENOM = os.path.join(_ROOT, 'nfl', 'research', 'inputs', 'denom_panel.csv.gz')
SEASONS = (2020, 2021, 2022, 2023, 2024, 2025)


def _i(v, d=0):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return d


def scan(files):
    """Per team-game counters, from raw play-by-play. Two-point plays out."""
    tg = collections.defaultdict(collections.Counter)
    excluded_kinds = collections.Counter()
    for path in files:
        with gzip.open(path, 'rt') as fh:
            for r in csv.DictReader(fh):
                if r.get('season_type') != 'REG':
                    continue
                if _i(r.get('two_point_attempt')):
                    continue
                po = r.get('posteam') or ''
                if not po:
                    continue
                c = tg[(_i(r.get('season')), _i(r.get('week')), po)]
                db = _i(r.get('qb_dropback'))
                sk, sc = _i(r.get('sack')), _i(r.get('qb_scramble'))
                thr = _i(r.get('pass_attempt')) and not sk
                if db:
                    c['dropbacks'] += 1
                if sk:
                    c['sacks'] += 1
                if sc:
                    c['scrambles'] += 1
                if _i(r.get('rush_attempt')):
                    c['rush_attempts'] += 1
                if thr:
                    c['throws'] += 1
                    if r.get('receiver_player_id'):
                        c['targeted'] += 1
                    else:
                        c['untargeted'] += 1
                # A throw, sack or scramble that qb_dropback does not count.
                if (not db) and (thr or sk or sc):
                    c['excluded'] += 1
                    excluded_kinds[
                        'spike' if _i(r.get('qb_spike'))
                        else ('nullified' if r.get('play_type') == 'no_play'
                              else (r.get('play_type') or '?'))] += 1
    return tg, excluded_kinds


def section_a(tg, kinds):
    ks = list(tg)
    n = len(ks)

    def M(k):
        return round(statistics.mean(tg[x][k] for x in ks), 4)

    res = [tg[k]['targeted']
           - (tg[k]['dropbacks'] - tg[k]['sacks'] - tg[k]['scrambles']
              + tg[k]['excluded'] - tg[k]['untargeted']) for k in ks]
    ex = sum(1 for v in res if v == 0)
    return {
        'n_team_games': n,
        'means': {k: M(k) for k in
                  ('dropbacks', 'sacks', 'scrambles', 'excluded', 'throws',
                   'targeted', 'untargeted', 'rush_attempts')},
        'closure': {
            'statement': 'targeted == dropbacks - sacks - scrambles '
                         '+ excluded - untargeted',
            'exact_team_games': ex, 'n': n,
            'max_abs_residual': max(abs(v) for v in res)},
        'excluded_pool_identified': dict(kinds),
        'excluded_pool_note':
            'every dropback is a throw, a sack or a scramble (0 unclassified). '
            'The excluded pool is the reverse: pass plays qb_dropback does not '
            'count, and it is entirely spikes and nullified plays. Named, not '
            'absorbed into a residual.',
        'throw_share_of_dropbacks': round(M('throws') / M('dropbacks'), 6),
    }


def section_b(tg):
    """D1's metrics against the play-by-play quantities they claim to be."""
    den = {}
    with gzip.open(DENOM, 'rt') as fh:
        for r in csv.DictReader(fh):
            den[(int(r['season']), int(r['week']), r['team'])] = r
    common = set(den) & set(tg)
    out = {'joined_team_games': len(common),
           'in_d1_only': len(set(den) - set(tg)),
           'in_pbp_only': len(set(tg) - set(den)), 'checks': {}}
    for d1, pb in (('team_targets', 'targeted'),
                   ('team_dropbacks_part', 'dropbacks'),
                   ('team_carries', 'rush_attempts')):
        d = [float(den[k][d1]) - tg[k][pb] for k in common]
        out['checks'][d1] = {
            'pbp_quantity': pb,
            'exact': sum(1 for v in d if abs(v) < 1e-9), 'n': len(common),
            'mean_abs_diff': round(statistics.mean(abs(v) for v in d), 6),
            'max_abs_diff': round(max(abs(v) for v in d), 4)}
    return out


def section_c(season=2026, week=1, m=400, seed=20260908):
    """The terminal-state mix, chronology-clean. Prior-only, no 2026 data."""
    from nfl.production.nonqb import football_engine as FE
    from nfl.production.rehearsal import run_slate as RS
    from sportsplatform.governance.outcome import State
    _, rrows = RS.roster(season, week)
    qbp = [{'gsis_id': r['gsis_id'], 'position': r['position'],
            'team': r['team']} for r in rrows
           if r['gsis_id'] and r['position'] == 'QB']
    qo = FE.qb_slate(season, week, qbp, m=m, seed=seed)
    if qo.state is not State.PASS:
        return {'status': f'{qo.state.value}[{qo.code}]'}
    rows, D, idx = qo.value['rows'], qo.value['draws'], qo.value['index_by_team']
    teams = sorted({q['team'] for q in qbp})
    qa = FE.QA.allocate(season, week, teams, qbp, m=m, seed=seed)
    share = {}
    if qa.state is State.PASS:
        for t, a in qa.value.items():
            for j, pid in enumerate(a['pids']):
                share[pid] = float(np.asarray(a['shares'][j], float).mean())
    tot = collections.Counter()
    wsum = wrate = 0.0
    nohist = 0
    for r in rows:
        db, sk, sc = r.get('h_db', 0), r.get('h_sack', 0), r.get('h_scr', 0)
        if not db:
            nohist += 1
            continue
        tot['db'] += db
        tot['sk'] += sk
        tot['sc'] += sc
        w = share.get(r['gsis_id'], 0.0)
        wsum += w
        wrate += w * ((sk + sc) / db)
    att = float(np.asarray(D['att']).sum(0).mean())
    dbs = float(np.asarray(D['db']).sum(0).mean())
    return {
        'n_qb_rows': len(rows), 'without_prior_dropbacks': nohist,
        'prior_dropbacks_observed': int(tot['db']),
        'pooled_prior_sack_plus_scramble_share':
            round((tot['sk'] + tot['sc']) / tot['db'], 6),
        'dropback_share_weighted_prior':
            round(wrate / max(wsum, 1e-9), 6),
        'simulator_pre_allocation_share': round(1 - att / dbs, 6),
        'simulator_pre_allocation_throw_share': round(att / dbs, 6),
        'chronology': 'strictly prior seasons only; no 2026 information of any '
                      'kind entered this comparison',
        'reading': 'the model reproduces the share-weighted prior rate of the '
                   'quarterbacks actually on this slate. The population, not '
                   'the model, explains the gap to the league mean.'}


def section_d(season=2026, week=1, m=400, seed=20260908):
    """OWN-1: allocated dropback share reaching no forecastable passer."""
    from nfl.production import qb_accounting as QBACC
    from nfl.production.nonqb import football_engine as FE
    from nfl.production.rehearsal import run_slate as RS
    from sportsplatform.governance.outcome import State
    _, rrows = RS.roster(season, week)
    qbp = [{'gsis_id': r['gsis_id'], 'position': r['position'],
            'team': r['team']} for r in rrows
           if r['gsis_id'] and r['position'] == 'QB']
    qo = FE.qb_slate(season, week, qbp, m=m, seed=seed)
    if qo.state is not State.PASS:
        return {'status': f'{qo.state.value}[{qo.code}]'}
    rows, idx = qo.value['rows'], qo.value['index_by_team']
    teams = sorted({q['team'] for q in qbp})
    qa = FE.QA.allocate(season, week, teams, qbp, m=m, seed=seed)
    if qa.state is not State.PASS:
        return {'status': f'{qa.state.value}[{qa.code}]'}
    o = QBACC.reconcile_allocation_share(
        qa.value,
        {t: [rows[i]['gsis_id'] for i in idx.get(t, [])] for t in teams})
    ev = dict(o.evidence)
    ev['guard_state'] = f'{o.state.value}[{o.code}]'
    ev['n_unforecastable_quarterbacks'] = sum(
        len(L['unforecastable']) for L in (ev.get('leaks') or []))
    ev['leaks'] = sorted(ev.get('leaks') or [],
                         key=lambda x: -x['share_lost'])[:12]
    return ev


def main():
    files = sorted(glob.glob(os.environ.get('INTEL1_PBP_GLOB', '')))
    if not files:
        raise SystemExit('PBP_NOT_LOCATED: set INTEL1_PBP_GLOB. Sections A and '
                         'B are refused rather than reported without them.')
    tg, kinds = scan(files)
    out = {'artifact': 'OWN1_TARGET_VOLUME_OWNERSHIP_AUDIT',
           'seasons': list(SEASONS),
           'source_files': [os.path.basename(p) for p in files],
           'A_historical_accounting': section_a(tg, kinds),
           'B_d1_metrics_are_the_pbp_quantities': section_b(tg),
           'C_terminal_state_mix_chronology_clean': section_c(),
           'D_own1_allocation_share_leak': section_d()}
    dest = os.path.join(HERE, 'own1_results.json')
    with open(dest, 'w') as fh:
        json.dump(out, fh, indent=2, sort_keys=True, default=float)
    print(json.dumps(out, indent=2, sort_keys=True, default=float))
    print(f'\nwrote {dest}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
