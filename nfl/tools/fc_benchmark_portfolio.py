#!/usr/bin/env python3.12
"""RESEARCH-ONLY Fantasy-Cruncher-benchmarked Showdown portfolio, beside (never instead of) the official one.

    python3.12 nfl/tools/fc_benchmark_portfolio.py SCENARIO_DIR FC_CSV EXPORT --out-dir DIR [--official-dir DIR]

Owner directive 2026-10-08. EXTERNALLY BENCHMARKED, NOT AN INDEPENDENTLY VALIDATED PROPRIETARY FORECAST.

Method, stated so it is not mistaken for anything else:
  * the worlds are OUR scenario's worlds (same world index for every player), so our joint structure is preserved:
    correlations, game script, and the known accounting defects (they are not repaired here);
  * each player's per-world DK points are multiplied by FC FLEX projection / our mean, so his mean equals FC's;
  * a player FC projects at 0 is zeroed; a player FC does not list keeps our draws, and is recorded;
  * the same salaries, the same absent list, the same contests and the same optimizer (showdown_portfolio.run).
Nothing is written into a scenario directory, the official upload is untouched, and FC remains outside every
proprietary projection. Output: DIR/ (the benchmark portfolio) plus DIR/FC_BENCHMARK_COMPARISON.json against the
official portfolio (captain shares, exposures, overlap, team-stack mix).
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import fc_qb_scenario_compare as FCC  # noqa: E402


def benchmark_draws(sd, fc_csv, out):
    sd = pathlib.Path(sd)
    dp = next(sd.glob('SHOWDOWN_*_DRAWS.json'))
    doc = json.loads(dp.read_text())
    flex, _cpt, ver = FCC.load_fc(fc_csv)
    rec = {'scaled': {}, 'zeroed_by_fc': [], 'not_in_fc_kept_ours': [], 'fc_version': ver}
    for k, d in doc['draws'].items():
        name, team = k.rsplit('|', 1)
        a = np.asarray(d, dtype=float)
        m = float(a.mean()) if a.size else 0.0
        f = (flex.get((name, team)) or {}).get('proj')
        if f is None:
            rec['not_in_fc_kept_ours'].append(k)
            continue
        if f == 0:
            if m > 0:
                rec['zeroed_by_fc'].append(k)
            doc['draws'][k] = [0.0] * len(d)
            continue
        if m <= 0:
            rec['not_in_fc_kept_ours'].append(k + ' (our mean 0; cannot rescale)')
            continue
        doc['draws'][k] = (a * (f / m)).tolist()
        rec['scaled'][k] = {'ours_mean': round(m, 3), 'fc': f, 'factor': round(f / m, 4)}
    doc['FC_BENCHMARK'] = ('RESEARCH ONLY: our worlds, each player recentred to the FC FLEX projection. Externally '
                           'benchmarked; not a proprietary forecast; never an official upload.')
    out = pathlib.Path(out)
    out.mkdir(parents=True, exist_ok=True)
    bp = out / dp.name.replace('_DRAWS.json', '_DRAWS_FC_BENCHMARK.json')
    bp.write_text(json.dumps(doc))
    return bp, rec


def _lineups(d):
    up = next(pathlib.Path(d).glob('SHOWDOWN_*_DK_UPLOAD.csv'))
    rows = [r for r in csv.reader(up.open()) if r and r[0] != 'Entry ID']
    return [tuple(x.strip() for x in r[4:10]) for r in rows]


def _exposure(d):
    p = next(pathlib.Path(d).glob('SHOWDOWN_*_EXPOSURES.csv'))
    q = next(pathlib.Path(d).glob('SHOWDOWN_*_CPT_EXPOSURES.csv'))
    fx, cx = collections.Counter(), collections.Counter()
    for r in csv.DictReader(p.open()):
        fx[r['player']] += int(r['n'])
    for r in csv.DictReader(q.open()):
        cx[r['captain']] += int(r['n'])
    return fx, cx


def compare(official, bench):
    lo, lb = _lineups(official), _lineups(bench)
    so, sb = {tuple([x[0]] + sorted(x[1:])) for x in lo}, {tuple([x[0]] + sorted(x[1:])) for x in lb}
    fo, co = _exposure(official)
    fb, cb = _exposure(bench)
    no, nb = len(lo), len(lb)
    ply = sorted(set(fo) | set(fb) | set(co) | set(cb))
    rows = [{'player': p, 'flex_share_official': round(fo[p] / no, 3), 'flex_share_fc_bench': round(fb[p] / nb, 3),
             'cpt_share_official': round(co[p] / no, 3), 'cpt_share_fc_bench': round(cb[p] / nb, 3),
             'cpt_shift': round(cb[p] / nb - co[p] / no, 3)} for p in ply]
    rows.sort(key=lambda r: -abs(r['cpt_shift']))
    return {'entries': [no, nb], 'distinct_lineups': [len(so), len(sb)], 'identical_distinct_lineups': len(so & sb),
            'largest_captain_shifts': rows[:10], 'exposures': rows}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('scenario_dir')
    ap.add_argument('fc_csv')
    ap.add_argument('export')
    ap.add_argument('--out-dir', required=True)
    ap.add_argument('--official-dir')
    a = ap.parse_args(argv)
    from nfl.tools import showdown_portfolio as SPF
    sd = pathlib.Path(a.scenario_dir).resolve()
    out = pathlib.Path(a.out_dir).resolve()
    bp, rec = benchmark_draws(sd, a.fc_csv, out)
    scen = json.loads((sd / 'SCENARIO.json').read_text())
    pre = next(sd.glob('SHOWDOWN_*_DK_UPLOAD.csv')).name.split('_DK_UPLOAD')[0]
    pf = SPF.run(a.export, bp, out, pre, inactives=scen['absent_in_state'],
                 proj_path=next(sd.glob('SHOWDOWN_*_PROJ.json')), state_path=next(sd.glob('SHOWDOWN_*_STATE.json')))
    res = {'ARTIFACT': 'FC_BENCHMARK_PORTFOLIO', 'LABEL': 'EXTERNALLY BENCHMARKED -- RESEARCH ONLY -- NOT FOR UPLOAD',
           'source_scenario': str(sd), 'portfolio': [pf.state.value, pf.code, pf.detail], 'rescaling': rec}
    if a.official_dir and pf.state.value == 'PASS':
        res['vs_official'] = compare(a.official_dir, out)
    (out / 'FC_BENCHMARK_COMPARISON.json').write_text(json.dumps(res, indent=1, default=str) + '\n')
    print(json.dumps({k: res[k] for k in ('portfolio',)}, default=str))
    if 'vs_official' in res:
        v = res['vs_official']
        print('entries', v['entries'], 'distinct', v['distinct_lineups'], 'shared distinct', v['identical_distinct_lineups'])
        for r in v['largest_captain_shifts']:
            print(f"  {r['player']:22s} CPT {r['cpt_share_official']:.3f} -> {r['cpt_share_fc_bench']:.3f}   "
                  f"FLEX {r['flex_share_official']:.3f} -> {r['flex_share_fc_bench']:.3f}")
    return 0 if pf.state.value == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
