#!/usr/bin/env python3.12
"""Market firewall check for one Showdown scenario: does any sportsbook number move the football forecast?

    python3.12 nfl/tools/market_firewall_check.py SCENARIO_DIR [--n-sims 300] [--out FIREWALL.json]

The production path runs proj_v1 with MARKET_ARM = 'FOOTBALL_ONLY' (owner contract 2026-10-03: spread, total and
implied totals are prohibited proprietary inputs). Reading the code is not proof, so this MEASURES it. On the
scenario's own frozen STATE it re-runs role_state -> proj_v1 -> showdown_draws three ways, entirely in a scratch
directory under the git-ignored nfl/dfs/salaries/runs/ (no shared or global path is written):

  A  CAPTURED     the state and TEAM_GAME exactly as captured
  B  PERTURBED    every market field moved hard: this game's total, spread and both implied totals, and
                  total_line / club_spread / spread_line_raw / implied_total / opponent_implied_total / moneyline
                  on EVERY TEAM_GAME row
  C  REMOVED      the same fields set to None everywhere

PASS requires the projection rows and every simulated draw to be byte-identical across A, B and C.

Two POSITIVE CONTROLS stop an "identical" result from meaning only that the harness ignored its inputs:
  P1  the incumbent MARKET arm on A vs B must DIFFER (the perturbation reaches market consumers)
  P2  the FOOTBALL_ONLY arm with one club's 2026 realised points changed must DIFFER (football inputs are live)

Verdicts: PASS_MARKET_BLIND, MARKET_INPUT_CONTAMINATION (A/B/C differ), or HARNESS_NOT_SENSITIVE (a control did
not move, so nothing can be concluded). The market fields stay available downstream, after the seal, only.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import pathlib
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

MARKET_ROW_FIELDS = ('total_line', 'club_spread', 'spread_line_raw', 'implied_total', 'opponent_implied_total',
                     'moneyline')
MARKET_ENV_FIELDS = ('home_implied', 'away_implied', 'total_line', 'home_spread')
SEED = 20261008


def _sha(b):
    return hashlib.sha256(b).hexdigest()


def _tg_variant(tg, mode, points_club=None):
    art = copy.deepcopy(tg)
    rows = art['rows'] if isinstance(art['rows'], list) else list(art['rows'].values())
    for r in rows:
        if mode == 'PERTURBED':
            for f in MARKET_ROW_FIELDS:
                if isinstance(r.get(f), (int, float)):
                    r[f] = -r[f] + 17.0 if f in ('club_spread', 'spread_line_raw', 'moneyline') else r[f] * 0.5 + 3.0
        elif mode == 'REMOVED':
            for f in MARKET_ROW_FIELDS:
                r[f] = None
        if points_club and r.get('club') == points_club and r.get('season') == 2026 and r.get('points') is not None:
            r['points'] = r['points'] + 14
    return art


def _state_variant(st, mode):
    s = copy.deepcopy(st)
    for e in s['environment']['games'].values():
        if mode == 'PERTURBED':
            e['home_implied'], e['away_implied'] = e['away_implied'] + 9.0, e['home_implied'] - 9.0
            e['total_line'] = (e['total_line'] or 44.0) - 15.0
            e['home_spread'] = -(e['home_spread'] or 0.0) - 10.0
        elif mode == 'REMOVED':
            for f in MARKET_ENV_FIELDS:
                e[f] = None
    return s


def arm(state, tg, work, *, market_arm, n_sims):
    from nfl.tools import role_state as RS, proj_v1 as PV, showdown_draws as SD, dst_model, market_response
    from nfl.sim import football_points as FP, game as sim_game
    work.mkdir(parents=True, exist_ok=True)
    sp, tp = work / 'state.json', work / 'TEAM_GAME.json'
    sp.write_text(json.dumps(state))
    tp.write_text(json.dumps(tg))
    saved = {(RS, 'POST'): RS.POST, (RS, 'OUT'): RS.OUT, (PV, 'POST'): PV.POST, (PV, 'ROLE'): PV.ROLE,
             (PV, 'OUT'): PV.OUT, (PV, 'SLATE_WEEK'): PV.SLATE_WEEK, (PV, 'MARKET_ARM'): PV.MARKET_ARM,
             (PV, '_MR'): PV._MR, (SD, 'OUT'): SD.OUT, (dst_model, 'OUT'): dst_model.OUT,
             (FP, 'TG'): FP.TG, (market_response, 'TEAM_GAME'): market_response.TEAM_GAME}
    try:
        RS.POST, RS.OUT = sp, work / 'role.json'
        PV.POST, PV.ROLE, PV.OUT = sp, work / 'role.json', work / 'proj.json'
        PV.SLATE_WEEK, PV.MARKET_ARM, PV._MR = int(state['week']), market_arm, None
        SD.OUT, dst_model.OUT = work / 'draws.json', work / 'dst_rates.json'
        FP.TG, market_response.TEAM_GAME = tp, tp
        r = RS.run()
        if r.state.value != 'PASS':
            return {'error': f'role_state {r.code} {r.detail}'}
        rc = PV.main()
        if rc != 0 or not PV.OUT.exists():
            return {'error': f'proj_v1 rc={rc}'}
        proj = json.loads(PV.OUT.read_text())
        o = SD.build(str(PV.OUT), str(sp), n_sims=n_sims, seed=SEED,
                     volume_centre=sim_game.VOLUME_CENTRE_PROJECTION, n_calib=n_sims)
        if o.state.value != 'PASS':
            return {'error': f'showdown_draws {o.code} {o.detail}'}
        draws = {k: list(v) for k, v in o.value['draws'].items()}
        rows = {k: v for k, v in sorted(proj['rows'].items())}
        return {'rows_sha256': _sha(json.dumps(rows, sort_keys=True, default=str).encode()),
                'draws_sha256': _sha(json.dumps(draws, sort_keys=True).encode()),
                'football_centre': proj.get('football_centre'),
                'means': {k: round(sum(v) / len(v), 4) for k, v in draws.items()},
                'market_arm': proj.get('market_arm')}
    finally:
        for (m, a), v in saved.items():
            setattr(m, a, v)


def check(scenario_dir, n_sims=300):
    sd = pathlib.Path(scenario_dir).resolve()
    stf = next(sd.glob('SHOWDOWN_*_STATE.json'))
    state = json.loads(stf.read_text())
    tgp = _REPO / 'nfl/warehouse/TEAM_GAME.json'
    tg = json.loads(tgp.read_text())
    home = state['home']
    # inside the repository (lineage stamps record repo-relative inputs) and git-ignored; never a shared path
    scratch = _REPO / 'nfl/dfs/salaries/runs'
    scratch.mkdir(parents=True, exist_ok=True)
    root = pathlib.Path(tempfile.mkdtemp(prefix='market_firewall_', dir=scratch))
    runs = {}
    for mode in ('CAPTURED', 'PERTURBED', 'REMOVED'):
        runs[mode] = arm(_state_variant(state, mode), _tg_variant(tg, mode), root / mode,
                         market_arm='FOOTBALL_ONLY', n_sims=n_sims)
    runs['P1_MARKET_ARM_CAPTURED'] = arm(_state_variant(state, 'CAPTURED'), _tg_variant(tg, 'CAPTURED'),
                                         root / 'P1A', market_arm='MARKET', n_sims=n_sims)
    runs['P1_MARKET_ARM_PERTURBED'] = arm(_state_variant(state, 'PERTURBED'), _tg_variant(tg, 'PERTURBED'),
                                          root / 'P1B', market_arm='MARKET', n_sims=n_sims)
    runs['P2_FOOTBALL_POINTS_CHANGED'] = arm(_state_variant(state, 'CAPTURED'),
                                             _tg_variant(tg, 'CAPTURED', points_club=home),
                                             root / 'P2', market_arm='FOOTBALL_ONLY', n_sims=n_sims)
    errs = {k: v['error'] for k, v in runs.items() if 'error' in v}
    key = lambda k: (runs[k].get('rows_sha256'), runs[k].get('draws_sha256'))  # noqa: E731
    blind = not errs and key('CAPTURED') == key('PERTURBED') == key('REMOVED')
    p1 = not errs and key('P1_MARKET_ARM_CAPTURED') != key('P1_MARKET_ARM_PERTURBED')
    p2 = not errs and key('P2_FOOTBALL_POINTS_CHANGED') != key('CAPTURED')
    verdict = ('HARNESS_ERROR' if errs else 'HARNESS_NOT_SENSITIVE' if not (p1 and p2)
               else 'PASS_MARKET_BLIND' if blind else 'MARKET_INPUT_CONTAMINATION')
    moved = {}
    if not blind and not errs:
        a, b = runs['CAPTURED']['means'], runs['PERTURBED']['means']
        moved = {k: [a[k], b.get(k)] for k in a if a[k] != b.get(k)}
    return {'ARTIFACT': 'MARKET_FIREWALL_CHECK', 'scenario_dir': str(sd.relative_to(_REPO)),
            'state_sha256': _sha(stf.read_bytes()), 'team_game_sha256': _sha(tgp.read_bytes()),
            'n_sims': n_sims, 'seed': SEED, 'VERDICT': verdict, 'errors': errs,
            'positive_controls': {'P1_market_arm_moves_with_the_market': p1,
                                  'P2_football_arm_moves_with_football_points': p2},
            'hashes': {k: {'rows': v.get('rows_sha256'), 'draws': v.get('draws_sha256')} for k, v in runs.items()},
            'football_centre_captured': runs['CAPTURED'].get('football_centre'),
            'moved_by_market_if_any': moved,
            'RULE': 'byte-identical projection rows and draws across captured / perturbed / removed market fields, '
                    'with both positive controls moving; written only to a scratch directory'}


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('scenario_dir')
    ap.add_argument('--n-sims', type=int, default=300)
    ap.add_argument('--out')
    a = ap.parse_args()
    res = check(a.scenario_dir, a.n_sims)
    txt = json.dumps(res, indent=1, default=str)
    if a.out:
        pathlib.Path(a.out).write_text(txt + '\n')
    print(json.dumps({k: res[k] for k in ('VERDICT', 'errors', 'positive_controls', 'hashes')}, indent=1))
    sys.exit(0 if res['VERDICT'] == 'PASS_MARKET_BLIND' else 2)
