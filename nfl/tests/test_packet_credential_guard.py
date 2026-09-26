#!/usr/bin/env python3.12
"""No credential may enter a committed packet, proven on the disk.

`assert_packet_is_clean` is the most consequential guard in the census's
unproven population: a packet is committed evidence, so a secret in one is
published rather than stored, and publication is not reversible. The census had
it with a direct unit test and NO load-bearing proof -- which is the exact gap
the standard here exists to close, because a unit test on the matcher says
nothing about whether a file appears on disk.

THE PROTECTED ACTION IS A FILE, so the proof inspects the filesystem:

    body = json.dumps(packet, indent=1, sort_keys=True) + '\\n'
    assert_packet_is_clean(body)      # raises
    p.write_text(body)                # never reached

Every credential in this file is an obviously fake shape -- a literal prefix
followed by repeated letters. Nothing here is a real key, and the benign cases
are as important as the dirty ones: a matcher that refuses "the OPENAI_API_KEY
env var" in a docstring would be turned off within a week.
"""
from __future__ import annotations

import json
import pathlib
import shutil
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))

from coordination.orchestrator import claude_code_transport as T
from nfl.tests import bypass as BP

passed = failed = 0
MOD = 'coordination.orchestrator.claude_code_transport'
CODE = 'PACKET_CONTAINS_SECRET'

#: Fake by construction: a real prefix plus repeated filler. Never a live key.
DIRTY = {
    'anthropic key shape': 'sk-ant-' + 'A' * 20,
    'openai project shape': 'sk-proj-' + 'B' * 20,
    'perplexity shape': 'pplx-' + 'c' * 20,
    'github token shape': 'ghp_' + 'D' * 24,
    'anthropic assignment': 'ANTHROPIC_API_KEY=notarealkey',
    'openai assignment': 'OPENAI_API_KEY: notarealkey',
    'oauth assignment': 'CLAUDE_CODE_OAUTH_TOKEN = notarealtoken',
}
#: Text that names a credential WITHOUT carrying one. All must pass.
BENIGN = (
    'sk-ant',
    'ANTHROPIC_API_KEY is read from the environment',
    'the OPENAI_API_KEY env var',
    'ghp_short',
    'a normal sentence about the packet',
    'skip-antler-migration',
)


def check(label, cond, detail=''):
    global passed, failed
    if cond:
        passed += 1
    else:
        failed += 1
        print(f'  FAIL {label}  {detail}')


def refused(text):
    try:
        T.assert_packet_is_clean(text)
        return None
    except T.PacketRefusal as exc:
        return exc


def test_every_credential_shape_is_refused_by_name():
    for label, secret in sorted(DIRTY.items()):
        exc = refused(json.dumps({'note': secret}))
        check(f'{label} is refused', exc is not None and exc.code == CODE,
              getattr(exc, 'code', 'NOT CAUGHT'))


def test_naming_a_credential_is_not_carrying_one():
    """The inverted half, and it matters as much as the other.

    A matcher that refuses a docstring mentioning OPENAI_API_KEY would be
    switched off by whoever it blocked first, and then nothing would be checked.
    """
    for text in BENIGN:
        check(f'{text[:38]!r} passes', refused(json.dumps({'note': text})) is None,
              'FALSE POSITIVE')


def test_the_refusal_names_what_it_saw_without_reprinting_it():
    exc = refused(json.dumps({'note': DIRTY['anthropic key shape']}))
    check('the refusal exists', exc is not None)
    if exc:
        check('  it says a credential shape was found',
              'credential' in exc.detail, exc.detail[:60])
        check('  and it TRUNCATES the match rather than echoing the secret',
              DIRTY['anthropic key shape'] not in exc.detail,
              'the refusal reprinted the whole secret, which republishes it')


def test_no_file_reaches_disk_when_a_packet_is_dirty():
    """The protected action, inspected rather than inferred."""
    d = pathlib.Path(tempfile.mkdtemp())
    try:
        exc = None
        try:
            T.write_packet({'task_id': 'PROBE-DIRTY',
                            'note': DIRTY['github token shape']}, repo=d)
        except T.PacketRefusal as e:
            exc = e
        check('write_packet refuses', exc is not None and exc.code == CODE,
              getattr(exc, 'code', 'IT WROTE THE PACKET'))
        on_disk = sorted(p.name for p in d.rglob('*.json'))
        check('  and NOTHING was written to disk', not on_disk, on_disk)
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_a_clean_packet_is_written_so_the_guard_is_not_simply_refusing_all():
    d = pathlib.Path(tempfile.mkdtemp())
    try:
        p = T.write_packet({'task_id': 'PROBE-CLEAN',
                            'note': 'no credential here'}, repo=d)
        check('a clean packet IS written', p.exists(), str(p))
        check('  and it lands under the packet directory',
              'ENGINEERING_PACKETS' in str(p), str(p))
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_bypassing_the_guard_lets_the_secret_reach_disk():
    """Which is what makes the checks above proof rather than decoration.

    bypass.py's own warning: a test that would still pass with the guard deleted
    is testing nothing. This guard returns None on success and RAISES on failure,
    so the permissive stub is a no-op returning None.
    """
    d = pathlib.Path(tempfile.mkdtemp())
    try:
        pkt = {'task_id': 'PROBE-BYPASS', 'note': DIRTY['perplexity shape']}
        with BP.guard_bypassed(MOD, 'assert_packet_is_clean', returns=None):
            wrote = None
            try:
                wrote = T.write_packet(pkt, repo=d)
            except T.PacketRefusal:
                wrote = None
        check('with the guard bypassed the dirty packet IS written',
              wrote is not None and wrote.exists(),
              'it was still refused, so something OTHER than this guard '
              'stopped it and these tests do not prove this guard works')
        if wrote and wrote.exists():
            check('  and the secret really is in the file that appeared',
                  DIRTY['perplexity shape'] in wrote.read_text())
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_both_write_sites_are_guarded_not_just_one():
    """build_packet hashes a body and write_packet writes one. A guard on only
    the second would let a dirty packet be hashed and returned to a caller that
    logs it; a guard on only the first would miss a packet mutated afterwards."""
    import ast
    src = (_REPO / 'coordination/orchestrator/claude_code_transport.py').read_text()
    tree = ast.parse(src)
    guarded = set()
    for fn in ast.walk(tree):
        if not isinstance(fn, ast.FunctionDef):
            continue
        for n in ast.walk(fn):
            if isinstance(n, ast.Call) and 'assert_packet_is_clean' in ast.unparse(
                    n.func):
                guarded.add(fn.name)
    for site in ('build_packet', 'write_packet'):
        check(f'{site} calls the guard', site in guarded, sorted(guarded))


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith('test_') and callable(fn):
            fn()
    print(f'test_packet_credential_guard: {passed} ok, {failed} failed')
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
