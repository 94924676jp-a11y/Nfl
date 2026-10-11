#!/usr/bin/env python3.12
"""Floor guard: does a change make the bar easier to pass? REPORT-ONLY (owner Phase 1 approval, 2026-10-10).

    python3.12 nfl/tools/floor_guard.py --base REF [--head REF | --worktree] [--repo DIR] [--json OUT]

WHY. CLAUDE.md rule 1: "The goal is not to make the checklist green. The goal is to make a false green state
difficult to produce." The runner proves a guard fires (`bypass.py`) and that a test module counted its checks,
but nothing compared a CHANGE for the cheap road to green: a deleted test, a removed check, a skip, a loosened
tolerance, an edited certificate, a FAIL rewritten as PASS. This reads the change from the merge base of
base and head (what the branch did, not what base gained meanwhile) and reports each such move with the file,
the line and the evidence. Pattern adapted from addyosmani/agent-skills@1be8e34
(skills/constraint-driven-development/references/floor-guard.md, MIT), reimplemented for Python and this
repository's own conventions (check()/observe()/BLOCKED counters, certificates, ledgers, protected paths).

WHAT IS COMPARED (floor-guard-2, after the independent coverage review of 2026-10-10). Python is read with
`ast`, never by line text:
  tests        collected the way nfl/tests/run_suite.py collects them (its own glob); a test function removed,
               shadowed (`test_x = ...`, `del test_x`), emptied or given an early return; checks counted as
               assert / check() / observe() / unittest asserts / `if cond: raise`; the module's own check()
               helper (does it still count a failure?); every comparison's operators and constant-folded numbers;
               tolerance keywords (rel_tol, abs_tol, atol, rtol, places, delta, ...); vacuous conditions
               (constants, `x == x`, `or True`, `len(x) >= 0`, a name bound to True); skips of every spelling.
               A test moved to another module or renamed with an identical body is not a removal.
  thresholds   module, class, tuple, dict and augmented assignments, argument defaults, call-site keywords and
               use-site expressions (`err > 1000 * TOL`), all constant-folded; JSON config numbers; a threshold
               overridden from a test module (`engine.TOL = 0.5`, setattr, patch.object). Worker, thread, batch,
               timeout and similar names are not bars and are not judged (NON_BAR).
  results      JSON results by field (a false `passed` turned true, a failure count zeroed, a FAIL status turned
               PASS, a failure entry deleted); text results by row (case-insensitive words, emoji, NOT VERIFIED is a
               failure word), including a failure row deleted, and a renamed document compared to its old self.
  protected    owner-authority and approval files and the safeguards (one list shared with coordination/git_guard),
               frozen artifacts and append-only logs (case-insensitive names), the verification machinery
               (runner, detectors row by row, conftest.py, pytest configuration).

REPORT-ONLY. Nothing calls this as a gate. `ENFORCEMENT` below is a code constant, not configuration, so turning
it into a gate is a reviewed code change that needs the owner's approval; a test pins it to REPORT_ONLY.

EXIT CODES. 0 no finding; 1 at least one finding of severity high or medium; 2 COULD NOT RUN (bad ref, no merge
base, git failure, an internal error). A 2 is never a 0 or a 1: an unreadable diff is not a clean diff, and a
crash is not a finding.

AUTHORIZATION. A finding is not a verdict that the change is wrong: an owner-approved tolerance change or a
corrected certificate is legitimate. But the guard records no authorization on its own: absent an owner record
the finding stands (`authorization: NONE_RECORDED`), and no file an agent writes can clear it.
"""
from __future__ import annotations

import argparse
import ast
import collections
import difflib
import fnmatch
import json
import math
import pathlib
import re
import subprocess
import sys
import warnings

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

SPEC_VERSION = 'floor-guard-2'
ENFORCEMENT = 'REPORT_ONLY'          # owner approval required to change; pinned by nfl/tests/test_floor_guard.py

#: what nfl/tests/run_suite.py actually runs (its glob, run_suite.py:290): top-level nfl/tests/test_*.py and
#: sportsplatform/**/test_*.py. A module outside this set is never executed by the authoritative runner.
COLLECTED = (re.compile(r'^nfl/tests/test_[^/]*\.py$'), re.compile(r'^sportsplatform/(.*/)?test_[^/]*\.py$'))
#: test-shaped modules (analysed as tests even when the runner does not collect them)
TEST_FILE = ('nfl/tests/test_*.py', 'nfl/tests/*/test_*.py', 'sportsplatform/*test_*.py', 'v7/test_*.py',
             'v8/*/test_*.py', '*/conftest.py', 'conftest.py')
#: the machinery that decides what counts as proof (an addition counts too: a new conftest.py can stop collection)
VERIFICATION_MACHINERY = ('nfl/tests/run_suite.py', 'nfl/tests/_controls.py', 'nfl/tests/_registry.py',
                          'nfl/tests/bypass.py', 'nfl/tests/certify_suite.py', 'nfl/tests/DETECTORS.json',
                          'nfl/tests/DETECTOR_VALIDATION.json', 'conftest.py', '*/conftest.py', 'pytest.ini',
                          '*/pytest.ini', 'nfl/tests/__init__.py')
#: configuration files that can carry test-collection settings: judged only when a changed line mentions them
TEST_CONFIG = ('pyproject.toml', 'setup.cfg', 'tox.ini', '*/pyproject.toml', '*/setup.cfg')
TEST_CONFIG_WORDS = re.compile(r'pytest|testpaths|addopts|collect_ignore|python_files|norecursedirs|--deselect|'
                               r'-p\s*no:', re.I)
try:
    from coordination.git_guard import APPROVAL_NAME, OWNER_AUTHORITY, SAFEGUARDS
    _SHARED_LIST = 'coordination/git_guard.py'
except Exception as _e:  # noqa: BLE001 -- never silently: run() refuses (exit 2) when the shared list is missing
    APPROVAL_NAME, OWNER_AUTHORITY, SAFEGUARDS, _SHARED_LIST = None, (), (), f'UNAVAILABLE: {_e}'
#: owner-authority files and the safeguards themselves (git_guard's lists, plus the briefing and every settings file)
GOVERNANCE = tuple(OWNER_AUTHORITY) + tuple(SAFEGUARDS) + ('.claude/settings*.json', 'CLAUDE.md')
#: artifacts that are written once: a modification or deletion is a finding, an addition is not (case-insensitive)
FROZEN = ('nfl/tests/certificates/*', '*seal*.json', '*freeze*.json', '*freeze*.md',
          'nfl/vintage/*', '*/baseline_*/*', 'nfl/dfs/salaries/classic_early_*/research_projection/rebuild_*/*',
          'nfl/postgame/*/pregame_freeze_manifest.json', '*run_receipt*.json')
#: append-only logs and manifests: lines may be added, never changed or removed (case-insensitive). A SHA256SUMS or
#: a .jsonl inside a frozen directory grows when an artifact is added beside the sealed ones (measured on the
#: 120-commit history, 2026-10-10: three such appends, no hash changed), so it is judged as append-only, not frozen.
APPEND_ONLY = ('*ledger*.jsonl', '*_manifest.jsonl', 'coordination/handoff_log.jsonl', '*seal_history*.jsonl',
               '*/sha256sums', 'nfl/vintage/*.jsonl')
#: result documents where a status flipping toward success is a finding
RESULT_DOCS = ('*.json', '*.md', '*.txt', '*.csv', '*.jsonl')
#: JSON files whose numbers are configuration (thresholds), not data
CONFIG_JSON = ('*config*.json', '*threshold*.json', '*policy*.json', '*gates*.json', '*tolerance*.json')

TOL_LOOSER_WHEN_LARGER = re.compile(r'(TOL|TOLERANCE|EPS|EPSILON|MARGIN|SLACK|MAX_|_MAX\b|MAX$|LIMIT|CAP\b|_CAP_|'
                                    r'SE_MULTIPLE|ALLOW|^ABS$|^REL$|DELTA)', re.I)
TOL_LOOSER_WHEN_SMALLER = re.compile(r'(MIN_|_MIN\b|^MIN$|FLOOR|REQUIRED|AT_LEAST|PLACES|DECIMAL)', re.I)
THRESHOLD_NAME = re.compile(r'(CUTOFF|BOUND|^MAX$|^MIN$|^LOWER$|^UPPER$|'
                            r'TOL|TOLERANCE|EPS|EPSILON|MARGIN|SLACK|THRESHOLD|MIN_|_MIN\b|MAX_|_MAX\b|LIMIT|'
                            r'CAP\b|_CAP_|FLOOR|CEIL|SE_MULTIPLE|ALPHA|LEVEL|BAR\b|_BAR_|MAJORITY|QUOTA|^ABS$|^REL$|'
                            r'PLACES|DECIMAL|DELTA)', re.I)
#: DECLARED: names that are capacity or plumbing, not a bar a result has to clear (review item 8). Matched against
#: whole underscore-separated parts of the name (MIN_SIM_OPPORTUNITIES is a bar; its "PORT" is not a part).
NON_BAR_PARTS = {'PORT', 'SEED', 'VERSION', 'CACHE', 'BUFFER', 'PAGE', 'WIDTH', 'HEIGHT', 'COLUMNS', 'LINES',
                 'RECURSION', 'SLEEP', 'PRINT', 'DISPLAY', 'JOBS', 'BATCH', 'CHUNK', 'CHUNKS', 'ROWS', 'BYTES', 'KB',
                 'MB', 'LOG'}
NON_BAR_STEMS = ('WORKER', 'THREAD', 'TIMEOUT', 'RETR', 'CONCURREN', 'PARALLEL', 'PROCESS', 'VERBOS', 'BACKOFF')


class _NonBar:
    @staticmethod
    def search(name):
        parts = [x for x in re.split(r'[^A-Za-z0-9]+', str(name).upper()) if x]
        return any(x in NON_BAR_PARTS or x.startswith(NON_BAR_STEMS) for x in parts)


NON_BAR = _NonBar()
TOL_KEYWORDS = {'rel_tol', 'abs_tol', 'atol', 'rtol', 'places', 'delta', 'abs', 'rel', 'tol', 'tolerance',
                'decimal', 'eps', 'epsilon', 'margin'}
SUPPRESS_LINE = re.compile(r'(#\s*noqa|#\s*type:\s*ignore|#\s*pragma:\s*no\s*cover|#\s*nosec)')
#: DECLARED EXEMPTION (not tuning): `# noqa: E402` marks an import placed after the repository's `sys.path` insert,
#: the house convention in every tool and test here. Import position says nothing about the strength of a check.
SUPPRESS_EXEMPT = re.compile(r'#\s*noqa:\s*(?:(?:E[1-5]\d\d|W[1-6]\d\d)\s*,?\s*)+$')
#: ... and the same holds for every pure-layout pycodestyle code (E1xx-E5xx indentation, whitespace, blank lines,
#: line length, import position; W1xx-W6xx). F-codes (unused names), BLE001, bare noqa, type: ignore and
#: pragma: no cover can hide a result that is computed and never checked, and stay findings in test modules.
FAIL_WORDS = re.compile(r'\b(NOT[ _]VERIFIED|NOT[ _]READY|NOT[ _]EXECUTED|NOT[ _]PASS(ED)?|NOT[ _]ESTABLISHED|'
                        r'NOT[ _]YET[ _]\w+|NOT[ _]RECONCILED|UNRECONCILED|UNRESOLVED|FAIL|FAILED|FAILING|'
                        r'FAILURE|BLOCKED|UNVERIFIED|VIOLATED|REFUSED|STALE|MISSING|ERROR|BROKEN)\b|[❌✗✘🔴⛔]', re.I)
PASS_WORDS = re.compile(r'\b(PASS|PASSED|PASSING|READY|VERIFIED|CLEAN|COMPLETE|OK|SUCCESS|GREEN|RECONCILED|'
                        r'RESOLVED)\b|[✅✓✔🟢]', re.I)
#: a result ROW: a table row, or a short `label: STATUS` / bullet line whose status word is written as a status
#: (upper case) -- prose that merely mentions "missing" or "error" is not a recorded result (review 2: 19 of 22
#: history findings of the text rule were prose)
_TABLE_ROW = re.compile(r'^\s*\|.*\|\s*$')
_STATUS_LINE = re.compile(r'^\s*(?:[-*+]\s+|\d+[.)]\s+)?[^.!?]{0,100}?(?::|=|—|–|\s-\s|\*\*)\s*[`*]*\s*'
                          r'(?:[A-Z][A-Z_ ]{1,30}\b|[❌✗✘🔴⛔✅✓✔🟢])')
CHECK_CALLS = ('check', 'observe', 'assert_guard_is_load_bearing', 'assertTrue', 'assertEqual', 'assertIn',
               'assertFalse', 'assertRaises', 'assertAlmostEqual', 'assertIsNone', 'assertIsNotNone', 'assertLess',
               'assertLessEqual', 'assertGreater', 'assertGreaterEqual', 'assertNotEqual', 'assertNotIn',
               'assertIs', 'assertIsNot', 'assertCountEqual', 'assertRaisesRegex', 'assert_allclose',
               'assert_array_equal', 'assert_frame_equal', 'assert_series_equal', 'assert_almost_equal',
               'raises', 'warns', 'assertWarns', 'assertLogs', 'assertRaisesRegexp', 'deprecated_call')
#: unittest asserts that are a single comparison: judged exactly like the plain `assert a <op> b` they spell
_UNITTEST_CMP = {'assertEqual': ast.Eq, 'assertNotEqual': ast.NotEq, 'assertLess': ast.Lt, 'assertLessEqual': ast.LtE,
                 'assertGreater': ast.Gt, 'assertGreaterEqual': ast.GtE, 'assertIn': ast.In, 'assertNotIn': ast.NotIn,
                 'assertIs': ast.Is, 'assertIsNot': ast.IsNot, 'assertAlmostEqual': ast.Eq}
SKIP_NAMES = {'skip', 'skipIf', 'skipif', 'skipUnless', 'importorskip', 'xfail', 'skipTest', 'SkipTest', '_blocked',
              'blocked'}
SKIP_COUNTERS = re.compile(r'^(BLOCKED|SKIPPED|blocked_count|N_BLOCKED|N_SKIPPED)$')
JSON_PASS_KEYS = re.compile(r'(^|_)(passed|pass|ok|success|succeeded|verified|ready|complete|clean|green)$', re.I)
JSON_FAIL_KEYS = re.compile(r'(^|_)(failed|fail|failing\w*|failures?|errors?|violations?|blocked|stale|missing|refused|'
                            r'broken|n_fail\w*)$', re.I)
#: a list that IS the failures (its whole name is the failure noun): `effect_on_failure` describes, it does not list
JSON_FAIL_LIST_KEYS = re.compile(r'^(n_)?(failures?|failed\w*|failing\w*|errors?|violations?|blocked\w*|missing\w*|'
                                 r'stale\w*|refused\w*|red\w*)$', re.I)
JSON_STATUS_KEYS = re.compile(r'(status|verdict|state|result|outcome|grade)$', re.I)


class CouldNotRun(RuntimeError):
    """The diff could not be read. Exit 2, never 0."""


def _match(path, patterns, ci=False):
    if path is None:
        return False
    p = path.lower() if ci else path
    return any(fnmatch.fnmatchcase(p, q.lower() if ci else q) for q in patterns)


def _collected(path):
    return path is not None and any(rx.match(path) for rx in COLLECTED)


def _git_bytes(repo, *args, ok_codes=(0,)):
    r = subprocess.run(['git', '-C', str(repo), '-c', 'core.quotePath=false', *args], capture_output=True)
    if r.returncode not in ok_codes:
        raise CouldNotRun(f'git {" ".join(args)} -> {r.returncode}: '
                          f'{r.stderr.decode("utf-8", "replace").strip()[:300]}')
    return r.stdout


def _git(repo, *args, ok_codes=(0,)):
    return _git_bytes(repo, *args, ok_codes=ok_codes).decode('utf-8', 'replace')


def _show(repo, ref, path):
    """File text at a ref (None for the working tree). Bytes that are not UTF-8 are replaced, never fatal."""
    if path is None:
        return None
    if ref is None:
        p = pathlib.Path(repo) / path
        try:
            if p.is_symlink():
                return 'SYMLINK -> ' + str(p.readlink())
            if p.exists() and not p.is_file():
                raise CouldNotRun(f'{path} in the working tree is not a regular file (FIFO, device or directory)')
            return p.read_bytes().decode('utf-8', 'replace') if p.is_file() else None
        except OSError:
            return None
    r = subprocess.run(['git', '-C', str(repo), 'show', f'{ref}:{path}'], capture_output=True)
    return r.stdout.decode('utf-8', 'replace') if r.returncode == 0 else None


def merge_base(repo, base, head):
    out = _git(repo, 'merge-base', base, head or 'HEAD', ok_codes=(0, 1)).strip()
    if not out:
        raise CouldNotRun(f'no merge base between {base} and {head or "HEAD"} (shallow clone or unrelated history)')
    return out


def changed_files(repo, base, head):
    """[(status, old_path, new_path)] with renames and copies detected. Status is one of A M D R T C; a copy is
    judged as an addition of the new path. NUL-separated, so a non-ASCII path is never C-quoted."""
    raw = _git_bytes(repo, 'diff', '--name-status', '-z', '-M', '-C', '--no-color', base, *([head] if head else []))
    parts = raw.decode('utf-8', 'surrogateescape').split('\0')     # round-trips any byte path back to git
    out, i = [], 0
    while i < len(parts) and parts[i]:
        st = parts[i][0]
        if st in 'RC':
            out.append((st, parts[i + 1], parts[i + 2]))
            i += 3
        else:
            out.append((st, parts[i + 1], parts[i + 1]))
            i += 2
    if head is None:
        for p in _git_bytes(repo, 'ls-files', '-z', '--others', '--exclude-standard').decode(
                'utf-8', 'surrogateescape').split('\0'):
            if p:
                out.append(('A', p, p))
    return out


# ------------------------------------------------------------------ constant folding
_BINOPS = {ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b, ast.Mult: lambda a, b: a * b,
           ast.Div: lambda a, b: a / b, ast.Pow: lambda a, b: a ** b, ast.FloorDiv: lambda a, b: a // b,
           ast.Mod: lambda a, b: a % b}


def _num(node, names=None):
    """The numeric value of an expression made of constants (and names bound to constants), or None."""
    names = names or {}
    try:
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return node.value
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            v = _num(node.operand, names)
            return None if v is None else (-v if isinstance(node.op, ast.USub) else v)
        if isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
            a, b = _num(node.left, names), _num(node.right, names)
            if a is None or b is None:
                return None
            if isinstance(node.op, ast.Pow) and abs(b) > 64:
                return None
            v = _BINOPS[type(node.op)](a, b)
            return v if isinstance(v, (int, float)) and math.isfinite(v) else None
        if isinstance(node, ast.Name) and node.id in names:
            return names[node.id]
        if isinstance(node, ast.Attribute) and node.attr in names and isinstance(node.value, ast.Name) \
                and node.value.id in ('self', 'cls'):
            return names[node.attr]
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ('float', 'int') \
                and len(node.args) == 1:
            a0 = node.args[0]
            if isinstance(a0, ast.Constant) and isinstance(a0.value, str):
                try:
                    return float(a0.value) if node.func.id == 'float' else int(a0.value)
                except ValueError:
                    return None
            return _num(a0, names)
    except (ArithmeticError, TypeError, ValueError):
        return None
    return None


def _nums_in(node, names):
    """Every maximal constant-foldable number inside an expression (negatives and arithmetic folded). Tolerance
    keyword values (rel=, abs=, places=, ...) are left out: they are judged with their direction separately."""
    out = []

    def walk(n):
        v = _num(n, names)                            # a Name folds only when it is bound to a module constant
        if v is not None:
            out.append(round(float(v), 12))
            return
        if isinstance(n, ast.Call):
            walk(n.func)
            for a in n.args:
                walk(a)
            for k in n.keywords:
                if k.arg not in TOL_KEYWORDS:
                    walk(k.value)
            return
        for c in ast.iter_child_nodes(n):
            walk(c)
    walk(node)
    return out


def _parse(src):
    if src is None:
        return None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            return ast.parse(src)
    except (SyntaxError, ValueError):
        return None


def _callee(call):
    fn = call.func
    return fn.id if isinstance(fn, ast.Name) else fn.attr if isinstance(fn, ast.Attribute) else ''


def _module_numbers(tree):
    """{NAME: number} of every module/class-level name bound to a foldable number, in source order (for folding)."""
    names = {}
    for node in _top_statements(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value is not None:
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for t in targets:
                if isinstance(t, ast.Name):
                    v = _num(node.value, names)
                    if v is not None:
                        names[t.id] = v
                elif isinstance(t, ast.Tuple) and isinstance(node.value, ast.Tuple) \
                        and len(t.elts) == len(node.value.elts):
                    for te, ve in zip(t.elts, node.value.elts):
                        v = _num(ve, names)
                        if isinstance(te, ast.Name) and v is not None:
                            names[te.id] = v
        elif isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name) and node.target.id in names \
                and type(node.op) in _BINOPS:
            v = _num(node.value, names)
            if v is not None:
                try:
                    names[node.target.id] = _BINOPS[type(node.op)](names[node.target.id], v)
                except ArithmeticError:
                    pass
    return names


def _top_statements(tree):
    """Module-level and class-level statements, in order (not inside functions)."""
    out = []

    def visit(body):
        for n in body:
            out.append(n)
            if isinstance(n, ast.ClassDef):
                visit(n.body)
            elif isinstance(n, (ast.If, ast.Try)):
                visit(n.body)
                visit(getattr(n, 'orelse', []))
                for h in getattr(n, 'handlers', []):
                    visit(h.body)
    visit(tree.body)
    return out


# ------------------------------------------------------------------ tests
def _is_vacuous(expr, local, names):
    """Is a check condition true whatever the code under test does?"""
    if expr is None:
        return False
    if isinstance(expr, ast.Constant):
        return bool(expr.value)
    if isinstance(expr, ast.Tuple):
        return bool(expr.elts)                       # assert (cond, 'msg') is a non-empty tuple: always true
    v = _num(expr, names)
    if v is not None:
        return bool(v)
    if isinstance(expr, ast.Name) and expr.id in local:
        return local[expr.id]
    if isinstance(expr, ast.BoolOp):
        vals = [_is_vacuous(x, local, names) for x in expr.values]
        return any(vals) if isinstance(expr.op, ast.Or) else all(vals)
    if isinstance(expr, ast.Compare) and len(expr.ops) == 1:
        left, right, op = expr.left, expr.comparators[0], expr.ops[0]
        if isinstance(op, (ast.Eq, ast.LtE, ast.GtE, ast.Is)) and ast.dump(left) == ast.dump(right):
            return True
        a, b = _num(left, names), _num(right, names)
        if a is not None and b is not None:
            try:
                return bool({ast.Eq: a == b, ast.NotEq: a != b, ast.Lt: a < b, ast.LtE: a <= b, ast.Gt: a > b,
                             ast.GtE: a >= b}.get(type(op), False))
            except TypeError:
                return False
        def is_len(x):
            return isinstance(x, ast.Call) and isinstance(x.func, ast.Name) and x.func.id in ('len', 'abs')
        if is_len(left) and isinstance(op, ast.GtE) and b is not None and b <= 0:
            return True
        if is_len(right) and isinstance(op, ast.LtE) and a is not None and a <= 0:
            return True
    return False


def _check_conditions(fn):
    """[(kind, condition expr or None, node)] for every check in a test function."""
    out = []
    for sub in ast.walk(fn):
        if isinstance(sub, ast.Assert):
            out.append(('assert', sub.test, sub))
        elif isinstance(sub, ast.Call):
            name = _callee(sub)
            if name in CHECK_CALLS:
                cond = None
                if name in ('check', 'observe') and len(sub.args) >= 2:
                    cond = sub.args[1]
                elif name in ('assertTrue', 'assertIsNotNone') and sub.args:
                    cond = sub.args[0]
                elif name in ('assertEqual', 'assertIs', 'assertAlmostEqual') and len(sub.args) >= 2:
                    cond = ast.Compare(left=sub.args[0], ops=[ast.Eq()], comparators=[sub.args[1]])
                out.append((name, cond, sub))
        elif isinstance(sub, ast.If) and _raises_in(sub.body):
            out.append(('if-raise', ast.UnaryOp(op=ast.Not(), operand=sub.test), sub))
    return out


def _cmp_parts(left, op, right, names):
    """(signature, detail) of one comparison. detail = (op, constant side, constant, other numbers) when exactly one
    side folds to a number, so that a bound moved one way can be told from a bound moved the other."""
    lv, rv = _num(left, names), _num(right, names)
    nums = tuple(sorted(_nums_in(left, names) + _nums_in(right, names)))
    sig = ('cmp', (op.__name__,), nums)
    detail = None
    if (lv is None) != (rv is None):
        side, const, other = ('right', rv, left) if rv is not None else ('left', lv, right)
        detail = (op.__name__, side, round(float(const), 12), tuple(sorted(_nums_in(other, names))))
    return sig, detail


def _signatures(fn, names):
    """Comparisons a test makes, without variable names: (operators, folded numbers); tolerance keywords; and
    `if ...: raise` tripwire conditions. A unittest assert that is one comparison has the same signature as the
    plain assert it spells. Returns (signatures, tolerance keywords, {signature: [direction details]})."""
    sigs, tols, details = collections.Counter(), [], collections.defaultdict(list)
    for sub in _walk_own(fn):
        if isinstance(sub, ast.Compare):
            if len(sub.ops) == 1:
                sig, det = _cmp_parts(sub.left, type(sub.ops[0]), sub.comparators[0], names)
            else:
                sig, det = ('cmp', tuple(type(o).__name__ for o in sub.ops), tuple(sorted(_nums_in(sub, names)))), None
            sigs[sig] += 1
            if det:
                details[sig].append(det)
        elif isinstance(sub, ast.Call):
            name = _callee(sub)
            for k in sub.keywords:
                if k.arg in TOL_KEYWORDS:
                    v = _num(k.value, names)
                    if v is not None:
                        tols.append((name, k.arg, v))
            if name in _UNITTEST_CMP and len(sub.args) >= 2:
                sig, det = _cmp_parts(sub.args[0], _UNITTEST_CMP[name], sub.args[1], names)
                sigs[sig] += 1
                if det:
                    details[sig].append(det)
            elif name.startswith('assert') and name not in ('assertTrue', 'assertFalse'):
                ns = [x for a in sub.args for x in _nums_in(a, names)]
                if ns:
                    sigs[('call', name, tuple(sorted(ns)))] += 1
        elif isinstance(sub, ast.If) and _raises_in(sub.body):
            sigs[('tripwire', ast.dump(sub.test, annotate_fields=False)[:400])] += 1
    return sigs, tols, details


def _walk_own(fn):
    """ast.walk over a function's own body, not into nested functions, lambdas or classes (their returns and
    comparisons are theirs, review 2: a nested helper's `return` read as the test returning early)."""
    nested = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)
    stack = [b for b in fn.body if not isinstance(b, nested)]
    while stack:
        n = stack.pop()
        yield n
        for c in ast.iter_child_nodes(n):
            if not isinstance(c, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
                stack.append(c)


def _raises_in(body):
    """Does a block raise as one of its own statements (`if bad: log(...); raise ...`)?"""
    return any(isinstance(b, ast.Raise) for b in body)


_TIGHTER = {('Lt', 'right'): -1, ('LtE', 'right'): -1, ('Gt', 'right'): 1, ('GtE', 'right'): 1,
            ('Lt', 'left'): 1, ('LtE', 'left'): 1, ('Gt', 'left'): -1, ('GtE', 'left'): -1}


def _bound_direction(db, da):
    """'tighter' / 'looser' / None for one comparison detail before and after: same operator and side, same other
    numbers, only the bound moved. `x < N`: a smaller N is tighter; `x > N`: a larger N is tighter."""
    if not (db and da) or db[0] != da[0] or db[1] != da[1] or db[3] != da[3] or db[2] == da[2]:
        return None
    sign = _TIGHTER.get((db[0], db[1]))
    if sign is None:
        return None
    return 'tighter' if (da[2] - db[2]) * sign > 0 else 'looser'


def _local_truths(fn, names):
    """{name: is-constant-truthy} for names a test function binds exactly once."""
    binds = collections.defaultdict(list)
    for sub in ast.walk(fn):
        if isinstance(sub, ast.Assign):
            for t in sub.targets:
                if isinstance(t, ast.Name):
                    binds[t.id].append(sub.value)
    out = {}
    for k, vs in binds.items():
        if len(vs) == 1:
            v = vs[0]
            out[k] = (isinstance(v, ast.Constant) and bool(v.value)) or (_num(v, names) not in (None, 0))
    return out


def _test_facts(fn, names):
    conds = _check_conditions(fn)
    local = _local_truths(fn, names)
    sigs, tols, details = _signatures(fn, names)
    body = [b for b in fn.body if not (isinstance(b, ast.Expr) and isinstance(b.value, ast.Constant))]
    last_check = max((c[2].lineno for c in conds), default=0)
    early = 0
    for sub in _walk_own(fn):
        if isinstance(sub, ast.Return) and sub.lineno < last_check:
            early += 1
    if not conds and body and isinstance(body[0], ast.Return):
        early += 1
    return {'n_checks': len(conds), 'vacuous': sum(_is_vacuous(c[1], local, names) for c in conds),
            'sigs': sigs, 'tols': tols, 'details': details, 'early_return': early,
            'trivial': (not body) or all(isinstance(b, ast.Pass) or (isinstance(b, ast.Expr) and
                                                                     isinstance(b.value, ast.Constant)) for b in body),
            'body': ast.dump(ast.Module(body=fn.body, type_ignores=[]), annotate_fields=False),
            'numbers': sorted(x for s in sigs for x in (s[2] if s[0] in ('cmp', 'call') else ()))}


def _tests_in(src):
    """{test function name: facts} for the tests nfl/tests/run_suite.py actually runs: module-level callables whose
    name starts with `test_` (run_suite.py: `n.startswith('test_') and callable(...)`). A method in a class or a
    function named `testx` is never run; a name rebound or deleted at module level after its def
    (`test_x = lambda: None`, `del test_x`) is not a test any more."""
    tree = _parse(src)
    if tree is None:
        return None
    names = _module_numbers(tree)
    out = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith('test_'):
            out[node.name] = _test_facts(node, names)
        elif isinstance(node, ast.ClassDef):
            # not run by this repository's runner, but judged for weakening (a pytest or unittest run would use them)
            for m in node.body:
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)) and m.name.startswith('test'):
                    out[f'{node.name}.{m.name}'] = _test_facts(m, names)
        elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for t in targets:
                if isinstance(t, ast.Name) and t.id in out:
                    out.pop(t.id)
        elif isinstance(node, ast.Delete):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    out.pop(t.id, None)
    return out


def _helpers(src):
    """{helper name: (fingerprint, n failure increments)} for the module's own check()/observe() helpers."""
    tree = _parse(src)
    out = {}
    if tree is None:
        return out
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in ('check', 'observe', '_check', 'expect'):
            incs = sum(1 for s in ast.walk(node) if isinstance(s, ast.AugAssign) and isinstance(s.target, ast.Name)
                       and re.search(r'FAIL', s.target.id, re.I))
            raises = sum(1 for s in ast.walk(node) if isinstance(s, ast.Raise))
            out[node.name] = (ast.dump(node, annotate_fields=False), incs + raises)
    return out


def _skips(src):
    """Number of skip paths in a module: skip calls and decorators of every spelling, SkipTest raises, BLOCKED or
    SKIPPED counters incremented (`+= 1` or `X = X + 1`)."""
    tree = _parse(src)
    if tree is None:
        return 0
    n = 0
    for s in ast.walk(tree):
        if isinstance(s, ast.Call) and _callee(s) in SKIP_NAMES:
            n += 1
        elif isinstance(s, ast.Raise) and s.exc is not None and 'SkipTest' in ast.dump(s.exc):
            n += 1
        elif isinstance(s, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'pytestmark' for t in s.targets) \
                and re.search(r"attr='(skip|skipif|xfail)'", ast.dump(s.value)):
            n += 1
        elif isinstance(s, ast.AugAssign) and isinstance(s.target, ast.Name) and SKIP_COUNTERS.match(s.target.id):
            n += 1
        elif isinstance(s, ast.Assign) and any(isinstance(t, ast.Name) and SKIP_COUNTERS.match(t.id) for t in s.targets) \
                and isinstance(s.value, ast.BinOp):
            n += 1
        elif isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            for d in s.decorator_list:
                tgt = d.func if isinstance(d, ast.Call) else d
                nm = tgt.id if isinstance(tgt, ast.Name) else tgt.attr if isinstance(tgt, ast.Attribute) else ''
                if nm in SKIP_NAMES:
                    n += 1
    return n


def _skip_lines(src):
    """The source lines of skip paths (evidence for a finding)."""
    tree = _parse(src)
    lines = (src or '').splitlines()
    out = []
    if tree is None:
        return out
    for s in ast.walk(tree):
        hit = (isinstance(s, ast.Call) and _callee(s) in SKIP_NAMES) or \
              (isinstance(s, ast.AugAssign) and isinstance(s.target, ast.Name) and SKIP_COUNTERS.match(s.target.id))
        if hit and 0 < s.lineno <= len(lines):
            out.append(lines[s.lineno - 1].strip()[:160])
    return out


# ------------------------------------------------------------------ thresholds
def _is_bar(name):
    return bool(THRESHOLD_NAME.search(name)) and not NON_BAR.search(name)


def _constants(src):
    """{KEY: number} for threshold-like bars: module/class names (tuple, augmented and annotated assignments
    folded), dict entries `D[key]`, and argument defaults `fn(arg)`."""
    tree = _parse(src)
    if tree is None:
        return {}
    names = _module_numbers(tree)
    out = {k: v for k, v in names.items() if _is_bar(k)}
    for node in _top_statements(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and isinstance(node.value, ast.Dict):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for t in targets:
                if not isinstance(t, ast.Name):
                    continue
                for k, v in zip(node.value.keys, node.value.values):
                    if isinstance(k, ast.Constant) and isinstance(k.value, str):
                        num = _num(v, names)
                        key = f'{t.id}[{k.value}]'
                        if num is not None and (_is_bar(t.id) or _is_bar(k.value)) and not NON_BAR.search(key):
                            out[key] = num
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            a = node.args
            pos = a.posonlyargs + a.args
            for arg, d in zip(pos[len(pos) - len(a.defaults):], a.defaults):
                num = _num(d, names)
                if num is not None and _is_bar(arg.arg):
                    out[f'{node.name}({arg.arg})'] = num
            for arg, d in zip(a.kwonlyargs, a.kw_defaults):
                num = _num(d, names) if d is not None else None
                if num is not None and _is_bar(arg.arg):
                    out[f'{node.name}({arg.arg})'] = num
    return out


def _call_keywords(tree, names):
    """Counter of (callee, keyword, value) for tolerance / bar keywords passed at call sites."""
    c = collections.Counter()
    for s in ast.walk(tree):
        if isinstance(s, ast.Call):
            for k in s.keywords:
                if k.arg and (k.arg in TOL_KEYWORDS or _is_bar(k.arg)):
                    v = _num(k.value, names)
                    if v is not None:
                        c[(_callee(s), k.arg, v)] += 1
    return c


def _threshold_uses(tree, names):
    """{(operator, other side as text, threshold names): folded value} for comparisons against a bar name, so
    `err > 1000 * TOL` replacing `err > TOL` is a change of the bar even though TOL itself did not move."""
    out = collections.defaultdict(list)
    for s in ast.walk(tree):
        if not (isinstance(s, ast.Compare) and len(s.ops) == 1):
            continue
        sides = [(s.left, s.comparators[0], False), (s.comparators[0], s.left, True)]
        for bar, other, flipped in sides:
            bar_names = sorted({n.id for n in ast.walk(bar) if isinstance(n, ast.Name) and _is_bar(n.id)})
            if not bar_names and not isinstance(bar, (ast.Constant, ast.UnaryOp, ast.BinOp)):
                continue
            v = _num(bar, names)
            if v is None:
                continue
            try:
                txt = ast.unparse(other)[:120]
            except Exception:  # noqa: BLE001
                txt = ast.dump(other)[:120]
            out[(type(s.ops[0]).__name__, flipped, txt)].append((v, bar_names))
    return out


def _overrides(tree):
    """[(module alias, attribute, value)] for thresholds a module sets on ANOTHER module: `engine.TOL = 0.5`,
    setattr(engine, 'TOL', 0.5), monkeypatch.setattr(engine, 'TOL', 0.5), patch.object(engine, 'TOL', 0.5)."""
    out = []
    for s in ast.walk(tree):
        if isinstance(s, ast.Assign):
            for t in s.targets:
                if isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name) and _is_bar(t.attr) \
                        and t.value.id not in ('self', 'cls'):
                    v = _num(s.value)
                    if v is not None:
                        out.append((t.value.id, t.attr, v))
        elif isinstance(s, ast.Call) and _callee(s) in ('setattr', 'object') and len(s.args) >= 3 \
                and isinstance(s.args[0], ast.Name) and isinstance(s.args[1], ast.Constant) \
                and isinstance(s.args[1].value, str) and _is_bar(s.args[1].value):
            v = _num(s.args[2])
            if v is not None:
                out.append((s.args[0].id, s.args[1].value, v))
    return out


def _imports(tree):
    """{alias: dotted module} for a module's imports."""
    out = {}
    for s in ast.walk(tree):
        if isinstance(s, ast.Import):
            for a in s.names:
                out[a.asname or a.name.split('.')[0]] = a.name if a.asname else a.name.split('.')[0]
        elif isinstance(s, ast.ImportFrom) and s.module:
            for a in s.names:
                out[a.asname or a.name] = f'{s.module}.{a.name}'
    return out


def _direction(name, before, after):
    """'looser', 'tighter' or 'changed' for a bar moving from before to after."""
    if before == after:
        return 'changed'
    if TOL_LOOSER_WHEN_SMALLER.search(name):
        return 'looser' if after < before else 'tighter'
    if TOL_LOOSER_WHEN_LARGER.search(name):
        return 'looser' if abs(after) > abs(before) else 'tighter'
    return 'changed'


def _bar_finding(path, key, before, after, what=''):
    leaf = key.split('[')[-1].split('(')[-1].rstrip('])=')
    d = _direction(leaf, before, after)
    if d == 'changed':                                # TOLERANCES['accounting']: the container names the bar
        d = _direction(re.split(r'[\[(.:]', key.split(': ')[-1])[0], before, after)
    if d == 'looser':
        return _f('THRESHOLD_LOOSENED', 'high', path, f'{key}: {before} -> {after}{what}')
    if d == 'tighter':
        return _f('THRESHOLD_TIGHTENED', 'info', path, f'{key}: {before} -> {after}{what}')
    return _f('THRESHOLD_CHANGED', 'medium', path, f'{key}: {before} -> {after}{what}')


def _json_numbers(text):
    try:
        doc = json.loads(text)
    except (ValueError, TypeError):
        return None
    out = {}

    def walk(x, path):
        if isinstance(x, dict):
            for k, v in x.items():
                walk(v, f'{path}.{k}' if path else str(k))
        elif isinstance(x, list):
            for i, v in enumerate(x):
                walk(v, f'{path}[{i}]')
        elif isinstance(x, (int, float)) and not isinstance(x, bool):
            out[path] = x
    walk(doc, '')
    return out


# ------------------------------------------------------------------ other code rules
def _broad_swallows(src):
    """Handlers that catch everything and carry on: `except:` / Exception / BaseException (alone or in a tuple)
    whose body only passes, continues, returns a constant or is `...`; and contextlib.suppress(Exception)."""
    tree = _parse(src)
    if tree is None:
        return 0
    broad_names = ('Exception', 'BaseException')

    def is_broad(t):
        if t is None:
            return True
        if isinstance(t, ast.Tuple):
            return any(is_broad(x) for x in t.elts)
        nm = t.id if isinstance(t, ast.Name) else t.attr if isinstance(t, ast.Attribute) else ''
        return nm in broad_names

    def swallows(body):
        for b in body:
            if isinstance(b, (ast.Pass, ast.Continue, ast.Break)):
                continue
            if isinstance(b, ast.Expr) and isinstance(b.value, ast.Constant):
                continue
            if isinstance(b, ast.Return) and (b.value is None or isinstance(b.value, ast.Constant)):
                continue
            return False
        return True
    n = 0
    for s in ast.walk(tree):
        if isinstance(s, ast.ExceptHandler) and is_broad(s.type) and swallows(s.body):
            n += 1
        elif isinstance(s, ast.With):
            for it in s.items:
                e = it.context_expr
                if isinstance(e, ast.Call) and _callee(e) == 'suppress' and any(is_broad(a) for a in e.args):
                    n += 1
    return n


def _guard_raises(src):
    """Validation guards in non-test code: `if <condition>: raise ...` (the stage refuses bad or empty output)."""
    tree = _parse(src)
    if tree is None:
        return 0
    return sum(1 for s in ast.walk(tree) if isinstance(s, ast.If) and _raises_in(s.body))


def _suppressions(lines):
    return sum(1 for ln in lines if SUPPRESS_LINE.search(ln) and not SUPPRESS_EXEMPT.search(ln))


# ------------------------------------------------------------------ result documents
def _status_key(line):
    """A result row with its status words removed: what the row is about, so a flipped row can be paired."""
    s = FAIL_WORDS.sub('', PASS_WORDS.sub('', line))
    s = re.sub(r'\([^)]*\)', '', s)
    return re.sub(r'[\s|:*`_\-]+', ' ', s).strip().lower()


def _fails(line):
    return bool(FAIL_WORDS.search(line))


def _passes(line):
    return bool(PASS_WORDS.search(FAIL_WORDS.sub('', line)))


_KV_STATUS = re.compile(r'^\s*[\w./:-]+\s*[:=,]\s*(fail|failed|failing|error|ok|pass|passed|success)\s*$', re.I)
_CSV_MODE = [False]


def _is_result_row(line):
    return bool(_TABLE_ROW.match(line) or _STATUS_LINE.match(line) or _KV_STATUS.match(line)
                or (_CSV_MODE[0] and ',' in line))


def _text_result_flips(before, after):
    """[(before line, after line or None)] where a recorded failure became a success, or a failing TABLE row was
    deleted. Only result rows count: a table row, or a short `label: STATUS` line; prose does not."""
    b_lines, a_lines = before.splitlines(), after.splitlines()
    a_count = collections.Counter(a_lines)
    a_by_key = collections.defaultdict(list)
    for ln in a_lines:
        a_by_key[_status_key(ln)].append(ln)
    n_fail_rows_after = sum(1 for ln in a_lines if _is_result_row(ln) and _fails(ln))
    n_fail_rows_before = sum(1 for ln in b_lines if _is_result_row(ln) and _fails(ln))
    out = []
    removed = collections.Counter(b_lines) - a_count
    for ln, k in removed.items():
        if not (_fails(ln) and _is_result_row(ln)):
            continue
        key = _status_key(ln)
        cands = a_by_key.get(key) or []
        if any(_fails(c) for c in cands):
            continue                                  # still recorded as a failure (reworded)
        flipped = [c for c in cands if _passes(c) and _is_result_row(c)]
        if flipped:
            out.append((ln, flipped[0]))
        elif key and not cands and (_TABLE_ROW.match(ln) or _CSV_MODE[0]) and n_fail_rows_after < n_fail_rows_before:
            out.append((ln, None))                    # a failing row is gone and the table has fewer failures
    return out


def _json_leaves(doc, path=''):
    if isinstance(doc, dict):
        for k, v in doc.items():
            yield from _json_leaves(v, f'{path}.{k}' if path else str(k))
    elif isinstance(doc, list):
        for i, v in enumerate(doc):
            yield from _json_leaves(v, f'{path}[{i}]')
    else:
        yield path, doc


def _jsonl_result_flips(before, after):
    """Row-by-row for a .jsonl whose rows carry an id: each row judged as a JSON result."""
    def rows(text):
        out = {}
        for ln in text.splitlines():
            try:
                r = json.loads(ln)
            except ValueError:
                return None
            if not isinstance(r, dict) or 'id' not in r:
                return None
            out[str(r['id'])] = r
        return out
    rb, ra = rows(before), rows(after)
    if rb is None or ra is None:
        return []
    out = []
    for k in sorted(set(rb) & set(ra)):
        if rb[k] != ra[k]:
            for p, bv, av in _json_result_flips(json.dumps(rb[k]), json.dumps(ra[k])) or []:
                out.append((f'{k}.{p}', bv, av))
    return out


def _json_parses(text):
    try:
        json.loads(text)
        return True
    except (ValueError, TypeError):
        return False


def _json_lists(doc, path=''):
    """{path: length} of every list in a JSON document."""
    out = {}
    if isinstance(doc, dict):
        for k, v in doc.items():
            out.update(_json_lists(v, f'{path}.{k}' if path else str(k)))
    elif isinstance(doc, list):
        out[path] = len(doc)
        for i, v in enumerate(doc):
            out.update(_json_lists(v, f'{path}[{i}]'))
    return out


def _json_result_flips(before, after):
    try:
        b, a = json.loads(before), json.loads(after)
    except (ValueError, TypeError):
        return None
    bl, al = dict(_json_leaves(b)), dict(_json_leaves(a))

    def n_failing(leaves):
        return sum(1 for k, v in leaves.items() if isinstance(v, str) and len(v) < 80 and _fails(v))
    n_fail_before, n_fail_after = n_failing(bl), n_failing(al)
    out = []
    lb, la = _json_lists(b), _json_lists(a)
    for path, nb in lb.items():
        key = re.split(r'[.\[]', path)[-1].rstrip(']')
        if JSON_FAIL_LIST_KEYS.match(key) and nb > la.get(path, 0):
            out.append((path, f'{nb} entries', f'{la.get(path, 0)} entries'))
    for path, bv in bl.items():
        key = re.split(r'[.\[]', path)[-1].rstrip(']')
        av = al.get(path, '__ABSENT__')
        if isinstance(bv, bool):
            if JSON_PASS_KEYS.search(key) and bv is False and av is True:
                out.append((path, bv, av))
            elif JSON_FAIL_KEYS.search(key) and bv is True and av in (False, '__ABSENT__'):
                out.append((path, bv, av))
        elif isinstance(bv, (int, float)) and JSON_FAIL_KEYS.search(key) and bv > 0 and \
                (av == 0 or av == '__ABSENT__'):
            out.append((path, bv, av))
        elif isinstance(bv, str) and (JSON_STATUS_KEYS.search(key) or _fails(bv) and len(bv) < 80) and _fails(bv):
            if av == '__ABSENT__' and JSON_STATUS_KEYS.search(key):
                if n_fail_after < n_fail_before:          # a renamed schema keeps its failures elsewhere
                    out.append((path, bv, None))
            elif isinstance(av, str) and not _fails(av) and _passes(av):
                out.append((path, bv, av))
    return out


# ------------------------------------------------------------------ rules
def _safe(text):
    """Display form of a path or detail: a byte that is not UTF-8 (kept as a surrogate so git gets the real path)
    is shown as an escape, so the report is always valid UTF-8."""
    return text.encode('utf-8', 'surrogateescape').decode('utf-8', 'backslashreplace') if isinstance(text, str) else text


def _f(rule, severity, path, detail, **ev):
    return {'rule': rule, 'severity': severity, 'path': _safe(path), 'detail': _safe(detail),
            'evidence': {k: _safe(v) for k, v in ev.items()}, 'authorization': 'NONE_RECORDED'}


def _detector_rows(text):
    try:
        doc = json.loads(text)
    except (ValueError, TypeError):
        return None
    rows = doc.get('detectors') if isinstance(doc, dict) else doc
    out = {}
    for r in rows or []:
        k = r.get('detector') if isinstance(r, dict) else str(r)
        out[k] = r
    return out


def _weaker_row(b, a):
    """Did a detector row lose something it must fire on, or have a field emptied?"""
    if not (isinstance(b, dict) and isinstance(a, dict)):
        return b != a
    for k, v in b.items():
        av = a.get(k)
        if isinstance(v, list) and (av is None or (isinstance(av, list) and len(av) < len(v))):
            return True
        if v and not av:
            return True
    return False


def judge_file(repo, base, head, st, old, new, ctx=None):
    out = []
    ctx = ctx or {}
    path = new
    if st == 'C':
        st, old = 'A', new                            # a copy is an addition of the new path
    type_changed = st == 'T'
    if st == 'T':
        st = 'M'                                      # a type change (file <-> symlink) is a modification
    is_test = _match(path, TEST_FILE) or _match(old, TEST_FILE)
    before = _show(repo, base, old) if st != 'A' else None
    after = _show(repo, head, new) if st != 'D' else None
    if (st != 'A' and before is None) or (st != 'D' and after is None):
        raise CouldNotRun(f'{old if before is None else new}: the {"base" if before is None else "head"} side of a '
                          f'{st} change could not be read (submodule, unreadable path or object)')

    # ---- the runner's collection: a test module it ran before and does not run now
    if _collected(old) and st != 'A' and (st == 'D' or not _collected(new)):
        out.append(_f('TEST_FILE_DELETED', 'high', old,
                      'a test module the runner collected was deleted' if st == 'D' else
                      f'a test module was moved out of the runner\'s collection ({new}); it no longer runs'))
    # ---- governance and approval evidence
    approval = APPROVAL_NAME is not None and any(p and APPROVAL_NAME.search(pathlib.PurePath(p).name) for p in (old, new))
    if _match(path, GOVERNANCE) or _match(old, GOVERNANCE) or approval:
        out.append(_f('GOVERNANCE_OR_SAFEGUARD_CHANGED', 'high', path,
                      'an owner-authority or approval file, or a safeguard itself, changed', status=st))
    if path == 'coordination/PROJECT_STATE.json' and after is not None and 'mode_declared' in after \
            and 'mode_declared' not in (before or ''):
        out.append(_f('GOVERNANCE_OR_SAFEGUARD_CHANGED', 'high', path, 'mode_declared written (only the owner states it)'))
    # ---- verification machinery
    if _match(path, VERIFICATION_MACHINERY) or _match(old, VERIFICATION_MACHINERY):
        sev, detail = 'high', 'the machinery that decides what counts as proof changed' + (' (new file)' if st == 'A' else '')
        if path.endswith('DETECTORS.json') and before is not None and after is not None:
            bk, ak = _detector_rows(before), _detector_rows(after)
            if bk is not None and ak is not None:
                gone = sorted(set(bk) - set(ak))
                weakened = sorted(k for k in set(bk) & set(ak) if bk[k] != ak[k] and _weaker_row(bk[k], ak[k]))
                edited = sorted(k for k in set(bk) & set(ak) if bk[k] != ak[k] and k not in weakened)
                if gone:
                    detail = f'{len(gone)} detector(s) removed: {gone[:5]}'
                elif weakened:
                    detail = f'{len(weakened)} detector row(s) weakened in place: {weakened[:5]}'
                elif edited:
                    sev, detail = 'medium', f'{len(edited)} detector row(s) edited: {edited[:5]}'
                else:
                    sev, detail = 'info', f'detectors only added ({len(set(ak) - set(bk))})'
        out.append(_f('VERIFICATION_MACHINERY_CHANGED', sev, path, detail, status=st))
    if _match(path, TEST_CONFIG) and after is not None:
        diff = list(difflib.unified_diff((before or '').splitlines(), after.splitlines(), lineterm='', n=0))
        if any(TEST_CONFIG_WORDS.search(d) for d in diff if d[:1] in '+-' and not d.startswith(('+++', '---'))):
            out.append(_f('VERIFICATION_MACHINERY_CHANGED', 'high', path, 'test collection or pytest options changed'))
    # ---- frozen and append-only
    frozen = _match(old, FROZEN, ci=True) and not _match(old, APPEND_ONLY, ci=True)
    if st in ('M', 'D', 'R') and frozen:
        out.append(_f('FROZEN_ARTIFACT_MODIFIED', 'high', old, 'a write-once artifact was modified, moved or deleted',
                      status=st))
    if st in ('M', 'D', 'R') and _match(old, APPEND_ONLY, ci=True):
        if st == 'D':
            out.append(_f('APPEND_ONLY_LOG_REWRITTEN', 'high', old, 'an append-only log was deleted'))
        elif before is not None and after is not None:
            # append-only means no existing line was removed or changed; a sorted manifest (SHA256SUMS) inserts new
            # lines in order, which is still only an addition. A rename is judged against the old content.
            gone = collections.Counter(before.splitlines()) - collections.Counter(after.splitlines())
            if gone:
                out.append(_f('APPEND_ONLY_LOG_REWRITTEN', 'high', old,
                              f'{sum(gone.values())} existing line(s) removed or changed in an append-only file'
                              + (f' (renamed to {new})' if st == 'R' else ''), example=next(iter(gone))[:160]))

    if st == 'D' or after is None:
        return out
    b_lines, a_lines = (before or '').splitlines(), after.splitlines()
    added = list((collections.Counter(a_lines) - collections.Counter(b_lines)).elements())
    removed = list((collections.Counter(b_lines) - collections.Counter(a_lines)).elements())

    if path.endswith('.py'):
        tree_a = _parse(after)
        tree_b = _parse(before) if before else None
        if is_test:
            out.extend(_judge_tests(path, st, before, after, ctx))
        # thresholds (module, class, dict, defaults), call-site keywords, use-site expressions
        cb, ca = _constants(before or ''), _constants(after)
        renamed_values = collections.Counter(ca[k] for k in set(ca) - set(cb))
        for name in sorted(set(cb) & set(ca)):
            if cb[name] != ca[name]:
                out.append(_bar_finding(path, name, cb[name], ca[name]))
        for name in sorted(set(cb) - set(ca)):
            elsewhere = [m for m, consts in ctx.get('constants_after', {}).items()
                         if m != path and consts.get(name) == cb[name]]
            if elsewhere:
                continue                               # moved to another module with the same value
            if renamed_values[cb[name]] > 0:
                renamed_values[cb[name]] -= 1          # same value under a new bar name: a rename
                continue
            out.append(_f('THRESHOLD_REMOVED', 'medium', path, f'{name} = {cb[name]} no longer defined'))
        if tree_a is not None and tree_b is not None:
            nb_, na_ = _module_numbers(tree_b), _module_numbers(tree_a)
            kb, ka = _call_keywords(tree_b, nb_), _call_keywords(tree_a, na_)
            by_b, by_a = collections.defaultdict(list), collections.defaultdict(list)
            for (c, k, v), n in (kb - ka).items():
                by_b[(c, k)].extend([v] * n)
            for (c, k, v), n in (ka - kb).items():
                by_a[(c, k)].extend([v] * n)
            for key in sorted(set(by_b) & set(by_a)):
                for vb, va in zip(sorted(by_b[key]), sorted(by_a[key])):
                    out.append(_bar_finding(path, f'{key[0]}({key[1]}=)', vb, va, ' at a call site'))
            ub, ua = _threshold_uses(tree_b, nb_), _threshold_uses(tree_a, na_)
            for key in sorted(set(ub) & set(ua)):
                vb, va = sorted(v for v, _ in ub[key]), sorted(v for v, _ in ua[key])
                names = sorted({n for _, ns in ub[key] + ua[key] for n in ns})
                if vb != va and len(vb) == len(va) and names:      # judged only where a named bar is involved
                    for x, y in zip(vb, va):
                        if x != y:
                            out.append(_bar_finding(path, names[0] if names else 'bar', x, y,
                                                    f' where it is compared with {key[2]}'))
        if tree_a is not None and is_test:
            imports = _imports(tree_a)
            old_over = set(_overrides(tree_b)) if tree_b is not None else set()
            for alias, attr, v in _overrides(tree_a):
                if (alias, attr, v) in old_over:
                    continue
                mod = imports.get(alias)
                orig = None
                if mod:
                    src = _show(repo, head, mod.replace('.', '/') + '.py')
                    orig = _constants(src or '').get(attr)
                if orig is not None and orig != v:
                    out.append(_bar_finding(path, f'{mod}.{attr}', orig, v, ' (overridden from a test module)'))
                elif orig is None:
                    out.append(_f('THRESHOLD_CHANGED', 'medium', path, f'{alias}.{attr} overridden to {v} from a test '
                                                                       f'module (original value not resolved)'))
        nb, na = _broad_swallows(before or ''), _broad_swallows(after)
        if na > nb:
            out.append(_f('BROAD_EXCEPT_PASS_ADDED', 'medium', path,
                          f'{na - nb} new broad exception swallow(s) (an error silenced is a failure hidden)'))
        if not is_test and before is not None:
            gb, ga = _guard_raises(before), _guard_raises(after)
            if ga < gb:
                out.append(_f('VALIDATION_REMOVED', 'medium', path, f'{gb - ga} `if ...: raise` validation guard(s) '
                                                                    f'removed ({gb} -> {ga})'))
        n_sup = _suppressions(added) - _suppressions(removed)
        if n_sup > 0:
            # medium in test modules (a suppressed warning there can hide a broken check); info elsewhere. Measured
            # 2026-10-10: 261 suppressions added over 120 commits (209 E402, 27 E731, 18 BLE001), none tied to a
            # weakened check; outside tests they are code style, not the bar.
            out.append(_f('SUPPRESSION_ADDED', 'medium' if is_test else 'info', path,
                          f'{n_sup} new lint/type/coverage suppression(s)'))
    elif path.endswith('.json') and _match(path, CONFIG_JSON, ci=True) and before is not None:
        jb, ja = _json_numbers(before), _json_numbers(after)
        if jb is not None and ja is not None:
            for k in sorted(set(jb) & set(ja)):
                leaf = re.split(r'[.\[]', k)[-1].rstrip(']')
                if jb[k] != ja[k] and _is_bar(leaf):
                    out.append(_bar_finding(path, k, jb[k], ja[k], ' (JSON configuration)'))
    if _match(path, RESULT_DOCS) and st in ('M', 'R') and before is not None and not path.endswith('.py'):
        if path.endswith('.json') and not type_changed and (_json_parses(before) != _json_parses(after)):
            raise CouldNotRun(f'{path}: only one side parses as JSON, so the recorded result cannot be compared')
        flips = _json_result_flips(before, after) if path.endswith('.json') and not type_changed else \
            (_jsonl_result_flips(before, after) if path.endswith('.jsonl') else None)
        if flips is not None:
            for p, bv, av in flips:
                out.append(_f('RESULT_STATUS_FLIPPED_TO_PASS', 'high', path,
                              f'{p}: {json.dumps(bv)} -> {"(removed)" if av in (None, "__ABSENT__") else json.dumps(av)}'))
        else:
            _CSV_MODE[0] = path.endswith('.csv')
            for old_ln, new_ln in _text_result_flips(before, after):
                out.append(_f('RESULT_STATUS_FLIPPED_TO_PASS', 'high', path,
                              'a recorded failure was rewritten as a success' if new_ln is not None else
                              'a recorded failure row was deleted', before=old_ln.strip()[:160],
                              after=(new_ln or '').strip()[:160]))
    return out


def _judge_tests(path, st, before, after, ctx):
    out = []
    tb = _tests_in(before) if before else {}
    ta = _tests_in(after)
    if ta is None:
        return [_f('TEST_MODULE_UNPARSEABLE', 'high', path, 'the test module no longer parses')]
    if tb is None:
        raise CouldNotRun(f'{path}: the base version does not parse, so its tests cannot be compared')
    moved_in = ctx.get('tests_after', {})            # every test function in every changed module, after
    for name, b in tb.items():
        a = ta.get(name)
        if a is None:
            # a body-identical rename here, or the same test (as strong) in another changed module, is not a removal
            same_body = [k for k, v in ta.items() if v['body'] == b['body'] and k not in tb
                         and ('.' in k) == ('.' in name)]   # into a class or out of test_* is not a rename
            elsewhere = [m for m, tests in moved_in.items() if m != path and name in tests
                         and tests[name]['n_checks'] >= b['n_checks'] and tests[name]['vacuous'] <= b['vacuous']]
            if same_body or elsewhere:
                continue
            out.append(_f('TEST_FUNCTION_REMOVED', 'high', path, f'{name} was removed, renamed or shadowed',
                          n_checks_before=b['n_checks']))
            continue
        if a['n_checks'] < b['n_checks']:
            out.append(_f('CHECKS_REDUCED', 'high', path, f'{name}: {b["n_checks"]} -> {a["n_checks"]} checks'))
        if a['trivial'] and not b['trivial']:
            out.append(_f('TEST_BODY_EMPTIED', 'high', path, f'{name} now does nothing'))
        if a['early_return'] > b['early_return']:
            out.append(_f('TEST_EARLY_RETURN', 'high', path, f'{name} now returns before its checks have run'))
        if a['vacuous'] > b['vacuous']:
            out.append(_f('CONSTANT_TRUE_CHECK_ADDED', 'medium', path,
                          f'{name}: {a["vacuous"] - b["vacuous"]} check(s) whose condition is true whatever the code '
                          f'does', n_before=b['vacuous'], n_after=a['vacuous']))
        gone, new_sigs = b['sigs'] - a['sigs'], a['sigs'] - b['sigs']
        tightened = 0
        for g in list(gone):
            for ns in list(new_sigs):
                d = next((_bound_direction(db, da) for db in b['details'].get(g, ()) for da in a['details'].get(ns, ())
                          if _bound_direction(db, da)), None)
                if d == 'tighter':
                    tightened += 1
                    gone[g] -= 1
                    new_sigs[ns] -= 1
                    gone, new_sigs = +gone, +new_sigs
                    break
        if tightened:
            out.append(_f('TEST_COMPARISON_TIGHTENED', 'info', path, f'{name}: {tightened} bound(s) made stricter'))
        if gone:
            out.append(_f('TEST_COMPARISON_NUMBER_CHANGED', 'medium', path,
                          f'{name}: {sum(gone.values())} comparison(s) removed, loosened or altered (operator, number '
                          f'or tripwire condition)', gone=[list(map(str, g)) for g in list(gone)[:6]]))
        tb_tol = collections.Counter(b['tols'])
        ta_tol = collections.Counter(a['tols'])
        lost, new = tb_tol - ta_tol, ta_tol - tb_tol
        for (callee, kw, vb) in lost:
            match = [x for x in new if x[0] == callee and x[1] == kw]
            if match:
                out.append(_bar_finding(path, f'{name}: {callee}({kw}=)', vb, match[0][2], ' (test tolerance)'))
                if out[-1]['rule'] == 'THRESHOLD_LOOSENED':
                    out[-1]['rule'] = 'TEST_COMPARISON_NUMBER_CHANGED'
            else:
                out.append(_f('TEST_COMPARISON_NUMBER_CHANGED', 'medium', path, f'{name}: tolerance {kw}={vb} removed'))
    hb, ha = _helpers(before or ''), _helpers(after)
    for h in sorted(set(hb) & set(ha)):
        if ha[h][1] < hb[h][1]:
            out.append(_f('CHECKS_REDUCED', 'high', path, f'the module\'s {h}() helper no longer records a failure '
                                                          f'({hb[h][1]} -> {ha[h][1]}): every check through it passes'))
        elif ha[h][0] != hb[h][0]:
            out.append(_f('CHECK_HELPER_CHANGED', 'medium', path, f'the module\'s {h}() helper changed'))
    for h in sorted(set(hb) - set(ha)):
        out.append(_f('CHECK_HELPER_CHANGED', 'medium', path, f'the module\'s {h}() helper was removed or replaced'))
    sb, sa = _skips(before or ''), _skips(after)
    if sa > sb:
        # in an EXISTING module a new skip lowers a bar that was there; in a NEW module it is a declared BLOCKED
        # path the runner already reports as BLOCKED FUNCTIONS (info, not a finding)
        new_lines = [ln for ln in _skip_lines(after) if ln not in set(_skip_lines(before or ''))]
        out.append(_f('SKIP_ADDED', 'high' if st != 'A' else 'info', path,
                      f'{sa - sb} skip path(s) added' + (' (new module)' if st == 'A' else ''),
                      lines=new_lines[:5]))
    return out


def run(repo, base, head='HEAD', worktree=False):
    if APPROVAL_NAME is None:
        raise CouldNotRun(f'the shared protected-path list could not be imported ({_SHARED_LIST})')
    repo = pathlib.Path(repo).resolve()
    head_ref = None if worktree else head
    _git(repo, 'rev-parse', '--verify', f'{base}^{{commit}}')
    if head_ref:
        _git(repo, 'rev-parse', '--verify', f'{head_ref}^{{commit}}')
    mb = merge_base(repo, base, head_ref)            # what the change did, not what base gained meanwhile
    findings = []
    files = changed_files(repo, mb, head_ref)
    ctx = {'tests_after': {}, 'constants_after': {}}
    for st, old, new in files:
        if st != 'D' and new.endswith('.py'):
            src = _show(repo, head_ref, new)
            if _match(new, TEST_FILE):
                t = _tests_in(src)
                if t:
                    ctx['tests_after'][new] = t
            ctx['constants_after'][new] = _constants(src or '')
    for st, old, new in files:
        findings.extend(judge_file(repo, mb, head_ref, st, old, new, ctx))
    counted = [f for f in findings if f['severity'] in ('high', 'medium')]
    by_rule = {}
    for f in findings:
        by_rule[f['rule']] = by_rule.get(f['rule'], 0) + 1
    return {'ARTIFACT': 'FLOOR_GUARD_REPORT', 'spec_version': SPEC_VERSION, 'enforcement': ENFORCEMENT,
            'repo': str(repo), 'base': base, 'head': 'WORKTREE' if worktree else head,
            'base_sha': _git(repo, 'rev-parse', base).strip(), 'merge_base_sha': mb,
            'head_sha': None if worktree else _git(repo, 'rev-parse', head).strip(),
            'n_files_changed': len(files), 'n_findings': len(counted), 'n_info': len(findings) - len(counted),
            'by_rule': by_rule, 'verdict': 'FINDINGS' if counted else 'CLEAN', 'findings': findings,
            'NOT_A_VERDICT_ON_THE_CHANGE': 'a finding says the bar may have moved; an owner record can authorize it'}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--base', required=True)
    ap.add_argument('--head', default='HEAD')
    ap.add_argument('--worktree', action='store_true', help='compare base to the working tree (uncommitted)')
    ap.add_argument('--repo', default='.')
    ap.add_argument('--json')
    a = ap.parse_args(argv)
    try:
        rep = run(a.repo, a.base, a.head, a.worktree)
    except Exception as e:  # noqa: BLE001 -- CouldNotRun or an internal error: never a 0 or a 1
        print(_safe(f'FLOOR_GUARD NOT_EXECUTED (exit 2): {type(e).__name__}: {e}'), file=sys.stderr)
        if a.json:
            pathlib.Path(a.json).write_text(json.dumps({'verdict': 'NOT_EXECUTED', 'why': f'{type(e).__name__}: {e}'})
                                            + '\n')
        return 2
    if a.json:
        pathlib.Path(a.json).write_text(json.dumps(rep, indent=1, default=str) + '\n')
    print(f"FLOOR_GUARD {rep['verdict']} [{ENFORCEMENT}] {rep['n_findings']} finding(s) "
          f"(+{rep['n_info']} info) over {rep['n_files_changed']} file(s) {rep['by_rule']}")
    for f in rep['findings']:
        if f['severity'] != 'info':
            print(f"  {f['severity']:6} {f['rule']:34} {f['path']}  {f['detail']}")
    return 1 if rep['verdict'] == 'FINDINGS' else 0


if __name__ == '__main__':
    sys.exit(main())
