"""nfl/tools/test_env_check.py: an incomplete test environment is named, never read as complete (Phase 1, 2026-10-10).

A fresh worktree has no git-ignored `nfl/derived/` or `nfl_vintage/raw/`. The checker must say MISSING for each, say
MISMATCH for a file whose bytes differ from its recorded provenance, and say COMPLETE only when every input is present
and verified.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import test_env_check as TE       # noqa: E402

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


def _root(derived_ok=True, raw=True, corrupt=False):
    d = pathlib.Path(tempfile.mkdtemp(prefix='envcheck_'))
    body = b'{"usage": 1}'
    sha = hashlib.sha256(body).hexdigest()
    (d / 'nfl' / 'production').mkdir(parents=True)
    (d / 'nfl' / 'production' / 'DERIVED_REBUILD_MANIFEST.json').write_text(
        json.dumps({'generation': 2, 'sha256': {'USAGE.json': sha}}))
    if derived_ok:
        (d / 'nfl' / 'derived').mkdir(parents=True)
        (d / 'nfl' / 'derived' / 'USAGE.json').write_bytes(b'{"usage": 2}' if corrupt else body)
    rb = b'season,week\n2026,5\n'
    rsha = hashlib.sha256(rb).hexdigest()
    (d / 'nfl' / 'vintage_manifest.jsonl').write_text(json.dumps({'state': 'PASS', 'value': {'sha256': rsha}}) + '\n')
    if raw:
        (d / 'nfl_vintage' / 'raw').mkdir(parents=True)
        (d / 'nfl_vintage' / 'raw' / f'weekly_rosters.{rsha[:16]}.csv').write_bytes(rb)
    return d


def _states(rep):
    return {r['input']: r['state'] for r in rep['inputs']}


def test_01_a_fresh_checkout_is_incomplete_and_names_each_missing_input():
    print('\n1. fresh checkout')
    rep = TE.check(_root(derived_ok=False, raw=False))
    s = _states(rep)
    check('verdict INCOMPLETE', rep['verdict'] == 'INCOMPLETE', rep['verdict'])
    check('  the derived artifact is MISSING by name, with how to rebuild it',
          s.get('nfl/derived/USAGE.json') == 'MISSING'
          and any('rebuild_derived.sh' in (r.get('reproduce') or '') for r in rep['inputs']), str(s))
    check('  the raw capture directory is MISSING', s.get('nfl_vintage/raw/') == 'MISSING', str(s))


def test_02_bytes_that_differ_from_provenance_are_a_mismatch_not_ok():
    print('\n2. corrupt copy')
    rep = TE.check(_root(corrupt=True))
    check('a derived file whose sha256 differs from the manifest is MISMATCH and the verdict INCOMPLETE',
          _states(rep).get('nfl/derived/USAGE.json') == 'MISMATCH' and rep['verdict'] == 'INCOMPLETE', str(_states(rep)))


def test_03_a_verified_environment_is_complete():
    print('\n3. verified')
    rep = TE.check(_root())
    s = _states(rep)
    check('every derived and raw input verified -> no MISSING or MISMATCH',
          not any(v in ('MISSING', 'MISMATCH') for k, v in s.items() if not k.startswith('python:')), str(s))


def test_04_a_raw_file_with_no_manifest_row_is_unverifiable_not_ok():
    print('\n4. raw file without provenance')
    d = _root()
    (d / 'nfl' / 'vintage_manifest.jsonl').write_text('')
    s = _states(TE.check(d))
    raw = [v for k, v in s.items() if k.startswith('nfl_vintage/raw/')]
    check('a raw file whose hash no manifest row records is UNVERIFIABLE, never OK', raw == ['UNVERIFIABLE'], str(s))


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for name, fn in sorted((k, v) for k, v in globals().items() if k.startswith('test_') and callable(v)):
        try:
            fn()
        except AssertionError as e:
            print(f'  {name}: {e}')
    print(f'\nPASSED {PASSED}  FAILED {FAILED}')
