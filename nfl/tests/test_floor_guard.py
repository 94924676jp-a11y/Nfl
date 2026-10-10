"""Floor guard (nfl/tools/floor_guard.py), Phase 1 N1, REPORT-ONLY: seeded defective and legitimate changes.

Each case builds a throwaway git repository from a small fixture tree, commits a base, applies one change,
commits it, and runs the guard twice: as a subprocess (the real exit codes) and in-process (the findings).

  DEFECTIVE cases: each must be reported under its expected rule, and the CLI must exit 1.
  LEGITIMATE cases: none may produce a high or medium finding, and the CLI must exit 0.
  COULD-NOT-RUN cases: a bad ref and a missing merge base must exit 2, never 0.
  LOAD-BEARING (CLAUDE.md rule 4, nfl/tests/bypass.py): with a rule's detector bypassed, its seeded case is
  no longer reported, so the case is testing the detector and not passing vacuously.
  ENFORCEMENT: pinned to REPORT_ONLY until the owner approves a change.

The counts printed at the end are the detection and false-positive rates the Phase 1 evidence report quotes.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import floor_guard as FG          # noqa: E402
from nfl.tests.bypass import guard_bypassed      # noqa: E402

PASSED = FAILED = 0
GUARD = str(_REPO / 'nfl' / 'tools' / 'floor_guard.py')


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(ok)


TEST_MODULE = '''\
PASSED = FAILED = 0


def check(label, ok, detail=''):
    return ok


def test_totals_reconcile():
    total = 10
    parts = [4, 6]
    check('parts sum to total', sum(parts) == total)
    check('no part negative', min(parts) >= 0)
    assert total > 0


def test_cap_is_respected():
    check('salary under cap', 49800 <= 50000)
    check('nine players', 9 == 9)
'''

ENGINE = '''\
ACCOUNTING_TOL = 1e-06
RECONCILE_TOL_SE_MULTIPLE = 3.0
MIN_SIM_OPPORTUNITIES = 30
SALARY_CAP = 50000


def total(xs):
    return sum(xs)
'''

FIXTURE = {
    'nfl/tests/test_engine.py': TEST_MODULE,
    'nfl/tests/test_other.py': 'def test_one():\n    assert 1 + 1 == 2\n',
    'nfl/tests/run_suite.py': 'def main():\n    return 0\n',
    'nfl/tests/DETECTORS.json': json.dumps({'detectors': [{'detector': 'a:b:C'}, {'detector': 'd:e:F'}]}),
    'nfl/sim/engine.py': ENGINE,
    'nfl/tests/certificates/CERT_A.json': json.dumps({'verdict': 'FAIL', 'failing': 2}),
    'nfl/dfs/salaries/DK_X_SEAL.json': json.dumps({'sealed_at': 't0', 'sha': 'abc'}),
    'nfl/integrations/REBUILD_LEDGER.jsonl': '{"n": 1}\n{"n": 2}\n',
    'docs/RESULT.md': '| check | result |\n|---|---|\n| accounting | FAIL (30,790 violations) |\n',
    'coordination/OWNER_DECISIONS.md': '# decisions\n- D1 approved\n',
    'nfl/tools/floor_guard.py': '# placeholder copy of the guard in the fixture tree\n',
    'nfl/research/notes.md': 'notes\n',
}


def _sub(text, old, new):
    assert old in text, (old, text)
    return text.replace(old, new, 1)


def _edit(path, old, new):
    return ('edit', path, old, new)


DEFECTIVE = [
    ('delete a test module', [('delete', 'nfl/tests/test_other.py')], 'TEST_FILE_DELETED'),
    ('remove a test function', [_edit('nfl/tests/test_engine.py',
                                      "def test_cap_is_respected():\n    check('salary under cap', 49800 <= 50000)\n    check('nine players', 9 == 9)\n", '')],
     'TEST_FUNCTION_REMOVED'),
    ('remove a check', [_edit('nfl/tests/test_engine.py', "    check('no part negative', min(parts) >= 0)\n", '')],
     'CHECKS_REDUCED'),
    ('remove an assert', [_edit('nfl/tests/test_engine.py', '    assert total > 0\n', '')], 'CHECKS_REDUCED'),
    ('add pytest.skip', [_edit('nfl/tests/test_engine.py', '    total = 10\n',
                               "    import pytest\n    pytest.skip('flaky')\n    total = 10\n")], 'SKIP_ADDED'),
    ('add a BLOCKED increment', [_edit('nfl/tests/test_engine.py', 'PASSED = FAILED = 0\n',
                                       'PASSED = FAILED = BLOCKED = 0\nBLOCKED += 1\n')], 'SKIP_ADDED'),
    ('early return in a test', [_edit('nfl/tests/test_engine.py', '    total = 10\n', '    return\n    total = 10\n')],
     'TEST_EARLY_RETURN'),
    ('empty a test body', [_edit('nfl/tests/test_engine.py',
                                 "    check('salary under cap', 49800 <= 50000)\n    check('nine players', 9 == 9)\n",
                                 '    pass\n')], 'TEST_BODY_EMPTIED'),
    ('replace a condition with True', [_edit('nfl/tests/test_engine.py', "check('parts sum to total', sum(parts) == total)",
                                             "check('parts sum to total', True)")], 'CONSTANT_TRUE_CHECK_ADDED'),
    ('change a number a test compares against', [_edit('nfl/tests/test_engine.py', '49800 <= 50000', '49800 <= 60000')],
     'TEST_COMPARISON_NUMBER_CHANGED'),
    ('loosen an accounting tolerance', [_edit('nfl/sim/engine.py', 'ACCOUNTING_TOL = 1e-06', 'ACCOUNTING_TOL = 0.5')],
     'THRESHOLD_LOOSENED'),
    ('loosen a reconcile SE multiple', [_edit('nfl/sim/engine.py', 'RECONCILE_TOL_SE_MULTIPLE = 3.0',
                                              'RECONCILE_TOL_SE_MULTIPLE = 6.0')], 'THRESHOLD_LOOSENED'),
    ('lower a minimum', [_edit('nfl/sim/engine.py', 'MIN_SIM_OPPORTUNITIES = 30', 'MIN_SIM_OPPORTUNITIES = 3')],
     'THRESHOLD_LOOSENED'),
    ('edit a regression certificate', [_edit('nfl/tests/certificates/CERT_A.json', '"FAIL"', '"PASS"')],
     'FROZEN_ARTIFACT_MODIFIED'),
    ('edit a sealed run', [_edit('nfl/dfs/salaries/DK_X_SEAL.json', '"abc"', '"def"')], 'FROZEN_ARTIFACT_MODIFIED'),
    ('rewrite an append-only ledger line', [_edit('nfl/integrations/REBUILD_LEDGER.jsonl', '{"n": 1}', '{"n": 9}')],
     'APPEND_ONLY_LOG_REWRITTEN'),
    ('change an existing hash in SHA256SUMS', [('write', 'nfl/dfs/salaries/x/SHA256SUMS', 'aaa  ./a\nccc  ./c\n'),
                                               ('commit',),
                                               _edit('nfl/dfs/salaries/x/SHA256SUMS', 'aaa  ./a', 'zzz  ./a')],
     'APPEND_ONLY_LOG_REWRITTEN'),
    ('remove a detector', [_edit('nfl/tests/DETECTORS.json', '{"detector": "a:b:C"}, ', '')],
     'VERIFICATION_MACHINERY_CHANGED'),
    ('edit the runner', [_edit('nfl/tests/run_suite.py', 'return 0', 'return 0  # always green')],
     'VERIFICATION_MACHINERY_CHANGED'),
    ('rewrite a recorded FAIL as PASS', [_edit('docs/RESULT.md', '| accounting | FAIL (30,790 violations) |',
                                               '| accounting | PASS |')], 'RESULT_STATUS_FLIPPED_TO_PASS'),
    ('silence errors with except-pass', [_edit('nfl/sim/engine.py', 'def total(xs):\n    return sum(xs)\n',
                                               'def total(xs):\n    try:\n        return sum(xs)\n    except Exception:\n        pass\n')],
     'BROAD_EXCEPT_PASS_ADDED'),
    # in a TEST module (medium); in other code a suppression is info since the 2026-10-10 history calibration
    ('add a noqa suppression in a test', [_edit('nfl/tests/test_engine.py', '    total = 10\n',
                                                '    total = 10  # noqa: F841\n')], 'SUPPRESSION_ADDED'),
    ('write an owner decision', [_edit('coordination/OWNER_DECISIONS.md', '- D1 approved\n',
                                       '- D1 approved\n- D2 approved (agent)\n')], 'GOVERNANCE_OR_SAFEGUARD_CHANGED'),
    ('edit the floor guard itself', [_edit('nfl/tools/floor_guard.py', 'placeholder', 'disabled')],
     'GOVERNANCE_OR_SAFEGUARD_CHANGED'),
]

LEGITIMATE = [
    ('add a new test function', [_edit('nfl/tests/test_engine.py', 'def test_cap_is_respected():',
                                       "def test_new():\n    check('new', 1 == 1)\n\n\ndef test_cap_is_respected():")]),
    ('add a check to a test', [_edit('nfl/tests/test_engine.py', '    assert total > 0\n',
                                     "    assert total > 0\n    check('len', len(parts) == 2)\n")]),
    ('refactor engine code', [_edit('nfl/sim/engine.py', 'def total(xs):\n    return sum(xs)\n',
                                    'def total(xs):\n    out = 0\n    for x in xs:\n        out += x\n    return out\n')]),
    ('tighten a tolerance', [_edit('nfl/sim/engine.py', 'ACCOUNTING_TOL = 1e-06', 'ACCOUNTING_TOL = 1e-09')]),
    ('append to a ledger', [_edit('nfl/integrations/REBUILD_LEDGER.jsonl', '{"n": 2}\n', '{"n": 2}\n{"n": 3}\n')]),
    ('insert into a sorted SHA256SUMS', [('write', 'nfl/dfs/salaries/x/SHA256SUMS', 'aaa  ./a\nccc  ./c\n'),
                                         ('commit',),
                                         _edit('nfl/dfs/salaries/x/SHA256SUMS', 'aaa  ./a\n', 'aaa  ./a\nbbb  ./b\n')]),
    ('add a new certificate', [('write', 'nfl/tests/certificates/CERT_B.json', '{"verdict": "PASS"}')]),
    ('add a detector', [_edit('nfl/tests/DETECTORS.json', '{"detector": "d:e:F"}', '{"detector": "d:e:F"}, {"detector": "g:h:I"}')]),
    ('edit research notes', [_edit('nfl/research/notes.md', 'notes', 'notes, revised')]),
    ('record a new failure in a result doc', [_edit('docs/RESULT.md', '| accounting | FAIL (30,790 violations) |',
                                                    '| accounting | FAIL (30,790 violations) |\n| dst | FAIL |')]),
    ('a suppression in non-test code (style, not the bar)', [_edit('nfl/sim/engine.py', '    return sum(xs)\n',
                                                                    '    return sum(xs)  # noqa: E731\n')]),
    ('add an import with the house E402 convention', [_edit('nfl/sim/engine.py', 'SALARY_CAP = 50000\n',
                                                            'SALARY_CAP = 50000\nimport math  # noqa: E402\n')]),
]


def _git(d, *args):
    r = subprocess.run(['git', '-C', str(d), *args], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r.stdout


def _repo():
    d = pathlib.Path(tempfile.mkdtemp(prefix='floor_guard_fx_'))
    _git(d, 'init', '-q', '-b', 'main')
    _git(d, 'config', 'user.email', 'fx@example.invalid')
    _git(d, 'config', 'user.name', 'fixture')
    for rel, text in FIXTURE.items():
        p = d / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    _git(d, 'add', '-A')
    _git(d, 'commit', '-q', '-m', 'base')
    return d


def _apply(d, ops):
    for op in ops:
        if op[0] == 'commit':                      # a setup step: commit what is there so far as the base
            p = d / 'nfl/dfs/salaries/x'
            p.parent.mkdir(parents=True, exist_ok=True)
            _git(d, 'add', '-A')
            _git(d, 'commit', '-q', '-m', 'setup')
            continue
        if op[0] == 'delete':
            (d / op[1]).unlink()
        elif op[0] == 'write':
            (d / op[1]).parent.mkdir(parents=True, exist_ok=True)
            (d / op[1]).write_text(op[2])
        else:
            _, rel, old, new = op
            p = d / rel
            p.write_text(_sub(p.read_text(), old, new))
    _git(d, 'add', '-A')
    _git(d, 'commit', '-q', '-m', 'change')


def _cli(d, *extra):
    r = subprocess.run([sys.executable, GUARD, '--repo', str(d), '--base', 'HEAD~1', '--head', 'HEAD', *extra],
                       capture_output=True, text=True, timeout=120)
    return r.returncode, r.stdout + r.stderr


def _case(ops):
    d = _repo()
    _apply(d, ops)
    rep = FG.run(d, 'HEAD~1', 'HEAD')
    rc, out = _cli(d)
    return d, rep, rc, out


def test_01_every_seeded_defect_is_reported_and_exits_1():
    print('\n1. defective changes')
    hits = 0
    for label, ops, rule in DEFECTIVE:
        _, rep, rc, out = _case(ops)
        rules = {f['rule'] for f in rep['findings'] if f['severity'] in ('high', 'medium')}
        ok = rule in rules and rc == 1
        hits += ok
        check(f'{label} -> {rule}, exit 1', ok, f'rules={sorted(rules)} rc={rc} {out[:200]}')
    print(f'  DETECTION {hits}/{len(DEFECTIVE)}')
    check(f'detection rate {hits}/{len(DEFECTIVE)} is complete', hits == len(DEFECTIVE))


def test_02_legitimate_changes_produce_no_finding_and_exit_0():
    print('\n2. legitimate changes')
    clean = 0
    for label, ops in LEGITIMATE:
        _, rep, rc, out = _case(ops)
        bad = [f for f in rep['findings'] if f['severity'] in ('high', 'medium')]
        ok = not bad and rc == 0
        clean += ok
        check(f'{label} -> no finding, exit 0', ok, f'{[(f["rule"], f["detail"]) for f in bad]} rc={rc}')
    print(f'  FALSE POSITIVES {len(LEGITIMATE) - clean}/{len(LEGITIMATE)}')


def test_03_a_diff_that_cannot_be_read_exits_2_never_0():
    print('\n3. could not run')
    d = _repo()
    rc, out = _cli(d, '--base', 'no-such-ref')
    check('an unknown base ref exits 2', rc == 2 and 'NOT_EXECUTED' in out, f'rc={rc} {out[:200]}')
    r = subprocess.run([sys.executable, GUARD, '--repo', str(d), '--base', 'HEAD~5'], capture_output=True, text=True)
    check('a base older than the history (shallow clone, no merge base) exits 2', r.returncode == 2,
          f'rc={r.returncode} {r.stderr[:200]}')
    nd = pathlib.Path(tempfile.mkdtemp(prefix='floor_guard_nogit_'))
    r = subprocess.run([sys.executable, GUARD, '--repo', str(nd), '--base', 'HEAD'], capture_output=True, text=True)
    check('a directory that is not a repository exits 2', r.returncode == 2, f'rc={r.returncode}')


def test_04_detectors_are_load_bearing():
    print('\n4. bypass: with the detector removed, the seeded case is no longer reported')
    for attr, label, ops, rule in [
        ('_tests_in', 'remove a check', DEFECTIVE[2][1], 'CHECKS_REDUCED'),
        ('_constants', 'loosen an accounting tolerance', DEFECTIVE[10][1], 'THRESHOLD_LOOSENED'),
    ]:
        with guard_bypassed('nfl.tools.floor_guard', attr, replacement=lambda *a, **k: {}):
            _, rep, _, _ = _case(ops)
        rules = {f['rule'] for f in rep['findings']}
        check(f'{attr} bypassed -> "{label}" goes unreported (so the case tests the detector)', rule not in rules,
              str(rules))


def test_05_working_tree_mode_sees_uncommitted_changes():
    print('\n5. --worktree')
    d = _repo()
    p = d / 'nfl/tests/test_engine.py'
    p.write_text(_sub(p.read_text(), "    check('no part negative', min(parts) >= 0)\n", ''))
    rep = FG.run(d, 'HEAD', worktree=True)
    check('an uncommitted removed check is reported', any(f['rule'] == 'CHECKS_REDUCED' for f in rep['findings']),
          str(rep['by_rule']))


def test_06_enforcement_is_pinned_to_report_only():
    print('\n6. enforcement')
    check('ENFORCEMENT is REPORT_ONLY (changing it needs the owner: Phase 1 approval 2026-10-10)',
          FG.ENFORCEMENT == 'REPORT_ONLY', FG.ENFORCEMENT)


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for name, fn in sorted((k, v) for k, v in globals().items() if k.startswith('test_') and callable(v)):
        try:
            fn()
        except AssertionError as e:
            print(f'  {name}: {e}')
    print(f'\nPASSED {PASSED}  FAILED {FAILED}')
