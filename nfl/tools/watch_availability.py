#!/usr/bin/env python3.12
"""Unattended availability watch for the participation inputs.

WHAT IT ANSWERS, AND THE ONLY THING IT ANSWERS

    "Has the 2026 source become published, or changed?"

WHAT IT IS NOT

Not event-anchored. It is not attributed to a game, it carries no game_id, it
declares no targets, and it discharges NO G0A item, NO T-90 obligation and NO
injury/inactives capture kind. `nfl-capture.yml` already had to have a
coverage-in-time argument corrected once for doing duty as a discharge claim;
this job is further from an obligation than that one was, and
`availability.assert_no_discharge` refuses any record that grows a claim.

ORDER OF OPERATIONS, AND WHY IT IS THIS ORDER

    request  ->  bytes arrive  ->  RAW BYTES STORED  ->  hash  ->  parse

Bytes are content-addressed and written before anything looks at them, so a
parser defect can never destroy the evidence of what actually arrived, and a
later parser version can be re-run against the original artifact. The parser
version is recorded downstream of the blob, never upstream of it.

Storage is append-only and immutable. A digest already on disk is NOT rewritten
and its first-retrieval sidecar is NOT restamped -- an unchanged artifact seen
again is a MEASUREMENT (a new manifest row) and not a new version.

Usage:
    python3.12 nfl/tools/watch_availability.py --season 2026
    python3.12 nfl/tools/watch_availability.py --season 2026 --dry-run
"""
from __future__ import annotations

import argparse
import dataclasses
import datetime as _dt
import gzip
import hashlib
import json
import pathlib
import subprocess
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402
from sportsplatform.governance.provenance import (                   # noqa: E402
    Provenance, validate as validate_prov)
from nfl.capture import availability as AV                           # noqa: E402
from nfl.capture import registry as _registry                        # noqa: E402

TIMEOUT_S = 300
PARSER_VERSION = "availability-watch-1"
WATCH_KIND = "periodic_availability_probe"


def _now_iso() -> str:
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


def _headers(path: pathlib.Path) -> dict:
    """Parse only the FINAL response block.

    curl runs with -L, so -D captures every block in the redirect chain. This
    host answers 302 then 200, and scanning all blocks once stamped a 302's
    Last-Modified onto a payload that carried none -- one resource's clock
    substituted for another's.
    """
    out = {"last_modified": None, "etag": None, "date": None,
           "content_length": None, "content_type": None, "status_line": None}
    if not path.exists():
        return out
    raw = path.read_text("utf-8", "replace")
    blocks = [b for b in raw.split("\r\n\r\n") if b.strip()]
    if len(blocks) == 1:
        blocks = [b for b in raw.split("\n\n") if b.strip()]
    if not blocks:
        return out
    for ln in blocks[-1].splitlines():
        low = ln.lower()
        if low.startswith("http/"):
            out["status_line"] = ln.strip()
        elif low.startswith("last-modified:"):
            out["last_modified"] = ln.split(":", 1)[1].strip()
        elif low.startswith("etag:"):
            out["etag"] = ln.split(":", 1)[1].strip()
        elif low.startswith("date:"):
            out["date"] = ln.split(":", 1)[1].strip()
        elif low.startswith("content-length:"):
            out["content_length"] = ln.split(":", 1)[1].strip()
        elif low.startswith("content-type:"):
            out["content_type"] = ln.split(":", 1)[1].strip()
    return out


def _rel(path: pathlib.Path) -> str:
    """Repo-relative when the store is inside the repo, absolute otherwise.

    The production store is `nfl/availability_raw/`, and a repo-relative path is
    what makes a manifest row portable and reviewable in a diff. A test store is
    a temp directory outside the tree, and forcing relative_to() there raised
    ValueError inside the writer -- so a defect in the tests' own scaffolding
    would have looked like a defect in capture.
    """
    try:
        return str(path.relative_to(_REPO))
    except ValueError:
        return str(path)


def _store_raw(name: str, season: int, payload: bytes, digest: str,
               retrieved_at: str, root: pathlib.Path) -> dict:
    """Content-addressed, gzipped, immutable, with a write-once sidecar.

    The sidecar is where "do not restamp cache hits" is actually enforced. The
    blob's own `first_retrieved_at` is written when the bytes are first seen and
    never touched again; the CURRENT retrieval time lives on the manifest row,
    which is a different fact. Collapsing them would make every re-observation
    look like a fresh arrival -- the V7 weather defect in a different costume.
    """
    root.mkdir(parents=True, exist_ok=True)
    blob = root / f"{name}_{season}.{digest[:16]}.csv.gz"
    side = root / f"{name}_{season}.{digest[:16]}.meta.json"
    unchanged = blob.exists()
    if not unchanged:
        with gzip.open(blob, "wb", compresslevel=9) as fh:
            fh.write(payload)
        side.write_text(json.dumps(
            {"source": name, "season": season, "sha256": digest,
             "n_bytes": len(payload),
             "first_retrieved_at": retrieved_at,
             "sha256_is_of": "uncompressed_bytes",
             "immutable": "content-addressed; never rewritten, never restamped"},
            indent=1) + "\n")
    first = retrieved_at
    if side.exists():
        try:
            first = json.loads(side.read_text()).get("first_retrieved_at", first)
        except ValueError:
            pass
    return {"blob": _rel(blob), "blob_sidecar": _rel(side),
            "blob_encoding": "gzip", "sha256_is_of": "uncompressed_bytes",
            "content_unchanged": unchanged,
            "blob_first_retrieved_at": first}


def probe(name: str, season: int, root: pathlib.Path,
          tmp: pathlib.Path) -> Outcome:
    """One source, one observation. Returns an availability record."""
    res = _registry.resolve(name, season)
    if res.state is not State.PASS:
        return res
    url = res.value
    spec = _registry.BY_NAME[name]
    if not spec.watch_only:
        return Outcome.fail(
            "WATCHED_SOURCE_NOT_WATCH_ONLY",
            f"{name} is registered without watch_only, so the vintage capture "
            f"path also fetches it. Two capture paths over one source is how a "
            f"periodic poll ends up inside an event-anchored execution.",
            source=name)

    # Owner decision RET-001 is checked BEFORE any bytes are requested. If the
    # retention policy is not the decided one, the right move is not to fetch
    # and store under the wrong policy and sort it out later -- the storing IS
    # the policy, and a 'reduce' write has already discarded what it discarded
    # by the time anyone looks.
    ret = AV.assert_retention_policy(name)
    if ret.state is State.FAIL or ret.state is State.BLOCKED:
        return Outcome.fail(
            ret.code, ret.detail,
            availability=AV.Availability.AMBIGUOUS.value,
            source=name, url=url)

    tmp.mkdir(parents=True, exist_ok=True)
    body = tmp / f".body.{name}"
    hdrf = tmp / f".headers.{name}"
    requested_at = _now_iso()
    cmd = ["curl", "-sS", "-L", "--max-time", str(TIMEOUT_S), "-D", str(hdrf),
           "-o", str(body), "-w", "%{http_code}", url]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=TIMEOUT_S + 30)
    except subprocess.TimeoutExpired:
        return Outcome.blocked(
            "PROBE_TIMEOUT", f"{name}: no response in {TIMEOUT_S}s",
            cause=Cause.NETWORK, source=name, url=url,
            availability=AV.Availability.AMBIGUOUS.value,
            requested_at=requested_at)

    # Rule 002: retrieved_at is when the bytes ARRIVED, never when we started
    # asking. Stamping it before the request makes the origin's own Date header
    # read later than our retrieval, and provenance.validate correctly refuses
    # that as impossible.
    retrieved_at = _now_iso()
    status = (r.stdout or "").strip() or "000"
    hdr = _headers(hdrf)
    src_ts = _http_date_to_iso(hdr["last_modified"])
    src_ts_header = "Last-Modified" if src_ts else None
    if not src_ts and hdr["date"]:
        src_ts = _http_date_to_iso(hdr["date"])
        src_ts_header = "Date"

    # `source_timestamp` is the ARTIFACT'S clock and is attached only on a path
    # where an artifact actually arrived. On a 404 the origin still sends a
    # Date header -- it is the clock of the ERROR RESPONSE, and carrying it as
    # source_timestamp would give a file that does not exist a timestamp. That
    # is the same substitution SOURCE_TIMESTAMP_ABSENT exists to refuse, so the
    # error response's own clock is recorded under its own name instead. It is
    # worth keeping: it says the origin genuinely answered.
    base = {"source": name, "season": season, "url": url,
            "http_status": status, "requested_at": requested_at,
            "retrieved_at": retrieved_at,
            "probe_response_date": _http_date_to_iso(hdr["date"]),
            "http": hdr, "watch_kind": WATCH_KIND,
            "retention_policy": AV.RETENTION_POLICY,
            "retention_decision_id": "RET-001",
            "discharges": [],
            "discharges_note": "This periodic watch discharges no G0A item, no "
                               "T-90 target and no capture kind.",
            "parser_version": PARSER_VERSION}

    if status == "000":
        return Outcome.blocked(
            "NO_EGRESS",
            f"{name}: no HTTP response for {url}. This says nothing about "
            f"whether the source published; it is a fact about this executor.",
            cause=Cause.NETWORK,
            availability=AV.Availability.AMBIGUOUS.value, **base)

    if status == "404":
        # THE EXPECTED STATE TODAY, and it is an observation, not a failure.
        # It is DEFERRED because it leaves a debt open: the watch keeps looking.
        return Outcome.deferred(
            "SOURCE_NOT_YET_PUBLISHED",
            f"{name}: HTTP 404 at {url}. The source has not published for "
            f"{season}. That is an observed state of the world, truthfully "
            f"recorded, and it is never rendered as a successful capture.",
            owed=f"{name}:{url}",
            availability=AV.Availability.NOT_PUBLISHED.value, **base)

    if status in ("403", "407"):
        return Outcome.blocked(
            f"PROBE_HTTP_{status}",
            f"{name}: egress policy denied {url}. A refusal aimed at us is not "
            f"a statement about the source.", cause=Cause.NETWORK,
            availability=AV.Availability.AMBIGUOUS.value, **base)

    if not status.startswith("2"):
        return Outcome.fail(
            f"PROBE_HTTP_{status}",
            f"{name}: HTTP {status} at {url}. Neither published nor absent -- "
            f"the source answered with an error.",
            availability=AV.Availability.HTTP_ERROR.value, **base)

    if not body.exists():
        return Outcome.fail(
            "PAYLOAD_MISSING", f"{name}: HTTP {status} and no file written.",
            availability=AV.Availability.AMBIGUOUS.value, **base)

    payload = body.read_bytes()
    base["n_bytes"] = len(payload)
    base["content_length_header"] = hdr["content_length"]
    # An artifact arrived, so it may now carry an artifact clock.
    base["source_timestamp"] = src_ts
    base["source_timestamp_header"] = src_ts_header

    # ---- guard: a 200 is not evidence that this is the artifact -----------
    ok_body = AV.assert_body_is_data(name, payload, "csv")
    if ok_body.state is not State.PASS:
        return Outcome.fail(
            ok_body.code, ok_body.detail,
            availability=AV.Availability.AMBIGUOUS.value, **base)

    # ---- RAW BEFORE PARSE. Bytes to disk before anything reads them -------
    digest = hashlib.sha256(payload).hexdigest()
    base["sha256"] = digest
    stored = _store_raw(name, season, payload, digest, retrieved_at, root)
    base.update(stored)

    # ---- guard: our own retrieval clock is not in the future --------------
    fut = AV.assert_not_future(retrieved_at)
    if fut.state is not State.PASS:
        return Outcome.fail(fut.code, fut.detail,
                            availability=AV.Availability.AMBIGUOUS.value, **base)

    if not src_ts:
        return Outcome.fail(
            "SOURCE_TIMESTAMP_ABSENT",
            f"{name}: HTTP {status} with bytes but no parseable source clock. "
            f"Recorded as absent, never backfilled from retrieved_at -- that "
            f"substitution is the V7 weather defect. The raw artifact is kept.",
            availability=AV.Availability.AMBIGUOUS.value, **base)

    prov = Provenance(
        source=f"nflverse:{name}", source_timestamp=src_ts,
        retrieved_at=retrieved_at, generated_at=_now_iso(),
        effective_for_date=str(season), schema_version=PARSER_VERSION,
        # No cache is used: this always fetches. Recorded as None rather than
        # omitted, so "live" and "unknown" cannot read alike.
        cache_timestamp=None, url=url)
    pv = validate_prov(prov)
    base["provenance"] = dataclasses.asdict(prov)
    if pv.state is not State.PASS:
        return Outcome.fail(
            "PROBE_PROVENANCE_INVALID",
            f"{name}: bytes arrived and are stored, but their clocks are "
            f"inconsistent ({pv.code}: {pv.detail})",
            availability=AV.Availability.AMBIGUOUS.value,
            provenance_code=pv.code, **base)

    # ---- parse: only now, and only downstream of the stored blob ----------
    fp = AV.schema_fingerprint(name, payload)
    if fp.state is not State.PASS:
        return Outcome.fail(
            fp.code, fp.detail,
            availability=AV.Availability.AMBIGUOUS.value, **base)
    base["schema_fingerprint"] = fp.value
    base["n_rows"] = fp.value["n_rows"]

    # ---- guard: schema drift fails CLOSED for downstream use --------------
    sch = AV.assert_schema_accepted(name, tuple(fp.value["columns"]))
    if sch.state is not State.PASS:
        return Outcome.fail(
            "SCHEMA_CHANGED",
            f"{name}: {sch.detail}",
            availability=AV.Availability.SCHEMA_CHANGED.value,
            downstream_use="FAILS CLOSED",
            raw_preserved=base.get("blob"),
            schema_evidence=sch.evidence, **base)

    return Outcome.ok(
        "SOURCE_AVAILABLE",
        value={**base, "availability": AV.Availability.AVAILABLE.value,
               "downstream_use": "NOT AUTHORIZED -- availability is not "
                                 "predictive eligibility"},
        detail=f"{name}: {len(payload)} bytes, {fp.value['n_cols']} cols, "
               f"{fp.value['n_rows']} rows"
               + (" (content unchanged)" if stored["content_unchanged"] else " (NEW)"),
        source=name)


def _record(out: Outcome) -> dict:
    """Flatten an Outcome into the manifest row, then check it claims nothing."""
    ev = dict(out.evidence or {})
    if out.state is State.PASS and isinstance(out.value, dict):
        ev.update(out.value)
    ev.setdefault("availability", AV.Availability.AMBIGUOUS.value)
    rec = {"state": out.state.value, "code": out.code,
           "detail": out.detail, **ev}
    guard = AV.assert_no_discharge({k: v for k, v in rec.items()
                                    if k != "discharges_note"}
                                   | {"discharges": rec.get("discharges") or None})
    rec["no_discharge_guard"] = {"state": guard.state.value, "code": guard.code}
    return rec


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--sources", default=",".join(AV.WATCHED))
    ap.add_argument("--manifest", default=str(AV.MANIFEST))
    ap.add_argument("--blob-root", default=str(AV.BLOB_ROOT))
    ap.add_argument("--first-seen", default=str(AV.FIRST_SEEN))
    ap.add_argument("--tmp", default="/tmp/nfl-availability")
    ap.add_argument("--dry-run", action="store_true",
                    help="probe and print; write no manifest row and no blob")
    args = ap.parse_args()

    root = pathlib.Path(args.blob_root)
    tmp = pathlib.Path(args.tmp)
    manifest = pathlib.Path(args.manifest)
    watch_id = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    print(f"availability watch {watch_id}  season {args.season}")
    print(f"  kind={WATCH_KIND}  discharges: NOTHING "
          f"(no G0A item, no T-90 target, no capture kind)")

    rows, worst = [], 0
    RANK = {"PASS": 0, "NOT_APPLICABLE": 0, "DEFERRED": 1, "BLOCKED": 1, "FAIL": 2}
    for name in [s for s in args.sources.split(",") if s]:
        out = probe(name, args.season, root if not args.dry_run
                    else pathlib.Path(args.tmp) / "dry", tmp)
        rec = _record(out)
        rec["watch_id"] = watch_id
        rows.append(rec)
        worst = max(worst, RANK.get(out.state.value, 2))
        print(f"  {out.state.value:<15}{rec.get('availability','?'):<16}"
              f"{name:<20}{out.code}")
        print(f"      {out.detail[:150]}")

        # FIRST-SEEN: written once, on the first observation that the artifact
        # is actually available. Never restamped by a later observation.
        if (out.state is State.PASS
                and rec.get("availability") == AV.Availability.AVAILABLE.value
                and not args.dry_run):
            key = f"{name}_{args.season}"
            fs = AV.record_first_seen(key, {
                "source": name, "season": args.season, "url": rec["url"],
                "first_requested_at": rec["requested_at"],
                "first_retrieved_at": rec["retrieved_at"],
                "http_status": rec["http_status"],
                "source_timestamp": rec["source_timestamp"],
                "source_timestamp_header": rec["source_timestamp_header"],
                "sha256": rec["sha256"], "blob": rec["blob"],
                "schema_fingerprint": rec["schema_fingerprint"],
                "n_rows": rec["n_rows"], "watch_id": watch_id,
            }, path=pathlib.Path(args.first_seen))
            rec["first_seen"] = {"state": fs.state.value, "code": fs.code}
            print(f"      first-seen: {fs.code}")

        if rec.get("availability") == AV.Availability.AVAILABLE.value \
                and not args.dry_run:
            v = AV.verify_record(rec)
            rec["verification"] = {"state": v.state.value, "code": v.code}
            if v.state is not State.PASS:
                print(f"      VERIFY {v.code}: {v.detail[:120]}")
                worst = 2
            el = AV.eligibility_record(rec)
            rec["predictive_eligibility"] = el
            print(f"      predictive eligibility: authorized="
                  f"{el['authorized']} ({el['authorization_code']})")

    if args.dry_run:
        print("\n--dry-run: nothing written")
        return 0

    manifest.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest, "a") as fh:                       # append-only
        for rec in rows:
            fh.write(json.dumps(rec, sort_keys=True) + "\n")
    print(f"\nappended {len(rows)} row(s) to {_rel(manifest)}")

    # A FAIL is a defect in a control. NOT_PUBLISHED and BLOCKED are states of
    # the world and of this executor, and neither is a failed run.
    return 1 if worst >= 2 else 0


if __name__ == "__main__":
    sys.exit(main())
