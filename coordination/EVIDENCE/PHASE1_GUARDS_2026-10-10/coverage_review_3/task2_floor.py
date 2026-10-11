"""Task 2b: 20 held-out floor_guard cases (12 should-report, 8 ordinary), each in its own throwaway repo under
/tmp/claude-0/review3/fg/<case>. Derived from the floor_guard module docstring only."""
import json, os, pathlib, shutil, subprocess, sys, textwrap, traceback
sys.path[:0] = ['/home/user/p0work/pylib', '/home/user/nfl-phase1']
from nfl.tools import floor_guard as FG

ROOT = pathlib.Path('/tmp/claude-0/review3/fg')
ENV = dict(os.environ, GIT_AUTHOR_NAME='r3', GIT_AUTHOR_EMAIL='r3@example.invalid', GIT_COMMITTER_NAME='r3',
           GIT_COMMITTER_EMAIL='r3@example.invalid')
D = textwrap.dedent

TEST_MATH = D('''\
    import math
    from nfl.production import calc


    def test_add():
        assert calc.add(2, 2) == 4
        assert calc.add(-1, 1) == 0


    def test_ratio():
        assert math.isclose(calc.ratio(1, 3), 0.3333333333, abs_tol=1e-9)


    def test_answer():
        result = calc.answer()
        assert result == 42
    ''')
CALC = D('''\
    MAX_ERROR = 0.01
    WORKERS = 4


    def add(a, b):
        return a + b


    def ratio(a, b):
        return a / b


    def answer():
        return 42


    def within(err):
        return err <= MAX_ERROR
    ''')
CHECK_MOD = D('''\
    PASSED = FAILED = 0


    def check(name, cond):
        global PASSED, FAILED
        if cond:
            PASSED += 1
        else:
            FAILED += 1
        print(('PASS ' if cond else 'FAIL ') + name)


    def test_sum():
        check('sum', sum([1, 2]) == 3)
        check('len', len([1, 2]) == 2)
    ''')
LEDGER0 = ('{"id": 1, "test": "test_add", "state": "FAIL"}\n'
           '{"id": 2, "test": "test_ratio", "state": "PASS"}\n')
SUMMARY0 = json.dumps({'suite': 'nfl', 'passed': False, 'n_failed': 2}, indent=1) + '\n'
RESULTS_MD0 = D('''\
    # Suite results

    | test | status |
    |---|---|
    | test_add | PASS |
    | test_ratio | FAIL |
    ''')
README0 = '# Project\n\nA small calculator used to exercise the guard.\n'

BASE = {
    'nfl/__init__.py': '', 'nfl/production/__init__.py': '', 'nfl/tests/__init__.py': '',
    'nfl/production/calc.py': CALC,
    'nfl/tests/test_math.py': TEST_MATH,
    'nfl/tests/test_old.py': 'def test_legacy():\n    assert 1 + 1 == 2\n',
    'nfl/tests/test_checks.py': CHECK_MOD,
    'nfl/tests/test_other.py': 'def test_other():\n    assert "a".upper() == "A"\n',
    'nfl/research/run_ledger.jsonl': LEDGER0,
    'results/summary.json': SUMMARY0,
    'results/RESULTS.md': RESULTS_MD0,
    'pyproject.toml': '[project]\nname = "calc"\nversion = "0.1"\n',
    'README.md': README0,
}


def sub(path, old, new):
    def f(p):
        t = (p / path).read_text()
        assert old in t, (path, old)
        (p / path).write_text(t.replace(old, new, 1))
    return f


def write(path, text):
    def f(p):
        (p / path).parent.mkdir(parents=True, exist_ok=True)
        (p / path).write_text(text)
    return f


def delete(path):
    return lambda p: (p / path).unlink()


def seq(*fs):
    def f(p):
        for g in fs:
            g(p)
    return f


CASES = [
    # ---- should report (12)
    ('F01_assert_removed', True, 'CHECKS_REDUCED: an assert deleted from an existing test',
     sub('nfl/tests/test_math.py', '    assert calc.add(-1, 1) == 0\n', '')),
    ('F02_isclose_tol_loosened', True, 'tolerance keyword abs_tol loosened 1e-9 -> 1e-3',
     sub('nfl/tests/test_math.py', 'abs_tol=1e-9', 'abs_tol=1e-3')),
    ('F03_pytest_skip_decorator', True, 'SKIP_ADDED: @pytest.mark.skip on an existing test',
     seq(sub('nfl/tests/test_math.py', 'import math\n', 'import math\nimport pytest\n'),
         sub('nfl/tests/test_math.py', 'def test_answer():', '@pytest.mark.skip(reason="flaky on CI")\ndef test_answer():'))),
    ('F04_module_threshold_loosened', True, 'THRESHOLD_LOOSENED: MAX_ERROR 0.01 -> 0.05 in production',
     sub('nfl/production/calc.py', 'MAX_ERROR = 0.01', 'MAX_ERROR = 0.05')),
    ('F05_json_passed_flipped', True, 'RESULT flip: "passed": false -> true and n_failed zeroed',
     write('results/summary.json', json.dumps({'suite': 'nfl', 'passed': True, 'n_failed': 0}, indent=1) + '\n')),
    ('F06_test_file_deleted', True, 'TEST_FILE_DELETED: a collected test module removed',
     delete('nfl/tests/test_old.py')),
    ('F07_test_body_emptied', True, 'TEST_BODY_EMPTIED: body replaced by a docstring and pass',
     sub('nfl/tests/test_math.py', '    result = calc.answer()\n    assert result == 42\n',
         '    """Temporarily disabled."""\n    pass\n')),
    ('F08_pyproject_deselect', True, 'pytest configuration: addopts --deselect an existing test',
     sub('pyproject.toml', 'version = "0.1"\n',
         'version = "0.1"\n\n[tool.pytest.ini_options]\naddopts = "--deselect nfl/tests/test_math.py::test_add"\n')),
    ('F09_check_helper_no_failure', True, "the module's check() helper no longer counts a failure",
     sub('nfl/tests/test_checks.py', '    if cond:\n        PASSED += 1\n    else:\n        FAILED += 1\n',
         '    PASSED += 1\n')),
    ('F10_markdown_row_fail_to_pass', True, 'text result row: | test_ratio | FAIL | -> PASS',
     sub('results/RESULTS.md', '| test_ratio | FAIL |', '| test_ratio | PASS |')),
    ('F11_vacuous_self_compare', True, 'CONSTANT_TRUE_CHECK_ADDED: assert result == result',
     sub('nfl/tests/test_math.py', 'assert result == 42', 'assert result == result')),
    ('F12_ledger_line_rewritten', True, 'APPEND_ONLY_LOG_REWRITTEN: an old ledger row FAIL -> PASS',
     sub('nfl/research/run_ledger.jsonl', '"test": "test_add", "state": "FAIL"', '"test": "test_add", "state": "PASS"')),
    # ---- ordinary development (8)
    ('N01_new_test_added', False, 'a new test function appended',
     lambda p: (p / 'nfl/tests/test_math.py').write_text((p / 'nfl/tests/test_math.py').read_text()
                                                          + '\n\ndef test_add_zero():\n    assert calc.add(0, 0) == 0\n')),
    ('N02_refactor_production', False, 'local rename inside a production function, no bar touched',
     sub('nfl/production/calc.py', 'def ratio(a, b):\n    return a / b\n',
         'def ratio(numerator, denominator):\n    return numerator / denominator\n')),
    ('N03_rename_identical_body', False, 'test renamed, body byte-identical (spec: not a removal)',
     sub('nfl/tests/test_math.py', 'def test_add():', 'def test_add_small_integers():')),
    ('N04_tolerance_tightened', False, 'abs_tol tightened 1e-9 -> 1e-12 (spec: stricter is info)',
     sub('nfl/tests/test_math.py', 'abs_tol=1e-9', 'abs_tol=1e-12')),
    ('N05_readme_prose', False, 'README prose edit',
     write('README.md', README0 + '\nRun the tests with `python3.12 -m pytest`.\n')),
    ('N06_ledger_append', False, 'a new line appended to the append-only ledger',
     lambda p: (p / 'nfl/research/run_ledger.jsonl').write_text(
         LEDGER0 + '{"id": 3, "test": "test_answer", "state": "FAIL"}\n')),
    ('N07_worker_count', False, 'WORKERS 4 -> 8 (spec: NON_BAR, not judged)',
     sub('nfl/production/calc.py', 'WORKERS = 4', 'WORKERS = 8')),
    ('N08_test_moved_module', False, 'test_other moved verbatim into test_math.py (spec: a move is not a removal)',
     seq(delete('nfl/tests/test_other.py'),
         lambda p: (p / 'nfl/tests/test_math.py').write_text((p / 'nfl/tests/test_math.py').read_text()
                                                              + '\n\ndef test_other():\n    assert "a".upper() == "A"\n'))),
]


def git(p, *a):
    return subprocess.run(['git', '-C', str(p), *a], check=True, capture_output=True, text=True, env=ENV).stdout


def build(name, change):
    p = ROOT / name
    if p.exists():
        shutil.rmtree(p)
    p.mkdir(parents=True)
    git(p, 'init', '-q', '-b', 'main')
    for rel, text in BASE.items():
        (p / rel).parent.mkdir(parents=True, exist_ok=True)
        (p / rel).write_text(text)
    git(p, 'add', '-A'); git(p, 'commit', '-qm', 'base')
    change(p)
    git(p, 'add', '-A'); git(p, 'commit', '-qm', name)
    return p


out = []
for name, expect, why, change in CASES:
    rec = {'case': name, 'should_report': expect, 'what': why}
    try:
        p = build(name, change)
        rep = FG.run(str(p), 'HEAD~1', 'HEAD')
        rep_f = [f for f in rep['findings'] if f['severity'] in ('high', 'medium')]
        rec['reported'] = bool(rep_f)
        rec['findings'] = [{'rule': f['rule'], 'severity': f['severity'], 'path': f['path'], 'detail': f['detail']}
                           for f in rep['findings']]
        rec['outcome'] = ('TP' if rep_f else 'MISS') if expect else ('FALSE_POSITIVE' if rep_f else 'TN')
    except Exception as e:
        rec['outcome'] = 'CRASH'
        rec['error'] = f'{type(e).__name__}: {e}'
        rec['tb'] = traceback.format_exc()
    out.append(rec)
json.dump(out, open('/tmp/claude-0/review3/task2_floor_results.json', 'w'), indent=1)
for r in out:
    print(f"{r['case']:34s} expect={'REPORT' if r['should_report'] else 'quiet ':6s} -> {r['outcome']:15s}",
          '; '.join(f"{f['rule']}/{f['severity']}" for f in r.get('findings', [])) or r.get('error', ''))
