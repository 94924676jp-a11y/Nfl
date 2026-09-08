"""Prospective source-availability watch. Participation inputs, 2026 onward.

WHY THIS EXISTS

The 2026-09-08 receiving information-gap audit found an infrastructure gap, not
a data gap: `pbp_participation` and `snap_counts` are the inputs the whole P
component is built from, neither is in the vintage capture set, and both return
404 for 2026. So if and when they publish, the project has no provenance chain
for them -- no raw bytes kept, no first-observation record, no schema check.
This module is that chain. It does not manufacture data and it does not make
anything usable.

THREE THINGS THAT ARE NOT THE SAME THING

    SOURCE AVAILABILITY    does the artifact exist upstream, and in what shape
    CAPTURE SUCCESS        did we get bytes and record them correctly
    PREDICTIVE ELIGIBILITY may a forecast lawfully consume it

Collapsing any pair of these is the Class A failure this project keeps paying
for. A source that has not published is NOT_PUBLISHED -- an observed state of
the world, truthfully recorded -- and it must never render as a successful
capture. A capture that succeeded says nothing about whether a model may read
it; that is a separate record and it is refused here by construction.

WHAT THIS IS NOT

It is not event-anchored. It discharges NO G0A target, NO T-90 obligation, and
NO injury or inactives capture kind. A periodic poll that could discharge a
deadline would let a routine heartbeat satisfy a perishable obligation, which is
the confusion `nfl-capture.yml` already had to have corrected once.
"""
from __future__ import annotations

import csv
import datetime as _dt
import enum
import hashlib
import io
import json
import pathlib
import sys
from typing import Optional

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402

FIRST_SEEN = _REPO / "nfl" / "availability_first_seen.json"
MANIFEST = _REPO / "nfl" / "availability_manifest.jsonl"
BLOB_ROOT = _REPO / "nfl" / "availability_raw"

# Watched sources. Deliberately NOT the capture registry's serving set: these
# names exist in nfl/capture/registry.py with watch_only=True precisely so the
# vintage capture path cannot fetch them and they cannot serve a capture kind.
WATCHED = ("pbp_participation", "snap_counts")


class Availability(str, enum.Enum):
    """The state of the SOURCE. Not of our capture, and not of our permission."""
    NOT_PUBLISHED = 'NOT_PUBLISHED'
    AVAILABLE = 'AVAILABLE'
    HTTP_ERROR = 'HTTP_ERROR'
    SCHEMA_CHANGED = 'SCHEMA_CHANGED'
    AMBIGUOUS = 'AMBIGUOUS'


class ForgedRecordError(RuntimeError):
    """Raised when an availability record does not match the bytes it names."""


# --- accepted historical schemas ------------------------------------------
#
# READ FROM HISTORICAL FINAL FILES, 2026-09-08, AND USED ONLY AS A SCHEMA
# REFERENCE. Directive §9: a final file's Last-Modified is never as-of evidence,
# and none is taken here. What a final file CAN tell us is what the columns are
# called, and that is all it is used for.
#
# pbp_participation genuinely has two accepted shapes -- 20 columns for
# 2016-2022 and 26 for 2023-2025, the second a strict superset appending
# offense_names/defense_names/offense_positions/defense_positions/
# offense_numbers/defense_numbers. Recording one and calling the other drift
# would raise a false alarm on data the project already consumes.
_PART_20 = (
    "nflverse_game_id,old_game_id,play_id,possession_team,offense_formation,"
    "offense_personnel,defenders_in_box,defense_personnel,"
    "number_of_pass_rushers,players_on_play,offense_players,defense_players,"
    "n_offense,n_defense,ngs_air_yards,time_to_throw,was_pressure,route,"
    "defense_man_zone_type,defense_coverage_type")
_PART_26 = _PART_20 + (
    ",offense_names,defense_names,offense_positions,defense_positions,"
    "offense_numbers,defense_numbers")
_SNAP_16 = (
    "game_id,pfr_game_id,season,game_type,week,player,pfr_player_id,position,"
    "team,opponent,offense_snaps,offense_pct,defense_snaps,defense_pct,"
    "st_snaps,st_pct")

ACCEPTED_SCHEMAS: dict = {
    "pbp_participation": (tuple(_PART_20.split(",")), tuple(_PART_26.split(","))),
    "snap_counts": (tuple(_SNAP_16.split(",")),),
}

# The columns this project actually consumes, from nfl/research/p1/build_panel.py
# lines 118-150 (participation) and the snap join below it. Recorded so a drift
# report can say whether the drift touches anything we read, WITHOUT that
# nuance ever softening the fail-closed verdict.
REQUIRED_COLUMNS: dict = {
    "pbp_participation": ("nflverse_game_id", "play_id", "offense_players",
                          "offense_personnel", "offense_formation"),
    "snap_counts": ("game_id", "season", "game_type", "week", "player",
                    "pfr_player_id", "team", "offense_snaps", "offense_pct"),
}


def _now() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc)


def _parse(ts) -> _dt.datetime:
    if isinstance(ts, _dt.datetime):
        return ts if ts.tzinfo else ts.replace(tzinfo=_dt.timezone.utc)
    d = _dt.datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    return d if d.tzinfo else d.replace(tzinfo=_dt.timezone.utc)


# ==========================================================================
# GUARDS. Each is a module-level name so a test can bypass it and prove the
# refusal came from the guard rather than from something else in the path.
# ==========================================================================

def assert_body_is_data(name: str, payload: bytes, content_kind: str) -> Outcome:
    """A 200 is not evidence that the response carries the artifact.

    MEASURED, 2026-09-08, on this very release host:
    `nextgen_stats/ngs_receiving.csv.gz` answers HTTP 200 with a body of
    `Not Found`. A byte-count check passes it; a CSV parser produces one column
    named "Not Found" and zero rows. Recording that as an available source would
    be an absence wearing a result's costume.
    """
    head = payload[:512].lstrip()
    low = head.lower()
    if low.startswith(b"<!doctype") or low.startswith(b"<html") or b"<html" in low:
        return Outcome.fail(
            "BODY_IS_HTML_NOT_DATA",
            f"{name}: HTTP 200 over an HTML document, not {content_kind} data. "
            f"An error page served with a success status is still an error.",
            source=name, head=head[:200].decode("utf-8", "replace"))
    stripped = payload.strip()
    if stripped.lower() in (b"not found", b"404: not found", b"404 not found"):
        return Outcome.fail(
            "BODY_IS_ERROR_TEXT",
            f"{name}: HTTP 200 whose entire body is {stripped[:40]!r}. Measured "
            f"on this host for another asset on 2026-09-08; a status code is "
            f"not a payload.",
            source=name, n_bytes=len(payload))
    if len(stripped) == 0:
        return Outcome.fail(
            "EMPTY_PAYLOAD_200",
            f"{name}: HTTP 200 with zero bytes. An empty result is not a result.",
            source=name, n_bytes=len(payload))
    return Outcome.ok("BODY_LOOKS_LIKE_DATA", value=True, source=name)


def assert_not_future(retrieved_at, now: _dt.datetime = None,
                      tolerance_s: float = 120.0) -> Outcome:
    """Bytes cannot arrive from the future.

    Tolerated to two minutes for clock skew between a runner and this checker;
    beyond that the record is refused rather than trusted, because a retrieval
    clock ahead of now is the one input that makes every downstream ordering
    test -- including prediction-time eligibility -- pass by accident.
    """
    now = now or _now()
    try:
        got = _parse(retrieved_at)
    except (ValueError, TypeError) as exc:
        return Outcome.fail("RETRIEVED_AT_UNPARSEABLE",
                            f"retrieved_at={retrieved_at!r}: {exc}")
    drift = (got - now).total_seconds()
    if drift > tolerance_s:
        return Outcome.fail(
            "RETRIEVED_AT_IN_FUTURE",
            f"retrieved_at {retrieved_at} is {drift:.0f}s ahead of now "
            f"{now.isoformat()}. A retrieval clock in the future would make "
            f"every ordering check downstream pass without meaning anything.",
            drift_s=drift)
    return Outcome.ok("RETRIEVED_AT_SANE", value=drift)


def assert_schema_accepted(name: str, columns: tuple) -> Outcome:
    """Fail CLOSED on any header this project has not already accepted.

    An unrecognised header is drift, full stop. The record still says whether
    the columns we consume survived -- that is useful to a reader -- but the
    nuance never softens the verdict, because "the bits we use are still there"
    is precisely the reasoning that lets a silent upstream redefinition through.
    """
    accepted = ACCEPTED_SCHEMAS.get(name)
    if accepted is None:
        return Outcome.blocked(
            "SOURCE_HAS_NO_ACCEPTED_SCHEMA",
            f"{name}: no accepted schema is recorded, so no drift judgement is "
            f"possible. An unknown source is undeclared, not clean.",
            cause=Cause.GOVERNANCE, source=name)
    if tuple(columns) in accepted:
        return Outcome.ok("SCHEMA_MATCHES_ACCEPTED", value=tuple(columns),
                          source=name, n_cols=len(columns))
    need = REQUIRED_COLUMNS.get(name, ())
    missing = [c for c in need if c not in columns]
    best = max(accepted, key=lambda a: len(set(a) & set(columns)))
    return Outcome.fail(
        "SCHEMA_CHANGED",
        f"{name}: header matches no accepted schema. Got {len(columns)} "
        f"columns; accepted shapes are {[len(a) for a in accepted]}. "
        f"Added {sorted(set(columns) - set(best))[:8]}, "
        f"removed {sorted(set(best) - set(columns))[:8]}. "
        f"Required columns missing: {missing or 'none'} -- reported for the "
        f"reader, and it does not soften this verdict. Downstream use FAILS "
        f"CLOSED; the raw artifact is preserved.",
        source=name, n_cols=len(columns), missing_required=missing,
        added=sorted(set(columns) - set(best)),
        removed=sorted(set(best) - set(columns)))


def assert_no_discharge(record: dict) -> Outcome:
    """This watch discharges nothing. Ever.

    The guard exists because `nfl-capture.yml` already had to have exactly this
    confusion corrected once: a coverage-in-time argument was doing duty as a
    discharge claim. A periodic availability poll is even further from an
    obligation than that job was, and a record that grew a `discharges` key
    would be indistinguishable from one that had earned it.
    """
    claimed = (record.get("discharges") or record.get("discharge_claims")
               or record.get("serves_kinds") or record.get("execution_target"))
    if claimed:
        return Outcome.fail(
            "AVAILABILITY_WATCH_CLAIMED_A_DISCHARGE",
            f"an availability record claims {claimed!r}. This watch is not "
            f"event-anchored, is not attributed to a game, and may not "
            f"discharge a T-90 target or any injury/inactives capture kind.",
            source=record.get("source"))
    return Outcome.ok("NO_DISCHARGE_CLAIMED", value=True,
                      source=record.get("source"))


# ==========================================================================
# SCHEMA FINGERPRINT
# ==========================================================================

def schema_fingerprint(name: str, payload: bytes) -> Outcome:
    """Column names, order, inferable types, row count, substantive digest.

    The digest is over the header AS ORDERED. A reordering is drift: a
    positional reader would silently swap two columns, and this project has
    already been bitten by a column-count check passing through a real loss
    (`injuries_2025.csv` dropped `date_modified` while keeping 16 columns).
    """
    try:
        text = payload.decode("utf-8", "replace")
    except Exception as exc:                                     # noqa: BLE001
        return Outcome.fail("PAYLOAD_UNDECODABLE", f"{name}: {exc}", source=name)
    try:
        rdr = csv.reader(io.StringIO(text))
        header = next(rdr)
    except (StopIteration, csv.Error) as exc:
        return Outcome.fail(
            "CSV_UNPARSEABLE",
            f"{name}: cannot read a header row ({type(exc).__name__}: {exc}).",
            source=name)
    header = [h.strip() for h in header]
    if not header or all(not h for h in header):
        return Outcome.fail("CSV_HEADER_EMPTY",
                            f"{name}: header row is empty.", source=name)

    rows, ragged, first_ragged = 0, 0, None
    sample = [[] for _ in header]
    try:
        for row in rdr:
            if not any(c.strip() for c in row):
                continue
            rows += 1
            # RAGGED ROWS ARE THE REAL MALFORMEDNESS TEST, and csv.Error is not.
            # Python's reader does not raise on an unterminated quote: it
            # swallows the rest of the file into one field and returns a single
            # tidy-looking row. A seeded `a,"unterminated` body therefore
            # reached AVAILABLE in this module's first version. Comparing each
            # row's field count against the header is what actually catches it.
            if len(row) != len(header):
                ragged += 1
                if first_ragged is None:
                    first_ragged = rows
            if rows <= 500:
                for i in range(min(len(row), len(header))):
                    sample[i].append(row[i])
    except csv.Error as exc:
        return Outcome.fail(
            "CSV_MALFORMED",
            f"{name}: header parsed but the body is malformed at row ~{rows} "
            f"({exc}). A partially readable file is not a readable file.",
            source=name, n_rows_before_error=rows)

    if ragged:
        return Outcome.fail(
            "CSV_RAGGED_ROWS",
            f"{name}: {ragged} of {rows} data row(s) do not have "
            f"{len(header)} fields, first at row {first_ragged}. A file that "
            f"does not parse to a rectangle is not a readable file, and a "
            f"reader that took the first {len(header)} fields of each row "
            f"would silently mis-assign every column after the break.",
            source=name, n_ragged=ragged, n_rows=rows,
            first_ragged_row=first_ragged, n_cols=len(header))

    if rows < 1:
        return Outcome.fail(
            "HEADER_ONLY_PAYLOAD",
            f"{name}: {len(header)} columns and 0 data rows -- a header with "
            f"nothing under it.", source=name, n_cols=len(header))

    types = {}
    for i, col in enumerate(header):
        vals = [v for v in sample[i] if v != ""]
        if not vals:
            types[col] = "empty"
            continue
        try:
            [int(v) for v in vals]
            types[col] = "int"
            continue
        except ValueError:
            pass
        try:
            [float(v) for v in vals]
            types[col] = "float"
        except ValueError:
            types[col] = "str"

    order_digest = hashlib.sha256(
        "\x1f".join(header).encode()).hexdigest()
    # Substantive digest: the sorted body, so a re-serialisation that reorders
    # rows is not reported as a content change. Non-authoritative -- sha256 of
    # the raw bytes still identifies the artifact and still decides storage.
    body = sorted(ln for ln in text.splitlines()[1:] if ln.strip())
    substantive = hashlib.sha256("\n".join(body).encode()).hexdigest()

    return Outcome.ok(
        "SCHEMA_FINGERPRINTED",
        value={"columns": header, "n_cols": len(header),
               "column_order_digest": order_digest, "types": types,
               "n_rows": rows, "substantive_digest": substantive},
        detail=f"{name}: {len(header)} cols, {rows} rows", source=name)


# ==========================================================================
# FIRST-SEEN LEDGER -- write once, never restamped
# ==========================================================================

def load_first_seen(path: pathlib.Path = None) -> dict:
    p = pathlib.Path(path or FIRST_SEEN)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except ValueError:
        return {}


def record_first_seen(key: str, record: dict, path: pathlib.Path = None) -> Outcome:
    """Persist the first observation of an artifact becoming available.

    Idempotent by construction: a second call for the same key returns the
    ORIGINAL record NOT_APPLICABLE. The alternative -- last-write-wins -- would
    quietly turn "first observed on the 9th" into "first observed today", every
    day, and the field would end up meaning nothing at all.

    The wording is fixed and is not a stylistic choice. What we know is when
    THIS system first saw it. The publisher's true first-publication time is not
    observable from here and is never implied.
    """
    p = pathlib.Path(path or FIRST_SEEN)
    book = load_first_seen(p)
    if key in book:
        return Outcome.not_applicable(
            "FIRST_SEEN_ALREADY_RECORDED",
            f"{key}: first observed available by this capture system at "
            f"{book[key].get('first_retrieved_at')}. A later observation does "
            f"not move it.", existing=book[key])
    rec = dict(record)
    rec["wording"] = "First observed available by this capture system."
    rec["not_a_claim_about"] = (
        "the publisher's true first publication time, which is not observable "
        "from here and is not implied")
    book[key] = rec
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(book, indent=1, sort_keys=True) + "\n")
    return Outcome.ok("FIRST_SEEN_RECORDED", value=rec, detail=f"{key} first seen")


# ==========================================================================
# RECORD INTEGRITY
# ==========================================================================

def verify_record(record: dict, repo_root: pathlib.Path = None) -> Outcome:
    """Recompute the digest from the stored blob and compare.

    A manifest row is a claim; the blob is the evidence. Without this, a row
    could be hand-written -- or written by a parser that got it wrong -- and
    nothing downstream would ever notice. A missing blob is a FAIL and never an
    absence read as "nothing to check".
    """
    import gzip
    root = pathlib.Path(repo_root or _REPO)
    if record.get("availability") != Availability.AVAILABLE.value:
        if record.get("blob") or record.get("sha256"):
            return Outcome.fail(
                "UNAVAILABLE_RECORD_CARRIES_BYTES",
                f"{record.get('source')}: availability is "
                f"{record.get('availability')} yet the row names bytes. A "
                f"source that did not publish has no payload.",
                source=record.get("source"))
        return Outcome.not_applicable(
            "NO_BYTES_TO_VERIFY",
            f"{record.get('source')}: {record.get('availability')} -- there is "
            f"no payload, which is the correct state, not a missing one.",
            source=record.get("source"))

    blob = record.get("blob")
    sha = record.get("sha256")
    if not blob or not sha:
        return Outcome.fail(
            "AVAILABLE_RECORD_WITHOUT_EVIDENCE",
            f"{record.get('source')}: AVAILABLE but names "
            f"blob={blob!r} sha256={sha!r}.", source=record.get("source"))
    path = root / blob
    if not path.exists():
        return Outcome.fail(
            "RAW_BLOB_MISSING",
            f"{record.get('source')}: manifest row names {blob} and it is not "
            f"on disk. The row is a claim; the blob is the evidence.",
            source=record.get("source"), blob=blob)
    try:
        raw = gzip.open(path, "rb").read() if str(path).endswith(".gz") \
            else path.read_bytes()
    except OSError as exc:
        return Outcome.fail("RAW_BLOB_UNREADABLE",
                            f"{record.get('source')}: {path}: {exc}",
                            source=record.get("source"))
    actual = hashlib.sha256(raw).hexdigest()
    if actual != sha:
        return Outcome.fail(
            "RECORD_DIGEST_MISMATCH",
            f"{record.get('source')}: row claims sha256 {sha[:16]} but the "
            f"stored bytes hash to {actual[:16]}. Either the row was forged or "
            f"the blob was rewritten; both are refused and neither is guessed "
            f"at.", source=record.get("source"),
            claimed=sha, actual=actual)
    return Outcome.ok("RECORD_VERIFIED", value=actual,
                      detail=f"{record.get('source')}: blob hashes as claimed",
                      source=record.get("source"))


# ==========================================================================
# PREDICTIVE ELIGIBILITY -- computed, and refused
# ==========================================================================

def eligibility_record(record: dict, forecast_written_at=None, kickoff=None,
                       now: _dt.datetime = None) -> dict:
    """What would be required LATER, evaluated now, and authorised by nobody.

    Two independent answers, deliberately not merged into one boolean:

      `ordering_ok`     retrieved_at < forecast.written_at < kickoff, plus the
                        record's own integrity. This is a fact about clocks.
      `authorized`      always False in this task. This is a decision, and it
                        is the owner's, not a consequence of the clocks lining
                        up.

    Merging them is how "the timestamps are fine" becomes "the model may read
    it", which is a promotion nobody made.
    """
    out = {"source": record.get("source"), "season": record.get("season"),
           "requirement": "retrieved_at < forecast.written_at < kickoff",
           "authorized": False,
           "authorization_code": "NOT_AUTHORIZED_BY_OWNER",
           "authorization_detail":
               "This task creates the evidence a later owner authorization "
               "would need. It does not grant model consumption, and an "
               "ordering test that passes does not grant it either."}

    if record.get("availability") != Availability.AVAILABLE.value:
        out.update(ordering_ok=False, ordering_code="SOURCE_NOT_AVAILABLE",
                   ordering_detail=f"availability is {record.get('availability')}")
        return out
    ver = verify_record(record)
    if ver.state is not State.PASS:
        out.update(ordering_ok=False, ordering_code=ver.code,
                   ordering_detail=ver.detail)
        return out
    fut = assert_not_future(record.get("retrieved_at"), now=now)
    if fut.state is not State.PASS:
        out.update(ordering_ok=False, ordering_code=fut.code,
                   ordering_detail=fut.detail)
        return out
    if forecast_written_at is None or kickoff is None:
        out.update(ordering_ok=None, ordering_code="NO_FORECAST_TO_JUDGE",
                   ordering_detail="no forecast time or kickoff was supplied, "
                                   "so the ordering is UNEVALUATED -- which is "
                                   "not the same as satisfied")
        return out
    try:
        got, wrote, kick = (_parse(record["retrieved_at"]),
                            _parse(forecast_written_at), _parse(kickoff))
    except (ValueError, TypeError, KeyError) as exc:
        out.update(ordering_ok=False, ordering_code="CLOCK_UNPARSEABLE",
                   ordering_detail=str(exc))
        return out
    ok = got < wrote < kick
    out.update(ordering_ok=ok,
               ordering_code="ORDERING_SATISFIED" if ok else "ORDERING_VIOLATED",
               ordering_detail=f"retrieved_at {got.isoformat()} "
                               f"{'<' if got < wrote else '>='} "
                               f"forecast.written_at {wrote.isoformat()} "
                               f"{'<' if wrote < kick else '>='} "
                               f"kickoff {kick.isoformat()}",
               retrieved_at=got.isoformat(),
               forecast_written_at=wrote.isoformat(), kickoff=kick.isoformat())
    return out
