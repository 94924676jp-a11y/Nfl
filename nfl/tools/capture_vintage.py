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
        out.append(Source(name=spec.name, url=spec.url(season),
                          required=spec.required, durability=spec.durability,
                          reduce_cols=spec.reduce_cols,
                          content_kind=spec.content_kind, note=spec.note))
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


def fetch(src: Source, season: int, store: pathlib.Path) -> Outcome:
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
        _markers = sum(_text.lower().count(m) for m in
                       ("questionable", "doubtful", "did not participate",
                        "limited participation", "full participation"))
        _shell = any(m in _text for m in ("__NEXT_DATA__", "window.__INITIAL"))
        if len(payload) < 1000 or _markers == 0:
            tmp.unlink()
            return Outcome.fail(
                "HTML_SHELL_OR_EMPTY",
                f"{src.name}: HTTP {status} with {len(payload)} bytes but "
                f"{_markers} status-word markers"
                f"{' and a JS-shell marker present' if _shell else ''}. A 200 "
                f"over a page carrying no injury data is not a capture.",
                source=src.name, n_bytes=n_bytes, n_markers=_markers,
                js_shell=_shell)
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
               "content_kind": src.content_kind, **stored,
               "provenance": dataclasses.asdict(prov)},
        detail=f"{src.name}: {n_bytes} bytes, {lines} lines"
               + (" (content unchanged)" if stored["content_unchanged"] else " (NEW)"),
        source=src.name)


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
        return {"blob": str(blob.relative_to(_REPO)), "blob_durable": True,
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
        return {"blob": str(red.relative_to(_REPO)), "blob_durable": True,
                "blob_encoding": "gzip", "sha256_is_of": "uncompressed_bytes",
                "content_unchanged": unchanged,
                "reduced": {"columns": list(src.reduce_cols),
                            "strategy": "newest_dt_slice" if not unchanged else "unchanged",
                            **detail,
                            "full_bytes_ephemeral_at": str(eph.relative_to(_REPO))},
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
    rows, counts = [], {}
    for src in _sources(args.season):
        out = fetch(src, args.season, store)
        counts[out.state.value] = counts.get(out.state.value, 0) + 1
        row = {"capture_id": capture_id, "season": args.season,
               "source": src.name, "state": out.state.value, "code": out.code,
               "detail": out.detail,
               "evidence": {k: v for k, v in out.evidence.items()}}
        if out.state is State.PASS:
            row["value"] = out.value
        rows.append(row)
        flag = ""
        if out.state is State.PASS:
            flag = "  [unchanged]" if out.value["content_unchanged"] else "  [NEW]"
        print(f"{out.state.value:<15} {out.code:<28} {src.name}{flag}", flush=True)

    if not rows:
        raise SystemExit("CAPTURE_EMPTY: no sources attempted.")

    for po in pending_sources(args.season):
        counts[po.state.value] = counts.get(po.state.value, 0) + 1
        rows.append({"capture_id": capture_id, "season": args.season,
                     "source": po.evidence.get("source"),
                     "state": po.state.value, "code": po.code,
                     "detail": po.detail,
                     "evidence": {k: v for k, v in po.evidence.items()}})
        print(f"{po.state.value:<15} {po.code:<28} "
              f"{po.evidence.get('source')}")

    # Written AFTER every source is accounted for, reachable or not. It was
    # written before the pending/blocked loop, so the console reported the gap
    # and the durable record omitted it -- the audit trail was missing exactly
    # the sources that constitute the Item 1 failure, which is the half that
    # survives this container.
    with open(manifest, "a") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")

    print(f"\ncapture {capture_id}: {counts}")
    unmet = _registry.unmet_targets(manifest)
    if unmet["unmet"]:
        print(f"\nUNMET CAPTURE TARGETS (no reachable source can discharge "
              f"these): {unmet['unmet']}")
        print(f"  pending endpoint verification: {unmet['pending_sources']}")
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
