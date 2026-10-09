#!/usr/bin/env python3.12
"""Showdown field study from DK standings: pregame ownership / duplication forecasts graded, and field structure.

    python3.12 nfl/research/field_study/showdown_field_study.py POSTGAME_DIR SCENARIO_DIR FC_CSV --out OUT.json

PREGAME vs POSTGAME, KEPT APART. Every forecast graded here was written BEFORE kickoff (file mtimes are recorded);
DK %Drafted and lineup copies come from the postgame standings and are used only as the answer key. Nothing here is a
forecast input.

  1 OWNERSHIP     shadow BLEND / FC_ONLY captain and FLEX ownership (SHOWDOWN_*_SHADOW_BOARD_*.json) against DK
                  %Drafted: MAE, RMSE, Spearman -- and a no-fit pregame baseline (share proportional to the FC FLEX
                  projection, normalised to 100% CPT / 500% FLEX), because a model that does not beat it is not a model.
  2 DUPLICATION   per-lineup predicted exact copies (shadow board) against the field's actual copies of that lineup.
  3 STRUCTURE     field, field top 1% and our entries: salary used, team split, captains, both-QB and K/DST rates,
                  duplication per entry (copies held by OTHER entries), distinct lineups.
One slate is one slate: these are descriptive measurements, not validated model comparisons.
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import gzip
import io
import json
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.postgame import showdown_standings as SS  # noqa: E402
from nfl.tools import fc_qb_scenario_compare as FCC  # noqa: E402


def _spear(a, b):
    ra, rb = np.argsort(np.argsort(a)), np.argsort(np.argsort(b))
    return float(np.corrcoef(ra, rb)[0, 1])


def _err(a, p):
    return {'mae': round(float(np.abs(a - p).mean()), 3), 'rmse': round(float(np.sqrt(((a - p) ** 2).mean())), 3),
            'spearman': round(_spear(a, p), 3), 'n_players': int(a.size)}


def load_contest(standings_doc, cid):
    c = standings_doc['contests'][cid]
    b = gzip.decompress((_REPO / c['provenance']['file']).read_bytes()).decode('utf-8-sig')
    E, _, own = SS.parse(list(csv.reader(io.StringIO(b))), cid)
    ours = {x['entry_id'] for x in c['ours']['entries']}
    return E, own, ours


def ownership(own, scenario_dir, fc_csv, cid):
    act = {s: {n: v['pct_drafted'] for (n, sl), v in own.items() if sl == s} for s in ('CPT', 'FLEX')}
    out = {}
    for p in sorted(pathlib.Path(scenario_dir).glob('SHOWDOWN_*_SHADOW_BOARD_*.json')):
        tag = p.stem.rsplit('SHADOW_BOARD_', 1)[-1]
        L = json.loads(p.read_text())['contests'][cid]['leverage']
        pred = {'CPT': {x['player']: x['shadow_cpt'] or 0 for x in L}, 'FLEX': {x['player']: x['shadow_flex'] or 0 for x in L}}
        out[tag] = {'written_utc': dt.datetime.fromtimestamp(p.stat().st_mtime, dt.timezone.utc).isoformat()}
        for s in ('CPT', 'FLEX'):
            ks = sorted(set(act[s]) | set(pred[s]))
            out[tag][s] = _err(np.array([act[s].get(k, 0) for k in ks]), np.array([pred[s].get(k, 0) for k in ks]))
    flex, _c, _v = FCC.load_fc(fc_csv)
    fcp = {n: v['proj'] for (n, _t), v in flex.items() if v['proj']}
    out['BASELINE_FC_PROPORTIONAL'] = {'definition': 'share proportional to FC FLEX projection; no parameter fitted'}
    for s, tot in (('CPT', 100.0), ('FLEX', 500.0)):
        ks = sorted(set(act[s]) | set(fcp))
        w = np.array([fcp.get(k, 0.0) for k in ks])
        out['BASELINE_FC_PROPORTIONAL'][s] = _err(np.array([act[s].get(k, 0) for k in ks]), w / w.sum() * tot)
    return out


def duplication(E, ours, scenario_dir, cid):
    cnt_f = collections.Counter((e['cpt'], e['flex']) for e in E if e['entry_id'] not in ours)
    out = {}
    for p in sorted(pathlib.Path(scenario_dir).glob('SHOWDOWN_*_SHADOW_BOARD_*.json')):
        lu = json.loads(p.read_text())['contests'][cid].get('lineups') or []
        if not lu:
            continue
        pr = np.array([x.get('pred_dupes_exact') or 0 for x in lu], float)
        ac = np.array([cnt_f[(x['captain'], tuple(sorted(x['flex'] if isinstance(x['flex'], list)
                                                         else [s.strip() for s in x['flex'].split('/')])))] for x in lu], float)
        out[p.stem.rsplit('SHADOW_BOARD_', 1)[-1]] = {
            'n_lineups': int(pr.size), 'pred_mean': round(float(pr.mean()), 1), 'pred_median': float(np.median(pr)),
            'actual_mean': round(float(ac.mean()), 1), 'actual_median': float(np.median(ac)),
            'spearman': round(_spear(pr, ac), 3),
            'median_log_ratio_pred_over_actual': round(float(np.median(np.log((pr + 1) / (ac + 1)))), 3),
            'NOTE': 'predicted for the OFFICIAL sealed lineups; actual = copies held by non-owner entries'}
    return out


def structure(E, ours, state):
    sal = {v['name']: (v['salary'], v['cpt_salary'], v['team'], v['position']) for v in state['players'].values()}
    home = state['home']
    cnt = collections.Counter((e['cpt'], e['flex']) for e in E)
    cnt_f = collections.Counter((e['cpt'], e['flex']) for e in E if e['entry_id'] not in ours)
    F = [e for e in E if e['entry_id'] not in ours]
    O = [e for e in E if e['entry_id'] in ours]
    top = np.percentile([e['points'] for e in F], 99)

    def d(L, own_side):
        if not L:
            return None
        sl = np.array([sal[e['cpt']][1] + sum(sal[x][0] for x in e['flex']) for e in L])
        away = [sum(1 for x in (e['cpt'], *e['flex']) if sal[x][2] != home) for e in L]
        other = np.array([cnt_f[(e['cpt'], e['flex'])] for e in L]) if own_side else \
            np.array([cnt[(e['cpt'], e['flex'])] - 1 for e in L])
        return {'n': len(L), 'mean_salary': round(float(sl.mean())), 'share_salary_le_48000': round(float((sl <= 48000).mean()), 3),
                'away_count_share': {int(k): round(v / len(L), 3) for k, v in sorted(collections.Counter(away).items())},
                'captains': [(k, round(100 * v / len(L), 1)) for k, v in collections.Counter(e['cpt'] for e in L).most_common(8)],
                'both_qbs': round(float(np.mean([sum(sal[x][3] == 'QB' for x in (e['cpt'], *e['flex'])) == 2 for e in L])), 3),
                'has_k': round(float(np.mean([any(sal[x][3] == 'K' for x in (e['cpt'], *e['flex'])) for e in L])), 3),
                'has_dst': round(float(np.mean([any(sal[x][3] == 'DST' for x in (e['cpt'], *e['flex'])) for e in L])), 3),
                'copies_held_by_other_entries': {'median': float(np.median(other)), 'mean': round(float(other.mean()), 1),
                                                 'share_unique': round(float((other == 0).mean()), 3)}}
    win = max(E, key=lambda e: e['points'])
    return {'field': d(F, False), 'field_top_1pct': d([e for e in F if e['points'] >= top], False), 'ours': d(O, True),
            'field_distinct_lineups': len(set((e['cpt'], e['flex']) for e in F)),
            'winning_score': win['points'], 'winning_lineup_copies': cnt[(win['cpt'], win['flex'])]}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('postgame_dir')
    ap.add_argument('scenario_dir')
    ap.add_argument('fc_csv')
    ap.add_argument('--out', required=True)
    a = ap.parse_args(argv)
    pg = pathlib.Path(a.postgame_dir)
    sd = next(pg.glob('*_STANDINGS.json'))
    std = json.loads(sd.read_text())
    state = json.loads(next(pathlib.Path(a.scenario_dir).glob('SHOWDOWN_*_STATE.json')).read_text())
    doc = {'ARTIFACT': 'SHOWDOWN_FIELD_STUDY', 'standings': str(sd.resolve().relative_to(_REPO)), 'contests': {},
           'PREGAME_POSTGAME_SEPARATION': 'forecasts read from prelock files (mtimes recorded); standings are the answer key only'}
    for cid in std['contests']:
        E, own, ours = load_contest(std, cid)
        doc['contests'][cid] = {'ownership': ownership(own, a.scenario_dir, a.fc_csv, cid),
                                'duplication_forecast': duplication(E, ours, a.scenario_dir, cid),
                                'structure': structure(E, ours, state)}
    pathlib.Path(a.out).write_text(json.dumps(doc, indent=1) + '\n')
    for cid, c in doc['contests'].items():
        o = c['ownership']
        print(cid, {k: (v['CPT']['mae'], v['CPT']['spearman']) for k, v in o.items()},
              c['structure']['field']['copies_held_by_other_entries'], c['structure']['ours']['copies_held_by_other_entries'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
