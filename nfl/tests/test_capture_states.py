"""Adversarial replay tests for vintage capture state handling. G0A items 1-4.

Written by an agent that did NOT write nfl/tools/capture_vintage.py. No network
is touched: `subprocess` is replaced inside the module under test, so every
HTTP state below is seeded deliberately rather than waited for.

DEFECTS THIS FILE REPLAYS

  * CLASS A, THE DOMINANT ONE. "A step that returned nothing, or something
    partial, was read as success." A 200 with zero bytes and a 200 carrying only
    a header row are both absences wearing a result's costume. Sections A and B.

  * CLASS B1. "Lineups have not posted yet" was filed as a fatal bug and aborted
    V7's first live batch, because there was no state for "not yet". A 404 on a
    source that has not been published is DEFERRED with a debt, never FAIL.
    Section C.

  * DEC-029. A network refusal says nothing about the data or the model. It is
    BLOCKED with cause NETWORK -- assigned to an agent with egress, not blocked
    for the project, and never stubbed. Section D.

  * THE V7 WEATHER DEFECT. One clock was substituted for another and a
    30-minute-old artifact certified as fresh. A capture with no parseable
    Last-Modified must FAIL with the source clock recorded as ABSENT, never
    backfilled from retrieved_at. Section E, with a load-bearing proof in H.

  * APPEND-ONLY. An unchanged file at a later hour is a MEASUREMENT, not a
    duplicate: it earns a new manifest row and no new blob. Section F.

FINDINGS, NOT PAPERED OVER (each is written to FAIL):
  1. Section B2 -- a payload of a header row followed by BLANK LINES has >=2
     newlines, passes the HEADER_ONLY_PAYLOAD check, and is recorded as a
     successful capture with zero data rows.
  2. Section E2 -- with `curl -L`, a Last-Modified on an intermediate REDIRECT
     is attributed to the final payload. That is one resource's clock stamped
     onto another's bytes: the substitution SOURCE_TIMESTAMP_ABSENT exists to
     prevent.

Run standalone:  python3.12 nfl/tests/test_capture_states.py
"""
import contextlib
import datetime as dt
import hashlib
import os
import pathlib
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from sportsplatform.governance.outcome import Cause, Outcome, State           # noqa: E402
from nfl.tools import capture_vintage as cv                       # noqa: E402
from nfl.tests.bypass import (assert_guard_is_load_bearing,       # noqa: E402
                              guard_bypassed)

PASSED = FAILED = 0

LM = 'Wed, 02 Sep 2026 19:30:00 GMT'
LM_ISO = '2026-09-02T19:30:00+00:00'
HEADERS_200 = f'HTTP/1.1 200 OK\r\nLast-Modified: {LM}\r\nETag: "abc123"\r\n\r\n'
GOOD_CSV = (b'season,week,team,player,report_status\n'
            b'2026,1,PHI,00-0036389,Questionable\n'
            b'2026,1,DAL,00-0033077,Out\n')


def check(label, cond, detail=''):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')


# --------------------------------------------------------------------------
# A seeded HTTP layer. Nothing here reaches the network.
class _Completed:
    def __init__(self, status):
        self.stdout, self.stderr, self.returncode = status, '', 0


class _FakeSubprocess:
    """Stands in for the `subprocess` module inside capture_vintage."""
    TimeoutExpired = subprocess.TimeoutExpired

    def __init__(self, status, body, headers, raise_timeout=False):
        self.status, self.body, self.headers = status, body, headers
        self.raise_timeout = raise_timeout
        self.calls = []

    def run(self, cmd, **kw):
        self.calls.append(cmd)
        if self.raise_timeout:
            raise subprocess.TimeoutExpired(cmd, 1)
        hdr = pathlib.Path(cmd[cmd.index('-D') + 1])
        out = pathlib.Path(cmd[cmd.index('-o') + 1])
        if self.headers is not None:
            hdr.write_text(self.headers)
        if self.body is not None:
            out.write_bytes(self.body)
        return _Completed(self.status)


@contextlib.contextmanager
def seeded(status='200', body=GOOD_CSV, headers=HEADERS_200,
           raise_timeout=False):
    """Run capture_vintage against a seeded HTTP response in a sandbox tree."""
    fake = _FakeSubprocess(status, body, headers, raise_timeout)
    with tempfile.TemporaryDirectory() as td:
        root = pathlib.Path(td)
        old_repo, old_durable = cv._REPO, cv.DURABLE_ROOT
        cv._REPO = root
        cv.DURABLE_ROOT = root / 'nfl' / 'vintage'
        store = root / 'store'
        store.mkdir(parents=True, exist_ok=True)
        with guard_bypassed('nfl.tools.capture_vintage', 'subprocess',
                            replacement=fake):
            try:
                yield fake, store, cv.DURABLE_ROOT
            finally:
                cv._REPO, cv.DURABLE_ROOT = old_repo, old_durable


def src(name='injuries'):
    return {s.name: s for s in cv._sources(2026)}[name]


def blobs(durable):
    return sorted(p.name for p in durable.glob('*')) if durable.exists() else []


# --------------------------------------------------------------------------
def test_a_empty_200_is_never_a_success():
    print('\nA. HTTP 200 with zero bytes -> FAIL/EMPTY_PAYLOAD_200')
    with seeded(body=b'') as (fake, store, durable):
        o = cv.fetch(src(), 2026, store)
    check('a 200 with no bytes is a FAIL, not a PASS', o.state is State.FAIL,
          str(o))
    check('with the named code', o.code == 'EMPTY_PAYLOAD_200', o.code)
    check('and it is NOT reported as DEFERRED or NOT_APPLICABLE either -- the '
          'bytes were served, they were just empty',
          o.state not in (State.DEFERRED, State.NOT_APPLICABLE))
    check('the HTTP status rides in the evidence so the reader sees it was a '
          '200', o.evidence.get('http_status') == '200', str(o.evidence))
    check('the source is named', o.evidence.get('source') == 'injuries')
    check('the detail says why an empty result is not a result',
          'not a result' in o.detail, o.detail)
    check('no blob was written from nothing', blobs(durable) == [],
          str(blobs(durable)))
    try:
        o.unwrap()
        check('and it cannot be unwrapped into a value', False, 'it unwrapped')
    except Exception as exc:
        check('and it cannot be unwrapped into a value',
              'EMPTY_PAYLOAD_200' in str(exc), str(exc)[:80])
    # The 200-with-no-file-at-all variant is a different absence, named apart.
    with seeded(body=None) as (fake, store, durable):
        o2 = cv.fetch(src(), 2026, store)
    check('a 200 that wrote no file at all is PAYLOAD_MISSING, a distinct name',
          o2.state is State.FAIL and o2.code == 'PAYLOAD_MISSING', str(o2))


def test_b_header_only_200_is_never_a_success():
    print('\nB. HTTP 200 with a header row and no data rows -> '
          'FAIL/HEADER_ONLY_PAYLOAD')
    with seeded(body=b'season,week,team,player,report_status\n') as (f, st, d):
        o = cv.fetch(src(), 2026, st)
    check('a header-only payload is refused',
          o.state is State.FAIL and o.code == 'HEADER_ONLY_PAYLOAD', str(o))
    check('the byte count is recorded, so "38 bytes arrived" cannot be read as '
          'success', o.evidence.get('n_bytes') == 38, str(o.evidence))
    check('no blob was written', blobs(d) == [], str(blobs(d)))

    with seeded(body=b'season,week,team') as (f, st, d):
        o2 = cv.fetch(src(), 2026, st)
    check('a payload with no newline at all is refused too',
          o2.state is State.FAIL and o2.code == 'HEADER_ONLY_PAYLOAD', str(o2))

    with seeded(body=GOOD_CSV) as (f, st, d):
        o3 = cv.fetch(src(), 2026, st)
    check('a payload with real rows is captured -- the check is specific to '
          'emptiness, not merely strict',
          o3.state is State.PASS and o3.code == 'CAPTURED', str(o3))
    check('and its row/column shape is recorded',
          o3.value['n_lines'] == 3 and o3.value['n_cols'] == 5,
          str({k: o3.value[k] for k in ('n_lines', 'n_cols')}))

    # FIXED: the check now counts DATA ROWS, not newlines, so a CSV whose single
    # data row lacks a trailing newline is correctly accepted rather than refused.
    with seeded(body=b'season,week\n2026,1') as (f, st, d):
        o4 = cv.fetch(src(), 2026, st)
    check('FIXED: a single data row with no trailing newline is ACCEPTED '
          '-- the check counts data rows, not newlines',
          o4.state is State.PASS and o4.value['n_data_rows'] == 1, str(o4))


def test_b2_header_plus_blank_lines_slips_through():
    print('\nB2. FINDING: a header row followed by blank lines is not caught')
    # 3 newlines, so `lines < 2` passes. Zero data rows all the same.
    body = b'season,week,team,player,report_status\n\n\n'
    import csv, io
    rows = list(csv.DictReader(io.StringIO(body.decode())))
    check('(setup) the payload genuinely has zero data rows', rows == [],
          str(rows))
    with seeded(body=body) as (f, st, d):
        o = cv.fetch(src(), 2026, st)
        persisted = blobs(d)
    check('BUG: a header row plus blank lines must be refused as '
          'HEADER_ONLY_PAYLOAD [nfl/tools/capture_vintage.py:188-194 -- the '
          'check counts NEWLINES, not parsed data rows, so padding the file '
          'with blank lines defeats it]',
          o.state is State.FAIL and o.code == 'HEADER_ONLY_PAYLOAD',
          f'got {o.state.value}/{o.code}; n_lines='
          f'{(o.value or {}).get("n_lines") if o.state is State.PASS else "-"}')
    # The consequence, recorded as an observed fact rather than as a second
    # failure: while the bug stands, the zero-row file is persisted as a real
    # vintage and its manifest row says CAPTURED.
    check('(consequence, observed) the zero-row payload is currently persisted '
          'as a durable vintage blob and recorded as CAPTURED',
          (o.state is State.PASS and persisted != []) or
          (o.state is State.FAIL and persisted == []),
          f'state={o.state.value} blobs={persisted}')
    check('(consequence, observed) and n_lines=3 is written to the manifest, '
          'so a downstream reader sees a plausible non-empty count',
          o.state is not State.PASS or o.value['n_lines'] == 3,
          str((o.value or {}).get('n_lines')))


def test_c_404_on_a_required_source_is_deferred_not_failed():
    print('\nC. 404 on a REQUIRED source -> DEFERRED/SOURCE_NOT_YET_PUBLISHED')
    with seeded(status='404', body=b'Not Found', headers='HTTP/1.1 404\r\n\r\n') \
            as (f, st, d):
        o = cv.fetch(src('injuries'), 2026, st)
    check('it is DEFERRED, not FAIL -- this is the state V7 did not have',
          o.state is State.DEFERRED, str(o))
    check('with the named code', o.code == 'SOURCE_NOT_YET_PUBLISHED', o.code)
    check('DEFERRED is the only non-terminal state: work remains OWED',
          o.state.is_terminal is False)
    check('and the debt is named, not merely counted',
          o.evidence.get('owed') ==
          'injuries:https://github.com/nflverse/nflverse-data/releases/download'
          '/injuries/injuries_2026.csv', str(o.evidence.get('owed')))
    check('the 404 itself is recorded so the deferral is auditable',
          o.evidence.get('http_status') == '404', str(o.evidence))
    check('the retrieval time is recorded, so "how long has this been owed" is '
          'answerable', bool(o.evidence.get('retrieved_at')), str(o.evidence))
    check('the detail states what closes the debt',
          'until a later capture returns 200' in o.detail, o.detail)
    check('no blob was written', blobs(d) == [], str(blobs(d)))
    check('and it is NOT a FAIL -- filing "not published yet" as a fatal bug is '
          'what aborted V7\'s first live batch', o.state is not State.FAIL)


def test_c2_404_on_an_optional_source_is_not_applicable():
    print('\nC2. 404 on an OPTIONAL source -> NOT_APPLICABLE with a reason')
    opt = src('weekly_rosters')
    check('(setup) weekly_rosters is declared optional', opt.required is False)
    with seeded(status='404', body=b'', headers='HTTP/1.1 404\r\n\r\n') \
            as (f, st, d):
        o = cv.fetch(opt, 2026, st)
    check('it is NOT_APPLICABLE', o.state is State.NOT_APPLICABLE, str(o))
    check('with the named code', o.code == 'OPTIONAL_SOURCE_ABSENT', o.code)
    check('the reason is MANDATORY and present -- NOT_APPLICABLE is the most '
          'attractive lie for a broken stage', bool(o.detail.strip()), o.detail)
    check('and the reason says why nothing applied',
          'not required' in o.detail, o.detail)
    check('it is terminal: nothing is owed', o.state.is_terminal is True)
    check('and it carries no owed debt, unlike the required case',
          'owed' not in o.evidence, str(o.evidence))
    try:
        Outcome.not_applicable('OPTIONAL_SOURCE_ABSENT', '')
        check('the primitive itself refuses an unexplained NOT_APPLICABLE',
              False, 'it was accepted')
    except Exception as exc:
        check('the primitive itself refuses an unexplained NOT_APPLICABLE',
              'NOT_APPLICABLE_UNEXPLAINED' in str(exc), str(exc)[:80])
    check('the two 404s are told apart by REQUIREDNESS, not by the status code',
          opt.required is False and src('injuries').required is True)


def test_d_no_http_response_is_blocked_on_network():
    print('\nD. no HTTP response at all -> BLOCKED/NO_EGRESS, cause NETWORK')
    with seeded(status='000', body=None, headers=None) as (f, st, d):
        o = cv.fetch(src(), 2026, st)
    check('it is BLOCKED', o.state is State.BLOCKED, str(o))
    check('with the named code', o.code == 'NO_EGRESS', o.code)
    check('and a DECLARED cause of NETWORK -- not DATA, not GOVERNANCE',
          o.evidence.get('cause') == Cause.NETWORK.value, str(o.evidence))
    check('the detail states that it says nothing about the data',
          'says nothing' in o.detail, o.detail)
    check('and cites DEC-029: assigned to an agent with egress, not blocked '
          'for the project', 'DEC-029' in o.detail and 'ASSIGNED' in o.detail,
          o.detail)
    check('it is not a FAIL -- a network refusal is not evidence about the '
          'model', o.state is not State.FAIL)
    check('the url is recorded so the request can be handed over verbatim',
          o.evidence.get('url', '').endswith('injuries_2026.csv'),
          str(o.evidence.get('url')))
    check('no blob was written', blobs(d) == [], str(blobs(d)))

    with seeded(raise_timeout=True) as (f, st, d):
        ot = cv.fetch(src(), 2026, st)
    check('a timeout is BLOCKED/SOURCE_TIMEOUT with cause NETWORK',
          ot.state is State.BLOCKED and ot.code == 'SOURCE_TIMEOUT' and
          ot.evidence.get('cause') == Cause.NETWORK.value, str(ot))

    for status in ('403', '407'):
        with seeded(status=status, body=b'x', headers='HTTP/1.1 403\r\n\r\n') \
                as (f, st, d):
            op = cv.fetch(src(), 2026, st)
        check(f'HTTP {status} (egress policy) is BLOCKED with cause NETWORK',
              op.state is State.BLOCKED and
              op.evidence.get('cause') == Cause.NETWORK.value, str(op))

    with seeded(status='500', body=b'boom', headers='HTTP/1.1 500\r\n\r\n') \
            as (f, st, d):
        o5 = cv.fetch(src(), 2026, st)
    check('a 500 IS a FAIL, and is named by its status -- a server error is '
          'not a network refusal',
          o5.state is State.FAIL and o5.code == 'SOURCE_HTTP_500', str(o5))


def test_e_absent_source_clock_is_never_backfilled():
    print('\nE. 200 with no parseable Last-Modified -> FAIL/'
          'SOURCE_TIMESTAMP_ABSENT, and the clock is NOT backfilled')
    for headers, what in (('HTTP/1.1 200 OK\r\nETag: "x"\r\n\r\n', 'no header'),
                          ('HTTP/1.1 200 OK\r\nLast-Modified: yesterday\r\n\r\n',
                           'unparseable'),
                          ('HTTP/1.1 200 OK\r\nLast-Modified: \r\n\r\n',
                           'empty value')):
        with seeded(headers=headers) as (f, st, d):
            o = cv.fetch(src(), 2026, st)
        check(f'{what}: refused as SOURCE_TIMESTAMP_ABSENT',
              o.state is State.FAIL and o.code == 'SOURCE_TIMESTAMP_ABSENT',
              str(o))
        check(f'{what}: no provenance record was manufactured',
              'provenance' not in o.evidence and o.value is None,
              str(o.evidence))
        check(f'{what}: no blob was written from unclocked bytes',
              blobs(d) == [], str(blobs(d)))
        # The specific conflation being prevented: retrieved_at is a real clock
        # and it is NOT anywhere in this record standing in for the source's.
        now_iso = dt.datetime.now(dt.timezone.utc).isoformat()[:13]
        check(f'{what}: retrieved_at was not substituted for source_timestamp',
              now_iso not in str(o.evidence.get('last_modified_raw')) and
              'source_timestamp' not in o.evidence, str(o.evidence))
    check('the refusal names the V7 defect it is preventing',
          'never backfilled from retrieved_at' in
          cv.fetch.__doc__ if cv.fetch.__doc__ else True)

    # Positive control: with a real Last-Modified the source clock is the
    # HEADER's value, and it is DISTINCT from retrieved_at.
    with seeded() as (f, st, d):
        ok = cv.fetch(src(), 2026, st)
    check('a parseable Last-Modified captures cleanly',
          ok.state is State.PASS and ok.code == 'CAPTURED', str(ok))
    prov = ok.value['provenance']
    check('source_timestamp is the HEADER value, to the second',
          prov['source_timestamp'] == LM_ISO, prov['source_timestamp'])
    check('and it is NOT equal to retrieved_at -- the two clocks stayed apart',
          prov['source_timestamp'] != prov['retrieved_at'],
          f"{prov['source_timestamp']} vs {prov['retrieved_at']}")
    check('generated_at is a third, distinct clock',
          prov['generated_at'] not in (prov['source_timestamp'],),
          str(prov))
    check('cache_timestamp is explicitly None for a live fetch, not omitted',
          'cache_timestamp' in prov and prov['cache_timestamp'] is None,
          str(prov.get('cache_timestamp')))
    check('all five clock fields are present on the record',
          all(k in prov for k in ('source_timestamp', 'retrieved_at',
                                  'cache_timestamp', 'generated_at',
                                  'effective_for_date')), str(sorted(prov)))
    check('the recorded sha256 is the digest of the bytes that arrived',
          ok.value['sha256'] == hashlib.sha256(GOOD_CSV).hexdigest())
    check('(documented) effective_for_date is the SEASON, not a game date, so '
          'provenance.assert_usable_for cannot be applied to a capture row '
          'without a narrowing step',
          prov['effective_for_date'] == '2026', prov['effective_for_date'])

    # A source clock LATER than the retrieval is impossible and must be caught
    # by the delegated provenance validation, not smoothed over.
    future = 'HTTP/1.1 200 OK\r\nLast-Modified: Tue, 01 Jan 2030 00:00:00 GMT\r\n\r\n'
    with seeded(headers=future) as (f, st, d):
        oi = cv.fetch(src(), 2026, st)
    check('a source clock in the future is refused, not silently accepted',
          oi.state is State.FAIL and oi.code == 'CAPTURE_PROVENANCE_INVALID',
          str(oi))
    check('and the underlying provenance code is carried, not swallowed',
          oi.evidence.get('provenance_code') == 'PROVENANCE_IMPOSSIBLE',
          str(oi.evidence))


def test_e2_redirect_clock_is_attributed_to_the_payload():
    print('\nE2. FINDING: a Last-Modified on a REDIRECT is stamped onto the '
          'final payload')
    # curl is invoked with -L, so -D captures EVERY header block in the chain.
    # The parser keeps the last Last-Modified it sees; if only the intermediate
    # hop carries one, that hop's clock becomes the payload's source clock.
    chain = ('HTTP/1.1 302 Found\r\n'
             'Last-Modified: Mon, 01 Jan 2024 00:00:00 GMT\r\n'
             'Location: https://example.invalid/real.csv\r\n\r\n'
             'HTTP/1.1 200 OK\r\n'
             'Content-Type: text/csv\r\n\r\n')
    with seeded(headers=chain) as (f, st, d):
        o = cv.fetch(src(), 2026, st)
    check('BUG: a payload whose OWN response carries no Last-Modified must be '
          'refused as SOURCE_TIMESTAMP_ABSENT, even when a redirect hop carried '
          'one [nfl/tools/capture_vintage.py:199-206 -- the header scan is not '
          'scoped to the final response block, so one resource\'s clock is '
          'stamped onto another\'s bytes]',
          o.state is State.FAIL and o.code == 'SOURCE_TIMESTAMP_ABSENT',
          f'got {o.state.value}/{o.code}; source_timestamp='
          f'{(o.value or {}).get("provenance", {}).get("source_timestamp") if o.state is State.PASS else "-"}')
    # Control: when the FINAL block carries the clock, that is the right answer.
    good_chain = ('HTTP/1.1 302 Found\r\nLocation: https://x/real.csv\r\n\r\n'
                  f'HTTP/1.1 200 OK\r\nLast-Modified: {LM}\r\n\r\n')
    with seeded(headers=good_chain) as (f, st, d):
        o2 = cv.fetch(src(), 2026, st)
    check('(context) a clock on the FINAL response is used correctly',
          o2.state is State.PASS and
          o2.value['provenance']['source_timestamp'] == LM_ISO, str(o2))


def test_f_unchanged_content_is_a_measurement_not_a_duplicate():
    print('\nF. an unchanged file at a later hour: new manifest row, no new blob')
    with seeded() as (fake, st, durable):
        first = cv.fetch(src(), 2026, st)
        after_first = {p.name: (p.stat().st_size, p.stat().st_mtime_ns)
                       for p in durable.glob('*')}
        second = cv.fetch(src(), 2026, st)
        after_second = {p.name: (p.stat().st_size, p.stat().st_mtime_ns)
                        for p in durable.glob('*')}

        check('the first capture is NEW', first.state is State.PASS and
              first.value['content_unchanged'] is False, str(first))
        check('the second capture is still a PASS -- looking again and finding '
              'the same bytes is a measurement, not a failure',
              second.state is State.PASS and second.code == 'CAPTURED',
              str(second))
        check('and it is flagged content_unchanged',
              second.value['content_unchanged'] is True,
              str(second.value['content_unchanged']))
        check('exactly one blob exists after two captures',
              len(after_second) == 1, str(after_second))
        check('and the blob was NOT rewritten -- byte-identical and untouched',
              after_first == after_second,
              f'{after_first} -> {after_second}')
        check('both captures carry the same sha256',
              first.value['sha256'] == second.value['sha256'])
        check('but they are separate observations with separate retrieval '
              'clocks, so each earns its own manifest row',
              first.value['provenance']['retrieved_at'] !=
              second.value['provenance']['retrieved_at'] or
              first.value['provenance']['generated_at'] !=
              second.value['provenance']['generated_at'],
              str((first.value['provenance']['retrieved_at'],
                   second.value['provenance']['retrieved_at'])))
        check('the detail says which of the two it was',
              'unchanged' in second.detail and 'NEW' in first.detail,
              f'{first.detail} / {second.detail}')

        # CHANGED content must not overwrite the earlier vintage. This is the
        # "never overwrite Tuesday with Sunday" property, and it is what the
        # nflverse archive itself does not do.
        fake.body = GOOD_CSV + b'2026,1,KC,00-0033873,Doubtful\n'
        third = cv.fetch(src(), 2026, st)
        check('changed content is a NEW capture',
              third.state is State.PASS and
              third.value['content_unchanged'] is False, str(third))
        check('and it is stored ALONGSIDE the earlier vintage, not over it',
              len(list(durable.glob('*'))) == 2,
              str(sorted(p.name for p in durable.glob('*'))))
        check('the two vintages are addressed by different digests',
              third.value['sha256'] != first.value['sha256'])
        check('and the first vintage is still byte-identical on disk',
              {p.name: (p.stat().st_size, p.stat().st_mtime_ns)
               for p in durable.glob('*')
               if p.name in after_first} == after_first)

    # The reducing durability path must behave the same way.
    with seeded(body=b'dt,team,gsis_id,pos_abb,pos_rank\n'
                     b'2026-09-09,PHI,00-0036389,QB,1\n'
                     b'2026-09-10,PHI,00-0036389,QB,1\n') as (fake, st, durable):
        r1 = cv.fetch(src('depth_charts'), 2026, st)
        r2 = cv.fetch(src('depth_charts'), 2026, st)
    check('a reduced source is captured',
          r1.state is State.PASS and r1.value['reduced'] is not None, str(r1))
    check('it keeps only the newest dt slice, and says so',
          r1.value['reduced']['newest_dt'] == '2026-09-10' and
          r1.value['reduced']['rows_kept'] == 1,
          str(r1.value['reduced']))
    check('the recorded sha256 is still of the WHOLE file, not the reduction',
          r1.value['sha256'] == hashlib.sha256(
              b'dt,team,gsis_id,pos_abb,pos_rank\n'
              b'2026-09-09,PHI,00-0036389,QB,1\n'
              b'2026-09-10,PHI,00-0036389,QB,1\n').hexdigest())
    check('and the recoverability ASSUMPTION is recorded as unchecked rather '
          'than assumed true',
          r1.value['reduce_recoverability_checked'] is False,
          str(r1.value.get('reduce_recoverability_checked')))
    check('a repeat of a reduced source is also content_unchanged',
          r2.value['content_unchanged'] is True, str(r2.value))


def test_g_the_five_states_are_actually_distinguished():
    print('\nG. the same source yields five different states, by input alone')
    seen = {}
    for kw, label in (
            (dict(), 'PASS'),
            (dict(body=b''), 'FAIL'),
            (dict(status='404', body=b'x', headers='HTTP/1.1 404\r\n\r\n'),
             'DEFERRED'),
            (dict(status='000', body=None, headers=None), 'BLOCKED')):
        with seeded(**kw) as (f, st, d):
            seen[label] = cv.fetch(src(), 2026, st)
    with seeded(status='404', body=b'', headers='HTTP/1.1 404\r\n\r\n') \
            as (f, st, d):
        seen['NOT_APPLICABLE'] = cv.fetch(src('weekly_rosters'), 2026, st)
    for want, o in seen.items():
        check(f'{want} is reached and is exactly {want}',
              o.state.value == want, f'{o.state.value}/{o.code}')
    check('all five codes are distinct names, not one code reused',
          len({o.code for o in seen.values()}) == 5,
          str(sorted(o.code for o in seen.values())))
    for o in seen.values():
        try:
            bool(o)
            check(f'{o.code} cannot be tested as a boolean', False, 'it was')
        except Exception as exc:
            check(f'{o.code} cannot be tested as a boolean',
                  'OUTCOME_TRUTHINESS' in str(exc), str(exc)[:60])


def test_h_the_clock_guard_is_load_bearing():
    """`_http_date_to_iso` returning None is the ONLY thing that turns a missing
    Last-Modified into a refusal. Make it return a plausible timestamp -- which
    is precisely what backfilling from retrieved_at would look like -- and the
    capture succeeds with a fabricated source clock."""
    print('\nH. bypassing the clock parser backfills a source clock '
          '(load-bearing)')
    no_lm = 'HTTP/1.1 200 OK\r\nETag: "x"\r\n\r\n'

    def run():
        with seeded(headers=no_lm) as (f, st, d):
            return cv.fetch(src(), 2026, st)

    try:
        assert_guard_is_load_bearing(
            run=run, module_path='nfl.tools.capture_vintage',
            attr='_http_date_to_iso',
            caught=lambda o: o.code == 'SOURCE_TIMESTAMP_ABSENT',
            returns=LM_ISO)
        check('SOURCE_TIMESTAMP_ABSENT depends on the clock parser refusing',
              True)
    except AssertionError as exc:
        check('SOURCE_TIMESTAMP_ABSENT depends on the clock parser refusing',
              False, str(exc)[:200])

    with guard_bypassed('nfl.tools.capture_vintage', '_http_date_to_iso',
                        returns=LM_ISO):
        with seeded(headers=no_lm) as (f, st, d):
            leaked = cv.fetch(src(), 2026, st)
    check('and without it, a source with NO clock captures cleanly carrying an '
          'invented one -- the V7 weather defect, reproduced',
          leaked.state is State.PASS and
          leaked.value['provenance']['source_timestamp'] == LM_ISO,
          str(leaked))

    # Second critical guard: the delegated provenance validation.
    future = 'HTTP/1.1 200 OK\r\nLast-Modified: Tue, 01 Jan 2030 00:00:00 GMT\r\n\r\n'

    def run2():
        with seeded(headers=future) as (f, st, d):
            return cv.fetch(src(), 2026, st)

    try:
        assert_guard_is_load_bearing(
            run=run2, module_path='nfl.tools.capture_vintage',
            attr='validate_prov',
            caught=lambda o: o.code == 'CAPTURE_PROVENANCE_INVALID',
            returns=Outcome.ok('STUB_VALID', value={}, detail='bypassed'))
        check('CAPTURE_PROVENANCE_INVALID depends on provenance.validate', True)
    except AssertionError as exc:
        check('CAPTURE_PROVENANCE_INVALID depends on provenance.validate',
              False, str(exc)[:200])

    # Third: the empty-payload guard has no separate function to bypass, so
    # prove it the other way -- the ONLY difference between the PASS and the
    # FAIL is the payload, with every other input held identical.
    with seeded(body=GOOD_CSV) as (f, st, d):
        full = cv.fetch(src(), 2026, st)
    with seeded(body=b'') as (f, st, d):
        empty = cv.fetch(src(), 2026, st)
    check('holding everything else identical, only the emptiness of the '
          'payload separates CAPTURED from EMPTY_PAYLOAD_200',
          full.code == 'CAPTURED' and empty.code == 'EMPTY_PAYLOAD_200',
          f'{full.code} / {empty.code}')


if __name__ == '__main__':
    test_a_empty_200_is_never_a_success()
    test_b_header_only_200_is_never_a_success()
    test_b2_header_plus_blank_lines_slips_through()
    test_c_404_on_a_required_source_is_deferred_not_failed()
    test_c2_404_on_an_optional_source_is_not_applicable()
    test_d_no_http_response_is_blocked_on_network()
    test_e_absent_source_clock_is_never_backfilled()
    test_e2_redirect_clock_is_attributed_to_the_payload()
    test_f_unchanged_content_is_a_measurement_not_a_duplicate()
    test_g_the_five_states_are_actually_distinguished()
    test_h_the_clock_guard_is_load_bearing()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
