#!/usr/bin/env python3.12
"""Next-slate SHADOW duplication comparison -- pre-registration section 7 (the confirmatory test). SHADOW_ONLY.

    python3.12 nfl/field/showdown_dupe_shadow.py --export DKEntries.csv --ownership SHADOW_OWNERSHIP.csv \
        --lineups FINAL_LINEUPS.csv --contest 196xxxxxx=237812 [--contest ...] [--fc FC.csv] \
        [--model B3] [--exclude-train ATL_NO] --out OUT.json

Run BEFORE LOCK on the next Showdown. For every production lineup it records the predicted number of OTHER entries
with the identical lineup under (a) B0, the current independent-product estimator, and (b) the named candidate
model (structural parameters fitted on the archived slates only; ownership = the slate's FROZEN shadow forecast).
The output is sealed (sha256 of its own content) and must be committed before lock; after the slate, the standings
grade it. NOTHING HERE IS READ BY SELECTION: it does not change a lineup, an exposure or the objective.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import math
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.field import showdown_dupe_research as DR  # noqa: E402

FEATURES = {'B1': [], 'B3S': ['stack_cpt_pc_own_qb', 'both_qbs', 'split_5_1', 'split_4_2', 'any_k_dst']}
FEATURES['B2'] = [f'sal_{n}' for n in DR.SAL_NAMES[:4]]
FEATURES['B3'] = FEATURES['B2'] + FEATURES['B3S']
FEATURES['B4'] = FEATURES['B3'] + ['fc_gap_pts', 'fc_top100']
ARCHIVE = {'PIT_CLE': 'PIT_CLE', 'PHI_CHI': 'PHI_CHI', 'ATL_NO': 'ATL_NO_160'}


class ShadowError(RuntimeError):
    pass


def train(model, exclude):
    names = FEATURES[model]
    needs_sal = any(n.startswith('sal_') for n in names)
    needs_fc = any(n.startswith('fc_') for n in names)
    sl = DR.load_slates()
    Us = []
    for slate, cid in ARCHIVE.items():
        if slate in exclude:
            continue
        s = sl[cid]
        if (needs_sal and not s['has_salary']) or (needs_fc and s['fc'] is None):
            continue
        Us.append(DR.build_universe(s))
    if not Us:
        raise ShadowError(f'NO_TRAINING_SLATE for {model} excluding {exclude}')
    theta, info = DR.maxent_train(Us, names)
    return names, theta, [U['id'] for U in Us], info


def run(a):
    meta = DR._pool_meta(pathlib.Path(a.export))
    fc = DR._fc(pathlib.Path(a.fc)) if a.fc else None
    own = list(csv.DictReader(open(a.ownership)))
    if not own:
        raise ShadowError('OWNERSHIP_EMPTY')
    cpt = {r['player']: float(r['shadow_cpt_own_pct']) / 100 for r in own}
    flx = {r['player']: float(r['shadow_flex_own_pct']) / 100 for r in own}
    names, theta, trained_on, tinfo = train(a.model, set(a.exclude_train or []))
    U = DR.forecast_universe('NEXT_SLATE', cpt, flx, meta, fc, 1)
    lq, minfo = DR.maxent_fit_marginals(U, theta, names)
    q = np.exp(lq)
    sizes = dict(x.split('=') for x in a.contest)
    rows = []
    for r in csv.DictReader(open(a.lineups)):
        cid = r['contest_id']
        if cid not in sizes:
            raise ShadowError(f'CONTEST_SIZE_MISSING {cid}')
        N = int(sizes[cid])
        flex = [r[f'FLEX{i}'] for i in range(1, 6)]
        e1 = N * cpt.get(r['CPT'], 0.0) * math.prod(flx.get(x, 0.0) for x in flex)
        loc = DR.locate(U, r['CPT'], flex)
        rows.append({'contest_id': cid, 'captain': r['CPT'], 'flex': flex,
                     'B0_independent_copies': round(e1, 3),
                     f'{a.model}_copies': None if loc is None else round(float(N * q[loc]), 3),
                     'outside_universe': loc is None})
    body = {'ARTIFACT': 'SHOWDOWN_DUPE_SHADOW_COMPARISON', 'STATUS': 'SHADOW_ONLY -- NOT READ BY SELECTION',
            'prereg': 'docs/NFL_SHOWDOWN_DUPLICATION_PREREGISTRATION.md section 7',
            'model': a.model, 'features': names, 'theta': dict(zip(names, [round(float(x), 5) for x in theta])),
            'trained_on': trained_on, 'excluded_from_training': sorted(a.exclude_train or []), 'train_info': tinfo,
            'ownership_file': {'path': a.ownership, 'sha256': hashlib.sha256(pathlib.Path(a.ownership).read_bytes()).hexdigest()},
            'lineups_file': {'path': a.lineups, 'sha256': hashlib.sha256(pathlib.Path(a.lineups).read_bytes()).hexdigest()},
            'marginal_fit': minfo, 'contest_sizes': sizes, 'lineups': rows,
            'summary': {cid: {'n': sum(r['contest_id'] == cid for r in rows),
                              'B0_total': round(sum(r['B0_independent_copies'] for r in rows if r['contest_id'] == cid), 1),
                              f'{a.model}_total': round(sum(r[f'{a.model}_copies'] or 0 for r in rows if r['contest_id'] == cid), 1),
                              'outside_universe': sum(r['outside_universe'] for r in rows if r['contest_id'] == cid)}
                        for cid in sizes},
            'written_at': dt.datetime.now(dt.timezone.utc).isoformat()}
    body['seal_sha256'] = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
    out = pathlib.Path(a.out)
    if out.exists():
        raise ShadowError(f'OUTPUT_EXISTS_WRITE_ONCE {out}')
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(body, indent=1))
    return out, body


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--export', required=True)
    ap.add_argument('--ownership', required=True)
    ap.add_argument('--lineups', required=True)
    ap.add_argument('--contest', action='append', required=True, help='CONTEST_ID=FIELD_SIZE')
    ap.add_argument('--fc')
    ap.add_argument('--model', default='B3', choices=sorted(FEATURES))
    ap.add_argument('--exclude-train', action='append')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    p, b = run(a)
    print(p)
    print(json.dumps(b['summary'], indent=1), b['trained_on'], b['theta'])
