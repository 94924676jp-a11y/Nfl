#!/usr/bin/env python3.12
"""SC-OWN-ROTATION-2 grader: the pre-registered bar, prospective slates only. SHADOW_ONLY.

    python3.12 nfl/research/ownership/grade_sc_own_rotation_2.py grade --prediction PRED.json \
        --contest-id CID --slate TB_DAL [--out GRADE.json]
    python3.12 nfl/research/ownership/grade_sc_own_rotation_2.py evaluate GRADE.json [GRADE.json ...] [--out EVAL.json]

GRADE reads the full-field archive through nfl/field/showdown_field_archive.load() (immutable, sha-checked) and scores
one sealed prediction against it. It REFUSES: an unsealed or tampered prediction (PREDICTION_UNSEALED /
SEAL_DOES_NOT_VERIFY), a dry run (NOT_A_PRELOCK_RECORD; a dry run is graded only with allow_dry_run and is then
labelled NOT_EVIDENCE), a seal written at or after kickoff (SEAL_WRITTEN_AT_OR_AFTER_KICKOFF), a prediction whose
freeze is not the current verified freeze (FREEZE_MISMATCH), and a development slate (DEVELOPMENT_SLATE).

Per slate (prereg section 4): MAE and signed bias of CPT% and FLEX% per bucket (SC-OWN-ROTATION-1 buckets, carried
in the sealed prediction, so they are prelock), total-ownership MAE, and the smoothed log score of the realised
ownership (multinomial per slot, per entry; CPT and FLEX separately), for the candidate and the BLEND baseline. Active
players only (absent players are predicted exactly 0 by both; realised mass on them is reported, not scored).

EVALUATE applies the bar to the FIRST four evaluation slates by kickoff, one primary contest each (the largest
field held). Fewer than four: NOT_YET_EVALUABLE -- never a pass, never a fail. Pooled = all (slate, player) rows of
the bucket pooled across the four slates. Criterion 5 is required for CPT and for FLEX (declared reading of
"smoothed log score" when the unit reports CPT and FLEX separately). Bootstrap over slates (2,000 resamples, seed
20261007) is reported; with N = 4 it is coarse and says so. A PASS_SHADOW is not a promotion.
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import math
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.research.ownership import sc_own_rotation_2 as M  # noqa: E402
from nfl.research.ownership import predict_sc_own_rotation_2 as PR  # noqa: E402
from nfl.field import showdown_cheap_ownership_research as CO  # noqa: E402

need = M.need
RotationError = M.RotationError
N_SLATES = 4
BOOT_N = 2000
BOOT_SEED = 20261007
MARGIN = {'cheap_cpt': 0.5, 'other_flex': 1.0, 'other_cpt': 0.5}    # pp, prereg section 4 bar
BUCKETS = CO.BUCKETS
CHEAP = CO.CHEAP
MODELS = ('candidate', 'baseline')


def _load_prediction(path, allow_dry_run=False, freeze_path=M.FREEZE_PATH):
    p = pathlib.Path(path)
    need(p.is_file() and p.stat().st_size > 0, 'PREDICTION_MISSING_OR_EMPTY', str(p))
    doc = json.loads(p.read_text())
    need(doc.get('ARTIFACT') == 'SC_OWN_ROTATION_2_PREDICTION', 'NOT_A_PREDICTION', str(p))
    need('seal_sha256' in doc, 'PREDICTION_UNSEALED', str(p))
    need(PR.verify_seal(doc), 'SEAL_DOES_NOT_VERIFY', str(p))
    if doc.get('MODE') != 'PRELOCK':
        need(allow_dry_run, 'NOT_A_PRELOCK_RECORD', f"MODE {doc.get('MODE')} (a dry run is never graded as evidence)")
    else:
        need(M.parse_ts(doc['written_at']) < M.parse_ts(doc['kickoff']), 'SEAL_WRITTEN_AT_OR_AFTER_KICKOFF',
             f"{doc['written_at']} vs {doc['kickoff']}")
    fz, fz_sha = M.load_freeze(freeze_path)
    need(doc['freeze']['sha256'] == fz_sha and doc['freeze']['content_sha256'] == fz['content_sha256'],
         'FREEZE_MISMATCH', f"prediction {doc['freeze']['sha256'][:12]} vs freeze {fz_sha[:12]}")
    if doc.get('MODE') == 'PRELOCK':
        need(M.parse_ts(fz['written_at']) < M.parse_ts(doc['kickoff']), 'FREEZE_NOT_BEFORE_LOCK', doc['slate'])
        need(not PR.is_development(doc['slate']), 'DEVELOPMENT_SLATE', doc['slate'])
    rows = doc['players']
    need(rows, 'PREDICTION_NO_PLAYERS', str(p))
    for s in M.SLOTS:
        tot = sum(r[f'candidate_{s}_pct'] for r in rows)
        need(abs(tot - M.MASS[s]) < 1e-6, 'PREDICTION_MASS', f'{s} {tot}')
    return doc


def _err(rows, model, slot):
    e = np.array([r[f'{model}_{slot}_pct'] - r[f'actual_{slot}'] for r in rows])
    return {'mae': float(np.mean(np.abs(e))), 'bias': float(np.mean(e)), 'n': len(e)} if len(e) else None


def log_score(rows, model, slot):
    """Mean log probability per entry-slot of the realised ownership under the smoothed forecast (active players).
    CPT: shares / 100 over one seat; FLEX: shares / 500 over five seats."""
    a = np.array([r[f'actual_{slot}'] for r in rows])
    p = np.array([r[f'{model}_{slot}_pct_smoothed'] for r in rows]) / M.MASS[slot]
    need(np.all(p > 0), 'LOG_SCORE_ZERO_PROBABILITY_ON_ACTIVE', f'{model} {slot}')
    need(a.sum() > 0, 'LOG_SCORE_NO_REALISED_MASS', slot)
    q = a / a.sum()
    return float(np.sum(q * np.log(p)))


def grade(prediction, contest_id, slate, root=None, allow_dry_run=False, freeze_path=M.FREEZE_PATH):
    from nfl.field import showdown_field_archive as FA
    doc = _load_prediction(prediction, allow_dry_run, freeze_path)
    S = FA.load(contest_id, slate, root or FA.RAW)
    pool = {r['name']: r for r in doc['players']}
    actual, n = CO.actual_ownership(S['entries'], pool)
    rows = []
    for r in doc['players']:
        rows.append({**r, 'actual_cpt': actual[r['name']]['cpt'], 'actual_flex': actual[r['name']]['flex']})
    act = [r for r in rows if r['active']]
    need(act, 'NO_ACTIVE_PLAYERS')
    out = {'buckets': {}}
    for b in BUCKETS:
        rs = [r for r in act if r['bucket'] == b]
        out['buckets'][b] = {'n': len(rs), **{f'{m}_{s}': _err(rs, m, s) for m in MODELS for s in M.SLOTS}}
    tot = {m: float(np.mean([abs(r[f'{m}_cpt_pct'] + r[f'{m}_flex_pct'] - r['actual_cpt'] - r['actual_flex'])
                             for r in act])) for m in MODELS}
    ls = {m: {s: log_score(act, m, s) for s in M.SLOTS} for m in MODELS}
    inactive_mass = {s: float(sum(r[f'actual_{s}'] for r in rows if not r['active'])) for s in M.SLOTS}
    mode = doc['MODE']
    return {'ARTIFACT': 'SC_OWN_ROTATION_2_GRADE', 'candidate_id': M.CANDIDATE_ID, 'LABEL': M.LABEL,
            'EVIDENCE': mode == 'PRELOCK',
            'STATUS': ('PROSPECTIVE GRADE (one slate; the bar needs N >= 4)' if mode == 'PRELOCK'
                       else f"NOT_EVIDENCE ({doc.get('run_label')})"),
            'prediction': M.rel(prediction), 'prediction_seal': doc['seal_sha256'], 'prediction_mode': mode,
            'slate': doc['slate'], 'kickoff': doc['kickoff'], 'archive_slate': slate, 'contest_id': str(contest_id),
            'standings_sha256': S['rec']['sha256'], 'filled_entries': n,
            'freeze_sha256': doc['freeze']['sha256'], 'score': out, 'total_ownership_mae': tot,
            'log_score_per_entry_slot': ls, 'realised_pct_on_absent_players_NOT_SCORED': inactive_mass,
            'rows': [{k: r[k] for k in ('name', 'team', 'position', 'flex_salary', 'bucket', 'active',
                                         'candidate_cpt_pct', 'candidate_flex_pct', 'baseline_cpt_pct',
                                         'baseline_flex_pct', 'actual_cpt', 'actual_flex')} for r in rows],
            'graded_at': dt.datetime.now(dt.timezone.utc).isoformat()}


# -------------------------------------------------------------------------------------------- evaluate
def _pooled(grades, bucket, model, slot):
    rs = [r for g in grades for r in g['rows'] if r['active'] and r['bucket'] == bucket]
    if not rs:
        return None
    e = np.array([r[f'{model}_{slot}_pct'] - r[f'actual_{slot}'] for r in rs])
    return {'mae': float(np.mean(np.abs(e))), 'bias': float(np.mean(e)), 'n': len(rs)}


def primary_per_slate(grades):
    by = collections.defaultdict(list)
    for g in grades:
        need(g.get('ARTIFACT') == 'SC_OWN_ROTATION_2_GRADE', 'NOT_A_GRADE')
        if not g.get('EVIDENCE'):
            continue
        by[g['slate']].append(g)
    prim = [max(v, key=lambda g: (g['filled_entries'], g['contest_id'])) for v in by.values()]
    return sorted(prim, key=lambda g: g['kickoff'])


def bar(grades4):
    c = {}
    per = []
    for g in grades4:
        B = g['score']['buckets'][CHEAP]
        per.append({'slate': g['slate'], 'n_cheap': B['n'],
                    'cheap_flex_mae': {m: (B[f'{m}_flex'] or {}).get('mae') for m in MODELS},
                    'log_score': g['log_score_per_entry_slot']})
    wins = sum(1 for x in per if x['cheap_flex_mae']['candidate'] is not None
               and x['cheap_flex_mae']['candidate'] < x['cheap_flex_mae']['baseline'])
    pc = {m: _pooled(grades4, CHEAP, m, 'flex') for m in MODELS}
    pcc = {m: _pooled(grades4, CHEAP, m, 'cpt') for m in MODELS}
    need(pc['candidate'] and pc['baseline'], 'NO_CHEAP_ROWS_IN_EVALUATION')
    c['1_cheap_flex_mae_better_on_3_of_4_and_pooled_improvement_positive'] = (
        wins >= 3 and pc['baseline']['mae'] - pc['candidate']['mae'] > 0)
    c['2_cheap_flex_abs_bias_pooled_not_worse'] = abs(pc['candidate']['bias']) <= abs(pc['baseline']['bias'])
    c['3_cheap_cpt_mae_pooled_within_0.5pp'] = pcc['candidate']['mae'] <= pcc['baseline']['mae'] + MARGIN['cheap_cpt']
    pooled_other = {}
    for b in BUCKETS:
        if b == CHEAP:
            continue
        for s, mk in (('flex', 'other_flex'), ('cpt', 'other_cpt')):
            pm = {m: _pooled(grades4, b, m, s) for m in MODELS}
            if pm['candidate'] is None:
                continue
            pooled_other[f'{b}_{s}'] = pm
            c[f'4_{b}_{s}_mae_pooled_within_{MARGIN[mk]}pp'] = pm['candidate']['mae'] <= pm['baseline']['mae'] + MARGIN[mk]
    for s in M.SLOTS:
        k = sum(1 for g in grades4 if g['log_score_per_entry_slot']['candidate'][s]
                >= g['log_score_per_entry_slot']['baseline'][s])
        c[f'5_log_score_{s}_candidate_ge_baseline_on_3_of_4'] = k >= 3
    return c, per, {'cheap_flex': pc, 'cheap_cpt': pcc, 'other': pooled_other}


def bootstrap(grades4, n=BOOT_N, seed=BOOT_SEED):
    rng = np.random.default_rng(seed)
    k = len(grades4)
    imp, ls = [], {s: [] for s in M.SLOTS}
    for _ in range(n):
        idx = rng.integers(0, k, size=k)
        gs = [grades4[i] for i in idx]
        pc = {m: _pooled(gs, CHEAP, m, 'flex') for m in MODELS}
        if pc['candidate'] is not None:
            imp.append(pc['baseline']['mae'] - pc['candidate']['mae'])
        for s in M.SLOTS:
            ls[s].append(float(np.mean([g['log_score_per_entry_slot']['candidate'][s]
                                        - g['log_score_per_entry_slot']['baseline'][s] for g in gs])))
    q = lambda v: [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] if v else None
    return {'resamples': n, 'seed': seed, 'unit': 'slate (blocked)',
            'cheap_flex_mae_improvement_pp_95': q(imp),
            'log_score_difference_95': {s: q(v) for s, v in ls.items()},
            'NOTE': f'N = {k} slates: the bootstrap distribution has at most {k ** k} distinct resamples and is coarse'}


def evaluate(grades):
    need(grades, 'NO_GRADES')
    prim = primary_per_slate(grades)
    doc = {'ARTIFACT': 'SC_OWN_ROTATION_2_EVALUATION', 'candidate_id': M.CANDIDATE_ID, 'LABEL': M.LABEL,
           'n_evaluation_slates': len(prim), 'slates': [g['slate'] for g in prim],
           'primary_contests': {g['slate']: g['contest_id'] for g in prim}}
    if len(prim) < N_SLATES:
        doc.update({'VERDICT': 'NOT_YET_EVALUABLE',
                    'reason': f'{len(prim)} evaluation slate(s) < N = {N_SLATES}; this is never a pass and never a fail'})
        return doc
    first = prim[:N_SLATES]
    c, per, pooled = bar(first)
    doc.update({'scored_slates': [g['slate'] for g in first], 'criteria': c, 'per_slate': per, 'pooled': pooled,
                'bootstrap_REPORTED_NOT_IN_BAR': bootstrap(first),
                'VERDICT': 'PASS_SHADOW' if all(c.values()) else 'FAIL',
                'failed': sorted(k for k, v in c.items() if not v),
                'PROMOTION': 'NONE. A pass is not a promotion; promotion requires the owner (proposed >= 8 slates).'})
    return doc


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=('grade', 'evaluate'))
    ap.add_argument('grades', nargs='*')
    ap.add_argument('--prediction')
    ap.add_argument('--contest-id')
    ap.add_argument('--slate')
    ap.add_argument('--out')
    a = ap.parse_args(argv)
    try:
        if a.cmd == 'grade':
            need(a.prediction and a.contest_id and a.slate, 'GRADE_NEEDS', '--prediction --contest-id --slate')
            d = grade(a.prediction, a.contest_id, a.slate)
        else:
            gs = []
            for p in a.grades:
                gs.append(json.loads(pathlib.Path(p).read_text()))
            d = evaluate(gs)
        if a.out:
            M.write_once(a.out, d)
        print(json.dumps({k: d[k] for k in d if k not in ('rows', 'score')}, default=str)[:3000])
    except RotationError as e:
        print(f'REFUSED[{e.code}] {e}')
        return 3
    return 0


if __name__ == '__main__':
    sys.exit(main())
