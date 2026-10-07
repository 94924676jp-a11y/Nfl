#!/usr/bin/env python3.12
"""SC-OWN-ROTATION-2 (nfl/research/ownership/): marginals, leakage, freeze, predictor, grader. SHADOW_ONLY.

    python3.12 nfl/tests/test_sc_own_rotation_2.py

  marginals    on generated predictions: CPT totals 100, FLEX 500, every slot share <= 100, absent players exactly 0
               (also when the universe is padded with pinned-out absent players), the smoothed shares floor every
               active player at 0.05 and keep the totals; a violated total is refused by name
  leakage      build_features takes no entries; features are identical when the slate's realised entries are present,
               shuffled, halved or absent; a snap row from the slate's own week and a depth snapshot at/after kickoff
               change nothing; the predictor never imports the field archive or reads entries
  fit          on a planted model the joint penalised ML recovers the coefficients and converges
  freeze       refuses a changed pre-registration, a changed module, a tampered freeze, an existing freeze, and a
               freeze at or after the first evaluation lock; the committed freeze verifies, is 0444 and predates lock
  predictor    refuses post-kickoff, overwrite, a tampered freeze, a development slate, a freeze that does not predate
               the lock, an unlabelled dry run, an empty input; a sealed prediction verifies and is 0444
  grader       refuses unsealed, tampered, post-kickoff and dry-run predictions and a foreign freeze; NOT_YET_EVALUABLE
               below N = 4; the bar recomputes PASS_SHADOW / FAIL from its own criteria
  empties      every loader and stage refuses empty input with a named code
  isolation    nothing on the execution path imports the candidate
"""
from __future__ import annotations

import ast
import copy
import csv
import datetime as dt
import inspect
import json
import os
import pathlib
import random
import sys
import tempfile
import textwrap

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))
from nfl.research.ownership import sc_own_rotation_2 as M  # noqa: E402
from nfl.research.ownership import predict_sc_own_rotation_2 as PR  # noqa: E402
from nfl.research.ownership import grade_sc_own_rotation_2 as G  # noqa: E402
from nfl.field import showdown_dupe_research as DR  # noqa: E402

PASSED = FAILED = 0
TMP = pathlib.Path(tempfile.mkdtemp(prefix='sc_own_rot2_'))
VEC = [1.2, 0.6, -0.05, -0.2, 1.3, -0.8, 0.8, 0.3, 0.6, -0.05, 1.2, 2.2, -1.3, -0.2, 0.7, -0.8, 0.1, 0.05, 0.3]


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
    except M.RotationError as e:
        if e.code != code:
            print(f'       (raised {e.code}, wanted {code}: {e})')
        return e.code == code
    except Exception as e:  # noqa: BLE001 -- a different exception is a failed refusal, reported
        print(f'       (raised {type(e).__name__}: {e}, wanted {code})')
        return False
    return False


# --------------------------------------------------------------------------------------------- fixtures
POS_PLAN = ('QB', 'QB', 'RB', 'RB', 'RB', 'WR', 'WR', 'WR', 'WR', 'WR', 'WR', 'TE', 'TE', 'TE', 'K', 'DST', 'WR', 'RB')


def synth(absent=(), n_per_team=18, seed=7):
    """A synthetic two-club slate: pool, baseline, projection, depth, snaps CSV. No entries anywhere."""
    rng = random.Random(seed)
    pool, proj, depth = {}, {}, {}
    for t in ('AAA', 'BBB'):
        rows = []
        cnt = {}
        for j, pos in enumerate(POS_PLAN[:n_per_team]):
            name = f'{t} {pos} {j}' if pos != 'DST' else f'{t} Defense'
            sal = int(rng.choice(range(200, 12000, 200))) if pos not in ('K', 'DST') else 4000 + 200 * j
            pool[name] = {'team': t, 'position': pos, 'flex_salary': sal, 'cpt_salary': int(sal * 1.5)}
            proj[name] = round(rng.uniform(0.0, 22.0), 3)
            if pos != 'DST':
                cnt[pos] = cnt.get(pos, 0) + 1
                rows.append(('PK' if pos == 'K' else pos, cnt[pos], name))
        depth[t] = {'dt': '2026-10-01T12:00:00Z', 'rows': rows}
    absent = set(absent)
    act = [n for n in sorted(pool) if n not in absent]
    w = np.array([rng.random() for _ in act])
    cpt = 100.0 * w / w.sum()
    fl = np.minimum(500.0 * w / w.sum(), 90.0)
    fl = fl * 500.0 / fl.sum()
    base = {n: {'team': pool[n]['team'], 'cpt': float(c), 'flex': float(f)} for n, c, f in zip(act, cpt, fl)}
    snaps = TMP / f'snaps_{seed}_{len(absent)}.csv'
    with snaps.open('w', newline='') as fh:
        wr = csv.writer(fh)
        wr.writerow(['season', 'game_type', 'week', 'player', 'position', 'team', 'offense_snaps', 'offense_pct'])
        for n, v in pool.items():
            if v['position'] in ('K', 'DST'):
                continue
            for wk in (1, 2, 3):
                wr.writerow(['2026', 'REG', wk, n, v['position'], v['team'], 30, round(rng.random(), 3)])
    return pool, base, proj, depth, snaps


def synth_features(absent=(), seed=7):
    pool, base, proj, depth, snaps = synth(absent, seed=seed)
    return pool, M.build_features('SYN', pool, base, proj, depth, set(absent), snaps, 4)


def tmp_freeze(path, written_at='2026-10-01T00:00:00+00:00', vec=VEC, prereg_sha=M.PREREG_SHA256, mods=None):
    body = {'ARTIFACT': 'SC_OWN_ROTATION_2_FREEZE', 'prereg': {'sha256': prereg_sha},
            'modules_enforced': mods if mods is not None else M.module_hashes(M.ENFORCED_MODULES),
            'coefficients': M.coef_doc(vec), 'written_at': written_at}
    body['content_sha256'] = M.sha_obj(body)
    p = pathlib.Path(path)
    if p.exists():
        os.chmod(p, 0o644)
        p.unlink()
    M.write_once(p, body)
    return p


ATL = M.FIT_SLATES['ATL_NO']


def atl_predict(out, now=None, dry_run=True, label='TEST_DRY_RUN', slate='ATL_NO', freeze=None, kickoff=None,
                **over):
    args = dict(export=ATL['export'], baseline=ATL['baseline']['csv'], projection=ATL['projection'],
                depth_chart=ATL['depth'], designations=ATL['designations'], snaps=ATL['snaps'],
                inactives=ATL['inactives'])
    args.update(over)
    return PR.predict(slate, 4, kickoff or ATL['kickoff'], args['export'], args['baseline'], args['projection'],
                      args['depth_chart'], args['designations'], args['snaps'], out, inactives=args['inactives'],
                      dry_run=dry_run, label=label, freeze_path=freeze or TMP / 'FREEZE_OK.json', now=now)


def _cand(P, s):
    return P['candidate'][s]


# ------------------------------------------------------------------------------------------------- tests
def test_marginal_constraints():
    for absent, tag in (((), 'full width'), (('AAA WR 5', 'AAA WR 6', 'BBB RB 3', 'BBB TE 13', 'AAA QB 1'), 'padded')):
        pool, feat = synth_features(absent)
        active = {n for n, r in feat['rows'].items() if r['active']}
        P = M.predict(feat, pool, VEC)
        for s in M.SLOTS:
            c = _cand(P, s)
            check(abs(sum(c.values()) - M.MASS[s]) < 1e-6, f'{tag}: {s} totals {M.MASS[s]:.0f} ({sum(c.values()):.6f})')
            check(max(c.values()) <= 100.0 + 1e-9, f'{tag}: every {s} share <= 100 (max {max(c.values()):.3f})')
            check(all(c[n] == 0.0 for n in c if n not in active), f'{tag}: absent players get exactly 0 at {s}')
            sm = P['candidate_smoothed'][s]
            check(abs(sum(sm.values()) - M.MASS[s]) < 1e-6, f'{tag}: smoothed {s} keeps total {M.MASS[s]:.0f}')
            check(all(sm[n] >= M.FLOOR_PCT - 1e-9 for n in active), f'{tag}: smoothed {s} floors every active player')
            check(all(sm[n] == 0.0 for n in sm if n not in active), f'{tag}: smoothed {s} keeps absent at 0')
            bs = P['baseline_smoothed'][s]
            check(abs(sum(bs.values()) - M.MASS[s]) < 1e-6 and all(bs[n] >= M.FLOOR_PCT - 1e-9 for n in active),
                  f'{tag}: baseline smoothed identically at {s}')
        if feat['pads']:
            check(all(n not in active for n in feat['pads']) and len(feat['universe']) == M.K,
                  f'{tag}: universe padded to {M.K} with absent players only {feat["pads"]}')
    # a violated total is refused by name
    bad = {'cpt': {'a': 60.0, 'b': 30.0}, 'flex': {'a': 250.0, 'b': 250.0}}
    check(refuses(lambda: M.assert_marginals(bad, {'a', 'b'}), 'MARGINAL_TOTAL'), 'CPT total != 100 -> MARGINAL_TOTAL')
    bad = {'cpt': {'a': 50.0, 'b': 50.0}, 'flex': {'a': 300.0, 'b': 200.0}}
    check(refuses(lambda: M.assert_marginals(bad, {'a', 'b'}), 'MARGINAL_SLOT_OVER_100'), 'FLEX share > 100 refused')
    bad = {'cpt': {'a': 50.0, 'b': 50.0}, 'flex': {'a': 100.0, 'b': 100.0, 'c': 300.0}}
    check(refuses(lambda: M.assert_marginals(bad, {'a', 'b'}), 'MARGINAL_SLOT_OVER_100'), 'inactive mass refused')
    sm = M.smooth({'a': 99.99, 'b': 0.01, 'c': 0.0, 'x': 0.0}, {'a', 'b', 'c'}, 100.0)
    check(abs(sm['b'] - 0.05) < 1e-12 and abs(sm['c'] - 0.05) < 1e-12 and sm['x'] == 0.0
          and abs(sm['a'] - 99.9) < 1e-9, 'floor mass is taken proportionally from the others (a -> 99.90)')


def test_no_realised_leakage():
    sig = inspect.signature(M.build_features)
    check(not any('entr' in p or 'actual' in p or 'standing' in p for p in sig.parameters),
          f'build_features takes no entries / actuals / standings {list(sig.parameters)}')
    def idents(tree):
        out = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Name):
                out.add(n.id)
            elif isinstance(n, ast.Attribute):
                out.add(n.attr)
            elif isinstance(n, ast.arg):
                out.add(n.arg)
            elif isinstance(n, (ast.Import, ast.ImportFrom)):
                out |= {a.name for a in n.names} | ({n.module} if getattr(n, 'module', None) else set())
        return out
    forbidden = {'entries', 'entry_counts', 'load_contest_entries', 'actual_ownership', 'showdown_field_archive',
                 'load_raw', 'load_standings', 'counts'}
    bf = idents(ast.parse(textwrap.dedent(inspect.getsource(M.build_features))))
    check(not (bf & forbidden), f'build_features code never names entries / actuals / standings {sorted(bf & forbidden)}')
    pt = idents(ast.parse(pathlib.Path(PR.__file__).read_text()))
    check(not (pt & forbidden), f'the predictor code never imports the archive or reads entries {sorted(pt & forbidden)}')
    # real slate: features identical whatever happens to its entries
    pool, _ = M.load_pool(ATL['export'])
    teams = {v['team'] for v in pool.values()}
    base = M.load_baseline(ATL['baseline']['csv'])
    proj = M.load_projection(ATL['projection'])
    ab = M.absent_set(pool, M.load_names(ATL['inactives']), M.load_designations(ATL['designations']))
    depth = M.load_depth(ATL['depth'], teams, ATL['kickoff'])

    def feats():
        return M.sha_obj(M.build_features('ATL_NO', pool, base, proj, depth, ab, ATL['snaps'], 4))
    h0 = feats()
    entries, _ = M.load_contest_entries('ATL_NO', '196285160')
    random.Random(1).shuffle(entries)
    h1 = feats()
    del entries[: len(entries) // 2]
    h2 = feats()
    entries.clear()
    h3 = feats()
    check(h0 == h1 == h2 == h3, 'ATL@NO features identical with entries loaded, shuffled, halved, removed')
    # synthetic: a row from the slate's own week and a post-kickoff depth snapshot change nothing
    pool_s, base_s, proj_s, depth_s, snaps = synth(seed=11)
    f0 = M.sha_obj(M.build_features('SYN', pool_s, base_s, proj_s, depth_s, set(), snaps, 4))
    leak = TMP / 'snaps_leak.csv'
    rows = list(csv.reader(snaps.open()))
    with leak.open('w', newline='') as fh:
        wr = csv.writer(fh)
        wr.writerows(rows)
        for n, v in pool_s.items():
            if v['position'] not in ('K', 'DST'):
                wr.writerow(['2026', 'REG', 4, n, v['position'], v['team'], 70, 0.999])
                wr.writerow(['2026', 'REG', 5, n, v['position'], v['team'], 70, 0.999])
    f1 = M.sha_obj(M.build_features('SYN', pool_s, base_s, proj_s, depth_s, set(), leak, 4))
    check(f0 == f1, 'snap rows from the slate week and later are ignored (weeks strictly before only)')
    dc = TMP / 'depth.csv'
    with dc.open('w', newline='') as fh:
        wr = csv.writer(fh)
        wr.writerow(['dt', 'team', 'player_name', 'pos_abb', 'pos_rank'])
        for t, d in depth_s.items():
            for pos, rk, nm in d['rows']:
                wr.writerow(['2026-10-01T12:00:00Z', t, nm, pos, rk])
                wr.writerow(['2026-10-06T00:15:00Z', t, nm, pos, 99 - rk])      # at kickoff: must be ignored
    d1 = M.load_depth(dc, {'AAA', 'BBB'}, '2026-10-06T00:15:00Z')
    check(all(d1[t]['dt'] == '2026-10-01T12:00:00Z' for t in d1) and
          sorted(d1['AAA']['rows']) == sorted(depth_s['AAA']['rows']),
          'a depth snapshot at kickoff is ignored; the latest strictly-prelock snapshot is used')


def test_fit_recovers_planted_coefficients():
    pool, feat = synth_features(seed=5)
    U = M.make_universe(feat, pool)
    F = DR._F(U, list(M.THETA_FEATURES))
    Dc, Df, off = M.design(feat, 'cpt'), M.design(feat, 'flex'), M.offset(feat)
    true = np.array([0.8, 0.5, -0.05, 0.4, 1.0, 0.3, 0.5, 0.4, 0.5, -0.05, 0.6, 1.5, 0.3, -0.3, 0.6, -0.7, 0.2, 0.1, 0.3])
    _, _, _, _, _, q = M.model_stats(U, Dc, Df, F, true, off)
    rng = np.random.default_rng(3)
    counts = np.bincount(rng.choice(len(q), size=60000, p=q / q.sum()), minlength=len(q)).astype(float)
    n = counts.sum()
    c = {'id': 'syn', 'n_in': n, 't_c': np.bincount(U['cpt'], weights=counts, minlength=M.K) / n,
         't_f': sum(np.bincount(U['flex'][:, k], weights=counts, minlength=M.K) for k in range(5)) / n,
         'e': (counts @ F) / n}
    r = M.fit([{'id': 'syn', 'U': U, 'Dc': Dc, 'Df': Df, 'F': F, 'off': off, 'contests': [c]}])
    err = np.abs(r['w'] - true)
    check(r['converged'] and r['max_abs_grad_per_entry'] <= M.FIT_TOL,
          f"planted fit converges (max_abs_grad_per_entry {r['max_abs_grad_per_entry']:.1e})")
    check(float(err.max()) < 0.35, f'planted coefficients recovered (max abs error {err.max():.3f})')
    m_c, m_f = M.marginals(U, Dc, Df, F, r['w'], off)
    check(abs(m_c.sum() - 1) < 1e-9 and abs(m_f.sum() - 5) < 1e-9, 'fitted marginals conserve slot mass')


def test_freeze_refusals():
    p = tmp_freeze(TMP / 'FREEZE_OK.json')
    d, h = M.load_freeze(p)
    check(h == M.sha_file(p) and oct(p.stat().st_mode & 0o777) == '0o444', 'a fresh freeze loads and is 0444')
    check(refuses(lambda: M.write_once(p, {'x': 1}), 'WRITE_ONCE_EXISTS'), 'the freeze is write-once')
    # tampered
    t = TMP / 'FREEZE_TAMPERED.json'
    doc = json.loads(p.read_text())
    doc['coefficients']['vector'][0] += 0.5
    t.write_text(json.dumps(doc))
    check(refuses(lambda: M.load_freeze(t), 'FREEZE_TAMPERED'), 'an edited coefficient -> FREEZE_TAMPERED')
    # changed module
    mods = M.module_hashes(M.ENFORCED_MODULES)
    mods[M.ENFORCED_MODULES[0]] = '0' * 64
    pm = tmp_freeze(TMP / 'FREEZE_MOD.json', mods=mods)
    check(refuses(lambda: M.load_freeze(pm), 'MODULE_CHANGED_SINCE_FREEZE'), 'a changed module -> MODULE_CHANGED_SINCE_FREEZE')
    # changed prereg
    pp = tmp_freeze(TMP / 'FREEZE_PREREG.json', prereg_sha='f' * 64)
    check(refuses(lambda: M.load_freeze(pp), 'PREREG_CHANGED'), 'a freeze carrying another prereg hash -> PREREG_CHANGED')
    edited = TMP / 'prereg_edited.md'
    edited.write_bytes(M.PREREG.read_bytes() + b'\n')
    check(refuses(lambda: M.check_prereg(edited), 'PREREG_CHANGED'), 'an edited prereg document -> PREREG_CHANGED')
    check(refuses(lambda: M.check_prereg(TMP / 'absent.md'), 'PREREG_ABSENT'), 'a missing prereg -> PREREG_ABSENT')
    # run_fit refuses before doing any work
    lock = M.parse_ts(M.FIRST_EVAL_LOCK)
    check(refuses(lambda: M.run_fit(now=lock, write=False, path=TMP / 'never.json'),
                  'FREEZE_AT_OR_AFTER_FIRST_EVALUATION_LOCK'), 'freeze at the first evaluation lock is refused')
    check(refuses(lambda: M.run_fit(now=lock + dt.timedelta(days=3), write=False, path=TMP / 'never.json'),
                  'FREEZE_AT_OR_AFTER_FIRST_EVALUATION_LOCK'), 'freeze after the first evaluation lock is refused')
    check(refuses(lambda: M.run_fit(now=lock - dt.timedelta(hours=1), write=False, path=p), 'FREEZE_EXISTS'),
          'an existing freeze is never overwritten (FREEZE_EXISTS)')


def test_committed_freeze():
    f = M.FREEZE_PATH
    check(f.is_file(), f'the freeze exists at {M.rel(f)}')
    if not f.is_file():
        return
    d, h = M.load_freeze(f)
    check(oct(f.stat().st_mode & 0o777) == '0o444', 'the freeze is mode 0444')
    check(M.parse_ts(d['written_at']) < M.parse_ts(M.FIRST_EVAL_LOCK), f"written {d['written_at']} before the TB@DAL lock")
    check(d['prereg']['sha256'] == M.PREREG_SHA256 == M.sha_file(M.PREREG), 'freeze, module and document prereg hashes agree')
    check(d['fit']['converged'] and d['fit']['max_abs_grad_per_entry'] <= M.FIT_TOL, 'the frozen fit converged')
    check(d['solver_falsification']['VERDICT'] == 'PASS', 'solver falsification test recorded PASS')
    gs = [v[k]['max_abs_grad'] for part in ('prelock_universe', 'b_family_archival_universe')
          for v in d['solver_falsification'][part].values() for k in ('theta_0', 'theta_fitted_fixed') if k in v]
    check(gs and max(gs) <= M.SOLVER_TOL, f'every recorded solver max_abs_grad <= 1e-6 (max {max(gs) if gs else None})')
    check(len(d['coefficients']['vector']) == M.n_params() and d['LABEL'] == 'SHADOW_ONLY'
          and d['INFLUENCES_SELECTION'] is False, 'coefficients complete; SHADOW_ONLY; does not influence selection')
    check('PHI_CHI' in d['NOT_AVAILABLE'] and set(d['fitting_data']) == {'PIT_CLE', 'ATL_NO'},
          'fitted on PIT@CLE and ATL@NO only; PHI@CHI NOT_AVAILABLE')
    dr = M.HERE / 'SC_OWN_ROTATION_2_DRYRUN_ATL_NO.json'
    check(dr.is_file(), 'the ATL@NO dry run exists')
    if dr.is_file():
        x = json.loads(dr.read_text())
        check(PR.verify_seal(x) and x['MODE'] == 'DRY_RUN' and x['run_label'] == 'DRY_RUN_IN_SAMPLE'
              and x['freeze']['sha256'] == h, 'dry run sealed, labelled DRY_RUN_IN_SAMPLE, made with this freeze')
        check(refuses(lambda: G._load_prediction(dr), 'NOT_A_PRELOCK_RECORD'), 'the dry run is refused as evidence')


def test_predictor_refusals():
    fz = tmp_freeze(TMP / 'FREEZE_OK.json')
    ko = M.parse_ts(ATL['kickoff'])
    check(refuses(lambda: atl_predict(TMP / 'p1.json', now=ko, dry_run=False, slate='TEST_SLATE'),
                  'PREDICTION_AT_OR_AFTER_KICKOFF'), 'at kickoff -> PREDICTION_AT_OR_AFTER_KICKOFF')
    check(refuses(lambda: atl_predict(TMP / 'p1.json', now=ko + dt.timedelta(hours=2), dry_run=False, slate='TEST_SLATE'),
                  'PREDICTION_AT_OR_AFTER_KICKOFF'), 'after kickoff -> PREDICTION_AT_OR_AFTER_KICKOFF')
    check(refuses(lambda: atl_predict(TMP / 'p1.json', now=ko - dt.timedelta(hours=2), dry_run=False),
                  'DEVELOPMENT_SLATE'), 'a development slate is refused unless --dry-run')
    check(refuses(lambda: atl_predict(TMP / 'p1.json', label=None), 'DRY_RUN_NEEDS_LABEL'), 'an unlabelled dry run is refused')
    late = tmp_freeze(TMP / 'FREEZE_LATE.json', written_at='2026-10-06T00:15:00+00:00')
    check(refuses(lambda: atl_predict(TMP / 'p1.json', now=ko - dt.timedelta(hours=2), dry_run=False, slate='TEST_SLATE',
                                      freeze=late), 'FREEZE_NOT_BEFORE_LOCK'), 'a slate locking before the freeze is not covered')
    t = TMP / 'FREEZE_TAMPERED2.json'
    doc = json.loads(fz.read_text())
    doc['coefficients']['vector'][3] = 9.0
    t.write_text(json.dumps(doc))
    check(refuses(lambda: atl_predict(TMP / 'p1.json', freeze=t), 'FREEZE_TAMPERED'), 'a tampered freeze -> FREEZE_TAMPERED')
    empty = TMP / 'empty.csv'
    empty.write_text('')
    check(refuses(lambda: atl_predict(TMP / 'p1.json', projection=empty), 'INPUT_MISSING_OR_EMPTY'),
          'an empty projection -> INPUT_MISSING_OR_EMPTY')
    # one PRELOCK record (synthetic slate id, real ATL@NO inputs) and one dry run, both sealed
    out = TMP / 'pred_prelock_P.json'
    d = atl_predict(out, now=ko - dt.timedelta(hours=3), dry_run=False, slate='TEST_SLATE', label=None)
    check(PR.verify_seal(d) and d['MODE'] == 'PRELOCK' and oct(out.stat().st_mode & 0o777) == '0o444',
          'a prelock prediction is sealed, MODE PRELOCK, 0444')
    for s in M.SLOTS:
        tot = sum(r[f'candidate_{s}_pct'] for r in d['players'])
        check(abs(tot - M.MASS[s]) < 1e-6 and max(r[f'candidate_{s}_pct'] for r in d['players']) <= 100,
              f'real-slate {s} marginals total {M.MASS[s]:.0f}, every share <= 100')
        check(all(r[f'candidate_{s}_pct'] == 0 for r in d['players'] if not r['active']),
              f'real-slate absent players exactly 0 at {s}')
        check(all(r[f'candidate_{s}_pct_smoothed'] >= M.FLOOR_PCT - 1e-9 for r in d['players'] if r['active']),
              f'real-slate smoothed {s} floor holds')
    check(refuses(lambda: atl_predict(out, now=ko - dt.timedelta(hours=3), dry_run=False, slate='TEST_SLATE', label=None),
                  'PREDICTION_EXISTS'), 'an existing prediction is never overwritten')
    dd = atl_predict(TMP / 'pred_dry_P.json', label='TEST_DRY_RUN')
    check(dd['MODE'] == 'DRY_RUN' and 'NOT EVIDENCE' in dd['EVIDENCE_STATUS'], 'a dry run is labelled NOT EVIDENCE')


def test_grader():
    fz = tmp_freeze(TMP / 'FREEZE_OK.json')
    out = TMP / 'pred_prelock.json'
    if not out.exists():
        ko = M.parse_ts(ATL['kickoff'])
        atl_predict(out, now=ko - dt.timedelta(hours=3), dry_run=False, slate='TEST_SLATE', label=None)
    g = G.grade(out, '196285160', 'ATL_NO', freeze_path=fz)
    check(g['EVIDENCE'] and g['filled_entries'] == 47308 and set(g['score']['buckets']) == set(G.BUCKETS),
          'a sealed prelock prediction grades against the archive (47,308 entries, every bucket)')
    check(all(np.isfinite(g['log_score_per_entry_slot'][m][s]) for m in G.MODELS for s in M.SLOTS),
          'smoothed log scores are finite for candidate and baseline')
    doc = json.loads(out.read_text())
    u = TMP / 'unsealed.json'
    u.write_text(json.dumps({k: v for k, v in doc.items() if k != 'seal_sha256'}))
    check(refuses(lambda: G.grade(u, '196285160', 'ATL_NO', freeze_path=fz), 'PREDICTION_UNSEALED'), 'unsealed -> refused')
    tp = copy.deepcopy(doc)
    tp['players'][0]['candidate_flex_pct'] += 1.0
    tpath = TMP / 'tampered.json'
    tpath.write_text(json.dumps(tp))
    check(refuses(lambda: G.grade(tpath, '196285160', 'ATL_NO', freeze_path=fz), 'SEAL_DOES_NOT_VERIFY'),
          'tampered -> SEAL_DOES_NOT_VERIFY')
    late = {k: v for k, v in doc.items() if k != 'seal_sha256'}
    late['written_at'] = late['kickoff']
    late['seal_sha256'] = PR.seal(late)
    lpath = TMP / 'late.json'
    lpath.write_text(json.dumps(late))
    check(refuses(lambda: G.grade(lpath, '196285160', 'ATL_NO', freeze_path=fz), 'SEAL_WRITTEN_AT_OR_AFTER_KICKOFF'),
          'a seal written at kickoff -> refused')
    dry = TMP / 'pred_dry.json'
    if not dry.exists():
        atl_predict(dry, label='TEST_DRY_RUN')
    check(refuses(lambda: G.grade(dry, '196285160', 'ATL_NO', freeze_path=fz), 'NOT_A_PRELOCK_RECORD'),
          'a dry run is refused as evidence')
    other = tmp_freeze(TMP / 'FREEZE_OTHER.json', vec=[v + 0.01 for v in VEC])
    check(refuses(lambda: G.grade(out, '196285160', 'ATL_NO', freeze_path=other), 'FREEZE_MISMATCH'),
          'a prediction made under another freeze -> FREEZE_MISMATCH')
    dev = {k: v for k, v in doc.items() if k != 'seal_sha256'}
    dev['slate'] = 'ATL_NO'
    dev['seal_sha256'] = PR.seal(dev)
    dpath = TMP / 'dev.json'
    dpath.write_text(json.dumps(dev))
    check(refuses(lambda: G.grade(dpath, '196285160', 'ATL_NO', freeze_path=fz), 'DEVELOPMENT_SLATE'),
          'a development slate cannot be an evaluation slate')
    # evaluation: N < 4 is NOT_YET_EVALUABLE; the bar recomputes from its criteria
    gs = []
    for i in range(4):
        x = copy.deepcopy(g)
        x['slate'], x['kickoff'] = f'S{i}', f'2026-10-1{i}T00:15:00+00:00'
        gs.append(x)
    for k in range(4):
        e = G.evaluate(gs[:k] if k else [dict(g, EVIDENCE=False)])
        check(e['VERDICT'] == 'NOT_YET_EVALUABLE' and e['n_evaluation_slates'] == k, f'{k} slate(s) -> NOT_YET_EVALUABLE')
    check(refuses(lambda: G.evaluate([]), 'NO_GRADES'), 'no grades -> NO_GRADES')

    def planted(better):
        out_ = []
        for i, x in enumerate(gs):
            y = copy.deepcopy(x)
            for r in y['rows']:
                for s in M.SLOTS:
                    a = r[f'actual_{s}']
                    r[f'baseline_{s}_pct'] = a + (2.0 if r['active'] else 0.0)
                    r[f'candidate_{s}_pct'] = a + ((0.5 if better else 4.0) if r['active'] else 0.0)
            for s in M.SLOTS:
                y['log_score_per_entry_slot']['candidate'][s] = y['log_score_per_entry_slot']['baseline'][s] + (0.01 if better else -0.01)
            B = y['score']['buckets'][G.CHEAP]
            B['candidate_flex'] = {'mae': 0.5 if better else 4.0, 'bias': 0.5, 'n': B['n']}
            B['baseline_flex'] = {'mae': 2.0, 'bias': 2.0, 'n': B['n']}
            out_.append(y)
        return out_
    ev = G.evaluate(planted(True) + [dict(g, slate='S9', kickoff='2026-12-01T00:00:00+00:00')])
    check(ev['VERDICT'] == 'PASS_SHADOW' and ev['scored_slates'] == ['S0', 'S1', 'S2', 'S3'] and not ev['failed'],
          'a uniformly better candidate passes on the FIRST four slates only')
    check('PROMOTION' in ev and ev['PROMOTION'].startswith('NONE'), 'a pass is not a promotion')
    ev = G.evaluate(planted(False))
    check(ev['VERDICT'] == 'FAIL' and ev['failed'], f"a uniformly worse candidate fails ({len(ev['failed'])} criteria)")
    check(ev['bootstrap_REPORTED_NOT_IN_BAR']['resamples'] == 2000 and ev['bootstrap_REPORTED_NOT_IN_BAR']['seed'] == 20261007,
          'bootstrap is 2,000 resamples over slates, seed 20261007, reported not in the bar')


def test_named_refusals_on_empty_inputs():
    e = TMP / 'e0.csv'
    e.write_text('')
    check(refuses(lambda: M.load_projection(e), 'PROJECTION_MISSING_OR_EMPTY'), 'empty projection file')
    h = TMP / 'proj_hdr.csv'
    h.write_text('player,proj_dk_points\n')
    check(refuses(lambda: M.load_projection(h), 'PROJECTION_EMPTY'), 'projection with a header only')
    b = TMP / 'proj_blank.csv'
    b.write_text('player,proj_dk_points\nA,\nB,\n')
    check(refuses(lambda: M.load_projection(b), 'PROJECTION_ALL_BLANK'), 'projection with every value blank')
    check(refuses(lambda: M.load_depth(e, {'AAA'}, '2026-10-06T00:15:00Z'), 'DEPTH_MISSING_OR_EMPTY'), 'empty depth chart')
    dc = TMP / 'depth_late.csv'
    dc.write_text('dt,team,player_name,pos_abb,pos_rank\n2026-10-07T00:00:00Z,AAA,X,QB,1\n')
    check(refuses(lambda: M.load_depth(dc, {'AAA'}, '2026-10-06T00:15:00Z'), 'DEPTH_NO_PRELOCK_SNAPSHOT'),
          'a depth chart with no prelock snapshot')
    j = TMP / 'empty_list.json'
    j.write_text('[]')
    check(refuses(lambda: M.load_names(j), 'INACTIVES_SCHEMA'), 'an empty inactive list')
    jd = TMP / 'empty_dict.json'
    jd.write_text('{}')
    check(refuses(lambda: M.load_designations(jd), 'DESIGNATIONS_SCHEMA'), 'empty designations')
    pool, base, proj, depth, snaps = synth(seed=3)
    check(refuses(lambda: M.build_features('X', {}, base, proj, depth, set(), snaps, 4), 'EMPTY_POOL'), 'empty pool')
    check(refuses(lambda: M.build_features('X', pool, {}, proj, depth, set(), snaps, 4), 'EMPTY_BASELINE'), 'empty baseline')
    check(refuses(lambda: M.build_features('X', pool, base, {}, depth, set(), snaps, 4), 'EMPTY_PROJECTION'), 'empty projection')
    check(refuses(lambda: M.build_features('X', pool, base, proj, {}, set(), snaps, 4), 'EMPTY_DEPTH'), 'empty depth')
    _, feat = synth_features(seed=3)
    U = M.make_universe(feat, pool)
    check(refuses(lambda: M.entry_counts(U, []), 'NO_ENTRIES'), 'no entries -> NO_ENTRIES')
    stray = [{'cpt': 'nobody', 'flex': ('a', 'b', 'c', 'd', 'e')}]
    check(refuses(lambda: M.entry_counts(U, stray), 'NO_ENTRIES_IN_UNIVERSE'), 'entries all outside the universe')
    check(refuses(lambda: M.fit([]), 'EMPTY_TRAINING'), 'no training blocks -> EMPTY_TRAINING')
    check(refuses(lambda: M.smooth({'a': 1.0}, set(), 100.0), 'SMOOTH_NO_ACTIVE'), 'smoothing with no active player')
    check(refuses(lambda: M.smooth({'a': 0.0}, {'a'}, 100.0), 'SMOOTH_EMPTY_SLOT'), 'smoothing an empty slot')


def test_not_on_execution_path():
    hits = []
    for sub in ('nfl/production', 'nfl/dfs', 'nfl/tools', 'nfl/sim', 'nfl/opt', 'nfl/product'):
        d = _REPO / sub
        if not d.is_dir():
            continue
        for f in d.rglob('*.py'):
            t = f.read_text(encoding='utf-8', errors='replace')
            if 'sc_own_rotation_2' in t or 'research.ownership' in t:
                hits.append(str(f.relative_to(_REPO)))
    check(not hits, f'no execution-path module imports the candidate {hits}')
    tree = ast.parse(pathlib.Path(M.__file__).read_text())
    imported = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    check(not any(m.startswith(('nfl.production', 'nfl.dfs.showdown.portfolio', 'nfl.opt')) for m in imported),
          f'the candidate imports nothing from selection {sorted(imported)}')


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed')


if __name__ == '__main__':
    for t in (test_marginal_constraints, test_no_realised_leakage, test_fit_recovers_planted_coefficients,
              test_freeze_refusals, test_committed_freeze, test_predictor_refusals, test_grader,
              test_named_refusals_on_empty_inputs, test_not_on_execution_path):
        print(t.__name__)
        t()
    print(f'{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
