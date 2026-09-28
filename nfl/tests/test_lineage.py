#!/usr/bin/env python3.12
"""Lineage must catch what timestamps cannot, and must refuse to call an unstamped artifact current.

The defect this guards against left no trace. role_state.py was corrected; the projection produced
byte-identical output because ROLE_STATE.json had not been rebuilt. Both runs looked the same from
outside, and a freshness check based on modification time would have passed the second one -- the
artifact was recent, its builder was merely newer.

So the checks here break lineage in each of the ways it can break and require the specific culprit to
be named, and one of them constructs exactly the case time-based freshness gets wrong.
"""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import sys
import tempfile
import time

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production import lineage, readiness  # noqa: E402
from sportsplatform.governance.outcome import State  # noqa: E402

RESULTS = []


def check(name):
    def deco(fn):
        RESULTS.append((name, fn))
        return fn
    return deco


def _sandbox():
    d = pathlib.Path(tempfile.mkdtemp())
    (d / 'nfl').mkdir()
    src = d / 'nfl' / 'builder.py'
    src.write_text('# builder v1\n')
    inp = d / 'nfl' / 'input.json'
    inp.write_text(json.dumps({'rows': [1, 2, 3]}))
    out = d / 'nfl' / 'output.json'
    out.write_text(json.dumps({'result': 42}))
    return d, src, inp, out


def _stamp(out, inp, src, root):
    old = lineage._REPO
    try:
        lineage._REPO = root
        return lineage.stamp(out, inputs=[inp], code=[src])
    finally:
        lineage._REPO = old


def _verify(out, root):
    old = lineage._REPO
    try:
        lineage._REPO = root
        return lineage.verify(out)
    finally:
        lineage._REPO = old


@check('a stamped artifact verifies, and names its inputs and its builder by content hash')
def t_roundtrip():
    d, src, inp, out = _sandbox()
    try:
        st = _stamp(out, inp, src, d)
        assert st.state is State.PASS, st
        art = json.loads(out.read_text())
        lin = art['_lineage']
        assert len(lin['inputs']) == 1 and len(lin['code']) == 1
        assert all(len(r['sha256']) == 64 for r in lin['inputs'] + lin['code'])
        assert lin['lineage_id']
        v = _verify(out, d)
        assert v.state is State.PASS and v.code == lineage.FRESH, v
        return f"stamped with lineage id {lin['lineage_id'][:12]} and verifies fresh"
    finally:
        shutil.rmtree(d, ignore_errors=True)


@check('LOAD-BEARING: editing the BUILDER invalidates the artifact and names the module')
def t_code_change():
    d, src, inp, out = _sandbox()
    try:
        _stamp(out, inp, src, d)
        src.write_text('# builder v2, one comment changed\n')
        v = _verify(out, d)
        assert v.state is State.FAIL and v.code == lineage.STALE_DEPENDENCY, (
            f'got {v.state}/{v.code}: the builder changed and the artifact still reported current, '
            f'which is the defect this module exists to remove')
        moved = v.evidence['moved']
        assert any(m['path'].endswith('builder.py') for m in moved), moved
        assert all(m['why'] == 'CONTENT_CHANGED_SINCE_BUILD' for m in moved)
        return f"editing the builder yields STALE_DEPENDENCY naming {moved[0]['path']}"
    finally:
        shutil.rmtree(d, ignore_errors=True)


@check('LOAD-BEARING: changing an INPUT invalidates the artifact and names the input')
def t_input_change():
    d, src, inp, out = _sandbox()
    try:
        _stamp(out, inp, src, d)
        inp.write_text(json.dumps({'rows': [1, 2, 3, 4]}))
        v = _verify(out, d)
        assert v.state is State.FAIL and v.code == lineage.STALE_DEPENDENCY, v
        assert any(m['path'].endswith('input.json') for m in v.evidence['moved'])
        inp.unlink()
        v2 = _verify(out, d)
        assert v2.state is State.FAIL
        assert any(m['why'] == 'INPUT_NOW_ABSENT' for m in v2.evidence['moved'])
        return 'a changed input and a deleted input are both caught and distinguished'
    finally:
        shutil.rmtree(d, ignore_errors=True)


@check('LOAD-BEARING: time-based freshness passes exactly the case lineage catches')
def t_time_cannot_see_it():
    d, src, inp, out = _sandbox()
    try:
        _stamp(out, inp, src, d)
        time.sleep(0.02)
        src.write_text('# builder v2\n')            # builder now NEWER than the artifact
        os.utime(out, None)                          # and the artifact is touched, so it looks new
        age_hours = (time.time() - out.stat().st_mtime) / 3600.0
        assert age_hours < 0.01, 'the artifact is recent by wall clock'
        v = _verify(out, d)
        assert v.state is State.FAIL and v.code == lineage.STALE_DEPENDENCY, (
            'the artifact is recent AND built from a builder that no longer exists. A freshness '
            'check on modification time passes this; lineage must not.')
        return (f'artifact is {age_hours * 3600:.2f}s old and still STALE_DEPENDENCY, because '
                f'recency is not provenance')
    finally:
        shutil.rmtree(d, ignore_errors=True)


@check('an UNSTAMPED artifact is a recorded debt, not a pass')
def t_unstamped():
    d, src, inp, out = _sandbox()
    try:
        v = _verify(out, d)
        assert v.state is State.DEFERRED, (
            f'got {v.state}: an artifact with no lineage cannot be proven current, so it must be a '
            f'tracked debt rather than an assumed success')
        assert v.code == lineage.UNSTAMPED
        assert v.evidence.get('owed')
        return 'no lineage block yields DEFERRED with the stamping recorded as owed'
    finally:
        shutil.rmtree(d, ignore_errors=True)


@check('the production role artifact is stamped against its own builder')
def t_role_state_stamped():
    p = _REPO / 'nfl/derived/ROLE_STATE.json'
    if not p.exists():
        return 'ROLE_STATE absent (derived artifacts are gitignored); skipped'
    art = json.loads(p.read_text())
    lin = art.get('_lineage')
    assert lin, 'the artifact whose staleness was invisible is still unstamped'
    code = [r['path'] for r in lin['code']]
    assert any(c.endswith('role_state.py') for c in code), code
    assert any(c.endswith('player_prior.py') for c in code), code
    v = lineage.verify(p)
    assert v.state is State.PASS, (
        f'{v.code}: the committed role artifact does not match its own builder. Rebuild it with '
        f'python3.12 nfl/tools/role_state.py')
    return f"stamped against {len(code)} source files and {len(lin['inputs'])} input(s), verifies fresh"


@check('LOAD-BEARING: a stale dependency forces NOT_PRODUCTION_READY')
def t_readiness_refuses():
    real = lineage.audit

    def poisoned(stages):
        out = real(stages)
        for r in out['rows']:
            if r['stage'] == 'derived.role_state':
                r['lineage_state'] = lineage.STALE_DEPENDENCY
                r['detail'] = [{'path': 'nfl/tools/role_state.py',
                                'why': 'CONTENT_CHANGED_SINCE_BUILD'}]
        out['any_stale_dependency'] = True
        return out
    try:
        lineage.audit = poisoned
        o = readiness.build()
        assert o.state is State.PASS, o
        v = o.value
        assert v['PRODUCT_MODE'] == 'NOT_PRODUCTION_READY', (
            f"mode is {v['PRODUCT_MODE']} with a stale dependency present. Nothing downstream of an "
            f"artifact built from content that no longer exists may report readiness.")
        assert 'derived.role_state' in v['stale_dependencies']
    finally:
        lineage.audit = real
        readiness.build()
    return 'a single stale dependency drops the product mode to NOT_PRODUCTION_READY'


@check('the role artifact is a declared readiness stage, so it cannot be skipped')
def t_declared():
    names = [s['name'] for s in readiness.STAGES]
    assert 'derived.role_state' in names, names
    st = next(s for s in readiness.STAGES if s['name'] == 'derived.role_state')
    assert st['tier'] in ('MODEL', 'FOUNDATION'), st['tier']
    proj = next(s for s in readiness.STAGES if s['name'] == 'slate.projection')
    assert 'derived.role_state' in proj['depends_on'], (
        'the projection does not declare the role artifact as an input, so an unrebuilt role '
        'artifact would not show the projection as behind its inputs')
    return f"declared at tier {st['tier']}, and the projection declares it as a dependency"


def main() -> int:
    ok = fail = 0
    for name, fn in RESULTS:
        try:
            detail = fn()
        except AssertionError as e:
            print(f'FAIL  {name}\n        {e}')
            fail += 1
        except Exception as e:  # noqa: BLE001
            print(f'ERROR {name}\n        {type(e).__name__}: {e}')
            fail += 1
        else:
            print(f'pass  {name}\n        {detail}')
            ok += 1
    print(f'\n{ok} passed, {fail} failed, {len(RESULTS)} checks')
    return 1 if fail else 0


if __name__ == '__main__':
    raise SystemExit(main())
