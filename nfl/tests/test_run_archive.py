#!/usr/bin/env python3.12
"""A sealed run is a record, so it must be unrewritable, hole-free, and detectably tampered with.

Production writes to fixed paths and a rerun overwrites them, so before this the slate actually
delivered on a Sunday existed only until the next run. Every other guarantee in the project -- seals,
lineage, execution identity -- described a run that the next run destroyed.

Two checks exist because of defects this module already had. Archiving over a sealed directory has to
be refused, because an immutable record that can be rewritten is not one. And the run id hashes the
code version rather than truncating it: the real version string starts with a 40-character commit sha
and carries a dirty-working-tree marker after it, so a fixed-width truncation dropped the marker and
gave a dirty and a clean tree the same id at the same second.
"""
from __future__ import annotations

import datetime as dt
import gzip
import json
import pathlib
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production import run_archive as RA  # noqa: E402

from nfl.tests import _registry  # noqa: E402

RESULTS = []


def check(name):
    def deco(fn):
        RESULTS.append((name, fn))
        return fn
    return deco


def _sandbox():
    d = pathlib.Path(tempfile.mkdtemp())
    src = d / 'src'
    src.mkdir()
    rel = []
    for i in range(3):
        f = src / f'out{i}.json'
        f.write_text(json.dumps({'i': i}))
        rel.append(str(f.relative_to(_REPO)) if str(f).startswith(str(_REPO)) else None)
    return d, src


def _with_repo_outputs(fn):
    """Run fn with RUNS and RUN_OUTPUTS pointed at a sandbox inside the repo tree."""
    tmp = pathlib.Path(tempfile.mkdtemp(dir=str(_REPO / 'nfl/production')))
    saved = (RA.RUNS, RA.CURRENT, RA.RUN_OUTPUTS, RA.RUN_OUTPUTS_OPTIONAL)
    try:
        src = tmp / 'src'
        src.mkdir()
        outs = []
        for i in range(3):
            f = src / f'out{i}.json'
            f.write_text(json.dumps({'i': i}))
            outs.append(str(f.relative_to(_REPO)))
        RA.RUNS = tmp / 'runs'
        RA.CURRENT = RA.RUNS / 'CURRENT.json'
        RA.RUN_OUTPUTS = tuple(outs)
        RA.RUN_OUTPUTS_OPTIONAL = ()
        return fn(tmp, src, tuple(outs))
    finally:
        RA.RUNS, RA.CURRENT, RA.RUN_OUTPUTS, RA.RUN_OUTPUTS_OPTIONAL = saved
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


@check('the run id distinguishes a dirty tree from a clean one at the same second')
def t_run_id_hashes_version():
    when = dt.datetime(2026, 9, 28, 12, 0, 0, tzinfo=dt.timezone.utc)
    clean = 'a' * 40
    dirty = 'a' * 40 + '+src1[025dff1b066fa876]'
    a = RA.run_id('S', when=when, code_version=clean)
    b = RA.run_id('S', when=when, code_version=dirty)
    assert a != b, (
        f'a clean and a dirty tree produced the same run id at the same second: {a}. The commit sha '
        f'alone is 40 characters, so truncating the version string to a fixed width drops the dirty '
        f'marker.')
    assert len(a.rsplit('__', 1)[1]) == 12
    return f'{a} != {b}, both 12-hex suffixes of the hashed version'


@check('archiving over a sealed run is refused')
def t_no_overwrite():
    def body(tmp, src, outs):
        when = dt.datetime(2026, 9, 28, 12, 0, 0, tzinfo=dt.timezone.utc)
        o1 = RA.archive('S', when=when)
        assert o1.state.name == 'PASS', f'{o1.code}: {o1.detail}'
        o2 = RA.archive('S', when=when)
        assert o2.state.name == 'FAIL' and o2.code == 'RUN_ALREADY_SEALED', o2.code
        return o1.value['run_id']
    rid = _with_repo_outputs(body)
    return f'a second archive at the same second into {rid} is refused, not merged'


@check('a missing or empty required output refuses the whole archive')
def t_hole_refused():
    def body(tmp, src, outs):
        (_REPO / outs[1]).unlink()
        o = RA.archive('S')
        assert o.state.name == 'FAIL' and o.code == 'RUN_OUTPUT_MISSING_OR_EMPTY', o.code
        assert any(m['why'] == 'ABSENT' for m in o.evidence['missing'])
        (_REPO / outs[1]).write_text('')
        o2 = RA.archive('S')
        assert o2.state.name == 'FAIL', o2.code
        assert any(m['why'] == 'EMPTY' for m in o2.evidence['missing'])
        return True
    _with_repo_outputs(body)
    return ('an absent and an empty required output each refuse the archive, so a hole cannot look '
            'like a finished run afterwards')


@check('a changed, removed or added byte in a sealed run is detected and named')
def t_tamper_detected():
    def body(tmp, src, outs):
        o = RA.archive('S')
        rid = o.value['run_id']
        assert RA.verify(rid).state.name == 'PASS'
        d = RA.RUNS / rid
        f = next(p for p in d.iterdir() if p.name != RA.SEAL_NAME)
        assert f.name.endswith('.gz'), f'archived files should be gzipped, got {f.name}'
        original = f.read_bytes()
        with gzip.open(f, 'rb') as fh:
            content = fh.read()
        with gzip.open(f, 'wb') as fh:
            fh.write(content + b' ')
        v = RA.verify(rid)
        assert v.state.name == 'FAIL' and v.code == 'SEALED_RUN_HAS_CHANGED', v.code
        assert v.evidence['moved'] and v.evidence['moved'][0]['file'] == f.name, (
            'the digest is of the UNCOMPRESSED content, so editing the content must be detected '
            'even though the container was rewritten legitimately')
        f.write_bytes(original)
        assert RA.verify(rid).state.name == 'PASS', 'restoring the byte must restore the seal'
        f.unlink()
        v2 = RA.verify(rid)
        assert v2.state.name == 'FAIL' and f.name in v2.evidence['absent'], v2.evidence
        f.write_bytes(original)
        f.write_bytes(b'not gzip at all')
        v4 = RA.verify(rid)
        assert v4.state.name == 'FAIL' and v4.evidence['unreadable'], (
            'an archived file that is no longer readable as gzip must break the seal rather than '
            'raise out of a governed function')
        f.write_bytes(original)
        (d / 'smuggled.json').write_text('{}')
        v3 = RA.verify(rid)
        assert v3.state.name == 'FAIL' and 'smuggled.json' in v3.evidence['added'], (
            'a file ADDED to a sealed run must also break the seal, or a record can be appended to')
        return rid
    rid = _with_repo_outputs(body)
    return 'a modified, a removed and an added file each break the seal and are named'


@check('live paths newer than the archive are DEFERRED, not silently fine and not a failure')
def t_current_deferred():
    def body(tmp, src, outs):
        RA.archive('S')
        assert RA.verify_current().state.name == 'PASS'
        (_REPO / outs[0]).write_text(json.dumps({'i': 0, 'rebuilt': True}))
        o = RA.verify_current()
        assert o.state.name == 'DEFERRED' and o.code == 'CURRENT_PATHS_AHEAD_OF_ARCHIVE', o.code
        assert o.evidence['drifted'][0]['why'] == 'REBUILT_SINCE_ARCHIVE'
        assert 'archive the current run' in str(o.evidence.get('owed'))
        return True
    _with_repo_outputs(body)
    return ('a rebuild between runs is the normal state, so it is an outstanding debt rather than a '
            'failure or a pass')


@check('the real archive exists, is intact, and matches the live outputs')
def t_real_archive():
    li = RA.list_runs()
    assert li.state.name == 'PASS', f'{li.code}: {li.detail}'
    assert li.value['n_runs'] >= 1, 'no run has ever been archived'
    bad = [r for r in li.value['runs'] if r['state'] != 'INTACT']
    assert not bad, f'archived runs not intact: {bad}'
    cur = RA.verify_current()
    assert cur.state.name in ('PASS', 'DEFERRED'), f'{cur.code}: {cur.detail}'
    names = {r['run_id'] for r in li.value['runs']}
    assert all('__' in n and len(n.rsplit('__', 1)[1]) == 12 for n in names), names
    return (f'{li.value["n_runs"]} run(s), all intact, current is {cur.code}')


@check('the seal says what it proves and what it does not')
def t_seal_is_honest():
    li = RA.list_runs()
    rid = li.value['runs'][0]['run_id']
    seal = json.loads((RA.RUNS / rid / RA.SEAL_NAME).read_text())
    txt = seal['WHAT_A_SEAL_PROVES_AND_DOES_NOT']
    assert 'does NOT prove the run was correct' in txt
    assert 'also needs the inputs' in txt, (
        'a seal over outputs alone does not make a run reproducible, and the artifact must say so '
        'rather than letting the word "sealed" imply it')
    assert 'IMMUTABLE' in seal and seal['code_version']
    return 'the seal states that it proves the bytes, not the correctness, and not reproducibility'


@check('the Sunday run records its archive step')
def t_wired_in():
    src = (_REPO / 'nfl/production/sunday.py').read_text()
    assert 'run_archive' in src, 'the Sunday run does not archive at all'
    rp = _REPO / 'nfl/production/SUNDAY_RUN_REPORT.json'
    if rp.exists():
        rep = json.loads(rp.read_text())
        if 'run_archive' in rep:
            assert 'ARCHIVE_MEANING' in rep, (
                'the report names an archive without saying that the fixed paths are the current '
                'run and the sealed directory is this one')
            rid = (rep['run_archive'] or {}).get('run_id')
            if rid:
                assert (RA.RUNS / rid / RA.SEAL_NAME).exists(), (
                    f'the run report names {rid} and no sealed directory of that name exists. A '
                    f'report pointing at an archive that is not there is worse than one pointing '
                    f'at nothing, because it reads as though the run were preserved.')
                v = RA.verify(rid)
                assert v.state.name == 'PASS', f'{rid}: {v.code}'
            return f'the run report names {rid}, which exists and verifies'
        return 'wired in; the report on disk predates the wiring and will carry it on the next run'
    return 'wired in; no run report on disk'


# EXPOSE EVERY CHECK TO run_suite, which is the authoritative execution path. Without this the
# runner reports `0 fn, NO TALLY` and executes NONE of them, while a direct run of this file prints
# a confident pass. See nfl/tests/_registry.py.
_EMITTED = _registry.emit(globals(), RESULTS)


def test_zz_every_check_passed():
    # The tally tripwire, in this module's own source because run_suite recognises it by shape.
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


def main() -> int:
    for fname in _EMITTED:
        try:
            globals()[fname]()
        except Exception:  # noqa: BLE001  -- already printed and counted by the wrapper
            pass
    test_zz_every_check_passed.__doc__
    print(f'\n{PASSED} passed, {FAILED} failed, {len(RESULTS)} checks')
    return 1 if FAILED else 0


if __name__ == '__main__':
    raise SystemExit(main())
