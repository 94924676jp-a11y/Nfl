"""OWNER RULE 3 (2026-10-02): explicit BUILD / VERIFY / OPERATE / RESEARCH modes in project state.

    python3.12 coordination/mode.py show
    python3.12 coordination/mode.py set BUILD --reason "..." [--slate NFL_W5_MAIN] [--by agent|owner]
    python3.12 coordination/mode.py check [--since <commit>]   # boundary over the diff + working tree

THE MODE LIVES IN coordination/PROJECT_STATE.json. Per that file's reading rule, `mode_declared`
is the owner's statement and pins the mode: an agent's `set` is refused while it is present.
`mode` (no suffix) is measured state and is written ONLY here, with a HANDOFF_LOG.jsonl row, so
every mode change is dated, attributed and reasoned. The policy table is
coordination/MODE_POLICY.json. Enforcement is `coordination/orchestrator/locks.enforce_mode_boundary`
(retrospective, over a changed-path set) and `coordination/mode_guard.py` (prospective, as a
PreToolUse hook on Edit|Write|Bash).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MODES = ('BUILD', 'VERIFY', 'OPERATE', 'RESEARCH')
POLICY_PATH = ROOT / 'coordination' / 'MODE_POLICY.json'


def state_path() -> pathlib.Path:
    return pathlib.Path(os.environ.get('NFL_PROJECT_STATE') or (ROOT / 'coordination' / 'PROJECT_STATE.json'))


def handoff_path() -> pathlib.Path:
    return pathlib.Path(os.environ.get('NFL_HANDOFF_LOG') or (ROOT / 'coordination' / 'HANDOFF_LOG.jsonl'))


def policy() -> dict:
    return json.loads(POLICY_PATH.read_text())


def read(doc: dict | None = None) -> dict:
    """The mode in force, and where it came from. mode_declared pins; mode is measured."""
    doc = doc if doc is not None else json.loads(state_path().read_text())
    declared = doc.get('mode_declared')
    if isinstance(declared, dict) and declared.get('mode') in MODES:
        return {'mode': declared['mode'], 'source': 'mode_declared', 'pinned': True, 'record': declared}
    if isinstance(declared, str) and declared in MODES:
        return {'mode': declared, 'source': 'mode_declared', 'pinned': True, 'record': {'mode': declared}}
    m = doc.get('mode')
    if isinstance(m, dict) and m.get('mode') in MODES:
        return {'mode': m['mode'], 'source': 'mode', 'pinned': False, 'record': m}
    return {'mode': None, 'source': None, 'pinned': False, 'record': None}


def _head() -> str | None:
    try:
        return subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True,
                              text=True, check=True).stdout.strip()
    except Exception:  # noqa: BLE001
        return None


def set_mode(mode: str, reason: str, by: str = 'agent', slate: str | None = None) -> dict:
    """Write the measured mode. Refused when the owner has pinned one. Logs a HANDOFF row."""
    if mode not in MODES:
        raise ValueError(f'MODE_UNKNOWN: {mode!r} is not one of {MODES}')
    if not (reason or '').strip():
        raise ValueError('MODE_REASON_REQUIRED: a mode change without a reason is not recorded')
    p = state_path()
    doc = json.loads(p.read_text())
    cur = read(doc)
    if cur['pinned'] and by != 'owner':
        raise PermissionError(
            f'MODE_PINNED_BY_OWNER: mode_declared={cur["mode"]} is the owner\'s statement; an '
            f'agent may not change it. Ask the owner, or have the owner clear mode_declared.')
    rec = {'mode': mode, 'since_commit': _head(),
           'since_utc': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
           'set_by': by, 'slate': slate, 'reason': reason.strip(),
           'previous': cur['mode']}
    doc['mode'] = rec
    tmp = p.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(doc, indent=1, sort_keys=False) + '\n')
    os.replace(tmp, p)
    # from_status/to_status carry the TASK status vocabulary the validator checks; a mode is not
    # a task status, so modes ride in their own fields on an event row.
    row = {'timestamp': rec['since_utc'], 'actor': 'claude' if by == 'agent' else by,
           'task_id': 'MODE', 'from_status': None, 'to_status': None,
           'event': 'MODE_SET', 'from_mode': cur['mode'], 'to_mode': mode,
           'reason': rec['reason'], 'slate': slate, 'head_commit': rec['since_commit']}
    with open(handoff_path(), 'a') as fh:
        fh.write(json.dumps(row, sort_keys=True) + '\n')
    return rec


def changed_paths(since: str | None = None) -> list[str]:
    """Committed diff since `since` (default: the mode's since_commit) plus the working tree."""
    out = set()
    try:
        if since:
            r = subprocess.run(['git', 'diff', '--name-only', f'{since}..HEAD'], cwd=ROOT,
                               capture_output=True, text=True)
            out.update(r.stdout.split())
        r = subprocess.run(['git', 'status', '--porcelain', '--untracked-files=all'], cwd=ROOT,
                           capture_output=True, text=True)
        for ln in r.stdout.splitlines():
            path = ln[3:].strip()
            if ' -> ' in path:
                path = path.split(' -> ', 1)[1]
            out.add(path)
    except Exception:  # noqa: BLE001
        pass
    return sorted(out)


def diff_text(since: str | None = None) -> str:
    try:
        parts = []
        if since:
            parts.append(subprocess.run(['git', 'diff', f'{since}..HEAD'], cwd=ROOT,
                                        capture_output=True, text=True).stdout)
        parts.append(subprocess.run(['git', 'diff'], cwd=ROOT, capture_output=True, text=True).stdout)
        return '\n'.join(parts)
    except Exception:  # noqa: BLE001
        return ''


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] == 'show':
        cur = read()
        print(json.dumps(cur, indent=1))
        return 0 if cur['mode'] else 3
    if argv[0] == 'set':
        mode = argv[1] if len(argv) > 1 else ''
        reason = argv[argv.index('--reason') + 1] if '--reason' in argv else ''
        by = argv[argv.index('--by') + 1] if '--by' in argv else 'agent'
        slate = argv[argv.index('--slate') + 1] if '--slate' in argv else None
        try:
            rec = set_mode(mode, reason, by=by, slate=slate)
        except (ValueError, PermissionError) as e:
            print(f'REFUSED {e}')
            return 2
        print(f'mode {rec["previous"]} -> {rec["mode"]} ({rec["set_by"]}) at {rec["since_commit"]}')
        return 0
    if argv[0] == 'check':
        from coordination.orchestrator import locks as L
        cur = read()
        since = argv[argv.index('--since') + 1] if '--since' in argv else (cur['record'] or {}).get('since_commit')
        o = L.mode_boundary(changed_paths(since), cur['mode'], diff=diff_text(since))
        print(json.dumps(o, indent=1))
        return 0 if o['state'] == 'CLEAN' else (3 if o['state'] == 'NOT_EXECUTED' else 1)
    print(__doc__)
    return 2


if __name__ == '__main__':
    sys.exit(main())
