"""Adversarial replay tests for the pre-kickoff forecast seal. G0A items 5, 11, 12.

Each section names the real defect it is seeded from. Written by an agent that
did NOT write nfl/identity/seal.py or nfl/identity/execution_identity.py, on the
assumption that the code is wrong until a seeded violation is refused.

DEFECTS THIS FILE REPLAYS

  * THE BACKWARDS DRAFT. An earlier draft of this control proposed
    `written_at < captured_at < kickoff`, which permits a forecast to consume
    bytes that had not arrived when it was written. Section B seeds exactly that
    and requires CAPTURE_AFTER_WRITE.

  * MLB M0. `SIM_FORMULA` excluded `corpus.py` and all corpus data, so
    substituting the corpus changed every output while `FP-ab18309e17e7e16e`
    stayed byte-identical. The fingerprint could not catch it because the inputs
    were never inside it. Section H substitutes an input hash and requires the
    fingerprint to move.

  * THE V7 WEATHER GUARD. A 30-minute-old cached forecast was re-wrapped with a
    fresh `generated_utc` and certified fresh. Section D seeds a cache hit
    restamped as a live retrieval and requires the seal to be refused, with the
    five clocks still distinct rather than collapsed to satisfy an ordering.

  * THE INERT GUARD (`assert_batch_games_are_new`), which read a field no row
    carried and therefore passed on every input it was ever given. Sections B
    and D each end with a load-bearing proof: bypass the guard, and the seeded
    violation must stop being caught.

BINDING TEST STANDARD (Owner Directive 3 §8): "A guard is not demonstrated
merely because compliant data passes it. It must reject a seeded violation, and
critical guards must demonstrate that removing/bypassing the guard causes the
replay test to fail."

Run standalone:  python3.12 nfl/tests/test_seal_ordering.py
"""
import datetime as dt
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from sportsplatform.governance.outcome import Cause, Outcome, State          # noqa: E402
from sportsplatform.governance.provenance import Provenance                   # noqa: E402
from nfl.identity.execution_identity import (ConsumedPartition,   # noqa: E402
                                             ExecutionIdentity)
from nfl.identity import seal as seal_mod                         # noqa: E402
from nfl.identity.seal import seal_forecast, append_seal          # noqa: E402
from nfl.tests.bypass import (assert_guard_is_load_bearing,       # noqa: E402
                              guard_bypassed)

PASSED = FAILED = 0


def check(label, cond, detail=''):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')


# --------------------------------------------------------------------------
# Fixtures. One Sunday game, kickoff 2026-09-13 17:00Z, filing deadline capture
# on the Friday, forecast written on the Friday evening.
KICKOFF = '2026-09-13T17:00:00+00:00'
FRIDAY_CAPTURE = '2026-09-11T20:00:00+00:00'
FRIDAY_WRITE = '2026-09-11T22:00:00+00:00'
SHA_INJ = 'a' * 64
SHA_SCH = 'b' * 64
SPEC_SHA = 'c' * 64


def prov(**over) -> Provenance:
    base = dict(source='nflverse:injuries',
                source_timestamp='2026-09-11T19:30:00+00:00',
                retrieved_at=FRIDAY_CAPTURE,
                generated_at='2026-09-11T20:00:05+00:00',
                effective_for_date='2026-09-13',
                schema_version='nflverse-release-1',
                url='https://example.invalid/injuries.csv')
    base.update(over)
    return Provenance(**base)


def part(pid='injuries', sha=SHA_INJ, **over) -> ConsumedPartition:
    return ConsumedPartition(partition_id=pid, source='nflverse', url='u',
                             sha256=sha, provenance=prov(**over))


def ident(*partitions, spec_sha=SPEC_SHA) -> ExecutionIdentity:
    if not partitions:
        partitions = (part(),)
    return ExecutionIdentity(spec_id='nfl-g0a-spec', spec_sha256=spec_sha,
                             code_version='g0a-1', interpreter='python3.12',
                             seed=20260913, partitions=tuple(partitions))


def do_seal(identity=None, consumed=('injuries',), written_at=FRIDAY_WRITE,
            kickoff=KICKOFF, payload=b'{"total": 44.5}', fid='F-2026-09-13-A'):
    return seal_forecast(forecast_id=fid, game_id='2026_01_AAA_BBB',
                         kickoff_utc=kickoff, payload=payload,
                         identity=identity if identity is not None else ident(),
                         consumed_partition_ids=list(consumed),
                         written_at=written_at)


# --------------------------------------------------------------------------
def test_a_valid_ordering_seals():
    """Owner case (a): capture -> write -> kickoff seals."""
    print('\nA. capture before write before kickoff -> FORECAST_SEALED')
    o = do_seal()
    check('a compliant forecast seals', o.state is State.PASS, str(o))
    check('with the named code', o.code == 'FORECAST_SEALED', o.code)
    s = o.unwrap()
    check('the seal carries the identity fingerprint',
          s.identity_fingerprint == ident().fingerprint(),
          f'{s.identity_fingerprint} vs {ident().fingerprint()}')
    check('the payload is identified by digest, not by trust',
          s.payload_sha256 == __import__('hashlib').sha256(
              b'{"total": 44.5}').hexdigest())
    check('the consumed partitions are recorded on the seal',
          s.consumed_partition_ids == ('injuries',), str(s.consumed_partition_ids))
    check('the seal is self-identifying', len(s.seal_sha256()) == 64)
    check('and the detail states the lead time, not just "ok"',
          'before kickoff' in o.detail, o.detail)
    # Boundary: retrieval EXACTLY at write time is legal -- nothing arrived late.
    o2 = do_seal(identity=ident(part(retrieved_at=FRIDAY_WRITE,
                                     generated_at=FRIDAY_WRITE)),
                 written_at=FRIDAY_WRITE)
    check('retrieval exactly at write time is permitted (<=, not <)',
          o2.state is State.PASS, str(o2))
    # Two consumed partitions, both in the identity.
    o3 = do_seal(identity=ident(part(), part('schedules', SHA_SCH)),
                 consumed=('injuries', 'schedules'))
    check('a two-partition forecast seals', o3.state is State.PASS, str(o3))
    check('and both ids ride on the seal, sorted',
          o3.unwrap().consumed_partition_ids == ('injuries', 'schedules'))


def test_b_capture_after_write_is_refused():
    """Owner case (b) -- THE CORRECTION.

    The withdrawn draft ordering `written_at < captured_at` would have made this
    the compliant case. A forecast cannot read bytes that had not arrived.
    """
    print('\nB. a consumed partition retrieved AFTER the write -> CAPTURE_AFTER_WRITE')
    late = part(retrieved_at='2026-09-12T09:00:00+00:00',
                source_timestamp='2026-09-12T08:00:00+00:00',
                generated_at='2026-09-12T09:00:05+00:00')
    o = do_seal(identity=ident(late))
    check('the seal is refused', o.state is State.FAIL, str(o))
    check('with the named code', o.code == 'CAPTURE_AFTER_WRITE', o.code)
    v = o.evidence.get('violations') or []
    check('the offending partition is named, not just counted',
          len(v) == 1 and v[0]['partition_id'] == 'injuries', str(v))
    check('and the size of the violation is quantified',
          v and v[0]['seconds_after_write'] > 0, str(v))
    # One late partition among three compliant ones must still refuse the seal.
    mixed = ident(part(), part('schedules', SHA_SCH),
                  ConsumedPartition('depth', 'nflverse', 'u', 'd' * 64,
                                    prov(retrieved_at='2026-09-12T09:00:00+00:00',
                                         source_timestamp='2026-09-12T08:00:00+00:00',
                                         generated_at='2026-09-12T09:00:05+00:00')))
    o2 = do_seal(identity=mixed, consumed=('injuries', 'schedules', 'depth'))
    check('one late partition among three refuses the whole seal',
          o2.state is State.FAIL and o2.code == 'CAPTURE_AFTER_WRITE', str(o2))
    check('and only the late one is named',
          [x['partition_id'] for x in o2.evidence['violations']] == ['depth'],
          str(o2.evidence.get('violations')))
    # A partition retrieved a full second late is still late. No grace window.
    o3 = do_seal(identity=ident(part(retrieved_at='2026-09-11T22:00:01+00:00',
                                     generated_at='2026-09-11T22:00:02+00:00')))
    check('a one-second-late retrieval is still refused (no grace window)',
          o3.state is State.FAIL and o3.code == 'CAPTURE_AFTER_WRITE', str(o3))


def test_b2_ordering_guard_is_load_bearing():
    """The guard must be what catches it, not an accident of the fixture.

    `seal._parse` is the guard's mechanism: it is what keeps the clocks apart
    long enough to be compared. Replacing it with one that returns the same
    instant for every field is precisely the "five clocks collapsed" failure the
    module docstring warns against, and the ordering check must go inert.
    """
    print('\nB2. bypassing the clock comparison stops the catch (load-bearing)')
    late = part(retrieved_at='2026-09-12T09:00:00+00:00',
                source_timestamp='2026-09-12T08:00:00+00:00',
                generated_at='2026-09-12T09:00:05+00:00')

    # The stub reads every clock off one compliant script regardless of what the
    # record actually says: retrieval, then write, then kickoff. This is what a
    # collapsed clock model looks like from the inside.
    _SCRIPT = {'retrieved_at': dt.datetime(2026, 9, 11, 20, 0, tzinfo=dt.timezone.utc),
               'written_at': dt.datetime(2026, 9, 11, 22, 0, tzinfo=dt.timezone.utc),
               'kickoff_utc': dt.datetime(2026, 9, 13, 17, 0, tzinfo=dt.timezone.utc)}

    def scripted(ts, field):
        return _SCRIPT[field]

    try:
        assert_guard_is_load_bearing(
            run=lambda: do_seal(identity=ident(late)),
            module_path='nfl.identity.seal', attr='_parse',
            caught=lambda o: o.code == 'CAPTURE_AFTER_WRITE',
            replacement=scripted)
        check('CAPTURE_AFTER_WRITE depends on the clocks staying distinct', True)
    except AssertionError as exc:
        check('CAPTURE_AFTER_WRITE depends on the clocks staying distinct',
              False, str(exc)[:200])
    # And the same for WRITE_AFTER_KICKOFF, which uses the same comparison.
    try:
        assert_guard_is_load_bearing(
            run=lambda: do_seal(written_at='2026-09-13T18:00:00+00:00',
                                identity=ident(part(
                                    retrieved_at='2026-09-13T17:30:00+00:00',
                                    source_timestamp='2026-09-13T17:00:00+00:00',
                                    generated_at='2026-09-13T17:30:05+00:00'))),
            module_path='nfl.identity.seal', attr='_parse',
            caught=lambda o: o.code == 'WRITE_AFTER_KICKOFF',
            replacement=scripted)
        check('WRITE_AFTER_KICKOFF likewise depends on the guard', True)
    except AssertionError as exc:
        check('WRITE_AFTER_KICKOFF likewise depends on the guard', False,
              str(exc)[:200])


def test_c_write_at_or_after_kickoff_is_refused():
    """Owner case (c): both strictly after AND exactly equal to kickoff."""
    print('\nC. a forecast written at or after kickoff is not prospective')
    after = do_seal(written_at='2026-09-13T17:00:01+00:00',
                    identity=ident(part(retrieved_at='2026-09-13T16:00:00+00:00',
                                        source_timestamp='2026-09-13T15:00:00+00:00',
                                        generated_at='2026-09-13T16:00:05+00:00')))
    check('written strictly after kickoff is refused',
          after.state is State.FAIL and after.code == 'WRITE_AFTER_KICKOFF',
          str(after))
    check('and the lateness is quantified',
          after.evidence.get('seconds_late') == 1.0,
          str(after.evidence.get('seconds_late')))

    equal = do_seal(written_at=KICKOFF,
                    identity=ident(part(retrieved_at='2026-09-13T16:00:00+00:00',
                                        source_timestamp='2026-09-13T15:00:00+00:00',
                                        generated_at='2026-09-13T16:00:05+00:00')))
    check('written EXACTLY at kickoff is refused (>=, not >)',
          equal.state is State.FAIL and equal.code == 'WRITE_AFTER_KICKOFF',
          str(equal))
    check('and zero seconds late is still late, not rounded away',
          equal.evidence.get('seconds_late') == 0.0,
          str(equal.evidence.get('seconds_late')))

    one_before = do_seal(written_at='2026-09-13T16:59:59+00:00',
                         identity=ident(part(retrieved_at='2026-09-13T16:00:00+00:00',
                                             source_timestamp='2026-09-13T15:00:00+00:00',
                                             generated_at='2026-09-13T16:00:05+00:00')))
    check('one second before kickoff still seals -- the boundary is exact',
          one_before.state is State.PASS, str(one_before))

    # Timezone laundering: the same instant written as -04:00 must be judged the
    # same. 13:00-04:00 IS 17:00Z, i.e. exactly kickoff.
    tz = do_seal(written_at='2026-09-13T13:00:00-04:00',
                 identity=ident(part(retrieved_at='2026-09-13T16:00:00+00:00',
                                     source_timestamp='2026-09-13T15:00:00+00:00',
                                     generated_at='2026-09-13T16:00:05+00:00')))
    check('an offset-shifted timestamp cannot launder a late write',
          tz.state is State.FAIL and tz.code == 'WRITE_AFTER_KICKOFF', str(tz))

    bad = do_seal(kickoff='sometime Sunday')
    check('an unparseable kickoff BLOCKS rather than defaulting',
          bad.state is State.BLOCKED and bad.code == 'SEAL_TIMESTAMP_UNPARSEABLE',
          str(bad))
    check('and names the cause as DATA, not NETWORK',
          bad.evidence.get('cause') == Cause.DATA.value, str(bad.evidence))


def test_d_cache_hit_restamped_as_fresh_is_refused():
    """Owner case (d): the V7 weather defect, delegated to provenance.validate.

    A record served from a 30-minute-old cache that reports `retrieved_at = now`
    must not be sealable. seal.py does not re-implement this; it delegates to
    `sportsplatform.governance.provenance.validate` through `ExecutionIdentity.validate`.
    This section checks both that the refusal happens AND that it comes back
    with the specific provenance code rather than being flattened into an
    ordering complaint.
    """
    print('\nD. a cache hit restamped as a fresh retrieval -> refused')
    cached = part(cache_timestamp='2026-09-11T19:30:00+00:00',
                  retrieved_at=FRIDAY_CAPTURE)     # 30 minutes apart
    o = do_seal(identity=ident(cached))
    check('the seal is refused', o.state is State.FAIL, str(o))
    check('at the identity layer, by name',
          o.code == 'IDENTITY_PARTITION_PROVENANCE_INVALID', o.code)
    fails = o.evidence.get('failures') or {}
    check('and the SPECIFIC provenance code survives the delegation',
          fails.get('injuries') == 'CACHE_RETRIEVAL_CONFLATED', str(fails))
    check('it is NOT flattened into an ordering code',
          o.code not in ('CAPTURE_AFTER_WRITE', 'WRITE_AFTER_KICKOFF'), o.code)

    # THE FIVE CLOCKS ARE NOT COLLAPSED. Nothing in the seal path may quietly
    # rewrite one clock to satisfy another; that rewrite IS the V7 defect.
    p = cached.provenance
    check('source_timestamp is still its own value',
          p.source_timestamp == '2026-09-11T19:30:00+00:00', p.source_timestamp)
    check('retrieved_at is still its own value',
          p.retrieved_at == FRIDAY_CAPTURE, p.retrieved_at)
    check('cache_timestamp survived and was not dropped',
          p.cache_timestamp == '2026-09-11T19:30:00+00:00', str(p.cache_timestamp))
    check('generated_at is distinct from retrieved_at',
          p.generated_at != p.retrieved_at, p.generated_at)
    check('effective_for_date is a date, not one of the four instants',
          p.effective_for_date == '2026-09-13', p.effective_for_date)
    check('all five names are distinct fields on the record',
          len({'source_timestamp', 'retrieved_at', 'cache_timestamp',
               'generated_at', 'effective_for_date'} -
              set(p.__dataclass_fields__)) == 0, str(sorted(p.__dataclass_fields__)))
    try:
        p.age_seconds('age')
        check('asking an unqualified "how old is this" is refused', False,
              'it answered')
    except ValueError as exc:
        check('asking an unqualified "how old is this" is refused',
              'name the clock' in str(exc), str(exc)[:80])
    check('and the effective age is measured on the OLDEST real clock',
          p.effective_age_seconds(
              now=dt.datetime(2026, 9, 11, 20, 30, tzinfo=dt.timezone.utc)) == 3600.0,
          str(p.effective_age_seconds(
              now=dt.datetime(2026, 9, 11, 20, 30, tzinfo=dt.timezone.utc))))

    # An honest cache hit -- retrieved_at equal to the cache write -- is legal.
    honest = part(cache_timestamp=FRIDAY_CAPTURE, retrieved_at=FRIDAY_CAPTURE)
    check('an honestly-declared cache hit still seals',
          do_seal(identity=ident(honest)).state is State.PASS,
          str(do_seal(identity=ident(honest))))

    # Sibling seeded violation on the same delegation: a wrapper that predates
    # its own contents, and retrieval before the source produced the bytes.
    impossible = part(retrieved_at='2026-09-11T18:00:00+00:00',
                      source_timestamp='2026-09-11T19:30:00+00:00')
    oi = do_seal(identity=ident(impossible))
    check('retrieved-before-source is refused too',
          oi.state is State.FAIL and
          (oi.evidence.get('failures') or {}).get('injuries') ==
          'PROVENANCE_IMPOSSIBLE', str(oi))
    incomplete = ConsumedPartition('injuries', 'nflverse', 'u', SHA_INJ,
                                   Provenance(source='x', source_timestamp='',
                                              retrieved_at=FRIDAY_CAPTURE,
                                              generated_at=FRIDAY_CAPTURE,
                                              effective_for_date='2026-09-13',
                                              schema_version='v1'))
    oc = do_seal(identity=ident(incomplete))
    check('a partition with a missing clock cannot be sealed',
          oc.state is State.FAIL and
          (oc.evidence.get('failures') or {}).get('injuries') ==
          'PROVENANCE_INCOMPLETE', str(oc))


def test_d2_cache_guard_is_load_bearing():
    print('\nD2. bypassing provenance validation lets the cache hit through '
          '(load-bearing)')
    cached = part(cache_timestamp='2026-09-11T19:30:00+00:00',
                  retrieved_at=FRIDAY_CAPTURE)
    try:
        assert_guard_is_load_bearing(
            run=lambda: do_seal(identity=ident(cached)),
            module_path='nfl.identity.execution_identity', attr='validate_prov',
            caught=lambda o: o.code == 'IDENTITY_PARTITION_PROVENANCE_INVALID',
            returns=Outcome.ok('STUB_PROVENANCE_VALID', value={},
                               detail='bypassed'))
        check('the cache-conflation refusal comes from provenance.validate', True)
    except AssertionError as exc:
        check('the cache-conflation refusal comes from provenance.validate',
              False, str(exc)[:200])
    # With the guard bypassed the seal must actually SUCCEED -- i.e. the only
    # thing standing between a stale cache and a sealed forecast is that call.
    with guard_bypassed('nfl.identity.execution_identity', 'validate_prov',
                        returns=Outcome.ok('STUB', value={}, detail='bypassed')):
        leaked = do_seal(identity=ident(cached))
    check('and without it a 30-minute-stale cache seals cleanly -- which is '
          'exactly the V7 weather defect',
          leaked.state is State.PASS, str(leaked))


def test_e_consumed_partition_absent_from_identity():
    """Owner case (e): an input outside the identity is invisible to the
    fingerprint. This is the MLB M0 shape restated at the seal boundary."""
    print('\nE. a consumed partition absent from the identity -> '
          'PARTITION_NOT_IN_IDENTITY')
    o = do_seal(identity=ident(part()), consumed=('injuries', 'weather'))
    check('the seal is refused', o.state is State.FAIL, str(o))
    check('with the named code', o.code == 'PARTITION_NOT_IN_IDENTITY', o.code)
    check('the missing input is named', o.evidence.get('missing') == ['weather'],
          str(o.evidence.get('missing')))
    check('both sides of the comparison are recorded for the reader',
          o.evidence.get('consumed') == ['injuries', 'weather'] and
          o.evidence.get('in_identity') == ['injuries'], str(o.evidence))
    o2 = do_seal(identity=ident(part()), consumed=('weather',))
    check('a wholly undeclared input is refused too',
          o2.state is State.FAIL and o2.code == 'PARTITION_NOT_IN_IDENTITY',
          str(o2))
    # The reverse asymmetry, recorded deliberately: the identity may carry MORE
    # partitions than were consumed, and those extras are not ordering-checked.
    # That is by design (the seal checks what the forecast READ), and it is only
    # sound because `consumed_partition_ids` is an honest declaration.
    extra = ident(part(), ConsumedPartition(
        'postgame', 'nflverse', 'u', 'e' * 64,
        prov(source_timestamp='2026-09-14T00:00:00+00:00',
             retrieved_at='2026-09-14T01:00:00+00:00',
             generated_at='2026-09-14T01:00:05+00:00')))
    oe = do_seal(identity=extra, consumed=('injuries',))
    check('an identity partition that was NOT consumed is not ordering-checked '
          '(documented asymmetry, sound only if the declaration is honest)',
          oe.state is State.PASS, str(oe))
    check('but declaring it consumed immediately refuses the seal',
          do_seal(identity=extra,
                  consumed=('injuries', 'postgame')).code == 'CAPTURE_AFTER_WRITE')


def test_f_absences_are_refused():
    print('\nF. an empty artifact cannot satisfy an ordering check')
    o = do_seal(payload=b'')
    check('an empty payload is refused',
          o.state is State.FAIL and o.code == 'SEAL_PAYLOAD_EMPTY', str(o))
    check('and the reason names the trap -- it would pass every clock check',
          'ordering' in o.detail, o.detail[:120])

    o2 = do_seal(consumed=())
    check('declaring no consumed partitions is refused',
          o2.state is State.FAIL and o2.code == 'SEAL_NO_CONSUMED_INPUTS', str(o2))

    o3 = do_seal(identity=ExecutionIdentity('s', SPEC_SHA, 'v', 'py', 1, ()))
    check('an identity with no partitions is refused',
          o3.state is State.FAIL and o3.code == 'IDENTITY_WITHOUT_INPUTS', str(o3))
    check('and it says why: a fingerprint over no inputs cannot detect a '
          'substitution', 'M0' in o3.detail, o3.detail[:150])

    o4 = do_seal(identity=ident(spec_sha=''))
    check('an unhashed spec is refused',
          o4.state is State.FAIL and o4.code == 'IDENTITY_SPEC_UNHASHED', str(o4))

    for bad in ('', 'deadbeef', 'a' * 63, 'a' * 65):
        try:
            ConsumedPartition('p', 's', 'u', bad, prov())
            check(f'sha256 {bad[:12]!r} (len {len(bad)}) refused', False,
                  'accepted')
        except ValueError:
            check(f'sha256 {bad[:12]!r} (len {len(bad)}) refused', True)

    check('the checks run in refusal order: an empty payload inside an invalid '
          'identity reports the identity first',
          do_seal(identity=ExecutionIdentity('s', SPEC_SHA, 'v', 'py', 1, ()),
                  payload=b'').code == 'IDENTITY_WITHOUT_INPUTS')


def test_g_seal_is_immutable():
    print('\nG. re-sealing a forecast_id is a named failure, never an update')
    with tempfile.TemporaryDirectory() as td:
        ledger = os.path.join(td, 'sub', 'seals.jsonl')
        s1 = do_seal().unwrap()
        a1 = append_seal(s1, ledger)
        check('the first seal is appended',
              a1.state is State.PASS and a1.code == 'SEAL_APPENDED', str(a1))
        check('the ledger file exists and holds one row',
              len(open(ledger).read().strip().splitlines()) == 1)

        a2 = append_seal(do_seal().unwrap(), ledger)
        check('re-recording IDENTICAL content is NOT_APPLICABLE',
              a2.state is State.NOT_APPLICABLE and
              a2.code == 'SEAL_ALREADY_RECORDED', str(a2))
        check('and it did not grow the ledger',
              len(open(ledger).read().strip().splitlines()) == 1)

        s3 = do_seal(payload=b'{"total": 47.5}').unwrap()
        a3 = append_seal(s3, ledger)
        check('a DIFFERENT payload under the same forecast_id is refused',
              a3.state is State.FAIL and
              a3.code == 'SEAL_IMMUTABLE_VIOLATION', str(a3))
        check('and the prior seal digest is quoted so the change is auditable',
              a3.evidence.get('prior_seal') == s1.seal_sha256(),
              str(a3.evidence))
        check('the ledger still holds one row -- nothing was overwritten',
              len(open(ledger).read().strip().splitlines()) == 1)

        # Same payload, different INPUTS. This is the substitution that MLB M0
        # could not see, and it must be visible here.
        s4 = do_seal(identity=ident(part(sha='9' * 64))).unwrap()
        a4 = append_seal(s4, ledger)
        check('the same payload built from SUBSTITUTED inputs is refused',
              a4.state is State.FAIL and
              a4.code == 'SEAL_IMMUTABLE_VIOLATION', str(a4))

        a5 = append_seal(do_seal(fid='F-2026-09-13-B').unwrap(), ledger)
        check('a genuinely different forecast_id appends normally',
              a5.state is State.PASS, str(a5))
        rows = [json.loads(x) for x in open(ledger).read().strip().splitlines()]
        check('the ledger now holds two rows', len(rows) == 2, str(len(rows)))
        check('every row carries its own seal_sha256',
              all(len(r['seal_sha256']) == 64 for r in rows))
        check('and the identity, including every input hash, is stored inline '
              'so the row is self-describing',
              rows[0]['identity']['partitions'][0]['sha256'] == SHA_INJ,
              str(rows[0]['identity'])[:120])


def test_h_fingerprint_consumes_every_input_hash():
    """THE MLB M0 FAILURE, and the reason this module exists.

    `SIM_FORMULA` excluded `corpus.py` and all corpus data, so substituting a
    corpus changed M0's outputs while leaving FP-ab18309e17e7e16e identical.
    Recording a hash NEXT TO a run does not help; the hash has to be INSIDE the
    identity the fingerprint is computed over. Anything below that changes an
    input and leaves the fingerprint alone is that defect, reproduced.
    """
    print('\nH. changing any input hash MUST change the fingerprint (MLB M0)')
    base = ident(part(), part('schedules', SHA_SCH))
    fp = base.fingerprint()
    check('the fingerprint is namespaced', fp.startswith('NFLFP-'), fp)

    one = ident(part(sha='9' * 64), part('schedules', SHA_SCH))
    check('substituting the FIRST partition sha256 moves the fingerprint',
          one.fingerprint() != fp, f'{one.fingerprint()} == {fp}')
    two = ident(part(), part('schedules', '9' * 64))
    check('substituting the SECOND partition sha256 moves the fingerprint',
          two.fingerprint() != fp, f'{two.fingerprint()} == {fp}')
    check('the two substitutions are themselves distinguishable',
          one.fingerprint() != two.fingerprint())

    # A single flipped hex character is enough -- no truncation may hide it.
    nudged = ident(part(sha='a' * 63 + 'b'), part('schedules', SHA_SCH))
    check('a ONE-CHARACTER difference in an input hash moves the fingerprint',
          nudged.fingerprint() != fp, nudged.fingerprint())

    check('dropping a partition moves the fingerprint',
          ident(part()).fingerprint() != fp)
    check('adding a partition moves the fingerprint',
          ident(part(), part('schedules', SHA_SCH),
                part('depth', 'd' * 64)).fingerprint() != fp)
    check('renaming a partition moves the fingerprint',
          ident(part(), part('rosters', SHA_SCH)).fingerprint() != fp)

    # Provenance is inside the identity too: a different capture of the same
    # bytes is a different execution identity.
    check('a different retrieved_at moves the fingerprint',
          ident(part(retrieved_at='2026-09-11T20:00:01+00:00'),
                part('schedules', SHA_SCH)).fingerprint() != fp)
    check('a different source_timestamp moves the fingerprint',
          ident(part(source_timestamp='2026-09-11T19:29:00+00:00'),
                part('schedules', SHA_SCH)).fingerprint() != fp)

    check('a different spec_sha256 moves the fingerprint',
          ident(part(), part('schedules', SHA_SCH),
                spec_sha='f' * 64).fingerprint() != fp)
    check('a different seed moves the fingerprint',
          dataclass_with(base, seed=1).fingerprint() != fp)
    check('a different code_version moves the fingerprint',
          dataclass_with(base, code_version='g0a-2').fingerprint() != fp)
    check('a different interpreter moves the fingerprint',
          dataclass_with(base, interpreter='python3.13').fingerprint() != fp)

    # Read order is not identity. Two runs that read the same inputs in a
    # different order are the same execution, and must not look different.
    reordered = ExecutionIdentity('nfl-g0a-spec', SPEC_SHA, 'g0a-1',
                                  'python3.12', 20260913,
                                  (part('schedules', SHA_SCH), part()))
    check('read ORDER does not change the fingerprint',
          reordered.fingerprint() == fp, f'{reordered.fingerprint()} != {fp}')

    # And the fingerprint must be stable across processes, not memory-address
    # dependent -- otherwise no two runs are ever comparable.
    check('the fingerprint is deterministic within a process',
          ident(part(), part('schedules', SHA_SCH)).fingerprint() == fp)
    blob = json.dumps(base.as_dict(), sort_keys=True, separators=(',', ':'))
    check('and it is computed over serialisable content only', 'sha256' in blob)

    v = base.validate()
    check('a well-formed identity validates', v.state is State.PASS, str(v))
    check('and returns the fingerprint as its value', v.value == fp, str(v.value))
    check('with the partition count in evidence',
          v.evidence.get('n_partitions') == 2, str(v.evidence))

    # The seal carries the fingerprint forward, so the substitution is visible
    # at the seal too, not only on the identity object.
    s_base = do_seal(identity=base, consumed=('injuries', 'schedules')).unwrap()
    s_sub = do_seal(identity=one, consumed=('injuries', 'schedules')).unwrap()
    check('two seals over the SAME payload and DIFFERENT inputs differ',
          s_base.identity_fingerprint != s_sub.identity_fingerprint)
    check('and their seal digests differ too',
          s_base.seal_sha256() != s_sub.seal_sha256())
    check('while the payload digest is identical -- proving the difference '
          'came from the inputs, which is exactly what M0 could not see',
          s_base.payload_sha256 == s_sub.payload_sha256)


def dataclass_with(identity, **over):
    import dataclasses
    return dataclasses.replace(identity, **over)


if __name__ == '__main__':
    test_a_valid_ordering_seals()
    test_b_capture_after_write_is_refused()
    test_b2_ordering_guard_is_load_bearing()
    test_c_write_at_or_after_kickoff_is_refused()
    test_d_cache_hit_restamped_as_fresh_is_refused()
    test_d2_cache_guard_is_load_bearing()
    test_e_consumed_partition_absent_from_identity()
    test_f_absences_are_refused()
    test_g_seal_is_immutable()
    test_h_fingerprint_consumes_every_input_hash()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
