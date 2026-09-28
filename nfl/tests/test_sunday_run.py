#!/usr/bin/env python3.12
"""The one command must refuse when it should, and must not pass with a failed step.

The orchestrator's whole value is that it says no. So the checks here break each clause of the
output contract in turn and require the run to notice -- including the clause it got wrong first
time, which was its own: it returned PASS while one of its steps had FAILED.
"""
from __future__ import annotations

import csv
import json
import pathlib
import shutil
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production import readiness, sunday  # noqa: E402
from nfl.tools import xlsx_writer  # noqa: E402
from sportsplatform.governance.outcome import State  # noqa: E402

RESULTS = []


def check(name):
    def deco(fn):
        RESULTS.append((name, fn))
        return fn
    return deco


@check('the run delivers, and every step passes')
def t_run():
    o = sunday.run()
    assert o.state is State.PASS, o
    v = o.value
    assert v['RESULT'] == 'DELIVERED', v['RESULT']
    assert all(s['state'] == 'PASS' for s in v['steps']), v['steps']
    return (f"{len(v['steps'])} steps all passing, mode {v['product_mode']}, "
            f"{v['output_contract']['n_csv_rows']} CSV rows, "
            f"{v['supplement']['n_sheets']} supplement sheets")


@check('every rosterable player appears in the CSV exactly once')
def t_exactly_once():
    o = sunday.verify_contract()
    assert o.state is State.PASS, o
    v = o.value
    assert v['n_csv_rows'] == v['n_universe'], (v['n_csv_rows'], v['n_universe'])
    assert not v['extra_in_csv_not_in_universe']
    return f"{v['n_csv_rows']} rows against a universe of {v['n_universe']}, no extras"


@check('LOAD-BEARING: a duplicated or missing player breaks the contract')
def t_contract_can_fail():
    real = sunday.CSV_MAIN
    tmp = pathlib.Path(tempfile.mkdtemp()) / 'csv.csv'
    with real.open(newline='') as fh:
        rows = list(csv.DictReader(fh))
        cols = list(rows[0].keys())
    # duplicate one player
    with tmp.open('w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow(r)
        w.writerow(rows[0])
    try:
        sunday.CSV_MAIN = tmp
        o = sunday.verify_contract()
        assert o.state is State.FAIL and o.code == 'CONTRACT_NOT_MET', (
            f'got {o.state}/{o.code}: a duplicated player passed the exactly-once clause')
        clauses = {p['clause'] for p in o.evidence['problems']}
        assert 'EXACTLY_ONCE' in clauses, clauses
    finally:
        sunday.CSV_MAIN = real
    # drop one player
    with tmp.open('w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in rows[1:]:
            w.writerow(r)
    try:
        sunday.CSV_MAIN = tmp
        o2 = sunday.verify_contract()
        assert o2.state is State.FAIL, o2
        clauses = {p['clause'] for p in o2.evidence['problems']}
        assert 'NO_SILENTLY_MISSING_PLAYER' in clauses, clauses
    finally:
        sunday.CSV_MAIN = real
        shutil.rmtree(tmp.parent, ignore_errors=True)
    return 'a duplicated player and a dropped player each break a named clause'


@check('LOAD-BEARING: the run REFUSES when the board is not production ready')
def t_refuses():
    import copy
    saved = copy.deepcopy(readiness.STAGES)
    try:
        readiness.STAGES.append({'name': 'model.invented',
                                 'path': 'nfl/sim/DOES_NOT_EXIST.json',
                                 'max_age_hours': 999, 'tier': 'MODEL', 'depends_on': [],
                                 'why': 'a model stage pointing at nothing'})
        o = sunday.run()
        assert o.state is State.BLOCKED, (
            f'got {o.state}/{o.code}: the run produced a deliverable while the model layer was '
            f'incomplete')
        assert o.code == 'SUNDAY_RUN_REFUSED_NOT_PRODUCTION_READY', o.code
        rep = json.loads(sunday.REPORT.read_text())
        assert rep['RESULT'] == 'REFUSED', rep['RESULT']
    finally:
        readiness.STAGES[:] = saved
        sunday.run()
    return 'a missing model artifact makes the run refuse, and the report says REFUSED'


@check('LOAD-BEARING: a failed step cannot be reported as a delivered run')
def t_no_silent_pass():
    real = sunday.supplement

    def broken():
        from sportsplatform.governance.outcome import Outcome
        return Outcome.fail('SUPPLEMENT_DELIBERATELY_BROKEN', 'for the test')
    try:
        sunday.supplement = broken
        o = sunday.run()
        assert o.state is State.FAIL and o.code == 'SUNDAY_RUN_STEP_FAILED', (
            f'got {o.state}/{o.code}: a failed step was reported as a delivered run, which is '
            f'the defect this module exists to prevent, in this module')
    finally:
        sunday.supplement = real
        sunday.run()
    return 'a failing step makes the whole run fail rather than pass with a note'


@check('verify checks sheet NAMES when given names, not a count')
def t_verify_names():
    p = pathlib.Path(tempfile.mkdtemp()) / 'w.xlsx'
    try:
        xlsx_writer.write(p, [('Alpha', [['a']]), ('Beta', [['b']])])
        good = xlsx_writer.verify(p, expected_sheets=['Alpha', 'Beta'])
        assert good['ok'], good
        assert good['sheet_names'] == ['Alpha', 'Beta'], good
        bad = xlsx_writer.verify(p, expected_sheets=['Alpha', 'Gamma'])
        assert not bad['ok'], (
            'a sheet that is not in the workbook was accepted; expected_sheets used to compare a '
            'COUNT against whatever it was handed, so names always failed for the wrong reason')
        assert 'Gamma' in str(bad.get('reason')), bad
        assert xlsx_writer.verify(p, expected_sheets=2)['ok']
        assert not xlsx_writer.verify(p, expected_sheets=3)['ok']
    finally:
        shutil.rmtree(p.parent, ignore_errors=True)
    return 'names are checked as names, and an integer still checks the count'


@check('the run submits nothing and recommends nothing')
def t_governance():
    rep = json.loads(sunday.REPORT.read_text())
    g = rep['GOVERNANCE']
    assert g['submitted'] == 'NOTHING'
    assert g['contest_entered'] == 'NONE'
    assert g['wager_recommended'] == 'NONE'
    assert g['external_projection_as_input'] == 'NONE'
    src = (_REPO / 'nfl/production/sunday.py').read_text()
    for bad in ('upload(', 'submit(', 'requests.', 'urlopen', 'fantasycruncher'):
        assert bad not in src, f'{bad} appears in the orchestrator'
    return 'nothing submitted, nothing entered, no wager, no network call in the module'


def main() -> int:
    ok = fail = 0
    for name, fn in RESULTS:
        try:
            detail = fn()
        except AssertionError as e:
            print(f'FAIL  {name}\n        {e}')
            fail += 1
        except Exception as e:  # noqa: BLE001
            print(f'ERROR {name}\n        {type(e).__name__}: {e}')
            fail += 1
        else:
            print(f'pass  {name}\n        {detail}')
            ok += 1
    print(f'\n{ok} passed, {fail} failed, {len(RESULTS)} checks')
    return 1 if fail else 0


if __name__ == '__main__':
    raise SystemExit(main())
