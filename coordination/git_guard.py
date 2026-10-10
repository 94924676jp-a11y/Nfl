#!/usr/bin/env python3.12
"""Git and PR guard, Phase 1 N2: REPORT-ONLY, fail-closed for protected operations (owner approval 2026-10-10).

Called from coordination/mode_guard.py (the one PreToolUse hook this repository registers); it is not a second
hook. For every tool call it classifies the attempted operation and appends one JSON line to the report log
(`NFL_GUARD_REPORT_LOG`, default `coordination/runs/guard_reports/git_guard.jsonl`, git-ignored):

  VERIFY_BYPASS        --no-verify (and abbreviations), commit -n, --no-gpg-sign, HUSKY=0 / SKIP= hook skips
  HOOK_PATH_CHANGE     core.hooksPath through -c or git config; writes, removals or chmod under .git/hooks
  SAFEGUARD_MODIFIED   writes to the guards themselves or to the hook registration (.claude/settings*.json)
  PROTECTED_PUSH       any push to a protected branch; force, delete or mirror against a protected or the shared
                       automation branch; a force push whose destination cannot be determined
  UNAUTHORIZED_MERGE   gh pr merge, auto-merge, merge or ref writes through gh api or the GitHub MCP tools
  SELF_APPROVAL        an agent approving a PR, or writing owner-authority or approval evidence (OWNER_DECISIONS,
                       the protected policies, *APPROV* / *.approved / *AUTHORIZ* files, PROJECT_STATE
                       mode_declared)
  WORKFLOW_DISPATCH    starting a GitHub Actions run (gh workflow run, the dispatches API, actions_run_trigger)
  CONCEALMENT          git update-index --assume-unchanged / --skip-worktree (hides a modification from status)
  MODE_CHANGE          coordination/mode.py set (allowed, recorded)

AUTHORIZATION. The protected operations above are the owner's. NO AGENT-WRITABLE ARTIFACT AUTHORIZES ONE: there
is no approval file, token or flag this guard honours, so an agent cannot fabricate one, and the attempt to write
such a file is itself a SELF_APPROVAL finding. The owner authorizes out of band (GitHub, or a commit by the owner to
a protected file). The would-be decision for every protected finding is therefore DENY.

FAIL CLOSED. An unreadable policy, an unparseable hook payload or an exception inside the classifier is never read
as permission: the record says why and its would-be decision is DENY. (Ordinary writes keep mode_guard's own
behaviour; this module adds no decision to them.)

REPORT-ONLY. `ENFORCEMENT` is a code constant. While it is REPORT_ONLY nothing is printed to the hook's stdout,
so no tool call is ever blocked by this module; a test pins the value. Promotion is a reviewed change the owner
approves.
"""
from __future__ import annotations

import datetime as dt
import fnmatch
import json
import os
import pathlib
import re
import shlex
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC_VERSION = 'git-guard-1'
ENFORCEMENT = 'REPORT_ONLY'          # owner approval required to change; pinned by nfl/tests/test_git_guard.py
LOG_DEFAULT = ROOT / 'coordination' / 'runs' / 'guard_reports' / 'git_guard.jsonl'

#: built-in floor, used even when the policy file is unreadable (fail-closed: never an empty list)
PROTECTED_BRANCHES_FLOOR = ('main', 'master')
OWNER_AUTHORITY = ('coordination/OWNER_DECISIONS.md', 'coordination/AUTOMATION_POLICY.json',
                   'coordination/MODE_POLICY.json', 'coordination/orchestrator/MODELS.json',
                   'nfl/production/authorization.py', 'nfl/production/review/gate.py')
APPROVAL_NAME = re.compile(r'(APPROV|AUTHORIZ|AUTHORIS|OWNER_DECISION|\.approved$|^\.review-approved$)', re.I)
SAFEGUARDS = ('.claude/settings.json', '.claude/settings.local.json', 'coordination/mode_guard.py',
              'coordination/git_guard.py', 'coordination/mode.py', 'coordination/orchestrator/locks.py',
              'nfl/tools/floor_guard.py', '.github/workflows/*')
PROTECTED_RULES = {'VERIFY_BYPASS', 'HOOK_PATH_CHANGE', 'SAFEGUARD_MODIFIED', 'PROTECTED_PUSH',
                   'UNAUTHORIZED_MERGE', 'SELF_APPROVAL', 'WORKFLOW_DISPATCH', 'CONCEALMENT', 'GUARD_INPUT_INVALID',
                   'GUARD_ERROR'}
GIT_GLOBAL_WITH_VALUE = {'-c', '-C', '--git-dir', '--work-tree', '--namespace', '--exec-path', '--super-prefix',
                         '--config-env'}
SEPARATORS = {';', '&&', '||', '|', '&', '\n'}
WRITE_VERBS = ('>', 'tee', 'sed', 'cp', 'mv', 'rm', 'touch', 'truncate', 'dd', 'install', 'ln', 'chmod',
               'open(', 'write_text', 'write_bytes', '.write(', 'shutil', 'os.remove', 'unlink', 'rename')


# ------------------------------------------------------------------ policy (fail-closed)
def policy():
    """Protected and shared branches, and whether the policy could be read."""
    try:
        bp = json.loads((ROOT / 'coordination' / 'AUTOMATION_POLICY.json').read_text())['branch_policy']
        prot = sorted(set(bp.get('protected_branches') or ()) | set(PROTECTED_BRANCHES_FLOOR))
        shared = bp.get('automation_branch')
        return {'protected': prot, 'shared': [shared] if shared else [], 'readable': True}
    except Exception as e:  # noqa: BLE001 -- recorded below, and read as the stricter answer
        return {'protected': list(PROTECTED_BRANCHES_FLOOR), 'shared': [], 'readable': False,
                'why': f'{type(e).__name__}: {e}'}


# ------------------------------------------------------------------ shell parsing
def _split(cmd):
    """Simple commands (argv lists) in a shell string, including $(...), backticks and bash -c / eval bodies."""
    out, nested = [], []
    for m in re.finditer(r'\$\(([^()]*)\)|`([^`]*)`', cmd):
        nested.append(m.group(1) if m.group(1) is not None else m.group(2))
    try:
        lex = shlex.shlex(cmd.replace('\n', ' ; '), posix=True, punctuation_chars=';&|')
        lex.whitespace_split = True
        toks = list(lex)
    except ValueError:
        toks = cmd.split()
    cur = []
    for t in toks:
        if t in SEPARATORS or set(t) <= set(';&|'):
            if cur:
                out.append(cur)
            cur = []
        else:
            cur.append(t)
    if cur:
        out.append(cur)
    expanded = []
    for argv in out:
        expanded.append(argv)
        for i, t in enumerate(argv):
            if t in ('-c', '-lc', '-ic') and i > 0 and os.path.basename(argv[i - 1]) in ('bash', 'sh', 'zsh', 'dash') \
                    and i + 1 < len(argv):
                nested.append(argv[i + 1])
            if t == 'eval' and i + 1 < len(argv):
                nested.append(' '.join(argv[i + 1:]))
    for body in nested:
        if body and body != cmd:
            expanded.extend(_split(body))
    return expanded


def _strip_prefix(argv):
    """Drop env assignments, `env`, `sudo`, `command`, `nohup`, `timeout N`; return (env, argv)."""
    env = {}
    i = 0
    while i < len(argv):
        t = argv[i]
        if re.match(r'^[A-Za-z_][A-Za-z0-9_]*=', t):
            k, v = t.split('=', 1)
            env[k] = v
            i += 1
        elif t in ('env', 'sudo', 'command', 'nohup', 'exec', 'nice', 'time'):
            i += 1
        elif t == 'timeout' and i + 1 < len(argv):
            i += 2
        elif t.startswith('-') and i > 0 and argv[i - 1] in ('env', 'sudo'):
            i += 1
        else:
            break
    return env, argv[i:]


def _git_parts(argv):
    """(config overrides, subcommand, args) for a git argv, or None."""
    if not argv or os.path.basename(argv[0]) != 'git':
        return None
    cfg, i = [], 1
    while i < len(argv):
        t = argv[i]
        if t in GIT_GLOBAL_WITH_VALUE:
            if t == '-c' and i + 1 < len(argv):
                cfg.append(argv[i + 1])
            i += 2
        elif t.startswith('-c') and len(t) > 2:
            cfg.append(t[2:])
            i += 1
        elif t.startswith('--') and '=' in t and t.split('=')[0] in GIT_GLOBAL_WITH_VALUE:
            i += 1
        elif t.startswith('-'):
            i += 1
        else:
            return cfg, t, argv[i + 1:]
    return cfg, None, []


def _current_branch(cwd):
    try:
        r = subprocess.run(['git', '-C', cwd or str(ROOT), 'rev-parse', '--abbrev-ref', 'HEAD'],
                           capture_output=True, text=True, timeout=5)
        b = r.stdout.strip()
        return b if r.returncode == 0 and b and b != 'HEAD' else None
    except Exception:  # noqa: BLE001
        return None


def _rel(path, cwd):
    if not path:
        return None
    p = pathlib.Path(path)
    if not p.is_absolute():
        p = pathlib.Path(cwd or os.getcwd()) / p
    try:
        return str(p.resolve().relative_to(ROOT))
    except ValueError:
        return None


def _is_approval_path(rel):
    if rel is None:
        return False
    if rel in OWNER_AUTHORITY:
        return True
    return bool(APPROVAL_NAME.search(pathlib.PurePath(rel).name))


def _is_safeguard(rel):
    return rel is not None and any(fnmatch.fnmatch(rel, p) for p in SAFEGUARDS)


def _finding(rule, detail, **ev):
    return {'rule': rule, 'protected': rule in PROTECTED_RULES, 'detail': detail, **({'evidence': ev} if ev else {})}


# ------------------------------------------------------------------ classification
def _git_findings(env, cfg, sub, args, cwd, pol):
    f = []
    hooks_cfg = [c for c in cfg if c.lower().startswith('core.hookspath')]
    if hooks_cfg:
        f.append(_finding('HOOK_PATH_CHANGE', f'git -c {hooks_cfg[0]} bypasses the repository hooks'))
    if sub == 'config' and any(a.lower() == 'core.hookspath' or a.lower().startswith('core.hookspath=')
                               for a in args):
        f.append(_finding('HOOK_PATH_CHANGE', 'git config core.hooksPath changes which hooks run'))
    if sub in ('commit', 'merge', 'push', 'rebase', 'am', 'cherry-pick', 'revert', 'pull', 'switch', 'checkout'):
        for a in args:
            if a.startswith('--no-v') and '--no-verify'.startswith(a.split('=')[0]):
                f.append(_finding('VERIFY_BYPASS', f'git {sub} {a} skips verification hooks'))
            if a.startswith('--no-gpg') and '--no-gpg-sign'.startswith(a):
                f.append(_finding('VERIFY_BYPASS', f'git {sub} {a} skips signing'))
        if sub == 'commit':
            for a in args:
                if a == '--':
                    break
                if re.match(r'^-[A-Za-z]+$', a) and 'n' in a[1:]:
                    f.append(_finding('VERIFY_BYPASS', f'git commit {a} (-n is --no-verify)'))
    for k in ('HUSKY', 'HUSKY_SKIP_HOOKS', 'SKIP', 'PRE_COMMIT_ALLOW_NO_CONFIG', 'LEFTHOOK'):
        if k in env and sub in ('commit', 'push', 'merge', 'rebase'):
            f.append(_finding('VERIFY_BYPASS', f'{k}={env[k]} disables hook managers for git {sub}'))
    if sub == 'update-index' and any(a in ('--assume-unchanged', '--skip-worktree') for a in args):
        f.append(_finding('CONCEALMENT', 'git update-index hides modifications from git status'))
    if sub == 'push':
        f.extend(_push_findings(args, cwd, pol))
    return f


def _push_findings(args, cwd, pol):
    f = []
    force = any(a in ('-f', '--force', '--force-if-includes') or a.startswith('--force-with-lease')
                or (re.match(r'^-[a-zA-Z]+$', a) and 'f' in a[1:]) for a in args)
    delete = any(a in ('-d', '--delete', '--prune') for a in args)
    mirror = any(a in ('--mirror', '--all') for a in args)
    pos = [a for a in args if not a.startswith('-')]
    refspecs = pos[1:] if len(pos) > 1 else []
    dests = []
    for r in refspecs:
        if r.startswith('+'):
            force = True
            r = r[1:]
        if r.startswith(':'):
            delete = True
            dests.append(r[1:])
        elif ':' in r:
            dests.append(r.split(':', 1)[1])
        elif r in ('HEAD', '@'):
            dests.append(_current_branch(cwd))
        else:
            dests.append(r)
    if not refspecs:
        dests = [_current_branch(cwd)]
    dests = [d.replace('refs/heads/', '') if d else None for d in dests]
    protected, shared = set(pol['protected']), set(pol['shared'])
    unknown = any(d is None for d in dests)
    for d in dests:
        if d in protected:
            f.append(_finding('PROTECTED_PUSH', f'push to protected branch {d} (owner-only)', branch=d,
                              force=force, delete=delete))
        elif (force or delete) and d in shared:
            f.append(_finding('PROTECTED_PUSH', f'{"force" if force else "delete"} push to the shared automation '
                                                 f'branch {d} rewrites history other agents build on', branch=d))
    if mirror:
        f.append(_finding('PROTECTED_PUSH', 'git push --mirror/--all touches every branch, protected ones included'))
    if (force or delete) and unknown:
        f.append(_finding('PROTECTED_PUSH', 'force or delete push whose destination branch cannot be determined '
                                             '(fail-closed: treated as protected)'))
    if not pol['readable'] and (force or delete):
        f.append(_finding('PROTECTED_PUSH', f'branch policy unreadable ({pol.get("why")}); every force or delete push '
                                             f'is treated as protected'))
    return f


def _gh_findings(argv):
    f = []
    if len(argv) < 2 or os.path.basename(argv[0]) != 'gh':
        return f
    sub = argv[1:]
    if sub[:2] == ['pr', 'merge']:
        f.append(_finding('UNAUTHORIZED_MERGE', 'gh pr merge (merging is the owner\'s)'))
    if sub[:2] == ['pr', 'review'] and any(a in ('--approve', '-a') for a in sub):
        f.append(_finding('SELF_APPROVAL', 'gh pr review --approve: an agent may not approve'))
    if sub[:2] == ['workflow', 'run'] or sub[:2] == ['run', 'rerun']:
        f.append(_finding('WORKFLOW_DISPATCH', f'gh {" ".join(sub[:2])} starts an Actions run'))
    if sub[:1] == ['api']:
        method = 'GET'
        for i, a in enumerate(sub):
            if a in ('-X', '--method') and i + 1 < len(sub):
                method = sub[i + 1].upper()
            elif a.startswith('--method='):
                method = a.split('=', 1)[1].upper()
            elif a.startswith('-X') and len(a) > 2:
                method = a[2:].upper()
        if method == 'GET' and any(a in ('-f', '-F', '--field', '--raw-field', '--input') for a in sub):
            method = 'POST'
        path = next((a for a in sub[1:] if not a.startswith('-') and '/' in a), '')
        if method != 'GET':
            if re.search(r'/pulls/\d+/merge|/merges\b|/auto-merge', path):
                f.append(_finding('UNAUTHORIZED_MERGE', f'gh api {method} {path}'))
            elif re.search(r'/pulls/\d+/reviews', path) and any('APPROVE' in a for a in sub):
                f.append(_finding('SELF_APPROVAL', f'gh api {method} {path} with event APPROVE'))
            elif re.search(r'/git/refs|/branches/[^/]+/protection|/rulesets', path):
                f.append(_finding('PROTECTED_PUSH', f'gh api {method} {path} writes refs or protection'))
            elif re.search(r'/actions/workflows/[^/]+/dispatches|/dispatches\b|/actions/runs/\d+/rerun', path):
                f.append(_finding('WORKFLOW_DISPATCH', f'gh api {method} {path}'))
            elif re.search(r'/contents/', path):
                rel = path.split('/contents/', 1)[1]
                if _is_approval_path(rel) or _is_safeguard(rel):
                    f.append(_finding('SELF_APPROVAL' if _is_approval_path(rel) else 'SAFEGUARD_MODIFIED',
                                      f'gh api {method} writes {rel}'))
    return f


_HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1[^\n]*\n(.*?)\n\s*\2\s*(?:\n|$)", re.S)
_Q = r"(['\"])(?P<p>[^'\"\n]+)(?P=q)"
_PY_WRITES = [
    re.compile(r"open\(\s*(?P<q>['\"])(?P<p>[^'\"\n]+)(?P=q)\s*,\s*['\"][^'\"]*[wax+]"),
    re.compile(r"Path\(\s*(?P<q>['\"])(?P<p>[^'\"\n]+)(?P=q)\s*\)\s*\.\s*(?:write_text|write_bytes|unlink|rename|replace|"
               r"touch|chmod|symlink_to)\("),
    re.compile(r"os\.(?:remove|unlink|rename|replace|chmod|truncate)\(\s*(?P<q>['\"])(?P<p>[^'\"\n]+)(?P=q)"),
    re.compile(r"shutil\.(?:copy\w*|move)\([^,\n]*,\s*(?P<q>['\"])(?P<p>[^'\"\n]+)(?P=q)"),
    re.compile(r"shutil\.rmtree\(\s*(?P<q>['\"])(?P<p>[^'\"\n]+)(?P=q)"),
]
#: a written path looks like one: no spaces, braces, quotes or parentheses (an f-string fragment is not a path)
_PATHLIKE = re.compile(r'^[\w./@+-]+$')
_PY_PATH_VAR = re.compile(r"(\w+)\s*=\s*(?:pathlib\.)?Path\(\s*(?P<q>['\"])(?P<p>[^'\"\n]+)(?P=q)\s*\)")


def strip_heredocs(cmd):
    """(command with heredoc bodies removed, [bodies]). A heredoc body is stdin data or a script, not arguments."""
    bodies = []

    def keep(m):
        bodies.append(m.group(3))
        return '\n'
    return _HEREDOC.sub(keep, cmd), bodies


def python_write_paths(text):
    """Paths a Python snippet writes: open(..., 'w'/'a'/'x'/'+'), Path(...).write_text(...), a variable bound to a
    Path and then written, os/shutil writes. Reads (open(p), json.load(open(p))) are not writes."""
    out = [m.group('p') for rx in _PY_WRITES for m in rx.finditer(text) if _PATHLIKE.match(m.group('p'))]
    for m in _PY_PATH_VAR.finditer(text):
        var, path = m.group(1), m.group('p')
        if not _PATHLIKE.match(path):
            continue
        if re.search(rf"\b{re.escape(var)}\s*\.\s*(?:write_text|write_bytes|unlink|rename|replace|touch|chmod)\(", text) \
                or re.search(rf"open\(\s*{re.escape(var)}\s*,\s*['\"][^'\"]*[wax+]", text):
            out.append(path)
    return out


def _write_targets(tool, ti, cwd):
    """Repository-relative paths a tool call writes. Reuses mode_guard's own Bash write parser, then adds the
    Python-snippet writes it cannot see (heredocs and -c bodies), matched precisely rather than by any token."""
    from coordination import mode_guard as MG
    if tool == 'Bash':
        # mode_guard's redirection parser reads a `>` inside a heredoc body (Python or HTML text) as a shell
        # redirect; a heredoc body is stdin, so it is removed before that parser sees the command.
        stripped, _ = strip_heredocs(ti.get('command') or '')
        paths = list(MG.targets(tool, dict(ti, command=stripped), cwd))
    else:
        paths = list(MG.targets(tool, ti, cwd))
    if tool == 'Bash':
        cmd = ti.get('command') or ''
        for raw in python_write_paths(cmd):
            r = _rel(raw, cwd)
            if r and r not in paths:
                paths.append(r)
        cmd, _ = strip_heredocs(cmd)
        for argv in _split(cmd):
            _, a = _strip_prefix(argv)
            if not a:
                continue
            verb = os.path.basename(a[0])
            operands = [t.strip('\'"') for t in a[1:] if not t.startswith('-')]
            if verb == 'chmod' and operands and re.match(r'^([ugoa]*[+=-][rwxXst]*|\d{3,4})$', operands[0]):
                operands = operands[1:]                       # the first operand is the mode
            if verb in ('cp', 'ln', 'install'):
                operands = operands[-1:]                      # only the destination is written
            if verb in ('chmod', 'rm', 'mv', 'cp', 'ln', 'install', 'truncate'):
                for tok in operands:
                    r = _rel(tok, cwd)
                    if r and r not in paths:
                        paths.append(r)
    return paths


def classify(payload):
    """[finding] for one PreToolUse payload. Raises only on programming errors (observe() records those)."""
    tool = payload.get('tool_name') or ''
    ti = payload.get('tool_input') or {}
    cwd = payload.get('cwd')
    pol = policy()
    out = []
    if tool == 'Bash':
        cmd, _ = strip_heredocs(ti.get('command') or '')
        for argv in _split(cmd):
            env, a = _strip_prefix(argv)
            if not a:
                continue
            gp = _git_parts(a)
            if gp:
                out.extend(_git_findings(env, gp[0], gp[1], gp[2], cwd, pol))
            out.extend(_gh_findings(a))
            if a[0].endswith('mode.py') or (len(a) > 1 and a[1].endswith('coordination/mode.py')):
                if 'set' in a:
                    out.append(_finding('MODE_CHANGE', 'coordination/mode.py set (recorded, not protected)'))
        if '.git/hooks' in cmd and any(v in cmd for v in WRITE_VERBS):
            out.append(_finding('HOOK_PATH_CHANGE', 'a command writes, removes or changes modes under .git/hooks'))
    if tool.startswith('mcp__github__'):
        name = tool[len('mcp__github__'):]
        branch = (ti.get('branch') or ti.get('ref') or '').replace('refs/heads/', '')
        if name in ('merge_pull_request', 'enable_pr_auto_merge'):
            out.append(_finding('UNAUTHORIZED_MERGE', f'{name} (merging is the owner\'s)'))
        if name == 'pull_request_review_write' and str(ti.get('event', '')).upper() == 'APPROVE':
            out.append(_finding('SELF_APPROVAL', 'an agent approving a pull request'))
        if name == 'actions_run_trigger':
            out.append(_finding('WORKFLOW_DISPATCH', 'actions_run_trigger starts an Actions run'))
        if name in ('push_files', 'create_or_update_file', 'delete_file'):
            if branch in set(pol['protected']) or (not branch and name != 'push_files'):
                out.append(_finding('PROTECTED_PUSH', f'{name} on branch {branch or "UNSPECIFIED (default branch)"}'))
            files = [x.get('path') for x in (ti.get('files') or []) if isinstance(x, dict)] + [ti.get('path')]
            for p in filter(None, files):
                if _is_approval_path(p):
                    out.append(_finding('SELF_APPROVAL', f'{name} writes approval or owner-authority file {p}'))
                elif _is_safeguard(p):
                    out.append(_finding('SAFEGUARD_MODIFIED', f'{name} writes safeguard {p}'))
    if tool in ('Edit', 'Write', 'MultiEdit', 'NotebookEdit', 'Bash'):
        # the hook registration itself, wherever it lives: a project, local or USER settings file outside this
        # repository can switch every hook off (disableAllHooks), after which no guard sees anything
        raw_target = ti.get('file_path') or ti.get('notebook_path') or ''
        body = (ti.get('content') or '') + (ti.get('new_string') or '')
        bcmd = strip_heredocs(ti.get('command') or '')[0] if tool == 'Bash' else ''
        settings_write = (re.search(r'(^|/)\.claude/settings(\.local)?\.json$', raw_target) or
                          (tool == 'Bash' and re.search(r'\.claude/settings(\.local)?\.json', bcmd)
                           and any(v in bcmd for v in WRITE_VERBS)) or
                          any(re.search(r'\.claude/settings(\.local)?\.json', x) for x in
                              python_write_paths(ti.get('command') or '')))
        if settings_write:
            out.append(_finding('SAFEGUARD_MODIFIED', 'writes a Claude Code settings file (hook registration)'))
        if 'disableAllHooks' in body + (ti.get('command') or ''):
            out.append(_finding('SAFEGUARD_MODIFIED', 'sets disableAllHooks: every hook, this guard included, stops'))
        for rel in _write_targets(tool, ti, cwd):
            if rel.startswith('.git/hooks'):
                out.append(_finding('HOOK_PATH_CHANGE', f'writes {rel}'))
            elif _is_approval_path(rel):
                out.append(_finding('SELF_APPROVAL', f'writes approval or owner-authority file {rel}'))
            elif _is_safeguard(rel):
                out.append(_finding('SAFEGUARD_MODIFIED', f'writes safeguard {rel}'))
            elif rel == 'coordination/PROJECT_STATE.json':
                body = (ti.get('content') or '') + (ti.get('new_string') or '') + (ti.get('command') or '')
                if 'mode_declared' in body:
                    out.append(_finding('SELF_APPROVAL', 'writes mode_declared, which only the owner states'))
    seen, uniq = set(), []
    for f in out:
        k = (f['rule'], f['detail'])
        if k not in seen:
            seen.add(k)
            uniq.append(f)
    if not pol['readable']:
        for f in uniq:
            f.setdefault('evidence', {})['policy_unreadable'] = pol.get('why')
    return uniq


def _summary(payload):
    ti = payload.get('tool_input') or {}
    s = ti.get('command') or ti.get('file_path') or ti.get('path') or json.dumps(ti)[:200]
    return str(s)[:300]


def _log(rec):
    p = pathlib.Path(os.environ.get('NFL_GUARD_REPORT_LOG') or LOG_DEFAULT)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, 'a') as fh:
            fh.write(json.dumps(rec, sort_keys=True) + '\n')
    except OSError:
        pass                           # the report is best-effort; the decision path below does not depend on it


def observe(payload):
    """Classify, record, and return a hook output ONLY when enforcing. In REPORT_ONLY this always returns None."""
    now = dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    try:
        findings = classify(payload)
        err = None
    except Exception as e:  # noqa: BLE001 -- fail-closed: an error is a DENY, never a silent allow
        findings = [_finding('GUARD_ERROR', f'{type(e).__name__}: {e}')]
        err = str(e)
    would = 'DENY' if any(f['protected'] for f in findings) else 'ALLOW'
    if findings or err:
        _log({'at': now, 'spec': SPEC_VERSION, 'enforcement': ENFORCEMENT, 'tool': payload.get('tool_name'),
              'summary': _summary(payload), 'would_decision': would, 'findings': findings})
    if ENFORCEMENT == 'ENFORCE' and would == 'DENY':
        why = '; '.join(f'{f["rule"]}: {f["detail"]}' for f in findings if f['protected'])[:900]
        return {'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'deny',
                                       'permissionDecisionReason': f'GIT_GUARD: {why}. Protected operations are the '
                                       f'owner\'s; no agent-written file authorizes one.'}}
    return None


def observe_invalid(raw):
    """An unparseable hook payload: recorded with would-decision DENY (fail-closed)."""
    now = dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    _log({'at': now, 'spec': SPEC_VERSION, 'enforcement': ENFORCEMENT, 'tool': None,
          'summary': (raw or '')[:200], 'would_decision': 'DENY',
          'findings': [_finding('GUARD_INPUT_INVALID', 'the hook payload is not valid JSON')]})
    if ENFORCEMENT == 'ENFORCE':
        return {'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'deny',
                                       'permissionDecisionReason': 'GIT_GUARD: unreadable hook payload (fail-closed)'}}
    return None
