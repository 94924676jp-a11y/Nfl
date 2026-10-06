#!/usr/bin/env python3.12
"""Postgame item 7 -- ownership / field / dupe recalibration, LEAVE-ONE-SLATE-OUT.

    python3.12 nfl/postgame/showdown_field_loso.py

LAYER: POSTGAME_DIAGNOSIS -> SUCCESSOR_CANDIDATE evidence. RESEARCH ONLY; promotes nothing.

SLATES. Two archived Showdown fields with full standings: PIT@CLE (196187080) and PHI@CHI (196036243), parsed by
nfl/field/showdown_history_calibration.py into SHOWDOWN_HISTORY_CALIBRATION.json and UNIQUE_LINEUPS_*.csv. ATL@NO
(196285137 / 160 / 161) has NO full-field standings in this repository -- the zip supplied on 2026-10-06 was the
Sunday classic contest -- so the ATL@NO fold is NOT_AVAILABLE and is reported as such, never filled.
With two slates "leave one out" is fit-on-one, test-on-the-other: two held-out folds, two observations.

WHAT IS TESTED (each a structural piece the shadow field model uses, current vs successor):
  S1 SHAPE PRIOR       lineup-shape marginals (symmetrised team split, QB count, K+DST count, CPT position).
                       CURRENT: derived from our optimizer-exposure field (showdown_archetype_field.targets).
                       SUCCESSOR: the other slate's realised field. Metric: total-variation distance to the held-out
                       field. The current method's prior exists only for ATL@NO, so S1 compares it CROSS-SLATE: a
                       method-level test, labelled so -- not a same-slate test.
  S2 DUPE MAPPING      log(copies) = a + b log(product ownership), fitted on one slate's observed unique lineups,
                       scored on the other's. CURRENT: E1 (N x product, no fit). ORACLE ownership on both sides: this
                       tests the ownership->copies mapping only, never an ownership forecast. Observed lineups only
                       (count >= 1), so both are scored on the same truncated population.
  S3 CPT:FLEX RATIO    CPT% = ratio(position) x FLEX% (FLEX actual -- oracle), ratio fitted on the other slate.
                       CURRENT: our ATL@NO shadow ratios by position (BLEND and FC_ONLY); FALSIFIED reference: 0.5.
                       Metric: MAE in percentage points over players with FLEX >= 5%.

DECISION RULE (fixed here before any fold was scored): a successor "beats" current on a piece only if it has the
lower metric on BOTH held-out folds. Anything else is NOT_DEMONSTRATED. Two folds cannot establish a calibration;
a win is a reason to keep testing on the next slates, never a promotion.
"""
from __future__ import annotations

import collections
import csv
import datetime as dt
import json
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

HIST = _REPO / 'nfl/postgame/showdown_history'
ATL = _REPO / 'nfl/dfs/salaries/showdown_atl_no'
V2 = ATL / 'RW_INACTIVES_CHARTFIX'
OUT = _REPO / 'nfl/postgame/showdown_atl_no_2026W4'
SLATES = ('PIT_CLE', 'PHI_CHI')
FLEX_FLOOR = 5.0


class LosoError(RuntimeError):
    pass


def _tvd(p, q):
    keys = set(p) | set(q)
    return round(0.5 * sum(abs(p.get(k, 0.0) - q.get(k, 0.0)) for k in keys), 4)


def _norm(d):
    s = sum(d.values())
    if s <= 0:
        raise LosoError('EMPTY_DISTRIBUTION')
    return {k: v / s for k, v in d.items()}


def _sym_split(pct):
    out = collections.Counter()
    for k, v in pct.items():
        a, h = (int(x) for x in k.split('-'))
        out[f'{max(a, h)}-{min(a, h)}'] += v
    return _norm(out)


def _cpt_pos(pct):
    out = collections.Counter()
    for k, v in pct.items():
        if k in ('QB', 'RB', 'WR', 'TE'):
            out[k] += v
        elif k in ('K', 'DST'):
            out['KD'] += v
    return _norm(out)


def hist_shapes(cal):
    sh = {}
    for s in SLATES:
        f = cal['contests'][s]['construction']['field']
        sh[s] = {'split': _sym_split(f['team_split_away_home']['pct']),
                 'qb_count': _norm({k: v for k, v in f['qb_count']['pct'].items()}),
                 'cpt_pos': _cpt_pos(f['cpt_position']['pct'])}
        kd = collections.Counter()
        for k, v in f['k_plus_dst_count']['pct'].items():
            kd['2+' if int(k) >= 2 else k] += v
        sh[s]['kd_count'] = _norm(kd)
    return sh


def opt_shapes():
    proj = {r['player'] + '|' + r['team']: r for r in csv.DictReader(open(next(V2.glob('SHOWDOWN_*_PROJECTIONS.csv'))))}
    out = {}
    for src, d in (('FC_ONLY', ATL / 'SHADOW_RW_INACTIVES_CHARTFIX'), ('BLEND', ATL / 'SHADOW_RW_INACTIVES_CHARTFIX_BLEND')):
        L = np.load(d / 'shadow_field_lineups.npy', allow_pickle=True)
        if len(L) == 0:
            raise LosoError(f'OPT_FIELD_EMPTY {d}')
        split, qb, kd, cp = (collections.Counter() for _ in range(4))
        miss = 0
        for row in L:
            seats = list(row)
            if any(k not in proj for k in seats):
                miss += 1
                continue
            pos = [proj[k]['pos'] for k in seats]
            atl = sum(k.endswith('|ATL') for k in seats)
            split[f'{max(atl, 6 - atl)}-{min(atl, 6 - atl)}'] += 1
            qb[str(sum(p == 'QB' for p in pos))] += 1
            n_kd = sum(p in ('K', 'DST') for p in pos)
            kd['2+' if n_kd >= 2 else str(n_kd)] += 1
            c = pos[0]
            cp['KD' if c in ('K', 'DST') else c] += 1
        if miss > 0.01 * len(L):
            raise LosoError(f'OPT_FIELD_UNMAPPED {src} {miss}/{len(L)}')
        out[src] = {'split': _norm(split), 'qb_count': _norm(qb), 'kd_count': _norm(kd), 'cpt_pos': _norm(cp),
                    'n_lineups': int(len(L)), 'unmapped': miss}
    return out


def s1(cal):
    H = hist_shapes(cal)
    O = opt_shapes()
    rows, verdict = [], {}
    for comp in ('split', 'qb_count', 'kd_count', 'cpt_pos'):
        folds = []
        for test in SLATES:
            train = [s for s in SLATES if s != test][0]
            succ = _tvd(H[train][comp], H[test][comp])
            cur = {src: _tvd(O[src][comp], H[test][comp]) for src in O}
            folds.append({'held_out': test, 'successor_other_slate_tvd': succ,
                          **{f'current_opt_field_{k}_tvd': v for k, v in cur.items()}})
        beats = {src: all(f['successor_other_slate_tvd'] < f[f'current_opt_field_{src}_tvd'] for f in folds) for src in O}
        verdict[comp] = {src: 'SUCCESSOR_BEATS_CURRENT_ON_BOTH_FOLDS' if b else 'NOT_DEMONSTRATED' for src, b in beats.items()}
        rows.append({'component': comp, 'folds': folds})
    return {'folds': rows, 'verdict': verdict, 'historical_shapes': H,
            'current_opt_field_shapes_ATL_NO': O,
            'CAVEAT': ('current-method prior exists only for ATL@NO (our optimizer-exposure field); its distance to the PIT@CLE '
                       'and PHI@CHI fields is cross-slate. The successor is also cross-slate (the other archived field). '
                       'Both are judged on the same held-out fields, so the comparison is fair as a METHOD test; neither '
                       'is a same-slate forecast.')}


def _lineups(s):
    p = HIST / f'UNIQUE_LINEUPS_{s}.csv'
    rows = [r for r in csv.DictReader(open(p)) if r['observed'] == '1']
    if not rows:
        raise LosoError(f'UNIQUE_LINEUPS_EMPTY {p}')
    y = np.log(np.array([float(r['actual_copies']) for r in rows]))
    x = np.array([float(r['log_prod_own']) for r in rows])
    e1 = np.array([float(r['E1']) for r in rows])
    return y, x, e1


def _score(y, logpred):
    err = np.abs(logpred - y)
    q = np.quantile(logpred, 0.9)
    top = logpred >= q
    return {'median_abs_log_err': round(float(np.median(err)), 4), 'mean_abs_log_err': round(float(err.mean()), 4),
            'total_pred_over_actual': round(float(np.exp(logpred).sum() / np.exp(y).sum()), 4),
            'top_decile_actual_over_pred': round(float(np.exp(y[top]).sum() / np.exp(logpred[top]).sum()), 4)}


def s2():
    data = {s: _lineups(s) for s in SLATES}
    folds = []
    for test in SLATES:
        train = [s for s in SLATES if s != test][0]
        yt, xt, _ = data[train]
        b, a = np.polyfit(xt, yt, 1)
        y, x, e1 = data[test]
        succ = _score(y, a + b * x)
        cur = _score(y, np.log(np.maximum(e1, 1e-9)))
        folds.append({'held_out': test, 'fit_on': train, 'a': round(float(a), 4), 'b': round(float(b), 4),
                      'n_test_lineups': int(len(y)), 'successor_fitted': succ, 'current_E1': cur})
    beats = {m: all(f['successor_fitted'][m] < f['current_E1'][m] for f in folds)
             for m in ('median_abs_log_err', 'mean_abs_log_err')}
    calib = {m: all(abs(np.log(f['successor_fitted'][m])) < abs(np.log(f['current_E1'][m])) for f in folds)
             for m in ('total_pred_over_actual', 'top_decile_actual_over_pred')}
    return {'folds': folds,
            'verdict': {m: 'SUCCESSOR_BEATS_CURRENT_ON_BOTH_FOLDS' if v else 'NOT_DEMONSTRATED' for m, v in beats.items()},
            'calibration_check_added_after_reading_folds': {
                m: 'SUCCESSOR_CLOSER_TO_1_ON_BOTH_FOLDS' if v else 'SUCCESSOR_NOT_CLOSER' for m, v in calib.items()},
            'OVERALL': ('MIXED -- NOT PROMOTION-GRADE. The declared metric (abs log error) favours the fitted mapping on both '
                        'folds, but it is a regression of log(copies), so exp(prediction) estimates a median, not a mean: it '
                        'under-predicts total copies by ~half and the most-duplicated decile by ~5x on both folds, where E1 is '
                        'within ~1.5x. Our use is expected copies of OUR lineups, which live in that top tail. The '
                        'calibration check was added after the folds were read and is reported, not used to flip the '
                        'declared verdict. Successor candidate for the next slates: the same fit on the count scale '
                        '(Poisson / negative-binomial mean model), declared now, scored on ATL@NO and later standings.'),
            'ORACLE': 'actual ownership on both sides; tests the ownership->copies mapping only',
            'TRUNCATION': 'observed unique lineups only (copies >= 1); unplayed lineups are absent from both fit and test'}


def _ratios(players):
    by = collections.defaultdict(lambda: [0.0, 0.0])
    for p in players:
        pos = 'KD' if p['position'] in ('K', 'DST') else p['position']
        by[pos][0] += p['dk_cpt_pct']
        by[pos][1] += p['dk_flex_pct']
    return {k: (v[0] / v[1] if v[1] > 0 else None) for k, v in by.items()}


def _atl_shadow_ratios():
    proj = {r['player']: r['pos'] for r in csv.DictReader(open(next(V2.glob('SHOWDOWN_*_PROJECTIONS.csv'))))}
    out = {}
    for src, d in (('FC_ONLY', ATL / 'SHADOW_RW_INACTIVES_CHARTFIX'), ('BLEND', ATL / 'SHADOW_RW_INACTIVES_CHARTFIX_BLEND')):
        rows = list(csv.DictReader(open(d / 'SHOWDOWN_ATL_NO_SHADOW_OWNERSHIP.csv')))
        if not rows:
            raise LosoError(f'SHADOW_OWNERSHIP_EMPTY {d}')
        pl = [{'position': proj.get(r['player'], '?'), 'dk_cpt_pct': float(r['shadow_cpt_own_pct']),
               'dk_flex_pct': float(r['shadow_flex_own_pct'])} for r in rows]
        out[src] = _ratios(pl)
    return out


def s3(cal):
    P = {s: [p for p in cal['contests'][s]['ownership']['players']
             if p['position'] in ('QB', 'RB', 'WR', 'TE', 'K', 'DST')] for s in SLATES}
    SH = _atl_shadow_ratios()
    folds = []
    for test in SLATES:
        train = [s for s in SLATES if s != test][0]
        R = _ratios(P[train])
        ev = [p for p in P[test] if p['dk_flex_pct'] >= FLEX_FLOOR]
        pos = lambda p: 'KD' if p['position'] in ('K', 'DST') else p['position']
        mae = lambda ratio: round(float(np.mean([abs((ratio.get(pos(p)) or 0.0) * p['dk_flex_pct'] - p['dk_cpt_pct'])
                                                 for p in ev])), 3)
        folds.append({'held_out': test, 'fit_on': train, 'n_players': len(ev),
                      'successor_other_slate_ratio_mae': mae(R),
                      **{f'current_shadow_{k}_ratio_mae': mae(v) for k, v in SH.items()},
                      'falsified_half_rule_mae': mae(collections.defaultdict(lambda: 0.5)),
                      'ratios_fitted': {k: round(v, 4) for k, v in R.items() if v is not None}})
    beats = {src: all(f['successor_other_slate_ratio_mae'] < f[f'current_shadow_{src}_ratio_mae'] for f in folds) for src in SH}
    return {'folds': folds,
            'current_shadow_ratios_ATL_NO': {k: {p: round(r, 4) for p, r in v.items() if r is not None} for k, v in SH.items()},
            'verdict': {src: 'SUCCESSOR_BEATS_CURRENT_ON_BOTH_FOLDS' if b else 'NOT_DEMONSTRATED' for src, b in beats.items()},
            'ORACLE': 'FLEX ownership is the actual value; tests the CPT:FLEX structure only'}


def run():
    cal = json.loads((HIST / 'SHOWDOWN_HISTORY_CALIBRATION.json').read_text())
    doc = {'ARTIFACT': 'SHOWDOWN_FIELD_LOSO', 'LAYER': 'POSTGAME_DIAGNOSIS', 'STATUS': 'RESEARCH_ONLY_NOT_PROMOTED',
           'slates': {s: {'contest_id': cal['contests'][s]['contest_id'], 'raw_sha256': cal['contests'][s]['raw']['sha256']}
                      for s in SLATES},
           'ATL_NO_FOLD': 'NOT_AVAILABLE -- full-field standings for 196285137/196285160/196285161 not in the repository '
                          '(outbox request M1); the 2026-10-06 zip was the Sunday classic contest',
           'FALSIFIED_ANCHORS_NOT_USED': ['FC-08 (90% >= $49,500)', 'FC-09 (80% exactly $50,000)', 'CPT = 0.5 x FLEX'],
           'DECISION_RULE': 'successor beats current only with the lower metric on BOTH held-out folds; never a promotion',
           'S1_shape_prior': s1(cal), 'S2_dupe_mapping': s2(), 'S3_cpt_flex_ratio': s3(cal),
           'written_at': dt.datetime.now(dt.timezone.utc).isoformat()}
    p = OUT / 'SHOWDOWN_FIELD_LOSO.json'
    p.write_text(json.dumps(doc, indent=1, default=float))
    return p, doc


if __name__ == '__main__':
    p, doc = run()
    print(p)
    for k in ('S1_shape_prior', 'S2_dupe_mapping', 'S3_cpt_flex_ratio'):
        d = doc[k]
        print(k, json.dumps(d['verdict']))
        print(json.dumps(d['folds'], indent=0, default=float)[:2500])
