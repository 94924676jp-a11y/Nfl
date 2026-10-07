#!/usr/bin/env python3.12
"""Authoritative-suite COMPLETION CERTIFICATE. A parent that does not trust its child's exit code.

    python3.12 nfl/tests/certify_suite.py [--timeout 7200] [--out nfl/tests/certificates/]
    python3.12 nfl/tests/certify_suite.py --root FIXTURE_ROOT --timeout 20 --out DIR   # sabotage fixtures

WHY. run_suite.py judges every module it reaches, but nothing judged whether it reached them all. On
2026-10-07 a module's import-time sys.exit(0) ended a 364-module run at module 12 with exit 0 and no
summary; a container shell that exited killed a background run with no terminal record at all. An exit
code is a claim by the process being audited. This supervisor is a separate process that:

  1. FREEZES the expected manifest before the run: every module the runner will discover (same globs),
     with the sha256 of each file, plus commit, dirty state, interpreter and dependency versions.
  2. Gives the child a FRESH progress file (NFL_SUITE_PROGRESS), so no record from another run can count.
  3. Runs the child under a timeout and records its exit status, including death by signal.
  4. Reads the child's records and requires, by IDENTITY not by count:
       - every line parses (a torn final line is TRUNCATED_RECORD);
       - exactly one run_id, the child's (anything else is FOREIGN_OR_STALE_RECORDS);
       - one suite_start whose n_modules equals the manifest;
       - module_done for every expected module, exactly once (MISSING_MODULES / DUPLICATE_MODULE_RECORDS;
         a duplicate plus a missing module preserves the count and is still caught);
       - no record for a module outside the manifest (UNEXPECTED_MODULES);
       - a terminal suite_done, whose verdict agrees with the exit code and the printed SUITE line;
       - a nonzero number of executed checks;
       - the manifest files unchanged after the run (MANIFEST_CHANGED_DURING_RUN).
  5. Writes a certificate whose verdict is one of
       CERTIFIED_COMPLETE        -- complete, and the suite passed;
       FAILED                    -- complete (every identity check holds), and the suite failed;
       INCOMPLETE_NOT_CERTIFIED  -- anything else, INCLUDING exit code 0 without proof of completion.
     Exit codes 0 / 1 / 4 respectively.

The certificate certifies COMPLETION and the runner's verdict. It does not re-judge a module's checks:
that is run_suite.py's job, and duplicating its logic here would give two judges that can disagree.
"""
from __future__ import annotations

import collections
import datetime as dt
import glob
import hashlib
import json
import os
import pathlib
import platform
import re
import signal
import subprocess
import sys
import time

_REPO = pathlib.Path(__file__).resolve().parents[2]

CERTIFIED, FAILED, INCOMPLETE = 'CERTIFIED_COMPLETE', 'FAILED', 'INCOMPLETE_NOT_CERTIFIED'
EXIT = {CERTIFIED: 0, FAILED: 1, INCOMPLETE: 4}


def _sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def discover(root):
    """The runner's own discovery (run_suite.main): nfl/tests/test_*.py then sportsplatform/**/test_*.py."""
    root = pathlib.Path(root)
    cwd = os.getcwd()
    try:
        os.chdir(root)
        files = (sorted(glob.glob('nfl/tests/test_*.py'))
                 + sorted(glob.glob('sportsplatform/**/test_*.py', recursive=True)))
    finally:
        os.chdir(cwd)
    return files


def manifest(root):
    files = discover(root)
    m = {f: _sha(pathlib.Path(root) / f) for f in files}
    return m, hashlib.sha256(json.dumps(m, sort_keys=True).encode()).hexdigest()


def _git(root, *a):
    try:
        return subprocess.run(['git', *a], cwd=root, capture_output=True, text=True, timeout=30).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return None


def _porcelain(root):
    """`git status --porcelain` lines, NOT stripped: the leading space is part of the two-letter status code."""
    try:
        out = subprocess.run(['git', 'status', '--porcelain'], cwd=root, capture_output=True, text=True, timeout=60).stdout
    except (OSError, subprocess.TimeoutExpired):
        return []
    return [l for l in out.splitlines() if l.strip()]


def environment(root):
    deps = {}
    for mod in ('numpy', 'pandas'):
        r = subprocess.run([sys.executable, '-c', f'import {mod}; print({mod}.__version__)'], capture_output=True,
                           text=True, env=os.environ)
        deps[mod] = r.stdout.strip() if r.returncode == 0 else 'NOT_IMPORTABLE'
    status = _git(root, 'status', '--porcelain')
    return {'commit': _git(root, 'rev-parse', 'HEAD'), 'branch': _git(root, 'rev-parse', '--abbrev-ref', 'HEAD'),
            'dirty_entries': None if status is None else len([l for l in status.splitlines() if l.strip()]),
            'shallow_clone': _git(root, 'rev-parse', '--is-shallow-repository'),
            'python': platform.python_version(), 'executable': sys.executable, 'dependencies': deps,
            'PYTHONPATH': os.environ.get('PYTHONPATH')}


def read_records(path):
    """Parse the child's progress file. Returns (records, problems)."""
    probs = []
    raw = pathlib.Path(path).read_bytes() if pathlib.Path(path).exists() else b''
    if not raw:
        return [], ['NO_PROGRESS_RECORDS: the child wrote nothing']
    if not raw.endswith(b'\n'):
        probs.append('TRUNCATED_RECORD: the last record has no terminating newline (torn write)')
    recs = []
    for n, line in enumerate(raw.decode('utf-8', errors='replace').splitlines(), 1):
        if not line.strip():
            continue
        try:
            recs.append(json.loads(line))
        except ValueError:
            probs.append(f'TRUNCATED_RECORD: line {n} does not parse: {line[:80]!r}')
    return recs, probs


def _nested(progress):
    """Nested runners launched by harness self-tests write here (NFL_SUITE_CERTIFY redirect). Reported, not judged."""
    p = pathlib.Path(str(progress) + '.nested.jsonl')
    if not p.exists():
        return {'file': None, 'run_ids': 0}
    ids = set()
    for line in p.read_text(errors='replace').splitlines():
        try:
            ids.add(json.loads(line).get('run_id'))
        except ValueError:
            pass
    return {'file': p.name, 'run_ids': len(ids), 'sha256': _sha(p)}


def failing_modules(done):
    """Modules the runner judged failing. OWN_PROCESS is a judged result (its own `failing` count decides);
    any result that is neither OK nor OWN_PROCESS (FAIL, NO_TALLY, IMPORT_ERROR, PROCESS_SCOPED_UNREADABLE, ...)
    is a failure. Counting OWN_PROCESS as a failure overstated the 2026-10-07 certified run by four modules."""
    bad = set()
    for r in done:
        res = r.get('result')
        if res == 'OWN_PROCESS':
            if r.get('failing'):
                bad.add(r['module'])
        elif res != 'OK':
            bad.add(r['module'])
    return sorted(bad)


def judge(expected, recs, rc, timed_out, stdout, manifest_after_ok):
    """Pure: the certificate verdict from the evidence. Every reason is named."""
    reasons = []
    run_ids = sorted({r.get('run_id') for r in recs})
    if len(run_ids) != 1:
        reasons.append(f'FOREIGN_OR_STALE_RECORDS: {len(run_ids)} run ids in a progress file written for one run {run_ids[:4]}')
    starts = [r for r in recs if r.get('phase') == 'suite_start']
    if len(starts) != 1:
        reasons.append(f'SUITE_START_COUNT {len(starts)} (expected 1)')
    elif starts[0].get('n_modules') != len(expected):
        reasons.append(f'SUITE_START_N_MODULES {starts[0].get("n_modules")} != manifest {len(expected)}')
    done = collections.Counter(r.get('module') for r in recs if r.get('phase') == 'module_done')
    started = collections.Counter(r.get('module') for r in recs if r.get('phase') == 'module_start')
    exp = set(expected)
    missing = sorted(exp - set(done))
    dup = sorted(m for m, n in done.items() if n > 1)
    unexpected = sorted((set(done) | set(started)) - exp)
    in_flight = sorted(m for m in started if m not in done)
    if missing:
        reasons.append(f'MISSING_MODULES {len(missing)}: {missing[:8]}'
                       + (f' (started, never finished: {in_flight[:4]})' if in_flight else ''))
    if dup:
        reasons.append(f'DUPLICATE_MODULE_RECORDS {dup[:8]}')
    if unexpected:
        reasons.append(f'UNEXPECTED_MODULES {unexpected[:8]}')
    ends = [r for r in recs if r.get('phase') == 'suite_done']
    verdict = None
    if len(ends) != 1:
        reasons.append(f'TERMINAL_RECORD_COUNT {len(ends)} (expected exactly 1 suite_done)')
    else:
        verdict = ends[0].get('verdict')
        if not ends[0].get('n_checks_executed'):
            reasons.append('ZERO_CHECKS_EXECUTED')
        if ends[0].get('n_modules') != len(expected):
            reasons.append(f'SUITE_DONE_N_MODULES {ends[0].get("n_modules")} != manifest {len(expected)}')
    if timed_out:
        reasons.append('TIMEOUT: the child was killed by the supervisor')
    elif rc is not None and rc < 0:
        reasons.append(f'KILLED_BY_SIGNAL {signal.Signals(-rc).name if -rc in signal.Signals._value2member_map_ else -rc}')
    printed = re.findall(r'^SUITE (PASS|FAIL|NOT_EXECUTED)', stdout or '', re.M)
    if verdict is not None:
        if printed[-1:] != [verdict]:
            reasons.append(f'PRINTED_VERDICT_DISAGREES {printed[-1:]} vs record {verdict}')
        want_rc = {'PASS': 0, 'FAIL': 1, 'NOT_EXECUTED': 3}.get(verdict)
        if rc != want_rc:
            reasons.append(f'EXIT_CODE_DISAGREES rc={rc} for verdict {verdict} (expected {want_rc})')
        if verdict == 'NOT_EXECUTED':
            reasons.append('RUNNER_VERDICT_NOT_EXECUTED')
    if not manifest_after_ok:
        reasons.append('MANIFEST_CHANGED_DURING_RUN: a test file was added, removed or edited while the suite ran')
    if reasons:
        return INCOMPLETE, reasons, verdict
    return (CERTIFIED if verdict == 'PASS' else FAILED), [], verdict


def certify(root=_REPO, timeout=7200, out_dir=None, runner_args=(), label='AUTHORITATIVE'):
    root = pathlib.Path(root).resolve()
    out_dir = pathlib.Path(out_dir or root / 'nfl/tests/certificates')
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    cert_id = f'{stamp}-{os.getpid()}'
    expected, msha = manifest(root)
    env_rec = environment(root)
    tree_before = set(_porcelain(root))
    progress = out_dir / f'SUITE_PROGRESS_{cert_id}.jsonl'
    log = out_dir / f'SUITE_LOG_{cert_id}.txt'
    if progress.exists():
        raise SystemExit(f'PROGRESS_FILE_EXISTS {progress}')
    env = dict(os.environ, NFL_SUITE_PROGRESS=str(progress), NFL_SUITE_CERTIFY='1')
    t0 = time.time()
    timed_out, rc = False, None
    with open(log, 'w') as fh:
        p = subprocess.Popen([sys.executable, '-u', str(root / 'nfl/tests/run_suite.py'), *runner_args], cwd=root,
                             env=env, stdout=fh, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            rc = p.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(p.pid, signal.SIGKILL)
            rc = p.wait()
    stdout = log.read_text(errors='replace')
    recs, rprobs = read_records(progress)
    after, msha_after = manifest(root)
    rel_out = str(out_dir.resolve().relative_to(root)) if out_dir.resolve().is_relative_to(root) else None
    tree_after = set(_porcelain(root))
    mutated = sorted(l[3:] for l in tree_after - tree_before if not (rel_out and l[3:].startswith(rel_out)))
    verdict, reasons, runner_verdict = judge(expected, recs, rc, timed_out, stdout, msha_after == msha)
    if rprobs:
        verdict, reasons = INCOMPLETE, rprobs + reasons
    done = [r for r in recs if r.get('phase') == 'module_done']
    end = next((r for r in recs if r.get('phase') == 'suite_done'), None)
    cert = {'ARTIFACT': 'SUITE_COMPLETION_CERTIFICATE', 'label': label, 'cert_id': cert_id,
            'VERDICT': verdict, 'reasons': reasons, 'runner_verdict': runner_verdict,
            'runner_run_id': (recs[0].get('run_id') if recs else None), 'runner_args': list(runner_args),
            'environment': env_rec, 'root': str(root),
            'manifest': {'n_modules': len(expected), 'sha256': msha, 'unchanged_after_run': msha_after == msha},
            'child': {'exit_code': rc, 'timed_out': timed_out, 'timeout_s': timeout, 'seconds': round(time.time() - t0, 1),
                      'log': log.name, 'log_sha256': _sha(log), 'progress': progress.name,
                      'progress_sha256': _sha(progress) if progress.exists() else None},
            'completed_modules': len({r.get('module') for r in done}),
            'nested_runs': _nested(progress),
            'TREE_MUTATED_BY_RUN': {'paths': mutated, 'n': len(mutated),
                                    'NOTE': 'working-tree entries that changed while the suite ran (outside the certificate '
                                            'directory). Reported, not a verdict reason: the mode-boundary judge in '
                                            'run_suite.py owns that rule.'},
            'terminal_record': end,
            'failing_modules': failing_modules(done),
            'module_results': {r['module']: {k: r.get(k) for k in ('result', 'n_fn', 'checks_ok', 'checks_failing')}
                               for r in done},
            'RULE': 'exit code 0 without a complete, identity-matched, terminal record is INCOMPLETE_NOT_CERTIFIED',
            'written_at': dt.datetime.now(dt.timezone.utc).isoformat()}
    cert['manifest']['modules'] = expected
    path = out_dir / f'SUITE_CERTIFICATE_{cert_id}.json'
    path.write_text(json.dumps(cert, indent=1, default=str))
    return path, cert


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default=str(_REPO))
    ap.add_argument('--timeout', type=float, default=7200)
    ap.add_argument('--out')
    ap.add_argument('--label', default='AUTHORITATIVE')
    ap.add_argument('runner_args', nargs='*', help='passed to run_suite.py (any restriction makes it non-authoritative)')
    a = ap.parse_args()
    lab = a.label if not a.runner_args else 'RESTRICTED_NOT_AUTHORITATIVE'
    p, c = certify(a.root, a.timeout, a.out, a.runner_args, lab)
    print(p)
    print(c['VERDICT'], json.dumps(c['reasons'])[:600])
    print(f"modules expected {c['manifest']['n_modules']} completed {c['completed_modules']} "
          f"failing {len(c['failing_modules'])} exit {c['child']['exit_code']} runner {c['runner_verdict']}")
    sys.exit(EXIT[c['VERDICT']])
