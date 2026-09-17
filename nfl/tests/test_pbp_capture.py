"""The pbp capture path, tested on its refusals before it is trusted.

EVERY TEST HERE IS A REFUSAL TEST, and that is the point. A capture path is
easy to make work on the happy path and the happy path is not what costs this
project: the recorded failures are a Git LFS pointer read as a corrupt log, a
connector read that dropped provenance and then reported provenance missing,
and an export that wrote 7,926 rows with every column blank. Each was a step
that returned something partial and was read as success.

So the fetcher is injectable and every test below hands it a body that is
wrong in one specific way.

THE REDIRECT CASE IS NOT HYPOTHETICAL. A live fetch of the real release
returned, in order:

    Content-Type: text/html; charset=utf-8
    Content-Length: 0
    HTTP/1.1 200 OK
    Content-Length: 1077501

A capture that validated on the first header block, or on a HEAD request,
would have seen zero bytes for a 1,077,501-byte file.
"""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import os
import pathlib
import sys
import tempfile

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sportsplatform.governance.outcome import Cause, State              # noqa: E402
from nfl.ingest import pbp_capture as PC                                # noqa: E402

PASSED = FAILED = 0
NOT_EXECUTED = []


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}: {detail}')


# ------------------------------------------------------------------ fixtures
def _csv(n_rows=4, cols=None, weeks=(1,), season=2026, drop=()):
    """A gzipped csv with the real column set, so drift tests are about drift."""
    cols = list(cols if cols is not None else _full_cols())
    cols = [c for c in cols if c not in drop]
    idx = {c: i for i, c in enumerate(cols)}
    out = io.StringIO()
    out.write(','.join(cols) + '\n')
    for r in range(n_rows):
        row = [''] * len(cols)
        for c, v in (('season', season), ('week', weeks[r % len(weeks)]),
                     ('season_type', 'REG'),
                     ('game_id', f'{season}_0{weeks[r % len(weeks)]}_AA_BB'),
                     ('play_id', r + 1), ('posteam', 'AA'),
                     ('defteam', 'BB'), ('home_team', 'BB'),
                     ('play_type', 'pass'), ('epa', 0.1)):
            if c in idx:
                row[idx[c]] = str(v)
        out.write(','.join(row) + '\n')
    return gzip.compress(out.getvalue().encode('utf-8'))


def _full_cols():
    """372 names, the required ones real and the remainder filler."""
    base = list(PC.REQUIRED_COLUMNS)
    base += [f'filler_{i}' for i in range(PC.EXPECTED_N_COLS - len(base))]
    assert len(base) == PC.EXPECTED_N_COLS, len(base)
    return base


def _opener(status='200', body=None, headers='HTTP/1.1 200 OK\n'):
    def go(u):
        return status, (_csv() if body is None else body), headers
    return go


# ============================================================ the happy path
def test_A_a_good_capture_records_everything_required():
    print('\nA. one clean capture, and every required field present')
    body = _csv(n_rows=6)
    digest = hashlib.sha256(body).hexdigest()
    with tempfile.TemporaryDirectory() as d:
        store = pathlib.Path(d) / 'vintage'
        man = pathlib.Path(d) / 'manifest.jsonl'
        o = PC.capture(2026, store=store, manifest=man,
                       opener=_opener(body=body))
        check('the capture passes', o.state is State.PASS,
              f'{o.state}[{o.code}] {o.detail[:200]}')
        if o.state is not State.PASS:
            NOT_EXECUTED.append('A: capture refused, nothing else checkable')
            return
        check('  one row was appended', man.exists()
              and len(man.read_text().strip().splitlines()) == 1)
        rec = json.loads(man.read_text().strip())
        v = rec['value']
        for f, why in (('sha256', 'the digest'),
                       ('n_bytes', 'the byte count'),
                       ('n_data_rows', 'the row count'),
                       ('n_cols', 'the column count'),
                       ('http_status', 'the HTTP status'),
                       ('url', 'the source url'),
                       ('blob', 'the archive path'),
                       ('retention_policy', 'the retention policy')):
            check(f'  the record carries {why}', f in v and v[f] not in (None, ''),
                  f'{f}={v.get(f)!r}')
        check('  and a retrieval timestamp inside provenance',
              bool((v.get('provenance') or {}).get('retrieved_at')))
        check('  the state and code are the source-state pair',
              rec['state'] == 'PASS' and rec['code'] == PC.CODE_CAPTURED,
              f'{rec["state"]}[{rec["code"]}]')
        check('  the digest is of the SERVED bytes, and says so',
              v['sha256'] == digest
              and 'before any parse' in v['sha256_is_of'],
              f'{v["sha256"][:16]} vs {digest[:16]}')
        check('  the row count is the data rows, not the lines',
              v['n_data_rows'] == 6, str(v['n_data_rows']))
        check('  the column count is the file`s',
              v['n_cols'] == PC.EXPECTED_N_COLS, str(v['n_cols']))
        check('  it records the parquet sibling it did NOT fetch',
              'parquet' in v.get('url_parquet_not_fetched', ''),
              str(v.get('url_parquet_not_fetched')))
        check('  and it does not claim any right to use epa as a feature',
              'MODEL_DERIVED' in v.get('governance_note', ''),
              str(v.get('governance_note'))[:120])


def test_B_the_archive_round_trips_by_hash():
    print('\nB. the archive holds the bytes that were served')
    body = _csv(n_rows=3)
    digest = hashlib.sha256(body).hexdigest()
    with tempfile.TemporaryDirectory() as d:
        store = pathlib.Path(d)
        a = PC.archive(body, digest, 2026, store)
        check('the archive passes', a.state is State.PASS,
              f'{a.state}[{a.code}]')
        p = pathlib.Path(a.value['blob'])
        check('  the file exists', p.exists())
        check('  and its bytes hash to the served digest',
              hashlib.sha256(p.read_bytes()).hexdigest() == digest)
        check('  BYTE-for-byte, not merely equal after a decompress',
              p.read_bytes() == body)
        # A re-archive of identical bytes is a no-op, not a rewrite.
        a2 = PC.archive(body, digest, 2026, store)
        check('  re-archiving identical bytes writes nothing and says so',
              a2.state is State.PASS and a2.code == PC.CODE_UNCHANGED
              and a2.value['wrote_bytes'] is False,
              f'{a2.state}[{a2.code}] wrote={a2.value.get("wrote_bytes")}')
        # A blob whose bytes do not match its own name is refused.
        p.write_bytes(body + b'x')
        a3 = PC.archive(body, digest, 2026, store)
        check('  a blob whose bytes contradict its name is REFUSED, not '
              'silently replaced',
              a3.state is State.FAIL and a3.code == PC.CODE_BLOB_COLLISION,
              f'{a3.state}[{a3.code}]')


def test_C_non_200_and_empty_bodies_are_refused():
    print('\nC. a status is not a capture and a 200 is not content')
    with tempfile.TemporaryDirectory() as d:
        st, mn = pathlib.Path(d) / 'v', pathlib.Path(d) / 'm.jsonl'
        for status, code, why in (
                ('500', PC.CODE_HTTP, 'a server error'),
                ('403', PC.CODE_HTTP, 'a proxy refusal'),
                ('302', PC.CODE_HTTP, 'an unfollowed redirect')):
            o = PC.capture(2026, store=st, manifest=mn,
                           opener=_opener(status=status))
            check(f'{why} ({status}) is refused by name',
                  o.state is State.FAIL and o.code == code,
                  f'{o.state}[{o.code}]')
        # 404 is NOT_APPLICABLE: the season is not published, which is neither
        # a failure nor a pass.
        o = PC.capture(2027, store=st, manifest=mn,
                       opener=_opener(status='404', body=b''))
        check('a 404 is NOT_APPLICABLE with the reason, never a silent skip',
              o.state is State.NOT_APPLICABLE
              and o.code == PC.CODE_NOT_PUBLISHED,
              f'{o.state}[{o.code}]')
        check('  and nothing was appended for it',
              not mn.exists() or not mn.read_text().strip())
        # THE REDIRECT ARTIFACT: 200 with an empty body.
        o = PC.capture(2026, store=st, manifest=mn,
                       opener=_opener(status='200', body=b''))
        check('a 200 with a ZERO-LENGTH body is refused',
              o.state is State.FAIL and o.code == PC.CODE_EMPTY,
              f'{o.state}[{o.code}]')
        check('  and the refusal names the redirect as the reason it exists',
              'redirect' in (o.detail or '').lower(), (o.detail or '')[:120])
        # An HTML error page served with status 200.
        o = PC.capture(2026, store=st, manifest=mn,
                       opener=_opener(body=b'<!DOCTYPE html><html>404</html>'))
        check('an HTML page served as 200 is refused, not archived as data',
              o.state is State.FAIL and o.code == PC.CODE_NOT_GZIP,
              f'{o.state}[{o.code}]')
        check('  and nothing reached the manifest through any of those',
              not mn.exists() or not mn.read_text().strip(),
              (mn.read_text()[:200] if mn.exists() else ''))


def test_D_the_body_is_hashed_before_it_is_parsed():
    print('\nD. the digest identifies what was served, not what we read')
    body = _csv(n_rows=5)
    seen = {}

    def spy(u):
        seen['served_sha'] = hashlib.sha256(body).hexdigest()
        return '200', body, 'HTTP/1.1 200 OK\n'

    o = PC.fetch(2026, opener=spy)
    check('fetch passes', o.state is State.PASS, f'{o.state}[{o.code}]')
    check('  and its digest is the served digest',
          o.evidence['sha256'] == seen['served_sha'])
    # A re-serialisation must NOT reproduce the digest -- if it did, this test
    # would be unable to tell the two apart and would prove nothing.
    raw = gzip.decompress(body)
    again = gzip.compress(raw)
    check('  a decompress-and-recompress does NOT reproduce it, which is why '
          'the order matters',
          hashlib.sha256(again).hexdigest() != seen['served_sha']
          or again == body,
          'recompression happened to be byte-identical, so this fixture '
          'cannot demonstrate the distinction')
    src = pathlib.Path(_ROOT, 'nfl/ingest/pbp_capture.py').read_text()
    i_hash = src.index("digest = hashlib.sha256(body).hexdigest()")
    i_parse = src.index('def inspect(')
    check('  and in the source, hashing is defined before any parser runs '
          'on the body', i_hash < i_parse, f'{i_hash} vs {i_parse}')


def test_E_schema_drift_blocks():
    print('\nE. a column set that moved is a different input')
    ok = PC.inspect(_csv())
    check('the real column set passes', ok.state is State.PASS,
          f'{ok.state}[{ok.code}] {ok.detail[:150]}')
    short = PC.inspect(_csv(drop=('filler_0',)))
    check('371 columns is refused as drift',
          short.state is State.FAIL and short.code == PC.CODE_SCHEMA_DRIFT,
          f'{short.state}[{short.code}]')
    check('  with cause DATA',
          (short.evidence.get('cause') or '') == Cause.DATA.value
          or short.evidence.get('cause') == Cause.DATA,
          str(short.evidence.get('cause')))
    gone = PC.inspect(_csv(drop=('epa', 'filler_0', 'filler_1'),
                           cols=_full_cols() + ['extra_a', 'extra_b']))
    check('a missing REQUIRED column is named in the refusal',
          gone.state is State.FAIL
          and 'epa' in (gone.evidence.get('missing_required') or []),
          f'{gone.state}[{gone.code}] {gone.evidence.get("missing_required")}')
    check('  and the refusal says it blocks rather than warns',
          'rather than warned' in (gone.detail or ''), (gone.detail or '')[:120])


def test_F_a_partial_week_file_is_a_distinct_vintage():
    print('\nF. one season has many lawful vintages')
    w1 = _csv(n_rows=4, weeks=(1,))
    w12 = _csv(n_rows=8, weeks=(1, 2))
    with tempfile.TemporaryDirectory() as d:
        st, mn = pathlib.Path(d) / 'v', pathlib.Path(d) / 'm.jsonl'
        a = PC.capture(2026, store=st, manifest=mn, opener=_opener(body=w1))
        check('the week-1-only capture passes', a.state is State.PASS,
              f'{a.state}[{a.code}]')
        check('  and is recorded as a new logical vintage',
              a.evidence['vintage']['is_new_logical_vintage'] is True)
        b = PC.capture(2026, store=st, manifest=mn, opener=_opener(body=w12))
        check('the week-1-and-2 capture ALSO passes', b.state is State.PASS,
              f'{b.state}[{b.code}]')
        check('  as a SEPARATE vintage, not an update to the first',
              b.evidence['vintage']['is_new_logical_vintage'] is True
              and b.evidence['vintage']['n_prior_with_other_bytes'] == 1,
              str(b.evidence['vintage']))
        check('  and it records that it extends the weeks previously seen',
              b.evidence['vintage']['extends_prior_weeks'] is True
              and b.evidence['vintage']['prior_weeks_seen'] == ['1'],
              str(b.evidence['vintage']))
        rows = [json.loads(x) for x in mn.read_text().strip().splitlines()]
        check('  BOTH rows survive in the manifest', len(rows) == 2,
              str(len(rows)))
        check('  with different digests and different week extents',
              rows[0]['value']['sha256'] != rows[1]['value']['sha256']
              and rows[0]['value']['weeks_present'] == ['1']
              and rows[1]['value']['weeks_present'] == ['1', '2'],
              f'{rows[0]["value"]["weeks_present"]} then '
              f'{rows[1]["value"]["weeks_present"]}')
        check('  and two blobs exist, so neither set of bytes was lost',
              len(sorted(st.glob('pbp_2026.*.csv.gz'))) == 2,
              str([p.name for p in st.glob('pbp_2026.*.csv.gz')]))


def test_G_identical_bytes_are_a_repeat_not_a_new_vintage():
    print('\nG. re-capturing the same bytes claims nothing new')
    body = _csv(n_rows=4)
    with tempfile.TemporaryDirectory() as d:
        st, mn = pathlib.Path(d) / 'v', pathlib.Path(d) / 'm.jsonl'
        PC.capture(2026, store=st, manifest=mn, opener=_opener(body=body))
        b = PC.capture(2026, store=st, manifest=mn, opener=_opener(body=body))
        check('the repeat passes', b.state is State.PASS, f'{b.state}[{b.code}]')
        check('  and is marked a repeat, not a new vintage',
              b.evidence['vintage']['is_repeat_of_existing_bytes'] is True
              and b.evidence['vintage']['is_new_logical_vintage'] is False,
              str(b.evidence['vintage']))
        check('  the row says content_unchanged',
              json.loads(mn.read_text().strip().splitlines()[-1]
                         )['value']['content_unchanged'] is True)
        check('  and only ONE blob exists, because it is content-addressed',
              len(sorted(st.glob('pbp_2026.*.csv.gz'))) == 1,
              str([p.name for p in st.glob('pbp_2026.*.csv.gz')]))


def test_H_the_module_does_not_grant_itself_epa_access():
    print('\nH. capturing a file is not permission to use its columns')
    from nfl.ingest import allowlist as AL
    o = AL.assert_columns_allowed('pbp', ['epa'], AL.Purpose.FORECAST)
    check('epa is STILL refused for Purpose.FORECAST after this module exists',
          o.state is State.FAIL and o.code == 'MODEL_DERIVED_COLUMN_ACCESS',
          f'{o.state}[{o.code}]')
    for c in ('spread_line', 'total_line'):
        x = AL.assert_columns_allowed('pbp', [c], AL.Purpose.FORECAST)
        check(f'  {c} is still refused as a market column',
              x.state is State.FAIL and x.code == 'MARKET_COLUMN_ACCESS',
              f'{x.state}[{x.code}]')
    # AN AST CHECK, NOT A SUBSTRING ONE. The first version of this check
    # searched the source text for "allowlist" and failed on the module's own
    # governance note, which says in prose that the allowlist -- not this
    # module -- decides column access. The note is the opposite of the defect
    # the check is for. What matters is that the module does not IMPORT the
    # allowlist, because a capture path that can reach the quarantine is a
    # capture path that can widen it.
    import ast
    tree = ast.parse(pathlib.Path(_ROOT, 'nfl/ingest/pbp_capture.py').read_text())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or '')
            imported.update(f'{node.module}.{a.name}' for a in node.names)
    check('  and the capture module never IMPORTS the allowlist, so it cannot '
          'widen the quarantine',
          not any('allowlist' in m for m in imported), str(sorted(imported)))


def test_I_the_provenance_timestamp_survives_a_long_header_dump():
    """A header parsed out of a truncated copy is a header that was not read.

    THE LIVE CAPTURE FOUND THIS, not this test. The first real 2026 capture
    recorded `source_timestamp: None` while the server had sent
    `Last-Modified: Thu, 17 Sep 2026 14:17:35 GMT`. The dump was truncated to
    4,000 characters for storage and then parsed from the truncated copy;
    with `-L` through a GitHub release redirect the real asset's headers come
    last, and `Last-Modified` sat at character 5,547 of 6,108.
    """
    print('\nI. the header parse reads the whole dump')
    # A dump shaped like the real one: a redirect block with an enormous
    # signed URL, then the asset block that actually describes the bytes.
    signed = 'https://release-assets.example/x?' + ('sig=%s&' % ('A' * 900))
    dump = (
        'HTTP/1.1 200 Connection Established\r\n\r\n'
        'HTTP/1.1 302 Found\r\n'
        'Content-Type: text/html; charset=utf-8\r\n'
        'Content-Length: 0\r\n'
        f'Location: {signed}\r\n'
        f'X-Padding: {"B" * 3000}\r\n\r\n'
        'HTTP/1.1 200 OK\r\n'
        'Content-Type: application/octet-stream\r\n'
        'Content-Length: 1077501\r\n'
        'Etag: "0x8DF14C66B9DB974"\r\n'
        'Last-Modified: Thu, 17 Sep 2026 14:17:35 GMT\r\n\r\n')
    i = dump.lower().find('last-modified')
    check('the fixture reproduces the real shape: Last-Modified past 4,000 '
          'characters', i > 4000, f'offset {i} of {len(dump)}')
    h = PC.parse_headers(dump)
    check('  and it is still parsed',
          h['last_modified'] == 'Thu, 17 Sep 2026 14:17:35 GMT',
          str(h['last_modified']))
    check('  parsing the TRUNCATED copy would have missed it, which is the bug',
          PC.parse_headers(dump[:4000])['last_modified'] is None,
          str(PC.parse_headers(dump[:4000])['last_modified']))
    check('  the LAST content-length wins, not the redirect`s zero',
          h['content_length'] == '1077501', str(h['content_length']))
    check('  the etag is carried too', h['etag'] == '"0x8DF14C66B9DB974"',
          str(h['etag']))
    check('  and every header block is counted, so a redirect is visible',
          h['n_header_blocks'] == 3, str(h['n_header_blocks']))
    # End to end: the manifest row must carry it.
    body = _csv(n_rows=3)
    with tempfile.TemporaryDirectory() as d:
        st, mn = pathlib.Path(d) / 'v', pathlib.Path(d) / 'm.jsonl'
        o = PC.capture(2026, store=st, manifest=mn,
                       opener=_opener(body=body, headers=dump))
        check('the capture passes on that dump', o.state is State.PASS,
              f'{o.state}[{o.code}]')
        if o.state is not State.PASS:
            NOT_EXECUTED.append('I: capture refused')
            return
        prov = json.loads(mn.read_text().strip())['value']['provenance']
        check('  and the manifest row carries the source timestamp',
              prov['source_timestamp'] == 'Thu, 17 Sep 2026 14:17:35 GMT',
              str(prov['source_timestamp']))
        check('  never None when the server supplied one',
              prov['source_timestamp'] is not None)
    src = pathlib.Path(_ROOT, 'nfl/ingest/pbp_capture.py').read_text()
    check('  and nothing parses the stored truncated copy',
          'parse_headers(' in src
          and 'headers_truncated_for_storage' in src
          and "parse_headers(ev['headers" not in src,
          'a parse still reads the truncated field')


def test_zz_every_check_passed():
    """The module's own counter, re-raised so a failure turns this module RED."""
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for fn in (test_A_a_good_capture_records_everything_required,
               test_B_the_archive_round_trips_by_hash,
               test_C_non_200_and_empty_bodies_are_refused,
               test_D_the_body_is_hashed_before_it_is_parsed,
               test_E_schema_drift_blocks,
               test_F_a_partial_week_file_is_a_distinct_vintage,
               test_G_identical_bytes_are_a_repeat_not_a_new_vintage,
               test_H_the_module_does_not_grant_itself_epa_access,
               test_I_the_provenance_timestamp_survives_a_long_header_dump):
        fn()
    for n in NOT_EXECUTED:
        print(f'  NOT_EXECUTED {n}')
    print(f'\n{PASSED} passed, {FAILED} failed, {len(NOT_EXECUTED)} NOT_EXECUTED')
    raise SystemExit(1 if FAILED else 0)
