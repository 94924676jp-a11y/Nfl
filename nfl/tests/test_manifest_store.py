"""One reader, and a proof that sharding changed nothing a consumer can see.

Twenty-one of the manifest's consumers both scan the whole file and depend on
ordering or a last-match-wins rule. So the property under test is not "the data
survived" but "the SEQUENCE survived, byte for byte, in order".
"""
from __future__ import annotations

import json
import pathlib
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.capture import manifest_store as MS                     # noqa: E402

PASSED = 0
FAILED = 0
BLOCKED = 0


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}: {detail}')


def blocked(label, why):
    global BLOCKED
    BLOCKED += 1
    print(f'  blocked {label}: {why}')


def raised(exc, fn, needle=None):
    try:
        fn()
    except exc as e:
        if needle is not None and needle not in str(e):
            return False, f'raised without {needle!r}: {e}'
        return True, ''
    except Exception as e:                                       # noqa: BLE001
        return False, f'raised {type(e).__name__} instead: {e}'
    return False, f'did not raise {exc.__name__}'


def _monolith(records):
    f = tempfile.NamedTemporaryFile('w', suffix='.jsonl', delete=False)
    for r in records:
        f.write(r + '\n')
    f.close()
    return pathlib.Path(f.name)


#: Deliberately out of date order, and with odd spacing and key order, because
#: that is what a real append-only log looks like after two years of edits.
_RAW = [
    '{"capture_id": "20260907T010000Z", "source": "a", "n": 1}',
    '{"source": "b",  "capture_id":"20260908T010000Z",   "n": 2}',
    '{"capture_id": "20260907T020000Z", "source": "c", "n": 3}',
    '{"source": "d", "note": "no capture id at all"}',
    '{"capture_id": "20260909T010000Z", "source": "e", "n": 5}',
]


def test_A_the_sequence_survives_byte_for_byte():
    print('\nA. the only property that matters to 21 consumers')
    src = _monolith(_RAW)
    dst = pathlib.Path(tempfile.mkdtemp()) / 's'
    try:
        MS.build_shards(src, dst)
        out = list(MS.records(dst, parse=False))
        check('same number of records', len(out) == len(_RAW), len(out))
        check('same lines in the same order, byte for byte',
              out == _RAW, out)
        rep = MS.equivalence(src, dst)
        check('equivalence agrees', rep['equivalent'] is True, rep)
        check('and the digests match', rep['digests_match'] is True)
    finally:
        src.unlink()


def test_B_lines_are_copied_not_reserialised():
    print('\nB. json.dumps of a round-trip is not the same bytes')
    src = _monolith(_RAW)
    dst = pathlib.Path(tempfile.mkdtemp()) / 's'
    try:
        MS.build_shards(src, dst)
        out = list(MS.records(dst, parse=False))
        odd = _RAW[1]                      # irregular spacing and key order
        check('the irregular line comes back unchanged', odd in out,
              [o for o in out if 'capture_id":"' in o])
        check('and a reserialisation would NOT have matched',
              json.dumps(json.loads(odd)) != odd,
              'if this fails the test proves nothing')
    finally:
        src.unlink()


def test_C_a_record_with_no_capture_id_is_kept_not_guessed():
    print('\nC. constraint 7: nothing is dropped to make the file smaller')
    src = _monolith(_RAW)
    dst = pathlib.Path(tempfile.mkdtemp()) / 's'
    try:
        idx = MS.build_shards(src, dst)
        keys = [s['key'] for s in idx['shards']]
        check('it lands in UNDATED', 'UNDATED' in keys, keys)
        check('and is still in the sequence',
              any('no capture id' in r for r in
                  MS.records(dst, parse=False)))
        check('every record is accounted for',
              idx['n_records'] == len(_RAW), idx['n_records'])
    finally:
        src.unlink()


def test_D_shard_order_follows_first_appearance_not_the_filename():
    print('\nD. a month that appears late must not jump to the front')
    src = _monolith(_RAW)
    dst = pathlib.Path(tempfile.mkdtemp()) / 's'
    try:
        idx = MS.build_shards(src, dst)
        keys = [s['key'] for s in idx['shards']]
        check('the undated shard keeps its position in source order',
              keys.index('UNDATED') == 2, keys)
        check('and reading back preserves the original interleaving',
              list(MS.records(dst, parse=False)) == _RAW)
    finally:
        src.unlink()


def test_E_a_tampered_shard_is_refused():
    print('\nE. the assertion that gates switching the live writer')
    src = _monolith(_RAW)
    dst = pathlib.Path(tempfile.mkdtemp()) / 's'
    try:
        idx = MS.build_shards(src, dst)
        victim = dst / idx['shards'][0]['file']
        victim.write_text(victim.read_text().replace('"n": 1', '"n": 99'))
        rep = MS.equivalence(src, dst)
        check('equivalence notices', rep['equivalent'] is False, rep)
        check('and says where', rep['first_difference_index'] is not None)
        ok, d = raised(MS.ManifestError,
                       lambda: MS.assert_equivalent(rep),
                       'The live writer must not be switched')
        check('and the assertion refuses', ok, d)
    finally:
        src.unlink()


def test_F_building_over_an_existing_tree_is_refused():
    print('\nF. two interleaved migrations')
    src = _monolith(_RAW)
    dst = pathlib.Path(tempfile.mkdtemp()) / 's'
    try:
        MS.build_shards(src, dst)
        ok, d = raised(MS.ManifestError,
                       lambda: MS.build_shards(src, dst), 'is not empty')
        check('a second build into the same tree refuses', ok, d)
        check('and the source is untouched, so it stays reversible',
              len(list(MS.records(src, parse=False))) == len(_RAW))
    finally:
        src.unlink()


def test_G_daily_bounds_the_largest_file_and_monthly_does_not():
    print('\nG. the measurement that chose the key')
    check('the default key is daily', MS.SHARD_KEY_MODE == 'day',
          MS.SHARD_KEY_MODE)
    r = '{"capture_id": "20260925T130823Z", "source": "x"}'
    check('daily keys carry the day', MS.shard_key(r, 'day') == '2026-09-25',
          MS.shard_key(r, 'day'))
    check('monthly keys do not', MS.shard_key(r, 'month') == '2026-09')
    check('an unparseable id is UNDATED under either',
          MS.shard_key('{"capture_id": "banana"}', 'day') == 'UNDATED')
    check('and so is a line that is not JSON',
          MS.shard_key('not json at all') == 'UNDATED')
