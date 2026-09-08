"""Adversarial tests for the prospective availability watch.

No network is touched: `subprocess` is replaced inside the module under test, so
every HTTP state below is SEEDED rather than waited for. A test that needed the
2026 file to publish would not be a test.

THE THREE SEPARATIONS THIS FILE EXISTS TO DEFEND

    SOURCE AVAILABILITY   /   CAPTURE SUCCESS   /   PREDICTIVE ELIGIBILITY

Collapsing any pair is the Class A failure this project keeps paying for. The
sharpest case is section A: a 404 is an OBSERVED STATE OF THE WORLD and must
never render as a successful capture, nor as a failure of the capture system.

REAL DEFECTS REPLAYED HERE

  * Section B. A 200 whose body is the text `Not Found`. This is not
    hypothetical: measured 2026-09-08 on this very release host, the asset
    `nextgen_stats/ngs_receiving.csv.gz` answers 200 with exactly that body. A
    byte-count check passes it.
  * Section E. A column-count check passing through a real loss --
    `injuries_2025.csv` dropped `date_modified` while keeping 16 columns.
    Hence the fingerprint is over ordered names, not a count.
  * Section H. The V7 weather defect: one clock substituted for another so a
    stale artifact certified as fresh. Here: a cache hit must not be restamped.

Run standalone:  python3.12 nfl/tests/test_availability_watch.py
"""
import contextlib
import datetime as dt
import gzip
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from sportsplatform.governance.outcome import Outcome, State        # noqa: E402
from nfl.capture import availability as AV                          # noqa: E402
from nfl.capture import registry as REG                             # noqa: E402
from nfl.tools import watch_availability as W                       # noqa: E402
from nfl.tools import capture_vintage as CV                         # noqa: E402
from nfl.tests.bypass import (assert_guard_is_load_bearing,         # noqa: E402
                              guard_bypassed)

PASSED = FAILED = 0

LM = 'Tue, 08 Sep 2026 12:00:00 GMT'
HDR200 = f'HTTP/1.1 200 OK\r\nLast-Modified: {LM}\r\nETag: "z9"\r\n\r\n'
HDR404 = 'HTTP/1.1 404 Not Found\r\nDate: Tue, 08 Sep 2026 12:00:00 GMT\r\n\r\n'

PART_HEADER = (AV.ACCEPTED_SCHEMAS['pbp_participation'][1])
GOOD_PART = (','.join(PART_HEADER) + '\n'
             + ','.join(['x'] * len(PART_HEADER)) + '\n'
             + ','.join(['y'] * len(PART_HEADER)) + '\n').encode()
SNAP_HEADER = AV.ACCEPTED_SCHEMAS['snap_counts'][0]
GOOD_SNAP = (','.join(SNAP_HEADER) + '\n'
             + ','.join(['1'] * len(SNAP_HEADER)) + '\n').encode()


def check(label, cond, detail=''):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}' + (f'  [{detail}]' if detail else ''))


@contextlib.contextmanager
def seeded(status='200', headers=HDR200, body=GOOD_PART):
    """Replace subprocess inside the watcher; yield (blob_root, tmp)."""
    class _R:
        def __init__(self, code): self.stdout, self.stderr = code, ''

    with tempfile.TemporaryDirectory() as d:
        d = pathlib.Path(d)
        (d / 'tmp').mkdir()

        class _SP:
            TimeoutExpired = subprocess.TimeoutExpired

            @staticmethod
            def run(cmd, **kw):
                out = pathlib.Path(cmd[cmd.index('-o') + 1])
                hdr = pathlib.Path(cmd[cmd.index('-D') + 1])
                hdr.write_text(headers)
                if body is not None:
                    out.write_bytes(body)
                return _R(status)

        orig = W.subprocess
        W.subprocess = _SP
        try:
            yield d / 'blobs', d / 'tmp'
        finally:
            W.subprocess = orig


# ==========================================================================
# A. availability is not capture success
# ==========================================================================
def test_a_404_is_not_published_not_a_pass_and_not_a_failure():
    print('\nA. a 404 is an observed source state, never a successful capture')
    with seeded(status='404', headers=HDR404, body=b'Not Found') as (root, tmp):
        out = W.probe('pbp_participation', 2026, root, tmp)
    check('404 -> DEFERRED, not PASS', out.state is State.DEFERRED,
          out.state.value)
    check('  availability is NOT_PUBLISHED',
          out.evidence.get('availability') == 'NOT_PUBLISHED',
          out.evidence.get('availability'))
    check('  it is not FAIL: the capture system worked correctly',
          out.state is not State.FAIL)
    check('  the debt stays owed', out.evidence.get('owed', '').startswith(
        'pbp_participation:'))
    check('  no bytes are claimed', not out.evidence.get('sha256')
          and not out.evidence.get('blob'))
    check('  and NO artifact clock is claimed either: a file that does not '
          'exist has no Last-Modified, and the 404 response\'s own Date is '
          'recorded under its own name',
          out.evidence.get('source_timestamp') is None
          and out.evidence.get('probe_response_date') is not None,
          f"src_ts={out.evidence.get('source_timestamp')} "
          f"resp={out.evidence.get('probe_response_date')}")
    rec = W._record(out)
    v = AV.verify_record(rec)
    check('  verify_record refuses to treat an absence as unverified data',
          v.state is State.NOT_APPLICABLE, v.code)


def test_a2_a_not_published_record_may_never_carry_bytes():
    print('\nA2. NOT_PUBLISHED plus a payload is incoherent and is refused')
    forged = {'source': 'pbp_participation',
              'availability': 'NOT_PUBLISHED',
              'sha256': 'de' * 32, 'blob': 'nfl/availability_raw/x.csv.gz'}
    v = AV.verify_record(forged)
    check('a NOT_PUBLISHED row naming bytes FAILS',
          v.state is State.FAIL and v.code == 'UNAVAILABLE_RECORD_CARRIES_BYTES',
          v.code)


# ==========================================================================
# B. a 200 is not evidence that the response carries the artifact
# ==========================================================================
def test_b_200_over_an_error_body_is_rejected_as_data():
    print('\nB. 200 with an HTML or error body is not a capture')
    with seeded(body=b'Not Found') as (root, tmp):
        o1 = W.probe('pbp_participation', 2026, root, tmp)
    check('200 + body "Not Found" -> FAIL BODY_IS_ERROR_TEXT '
          '(measured live on this host 2026-09-08)',
          o1.state is State.FAIL and o1.code == 'BODY_IS_ERROR_TEXT', o1.code)
    check('  availability is AMBIGUOUS, not AVAILABLE',
          o1.evidence.get('availability') == 'AMBIGUOUS')

    with seeded(body=b'<!DOCTYPE html><html><body>404</body></html>') as (r, t):
        o2 = W.probe('pbp_participation', 2026, r, t)
    check('200 + an HTML document -> FAIL BODY_IS_HTML_NOT_DATA',
          o2.state is State.FAIL and o2.code == 'BODY_IS_HTML_NOT_DATA', o2.code)

    with seeded(body=b'') as (r, t):
        o3 = W.probe('pbp_participation', 2026, r, t)
    check('200 + zero bytes -> FAIL EMPTY_PAYLOAD_200',
          o3.state is State.FAIL and o3.code == 'EMPTY_PAYLOAD_200', o3.code)


def test_b2_header_only_and_malformed_csv():
    print('\nB2. a header with nothing under it, and a body that will not parse')
    with seeded(body=(','.join(PART_HEADER) + '\n').encode()) as (r, t):
        o1 = W.probe('pbp_participation', 2026, r, t)
    check('header row only -> FAIL HEADER_ONLY_PAYLOAD',
          o1.state is State.FAIL and o1.code == 'HEADER_ONLY_PAYLOAD', o1.code)

    with seeded(body=(','.join(PART_HEADER) + '\n\n\n\n').encode()) as (r, t):
        o2 = W.probe('pbp_participation', 2026, r, t)
    check('header plus blank lines is still zero data rows',
          o2.state is State.FAIL and o2.code == 'HEADER_ONLY_PAYLOAD', o2.code)

    bad = (','.join(PART_HEADER) + '\n' + 'a,"unterminated\n').encode()
    with seeded(body=bad) as (r, t):
        o3 = W.probe('pbp_participation', 2026, r, t)
    check('an unterminated quote is caught as ragged rows, NOT waved through '
          '(csv does not raise on it -- it swallows the file into one field)',
          o3.state is State.FAIL and o3.code == 'CSV_RAGGED_ROWS',
          f'{o3.state.value}/{o3.code}')
    check('  and availability is never AVAILABLE',
          o3.evidence.get('availability') != 'AVAILABLE')
    short = (','.join(PART_HEADER) + '\n' + 'a,b,c\n').encode()
    with seeded(body=short) as (r, t):
        o4 = W.probe('pbp_participation', 2026, r, t)
    check('  a row with too few fields is ragged too',
          o4.state is State.FAIL and o4.code == 'CSV_RAGGED_ROWS', o4.code)


# ==========================================================================
# C. the happy path, and what it still refuses to grant
# ==========================================================================
def test_c_available_is_recorded_but_grants_nothing():
    print('\nC. AVAILABLE is recorded, verified -- and authorises nothing')
    with seeded(body=GOOD_PART) as (root, tmp):
        out = W.probe('pbp_participation', 2026, root, tmp)
        check('accepted schema + rows -> PASS SOURCE_AVAILABLE',
              out.state is State.PASS and out.code == 'SOURCE_AVAILABLE',
              f'{out.state.value}/{out.code}')
        rec = W._record(out)
        check('  availability is AVAILABLE', rec['availability'] == 'AVAILABLE')
        check('  raw bytes were stored BEFORE parsing, content-addressed',
              (root / pathlib.Path(rec['blob']).name).exists()
              or (W._REPO / rec['blob']).exists())
        check('  sha256 is of the uncompressed bytes',
              rec['sha256'] == hashlib.sha256(GOOD_PART).hexdigest())
        v = AV.verify_record(rec, repo_root=W._REPO)
        check('  the stored blob hashes back to the recorded digest',
              v.state is State.PASS, v.code)
        el = AV.eligibility_record(rec)
        check('  predictive eligibility: NOT authorized',
              el['authorized'] is False
              and el['authorization_code'] == 'NOT_AUTHORIZED_BY_OWNER')
        check('  with no forecast supplied the ordering is UNEVALUATED, '
              'not satisfied',
              el['ordering_ok'] is None
              and el['ordering_code'] == 'NO_FORECAST_TO_JUDGE')


def test_c2_ordering_is_computed_but_never_authorises():
    print('\nC2. even a satisfied ordering does not authorise consumption')
    # Inside the block deliberately: eligibility VERIFIES the blob, so a record
    # whose evidence has been deleted reports RAW_BLOB_MISSING rather than an
    # ordering verdict. That is the correct behaviour -- section H covers it --
    # but it is not what this section is testing.
    with seeded(body=GOOD_PART) as (root, tmp):
        rec = W._record(W.probe('pbp_participation', 2026, root, tmp))
        got = dt.datetime.fromisoformat(rec['retrieved_at'])
        good = AV.eligibility_record(
            rec, forecast_written_at=got + dt.timedelta(hours=1),
            kickoff=got + dt.timedelta(hours=5))
        check('retrieved_at < written_at < kickoff -> ORDERING_SATISFIED',
              good['ordering_ok'] is True
              and good['ordering_code'] == 'ORDERING_SATISFIED',
              good['ordering_code'])
        check('  and authorized is STILL False', good['authorized'] is False)
        bad = AV.eligibility_record(
            rec, forecast_written_at=got - dt.timedelta(hours=1),
            kickoff=got + dt.timedelta(hours=5))
        check('a forecast written BEFORE retrieval -> ORDERING_VIOLATED',
              bad['ordering_ok'] is False, bad['ordering_code'])
        late = AV.eligibility_record(
            rec, forecast_written_at=got + dt.timedelta(hours=6),
            kickoff=got + dt.timedelta(hours=5))
        check('a forecast written AFTER kickoff -> ORDERING_VIOLATED',
              late['ordering_ok'] is False, late['ordering_code'])
    check('and once the evidence is gone, eligibility reports THAT instead of '
          'an ordering verdict',
          AV.eligibility_record(rec)['ordering_code'] == 'RAW_BLOB_MISSING')


# ==========================================================================
# D. wrong season, wrong source
# ==========================================================================
def test_d_wrong_season_and_wrong_source():
    print('\nD. the record names the season and source it was actually for')
    with seeded(body=GOOD_SNAP) as (root, tmp):
        out = W.probe('snap_counts', 2026, root, tmp)
    rec = W._record(out)
    check('season is recorded on the row', rec['season'] == 2026, rec.get('season'))
    check('the URL carries that season and no other',
          rec['url'].endswith('snap_counts_2026.csv'), rec['url'])
    check('the URL names the source it was probed for',
          '/snap_counts/' in rec['url'])
    check('a season the registry can format is not silently reused',
          REG.resolve('snap_counts', 2025).value.endswith('2025.csv'))

    out2 = W.probe('not_a_real_source', 2026,
                   pathlib.Path(tempfile.mkdtemp()), pathlib.Path('/tmp'))
    check('an unregistered source is BLOCKED, never probed',
          out2.state is State.BLOCKED
          and out2.code == 'SOURCE_NOT_IN_REGISTRY', out2.code)

    out3 = W.probe('injuries', 2026, pathlib.Path(tempfile.mkdtemp()),
                   pathlib.Path('/tmp'))
    check('a registered but NOT watch-only source is refused by the watcher',
          out3.state is State.FAIL
          and out3.code == 'WATCHED_SOURCE_NOT_WATCH_ONLY', out3.code)


# ==========================================================================
# E. schema
# ==========================================================================
def test_e_schema_drift_and_reordering_fail_closed():
    print('\nE. drift and reordering both fail closed; the raw artifact is kept')
    drifted = list(PART_HEADER) + ['brand_new_column']
    body = (','.join(drifted) + '\n' + ','.join(['x'] * len(drifted)) + '\n').encode()
    with seeded(body=body) as (root, tmp):
        out = W.probe('pbp_participation', 2026, root, tmp)
    check('an added column -> FAIL SCHEMA_CHANGED',
          out.state is State.FAIL and out.code == 'SCHEMA_CHANGED', out.code)
    check('  availability is SCHEMA_CHANGED',
          out.evidence.get('availability') == 'SCHEMA_CHANGED')
    check('  downstream use fails closed',
          out.evidence.get('downstream_use') == 'FAILS CLOSED')
    check('  and the raw artifact is preserved anyway',
          bool(out.evidence.get('raw_preserved')))

    ro = list(PART_HEADER)
    ro[0], ro[1] = ro[1], ro[0]
    body2 = (','.join(ro) + '\n' + ','.join(['x'] * len(ro)) + '\n').encode()
    with seeded(body=body2) as (root, tmp):
        out2 = W.probe('pbp_participation', 2026, root, tmp)
    check('SAME columns in a different ORDER is drift, not a match',
          out2.state is State.FAIL and out2.code == 'SCHEMA_CHANGED', out2.code)

    dropped = [c for c in PART_HEADER if c != 'offense_players']
    body3 = (','.join(dropped) + '\n' + ','.join(['x'] * len(dropped)) + '\n').encode()
    with seeded(body=body3) as (root, tmp):
        out3 = W.probe('pbp_participation', 2026, root, tmp)
    check('dropping a column we consume is drift and names it',
          out3.state is State.FAIL
          and 'offense_players' in str(out3.evidence.get('schema_evidence', {})),
          out3.code)


def test_e2_both_accepted_participation_schemas_are_accepted():
    print('\nE2. the 20-column and 26-column shapes are both real and accepted')
    for shape in AV.ACCEPTED_SCHEMAS['pbp_participation']:
        body = (','.join(shape) + '\n' + ','.join(['x'] * len(shape)) + '\n').encode()
        with seeded(body=body) as (root, tmp):
            out = W.probe('pbp_participation', 2026, root, tmp)
        check(f'{len(shape)}-column shape is accepted, not reported as drift',
              out.state is State.PASS, f'{out.state.value}/{out.code}')
    check('the fingerprint is over ordered NAMES, not a count '
          '(injuries_2025 dropped date_modified while keeping 16 columns)',
          AV.schema_fingerprint('x', b'a,b\n1,2\n').value['column_order_digest']
          != AV.schema_fingerprint('x', b'b,a\n1,2\n').value['column_order_digest'])


# ==========================================================================
# F. bytes: duplicates, changes, immutability
# ==========================================================================
def test_f_duplicate_identical_bytes_and_changed_bytes():
    print('\nF. identical bytes are a measurement; changed bytes are a version')
    with seeded(body=GOOD_PART) as (root, tmp):
        o1 = W.probe('pbp_participation', 2026, root, tmp)
        o2 = W.probe('pbp_participation', 2026, root, tmp)
        check('first observation writes a NEW blob',
              o1.value['content_unchanged'] is False)
        check('identical bytes again: no new blob, still a PASS row',
              o2.value['content_unchanged'] is True and o2.state is State.PASS)
        check('  same digest', o1.value['sha256'] == o2.value['sha256'])
        check('  but a NEW retrieved_at -- it is a fresh observation',
              o2.value['retrieved_at'] >= o1.value['retrieved_at'])
        n_blobs = len(list(root.glob('*.csv.gz')))
        check('  exactly one blob on disk for one distinct payload',
              n_blobs == 1, n_blobs)

        changed = GOOD_PART + b','.join([b'z'] * len(PART_HEADER)) + b'\n'
        with seeded(body=changed) as (_r2, tmp2):
            o3 = W.probe('pbp_participation', 2026, root, tmp2)
        check('changed bytes -> a second, distinct blob',
              o3.value['sha256'] != o1.value['sha256']
              and o3.value['content_unchanged'] is False)
        check('  the first blob is NOT overwritten',
              len(list(root.glob('*.csv.gz'))) == 2)


def test_f2_changed_bytes_under_the_SAME_source_clock():
    print('\nF2. changed bytes carrying an unchanged source clock')
    with seeded(body=GOOD_PART) as (root, tmp):
        o1 = W.probe('pbp_participation', 2026, root, tmp)
        changed = GOOD_PART + b','.join([b'q'] * len(PART_HEADER)) + b'\n'
        with seeded(body=changed, headers=HDR200) as (_r, tmp2):
            o2 = W.probe('pbp_participation', 2026, root, tmp2)
        check('the source clock is identical', o1.value['source_timestamp']
              == o2.value['source_timestamp'])
        check('the CONTENT digest still differs, so the change is visible '
              'without trusting the clock',
              o1.value['sha256'] != o2.value['sha256'])
        check('  and both blobs survive',
              len(list(root.glob('*.csv.gz'))) == 2)
        check('  the substantive digest differs too',
              o1.value['schema_fingerprint']['substantive_digest']
              != o2.value['schema_fingerprint']['substantive_digest'])


def test_f3_cache_hit_does_not_restamp():
    print('\nF3. a cache hit does not restamp -- the V7 weather defect')
    with seeded(body=GOOD_PART) as (root, tmp):
        o1 = W.probe('pbp_participation', 2026, root, tmp)
        first = o1.value['blob_first_retrieved_at']
        side = W._REPO / o1.value['blob_sidecar'] if not os.path.isabs(
            o1.value['blob_sidecar']) else pathlib.Path(o1.value['blob_sidecar'])
        o2 = W.probe('pbp_participation', 2026, root, tmp)
    check('the blob keeps its ORIGINAL first_retrieved_at',
          o2.value['blob_first_retrieved_at'] == first, 
          f"{first} -> {o2.value['blob_first_retrieved_at']}")
    check('  while the row carries the CURRENT retrieval time, kept separate',
          o2.value['retrieved_at'] >= first)
    check('  the two are different fields and are not merged',
          'blob_first_retrieved_at' in o2.value and 'retrieved_at' in o2.value)
    # And the provenance primitive itself refuses the conflation.
    from sportsplatform.governance.provenance import Provenance, validate
    p = Provenance(source='x', source_timestamp='2026-09-08T10:00:00+00:00',
                   retrieved_at='2026-09-08T12:00:00+00:00',
                   generated_at='2026-09-08T12:00:01+00:00',
                   effective_for_date='2026', schema_version='v',
                   cache_timestamp='2026-09-08T10:30:00+00:00')
    v = validate(p)
    check('a record served from a cache but claiming a fresh retrieval FAILS',
          v.state is State.FAIL and v.code == 'CACHE_RETRIEVAL_CONFLATED', v.code)


# ==========================================================================
# G. clocks
# ==========================================================================
def test_g_source_clock_later_than_retrieval_is_impossible():
    print('\nG. clock ordering')
    future_lm = 'Fri, 08 Sep 2028 12:00:00 GMT'
    hdr = f'HTTP/1.1 200 OK\r\nLast-Modified: {future_lm}\r\n\r\n'
    with seeded(headers=hdr, body=GOOD_PART) as (root, tmp):
        out = W.probe('pbp_participation', 2026, root, tmp)
    check('source clock AFTER retrieval -> FAIL, never reconciled by guessing',
          out.state is State.FAIL and out.code == 'PROBE_PROVENANCE_INVALID',
          out.code)
    check('  and the underlying reason is named',
          out.evidence.get('provenance_code') == 'PROVENANCE_IMPOSSIBLE',
          out.evidence.get('provenance_code'))
    check('  the bytes were stored anyway -- evidence survives the refusal',
          bool(out.evidence.get('blob')))

    hdr2 = 'HTTP/1.1 200 OK\r\nETag: "no-clock"\r\n\r\n'
    with seeded(headers=hdr2, body=GOOD_PART) as (root, tmp):
        out2 = W.probe('pbp_participation', 2026, root, tmp)
    check('no parseable source clock -> FAIL, never backfilled from retrieved_at',
          out2.state is State.FAIL and out2.code == 'SOURCE_TIMESTAMP_ABSENT',
          out2.code)


def test_g2_future_retrieved_at_is_refused():
    print('\nG2. a retrieval clock in the future')
    ahead = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=3)
    o = AV.assert_not_future(ahead.isoformat())
    check('retrieved_at three hours ahead -> FAIL RETRIEVED_AT_IN_FUTURE',
          o.state is State.FAIL and o.code == 'RETRIEVED_AT_IN_FUTURE', o.code)
    o2 = AV.assert_not_future(dt.datetime.now(dt.timezone.utc).isoformat())
    check('  now is fine', o2.state is State.PASS)
    with seeded(body=GOOD_PART) as (root, tmp):
        rec = W._record(W.probe('pbp_participation', 2026, root, tmp))
        el = AV.eligibility_record(dict(rec, retrieved_at=ahead.isoformat()))
        check('  a real, verifiable record with a FUTURE retrieved_at is '
              'refused on that ground specifically',
              el['ordering_ok'] is False
              and el['ordering_code'] == 'RETRIEVED_AT_IN_FUTURE',
              el['ordering_code'])


# ==========================================================================
# H. forgery and missing evidence
# ==========================================================================
def test_h_forged_record_and_missing_blob():
    print('\nH. a manifest row is a claim; the blob is the evidence')
    with seeded(body=GOOD_PART) as (root, tmp):
        rec = W._record(W.probe('pbp_participation', 2026, root, tmp))
        forged = dict(rec, sha256='0' * 64)
        v = AV.verify_record(forged, repo_root=W._REPO)
        check('a row whose digest does not match the bytes -> FAIL',
              v.state is State.FAIL and v.code == 'RECORD_DIGEST_MISMATCH', v.code)
        missing = dict(rec, blob='nfl/availability_raw/does_not_exist.csv.gz')
        v2 = AV.verify_record(missing, repo_root=W._REPO)
        check('a row naming a blob that is not on disk -> FAIL RAW_BLOB_MISSING',
              v2.state is State.FAIL and v2.code == 'RAW_BLOB_MISSING', v2.code)
        v3 = AV.verify_record(dict(rec, blob=None), repo_root=W._REPO)
        check('AVAILABLE with no evidence named at all -> FAIL',
              v3.state is State.FAIL
              and v3.code == 'AVAILABLE_RECORD_WITHOUT_EVIDENCE', v3.code)
        v4 = AV.verify_record(rec, repo_root=W._REPO)
        check('  the honest row still verifies', v4.state is State.PASS, v4.code)


# ==========================================================================
# I. first-seen
# ==========================================================================
def test_i_first_seen_is_written_once_and_never_moved():
    print('\nI. first-seen is write-once')
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d) / 'fs.json'
        r1 = AV.record_first_seen('pbp_participation_2026',
                                  {'first_retrieved_at': '2026-09-09T01:00:00+00:00',
                                   'sha256': 'a' * 64}, path=p)
        check('the first observation is recorded', r1.state is State.PASS, r1.code)
        check('  with the required wording',
              r1.value['wording'] ==
              'First observed available by this capture system.')
        check('  and an explicit disclaimer about true publication time',
              'not observable from here' in r1.value['not_a_claim_about'])
        r2 = AV.record_first_seen('pbp_participation_2026',
                                  {'first_retrieved_at': '2026-10-01T01:00:00+00:00',
                                   'sha256': 'b' * 64}, path=p)
        check('a LATER observation does not move it',
              r2.state is State.NOT_APPLICABLE
              and r2.code == 'FIRST_SEEN_ALREADY_RECORDED', r2.code)
        book = AV.load_first_seen(p)
        check('  the stored value is still the FIRST one',
              book['pbp_participation_2026']['first_retrieved_at']
              == '2026-09-09T01:00:00+00:00',
              book['pbp_participation_2026']['first_retrieved_at'])
        check('  and still the first digest',
              book['pbp_participation_2026']['sha256'] == 'a' * 64)


# ==========================================================================
# J. THE SEPARATION FROM T-90 AND THE OBLIGATION CASCADE
# ==========================================================================
def test_j_the_watch_can_discharge_nothing():
    print('\nJ. a periodic poll may not discharge an event-anchored obligation')
    for kind in ('practice', 'final_status', 'inactives'):
        for src in AV.WATCHED:
            check(f'{src} cannot discharge {kind}',
                  REG.can_discharge(src, kind) is False)
    for src in AV.WATCHED:
        check(f'{src} serves no capture kind at all',
              REG.BY_NAME[src].serves_kinds == ())
        check(f'{src} is watch_only', REG.BY_NAME[src].watch_only is True)

    with seeded(body=GOOD_PART) as (root, tmp):
        rec = W._record(W.probe('pbp_participation', 2026, root, tmp))
    check('the emitted row claims no discharge', rec['discharges'] == [])
    check('  and the guard confirms it',
          rec['no_discharge_guard']['state'] == 'PASS')
    check('  the row carries no game_id -- it is not attributed to a game',
          'game_id' not in rec)
    check('  and it is labelled a periodic probe, not an execution target',
          rec['watch_kind'] == 'periodic_availability_probe'
          and 'execution_target' not in rec)

    forged = dict(rec, discharges=['inactives'])
    g = AV.assert_no_discharge(forged)
    check('a row that GREW a discharge claim is refused',
          g.state is State.FAIL
          and g.code == 'AVAILABILITY_WATCH_CLAIMED_A_DISCHARGE', g.code)
    g2 = AV.assert_no_discharge(dict(rec, execution_target={'targets': [1]}))
    check('  as is one that grew an execution target',
          g2.state is State.FAIL, g2.code)


def test_j2_the_vintage_capture_path_never_fetches_a_watched_source():
    print('\nJ2. the two capture paths do not overlap')
    fetched = [s.name for s in CV._sources(2026)]
    for src in AV.WATCHED:
        check(f'{src} is NOT fetched by the vintage capture', src not in fetched)
    codes = {o.evidence.get('source'): o.code for o in CV.pending_sources(2026)}
    for src in AV.WATCHED:
        check(f'  {src} is reported as deliberately elsewhere, not as silence',
              codes.get(src) == 'WATCH_ONLY_SOURCE_NOT_CAPTURED_HERE',
              codes.get(src))
    check('the injury/inactives sources are still fetched there',
          'official_inactives' in fetched and 'official_injury_report' in fetched)
    check('a watched source cannot discharge the injury obligation either',
          not REG.can_discharge('snap_counts', 'practice'))


# ==========================================================================
# L. THE HISTORICAL-VINTAGE GUARD
# ==========================================================================
def test_l_no_final_file_timestamp_becomes_point_in_time_evidence():
    print('\nL. a final file\'s Last-Modified is never as-of evidence')
    # The two watched sources deliberately derive NO date interval from their
    # own Last-Modified, unlike `injuries` and `schedules`, which do. The
    # difference is not an oversight: a season file that upstream rewrites is a
    # FINAL WRITE, and narrowing on it would manufacture a validity window that
    # was never observed. Measured 2026-09-08: pbp_participation_2025.csv reads
    # 10 Feb 2026 and pbp_participation_2024.csv reads 04 Sep 2025 -- both after
    # their seasons, and neither says anything about in-season availability.
    for src in AV.WATCHED:
        spec = REG.BY_NAME[src]
        check(f'{src} derives no narrowed scope kind',
              spec.narrow_to_kind is None, spec.narrow_to_kind)
        check(f'  {src} declares no narrowing method',
              spec.narrow_method is None, spec.narrow_method)
        check(f'  {src} states WHY in its evidence',
              'as-of' in (spec.narrow_evidence or '')
              or 'NOT NARROWED' in (spec.narrow_evidence or ''),
              spec.narrow_evidence)
    check('by contrast, injuries DOES narrow on Last-Modified -- so the '
          'difference above is a decision, not an absence',
          REG.BY_NAME['injuries'].narrow_to_kind is not None)

    # No backfilled vintage: the first-seen ledger can only be written by an
    # actual observation, and a hand-written past date cannot displace one.
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d) / 'fs.json'
        AV.record_first_seen('pbp_participation_2026',
                             {'first_retrieved_at': '2026-09-09T01:00:00+00:00'},
                             path=p)
        AV.record_first_seen('pbp_participation_2026',
                             {'first_retrieved_at': '2020-01-01T00:00:00+00:00'},
                             path=p)
        check('a backdated first-seen cannot displace a real observation',
              AV.load_first_seen(p)['pbp_participation_2026'][
                  'first_retrieved_at'] == '2026-09-09T01:00:00+00:00')

    # The accepted schemas are read from final files, and that use is legitimate
    # BECAUSE it is a claim about column names and nothing else.
    check('the accepted-schema constants are column names only, carrying no '
          'timestamp of any kind',
          all(isinstance(c, str) and not any(ch.isdigit() for ch in c)
              or c in ('x1d',)
              for shape in AV.ACCEPTED_SCHEMAS.values()
              for cols in shape for c in cols))
    with seeded(body=GOOD_PART) as (root, tmp):
        rec = W._record(W.probe('pbp_participation', 2026, root, tmp))
    check('  a row keeps source_timestamp and retrieved_at as separate fields',
          rec['source_timestamp'] != rec['retrieved_at']
          and rec['source_timestamp_header'] == 'Last-Modified')
    check('  effective_for_date is the SEASON, not a date derived from the '
          'file\'s own clock',
          rec['provenance']['effective_for_date'] == '2026')


# ==========================================================================
# K. GUARD DELETION PROOFS
# ==========================================================================
def test_k_guard_deletions():
    print('\nK. load-bearing proofs: bypass the guard, lose the refusal')

    # K1 -- the body-is-data guard, on the real measured case.
    def run_body():
        with seeded(body=b'Not Found') as (root, tmp):
            return W.probe('pbp_participation', 2026, root, tmp)
    assert_guard_is_load_bearing(
        run=run_body, module_path='nfl.capture.availability',
        attr='assert_body_is_data',
        caught=lambda o: o.state is State.FAIL
        and o.code in ('BODY_IS_ERROR_TEXT', 'BODY_IS_HTML_NOT_DATA'),
        returns=Outcome.ok('STUB', value=True))
    check('K1 assert_body_is_data is load-bearing '
          '(bypassed, "Not Found" stops being caught by it)', True)
    with guard_bypassed('nfl.capture.availability', 'assert_body_is_data',
                        returns=Outcome.ok('STUB', value=True)):
        with seeded(body=b'Not Found') as (root, tmp):
            leaked = W.probe('pbp_participation', 2026, root, tmp)
    check('  and what the bypass produces is a stored blob over an error page',
          leaked.code != 'BODY_IS_ERROR_TEXT', leaked.code)

    # K2 -- the schema guard.
    drifted = list(PART_HEADER) + ['surprise']
    body = (','.join(drifted) + '\n' + ','.join(['x'] * len(drifted)) + '\n').encode()

    def run_schema():
        with seeded(body=body) as (root, tmp):
            return W.probe('pbp_participation', 2026, root, tmp)
    assert_guard_is_load_bearing(
        run=run_schema, module_path='nfl.capture.availability',
        attr='assert_schema_accepted',
        caught=lambda o: o.state is State.FAIL and o.code == 'SCHEMA_CHANGED',
        returns=Outcome.ok('STUB', value=()))
    check('K2 assert_schema_accepted is load-bearing '
          '(bypassed, an unknown 27-column file passes as AVAILABLE)', True)

    # K3 -- the future-clock guard.
    # K3 -- the future-clock guard. The record must otherwise VERIFY, or
    # verify_record fires first and the proof would be about the wrong guard.
    with seeded(body=GOOD_PART) as (root, tmp):
        real = W._record(W.probe('pbp_participation', 2026, root, tmp))
        ahead = (dt.datetime.now(dt.timezone.utc)
                 + dt.timedelta(days=1)).isoformat()

        def run_future():
            return AV.eligibility_record(dict(real, retrieved_at=ahead))
        assert_guard_is_load_bearing(
            run=run_future, module_path='nfl.capture.availability',
            attr='assert_not_future',
            caught=lambda r: r['ordering_ok'] is False
            and r['ordering_code'] == 'RETRIEVED_AT_IN_FUTURE',
            returns=Outcome.ok('STUB', value=0.0))
    check('K3 assert_not_future is load-bearing', True)

    # K4 -- the no-discharge guard.
    def run_discharge():
        return AV.assert_no_discharge({'source': 'pbp_participation',
                                       'discharges': ['inactives']})
    assert_guard_is_load_bearing(
        run=run_discharge, module_path='nfl.capture.availability',
        attr='assert_no_discharge',
        caught=lambda o: o.state is State.FAIL,
        returns=Outcome.ok('STUB', value=True))
    check('K4 assert_no_discharge is load-bearing', True)


if __name__ == '__main__':
    test_a_404_is_not_published_not_a_pass_and_not_a_failure()
    test_a2_a_not_published_record_may_never_carry_bytes()
    test_b_200_over_an_error_body_is_rejected_as_data()
    test_b2_header_only_and_malformed_csv()
    test_c_available_is_recorded_but_grants_nothing()
    test_c2_ordering_is_computed_but_never_authorises()
    test_d_wrong_season_and_wrong_source()
    test_e_schema_drift_and_reordering_fail_closed()
    test_e2_both_accepted_participation_schemas_are_accepted()
    test_f_duplicate_identical_bytes_and_changed_bytes()
    test_f2_changed_bytes_under_the_SAME_source_clock()
    test_f3_cache_hit_does_not_restamp()
    test_g_source_clock_later_than_retrieval_is_impossible()
    test_g2_future_retrieved_at_is_refused()
    test_h_forged_record_and_missing_blob()
    test_i_first_seen_is_written_once_and_never_moved()
    test_j_the_watch_can_discharge_nothing()
    test_j2_the_vintage_capture_path_never_fetches_a_watched_source()
    test_l_no_final_file_timestamp_becomes_point_in_time_evidence()
    test_k_guard_deletions()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
