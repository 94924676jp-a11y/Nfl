"""OWNER RULE 3 (2026-10-02): BUILD / VERIFY / OPERATE / RESEARCH, with enforceable write boundaries.

For each mode: a POSITIVE control (a forbidden path in the changed set -> MODE_BOUNDARY_VIOLATED)
and a NEGATIVE control (an allowed path -> CLEAN). Plus: no mode in force is NOT_EXECUTED, never
CLEAN; the pinned-mode refusal (an agent `mode.py set` under mode_declared is refused); every mode
change writes a HANDOFF_LOG row; and the PreToolUse hook, pipe-tested with synthesized JSON, denies
an OPERATE-mode write to nfl/sim/game.py and stays silent on an artifact write.

The self-certification refusal (a BUILD-mode suite row cannot mark PROJECT_STATE.test_surface
current) is checked in test_mode_self_certification once refresh_state carries it.
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from coordination import mode as M                       # noqa: E402
from coordination.orchestrator import locks as L         # noqa: E402
from nfl.tests._controls import observe                  # noqa: E402

PASSED = FAILED = 0


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(ok)


CASES = {
    # mode: (forbidden paths -> VIOLATED, allowed paths -> CLEAN)
    'BUILD': (['coordination/AUTOMATION_POLICY.json'], ['nfl/sim/game.py', 'nfl/tests/test_x.py']),
    'VERIFY': (['nfl/production/qb_v1.py', 'nfl/tests/run_suite.py'],
               ['nfl/tests/test_x.py', 'coordination/HANDOFF_LOG.jsonl']),
    'OPERATE': (['nfl/sim/game.py', 'nfl/tools/proj_v1.py', 'coordination/PROJECT_STATE.json'],
                ['nfl/dfs/salaries/BOARD.json', 'nfl/production/runs/r1/SEAL.json',
                 'nfl/production/READINESS.json', 'nfl/vintage_manifest.jsonl']),
    'RESEARCH': (['nfl/production/qb_v1.py', 'nfl/tools/proj_v1.py'],
                 ['nfl/research/x/y.py', 'nfl/tests/test_y.py', 'nfl/derived/z.npy']),
}


def test_01_every_mode_has_a_positive_and_a_negative_control():
    print('\n1. the boundary judge, per mode')
    for mode, (bad, good) in CASES.items():
        o = L.mode_boundary(bad, mode)
        observe(f'coordination.orchestrator.locks:mode_boundary:VIOLATED', o)
        check(f'{mode}: forbidden {bad} -> VIOLATED naming each path',
              o['state'] == 'VIOLATED' and {v['path'] for v in o['violations']} == set(bad), str(o))
        o = L.mode_boundary(good, mode)
        check(f'  {mode}: allowed {good} -> CLEAN', o['state'] == 'CLEAN', str(o))
        try:
            L.enforce_mode_boundary(bad, mode)
            check(f'  {mode}: enforce_mode_boundary raises', False, 'did not raise')
        except L.Refusal as e:
            observe('coordination.orchestrator.locks:enforce_mode_boundary:MODE_BOUNDARY_VIOLATED', e.code)
            check(f'  {mode}: enforce_mode_boundary raises MODE_BOUNDARY_VIOLATED',
                  e.code == 'MODE_BOUNDARY_VIOLATED' and mode in str(e), str(e)[:160])


def test_02_research_cannot_promote_through_a_default_switch_line():
    print('\n2. RESEARCH: a default-switch line is a promotion wherever it sits')
    o = L.mode_boundary(['nfl/research/arm/notes.py'], 'RESEARCH',
                        diff="+MARKET_ARM = 'football'\n")
    check('a diff that changes MARKET_ARM = is VIOLATED even in an allowed research path',
          o['state'] == 'VIOLATED' and o['violations'][0]['rule'] == 'forbidden_diff_line', str(o))
    o = L.mode_boundary(['nfl/research/arm/notes.py'], 'RESEARCH', diff='+x = MARKET_ARM\n')
    check('  reading the switch is not changing it', o['state'] == 'CLEAN', str(o))


def test_03_no_mode_in_force_is_not_executed_not_clean():
    print('\n3. no mode -> NOT_EXECUTED (rule 1 applied to rule 3)')
    o = L.mode_boundary(['nfl/sim/game.py'], None)
    observe('coordination.orchestrator.locks:mode_boundary:NOT_EXECUTED', o)
    check('no mode in force is NOT_EXECUTED with cause EMPTY_INPUT, never CLEAN',
          o['state'] == 'NOT_EXECUTED' and o['cause'] == 'EMPTY_INPUT', str(o))


def _temp_state(doc: dict):
    td = tempfile.mkdtemp(prefix='mode_')
    sp = pathlib.Path(td) / 'PROJECT_STATE.json'
    sp.write_text(json.dumps(doc))
    hp = pathlib.Path(td) / 'HANDOFF_LOG.jsonl'
    hp.write_text('')
    return sp, hp


def _with_env(sp, hp):
    saved = {k: os.environ.get(k) for k in ('NFL_PROJECT_STATE', 'NFL_HANDOFF_LOG')}
    os.environ['NFL_PROJECT_STATE'] = str(sp)
    os.environ['NFL_HANDOFF_LOG'] = str(hp)
    return saved


def _restore(saved):
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


def test_04_set_writes_the_mode_and_a_handoff_row_and_respects_the_owner_pin():
    print('\n4. mode.py set: measured mode, logged; pinned mode refused')
    sp, hp = _temp_state({'reading_rule': 'x', 'test_surface': {}})
    saved = _with_env(sp, hp)
    try:
        cur = M.read()
        check('a state with no mode block reads as mode None', cur['mode'] is None, str(cur))
        rec = M.set_mode('VERIFY', 'proving rule 3', by='agent')
        doc = json.loads(sp.read_text())
        check('  set writes mode.mode with since_commit, since_utc, set_by, reason',
              doc['mode']['mode'] == 'VERIFY' and doc['mode']['set_by'] == 'agent'
              and doc['mode']['reason'] == 'proving rule 3' and 'since_utc' in doc['mode'], str(doc['mode']))
        rows = [json.loads(ln) for ln in hp.read_text().splitlines()]
        check('  and appends one MODE_SET row to the handoff log',
              len(rows) == 1 and rows[0]['event'] == 'MODE_SET' and rows[0]['to_mode'] == 'VERIFY' and rows[0]['to_status'] is None, str(rows))
        try:
            M.set_mode('BUILD', '', by='agent')
            check('  a change without a reason is refused', False, 'accepted')
        except ValueError as e:
            check('  a change without a reason is refused', 'MODE_REASON_REQUIRED' in str(e), str(e))
        doc['mode_declared'] = {'mode': 'OPERATE', 'set_by': 'owner', 'reason': 'live slate'}
        sp.write_text(json.dumps(doc))
        cur = M.read()
        check('  mode_declared pins: read() reports OPERATE from mode_declared',
              cur['mode'] == 'OPERATE' and cur['pinned'] and cur['source'] == 'mode_declared', str(cur))
        try:
            M.set_mode('BUILD', 'I want to refactor', by='agent')
            check('  positive control: an agent set under a pinned mode is REFUSED', False, 'accepted')
        except PermissionError as e:
            observe('coordination.mode:set_mode:MODE_PINNED_BY_OWNER', str(e).split(':')[0])
            check('  positive control: an agent set under a pinned mode is REFUSED',
                  'MODE_PINNED_BY_OWNER' in str(e), str(e)[:120])
        check('  and the pinned mode is untouched', M.read()['mode'] == 'OPERATE')
        rec = M.set_mode('BUILD', 'owner lifts the slate', by='owner')
        check('  negative control: the owner may set it (recorded as set_by owner)',
              rec['set_by'] == 'owner' and json.loads(sp.read_text())['mode']['mode'] == 'BUILD')
    finally:
        _restore(saved)


def test_05_the_hook_denies_an_operate_write_to_code_and_allows_an_artifact():
    print('\n5. PreToolUse hook, pipe-tested')
    sp, hp = _temp_state({'reading_rule': 'x', 'mode': {'mode': 'OPERATE', 'set_by': 'agent'}})
    env = dict(os.environ, NFL_PROJECT_STATE=str(sp), NFL_HANDOFF_LOG=str(hp))
    guard = str(_REPO / 'coordination' / 'mode_guard.py')

    def run(payload):
        r = subprocess.run([sys.executable, guard], input=json.dumps(payload), capture_output=True,
                           text=True, env=env, cwd=str(_REPO), timeout=120)
        return r.returncode, r.stdout.strip(), r.stderr.strip()

    rc, out, err = run({'tool_name': 'Write', 'tool_input': {'file_path': 'nfl/sim/game.py', 'content': 'x'},
                        'cwd': str(_REPO)})
    d = json.loads(out) if out else {}
    observe('coordination.mode_guard:decide:deny',
            (d.get('hookSpecificOutput') or {}).get('permissionDecision'))
    check('positive control: OPERATE + Write nfl/sim/game.py -> permissionDecision deny',
          rc == 0 and (d.get('hookSpecificOutput') or {}).get('permissionDecision') == 'deny'
          and 'MODE_BOUNDARY_VIOLATED' in (d.get('hookSpecificOutput') or {}).get('permissionDecisionReason', ''),
          f'rc={rc} out={out[:200]} err={err[:200]}')
    rc, out, err = run({'tool_name': 'Bash', 'tool_input': {'command': "echo x > nfl/tools/proj_v1.py"},
                        'cwd': str(_REPO)})
    check('  Bash redirection into code is denied too',
          rc == 0 and 'deny' in out, f'rc={rc} out={out[:200]} err={err[:200]}')
    rc, out, err = run({'tool_name': 'Write', 'tool_input': {'file_path': 'nfl/dfs/salaries/BOARD.json', 'content': '{}'},
                        'cwd': str(_REPO)})
    check('  negative control: an artifact write gets no decision (silent allow)',
          rc == 0 and out == '', f'rc={rc} out={out[:200]} err={err[:200]}')
    rc, out, err = run({'tool_name': 'Bash', 'tool_input': {'command': 'git status --short'}, 'cwd': str(_REPO)})
    check('  a read-only command gets no decision', rc == 0 and out == '', f'out={out[:200]}')
    rc, out, err = run({'tool_name': 'Edit', 'tool_input': {'file_path': 'nfl/research/a.py', 'old_string': 'a',
                                                           'new_string': "MARKET_ARM = 'x'"}, 'cwd': str(_REPO)})
    check('  OPERATE + Edit under nfl/research is denied (code is frozen in OPERATE)',
          'deny' in out, out[:200])
    sp.write_text(json.dumps({'reading_rule': 'x'}))
    rc, out, err = run({'tool_name': 'Write', 'tool_input': {'file_path': 'nfl/sim/game.py', 'content': 'x'},
                        'cwd': str(_REPO)})
    check('  with no mode in force the hook makes no decision (and the retrospective check says NOT_EXECUTED)',
          rc == 0 and out == '', out[:200])


def test_06_the_hook_is_registered_in_the_project_settings():
    print('\n6. registration')
    p = _REPO / '.claude' / 'settings.json'
    check('.claude/settings.json exists in the NFL repository', p.exists())
    if p.exists():
        doc = json.loads(p.read_text())
        hooks = doc.get('hooks', {}).get('PreToolUse', [])
        cmds = [h.get('command', '') for g in hooks for h in g.get('hooks', [])]
        check('  a PreToolUse hook runs coordination/mode_guard.py',
              any('mode_guard.py' in c for c in cmds), str(cmds))
        check('  matched on Edit|Write|...|Bash',
              any('Bash' in g.get('matcher', '') and 'Write' in g.get('matcher', '') for g in hooks),
              str([g.get('matcher') for g in hooks]))
    check('  CAVEAT recorded: this session is rooted in another repository, so the hook firing in a '
          'live session is proven only in a session rooted here; the pipe-test above is the proof '
          'available now', True)


def test_07_build_cannot_self_certify_the_test_surface():
    print('\n7. refresh_state.certify_test_surface: BUILD may not self-certify')
    from coordination import refresh_state as RS
    import json as _j
    saved = RS.REPO
    with tempfile.TemporaryDirectory() as td:
        root = pathlib.Path(td)
        (root / 'nfl' / 'tests').mkdir(parents=True)
        prog = root / 'nfl' / 'tests' / '_suite_progress.jsonl'
        try:
            RS.REPO = root
            prog.write_text('')
            r = RS.certify_test_surface('abc1234')
            observe('coordination.refresh_state:certify_test_surface:NOT_EXECUTED', r['certification'])
            check('no verdict row -> NOT_EXECUTED (cause EMPTY_INPUT), never CURRENT',
                  r['certification'] == 'NOT_EXECUTED' and r['cause'] == 'EMPTY_INPUT', str(r))
            row = {'phase': 'suite_done', 'verdict': 'PASS', 'n_modules': 5, 'n_checks_executed': 40,
                   'n_failing': 0, 'mode': 'BUILD', 'head': 'abc1234', 'run_id': 'x', 't': 1.0}
            prog.write_text(_j.dumps(row) + '\n')
            r = RS.certify_test_surface('abc1234')
            observe('coordination.refresh_state:certify_test_surface:NOT_CERTIFIED', r['certification'])
            check('positive control: a PASS row produced in BUILD mode at HEAD is NOT_CERTIFIED '
                  '(self-certification)', r['certification'] == 'NOT_CERTIFIED'
                  and any('BUILD' in w for w in r['why']), str(r)[:240])
            row['mode'] = 'VERIFY'; row['head'] = 'ffff999'
            prog.write_text(_j.dumps(row) + '\n')
            r = RS.certify_test_surface('abc1234')
            check('  a VERIFY row at another head is NOT_CERTIFIED (stale)',
                  r['certification'] == 'NOT_CERTIFIED' and any('head' in w for w in r['why']), str(r)[:240])
            row['head'] = 'abc1234'
            prog.write_text(_j.dumps(row) + '\n')
            r = RS.certify_test_surface('abc1234')
            check('  negative control: a full VERIFY-mode PASS at this head is CURRENT',
                  r['certification'] == 'CURRENT' and r['certified_by_mode'] == 'VERIFY', str(r)[:240])
            row['verdict'] = 'FAIL'
            prog.write_text(_j.dumps(row) + '\n')
            r = RS.certify_test_surface('abc1234')
            check('  and a VERIFY run that FAILED does not certify either',
                  r['certification'] == 'NOT_CERTIFIED', str(r)[:200])
        finally:
            RS.REPO = saved


def test_zz_every_check_passed():
    """The module's own counter, re-raised so a failure turns this module RED."""
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for name, fn in sorted((k, v) for k, v in globals().items() if k.startswith('test_') and callable(v)):
        try:
            fn()
        except AssertionError as e:
            print(f'  {name}: {e}')
    print(f'\nPASSED {PASSED}  FAILED {FAILED}')
    sys.exit(1 if FAILED else 0)
