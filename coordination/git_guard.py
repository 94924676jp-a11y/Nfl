#!/usr/bin/env python3.12
"""Git and PR guard, Phase 1 N2: REPORT-ONLY, fail-closed for protected operations (owner approval 2026-10-10).

Called from coordination/mode_guard.py (the one PreToolUse hook this repository registers); it is not a second
hook. For every tool call it classifies the attempted operation and appends one JSON line to the report log
(`NFL_GUARD_REPORT_LOG`, default `coordination/runs/guard_reports/git_guard.jsonl`, git-ignored):

  VERIFY_BYPASS        --no-verify (and abbreviations), commit -n, --no-gpg-sign, HUSKY=0 / SKIP= hook skips
  HOOK_PATH_CHANGE     core.hooksPath through -c, --config-env, GIT_CONFIG_* or git config; any write, removal or
                       chmod under the hooks directory; any direct write to the git config file
  SAFEGUARD_MODIFIED   writes to the guards themselves or to a Claude Code settings file (hook registration), at
                       project, local or user level
  PROTECTED_PUSH       any push to a protected branch; force, delete or mirror against a protected or the shared
                       automation branch; a push whose destination cannot be determined when it could be one
  UNAUTHORIZED_MERGE   gh pr merge, auto-merge, merge through gh api REST or GraphQL, or the GitHub MCP tools
  SELF_APPROVAL        an agent approving a PR, or writing owner-authority or approval evidence (OWNER_DECISIONS,
                       the protected policies, *APPROV* / *.approved / *AUTHORIZ* files, PROJECT_STATE
                       mode_declared)
  WORKFLOW_DISPATCH    starting or re-running a GitHub Actions run
  CONCEALMENT          git update-index --assume-unchanged / --skip-worktree, git sparse-checkout set/add
  MODE_CHANGE          coordination/mode.py set (allowed, recorded)

HOW A COMMAND IS READ (rewritten after the independent coverage review, 2026-10-10). One shell lexer turns the
command into simple commands with their redirections, heredoc bodies and command substitutions: quotes,
backslashes, `$(...)`, backticks, `(`/`)` subshells, `{ }` groups, reserved words (`then`, `do`, ...), comments and
`cd` are honoured, heredoc bodies are consumed line by line (linear time), and a redirection token is never an
argument. Every rule then reads parsed argv, never a substring of the raw text. Python run through `-c` or a heredoc
is read with `ast` (string variables, `Path(...) / 'x'`, `open(..., mode='w')`, subprocess and os.system bodies);
an unparseable snippet falls back to precise regexes.

AUTHORIZATION. The protected operations above are the owner's. NO AGENT-WRITABLE ARTIFACT AUTHORIZES ONE: there
is no approval file, token or flag this guard honours, so an agent cannot fabricate one, and the attempt to write
such a file is itself a SELF_APPROVAL finding. The owner authorizes out of band (GitHub, or a commit by the owner to
a protected file). The would-be decision for every protected finding is therefore DENY.

FAIL CLOSED. An unreadable policy, an unparseable or oversized hook payload or an exception inside the classifier is
never read as permission: the record says why and its would-be decision is DENY. (Ordinary writes keep
mode_guard's own behaviour; this module adds no decision to them.)

WHAT THIS CANNOT SEE (the enforcement boundary): a script that does the write itself (`python3.12 tool.py`), a
patch whose file is absent, git operations whose effect depends on history (merge, reset, stash pop), other
sessions, other agents, humans, and GitHub itself. It is advisory classification of tool-call text; a guarantee
needs server-side branch protection.

REPORT-ONLY. `ENFORCEMENT` is a code constant. While it is REPORT_ONLY nothing is printed to the hook's stdout,
so no tool call is ever blocked by this module; a test pins the value. Promotion is a reviewed change the owner
approves.
"""
from __future__ import annotations

import ast
import datetime as dt
import fnmatch
import json
import os
import pathlib
import posixpath
import re
import subprocess
import warnings

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC_VERSION = 'git-guard-2'
ENFORCEMENT = 'REPORT_ONLY'          # owner approval required to change; pinned by nfl/tests/test_git_guard.py
LOG_DEFAULT = ROOT / 'coordination' / 'runs' / 'guard_reports' / 'git_guard.jsonl'
MAX_COMMAND_BYTES = 1 << 20          # larger than this is not classified: recorded as GUARD_INPUT_INVALID (DENY)

#: built-in floor, used even when the policy file is unreadable (fail-closed: never an empty list)
PROTECTED_BRANCHES_FLOOR = ('main', 'master', 'capture-prod')
OWNER_AUTHORITY = ('coordination/OWNER_DECISIONS.md', 'coordination/AUTOMATION_POLICY.json',
                   'coordination/MODE_POLICY.json', 'coordination/orchestrator/MODELS.json',
                   'nfl/production/authorization.py', 'nfl/production/review/gate.py')
#: Approval evidence by name. nfl/governance/OWNER_APPROVAL_QUEUE.jsonl matches deliberately: it carries the
#: owner_decision field, so a direct edit could forge a verdict; the request path is nfl/governance/ledgers.py.
APPROVAL_NAME = re.compile(r'(APPROV|AUTHORIZ|AUTHORIS|OWNER_DECISION|\.approved$|^\.review-approved$)', re.I)
SAFEGUARDS = ('.claude/settings.json', '.claude/settings.local.json', 'coordination/mode_guard.py',
              'coordination/git_guard.py', 'coordination/mode.py', 'coordination/orchestrator/locks.py',
              'nfl/tools/floor_guard.py', '.github/workflows/*')
SETTINGS_FILE = re.compile(r'(^|/)(\.claude/settings(\.local)?\.json|managed-settings\.json)$')
GIT_INTERNAL = re.compile(r'(^|/)\.git/(hooks(/|$)|config$|config\.worktree$)')
PROTECTED_RULES = {'VERIFY_BYPASS', 'HOOK_PATH_CHANGE', 'SAFEGUARD_MODIFIED', 'PROTECTED_PUSH',
                   'UNAUTHORIZED_MERGE', 'SELF_APPROVAL', 'WORKFLOW_DISPATCH', 'CONCEALMENT', 'GUARD_INPUT_INVALID',
                   'GUARD_ERROR'}


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


_GITDIRS = {}


def git_dirs(repo=None):
    """(git dir, common git dir) of this checkout, absolute. A worktree's hooks and config live in the COMMON dir,
    outside ROOT, so `.git/hooks` relative to ROOT is not where they are."""
    key = str(repo or ROOT)
    if key not in _GITDIRS:
        dirs = {str(pathlib.Path(key) / '.git')}
        try:
            r = subprocess.run(['git', '-C', key, 'rev-parse', '--absolute-git-dir', '--git-common-dir'],
                               capture_output=True, text=True, timeout=5)
            if r.returncode == 0:
                for ln in r.stdout.split():
                    p = pathlib.Path(ln)
                    dirs.add(os.path.realpath(p if p.is_absolute() else pathlib.Path(key) / p))
        except Exception:  # noqa: BLE001 -- the ROOT/.git default still applies
            pass
        _GITDIRS[key] = sorted(dirs)
    return _GITDIRS[key]


# ------------------------------------------------------------------ the shell lexer
_OPS = ('&&', '||', '|&', ';;', ';', '|', '&', '(', ')', '\n')
_REDIRS = ('&>>', '&>', '<<<', '<<-', '<<', '>>', '>|', '>&', '<&', '<>', '>', '<')
RESERVED = {'{', '}', '!', 'then', 'do', 'else', 'elif', 'if', 'while', 'until', 'fi', 'done', 'esac', 'time',
            'in', 'coproc'}
SHELLS = {'bash', 'sh', 'zsh', 'dash', 'ksh'}
#: substitutions whose value is this checkout's git layout (a worktree-correct spelling of the hooks dir)
_KNOWN_SUBS = {
    'git rev-parse --git-path hooks': lambda: os.path.join(git_dirs()[-1] if git_dirs() else str(ROOT / '.git'),
                                                           'hooks'),
    'git rev-parse --git-dir': lambda: git_dirs()[0],
    'git rev-parse --absolute-git-dir': lambda: git_dirs()[0],
    'git rev-parse --git-common-dir': lambda: git_dirs()[-1],
    'git rev-parse --show-toplevel': lambda: str(ROOT),
}


class Word(str):
    """A shell word with quotes removed. `subs` are the bodies of its command substitutions; `dynamic` is True
    when part of it is only known at run time ($VAR, $(...), backticks)."""
    subs: list
    dynamic: bool


def _word(text, subs, dynamic):
    w = Word(text)
    w.subs, w.dynamic = subs, dynamic
    return w


def _match_paren(s, i):
    """Index just past the `)` closing the `$(` whose body starts at i, honouring quotes and nesting."""
    depth, n = 1, len(s)
    while i < n:
        c = s[i]
        if c == '\\':
            i += 2
            continue
        if c == "'":
            j = s.find("'", i + 1)
            i = n if j < 0 else j + 1
            continue
        if c == '"':
            i += 1
            while i < n and s[i] != '"':
                i += 2 if s[i] == '\\' else 1
            i += 1
            continue
        if c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return n


def lex(s):
    """Tokens of a shell string: ('w', Word) | ('op', op) | ('r', redir, heredoc-holder). Linear in len(s).
    A heredoc body is attached to its `<<` token (holder['body']) and is not lexed as commands."""
    toks, n, i = [], len(s), 0
    pending = []                                    # heredocs whose body starts after the next newline
    buf, subs, dyn, inword = [], [], False, False

    def end_word():
        nonlocal buf, subs, dyn, inword
        if inword:
            toks.append(('w', _word(''.join(buf), subs, dyn)))
        buf, subs, dyn, inword = [], [], False, False

    def read_heredocs(i):
        for h in pending:
            lines = []
            while i < n:
                j = s.find('\n', i)
                line = s[i:] if j < 0 else s[i:j]
                i = n if j < 0 else j + 1
                if (line.lstrip('\t') if h['strip'] else line) == h['delim']:
                    break
                lines.append(line)
            h['body'] = '\n'.join(lines)
        pending.clear()
        return i

    while i < n:
        c = s[i]
        if c == '\\':
            if i + 1 < n and s[i + 1] == '\n':
                i += 2                              # line continuation
                continue
            buf.append(s[i + 1] if i + 1 < n else '')
            inword = True
            i += 2
            continue
        if c == "'":
            j = s.find("'", i + 1)
            j = n if j < 0 else j
            buf.append(s[i + 1:j])
            inword = True
            i = j + 1
            continue
        if c == '$' and i + 1 < n and s[i + 1] == "'":
            j = i + 2
            while j < n and s[j] != "'":
                j += 2 if s[j] == '\\' else 1
            buf.append(s[i + 2:j].encode('utf-8', 'replace').decode('unicode_escape', 'replace'))
            inword = True
            i = j + 1
            continue
        if c == '"':
            i += 1
            inword = True
            while i < n and s[i] != '"':
                if s[i] == '\\' and i + 1 < n and s[i + 1] in '"\\$`\n':
                    buf.append(s[i + 1] if s[i + 1] != '\n' else '')
                    i += 2
                elif s[i] == '$' and s.startswith('$(', i):
                    j = _match_paren(s, i + 2)
                    subs.append(s[i + 2:j - 1])
                    buf.append(s[i:j])
                    dyn = True
                    i = j
                elif s[i] == '`':
                    j = s.find('`', i + 1)
                    j = n if j < 0 else j
                    subs.append(s[i + 1:j])
                    buf.append(s[i:j + 1])
                    dyn = True
                    i = j + 1
                else:
                    if s[i] == '$':
                        dyn = True
                    buf.append(s[i])
                    i += 1
            i += 1
            continue
        if c == '$' and s.startswith('$(', i):
            j = _match_paren(s, i + 2)
            subs.append(s[i + 2:j - 1])
            buf.append(s[i:j])
            dyn = inword = True
            i = j
            continue
        if c == '`':
            j = s.find('`', i + 1)
            j = n if j < 0 else j
            subs.append(s[i + 1:j])
            buf.append(s[i:j + 1])
            dyn = inword = True
            i = j + 1
            continue
        if c in ' \t\r':
            end_word()
            i += 1
            continue
        if c == '#' and not inword:
            j = s.find('\n', i)
            i = n if j < 0 else j
            continue
        if c == '\n':
            end_word()
            toks.append(('op', '\n'))
            i = read_heredocs(i + 1)
            continue
        if c in '<>' or (c == '&' and s.startswith('&>', i)):
            if inword and ''.join(buf).isdigit() and not subs:
                buf, inword = [], False             # `2>`: the fd number is not a word
            end_word()
            op = next(r for r in _REDIRS if s.startswith(r, i))
            i += len(op)
            holder = {}
            toks.append(('r', op, holder))
            if op in ('<<', '<<-'):
                while i < n and s[i] in ' \t':
                    i += 1
                j = i
                while j < n and s[j] not in ' \t\n;&|<>()':
                    j += 1
                holder.update(delim=s[i:j].replace("'", '').replace('"', '').replace('\\', ''),
                              strip=op == '<<-', body='')
                pending.append(holder)
                i = j
            continue
        if c in ';&|()':
            end_word()
            op = next(o for o in _OPS if s.startswith(o, i))
            toks.append(('op', op))
            i += len(op)
            continue
        if c == '$':
            dyn = True
        buf.append(c)
        inword = True
        i += 1
    end_word()
    if pending:
        read_heredocs(n)
    return toks


class Cmd:
    """One simple command: argv (Words), redirections [(op, target Word | None, heredoc body | None)], the cwd it runs
    in, the environment it sees (persisted exports plus its own prefix assignments), and whether it reads stdin
    from a pipe."""

    def __init__(self, argv, redirs, cwd, env, piped):
        self.argv, self.redirs, self.cwd, self.env, self.piped = argv, redirs, cwd, env, piped


def _strip_prefix(argv, env):
    """Drop assignments and wrapper commands (env, sudo, command, nohup, exec, nice, time, timeout N, stdbuf, xargs);
    return (env, argv, via_xargs)."""
    env = dict(env)
    i, xargs = 0, False
    while i < len(argv):
        t = argv[i]
        b = os.path.basename(t)
        if re.match(r'^[A-Za-z_][A-Za-z0-9_]*=', t):
            k, v = t.split('=', 1)
            env[k] = v
            i += 1
        elif b in ('env', 'sudo', 'command', 'nohup', 'exec', 'nice', 'time', 'builtin', 'stdbuf', 'doas', 'chronic'):
            i += 1
            while i < len(argv) and argv[i].startswith('-'):
                i += 2 if argv[i] in ('-u', '-n', '-g', '-C') else 1
        elif b == 'timeout':
            i += 1
            while i < len(argv) and argv[i].startswith('-'):
                i += 2 if argv[i] in ('-s', '-k', '--signal', '--kill-after') else 1
            i += 1
        elif b == 'xargs':
            xargs = True
            i += 1
            while i < len(argv) and argv[i].startswith('-'):
                i += 2 if argv[i] in ('-I', '-n', '-P', '-d', '-L', '-a', '-E', '-s') else 1
        else:
            break
    return env, argv[i:], xargs


def parse(cmd, cwd=None, env=None, _depth=0):
    """[Cmd] for a shell string, nested bodies included: $(...), backticks, bash -c / sh -c, eval, a heredoc fed to
    a shell, and (as their own Cmds) shell strings that a Python snippet runs through subprocess or os.system."""
    if _depth > 8:
        return []
    out, persisted = [], dict(env or {})
    cwds = [cwd]
    toks = lex(cmd)
    cur, redirs, piped, k = [], [], False, 0

    def flush(next_piped):
        nonlocal cur, redirs, piped
        argv = cur
        while argv and argv[0] in RESERVED:
            argv = argv[1:]
        if argv or redirs:
            only_assign = argv and all(re.match(r'^[A-Za-z_][A-Za-z0-9_]*=', a) for a in argv)
            if argv and argv[0] in ('export', 'declare', 'typeset', 'readonly', 'local') or only_assign:
                for a in argv[0 if only_assign else 1:]:
                    if '=' in a and not a.startswith('-'):
                        kk, v = a.split('=', 1)
                        persisted[kk] = v
            elif argv and argv[0] == 'cd' and len(argv) >= 2 and not argv[1].dynamic:
                cwds[-1] = _abs(argv[1], cwds[-1]) or cwds[-1]
            elif argv and argv[0] == 'cd' and len(argv) == 1:
                cwds[-1] = os.path.expanduser('~')
            c = Cmd(argv, redirs, cwds[-1], persisted, piped)
            out.append(c)
            for w in argv:
                for body in w.subs:
                    out.extend(parse(body, cwds[-1], persisted, _depth + 1))
            for _, tgt, _ in redirs:
                for body in (tgt.subs if tgt is not None else []):
                    out.extend(parse(body, cwds[-1], persisted, _depth + 1))
            _nested(c, out, _depth)
        cur, redirs, piped = [], [], next_piped

    while k < len(toks):
        t = toks[k]
        if t[0] == 'w':
            cur.append(t[1])
            k += 1
        elif t[0] == 'r':
            tgt = toks[k + 1][1] if k + 1 < len(toks) and toks[k + 1][0] == 'w' else None
            redirs.append((t[1], tgt, t[2].get('body') if t[1] in ('<<', '<<-') else None))
            k += 2 if tgt is not None else 1
        else:
            op = t[1]
            flush(op in ('|', '|&'))
            if op == '(':
                cwds.append(cwds[-1])
            elif op == ')' and len(cwds) > 1:
                cwds.pop()
            k += 1
    flush(False)
    return out


def _nested(c, out, depth):
    env, a, _ = _strip_prefix(c.argv, c.env)
    if not a:
        return
    verb = os.path.basename(a[0])
    if verb in SHELLS:
        for i, t in enumerate(a[1:], 1):
            if re.match(r'^-[a-z]*c[a-z]*$', t) and i + 1 < len(a):
                out.extend(parse(a[i + 1], c.cwd, env, depth + 1))
                break
        else:
            for op, _, body in c.redirs:                # `bash <<EOF` and `bash -s <<EOF`: the body is the script
                if body:
                    out.extend(parse(body, c.cwd, env, depth + 1))
            for op, tgt, _ in c.redirs:
                if op == '<<<' and tgt is not None:
                    out.extend(parse(str(tgt), c.cwd, env, depth + 1))
    elif verb == 'eval' and len(a) > 1:
        out.extend(parse(' '.join(a[1:]), c.cwd, env, depth + 1))
    elif _is_python(verb):
        for code in _python_code(a, c):
            for sh in python_analysis(code)['shell']:
                out.extend(parse(sh, c.cwd, env, depth + 1))


def _is_python(verb):
    return bool(re.match(r'^python[\d.]*$', verb))


def _python_code(a, c):
    """Python source a python argv runs inline: the -c body, or stdin from a heredoc / here-string."""
    for i, t in enumerate(a[1:], 1):
        if t == '-c' and i + 1 < len(a):
            return [str(a[i + 1])]
        if t == '-m' or (not t.startswith('-') and t != '-'):
            return []                                   # a script or module: its writes are invisible here
    return [b for op, _, b in c.redirs if b] + [str(t) for op, t, _ in c.redirs if op == '<<<' and t is not None]


# ------------------------------------------------------------------ Python snippets
_PY_WRITE_METHODS = {'write_text', 'write_bytes', 'unlink', 'rename', 'replace', 'touch', 'chmod', 'symlink_to',
                     'hardlink_to', 'rmdir'}
_PY_OS_ONE = {'remove', 'unlink', 'rmdir', 'chmod', 'truncate', 'utime', 'removedirs', 'lchmod'}
_PY_OS_TWO = {'rename', 'replace', 'symlink', 'link', 'renames'}
_PY_SHUTIL_DST = {'copy', 'copy2', 'copyfile', 'copytree', 'move', 'copymode', 'copystat'}
_Q = r"(?P<q>['\"])(?P<p>[^'\"\n]+)(?P=q)"
_PY_WRITES_RX = [
    re.compile(r"open\(\s*" + _Q + r"\s*,\s*(?:mode\s*=\s*)?['\"][^'\"]*[wax+]"),
    re.compile(r"Path\(\s*" + _Q + r"\s*\)\s*\.\s*(?:write_text|write_bytes|unlink|rename|replace|touch|chmod|"
               r"symlink_to)\("),
    re.compile(r"os\.(?:remove|unlink|rename|replace|chmod|truncate)\(\s*" + _Q),
    re.compile(r"shutil\.(?:copy\w*|move)\([^,\n]*,\s*" + _Q),
    re.compile(r"shutil\.rmtree\(\s*" + _Q),
]


def _dotted(node):
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return '.'.join(reversed(parts))
    return None


def python_analysis(code):
    """{'writes': [path], 'shell': [command string]} for a Python snippet. String-valued variables, Path(...) and
    os.path.join, the `/` operator and constant f-strings are folded; a path that is only known at run time is not
    reported (residual: a snippet computing its path from input is invisible)."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')          # a snippet's own invalid escapes are not this guard's output
            tree = ast.parse(code)
    except (SyntaxError, ValueError):
        return {'writes': [m.group('p') for rx in _PY_WRITES_RX for m in rx.finditer(code)], 'shell': [],
                'parsed': False}
    names = {}

    def ev(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.Name):
            return names.get(node.id)
        if isinstance(node, ast.JoinedStr):
            parts = [ev(v) if not isinstance(v, ast.FormattedValue) else ev(v.value) for v in node.values]
            return ''.join(parts) if all(p is not None for p in parts) else None
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            a, b = ev(node.left), ev(node.right)
            return posixpath.join(a, b) if a is not None and b is not None else None
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            a, b = ev(node.left), ev(node.right)
            return a + b if a is not None and b is not None else None
        if isinstance(node, ast.Call):
            f = _dotted(node.func) or ''
            base = f.split('.')[-1]
            if base in ('Path', 'PurePath', 'PosixPath') or f in ('os.path.join', 'posixpath.join'):
                parts = [ev(x) for x in node.args]
                return posixpath.join(*parts) if parts and all(p is not None for p in parts) else (
                    '.' if not parts and base in ('Path', 'PurePath', 'PosixPath') else None)
            if f in ('str', 'os.fspath', 'os.path.expanduser', 'os.path.abspath', 'os.path.realpath') and node.args:
                v = ev(node.args[0])
                return os.path.expanduser(v) if v is not None and 'expanduser' in f else v
            if f.endswith('Path.home'):
                return os.path.expanduser('~')
            if isinstance(node.func, ast.Attribute) and node.func.attr in ('expanduser', 'resolve', 'absolute'):
                v = ev(node.func.value)
                return os.path.expanduser(v) if v is not None else None
        return None

    assigns = sorted((n for n in ast.walk(tree) if isinstance(n, (ast.Assign, ast.AnnAssign, ast.NamedExpr))),
                     key=lambda n: (n.lineno, n.col_offset))
    for n in assigns:
        targets = n.targets if isinstance(n, ast.Assign) else [n.target]
        v = ev(n.value) if n.value is not None else None
        for t in targets:
            if isinstance(t, ast.Name):
                if v is not None:
                    names[t.id] = v
                else:
                    names.pop(t.id, None)
    writes, shell = [], []
    for n in ast.walk(tree):
        if not isinstance(n, ast.Call):
            continue
        f = _dotted(n.func) or ''
        attr = n.func.attr if isinstance(n.func, ast.Attribute) else None
        kw = {k.arg: k.value for k in n.keywords if k.arg}
        if f in ('open', 'io.open', 'codecs.open', 'builtins.open') and n.args:
            mode = ev(n.args[1]) if len(n.args) > 1 else (ev(kw['mode']) if 'mode' in kw else 'r')
            if mode is not None and re.search(r'[wax+]', mode):
                writes.append(ev(n.args[0]))
        elif attr == 'open' and isinstance(n.func, ast.Attribute) and f != 'os.open':
            mode = ev(n.args[0]) if n.args else (ev(kw['mode']) if 'mode' in kw else 'r')
            if mode is not None and re.search(r'[wax+]', mode):
                writes.append(ev(n.func.value))
        elif attr in _PY_WRITE_METHODS and not f.startswith(('os.', 'shutil.')):
            writes.append(ev(n.func.value))
            if attr in ('rename', 'replace', 'symlink_to') and n.args:
                writes.append(ev(n.args[0]))
        elif f.startswith('os.') and f[3:] in _PY_OS_ONE and n.args:
            writes.append(ev(n.args[0]))
        elif f.startswith('os.') and f[3:] in _PY_OS_TWO and len(n.args) > 1:
            writes.extend([ev(n.args[0]), ev(n.args[1])] if f[3:] in ('rename', 'replace', 'renames')
                          else [ev(n.args[1])])
        elif f.startswith('shutil.') and f[7:] in _PY_SHUTIL_DST and len(n.args) > 1:
            writes.append(ev(n.args[1]))
            if f[7:] == 'move':
                writes.append(ev(n.args[0]))
        elif f == 'shutil.rmtree' and n.args:
            writes.append(ev(n.args[0]))
        elif f in ('os.system', 'os.popen', 'subprocess.getoutput', 'subprocess.getstatusoutput') and n.args:
            v = ev(n.args[0])
            if v is not None:
                shell.append(v)
        elif f.split('.')[-1] in ('run', 'call', 'check_call', 'check_output', 'Popen') and n.args \
                and (f.startswith('subprocess.') or f in ('run', 'call', 'check_call', 'check_output', 'Popen')):
            a0 = n.args[0]
            if isinstance(a0, (ast.List, ast.Tuple)):
                parts = [ev(x) for x in a0.elts]
                if parts and all(p is not None for p in parts):
                    shell.append(' '.join(_shquote(p) for p in parts))
            else:
                v = ev(a0)
                if v is not None:
                    shell.append(v)
    return {'writes': [w for w in writes if w], 'shell': shell, 'parsed': True}


def _shquote(s):
    return s if re.match(r'^[\w./:@%+=,-]+$', s) else "'" + s.replace("'", "'\\''") + "'"


# ------------------------------------------------------------------ paths
def _abs(word, cwd):
    """Absolute normalised path for a shell word, or None when it is only known at run time."""
    if word is None:
        return None
    w = str(word)
    for sub, val in _KNOWN_SUBS.items():
        for spelling in (f'$({sub})', f'`{sub}`'):
            if spelling in w:
                w = w.replace(spelling, val())
    w = re.sub(r'^\$\{?HOME\}?(?=/|$)', os.path.expanduser('~'), w)
    w = os.path.expanduser(w)
    if not w or '$' in w or '`' in w or w.startswith('/dev/') or w == '-':
        return None
    p = w if os.path.isabs(w) else os.path.join(cwd or os.getcwd(), w)
    return os.path.realpath(p)


def _rel(path, cwd=None):
    """Repository-relative path, or None outside the repository. Accepts a str or Word."""
    a = _abs(path, cwd) if not (isinstance(path, str) and os.path.isabs(path) and '$' not in path) else \
        os.path.realpath(path)
    if a is None:
        return None
    try:
        return str(pathlib.Path(a).relative_to(ROOT))
    except ValueError:
        return None


def _norm_repo_path(p):
    """A path an MCP or REST call names inside the repository, normalised ('./a', '/a', 'a//b' -> 'a', 'a/b')."""
    p = posixpath.normpath('/' + str(p or '')).lstrip('/')
    return p if p and p != '.' else None


def _is_approval_path(rel):
    if rel is None:
        return False
    if rel in OWNER_AUTHORITY:
        return True
    return bool(APPROVAL_NAME.search(pathlib.PurePath(rel).name))


def _is_safeguard(rel):
    return rel is not None and any(fnmatch.fnmatch(rel, p) for p in SAFEGUARDS)


def _git_internal(absp):
    """'hooks' or 'config' when an absolute path is this checkout's (or any repository's) hooks dir or git config."""
    if absp is None:
        return None
    for d in git_dirs():
        if absp == os.path.join(d, 'hooks') or absp.startswith(os.path.join(d, 'hooks') + os.sep):
            return 'hooks'
        if absp in (os.path.join(d, 'config'), os.path.join(d, 'config.worktree')):
            return 'config'
        if absp == d:
            return 'hooks'                               # moving or removing the git dir takes the hooks with it
    m = GIT_INTERNAL.search(absp)
    return None if not m else ('hooks' if m.group(2).startswith('hooks') else 'config')


def _finding(rule, detail, **ev):
    return {'rule': rule, 'protected': rule in PROTECTED_RULES, 'detail': detail, **({'evidence': ev} if ev else {})}


# ------------------------------------------------------------------ option parsing helpers
def _long(opt, names):
    """Resolve a long option (`--del`, `--force-with-lease=x`) to its full name by exact or unique prefix match."""
    name = opt[2:].split('=', 1)[0]
    if name in names:
        return name
    hits = [x for x in names if x.startswith(name)]
    return hits[0] if len(hits) == 1 else None


def _operands(args, short_val='', long_val=(), long_names=None):
    """(operands, options) of an argv tail. Values of value-taking options are consumed, `--` ends options."""
    ops, opts, i = [], [], 0
    while i < len(args):
        t = args[i]
        if t == '--':
            ops.extend(args[i + 1:])
            break
        if t.startswith('--') and len(t) > 2:
            name = _long(t, long_names) if long_names else t[2:].split('=', 1)[0]
            opts.append((name or t[2:].split('=', 1)[0], t.split('=', 1)[1] if '=' in t else None))
            if '=' not in t and name in long_val:
                opts[-1] = (name, args[i + 1] if i + 1 < len(args) else None)
                i += 1
        elif t.startswith('-') and len(t) > 1:
            j = 1
            while j < len(t):
                ch = t[j]
                if ch in short_val:
                    val = t[j + 1:] or (args[i + 1] if i + 1 < len(args) else None)
                    if not t[j + 1:]:
                        i += 1
                    opts.append((ch, val))
                    break
                opts.append((ch, None))
                j += 1
        else:
            ops.append(t)
        i += 1
    return ops, opts


# ------------------------------------------------------------------ write targets
def _dest_expand(dest, srcs, cwd, target_dir=None):
    """Paths a copy/move/link writes: DEST itself, or DEST/<basename src> when DEST is a directory."""
    out = []
    d = target_dir or dest
    da = _abs(d, cwd)
    if da is None:
        return out
    if target_dir or os.path.isdir(da) or str(d).endswith('/'):
        out.extend(os.path.join(da, os.path.basename(str(s).rstrip('/'))) for s in srcs if s)
        out.append(da)
    else:
        out.append(da)
    return out


def _patch_paths(path, cwd):
    """Files a unified diff (git apply / patch) would write, read from the patch file when it exists."""
    a = _abs(path, cwd)
    try:
        if a and os.path.getsize(a) < 5 << 20:
            text = open(a, errors='replace').read()
        else:
            return []
    except OSError:
        return []
    out = []
    for m in re.finditer(r'^(?:\+\+\+|---) (?:[ab]/)?(\S+)', text, re.M):
        if m.group(1) != '/dev/null':
            out.append(os.path.realpath(os.path.join(str(ROOT), m.group(1))))
    return out


def command_writes(c):
    """Absolute paths one simple command writes (redirections included), with the verb that writes them."""
    out = []
    for op, tgt, _ in c.redirs:
        if op in ('>', '>>', '>|', '&>', '&>>', '<>') and tgt is not None:
            out.append((_abs(tgt, c.cwd), f'redirect {op}'))
        elif op == '>&' and tgt is not None and not re.match(r'^\d+-?$|^-$', str(tgt)):
            out.append((_abs(tgt, c.cwd), 'redirect >&'))
    env, a, _ = _strip_prefix(c.argv, c.env)
    if not a:
        return [(p, how) for p, how in out if p]
    verb, args, cwd = os.path.basename(a[0]), a[1:], c.cwd
    add = lambda paths, how: out.extend((p, how) for p in paths)  # noqa: E731
    if verb in ('rm', 'rmdir', 'unlink', 'touch', 'shred', 'mkdir'):
        ops, _ = _operands(args, short_val='m' if verb == 'mkdir' else '')
        if verb != 'mkdir':
            add([_abs(x, cwd) for x in ops], verb)
    elif verb == 'truncate':
        ops, _ = _operands(args, short_val='sr', long_val=('size', 'reference'))
        add([_abs(x, cwd) for x in ops], verb)
    elif verb == 'tee':
        ops, _ = _operands(args)
        add([_abs(x, cwd) for x in ops], verb)
    elif verb in ('chmod', 'chown', 'chgrp', 'setfacl', 'chattr'):
        ops, opts = _operands(args)
        if not any(o[0].startswith('reference') for o in opts) and ops:
            ops = ops[1:]                                  # the mode / owner
        if verb == 'chmod' and args and re.match(r'^-[rwxXst]+$', args[0]):
            ops = [x for x in args[1:] if not x.startswith('-')]   # `chmod -x f`: -x is the mode
        add([_abs(x, cwd) for x in ops], verb)
    elif verb in ('cp', 'mv', 'ln', 'install', 'rsync'):
        sv = {'cp': 'tS', 'mv': 'tS', 'ln': 'tS', 'install': 'tmogS', 'rsync': 'efT'}[verb]
        lv = ('target-directory', 'suffix', 'mode', 'owner', 'group', 'rsh', 'exclude', 'include', 'filter',
              'temp-dir', 'backup-dir', 'chmod', 'chown')
        ops, opts = _operands(args, short_val=sv, long_val=lv)
        tdir = next((v for k, v in opts if k in ('t', 'target-directory')), None)
        if verb == 'install' and any(k in ('d', 'directory') for k, _ in opts):
            add([_abs(x, cwd) for x in ops], verb)
        elif verb == 'rsync':
            ops = [x for x in ops if not re.match(r'^[\w.-]+@?[\w.-]*:', str(x))]
            if ops:
                add(_dest_expand(ops[-1], ops[:-1], cwd), verb)
        elif tdir:
            add(_dest_expand(None, ops, cwd, target_dir=tdir), verb)
        elif len(ops) >= 2:
            add(_dest_expand(ops[-1], ops[:-1], cwd), verb)
        elif len(ops) == 1 and verb == 'ln':
            add([_abs(os.path.basename(str(ops[0])), cwd)], verb)
        if verb == 'mv':
            add([_abs(x, cwd) for x in (ops if tdir else ops[:-1])], 'mv (source removed)')
    elif verb == 'dd':
        add([_abs(x[3:], cwd) for x in args if x.startswith('of=')], verb)
    elif verb == 'sed':
        inplace, script_given, ops, i = False, False, [], 0
        while i < len(args):
            t = args[i]
            if t == '--':
                ops.extend(args[i + 1:])
                break
            if t.startswith('--'):
                name = t[2:].split('=', 1)[0]
                if 'in-place'.startswith(name) and len(name) >= 2:
                    inplace = True
                elif name in ('expression', 'file') or (name and ('expression'.startswith(name) or
                                                                  'file'.startswith(name))):
                    script_given = True
                    if '=' not in t:
                        i += 1
                elif name in ('line-length',) and '=' not in t:
                    i += 1
            elif t.startswith('-') and len(t) > 1:
                for j, ch in enumerate(t[1:], 1):
                    if ch == 'i':
                        inplace = True
                        break                               # the rest is the backup suffix
                    if ch in 'efl':
                        script_given = script_given or ch in 'ef'
                        if not t[j + 1:]:
                            i += 1
                        break
            else:
                ops.append(t)
            i += 1
        if inplace:
            add([_abs(x, cwd) for x in (ops if script_given else ops[1:])], 'sed -i')
    elif verb == 'perl':
        inplace, script_given, ops, i = False, False, [], 0
        while i < len(args):
            t = args[i]
            if t == '--':
                ops.extend(args[i + 1:])
                break
            if t.startswith('-') and len(t) > 1 and not ops:
                for j, ch in enumerate(t[1:], 1):
                    if ch == 'i':
                        inplace = True
                        break
                    if ch in 'eE':
                        script_given = True
                        if not t[j + 1:]:
                            i += 1
                        break
                    if ch in 'MmIFCdDxV0l':
                        break                               # attached value
            else:
                ops.append(t)
            i += 1
        if inplace:
            add([_abs(x, cwd) for x in (ops if script_given else ops[1:])], 'perl -i')
    elif verb == 'patch':
        ops, opts = _operands(args, short_val='ipdDoBrVzFg', long_val=('input', 'directory', 'output'))
        src = next((v for k, v in opts if k in ('i', 'input')), None)
        src = src or next((str(t) for op, t, _ in c.redirs if op == '<' and t is not None), None)
        if ops:
            add([_abs(ops[0], cwd)], 'patch')
        elif src:
            add(_patch_paths(src, cwd), 'patch')
    elif verb == 'git':
        gp = _git_parts(a)
        if gp:
            out.extend(_git_worktree_writes(gp[1], gp[2], cwd))
    elif _is_python(verb):
        for code in _python_code(a, c):
            add([_abs(p, cwd) for p in python_analysis(code)['writes']], 'python')
    return [(p, how) for p, how in out if p]


def _git_worktree_writes(sub, args, cwd):
    out = []
    if sub == 'checkout':
        ops, opts = _operands(args, short_val='bBO', long_val=('orphan', 'conflict', 'pathspec-from-file'))
        if '--' in args:
            paths = args[args.index('--') + 1:]
        else:
            paths = [x for x in ops[1:] if (_abs(x, cwd) and os.path.exists(_abs(x, cwd)))]
        out += [(_abs(x, cwd), f'git checkout <rev> -- path') for x in paths]
    elif sub == 'restore':
        ops, opts = _operands(args, short_val='s', long_val=('source', 'conflict', 'pathspec-from-file'))
        keys = {k for k, _ in opts}
        if not (keys & {'S', 'staged'}) or (keys & {'W', 'worktree'}):
            out += [(_abs(x, cwd), 'git restore') for x in ops]
    elif sub in ('rm', 'mv'):
        ops, _ = _operands(args)
        out += [(_abs(x, cwd), f'git {sub}') for x in ops]
    elif sub in ('apply', 'am'):
        ops, opts = _operands(args, short_val='pC', long_val=('directory', 'exclude', 'include'))
        if any(k in ('cached', 'check', 'stat', 'numstat', 'summary') for k, _ in opts) and \
                not any(k == 'index' for k, _ in opts):
            return out
        for x in ops:
            out += [(p, f'git {sub}') for p in _patch_paths(x, cwd)]
    return [(p, h) for p, h in out if p]


def write_targets(payload):
    """[(absolute path, how)] a tool call writes. Edit/Write/MultiEdit/NotebookEdit name their file; a Bash
    command is parsed into simple commands and each one's writes are read from argv and redirections."""
    tool = payload.get('tool_name') or ''
    ti = payload.get('tool_input') or {}
    cwd = payload.get('cwd')
    if tool in ('Edit', 'Write', 'MultiEdit', 'NotebookEdit'):
        p = ti.get('file_path') or ti.get('notebook_path')
        a = _abs(p, cwd) if p else None
        return [(a, tool)] if a else []
    if tool == 'Bash':
        out = []
        for c in parse(ti.get('command') or '', cwd):
            out.extend(command_writes(c))
        return out
    return []


def _written_text(ti):
    """The text a tool call puts into a file: content, new_string, every MultiEdit new_string, new_source."""
    parts = [ti.get('content'), ti.get('new_string'), ti.get('new_source')]
    parts += [e.get('new_string') for e in (ti.get('edits') or []) if isinstance(e, dict)]
    return '\n'.join(str(p) for p in parts if p)


# ------------------------------------------------------------------ git
GIT_GLOBAL_WITH_VALUE = {'-c', '-C', '--git-dir', '--work-tree', '--namespace', '--exec-path', '--super-prefix',
                         '--config-env', '--attr-source', '--list-cmds'}
PUSH_LONG = {'all', 'branches', 'mirror', 'delete', 'tags', 'follow-tags', 'dry-run', 'porcelain', 'force',
             'force-with-lease', 'force-if-includes', 'no-force-with-lease', 'no-force-if-includes', 'repo',
             'set-upstream', 'thin', 'no-thin', 'quiet', 'verbose', 'progress', 'no-progress', 'prune', 'no-prune',
             'no-verify', 'verify', 'recurse-submodules', 'no-recurse-submodules', 'atomic', 'no-atomic',
             'push-option', 'ipv4', 'ipv6', 'receive-pack', 'exec', 'signed', 'no-signed'}
PUSH_LONG_VALUE = {'repo', 'push-option', 'receive-pack', 'exec'}
COMMIT_LONG_VALUE = {'message', 'file', 'reuse-message', 'reedit-message', 'fixup', 'squash', 'author', 'date',
                     'template', 'cleanup', 'trailer', 'pathspec-from-file'}


def _git_parts(argv):
    """(config overrides, subcommand, args) for a git argv, or None. --config-env keys count as overrides."""
    if not argv or os.path.basename(argv[0]) != 'git':
        return None
    cfg, i = [], 1
    while i < len(argv):
        t = argv[i]
        if t in GIT_GLOBAL_WITH_VALUE:
            if t in ('-c', '--config-env') and i + 1 < len(argv):
                cfg.append(argv[i + 1])
            i += 2
        elif t.startswith('-c') and len(t) > 2 and not t.startswith('--'):
            cfg.append(t[2:])
            i += 1
        elif t.startswith('--') and '=' in t and t.split('=')[0] in GIT_GLOBAL_WITH_VALUE:
            if t.startswith('--config-env='):
                cfg.append(t.split('=', 1)[1])
            i += 1
        elif t.startswith('-'):
            i += 1
        else:
            return cfg, t, argv[i + 1:]
    return cfg, None, []


_BRANCH_CACHE = {}


def _current_branch(cwd):
    key = cwd or str(ROOT)
    if key not in _BRANCH_CACHE:
        try:
            r = subprocess.run(['git', '-C', key, 'rev-parse', '--abbrev-ref', 'HEAD'],
                               capture_output=True, text=True, timeout=5)
            b = r.stdout.strip()
            _BRANCH_CACHE[key] = b if r.returncode == 0 and b and b != 'HEAD' else None
        except Exception:  # noqa: BLE001
            _BRANCH_CACHE[key] = None
    return _BRANCH_CACHE[key]


def _env_config(env):
    """git config entries an environment sets: GIT_CONFIG_COUNT/KEY_n/VALUE_n and GIT_CONFIG_PARAMETERS."""
    out = [f'{v}={env.get("GIT_CONFIG_VALUE_" + k[len("GIT_CONFIG_KEY_"):], "")}'
           for k, v in env.items() if k.startswith('GIT_CONFIG_KEY_')]
    if 'GIT_CONFIG_PARAMETERS' in env:
        out += re.findall(r"'([^']+)'(?:=)?", env['GIT_CONFIG_PARAMETERS'])
    return out


def _git_findings(env, cfg, sub, args, cwd, pol, via_xargs=False):
    f = []
    allcfg = cfg + _env_config(env)
    hooks_cfg = [c for c in allcfg if c.lower().replace(' ', '').startswith('core.hookspath')]
    if hooks_cfg:
        f.append(_finding('HOOK_PATH_CHANGE', f'git config override {hooks_cfg[0]} bypasses the repository hooks'))
    if sub == 'config':
        ops, _ = _operands(args, short_val='f', long_val=('file', 'type', 'default', 'comment', 'value'))
        if any(str(a).lower().split('=')[0] == 'core.hookspath' for a in ops):
            f.append(_finding('HOOK_PATH_CHANGE', 'git config core.hooksPath changes which hooks run'))
    if sub in ('commit', 'merge', 'push', 'rebase', 'am', 'cherry-pick', 'revert', 'pull', 'switch', 'checkout'):
        i = 0
        while i < len(args):
            a = args[i]
            if a == '--':
                break
            if a.startswith('--'):
                name = a[2:].split('=', 1)[0]
                if a.startswith('--no-v') and '--no-verify'.startswith(a.split('=')[0]):
                    f.append(_finding('VERIFY_BYPASS', f'git {sub} {a} skips verification hooks'))
                if a.startswith('--no-gpg') and '--no-gpg-sign'.startswith(a):
                    f.append(_finding('VERIFY_BYPASS', f'git {sub} {a} skips signing'))
                if sub == 'commit' and '=' not in a and name in COMMIT_LONG_VALUE:
                    i += 1                                   # the option's value, e.g. a message, is not an option
            elif sub == 'commit' and re.match(r'^-[A-Za-z]+$', a):
                for j, ch in enumerate(a[1:], 1):
                    if ch == 'n':
                        f.append(_finding('VERIFY_BYPASS', f'git commit {a} (-n is --no-verify)'))
                        break
                    if ch in 'mFCct':
                        if not a[j + 1:]:
                            i += 1                           # value is the next argument
                        break                                # value is the rest of the cluster
                    if ch in 'Su':
                        break                                # optional attached value
            i += 1
    for k in ('HUSKY', 'HUSKY_SKIP_HOOKS', 'SKIP', 'PRE_COMMIT_ALLOW_NO_CONFIG', 'LEFTHOOK', 'GIT_HOOKS_DISABLED'):
        if k in env and sub in ('commit', 'push', 'merge', 'rebase'):
            f.append(_finding('VERIFY_BYPASS', f'{k}={env[k]} disables hook managers for git {sub}'))
    if sub == 'update-index' and any(a in ('--assume-unchanged', '--skip-worktree') for a in args):
        f.append(_finding('CONCEALMENT', 'git update-index hides modifications from git status'))
    if sub == 'sparse-checkout' and args and args[0] in ('set', 'add', 'init', 'reapply'):
        f.append(_finding('CONCEALMENT', f'git sparse-checkout {args[0]} marks every path outside the cone '
                                         f'skip-worktree, hiding it from status'))
    if sub == 'push':
        f.extend(_push_findings(args, cwd, pol, cfg=allcfg, via_xargs=via_xargs))
    return f


def _push_findings(args, cwd, pol, cfg=(), via_xargs=False):
    """Findings for one `git push` argv tail. Options are parsed with their values, abbreviations resolved the
    way git resolves them (unique prefix), and the destination of every refspec computed."""
    pos, force, delete, mirror, dry, repo = [], False, False, False, False, None
    i = 0
    while i < len(args):
        t = str(args[i])
        if t == '--':
            pos.extend(args[i + 1:])
            break
        if t.startswith('--'):
            name = _long(t, PUSH_LONG)
            if name is None:
                pass                                         # unknown or ambiguous: git refuses it
            elif name in ('force', 'force-with-lease', 'force-if-includes'):
                force = True
            elif name in ('delete', 'prune'):
                delete = True
            elif name in ('mirror', 'all', 'branches'):
                mirror = True
            elif name == 'dry-run':
                dry = True
            elif name == 'repo':
                repo = t.split('=', 1)[1] if '=' in t else (args[i + 1] if i + 1 < len(args) else None)
            if name in PUSH_LONG_VALUE and '=' not in t:
                i += 1
        elif t.startswith('-') and len(t) > 1:
            for j, ch in enumerate(t[1:], 1):
                if ch == 'f':
                    force = True
                elif ch == 'd':
                    delete = True
                elif ch == 'n':
                    dry = True
                elif ch == 'o':
                    if not t[j + 1:]:
                        i += 1
                    break
        else:
            pos.append(t)
        i += 1
    if any(re.match(r'(?i)^remote\.[^=]+\.mirror=(true|1|yes|on)?$', c) or c.lower() == 'push.default=matching'
           for c in cfg):
        mirror = True
    refspecs = pos if repo is not None else pos[1:]
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
        elif re.search(r'[~^]', r):
            dests.append(None)
        else:
            dests.append(r)
    if not refspecs and not mirror:
        dests = [_current_branch(cwd)]
    norm = []
    for d in dests:
        if d is None:
            norm.append(None)
        elif d.startswith('refs/tags/'):
            continue
        elif d in ('HEAD', '@'):
            norm.append(_current_branch(cwd))
        else:
            norm.append(re.sub(r'^(refs/heads/|heads/)', '', d))
    protected, shared = set(pol['protected']), set(pol['shared'])
    if dry:
        return []
    f = []
    for d in norm:
        if d is None:
            continue
        hit_p = [b for b in protected if fnmatch.fnmatchcase(b, d)] if any(ch in d for ch in '*?[') else \
            ([d] if d in protected else [])
        hit_s = [b for b in shared if fnmatch.fnmatchcase(b, d)] if any(ch in d for ch in '*?[') else \
            ([d] if d in shared else [])
        for b in hit_p:
            f.append(_finding('PROTECTED_PUSH', f'push to protected branch {b} (owner-only)', branch=b,
                              force=force, delete=delete))
        if (force or delete) and hit_s and not hit_p:
            f.append(_finding('PROTECTED_PUSH', f'{"force" if force else "delete"} push to the shared automation '
                                                 f'branch {hit_s[0]} rewrites history other agents build on',
                              branch=hit_s[0]))
    if mirror:
        f.append(_finding('PROTECTED_PUSH', 'git push --mirror/--all/--branches (or a mirror/matching config) '
                                             'touches every branch, protected ones included'))
    if via_xargs:
        f.append(_finding('PROTECTED_PUSH', 'git push run through xargs: its refspecs arrive on stdin at run time '
                                             '(fail-closed: treated as protected)'))
    elif (force or delete) and any(d is None for d in norm):
        f.append(_finding('PROTECTED_PUSH', 'force or delete push whose destination branch cannot be determined '
                                             '(fail-closed: treated as protected)'))
    if not pol['readable'] and (force or delete):
        f.append(_finding('PROTECTED_PUSH', f'branch policy unreadable ({pol.get("why")}); every force or delete push '
                                             f'is treated as protected'))
    return f


# ------------------------------------------------------------------ gh
GH_API_VALUE = {'-H': 'header', '--header': 'header', '-f': 'raw', '--raw-field': 'raw', '-F': 'field',
                '--field': 'field', '-X': 'method', '--method': 'method', '--input': 'input', '-q': 'jq',
                '--jq': 'jq', '-t': 'template', '--template': 'template', '--hostname': 'hostname', '-p': 'preview',
                '--preview': 'preview', '--cache': 'cache'}


def _gh_api_args(sub):
    """(endpoint, method, fields, input file) of a `gh api` argv tail (after 'api')."""
    endpoint, method, fields, inp, i = None, None, {}, None, 0
    while i < len(sub):
        t = str(sub[i])
        key, val = None, None
        if t in GH_API_VALUE:
            key, val = GH_API_VALUE[t], (str(sub[i + 1]) if i + 1 < len(sub) else '')
            i += 1
        elif t.startswith('--') and '=' in t and t.split('=', 1)[0] in GH_API_VALUE:
            key, val = GH_API_VALUE[t.split('=', 1)[0]], t.split('=', 1)[1]
        elif re.match(r'^-[HfFXqtp].', t):
            key, val = GH_API_VALUE[t[:2]], t[2:]
        elif t.startswith('-'):
            pass
        elif endpoint is None:
            endpoint = t
        if key == 'method':
            method = val.upper()
        elif key in ('raw', 'field') and '=' in val:
            k, v = val.split('=', 1)
            fields.setdefault(re.sub(r'\[\]$', '', k), v)
        elif key in ('raw', 'field'):
            fields.setdefault(val, '')
        elif key == 'input':
            inp = val
        i += 1
    if method is None:
        method = 'POST' if (fields or inp) else 'GET'
    return endpoint or '', method, fields, inp


def _read_body(path, cwd):
    """(text, readable) of a request body file named by --input or a field's @file value."""
    if path in ('-', None):
        return '', False
    a = _abs(path, cwd)
    try:
        return open(a, errors='replace').read(1 << 20), True
    except (OSError, TypeError):
        return '', False


def _gh_findings(argv, cwd, pol):
    f = []
    if len(argv) < 2 or os.path.basename(argv[0]) != 'gh':
        return f
    sub = [str(x) for x in argv[1:]]
    while sub and sub[0] in ('-R', '--repo'):
        sub = sub[2:]
    protected, shared = set(pol['protected']), set(pol['shared'])
    if sub[:2] == ['pr', 'merge']:
        f.append(_finding('UNAUTHORIZED_MERGE', 'gh pr merge (merging is the owner\'s)'))
    if sub[:2] == ['pr', 'review'] and any(a in ('--approve', '-a') or re.match(r'^-[a-z]*a', a) for a in sub[2:]
                                           if a.startswith('-') and not a.startswith('--b')):
        f.append(_finding('SELF_APPROVAL', 'gh pr review --approve: an agent may not approve'))
    if sub[:2] == ['workflow', 'run'] or sub[:2] == ['run', 'rerun']:
        f.append(_finding('WORKFLOW_DISPATCH', f'gh {" ".join(sub[:2])} starts an Actions run'))
    if sub[:2] == ['repo', 'sync']:
        ops, opts = _operands(sub[2:], short_val='bs', long_val=('branch', 'source'))
        br = next((v for k, v in opts if k in ('b', 'branch')), None)
        if ops and (br is None or br in protected or (br in shared and any(k == 'force' for k, _ in opts))):
            f.append(_finding('PROTECTED_PUSH', f'gh repo sync {ops[0]} writes the remote branch '
                                                 f'{br or "DEFAULT (main)"}'))
    if sub[:1] == ['api']:
        f.extend(_gh_api_findings(sub[1:], cwd, protected, shared))
    return f


def _gh_api_findings(sub, cwd, protected, shared):
    f = []
    endpoint, method, fields, inp = _gh_api_args(sub)
    body, readable = ('', True)
    if inp:
        body, readable = _read_body(inp, cwd)
    for k, v in list(fields.items()):
        if v.startswith('@'):
            t, ok = _read_body(v[1:], cwd)
            fields[k] = t
            readable = readable and ok
    text = body + '\n' + '\n'.join(f'{k}={v}' for k, v in fields.items())
    path = re.sub(r'^https?://[^/]+/', '', endpoint).split('?', 1)[0].lstrip('/')
    if path == 'graphql':
        if not readable:
            f.append(_finding('UNAUTHORIZED_MERGE', 'gh api graphql with a body this guard cannot read '
                                                     '(fail-closed: treated as protected)'))
        if re.search(r'\b(mergePullRequest|enablePullRequestAutoMerge|mergeBranch)\b', text):
            f.append(_finding('UNAUTHORIZED_MERGE', 'gh api graphql merge mutation'))
        if re.search(r'\b(addPullRequestReview|submitPullRequestReview)\b', text) and re.search(r'\bAPPROVE\b', text):
            f.append(_finding('SELF_APPROVAL', 'gh api graphql review mutation with event APPROVE'))
        if re.search(r'\b(createRef|updateRef|updateRefs|deleteRef|createBranchProtectionRule|'
                     r'updateBranchProtectionRule|deleteBranchProtectionRule|createRepositoryRuleset|'
                     r'updateRepositoryRuleset|deleteRepositoryRuleset)\b', text):
            f.append(_finding('PROTECTED_PUSH', 'gh api graphql writes refs or branch protection'))
        if re.search(r'\bcreateCommitOnBranch\b', text):
            names = re.findall(r'branchName\W+([\w./-]+)', text)
            if not names or any(re.sub(r'^refs/heads/', '', x) in protected for x in names):
                f.append(_finding('PROTECTED_PUSH', 'gh api graphql createCommitOnBranch on a protected or '
                                                     'undetermined branch'))
        return f
    if method == 'GET':
        return f
    if re.search(r'(^|/)pulls/\d+/merge$|(^|/)merges$', path):
        f.append(_finding('UNAUTHORIZED_MERGE', f'gh api {method} {path}'))
    elif re.search(r'(^|/)pulls/\d+/reviews(/\d+/events)?$', path):
        ev = (fields.get('event') or '') + body
        if 'APPROVE' in ev.upper() or (inp and not readable):
            f.append(_finding('SELF_APPROVAL', f'gh api {method} {path} with event APPROVE'
                                               f'{" (body unreadable: fail-closed)" if inp and not readable else ""}'))
    elif re.search(r'(^|/)git/refs(/|$)', path):
        ref = path.split('git/refs/', 1)[1] if 'git/refs/' in path else (fields.get('ref') or '')
        ref = re.sub(r'^(refs/)?heads/', '', ref)
        if ref.startswith(('tags/', 'refs/tags/')):
            pass
        elif not ref or ref in protected:
            f.append(_finding('PROTECTED_PUSH', f'gh api {method} {path} writes ref {ref or "UNDETERMINED"}'))
        elif ref in shared and (method == 'DELETE' or str(fields.get('force', '')).lower() == 'true'):
            f.append(_finding('PROTECTED_PUSH', f'gh api {method} {path} rewrites the shared branch {ref}'))
    elif re.search(r'(^|/)branches/[^/]+/protection|(^|/)rulesets(/|$)', path):
        f.append(_finding('PROTECTED_PUSH', f'gh api {method} {path} changes branch protection'))
    elif re.search(r'actions/workflows/[^/]+/dispatches$|(^|/)dispatches$|actions/runs/\d+/(rerun|rerun-failed-jobs)$|'
                   r'actions/jobs/\d+/rerun$', path):
        f.append(_finding('WORKFLOW_DISPATCH', f'gh api {method} {path}'))
    elif re.search(r'(^|/)merge-upstream$', path):
        br = fields.get('branch')
        if not br or br in protected:
            f.append(_finding('PROTECTED_PUSH', f'gh api {method} {path} writes branch {br or "UNDETERMINED"}'))
    elif '/contents/' in path:
        rel = _norm_repo_path(path.split('/contents/', 1)[1])
        br = fields.get('branch')
        if not br or br in protected:
            f.append(_finding('PROTECTED_PUSH', f'gh api {method} {path} on branch {br or "DEFAULT (main)"}'))
        if _is_approval_path(rel) or _is_safeguard(rel):
            f.append(_finding('SELF_APPROVAL' if _is_approval_path(rel) else 'SAFEGUARD_MODIFIED',
                              f'gh api {method} writes {rel}'))
    return f


# ------------------------------------------------------------------ MCP
_MCP = re.compile(r'^mcp__(?P<srv>.+?)__(?P<name>[^_].*)$')
#: actions_run_trigger methods that do not start a run; every other method is read as starting one (fail-closed)
_ACTIONS_NON_STARTING = {'cancel_workflow_run', 'delete_workflow_run_logs'}


def _mcp_findings(tool, ti, pol):
    m = _MCP.match(tool)
    if not m or 'github' not in m.group('srv').lower():
        return []
    name, out = m.group('name'), []
    protected = set(pol['protected'])
    branch = str(ti.get('branch') or ti.get('ref') or '').replace('refs/heads/', '')
    if name in ('merge_pull_request', 'enable_pr_auto_merge'):
        out.append(_finding('UNAUTHORIZED_MERGE', f'{name} (merging is the owner\'s)'))
    if name == 'pull_request_review_write' and str(ti.get('event', '')).upper() == 'APPROVE':
        out.append(_finding('SELF_APPROVAL', 'an agent approving a pull request'))
    if name == 'actions_run_trigger' and str(ti.get('method') or '') not in _ACTIONS_NON_STARTING:
        out.append(_finding('WORKFLOW_DISPATCH', f'actions_run_trigger {ti.get("method")} starts an Actions run'))
    if name == 'create_branch' and branch in protected:
        out.append(_finding('PROTECTED_PUSH', f'create_branch {branch}'))
    if name in ('push_files', 'create_or_update_file', 'delete_file'):
        if branch in protected or not branch:
            out.append(_finding('PROTECTED_PUSH', f'{name} on branch {branch or "UNSPECIFIED (default branch)"}'))
        files = [x.get('path') for x in (ti.get('files') or []) if isinstance(x, dict)] + [ti.get('path')]
        for p in filter(None, (_norm_repo_path(x) for x in files if x)):
            if _is_approval_path(p):
                out.append(_finding('SELF_APPROVAL', f'{name} writes approval or owner-authority file {p}'))
            elif _is_safeguard(p):
                out.append(_finding('SAFEGUARD_MODIFIED', f'{name} writes safeguard {p}'))
    return out


# ------------------------------------------------------------------ classification
def classify(payload):
    """[finding] for one PreToolUse payload. Raises only on programming errors (observe() records those)."""
    if not isinstance(payload, dict):
        return [_finding('GUARD_INPUT_INVALID', f'the hook payload is a {type(payload).__name__}, not an object')]
    tool = str(payload.get('tool_name') or '')
    ti = payload.get('tool_input') or {}
    if not isinstance(ti, dict):
        return [_finding('GUARD_INPUT_INVALID', 'tool_input is not an object')]
    cwd = payload.get('cwd')
    pol = policy()
    out = []
    if tool == 'Bash':
        cmd = str(ti.get('command') or '')
        if len(cmd.encode('utf-8', 'replace')) > MAX_COMMAND_BYTES:
            return [_finding('GUARD_INPUT_INVALID', f'command of {len(cmd)} chars exceeds {MAX_COMMAND_BYTES} bytes; '
                                                     f'not classified (fail-closed)')]
        for c in parse(cmd, cwd):
            env, a, xargs = _strip_prefix(c.argv, c.env)
            if not a:
                continue
            gp = _git_parts(a)
            if gp:
                out.extend(_git_findings(env, gp[0], gp[1], gp[2], c.cwd, pol, via_xargs=xargs))
            out.extend(_gh_findings(a, c.cwd, pol))
            if any(str(x).endswith('coordination/mode.py') or str(x) == 'mode.py' for x in a[:2]) and 'set' in a:
                out.append(_finding('MODE_CHANGE', 'coordination/mode.py set (recorded, not protected)'))
    out.extend(_mcp_findings(tool, ti, pol))
    written = _written_text(ti) + (str(ti.get('command') or '') if tool == 'Bash' else '')
    for absp, how in write_targets(payload):
        gi = _git_internal(absp)
        rel = None
        try:
            rel = str(pathlib.Path(absp).relative_to(ROOT))
        except ValueError:
            pass
        if gi == 'hooks':
            out.append(_finding('HOOK_PATH_CHANGE', f'{how} writes, removes or changes the hooks directory: {absp}'))
        elif gi == 'config':
            out.append(_finding('HOOK_PATH_CHANGE', f'{how} writes the git config file directly ({absp}); it can set '
                                                     f'core.hooksPath'))
        elif SETTINGS_FILE.search(absp):
            out.append(_finding('SAFEGUARD_MODIFIED', f'{how} writes a Claude Code settings file (hook registration): '
                                                       f'{absp}' + ('; sets disableAllHooks'
                                                                    if 'disableAllHooks' in written else '')))
        elif _is_approval_path(rel):
            out.append(_finding('SELF_APPROVAL', f'{how} writes approval or owner-authority file {rel}'))
        elif _is_safeguard(rel):
            out.append(_finding('SAFEGUARD_MODIFIED', f'{how} writes safeguard {rel}'))
        elif rel == 'coordination/PROJECT_STATE.json' and 'mode_declared' in written:
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
    try:
        ti = payload.get('tool_input') or {}
        s = ti.get('command') or ti.get('file_path') or ti.get('path') or json.dumps(ti, default=str)[:200]
        return str(s)[:300]
    except Exception:  # noqa: BLE001
        return repr(payload)[:300]


def _log(rec):
    p = pathlib.Path(os.environ.get('NFL_GUARD_REPORT_LOG') or LOG_DEFAULT)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, 'a') as fh:
            fh.write(json.dumps(rec, sort_keys=True, default=str) + '\n')
    except OSError:
        pass                           # the report is best-effort; the decision path below does not depend on it


def _deny(why):
    return {'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'deny',
                                   'permissionDecisionReason': f'GIT_GUARD: {why}. Protected operations are the '
                                   f'owner\'s; no agent-written file authorizes one.'}}


def observe(payload):
    """Classify, record, and return a hook output ONLY when enforcing. In REPORT_ONLY this always returns None.
    Nothing in here may raise: a failure is itself recorded as a would-deny GUARD_ERROR."""
    now = dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    try:
        findings = classify(payload)
    except Exception as e:  # noqa: BLE001 -- fail-closed: an error is a DENY, never a silent allow
        findings = [_finding('GUARD_ERROR', f'{type(e).__name__}: {e}')]
    would = 'DENY' if any(f['protected'] for f in findings) else 'ALLOW'
    if findings:
        tool = payload.get('tool_name') if isinstance(payload, dict) else None
        _log({'at': now, 'spec': SPEC_VERSION, 'enforcement': ENFORCEMENT, 'tool': tool,
              'summary': _summary(payload) if isinstance(payload, dict) else repr(payload)[:300],
              'would_decision': would, 'findings': findings})
    if ENFORCEMENT == 'ENFORCE' and would == 'DENY':
        return _deny('; '.join(f'{f["rule"]}: {f["detail"]}' for f in findings if f['protected'])[:900])
    return None


def observe_invalid(raw):
    """An unparseable hook payload: recorded with would-decision DENY (fail-closed)."""
    now = dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    _log({'at': now, 'spec': SPEC_VERSION, 'enforcement': ENFORCEMENT, 'tool': None,
          'summary': str(raw or '')[:200], 'would_decision': 'DENY',
          'findings': [_finding('GUARD_INPUT_INVALID', 'the hook payload is not valid JSON')]})
    if ENFORCEMENT == 'ENFORCE':
        return _deny('unreadable hook payload (fail-closed)')
    return None
