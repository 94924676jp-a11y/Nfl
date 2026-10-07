#!/usr/bin/env python3.12
"""Next-slate SHADOW duplication diagnostic -- pre-registration section 7 (the confirmatory test). SHADOW_ONLY.

    python3.12 nfl/field/showdown_dupe_shadow.py --export DKEntries.csv --ownership SHADOW_OWNERSHIP.csv \
        --lineups FINAL_LINEUPS.csv --contest 196xxxxxx=237812[:150] [--contest ...] [--fc FC.csv] \
        [--model B4 --model B3S] [--legacy-dupe-stack SHOWDOWN_..._DUPE_STACK_BLEND.json] \
        [--exclude-train ATL_NO] --kickoff 2026-10-12T17:00:00Z --out OUT.json [--dry-run]

Run BEFORE LOCK on the exact production lineups. For every lineup it records the predicted number of entries in the field
holding the identical lineup (all copies; see CONVENTIONS) under
  * B0 / E1 -- the legacy independent-product estimator the production boards print (N x cpt% x prod flex%);
  * E2 / E3 / E4 -- the legacy archetype-field estimates, when a DUPE_STACK artifact is passed (it stores per-lineup
    rows only for small contests; elsewhere they are NOT_STORED, never zero);
  * every named maxent model (default B4 and B3S), structural parameters fitted on the archived slates only,
    marginals = the slate's FROZEN shadow ownership forecast;
and the disagreement between them, plus the lineup's construction: salary used / left, captain, team split, QB
stack structure, K/DST structure, cheap-player composition, and the contest type.

A model whose inputs are absent (B4 without an FC file, a salary model without salaries) is reported as
NOT_AVAILABLE with the reason -- the tool never silently drops to a weaker model.

FROZEN BEFORE KICKOFF. Write-once, sealed with the sha256 of its own content. Without --dry-run it refuses to run at
or after --kickoff (SHADOW_AFTER_KICKOFF): a postlock "shadow" would be graded against a field it could have seen.
NOTHING HERE IS READ BY SELECTION: it does not change a lineup, an exposure or the objective.
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import hashlib
import json
import math
import pathlib
import re
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
DEFAULT_MODELS = ('B4', 'B3S')
# Reporting bands only -- no decision reads them. 1000 is the CHEAP_SALARY the candidate generator already uses
# (nfl/dfs/showdown/candidates.py); 3000 separates the remaining sub-starter band from midrange for the report.
CHEAP_BANDS = (('le_1000', 0, 1000), ('1100_2900', 1100, 2900))
# A 2x disagreement is the flag ratio the legacy archetype-field board already uses (FLAG_RATIO, E1 vs E3).
DISAGREE_LOG2 = 1.0


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


def contest_type(name, field_size, our_entries, declared_max=None):
    m = re.search(r'\[(\d+)\s*Entry Max\]', name or '', re.I)
    from_name = int(m.group(1)) if m else (1 if re.search(r'single entry', name or '', re.I) else None)
    if declared_max is not None and from_name is not None and declared_max != from_name:
        raise ShadowError(f'CONTEST_MAX_CONFLICT name says {from_name}, declared {declared_max}: {name}')
    mx = declared_max if declared_max is not None else from_name
    return {'name': name or None, 'field_size': field_size, 'our_entries': our_entries,
            'max_entries_per_user': mx,
            'max_entries_source': 'DECLARED' if declared_max is not None else ('NAME' if from_name else None),
            'class': f'{mx}-max' if mx else 'UNKNOWN_MAX_ENTRIES'}


def construction(cpt, flex, meta):
    """Descriptive construction of one lineup. Missing metadata is reported as such, never filled."""
    names = [cpt] + list(flex)
    missing = [p for p in names if p not in meta]
    if missing:
        return {'METADATA_MISSING': missing}
    sal = [meta[cpt]['cpt_salary']] + [meta[x]['flex_salary'] for x in flex]
    used = sum(sal) if all(isinstance(s, (int, float)) for s in sal) else None
    pos = {p: meta[p]['position'] for p in names}
    team = {p: meta[p]['team'] for p in names}
    split = collections.Counter(team.values())
    qbs = [p for p in names if pos[p] == 'QB']
    ct = team[cpt]
    own_pc = [x for x in flex if pos[x] in ('WR', 'TE') and team[x] == ct]
    if pos[cpt] == 'QB':
        qb_struct = 'CPT_QB_WITH_OWN_PASS_CATCHER' if own_pc else 'CPT_QB_NAKED'
    elif pos[cpt] in ('WR', 'TE') and any(pos[x] == 'QB' and team[x] == ct for x in flex):
        qb_struct = 'CPT_PASS_CATCHER_WITH_OWN_QB'
    elif qbs:
        qb_struct = 'QB_IN_FLEX_NOT_STACKED_WITH_CPT'
    else:
        qb_struct = 'NO_QB'
    kd = [p for p in names if pos[p] in ('K', 'DST')]
    flex_sal = {x: meta[x]['flex_salary'] for x in flex}
    cheap = {b: sorted(x for x, s in flex_sal.items() if isinstance(s, (int, float)) and lo <= s <= hi)
             for b, lo, hi in CHEAP_BANDS}
    big = max(split.values())
    return {'salary_used': used, 'salary_left': None if used is None else DR.CAP - used,
            'captain': cpt, 'captain_position': pos[cpt], 'captain_team': ct,
            'team_split': dict(sorted(split.items())), 'split_class': f'{big}-{6 - big}',
            'qb_count': len(qbs), 'qb_structure': qb_struct, 'both_qbs': len(qbs) >= 2,
            'own_pass_catchers_with_cpt': len(own_pc),
            'k_dst': {'count': len(kd), 'players': kd, 'captain_is_k_or_dst': pos[cpt] in ('K', 'DST'),
                      'kickers': sum(pos[p] == 'K' for p in kd), 'dst': sum(pos[p] == 'DST' for p in kd)},
            'cheap_flex': {b: {'n': len(v), 'players': v} for b, v in cheap.items()}}


def _log2(a, b):
    if a is None or b is None or a <= 0 or b <= 0:
        return None
    return round(math.log2(a / b), 3)


def legacy_index(paths):
    """(captain, sorted flex) -> E1..E4 rows from DUPE_STACK artifacts (phi 200, the value the board carries)."""
    idx, seen = {}, []
    for p in paths or []:
        d = json.loads(pathlib.Path(p).read_text())
        blk = d['by_phi'].get('200.0') or d['by_phi'][sorted(d['by_phi'])[0]]
        for cid, c in blk['contests'].items():
            for r in c.get('lineups') or []:
                # the board's own numbers at the board's own field-size estimate (N_estimate), kept as printed
                idx[(cid, r['captain'], tuple(sorted(r['flex'])))] = {
                    'board_N_estimate': c.get('N_estimate'),
                    **{f'board_{k}': r.get(k) for k in ('E1_independent_product', 'E2_adjusted_product',
                                                       'E3_archetype_field', 'E4_optimizer_field', 'FLAG')}}
        seen.append({'path': str(p), 'sha256': hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest(),
                     'label': d.get('label'), 'STATUS': d.get('STATUS')})
    return idx, seen


def run(a, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    kickoff = dt.datetime.fromisoformat(a.kickoff.replace('Z', '+00:00')) if a.kickoff else None
    if not a.dry_run:
        if kickoff is None:
            raise ShadowError('KICKOFF_REQUIRED (or --dry-run for a labelled historical replay)')
        if now >= kickoff:
            raise ShadowError(f'SHADOW_AFTER_KICKOFF now {now.isoformat()} kickoff {kickoff.isoformat()}')
    out = pathlib.Path(a.out)
    if out.exists():
        raise ShadowError(f'OUTPUT_EXISTS_WRITE_ONCE {out}')
    meta = DR._pool_meta(pathlib.Path(a.export))
    fc = DR._fc(pathlib.Path(a.fc)) if a.fc else None
    own = list(csv.DictReader(open(a.ownership)))
    if not own:
        raise ShadowError('OWNERSHIP_EMPTY')
    cpt = {r['player']: float(r['shadow_cpt_own_pct']) / 100 for r in own}
    flx = {r['player']: float(r['shadow_flex_own_pct']) / 100 for r in own}
    lineups = list(csv.DictReader(open(a.lineups)))
    if not lineups:
        raise ShadowError('LINEUPS_EMPTY')
    sizes, maxes = {}, {}
    for x in a.contest:
        k, v = x.split('=')
        n, _, mx = v.partition(':')
        sizes[k], maxes[k] = int(n), (int(mx) if mx else None)
    missing = sorted({r['contest_id'] for r in lineups} - set(sizes))
    if missing:
        raise ShadowError(f'CONTEST_SIZE_MISSING {missing}')
    has_salary = all(isinstance(m.get('flex_salary'), (int, float)) and m['flex_salary'] > 0 for m in meta.values())
    models, fitted = list(dict.fromkeys(a.model or DEFAULT_MODELS)), {}
    for m in models:
        names = FEATURES[m]
        if any(n.startswith('fc_') for n in names) and fc is None:
            fitted[m] = {'state': 'NOT_AVAILABLE', 'reason': 'NO_FC_FILE (B4 needs the FC projection gap)'}
            continue
        if any(n.startswith('sal_') for n in names) and not has_salary:
            fitted[m] = {'state': 'NOT_AVAILABLE', 'reason': 'NO_SALARIES_IN_EXPORT'}
            continue
        names, theta, trained_on, tinfo = train(m, set(a.exclude_train or []))
        U = DR.forecast_universe('NEXT_SLATE', cpt, flx, meta, fc, 1)
        lq, minfo = DR.maxent_fit_marginals(U, theta, names)
        fitted[m] = {'state': 'FITTED', 'features': names,
                     'theta': dict(zip(names, [round(float(x), 5) for x in theta])),
                     'trained_on': trained_on, 'train_info': tinfo, 'marginal_fit': minfo,
                     '_U': U, '_q': np.exp(lq)}
    live = [m for m in models if fitted[m]['state'] == 'FITTED']
    if not live:
        raise ShadowError(f'NO_MODEL_AVAILABLE {[(m, fitted[m]["reason"]) for m in models]}')
    leg_idx, leg_src = legacy_index(a.legacy_dupe_stack)
    n_ours = collections.Counter(r['contest_id'] for r in lineups)
    ctype = {cid: contest_type(next((r.get('contest') for r in lineups if r['contest_id'] == cid), None),
                               sizes[cid], n_ours[cid], maxes[cid]) for cid in sizes}
    rows = []
    for r in lineups:
        cid, N = r['contest_id'], sizes[r['contest_id']]
        flex = [r[f'FLEX{i}'] for i in range(1, 6)]
        e1 = N * cpt.get(r['CPT'], 0.0) * math.prod(flx.get(x, 0.0) for x in flex)
        row = {'contest_id': cid, 'entry_id': r.get('entry_id'), 'captain': r['CPT'], 'flex': flex,
               'contest_type': ctype[cid]['class'],
               'legacy': {'E1_independent_copies': round(e1, 3),
                          'structural_duplication_index': r.get('structural_duplication_index')},
               'models': {}}
        lg = leg_idx.get((cid, r['CPT'], tuple(sorted(flex))))
        row['legacy'].update(lg if lg else {'E2_E3_E4': 'NOT_STORED' if leg_src else 'NO_DUPE_STACK_PASSED'})
        for m in models:
            f = fitted[m]
            if f['state'] != 'FITTED':
                row['models'][m] = f['state']
                continue
            loc = DR.locate(f['_U'], r['CPT'], flex)
            row['models'][m] = ({'copies': None, 'state': 'OUTSIDE_UNIVERSE'} if loc is None else
                                {'copies': round(float(N * f['_q'][loc]), 3), 'state': 'PRICED'})
        cop = {m: (row['models'][m] or {}).get('copies') if isinstance(row['models'][m], dict) else None for m in models}
        dis = {f'log2_{m}_over_E1': _log2(cop[m], e1) for m in live}
        if 'B4' in live and 'B3S' in live:
            dis['log2_B4_over_B3S'] = _log2(cop['B4'], cop['B3S'])
        dis['FLAG_GT_2X'] = sorted(k for k, v in dis.items() if isinstance(v, float) and abs(v) > DISAGREE_LOG2)
        row['disagreement'] = dis
        row['construction'] = construction(r['CPT'], flex, meta)
        rows.append(row)

    def tot(cid, m):
        v = [x['models'][m]['copies'] for x in rows if x['contest_id'] == cid and isinstance(x['models'][m], dict)
             and x['models'][m]['copies'] is not None]
        return round(sum(v), 1) if v else None
    summary = {}
    for cid in sizes:
        rs = [x for x in rows if x['contest_id'] == cid]
        summary[cid] = {'contest_type': ctype[cid], 'n': len(rs),
                        'E1_total': round(sum(x['legacy']['E1_independent_copies'] for x in rs), 1),
                        **{f'{m}_total': tot(cid, m) for m in live},
                        'outside_universe': {m: sum(isinstance(x['models'][m], dict) and x['models'][m]['state'] ==
                                                    'OUTSIDE_UNIVERSE' for x in rs) for m in live},
                        'flagged_gt_2x': sum(bool(x['disagreement']['FLAG_GT_2X']) for x in rs),
                        'qb_structure': dict(collections.Counter(x['construction'].get('qb_structure') for x in rs)),
                        'split_class': dict(collections.Counter(x['construction'].get('split_class') for x in rs))}
    body = {'ARTIFACT': 'SHOWDOWN_DUPE_SHADOW_COMPARISON', 'STATUS': 'SHADOW_ONLY -- NOT READ BY SELECTION',
            'AUDIT_LADDER': 'IMPLEMENTED, ON_EXECUTION_PATH (non-blocking, after the portfolio), SUCCESS_TESTED, '
                            'REFUSAL_TESTED; NOT PROSPECTIVELY_VALIDATED, NOT PROMOTED',
            'MODE': 'DRY_RUN_NOT_PRELOCK' if a.dry_run else 'PRELOCK',
            'kickoff': kickoff.isoformat() if kickoff else None, 'written_at': now.isoformat(),
            'prereg': 'docs/NFL_SHOWDOWN_DUPLICATION_PREREGISTRATION.md section 7',
            'models': {m: {k: v for k, v in fitted[m].items() if not k.startswith('_')} for m in models},
            'excluded_from_training': sorted(a.exclude_train or []),
            'inputs': {k: {'path': p, 'sha256': hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()}
                       for k, p in (('export', a.export), ('ownership', a.ownership), ('lineups', a.lineups),
                                    ('fc', a.fc)) if p},
            'legacy_dupe_stack': leg_src, 'contest_sizes': sizes,
            'CONVENTIONS': {'copies': ('expected number of entries in the field holding the identical lineup (N x q, ALL '
                                       'copies under independent entry); for one of our entered lineups the expected '
                                       'OTHER-copies count is (N-1) x q. Unique-lineup units. Score ties are not copies. '
                                       'See nfl/postgame/dupe_research/DUPE_COPY_COUNT_SEMANTICS.json'),
                            'disagreement': f'log2 ratios; |log2| > {DISAGREE_LOG2} (2x) is flagged',
                            'cheap_flex_bands': {b: [lo, hi] for b, lo, hi in CHEAP_BANDS}},
            'summary': summary, 'lineups': rows}
    body['seal_sha256'] = hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(body, indent=1, default=str))
    return out, body


def parser():
    ap = argparse.ArgumentParser()
    ap.add_argument('--export', required=True)
    ap.add_argument('--ownership', required=True)
    ap.add_argument('--lineups', required=True)
    ap.add_argument('--contest', action='append', required=True, help='CONTEST_ID=FIELD_SIZE[:MAX_ENTRIES_PER_USER]')
    ap.add_argument('--fc')
    ap.add_argument('--model', action='append', choices=sorted(FEATURES))
    ap.add_argument('--legacy-dupe-stack', action='append')
    ap.add_argument('--exclude-train', action='append')
    ap.add_argument('--kickoff')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--out', required=True)
    return ap


if __name__ == '__main__':
    p, b = run(parser().parse_args())
    print(p)
    print(json.dumps(b['summary'], indent=1))
