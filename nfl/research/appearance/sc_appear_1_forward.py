#!/usr/bin/env python3.12
"""SC-APPEAR-1 forward-chained test (declared 2026-10-06 in ATL_NO_SUCCESSOR_CANDIDATES.json). SHADOW_ONLY.

    python3.12 nfl/research/appearance/sc_appear_1_forward.py

QUESTION. For an officially ACTIVE (dressed) RB / WR / TE, what is P(at least one opportunity in the field)? The
production allocator answers with the depth-table appearance rate at his usage rank (proj_v1.depth_shares:
the share of club-weeks in which at least r players of that position recorded any stat). SC-APPEAR-1 answers, for
players who recorded >= 1 opportunity in that field in each of their club's previous 3 games, with the measured
rate for that condition; everyone else keeps the production rate.

FORWARD CHAIN. Everything the predictions use is fitted on 2024 and earlier (depth table through=2024; the
SC-APPEAR-1 rates on 2024 snap counts + panel). Scored on every 2025 regular-season week >= 4. Dressed = present in
nflverse snap counts for that game (offense or special teams), which is what the official ACTIVE list implies.

DECLARED BAR (held_out_bar, recorded before this ran): zero-opportunity calibration better than current on held-out
weeks by > 2 week-blocked SE, and no regression for rank-1 players. The bar's other half (unconditional opportunity
MAE) needs the if-plays volume model and is NOT tested here; it is reported as NOT_TESTED, not as passed.
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import pathlib
import sys

import numpy as np
import pandas as pd

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import player_prior as PP  # noqa: E402
from nfl.tools import proj_v1 as PV  # noqa: E402
from nfl.tools import role_state_history as RSH  # noqa: E402

HIST = _REPO / 'nfl/postgame/raw/role_audit_history'
OUT = _REPO / 'nfl/research/appearance'
FIELDS = [('RB', 'carries'), ('RB', 'targets'), ('WR', 'targets'), ('TE', 'targets')]
EPS = 1e-4


class AppearError(RuntimeError):
    pass


def _dressed(season):
    prov = json.loads((HIST / 'PROVENANCE.json').read_text())
    f = {x['kind']: _REPO / x['file'] for x in prov['files']}
    cw = pd.read_csv(f['players_crosswalk'])
    s = pd.read_csv(f[f'snap_counts_{season}'])
    s = s[s.game_type == 'REG'].merge(cw[['pfr_id', 'gsis_id']], left_on='pfr_player_id', right_on='pfr_id')
    out = collections.defaultdict(set)
    for r in s.itertuples():
        out[(r.team, int(r.week))].add(r.gsis_id)
    if not out:
        raise AppearError(f'NO_SNAPS_{season}')
    return out


def rows_for(panel, pos_of, season, dressed):
    """One row per dressed player-game with a pregame usage rank, field and position."""
    P = panel['players']
    team_weeks = collections.defaultdict(set)
    for g, ss in P.items():
        for w, d in (ss.get(str(season)) or {}).items():
            if d.get('team'):
                team_weeks[d['team']].add(int(w))
    out = []
    weeks = sorted({w for v in team_weeks.values() for w in v})
    for week in weeks:
        if week < 4:
            continue
        depth = RSH.pregame_depth(panel, pos_of, season, week)
        for (team, wk), ids in dressed.items():
            if wk != week:
                continue
            prev = sorted(w for w in team_weeks.get(team, ()) if w < week)[-3:]
            if len(prev) < 3:
                continue
            for g in ids:
                pos = pos_of.get(g)
                if pos not in ('RB', 'WR', 'TE'):
                    continue
                rk = (depth.get(g) or {}).get('pregame_rank')
                if not isinstance(rk, int):
                    continue
                row_now = (P.get(g, {}).get(str(season)) or {}).get(str(week)) or {}
                for p_, fld in FIELDS:
                    if p_ != pos:
                        continue
                    prior = [((P.get(g, {}).get(str(season)) or {}).get(str(w)) or {}).get(fld) or 0 for w in prev]
                    act = [x for x in prior if x > 0]
                    out.append({'season': season, 'week': week, 'team': team, 'gsis': g, 'pos': pos, 'field': fld,
                                'rank': rk, 'prior3_all': all(x > 0 for x in prior),
                                'v_if_plays_proxy': float(np.mean(act)) if act else 0.0,
                                'opp': float(row_now.get(fld) or 0),
                                'y': int((row_now.get(fld) or 0) > 0)})
    if not out:
        raise AppearError(f'NO_ROWS_{season}')
    return pd.DataFrame(out)


def current_p(df, table):
    p = []
    for r in df.itertuples():
        by = table[r.pos]['by_rank']
        ranks = sorted(int(k.split('_')[1]) for k in by)
        k = f'rank_{min(r.rank, ranks[-1])}'
        p.append(by[k]['appearance_rate'])
    return np.array(p, float)


def score(y, p):
    p = np.clip(p, EPS, 1 - EPS)
    return (y - p) ** 2, -(y * np.log(p) + (1 - y) * np.log(1 - p))


def blocked(diff, weeks):
    by = pd.Series(diff).groupby(np.asarray(weeks)).mean()
    return float(by.mean()), float(by.std(ddof=1) / np.sqrt(len(by))), int(len(by))


def run():
    po = PP.load_panel()
    if po.state.value != 'PASS':
        raise AppearError('PANEL')
    panel, pos_of = po.value, PP.position_index()
    table = PV.depth_shares(panel, pos_of, through=2024)
    tr = rows_for(panel, pos_of, 2024, _dressed(2024))
    te = rows_for(panel, pos_of, 2025, _dressed(2025))
    rates = {(p_, f): float(tr[(tr.pos == p_) & (tr.field == f) & tr.prior3_all].y.mean()) for p_, f in FIELDS}
    te['p_current'] = current_p(te, table)
    te['p_candidate'] = [rates[(r.pos, r.field)] if r.prior3_all else r.p_current for r in te.itertuples()]
    res = {}
    for sub, m in (('ALL', np.ones(len(te), bool)), ('QUALIFYING_prior3_all', te.prior3_all.values),
                   ('RANK_1', (te['rank'] == 1).values), ('RANK_2_PLUS_QUALIFYING', ((te['rank'] >= 2) & te.prior3_all).values)):
        d = te[m]
        bc, lc = score(d.y.values, d.p_current.values)
        bn, ln = score(d.y.values, d.p_candidate.values)
        mb, sb, nb = blocked(bc - bn, d.week.values)
        ml, sl, _ = blocked(lc - ln, d.week.values)
        res[sub] = {'n_player_games': int(len(d)), 'observed_rate': round(float(d.y.mean()), 4),
                    'mean_p_current': round(float(d.p_current.mean()), 4), 'mean_p_candidate': round(float(d.p_candidate.mean()), 4),
                    'brier_current': round(float(bc.mean()), 5), 'brier_candidate': round(float(bn.mean()), 5),
                    'brier_improvement_week_blocked': {'mean': round(mb, 5), 'se': round(sb, 5), 'n_weeks': nb,
                                                       'z': round(mb / sb, 2) if sb > 0 else None},
                    'logloss_improvement_week_blocked': {'mean': round(ml, 5), 'se': round(sl, 5),
                                                         'z': round(ml / sl, 2) if sl > 0 else None}}
    mae = {}
    for sub, m in (('QUALIFYING_prior3_all', te.prior3_all.values), ('RANK_1', (te['rank'] == 1).values),
                   ('ALL', np.ones(len(te), bool))):
        d = te[m]
        ec = np.abs(d.p_current * d.v_if_plays_proxy - d.opp).values
        en = np.abs(d.p_candidate * d.v_if_plays_proxy - d.opp).values
        mm, ss, nn = blocked(ec - en, d.week.values)
        mae[sub] = {'mae_current': round(float(ec.mean()), 4), 'mae_candidate': round(float(en.mean()), 4),
                    'improvement_week_blocked': {'mean': round(mm, 4), 'se': round(ss, 4), 'z': round(mm / ss, 2) if ss > 0 else None}}
    by_field = {}
    for p_, f in FIELDS:
        d = te[(te.pos == p_) & (te.field == f) & te.prior3_all]
        by_field[f'{p_}_{f}'] = {'n': int(len(d)), 'observed': round(float(d.y.mean()), 4),
                                 'p_current_mean': round(float(d.p_current.mean()), 4),
                                 'p_candidate': round(rates[(p_, f)], 4)}
    q = res['QUALIFYING_prior3_all']['brier_improvement_week_blocked']
    r1 = res['RANK_1']['brier_improvement_week_blocked']
    passed = q['z'] is not None and q['z'] > 2 and r1['mean'] >= -2 * r1['se']
    mq, m1 = mae['QUALIFYING_prior3_all']['improvement_week_blocked'], mae['RANK_1']['improvement_week_blocked']
    mae_pass = mq['z'] is not None and mq['z'] > 2 and m1['mean'] >= -2 * m1['se']
    doc = {'ARTIFACT': 'SC_APPEAR_1_FORWARD_TEST', 'STATUS': 'SHADOW_ONLY',
           'fit': 'depth table through 2024; SC-APPEAR-1 rates on 2024', 'scored': '2025 REG weeks >= 4, dressed players',
           'sc_appear_1_rates_fit_2024': {f'{k[0]}_{k[1]}': round(v, 4) for k, v in rates.items()},
           'results': res, 'qualifying_by_field': by_field,
           'BAR_zero_opportunity_calibration': 'PASS' if passed else 'FAIL',
           'unconditional_opportunity_mae_PROXY': mae,
           'BAR_unconditional_opportunity_MAE': (('PASS' if mae_pass else 'FAIL') + ' -- PROXY: the if-plays volume is '
                                                 'the prior-3-game mean when active, identical for both arms; the '
                                                 'production conditional_volume was not replayed on 2025'),
           'VERDICT': ('zero-opportunity half of the bar PASSES on held-out 2025; promotion still needs the MAE half and the '
                       'owner' if passed else 'NOT DEMONSTRATED on held-out 2025'),
           'written_at': dt.datetime.now(dt.timezone.utc).isoformat()}
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / 'SC_APPEAR_1_FORWARD_TEST.json'
    p.write_text(json.dumps(doc, indent=1))
    return p, doc


if __name__ == '__main__':
    p, doc = run()
    print(p)
    print(json.dumps({k: doc[k] for k in ('sc_appear_1_rates_fit_2024', 'results', 'qualifying_by_field',
                                          'BAR_zero_opportunity_calibration', 'VERDICT')}, indent=1))
