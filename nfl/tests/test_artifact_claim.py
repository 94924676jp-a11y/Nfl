"""ARTIFACT_CLAIM_WITHOUT_VERIFIED_FILE, including the real SIGPIPE case.

The centrepiece is test C. It does not simulate the 2026-09-18 defect with a
mock; it runs a generator in a subprocess, pipes its stdout into `head`, and
lets the pipe kill it exactly as `dual_board.py | head -22` was killed. Then it
asserts two things that must both hold for the rule to be worth anything:

  * the generator's stdout LOOKED successful -- the same evidence that fooled
    me -- and
  * `artifact_claim.verify` refuses anyway, because it reads the filesystem.

A mock could not establish the first, and the first is the whole reason the
defect was believable.
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

from sportsplatform.governance import artifact_claim as AC              # noqa: E402
from sportsplatform.governance.outcome import Cause, State              # noqa: E402

PASSED = 0
FAILED = 0
NOT_EXECUTED = []


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}: {detail}')


#: A generator with the same shape as the one that failed: print a long table
#: first, write the artifact last. Nothing about it is contrived -- this is the
#: ordinary way a reporting script is written.
#: N_ROWS IS A DETERMINISM REQUIREMENT, NOT A SIZE PREFERENCE. DEF-070.
#:
#: This was 40 rows, and at ~20 bytes a line that is ~800 bytes -- which fits
#: entirely inside the 64 KiB pipe buffer. So the generator normally printed
#: everything without ever blocking, wrote the artifact, and exited: NO SIGPIPE
#: AT ALL. It only died mid-print when scheduling happened to let `head` exit
#: and tear down the read end first, which made the check report either verdict
#: on identical code. Measured 2026-09-26: 0 failing in one full-suite run, 2
#: failing in six consecutive isolated runs, 2 under artificial CPU load, 0
#: immediately after removing it.
#:
#: Exceeding the pipe capacity FORCES the block. `head -5` exits after five
#: lines, the generator's next flush finds no reader, and EPIPE arrives while it
#: is still inside the print loop -- before the write, every time, by the
#: kernel's buffering rather than by luck. 20,000 rows is ~400 KiB, a six-fold
#: margin over the 64 KiB default so the property does not depend on the exact
#: capacity of any one kernel.
#:
#: DO NOT REDUCE THIS to make the test faster. Below the pipe capacity the race
#: returns and the check stops being evidence of anything.
SIGPIPE_ROWS = 20000

GENERATOR = '''
import json, pathlib, sys
out = pathlib.Path(sys.argv[1])
n = int(sys.argv[2]) if len(sys.argv) > 2 else 40
rows = [{"player": f"p{i}", "mean": float(i)} for i in range(n)]
for r in rows:
    print(f"{r['player']:10s} {r['mean']:8.2f}")
print(f"wrote {out}")
out.write_text(json.dumps({"rows": rows}))
'''


def test_A_a_real_artifact_verifies():
    print('\nA. the happy path')
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d) / 'a.json'
        p.write_text(json.dumps({'rows': [1, 2], 'evidence': {}}))
        o = AC.verify(p, schema=['rows', 'evidence'], label='a')
        check('it passes', o.state is State.PASS, f'{o.state}[{o.code}]')
        check('  the hash is computed from the bytes on disk',
              o.evidence['sha256'] ==
              __import__('hashlib').sha256(p.read_bytes()).hexdigest())
        check('  and the value returned is the RESOLVED path, so the caller '
              'reports what was checked',
              o.value == str(p.resolve()), o.value)


def test_B_the_four_ways_a_claim_fails():
    print('\nB. absent, empty, wrong shape, wrong hash')
    with tempfile.TemporaryDirectory() as d:
        d = pathlib.Path(d)
        o = AC.verify(d / 'nope.json', label='absent')
        check('absent file refused', o.state is State.FAIL
              and o.evidence['reason'] == AC.ABSENT, f'{o.state}[{o.code}]')
        check('  with the named code',
              o.code == 'ARTIFACT_CLAIM_WITHOUT_VERIFIED_FILE')
        check('  and cause GOVERNANCE, because nothing external is missing -- '
              'the generator simply did not do what it said',
              o.evidence.get('cause') in (Cause.GOVERNANCE,
                                          Cause.GOVERNANCE.value))
        (d / 'empty.json').write_bytes(b'')
        o = AC.verify(d / 'empty.json', label='empty')
        check('zero-byte file refused', o.state is State.FAIL
              and o.evidence['reason'] == AC.EMPTY, f'{o.state}[{o.code}]')
        (d / 'shape.json').write_text(json.dumps({'other': 1}))
        o = AC.verify(d / 'shape.json', schema=['rows'], label='shape')
        check('present, non-empty, wrong shape refused', o.state is State.FAIL
              and o.evidence['reason'] == AC.SCHEMA, f'{o.state}[{o.code}]')
        check('  naming the missing key', 'rows' in o.detail, o.detail[:100])
        (d / 'h.json').write_text(json.dumps({'rows': []}))
        o = AC.verify(d / 'h.json', expect_sha256='0' * 64, label='hash')
        check('a hash that does not match the bytes is refused',
              o.state is State.FAIL
              and o.evidence['reason'] == AC.HASH_MISMATCH,
              f'{o.state}[{o.code}]')


def test_C_the_sigpipe_case_reproduced_not_mocked():
    print('\nC. THE REGRESSION: stdout succeeds, the file never appears')
    with tempfile.TemporaryDirectory() as d:
        d = pathlib.Path(d)
        gen = d / 'gen.py'
        gen.write_text(GENERATOR)
        target = d / 'board.json'
        # EXACTLY THE SHAPE OF THE COMMAND THAT FAILED: generator | head -n.
        proc = subprocess.run(
            f'{sys.executable} {gen} {target} {SIGPIPE_ROWS} | head -5',
            shell=True, capture_output=True, text=True)
        printed = proc.stdout
        check('the pipeline exits 0, because `head` exits 0',
              proc.returncode == 0, str(proc.returncode))
        check('  stdout looks like a working run', len(printed.splitlines()) == 5,
              repr(printed[:60]))
        # THE DETERMINISM IS ITSELF CHECKED. If a future edit shrinks
        # SIGPIPE_ROWS back under the pipe capacity the race returns, the check
        # starts reporting either verdict, and nothing would say so -- which is
        # exactly the state DEF-070 found it in. A comment cannot enforce that;
        # this can.
        PIPE_CAPACITY = 65536
        est_bytes = SIGPIPE_ROWS * 20
        check('  the generator MUST block: output exceeds the pipe buffer',
              est_bytes > PIPE_CAPACITY * 2,
              f'~{est_bytes} bytes against a {PIPE_CAPACITY}-byte buffer; '
              f'below it the SIGPIPE is a race and this check stops being '
              f'evidence')
        check('  and the file is NOT on disk', not target.exists())
        o = AC.verify(target, schema=['rows'], label='board')
        check('verify REFUSES', o.state is State.FAIL
              and o.code == 'ARTIFACT_CLAIM_WITHOUT_VERIFIED_FILE',
              f'{o.state}[{o.code}]')
        check('  naming FILE_ABSENT', o.evidence['reason'] == AC.ABSENT)
        check('  and explaining why printed output is not evidence',
              'flushed BEFORE' in o.detail, o.detail[:120])
        # THE CONTROL. The same generator, same target, no pipe.
        target2 = d / 'board2.json'
        # THE CONTROL keeps a small count on purpose: no pipe, so nothing
        # should interrupt it, and 40 rows makes that fast.
        p2 = subprocess.run([sys.executable, str(gen), str(target2), '40'],
                            capture_output=True, text=True)
        check('CONTROL: unpiped, the same generator writes the file',
              p2.returncode == 0 and target2.exists())
        ok = AC.verify(target2, schema=['rows'], label='board2')
        check('  and the claim verifies', ok.state is State.PASS,
              f'{ok.state}[{ok.code}]')
        check('  so the refusal above was about the pipe, not the generator',
              ok.evidence['n_bytes'] > 0)


def test_D_a_truncated_write_is_caught_by_schema_not_by_size():
    print('\nD. the failure that looks most like success')
    with tempfile.TemporaryDirectory() as d:
        d = pathlib.Path(d)
        # A JSON write cut off mid-stream: non-zero, non-empty, unparseable.
        (d / 'cut.json').write_text('{"rows": [{"player": "p0", "mea')
        o = AC.verify(d / 'cut.json', schema=['rows'], label='truncated')
        check('a truncated file has non-zero size', (d / 'cut.json').stat().st_size > 0)
        check('  and is still refused, on schema', o.state is State.FAIL
              and o.evidence['reason'] == AC.SCHEMA, f'{o.state}[{o.code}]')
        # CSV header-only, which a size check would pass.
        (d / 'h.csv').write_text('a,b,c\n')
        o = AC.verify(d / 'h.csv', schema=['a', 'b', 'c'], min_bytes=1,
                      label='header only')
        check('  a header-only CSV passes schema but can be caught on size',
              o.state is State.PASS, f'{o.state}[{o.code}]')
        o2 = AC.verify(d / 'h.csv', schema=['a', 'b', 'c'], min_bytes=100,
                       label='header only')
        check('    with an explicit min_bytes', o2.state is State.FAIL
              and o2.evidence['reason'] == AC.EMPTY)
        o3 = AC.verify(d / 'h.csv', schema=['a', 'b', 'missing'],
                       label='wrong columns')
        check('  and a CSV missing a declared column is refused',
              o3.state is State.FAIL and o3.evidence['reason'] == AC.SCHEMA)


def test_E_the_reported_path_must_be_the_verified_path():
    print('\nE. a claim cannot describe one file while checking another')
    with tempfile.TemporaryDirectory() as d:
        d = pathlib.Path(d)
        (d / 'real.json').write_text(json.dumps({'rows': []}))
        o = AC.verify(d / 'real.json', schema=['rows'],
                      reported_as=d / 'something_else.json', label='mismatch')
        check('a mismatched reported path is refused', o.state is State.FAIL
              and o.evidence['reason'] == AC.PATH_MISMATCH,
              f'{o.state}[{o.code}]')
        o2 = AC.verify(d / 'real.json', schema=['rows'],
                       reported_as=d / 'real.json', label='match')
        check('  and the matching one passes', o2.state is State.PASS)


def test_F_claim_prints_from_the_verification_not_the_intention():
    print('\nF. the line a generator prints is produced BY the check')
    import contextlib
    with tempfile.TemporaryDirectory() as d:
        d = pathlib.Path(d)
        buf = __import__('io').StringIO()
        with contextlib.redirect_stdout(buf):
            o = AC.claim(d / 'gone.json', label='gone')
        out = buf.getvalue()
        check('a missing artifact prints the refusal, not a success line',
              'ARTIFACT_CLAIM_WITHOUT_VERIFIED_FILE' in out and 'VERIFIED /' not in out,
              repr(out[:80]))
        check('  and returns FAIL', o.state is State.FAIL)
        (d / 'there.json').write_text(json.dumps({'rows': [1]}))
        buf2 = __import__('io').StringIO()
        with contextlib.redirect_stdout(buf2):
            AC.claim(d / 'there.json', schema=['rows'], label='there')
        check('  a real artifact prints a line carrying size and hash',
              'VERIFIED' in buf2.getvalue() and 'sha256' in buf2.getvalue(),
              repr(buf2.getvalue()[:90]))


def test_G_the_dfs_generators_claim_their_outputs():
    print('\nG. the rule is applied, not merely available')
    import ast
    expected = {
        'nfl/dfs/scoring/dual_board.py',
        'nfl/dfs/showdown/captain_metrics.py',
        'nfl/dfs/showdown/optimal_worlds.py',
        'nfl/dfs/showdown/scenarios.py',
        'nfl/dfs/showdown/correlation.py',
        'nfl/production/ownership_audit.py',
    }
    for rel in sorted(expected):
        src = (_REPO / rel).read_text()
        uses = ('artifact_claim' in src
                and ('claim(' in src or 'claim_or_raise(' in src))
        check(f'  {rel} claims its artifact', uses)
    # And nothing in those files announces a path with a bare print.
    offenders = []
    for rel in sorted(expected):
        for line in (_REPO / rel).read_text().splitlines():
            s = line.strip()
            if s.startswith('print(') and "wrote" in s:
                offenders.append(f'{rel}: {s[:60]}')
    check('no generator still prints a bare "wrote <path>" line',
          not offenders, str(offenders))


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for fn in (test_A_a_real_artifact_verifies,
               test_B_the_four_ways_a_claim_fails,
               test_C_the_sigpipe_case_reproduced_not_mocked,
               test_D_a_truncated_write_is_caught_by_schema_not_by_size,
               test_E_the_reported_path_must_be_the_verified_path,
               test_F_claim_prints_from_the_verification_not_the_intention,
               test_G_the_dfs_generators_claim_their_outputs):
        fn()
    for n in NOT_EXECUTED:
        print(f'  NOT_EXECUTED {n}')
    print(f'\n{PASSED} passed, {FAILED} failed, {len(NOT_EXECUTED)} NOT_EXECUTED')
    raise SystemExit(1 if FAILED else 0)
