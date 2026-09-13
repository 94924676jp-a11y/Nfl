"""Ingest externally DELIVERED authoritative injury/game-status evidence.

WHY THIS MODULE EXISTS, MEASURED 2026-09-13

The governed inactive path already accepts delivered bytes: `ingest_inactives.py`
takes `--bytes` and an `EXTERNAL_AUTHORITATIVE_DELIVERY` provenance block. The
injury path did not. `capture_vintage.py` fetches over the network itself, has
no offline mode, and the token `delivered_by` appeared nowhere outside the
inactives tool. So on the first real production Sunday an executor with no
egress held a complete, hash-verified official evidence package and had no
lawful way to put it into production, while every one of the day's 24 teams sat
on INJURY_REPORT_INCOMPLETE from a capture two days stale.

That is an INGESTION AND INTERFACE defect, not a model defect, and this module
is the narrowest repair for it.

WHAT IT DOES NOT DO

It does not define a second predictive-data standard. Delivered evidence is
written into the SAME `injuries` vintage schema, at the SAME content-addressed
path convention, with a manifest row the SAME selector reads, so everything
downstream -- `readiness._all_injury_captures`, `team_report_history`,
`appearance_model.parse_injuries_rows` -- consumes it without knowing or caring
that it arrived by hand. The one thing that differs is provenance, and that
difference is recorded loudly rather than smoothed away: `acquisition` says
EXTERNAL_AUTHORITATIVE_DELIVERY, never NATIVE_NETWORK_CAPTURE.

It does not interpret. Every refusal below is a refusal to guess:

  * a status outside the governed vocabulary is REFUSED, not corrected. The
    package carries a literal `QUESTIONBLE` typo from nfl.com. A parser that
    reads that as `Questionable` is a parser that will one day read something
    worse as something convenient.
  * a name that does not resolve to exactly one rostered gsis_id is REFUSED,
    not dropped. `appearance_model.parse_injuries_rows` skips any row without a
    gsis_id, so a dropped row would leave readiness reporting a filed report
    that the model never actually reads.
  * an explicit team-level "no injury designations" statement is stored as its
    OWN record kind and is NEVER turned into injury rows, and never into an
    absence of rows that some later reader could mistake for one. It does not
    clear a readiness gate here. See EXPLICIT_NO_DESIGNATIONS below.
  * a game-day inactive flag is REFUSED outright. Game status and game-day
    inactive are different facts with different clocks and different consumers,
    and this path carries only the first.
"""
from __future__ import annotations

import csv
import datetime as dt
import gzip
import hashlib
import io
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import (Cause, Outcome,  # noqa: E402
                                               State)
from nfl.production.nonqb import inactives as INA              # noqa: E402

SPEC_VERSION = 'delivered_injuries/1.0.0'
ACQUISITION = 'EXTERNAL_AUTHORITATIVE_DELIVERY'
NATIVE_ACQUISITION = 'NATIVE_NETWORK_CAPTURE'

VINTAGE = _REPO / 'nfl' / 'vintage'
MANIFEST = _REPO / 'nfl' / 'vintage_manifest.jsonl'

# The nflverse injuries schema, in order. Delivered rows are written into THIS
# and nothing else, because this is what the whole downstream already reads.
INJURY_COLUMNS = ('season', 'season_type', 'game_type', 'team', 'week',
                  'gsis_id', 'position', 'full_name', 'first_name',
                  'last_name', 'report_primary_injury', 'report_status',
                  'practice_primary_injury', 'practice_secondary_injury',
                  'practice_status')

# The league's three game-status designations, spelled as the feed spells them.
# Exact membership, never a prefix or a case-folded contains: the whole point
# is that QUESTIONBLE is not in this tuple.
REPORT_STATUS_VOCAB = ('Out', 'Doubtful', 'Questionable')

# What a row must say about itself before it is allowed to become data.
REQUIRED_EVIDENCE_CLASS = 'OFFICIAL_SOURCE_OBSERVATION'
REQUIRED_CONCLUSION_CLASS = 'PROVEN'
REQUIRED_STATUS_SEMANTICS = 'EXPLICIT_DESIGNATION'

# An explicit team-level statement that a club filed no designations. It is a
# DIFFERENT FACT from "no rows arrived", and it is stored so the difference is
# on the record. It is deliberately NOT written as injury rows and NOT given
# any power to satisfy the appearance contract here -- doing that is a
# governance change, not an ingestion repair, and is out of this module's scope.
EXPLICIT_NO_DESIGNATIONS = 'EXPLICIT_TEAM_NO_INJURY_DESIGNATIONS'

# SOURCE CLUB CODES ARE NOT OUR CLUB CODES.
#
# nfl.com writes the Cardinals as `AZ`; every governed artifact in this
# repository -- schedules, rosters, depth charts, game ids -- writes `ARI`.
# This is a spelling table for codes actually observed in delivered evidence,
# verified against the roster vintage's own team set at ingest time. An
# unmapped code that is not itself a roster team is REFUSED, never passed
# through and never guessed at.
SOURCE_TEAM_CODES = {'AZ': 'ARI'}

# Roster columns this module is permitted to read. `status` is NOT among them:
# `weekly_rosters.status == INA` is postgame roster state, and reading it here
# would put a game outcome into a pregame path.
ROSTER_IDENTITY_COLUMNS = ('season', 'week', 'team', 'gsis_id', 'full_name',
                           'football_name', 'first_name', 'last_name',
                           'position')
ROSTER_FORBIDDEN_COLUMNS = ('status', 'game_type_status', 'status_description_abbr')


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _sha256_file(p) -> str:
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _parse_ts(t):
    if not t:
        return None
    try:
        d = dt.datetime.fromisoformat(str(t).replace('Z', '+00:00'))
    except (TypeError, ValueError):
        return None
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)


# ---------------------------------------------------------------------------
# 1. the package, verified before anything is read out of it
# ---------------------------------------------------------------------------

def verify_package(root) -> Outcome:
    """Every delivered byte hashes to what the delivery says it hashes to.

    Two independent statements are checked, not one: the per-source `manifest.json`
    (which carries the retrieval clocks and the source URLs) and the flat
    `checksums.json` (which covers every file in the package including the
    derived jsonl). A package that passes one and fails the other is refused.
    """
    root = pathlib.Path(root)
    man_p, ck_p = root / 'manifest.json', root / 'checksums.json'
    for p in (man_p, ck_p):
        if not p.exists():
            return Outcome.blocked(
                'DELIVERED_PACKAGE_INCOMPLETE',
                f'{p.name} is absent, so the delivery cannot state its own '
                f'content identity and nothing in it may be trusted.',
                path=str(p), cause=Cause.DATA)
    manifest = json.loads(man_p.read_text())
    checksums = json.loads(ck_p.read_text())

    mismatched, missing = [], []
    n_raw = 0
    for e in manifest:
        rp = e.get('raw_path')
        if not rp:
            continue                      # a failed fetch; it carries `error`
        p = root / rp
        if not p.exists():
            missing.append(rp)
            continue
        n_raw += 1
        if _sha256_file(p) != e.get('sha256'):
            mismatched.append(rp)
        elif p.stat().st_size != e.get('byte_size'):
            mismatched.append(rp + ':byte_size')

    n_ck = 0
    for name, dig in checksums.items():
        p = root / name
        if not p.exists():
            missing.append(name)
            continue
        n_ck += 1
        if _sha256_file(p) != dig:
            mismatched.append(name)

    if mismatched or missing:
        return Outcome.fail(
            'DELIVERED_PACKAGE_HASH_MISMATCH',
            f'{len(mismatched)} file(s) do not hash to their declared digest '
            f'and {len(missing)} declared file(s) are absent. A delivery whose '
            f'bytes do not match its own manifest is not authoritative '
            f'evidence, whatever it claims to be.',
            mismatched=sorted(mismatched)[:20], missing=sorted(missing)[:20],
            n_mismatched=len(mismatched), n_missing=len(missing))

    return Outcome.ok(
        'DELIVERED_PACKAGE_VERIFIED',
        value={'manifest': manifest, 'checksums': checksums, 'root': str(root)},
        spec_version=SPEC_VERSION, n_manifest_entries=len(manifest),
        n_raw_verified=n_raw, n_checksums_verified=n_ck,
        n_fetch_errors=sum(1 for e in manifest if e.get('error')))


# ---------------------------------------------------------------------------
# 2. raw bytes preserved before parse, content-addressed, append-only
# ---------------------------------------------------------------------------

def store_raw(raw: bytes, *, source_id: str, vintage_root=None) -> Outcome:
    """Write delivered raw bytes to a content-addressed blob, or find it there.

    APPEND-ONLY AND NEVER RESTAMPED. The path is a function of the bytes, so
    delivering the same document twice resolves to the same blob. The second
    delivery is a MEASUREMENT -- it gets its own manifest row and changes no
    byte and no clock of the first. That is the same rule `capture_vintage.py`
    states for an unchanged native fetch, and it is kept identical on purpose.
    """
    root = pathlib.Path(vintage_root) if vintage_root else VINTAGE
    root.mkdir(parents=True, exist_ok=True)
    sha = _sha256_bytes(raw)
    blob = root / f'delivered_injury_evidence.{sha[:16]}.html.gz'
    existed = blob.exists()
    if not existed:
        tmp = blob.with_suffix(blob.suffix + '.tmp')
        with gzip.GzipFile(tmp, 'wb', mtime=0) as f:
            f.write(raw)
        tmp.replace(blob)
    stored = gzip.open(blob, 'rb').read()
    if _sha256_bytes(stored) != sha:
        return Outcome.fail(
            'DELIVERED_RAW_ROUNDTRIP_FAILED',
            'the bytes read back out of the blob do not hash to the bytes '
            'that went in', sha256=sha, blob=str(blob))
    return Outcome.ok('DELIVERED_RAW_STORED', value=str(blob),
                      sha256=sha, n_bytes=len(raw), source_id=source_id,
                      blob_already_present=existed,
                      deduplicated=existed, spec_version=SPEC_VERSION)


# ---------------------------------------------------------------------------
# 3. identity, through the governed crosswalk and nothing else
# ---------------------------------------------------------------------------

def roster_index(roster_csv, season: int, week: int) -> Outcome:
    """{gsis_id: {name, team, position}} from a raw roster vintage.

    Only ROSTER_IDENTITY_COLUMNS are read. The refusal below is structural: if
    a forbidden column is ever consumed by this function the guard fires before
    a row is built, because postgame roster state has no business in a pregame
    identity join.
    """
    p = pathlib.Path(roster_csv)
    if not p.exists():
        return Outcome.blocked(
            'ROSTER_VINTAGE_ABSENT',
            f'{p} does not exist, so no delivered name can be resolved to a '
            f'gsis_id. Refusing rather than guessing.', path=str(p),
            cause=Cause.DATA)
    out = {}
    with open(p, newline='') as f:
        rd = csv.DictReader(f)
        for r in rd:
            if r.get('season') != str(season) or r.get('week') != str(week):
                continue
            pid = r.get('gsis_id')
            if not pid:
                continue
            nm = (r.get('full_name') or r.get('football_name') or '').strip()
            if not nm:
                continue
            out[pid] = {'name': nm, 'team': r.get('team'),
                        'position': r.get('position')}
    if not out:
        return Outcome.blocked(
            'ROSTER_VINTAGE_EMPTY_FOR_WEEK',
            f'no {season} week {week} rows with a name in {p.name}',
            path=str(p), cause=Cause.DATA)
    return Outcome.ok('ROSTER_INDEX_BUILT', value=out, n_players=len(out),
                      n_teams=len({v['team'] for v in out.values()}),
                      columns_read=list(ROSTER_IDENTITY_COLUMNS),
                      columns_refused=list(ROSTER_FORBIDDEN_COLUMNS))


def map_team(code: str, roster_teams) -> str | None:
    """A delivered club code in OUR spelling, or None to refuse it."""
    c = (code or '').strip().upper()
    if c in roster_teams:
        return c
    return SOURCE_TEAM_CODES.get(c) if SOURCE_TEAM_CODES.get(c) in roster_teams else None


# ---------------------------------------------------------------------------
# 4. candidates -> injuries rows, with every refusal named
# ---------------------------------------------------------------------------

def rows_from_candidates(candidates, roster, season: int, week: int,
                         season_type: str = 'REG') -> Outcome:
    """Delivered status candidates -> rows in the nflverse injuries schema.

    Refuses the whole set if ANY row cannot be represented honestly. Partial
    ingestion of an evidence set is how a team ends up looking reported when
    half of its report was silently discarded.
    """
    roster_teams = {v['team'] for v in roster.values()}
    refusals, names_by_team, keep = [], {}, []

    for i, c in enumerate(candidates):
        where = f'row {i} ({c.get("team")} {c.get("player")})'
        if c.get('game_day_inactive') is not None:
            refusals.append({'row': where, 'code': 'GAME_STATUS_IS_NOT_INACTIVE_STATUS',
                             'detail': 'this row carries a game_day_inactive '
                                       'flag. Game status and game-day '
                                       'inactive are different facts; this '
                                       'path carries only the first, and the '
                                       'inactive path is ingest_inactives.py.'})
            continue
        if c.get('evidence_class') != REQUIRED_EVIDENCE_CLASS:
            refusals.append({'row': where, 'code': 'EVIDENCE_CLASS_NOT_OFFICIAL',
                             'detail': str(c.get('evidence_class'))})
            continue
        if c.get('conclusion_class') != REQUIRED_CONCLUSION_CLASS:
            refusals.append({'row': where, 'code': 'CONCLUSION_NOT_PROVEN',
                             'detail': str(c.get('conclusion_class'))})
            continue
        if c.get('status_semantics') != REQUIRED_STATUS_SEMANTICS:
            refusals.append({'row': where, 'code': 'STATUS_SEMANTICS_NOT_EXPLICIT',
                             'detail': f'{c.get("status_semantics")}. A row '
                                       f'that says it needs normalisation is '
                                       f'not normalised here.'})
            continue
        st = c.get('report_status')
        if st not in REPORT_STATUS_VOCAB:
            refusals.append({'row': where,
                             'code': 'STATUS_NOT_IN_GOVERNED_VOCABULARY',
                             'detail': f'{st!r} (raw {c.get("report_status_raw")!r}) '
                                       f'is not one of {REPORT_STATUS_VOCAB}. '
                                       f'It is refused, never corrected.'})
            continue
        team = map_team(c.get('team'), roster_teams)
        if team is None:
            refusals.append({'row': where, 'code': 'TEAM_CODE_UNMAPPED',
                             'detail': f'{c.get("team")!r} is neither a roster '
                                       f'club code nor a declared source '
                                       f'spelling'})
            continue
        keep.append((c, team, st))
        names_by_team.setdefault(team, []).append(c['player'])

    if not keep:
        return Outcome.blocked(
            'DELIVERED_NO_ADMISSIBLE_ROWS',
            f'none of {len(candidates)} delivered candidate(s) survived the '
            f'admissibility checks', refusals=refusals[:20],
            n_refused=len(refusals), cause=Cause.GOVERNANCE)

    # Identity through the governed resolver: exact match, else generational
    # suffix, else nothing. No edit distance, no nicknames, no initials.
    res = INA.resolve(names_by_team, roster)
    if res.state is not State.PASS:
        return Outcome.fail('DELIVERED_IDENTITY_AMBIGUOUS', res.detail,
                            **dict(res.evidence))
    unmapped = list(res.evidence.get('unmapped') or [])
    if unmapped:
        return Outcome.blocked(
            'DELIVERED_IDENTITY_UNRESOLVED',
            f'{len(unmapped)} delivered name(s) resolve to no rostered player. '
            f'A row without a gsis_id is skipped by '
            f'appearance_model.parse_injuries_rows, so admitting it would let '
            f'readiness report a filed designation the model never reads. '
            f'Refused as a set rather than written in part.',
            unmapped=unmapped, n_unmapped=len(unmapped),
            n_admissible=len(keep), refusals=refusals[:20],
            n_refused=len(refusals), cause=Cause.DATA)

    by_team_ids = res.value
    cursor = {t: 0 for t in by_team_ids}
    rows = []
    for c, team, st in keep:
        pid = by_team_ids[team][cursor[team]]
        cursor[team] += 1
        nm = roster[pid]['name']
        first, _, last = nm.partition(' ')
        rows.append({
            'season': str(season), 'season_type': season_type,
            'game_type': season_type, 'team': team, 'week': str(week),
            'gsis_id': pid, 'position': roster[pid].get('position') or '',
            'full_name': nm, 'first_name': first, 'last_name': last,
            'report_primary_injury': (c.get('injury') or ''),
            'report_status': st,
            # THE PACKAGE CARRIES NO PRACTICE PARTICIPATION FOR THESE ROWS.
            # Empty means unfiled and is left empty. It is never backfilled
            # from the designation, which would invent a practice observation
            # out of a game-status one.
            'practice_primary_injury': '',
            'practice_secondary_injury': '',
            'practice_status': '',
        })
    return Outcome.ok(
        'DELIVERED_ROWS_BUILT', value=rows, n_rows=len(rows),
        n_teams=len({r['team'] for r in rows}),
        teams=sorted({r['team'] for r in rows}),
        n_refused=len(refusals), refusals=refusals[:20],
        n_matched_by_suffix_normalisation=res.evidence.get(
            'n_matched_by_suffix_normalisation'),
        matched_by_suffix_normalisation=res.evidence.get(
            'matched_by_suffix_normalisation'),
        spec_version=SPEC_VERSION)


def to_csv_bytes(rows) -> bytes:
    buf = io.StringIO(newline='')
    w = csv.DictWriter(buf, fieldnames=list(INJURY_COLUMNS),
                       lineterminator='\n')
    w.writeheader()
    for r in sorted(rows, key=lambda r: (r['team'], r['gsis_id'])):
        w.writerow({k: r.get(k, '') for k in INJURY_COLUMNS})
    return buf.getvalue().encode()


# ---------------------------------------------------------------------------
# 5. explicit no-designation statements: stored, not converted
# ---------------------------------------------------------------------------

def no_designation_records(statements, roster_teams) -> Outcome:
    """Team-level "no injury designations" statements, kept as their own kind.

    THE DISTINCTION THIS PRESERVES, AND WHY IT IS NOT A GATE CHANGE.

    Three team states are genuinely different and the injuries feed can only
    spell two of them:

      (a) rows filed, designations present        -> the feed says so
      (b) rows filed, no designation yet filed    -> the feed says so
      (c) the club has explicitly stated it has NO designations

    (c) is real evidence and (b) is an absence of evidence, and the current
    appearance contract has no field, value or state that distinguishes them.
    This function therefore records (c) verbatim, with its clocks and its
    source hash, and does exactly nothing else with it. It does not write
    injury rows. It does not create an empty team block. It cannot clear
    INJURY_REPORT_INCOMPLETE, because teaching the gate to accept a new class
    of evidence is a governance decision and this module is an ingestion
    repair. What it buys today is that the evidence is ON THE RECORD, in the
    vintage, hashed and clocked, instead of being thrown away for want of a
    field to put it in.
    """
    out, refused = [], []
    for s in statements:
        if s.get('status_semantics') != EXPLICIT_NO_DESIGNATIONS:
            refused.append({'team': s.get('team'),
                            'code': 'NOT_AN_EXPLICIT_NO_DESIGNATION_STATEMENT',
                            'detail': str(s.get('status_semantics'))})
            continue
        team = map_team(s.get('team'), roster_teams)
        if team is None:
            refused.append({'team': s.get('team'), 'code': 'TEAM_CODE_UNMAPPED',
                            'detail': 'not a roster club code or declared '
                                      'source spelling'})
            continue
        out.append({
            'team': team, 'source_team_code': s.get('team'),
            'kind': EXPLICIT_NO_DESIGNATIONS,
            'game_date': s.get('game_date'),
            'report_period': s.get('report_period'),
            'evidence_text': s.get('evidence_text'),
            'source_id': s.get('source_id'), 'source_url': s.get('source_url'),
            'content_sha256': s.get('content_sha256'),
            'retrieved_at': s.get('retrieved_at'),
            'publication_time': s.get('publication_time'),
            'source_modified_time': s.get('source_modified_time'),
            'effective_time': s.get('effective_time'),
            'locator': s.get('locator'),
            'clears_a_readiness_gate': False,
            'why_not': ('the appearance contract has no representation for an '
                        'explicit no-designation state. Recorded as evidence; '
                        'changing what the gate accepts is a governance '
                        'decision, not an ingestion repair.'),
        })
    return Outcome.ok('NO_DESIGNATION_STATEMENTS_RECORDED', value=out,
                      n_statements=len(out), teams=sorted(r['team'] for r in out),
                      n_refused=len(refused), refused=refused[:20],
                      spec_version=SPEC_VERSION)


# ---------------------------------------------------------------------------
# 6. quarantine: evidence that exists and must not become data
# ---------------------------------------------------------------------------

def quarantine_records(observations, candidates, reconciliation) -> Outcome:
    """Observations the delivery declined to promote, kept with their reason.

    An observation that is in the evidence set but not in the candidate set is
    quarantined, never discarded and never resolved by this module. The two
    live cases today are a temporally unaligned pair of official statements
    (article says one designation, league table says another, with no revision
    period established to order them) and a literal source typo. Picking a
    winner for either would be manufacturing a fact.
    """
    ck = {(c.get('team'), c.get('player'), c.get('source_id'))
          for c in candidates}
    disc = {}
    for d in (reconciliation.get('new_status_discrepancies') or []):
        disc[(d.get('team'), d.get('player'))] = d
    out = []
    for o in observations:
        key = (o.get('team'), o.get('player'), o.get('source_id'))
        if key in ck:
            continue
        d = disc.get((o.get('team'), o.get('player')))
        if d is not None:
            reason, code = d.get('reason'), d.get('classification')
        elif o.get('status_semantics') != REQUIRED_STATUS_SEMANTICS:
            code = 'SOURCE_TYPO_NOT_NORMALISED'
            reason = (f'raw status {o.get("report_status_raw")!r} is not in '
                      f'{REPORT_STATUS_VOCAB}. Refused, never corrected.')
        else:
            code = 'NOT_PROMOTED_BY_DELIVERY'
            reason = 'present in the evidence set, absent from the candidates'
        out.append({'team': o.get('team'), 'player': o.get('player'),
                    'source_id': o.get('source_id'),
                    'report_status': o.get('report_status'),
                    'report_status_raw': o.get('report_status_raw'),
                    'game_date': o.get('game_date'),
                    'classification': code, 'reason': reason,
                    'resolved_by_this_module': False})
    return Outcome.ok('QUARANTINE_RECORDED', value=out, n_quarantined=len(out),
                      teams=sorted({r['team'] for r in out}),
                      spec_version=SPEC_VERSION)


# ---------------------------------------------------------------------------
# 7. the manifest row the existing selector reads
# ---------------------------------------------------------------------------

def _capture_id(ts: str) -> str:
    d = _parse_ts(ts) or dt.datetime.now(dt.timezone.utc)
    return d.astimezone(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')


def manifest_row(*, csv_bytes: bytes, blob_rel: str, rows, primary,
                 season: int, delivered_by: str, package_sha256: str,
                 raw_blobs, no_designations, quarantined,
                 generated_at: str) -> dict:
    """A `source: injuries` PASS row, shaped exactly like a native capture.

    EVERY CLOCK IS A DIFFERENT FIELD AND NONE IS DERIVED FROM ANOTHER.

      requested_at            when the delivering agent asked the source
      retrieved_at            when the delivering agent had the bytes
      publication_time        when the source says it published
      source_timestamp        when the source says it last modified
      effective_for_date      the date the evidence is about
      generated_at            when THIS ingestion ran
      cache_timestamp         null, always: nothing here is a cache read and
                              nothing here is restamped

    `retrieved_at` is the delivering agent's real clock, carried through
    unchanged. It is NOT set to ingestion time -- doing that would make
    two-day-old evidence look fresh to the chronology gate, which is the exact
    failure this whole path exists to avoid.
    """
    sha = _sha256_bytes(csv_bytes)
    return {
        'capture_id': _capture_id(primary['retrieved_at']),
        'code': 'CAPTURED_BY_DELIVERY',
        'detail': (f'injuries: {len(csv_bytes)} bytes, {len(rows)} data rows '
                   f'from {ACQUISITION} ({primary["source_id"]})'),
        'evidence': {'source': 'injuries', 'acquisition': ACQUISITION},
        'season': season,
        'source': 'injuries',
        'state': 'PASS',
        'value': {
            'blob': blob_rel,
            'blob_durable': True,
            'blob_encoding': 'gzip',
            'content_kind': 'csv',
            'content_unchanged': False,
            'acquisition': ACQUISITION,
            'spec_version': SPEC_VERSION,
            'header': ','.join(INJURY_COLUMNS),
            'n_bytes': len(csv_bytes),
            'n_cols': len(INJURY_COLUMNS),
            'n_data_rows': len(rows),
            'n_lines': len(rows) + 1,
            'http_status': str(primary.get('http_status') or ''),
            'requested_at': primary.get('retrieval_start'),
            'retrieved_at': primary['retrieved_at'],
            'sha256': sha,
            'sha256_is_of': 'uncompressed_bytes',
            'source': 'injuries',
            'source_timestamp_header': 'delivered:source_modified_time',
            'url': primary.get('source_url'),
            'reduced': None,
            'durability': 'commit_raw',
            'provenance': {
                'source': f'delivered:{primary["source_id"]}',
                'acquisition': ACQUISITION,
                'url': primary.get('source_url'),
                'requested_at': primary.get('retrieval_start'),
                'retrieved_at': primary['retrieved_at'],
                'publication_time': primary.get('publication_time'),
                'source_timestamp': primary.get('source_modified_time'),
                'effective_time': primary.get('effective_time'),
                'effective_for_date': primary.get('game_date'),
                'generated_at': generated_at,
                'cache_timestamp': None,
                'cache_timestamp_note': ('null by construction. A delivered '
                                         'artifact is never restamped with '
                                         'the ingestion clock.'),
                'schema_version': 'nflverse-release-1',
                'schema_note': ('the nflverse injuries schema, unchanged, so '
                                'the downstream selector and parser consume '
                                'this exactly as they consume a native '
                                'capture'),
            },
            'delivery': {
                'kind': ACQUISITION,
                'not': NATIVE_ACQUISITION,
                'delivered_by': delivered_by,
                'delivered_package_sha256': package_sha256,
                'primary_source_id': primary['source_id'],
                'primary_source_url': primary.get('source_url'),
                'primary_content_sha256': primary.get('content_sha256'),
                'raw_evidence_blobs': list(raw_blobs),
                'what_this_is': (
                    'Official league game-status evidence retrieved by a '
                    'networked agent, delivered as bytes with its own '
                    'manifest and checksums, verified here against both '
                    'before a single row was parsed out of it.'),
                'what_this_is_not': (
                    'NOT a network capture performed by this executor, and '
                    'NOT a game-day inactive list. The chain of custody runs '
                    'official source -> delivering agent -> this artifact, '
                    'and every clock above is the delivering agent\'s, not '
                    'this run\'s.'),
            },
            'effective_scope': {
                'authority': 'DELIVERED_EXPLICIT',
                'scope': 'SEASON_WEEK_TEAMS',
                'teams': sorted({r['team'] for r in rows}),
                'derivation': {
                    'evidence': ('every row carries its own season, week and '
                                 'team from the delivered evidence; the '
                                 'boundary is not inferred from a file clock'),
                },
            },
            'explicit_no_designations': no_designations,
            'quarantined_evidence': quarantined,
            'substantive': {
                'authority': 'DERIVED_DETERMINISTIC',
                'digest': sha, 'raw_sha256': sha,
                'digest_version': 'substantive/1.0.0',
                'bytes_before': len(csv_bytes), 'bytes_after': len(csv_bytes),
            },
        },
    }


def append_manifest(row: dict, manifest=None) -> Outcome:
    p = pathlib.Path(manifest) if manifest else MANIFEST
    line = json.dumps(row, sort_keys=True) + '\n'
    with open(p, 'a') as f:
        f.write(line)
    return Outcome.ok('MANIFEST_ROW_APPENDED', value=str(p),
                      capture_id=row['capture_id'], n_bytes=len(line))
