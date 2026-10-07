#!/usr/bin/env python3.12
"""Readiness item 1 -- the B4 prelock duplication shadow (nfl/field/showdown_dupe_shadow.py). SHADOW_ONLY.

    python3.12 nfl/tests/test_dupe_shadow_diagnostic.py

  construction  QB stack / split / K-DST / cheap-band / salary classification on synthetic lineups
  contest type  max entries from the contest name, from a declaration, and a conflict between them refused
  refusals      after kickoff, no kickoff, write-once, unknown contest size, B4 without FC (never a silent fallback)
  isolation     no selection / portfolio module imports the shadow tool (it cannot change a lineup or exposure)
  dry run       the committed ATL@NO dry run is sealed, carries both models and every per-lineup field, and its B4
                totals equal the earlier B4-only dry run on the same frozen inputs
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import pathlib
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))
from nfl.field import showdown_dupe_shadow as SH  # noqa: E402

PASSED = FAILED = 0
D = _REPO / 'nfl/dfs/salaries/showdown_atl_no'
R = _REPO / 'nfl/dfs/salaries/raw/showdown_atl_no_2026W4'
EXPORT = R / 'DKEntries_ATL_NO_SHOWDOWN_2026W4.fd0c1faa2271ca66.csv'
OWN = D / 'SHADOW_RW_INACTIVES_CHARTFIX_BLEND/SHOWDOWN_ATL_NO_SHADOW_OWNERSHIP.csv'
LINEUPS = D / 'RW_INACTIVES_CHARTFIX/SHOWDOWN_ATL_NO_FINAL_LINEUPS.csv'
DRY = _REPO / 'nfl/postgame/dupe_research/SHADOW_DRYRUN_ATL_NO_B4_B3S_FULL.json'
DRY_B4_ONLY = _REPO / 'nfl/postgame/dupe_research/SHADOW_DRYRUN_ATL_NO_B4.json'


def check(ok, msg):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {msg}')
    else:
        FAILED += 1
        print(f'  FAIL {msg}')


def _meta():
    m = {}
    for name, team, pos, fs in (('QA', 'A', 'QB', 10000), ('WA1', 'A', 'WR', 9000), ('TA', 'A', 'TE', 3000),
                                ('RA', 'A', 'RB', 8000), ('KA', 'A', 'K', 4000), ('DA', 'A', 'DST', 3600),
                                ('QB_', 'B', 'QB', 9600), ('WB1', 'B', 'WR', 8400), ('WB5', 'B', 'WR', 1000),
                                ('TB3', 'B', 'TE', 200), ('RB2', 'B', 'RB', 2400), ('KB', 'B', 'K', 4200)):
        m[name] = {'team': team, 'position': pos, 'flex_salary': fs, 'cpt_salary': int(fs * 1.5)}
    return m


def test_construction():
    m = _meta()
    c = SH.construction('QA', ['WA1', 'TA', 'RB2', 'KB', 'WB5'], m)
    check(c['qb_structure'] == 'CPT_QB_WITH_OWN_PASS_CATCHER' and c['own_pass_catchers_with_cpt'] == 2,
          f"CPT QB + own WR/TE -> stacked ({c['qb_structure']}, {c['own_pass_catchers_with_cpt']})")
    check(c['salary_used'] == 15000 + 9000 + 3000 + 2400 + 4200 + 1000 and c['salary_left'] == 50000 - c['salary_used'],
          f"salary used/left from DK salaries ({c['salary_used']}/{c['salary_left']})")
    check(c['team_split'] == {'A': 3, 'B': 3} and c['split_class'] == '3-3', f"split {c['team_split']}")
    check(c['k_dst']['count'] == 1 and c['k_dst']['kickers'] == 1 and not c['k_dst']['captain_is_k_or_dst'], 'K in flex')
    check(c['cheap_flex']['le_1000']['players'] == ['WB5'] and c['cheap_flex']['1100_2900']['players'] == ['RB2'],
          f"cheap bands {c['cheap_flex']}")
    c = SH.construction('QA', ['RA', 'RB2', 'KB', 'DA', 'WB5'], m)
    check(c['qb_structure'] == 'CPT_QB_NAKED', f"CPT QB with no own pass catcher is naked ({c['qb_structure']})")
    c = SH.construction('WA1', ['QA', 'QB_', 'TB3', 'RB2', 'KA'], m)
    check(c['qb_structure'] == 'CPT_PASS_CATCHER_WITH_OWN_QB' and c['both_qbs'] and c['qb_count'] == 2,
          f"CPT WR + own QB, both QBs ({c['qb_structure']})")
    c = SH.construction('RA', ['QB_', 'WB1', 'RB2', 'KB', 'TB3'], m)
    check(c['qb_structure'] == 'QB_IN_FLEX_NOT_STACKED_WITH_CPT' and c['split_class'] == '5-1',
          f"CPT RB with opposing QB only ({c['qb_structure']}, {c['split_class']})")
    c = SH.construction('DA', ['RA', 'WA1', 'TA', 'KA', 'WB1'], m)
    check(c['qb_structure'] == 'NO_QB' and c['k_dst']['captain_is_k_or_dst'] and c['k_dst']['count'] == 2,
          'CPT DST, no QB, K+DST counted')
    c = SH.construction('QA', ['WA1', 'TA', 'RB2', 'KB', 'NOBODY'], m)
    check(c == {'METADATA_MISSING': ['NOBODY']}, 'a player missing from the pool is reported, not priced at zero')


def test_contest_type():
    t = SH.contest_type('NFL Showdown $100K mini-MAX [150 Entry Max] (ATL @ NO)', 237812, 150)
    check(t['max_entries_per_user'] == 150 and t['class'] == '150-max' and t['max_entries_source'] == 'NAME', str(t))
    t = SH.contest_type('NFL Showdown $10K Quarter Jukebox [Just $0.25!] (ATL @ NO)', 47562, 20)
    check(t['class'] == 'UNKNOWN_MAX_ENTRIES', 'a name that does not state the cap is UNKNOWN, not guessed')
    t = SH.contest_type('NFL Showdown $10K Quarter Jukebox [Just $0.25!] (ATL @ NO)', 47562, 20, 20)
    check(t['class'] == '20-max' and t['max_entries_source'] == 'DECLARED', 'declared cap used')
    try:
        SH.contest_type('X [150 Entry Max]', 1, 1, 20)
        check(False, 'name/declaration conflict refused')
    except SH.ShadowError as e:
        check('CONTEST_MAX_CONFLICT' in str(e), f'name/declaration conflict refused ({e})')


def _args(out, **kw):
    a = argparse.Namespace(export=str(EXPORT), ownership=str(OWN), lineups=str(LINEUPS),
                           contest=['196285137=237812', '196285160=47562', '196285161=59453'], fc=None, model=['B4'],
                           legacy_dupe_stack=None, exclude_train=['ATL_NO'], kickoff='2026-10-04T17:00:00Z',
                           dry_run=False, out=str(out))
    for k, v in kw.items():
        setattr(a, k, v)
    return a


def _refused(a, code, msg, now=None):
    try:
        SH.run(a, now=now)
        check(False, f'{msg}: ran')
    except SH.ShadowError as e:
        check(code in str(e), f'{msg} ({str(e)[:90]})')


def test_refusals():
    with tempfile.TemporaryDirectory() as td:
        out = pathlib.Path(td) / 'S.json'
        before = dt.datetime(2026, 10, 4, 16, 0, tzinfo=dt.timezone.utc)
        _refused(_args(out), 'SHADOW_AFTER_KICKOFF', 'a non-dry-run shadow after kickoff is refused',
                 now=dt.datetime(2026, 10, 4, 17, 0, tzinfo=dt.timezone.utc))
        _refused(_args(out, kickoff=None), 'KICKOFF_REQUIRED', 'no kickoff and not a dry run is refused')
        _refused(_args(out, contest=['196285137=237812']), 'CONTEST_SIZE_MISSING',
                 'a lineup in a contest without a declared size is refused', now=before)
        _refused(_args(out), 'NO_MODEL_AVAILABLE', 'B4 alone without an FC file is refused, not downgraded', now=before)
        check(not out.exists(), 'no output written by any refused run')
        out.write_text('{}')
        _refused(_args(out), 'OUTPUT_EXISTS_WRITE_ONCE', 'an existing output is never overwritten', now=before)
        check(out.read_text() == '{}', 'existing output untouched')


def test_selection_isolation():
    hits = []
    for d in ('nfl/dfs', 'nfl/tools', 'nfl/production'):
        for p in (_REPO / d).rglob('*.py'):
            if 'showdown_dupe_shadow' in p.read_text(errors='ignore'):
                hits.append(str(p.relative_to(_REPO)))
    check(hits == [], f'no selection/portfolio/production module references the shadow tool ({hits})')


def test_dry_run_artifact():
    if not DRY.exists():
        check(False, f'dry-run artifact present ({DRY.relative_to(_REPO)})')
        return
    b = json.loads(DRY.read_text())
    seal = b.pop('seal_sha256')
    check(hashlib.sha256(json.dumps(b, sort_keys=True, default=str).encode()).hexdigest() == seal, 'seal verifies')
    check(b['MODE'] == 'DRY_RUN_NOT_PRELOCK' and b['STATUS'].startswith('SHADOW_ONLY'), 'labelled dry run, shadow only')
    check(all(b['models'][m]['state'] == 'FITTED' and 'ATL_NO_160' not in b['models'][m]['trained_on']
              for m in ('B4', 'B3S')), 'B4 and B3S fitted, ATL@NO excluded from training')
    need = {'legacy', 'models', 'disagreement', 'construction', 'contest_type', 'captain'}
    rows = b['lineups']
    check(len(rows) == 172 and all(need <= set(r) for r in rows), f'172 lineups, every per-lineup field ({len(rows)})')
    cons = {'salary_used', 'salary_left', 'team_split', 'qb_structure', 'k_dst', 'cheap_flex'}
    check(all(cons <= set(r['construction']) for r in rows), 'construction fields on every lineup')
    check({b['summary'][c]['contest_type']['class'] for c in b['summary']} == {'150-max', '20-max', '2-max'},
          'contest types declared for all three contests')
    old = json.loads(DRY_B4_ONLY.read_text())['summary']
    check(all(abs(b['summary'][c]['B4_total'] - old[c]['B4_total']) < 0.05 for c in old),
          f"B4 totals reproduce the B4-only dry run {[(c, b['summary'][c]['B4_total'], old[c]['B4_total']) for c in old]}")
    two = [r for r in rows if r['contest_id'] == '196285161']
    check(all('board_E3_archetype_field' in r['legacy'] for r in two), 'board E2-E4 carried where the board stored them')


if __name__ == '__main__':
    for t in (test_construction, test_contest_type, test_refusals, test_selection_isolation, test_dry_run_artifact):
        print(t.__name__)
        t()
    print(f'{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
