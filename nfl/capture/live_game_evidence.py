"""One game's pregame evidence set, assembled from the capture record. WS-L1.

WHAT THIS IS

A reader over `nfl/vintage_manifest.jsonl` and `nfl/vintage/`. It fetches
nothing, transforms nothing and stores nothing new: `capture_vintage.py` is
still the only thing that retrieves bytes. What this adds is the per-game,
per-cutoff VIEW that a forecast needs before it is allowed to run, and it is
built to refuse rather than to fill in.

THE FOUR PROPERTIES IT EXISTS TO ESTABLISH

1. CHRONOLOGY IS AN INPUT, NOT A DISCOVERY. `bundle()` takes `cutoff` and has
   no default. Selection runs through `nfl.production.nonqb.vintage_selector`,
   whose `resolve_as_of` raises rather than defaulting to "now" or "no bound",
   so there is no path through this module that reads the newest file on disk.
   Filesystem mtime is never consulted. The only ordering is the selector's
   `max(retrieved_at, content_sha256)` over lawful candidates.

2. A MIRROR MAY NOT OCCUPY A GOVERNING SLOT SILENTLY. Tonight the governing
   injury source (nfl.com) is refused by this executor's proxy and the
   nflverse `injuries` feed is the only injury evidence in hand. That feed is
   registered ARCHIVE, not OFFICIAL, and this module records the substitution
   as an explicit DOWNGRADE carrying the governing source's name, the exact
   refusal code, and what the mirror cannot answer. Being the only thing
   available is not a promotion.

3. AN ABSENT OFFICIAL SOURCE IS EVIDENCE. Every unreachable governing source
   gets a record with its URL and the transport's own refusal, taken from the
   capture manifest rather than from memory. A gap that is written down is a
   finding; a gap that is left out is a hole shaped exactly like a source that
   was never registered.

4. THE SPORTSBOOK IS EXCLUDED BY MEASUREMENT, NOT BY ASSERTION. The schedules
   file carries eight market columns and they are POPULATED for this game
   (away_moneyline, home_moneyline, spread_line, away_spread_odds,
   home_spread_odds, total_line, under_odds, over_odds). `market_exclusion()`
   does not claim they are absent -- it reads their real values out of the
   captured blob, then proves that no key AND NO VALUE of them appears anywhere
   in the object this module hands a forecast, and that
   `ingest.allowlist.assert_columns_allowed(..., Purpose.FORECAST)` refuses
   each one by name. A value scan is the half that matters: renaming a column
   defeats a key check and does not defeat this.

WHAT IT DELIBERATELY DOES NOT DO

It does not infer active status from omission, it does not treat a source's
silence as a negative observation, and it does not widen a cutoff to reach a
capture. `NoLawfulVintage` and a BLOCKED Outcome are the correct outputs when
the evidence at a cutoff is thin, and they are preferred to a bundle that looks
complete.
"""
from __future__ import annotations

import csv
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
from nfl.capture import registry as _registry  # noqa: E402
from nfl.ingest import allowlist as _allow  # noqa: E402
from nfl.production.nonqb import vintage_selector as _vs  # noqa: E402

SPEC_VERSION = "live-game-evidence-1"

MANIFEST = _REPO / "nfl" / "vintage_manifest.jsonl"
VINTAGE = _REPO / "nfl" / "vintage"

# The families a pregame forecast reads, and the order they are reported in.
# DECLARED, not discovered from what happens to be on disk: a source that
# vanishes must show up as a missing required family, not as a shorter list.
FAMILIES = ("schedules", "weekly_rosters", "depth_charts", "injuries")
REQUIRED = ("schedules", "weekly_rosters", "depth_charts")

# Governing sources, named with what they govern. A mirror standing in for one
# of these is a downgrade and is recorded as one.
GOVERNING = {
    "injuries": "official_injury_report",
    "inactives": "official_inactives",
    "transactions": "official_transactions",
}

# What the nflverse mirror CANNOT answer, stated once so no consumer has to
# work it out. These are the questions the official report exists to settle.
MIRROR_CEILING = (
    "The nflverse `injuries` feed is a weekly archive restatement, not the "
    "league's intraweek cascade. It keeps ONE row per player-week and the "
    "2025+ schema dropped `date_modified`, so no row-level clock survives: "
    "Wednesday's practice designation is overwritten rather than stored. It "
    "cannot answer (a) the club's filed practice participation on a named day, "
    "(b) the Friday game-status designation at the moment it was filed, or "
    "(c) inactives, which resolve Questionable to 0/1 at T-90 and appear in no "
    "form in this file. A player absent from it is not thereby active: "
    "omission is not an observation."
)


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _rows():
    if not MANIFEST.exists():
        return []
    out = []
    for line in MANIFEST.read_text().splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    return out


def _read_blob(rel: str) -> bytes:
    p = _REPO / rel
    if not p.exists():
        raise FileNotFoundError(rel)
    if p.name.endswith(".gz"):
        with gzip.open(p, "rb") as fh:
            return fh.read()
    return p.read_bytes()


# Fields that are properties of THE BYTES, not of the occasion on which they
# were observed. Two rows describing the same content hash must agree on every
# one of them, so a later re-observation may supply one the earlier row lacks.
# Everything not on this list -- every clock, every execution declaration --
# stays with the EARLIEST row, because those are properties of the observation.
_BYTE_PROPERTY_FIELDS = (
    "upstream_content_sha256", "persisted_content_sha256", "blob_file_sha256",
    "persisted_is_upstream_verbatim", "persisted_n_bytes", "sha256_is_of",
    "retention_ruling3", "retention_policy", "raw_blob", "raw_blob_durable",
    "raw_blob_content_sha256", "raw_blob_file_sha256", "raw_blob_n_bytes",
    "transformation", "upstream_n_bytes", "n_data_rows",
)


def _manifest_value(source: str, sha256: str):
    """The PASS row whose upstream digest is `sha256`, at its earliest sighting.

    Joined on content, never on position or on recency. The capture workflow
    writes a row every time it looks, so the same bytes carry many rows; the
    earliest is the tightest defensible bound on when they existed and it is
    the only one that can be conservative.

    ONE NARROW MERGE, AND IT IS NOT A RECENCY RULE. The manifest schema gained
    `persisted_content_sha256` and the Ruling 3 retention block partway through
    the season, so the earliest row for a given content hash can lack a digest
    that a later row -- describing THE SAME BYTES, matched on hash -- records.
    Those fields are properties of the bytes, so taking them from a later
    re-observation states nothing new about the world. Every clock stays with
    the earliest row. The merge is listed field by field in
    `_merged_byte_properties` so a reader can see exactly what was filled in
    and from which capture, rather than having to trust that it was narrow.
    """
    seen = []
    for r in _rows():
        if r.get("source") != source or r.get("state") != "PASS":
            continue
        v = r.get("value") or {}
        if v.get("sha256") != sha256 and v.get(
                "upstream_content_sha256") != sha256:
            continue
        seen.append((r.get("capture_id") or "", v))
    if not seen:
        return None
    seen.sort(key=lambda q: q[0])
    out = dict(seen[0][1])
    merged = {}
    for cid, v in seen[1:]:
        for k in _BYTE_PROPERTY_FIELDS:
            if out.get(k) in (None, {}, "") and v.get(k) not in (None, {}, ""):
                out[k] = v[k]
                merged[k] = cid
    out["_earliest_capture_id"] = seen[0][0]
    out["_n_rows_for_this_content"] = len(seen)
    out["_merged_byte_properties"] = merged
    return out


# ------------------------------------------------------------- retention
def retention_record(value: dict) -> dict:
    """Ruling 3, read back off a manifest row rather than assumed.

    Five things must survive: raw bytes, raw hash, transformation version,
    reduced artifact, reduced hash. The SIXTH field is the one that made the
    difference here -- whether the raw bytes' only home is gitignored. WS-L
    measured raw retention as "a property of which machine looked": 6 of 6
    Actions-only vintages lost their raw bytes and 7 of 7 seen elsewhere kept
    them. A sole gitignored home is not retention, so it is reported as a
    named state, not as a present-or-absent field.
    """
    ret = dict(value.get("retention_ruling3") or {})
    raw = ret.get("raw_bytes")
    raw_on_disk = bool(raw) and (_REPO / raw).exists()
    gitignored_only = ret.get("raw_home_is_gitignored_only")
    complete = bool(
        ret.get("raw_bytes") and ret.get("raw_hash")
        and ret.get("transformation_version") and raw_on_disk
        and gitignored_only is False and value.get("raw_blob_durable"))
    if complete:
        status = "RULING3_COMPLETE"
    elif not ret:
        # A capture taken before the retention block existed. Its bytes may be
        # perfectly fine; what is missing is the record that says so, and that
        # distinction is the whole point of a four-state answer.
        status = "RULING3_PREDATES_POLICY__RECORD_ABSENT"
    elif gitignored_only:
        status = "RULING3_UNSATISFIED_RAW_HOME_GITIGNORED_ONLY"
    elif not raw_on_disk:
        status = "RULING3_UNSATISFIED_RAW_BLOB_NOT_ON_DISK"
    else:
        status = "RULING3_INCOMPLETE"
    return {
        "status": status,
        "raw_bytes": raw,
        "raw_hash": ret.get("raw_hash"),
        "raw_blob_durable": value.get("raw_blob_durable"),
        "raw_bytes_present_on_disk": raw_on_disk,
        "raw_n_bytes": value.get("raw_blob_n_bytes"),
        "transformation_version": ret.get("transformation_version"),
        "transformation_code_sha256": (value.get("transformation") or {}).get(
            "code_sha256"),
        "reduced_artifact": ret.get("reduced_artifact"),
        "reduced_hash": ret.get("reduced_hash"),
        "raw_home_is_gitignored_only": gitignored_only,
        "retention_policy": value.get("retention_policy"),
    }


def verify_on_disk(value: dict) -> dict:
    """Re-hash what is stored. A row is not evidence until its bytes match it.

    Both objects are checked, because they are different objects: the persisted
    blob (a reduction, for two of the four families) and the raw upstream file.
    Either one failing is reported by name; a single boolean would make a
    missing raw file and a corrupted reduction look alike.
    """
    ret = value.get("retention_ruling3") or {}
    out = {}
    for label, rel, want in (
            ("persisted", value.get("blob"),
             value.get("persisted_content_sha256")),
            ("raw", ret.get("raw_bytes"), ret.get("raw_hash"))):
        if not rel or not want:
            # A ROW THAT PREDATES THE RETENTION POLICY IS NOT A CORRUPT ROW,
            # AND THE TWO MUST NOT RENDER THE SAME COLOUR. Rows written before
            # 2026-09-14 carry no `retention_ruling3` at all. Where the blob is
            # the upstream bytes verbatim, verifying the blob verifies the raw
            # artifact -- they are one object and the row says so. Where it is
            # a reduction, the raw bytes genuinely were not retained durably
            # and that is the historical evidence ceiling, recorded as such
            # rather than as a failure of this capture.
            if label == "raw" and value.get(
                    "persisted_is_upstream_verbatim") is True:
                out[label] = {
                    "state": "VERIFIED_AS_THE_SAME_OBJECT",
                    "blob": value.get("blob"),
                    "note": "commit_raw retains the upstream bytes verbatim, "
                            "so the persisted check above covers the raw "
                            "artifact; they are one object.",
                    "is_failure": False}
            elif label == "raw":
                out[label] = {
                    "state": "RAW_NOT_RETAINED__PREDATES_RULING3_POLICY",
                    "blob": None,
                    "note": "this capture predates the durable raw retention "
                            "(capture_vintage.RETENTION_POLICY). Its raw bytes "
                            "survive only in the gitignored ephemeral store, "
                            "if at all. A historical evidence ceiling, not a "
                            "defect in this bundle, and not repairable by "
                            "re-fetching -- a later fetch is different bytes.",
                    "is_failure": False}
            elif (rel and value.get("sha256")
                  and "persisted_uncompressed_bytes" in str(
                      value.get("sha256_is_of") or "")):
                # A row written before the two-digest schema. It carries ONE
                # digest and its own `sha256_is_of` states that the upstream
                # bytes ARE the persisted bytes -- the row's own statement,
                # not an assumption made here -- so that digest lawfully covers
                # the blob. Verified against it, under a state that names which
                # field was used so the weaker provenance is visible.
                try:
                    got = hashlib.sha256(_read_blob(rel)).hexdigest()
                except FileNotFoundError:
                    out[label] = {"state": "BLOB_NOT_ON_DISK", "blob": rel,
                                  "is_failure": True}
                    continue
                ok = got == value["sha256"]
                out[label] = {
                    "state": ("VERIFIED_VIA_UPSTREAM_DIGEST__ROW_PREDATES_"
                              "TWO_DIGEST_SCHEMA" if ok
                              else "DIGEST_MISMATCH"),
                    "blob": rel, "expected_sha256": value["sha256"],
                    "actual_sha256": got,
                    "digest_field_used": "sha256",
                    "authorised_by": value.get("sha256_is_of"),
                    "is_failure": not ok}
            else:
                out[label] = {"state": "ABSENT_FROM_ROW", "blob": rel,
                              "is_failure": True}
            continue
        try:
            got = hashlib.sha256(_read_blob(rel)).hexdigest()
        except FileNotFoundError:
            out[label] = {"state": "BLOB_NOT_ON_DISK", "blob": rel,
                          "is_failure": True}
            continue
        ok = got == want
        out[label] = {
            "state": "VERIFIED" if ok else "DIGEST_MISMATCH",
            "blob": rel, "expected_sha256": want, "actual_sha256": got,
            "is_failure": not ok}
    return out


# --------------------------------------------------------------- sources
def source_record(family: str, cutoff) -> dict:
    """One captured family at `cutoff`: everything a capture must preserve.

    SOURCE, URL, RAW BYTES, RAW HASH, PERSISTED HASH, RETRIEVED_AT,
    PUBLICATION/OBSERVATION TIME, FORECAST CUTOFF ELIGIBILITY, AUTHORITY.
    """
    spec = _registry.BY_NAME[family]
    sel = _vs.select(family, as_of=cutoff)
    lawful, rejected = _vs.candidates(family, as_of=cutoff)
    base = {
        "family": family,
        "source": family,
        "url": spec.url(2026),
        "required": family in REQUIRED,
        "authority": spec.authority.value,
        "authority_rank": spec.authority_rank,
        "source_status": spec.source_status.value,
        "executor_access": spec.executor_access.value,
        "serves_kinds": list(spec.serves_kinds),
        "durability": spec.durability,
        "cutoff": _vs.parse_ts(cutoff).isoformat(),
        "n_lawful_at_cutoff": len(lawful),
        "n_rejected_at_cutoff": len(rejected),
        "n_rejected_as_later_than_cutoff": sum(
            1 for r in rejected if r.chronology == _vs.REJECT_LATE),
        "selection_rule": "max(retrieved_at, content_sha256) over lawful",
        "forbidden_selection_inputs": [
            "filesystem mtime", "glob order", "filename order", "file size",
            "row count", "latest-on-disk"],
        "evidence_ceiling": _vs.FAMILIES[family]["ceiling"],
    }
    if sel.state is not State.PASS:
        base.update({
            "forecast_cutoff_eligibility": "NO_LAWFUL_VINTAGE_AT_CUTOFF",
            "state": sel.state.value, "code": sel.code,
            "detail": sel.detail,
            # Deliberately kept: "there was nothing" and "there were six and
            # every one of them is later than the cut" are different facts.
            "rejected": [r.record() for r in rejected[:6]],
        })
        return base

    v = sel.value
    row = _manifest_value(family, v.content_sha256) or {}
    ret = retention_record(row)
    base.update({
        "state": "PASS", "code": sel.code,
        "capture_id": v.capture_id,
        "blob": v.blob,
        "raw_bytes": ret["raw_bytes"],
        "raw_hash": ret["raw_hash"],
        "raw_n_bytes": ret["raw_n_bytes"],
        "upstream_content_sha256": row.get("upstream_content_sha256"),
        "persisted_content_sha256": row.get("persisted_content_sha256"),
        "blob_file_sha256": row.get("blob_file_sha256"),
        "upstream_n_bytes": row.get("upstream_n_bytes") or row.get("n_bytes"),
        "n_data_rows": row.get("n_data_rows"),
        "retrieved_at": v.retrieved_at,
        "observation_time": v.published_at,
        "observation_time_authority": v.published_authority,
        "observation_time_header": row.get("source_timestamp_header"),
        "effective_scope": row.get("effective_scope"),
        "transformation": row.get("transformation"),
        "retention_ruling3": ret,
        "artifact_verification": verify_on_disk(row),
        # THE ELIGIBILITY STATEMENT, and it is narrow on purpose. It says the
        # bytes were in hand at or before the cutoff. It does not say they are
        # sufficient, current, or authoritative -- `evidence_ceiling` and
        # `authority` are separate fields precisely so that a chronology pass
        # cannot be read as a quality pass.
        "forecast_cutoff_eligibility": "LAWFUL_AT_CUTOFF",
        "lawful_because": (
            f"retrieved_at {v.retrieved_at} <= cutoff "
            f"{_vs.parse_ts(cutoff).isoformat()}"),
    })
    return base


def probe(name: str, *, live: bool = True, timeout_s: int = 25) -> dict:
    """An unreachable official source, recorded as the finding it is.

    The manifest's own last attempt is the authority for WHAT HAPPENED, because
    it was written by the capture path rather than by this reader. A live probe
    is additional and is labelled as such: it confirms the refusal is current
    rather than remembered, and one probe is enough -- retrying a policy denial
    produces the same denial and spends a window.
    """
    spec = _registry.BY_NAME.get(name)
    if spec is None:
        return {"source": name, "state": "BLOCKED",
                "code": "SOURCE_NOT_IN_REGISTRY"}
    url = spec.url(2026)
    last = None
    for r in _rows():
        if r.get("source") == name and r.get("state") in (
                "BLOCKED", "FAIL", "DEFERRED", "PASS"):
            last = r
    rec = {
        "source": name,
        "url": url,
        "authority": spec.authority.value,
        "authority_rank": spec.authority_rank,
        "serves_kinds": list(spec.serves_kinds),
        "source_status": spec.source_status.value,
        "declared_executor_access": spec.executor_access.value,
        "registry_note": spec.note,
        "last_capture_attempt": None if last is None else {
            "capture_id": last.get("capture_id"),
            "state": last.get("state"), "code": last.get("code"),
            "detail": (last.get("detail") or "")[:300],
            "curl_exit_code": (last.get("evidence") or {}).get(
                "curl_exit_code"),
            "curl_stderr": (last.get("evidence") or {}).get("curl_stderr"),
            "proxy_refusal_status": (last.get("evidence") or {}).get(
                "proxy_refusal_status"),
            "http_code_reported": (last.get("evidence") or {}).get(
                "http_code_reported"),
        },
        # SAID EXPLICITLY. The source answering 200 elsewhere and this executor
        # being denied are different facts with different owners, and merging
        # them is how nfl.com got recorded as globally unreachable.
        "interpretation": (
            "The SOURCE is not known to be down. THIS executor is refused at "
            "the egress proxy. Those are different facts and only the second "
            "is ours."),
        "is_evidence_not_a_gap": True,
        "may_be_inferred_from_absence": False,
    }
    if not live or not url:
        rec["live_probe"] = {"state": "NOT_ATTEMPTED",
                             "reason": "no url" if not url else "not requested"}
        return rec
    started = _now()
    try:
        r = subprocess.run(
            ["curl", "-sS", "-o", "/dev/null", "-w", "%{http_code}",
             "--max-time", str(timeout_s), url],
            capture_output=True, text=True, timeout=timeout_s + 15)
        code = (r.stdout or "").strip() or "000"
        err = (r.stderr or "").strip()[:300]
    except subprocess.TimeoutExpired:
        code, err, r = "000", "curl timed out", None
    import re as _re
    m = _re.search(r"response (\d{3})", err or "")
    rec["live_probe"] = {
        "state": "REACHED" if code.startswith("2") else "REFUSED",
        "probed_at": started,
        "http_code_reported": code,
        "curl_exit_code": None if r is None else r.returncode,
        "curl_stderr": err or None,
        "proxy_refusal_status": m.group(1) if m else None,
        "probed_once": True,
        "retry_policy": "none -- a policy denial repeats, and retrying spends "
                        "the window it is denying",
    }
    return rec


def downgrades(records: dict, probes: dict) -> list:
    """Where a mirror is standing in for a governing source. Never silent."""
    out = []
    for slot, gov in GOVERNING.items():
        p = probes.get(gov) or {}
        available = (p.get("live_probe") or {}).get("state") == "REACHED"
        if available:
            continue
        stand_in = None
        if slot == "injuries" and records.get("injuries", {}).get(
                "state") == "PASS":
            stand_in = "injuries"
        out.append({
            "slot": slot,
            "governing_source": gov,
            "governing_authority": _registry.BY_NAME[gov].authority.value,
            "governing_available_to_this_executor": False,
            "governing_refusal": (p.get("live_probe") or {}).get(
                "proxy_refusal_status")
                or (p.get("last_capture_attempt") or {}).get("code"),
            "stand_in_source": stand_in,
            "stand_in_authority": (
                _registry.BY_NAME[stand_in].authority.value
                if stand_in else None),
            "status": ("DOWNGRADED__MIRROR_IN_A_GOVERNING_SLOT" if stand_in
                       else "UNFILLED__NO_SOURCE_OF_ANY_AUTHORITY"),
            "ceiling": MIRROR_CEILING if stand_in else (
                f"No source of any authority covers {slot} at this cutoff. "
                f"The correct downstream response is to refuse the claim, not "
                f"to substitute a source that answers a different question."),
            "authority_promotion": False,
            "authority_promotion_note": (
                "Being the only source in hand is not a promotion. The "
                "stand-in keeps its registered authority and the governing "
                "slot is recorded as unfilled by an OFFICIAL source."),
        })
    return out


# ---------------------------------------------------- the market exclusion
def market_exclusion(game_row: dict, emitted: dict) -> dict:
    """Prove the sportsbook columns cannot reach the forecast. By measurement.

    Three independent checks, because each alone is defeatable:

      KEY      no quarantined column name appears among the emitted keys.
      VALUE    no quarantined column's ACTUAL VALUE for this game appears
               anywhere in the emitted object, at any depth, under any name.
               This is the check that survives a rename.
      GATE     `allowlist.assert_columns_allowed(..., Purpose.FORECAST)`
               refuses each column by name, and clears the ones actually
               emitted.

    `game_row` is the raw schedules row so the values are read, not recalled.
    For 2026_01_DEN_KC they are populated -- this is not a vacuous proof over
    empty fields.
    """
    q = _allow.quarantined_columns("schedules")
    market = sorted(c for c, cat in q.items()
                    if cat is _allow.Category.MARKET)
    values = {c: game_row.get(c) for c in market}
    populated = {c: v for c, v in values.items() if v not in (None, "")}
    # THE PROOF MAY NOT SHIP THE THING IT IS EXCLUDING.
    #
    # An earlier version put the real market values into this record so the
    # proof could be seen to be non-vacuous. That put "43.5" and "-130" inside
    # the very object the scan certifies as market-free -- an audit block is
    # still part of the artifact a consumer walks, and a rule against the
    # sportsbook reaching a forecast is not satisfied by the sportsbook
    # arriving under the heading "proof that the sportsbook did not arrive".
    # It also made the record un-closed: re-running the scan over the finished
    # bundle found its own evidence and reported a leak.
    #
    # Digests keep the proof checkable -- anyone holding the captured file can
    # recompute them -- without restating the price.
    # AND THE AUDIT BLOCK MAY NOT USE THE COLUMN NAMES AS KEYS EITHER.
    #
    # Keying these maps by the bare column name put `spread_line` and
    # `total_line` into the emitted key set, so the closure scan below found
    # the proof's own bookkeeping and reported a leak. Adding an exception for
    # "our own audit block" would have been the wrong repair -- an exception is
    # exactly where a real leak would later hide. Prefixing makes the whole
    # object scannable under ONE rule with no carve-out.
    _K = "quarantined_column:"
    digests = {f"{_K}{c}": hashlib.sha256(str(v).encode()).hexdigest()
               for c, v in populated.items()}

    emitted_keys, emitted_values = set(), []

    def _walk(node, path=""):
        if isinstance(node, dict):
            for k, v in node.items():
                emitted_keys.add(str(k))
                _walk(v, f"{path}.{k}")
        elif isinstance(node, (list, tuple)):
            for i, v in enumerate(node):
                _walk(v, f"{path}[{i}]")
        else:
            emitted_values.append((path, node))

    _walk(emitted)

    key_hits = sorted(emitted_keys & set(market))
    # Compared as strings, normalised, because a value that survived a float
    # round-trip is the same leak. Only POPULATED values are scanned: an empty
    # string matches everything and would make the check meaningless.
    wanted = {str(v).strip(): c for c, v in populated.items()}
    value_hits = []
    for path, node in emitted_values:
        if node is None:
            continue
        s = str(node).strip()
        if s in wanted:
            value_hits.append({"path": path, "value": s,
                               "matches_column": wanted[s]})

    gate = {}
    for c in market:
        o = _allow.assert_columns_allowed("schedules", [c],
                                          _allow.Purpose.FORECAST)
        gate[f"{_K}{c}"] = {"state": o.state.value, "code": o.code,
                            "category": o.evidence.get("category")}
    emitted_schedule_cols = sorted(
        set((emitted.get("game") or {}).keys()))
    cleared = _allow.assert_columns_allowed(
        "schedules", emitted_schedule_cols, _allow.Purpose.FORECAST)

    ok = (not key_hits and not value_hits
          and all(g["state"] == "FAIL" for g in gate.values())
          and cleared.state is State.PASS and bool(populated))
    return {
        "market_columns_declared": market,
        # Populated-or-not, and a digest. Never the value; see above.
        "market_columns_populated_for_this_game": {
            f"{_K}{c}": (v not in (None, "")) for c, v in values.items()},
        "audit_key_prefix": _K,
        "market_value_sha256": digests,
        "market_values_are_not_reproduced_here": (
            "deliberate. The digest is recomputable from the captured file by "
            "anyone auditing this; restating the price inside the artifact "
            "the forecast reads is the leak, not the audit."),
        "n_populated_for_this_game": len(populated),
        "proof_is_vacuous": not populated,
        "key_check": {"hits": key_hits,
                      "n_emitted_keys_scanned": len(emitted_keys)},
        "value_check": {"hits": value_hits,
                        "n_emitted_values_scanned": len(emitted_values),
                        "note": "a value scan is what survives a rename; a key "
                                "check alone does not"},
        "gate_check": gate,
        "emitted_schedule_columns": emitted_schedule_cols,
        "emitted_columns_cleared_for_forecast": {
            "state": cleared.state.value, "code": cleared.code},
        "posthoc_and_outcome_also_excluded": sorted(
            c for c, cat in q.items() if cat is not _allow.Category.MARKET),
        "verdict": "MARKET_PROVABLY_EXCLUDED" if ok else "NOT_PROVEN",
        "captured_not_consumed": (
            "The market columns ARE captured -- they are inside the schedules "
            "file and the file is retained verbatim. Ruling 3 retention and "
            "forecast quarantine are different obligations and this is the "
            "line between them: the bytes are kept, and nothing that reaches a "
            "forecast carries them."),
    }


# ------------------------------------------------------------- the bundle
def game_identity(game_id: str, cutoff) -> Outcome:
    """The game's own row, from the schedules vintage lawful at `cutoff`.

    FORECAST-SAFE COLUMNS ONLY. Built with `forecast_safe_columns`, which
    RAISES on an undeclared source rather than returning everything, so the
    market columns cannot arrive by way of a name the quarantine has never
    heard of.
    """
    sel = _vs.select("schedules", as_of=cutoff)
    if sel.state is not State.PASS:
        return sel
    blob = sel.value.blob
    text = _read_blob(blob).decode("utf-8", "replace")
    rows = [r for r in csv.DictReader(io.StringIO(text))
            if r.get("game_id") == game_id]
    if not rows:
        return Outcome.fail(
            "GAME_NOT_IN_SCHEDULE_VINTAGE",
            f"{game_id} does not appear in {blob}, the schedules vintage "
            f"lawful at the cutoff. A game that is not in the schedule we "
            f"hold is not a game we may forecast.",
            game_id=game_id, blob=blob)
    if len(rows) > 1:
        return Outcome.fail(
            "GAME_ID_NOT_UNIQUE",
            f"{game_id} appears {len(rows)} times in {blob}.",
            game_id=game_id, blob=blob, n=len(rows))
    raw = rows[0]
    safe = _allow.forecast_safe_columns("schedules", list(raw.keys()))
    return Outcome.ok(
        "GAME_IDENTITY",
        value={"raw": raw, "safe": {c: raw[c] for c in safe},
               "blob": blob, "safe_columns": safe},
        detail=f"{game_id} from {blob}: {len(safe)} of {len(raw)} columns "
               f"are forecast-safe", game_id=game_id)


def earliest_lawful_cutoff(cutoff) -> dict:
    """The earliest cutoff at which every REQUIRED family has a vintage.

    It is the MAXIMUM of the required families' earliest retrievals, which is
    the awkward direction and the right one: a cutoff earlier than that leaves
    at least one required source with nothing lawful, and the honest response
    to that is a refusal rather than a forecast built on three of four inputs.
    """
    per, missing = {}, []
    for fam in REQUIRED:
        lawful, _ = _vs.candidates(fam, as_of=cutoff)
        if not lawful:
            missing.append(fam)
            continue
        earliest = min(v.retrieved_at for v in lawful if v.retrieved_at)
        per[fam] = earliest
    if missing:
        return {"state": "BLOCKED", "code": "REQUIRED_FAMILY_HAS_NO_VINTAGE",
                "missing_required": missing, "per_family_earliest": per}
    floor = max(per.values())
    return {
        "state": "PASS",
        "code": "EARLIEST_LAWFUL_CUTOFF",
        "earliest_lawful_cutoff_utc": floor,
        "binding_family": [f for f, t in per.items() if t == floor],
        "per_family_earliest_retrieved_at": per,
        "rule": ("max over required families of the earliest lawful retrieval. "
                 "A cutoff below this leaves a required family empty, and an "
                 "empty required family is a refusal, not a smaller forecast."),
        "required_families": list(REQUIRED),
    }


def bundle(game_id: str, cutoff, *, live_probe: bool = True) -> Outcome:
    """Everything preserved for one game at one explicit cutoff.

    `cutoff` has NO DEFAULT and is not optional. A selector without a clock
    takes the newest capture on disk, which is how a post-kickoff injury report
    reached a pregame forecast for 28 of 32 week-1 teams.
    """
    cut = _vs.parse_ts(cutoff)
    if cut is None:
        return Outcome.fail(
            "CUTOFF_UNPARSEABLE",
            f"cutoff={cutoff!r} is not an ISO-8601 instant. A cutoff is an "
            f"input to this function and there is deliberately no default: "
            f"defaulting it is what a chronology guard exists to prevent.")

    ident = game_identity(game_id, cut)
    if ident.state is not State.PASS:
        return ident

    records = {f: source_record(f, cut) for f in FAMILIES}
    probes = {g: probe(g, live=live_probe) for g in GOVERNING.values()}
    down = downgrades(records, probes)

    kickoff = None
    raw = ident.value["raw"]
    if raw.get("gameday") and raw.get("gametime"):
        from nfl.capture.schedule import _parse_kick
        kickoff = _parse_kick(raw["gameday"], raw["gametime"])

    emitted = {
        "spec_version": SPEC_VERSION,
        "generated_at": _now(),
        "game_id": game_id,
        "cutoff_utc": cut.isoformat(),
        "cutoff_is_an_explicit_input": True,
        "kickoff_utc": kickoff.isoformat() if kickoff else None,
        "cutoff_is_pregame": (None if kickoff is None else cut < kickoff),
        "game": ident.value["safe"],
        "game_identity_blob": ident.value["blob"],
        "sources": records,
        "unreachable_official_sources": probes,
        "authority_downgrades": down,
        "earliest_lawful_cutoff": earliest_lawful_cutoff(cut),
    }
    emitted["market_exclusion"] = market_exclusion(raw, emitted)
    # CLOSED UNDER ITS OWN SCAN. The proof above was computed over the bundle
    # BEFORE the proof was attached, which is the right scope for the scan and
    # the wrong scope for the guarantee: the object a consumer actually
    # receives includes the audit block. Re-running the scan over the finished
    # object is what makes the guarantee cover what is handed over. It is a
    # separate field rather than a replacement so that a future edit which
    # reintroduces a value into the audit block fails loudly here instead of
    # quietly widening what "excluded" means.
    _closure = market_exclusion(raw, emitted)
    emitted["market_exclusion"]["closure_check"] = {
        "scope": "the COMPLETE emitted object, audit block included",
        "verdict": _closure["verdict"],
        "key_hits": _closure["key_check"]["hits"],
        "value_hits": _closure["value_check"]["hits"],
        "n_values_scanned": _closure["value_check"]["n_emitted_values_scanned"],
    }
    if _closure["verdict"] != "MARKET_PROVABLY_EXCLUDED":
        emitted["market_exclusion"]["verdict"] = "NOT_PROVEN_UNDER_CLOSURE"

    missing = [f for f in REQUIRED
               if records[f].get("forecast_cutoff_eligibility")
               != "LAWFUL_AT_CUTOFF"]
    # A FAILURE, NOT MERELY A NON-PASS. `is_failure` is set per check, so a
    # row that predates the retention policy reports its ceiling without
    # being counted as a corrupted artifact. Collapsing those two would make
    # every historical capture look broken and would hide a real mismatch in
    # the noise.
    unverified = sorted(
        f for f in FAMILIES
        if records[f].get("state") == "PASS"
        and any(x.get("is_failure")
                for x in (records[f].get("artifact_verification") or {}
                          ).values()))
    ceilings = sorted(
        f"{f}:{k}={x['state']}" for f in FAMILIES
        for k, x in (records[f].get("artifact_verification") or {}).items()
        if not x.get("is_failure") and x.get("state") != "VERIFIED")
    emitted["completeness"] = {
        "required_families": list(REQUIRED),
        "required_missing_at_cutoff": missing,
        "families_with_unverified_artifacts": unverified,
        "evidence_ceilings_not_failures": ceilings,
        "retention_by_family": {
            f: (records[f].get("retention_ruling3") or {}).get("status")
            for f in FAMILIES},
    }

    if missing:
        return Outcome.blocked(
            "EVIDENCE_INCOMPLETE_AT_CUTOFF",
            f"{game_id}: required famil(ies) {missing} have no lawful vintage "
            f"at {cut.isoformat()}. Widening the cutoff to reach one is the "
            f"defect this refuses.",
            cause=Cause.DATA, value=emitted, game_id=game_id,
            cutoff=cut.isoformat(), missing=missing)
    if emitted["market_exclusion"]["verdict"] != "MARKET_PROVABLY_EXCLUDED":
        return Outcome.fail(
            "MARKET_EXCLUSION_NOT_PROVEN",
            f"{game_id}: the sportsbook columns could not be proven excluded "
            f"from the emitted bundle. Refusing to hand it to a forecast.",
            value=emitted, game_id=game_id,
            key_hits=emitted["market_exclusion"]["key_check"]["hits"],
            value_hits=emitted["market_exclusion"]["value_check"]["hits"])
    if unverified:
        return Outcome.fail(
            "ARTIFACT_VERIFICATION_FAILED",
            f"{game_id}: {unverified} have manifest rows whose digests do not "
            f"match the bytes on disk.",
            value=emitted, game_id=game_id, families=unverified)

    return Outcome.ok(
        "LIVE_GAME_EVIDENCE",
        value=emitted,
        detail=f"{game_id} at {cut.isoformat()}: {len(FAMILIES)} families, "
               f"{len(down)} authority downgrade(s), market provably excluded",
        game_id=game_id, cutoff=cut.isoformat(),
        n_downgrades=len(down))


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--game-id", required=True)
    ap.add_argument("--cutoff", required=True,
                    help="ISO-8601 UTC instant. No default, deliberately.")
    ap.add_argument("--out", default=None)
    ap.add_argument("--no-live-probe", action="store_true")
    a = ap.parse_args()

    out = bundle(a.game_id, a.cutoff, live_probe=not a.no_live_probe)
    payload = out.value if out.value is not None else out.evidence.get("value")
    if a.out and payload:
        p = _REPO / a.out
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(payload, indent=1, sort_keys=True) + "\n")
        print(f"wrote {a.out}")
    print(f"{out.state.value}[{out.code}] {out.detail}")
    if payload:
        for f, r in payload["sources"].items():
            print(f"  {f:<16}{r.get('forecast_cutoff_eligibility'):<28}"
                  f"{r.get('authority',''):<20}"
                  f"retrieved={r.get('retrieved_at')}")
        for d in payload["authority_downgrades"]:
            print(f"  DOWNGRADE {d['slot']:<14}{d['status']}")
        print(f"  market: {payload['market_exclusion']['verdict']}")
        print(f"  earliest lawful cutoff: "
              f"{payload['earliest_lawful_cutoff'].get('earliest_lawful_cutoff_utc')}")
    return 0 if out.state is State.PASS else 1


if __name__ == "__main__":
    sys.exit(main())
