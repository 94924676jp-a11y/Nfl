#!/usr/bin/env python3.12
"""Replay every real tool call recorded in a session transcript through git_guard, and through the OLD and NEW
mode_guard entry points, in-process.

    PYTHONPATH=. python3.12 replay_real_tool_calls.py TRANSCRIPT.jsonl BASE_MODE_GUARD.py OUT.json

Measures, on real work rather than fixtures:
  * how many real calls git_guard classifies as protected (each one is listed for manual classification);
  * whether the hook's stdout differs between the base mode_guard.py and the Phase 1 one for any call
    (it must not: git_guard is REPORT_ONLY).
Paths in the transcript are judged against this worktree; the mode in force is the repository's own
(PROJECT_STATE), as a live session would see it. Nothing is executed: the hook classifies, it does not run commands.
"""
import collections
import contextlib
import importlib.util
import io
import json
import os
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


def calls(transcript):
    seen = set()
    for ln in open(transcript):
        try:
            d = json.loads(ln)
        except ValueError:
            continue
        msg = d.get('message') or {}
        for c in msg.get('content') or [] if isinstance(msg.get('content'), list) else []:
            if isinstance(c, dict) and c.get('type') == 'tool_use':
                name, ti = c.get('name'), c.get('input') or {}
                if name in ('Bash', 'Write', 'Edit', 'MultiEdit', 'NotebookEdit') or str(name).startswith('mcp__github__'):
                    key = c.get('id')
                    if key in seen:
                        continue
                    seen.add(key)
                    yield {'tool_name': name, 'tool_input': ti, 'cwd': str(ROOT)}


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def hook_stdout(mod, payload):
    buf = io.StringIO()
    saved = sys.stdin
    try:
        sys.stdin = io.StringIO(json.dumps(payload))
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
            rc = mod.main()
    finally:
        sys.stdin = saved
    return rc, buf.getvalue()


def main(transcript, base_guard, out):
    os.environ['NFL_GUARD_REPORT_LOG'] = str(pathlib.Path(out).with_suffix('.guard_log.jsonl'))
    from coordination import git_guard as GG
    new = load(ROOT / 'coordination' / 'mode_guard.py', 'mode_guard_new')
    old = load(base_guard, 'mode_guard_old')
    # The base copy lives outside the worktree, so its own ROOT (parents[1] of its file) is wrong and every path
    # would resolve outside "the repository": it would never deny anything and the comparison would be vacuous.
    # Found 2026-10-11; every identity result before this line was made with that defect and is superseded.
    old.ROOT = new.ROOT
    assert old.ROOT == ROOT, (old.ROOT, ROOT)
    rows, flagged, differ = [], [], []
    denied_old = denied_new = 0
    by_tool = collections.Counter()
    t0 = time.time()
    for p in calls(transcript):
        by_tool[p['tool_name'] if not p['tool_name'].startswith('mcp__') else 'mcp__github__*'] += 1
        prot = [f for f in GG.classify(p) if f['protected']]
        if prot:
            flagged.append({'tool': p['tool_name'], 'summary': GG._summary(p), 'findings': prot})
        o, n = hook_stdout(old, p), hook_stdout(new, p)
        denied_old += '"deny"' in o[1]
        denied_new += '"deny"' in n[1]
        if o != n:
            differ.append({'tool': p['tool_name'], 'summary': GG._summary(p), 'old': o, 'new': n})
        rows.append(1)
    res = {'transcript': str(transcript), 'n_calls': len(rows), 'by_tool': dict(by_tool),
           'n_protected_flagged': len(flagged), 'flagged': flagged,
           'n_hook_stdout_differs_old_vs_new': len(differ), 'differ': differ[:50],
           'n_denied_by_base_mode_guard': denied_old, 'n_denied_by_phase1_mode_guard': denied_new,
           'IDENTITY_IS_INFORMATIVE': denied_old > 0,
           'seconds': round(time.time() - t0, 1),
           'per_call_ms': round(1000 * (time.time() - t0) / max(1, len(rows)) / 2, 2)}
    pathlib.Path(out).write_text(json.dumps(res, indent=1) + '\n')
    print(f"{res['n_calls']} real calls {res['by_tool']}; protected-flagged {len(flagged)}; "
          f"hook stdout differs old vs new: {len(differ)}; denied base/new {denied_old}/{denied_new}; "
          f"{res['per_call_ms']} ms/call/guard")


if __name__ == '__main__':
    main(*sys.argv[1:4])
