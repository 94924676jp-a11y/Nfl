#!/usr/bin/env python3.12
"""Floor guard: does a change make the bar easier to pass? REPORT-ONLY (owner Phase 1 approval, 2026-10-10).

    python3.12 nfl/tools/floor_guard.py --base REF [--head REF | --worktree] [--repo DIR] [--json OUT]

WHY. CLAUDE.md rule 1: "The goal is not to make the checklist green. The goal is to make a false green state
difficult to produce." The runner proves a guard fires (`bypass.py`) and that a test module counted its checks,
but nothing compared a CHANGE for the cheap road to green: a deleted test, a removed check, a skip, a loosened
tolerance, an edited certificate, a FAIL rewritten as PASS. This reads `git diff base..head` and reports each
such move with the file, the line and the evidence. Pattern adapted from addyosmani/agent-skills@1be8e34
(skills/constraint-driven-development/references/floor-guard.md, MIT), reimplemented for Python and this
repository's own conventions (check()/observe()/BLOCKED counters, certificates, ledgers, protected paths).

REPORT-ONLY. Nothing calls this as a gate. `ENFORCEMENT` below is a code constant, not configuration, so turning
it into a gate is a reviewed code change that needs the owner's approval; a test pins it to REPORT_ONLY.

EXIT CODES. 0 no finding; 1 at least one finding of severity high or medium; 2 COULD NOT RUN (bad ref, no merge
base, git failure). A 2 is never a 0: an unreadable diff is not a clean diff.

AUTHORIZATION. A finding is not a verdict that the change is wrong: an owner-approved tolerance change or a
corrected certificate is legitimate. But the guard records no authorization on its own: absent an owner record
the finding stands (`authorization: NONE_RECORDED`), and no file an agent writes can clear it.
"""
from __future__ import annotations

import argparse
import ast
import collections
import fnmatch
import json
import pathlib
import re
import subprocess
import sys

SPEC_VERSION = 'floor-guard-1'
ENFORCEMENT = 'REPORT_ONLY'          # owner approval required to change; pinned by nfl/tests/test_floor_guard.py

TEST_FILE = ('nfl/tests/test_*.py', 'nfl/tests/*/test_*.py', 'sportsplatform/*/test_*.py',
             'sportsplatform/*/*/test_*.py', 'v7/test_*.py', 'v8/*/test_*.py')
#: the machinery that decides what counts as proof
VERIFICATION_MACHINERY = ('nfl/tests/run_suite.py', 'nfl/tests/_controls.py', 'nfl/tests/_registry.py',
                          'nfl/tests/bypass.py', 'nfl/tests/certify_suite.py', 'nfl/tests/DETECTORS.json',
                          'nfl/tests/DETECTOR_VALIDATION.json')
#: owner-authority files and the safeguards themselves
GOVERNANCE = ('coordination/OWNER_DECISIONS.md', 'coordination/AUTOMATION_POLICY.json',
              'coordination/MODE_POLICY.json', 'coordination/orchestrator/MODELS.json',
              'nfl/production/authorization.py', 'nfl/production/review/gate.py', '.github/workflows/*',
              'coordination/mode_guard.py', 'coordination/git_guard.py', 'coordination/mode.py',
              'coordination/orchestrator/locks.py', 'nfl/tools/floor_guard.py', '.claude/settings.json',
              '.claude/settings.local.json', 'CLAUDE.md')
#: artifacts that are written once: a modification or deletion is a finding, an addition is not
FROZEN = ('nfl/tests/certificates/*', '*SEAL*.json', '*FREEZE*.json', '*FREEZE*.md',
          'nfl/vintage/*', '*/baseline_*/*', 'nfl/dfs/salaries/classic_early_*/research_projection/rebuild_*/*',
          'nfl/postgame/*/PREGAME_FREEZE_MANIFEST.json', '*RUN_RECEIPT*.json')
#: append-only logs and manifests: lines may be added at the end, never changed or removed. A SHA256SUMS or a
#: .jsonl inside a frozen directory grows when an artifact is added beside the sealed ones (measured on the
#: 120-commit history, 2026-10-10: three such appends, no hash changed), so it is judged as append-only, not frozen.
APPEND_ONLY = ('*LEDGER*.jsonl', '*_manifest.jsonl', 'coordination/HANDOFF_LOG.jsonl', '*SEAL_HISTORY*.jsonl',
               '*/SHA256SUMS', 'nfl/vintage/*.jsonl')
#: result documents where a status word flipping toward success is a finding
RESULT_DOCS = ('*.json', '*.md', '*.txt', '*.csv')

TOL_LOOSER_WHEN_LARGER = re.compile(r'(TOL|TOLERANCE|EPS|EPSILON|MARGIN|SLACK|MAX_|_MAX\b|LIMIT|CAP\b|_CAP_|'
                                    r'SE_MULTIPLE|ALLOW|MAX$)', re.I)
TOL_LOOSER_WHEN_SMALLER = re.compile(r'(MIN_|_MIN\b|FLOOR|MIN$|REQUIRED|AT_LEAST)', re.I)
THRESHOLD_NAME = re.compile(r'(TOL|TOLERANCE|EPS|EPSILON|MARGIN|SLACK|THRESHOLD|MIN_|_MIN\b|MAX_|_MAX\b|LIMIT|'
                            r'CAP\b|_CAP_|FLOOR|CEIL|SE_MULTIPLE|ALPHA|LEVEL|BAR\b|_BAR_|MAJORITY|QUOTA)', re.I)
SKIP_LINE = re.compile(r'(pytest\.skip|mark\.skip|mark\.xfail|unittest\.skip|skipTest|raise\s+SkipTest|'
                       r'\bBLOCKED\s*\+=|\bSKIPPED\s*\+=|blocked_count\s*\+=)')
SUPPRESS_LINE = re.compile(r'(#\s*noqa|#\s*type:\s*ignore|#\s*pragma:\s*no\s*cover|#\s*nosec)')
#: DECLARED EXEMPTION (not tuning): `# noqa: E402` marks an import placed after the repository's `sys.path` insert,
#: the house convention in every tool and test here. Import position says nothing about the strength of a check.
SUPPRESS_EXEMPT = re.compile(r'#\s*noqa:\s*E402\s*$')
FAIL_WORDS = re.compile(r'\b(FAIL|FAILED|FAILING|BLOCKED|UNVERIFIED|NOT_READY|NOT_EXECUTED|VIOLATED|REFUSED|'
                        r'STALE|MISSING)\b')
PASS_WORDS = re.compile(r'\b(PASS|PASSED|READY|VERIFIED|CLEAN|COMPLETE|OK)\b')
CHECK_CALLS = ('check', 'observe', 'assert_guard_is_load_bearing', 'assertTrue', 'assertEqual', 'assertIn',
               'assertFalse', 'assertRaises', 'assertAlmostEqual', 'assertIsNone', 'assertIsNotNone')


class CouldNotRun(RuntimeError):
    """The diff could not be read. Exit 2, never 0."""


def _match(path, patterns):
    return any(fnmatch.fnmatch(path, p) for p in patterns)


def _git(repo, *args, ok_codes=(0,)):
    r = subprocess.run(['git', '-C', str(repo), *args], capture_output=True, text=True)
    if r.returncode not in ok_codes:
        raise CouldNotRun(f'git {" ".join(args)} -> {r.returncode}: {r.stderr.strip()[:300]}')
    return r.stdout


def _show(repo, ref, path):
    if ref is None:                                     # working tree
        p = pathlib.Path(repo) / path
        return p.read_text(errors='replace') if p.exists() else None
    r = subprocess.run(['git', '-C', str(repo), 'show', f'{ref}:{path}'], capture_output=True, text=True,
                       errors='replace')
    return r.stdout if r.returncode == 0 else None


def changed_files(repo, base, head):
    """[(status, old_path, new_path)] with renames detected."""
    args = ['diff', '--name-status', '-M', '--no-color', base] + ([head] if head else [])
    out = []
    for ln in _git(repo, *args).splitlines():
        parts = ln.split('\t')
        st = parts[0][0]
        if st == 'R':
            out.append(('R', parts[1], parts[2]))
        else:
            out.append((st, parts[1], parts[1]))
    return out


# ------------------------------------------------------------------ python structure
def _tests_in(src):
    """{test function name: (n_checks, first_stmt_kind, n_compare_numbers, body_is_trivial, numbers)}"""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return None
    out = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith('test'):
            n_checks, numbers, const_true = 0, [], 0
            for sub in ast.walk(node):
                if isinstance(sub, ast.Assert):
                    n_checks += 1
                elif isinstance(sub, ast.Call):
                    fn = sub.func
                    name = fn.id if isinstance(fn, ast.Name) else fn.attr if isinstance(fn, ast.Attribute) else ''
                    if name in CHECK_CALLS:
                        n_checks += 1
                        if (name == 'check' and len(sub.args) >= 2 and isinstance(sub.args[1], ast.Constant)
                                and sub.args[1].value is True):
                            const_true += 1
                elif isinstance(sub, ast.Compare):
                    for c in [sub.left, *sub.comparators]:
                        if isinstance(c, ast.Constant) and isinstance(c.value, (int, float)) \
                                and not isinstance(c.value, bool):
                            numbers.append(c.value)
            body = [b for b in node.body if not (isinstance(b, ast.Expr) and isinstance(b.value, ast.Constant))]
            first = type(body[0]).__name__ if body else 'EMPTY'
            trivial = (not body) or all(isinstance(b, ast.Pass) for b in body)
            out[node.name] = {'n_checks': n_checks, 'first': first, 'trivial': trivial,
                              'numbers': sorted(numbers), 'const_true_checks': const_true,
                              'early_return': bool(body) and isinstance(body[0], ast.Return)}
    return out


def _constants(src):
    """{NAME: number} for module- and class-level numeric assignments whose name reads as a threshold."""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return {}
    out = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            val = node.value
            if isinstance(val, ast.UnaryOp) and isinstance(val.op, ast.USub) and isinstance(val.operand, ast.Constant):
                num = -val.operand.value if isinstance(val.operand.value, (int, float)) else None
            elif isinstance(val, ast.Constant) and isinstance(val.value, (int, float)) and not isinstance(val.value, bool):
                num = val.value
            else:
                num = None
            if num is None:
                continue
            for t in targets:
                if isinstance(t, ast.Name) and THRESHOLD_NAME.search(t.id):
                    out[t.id] = num
    return out


def _suppressions(lines):
    return sum(1 for ln in lines if SUPPRESS_LINE.search(ln) and not SUPPRESS_EXEMPT.search(ln))


def _broad_except_pass(src):
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return 0
    n = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            broad = node.type is None or (isinstance(node.type, ast.Name) and node.type.id in ('Exception', 'BaseException'))
            if broad and all(isinstance(b, (ast.Pass, ast.Continue)) for b in node.body):
                n += 1
    return n


def _diff_lines(repo, base, head, path):
    args = ['diff', '--no-color', '-U0', base] + ([head] if head else []) + ['--', path]
    added, removed, pairs = [], [], []
    rem_buf = []
    for ln in _git(repo, *args).splitlines():
        if ln.startswith('+++') or ln.startswith('---'):
            continue
        if ln.startswith('@@'):
            rem_buf = []
            continue
        if ln.startswith('-'):
            removed.append(ln[1:])
            rem_buf.append(ln[1:])
        elif ln.startswith('+'):
            added.append(ln[1:])
            if rem_buf:
                pairs.append((rem_buf.pop(0), ln[1:]))
    return added, removed, pairs


# ------------------------------------------------------------------ rules
def _f(rule, severity, path, detail, **ev):
    return {'rule': rule, 'severity': severity, 'path': path, 'detail': detail, 'evidence': ev,
            'authorization': 'NONE_RECORDED'}


def judge_file(repo, base, head, st, old, new):
    out = []
    path = new
    is_test = _match(path, TEST_FILE) or _match(old, TEST_FILE)
    before = _show(repo, base, old) if st != 'A' else None
    after = _show(repo, head, new) if st != 'D' else None

    if st == 'D' and is_test:
        out.append(_f('TEST_FILE_DELETED', 'high', old, 'a test module was deleted'))
    if _match(path, GOVERNANCE) or _match(old, GOVERNANCE):
        out.append(_f('GOVERNANCE_OR_SAFEGUARD_CHANGED', 'high', path,
                      'an owner-authority file or a safeguard itself changed', status=st))
    if (_match(path, VERIFICATION_MACHINERY) or _match(old, VERIFICATION_MACHINERY)) and st != 'A':
        sev, detail = 'high', 'the machinery that decides what counts as proof changed'
        if path.endswith('DETECTORS.json') and before is not None and after is not None:
            def ids(doc):
                rows = doc.get('detectors') if isinstance(doc, dict) else doc
                return {r.get('detector') if isinstance(r, dict) else str(r) for r in (rows or [])}
            try:
                bk, ak = ids(json.loads(before)), ids(json.loads(after))
            except (ValueError, AttributeError):
                bk = ak = None
            if bk is not None and ak is not None:
                if bk - ak:
                    detail = f'{len(bk - ak)} detector(s) removed: {sorted(bk - ak)[:5]}'
                else:
                    sev, detail = 'info', f'detectors only added ({len(ak - bk)})'
        out.append(_f('VERIFICATION_MACHINERY_CHANGED', sev, path, detail, status=st))
    if st in ('M', 'D', 'R') and _match(old, FROZEN) and not _match(old, APPEND_ONLY):
        out.append(_f('FROZEN_ARTIFACT_MODIFIED', 'high', old, 'a write-once artifact was modified or deleted',
                      status=st))
    if st in ('M', 'D') and _match(old, APPEND_ONLY):
        if st == 'D':
            out.append(_f('APPEND_ONLY_LOG_REWRITTEN', 'high', old, 'an append-only log was deleted'))
        elif before is not None and after is not None:
            # append-only means no existing line was removed or changed; a sorted manifest (SHA256SUMS) inserts new
            # lines in order, which is still only an addition
            gone = collections.Counter(before.splitlines()) - collections.Counter(after.splitlines())
            if gone:
                out.append(_f('APPEND_ONLY_LOG_REWRITTEN', 'high', old,
                              f'{sum(gone.values())} existing line(s) removed or changed in an append-only file',
                              example=next(iter(gone))[:160]))

    if st == 'D' or after is None:
        return out
    try:
        added, removed, pairs = _diff_lines(repo, base, head, new) if st != 'R' else ([], [], [])
    except CouldNotRun:
        added, removed, pairs = [], [], []

    if path.endswith('.py'):
        if is_test:
            tb = _tests_in(before) if before else {}
            ta = _tests_in(after)
            if ta is None:
                out.append(_f('TEST_MODULE_UNPARSEABLE', 'high', path, 'the test module no longer parses'))
            elif tb:
                for name, b in tb.items():
                    a = ta.get(name)
                    if a is None:
                        out.append(_f('TEST_FUNCTION_REMOVED', 'high', path, f'{name} was removed or renamed',
                                      n_checks_before=b['n_checks']))
                        continue
                    if a['n_checks'] < b['n_checks']:
                        out.append(_f('CHECKS_REDUCED', 'high', path, f'{name}: {b["n_checks"]} -> {a["n_checks"]} checks'))
                    if a['trivial'] and not b['trivial']:
                        out.append(_f('TEST_BODY_EMPTIED', 'high', path, f'{name} now does nothing'))
                    if a['early_return'] and not b['early_return']:
                        out.append(_f('TEST_EARLY_RETURN', 'high', path, f'{name} now returns before testing'))
                    if a['const_true_checks'] > b['const_true_checks']:
                        out.append(_f('CONSTANT_TRUE_CHECK_ADDED', 'medium', path,
                                      f'{name}: check(label, True) added; a constant condition proves nothing',
                                      n_before=b['const_true_checks'], n_after=a['const_true_checks']))
                    # a number the test compared against was removed or altered (a NEW comparison adds numbers
                    # and is not a finding: measured false positive on the 'add a check' fixture, 2026-10-10)
                    gone = collections.Counter(b['numbers']) - collections.Counter(a['numbers'])
                    if gone:
                        out.append(_f('TEST_COMPARISON_NUMBER_CHANGED', 'medium', path,
                                      f'{name}: compared-against number(s) removed or altered: {sorted(gone)[:8]}',
                                      before=b['numbers'][:12], after=a['numbers'][:12]))
            for ln in added:
                if SKIP_LINE.search(ln):
                    # in an EXISTING module a new skip lowers a bar that was there; in a NEW module it is a declared
                    # BLOCKED path the runner already reports as BLOCKED FUNCTIONS (info, not a finding)
                    out.append(_f('SKIP_ADDED', 'high' if st != 'A' else 'info', path,
                                  'a skip, xfail or BLOCKED increment was added' + (' (new module)' if st == 'A' else ''),
                                  line=ln.strip()[:160]))
        cb, ca = _constants(before or ''), _constants(after)
        for name in sorted(set(cb) & set(ca)):
            if cb[name] == ca[name]:
                continue
            looser = ((TOL_LOOSER_WHEN_LARGER.search(name) and abs(ca[name]) > abs(cb[name])) or
                      (TOL_LOOSER_WHEN_SMALLER.search(name) and ca[name] < cb[name]))
            tighter = ((TOL_LOOSER_WHEN_LARGER.search(name) and abs(ca[name]) < abs(cb[name])) or
                       (TOL_LOOSER_WHEN_SMALLER.search(name) and ca[name] > cb[name]))
            rule, sev = (('THRESHOLD_LOOSENED', 'high') if looser else ('THRESHOLD_TIGHTENED', 'info') if tighter
                         else ('THRESHOLD_CHANGED', 'medium'))
            out.append(_f(rule, sev, path, f'{name}: {cb[name]} -> {ca[name]}'))
        for name in sorted(set(cb) - set(ca)):
            out.append(_f('THRESHOLD_REMOVED', 'medium', path, f'{name} = {cb[name]} no longer defined'))
        nb, na = _broad_except_pass(before or ''), _broad_except_pass(after)
        if na > nb:
            out.append(_f('BROAD_EXCEPT_PASS_ADDED', 'medium', path,
                          f'{na - nb} new `except: pass` (an error silenced is a failure hidden)'))
        n_sup = _suppressions(added) - _suppressions(removed)
        if n_sup > 0:
            # medium in test modules (a suppressed warning there can hide a broken check); info elsewhere. Measured
            # 2026-10-10: 261 suppressions added over 120 commits (209 E402, 27 E731, 18 BLE001), none tied to a
            # weakened check; outside tests they are code style, not the bar.
            out.append(_f('SUPPRESSION_ADDED', 'medium' if is_test else 'info', path,
                          f'{n_sup} new lint/type/coverage suppression(s)'))
    elif _match(path, RESULT_DOCS) and st == 'M':
        for old_ln, new_ln in pairs:
            ow, nw = set(FAIL_WORDS.findall(old_ln)), set(FAIL_WORDS.findall(new_ln))
            if ow - nw and PASS_WORDS.search(new_ln) and not PASS_WORDS.search(old_ln):
                out.append(_f('RESULT_STATUS_FLIPPED_TO_PASS', 'high', path,
                              'a recorded failure was rewritten as a success', before=old_ln.strip()[:160],
                              after=new_ln.strip()[:160]))
    return out


def run(repo, base, head='HEAD', worktree=False):
    repo = pathlib.Path(repo).resolve()
    head_ref = None if worktree else head
    _git(repo, 'rev-parse', '--verify', f'{base}^{{commit}}')
    if head_ref:
        _git(repo, 'rev-parse', '--verify', f'{head_ref}^{{commit}}')
    findings = []
    files = changed_files(repo, base, head_ref)
    for st, old, new in files:
        findings.extend(judge_file(repo, base, head_ref, st, old, new))
    counted = [f for f in findings if f['severity'] in ('high', 'medium')]
    by_rule = {}
    for f in findings:
        by_rule[f['rule']] = by_rule.get(f['rule'], 0) + 1
    return {'ARTIFACT': 'FLOOR_GUARD_REPORT', 'spec_version': SPEC_VERSION, 'enforcement': ENFORCEMENT,
            'repo': str(repo), 'base': base, 'head': 'WORKTREE' if worktree else head,
            'base_sha': _git(repo, 'rev-parse', base).strip(),
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
    except CouldNotRun as e:
        print(f'FLOOR_GUARD NOT_EXECUTED (exit 2): {e}', file=sys.stderr)
        if a.json:
            pathlib.Path(a.json).write_text(json.dumps({'verdict': 'NOT_EXECUTED', 'why': str(e)}) + '\n')
        return 2
    if a.json:
        pathlib.Path(a.json).write_text(json.dumps(rep, indent=1) + '\n')
    print(f"FLOOR_GUARD {rep['verdict']} [{ENFORCEMENT}] {rep['n_findings']} finding(s) "
          f"(+{rep['n_info']} info) over {rep['n_files_changed']} file(s) {rep['by_rule']}")
    for f in rep['findings']:
        if f['severity'] != 'info':
            print(f"  {f['severity']:6} {f['rule']:34} {f['path']}  {f['detail']}")
    return 1 if rep['verdict'] == 'FINDINGS' else 0


if __name__ == '__main__':
    sys.exit(main())
