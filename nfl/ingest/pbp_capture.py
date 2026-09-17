"""Governed capture of the nflverse season play-by-play release.

WHY THIS EXISTS. `nfl/vintage_manifest.jsonl` holds 4,492 records across 12
sources and ZERO of them are `pbp`. The only pbp-adjacent entry is
`pbp_participation`, 380 times, as `NOT_APPLICABLE /
WATCH_ONLY_SOURCE_NOT_CAPTURED_HERE`. Measured at HEAD 638af4f, so OAS1's
input has never been captured and cannot be built from anything archived.

THE ONE RULE THIS MODULE IS ORGANISED AROUND: **hash what was served, before
anything reads it.** A digest taken after a parse-and-re-serialise identifies
this machine's pandas version, not the bytes nflverse published. Every other
field here -- row count, column count, weeks present -- is computed from the
already-hashed bytes, never from a re-fetch.

WHY CSV.GZ AND NOT PARQUET. The research package names
`play_by_play_2026.parquet` as the primary source. That file is real and
reachable (200, 1,355,784 bytes), but reading it needs `pyarrow`, which is
absent here and not installable: this interpreter is an externally-managed
environment and `pip install pyarrow` exits under PEP 668. Overriding that with
`--break-system-packages` to satisfy a row count is not a trade worth making.

The same nflverse release publishes `play_by_play_2026.csv.gz`, 1,077,501
bytes, and it was verified to carry the identical frame the package measured on
the parquet: 2,756 rows, 372 columns, 2026 only, week 1 only, REG only, 16
games, 32 clubs, 32 null `epa`. Every cell of the package's B.1 table
reproduces. It is also the format every existing capture in this repository
already uses, so `content_kind` stays `csv` and nothing new has to learn how to
read a vintage.

If parquet becomes necessary -- for a column the csv export drops, say -- that
is a source change with its own capture, not a silent switch.

THE REDIRECT ARTIFACT IS REAL AND WAS OBSERVED. A GitHub release download
answers with an HTML redirect carrying `Content-Length: 0` before the real
`200 OK` with the payload length. Measured on the live fetch:

    Content-Type: text/html; charset=utf-8
    Content-Length: 0
    HTTP/1.1 200 OK
    Content-Length: 1077501

Validating on a header's content-length, or on a HEAD request, therefore sees
zero bytes for a file that is fine. This module validates on the BODY IT
RECEIVED and on nothing else, and `FINAL_STATUS_ONLY` records that decision
where a reader will meet it.
"""
from __future__ import annotations

import datetime as _dt
import gzip
import hashlib
import io
import json
import pathlib
import subprocess
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402

SPEC_VERSION = 'oas1-pbp-capture-1'
SOURCE = 'pbp'
SCHEMA_VERSION = 'nflverse-release-1'
RETENTION_POLICY = 'ruling3-raw-and-reduced-durable-1'

NFLVERSE = 'https://github.com/nflverse/nflverse-data/releases/download'
URL_TEMPLATE = NFLVERSE + '/pbp/play_by_play_{season}.csv.gz'
#: The parquet sibling, recorded so the choice above is auditable rather than
#: implicit. Not fetched: see the module docstring.
URL_TEMPLATE_PARQUET = NFLVERSE + '/pbp/play_by_play_{season}.parquet'

TIMEOUT_S = 300

#: Validation is on the received body. A header length of 0 on a GitHub
#: release redirect is an artifact of the redirect, not an empty file.
FINAL_STATUS_ONLY = True

CODE_CAPTURED = 'PBP_CAPTURED'
CODE_UNCHANGED = 'PBP_CONTENT_UNCHANGED'
CODE_NOT_PUBLISHED = 'PBP_SEASON_NOT_PUBLISHED'
CODE_HTTP = 'PBP_HTTP_STATUS'
CODE_NO_EGRESS = 'PBP_NO_EGRESS'
CODE_EMPTY = 'PBP_EMPTY_BODY'
CODE_NOT_GZIP = 'PBP_BODY_NOT_GZIP'
CODE_SCHEMA_DRIFT = 'PBP_SCHEMA_DRIFT'
CODE_ROUNDTRIP = 'PBP_ARCHIVE_ROUNDTRIP_MISMATCH'
CODE_BLOB_COLLISION = 'PBP_BLOB_BYTES_DIFFER'
CODE_VINTAGE_OVERWRITE = 'PBP_VINTAGE_OVERWRITE_REFUSED'

#: MEASURED on the 2026 release, 2026-09-17, sha256
#: b69f55a172965e16c2ac9104dc96e268dd56dc357ebdfd8ac2c68151afe9da59.
#: Asserted, not assumed: a column count that moves is upstream schema drift
#: and it BLOCKS, because the alternative is discovering it after a fit.
EXPECTED_N_COLS = 372

#: Columns OAS1 cannot be built without. Enumerated rather than pattern-matched
#: for the same reason the ingest allowlist enumerates: a pattern admits a
#: column nobody reviewed.
REQUIRED_COLUMNS = (
    'season', 'week', 'season_type', 'game_id', 'play_id', 'game_date',
    'posteam', 'defteam', 'home_team', 'play_type', 'epa', 'pass_attempt',
    'rush_attempt', 'sack', 'qb_scramble', 'qb_kneel', 'qb_spike', 'qtr',
    'ydstogo', 'game_seconds_remaining', 'score_differential', 'penalty',
)


class PbpCaptureError(ValueError):
    """Named so a caller can tell a refusal from an arithmetic failure."""


def url(season: int) -> str:
    return URL_TEMPLATE.format(season=int(season))


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


def _curl(u: str, out: pathlib.Path, hdr: pathlib.Path,
          timeout_s: int) -> tuple:
    """Returns (status, transport_evidence). The body lands in `out`."""
    cmd = ['curl', '-sS', '-L', '--max-time', str(timeout_s),
           '-D', str(hdr), '-o', str(out), '-w', '%{http_code}', u]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=timeout_s + 30)
    except subprocess.TimeoutExpired:
        return '000', {'curl_exit_code': None, 'curl_stderr': 'timeout'}
    # THE TRANSPORT'S OWN REFUSAL, KEPT. A proxy CONNECT denial is curl exit
    # 56 with http_code 000, and the gateway's real status lives only in
    # stderr. "We got nothing" and "the gateway refused with 403" are
    # different facts and only the second names who can fix it.
    return ((r.stdout or '').strip() or '000',
            {'curl_exit_code': r.returncode,
             'curl_stderr': (r.stderr or '').strip()[:400] or None})


def fetch(season: int, *, store: pathlib.Path = None, opener=None,
          timeout_s: int = TIMEOUT_S) -> Outcome:
    """Retrieve the season release and hash the body BEFORE anything reads it.

    `opener` is injectable for tests and must return
    `(status: str, body: bytes, headers: str)`. Nothing else about the
    behaviour changes when it is supplied, so a test exercises the same
    validation the live path does.
    """
    u = url(season)
    requested_at = _now()
    if opener is not None:
        status, body, headers = opener(u)
        status = str(status)
    else:
        store = pathlib.Path(store or (_REPO / 'nfl_vintage' / 'pbp'))
        store.mkdir(parents=True, exist_ok=True)
        tmp = store / f'.incoming.pbp.{season}'
        hdr = store / f'.headers.pbp.{season}'
        status, transport = _curl(u, tmp, hdr, timeout_s)
        body = tmp.read_bytes() if tmp.exists() else b''
        headers = hdr.read_text(errors='replace') if hdr.exists() else ''
        if status == '000':
            return Outcome.blocked(
                CODE_NO_EGRESS,
                f'pbp {season}: no HTTP status was returned; the request did '
                f'not complete. {transport.get("curl_stderr")}',
                cause=Cause.NETWORK, source=SOURCE, url=u,
                requested_at=requested_at, transport=transport)
    # RETRIEVED_AT IS WHEN THE BYTES ARRIVED, not when we started asking. A
    # pre-request stamp reads earlier than the server's own Date header and
    # provenance validation correctly refuses "retrieved before produced".
    retrieved_at = _now()
    # PARSED FROM THE FULL DUMP, THEN TRUNCATED FOR STORAGE -- in that order.
    # The reverse order is what lost `Last-Modified` on the first live capture.
    hdr = parse_headers(headers)
    ev = {'spec_version': SPEC_VERSION, 'source': SOURCE, 'url': u,
          'season': int(season), 'http_status': str(status),
          'requested_at': requested_at, 'retrieved_at': retrieved_at,
          'n_bytes': len(body), 'final_status_only': FINAL_STATUS_ONLY,
          'header_fields': hdr,
          'headers_truncated_for_storage': (headers or '')[:4000],
          'headers_n_chars': len(headers or '')}

    if str(status) == '404':
        # A SEASON THAT IS NOT PUBLISHED YET IS NOT A FAILURE, AND IT IS NOT A
        # PASS EITHER. NOT_APPLICABLE with the reason, never a silent skip.
        return Outcome.not_applicable(
            CODE_NOT_PUBLISHED,
            f'pbp {season}: the release returned 404. The season file is not '
            f'published. Recorded as absent rather than captured.', **ev)
    if str(status) != '200':
        return Outcome.fail(
            CODE_HTTP,
            f'pbp {season}: HTTP {status}. A capture is the bytes a 200 '
            f'returned; anything else is refused rather than archived.', **ev)
    if not body:
        return Outcome.fail(
            CODE_EMPTY,
            f'pbp {season}: HTTP 200 with a zero-length body. A 200 is not '
            f'evidence of content, and a GitHub release redirect answers 200 '
            f'with Content-Length 0 before the payload, which is exactly why '
            f'this validates on the body and not on a header.', **ev)
    if body[:2] != b'\x1f\x8b':
        return Outcome.fail(
            CODE_NOT_GZIP,
            f'pbp {season}: the body is {len(body)} byte(s) and does not '
            f'start with the gzip magic number. An HTML error page served '
            f'with status 200 looks exactly like this.',
            body_head=body[:80].decode('latin-1'), **ev)

    digest = hashlib.sha256(body).hexdigest()
    ev['sha256'] = digest
    ev['sha256_is_of'] = 'the bytes as served, before any parse'
    return Outcome.ok(CODE_CAPTURED, value={'body': body, 'sha256': digest},
                      detail=f'pbp {season}: {len(body)} bytes, sha256 '
                             f'{digest[:16]}', **ev)


def inspect(body: bytes, *, expected_n_cols: int = EXPECTED_N_COLS) -> Outcome:
    """Row count, column count and the frame's own extent, from the hashed bytes.

    Reads the decompressed CSV header directly rather than through a dataframe
    library, so the column count is the file's and not a reader's inference.
    Rows are counted by the csv module so that an embedded newline inside a
    quoted field is not miscounted as a row -- pbp free-text columns contain
    them.
    """
    import csv
    try:
        text = gzip.decompress(body).decode('utf-8')
    except Exception as e:                                    # noqa: BLE001
        return Outcome.fail(
            CODE_NOT_GZIP, f'the body did not decompress as gzip utf-8: '
                           f'{type(e).__name__}: {e}')
    rdr = csv.reader(io.StringIO(text))
    try:
        header = next(rdr)
    except StopIteration:
        return Outcome.fail(CODE_EMPTY, 'the decompressed file has no header')
    n_rows = 0
    i_season = header.index('season') if 'season' in header else None
    i_week = header.index('week') if 'week' in header else None
    i_type = header.index('season_type') if 'season_type' in header else None
    i_game = header.index('game_id') if 'game_id' in header else None
    seasons, weeks, types, games = set(), set(), set(), set()
    for row in rdr:
        if not row:
            continue
        n_rows += 1
        if i_season is not None and row[i_season]:
            seasons.add(row[i_season])
        if i_week is not None and row[i_week]:
            weeks.add(row[i_week])
        if i_type is not None and row[i_type]:
            types.add(row[i_type])
        if i_game is not None and row[i_game]:
            games.add(row[i_game])
    ev = {'spec_version': SPEC_VERSION, 'n_cols': len(header),
          'n_data_rows': n_rows, 'header': ','.join(header)[:8000],
          'seasons_present': sorted(seasons),
          'weeks_present': sorted(weeks, key=lambda w: int(float(w))),
          'season_types_present': sorted(types), 'n_games': len(games),
          'expected_n_cols': int(expected_n_cols)}
    missing = [c for c in REQUIRED_COLUMNS if c not in header]
    if missing or len(header) != int(expected_n_cols):
        return Outcome.fail(
            CODE_SCHEMA_DRIFT,
            f'pbp schema drift: {len(header)} column(s) against an expected '
            f'{expected_n_cols}' + (f', and {missing} are absent' if missing
                                    else '') + '. Blocked rather than warned: '
            f'a column set that moved between the measurement and the fit is '
            f'a different input wearing the same name.',
            cause=Cause.DATA, missing_required=missing, **ev)
    return Outcome.ok(
        'PBP_SCHEMA_OK', value=dict(ev),
        detail=f'{n_rows} row(s), {len(header)} column(s), season(s) '
               f'{sorted(seasons)}, week(s) '
               f'{sorted(weeks, key=lambda w: int(float(w)))}', **ev)


def blob_path(season: int, digest: str, store: pathlib.Path) -> pathlib.Path:
    """Content-addressed, so identical bytes never occupy two paths."""
    return pathlib.Path(store) / f'pbp_{int(season)}.{digest[:16]}.csv.gz'


def archive(body: bytes, digest: str, season: int,
            store: pathlib.Path) -> Outcome:
    """Write the served bytes VERBATIM and verify the round trip by hash.

    No decompress-and-recompress: gzip output depends on the library's
    compression level and on an mtime it stamps into the header, so a
    re-serialised archive would not reproduce the upstream digest and the
    capture could never prove it holds what was served.
    """
    store = pathlib.Path(store)
    store.mkdir(parents=True, exist_ok=True)
    p = blob_path(season, digest, store)
    if p.exists():
        have = hashlib.sha256(p.read_bytes()).hexdigest()
        if have != digest:
            # Content-addressed paths make this impossible unless the file on
            # disk is corrupt. Refused rather than overwritten: a blob whose
            # bytes do not match its own name is evidence of a problem, and
            # silently replacing it destroys the evidence.
            return Outcome.fail(
                CODE_BLOB_COLLISION,
                f'{p.name} already exists and its bytes hash to '
                f'{have[:16]}, not the {digest[:16]} its name claims. '
                f'Refused rather than overwritten.',
                path=str(p), on_disk_sha256=have, expected_sha256=digest)
        return Outcome.ok(
            CODE_UNCHANGED, value={'blob': str(p), 'sha256': digest,
                                   'wrote_bytes': False},
            detail=f'{p.name} already holds these exact bytes',
            path=str(p), sha256=digest, n_bytes=len(body))
    p.write_bytes(body)
    back = p.read_bytes()
    got = hashlib.sha256(back).hexdigest()
    if got != digest or len(back) != len(body):
        return Outcome.fail(
            CODE_ROUNDTRIP,
            f'the archived file reads back as {got[:16]} over {len(back)} '
            f'byte(s) against the served {digest[:16]} over {len(body)}. '
            f'The archive does not hold what was captured.',
            path=str(p), read_back_sha256=got, served_sha256=digest)
    return Outcome.ok(
        CODE_CAPTURED, value={'blob': str(p), 'sha256': digest,
                              'wrote_bytes': True},
        detail=f'archived {len(body)} byte(s) verbatim to {p.name}, round '
               f'trip verified by hash',
        path=str(p), sha256=digest, n_bytes=len(back),
        retention_policy=RETENTION_POLICY,
        persisted_is_upstream_verbatim=True)


def existing_captures(manifest: pathlib.Path, season: int = None) -> list:
    """Every pbp record already in the manifest, oldest first."""
    p = pathlib.Path(manifest)
    if not p.exists():
        return []
    out = []
    for ln in p.read_text().splitlines():
        if not ln.strip():
            continue
        try:
            r = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if r.get('source') != SOURCE:
            continue
        if season is not None and int(r.get('season') or -1) != int(season):
            continue
        out.append(r)
    return out


def vintage_decision(prior: list, season: int, digest: str,
                     weeks_present: list) -> Outcome:
    """Is this a new logical vintage, a repeat, or an overwrite attempt?

    THE LOGICAL VINTAGE IS `(source, season, sha256)`, NOT `(source, season)`.
    That distinction is the whole point. nflverse republishes the running
    season after each game day and again after the Monday-to-Wednesday stat
    corrections, so one season has MANY lawful vintages: a week-1-only file and
    a week-1-and-2 file are different evidence, and a Monday capture and a
    Thursday capture of the same weeks are different evidence too.

    So a second capture with different bytes is a NEW CAPTURE, appended, and
    never an update to the old row. What is refused is re-using an existing
    capture's identity for different bytes, which is the only form of
    "overwrite" that can actually destroy a record here.
    """
    same = [r for r in prior
            if ((r.get('value') or {}).get('sha256') == digest)]
    others = [r for r in prior
              if ((r.get('value') or {}).get('sha256') or '') != digest]
    prior_weeks = sorted({w for r in others
                          for w in ((r.get('value') or {}).get(
                              'weeks_present') or [])},
                         key=lambda w: int(float(w)))
    now_weeks = sorted(weeks_present, key=lambda w: int(float(w)))
    ev = {'spec_version': SPEC_VERSION, 'season': int(season),
          'sha256': digest, 'n_prior_captures': len(prior),
          'n_prior_with_same_bytes': len(same),
          'n_prior_with_other_bytes': len(others),
          'weeks_present': now_weeks, 'prior_weeks_seen': prior_weeks,
          'is_repeat_of_existing_bytes': bool(same),
          'is_new_logical_vintage': not same,
          'extends_prior_weeks': bool(others) and now_weeks != prior_weeks}
    return Outcome.ok(
        'PBP_VINTAGE_DECIDED', value=dict(ev),
        detail=('these exact bytes are already captured; recording a repeat'
                if same else
                f'new vintage: weeks {now_weeks} against previously seen '
                f'{prior_weeks or "none"}'), **ev)


def manifest_record(cap: Outcome, ins: Outcome, arc: Outcome,
                    vin: Outcome, season: int, capture_id: str) -> dict:
    """The row, in the shape every existing capture in this manifest uses."""
    v = {
        'source': SOURCE, 'url': cap.evidence['url'],
        'url_parquet_not_fetched': URL_TEMPLATE_PARQUET.format(season=season),
        'http_status': cap.evidence['http_status'],
        'sha256': cap.evidence['sha256'],
        'sha256_is_of': cap.evidence['sha256_is_of'],
        'upstream_content_sha256': cap.evidence['sha256'],
        'upstream_n_bytes': cap.evidence['n_bytes'],
        'n_bytes': cap.evidence['n_bytes'],
        'n_cols': ins.evidence['n_cols'],
        'n_data_rows': ins.evidence['n_data_rows'],
        'header': ins.evidence['header'],
        'seasons_present': ins.evidence['seasons_present'],
        'weeks_present': ins.evidence['weeks_present'],
        'season_types_present': ins.evidence['season_types_present'],
        'n_games': ins.evidence['n_games'],
        'content_kind': 'csv', 'blob_encoding': 'gzip',
        'durability': 'commit_raw',
        'retention_policy': RETENTION_POLICY,
        'persisted_is_upstream_verbatim': True,
        'blob': arc.value['blob'],
        'blob_wrote_bytes': arc.value['wrote_bytes'],
        'raw_blob': arc.value['blob'],
        'raw_blob_content_sha256': cap.evidence['sha256'],
        'vintage': vin.value,
        'content_unchanged': bool(vin.value['is_repeat_of_existing_bytes']),
        'final_status_only': FINAL_STATUS_ONLY,
        'provenance': {
            'schema_version': SCHEMA_VERSION,
            'source': f'nflverse:{SOURCE}',
            'url': cap.evidence['url'],
            'requested_at': cap.evidence['requested_at'],
            'retrieved_at': cap.evidence['retrieved_at'],
            'effective_for_date': str(season),
            'source_timestamp': (cap.evidence.get('header_fields')
                                 or {}).get('last_modified'),
            'source_timestamp_header': 'Last-Modified',
            'etag': (cap.evidence.get('header_fields') or {}).get('etag'),
            'n_header_blocks': (cap.evidence.get('header_fields')
                                or {}).get('n_header_blocks'),
        },
        # THE TARGET IS GOVERNED SEPARATELY AND THIS SAYS SO. Capturing the
        # file does not grant any reader the right to use `epa` as a forecast
        # input; that is `nfl/ingest/allowlist.py`'s decision and OAS1's
        # target-only exemption, not this module's.
        'governance_note': (
            'capture only. `epa` remains MODEL_DERIVED and refused for '
            'Purpose.FORECAST except on the OAS1 target-only path; no '
            'market column may be read from this file at all.'),
    }
    return {'capture_id': capture_id, 'source': SOURCE, 'season': int(season),
            'state': State.PASS.value, 'code': CODE_CAPTURED,
            'detail': cap.detail, 'evidence': {'source': SOURCE},
            'value': v}


#: Header fields lifted out of the dump and carried as their own keys.
HEADER_FIELDS = ('last-modified', 'etag', 'content-type', 'content-length')


def parse_headers(headers: str) -> dict:
    """The header fields this capture needs, taken from the WHOLE dump.

    THIS WAS A SILENT PROVENANCE LOSS AND A LIVE CAPTURE PROVED IT. The first
    2026 capture recorded `source_timestamp: None` while the server had in
    fact sent `Last-Modified: Thu, 17 Sep 2026 14:17:35 GMT`. The header dump
    was being truncated to 4,000 characters for the evidence block, and the
    parse then ran on the truncated copy -- `Last-Modified` sits at character
    5,547 of a 6,108-character dump, because a GitHub release redirect carries
    a signed URL about a thousand characters long and there are several header
    blocks before the real one.

    The lesson is the project's own recurring one: a step returned something
    partial and the next step read it as the whole thing. Parsing happens here,
    on the full text, and the truncated copy is kept only as context that
    nothing parses.

    THE LAST OCCURRENCE WINS, deliberately. With `-L` the dump holds the
    redirect's headers first and the actual asset's last, and it is the asset's
    timestamp that describes the bytes.
    """
    out = {k.replace('-', '_'): None for k in HEADER_FIELDS}
    statuses = []
    for ln in (headers or '').splitlines():
        low = ln.lower()
        if low.startswith('http/'):
            statuses.append(ln.strip())
            continue
        for k in HEADER_FIELDS:
            if low.startswith(k + ':'):
                out[k.replace('-', '_')] = ln.split(':', 1)[1].strip()
    out['status_lines'] = statuses
    out['n_header_blocks'] = len(statuses)
    out['n_header_chars'] = len(headers or '')
    return out


def _last_modified(headers: str) -> str | None:
    return parse_headers(headers).get('last_modified')


def capture(season: int, *, store: pathlib.Path = None,
            manifest: pathlib.Path = None, opener=None,
            append: bool = True) -> Outcome:
    """Fetch, validate, archive, decide the vintage, and append one row.

    ROWS BEFORE BYTES IS DELIBERATELY NOT THE ORDER HERE. `capture_vintage`
    stages rows first because its blobs are reductions that can be rebuilt.
    This archive IS the evidence, so the bytes are written and hash-verified
    before any row claims they exist. A manifest row pointing at a blob that
    was never written is the failure this ordering removes.
    """
    store = pathlib.Path(store or (_REPO / 'nfl' / 'vintage'))
    manifest = pathlib.Path(manifest or (_REPO / 'nfl' / 'vintage_manifest.jsonl'))
    cap = fetch(season, opener=opener)
    if cap.state is not State.PASS:
        return cap
    body, digest = cap.value['body'], cap.value['sha256']
    ins = inspect(body)
    if ins.state is not State.PASS:
        return ins
    arc = archive(body, digest, season, store)
    if arc.state is not State.PASS:
        return arc
    prior = existing_captures(manifest, season)
    vin = vintage_decision(prior, season, digest,
                           ins.evidence['weeks_present'])
    # THE CAPTURE IDENTITY CARRIES THE CONTENT DIGEST, AND A TEST FORCED THAT.
    #
    # This was a bare `%Y%m%dT%H%M%SZ` timestamp, matching the existing
    # captures. Two captures of DIFFERENT bytes inside the same second then
    # collided, and the second -- a genuinely new vintage -- was refused as an
    # overwrite. The partial-week test hit it immediately, which is exactly
    # the case that matters: nflverse republishes the running season several
    # times a day.
    #
    # Sub-second resolution plus the digest makes two distinct captures
    # distinctly named by construction rather than by luck of the clock.
    capture_id = (_dt.datetime.now(_dt.timezone.utc)
                  .strftime('%Y%m%dT%H%M%S.%fZ') + f'.{digest[:16]}')
    # AND THE GUARD NOW CHECKS WHAT IT ACTUALLY PROTECTS. Re-using an existing
    # capture identity for DIFFERENT bytes is the only form of overwrite that
    # can destroy a record. The same identity with the same bytes is the same
    # capture, and refusing that would refuse an idempotent re-run.
    clash = [r for r in prior
             if r.get('capture_id') == capture_id
             and (r.get('value') or {}).get('sha256') != digest]
    if clash:
        return Outcome.fail(
            CODE_VINTAGE_OVERWRITE,
            f'capture_id {capture_id} already exists for pbp {season} with '
            f'different bytes. A capture identity may never be re-used for '
            f'content it does not describe.',
            capture_id=capture_id,
            existing_sha256=(clash[0].get('value') or {}).get('sha256'),
            this_sha256=digest)
    rec = manifest_record(cap, ins, arc, vin, season, capture_id)
    if append:
        with open(manifest, 'a', encoding='utf-8') as fh:
            fh.write(json.dumps(rec, sort_keys=True) + '\n')
    return Outcome.ok(
        CODE_CAPTURED, value={'record': rec, 'sha256': digest,
                              'blob': arc.value['blob'],
                              'n_data_rows': ins.evidence['n_data_rows'],
                              'n_cols': ins.evidence['n_cols'],
                              'weeks_present': ins.evidence['weeks_present'],
                              'appended': bool(append)},
        detail=f'pbp {season}: {ins.evidence["n_data_rows"]} rows, '
               f'{ins.evidence["n_cols"]} cols, sha256 {digest[:16]}, '
               f'{"appended" if append else "not appended"}',
        spec_version=SPEC_VERSION, capture_id=capture_id, sha256=digest,
        vintage=vin.value)


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--season', type=int, required=True)
    ap.add_argument('--dry-run', action='store_true',
                    help='fetch, validate and archive, but append no row')
    a = ap.parse_args()
    o = capture(a.season, append=not a.dry_run)
    print(f'{o.state.value}[{o.code}] {o.detail}')
    raise SystemExit(0 if o.state in (State.PASS, State.NOT_APPLICABLE) else 1)
