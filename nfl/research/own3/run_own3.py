"""OWN-3: gates and scores for the cold-start candidates.

    python3.12 nfl/research/own3/run_own3.py [--part A|B|both] [--games N]

Refuses to run against a modified pre-registration.

Part A -- GATES, on the 2026 week-1 rehearsal slate. Structural, decisive, and
scored against nothing.
Part B -- the CHRONOLOGICAL PARTICIPATION CALIBRATION that decides whether C1 is
admissible at all. Strictly forward-chained: parameters for evaluation season
`ev` are fitted on seasons strictly before `ev`, and every case reproduces the
information state available before kickoff.

No 2026 outcome is used anywhere. Development evidence may reject a candidate;
it may never promote one.
"""
from __future__ import annotations

import argparse
import bisect
import collections
import csv
import gzip
import hashlib
import json
import os
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
for _q in (_ROOT, os.path.join(_ROOT, 'nfl', 'research', 'qb3')):
    if _q not in sys.path:
        sys.path.insert(0, _q)

csv.field_size_limit(10 ** 7)
HERE = os.path.dirname(os.path.abspath(__file__))
PREDECL = os.path.join(HERE, 'predeclaration_own3.md')
PREDECL_SHA = 'aedced9c82f74b5b406e4658ddf8b435fc1582fdfc0e7d759a5a7ff3b5f07c82'
INPUTS = os.path.join(_ROOT, 'nfl', 'research', 'inputs')

EVAL_SEASONS = (2022, 2023, 2024)      # 2020-2021 burn-in, never scored
RANKS = ('rank1', 'rank2', 'rank3plus')


def check_predeclaration():
    with open(PREDECL, 'rb') as fh:
        got = hashlib.sha256(fh.read()).hexdigest()
    if got != PREDECL_SHA:
        raise SystemExit(
            f'PREDECLARATION_MODIFIED: {PREDECL} hashes to {got}, not the '
            f'committed {PREDECL_SHA}. A pre-registration edited after the '
            f'fact is not a pre-registration.')
    return got


def _rk(rank):
    return 'rank1' if rank == 1 else ('rank2' if rank == 2 else 'rank3plus')


# ------------------------------------------------------------------ part A
def part_a(max_games=None, m=400, seed=20260908):
    """Gates. Every one of them is pass/fail and none is traded against a score."""
    from sportsplatform.governance.outcome import State
    from nfl.capture import coverage as C
    from nfl.production import qb_accounting as QBACC
    from nfl.production import qb_v1 as QBV1
    from nfl.production import team_volume_v1 as TV
    from nfl.production.nonqb import engine_rehearsal as ER
    from nfl.production.nonqb import football_engine as FE
    from nfl.production.rehearsal import run_slate as RS

    prior = TV.JOINT_RESIDUALS_DEFAULT
    TV.JOINT_RESIDUALS_DEFAULT = True
    try:
        plan = C.load_week_plan(2026, 1)
        ko = {c.game_id: c.kickoff_utc for c in plan.value}
        games = sorted(ko)[:max_games] if max_games else sorted(ko)
        _, rrows = RS.roster(2026, 1)
        by = collections.defaultdict(list)
        for r in rrows:
            if r['gsis_id'] and r['position'] in ER.POS:
                by[r['team']].append({'gsis_id': r['gsis_id'],
                                      'position': r['position'],
                                      'team': r['team'],
                                      'player_name': r.get('player_name')})
        fits = FE.slate_fits(2026, 1, [q for t in sorted(by) for q in by[t]])
        if fits.state is not State.PASS:
            raise SystemExit(f'slate fits {fits.code}')
        qbp = [{'gsis_id': r['gsis_id'], 'position': r['position'],
                'team': r['team']} for r in rrows
               if r['gsis_id'] and r['position'] == 'QB']
        teams = sorted({q['team'] for q in qbp})
        qa = FE.QA.allocate(2026, 1, teams, qbp, m=m, seed=seed)
        if qa.state is not State.PASS:
            raise SystemExit(f'allocation {qa.code}')

        arms = {}
        for name, flag in (('B0_refuse', False), ('C0_passthrough', True)):
            qo = FE.qb_slate(2026, 1, qbp, m=m, seed=seed,
                             include_cold_start=flag)
            rows, idx = qo.value['rows'], qo.value['index_by_team']
            share = QBACC.reconcile_allocation_share(
                qa.value,
                {t: [rows[i]['gsis_id'] for i in idx.get(t, [])]
                 for t in teams})
            arms[name] = {'flag': flag, 'qo': qo,
                          'n_rows': len(rows),
                          'n_cold_start': qo.evidence.get('n_cold_start_rows', 0),
                          'gate1_allocation_closure':
                              f'{share.state.value}[{share.code}]',
                          'gate1_evidence': {
                              k: v for k, v in share.evidence.items()
                              if k != 'leaks'}}

        # GATE: no forecastable quarterback's draw may change (prohibition 8)
        ro, rn = arms['B0_refuse']['qo'].value, arms['C0_passthrough']['qo'].value
        io = {r['gsis_id']: i for i, r in enumerate(ro['rows'])}
        inn = {r['gsis_id']: i for i, r in enumerate(rn['rows'])}
        diffs, checked = [], 0
        for pid, i in io.items():
            j = inn.get(pid)
            if j is None:
                diffs.append((pid, 'MISSING'))
                continue
            for f in QBV1.FIELDS:
                checked += 1
                if not np.array_equal(np.asarray(ro['draws'][f][i]),
                                      np.asarray(rn['draws'][f][j])):
                    diffs.append((pid, f))
        equiv = {'n_forecastable': len(io), 'field_comparisons': checked,
                 'differing': len(diffs), 'examples': diffs[:5],
                 'PASS': not diffs}

        # engine gates, per arm
        out_arms = {}
        for name, a in arms.items():
            qb = dict(a['qo'].value)
            qb['allocation'] = qa.value
            cold = {r['gsis_id'] for r in qb['rows'] if r.get('cold_start')}
            acc = collections.Counter()
            db_ratio, term_bad, term_tot = [], 0, 0
            disp_zero, disp_n = 0, 0
            for gid in games:
                players = [q for t in gid.split('_')[2:4] for q in by.get(t, [])]
                g, payload = FE.run_game(
                    2026, 1, gid, players, fits.value, m=m, seed=seed,
                    injuries_rows=ER.stub_injuries(2026, 1, players),
                    test_only=True, kickoff_utc=ko[gid], qb=qb)
                for k in ('qb_allocation_share', 'qb_team_volume', 'receiving',
                          'rushing', 'chain', 'cross_layer'):
                    v = g['accounting'].get(k)
                    if isinstance(v, str):
                        acc[f'{k}::{v}'] += 1
                if payload is None or payload.get('qb') is None:
                    continue
                D = payload['qb']['draws']
                qt = np.asarray(payload['qb']['team'])
                tv = TV.forecast(2026, 1, list(g['teams']), m=m, seed=seed)
                for t in g['teams']:
                    sel = (qt == t)
                    if not sel.any():
                        continue
                    s = np.asarray(D['db'], float)[sel].sum(0)
                    b = np.asarray(tv.value[('team_dropbacks_part', t)], float)
                    db_ratio.append(float(np.abs(s - b).max()))
                lhs = (np.asarray(D['att']) + np.asarray(D['sacks'])
                       + np.asarray(D['scr']))
                rhs = np.asarray(D['db'])
                term_bad += int((np.abs(lhs - rhs) > 1e-6).sum())
                term_tot += int(lhs.size)
                ids = payload['qb']['ids']
                dbm = np.asarray(D['db'], float)
                for i, pid in enumerate(ids):
                    if pid in cold:
                        disp_n += 1
                        if dbm[i].std() < 1e-9:
                            disp_zero += 1
            out_arms[name] = {
                'flag': a['flag'], 'n_rows': a['n_rows'],
                'n_cold_start_rows': a['n_cold_start'],
                'gate1_allocation_closure': a['gate1_allocation_closure'],
                'gate1_evidence': a['gate1_evidence'],
                'gate3_team_dropback_closure': {
                    'max_abs_diff_over_team_games':
                        round(max(db_ratio), 6) if db_ratio else None,
                    'team_games': len(db_ratio),
                    'PASS': bool(db_ratio) and max(db_ratio) < 1e-6},
                'gate4_terminal_state_closure': {
                    'violating_cells': term_bad, 'cells': term_tot,
                    'PASS': term_bad == 0},
                'gate7_dispersion': {
                    'cold_start_rows_checked': disp_n,
                    'zero_dispersion_rows': disp_zero,
                    'PASS': disp_zero == 0 if disp_n else None},
                'accounting_states': dict(acc)}
        return {'games': len(games), 'n_draws': m,
                'gate_equivalence_no_forecastable_draw_changed': equiv,
                'arms': out_arms}
    finally:
        TV.JOINT_RESIDUALS_DEFAULT = prior


# ------------------------------------------------------------------ part B
def part_b(m=400):
    """Does C0's allocated share reproduce the observed participation rates?

    Strictly chronological. `qb3_lib.fit` is given seasons strictly before the
    evaluation season, and the room is the DEPTH CHART -- the live information
    state, not the list of men who turned out to play.
    """
    import qb3_lib as Q
    rows = Q.load_qb_panel()
    depth = Q.load_depth()
    frame = Q.build_frame(rows, depth)

    # prior-only per-player dropback ordinals, to identify the cold-start rows
    db_ord = collections.defaultdict(list)
    with gzip.open(os.path.join(INPUTS, 'panel_p3.csv.gz'), 'rt') as fh:
        for r in csv.DictReader(fh):
            if r.get('position') != 'QB' or not r.get('gsis_id'):
                continue
            try:
                db = float(r.get('dropbacks_as_passer') or 0)
            except ValueError:
                db = 0.0
            if db > 0:
                db_ord[r['gsis_id']].append(int(r['season']) * 100
                                            + int(r['week']))
    for k in db_ord:
        db_ord[k].sort()

    by_tg = collections.defaultdict(list)
    for r in frame:
        by_tg[(r['ord'], r['team'])].append(r)

    # league mean team dropbacks from seasons strictly before each eval season
    tdb_by_season = collections.defaultdict(list)
    with gzip.open(os.path.join(INPUTS, 'denom_panel.csv.gz'), 'rt') as fh:
        for r in csv.DictReader(fh):
            tdb_by_season[int(r['season'])].append(
                float(r['team_dropbacks_part']))

    cells = collections.defaultdict(lambda: {'n': 0, 'obs': 0, 'model': []})
    for ev in EVAL_SEASONS:
        par = Q.fit(frame, ev)
        prior_tdb = [v for s, vals in tdb_by_season.items() if s < ev
                     for v in vals]
        if not prior_tdb:
            continue
        budget = float(np.mean(prior_tdb))
        for (ordn, team), room in by_tg.items():
            if ordn // 100 != ev:
                continue
            tq = [(r['pid'], r['rank'], r.get('was_prev_primary', 0))
                  for r in room]
            S = Q.allocate(par, tq, m=m, seed=Q.SEED, ordinal=ordn, team=team)
            for i, r in enumerate(room):
                is_cold = bisect.bisect_left(
                    db_ord.get(r['pid']) or [], ordn) == 0
                # WHERE DOES THE MISCALIBRATION LIVE? If QB3's allocation is
                # equally miscalibrated for FORECASTABLE quarterbacks at the
                # same rank, it is a property of the allocation and not of the
                # cold-start component, and correcting it inside a cold-start
                # model would be fixing the wrong layer.
                cf = cells[('forecastable' if not is_cold else 'cold')
                           + '|' + _rk(r['rank'])]
                cf['n'] += 1
                cf['obs'] += int((r.get('share') or 0.0) > 0.0)
                cf['model'].append(float((S[i] * budget >= 1.0).mean()))
                if not is_cold:
                    continue                       # forecastable; not ours
                c = cells[_rk(r['rank'])]
                c['n'] += 1
                c['obs'] += int((r.get('share') or 0.0) > 0.0)
                c['model'].append(float((S[i] * budget >= 1.0).mean()))
    out = {'eval_seasons': list(EVAL_SEASONS), 'n_draws': m,
           'budget_note': 'team dropback budget is the league mean over '
                          'seasons strictly before the evaluation season; the '
                          'participation margin is driven by the allocated '
                          'share and the budget only matters at the boundary',
           'by_rank': {}}
    for rk in list(RANKS) + [f'{k}|{r}' for k in ('cold', 'forecastable')
                             for r in RANKS]:
        c = cells[rk]
        if not c['n']:
            continue
        obs = c['obs'] / c['n']
        mod = float(np.mean(c['model']))
        out['by_rank'][rk] = {
            'n_cases': c['n'], 'observed_participation': round(obs, 6),
            'model_participation_C0': round(mod, 6),
            'gap_model_minus_observed': round(mod - obs, 6),
            'brier_C0': round(float(np.mean(
                (np.asarray(c['model']) - np.asarray(
                    [1.0] * c['obs'] + [0.0] * (c['n'] - c['obs'])).mean()
                 ) ** 2)), 6)}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--part', default='both', choices=('A', 'B', 'both'))
    ap.add_argument('--games', type=int, default=None)
    ap.add_argument('--draws', type=int, default=400)
    a = ap.parse_args()
    sha = check_predeclaration()
    out = {'artifact': 'OWN3_RESULTS', 'TEST_ONLY': True,
           'predeclaration': 'nfl/research/own3/predeclaration_own3.md',
           'predeclaration_sha256': sha,
           'governance': 'CANDIDATE -- pre-registered, NOT promoted; '
                         'production default include_cold_start=False',
           'no_2026_outcomes_used': True}
    if a.part in ('B', 'both'):
        out['part_B_participation_calibration'] = part_b(m=a.draws)
    if a.part in ('A', 'both'):
        out['part_A_gates'] = part_a(max_games=a.games, m=a.draws)
    dest = os.path.join(HERE, 'own3_results.json')
    with open(dest, 'w') as fh:
        json.dump(out, fh, indent=2, sort_keys=True, default=float)
    print(json.dumps(out, indent=2, sort_keys=True, default=float))
    print(f'\nwrote {dest}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
