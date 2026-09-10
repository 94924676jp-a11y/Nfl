#!/usr/bin/env python3.12
"""Append-only vintage capture for NFL weekly information. G0A items 1-4.

WHY THIS EXISTS

Measured 2026-09-06: the nflverse injury archive keeps ONE row per player-week
(2024: 6,215 rows, 6,213 distinct season/week/player) stamped near the Friday
report, so the Wednesday practice vintage is overwritten rather than stored.
`injuries_2025.csv` dropped `date_modified` while keeping 16 columns, so 2025+
archive rows carry no clock at all and a column-count check passes straight
through the loss. The weekly cascade therefore cannot be reconstructed later at
any price. It exists only if something writes it down as it happens.

WHAT IT IS NOT

Not a model, a projection, or a feature builder. It fetches bytes, records what
arrived, and refuses to interpret.

DISCIPLINE, INHERITED

  * `sportsplatform.governance.outcome.Outcome` -- five states, named codes (Rule 001).
  * `sportsplatform.governance.provenance.Provenance` -- five clocks kept apart and
    VALIDATED per capture (Rule 002), not merely written down. HTTP
    `Last-Modified` supplies `source_timestamp`, which is how a file whose own
    schema lost its timestamp still gets one.
  * Raw bytes written BEFORE parsing, with status and headers.
  * Append-only: update is physically unavailable, so "never overwrite Tuesday
    with Sunday" holds by construction. An unchanged file at a later hour is a
    MEASUREMENT -- new manifest row, no new blob.

Usage:
    python3.12 nfl/tools/capture_vintage.py --season 2026
    python3.12 nfl/tools/capture_vintage.py --season 2026 --plan-only
"""
from __future__ import annotations

import argparse
import dataclasses
import datetime as _dt
import hashlib
import json
import pathlib
import subprocess
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402
from sportsplatform.governance.provenance import Provenance, validate as validate_prov  # noqa: E402
from nfl.capture import registry as _registry  # noqa: E402

NFLVERSE = "https://github.com/nflverse/nflverse-data/releases/download"

# Blobs the project must be able to re-read live INSIDE git; the rest are
# content-hashed with a durable reduced projection. See DURABILITY below.
DURABLE_ROOT = _REPO / "nfl" / "vintage"
EPHEMERAL_ROOT = _REPO / "nfl_vintage"
MANIFEST = _REPO / "nfl" / "vintage_manifest.jsonl"

TIMEOUT_S = 240
SCHEMA_VERSION = "nflverse-release-1"


@dataclasses.dataclass(frozen=True)
class Source:
    name: str
    url: str
    required: bool
    durability: str   # 'commit_raw' | 'reduce' | 'ephemeral'
    reduce_cols: tuple = ()
    content_kind: str = "csv"   # 'csv' | 'html' | 'json'
    note: str = ""
    # THE FIELD THE CONTENT GUARD READS, AND IT WAS NEVER CARRIED HERE.
    #
    # registry.SourceSpec defines content_markers and both official sources
    # set it, but this local Source did not declare it and _sources() did not
    # copy it across, so the content check at the html branch raised
    # AttributeError instead of running. The egress block hid that completely:
    # in an executor that cannot reach nfl.com the fetch fails long before the
    # guard is reached, so every run here reported a clean BLOCKED[NO_EGRESS]
    # while the guard underneath was broken. The executor that CAN fetch found
    # it instead -- official_inactives and official_injury_report both came
    # back FAIL[SOURCE_RAISED] on 2026-09-10T23:04Z, in the T-90 window.
    #
    # An unreachable code path is not a working one, and a guard is not
    # verified by an environment that never executes it.
    content_markers: tuple = ()


def _sources(season: int) -> list[Source]:
    """Built from nfl/capture/registry.py.

    Only REACHABLE specs are fetched here. A spec awaiting endpoint verification
    is reported by `pending_sources()` as a named BLOCKED rather than skipped,
    so its absence is visible in every capture rather than inferred from silence.
    """
    out = []
    for spec in _registry.REGISTRY:
        if spec.reachability is not _registry.Reachability.REACHABLE:
            continue
        # WATCH-ONLY sources are never fetched here. They belong to the
        # periodic availability watch (nfl/tools/watch_availability.py), which
        # is not event-anchored and discharges nothing. Letting them into this
        # path would put a routine poll's bytes inside an execution that
        # declares T-90 targets, and a capture that lands inside a window is
        # one argument away from being read as satisfying it.
        if spec.watch_only:
            continue
        out.append(Source(name=spec.name, url=spec.url(season),
                          required=spec.required, durability=spec.durability,
                          reduce_cols=spec.reduce_cols,
                          content_kind=spec.content_kind, note=spec.note,
                          content_markers=tuple(
                              getattr(spec, 'content_markers', ()) or ())))
    return out


def pending_sources(season: int) -> list[Outcome]:
    """Every registered source this executor cannot fetch, reported each run.

    Previously this reported only PENDING_ENDPOINT_VERIFICATION, so when the
    official sources gained real URLs and moved to BLOCKED_NO_EGRESS they
    vanished from the output entirely -- the most important gap in the system
    became invisible by being better understood. Any non-REACHABLE spec is
    reported.
    """
    out = []
    for spec in _registry.REGISTRY:
        if spec.watch_only:
            # Not a gap, and not silence either. Reported as NOT_APPLICABLE so a
            # reader of this capture can see the source exists, is reachable,
            # and is deliberately handled elsewhere -- rather than wondering
            # why a registered source produced no row.
            out.append(Outcome.not_applicable(
                "WATCH_ONLY_SOURCE_NOT_CAPTURED_HERE",
                f"{spec.name}: registered and reachable, but handled by the "
                f"periodic availability watch, which is not event-anchored and "
                f"discharges nothing. Deliberately outside this execution.",
                source=spec.name, url=spec.url(season)))
            continue
        if spec.reachability is _registry.Reachability.REACHABLE:
            continue
        out.append(_registry.resolve(spec.name, season))
    return out


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


def _http_date_to_iso(v: str | None) -> str | None:
    if not v:
        return None
    for fmt in ("%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S GMT"):
        try:
            return _dt.datetime.strptime(v.strip(), fmt).replace(
                tzinfo=_dt.timezone.utc).isoformat()
        except ValueError:
            continue
    return None


def fetch(src: Source, season: int, store: pathlib.Path,
          declaration: dict = None) -> Outcome:
    raw_dir = store / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    tmp = raw_dir / f".incoming.{src.name}"
    hdr_path = raw_dir / f".headers.{src.name}"

    requested_at = _now()
    cmd = ["curl", "-sS", "-L", "--max-time", str(TIMEOUT_S),
           "-D", str(hdr_path), "-o", str(tmp), "-w", "%{http_code}", src.url]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=TIMEOUT_S + 30)
    except subprocess.TimeoutExpired:
        return Outcome.blocked("SOURCE_TIMEOUT",
                               f"{src.name}: no response in {TIMEOUT_S}s",
                               cause=Cause.NETWORK, source=src.name, url=src.url)

    # Rule 002: "a retrieval timestamp is when the bytes ARRIVED". Stamping it
    # before the request is when we started ASKING, and for a live origin those
    # differ enough to matter: the server's own Date header then reads LATER
    # than our retrieved_at, and provenance.validate correctly refuses the
    # record as impossible -- you cannot have retrieved data before the source
    # produced it. That is what CAPTURE_PROVENANCE_INVALID caught on the first
    # real run against nfl.com.
    retrieved_at = _now()
    status = (r.stdout or "").strip() or "000"

    if status == "000":
        return Outcome.blocked(
            "NO_EGRESS",
            f"{src.name}: no HTTP response for {src.url}. This says nothing "
            f"about the data. Per DEC-029 it is ASSIGNED to an agent with "
            f"egress, not blocked for the project, and it is never stubbed.",
            cause=Cause.NETWORK, source=src.name, url=src.url,
            requested_at=requested_at, retrieved_at=retrieved_at)

    if status == "404":
        if src.required:
            return Outcome.deferred(
                "SOURCE_NOT_YET_PUBLISHED",
                f"{src.name}: 404 at {src.url}. Expected before the season "
                f"opens. Stays OWED until a later capture returns 200.",
                owed=f"{src.name}:{src.url}", source=src.name, url=src.url,
                http_status=status, retrieved_at=retrieved_at)
        return Outcome.not_applicable(
            "OPTIONAL_SOURCE_ABSENT",
            f"{src.name}: 404 and not required for the vintage log.",
            source=src.name, url=src.url)

    if status in ("403", "407"):
        return Outcome.blocked(f"SOURCE_HTTP_{status}",
                               f"{src.name}: egress policy denied {src.url}",
                               cause=Cause.NETWORK, source=src.name)
    if not status.startswith("2"):
        return Outcome.fail(f"SOURCE_HTTP_{status}",
                            f"{src.name}: unexpected status for {src.url}",
                            source=src.name)
    if not tmp.exists():
        return Outcome.fail("PAYLOAD_MISSING",
                            f"{src.name}: HTTP {status}, no file written.",
                            source=src.name)

    payload = tmp.read_bytes()
    n_bytes = len(payload)
    if n_bytes == 0:
        tmp.unlink()
        return Outcome.fail(
            "EMPTY_PAYLOAD_200",
            f"{src.name}: HTTP {status} with zero bytes. An empty result is "
            f"not a result.", source=src.name, http_status=status)

    _text = payload.decode("utf-8", "replace")
    _text_lines = _text.splitlines()
    _nonblank = [ln for ln in _text_lines if ln.strip()]
    lines = len(_text_lines)

    if src.content_kind == "html":
        # A CSV row count is meaningless here, and "200 with bytes" is not
        # evidence: a JavaScript shell returns a healthy-looking 200 over a page
        # containing no injury data at all. Fail closed on the shell.
        #
        # THE VOCABULARY IS THE SOURCE'S OWN, NOT ONE SHARED SET.
        # Sharing the injury-report words across every html source meant the
        # inactives page -- whose subject word is "inactive" -- was judged by
        # words it does not use, and passed on 4 incidental "questionable"s
        # against 21 "inactive"s. When those four left the page it went FAIL
        # over 419KB of real content. Measured on the committed blobs.
        _markers_for = src.content_markers or (
            "questionable", "doubtful", "did not participate",
            "limited participation", "full participation")
        _markers = sum(_text.lower().count(m.lower()) for m in _markers_for)
        _shell = any(m in _text for m in ("__NEXT_DATA__", "window.__INITIAL"))
        # A SHELL AND AN UNPUBLISHED PAGE ARE DIFFERENT FACTS.
        # Tiny payload, or a JS shell marker, is a real defect: the page did
        # not render. A full-size page that simply carries no rows yet is the
        # source not having published, which is a STATE -- the same state the
        # 404 sources report -- and calling it FAIL both misnames it and, in
        # this workflow, discards every other source's evidence for that run.
        if len(payload) < 1000 or _shell:
            tmp.unlink()
            return Outcome.fail(
                "HTML_SHELL_OR_EMPTY",
                f"{src.name}: HTTP {status} with {len(payload)} bytes"
                f"{' and a JS-shell marker present' if _shell else ''}. A 200 "
                f"over a page that did not render is not a capture.",
                source=src.name, n_bytes=n_bytes, n_markers=_markers,
                js_shell=_shell)
        if _markers == 0:
            # NOT a pass: nothing is stored and nothing is discharged. It is a
            # debt, and it stays owed until a later capture carries rows.
            tmp.unlink()
            return Outcome.deferred(
                "SOURCE_HAS_NO_ROWS_YET",
                f"{src.name}: HTTP {status}, {len(payload)} bytes that render, "
                f"carrying 0 of its own subject markers {_markers_for}. The "
                f"page exists and has not published rows yet. This discharges "
                f"nothing and is owed until a capture carries rows.",
                source=src.name, n_bytes=n_bytes, n_markers=0,
                markers_looked_for=list(_markers_for),
                owed=f"{src.name}:{url}")
        n_data_rows = _markers      # the HTML analogue of "rows that mean something"
    elif src.content_kind == "json":
        # A minified JSON document is a single line, so a row count read 8,996,076
        # bytes of real data as "a header with nothing under it". The question
        # for JSON is whether it parses and carries entries.
        import json as _json
        try:
            _doc = _json.loads(_text)
        except ValueError as exc:
            tmp.unlink()
            return Outcome.fail(
                "JSON_UNPARSEABLE",
                f"{src.name}: HTTP {status}, {n_bytes} bytes that do not parse "
                f"as JSON ({exc}).", source=src.name, n_bytes=n_bytes)
        _n = (len(_doc) if isinstance(_doc, list)
              else sum(len(v) if isinstance(v, list) else 1
                       for v in _doc.values()) if isinstance(_doc, dict) else 0)
        if _n < 1:
            tmp.unlink()
            return Outcome.fail(
                "JSON_EMPTY_DOCUMENT",
                f"{src.name}: parses as JSON but carries no entries. Valid and "
                f"empty is still empty.", source=src.name, n_bytes=n_bytes)
        n_data_rows = _n
    else:
        # Count DATA ROWS, not newlines. Counting newlines let b"a,b,c\n\n\n"
        # through as three lines: a durable blob written and a manifest row
        # claiming a real vintage, over zero rows of data.
        n_data_rows = max(0, len(_nonblank) - 1)
    if n_data_rows < 1:
        tmp.unlink()
        return Outcome.fail(
            "HEADER_ONLY_PAYLOAD",
            f"{src.name}: {n_bytes} bytes and {lines} line(s) but "
            f"{n_data_rows} data rows -- a header with nothing under it.",
            source=src.name, n_bytes=n_bytes, n_lines=lines,
            n_data_rows=n_data_rows)

    digest = hashlib.sha256(payload).hexdigest()
    header = payload.split(b"\n", 1)[0].decode("utf-8", "replace").strip()

    # curl runs with -L, so -D captures EVERY header block in the redirect
    # chain. Scanning all of them stamped a 302's Last-Modified onto a final
    # payload that carried none -- one resource's clock substituted for
    # another's, which is the substitution SOURCE_TIMESTAMP_ABSENT exists to
    # refuse. Only the final response block is read.
    last_modified = etag = http_date = None
    src_ts_header = None
    if hdr_path.exists():
        raw_headers = hdr_path.read_text("utf-8", "replace")
        blocks = [b for b in raw_headers.split("\r\n\r\n") if b.strip()]
        if len(blocks) == 1:
            blocks = [b for b in raw_headers.split("\n\n") if b.strip()]
        for ln in blocks[-1].splitlines():
            low = ln.lower()
            if low.startswith("last-modified:"):
                last_modified = ln.split(":", 1)[1].strip()
                src_ts_header = "Last-Modified"
            elif low.startswith("date:") and not last_modified:
                # Fallback ONLY. For a dynamically rendered page there is no
                # Last-Modified to have; Date is the origin's own statement of
                # when it generated this representation. That is a weaker clock
                # than Last-Modified and it is recorded as a different one --
                # never relabelled, and never taken from our own machine.
                http_date = ln.split(":", 1)[1].strip()
            elif low.startswith("etag:"):
                etag = ln.split(":", 1)[1].strip()

    src_ts = _http_date_to_iso(last_modified)
    if not src_ts and http_date:
        src_ts = _http_date_to_iso(http_date)
        src_ts_header = "Date"
    if not src_ts:
        # No source clock at all. Recorded as such, never backfilled from
        # retrieved_at -- that conflation is the V7 weather defect.
        tmp.unlink()
        return Outcome.fail(
            "SOURCE_TIMESTAMP_ABSENT",
            f"{src.name}: no parseable Last-Modified. The source clock is "
            f"recorded as absent rather than backfilled from retrieved_at; "
            f"substituting one clock for another is how a 30-minute-old "
            f"artifact passed a freshness check in V7.",
            source=src.name, last_modified_raw=last_modified,
            date_raw=http_date)

    stored = _persist(src, payload, digest, store)

    prov = Provenance(
        source=f"nflverse:{src.name}",
        source_timestamp=src_ts,
        retrieved_at=retrieved_at,
        generated_at=_now(),
        effective_for_date=str(season),
        schema_version=SCHEMA_VERSION,
        cache_timestamp=None,
        url=src.url,
    )
    pv = validate_prov(prov)
    if pv.state is not State.PASS:
        return Outcome.fail(
            "CAPTURE_PROVENANCE_INVALID",
            f"{src.name}: bytes arrived but their provenance is inconsistent "
            f"({pv.code}: {pv.detail})",
            source=src.name, provenance_code=pv.code)

    scope_out = _registry.build_scope(src.name, season=season,
                                     source_timestamp=src_ts)
    if scope_out.state is not State.PASS:
        return scope_out
    scope = scope_out.value

    return Outcome.ok(
        "CAPTURED",
        value={"source": src.name, "url": src.url, "http_status": status,
               "effective_scope": scope.as_dict(),
               "sha256": digest, "n_bytes": n_bytes, "n_lines": lines,
               "n_data_rows": n_data_rows,
               "n_cols": len(header.split(",")), "header": header[:2000],
               "etag": etag, "durability": src.durability,
               "source_timestamp_header": src_ts_header,
               "requested_at": requested_at,
               "substantive": _substantive(payload),
               # Directive 7 §2/§6. The declaration was fixed BEFORE this fetch
               # ran; eligibility judges these bytes against it. The old
               # post-hoc `discharge_claims` field is gone: it inferred the
               # target set from retrieved_at, which is what §6 forbids.
               "execution_target": declaration,
               "discharge_eligibility": _eligibility(
                   declaration, src.name, "PASS", retrieved_at, digest,
                   stored.get("blob"), True),
               "content_kind": src.content_kind, **stored,
               "provenance": dataclasses.asdict(prov)},
        detail=f"{src.name}: {n_bytes} bytes, {lines} lines"
               + (" (content unchanged)" if stored["content_unchanged"] else " (NEW)"),
        source=src.name)


def _eligibility(declaration, source, state, retrieved_at, sha256,
                 blob_path, provenance_valid) -> dict:
    """Judge these bytes against the targets the run DECLARED before fetching.

    A missing declaration is recorded as a refusal rather than as an empty
    result: a capture that cannot say what it was for is not a capture that was
    for nothing, and the two must not read alike.
    """
    from nfl.capture.execution import eligibility
    if not declaration:
        return {"state": "BLOCKED", "code": "NO_EXECUTION_DECLARATION",
                "detail": "this capture carries no pre-fetch target "
                          "declaration, so it may discharge nothing."}
    try:
        return eligibility(declaration, source=source, capture_state=state,
                           retrieved_at=retrieved_at, sha256=sha256,
                           blob_path=blob_path,
                           provenance_valid=provenance_valid)
    except Exception as exc:                                  # noqa: BLE001
        return {"state": "BLOCKED", "code": "ELIGIBILITY_FAILED",
                "detail": f"{type(exc).__name__}: {exc}"}




def _newest_schedule_snapshot():
    """The schedules blob this run should anchor to, chosen DETERMINISTICALLY.

    This was `sorted(glob(...), key=mtime)[-1]`. On a fresh Actions checkout
    every file carries the checkout time, so mtime order is git's write order,
    not capture order -- with 37 schedules blobs in the tree the "newest"
    snapshot was effectively arbitrary, and the windows a run anchors to are
    computed from it. Identity of the anchored target must not depend on
    filesystem incidentals.

    The manifest records when each blob was captured, so it is the authority.
    mtime remains only as a last resort when the manifest names none.
    """
    snaps = {q.name: q for q in DURABLE_ROOT.glob("schedules.*.csv.gz")}
    if not snaps:
        return None
    best, best_cid = None, ""
    try:
        with open(MANIFEST) as fh:
            for line in fh:
                if '"schedules"' not in line:
                    continue
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if r.get("source") != "schedules" or r.get("state") != "PASS":
                    continue
                blob = (r.get("value") or {}).get("blob") or ""
                name = pathlib.PurePosixPath(blob).name
                cid = str(r.get("capture_id") or "")
                if name in snaps and cid >= best_cid:
                    best, best_cid = snaps[name], cid
    except OSError:
        best = None
    if best is not None:
        return best
    return sorted(snaps.values(), key=lambda q: (q.stat().st_mtime, q.name))[-1]

def _rel(p) -> str:
    """A repo-relative path when the path is inside the repo, else as given.

    `pathlib.relative_to` RAISES when it is not a subpath, and that raise was
    inside the per-source fetch, so a store outside the repository killed the
    whole capture after its durable blobs were already on disk. A provenance
    string is not worth losing a capture window over.
    """
    q = pathlib.Path(p)
    try:
        return str(q.resolve().relative_to(_REPO))
    except ValueError:
        return str(q)


def _flush(manifest, rows) -> int:
    """Append every row, and say how many. Called from a finally block.

    The manifest used to be written only if the loop ran to completion, so a
    late failure erased the record of the earlier successes. The bytes were
    already durable; only the evidence that would let them discharge anything
    was lost.
    """
    if not rows:
        return 0
    with open(manifest, "a") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    return len(rows)

def _declare(season: int) -> dict:
    """The execution's target set, fixed at run start before any fetch."""
    from nfl.capture.execution import declare
    try:
        started = _dt.datetime.now(_dt.timezone.utc)
        plan = _nearby_plan(season, started.isoformat())
        if plan.state is not State.PASS:
            return {"state": plan.state.value, "code": plan.code,
                    "detail": plan.detail[:300]}
        snap = _newest_schedule_snapshot()
        out = declare(plan.value, declared_at=started,
                      plan_snapshot=snap.name if snap is not None else None)
        if out.state is not State.PASS:
            return {"state": out.state.value, "code": out.code,
                    "detail": out.detail[:300]}
        return out.value
    except Exception as exc:                                  # noqa: BLE001
        return {"state": "BLOCKED", "code": "DECLARATION_FAILED",
                "detail": f"{type(exc).__name__}: {exc}"}


def _nearby_plan(season: int, retrieved_at) -> Outcome:
    """Capture targets for every game within a week of `retrieved_at`.

    Spans weeks deliberately. The widest window is a practice report at
    deadline + 20h, so a capture can legitimately sit inside a window belonging
    to a game several days away, and week boundaries have nothing to do with it.
    Over-planning is safe: `claims_for` keeps only the windows that actually
    contain the instant, so extra games cost a little work and can add no claim.
    """
    import csv as _csv, gzip as _gzip, io as _io
    from nfl.capture.schedule import season_plan

    ts = _dt.datetime.fromisoformat(str(retrieved_at).replace("Z", "+00:00"))
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=_dt.timezone.utc)

    _best = _newest_schedule_snapshot()
    snaps = [_best] if _best is not None else []
    if not snaps:
        return Outcome.blocked(
            "NO_SCHEDULE_SNAPSHOT",
            "no schedules artifact captured, so no kickoff time is known and "
            "no capture can be attributed to a game.", cause=Cause.DEPENDENCY)

    rows, weeks = [], set()
    for r in _csv.DictReader(_io.StringIO(_gzip.open(snaps[-1], "rt").read())):
        if r.get("season") != str(season) or r.get("game_type") != "REG":
            continue
        try:
            gd = _dt.date.fromisoformat(r["gameday"])
        except (ValueError, KeyError, TypeError):
            continue
        if abs((gd - ts.date()).days) <= 7:
            rows.append(r)
            weeks.add(r.get("week"))
    if not rows:
        return Outcome.not_applicable(
            "NO_GAMES_NEARBY",
            f"no {season} regular-season game within 7 days of "
            f"{ts.date().isoformat()}, so no target window can be open.")
    plan = season_plan(rows)
    return Outcome.ok("NEARBY_PLAN", value=plan,
                      detail=f"{len(plan)} targets over {len(rows)} games "
                             f"in weeks {sorted(weeks)}",
                      n_games=len(rows), weeks=sorted(weeks))


def _substantive(payload: bytes) -> dict:
    """The DERIVED content digest, recorded beside the authoritative sha256.

    Additive and non-authoritative. `sha256` still identifies the bytes and
    still decides blob storage; this only lets a later reader tell a real
    content change from a rotated render nonce. Measured 2026-09-07: four
    captures each of the inactives page and the injury report produced four
    distinct raw digests apiece and ONE substantive digest apiece, so every
    `content_unchanged: false` on those rows was a fake new version.

    Blob deduplication is deliberately NOT changed here. That is a change to
    what the capture system stores and it is the owner's call.
    """
    from nfl.capture.volatility import substantive_digest
    out = substantive_digest(payload)
    if out.state is not State.PASS:
        # A digest that could not be computed is recorded as such. Omitting the
        # key would make "not computed" indistinguishable from "not applicable".
        return {"state": out.state.value, "code": out.code}
    return out.value


def _persist(src: Source, payload: bytes, digest: str,
             store: pathlib.Path) -> dict:
    """Durability policy, per source.

    Durable blobs are stored GZIPPED. Compression is lossless, so the recorded
    sha256 is still the digest of the ORIGINAL bytes and integrity is unchanged;
    it just makes daily retention affordable. Git is not assumed to be a durable
    archive in principle -- it is simply the durable store this environment has,
    and the policy is sized so that using it stays honest rather than aspirational.
    """
    import gzip

    def _write_gz(path: pathlib.Path, data: bytes) -> None:
        with gzip.open(path, "wb", compresslevel=9) as fh:
            fh.write(data)

    if src.durability == "commit_raw":
        DURABLE_ROOT.mkdir(parents=True, exist_ok=True)
        _ext = {"html": "html", "json": "json"}.get(src.content_kind, "csv")
        blob = DURABLE_ROOT / f"{src.name}.{digest[:16]}.{_ext}.gz"
        unchanged = blob.exists()
        if not unchanged:
            _write_gz(blob, payload)
        return {"blob": _rel(blob), "blob_durable": True,
                "blob_encoding": "gzip", "sha256_is_of": "uncompressed_bytes",
                "content_unchanged": unchanged, "reduced": None}

    if src.durability == "reduce":
        DURABLE_ROOT.mkdir(parents=True, exist_ok=True)
        red = DURABLE_ROOT / f"{src.name}.{digest[:16]}.reduced.csv.gz"
        unchanged = red.exists()
        detail = {}
        if not unchanged:
            import csv, io
            rdr = csv.DictReader(io.StringIO(payload.decode("utf-8", "replace")))
            fields = rdr.fieldnames or []
            cols = [c for c in src.reduce_cols if c in fields]
            missing = [c for c in src.reduce_cols if c not in fields]
            rows = list(rdr)

            # `dt`-versioned sources (depth_charts) are an upstream CUMULATIVE
            # history: every capture re-ships all prior snapshots. Storing the
            # whole file daily would retain the same rows ~170 times over. The
            # vintage fact we need is what the NEWEST snapshot said at the moment
            # we looked, and the manifest sha256 still attests to the whole file.
            newest = None
            if "dt" in fields and rows:
                newest = max((r.get("dt") or "") for r in rows)
                kept = [r for r in rows if (r.get("dt") or "") == newest]
            else:
                kept = rows

            buf = io.StringIO()
            w = csv.DictWriter(buf, fieldnames=cols)
            w.writeheader()
            for row in kept:
                w.writerow({c: row.get(c, "") for c in cols})
            _write_gz(red, buf.getvalue().encode())
            detail = {"rows_in_file": len(rows), "rows_kept": len(kept),
                      "newest_dt": newest, "missing_columns": missing}

        eph = store / "raw" / f"{src.name}.{digest[:16]}.csv"
        if not eph.exists():
            eph.write_bytes(payload)
        return {"blob": _rel(red), "blob_durable": True,
                "blob_encoding": "gzip", "sha256_is_of": "uncompressed_bytes",
                "content_unchanged": unchanged,
                "reduced": {"columns": list(src.reduce_cols),
                            "strategy": "newest_dt_slice" if not unchanged else "unchanged",
                            **detail,
                            "full_bytes_ephemeral_at": _rel(eph)},
                "reduce_recoverability_assumption":
                    "upstream retains full dt history for this source",
                "reduce_recoverability_checked": False}

    eph = store / "raw" / f"{src.name}.{digest[:16]}.csv"
    unchanged = eph.exists()
    if not unchanged:
        eph.write_bytes(payload)
    return {"blob": str(eph), "blob_durable": False,
            "content_unchanged": unchanged, "reduced": None}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--store", default=str(EPHEMERAL_ROOT))
    ap.add_argument("--manifest", default=str(MANIFEST))
    ap.add_argument("--plan-only", action="store_true",
                    help="Print the kickoff-anchored capture plan and exit.")
    args = ap.parse_args()

    if args.plan_only:
        from nfl.capture.schedule import capture_plan
        import csv as _csv
        sched = DURABLE_ROOT.glob("schedules.*.csv")
        latest = max(sched, key=lambda p: p.stat().st_mtime, default=None)
        if latest is None:
            print("no schedules snapshot captured yet; run a capture first")
            return 1
        rows = [r for r in _csv.DictReader(open(latest))
                if r["season"] == str(args.season) and r["game_type"] == "REG"
                and r["week"] == "1"]
        for g in rows[:4]:
            for c in capture_plan(g["game_id"], g["gameday"], g.get("gametime")):
                print(f'{c.due_utc.isoformat()}  {c.game_id:<22} {c.label:<18}'
                      f'{"" if c.confirmed else "  [DERIVED cadence]"}')
        return 0

    store = pathlib.Path(args.store)
    store.mkdir(parents=True, exist_ok=True)
    manifest = pathlib.Path(args.manifest)
    manifest.parent.mkdir(parents=True, exist_ok=True)

    capture_id = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    # DECLARED ONCE, HERE, BEFORE ANY BYTES ARE REQUESTED. Directive 7 §6: the
    # target set may not be inferred afterwards from timestamps. Every row in
    # this capture carries this same declaration, so the manifest records one
    # execution with one intent rather than N independently-rationalised ones.
    declaration = _declare(args.season)
    basis = declaration.get("basis", declaration.get("code", "UNKNOWN"))
    n_t = len(declaration.get("targets", []))
    print(f"execution {capture_id}: basis={basis}, {n_t} target(s) declared, "
          f"can_discharge={declaration.get('basis_can_discharge', False)}")
    for t in declaration.get("targets", [])[:12]:
        print(f"  target {t['game_id']:<18} {t['kind']:<13} "
              f"{t['window_start_utc'][11:16]}Z..{t['window_end_utc'][11:16]}Z")

    rows, counts = [], {}
    for src in _sources(args.season):
        # ONE SOURCE MAY NOT DESTROY THE RUN. There was no boundary here, and
        # the manifest was written only after the whole loop, so ANY unhandled
        # exception in ANY source discarded every row -- including sources
        # already captured successfully, whose durable blobs had already been
        # written into nfl/vintage. That is the observed production signature:
        # a schedules blob committed with no manifest row, a commit message
        # reading "capture unknown" because the final summary line never
        # printed, and the workflow reporting success. Reproduced locally.
        #
        # A raised source is now a NAMED row, never a lost run.
        try:
            out = fetch(src, args.season, store, declaration)
        except Exception as exc:                              # noqa: BLE001
            out = Outcome.fail(
                'SOURCE_RAISED',
                f'{type(exc).__name__}: {exc}'[:400])
        counts[out.state.value] = counts.get(out.state.value, 0) + 1
        row = {"capture_id": capture_id, "season": args.season,
               "source": src.name, "state": out.state.value, "code": out.code,
               "detail": out.detail,
               "evidence": {k: v for k, v in out.evidence.items()}}
        if out.state is State.PASS:
            row["value"] = out.value
        else:
            # A run that ATTEMPTED a declared target and failed must leave that
            # attempt in the record. Directive 7 §14: attempting is not
            # completing, and an attempt that vanishes cannot be told from one
            # that never happened.
            row["value"] = {
                "execution_target": declaration,
                "discharge_eligibility": _eligibility(
                    declaration, src.name, out.state.value, None, None, None,
                    False)}
        rows.append(row)
        flag = ""
        if out.state is State.PASS:
            flag = "  [unchanged]" if out.value["content_unchanged"] else "  [NEW]"
        print(f"{out.state.value:<15} {out.code:<28} {src.name}{flag}", flush=True)

    if not rows:
        raise SystemExit("CAPTURE_EMPTY: no sources attempted.")

    try:
        _pend = list(pending_sources(args.season))
    except Exception as exc:                                  # noqa: BLE001
        # Same rule as the source loop: a raise here is a named row, not a
        # lost run. The successes already in `rows` are not this loop's to
        # destroy.
        _pend = []
        rows.append({"capture_id": capture_id, "season": args.season,
                     "source": "pending_sources", "state": "FAIL",
                     "code": "PENDING_ENUMERATION_RAISED",
                     "detail": f'{type(exc).__name__}: {exc}'[:400],
                     "evidence": {"source": "pending_sources"},
                     "value": {"execution_target": declaration}})
    for po in _pend:
        counts[po.state.value] = counts.get(po.state.value, 0) + 1
        rows.append({"capture_id": capture_id, "season": args.season,
                     "source": po.evidence.get("source"),
                     "state": po.state.value, "code": po.code,
                     "detail": po.detail,
                     "evidence": {k: v for k, v in po.evidence.items()},
                     # Every row of this execution carries the same declaration,
                     # including the sources that never ran. A target this run
                     # declared and could not attempt is part of what the run
                     # did, and dropping it would make the record thinner than
                     # the truth.
                     "value": {
                         "execution_target": declaration,
                         "discharge_eligibility": _eligibility(
                             declaration, po.evidence.get("source"),
                             po.state.value, None, None, None, False)}})
        print(f"{po.state.value:<15} {po.code:<28} "
              f"{po.evidence.get('source')}")

    # Written AFTER every source is accounted for, reachable or not. It was
    # written before the pending/blocked loop, so the console reported the gap
    # and the durable record omitted it -- the audit trail was missing exactly
    # the sources that constitute the Item 1 failure, which is the half that
    # survives this container.
    n_written = _flush(manifest, rows)

    # A CAPTURE THAT WROTE NO MANIFEST ROW DID NOT CAPTURE ANYTHING, whatever
    # landed in nfl/vintage. Durable blobs with no row are orphans: nothing can
    # attribute them to a game, a window or a basis, so they can discharge
    # nothing. This is the exact production failure -- schedules blobs
    # committed, manifest untouched since 2026-09-08, and the workflow green.
    if n_written == 0:
        raise SystemExit(
            "CAPTURE_WROTE_NO_MANIFEST_ROW: sources ran and durable bytes may "
            "already be on disk, but no manifest row was appended, so nothing "
            "captured here can be attributed or discharge any obligation. "
            "Failing loudly rather than leaving orphan blobs behind a green "
            "run.")
    print(f"\nmanifest rows appended: {n_written}")

    print(f"\ncapture {capture_id}: {counts}")
    unmet = _registry.unmet_targets(manifest)
    # SOURCE-LEVEL, and it must be labelled as such wherever it is printed.
    # It answers "has an authorised source ever been captured for this kind",
    # which has no time dimension and no game dimension. Read as coverage it
    # says a Sunday poll discharges a Thursday kickoff's T-90 obligation, and it
    # did read that way: it reported all three perishable targets met while no
    # game had reached a window and no capture carried a game_id.
    print(f"\nSOURCE-LEVEL (has this kind ever been captured at all): "
          f"met={unmet['met']} unmet={unmet['unmet']}")
    print("  This is NOT coverage. It carries no window and no game.")
    if unmet["unmet"]:
        print(f"  pending endpoint verification: {unmet['pending_sources']}")

    # GAME-LEVEL. The answer that decides whether a perishable window was hit.
    try:
        from nfl.capture.coverage import coverage as _coverage
        cov = _coverage(args.season, 1, manifest_path=manifest)
        print(f"\nGAME-LEVEL COVERAGE  {cov.state.value}[{cov.code}]")
        print(f"  {cov.detail.splitlines()[0][:150]}")
        ev = cov.evidence
        if "n_targets" in ev:
            print(f"  targets={ev['n_targets']} covered={ev['covered']} "
                  f"missed={ev['missed']} not_yet_due={ev['not_yet_due']} "
                  f"game_attributed_captures={ev['attributed_captures']}"
                  f"/{ev['total_captures']}")
        for m in ev.get("missed_detail", [])[:10]:
            print(f"  MISSED {m['game_id']} {m['label']} "
                  f"window {m['window_start_utc']}..{m['window_end_utc']}")
    except Exception as exc:                       # noqa: BLE001
        # A coverage computation that cannot run is BLOCKED and must say so.
        # Swallowing it would restore the exact silence this replaces.
        print(f"\nGAME-LEVEL COVERAGE  BLOCKED[COVERAGE_NOT_COMPUTABLE]: "
              f"{type(exc).__name__}: {exc}")
    owed = [r for r in rows if r["state"] == "DEFERRED"]
    blocked = [r for r in rows if r["state"] == "BLOCKED"]
    if owed:
        print("\nOWED (DEFERRED, closed by a later capture):")
        for r in owed:
            print(f"  - {r['source']}: {r['code']}")
    if blocked:
        print("\nASSIGNED (BLOCKED here; another agent has the capability):")
        for r in blocked:
            print(f"  - {r['source']}: {r['code']}")
    # DEFERRED and BLOCKED are expected states, not run failures.
    return 1 if any(r["state"] == "FAIL" for r in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
