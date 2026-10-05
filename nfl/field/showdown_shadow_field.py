#!/usr/bin/env python3.12
"""SHADOW Showdown field: predicted CPT/FLEX ownership and duplication. EXTERNAL_RESEARCH_SHADOW. Not validated.

    python3.12 nfl/field/showdown_shadow_field.py EXPORT FC_CSV OUT_DIR [--absent JSON]

NEVER A FOOTBALL INPUT. Nothing in the projection or simulator reads this. It models what the FIELD will
build, so it is built from what the field sees -- a public projection -- not from our numbers.

METHOD (from the owner's research pack, nfl/research/external/2026-10-05_owner_pack, SaberSim 3:49/3:16
and 6:01): ownership is read off thousands of high-variance optimizer builds over an industry projection.
Here: K field lineups, each the exact DK-legal optimum (optimal_worlds.solve: CPT x1.5, both teams, cap)
over the FantasyCruncher projection multiplied by independent lognormal noise exp(s*z - s^2/2). The noise
scale s is the one free parameter. It is NOT fitted to football; it is chosen to best reproduce five
external field-ownership reference points quoted in the Stokastic ATL@NO transcript (Kamara 33, Miller 13,
Lance 25, Dotson 18, Zaccheaus 10 per cent), reported at every candidate s so the choice is visible.

DUPLICATION, two estimators (ETR 43:54 / SaberSim 3:09):
  exact      copies of the exact lineup in the shadow field, scaled to the contest's field size
  product    field size x CPT ownership x product of FLEX ownerships (independence; SaberSim notes it
             under-counts correlated stacks and over-counts very low-salary builds)
Field sizes are ESTIMATES from prize pool / (fee x 0.85) and are labelled so.

KNOWN LIMITS: an optimizer field spends nearly all salary (real fields leave more); no stake- or
entry-limit-specific ownership sets (SaberSim keeps 13); one public projection, not an aggregate.
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import math
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import showdown_to_portfolio as S  # noqa: E402
from nfl.dfs.showdown import optimal_worlds as OW  # noqa: E402

LABEL = 'EXTERNAL_RESEARCH_SHADOW'
SIGMAS = (0.25, 0.40, 0.60)
K = 5000
SEED = 20261005
ANCHORS = {'Alvin Kamara': 33.0, 'Kendre Miller': 13.0, 'Bryce Lance': 25.0, 'Jahan Dotson': 18.0,
           'Olamide Zaccheaus': 10.0}
ANCHOR_SOURCE = 'Stokastic ATL@NO show 2026-10-05 (owner transcript), 45:18 / 1:10:53 / 26:57; UNVERIFIED_EXTERNAL'
#: prize pool and fee from the DK contest names; rake assumed 15% -> field ~ prize / (fee * 0.85). ESTIMATE.
CONTEST_PRIZE = {'196285137': (100000, 0.50), '196285160': (10000, 0.25), '196285161': (5000, 0.10)}


def fc_projection(fc_csv):
    rows = list(csv.reader(open(fc_csv, newline='', encoding='utf-8-sig')))
    hdr = next(i for i, r in enumerate(rows) if 'Player' in r and 'FC' in r)
    H = {h: j for j, h in enumerate(rows[hdr])}
    out = {}
    for r in rows[hdr + 1:]:
        if len(r) < len(H) or r[H['Pos']] == 'CPTN':
            continue
        out[(r[H['Player']], r[H['Team']])] = float(r[H['FC']] or 0)
    return out


def field(slate, absent, fc, sigma, k=K, seed=SEED):
    rng = np.random.default_rng(seed)
    players = []
    for key, v in slate['players'].items():
        p = fc.get((v['name'], v['dk_team']), 0.0)
        if key in absent or p <= 0:
            continue
        z = rng.standard_normal(k)
        players.append({'name': key, 'team': v['dk_team'], 'pos': v['position'], 'tag': S.TAG_NOT_CLAIMED,
                        'salary': v['flex']['salary'], 'cpt_salary': v['cpt']['salary'],
                        'draws': p * np.exp(sigma * z - sigma * sigma / 2.0)})
    o = OW.solve(players, cap=S.SALARY_CAP, n_flex=S.N_FLEX, require_team_coverage=True)
    nm = o.value['names']
    lines = []
    for ln in o.value['lineups']:
        if ln is None:
            continue
        c, f = ln
        lines.append((nm[c], tuple(sorted(nm[i] for i in f))))
    return lines


def ownership(lines, slate):
    n = len(lines)
    cpt = collections.Counter(c for c, _ in lines)
    flex = collections.Counter(k for _, f in lines for k in f)
    keys = set(cpt) | set(flex)
    return {k: {'cpt': 100.0 * cpt[k] / n, 'flex': 100.0 * flex[k] / n, 'total': 100.0 * (cpt[k] + flex[k]) / n}
            for k in keys}


def run(export, fc_csv, out_dir, absent=()):
    ing = S.s1_ingest(pathlib.Path(export))
    slate = S.s2_slate_identity(ing.value['pool']).value
    absent = set(absent)
    absent_keys = {k for k, v in slate['players'].items() if v['name'] in absent or k in absent}
    fc = fc_projection(fc_csv)
    sweep, fields = {}, {}
    for s in SIGMAS:
        L = field(slate, absent_keys, fc, s)
        own = ownership(L, slate)
        err = {a: round(own.get(next((k for k in slate['players'] if slate['players'][k]['name'] == a), ''), {}).get('total', 0.0) - v, 1)
               for a, v in ANCHORS.items()}
        sweep[s] = {'anchor_errors_pct_pts': err, 'rmse': round(math.sqrt(sum(e * e for e in err.values()) / len(err)), 2)}
        fields[s] = (L, own)
    best = min(sweep, key=lambda s: sweep[s]['rmse'])
    L, own = fields[best]
    sal = []
    for c, f in L:
        v = slate['players']
        sal.append(S.SALARY_CAP - (v[c]['cpt']['salary'] + sum(v[x]['flex']['salary'] for x in f)))
    exact = collections.Counter(L)
    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / 'SHOWDOWN_ATL_NO_SHADOW_OWNERSHIP.csv').open('w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['player', 'team', 'pos', 'salary', 'fc_flex_proj', 'shadow_cpt_own_pct', 'shadow_flex_own_pct',
                    'shadow_total_own_pct', 'label'])
        for k, v in sorted(own.items(), key=lambda kv: -kv[1]['total']):
            p = slate['players'][k]
            w.writerow([p['name'], p['dk_team'], p['position'], p['flex']['salary'], fc.get((p['name'], p['dk_team'])),
                        round(v['cpt'], 2), round(v['flex'], 2), round(v['total'], 2), LABEL])
    doc = {'ARTIFACT': 'SHOWDOWN_SHADOW_FIELD', 'label': LABEL, 'VALIDATED': False,
           'NOT_A_FOOTBALL_INPUT': True, 'field_projection': 'FantasyCruncher FLEX projection (public), x1.5 at CPT',
           'k_lineups': K, 'sigma_sweep': {str(s): v for s, v in sweep.items()}, 'sigma_chosen': best,
           'anchors': ANCHORS, 'anchor_source': ANCHOR_SOURCE,
           'salary_left': {'mean': round(float(np.mean(sal)), 0), 'p50': float(np.median(sal)),
                           'share_0': round(float(np.mean(np.array(sal) == 0)), 3),
                           'NOTE': 'an optimizer field spends nearly everything; real fields leave more'},
           'exact_duplication_in_shadow_field': {'distinct_lineups': len(exact), 'top': [[c, list(f), n] for (c, f), n in exact.most_common(10)]},
           'field_size_estimates': {c: round(p / (f * 0.85)) for c, (p, f) in CONTEST_PRIZE.items()},
           'FIELD_SIZE_NOTE': 'ESTIMATE: prize / (fee x 0.85); replace with the real entry counts when known'}
    (out_dir / 'SHOWDOWN_ATL_NO_SHADOW_FIELD.json').write_text(json.dumps(doc, indent=1, default=str))
    np.save(out_dir / 'shadow_field_lineups.npy', np.array([[c] + list(f) for c, f in L], dtype=object), allow_pickle=True)
    return doc, own, exact, slate


def lineup_dupes(lineups, own, exact, k, field_size):
    """Predicted copies of each of OUR lineups in a field of `field_size` (both estimators)."""
    out = []
    for c, f in lineups:
        key = (c, tuple(sorted(f)))
        ex = exact.get(key, 0) / k * field_size
        prod = (own.get(c, {}).get('cpt', 0) / 100.0) * math.prod(own.get(x, {}).get('flex', 0) / 100.0 for x in f)
        geo = (max(prod, 1e-12)) ** (1 / 6)
        out.append({'pred_dupes_exact': round(ex, 1), 'pred_dupes_product': round(prod * field_size, 2),
                    'geomean_ownership': round(geo * 100, 2)})
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('export')
    ap.add_argument('fc')
    ap.add_argument('out')
    ap.add_argument('--absent')
    a = ap.parse_args()
    ab = json.loads(pathlib.Path(a.absent).read_text()) if a.absent else []
    doc, own, exact, slate = run(a.export, a.fc, a.out, ab)
    print(json.dumps({k: doc[k] for k in ('sigma_sweep', 'sigma_chosen', 'salary_left', 'field_size_estimates')}, indent=1))
