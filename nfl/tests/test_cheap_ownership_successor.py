#!/usr/bin/env python3.12
"""Cheap rotation-player ownership successor (nfl/field/showdown_cheap_ownership_research.py). SHADOW_ONLY.

    python3.12 nfl/tests/test_cheap_ownership_successor.py

  leakage      prelock_features takes no entries; features are identical whether the evaluated contest's entries
               are present, shuffled, swapped for another contest's or absent; snap history drops the slate's week
  buckets      bucket assignment reads only the declared prelock fields (by source inspection and by perturbing
               every other field), and its boundaries follow the pre-registration
  refusals     empty pool / baseline / entries / training set, entries naming a player outside the pool, a fold
               whose training set contains its test slate, a changed pre-registration -> named errors
  fit          on a synthetic slate the fit recovers a planted cheap-bucket multiplier and conserves slot mass
  artifact     CHEAP_OWNERSHIP_LOSO.json is SHADOW_ONLY, carries the pre-registration hash, never evaluates on a
               training slate, PHI_CHI is NOT_AVAILABLE, and every verdict recomputes from its own criteria
  isolation    nothing on the execution path imports the research module
"""
from __future__ import annotations

import ast
import inspect
import json
import pathlib
import random
import re
import sys
import tempfile
import textwrap

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))
from nfl.field import showdown_cheap_ownership_research as M  # noqa: E402

PASSED = FAILED = 0


def check(ok, msg):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {msg}')
    else:
        FAILED += 1
        print(f'  FAIL {msg}')


def refuses(fn, code):
    try:
        fn()
    except M.CheapOwnershipError as e:
        return e.code == code
    return False


def _atl_features():
    pool, _ = M.load_pool(M.ATL['export'])
    teams = {v['team'] for v in pool.values()}
    absent = set(json.loads(M.ATL['absent'].read_text())) & set(pool)
    base = M.load_frozen_baseline(M.ATL['baseline']['FC_ONLY'])
    args = ('ATL_NO', pool, absent, base, M.load_snaps(M.SNAPS, teams, 4), M.load_identity(M.ROSTER, teams),
            M.load_usage(M.USAGE, 4), 4)
    return pool, args


def _feat(rows):
    return [{k: r[k] for k in M.FEATURE_SCHEMA} for r in rows]


def test_no_future_ownership_leakage():
    params = set(inspect.signature(M.prelock_features).parameters)
    check(not any(re.search(r'entr|actual|own|standing|contest', p) for p in params),
          f'prelock_features accepts no entries / actual-ownership argument {sorted(params)}')
    fn = ast.parse(textwrap.dedent(inspect.getsource(M.prelock_features))).body[0]
    body = fn.body[1:] if (fn.body and isinstance(fn.body[0], ast.Expr) and isinstance(fn.body[0].value, ast.Constant)) else fn.body
    toks = set()
    for node in body:
        for n in ast.walk(node):
            if isinstance(n, ast.Name):
                toks.add(n.id)
            elif isinstance(n, ast.Attribute):
                toks.add(n.attr)
            elif isinstance(n, ast.Constant) and isinstance(n.value, str):
                toks.add(n.value)
    bad = sorted(t for t in toks if re.search(r'entries|actual_|standings|load_raw|load_contest_entries', t))
    check(not bad, f'prelock_features code (identifiers and string keys, docstring excluded) never touches entries, standings or actual_* {bad}')
    pool, args = _atl_features()
    rows = M.prelock_features(*args)
    check(len(rows) == len(pool) and all(set(M.FEATURE_SCHEMA) <= set(r) for r in rows),
          f'one schema-complete prelock row per pool player ({len(rows)})')
    check(not any(k.startswith('actual_') for r in rows for k in r), 'prelock rows carry no realised-ownership field')
    from nfl.postgame import showdown_atl_no_field_actual as FA
    ent = FA.load_standings(M.ATL['primary'])['entries']
    other = FA.load_standings('196285161')['entries']
    shuf = list(ent)
    random.Random(7).shuffle(shuf)
    shuf = [{**e, 'cpt': e['flex'][0], 'flex': tuple(sorted([e['cpt'], *e['flex'][1:]]))} for e in shuf]  # scramble slots
    ref = _feat(rows)
    variants = {}
    for lab, E in (('real', ent), ('shuffled_and_slot_scrambled', shuf), ('other_contest', other)):
        act, _ = M.actual_ownership(E, pool)
        variants[lab] = M.attach_actuals(rows, act)
    check(all(_feat(v) == ref for v in variants.values()),
          'features identical with the evaluated contest\'s entries real, shuffled+scrambled, or replaced by another contest')
    check(_feat(M.prelock_features(*args)) == ref, 'features identical when rebuilt with no entries loaded at all')
    check(_feat(rows) == ref and not any(k.startswith('actual_') for r in rows for k in r),
          'attach_actuals copies; the prelock rows are never mutated')
    check(variants['real'][0]['actual_flex'] != variants['other_contest'][0]['actual_flex']
          or variants['real'][1]['actual_flex'] != variants['other_contest'][1]['actual_flex'],
          'the actuals did differ between variants (the identity above is not vacuous)')
    # the raw snap file DOES contain the PIT@CLE game's own week; the loader must drop it
    import csv
    raw_w4 = [r for r in csv.DictReader(open(M.SNAPS)) if r['team'] in ('PIT', 'CLE') and r['week'] == '4']
    sn = M.load_snaps(M.SNAPS, {'PIT', 'CLE'}, 4)
    check(len(raw_w4) > 0 and all(x['week'] < 4 for v in sn.values() for x in v),
          f'snap history drops the evaluated week ({len(raw_w4)} raw week-4 PIT/CLE rows exist, none loaded)')
    pl, tm = M.load_usage(M.USAGE, 4)
    check(all(w < 4 for v in pl.values() for w in v) and all(w < 4 for v in tm.values() for w in v),
          'usage history restricted to weeks < slate week')


def _row(**kw):
    r = {'position': 'WR', 'flex_salary': 2000, 'role_evidence': True}
    r.update(kw)
    return r


def test_bucket_uses_prelock_fields_only():
    src = inspect.getsource(M.assign_bucket)
    keys = set(re.findall(r"row\[['\"](\w+)['\"]\]", src))
    check(keys <= set(M.BUCKET_FIELDS) and 'row.get' not in src and '**row' not in src,
          f'assign_bucket subscripts only {sorted(keys)} of BUCKET_FIELDS {M.BUCKET_FIELDS}')
    check(not any(re.search(r'actual|own|entr|baseline', f) for f in M.BUCKET_FIELDS), 'BUCKET_FIELDS are all prelock')
    rng = np.random.default_rng(3)
    base = _row()
    b0 = M.assign_bucket(base)
    noisy = [M.assign_bucket({**base, 'actual_flex': float(rng.uniform(0, 80)), 'actual_cpt': float(rng.uniform(0, 30)),
                              'baseline_flex': float(rng.uniform(0, 80)), 'snap_share_mean': float(rng.random()),
                              'injury_opp': int(rng.integers(2))}) for _ in range(50)]
    check(all(b == b0 for b in noisy), f'bucket unchanged by realised ownership / baseline / any non-bucket field ({b0})')
    cases = [(_row(flex_salary=1000), 'PUNT_FRINGE'), (_row(flex_salary=1200), M.CHEAP), (_row(flex_salary=3800), M.CHEAP),
             (_row(flex_salary=4000), 'MIDRANGE'), (_row(flex_salary=7800), 'MIDRANGE'), (_row(flex_salary=8000), 'STAR'),
             (_row(flex_salary=3000, role_evidence=False), 'PUNT_FRINGE'), (_row(position='QB', flex_salary=6000, role_evidence=False), 'PUNT_FRINGE'),
             (_row(position='K', flex_salary=4800), 'K_DST'), (_row(position='DST', flex_salary=3600, role_evidence=False), 'K_DST')]
    bad = [(c, w, M.assign_bucket(c)) for c, w in cases if M.assign_bucket(c) != w]
    check(not bad, f'bucket boundaries follow the pre-registration {bad}')
    check(refuses(lambda: M.assign_bucket({'position': 'WR', 'flex_salary': 2000}), 'BUCKET_FIELD_MISSING'),
          'a row missing a bucket field is refused, not defaulted')


def _synthetic(n=30, seed=0, cheap_mult=3.0):
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n):
        bucket = M.BUCKETS[i % len(M.BUCKETS)]
        b_flex, b_cpt = float(rng.uniform(0, 40)), float(rng.uniform(0, 10))
        rows.append({'slate': 'SYN', 'name': f'p{i}', 'absent': False, 'bucket': bucket, 'snap_share_mean': float(rng.random()),
                     'injury_opp': int(rng.integers(2)), 'baseline_flex': b_flex, 'baseline_cpt': b_cpt})
    for s in ('flex', 'cpt'):
        w = np.array([(r[f'baseline_{s}'] + M.KAPPA) * (cheap_mult if r['bucket'] == M.CHEAP else 1.0) for r in rows])
        w = w / w.sum() * M.MASS[s]
        for r, v in zip(rows, w):
            r[f'actual_{s}'] = float(v)
    return rows


def test_refusals():
    pool, args = _atl_features()
    a = list(args)
    check(refuses(lambda: M.prelock_features(a[0], {}, *a[2:]), 'EMPTY_POOL'), 'empty pool refused (EMPTY_POOL)')
    check(refuses(lambda: M.prelock_features(a[0], a[1], a[2], {}, *a[4:]), 'EMPTY_BASELINE'), 'empty baseline refused')
    check(refuses(lambda: M.prelock_features(a[0], a[1], a[2], a[3], {}, *a[5:]), 'EMPTY_SNAPS'), 'empty snap history refused')
    check(refuses(lambda: M.actual_ownership([], pool), 'NO_ENTRIES'), 'empty entries refused (zero is not a result)')
    stranger = [{'cpt': 'Nobody Atall', 'flex': tuple(sorted(list(pool)[:5]))}]
    check(refuses(lambda: M.actual_ownership(stranger, pool), 'ENTRY_PLAYER_NOT_IN_POOL'), 'entry naming a non-pool player refused')
    check(refuses(lambda: M.actual_ownership([{'cpt': 'x', 'flex': ('a',)}], pool), 'ENTRY_SCHEMA'), 'malformed entry refused')
    check(refuses(lambda: M.attach_actuals([], {'x': {}}), 'EMPTY_FEATURES'), 'attach_actuals on no rows refused')
    check(refuses(lambda: M.fit([], 'flex'), 'EMPTY_TRAINING'), 'fit on an empty training set refused')
    rows = M.prelock_features(*args)
    check(refuses(lambda: M.fit(rows, 'flex'), 'TRAINING_WITHOUT_ACTUALS'), 'fit on rows without realised ownership refused')
    zero = [{**r, 'actual_flex': 0.0, 'actual_cpt': 0.0} for r in rows]
    check(refuses(lambda: M.fit(zero, 'flex'), 'TRAINING_TARGET_EMPTY'), 'all-zero training target refused')
    check(refuses(lambda: M.load_snaps(M.SNAPS, {'PIT', 'CLE'}, 1), 'SNAPS_NO_PRIOR_ROWS'), 'no prior-week history refused')
    syn = _synthetic()
    m = {s: M.fit(syn, s) for s in ('cpt', 'flex')}
    check(refuses(lambda: M.run_fold('X', ['SYN'], {'slate': 'SYN', 'contest': 'c', 'baseline': 'b', 'rows': syn,
                                                     'baseline_state': 's', 'role': 'PRIMARY'}, m), 'TRAIN_TEST_OVERLAP'),
          'a fold whose training set contains its test slate is refused')
    old = M.PREREG
    try:
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d) / 'prereg.md'
            p.write_text(old.read_text() + '\nedited after fitting\n')
            M.PREREG = p
            check(refuses(M.check_prereg, 'PREREG_CHANGED_AFTER_WRITE'), 'a pre-registration edited after its hash was recorded is refused')
            p.write_text('')
            check(refuses(M.check_prereg, 'PREREG_ABSENT'), 'an empty pre-registration is refused')
    finally:
        M.PREREG = old
    check(M.check_prereg() == M.PREREG_SHA256_AT_WRITE, 'the committed pre-registration still hashes to the recorded value')


def test_fit_recovers_planted_effect():
    syn = _synthetic(cheap_mult=3.0)
    m = M.fit(syn, 'flex', lam=0.0)
    th = dict(zip(M.FEATURES, m['theta']))
    check(m['converged'] and abs(th['is_cheap_active_rotation'] - np.log(3.0)) < 0.02 and abs(th['log_baseline_plus_kappa'] - 1) < 0.02,
          f"planted cheap multiplier x3 recovered (t_cheap {th['is_cheap_active_rotation']:.4f} vs {np.log(3):.4f})")
    p = M.predict(syn, m, 'flex')
    check(abs(sum(p.values()) - 500.0) < 1e-6 and max(abs(p[r['name']] - r['actual_flex']) for r in syn) < 0.05,
          'prediction conserves FLEX mass (500) and reproduces the planted shares')
    pc = M.predict(syn, M.fit(syn, 'cpt'), 'cpt')
    check(abs(sum(pc.values()) - 100.0) < 1e-6, 'prediction conserves CPT mass (100)')
    null = M.fit(_synthetic(cheap_mult=1.0), 'flex', lam=0.0)
    check(abs(dict(zip(M.FEATURES, null['theta']))['is_cheap_active_rotation']) < 0.02, 'no planted effect -> no fitted effect')


def test_loso_artifact():
    p = M.ARTIFACT
    if not p.exists() or p.stat().st_size == 0:
        check(False, f'artifact present ({p.relative_to(_REPO)})')
        return
    d = json.loads(p.read_text())
    check(d['LABEL'] == 'SHADOW_ONLY' and d['STATUS'].startswith('SHADOW_ONLY') and d['NOT_A_FOOTBALL_INPUT'] is True
          and d['ON_EXECUTION_PATH'] is False and d['PROSPECTIVELY_VALIDATED'] is False, 'labelled SHADOW_ONLY, off path, not validated')
    check(d['prereg_sha256'] == M.PREREG_SHA256_AT_WRITE == M.sha(M.PREREG) and d['prereg_sha256_matches'] is True,
          'artifact carries the pre-registration hash recorded before fitting, and it matches the file')
    tested = 0
    for fid in ('A', 'B'):
        f = d['folds'][fid]
        train = {x.split(':')[0] for x in f['trained_on']}
        for t in f['tests']:
            tested += 1
            check(t['test_slate'] not in train and t['test_slate'] not in t['trained_on'],
                  f"fold {fid}: test {t['test_slate']}:{t['test_contest']}:{t['baseline']} is not a training slate {sorted(train)}")
            crit = t['bar'].get('criteria', {})
            want = 'NOT_TESTABLE' if not crit else ('PASS' if all(crit.values()) else 'FAIL')
            check(t['bar']['verdict'] == want, f"fold {fid} {t['test_contest']} {t['baseline']}: bar verdict recomputes ({want})")
        prim = [t['bar']['verdict'] for t in f['tests'] if t['role'] == 'PRIMARY']
        want = 'NOT_TESTABLE' if 'NOT_TESTABLE' in prim else ('PASS' if all(v == 'PASS' for v in prim) else 'FAIL')
        check(prim and f['fold_verdict'] == want, f'fold {fid} verdict recomputes from its primary tests ({want})')
    check(tested > 0, f'{tested} scored tests present (an empty artifact is an error)')
    check(d['folds']['A']['test_slate'] == 'ATL_NO' and set(t['baseline'] for t in d['folds']['A']['tests']
                                                          if t['role'] == 'PRIMARY') == {'FC_ONLY', 'BLEND'},
          'fold A is scored against both frozen ATL@NO baselines')
    check(d['folds']['C']['test_slate'] == 'PHI_CHI' and d['folds']['C']['fold_verdict'] == 'NOT_AVAILABLE',
          'PHI_CHI reported NOT_AVAILABLE, not as a pass')
    fv = [d['folds'][f]['fold_verdict'] for f in d['testable_folds']]
    want = ('FAIL' if 'FAIL' in fv else 'PASS_EXPLORATORY_SHADOW_ONLY' if len(fv) >= 2 and all(v == 'PASS' for v in fv)
            else 'NOT_TESTABLE')
    check(d['VERDICT'] == want, f"overall verdict recomputes from the testable folds ({want})")
    check(d['baselines']['PIT_CLE']['state'] == 'RECONSTRUCTED_POSTGAME_FROM_PRELOCK_INPUTS'
          and d['reconstruction_method_check_on_atl']['state'] == 'REPRODUCES_FROZEN_FC_ONLY',
          'PIT@CLE baseline labelled reconstructed; the method reproduced the frozen ATL@NO FC_ONLY')
    text = json.dumps(d).lower()
    check(not re.search(r'\b(unbiased|is validated|correct model)\b', text), 'no "unbiased" / "validated" / "correct" claim')


def test_not_on_execution_path():
    hits = []
    for sub in ('nfl/production', 'nfl/dfs', 'nfl/tools', 'nfl/sim', 'nfl/opt', 'nfl/product'):
        for f in (_REPO / sub).rglob('*.py'):
            if 'showdown_cheap_ownership_research' in f.read_text(encoding='utf-8', errors='replace'):
                hits.append(str(f.relative_to(_REPO)))
    check(not hits, f'no execution-path module imports the research module {hits}')


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed')


if __name__ == '__main__':
    for t in (test_no_future_ownership_leakage, test_bucket_uses_prelock_fields_only, test_refusals,
              test_fit_recovers_planted_effect, test_loso_artifact, test_not_on_execution_path):
        print(t.__name__)
        t()
    print(f'{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
