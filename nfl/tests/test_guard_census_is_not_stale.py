"""The committed guard census must match the code it describes.

WHY THIS EXISTS, AND IT IS A DEFECT THAT ACTUALLY HAPPENED

`nfl/research/audit/GUARD_REACHABILITY.json` is not decoration. Other tests read
it as ground truth -- `test_uncalled_governance_guards.py` asserts a
supersession is real by comparing two rows out of it. So a stale census does not
merely mislead a reader: it makes those tests assert stale facts and pass.

And it goes stale silently, because `guard_reachability.py --json` PRINTS the
census to stdout. The file is produced by shell redirection, which means there
is no step anywhere that fails when the code and the artifact disagree.
Measured 2026-09-27: after adding a proof to `LOAD_BEARING_PROOFS`, the
committed JSON still showed `load_bearing_proof: NONE` and
`classification: NOT_ESTABLISHED` for that guard, and every test reading the
file was perfectly happy. The census was 2 hours and one code change out of
date and nothing said so.

WHAT THIS TEST DOES

Regenerates the census in memory and compares it to the committed file. No
tolerance, no "close enough": the generator is deterministic over the tree, so
any difference means the file was not regenerated after a change.

It deliberately does NOT rewrite the file. A test that silently fixes the thing
it is checking converts a detectable defect into an invisible one, and the point
here is to make the drift visible at the moment it is introduced.

WHAT IT DOES NOT ESTABLISH

That the census is CORRECT -- only that it is current. A wrong classification
committed alongside its own generator output passes this test, as it should:
whether a guard is load-bearing is settled by a bypass proof, not by agreement
between a file and the function that wrote it.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from nfl.tools import guard_reachability as GR                  # noqa: E402

PASSED = FAILED = 0
COMMITTED = pathlib.Path(_ROOT) / 'nfl/research/audit/GUARD_REACHABILITY.json'
REGEN = 'python3.12 nfl/tools/guard_reachability.py --json > ' \
        'nfl/research/audit/GUARD_REACHABILITY.json'


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(ok)


_CACHE = {}


def _fresh():
    """One census per process, round-tripped through JSON.

    `GR.census()` parses every module in the tree and takes seconds. This file
    needs it in six tests, and an early version called it three times in a
    single test, which made the module one of the slowest in the suite for no
    benefit. The generator is deterministic -- `test_the_generator_is_
    deterministic` establishes exactly that -- so caching cannot mask drift.
    """
    if 'c' not in _CACHE:
        _CACHE['c'] = json.loads(json.dumps(GR.census()))
    return _CACHE['c']


def _fresh_uncached():
    """A second, independent census. Only the determinism test needs one."""
    return json.loads(json.dumps(GR.census()))


def test_the_committed_census_exists_and_parses():
    check('the census file exists', COMMITTED.exists(), str(COMMITTED))
    if COMMITTED.exists():
        try:
            d = json.loads(COMMITTED.read_text())
            check('and parses as JSON', isinstance(d, dict), type(d).__name__)
            check('and is not empty', bool(d.get('rows')),
                  str(len(d.get('rows') or [])))
        except Exception as exc:                               # noqa: BLE001
            check('and parses as JSON', False, repr(exc))


def test_the_generator_is_deterministic():
    """Otherwise a mismatch below would be noise, not drift."""
    a, b = _fresh_uncached(), _fresh_uncached()
    check('two consecutive censuses are identical',
          json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True),
          'the generator is not deterministic, so staleness cannot be '
          'distinguished from run-to-run variation')


def test_the_guard_count_matches():
    if not COMMITTED.exists():
        print('  skip  no committed census')
        return
    fresh, have = _fresh(), json.loads(COMMITTED.read_text())
    check('n_guards matches', fresh['n_guards'] == have.get('n_guards'),
          f"fresh {fresh['n_guards']} vs committed {have.get('n_guards')} -- "
          f"regenerate with: {REGEN}")
    fg = {(r['guard'], r.get('defined_in')) for r in fresh['rows']}
    hg = {(r['guard'], r.get('defined_in'))
          for r in have.get('rows') or []}
    check('no guard is missing from the committed file', not (fg - hg),
          str(sorted(fg - hg)[:6]))
    check('the committed file names no guard that no longer exists',
          not (hg - fg), str(sorted(hg - fg)[:6]))


def test_every_row_matches_field_for_field():
    if not COMMITTED.exists():
        print('  skip  no committed census')
        return
    fresh, have = _fresh(), json.loads(COMMITTED.read_text())
    # Keyed on name AND defining file, because a bare name is not unique: two
    # `assert_complete` exist (identity_crosswalk.py and contracts/
    # completeness.py) and two `assert_publishable`. A dict keyed on the name
    # alone silently drops one and then compares the survivor against the
    # other's committed row, which reports drift that is not there -- the first
    # version of this test did exactly that and disagreed with the byte-level
    # check three lines below it.
    hrows = {(r['guard'], r.get('defined_in')): r
             for r in have.get('rows') or []}
    drifted = []
    for r in fresh['rows']:
        h = hrows.get((r['guard'], r.get('defined_in')))
        if h is None:
            continue
        for k, v in r.items():
            if h.get(k) != v:
                drifted.append((r['guard'], k, h.get(k), v))
    check('no row has drifted', not drifted,
          '; '.join(f'{g}.{k}: committed {o!r} but code says {n!r}'
                    for g, k, o, n in drifted[:6])
          + (f' (+{len(drifted) - 6} more)' if len(drifted) > 6 else '')
          + f' -- regenerate with: {REGEN}')


def test_guard_names_are_not_unique_so_keying_on_them_alone_is_wrong():
    """Pins the reason the comparison above keys on the defining file too."""
    import collections
    names = collections.Counter(r['guard'] for r in _fresh()['rows'])
    dupes = sorted(n for n, c in names.items() if c > 1)
    check('at least one guard name is defined in more than one module',
          bool(dupes),
          'if this ever becomes empty the keying is merely redundant, not '
          'wrong -- but do not simplify it back to the bare name without '
          'checking this again')
    print(f'       duplicated guard names: {dupes}')
    keys = {(r['guard'], r.get('defined_in')) for r in _fresh()['rows']}
    check('name plus defining file IS unique',
          len(keys) == len(_fresh()['rows']),
          f'{len(keys)} keys for {len(_fresh()["rows"])} rows')


def test_the_whole_document_matches():
    """The blunt check, after the specific ones so a failure reads usefully."""
    if not COMMITTED.exists():
        print('  skip  no committed census')
        return
    fresh = json.dumps(_fresh(), indent=1) + '\n'
    have = COMMITTED.read_text()
    check('the committed census is byte-current with the generator',
          fresh == have,
          f'the file is {len(have)} bytes, a fresh census is {len(fresh)} -- '
          f'regenerate with: {REGEN}')


def test_this_test_does_not_repair_what_it_checks():
    """A test that silently fixes drift hides the drift."""
    before = COMMITTED.read_bytes() if COMMITTED.exists() else b''
    _fresh()
    after = COMMITTED.read_bytes() if COMMITTED.exists() else b''
    check('generating a census does not write the file', before == after,
          'census() has a side effect on disk, which would make every '
          'staleness check self-fulfilling')


def test_the_proofs_table_points_at_files_that_exist():
    """A proof naming a deleted test file is worse than no proof."""
    missing = []
    for guard, path in GR.LOAD_BEARING_PROOFS.items():
        if not (pathlib.Path(_ROOT) / path).exists():
            missing.append((guard, path))
    check('every load-bearing proof names a file that exists', not missing,
          str(missing))


def test_load_bearing_classification_requires_a_named_proof():
    """LOAD_BEARING without a proof file is the claim this project forbids."""
    fresh = _fresh()
    bad = [r['guard'] for r in fresh['rows']
           if r.get('classification') == 'LOAD_BEARING'
           and r.get('load_bearing_proof') in (None, '', 'NONE')]
    check('no guard is classified LOAD_BEARING without a named proof',
          not bad, str(bad))


if __name__ == '__main__':
    import traceback
    for _n in sorted(k for k in dict(globals()) if k.startswith('test_')):
        print(f'## {_n}')
        try:
            globals()[_n]()
        except Exception:                                      # noqa: BLE001
            FAILED += 1
            traceback.print_exc()
    print(f'\nPASSED {PASSED} FAILED {FAILED}')
    sys.exit(1 if FAILED else 0)
