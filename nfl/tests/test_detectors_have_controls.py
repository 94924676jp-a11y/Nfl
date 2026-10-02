"""OWNER RULE 2 (2026-10-02): the static half of "every detector has a demonstrated trip case".

The dynamic half -- did a control RUN and TRIP in this run -- is judged by run_suite itself at
the end of every run (nfl/tests/_controls.validate, written to DETECTOR_VALIDATION.json), because
no single test module can see the whole run. This module checks what can be checked without
running: the manifest is well-formed, every detector names a module and function that exist and a
code that appears in that module's source, every detector has at least one DECLARED control
somewhere in nfl/tests, and the registry's own machinery trips on a known violation.
"""
from __future__ import annotations

import importlib
import json
import os
import pathlib
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tests import _controls as C  # noqa: E402

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


def test_01_manifest_is_well_formed_and_non_empty():
    print('\n1. DETECTORS.json')
    doc = json.loads(C.MANIFEST.read_text())
    dets = doc.get('detectors') or []
    check('the manifest lists at least one detector (an empty manifest enforces nothing)',
          len(dets) > 0, str(len(dets)))
    bad = [d for d in dets if d.get('detector', '').count(':') != 2]
    check('  every entry is <module>:<function>:<CODE>', not bad, str(bad[:3]))
    dup = len(dets) - len({d['detector'] for d in dets})
    check('  no duplicates', dup == 0, str(dup))


def test_02_every_detector_names_something_that_exists():
    print('\n2. every detector resolves to real code')
    missing_mod, missing_fn, missing_code = [], [], []
    for d in C.load_manifest():
        mod, fn, code = d['detector'].split(':')
        src_path = _REPO / (mod.replace('.', '/') + '.py')
        if not src_path.exists():
            missing_mod.append(d['detector'])
            continue
        src = src_path.read_text(encoding='utf-8')
        head = fn.split('.')[0]
        if f'def {head}(' not in src and f'class {head}' not in src:
            missing_fn.append(d['detector'])
        # measured() derives its code as <caller code>_EMPTY_INPUT; the caller's code is in source
        probe = code[:-len('_EMPTY_INPUT')] if d.get('kind') == 'measured-suffix' and code.endswith('_EMPTY_INPUT') else code
        if probe not in src and d.get('kind') not in ('harness-verdict', 'summary-text', 'state'):
            missing_code.append(d['detector'])
    check('every detector module exists', not missing_mod, str(missing_mod[:5]))
    check('  and names a function defined there', not missing_fn, str(missing_fn[:5]))
    check('  and its code string appears in that module', not missing_code, str(missing_code[:5]))


def test_03_every_detector_has_a_declared_control():
    print('\n3. every detector has at least one declared positive control in nfl/tests')
    decl = C.declared_controls()
    none = [d['detector'] for d in C.load_manifest() if not decl.get(d['detector'])]
    n = len(C.load_manifest())
    check(f'{n - len(none)} of {n} detectors have a declared control; those without are listed',
          not none, '\n      ' + '\n      '.join(none[:80]) + ('\n      ...' if len(none) > 80 else ''))


def test_04_the_registry_itself_trips_and_distinguishes_a_non_trip():
    print('\n4. the registry machinery (positive and negative control on itself)')
    from sportsplatform.governance.outcome import Outcome
    with tempfile.TemporaryDirectory() as td:
        saved = {k: os.environ.get(k) for k in ('NFL_CONTROL_HITS', 'NFL_SUITE_RUN_ID')}
        try:
            os.environ['NFL_CONTROL_HITS'] = os.path.join(td, 'h.jsonl')
            os.environ['NFL_SUITE_RUN_ID'] = 'selftest'
            t1 = C.observe('m:f:CODE_A', Outcome.fail('CODE_A', 'tripped'))
            t2 = C.observe('m:f:CODE_A', Outcome.ok('CODE_B', 1))
            t3 = C.observe('m:g:STATE_X', {'state': 'STATE_X'})
            rows = C.hits('selftest')
            check('a detector that returned its code records tripped=true', t1 and rows[0]['tripped'])
            check('  one that returned a different code records tripped=false, not an error',
                  (not t2) and rows[1]['tripped'] is False and rows[1]['got'] == 'CODE_B')
            check('  a dict state is read as the code', t3 and rows[2]['tripped'])
            check('  every row carries the run id and the calling module', all(
                r['run_id'] == 'selftest' and r['module'].endswith('test_detectors_have_controls.py')
                for r in rows), str(rows[0]))
            # validate() on a synthetic manifest-less view: statuses from these rows
            byd = {}
            for r in rows:
                byd.setdefault(r['detector'], []).append(r)
            check('  validate-style reading: CODE_A is VALIDATED by its tripped row even though a '
                  'non-trip row also exists', any(h['tripped'] for h in byd['m:f:CODE_A']))
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v


def test_05_the_last_validation_artifact_if_present_is_honest_about_scope():
    print('\n5. DETECTOR_VALIDATION.json, when present, says what run produced it')
    if not C.VALIDATION.exists():
        check('no validation artifact yet (first run); nothing to read', True)
        return
    doc = json.loads(C.VALIDATION.read_text())
    check('the artifact carries run_id, full_run and a verdict',
          all(k in doc for k in ('run_id', 'full_run', 'verdict', 'rows')), str(list(doc)[:8]))
    check('  a verdict of ALL_VALIDATED is only claimed when every row is VALIDATED',
          doc['verdict'] != 'ALL_VALIDATED' or all(r['status'] == C.VALIDATED for r in doc['rows']))
    check('  the census of unlisted refusal codes is reported, not dropped',
          isinstance(doc.get('census'), dict) and doc['census'].get('state'), str(doc.get('census'))[:120])


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
