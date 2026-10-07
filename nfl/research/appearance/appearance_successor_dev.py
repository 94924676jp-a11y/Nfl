#!/usr/bin/env python3.12
"""2025 DEVELOPMENT scoring of the appearance successor. SHADOW_ONLY. DEVELOPMENT EVIDENCE ONLY.

    python3.12 nfl/research/appearance/appearance_successor_dev.py [--quick]

2025 has been read three times before this (SC-APPEAR-1 forward test, production-path replay, propagation prototype);
this is the fourth read. Nothing here is confirmatory. The endpoints are the pre-registered ones
(docs/NFL_APPEARANCE_SUCCESSOR_PREREGISTRATION.md section 5), computed on the sc_appear_1_propagation harness
(fit <= 2024, dressed universe, 2025 REG weeks >= 4) with week blocks and club blocks, END TO END through the
production post-steps (A.end_to_end), at 1,000 worlds per arm per game.

Arms: CURRENT (production allocator + production simulate_game_centred), CANDIDATE (SC-APPEAR-1 allocation, no gate),
SUCCESSOR (SC-APPEAR-1 allocation + hurdle gate, field-specific pi). Writes only
nfl/research/appearance/APPEARANCE_SUCCESSOR_DEV_2025.json. Refuses to run unless the pre-registration lock exists
and matches (the dev score is computed after the lock).
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import importlib.util
import json
import math
import pathlib
import sys
import time

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


A = _load('appearance_successor', _REPO / 'nfl/research/appearance/appearance_successor.py')
G = _load('grade_appearance_seal', _REPO / 'nfl/research/appearance/grade_appearance_seal.py')
P2, F1 = A.P2, A.F1
from nfl.sim import football_points as FP  # noqa: E402

OUT = _REPO / 'nfl/research/appearance/APPEARANCE_SUCCESSOR_DEV_2025.json'
N_SIMS = 1000
SEED = 20261007
SCORED = {'RB': ('carries', 'targets'), 'WR': ('targets',), 'TE': ('targets',)}
ARMS = ('CURRENT', 'CANDIDATE', 'SUCCESSOR')


def prereg_locked():
    lock = json.loads(G.PREREG_LOCK.read_text())
    if A.sha_file(G.PREREG) != lock['prereg_sha256']:
        raise A.SuccessorError('PREREG_MODIFIED_AFTER_LOCK')
    return lock


def run(quick=False, log=print):
    lock = prereg_locked()
    t0 = time.time()
    hashes_before = A.production_hashes()
    po = P2.PP.load_panel()
    panel, pos_of = po.value, P2.PP.position_index()
    fitted = P2.fit(panel, pos_of, F1._dressed(P2.FIT_SEASON))
    fr = A.fit_field_rates(panel, pos_of, F1._dressed(A.FIT_SEASON))
    sc_rates = {(p, f): fr['rates'][(p, f, A.N_PRIOR)] for p, f in A.GATED_CELLS}
    if any(abs(sc_rates[k] - fitted['rates'][k]) > 0 for k in sc_rates):
        raise A.SuccessorError('FIT_H3_NOT_EQUAL_SC_APPEAR_1')
    ctx = P2.context(panel, pos_of, P2.TEST_SEASON, F1._dressed(P2.TEST_SEASON),
                     snap_pos=P2._snap_positions(P2.TEST_SEASON))
    tw = A.club_team_weeks(panel, P2.TEST_SEASON)
    model = A.load_model()
    ir = A.V.int_rate(panel, pos_of, through=P2.FIT_SEASON)['int_per_attempt']
    table = FP.club_points_table(FP._rows())
    games = {}
    for (team, wk) in ctx['dressed']:
        games.setdefault(wk, set()).add(team)
    snaps, sgames = _snaps()
    weeks = [6, 12] if quick else sorted(w for w in {g['week'] for g in sgames.values()} if w >= P2.MIN_WEEK)
    units, refused, counts, n_games = [], collections.Counter(), collections.Counter(), 0
    for week in weeks:
        starter = P2.starter_proxy(ctx, week)
        for gi, (gid, g) in enumerate(sorted((k, v) for k, v in sgames.items() if v['week'] == week)):
            if quick and gi >= 4:
                break
            arms = {}
            for c in (g['home'], g['away']):
                prev = sorted(w for w in ctx['team_weeks'].get(c, ()) if w < week)
                pool = P2.pool_for(ctx, c, week, 'DRESSED')
                if len(prev) < P2.N_PRIOR or not pool:
                    arms = None
                    break
                a = A.club_arms(ctx, fitted['depth'], fitted['groups'], sc_rates, c, week, starter, pool, tw,
                                qual_requires_dressed=True)
                if a is None:
                    arms = None
                    break
                arms[c] = a
            if arms is None:
                refused['CLUB_NOT_PROJECTABLE'] += 1
                continue
            fc = FP.centre_for_game(g['home'], g['away'], P2.TEST_SEASON, week, table=table)
            if fc is None:
                refused['NO_FOOTBALL_CENTRE'] += 1
                continue
            centre = A.centre_from_tv(arms)
            seed = SEED + week * 1000 + gi
            outs = {}
            try:
                for arm, key in (('CURRENT', 'cur'), ('CANDIDATE', 'cand'), ('SUCCESSOR', 'cand')):
                    rows = [r for c in (g['home'], g['away']) for r in A.harness_rows(arms[c][key])]
                    rbk = {A.S.player_key(r['name'], r['team']): r for r in rows}
                    sp = A.build_spec(rows, g['home'], g['away'], fc)
                    gates = None
                    if arm == 'SUCCESSOR':
                        gates = {}
                        for c in (g['home'], g['away']):
                            gates.update(A.gates_for(arms[c]['cand'], arms[c]['hist'], fr, c))
                    e = A.end_to_end(model, sp, centre, rbk, ir, N_SIMS, seed, gates=gates)
                    outs[arm] = e
                    if gates:
                        counts.update(e['counts'])
            except A.SuccessorError as ex:
                refused[ex.code] += 1
                continue
            n_games += 1
            for c in (g['home'], g['away']):
                a = arms[c]
                dressed_now = ctx['dressed'].get((c, week), set())
                for rc, rn in zip(a['cur'], a['cand']):
                    gs, pos = rc['_dk'], rc['position']
                    if pos not in SCORED or ctx['pos_src'].get(gs) == 'USAGE_INFERRED' or gs not in dressed_now:
                        continue
                    key = A.S.player_key(gs, c)
                    now = ((panel['players'].get(gs) or {}).get(str(P2.TEST_SEASON)) or {}).get(str(week)) or {}
                    tf = P2.TABLE_FIELD[pos]
                    for f in SCORED[pos]:
                        y = float(now.get(f) or 0.0)
                        y0 = 1.0 if y == 0 else 0.0
                        pi = A.pi_for(fr, pos, f, a['hist'][(gs, f)])
                        u = {'week': week, 'club': c, 'gsis': gs, 'pos': pos, 'field': f, 'y': y, 'y0': y0,
                             'h': a['hist'][(gs, f)], 'qualifies': a['qual'][(gs, f)], 'pi': pi,
                             'rank_table': ((rc.get('allocation') or {}).get(tf) or {}).get('depth_rank_in_group'),
                             'p0_PROJ_CURRENT': 1 - float((rc.get('p_plays') or {}).get(f, 1.0)),
                             'p0_PROJ_CANDIDATE': 1 - pi}
                        for arm in ARMS:
                            x = np.asarray(A.field_counts(outs[arm]['stat_draws'][key], f), float)
                            u[f'p0_DRAW_{arm}'] = float((x == 0).mean())
                            u[f'mean_{arm}'] = float(x.mean())
                            if y > 0:
                                hp = A.conditional_hist(A.histogram(x))
                                u[f'ccrps_{arm}'] = A.crps_hist(hp, y) if hp else float('nan')
                            dk = np.asarray(outs[arm]['draws_final'][key], float)
                            u[f'dk0_{arm}'] = float((dk == 0).mean())
                        for name in ('PROJ_CURRENT', 'PROJ_CANDIDATE') + tuple(f'DRAW_{x}' for x in ARMS):
                            p = G._clip(u[f'p0_{name}'], N_SIMS)
                            u[f'brier_{name}'] = (p - y0) ** 2
                            u[f'log_{name}'] = -(y0 * math.log(p) + (1 - y0) * math.log(1 - p))
                        units.append(u)
            log(f'  week {week} {gid}: games {n_games} units {len(units)} {time.time() - t0:.0f}s')
    if not units:
        raise A.SuccessorError('NO_SCORED_UNITS')
    return summarise(units, refused, counts, n_games, fr, lock, hashes_before, quick, t0)


def _snaps():
    s, g = None, None
    from importlib import import_module  # noqa: F401
    P = _load('sc_appear_1_propagation', _REPO / 'nfl/research/appearance/sc_appear_1_propagation.py')
    return P._snaps(P2.TEST_SEASON)


def _cmp(units, a, b, key='brier'):
    return G._paired(units, a, b, key=key)


def summarise(units, refused, counts, n_games, fr, lock, hashes_before, quick, t0):
    def cohort(us):
        if not us:
            return {'n_units': 0}
        out = {'n_units': len(us), 'observed_P0': sum(u['y0'] for u in us) / len(us), 'arms': {}}
        for name in ('PROJ_CURRENT', 'PROJ_CANDIDATE') + tuple(f'DRAW_{x}' for x in ARMS):
            out['arms'][name] = {'mean_P0': float(np.mean([u[f'p0_{name}'] for u in us])),
                                 'brier': float(np.mean([u[f'brier_{name}'] for u in us])),
                                 'log_score': float(np.mean([u[f'log_{name}'] for u in us]))}
        for arm in ARMS:
            out['arms'][f'DRAW_{arm}']['mean_count_minus_actual'] = float(np.mean([u[f'mean_{arm}'] - u['y'] for u in us]))
            pos = [u[f'ccrps_{arm}'] for u in us if u['y'] > 0 and not math.isnan(u.get(f'ccrps_{arm}', float('nan')))]
            out['arms'][f'DRAW_{arm}']['conditional_crps_given_gt0'] = float(np.mean(pos)) if pos else None
        out['successor_P0_minus_1_minus_pi_mean'] = float(np.mean([u['p0_DRAW_SUCCESSOR'] - (1 - u['pi']) for u in us]))
        return out

    pos = [u for u in units if u['y'] > 0]
    r1 = [u for u in units if u['rank_table'] == 1]
    comps = {
        'PRIMARY__SUCCESSOR_vs_CURRENT_draw_zero_brier': _cmp(units, 'DRAW_CURRENT', 'DRAW_SUCCESSOR'),
        'POSITIVE_COUNT__conditional_crps_SUCCESSOR_vs_CURRENT': _cmp(pos, 'CURRENT', 'SUCCESSOR', key='ccrps'),
        'RANK1__SUCCESSOR_vs_CURRENT_draw_zero_brier': _cmp(r1, 'DRAW_CURRENT', 'DRAW_SUCCESSOR'),
        'S__SUCCESSOR_vs_CANDIDATE_UNGATED_draw_zero_brier': _cmp(units, 'DRAW_CANDIDATE', 'DRAW_SUCCESSOR'),
        'S__CANDIDATE_UNGATED_vs_CURRENT_draw_zero_brier': _cmp(units, 'DRAW_CURRENT', 'DRAW_CANDIDATE'),
        'S__PROJ_CANDIDATE_vs_PROJ_CURRENT_brier': _cmp(units, 'PROJ_CURRENT', 'PROJ_CANDIDATE'),
        'S__SUCCESSOR_vs_CURRENT_log_score': _cmp(units, 'DRAW_CURRENT', 'DRAW_SUCCESSOR', key='log'),
        'S__POSITIVE_COUNT_SUCCESSOR_vs_CANDIDATE_UNGATED': _cmp(pos, 'CANDIDATE', 'SUCCESSOR', key='ccrps'),
    }
    cohorts = {'ALL_RB_WR_TE': cohort(units), 'RANK1': cohort(r1),
               'QUALIFYING_h3': cohort([u for u in units if u['qualifies']]),
               'NON_QUALIFYING': cohort([u for u in units if not u['qualifies']])}
    for pos_, f in A.GATED_CELLS:
        for h in A.HISTORY_CLASSES:
            cohorts[f'{pos_}_{f}_h{h}'] = cohort([u for u in units if u['pos'] == pos_ and u['field'] == f and u['h'] == h])
    # the prereg's bar applied as a DESCRIPTION of development data (never a verdict on 2025)
    ev = G.evaluate([{**u, 'rank_table': u['rank_table']} for u in units])
    doc = {'ARTIFACT': 'APPEARANCE_SUCCESSOR_DEV_2025', 'STATUS': 'SHADOW_ONLY',
           'EVIDENCE_CLASS': ('DEVELOPMENT ONLY. 2025 read for the FOURTH time (forward test, production-path replay, '
                              'propagation prototype, this). Not confirmatory; the prospective evaluation is the test.'),
           'prereg_sha256': lock['prereg_sha256'], 'prereg_locked_at': lock['locked_at'],
           'scored_at': dt.datetime.now(dt.timezone.utc).isoformat(), 'quick_subset': quick,
           'n_games_simulated': n_games, 'n_units': len(units), 'n_weeks': len({u['week'] for u in units}),
           'n_clubs': len({u['club'] for u in units}), 'n_sims_per_arm': N_SIMS, 'refused': dict(refused),
           'hurdle_counts': dict(counts), 'pi': A.rates_json(fr), 'positive_part': A.POSITIVE_PART,
           'comparisons': comps, 'cohorts': cohorts,
           'PREREG_BAR_APPLIED_DESCRIPTIVELY': {k: ev.get(k) for k in ('checks', 't_critical_week_blocked', 'VERDICT')},
           'PREREG_BAR_NOTE': ('the section-5 bar evaluated on DEVELOPMENT data only to show where the candidate '
                               'stands; it is not the pre-registered verdict, which is prospective'),
           'production_files_unchanged': hashes_before == A.production_hashes(),
           'seconds': round(time.time() - t0, 1)}
    OUT.write_text(json.dumps(doc, indent=1, default=float))
    return OUT, doc


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--quick', action='store_true')
    a = ap.parse_args()
    p, d = run(quick=a.quick)
    print(p)
    print(json.dumps({'n_units': d['n_units'], 'primary': d['comparisons']['PRIMARY__SUCCESSOR_vs_CURRENT_draw_zero_brier'],
                      'bar_descriptive': d['PREREG_BAR_APPLIED_DESCRIPTIVELY']}, indent=1, default=float))
