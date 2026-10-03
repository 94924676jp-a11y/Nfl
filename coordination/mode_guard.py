#!/usr/bin/env python3.12
"""OWNER RULE 3 (2026-10-02): the prospective mode boundary, as a Claude Code PreToolUse hook.

Registered in .claude/settings.json on Edit|Write|Bash. Reads the hook's JSON from stdin, derives
the paths the tool is about to write, judges them with the SAME judge the retrospective check uses
(coordination/orchestrator/locks.mode_boundary over coordination/MODE_POLICY.json), and returns
`permissionDecision: deny` with the reason when the mode in force forbids the write. No mode in
force -> no decision (the retrospective check reports NOT_EXECUTED; this hook cannot invent a mode).

Pipe-test:  echo '{"tool_name":"Write","tool_input":{"file_path":"nfl/sim/game.py"},"cwd":"."}' \\
            | NFL_PROJECT_STATE=<state with mode OPERATE> python3.12 coordination/mode_guard.py
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import shlex
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_BASH_WRITE = re.compile(
    r'(?:>>?\s*|\btee\s+(?:-a\s+)?|\bsed\s+-i[^\s]*\s+(?:\'[^\']*\'|"[^"]*"|\S+)\s+|\brm\s+(?:-\w+\s+)*|'
    r'\bmv\s+(?:-\w+\s+)*\S+\s+|\bcp\s+(?:-\w+\s+)*\S+\s+|\bgit\s+checkout\s+--\s+|\btouch\s+|\bmkdir\s+(?:-p\s+)?)'
    r'([^\s;&|>]+)')


def _rel(path: str, cwd: str | None) -> str | None:
    if not path or path.startswith(('-', '$', '/dev/')):
        return None
    p = pathlib.Path(path)
    if not p.is_absolute():
        p = pathlib.Path(cwd or os.getcwd()) / p
    try:
        return str(p.resolve().relative_to(ROOT))
    except ValueError:
        return None  # outside the repository: not this guard's business


def targets(tool_name: str, tool_input: dict, cwd: str | None) -> list[str]:
    if tool_name in ('Edit', 'Write', 'MultiEdit', 'NotebookEdit'):
        r = _rel(tool_input.get('file_path') or tool_input.get('notebook_path') or '', cwd)
        return [r] if r else []
    if tool_name == 'Bash':
        cmd = tool_input.get('command') or ''
        out = []
        for m in _BASH_WRITE.finditer(cmd):
            tok = m.group(1).strip('\'"')
            r = _rel(tok, cwd)
            if r:
                out.append(r)
        # `python3.12 some_tool.py` writing files is invisible here; the retrospective check covers it.
        return sorted(set(out))
    return []


def diff_of(tool_name: str, tool_input: dict) -> str:
    if tool_name == 'Edit':
        return '\n'.join(f'+{ln}' for ln in (tool_input.get('new_string') or '').splitlines())
    if tool_name == 'Write':
        return '\n'.join(f'+{ln}' for ln in (tool_input.get('content') or '').splitlines())
    return ''


def decide(payload: dict) -> dict | None:
    from coordination import mode as M
    from coordination.orchestrator import locks as L
    cur = M.read()
    if not cur['mode']:
        return None
    tool = payload.get('tool_name') or ''
    ti = payload.get('tool_input') or {}
    paths = targets(tool, ti, payload.get('cwd'))
    if not paths and not diff_of(tool, ti):
        return None
    o = L.mode_boundary(paths, cur['mode'], diff=diff_of(tool, ti))
    if o['state'] != 'VIOLATED':
        return None
    why = '; '.join(f'{v["path"]} ({v["rule"]} {v["pattern"]})' for v in o['violations'][:6])
    return {'hookSpecificOutput': {
        'hookEventName': 'PreToolUse', 'permissionDecision': 'deny',
        'permissionDecisionReason': (
            f'MODE_BOUNDARY_VIOLATED: project mode is {cur["mode"]} ({cur["source"]}); this write '
            f'is outside what that mode may touch: {why}. Change the mode with '
            f'`python3.12 coordination/mode.py set <MODE> --reason ...` if the work is legitimate, '
            f'or do it in the right mode.')}}


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:  # noqa: BLE001
        return 0
    try:
        d = decide(payload)
    except Exception as e:  # noqa: BLE001
        # a guard that crashes must not silently allow: say so on stderr, deny nothing, and let the
        # retrospective check catch it. (exit 2 would block every tool call on a broken guard.)
        print(f'mode_guard: NOT_EXECUTED {type(e).__name__}: {e}', file=sys.stderr)
        return 0
    if d:
        print(json.dumps(d))
    return 0


if __name__ == '__main__':
    sys.exit(main())
